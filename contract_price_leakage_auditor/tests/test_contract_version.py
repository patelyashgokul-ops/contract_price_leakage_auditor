import base64
import sys
import threading
import traceback
import uuid

from odoo import Command, api, fields
from odoo.exceptions import AccessError, LockError, UserError, ValidationError
from odoo.modules.module import Manifest
from odoo.orm.registry import DummyRLock, Registry
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'


@tagged('post_install', '-at_install')
class TestDev05ContractVersion(TransactionCase):
    """Approved contract versions. These tests do not audit invoices."""

    @classmethod
    def setUpClass(cls):
        # Registered first so it runs after the test cursor closes and
        # releases the role-table locks taken by the other test users.
        cls.addClassCleanup(cls._clear_committed_role_membership)
        super().setUpClass()
        cls._commit_concurrency_pool()
        currency = cls.env.company.currency_id
        cls.company_a = cls.env['res.company'].create({
            'name': 'ABC India',
            'currency_id': currency.id,
        })
        cls.company_b = cls.env['res.company'].create({
            'name': 'ABC UAE',
            'currency_id': currency.id,
        })
        cls.owner = cls._make_user('cpla05_owner', 'group_contract_user', cls.company_a)
        cls.other_owner = cls._make_user('cpla05_owner2', 'group_contract_user', cls.company_a)
        cls.user_b = cls._make_user('cpla05_user_b', 'group_contract_user', cls.company_b)
        cls.manager = cls._make_user('cpla05_manager', 'group_contract_manager', cls.company_a)
        cls.manager_b = cls._make_user('cpla05_manager_b', 'group_contract_manager', cls.company_b)
        cls.reviewer = cls._make_user('cpla05_reviewer', 'group_finance_reviewer', cls.company_a)
        cls.finance_manager = cls._make_user('cpla05_fin_mgr', 'group_finance_manager', cls.company_a)
        cls.auditor = cls._make_user('cpla05_auditor', 'group_internal_auditor', cls.company_a)
        cls.app_admin = cls._make_user('cpla05_admin', 'group_app_admin', cls.company_a)
        cls.sales = cls._make_user('cpla05_sales', 'group_sales_pricing_reviewer', cls.company_a)
        cls.combined = cls._make_user(
            'cpla05_combined', 'group_contract_user', cls.company_a,
            extra_groups=('group_finance_reviewer', 'group_internal_auditor'),
        )
        cls.policy_a = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_a.id,
            'change_reason': 'Candidate reference for version snapshots. Not an operational approval.',
            'pricing_date_policy': 'order_confirmation',
        })
        cls.policy_b = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_b.id,
            'change_reason': 'Candidate reference for version snapshots. Not an operational approval.',
        })
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'XYZ Manufacturing',
            'is_company': True,
            'company_id': cls.company_a.id,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'UAE Buyer',
            'is_company': True,
            'company_id': cls.company_b.id,
        })
        cls.bearing_a = cls.env['product.product'].create({
            'name': 'Bearing A',
            'list_price': 9999.0,
            'company_id': False,
        })
        cls.bearing_b = cls.env['product.product'].create({
            'name': 'Bearing B',
            'list_price': 8888.0,
            'company_id': False,
        })
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.pack = cls.env['uom.uom'].create({
            'name': 'CPLA05 Pack of 6',
            'relative_uom_id': cls.unit.id,
            'relative_factor': 6.0,
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

    @classmethod
    def _commit_concurrency_pool(cls):
        """Commit users before this class locks the shared role rows.

        A second cursor cannot join those roles while setUpClass still holds
        the group rows. The pool is committed and reused by the concurrency
        tests. Role membership is removed when the class finishes. Version
        rows are not deleted.
        """
        token = uuid.uuid4().hex[:8]
        with cls.env.registry.cursor() as cursor:
            cursor.execute("SET lock_timeout = '8s'")
            env = api.Environment(cursor, api.SUPERUSER_ID, {})
            company = env['res.company'].create({
                'name': 'CPLA05 Conc Pool %s' % token,
                'currency_id': env.company.currency_id.id,
            })

            def make(login, xmlid):
                return new_test_user(
                    env,
                    login=login,
                    groups='base.group_user,%s.%s' % (MODULE, xmlid),
                    password='cpla-test',
                    company_id=company.id,
                    company_ids=[Command.set([company.id])],
                )

            owner = make('cpla05_pool_owner_%s' % token, 'group_contract_user')
            manager = make('cpla05_pool_mgr_%s' % token, 'group_contract_manager')
            finance = make('cpla05_pool_fin_%s' % token, 'group_finance_manager')
            policy = env['cpla.company.policy'].create({
                'company_id': company.id,
                'change_reason': 'Concurrency pool. Not an operational approval.',
            })
            partner = env['res.partner'].create({
                'name': 'Pool Buyer %s' % token,
                'is_company': True,
                'company_id': company.id,
            })
            product = env['product.product'].create({
                'name': 'Pool Bearing %s' % token,
                'list_price': 9999.0,
                'company_id': False,
            })
            cursor.commit()
            cls.pool = {
                'company_id': company.id,
                'owner_id': owner.id,
                'manager_id': manager.id,
                'finance_id': finance.id,
                'policy_id': policy.id,
                'partner_id': partner.id,
                'product_id': product.id,
            }

    @classmethod
    def _clear_committed_role_membership(cls):
        """Drop committed APP 04 role membership and concurrency-pool rows.

        Later security tests require these groups to have no users. The
        policy cardinality test requires no committed policy rows. Only
        companies named like the concurrency pool are deleted.
        """
        registry = getattr(cls, 'registry', None)
        if registry is None:
            return
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        xmlids = (
            'group_contract_user',
            'group_contract_manager',
            'group_sales_pricing_reviewer',
            'group_finance_reviewer',
            'group_finance_manager',
            'group_recovery_operator',
            'group_internal_auditor',
            'group_app_admin',
        )
        with registry.cursor() as cursor:
            cursor.execute("SET lock_timeout = '8s'")
            env = api.Environment(cursor, api.SUPERUSER_ID, {MODULE_UNINSTALL_FLAG: True})
            groups = env['res.groups']
            for xmlid in xmlids:
                groups |= env.ref('%s.%s' % (MODULE, xmlid))
            users = groups.user_ids
            if users:
                internal = env.ref('base.group_user')
                users.write({'group_ids': [Command.set(internal.ids)]})
            cursor.execute(
                "SELECT id FROM res_company WHERE name LIKE %s",
                ('CPLA05 Conc Pool%',),
            )
            company_ids = [row[0] for row in cursor.fetchall()]
            if company_ids:
                cls._delete_pool_company_rows(cursor, company_ids)
            cursor.commit()

    @classmethod
    def _delete_pool_company_rows(cls, cursor, company_ids):
        """Remove disposable concurrency rows that restrict foreign keys block.

        Version lines, evidence, and policies use ondelete restrict, and an
        approved line write does not honor the uninstall flag. Null the
        pointers, then delete children before parents. This runs only for
        companies created by the concurrency pool.
        """
        statements = (
            """UPDATE cpla_customer_contract_version_line
               SET origin_line_id = NULL, contract_line_id = NULL
               WHERE company_id = ANY(%s)""",
            """UPDATE cpla_customer_contract_version_evidence
               SET origin_evidence_id = NULL, source_evidence_id = NULL
               WHERE company_id = ANY(%s)""",
            """UPDATE cpla_customer_contract_version_event
               SET source_version_id = NULL, supersedes_version_id = NULL
               WHERE company_id = ANY(%s)""",
            """UPDATE cpla_customer_contract_version
               SET source_version_id = NULL, supersedes_version_id = NULL, policy_id = NULL
               WHERE company_id = ANY(%s)""",
            """UPDATE cpla_customer_contract
               SET policy_id = NULL
               WHERE company_id = ANY(%s)""",
            """UPDATE cpla_company_policy
               SET supersedes_id = NULL
               WHERE company_id = ANY(%s)""",
            """DELETE FROM cpla_version_covered_partner_rel
               WHERE version_id IN (
                   SELECT id FROM cpla_customer_contract_version WHERE company_id = ANY(%s)
               )""",
            """DELETE FROM cpla_customer_contract_covered_partner_rel
               WHERE contract_id IN (
                   SELECT id FROM cpla_customer_contract WHERE company_id = ANY(%s)
               )""",
            """DELETE FROM ir_attachment
               WHERE res_model = 'cpla.customer.contract.version.evidence'
                 AND res_id IN (
                     SELECT id FROM cpla_customer_contract_version_evidence
                     WHERE company_id = ANY(%s)
                 )""",
            """DELETE FROM ir_attachment
               WHERE res_model = 'cpla.customer.contract.evidence'
                 AND res_id IN (
                     SELECT id FROM cpla_customer_contract_evidence
                     WHERE company_id = ANY(%s)
                 )""",
            "DELETE FROM cpla_customer_contract_version_event WHERE company_id = ANY(%s)",
            "DELETE FROM cpla_customer_contract_version_evidence WHERE company_id = ANY(%s)",
            "DELETE FROM cpla_customer_contract_version_line WHERE company_id = ANY(%s)",
            "DELETE FROM cpla_customer_contract_version WHERE company_id = ANY(%s)",
            "DELETE FROM cpla_customer_contract_evidence WHERE company_id = ANY(%s)",
            "DELETE FROM cpla_customer_contract_line WHERE company_id = ANY(%s)",
            "DELETE FROM cpla_customer_contract WHERE company_id = ANY(%s)",
            "DELETE FROM cpla_company_policy WHERE company_id = ANY(%s)",
        )
        for statement in statements:
            cursor.execute(statement, (company_ids,))

    def _env(self, user, companies=None):
        companies = companies or user.company_ids
        return self.env(user=user, context={
            **self.env.context,
            'allowed_company_ids': list(companies.ids),
        })

    def _today(self):
        return fields.Date.context_today(self)

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

    def _ready_contract(self, owner=None, company=None, partner=None, policy=None,
                        products=None, price=1000.0, valid_from=None, valid_to=None):
        owner = owner or self.owner
        company = company or self.company_a
        partner = partner or self.partner_a
        policy = policy or (self.policy_a if company == self.company_a else self.policy_b)
        valid_from = valid_from or self._on(-30)
        valid_to = valid_to or self._on(180)
        env = self._env(owner, company)
        contract = env['cpla.customer.contract'].create({
            'name': 'Negotiated supply',
            'company_id': company.id,
            'partner_id': partner.id,
            'owner_id': owner.id,
            'currency_id': company.currency_id.id,
            'valid_from': valid_from,
            'valid_to': valid_to,
            'policy_id': policy.id,
        })
        lines = products or [(self.bearing_a, price)]
        for product, line_price in lines:
            env['cpla.customer.contract.line'].create({
                'contract_id': contract.id,
                'product_id': product.id,
                'price_unit': line_price,
                'uom_id': product.uom_id.id,
            })
        env['cpla.customer.contract.evidence'].create({
            'contract_id': contract.id,
            'name': 'signed-agreement.pdf',
            'document_type': 'signed_agreement',
            'source_reference': 'AGR-001',
            'description': 'Signed pricing schedule.',
            'datas': base64.b64encode(b'signed agreement'),
        })
        contract.action_submit_for_review()
        return contract

    def _approve_v1(self, **kwargs):
        contract = self._ready_contract(**kwargs)
        env = self._env(self.manager, contract.company_id)
        version = env['cpla.customer.contract.version'].approve_initial(
            env['cpla.customer.contract'].browse(contract.id)
        )
        return version

    def _amend(self, version, user=None, effective_days=14, reason='Price amendment'):
        user = user or self.owner
        env = self._env(user, version.company_id)
        amendment = env['cpla.customer.contract.version'].browse(version.id).create_amendment()
        amendment.write({
            'amendment_reason': reason,
            'effective_from': self._on(effective_days),
        })
        return amendment

    def _submit(self, version, user=None):
        user = user or self.owner
        env = self._env(user, version.company_id)
        record = env['cpla.customer.contract.version'].browse(version.id)
        record.action_submit_for_review()
        return record

    def _approve(self, version, user=None):
        user = user or self.finance_manager
        env = self._env(user, version.company_id)
        record = env['cpla.customer.contract.version'].browse(version.id)
        if record.state == 'draft':
            self._submit(record)
            record = env['cpla.customer.contract.version'].browse(version.id)
        record.action_approve()
        return record

    def _price(self, version, product):
        line = version.line_ids.filtered(lambda item: item.product_id == product)
        self.assertEqual(len(line), 1)
        return line.price_unit

    def test_ver_t001_initial_version_from_ready_contract(self):
        contract = self._ready_contract(price=1000.0)
        self.assertEqual(contract.state, 'ready_for_review')
        self.assertNotIn('approved', dict(contract._fields['state'].selection))
        version = self._env(self.manager, self.company_a)['cpla.customer.contract.version'].approve_initial(
            self._env(self.manager, self.company_a)['cpla.customer.contract'].browse(contract.id)
        )
        self.assertEqual(version.state, 'approved')
        self.assertEqual(version.version_number, 1)
        self.assertEqual(len(version.line_ids), 1)
        self.assertEqual(version.approved_by_id, self.manager)
        self.assertTrue(version.approved_at)
        self.assertNotEqual(fields.Date.to_date(version.approved_at), version.effective_from)
        self.assertTrue(version.contract_id.audit_authoritative)
        self.assertEqual(version.contract_id.state, 'ready_for_review')
        self.assertEqual(len(version.event_ids.filtered(lambda event: event.event_type == 'approved')), 1)

    def test_contract_v001_draft_save_does_not_approve(self):
        version = self._approve_v1(price=1000.0)
        self.assertEqual(version.partner_id.name, 'XYZ Manufacturing')
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)
        self.assertNotEqual(self._price(version, self.bearing_a), self.bearing_a.list_price)

    def test_ver_t002_version_number_unique_within_contract(self):
        first = self._approve_v1()
        second = self._approve(self._amend(first))
        self.assertEqual(first.version_number, 1)
        self.assertEqual(second.version_number, 2)
        with self.assertRaises(UserError):
            second.write({'version_number': 1})

    def test_ver_t003_version_reference_is_stable(self):
        version = self._approve_v1()
        self.assertEqual(version.reference, '%s/V0001' % version.contract_id.reference)
        with self.assertRaises(UserError):
            version.write({'reference': 'CHANGED'})

    def test_ver_t004_company_ownership_matches_parent(self):
        version = self._approve_v1()
        self.assertEqual(version.company_id, self.company_a)
        self.assertEqual(version.line_ids.company_id, self.company_a)
        self.assertEqual(version.evidence_ids.company_id, self.company_a)

    def test_ver_t005_source_contract_relationship(self):
        version = self._approve_v1()
        amendment = self._amend(version)
        self.assertEqual(version.contract_id, amendment.contract_id)
        self.assertEqual(amendment.source_version_id, version)
        self.assertFalse(version.source_version_id)

    def test_ver_t006_customer_scope_snapshot(self):
        version = self._approve_v1()
        self.assertEqual(version.partner_id, self.partner_a)
        self.assertEqual(version.partner_name, 'XYZ Manufacturing')
        self.partner_a.write({'name': 'Renamed Manufacturing'})
        self.assertEqual(version.partner_name, 'XYZ Manufacturing')

    def test_ver_t007_currency_snapshot_is_not_converted(self):
        version = self._approve_v1(price=1000.0)
        self.assertEqual(version.currency_id, self.company_a.currency_id)
        self.assertEqual(version.line_ids.currency_id, version.currency_id)
        self.assertEqual(version.line_ids.price_unit, 1000.0)

    def test_ver_t008_product_line_snapshots(self):
        version = self._approve_v1(products=[
            (self.bearing_a, 1000.0),
            (self.bearing_b, 1500.0),
        ])
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)
        self.assertEqual(self._price(version, self.bearing_b), 1500.0)
        self.assertEqual(version.line_ids.filtered(
            lambda line: line.product_id == self.bearing_a
        ).product_name, 'Bearing A')

    def test_ver_t009_effective_date(self):
        start = self._on(-10)
        version = self._approve_v1(valid_from=start, valid_to=self._on(90))
        self.assertEqual(version.effective_from, start)
        self.assertEqual(version.effective_status, 'currently_effective')

    def test_ver_t010_missing_evidence_is_rejected(self):
        version = self._approve_v1()
        amendment = self._amend(version)
        amendment.evidence_ids.unlink()
        with self.assertRaises(UserError):
            self._submit(amendment)
        self.assertEqual(amendment.state, 'draft')
        self.assertFalse(amendment.approved_by_id)

    def test_ver_t011_failed_approval_leaves_no_partial_snapshot(self):
        version = self._approve_v1()
        amendment = self._submit(self._amend(version, effective_days=-1))
        with self.assertRaises(UserError):
            self._env(self.finance_manager, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(amendment.id).action_approve()
        self.assertEqual(amendment.state, 'ready_for_review')
        self.assertFalse(amendment.approved_by_id)
        self.assertFalse(amendment.approval_reference)
        self.assertEqual(version.state, 'approved')

    def test_ver_t012_approved_version_survives_parent_edits(self):
        version = self._approve_v1(price=1000.0)
        with self.assertRaises(UserError):
            version.contract_id.write({'description': 'Changed after approval'})
        self.bearing_a.write({'list_price': 1.0})
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)

    def test_amd_t001_authorized_draft_amendment(self):
        amendment = self._amend(self._approve_v1())
        self.assertEqual(amendment.state, 'draft')
        self.assertEqual(amendment.requested_by_id, self.owner)
        self.assertFalse(amendment.approved_by_id)
        self.assertFalse(amendment.approved_at)

    def test_amd_t002_source_approved_version_is_preserved(self):
        source = self._approve_v1(price=1000.0)
        price = self._price(source, self.bearing_a)
        self._amend(source)
        self.assertEqual(source.state, 'approved')
        self.assertEqual(self._price(source, self.bearing_a), price)

    def test_amd_t003_draft_amendment_is_not_approved(self):
        amendment = self._amend(self._approve_v1())
        self.assertNotEqual(amendment.state, 'approved')
        self.assertFalse(amendment.contract_id.version_ids.filtered(
            lambda version: version.state == 'approved' and version != amendment.source_version_id
        ))

    def test_amd_t004_changed_product_price_is_proposed(self):
        source = self._approve_v1(products=[(self.bearing_a, 1000.0), (self.bearing_b, 1500.0)])
        amendment = self._amend(source)
        line = amendment.line_ids.filtered(lambda item: item.product_id == self.bearing_a)
        line.write({'price_unit': 1200.0})
        self.assertEqual(line.price_unit, 1200.0)
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)

    def test_amd_t005_unchanged_product_price_is_retained(self):
        source = self._approve_v1(products=[(self.bearing_a, 1000.0), (self.bearing_b, 1500.0)])
        amendment = self._amend(source)
        amendment.line_ids.filtered(lambda item: item.product_id == self.bearing_a).write({
            'price_unit': 1200.0,
        })
        self.assertEqual(self._price(amendment, self.bearing_b), 1500.0)

    def test_amd_t006_removed_product_is_explicit_in_comparison(self):
        source = self._approve_v1(products=[(self.bearing_a, 1000.0), (self.bearing_b, 1500.0)])
        amendment = self._amend(source)
        amendment.line_ids.filtered(lambda item: item.product_id == self.bearing_b).unlink()
        approved = self._approve(amendment)
        comparison = source.compare_with(approved)
        removed = [row for row in comparison['lines'] if row['category'] == 'Removed Product']
        self.assertTrue(removed)
        self.assertEqual(self._price(source, self.bearing_b), 1500.0)
        self.assertFalse(approved.line_ids.filtered(lambda item: item.product_id == self.bearing_b))

    def test_amd_t007_new_product_is_included(self):
        source = self._approve_v1(products=[(self.bearing_a, 1000.0)])
        amendment = self._amend(source)
        amendment.env['cpla.customer.contract.version.line'].create({
            'version_id': amendment.id,
            'product_id': self.bearing_b.id,
            'price_unit': 1500.0,
            'uom_id': self.bearing_b.uom_id.id,
        })
        approved = self._approve(amendment)
        self.assertEqual(self._price(approved, self.bearing_b), 1500.0)
        added = [
            row for row in source.compare_with(approved)['lines']
            if row['category'] == 'Added Product'
        ]
        self.assertTrue(added)

    def test_amd_t008_invalid_effective_date_is_rejected(self):
        amendment = self._amend(self._approve_v1(), effective_days=400)
        with self.assertRaises(UserError):
            self._submit(amendment)
        self.assertEqual(amendment.state, 'draft')

    def test_amd_t009_approval_requires_authority(self):
        amendment = self._submit(self._amend(self._approve_v1()))
        with self.assertRaises(AccessError):
            self._env(self.owner, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(amendment.id).action_approve()
        approved = self._approve(amendment, user=self.finance_manager)
        self.assertEqual(approved.state, 'approved')
        self.assertEqual(approved.approved_by_id, self.finance_manager)

    def test_amd_t010_rejected_amendment_does_not_affect_prior_version(self):
        source = self._approve_v1(price=1000.0)
        amendment = self._amend(source)
        amendment.line_ids.write({'price_unit': 900.0})
        amendment = self._submit(amendment)
        env = self._env(self.manager, self.company_a)
        record = env['cpla.customer.contract.version'].browse(amendment.id)
        record.write({'rejection_reason': 'Price cut is not accepted.'})
        record.action_reject()
        self.assertEqual(record.state, 'rejected')
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)
        self.assertFalse(record.supersedes_version_id)
        self.assertTrue(record.event_ids.filtered(lambda event: event.event_type == 'rejected'))

    def test_amd_t011_future_dated_amendment_stays_scheduled(self):
        source = self._approve_v1()
        approved = self._approve(self._amend(source, effective_days=14))
        self.assertEqual(approved.state, 'approved')
        self.assertEqual(approved.effective_status, 'scheduled')
        self.assertEqual(source.effective_status, 'currently_effective')
        self.assertNotEqual(approved.effective_status, 'currently_effective')

    def test_amd_t012_supersession_relationship(self):
        source = self._approve_v1()
        approved = self._approve(self._amend(source))
        self.assertEqual(approved.supersedes_version_id, source)
        self.assertFalse(source.supersedes_version_id)
        self.assertIn(approved, source.superseded_by_ids)
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)

    def test_amd_t013_amendment_draft_cannot_modify_approved_snapshot(self):
        source = self._approve_v1(price=1000.0)
        amendment = self._amend(source)
        amendment.line_ids.write({'price_unit': 1200.0})
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)
        with self.assertRaises(UserError):
            source.line_ids.write({'price_unit': 1200.0})

    def test_amd_t014_direct_child_line_write_cannot_mutate_history(self):
        version = self._approve_v1(price=1000.0)
        with self.assertRaises(UserError):
            self._env(self.manager, self.company_a)[
                'cpla.customer.contract.version.line'
            ].browse(version.line_ids.id).write({'price_unit': 50.0})
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)

    def test_amd_t015_retroactive_amendment_requires_policy(self):
        amendment = self._submit(self._amend(self._approve_v1(), effective_days=-1))
        self.assertTrue(amendment.reassessment_required)
        with self.assertRaises(UserError) as caught:
            self._env(self.finance_manager, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(amendment.id).action_approve()
        self.assertIn('Retroactive', str(caught.exception))
        self.assertEqual(amendment.state, 'ready_for_review')
        self.assertEqual(amendment.retroactivity_policy, 'not_authorized')

    def test_amd_t016_retroactive_attempt_preserves_as_known_at_history(self):
        source = self._approve_v1(price=1000.0)
        approved_at = source.approved_at
        amendment = self._submit(self._amend(source, effective_days=-1))
        finance = self._env(self.finance_manager, self.company_a)
        record = finance['cpla.customer.contract.version'].browse(amendment.id)
        self.assertTrue(record.reassessment_required)
        record._record_retroactive_block()
        self.env.flush_all()
        self.assertTrue(record.event_ids.filtered(
            lambda event: event.event_type == 'historical_reassessment_required'
        ))
        with self.assertRaises(UserError) as caught:
            record.action_approve()
        self.assertIn('Retroactive', str(caught.exception))
        self.assertEqual(source.approved_at, approved_at)
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)
        self.assertEqual(record.state, 'ready_for_review')
        self.assertFalse(record.approved_by_id)
        self.assertFalse(record.snapshot_sha256)
        self.assertTrue(record.reassessment_required)
        self.assertFalse(source.event_ids.filtered(
            lambda event: event.event_type == 'historical_reassessment_required'
        ))
        self.assertTrue(record.event_ids.filtered(
            lambda event: event.event_type == 'historical_reassessment_required'
        ))

    def test_amd_t017_reassessment_does_not_run_invoice_audits(self):
        before = self.env['account.move'].search_count([]) if 'account.move' in self.env.registry else None
        amendment = self._submit(self._amend(self._approve_v1(), effective_days=-1))
        with self.assertRaises(UserError):
            self._env(self.manager, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(amendment.id).action_approve()
        self.assertTrue(amendment.reassessment_required)
        self.assertFalse(self.env['cpla.leakage.finding'].search_count([]))
        self.assertFalse(self.env['cpla.invoice.audit.result'].search_count([]))
        if before is not None:
            self.assertEqual(self.env['account.move'].search_count([]), before)

    def test_amd_t018_stale_draft_is_not_approved(self):
        source = self._approve_v1()
        stale = self._amend(source, effective_days=20)
        newer = self._approve(self._amend(source, effective_days=10))
        self.assertEqual(newer.supersedes_version_id, source)
        with self.assertRaises(UserError) as caught:
            self._submit(stale)
        self.assertIn('Stale', str(caught.exception))
        self.assertEqual(stale.state, 'draft')
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)

    def test_contract_v002_prospective_increase_keeps_both_versions(self):
        source = self._approve_v1(price=1000.0)
        amendment = self._amend(source, effective_days=14)
        amendment.line_ids.write({'price_unit': 1200.0})
        approved = self._approve(amendment)
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)
        self.assertEqual(self._price(approved, self.bearing_a), 1200.0)
        self.assertEqual(approved.effective_status, 'scheduled')
        self.assertTrue(approved.event_ids.filtered(lambda event: event.event_type == 'supersession_recorded'))
        self.assertNotIn('account.move', approved._fields)

    def test_contract_v003_multiple_products_comparison(self):
        source = self._approve_v1(products=[(self.bearing_a, 1000.0), (self.bearing_b, 1500.0)])
        amendment = self._amend(source)
        amendment.line_ids.filtered(lambda line: line.product_id == self.bearing_a).write({
            'price_unit': 1200.0,
        })
        approved = self._approve(amendment)
        comparison = source.compare_with(approved)
        by_product = {row['product']: row for row in comparison['lines']}
        self.assertEqual(by_product['Bearing A']['category'], 'Price Increased')
        self.assertEqual(by_product['Bearing A']['price_delta'], 200.0)
        self.assertEqual(by_product['Bearing B']['category'], 'No Change')
        self.assertFalse(comparison['is_recovered_cash'])
        self.assertEqual(self._price(source, self.bearing_b), 1500.0)

    def test_contract_v004_rejected_amendment(self):
        source = self._approve_v1(price=1000.0)
        amendment = self._submit(self._amend(source))
        env = self._env(self.manager, self.company_a)
        record = env['cpla.customer.contract.version'].browse(amendment.id)
        record.write({'rejection_reason': 'Below the approved price.'})
        record.action_reject()
        self.assertEqual(record.state, 'rejected')
        self.assertEqual(source.effective_status, 'currently_effective')

    def test_contract_v005_contract_user_cannot_approve(self):
        amendment = self._submit(self._amend(self._approve_v1()))
        with self.assertRaises(AccessError):
            self._env(self.owner, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(amendment.id).action_approve()
        self.assertEqual(amendment.state, 'ready_for_review')
        self.assertFalse(amendment.supersedes_version_id)

    def test_contract_v006_future_dated_version_is_not_effective_early(self):
        approved = self._approve(self._amend(self._approve_v1(), effective_days=21))
        self.assertEqual(approved.state, 'approved')
        self.assertEqual(approved.effective_status, 'scheduled')
        self.assertGreater(approved.effective_from, self._today())

    def test_contract_v007_retroactive_amendment_is_blocked(self):
        source = self._approve_v1(price=1000.0)
        amendment = self._submit(self._amend(source, effective_days=-1))
        with self.assertRaises(UserError):
            self._approve(amendment)
        self.assertTrue(amendment.reassessment_required)
        self.assertEqual(source.state, 'approved')
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)

    def test_contract_v009_stale_source_blocks_automatic_supersession(self):
        source = self._approve_v1()
        stale = self._submit(self._amend(source, effective_days=30))
        self._approve(self._amend(source, effective_days=12))
        with self.assertRaises(UserError):
            self._approve(stale)
        self.assertNotEqual(stale.state, 'approved')

    def test_his_t001_v1_price_preserved_after_v2(self):
        source = self._approve_v1(price=1000.0)
        self._approve(self._amend(source))
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)

    def test_his_t002_v2_price_is_independent(self):
        source = self._approve_v1(price=1000.0)
        amendment = self._amend(source)
        amendment.line_ids.write({'price_unit': 1200.0})
        approved = self._approve(amendment)
        self.assertEqual(self._price(approved, self.bearing_a), 1200.0)
        self.assertEqual(self._price(source, self.bearing_a), 1000.0)

    def test_his_t003_list_price_change_does_not_mutate_version_price(self):
        version = self._approve_v1(price=1000.0)
        self.bearing_a.write({'list_price': 50.0})
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)

    def test_his_t004_product_archival_does_not_erase_snapshot(self):
        version = self._approve_v1()
        self.bearing_a.write({'active': False})
        self.assertTrue(version.line_ids.product_id)
        self.assertEqual(version.line_ids.product_name, 'Bearing A')

    def test_his_t005_contract_description_update_does_not_rewrite_history(self):
        version = self._approve_v1()
        snapshot = version.description
        # A submitted header is frozen, including its description. The rejected
        # write cannot rewrite the approved version snapshot.
        with self.assertRaises(UserError):
            version.contract_id.write({'description': 'Header note'})
        self.assertEqual(version.description, snapshot)
        self.assertNotEqual(version.contract_id.description, 'Header note')

    def test_his_t006_approved_version_write_is_rejected(self):
        version = self._approve_v1(price=1000.0)
        with self.assertRaises(UserError):
            self._env(self.manager, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(version.id).write({'description': 'Rewrite'})
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)

    def test_his_t007_approved_line_write_is_rejected(self):
        version = self._approve_v1(price=1000.0)
        with self.assertRaises(UserError):
            version.line_ids.with_user(self.manager).write({'price_unit': 1.0})
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)

    def test_his_t008_approved_version_unlink_is_rejected(self):
        version = self._approve_v1()
        with self.assertRaises(UserError):
            version.unlink()
        self.assertTrue(version.exists())

    def test_his_t009_approved_line_unlink_is_rejected(self):
        version = self._approve_v1()
        with self.assertRaises(UserError):
            version.line_ids.unlink()
        self.assertTrue(version.line_ids.exists())

    def test_his_t010_approval_event_history_is_preserved(self):
        version = self._approve_v1()
        event = version.event_ids.filtered(lambda item: item.event_type == 'approved')
        self.assertEqual(len(event), 1)
        self.assertEqual(event.actor_id, self.manager)
        self.assertLess(abs((event.occurred_at - version.approved_at).total_seconds()), 5)
        with self.assertRaises(UserError):
            event.write({'reason': 'changed'})
        with self.assertRaises(UserError):
            event.unlink()

    def test_his_t011_comparison_identifies_changed_terms(self):
        source = self._approve_v1(products=[(self.bearing_a, 1000.0), (self.bearing_b, 1500.0)])
        amendment = self._amend(source)
        amendment.line_ids.filtered(lambda line: line.product_id == self.bearing_a).write({
            'price_unit': 1200.0,
        })
        line = amendment.line_ids.filtered(lambda item: item.product_id == self.bearing_a)
        line.write({'uom_id': self.pack.id})
        comparison = source.compare_with(amendment)
        categories = {row['category'] for row in comparison['lines']}
        self.assertIn('UoM Changed', categories)
        self.assertTrue(comparison['normalization_required'])
        changed = [row for row in comparison['lines'] if row['category'] == 'UoM Changed']
        self.assertIsNone(changed[0]['price_delta'])
        self.assertFalse(comparison['is_recovered_cash'])

    def test_his_t012_repeated_approval_does_not_duplicate_authority(self):
        version = self._approve_v1()
        again = self._env(self.manager, self.company_a)[
            'cpla.customer.contract.version'
        ].approve_initial(self._env(self.manager, self.company_a)[
            'cpla.customer.contract'
        ].browse(version.contract_id.id))
        self.assertEqual(again, version)
        version.action_approve()
        self.assertEqual(len(version.contract_id.version_ids.filtered(
            lambda item: item.state == 'approved'
        )), 1)
        self.assertEqual(len(version.event_ids.filtered(
            lambda event: event.event_type == 'approved'
        )), 1)

    def test_his_t013_history_remains_after_parent_cancel_is_refused(self):
        version = self._approve_v1()
        with self.assertRaises(UserError):
            version.contract_id.action_cancel()
        self.assertTrue(version.exists())
        self.assertEqual(version.state, 'approved')
        self.assertTrue(self._env(self.auditor, self.company_a)[
            'cpla.customer.contract.version'
        ].browse(version.id).reference)

    def test_his_t014_effective_date_boundaries(self):
        source = self._approve_v1(valid_from=self._on(-10), valid_to=self._on(90))
        scheduled = self._approve(self._amend(source, effective_days=5))
        self.assertEqual(scheduled.effective_status, 'scheduled')
        self.assertEqual(source.effective_status, 'currently_effective')
        self.assertEqual(source.authority_to, self._on(4))
        boundary = self._approve_v1(valid_from=self._on(-10), valid_to=self._on(90))
        current = self._approve(self._amend(boundary, effective_days=0))
        self.assertEqual(current.effective_status, 'currently_effective')
        self.assertEqual(boundary.effective_status, 'superseded')
        self.assertTrue(boundary.historically_effective)
        self.assertEqual(boundary.authority_to, self._on(-1))

    def test_his_t015_overlapping_approved_authority_is_rejected(self):
        source = self._approve_v1()
        first = self._amend(source, effective_days=10)
        second = self._amend(source, effective_days=10)
        self._approve(first)
        with self.assertRaises(UserError) as caught:
            self._approve(second)
        self.assertIn('No price was selected', str(caught.exception))
        self.assertNotEqual(second.state, 'approved')

    def test_his_t016_supersession_does_not_erase_prior_snapshot(self):
        source = self._approve_v1(price=1000.0)
        checksum = source.snapshot_sha256
        approved_at = source.approved_at
        self._approve(self._amend(source))
        self.assertEqual(source.snapshot_sha256, checksum)
        self.assertEqual(source.approved_at, approved_at)
        self.assertEqual(source.state, 'approved')

    def test_sec05_t001_manager_can_review_permitted_version(self):
        version = self._approve_v1(price=1000.0)
        env = self._env(self.manager, self.company_a)
        record = env['cpla.customer.contract.version'].browse(version.id)
        record.check_access('read')
        self.assertEqual(record.line_ids.price_unit, 1000.0)
        self.assertIn('Approve', record.get_view(view_type='form')['arch'])

    def test_sec05_t002_contract_user_cannot_approve(self):
        amendment = self._submit(self._amend(self._approve_v1()))
        with self.assertRaises(AccessError):
            self._env(self.owner, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(amendment.id).action_approve()

    def test_sec05_t003_self_approval_is_prohibited(self):
        contract = self._ready_contract(owner=self.manager)
        with self.assertRaises(AccessError) as caught:
            self._env(self.manager, self.company_a)[
                'cpla.customer.contract.version'
            ].approve_initial(self._env(self.manager, self.company_a)[
                'cpla.customer.contract'
            ].browse(contract.id))
        self.assertIn('Self-approval', str(caught.exception))
        self.assertFalse(contract.version_ids)

    def test_sec05_t004_finance_reviewer_cannot_approve(self):
        amendment = self._submit(self._amend(self._approve_v1()))
        with self.assertRaises(AccessError):
            self._env(self.reviewer, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(amendment.id).action_approve()

    def test_sec05_t005_application_administrator_cannot_approve(self):
        version = self._approve_v1()
        with self.assertRaises(AccessError):
            self._env(self.app_admin, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(version.id).read(['reference'])

    def test_sec05_t006_company_a_user_cannot_read_company_b_version(self):
        version = self._env(self.manager_b, self.company_b)['cpla.customer.contract.version'].approve_initial(
            self._env(self.manager_b, self.company_b)['cpla.customer.contract'].browse(
                self._ready_contract(
                    owner=self.user_b, company=self.company_b, partner=self.partner_b,
                ).id
            )
        )
        env = self._env(self.owner, self.company_a)
        self.assertFalse(env['cpla.customer.contract.version'].search([('id', '=', version.id)]))
        with self.assertRaises(AccessError):
            env['cpla.customer.contract.version'].browse(version.id).read(['reference'])

    def test_sec05_t007_company_a_cannot_approve_company_b(self):
        contract = self._ready_contract(
            owner=self.user_b, company=self.company_b, partner=self.partner_b,
        )
        with self.assertRaises(AccessError):
            self._env(self.manager, self.company_a)[
                'cpla.customer.contract.version'
            ].approve_initial(self._env(self.manager, self.company_a)[
                'cpla.customer.contract'
            ].browse(contract.id))
        self.assertFalse(contract.version_ids.filtered(lambda version: version.state == 'approved'))

    def test_sec05_t008_cross_company_line_is_rejected(self):
        version = self._approve_v1()
        foreign = self.env['product.product'].create({
            'name': 'UAE Only Bearing',
            'company_id': self.company_b.id,
        })
        amendment = self._amend(version)
        with self.assertRaises(UserError):
            amendment.env['cpla.customer.contract.version.line'].create({
                'version_id': amendment.id,
                'product_id': foreign.id,
                'price_unit': 10.0,
                'uom_id': foreign.uom_id.id,
            })

    def test_sec05_t009_unauthorized_evidence_read_is_rejected(self):
        version = self._approve_v1()
        env = self._env(self.user_b, self.company_b)
        self.assertFalse(env['cpla.customer.contract.version.evidence'].search([
            ('id', 'in', version.evidence_ids.ids),
        ]))
        with self.assertRaises(AccessError):
            env['cpla.customer.contract.version.evidence'].browse(
                version.evidence_ids.id
            ).read(['name'])

    def test_sec05_t010_direct_rpc_approval_bypass_is_rejected(self):
        amendment = self._submit(self._amend(self._approve_v1()))
        env = self._env(self.manager, self.company_a)
        record = env['cpla.customer.contract.version'].browse(amendment.id)
        with self.assertRaises(UserError):
            record.write({'state': 'approved', 'approved_by_id': self.manager.id})
        self.assertEqual(record.state, 'ready_for_review')
        with self.assertRaises(UserError):
            env['cpla.customer.contract.version'].create({
                'contract_id': record.contract_id.id,
                'state': 'approved',
                'partner_id': self.partner_a.id,
                'currency_id': self.company_a.currency_id.id,
                'source_version_id': record.source_version_id.id,
            })

    def test_sec05_t011_child_line_mutation_cannot_bypass_immutability(self):
        version = self._approve_v1(price=1000.0)
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)[
                'cpla.customer.contract.version.line'
            ].browse(version.line_ids.id).write({'price_unit': 5.0})
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)

    def test_sec05_t012_combined_groups_stay_inside_company_and_owner(self):
        hidden = self._approve_v1(owner=self.other_owner, price=700.0)
        foreign = self._env(self.manager_b, self.company_b)['cpla.customer.contract.version'].approve_initial(
            self._env(self.manager_b, self.company_b)['cpla.customer.contract'].browse(
                self._ready_contract(
                    owner=self.user_b, company=self.company_b, partner=self.partner_b, price=40.0,
                ).id
            )
        )
        env = self._env(self.combined, self.company_a)
        found = env['cpla.customer.contract.version'].search([])
        self.assertNotIn(hidden, found)
        self.assertNotIn(foreign, found)
        with self.assertRaises(AccessError):
            env['cpla.customer.contract.version'].browse(foreign.id).action_approve()

    def test_sec05_t013_auditor_cannot_alter_approved_price(self):
        version = self._approve_v1(price=1000.0)
        with self.assertRaises(AccessError):
            self._env(self.auditor, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(version.id).write({'description': 'auditor edit'})
        self.assertEqual(self._price(version, self.bearing_a), 1000.0)

    def test_sec05_t014_unauthorized_history_export_is_denied(self):
        version = self._approve_v1()
        rows = self._env(self.auditor, self.company_a)[
            'cpla.customer.contract.version'
        ].browse(version.id).history_rows()
        self.assertEqual(rows[0]['reference'], version.reference)
        with self.assertRaises(AccessError):
            self._env(self.sales, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(version.id).history_rows()
        with self.assertRaises(AccessError):
            self._env(self.user_b, self.company_b)[
                'cpla.customer.contract.version'
            ].browse(version.id).history_rows()

    def test_sec05_t015_restricted_cancel_and_reject_are_denied(self):
        amendment = self._submit(self._amend(self._approve_v1()))
        owner_env = self._env(self.owner, self.company_a)
        record = owner_env['cpla.customer.contract.version'].browse(amendment.id)
        with self.assertRaises(AccessError):
            record.action_reject()
        with self.assertRaises(AccessError):
            record.action_cancel()
        self.assertEqual(record.state, 'ready_for_review')

    def test_con05_t004_failed_approval_does_not_leave_partial_snapshot(self):
        amendment = self._submit(self._amend(self._approve_v1(), effective_days=-1))
        with self.assertRaises(UserError):
            self._env(self.finance_manager, self.company_a)[
                'cpla.customer.contract.version'
            ].browse(amendment.id).action_approve()
        self.assertFalse(amendment.approved_by_id)
        self.assertFalse(amendment.snapshot_sha256)
        self.assertNotEqual(amendment.state, 'approved')

    def test_con05_t005_repeated_approval_is_idempotent(self):
        source = self._approve_v1()
        approved = self._approve(self._amend(source))
        events = len(approved.event_ids)
        lines = len(approved.line_ids)
        approved.action_approve()
        self.assertEqual(len(approved.event_ids), events)
        self.assertEqual(len(approved.line_ids), lines)
        self.assertEqual(len(approved.contract_id.version_ids.filtered(
            lambda version: version.state == 'approved' and version.version_number == approved.version_number
        )), 1)

    def test_con05_t006_supersession_chronology_stays_consistent(self):
        first = self._approve_v1(valid_from=self._on(-20), valid_to=self._on(180))
        second = self._approve(self._amend(first, effective_days=7))
        self.assertEqual(second.supersedes_version_id, first)
        self.assertEqual(first.effective_status, 'currently_effective')
        self.assertEqual(second.effective_status, 'scheduled')
        self.assertLess(first.version_number, second.version_number)
        self.assertLess(first.effective_from, second.effective_from)

    def test_contract_v008_and_con05_concurrent_approval(self):
        self._run_concurrent_approval()

    def test_con05_t001_simultaneous_approvals_do_not_duplicate(self):
        self._run_concurrent_approval()

    def test_con05_t002_concurrent_version_numbers_stay_unique(self):
        self._run_concurrent_numbering()

    def test_con05_t003_concurrent_amendments_detect_stale_source(self):
        self._run_concurrent_stale()

    def test_contract_v010_cross_company_approval_is_denied(self):
        contract = self._ready_contract(
            owner=self.user_b, company=self.company_b, partner=self.partner_b, price=50.0,
        )
        with self.assertRaises(AccessError):
            self._env(self.manager, self.company_a)[
                'cpla.customer.contract.version'
            ].approve_initial(
                self._env(self.manager, self.company_a)[
                    'cpla.customer.contract'
                ].browse(contract.id)
            )
        self.assertFalse(contract.version_ids)

    def test_reg05_t001_installed_module_matches_manifest(self):
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(module.state, 'installed')
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(module.latest_version, '19.0.1.15.0')
        self.assertIn('cpla.customer.contract.version', self.env.registry)

    def test_reg05_t003_existing_contract_model_is_preserved(self):
        contract = self._ready_contract()
        self.assertEqual(contract.state, 'ready_for_review')
        self.assertTrue(contract.reference.startswith('CPL/'))

    def test_reg05_t004_existing_contract_lines_are_preserved(self):
        contract = self._ready_contract(price=1000.0)
        self.assertEqual(contract.line_ids.price_unit, 1000.0)
        self.assertEqual(contract.line_ids.product_id, self.bearing_a)

    def test_reg05_t005_prior_test_modules_remain_loaded(self):
        suite = self.env['ir.module.module'].search([('name', '=', MODULE)])
        self.assertEqual(suite.state, 'installed')
        from odoo.addons.contract_price_leakage_auditor.tests import test_customer_contract
        self.assertTrue(test_customer_contract.TestDev04CustomerContract)

    def test_reg05_t006_views_menus_and_security_load(self):
        model = self.env['cpla.customer.contract.version']
        for view_type in ('list', 'form', 'search'):
            loaded = model.get_view(view_type=view_type)
            self.assertTrue(loaded['arch'])
        # Superuser is not a Contract Manager, so get_view removes those buttons.
        form = self._env(self.manager, self.company_a)[
            'cpla.customer.contract.version'
        ].get_view(view_type='form')
        self.assertIn('action_approve', form['arch'])
        self.assertIn('action_create_amendment', form['arch'])
        contract_form = self.env['cpla.customer.contract'].get_view(view_type='form')
        self.assertIn('not an approved price', contract_form['arch'])
        self.assertEqual(self.env.ref('%s.menu_cpla_contract_versions' % MODULE).name, 'Contract Versions')
        self.assertEqual(self.env.ref('%s.menu_cpla_amendment_review' % MODULE).name, 'Amendment Review')

    def test_reg05_t007_version_xml_ids_are_unique(self):
        for xmlid in (
            'cpla_customer_contract_version_company_rule',
            'cpla_customer_contract_version_owner_rule',
            'cpla_customer_contract_version_manager_rule',
            'action_cpla_customer_contract_version',
            'menu_cpla_contract_versions',
            'menu_cpla_amendment_review',
        ):
            self.assertEqual(self.env['ir.model.data'].search_count([
                ('module', '=', MODULE),
                ('name', '=', xmlid),
            ]), 1)

    def test_reg05_t008_no_accounting_records_are_created(self):
        self.assertNotIn('account.move', self.env['cpla.customer.contract.version']._fields)
        version = self._approve_v1()
        self.assertTrue(version.snapshot_sha256)
        if 'account.move' in self.env.registry:
            self.assertFalse(self.env['account.move'].search([
                ('ref', '=', version.reference),
            ]))

    def test_reg05_t009_no_invoice_audit_jobs_are_created(self):
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'ir.cron'),
        ]))

    def test_reg05_t010_configuration_policies_remain_intact(self):
        self.assertFalse(self.policy_a.operationally_approved)
        self.assertNotEqual(self.policy_a.state, 'approved_ready')
        version = self._approve_v1()
        self.assertEqual(version.pricing_date_policy_snapshot, 'order_confirmation')
        self.assertEqual(version.amount_threshold_policy, 'not_configured')
        self.assertFalse(self.policy_a.operationally_approved)

    def test_gold_fin_002_both_prices_and_policy_are_preserved(self):
        """Future applicability fixture only. This does not calculate leakage."""
        first = self._approve_v1(price=1000.0)
        amendment = self._amend(first, effective_days=14)
        amendment.line_ids.write({'price_unit': 1200.0})
        second = self._approve(amendment)
        self.assertEqual(self._price(first, self.bearing_a), 1000.0)
        self.assertEqual(self._price(second, self.bearing_a), 1200.0)
        self.assertEqual(second.pricing_date_policy_snapshot, 'order_confirmation')
        self.assertNotIn('25000', second.change_summary or '')
        self.assertFalse(second.compare_with(first)['is_recovered_cash'])

    def _pool_approved_version(self, cursor, name, filename, payload):
        pool = self.pool
        company_id = pool['company_id']
        owner_env = api.Environment(cursor, pool['owner_id'], {
            'allowed_company_ids': [company_id],
        })
        company = owner_env['res.company'].browse(company_id)
        product = owner_env['product.product'].browse(pool['product_id'])
        contract = owner_env['cpla.customer.contract'].create({
            'name': name,
            'company_id': company_id,
            'partner_id': pool['partner_id'],
            'owner_id': pool['owner_id'],
            'currency_id': company.currency_id.id,
            'valid_from': self._on(-10),
            'valid_to': self._on(120),
            'policy_id': pool['policy_id'],
        })
        owner_env['cpla.customer.contract.line'].create({
            'contract_id': contract.id,
            'product_id': product.id,
            'price_unit': 1000.0,
            'uom_id': product.uom_id.id,
        })
        owner_env['cpla.customer.contract.evidence'].create({
            'contract_id': contract.id,
            'name': filename,
            'document_type': 'signed_agreement',
            'datas': base64.b64encode(payload),
        })
        contract.action_submit_for_review()
        manager_env = api.Environment(cursor, pool['manager_id'], {
            'allowed_company_ids': [company_id],
        })
        version = manager_env['cpla.customer.contract.version'].approve_initial(
            manager_env['cpla.customer.contract'].browse(contract.id)
        )
        return owner_env, version

    def _run_workers(self, threads):
        """Run worker threads that open their own environments.

        The Odoo test runner holds Registry._lock for the whole suite.
        A worker that builds an Environment calls Registry() and would
        wait on that lock until the suite ends. The dummy lock lets the
        workers construct the existing registry. The server still holds
        the original lock object.
        """
        held = Registry._lock
        Registry._lock = DummyRLock()
        try:
            for thread in threads:
                thread.daemon = True
                thread.start()
            for thread in threads:
                thread.join(30)
                if thread.is_alive():
                    frame = sys._current_frames().get(thread.ident)
                    stack = ''.join(traceback.format_stack(frame)) if frame else 'no stack'
                    self.fail('Worker still running:\n%s' % stack)
        finally:
            Registry._lock = held

    def _run_concurrent_approval(self):
        registry = self.env.registry
        pool = self.pool
        with registry.cursor() as cursor:
            cursor.execute("SET lock_timeout = '8s'")
            owner_env, version = self._pool_approved_version(
                cursor, 'Concurrent approval', 'conc.pdf', b'concurrent',
            )
            amendment = owner_env['cpla.customer.contract.version'].browse(version.id).create_amendment()
            amendment.write({
                'amendment_reason': 'Concurrent approval',
                'effective_from': self._on(9),
            })
            amendment.action_submit_for_review()
            cursor.commit()
            company_id = pool['company_id']
            amendment_id = amendment.id
            actor_ids = [pool['manager_id'], pool['finance_id']]
        results = []
        barrier = threading.Barrier(2)

        def approve(user_id):
            try:
                with registry.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '12s'")
                    env = api.Environment(cursor, user_id, {'allowed_company_ids': [company_id]})
                    barrier.wait(timeout=20)
                    env['cpla.customer.contract.version'].browse(amendment_id).action_approve()
                    cursor.commit()
                    results.append('ok')
            except Exception as error:
                results.append('%s: %s' % (type(error).__name__, error))

        threads = [threading.Thread(target=approve, args=(user_id,)) for user_id in actor_ids]
        self._run_workers(threads)
        with registry.cursor() as cursor:
            env = api.Environment(cursor, self.env.uid, {'allowed_company_ids': [company_id]})
            approved = env['cpla.customer.contract.version'].browse(amendment_id)
            approved_count = env['cpla.customer.contract.version'].search_count([
                ('id', '=', amendment_id),
                ('state', '=', 'approved'),
            ])
            event_count = env['cpla.customer.contract.version.event'].search_count([
                ('version_id', '=', amendment_id),
                ('event_type', '=', 'approved'),
            ])
            supersession_count = env['cpla.customer.contract.version.event'].search_count([
                ('version_id', '=', amendment_id),
                ('event_type', '=', 'supersession_recorded'),
            ])
            state = approved.state
        self.assertEqual(approved_count, 1)
        self.assertEqual(event_count, 1)
        self.assertEqual(supersession_count, 1)
        self.assertTrue(any(item == 'ok' for item in results), results)
        self.assertTrue(all(
            item == 'ok'
            or item.startswith(('LockError', 'SerializationFailure'))
            or 'could not serialize' in item
            or 'Stale' in item
            or 'already' in item.lower()
            for item in results
        ), results)
        self.assertEqual(state, 'approved')

    def _run_concurrent_numbering(self):
        registry = self.env.registry
        pool = self.pool
        with registry.cursor() as cursor:
            cursor.execute("SET lock_timeout = '8s'")
            _owner_env, version = self._pool_approved_version(
                cursor, 'Concurrent numbering', 'num.pdf', b'number',
            )
            cursor.commit()
            company_id = pool['company_id']
            contract_id = version.contract_id.id
            version_id = version.id
            owner_id = pool['owner_id']
        results = []
        barrier = threading.Barrier(2)

        def create_amendment():
            try:
                with registry.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '12s'")
                    env = api.Environment(cursor, owner_id, {'allowed_company_ids': [company_id]})
                    barrier.wait(timeout=20)
                    created = env['cpla.customer.contract.version'].browse(version_id).create_amendment()
                    cursor.commit()
                    results.append(created.version_number)
            except Exception as error:
                results.append('%s: %s' % (type(error).__name__, error))

        threads = [threading.Thread(target=create_amendment) for _index in range(2)]
        self._run_workers(threads)
        numbers = [item for item in results if isinstance(item, int)]
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertTrue(numbers or any(str(item).startswith('LockError') for item in results), results)
        with registry.cursor() as cursor:
            env = api.Environment(cursor, self.env.uid, {'allowed_company_ids': [company_id]})
            found = env['cpla.customer.contract.version'].search([
                ('contract_id', '=', contract_id),
            ])
            self.assertEqual(len(found.mapped('version_number')), len(set(found.mapped('version_number'))))

    def _run_concurrent_stale(self):
        registry = self.env.registry
        pool = self.pool
        with registry.cursor() as cursor:
            cursor.execute("SET lock_timeout = '8s'")
            owner_env, version = self._pool_approved_version(
                cursor, 'Concurrent stale', 'stale.pdf', b'stale',
            )
            first = owner_env['cpla.customer.contract.version'].browse(version.id).create_amendment()
            second = owner_env['cpla.customer.contract.version'].browse(version.id).create_amendment()
            first.write({'amendment_reason': 'First', 'effective_from': self._on(11)})
            second.write({'amendment_reason': 'Second', 'effective_from': self._on(16)})
            first.action_submit_for_review()
            second.action_submit_for_review()
            cursor.commit()
            company_id = pool['company_id']
            draft_ids = [first.id, second.id]
            actor_ids = [pool['manager_id'], pool['finance_id']]
        results = []
        barrier = threading.Barrier(2)

        def approve(user_id, version_id):
            try:
                with registry.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '12s'")
                    env = api.Environment(cursor, user_id, {'allowed_company_ids': [company_id]})
                    barrier.wait(timeout=20)
                    env['cpla.customer.contract.version'].browse(version_id).action_approve()
                    cursor.commit()
                    results.append('ok')
            except Exception as error:
                results.append('%s: %s' % (type(error).__name__, error))

        threads = [
            threading.Thread(target=approve, args=(actor_ids[index], draft_ids[index]))
            for index in range(2)
        ]
        self._run_workers(threads)
        with registry.cursor() as cursor:
            env = api.Environment(cursor, self.env.uid, {'allowed_company_ids': [company_id]})
            approved = env['cpla.customer.contract.version'].search_count([
                ('id', 'in', draft_ids),
                ('state', '=', 'approved'),
            ])
        self.assertEqual(approved, 1)
        self.assertTrue(results)
        self.assertTrue(any(
            item == 'ok'
            or 'LockError' in item
            or 'SerializationFailure' in item
            or 'could not serialize' in item
            or 'Stale' in item
            or 'Conflicting' in item
            or 'not approved' in item
            for item in results
        ), results)
