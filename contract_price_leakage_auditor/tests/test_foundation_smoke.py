import os

from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, tagged

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

FORBIDDEN_DATA_MODELS = (
    'ir.cron',
    'ir.actions.server',
    'ir.actions.report',
    'ir.attachment',
)


@tagged('post_install', '-at_install')
class TestDev01Foundation(TransactionCase):
    """Smoke tests for the DEV-01 foundation. They do not calculate prices."""

    def _ref(self, xmlid):
        return self.env.ref(f'{MODULE}.{xmlid}')

    def _groups(self):
        groups = self.env['res.groups']
        for xmlid in GROUP_XMLIDS:
            groups |= self._ref(xmlid)
        return groups

    def test_smoke_001_module_installation_state(self):
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        self.assertEqual(len(module), 1)
        self.assertEqual(module.state, 'installed')

    def test_smoke_002_manifest_metadata(self):
        manifest = Manifest.for_addon(MODULE)
        self.assertTrue(manifest)
        self.assertEqual(manifest['name'], 'Contract Price Leakage Auditor')
        self.assertTrue(str(manifest['version']).startswith('19.0.'))
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])
        self.assertEqual(manifest['license'], 'Other proprietary')
        self.assertFalse(manifest['author'])
        self.assertFalse(manifest['application'])
        self.assertFalse(manifest['auto_install'])
        self.assertTrue(manifest['installable'])
        self.assertNotIn('account', manifest['depends'])
        self.assertNotIn('mail', manifest['depends'])

    def test_smoke_003_import_initialization(self):
        import odoo.addons.contract_price_leakage_auditor as addon
        self.assertTrue(addon.__file__)
        self.assertTrue(addon.models)
        self.assertEqual(self.env['cpla.company.policy']._name, 'cpla.company.policy')
        self.assertEqual(self.env['cpla.customer.contract']._name, 'cpla.customer.contract')
        self.assertEqual(self.env['cpla.customer.contract.line']._name, 'cpla.customer.contract.line')
        self.assertEqual(
            self.env['cpla.customer.contract.evidence']._name,
            'cpla.customer.contract.evidence',
        )
        self.assertEqual(
            self.env['cpla.customer.contract.version']._name,
            'cpla.customer.contract.version',
        )
        self.assertEqual(
            self.env['cpla.customer.contract.version.line']._name,
            'cpla.customer.contract.version.line',
        )
        self.assertEqual(
            self.env['cpla.customer.contract.version.evidence']._name,
            'cpla.customer.contract.version.evidence',
        )
        self.assertEqual(
            self.env['cpla.customer.contract.version.event']._name,
            'cpla.customer.contract.version.event',
        )
        forbidden = [
            name for name in self.env.registry
            if name.startswith(('cpla.contract', 'cpla.audit'))
            or (
                name.startswith('cpla.leakage')
                and name != 'cpla.leakage.finding'
                and not name.startswith(('cpla.leakage.case', 'cpla.leakage.reassessment'))
            )
        ]
        self.assertFalse(forbidden)

    def test_smoke_004_declared_data_references(self):
        manifest = Manifest.for_addon(MODULE)
        data_files = list(manifest['data'])
        self.assertTrue(data_files)
        for relative in data_files:
            self.assertTrue(
                os.path.isfile(os.path.join(manifest.path, relative)),
                relative,
            )
        self._ref('module_category_contract_price_leakage')
        for xmlid in PRIVILEGE_XMLIDS:
            self._ref(xmlid)
        for xmlid in GROUP_XMLIDS:
            self._ref(xmlid)

    def test_smoke_005_initial_security_groups(self):
        groups = self._groups()
        self.assertEqual(len(groups), len(GROUP_XMLIDS))
        self.assertFalse(groups.user_ids)
        ruled = self._ref('group_contract_user') | self._ref('group_contract_manager')
        self.assertFalse((groups - ruled).rule_groups)
        self.assertTrue(ruled.rule_groups)
        self.assertFalse(self.env['ir.model.access'].search([
            ('model_id.model', '=like', 'cpla.%'),
            ('group_id', '=', False),
        ]))
        for xmlid in (
            'group_sales_pricing_reviewer',
            'group_recovery_operator',
        ):
            self.assertFalse(self._ref(xmlid).model_access)
            self.assertFalse(self._ref(xmlid).menu_access)
        contract_user = self._ref('group_contract_user')
        self.assertTrue(contract_user.model_access)
        self.assertTrue(contract_user.menu_access)
        for access in contract_user.model_access:
            if access.model_id.model == 'cpla.company.policy':
                self.assertTrue(access.perm_read)
                self.assertFalse(access.perm_write)
                self.assertFalse(access.perm_create)
                self.assertFalse(access.perm_unlink)
            elif access.model_id.model == 'cpla.customer.contract':
                self.assertTrue(access.perm_read)
                self.assertTrue(access.perm_write)
                self.assertTrue(access.perm_create)
                self.assertFalse(access.perm_unlink)
            elif access.model_id.model == 'cpla.customer.contract.version':
                self.assertTrue(access.perm_read)
                self.assertTrue(access.perm_write)
                self.assertTrue(access.perm_create)
                self.assertFalse(access.perm_unlink)
            elif access.model_id.model in (
                'cpla.customer.contract.version.event',
                'cpla.discount.event',
                'cpla.leakage.case.event',
                'cpla.leakage.case.submission',
            ):
                self.assertTrue(access.perm_read)
                self.assertFalse(access.perm_write)
                self.assertTrue(access.perm_create)
                self.assertFalse(access.perm_unlink)
            elif access.model_id.model == 'cpla.sale.price.lock':
                self.assertTrue(access.perm_read)
                self.assertFalse(access.perm_write)
                self.assertFalse(access.perm_create)
                self.assertFalse(access.perm_unlink)
            elif access.model_id.model in (
                'cpla.invoice.source.map',
                'cpla.invoice.source.allocation',
                'cpla.invoice.audit.run',
                'cpla.invoice.audit.result',
                'cpla.leakage.finding',
            ):
                self.assertTrue(access.perm_read)
                self.assertFalse(access.perm_write)
                self.assertFalse(access.perm_create)
                self.assertFalse(access.perm_unlink)
            elif access.model_id.model == 'cpla.leakage.case.membership':
                self.assertTrue(access.perm_read)
                self.assertTrue(access.perm_write)
                self.assertTrue(access.perm_create)
                self.assertFalse(access.perm_unlink)
            elif access.model_id.model in (
                'cpla.leakage.case',
                'cpla.leakage.case.checklist',
                'cpla.leakage.case.evidence',
            ):
                self.assertTrue(access.perm_read)
                self.assertTrue(access.perm_write)
                self.assertFalse(access.perm_create)
                self.assertFalse(access.perm_unlink)
            elif access.model_id.model in (
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
            ):
                self.assertTrue(access.perm_read)
                self.assertFalse(access.perm_write)
                self.assertFalse(access.perm_create)
                self.assertFalse(access.perm_unlink)
            else:
                self.assertTrue(access.perm_read)
                self.assertTrue(access.perm_write)
                self.assertTrue(access.perm_create)
                self.assertTrue(access.perm_unlink)
        manager = self._ref('group_contract_manager')
        policy_access = manager.model_access.filtered(
            lambda access: access.model_id.model == 'cpla.company.policy'
        )
        self.assertEqual(len(policy_access), 1)
        self.assertTrue(policy_access.perm_read)
        self.assertFalse(policy_access.perm_write)
        self.assertFalse(policy_access.perm_create)
        self.assertFalse(policy_access.perm_unlink)
        header_access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'cpla.customer.contract'),
        ])
        self.assertTrue(header_access)
        self.assertFalse(any(header_access.mapped('perm_unlink')))
        account_links = self.env['ir.model.data'].search([
            ('model', '=', 'res.groups'),
            ('res_id', 'in', groups.implied_ids.ids),
            ('module', '=', 'account'),
        ])
        self.assertFalse(account_links)
        user = self._ref('group_contract_user')
        manager = self._ref('group_contract_manager')
        self.assertEqual(manager.implied_ids, user)
        self.assertEqual(user.privilege_id, manager.privilege_id)
        reviewer = self._ref('group_finance_reviewer')
        finance_manager = self._ref('group_finance_manager')
        self.assertEqual(finance_manager.implied_ids, reviewer)
        self.assertNotEqual(user.privilege_id, reviewer.privilege_id)
        for xmlid in (
            'group_sales_pricing_reviewer',
            'group_recovery_operator',
            'group_internal_auditor',
            'group_app_admin',
        ):
            self.assertFalse(self._ref(xmlid).implied_ids)
        privileges = self.env['res.groups.privilege']
        for xmlid in PRIVILEGE_XMLIDS:
            privileges |= self._ref(xmlid)
        self.assertEqual(len(privileges), len(PRIVILEGE_XMLIDS))
        self.assertEqual(groups.privilege_id, privileges)

    def test_smoke_006_no_unauthorized_business_tables(self):
        owned = self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', 'in', list(FORBIDDEN_DATA_MODELS)),
        ])
        self.assertFalse(owned)
        leaked = [
            name for name in self.env.registry
            if name.startswith(('contract.price.', 'cpla.', 'contract_price_leakage.'))
        ]
        self.assertEqual(set(leaked), {
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

    def test_smoke_007_registry_and_dependency_loading(self):
        self.assertTrue(self.env.registry.ready)
        self.assertIn('res.groups', self.env.registry)
        self.assertIn('res.groups.privilege', self.env.registry)
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        self.assertEqual(module.dependencies_id.mapped('name'), ['base', 'product', 'sale'])
        self.assertEqual(set(module.dependencies_id.mapped('state')), {'installed'})

    def test_smoke_008_configuration_cardinality_is_stable(self):
        """XML IDs are stable. A second read must not show duplicate rows.

        The separate database update command is the install-update check.
        This assertion guards the same external IDs inside the test transaction.
        """
        domain = [('module', '=', MODULE)]
        first = self.env['ir.model.data'].search(domain)
        second = self.env['ir.model.data'].search(domain)
        self.assertEqual(first.ids, second.ids)
        models = set(first.mapped('model'))
        self.assertTrue({
            'ir.module.category',
            'res.groups.privilege',
            'res.groups',
            'ir.model',
            'ir.model.fields',
            'ir.model.access',
            'ir.rule',
            'ir.ui.view',
            'ir.ui.menu',
            'ir.actions.act_window',
        } <= models)
        self.assertFalse(models & set(FORBIDDEN_DATA_MODELS))
        self.assertEqual(len(first.mapped('name')), len(set(first.mapped('name'))))
        self.assertEqual(
            len(first.filtered(lambda row: row.model == 'res.groups')),
            len(GROUP_XMLIDS),
        )
