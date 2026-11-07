"""DEV-16 commercial recovery tests.

These methods are bound onto TestDev12InvoiceAudit so they share that
class chart, users, and concurrency pool. They are not a second chart load.
"""
import logging
import sys
import threading
import time
import traceback
from decimal import Decimal

from odoo import Command, api, fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import Manifest
from odoo.orm.registry import DummyRLock, Registry
from odoo.tests.common import new_test_user

from odoo.addons.contract_price_leakage_auditor.tests.test_invoice_audit import (
    MODULE,
    TestDev12InvoiceAudit,
    _POOL_CLEAR_SQL,
    _money,
)


def _rec_level(kind, sequence=1, ceiling='100000'):
    return {
        'name': 'Contract Manager',
        'action_kind': kind,
        'level_sequence': sequence,
        'authority_group': 'contract_manager',
        'applies_from_exact': '0',
        'has_ceiling': True,
        'maximum_exact': ceiling,
    }


def _rec_env(self, user=None):
    return self._env(user or self.manager, self.company_a)


def _rec_moves(self):
    company = self.company_a
    return (
        self.env['account.move'].search_count([('company_id', '=', company.id)]),
        self.env['account.payment'].search_count([('company_id', '=', company.id)]),
    )


def _rec_equation(self, position):
    validated = _money(position['validated'])
    waiver = _money(position['waiver'])
    target = _money(position['recovery_target'])
    unallocated = _money(position['unallocated'])
    self.assertEqual(validated, waiver + target + unallocated, position)
    self.assertEqual(_money(position['billed']), Decimal('0'), position)
    self.assertEqual(_money(position['collected']), Decimal('0'), position)
    disputed = _money(position['disputed'])
    acknowledged = _money(position['acknowledged'])
    self.assertGreaterEqual(target, disputed + acknowledged, position)
    self.assertEqual(
        _money(position['unanswered']),
        target - disputed - acknowledged,
        position,
    )


def _rec_policy(self, ceiling='100000', levels=None, currency=None, four_eyes=True):
    """Approve a commercial matrix. ``ceiling`` is a fixture, not a seeded limit."""
    company = self.company_a
    env = self._env(self.manager, company)
    policy = env['cpla.recovery.policy'].create({
        'company_id': company.id,
        'name': 'Commercial recovery matrix',
        'currency_id': (currency or company.currency_id).id,
        'four_eyes_required': four_eyes,
        'dispute_blocks_handoff': True,
        'change_reason': 'Test commercial matrix. This ceiling is a fixture, not a seeded limit.',
    })
    specs = levels or [
        _rec_level(kind, ceiling=ceiling)
        for kind in ('recovery', 'waiver', 'settlement', 'handoff')
    ]
    for spec in specs:
        env['cpla.recovery.policy.level'].create(dict(spec, policy_id=policy.id))
    env['cpla.recovery.policy'].browse(policy.id).action_approve_policy()
    self.env.invalidate_all()
    return self.env['cpla.recovery.policy'].browse(policy.id)


def _rec_validated(self, quantity=500, partial=None):
    """Finance-approve one posted underbilling. The approval is not recovery."""
    self._fv_policy(partial=bool(partial), ceiling='100000')
    ready = self._fv_ready(quantity)
    record = self._fv_prepare(ready['case'])
    if partial:
        validated, rejected, unresolved = partial
        decisions = [
            self._fv_decision(
                line, validated, rejected, unresolved, 'PARTIALLY_SUPPORTED',
                'Only the supported portion is validated. The rest is not a waiver.',
            )
            for line in record.line_ids
        ]
    else:
        decisions = self._fv_full_decisions(record)
    record = self._fv_pending(record, decisions)
    self._fv_as(record, self.finance).action_approve(
        'Finance validates the supported amount. This is not recovery authority.'
    )
    record = self._fv_record(record)
    payload = record.decision_payload()
    self.assertFalse(payload['recovery_authority'])
    self.assertFalse(payload['creates_customer_receivable'])
    self.assertFalse(payload['proves_cash_collection'])
    self.assertFalse(payload['is_waiver'])
    self.assertFalse(payload['is_recovery_billed'])
    self.assertFalse(payload['is_cash_recovered'])
    self.assertFalse(record.is_waiver)
    self.assertFalse(record.is_recovery_billed)
    self.assertFalse(record.is_cash_recovered)
    return record


def _rec_request(self, validation, amount=None, force_new=False, user=None):
    env = self._env(user or self.manager, validation.company_id)
    amounts = None
    if amount is not None:
        line = validation.line_ids.filtered(
            lambda item: item.counts_current and _money(item.approved_validated_exact) > 0
        )[:1]
        self.assertTrue(line)
        amounts = {line.id: amount}
    request = env['cpla.recovery.request'].prepare_from_validation(
        validation.id, amounts, force_new=force_new,
    )
    self.env.invalidate_all()
    return self.env['cpla.recovery.request'].browse(request.id)


def _rec_submit(self, request, user=None):
    env = self._env(user or self.manager, request.company_id)
    record = env['cpla.recovery.request'].browse(request.id)
    if record.state == 'draft':
        record.action_submit()
        record = env['cpla.recovery.request'].browse(request.id)
    if record.state in ('submitted', 'under_review'):
        record.action_request_approval()
    self.env.invalidate_all()
    return self.env['cpla.recovery.request'].browse(request.id)


def _rec_approve_request(self, request, user):
    self._env(user, request.company_id)['cpla.recovery.request'].browse(request.id).action_approve(
        'Commercial recovery approval. This is not an invoice and not collected cash.'
    )
    self.env.invalidate_all()
    return self.env['cpla.recovery.request'].browse(request.id)


def _rec_waiver(self, validation, amount, request_line=None, reduces=False, settlement=None, user=None):
    line = validation.line_ids.filtered(
        lambda item: item.counts_current and _money(item.approved_validated_exact) > 0
    )[:1]
    self.assertTrue(line)
    env = self._env(user or self.manager, validation.company_id)
    waiver = env['cpla.recovery.waiver'].prepare(
        line.id,
        amount,
        'relationship_preservation',
        'Documented commercial reason for this fixture.',
        request_line_id=request_line.id if request_line else None,
        reduces_recovery=reduces,
        settlement_id=settlement.id if settlement else None,
    )
    self.env.invalidate_all()
    return self.env['cpla.recovery.waiver'].browse(waiver.id)


def _rec_submit_waiver(self, waiver):
    env = self._env(self.manager, waiver.company_id)
    record = env['cpla.recovery.waiver'].browse(waiver.id)
    if record.state == 'draft':
        record.action_submit()
        record = env['cpla.recovery.waiver'].browse(waiver.id)
    if record.state == 'submitted':
        record.action_request_approval()
    self.env.invalidate_all()
    return self.env['cpla.recovery.waiver'].browse(waiver.id)


def _rec_approve_waiver(self, waiver, user=None):
    waiver = self._rec_submit_waiver(waiver)
    approver = user or self.commercial
    self._env(approver, waiver.company_id)['cpla.recovery.waiver'].browse(waiver.id).action_approve(
        'Commercial waiver approval. This is not a finance rejection or a write-off.'
    )
    self.env.invalidate_all()
    return self.env['cpla.recovery.waiver'].browse(waiver.id)


def _rec_position(self, validation):
    self.env.invalidate_all()
    return self.env['cpla.recovery.balance'].position_for(
        self.env['cpla.finance.validation'].browse(validation.id)
    )


def _rec_line(self, request):
    line = request.line_ids[:1]
    self.assertTrue(line)
    return line


def test_rec16_views_and_no_accounting(self):
    """Menus, sequences, and alerts load. No cron and no seeded ceiling."""
    manifest = Manifest.for_addon(MODULE)
    self.assertEqual(manifest['version'], '19.0.1.15.0')
    self.assertIn('views/recovery_views.xml', manifest['data'])
    self.assertIn('security/recovery_rules.xml', manifest['data'])
    self.assertIn('data/recovery_sequence.xml', manifest['data'])
    expected = {
        'seq_cpla_recovery_policy': 'CPL-RCP/%(year)s/',
        'seq_cpla_recovery_request': 'CPL-REC/%(year)s/',
        'seq_cpla_recovery_waiver': 'CPL-WAV/%(year)s/',
        'seq_cpla_recovery_dispute': 'CPL-DSP/%(year)s/',
        'seq_cpla_recovery_settlement': 'CPL-SET/%(year)s/',
    }
    for xmlid, prefix in expected.items():
        sequence = self.env.ref('%s.%s' % (MODULE, xmlid))
        self.assertEqual(sequence.prefix, prefix)
        self.assertEqual(sequence.padding, 5)
        self.assertFalse(sequence.company_id)
    finance_form = self.env.ref(MODULE + '.view_cpla_finance_validation_form').arch
    self.assertIn('DEV-16 handoff', finance_form)
    self.assertIn('Prepare Recovery Request', finance_form)
    self.assertIn('not an invoice and is not collected cash', finance_form)
    self.assertNotIn('Recovered', finance_form.replace('not recovered cash', ''))
    request_form = self.env.ref(MODULE + '.view_cpla_recovery_request_form').arch
    self.assertIn('not a posted invoice and is not collected cash', request_form)
    self.assertIn('does not create an invoice, a debit note, or a payment', request_form)
    waiver_form = self.env.ref(MODULE + '.view_cpla_recovery_waiver_form').arch
    self.assertIn('not a finance rejection', waiver_form)
    self.assertIn('does not post an accounting write-off', waiver_form)
    dispute_form = self.env.ref(MODULE + '.view_cpla_recovery_dispute_form').arch
    self.assertIn('does not reduce that target', dispute_form)
    self.assertIn('does not send a customer email', dispute_form)
    settlement_form = self.env.ref(MODULE + '.view_cpla_recovery_settlement_form').arch
    self.assertIn('Internal approval is not customer acceptance', settlement_form)
    policy_form = self.env.ref(MODULE + '.view_cpla_recovery_policy_form').arch
    self.assertIn('No approval amount is seeded', policy_form)
    for model_name in (
        'cpla.recovery.request',
        'cpla.recovery.waiver',
        'cpla.recovery.dispute',
        'cpla.recovery.settlement',
        'cpla.recovery.policy',
    ):
        self.env[model_name].get_view(view_type='form')
    parent = self.env.ref(MODULE + '.menu_cpla_recovery')
    children = self.env['ir.ui.menu'].search([('parent_id', '=', parent.id)])
    self.assertEqual(len(children), 22)
    auditor = self.env.ref(MODULE + '.group_internal_auditor')
    operator = self.env.ref(MODULE + '.group_recovery_operator')
    admin = self.env.ref(MODULE + '.group_app_admin')
    for menu in children | parent:
        self.assertIn(menu, auditor.menu_access)
        self.assertNotIn(menu, operator.menu_access)
        self.assertNotIn(menu, admin.menu_access)
    self.assertFalse(self.env['ir.model.data'].search([
        ('module', '=', MODULE),
        ('model', 'in', ('ir.cron', 'ir.actions.server', 'ir.actions.report')),
    ]))
    env = self._env(self.manager, self.company_a)
    policy = env['cpla.recovery.policy'].create({
        'company_id': self.company_a.id,
        'name': 'Empty ceiling',
        'currency_id': self.company_a.currency_id.id,
        'change_reason': 'A ceiling was not entered.',
    })
    env['cpla.recovery.policy.level'].create({
        'policy_id': policy.id,
        'name': 'Contract Manager',
        'action_kind': 'waiver',
        'level_sequence': 1,
        'authority_group': 'contract_manager',
        'applies_from_exact': '0',
        'has_ceiling': True,
    })
    self._fv_error(
        lambda: env['cpla.recovery.policy'].browse(policy.id).action_approve_policy(),
        'APPROVAL_MATRIX_MISSING',
    )
    self._fv_error(
        lambda: self._env(self.admin, self.company_a)['cpla.recovery.request'].prepare_from_validation(1),
        'APPROVAL_MATRIX_MISSING',
    )
    operator_user = new_test_user(
        self.env, login='cpla16_operator', password='cpla-test',
        groups='base.group_user,%s.group_recovery_operator' % MODULE,
        company_id=self.company_a.id, company_ids=[Command.set([self.company_a.id])],
    )
    self._fv_error(
        lambda: self._env(operator_user, self.company_a)['cpla.recovery.request'].prepare_from_validation(1),
        'COMMERCIAL_AUTHORITY_DENIED',
    )


def test_rec16_full_recovery_and_partial_waiver(self):
    """GOLD-REC16-001 and GOLD-REC16-019. Approval is not billing or cash."""
    started = time.perf_counter()
    validation = self._rec_validated(500)
    self._rec_policy(levels=[
        _rec_level('recovery', 1),
        _rec_level('recovery', 2),
        _rec_level('waiver', 1),
        _rec_level('settlement', 1),
        _rec_level('handoff', 1),
    ])
    request = self._rec_request(validation)
    self._assert_amount(request.requested_amount_exact, '25000')
    self._assert_amount(request.approved_recovery_exact, '0')
    case = self.env['cpla.leakage.case'].browse(request.case_id.id)
    followers = set(case.message_partner_ids.ids)
    mails = self.env['mail.mail'].search_count([])
    moves = self._rec_moves()
    request = self._rec_submit(request)
    self.assertEqual(request.state, 'pending_approval')
    self.assertEqual(self.env['mail.mail'].search_count([]), mails)
    case = self.env['cpla.leakage.case'].browse(case.id)
    self.assertEqual(set(case.message_partner_ids.ids), followers)
    activity = self.env['mail.activity'].search([
        ('res_model', '=', 'cpla.leakage.case'),
        ('res_id', '=', case.id),
        ('summary', '=', 'Review recovery request'),
    ])
    self.assertTrue(activity)
    self.assertNotIn('25000', activity.note or '')
    self._fv_error(
        lambda: self._rec_approve_request(request, self.manager),
        'SELF_APPROVAL_PROHIBITED',
    )
    self._fv_error(
        lambda: self._rec_approve_request(request, self.finance),
        'APPROVAL_LIMIT_EXCEEDED',
    )
    request = self._rec_approve_request(request, self.commercial)
    self.assertEqual(request.state, 'pending_approval')
    self._assert_amount(request.current_recovery_exact, '0')
    self._fv_error(
        lambda: self._rec_approve_request(request, self.commercial),
        'SELF_APPROVAL_PROHIBITED',
    )
    request = self._rec_approve_request(request, self.commercial_b)
    self.assertEqual(request.state, 'approved')
    self._assert_amount(request.approved_recovery_exact, '25000')
    self._assert_amount(request.current_recovery_exact, '25000')
    request = self._rec_approve_request(request, self.commercial_b)
    self.assertEqual(len(request.event_ids.filtered(
        lambda event: event.event_type == 'recovery_level_approved' and event.level_sequence > 0
    )), 2)
    position = self._rec_position(validation)
    self._rec_equation(position)
    self._assert_amount(position['validated'], '25000')
    self._assert_amount(position['waiver'], '0')
    self._assert_amount(position['recovery_target'], '25000')
    self._assert_amount(position['unallocated'], '0')
    blocked = request.accounting_handoff_payload()
    self.assertEqual(blocked['status'], 'NOT_READY_WITH_REASONS')
    self.assertFalse(blocked['creates_account_move'])
    payload = self._env(self.commercial, self.company_a)['cpla.recovery.request'].browse(
        request.id
    ).action_authorize_handoff('Authorize accounting to read this allocation. Do not post it here.')
    self.assertEqual(payload['status'], 'READY_FOR_ACCOUNTING')
    self.assertTrue(payload['handoff_key'])
    self.assertFalse(payload['creates_account_move'])
    self.assertFalse(payload['creates_customer_receivable'])
    self.assertFalse(payload['proves_cash_collection'])
    self._assert_amount(payload['billed_amount'], '0')
    self._assert_amount(payload['collected_amount'], '0')
    self._assert_amount(payload['authorized_amount'], '25000')
    repeat = self._env(self.commercial, self.company_a)['cpla.recovery.request'].browse(
        request.id
    ).action_authorize_handoff('Repeat the same handoff.')
    self.assertEqual(repeat['handoff_key'], payload['handoff_key'])
    request = self.env['cpla.recovery.request'].browse(request.id)
    self.assertEqual(len(request.event_ids.filtered(
        lambda event: event.event_type == 'handoff_authorized'
    )), 1)
    self._assert_amount(request.billed_amount_exact, '0')
    self._assert_amount(request.collected_amount_exact, '0')
    self.assertEqual(self._rec_moves(), moves)
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(
            request.id
        ).write({'approved_recovery_exact': '1'}),
        'HISTORICAL_APPROVAL_PROTECTED',
    )
    logging.getLogger(__name__).info(
        'DEV16 commercial approval elapsed_seconds=%s',
        round(time.perf_counter() - started, 3),
    )


def test_rec16_partial_waiver_reconciliation(self):
    """GOLD-REC16-002. Approve the waiver before the recovery target."""
    validation = self._rec_validated(500)
    moves = self._rec_moves()
    self._rec_policy(levels=[
        _rec_level('waiver', 1),
        _rec_level('waiver', 2),
        _rec_level('recovery', 1),
        _rec_level('settlement', 1),
        _rec_level('handoff', 1),
    ])
    waiver = self._rec_submit_waiver(self._rec_waiver(validation, '5000'))
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.waiver'].browse(
            waiver.id
        ).action_approve('The requester cannot waive.'),
        'SELF_APPROVAL_PROHIBITED',
    )
    self._env(self.commercial, self.company_a)['cpla.recovery.waiver'].browse(waiver.id).action_approve(
        'First waiver level. The amount is not final.'
    )
    waiver = self.env['cpla.recovery.waiver'].browse(waiver.id)
    self.assertEqual(waiver.state, 'pending_approval')
    self._assert_amount(self._rec_position(validation)['waiver'], '0')
    self._fv_error(
        lambda: self._env(self.commercial, self.company_a)['cpla.recovery.waiver'].browse(
            waiver.id
        ).action_approve('The same user cannot complete both levels.'),
        'SELF_APPROVAL_PROHIBITED',
    )
    self._env(self.commercial_b, self.company_a)['cpla.recovery.waiver'].browse(waiver.id).action_approve(
        'Second waiver level authorizes five thousand.'
    )
    self._env(self.commercial_b, self.company_a)['cpla.recovery.waiver'].browse(waiver.id).action_approve(
        'Retry the finished waiver.'
    )
    waiver = self.env['cpla.recovery.waiver'].browse(waiver.id)
    self.assertEqual(waiver.state, 'approved')
    self._assert_amount(waiver.approved_amount_exact, '5000')
    self.assertTrue(waiver.approval_snapshot)
    self._assert_amount(self._rec_position(validation)['unallocated'], '20000')
    request = self._rec_submit(self._rec_request(validation, '20000'))
    request = self._rec_approve_request(request, self.commercial)
    self.assertEqual(request.state, 'approved')
    position = self._rec_position(validation)
    self._rec_equation(position)
    self._assert_amount(position['validated'], '25000')
    self._assert_amount(position['waiver'], '5000')
    self._assert_amount(position['recovery_target'], '20000')
    self._assert_amount(position['unallocated'], '0')
    self._assert_amount(request.billed_amount_exact, '0')
    self._assert_amount(request.collected_amount_exact, '0')
    self.assertFalse(validation.is_waiver)
    self._fv_error(
        lambda: self._rec_waiver(validation, '8000'),
        'ALLOCATION_EXCEEDS_VALIDATED',
    )
    self.assertEqual(self._rec_moves(), moves)


def test_rec16_undecided_and_unapproved_waiver(self):
    """GOLD-REC16-003 and GOLD-REC16-006. A draft waiver is not an approved waiver."""
    validation = self._rec_validated(500)
    self._rec_policy()
    self._rec_approve_waiver(self._rec_waiver(validation, '5000'))
    request = self._rec_submit(self._rec_request(validation, '12000'))
    request = self._rec_approve_request(request, self.commercial)
    position = self._rec_position(validation)
    self._rec_equation(position)
    self._assert_amount(position['validated'], '25000')
    self._assert_amount(position['waiver'], '5000')
    self._assert_amount(position['recovery_target'], '12000')
    self._assert_amount(position['unallocated'], '8000')
    draft = self._rec_waiver(validation, '1000')
    self.assertEqual(draft.state, 'draft')
    self._assert_amount(draft.approved_amount_exact, '0')
    position = self._rec_position(validation)
    self._assert_amount(position['waiver'], '5000')
    self._assert_amount(position['recovery_target'], '12000')
    self._assert_amount(position['unallocated'], '8000')
    self._fv_error(
        lambda: self._rec_request(validation, '8000', force_new=True),
        'ALLOCATION_EXCEEDS_VALIDATED',
    )
    self._assert_amount(request.current_recovery_exact, '12000')
    self._assert_amount(request.billed_amount_exact, '0')
    self._assert_amount(request.collected_amount_exact, '0')


def test_rec16_dispute_acknowledgement_silence(self):
    """GOLD-REC16-004, 014, and 015. Dispute and acknowledgement stay inside the target."""
    validation = self._rec_validated(500)
    self._rec_policy()
    original = self._rec_approve_waiver(self._rec_waiver(validation, '5000'))
    request = self._rec_submit(self._rec_request(validation, '20000'))
    request = self._rec_approve_request(request, self.commercial)
    moves = self._rec_moves()
    mails = self.env['mail.mail'].search_count([])
    self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(
        request.id
    ).action_mark_discussion()
    request = self.env['cpla.recovery.request'].browse(request.id)
    self.assertEqual(request.customer_state, 'discussion')
    position = self._rec_position(validation)
    self._assert_amount(position['acknowledged'], '0')
    self._assert_amount(position['disputed'], '0')
    self._assert_amount(position['unanswered'], '20000')
    self._assert_amount(position['recovery_target'], '20000')
    line = _rec_line(self, request)
    dispute_model = self._env(self.manager, self.company_a)['cpla.recovery.dispute']
    dispute_model.record_acknowledgement(
        line.id, '7000', 'Customer letter acknowledges seven thousand.', 'letter', self._today(),
    )
    dispute = dispute_model.open_dispute(
        line.id, '8000', 'price_not_accepted',
        'The customer does not accept eight thousand of the price.',
        'Email of 5 November objects to that portion.',
        'email', self._today(),
    )
    position = self._rec_position(validation)
    self._rec_equation(position)
    self._assert_amount(position['recovery_target'], '20000')
    self._assert_amount(position['acknowledged'], '7000')
    self._assert_amount(position['disputed'], '8000')
    self._assert_amount(position['unanswered'], '5000')
    self._assert_amount(position['waiver'], '5000')
    dispute_model.record_acknowledgement(
        line.id, '5000', 'A later letter acknowledges five thousand more.', 'letter', self._today(),
    )
    position = self._rec_position(validation)
    self._assert_amount(position['acknowledged'], '12000')
    self._assert_amount(position['disputed'], '8000')
    self._assert_amount(position['unanswered'], '0')
    self._assert_amount(position['recovery_target'], '20000')
    self._fv_error(
        lambda: dispute_model.open_dispute(
            line.id, '8000', 'duplicate_demand',
            'A second dispute of the same eight thousand.',
            'The second letter repeats the objection.',
            'email', self._today(),
        ),
        'DISPUTE_EXCEEDS_TARGET',
    )
    self._assert_amount(self._rec_position(validation)['disputed'], '8000')
    runs = self.env['cpla.invoice.audit.run'].search_count([
        ('company_id', '=', self.company_a.id),
    ])
    finding = self.env['cpla.leakage.finding'].browse(line.finding_id.id)
    self._env(self.manager, self.company_a)['cpla.recovery.dispute'].browse(
        dispute.id
    ).action_request_source_review(
        'Ask finance to review the customer evidence. Do not rerun the audit from here.'
    )
    dispute = self.env['cpla.recovery.dispute'].browse(dispute.id)
    self.assertTrue(dispute.reassessment_requested)
    self.assertEqual(dispute.state, 'escalated')
    self.assertTrue(finding.is_current)
    self.assertEqual(self.env['cpla.invoice.audit.run'].search_count([
        ('company_id', '=', self.company_a.id),
    ]), runs)
    self._env(self.manager, self.company_a)['cpla.recovery.dispute'].browse(
        dispute.id
    ).action_withdraw('The objection is withdrawn. The target stays.')
    dispute = self.env['cpla.recovery.dispute'].browse(dispute.id)
    self.assertEqual(dispute.state, 'withdrawn')
    self.assertFalse(dispute.counts_current)
    position = self._rec_position(validation)
    self._assert_amount(position['disputed'], '0')
    self._assert_amount(position['recovery_target'], '20000')
    self._assert_amount(position['waiver'], '5000')
    self.assertTrue(original.counts_current)
    request = self.env['cpla.recovery.request'].browse(request.id)
    self._assert_amount(request.billed_amount_exact, '0')
    self._assert_amount(request.collected_amount_exact, '0')
    self.assertEqual(self.env['mail.mail'].search_count([]), mails)
    self.assertEqual(self._rec_moves(), moves)


def test_rec16_settlement_counteroffer_and_extra_waiver(self):
    """GOLD-REC16-005, 013, 016, and 017. Internal approval is not acceptance or cash."""
    validation = self._rec_validated(500)
    self._rec_policy()
    original = self._rec_approve_waiver(self._rec_waiver(validation, '5000'))
    request = self._rec_submit(self._rec_request(validation, '20000'))
    request = self._rec_approve_request(request, self.commercial)
    moves = self._rec_moves()
    settlement_model = self._env(self.manager, self.company_a)['cpla.recovery.settlement']
    first = settlement_model.propose(
        request.id, '20000', '0',
        'Propose the full target. This is not customer acceptance.',
        'Opening proposal.',
    )
    self.assertEqual(first.internal_state, 'draft')
    self.assertEqual(first.customer_state, 'not_sent')
    self._assert_amount(self._rec_position(validation)['recovery_target'], '20000')
    self._env(self.manager, self.company_a)['cpla.recovery.settlement'].browse(
        first.id
    ).action_record_counteroffer(
        '15000', 'The customer offered fifteen thousand in the meeting notes.', 'meeting', self._today(),
    )
    first = self.env['cpla.recovery.settlement'].browse(first.id)
    self.assertEqual(first.customer_state, 'counteroffer')
    self.assertEqual(first.internal_state, 'draft')
    self._assert_amount(first.counteroffer_exact, '15000')
    request = self.env['cpla.recovery.request'].browse(request.id)
    self._assert_amount(request.current_recovery_exact, '20000')
    self._assert_amount(request.approved_recovery_exact, '20000')
    second = self._env(self.manager, self.company_a)['cpla.recovery.settlement'].propose(
        request.id, '17000', '3000',
        'Revised proposal with an additional three thousand concession.',
        'The concession still needs its own waiver approval.',
        supersedes_id=first.id,
    )
    self.assertFalse(self.env['cpla.recovery.settlement'].browse(first.id).counts_current)
    self.assertTrue(second.counts_current)
    env = self._env(self.manager, self.company_a)
    record = env['cpla.recovery.settlement'].browse(second.id)
    record.action_submit()
    record = env['cpla.recovery.settlement'].browse(second.id)
    record.action_request_approval()
    self._env(self.commercial, self.company_a)['cpla.recovery.settlement'].browse(
        second.id
    ).action_approve_internal('Internal approval only. The customer has not accepted.')
    second = self.env['cpla.recovery.settlement'].browse(second.id)
    self.assertEqual(second.internal_state, 'approved')
    self.assertEqual(second.customer_state, 'not_sent')
    position = self._rec_position(validation)
    self._assert_amount(position['waiver'], '5000')
    self._assert_amount(position['recovery_target'], '20000')
    self._env(self.manager, self.company_a)['cpla.recovery.settlement'].browse(
        second.id
    ).action_record_customer_acceptance(
        'Signed proposal accepts seventeen thousand.', 'signed_proposal', self._today(),
    )
    second = self.env['cpla.recovery.settlement'].browse(second.id)
    self.assertEqual(second.customer_state, 'accepted')
    self.assertEqual(second.execution_state, 'pending_conditions')
    self._assert_amount(self._rec_position(validation)['collected'], '0')
    line = _rec_line(self, request)
    extra = self._rec_approve_waiver(self._rec_waiver(
        validation, '3000', request_line=line, reduces=True, settlement=second,
    ))
    second = self.env['cpla.recovery.settlement'].browse(second.id)
    self.assertEqual(second.additional_waiver_id, extra)
    position = self._rec_position(validation)
    self._rec_equation(position)
    self._assert_amount(position['validated'], '25000')
    self._assert_amount(position['waiver'], '8000')
    self._assert_amount(position['recovery_target'], '17000')
    self._assert_amount(position['unallocated'], '0')
    self.assertTrue(original.counts_current)
    self._assert_amount(original.approved_amount_exact, '5000')
    request = self.env['cpla.recovery.request'].browse(request.id)
    self._assert_amount(request.approved_recovery_exact, '20000')
    self._assert_amount(request.current_recovery_exact, '17000')
    self._assert_amount(request.billed_amount_exact, '0')
    self._assert_amount(request.collected_amount_exact, '0')
    payload = self._env(self.commercial, self.company_a)['cpla.recovery.request'].browse(
        request.id
    ).action_authorize_handoff('The accepted settlement is ready for accounting to read.')
    self.assertEqual(payload['status'], 'READY_FOR_ACCOUNTING')
    self._assert_amount(payload['authorized_amount'], '17000')
    self._assert_amount(payload['billed_amount'], '0')
    self._assert_amount(payload['collected_amount'], '0')
    self.assertFalse(payload['creates_account_move'])
    second = self.env['cpla.recovery.settlement'].browse(second.id)
    self.assertEqual(second.execution_state, 'ready_for_dev17')
    self.assertEqual(self._rec_moves(), moves)


def test_rec16_excess_waiver_and_duplicate_and_partial_split(self):
    """GOLD-REC16-007 and GOLD-REC16-008. Five thousand free cannot accept an eight thousand waiver."""
    validation = self._rec_validated(200)
    self._rec_policy()
    self._fv_error(lambda: self._rec_waiver(validation, '0'), 'INVALID_RECOVERY_AMOUNT')
    self._fv_error(lambda: self._rec_waiver(validation, '-5'), 'INVALID_RECOVERY_AMOUNT')
    first = self._rec_request(validation)
    again = self._rec_request(validation)
    self.assertEqual(again, first)
    self._fv_error(
        lambda: self._rec_request(validation, force_new=True),
        'ALLOCATION_EXCEEDS_VALIDATED',
    )
    pending = self._rec_submit(first)
    self._env(self.commercial, self.company_a)['cpla.recovery.request'].browse(
        pending.id
    ).action_reject('This proposal is not authorized.')
    pending = self.env['cpla.recovery.request'].browse(pending.id)
    self.assertEqual(pending.state, 'rejected')
    self._assert_amount(self._rec_position(validation)['recovery_target'], '0')
    replacement = self._rec_submit(self._rec_request(validation))
    self.assertNotEqual(replacement, pending)
    replacement = self._rec_approve_request(replacement, self.commercial)
    self._assert_amount(replacement.current_recovery_exact, '10000')
    self._fv_error(
        lambda: self._rec_request(validation, force_new=True),
        'ALLOCATION_EXCEEDS_VALIDATED',
    )
    self._assert_amount(self._rec_position(validation)['recovery_target'], '10000')
    self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(
        replacement.id
    ).action_withdraw('Release the approved target. No accounting handoff exists.')
    self._assert_amount(self._rec_position(validation)['recovery_target'], '0')
    self._assert_amount(self._rec_position(validation)['unallocated'], '10000')
    self._rec_approve_waiver(self._rec_waiver(validation, '5000'))
    self._assert_amount(self._rec_position(validation)['unallocated'], '5000')
    self._fv_error(
        lambda: self._rec_waiver(validation, '8000'),
        'ALLOCATION_EXCEEDS_VALIDATED',
    )
    kept = self._rec_approve_request(
        self._rec_submit(self._rec_request(validation, '5000')),
        self.commercial,
    )
    position = self._rec_position(validation)
    self._rec_equation(position)
    self._assert_amount(position['validated'], '10000')
    self._assert_amount(position['waiver'], '5000')
    self._assert_amount(position['recovery_target'], '5000')
    self._assert_amount(position['unallocated'], '0')
    self._assert_amount(kept.billed_amount_exact, '0')
    self._assert_amount(replacement.collected_amount_exact, '0')


def test_rec16_nonoverlapping_partial_requests(self):
    """GOLD-REC16-009. Two requests may share one validation when the slices do not overlap."""
    shared = self._rec_validated(400)
    self._rec_policy()
    left = self._rec_submit(self._rec_request(shared, '12000'))
    right = self._rec_submit(self._rec_request(shared, '8000'))
    self.assertNotEqual(left, right)
    left = self._rec_approve_request(left, self.commercial)
    right = self._rec_approve_request(right, self.commercial)
    position = self._rec_position(shared)
    self._rec_equation(position)
    self._assert_amount(position['validated'], '20000')
    self._assert_amount(position['waiver'], '0')
    self._assert_amount(position['recovery_target'], '20000')
    self._assert_amount(position['unallocated'], '0')
    self._assert_amount(left.billed_amount_exact, '0')
    self._assert_amount(right.collected_amount_exact, '0')


def test_rec16_finance_rejection_not_waiver(self):
    """GOLD-REC16-010. A finance rejection is not a commercial waiver."""
    validation = self._rec_validated(500, partial=('18000', '7000', '0'))
    correction = self._fv_as(validation, self.reviewer).action_create_correction(
        'A later draft is not an approved finance decision.'
    )
    correction = self._fv_record(correction)
    self.assertEqual(correction.state, 'draft')
    validation = self._fv_record(validation)
    self.assertTrue(validation.is_current)
    self._fv_error(lambda: self._rec_request(correction), 'RECOVERY_SOURCE_NOT_READY')
    self.assertEqual(validation.state, 'partially_approved')
    self.assertFalse(validation.is_waiver)
    self._assert_amount(validation.validated_exact, '18000')
    self._assert_amount(validation.rejected_exact, '7000')
    self._rec_policy()
    self._fv_error(lambda: self._rec_request(validation, '18001'), 'ALLOCATION_EXCEEDS_VALIDATED')
    self._fv_error(lambda: self._rec_waiver(validation, '19000'), 'ALLOCATION_EXCEEDS_VALIDATED')
    request = self._rec_submit(self._rec_request(validation, '18000'))
    request = self._rec_approve_request(request, self.commercial)
    position = self._rec_position(validation)
    self._rec_equation(position)
    self._assert_amount(position['validated'], '18000')
    self._assert_amount(position['waiver'], '0')
    self._assert_amount(position['recovery_target'], '18000')
    self._assert_amount(position['unallocated'], '0')
    self.assertFalse(self.env['cpla.recovery.waiver'].search_count([
        ('validation_id', '=', validation.id),
        ('state', '=', 'approved'),
    ]))
    self._assert_amount(request.billed_amount_exact, '0')
    self._assert_amount(request.collected_amount_exact, '0')


def test_rec16_stale_blocks_new_approval(self):
    """GOLD-REC16-011. A changed finance source blocks a new commercial approval."""
    validation = self._rec_validated(500)
    self._rec_policy()
    request = self._rec_submit(self._rec_request(validation))
    request = self._rec_approve_request(request, self.commercial)
    moves = self._rec_moves()
    finding = request.line_ids.finding_id
    self.env['cpla.finance.validation']._flag_source_change(finding)
    request = self.env['cpla.recovery.request'].browse(request.id)
    validation = self._fv_record(validation)
    self.assertTrue(request.stale_source)
    self.assertEqual(request.state, 'approved')
    self._assert_amount(request.approved_recovery_exact, '25000')
    self.assertTrue(validation.stale_source)
    self.assertFalse(validation.is_current)
    self._assert_amount(
        self.env['cpla.finance.validation'].current_validated_amount(self.company_a),
        '0',
    )
    self.assertTrue(request.event_ids.filtered(lambda event: event.event_type == 'source_stale'))
    self._fv_error(lambda: self._rec_request(validation), 'STALE_FINANCIAL_EVIDENCE')
    stale_line = request.line_ids.validation_line_id
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.waiver'].prepare(
            stale_line.id, '1000', 'relationship_preservation',
            'A new waiver cannot use a stale finance source.',
        ),
        'STALE_FINANCIAL_EVIDENCE',
    )
    self._assert_amount(request.approved_recovery_exact, '25000')
    self._assert_amount(request.billed_amount_exact, '0')
    self.assertEqual(self._rec_moves(), moves)


def test_rec16_currency_ceiling(self):
    """A recorded rate is required, and the converted amount uses the fixture ceiling."""
    validation = self._rec_validated(500)
    other = self.env['res.currency'].with_context(active_test=False).search([
        ('id', '!=', self.company_a.currency_id.id),
    ], limit=1)
    self.assertTrue(other)
    self._rec_policy(ceiling='30000', currency=other)
    request = self._rec_request(validation)
    request = self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(request.id)
    request.action_submit()
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(
            request.id
        ).action_request_approval(),
        'CURRENCY_BASIS_REVIEW_REQUIRED',
    )
    self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(
        request.id
    ).action_set_review_rate('2', self._today(), 'Recorded test rate. Not a market lookup.')
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(
            request.id
        ).action_request_approval(),
        'APPROVAL_LIMIT_EXCEEDED',
    )
    request = self.env['cpla.recovery.request'].browse(request.id)
    self.assertEqual(request.state, 'submitted')
    self._assert_amount(request.current_recovery_exact, '0')
    self._assert_amount(request.fx_rate_exact, '2')
    self._rec_policy(ceiling='100000', currency=other)
    self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(
        request.id
    ).action_request_approval()
    request = self.env['cpla.recovery.request'].browse(request.id)
    self.assertEqual(request.state, 'pending_approval')
    self._assert_amount(request.current_recovery_exact, '0')
    self._assert_amount(request.billed_amount_exact, '0')
    self._assert_amount(request.collected_amount_exact, '0')


def test_rec16_wrong_company_and_security(self):
    """GOLD-REC16-012. Company B cannot read or allocate Company A."""
    validation = self._rec_validated(100)
    self._rec_policy()
    request = self._rec_request(validation)
    manager_b = new_test_user(
        self.env, login='cpla16_mgr_b', password='cpla-test',
        groups='base.group_user,%s.group_contract_manager' % MODULE,
        company_id=self.company_b.id, company_ids=[Command.set([self.company_b.id])],
    )
    self.assertFalse(self._env(manager_b, self.company_b)['cpla.recovery.request'].search([
        ('id', '=', request.id),
    ]))
    with self.assertRaises(AccessError):
        self._env(manager_b, self.company_b)['cpla.recovery.request'].browse(request.id).read(['reference'])
    with self.assertRaises(AccessError):
        self._env(manager_b, self.company_b)['cpla.recovery.request'].prepare_from_validation(
            validation.id
        )
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.request'].browse(
            request.id
        ).write({'requested_amount_exact': '1'}),
        'HISTORICAL_APPROVAL_PROTECTED',
    )
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.request.line'].browse(
            request.line_ids.id
        ).write({'proposed_recovery_exact': '1'}),
        'HISTORICAL_APPROVAL_PROTECTED',
    )
    operator = new_test_user(
        self.env, login='cpla16_operator_sec', password='cpla-test',
        groups='base.group_user,%s.group_recovery_operator' % MODULE,
        company_id=self.company_a.id, company_ids=[Command.set([self.company_a.id])],
    )
    with self.assertRaises(AccessError):
        self._env(operator, self.company_a)['cpla.recovery.request'].browse(request.id).write({
            'state': 'approved',
        })
    with self.assertRaises(AccessError):
        self._env(self.auditor, self.company_a)['cpla.recovery.request'].browse(request.id).write({
            'state': 'approved',
        })
    reference = self._env(self.auditor, self.company_a)['cpla.recovery.request'].browse(
        request.id
    ).read(['reference'])
    self.assertEqual(reference[0]['reference'], request.reference)
    self._fv_error(
        lambda: self._env(self.finance, self.company_a)['cpla.recovery.request'].browse(
            request.id
        ).export_data(['reference']),
        'COMPANY_ACCESS_DENIED',
    )
    self.auditor.write({
        'group_ids': [Command.link(self.env.ref('base.group_allow_export').id)],
    })
    exported = self._env(self.auditor, self.company_a)['cpla.recovery.request'].browse(
        request.id
    ).export_data(['reference'])
    self.assertTrue(exported)
    with self.assertRaises(UserError):
        self.env['ir.attachment'].create({
            'name': 'secret.pdf',
            'res_model': 'cpla.recovery.request',
            'res_id': request.id,
            'public': True,
            'datas': 'eA==',
        })
    attachment = self.env['ir.attachment'].create({
        'name': 'negotiation.pdf',
        'res_model': 'cpla.recovery.request',
        'res_id': request.id,
        'datas': 'eA==',
    })
    with self.assertRaises(AccessError):
        self._env(manager_b, self.company_b)['ir.attachment'].browse(attachment.id).read(['name'])
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.event'].create({
            'company_id': self.company_a.id,
            'request_id': request.id,
            'event_type': 'recovery_requested',
            'reason': 'A client cannot write the event log.',
        }),
        'HISTORICAL_APPROVAL_PROTECTED',
    )


def test_rec16_concurrent_waiver_allocation(self):
    """GOLD-REC16-018. Two workers cannot approve the same five thousand twice."""
    registry = self.env.registry
    pool = self.conc_pool
    company_id = pool['company_id']
    waiver_id = False
    cursor = registry.cursor()
    saved = {
        'env': self.env,
        'company_a': self.company_a,
        'owner': self.owner,
        'manager': self.manager,
        'finance': self.finance,
        'reviewer': self.reviewer,
        'salesman': self.salesman,
        'partner': self.partner,
        'policy_a': self.policy_a,
        'bearing': self.bearing,
    }
    try:
        try:
            cursor.execute("SET lock_timeout = '20s'")
            cursor.execute("SET statement_timeout = '180s'")
            side = api.Environment(cursor, api.SUPERUSER_ID, {
                'allowed_company_ids': [company_id],
            })
            self.env = side
            self.company_a = side['res.company'].browse(company_id)
            self.owner = side['res.users'].browse(pool['owner_id'])
            self.manager = side['res.users'].browse(pool['manager_id'])
            self.finance = side['res.users'].browse(pool['finance_id'])
            self.salesman = side['res.users'].browse(pool['salesman_id'])
            self.partner = side['res.partner'].browse(pool['partner_id'])
            self.policy_a = side['cpla.company.policy'].browse(pool['policy_id'])
            self.bearing = side['product.product'].browse(pool['product_id'])
            self.reviewer = side['res.users'].browse(pool['reviewer_id'])
            validation = self._rec_validated(100)
            self._rec_policy(levels=[_rec_level('waiver')])
            waiver = self._rec_waiver(validation, '5000')
            env = self._env(self.manager, self.company_a)
            record = env['cpla.recovery.waiver'].browse(waiver.id)
            record.action_submit()
            record = env['cpla.recovery.waiver'].browse(waiver.id)
            record.action_request_approval()
            self.assertEqual(record.state, 'pending_approval')
            waiver_id = record.id
            cursor.commit()
        finally:
            self.env = saved['env']
            self.company_a = saved['company_a']
            self.owner = saved['owner']
            self.manager = saved['manager']
            self.finance = saved['finance']
            self.reviewer = saved['reviewer']
            self.salesman = saved['salesman']
            self.partner = saved['partner']
            self.policy_a = saved['policy_a']
            self.bearing = saved['bearing']
            cursor.close()

        self.assertTrue(waiver_id)
        results = []
        barrier = threading.Barrier(2)

        def approve(user_id):
            try:
                with registry.cursor() as thread_cursor:
                    thread_cursor.execute("SET lock_timeout = '20s'")
                    thread_cursor.execute("SET statement_timeout = '60s'")
                    thread_env = api.Environment(thread_cursor, user_id, {
                        'allowed_company_ids': [company_id],
                    })
                    barrier.wait(timeout=30)
                    thread_env['cpla.recovery.waiver'].browse(waiver_id).action_approve(
                        'Approve this waiver from one worker.'
                    )
                    thread_cursor.commit()
                    results.append('ok')
            except Exception as error:
                results.append('%s: %s' % (type(error).__name__, error))

        threads = [
            threading.Thread(target=approve, args=(pool['commercial_id'],)),
            threading.Thread(target=approve, args=(pool['commercial_b_id'],)),
        ]
        held = Registry._lock
        Registry._lock = DummyRLock()
        try:
            for thread in threads:
                thread.daemon = True
                thread.start()
            for thread in threads:
                thread.join(90)
                if thread.is_alive():
                    frame = sys._current_frames().get(thread.ident)
                    stack = ''.join(traceback.format_stack(frame)) if frame else 'no stack'
                    self.fail('Worker still running:\n%s' % stack)
        finally:
            Registry._lock = held
        self.assertEqual(len(results), 2, results)
        self.assertEqual(sum(1 for item in results if item == 'ok'), 1, results)
        with registry.cursor() as check:
            check_env = api.Environment(check, api.SUPERUSER_ID, {
                'allowed_company_ids': [company_id],
            })
            waiver = check_env['cpla.recovery.waiver'].browse(waiver_id)
            self.assertEqual(waiver.state, 'approved', results)
            balance = waiver.balance_id
            self.assertEqual(_money(balance.waiver_exact), Decimal('5000'), results)
            self.assertEqual(_money(balance.recovery_exact), Decimal('0'), results)
            self.assertEqual(_money(balance.validated_exact), Decimal('5000'), results)
            self.assertEqual(check_env['cpla.recovery.waiver'].search_count([
                ('company_id', '=', company_id),
                ('state', '=', 'approved'),
                ('counts_current', '=', True),
            ]), 1, results)
    finally:
        if company_id:
            with registry.cursor() as cleanup:
                cleanup.execute("SET lock_timeout = '20s'")
                for statement in _POOL_CLEAR_SQL:
                    if statement.startswith('DELETE FROM cpla_company_policy'):
                        continue
                    cleanup.execute(statement, ([company_id],))
                cleanup.commit()


for _method in (
    _rec_env,
    _rec_moves,
    _rec_equation,
    _rec_policy,
    _rec_validated,
    _rec_request,
    _rec_submit,
    _rec_approve_request,
    _rec_waiver,
    _rec_submit_waiver,
    _rec_approve_waiver,
    _rec_position,
    test_rec16_views_and_no_accounting,
    test_rec16_full_recovery_and_partial_waiver,
    test_rec16_partial_waiver_reconciliation,
    test_rec16_undecided_and_unapproved_waiver,
    test_rec16_dispute_acknowledgement_silence,
    test_rec16_settlement_counteroffer_and_extra_waiver,
    test_rec16_excess_waiver_and_duplicate_and_partial_split,
    test_rec16_nonoverlapping_partial_requests,
    test_rec16_finance_rejection_not_waiver,
    test_rec16_stale_blocks_new_approval,
    test_rec16_currency_ceiling,
    test_rec16_wrong_company_and_security,
    test_rec16_concurrent_waiver_allocation,
):
    setattr(TestDev12InvoiceAudit, _method.__name__, _method)
