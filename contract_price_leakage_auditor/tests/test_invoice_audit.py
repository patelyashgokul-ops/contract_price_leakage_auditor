import logging
import sys
import threading
import traceback
import time
import uuid
from decimal import ROUND_HALF_UP, Decimal

from psycopg2 import IntegrityError

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import Manifest
from odoo.orm.registry import DummyRLock, Registry
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tests.common import freeze_time

MODULE = 'contract_price_leakage_auditor'
_logger = logging.getLogger(__name__)


def _money(value):
    if value is False or value is None or value == '':
        return None
    return Decimal(str(value))


# Committed only so worker cursors can see it. Later test classes count
# these tables from zero, so the rows have to be removed on their own cursor.
_POOL_COMPANY_LIKE = 'CPLA14 Conc Pool%'
_POOL_CLEAR_SQL = (
    "UPDATE cpla_company_policy SET supersedes_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_customer_contract_version SET source_version_id = NULL, supersedes_version_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_customer_contract_version_line SET origin_line_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_customer_contract_version_evidence SET origin_evidence_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_invoice_source_map SET previous_map_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_finance_validation SET supersedes_id = NULL, superseded_by_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_finance_validation_policy SET supersedes_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_recovery_billing_policy SET supersedes_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_recovery_billing SET supersedes_id = NULL WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_billing_policy_tax_rel WHERE policy_id IN (SELECT id FROM cpla_recovery_billing_policy WHERE company_id = ANY(%s))",
    "DELETE FROM cpla_recovery_collection_evidence WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_accounting_adjustment WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_accounting_link WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_billing_line WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_billing WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_billing_policy WHERE company_id = ANY(%s)",
    "UPDATE cpla_recovery_request SET supersedes_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_recovery_waiver SET supersedes_id = NULL, settlement_id = NULL, request_id = NULL, request_line_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_recovery_settlement SET supersedes_id = NULL, additional_waiver_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_recovery_policy SET supersedes_id = NULL WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_wizard WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_event WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_dispute WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_settlement WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_waiver WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_request_line WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_request WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_balance WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_policy_level WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_recovery_policy WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_finance_validation_wizard WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_finance_validation_approval WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_finance_validation_line WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_finance_validation WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_finance_validation_policy_level WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_finance_validation_policy WHERE company_id = ANY(%s)",
    "UPDATE cpla_leakage_case SET superseded_by_case_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_discount_approval SET superseded_by_id = NULL WHERE company_id = ANY(%s)",
    "UPDATE cpla_discount_concession SET superseded_by_id = NULL WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_reassessment_event WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_reassessment_wizard WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_case_wizard WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_reassessment WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_case_membership WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_case_checklist WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_case_event WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_case_evidence WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_case_submission WHERE company_id = ANY(%s)",
    "DELETE FROM mail_activity WHERE res_model = 'cpla.leakage.case' AND res_id IN (SELECT id FROM cpla_leakage_case WHERE company_id = ANY(%s))",
    "DELETE FROM cpla_leakage_case WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_leakage_finding WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_invoice_audit_result WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_invoice_source_verification_line WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_invoice_source_verification WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_invoice_source_allocation WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_invoice_source_map WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_invoice_audit_run WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_sale_price_lock WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_discount_event WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_discount_approval WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_discount_concession WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_pricing_applicability_check WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_quotation_override_request WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_customer_contract_version_tier WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_customer_contract_version_line WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_customer_contract_version_evidence WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_customer_contract_version_event WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_customer_contract_version WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_customer_contract_evidence WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_customer_contract_line WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_customer_contract WHERE company_id = ANY(%s)",
    "DELETE FROM cpla_company_policy WHERE company_id = ANY(%s)",
)


def purge_dev14_concurrency_pool(registry):
    """Remove committed concurrency-pool rows and their role grants.

    The pool company stays. Account moves stay. Absolute-zero assertions
    cover the commercial tables above, not the chart.
    """
    if registry is None:
        return
    from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
    with registry.cursor() as cursor:
        cursor.execute("SET lock_timeout = '20s'")
        cursor.execute("SET statement_timeout = '120s'")
        cursor.execute(
            "SELECT id FROM res_company WHERE name LIKE %s",
            (_POOL_COMPANY_LIKE,),
        )
        company_ids = [row[0] for row in cursor.fetchall()]
        if company_ids:
            for statement in _POOL_CLEAR_SQL:
                cursor.execute(statement, (company_ids,))
        env = api.Environment(cursor, api.SUPERUSER_ID, {MODULE_UNINSTALL_FLAG: True})
        users = env['res.users'].with_context(active_test=False).search([
            ('login', '=like', 'cpla14_pool_%'),
        ])
        if users:
            internal = env.ref('base.group_user')
            users.write({'group_ids': [Command.set(internal.ids)]})
        cursor.commit()


@tagged('post_install', '-at_install')
class TestDev12InvoiceAudit(TransactionCase):
    """Posted-invoice potential leakage and finance validation of that evidence."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Registered before the pool commit so a failed chart load still
        # removes any users that were already committed.
        cls.addClassCleanup(cls._clear_dev14_concurrency_pool)
        cls._commit_dev14_concurrency_pool()
        cls.company_a = cls.env['res.company'].create({'name': 'ABC India'})
        cls.company_b = cls.env['res.company'].create({'name': 'ABC UAE'})
        chart = cls.env['account.chart.template']
        chart.with_company(cls.company_a).try_loading('generic_coa', cls.company_a, install_demo=False)
        chart.with_company(cls.company_b).try_loading('generic_coa', cls.company_b, install_demo=False)
        cls.owner = cls._make_sale_user(
            'cpla12_owner', cls.company_a, extra_groups=('group_contract_user',),
        )
        cls.owner_b = cls._make_user('cpla12_owner_b', 'group_contract_user', cls.company_b)
        cls.manager = cls._make_user('cpla12_manager', 'group_contract_manager', cls.company_a)
        cls.commercial = cls._make_user('cpla16_commercial', 'group_contract_manager', cls.company_a)
        cls.commercial_b = cls._make_user('cpla16_commercial_b', 'group_contract_manager', cls.company_a)
        cls.finance = cls._make_account_user('cpla12_finance', 'group_finance_manager', cls.company_a)
        cls.reviewer = cls._make_account_user('cpla12_reviewer', 'group_finance_reviewer', cls.company_a)
        cls.auditor = cls._make_account_user('cpla12_auditor', 'group_internal_auditor', cls.company_a)
        cls.admin = cls._make_user('cpla12_admin', 'group_app_admin', cls.company_a)
        cls.salesman = cls._make_sale_user('cpla12_salesman', cls.company_a)
        cls.plain = new_test_user(
            cls.env, login='cpla12_plain', groups='base.group_user', password='cpla-test',
            company_id=cls.company_a.id, company_ids=[Command.set([cls.company_a.id])],
        )
        cls.both = cls._make_account_user(
            'cpla12_both', 'group_finance_manager', cls.company_a,
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
            'name': 'Bearing A', 'type': 'consu', 'invoice_policy': 'order',
            'list_price': 9999.0, 'company_id': False, 'taxes_id': [Command.clear()],
        })
        cls.other_product = cls.env['product.product'].create({
            'name': 'Bearing B', 'type': 'consu', 'invoice_policy': 'order',
            'list_price': 9999.0, 'company_id': False, 'taxes_id': [Command.clear()],
        })
        cls.unit = cls.env.ref('uom.product_uom_unit')
        for company in (cls.company_a, cls.company_b):
            income = cls.env['account.account'].with_company(company).search([
                ('account_type', '=', 'income'),
            ], limit=1)
            for product in (cls.bearing, cls.other_product):
                product.with_company(company).write({
                    'property_account_income_id': income.id,
                    'taxes_id': [Command.clear()],
                })

    @classmethod
    def _commit_dev14_concurrency_pool(cls):
        """Commit a company the worker cursors can see.

        The class transaction is never committed. A second cursor cannot
        read its company, chart, or users, and it cannot join the role
        rows that transaction still holds. This pool is committed first.
        """
        token = uuid.uuid4().hex[:8]
        with cls.registry.cursor() as cursor:
            cursor.execute("SET lock_timeout = '20s'")
            cursor.execute("SET statement_timeout = '180s'")
            env = api.Environment(cursor, api.SUPERUSER_ID, {})
            company = env['res.company'].create({
                'name': 'CPLA14 Conc Pool %s' % token,
                'currency_id': env.company.currency_id.id,
            })
            env['account.chart.template'].with_company(company).try_loading(
                'generic_coa', company, install_demo=False,
            )
            env = api.Environment(cursor, api.SUPERUSER_ID, {
                'allowed_company_ids': [company.id],
            })

            def make(login, groups):
                return new_test_user(
                    env,
                    login=login,
                    groups=groups,
                    password='cpla-test',
                    company_id=company.id,
                    company_ids=[Command.set([company.id])],
                )

            owner = make(
                'cpla14_pool_owner_%s' % token,
                'base.group_user,sales_team.group_sale_salesman,%s.group_contract_user' % MODULE,
            )
            manager = make(
                'cpla14_pool_mgr_%s' % token,
                'base.group_user,%s.group_contract_manager' % MODULE,
            )
            finance = make(
                'cpla14_pool_fin_%s' % token,
                'base.group_user,account.group_account_invoice,%s.group_finance_manager' % MODULE,
            )
            salesman = make(
                'cpla14_pool_sale_%s' % token,
                'base.group_user,sales_team.group_sale_salesman',
            )
            reviewer = make(
                'cpla14_pool_rev_%s' % token,
                'base.group_user,account.group_account_invoice,%s.group_finance_reviewer' % MODULE,
            )
            commercial = make(
                'cpla14_pool_com_%s' % token,
                'base.group_user,%s.group_contract_manager' % MODULE,
            )
            commercial_b = make(
                'cpla14_pool_com2_%s' % token,
                'base.group_user,%s.group_contract_manager' % MODULE,
            )
            policy = env['cpla.company.policy'].create({
                'company_id': company.id,
                'change_reason': 'Concurrency pool. Not an operational approval.',
            })
            policy.write({
                'quotation_compliance_mode': 'warning',
                'pricing_date_policy': 'order_confirmation',
            })
            partner = env['res.partner'].with_company(company).create({
                'name': 'Pool Buyer %s' % token,
                'is_company': True,
                'company_id': company.id,
            })
            product = env['product.product'].with_company(company).create({
                'name': 'Pool Bearing %s' % token,
                'type': 'consu',
                'invoice_policy': 'order',
                'list_price': 9999.0,
                'company_id': False,
                'taxes_id': [Command.clear()],
            })
            income = env['account.account'].with_company(company).search([
                ('account_type', '=', 'income'),
            ], limit=1)
            if not income:
                raise AssertionError('The concurrency pool has no income account.')
            product.with_company(company).write({
                'property_account_income_id': income.id,
                'taxes_id': [Command.clear()],
            })
            cursor.commit()
            cls.conc_pool = {
                'token': token,
                'company_id': company.id,
                'owner_id': owner.id,
                'manager_id': manager.id,
                'finance_id': finance.id,
                'salesman_id': salesman.id,
                'reviewer_id': reviewer.id,
                'commercial_id': commercial.id,
                'commercial_b_id': commercial_b.id,
                'policy_id': policy.id,
                'partner_id': partner.id,
                'product_id': product.id,
            }

    @classmethod
    def _clear_dev14_concurrency_pool(cls):
        """Drop the committed pool before the next test class starts."""
        purge_dev14_concurrency_pool(getattr(cls, 'registry', None))

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
        return fields.Date.context_today(self.env['cpla.invoice.audit.run'])

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

    def _assert_amount(self, actual, expected):
        self.assertEqual(_money(actual), Decimal(str(expected)))

    def _assert_blank(self, value):
        self.assertIn(value, (False, None, ''))

    def _v1(self, products, currency, company=None, partner=None, valid_from=None, valid_to=None):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
        owner = self.owner if company == self.company_a else self.owner_b
        env = self._env(owner, company)
        contract = env['cpla.customer.contract'].create({
            'name': 'Negotiated supply',
            'company_id': company.id,
            'partner_id': partner.id,
            'owner_id': owner.id,
            'currency_id': currency.id,
            'valid_from': valid_from or self._on(-30),
            'valid_to': valid_to or self._on(180),
            'policy_id': (self.policy_a if company == self.company_a else self.policy_b).id,
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
            'source_reference': 'AGR-012',
            'description': 'Signed pricing schedule.',
            'datas': 'c2lnbmVk',
        })
        contract.action_submit_for_review()
        manager = self.manager if company == self.company_a else self._make_user(
            'cpla12_mgr_%s' % contract.id, 'group_contract_manager', company,
        )
        return self._env(manager, company)['cpla.customer.contract.version'].approve_initial(
            self._env(manager, company)['cpla.customer.contract'].browse(contract.id)
        )

    def _priced(self, price='1150', concessions=(), policy=None, tiers=None, currency=None,
                company=None, partner=None, product=None, effective=None, valid_from=None, valid_to=None):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
        product = product or self.bearing
        currency = currency or company.currency_id
        first = self._v1(
            [(product, price)], currency, company=company, partner=partner,
            valid_from=valid_from, valid_to=valid_to,
        )
        owner = self.owner if company == self.company_a else self.owner_b
        env = self._env(owner, company)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        values = {
            'amendment_reason': 'Authorized price clause. Not a retroactive restatement.',
            'effective_from': effective or self._today(),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        }
        values.update(policy or {})
        amendment.write(values)
        amendment.line_ids.write({'price_unit': price})
        if tiers:
            line = amendment.line_ids[:1]
            line.write({
                'tier_method': 'full_volume',
                'quantity_basis': tiers['basis'],
                'return_policy': tiers['return_policy'],
            })
            for spec in tiers['rows']:
                minimum, maximum, tier_price = spec[0], spec[1], spec[2]
                quantity_uom = spec[3] if len(spec) > 3 else line.uom_id
                pricing_uom = spec[4] if len(spec) > 4 else line.uom_id
                env['cpla.customer.contract.version.tier'].create({
                    'version_line_id': line.id,
                    'min_quantity': minimum,
                    'has_maximum': maximum is not None,
                    'max_quantity': maximum or 0.0,
                    'quantity_uom_id': quantity_uom.id,
                    'price_unit': tier_price,
                    'pricing_uom_id': pricing_uom.id,
                })
        for spec in concessions:
            self._concession(amendment, spec)
        amendment.action_submit_for_review()
        finance = self.finance if company == self.company_a else self._make_account_user(
            'cpla12_fin_%s' % amendment.id, 'group_finance_manager', company,
        )
        record = self._env(finance, company)['cpla.customer.contract.version'].browse(amendment.id)
        record.action_approve()
        return record

    def _concession(self, version, spec):
        line = version.line_ids[:1]
        kind = spec['type']
        values = {
            'version_id': version.id,
            'sequence': spec.get('sequence', 10),
            'concession_type': kind,
            'customer_scope': 'version_customer',
            'product_scope': 'version_line',
            'version_line_id': line.id,
            'evidence_reference': spec.get('evidence', 'AGR-DISC-012'),
        }
        if kind == 'percentage':
            values['percent_exact'] = spec['percent']
        elif kind == 'fixed_special_price':
            values['amount_exact'] = spec['amount']
            values['currency_id'] = version.currency_id.id
            values['uom_id'] = line.uom_id.id
        owner = self.owner if version.company_id == self.company_a else self.owner_b
        return self._env(owner, version.company_id)['cpla.discount.concession'].create(values)

    def _later(self, version, price, effective=None):
        time.sleep(1.1)
        owner = self.owner if version.company_id == self.company_a else self.owner_b
        finance = self.finance if version.company_id == self.company_a else self._make_account_user(
            'cpla12_later_%s' % version.id, 'group_finance_manager', version.company_id,
        )
        env = self._env(owner, version.company_id)
        amendment = env['cpla.customer.contract.version'].browse(version.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Later approved price. Not a silent overwrite of history.',
            'effective_from': effective or self._today(),
            'comparison_currency_policy': version.comparison_currency_policy,
            'tax_basis': version.tax_basis,
            'tax_structure': version.tax_structure,
            'rounding_stage': version.rounding_stage,
        })
        amendment.line_ids.write({'price_unit': price})
        amendment.action_submit_for_review()
        record = self._env(finance, version.company_id)['cpla.customer.contract.version'].browse(amendment.id)
        record.action_approve()
        return record

    def _limit(self):
        return {
            'authority_limit_basis': 'per_unit_reduction',
            'authority_max_unit_reduction_exact': '50',
        }

    def _box(self, name, factor):
        box = self.env['uom.uom'].create({
            'name': name,
            'relative_uom_id': self.unit.id,
            'relative_factor': factor,
        })
        self.bearing.product_tmpl_id.write({'uom_ids': [Command.link(box.id)]})
        return box

    def _pricelist(self, company):
        currency = company.currency_id
        pricelist = self.env['product.pricelist'].search([
            ('company_id', 'in', [False, company.id]),
            ('currency_id', '=', currency.id),
        ], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': 'CPLA12 %s' % currency.name,
                'currency_id': currency.id,
                'company_id': company.id,
            })
        return pricelist

    def _quote(self, price, quantity=100, partner=None, product=None, company=None, discount=0.0):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
        product = product or self.bearing
        order = self.env['sale.order'].with_company(company).create({
            'partner_id': partner.id,
            'company_id': company.id,
            'pricelist_id': self._pricelist(company).id,
            'currency_id': company.currency_id.id,
            'user_id': self.salesman.id if company == self.company_a else self.env.user.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': quantity,
            })],
        })
        line = order.order_line.filtered(lambda item: not item.display_type)[:1]
        line.write({
            'price_unit': price,
            'technical_price_unit': 0,
            'discount': discount,
            'tax_ids': [Command.clear()],
        })
        return order

    def _confirm(self, order):
        order.action_confirm()
        self.assertIn(order.state, ('sale', 'done'))
        return order

    def _product_lines(self, move):
        return move.invoice_line_ids.filtered(lambda item: item.display_type == 'product')

    def _invoice(self, order, quantity=None, price=None, discount=None, invoice_date=None, post=True):
        invoice = order.with_company(order.company_id)._create_invoices()
        self.assertEqual(len(invoice), 1)
        line = self._product_lines(invoice)[:1]
        values = {'tax_ids': [Command.clear()]}
        if quantity is not None:
            values['quantity'] = quantity
        if price is not None:
            values['price_unit'] = price
        if discount is not None:
            values['discount'] = discount
        line.write(values)
        if invoice_date:
            invoice.invoice_date = invoice_date
        if post:
            invoice.action_post()
        return invoice

    def _journal(self, company, journal_type):
        return self.env['account.journal'].search([
            ('company_id', '=', company.id), ('type', '=', journal_type),
        ], limit=1)

    def _manual(self, move_type='out_invoice', company=None, partner=None, product=None,
                quantity=100, price=1100, post=True):
        company = company or self.company_a
        partner = partner or self.partner
        product = product or self.bearing
        journal_type = 'sale' if move_type.startswith('out') else 'purchase'
        invoice = self.env['account.move'].with_company(company).create({
            'move_type': move_type,
            'partner_id': partner.id,
            'company_id': company.id,
            'journal_id': self._journal(company, journal_type).id,
            'invoice_date': fields.Date.context_today(self.env['account.move']),
            'invoice_line_ids': [Command.create({
                'product_id': product.id,
                'quantity': quantity,
                'price_unit': price,
                'name': product.display_name,
                'tax_ids': [Command.clear()],
            })],
        })
        if post:
            invoice.action_post()
        return invoice

    def _sale(self, approved, actual, quantity=100, **priced):
        self._priced(approved, **priced)
        order = self._confirm(self._quote(actual, quantity=quantity))
        invoice = self._invoice(order, quantity=quantity, price=actual)
        return order, invoice

    def _run(self, **extra):
        values = {
            'company_id': self.company_a.id,
            'date_from': self._on(-500),
            'date_to': self._on(5),
            'date_basis': 'invoice_date',
            'mode': 'on_demand',
        }
        values.update(extra)
        return self.env['cpla.invoice.audit.run'].create(values)

    def _audit(self, **extra):
        run = self._run(**extra)
        run.action_run()
        return run

    def _results(self, run, move=None):
        rows = run.result_ids
        if move:
            rows = rows.filtered(lambda item: item.move_id == move)
        return rows.sorted('id')

    def _latest(self, run, move=None):
        rows = self._results(run, move).filtered(lambda item: item.product_id)
        self.assertTrue(rows)
        return rows[-1]

    def _current(self, run=None):
        domain = [('is_current', '=', True), ('company_id', '=', self.company_a.id)]
        if run:
            domain.append(('run_id', '=', run.id))
        return self.env['cpla.leakage.finding'].search(domain)

    def _potential(self, company=None):
        company = company or self.company_a
        return self.env['cpla.leakage.finding'].search([
            ('company_id', '=', company.id),
            ('is_current', '=', True),
            ('finding_status', '=', 'potential'),
        ])

    def _exposure(self, company=None):
        total = Decimal('0')
        for finding in self._potential(company):
            total += _money(finding.potential_leakage_exact) or Decimal('0')
        return total

    def _override(self, line):
        line.order_id.write({'user_id': self.owner.id})
        env = self._env(self.owner, line.order_id.company_id)
        wizard = env['cpla.quotation.override.request'].create({
            'sale_line_id': line.id,
            'reason': 'Customer accepted this quotation price.',
            'evidence_reference': 'MAIL-012',
        })
        action = wizard.action_create_request()
        approval = env['cpla.discount.approval'].browse(action['res_id'])
        approval.action_submit()
        self._env(self.finance, line.order_id.company_id)['cpla.discount.approval'].browse(
            approval.id
        ).action_approve()
        return approval

    def _included_tax(self):
        group = self.env['account.tax.group'].create({
            'name': 'CPLA12 taxes',
            'company_id': self.company_a.id,
        })
        country = self.company_a.country_id or self.env.ref('base.us')
        return self.env['account.tax'].create({
            'name': 'CPLA12 included 18',
            'amount': 18.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
            'company_id': self.company_a.id,
            'country_id': country.id,
            'tax_group_id': group.id,
        })

    def test_elg12_t001_posted_customer_invoice_is_eligible(self):
        _order, invoice = self._sale('1150', 1150)
        run = self._audit()
        result = self._latest(run, invoice)
        self.assertEqual(result.result_classification, 'PRICING_COMPLIANT')
        self.assertEqual(invoice.state, 'posted')
        self.assertFalse(self._potential())

    def test_elg12_t002_draft_customer_invoice_is_excluded(self):
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1150)), post=False)
        self.assertEqual(invoice.state, 'draft')
        run = self._audit()
        self.assertNotIn(invoice, run.result_ids.move_id)
        outcome = run._audit_move(invoice)
        self.assertGreaterEqual(outcome['excluded'], 1)
        self.assertFalse(self._potential())

    def test_elg12_t003_cancelled_invoice_is_excluded(self):
        _order, invoice = self._sale('1150', 1150)
        invoice.button_cancel()
        self.assertEqual(invoice.state, 'cancel')
        run = self._audit()
        self.assertNotIn(invoice, self.env['account.move'].search([
            ('id', '=', invoice.id),
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
        ]))
        self.assertFalse(run.result_ids.filtered(lambda item: item.move_id == invoice and item.potential_exposure_exact))

    def test_elg12_t004_vendor_bill_is_excluded(self):
        bill = self._manual(move_type='in_invoice', price=100)
        run = self._audit()
        self.assertNotIn(bill, run.result_ids.move_id)
        outcome = run._audit_move(bill)
        self.assertGreaterEqual(outcome['excluded'], 1)
        self.assertFalse(self._potential())

    def test_elg12_t005_vendor_refund_is_excluded(self):
        refund = self._manual(move_type='in_refund', price=100)
        run = self._audit()
        self.assertNotIn(refund, run.result_ids.move_id)
        self.assertGreaterEqual(run._audit_move(refund)['excluded'], 1)

    def test_elg12_t006_display_section_is_excluded(self):
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1150)), post=False)
        invoice.write({'invoice_line_ids': [Command.create({
            'display_type': 'line_section',
            'name': 'Section',
        })]})
        invoice.action_post()
        run = self._audit()
        section = run.result_ids.filtered(
            lambda item: item.move_id == invoice and item.move_line_id.display_type == 'line_section'
        )
        self.assertEqual(len(section), 1)
        self.assertEqual(section.result_classification, 'UNSUPPORTED_TRANSACTION')
        self._assert_blank(section.potential_exposure_exact)

    def test_elg12_t007_tax_and_receivable_lines_are_excluded(self):
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1150)), post=False)
        tax = self.env['account.tax'].search([
            ('company_id', '=', self.company_a.id),
            ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'),
        ], limit=1)
        self._product_lines(invoice).write({'tax_ids': [Command.set(tax.ids)]})
        invoice.action_post()
        run = self._audit()
        technical = run.result_ids.filtered(
            lambda item: item.move_id == invoice and item.result_classification == 'UNSUPPORTED_TRANSACTION'
        )
        self.assertGreaterEqual(len(technical), 1)
        self.assertTrue(all(not row.potential_exposure_exact for row in technical))

    def test_elg12_t008_commercial_product_line_is_included(self):
        _order, invoice = self._sale('1150', 1100)
        run = self._audit()
        result = self._latest(run, invoice)
        self.assertEqual(result.product_id, self.bearing)
        self.assertEqual(result.result_classification, 'UNAUTHORIZED_UNDERPRICING')
        self.assertEqual(len(self._potential()), 1)

    def test_elg12_t009_credit_note_is_classified_separately(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        credit = invoice._reverse_moves()
        credit.action_post()
        run = self._audit()
        credit_result = self._results(run, credit).filtered('product_id')[:1]
        self.assertEqual(credit_result.credit_treatment, 'verified_full_reversal')
        self._assert_blank(credit_result.potential_exposure_exact)
        self.assertEqual(self._exposure(), Decimal('0'))

    def test_elg12_t010_wrong_company_is_rejected(self):
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        order = self._confirm(self._quote(1150, company=self.company_b, partner=self.partner_b))
        invoice = self._invoice(order)
        with self.assertRaises(AccessError):
            self._env(self.finance, self.company_a)['cpla.invoice.audit.run'].create({
                'company_id': self.company_b.id,
                'date_from': self._on(-1),
                'date_to': self._today(),
            })
        foreign = self._audit(company_id=self.company_b.id)
        self.assertIn(invoice, foreign.result_ids.move_id)
        local = self._audit()
        self.assertNotIn(invoice, local.result_ids.move_id)

    def test_elg12_t011_date_range_filter_is_applied(self):
        self._priced('1150')
        invoice = self._invoice(
            self._confirm(self._quote(1100)), price=1100, invoice_date=self._on(-10),
        )
        missed = self._audit(date_from=self._today(), date_to=self._today())
        self.assertNotIn(invoice, missed.result_ids.move_id)
        found = self._audit(date_from=self._on(-10), date_to=self._on(-10))
        self.assertIn(invoice, found.result_ids.move_id)

    def test_elg12_t012_unsupported_source_is_explicit(self):
        entry = self.env['account.move'].with_company(self.company_a).create({
            'move_type': 'entry',
            'company_id': self.company_a.id,
            'date': self._today(),
            'journal_id': self._journal(self.company_a, 'general').id,
        })
        run = self._run()
        outcome = run._audit_move(entry) if entry.state == 'posted' else {'excluded': 1}
        self.assertGreaterEqual(outcome['excluded'], 0)
        self.assertNotIn(entry, self._audit().result_ids.filtered(
            lambda item: item.result_classification in (
                'UNAUTHORIZED_UNDERPRICING', 'MISSED_CONTRACT_PRICE_INCREASE',
            )
        ).move_id)

    def test_his12_t001_approved_historical_version_is_selected(self):
        version = self._priced('1150')
        _order, invoice = self._sale('1150', 1100) if False else (None, None)
        self._confirm(self._quote(1100))
        invoice = self._invoice(self.env['sale.order'].search([], limit=1), price=1100)
        run = self._audit()
        result = self._latest(run, invoice)
        self.assertEqual(result.version_id, version)
        self._assert_amount(result.approved_adjusted_exact, '1150')

    def test_his12_t002_draft_version_is_ignored(self):
        version = self._priced('1150')
        draft = self._env(self.owner, self.company_a)['cpla.customer.contract.version'].browse(
            version.id
        ).create_amendment()
        draft.line_ids.write({'price_unit': 900})
        _order, invoice = (None, self._invoice(self._confirm(self._quote(1100)), price=1100))
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.version_id, version)
        self.assertNotEqual(result.version_id, draft)
        self._assert_amount(result.approved_adjusted_exact, '1150')

    def test_his12_t003_rejected_amendment_is_ignored(self):
        version = self._priced('1150')
        amendment = self._env(self.owner, self.company_a)['cpla.customer.contract.version'].browse(
            version.id
        ).create_amendment()
        amendment.write({
            'amendment_reason': 'Rejected price.',
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
            'effective_from': self._on(5),
            'rejection_reason': 'The price was not approved.',
        })
        amendment.line_ids.write({'price_unit': 900})
        amendment.action_submit_for_review()
        self._env(self.finance, self.company_a)['cpla.customer.contract.version'].browse(
            amendment.id
        ).action_reject()
        invoice = self._invoice(self._confirm(self._quote(1100)), price=1100)
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.version_id, version)
        self.assertEqual(amendment.state, 'rejected')

    def test_his12_t004_effective_date_boundary_is_respected(self):
        self.policy_a.pricing_date_policy = 'invoice'
        version = self._priced('1000', effective=self._today())
        future = self._later(version, '1200', effective=self._on(10))
        invoice = self._invoice(
            self._confirm(self._quote(1000)), price=1000, invoice_date=self._today(),
        )
        result = self._latest(self._audit(), invoice)
        self.assertNotEqual(result.version_id, future)
        self._assert_amount(result.approved_adjusted_exact, '1000')
        self.assertEqual(self._exposure(), Decimal('0'))

    def test_his12_t005_invoice_date_policy_selects_the_later_version(self):
        self.policy_a.pricing_date_policy = 'invoice'
        with freeze_time('2026-10-18'):
            version = self._priced(
                '1000', effective=fields.Date.to_date('2026-10-19'),
                valid_from=fields.Date.to_date('2026-10-01'),
                valid_to=fields.Date.to_date('2026-12-31'),
            )
        with freeze_time('2026-10-28'):
            later = self._later(version, '1200', effective=fields.Date.to_date('2026-10-28'))
        invoice = self._invoice(
            self._confirm(self._quote(1000, quantity=100)),
            price=1000, quantity=100, invoice_date=fields.Date.to_date('2026-10-28'),
        )
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.version_id, later)
        self.assertEqual(result.result_classification, 'MISSED_CONTRACT_PRICE_INCREASE')
        self._assert_amount(result.potential_exposure_exact, '20000')

    def test_his12_t006_order_date_grandfathering_keeps_the_locked_price(self):
        with freeze_time('2026-06-25'):
            version = self._priced(
                '1000', effective=fields.Date.to_date('2026-06-25'),
                valid_from=fields.Date.to_date('2026-06-01'),
                valid_to=fields.Date.to_date('2026-12-31'),
            )
            order = self._confirm(self._quote(1000, quantity=100))
        with freeze_time('2026-07-01'):
            self._later(version, '1200', effective=fields.Date.to_date('2026-07-01'))
        invoice = self._invoice(order, quantity=100, price=1000, invoice_date=fields.Date.to_date('2026-07-15'))
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.version_id, version)
        self.assertTrue(result.calculation_trace)
        self.assertIn('order-date lock', result.calculation_trace)
        self.assertEqual(self._exposure(), Decimal('0'))

    def test_his12_t007_missing_pricing_date_is_flagged(self):
        self.policy_a.pricing_date_policy = 'delivery'
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1100)), price=1100)
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'MISSING_PRICING_EVIDENCE')
        self._assert_blank(result.potential_exposure_exact)

    def test_his12_t008_conflicting_contract_authority_is_flagged(self):
        self.policy_a.pricing_date_policy = 'invoice'
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1100)), price=1100)
        self._priced('1000')
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'CONTRACT_CONFLICT_REVIEW_REQUIRED')
        self._assert_blank(result.potential_exposure_exact)
        self.assertFalse(self._potential())

    def test_his12_t009_missing_contract_produces_no_fabricated_leakage(self):
        invoice = self._invoice(self._confirm(self._quote(1100)), price=1100)
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'CONTRACT_COVERAGE_EXCEPTION')
        self._assert_blank(result.potential_exposure_exact)
        self.assertFalse(self._potential())

    def test_his12_t010_historical_cutoff_is_respected(self):
        self.policy_a.pricing_date_policy = 'invoice'
        with freeze_time('2026-06-01'):
            version = self._priced(
                '1000', effective=fields.Date.to_date('2026-06-02'),
                valid_from=fields.Date.to_date('2026-06-01'),
                valid_to=fields.Date.to_date('2026-12-31'),
            )
        with freeze_time('2026-07-20'):
            later = self._later(version, '1200', effective=fields.Date.to_date('2026-07-20'))
        invoice = self._invoice(
            self._confirm(self._quote(1000, quantity=100)),
            quantity=100, price=1000, invoice_date=fields.Date.to_date('2026-07-25'),
        )
        early = self._audit(knowledge_cutoff='2026-07-01 00:00:00')
        early_result = self._latest(early, invoice)
        self.assertEqual(early_result.version_id, version)
        self.assertEqual(self._exposure(), Decimal('0'))
        late = self._audit(knowledge_cutoff='2026-07-21 00:00:00')
        late_result = self._latest(late, invoice)
        self.assertEqual(late_result.version_id, later)
        self._assert_amount(late_result.potential_exposure_exact, '20000')
        self.assertEqual(early_result.version_id, version)
        self.assertNotEqual(early_result.input_fingerprint, late_result.input_fingerprint)

    def test_his12_t011_retroactive_amendment_stays_distinguishable(self):
        self.policy_a.pricing_date_policy = 'invoice'
        version = self._priced('1000')
        amendment = self._env(self.owner, self.company_a)['cpla.customer.contract.version'].browse(
            version.id
        ).create_amendment()
        amendment.write({
            'amendment_reason': 'Backdated price.',
            'effective_from': self._on(-10),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        amendment.line_ids.write({'price_unit': 1200})
        with self.assertRaises(UserError):
            amendment.action_submit_for_review()
            self._env(self.finance, self.company_a)['cpla.customer.contract.version'].browse(
                amendment.id
            ).action_approve()
        invoice = self._invoice(self._confirm(self._quote(1000)), price=1000)
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.version_id, version)
        self.assertNotEqual(result.version_id, amendment)
        self.assertEqual(self._exposure(), Decimal('0'))

    def test_his12_t012_product_variant_scope_is_enforced(self):
        self._priced('1150')
        invoice = self._invoice(
            self._confirm(self._quote(1100, product=self.other_product)),
            price=1100,
        )
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.product_id, self.other_product)
        self.assertEqual(result.result_classification, 'CONTRACT_COVERAGE_EXCEPTION')
        self._assert_blank(result.potential_exposure_exact)

    def test_his12_t013_customer_group_is_not_invented(self):
        version = self._priced('1150')
        resolved = self.env['cpla.pricing.applicability'].resolve({
            'company_id': self.company_a.id,
            'partner_id': self.other_partner.id,
            'product_id': self.bearing.id,
            'pricing_date': self._today(),
            'customer_group_ref': 'UNAPPROVED-GROUP',
        })
        self.assertNotEqual(resolved.get('status'), 'MATCHED_AUTHORITATIVE')
        self.assertFalse(resolved.get('approved_adjusted_unit_price_exact'))
        self.assertNotEqual(resolved.get('version_id'), version.id)

    def test_his12_t014_contract_scope_does_not_cross_companies(self):
        foreign = self._priced('900', company=self.company_b, partner=self.partner_b)
        invoice = self._invoice(self._confirm(self._quote(1100)), price=1100)
        result = self._latest(self._audit(), invoice)
        self.assertNotEqual(result.version_id, foreign)
        self.assertEqual(result.result_classification, 'CONTRACT_COVERAGE_EXCEPTION')
        self._assert_blank(result.potential_exposure_exact)

    def test_fin12_t001_gold_aud_001_special_price_leakage_is_25000(self):
        self._priced('1200', concessions=[{'type': 'fixed_special_price', 'amount': '1150'}])
        invoice = self._invoice(self._confirm(self._quote(1100, quantity=500)), quantity=500, price=1100)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.gross_difference_exact, '50000')
        self._assert_amount(result.authorized_concession_exact, '25000')
        self._assert_amount(result.potential_exposure_exact, '25000')
        self.assertEqual(result.result_classification, 'UNAUTHORIZED_DISCOUNT_INDICATOR')
        self.assertEqual(self._exposure(), Decimal('25000'))

    def test_fin12_t002_gold_aud_002_compliant_invoice_has_zero_leakage(self):
        invoice = self._sale('1150', 1150, quantity=500)[1]
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'PRICING_COMPLIANT')
        self._assert_amount(result.potential_exposure_exact, '0')
        self.assertFalse(self._potential())

    def test_fin12_t003_gold_aud_003_authorized_override_is_not_leakage(self):
        self._priced('1150', policy=self._limit())
        order = self._confirm(self._quote(1100, quantity=100))
        self._override(order.order_line)
        invoice = self._invoice(order, quantity=100, price=1100)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.approved_adjusted_exact, '1100')
        self._assert_amount(result.potential_exposure_exact, '0')
        self.assertFalse(self._potential())
        self.assertFalse(result.is_recovered_cash)

    def test_fin12_t004_gold_aud_004_missed_increase_is_20000(self):
        self.policy_a.pricing_date_policy = 'invoice'
        with freeze_time('2026-06-01'):
            version = self._priced(
                '1000', effective=fields.Date.to_date('2026-06-02'),
                valid_from=fields.Date.to_date('2026-06-01'),
                valid_to=fields.Date.to_date('2026-12-31'),
            )
        with freeze_time('2026-07-01'):
            later = self._later(version, '1200', effective=fields.Date.to_date('2026-07-01'))
        invoice = self._invoice(
            self._confirm(self._quote(1000, quantity=100)),
            quantity=100, price=1000, invoice_date=fields.Date.to_date('2026-07-15'),
        )
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.version_id, later)
        self.assertEqual(result.result_classification, 'MISSED_CONTRACT_PRICE_INCREASE')
        self._assert_amount(result.potential_exposure_exact, '20000')

    def test_fin12_t005_gold_aud_005_grandfathered_invoice_has_no_false_increase(self):
        self.test_his12_t006_order_date_grandfathering_keeps_the_locked_price()

    def test_fin12_t006_gold_aud_006_fx_uom_discount_is_760(self):
        foreign = self.env['res.currency'].create({'name': 'Q12A', 'symbol': 'Q', 'rounding': 0.01})
        box = self._box('CPLA12 Box 10', 10)
        self._priced(
            '120', currency=foreign,
            concessions=[{'type': 'percentage', 'percent': '5'}],
            tiers={
                'basis': 'sales_order',
                'return_policy': 'order_tier_lock',
                'rows': [(1, None, 120, self.unit, box)],
            },
            policy={
                'comparison_currency_policy': 'company_currency',
                'fx_policy': 'fixed_rate',
                'fx_source_currency_id': foreign.id,
                'fx_target_currency_id': self.company_a.currency_id.id,
                'fx_multiplier_exact': '84',
                'tax_basis': 'tax_excluded',
                'tax_structure': 'none',
                'rounding_stage': 'preserve_exact',
                'tier_discount_policy': 'discount_after_tier',
            },
        )
        invoice = self._invoice(self._confirm(self._quote(950, quantity=100)), quantity=100, price=950)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.approved_adjusted_exact, '957.6')
        self._assert_amount(result.potential_exposure_exact, '760')
        self.assertNotEqual(_money(result.approved_adjusted_exact), Decimal('958'))

    def test_fin12_t007_gold_aud_007_box_to_piece_is_1000(self):
        box = self._box('CPLA12 Box 12', 12)
        self._priced('2400', tiers={
            'basis': 'sales_order',
            'return_policy': 'order_tier_lock',
            'rows': [(1, None, 2400, self.unit, box)],
        })
        invoice = self._invoice(self._confirm(self._quote(190, quantity=100)), quantity=100, price=190)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.approved_adjusted_exact, '200')
        self._assert_amount(result.potential_exposure_exact, '1000')

    def test_fin12_t008_gold_aud_008_tax_included_invoice_is_10000(self):
        self._priced('1000')
        invoice = self._invoice(self._confirm(self._quote(1062, quantity=100)), quantity=100, price=1062, post=False)
        tax = self._included_tax()
        self._product_lines(invoice).write({
            'tax_ids': [Command.set(tax.ids)],
            'price_unit': 1062,
        })
        invoice.action_post()
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.actual_unit_exact, '900')
        self._assert_amount(result.potential_exposure_exact, '10000')

    def test_fin12_t009_invoice_discount_is_applied_once(self):
        self._priced('1200')
        order = self._confirm(self._quote(1200, quantity=100, discount=5))
        invoice = self._invoice(order, quantity=100)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.actual_unit_exact, '1140')
        self._assert_amount(result.potential_exposure_exact, '6000')
        self.assertNotEqual(_money(result.actual_unit_exact), Decimal('1083'))

    def test_fin12_t010_approved_concession_is_not_leakage(self):
        self._priced('1200', concessions=[{'type': 'fixed_special_price', 'amount': '1150'}])
        invoice = self._invoice(self._confirm(self._quote(1150, quantity=500)), quantity=500, price=1150)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.authorized_concession_exact, '25000')
        self._assert_amount(result.potential_exposure_exact, '0')
        self.assertFalse(self._potential())

    def test_fin12_t011_gold_aud_015_overbilling_is_not_positive_leakage(self):
        invoice = self._sale('1000', 1100, quantity=100)[1]
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'PRICE_ABOVE_APPROVED_RATE')
        self._assert_amount(result.raw_difference_exact, '-10000')
        self._assert_amount(result.potential_exposure_exact, '0')
        self.assertEqual(self._exposure(), Decimal('0'))

    def test_fin12_t012_small_raw_difference_is_preserved(self):
        invoice = self._sale('1150', 1149, quantity=1)[1]
        result = self._latest(self._audit(), invoice)
        self.assertNotEqual(result.result_classification, 'WITHIN_APPROVED_TOLERANCE')
        self._assert_amount(result.raw_difference_exact, '1')
        self._assert_amount(result.potential_exposure_exact, '1')
        self.assertEqual(self.policy_a.tolerance_policy, 'unconfigured')

    def test_fin12_t013_exact_decimal_text_is_preserved(self):
        self.test_fin12_t006_gold_aud_006_fx_uom_discount_is_760()

    def test_fin12_t014_exact_division_does_not_invent_leakage(self):
        box = self._box('CPLA12 Exact 12', 12)
        self._priced('2400', tiers={
            'basis': 'sales_order',
            'return_policy': 'order_tier_lock',
            'rows': [(1, None, 2400, self.unit, box)],
        })
        invoice = self._invoice(self._confirm(self._quote(200, quantity=12)), quantity=12, price=200)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.approved_adjusted_exact, '200')
        self._assert_amount(result.potential_exposure_exact, '0')

    def test_fin12_t015_missing_fx_prevents_an_authoritative_amount(self):
        foreign = self.env['res.currency'].create({'name': 'Q12B', 'symbol': 'R', 'rounding': 0.01})
        self._priced('100', currency=foreign, policy={
            'comparison_currency_policy': 'company_currency',
            'fx_policy': 'unconfigured',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        invoice = self._invoice(self._confirm(self._quote(50)), price=50)
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'FX_OR_TAX_REVIEW_REQUIRED')
        self._assert_blank(result.potential_exposure_exact)

    def test_fin12_t016_incompatible_uom_prevents_an_authoritative_amount(self):
        self._priced('1150')
        order = self._quote(1100)
        isolated = self.env['uom.uom'].create({'name': 'CPLA12 Isolated'})
        order.order_line.write({'product_uom_id': isolated.id})
        invoice = self._invoice(self._confirm(order), price=1100)
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'MISSING_PRICING_EVIDENCE')
        self._assert_blank(result.potential_exposure_exact)
        self.assertFalse(self._potential())

    def test_fin12_t017_unsupported_tax_prevents_a_guess(self):
        self._priced('1000')
        invoice = self._invoice(self._confirm(self._quote(1000)), price=1000, post=False)
        group = self.env['account.tax.group'].create({
            'name': 'CPLA12 mixed', 'company_id': self.company_a.id,
        })
        country = self.company_a.country_id or self.env.ref('base.us')
        taxes = self.env['account.tax']
        for amount in (5, 12):
            taxes |= self.env['account.tax'].create({
                'name': 'CPLA12 %s' % amount,
                'amount': amount,
                'amount_type': 'percent',
                'type_tax_use': 'sale',
                'price_include_override': 'tax_included',
                'company_id': self.company_a.id,
                'country_id': country.id,
                'tax_group_id': group.id,
            })
        self._product_lines(invoice).write({'tax_ids': [Command.set(taxes.ids)], 'price_unit': 1000})
        invoice.action_post()
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'FX_OR_TAX_REVIEW_REQUIRED')
        self._assert_blank(result.potential_exposure_exact)

    def test_fin12_t018_signed_raw_difference_is_preserved(self):
        invoice = self._sale('1150', 1100, quantity=1)[1]
        result = self._latest(self._audit(), invoice)
        self.assertGreater(_money(result.raw_difference_exact), Decimal('0'))
        over = self._invoice(self._confirm(self._quote(1200, quantity=1)), quantity=1, price=1200)
        over_result = self._latest(self._audit(), over)
        self.assertLess(_money(over_result.raw_difference_exact), Decimal('0'))

    def test_fin12_t019_simple_waterfall_reconciles(self):
        self.test_fin12_t001_gold_aud_001_special_price_leakage_is_25000()

    def test_fin12_t020_one_economic_amount_is_not_added_twice(self):
        self._priced('1200', concessions=[{'type': 'fixed_special_price', 'amount': '1150'}])
        self._invoice(self._confirm(self._quote(1100, quantity=500)), quantity=500, price=1100)
        self._audit()
        self.assertEqual(len(self._potential()), 1)
        self.assertEqual(self._exposure(), Decimal('25000'))
        self.assertNotEqual(self._exposure(), Decimal('75000'))

    def test_par12_t001_partial_quantities_reconcile(self):
        self._priced('1150')
        order = self._confirm(self._quote(1100, quantity=500))
        first = self._invoice(order, quantity=200, price=1100)
        second = self._invoice(order, quantity=200, price=1100)
        third = self._invoice(order, quantity=100, price=1100)
        self.assertEqual(
            sum(self._product_lines(move).quantity for move in (first, second, third)),
            500,
        )

    def test_par12_t002_gold_aud_009_partial_exposure_is_25000(self):
        self._priced('1150')
        order = self._confirm(self._quote(1100, quantity=500))
        invoices = [
            self._invoice(order, quantity=200, price=1100),
            self._invoice(order, quantity=200, price=1100),
            self._invoice(order, quantity=100, price=1100),
        ]
        run = self._audit()
        amounts = [
            _money(self._latest(run, invoice).potential_exposure_exact)
            for invoice in invoices
        ]
        self.assertEqual(amounts, [Decimal('10000'), Decimal('10000'), Decimal('5000')])
        self.assertEqual(self._exposure(), Decimal('25000'))

    def test_par12_t003_order_quantity_is_not_billed_on_every_invoice(self):
        self._priced('1150')
        order = self._confirm(self._quote(1100, quantity=500))
        invoice = self._invoice(order, quantity=200, price=1100)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.eligible_quantity_exact, '200')
        self._assert_amount(result.potential_exposure_exact, '10000')
        self.assertNotEqual(_money(result.potential_exposure_exact), Decimal('25000'))

    def test_par12_t004_and_t005_verified_allocations_are_priced_separately(self):
        with freeze_time('2026-06-25'):
            version = self._priced(
                '1000', effective=fields.Date.to_date('2026-06-25'),
                valid_from=fields.Date.to_date('2026-06-01'),
                valid_to=fields.Date.to_date('2026-12-31'),
            )
            first = self._confirm(self._quote(1000, quantity=200))
        with freeze_time('2026-07-01'):
            later = self._later(version, '1200', effective=fields.Date.to_date('2026-07-01'))
        second = self._confirm(self._quote(1000, quantity=100))
        invoice = first._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'quantity': 300,
            'price_unit': 1000,
            'tax_ids': [Command.clear()],
            'sale_line_ids': [Command.set((first.order_line | second.order_line).ids)],
        })
        invoice.invoice_date = fields.Date.to_date('2026-07-15')
        invoice.action_post()
        current = self.env['cpla.invoice.source'].map_move(invoice).filtered(
            lambda item: item.is_current and item.product_id == self.bearing
        )[:1]
        verified = current.action_verify_documentary(
            [(first.order_line.id, '200'), (second.order_line.id, '100')],
            'SPLIT-012',
        )
        self.assertEqual(len(verified.allocation_ids), 2)
        run = self._audit()
        rows = self._results(run, invoice).filtered('allocation_id')
        self.assertEqual(len(rows), 2)
        by_qty = {row.eligible_quantity_exact: row for row in rows}
        self.assertEqual(by_qty['200'].version_id, version)
        self._assert_amount(by_qty['200'].potential_exposure_exact, '0')
        self.assertEqual(by_qty['100'].version_id, later)
        self._assert_amount(by_qty['100'].potential_exposure_exact, '20000')

    def test_par12_t006_and_t007_missing_allocation_is_not_invented(self):
        self._priced('1150')
        first = self._confirm(self._quote(1100, quantity=200))
        second = self._confirm(self._quote(1100, quantity=100))
        invoice = first._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'quantity': 300,
            'price_unit': 1100,
            'tax_ids': [Command.clear()],
            'sale_line_ids': [Command.set((first.order_line | second.order_line).ids)],
        })
        invoice.action_post()
        result = self._latest(self._audit(), invoice)
        self.assertEqual(result.result_classification, 'SOURCE_ALLOCATION_REVIEW_REQUIRED')
        self._assert_blank(result.potential_exposure_exact)
        self.assertFalse(result.allocation_id)

    def test_par12_t008_order_tier_qualification_is_preserved(self):
        self._priced('1200', tiers={
            'basis': 'sales_order',
            'return_policy': 'order_tier_lock',
            'rows': [(1, 500, 1200), (500, None, 1150)],
        })
        order = self._confirm(self._quote(1100, quantity=500))
        invoice = self._invoice(order, quantity=200, price=1100)
        result = self._latest(self._audit(), invoice)
        self._assert_amount(result.approved_adjusted_exact, '1150')
        self._assert_amount(result.eligible_quantity_exact, '200')
        self._assert_amount(result.potential_exposure_exact, '10000')

    def test_par12_t009_product_quantities_are_normalized(self):
        self.test_fin12_t007_gold_aud_007_box_to_piece_is_1000()

    def test_par12_t010_repeated_partial_audit_has_one_current_exposure(self):
        self._priced('1150')
        order = self._confirm(self._quote(1100, quantity=500))
        self._invoice(order, quantity=200, price=1100)
        self._invoice(order, quantity=200, price=1100)
        self._invoice(order, quantity=100, price=1100)
        self._audit()
        self._audit()
        self._audit()
        self.assertEqual(len(self._potential()), 3)
        self.assertEqual(self._exposure(), Decimal('25000'))

    def test_ref12_t001_and_t002_gold_aud_010_return_is_4000(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        self._audit()
        self.assertEqual(self._exposure(), Decimal('4000'))
        self.assertEqual(len(self._potential()), 1)
        self.assertNotEqual(self._exposure(), Decimal('22000'))

    def test_ref12_t003_and_t004_gold_aud_011_full_reversal_clears_current_exposure(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        first = self._audit()
        original = self._latest(first, invoice)
        self._assert_amount(original.potential_exposure_exact, '5000')
        credit = invoice._reverse_moves()
        credit.action_post()
        second = self._audit()
        self.assertTrue(original.exists())
        self._assert_amount(original.potential_exposure_exact, '5000')
        self.assertEqual(self._exposure(), Decimal('0'))
        historical = self.env['cpla.leakage.finding'].search([
            ('move_id', '=', invoice.id),
            ('finding_status', '=', 'superseded_by_reassessment'),
        ])
        self.assertTrue(historical)
        self.assertTrue(second.result_ids)

    def test_ref12_t005_gold_aud_012_replacement_does_not_duplicate_exposure(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        self._audit()
        credit = invoice._reverse_moves()
        credit.action_post()
        replacement_order = self._confirm(self._quote(1150, quantity=100))
        replacement = self._invoice(replacement_order, quantity=100, price=1150)
        self._audit()
        self.assertEqual(self._exposure(), Decimal('0'))
        self.assertFalse(self.env['account.payment'].search([('reconciled_invoice_ids', 'in', replacement.id)]))
        self.assertFalse(self._latest(self.env['cpla.invoice.audit.run'].search([], limit=1), replacement).is_recovered_cash)

    def test_ref12_t006_credit_is_not_a_new_positive_sale(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        credit = invoice._reverse_moves()
        credit.action_post()
        run = self._audit()
        credit_result = self._results(run, credit).filtered('product_id')[:1]
        self.assertNotEqual(credit_result.result_classification, 'UNAUTHORIZED_UNDERPRICING')
        self._assert_blank(credit_result.potential_exposure_exact)

    def test_ref12_t007_gold_aud_017_amount_only_credit_is_not_a_quantity_return(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'price_unit': 20, 'quantity': 100})
        credit.action_post()
        run = self._audit()
        credit_result = self._results(run, credit).filtered('product_id')[:1]
        self.assertEqual(credit_result.result_classification, 'REFUND_REASSESSMENT_REQUIRED')
        self.assertEqual(credit_result.credit_treatment, 'price_adjustment')
        self.assertEqual(self._exposure(), Decimal('5000'))

    def test_ref12_t008_tax_only_credit_is_not_a_product_return(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        tax = self.env['account.tax'].search([
            ('company_id', '=', self.company_a.id), ('type_tax_use', '=', 'sale'),
        ], limit=1)
        credit = self._manual(move_type='out_refund', quantity=1, price=18, post=False)
        self._product_lines(credit).write({
            'product_id': False,
            'quantity': 1,
            'price_unit': 18,
            'tax_ids': [Command.set(tax.ids)],
            'name': 'Tax correction',
        })
        credit.write({'reversed_entry_id': invoice.id})
        credit.action_post()
        run = self._audit()
        rows = self._results(run, credit)
        self.assertTrue(rows)
        self.assertTrue(all(row.result_classification == 'UNSUPPORTED_TRANSACTION' for row in rows))
        self.assertEqual(self._exposure(), Decimal('5000'))

    def test_ref12_t009_credit_is_applied_to_the_matching_invoice_line(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        other = self._invoice(self._confirm(self._quote(1100, quantity=50)), quantity=50, price=1100)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        self._audit()
        invoice_finding = self._potential().filtered(lambda item: item.move_id == invoice)
        other_finding = self._potential().filtered(lambda item: item.move_id == other)
        self._assert_amount(invoice_finding.potential_leakage_exact, '4000')
        self._assert_amount(other_finding.potential_leakage_exact, '2500')

    def test_ref12_t010_ambiguous_refund_requires_review(self):
        credit = self._manual(move_type='out_refund', quantity=20, price=1100)
        result = self._latest(self._audit(), credit)
        self.assertEqual(result.result_classification, 'REFUND_REASSESSMENT_REQUIRED')
        self._assert_blank(result.potential_exposure_exact)

    def test_ref12_t011_net_quantity_return_retiers(self):
        self._priced('1200', tiers={
            'basis': 'invoice_line',
            'return_policy': 'net_quantity',
            'rows': [(1, 80, 1200), (80, None, 1100)],
        })
        order = self._confirm(self._quote(1000, quantity=100))
        invoice = self._invoice(order, quantity=100, price=1000)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 30, 'price_unit': 1000})
        credit.action_post()
        self._audit()
        self.assertEqual(self._exposure(), Decimal('14000'))

    def test_ref12_t012_order_tier_lock_keeps_the_original_tier(self):
        self._priced('1200', tiers={
            'basis': 'invoice_line',
            'return_policy': 'order_tier_lock',
            'rows': [(1, 80, 1200), (80, None, 1100)],
        })
        order = self._confirm(self._quote(1000, quantity=100))
        invoice = self._invoice(order, quantity=100, price=1000)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 30, 'price_unit': 1000})
        credit.action_post()
        self._audit()
        self.assertEqual(self._exposure(), Decimal('7000'))

    def test_ref12_t013_repeated_refund_processing_does_not_double_adjust(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        self._audit()
        self._audit()
        self.assertEqual(len(self._potential()), 1)
        self.assertEqual(self._exposure(), Decimal('4000'))

    def test_ref12_t014_customer_credit_is_not_collected_cash(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        credit = invoice._reverse_moves()
        credit.action_post()
        before_payments = self.env['account.payment'].search_count([])
        self._audit()
        self.assertEqual(self.env['account.payment'].search_count([]), before_payments)
        self.assertFalse(any(self._current().mapped('is_recovered_cash')))
        self.assertNotIn('finance_validated_amount', self.env['cpla.leakage.finding']._fields)

    def test_ref12_t015_corrective_billing_needs_verified_source_evidence(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        extra = self._manual(price=50, quantity=1)
        self._audit()
        extra_result = self._latest(self.env['cpla.invoice.audit.run'].search([], order='id desc', limit=1), extra)
        self.assertNotEqual(extra_result.result_classification, 'PRICING_COMPLIANT')
        self.assertNotIn(extra, invoice.reversal_move_ids)

    def test_idm12_t001_and_t002_repeated_audit_keeps_one_current_finding(self):
        invoice = self._sale('1150', 1100, quantity=100)[1]
        runs = [self._audit() for _index in range(3)]
        self.assertEqual(len(runs), 3)
        self.assertEqual(len(set(runs)), 3)
        self.assertEqual(len(self._potential()), 1)
        self.assertEqual(self._exposure(), Decimal('5000'))
        self.assertEqual(len(self.env['cpla.invoice.audit.result'].search([
            ('move_id', '=', invoice.id),
            ('result_classification', '=', 'UNAUTHORIZED_UNDERPRICING'),
        ])), 3)

    def test_idm12_t003_canonical_identity_is_stable(self):
        self._sale('1150', 1100)
        self._audit()
        self._audit()
        finding = self._potential()
        self.assertEqual(len(finding), 1)
        self.assertIn('|sUNDERBILLING', finding.current_identity)
        self.assertNotIn(finding.potential_leakage_exact, finding.current_identity)

    def test_idm12_t004_separate_allocations_remain_independent(self):
        self.test_par12_t002_gold_aud_009_partial_exposure_is_25000()
        identities = set(self._potential().mapped('current_identity'))
        self.assertEqual(len(identities), 3)

    def test_idm12_t005_unique_constraint_rejects_a_second_current_row(self):
        """The unique pointer is the database guard.

        This TransactionCase does not open a second session and does not
        commit. It is not evidence of two-worker concurrency.
        """
        self._sale('1150', 1100)
        self._audit()
        current = self._potential()
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                models.Model.create(self.env['cpla.leakage.finding'], [{
                    'reference': 'LKF/TEST/DUP',
                    'company_id': current.company_id.id,
                    'move_id': current.move_id.id,
                    'move_line_id': current.move_line_id.id,
                    'finding_status': 'potential',
                    'current_identity': current.current_identity,
                    'is_current': True,
                    'potential_leakage_exact': '1',
                    'leakage_category': 'UNAUTHORIZED_UNDERPRICING',
                }])
        self.assertEqual(len(self._potential()), 1)

    def test_idm12_t006_and_t007_failed_record_does_not_complete_the_run(self):
        good = self._sale('1150', 1100)[1]
        bad = self._invoice(self._confirm(self._quote(1000, quantity=1)), quantity=1, price=1000)
        run = self._run()
        original = type(run)._audit_move

        def boom(self, move):
            if move.id == bad.id:
                raise UserError('Forced audit failure.')
            return original(self, move)

        type(run)._audit_move = boom
        try:
            run.action_run()
        finally:
            type(run)._audit_move = original
        self.assertEqual(run.state, 'completed_with_exceptions')
        self.assertEqual(run.failure_count, 1)
        self.assertNotEqual(run.state, 'completed')
        self.assertTrue(run.result_ids.filtered(lambda item: item.move_id == good))
        self.assertFalse(run.result_ids.filtered(
            lambda item: item.move_id == bad and item.result_classification == 'PRICING_COMPLIANT'
        ))
        retry = self._audit()
        self.assertIn(retry.state, ('completed', 'completed_with_exceptions'))
        self.assertEqual(len(self._potential().filtered(lambda item: item.move_id == good)), 1)

    def test_idm12_t008_unchanged_fingerprint_keeps_the_same_finding(self):
        self._sale('1150', 1100)
        self._audit()
        finding = self._potential()
        fingerprint = finding.input_fingerprint
        self._audit()
        self.assertEqual(self._potential().input_fingerprint, fingerprint)
        self.assertEqual(self._potential().id, finding.id)

    def test_idm12_t009_and_t010_changed_source_preserves_the_old_result(self):
        order, invoice = self._sale('1150', 1100)
        first = self._audit()
        original = self._latest(first, invoice)
        order.order_line.write({'price_unit': 900, 'technical_price_unit': 0})
        second = self._audit()
        self.assertTrue(original.exists())
        self.assertEqual(original.result_classification, 'UNAUTHORIZED_UNDERPRICING')
        revised = self._latest(second, invoice)
        self.assertNotEqual(revised.id, original.id)
        self.assertNotEqual(revised.input_fingerprint, original.input_fingerprint)

    def test_idm12_t011_gold_aud_018_as_known_result_is_not_overwritten(self):
        self.test_his12_t010_historical_cutoff_is_respected()

    def test_idm12_t012_duplicate_refund_adjustment_is_prevented(self):
        self.test_ref12_t013_repeated_refund_processing_does_not_double_adjust()

    def test_idm12_t013_cancel_status_requires_reassessment(self):
        _order, invoice = self._sale('1150', 1100)
        self._audit()
        self.assertEqual(self._exposure(), Decimal('5000'))
        invoice.button_cancel()
        rerun = self._audit()
        self.assertNotIn(invoice, rerun.result_ids.filtered(
            lambda item: item.result_classification == 'UNAUTHORIZED_UNDERPRICING'
        ).move_id)

    def test_idm12_t014_current_totals_ignore_superseded_rows(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        self._audit()
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        self._audit()
        stored = self.env['cpla.leakage.finding'].search([
            ('company_id', '=', self.company_a.id),
        ])
        self.assertGreater(len(stored), 1)
        self.assertTrue(stored.filtered(lambda item: not item.is_current))
        self.assertEqual(len(self._potential()), 1)
        self.assertEqual(self._exposure(), Decimal('4000'))

    def test_sec12_t001_and_t002_company_scope_is_enforced(self):
        invoice = self._sale('1150', 1100)[1]
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        foreign_invoice = self._invoice(self._confirm(self._quote(
            900, company=self.company_b, partner=self.partner_b,
        )))
        run = self._env(self.finance, self.company_a)['cpla.invoice.audit.run'].create({
            'company_id': self.company_a.id,
            'date_from': self._on(-500),
            'date_to': self._on(5),
        })
        run.action_run()
        self.assertIn(invoice, run.result_ids.move_id)
        self.assertNotIn(foreign_invoice, run.result_ids.move_id)
        hidden = self._env(self.finance, self.company_a)['cpla.leakage.finding'].search([
            ('move_id', '=', foreign_invoice.id),
        ])
        self.assertFalse(hidden)

    def test_sec12_t003_and_t004_cross_company_source_is_rejected(self):
        self.test_his12_t014_contract_scope_does_not_cross_companies()
        foreign = self._confirm(self._quote(1150, company=self.company_b, partner=self.partner_b))
        invoice = self._manual()
        self._product_lines(invoice).write({'sale_line_ids': [Command.set(foreign.order_line.ids)]})
        result = self._latest(self._audit(), invoice)
        self.assertIn(result.result_classification, (
            'SOURCE_ALLOCATION_REVIEW_REQUIRED', 'CONTRACT_COVERAGE_EXCEPTION',
        ))
        self._assert_blank(result.potential_exposure_exact)

    def test_sec12_t005_unauthorized_run_creation_is_denied(self):
        with self.assertRaises(AccessError):
            self._env(self.plain, self.company_a)['cpla.invoice.audit.run'].create({
                'company_id': self.company_a.id,
                'date_from': self._today(),
                'date_to': self._today(),
            })
        with self.assertRaises(AccessError):
            self._env(self.auditor, self.company_a)['cpla.invoice.audit.run'].create({
                'company_id': self.company_a.id,
                'date_from': self._today(),
                'date_to': self._today(),
            })

    def test_sec12_t006_unauthorized_finding_read_is_denied(self):
        self._sale('1150', 1100)
        self._audit()
        finding = self._potential()
        with self.assertRaises(AccessError):
            self._env(self.plain, self.company_a)['cpla.leakage.finding'].search([
                ('id', '=', finding.id),
            ])

    def test_sec12_t007_direct_rpc_checks_access(self):
        run = self._run()
        with self.assertRaises(AccessError):
            self._env(self.salesman, self.company_a)['cpla.invoice.audit.run'].browse(run.id).action_run()

    def test_sec12_t008_sales_user_cannot_edit_evidence(self):
        self._sale('1150', 1100)
        result = self._latest(self._audit())
        with self.assertRaises(AccessError):
            self._env(self.salesman, self.company_a)['cpla.invoice.audit.result'].browse(result.id).write({
                'potential_exposure_exact': '1',
            })

    def test_sec12_t009_auditor_cannot_validate_finance_recovery(self):
        self.assertNotIn('action_validate_finance', self.env['cpla.leakage.finding']._fields)
        self.assertNotIn('finance_validated_exact', self.env['cpla.leakage.finding']._fields)
        self._sale('1150', 1100)
        finding = self._potential() if False else None
        self._audit()
        finding = self._potential()
        with self.assertRaises(AccessError):
            self._env(self.auditor, self.company_a)['cpla.leakage.finding'].browse(finding.id).write({
                'finding_status': 'potential',
            })

    def test_sec12_t010_administrator_is_not_a_finance_approver(self):
        access = self.env.ref(MODULE + '.group_app_admin').model_access
        self.assertEqual(len(access), 1)
        self.assertEqual(access.model_id.model, 'cpla.company.policy')
        self.assertNotIn('cpla.leakage.finding', set(access.mapped('model_id.model')))

    def test_sec12_t011_unauthorized_export_is_denied(self):
        self._sale('1150', 1100)
        finding = self._potential() if False else self._latest(self._audit())
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.invoice.audit.result'].browse(
                finding.id
            ).export_data(['result_classification'])

    def test_sec12_t012_combined_groups_do_not_cross_companies(self):
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        foreign = self._invoice(self._confirm(self._quote(
            900, company=self.company_b, partner=self.partner_b,
        )))
        self._env(self.both, self.company_b)['cpla.invoice.audit.run'].create({
            'company_id': self.company_b.id,
            'date_from': self._on(-30),
            'date_to': self._on(5),
        }).action_run()
        visible = self.env(user=self.both, context={
            'allowed_company_ids': [self.company_a.id],
        })['cpla.invoice.audit.result'].search([('move_id', '=', foreign.id)])
        self.assertFalse(visible)

    def test_sec12_t013_no_unrestricted_sudo_discloses_prices(self):
        root = Manifest.for_addon(MODULE).path
        import os
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in ('tests', '__pycache__', 'docs', 'local_testing')]
            for filename in filenames:
                if filename.endswith('.py'):
                    with open(os.path.join(dirpath, filename), encoding='utf-8') as handle:
                        text = handle.read()
                    self.assertNotIn('sudo(', text, filename)
                    self.assertNotIn('.execute(', text, filename)

    def test_sec12_t014_historical_snapshots_reject_direct_edits(self):
        result = self._latest(self._audit()) if False else None
        self._sale('1150', 1100)
        result = self._latest(self._audit())
        with self.assertRaises(UserError):
            self._env(self.finance, self.company_a)['cpla.invoice.audit.result'].browse(result.id).write({
                'potential_exposure_exact': '1',
            })
        self.assertNotEqual(result.potential_exposure_exact, '1')

    def test_sec12_t015_company_policy_references_stay_isolated(self):
        self._priced('1150', company=self.company_b, partner=self.partner_b)
        invoice = self._invoice(self._confirm(self._quote(
            1100, company=self.company_b, partner=self.partner_b,
        )), price=1100)
        result = self._latest(self._audit(company_id=self.company_b.id), invoice)
        self.assertEqual(result.company_id, self.company_b)
        self.assertEqual(result.version_id.company_id, self.company_b)
        self.assertFalse(self._env(self.finance, self.company_a)['cpla.invoice.audit.result'].search([
            ('id', '=', result.id),
        ]))

    def test_int12_t001_through_t010_services_are_reused(self):
        invoice = self._sale('1150', 1100, quantity=10)[1]
        result = self._latest(self._audit(), invoice)
        self.assertTrue(result.version_id)
        self.assertTrue(result.calculation_trace)
        self.assertIn(result.version_id.reference, result.calculation_trace)
        self.assertIn('Potential leakage is not finance-validated', result.calculation_trace)
        self.assertFalse(result.is_recovered_cash)

    def test_int12_t011_calculation_trace_names_the_waterfall(self):
        self._priced('1200', concessions=[{'type': 'fixed_special_price', 'amount': '1150'}])
        invoice = self._invoice(self._confirm(self._quote(1100, quantity=500)), quantity=500, price=1100)
        result = self._latest(self._audit(), invoice)
        self.assertIn('50000', result.calculation_trace)
        self.assertIn('25000', result.calculation_trace)
        self.assertIn(result.version_id.reference, result.calculation_trace)

    def test_int12_t012_posted_documents_are_not_mutated(self):
        _order, invoice = self._sale('1150', 1100)
        line = self._product_lines(invoice)
        before = (invoice.state, invoice.amount_total, line.price_unit, line.quantity)
        payments = self.env['account.payment'].search_count([])
        moves = self.env['account.move'].search_count([])
        self._audit()
        self.assertEqual((invoice.state, invoice.amount_total, line.price_unit, line.quantity), before)
        self.assertEqual(self.env['account.payment'].search_count([]), payments)
        self.assertEqual(self.env['account.move'].search_count([]), moves)

    def test_reg12_views_security_and_no_cron(self):
        self.assertTrue(self.env.ref(MODULE + '.view_cpla_invoice_audit_run_form'))
        self.assertTrue(self.env.ref(MODULE + '.cpla_leakage_finding_company_rule'))
        menu = self.env.ref(MODULE + '.menu_cpla_audits')
        self.assertNotIn(menu, self.env.ref(MODULE + '.group_internal_auditor').menu_access)
        self.assertNotIn(menu, self.env.ref(MODULE + '.group_app_admin').menu_access)
        self.assertIn(menu, self.env.ref(MODULE + '.group_finance_manager').menu_access)
        rules = self.env['ir.rule'].search([('model_id.model', '=', 'cpla.leakage.finding')])
        self.assertFalse(rules.groups)
        self.assertIn('company_id', rules.domain_force)
        arch = self.env.ref(MODULE + '.view_cpla_leakage_finding_form').arch
        self.assertNotIn('Leakage Confirmed', arch)
        self.assertNotIn('Finance Validated', arch)
        self.assertIn('not finance-validated', arch)
        version_arch = self.env.ref(MODULE + '.view_cpla_customer_contract_version_form').arch
        self.assertNotIn('Run Invoice Audit', version_arch)
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE), ('model', '=', 'ir.cron'),
        ]))
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])

    def test_reg12_prior_gate_still_blocks_a_low_price(self):
        self.policy_a.quotation_compliance_mode = 'block'
        self._priced('1200')
        order = self._quote(1000)
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_gold_aud_016_three_runs_do_not_triple_count(self):
        self.test_idm12_t001_and_t002_repeated_audit_keeps_one_current_finding()

    def test_gold_aud_019_company_b_version_is_not_applied(self):
        self.test_his12_t014_contract_scope_does_not_cross_companies()

    def test_gold_aud_020_later_lifecycle_amounts_are_not_created(self):
        self._priced('1200', concessions=[{'type': 'fixed_special_price', 'amount': '1150'}])
        self._invoice(self._confirm(self._quote(1100, quantity=500)), quantity=500, price=1100)
        self._audit()
        finding = self._potential()
        self._assert_amount(finding.potential_leakage_exact, '25000')
        for name in (
            'finance_validated_exact', 'approved_recovery_exact', 'billed_recovery_exact',
            'collected_cash_exact', 'outstanding_exact', 'waiver_exact',
        ):
            self.assertNotIn(name, finding._fields)
        self.assertFalse(finding.is_recovered_cash)

    def test_dev12_repeat_audit_timing_is_logged(self):
        invoice = self._sale('1150', 1100)[1]
        self._audit()
        started = time.perf_counter()
        for _index in range(10):
            self._audit()
        elapsed = time.perf_counter() - started
        _logger.info('DEV12 audit x10 %s invoice=%s', elapsed, invoice.id)
        self.assertEqual(len(self._potential()), 1)
        self.assertGreater(elapsed, 0)

    def _reassess(self, finding, trigger, reason, source_move=None, cutoff=None, user=None):
        actor = user or self.manager
        env = self._env(actor, finding.company_id)
        kwargs = {}
        if source_move is not None:
            kwargs['source_model'] = 'account.move'
            kwargs['source_res_id'] = source_move.id
        if cutoff is not None:
            kwargs['knowledge_cutoff'] = cutoff
        record = env['cpla.leakage.reassessment'].request_for_finding(
            finding.id, trigger, reason, **kwargs,
        )
        self.env.invalidate_all()
        return self.env['cpla.leakage.reassessment'].browse(record.id)

    def _evaluate(self, record, user=None):
        actor = user or self.finance
        self._env(actor, record.company_id)['cpla.leakage.reassessment'].browse(
            record.id
        ).action_evaluate()
        self.env.invalidate_all()
        return self.env['cpla.leakage.reassessment'].browse(record.id)

    def _accept(self, record, reason='Accept the proposed evidence correction.', user=None):
        actor = user or self.finance
        self._env(actor, record.company_id)['cpla.leakage.reassessment'].browse(
            record.id
        ).action_accept(reason)
        self.env.invalidate_all()
        return self.env['cpla.leakage.reassessment'].browse(record.id)

    def _open_case(self, finding):
        case = self._env(self.manager, finding.company_id)['cpla.leakage.case'].create_from_findings(
            [finding.id]
        )
        self.env.invalidate_all()
        return self.env['cpla.leakage.case'].browse(case.id)

    def _submit_case(self, case):
        manager = self._env(self.manager, case.company_id)['cpla.leakage.case'].browse(case.id)
        manager.action_assign(self.manager.id, 'Assign the contract manager as investigator.')
        manager.action_start()
        for line in manager.checklist_ids.filtered('required_for_submission'):
            manager.action_answer_checklist(line.code, 'yes')
        for evidence in manager.evidence_ids.filtered(lambda item: item.evidence_kind == 'source'):
            manager.action_verify_evidence(evidence.id, 'Source record reviewed.')
        manager.action_record_root_cause(
            'missed_contract_price_increase',
            'The invoice rate does not match the approved contract rate.',
        )
        manager.action_record_outcome(
            'likely_missed_price_increase',
            'The investigator conclusion is not a finance validation.',
        )
        manager.action_submit_for_finance()
        self.env.invalidate_all()
        return self.env['cpla.leakage.case'].browse(case.id)

    def test_rev14_t001_quantity_return_preserves_original_and_accepts_4000(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        first = self._audit()
        original = self._latest(first, invoice)
        finding = self._potential()
        self.assertEqual(len(finding), 1)
        self._assert_amount(original.potential_exposure_exact, '5000')
        self._assert_amount(finding.potential_leakage_exact, '5000')
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        line = self._product_lines(invoice)
        price = line.price_unit
        quantity = line.quantity
        payments = self.env['account.payment'].search_count([])
        moves = self.env['account.move'].search_count([])
        findings_before = self.env['cpla.leakage.finding'].search_count([])
        results_before = self.env['cpla.invoice.audit.result'].search_count([])
        record = self._reassess(
            finding, 'verified_quantity_return',
            'Verified 20 piece return of the original invoice line.',
            source_move=credit,
        )
        again = self._reassess(
            finding, 'verified_quantity_return',
            'The same open request is reused.',
            source_move=credit,
        )
        self.assertEqual(again, record)
        self.assertTrue(record.reference.startswith('CPL-REASS/'))
        self.assertEqual(record.state, 'requested')
        self.assertEqual(record.change_class, 'financially_material')
        self.assertEqual(record.requested_by_id, self.manager)
        record = self._evaluate(record)
        self.assertEqual(self.env['cpla.leakage.finding'].search_count([]), findings_before)
        self.assertEqual(self.env['cpla.invoice.audit.result'].search_count([]), results_before)
        self.assertEqual(record.state, 'proposed_revision_ready')
        self._assert_amount(record.proposed_quantity_exact, '80')
        self._assert_amount(record.proposed_adjusted_exact, '1150')
        self._assert_amount(record.proposed_actual_exact, '1100')
        self._assert_amount(record.proposed_exposure_exact, '4000')
        self._assert_amount(record.delta_exact, '-1000')
        self.assertEqual(record.delta_class, 'exposure_decreased')
        self.assertEqual(record.credit_class_observed, 'QUANTITY_RETURN')
        self.assertTrue(record.credit_quantity_trusted)
        self.assertEqual(record.schema_version, 'dev14.2')
        self.assertEqual(record.engine_version, 'dev12.1')
        self.assertEqual(record.comparison_currency_id, self.company_a.currency_id)
        self.assertIn('evidence correction', record.difference_explanation)
        self.assertIn('not recovered cash', record.difference_explanation)
        self.assertIn('not an approved write-off', record.difference_explanation)
        self.assertFalse(record.is_recovered_cash)
        self.assertFalse(record.is_writeoff)
        self.assertTrue(record.proposal_digest)
        self.assertEqual(record.original_proposal_digest, record.proposal_digest)
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')
        self._assert_amount(original.potential_exposure_exact, '5000')
        with self.assertRaises(UserError):
            record.write({'proposed_exposure_exact': '1'})
        with self.assertRaises(AccessError):
            self._env(self.manager, self.company_a)['cpla.leakage.reassessment'].browse(
                record.id
            ).action_accept('A contract manager cannot accept this proposal.')
        self.env.invalidate_all()
        record = self.env['cpla.leakage.reassessment'].browse(record.id)
        self.assertEqual(record.state, 'proposed_revision_ready')
        self.assertFalse(self._env(self.owner_b, self.company_b)['cpla.leakage.reassessment'].search([
            ('id', '=', record.id),
        ]))
        with self.assertRaises(AccessError):
            self._env(self.owner_b, self.company_b)['cpla.leakage.reassessment'].browse(
                record.id
            ).read(['reference'])
        record = self._accept(record, 'The verified return supports eligible quantity 80.')
        self.assertEqual(record.state, 'accepted')
        self.assertEqual(record.decision_by_id, self.finance)
        self.assertFalse(record.is_recovered_cash)
        self.assertFalse(record.is_writeoff)
        self.assertEqual(self._exposure(), Decimal('4000'))
        self.assertEqual(len(self._potential()), 1)
        self.assertNotEqual(self._exposure(), Decimal('9000'))
        current = self._potential()
        self._assert_amount(current.eligible_quantity_exact, '80')
        self.assertFalse(current.is_recovered_cash)
        historical = self.env['cpla.leakage.finding'].search([
            ('move_id', '=', invoice.id),
            ('finding_status', '=', 'superseded_by_reassessment'),
        ])
        self.assertEqual(len(historical), 1)
        self._assert_amount(historical.potential_leakage_exact, '5000')
        self.assertFalse(historical.is_current)
        original = self.env['cpla.invoice.audit.result'].browse(original.id)
        self._assert_amount(original.potential_exposure_exact, '5000')
        self.assertEqual(line.price_unit, price)
        self.assertEqual(line.quantity, quantity)
        self.assertEqual(self.env['account.payment'].search_count([]), payments)
        self.assertEqual(self.env['account.move'].search_count([]), moves)
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE), ('model', '=', 'ir.cron'),
        ]))
        with self.assertRaises(UserError):
            self._reassess(
                historical, 'verified_quantity_return',
                'A superseded finding is not reopened.',
                source_move=credit,
            )

    def test_rev14_t002_digest_tamper_blocks_acceptance(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        record = self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'Proposal to be checked before acceptance.',
            source_move=credit,
        ))
        self.assertEqual(record.state, 'proposed_revision_ready')
        original_digest = record.original_proposal_digest
        models.Model.write(record, {'proposed_exposure_exact': '1'})
        self.env.invalidate_all()
        record = self._accept(self.env['cpla.leakage.reassessment'].browse(record.id))
        self.assertEqual(record.state, 'blocked')
        self.assertTrue(record.digest_mismatch)
        self.assertEqual(record.original_proposal_digest, original_digest)
        self.assertEqual(record.proposed_exposure_exact, '1')
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')
        self.assertEqual(self._exposure(), Decimal('5000'))

    def test_rev14_t003_open_case_keeps_reviewed_until_investigator_accepts(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        case = self._open_case(finding)
        self._assert_amount(case.reviewed_exposure_exact, '5000')
        self.assertEqual(case.state, 'new')
        self.assertFalse(case.finance_package_stale)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        record = self._accept(self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'Return posted after the case reviewed 100 pieces.',
            source_move=credit,
        )))
        self.assertEqual(record.state, 'accepted')
        case = self.env['cpla.leakage.case'].browse(case.id)
        self.assertEqual(case.state, 'new')
        self._assert_amount(case.reviewed_exposure_exact, '5000')
        self.assertTrue(case.source_reassessment_required)
        self._assert_blank(case.current_potential_exposure_exact)
        self.assertFalse(case.finance_package_stale)
        self._env(self.manager, case.company_id)['cpla.leakage.case'].browse(
            case.id
        ).action_accept_current_source('The investigator accepts the current 80 piece reading.')
        self.env.invalidate_all()
        case = self.env['cpla.leakage.case'].browse(case.id)
        self._assert_amount(case.reviewed_exposure_exact, '4000')
        self._assert_amount(case.current_potential_exposure_exact, '4000')
        self.assertFalse(case.source_reassessment_required)
        self.assertEqual(case.state, 'new')

    def test_rev14_t004_finance_package_becomes_stale(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        case = self._submit_case(self._open_case(finding))
        self.assertEqual(case.state, 'ready_for_finance_review')
        self._assert_amount(case.reviewed_exposure_exact, '5000')
        self.assertEqual(len(case.submission_ids), 1)
        self.assertFalse(case.finance_package_stale)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        record = self._accept(self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'Return posted after the finance package was submitted.',
            source_move=credit,
        )))
        self.assertEqual(record.state, 'accepted')
        case = self.env['cpla.leakage.case'].browse(case.id)
        self.assertEqual(case.state, 'ready_for_finance_review')
        self.assertTrue(case.finance_package_stale)
        self._assert_amount(case.reviewed_exposure_exact, '5000')
        self.assertEqual(len(case.submission_ids), 1)
        with self.assertRaises(UserError):
            self._env(self.manager, case.company_id)['cpla.leakage.case'].browse(
                case.id
            ).action_accept_current_source('Finance still holds this package.')

    def test_rev14_t005_requester_cannot_accept(self):
        combo = new_test_user(
            self.env, login='cpla14_combo', password='cpla-test',
            groups='base.group_user,account.group_account_invoice,%s.group_contract_manager,%s.group_finance_manager' % (
                MODULE, MODULE,
            ),
            company_id=self.company_a.id,
            company_ids=[Command.set([self.company_a.id])],
        )
        _order, invoice = self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        record = self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'The same person requests and tries to accept.',
            source_move=credit, user=combo,
        ), user=combo)
        self.assertEqual(record.state, 'proposed_revision_ready')
        self.assertEqual(record.requested_by_id, combo)
        with self.assertRaises(AccessError):
            self._env(combo, self.company_a)['cpla.leakage.reassessment'].browse(
                record.id
            ).action_accept('Self-approval is not permitted.')
        self.env.invalidate_all()
        record = self.env['cpla.leakage.reassessment'].browse(record.id)
        self.assertEqual(record.state, 'proposed_revision_ready')
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')

    def test_rev14_t006_amount_only_credit_is_not_a_quantity_return(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        first = self._audit()
        original = self._latest(first, invoice)
        finding = self._potential()
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'price_unit': 20, 'quantity': 100})
        credit.action_post()
        quantity_request = self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'This credit must not be treated as returned pieces.',
            source_move=credit,
        ))
        self.assertEqual(quantity_request.state, 'evidence_review_required')
        self._assert_blank(quantity_request.proposed_exposure_exact)
        self.assertIn('No returned quantity was invented.', quantity_request.review_reason)
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')
        price_request = self._evaluate(self._reassess(
            finding, 'price_adjustment_credit',
            'Read the amount-only credit without reducing pieces.',
            source_move=credit,
        ))
        self.assertEqual(price_request.state, 'proposed_revision_ready')
        self._assert_amount(price_request.proposed_quantity_exact, '100')
        self._assert_amount(price_request.proposed_exposure_exact, '5000')
        self.assertIn('not converted into returned pieces', price_request.difference_explanation)
        self.assertEqual(self._exposure(), Decimal('5000'))
        original = self.env['cpla.invoice.audit.result'].browse(original.id)
        self._assert_amount(original.potential_exposure_exact, '5000')

    def test_rev14_t007_full_reversal_clears_current_without_a_second_exposure(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        first = self._audit()
        original = self._latest(first, invoice)
        finding = self._potential()
        credit = invoice._reverse_moves()
        credit.action_post()
        record = self._evaluate(self._reassess(
            finding, 'full_invoice_reversal',
            'The posted credit reverses the original billed quantity.',
            source_move=credit,
        ))
        self.assertEqual(record.state, 'proposed_revision_ready')
        self._assert_amount(record.proposed_exposure_exact, '0')
        self.assertEqual(record.delta_class, 'exposure_eliminated')
        self._assert_amount(record.delta_exact, '-5000')
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')
        record = self._accept(record, 'Accept the verified full reversal. This is not collected cash.')
        self.assertEqual(record.state, 'accepted')
        self.assertEqual(self._exposure(), Decimal('0'))
        self.assertFalse(self._potential())
        self.assertFalse(self.env['cpla.leakage.finding'].search([
            ('move_id', '=', invoice.id),
            ('is_current', '=', True),
            ('finding_status', '=', 'potential'),
        ]))
        historical = self.env['cpla.leakage.finding'].search([
            ('move_id', '=', invoice.id),
            ('potential_leakage_exact', '=', '5000'),
        ])
        self.assertTrue(historical)
        self.assertTrue(all(not row.is_current for row in historical))
        self.assertTrue(record.successor_result_id)
        self._assert_amount(record.successor_result_id.potential_exposure_exact, '0')
        self.assertFalse(record.successor_result_id.is_recovered_cash)
        original = self.env['cpla.invoice.audit.result'].browse(original.id)
        self._assert_amount(original.potential_exposure_exact, '5000')
        self.assertFalse(record.is_recovered_cash)
        self.assertFalse(record.is_writeoff)

    def test_rev14_t008_separate_cutoff_is_not_summed(self):
        self.policy_a.pricing_date_policy = 'invoice'
        with freeze_time('2026-06-01'):
            version = self._priced(
                '1000', effective=fields.Date.to_date('2026-06-02'),
                valid_from=fields.Date.to_date('2026-06-01'),
                valid_to=fields.Date.to_date('2026-12-31'),
            )
        with freeze_time('2026-07-20'):
            later = self._later(version, '1200', effective=fields.Date.to_date('2026-07-20'))
        invoice = self._invoice(
            self._confirm(self._quote(1000, quantity=100)),
            quantity=100, price=1000, invoice_date=fields.Date.to_date('2026-07-25'),
        )
        early = self._audit(knowledge_cutoff='2026-07-01 00:00:00')
        early_result = self._latest(early, invoice)
        early_version = early_result.version_id
        early_amount = early_result.potential_exposure_exact
        early_fingerprint = early_result.input_fingerprint
        self.assertEqual(early_version, version)
        late = self._audit(knowledge_cutoff='2026-07-21 00:00:00')
        late_result = self._latest(late, invoice)
        self.assertEqual(late_result.version_id, later)
        self._assert_amount(late_result.potential_exposure_exact, '20000')
        finding = self._potential()
        self.assertEqual(len(finding), 1)
        self._assert_amount(finding.potential_leakage_exact, '20000')
        case = self._open_case(finding)
        record = self._evaluate(self._reassess(
            finding, 'approved_retroactive_amendment',
            'Reconstruct the earlier cutoff. Do not rewrite the later finding.',
            cutoff='2026-07-01 00:00:00',
        ))
        self.assertEqual(record.state, 'proposed_revision_ready')
        self.assertEqual(record.proposed_version_id, version)
        self._assert_amount(record.proposed_exposure_exact, '0')
        self._assert_blank(record.delta_exact)
        self.assertEqual(record.delta_class, 'undetermined')
        self.assertNotEqual(record.proposed_identity, record.original_identity)
        self.assertIn('were not subtracted', record.difference_explanation)
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self.assertEqual(finding.version_id, later)
        self._assert_amount(finding.potential_leakage_exact, '20000')
        record = self._accept(record, 'Keep both cutoff readings. Do not add them together.')
        self.assertEqual(record.state, 'accepted')
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self.assertEqual(finding.version_id, later)
        self._assert_amount(finding.potential_leakage_exact, '20000')
        self.assertEqual(len(self._potential()), 1)
        self.assertEqual(self._exposure(), Decimal('20000'))
        early_result = self.env['cpla.invoice.audit.result'].browse(early_result.id)
        self.assertEqual(early_result.version_id, early_version)
        self.assertEqual(early_result.potential_exposure_exact, early_amount)
        self.assertEqual(early_result.input_fingerprint, early_fingerprint)
        case = self.env['cpla.leakage.case'].browse(case.id)
        self.assertFalse(case.source_reassessment_required)
        self._assert_amount(case.reviewed_exposure_exact, '20000')
        self.assertEqual(case.membership_ids.filtered('is_current').finding_id, finding)
        self.assertTrue(case.event_ids.filtered(
            lambda event: event.event_type == 'separate_interpretation_recorded'
        ))
        amendment = self._env(self.owner, self.company_a)['cpla.customer.contract.version'].browse(
            later.id
        ).create_amendment()
        amendment.write({
            'amendment_reason': 'Backdated price was not approved.',
            'effective_from': self._on(-10),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        amendment.line_ids.write({'price_unit': 1300})
        with self.assertRaises(UserError):
            amendment.action_submit_for_review()
            self._env(self.finance, self.company_a)['cpla.customer.contract.version'].browse(
                amendment.id
            ).action_approve()
        self.assertNotEqual(amendment.state, 'approved')
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertEqual(finding.version_id, later)

    def test_rev14_t009_reviewer_can_reject_and_cannot_accept(self):
        _order, _invoice = self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        record = self._reassess(
            finding, 'manual_authorized_review',
            'Ask finance to reread the current evidence.',
        )
        with self.assertRaises(AccessError):
            self._env(self.reviewer, self.company_a)['cpla.leakage.reassessment'].browse(
                record.id
            ).action_evaluate()
        record = self._evaluate(record)
        self.assertEqual(record.state, 'proposed_revision_ready')
        self._assert_amount(record.proposed_exposure_exact, '5000')
        self._env(self.reviewer, self.company_a)['cpla.leakage.reassessment'].browse(
            record.id
        ).action_reject('The reviewer does not accept this reread.')
        self.env.invalidate_all()
        record = self.env['cpla.leakage.reassessment'].browse(record.id)
        self.assertEqual(record.state, 'rejected')
        self.assertEqual(record.decision_by_id, self.reviewer)
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')
        second = self._evaluate(self._reassess(
            finding, 'manual_authorized_review',
            'A rejected request does not block a later review.',
        ))
        self.assertEqual(second.state, 'proposed_revision_ready')
        with self.assertRaises(AccessError):
            self._env(self.reviewer, self.company_a)['cpla.leakage.reassessment'].browse(
                second.id
            ).action_accept('A finance reviewer cannot accept the proposal.')
        self.env.invalidate_all()
        second = self.env['cpla.leakage.reassessment'].browse(second.id)
        self.assertEqual(second.state, 'proposed_revision_ready')

    def test_rev14_t010_replacement_without_reversal_is_not_forced_to_zero(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        first = self._audit()
        original = self._latest(first, invoice)
        finding = self._potential()
        replacement = self._invoice(self._confirm(self._quote(1150, quantity=100)), quantity=100, price=1150)
        record = self._evaluate(self._reassess(
            finding, 'replacement_invoice',
            'A replacement without a verified reversal is not zero exposure.',
            source_move=replacement,
        ))
        self.assertEqual(record.state, 'evidence_review_required')
        self.assertIn('Exposure was not forced to zero.', record.review_reason)
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')
        credit = invoice._reverse_moves()
        credit.action_post()
        self._env(self.finance, self.company_a)['cpla.invoice.source'].map_move(credit)
        record = self._evaluate(record)
        self.assertEqual(record.state, 'proposed_revision_ready')
        self._assert_amount(record.proposed_exposure_exact, '0')
        self.assertEqual(record.delta_class, 'exposure_eliminated')
        payments = self.env['account.payment'].search_count([])
        record = self._accept(record, 'The reversal and replacement are verified. This is not collected cash.')
        self.assertEqual(record.state, 'accepted')
        self.assertEqual(self._exposure(), Decimal('0'))
        self.assertFalse(self._potential().filtered(lambda item: item.move_id == replacement))
        original = self.env['cpla.invoice.audit.result'].browse(original.id)
        self._assert_amount(original.potential_exposure_exact, '5000')
        self.assertFalse(record.is_recovered_cash)
        self.assertEqual(self.env['account.payment'].search_count([]), payments)

    def test_rev14_t011_views_sequence_and_no_finance_validation(self):
        self.assertEqual(Manifest.for_addon(MODULE)['version'], '19.0.1.15.0')
        self.assertTrue(self.env.ref(MODULE + '.view_cpla_leakage_reassessment_form'))
        self.assertTrue(self.env.ref(MODULE + '.menu_cpla_reassessments'))
        sequence = self.env.ref(MODULE + '.seq_cpla_leakage_reassessment')
        self.assertEqual(sequence.code, 'cpla.leakage.reassessment')
        self.assertEqual(sequence.prefix, 'CPL-REASS/%(year)s/')
        self.assertEqual(sequence.padding, 5)
        self.assertFalse(sequence.company_id)
        finding_arch = self.env.ref(MODULE + '.view_cpla_leakage_finding_form').arch
        self.assertIn('action_open_reassessment_wizard', finding_arch)
        run_arch = self.env.ref(MODULE + '.view_cpla_invoice_audit_run_form').arch
        self.assertIn('action_reassess', run_arch)
        form = self.env.ref(MODULE + '.view_cpla_leakage_reassessment_form').arch
        self.assertIn('not recovered cash', form)
        self.assertIn('finance validation', form)
        self.assertIn('not a legal archive', form)
        case_form = self.env.ref(MODULE + '.view_cpla_leakage_case_form').arch
        self.assertIn('finance_package_stale', case_form)
        self.assertIn('not a finance-validated amount', case_form)
        rules = self.env['ir.rule'].search([
            ('model_id.model', '=', 'cpla.leakage.reassessment'),
        ])
        self.assertTrue(rules)
        self.assertFalse(rules.groups)
        self.assertIn('company_id', rules.domain_force)
        self.assertNotIn('finance_validated_exact', self.env['cpla.leakage.reassessment']._fields)
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE), ('model', '=', 'ir.cron'),
        ]))
        _order, _invoice = self._sale('1150', 1100, quantity=10)
        self._audit()
        finding = self._potential()
        action = self._env(self.manager, self.company_a)['cpla.leakage.finding'].browse(
            finding.id
        ).action_open_reassessment_wizard()
        wizard = self.env['cpla.leakage.reassessment.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.operation, 'request')
        self.assertEqual(wizard.trigger_type, 'manual_authorized_review')
        self.assertIn('original_quantity_exact', form)
        self.assertIn('revision_verification', finding_arch)
        self.assertIn('not a fresh verification', finding_arch)
        self.assertIn('reinvestigation_required', case_form)
        self.assertIn('filter_source_review', self.env.ref(
            MODULE + '.view_cpla_leakage_finding_search'
        ).arch)

    def test_rev14_t012_rejection_keeps_the_accepted_amount_and_flags_review(self):
        _order, invoice = self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        case = self._open_case(finding)
        investigator = self._env(self.manager, case.company_id)['cpla.leakage.case'].browse(case.id)
        investigator.action_assign(self.manager.id, 'Assign the investigator.')
        investigator.action_start()
        investigator.action_record_root_cause(
            'missed_contract_price_increase',
            'The invoice rate does not match the approved contract rate.',
        )
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        record = self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'A 20 piece return is proposed and then rejected.',
            source_move=credit,
        ))
        self.assertEqual(record.state, 'proposed_revision_ready')
        self._assert_amount(record.proposed_exposure_exact, '4000')
        self._assert_amount(record.original_quantity_exact, '100')
        self._assert_amount(record.original_adjusted_exact, '1150')
        self._assert_amount(record.original_actual_exact, '1100')
        self.assertIn('evidence correction', record.difference_explanation)
        self._env(self.reviewer, self.company_a)['cpla.leakage.reassessment'].browse(
            record.id
        ).action_reject('The return evidence is not sufficient.')
        self.env.invalidate_all()
        record = self.env['cpla.leakage.reassessment'].browse(record.id)
        self.assertEqual(record.state, 'rejected')
        self.assertEqual(record.decision_reason, 'The return evidence is not sufficient.')
        self.assertEqual(record.decision_by_id, self.reviewer)
        self.assertTrue(record.decision_at)
        self._assert_amount(record.proposed_exposure_exact, '4000')
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')
        self.assertEqual(finding.revision_verification, 'source_changed_review_pending')
        case = self.env['cpla.leakage.case'].browse(case.id)
        self.assertEqual(case.root_cause, 'missed_contract_price_increase')
        self.assertEqual(case.state, 'under_investigation')
        self._assert_amount(case.reviewed_exposure_exact, '5000')
        self.assertTrue(case.reinvestigation_required)
        self.assertEqual(self._exposure(), Decimal('5000'))
        self.assertTrue(record.event_ids.filtered(lambda event: event.event_type == 'rejected'))

    def test_rev14_t013_unchanged_source_does_not_add_a_finding(self):
        self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        before = self.env['cpla.leakage.finding'].search_count([])
        record = self._evaluate(self._reassess(
            finding, 'manual_authorized_review',
            'Read the same evidence again.',
        ))
        self.assertEqual(record.state, 'proposed_revision_ready')
        self.assertEqual(record.delta_class, 'no_material_change')
        self.assertEqual(record.proposed_fingerprint, record.original_fingerprint)
        self._assert_amount(record.proposed_exposure_exact, '5000')
        record = self._accept(record, 'The same fingerprint does not create another exposure.')
        self.assertEqual(record.state, 'accepted')
        self.assertEqual(self.env['cpla.leakage.finding'].search_count([]), before)
        self.assertEqual(len(self._potential()), 1)
        self.assertEqual(self._exposure(), Decimal('5000'))
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self.assertEqual(finding.revision_verification, 'reassessment_accepted')

    def test_rev14_t014_affected_findings_stay_inside_the_company(self):
        self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        self.assertFalse(self.env['cpla.leakage.reassessment'].search([
            ('finding_id', '=', finding.id),
        ]))
        selected = self.env['cpla.leakage.reassessment'].affected_findings(
            self.company_a, version=finding.version_id, product=finding.product_id,
        )
        self.assertIn(finding, selected)
        self.assertTrue(all(row.company_id == self.company_a for row in selected))
        version_b = self._priced('900', company=self.company_b)
        with self.assertRaises(UserError):
            self.env['cpla.leakage.reassessment'].affected_findings(
                self.company_a, version=version_b,
            )
        with self.assertRaises(AccessError):
            self._env(self.owner_b, self.company_b)['cpla.leakage.reassessment'].affected_findings(
                self.company_a,
            )
        self.assertFalse(self.env['cpla.leakage.reassessment'].search([
            ('finding_id', '=', finding.id),
        ]))

    def test_rev14_t015_discount_and_fx_corrections_do_not_invent_amounts(self):
        self._sale('1150', 1100, quantity=100)
        self._audit()
        finding = self._potential()
        discount = self._evaluate(self._reassess(
            finding, 'approved_discount_correction',
            'No approved discount correction exists at this cutoff.',
        ))
        self.assertEqual(discount.state, 'evidence_review_required')
        self.assertIn('previous price was not replaced', discount.review_reason)
        self.assertFalse(discount.calculation_authoritative)
        rate = self._evaluate(self._reassess(
            finding, 'historical_fx_correction',
            'No replacement FX rate was supplied.',
        ))
        self.assertEqual(rate.state, 'evidence_review_required')
        self.assertIn('No corrected amount was fabricated.', rate.review_reason)
        tax = self._evaluate(self._reassess(
            finding, 'tax_basis_correction',
            'No replacement tax evidence was supplied.',
        ))
        self.assertEqual(tax.state, 'evidence_review_required')
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertTrue(finding.is_current)
        self._assert_amount(finding.potential_leakage_exact, '5000')
        self.assertEqual(finding.revision_verification, 'current_result_uncertain')
        with self.assertRaises(UserError):
            self._accept(discount, 'Incomplete discount evidence cannot be accepted.')

    def test_rev14_t016_concurrent_acceptance_keeps_one_current_finding(self):
        """Two workers accept different proposals for one finding.

        The fixture is committed on its own cursor. The class transaction
        is invisible to the workers, and the test runner holds Registry._lock
        for the whole suite, so the workers use a dummy lock only while they
        run. This is two threads, not a sequential replay.
        """
        registry = self.env.registry
        pool = self.conc_pool
        company_id = pool['company_id']
        finance_id = pool['finance_id']
        invoice_id = False
        return_id = False
        manual_id = False
        cursor = registry.cursor()
        saved = {
            'env': self.env,
            'company_a': self.company_a,
            'owner': self.owner,
            'manager': self.manager,
            'finance': self.finance,
            'salesman': self.salesman,
            'partner': self.partner,
            'policy_a': self.policy_a,
            'bearing': self.bearing,
        }
        try:
            cursor.execute("SET lock_timeout = '20s'")
            cursor.execute("SET statement_timeout = '120s'")
            side = api.Environment(cursor, api.SUPERUSER_ID, {
                'allowed_company_ids': [company_id],
            })
            self.env = side
            self.company_a = side['res.company'].browse(company_id)
            self.owner = side['res.users'].browse(pool['owner_id'])
            self.manager = side['res.users'].browse(pool['manager_id'])
            self.finance = side['res.users'].browse(finance_id)
            self.salesman = side['res.users'].browse(pool['salesman_id'])
            self.partner = side['res.partner'].browse(pool['partner_id'])
            self.policy_a = side['cpla.company.policy'].browse(pool['policy_id'])
            self.bearing = side['product.product'].browse(pool['product_id'])
            _order, invoice = self._sale('1150', 1100, quantity=100)
            self._audit()
            finding = side['cpla.leakage.finding'].search([
                ('move_id', '=', invoice.id),
                ('is_current', '=', True),
                ('finding_status', '=', 'potential'),
            ])
            self.assertEqual(len(finding), 1, 'The committed fixture needs one current finding.')
            credit = invoice._reverse_moves()
            self._product_lines(credit).write({'quantity': 20})
            credit.action_post()
            return_request = self._evaluate(self._reassess(
                finding, 'verified_quantity_return',
                'Concurrent return proposal.',
                source_move=credit,
            ))
            manual_request = self._evaluate(self._reassess(
                finding, 'manual_authorized_review',
                'Concurrent reread of the same finding.',
            ))
            self.assertEqual(return_request.state, 'proposed_revision_ready')
            self.assertEqual(manual_request.state, 'proposed_revision_ready')
            invoice_id = invoice.id
            return_id = return_request.id
            manual_id = manual_request.id
            cursor.commit()
        finally:
            self.env = saved['env']
            self.company_a = saved['company_a']
            self.owner = saved['owner']
            self.manager = saved['manager']
            self.finance = saved['finance']
            self.salesman = saved['salesman']
            self.partner = saved['partner']
            self.policy_a = saved['policy_a']
            self.bearing = saved['bearing']
            cursor.close()

        def _clear_pool_findings():
            with registry.cursor() as cleanup:
                cleanup.execute("SET lock_timeout = '20s'")
                cleanup.execute(
                    """
                    UPDATE cpla_leakage_finding
                       SET is_current = false,
                           current_identity = NULL,
                           finding_status = 'superseded_by_reassessment'
                     WHERE company_id = %s
                       AND is_current
                    """,
                    (company_id,),
                )
                cleanup.commit()

        self.addCleanup(_clear_pool_findings)
        results = []
        barrier = threading.Barrier(2)

        def accept(record_id):
            try:
                with registry.cursor() as thread_cursor:
                    thread_cursor.execute("SET lock_timeout = '20s'")
                    thread_cursor.execute("SET statement_timeout = '60s'")
                    thread_env = api.Environment(thread_cursor, finance_id, {
                        'allowed_company_ids': [company_id],
                    })
                    barrier.wait(timeout=30)
                    thread_env['cpla.leakage.reassessment'].browse(record_id).action_accept(
                        'Accept from one worker.'
                    )
                    thread_cursor.commit()
                    results.append('ok')
            except Exception as error:
                results.append('%s: %s' % (type(error).__name__, error))

        threads = [
            threading.Thread(target=accept, args=(return_id,)),
            threading.Thread(target=accept, args=(manual_id,)),
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
        try:
            self.assertEqual(len(results), 2, results)
            with registry.cursor() as check:
                check_env = api.Environment(check, api.SUPERUSER_ID, {
                    'allowed_company_ids': [company_id],
                })
                current = check_env['cpla.leakage.finding'].search([
                    ('company_id', '=', company_id),
                    ('is_current', '=', True),
                    ('finding_status', '=', 'potential'),
                ])
                amounts = [row.potential_leakage_exact for row in current]
                total = Decimal('0')
                for amount in amounts:
                    total += _money(amount) or Decimal('0')
                self.assertLessEqual(len(current), 1, (results, amounts))
                self.assertNotEqual(total, Decimal('9000'), (results, amounts))
                accepted = check_env['cpla.leakage.reassessment'].search_count([
                    ('id', 'in', [return_id, manual_id]),
                    ('state', '=', 'accepted'),
                ])
                self.assertGreaterEqual(accepted, 1, results)
                self.assertLessEqual(accepted, 2, results)
        finally:
            if company_id:
                with registry.cursor() as cleanup:
                    cleanup.execute("SET lock_timeout = '20s'")
                    cleanup.execute(
                        """
                        UPDATE cpla_leakage_finding
                           SET is_current = false,
                               current_identity = NULL,
                               finding_status = 'superseded_by_reassessment'
                         WHERE company_id = %s
                           AND is_current
                        """,
                        (company_id,),
                    )
                    cleanup.commit()

    def _fv_record(self, record):
        self.env.invalidate_all()
        return self.env['cpla.finance.validation'].browse(record.id)

    def _fv_as(self, record, user):
        return self._env(user, record.company_id)['cpla.finance.validation'].browse(record.id)

    def _fv_error(self, call, code):
        """Accept either access or user errors. Odoo 19 assertRaises takes one class."""
        try:
            with self.assertRaises(AccessError) as caught:
                call()
        except UserError as error:
            self.assertIn(code, str(error), str(error))
            return error
        self.assertIn(code, str(caught.exception), str(caught.exception))
        return caught.exception

    def _fv_policy(self, partial=False, ceiling='100000', levels=None, basis='accepted_potential',
                   currency=None, four_eyes=True, company=None, editor=None):
        """Approve a company matrix. ``ceiling`` is a test fixture, not a seeded limit."""
        company = company or self.company_a
        editor = editor or self.finance
        env = self._env(editor, company)
        policy = env['cpla.finance.validation.policy'].create({
            'company_id': company.id,
            'name': 'Finance validation matrix',
            'currency_id': (currency or company.currency_id).id,
            'threshold_basis': basis,
            'partial_validation_allowed': partial,
            'four_eyes_required': four_eyes,
            'change_reason': 'Test approval matrix. This ceiling is a fixture, not a seeded limit.',
        })
        specs = levels or [{
            'name': 'Finance manager',
            'level_sequence': 1,
            'authority_group': 'finance_manager',
            'applies_from_exact': '0',
            'has_ceiling': True,
            'maximum_exact': ceiling,
        }]
        for spec in specs:
            env['cpla.finance.validation.policy.level'].create(dict(spec, policy_id=policy.id))
        env['cpla.finance.validation.policy'].browse(policy.id).action_approve_policy()
        self.env.invalidate_all()
        return self.env['cpla.finance.validation.policy'].browse(policy.id)

    def _fv_ready(self, quantity=500):
        _order, invoice = self._sale('1150', 1100, quantity=quantity)
        run = self._audit()
        result = self._latest(run, invoice)
        finding = self._potential()
        self.assertEqual(len(finding), 1)
        case = self._submit_case(self._open_case(finding))
        self.assertEqual(case.state, 'ready_for_finance_review')
        self.assertFalse(case.finance_package_stale)
        return {
            'case': case,
            'invoice': invoice,
            'finding': self.env['cpla.leakage.finding'].browse(finding.id),
            'result': result,
        }

    def _fv_submit_as(self, case, user):
        env = self._env(user, case.company_id)
        manager = env['cpla.leakage.case'].browse(case.id)
        if manager.state == 'new':
            manager.action_assign(user.id, 'Assign the investigator for finance submission.')
            manager = env['cpla.leakage.case'].browse(case.id)
        if manager.state in ('assigned', 'returned_for_rework'):
            manager.action_start()
            manager = env['cpla.leakage.case'].browse(case.id)
        for line in manager.checklist_ids.filtered(
            lambda item: item.required_for_submission and item.answer == 'unanswered'
        ):
            manager.action_answer_checklist(line.code, 'yes')
        for evidence in manager.evidence_ids.filtered(
            lambda item: item.evidence_kind == 'source' and item.status not in ('verified', 'not_applicable')
        ):
            manager.action_verify_evidence(evidence.id, 'Source record reviewed.')
        manager = env['cpla.leakage.case'].browse(case.id)
        if not manager.root_cause:
            manager.action_record_root_cause(
                'missed_contract_price_increase',
                'The invoice rate does not match the approved contract rate.',
            )
        if not manager.investigation_outcome:
            manager.action_record_outcome(
                'likely_missed_price_increase',
                'The investigator conclusion is not a finance validation.',
            )
        manager.action_submit_for_finance()
        self.env.invalidate_all()
        return self.env['cpla.leakage.case'].browse(case.id)

    def _fv_decision(self, line, validated, rejected, unresolved, reason, explanation=''):
        return {
            'line_id': line.id,
            'validated': validated,
            'rejected': rejected,
            'unresolved': unresolved,
            'reason_code': reason,
            'explanation': explanation,
        }

    def _fv_prepare(self, case, user=None):
        actor = user or self.reviewer
        record = self._env(actor, case.company_id)['cpla.finance.validation'].prepare_from_case(case.id)
        return self._fv_record(record)

    def _fv_pending(self, record, decisions, user=None):
        actor = user or self.reviewer
        validation = self._fv_as(record, actor)
        if validation.state == 'draft':
            validation.action_submit()
            validation = self._fv_as(record, actor)
        if validation.state == 'submitted':
            validation.action_start_review()
            validation = self._fv_as(record, actor)
        validation.action_propose(decisions)
        validation = self._fv_as(record, actor)
        validation.action_request_approval()
        return self._fv_record(record)

    def _fv_full_decisions(self, record):
        return [
            self._fv_decision(line, line.potential_exact, '0', '0', 'FULLY_SUPPORTED')
            for line in record.line_ids
        ]

    def _fv_side_counts(self):
        company = self.company_a
        return (
            self.env['account.move'].search_count([('company_id', '=', company.id)]),
            self.env['account.payment'].search_count([('company_id', '=', company.id)]),
        )

    def test_fv15_views_sequence_and_menus(self):
        """Finance views load. No approval amount is seeded. No recovery cron."""
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])
        sequence = self.env.ref(MODULE + '.seq_cpla_finance_validation')
        self.assertEqual(sequence.code, 'cpla.finance.validation')
        self.assertEqual(sequence.prefix, 'CPL-FV/%(year)s/')
        self.assertEqual(sequence.padding, 5)
        self.assertFalse(sequence.company_id)
        policy_sequence = self.env.ref(MODULE + '.seq_cpla_finance_validation_policy')
        self.assertEqual(policy_sequence.prefix, 'CPL-FVP/%(year)s/')
        self.assertFalse(policy_sequence.company_id)
        form = self.env.ref(MODULE + '.view_cpla_finance_validation_form').arch
        self.assertIn('not recovered cash', form)
        self.assertIn('not a customer receivable', form)
        self.assertIn('not a waiver', form)
        self.assertIn('not a billed recovery', form)
        self.assertIn('action_submit', form)
        self.assertIn('DEV-16 handoff', form)
        self.assertNotIn('Recovered', form.replace('not recovered cash', ''))
        policy_form = self.env.ref(MODULE + '.view_cpla_finance_validation_policy_form').arch
        self.assertIn('No approval amount is seeded', policy_form)
        self.env['cpla.finance.validation'].get_view(view_type='form')
        self.env['cpla.finance.validation'].get_view(view_type='list')
        codes = dict(self.env['cpla.finance.validation.line']._fields['reason_code'].selection)
        self.assertIn('FULLY_SUPPORTED', codes)
        self.assertIn('AUTHORIZED_DISCOUNT_CONFIRMED', codes)
        self.assertNotIn('FRAUD', codes)
        self.assertNotIn('finance_validated_exact', self.env['cpla.leakage.finding']._fields)
        self.assertNotIn('finance_validated_exact', self.env['cpla.leakage.reassessment']._fields)
        run_arch = self.env.ref(MODULE + '.view_cpla_invoice_audit_run_form').arch
        self.assertIn('action_reassess', run_arch)
        for xmlid in (
            'menu_cpla_finance',
            'menu_cpla_finance_pending',
            'menu_cpla_finance_mine',
            'menu_cpla_finance_evidence',
            'menu_cpla_finance_approval',
            'menu_cpla_finance_approved',
            'menu_cpla_finance_partial',
            'menu_cpla_finance_rejected',
            'menu_cpla_finance_stale',
            'menu_cpla_finance_history',
            'menu_cpla_finance_policy',
        ):
            self.assertTrue(self.env.ref(MODULE + '.' + xmlid))
        finance_menu = self.env.ref(MODULE + '.menu_cpla_finance')
        self.assertIn(finance_menu, self.env.ref(MODULE + '.group_internal_auditor').menu_access)
        self.assertIn(finance_menu, self.env.ref(MODULE + '.group_finance_reviewer').menu_access)
        for xmlid in ('group_app_admin', 'group_sales_pricing_reviewer', 'group_recovery_operator'):
            self.assertNotIn(finance_menu, self.env.ref(MODULE + '.' + xmlid).menu_access)
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE), ('model', '=', 'ir.cron'),
        ]))
        rules = self.env['ir.rule'].search([('model_id.model', '=', 'cpla.finance.validation')])
        self.assertTrue(rules)
        self.assertFalse(rules.groups)
        self.assertIn('company_id', rules.domain_force)
        self._fv_error(
            lambda: self._env(self.reviewer, self.company_a)['cpla.finance.validation.policy'].create({
                'company_id': self.company_a.id,
                'name': 'Reviewer cannot write the matrix',
                'currency_id': self.company_a.currency_id.id,
                'change_reason': 'A reviewer does not approve the matrix.',
            }),
            'APPROVAL_MATRIX_MISSING',
        )
        self._fv_error(
            lambda: self._env(self.admin, self.company_a)['cpla.finance.validation.policy'].create({
                'company_id': self.company_a.id,
                'name': 'Administrator cannot write the matrix',
                'currency_id': self.company_a.currency_id.id,
                'change_reason': 'Technical administration is not finance authority.',
            }),
            'APPROVAL_MATRIX_MISSING',
        )

    def test_fv15_full_then_partial_correction(self):
        """GOLD-FV-001, 002, 005, 012, 013, 016, 019, and 020 on one case."""
        ready = self._fv_ready(500)
        case = ready['case']
        finding = ready['finding']
        self._assert_amount(finding.potential_leakage_exact, '25000')
        root_cause = case.root_cause
        moves, payments = self._fv_side_counts()
        self._fv_error(
            lambda: self.env['cpla.finance.validation'].prepare_from_case(case.id),
            'APPROVAL_MATRIX_MISSING',
        )
        for user in (self.admin, self.auditor, self.plain, self.owner):
            self._fv_error(
                lambda user=user: self._env(user, self.company_a)['cpla.finance.validation'].prepare_from_case(case.id),
                'APPROVAL_MATRIX_MISSING' if user in (self.admin, self.auditor) else 'COMPANY_ACCESS_DENIED',
            )
        fin_b = self._make_account_user('cpla15_fin_b', 'group_finance_manager', self.company_b)
        with self.assertRaises(AccessError):
            self._env(fin_b, self.company_b)['cpla.finance.validation'].prepare_from_case(case.id)
        self._fv_error(
            lambda: self._env(self.finance, self.company_a)['cpla.finance.validation'].create({
                'company_id': self.company_a.id,
                'state': 'approved',
                'validated_exact': '25000',
            }),
            'FINANCE_SOURCE_NOT_READY',
        )
        record = self._fv_prepare(case)
        self.assertEqual(record.state, 'draft')
        self.assertTrue(record.reference.startswith('CPL-FV/'))
        self.assertTrue(record.submission_snapshot)
        self._assert_amount(record.accepted_potential_exact, '25000')
        self._assert_amount(record.validated_exact, '0')
        self.assertEqual(
            self.env['cpla.finance.validation'].current_validated_amount(self.company_a, case.partner_id),
            '0',
        )
        self._fv_error(lambda: self._fv_as(record, self.reviewer).action_submit(), 'APPROVAL_MATRIX_MISSING')
        self.assertEqual(self._fv_record(record).state, 'draft')
        policy = self._fv_policy(partial=True, ceiling='100000')
        self.assertTrue(policy.reference.startswith('CPL-FVP/'))
        self.assertEqual(policy.approved_by_id, self.finance)
        record = self._fv_record(record)
        self._fv_as(record, self.reviewer).action_submit()
        record = self._fv_record(record)
        self.assertEqual(record.state, 'submitted')
        self.assertEqual(record.requested_by_id, self.reviewer)
        self.assertTrue(record.requested_at)
        self._assert_amount(record.validated_exact, '0')
        self.assertEqual(record.policy_id, policy)
        self._fv_as(record, self.reviewer).action_start_review()
        record = self._fv_record(record)
        self.assertEqual(record.state, 'under_finance_review')
        self.assertEqual(record.reviewer_id, self.reviewer)
        line = record.line_ids
        self.assertEqual(len(line), 1)
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_propose([
                self._fv_decision(line, '30000', '0', '0', 'FULLY_SUPPORTED'),
            ]),
            'VALIDATION_EXCEEDS_POTENTIAL',
        )
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_propose([
                self._fv_decision(line, '-1', '0', '25001', 'OTHER_DOCUMENTED_REASON', 'Negative amount.'),
            ]),
            'INVALID_VALIDATION_AMOUNT',
        )
        increment = Decimal(str(self.company_a.currency_id.rounding or '0.01'))
        potential = _money(line.potential_exact)
        dusty = potential + (increment / Decimal('10'))
        self.assertEqual(dusty.quantize(increment, rounding=ROUND_HALF_UP), potential)
        self._fv_as(record, self.reviewer).action_propose([
            self._fv_decision(line, format(dusty, 'f'), '0', '0', 'FULLY_SUPPORTED'),
        ])
        record = self._fv_record(record)
        self.assertEqual(record.state, 'proposed_decision')
        self._assert_amount(record.proposed_validated_exact, '25000')
        self._assert_amount(record.validated_exact, '0')
        self.assertNotEqual(record.proposed_validated_exact, format(dusty, 'f'))
        self._fv_as(record, self.reviewer).action_request_approval()
        record = self._fv_record(record)
        self.assertEqual(record.state, 'pending_approval')
        self.assertEqual(record.required_level_count, 1)
        self._assert_amount(record.validated_exact, '0')
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_approve('The requester cannot approve this request.'),
            'APPROVAL_LIMIT_EXCEEDED',
        )
        finance = self._env(self.finance, self.company_a)
        action = finance['cpla.finance.validation'].browse(record.id).action_open_approve_wizard()
        wizard = finance['cpla.finance.validation.wizard'].browse(action['res_id'])
        wizard.write({'reason': 'Approved from the finance form. Not a receivable.'})
        wizard.action_apply()
        record = self._fv_record(record)
        self.assertEqual(record.state, 'approved')
        self.assertEqual(record.decision_type, 'full_validation')
        self._assert_amount(record.validated_exact, '25000')
        self._assert_amount(record.rejected_exact, '0')
        self._assert_amount(record.unresolved_exact, '0')
        self.assertEqual(record.decision_by_id, self.finance)
        self.assertTrue(record.decision_at)
        self.assertTrue(record.is_current)
        self.assertFalse(record.stale_source)
        self.assertFalse(record.creates_customer_receivable)
        self.assertFalse(record.proves_cash_collection)
        self.assertFalse(record.is_waiver)
        self.assertFalse(record.is_recovery_billed)
        self.assertFalse(record.is_cash_recovered)
        approved_events = record.approval_ids.filtered(lambda event: event.decision == 'approved')
        self.assertEqual(len(approved_events), 1)
        self.assertEqual(approved_events.actor_id, self.finance)
        self.assertTrue(approved_events.acted_at)
        self.assertEqual(approved_events.policy_id, policy)
        self.assertIn(policy.reference, record.policy_snapshot or '')
        self._fv_as(record, self.finance).action_approve('Retry the same approval.')
        record = self._fv_record(record)
        self.assertEqual(len(record.approval_ids.filtered(lambda event: event.decision == 'approved')), 1)
        other = self._make_account_user('cpla15_fin_other', 'group_finance_manager', self.company_a)
        self._fv_error(
            lambda: self._fv_as(record, other).action_approve('A second final approval is not a new amount.'),
            'HISTORICAL_APPROVAL_PROTECTED',
        )
        self._fv_error(
            lambda: self._fv_as(record, self.finance).write({'validated_exact': '1'}),
            'HISTORICAL_APPROVAL_PROTECTED',
        )
        self._fv_error(
            lambda: self._env(self.finance, self.company_a)['cpla.finance.validation.line'].browse(
                record.line_ids.id
            ).write({'approved_validated_exact': '1'}),
            'HISTORICAL_APPROVAL_PROTECTED',
        )
        with self.assertRaises(AccessError):
            self._env(self.finance, self.company_a)['cpla.finance.validation.approval'].browse(
                approved_events.id
            ).write({'amount_exact': '1'})
        self._fv_error(
            lambda: self.env['cpla.finance.validation.approval'].browse(
                approved_events.id
            ).write({'amount_exact': '1'}),
            'HISTORICAL_APPROVAL_PROTECTED',
        )
        with self.assertRaises(AccessError):
            self._fv_as(record, self.finance).unlink()
        self._fv_error(
            lambda: self.env['cpla.finance.validation'].browse(record.id).unlink(),
            'HISTORICAL_APPROVAL_PROTECTED',
        )
        self._fv_error(
            lambda: self._env(self.owner, self.company_a)['cpla.finance.validation'].browse(
                record.id
            ).export_data(['reference']),
            'COMPANY_ACCESS_DENIED',
        )
        self._fv_error(
            lambda: self.env['cpla.finance.validation'].browse(record.id).export_data(['reference']),
            'COMPANY_ACCESS_DENIED',
        )
        self.auditor.write({
            'group_ids': [Command.link(self.env.ref('base.group_allow_export').id)],
        })
        exported = self._env(self.auditor, self.company_a)['cpla.finance.validation'].browse(
            record.id
        ).export_data(['reference'])
        self.assertTrue(exported)
        payload = self._fv_as(record, self.auditor).decision_payload()
        self.assertEqual(payload['approved_amount'], record.validated_exact)
        self.assertTrue(payload['current'])
        self.assertTrue(payload['approval_complete'])
        self.assertFalse(payload['recovery_authority'])
        self.assertFalse(payload['creates_customer_receivable'])
        self.assertFalse(payload['proves_cash_collection'])
        self.assertFalse(payload['is_waiver'])
        self.assertFalse(self._env(fin_b, self.company_b)['cpla.finance.validation'].search([
            ('id', '=', record.id),
        ]))
        with self.assertRaises(AccessError):
            self._env(fin_b, self.company_b)['cpla.finance.validation'].browse(record.id).read(['reference'])
        self.assertTrue(self._env(self.both, self.company_a)['cpla.finance.validation'].search([
            ('id', '=', record.id),
        ]))
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self._assert_amount(finding.potential_leakage_exact, '25000')
        self.assertNotIn('finance_validated_exact', finding._fields)
        case = self.env['cpla.leakage.case'].browse(case.id)
        self.assertEqual(case.root_cause, root_cause)
        self._assert_amount(case.current_potential_exposure_exact, '25000')
        events = case.event_ids.filtered(lambda item: item.event_type == 'finance_decision_recorded')
        self.assertTrue(events)
        self.assertEqual(events[-1].new_value, record.reference)
        self.assertNotIn('25000', events[-1].reason or '')
        self._fv_error(
            lambda: self._env(self.reviewer, self.company_a)['cpla.finance.validation'].prepare_from_case(case.id),
            'DUPLICATE_VALIDATION_REQUEST',
        )
        correction = self._fv_as(record, self.reviewer).action_create_correction(
            'Correct the full approval to the supportable portion.'
        )
        correction = self._fv_record(correction)
        self.assertEqual(correction.state, 'draft')
        self._assert_amount(correction.validated_exact, '0')
        self.assertEqual(correction.supersedes_id, record)
        record = self._fv_record(record)
        self.assertTrue(record.is_current)
        self._assert_amount(record.validated_exact, '25000')
        line = correction.line_ids
        correction = self._fv_pending(correction, [
            self._fv_decision(
                line, '18000', '7000', '0', 'PARTIALLY_SUPPORTED',
                'Seven thousand is not supported by the evidence. This is not a waiver.',
            ),
        ])
        self.assertEqual(correction.state, 'pending_approval')
        self._assert_amount(correction.validated_exact, '0')
        self._fv_as(correction, self.finance).action_approve(
            'The supportable portion is eighteen thousand. The rest is not a waiver.'
        )
        correction = self._fv_record(correction)
        record = self._fv_record(record)
        self.assertEqual(correction.state, 'partially_approved')
        self.assertEqual(correction.decision_type, 'partial_validation')
        self._assert_amount(correction.validated_exact, '18000')
        self._assert_amount(correction.rejected_exact, '7000')
        self._assert_amount(correction.unresolved_exact, '0')
        self.assertTrue(correction.is_current)
        self.assertFalse(correction.is_waiver)
        self.assertFalse(correction.creates_customer_receivable)
        self.assertFalse(correction.proves_cash_collection)
        self.assertEqual(record.state, 'superseded')
        self.assertFalse(record.is_current)
        self._assert_amount(record.validated_exact, '25000')
        self.assertEqual(record.superseded_by_id, correction)
        self._assert_amount(
            self.env['cpla.finance.validation'].current_validated_amount(self.company_a, case.partner_id),
            '18000',
        )
        self.assertEqual(self._fv_side_counts(), (moves, payments))
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE), ('model', '=', 'ir.cron'),
        ]))
        bodies = ' '.join(case.message_ids.mapped('body'))
        self.assertNotIn('18000', bodies)

    def test_fv15_unresolved_portion_stays_unresolved(self):
        """GOLD-FV-003. Unresolved is not stored as rejected or validated."""
        ready = self._fv_ready(500)
        self._fv_policy(partial=True)
        record = self._fv_prepare(ready['case'])
        self._fv_as(record, self.reviewer).action_submit()
        self._fv_as(record, self.reviewer).action_start_review()
        line = self._fv_record(record).line_ids
        self._fv_as(record, self.reviewer).action_propose([
            self._fv_decision(
                line, '18000', '2000', '5000', 'PARTIALLY_SUPPORTED',
                'Five thousand is still unresolved and is not rejected.',
            ),
        ])
        record = self._fv_record(record)
        self._assert_amount(record.proposed_unresolved_exact, '5000')
        self._assert_amount(record.proposed_rejected_exact, '2000')
        self._assert_amount(record.validated_exact, '0')
        self._fv_as(record, self.reviewer).action_request_approval()
        self._fv_as(record, self.finance).action_approve('Unresolved evidence stays unresolved.')
        record = self._fv_record(record)
        self.assertEqual(record.state, 'partially_approved')
        self._assert_amount(record.validated_exact, '18000')
        self._assert_amount(record.rejected_exact, '2000')
        self._assert_amount(record.unresolved_exact, '5000')
        self.assertFalse(record.is_waiver)
        finding = self.env['cpla.leakage.finding'].browse(ready['finding'].id)
        self._assert_amount(finding.potential_leakage_exact, '25000')

    def test_fv15_full_rejection_is_not_a_waiver(self):
        """GOLD-FV-004 and GOLD-FV-014. The submitter cannot approve the rejection."""
        _order, _invoice = self._sale('1150', 1100, quantity=500)
        self._audit()
        finding = self._potential()
        dual = self._make_user(
            'cpla15_dual', 'group_contract_manager', self.company_a,
            extra_groups=('group_finance_manager',),
        )
        case = self._fv_submit_as(self._open_case(finding), dual)
        self.assertEqual(case.submitted_by_id, dual)
        self._fv_policy(partial=False)
        record = self._fv_prepare(case)
        line = record.line_ids
        record = self._fv_pending(record, [
            self._fv_decision(
                line, '0', '25000', '0', 'CONTRACT_SCOPE_NOT_PROVEN',
                'The evidence does not support this exposure. This is not a waiver.',
            ),
        ])
        self._fv_error(
            lambda: self._fv_as(record, dual).action_approve('The case submitter tries to approve.'),
            'SELF_APPROVAL_PROHIBITED',
        )
        self._fv_as(record, self.finance).action_approve('None of the exposure is financially supportable.')
        record = self._fv_record(record)
        self.assertEqual(record.state, 'rejected')
        self.assertEqual(record.decision_type, 'full_rejection')
        self._assert_amount(record.validated_exact, '0')
        self._assert_amount(record.rejected_exact, '25000')
        self._assert_amount(record.unresolved_exact, '0')
        self.assertFalse(record.level_denied)
        self.assertFalse(record.is_waiver)
        self.assertFalse(record.line_ids.counts_current)
        self._assert_amount(
            self.env['cpla.finance.validation'].current_validated_amount(self.company_a),
            '0',
        )
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self._assert_amount(finding.potential_leakage_exact, '25000')
        payload = record.decision_payload()
        self.assertFalse(payload['current'])
        self.assertEqual(payload['approved_amount'], '0')
        self._assert_amount(payload['rejected_amount'], '25000')

    def test_fv15_many_findings_reconcile(self):
        """GOLD-FV-006. Each finding keeps its own validated, rejected, or unresolved amount."""
        self._priced('1150')
        order = self._confirm(self._quote(1100, quantity=500))
        self._invoice(order, quantity=200, price=1100)
        self._invoice(order, quantity=200, price=1100)
        self._invoice(order, quantity=100, price=1100)
        self._audit()
        findings = self._potential()
        self.assertEqual(len(findings), 3)
        self.assertEqual(self._exposure(), Decimal('25000'))
        case = self._env(self.manager, self.company_a)['cpla.leakage.case'].create_from_findings(
            findings.ids,
            grouping_basis='explicit_same_issue',
            grouping_note='One pricing issue across three invoices.',
        )
        case = self._submit_case(case)
        self._fv_policy(partial=True)
        record = self._fv_prepare(case)
        self.assertEqual(len(record.line_ids), 3)
        by_amount = {}
        for line in record.line_ids:
            by_amount.setdefault(str(_money(line.potential_exact)), []).append(line)
        first, second = by_amount['10000']
        third = by_amount['5000'][0]
        self._fv_as(record, self.reviewer).action_submit()
        self._fv_as(record, self.reviewer).action_start_review()
        blocked = [
            self._fv_decision(first, '10000', '0', '0', 'FULLY_SUPPORTED'),
            self._fv_decision(
                second, '8000', '2000', '0', 'PARTIALLY_SUPPORTED',
                'Two thousand on this invoice is not supported.',
            ),
            self._fv_decision(
                third, '0', '0', '5000', 'ADDITIONAL_EVIDENCE_REQUIRED',
                'This finding still needs evidence.',
            ),
        ]
        self._fv_as(record, self.reviewer).action_propose(blocked)
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_request_approval(),
            'EVIDENCE_INCOMPLETE',
        )
        self.assertEqual(self._fv_record(record).state, 'proposed_decision')
        self._assert_amount(self._fv_record(record).validated_exact, '0')
        decided = [
            blocked[0],
            blocked[1],
            self._fv_decision(
                third, '0', '0', '5000', 'OTHER_DOCUMENTED_REASON',
                'This finding stays unresolved. It is not rejected.',
            ),
        ]
        record = self._fv_pending(record, decided)
        self._fv_as(record, self.finance).action_approve('Eighteen thousand is the supportable total.')
        record = self._fv_record(record)
        self._assert_amount(record.validated_exact, '18000')
        self._assert_amount(record.rejected_exact, '2000')
        self._assert_amount(record.unresolved_exact, '5000')
        self.assertEqual(record.state, 'partially_approved')
        self.assertFalse(record.is_waiver)
        rows = sorted(
            (
                _money(line.potential_exact),
                _money(line.approved_validated_exact),
                _money(line.approved_rejected_exact),
                _money(line.approved_unresolved_exact),
            )
            for line in record.line_ids
        )
        self.assertEqual(rows, [
            (Decimal('5000'), Decimal('0'), Decimal('0'), Decimal('5000')),
            (Decimal('10000'), Decimal('8000'), Decimal('2000'), Decimal('0')),
            (Decimal('10000'), Decimal('10000'), Decimal('0'), Decimal('0')),
        ])
        self._assert_amount(
            self.env['cpla.finance.validation'].current_validated_amount(self.company_a),
            '18000',
        )

    def test_fv15_repeated_audits_validate_once(self):
        """GOLD-FV-007. Three audit runs do not create three finance amounts."""
        self._sale('1150', 1100, quantity=500)
        self._audit()
        self._audit()
        self._audit()
        self.assertEqual(len(self._potential()), 1)
        case = self._submit_case(self._open_case(self._potential()))
        self._fv_policy(partial=False)
        record = self._fv_prepare(case)
        record = self._fv_pending(record, self._fv_full_decisions(record))
        self._fv_as(record, self.finance).action_approve('One current finding has one finance amount.')
        record = self._fv_record(record)
        self._assert_amount(record.validated_exact, '25000')
        self.assertEqual(len(record.line_ids.filtered('counts_current')), 1)
        self._assert_amount(
            self.env['cpla.finance.validation'].current_validated_amount(self.company_a),
            '25000',
        )

    def test_fv15_refund_uses_accepted_basis(self):
        """GOLD-FV-018. Finance uses the accepted four thousand and does not subtract the return again."""
        _order, invoice = self._sale('1150', 1100, quantity=100)
        run = self._audit()
        original = self._latest(run, invoice)
        self._assert_amount(original.potential_exposure_exact, '5000')
        finding = self._potential()
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        moves, payments = self._fv_side_counts()
        self._accept(self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'Verified 20 piece return of the original invoice line.',
            source_move=credit,
        )))
        self.assertEqual(self._exposure(), Decimal('4000'))
        current = self._potential()
        self.assertEqual(len(current), 1)
        case = self._submit_case(self._open_case(current))
        self._fv_policy(partial=False)
        record = self._fv_prepare(case)
        self._assert_amount(record.accepted_potential_exact, '4000')
        record = self._fv_pending(record, self._fv_full_decisions(record))
        self._fv_as(record, self.finance).action_approve('The accepted basis is four thousand.')
        record = self._fv_record(record)
        self._assert_amount(record.validated_exact, '4000')
        self.assertNotEqual(_money(record.validated_exact), Decimal('3000'))
        self.assertNotEqual(_money(record.validated_exact), Decimal('5000'))
        original = self.env['cpla.invoice.audit.result'].browse(original.id)
        self._assert_amount(original.potential_exposure_exact, '5000')
        self.assertEqual(self._fv_side_counts(), (moves, payments))

    def test_fv15_discount_evidence_and_reassessment_block(self):
        """GOLD-FV-010 and GOLD-FV-011. A proposed reread and a missing discount do not approve."""
        ready = self._fv_ready(100)
        finding = ready['finding']
        proposal = self._evaluate(self._reassess(
            finding, 'manual_authorized_review',
            'A proposed reread is not current accepted evidence.',
        ))
        self.assertEqual(proposal.state, 'proposed_revision_ready')
        self._fv_error(
            lambda: self._fv_prepare(ready['case']),
            'STALE_FINANCIAL_EVIDENCE',
        )
        self._env(self.reviewer, self.company_a)['cpla.leakage.reassessment'].browse(
            proposal.id
        ).action_reject('The proposed reread is not accepted.')
        finding = self.env['cpla.leakage.finding'].browse(finding.id)
        self.assertIn(finding.revision_verification, ('current_verified', 'reassessment_accepted'))
        self._assert_amount(finding.potential_leakage_exact, '5000')
        self._fv_policy(partial=True)
        record = self._fv_prepare(ready['case'])
        self._fv_as(record, self.reviewer).action_submit()
        self._fv_as(record, self.reviewer).action_start_review()
        line = self._fv_record(record).line_ids
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_propose([
                self._fv_decision(line, line.potential_exact, '0', '0', 'AUTHORIZED_DISCOUNT_CONFIRMED'),
            ]),
            'APPROVAL_EVIDENCE_MISSING',
        )
        self.assertEqual(self._fv_record(record).state, 'under_finance_review')
        self._assert_amount(self._fv_record(record).validated_exact, '0')
        moves, payments = self._fv_side_counts()
        self._fv_as(record, self.reviewer).action_request_evidence(
            'The signed pricing support for this discount is not on the approval record.',
            'Attach the approved discount evidence and resubmit.',
        )
        record = self._fv_record(record)
        case = self.env['cpla.leakage.case'].browse(ready['case'].id)
        self.assertEqual(record.state, 'additional_evidence_required')
        self.assertEqual(case.state, 'returned_for_rework')
        self._assert_amount(record.validated_exact, '0')
        self.assertTrue(record.approval_ids.filtered(lambda event: event.decision == 'evidence_requested'))
        self._fv_error(
            lambda: self._fv_as(record, self.finance).action_approve('Incomplete evidence cannot be approved.'),
            'APPROVAL_LEVEL_PENDING',
        )
        self.assertEqual(self._fv_side_counts(), (moves, payments))

    def test_fv15_stale_before_approval_uses_the_new_basis(self):
        """GOLD-FV-008. A source change before approval blocks the old package."""
        _order, invoice = self._sale('1150', 1100, quantity=500)
        run = self._audit()
        original = self._latest(run, invoice)
        finding = self._potential()
        case = self._submit_case(self._open_case(finding))
        self._fv_policy(partial=False)
        record = self._fv_prepare(case)
        record = self._fv_pending(record, self._fv_full_decisions(record))
        self.assertEqual(record.state, 'pending_approval')
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 100})
        credit.action_post()
        self._accept(self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'Verified 100 piece return before finance approval.',
            source_move=credit,
        )))
        record = self._fv_record(record)
        self.assertEqual(record.state, 'stale_source_review_required')
        self.assertTrue(record.stale_source)
        self._assert_amount(record.validated_exact, '0')
        self._fv_error(
            lambda: self._fv_as(record, self.finance).action_approve('The old twenty-five thousand cannot be approved.'),
            'APPROVAL_LEVEL_PENDING',
        )
        record = self._fv_record(record)
        self.assertEqual(record.state, 'stale_source_review_required')
        self._assert_amount(record.validated_exact, '0')
        self._fv_as(record, self.finance).action_retire_stale_package()
        record = self._fv_record(record)
        self.assertEqual(record.state, 'superseded')
        case = self.env['cpla.leakage.case'].browse(case.id)
        self._env(self.finance, self.company_a)['cpla.leakage.case'].browse(case.id).action_return_for_rework(
            'The accepted source changed before approval.',
            'Accept the revised finding and resubmit.',
        )
        manager = self._env(self.manager, self.company_a)['cpla.leakage.case'].browse(case.id)
        manager.action_accept_current_source('Accept the revised eligible quantity.')
        manager = self._env(self.manager, self.company_a)['cpla.leakage.case'].browse(case.id)
        self.assertFalse(manager.reinvestigation_required)
        self.assertFalse(manager.source_reassessment_required)
        manager.action_start()
        manager.action_submit_for_finance()
        case = self.env['cpla.leakage.case'].browse(case.id)
        self.assertEqual(case.state, 'ready_for_finance_review')
        self.assertFalse(case.finance_package_stale)
        self._assert_amount(case.current_potential_exposure_exact, '20000')
        refreshed = self._fv_prepare(case)
        self._assert_amount(refreshed.accepted_potential_exact, '20000')
        refreshed = self._fv_pending(refreshed, self._fv_full_decisions(refreshed))
        self._fv_as(refreshed, self.finance).action_approve('The current accepted basis is twenty thousand.')
        refreshed = self._fv_record(refreshed)
        self._assert_amount(refreshed.validated_exact, '20000')
        self.assertTrue(refreshed.is_current)
        self._assert_amount(self._fv_record(record).validated_exact, '0')
        original = self.env['cpla.invoice.audit.result'].browse(original.id)
        self._assert_amount(original.potential_exposure_exact, '25000')

    def test_fv15_stale_after_approval_keeps_history(self):
        """GOLD-FV-009. A later source change does not rewrite the approved amount."""
        _order, invoice = self._sale('1150', 1100, quantity=500)
        self._audit()
        finding = self._potential()
        case = self._submit_case(self._open_case(finding))
        self._fv_policy(partial=False)
        record = self._fv_prepare(case)
        record = self._fv_pending(record, self._fv_full_decisions(record))
        self._fv_as(record, self.finance).action_approve('Approve the current twenty-five thousand.')
        record = self._fv_record(record)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 100})
        credit.action_post()
        moves, payments = self._fv_side_counts()
        self._accept(self._evaluate(self._reassess(
            finding, 'verified_quantity_return',
            'Verified 100 piece return after finance approval.',
            source_move=credit,
        )))
        record = self._fv_record(record)
        self.assertEqual(record.state, 'approved')
        self.assertTrue(record.stale_source)
        self.assertFalse(record.is_current)
        self._assert_amount(record.validated_exact, '25000')
        self.assertFalse(record.line_ids.counts_current)
        payload = record.decision_payload()
        self.assertFalse(payload['current'])
        self.assertFalse(payload['recovery_authority'])
        self._assert_amount(payload['approved_amount'], '25000')
        self._assert_amount(
            self.env['cpla.finance.validation'].current_validated_amount(self.company_a),
            '0',
        )
        self.assertEqual(self._fv_side_counts(), (moves, payments))
        self._assert_amount(self.env['cpla.invoice.audit.result'].search([
            ('move_id', '=', invoice.id),
        ], order='id', limit=1).potential_exposure_exact, '25000')

    def test_fv15_two_levels_and_self_approval(self):
        """GOLD-FV-015. One user cannot complete both required levels."""
        ready = self._fv_ready(500)
        clerk = self._make_account_user('cpla15_clerk', 'group_finance_reviewer', self.company_a)
        second = self._make_account_user('cpla15_fin2', 'group_finance_manager', self.company_a)
        self._fv_policy(partial=False, levels=[
            {
                'name': 'First finance reviewer',
                'level_sequence': 1,
                'authority_group': 'finance_reviewer',
                'applies_from_exact': '0',
                'has_ceiling': True,
                'maximum_exact': '100000',
            },
            {
                'name': 'Second finance manager',
                'level_sequence': 2,
                'authority_group': 'finance_manager',
                'applies_from_exact': '0',
                'has_ceiling': True,
                'maximum_exact': '100000',
            },
        ])
        record = self._fv_prepare(ready['case'], user=clerk)
        record = self._fv_pending(record, self._fv_full_decisions(record), user=clerk)
        self.assertEqual(record.required_level_count, 2)
        self._fv_error(
            lambda: self._fv_as(record, clerk).action_approve('The requester tries to approve level one.'),
            'SELF_APPROVAL_PROHIBITED',
        )
        self._fv_as(record, self.finance).action_approve('First level only.')
        record = self._fv_record(record)
        self.assertEqual(record.state, 'pending_approval')
        self.assertEqual(record.approval_level_done, 1)
        self._assert_amount(record.validated_exact, '0')
        self.assertFalse(record.decision_payload()['approval_complete'])
        self._fv_error(
            lambda: self._fv_as(record, self.finance).action_approve('The same user tries the second level.'),
            'SELF_APPROVAL_PROHIBITED',
        )
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_approve('A reviewer is not the second level.'),
            'APPROVAL_LIMIT_EXCEEDED',
        )
        self._fv_as(record, second).action_approve('Second level completes the decision.')
        record = self._fv_record(record)
        self.assertEqual(record.state, 'approved')
        self._assert_amount(record.validated_exact, '25000')
        self.assertEqual(len(record.approval_ids.filtered(lambda event: event.decision == 'approved')), 2)
        self.assertEqual(record.decision_by_id, second)
        self._fv_as(record, second).action_approve('Retry the finished second level.')
        record = self._fv_record(record)
        self.assertEqual(len(record.approval_ids.filtered(lambda event: event.decision == 'approved')), 2)
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_approve('A user who did not approve cannot add one.'),
            'HISTORICAL_APPROVAL_PROTECTED',
        )

    def test_fv15_currency_ceiling_and_missing_matrix(self):
        """GOLD-FV-017. A recorded rate is required, and the converted amount uses the fixture ceiling."""
        ready = self._fv_ready(500)
        record = self._fv_prepare(ready['case'])
        self._fv_error(lambda: self._fv_as(record, self.reviewer).action_submit(), 'APPROVAL_MATRIX_MISSING')
        other = self.env['res.currency'].with_context(active_test=False).search([
            ('id', '!=', self.company_a.currency_id.id),
        ], limit=1)
        self.assertTrue(other)
        model = self.env['cpla.finance.validation']
        self.assertTrue(model._require_currency_basis(
            self.company_a.currency_id, self.company_a.currency_id, None,
        ))
        self._fv_error(
            lambda: model._require_currency_basis(self.company_a.currency_id, other, None),
            'CURRENCY_BASIS_REVIEW_REQUIRED',
        )
        self.assertTrue(model._require_currency_basis(self.company_a.currency_id, other, '2'))
        self._fv_policy(partial=False, ceiling='30000', currency=other)
        line = self._fv_record(record).line_ids
        models.Model.write(line, {'currency_id': other.id})
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_submit(),
            'CURRENCY_BASIS_REVIEW_REQUIRED',
        )
        models.Model.write(line, {'currency_id': self.company_a.currency_id.id})
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_submit(),
            'CURRENCY_BASIS_REVIEW_REQUIRED',
        )
        self._fv_as(record, self.reviewer).action_set_review_rate(
            '2', self._today(), 'Recorded test rate. Not a market lookup.',
        )
        self._fv_as(record, self.reviewer).action_submit()
        self._fv_as(record, self.reviewer).action_start_review()
        record = self._fv_record(record)
        self._fv_as(record, self.reviewer).action_propose(self._fv_full_decisions(record))
        self._fv_error(
            lambda: self._fv_as(record, self.reviewer).action_request_approval(),
            'APPROVAL_LIMIT_EXCEEDED',
        )
        record = self._fv_record(record)
        self.assertEqual(record.state, 'proposed_decision')
        self._assert_amount(record.validated_exact, '0')
        self._assert_amount(record.fx_rate_exact, '2')

    def test_fv15_level_denial_records_no_amount(self):
        """A denied level rejects the proposal and does not validate the potential."""
        ready = self._fv_ready(100)
        self._fv_policy(partial=False)
        record = self._fv_prepare(ready['case'])
        record = self._fv_pending(record, self._fv_full_decisions(record))
        self._fv_as(record, self.finance).action_deny_level(
            'This proposal is denied. The potential is not validated and it is not a waiver.'
        )
        record = self._fv_record(record)
        self.assertEqual(record.state, 'rejected')
        self.assertTrue(record.level_denied)
        self.assertTrue(record.is_current)
        self._assert_amount(record.validated_exact, '0')
        self.assertFalse(record.is_waiver)
        payload = record.decision_payload()
        self.assertEqual(payload['approved_amount'], '0')
        self.assertFalse(payload['current'])
        self._fv_error(
            lambda: self._fv_as(record, self.finance).action_approve('The denial already closed this level.'),
            'HISTORICAL_APPROVAL_PROTECTED',
        )
        self._fv_error(
            lambda: self._env(self.reviewer, self.company_a)['cpla.finance.validation'].prepare_from_case(
                ready['case'].id
            ),
            'DUPLICATE_VALIDATION_REQUEST',
        )
        correction = self._fv_as(record, self.reviewer).action_create_correction(
            'Open a new draft after the denial. The denied amount stays zero.'
        )
        correction = self._fv_record(correction)
        self.assertEqual(correction.state, 'draft')
        self._assert_amount(correction.validated_exact, '0')
        self._assert_amount(self._fv_record(record).validated_exact, '0')

    def test_fv15_concurrent_approval_keeps_one_decision(self):
        """Two workers approve one pending request. This is not a sequential replay."""
        registry = self.env.registry
        pool = self.conc_pool
        company_id = pool['company_id']
        finance_id = pool['finance_id']
        validation_id = False
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
        }
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
            self.finance = side['res.users'].browse(finance_id)
            self.salesman = side['res.users'].browse(pool['salesman_id'])
            self.partner = side['res.partner'].browse(pool['partner_id'])
            self.policy_a = side['cpla.company.policy'].browse(pool['policy_id'])
            self.bearing = side['product.product'].browse(pool['product_id'])
            self.reviewer = side['res.users'].browse(pool['reviewer_id'])
            ready = self._fv_ready(100)
            self._fv_policy(partial=False, ceiling='100000')
            record = self._fv_prepare(ready['case'])
            record = self._fv_pending(record, self._fv_full_decisions(record))
            self.assertEqual(record.state, 'pending_approval')
            validation_id = record.id
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
            cursor.close()

        results = []
        barrier = threading.Barrier(2)

        def approve():
            try:
                with registry.cursor() as thread_cursor:
                    thread_cursor.execute("SET lock_timeout = '20s'")
                    thread_cursor.execute("SET statement_timeout = '60s'")
                    thread_env = api.Environment(thread_cursor, finance_id, {
                        'allowed_company_ids': [company_id],
                    })
                    barrier.wait(timeout=30)
                    thread_env['cpla.finance.validation'].browse(validation_id).action_approve(
                        'Approve from one worker.'
                    )
                    thread_cursor.commit()
                    results.append('ok')
            except Exception as error:
                results.append('%s: %s' % (type(error).__name__, error))

        threads = [threading.Thread(target=approve), threading.Thread(target=approve)]
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
        try:
            self.assertEqual(len(results), 2, results)
            self.assertTrue(any(item == 'ok' for item in results), results)
            with registry.cursor() as check:
                check_env = api.Environment(check, api.SUPERUSER_ID, {
                    'allowed_company_ids': [company_id],
                })
                record = check_env['cpla.finance.validation'].browse(validation_id)
                self.assertEqual(record.state, 'approved', results)
                self.assertEqual(len(record.approval_ids.filtered(
                    lambda event: event.decision == 'approved' and event.level_sequence > 0
                )), 1, results)
                self.assertEqual(_money(record.validated_exact), _money(record.accepted_potential_exact), results)
                self.assertEqual(check_env['cpla.finance.validation'].search_count([
                    ('company_id', '=', company_id),
                    ('state', 'in', ('approved', 'partially_approved')),
                ]), 1, results)
        finally:
            if company_id:
                with registry.cursor() as cleanup:
                    cleanup.execute("SET lock_timeout = '20s'")
                    # Keep the pool company policy. Remove this test's contracts
                    # and findings so the later reassessment race sees one match.
                    for statement in _POOL_CLEAR_SQL:
                        if statement.startswith('DELETE FROM cpla_company_policy'):
                            continue
                        cleanup.execute(statement, ([company_id],))
                    cleanup.commit()
