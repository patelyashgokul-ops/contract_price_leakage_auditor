import logging
import time
from decimal import Decimal

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'
_logger = logging.getLogger(__name__)


def _dec(value):
    return Decimal(str(value))


@tagged('post_install', '-at_install')
class TestDev10QuotationCompliance(TransactionCase):
    """Quotation compliance. Preventive exposure is not recovered cash.

    The approved price comes from the existing resolver. This suite does not
    post invoices or create recovery documents.
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
        cls.owner = cls._make_sale_user(
            'cpla10_owner', cls.company_a, extra_groups=('group_contract_user',),
        )
        cls.owner_b = cls._make_user('cpla10_owner_b', 'group_contract_user', cls.company_b)
        cls.manager = cls._make_user('cpla10_manager', 'group_contract_manager', cls.company_a)
        cls.finance = cls._make_user('cpla10_finance', 'group_finance_manager', cls.company_a)
        cls.finance2 = cls._make_user('cpla10_finance2', 'group_finance_manager', cls.company_a)
        cls.auditor = cls._make_user('cpla10_auditor', 'group_internal_auditor', cls.company_a)
        cls.admin = cls._make_user('cpla10_admin', 'group_app_admin', cls.company_a)
        cls.reviewer = cls._make_user('cpla10_reviewer', 'group_sales_pricing_reviewer', cls.company_a)
        cls.combined = cls._make_sale_user(
            'cpla10_combined', cls.company_a,
            extra_groups=('group_contract_manager', 'group_finance_manager'),
        )
        cls.seller = cls._make_sale_user(
            'cpla10_seller', cls.company_a, extra_groups=('group_contract_user',),
        )
        cls.salesman = cls._make_sale_user('cpla10_salesman', cls.company_a)
        cls.plain = new_test_user(
            cls.env,
            login='cpla10_plain',
            groups='base.group_user',
            password='cpla-test',
            company_id=cls.company_a.id,
            company_ids=[Command.set([cls.company_a.id])],
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
            'name': 'Q0A',
            'symbol': 'Q',
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

    @classmethod
    def _make_sale_user(cls, login, company, extra_groups=()):
        names = ['base.group_user', 'sales_team.group_sale_salesman']
        names.extend('%s.%s' % (MODULE, extra) for extra in extra_groups)
        return new_test_user(
            cls.env,
            login=login,
            groups=','.join(names),
            password='cpla-test',
            company_id=company.id,
            company_ids=[Command.set([company.id])],
        )

    def _env(self, user, company):
        return self.env(user=user, context={
            **self.env.context,
            'allowed_company_ids': [company.id],
        })

    def _today(self):
        return fields.Date.context_today(self.env['cpla.quotation.compliance'])

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

    def _mode(self, mode, company=None):
        company = company or self.company_a
        policy = self.policy_a if company == self.company_a else self.policy_b
        policy.write({'quotation_compliance_mode': mode})
        return policy

    def _v1(self, products, currency, company=None, partner=None, owner=None):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
        owner = owner or (self.owner if company == self.company_a else self.owner_b)
        env = self._env(owner, company)
        contract = env['cpla.customer.contract'].create({
            'name': 'Negotiated supply',
            'company_id': company.id,
            'partner_id': partner.id,
            'owner_id': owner.id,
            'currency_id': currency.id,
            'valid_from': self._on(-30),
            'valid_to': self._on(180),
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
            'source_reference': 'AGR-010',
            'description': 'Signed pricing schedule.',
            'datas': 'c2lnbmVk',
        })
        contract.action_submit_for_review()
        manager = self.manager if company == self.company_a else self.env['res.users']
        if company != self.company_a:
            manager = self._make_user('cpla10_mgr_b_%s' % contract.id, 'group_contract_manager', company)
        return self._env(manager, company)['cpla.customer.contract.version'].approve_initial(
            self._env(manager, company)['cpla.customer.contract'].browse(contract.id)
        )

    def _priced(self, price='1200', concessions=(), policy=None, currency=None, company=None,
                products=None, tiers=None, partner=None, quantity_basis='sales_order', owner=None):
        company = company or self.company_a
        currency = currency or company.currency_id
        products = products or [(self.bearing, price)]
        first = self._v1(products, currency, company=company, partner=partner, owner=owner)
        owner = owner or (self.owner if company == self.company_a else self.owner_b)
        finance = self.finance if company == self.company_a else None
        env = self._env(owner, company)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        values = {
            'amendment_reason': 'Authorized price clause. Not a retroactive restatement.',
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
                'quantity_basis': quantity_basis,
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
        if finance is None:
            finance = self._make_user('cpla10_fin_b_%s' % amendment.id, 'group_finance_manager', company)
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
            'customer_scope': 'version_customer',
            'product_scope': 'version_line',
            'version_line_id': line.id,
            'exclusive': spec.get('exclusive', False),
            'precedence_rank': spec.get('rank', 0),
            'evidence_reference': 'AGR-DISC-010',
        }
        if kind == 'percentage':
            values['percent_exact'] = spec['percent']
        elif kind in ('fixed_per_unit', 'fixed_special_price'):
            values['amount_exact'] = spec['amount']
            values['currency_id'] = version.currency_id.id
            values['uom_id'] = line.uom_id.id
        owner = self.owner if version.company_id == self.company_a else self.owner_b
        return self._env(owner, version.company_id)['cpla.discount.concession'].create(values)

    def _limit(self):
        return {
            'authority_limit_basis': 'per_unit_reduction',
            'authority_max_unit_reduction_exact': '50',
        }

    def _pricelist(self, company, currency=None):
        currency = currency or company.currency_id
        pricelist = self.env['product.pricelist'].search([
            ('company_id', 'in', [False, company.id]),
            ('currency_id', '=', currency.id),
        ], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].create({
                'name': 'CPLA %s' % currency.name,
                'currency_id': currency.id,
                'company_id': company.id,
            })
        return pricelist

    def _quote(self, price, quantity=500, partner=None, product=None, discount=0.0,
               company=None, currency=None, user=None):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
        product = product or self.bearing
        currency = currency or company.currency_id
        order = self.env['sale.order'].with_company(company).create({
            'partner_id': partner.id,
            'company_id': company.id,
            'pricelist_id': self._pricelist(company, currency).id,
            'currency_id': currency.id,
            'user_id': (user or self.env.user).id,
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
        })
        return order

    def _freeze(self, line, price, discount=None, quantity=None):
        values = {
            'price_unit': price,
            'technical_price_unit': 0,
        }
        if discount is not None:
            values['discount'] = discount
        if quantity is not None:
            values['product_uom_qty'] = quantity
        line.write(values)
        return line

    def _summary(self, order, user=None):
        company = order.company_id
        env = self._env(user or self.env.user, company)
        return env['cpla.quotation.compliance'].evaluate_order(env['sale.order'].browse(order.id))

    def _first(self, order, user=None):
        summary = self._summary(order, user=user)
        products = [line for line in summary['lines'] if line['kind'] == 'product']
        self.assertTrue(products)
        return products[0], summary

    def _special(self, price='1200', special='1150'):
        return self._priced(
            price,
            concessions=[{'type': 'fixed_special_price', 'amount': special}],
            policy=self._limit(),
        )

    def _override(self, line, price=None, quantity=None, user=None, effective_from=None, effective_to=None):
        user = user or self.owner
        if line.order_id.user_id != user:
            line.order_id.write({'user_id': user.id})
        env = self._env(user, line.order_id.company_id)
        wizard = env['cpla.quotation.override.request'].create({
            'sale_line_id': line.id,
            'reason': 'Customer accepted this quotation price.',
            'evidence_reference': 'MAIL-010',
        })
        action = wizard.action_create_request()
        approval = env['cpla.discount.approval'].browse(action['res_id'])
        updates = {}
        if price is not None:
            updates['proposed_price_exact'] = price
        if quantity is not None:
            updates['quantity_exact'] = quantity
        if effective_from:
            updates['effective_from'] = effective_from
        if effective_to:
            updates['effective_to'] = effective_to
        if updates:
            approval.write(updates)
        approval.action_submit()
        return approval

    def _locks(self, order):
        return self.env['cpla.sale.price.lock'].search([('sale_order_id', '=', order.id)])

    def test_price10_t001_compliant_price(self):
        self._priced('1150')
        order = self._quote(1150)
        line, summary = self._first(order)
        self.assertEqual(line['status'], 'COMPLIANT')
        self.assertEqual(line['actual_unit_price_exact'], '1150')
        self.assertEqual(line['approved_adjusted_unit_price_exact'], '1150')
        self.assertFalse(line['preventive_exposure_exact'])
        self.assertFalse(line['leakage_amount'])
        self.assertFalse(line['is_recovered_cash'])
        self.assertFalse(summary['leakage_amount'])
        self.assertEqual(order.order_line.price_unit, 1150)

    def test_price10_t002_below_approved_price(self):
        self._priced('1150')
        line, _summary = self._first(self._quote(1100))
        self.assertEqual(line['status'], 'BELOW_APPROVED_PRICE')
        self.assertNotEqual(line['status'], 'COMPLIANT')

    def test_price10_t003_additional_exposure_is_not_the_gross_gap(self):
        self._special()
        line, summary = self._first(self._quote(1100))
        self.assertEqual(_dec(line['approved_adjusted_unit_price_exact']), _dec(1150))
        self.assertEqual(_dec(line['preventive_exposure_exact']), _dec(25000))
        self.assertEqual(_dec(line['authorized_concession_extended_exact']), _dec(25000))
        self.assertEqual(_dec(line['gross_difference_extended_exact']), _dec(50000))
        self.assertNotEqual(_dec(line['preventive_exposure_exact']), _dec(50000))
        self.assertFalse(summary['is_recovered_cash'])
        self.assertEqual(summary['preventive_exposure_exact'], '25000')

    def test_price10_t004_approved_special_price_is_not_unauthorized(self):
        self._special()
        line, _summary = self._first(self._quote(1150))
        self.assertEqual(line['status'], 'COMPLIANT')
        self.assertFalse(line['preventive_exposure_exact'])
        self.assertEqual(_dec(line['authorized_concession_extended_exact']), _dec(25000))

    def test_price10_t005_native_discount_is_the_effective_price(self):
        self._priced('1140')
        order = self._quote(1200, discount=5)
        line, _summary = self._first(order)
        self.assertEqual(line['actual_unit_price_exact'], '1140')
        self.assertEqual(line['status'], 'COMPLIANT')
        self.assertEqual(order.order_line.discount, 5)
        self.assertEqual(order.order_line.price_unit, 1200)

    def test_price10_t006_discount_already_in_price_unit_is_not_subtracted_again(self):
        self._priced('1140')
        line, _summary = self._first(self._quote(1140, discount=0))
        self.assertEqual(line['actual_unit_price_exact'], '1140')
        self.assertNotEqual(line['actual_unit_price_exact'], '1083')
        self.assertEqual(line['status'], 'COMPLIANT')

    def test_price10_t007_order_quantity_selects_the_tier(self):
        self._priced('1200', tiers=[(500, None, 1100)])
        matched, _summary = self._first(self._quote(1100, quantity=500))
        self.assertEqual(matched['status'], 'COMPLIANT')
        self.assertEqual(matched['approved_adjusted_unit_price_exact'], '1100')
        dropped = self._quote(1100, quantity=400)
        missed, _summary = self._first(dropped)
        self.assertNotEqual(missed['status'], 'COMPLIANT')
        self.assertFalse(missed['preventive_exposure_exact'])

    def test_price10_t008_and_t009_uom_and_fx_are_not_raw_box_values(self):
        box = self.env['uom.uom'].create({
            'name': 'CPLA10 Box',
            'relative_uom_id': self.unit.id,
            'relative_factor': 10,
        })
        self.bearing.product_tmpl_id.write({'uom_ids': [Command.link(box.id)]})
        first = self._v1([(self.bearing, 1)], self.foreign)
        amendment = self._env(self.owner, self.company_a)[
            'cpla.customer.contract.version'
        ].browse(first.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Foreign box price converted before comparison.',
            'effective_from': self._today(),
            'comparison_currency_policy': 'company_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
            'fx_policy': 'fixed_rate',
            'fx_source_currency_id': self.foreign.id,
            'fx_target_currency_id': self.company_a.currency_id.id,
            'fx_multiplier_exact': '84',
        })
        contract_line = amendment.line_ids[:1]
        contract_line.write({
            'tier_method': 'full_volume',
            'quantity_basis': 'sales_order',
            'return_policy': 'unconfigured',
        })
        self._env(self.owner, self.company_a)['cpla.customer.contract.version.tier'].create({
            'version_line_id': contract_line.id,
            'min_quantity': 1,
            'has_maximum': False,
            'max_quantity': 0.0,
            'quantity_uom_id': self.unit.id,
            'price_unit': 50,
            'pricing_uom_id': box.id,
        })
        amendment.action_submit_for_review()
        self._env(self.finance, self.company_a)[
            'cpla.customer.contract.version'
        ].browse(amendment.id).action_approve()
        probe = self._quote(1, quantity=1)
        discovered, _summary = self._first(probe)
        self.assertTrue(discovered['approved_adjusted_unit_price_exact'])
        self.assertNotEqual(discovered['approved_adjusted_unit_price_exact'], '50')
        self.assertNotEqual(discovered['comparison_currency_id'], self.foreign.id)
        priced = self._quote(_dec(discovered['approved_adjusted_unit_price_exact']), quantity=1)
        matched, _summary = self._first(priced)
        self.assertEqual(
            matched['approved_adjusted_unit_price_exact'],
            discovered['approved_adjusted_unit_price_exact'],
        )
        self.assertEqual(matched['status'], 'COMPLIANT')

    def test_price10_t010_tax_included_price_is_not_compared(self):
        self._priced('1150')
        group = self.env['account.tax.group'].create({
            'name': 'CPLA10 taxes',
            'company_id': self.company_a.id,
        })
        country = self.company_a.country_id or self.env.company.country_id or self.env.ref('base.in')
        included = self.env['account.tax'].create({
            'name': 'CPLA included',
            'amount': 18.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
            'company_id': self.company_a.id,
            'country_id': country.id,
            'tax_group_id': group.id,
        })
        order = self._quote(1150)
        order.order_line.write({'tax_ids': [Command.set(included.ids)]})
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'REVIEW_REQUIRED')
        self.assertEqual(line['reason'], 'quotation_tax_not_compared')
        self.assertFalse(line['preventive_exposure_exact'])
        self.assertFalse(line['approved_adjusted_unit_price_exact'])

    def test_price10_t011_no_unapproved_tolerance_suppresses_a_difference(self):
        self._priced('1150')
        self.assertEqual(self.policy_a.tolerance_policy, 'unconfigured')
        exact, _summary = self._first(self._quote(1150))
        self.assertEqual(exact['status'], 'COMPLIANT')
        below, _summary = self._first(self._quote(1149.99))
        self.assertEqual(below['status'], 'BELOW_APPROVED_PRICE')
        self.assertTrue(below['preventive_exposure_exact'])
        self.assertFalse(below['leakage_amount'])

    def test_price10_t012_overpricing_is_not_positive_leakage(self):
        self._priced('1150')
        self._mode('block')
        order = self._quote(1200)
        line, summary = self._first(order)
        self.assertEqual(line['status'], 'PRICE_ABOVE_APPROVED_RATE')
        self.assertFalse(line['preventive_exposure_exact'])
        self.assertFalse(line['blocks_confirmation'])
        self.assertFalse(summary['preventive_exposure_exact'])
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertFalse(self._locks(order).leakage_amount)
        self.assertFalse(self._locks(order).is_recovered_cash)

    def test_price10_t013_note_line_is_not_a_contract_sale(self):
        self._priced('1150')
        order = self._quote(1150)
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'display_type': 'line_note',
            'name': 'Commercial note',
        })
        summary = self._summary(order)
        notes = [line for line in summary['lines'] if line['kind'] == 'note']
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]['status'], 'NOT_APPLICABLE')
        self.assertFalse(notes[0]['approved_adjusted_unit_price_exact'])
        self.assertFalse(notes[0]['blocks_confirmation'])

    def test_price10_t014_missing_contract_is_not_an_invented_price(self):
        self._priced('1150')
        line, _summary = self._first(self._quote(1100, partner=self.other_partner))
        self.assertEqual(line['status'], 'CONTRACT_NOT_FOUND')
        self.assertFalse(line['approved_adjusted_unit_price_exact'])
        self.assertFalse(line['preventive_exposure_exact'])

    def test_price10_t015_two_approved_contracts_conflict(self):
        self._priced('1150')
        self._priced('1000')
        line, _summary = self._first(self._quote(1150))
        self.assertEqual(line['status'], 'CONTRACT_CONFLICT')
        self.assertFalse(line['approved_adjusted_unit_price_exact'])
        self.assertFalse(line['preventive_exposure_exact'])

    def test_conf10_t001_compliant_order_confirms(self):
        self._priced('1150', owner=self.seller)
        self._mode('block')
        order = self._quote(1150, user=self.seller)
        before = self.env['account.move'].search_count([])
        self._env(self.seller, self.company_a)['sale.order'].browse(order.id).action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(len(self._locks(order)), 1)
        self.assertEqual(self._locks(order).compliance_status, 'COMPLIANT')
        self.assertEqual(self.env['account.move'].search_count([]), before)

    def test_conf10_t002_block_mode_rejects_underpricing(self):
        self._priced('1150')
        self._mode('block')
        order = self._quote(1100)
        with self.assertRaises(UserError):
            order.with_context(skip_price_check=True).action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertFalse(self._locks(order))

    def test_conf10_t003_warning_mode_allows_confirmation_without_an_override(self):
        self._priced('1150')
        self._mode('warning')
        order = self._quote(1100)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        lock = self._locks(order)
        self.assertEqual(lock.compliance_status, 'BELOW_APPROVED_PRICE')
        self.assertEqual(lock.control_mode, 'warning')
        self.assertFalse(lock.approval_id)
        self.assertNotEqual(lock.compliance_status, 'COMPLIANT_AUTHORIZED_OVERRIDE')
        self.assertFalse(lock.is_recovered_cash)

    def test_conf10_t004_pending_approval_blocks_when_approval_is_required(self):
        self._special()
        self._mode('approval_required')
        order = self._quote(1100)
        self._override(order.order_line)
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'APPROVAL_PENDING')
        self.assertTrue(line['blocks_confirmation'])
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertFalse(self._locks(order))

    def test_conf10_t005_valid_override_permits_confirmation(self):
        self._special()
        self._mode('block')
        order = self._quote(1100)
        approval = self._override(order.order_line)
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')
        self.assertEqual(_dec(line['preventive_exposure_exact'] or 0), _dec(0) if not line['preventive_exposure_exact'] else _dec(line['preventive_exposure_exact']))
        self.assertFalse(line['preventive_exposure_exact'])
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        lock = self._locks(order)
        self.assertEqual(lock.approval_id, approval)
        self.assertEqual(lock.compliance_status, 'COMPLIANT_AUTHORIZED_OVERRIDE')
        self.assertFalse(lock.leakage_amount)

    def test_conf10_t006_rejected_override_does_not_authorize(self):
        self._special()
        self._mode('block')
        order = self._quote(1100)
        approval = self._override(order.order_line)
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_reject(
            reason='The reduction is not accepted.',
        )
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'APPROVAL_REJECTED')
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertFalse(self._locks(order))

    def test_conf10_t007_expired_override_does_not_authorize(self):
        self._priced(
            '1150',
            policy={
                **self._limit(),
                'retroactive_discount_authority': 'explicitly_allowed',
            },
        )
        self._mode('block')
        order = self._quote(1100)
        approval = self._override(
            order.order_line,
            effective_from=self._on(-1),
            effective_to=self._on(-1),
        )
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'APPROVAL_EXPIRED')
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')

    def test_conf10_t008_changed_price_invalidates_the_override(self):
        self._special()
        self._mode('block')
        order = self._quote(1100)
        approval = self._override(order.order_line)
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        self._freeze(order.order_line, 1050)
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'BELOW_APPROVED_PRICE')
        self.assertNotEqual(line['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_conf10_t009_changed_quantity_is_not_covered(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100, quantity=100)
        approval = self._override(order.order_line, quantity='100')
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        self._freeze(order.order_line, 1100, quantity=1000)
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'REVIEW_REQUIRED')
        self.assertEqual(line['reason'], 'override_quantity_not_covered')
        self.assertNotEqual(line['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')

    def test_conf10_t010_changed_product_invalidates_the_override(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        approval = self._override(order.order_line)
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        order.order_line.write({
            'product_id': self.other_product.id,
            'price_unit': 1100,
            'technical_price_unit': 0,
        })
        line, _summary = self._first(order)
        self.assertNotEqual(line['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')

    def test_conf10_t011_changed_customer_invalidates_the_override(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        approval = self._override(order.order_line)
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        order.write({'partner_id': self.other_partner.id})
        line, _summary = self._first(order)
        self.assertNotEqual(line['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')
        self.assertEqual(line['status'], 'CONTRACT_NOT_FOUND')

    def test_conf10_t012_changed_currency_is_not_compared_raw(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        approval = self._override(order.order_line)
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        foreign_list = self.env['product.pricelist'].create({
            'name': 'CPLA foreign quotation',
            'currency_id': self.foreign.id,
            'company_id': self.company_a.id,
        })
        order.write({
            'pricelist_id': foreign_list.id,
            'currency_id': self.foreign.id,
        })
        self._freeze(order.order_line, 1100)
        line, _summary = self._first(order)
        self.assertNotEqual(line['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')
        self.assertFalse(line['preventive_exposure_exact'])

    def test_conf10_t013_direct_call_enforces_the_gate(self):
        self._priced('1150', owner=self.seller)
        self._mode('block')
        order = self._quote(1100, user=self.seller)
        with self.assertRaises(UserError) as caught:
            self._env(self.seller, self.company_a)['sale.order'].browse(order.id).action_confirm()
        self.assertIn('Below approved price', str(caught.exception))
        self.assertEqual(order.state, 'draft')
        self.assertFalse(self._locks(order))

    def test_conf10_t014_batch_confirmation_does_not_confirm_a_blocked_order(self):
        self._priced('1150')
        self._mode('block')
        good = self._quote(1150)
        bad = self._quote(1100)
        with self.assertRaises(UserError):
            (good | bad).action_confirm()
        self.assertEqual(good.state, 'draft')
        self.assertEqual(bad.state, 'draft')
        self.assertFalse(self._locks(good))
        self.assertFalse(self._locks(bad))

    def test_conf10_t015_failed_confirmation_stores_no_price_lock(self):
        self._priced('1150')
        self._mode('block')
        order = self._quote(1100)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertEqual(self.env['cpla.sale.price.lock'].search_count([
            ('sale_order_id', '=', order.id),
        ]), 0)

    def test_conf10_t016_standard_confirmation_still_reaches_sale(self):
        self._priced('1150')
        order = self._quote(1150)
        confirmed = order.action_confirm()
        self.assertTrue(confirmed)
        self.assertEqual(order.state, 'sale')
        self.assertEqual(len(self._locks(order)), 1)

    def test_his10_t001_through_t007_confirmed_order_stores_the_pricing_basis(self):
        self.policy_a.write({'pricing_date_policy': 'order_confirmation'})
        version = self._priced('1200', tiers=[(500, None, 1150)])
        order = self._quote(1150)
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'COMPLIANT')
        order.action_confirm()
        lock = self._locks(order)
        self.assertEqual(lock.sale_order_id, order)
        self.assertEqual(lock.sale_line_id, order.order_line)
        self.assertEqual(lock.partner_id, self.partner)
        self.assertEqual(lock.company_id, self.company_a)
        self.assertEqual(lock.product_id, self.bearing)
        self.assertEqual(lock.quantity_exact, '500')
        self.assertEqual(lock.uom_id, self.unit)
        self.assertEqual(lock.pricing_date, self._today())
        self.assertTrue(lock.confirmed_at)
        self.assertEqual(lock.version_id, version)
        self.assertEqual(lock.version_id.state, 'approved')
        self.assertEqual(lock.pricing_date_rule, 'explicit_date')
        self.assertEqual(lock.pricing_date_policy_snapshot, 'order_confirmation')
        self.assertTrue(lock.order_date_lock_candidate)
        self.assertFalse(lock.grandfathering_applied)
        self.assertEqual(lock.tier_id, version.line_ids.tier_ids)
        self.assertEqual(lock.quantity_basis, 'sales_order')
        self.assertEqual(lock.tax_basis, 'tax_excluded')
        self.assertTrue(lock.financial_status)
        self.assertEqual(lock.discount_status, 'NO_ADDITIONAL_DISCOUNT')
        self.assertEqual(lock.approved_adjusted_unit_price_exact, '1150')
        self.assertEqual(lock.actual_unit_price_exact, '1150')
        self.assertEqual(lock.control_mode, 'unconfigured')
        self.assertFalse(lock.leakage_amount)
        self.assertFalse(lock.is_recovered_cash)

    def test_his10_t008_later_contract_price_does_not_rewrite_the_lock(self):
        self.policy_a.write({'pricing_date_policy': 'order_confirmation'})
        version = self._priced('1000')
        order = self._quote(1000)
        order.action_confirm()
        lock = self._locks(order)
        self.assertEqual(lock.version_id, version)
        self.assertEqual(lock.approved_adjusted_unit_price_exact, '1000')
        later = self._env(self.owner, self.company_a)[
            'cpla.customer.contract.version'
        ].browse(version.id).create_amendment()
        later.write({
            'amendment_reason': 'Later list. The confirmed order keeps its basis.',
            'effective_from': self._on(1),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        later.line_ids.write({'price_unit': 1200})
        later.action_submit_for_review()
        self._env(self.finance, self.company_a)[
            'cpla.customer.contract.version'
        ].browse(later.id).action_approve()
        lock.invalidate_recordset()
        self.assertEqual(lock.version_id, version)
        self.assertEqual(lock.approved_adjusted_unit_price_exact, '1000')
        self.assertTrue(lock.order_date_lock_candidate)
        tomorrow = self._env(self.env.user, self.company_a)['cpla.pricing.applicability'].resolve({
            'company_id': self.company_a.id,
            'partner_id': self.partner.id,
            'product_id': self.bearing.id,
            'pricing_date': self._on(1),
            'quantity': '500',
            'order_quantity': '500',
            'quantity_uom_id': self.unit.id,
            'comparison_uom_id': self.unit.id,
        })
        self.assertEqual(tomorrow.get('version_id'), later.id)
        self.assertNotEqual(lock.version_id.id, later.id)

    def test_his10_t009_invoice_date_policy_does_not_lock_the_order_date(self):
        self.policy_a.write({'pricing_date_policy': 'invoice'})
        version = self._priced('1000')
        order = self._quote(1000)
        order.action_confirm()
        lock = self._locks(order)
        self.assertEqual(lock.pricing_date_policy_snapshot, 'invoice')
        self.assertFalse(lock.order_date_lock_candidate)
        self.assertFalse(lock.grandfathering_applied)
        self.assertEqual(lock.version_id, version)

    def test_his10_t010_amendment_keeps_the_original_evidence(self):
        self._priced('1150')
        order = self._quote(1150)
        order.action_confirm()
        lock = self._locks(order)
        original_price = lock.approved_adjusted_unit_price_exact
        original_actual = lock.actual_unit_price_exact
        self._freeze(order.order_line, 900)
        self.assertEqual(lock.approved_adjusted_unit_price_exact, original_price)
        self.assertEqual(lock.actual_unit_price_exact, original_actual)
        self.assertTrue(lock.revalidation_required)
        self.assertEqual(lock.revalidation_reason, 'material_change_after_confirmation')
        with self.assertRaises(UserError):
            lock.write({'approved_adjusted_unit_price_exact': '1'})

    def test_his10_t011_repeated_confirmation_does_not_duplicate_the_lock(self):
        self._priced('1150')
        order = self._quote(1150)
        order.action_confirm()
        order._cpla_store_price_locks()
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(self.env['cpla.sale.price.lock'].search_count([
            ('sale_line_id', '=', order.order_line.id),
        ]), 1)

    def test_his10_t012_snapshot_can_be_read_for_a_later_comparison(self):
        self._priced('1150')
        order = self._quote(1150)
        order.action_confirm()
        lock = self._locks(order)
        self.assertTrue(lock.version_id)
        self.assertTrue(lock.pricing_date)
        self.assertTrue(lock.actual_unit_price_exact)
        self.assertFalse(self.env['cpla.sale.price.lock']._fields.get('invoice_id'))
        self.assertNotIn('account.move.line', self.env['cpla.sale.price.lock']._fields)

    def test_app10_t001_request_is_linked_to_the_exact_line(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        other = self._quote(1100)
        approval = self._override(order.order_line)
        self.assertEqual(approval.state, 'submitted')
        self.assertEqual(approval.sale_order_id, order)
        self.assertEqual(approval.sale_line_id, order.order_line)
        self.assertEqual(approval.sale_reference, str(order.id))
        self.assertEqual(approval.sale_line_reference, str(order.order_line.id))
        self.assertNotEqual(approval.sale_order_id, other)

    def test_app10_t002_requester_cannot_self_approve(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        approval = self._override(order.order_line, user=self.combined)
        with self.assertRaises(AccessError):
            self._env(self.combined, self.company_a)['cpla.discount.approval'].browse(
                approval.id
            ).action_approve()
        self.assertEqual(approval.state, 'submitted')

    def test_app10_t003_and_t007_approver_authority_and_other_order(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        approval = self._override(order.order_line)
        with self.assertRaises(AccessError):
            self._env(self.admin, self.company_a)['cpla.discount.approval'].browse(
                approval.id
            ).action_approve()
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        self.assertEqual(approval.state, 'approved')
        other = self._quote(1100)
        other_line, _summary = self._first(other)
        self.assertNotEqual(other_line['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')

    def test_app10_t004_amount_limit_is_enforced(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1000)
        approval = self._override(order.order_line)
        with self.assertRaises(UserError):
            self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(
                approval.id
            ).action_approve()
        self.assertEqual(approval.state, 'submitted')

    def test_app10_t005_and_t006_company_customer_and_product_scope(self):
        version = self._priced('1150', policy=self._limit())
        order = self._quote(1100, user=self.owner)
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.discount.approval'].create({
                'company_id': self.company_a.id,
                'request_kind': 'transaction_override',
                'version_id': version.id,
                'partner_id': self.partner_b.id,
                'product_id': self.bearing.id,
                'proposed_price_exact': '1100',
                'currency_id': self.company_a.currency_id.id,
                'uom_id': self.unit.id,
                'quantity_exact': '500',
                'sale_reference': str(order.id),
                'sale_line_reference': str(order.order_line.id),
                'sale_order_id': order.id,
                'reason': 'Wrong customer',
                'evidence_reference': 'X',
                'effective_from': self._today(),
            })
        other = self._quote(1100, user=self.owner)
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.discount.approval'].create({
                'company_id': self.company_a.id,
                'request_kind': 'transaction_override',
                'version_id': version.id,
                'partner_id': self.partner.id,
                'product_id': self.bearing.id,
                'proposed_price_exact': '1100',
                'currency_id': self.company_a.currency_id.id,
                'uom_id': self.unit.id,
                'quantity_exact': '500',
                'sale_reference': str(order.id),
                'sale_line_reference': str(other.order_line.id),
                'sale_order_id': order.id,
                'sale_line_id': other.order_line.id,
                'reason': 'Line is on another order',
                'evidence_reference': 'X',
                'effective_from': self._today(),
            })

    def test_app10_t008_lower_price_than_the_override_is_not_authorized(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        approval = self._override(order.order_line)
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        self._freeze(order.order_line, 1090)
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'BELOW_APPROVED_PRICE')

    def test_app10_t009_quantity_scope_is_enforced(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100, quantity=100)
        approval = self._override(order.order_line, quantity='100')
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        covered, _summary = self._first(order)
        self.assertEqual(covered['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')
        self._freeze(order.order_line, 1100, quantity=101)
        uncovered, _summary = self._first(order)
        self.assertEqual(uncovered['reason'], 'override_quantity_not_covered')

    def test_app10_t010_effective_period_is_enforced(self):
        self._priced(
            '1150',
            policy={
                **self._limit(),
                'retroactive_discount_authority': 'explicitly_allowed',
            },
        )
        order = self._quote(1100)
        approval = self._override(
            order.order_line,
            effective_from=self._on(-2),
            effective_to=self._on(-1),
        )
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'APPROVAL_EXPIRED')

    def test_sec10_t001_and_t010_company_boundary(self):
        version = self._priced('1150')
        self.assertFalse(self._env(self.owner_b, self.company_b)['cpla.customer.contract.version'].search([
            ('id', '=', version.id),
        ]))
        order = self._quote(1150)
        with self.assertRaises(AccessError):
            self._summary(order, user=self.owner_b)

    def test_sec10_t002_company_b_override_cannot_authorize_company_a(self):
        version_b = self._priced('1150', company=self.company_b, partner=self.partner_b)
        order = self._quote(1100)
        with self.assertRaises(UserError):
            self.env['cpla.discount.approval'].with_user(self.owner).create({
                'company_id': self.company_a.id,
                'request_kind': 'transaction_override',
                'version_id': version_b.id,
                'partner_id': self.partner.id,
                'product_id': self.bearing.id,
                'proposed_price_exact': '1100',
                'currency_id': self.company_a.currency_id.id,
                'uom_id': self.unit.id,
                'quantity_exact': '500',
                'sale_reference': str(order.id),
                'sale_line_reference': str(order.order_line.id),
                'reason': 'Wrong company version',
                'evidence_reference': 'X',
                'effective_from': self._today(),
            })

    def test_sec10_t003_restricted_user_does_not_receive_the_baseline(self):
        self._priced('1150')
        order = self._quote(1100, user=self.salesman)
        with self.assertRaises(AccessError):
            self._env(self.plain, self.company_a)['cpla.customer.contract.version'].search([])
        line = self._env(self.salesman, self.company_a)['sale.order.line'].browse(order.order_line.id)
        self.assertFalse(line.cpla_approved_price_exact)
        self.assertNotIn('1150', line.cpla_compliance_message or '')
        self.assertNotIn('1100', line.cpla_compliance_message or '')

    def test_sec10_t004_rpc_cannot_skip_the_server_gate(self):
        self._priced('1150')
        self._mode('block')
        order = self._quote(1100)
        with self.assertRaises(UserError):
            order.with_context(skip_price_check=True).action_confirm()
        self.assertEqual(order.state, 'draft')

    def test_sec10_t005_price_lock_mutation_is_denied(self):
        self._priced('1150')
        order = self._quote(1150)
        order.action_confirm()
        lock = self._locks(order)
        with self.assertRaises(UserError):
            lock.write({'actual_unit_price_exact': '1'})
        with self.assertRaises(UserError):
            lock.unlink()
        with self.assertRaises(AccessError):
            self._env(self.plain, self.company_a)['cpla.sale.price.lock'].browse(lock.id).read([
                'approved_adjusted_unit_price_exact',
            ])

    def test_sec10_t006_and_t007_and_t008_separation_of_duties(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        approval = self._override(order.order_line, user=self.owner)
        with self.assertRaises(AccessError):
            self._env(self.owner, self.company_a)['cpla.discount.approval'].browse(
                approval.id
            ).action_approve()
        with self.assertRaises(AccessError):
            self._env(self.admin, self.company_a)['cpla.discount.approval'].browse(
                approval.id
            ).action_approve()
        self.assertFalse(self.reviewer.groups_id if False else self.env['ir.model.access'].search([
            ('group_id', '=', self.env.ref('%s.group_sales_pricing_reviewer' % MODULE).id),
        ]))
        self.assertEqual(self.env['ir.model.access'].search_count([
            ('group_id', '=', self.env.ref('%s.group_app_admin' % MODULE).id),
        ]), 1)
        self.assertEqual(approval.state, 'submitted')

    def test_sec10_t009_export_of_pricing_evidence_is_restricted(self):
        self._priced('1150')
        order = self._quote(1150)
        order.action_confirm()
        lock = self._locks(order)
        with self.assertRaises(UserError):
            self._env(self.auditor, self.company_a)['cpla.sale.price.lock'].browse(
                lock.id
            ).export_data(['approved_adjusted_unit_price_exact'])
        self.assertFalse(self._env(self.owner_b, self.company_b)['cpla.sale.price.lock'].search([
            ('id', '=', lock.id),
        ]))

    def test_con10_t001_second_store_returns_the_same_lock(self):
        self._priced('1150')
        order = self._quote(1150)
        order.action_confirm()
        first = self._locks(order)
        order._cpla_store_price_locks()
        second = self._locks(order)
        self.assertEqual(first, second)
        self.assertEqual(len(second), 1)

    def test_con10_t002_price_change_after_approval_is_rechecked(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100)
        approval = self._override(order.order_line)
        self._freeze(order.order_line, 1050)
        self._env(self.finance, self.company_a)['cpla.discount.approval'].browse(approval.id).action_approve()
        line, _summary = self._first(order)
        self.assertNotEqual(line['status'], 'COMPLIANT_AUTHORIZED_OVERRIDE')
        self.assertEqual(approval.proposed_price_exact, '1100')

    def test_con10_t003_repeated_evaluation_creates_no_exposure_rows(self):
        self._priced('1150')
        order = self._quote(1100)
        before = self.env['cpla.sale.price.lock'].search_count([])
        approvals = self.env['cpla.discount.approval'].search_count([])
        first = self._summary(order)
        second = self._summary(order)
        self.assertEqual(first['status'], second['status'])
        self.assertEqual(first['preventive_exposure_exact'], second['preventive_exposure_exact'])
        self.assertEqual(self.env['cpla.sale.price.lock'].search_count([]), before)
        self.assertEqual(self.env['cpla.discount.approval'].search_count([]), approvals)

    def test_con10_t004_failure_does_not_leave_confirmation_evidence(self):
        self._priced('1150')
        self._mode('block')
        order = self._quote(1100)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')
        self.assertFalse(order.order_line.filtered(lambda line: line.state == 'sale'))
        self.assertFalse(self._locks(order))

    def test_con10_t005_confirmation_reads_the_current_price(self):
        self._priced('1150')
        self._mode('block')
        order = self._quote(1150)
        self._freeze(order.order_line, 1100)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')

    def test_reg10_installation_views_and_no_recovery_documents(self):
        manifest = Manifest.for_addon(MODULE)
        module = self.env['ir.module.module'].search([('name', '=', MODULE)])
        self.assertEqual(module.state, 'installed')
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(module.latest_version, '19.0.1.15.0')
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])
        self.assertNotIn('account', manifest['depends'])
        form = self.env['sale.order'].get_view(view_type='form')
        inherit = self.env.ref('%s.view_order_form_cpla_compliance' % MODULE)
        seller_form = self._env(self.seller, self.company_a)['sale.order'].get_view(view_type='form')
        salesman_form = self._env(self.salesman, self.company_a)['sale.order'].get_view(view_type='form')
        self.assertIn('Recheck Compliance', form['arch'])
        self.assertIn('Contract Compliance', form['arch'])
        self.assertIn('action_cpla_request_override', inherit.arch_db)
        self.assertIn('action_cpla_request_override', seller_form['arch'])
        self.assertNotIn('action_cpla_request_override', salesman_form['arch'])
        self.assertNotIn('Apply Approved Contract Price', form['arch'])
        self.assertNotIn('Run Invoice Audit', form['arch'])
        policy = self.env['cpla.company.policy'].get_view(view_type='form')
        self.assertIn('quotation_compliance_mode', policy['arch'])
        views = self.env['ir.ui.view'].search([('model', '=like', 'cpla.%')])
        for view in views:
            self.assertNotIn('portal', view.arch_db or '')
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', 'in', ['account.move', 'ir.cron', 'ir.actions.server']),
        ]))
        for name in self.env.registry:
            if name == 'cpla.leakage.finding' or name.startswith((
                'cpla.leakage.case', 'cpla.leakage.reassessment',
            )):
                continue
            self.assertFalse(name.startswith((
                'cpla.leakage', 'cpla.audit', 'cpla.waiver',
            )))
        if 'cpla.recovery.request' in self.env.registry:
            self.assertFalse(self.env['cpla.recovery.request'].search_count([]))
        self.assertIn('cpla.pricing.applicability', self.env.registry)
        self.assertIn('cpla.discount.evaluator', self.env.registry)
        self.assertTrue(self.policy_a.exists())
        self.assertFalse(self.policy_a.operationally_approved)

    def test_reg10_delivery_quantity_change_does_not_flag_revalidation(self):
        self._priced('1150')
        order = self._quote(1150)
        order.action_confirm()
        lock = self._locks(order)
        order.order_line.write({'qty_delivered': 1})
        self.assertFalse(lock.revalidation_required)

    def test_quote_ref_019_mixed_lines_do_not_invent_a_note_price(self):
        self._priced('1150')
        self._mode('block')
        order = self._quote(1150)
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'display_type': 'line_note',
            'name': 'Packing note',
        })
        extra = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.bearing.id,
            'product_uom_qty': 500,
        })
        self._freeze(extra, 1100)
        summary = self._summary(order)
        statuses = {line['kind']: [] for line in summary['lines']}
        for line in summary['lines']:
            statuses.setdefault(line['kind'], []).append(line['status'])
        self.assertIn('NOT_APPLICABLE', statuses['note'])
        self.assertIn('COMPLIANT', statuses['product'])
        self.assertIn('BELOW_APPROVED_PRICE', statuses['product'])
        self.assertEqual(summary['status'], 'BELOW_APPROVED_PRICE')
        self.assertEqual(_dec(summary['preventive_exposure_exact']), _dec(25000))
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_quote_ref_013_and_disabled_mode_do_not_block_a_missing_contract(self):
        self._mode('disabled')
        order = self._quote(1100, partner=self.other_partner)
        line, _summary = self._first(order)
        self.assertEqual(line['status'], 'CONTRACT_NOT_FOUND')
        self.assertFalse(line['blocks_confirmation'])
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertNotEqual(self._locks(order).compliance_status, 'COMPLIANT_AUTHORIZED_OVERRIDE')

    def test_unconfigured_mode_blocks_a_detected_reduction_for_a_reader(self):
        self._priced('1150')
        self.assertEqual(self.policy_a.quotation_compliance_mode, 'unconfigured')
        order = self._quote(1100)
        line, _summary = self._first(order)
        self.assertTrue(line['blocks_confirmation'])
        with self.assertRaises(UserError):
            order.action_confirm()
        missing = self._quote(1100, partner=self.other_partner)
        missing_line, _summary = self._first(missing)
        self.assertFalse(missing_line['blocks_confirmation'])

    def test_salesman_without_contract_access_is_not_shown_a_baseline(self):
        self._priced('1150')
        self._mode('warning')
        order = self._quote(1100, user=self.salesman)
        line = self._env(self.salesman, self.company_a)['sale.order.line'].browse(order.order_line.id)
        self.assertFalse(line.cpla_approved_price_exact)
        self.assertFalse(line.cpla_preventive_exposure_exact)
        self._env(self.salesman, self.company_a)['sale.order'].browse(order.id).action_confirm()
        self.assertEqual(order.state, 'sale')
        lock = self._env(self.salesman, self.company_a)['cpla.sale.price.lock'].search([
            ('sale_order_id', '=', order.id),
        ])
        self.assertTrue(lock)
        self.assertFalse(lock.approved_adjusted_unit_price_exact)

    def test_block_mode_does_not_treat_an_unreadable_contract_as_compliant(self):
        self._priced('1150')
        self._mode('block')
        order = self._quote(1150, user=self.salesman)
        with self.assertRaises(UserError):
            self._env(self.salesman, self.company_a)['sale.order'].browse(order.id).action_confirm()
        self.assertEqual(order.state, 'draft')

    def test_invoice_quantity_basis_is_provisional_at_quotation(self):
        self._priced('1200', tiers=[(1, None, 1100)], quantity_basis='invoice_line')
        line, _summary = self._first(self._quote(1100))
        self.assertNotEqual(line['status'], 'COMPLIANT')
        self.assertFalse(line['preventive_exposure_exact'])

    def test_dev10_evaluate_timing_is_logged(self):
        self._priced('1150')
        order = self._quote(1150)
        service = self._env(self.env.user, order.company_id)['cpla.quotation.compliance']
        scoped_order = service.env['sale.order'].browse(order.id)
        started = time.perf_counter()
        for _index in range(30):
            service.evaluate_order(scoped_order)
        elapsed = time.perf_counter() - started
        _logger.info('DEV10 evaluate x30 elapsed %s', elapsed)
        self.assertGreater(elapsed, 0)

    def test_request_override_does_not_approve_or_rewrite_the_price(self):
        self._priced('1150', policy=self._limit())
        order = self._quote(1100, user=self.owner)
        approval = self._env(self.owner, self.company_a)['cpla.quotation.override.request'].create({
            'sale_line_id': order.order_line.id,
            'reason': 'Needs a decision.',
            'evidence_reference': 'MAIL-010',
        }).action_create_request()
        record = self.env['cpla.discount.approval'].browse(approval['res_id'])
        self.assertEqual(record.state, 'draft')
        self.assertEqual(order.order_line.price_unit, 1100)
        self._env(self.owner, self.company_a)['cpla.discount.approval'].browse(record.id).action_submit()
        self.assertEqual(record.state, 'submitted')
        self.assertNotEqual(record.state, 'approved')
        with self.assertRaises(AccessError):
            self._env(self.salesman, self.company_a)['cpla.quotation.override.request'].create({
                'sale_line_id': order.order_line.id,
                'reason': 'Not allowed',
                'evidence_reference': 'X',
            })
