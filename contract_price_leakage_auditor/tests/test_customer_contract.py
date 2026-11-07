import base64
import re
from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'


@tagged('post_install', '-at_install')
class TestDev04CustomerContract(TransactionCase):
    """Draft customer contracts. These tests do not audit invoices."""

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
        cls.user_a = cls._make_user('cpla04_user_a', 'group_contract_user', cls.company_a)
        cls.user_a2 = cls._make_user('cpla04_user_a2', 'group_contract_user', cls.company_a)
        cls.user_b = cls._make_user('cpla04_user_b', 'group_contract_user', cls.company_b)
        cls.manager_a = cls._make_user('cpla04_manager_a', 'group_contract_manager', cls.company_a)
        cls.manager_both = cls._make_user(
            'cpla04_manager_both', 'group_contract_manager', cls.company_a,
            companies=cls.company_a | cls.company_b,
        )
        cls.finance_a = cls._make_user('cpla04_finance_a', 'group_finance_reviewer', cls.company_a)
        cls.auditor_a = cls._make_user('cpla04_auditor_a', 'group_internal_auditor', cls.company_a)
        cls.admin_a = cls._make_user('cpla04_admin_a', 'group_app_admin', cls.company_a)
        cls.sales_a = cls._make_user('cpla04_sales_a', 'group_sales_pricing_reviewer', cls.company_a)
        cls.recovery_a = cls._make_user('cpla04_recovery_a', 'group_recovery_operator', cls.company_a)
        cls.combined_a = cls._make_user(
            'cpla04_combined_a', 'group_contract_user', cls.company_a,
            extra_groups=('group_finance_reviewer', 'group_internal_auditor'),
        )
        cls.policy_a = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_a.id,
            'change_reason': 'Current reference for draft contracts. Not an approval.',
        })
        cls.policy_b = cls.env['cpla.company.policy'].create({
            'company_id': cls.company_b.id,
            'change_reason': 'Current reference for draft contracts. Not an approval.',
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
        cls.shared_partner = cls.env['res.partner'].create({
            'name': 'Shared Buyer',
            'is_company': True,
            'company_id': False,
        })
        cls.product_bearing = cls.env['product.product'].create({
            'name': 'Industrial Bearing',
            'list_price': 9999.0,
            'company_id': False,
        })
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.pack = cls.env['uom.uom'].create({
            'name': 'CPLA Pack of 6',
            'relative_uom_id': cls.unit.id,
            'relative_factor': 6.0,
        })
        cls.inr = cls.env.ref('base.INR')
        cls.usd = cls.env.ref('base.USD')
        cls.aed = cls.env.ref('base.AED')

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

    def _env_as(self, user, companies):
        return self.env(user=user, context={
            **self.env.context,
            'allowed_company_ids': list(companies.ids),
        })

    def _contract_vals(self, company, partner, owner, currency, policy, **extra):
        values = {
            'name': extra.pop('name', 'Negotiated supply'),
            'company_id': company.id,
            'partner_id': partner.id if partner else False,
            'owner_id': owner.id,
            'currency_id': currency.id if currency else False,
            'valid_from': extra.pop('valid_from', date(2026, 7, 1)),
            'valid_to': extra.pop('valid_to', date(2026, 12, 31)),
            'policy_id': policy.id if policy else False,
        }
        values.update(extra)
        return values

    def _create_contract(self, user, companies, **values):
        return self._env_as(user, companies)['cpla.customer.contract'].create(values)

    def _line_vals(self, product, price, uom=None, **extra):
        values = {
            'product_id': product.id,
            'price_unit': price,
            'uom_id': (uom or product.uom_id).id,
        }
        values.update(extra)
        return values

    def _add_line(self, contract, product, price, uom=None, **extra):
        return contract.env['cpla.customer.contract.line'].create({
            'contract_id': contract.id,
            **self._line_vals(product, price, uom, **extra),
        })

    def _add_evidence(self, contract, content=b'signed agreement'):
        return contract.env['cpla.customer.contract.evidence'].create({
            'contract_id': contract.id,
            'name': 'signed-agreement.pdf',
            'document_type': 'signed_agreement',
            'source_reference': 'AGR-001',
            'description': 'Signed pricing schedule.',
            'datas': base64.b64encode(content),
        })

    def _full_draft(self, user=None, company=None, partner=None, currency=None,
                    product=None, price=1200.0, policy=None, **extra):
        user = user or self.user_a
        company = company or self.company_a
        partner = partner if partner is not None else self.partner_a
        currency = currency if currency is not None else company.currency_id
        product = product or self.product_bearing
        if policy is None:
            policy = self.policy_a if company == self.company_a else self.policy_b
        contract = self._create_contract(user, company, **self._contract_vals(
            company, partner, user, currency, policy, **extra,
        ))
        if product and price is not None:
            self._add_line(contract, product, price)
        return contract

    def _states(self):
        field = self.env['cpla.customer.contract']._fields['state']
        return dict(field._description_selection(self.env))

    def test_cth_t001_contract_user_creates_a_draft(self):
        contract = self._create_contract(self.user_a, self.company_a, **self._contract_vals(
            self.company_a, self.partner_a, self.user_a, self.company_a.currency_id, self.policy_a,
        ))
        self.assertEqual(contract.state, 'draft')
        self.assertEqual(contract.owner_id, self.user_a)
        self.assertEqual(contract.company_id, self.company_a)
        self.assertFalse(contract.audit_authoritative)
        self.assertNotIn('message_ids', contract._fields)

    def test_cth_t002_contract_manager_creates_a_draft(self):
        contract = self._create_contract(self.manager_a, self.company_a, **self._contract_vals(
            self.company_a, self.partner_a, self.manager_a, self.company_a.currency_id, self.policy_a,
            name='Manager draft',
        ))
        self.assertEqual(contract.owner_id, self.manager_a)
        self.assertEqual(contract.state, 'draft')
        self.assertEqual(contract.company_id, self.company_a)

    def test_cth_t003_contract_reference_is_generated(self):
        first = self._full_draft()
        second = self._full_draft(name='Second agreement')
        self.assertRegex(first.reference, r'^CPL/2026/\d{5}$')
        self.assertRegex(second.reference, r'^CPL/2026/\d{5}$')
        self.assertNotEqual(first.reference, second.reference)
        first.write({'name': 'Renamed draft'})
        self.assertRegex(first.reference, r'^CPL/2026/\d{5}$')

    def test_cth_t004_contract_reference_is_unique_per_company(self):
        first = self._full_draft()
        with self.assertRaises(ValidationError):
            self._create_contract(self.user_a, self.company_a, **self._contract_vals(
                self.company_a, self.partner_a, self.user_a, self.company_a.currency_id, self.policy_a,
                reference=first.reference,
            ))
        with self.assertRaises(UserError):
            first.write({'reference': 'CPL/2026/99999'})
        self.assertRegex(first.reference, r'^CPL/2026/\d{5}$')

    def test_cth_t005_company_default_follows_the_active_company(self):
        env = self._env_as(self.user_a, self.company_a)
        contract = env['cpla.customer.contract'].create({
            'partner_id': self.partner_a.id,
            'currency_id': self.company_a.currency_id.id,
        })
        self.assertEqual(contract.company_id, self.company_a)
        self.assertEqual(contract.owner_id, self.user_a)

    def test_cth_t006_company_customer_is_accepted(self):
        contract = self._full_draft()
        self.assertEqual(contract.partner_id, self.partner_a)
        self.assertEqual(contract.commercial_partner_id, self.partner_a)

    def test_cth_t007_shared_customer_is_accepted(self):
        contract = self._full_draft(partner=self.shared_partner)
        self.assertFalse(contract.partner_id.company_id)
        self.assertEqual(contract.company_id, self.company_a)

    def test_cth_t008_wrong_company_customer_is_rejected(self):
        # The caller can name the other company's partner. Odoo then rejects
        # the company inconsistency with UserError before a contract is stored.
        with self.assertRaises(UserError) as caught:
            self._create_contract(self.user_a, self.company_a, **self._contract_vals(
                self.company_a, self.partner_b, self.user_a, self.company_a.currency_id, self.policy_a,
            ))
        self.assertIn('company', str(caught.exception).lower())

    def test_cth_t009_currency_is_stored_separately_from_company_currency(self):
        rates_before = self.env['res.currency.rate'].search_count([('currency_id', '=', self.usd.id)])
        active_before = self.usd.active
        contract = self._full_draft(currency=self.usd, price=100.0)
        self.assertEqual(contract.currency_id, self.usd)
        self.assertEqual(contract.company_currency_id, self.company_a.currency_id)
        self.assertEqual(contract.line_ids.currency_id, self.usd)
        self.assertEqual(contract.line_ids.price_unit, 100.0)
        self.assertEqual(self.usd.active, active_before)
        self.assertEqual(
            self.env['res.currency.rate'].search_count([('currency_id', '=', self.usd.id)]),
            rates_before,
        )

    def test_cth_t010_missing_currency_blocks_review(self):
        contract = self._full_draft(currency=False, product=False, price=None)
        self._add_evidence(contract)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('currency', str(caught.exception).lower())
        self.assertEqual(contract.state, 'draft')

    def test_cth_t011_valid_date_range_is_accepted(self):
        contract = self._full_draft(valid_from=date(2026, 7, 1), valid_to=date(2026, 12, 31))
        self.assertEqual(contract.valid_from, date(2026, 7, 1))
        self.assertEqual(contract.valid_to, date(2026, 12, 31))

    def test_cth_t012_end_date_before_start_date_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            self._full_draft(valid_from=date(2026, 12, 31), valid_to=date(2026, 7, 1))
        self.assertIn('not swapped', str(caught.exception).lower())

    def test_cth_t013_open_ended_draft_cannot_be_submitted(self):
        contract = self._full_draft(valid_to=False)
        self._add_evidence(contract)
        self.assertEqual(contract.state, 'draft')
        self.assertFalse(contract.valid_to)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('Valid To', str(caught.exception))
        self.assertEqual(contract.state, 'draft')

    def test_cth_t014_contract_owner_is_stored(self):
        contract = self._full_draft()
        self.assertEqual(contract.owner_id, self.user_a)
        self.assertNotEqual(contract.owner_id, self.env.ref('base.user_root'))
        self.assertTrue(contract.create_uid)
        self.assertTrue(contract.create_date)

    def test_cth_t015_unauthorized_owner_or_company_change_is_rejected(self):
        contract = self._full_draft()
        with self.assertRaises(UserError):
            contract.write({'owner_id': self.user_a2.id})
        with self.assertRaises(UserError):
            contract.write({'company_id': self.company_b.id})
        with self.assertRaises(AccessError):
            self._create_contract(self.user_a, self.company_a, **self._contract_vals(
                self.company_b, self.partner_b, self.user_a, self.company_b.currency_id, self.policy_b,
            ))
        manager_contract = self._full_draft(user=self.manager_a)
        with self.assertRaises(ValidationError):
            manager_contract.write({'owner_id': self.finance_a.id})
        manager_contract.write({'owner_id': self.user_a2.id})
        self.assertEqual(manager_contract.owner_id, self.user_a2)

    def test_ctl_t001_valid_product_line_is_created(self):
        contract = self._full_draft(price=1200.0)
        line = contract.line_ids
        self.assertEqual(line.product_id, self.product_bearing)
        self.assertEqual(line.contract_id, contract)
        self.assertEqual(len(contract.line_ids), 1)

    def test_ctl_t002_product_variant_is_stored(self):
        attribute = self.env['product.attribute'].create({
            'name': 'Bearing Series',
            'create_variant': 'always',
            'value_ids': [Command.create({'name': 'A'}), Command.create({'name': 'B'})],
        })
        template = self.env['product.template'].create({
            'name': 'Series Bearing',
            'company_id': False,
            'attribute_line_ids': [Command.create({
                'attribute_id': attribute.id,
                'value_ids': [Command.set(attribute.value_ids.ids)],
            })],
        })
        self.assertGreater(len(template.product_variant_ids), 1)
        chosen = template.product_variant_ids[0]
        other = template.product_variant_ids[1]
        contract = self._full_draft(product=chosen, price=1200.0)
        self.assertEqual(contract.line_ids.product_id, chosen)
        self.assertNotEqual(contract.line_ids.product_id, other)

    def test_ctl_t003_product_template_is_derived(self):
        contract = self._full_draft()
        self.assertEqual(contract.line_ids.product_tmpl_id, self.product_bearing.product_tmpl_id)

    def test_ctl_t004_negotiated_price_is_stored(self):
        contract = self._full_draft(price=1200.0)
        self.assertEqual(contract.line_ids.price_unit, 1200.0)

    def test_ctl_t005_negative_price_is_rejected(self):
        contract = self._create_contract(self.user_a, self.company_a, **self._contract_vals(
            self.company_a, self.partner_a, self.user_a, self.company_a.currency_id, self.policy_a,
        ))
        with self.assertRaises(ValidationError):
            self._add_line(contract, self.product_bearing, -1.0)

    def test_ctl_t006_zero_price_blocks_review(self):
        contract = self._full_draft(price=0.0)
        self._add_evidence(contract)
        self.assertEqual(contract.line_ids.price_unit, 0.0)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('zero', str(caught.exception).lower())
        self.assertEqual(contract.state, 'draft')

    def test_ctl_t007_line_currency_follows_the_contract(self):
        contract = self._full_draft(currency=self.company_a.currency_id, price=50.0)
        self.assertEqual(contract.line_ids.currency_id, contract.currency_id)
        self.assertEqual(contract.company_currency_id, self.company_a.currency_id)

    def test_ctl_t008_product_default_uom_is_accepted(self):
        contract = self._full_draft()
        self.assertEqual(contract.line_ids.uom_id, self.product_bearing.uom_id)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        self.assertEqual(contract.state, 'ready_for_review')

    def test_ctl_t009_incompatible_uom_is_rejected(self):
        contract = self._create_contract(self.user_a, self.company_a, **self._contract_vals(
            self.company_a, self.partner_a, self.user_a, self.company_a.currency_id, self.policy_a,
        ))
        with self.assertRaises(ValidationError) as caught:
            self._add_line(contract, self.product_bearing, 10.0, uom=self.kg)
        self.assertIn('same family', str(caught.exception).lower())

    def test_ctl_t010_shared_product_is_accepted(self):
        self.assertFalse(self.product_bearing.company_id)
        contract = self._full_draft()
        self.assertFalse(contract.line_ids.product_id.company_id)
        self.assertEqual(contract.company_id, self.company_a)

    def test_ctl_t011_cross_company_product_is_rejected(self):
        restricted = self.env['product.product'].create({
            'name': 'UAE Only Component',
            'company_id': self.company_b.id,
        })
        contract = self._create_contract(self.user_a, self.company_a, **self._contract_vals(
            self.company_a, self.partner_a, self.user_a, self.company_a.currency_id, self.policy_a,
        ))
        with self.assertRaises(UserError) as caught:
            self._add_line(contract, restricted, 10.0)
        self.assertIn('company', str(caught.exception).lower())
        both = self._env_as(self.manager_both, self.company_a | self.company_b)
        visible = both['cpla.customer.contract'].create(self._contract_vals(
            self.company_a, self.partner_a, self.manager_both, self.company_a.currency_id, self.policy_a,
        ))
        with self.assertRaises(UserError):
            both['cpla.customer.contract.line'].create({
                'contract_id': visible.id,
                **self._line_vals(restricted, 10.0),
            })

    def test_ctl_t012_line_company_matches_the_header(self):
        contract = self._full_draft()
        self.assertEqual(contract.line_ids.company_id, contract.company_id)

    def test_ctl_t013_line_company_cannot_be_reassigned(self):
        contract = self._full_draft()
        line = contract.line_ids
        with self.assertRaises(UserError):
            line.write({'company_id': self.company_b.id})
        self.assertEqual(line.company_id, self.company_a)
        other = self._full_draft(name='Other draft')
        with self.assertRaises(UserError):
            line.write({'contract_id': other.id})

    def test_ctl_t014_exact_duplicate_line_is_rejected(self):
        contract = self._full_draft(price=1200.0)
        with self.assertRaises(ValidationError):
            self._add_line(contract, self.product_bearing, 1100.0, uom=self.product_bearing.uom_id)

    def test_ctl_t015_same_product_with_another_uom_is_not_blocked_by_product_uniqueness(self):
        template = self.product_bearing.product_tmpl_id
        template.write({'uom_ids': [Command.link(self.pack.id)]})
        contract = self._full_draft(price=200.0)
        second = self._add_line(contract, self.product_bearing, 2400.0, uom=self.pack)
        self.assertEqual(len(contract.line_ids), 2)
        self.assertEqual(second.uom_id, self.pack)
        self.assertNotEqual(contract.line_ids[0].uom_id, contract.line_ids[1].uom_id)
        self._add_evidence(contract)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('packaging', str(caught.exception).lower())
        self.assertEqual(len(contract.line_ids), 2)

    def test_ctl_t016_contract_price_ignores_list_price_changes(self):
        contract = self._full_draft(price=1200.0)
        self.product_bearing.list_price = 50.0
        self.assertEqual(contract.line_ids.price_unit, 1200.0)
        self.product_bearing.list_price = 80.0
        self.assertEqual(contract.line_ids.price_unit, 1200.0)

    def test_ctl_t017_direct_line_edit_respects_header_state(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        with self.assertRaises(UserError):
            contract.line_ids.write({'price_unit': 1000.0})
        self.assertEqual(contract.line_ids.price_unit, 1200.0)
        self.assertEqual(contract.state, 'ready_for_review')

    def test_ctl_t018_protected_line_cannot_be_deleted(self):
        contract = self._full_draft(price=1200.0)
        spare = self.env['product.product'].create({
            'name': 'Spare Bearing',
            'company_id': False,
        })
        extra = self._add_line(contract, spare, 300.0)
        extra.unlink()
        self.assertEqual(len(contract.line_ids), 1)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        with self.assertRaises(UserError):
            contract.line_ids.unlink()
        self.assertTrue(contract.line_ids.exists())

    def test_lfc_t001_new_contract_starts_in_draft(self):
        contract = self._full_draft()
        self.assertEqual(contract.state, 'draft')
        self.assertEqual(list(self._states()), ['draft', 'ready_for_review', 'cancelled'])

    def test_lfc_t002_incomplete_draft_can_remain_draft(self):
        contract = self._create_contract(self.user_a, self.company_a, **self._contract_vals(
            self.company_a, False, self.user_a, False, False,
            valid_from=False, valid_to=False, name='Incomplete',
        ))
        contract.write({'description': 'Still being prepared.'})
        self.assertEqual(contract.state, 'draft')
        self.assertFalse(contract.line_ids)
        self.assertFalse(contract.audit_authoritative)

    def test_lfc_t003_complete_draft_can_be_submitted(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        self.assertTrue(contract.action_submit_for_review())
        self.assertEqual(contract.state, 'ready_for_review')
        self.assertFalse(contract.audit_authoritative)
        self.assertFalse(contract.policy_id.operationally_approved)

    def test_lfc_t004_missing_line_blocks_submission(self):
        contract = self._full_draft(product=False, price=None)
        self._add_evidence(contract)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('line', str(caught.exception).lower())
        self.assertEqual(contract.state, 'draft')

    def test_lfc_t005_missing_end_date_blocks_submission(self):
        contract = self._full_draft(valid_to=False)
        self._add_evidence(contract)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('Valid To', str(caught.exception))

    def test_lfc_t006_missing_evidence_blocks_submission(self):
        contract = self._full_draft(price=1200.0)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('evidence', str(caught.exception).lower())
        contract.write({'description': 'The draft is still editable.'})
        self.assertEqual(contract.state, 'draft')

    def test_lfc_t007_unauthorized_user_cannot_submit(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        for user in (self.finance_a, self.auditor_a, self.sales_a, self.admin_a, self.user_a2):
            with self.assertRaises(AccessError):
                contract.with_env(self._env_as(user, self.company_a)).action_submit_for_review()
        self.assertEqual(contract.state, 'draft')

    def test_lfc_t008_ready_for_review_is_not_approved(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        self.assertEqual(contract.state, 'ready_for_review')
        self.assertNotEqual(contract.state, 'approved')
        self.assertNotIn('approved', self._states())
        self.assertNotIn('active', self._states())
        self.assertNotIn('superseded', self._states())
        self.assertFalse(contract.audit_authoritative)
        self.assertFalse(contract.policy_id.operationally_approved)

    def test_lfc_t009_submitted_terms_cannot_be_changed_without_reset(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        with self.assertRaises(UserError):
            contract.write({'partner_id': self.shared_partner.id})
        with self.assertRaises(UserError):
            contract.write({'line_ids': [Command.update(contract.line_ids.id, {'price_unit': 1.0})]})
        self.assertEqual(contract.line_ids.price_unit, 1200.0)
        manager = contract.with_env(self._env_as(self.manager_a, self.company_a))
        with self.assertRaises(UserError):
            manager.action_reset_to_draft()
        manager.write({'reset_reason': 'Correct a commercial term before review. This is not approval.'})
        manager.action_reset_to_draft()
        self.assertEqual(contract.state, 'draft')
        contract.line_ids.write({'price_unit': 1150.0})
        self.assertEqual(contract.line_ids.price_unit, 1150.0)

    def test_lfc_t010_direct_line_write_cannot_bypass_submission(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        with self.assertRaises(UserError):
            self.env['cpla.customer.contract.line'].browse(contract.line_ids.id).with_env(
                contract.env
            ).write({'price_unit': 10.0})
        self.assertEqual(contract.line_ids.price_unit, 1200.0)

    def test_lfc_t011_repeated_submission_is_idempotent(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        line_count = len(contract.line_ids)
        evidence_count = len(contract.evidence_ids)
        contract.action_submit_for_review()
        self.assertEqual(contract.state, 'ready_for_review')
        self.assertEqual(len(contract.line_ids), line_count)
        self.assertEqual(len(contract.evidence_ids), evidence_count)

    def test_lfc_t012_cancellation_follows_the_draft_policy(self):
        draft = self._full_draft(price=500.0)
        evidence = self._add_evidence(draft)
        draft.action_cancel()
        self.assertEqual(draft.state, 'cancelled')
        self.assertTrue(evidence.exists())
        ready = self._full_draft(user=self.manager_a, price=700.0, name='Manager review')
        self._add_evidence(ready)
        ready.action_submit_for_review()
        with self.assertRaises(AccessError):
            ready.with_env(self._env_as(self.user_a, self.company_a)).action_cancel()
        ready.action_cancel()
        self.assertEqual(ready.state, 'cancelled')
        ready.action_cancel()
        self.assertEqual(ready.state, 'cancelled')

    def test_lfc_t013_evidence_remains_after_cancellation(self):
        contract = self._full_draft(price=1200.0)
        evidence = self._add_evidence(contract, content=b'keep this file')
        contract.action_submit_for_review()
        contract.with_env(self._env_as(self.manager_a, self.company_a)).action_cancel()
        self.assertEqual(contract.state, 'cancelled')
        self.assertTrue(evidence.exists())
        self.assertTrue(evidence.datas)
        with self.assertRaises(UserError):
            evidence.unlink()
        self.assertTrue(evidence.exists())

    def test_lfc_t014_dev05_states_are_not_activated(self):
        self.assertEqual(set(self._states()), {'draft', 'ready_for_review', 'cancelled'})
        contract = self._full_draft()
        self.assertFalse(contract.audit_authoritative)
        self.assertNotIn('message_ids', contract._fields)
        for name in self.env.registry:
            self.assertFalse(name.startswith((
                'cpla.contract.version', 'cpla.contract.amendment', 'cpla.audit',
            )))

    def test_sec04_t001_company_user_reads_own_contract(self):
        contract = self._full_draft(price=1200.0)
        visible = self._env_as(self.user_a, self.company_a)['cpla.customer.contract'].search([
            ('id', '=', contract.id),
        ])
        self.assertEqual(visible.reference, contract.reference)
        self.assertEqual(visible.partner_id, self.partner_a)

    def test_sec04_t002_company_user_cannot_read_the_other_company(self):
        contract = self._full_draft(user=self.user_b, company=self.company_b, partner=self.partner_b, price=50.0)
        env = self._env_as(self.user_a, self.company_a)
        self.assertFalse(env['cpla.customer.contract'].search([('id', '=', contract.id)]))
        with self.assertRaises(AccessError):
            env['cpla.customer.contract'].browse(contract.id).read(['reference'])

    def test_sec04_t003_company_user_cannot_write_the_other_company(self):
        contract = self._full_draft(user=self.user_b, company=self.company_b, partner=self.partner_b, price=50.0)
        with self.assertRaises(AccessError):
            self._env_as(self.user_a, self.company_a)['cpla.customer.contract'].browse(contract.id).write({
                'description': 'Cross-company edit.',
            })
        self.assertFalse(contract.description)

    def test_sec04_t004_company_user_cannot_create_for_the_other_company(self):
        with self.assertRaises(AccessError):
            self._create_contract(self.user_a, self.company_a, **self._contract_vals(
                self.company_b, self.partner_b, self.user_b, self.company_b.currency_id, self.policy_b,
            ))

    def test_sec04_t005_multi_company_user_stays_inside_the_active_companies(self):
        both = self.company_a | self.company_b
        env = self._env_as(self.manager_both, both)
        contract_a = env['cpla.customer.contract'].create(self._contract_vals(
            self.company_a, self.partner_a, self.manager_both, self.company_a.currency_id, self.policy_a,
        ))
        contract_b = env['cpla.customer.contract'].create(self._contract_vals(
            self.company_b, self.partner_b, self.manager_both, self.aed, self.policy_b,
            name='UAE draft',
        ))
        self.assertEqual(contract_a.company_id, self.company_a)
        self.assertEqual(contract_b.company_id, self.company_b)
        self.assertEqual(contract_b.currency_id, self.aed)
        self.assertEqual(contract_b.company_currency_id, self.company_b.currency_id)
        narrowed = self._env_as(self.manager_both, self.company_a)
        with self.assertRaises(AccessError):
            narrowed['cpla.customer.contract'].create(self._contract_vals(
                self.company_b, self.partner_b, self.manager_both, self.company_b.currency_id, self.policy_b,
            ))
        self.assertFalse(narrowed['cpla.customer.contract'].search([('id', '=', contract_b.id)]))

    def test_sec04_t006_shared_customer_does_not_bypass_company_isolation(self):
        own = self._full_draft(partner=self.shared_partner, price=1200.0)
        other = self._full_draft(
            user=self.user_b, company=self.company_b, partner=self.shared_partner, price=50.0,
        )
        env = self._env_as(self.user_a, self.company_a)
        found = env['cpla.customer.contract'].search([
            ('partner_id', '=', self.shared_partner.id),
        ])
        self.assertIn(own, found)
        self.assertNotIn(other, found)

    def test_sec04_t007_direct_write_checks_business_authorization(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        with self.assertRaises(UserError):
            contract.line_ids.write({'price_unit': 1.0})
        with self.assertRaises(AccessError):
            self._env_as(self.auditor_a, self.company_a)['cpla.customer.contract.line'].browse(
                contract.line_ids.id
            ).write({'price_unit': 1.0})
        self.assertEqual(contract.line_ids.price_unit, 1200.0)

    def test_sec04_t008_contract_user_cannot_perform_manager_actions(self):
        contract = self._full_draft(price=1200.0)
        self._add_evidence(contract)
        contract.action_submit_for_review()
        user_env = self._env_as(self.user_a, self.company_a)
        with self.assertRaises(AccessError):
            user_env['cpla.customer.contract'].browse(contract.id).action_reset_to_draft()
        with self.assertRaises(AccessError):
            user_env['cpla.customer.contract'].browse(contract.id).action_cancel()
        draft = self._full_draft(name='Owned draft')
        with self.assertRaises(UserError):
            draft.write({'owner_id': self.manager_a.id})
        menus = self.env.ref(f'{MODULE}.group_contract_user').menu_access
        self.assertIn(self.env.ref(f'{MODULE}.menu_cpla_customer_contracts'), menus)
        self.assertNotIn(self.env.ref(f'{MODULE}.menu_cpla_configuration'), menus)

    def test_sec04_t009_auditor_and_finance_cannot_change_prices(self):
        contract = self._full_draft(price=1200.0)
        for user in (self.auditor_a, self.finance_a):
            env = self._env_as(user, self.company_a)
            visible = env['cpla.customer.contract'].browse(contract.id)
            self.assertEqual(visible.line_ids.price_unit, 1200.0)
            with self.assertRaises(AccessError):
                visible.line_ids.write({'price_unit': 1.0})
        self.assertEqual(contract.line_ids.price_unit, 1200.0)

    def test_sec04_t010_application_administrator_has_no_commercial_approval(self):
        contract = self._full_draft(price=1200.0)
        admin = self._env_as(self.admin_a, self.company_a)
        with self.assertRaises(AccessError):
            admin['cpla.customer.contract'].search([])
        with self.assertRaises(AccessError):
            admin['cpla.customer.contract'].browse(contract.id).action_submit_for_review()
        self.assertNotIn('approved', self._states())
        self.assertEqual(contract.state, 'draft')
        self.assertFalse(self.env.ref(f'{MODULE}.group_app_admin').rule_groups)

    def test_sec04_t011_unauthorized_attachment_access_is_denied(self):
        contract = self._full_draft(price=1200.0)
        evidence = self._add_evidence(contract)
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'cpla.customer.contract.evidence'),
            ('res_id', '=', evidence.id),
            ('res_field', '=', 'datas'),
        ])
        self.assertTrue(attachment)
        self.assertFalse(attachment.public)
        with self.assertRaises(AccessError):
            self._env_as(self.user_b, self.company_b)['ir.attachment'].browse(attachment.ids).check_access('read')
        with self.assertRaises(AccessError):
            self._env_as(self.sales_a, self.company_a)['ir.attachment'].browse(attachment.ids).check_access('read')

    def test_sec04_t012_evidence_does_not_leak_through_search_or_export(self):
        contract = self._full_draft(price=1200.0)
        evidence = self._add_evidence(contract)
        outsider = self._env_as(self.user_b, self.company_b)
        self.assertFalse(outsider['cpla.customer.contract'].search([('id', '=', contract.id)]))
        self.assertFalse(outsider['cpla.customer.contract.evidence'].search([('id', '=', evidence.id)]))
        with self.assertRaises(AccessError):
            self._env_as(self.sales_a, self.company_a)['cpla.customer.contract'].search([])
        with self.assertRaises(UserError):
            outsider['cpla.customer.contract.evidence'].browse(evidence.id).export_data(['name', 'datas'])
        with self.assertRaises(UserError):
            contract.export_data(['reference', 'partner_id'])

    def test_sec04_t013_line_access_cannot_bypass_header_access(self):
        contract = self._full_draft(price=1200.0)
        outsider = self._env_as(self.user_b, self.company_b)
        self.assertFalse(outsider['cpla.customer.contract.line'].search([
            ('contract_id', '=', contract.id),
        ]))
        with self.assertRaises(AccessError):
            outsider['cpla.customer.contract.line'].browse(contract.line_ids.id).read(['price_unit'])

    def test_sec04_t014_deletion_and_archive_follow_policy(self):
        contract = self._full_draft(price=1200.0)
        self.assertNotIn('active', contract._fields)
        with self.assertRaises(UserError):
            contract.unlink()
        self.assertTrue(contract.exists())
        evidence = self._add_evidence(contract)
        contract.action_submit_for_review()
        with self.assertRaises(UserError):
            contract.line_ids.unlink()
        with self.assertRaises(UserError):
            evidence.unlink()
        self.assertTrue(evidence.exists())

    def test_sec04_t015_combined_groups_do_not_defeat_company_or_owner_limits(self):
        owned = self._full_draft(user=self.combined_a, price=800.0, name='Combined owner')
        hidden = self._full_draft(user=self.manager_a, price=900.0, name='Manager owned')
        foreign = self._full_draft(
            user=self.user_b, company=self.company_b, partner=self.partner_b, price=40.0,
        )
        env = self._env_as(self.combined_a, self.company_a)
        found = env['cpla.customer.contract'].search([])
        self.assertIn(owned, found)
        self.assertNotIn(hidden, found)
        self.assertNotIn(foreign, found)
        with self.assertRaises(AccessError):
            env['cpla.customer.contract'].browse(foreign.id).write({'description': 'No.'})
        with self.assertRaises(AccessError):
            env['cpla.customer.contract.line'].browse(foreign.line_ids.id).write({'price_unit': 1.0})

    def test_reg04_t001_module_is_installed_at_the_contract_version(self):
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(module.state, 'installed')
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(module.latest_version, '19.0.1.15.0')
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])

    def test_reg04_t003_company_policy_behavior_is_preserved(self):
        self.assertTrue(self.policy_a.is_current)
        self.assertFalse(self.policy_a.operationally_approved)
        self.policy_a.action_submit_for_review()
        self.assertEqual(self.policy_a.state, 'ready_for_business_review')
        self.assertFalse(self.policy_a.operationally_approved)
        self.assertNotEqual(self.policy_a.state, 'approved_ready')

    def test_reg04_t004_security_groups_are_preserved(self):
        user = self.env.ref(f'{MODULE}.group_contract_user')
        manager = self.env.ref(f'{MODULE}.group_contract_manager')
        reviewer = self.env.ref(f'{MODULE}.group_finance_reviewer')
        finance_manager = self.env.ref(f'{MODULE}.group_finance_manager')
        self.assertEqual(manager.implied_ids, user)
        self.assertEqual(finance_manager.implied_ids, reviewer)
        self.assertEqual(len(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'res.groups'),
        ])), 8)

    def test_reg04_t005_views_and_menus_load(self):
        model = self.env['cpla.customer.contract']
        for view_type in ('list', 'form', 'search'):
            loaded = model.get_view(view_type=view_type)
            self.assertIn('ready_for_review', loaded['arch'])
            self.assertNotIn('decoration-success', loaded['arch'])
        user_view = self._env_as(self.user_a, self.company_a)['cpla.customer.contract'].get_view(
            view_type='form',
        )
        self.assertIn('not an approved price', user_view['arch'])
        self.env['cpla.company.policy'].get_view(view_type='form')

    def test_reg04_t006_xml_ids_resolve(self):
        for xmlid in (
            'group_contract_user',
            'group_contract_manager',
            'seq_cpla_customer_contract',
            'action_cpla_customer_contract',
            'menu_cpla_root',
            'menu_cpla_contracts',
            'menu_cpla_customer_contracts',
            'menu_cpla_configuration',
            'cpla_customer_contract_company_rule',
            'cpla_customer_contract_owner_rule',
            'cpla_customer_contract_manager_rule',
        ):
            self.assertTrue(self.env.ref(f'{MODULE}.{xmlid}'))

    def test_reg04_t007_contract_menus_are_not_duplicated(self):
        menu_ids = self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'ir.ui.menu'),
        ]).mapped('res_id')
        menus = self.env['ir.ui.menu'].browse(menu_ids)
        self.assertEqual(len(menus.filtered(lambda menu: menu.name == 'Customer Pricing Contracts')), 1)
        self.assertEqual(len(menus.filtered(lambda menu: menu.name == 'Configuration')), 1)
        self.assertFalse(menus.filtered(lambda menu: menu.name in (
            'Invoice Audit', 'Recovery', 'Leakage Dashboard',
        )))
        partner_views = self.env['ir.ui.view'].search([
            ('model', '=', 'res.partner'),
            ('id', 'in', self.env['ir.model.data'].search([
                ('module', '=', MODULE),
                ('model', '=', 'ir.ui.view'),
            ]).mapped('res_id')),
        ])
        self.assertFalse(partner_views)

    def test_reg04_t008_contract_tests_are_imported(self):
        import odoo.addons.contract_price_leakage_auditor.tests as tests_pkg
        self.assertTrue(tests_pkg.test_customer_contract)
        self.assertTrue(tests_pkg.test_company_policy)
        self.assertTrue(tests_pkg.test_security_foundation)

    def test_reg04_t009_policy_activation_is_still_refused(self):
        with self.assertRaises(AccessError):
            self.policy_a.with_env(self._env_as(self.admin_a, self.company_a)).action_request_activation()
        self.assertFalse(self.policy_a.operationally_approved)

    def test_reg04_t010_no_accounting_or_leakage_records_are_created(self):
        before_moves = (
            self.env['account.move'].search_count([])
            if 'account.move' in self.env.registry else 0
        )
        before = self.env['cpla.customer.contract'].search_count([])
        contract = self._full_draft(price=1200.0)
        self.assertEqual(self.env['cpla.customer.contract'].search_count([]), before + 1)
        self.assertTrue(contract.reference)
        if 'account.move' in self.env.registry:
            self.assertEqual(self.env['account.move'].search_count([]), before_moves)
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'account.move'),
        ]))
        for name in self.env.registry:
            self.assertFalse(name.startswith(('cpla.audit', 'cpla.waiver')))
        if 'cpla.recovery.request' in self.env.registry:
            self.assertFalse(self.env['cpla.recovery.request'].search_count([]))
            if name.startswith('cpla.leakage'):
                self.assertTrue(
                    name == 'cpla.leakage.finding'
                    or name.startswith(('cpla.leakage.case', 'cpla.leakage.reassessment'))
                )

    def test_contract_ref_001_standard_negotiated_price(self):
        active_before = self.inr.active
        currency = self.inr if self.inr.active else self.company_a.currency_id
        contract = self._full_draft(
            partner=self.partner_a,
            currency=currency,
            product=self.product_bearing,
            price=1200.0,
            name='XYZ Manufacturing bearings',
            valid_from=date(2026, 7, 1),
            valid_to=date(2026, 12, 31),
        )
        self.assertEqual(contract.line_ids.price_unit, 1200.0)
        self.assertEqual(contract.line_ids.uom_id, self.product_bearing.uom_id)
        self.assertNotEqual(contract.line_ids.price_unit, self.product_bearing.list_price)
        with self.assertRaises(UserError):
            contract.action_submit_for_review()
        self._add_evidence(contract)
        if currency.active:
            contract.action_submit_for_review()
            self.assertEqual(contract.state, 'ready_for_review')
            self.assertFalse(contract.audit_authoritative)
        self.assertEqual(self.inr.active, active_before)

    def test_contract_ref_002_foreign_currency_is_not_converted(self):
        rates_before = self.env['res.currency.rate'].search_count([('currency_id', '=', self.usd.id)])
        active_before = self.usd.active
        contract = self._full_draft(currency=self.usd, price=100.0, name='Equipment component')
        self.assertEqual(contract.line_ids.price_unit, 100.0)
        self.assertEqual(contract.currency_id, self.usd)
        self.assertEqual(contract.company_currency_id, self.company_a.currency_id)
        self.assertEqual(self.usd.active, active_before)
        self.assertEqual(
            self.env['res.currency.rate'].search_count([('currency_id', '=', self.usd.id)]),
            rates_before,
        )

    def test_contract_ref_003_companies_keep_separate_prices(self):
        india = self._full_draft(currency=self.company_a.currency_id, price=1200.0)
        uae = self._full_draft(
            user=self.user_b, company=self.company_b, partner=self.partner_b, currency=self.aed, price=50.0,
        )
        self.assertEqual(india.line_ids.price_unit, 1200.0)
        self.assertEqual(uae.line_ids.price_unit, 50.0)
        self.assertEqual(uae.currency_id, self.aed)
        self.assertNotEqual(india.company_id, uae.company_id)
        self.assertFalse(self._env_as(self.user_a, self.company_a)['cpla.customer.contract'].search([
            ('id', '=', uae.id),
        ]))

    def test_contract_ref_004_invalid_period_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._full_draft(valid_from=date(2026, 12, 31), valid_to=date(2026, 7, 1))

    def test_contract_ref_005_missing_evidence_blocks_review(self):
        contract = self._full_draft(price=1200.0, name='Missing signature')
        contract.write({'description': 'Prices are entered. The file is not.'})
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('evidence', str(caught.exception).lower())
        self.assertEqual(contract.state, 'draft')

    def test_contract_ref_006_one_customer_three_products(self):
        products = [
            self.env['product.product'].create({'name': name, 'company_id': False, 'list_price': 1.0})
            for name in ('Bearing A', 'Bearing B', 'Bearing C')
        ]
        contract = self._full_draft(product=products[0], price=1200.0, name='Three bearings')
        self._add_line(contract, products[1], 1400.0)
        self._add_line(contract, products[2], 1600.0)
        self.assertEqual(
            list(contract.line_ids.sorted('price_unit').mapped('price_unit')),
            [1200.0, 1400.0, 1600.0],
        )
        self.assertEqual(len(contract.line_ids.product_id), 3)
        self.assertEqual(set(contract.line_ids.mapped('company_id').ids), {self.company_a.id})

    def test_overlap_warning_does_not_choose_a_price(self):
        first = self._full_draft(price=1200.0, name='July bearing 1200')
        second = self._full_draft(price=1100.0, name='July bearing 1100')
        self._add_evidence(first)
        self._add_evidence(second)
        first.action_submit_for_review()
        second.action_submit_for_review()
        self.assertIn(second.reference, first.overlap_warning)
        self.assertIn('CONTRACT_CONFLICT_REVIEW_REQUIRED', first.overlap_warning)
        self.assertEqual(first.line_ids.price_unit, 1200.0)
        self.assertEqual(second.line_ids.price_unit, 1100.0)
        self.assertFalse(first.audit_authoritative)
        self.assertFalse(second.audit_authoritative)

    def test_currency_change_with_lines_is_blocked(self):
        contract = self._full_draft(currency=self.company_a.currency_id, price=1200.0)
        other = self.usd if self.usd != contract.currency_id else self.inr
        with self.assertRaises(UserError) as caught:
            contract.write({'currency_id': other.id})
        self.assertIn('not converted', str(caught.exception).lower())
        self.assertEqual(contract.currency_id, self.company_a.currency_id)
        self.assertEqual(contract.line_ids.price_unit, 1200.0)

    def test_extra_covered_entities_block_submission_while_dec03_is_open(self):
        contract = self._full_draft()
        child = self.env['res.partner'].create({
            'name': 'XYZ Invoice Desk',
            'parent_id': self.partner_a.id,
            'type': 'invoice',
        })
        exact = self._full_draft(partner=child, price=1200.0, name='Exact child customer')
        self.assertEqual(exact.partner_id, child)
        self.assertEqual(exact.commercial_partner_id, self.partner_a)
        self.assertFalse(exact.covered_partner_ids)
        contract.write({'covered_partner_ids': [Command.set([child.id])]})
        self._add_evidence(contract)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('DEC-03', str(caught.exception))
        self.assertEqual(contract.state, 'draft')

    def test_archived_product_is_retained_and_blocks_review(self):
        archived = self.env['product.product'].create({
            'name': 'Archived Bearing',
            'company_id': False,
            'active': False,
        })
        contract = self._create_contract(self.user_a, self.company_a, **self._contract_vals(
            self.company_a, self.partner_a, self.user_a, self.company_a.currency_id, self.policy_a,
        ))
        line = self._add_line(contract, archived, 1200.0)
        self.assertTrue(line.exists())
        self.assertFalse(line.product_id.active)
        self._add_evidence(contract)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('archived', str(caught.exception).lower())

    def test_non_current_policy_blocks_submission(self):
        self.policy_a.with_env(self.env).action_new_revision()
        self.assertFalse(self.policy_a.is_current)
        contract = self._full_draft(policy=self.policy_a)
        self._add_evidence(contract)
        with self.assertRaises(UserError) as caught:
            contract.action_submit_for_review()
        self.assertIn('current', str(caught.exception).lower())
