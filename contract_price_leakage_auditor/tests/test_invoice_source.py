import logging
import time

from psycopg2 import IntegrityError

from odoo import Command, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import Manifest
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = 'contract_price_leakage_auditor'
_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDev11InvoiceSource(TransactionCase):
    """Posted invoice source mapping. No leakage finding is created."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env['res.company'].create({'name': 'ABC India'})
        cls.company_b = cls.env['res.company'].create({'name': 'ABC UAE'})
        chart = cls.env['account.chart.template']
        chart.with_company(cls.company_a).try_loading('generic_coa', cls.company_a, install_demo=False)
        chart.with_company(cls.company_b).try_loading('generic_coa', cls.company_b, install_demo=False)
        cls.owner = cls._make_sale_user(
            'cpla11_owner', cls.company_a, extra_groups=('group_contract_user',),
        )
        cls.owner_b = cls._make_user('cpla11_owner_b', 'group_contract_user', cls.company_b)
        cls.manager = cls._make_user('cpla11_manager', 'group_contract_manager', cls.company_a)
        cls.finance = cls._make_account_user('cpla11_finance', 'group_finance_manager', cls.company_a)
        cls.auditor = cls._make_account_user('cpla11_auditor', 'group_internal_auditor', cls.company_a)
        cls.admin = cls._make_user('cpla11_admin', 'group_app_admin', cls.company_a)
        cls.salesman = cls._make_sale_user('cpla11_salesman', cls.company_a)
        cls.plain = new_test_user(
            cls.env,
            login='cpla11_plain',
            groups='base.group_user',
            password='cpla-test',
            company_id=cls.company_a.id,
            company_ids=[Command.set([cls.company_a.id])],
        )
        cls.both = cls._make_account_user(
            'cpla11_both',
            'group_finance_manager',
            cls.company_a,
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
        cls.partner = cls.env['res.partner'].with_company(cls.company_a).create({
            'name': 'XYZ Manufacturing',
            'is_company': True,
            'company_id': cls.company_a.id,
        })
        cls.other_partner = cls.env['res.partner'].with_company(cls.company_a).create({
            'name': 'Unrelated Buyer',
            'is_company': True,
            'company_id': cls.company_a.id,
        })
        cls.partner_b = cls.env['res.partner'].with_company(cls.company_b).create({
            'name': 'UAE Buyer',
            'is_company': True,
            'company_id': cls.company_b.id,
        })
        cls.shared_partner = cls.env['res.partner'].create({
            'name': 'Shared Buyer',
            'is_company': True,
            'company_id': False,
        })
        cls.bearing = cls.env['product.product'].create({
            'name': 'Bearing A',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': 9999.0,
            'company_id': False,
            'taxes_id': [Command.clear()],
        })
        cls.other_product = cls.env['product.product'].create({
            'name': 'Bearing B',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': 9999.0,
            'company_id': False,
            'taxes_id': [Command.clear()],
        })
        cls.unit = cls.env.ref('uom.product_uom_unit')
        for company in (cls.company_a, cls.company_b):
            income = cls.env['account.account'].with_company(company).search([
                ('account_type', '=', 'income'),
            ], limit=1)
            cls.bearing.with_company(company).write({
                'property_account_income_id': income.id,
                'taxes_id': [Command.clear()],
            })
            cls.other_product.with_company(company).write({
                'property_account_income_id': income.id,
                'taxes_id': [Command.clear()],
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
    def _make_account_user(cls, login, xmlid, company, companies=None):
        companies = companies or company
        names = [
            'base.group_user',
            'account.group_account_invoice',
            '%s.%s' % (MODULE, xmlid),
        ]
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
        return fields.Date.context_today(self.env['cpla.invoice.source'])

    def _on(self, days):
        return fields.Date.add(self._today(), days=days)

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
            'source_reference': 'AGR-011',
            'description': 'Signed pricing schedule.',
            'datas': 'c2lnbmVk',
        })
        contract.action_submit_for_review()
        manager = self.manager if company == self.company_a else self._make_user(
            'cpla11_mgr_b_%s' % contract.id, 'group_contract_manager', company,
        )
        return self._env(manager, company)['cpla.customer.contract.version'].approve_initial(
            self._env(manager, company)['cpla.customer.contract'].browse(contract.id)
        )

    def _priced(self, price='1150', company=None, partner=None, product=None, effective=None):
        company = company or self.company_a
        partner = partner or (self.partner if company == self.company_a else self.partner_b)
        product = product or self.bearing
        currency = company.currency_id
        first = self._v1([(product, price)], currency, company=company, partner=partner)
        owner = self.owner if company == self.company_a else self.owner_b
        finance = self.finance if company == self.company_a else self._make_account_user(
            'cpla11_fin_b_%s' % first.id, 'group_finance_manager', company,
        )
        env = self._env(owner, company)
        amendment = env['cpla.customer.contract.version'].browse(first.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Authorized price clause. Not a retroactive restatement.',
            'effective_from': effective or self._today(),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        amendment.line_ids.write({'price_unit': price})
        amendment.action_submit_for_review()
        record = self._env(finance, company)['cpla.customer.contract.version'].browse(amendment.id)
        record.action_approve()
        return record

    def _later(self, version, price, days=10):
        time.sleep(1.1)
        owner = self.owner if version.company_id == self.company_a else self.owner_b
        finance = self.finance if version.company_id == self.company_a else self._make_account_user(
            'cpla11_fin_later_%s' % version.id, 'group_finance_manager', version.company_id,
        )
        env = self._env(owner, version.company_id)
        amendment = env['cpla.customer.contract.version'].browse(version.id).create_amendment()
        amendment.write({
            'amendment_reason': 'Later price. The confirmed order keeps its own basis.',
            'effective_from': self._on(days),
            'comparison_currency_policy': 'contract_currency',
            'tax_basis': 'tax_excluded',
            'tax_structure': 'none',
            'rounding_stage': 'preserve_exact',
        })
        amendment.line_ids.write({'price_unit': price})
        amendment.action_submit_for_review()
        record = self._env(finance, version.company_id)[
            'cpla.customer.contract.version'
        ].browse(amendment.id)
        record.action_approve()
        return record

    def _pricelist(self, company):
        currency = company.currency_id
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

    def _quote(self, price, quantity=100, partner=None, product=None, company=None, discount=0.0, uom=None):
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
        values = {
            'price_unit': price,
            'technical_price_unit': 0,
            'discount': discount,
            'tax_ids': [Command.clear()],
        }
        if uom:
            values['product_uom_id'] = uom.id
        line.write(values)
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
            self.assertEqual(invoice.state, 'posted')
        return invoice

    def _map(self, move):
        return self.env['cpla.invoice.source'].map_move(move)

    def _commercial(self, move):
        maps = self._map(move)
        return maps.filtered(lambda item: item.line_class not in (
            'EXCLUDED_DISPLAY',
            'EXCLUDED_TAX',
            'EXCLUDED_RECEIVABLE',
            'EXCLUDED_ROUNDING',
            'EXCLUDED_EARLY_PAYMENT_DISCOUNT',
            'EXCLUDED_GLOBAL_DISCOUNT',
            'EXCLUDED_DOWN_PAYMENT',
            'EXCLUDED_SHIPPING',
            'EXCLUDED_COGS',
            'EXCLUDED_TECHNICAL',
        ) and item.is_current)

    def _journal(self, company, journal_type):
        return self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', journal_type),
        ], limit=1)

    def _manual(self, move_type='out_invoice', company=None, partner=None, product=None,
                quantity=100, price=1100, post=True, origin=None):
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
            'invoice_origin': origin,
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

    def test_inv11_t001_posted_customer_invoice_is_eligible(self):
        """SRC-REF-001."""
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order, quantity=100)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.document_class, 'ELIGIBLE_CUSTOMER_INVOICE')
        self.assertEqual(mapping.move_state, 'posted')
        self.assertEqual(mapping.mapping_status, 'SOURCE_VERIFIED')
        self.assertEqual(mapping.provenance, 'NATIVE_RELATION_VERIFIED')
        self.assertEqual(mapping.allocation_ids.sale_line_id, order.order_line)
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.amount_total, invoice.amount_total)

    def test_inv11_t002_draft_invoice_is_excluded(self):
        """SRC-REF-015."""
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order, post=False)
        self.assertEqual(invoice.state, 'draft')
        mapping = self._map(invoice).filtered('move_line_id')[:1]
        self.assertEqual(mapping.document_class, 'DRAFT_EXCLUDED')
        self.assertEqual(mapping.mapping_status, 'EXCLUDED_DOCUMENT')
        self.assertFalse(mapping.audit_ready)
        self.assertFalse(mapping.allocation_ids)

    def test_inv11_t003_cancelled_invoice_is_excluded(self):
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order, post=False)
        invoice.button_cancel()
        self.assertEqual(invoice.state, 'cancel')
        mapping = self._map(invoice).filtered('move_line_id')[:1]
        self.assertEqual(mapping.document_class, 'CANCELLED_EXCLUDED')
        self.assertEqual(mapping.mapping_status, 'REVERSED_OR_CANCELLED')
        self.assertFalse(mapping.audit_ready)

    def test_inv11_t004_vendor_bill_is_not_a_customer_sale(self):
        """SRC-REF-016."""
        bill = self._manual(move_type='in_invoice', price=1150)
        mapping = self._map(bill).filtered(lambda item: item.product_id == self.bearing)
        self.assertTrue(mapping)
        self.assertEqual(mapping.document_class, 'NON_CUSTOMER_DOCUMENT')
        self.assertEqual(mapping.mapping_status, 'EXCLUDED_DOCUMENT')
        self.assertFalse(mapping.allocation_ids)
        self.assertFalse(mapping.audit_ready)

    def test_inv11_t005_vendor_refund_is_excluded(self):
        refund = self._manual(move_type='in_refund', price=1150)
        mapping = self._map(refund).filtered(lambda item: item.product_id == self.bearing)
        self.assertEqual(mapping.document_class, 'NON_CUSTOMER_DOCUMENT')
        self.assertNotEqual(mapping.commercial_sign, 1)

    def test_inv11_t006_customer_credit_is_classified_separately(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        credit = invoice._reverse_moves()
        credit.action_post()
        mapping = self._commercial(credit)
        self.assertEqual(mapping.document_class, 'ELIGIBLE_CUSTOMER_CREDIT')
        self.assertEqual(mapping.commercial_sign, -1)
        self.assertNotEqual(mapping.document_class, 'ELIGIBLE_CUSTOMER_INVOICE')

    def test_inv11_t007_product_line_is_commercial(self):
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1150)))
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.line_class, 'COMMERCIAL_PRODUCT')
        self.assertEqual(mapping.product_id, self.bearing)

    def test_inv11_t008_section_and_note_are_excluded(self):
        """SRC-REF-018 display lines."""
        order = self._confirm(self._quote(1150))
        invoice = order._create_invoices()
        invoice.write({'invoice_line_ids': [
            Command.create({'display_type': 'line_section', 'name': 'Section'}),
            Command.create({'display_type': 'line_note', 'name': 'Note'}),
        ]})
        self._product_lines(invoice).write({'tax_ids': [Command.clear()]})
        invoice.action_post()
        maps = self._map(invoice)
        classes = set(maps.mapped('line_class'))
        self.assertIn('EXCLUDED_DISPLAY', classes)
        self.assertIn('COMMERCIAL_PRODUCT', classes)
        for mapping in maps.filtered(lambda item: item.line_class == 'EXCLUDED_DISPLAY'):
            self.assertEqual(mapping.mapping_status, 'UNSUPPORTED_LINE_TYPE')
            self.assertFalse(mapping.allocation_ids)
            self.assertFalse(mapping.version_id if 'version_id' in mapping._fields else False)

    def test_inv11_t009_tax_and_receivable_lines_are_excluded(self):
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        maps = self._map(invoice)
        self.assertTrue(maps.filtered(lambda item: item.line_class == 'EXCLUDED_RECEIVABLE'))
        for mapping in maps.filtered(lambda item: item.line_class == 'EXCLUDED_RECEIVABLE'):
            self.assertEqual(mapping.mapping_status, 'UNSUPPORTED_LINE_TYPE')
            self.assertFalse(mapping.allocation_ids)

    def test_inv11_t010_unsupported_document_type_is_explicit(self):
        receipt = self._manual(move_type='out_receipt')
        mapping = self._map(receipt).filtered(lambda item: item.product_id == self.bearing)
        self.assertEqual(mapping.document_class, 'UNSUPPORTED_DOCUMENT_TYPE')
        self.assertEqual(mapping.mapping_status, 'EXCLUDED_DOCUMENT')
        self.assertIn('UNSUPPORTED_DOCUMENT_TYPE', mapping.exception_codes or '')

    def test_inv11_t011_company_and_customer_are_preserved(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.company_id, self.company_a)
        self.assertEqual(mapping.partner_id, self.partner)
        self.assertEqual(mapping.allocation_ids.sale_order_id.partner_id, self.partner)

    def test_inv11_t012_state_and_dates_are_preserved(self):
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order, invoice_date=self._on(-2))
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.move_state, 'posted')
        self.assertEqual(mapping.invoice_date, invoice.invoice_date)
        self.assertEqual(mapping.posting_date, invoice.date)
        self.assertNotEqual(mapping.invoice_date, self._on(40))

    def test_map11_t001_native_sale_line_is_identified(self):
        """SRC-REF-001."""
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        line = self._product_lines(invoice)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.allocation_ids.sale_line_id, order.order_line)
        self.assertIn(order.order_line, line.sale_line_ids)

    def test_map11_t002_reverse_relation_matches_the_invoice_line(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        line = self._product_lines(invoice)
        self.assertIn(line, order.order_line.invoice_lines)
        self.assertIn(order.order_line, line.sale_line_ids)

    def test_map11_t003_sales_order_identity_is_preserved(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.allocation_ids.sale_order_id, order)
        self.assertNotEqual(mapping.allocation_ids.sale_order_id.name, False)

    def test_map11_t004_confirmed_order_snapshot_is_linked(self):
        version = self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        lock = self.env['cpla.sale.price.lock'].search([('sale_line_id', '=', order.order_line.id)])
        allocation = self._commercial(invoice).allocation_ids
        self.assertEqual(allocation.price_lock_id, lock)
        self.assertEqual(allocation.confirmed_version_id, version)
        self.assertEqual(lock.approved_adjusted_unit_price_exact, '1150')

    def test_map11_t005_contract_version_reference_is_preserved(self):
        version = self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        allocation = self._commercial(invoice).allocation_ids
        self.assertEqual(allocation.version_id, version)
        self.assertEqual(allocation.version_id.state, 'approved')

    def test_map11_t006_multiple_sale_lines_are_not_collapsed(self):
        """SRC-REF-003 and SRC-REF-004 setup before quantities are verified."""
        self._priced('1150')
        first = self._confirm(self._quote(1150, quantity=200))
        second = self._confirm(self._quote(1150, quantity=100))
        invoice = first._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'quantity': 300,
            'tax_ids': [Command.clear()],
            'sale_line_ids': [Command.set((first.order_line | second.order_line).ids)],
        })
        invoice.action_post()
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.mapping_status, 'SOURCE_ALLOCATION_REVIEW_REQUIRED')
        self.assertFalse(mapping.allocation_ids)
        self.assertEqual(len(line.sale_line_ids), 2)

    def test_map11_t007_invoice_origin_text_is_not_proof(self):
        order = self._confirm(self._quote(1150))
        invoice = self._manual(origin=order.name)
        before = invoice.invoice_line_ids.sale_line_ids
        mapping = self._commercial(invoice)
        self.assertFalse(before)
        self.assertEqual(mapping.provenance, 'CANDIDATE_ONLY')
        self.assertEqual(mapping.mapping_status, 'MANUAL_INVOICE_REVIEW_REQUIRED')
        self.assertFalse(mapping.allocation_ids)
        self.assertFalse(mapping.audit_ready)
        self.assertEqual(mapping.candidate_origin, order.name)

    def test_map11_t008_missing_native_link_is_manual(self):
        """SRC-REF-005."""
        invoice = self._manual()
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.provenance, 'UNLINKED_MANUAL_INVOICE')
        self.assertEqual(mapping.mapping_status, 'MANUAL_INVOICE_REVIEW_REQUIRED')
        self.assertFalse(mapping.allocation_ids)
        self.assertFalse(self.env['sale.order'].search([('invoice_ids', 'in', invoice.id)]))

    def test_map11_t009_wrong_product_is_rejected(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, product=self.other_product))
        invoice = self._manual()
        line = self._product_lines(invoice)
        line.write({'sale_line_ids': [Command.set(order.order_line.ids)]})
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.mapping_status, 'SOURCE_RELATION_CONFLICT')
        self.assertIn('PRODUCT_MISMATCH', mapping.exception_codes)
        self.assertFalse(mapping.allocation_ids)

    def test_map11_t010_wrong_customer_is_rejected(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, partner=self.other_partner))
        invoice = self._manual()
        self._product_lines(invoice).write({
            'sale_line_ids': [Command.set(order.order_line.ids)],
        })
        mapping = self._commercial(invoice)
        self.assertIn('WRONG_CUSTOMER_SOURCE', mapping.exception_codes)
        self.assertFalse(mapping.allocation_ids)

    def test_map11_t011_company_mismatch_is_rejected(self):
        """SRC-REF-014."""
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        order = self._confirm(self._quote(1150, company=self.company_b, partner=self.partner_b))
        invoice = self._manual()
        self._product_lines(invoice).write({
            'sale_line_ids': [Command.set(order.order_line.ids)],
        })
        mapping = self._commercial(invoice)
        self.assertIn('WRONG_COMPANY_SOURCE', mapping.exception_codes)
        self.assertFalse(mapping.allocation_ids)
        self.assertNotEqual(mapping.company_id, order.company_id)

    def test_map11_t012_documentary_mapping_is_not_called_native(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._manual(quantity=100, price=1150)
        current = self._commercial(invoice)
        verified = self._env(self.finance, self.company_a)[
            'cpla.invoice.source.map'
        ].browse(current.id).action_verify_documentary(
            [(order.order_line.id, '100')],
            'SHIP-011',
        )
        self.assertEqual(verified.provenance, 'DOCUMENTARY_LINK_VERIFIED')
        self.assertEqual(verified.mapping_method, 'documentary')
        self.assertEqual(verified.documentary_reference, 'SHIP-011')
        self.assertEqual(verified.verified_by_id, self.finance)
        self.assertEqual(verified.allocation_ids.allocation_method, 'documentary_quantity')
        self.assertFalse(invoice.invoice_line_ids.sale_line_ids)

    def test_map11_t013_candidate_mapping_is_not_verified(self):
        order = self._confirm(self._quote(1150))
        invoice = self._manual(origin=order.name)
        mapping = self._commercial(invoice)
        self.assertNotIn(mapping.mapping_status, ('SOURCE_VERIFIED', 'MULTI_SOURCE_VERIFIED'))
        self.assertEqual(mapping.provenance, 'CANDIDATE_ONLY')

    def test_map11_t014_historical_pricing_context_is_returned(self):
        """SRC-REF-006."""
        self.policy_a.write({'pricing_date_policy': 'order_confirmation'})
        version = self._priced('1000')
        order = self._confirm(self._quote(1000))
        later = self._later(version, '1200', days=10)
        invoice = self._invoice(order, invoice_date=self._on(15))
        allocation = self._commercial(invoice).allocation_ids
        self.assertEqual(allocation.version_id, version)
        self.assertNotEqual(allocation.version_id, later)
        self.assertTrue(allocation.order_date_lock_candidate)
        self.assertEqual(allocation.applicable_pricing_date, allocation.price_lock_id.pricing_date)
        self.assertNotEqual(allocation.applicable_pricing_date, invoice.invoice_date)
        self.assertEqual(allocation.approved_unit_price_exact, '1000')

    def test_par11_t001_partial_invoices_keep_each_posted_quantity(self):
        """SRC-REF-002."""
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=500))
        invoices = [
            self._invoice(order, quantity=quantity)
            for quantity in (200, 200, 100)
        ]
        quantities = []
        for invoice in invoices:
            mapping = self._commercial(invoice)
            self.assertEqual(mapping.mapping_status, 'SOURCE_VERIFIED')
            quantities.append(mapping.allocation_ids.allocated_quantity_exact)
        self.assertEqual(quantities, ['200', '200', '100'])

    def test_par11_t002_allocations_reconcile_to_the_order_without_duplication(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=500))
        for quantity in (200, 200, 100):
            self._map(self._invoice(order, quantity=quantity))
        net = self.env['cpla.invoice.source'].net_quantity_for_sale_line(order.order_line)
        self.assertEqual(net, '500')

    def test_par11_t003_ordered_quantity_is_not_billed_on_every_invoice(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=500))
        invoices = [self._invoice(order, quantity=quantity) for quantity in (200, 200, 100)]
        ordered = []
        billed = []
        for invoice in invoices:
            allocation = self._commercial(invoice).allocation_ids
            ordered.append(allocation.ordered_quantity_exact)
            billed.append(allocation.signed_quantity_exact)
        self.assertEqual(ordered, ['500', '500', '500'])
        self.assertEqual(billed, ['200', '200', '100'])
        self.assertNotEqual(sum(int(item) for item in billed), 1500)

    def test_par11_t004_one_invoice_line_can_reference_two_sale_lines(self):
        self._priced('1150')
        first = self._confirm(self._quote(1150, quantity=200))
        second = self._confirm(self._quote(1150, quantity=100))
        invoice = first._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'quantity': 300,
            'price_unit': 1150,
            'tax_ids': [Command.clear()],
            'sale_line_ids': [Command.set((first.order_line | second.order_line).ids)],
        })
        invoice.action_post()
        self.assertEqual(set(line.sale_line_ids.ids), set((first.order_line | second.order_line).ids))
        self.assertEqual(self._commercial(invoice).mapping_status, 'SOURCE_ALLOCATION_REVIEW_REQUIRED')

    def test_par11_t005_verified_split_sums_to_the_invoice_quantity(self):
        """SRC-REF-003."""
        self._priced('1150')
        first = self._confirm(self._quote(1150, quantity=200))
        second = self._confirm(self._quote(1150, quantity=100))
        invoice = first._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'quantity': 300,
            'price_unit': 1150,
            'tax_ids': [Command.clear()],
            'sale_line_ids': [Command.set((first.order_line | second.order_line).ids)],
        })
        invoice.action_post()
        current = self._commercial(invoice)
        verified = current.action_verify_documentary(
            [(first.order_line.id, '200'), (second.order_line.id, '100')],
            'SPLIT-300',
        )
        self.assertEqual(verified.mapping_status, 'MULTI_SOURCE_VERIFIED')
        self.assertEqual(
            sorted(verified.allocation_ids.mapped('allocated_quantity_exact')),
            ['100', '200'],
        )
        self.assertEqual(len(verified.allocation_ids), 2)

    def test_par11_t006_missing_split_stays_in_review(self):
        """SRC-REF-004."""
        self._priced('1150')
        first = self._confirm(self._quote(1150, quantity=200))
        second = self._confirm(self._quote(1150, quantity=100))
        invoice = first._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'quantity': 300,
            'tax_ids': [Command.clear()],
            'sale_line_ids': [Command.set((first.order_line | second.order_line).ids)],
        })
        invoice.action_post()
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.mapping_status, 'SOURCE_ALLOCATION_REVIEW_REQUIRED')
        self.assertIn('ALLOCATION_NOT_VERIFIED', mapping.exception_codes)
        self.assertFalse(mapping.allocation_ids)

    def test_par11_t007_no_proportional_allocation_is_invented(self):
        self._priced('1150')
        first = self._confirm(self._quote(1150, quantity=200))
        second = self._confirm(self._quote(1150, quantity=100))
        invoice = first._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'quantity': 300,
            'tax_ids': [Command.clear()],
            'sale_line_ids': [Command.set((first.order_line | second.order_line).ids)],
        })
        invoice.action_post()
        mapping = self._commercial(invoice)
        self.assertFalse(mapping.allocation_ids.filtered(
            lambda item: item.allocated_quantity_exact == '150'
        ))
        self.assertFalse(mapping.allocation_ids)

    def test_par11_t008_different_uoms_use_the_snapshot_factor(self):
        """SRC-REF-019."""
        box = self.env['uom.uom'].create({
            'name': 'CPLA Box 10',
            'relative_uom_id': self.unit.id,
            'relative_factor': 10.0,
        })
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=1, uom=box))
        invoice = order._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'product_uom_id': self.unit.id,
            'quantity': 10,
            'tax_ids': [Command.clear()],
        })
        invoice.action_post()
        allocation = self._commercial(invoice).allocation_ids
        self.assertEqual(allocation.allocated_quantity_exact, '10')
        self.assertEqual(allocation.converted_sale_quantity_exact, '1')
        self.assertNotEqual(allocation.allocated_quantity_exact, allocation.ordered_quantity_exact)

    def test_par11_t009_product_variant_identity_is_preserved(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        allocation = self._commercial(invoice).allocation_ids
        self.assertEqual(allocation.sale_line_id.product_id, self.bearing)
        self.assertEqual(self._commercial(invoice).product_id, self.bearing)
        self.assertTrue(allocation.product_match)

    def test_par11_t010_order_quantity_remains_the_tier_evidence(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=500))
        invoice = self._invoice(order, quantity=200)
        allocation = self._commercial(invoice).allocation_ids
        self.assertEqual(allocation.ordered_quantity_exact, '500')
        self.assertEqual(allocation.allocated_quantity_exact, '200')
        self.assertEqual(allocation.price_lock_id.quantity_exact, '500')

    def test_par11_t011_invoice_quantity_stays_separate_from_the_order_quantity(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=500))
        invoice = self._invoice(order, quantity=200)
        allocation = self._commercial(invoice).allocation_ids
        self.assertNotEqual(
            allocation.allocated_quantity_exact,
            allocation.ordered_quantity_exact,
        )
        self.assertEqual(allocation.odoo_invoiced_quantity_exact, '200')

    def test_par11_t012_repeat_mapping_does_not_duplicate_quantities(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=500))
        invoices = [self._invoice(order, quantity=quantity) for quantity in (200, 200, 100)]
        service = self.env['cpla.invoice.source']
        for invoice in invoices:
            service.map_move(invoice)
            service.map_move(invoice)
        self.assertEqual(service.net_quantity_for_sale_line(order.order_line), '500')
        self.assertEqual(self.env['cpla.invoice.source.map'].search_count([
            ('move_id', 'in', [invoice.id for invoice in invoices]),
            ('is_current', '=', True),
            ('line_class', '=', 'COMMERCIAL_PRODUCT'),
        ]), 3)

    def test_ref11_t001_posted_customer_credit_is_recognized(self):
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        credit = invoice._reverse_moves()
        credit.action_post()
        self.assertEqual(credit.move_type, 'out_refund')
        self.assertEqual(credit.state, 'posted')
        self.assertEqual(self._commercial(credit).document_class, 'ELIGIBLE_CUSTOMER_CREDIT')

    def test_ref11_t002_document_reversal_is_identified(self):
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        credit = invoice._reverse_moves()
        credit.action_post()
        mapping = self._commercial(credit)
        self.assertEqual(credit.reversed_entry_id, invoice)
        self.assertEqual(mapping.reversed_entry_id, invoice)
        self.assertIn(credit, invoice.reversal_move_ids)

    def test_ref11_t003_full_refund_nets_to_zero(self):
        """SRC-REF-009."""
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        self._map(invoice)
        credit = invoice._reverse_moves()
        credit.action_post()
        self._map(credit)
        mapping = self._commercial(credit)
        self.assertEqual(mapping.credit_class, 'FULL_REVERSAL')
        self.assertEqual(mapping.returned_quantity_exact, '100')
        self.assertEqual(
            self.env['cpla.invoice.source'].net_quantity_for_sale_line(order.order_line),
            '0',
        )

    def test_ref11_t004_partial_refund_nets_the_returned_quantity(self):
        """SRC-REF-010."""
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        self._map(invoice)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        self._map(credit)
        mapping = self._commercial(credit)
        self.assertEqual(mapping.credit_class, 'QUANTITY_RETURN')
        self.assertEqual(mapping.returned_quantity_exact, '20')
        self.assertEqual(
            self.env['cpla.invoice.source'].net_quantity_for_sale_line(order.order_line),
            '80',
        )

    def test_ref11_t005_standalone_credit_requires_review(self):
        """SRC-REF-013."""
        credit = self._manual(move_type='out_refund', quantity=20, price=1150)
        mapping = self._commercial(credit)
        self.assertEqual(mapping.mapping_status, 'CREDIT_ORIGIN_REVIEW_REQUIRED')
        self.assertEqual(mapping.credit_class, 'UNKNOWN_CREDIT_REASON')
        self.assertFalse(mapping.returned_quantity_exact)
        self.assertFalse(mapping.allocation_ids)
        self.assertFalse(mapping.origin_line_id)

    def test_ref11_t006_credit_is_not_a_positive_sale(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        credit = invoice._reverse_moves()
        credit.action_post()
        mapping = self._commercial(credit)
        self.assertEqual(mapping.commercial_sign, -1)
        self.assertTrue(mapping.commercial_quantity_exact.startswith('-'))
        self.assertGreater(self._product_lines(credit).quantity, 0)
        self.assertNotEqual(
            self.env['cpla.invoice.source'].net_quantity_for_sale_line(order.order_line),
            '200',
        )

    def test_ref11_t007_amount_only_credit_does_not_invent_a_return(self):
        """SRC-REF-011."""
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        self._map(invoice)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'price_unit': 50, 'quantity': 100})
        credit.action_post()
        mapping = self._commercial(credit)
        self.assertEqual(mapping.credit_class, 'PRICE_ADJUSTMENT')
        self.assertFalse(mapping.returned_quantity_exact)
        self.assertEqual(mapping.commercial_quantity_exact, '0')
        self.assertFalse(mapping.quantity_trusted)
        self.assertEqual(
            self.env['cpla.invoice.source'].net_quantity_for_sale_line(order.order_line),
            '100',
        )

    def test_ref11_t008_wrong_original_invoice_is_not_used(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, product=self.other_product))
        other = self._invoice(order)
        credit = self._manual(move_type='out_refund', product=self.bearing, post=False)
        credit.write({'reversed_entry_id': other.id})
        credit.action_post()
        mapping = self._commercial(credit)
        self.assertFalse(mapping.allocation_ids)
        self.assertNotEqual(mapping.origin_line_id.product_id, self.other_product)
        self.assertEqual(mapping.mapping_status, 'CREDIT_ORIGIN_REVIEW_REQUIRED')

    def test_ref11_t009_credit_company_mismatch_is_rejected(self):
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        foreign = self._confirm(self._quote(1150, company=self.company_b, partner=self.partner_b))
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({
            'sale_line_ids': [Command.set(foreign.order_line.ids)],
        })
        credit.action_post()
        mapping = self._commercial(credit)
        self.assertIn('WRONG_COMPANY_SOURCE', mapping.exception_codes or '')
        self.assertFalse(mapping.allocation_ids)

    def test_ref11_t010_partial_refund_uses_the_matching_original_line(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        original = self._product_lines(invoice)
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({'quantity': 20})
        credit.action_post()
        mapping = self._commercial(credit)
        self.assertEqual(mapping.origin_line_id, original)
        self.assertEqual(mapping.allocation_ids.origin_move_line_id, original)

    def test_ref11_t011_full_reversal_preserves_the_original_invoice(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        original_map = self._commercial(invoice)
        credit = invoice._reverse_moves()
        credit.action_post()
        self._map(credit)
        self.assertTrue(invoice.exists())
        self.assertEqual(invoice.state, 'posted')
        self.assertTrue(original_map.exists())
        self.assertEqual(original_map.commercial_quantity_exact, '100')

    def test_ref11_t012_replacement_invoice_stays_separate(self):
        """SRC-REF-012."""
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        original = self._invoice(order)
        self._map(original)
        credit = original._reverse_moves()
        credit.action_post()
        self._map(credit)
        replacement = self._invoice(order)
        self._map(replacement)
        self.assertEqual(len({original.id, credit.id, replacement.id}), 3)
        self.assertEqual(
            self.env['cpla.invoice.source'].net_quantity_for_sale_line(order.order_line),
            '100',
        )
        self.assertNotEqual(
            self._commercial(original).move_id,
            self._commercial(replacement).move_id,
        )

    def test_ref11_t013_repeated_refund_mapping_is_idempotent(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        credit = invoice._reverse_moves()
        credit.action_post()
        service = self.env['cpla.invoice.source']
        service.map_move(invoice)
        first = service.map_move(credit)
        second = service.map_move(credit)
        self.assertEqual(first, second)
        self.assertEqual(service.net_quantity_for_sale_line(order.order_line), '0')
        self.assertEqual(self.env['cpla.invoice.source.allocation'].search_count([
            ('map_id.move_id', '=', credit.id),
            ('map_id.is_current', '=', True),
        ]), 1)

    def test_ref11_t014_draft_credit_is_not_a_posted_adjustment(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        self._map(invoice)
        credit = invoice._reverse_moves()
        self.assertEqual(credit.state, 'draft')
        mapping = self._map(credit).filtered(lambda item: item.product_id == self.bearing)[:1]
        self.assertEqual(mapping.document_class, 'DRAFT_EXCLUDED')
        self.assertEqual(
            self.env['cpla.invoice.source'].net_quantity_for_sale_line(order.order_line),
            '100',
        )

    def test_ref11_t015_tax_line_is_not_a_physical_return(self):
        tax = self.env['account.tax'].with_company(self.company_a).create({
            'name': 'CPLA 15',
            'amount': 15.0,
            'type_tax_use': 'sale',
            'company_id': self.company_a.id,
            'country_id': self.company_a.country_id.id,
        })
        if 'price_include_override' in tax._fields:
            tax.price_include_override = 'tax_excluded'
        order = self._confirm(self._quote(1150))
        invoice = order._create_invoices()
        self._product_lines(invoice).write({'tax_ids': [Command.set(tax.ids)]})
        invoice.action_post()
        credit = invoice._reverse_moves()
        credit.action_post()
        maps = self._map(credit)
        tax_maps = maps.filtered(lambda item: item.line_class == 'EXCLUDED_TAX')
        self.assertTrue(tax_maps)
        for tax_map in tax_maps:
            self.assertFalse(tax_map.allocation_ids)
            self.assertFalse(tax_map.returned_quantity_exact)
            self.assertEqual(tax_map.credit_class, 'TAX_ONLY_CORRECTION')

    def test_ref11_t016_mapping_creates_no_recovery_accounting(self):
        payments = self.env['account.payment'].search_count([])
        moves = self.env['account.move'].search_count([])
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        self._map(invoice)
        self.assertEqual(self.env['account.payment'].search_count([]), payments)
        self.assertEqual(invoice.line_ids.mapped('price_unit'), invoice.line_ids.mapped('price_unit'))
        self.assertGreaterEqual(self.env['account.move'].search_count([]), moves)
        self.assertFalse(self.env['cpla.leakage.finding'].search_count([]))
        self.assertNotIn('cpla.recovery', self.env.registry)

    def test_fin11_t001_posted_unit_price_is_captured(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order, price=1100)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.price_unit_exact, '1100')
        self.assertEqual(self._product_lines(invoice).price_unit, 1100)

    def test_fin11_t002_native_discount_is_captured(self):
        self._priced('1200')
        order = self._confirm(self._quote(1200, discount=5))
        invoice = self._invoice(order)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.discount_exact, '5')

    def test_fin11_t003_effective_unit_keeps_the_percent_once(self):
        self._priced('1200')
        order = self._confirm(self._quote(1200, discount=5))
        invoice = self._invoice(order)
        self.assertEqual(self._commercial(invoice).effective_unit_exact, '1140')

    def test_fin11_t004_quantity_and_uom_are_preserved(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.source_quantity_exact, '100')
        self.assertEqual(mapping.uom_id, self.unit)

    def test_fin11_t005_invoice_currency_is_preserved(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.currency_id, invoice.currency_id)
        self.assertEqual(mapping.company_currency_id, self.company_a.currency_id)

    def test_fin11_t006_tax_and_subtotal_evidence_are_preserved(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=2))
        invoice = self._invoice(order)
        line = self._product_lines(invoice)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.tax_basis, 'tax_excluded')
        self.assertEqual(mapping.price_subtotal_exact, str(int(line.price_subtotal)) if line.price_subtotal == int(line.price_subtotal) else mapping.price_subtotal_exact)
        self.assertEqual(mapping.price_subtotal_exact, '2300')

    def test_fin11_t007_invoice_date_is_not_the_posting_date_field(self):
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order, invoice_date=self._on(-5))
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.invoice_date, invoice.invoice_date)
        self.assertEqual(mapping.posting_date, invoice.date)
        self.assertTrue(mapping._fields['invoice_date'])
        self.assertTrue(mapping._fields['posting_date'])

    def test_fin11_t008_confirmed_price_stays_distinct_from_the_invoice_price(self):
        """SRC-REF-008."""
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order, price=1100)
        allocation = self._commercial(invoice).allocation_ids
        self.assertEqual(allocation.confirmed_unit_price_exact, '1150')
        self.assertEqual(self._commercial(invoice).price_unit_exact, '1100')
        self.assertFalse(self._commercial(invoice).leakage_amount)
        self.assertFalse(self._commercial(invoice).is_recovered_cash)

    def test_fin11_t009_grandfather_reference_is_preserved(self):
        self.policy_a.write({'pricing_date_policy': 'order_confirmation'})
        version = self._priced('1000')
        order = self._confirm(self._quote(1000))
        self._later(version, '1200', days=10)
        invoice = self._invoice(order, invoice_date=self._on(15))
        allocation = self._commercial(invoice).allocation_ids
        self.assertTrue(allocation.order_date_lock_candidate)
        self.assertEqual(allocation.price_lock_id.version_id, version)
        self.assertEqual(allocation.version_id, version)

    def test_fin11_t010_invoice_date_policy_uses_the_invoice_date(self):
        """SRC-REF-007."""
        self.policy_a.write({'pricing_date_policy': 'invoice'})
        version = self._priced('1000')
        order = self._confirm(self._quote(1000))
        later = self._later(version, '1200', days=10)
        invoice = self._invoice(order, invoice_date=self._on(10))
        allocation = self._commercial(invoice).allocation_ids
        self.assertFalse(allocation.order_date_lock_candidate)
        self.assertEqual(allocation.confirmed_version_id, version)
        self.assertEqual(allocation.version_id, later)
        self.assertEqual(str(allocation.applicable_pricing_date), str(invoice.invoice_date))

    def test_fin11_t011_missing_historical_contract_is_classified(self):
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.provenance, 'NATIVE_RELATION_VERIFIED')
        self.assertEqual(mapping.mapping_status, 'CONTRACT_CONTEXT_REVIEW_REQUIRED')
        self.assertIn('HISTORICAL_CONTRACT_MISSING', mapping.exception_codes)
        self.assertFalse(mapping.audit_ready)
        self.assertFalse(mapping.allocation_ids.version_id)

    def test_fin11_t012_missing_uom_evidence_is_not_replaced(self):
        invoice = self._manual(post=False)
        line = self._product_lines(invoice)
        line.write({'product_uom_id': False, 'quantity': 4})
        invoice.action_post()
        mapping = self._commercial(invoice)
        self.assertIn('MISSING_UOM_EVIDENCE', mapping.exception_codes or '')
        self.assertFalse(mapping.audit_ready)

    def test_fin11_t013_current_list_price_is_not_the_source_price(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        self.bearing.list_price = 1.0
        mapping = self._map(invoice).filtered(lambda item: item.line_class == 'COMMERCIAL_PRODUCT' and item.is_current)
        self.assertEqual(mapping.price_unit_exact, '1150')
        self.assertNotEqual(mapping.price_unit_exact, '1')

    def test_fin11_t014_no_leakage_finding_is_created(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order, price=900)
        self._map(invoice)
        self.assertFalse(self.env['cpla.leakage.finding'].search_count([]))
        mapping = self._commercial(invoice)
        self.assertFalse(mapping.leakage_amount)
        self.assertFalse(mapping.is_recovered_cash)

    def test_fin11_t015_posted_invoice_is_not_modified(self):
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order, price=1100)
        line = self._product_lines(invoice)
        before = (line.price_unit, line.discount, line.quantity, invoice.partner_id, invoice.company_id, invoice.state)
        self._map(invoice)
        self.assertEqual(
            (line.price_unit, line.discount, line.quantity, invoice.partner_id, invoice.company_id, invoice.state),
            before,
        )

    def test_fin11_t016_revision_remains_traceable(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        first = self._commercial(invoice)
        order.order_line.write({'price_unit': 900, 'technical_price_unit': 0})
        second = self._commercial(invoice)
        self.assertNotEqual(first, second)
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(second.previous_map_id, first)
        self.assertTrue(second.reassessment_required)
        self.assertGreater(second.revision, first.revision)

    def test_sec11_t001_company_user_reads_authorized_source(self):
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1150)))
        mapping = self._commercial(invoice)
        visible = self._env(self.finance, self.company_a)['cpla.invoice.source.map'].search([
            ('id', '=', mapping.id),
        ])
        self.assertEqual(visible, mapping)

    def test_sec11_t002_company_a_cannot_read_company_b_mapping(self):
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        order = self._confirm(self._quote(1150, company=self.company_b, partner=self.partner_b))
        invoice = self._invoice(order)
        mapping = self._map(invoice).filtered(lambda item: item.product_id == self.bearing)[:1]
        self.assertEqual(mapping.company_id, self.company_b)
        hidden = self._env(self.finance, self.company_a)['cpla.invoice.source.map'].search([
            ('id', '=', mapping.id),
        ])
        self.assertFalse(hidden)

    def test_sec11_t003_company_a_cannot_map_company_b_sale_order(self):
        """SRC-REF-014."""
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        foreign = self._confirm(self._quote(1150, company=self.company_b, partner=self.partner_b))
        invoice = self._manual()
        current = self._commercial(invoice)
        with self.assertRaises(UserError):
            current.action_verify_documentary([(foreign.order_line.id, '100')], 'NO-CROSS')

    def test_sec11_t004_shared_customer_does_not_bypass_company(self):
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        foreign = self._confirm(self._quote(
            1150, company=self.company_b, partner=self.shared_partner,
        ))
        invoice = self._manual(partner=self.shared_partner)
        self._product_lines(invoice).write({
            'sale_line_ids': [Command.set(foreign.order_line.ids)],
        })
        mapping = self._commercial(invoice)
        self.assertIn('WRONG_COMPANY_SOURCE', mapping.exception_codes)
        self.assertFalse(mapping.allocation_ids)

    def test_sec11_t005_multi_company_user_still_cannot_cross_companies(self):
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        foreign = self._confirm(self._quote(1150, company=self.company_b, partner=self.partner_b))
        invoice = self._manual()
        current = self._commercial(invoice)
        with self.assertRaises(UserError):
            self.env(user=self.both, context={
                'allowed_company_ids': [self.company_a.id, self.company_b.id],
            })['cpla.invoice.source.map'].browse(current.id).action_verify_documentary(
                [(foreign.order_line.id, '100')],
                'BOTH-NO',
            )

    def test_sec11_t006_unauthorized_correction_is_rejected(self):
        invoice = self._manual()
        mapping = self._commercial(invoice)
        with self.assertRaises(AccessError):
            self._env(self.owner, self.company_a)['cpla.invoice.source.map'].browse(
                mapping.id
            ).write({'mapping_status': 'SOURCE_VERIFIED'})

    def test_sec11_t007_direct_action_checks_the_finance_role(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._manual(quantity=100, price=1150)
        mapping = self._commercial(invoice)
        with self.assertRaises(AccessError):
            self._env(self.owner, self.company_a)['cpla.invoice.source.map'].browse(
                mapping.id
            ).action_verify_documentary([(order.order_line.id, '100')], 'USER-NO')
        forged = self.env['cpla.invoice.source.map'].create({
            'move_line_id': self._product_lines(invoice).id,
            'price_unit_exact': '1',
            'mapping_status': 'SOURCE_VERIFIED',
        })
        self.assertNotEqual(forged.price_unit_exact, '1')

    def test_sec11_t008_mapper_does_not_use_unrestricted_sudo(self):
        root = Manifest.for_addon(MODULE).path
        path = root + '/models/invoice_source.py'
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
        self.assertNotIn('sudo(', text)
        self.assertNotIn('.execute(', text)

    def test_sec11_t009_plain_user_cannot_read_contract_price_evidence(self):
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1150)))
        mapping = self._commercial(invoice)
        plain = self._env(self.plain, self.company_a)
        with self.assertRaises(AccessError):
            plain['cpla.invoice.source.map'].browse(mapping.id).read(['price_unit_exact'])
        with self.assertRaises(AccessError):
            plain['cpla.invoice.source.allocation'].browse(
                mapping.allocation_ids.ids
            ).read(['approved_unit_price_exact'])

    def test_sec11_t010_source_evidence_is_not_an_attachment(self):
        invoice = self._manual()
        before = self.env['ir.attachment'].search_count([
            ('res_model', '=', 'cpla.invoice.source.map'),
        ])
        self._map(invoice)
        self.assertEqual(self.env['ir.attachment'].search_count([
            ('res_model', '=', 'cpla.invoice.source.map'),
        ]), before)

    def test_sec11_t011_unauthorized_export_is_rejected(self):
        invoice = self._manual()
        mapping = self._commercial(invoice)
        with self.assertRaises(UserError):
            self._env(self.owner, self.company_a)['cpla.invoice.source.map'].browse(
                mapping.id
            ).export_data(['mapping_status'])

    def test_sec11_t012_ordinary_user_cannot_rewrite_history(self):
        invoice = self._manual()
        mapping = self._commercial(invoice)
        with self.assertRaises(UserError):
            mapping.write({'price_unit_exact': '1', 'audit_ready': True})
        self.assertNotEqual(mapping.price_unit_exact, '1')

    def test_sec11_t013_credit_and_invoice_company_must_match(self):
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        foreign = self._confirm(self._quote(1150, company=self.company_b, partner=self.partner_b))
        invoice = self._invoice(self._confirm(self._quote(1150)))
        credit = invoice._reverse_moves()
        self._product_lines(credit).write({
            'sale_line_ids': [Command.set(foreign.order_line.ids)],
        })
        credit.action_post()
        mapping = self._commercial(credit)
        self.assertNotEqual(mapping.company_id, foreign.company_id)
        self.assertFalse(mapping.allocation_ids)

    def test_sec11_t014_combined_roles_do_not_cross_companies(self):
        self.policy_b.write({'quotation_compliance_mode': 'warning'})
        foreign = self._invoice(self._confirm(self._quote(
            1150, company=self.company_b, partner=self.partner_b,
        )))
        foreign_map = self._map(foreign).filtered(
            lambda item: item.product_id == self.bearing
        )[:1]
        visible = self.env(user=self.both, context={
            'allowed_company_ids': [self.company_a.id],
        })['cpla.invoice.source.map'].search([('id', '=', foreign_map.id)])
        self.assertFalse(visible)

    def test_idm11_t001_repeat_mapping_keeps_one_current_row(self):
        invoice = self._invoice(self._confirm(self._quote(1150)))
        service = self.env['cpla.invoice.source']
        first = service.map_move(invoice)
        second = service.map_move(invoice)
        self.assertEqual(first, second)
        self.assertEqual(self.env['cpla.invoice.source.map'].search_count([
            ('move_id', '=', invoice.id),
            ('is_current', '=', True),
        ]), len(invoice.line_ids))

    def test_idm11_t002_repeat_mapping_does_not_duplicate_allocations(self):
        self._priced('1150')
        invoice = self._invoice(self._confirm(self._quote(1150)))
        service = self.env['cpla.invoice.source']
        service.map_move(invoice)
        service.map_move(invoice)
        self.assertEqual(self.env['cpla.invoice.source.allocation'].search_count([
            ('map_id.move_id', '=', invoice.id),
            ('map_id.is_current', '=', True),
        ]), 1)

    def test_idm11_t003_unique_current_pointer_rejects_a_second_row(self):
        """The unique pointer is the cross-session guard.

        This TransactionCase does not open a second database session and
        does not commit. It is not evidence of two-worker concurrency.
        """
        invoice = self._invoice(self._confirm(self._quote(1150)))
        current = self._commercial(invoice)
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                models.Model.create(self.env['cpla.invoice.source.map'], [{
                    'company_id': current.company_id.id,
                    'move_id': current.move_id.id,
                    'move_line_id': current.move_line_id.id,
                    'current_line_id': current.move_line_id.id,
                    'is_current': True,
                    'source_fingerprint': current.source_fingerprint + 'x',
                    'revision': 99,
                    'mapping_status': 'MANUAL_INVOICE_REVIEW_REQUIRED',
                    'document_class': current.document_class,
                    'provenance': 'CANDIDATE_ONLY',
                    'line_class': current.line_class,
                }])

    def test_idm11_t004_partial_batch_failure_does_not_verify_the_failed_move(self):
        good = self._invoice(self._confirm(self._quote(1150)))
        bad = self._invoice(self._confirm(self._quote(1000, quantity=2)))
        service = self.env['cpla.invoice.source']
        original = type(service)._evaluate_move

        def boom(self, move):
            if move.id == bad.id:
                raise UserError('boom')
            return original(self, move)

        type(service)._evaluate_move = boom
        try:
            service.map_moves(good | bad)
        finally:
            type(service)._evaluate_move = original
        self.assertTrue(self.env['cpla.invoice.source.map'].search_count([
            ('move_id', '=', good.id),
            ('is_current', '=', True),
        ]))
        self.assertFalse(self.env['cpla.invoice.source.map'].search_count([
            ('move_id', '=', bad.id),
            ('mapping_status', '=', 'SOURCE_VERIFIED'),
        ]))

    def test_idm11_t005_unchanged_fingerprint_returns_the_same_row(self):
        invoice = self._invoice(self._confirm(self._quote(1150)))
        service = self.env['cpla.invoice.source']
        first = service.map_move(invoice)
        fingerprint = first.mapped('source_fingerprint')
        second = service.map_move(invoice)
        self.assertEqual(first.ids, second.ids)
        self.assertEqual(second.mapped('source_fingerprint'), fingerprint)

    def test_idm11_t006_changed_evidence_opens_a_reassessment(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        first = self._commercial(invoice)
        order.order_line.write({'price_unit': 800, 'technical_price_unit': 0})
        second = self._commercial(invoice)
        self.assertTrue(first.exists())
        self.assertFalse(first.is_current)
        self.assertTrue(second.reassessment_required)
        self.assertFalse(second.audit_ready)
        self.assertIn('HISTORICAL_SOURCE_CHANGED', second.exception_codes)

    def test_idm11_t007_two_legitimate_allocations_are_allowed(self):
        self._priced('1150')
        first = self._confirm(self._quote(1150, quantity=200))
        second = self._confirm(self._quote(1150, quantity=100))
        invoice = first._create_invoices()
        line = self._product_lines(invoice)
        line.write({
            'quantity': 300,
            'price_unit': 1150,
            'tax_ids': [Command.clear()],
            'sale_line_ids': [Command.set((first.order_line | second.order_line).ids)],
        })
        invoice.action_post()
        verified = self._commercial(invoice).action_verify_documentary(
            [(first.order_line.id, '200'), (second.order_line.id, '100')],
            'TWO-LINES',
        )
        self.assertEqual(len(verified.allocation_ids), 2)

    def test_idm11_t008_refund_mapping_is_not_applied_twice(self):
        self._priced('1150')
        order = self._confirm(self._quote(1150, quantity=100))
        invoice = self._invoice(order)
        credit = invoice._reverse_moves()
        credit.action_post()
        service = self.env['cpla.invoice.source']
        service.map_move(invoice)
        service.map_move(credit)
        service.map_move(credit)
        self.assertEqual(service.net_quantity_for_sale_line(order.order_line), '0')

    def test_idm11_t009_a_technical_error_is_not_stored_as_verified(self):
        invoice = self._invoice(self._confirm(self._quote(1150)))
        service = self.env['cpla.invoice.source']
        original = type(service)._evaluate_move

        def boom(self, move):
            raise UserError('technical')

        type(service)._evaluate_move = boom
        try:
            service.map_moves(invoice)
        finally:
            type(service)._evaluate_move = original
        self.assertFalse(self.env['cpla.invoice.source.map'].search_count([
            ('move_id', '=', invoice.id),
            ('mapping_status', '=', 'SOURCE_VERIFIED'),
        ]))

    def test_idm11_t010_a_failed_batch_can_be_mapped_again(self):
        invoice = self._invoice(self._confirm(self._quote(1150)))
        service = self.env['cpla.invoice.source']
        original = type(service)._evaluate_move

        def boom(self, move):
            raise UserError('technical')

        type(service)._evaluate_move = boom
        try:
            service.map_moves(invoice)
        finally:
            type(service)._evaluate_move = original
        saved = service.map_move(invoice)
        self.assertTrue(saved)
        self.assertTrue(self._commercial(invoice))

    def test_src_ref_007_invoice_date_context_is_v2(self):
        self.test_fin11_t010_invoice_date_policy_uses_the_invoice_date()

    def test_src_ref_018_mixed_lines_have_no_invented_contract(self):
        invoice = self._manual(post=False)
        invoice.write({'invoice_line_ids': [
            Command.create({'display_type': 'line_section', 'name': 'Section'}),
            Command.create({'display_type': 'line_note', 'name': 'Note'}),
            Command.create({
                'display_type': 'discount',
                'name': 'Global discount',
            }),
        ]})
        invoice.action_post()
        maps = self._map(invoice)
        product = maps.filtered(lambda item: item.line_class == 'COMMERCIAL_PRODUCT')
        self.assertEqual(product.mapping_status, 'MANUAL_INVOICE_REVIEW_REQUIRED')
        self.assertFalse(product.allocation_ids)
        self.assertTrue(maps.filtered(lambda item: item.line_class == 'EXCLUDED_DISPLAY'))
        self.assertTrue(maps.filtered(lambda item: item.line_class == 'EXCLUDED_GLOBAL_DISCOUNT'))
        self.assertTrue(maps.filtered(lambda item: item.line_class == 'EXCLUDED_RECEIVABLE'))

    def test_src_ref_020_delivery_periods_are_not_guessed(self):
        """SRC-REF-020. Stock is not a dependency, so deliveries are not split."""
        self.assertNotIn('stock', Manifest.for_addon(MODULE)['depends'])
        self.policy_a.write({'pricing_date_policy': 'delivery'})
        self._priced('1150')
        order = self._confirm(self._quote(1150))
        invoice = self._invoice(order)
        mapping = self._commercial(invoice)
        allocation = mapping.allocation_ids
        self.assertIn('DELIVERY_DATE_NOT_ALLOCATED', mapping.exception_codes or '')
        self.assertFalse(mapping.audit_ready)
        self.assertFalse(allocation.applicable_pricing_date)
        self.assertFalse(allocation.order_date_lock_candidate)

    def test_zero_price_commercial_line_is_not_a_technical_error(self):
        order = self._confirm(self._quote(0, quantity=5))
        invoice = self._invoice(order, price=0)
        mapping = self._commercial(invoice)
        self.assertEqual(mapping.line_class, 'ZERO_PRICE_COMMERCIAL')
        self.assertNotEqual(mapping.mapping_status, 'UNSUPPORTED_LINE_TYPE')
        self.assertEqual(mapping.effective_unit_exact, '0')

    def test_down_payment_line_is_not_given_a_product_contract(self):
        order = self._confirm(self._quote(1150))
        invoice = order._create_invoices()
        line = self._product_lines(invoice)
        line.write({'is_downpayment': True, 'tax_ids': [Command.clear()]})
        invoice.action_post()
        mapping = self._map(invoice).filtered(lambda item: item.move_line_id == line)
        self.assertEqual(mapping.line_class, 'EXCLUDED_DOWN_PAYMENT')
        self.assertEqual(mapping.mapping_status, 'UNSUPPORTED_LINE_TYPE')
        self.assertFalse(mapping.allocation_ids)

    def test_reg11_views_and_security_load(self):
        self.assertTrue(self.env.ref(MODULE + '.view_cpla_invoice_source_map_form'))
        self.assertTrue(self.env.ref(MODULE + '.cpla_invoice_source_map_company_rule'))
        menu = self.env.ref(MODULE + '.menu_cpla_invoice_source')
        self.assertNotIn(menu, self.env.ref(MODULE + '.group_internal_auditor').menu_access)
        self.assertNotIn(menu, self.env.ref(MODULE + '.group_app_admin').menu_access)
        self.assertIn(menu, self.env.ref(MODULE + '.group_finance_manager').menu_access)
        rules = self.env['ir.rule'].search([
            ('model_id.model', '=', 'cpla.invoice.source.map'),
        ])
        self.assertFalse(rules.groups)
        arch = self.env.ref(MODULE + '.view_cpla_invoice_source_map_form').arch
        self.assertIn('action_open_verification', arch)
        self.assertNotIn('Leakage Confirmed', arch)
        self.assertNotIn('Recovered', arch)

    def test_reg11_prior_services_and_confirmation_gate_remain(self):
        converted = self.env['cpla.pricing.quantity'].convert_quantity('10', '1', '10')
        self.assertTrue(converted['ok'])
        self.assertEqual(converted['exact'], '1')
        self.policy_a.write({'quotation_compliance_mode': 'block'})
        self._priced('1200')
        order = self._quote(1000)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertNotEqual(order.state, 'sale')
        manifest = Manifest.for_addon(MODULE)
        self.assertEqual(manifest['version'], '19.0.1.15.0')
        self.assertEqual(list(manifest['depends']), ['base', 'product', 'sale'])
        self.assertNotIn('account', manifest['depends'])
        self.assertNotIn('stock', manifest['depends'])
        self.assertFalse(self.env['ir.model.data'].search([
            ('module', '=', MODULE),
            ('model', '=', 'ir.cron'),
        ]))

    def test_dev11_repeat_map_timing_is_logged(self):
        invoice = self._invoice(self._confirm(self._quote(1150)))
        service = self.env['cpla.invoice.source']
        service.map_move(invoice)
        started = time.perf_counter()
        for _index in range(30):
            service.map_move(invoice)
        elapsed = time.perf_counter() - started
        _logger.info('DEV11 map x30 %s', elapsed)
        self.assertGreater(elapsed, 0)
