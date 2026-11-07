import base64
import logging
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import Command, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'
_logger = logging.getLogger(__name__)


def _money(value):
    if value is False or value is None or value == '':
        return None
    return Decimal(str(value))


@tagged('post_install', '-at_install')
class TestDev13LeakageCase(TransactionCase):
    """Investigation cases over DEV-12 findings. Not finance validation or recovery."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env['res.company'].create({'name': 'ABC India'})
        cls.company_b = cls.env['res.company'].create({'name': 'ABC UAE'})
        chart = cls.env['account.chart.template']
        chart.with_company(cls.company_a).try_loading('generic_coa', cls.company_a, install_demo=False)
        chart.with_company(cls.company_b).try_loading('generic_coa', cls.company_b, install_demo=False)
        cls.owner = cls._make_user('cpla13_owner', 'group_contract_user', cls.company_a)
        cls.manager = cls._make_user('cpla13_manager', 'group_contract_manager', cls.company_a)
        cls.manager_b = cls._make_user('cpla13_manager_b', 'group_contract_manager', cls.company_b)
        cls.investigator = cls._make_user('cpla13_investigator', 'group_contract_user', cls.company_a)
        cls.investigator_b = cls._make_user('cpla13_investigator_b', 'group_contract_user', cls.company_b)
        cls.both = cls._make_user(
            'cpla13_both', 'group_contract_manager', cls.company_a,
            companies=cls.company_a | cls.company_b,
        )
        cls.finance = cls._make_account_user('cpla13_finance', 'group_finance_manager', cls.company_a)
        cls.reviewer = cls._make_account_user('cpla13_reviewer', 'group_finance_reviewer', cls.company_a)
        cls.combo = new_test_user(
            cls.env, login='cpla13_combo', password='cpla-test',
            groups='base.group_user,%s.group_contract_manager,%s.group_finance_reviewer' % (MODULE, MODULE),
            company_id=cls.company_a.id, company_ids=[Command.set([cls.company_a.id])],
        )
        cls.auditor = cls._make_user('cpla13_auditor', 'group_internal_auditor', cls.company_a)
        cls.admin = cls._make_user('cpla13_admin', 'group_app_admin', cls.company_a)
        cls.salesman = cls._make_sale_user('cpla13_salesman', cls.company_a)
        cls.recovery = cls._make_user('cpla13_recovery', 'group_recovery_operator', cls.company_a)
        cls.plain = new_test_user(
            cls.env, login='cpla13_plain', groups='base.group_user', password='cpla-test',
            company_id=cls.company_a.id, company_ids=[Command.set([cls.company_a.id])],
        )
        cls.policy_a = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_a.id,
            'change_reason': 'Candidate reference. Not an operational approval.',
        })
        cls.policy_b = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_b.id,
            'change_reason': 'Candidate reference. Not an operational approval.',
        })
        cls.policy_a.write({
            'quotation_compliance_mode': 'warning',
            'pricing_date_policy': 'order_confirmation',
        })
        cls.policy_b.write({
            'quotation_compliance_mode': 'warning',
            'pricing_date_policy': 'order_confirmation',
        })
        cls.partner = cls.env['res.partner'].with_company(cls.company_a).create({
            'name': 'XYZ Manufacturing', 'is_company': True, 'company_id': cls.company_a.id,
        })
        cls.other_partner = cls.env['res.partner'].with_company(cls.company_a).create({
            'name': 'Unrelated Buyer', 'is_company': True, 'company_id': cls.company_a.id,
        })
        cls.partner_b = cls.env['res.partner'].with_company(cls.company_b).create({
            'name': 'UAE Buyer', 'is_company': True, 'company_id': cls.company_b.id,
        })
        cls.bearing = cls.env['product.product'].create({
            'name': 'Industrial Bearing', 'type': 'consu', 'invoice_policy': 'order',
            'list_price': 9999.0, 'company_id': False, 'taxes_id': [Command.clear()],
        })
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.eur = cls.env.ref('base.EUR')
        if not cls.eur.active:
            cls.eur.active = True
        for company in (cls.company_a, cls.company_b):
            income = cls.env['account.account'].with_company(company).search([
                ('account_type', '=', 'income'),
            ], limit=1)
            cls.bearing.with_company(company).write({
                'property_account_income_id': income.id,
                'taxes_id': [Command.clear()],
            })
        cls._sequence = 0

    @classmethod
    def _make_user(cls, login, xmlid, company, companies=None, extra_groups=()):
        companies = companies or company
        names = ['base.group_user', '%s.%s' % (MODULE, xmlid)]
        names.extend('%s.%s' % (MODULE, extra) for extra in extra_groups)
        return new_test_user(
            cls.env, login=login, groups=','.join(names), password='cpla-test',
            company_id=company.id, company_ids=[Command.set(companies.ids)],
        )

    @classmethod
    def _make_account_user(cls, login, xmlid, company, companies=None):
        companies = companies or company
        return new_test_user(
            cls.env, login=login, password='cpla-test',
            groups='base.group_user,account.group_account_invoice,%s.%s' % (MODULE, xmlid),
            company_id=company.id, company_ids=[Command.set(companies.ids)],
        )

    @classmethod
    def _make_sale_user(cls, login, company, extra_groups=()):
        names = ['base.group_user', 'sales_team.group_sale_salesman']
        names.extend('%s.%s' % (MODULE, extra) for extra in extra_groups)
        return new_test_user(
            cls.env, login=login, groups=','.join(names), password='cpla-test',
            company_id=company.id, company_ids=[Command.set([company.id])],
        )

    def _env(self, user, company):
        return self.env(user=user, context={**self.env.context, 'allowed_company_ids': [company.id]})

    def _today(self):
        return fields.Date.context_today(self.env['cpla.leakage.case'])

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

    def _journal(self, company):
        return self.env['account.journal'].search([
            ('company_id', '=', company.id), ('type', '=', 'sale'),
        ], limit=1)

    def _invoice(self, company=None, partner=None, prices=None, quantity=500):
        company = company or self.company_a
        partner = partner or self.partner
        prices = prices or [1100]
        invoice = self.env['account.move'].with_company(company).create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'company_id': company.id,
            'journal_id': self._journal(company).id,
            'invoice_date': self._today(),
            'invoice_line_ids': [Command.create({
                'product_id': self.bearing.id,
                'quantity': quantity,
                'price_unit': price,
                'name': self.bearing.display_name,
                'tax_ids': [Command.clear()],
            }) for price in prices],
        })
        invoice.action_post()
        return invoice

    def _lines(self, invoice):
        return invoice.invoice_line_ids.filtered(lambda item: item.display_type == 'product')

    def _finding(self, amount='25000', category='UNAUTHORIZED_UNDERPRICING', status='potential',
                 partner=None, company=None, currency=None, version=None, line=None, identity=None):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
        currency = currency or company.currency_id
        if not line:
            invoice = self._invoice(company=company, partner=partner, quantity=500, prices=[1100])
            line = self._lines(invoice)[:1]
        self.__class__._sequence += 1
        token = self._sequence
        reference = self.env['ir.sequence'].with_company(company).next_by_code('cpla.leakage.finding')
        self.assertTrue(reference)
        values = {
            'reference': reference,
            'company_id': company.id,
            'move_id': line.move_id.id,
            'move_line_id': line.id,
            'partner_id': partner.id,
            'product_id': line.product_id.id,
            'version_id': version.id if version else False,
            'leakage_category': category,
            'approved_adjusted_exact': '1150',
            'actual_unit_exact': '1100',
            'eligible_quantity_exact': '500',
            'currency_id': currency.id,
            'potential_leakage_exact': amount if amount is not None else False,
            'finding_status': status,
            'current_identity': identity or 'c%s|l%s|a0|kcase%s|sUNDERBILLING' % (company.id, line.id, token),
            'is_current': True,
            'input_fingerprint': 'case-fp-%s' % token,
            'calculation_revision': 1,
            'first_detected_at': fields.Datetime.now(),
            'last_evaluated_at': fields.Datetime.now(),
            'engine_version': 'dev12.1',
            'is_recovered_cash': False,
            'source_revision': 1,
        }
        self.env['cpla.leakage.finding'].flush_model()
        return models.Model.create(self.env['cpla.leakage.finding'], [values])

    def _open(self, findings, basis=None, note=None, user=None):
        records = findings if hasattr(findings, 'ids') else self.env['cpla.leakage.finding'].browse(findings)
        actor = user or self.manager
        company = records[:1].company_id
        return self._env(actor, company)['cpla.leakage.case'].create_from_findings(
            records.ids, grouping_basis=basis, grouping_note=note,
        )

    def _as(self, user, case):
        return self._env(user, case.company_id)['cpla.leakage.case'].browse(case.id)

    def _assign(self, case, user=None):
        owner = user or self.investigator
        self._as(self.manager, case).action_assign(owner.id, 'Assign the authorized investigator.')
        return self._as(owner, case)

    def _investigate(self, case, user=None):
        owner = user or self.investigator
        case = self._as(self.manager, case)
        if case.state == 'new':
            case.action_assign(owner.id, 'Assign the authorized investigator.')
        case = self._as(owner, case)
        if case.state in ('assigned', 'returned_for_rework'):
            case.action_start()
        return case

    def _answer_required(self, case, answer='yes', note=None):
        for line in case.checklist_ids.filtered('required_for_submission'):
            case.action_answer_checklist(line.code, answer, note)
        return case

    def _verify_source(self, case):
        for evidence in case.evidence_ids.filtered(lambda item: item.evidence_kind == 'source'):
            case.action_verify_evidence(evidence.id, 'Source record reviewed.')
        return case

    def _conclude(self, case, root='missed_contract_price_increase', outcome='likely_missed_price_increase'):
        case.action_record_root_cause(root, 'The invoice rate does not match the approved contract rate.')
        case.action_record_outcome(outcome, 'The investigator conclusion is not a finance validation.')
        return case

    def _ready_potential(self, case, user=None):
        case = self._investigate(case, user)
        self._answer_required(case)
        self._verify_source(case)
        self._conclude(case)
        return case

    def _payments(self):
        return self.env['account.payment'].search_count([])

    def _v1(self, price):
        env = self._env(self.owner, self.company_a)
        contract = env['cpla.customer.contract'].create({
            'name': 'Negotiated bearings',
            'company_id': self.company_a.id,
            'partner_id': self.partner.id,
            'owner_id': self.owner.id,
            'currency_id': self.company_a.currency_id.id,
            'valid_from': self._on(-30),
            'valid_to': self._on(180),
            'policy_id': self.policy_a.id,
        })
        env['cpla.customer.contract.line'].create({
            'contract_id': contract.id,
            'product_id': self.bearing.id,
            'price_unit': price,
            'uom_id': self.bearing.uom_id.id,
        })
        env['cpla.customer.contract.evidence'].create({
            'contract_id': contract.id,
            'name': 'signed-agreement.pdf',
            'document_type': 'signed_agreement',
            'source_reference': 'AGR-013',
            'description': 'Signed pricing schedule.',
            'datas': 'c2lnbmVk',
        })
        contract.action_submit_for_review()
        return self._env(self.manager, self.company_a)['cpla.customer.contract.version'].approve_initial(
            self._env(self.manager, self.company_a)['cpla.customer.contract'].browse(contract.id)
        )

    def _priced(self, price='1150'):
        first = self._v1(price)
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Authorized price clause. Not a retroactive restatement.',
            'effective_from': self._today(),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        amendment.line_ids.write({'price_unit': price})
        amendment.action_submit_for_review()
        record = self._env(self.finance, self.company_a)['cpla.customer.contract.version'].browse(amendment.id)
        record.action_approve()
        return record

    def _pricelist(self):
        currency = self.company_a.currency_id
        pricelist = self.env['product.pricelist'].search([
            ('company_id', 'in', [False, self.company_a.id]),
            ('currency_id', '=', currency.id),
        ], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': 'CPLA13 %s' % currency.name,
                'currency_id': currency.id,
                'company_id': self.company_a.id,
            })
        return pricelist

    def _quote(self, price, quantity):
        order = self.env['sale.order'].with_company(self.company_a).create({
            'partner_id': self.partner.id,
            'company_id': self.company_a.id,
            'pricelist_id': self._pricelist().id,
            'currency_id': self.company_a.currency_id.id,
            'user_id': self.salesman.id,
            'order_line': [Command.create({
                'product_id': self.bearing.id,
                'product_uom_qty': quantity,
            })],
        })
        line = order.order_line.filtered(lambda item: not item.display_type)[:1]
        line.write({
            'price_unit': price,
            'technical_price_unit': 0,
            'discount': 0,
            'tax_ids': [Command.clear()],
        })
        return order

    def _posted_sale_invoice(self, price, quantity):
        order = self._quote(price, quantity)
        order.action_confirm()
        invoice = order._create_invoices()
        self._lines(invoice).write({'price_unit': price, 'quantity': quantity, 'tax_ids': [Command.clear()]})
        invoice.invoice_date = self._today()
        invoice.action_post()
        return order, invoice

    def _audit(self):
        run = self.env['cpla.invoice.audit.run'].create({
            'company_id': self.company_a.id,
            'date_from': self._on(-500),
            'date_to': self._on(5),
            'date_basis': 'invoice_date',
            'mode': 'on_demand',
        })
        run.action_run()
        return run

    def _current_potential(self):
        return self.env['cpla.leakage.finding'].search([
            ('company_id', '=', self.company_a.id),
            ('is_current', '=', True),
            ('finding_status', '=', 'potential'),
        ])

    def test_case13_creation_company_reference_and_reuse(self):
        """CASE13-T001 T002 T003 T005 T006 T007 T008 T012 and CASE-REF-001."""
        self._priced('1150')
        _order, invoice = self._posted_sale_invoice(1100, 500)
        line = self._lines(invoice)
        price_before = line.price_unit
        moves = self.env['account.move'].search_count([])
        payments = self._payments()
        self._audit()
        finding = self._current_potential().filtered(lambda item: item.move_id == invoice)
        self.assertEqual(len(finding), 1)
        self.assertEqual(_money(finding.potential_leakage_exact), Decimal('25000'))
        amount_before = finding.potential_leakage_exact
        case = self._open(finding)
        again = self._open(finding)
        self.assertEqual(case, again)
        self.assertEqual(case.company_id, self.company_a)
        self.assertEqual(case.partner_id, self.partner)
        self.assertEqual(case.state, 'new')
        self.assertRegex(case.reference, r'^CPL-CASE/\d{4}/\d{5}$')
        self.assertEqual(case.current_potential_exposure_exact, '25000')
        self.assertEqual(case.reviewed_exposure_exact, '25000')
        self.assertEqual(finding.potential_leakage_exact, amount_before)
        self.assertTrue(case.membership_ids.filtered('is_current'))
        self.assertNotIn('finance_validated_exact', case._fields)
        self.assertNotIn('billed_recovery_exact', case._fields)
        self.assertNotIn('collected_recovery_exact', case._fields)
        self.assertFalse(finding.is_recovered_cash)
        self.assertEqual(line.price_unit, price_before)
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(self.env['account.move'].search_count([]), moves)
        self.assertEqual(self._payments(), payments)
        self.assertEqual(len(self.env['cpla.leakage.case.membership'].search([
            ('finding_id', '=', finding.id), ('is_current', '=', True),
        ])), 1)

    def test_case13_t004_only_a_manager_opens_a_case(self):
        finding = self._finding('25000')
        with self.assertRaises(AccessError):
            self._open(finding, user=self.investigator)
        with self.assertRaises(AccessError):
            self._open(finding, user=self.reviewer)
        with self.assertRaises(AccessError):
            self._open(finding, user=self.auditor)
        case = self._open(finding)
        self.assertEqual(case.state, 'new')

    def test_case13_t009_t010_exception_case_keeps_a_blank_amount(self):
        """CASE13-T009 T010, CASE-REF-008 and CASE-REF-009."""
        missing = self._finding(
            amount=None, category='MISSING_PRICING_EVIDENCE', status='review_required',
        )
        case = self._open(missing)
        self.assertEqual(case.case_type, 'pricing_evidence_exception')
        self.assertEqual(case.exception_queue, 'pricing_date_review')
        self.assertFalse(case.current_potential_exposure_exact)
        self.assertGreaterEqual(case.exposure_unknown_count, 1)
        self.assertNotEqual(case.current_potential_exposure_exact, '0')
        conflict = self._finding(
            amount=None, category='CONTRACT_CONFLICT_REVIEW_REQUIRED', status='review_required',
        )
        conflict_case = self._open(conflict)
        self.assertEqual(conflict_case.case_type, 'conflict_review')
        self.assertEqual(conflict_case.exception_queue, 'contract_review')
        self.assertFalse(conflict_case.current_potential_exposure_exact)
        coverage = self._open(self._finding(
            amount=None, category='CONTRACT_COVERAGE_EXCEPTION', status='review_required',
        ))
        self.assertEqual(coverage.exception_queue, 'contract_review')
        fx = self._open(self._finding(
            amount=None, category='FX_OR_TAX_REVIEW_REQUIRED', status='review_required',
        ))
        self.assertEqual(fx.exception_queue, 'financial_normalization_review')
        source = self._open(self._finding(
            amount=None, category='SOURCE_ALLOCATION_REVIEW_REQUIRED', status='review_required',
        ))
        self.assertEqual(source.exception_queue, 'source_mapping_review')
        refund = self._open(self._finding(
            amount=None, category='REFUND_REASSESSMENT_REQUIRED', status='review_required',
        ))
        self.assertEqual(refund.case_type, 'refund_reassessment_exception')
        self.assertEqual(refund.exception_queue, 'credit_refund_review')
        other = self._open(self._finding(
            amount=None, category='TECHNICAL_AUDIT_FAILURE', status='review_required',
        ))
        self.assertEqual(other.exception_queue, 'other_evidence_review')
        monetary = self._finding('25000', category='UNAUTHORIZED_DISCOUNT_INDICATOR')
        discount_case = self._open(monetary)
        self.assertFalse(discount_case.exception_queue)
        self.assertEqual(discount_case.case_type, 'potential_leakage')
        selection = dict(discount_case._fields['exception_queue'].selection)
        self.assertIn('discount_approval_review', selection)
        self.assertIn('security_or_company_exception', selection)

    def test_case13_t011_historical_revision_is_not_a_second_case(self):
        current = self._finding('25000')
        historical = self._finding('25000')
        historical.write({
            'is_current': False,
            'current_identity': False,
            'finding_status': 'superseded_by_reassessment',
        })
        with self.assertRaises(UserError):
            self._open(historical)
        case = self._open(current)
        self.assertEqual(case.current_potential_exposure_exact, '25000')
        self.assertEqual(self.env['cpla.leakage.case'].search_count([
            ('membership_ids.finding_id', '=', historical.id),
        ]), 0)

    def test_grp13_three_findings_sum_and_customer_company_currency_guards(self):
        """GRP13-T001 through T008 and CASE-REF-002, 004, 005."""
        one = self._finding('25000')
        self.assertEqual(self._open(one).current_potential_exposure_exact, '25000')
        first, second, third = self._finding('10000'), self._finding('10000'), self._finding('5000')
        with self.assertRaises(UserError):
            self._open(first | second | third)
        with self.assertRaises(UserError):
            self._open(first | second, basis='same_customer', note='Customer match is not enough.')
        grouped = self._open(
            first | second | third, basis='explicit_same_issue', note='One rate problem on related invoices.',
        )
        self.assertEqual(len(grouped.membership_ids.filtered('is_current')), 3)
        self.assertEqual(grouped.current_potential_exposure_exact, '25000')
        self.assertEqual(len(grouped), 1)
        repeated = self._open(
            first | second | third, basis='explicit_same_issue', note='Repeat.',
        )
        self.assertEqual(repeated, grouped)
        self.assertEqual(len(self.env['cpla.leakage.case.membership'].search([
            ('finding_id', 'in', (first | second | third).ids), ('is_current', '=', True),
        ])), 3)
        left = self._finding('10000', partner=self.partner)
        right = self._finding('10000', partner=self.other_partner)
        with self.assertRaises(UserError):
            self._open(left | right, basis='explicit_same_issue', note='Different customers.')
        self.assertNotEqual(self._open(left).id, self._open(right).id)
        local = self._finding('10000')
        foreign = self._finding('10000', company=self.company_b, partner=self.partner_b)
        with self.assertRaises(UserError):
            self.env(user=self.both, context={'allowed_company_ids': [self.company_a.id, self.company_b.id]})[
                'cpla.leakage.case'
            ].create_from_findings(
                [local.id, foreign.id], grouping_basis='explicit_same_issue', grouping_note='Cross company.',
            )
        priced = self._finding('10000')
        unknown = self._finding(amount=None, category='CONTRACT_COVERAGE_EXCEPTION', status='review_required')
        with self.assertRaises(UserError):
            self._open(priced | unknown, basis='explicit_same_issue', note='Unknown plus known.')
        inr = self._finding('10000')
        other = self._finding('10000', currency=self.eur)
        with self.assertRaises(UserError):
            self._open(inr | other, basis='explicit_same_issue', note='Two currencies.')
        historical = self._finding('9000')
        historical.write({
            'is_current': False,
            'current_identity': False,
            'finding_status': 'superseded_by_reassessment',
        })
        live = self._finding('10000')
        case = self._open(live)
        self.assertEqual(case.current_potential_exposure_exact, '10000')
        self.assertNotEqual(case.current_potential_exposure_exact, '19000')

    def test_grp13_same_invoice_order_and_version_bases(self):
        """GRP13-T002 approved bases other than explicit attestation."""
        invoice = self._invoice(prices=[1100, 1000], quantity=100)
        lines = self._lines(invoice)
        self.assertEqual(len(lines), 2)
        findings = self._finding('1000', line=lines[0]) | self._finding('500', line=lines[1])
        case = self._open(findings, basis='same_invoice', note='Same invoice.')
        self.assertEqual(case.current_potential_exposure_exact, '1500')
        order = self._quote(1100, 1)
        alpha = self._finding('2000')
        beta = self._finding('3000')
        run = self.env['cpla.invoice.audit.run'].create({
            'company_id': self.company_a.id,
            'date_from': self._on(-5),
            'date_to': self._on(5),
        })
        for finding in alpha | beta:
            models.Model.create(self.env['cpla.invoice.audit.result'], [{
                'run_id': run.id,
                'company_id': self.company_a.id,
                'move_id': finding.move_id.id,
                'move_line_id': finding.move_line_id.id,
                'finding_id': finding.id,
                'sale_order_id': order.id,
                'partner_id': finding.partner_id.id,
                'result_classification': 'UNAUTHORIZED_UNDERPRICING',
                'potential_exposure_exact': finding.potential_leakage_exact,
                'engine_version': 'dev12.1',
                'is_recovered_cash': False,
            }])
        ordered = self._open(alpha | beta, basis='same_sales_order', note='Same sales order.')
        self.assertEqual(ordered.current_potential_exposure_exact, '5000')
        self.assertEqual(ordered.order_count, 1)
        version = self._priced('1150')
        versioned = self._finding('4000', version=version) | self._finding('1000', version=version)
        version_case = self._open(versioned, basis='same_contract_version', note='Same version.')
        self.assertEqual(version_case.current_potential_exposure_exact, '5000')
        mismatched = self._finding('1000') | self._finding('1000')
        with self.assertRaises(UserError):
            self._open(mismatched, basis='same_contract_version', note='No shared version.')

    def test_grp13_merge_and_split_preserve_findings(self):
        """GRP13-T009 through T012 and CASE-REF-013 and CASE-REF-014."""
        left = self._open(self._finding('10000') | self._finding('10000'), basis='explicit_same_issue', note='Pair.')
        right_finding = self._finding('5000')
        right = self._open(right_finding)
        finding_ids = (left.membership_ids | right.membership_ids).finding_id
        amounts = {finding.id: finding.potential_leakage_exact for finding in finding_ids}
        left.action_merge(right.id, 'The third invoice belongs to the same rate issue.')
        self.assertEqual(left.current_potential_exposure_exact, '25000')
        self.assertEqual(right.state, 'closed_with_reason')
        self.assertEqual(right.closure_reason, 'superseded_by_case')
        self.assertEqual(right.superseded_by_case_id, left)
        self.assertTrue(right.exists())
        for finding in finding_ids:
            self.assertTrue(finding.exists())
            self.assertEqual(finding.potential_leakage_exact, amounts[finding.id])
        self.assertEqual(len(left.membership_ids.filtered('is_current')), 3)
        self.assertFalse(right.membership_ids.filtered('is_current'))
        self.assertTrue(left.event_ids.filtered(lambda item: item.event_type == 'merged'))
        self.assertTrue(right.event_ids.filtered(lambda item: item.event_type == 'closed'))
        spawned = left.action_split([right_finding.id], 'This invoice is a separate issue.')
        self.assertEqual(left.current_potential_exposure_exact, '20000')
        self.assertEqual(spawned.current_potential_exposure_exact, '5000')
        self.assertEqual(
            _money(left.current_potential_exposure_exact) + _money(spawned.current_potential_exposure_exact),
            Decimal('25000'),
        )
        self.assertEqual(len(self.env['cpla.leakage.case.membership'].search([
            ('finding_id', 'in', finding_ids.ids), ('is_current', '=', True),
        ])), 3)
        self.assertTrue(left.event_ids.filtered(lambda item: item.event_type == 'split'))
        with self.assertRaises(UserError):
            left.action_split(left.membership_ids.filtered('is_current').finding_id.ids, 'Leave none behind.')
        foreign = self._open(self._finding('1000', company=self.company_b, partner=self.partner_b), user=self.manager_b)
        with self.assertRaises(UserError):
            self._as(self.both, left).action_merge(foreign.id, 'Different companies.')

    def test_wf13_lifecycle_submission_return_close_and_reopen(self):
        """WF13-T001 through T016 and CASE-REF-006, 010, 011, 012, 016, 017."""
        finding = self._finding('25000')
        case = self._open(finding)
        self.assertEqual(case.state, 'new')
        self.assertFalse(case.owner_id)
        self.assertFalse(case.priority)
        with self.assertRaises(AccessError):
            self._as(self.investigator, case).action_assign(self.investigator.id, 'Self assignment.')
        case = self._assign(case)
        self.assertEqual(case.state, 'assigned')
        self.assertEqual(case.owner_id, self.investigator)
        self.assertTrue(case.event_ids.filtered(lambda item: item.event_type == 'assigned'))
        with self.assertRaises(UserError):
            case.action_submit_for_finance()
        case.action_start()
        self.assertEqual(case.state, 'under_investigation')
        case.action_mark_evidence_pending('The signed amendment is not attached.')
        self.assertEqual(case.state, 'evidence_pending')
        self.assertTrue(case.evidence_requested_at)
        case.action_resume_investigation()
        with self.assertRaises(UserError):
            case.action_submit_for_finance()
        self._answer_required(case)
        with self.assertRaises(UserError):
            case.action_submit_for_finance()
        self._verify_source(case)
        self.assertEqual(case.evidence_status, 'verified')
        with self.assertRaises(UserError):
            case.action_record_root_cause('missed_contract_price_increase', ' ')
        case.action_record_root_cause(
            'missed_contract_price_increase',
            'The invoice kept the earlier rate after the approved increase.',
        )
        self.assertNotEqual(case.root_cause, finding.leakage_category)
        self.assertNotIn('fraud', (case.root_cause or '').lower())
        case.action_record_outcome(
            'likely_missed_price_increase',
            'This is an investigator conclusion, not finance validation.',
        )
        moves = self.env['account.move'].search_count([])
        payments = self._payments()
        case.action_submit_for_finance()
        self.assertEqual(case.state, 'ready_for_finance_review')
        self.assertEqual(case.submitted_by_id, self.investigator)
        submission = case.submission_ids
        self.assertEqual(len(submission), 1)
        self.assertEqual(submission.potential_exposure_exact, '25000')
        self.assertIn(str(finding.id), submission.finding_snapshot)
        self.assertNotIn('finance_validated', submission.finding_snapshot)
        self.assertEqual(self.env['account.move'].search_count([]), moves)
        self.assertEqual(self._payments(), payments)
        with self.assertRaises(UserError):
            self._as(self.manager, case).action_close('duplicate_case', 'Cannot bypass finance review.')
        with self.assertRaises(AccessError):
            case.action_return_for_rework('Need the invoice source.', 'Attach the source map.')
        self._as(self.reviewer, case).action_return_for_rework(
            'Invoice source is not verified.',
            'Link the confirmed sales order and resubmit.',
        )
        self.assertEqual(case.state, 'returned_for_rework')
        self.assertEqual(case.returned_by_id, self.reviewer)
        self.assertTrue(case.returned_at)
        self.assertEqual(submission.potential_exposure_exact, '25000')
        self.assertTrue(submission.return_reason)
        self.assertEqual(len(case.submission_ids), 1)
        case.action_start()
        case.action_submit_for_finance()
        self.assertEqual(len(case.submission_ids), 2)
        self.assertEqual(case.submission_ids.sorted('id')[0].potential_exposure_exact, '25000')
        self._as(self.reviewer, case).action_return_for_rework(
            'Still missing the order link.',
            'Add the sales order evidence.',
        )
        self._as(self.manager, case).action_close(
            'duplicate_case',
            'A separate case already investigates this commercial issue.',
        )
        self.assertEqual(case.state, 'closed_with_reason')
        self.assertEqual(case.closure_reason, 'duplicate_case')
        self.assertTrue(finding.exists())
        self.assertEqual(finding.potential_leakage_exact, '25000')
        self.assertFalse(finding.is_recovered_cash)
        self.assertTrue(case.membership_ids.filtered('is_current'))
        self.assertEqual(self._payments(), payments)
        self.assertEqual(self._open(finding), case)
        self._as(self.manager, case).action_reopen('A later amendment was produced for review.')
        self.assertEqual(case.state, 'under_investigation')
        self.assertTrue(case.reopened_at)
        self.assertTrue(case.event_ids.filtered(lambda item: item.event_type == 'closed'))
        self.assertTrue(case.event_ids.filtered(lambda item: item.event_type == 'reopened'))
        self.assertEqual(len(self.env['cpla.leakage.case.membership'].search([
            ('finding_id', '=', finding.id), ('is_current', '=', True),
        ])), 1)
        with self.assertRaises(UserError):
            self._as(self.manager, case).write({'state': 'ready_for_finance_review'})
        with self.assertRaises(UserError):
            self._as(self.manager, case).create({
                'reference': 'CPL-CASE/2026/99999',
                'title': 'Forged',
                'company_id': self.company_a.id,
                'partner_id': self.partner.id,
                'case_type': 'potential_leakage',
                'opened_at': fields.Datetime.now(),
            })

    def test_wf13_t010_submitter_cannot_return_the_same_case(self):
        finding = self._finding('25000')
        case = self._ready_potential(self._open(finding, user=self.combo), user=self.combo)
        case.action_submit_for_finance()
        self.assertEqual(case.submitted_by_id, self.combo)
        with self.assertRaises(AccessError):
            case.action_return_for_rework('Own submission.', 'More evidence.')
        self.assertEqual(case.state, 'ready_for_finance_review')

    def test_wf13_required_no_answer_must_be_disclosed(self):
        finding = self._finding('25000')
        case = self._investigate(self._open(finding))
        for line in case.checklist_ids.filtered('required_for_submission'):
            answer = 'no' if line.code == 'ready_for_finance_review' else 'yes'
            case.action_answer_checklist(line.code, answer)
        self._verify_source(case)
        self._conclude(case)
        with self.assertRaises(UserError):
            case.action_submit_for_finance()
        self._as(self.manager, case).write({
            'outstanding_qualification': 'The pricing date is still uncertain.',
        })
        case.action_submit_for_finance()
        self.assertEqual(case.state, 'ready_for_finance_review')
        self.assertNotIn('finance_validated_exact', case._fields)

    def test_own13_assignment_priority_activity_and_no_threshold(self):
        """OWN13-T001 through T012 and CASE-REF-007 and CASE-REF-018."""
        finding = self._finding('25000')
        case = self._open(finding)
        self.assertFalse(case.owner_id)
        self.assertFalse(case.priority)
        self.assertFalse(case.severity)
        self.assertFalse(case.target_review_date)
        with self.assertRaises(AccessError):
            self._as(self.manager, case).action_assign(self.investigator_b.id, 'Wrong company.')
        with self.assertRaises(AccessError):
            self._as(self.manager, case).action_assign(self.admin.id, 'Technical admin is not an investigator.')
        with self.assertRaises(AccessError):
            self._as(self.manager, case).action_assign(self.reviewer.id, 'Finance is not the investigator.')
        with self.assertRaises(AccessError):
            self._as(self.manager, case).action_assign(self.salesman.id, 'Sales is not the investigator.')
        case.action_assign(self.investigator.id, 'Company A investigator.')
        self.assertIn(self.company_a, self.investigator.company_ids)
        previous = case.owner_id
        case.action_assign(self.manager.id, 'Manager takes the investigation.')
        change = case.event_ids.filtered(lambda item: item.event_type == 'owner_changed')
        self.assertTrue(change)
        self.assertIn(previous.name, change[-1].previous_value or previous.display_name)
        self.assertEqual(case.owner_id, self.manager)
        self.assertTrue(case.event_ids.filtered(lambda item: item.event_type == 'assigned'))
        case.action_set_priority('high', 'Manager review. No amount threshold is configured.')
        case.action_set_severity('medium', 'Severity is a label, not a money rule.')
        self.assertEqual(case.priority, 'high')
        self.assertNotEqual(case.current_potential_exposure_exact, case.priority)
        with self.assertRaises(UserError):
            case.action_set_priority('critical', ' ')
        cron_before = self.env['ir.cron'].search_count([])
        activity = case.action_schedule_activity(
            self.manager.id, self._on(14), 'Review the contract rate', 'No recovery letter.',
        )
        self.assertEqual(activity.user_id, self.manager)
        self.assertEqual(activity.date_deadline, self._on(14))
        self.assertFalse(activity.automated)
        activity.action_feedback(feedback='Evidence reviewed. No leakage was validated.')
        self.assertEqual(case.state, 'assigned')
        self.assertEqual(finding.potential_leakage_exact, '25000')
        self.assertFalse(finding.is_recovered_cash)
        self.assertEqual(self.env['ir.cron'].search_count([]), cron_before)
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE), ('model', '=', 'ir.cron'),
        ]))
        with self.assertRaises(UserError):
            case.action_schedule_activity(self.manager.id, False, 'Missing date')
        self._as(self.manager, case).write({'target_review_date': self._on(-1)})
        self.assertTrue(case.is_overdue)
        self.assertIn('business-day', case._fields['age_calendar_days'].help)
        closed = self._open(self._finding('1000'))
        self._as(self.manager, closed).action_close('not_in_scope', 'Outside the investigation scope.')
        self.assertFalse(closed.is_overdue)

    def test_evd13_evidence_history_snapshot_and_chatter(self):
        """EVD13-T001 through T014 and CASE-REF-019."""
        version = self._priced('1150')
        finding = self._finding('25000', version=version)
        run = self.env['cpla.invoice.audit.run'].create({
            'company_id': self.company_a.id,
            'date_from': self._on(-5),
            'date_to': self._on(5),
        })
        result = models.Model.create(self.env['cpla.invoice.audit.result'], [{
            'run_id': run.id,
            'company_id': self.company_a.id,
            'move_id': finding.move_id.id,
            'move_line_id': finding.move_line_id.id,
            'finding_id': finding.id,
            'version_id': version.id,
            'partner_id': finding.partner_id.id,
            'result_classification': 'UNAUTHORIZED_UNDERPRICING',
            'potential_exposure_exact': '25000',
            'engine_version': 'dev12.1',
            'is_recovered_cash': False,
        }])
        case = self._investigate(self._open(finding))
        source_models = {line.source_model for line in case.evidence_ids}
        self.assertIn('cpla.leakage.finding', source_models)
        self.assertIn('cpla.invoice.audit.result', source_models)
        self.assertIn('account.move', source_models)
        self.assertIn('cpla.customer.contract.version', source_models)
        self.assertTrue(case.evidence_ids.filtered(
            lambda item: item.source_res_id == result.id and item.status == 'received'
        ))
        self.assertTrue(any(item.answer == 'unanswered' for item in case.checklist_ids))
        extra = case.evidence_ids.filtered(lambda item: item.evidence_kind == 'investigation')[:1]
        case.action_request_evidence(extra.id, 'Ask sales for the approval email.')
        self.assertEqual(extra.status, 'requested')
        self.assertEqual(extra.requested_by_id, self.investigator)
        self.assertTrue(case.event_ids.filtered(lambda item: item.event_type == 'evidence_requested'))
        with self.assertRaises(UserError):
            case.action_reject_evidence(extra.id, ' ')
        case.action_reject_evidence(extra.id, 'The email does not approve this price.')
        self.assertEqual(extra.status, 'rejected')
        self.assertEqual(extra.reviewed_by_id, self.investigator)
        with self.assertRaises(UserError):
            case.action_mark_evidence_not_applicable(extra.id, '')
        source = case.evidence_ids.filtered(lambda item: item.evidence_kind == 'source')[:1]
        case.action_verify_evidence(source.id, 'Reviewed.')
        self.assertEqual(source.reviewed_by_id, self.investigator)
        with self.assertRaises(UserError):
            case.action_submit_for_finance()
        event = case.event_ids[:1]
        with self.assertRaises(UserError):
            event.write({'reason': 'forged'})
        with self.assertRaises(UserError):
            event.unlink()
        with self.assertRaises(UserError):
            self.env['cpla.leakage.case.event'].create({
                'case_id': case.id,
                'company_id': case.company_id.id,
                'event_type': 'created',
                'actor_id': self.env.user.id,
                'occurred_at': fields.Datetime.now(),
            })
        line = case.checklist_ids[:1]
        with self.assertRaises(UserError):
            line.write({'required_for_submission': False})
        amount = finding.potential_leakage_exact
        self._as(self.manager, case).write({'investigation_summary': 'A note does not change the amount.'})
        self.assertEqual(finding.potential_leakage_exact, amount)
        self.assertEqual(result.potential_exposure_exact, '25000')
        with self.assertRaises(AccessError):
            case.message_subscribe(partner_ids=[self.partner.id])
        self.assertNotIn(self.partner, case.message_partner_ids)
        with self.assertRaises(AccessError):
            self._as(self.auditor, case).message_post(body='Auditor note')
        posted = case.message_post(body='Internal review note')
        self.assertTrue(posted)
        self.assertIn(self.investigator.partner_id, case.message_partner_ids)
        attachment = self.env['ir.attachment'].create({
            'name': 'contract-rate.pdf',
            'datas': base64.b64encode(b'confidential rate'),
            'res_model': 'cpla.leakage.case',
            'res_id': case.id,
            'company_id': case.company_id.id,
        })
        with self.assertRaises(UserError):
            self.env['ir.attachment'].create({
                'name': 'public.pdf',
                'datas': base64.b64encode(b'secret'),
                'res_model': 'cpla.leakage.case',
                'res_id': case.id,
                'public': True,
            })
        with self.assertRaises(UserError):
            attachment.generate_access_token()
        with self.assertRaises(UserError):
            attachment.unlink()
        with self.assertRaises(AccessError):
            self._env(self.manager_b, self.company_b)['ir.attachment'].browse(attachment.id).read(['datas'])

    def test_evd13_submission_snapshot_survives_return(self):
        finding = self._finding('25000')
        case = self._ready_potential(self._open(finding))
        case.action_submit_for_finance()
        snapshot = case.submission_ids.finding_snapshot
        exposure = case.submission_ids.potential_exposure_exact
        revision = case.submission_ids.case_revision
        self._as(self.reviewer, case).action_return_for_rework(
            'Need the contract attachment.',
            'Verify the signed version.',
        )
        self.assertEqual(case.submission_ids.finding_snapshot, snapshot)
        self.assertEqual(case.submission_ids.potential_exposure_exact, exposure)
        self.assertEqual(case.submission_ids.case_revision, revision)
        self.assertTrue(case.submission_ids.returned_at)

    def test_fin13_exposure_revision_and_downstream_amounts(self):
        """FIN13-T001 through T014 and CASE-REF-015 and CASE-REF-020."""
        finding = self._finding('25000')
        case = self._open(finding)
        self.assertEqual(case.current_potential_exposure_exact, finding.potential_leakage_exact)
        self.assertEqual(case.current_potential_exposure_exact, '25000')
        parts = self._finding('10000') | self._finding('10000') | self._finding('5000')
        grouped = self._open(parts, basis='explicit_same_issue', note='Three current findings.')
        self.assertEqual(grouped.current_potential_exposure_exact, '25000')
        again = self._open(parts[:1])
        self.assertEqual(again, grouped)
        self.assertEqual(grouped.current_potential_exposure_exact, '25000')
        blank = self._open(self._finding(
            amount=None, category='CONTRACT_COVERAGE_EXCEPTION', status='review_required',
        ))
        self.assertFalse(blank.current_potential_exposure_exact)
        self.assertNotEqual(blank.current_potential_exposure_exact, '0')
        with self.assertRaises(UserError):
            self._open(self._finding('1', currency=self.eur) | self._finding('1'), basis='explicit_same_issue', note='Mixed.')
        self.assertNotIn('finance_validated_exact', case._fields)
        self.assertNotIn('recovery_target_exact', case._fields)
        moves = self.env['account.move'].search_count([])
        payments = self._payments()
        self._as(self.manager, case).write({'investigation_summary': 'Propose 1.'})
        self.assertEqual(case.current_potential_exposure_exact, '25000')
        self.assertEqual(finding.potential_leakage_exact, '25000')
        self.assertEqual(self.env['account.move'].search_count([]), moves)
        self.assertEqual(self._payments(), payments)
        identity = finding.current_identity
        reviewed = case.reviewed_exposure_exact
        finding.write({
            'is_current': False,
            'current_identity': False,
            'finding_status': 'superseded_by_reassessment',
        })
        successor = self._finding('4000', line=finding.move_line_id, identity=identity)
        successor_amount = successor.potential_leakage_exact
        case.action_refresh_source_status()
        self.assertTrue(case.source_reassessment_required)
        self.assertFalse(case.current_potential_exposure_exact)
        self.assertEqual(case.reviewed_exposure_exact, reviewed)
        ready = self._investigate(case)
        self._answer_required(ready)
        self._verify_source(ready)
        self._conclude(ready)
        with self.assertRaises(UserError):
            ready.action_submit_for_finance()
        ready.action_accept_current_source('The verified return reduced the current finding to 4000.')
        self.assertEqual(ready.current_potential_exposure_exact, '4000')
        self.assertEqual(ready.reviewed_exposure_exact, '4000')
        self.assertEqual(successor.potential_leakage_exact, successor_amount)
        self.assertNotEqual(ready.current_potential_exposure_exact, '9000')
        self.assertFalse(finding.is_current)
        self.assertTrue(ready.event_ids.filtered(
            lambda item: item.event_type == 'source_revision_accepted' and item.previous_value == '25000'
        ))
        self._as(self.manager, ready).action_close('source_error', 'The source was corrected.')
        self.assertEqual(ready.current_potential_exposure_exact, '4000')
        self.assertFalse(successor.is_recovered_cash)
        self.assertEqual(self._payments(), payments)

    def test_fin13_t002_authorized_price_is_not_opened_as_leakage(self):
        self._priced('1150')
        _order, invoice = self._posted_sale_invoice(1150, 100)
        self._audit()
        self.assertFalse(self._current_potential().filtered(lambda item: item.move_id == invoice))
        self.assertFalse(self.env['cpla.leakage.case'].search([
            ('membership_ids.finding_id.move_id', '=', invoice.id),
        ]))

    def test_fin13_t006_credit_reassessment_does_not_invent_cash(self):
        self._priced('1150')
        _order, invoice = self._posted_sale_invoice(1100, 100)
        self._audit()
        finding = self._current_potential().filtered(lambda item: item.move_id == invoice)
        self.assertEqual(len(finding), 1)
        case = self._open(finding)
        reviewed = case.reviewed_exposure_exact
        payments = self._payments()
        credit = invoice._reverse_moves()
        credit.action_post()
        self._audit()
        case.action_refresh_source_status()
        self.assertTrue(case.source_reassessment_required)
        self.assertFalse(case.current_potential_exposure_exact)
        self.assertEqual(case.reviewed_exposure_exact, reviewed)
        self.assertEqual(self._payments(), payments)
        self.assertFalse(finding.is_recovered_cash)

    def test_sec13_company_roles_rpc_and_history(self):
        """SEC13-T001 through T016."""
        finding = self._finding('25000')
        case = self._open(finding)
        self.assertEqual(self._as(self.investigator, case).reference, case.reference)
        self.assertFalse(self._env(self.manager_b, self.company_b)['cpla.leakage.case'].search([
            ('id', '=', case.id),
        ]))
        with self.assertRaises(AccessError):
            self._env(self.manager_b, self.company_b)['cpla.leakage.case'].browse(case.id).read(['reference'])
        foreign = self._finding('1000', company=self.company_b, partner=self.partner_b)
        with self.assertRaises(UserError):
            self.env(user=self.both, context={
                'allowed_company_ids': [self.company_a.id, self.company_b.id],
            })['cpla.leakage.case'].create_from_findings(
                [finding.id, foreign.id], grouping_basis='explicit_same_issue', grouping_note='No.',
            )
        for user in (self.investigator, self.salesman, self.recovery, self.plain, self.auditor, self.admin):
            with self.assertRaises(AccessError):
                self._open(self._finding('100'), user=user)
        with self.assertRaises(AccessError):
            self._as(self.investigator, case).action_assign(self.manager.id, 'Not a manager.')
        other = self._open(self._finding('2000'))
        with self.assertRaises(AccessError):
            self._as(self.investigator, case).action_merge(other.id, 'Unauthorized merge.')
        with self.assertRaises(AccessError):
            self._as(self.auditor, case).write({'title': 'Changed'})
        self.assertFalse(any(name.startswith('action_validate') for name in case._fields))
        self.assertNotIn('finance_validated_exact', case._fields)
        with self.assertRaises(AccessError):
            self._as(self.admin, case).read(['current_potential_exposure_exact'])
        with self.assertRaises(UserError):
            self._as(self.manager, case).write({'state': 'closed_with_reason', 'closure_reason': 'source_error'})
        with self.assertRaises(UserError):
            self._as(self.investigator, case).export_data(['reference'])
        self.assertFalse(self._env(self.manager_b, self.company_b)['cpla.leakage.case'].search_count([
            ('id', '=', case.id),
        ]))
        event = case.event_ids[:1]
        before = event.reason
        with self.assertRaises(UserError):
            event.write({'reason': 'rewritten'})
        self.assertEqual(event.reason, before)
        membership = self._env(self.investigator, case.company_id)[
            'cpla.leakage.case.membership'
        ].browse(case.membership_ids.filtered('is_current')[:1].id)
        with self.assertRaises(UserError):
            membership.write({'is_current': False})
        self.assertTrue(membership.is_current)
        with self.assertRaises(UserError):
            self._env(self.investigator, case.company_id)['cpla.leakage.case.membership'].create({
                'case_id': case.id,
                'finding_id': membership.finding_id.id,
                'company_id': case.company_id.id,
                'is_current': True,
            })
        source = Path(Manifest.for_addon(MODULE).path, 'models', 'leakage_case.py').read_text(encoding='utf-8')
        self.assertNotIn('sudo(', source)
        self.assertNotIn('.execute(', source)

    def test_con13_duplicate_index_rollback_and_idempotent_sync(self):
        """CON13-T001 through T008. Two database workers were not started."""
        _logger.info('CON13 two-worker concurrency was NOT_EXECUTED. This test uses one transaction.')
        finding = self._finding('25000')
        case = self._open(finding)
        membership_model = type(self.env['cpla.leakage.case.membership'])
        case_model = type(self.env['cpla.leakage.case'])
        original = membership_model.search

        def hide_in_search(this, domain, offset=0, limit=None, order=None):
            if any(
                isinstance(item, (list, tuple)) and len(item) >= 2 and item[0] == 'finding_id' and item[1] == 'in'
                for item in domain
            ):
                return this.browse()
            return original(this, domain, offset=offset, limit=limit, order=order)

        with patch.object(membership_model, 'search', hide_in_search), patch.object(
            case_model, '_create_case', side_effect=IntegrityError('duplicate membership'),
        ):
            raced = self._open(finding)
        self.assertEqual(raced, case)
        second_case = self._open(self._finding('1000'))
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                models.Model.create(self.env['cpla.leakage.case.membership'], [{
                    'case_id': second_case.id,
                    'finding_id': finding.id,
                    'company_id': finding.company_id.id,
                    'is_current': True,
                    'reviewed_status': finding.finding_status,
                    'linked_at': fields.Datetime.now(),
                }])
        self.assertEqual(len(self.env['cpla.leakage.case.membership'].search([
            ('finding_id', '=', finding.id), ('is_current', '=', True),
        ])), 1)
        fresh = self._finding('3000')
        with patch.object(case_model, '_seed_checklist', side_effect=UserError('stop')):
            with self.assertRaises(UserError):
                self._open(fresh)
        self.assertFalse(self.env['cpla.leakage.case.membership'].search([
            ('finding_id', '=', fresh.id),
        ]))
        self.assertFalse(fresh.current_case_id)
        self.assertEqual(self._open(finding), case)
        identity = fresh.current_identity
        fresh.write({
            'is_current': False,
            'current_identity': False,
            'finding_status': 'superseded_by_reassessment',
        })
        successor = self._finding('2500', line=fresh.move_line_id, identity=identity)
        self.assertEqual(len(self._open(successor)), 1)
        self.assertNotEqual(self._open(successor), case)
        owner_case = self._assign(self._open(self._finding('800')))
        self._as(self.manager, owner_case).action_assign(self.manager.id, 'Second assignment.')
        self.assertGreaterEqual(len(owner_case.event_ids.filtered(
            lambda item: item.event_type in ('assigned', 'owner_changed')
        )), 2)
        merge_left = self._open(self._finding('1500'))
        merge_right = self._open(self._finding('500'))
        with patch.object(case_model, '_link', side_effect=IntegrityError('merge race')):
            with self.assertRaises(UserError):
                merge_left.action_merge(merge_right.id, 'Concurrent merge.')
        self.assertEqual(merge_right.state, 'new')
        self.assertTrue(merge_right.membership_ids.filtered('is_current'))
        self.assertEqual(merge_left.current_potential_exposure_exact, '1500')
        closing = self._open(self._finding('700'))
        self._as(self.manager, closing).action_close('withdrawn_after_review', 'Withdrawn.')
        with self.assertRaises(UserError):
            self._as(self.manager, closing).action_close('source_error', 'Already closed.')
        self._as(self.manager, closing).action_reopen('The withdrawal was recorded too early.')
        self.assertEqual(closing.state, 'under_investigation')
        self.assertEqual(len(closing.membership_ids.filtered('is_current')), 1)

    def test_reg13_views_upgrade_shape_and_no_accounting_side_effects(self):
        """REG13-T001 through T014 for the objects this database can show."""
        manifest = Manifest.for_addon(MODULE)
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        self.assertEqual(module.state, 'installed')
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])
        self.assertNotIn('mail', manifest['depends'])
        self.assertNotIn('account', manifest['depends'])
        form = self.env['cpla.leakage.case'].get_view(view_type='form')
        listing = self.env['cpla.leakage.case'].get_view(view_type='list')
        kanban = self.env['cpla.leakage.case'].get_view(view_type='kanban')
        self.assertIn('not a finance-validated amount', form['arch'])
        self.assertIn('current_potential_exposure_exact', listing['arch'])
        self.assertIn('reference', kanban['arch'])
        self.assertIn('chatter', form['arch'])
        for xmlid in (
            'menu_cpla_investigation',
            'menu_cpla_leakage_cases',
            'menu_cpla_my_cases',
            'menu_cpla_unassigned_cases',
            'menu_cpla_evidence_pending',
            'menu_cpla_ready_finance',
            'menu_cpla_exception_queue',
            'menu_cpla_case_history',
            'seq_cpla_leakage_case',
        ):
            self.assertTrue(self.env.ref('%s.%s' % (MODULE, xmlid)))
        auditor = self.env.ref('%s.group_internal_auditor' % MODULE)
        admin = self.env.ref('%s.group_app_admin' % MODULE)
        self.assertIn(self.env.ref('%s.menu_cpla_investigation' % MODULE), auditor.menu_access)
        self.assertNotIn(self.env.ref('%s.menu_cpla_audits' % MODULE), auditor.menu_access)
        self.assertNotIn(self.env.ref('%s.menu_cpla_investigation' % MODULE), admin.menu_access)
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', 'in', ['ir.cron', 'ir.actions.server', 'ir.actions.report']),
        ]))
        rules = self.env['ir.rule'].search([('model_id.model', '=', 'cpla.leakage.case')])
        self.assertTrue(rules)
        self.assertFalse(rules.groups)
        self.assertIn('company_id', rules.domain_force)
        finding = self._finding('25000')
        with self.assertRaises(UserError):
            self.env['cpla.leakage.finding'].create({
                'reference': 'FORGED',
                'company_id': self.company_a.id,
                'move_line_id': finding.move_line_id.id,
                'finding_status': 'potential',
                'potential_leakage_exact': '1',
            })
        price = finding.move_line_id.price_unit
        payments = self._payments()
        moves = self.env['account.move'].search_count([])
        self._open(finding)
        self.assertEqual(finding.move_line_id.price_unit, price)
        self.assertEqual(self._payments(), payments)
        self.assertEqual(self.env['account.move'].search_count([]), moves)
        self.assertTrue(self.env['cpla.invoice.audit.run']._name)
        self.assertTrue(self.env['cpla.invoice.audit.result']._name)
        self.assertEqual(self.env['cpla.leakage.finding']._name, 'cpla.leakage.finding')

    def test_case_ref_015_and_activity_do_not_schedule_a_cron(self):
        started = time.perf_counter()
        opened = self.env['cpla.leakage.case']
        for _index in range(20):
            opened |= self._open(self._finding('100'))
        elapsed = time.perf_counter() - started
        _logger.info('DEV13 sequential case open count=20 elapsed_seconds=%.3f', elapsed)
        self.assertEqual(len(opened), 20)
        self.assertGreater(elapsed, 0)
        self.assertFalse(self.env['ir.cron'].search([
            ('model_id.model', '=', 'cpla.leakage.case'),
        ]))
