import os

from odoo import Command
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'

GROUP_XMLIDS = (
    'group_contract_user',
    'group_contract_manager',
    'group_sales_pricing_reviewer',
    'group_finance_reviewer',
    'group_finance_manager',
    'group_recovery_operator',
    'group_internal_auditor',
    'group_app_admin',
)

PRIVILEGE_XMLIDS = (
    'privilege_contract_access',
    'privilege_sales_pricing_review',
    'privilege_finance',
    'privilege_recovery',
    'privilege_internal_audit',
    'privilege_application_admin',
)

STANDARD_GROUPS = (
    'base.group_user',
    'base.group_portal',
    'base.group_public',
    'base.group_system',
    'base.group_erp_manager',
)


@tagged('post_install', '-at_install')
class TestDev02Security(TransactionCase):
    """Role checks for the DEV-02 foundation.

    These tests do not create contracts, prices, invoices, or recovery records.
    """

    def _ref(self, xmlid):
        return self.env.ref(f'{MODULE}.{xmlid}')

    def _groups(self):
        groups = self.env['res.groups']
        for xmlid in GROUP_XMLIDS:
            groups |= self._ref(xmlid)
        return groups

    def _user(self, login, *xmlids, company=None):
        groups = 'base.group_user,' + ','.join(f'{MODULE}.{xmlid}' for xmlid in xmlids)
        values = {'password': 'cpla-test'}
        if company:
            values['company_id'] = company.id
            values['company_ids'] = [Command.set([company.id])]
        return new_test_user(self.env, login=login, groups=groups, **values)

    def _app_membership(self, user):
        return user.all_group_ids & self._groups()

    def test_sec_t001_groups_exist_with_stable_ids(self):
        groups = self._groups()
        self.assertEqual(len(groups), len(GROUP_XMLIDS))
        self.assertEqual(len(set(groups.ids)), len(GROUP_XMLIDS))
        for xmlid, group in zip(GROUP_XMLIDS, [
            self._ref(xmlid) for xmlid in GROUP_XMLIDS
        ]):
            data = self.env['ir.model.data'].search([
                ('module', '=', MODULE),
                ('name', '=', xmlid),
                ('model', '=', 'res.groups'),
            ])
            self.assertEqual(data.res_id, group.id)

    def test_sec_t002_group_definitions_are_installed(self):
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        self.assertEqual(module.state, 'installed')
        self.assertEqual(len(self._groups()), 8)
        self.assertEqual(
            self.env['ir.model.data'].search_count([
                ('module', '=', MODULE),
                ('model', '=', 'res.groups'),
            ]),
            8,
        )

    def test_sec_t003_privilege_assignment_matches_odoo19(self):
        category = self._ref('module_category_contract_price_leakage')
        self.assertFalse(category.exclusive)
        privileges = self.env['res.groups.privilege']
        for xmlid in PRIVILEGE_XMLIDS:
            privileges |= self._ref(xmlid)
        self.assertEqual(len(privileges), 6)
        self.assertEqual(privileges.category_id, category)
        groups = self._groups()
        self.assertEqual(groups.privilege_id, privileges)
        self.assertEqual(
            self._ref('group_contract_user').privilege_id,
            self._ref('group_contract_manager').privilege_id,
        )
        self.assertEqual(
            self._ref('group_finance_reviewer').privilege_id,
            self._ref('group_finance_manager').privilege_id,
        )
        independent = self.env['res.groups.privilege']
        for xmlid in (
            'group_sales_pricing_reviewer',
            'group_recovery_operator',
            'group_internal_auditor',
            'group_app_admin',
        ):
            independent |= self._ref(xmlid).privilege_id
        self.assertEqual(len(independent), 4)
        self.assertFalse(independent & self._ref('group_contract_user').privilege_id)
        self.assertFalse(independent & self._ref('group_finance_reviewer').privilege_id)

    def test_sec_t004_inheritance_follows_two_ladders_only(self):
        contract_user = self._ref('group_contract_user')
        contract_manager = self._ref('group_contract_manager')
        reviewer = self._ref('group_finance_reviewer')
        finance_manager = self._ref('group_finance_manager')
        self.assertEqual(contract_manager.implied_ids, contract_user)
        self.assertEqual(contract_manager.all_implied_ids, contract_manager | contract_user)
        self.assertEqual(contract_user.all_implied_ids, contract_user)
        self.assertEqual(finance_manager.implied_ids, reviewer)
        self.assertEqual(finance_manager.all_implied_ids, finance_manager | reviewer)
        self.assertEqual(reviewer.all_implied_ids, reviewer)
        for xmlid in (
            'group_sales_pricing_reviewer',
            'group_recovery_operator',
            'group_internal_auditor',
            'group_app_admin',
        ):
            group = self._ref(xmlid)
            self.assertFalse(group.implied_ids)
            self.assertEqual(group.all_implied_ids, group)

    def test_sec_t005_auditor_has_no_financial_write_authority(self):
        auditor = self._ref('group_internal_auditor')
        self.assertEqual(auditor.all_implied_ids, auditor)
        forbidden = self.env['res.groups']
        for xmlid in (
            'group_finance_reviewer',
            'group_finance_manager',
            'group_recovery_operator',
            'group_contract_manager',
            'group_app_admin',
        ):
            forbidden |= self._ref(xmlid)
        self.assertFalse(auditor.all_implied_ids & forbidden)
        access = auditor.model_access
        self.assertEqual(len(access), 47)
        self.assertEqual(set(access.mapped('model_id.model')), {
            'cpla.company.policy',
            'cpla.customer.contract',
            'cpla.customer.contract.line',
            'cpla.customer.contract.evidence',
            'cpla.customer.contract.version',
            'cpla.customer.contract.version.line',
            'cpla.customer.contract.version.tier',
            'cpla.customer.contract.version.evidence',
            'cpla.customer.contract.version.event',
            'cpla.pricing.applicability.check',
            'cpla.discount.concession',
            'cpla.discount.approval',
            'cpla.discount.event',
            'cpla.sale.price.lock',
            'cpla.invoice.source.map',
            'cpla.invoice.source.allocation',
            'cpla.invoice.audit.run',
            'cpla.invoice.audit.result',
            'cpla.leakage.finding',
            'cpla.leakage.case',
            'cpla.leakage.case.membership',
            'cpla.leakage.case.event',
            'cpla.leakage.case.checklist',
            'cpla.leakage.case.evidence',
            'cpla.leakage.case.submission',
            'cpla.leakage.reassessment',
            'cpla.leakage.reassessment.event',
            'cpla.finance.validation.policy',
            'cpla.finance.validation.policy.level',
            'cpla.finance.validation',
            'cpla.finance.validation.line',
            'cpla.finance.validation.approval',
            'cpla.recovery.policy',
            'cpla.recovery.policy.level',
            'cpla.recovery.request',
            'cpla.recovery.request.line',
            'cpla.recovery.waiver',
            'cpla.recovery.dispute',
            'cpla.recovery.settlement',
            'cpla.recovery.event',
            'cpla.recovery.balance',
            'cpla.recovery.billing.policy',
            'cpla.recovery.billing',
            'cpla.recovery.billing.line',
            'cpla.recovery.accounting.link',
            'cpla.recovery.collection.evidence',
            'cpla.recovery.accounting.adjustment',
        })
        for row in access:
            self.assertTrue(row.perm_read)
            if row.model_id.model == 'cpla.pricing.applicability.check':
                self.assertTrue(row.perm_write)
                self.assertTrue(row.perm_create)
                self.assertTrue(row.perm_unlink)
            else:
                self.assertFalse(row.perm_write)
                self.assertFalse(row.perm_create)
                self.assertFalse(row.perm_unlink)
        self.assertFalse(auditor.rule_groups)
        self.assertEqual(
            auditor.menu_access,
            self._ref('menu_cpla_root') | self._ref('menu_cpla_configuration')
            | self._ref('menu_cpla_contracts') | self._ref('menu_cpla_customer_contracts')
            | self._ref('menu_cpla_contract_versions') | self._ref('menu_cpla_amendment_review')
            | self._ref('menu_cpla_pricing_applicability')
            | self._ref('menu_cpla_discount_approvals')
            | self._ref('menu_cpla_price_overrides')
            | self._ref('menu_cpla_discount_concessions')
            | self._ref('menu_cpla_investigation')
            | self._ref('menu_cpla_leakage_cases')
            | self._ref('menu_cpla_my_cases')
            | self._ref('menu_cpla_unassigned_cases')
            | self._ref('menu_cpla_evidence_pending')
            | self._ref('menu_cpla_ready_finance')
            | self._ref('menu_cpla_exception_queue')
            | self._ref('menu_cpla_case_history')
            | self._ref('menu_cpla_reassessments')
            | self._ref('menu_cpla_finance')
            | self._ref('menu_cpla_finance_pending')
            | self._ref('menu_cpla_finance_mine')
            | self._ref('menu_cpla_finance_evidence')
            | self._ref('menu_cpla_finance_approval')
            | self._ref('menu_cpla_finance_approved')
            | self._ref('menu_cpla_finance_partial')
            | self._ref('menu_cpla_finance_rejected')
            | self._ref('menu_cpla_finance_stale')
            | self._ref('menu_cpla_finance_history')
            | self._ref('menu_cpla_finance_policy')
            | self._ref('menu_cpla_recovery')
            | self._ref('menu_cpla_recovery_requests')
            | self._ref('menu_cpla_recovery_mine')
            | self._ref('menu_cpla_recovery_approval')
            | self._ref('menu_cpla_recovery_approved')
            | self._ref('menu_cpla_recovery_waivers')
            | self._ref('menu_cpla_recovery_waiver_approval')
            | self._ref('menu_cpla_recovery_disputes')
            | self._ref('menu_cpla_recovery_settlements')
            | self._ref('menu_cpla_recovery_settlement_approval')
            | self._ref('menu_cpla_recovery_handoff')
            | self._ref('menu_cpla_recovery_history')
            | self._ref('menu_cpla_recovery_policy')
            | self._ref('menu_cpla_recovery_billing')
            | self._ref('menu_cpla_recovery_billing_policy')
            | self._ref('menu_cpla_recovery_billing_requests')
            | self._ref('menu_cpla_recovery_billing_drafts')
            | self._ref('menu_cpla_recovery_billing_posted')
            | self._ref('menu_cpla_recovery_accounting_links')
            | self._ref('menu_cpla_recovery_collections')
            | self._ref('menu_cpla_recovery_bank_pending')
            | self._ref('menu_cpla_recovery_credits')
            | self._ref('menu_cpla_recovery_overdue'),
        )

    def test_sec_t006_administrator_has_no_commercial_approval_groups(self):
        admin = self._ref('group_app_admin')
        self.assertEqual(admin.all_implied_ids, admin)
        for xmlid in GROUP_XMLIDS:
            if xmlid == 'group_app_admin':
                continue
            self.assertNotIn(self._ref(xmlid), admin.all_implied_ids)
        access = admin.model_access
        self.assertEqual(len(access), 1)
        self.assertEqual(access.model_id.model, 'cpla.company.policy')
        self.assertTrue(access.perm_read)
        self.assertTrue(access.perm_write)
        self.assertTrue(access.perm_create)
        self.assertFalse(access.perm_unlink)
        self.assertEqual(
            admin.menu_access,
            self._ref('menu_cpla_root') | self._ref('menu_cpla_configuration'),
        )
        self.assertNotIn(self.env.ref('base.group_system'), admin.all_implied_ids)

    def test_sec_t007_no_public_portal_or_unrestricted_acl(self):
        groups = self._groups()
        standard = self.env['res.groups']
        for xmlid in STANDARD_GROUPS:
            standard |= self.env.ref(xmlid)
        for group in groups:
            self.assertFalse(group.share)
            self.assertFalse(group.all_implied_ids & standard)
            self.assertFalse(group.user_ids)
        self.assertFalse(self.env['ir.model.access'].search([
            ('model_id.model', '=', 'cpla.company.policy'),
            ('group_id', '=', False),
        ]))
        self.assertTrue(self._ref('group_contract_user').model_access)
        self.assertFalse(self._ref('group_sales_pricing_reviewer').model_access)
        self.assertFalse(self._ref('group_recovery_operator').model_access)
        rules = self.env['ir.rule'].search([
            ('model_id.model', '=', 'cpla.company.policy'),
        ])
        self.assertEqual(len(rules), 1)
        self.assertFalse(rules.groups)
        self.assertIn('company_id', rules.domain_force)
        contract_groups = self._ref('group_contract_user') | self._ref('group_contract_manager')
        contract_models = {
            'cpla.customer.contract',
            'cpla.customer.contract.line',
            'cpla.customer.contract.evidence',
            'cpla.customer.contract.version',
            'cpla.customer.contract.version.line',
            'cpla.customer.contract.version.tier',
            'cpla.customer.contract.version.evidence',
            'cpla.customer.contract.version.event',
            'cpla.discount.concession',
            'cpla.discount.approval',
            'cpla.discount.event',
        }
        grouped_rules = self.env['ir.rule'].search([('groups', 'in', groups.ids)])
        self.assertTrue(grouped_rules)
        for rule in grouped_rules:
            self.assertIn(rule.model_id.model, contract_models)
            self.assertFalse(rule.groups - contract_groups)
        self.assertFalse(self.env['ir.rule'].search([
            ('groups', 'in', (groups - contract_groups).ids),
        ]))
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', 'in', ['ir.attachment', 'ir.actions.report', 'ir.cron', 'ir.actions.server']),
        ]))
        registry_models = [
            model._name
            for model in self.env.registry.values()
            if getattr(model, '_module', None) == MODULE
        ]
        introduced = [name for name in registry_models if name.startswith('cpla.')]
        extended = [name for name in registry_models if not name.startswith('cpla.')]
        # Odoo sets _module to the last extender. Another installed module may
        # load after this one and keep sale.order attributed to that module.
        self.assertLessEqual(set(extended), {
            'sale.order',
            'sale.order.line',
            'account.move',
            'ir.attachment',
        })
        self.assertEqual(set(introduced), {
            'cpla.company.policy',
            'cpla.customer.contract',
            'cpla.customer.contract.line',
            'cpla.customer.contract.evidence',
            'cpla.customer.contract.version',
            'cpla.customer.contract.version.line',
            'cpla.customer.contract.version.evidence',
            'cpla.customer.contract.version.event',
            'cpla.customer.contract.version.compare',
            'cpla.customer.contract.version.tier',
            'cpla.pricing.applicability',
            'cpla.pricing.applicability.check',
            'cpla.pricing.quantity',
            'cpla.pricing.financial',
            'cpla.discount.concession',
            'cpla.discount.approval',
            'cpla.discount.event',
            'cpla.discount.evaluator',
            'cpla.quotation.compliance',
            'cpla.sale.price.lock',
            'cpla.quotation.override.request',
            'cpla.invoice.source',
            'cpla.invoice.source.map',
            'cpla.invoice.source.allocation',
            'cpla.invoice.source.verification',
            'cpla.invoice.source.verification.line',
            'cpla.invoice.audit.run',
            'cpla.invoice.audit.result',
            'cpla.leakage.finding',
            'cpla.leakage.case',
            'cpla.leakage.case.membership',
            'cpla.leakage.case.event',
            'cpla.leakage.case.checklist',
            'cpla.leakage.case.evidence',
            'cpla.leakage.case.submission',
            'cpla.leakage.case.wizard',
            'cpla.leakage.reassessment',
            'cpla.leakage.reassessment.event',
            'cpla.leakage.reassessment.wizard',
            'cpla.finance.validation.policy',
            'cpla.finance.validation.policy.level',
            'cpla.finance.validation',
            'cpla.finance.validation.line',
            'cpla.finance.validation.approval',
            'cpla.finance.validation.wizard',
            'cpla.recovery.policy',
            'cpla.recovery.policy.level',
            'cpla.recovery.request',
            'cpla.recovery.request.line',
            'cpla.recovery.waiver',
            'cpla.recovery.dispute',
            'cpla.recovery.settlement',
            'cpla.recovery.event',
            'cpla.recovery.balance',
            'cpla.recovery.wizard',
            'cpla.recovery.billing.policy',
            'cpla.recovery.billing',
            'cpla.recovery.billing.line',
            'cpla.recovery.accounting.link',
            'cpla.recovery.collection.evidence',
            'cpla.recovery.accounting.adjustment',
        })
        root = Manifest.for_addon(MODULE).path
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name for name in dirnames
                if name not in ('tests', '__pycache__', 'docs', 'local_testing')
            ]
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                with open(os.path.join(dirpath, filename), encoding='utf-8') as handle:
                    text = handle.read()
                self.assertNotIn('sudo(', text, filename)
                self.assertNotIn('.execute(', text, filename)

    def test_sec_t029_contract_user_plus_finance_reviewer_stays_in_scope(self):
        user = self._user(
            'cpla_t029',
            'group_contract_user',
            'group_finance_reviewer',
        )
        self.assertEqual(self._app_membership(user), (
            self._ref('group_contract_user') | self._ref('group_finance_reviewer')
        ))
        self.assertTrue(user._has_group(f'{MODULE}.group_contract_user'))
        self.assertTrue(user._has_group(f'{MODULE}.group_finance_reviewer'))
        self.assertFalse(user._has_group(f'{MODULE}.group_contract_manager'))
        self.assertFalse(user._has_group(f'{MODULE}.group_finance_manager'))
        self.assertFalse(user._has_group(f'{MODULE}.group_recovery_operator'))
        self.assertFalse(user._has_group(f'{MODULE}.group_app_admin'))

    def test_sec_t030_finance_manager_plus_operator_does_not_merge_duties(self):
        user = self._user(
            'cpla_t030',
            'group_finance_manager',
            'group_recovery_operator',
        )
        expected = (
            self._ref('group_finance_manager')
            | self._ref('group_finance_reviewer')
            | self._ref('group_recovery_operator')
        )
        self.assertEqual(self._app_membership(user), expected)
        self.assertFalse(
            self._ref('group_finance_manager').all_implied_ids
            & self._ref('group_recovery_operator')
        )
        self.assertFalse(
            self._ref('group_recovery_operator').all_implied_ids
            & self._ref('group_finance_manager')
        )
        self.assertFalse(user._has_group(f'{MODULE}.group_app_admin'))

    def test_sec_t031_auditor_plus_contract_user_cannot_approve(self):
        user = self._user(
            'cpla_t031',
            'group_internal_auditor',
            'group_contract_user',
        )
        self.assertEqual(self._app_membership(user), (
            self._ref('group_internal_auditor') | self._ref('group_contract_user')
        ))
        for xmlid in (
            'group_finance_reviewer',
            'group_finance_manager',
            'group_recovery_operator',
            'group_contract_manager',
            'group_app_admin',
        ):
            self.assertFalse(user._has_group(f'{MODULE}.{xmlid}'))

    def test_sec_t032_removing_a_group_removes_that_privilege(self):
        user = self._user('cpla_t032', 'group_contract_user', 'group_finance_reviewer')
        self.assertTrue(user._has_group(f'{MODULE}.group_finance_reviewer'))
        user.write({
            'group_ids': [Command.unlink(self._ref('group_finance_reviewer').id)],
        })
        self.assertFalse(user._has_group(f'{MODULE}.group_finance_reviewer'))
        self.assertTrue(user._has_group(f'{MODULE}.group_contract_user'))
        self.assertTrue(user._has_group('base.group_user'))
        self.assertNotIn(self._ref('group_finance_reviewer'), user.all_group_ids)

    def test_company_context_does_not_change_group_membership(self):
        """Group membership is not derived from allowed_company_ids.

        This does not pass SEC-T008 through SEC-T015. Those require business
        records that do not exist yet.
        """
        currency = self.env.company.currency_id
        company_a = self.env['res.company'].create({
            'name': 'ABC India',
            'currency_id': currency.id,
        })
        company_b = self.env['res.company'].create({
            'name': 'ABC UAE',
            'currency_id': currency.id,
        })
        user = self._user('cpla_company_a', 'group_contract_user', company=company_a)
        self.assertEqual(user.company_ids, company_a)
        self.assertNotIn(company_b, user.company_ids)
        before = user.all_group_ids
        switched = user.with_context(allowed_company_ids=[company_b.id])
        self.assertEqual(switched.all_group_ids, before)
        self.assertFalse(switched._has_group(f'{MODULE}.group_finance_manager'))
