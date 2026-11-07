import os
import time
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'


@tagged('post_install', '-at_install')
class TestDev06PricingApplicability(TransactionCase):
    """Approved-contract selection. These tests do not calculate leakage."""

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
        cls.owner = cls._make_user('cpla06_owner', 'group_contract_user', cls.company_a)
        cls.other = cls._make_user('cpla06_other', 'group_contract_user', cls.company_a)
        cls.owner_b = cls._make_user('cpla06_owner_b', 'group_contract_user', cls.company_b)
        cls.manager = cls._make_user('cpla06_manager', 'group_contract_manager', cls.company_a)
        cls.manager_b = cls._make_user('cpla06_manager_b', 'group_contract_manager', cls.company_b)
        cls.finance = cls._make_user('cpla06_finance', 'group_finance_manager', cls.company_a)
        cls.finance_b = cls._make_user('cpla06_finance_b', 'group_finance_manager', cls.company_b)
        cls.reviewer = cls._make_user('cpla06_reviewer', 'group_finance_reviewer', cls.company_a)
        cls.auditor = cls._make_user('cpla06_auditor', 'group_internal_auditor', cls.company_a)
        cls.sales = cls._make_user('cpla06_sales', 'group_sales_pricing_reviewer', cls.company_a)
        cls.recovery = cls._make_user('cpla06_recovery', 'group_recovery_operator', cls.company_a)
        cls.admin = cls._make_user('cpla06_admin', 'group_app_admin', cls.company_a)
        cls.combined = cls._make_user(
            'cpla06_combined', 'group_contract_user', cls.company_a,
            extra_groups=('group_finance_reviewer', 'group_internal_auditor'),
        )
        cls.both = cls._make_user(
            'cpla06_both', 'group_contract_manager', cls.company_a,
            companies=cls.company_a | cls.company_b,
        )
        cls.policy_a = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_a.id,
            'change_reason': 'Candidate reference. Not an operational approval.',
            'pricing_date_policy': 'order_confirmation',
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
        cls.shared = cls.env['res.partner'].create({
            'name': 'Shared Buyer',
            'is_company': True,
            'company_id': False,
        })
        cls.branch = cls.env['res.partner'].create({
            'name': 'Branch B',
            'is_company': True,
            'parent_id': cls.partner.id,
            'company_id': cls.company_a.id,
        })
        cls.other_branch = cls.env['res.partner'].create({
            'name': 'Branch C',
            'is_company': True,
            'parent_id': cls.partner.id,
            'company_id': cls.company_a.id,
        })
        cls.bearing = cls.env['product.product'].create({
            'name': 'Bearing A',
            'list_price': 9999.0,
            'company_id': False,
        })
        cls.sibling = cls.env['product.product'].create({
            'name': 'Bearing Sibling',
            'list_price': 8888.0,
            'company_id': False,
        })
        attribute = cls.env['product.attribute'].create({
            'name': 'CPLA06 Size',
            'create_variant': 'always',
        })
        values = cls.env['product.attribute.value'].create([
            {'name': '10 mm', 'attribute_id': attribute.id},
            {'name': '20 mm', 'attribute_id': attribute.id},
        ])
        template = cls.env['product.template'].create({
            'name': 'Industrial Bearing',
            'company_id': False,
            'attribute_line_ids': [Command.create({
                'attribute_id': attribute.id,
                'value_ids': [Command.set(values.ids)],
            })],
        })
        by_size = {}
        for product in template.product_variant_ids:
            label = product.product_template_attribute_value_ids[:1].name
            by_size[label] = product
        cls.small = by_size['10 mm']
        cls.large = by_size['20 mm']
        cls.unit = cls.env.ref('uom.product_uom_unit')

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
        return fields.Date.context_today(self.env['cpla.pricing.applicability'])

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

    def _stamp(self, day):
        return fields.Date.to_string(day)

    def _staff(self, company):
        if company == self.company_a:
            return self.owner, self.manager, self.finance
        return self.owner_b, self.manager_b, self.finance_b

    def _policy(self, company):
        return self.policy_a if company == self.company_a else self.policy_b

    def _draft(self, partner, lines, company=None, owner=None, valid_from=None, valid_to=None):
        company = company or partner.company_id or self.company_a
        owner = owner or self._staff(company)[0]
        env = self._env(owner, company)
        contract = env['cpla.customer.contract'].create({
            'name': 'Negotiated supply',
            'company_id': company.id,
            'partner_id': partner.id,
            'owner_id': owner.id,
            'currency_id': company.currency_id.id,
            'valid_from': valid_from or self._on(-30),
            'valid_to': valid_to or self._on(180),
            'policy_id': self._policy(company).id,
        })
        for product, price in lines:
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
            'source_reference': 'AGR-006',
            'description': 'Signed pricing schedule.',
            'datas': 'c2lnbmVk',
        })
        return contract

    def _approve_initial(self, contract):
        _owner, manager, _finance = self._staff(contract.company_id)
        env = self._env(manager, contract.company_id)
        return env['cpla.customer.contract.version'].approve_initial(
            env['cpla.customer.contract'].browse(contract.id)
        )

    def _v1(self, partner=None, product=None, price=1000.0, company=None, **window):
        partner = partner or self.partner
        product = product or self.bearing
        company = company or partner.company_id or self.company_a
        contract = self._draft(
            partner, [(product, price)], company=company,
            valid_from=window.get('valid_from'), valid_to=window.get('valid_to'),
        )
        contract.action_submit_for_review()
        return self._approve_initial(contract)

    def _amend(self, version, price=1200.0, effective_days=1, approve=True):
        owner, _manager, finance = self._staff(version.company_id)
        env = self._env(owner, version.company_id)
        amendment = env['cpla.customer.contract.version'].browse(version.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Scheduled price change. Not a retroactive restatement.',
            'effective_from': self._on(effective_days),
        })
        amendment.line_ids.write({'price_unit': price})
        if not approve:
            return amendment
        env['cpla.customer.contract.version'].browse(amendment.id).action_submit_for_review()
        reviewer = self._env(finance, version.company_id)
        record = reviewer['cpla.customer.contract.version'].browse(amendment.id)
        record.action_approve()
        return record

    def _resolve(self, user, company, partner, product, **extra):
        payload = {
            'company_id': company.id,
            'partner_id': partner.id if partner else False,
            'product_id': product.id if product else False,
        }
        payload.update(extra)
        return self._env(user, company)['cpla.pricing.applicability'].resolve(payload)

    def _dated(self, user, company, partner, product, day, **extra):
        return self._resolve(
            user, company, partner, product, pricing_date=day, **extra,
        )

    def _assert_price_hidden(self, result, *prices):
        self.assertFalse(result['unit_price'])
        self.assertFalse(result['version_id'])
        self.assertFalse(result['leakage_amount'])
        text = result['explanation'] or ''
        # Contract references are allowed in the message. A reference such as
        # CPL/2026/01200 can contain the same digits as a hidden unit price.
        marker = 'Visible references:'
        if marker in text:
            text = text.split(marker, 1)[0]
        for price in prices:
            self.assertNotIn(str(price), text)

    def test_app_001_exact_customer_and_exact_variant(self):
        version = self._v1(price=1000.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['reason_code'], 'single_eligible_authority')
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['contract_id'], version.contract_id.id)
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertEqual(result['customer_scope'], 'exact_customer')
        self.assertEqual(result['product_specificity'], 'exact_variant')
        self.assertEqual(result['currency_id'], self.company_a.currency_id.id)
        self.assertEqual(result['uom_id'], self.bearing.uom_id.id)
        self.assertFalse(result['policy_operationally_approved'])
        self.assertFalse(result['leakage_amount'])
        self.assertFalse(result['is_recovered_cash'])
        self.assertIn(version.reference, result['explanation'])
        self.assertIn('not an invoice audit', result['explanation'].lower())

    def test_app_002_branch_is_not_covered_by_the_parent_contract(self):
        self._v1(price=1000.0)
        result = self._dated(self.manager, self.company_a, self.branch, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)

    def test_app_003_explicit_branch_coverage_cannot_be_approved(self):
        contract = self._draft(self.partner, [(self.bearing, 1000.0)])
        contract.write({'covered_partner_ids': [Command.set(self.branch.ids)]})
        with self.assertRaises(UserError):
            contract.action_submit_for_review()
        self.assertEqual(contract.state, 'draft')
        result = self._dated(self.manager, self.company_a, self.branch, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)
        unrelated = self._dated(
            self.manager, self.company_a, self.other_branch, self.bearing, self._today(),
        )
        self.assertEqual(unrelated['status'], 'NO_APPLICABLE_CONTRACT')

    def test_app_004_exact_customer_is_not_widened_by_a_group_reference(self):
        version = self._v1(price=1000.0)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._today(),
            customer_group_ref='GROUP-X',
        )
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['customer_scope'], 'exact_customer')
        self.assertEqual(result['precedence_policy_snapshot'], 'unconfigured')

    def test_app_005_template_price_is_not_invented_for_a_variant(self):
        self._v1(partner=self.partner, product=self.large, price=1200.0)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.small, self._today(),
            template_fallback_requested=True,
        )
        self.assertEqual(result['status'], 'POLICY_REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'product_template_scope_not_represented')
        self._assert_price_hidden(result, 1100, 1200)

    def test_app_006_day_before_the_next_effective_date_keeps_v1(self):
        """Today stands in for 30 June. A July amendment would be retroactive on this database."""
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertNotEqual(result['version_id'], second.id)
        self.assertEqual(result['authority_to'], self._stamp(self._today()))

    def test_app_007_the_next_effective_date_selects_v2(self):
        """Tomorrow stands in for 1 July. The boundary is inclusive on effective_from."""
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._on(1))
        self.assertEqual(result['version_id'], second.id)
        self.assertEqual(result['unit_price'], 1200.0)
        self.assertEqual(result['pricing_date'], self._stamp(self._on(1)))

    def test_app_008_confirmed_order_date_keeps_the_earlier_version(self):
        first = self._v1(price=1000.0)
        self._amend(first, price=1200.0, effective_days=1)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation',
            order_confirmed=True,
            order_confirmation_date=self._today(),
            invoice_date=self._on(1),
        )
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertTrue(result['grandfathering_applied'])
        self.assertEqual(result['pricing_date_rule'], 'order_confirmation')
        self.assertFalse(result['policy_operationally_approved'])

    def test_app_009_invoice_date_selects_the_later_version(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='invoice',
            order_confirmed=True,
            order_confirmation_date=self._today(),
            invoice_date=self._on(1),
        )
        self.assertEqual(result['version_id'], second.id)
        self.assertEqual(result['unit_price'], 1200.0)
        self.assertFalse(result['grandfathering_applied'])

    def test_app_010_quotation_date_is_not_a_confirmation_date(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        missing = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation',
            order_confirmed=False,
            quotation_date=self._on(-5),
            order_confirmation_date=self._on(1),
        )
        self.assertEqual(missing['status'], 'MISSING_CONTEXT')
        self.assertEqual(missing['reason_code'], 'order_not_confirmed')
        self._assert_price_hidden(missing, 1000, 1200)
        confirmed = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation',
            order_confirmed=True,
            quotation_date=self._on(-5),
            order_confirmation_date=self._on(1),
        )
        self.assertEqual(confirmed['version_id'], second.id)
        self.assertEqual(confirmed['pricing_date'], self._stamp(self._on(1)))

    def test_app_011_a_future_effective_version_is_not_used_early(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        self.assertEqual(second.state, 'approved')
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)

    def test_app_012_a_draft_amendment_is_excluded(self):
        first = self._v1(price=1000.0)
        draft = self._amend(first, price=900.0, effective_days=1, approve=False)
        self.assertEqual(draft.state, 'draft')
        today = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        tomorrow = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._on(1))
        self.assertEqual(today['version_id'], first.id)
        self.assertEqual(today['unit_price'], 1000.0)
        self.assertEqual(tomorrow['version_id'], first.id)
        self.assertNotEqual(tomorrow['unit_price'], 900.0)

    def test_app_013_knowledge_cutoff_hides_a_later_approval(self):
        first = self._v1(price=1000.0)
        time.sleep(1.1)
        second = self._amend(first, price=1200.0, effective_days=1)
        self.assertGreater(second.approved_at, first.approved_at)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._on(1),
            knowledge_cutoff=first.approved_at,
        )
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertEqual(result['authority_to'], self._stamp(first.valid_to))
        self.assertEqual(result['resolution_purpose'], 'historical')

    def test_app_014_retroactive_amendment_cannot_restate_history(self):
        first = self._v1(price=1000.0)
        owner, _manager, finance = self._staff(self.company_a)
        amendment = self._amend(first, price=1200.0, effective_days=1, approve=False)
        amendment.write({'effective_from': self._on(-1)})
        self._env(owner, self.company_a)['cpla.customer.contract.version'].browse(
            amendment.id
        ).action_submit_for_review()
        with self.assertRaises(UserError):
            self._env(finance, self.company_a)['cpla.customer.contract.version'].browse(
                amendment.id
            ).action_approve()
        self.assertNotEqual(amendment.state, 'approved')
        later_cutoff = fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(days=1)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._on(-1),
            knowledge_cutoff=later_cutoff,
        )
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)

    def test_app_015_two_equal_contracts_require_review(self):
        first = self._v1(price=1500.0)
        second = self._v1(price=500.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'CONFLICT_REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'equal_authority_conflict')
        self.assertFalse(result['version_id'])
        self.assertNotEqual(result['version_id'], first.id)
        self.assertNotEqual(result['version_id'], second.id)
        self._assert_price_hidden(result, 500, 1500)
        self.assertIn(first.reference, result['explanation'])
        self.assertIn(second.reference, result['explanation'])
        self.assertCountEqual(result['conflicting_version_ids'], [first.id, second.id])

    def test_app_016_missing_delivery_date_is_missing_context(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing, basis='delivery',
        )
        self.assertEqual(result['status'], 'MISSING_CONTEXT')
        self.assertEqual(result['reason_code'], 'delivery_missing')
        self._assert_price_hidden(result, 1000)

    def test_app_017_another_company_contract_is_not_selected(self):
        foreign = self._v1(
            partner=self.shared, product=self.bearing, price=1800.0, company=self.company_b,
        )
        result = self._dated(self.manager, self.company_a, self.shared, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1800)
        self.assertNotEqual(result['version_id'], foreign.id)

    def test_app_018_template_fallback_does_not_select_a_sibling_price(self):
        self._v1(partner=self.partner, product=self.large, price=1100.0)
        silent = self._dated(self.manager, self.company_a, self.partner, self.small, self._today())
        self.assertEqual(silent['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(silent, 1100)
        asked = self._dated(
            self.manager, self.company_a, self.partner, self.small, self._today(),
            template_fallback_requested=True,
        )
        self.assertEqual(asked['status'], 'POLICY_REVIEW_REQUIRED')
        self.assertEqual(asked['reason_code'], 'product_template_scope_not_represented')
        self._assert_price_hidden(asked, 1100)

    def test_app_019_current_parent_does_not_prove_historical_coverage(self):
        self._v1(price=1000.0)
        child = self.env['res.partner'].create({
            'name': 'Later Branch',
            'is_company': True,
            'company_id': self.company_a.id,
        })
        before = self._dated(
            self.manager, self.company_a, child, self.bearing, self._on(-10),
            customer_group_ref='GROUP-JULY',
        )
        self.assertEqual(before['status'], 'HISTORICAL_EVIDENCE_REVIEW_REQUIRED')
        self.assertEqual(before['reason_code'], 'customer_group_not_approved')
        child.write({'parent_id': self.partner.id})
        after = self._dated(
            self.manager, self.company_a, child, self.bearing, self._on(-10),
            customer_group_ref='GROUP-JULY',
        )
        self.assertEqual(after['status'], 'HISTORICAL_EVIDENCE_REVIEW_REQUIRED')
        self._assert_price_hidden(after, 1000)

    def test_app_020_two_delivery_dates_are_not_collapsed(self):
        self._v1(price=1000.0)
        self._amend(self.env['cpla.customer.contract.version'].search([
            ('partner_id', '=', self.partner.id),
            ('state', '=', 'approved'),
        ], limit=1), price=1200.0, effective_days=1)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='delivery',
            delivery_dates=[self._today(), self._on(1)],
            quantity=100,
        )
        self.assertEqual(result['status'], 'PARTITION_REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'delivery_allocation_required')
        self._assert_price_hidden(result, 1000, 1200)
        self.assertEqual(result['tier_status'], 'not_applicable')

    def test_cus06_t001_exact_customer_matches(self):
        version = self._v1(price=1000.0)
        result = self._dated(self.owner, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['partner_id'], self.partner.id)

    def test_cus06_t002_unrelated_customer_does_not_match(self):
        self._v1(price=1000.0)
        result = self._dated(
            self.manager, self.company_a, self.other_partner, self.bearing, self._today(),
        )
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)

    def test_cus06_t003_contract_on_the_branch_matches_that_branch(self):
        version = self._v1(partner=self.branch, price=1000.0)
        result = self._dated(self.manager, self.company_a, self.branch, self.bearing, self._today())
        self.assertEqual(result['version_id'], version.id)
        parent = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(parent['status'], 'NO_APPLICABLE_CONTRACT')

    def test_cus06_t004_parent_coverage_of_a_branch_is_not_approved(self):
        self._v1(price=1000.0)
        result = self._dated(self.manager, self.company_a, self.branch, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self.assertNotEqual(result['customer_scope'], 'covered_branch')
        self._assert_price_hidden(result, 1000)

    def test_cus06_t005_unrelated_branch_is_rejected(self):
        self._v1(partner=self.branch, price=1000.0)
        result = self._dated(
            self.manager, self.company_a, self.other_branch, self.bearing, self._today(),
        )
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)

    def test_cus06_t006_group_reference_does_not_replace_an_exact_match(self):
        version = self._v1(price=1000.0)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._today(),
            customer_group_ref='GROUP-X',
        )
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['customer_scope'], 'exact_customer')

    def test_cus06_t007_unknown_group_membership_is_review(self):
        result = self._dated(
            self.manager, self.company_a, self.other_partner, self.bearing, self._today(),
            customer_group_ref='GROUP-OTHER',
        )
        self.assertEqual(result['status'], 'HISTORICAL_EVIDENCE_REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'customer_group_not_approved')
        self._assert_price_hidden(result, 1000)

    def test_cus06_t008_group_reference_is_not_backdated(self):
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._on(-10),
            customer_group_ref='GROUP-JULY',
        )
        self.assertEqual(result['status'], 'HISTORICAL_EVIDENCE_REVIEW_REQUIRED')
        self._assert_price_hidden(result)

    def test_cus06_t009_current_parent_hierarchy_is_not_historical_coverage(self):
        self._v1(price=1000.0)
        self.branch.write({'parent_id': False})
        self.branch.write({'parent_id': self.partner.id})
        result = self._dated(self.manager, self.company_a, self.branch, self.bearing, self._on(-10))
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)

    def test_cus06_t010_shared_customer_does_not_cross_companies(self):
        self._v1(partner=self.shared, product=self.bearing, price=1800.0, company=self.company_b)
        result = self._dated(self.manager, self.company_a, self.shared, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1800)

    def test_cus06_t011_exact_customer_does_not_use_group_precedence(self):
        version = self._v1(price=1000.0)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._today(),
            customer_group_ref='GROUP-X',
        )
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['precedence_rule'], 'single_eligible_authority')
        self.assertEqual(result['precedence_policy_snapshot'], 'unconfigured')

    def test_cus06_t012_two_customer_contracts_conflict(self):
        self._v1(price=1000.0)
        self._v1(price=1300.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'CONFLICT_REVIEW_REQUIRED')
        self._assert_price_hidden(result, 1000, 1300)

    def test_prd06_t001_exact_variant_matches(self):
        version = self._v1(product=self.large, price=1200.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.large, self._today())
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['product_specificity'], 'exact_variant')
        self.assertEqual(result['unit_price'], 1200.0)

    def test_prd06_t002_sibling_variant_does_not_match(self):
        self._v1(product=self.large, price=1200.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.small, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1200)

    def test_prd06_t003_template_scope_is_not_a_stored_price(self):
        """No template-level price exists. A sibling price is not applied."""
        self._v1(product=self.large, price=1100.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.small, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self.assertNotEqual(result['product_specificity'], 'product_template')
        self._assert_price_hidden(result, 1100)

    def test_prd06_t004_exact_variant_is_not_copied_to_a_sibling(self):
        version = self._v1(product=self.large, price=1200.0)
        exact = self._dated(self.manager, self.company_a, self.partner, self.large, self._today())
        sibling = self._dated(self.manager, self.company_a, self.partner, self.small, self._today())
        self.assertEqual(exact['version_id'], version.id)
        self.assertEqual(sibling['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(sibling, 1200)

    def test_prd06_t005_two_exact_variant_contracts_conflict(self):
        self._v1(product=self.large, price=1100.0)
        self._v1(product=self.large, price=1200.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.large, self._today())
        self.assertEqual(result['status'], 'CONFLICT_REVIEW_REQUIRED')
        self._assert_price_hidden(result, 1100, 1200)

    def test_prd06_t006_archived_product_keeps_its_approved_identity(self):
        version = self._v1(price=1000.0)
        self.bearing.active = False
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['product_id'], self.bearing.id)
        self.assertEqual(result['unit_price'], 1000.0)

    def test_prd06_t007_other_company_product_is_rejected(self):
        private = self.env['product.product'].create({
            'name': 'UAE Bearing',
            'list_price': 1800.0,
            'company_id': self.company_b.id,
        })
        with self.assertRaises(AccessError) as caught:
            self._dated(self.manager, self.company_a, self.partner, private, self._today())
        self.assertNotIn('1800', str(caught.exception))

    def test_prd06_t008_product_category_is_not_a_pricing_scope(self):
        category = self.env['product.category'].create({'name': 'CPLA06 Category'})
        result = self._resolve(
            self.manager, self.company_a, self.partner, None,
            category_id=category.id,
            pricing_date=self._today(),
        )
        self.assertEqual(result['status'], 'POLICY_REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'product_category_not_supported')
        self._assert_price_hidden(result)

    def test_prd06_t009_each_variant_line_is_selected_on_its_own(self):
        contract = self._draft(self.partner, [(self.large, 1200.0), (self.small, 900.0)])
        contract.action_submit_for_review()
        version = self._approve_initial(contract)
        large = self._dated(self.manager, self.company_a, self.partner, self.large, self._today())
        small = self._dated(self.manager, self.company_a, self.partner, self.small, self._today())
        self.assertEqual(large['version_id'], version.id)
        self.assertEqual(large['unit_price'], 1200.0)
        self.assertEqual(small['version_id'], version.id)
        self.assertEqual(small['unit_price'], 900.0)
        self.assertEqual(large['status'], 'MATCHED_AUTHORITATIVE')

    def test_prd06_t010_quantity_does_not_create_a_tier_conflict(self):
        version = self._v1(price=1000.0)
        pack = self.env['uom.uom'].create({
            'name': 'CPLA06 Pack of 6',
            'relative_uom_id': self.unit.id,
            'relative_factor': 6.0,
        })
        contract = self._draft(self.other_partner, [(self.bearing, 1000.0)])
        contract.line_ids.write({'uom_id': pack.id})
        with self.assertRaises(UserError):
            contract.action_submit_for_review()
        self.assertEqual(contract.state, 'draft')
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._today(),
            quantity=40,
        )
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['tier_status'], 'base_price_applicable')
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertNotEqual(result['unit_price'], 40000.0)
        self.assertIn('not a qualified tier price', result['explanation'])
        self.assertFalse(result['leakage_amount'])

    def test_dat06_t001_sales_order_confirmation_date_is_used(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation',
            order_confirmed=True,
            order_confirmation_date=self._today(),
        )
        self.assertEqual(result['pricing_date'], self._stamp(self._today()))
        self.assertEqual(result['pricing_date_rule'], 'order_confirmation')
        self.assertEqual(result['basis_source'], 'request')

    def test_dat06_t002_draft_quotation_date_is_not_substituted(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation',
            order_confirmed=False,
            quotation_date=self._on(-5),
        )
        self.assertEqual(result['status'], 'MISSING_CONTEXT')
        self.assertEqual(result['reason_code'], 'order_not_confirmed')
        self.assertFalse(result['pricing_date'])
        self.assertNotIn(self._stamp(self._on(-5)), result['explanation'])

    def test_dat06_t003_invoice_date_is_used_when_requested(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='invoice', invoice_date=self._on(1),
        )
        self.assertEqual(result['version_id'], second.id)
        self.assertEqual(result['pricing_date_rule'], 'invoice')
        self.assertEqual(result['pricing_date'], self._stamp(self._on(1)))

    def test_dat06_t004_one_delivery_date_is_used_when_requested(self):
        version = self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='delivery', delivery_dates=[self._today()],
        )
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['pricing_date_rule'], 'delivery')

    def test_dat06_t005_a_required_date_is_not_replaced_with_today(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing, basis='invoice',
        )
        self.assertEqual(result['status'], 'MISSING_CONTEXT')
        self.assertEqual(result['reason_code'], 'invoice_date_missing')
        self.assertFalse(result['pricing_date'])
        self._assert_price_hidden(result, 1000)

    def test_dat06_t006_inclusive_start_of_v1_period(self):
        first = self._v1(price=1000.0)
        self._amend(first, price=1200.0, effective_days=1)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['unit_price'], 1000.0)

    def test_dat06_t007_inclusive_start_of_v2_period(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, second.effective_from)
        self.assertEqual(result['version_id'], second.id)

    def test_dat06_t008_future_effective_version_stays_inactive(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=14)
        self.assertEqual(second.state, 'approved')
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['version_id'], first.id)

    def test_dat06_t009_expired_contract_is_excluded(self):
        self._v1(price=1000.0, valid_from=self._on(-30), valid_to=self._on(-1))
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)

    def test_dat06_t010_cutoff_before_approval_finds_nothing(self):
        self._v1(price=1000.0)
        cutoff = fields.Datetime.to_datetime(fields.Datetime.now()) - timedelta(days=1)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._today(),
            knowledge_cutoff=cutoff,
        )
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)

    def test_dat06_t011_as_known_cutoff_keeps_v1(self):
        first = self._v1(price=1000.0)
        time.sleep(1.1)
        second = self._amend(first, price=1200.0, effective_days=1)
        self.assertGreater(second.approved_at, first.approved_at)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._on(1),
            knowledge_cutoff=first.approved_at,
        )
        self.assertEqual(result['version_id'], first.id)
        self.assertNotIn(str(second.line_ids.price_unit), result['explanation'])

    def test_dat06_t012_unauthorized_retroactive_version_is_not_restated(self):
        first = self._v1(price=1000.0)
        amendment = self._amend(first, price=900.0, effective_days=1, approve=False)
        amendment.write({'effective_from': self._on(-1)})
        self._env(self.owner, self.company_a)['cpla.customer.contract.version'].browse(
            amendment.id
        ).action_submit_for_review()
        with self.assertRaises(UserError):
            self._env(self.finance, self.company_a)['cpla.customer.contract.version'].browse(
                amendment.id
            ).action_approve()
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._today(),
            knowledge_cutoff=fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(days=2),
        )
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)

    def test_dat06_t013_snapshots_do_not_pick_different_dates(self):
        first = self._v1(price=1000.0)
        self.policy_a.write({
            'pricing_date_policy': 'invoice',
            'change_reason': 'Candidate change. Not an operational approval.',
        })
        second_contract = self._v1(price=1300.0)
        self.assertEqual(first.pricing_date_policy_snapshot, 'order_confirmation')
        self.assertEqual(second_contract.pricing_date_policy_snapshot, 'invoice')
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'CONFLICT_REVIEW_REQUIRED')
        self._assert_price_hidden(result, 1000, 1300)

    def test_dat06_t014_multiple_delivery_dates_stay_unpartitioned(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='delivery',
            delivery_dates=[self._today(), self._on(1)],
        )
        self.assertEqual(result['status'], 'PARTITION_REVIEW_REQUIRED')
        self.assertFalse(result['version_id'])

    def test_dat06_t015_calendar_dates_change_on_the_effective_day(self):
        """Commercial dates are calendar dates. Midnight is not a second boundary."""
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        before = self._dated(
            self.manager, self.company_a, self.partner, self.bearing,
            fields.Date.add(second.effective_from, days=-1),
        )
        on_day = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, second.effective_from,
        )
        self.assertEqual(before['version_id'], first.id)
        self.assertEqual(on_day['version_id'], second.id)

    def test_dat06_t016_supersession_follows_effective_dates(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        self.assertEqual(second.supersedes_version_id, first)
        self.assertGreater(second.version_number, first.version_number)
        early = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        later = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._on(1))
        self.assertEqual(early['version_id'], first.id)
        self.assertEqual(later['version_id'], second.id)

    def test_gfd06_t001_pre_increase_confirmation_keeps_v1(self):
        first = self._v1(price=1000.0)
        self._amend(first, price=1200.0, effective_days=1)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(), invoice_date=self._on(1),
        )
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertTrue(result['grandfathering_applied'])

    def test_gfd06_t002_confirmation_on_the_increase_date_uses_v2(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(), invoice_date=self._on(1),
        )
        self.assertEqual(result['version_id'], second.id)
        self.assertEqual(result['unit_price'], 1200.0)
        self.assertFalse(result['grandfathering_applied'])

    def test_gfd06_t003_unconfirmed_quotation_does_not_lock_a_price(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=False,
            quotation_date=self._today(),
        )
        self.assertEqual(result['status'], 'MISSING_CONTEXT')
        self.assertEqual(result['reason_code'], 'order_not_confirmed')
        self.assertFalse(result['grandfathering_applied'])

    def test_gfd06_t004_missing_confirmation_date_is_review(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
        )
        self.assertEqual(result['status'], 'MISSING_CONTEXT')
        self.assertEqual(result['reason_code'], 'pricing_date_missing')
        self._assert_price_hidden(result, 1000)

    def test_gfd06_t005_grandfathering_does_not_cross_products(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.sibling,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(), invoice_date=self._on(1),
        )
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)

    def test_gfd06_t006_a_caller_time_limit_is_not_approved(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(), invoice_date=self._on(1),
            grandfather_limit=30,
        )
        self.assertEqual(result['status'], 'POLICY_REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'grandfather_limit_not_approved')
        self._assert_price_hidden(result, 1000)

    def test_gfd06_t007_later_invoice_context_keeps_the_order_date(self):
        first = self._v1(price=1000.0)
        self._amend(first, price=1200.0, effective_days=1)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(), invoice_date=self._on(1),
            quantity=40,
        )
        self.assertEqual(result['version_id'], first.id)
        self.assertTrue(result['grandfathering_applied'])
        self.assertEqual(result['tier_status'], 'base_price_applicable')
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertFalse(result['leakage_amount'])

    def test_gfd06_t008_another_customer_does_not_inherit_the_lock(self):
        self._v1(price=1000.0)
        result = self._resolve(
            self.manager, self.company_a, self.other_partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(), invoice_date=self._on(1),
        )
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self.assertFalse(result['grandfathering_applied'])
        self._assert_price_hidden(result, 1000)

    def test_gfd06_t009_request_basis_is_not_replaced_by_the_snapshot(self):
        version = self._v1(price=1000.0)
        self.policy_a.write({
            'pricing_date_policy': 'invoice',
            'change_reason': 'Candidate change. Not an operational approval.',
        })
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(),
        )
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['pricing_date_policy_snapshot'], 'order_confirmation')
        self.assertEqual(self.policy_a.pricing_date_policy, 'invoice')
        self.assertFalse(result['policy_operationally_approved'])

    def test_gfd06_t010_selection_does_not_calculate_leakage(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        before = self.env['account.move'].search_count([]) if 'account.move' in self.env.registry else None
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(), invoice_date=self._on(1),
            quantity=500,
        )
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertFalse(result['leakage_amount'])
        self.assertFalse(result['is_recovered_cash'])
        self.assertNotIn('25000', result['explanation'])
        self.assertNotIn('760', result['explanation'])
        if before is not None:
            self.assertEqual(self.env['account.move'].search_count([]), before)
        self.assertEqual(second.line_ids.price_unit, 1200.0)

    def test_pre06_t001_one_eligible_authority_is_selected(self):
        version = self._v1(price=1000.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertEqual(result['version_id'], version.id)

    def test_pre06_t002_ineligible_customer_is_excluded(self):
        self._v1(price=1000.0)
        result = self._dated(
            self.manager, self.company_a, self.other_partner, self.bearing, self._today(),
        )
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')

    def test_pre06_t003_group_reference_does_not_invent_precedence(self):
        version = self._v1(price=1000.0)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._today(),
            customer_group_ref='GROUP-X',
        )
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['precedence_rule'], 'single_eligible_authority')

    def test_pre06_t004_variant_authority_stays_on_that_variant(self):
        version = self._v1(product=self.large, price=1200.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.large, self._today())
        self.assertEqual(result['version_id'], version.id)
        other = self._dated(self.manager, self.company_a, self.partner, self.small, self._today())
        self.assertNotEqual(other['version_id'], version.id)

    def test_pre06_t005_later_effective_version_is_selected_on_its_date(self):
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._on(1))
        self.assertEqual(result['version_id'], second.id)
        self.assertGreater(second.version_number, first.version_number)

    def test_pre06_t006_database_id_does_not_choose_the_winner(self):
        first = self._v1(price=1500.0)
        second = self._v1(price=500.0)
        self.assertLess(first.id, second.id)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertFalse(result['version_id'])
        self.assertNotEqual(result['unit_price'], 1500.0)
        self.assertNotEqual(result['unit_price'], 500.0)

    def test_pre06_t007_price_does_not_break_the_tie(self):
        self._v1(price=1500.0)
        self._v1(price=500.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'CONFLICT_REVIEW_REQUIRED')
        self.assertFalse(result['unit_price'])

    def test_pre06_t008_equal_priority_is_a_conflict(self):
        self._v1(price=1000.0)
        self._v1(price=1000.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['reason_code'], 'equal_authority_conflict')
        self.assertEqual(len(result['conflicting_version_ids']), 2)

    def test_pre06_t009_template_and_variant_are_not_ranked(self):
        self._v1(product=self.large, price=1200.0)
        result = self._dated(
            self.manager, self.company_a, self.partner, self.small, self._today(),
            template_fallback_requested=True,
        )
        self.assertEqual(result['status'], 'POLICY_REVIEW_REQUIRED')
        self.assertEqual(result['reason_code'], 'product_template_scope_not_represented')
        self._assert_price_hidden(result, 1200)

    def test_pre06_t010_unconfigured_precedence_does_not_choose(self):
        self._v1(price=1000.0)
        self._v1(price=1100.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'CONFLICT_REVIEW_REQUIRED')
        self.assertEqual(self.policy_a.contract_precedence_policy, 'unconfigured')
        self._assert_price_hidden(result, 1000, 1100)

    def test_pre06_t011_duplicate_approved_authority_conflicts(self):
        self._v1(price=1000.0)
        self._v1(price=1250.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'CONFLICT_REVIEW_REQUIRED')
        self.assertFalse(result['version_id'])

    def test_pre06_t012_rejected_version_is_excluded(self):
        first = self._v1(price=1000.0)
        amendment = self._amend(first, price=900.0, effective_days=1, approve=False)
        self._env(self.owner, self.company_a)['cpla.customer.contract.version'].browse(
            amendment.id
        ).action_submit_for_review()
        reviewer = self._env(self.finance, self.company_a)
        record = reviewer['cpla.customer.contract.version'].browse(amendment.id)
        record.write({'rejection_reason': 'The proposed price is not accepted.'})
        record.action_reject()
        self.assertEqual(record.state, 'rejected')
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._on(1))
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)

    def test_pre06_t013_draft_amendment_is_excluded(self):
        first = self._v1(price=1000.0)
        self._amend(first, price=900.0, effective_days=1, approve=False)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._on(1))
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)

    def test_pre06_t014_repeated_calls_return_the_same_authority(self):
        version = self._v1(price=1000.0)
        first = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        second = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(first, second)
        self.assertEqual(first['version_id'], version.id)

    def test_pre06_t015_authorized_conflict_explanation_names_references(self):
        first = self._v1(price=1000.0)
        second = self._v1(price=1400.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertIn(first.reference, result['explanation'])
        self.assertIn(second.reference, result['explanation'])
        self.assertNotIn('1000', result['explanation'])
        self.assertNotIn('1400', result['explanation'])

    def test_pre06_t016_non_owner_does_not_receive_the_price(self):
        self._v1(price=4242.0)
        result = self._dated(self.other, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 4242)
        with self.assertRaises(AccessError):
            self._dated(self.sales, self.company_a, self.partner, self.bearing, self._today())

    def test_sec06_t001_company_user_resolves_an_authorized_contract(self):
        version = self._v1(price=1000.0)
        result = self._dated(self.owner, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['company_id'], self.company_a.id)

    def test_sec06_t002_company_user_cannot_read_the_other_company(self):
        foreign = self._v1(
            partner=self.partner_b, product=self.bearing, price=1800.0, company=self.company_b,
        )
        self.assertFalse(self._env(self.manager, self.company_a)[
            'cpla.customer.contract.version'
        ].search([('id', '=', foreign.id)]))
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertNotEqual(result['version_id'], foreign.id)
        self._assert_price_hidden(result, 1800)

    def test_sec06_t003_wrong_company_context_is_rejected(self):
        self._v1(partner=self.partner_b, product=self.bearing, price=1800.0, company=self.company_b)
        with self.assertRaises(AccessError) as caught:
            self._env(self.manager, self.company_a)['cpla.pricing.applicability'].resolve({
                'company_id': self.company_b.id,
                'partner_id': self.partner_b.id,
                'product_id': self.bearing.id,
                'pricing_date': self._today(),
            })
        self.assertNotIn('1800', str(caught.exception))

    def test_sec06_t004_direct_call_enforces_the_role(self):
        for user in (self.sales, self.recovery, self.admin):
            with self.assertRaises(AccessError):
                self._dated(user, self.company_a, self.partner, self.bearing, self._today())

    def test_sec06_t005_supplied_ids_are_validated(self):
        version = self._v1(price=1000.0)
        missing = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            product_id=False, pricing_date=self._today(),
        )
        self.assertEqual(missing['status'], 'MISSING_CONTEXT')
        self.assertEqual(missing['reason_code'], 'product_missing')
        with self.assertRaises(AccessError):
            self._resolve(
                self.manager, self.company_a, self.partner, self.bearing,
                product_id=999999999, pricing_date=self._today(),
            )
        ignored = self._dated(
            self.manager, self.company_a, self.partner, self.bearing, self._today(),
            version_id=version.id + 99, unit_price=1.0,
        )
        self.assertEqual(ignored['version_id'], version.id)
        self.assertEqual(ignored['unit_price'], 1000.0)

    def test_sec06_t006_non_owner_cannot_inspect_the_price(self):
        version = self._v1(price=4242.0)
        result = self._dated(self.other, self.company_a, self.partner, self.bearing, self._today())
        self._assert_price_hidden(result, 4242)
        with self.assertRaises(AccessError):
            self._env(self.other, self.company_a)[
                'cpla.customer.contract.version.line'
            ].browse(version.line_ids.id).read(['price_unit'])

    def test_sec06_t007_resolver_source_has_no_unrestricted_elevation(self):
        path = os.path.join(
            Manifest.for_addon(MODULE).path, 'models', 'pricing_applicability.py',
        )
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
        self.assertNotIn('sudo(', text)
        self.assertNotIn('.execute(', text)
        version = self._v1(price=1000.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['version_id'], version.id)
        self.assertFalse(self._env(self.manager, self.company_a).su)

    def test_sec06_t008_shared_customer_does_not_leak_the_other_price(self):
        self._v1(partner=self.shared, product=self.bearing, price=1800.0, company=self.company_b)
        result = self._dated(self.owner, self.company_a, self.shared, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1800)

    def test_sec06_t009_multi_company_user_keeps_company_scope(self):
        local = self._v1(partner=self.shared, product=self.bearing, price=1000.0, company=self.company_a)
        foreign = self._v1(
            partner=self.shared, product=self.bearing, price=1800.0, company=self.company_b,
        )
        env = self.env(user=self.both, context={
            **self.env.context,
            'allowed_company_ids': [self.company_a.id, self.company_b.id],
        })
        result = env['cpla.pricing.applicability'].resolve({
            'company_id': self.company_a.id,
            'partner_id': self.shared.id,
            'product_id': self.bearing.id,
            'pricing_date': self._today(),
        })
        self.assertEqual(result['version_id'], local.id)
        self.assertNotEqual(result['version_id'], foreign.id)
        self.assertEqual(result['unit_price'], 1000.0)
        private = self.env['product.product'].create({
            'name': 'Company B only',
            'company_id': self.company_b.id,
            'list_price': 1800.0,
        })
        with self.assertRaises(UserError) as caught:
            env['cpla.pricing.applicability'].resolve({
                'company_id': self.company_a.id,
                'partner_id': self.shared.id,
                'product_id': private.id,
                'pricing_date': self._today(),
            })
        self.assertNotIn('1800', str(caught.exception))

    def test_sec06_t010_wizard_enforces_server_permissions(self):
        version = self._v1(price=1000.0)
        with self.assertRaises(AccessError):
            self._env(self.sales, self.company_a)['cpla.pricing.applicability.check'].create({
                'company_id': self.company_a.id,
                'partner_id': self.partner.id,
                'product_id': self.bearing.id,
            })
        wizard = self._env(self.owner, self.company_a)['cpla.pricing.applicability.check'].create({
            'company_id': self.company_a.id,
            'partner_id': self.partner.id,
            'product_id': self.bearing.id,
            'pricing_date': self._today(),
        })
        self.assertTrue(wizard.action_resolve())
        self.assertEqual(wizard.status, 'MATCHED_AUTHORITATIVE')
        self.assertEqual(wizard.version_id, version)
        self.assertEqual(wizard.unit_price, 1000.0)
        hidden = self._env(self.other, self.company_a)['cpla.pricing.applicability.check'].search([
            ('id', '=', wizard.id),
        ])
        self.assertFalse(hidden)
        form = self._env(self.manager, self.company_a)[
            'cpla.pricing.applicability.check'
        ].get_view(view_type='form')
        self.assertIn('action_resolve', form['arch'])
        self.assertIn('not an approved price', form['arch'])
        self.assertNotIn('Run Invoice Audit', form['arch'])
        menu = self.env.ref('%s.menu_cpla_pricing_applicability' % MODULE)
        self.assertIn(menu, self.env.ref('%s.group_contract_user' % MODULE).menu_access)
        self.assertNotIn(menu, self.env.ref('%s.group_app_admin' % MODULE).menu_access)
        self.assertNotIn(menu, self.env.ref('%s.group_sales_pricing_reviewer' % MODULE).menu_access)

    def test_sec06_t011_export_and_read_group_hide_the_other_company(self):
        foreign = self._v1(
            partner=self.partner_b, product=self.bearing, price=1800.0, company=self.company_b,
        )
        outsider = self._env(self.manager, self.company_a)
        grouped = outsider['cpla.customer.contract.version.line'].read_group(
            [('company_id', '=', self.company_b.id)],
            ['price_unit:sum'],
            ['company_id'],
        )
        self.assertFalse(grouped)
        with self.assertRaises(UserError) as caught:
            outsider['cpla.customer.contract.version.line'].browse(
                foreign.line_ids.id
            ).export_data(['price_unit'])
        self.assertNotIn('1800', str(caught.exception))
        with self.assertRaises(AccessError):
            self._env(self.sales, self.company_a)[
                'cpla.customer.contract.version.line'
            ].read_group([], ['price_unit:sum'], ['company_id'])

    def test_sec06_t012_combined_roles_stay_owner_limited(self):
        self._v1(price=4242.0)
        result = self._dated(self.combined, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 4242)

    def test_sec06_t013_request_company_must_be_allowed(self):
        with self.assertRaises(AccessError) as caught:
            self._env(self.manager, self.company_a)['cpla.pricing.applicability'].resolve({
                'company_id': self.company_b.id,
                'partner_id': self.partner.id,
                'product_id': self.bearing.id,
                'pricing_date': self._today(),
            })
        self.assertNotIn('price', str(caught.exception).lower())

    def test_sec06_t014_approval_history_follows_the_same_scope(self):
        version = self._v1(price=1000.0)
        auditor_events = self._env(self.auditor, self.company_a)[
            'cpla.customer.contract.version.event'
        ].search([('version_id', '=', version.id)])
        self.assertTrue(auditor_events)
        self.assertFalse(self._env(self.other, self.company_a)[
            'cpla.customer.contract.version.event'
        ].search([('version_id', '=', version.id)]))
        self.assertFalse(self._env(self.manager, self.company_a)[
            'cpla.customer.contract.version.event'
        ].search([('version_id.company_id', '=', self.company_b.id)]))

    def test_sec06_t015_allowed_company_context_does_not_broaden_the_request(self):
        foreign = self._v1(
            partner=self.shared, product=self.bearing, price=1800.0, company=self.company_b,
        )
        result = self._dated(self.manager, self.company_a, self.shared, self.bearing, self._today())
        self.assertNotEqual(result['version_id'], foreign.id)
        self._assert_price_hidden(result, 1800)

    def test_det06_t001_identical_inputs_return_identical_results(self):
        self._v1(price=1000.0)
        first = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        second = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(first, second)

    def test_det06_t002_creation_order_does_not_choose_an_authority(self):
        low_id = self._v1(price=1700.0)
        high_id = self._v1(price=400.0)
        self.assertLess(low_id.id, high_id.id)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertFalse(result['version_id'])
        self.assertFalse(result['unit_price'])

    def test_det06_t003_list_price_change_does_not_change_the_version(self):
        version = self._v1(price=1000.0)
        self.bearing.list_price = 1.0
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertNotEqual(result['unit_price'], self.bearing.list_price)

    def test_det06_t004_parent_change_does_not_rewrite_coverage(self):
        self._v1(price=1000.0)
        self.other_partner.write({'parent_id': self.partner.id})
        result = self._dated(
            self.manager, self.company_a, self.other_partner, self.bearing, self._today(),
        )
        self.assertEqual(result['status'], 'NO_APPLICABLE_CONTRACT')
        self._assert_price_hidden(result, 1000)

    def test_det06_t005_live_policy_text_does_not_replace_the_snapshot(self):
        version = self._v1(price=1000.0)
        self.policy_a.write({
            'pricing_date_policy': 'delivery',
            'change_reason': 'Candidate change. Not an operational approval.',
        })
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(result['version_id'], version.id)
        self.assertEqual(result['pricing_date_policy_snapshot'], 'order_confirmation')
        self.assertEqual(self.policy_a.pricing_date_policy, 'delivery')
        self.assertFalse(version.policy_id.operationally_approved)

    def test_det06_t006_cache_key_includes_company_and_cutoff(self):
        resolver = self.env['cpla.pricing.applicability']
        base = {
            'company_id': self.company_a.id,
            'partner_id': self.partner.id,
            'product_id': self.bearing.id,
            'pricing_date': self._stamp(self._today()),
        }
        other = dict(base, company_id=self.company_b.id)
        later = dict(base, knowledge_cutoff='2026-10-28 00:00:00')
        self.assertNotEqual(resolver.cache_key(base), resolver.cache_key(other))
        self.assertNotEqual(resolver.cache_key(base), resolver.cache_key(later))
        self.assertNotIn('cpla.pricing.applicability.cache', self.env.registry)
        self._v1(price=1000.0)
        before = self.env['cpla.customer.contract.version'].search_count([])
        self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(self.env['cpla.customer.contract.version'].search_count([]), before)

    def test_det06_t007_a_new_approval_is_visible_on_the_next_call(self):
        first = self._v1(price=1000.0)
        early = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._on(1))
        self.assertEqual(early['version_id'], first.id)
        second = self._amend(first, price=1200.0, effective_days=1)
        later = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._on(1))
        self.assertEqual(later['version_id'], second.id)
        still = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(still['version_id'], first.id)

    def test_det06_t008_selected_line_belongs_to_the_selected_version(self):
        """Same-transaction consistency. This is not a concurrent approval race."""
        version = self._v1(price=1000.0)
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        line = self.env['cpla.customer.contract.version.line'].browse(result['version_line_id'])
        self.assertEqual(line.version_id, version)
        self.assertEqual(line.price_unit, result['unit_price'])
        self.assertEqual(line.product_id, self.bearing)
        self.assertEqual(result['contract_id'], version.contract_id.id)

    def test_det06_t009_one_lookup_stays_within_a_small_sample_bound(self):
        version = self._v1(price=1000.0)
        for index in range(8):
            partner = self.env['res.partner'].create({
                'name': 'Sample Buyer %s' % index,
                'is_company': True,
                'company_id': self.company_a.id,
            })
            self._v1(partner=partner, price=1000.0 + index)
        started = time.perf_counter()
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        elapsed = time.perf_counter() - started
        self.assertEqual(result['version_id'], version.id)
        self.assertLess(elapsed, 5.0, 'measured_seconds=%.4f' % elapsed)

    def test_det06_t010_repeated_resolution_creates_no_business_rows(self):
        self._v1(price=1000.0)
        before = self.env['cpla.customer.contract.version'].search_count([])
        for _index in range(3):
            self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(self.env['cpla.customer.contract.version'].search_count([]), before)
        self.assertFalse(self.env['ir.cron'].search([
            ('cron_name', 'ilike', 'applicability'),
        ]))

    def test_det06_t011_resolution_does_not_write_the_version(self):
        version = self._v1(price=1000.0)
        stamp = version.write_date
        price = version.line_ids.price_unit
        self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(version.write_date, stamp)
        self.assertEqual(version.line_ids.price_unit, price)
        self.assertEqual(version.state, 'approved')

    def test_det06_t012_measured_lookup_is_recorded_without_a_throughput_claim(self):
        self._v1(price=1000.0)
        started = time.perf_counter()
        result = self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        elapsed = time.perf_counter() - started
        self.assertEqual(result['status'], 'MATCHED_AUTHORITATIVE')
        self.assertLess(elapsed, 5.0, 'measured_seconds=%.4f' % elapsed)

    def test_reg06_t001_module_version_is_loaded(self):
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(module.state, 'installed')
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(module.latest_version, '19.0.1.15.0')

    def test_reg06_t002_previous_models_remain_registered(self):
        for name in (
            'cpla.company.policy',
            'cpla.customer.contract',
            'cpla.customer.contract.version',
            'cpla.customer.contract.version.line',
            'cpla.pricing.applicability',
            'cpla.pricing.applicability.check',
        ):
            self.assertIn(name, self.env.registry)

    def test_reg06_t003_contract_header_behavior_is_preserved(self):
        contract = self._draft(self.partner, [(self.bearing, 1000.0)])
        contract.action_submit_for_review()
        self.assertEqual(contract.state, 'ready_for_review')
        self.assertNotIn('approved', dict(contract._fields['state'].selection))
        self.assertTrue(contract.reference.startswith('CPL/'))

    def test_reg06_t004_approved_snapshot_is_not_changed_by_resolution(self):
        version = self._v1(price=1000.0)
        digest = version.snapshot_sha256
        self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(version.snapshot_sha256, digest)
        self.assertEqual(version.line_ids.price_unit, 1000.0)

    def test_reg06_t005_approval_events_are_preserved(self):
        version = self._v1(price=1000.0)
        before = len(version.event_ids)
        self._dated(self.manager, self.company_a, self.partner, self.bearing, self._today())
        self.assertEqual(len(version.event_ids), before)
        self.assertTrue(version.event_ids.filtered(lambda event: event.event_type == 'approved'))

    def test_reg06_t006_company_rules_remain(self):
        version_rule = self.env.ref('%s.cpla_customer_contract_version_company_rule' % MODULE)
        check_rule = self.env.ref('%s.cpla_pricing_applicability_check_company_rule' % MODULE)
        self.assertIn('company_id', version_rule.domain_force)
        self.assertIn('company_id', check_rule.domain_force)
        self.assertFalse(check_rule.groups)

    def test_reg06_t007_policy_remains_unapproved(self):
        self.assertFalse(self.policy_a.operationally_approved)
        version = self._v1(price=1000.0)
        self.assertFalse(version.policy_id.operationally_approved)
        self.assertEqual(version.amount_threshold_policy, 'not_configured')
        self.assertEqual(version.retroactivity_policy, 'not_authorized')

    def test_reg06_t008_views_and_menu_load(self):
        model = self.env['cpla.pricing.applicability.check']
        form = model.get_view(view_type='form')
        listing = model.get_view(view_type='list')
        self.assertIn('action_resolve', form['arch'])
        self.assertIn('not an approved price', form['arch'])
        self.assertNotIn('Run Invoice Audit', form['arch'])
        self.assertIn('status', listing['arch'])
        menu = self.env.ref('%s.menu_cpla_pricing_applicability' % MODULE)
        self.assertEqual(menu.name, 'Applicability Check')
        names = self.env['ir.ui.menu'].browse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'ir.ui.menu'),
        ]).mapped('res_id')).mapped('name')
        self.assertEqual(names.count('Customer Pricing Contracts'), 1)
        self.assertEqual(names.count('Configuration'), 1)

    def test_reg06_t009_applicability_tests_are_imported(self):
        from odoo.addons.contract_price_leakage_auditor.tests import test_pricing_applicability
        self.assertTrue(test_pricing_applicability.TestDev06PricingApplicability)

    def test_reg06_t010_prior_test_modules_remain_imported(self):
        from odoo.addons.contract_price_leakage_auditor.tests import (
            test_company_policy,
            test_contract_version,
            test_customer_contract,
            test_foundation_smoke,
            test_security_foundation,
        )
        self.assertTrue(test_contract_version.TestDev05ContractVersion)
        self.assertTrue(test_customer_contract.TestDev04CustomerContract)
        self.assertTrue(test_company_policy.TestDev03CompanyPolicy)
        self.assertTrue(test_foundation_smoke.TestDev01Foundation)
        self.assertTrue(test_security_foundation.TestDev02Security)

    def test_reg06_t011_no_invoice_or_leakage_records_are_created(self):
        self.assertFalse(self.env['cpla.leakage.finding'].search_count([]))
        self.assertNotIn('cpla.recovery', self.env.registry)
        self.assertNotIn('cpla.audit', self.env.registry)
        version = self._v1(price=1000.0)
        if 'account.move' in self.env.registry:
            self.assertFalse(self.env['account.move'].search([
                ('ref', '=', version.reference),
            ]))

    def test_reg06_t012_no_applicability_cron_is_created(self):
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'ir.cron'),
        ]))

    def test_gold_fin_002_order_date_selection_does_not_calculate_leakage(self):
        """Authority selection only. INR 25,000 and INR 760 are not calculated."""
        first = self._v1(price=1000.0)
        second = self._amend(first, price=1200.0, effective_days=1)
        result = self._resolve(
            self.manager, self.company_a, self.partner, self.bearing,
            basis='order_confirmation', order_confirmed=True,
            order_confirmation_date=self._today(), invoice_date=self._on(1),
        )
        self.assertEqual(result['version_id'], first.id)
        self.assertEqual(result['unit_price'], 1000.0)
        self.assertEqual(second.line_ids.price_unit, 1200.0)
        self.assertFalse(result['leakage_amount'])
        self.assertNotIn('25000', result['explanation'])
