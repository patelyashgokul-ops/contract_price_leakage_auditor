import logging
import time
from decimal import Decimal

from odoo import Command, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'
_logger = logging.getLogger(__name__)


def _dec(value):
    return Decimal(str(value))


@tagged('post_install', '-at_install')
class TestDev09DiscountAuthority(TransactionCase):
    """Authorized discounts. An approved concession is not a leakage finding.

    Amounts use the test company currency and fictional codes. INR and USD
    are not activated. Company discount candidates are not rules.
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
        cls.owner = cls._make_user('cpla09_owner', 'group_contract_user', cls.company_a)
        cls.owner_b = cls._make_user('cpla09_owner_b', 'group_contract_user', cls.company_b)
        cls.manager = cls._make_user('cpla09_manager', 'group_contract_manager', cls.company_a)
        cls.manager_b = cls._make_user('cpla09_manager_b', 'group_contract_manager', cls.company_b)
        cls.finance = cls._make_user('cpla09_finance', 'group_finance_manager', cls.company_a)
        cls.finance2 = cls._make_user('cpla09_finance2', 'group_finance_manager', cls.company_a)
        cls.finance_b = cls._make_user('cpla09_finance_b', 'group_finance_manager', cls.company_b)
        cls.reviewer = cls._make_user('cpla09_reviewer', 'group_finance_reviewer', cls.company_a)
        cls.auditor = cls._make_user('cpla09_auditor', 'group_internal_auditor', cls.company_a)
        cls.sales = cls._make_user('cpla09_sales', 'group_sales_pricing_reviewer', cls.company_a)
        cls.admin = cls._make_user('cpla09_admin', 'group_app_admin', cls.company_a)
        cls.combined = cls._make_user(
            'cpla09_combined', 'group_contract_user', cls.company_a,
            extra_groups=('group_finance_manager',),
        )
        cls.both = cls._make_user(
            'cpla09_both', 'group_contract_manager', cls.company_a,
            companies=cls.company_a | cls.company_b,
        )
        cls.policy_a = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_a.id,
            'change_reason': 'Candidate reference. Not an operational approval.',
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
        cls.branch = cls.env['res.partner'].create({
            'name': 'XYZ Plant',
            'parent_id': cls.partner.id,
            'company_id': cls.company_a.id,
            'type': 'delivery',
        })
        cls.other_partner = cls.env['res.partner'].create({
            'name': 'Unrelated Buyer',
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
        cls.other_product = cls.env['product.product'].create({
            'name': 'Bearing B',
            'list_price': 9999.0,
            'company_id': False,
        })
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.foreign = cls.env['res.currency'].create({
            'name': 'Q9A',
            'symbol': 'Q',
            'rounding': 0.01,
        })
        cls.third = cls.env['res.currency'].create({
            'name': 'Q9B',
            'symbol': 'B',
            'rounding': 0.01,
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
        return fields.Date.context_today(self.env['cpla.discount.evaluator'])

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

    def _staff(self, company):
        if company == self.company_a:
            return self.owner, self.manager, self.finance
        return self.owner_b, self.manager_b, self.finance_b

    def _policy(self, company):
        return self.policy_a if company == self.company_a else self.policy_b

    def _v1(self, products, currency, company=None, partner=None):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
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
        for product, price in products:
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
            'source_reference': 'AGR-009',
            'description': 'Signed pricing schedule.',
            'datas': 'c2lnbmVk',
        })
        contract.action_submit_for_review()
        manager = self._staff(company)[1]
        return self._env(manager, company)['cpla.customer.contract.version'].approve_initial(
            self._env(manager, company)['cpla.customer.contract'].browse(contract.id)
        )

    def _priced(self, price='1200', concessions=(), policy=None, currency=None, company=None,
                products=None, tiers=None, partner=None):
        company = company or self.company_a
        currency = currency or company.currency_id
        products = products or [(self.bearing, price)]
        first = self._v1(products, currency, company=company, partner=partner)
        owner = self._staff(company)[0]
        env = self._env(owner, company)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        values = {
            'amendment_reason': 'Authorized discount clause. Not a retroactive restatement.',
            'effective_from': self._today(),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        }
        values.update(policy or {})
        amendment.write(values)
        if tiers:
            line = amendment.line_ids.filtered(lambda item: item.product_id == products[0][0])[:1]
            line.write({
                'tier_method': 'full_volume',
                'quantity_basis': 'sales_order',
                'return_policy': 'unconfigured',
            })
            for minimum, maximum, tier_price in tiers:
                env['cpla.customer.contract.version.tier'].create({
                    'version_line_id': line.id,
                    'min_quantity': minimum,
                    'has_maximum': maximum is not None,
                    'max_quantity': maximum or 0.0,
                    'quantity_uom_id': line.uom_id.id,
                    'price_unit': tier_price,
                    'pricing_uom_id': line.uom_id.id,
                })
        for spec in concessions:
            self._concession(amendment, spec)
        amendment.action_submit_for_review()
        finance = self._staff(company)[2]
        record = self._env(finance, company)['cpla.customer.contract.version'].browse(amendment.id)
        record.action_approve()
        return record

    def _concession(self, version, spec):
        product = spec.get('product') or version.line_ids[:1].product_id
        line = version.line_ids.filtered(lambda item: item.product_id == product)[:1]
        kind = spec['type']
        values = {
            'version_id': version.id,
            'sequence': spec.get('sequence', 10),
            'concession_type': kind,
            'customer_scope': spec.get('customer_scope', 'version_customer'),
            'partner_id': spec.get('partner').id if spec.get('partner') else False,
            'product_scope': spec.get('product_scope', 'version_line'),
            'product_id': spec.get('variant').id if spec.get('variant') else False,
            'product_tmpl_id': spec.get('template').id if spec.get('template') else False,
            'exclusive': spec.get('exclusive', False),
            'precedence_rank': spec.get('rank', 0),
            'effective_from': spec.get('start'),
            'effective_to': spec.get('end'),
            'quantity_min_exact': spec.get('minimum'),
            'quantity_max_exact': spec.get('maximum'),
            'quantity_uom_id': spec.get('quantity_uom').id if spec.get('quantity_uom') else False,
            'evidence_reference': spec.get('evidence', 'AGR-DISC-009'),
            'unsupported_reason': spec.get('unsupported_reason'),
        }
        if values['product_scope'] == 'version_line':
            values['version_line_id'] = line.id
        if kind == 'percentage':
            values['percent_exact'] = spec['percent']
        elif kind in ('fixed_per_unit', 'fixed_special_price'):
            values['amount_exact'] = spec['amount']
            values['currency_id'] = (spec.get('currency') or version.currency_id).id
            values['uom_id'] = (spec.get('uom') or line.uom_id).id
        owner = self._staff(version.company_id)[0]
        return self._env(owner, version.company_id)['cpla.discount.concession'].create(values)

    def _eval(self, version, user=None, product=None, **extra):
        user = user or self.manager
        product = product or extra.get('product_id') and self.env['product.product'].browse(extra['product_id'])
        line = version.line_ids[:1]
        if product:
            matched = version.line_ids.filtered(lambda item: item.product_id == product)
            if matched:
                line = matched[:1]
        else:
            product = line.product_id
        payload = {
            'partner_id': version.partner_id.id,
            'product_id': product.id,
            'pricing_date': self._today(),
        }
        payload.update(extra)
        return self._env(user, version.company_id)['cpla.discount.evaluator'].evaluate(line, payload)

    def _price(self, result):
        self.assertIn(result['discount_status'], (
            'AUTHORIZED_PRICE_RESOLVED',
            'NO_ADDITIONAL_DISCOUNT',
            'SPECIAL_PRICE_APPLICABLE',
            'APPROVED_OVERRIDE_APPLICABLE',
        ))
        return _dec(result['approved_adjusted_unit_price_exact'])

    def _request(self, version, kind='transaction_override', user=None, **extra):
        user = user or self.owner
        product = extra.pop('product', version.line_ids[:1].product_id)
        values = {
            'company_id': version.company_id.id,
            'request_kind': kind,
            'version_id': version.id,
            'partner_id': extra.pop('partner', version.partner_id).id,
            'product_id': product.id,
            'currency_id': (extra.pop('currency', version.currency_id)).id,
            'uom_id': (extra.pop('uom', version.line_ids[:1].uom_id)).id,
            'reason': 'Named commercial reason.',
            'evidence_reference': 'EMAIL-009',
            'effective_from': self._today(),
        }
        values.update(extra)
        return self._env(user, version.company_id)['cpla.discount.approval'].create(values)

    def _approve(self, approval, user=None):
        user = user or self.finance
        record = self._env(user, approval.company_id)['cpla.discount.approval'].browse(approval.id)
        record.action_approve()
        return record

    def _limit(self, basis='per_unit_reduction'):
        if basis == 'percent_reduction':
            return {
                'authority_limit_basis': 'percent_reduction',
                'authority_max_percent_exact': '10',
            }
        if basis == 'stated_exposure':
            return {
                'authority_limit_basis': 'stated_exposure',
                'authority_max_exposure_exact': '25000',
                'authority_exposure_currency_id': self.company_a.currency_id.id,
                'authority_exposure_quantity_exact': '500',
            }
        return {
            'authority_limit_basis': 'per_unit_reduction',
            'authority_max_unit_reduction_exact': '50',
        }

    def _box(self):
        box = self.env['uom.uom'].create({
            'name': 'CPLA09 Box',
            'relative_uom_id': self.unit.id,
            'relative_factor': 10,
        })
        self.bearing.product_tmpl_id.write({'uom_ids': [Command.link(box.id)]})
        return box

    def test_disc09_t001_gold_disc_001_special_price_and_reconciliation(self):
        version = self._priced(concessions=[{
            'type': 'fixed_special_price',
            'amount': '1150',
        }])
        result = self._eval(version, quantity='500', actual_unit_price_exact='1100')
        self.assertEqual(result['discount_status'], 'SPECIAL_PRICE_APPLICABLE')
        self.assertEqual(self._price(result), _dec(1150))
        self.assertEqual(_dec(result['pre_discount_unit_price_exact']), _dec(1200))
        self.assertEqual(_dec(result['concession_per_unit_exact']), _dec(50))
        self.assertEqual(_dec(result['authorized_concession_extended_exact']), _dec(25000))
        self.assertEqual(_dec(result['gross_difference_extended_exact']), _dec(50000))
        self.assertEqual(_dec(result['potential_unauthorized_extended_exact']), _dec(25000))
        self.assertEqual(result['price_exception_indicator'], 'UNAUTHORIZED_DISCOUNT_INDICATOR')
        self.assertFalse(result['leakage_amount'])
        self.assertFalse(result['is_recovered_cash'])
        self.assertFalse(result['leakage_finding_created'])
        self.assertTrue(result['discount_applied'])
        self.assertTrue(result['calculation_stages'])
        self.assertTrue(result['selected_concession_ids'])

    def test_disc09_t002_gold_disc_002_percentage(self):
        version = self._priced(concessions=[{'type': 'percentage', 'percent': '5'}])
        result = self._eval(version)
        self.assertEqual(result['discount_status'], 'AUTHORIZED_PRICE_RESOLVED')
        self.assertEqual(self._price(result), _dec(1140))
        self.assertTrue(result['discount_applied'])

    def test_disc09_t003_gold_disc_003_fixed_reduction(self):
        version = self._priced(concessions=[{'type': 'fixed_per_unit', 'amount': '50'}])
        result = self._eval(version)
        self.assertEqual(self._price(result), _dec(1150))
        self.assertEqual(_dec(result['concession_per_unit_exact']), _dec(50))

    def test_disc09_t004_foreign_amount_is_not_subtracted_without_a_rate(self):
        version = self._priced(
            '100',
            concessions=[{
                'type': 'fixed_per_unit',
                'amount': '5',
                'currency': self.third,
            }],
            currency=self.foreign,
            policy={
                'fx_policy': 'fixed_rate',
                'fx_source_currency_id': self.foreign.id,
                'fx_target_currency_id': self.company_a.currency_id.id,
                'fx_multiplier_exact': '84',
                'comparison_currency_policy': 'company_currency',
            },
        )
        result = self._eval(version)
        self.assertEqual(result['discount_status'], 'DISCOUNT_EVIDENCE_REVIEW_REQUIRED')
        self.assertEqual(result['discount_reason'], 'concession_fx_missing')
        self.assertFalse(result['approved_adjusted_unit_price_exact'])
        self.assertFalse(result['discount_applied'])

    def test_disc09_t005_gold_disc_009_box_discount_converts_then_fx(self):
        box = self._box()
        version = self._priced(
            '100',
            concessions=[{
                'type': 'fixed_per_unit',
                'amount': '5',
                'currency': self.foreign,
                'uom': box,
            }],
            currency=self.foreign,
            policy={
                'fx_policy': 'fixed_rate',
                'fx_source_currency_id': self.foreign.id,
                'fx_target_currency_id': self.company_a.currency_id.id,
                'fx_multiplier_exact': '84',
                'comparison_currency_policy': 'company_currency',
            },
        )
        concession = version.concession_ids
        self.assertEqual(
            _dec(concession.concession_uom_factor_exact) / _dec(concession.product_uom_factor_exact),
            _dec(10),
        )
        result = self._eval(version, quantity='1')
        self.assertEqual(self._price(result), _dec(8358))
        self.assertEqual(_dec(result['concession_per_unit_exact']), _dec(42))
        self.assertEqual(_dec(result['pre_discount_unit_price_exact']), _dec(8400))

    def test_disc09_t006_gold_disc_004_sequential_percentages(self):
        version = self._priced(
            concessions=[
                {'type': 'percentage', 'percent': '5', 'sequence': 10},
                {'type': 'percentage', 'percent': '3', 'sequence': 20},
            ],
            policy={'discount_stacking_policy': 'sequential_percentage'},
        )
        result = self._eval(version)
        self.assertEqual(self._price(result), _dec('1105.8'))
        self.assertEqual(len(result['calculation_stages']), 2)

    def test_disc09_t007_gold_disc_005_additive_percentages(self):
        version = self._priced(
            concessions=[
                {'type': 'percentage', 'percent': '5', 'sequence': 10},
                {'type': 'percentage', 'percent': '3', 'sequence': 20},
            ],
            policy={'discount_stacking_policy': 'additive_percentage'},
        )
        result = self._eval(version)
        self.assertEqual(self._price(result), _dec(1104))

    def test_disc09_t008_gold_disc_006_exclusive_special_is_not_discounted_again(self):
        version = self._priced(concessions=[
            {'type': 'fixed_special_price', 'amount': '1150', 'exclusive': True, 'sequence': 10},
            {'type': 'percentage', 'percent': '5', 'sequence': 20},
        ])
        result = self._eval(version)
        self.assertEqual(result['discount_status'], 'SPECIAL_PRICE_APPLICABLE')
        self.assertEqual(self._price(result), _dec(1150))
        self.assertEqual(len(result['selected_concession_ids']), 1)

    def test_disc09_t009_gold_disc_007_percentage_then_fixed(self):
        version = self._priced(
            concessions=[
                {'type': 'percentage', 'percent': '10', 'sequence': 20},
                {'type': 'fixed_per_unit', 'amount': '50', 'sequence': 10},
            ],
            policy={'discount_stacking_policy': 'percentage_then_fixed'},
        )
        result = self._eval(version)
        self.assertEqual(self._price(result), _dec(1030))

    def test_disc09_t010_gold_disc_008_fixed_then_percentage(self):
        version = self._priced(
            concessions=[
                {'type': 'fixed_per_unit', 'amount': '50', 'sequence': 20},
                {'type': 'percentage', 'percent': '10', 'sequence': 10},
            ],
            policy={'discount_stacking_policy': 'fixed_then_percentage'},
        )
        result = self._eval(version)
        self.assertEqual(self._price(result), _dec(1035))

    def test_disc09_t011_one_percent_is_not_applied_twice(self):
        version = self._priced(concessions=[{'type': 'percentage', 'percent': '5'}])
        result = self._eval(version)
        self.assertEqual(self._price(result), _dec(1140))
        self.assertNotEqual(self._price(result), _dec(1083))
        self.assertEqual(len(result['selected_concession_ids']), 1)

    def test_disc09_t012_two_concessions_without_a_mode_stay_in_review(self):
        self.policy_a.write({'discount_approval_policy': 'approval_reference_required'})
        version = self._priced(concessions=[
            {'type': 'percentage', 'percent': '5'},
            {'type': 'percentage', 'percent': '3'},
        ])
        result = self._eval(version)
        self.assertEqual(result['discount_status'], 'DISCOUNT_STACKING_REVIEW_REQUIRED')
        self.assertFalse(result['approved_adjusted_unit_price_exact'])
        self.assertFalse(result['discount_applied'])
        self.assertEqual(self.policy_a.discount_approval_policy, 'approval_reference_required')

    def test_disc09_t013_unsupported_benefit_is_not_converted(self):
        version = self._priced(concessions=[
            {
                'type': 'unsupported',
                'unsupported_reason': 'Buy two get one is not a per-unit discount.',
            },
            {'type': 'percentage', 'percent': '5'},
        ])
        result = self._eval(version)
        self.assertEqual(result['discount_status'], 'UNSUPPORTED_CONCESSION_TYPE')
        self.assertFalse(result['approved_adjusted_unit_price_exact'])
        self.assertFalse(result['discount_applied'])

    def test_disc09_t014_exact_stack_is_not_rounded_early_and_per_unit_rounds_once(self):
        sequential = self._priced(
            concessions=[
                {'type': 'percentage', 'percent': '5', 'sequence': 10},
                {'type': 'percentage', 'percent': '3', 'sequence': 20},
            ],
            policy={'discount_stacking_policy': 'sequential_percentage'},
        )
        exact = self._eval(sequential)
        self.assertEqual(exact['approved_adjusted_unit_price_exact'], '1105.8')
        rounded = self._priced(
            '10',
            concessions=[{'type': 'percentage', 'percent': '33.33'}],
            currency=self.foreign,
            policy={'rounding_stage': 'per_unit'},
        )
        result = self._eval(rounded)
        self.assertEqual(self._price(result), _dec('6.67'))

    def test_disc09_t015_a_non_positive_price_is_refused(self):
        with self.assertRaises(ValidationError):
            self._priced(concessions=[{'type': 'percentage', 'percent': '100'}])
        version = self._priced(concessions=[{'type': 'fixed_per_unit', 'amount': '1200'}])
        result = self._eval(version)
        self.assertEqual(result['discount_status'], 'DISCOUNT_PRICE_INVALID')
        self.assertFalse(result['approved_adjusted_unit_price_exact'])
        self.assertFalse(result['discount_applied'])

    def test_gold_disc_010_and_011_expired_and_future_dates(self):
        expired = self._priced(concessions=[{
            'type': 'percentage',
            'percent': '5',
            'start': self._on(-10),
            'end': self._on(-1),
        }])
        past = self._eval(expired)
        self.assertEqual(past['discount_status'], 'DISCOUNT_EXPIRED')
        self.assertFalse(past['approved_adjusted_unit_price_exact'])
        future = self._priced(concessions=[{
            'type': 'percentage',
            'percent': '5',
            'start': self._on(5),
        }])
        early = self._eval(future)
        self.assertEqual(early['discount_status'], 'DISCOUNT_NOT_YET_EFFECTIVE')
        self.assertFalse(early['approved_adjusted_unit_price_exact'])
        later = self._eval(future, pricing_date=self._on(5))
        self.assertEqual(self._price(later), _dec(1140))

    def test_gold_disc_012_and_013_wrong_customer_and_variant(self):
        version = self._priced(concessions=[{'type': 'fixed_special_price', 'amount': '1150'}])
        customer = self._eval(version, partner_id=self.other_partner.id)
        self.assertEqual(customer['discount_status'], 'DISCOUNT_SCOPE_MISMATCH')
        self.assertFalse(customer['approved_adjusted_unit_price_exact'])
        variant = self._eval(version, product_id=self.other_product.id)
        self.assertEqual(variant['discount_status'], 'DISCOUNT_SCOPE_MISMATCH')
        self.assertFalse(variant['approved_adjusted_unit_price_exact'])
        self.assertNotIn('1150', ' '.join(variant['discount_trace']))

    def test_gold_disc_014_override_exposure_uses_the_adjusted_baseline(self):
        version = self._priced(
            concessions=[{'type': 'fixed_special_price', 'amount': '1150'}],
            policy=self._limit('per_unit_reduction'),
        )
        approval = self._request(
            version,
            proposed_price_exact='1100',
            quantity_exact='500',
            sale_reference='SO-009',
            sale_line_reference='SOL-009',
        )
        approval.action_submit()
        approved = self._approve(approval)
        self.assertEqual(approved.baseline_unit_price_exact, '1150')
        self.assertEqual(approved.exposure_exact, '25000')
        self.assertEqual(approved.approver_id, self.finance)
        self.assertTrue(approved.approved_at)
        self.assertNotEqual(approved.approver_id, approved.requester_id)

    def test_gold_disc_015_rejected_override_is_not_a_price(self):
        version = self._priced(policy=self._limit())
        approval = self._request(
            version,
            proposed_price_exact='1100',
            quantity_exact='500',
            sale_reference='SO-015',
            sale_line_reference='SOL-015',
        )
        approval.action_submit()
        finance = self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id)
        finance.write({'rejection_reason': 'Outside the named authority.'})
        finance.action_reject()
        result = self._eval(
            version,
            sale_reference='SO-015',
            sale_line_reference='SOL-015',
            quantity='500',
        )
        self.assertEqual(result['discount_status'], 'DISCOUNT_APPROVAL_REJECTED')
        self.assertFalse(result['approved_adjusted_unit_price_exact'])
        self.assertFalse(result['discount_applied'])

    def test_gold_disc_016_an_entered_discount_without_approval_is_not_authorized(self):
        version = self._priced()
        forged = self._eval(version, discount_rate='0.05', entered_discount_percent='5')
        self.assertEqual(forged['discount_status'], 'DISCOUNT_EVIDENCE_REVIEW_REQUIRED')
        self.assertEqual(forged['discount_reason'], 'entered_discount_without_approval')
        self.assertFalse(forged['approved_adjusted_unit_price_exact'])
        self.assertFalse(forged['discount_applied'])
        clean = self._eval(version, discount_rate='0.05')
        self.assertEqual(self._price(clean), _dec(1200))
        self.assertFalse(clean['discount_applied'])

    def test_gold_disc_017_his09_retroactive_grant_respects_the_cutoff(self):
        version = self._priced(policy={
            'retroactive_discount_authority': 'explicitly_allowed',
            'authority_limit_basis': 'percent_reduction',
            'authority_max_percent_exact': '10',
        })
        time.sleep(1.1)
        cutoff = fields.Datetime.now()
        time.sleep(1.1)
        approval = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='5',
            effective_from=self._on(-5),
        )
        approval.action_submit()
        approved = self._approve(approval)
        self.assertTrue(approved.retroactive_granted)
        hidden = self._eval(version, knowledge_cutoff=cutoff)
        self.assertEqual(self._price(hidden), _dec(1200))
        self.assertFalse(hidden['discount_applied'])
        shown = self._eval(version)
        self.assertEqual(self._price(shown), _dec(1140))
        self.assertTrue(shown['discount_applied'])

    def test_gold_disc_018_exclusive_prices_without_precedence_conflict(self):
        version = self._priced(concessions=[
            {'type': 'fixed_special_price', 'amount': '1150', 'exclusive': True, 'rank': 0},
            {'type': 'fixed_special_price', 'amount': '1100', 'exclusive': True, 'rank': 0},
        ])
        result = self._eval(version)
        self.assertEqual(result['discount_status'], 'DISCOUNT_AUTHORITY_CONFLICT')
        self.assertFalse(result['approved_adjusted_unit_price_exact'])
        ranked = self._priced(concessions=[
            {'type': 'fixed_special_price', 'amount': '1100', 'exclusive': True, 'rank': 2},
            {'type': 'fixed_special_price', 'amount': '1180', 'exclusive': True, 'rank': 1},
        ])
        chosen = self._eval(ranked)
        self.assertEqual(self._price(chosen), _dec(1180))

    def test_gold_disc_019_tier_policy_is_explicit(self):
        after = self._priced(
            concessions=[{'type': 'percentage', 'percent': '5'}],
            policy={'tier_discount_policy': 'discount_after_tier'},
            tiers=[(500, None, 1100)],
        )
        discounted = self._eval(after, quantity='500')
        self.assertEqual(_dec(discounted['pre_discount_unit_price_exact']), _dec(1100))
        self.assertEqual(self._price(discounted), _dec(1045))
        exclusive = self._priced(
            concessions=[{'type': 'percentage', 'percent': '5'}],
            policy={'tier_discount_policy': 'exclusive_tier'},
            tiers=[(500, None, 1100)],
        )
        held = self._eval(exclusive, quantity='500')
        self.assertEqual(held['discount_status'], 'NO_ADDITIONAL_DISCOUNT')
        self.assertEqual(held['discount_reason'], 'exclusive_tier')
        self.assertEqual(self._price(held), _dec(1100))
        self.assertFalse(held['discount_applied'])
        missing = self._priced(
            concessions=[{'type': 'percentage', 'percent': '5'}],
            tiers=[(500, None, 1100)],
        )
        review = self._eval(missing, quantity='500')
        self.assertEqual(review['discount_status'], 'DISCOUNT_STACKING_REVIEW_REQUIRED')
        self.assertEqual(review['discount_reason'], 'tier_discount_policy_missing')
        self.assertFalse(review['approved_adjusted_unit_price_exact'])

    def test_gold_disc_020_no_recovery_or_accounting_document(self):
        before = self.env['account.move'].search_count([]) if 'account.move' in self.env else 0
        version = self._priced(concessions=[{'type': 'fixed_special_price', 'amount': '1150'}])
        result = self._eval(version, quantity='500', actual_unit_price_exact='1100')
        self.assertEqual(self._price(result), _dec(1150))
        self.assertFalse(result['leakage_amount'])
        self.assertFalse(result['is_recovered_cash'])
        self.assertFalse(result['leakage_finding_created'])
        self.assertFalse(self.env['cpla.leakage.finding'].search_count([]))
        if 'account.move' in self.env:
            self.assertEqual(self.env['account.move'].search_count([]), before)
        if 'sale.order' in self.env:
            self.assertEqual(self.env['sale.order'].search_count([
                ('client_order_ref', '=', 'SO-020'),
            ]), 0)

    def test_app09_t001_owner_creates_a_draft_and_cannot_set_the_approver(self):
        version = self._priced(policy=self._limit())
        approval = self._request(
            version,
            proposed_price_exact='1150',
            quantity_exact='10',
            sale_reference='SO-001',
            sale_line_reference='SOL-001',
        )
        self.assertEqual(approval.state, 'draft')
        self.assertEqual(approval.requester_id, self.owner)
        self.assertFalse(approval.approver_id)
        with self.assertRaises(UserError):
            self._request(version, approver_id=self.owner.id, state='approved')

    def test_app09_t002_submit_requires_evidence_and_scope(self):
        version = self._priced(policy=self._limit())
        incomplete = self._request(version, reason=False, evidence_reference=False)
        with self.assertRaises(UserError):
            incomplete.action_submit()
        self.assertEqual(incomplete.state, 'draft')
        wrong = self._request(version, partner=self.other_partner, reason='Because', evidence_reference='EMAIL')
        with self.assertRaises(UserError):
            wrong.action_submit()
        self.assertEqual(wrong.state, 'draft')

    def test_app09_t003_finance_manager_approves_within_the_limit(self):
        version = self._priced(policy=self._limit('percent_reduction'))
        approval = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='5',
        )
        approval.action_submit()
        approved = self._approve(approval)
        self.assertEqual(approved.state, 'approved')
        self.assertEqual(approved.approver_id, self.finance)
        result = self._eval(version)
        self.assertEqual(self._price(result), _dec(1140))

    def test_app09_t004_manager_reviewer_and_admin_cannot_approve(self):
        version = self._priced(policy=self._limit())
        approval = self._request(
            version,
            proposed_price_exact='1160',
            quantity_exact='10',
            sale_reference='SO-004',
            sale_line_reference='SOL-004',
        )
        approval.action_submit()
        for user in (self.manager, self.reviewer, self.owner, self.admin):
            record = self._env(user, self.company_a)['cpla.discount.approval'].browse(approval.id)
            with self.assertRaises(AccessError):
                record.action_approve()
        self.assertEqual(approval.state, 'submitted')
        self.assertFalse(approval.approver_id)

    def test_app09_t005_combined_role_cannot_self_approve(self):
        version = self._priced(policy=self._limit())
        approval = self._request(
            version,
            user=self.combined,
            proposed_price_exact='1160',
            quantity_exact='10',
            sale_reference='SO-005',
            sale_line_reference='SOL-005',
        )
        self._env(self.combined, self.company_a)['cpla.discount.approval'].browse(approval.id).action_submit()
        record = self._env(self.combined, self.company_a)['cpla.discount.approval'].browse(approval.id)
        with self.assertRaises(AccessError):
            record.action_approve()
        self.assertEqual(approval.state, 'submitted')
        self.assertFalse(approval.approver_id)

    def test_app09_t006_unit_percent_and_exposure_limits_block(self):
        version = self._priced(policy=self._limit())
        over = self._request(
            version,
            proposed_price_exact='1100',
            quantity_exact='10',
            sale_reference='SO-006',
            sale_line_reference='SOL-006',
        )
        over.action_submit()
        with self.assertRaises(UserError):
            self._approve(over)
        self.assertEqual(over.state, 'submitted')
        self.assertFalse(over.approver_id)
        percent_version = self._priced(policy=self._limit('percent_reduction'))
        percent = self._request(
            percent_version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='11',
        )
        percent.action_submit()
        with self.assertRaises(UserError):
            self._approve(percent)
        self.assertEqual(percent.state, 'submitted')

    def test_app09_t007_cross_currency_and_uom_are_not_invented(self):
        version = self._priced(policy=self._limit())
        foreign = self._request(
            version,
            currency=self.foreign,
            proposed_price_exact='10',
            quantity_exact='10',
            sale_reference='SO-007',
            sale_line_reference='SOL-007',
        )
        foreign.action_submit()
        with self.assertRaises(UserError):
            self._approve(foreign)
        self.assertEqual(foreign.state, 'submitted')
        box = self._box()
        mismatched = self._request(
            version,
            uom=box,
            proposed_price_exact='1100',
            quantity_exact='10',
            sale_reference='SO-007B',
            sale_line_reference='SOL-007B',
        )
        mismatched.action_submit()
        with self.assertRaises(UserError):
            self._approve(mismatched)
        self.assertEqual(mismatched.state, 'submitted')

    def test_app09_t008_an_empty_limit_does_not_approve(self):
        version = self._priced()
        approval = self._request(
            version,
            proposed_price_exact='1100',
            quantity_exact='10',
            sale_reference='SO-008',
            sale_line_reference='SOL-008',
        )
        approval.action_submit()
        with self.assertRaises(UserError):
            self._approve(approval)
        self.assertEqual(approval.state, 'submitted')
        self.assertFalse(approval.approver_id)
        self.assertFalse(approval.approved_at)
        self.assertFalse(self.env['cpla.discount.event'].search([
            ('approval_id', '=', approval.id),
            ('event_type', '=', 'approved'),
        ]))

    def test_app09_t009_t010_approver_and_timestamp_come_from_the_server(self):
        version = self._priced(policy=self._limit())
        before = fields.Datetime.now()
        approval = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='4',
        )
        approval.action_submit()
        approved = self._approve(approval)
        self.assertEqual(approved.approver_id, self.finance)
        self.assertGreaterEqual(approved.approved_at, before)
        self.assertNotEqual(approved.requester_id, self.finance)
        snapshot = approved.limit_snapshot_json
        self.assertIn('per_unit_reduction', snapshot)

    def test_app09_t011_and_t012_rejected_and_cancelled_are_excluded(self):
        version = self._priced(policy=self._limit('percent_reduction'))
        rejected = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='5',
        )
        rejected.action_submit()
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(rejected.id).action_reject(
            'Not accepted.'
        )
        denied = self._eval(version)
        self.assertEqual(denied['discount_status'], 'DISCOUNT_APPROVAL_REJECTED')
        self.assertFalse(denied['discount_applied'])
        cancelled = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='4',
        )
        cancelled.action_cancel()
        self.assertEqual(cancelled.state, 'cancelled')
        # The rejected request still matches this version, so the cancelled row is not a price.
        self.assertNotEqual(self._eval(version)['discount_status'], 'AUTHORIZED_PRICE_RESOLVED')

    def test_app09_t013_and_t014_future_and_expired_requests_are_not_applied(self):
        version = self._priced(policy=self._limit('percent_reduction'))
        future = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='5',
            effective_from=self._on(4),
        )
        future.action_submit()
        self._approve(future)
        early = self._eval(version)
        self.assertEqual(self._price(early), _dec(1200))
        self.assertFalse(early['discount_applied'])
        expired = self._priced(
            concessions=[{
                'type': 'percentage',
                'percent': '5',
                'start': self._on(-8),
                'end': self._on(-1),
            }],
        )
        result = self._eval(expired)
        self.assertEqual(result['discount_status'], 'DISCOUNT_EXPIRED')
        self.assertFalse(result['discount_applied'])

    def test_app09_t015_approved_terms_and_history_cannot_be_rewritten(self):
        version = self._priced(
            concessions=[{'type': 'percentage', 'percent': '5'}],
            policy=self._limit('percent_reduction'),
        )
        concession = version.concession_ids
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.discount.concession'].browse(
                concession.id
            ).write({'percent_exact': '9'})
        self.assertEqual(concession.percent_exact, '5')
        with self.assertRaises(UserError):
            concession.unlink()
        approval = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='1',
        )
        approval.action_submit()
        approved = self._approve(approval)
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.discount.approval'].browse(approved.id).write({
                'percent_exact': '9',
            })
        event = self.env['cpla.discount.event'].search([
            ('approval_id', '=', approved.id),
            ('event_type', '=', 'approved'),
        ])
        with self.assertRaises(UserError):
            event.write({'note': 'changed'})
        with self.assertRaises(UserError):
            event.unlink()
        self.assertEqual(approved.percent_exact, '1')

    def test_app09_t016_t017_repeat_and_conflict_do_not_duplicate_authority(self):
        version = self._priced(policy=self._limit('percent_reduction'))
        approval = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='5',
            exclusive=True,
            precedence_rank=1,
        )
        approval.action_submit()
        self._approve(approval)
        self._approve(approval)
        self.assertEqual(self.env['cpla.discount.event'].search_count([
            ('approval_id', '=', approval.id),
            ('event_type', '=', 'approved'),
        ]), 1)
        rival = self._request(
            version,
            'additional_concession',
            concession_type='fixed_special_price',
            amount_exact='1100',
            exclusive=True,
            precedence_rank=0,
        )
        rival.action_submit()
        with self.assertRaises(UserError):
            self._approve(rival)
        self.assertEqual(rival.state, 'submitted')
        self.assertFalse(rival.approver_id)

    def test_app09_t018_events_follow_the_real_actor(self):
        version = self._priced(policy=self._limit('percent_reduction'))
        approval = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='5',
        )
        approval.action_submit()
        self._approve(approval)
        events = self.env['cpla.discount.event'].search([('approval_id', '=', approval.id)])
        actors = {event.event_type: event.actor_id for event in events}
        self.assertEqual(actors['submitted'], self.owner)
        self.assertEqual(actors['approved'], self.finance)
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.discount.event'].create({
                'approval_id': approval.id,
                'event_type': 'approved',
                'note': 'Forged',
            })

    def test_his09_t001_version_customer_only(self):
        version = self._priced(concessions=[{'type': 'percentage', 'percent': '5'}])
        own = self._eval(version)
        self.assertEqual(self._price(own), _dec(1140))
        other = self._eval(version, partner_id=self.other_partner.id)
        self.assertEqual(other['discount_status'], 'DISCOUNT_SCOPE_MISMATCH')

    def test_his09_t002_t003_branch_is_named_and_another_company_is_not(self):
        version = self._priced(concessions=[{
            'type': 'percentage',
            'percent': '5',
            'customer_scope': 'exact_partner',
            'partner': self.branch,
        }])
        covered = self._eval(version, partner_id=self.branch.id)
        self.assertEqual(self._price(covered), _dec(1140))
        parent = self._eval(version, partner_id=self.partner.id)
        self.assertEqual(parent['discount_status'], 'DISCOUNT_SCOPE_MISMATCH')
        denied = self._eval(version, partner_id=self.partner_b.id, company_id=self.company_b.id)
        self.assertEqual(denied['discount_status'], 'COMPANY_ACCESS_DENIED')
        self.assertFalse(denied['pre_discount_unit_price_exact'])
        self.assertFalse(denied['approved_adjusted_unit_price_exact'])

    def test_his09_t004_t005_variant_and_template_scope(self):
        version = self._priced(
            products=[(self.bearing, '1200'), (self.other_product, '800')],
            concessions=[{
                'type': 'percentage',
                'percent': '5',
                'product_scope': 'exact_variant',
                'variant': self.bearing,
            }],
        )
        matched = self._eval(version, product=self.bearing)
        self.assertEqual(self._price(matched), _dec(1140))
        other = self._eval(version, product=self.other_product)
        self.assertEqual(self._price(other), _dec(800))
        self.assertFalse(other['discount_applied'])
        template_version = self._priced(concessions=[{
            'type': 'percentage',
            'percent': '5',
            'product_scope': 'product_template',
            'template': self.bearing.product_tmpl_id,
        }])
        templated = self._eval(template_version)
        self.assertEqual(self._price(templated), _dec(1140))

    def test_his09_t006_quantity_bounds(self):
        version = self._priced(concessions=[{
            'type': 'percentage',
            'percent': '5',
            'minimum': '500',
            'maximum': '1000',
            'quantity_uom': self.unit,
        }])
        missing = self._eval(version)
        self.assertEqual(missing['discount_status'], 'DISCOUNT_EVIDENCE_REVIEW_REQUIRED')
        self.assertEqual(missing['discount_reason'], 'quantity_missing')
        low = self._eval(version, quantity='499', quantity_uom_id=self.unit.id)
        self.assertEqual(low['discount_status'], 'DISCOUNT_SCOPE_MISMATCH')
        qualified = self._eval(version, quantity='500', quantity_uom_id=self.unit.id)
        self.assertEqual(self._price(qualified), _dec(1140))
        ceiling = self._eval(version, quantity='1000', quantity_uom_id=self.unit.id)
        self.assertEqual(ceiling['discount_status'], 'DISCOUNT_SCOPE_MISMATCH')

    def test_his09_t007_and_t008_pricing_date_and_knowledge_cutoff(self):
        first = self._v1([(self.bearing, '1200')], self.company_a.currency_id)
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Dated concession.',
            'effective_from': self._today(),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        self._concession(amendment, {
            'type': 'percentage',
            'percent': '5',
            'start': self._on(-3),
        })
        amendment.action_submit_for_review()
        time.sleep(1.1)
        cutoff = fields.Datetime.now()
        time.sleep(1.1)
        record = self._env(self.finance, self.company_a)[
            'cpla.customer.contract.version'
        ].browse(amendment.id)
        record.action_approve()
        unknown = self._eval(record, knowledge_cutoff=cutoff)
        self.assertEqual(unknown['discount_status'], 'not_applicable')
        self.assertEqual(unknown['discount_reason'], 'version_not_known_at_cutoff')
        self.assertFalse(unknown['approved_adjusted_unit_price_exact'])
        known = self._eval(record, pricing_date=self._on(-3))
        self.assertEqual(self._price(known), _dec(1140))

    def test_his09_t011_revocation_keeps_the_original_amount(self):
        version = self._priced(
            concessions=[{
                'type': 'percentage',
                'percent': '5',
                'start': self._on(-10),
            }],
            policy={'retroactive_discount_authority': 'explicitly_allowed'},
        )
        concession = version.concession_ids
        with self.assertRaises(AccessError):
            self._env(self.finance, self.company_a)['cpla.discount.concession'].browse(
                concession.id
            ).action_revoke(self._today(), 'The approver cannot revoke.')
        self._env(self.finance2, self.company_a)['cpla.discount.concession'].browse(
            concession.id
        ).action_revoke(self._today(), 'Ends today. Earlier days stay authorized.')
        self.assertEqual(concession.percent_exact, '5')
        self.assertEqual(concession.revocation_state, 'revoked')
        today = self._eval(version)
        self.assertEqual(self._price(today), _dec(1200))
        self.assertFalse(today['discount_applied'])
        earlier = self._eval(version, pricing_date=self._on(-1))
        self.assertEqual(self._price(earlier), _dec(1140))

    def test_his09_t012_con09_t006_amendment_does_not_change_the_old_amount(self):
        old = self._priced(concessions=[{
            'type': 'percentage',
            'percent': '5',
            'start': self._on(-10),
        }])
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(old.id).create_amendment()
        amendment.write({
            'amendment_reason': 'A later percent. The previous snapshot stays.',
            'effective_from': self._on(1),
        })
        amendment.concession_ids.write({
            'percent_exact': '9',
            'effective_from': False,
        })
        amendment.action_submit_for_review()
        self._env(self.finance, self.company_a)['cpla.customer.contract.version'].browse(
            amendment.id
        ).action_approve()
        self.assertEqual(old.concession_ids.percent_exact, '5')
        self.assertEqual(amendment.concession_ids.percent_exact, '9')
        old.invalidate_recordset(['authority_to', 'effective_status'])
        historical = self._eval(old, pricing_date=self._on(-1))
        self.assertEqual(self._price(historical), _dec(1140))
        current = self._eval(amendment, pricing_date=self._on(1))
        self.assertEqual(self._price(current), _dec(1092))

    def test_his09_t013_a_pricelist_discount_is_not_contract_authority(self):
        pricelist = self.env['product.pricelist'].create({
            'name': 'Current commercial list',
            'currency_id': self.company_a.currency_id.id,
        })
        self.env['product.pricelist.item'].create({
            'pricelist_id': pricelist.id,
            'applied_on': '0_product_variant',
            'product_id': self.bearing.id,
            'compute_price': 'percentage',
            'percent_price': 50,
        })
        version = self._priced()
        result = self._eval(version)
        self.assertEqual(self._price(result), _dec(1200))
        self.assertFalse(result['discount_applied'])

    def test_his09_t014_t015_t016_snapshot_repeatability_and_conflict(self):
        version = self._priced(concessions=[{
            'type': 'percentage',
            'percent': '5',
            'evidence': 'AGR-KEEP',
        }])
        self.assertEqual(version.concession_ids.evidence_reference, 'AGR-KEEP')
        self.assertEqual(version.concession_ids.percent_exact, '5')
        first = self._eval(version, quantity='500')
        second = self._eval(version, quantity='500')
        self.assertEqual(first['approved_adjusted_unit_price_exact'], second['approved_adjusted_unit_price_exact'])
        self.assertEqual(first['calculation_stages'], second['calculation_stages'])
        self.assertEqual(self.env['cpla.discount.approval'].search_count([
            ('version_id', '=', version.id),
        ]), 0)
        conflict = self._priced(concessions=[
            {'type': 'fixed_special_price', 'amount': '1150', 'exclusive': True},
            {'type': 'fixed_special_price', 'amount': '1100', 'exclusive': True},
        ])
        result = self._eval(conflict)
        self.assertEqual(result['discount_status'], 'DISCOUNT_AUTHORITY_CONFLICT')
        self.assertFalse(result['approved_adjusted_unit_price_exact'])

    def test_ovr09_t001_t002_exposure_and_company(self):
        version = self._priced(
            concessions=[{'type': 'fixed_special_price', 'amount': '1150'}],
            policy=self._limit('stated_exposure'),
        )
        approval = self._request(
            version,
            proposed_price_exact='1100',
            quantity_exact='500',
            sale_reference='SO-OVR',
            sale_line_reference='SOL-OVR',
        )
        self.assertEqual(approval.company_id, self.company_a)
        approval.action_submit()
        approved = self._approve(approval)
        self.assertEqual(approved.baseline_unit_price_exact, '1150')
        self.assertEqual(approved.exposure_exact, '25000')
        applied = self._eval(
            version,
            sale_reference='SO-OVR',
            sale_line_reference='SOL-OVR',
            quantity='500',
        )
        self.assertEqual(applied['discount_status'], 'APPROVED_OVERRIDE_APPLICABLE')
        self.assertEqual(self._price(applied), _dec(1100))

    def test_ovr09_t004_t005_t006_wrong_scope_is_rejected(self):
        version = self._priced(policy=self._limit())
        wrong_customer = self._request(
            version,
            partner=self.other_partner,
            proposed_price_exact='1160',
            quantity_exact='10',
            sale_reference='SO-CUST',
            sale_line_reference='SOL-CUST',
        )
        with self.assertRaises(UserError):
            wrong_customer.action_submit()
        wrong_product = self._request(
            version,
            product=self.other_product,
            proposed_price_exact='1160',
            quantity_exact='10',
            sale_reference='SO-PROD',
            sale_line_reference='SOL-PROD',
        )
        with self.assertRaises(UserError):
            wrong_product.action_submit()
        missing_order = self._request(
            version,
            proposed_price_exact='1160',
            quantity_exact='10',
            sale_reference=False,
            sale_line_reference=False,
        )
        with self.assertRaises(UserError):
            missing_order.action_submit()

    def test_ovr09_t007_through_t011_quantity_dates_and_order_scope(self):
        version = self._priced(
            concessions=[{'type': 'fixed_special_price', 'amount': '1150'}],
            policy=self._limit(),
        )
        approval = self._request(
            version,
            proposed_price_exact='1100',
            quantity_exact='100',
            sale_reference='SO-LINE',
            sale_line_reference='SOL-LINE',
            effective_to=self._on(2),
        )
        approval.action_submit()
        self._approve(approval)
        larger = self._eval(
            version,
            sale_reference='SO-LINE',
            sale_line_reference='SOL-LINE',
            quantity='10000',
        )
        self.assertEqual(self._price(larger), _dec(1150))
        self.assertNotEqual(larger['discount_status'], 'APPROVED_OVERRIDE_APPLICABLE')
        other_order = self._eval(
            version,
            sale_reference='SO-OTHER',
            sale_line_reference='SOL-OTHER',
            quantity='100',
        )
        self.assertEqual(self._price(other_order), _dec(1150))
        self.assertEqual(other_order['discount_status'], 'SPECIAL_PRICE_APPLICABLE')
        expired = self._eval(
            version,
            sale_reference='SO-LINE',
            sale_line_reference='SOL-LINE',
            quantity='100',
            pricing_date=self._on(3),
        )
        self.assertEqual(self._price(expired), _dec(1150))
        pending = self._request(
            version,
            proposed_price_exact='1000',
            quantity_exact='100',
            sale_reference='SO-PEND',
            sale_line_reference='SOL-PEND',
        )
        pending.action_submit()
        waiting = self._eval(
            version,
            sale_reference='SO-PEND',
            sale_line_reference='SOL-PEND',
            quantity='100',
        )
        self.assertEqual(self._price(waiting), _dec(1150))
        self.assertNotEqual(waiting['approved_adjusted_unit_price_exact'], '1000')

    def test_ovr09_t012_t013_t014_evaluation_creates_nothing(self):
        version = self._priced(concessions=[{'type': 'percentage', 'percent': '5'}])
        approvals = self.env['cpla.discount.approval'].search_count([])
        moves = self.env['account.move'].search_count([]) if 'account.move' in self.env else None
        orders = self.env['sale.order'].search_count([]) if 'sale.order' in self.env else None
        self._eval(version, quantity='4', actual_unit_price_exact='1000')
        self._eval(version, quantity='4', actual_unit_price_exact='1000')
        self.assertEqual(self.env['cpla.discount.approval'].search_count([]), approvals)
        if moves is not None:
            self.assertEqual(self.env['account.move'].search_count([]), moves)
        if orders is not None:
            self.assertEqual(self.env['sale.order'].search_count([]), orders)
        self.assertEqual(version.line_ids.price_unit, 1200.0)

    def test_sec09_company_isolation_and_read_only_roles(self):
        version = self._priced(concessions=[{'type': 'fixed_special_price', 'amount': '1150'}])
        concession = version.concession_ids
        self.assertFalse(self._env(self.manager_b, self.company_b)['cpla.discount.concession'].search([
            ('id', '=', concession.id),
        ]))
        with self.assertRaises(AccessError):
            self._eval(version, user=self.manager_b)
        with self.assertRaises(AccessError):
            self._eval(version, user=self.sales)
        hidden = self._eval(version, company_id=self.company_b.id)
        self.assertEqual(hidden['discount_status'], 'COMPANY_ACCESS_DENIED')
        self.assertNotIn('1150', str(hidden))
        self.assertNotIn('1200', str(hidden))
        with self.assertRaises(AccessError):
            self._env(self.auditor, self.company_a)['cpla.discount.concession'].browse(
                concession.id
            ).write({'percent_exact': '1'})
        self.assertEqual(self.env['ir.model.access'].search_count([
            ('group_id', '=', self.env.ref('%s.group_app_admin' % MODULE).id),
        ]), 1)
        self.assertFalse(self.env['ir.model.access'].search([
            ('model_id.model', '=', 'cpla.discount.evaluator'),
        ]))
        finance_create = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'cpla.discount.approval'),
            ('group_id', '=', self.env.ref('%s.group_finance_manager' % MODULE).id),
        ])
        self.assertTrue(finance_create.perm_read)
        self.assertTrue(finance_create.perm_write)
        self.assertFalse(finance_create.perm_create)

    def test_sec09_attachment_export_and_forged_event(self):
        version = self._priced(policy=self._limit('percent_reduction'))
        approval = self._request(
            version,
            'additional_concession',
            concession_type='percentage',
            percent_exact='5',
        )
        attachment = self.env['ir.attachment'].create({
            'name': 'approval-note.txt',
            'res_model': 'cpla.discount.approval',
            'res_id': approval.id,
            'datas': 'bm90ZQ==',
            'company_id': self.company_a.id,
        })
        self.assertFalse(self._env(self.owner_b, self.company_b)['ir.attachment'].search([
            ('id', '=', attachment.id),
        ]))
        with self.assertRaises(UserError):
            self._env(self.auditor, self.company_a)['cpla.discount.approval'].browse(
                approval.id
            ).export_data(['percent_exact'])
        foreign = self._priced('100', company=self.company_b)
        both = self.env(user=self.both, context={
            **self.env.context,
            'allowed_company_ids': [self.company_a.id, self.company_b.id],
        })
        with self.assertRaises(UserError):
            both['cpla.discount.approval'].create({
                'company_id': self.company_a.id,
                'request_kind': 'additional_concession',
                'version_id': foreign.id,
                'partner_id': self.partner.id,
                'product_id': self.bearing.id,
                'concession_type': 'percentage',
                'percent_exact': '5',
                'reason': 'Cross company',
                'evidence_reference': 'X',
            })

    def test_int09_resolver_keeps_dev06_dev07_and_dev08(self):
        version = self._priced(concessions=[{'type': 'percentage', 'percent': '5'}])
        result = self._env(self.manager, self.company_a)['cpla.pricing.applicability'].resolve({
            'company_id': self.company_a.id,
            'partner_id': self.partner.id,
            'product_id': self.bearing.id,
            'pricing_date': self._today(),
            'quantity': 500,
        })
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['unit_price'], 1200.0)
        self.assertEqual(result['financial_status'], 'SAME_CURRENCY_NO_CONVERSION')
        self.assertEqual(_dec(result['comparable_unit_price_exact']), _dec(1200))
        self.assertEqual(result['discount_status'], 'AUTHORIZED_PRICE_RESOLVED')
        self.assertEqual(_dec(result['approved_adjusted_unit_price_exact']), _dec(1140))
        self.assertTrue(result['discount_applied'])
        self.assertFalse(result['leakage_amount'])
        self.assertFalse(result['is_recovered_cash'])
        plain = self._priced(partner=self.other_partner)
        untouched = self._env(self.manager, self.company_a)['cpla.pricing.applicability'].resolve({
            'company_id': self.company_a.id,
            'partner_id': self.other_partner.id,
            'product_id': self.bearing.id,
            'pricing_date': self._today(),
            'discount_rate': '0.05',
        })
        self.assertEqual(_dec(untouched['comparable_unit_price_exact']), _dec(1200))
        self.assertFalse(untouched['discount_applied'])
        self.assertEqual(untouched['discount_status'], 'NO_ADDITIONAL_DISCOUNT')
        wizard = self._env(self.manager, self.company_a)['cpla.pricing.applicability.check'].create({
            'company_id': self.company_a.id,
            'partner_id': self.partner.id,
            'product_id': self.bearing.id,
            'pricing_date': self._today(),
        })
        wizard.action_resolve()
        self.assertEqual(wizard.discount_status, 'AUTHORIZED_PRICE_RESOLVED')
        self.assertEqual(wizard.approved_adjusted_unit_price_exact, '1140')
        self.assertEqual(wizard.unit_price, 1200.0)
        self.assertEqual(plain.line_ids.price_unit, 1200.0)

    def test_con09_stale_superseded_request_is_not_approved(self):
        old = self._v1([(self.bearing, '1200')], self.company_a.currency_id)
        env = self._env(self.owner, self.company_a)
        amendment = env['cpla.customer.contract.version'].browse(old.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Current version replaces the previous authority.',
            'effective_from': self._today(),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        amendment.action_submit_for_review()
        self._env(self.finance, self.company_a)['cpla.customer.contract.version'].browse(
            amendment.id
        ).action_approve()
        stale = self._request(
            old,
            'additional_concession',
            concession_type='percentage',
            percent_exact='5',
        )
        stale.action_submit()
        old.invalidate_recordset(['effective_status', 'authority_to'])
        self.assertEqual(old.effective_status, 'superseded')
        with self.assertRaises(UserError):
            self._approve(stale)
        self.assertEqual(stale.state, 'submitted')
        self.assertFalse(stale.approver_id)
        self.assertFalse(self.env['cpla.discount.event'].search([
            ('approval_id', '=', stale.id),
            ('event_type', '=', 'approved'),
        ]))

    def test_reg09_views_manifest_and_no_audit_cron(self):
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])
        form = self.env['cpla.customer.contract.version'].get_view(view_type='form')
        check = self.env['cpla.pricing.applicability.check'].get_view(view_type='form')
        approval = self.env['cpla.discount.approval'].get_view(view_type='form')
        self.assertIn('Authorized Discounts', form['arch'])
        self.assertIn('apply a discount', form['arch'])
        self.assertIn('approved_adjusted_unit_price_exact', check['arch'])
        self.assertIn('Submit for Approval', approval['arch'])
        self.assertNotIn('Run Invoice Audit', form['arch'])
        for xmlid in (
            'menu_cpla_discount_approvals',
            'menu_cpla_price_overrides',
            'menu_cpla_discount_concessions',
        ):
            menu = self.env.ref('%s.%s' % (MODULE, xmlid))
            self.assertNotIn(menu.name, ('Invoice Audit', 'Recovery', 'Leakage Dashboard'))
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'ir.cron'),
        ]))
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'account.move'),
        ]))

    def test_dev09_repeated_evaluation_stays_under_the_ceiling(self):
        version = self._priced(concessions=[{'type': 'percentage', 'percent': '5'}])
        service = self._env(self.manager, self.company_a)['cpla.discount.evaluator']
        line = version.line_ids
        request = {
            'partner_id': version.partner_id.id,
            'product_id': line.product_id.id,
            'pricing_date': self._today(),
            'quantity': '500',
        }
        started = time.perf_counter()
        for _index in range(30):
            result = service.evaluate(line, dict(request))
        elapsed = time.perf_counter() - started
        _logger.info('DEV09 evaluate x30 elapsed %s', elapsed)
        self.assertEqual(_dec(result['approved_adjusted_unit_price_exact']), _dec(1140))
        self.assertLess(elapsed, 5.0)
        self.assertFalse(result['leakage_finding_created'])
