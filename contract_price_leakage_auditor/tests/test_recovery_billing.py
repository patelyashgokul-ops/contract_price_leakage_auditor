"""DEV-17 accounting recovery billing tests.

These methods are bound onto TestDev12InvoiceAudit so they share that
class chart, users, and concurrency pool. They are not a second chart load.

Supported credits reduce the receivable and are not cash. An unsupported
credit stays an exception. No exchange-rate fixture is created. A golden
foreign-exchange amount is NOT_EXECUTED.
"""
import sys
import threading
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


def _bill_env(self, user=None, company=None):
    company = company or self.company_a
    return self._env(user or self.finance, company)


def _bill_income(self, company):
    account = self.env['account.account'].with_company(company).search([
        ('account_type', '=', 'income'),
    ], limit=1)
    self.assertTrue(account, 'The company chart has no income account.')
    return account


def _bill_tax(self, amount=10):
    """A company-entered fixture rate. It is not a statutory tax."""
    return self.env['account.tax'].with_company(self.company_a).create({
        'name': 'CPLA fixture recovery tax %s' % amount,
        'amount_type': 'percent',
        'amount': amount,
        'type_tax_use': 'sale',
        'price_include_override': 'tax_excluded',
        'company_id': self.company_a.id,
    })


def _bill_policy(self, method='standalone_invoice', treatment='untaxed_explicit', taxes=None,
                 bank=True, four_eyes=True, dispute=True, company=None, approve=True):
    company = company or self.company_a
    env = _bill_env(self, self.finance, company)
    journal = self._journal(company, 'sale')
    income = _bill_income(self, company)
    self.assertTrue(journal, 'The company chart has no sales journal.')
    creating = method in ('standalone_invoice', 'debit_note')
    policy = env['cpla.recovery.billing.policy'].create({
        'company_id': company.id,
        'name': 'Recovery billing policy',
        'billing_method': method,
        'tax_treatment': treatment,
        'journal_id': journal.id if creating or method == 'existing_document' else False,
        'revenue_account_id': income.id if creating else False,
        'four_eyes_posting': four_eyes,
        'bank_verification_required': bank,
        'dispute_blocks_billing': dispute,
        'change_reason': 'Test billing policy. No journal, account, or tax rate is seeded.',
    })
    if taxes:
        policy.write({'tax_ids': [Command.set(taxes.ids)]})
    if approve:
        env['cpla.recovery.billing.policy'].browse(policy.id).action_approve_policy()
    self.env.invalidate_all()
    return self.env['cpla.recovery.billing.policy'].browse(policy.id)


def _bill_ready_request(self, quantity=500, amount=None, waiver=None):
    """Validate, optionally waive, approve, and authorize the accounting handoff."""
    validation = self._rec_validated(quantity)
    self._rec_policy()
    if waiver:
        self._rec_approve_waiver(self._rec_waiver(validation, waiver))
    request = self._rec_request(validation, amount)
    request = self._rec_submit(request)
    request = self._rec_approve_request(request, self.commercial)
    self._env(self.commercial, request.company_id)['cpla.recovery.request'].browse(
        request.id
    ).action_authorize_handoff(
        'Authorize accounting to bill this recovery. This is not an invoice.'
    )
    self.env.invalidate_all()
    request = self.env['cpla.recovery.request'].browse(request.id)
    payload = request.accounting_handoff_payload()
    self.assertEqual(payload['status'], 'READY_FOR_ACCOUNTING')
    self.assertFalse(payload['creates_account_move'])
    self.assertFalse(payload['proves_cash_collection'])
    self._assert_amount(payload['billed_amount'], '0')
    self._assert_amount(payload['collected_amount'], '0')
    self._assert_amount(request.billed_amount_exact, '0')
    self._assert_amount(request.collected_amount_exact, '0')
    return validation, request


def _bill_prepare(self, request, line_amounts=None, slice_key=None, existing_move_id=None):
    env = _bill_env(self, self.finance, request.company_id)
    billing = env['cpla.recovery.billing'].prepare_from_request(
        request.id, line_amounts, slice_key=slice_key, existing_move_id=existing_move_id,
    )
    self.env.invalidate_all()
    return self.env['cpla.recovery.billing'].browse(billing.id)


def _bill_as(self, billing, user=None):
    user = user or self.finance
    return self._env(user, billing.company_id)['cpla.recovery.billing'].browse(billing.id)


def _bill_position(self, request):
    self.env.invalidate_all()
    return self.env['cpla.recovery.request'].browse(request.id).accounting_position()


def _bill_line(self, request):
    line = request.line_ids[:1]
    self.assertTrue(line)
    return line


def _bill_payment(self, invoice, amount, payment_date=None):
    journal = self._journal(invoice.company_id, 'bank')
    self.assertTrue(journal, 'The company chart has no bank journal.')
    method = journal.inbound_payment_method_line_ids[:1]
    self.assertTrue(method, 'The bank journal has no inbound payment method.')
    if not method.payment_account_id:
        outstanding = self.env['account.chart.template'].with_company(invoice.company_id).ref(
            'account_journal_payment_debit_account_id', raise_if_not_found=False,
        )
        if outstanding:
            method.payment_account_id = outstanding.id
    values = {
        'amount': amount,
        'payment_method_line_id': method.id,
    }
    if payment_date:
        values['payment_date'] = payment_date
    if len(invoice) > 1:
        values['group_payment'] = True
    payment = self.env['account.payment.register'].with_company(invoice.company_id).with_context(
        active_model='account.move',
        active_ids=invoice.ids,
    ).create(values)._create_payments()
    self.assertEqual(len(payment), 1)
    payment.invalidate_recordset()
    return payment


def _bill_match_bank(self, payment, amount):
    """Reconcile a statement to the payment outstanding line. Do not touch the invoice twice."""
    payment.invalidate_recordset()
    if not payment.outstanding_account_id:
        return False
    statement = self.env['account.bank.statement.line'].with_company(payment.company_id).create({
        'payment_ref': payment.name,
        'journal_id': payment.journal_id.id,
        'partner_id': payment.partner_id.id,
        'amount': amount,
        'date': payment.date,
    })
    _liquidity, suspense, _rest = statement._seek_for_lines()
    liquidity, _counterpart, _writeoff = payment._seek_for_lines()
    self.assertTrue(suspense and liquidity, 'The statement or payment has no liquidity line to match.')
    suspense.account_id = liquidity.account_id
    (suspense + liquidity).reconcile()
    payment.invalidate_recordset()
    return bool(payment.reconciled_statement_line_ids)


def test_bill17_views_sequences_and_alerts(self):
    """Billing screens, sequences, and the separation alerts load. No cron is added."""
    manifest = Manifest.for_addon(MODULE)
    self.assertEqual(manifest['version'], '19.0.1.15.0')
    self.assertIn('views/billing_views.xml', manifest['data'])
    self.assertIn('security/billing_rules.xml', manifest['data'])
    self.assertIn('data/billing_sequence.xml', manifest['data'])
    self.assertNotIn('account', manifest['depends'])
    expected = {
        'seq_cpla_recovery_billing_policy': 'CPL-BPO/%(year)s/',
        'seq_cpla_recovery_billing': 'CPL-BIL/%(year)s/',
    }
    for xmlid, prefix in expected.items():
        sequence = self.env.ref('%s.%s' % (MODULE, xmlid))
        self.assertEqual(sequence.prefix, prefix)
        self.assertEqual(sequence.padding, 5)
        self.assertFalse(sequence.company_id)
    policy_form = self.env.ref(MODULE + '.view_cpla_recovery_billing_policy_form').arch
    self.assertIn('No journal, account, or tax is seeded', policy_form)
    self.assertIn('does not create an invoice', policy_form)
    billing_form = self.env.ref(MODULE + '.view_cpla_recovery_billing_form').arch
    self.assertIn('A draft accounting document is not posted recovery', billing_form)
    self.assertIn('A posted invoice is not collected cash', billing_form)
    self.assertIn('A credit note is not incoming cash', billing_form)
    self.assertIn('does not auto-post', billing_form)
    request_form = self.env.ref(MODULE + '.view_cpla_recovery_request_form').arch
    self.assertIn('does not create an invoice, a debit note, or a payment', request_form)
    self.assertIn('Prepare accounting billing', request_form)
    self.assertFalse(self.env['ir.model.data'].search([
        ('module', '=', MODULE),
        ('model', 'in', ('ir.cron', 'ir.actions.server', 'ir.actions.report')),
    ]))


def test_bill17_fx_difference_not_executed(self):
    """The classifier knows an exchange difference. No currency and no golden FX amount are created."""
    before = self.env['res.currency'].with_context(active_test=False).search_count([])
    kinds = dict(self.env['cpla.recovery.collection.evidence']._fields['classification'].selection)
    self.assertIn('fx_difference', kinds)
    self.assertIn('unknown_credit', kinds)
    categories = dict(self.env['cpla.recovery.collection.evidence']._fields['credit_category'].selection)
    for code in (
        'FULL_RECOVERY_BILL_REVERSAL',
        'PARTIAL_RECOVERY_BILL_REVERSAL',
        'SETTLEMENT_CREDIT',
        'TAX_ONLY_CREDIT',
        'DUPLICATE_BILLING_CORRECTION',
        'UNRELATED_CUSTOMER_CREDIT',
        'UNKNOWN_CREDIT_ALLOCATION',
    ):
        self.assertIn(code, categories)
    self.assertEqual(
        self.env['res.currency'].with_context(active_test=False).search_count([]),
        before,
    )
    self.assertNotIn('cpla.recovery', self.env.registry)
    self.assertIn('cpla.recovery.billing', self.env.registry)


def test_bill17_policy_blocks(self):
    """Unresolved tax, a foreign journal, and a missing sales journal block the policy."""
    env = _bill_env(self)
    unresolved = env['cpla.recovery.billing.policy'].create({
        'company_id': self.company_a.id,
        'name': 'Unresolved tax policy',
        'billing_method': 'manual_handoff',
        'tax_treatment': 'unresolved',
        'change_reason': 'Tax treatment is not chosen.',
    })
    self._fv_error(
        lambda: env['cpla.recovery.billing.policy'].browse(unresolved.id).action_approve_policy(),
        'TAX_TREATMENT_UNRESOLVED',
    )
    taxed = _bill_tax(self)
    self._fv_error(
        lambda: _bill_policy(self, taxes=taxed),
        'TAX_TREATMENT_UNRESOLVED',
    )
    incomplete = env['cpla.recovery.billing.policy'].create({
        'company_id': self.company_a.id,
        'name': 'Missing journal',
        'billing_method': 'standalone_invoice',
        'tax_treatment': 'untaxed_explicit',
        'change_reason': 'A sales journal was not selected.',
    })
    self._fv_error(
        lambda: env['cpla.recovery.billing.policy'].browse(incomplete.id).action_approve_policy(),
        'ACCOUNTING_CONFIGURATION_INCOMPLETE',
    )
    journal_b = self._journal(self.company_b, 'sale')
    income_a = _bill_income(self, self.company_a)
    with self.assertRaises(UserError):
        env['cpla.recovery.billing.policy'].create({
            'company_id': self.company_a.id,
            'name': 'Foreign journal',
            'billing_method': 'standalone_invoice',
            'tax_treatment': 'untaxed_explicit',
            'journal_id': journal_b.id,
            'revenue_account_id': income_a.id,
            'change_reason': 'Company A cannot use a Company B journal.',
        })


def test_bill17_debit_note_method(self):
    """Debit notes stay blocked while the community wizard is not installed."""
    if 'account.debit.note' not in self.env.registry:
        self._fv_error(
            lambda: _bill_policy(self, method='debit_note'),
            'ACCOUNTING_METHOD_UNAVAILABLE',
        )
        self.assertFalse(self.env['account.move'].search_count([
            ('company_id', '=', self.company_a.id),
            ('ref', 'ilike', 'CPL-BIL/'),
        ]))
        return
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self, method='debit_note')
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.move_id.state, 'draft')
    self.assertEqual(billing.move_id.debit_origin_id, billing.origin_move_id)
    self._assert_amount(billing.posted_principal_exact, '0')
    _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'posted')
    self._assert_amount(billing.posted_principal_exact, '5000')
    self._assert_amount(_bill_position(self, request)['verified_cash_principal'], '0')


def test_bill17_golden_posted_and_bank_cash(self):
    """25,000 validated, 5,000 waived, 20,000 posted, 12,000 bank-verified, 8,000 outstanding."""
    _validation, request = _bill_ready_request(self, 500, '20000', waiver='5000')
    _bill_policy(self)
    billing = _bill_prepare(self, request)
    self.assertEqual(billing.state, 'handoff_verified')
    self.assertFalse(billing.move_id)
    position = _bill_position(self, request)
    self._assert_amount(position['authorized_target'], '20000')
    self._assert_amount(position['posted_principal'], '0')
    self._assert_amount(position['draft_reserved_principal'], '20000')
    self._assert_amount(position['unbilled_target'], '20000')
    self._assert_amount(position['dev16_billed'], '0')
    self._assert_amount(position['dev16_collected'], '0')
    self.assertFalse(position['draft_is_posted'])
    self.assertFalse(position['document_is_cash'])
    _bill_as(self, billing).action_create_draft()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'draft_document_created')
    self.assertEqual(billing.move_id.state, 'draft')
    self.assertEqual(billing.link_source, 'created_by_app')
    self._assert_amount(billing.posted_principal_exact, '0')
    self._assert_amount(billing.move_id.amount_untaxed, '20000')
    self._assert_amount(billing.move_id.amount_tax, '0')
    same = _bill_prepare(self, request)
    self.assertEqual(same, billing)
    moves = self.env['account.move'].search_count([('company_id', '=', self.company_a.id)])
    _bill_as(self, billing).action_create_draft()
    self.assertEqual(
        self.env['account.move'].search_count([('company_id', '=', self.company_a.id)]),
        moves,
    )
    billing.move_id.write({
        'invoice_payment_term_id': False,
        'invoice_date_due': self._on(-1),
    })
    _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'posted')
    self.assertEqual(billing.move_id.state, 'posted')
    self._assert_amount(billing.posted_principal_exact, '20000')
    self._assert_amount(billing.tax_exact, '0')
    self._assert_amount(billing.gross_exact, '20000')
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '20000')
    self._assert_amount(position['unbilled_target'], '0')
    self._assert_amount(position['verified_cash_principal'], '0')
    self._assert_amount(position['outstanding_principal'], '20000')
    self._assert_amount(position['dev16_billed'], '0')
    self.assertEqual(billing.due_date, self._on(-1))
    self.assertTrue(position['overdue'])
    posted_moves = self.env['account.move'].search_count([('company_id', '=', self.company_a.id)])
    _bill_as(self, billing).action_post()
    self.assertEqual(
        self.env['account.move'].search_count([('company_id', '=', self.company_a.id)]),
        posted_moves,
    )
    payment = _bill_payment(self, billing.move_id, 12000)
    _bill_as(self, billing).action_refresh_collections()
    position = _bill_position(self, request)
    self._assert_amount(billing.move_id.amount_residual, '8000')
    self._assert_amount(position['verified_cash_principal'], '0')
    self._assert_amount(position['unconfirmed_principal'], '12000')
    self._assert_amount(position['outstanding_principal'], '20000')
    self.assertNotEqual(position['verified_cash_principal'], position['unconfirmed_principal'])
    matched = _bill_match_bank(self, payment, 12000)
    self.assertTrue(
        matched,
        'Bank evidence did not link. Outstanding account: %s.' % payment.outstanding_account_id.id,
    )
    _bill_as(self, billing).action_refresh_collections()
    position = _bill_position(self, request)
    self._assert_amount(position['verified_cash_principal'], '12000')
    self._assert_amount(position['unconfirmed_principal'], '0')
    self._assert_amount(position['outstanding_principal'], '8000')
    self._assert_amount(position['credit_note_principal'], '0')
    self._assert_amount(position['fx_company_amount'], '0')
    self._assert_amount(position['posted_principal'], '20000')
    self._assert_amount(position['accounting_residual'], '8000')
    self.assertFalse(position['document_is_cash'])
    commercial = self._rec_position(request.validation_id)
    self._rec_equation(commercial)
    self._assert_amount(commercial['validated'], '25000')
    self._assert_amount(commercial['waiver'], '5000')
    self._assert_amount(commercial['recovery_target'], '20000')
    payload = self.env['cpla.recovery.request'].browse(request.id).accounting_handoff_payload()
    self.assertFalse(payload['creates_account_move'])
    self._assert_amount(payload['billed_amount'], '0')
    self._assert_amount(payload['collected_amount'], '0')
    self.assertNotIn('RECEIVABLE_RESIDUAL_MISMATCH', position['exception_codes'])
    report = _bill_env(self)['cpla.recovery.billing'].reconciliation_report(self.company_a.id)
    self.assertFalse(report['totals'])
    self.assertFalse(report['mixed_currency'])
    row = next(item for item in report['rows'] if item['request_id'] == request.id)
    self._assert_amount(row['finance_validated'], '25000')
    self._assert_amount(row['approved_waiver'], '5000')
    self._assert_amount(row['approved_target'], '20000')
    self._assert_amount(row['posted_principal'], '20000')
    self._assert_amount(row['verified_cash_principal'], '12000')
    self._assert_amount(row['unbilled_principal'], '0')
    self._assert_amount(row['receivable_outstanding'], '8000')
    self.assertNotEqual(_money(row['finance_validated']), _money(row['verified_cash_principal']))


def test_bill17_partial_slices(self):
    """12,000 posted and 8,000 still draft leaves 8,000 of the target unbilled."""
    _validation, request = _bill_ready_request(self, 400, '20000')
    _bill_policy(self)
    line = _bill_line(self, request)
    first = _bill_prepare(self, request, {line.id: '12000'}, slice_key='slice-12000')
    _bill_as(self, first).action_create_draft()
    _bill_as(self, first).action_post()
    second = _bill_prepare(self, request, {line.id: '8000'}, slice_key='slice-8000')
    self.assertEqual(second.state, 'handoff_verified')
    self.assertFalse(second.move_id)
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '12000')
    self._assert_amount(position['draft_reserved_principal'], '8000')
    self._assert_amount(position['unbilled_target'], '8000')
    self._fv_error(
        lambda: _bill_prepare(self, request, {line.id: '8000'}, slice_key='slice-overlap'),
        'BILLING_EXCEEDS_AUTHORIZED',
    )
    _bill_as(self, second).action_create_draft()
    _bill_as(self, second).action_post()
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '20000')
    self._assert_amount(position['unbilled_target'], '0')
    self._assert_amount(position['verified_cash_principal'], '0')
    self.assertEqual(
        self.env['cpla.recovery.billing'].search_count([
            ('request_id', '=', request.id),
            ('state', '=', 'posted'),
        ]),
        2,
    )


def test_bill17_waiver_is_not_billed(self):
    """A reducing waiver that clears the target cannot be billed."""
    validation, request = _bill_ready_request(self, 500, '25000')
    _bill_policy(self)
    line = _bill_line(self, request)
    self._rec_approve_waiver(self._rec_waiver(
        validation, '25000', request_line=line, reduces=True,
    ))
    request = self.env['cpla.recovery.request'].browse(request.id)
    self._assert_amount(request.current_recovery_exact, '0')
    self._assert_amount(request.billed_amount_exact, '0')
    position = self._rec_position(validation)
    self._assert_amount(position['waiver'], '25000')
    self._assert_amount(position['recovery_target'], '0')
    self._assert_amount(position['billed'], '0')
    self._fv_error(lambda: _bill_prepare(self, request), 'BILLING_EXCEEDS_AUTHORIZED')
    self.assertFalse(self.env['cpla.recovery.billing'].search_count([
        ('request_id', '=', request.id),
    ]))


def test_bill17_existing_document_link(self):
    """Link one posted document of the exact slice. The source invoice is not that document."""
    validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self, method='existing_document')
    origin = _bill_line(self, request).validation_line_id.move_line_id.move_id
    origin_price = origin.invoice_line_ids[:1].price_unit
    self._fv_error(
        lambda: _bill_prepare(self, request),
        'BILLING_DOCUMENT_MISMATCH',
    )
    self._fv_error(
        lambda: _bill_prepare(self, request, existing_move_id=origin.id),
        'BILLING_DOCUMENT_MISMATCH',
    )
    draft = self._manual(price=5000, quantity=1, post=False)
    self._fv_error(
        lambda: _bill_prepare(self, request, existing_move_id=draft.id),
        'BILLING_DOCUMENT_MISMATCH',
    )
    wrong = self._manual(price=6000, quantity=1, post=True)
    self._fv_error(
        lambda: _bill_prepare(self, request, existing_move_id=wrong.id),
        'BILLING_DOCUMENT_MISMATCH',
    )
    other_customer = self.env['res.partner'].with_company(self.company_a).create({
        'name': 'Other recovery customer',
        'company_id': self.company_a.id,
    })
    wrong_customer = self._manual(price=5000, quantity=1, post=True, partner=other_customer)
    self._fv_error(
        lambda: _bill_prepare(self, request, existing_move_id=wrong_customer.id),
        'BILLING_DOCUMENT_MISMATCH',
    )
    exact = self._manual(price=5000, quantity=1, post=True)
    billing = _bill_prepare(self, request, existing_move_id=exact.id)
    self.assertEqual(billing.state, 'posted')
    self.assertEqual(billing.link_source, 'existing_verified')
    self.assertEqual(billing.move_id, exact)
    self.assertNotEqual(billing.link_source, 'created_by_app')
    self._assert_amount(billing.posted_principal_exact, '5000')
    self._assert_amount(_bill_position(self, request)['verified_cash_principal'], '0')
    self.assertEqual(origin.state, 'posted')
    self.assertEqual(origin.invoice_line_ids[:1].price_unit, origin_price)
    again = _bill_prepare(self, request, existing_move_id=exact.id)
    self.assertEqual(again, billing)
    self.assertEqual(self.env['cpla.recovery.accounting.link'].search_count([
        ('move_id', '=', exact.id),
        ('counts_current', '=', True),
    ]), 1)
    self.assertEqual(validation.company_id, billing.company_id)


def test_bill17_manual_handoff_and_cancel(self):
    """A manual package creates no move. Cancelling it releases the slice."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self, method='manual_handoff')
    moves = self.env['account.move'].search_count([('company_id', '=', self.company_a.id)])
    payments = self.env['account.payment'].search_count([('company_id', '=', self.company_a.id)])
    billing = _bill_prepare(self, request)
    self.assertEqual(billing.state, 'document_prepared')
    self.assertFalse(billing.move_id)
    self.assertEqual(
        self.env['account.move'].search_count([('company_id', '=', self.company_a.id)]),
        moves,
    )
    self.assertEqual(
        self.env['account.payment'].search_count([('company_id', '=', self.company_a.id)]),
        payments,
    )
    package = _bill_as(self, billing).handoff_package()
    self.assertEqual(package['status'], 'MANUAL_ACCOUNTING_HANDOFF')
    self.assertFalse(package['creates_account_move'])
    self.assertFalse(package['posts_account_move'])
    self.assertFalse(package['proves_cash_collection'])
    self._fv_error(lambda: _bill_as(self, billing).action_post(), 'ACCOUNTING_METHOD_UNAVAILABLE')
    _bill_as(self, billing).action_cancel('The accountant has not created a document.')
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'cancelled')
    self.assertFalse(billing.line_ids.filtered('counts_current'))
    again = _bill_prepare(self, request)
    self.assertNotEqual(again, billing)
    self.assertEqual(again.state, 'document_prepared')
    self.assertFalse(again.move_id)


def test_bill17_stale_blocks_post(self):
    """A changed finance source blocks posting and leaves the draft unposted."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    finding = _bill_line(self, request).finding_id
    self.env['cpla.finance.validation']._flag_source_change(finding)
    self._fv_error(lambda: _bill_as(self, billing).action_post(), 'STALE_FINANCIAL_EVIDENCE')
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'draft_document_created')
    self.assertEqual(billing.move_id.state, 'draft')
    self._assert_amount(billing.posted_principal_exact, '0')
    self._assert_amount(_bill_position(self, request)['posted_principal'], '0')


def test_bill17_security_company_and_four_eyes(self):
    """A reviewer, the requester, and Company B cannot post. The poster is a different finance user."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    self._fv_error(
        lambda: self._env(self.reviewer, self.company_a)['cpla.recovery.billing'].prepare_from_request(request.id),
        'POSTING_AUTHORITY_DENIED',
    )
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.billing'].prepare_from_request(request.id),
        'POSTING_AUTHORITY_DENIED',
    )
    finance_b = new_test_user(
        self.env, login='cpla17_fin_b', password='cpla-test',
        groups='base.group_user,account.group_account_invoice,%s.group_finance_manager' % MODULE,
        company_id=self.company_b.id, company_ids=[Command.set([self.company_b.id])],
    )
    with self.assertRaises(AccessError):
        self._env(finance_b, self.company_b)['cpla.recovery.billing'].prepare_from_request(request.id)
    self._fv_error(
        lambda: _bill_env(self)['cpla.recovery.billing'].create({
            'company_id': self.company_a.id,
            'partner_id': self.partner.id,
        }),
        'RECOVERY_SOURCE_NOT_READY',
    )
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    self._fv_error(
        lambda: self._env(self.manager, self.company_a)['cpla.recovery.billing'].browse(
            billing.id
        ).export_data(['reference']),
        'COMPANY_ACCESS_DENIED',
    )
    self.manager.write({'group_ids': [
        Command.link(self.env.ref('account.group_account_invoice').id),
        Command.link(self.env.ref(MODULE + '.group_finance_manager').id),
    ]})
    self.env.invalidate_all()
    self._fv_error(
        lambda: _bill_as(self, billing, self.manager).action_post(),
        'POSTING_AUTHORITY_DENIED',
    )
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.move_id.state, 'draft')
    _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'posted')
    self.assertNotEqual(billing.posted_by_id, request.requested_by_id)
    self.assertFalse(self._env(finance_b, self.company_b)['cpla.recovery.billing'].search([
        ('id', '=', billing.id),
    ]))
    self.auditor.write({
        'group_ids': [Command.link(self.env.ref('base.group_allow_export').id)],
    })
    exported = self._env(self.auditor, self.company_a)['cpla.recovery.billing'].browse(
        billing.id
    ).export_data(['reference'])
    self.assertTrue(exported)
    self._fv_error(
        lambda: _bill_as(self, billing).write({'posted_principal_exact': '1'}),
        'HISTORICAL_APPROVAL_PROTECTED',
    )


def test_bill17_credit_is_not_cash(self):
    """A 5,000 credit reduces the receivable. It is not cash. A full credit releases the slice."""
    _validation, request = _bill_ready_request(self, 400, '20000')
    _bill_policy(self)
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    _bill_as(self, billing).action_post()
    moves = self.env['account.move'].search_count([('company_id', '=', self.company_a.id)])
    adjustment = _bill_as(self, billing).action_prepare_credit(
        '5000', 'Commercial credit. This is not incoming cash.',
    )
    self.assertEqual(adjustment.state, 'draft')
    self.assertFalse(adjustment.is_cash)
    self.assertEqual(adjustment.move_id.state, 'draft')
    self.assertEqual(adjustment.move_id.move_type, 'out_refund')
    _bill_as(self, billing).action_post_credit()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'partially_reversed')
    self.assertTrue(billing.line_ids.filtered('counts_current'))
    partial_credit = billing.evidence_ids.filtered(
        lambda item: item.counts_current and item.classification == 'credit_note'
    )
    self.assertEqual(partial_credit.credit_category, 'PARTIAL_RECOVERY_BILL_REVERSAL')
    self.assertEqual(partial_credit.verification_state, 'CREDIT_NOTE_SETTLEMENT')
    self.assertFalse(partial_credit.is_verified_cash)
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '20000')
    self._assert_amount(position['credit_note_principal'], '5000')
    self._assert_amount(position['verified_cash_principal'], '0')
    self._assert_amount(position['outstanding_principal'], '15000')
    self._assert_amount(position['unbilled_target'], '0')
    self.assertFalse(adjustment.is_cash)
    self.assertGreater(
        self.env['account.move'].search_count([('company_id', '=', self.company_a.id)]),
        moves,
    )
    _bill_as(self, billing).action_prepare_credit(
        '15000', 'Reverse the remaining recovery principal. This is not cash.',
    )
    _bill_as(self, billing).action_post_credit()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'fully_reversed')
    self.assertFalse(billing.line_ids.filtered('counts_current'))
    self.assertEqual(
        set(billing.evidence_ids.filtered(lambda item: item.classification == 'credit_note').mapped('credit_category')),
        {'FULL_RECOVERY_BILL_REVERSAL'},
    )
    self._assert_amount(billing.posted_principal_exact, '20000')
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '0')
    self._assert_amount(position['historical_posted_principal'], '20000')
    self._assert_amount(position['credit_note_principal'], '0')
    self._assert_amount(position['unbilled_target'], '20000')
    self._assert_amount(position['verified_cash_principal'], '0')
    replacement = _bill_prepare(self, request)
    self.assertNotEqual(replacement, billing)
    _bill_as(self, replacement).action_create_draft()
    _bill_as(self, replacement).action_post()
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '20000')
    self._assert_amount(position['historical_posted_principal'], '40000')
    self._assert_amount(position['verified_cash_principal'], '0')


def test_bill17_tax_is_not_principal(self):
    """An 18 percent fixture tax stays beside principal. Half the gross is not half as cash principal until allocated."""
    _validation, request = _bill_ready_request(self, 400, '20000')
    tax = _bill_tax(self, 18)
    _bill_policy(self, treatment='taxes_on_policy', taxes=tax)
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self._assert_amount(billing.posted_principal_exact, '20000')
    self._assert_amount(billing.tax_exact, '3600')
    self._assert_amount(billing.gross_exact, '23600')
    payment = _bill_payment(self, billing.move_id, 11800)
    _bill_as(self, billing).action_refresh_collections()
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '20000')
    self._assert_amount(position['tax_billed'], '3600')
    self._assert_amount(position['gross_receivable'], '23600')
    self._assert_amount(position['verified_cash_principal'], '0')
    self._assert_amount(position['unconfirmed_principal'], '10000')
    self._assert_amount(position['outstanding_principal'], '20000')
    self.assertNotEqual(_money(position['unconfirmed_principal']), Decimal('11800'))
    matched = _bill_match_bank(self, payment, 11800)
    self.assertTrue(matched, 'Bank evidence did not link for the taxed payment.')
    _bill_as(self, billing).action_refresh_collections()
    position = _bill_position(self, request)
    self._assert_amount(position['verified_cash_principal'], '10000')
    self._assert_amount(position['outstanding_principal'], '10000')
    self.assertNotEqual(_money(position['verified_cash_principal']), Decimal('11800'))


def test_bill17_multi_invoice_payment_uses_this_receivable(self):
    """A payment that also covers another invoice is not allocated entirely to this recovery."""
    _validation, request = _bill_ready_request(self, 400, '20000')
    _bill_policy(self)
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    other = self._manual(price=5000, quantity=1, post=True)
    payment = _bill_payment(self, billing.move_id | other, 25000)
    self.assertEqual(_money(payment.amount), Decimal('25000'))
    _bill_as(self, billing).action_refresh_collections()
    position = _bill_position(self, request)
    self._assert_amount(position['unconfirmed_principal'], '20000')
    self._assert_amount(position['verified_cash_principal'], '0')
    self.assertNotEqual(_money(position['unconfirmed_principal']), _money(payment.amount))
    evidence = billing.evidence_ids.filtered('counts_current')
    self.assertTrue(evidence)
    self.assertTrue(all(_money(row.principal_exact) <= Decimal('20000') for row in evidence))


def test_bill17_lock_date_blocks_post(self):
    """A lock date is left to the accounting engine. The draft stays unposted."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    self.company_a.write({
        'fiscalyear_lock_date': self._today(),
        'sale_lock_date': self._today(),
    })
    with self.assertRaises(UserError):
        _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.state, 'draft_document_created')
    self.assertEqual(billing.move_id.state, 'draft')
    self._assert_amount(billing.posted_principal_exact, '0')


def test_bill17_dispute_blocks_billing(self):
    """An open dispute blocks a new billing slice under the approved policy."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    line = _bill_line(self, request)
    self._env(self.manager, self.company_a)['cpla.recovery.dispute'].open_dispute(
        line.id, '1000', 'price_not_accepted',
        'The customer disputes this price.',
        'Email from the customer on this date.',
        'email', self._today(),
    )
    self._fv_error(lambda: _bill_prepare(self, request), 'RECOVERY_SOURCE_NOT_READY')
    self.assertFalse(self.env['cpla.recovery.billing'].search_count([
        ('request_id', '=', request.id),
    ]))


def test_bill17_settlement_blocks_billing(self):
    """A settlement without customer acceptance blocks billing."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    self._env(self.manager, self.company_a)['cpla.recovery.settlement'].propose(
        request.id, '5000', '0',
        'Internal settlement proposal.',
        'The customer has not accepted this proposal.',
    )
    self._fv_error(lambda: _bill_prepare(self, request), 'RECOVERY_SOURCE_NOT_READY')
    self.assertFalse(self.env['account.payment'].search_count([
        ('company_id', '=', self.company_a.id),
        ('partner_id', '=', request.partner_id.id),
        ('amount', '=', 5000),
    ]))


def test_bill17_advance_is_not_new_cash(self):
    """A payment dated before the billing date is an advance, not verified cash."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    _bill_payment(self, billing.move_id, 3000, payment_date=self._on(-1))
    _bill_as(self, billing).action_refresh_collections()
    position = _bill_position(self, request)
    self._assert_amount(position['advance_principal'], '3000')
    self._assert_amount(position['verified_cash_principal'], '0')
    self._assert_amount(position['unconfirmed_principal'], '0')
    self._assert_amount(position['outstanding_principal'], '2000')


def test_bill17_writeoff_is_classified_not_created(self):
    """A write-off label does not post a new entry and is not cash."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    receivable = billing.move_id.line_ids.filtered(
        lambda line: line.account_type == 'asset_receivable'
    )[:1]
    entry = self.env['account.move'].with_company(self.company_a).create({
        'move_type': 'entry',
        'journal_id': self._journal(self.company_a, 'general').id,
        'date': self._today(),
        'ref': 'Netting fixture. Not an automatic write-off.',
        'line_ids': [
            Command.create({
                'name': 'Netting fixture',
                'account_id': receivable.account_id.id,
                'partner_id': billing.partner_id.id,
                'credit': 1000.0,
                'debit': 0.0,
            }),
            Command.create({
                'name': 'Netting fixture',
                'account_id': billing.revenue_account_id.id,
                'debit': 1000.0,
                'credit': 0.0,
            }),
        ],
    })
    entry.action_post()
    credit_line = entry.line_ids.filtered(lambda line: line.account_id == receivable.account_id)
    (receivable + credit_line).reconcile()
    moves = self.env['account.move'].search_count([('company_id', '=', self.company_a.id)])
    _bill_as(self, billing).action_refresh_collections()
    evidence = billing.evidence_ids.filtered('counts_current')[:1]
    self.assertEqual(evidence.classification, 'other_settlement')
    self.assertFalse(evidence.is_verified_cash)
    _bill_as(self, billing).action_classify_settlement(
        evidence.partial_reconcile_key, 'write_off',
        'Label the existing netting. Do not post another entry.',
    )
    self.assertEqual(
        self.env['account.move'].search_count([('company_id', '=', self.company_a.id)]),
        moves,
    )
    position = _bill_position(self, request)
    self._assert_amount(position['write_off_principal'], '1000')
    self._assert_amount(position['verified_cash_principal'], '0')
    self._assert_amount(position['outstanding_principal'], '4000')


def test_bill17_concurrent_prepare(self):
    """Two workers cannot reserve the same slice twice."""
    registry = self.env.registry
    pool = self.conc_pool
    company_id = pool['company_id']
    request_id = False
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
        'commercial': self.commercial,
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
            self.commercial = side['res.users'].browse(pool['commercial_id'])
            _validation, request = _bill_ready_request(self, 100, '5000')
            _bill_policy(self)
            request_id = request.id
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
            self.commercial = saved['commercial']
            cursor.close()

        self.assertTrue(request_id)
        results = []
        barrier = threading.Barrier(2)

        def prepare(user_id):
            try:
                with registry.cursor() as thread_cursor:
                    thread_cursor.execute("SET lock_timeout = '20s'")
                    thread_cursor.execute("SET statement_timeout = '60s'")
                    thread_env = api.Environment(thread_cursor, user_id, {
                        'allowed_company_ids': [company_id],
                    })
                    barrier.wait(timeout=30)
                    billing = thread_env['cpla.recovery.billing'].prepare_from_request(request_id)
                    thread_cursor.commit()
                    results.append('ok:%s' % billing.id)
            except Exception as error:
                results.append('%s: %s' % (type(error).__name__, error))

        threads = [
            threading.Thread(target=prepare, args=(pool['finance_id'],)),
            threading.Thread(target=prepare, args=(pool['finance_id'],)),
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
        self.assertGreaterEqual(sum(1 for item in results if item.startswith('ok:')), 1, results)
        with registry.cursor() as check:
            check_env = api.Environment(check, api.SUPERUSER_ID, {
                'allowed_company_ids': [company_id],
            })
            billings = check_env['cpla.recovery.billing'].search([
                ('request_id', '=', request_id),
                ('state', 'not in', ('cancelled', 'superseded', 'fully_reversed')),
            ])
            self.assertEqual(len(billings), 1, results)
            self.assertEqual(_money(billings.requested_principal_exact), Decimal('5000'), results)
            self.assertEqual(
                sum(_money(line.principal_exact) for line in billings.line_ids if line.counts_current),
                Decimal('5000'),
                results,
            )
    finally:
        if company_id:
            with registry.cursor() as cleanup:
                cleanup.execute("SET lock_timeout = '20s'")
                for statement in _POOL_CLEAR_SQL:
                    if statement.startswith('DELETE FROM cpla_company_policy'):
                        continue
                    cleanup.execute(statement, ([company_id],))
                cleanup.commit()


def _bill_post(self, request):
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    _bill_as(self, billing).action_post()
    self.env.invalidate_all()
    return self.env['cpla.recovery.billing'].browse(billing.id)


def test_bill17_three_bank_payments(self):
    """Three verified payments add once each. Two of them do not close the receivable."""
    _validation, request = _bill_ready_request(self, 400, '20000')
    _bill_policy(self)
    billing = _bill_post(self, request)
    for amount, cash, outstanding in (('5000', '5000', '15000'), ('7000', '12000', '8000'), ('8000', '20000', '0')):
        payment = _bill_payment(self, billing.move_id, int(amount))
        self.assertTrue(_bill_match_bank(self, payment, int(amount)))
        _bill_as(self, billing).action_refresh_collections()
        position = _bill_position(self, request)
        self._assert_amount(position['verified_cash_principal'], cash)
        self._assert_amount(position['outstanding_principal'], outstanding)
    evidence = billing.evidence_ids.filtered('counts_current')
    self.assertEqual(len(evidence), 3)
    self.assertEqual(len(set(evidence.mapped('partial_reconcile_key'))), 3)
    self.assertEqual(sum(_money(row.principal_exact) for row in evidence), Decimal('20000'))
    self.assertTrue(all(row.verification_state == 'BANK_VERIFIED_CASH' for row in evidence))


def test_bill17_credit_plus_cash(self):
    """Cash and a supported credit stay separate. Their sum is not cash."""
    _validation, request = _bill_ready_request(self, 400, '20000')
    _bill_policy(self)
    billing = _bill_post(self, request)
    _bill_as(self, billing).action_prepare_credit('5000', 'Supported credit. Not incoming cash.')
    _bill_as(self, billing).action_post_credit()
    payment = _bill_payment(self, billing.move_id, 10000)
    self.assertTrue(_bill_match_bank(self, payment, 10000))
    _bill_as(self, billing).action_refresh_collections()
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '20000')
    self._assert_amount(position['verified_cash_principal'], '10000')
    self._assert_amount(position['credit_note_principal'], '5000')
    self._assert_amount(position['outstanding_principal'], '5000')
    self._assert_amount(position['unbilled_target'], '0')
    self.assertNotEqual(_money(position['verified_cash_principal']), Decimal('15000'))
    self.assertIn('BANK_VERIFIED_CASH', position['verification_state'])
    self.assertIn('CREDIT_NOTE_SETTLEMENT', position['verification_state'])


def test_bill17_unrelated_credit_needs_review(self):
    """A customer credit that does not reverse this billing does not reduce principal."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_post(self, request)
    credit = self._manual(move_type='out_refund', price=1000, quantity=1, post=True)
    self.assertFalse(credit.reversed_entry_id)
    invoice_line = billing.move_id.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')[:1]
    credit_line = credit.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')[:1]
    (invoice_line + credit_line).reconcile()
    _bill_as(self, billing).action_refresh_collections()
    evidence = billing.evidence_ids.filtered('counts_current')[:1]
    self.assertEqual(evidence.classification, 'unknown_credit')
    self.assertEqual(evidence.credit_category, 'UNKNOWN_CREDIT_ALLOCATION')
    self.assertEqual(evidence.verification_state, 'UNVERIFIED_SETTLEMENT')
    position = _bill_position(self, request)
    self._assert_amount(position['credit_note_principal'], '0')
    self._assert_amount(position['outstanding_principal'], '5000')
    self._assert_amount(position['verified_cash_principal'], '0')
    self.assertIn('CREDIT_ALLOCATION_AMBIGUOUS', position['exception_codes'])
    self.assertNotEqual(_money(position['accounting_residual']), _money(position['outstanding_principal']))


def test_bill17_full_noncash_offset(self):
    """An authorized label on an existing credit clears the receivable and is not cash."""
    _validation, request = _bill_ready_request(self, 400, '20000')
    _bill_policy(self)
    billing = _bill_post(self, request)
    credit = self._manual(move_type='out_refund', price=20000, quantity=1, post=True)
    invoice_line = billing.move_id.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')[:1]
    credit_line = credit.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')[:1]
    (invoice_line + credit_line).reconcile()
    moves = self.env['account.move'].search_count([('company_id', '=', self.company_a.id)])
    _bill_as(self, billing).action_refresh_collections()
    evidence = billing.evidence_ids.filtered('counts_current')[:1]
    _bill_as(self, billing).action_classify_settlement(
        evidence.partial_reconcile_key, 'other_settlement',
        'Apply this existing customer credit to the recovery receivable. It is not cash.',
    )
    self.assertEqual(self.env['account.move'].search_count([('company_id', '=', self.company_a.id)]), moves)
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    evidence = billing.evidence_ids.filtered('counts_current')[:1]
    self.assertEqual(evidence.classification, 'other_settlement')
    self.assertEqual(evidence.credit_category, 'SETTLEMENT_CREDIT')
    self.assertFalse(evidence.is_verified_cash)
    position = _bill_position(self, request)
    self._assert_amount(position['posted_principal'], '20000')
    self._assert_amount(position['other_settlement_principal'], '20000')
    self._assert_amount(position['verified_cash_principal'], '0')
    self._assert_amount(position['outstanding_principal'], '0')
    self._assert_amount(position['unbilled_target'], '0')
    self._assert_amount(position['accounting_residual'], '0')
    self.assertEqual(billing.state, 'posted')


def test_bill17_payment_reversal_keeps_history(self):
    """Unreconciling a payment removes it from current cash and keeps the old evidence row."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_post(self, request)
    payment = _bill_payment(self, billing.move_id, 3000)
    self.assertTrue(_bill_match_bank(self, payment, 3000))
    _bill_as(self, billing).action_refresh_collections()
    self._assert_amount(_bill_position(self, request)['verified_cash_principal'], '3000')
    receivable = billing.move_id.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')
    receivable.remove_move_reconcile()
    _bill_as(self, billing).action_refresh_collections()
    position = _bill_position(self, request)
    self._assert_amount(position['verified_cash_principal'], '0')
    self._assert_amount(position['outstanding_principal'], '5000')
    historical = billing.evidence_ids.filtered(lambda item: not item.counts_current)
    self.assertTrue(historical)
    self.assertEqual(historical.verification_state, 'REVERSAL')
    self.assertFalse(historical.is_verified_cash)
    self._assert_amount(historical.principal_exact, '3000')


def test_bill17_installment_aging(self):
    """Each open receivable installment is aged from its own maturity date."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_prepare(self, request)
    _bill_as(self, billing).action_create_draft()
    term = self.env['account.payment.term'].with_company(self.company_a).create({
        'name': 'CPLA recovery installments',
        'company_id': self.company_a.id,
        'early_discount': False,
        'line_ids': [
            Command.clear(),
            Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 10, 'delay_type': 'days_after'}),
            Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 130, 'delay_type': 'days_after'}),
        ],
    })
    billing.move_id.write({
        'invoice_date': self._on(-100),
        'invoice_payment_term_id': term.id,
    })
    _bill_as(self, billing).action_post()
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    lines = billing.move_id.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')
    self.assertGreaterEqual(len(lines), 2)
    self.assertGreaterEqual(len(set(lines.mapped('date_maturity'))), 2)
    today = self._today()
    expected = {
        'not_yet_due': Decimal('0'),
        'days_1_30': Decimal('0'),
        'days_31_60': Decimal('0'),
        'days_61_90': Decimal('0'),
        'days_over_90': Decimal('0'),
    }
    for line in lines:
        self.assertTrue(line.date_maturity)
        days = (today - line.date_maturity).days
        if days <= 0:
            label = 'not_yet_due'
        elif days <= 30:
            label = 'days_1_30'
        elif days <= 60:
            label = 'days_31_60'
        elif days <= 90:
            label = 'days_61_90'
        else:
            label = 'days_over_90'
        expected[label] += _money(line.amount_residual_currency)
    self.assertGreaterEqual(sum(1 for amount in expected.values() if amount > 0), 2)
    position = _bill_position(self, request)
    for label, amount in expected.items():
        self._assert_amount(position['aging'][label], amount)
    self.assertNotEqual(_money(position['aging']['not_yet_due']), Decimal('5000'))
    self.assertTrue(position['overdue'])
    self.assertGreater(position['overdue_days'], 0)


def test_bill17_stale_posted_flags_review(self):
    """A later source change flags the posted billing and leaves the invoice as it was posted."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_post(self, request)
    origin = billing.origin_move_id
    origin_price = origin.invoice_line_ids[:1].price_unit
    recovery_price = billing.move_id.invoice_line_ids[:1].price_unit
    finding = _bill_line(self, request).finding_id
    self.env['cpla.finance.validation']._flag_source_change(finding)
    billing = self.env['cpla.recovery.billing'].browse(billing.id)
    self.assertEqual(billing.move_id.state, 'posted')
    self.assertEqual(billing.move_id.invoice_line_ids[:1].price_unit, recovery_price)
    self.assertEqual(origin.invoice_line_ids[:1].price_unit, origin_price)
    position = _bill_position(self, request)
    self.assertIn('ACCOUNTING_IMPACT_REVIEW_REQUIRED', position['exception_codes'])
    self._assert_amount(position['posted_principal'], '5000')
    self._assert_amount(billing.posted_principal_exact, '5000')


def test_bill17_failed_read_is_not_zero(self):
    """A user who cannot read the accounting document does not receive a fabricated zero balance."""
    _validation, request = _bill_ready_request(self, 100, '5000')
    _bill_policy(self)
    billing = _bill_post(self, request)
    reader = new_test_user(
        self.env, login='cpla17_fin_plain', password='cpla-test',
        groups='base.group_user,%s.group_finance_manager' % MODULE,
        company_id=self.company_a.id, company_ids=[Command.set([self.company_a.id])],
    )
    self._fv_error(
        lambda: self._env(reader, self.company_a)['cpla.recovery.billing'].browse(billing.id).billing_position(),
        'TECHNICAL_ACCOUNTING_FAILURE',
    )


for _method in (
    _bill_env,
    _bill_income,
    _bill_tax,
    _bill_policy,
    _bill_ready_request,
    _bill_prepare,
    _bill_as,
    _bill_line,
    _bill_position,
    _bill_payment,
    _bill_match_bank,
    test_bill17_views_sequences_and_alerts,
    test_bill17_fx_difference_not_executed,
    test_bill17_policy_blocks,
    test_bill17_debit_note_method,
    test_bill17_golden_posted_and_bank_cash,
    test_bill17_partial_slices,
    test_bill17_waiver_is_not_billed,
    test_bill17_existing_document_link,
    test_bill17_manual_handoff_and_cancel,
    test_bill17_stale_blocks_post,
    test_bill17_security_company_and_four_eyes,
    test_bill17_credit_is_not_cash,
    test_bill17_tax_is_not_principal,
    test_bill17_multi_invoice_payment_uses_this_receivable,
    test_bill17_lock_date_blocks_post,
    test_bill17_dispute_blocks_billing,
    test_bill17_settlement_blocks_billing,
    test_bill17_advance_is_not_new_cash,
    test_bill17_writeoff_is_classified_not_created,
    test_bill17_concurrent_prepare,
    _bill_post,
    test_bill17_three_bank_payments,
    test_bill17_credit_plus_cash,
    test_bill17_unrelated_credit_needs_review,
    test_bill17_full_noncash_offset,
    test_bill17_payment_reversal_keeps_history,
    test_bill17_installment_aging,
    test_bill17_stale_posted_flags_review,
    test_bill17_failed_read_is_not_zero,
):
    setattr(TestDev12InvoiceAudit, _method.__name__, _method)
