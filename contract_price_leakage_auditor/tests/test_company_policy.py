from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'


@tagged('post_install', '-at_install')
class TestDev03CompanyPolicy(TransactionCase):
    """Company policy, readiness, and isolation tests.

    These tests do not create contracts, invoices, leakage cases, or payments.
    """

    @classmethod
    def setUpClass(cls):
        # This file is the first post-install class. Purge before the test
        # cursor opens: Odoo uses repeatable read, so a delete committed
        # after super() would stay invisible to this class.
        from odoo.orm.registry import Registry
        from odoo.tests.common import get_db_name
        from odoo.addons.contract_price_leakage_auditor.tests.test_invoice_audit import (
            purge_dev14_concurrency_pool,
        )
        purge_dev14_concurrency_pool(Registry(get_db_name()))
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
        cls.admin_a = cls._make_user('cfg_admin_a', 'group_app_admin', cls.company_a)
        cls.admin_b = cls._make_user('cfg_admin_b', 'group_app_admin', cls.company_b)
        cls.admin_both = cls._make_user(
            'cfg_admin_both',
            'group_app_admin',
            cls.company_a,
            companies=cls.company_a | cls.company_b,
        )
        cls.contract_user_a = cls._make_user('cfg_contract_user', 'group_contract_user', cls.company_a)
        cls.contract_manager_a = cls._make_user(
            'cfg_contract_manager', 'group_contract_manager', cls.company_a,
        )
        cls.reviewer_a = cls._make_user('cfg_reviewer', 'group_finance_reviewer', cls.company_a)
        cls.finance_manager_a = cls._make_user(
            'cfg_finance_manager', 'group_finance_manager', cls.company_a,
        )
        cls.auditor_a = cls._make_user('cfg_auditor', 'group_internal_auditor', cls.company_a)
        cls.recovery_a = cls._make_user('cfg_recovery', 'group_recovery_operator', cls.company_a)
        cls.sales_a = cls._make_user('cfg_sales', 'group_sales_pricing_reviewer', cls.company_a)

    @classmethod
    def _make_user(cls, login, xmlid, company, companies=None):
        companies = companies or company
        return new_test_user(
            cls.env,
            login=login,
            groups='base.group_user,%s.%s' % (MODULE, xmlid),
            password='cpla-test',
            company_id=company.id,
            company_ids=[Command.set(companies.ids)],
        )

    def _policy(self, company, **extra):
        values = {
            'company_id': company.id,
            'change_reason': 'Test draft. This is not an approval.',
        }
        values.update(extra)
        return self.env['cpla.company.policy'].create(values)

    def _env_as(self, user, companies):
        return self.env(user=user, context=dict(
            self.env.context,
            allowed_company_ids=list(companies.ids),
        ))

    def _snapshot(self, policy):
        return policy.read([
            'state', 'is_current', 'version', 'pricing_date_policy',
            'fx_basis_policy', 'operationally_approved',
        ])[0]

    def test_cfg_t001_company_a_configuration_can_be_created(self):
        policy = self._policy(self.company_a)
        self.assertEqual(policy.company_id, self.company_a)
        self.assertEqual(policy.version, 1)
        self.assertTrue(policy.is_current)
        self.assertEqual(policy.state, 'not_configured')
        self.assertFalse(policy.operationally_approved)

    def test_cfg_t002_company_b_configuration_is_independent(self):
        policy_b = self._policy(self.company_b, pricing_date_policy='delivery')
        self.assertEqual(policy_b.company_id, self.company_b)
        self.assertEqual(policy_b.pricing_date_policy, 'delivery')
        self.assertFalse(self.env['cpla.company.policy'].search([
            ('company_id', '=', self.company_a.id),
        ]))

    def test_cfg_t003_company_a_changes_do_not_alter_company_b(self):
        policy_a = self._policy(self.company_a, pricing_date_policy='delivery')
        policy_b = self._policy(self.company_b, pricing_date_policy='invoice')
        policy_a.write({'pricing_date_policy': 'order_confirmation'})
        self.assertEqual(policy_a.pricing_date_policy, 'order_confirmation')
        self.assertEqual(policy_b.pricing_date_policy, 'invoice')
        self.assertEqual(policy_b.company_id, self.company_b)

    def test_cfg_t004_unapproved_policies_do_not_become_operational(self):
        policy = self._policy(self.company_a)
        policy.write({
            'pricing_date_policy': 'invoice',
            'contract_precedence_policy': 'exact_customer',
            'customer_coverage_policy': 'exact_customer',
            'quantity_basis_policy': 'invoice',
            'discount_approval_policy': 'approval_reference_required',
            'fx_basis_policy': 'invoice_date',
            'tax_comparison_policy': 'tax_excluded',
            'monetary_precision_policy': 'company_currency_rounding',
            'tolerance_policy': 'do_not_suppress',
            'missing_evidence_policy': 'review_required',
        })
        policy.action_submit_for_review()
        self.assertEqual(policy.state, 'ready_for_business_review')
        self.assertFalse(policy.operationally_approved)
        with self.assertRaises(UserError):
            policy.with_env(
                self._env_as(self.finance_manager_a, self.company_a)
            ).action_request_activation()
        self.assertEqual(policy.state, 'ready_for_business_review')
        self.assertFalse(policy.approved_by)
        with self.assertRaises(UserError):
            policy.write({'state': 'approved_ready'})
        self.assertNotEqual(policy.state, 'approved_ready')

    def test_cfg_t005_required_configuration_fields_are_validated(self):
        with self.assertRaises(ValidationError):
            self.env['cpla.company.policy'].create({
                'change_reason': 'Missing company.',
            })
        with self.assertRaises(ValidationError):
            self.env['cpla.company.policy'].create({
                'company_id': self.company_a.id,
                'change_reason': '   ',
            })

    def test_cfg_t006_invalid_policy_selection_is_rejected(self):
        policy = self._policy(self.company_a)
        with self.assertRaises(ValueError):
            policy.write({'pricing_date_policy': 'lowest_price'})
        self.assertEqual(policy.pricing_date_policy, 'unconfigured')

    def test_cfg_t007_duplicate_active_policy_versions_are_prevented(self):
        policy = self._policy(self.company_a)
        with self.assertRaises(ValidationError):
            self._policy(self.company_a)
        with self.assertRaises(UserError):
            policy.copy()
        action = policy.action_new_revision()
        second = self.env['cpla.company.policy'].browse(action['res_id'])
        second.action_new_revision()
        currents = self.env['cpla.company.policy'].search([
            ('company_id', '=', self.company_a.id),
            ('is_current', '=', True),
        ])
        self.assertEqual(len(currents), 1)
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = %s",
            ['cpla_company_policy_one_current_idx'],
        )
        definition = self.env.cr.fetchone()[0]
        self.assertIn('UNIQUE', definition.upper())

    def test_cfg_t008_historical_policy_remains_traceable(self):
        policy = self._policy(self.company_a, pricing_date_policy='delivery')
        old_id = policy.id
        action = policy.action_new_revision()
        old = self.env['cpla.company.policy'].browse(old_id)
        new = self.env['cpla.company.policy'].browse(action['res_id'])
        self.assertFalse(old.is_current)
        self.assertEqual(old.pricing_date_policy, 'delivery')
        self.assertNotEqual(old.state, 'approved_ready')
        self.assertFalse(old.operationally_approved)
        self.assertEqual(new.supersedes_id, old)
        self.assertTrue(new.is_current)
        self.assertFalse(new.operationally_approved)

    def test_cfg_t009_invalid_effective_date_is_rejected(self):
        policy = self._policy(self.company_a)
        with self.assertRaises(ValidationError):
            policy.write({
                'effective_from': '2026-10-28',
                'effective_to': '2026-10-01',
            })
        self.assertFalse(policy.effective_from)
        self.assertFalse(policy.effective_to)

    def test_cfg_t010_repeated_save_does_not_duplicate_revisions(self):
        policy = self._policy(self.company_a)
        policy.write({'change_reason': 'Wording only. Still not approved.'})
        policy.write({'change_reason': 'Wording only. Still not approved.'})
        self.assertEqual(self.env['cpla.company.policy'].search_count([
            ('company_id', '=', self.company_a.id),
        ]), 1)
        self.assertEqual(policy.version, 1)

    def test_cfg_t011_valid_pricing_date_candidate_is_draft_only(self):
        policy = self._policy(self.company_a)
        policy.write({'pricing_date_policy': 'order_confirmation'})
        self.assertEqual(policy.pricing_date_policy, 'order_confirmation')
        self.assertEqual(policy.state, 'draft')
        self.assertFalse(policy.operationally_approved)
        readiness = policy.get_configuration_readiness()
        self.assertIn('PRICING_DATE_POLICY_REQUIRES_APPROVAL', readiness['codes'])
        self.assertFalse(readiness['operationally_approved'])

    def test_cfg_t012_unresolved_pricing_date_stays_incomplete(self):
        policy = self._policy(self.company_a)
        self.assertEqual(policy.pricing_date_policy, 'unconfigured')
        readiness = policy.get_configuration_readiness()
        self.assertIn('pricing_date_policy', readiness['missing'])
        self.assertIn('PRICING_DATE_POLICY_REQUIRES_APPROVAL', readiness['codes'])
        self.assertNotEqual(policy.state, 'approved_ready')

    def test_cfg_t013_contract_specific_priority_is_documented_only(self):
        policy = self._policy(self.company_a, pricing_date_policy='contract_specific')
        self.assertIn('LATER_APPROVED_CONTRACT', policy.contract_priority_rule)
        self.assertFalse(policy.operationally_approved)
        self.assertFalse([
            name for name in self.env.registry
            if name.startswith('cpla.contract')
        ])

    def test_cfg_t014_invalid_precedence_configuration_is_rejected(self):
        policy = self._policy(self.company_a)
        with self.assertRaises(ValueError):
            policy.write({'contract_precedence_policy': 'lowest_price'})
        self.assertEqual(policy.contract_precedence_policy, 'unconfigured')

    def test_cfg_t015_conflict_state_does_not_produce_false_readiness(self):
        policy = self._policy(
            self.company_a,
            contract_precedence_policy='exact_customer',
        )
        self.assertEqual(policy.conflict_behavior, 'CONTRACT_CONFLICT_REVIEW_REQUIRED')
        readiness = policy.get_configuration_readiness()
        self.assertIn('CONTRACT_CONFLICT_REVIEW_REQUIRED', readiness['codes'])
        self.assertTrue(readiness['blocking'])
        self.assertFalse(readiness['operationally_approved'])
        self.assertNotEqual(policy.state, 'approved_ready')

    def test_cfg_t016_company_currency_is_identified(self):
        policy = self._policy(self.company_a)
        self.assertTrue(policy.company_currency_id)
        self.assertEqual(policy.company_currency_id, self.company_a.currency_id)

    def test_cfg_t017_currency_reference_is_validated_without_activation(self):
        policy = self._policy(self.company_a)
        before = self.env['res.currency.rate'].search_count([])
        active = policy.validate_currency(policy.company_currency_id)
        self.assertEqual(active['classification'], 'VALID')
        self.assertEqual(active['fx_basis'], 'MISSING')
        self.assertFalse(active['operationally_approved'])
        self.assertFalse(active['activated'])
        inactive = self.env['res.currency'].create({
            'name': 'XCP',
            'symbol': 'X',
            'active': False,
        })
        blocked = policy.validate_currency(inactive)
        self.assertEqual(blocked['classification'], 'BLOCKING_CONFIGURATION_ERROR')
        self.assertFalse(inactive.active)
        self.assertEqual(self.env['res.currency.rate'].search_count([]), before)

    def test_cfg_t018_missing_fx_basis_is_flagged(self):
        policy = self._policy(self.company_a)
        self.assertEqual(policy.fx_basis_policy, 'unconfigured')
        readiness = policy.get_configuration_readiness()
        self.assertIn('fx_basis_policy', readiness['missing'])
        self.assertIn('DEC-06', readiness['codes'])
        result = policy.validate_currency(policy.company_currency_id)
        self.assertEqual(result['fx_basis'], 'MISSING')

    def test_cfg_t019_fx_policy_is_isolated_by_company(self):
        policy_a = self._policy(self.company_a, fx_basis_policy='invoice_date')
        policy_b = self._policy(self.company_b, fx_basis_policy='order_date')
        policy_a.write({'fx_basis_policy': 'pricing_date'})
        self.assertEqual(policy_a.fx_basis_policy, 'pricing_date')
        self.assertEqual(policy_b.fx_basis_policy, 'order_date')
        self.assertFalse(policy_a.operationally_approved)
        self.assertFalse(policy_b.operationally_approved)

    def test_cfg_t020_payment_date_fx_is_not_pricing_leakage(self):
        result = self.env['cpla.company.policy'].classify_exchange_difference('payment_date')
        self.assertEqual(result['code'], 'PAYMENT_FX_NOT_CONTRACT_LEAKAGE')
        self.assertFalse(result['pricing_leakage'])
        self.assertFalse(result['operationally_approved'])
        with self.assertRaises(UserError):
            self.env['cpla.company.policy'].propose_fixed_rate(84.0)

    def test_cfg_t021_valid_product_master_is_accepted(self):
        product = self.env['product.product'].create({
            'name': 'ABC India Widget',
            'company_id': self.company_a.id,
        })
        uom = product.uom_id
        results = self.env['cpla.company.policy'].validate_products(product, self.company_a)
        self.assertEqual(results[0]['classification'], 'VALID')
        self.assertEqual(results[0]['code'], 'PRODUCT_IDENTITY_OK')
        self.assertFalse(results[0]['operationally_approved'])
        self.assertEqual(product.uom_id, uom)
        self.assertTrue(product.active)

    def test_cfg_t022_wrong_company_product_is_rejected(self):
        product = self.env['product.product'].create({
            'name': 'UAE Widget',
            'company_id': self.company_b.id,
        })
        result = self.env['cpla.company.policy'].validate_product(product, self.company_a)
        self.assertEqual(result['classification'], 'BLOCKING_CONFIGURATION_ERROR')
        self.assertEqual(result['code'], 'WRONG_COMPANY_PRODUCT')
        self.assertEqual(product.company_id, self.company_b)

    def test_cfg_t023_shared_product_is_accepted_without_contract_inheritance(self):
        product = self.env['product.product'].create({
            'name': 'Shared Widget',
            'company_id': False,
        })
        result = self.env['cpla.company.policy'].validate_product(product, self.company_a)
        self.assertEqual(result['classification'], 'WARNING')
        self.assertEqual(result['code'], 'SHARED_PRODUCT_NO_CONTRACT_INHERITANCE')
        self.assertFalse(product.company_id)
        self.assertTrue(product.exists())

    def test_cfg_t024_product_variant_mapping_is_validated(self):
        attribute = self.env['product.attribute'].create({'name': 'CPLA Size'})
        values = self.env['product.attribute.value'].create([
            {'name': 'Small', 'attribute_id': attribute.id},
            {'name': 'Large', 'attribute_id': attribute.id},
        ])
        template = self.env['product.template'].create({
            'name': 'Ambiguous widget',
            'company_id': self.company_a.id,
            'attribute_line_ids': [Command.create({
                'attribute_id': attribute.id,
                'value_ids': [Command.set(values.ids)],
            })],
        })
        ambiguous = self.env['cpla.company.policy'].validate_product(template, self.company_a)
        self.assertEqual(ambiguous['code'], 'AMBIGUOUS_PRODUCT_VARIANT')
        variant = template.product_variant_ids[:1]
        specific = self.env['cpla.company.policy'].validate_product(variant, self.company_a)
        self.assertEqual(specific['classification'], 'VALID')

    def test_cfg_t025_valid_uom_conversion_is_accepted(self):
        unit = self.env.ref('uom.product_uom_unit')
        pack = self.env.ref('uom.product_uom_pack_6')
        result = self.env['cpla.company.policy'].validate_uom_conversion(pack, unit)
        self.assertEqual(result['classification'], 'VALID')
        self.assertAlmostEqual(result['quantity'], 6.0)

    def test_cfg_t026_invalid_or_incompatible_conversion_is_flagged(self):
        unit = self.env.ref('uom.product_uom_unit')
        weight = self.env.ref('uom.product_uom_kgm')
        incompatible = self.env['cpla.company.policy'].validate_uom_conversion(unit, weight)
        self.assertEqual(incompatible['code'], 'INCOMPATIBLE_UOM')
        negative = self.env['uom.uom'].new({
            'name': 'Negative carton',
            'relative_uom_id': unit.id,
            'relative_factor': -1.0,
        })
        zero = self.env['uom.uom'].new({
            'name': 'Zero carton',
            'relative_uom_id': unit.id,
            'relative_factor': 0.0,
        })
        self.assertEqual(
            self.env['cpla.company.policy'].validate_uom_conversion(unit, negative)['code'],
            'INVALID_CONVERSION_FACTOR',
        )
        self.assertEqual(
            self.env['cpla.company.policy'].validate_uom_conversion(unit, zero)['code'],
            'INVALID_CONVERSION_FACTOR',
        )
        missing = self.env['cpla.company.policy'].validate_uom_conversion(
            unit, self.env['uom.uom'],
        )
        self.assertEqual(missing['code'], 'MISSING_UOM')

    def test_cfg_t027_packaging_is_not_treated_as_the_price_uom(self):
        unit = self.env.ref('uom.product_uom_unit')
        carton = self.env['uom.uom'].create({
            'name': 'Carton 10',
            'relative_uom_id': unit.id,
            'relative_factor': 10.0,
        })
        product = self.env['product.product'].create({
            'name': 'Carton product',
            'company_id': self.company_a.id,
            'uom_id': unit.id,
            'uom_ids': [Command.link(carton.id)],
        })
        packaged = self.env['cpla.company.policy'].classify_pricing_unit(product, carton)
        default = self.env['cpla.company.policy'].classify_pricing_unit(product, unit)
        self.assertEqual(packaged['classification'], 'REVIEW_REQUIRED')
        self.assertEqual(packaged['code'], 'PACKAGING_UOM_NOT_PRICE_UNIT')
        self.assertEqual(default['classification'], 'VALID')
        self.assertNotIn('product.packaging', self.env.registry)

    def test_cfg_t028_archived_product_is_reviewed_not_deleted(self):
        product = self.env['product.product'].create({
            'name': 'Archived widget',
            'company_id': self.company_a.id,
        })
        product.active = False
        result = self.env['cpla.company.policy'].validate_product(product, self.company_a)
        self.assertEqual(result['code'], 'ARCHIVED_PRODUCT_RETAINED')
        stored = self.env['product.product'].with_context(active_test=False).browse(product.id)
        self.assertTrue(stored.exists())
        self.assertFalse(stored.active)

    def test_cfg_t029_precision_candidate_does_not_round_away_a_difference(self):
        policy = self._policy(
            self.company_a,
            monetary_precision_policy='company_currency_rounding',
        )
        self.assertEqual(policy.monetary_precision_policy, 'company_currency_rounding')
        self.assertFalse(policy.operationally_approved)
        self.assertEqual(policy.company_currency_id.round(25000.0), 25000.0)
        assessment = policy.assess_monetary_difference(25000.0)
        self.assertEqual(assessment['rounded_difference'], 25000.0)
        self.assertFalse(assessment['suppressed'])
        self.assertFalse(assessment['audited'])

    def test_cfg_t030_negative_tolerance_is_rejected_and_positive_is_not_stored(self):
        policy = self._policy(self.company_a)
        with self.assertRaises(ValidationError):
            self.env['cpla.company.policy'].propose_tolerance(-1)
        with self.assertRaises(UserError):
            self.env['cpla.company.policy'].propose_tolerance(10)
        self.assertNotIn('tolerance_amount', policy._fields)
        self.assertIn(policy.tolerance_policy, ('unconfigured', 'do_not_suppress'))
        policy.write({'tolerance_policy': 'do_not_suppress'})
        assessment = policy.assess_monetary_difference(25000.0)
        self.assertFalse(assessment['suppressed'])

    def test_cfg_t031_missing_tax_comparison_policy_is_flagged(self):
        policy = self._policy(self.company_a)
        readiness = policy.get_configuration_readiness()
        self.assertIn('tax_comparison_policy', readiness['missing'])
        self.assertIn('DEC-07', readiness['codes'])

    def test_cfg_t032_tax_inclusive_and_exclusive_are_not_comparable(self):
        result = self.env['cpla.company.policy'].classify_tax_bases(
            'tax_included', 'tax_excluded',
        )
        self.assertEqual(result['classification'], 'REVIEW_REQUIRED')
        self.assertEqual(result['code'], 'TAX_INCLUSIVE_EXCLUSIVE_NOT_COMPARABLE')
        self.assertFalse(result['comparable'])
        self.assertFalse(result['operationally_approved'])

    def test_cfg_t033_unverified_tax_treatment_cannot_be_approved_ready(self):
        policy = self._policy(self.company_a)
        policy.write({'tax_comparison_policy': 'tax_excluded'})
        policy.action_submit_for_review()
        same = policy.classify_tax_bases('tax_excluded', 'tax_excluded')
        unknown = policy.classify_tax_bases('guessed', 'tax_excluded')
        self.assertEqual(policy.state, 'ready_for_business_review')
        self.assertFalse(policy.operationally_approved)
        self.assertFalse(same['comparable'])
        self.assertEqual(same['code'], 'TAX_TREATMENT_UNVERIFIED')
        self.assertEqual(unknown['code'], 'TAX_BASIS_UNKNOWN')
        self.assertNotEqual(policy.state, 'approved_ready')

    def test_cfg_t034_contract_user_cannot_edit_company_policy(self):
        policy = self._policy(self.company_a)
        user_env = self._env_as(self.contract_user_a, self.company_a)
        visible = user_env['cpla.company.policy'].search([('id', '=', policy.id)])
        self.assertEqual(visible, policy)
        self.assertEqual(visible.change_reason, policy.change_reason)
        with self.assertRaises(AccessError):
            visible.write({'change_reason': 'Unauthorized edit.'})
        with self.assertRaises(AccessError):
            visible.read(['fx_basis_policy'])
        for user in (self.recovery_a, self.sales_a):
            env = self._env_as(user, self.company_a)
            with self.assertRaises(AccessError):
                env['cpla.company.policy'].browse(policy.id).write({
                    'change_reason': 'Unauthorized edit.',
                })
            with self.assertRaises(AccessError):
                env['cpla.company.policy'].search([])

    def test_cfg_t035_finance_reviewer_cannot_alter_approval_limits(self):
        policy = self._policy(self.company_a)
        env = self._env_as(self.reviewer_a, self.company_a)
        with self.assertRaises(AccessError):
            env['cpla.company.policy'].browse(policy.id).write({
                'discount_approval_policy': 'approval_reference_required',
            })
        with self.assertRaises(AccessError):
            env['cpla.company.policy'].browse(policy.id).action_request_activation()
        self.assertNotIn('approval_limit', policy._fields)
        self.assertFalse(policy.approved_by)

    def test_cfg_t036_company_a_user_cannot_modify_company_b(self):
        policy_b = self._policy(self.company_b, pricing_date_policy='delivery')
        env = self._env_as(self.admin_a, self.company_a)
        with self.assertRaises(AccessError):
            env['cpla.company.policy'].browse(policy_b.id).write({
                'change_reason': 'Cross-company edit.',
            })
        self.assertEqual(policy_b.pricing_date_policy, 'delivery')
        self.assertEqual(policy_b.change_reason, 'Test draft. This is not an approval.')

    def test_cfg_t037_direct_configuration_update_outside_scope_is_rejected(self):
        policy_a = self._policy(self.company_a, pricing_date_policy='delivery')
        policy_b = self._policy(self.company_b, pricing_date_policy='invoice')
        env_a = self._env_as(self.admin_a, self.company_a)
        with self.assertRaises(AccessError):
            env_a['cpla.company.policy'].create({
                'company_id': self.company_b.id,
                'change_reason': 'Forged company.',
            })
        limited = self._env_as(self.admin_both, self.company_a)
        with self.assertRaises(AccessError):
            limited['cpla.company.policy'].browse(policy_b.id).write({
                'change_reason': 'Active company does not include UAE.',
            })
        with self.assertRaises(UserError):
            policy_a.write({'company_id': self.company_b.id})
        self.assertEqual(policy_a.company_id, self.company_a)
        self.assertEqual(policy_b.pricing_date_policy, 'invoice')
        both = self._env_as(self.admin_both, self.company_a | self.company_b)
        both['cpla.company.policy'].browse(policy_b.id).write({
            'change_reason': 'UAE wording only.',
        })
        self.assertEqual(policy_a.pricing_date_policy, 'delivery')
        self.assertEqual(policy_b.change_reason, 'UAE wording only.')

    def test_cfg_t038_configuration_manager_can_edit_a_draft(self):
        env = self._env_as(self.admin_a, self.company_a)
        policy = env['cpla.company.policy'].create({
            'company_id': self.company_a.id,
            'change_reason': 'Administrator draft.',
        })
        policy.write({'pricing_date_policy': 'order_confirmation'})
        self.assertEqual(policy.pricing_date_policy, 'order_confirmation')
        self.assertEqual(policy.requested_by, self.admin_a)
        self.assertFalse(policy.operationally_approved)
        manager_env = self._env_as(self.contract_manager_a, self.company_a)
        with self.assertRaises(AccessError):
            manager_env['cpla.company.policy'].browse(policy.id).write({
                'change_reason': 'Manager edit.',
            })

    def test_cfg_t039_historical_change_records_cannot_be_rewritten(self):
        policy = self._policy(self.company_a, pricing_date_policy='delivery')
        policy.action_new_revision()
        self.assertFalse(policy.is_current)
        with self.assertRaises(UserError):
            policy.write({'pricing_date_policy': 'invoice'})
        with self.assertRaises(UserError):
            policy.unlink()
        env = self._env_as(self.auditor_a, self.company_a)
        with self.assertRaises(AccessError):
            env['cpla.company.policy'].browse(policy.id).write({
                'change_reason': 'Auditor rewrite.',
            })
        self.assertEqual(policy.pricing_date_policy, 'delivery')

    def test_cfg_t040_sensitive_settings_are_not_exposed_to_unauthorized_readers(self):
        policy = self._policy(
            self.company_a,
            tax_comparison_policy='tax_excluded',
            fx_basis_policy='invoice_date',
        )
        hidden = self._env_as(self.contract_user_a, self.company_a)
        with self.assertRaises(AccessError):
            hidden['cpla.company.policy'].browse(policy.id).read(['fx_basis_policy'])
        with self.assertRaises(UserError):
            hidden['cpla.company.policy'].browse(policy.id).export_data(['fx_basis_policy'])
        manager = self._env_as(self.contract_manager_a, self.company_a)[
            'cpla.company.policy'
        ].browse(policy.id)
        visible = manager.read()[0]
        self.assertNotIn('fx_basis_policy', visible)
        self.assertNotIn('tax_comparison_policy', visible)
        self.assertNotIn('tolerance_policy', visible)
        with self.assertRaises(AccessError):
            manager.read(['fx_basis_policy'])
        readiness = manager.get_configuration_readiness()
        self.assertNotIn('tax_comparison_policy', readiness['candidates'])
        self.assertNotIn('fx_basis_policy', readiness['candidates'])

    def test_cfg_t041_valid_draft_change_is_recorded(self):
        env = self._env_as(self.admin_a, self.company_a)
        policy = env['cpla.company.policy'].create({
            'company_id': self.company_a.id,
            'change_reason': 'Initial draft for ABC India.',
        })
        self.assertEqual(policy.requested_by, self.admin_a)
        self.assertTrue(policy.requested_on)
        self.assertEqual(policy.change_reason, 'Initial draft for ABC India.')
        self.assertIn(policy.state, ('not_configured', 'draft'))
        self.assertFalse(policy.approved_by)

    def test_cfg_t042_activation_does_not_create_an_approved_revision(self):
        policy = self._policy(self.company_a, pricing_date_policy='delivery')
        before = self.env['cpla.company.policy'].search_count([
            ('company_id', '=', self.company_a.id),
        ])
        with self.assertRaises(AccessError):
            policy.with_env(self._env_as(self.admin_a, self.company_a)).action_request_activation()
        policy.write({'requested_by': self.finance_manager_a.id})
        with self.assertRaises(AccessError):
            policy.with_env(
                self._env_as(self.finance_manager_a, self.company_a)
            ).action_request_activation()
        policy.write({'requested_by': self.admin_a.id})
        with self.assertRaises(UserError):
            policy.with_env(
                self._env_as(self.finance_manager_a, self.company_a)
            ).action_request_activation()
        self.assertEqual(self.env['cpla.company.policy'].search_count([
            ('company_id', '=', self.company_a.id),
        ]), before)
        self.assertFalse(policy.operationally_approved)
        self.assertFalse(policy.approved_by)
        self.assertNotEqual(policy.state, 'approved_ready')

    def test_cfg_t043_failed_activation_leaves_no_partial_active_state(self):
        policy = self._policy(self.company_a, pricing_date_policy='order_confirmation')
        before = self._snapshot(policy)
        with self.assertRaises(UserError):
            policy.with_env(
                self._env_as(self.finance_manager_a, self.company_a)
            ).action_request_activation()
        self.assertEqual(self._snapshot(policy), before)
        self.assertEqual(self.env['cpla.company.policy'].search_count([
            ('company_id', '=', self.company_a.id),
            ('is_current', '=', True),
        ]), 1)

    def test_cfg_t044_unapproved_change_does_not_supersede_into_an_approval(self):
        policy = self._policy(self.company_a, pricing_date_policy='delivery')
        action = policy.action_new_revision()
        new = self.env['cpla.company.policy'].browse(action['res_id'])
        self.assertNotEqual(policy.state, 'approved_ready')
        self.assertNotEqual(new.state, 'approved_ready')
        self.assertFalse(policy.operationally_approved)
        self.assertFalse(new.operationally_approved)
        self.assertEqual(new.supersedes_id, policy)
        self.assertFalse(policy.approved_by)
        self.assertFalse(new.approved_by)

    def test_cfg_t045_previous_policy_snapshot_remains_traceable(self):
        policy = self._policy(self.company_a, quantity_basis_policy='sales_order')
        first_id = policy.id
        action = policy.action_new_revision()
        new = self.env['cpla.company.policy'].browse(action['res_id'])
        old = self.env['cpla.company.policy'].browse(first_id)
        self.assertEqual(new.supersedes_id, old)
        self.assertEqual(old.quantity_basis_policy, 'sales_order')
        self.assertEqual(new.quantity_basis_policy, 'sales_order')
        self.assertTrue(old.exists())
        self.assertGreater(new.version, old.version)

    def test_cfg_t046_module_install_state_is_consistent(self):
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(module.state, 'installed')
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(module.latest_version, manifest['version'])

    def test_cfg_t047_updated_module_keeps_dev02_groups(self):
        self.assertEqual(self.env['ir.model.data'].search_count([
            ('module', '=', MODULE),
            ('model', '=', 'res.groups'),
        ]), 8)
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        self.assertEqual(module.dependencies_id.mapped('name'), ['base', 'product', 'sale'])
        self.assertEqual(module.state, 'installed')

    def test_cfg_t048_security_and_policy_records_are_not_duplicated(self):
        policy_access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'cpla.company.policy'),
        ])
        self.assertEqual(len(policy_access), 7)
        salesman_access = policy_access.filtered(
            lambda access: access.group_id == self.env.ref('sales_team.group_sale_salesman')
        )
        self.assertEqual(len(salesman_access), 1)
        self.assertTrue(salesman_access.perm_read)
        self.assertFalse(salesman_access.perm_write)
        self.assertFalse(salesman_access.perm_create)
        self.assertFalse(salesman_access.perm_unlink)
        contract_user_access = policy_access.filtered(
            lambda access: access.group_id == self.env.ref('%s.group_contract_user' % MODULE)
        )
        self.assertEqual(len(contract_user_access), 1)
        self.assertTrue(contract_user_access.perm_read)
        self.assertFalse(contract_user_access.perm_write)
        self.assertFalse(contract_user_access.perm_create)
        self.assertFalse(contract_user_access.perm_unlink)
        self.assertEqual(self.env['ir.rule'].search_count([
            ('model_id.model', '=', 'cpla.company.policy'),
        ]), 1)
        self.assertEqual(self.env['cpla.company.policy'].search_count([]), 0)
        self.assertEqual(self.env['ir.model.data'].search_count([
            ('module', '=', MODULE),
            ('model', '=', 'res.groups'),
        ]), 8)

    def test_cfg_t049_foundation_remains_operational(self):
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(manifest['license'], 'Other proprietary')
        self.assertFalse(manifest['author'])
        self.assertFalse(manifest['application'])
        self.assertNotIn('account', manifest['depends'])
        self.assertIn('sale', manifest['depends'])
        self.assertTrue(self.env.registry.ready)
        self.assertIn('cpla.company.policy', self.env.registry)
        self.assertEqual(len(self.env['res.groups'].search([
            ('privilege_id.category_id', '=', self.env.ref(
                '%s.module_category_contract_price_leakage' % MODULE
            ).id),
        ])), 8)

    def test_cfg_t050_views_and_fields_load(self):
        model = self.env['cpla.company.policy']
        for view_type in ('form', 'list'):
            loaded = model.get_view(view_type=view_type)
            self.assertTrue(loaded.get('arch'))
        manager_env = self._env_as(self.contract_manager_a, self.company_a)
        manager_env['cpla.company.policy'].get_view(view_type='form')
        for field_name in (
            'company_id', 'version', 'state', 'is_current',
            'pricing_date_policy', 'fx_basis_policy', 'tolerance_policy',
            'operationally_approved',
        ):
            self.assertIn(field_name, model._fields)
        self.assertNotIn('approval_limit', model._fields)
        self.assertNotIn('tolerance_amount', model._fields)

    def test_cfg_customer_identity_and_archived_history(self):
        exact = self.env['res.partner'].create({
            'name': 'ABC India Buyer',
            'company_id': self.company_a.id,
            'is_company': True,
        })
        identity = self.env['cpla.company.policy'].validate_customer(exact, self.company_a)
        self.assertEqual(identity['classification'], 'VALID')
        self.assertFalse(identity['coverage_approved'])
        self.assertFalse(identity['inherits_parent_contract'])
        shared = self.env['res.partner'].create({
            'name': 'Shared Buyer',
            'is_company': True,
            'company_id': False,
        })
        shared_result = self.env['cpla.company.policy'].validate_customer(shared, self.company_a)
        self.assertEqual(shared_result['code'], 'SHARED_CUSTOMER_NO_CONTRACT_INHERITANCE')
        child = self.env['res.partner'].create({
            'name': 'Invoice desk',
            'parent_id': exact.id,
            'type': 'invoice',
        })
        child_result = self.env['cpla.company.policy'].validate_customer(child, self.company_a)
        self.assertEqual(child_result['code'], 'CHILD_CONTACT_DOES_NOT_INHERIT_CONTRACT')
        self.assertFalse(child_result['inherits_parent_contract'])
        other = self.env['res.partner'].create({
            'name': 'UAE Buyer',
            'company_id': self.company_b.id,
            'is_company': True,
        })
        other_result = self.env['cpla.company.policy'].validate_customer(other, self.company_a)
        self.assertEqual(other_result['classification'], 'BLOCKING_CONFIGURATION_ERROR')
        exact.active = False
        archived = self.env['cpla.company.policy'].validate_customer(exact, self.company_a)
        self.assertEqual(archived['code'], 'ARCHIVED_CUSTOMER_RETAINED')
        self.assertTrue(exact.with_context(active_test=False).exists())

    def test_cfg_cross_company_approval_reference_is_rejected(self):
        policy = self._policy(self.company_a)
        with self.assertRaises(ValidationError):
            policy.check_approval_reference(self.admin_b)
        with self.assertRaises(UserError):
            policy.check_approval_reference(self.finance_manager_a)
        self.assertFalse(policy.approved_by)
        self.assertNotIn('approval_limit', policy._fields)

    def test_cfg_golden_fixtures_remain_reference_only(self):
        reference = self.env['cpla.company.policy'].golden_fixture_reference()
        self.assertFalse(reference['audited'])
        self.assertFalse(reference['implemented'])
        by_code = {row['code']: row for row in reference['fixtures']}
        row = by_code['GOLD-FIN-001']
        self.assertEqual(
            (row['approved_price'] - row['invoice_price']) * row['quantity'],
            row['expected_difference'],
        )
        row = by_code['GOLD-FIN-003']
        approved_piece = (
            row['box_price'] / row['pieces_per_box'] * row['fx_rate'] * (1 - row['discount_rate'])
        )
        self.assertAlmostEqual(
            (approved_piece - row['invoice_piece_price']) * row['quantity'],
            row['expected_difference'],
        )
        row = by_code['GOLD-FIN-004']
        self.assertEqual(
            (row['box_price'] / row['pieces_per_box'] - row['invoice_piece_price']) * row['quantity'],
            row['expected_difference'],
        )
        row = by_code['GOLD-FIN-005']
        self.assertEqual(
            (row['expected_net_price'] - row['invoice_net_price']) * row['quantity'],
            row['expected_difference'],
        )
        policy = self._policy(self.company_a)
        assessment = policy.assess_monetary_difference(25000.0)
        self.assertEqual(assessment['rounded_difference'], 25000.0)
        self.assertFalse(assessment['suppressed'])
        self.assertFalse(assessment['audited'])
