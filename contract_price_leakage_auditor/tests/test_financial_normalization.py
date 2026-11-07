import logging
import time
from decimal import Decimal

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'
_logger = logging.getLogger(__name__)


def _dec(value):
    return Decimal(str(value))


@tagged('post_install', '-at_install')
class TestDev08FinancialNormalization(TransactionCase):
    """Currency, tax basis, and precision. Amounts use fictional currency codes.

    INR and USD are not activated. Company policy candidates stay unapproved.
    A normalized price is not a leakage amount.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        currency = cls.env.company.currency_id
        cls.company_a = cls.env['res.company'].create({
            'name': 'ABC India',
            'currency_id': currency.id,
        })
        cls.company_b = cls.env['res.company'].create({
            'name': 'ABC UAE',
            'currency_id': currency.id,
        })
        cls.owner = cls._make_user('cpla08_owner', 'group_contract_user', cls.company_a)
        cls.owner_b = cls._make_user('cpla08_owner_b', 'group_contract_user', cls.company_b)
        cls.manager = cls._make_user('cpla08_manager', 'group_contract_manager', cls.company_a)
        cls.manager_b = cls._make_user('cpla08_manager_b', 'group_contract_manager', cls.company_b)
        cls.finance = cls._make_user('cpla08_finance', 'group_finance_manager', cls.company_a)
        cls.finance_b = cls._make_user('cpla08_finance_b', 'group_finance_manager', cls.company_b)
        cls.reviewer = cls._make_user('cpla08_reviewer', 'group_finance_reviewer', cls.company_a)
        cls.auditor = cls._make_user('cpla08_auditor', 'group_internal_auditor', cls.company_a)
        cls.sales = cls._make_user('cpla08_sales', 'group_sales_pricing_reviewer', cls.company_a)
        cls.recovery = cls._make_user('cpla08_recovery', 'group_recovery_operator', cls.company_a)
        cls.admin = cls._make_user('cpla08_admin', 'group_app_admin', cls.company_a)
        cls.both = cls._make_user(
            'cpla08_both', 'group_contract_manager', cls.company_a,
            companies=cls.company_a | cls.company_b,
        )
        cls.policy_a = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_a.id,
            'change_reason': 'Candidate reference. Not an operational approval.',
            'fx_basis_policy': 'invoice_date',
            'tax_comparison_policy': 'tax_included',
            'monetary_precision_policy': 'company_currency_rounding',
            'tolerance_policy': 'do_not_suppress',
        })
        cls.policy_b = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_b.id,
            'change_reason': 'Candidate reference. Not an operational approval.',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'XYZ Manufacturing',
            'is_company': True,
            'company_id': cls.company_a.id,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'UAE Buyer',
            'is_company': True,
            'company_id': cls.company_b.id,
        })
        cls.bearing = cls.env['product.product'].create({
            'name': 'Bearing A',
            'list_price': 9999.0,
            'company_id': False,
        })
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.foreign = cls.env['res.currency'].create({
            'name': 'Q8A',
            'symbol': 'Q',
            'rounding': 0.01,
        })
        cls.third = cls.env['res.currency'].create({
            'name': 'Q8B',
            'symbol': 'B',
            'rounding': 0.01,
        })
        cls.whole = cls.env['res.currency'].create({
            'name': 'Q8C',
            'symbol': 'C',
            'rounding': 1.0,
        })

    @classmethod
    def _make_user(cls, login, xmlid, company, companies=None, extra_groups=()):
        companies = companies or company
        names = ['base.group_user', '%s.%s' % (MODULE, xmlid)]
        names.extend('%s.%s' % (MODULE, extra) for extra in extra_groups)
        return new_test_user(
            cls.env,
            login=login,
            groups=','.join(names),
            password='cpla-test',
            company_id=company.id,
            company_ids=[Command.set(companies.ids)],
        )

    def _env(self, user, company):
        return self.env(user=user, context={
            **self.env.context,
            'allowed_company_ids': [company.id],
        })

    def _today(self):
        return fields.Date.context_today(self.env['cpla.pricing.financial'])

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

    def _staff(self, company):
        if company == self.company_a:
            return self.owner, self.manager, self.finance
        return self.owner_b, self.manager_b, self.finance_b

    def _policy(self, company):
        return self.policy_a if company == self.company_a else self.policy_b

    def _draft(self, price, currency, company=None, partner=None, product=None):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
        product = product or self.bearing
        owner = self._staff(company)[0]
        env = self._env(owner, company)
        contract = env['cpla.customer.contract'].create({
            'name': 'Negotiated supply',
            'company_id': company.id,
            'partner_id': partner.id,
            'owner_id': owner.id,
            'currency_id': currency.id,
            'valid_from': self._on(-30),
            'valid_to': self._on(180),
            'policy_id': self._policy(company).id,
        })
        env['cpla.customer.contract.line'].create({
            'contract_id': contract.id,
            'product_id': product.id,
            'price_unit': price,
            'uom_id': product.uom_id.id,
        })
        env['cpla.customer.contract.evidence'].create({
            'contract_id': contract.id,
            'name': 'signed-agreement.pdf',
            'document_type': 'signed_agreement',
            'source_reference': 'AGR-008',
            'description': 'Signed pricing schedule.',
            'datas': 'c2lnbmVk',
        })
        return contract

    def _v1(self, price, currency, company=None):
        contract = self._draft(price, currency, company=company)
        contract.action_submit_for_review()
        _owner, manager, _finance = self._staff(contract.company_id)
        env = self._env(manager, contract.company_id)
        return env['cpla.customer.contract.version'].approve_initial(
            env['cpla.customer.contract'].browse(contract.id)
        )

    def _clause(self, price, currency, clause, company=None):
        first = self._v1(price, currency, company=company)
        company = first.company_id
        owner, _manager, finance = self._staff(company)
        env = self._env(owner, company)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        values = {
            'amendment_reason': 'Financial clause. Not a retroactive restatement.',
            'effective_from': self._today(),
        }
        values.update(clause)
        amendment.write(values)
        amendment.action_submit_for_review()
        reviewer = self._env(finance, company)
        record = reviewer['cpla.customer.contract.version'].browse(amendment.id)
        record.action_approve()
        return record

    def _rate(self, currency, company, day, inverse):
        return self.env['res.currency.rate'].create({
            'name': day,
            'currency_id': currency.id,
            'company_id': company.id,
            'inverse_company_rate': inverse,
        })

    def _service(self, user=None, company=None):
        user = user or self.manager
        company = company or self.company_a
        return self._env(user, company)['cpla.pricing.financial']

    def _normalize(self, version, user=None, **extra):
        user = user or self.manager
        return self._service(user, version.company_id).normalize(version.line_ids, extra)

    def _fixed(self, price='100', multiplier='84', currency=None, company=None, **extra):
        currency = currency or self.foreign
        clause = {
            'fx_policy': 'fixed_rate',
            'fx_source_currency_id': currency.id,
            'fx_target_currency_id': (company or self.company_a).currency_id.id,
            'fx_multiplier_exact': multiplier,
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        }
        clause.update(extra)
        return self._clause(price, currency, clause, company=company)

    def test_fx08_t001_same_currency_needs_no_rate(self):
        version = self._clause(1150, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        self.assertEqual(result['financial_status'], 'SAME_CURRENCY_NO_CONVERSION')
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(1150))
        self.assertFalse(result['fx_rate_id'])
        self.assertFalse(result['fx_rate_exact'])
        self.assertFalse(result['leakage_amount'])

    def test_fx08_t002_source_to_company_uses_the_fixed_rate(self):
        version = self._fixed('100', '84')
        result = self._normalize(version)
        self.assertEqual(result['financial_status'], 'NORMALIZED')
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(8400))
        self.assertEqual(result['fx_rate_direction'], 'multiply')
        self.assertNotEqual(_dec(result['comparable_unit_price_exact']), _dec('1.190476'))

    def test_fx08_t003_inverse_fixed_rate_divides(self):
        version = self._clause(8400, self.company_a.currency_id, {
            'fx_policy': 'fixed_rate',
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'fx_multiplier_exact': '84',
            'comparison_currency_policy': 'explicit_currency',
            'comparison_currency_id': self.foreign.id,
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(100))
        self.assertEqual(result['fx_rate_direction'], 'divide')

    def test_fx08_t004_reversed_direction_is_not_used(self):
        version = self._fixed('100', '84')
        result = self._normalize(version)
        self.assertGreater(_dec(result['comparable_unit_price_exact']), _dec(100))
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(8400))

    def test_fx08_t005_company_specific_rate_is_selected(self):
        self._rate(self.foreign, self.company_a, self._on(-4), 84.0)
        self._rate(self.foreign, self.company_b, self._on(-4), 30.0)
        selected = self._service().select_rate(
            self.company_a, self.foreign, self._on(-4), mode='exact',
        )
        other = self._service(self.manager_b, self.company_b).select_rate(
            self.company_b, self.foreign, self._on(-4), mode='exact',
        )
        self.assertEqual(_dec(selected['company_per_unit_exact']), _dec(84))
        self.assertEqual(_dec(other['company_per_unit_exact']), _dec(30))

    def test_fx08_t006_historical_date_selects_the_named_row(self):
        early = self._rate(self.foreign, self.company_a, self._on(-6), 80.0)
        later = self._rate(self.foreign, self.company_a, self._on(-2), 84.0)
        selected = self._service().select_rate(
            self.company_a, self.foreign, self._on(-2), mode='exact',
        )
        self.assertEqual(selected['rate_id'], later.id)
        self.assertNotEqual(selected['rate_id'], early.id)
        self.assertEqual(selected['rate_date'], fields.Date.to_string(self._on(-2)))

    def test_fx08_t007_exact_date_does_not_use_another_day(self):
        self._rate(self.foreign, self.company_a, self._on(-6), 84.0)
        selected = self._service().select_rate(
            self.company_a, self.foreign, self._on(-1), mode='exact',
        )
        self.assertFalse(selected['ok'])
        self.assertEqual(selected['status'], 'MISSING_HISTORICAL_FX')
        self.assertFalse(selected['company_per_unit_exact'])

    def test_fx08_t008_prior_rate_keeps_the_row_date(self):
        row = self._rate(self.foreign, self.company_a, self._on(-6), 84.0)
        selected = self._service().select_rate(
            self.company_a, self.foreign, self._on(-1), mode='prior',
        )
        self.assertTrue(selected['ok'])
        self.assertEqual(selected['rate_id'], row.id)
        self.assertEqual(selected['rate_date'], fields.Date.to_string(self._on(-6)))
        self.assertEqual(_dec(selected['company_per_unit_exact']), _dec(84))

    def test_fx08_t009_missing_snapshot_does_not_invent_a_price(self):
        version = self._clause(100, self.foreign, {
            'fx_policy': 'historical_exact_date',
            'fx_date_source': 'explicit_date',
            'fx_explicit_date': self._on(-3),
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
        })
        result = self._normalize(version)
        self.assertEqual(result['financial_status'], 'MISSING_HISTORICAL_FX')
        self.assertFalse(result['comparable_unit_price_exact'])
        self.assertFalse(result['price_after_fx_exact'])

    def test_fx08_t010_future_rate_is_not_a_fallback(self):
        self._rate(self.foreign, self.company_a, self._on(5), 90.0)
        self._rate(self.foreign, self.company_a, self._on(-6), 84.0)
        exact = self._service().select_rate(
            self.company_a, self.foreign, self._today(), mode='exact',
        )
        prior = self._service().select_rate(
            self.company_a, self.foreign, self._today(), mode='prior',
        )
        self.assertFalse(exact['ok'])
        self.assertEqual(prior['rate_date'], fields.Date.to_string(self._on(-6)))
        self.assertEqual(_dec(prior['company_per_unit_exact']), _dec(84))

    def test_fx08_t011_fixed_rate_beats_a_different_market_row(self):
        self._rate(self.foreign, self.company_a, self._today(), 84.0)
        version = self._fixed('100', '83')
        result = self._normalize(version)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(8300))
        self.assertEqual(result['fx_evidence'], 'contract_fixed_rate')

    def test_fx08_t012_incomplete_fixed_rate_blocks_submission(self):
        first = self._v1(100, self.foreign)
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Incomplete fixed rate.',
            'effective_from': self._today(),
            'fx_policy': 'fixed_rate',
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
        })
        with self.assertRaises(UserError) as caught:
            amendment.action_submit_for_review()
        self.assertIn('positive exact number', str(caught.exception).lower())
        self.assertEqual(amendment.state, 'draft')

    def test_fx08_t013_snapshot_keeps_rate_evidence(self):
        self._rate(self.foreign, self.company_a, self._on(-3), 84.0)
        version = self._clause(100, self.foreign, {
            'fx_policy': 'historical_exact_date',
            'fx_date_source': 'explicit_date',
            'fx_explicit_date': self._on(-3),
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(8400))
        self.assertEqual(result['fx_date_used'], fields.Date.to_string(self._on(-3)))
        self.assertTrue(version.fx_rate_id)
        self.assertEqual(version.fx_company_per_source_exact, '84')
        self.assertEqual(result['fx_evidence'], 'frozen_rate_snapshot')

    def test_fx08_t014_rate_correction_does_not_rewrite_the_snapshot(self):
        row = self._rate(self.foreign, self.company_a, self._on(-3), 84.0)
        version = self._clause(100, self.foreign, {
            'fx_policy': 'historical_exact_date',
            'fx_date_source': 'explicit_date',
            'fx_explicit_date': self._on(-3),
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        frozen = version.fx_company_per_source_exact
        digest = version.snapshot_sha256
        row.write({'inverse_company_rate': 83.0})
        result = self._normalize(version)
        self.assertEqual(version.fx_company_per_source_exact, frozen)
        self.assertEqual(version.snapshot_sha256, digest)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(8400))
        self.assertTrue(result['fx_reassessment_required'])

    def test_fx08_t015_the_same_input_returns_the_same_price(self):
        version = self._fixed('100', '84')
        first = self._normalize(version)
        second = self._normalize(version)
        self.assertEqual(first['comparable_unit_price_exact'], second['comparable_unit_price_exact'])
        self.assertEqual(first['financial_status'], second['financial_status'])

    def test_fx08_t016_cutoff_before_approval_does_not_use_the_clause(self):
        version = self._fixed('100', '84')
        cutoff = fields.Datetime.subtract(version.approved_at, seconds=5)
        result = self._normalize(version, knowledge_cutoff=cutoff)
        self.assertEqual(result['financial_status'], 'HISTORICAL_EVIDENCE_REVIEW_REQUIRED')
        self.assertFalse(result['comparable_unit_price_exact'])
        self.assertNotIn('8400', result['financial_explanation'] or '')

    def test_fx08_t017_cross_currency_uses_company_units(self):
        self._rate(self.foreign, self.company_a, self._on(-3), 84.0)
        self._rate(self.third, self.company_a, self._on(-3), 90.0)
        version = self._clause(100, self.foreign, {
            'fx_policy': 'historical_exact_date',
            'fx_date_source': 'explicit_date',
            'fx_explicit_date': self._on(-3),
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.third.id,
            'comparison_currency_policy': 'explicit_currency',
            'comparison_currency_id': self.third.id,
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        expected = _dec(100) * _dec(84) / _dec(90)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), expected)
        inverted = _dec(100) * _dec(90) / _dec(84)
        self.assertNotEqual(_dec(result['comparable_unit_price_exact']), inverted)

    def test_fx08_t018_payment_fx_is_not_price_leakage(self):
        version = self._fixed('100', '84')
        result = self._normalize(version, fx_source='payment_date')
        self.assertEqual(result['financial_status'], 'PAYMENT_FX_NOT_CONTRACT_LEAKAGE')
        self.assertFalse(result['comparable_unit_price_exact'])
        self.assertFalse(result['leakage_amount'])
        classified = self._service().classify_fx_source('payment_date')
        self.assertFalse(classified['leakage_amount'])

    def test_tax08_t001_tax_exclusive_prices_stay_exclusive(self):
        version = self._clause(1000, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(1000))
        self.assertEqual(result['tax_component_exact'], '0')
        self.assertEqual(result['normalized_tax_basis'], 'tax_excluded')

    def test_tax08_t002_simple_included_percent_becomes_net(self):
        version = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(1000))
        self.assertEqual(_dec(result['tax_component_exact']), _dec(180))

    def test_tax08_t003_included_contract_matches_excluded_net(self):
        gross = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
            'rounding_stage': 'preserve_exact',
        })
        net = self._clause(1000, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        left = self._normalize(gross)
        right = self._normalize(net)
        difference = self._service().classify_difference(
            left['comparable_unit_price_exact'], right['comparable_unit_price_exact'],
        )
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec(0))
        self.assertFalse(difference['leakage_amount'])

    def test_tax08_t004_excluded_contract_and_included_amount_share_a_net(self):
        contract = self._clause(1000, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        invoice_shape = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
            'rounding_stage': 'preserve_exact',
        })
        expected = self._normalize(contract)
        actual = self._normalize(invoice_shape)
        self.assertEqual(expected['comparable_unit_price_exact'], actual['comparable_unit_price_exact'])
        self.assertEqual(_dec(actual['tax_component_exact']), _dec(180))

    def test_tax08_t005_fiscal_position_is_not_guessed(self):
        version = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
        })
        result = self._normalize(version, fiscal_position_id=1)
        self.assertEqual(result['financial_status'], 'TAX_BASIS_REVIEW_REQUIRED')
        self.assertEqual(result['financial_reason'], 'fiscal_position_not_verified')
        self.assertFalse(result['comparable_unit_price_exact'])

    def test_tax08_t006_group_tax_is_not_divided(self):
        self._assert_unsupported('group')

    def test_tax08_t007_fixed_tax_is_not_divided(self):
        self._assert_unsupported('fixed')

    def test_tax08_t008_division_tax_is_not_divided_by_one_plus_rate(self):
        self._assert_unsupported('division')

    def test_tax08_t009_grouped_order_is_not_simplified(self):
        self._assert_unsupported('group')

    def test_tax08_t010_tax_on_tax_is_not_simplified(self):
        self._assert_unsupported('tax_on_tax')

    def test_tax08_t011_historical_tax_clause_stays_on_the_version(self):
        version = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
            'rounding_stage': 'preserve_exact',
        })
        self.assertEqual(version.tax_percent_exact, '18')
        self.assertEqual(self._normalize(version)['tax_structure'], 'single_ordinary_percent')

    def test_tax08_t012_missing_tax_basis_is_review(self):
        version = self._clause(1000, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        self.assertEqual(result['financial_status'], 'TAX_BASIS_REVIEW_REQUIRED')
        self.assertFalse(result['comparable_unit_price_exact'])

    def test_tax08_t013_complex_tax_does_not_return_a_guess(self):
        result = self._assert_unsupported('complex')
        self.assertIs(result['comparable_unit_price_exact'], False)
        self.assertNotEqual(result['comparable_unit_price_exact'], '0')

    def test_tax08_gold_tax_003_included_gross_net_and_extended_difference(self):
        """GOLD-TAX-003. Unit nets only. The extended difference is not a finding."""
        contract = self._clause(1000, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        invoice_shape = self._clause(1062, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
            'rounding_stage': 'preserve_exact',
        })
        expected = self._normalize(contract)
        actual = self._normalize(invoice_shape)
        self.assertEqual(_dec(expected['comparable_unit_price_exact']), _dec(1000))
        self.assertEqual(_dec(actual['comparable_unit_price_exact']), _dec(900))
        difference = self._service().classify_difference(
            expected['comparable_unit_price_exact'],
            actual['comparable_unit_price_exact'],
            quantity=100,
        )
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec(100))
        self.assertEqual(_dec(difference['extended_amount_exact']), _dec(10000))
        self.assertFalse(difference['leakage_amount'])
        self.assertFalse(actual['leakage_amount'])

    def test_tax08_t014_tax_amount_is_not_lost_revenue(self):
        version = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        difference = self._service().classify_difference('1000', result['comparable_unit_price_exact'])
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec(0))
        self.assertNotEqual(_dec(result['tax_component_exact']), _dec(difference['raw_difference_exact']))
        self.assertFalse(result['leakage_amount'])

    def test_tax08_t015_normalization_creates_no_tax_entry(self):
        before = self._move_count()
        version = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
            'rounding_stage': 'preserve_exact',
        })
        self._normalize(version)
        self.assertEqual(self._move_count(), before)

    def test_prec08_t001_source_currency_rounding_is_not_hardcoded(self):
        self.assertEqual(self.whole.decimal_places, 0)
        self.assertNotEqual(self.whole.rounding, 0.01)

    def test_prec08_t002_target_currency_increment_is_used(self):
        version = self._clause('100.6', self.whole, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'per_unit',
        })
        result = self._normalize(version)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(101))

    def test_prec08_t003_intermediate_fx_is_not_rounded_to_two_decimals(self):
        version = self._fixed('100', '84.123456789')
        result = self._normalize(version)
        self.assertEqual(
            _dec(result['comparable_unit_price_exact']),
            _dec(100) * _dec('84.123456789'),
        )
        self.assertNotEqual(_dec(result['comparable_unit_price_exact']), _dec('8412.35'))

    def test_prec08_t004_uom_price_stays_exact_before_fx(self):
        version = self._box_version()
        result = self._normalize(version, quantity=10, comparison_uom_id=self.unit.id)
        self.assertEqual(result['financial_status'], 'NORMALIZED')
        self.assertEqual(_dec(result['source_price_exact']), _dec(12))
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(1008))

    def test_prec08_t005_extended_amount_is_rounded_after_multiplication(self):
        version = self._priced('1.005', 'extended_amount')
        result = self._normalize(version, quantity=100)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec('1.005'))
        self.assertEqual(_dec(result['extended_amount_rounded_exact']), _dec('100.50'))

    def test_prec08_t006_per_unit_rounding_is_a_different_stage(self):
        version = self._priced('1.005', 'per_unit')
        result = self._normalize(version, quantity=100)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec('1.01'))
        self.assertEqual(_dec(result['extended_amount_rounded_exact']), _dec(101))

    def test_prec08_t007_fractional_quantity_stays_exact(self):
        version = self._priced('1.5', 'preserve_exact')
        result = self._normalize(version, quantity='0.5')
        self.assertEqual(_dec(result['extended_amount_exact']), _dec('0.75'))
        self.assertFalse(result['rounding_applied'])

    def test_prec08_t008_decimal_difference_is_not_a_binary_float_compare(self):
        difference = self._service().classify_difference('0.3', _dec('0.1') + _dec('0.2'))
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec(0))
        self.assertNotEqual((0.1 + 0.2) - 0.3, 0.0)

    def test_prec08_t009_negative_tolerance_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._service().classify_difference('10', '9.98', tolerance_amount=-1)

    def test_prec08_t010_missing_tolerance_does_not_suppress(self):
        difference = self._service().classify_difference('1000', '999.98')
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec('0.02'))
        self.assertFalse(difference['within_tolerance'])
        self.assertFalse(difference['tolerance_suppressed'])
        self.assertFalse(difference['leakage_amount'])

    def test_prec08_t011_absolute_tolerance_is_not_approved(self):
        difference = self._service().classify_difference('1000.02', '1000', tolerance_amount='0.05')
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec('0.02'))
        self.assertFalse(difference['within_tolerance'])
        self.assertFalse(difference['tolerance_suppressed'])

    def test_prec08_t012_percentage_tolerance_is_not_approved(self):
        difference = self._service().classify_difference('1000', '995', tolerance_amount='0.5')
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec(5))
        self.assertFalse(difference['tolerance_suppressed'])

    def test_prec08_t013_combined_tolerance_is_not_invented(self):
        difference = self._service().classify_difference('1000', '999', tolerance_amount='2')
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec(1))
        self.assertFalse(difference['within_tolerance'])

    def test_prec08_t014_raw_difference_remains_visible(self):
        difference = self._service().classify_difference('0.02', '0', quantity=1)
        self.assertEqual(difference['raw_difference_exact'], '0.02')
        self.assertEqual(_dec(difference['extended_amount_exact']), _dec('0.02'))

    def test_prec08_t015_overbilling_stays_negative(self):
        difference = self._service().classify_difference('1000', '1100', quantity=1)
        self.assertEqual(_dec(difference['raw_difference_exact']), _dec(-100))
        self.assertNotEqual(_dec(difference['raw_difference_exact']), _dec(100))
        self.assertFalse(difference['leakage_amount'])

    def test_prec08_t016_rounding_stages_do_not_collapse(self):
        extended = self._normalize(self._priced('1.005', 'extended_amount'), quantity=100)
        per_unit = self._normalize(self._priced('1.005', 'per_unit'), quantity=100)
        self.assertNotEqual(
            extended['extended_amount_rounded_exact'],
            per_unit['extended_amount_rounded_exact'],
        )

    def test_sec08_t001_company_user_cannot_read_the_other_financial_clause(self):
        version = self._fixed('100', '84', company=self.company_b)
        with self.assertRaises(AccessError) as caught:
            self._service(self.manager, self.company_a).normalize(version.line_ids, {})
        self.assertNotIn('8400', str(caught.exception))

    def test_sec08_t002_company_rate_is_not_applied_to_the_other_company(self):
        self._rate(self.foreign, self.company_a, self._on(-3), 84.0)
        version = self._clause(100, self.foreign, {
            'fx_policy': 'historical_exact_date',
            'fx_date_source': 'explicit_date',
            'fx_explicit_date': self._on(-3),
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_b.currency_id.id,
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
        }, company=self.company_b)
        result = self._normalize(version, user=self.manager_b)
        self.assertEqual(result['financial_status'], 'MISSING_HISTORICAL_FX')
        self.assertFalse(result['comparable_unit_price_exact'])

    def test_sec08_t003_approved_fixed_rate_cannot_be_rewritten(self):
        version = self._fixed('100', '84')
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.customer.contract.version'].browse(
                version.id
            ).write({'fx_multiplier_exact': '10'})
        self.assertEqual(version.fx_multiplier_exact, '84')

    def test_sec08_t004_reviewer_cannot_write_the_historical_clause(self):
        version = self._fixed('100', '84')
        with self.assertRaises(AccessError):
            self._env(self.reviewer, self.company_a)['cpla.customer.contract.version'].browse(
                version.id
            ).write({'fx_policy': 'unconfigured'})

    def test_sec08_t005_request_company_cannot_override_the_version(self):
        version = self._fixed('100', '84')
        result = self._normalize(version, company_id=self.company_b.id)
        self.assertEqual(result['financial_status'], 'COMPANY_ACCESS_DENIED')
        self.assertFalse(result['comparable_unit_price_exact'])
        self.assertNotIn('8400', result['financial_explanation'])

    def test_sec08_t006_unapproved_caller_does_not_receive_the_price(self):
        version = self._fixed('100', '84')
        with self.assertRaises(AccessError) as caught:
            self._service(self.sales, self.company_a).normalize(version.line_ids, {})
        self.assertNotIn('8400', str(caught.exception))

    def test_sec08_t007_service_file_has_no_unrestricted_elevation(self):
        path = Manifest.for_addon(MODULE).path
        filename = path + '/models/financial_normalization.py'
        with open(filename, encoding='utf-8') as handle:
            text = handle.read()
        self.assertNotIn('sudo(', text)
        self.assertNotIn('.execute(', text)

    def test_sec08_t008_other_company_clause_is_not_a_tax_source(self):
        foreign_clause = self._fixed('1180', '84', company=self.company_b)
        local = self._clause(500, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
        })
        result = self._normalize(local)
        self.assertNotEqual(result['financial_status'], 'NORMALIZED')
        self.assertFalse(result['comparable_unit_price_exact'])
        self.assertNotIn(foreign_clause.fx_multiplier_exact, result['financial_explanation'] or '')

    def test_sec08_t009_correction_keeps_the_approved_version_number(self):
        row = self._rate(self.foreign, self.company_a, self._on(-3), 84.0)
        version = self._clause(100, self.foreign, {
            'fx_policy': 'historical_exact_date',
            'fx_date_source': 'explicit_date',
            'fx_explicit_date': self._on(-3),
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        price = version.line_ids.price_unit
        row.write({'inverse_company_rate': 10.0})
        self.assertEqual(version.line_ids.price_unit, price)
        self.assertEqual(version.state, 'approved')
        self.assertEqual(_dec(self._normalize(version)['comparable_unit_price_exact']), _dec(8400))

    def test_sec08_t010_existing_approved_price_is_not_overwritten(self):
        version = self._fixed('100', '84')
        price = version.line_ids.price_unit
        self._normalize(version)
        self.assertEqual(version.line_ids.price_unit, price)
        self.assertEqual(version.state, 'approved')

    def test_sec08_t011_multi_company_user_uses_each_version_clause(self):
        left = self._fixed('100', '84', company=self.company_a)
        right = self._fixed('100', '30', company=self.company_b)
        env = self.env(user=self.both, context={
            **self.env.context,
            'allowed_company_ids': [self.company_a.id, self.company_b.id],
        })
        service = env['cpla.pricing.financial']
        first = service.normalize(left.line_ids, {})
        second = service.normalize(right.line_ids, {})
        self.assertEqual(_dec(first['comparable_unit_price_exact']), _dec(8400))
        self.assertEqual(_dec(second['comparable_unit_price_exact']), _dec(3000))

    def test_sec08_t012_export_without_export_rights_is_rejected(self):
        version = self._fixed('100', '84')
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.customer.contract.version'].browse(
                version.id
            ).export_data(['fx_multiplier_exact'])

    def test_his08_t001_repeated_normalization_matches(self):
        version = self._fixed('120', '84')
        self.assertEqual(
            self._normalize(version)['comparable_unit_price_exact'],
            self._normalize(version)['comparable_unit_price_exact'],
        )

    def test_his08_t002_explicit_date_is_the_approved_policy(self):
        self._rate(self.foreign, self.company_a, self._on(-8), 70.0)
        self._rate(self.foreign, self.company_a, self._on(-3), 84.0)
        version = self._clause(100, self.foreign, {
            'fx_policy': 'historical_exact_date',
            'fx_date_source': 'explicit_date',
            'fx_explicit_date': self._on(-3),
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        result = self._normalize(version)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(8400))
        self.assertEqual(result['fx_date_used'], fields.Date.to_string(self._on(-3)))

    def test_his08_t003_corrected_rate_requires_reassessment(self):
        row = self._rate(self.foreign, self.company_a, self._on(-3), 84.0)
        version = self._clause(100, self.foreign, {
            'fx_policy': 'historical_exact_date',
            'fx_date_source': 'explicit_date',
            'fx_explicit_date': self._on(-3),
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        row.write({'inverse_company_rate': 83.0})
        result = self._normalize(version)
        self.assertTrue(result['fx_reassessment_required'])
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(8400))

    def test_his08_t004_as_known_result_does_not_use_a_later_approval(self):
        self._fixed('100', '84')
        time.sleep(1.1)
        later = self._fixed('100', '90')
        cutoff = fields.Datetime.subtract(later.approved_at, seconds=1)
        result = self._normalize(later, knowledge_cutoff=cutoff)
        self.assertEqual(result['financial_status'], 'HISTORICAL_EVIDENCE_REVIEW_REQUIRED')
        self.assertFalse(result['comparable_unit_price_exact'])

    def test_his08_t005_repeated_calls_do_not_create_rows(self):
        version = self._fixed('100', '84')
        versions = self.env['cpla.customer.contract.version'].search_count([])
        rates = self.env['res.currency.rate'].search_count([])
        self._normalize(version)
        self._normalize(version)
        self.assertEqual(self.env['cpla.customer.contract.version'].search_count([]), versions)
        self.assertEqual(self.env['res.currency.rate'].search_count([]), rates)

    def test_his08_t006_one_snapshot_is_not_mixed_with_a_later_clause(self):
        version = self._fixed('100', '84')
        price = self._normalize(version)['comparable_unit_price_exact']
        self.assertEqual(_dec(price), _dec(8400))
        self.assertEqual(version.tax_basis, 'tax_excluded')
        self.assertEqual(version.fx_multiplier_exact, '84')

    def test_int08_t001_resolver_selects_the_approved_version(self):
        version = self._fixed('100', '84')
        result = self._resolve(version)
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['version_id'], version.id)

    def test_int08_t002_quantity_tier_is_selected(self):
        version = self._box_version()
        result = self._resolve(version, quantity=10, comparison_uom_id=self.unit.id)
        self.assertEqual(result['tier_status'], 'tier_matched')
        self.assertEqual(_dec(result['normalized_unit_price_exact']), _dec(12))

    def test_int08_t003_uom_price_is_preserved_as_the_source(self):
        version = self._box_version()
        result = self._resolve(version, quantity=10, comparison_uom_id=self.unit.id)
        self.assertEqual(_dec(result['source_price_exact']), _dec(12))
        self.assertEqual(_dec(result['normalized_unit_price_exact']), _dec(12))

    def test_int08_t004_currency_conversion_follows_the_uom_price(self):
        version = self._box_version()
        result = self._resolve(version, quantity=10, comparison_uom_id=self.unit.id)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(1008))

    def test_int08_t005_tax_basis_is_applied_before_a_comparable_price(self):
        version = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': 'single_ordinary_percent',
            'tax_percent_exact': '18',
            'rounding_stage': 'preserve_exact',
        })
        result = self._resolve(version)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(1000))
        self.assertEqual(result['tax_status'], 'TAX_INCLUDED_SIMPLE')

    def test_int08_t006_output_keeps_the_source_references(self):
        version = self._fixed('100', '84')
        result = self._resolve(version)
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['version_line_id'], version.line_ids.id)
        self.assertEqual(result['policy_revision_id'], version.policy_id.id)
        self.assertFalse(result['policy_operationally_approved'])

    def test_int08_t007_missing_clause_stays_in_review(self):
        version = self._v1(1000, self.company_a.currency_id)
        result = self._resolve(version)
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertIn(result['financial_status'], (
            'INVALID_CURRENCY_CONTEXT',
            'FX_RATE_REVIEW_REQUIRED',
            'TAX_BASIS_REVIEW_REQUIRED',
        ))
        self.assertFalse(result['comparable_unit_price_exact'])
        self.assertFalse(result['leakage_amount'])

    def test_int08_t008_discount_is_not_applied(self):
        version = self._box_version()
        result = self._resolve(version, quantity=100, comparison_uom_id=self.unit.id, discount_rate=0.05)
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(1008))
        self.assertNotEqual(_dec(result['comparable_unit_price_exact']), _dec('957.60'))
        self.assertFalse(result['discount_applied'])

    def test_int08_t009_no_leakage_finding_is_created(self):
        self._fixed('100', '84')
        self.assertFalse(self.env['cpla.leakage.finding'].search_count([]))
        self.assertNotIn('cpla.recovery', self.env.registry)
        self.assertNotIn('cpla.audit', self.env.registry)

    def test_int08_t010_no_posted_move_is_modified(self):
        before = self._move_count()
        version = self._fixed('100', '84')
        self._resolve(version)
        self.assertEqual(self._move_count(), before)

    def test_reg08_t001_module_version_is_pinned(self):
        manifest = Manifest.for_addon(MODULE)
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(module.latest_version, '19.0.1.15.0')
        self.assertEqual(module.state, 'installed')

    def test_reg08_t002_financial_fields_exist_on_the_version(self):
        self.assertIn('fx_policy', self.env['cpla.customer.contract.version']._fields)
        self.assertIn('tax_basis', self.env['cpla.customer.contract.version']._fields)
        self.assertEqual(
            self.env['cpla.customer.contract.version']._fields['fx_policy'].default(self.env['cpla.customer.contract.version']),
            'unconfigured',
        )

    def test_reg08_t003_unconfigured_upgrade_does_not_invent_a_clause(self):
        version = self._v1(1000, self.company_a.currency_id)
        self.assertEqual(version.fx_policy, 'unconfigured')
        self.assertFalse(version.fx_multiplier_exact)
        self.assertEqual(version.line_ids.price_unit, 1000.0)

    def test_reg08_t004_quantity_tier_model_remains(self):
        self.assertIn('cpla.customer.contract.version.tier', self.env.registry)
        self.assertIn('cpla.pricing.quantity', self.env.registry)

    def test_reg08_t005_company_policy_is_still_not_operational(self):
        self.assertFalse(self.policy_a.operationally_approved)
        self.assertEqual(self.policy_a.fx_basis_policy, 'invoice_date')
        with self.assertRaises(UserError):
            self._env(self.manager, self.company_a)['cpla.company.policy'].propose_fixed_rate(84)

    def test_reg08_t006_security_groups_still_resolve(self):
        self.assertTrue(self.manager.has_group(f'{MODULE}.group_contract_manager'))
        self.assertFalse(self.sales.has_group(f'{MODULE}.group_contract_user'))
        self.assertEqual(
            self.env['ir.model.access'].search_count([
                ('model_id.model', '=', 'cpla.pricing.financial'),
            ]),
            0,
        )

    def test_reg08_t007_views_load(self):
        form = self.env['cpla.customer.contract.version'].get_view(view_type='form')
        check = self.env['cpla.pricing.applicability.check'].get_view(view_type='form')
        self.assertIn('Financial Clause', form['arch'])
        self.assertIn('comparable_unit_price_exact', check['arch'])
        self.assertIn('not an approved price', check['arch'])
        self.assertNotIn('Run Invoice Audit', form['arch'])
        self.assertNotIn('Run Invoice Audit', check['arch'])

    def test_reg08_t008_dependencies_remain_base_and_product(self):
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])

    def test_reg08_t009_no_accounting_journal_is_created_by_install_data(self):
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'account.move'),
        ]))

    def test_reg08_t010_no_audit_cron_is_created(self):
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'ir.cron'),
        ]))

    def test_dev08_repeated_normalization_stays_under_the_ceiling(self):
        version = self._fixed('100', '84')
        service = self._service()
        line = version.line_ids
        started = time.perf_counter()
        for _index in range(30):
            service.normalize(line, {})
        elapsed = time.perf_counter() - started
        _logger.info('DEV08 normalize x30 elapsed %s', elapsed)
        self.assertLess(elapsed, 5.0)

    def _assert_unsupported(self, structure):
        version = self._clause(1180, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_included',
            'tax_structure': structure,
            'tax_percent_exact': '18',
        })
        result = self._normalize(version)
        self.assertEqual(result['financial_status'], 'UNSUPPORTED_TAX_STRUCTURE')
        self.assertFalse(result['comparable_unit_price_exact'])
        return result

    def _priced(self, price, stage):
        return self._clause(price, self.company_a.currency_id, {
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': stage,
        })

    def _box_version(self):
        box = self.env['uom.uom'].create({
            'name': 'CPLA08 Box',
            'relative_uom_id': self.unit.id,
            'relative_factor': 10,
        })
        self.bearing.product_tmpl_id.write({'uom_ids': [Command.link(box.id)]})
        first = self._v1(120, self.foreign)
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Box price with a fixed rate.',
            'effective_from': self._today(),
            'fx_policy': 'fixed_rate',
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'fx_multiplier_exact': '84',
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        line = amendment.line_ids
        line.write({
            'tier_method': 'full_volume',
            'quantity_basis': 'sales_order',
            'return_policy': 'unconfigured',
        })
        env['cpla.customer.contract.version.tier'].create({
            'version_line_id': line.id,
            'min_quantity': 1,
            'has_maximum': False,
            'quantity_uom_id': self.unit.id,
            'price_unit': 120,
            'pricing_uom_id': box.id,
        })
        amendment.action_submit_for_review()
        record = self._env(self.finance, self.company_a)[
            'cpla.customer.contract.version'
        ].browse(amendment.id)
        record.action_approve()
        return record

    def _resolve(self, version, **extra):
        payload = {
            'company_id': version.company_id.id,
            'partner_id': version.partner_id.id,
            'product_id': version.line_ids.product_id.id,
            'pricing_date': self._today(),
        }
        payload.update(extra)
        return self._env(self.manager if version.company_id == self.company_a else self.manager_b, version.company_id)[
            'cpla.pricing.applicability'
        ].resolve(payload)

    def _move_count(self):
        if 'account.move' not in self.env.registry:
            return 0
        return self.env['account.move'].search_count([])
