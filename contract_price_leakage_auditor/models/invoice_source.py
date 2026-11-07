import hashlib
import json

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    FINANCE_MANAGER_GROUP,
    MANAGER_GROUP,
    _arithmetic,
    _decimal,
    _text,
)

MODULE = 'contract_price_leakage_auditor'

MAP_GROUPS = (MANAGER_GROUP, FINANCE_MANAGER_GROUP)
VERIFIED_STATUSES = frozenset({'SOURCE_VERIFIED', 'MULTI_SOURCE_VERIFIED'})
QUANTITY_STATUSES = VERIFIED_STATUSES | frozenset({'CONTRACT_CONTEXT_REVIEW_REQUIRED'})
TRUSTED_PROVENANCE = frozenset({
    'NATIVE_RELATION_VERIFIED',
    'DOCUMENTARY_LINK_VERIFIED',
})
EXCLUDED_LINE_CLASSES = frozenset({
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
})
BLOCKING_EXCEPTIONS = frozenset({
    'HISTORICAL_CONTRACT_MISSING',
    'ALLOCATION_NOT_VERIFIED',
    'DELIVERY_DATE_NOT_ALLOCATED',
    'REFUND_ORIGIN_MISSING',
    'REVERSAL_LINE_AMBIGUOUS',
    'WRONG_CUSTOMER_SOURCE',
    'WRONG_COMPANY_SOURCE',
    'PRODUCT_MISMATCH',
    'UOM_MISMATCH',
    'UOM_CONVERSION_FAILED',
    'CANDIDATE_ORIGIN_ONLY',
    'INVALID_ORDER_PRICE_LOCK',
    'CONTRACT_VERSION_CONFLICT',
    'HISTORICAL_SOURCE_CHANGED',
    'PRICE_ADJUSTMENT_UNCLASSIFIED',
    'PRICING_DATE_MISSING',
    'PRICING_DATE_POLICY_NOT_OPERATIONAL',
    'TAX_INCLUDED_REVIEW',
    'MISSING_FX_EVIDENCE',
    'MISSING_UOM_EVIDENCE',
    'RESOLVER_NOT_AUTHORITATIVE',
})


def _codes(value):
    if not value:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        raw = list(value)
    else:
        raw = str(value).split(',')
    return sorted({item.strip() for item in raw if item and str(item).strip()})


def _join(existing, extra=None):
    codes = _codes(existing)
    for item in _codes(extra):
        if item not in codes:
            codes.append(item)
    return ','.join(sorted(set(codes)))


def _same(left, right):
    left_d = _decimal(left)
    right_d = _decimal(right)
    if left_d is None or right_d is None:
        return False
    return left_d == right_d


class InvoiceSource(models.AbstractModel):
    """Read-only posted-invoice source identification.

    The service stores APP 04 evidence. It does not post, edit, refund,
    or reconcile accounting documents, and it does not create leakage findings.
    """

    _name = 'cpla.invoice.source'
    _description = 'Customer Invoice Source Mapper'

    @api.model
    def _can_map(self):
        if self.env.su or self.env.user._is_superuser():
            return True
        return any(self.env.user.has_group(group) for group in MAP_GROUPS)

    @api.model
    def _check_caller(self):
        if self._can_map():
            return True
        raise AccessError(self.env._(
            'You cannot build invoice source evidence with this access.'
        ))

    @api.model
    def _assert_readable(self, move):
        move.ensure_one()
        move.check_access('read')
        if move.company_id not in self.env.companies and not self.env.su:
            raise AccessError(self.env._(
                'You cannot read invoice source evidence for another company.'
            ))
        return True

    @api.model
    def map_moves(self, moves):
        """Map each invoice in its own savepoint.

        A failure on one document rolls that document back. It does not mark
        the failed document as verified and it does not undo earlier documents
        in the batch. This method does not open a second database session.
        """
        self._check_caller()
        saved = self.env['cpla.invoice.source.map']
        for move in moves:
            try:
                with self.env.cr.savepoint():
                    saved |= self.map_move(move)
            except Exception:
                continue
        return saved

    @api.model
    def map_move(self, move):
        self._check_caller()
        move = move.exists()
        if not move:
            raise UserError(self.env._('The invoice to map does not exist.'))
        if len(move) != 1:
            return self.map_moves(move)
        self._assert_readable(move)
        saved = self.env['cpla.invoice.source.map']
        evaluated = self._evaluate_move(move)
        if not evaluated:
            saved |= self._persist(self._header_payload(move), [])
            return saved
        for payload, allocations in evaluated:
            saved |= self._persist(payload, allocations)
        return saved

    @api.model
    def map_line(self, line):
        self._check_caller()
        line = line.exists()
        if len(line) != 1:
            raise UserError(self.env._('Map one invoice line at a time.'))
        self._assert_readable(line.move_id)
        for payload, allocations in self._evaluate_move(line.move_id):
            if payload.get('move_line_id') == line.id:
                return self._persist(payload, allocations)
        raise UserError(self.env._('The invoice line could not be classified.'))

    @api.model
    def document_class(self, move):
        if move.state == 'cancel':
            return 'CANCELLED_EXCLUDED'
        if move.state != 'posted':
            return 'DRAFT_EXCLUDED'
        if move.move_type == 'out_invoice':
            return 'ELIGIBLE_CUSTOMER_INVOICE'
        if move.move_type == 'out_refund':
            return 'ELIGIBLE_CUSTOMER_CREDIT'
        if move.move_type in ('in_invoice', 'in_refund'):
            return 'NON_CUSTOMER_DOCUMENT'
        return 'UNSUPPORTED_DOCUMENT_TYPE'

    @api.model
    def commercial_sign(self, move):
        """Customer invoice is positive billing. Customer credit is negative.

        Odoo keeps a positive quantity on a credit note. The document type
        carries the business sign. ``direction_sign`` is not reused here.
        """
        if move.move_type == 'out_refund':
            return -1
        if move.move_type == 'out_invoice':
            return 1
        return 0

    @api.model
    def line_class(self, line):
        display = line.display_type or ''
        if display in ('line_section', 'line_subsection', 'line_note'):
            return 'EXCLUDED_DISPLAY'
        if display == 'tax':
            return 'EXCLUDED_TAX'
        if display == 'payment_term':
            return 'EXCLUDED_RECEIVABLE'
        if display == 'rounding':
            return 'EXCLUDED_ROUNDING'
        if display == 'epd':
            return 'EXCLUDED_EARLY_PAYMENT_DISCOUNT'
        if display == 'discount':
            return 'EXCLUDED_GLOBAL_DISCOUNT'
        if display == 'cogs':
            return 'EXCLUDED_COGS'
        if display in (
            'non_deductible_product_total',
            'non_deductible_product',
            'non_deductible_tax',
        ):
            return 'EXCLUDED_TECHNICAL'
        if display != 'product':
            return 'EXCLUDED_TECHNICAL'
        if line.is_downpayment:
            return 'EXCLUDED_DOWN_PAYMENT'
        if self._is_shipping(line):
            return 'EXCLUDED_SHIPPING'
        price = _decimal(line.price_unit)
        if price is not None and price == 0:
            return 'ZERO_PRICE_COMMERCIAL'
        product = line.product_id
        if product and product.type == 'service':
            return 'COMMERCIAL_SERVICE'
        if product:
            return 'COMMERCIAL_PRODUCT'
        return 'EXCLUDED_TECHNICAL'

    @api.model
    def _is_shipping(self, line):
        for sale_line in line.sale_line_ids:
            if 'is_delivery' in sale_line._fields and sale_line.is_delivery:
                return True
        return False

    @api.model
    def _evaluate_move(self, move):
        document = self.document_class(move)
        sign = self.commercial_sign(move)
        locks = self._locks_for(move)
        origin_lines = self._origin_lines(move)
        results = []
        for line in move.line_ids:
            results.append(self._evaluate_line(
                line, document, sign, locks, origin_lines,
            ))
        return results

    @api.model
    def _locks_for(self, move):
        sale_lines = move.line_ids.sale_line_ids
        if not sale_lines:
            return {}
        locks = self.env['cpla.sale.price.lock'].search([
            ('sale_line_id', 'in', sale_lines.ids),
        ])
        return {lock.sale_line_id.id: lock for lock in locks}

    @api.model
    def _origin_lines(self, move):
        origin = move.reversed_entry_id
        if not origin or origin.company_id != move.company_id:
            return self.env['account.move.line']
        try:
            origin.check_access('read')
        except AccessError:
            return self.env['account.move.line']
        return origin.line_ids

    @api.model
    def _evaluate_line(self, line, document, sign, locks, origin_lines):
        classification = self.line_class(line)
        payload = self._line_payload(line, document, sign, classification)
        allocations = []
        if document in (
            'DRAFT_EXCLUDED',
            'CANCELLED_EXCLUDED',
            'NON_CUSTOMER_DOCUMENT',
            'UNSUPPORTED_DOCUMENT_TYPE',
        ):
            payload['mapping_status'] = (
                'REVERSED_OR_CANCELLED'
                if document == 'CANCELLED_EXCLUDED'
                else 'EXCLUDED_DOCUMENT'
            )
            payload['provenance'] = 'NOT_APPLICABLE'
            if document == 'UNSUPPORTED_DOCUMENT_TYPE':
                payload['exception_codes'] = 'UNSUPPORTED_DOCUMENT_TYPE'
            self._finish(payload)
            return payload, allocations
        if classification in EXCLUDED_LINE_CLASSES:
            payload['mapping_status'] = 'UNSUPPORTED_LINE_TYPE'
            payload['provenance'] = 'NOT_APPLICABLE'
            if classification == 'EXCLUDED_TAX' and document == 'ELIGIBLE_CUSTOMER_CREDIT':
                payload['credit_class'] = 'TAX_ONLY_CORRECTION'
            self._finish(payload)
            return payload, allocations
        if document == 'ELIGIBLE_CUSTOMER_CREDIT':
            return self._evaluate_credit(line, payload, locks, origin_lines)
        return self._evaluate_sale_link(line, payload, locks)

    @api.model
    def _evaluate_sale_link(self, line, payload, locks):
        move = line.move_id
        native = line.sale_line_ids
        if not native:
            payload['provenance'] = 'UNLINKED_MANUAL_INVOICE'
            payload['mapping_status'] = 'MANUAL_INVOICE_REVIEW_REQUIRED'
            payload['exception_codes'] = _join(
                payload.get('exception_codes'),
                'INVOICE_WITHOUT_SALES_ORDER',
            )
            origin = (move.invoice_origin or '').strip()
            if origin:
                payload['candidate_origin'] = origin
                payload['provenance'] = 'CANDIDATE_ONLY'
                payload['exception_codes'] = _join(
                    payload['exception_codes'],
                    'CANDIDATE_ORIGIN_ONLY',
                )
                self._note_candidate(move, origin, payload)
            self._finish(payload)
            return payload, []
        accepted = []
        exceptions = _codes(payload.get('exception_codes'))
        for sale_line in native:
            reason = self._sale_line_rejection(line, sale_line)
            if reason:
                exceptions.append(reason)
                continue
            accepted.append(sale_line)
        payload['exception_codes'] = _join(exceptions)
        if not accepted:
            payload['provenance'] = 'CONFLICTING_SOURCE_RELATIONS'
            payload['mapping_status'] = 'SOURCE_RELATION_CONFLICT'
            self._finish(payload)
            return payload, []
        if len(accepted) > 1:
            payload['provenance'] = 'NATIVE_RELATION_VERIFIED'
            payload['mapping_status'] = 'SOURCE_ALLOCATION_REVIEW_REQUIRED'
            payload['exception_codes'] = _join(
                payload['exception_codes'],
                ['MULTIPLE_SALES_SOURCES', 'ALLOCATION_NOT_VERIFIED'],
            )
            versions = self._version_ids(accepted, locks)
            if len(versions) > 1:
                payload['exception_codes'] = _join(
                    payload['exception_codes'],
                    'CONTRACT_VERSION_CONFLICT',
                )
            self._finish(payload)
            return payload, []
        sale_line = accepted[0]
        allocation = self._allocation_from_native(line, sale_line, locks)
        if allocation.get('exception'):
            payload['exception_codes'] = _join(
                payload['exception_codes'],
                allocation['exception'],
            )
            payload['provenance'] = 'NATIVE_RELATION_VERIFIED'
            payload['mapping_status'] = 'CONTRACT_CONTEXT_REVIEW_REQUIRED'
            self._finish(payload)
            return payload, []
        payload['provenance'] = 'NATIVE_RELATION_VERIFIED'
        payload['mapping_status'] = 'SOURCE_VERIFIED'
        payload['exception_codes'] = _join(
            payload.get('exception_codes'),
            allocation.get('context_exceptions'),
        )
        self._finish(payload)
        if payload['mapping_status'] in QUANTITY_STATUSES or payload['quantity_trusted']:
            return payload, [allocation['values']]
        return payload, []

    @api.model
    def _evaluate_credit(self, line, payload, locks, origin_lines):
        move = line.move_id
        payload['commercial_sign'] = -1
        quantity = _decimal(line.quantity)
        payload['commercial_quantity_exact'] = _text(
            _arithmetic('mul', quantity or _decimal('0'), _decimal('-1'))
        ) if quantity is not None else False
        subtotal = _decimal(line.price_subtotal)
        if subtotal is not None:
            payload['signed_subtotal_exact'] = _text(
                _arithmetic('mul', subtotal.copy_abs(), _decimal('-1'))
            )
        if not move.reversed_entry_id and not line.sale_line_ids:
            payload['credit_class'] = 'UNKNOWN_CREDIT_REASON'
            payload['provenance'] = 'UNLINKED_MANUAL_INVOICE'
            payload['mapping_status'] = 'CREDIT_ORIGIN_REVIEW_REQUIRED'
            payload['exception_codes'] = 'REFUND_ORIGIN_MISSING'
            payload['returned_quantity_exact'] = False
            self._finish(payload)
            return payload, []
        if move.reversed_entry_id and move.reversed_entry_id.company_id != move.company_id:
            payload['credit_class'] = 'UNKNOWN_CREDIT_REASON'
            payload['provenance'] = 'CONFLICTING_SOURCE_RELATIONS'
            payload['mapping_status'] = 'SOURCE_RELATION_CONFLICT'
            payload['exception_codes'] = 'WRONG_COMPANY_SOURCE'
            payload['returned_quantity_exact'] = False
            self._finish(payload)
            return payload, []
        match = self._match_origin_line(line, origin_lines)
        if match.get('ambiguous'):
            payload['credit_class'] = 'UNKNOWN_CREDIT_REASON'
            payload['provenance'] = 'CONFLICTING_SOURCE_RELATIONS'
            payload['mapping_status'] = 'CREDIT_ORIGIN_REVIEW_REQUIRED'
            payload['exception_codes'] = 'REVERSAL_LINE_AMBIGUOUS'
            payload['returned_quantity_exact'] = False
            self._finish(payload)
            return payload, []
        origin_line = match.get('line')
        if not origin_line:
            payload['credit_class'] = 'UNKNOWN_CREDIT_REASON'
            payload['mapping_status'] = 'CREDIT_ORIGIN_REVIEW_REQUIRED'
            payload['provenance'] = 'CANDIDATE_ONLY' if move.reversed_entry_id else 'UNLINKED_MANUAL_INVOICE'
            payload['exception_codes'] = 'REFUND_ORIGIN_MISSING'
            payload['returned_quantity_exact'] = False
            self._finish(payload)
            return payload, []
        kind = self._credit_kind(line, origin_line, origin_lines)
        payload['credit_class'] = kind
        payload['origin_move_id'] = origin_line.move_id.id
        payload['origin_line_id'] = origin_line.id
        if kind in ('PRICE_ADJUSTMENT', 'COMMERCIAL_CREDIT', 'TAX_ONLY_CORRECTION', 'UNKNOWN_CREDIT_REASON'):
            payload['returned_quantity_exact'] = False
            payload['commercial_quantity_exact'] = '0'
            payload['mapping_status'] = 'SOURCE_VERIFIED' if kind == 'PRICE_ADJUSTMENT' else 'CREDIT_ORIGIN_REVIEW_REQUIRED'
            payload['provenance'] = 'DOCUMENTARY_LINK_VERIFIED' if move.reversed_entry_id else 'CANDIDATE_ONLY'
            if kind == 'PRICE_ADJUSTMENT':
                payload['provenance'] = 'NATIVE_RELATION_VERIFIED' if line.sale_line_ids else 'DOCUMENTARY_LINK_VERIFIED'
                payload['exception_codes'] = ''
            else:
                payload['exception_codes'] = 'PRICE_ADJUSTMENT_UNCLASSIFIED'
            self._finish(payload)
            return payload, []
        payload['returned_quantity_exact'] = _text(quantity) if quantity is not None else False
        sale_lines = line.sale_line_ids or origin_line.sale_line_ids
        if len(sale_lines) != 1:
            payload['mapping_status'] = 'SOURCE_ALLOCATION_REVIEW_REQUIRED'
            payload['provenance'] = 'NATIVE_RELATION_VERIFIED' if sale_lines else 'DOCUMENTARY_LINK_VERIFIED'
            payload['exception_codes'] = _join(
                'REVERSAL_LINE_AMBIGUOUS' if len(sale_lines) > 1 else 'REFUND_ORIGIN_MISSING',
                'ALLOCATION_NOT_VERIFIED',
            )
            payload['returned_quantity_exact'] = False
            payload['commercial_quantity_exact'] = '0'
            self._finish(payload)
            return payload, []
        sale_line = sale_lines[0]
        reason = self._sale_line_rejection(line, sale_line)
        if reason:
            payload['mapping_status'] = 'SOURCE_RELATION_CONFLICT'
            payload['provenance'] = 'CONFLICTING_SOURCE_RELATIONS'
            payload['exception_codes'] = reason
            payload['returned_quantity_exact'] = False
            self._finish(payload)
            return payload, []
        allocation = self._allocation_from_native(line, sale_line, locks, credit=True)
        if allocation.get('exception'):
            payload['exception_codes'] = allocation['exception']
            payload['mapping_status'] = 'CONTRACT_CONTEXT_REVIEW_REQUIRED'
            payload['provenance'] = 'NATIVE_RELATION_VERIFIED'
            payload['returned_quantity_exact'] = False
            self._finish(payload)
            return payload, []
        values = allocation['values']
        values['origin_move_line_id'] = origin_line.id
        values['signed_quantity_exact'] = payload['commercial_quantity_exact']
        payload['provenance'] = 'NATIVE_RELATION_VERIFIED'
        payload['mapping_status'] = 'SOURCE_VERIFIED'
        payload['exception_codes'] = _join(allocation.get('context_exceptions'))
        self._finish(payload)
        return payload, [values]

    @api.model
    def _match_origin_line(self, line, origin_lines):
        commercial = origin_lines.filtered(
            lambda item: self.line_class(item) not in EXCLUDED_LINE_CLASSES
            and item.product_id == line.product_id
            and item.product_uom_id == line.product_uom_id
        )
        if not commercial:
            return {}
        if len(commercial) == 1:
            return {'line': commercial}
        quantity = _decimal(line.quantity)
        same_qty = commercial.filtered(lambda item: _same(item.quantity, quantity))
        if len(same_qty) == 1:
            return {'line': same_qty}
        return {'ambiguous': True}

    @api.model
    def _credit_kind(self, line, origin_line, origin_lines):
        quantity = _decimal(line.quantity)
        if quantity is None:
            return 'UNKNOWN_CREDIT_REASON'
        if quantity == 0:
            subtotal = _decimal(line.price_subtotal)
            if subtotal is not None and subtotal != 0:
                return 'PRICE_ADJUSTMENT'
            return 'UNKNOWN_CREDIT_REASON'
        origin_qty = _decimal(origin_line.quantity)
        credit_unit, _reason = self.env['cpla.quotation.compliance']._effective_unit(line)
        origin_unit, _origin_reason = self.env['cpla.quotation.compliance']._effective_unit(origin_line)
        price_matches = (
            credit_unit is not None
            and origin_unit is not None
            and credit_unit == origin_unit
        )
        if not price_matches:
            if origin_qty is not None and quantity == origin_qty:
                return 'PRICE_ADJUSTMENT'
            return 'UNKNOWN_CREDIT_REASON'
        if origin_qty is None or quantity > origin_qty:
            return 'UNKNOWN_CREDIT_REASON'
        commercial_origin = origin_lines.filtered(
            lambda item: self.line_class(item) not in EXCLUDED_LINE_CLASSES
        )
        if quantity == origin_qty and len(commercial_origin) == 1:
            return 'FULL_REVERSAL'
        return 'QUANTITY_RETURN'

    @api.model
    def _sale_line_rejection(self, line, sale_line):
        move = line.move_id
        order = sale_line.order_id
        try:
            sale_line.check_access('read')
            order.check_access('read')
        except AccessError:
            return 'WRONG_COMPANY_SOURCE'
        if order.company_id != move.company_id:
            return 'WRONG_COMPANY_SOURCE'
        if sale_line.product_id != line.product_id:
            return 'PRODUCT_MISMATCH'
        if not self._same_customer(move, order):
            return 'WRONG_CUSTOMER_SOURCE'
        return False

    @api.model
    def _same_customer(self, move, order):
        left = move.partner_id.commercial_partner_id
        right = order.partner_id.commercial_partner_id
        return bool(left and right and left == right)

    @api.model
    def _version_ids(self, sale_lines, locks):
        versions = set()
        for sale_line in sale_lines:
            lock = locks.get(sale_line.id)
            if lock and lock.version_id:
                versions.add(lock.version_id.id)
        return versions

    @api.model
    def _allocation_from_native(self, line, sale_line, locks, credit=False):
        move = line.move_id
        lock = locks.get(sale_line.id)
        if lock is None:
            lock = self.env['cpla.sale.price.lock'].search([
                ('sale_line_id', '=', sale_line.id),
            ], limit=1)
        context_exceptions = []
        converted = self._convert_to_sale_uom(line, sale_line)
        if not converted.get('ok'):
            return {'exception': converted.get('exception') or 'UOM_CONVERSION_FAILED'}
        context = self._pricing_context(move, line, sale_line, lock)
        context_exceptions.extend(context.get('exceptions') or [])
        quantity = _decimal(line.quantity) or _decimal('0')
        signed = quantity
        if credit or move.move_type == 'out_refund':
            signed = _arithmetic('mul', quantity, _decimal('-1'))
        values = {
            'company_id': move.company_id.id,
            'sale_order_id': sale_line.order_id.id,
            'sale_line_id': sale_line.id,
            'allocated_quantity_exact': _text(quantity),
            'signed_quantity_exact': _text(signed),
            'allocation_uom_id': line.product_uom_id.id,
            'converted_sale_quantity_exact': converted.get('exact') or False,
            'sale_uom_id': sale_line.product_uom_id.id,
            'allocation_method': 'native_line_quantity',
            'ordered_quantity_exact': _text(_decimal(sale_line.product_uom_qty) or _decimal('0')),
            'delivered_quantity_exact': _text(_decimal(sale_line.qty_delivered) or _decimal('0')),
            'odoo_invoiced_quantity_exact': _text(_decimal(sale_line.qty_invoiced) or _decimal('0')),
            'price_lock_id': lock.id if lock else False,
            'confirmed_version_id': lock.version_id.id if lock and lock.version_id else False,
            'version_id': context.get('applicable_version_id') or False,
            'contract_id': context.get('contract_id') or False,
            'pricing_date_policy_snapshot': lock.pricing_date_policy_snapshot if lock else False,
            'order_date_lock_candidate': bool(context.get('order_date_lock_candidate')),
            'applicable_pricing_date': context.get('applicable_pricing_date') or False,
            'lock_pricing_date': lock.pricing_date if lock else False,
            'confirmed_unit_price_exact': lock.actual_unit_price_exact if lock else False,
            'approved_unit_price_exact': context.get('approved_unit_price_exact') or (
                lock.approved_adjusted_unit_price_exact if lock else False
            ),
            'product_match': True,
            'partner_match': True,
            'company_match': True,
        }
        return {'values': values, 'context_exceptions': context_exceptions}

    @api.model
    def _convert_to_sale_uom(self, line, sale_line):
        invoice_uom = line.product_uom_id
        sale_uom = sale_line.product_uom_id
        if not invoice_uom or not sale_uom:
            return {'ok': False, 'exception': 'MISSING_UOM_EVIDENCE'}
        if invoice_uom == sale_uom:
            quantity = _decimal(line.quantity)
            return {'ok': True, 'exact': _text(quantity) if quantity is not None else False}
        if invoice_uom.factor <= 0 or sale_uom.factor <= 0:
            return {'ok': False, 'exception': 'UOM_CONVERSION_FAILED'}
        converted = self.env['cpla.pricing.quantity'].convert_quantity(
            line.quantity,
            invoice_uom.factor,
            sale_uom.factor,
        )
        if not converted.get('ok'):
            return {'ok': False, 'exception': 'UOM_CONVERSION_FAILED'}
        parsed = _decimal(converted.get('exact'))
        if parsed is None:
            return {'ok': False, 'exception': 'UOM_CONVERSION_FAILED'}
        return {'ok': True, 'exact': _text(parsed)}

    @api.model
    def _pricing_context(self, move, line, sale_line, lock):
        if not lock or not lock.version_id:
            return {
                'exceptions': ['HISTORICAL_CONTRACT_MISSING'],
                'order_date_lock_candidate': False,
            }
        if lock.company_id != move.company_id:
            return {'exceptions': ['WRONG_COMPANY_SOURCE']}
        snapshot = lock.pricing_date_policy_snapshot or 'unconfigured'
        if snapshot == 'order_confirmation':
            if not lock.order_date_lock_candidate or not lock.pricing_date:
                return {'exceptions': ['INVALID_ORDER_PRICE_LOCK']}
            return {
                'applicable_version_id': lock.version_id.id,
                'contract_id': lock.contract_id.id,
                'applicable_pricing_date': lock.pricing_date,
                'order_date_lock_candidate': True,
                'approved_unit_price_exact': lock.approved_adjusted_unit_price_exact,
            }
        if snapshot == 'delivery':
            return {
                'exceptions': ['DELIVERY_DATE_NOT_ALLOCATED'],
                'order_date_lock_candidate': False,
                'confirmed_version_id': lock.version_id.id,
            }
        if snapshot == 'invoice':
            if not move.invoice_date:
                return {'exceptions': ['PRICING_DATE_MISSING']}
            resolved = self._resolve_invoice_date(move, line, sale_line, lock)
            if resolved.get('exception'):
                return resolved
            return resolved
        return {'exceptions': ['PRICING_DATE_POLICY_NOT_OPERATIONAL']}

    @api.model
    def _resolve_invoice_date(self, move, line, sale_line, lock):
        """Ask the approved resolver which version the invoice date selects.

        The confirmed-order lock stays attached. It is not rewritten and it
        is not treated as an order-date price lock.
        """
        order_qty = lock.quantity_exact or _text(_decimal(sale_line.product_uom_qty) or _decimal('0'))
        request = {
            'company_id': move.company_id.id,
            'partner_id': move.partner_id.id,
            'product_id': line.product_id.id,
            'pricing_date': move.invoice_date,
            'quantity': order_qty,
            'order_quantity': order_qty,
            'quantity_uom_id': sale_line.product_uom_id.id,
            'comparison_uom_id': line.product_uom_id.id,
            'sale_reference': sale_line.order_id.name or '',
            'sale_line_reference': str(sale_line.id),
        }
        resolved = self.env['cpla.pricing.applicability'].resolve(request)
        status = resolved.get('status')
        if status != 'MATCHED_AUTHORITATIVE' or not resolved.get('version_id'):
            return {
                'exceptions': ['RESOLVER_NOT_AUTHORITATIVE'],
                'order_date_lock_candidate': False,
            }
        version = self.env['cpla.customer.contract.version'].browse(resolved['version_id']).exists()
        if not version or version.company_id != move.company_id:
            return {'exceptions': ['WRONG_COMPANY_SOURCE']}
        return {
            'applicable_version_id': version.id,
            'contract_id': version.contract_id.id,
            'applicable_pricing_date': move.invoice_date,
            'order_date_lock_candidate': False,
            'approved_unit_price_exact': resolved.get('approved_adjusted_unit_price_exact') or False,
        }

    @api.model
    def _note_candidate(self, move, origin, payload):
        """Record that free text named an order. Do not link it as verified."""
        found = self.env['sale.order'].search([
            ('name', '=', origin),
            ('company_id', '=', move.company_id.id),
        ], limit=2)
        if len(found) == 1 and self._same_customer(move, found):
            payload['candidate_order_name'] = found.name
        else:
            payload['candidate_order_name'] = False

    @api.model
    def _line_payload(self, line, document, sign, classification):
        move = line.move_id
        quantity = _decimal(line.quantity)
        effective, price_reason = self.env['cpla.quotation.compliance']._effective_unit(line)
        tax_basis = self.env['cpla.quotation.compliance']._sale_tax_basis(line)
        subtotal = _decimal(line.price_subtotal)
        signed_subtotal = False
        if subtotal is not None and sign:
            signed_subtotal = _text(_arithmetic('mul', subtotal.copy_abs(), _decimal(sign)))
        commercial_qty = False
        if quantity is not None and sign:
            commercial_qty = _text(_arithmetic('mul', quantity, _decimal(sign)))
        exceptions = []
        if price_reason:
            exceptions.append('PRICE_EVIDENCE_INCOMPLETE')
        if tax_basis == 'tax_included_or_mixed':
            exceptions.append('TAX_INCLUDED_REVIEW')
        if tax_basis == 'tax_unknown':
            exceptions.append('TAX_INCLUDED_REVIEW')
        if (
            move.currency_id
            and move.company_id.currency_id
            and move.currency_id != move.company_id.currency_id
            and not move.invoice_currency_rate
        ):
            exceptions.append('MISSING_FX_EVIDENCE')
        if classification not in EXCLUDED_LINE_CLASSES and not line.product_uom_id:
            exceptions.append('MISSING_UOM_EVIDENCE')
        return {
            'company_id': move.company_id.id,
            'move_id': move.id,
            'move_line_id': line.id,
            'partner_id': move.partner_id.id,
            'product_id': line.product_id.id,
            'document_class': document,
            'line_class': classification,
            'move_type': move.move_type,
            'move_state': move.state,
            'commercial_sign': sign,
            'source_quantity_exact': _text(quantity) if quantity is not None else False,
            'commercial_quantity_exact': commercial_qty,
            'returned_quantity_exact': False,
            'uom_id': line.product_uom_id.id,
            'currency_id': move.currency_id.id,
            'company_currency_id': move.company_id.currency_id.id,
            'price_unit_exact': _text(_decimal(line.price_unit)) if _decimal(line.price_unit) is not None else False,
            'discount_exact': _text(_decimal(line.discount) or _decimal('0')),
            'effective_unit_exact': _text(effective) if effective is not None else False,
            'price_subtotal_exact': _text(subtotal) if subtotal is not None else False,
            'price_total_exact': _text(_decimal(line.price_total)) if _decimal(line.price_total) is not None else False,
            'signed_subtotal_exact': signed_subtotal,
            'tax_basis': tax_basis,
            'tax_ids_text': ','.join(str(tax_id) for tax_id in sorted(line.tax_ids.ids)),
            'fiscal_position_id': move.fiscal_position_id.id,
            'invoice_date': move.invoice_date,
            'posting_date': move.date,
            'invoice_currency_rate_exact': (
                _text(_decimal(move.invoice_currency_rate))
                if _decimal(move.invoice_currency_rate) is not None
                else False
            ),
            'reversed_entry_id': move.reversed_entry_id.id,
            'candidate_origin': False,
            'candidate_order_name': False,
            'credit_class': False,
            'origin_move_id': False,
            'origin_line_id': False,
            'exception_codes': _join(exceptions),
            'mapping_method': 'automatic',
            'leakage_amount': False,
            'is_recovered_cash': False,
            'source_fingerprint': self._fingerprint(line),
        }

    @api.model
    def _header_payload(self, move):
        document = self.document_class(move)
        payload = {
            'company_id': move.company_id.id,
            'move_id': move.id,
            'move_line_id': False,
            'partner_id': move.partner_id.id,
            'document_class': document,
            'line_class': 'EXCLUDED_TECHNICAL',
            'move_type': move.move_type,
            'move_state': move.state,
            'commercial_sign': self.commercial_sign(move),
            'currency_id': move.currency_id.id,
            'company_currency_id': move.company_id.currency_id.id,
            'invoice_date': move.invoice_date,
            'posting_date': move.date,
            'mapping_status': 'EXCLUDED_DOCUMENT',
            'provenance': 'NOT_APPLICABLE',
            'mapping_method': 'automatic',
            'leakage_amount': False,
            'is_recovered_cash': False,
            'source_fingerprint': self._fingerprint_move(move),
            'exception_codes': (
                'UNSUPPORTED_DOCUMENT_TYPE'
                if document == 'UNSUPPORTED_DOCUMENT_TYPE'
                else False
            ),
        }
        self._finish(payload)
        return payload

    @api.model
    def _finish(self, payload):
        exceptions = _codes(payload.get('exception_codes'))
        status = payload.get('mapping_status')
        blocking = [code for code in exceptions if code in BLOCKING_EXCEPTIONS]
        if blocking and status in VERIFIED_STATUSES:
            if 'DELIVERY_DATE_NOT_ALLOCATED' in blocking or 'HISTORICAL_CONTRACT_MISSING' in blocking or (
                'PRICING_DATE_MISSING' in blocking
            ) or 'PRICING_DATE_POLICY_NOT_OPERATIONAL' in blocking or (
                'RESOLVER_NOT_AUTHORITATIVE' in blocking
            ) or 'INVALID_ORDER_PRICE_LOCK' in blocking or 'TAX_INCLUDED_REVIEW' in blocking or (
                'MISSING_FX_EVIDENCE' in blocking
            ):
                status = 'CONTRACT_CONTEXT_REVIEW_REQUIRED'
            elif 'ALLOCATION_NOT_VERIFIED' in blocking or 'UOM_MISMATCH' in blocking or (
                'UOM_CONVERSION_FAILED' in blocking
            ):
                status = 'SOURCE_ALLOCATION_REVIEW_REQUIRED'
            elif 'REFUND_ORIGIN_MISSING' in blocking or 'REVERSAL_LINE_AMBIGUOUS' in blocking:
                status = 'CREDIT_ORIGIN_REVIEW_REQUIRED'
            elif 'WRONG_COMPANY_SOURCE' in blocking:
                status = 'COMPANY_ACCESS_DENIED'
            else:
                status = 'CONTRACT_CONTEXT_REVIEW_REQUIRED'
            payload['mapping_status'] = status
        quantity_trusted = (
            payload.get('provenance') in TRUSTED_PROVENANCE
            and status in QUANTITY_STATUSES
            and 'ALLOCATION_NOT_VERIFIED' not in exceptions
            and 'UOM_CONVERSION_FAILED' not in exceptions
            and 'WRONG_COMPANY_SOURCE' not in exceptions
            and 'PRODUCT_MISMATCH' not in exceptions
            and 'WRONG_CUSTOMER_SOURCE' not in exceptions
        )
        if payload.get('credit_class') in (
            'PRICE_ADJUSTMENT',
            'UNKNOWN_CREDIT_REASON',
            'TAX_ONLY_CORRECTION',
            'COMMERCIAL_CREDIT',
        ):
            quantity_trusted = False
        payload['quantity_trusted'] = quantity_trusted
        payload['audit_ready'] = bool(
            status in VERIFIED_STATUSES and not blocking and quantity_trusted
        )
        payload['exception_codes'] = _join(exceptions) or False
        payload['is_current'] = True
        if payload.get('move_line_id'):
            payload['current_line_id'] = payload['move_line_id']
            payload['current_header_move_id'] = False
        else:
            payload['current_line_id'] = False
            payload['current_header_move_id'] = payload.get('move_id')

    @api.model
    def _fingerprint(self, line):
        move = line.move_id
        lock_rows = []
        locks = self.env['cpla.sale.price.lock'].search([
            ('sale_line_id', 'in', line.sale_line_ids.ids),
        ]) if line.sale_line_ids else self.env['cpla.sale.price.lock']
        for lock in locks.sorted('id'):
            lock_rows.append({
                'id': lock.id,
                'fingerprint': lock.line_fingerprint or '',
                'revalidation': bool(lock.revalidation_required),
                'version_id': lock.version_id.id or 0,
            })
        payload = {
            'move_id': move.id,
            'line_id': line.id,
            'move_type': move.move_type,
            'state': move.state,
            'company_id': move.company_id.id,
            'partner_id': move.partner_id.id,
            'product_id': line.product_id.id or 0,
            'quantity': _text(_decimal(line.quantity) or _decimal('0')),
            'uom_id': line.product_uom_id.id or 0,
            'price_unit': _text(_decimal(line.price_unit) or _decimal('0')),
            'discount': _text(_decimal(line.discount) or _decimal('0')),
            'currency_id': move.currency_id.id or 0,
            'tax_ids': sorted(line.tax_ids.ids),
            'sale_line_ids': sorted(line.sale_line_ids.ids),
            'reversed_entry_id': move.reversed_entry_id.id or 0,
            'invoice_date': str(move.invoice_date or ''),
            'date': str(move.date or ''),
            'locks': lock_rows,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode('utf-8')
        ).hexdigest()

    @api.model
    def _fingerprint_move(self, move):
        payload = {
            'move_id': move.id,
            'line_id': 0,
            'move_type': move.move_type,
            'state': move.state,
            'company_id': move.company_id.id,
            'partner_id': move.partner_id.id,
            'date': str(move.date or ''),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode('utf-8')
        ).hexdigest()

    @api.model
    def _persist(self, payload, allocations, replacing=False):
        Map = self.env['cpla.invoice.source.map']
        existing = self._current_map(payload)
        if (
            existing
            and existing.source_fingerprint == payload.get('source_fingerprint')
            and not replacing
        ):
            return existing
        if existing:
            payload = dict(payload)
            payload['revision'] = (existing.revision or 1) + 1
            payload['previous_map_id'] = existing.id
            if not replacing:
                payload['reassessment_required'] = True
                payload['exception_codes'] = _join(
                    payload.get('exception_codes'),
                    'HISTORICAL_SOURCE_CHANGED',
                )
                payload['audit_ready'] = False
                if payload.get('mapping_status') in VERIFIED_STATUSES:
                    payload['mapping_status'] = 'HISTORICAL_EVIDENCE_INCOMPLETE'
                payload['quantity_trusted'] = False
            existing.write({
                'is_current': False,
                'current_line_id': False,
                'current_header_move_id': False,
            })
        else:
            payload = dict(payload)
            payload['revision'] = 1
            payload.setdefault('reassessment_required', False)
        try:
            with self.env.cr.savepoint():
                record = models.Model.create(Map, [payload])
        except IntegrityError:
            current = self._current_map(payload)
            if current and current.source_fingerprint == payload.get('source_fingerprint'):
                return current
            raise
        if allocations and (record.quantity_trusted or replacing):
            rows = []
            for values in allocations:
                row = dict(values)
                row['map_id'] = record.id
                row['company_id'] = record.company_id.id
                rows.append(row)
            models.Model.create(self.env['cpla.invoice.source.allocation'], rows)
        return record

    @api.model
    def _current_map(self, payload):
        Map = self.env['cpla.invoice.source.map']
        if payload.get('move_line_id'):
            return Map.search([
                ('current_line_id', '=', payload['move_line_id']),
            ], limit=1)
        return Map.search([
            ('current_header_move_id', '=', payload.get('move_id')),
        ], limit=1)

    @api.model
    def net_quantity_for_sale_line(self, sale_line):
        """Sum trusted signed quantities for one sales line.

        Review-only and reassessment rows are omitted. The ordered quantity
        is not added again for each invoice.
        """
        sale_line.ensure_one()
        sale_line.check_access('read')
        allocations = self.env['cpla.invoice.source.allocation'].search([
            ('sale_line_id', '=', sale_line.id),
            ('map_id.is_current', '=', True),
            ('map_id.quantity_trusted', '=', True),
        ])
        total = _decimal('0')
        for allocation in allocations:
            signed = _decimal(allocation.signed_quantity_exact)
            if signed is None:
                continue
            total = _arithmetic('add', total, signed)
        return _text(total)


class InvoiceSourceMap(models.Model):
    """Current source evidence for one invoice line revision.

    Older revisions stay in the table with ``is_current`` clear. Posted
    accounting documents are not written by this model.
    """

    _name = 'cpla.invoice.source.map'
    _description = 'Invoice Source Mapping'
    _order = 'id desc'
    _check_company_auto = True

    _current_line_unique = models.Constraint(
        'UNIQUE(current_line_id)',
        'This invoice line already has current source evidence.',
    )
    _current_header_unique = models.Constraint(
        'UNIQUE(current_header_move_id)',
        'This invoice already has current header source evidence.',
    )

    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    move_id = fields.Many2one(
        'account.move', required=True, index=True, readonly=True, ondelete='restrict',
        check_company=True,
    )
    move_line_id = fields.Many2one(
        'account.move.line', index=True, readonly=True, ondelete='restrict',
    )
    current_line_id = fields.Many2one('account.move.line', index=True, readonly=True, copy=False)
    current_header_move_id = fields.Many2one('account.move', index=True, readonly=True, copy=False)
    partner_id = fields.Many2one('res.partner', readonly=True, index=True)
    product_id = fields.Many2one('product.product', readonly=True, index=True)
    document_class = fields.Selection(
        selection=[
            ('ELIGIBLE_CUSTOMER_INVOICE', 'Eligible customer invoice'),
            ('ELIGIBLE_CUSTOMER_CREDIT', 'Eligible customer credit'),
            ('DRAFT_EXCLUDED', 'Draft excluded'),
            ('CANCELLED_EXCLUDED', 'Cancelled excluded'),
            ('NON_CUSTOMER_DOCUMENT', 'Not a customer document'),
            ('UNSUPPORTED_DOCUMENT_TYPE', 'Unsupported document type'),
        ],
        readonly=True,
        index=True,
    )
    line_class = fields.Char(readonly=True, index=True)
    mapping_status = fields.Selection(
        selection=[
            ('SOURCE_VERIFIED', 'Source verified'),
            ('MULTI_SOURCE_VERIFIED', 'Multiple sources verified'),
            ('MANUAL_INVOICE_REVIEW_REQUIRED', 'Manual invoice review'),
            ('SOURCE_ALLOCATION_REVIEW_REQUIRED', 'Allocation review'),
            ('CONTRACT_CONTEXT_REVIEW_REQUIRED', 'Contract context review'),
            ('UNSUPPORTED_LINE_TYPE', 'Unsupported line'),
            ('SOURCE_RELATION_CONFLICT', 'Source conflict'),
            ('CREDIT_ORIGIN_REVIEW_REQUIRED', 'Credit origin review'),
            ('REVERSED_OR_CANCELLED', 'Reversed or cancelled'),
            ('HISTORICAL_EVIDENCE_INCOMPLETE', 'Historical evidence incomplete'),
            ('COMPANY_ACCESS_DENIED', 'Company access denied'),
            ('EXCLUDED_DOCUMENT', 'Excluded document'),
            ('MAPPING_FAILED', 'Mapping failed'),
        ],
        readonly=True,
        index=True,
    )
    provenance = fields.Selection(
        selection=[
            ('NATIVE_RELATION_VERIFIED', 'Native relation verified'),
            ('DOCUMENTARY_LINK_VERIFIED', 'Documentary link verified'),
            ('CANDIDATE_ONLY', 'Candidate only'),
            ('UNLINKED_MANUAL_INVOICE', 'Unlinked manual invoice'),
            ('CONFLICTING_SOURCE_RELATIONS', 'Conflicting relations'),
            ('NOT_APPLICABLE', 'Not applicable'),
        ],
        readonly=True,
    )
    credit_class = fields.Selection(
        selection=[
            ('QUANTITY_RETURN', 'Quantity return'),
            ('PRICE_ADJUSTMENT', 'Price adjustment'),
            ('TAX_ONLY_CORRECTION', 'Tax-only correction'),
            ('COMMERCIAL_CREDIT', 'Commercial credit'),
            ('FULL_REVERSAL', 'Full reversal'),
            ('UNKNOWN_CREDIT_REASON', 'Unknown credit reason'),
        ],
        readonly=True,
    )
    commercial_sign = fields.Integer(readonly=True)
    source_quantity_exact = fields.Char(readonly=True)
    commercial_quantity_exact = fields.Char(readonly=True)
    returned_quantity_exact = fields.Char(readonly=True)
    uom_id = fields.Many2one('uom.uom', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    company_currency_id = fields.Many2one('res.currency', readonly=True)
    price_unit_exact = fields.Char(readonly=True)
    discount_exact = fields.Char(readonly=True)
    effective_unit_exact = fields.Char(readonly=True)
    price_subtotal_exact = fields.Char(readonly=True)
    price_total_exact = fields.Char(readonly=True)
    signed_subtotal_exact = fields.Char(readonly=True)
    tax_basis = fields.Char(readonly=True)
    tax_ids_text = fields.Char(readonly=True)
    fiscal_position_id = fields.Many2one('account.fiscal.position', readonly=True)
    invoice_date = fields.Date(readonly=True)
    posting_date = fields.Date(readonly=True)
    move_type = fields.Char(readonly=True)
    move_state = fields.Char(readonly=True)
    invoice_currency_rate_exact = fields.Char(readonly=True)
    reversed_entry_id = fields.Many2one('account.move', readonly=True)
    origin_move_id = fields.Many2one('account.move', readonly=True)
    origin_line_id = fields.Many2one('account.move.line', readonly=True)
    candidate_origin = fields.Char(readonly=True)
    candidate_order_name = fields.Char(readonly=True)
    exception_codes = fields.Char(readonly=True)
    mapping_method = fields.Selection(
        selection=[
            ('automatic', 'Automatic'),
            ('documentary', 'Documentary verification'),
            ('reassessment_accepted', 'Reassessment accepted'),
        ],
        readonly=True,
    )
    quantity_trusted = fields.Boolean(readonly=True)
    audit_ready = fields.Boolean(readonly=True, index=True)
    reassessment_required = fields.Boolean(readonly=True, index=True)
    source_fingerprint = fields.Char(readonly=True, index=True)
    revision = fields.Integer(readonly=True, default=1)
    is_current = fields.Boolean(readonly=True, index=True)
    previous_map_id = fields.Many2one('cpla.invoice.source.map', readonly=True)
    verified_by_id = fields.Many2one('res.users', readonly=True)
    verified_on = fields.Datetime(readonly=True)
    documentary_reference = fields.Char(readonly=True)
    allocation_ids = fields.One2many('cpla.invoice.source.allocation', 'map_id')
    leakage_amount = fields.Boolean(readonly=True, default=False)
    is_recovered_cash = fields.Boolean(readonly=True, default=False)

    @api.model_create_multi
    def create(self, vals_list):
        service = self.env['cpla.invoice.source']
        service._check_caller()
        records = self.browse()
        for vals in vals_list:
            line_id = vals.get('move_line_id')
            move_id = vals.get('move_id')
            if line_id:
                line = self.env['account.move.line'].browse(line_id).exists()
                if not line:
                    raise UserError(self.env._('The invoice line does not exist.'))
                records |= service.map_line(line)
            elif move_id:
                move = self.env['account.move'].browse(move_id).exists()
                if not move:
                    raise UserError(self.env._('The invoice does not exist.'))
                records |= service.map_move(move)
            else:
                raise UserError(self.env._(
                    'Source evidence is created from an invoice. Client prices are ignored.'
                ))
        return records

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        allowed = {'is_current', 'current_line_id', 'current_header_move_id'}
        if set(vals) <= allowed and vals.get('is_current') is False and not vals.get('current_line_id'):
            if not self.env['cpla.invoice.source']._can_map():
                raise AccessError(self.env._(
                    'You cannot change invoice source evidence.'
                ))
            return super().write(vals)
        raise UserError(self.env._(
            'Invoice source evidence cannot be overwritten.'
        ))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.check_access('unlink')
        raise UserError(self.env._(
            'Invoice source evidence cannot be deleted.'
        ))

    def action_refresh(self):
        self.ensure_one()
        self.move_id.check_access('read')
        self.env['cpla.invoice.source'].map_move(self.move_id)
        return self.move_id.action_cpla_open_source_maps()

    def action_open_verification(self):
        self.ensure_one()
        if not self.env.user.has_group(FINANCE_MANAGER_GROUP) and not self.env.su:
            raise AccessError(self.env._(
                'Only a finance manager can verify documentary source evidence.'
            ))
        self.move_id.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Verify source evidence'),
            'res_model': 'cpla.invoice.source.verification',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_map_id': self.id},
        }

    def action_accept_reassessment(self):
        """Record a new revision that accepts an unchanged recalculation.

        The previous revision stays. This does not edit the invoice.
        """
        self.ensure_one()
        if not self.env.user.has_group(FINANCE_MANAGER_GROUP) and not self.env.su:
            raise AccessError(self.env._(
                'Only a finance manager can accept a source reassessment.'
            ))
        if not self.is_current or not self.reassessment_required:
            raise UserError(self.env._(
                'Only the current reassessment can be accepted.'
            ))
        service = self.env['cpla.invoice.source']
        service._assert_readable(self.move_id)
        if self.move_line_id:
            fresh = service._fingerprint(self.move_line_id)
        else:
            fresh = service._fingerprint_move(self.move_id)
        if fresh != self.source_fingerprint:
            raise UserError(self.env._(
                'The invoice changed again. Refresh the source evidence before accepting it.'
            ))
        if self.move_line_id:
            evaluated = [
                item for item in service._evaluate_move(self.move_id)
                if item[0].get('move_line_id') == self.move_line_id.id
            ]
        else:
            evaluated = [(service._header_payload(self.move_id), [])]
        if not evaluated:
            raise UserError(self.env._('The invoice line could not be classified.'))
        payload, allocations = evaluated[0]
        if payload.get('mapping_status') not in VERIFIED_STATUSES | QUANTITY_STATUSES:
            raise UserError(self.env._(
                'The refreshed evidence is still not verified. Acceptance was not stored.'
            ))
        blocking = [
            code for code in _codes(payload.get('exception_codes'))
            if code in BLOCKING_EXCEPTIONS
        ]
        if blocking:
            raise UserError(self.env._(
                'Blocking source exceptions remain. Acceptance was not stored.'
            ))
        payload['mapping_method'] = 'reassessment_accepted'
        payload['verified_by_id'] = self.env.user.id
        payload['verified_on'] = fields.Datetime.now()
        payload['reassessment_required'] = False
        return service._persist(payload, allocations, replacing=True)

    def action_verify_documentary(self, sale_line_quantities, reference):
        """Store an authorized quantity split. This is not a native Odoo link."""
        self.ensure_one()
        if not self.env.user.has_group(FINANCE_MANAGER_GROUP) and not self.env.su:
            raise AccessError(self.env._(
                'Only a finance manager can verify documentary source evidence.'
            ))
        reference = (reference or '').strip()
        if not reference:
            raise UserError(self.env._(
                'Documentary verification needs a source reference.'
            ))
        if not self.move_line_id or not self.is_current:
            raise UserError(self.env._(
                'Verify the current commercial invoice line.'
            ))
        service = self.env['cpla.invoice.source']
        line = self.move_line_id
        service._assert_readable(line.move_id)
        if service.line_class(line) in EXCLUDED_LINE_CLASSES:
            raise UserError(self.env._(
                'This invoice line is not a commercial source line.'
            ))
        if not sale_line_quantities:
            raise UserError(self.env._('Name each source line and its quantity.'))
        native_ids = set(line.sale_line_ids.ids)
        locks = service._locks_for(line.move_id)
        allocations = []
        total = _decimal('0')
        seen = set()
        for sale_line_id, quantity_text in sale_line_quantities:
            sale_line = self.env['sale.order.line'].browse(sale_line_id).exists()
            if not sale_line:
                raise UserError(self.env._('A source sales line does not exist.'))
            if sale_line.id in seen:
                raise UserError(self.env._(
                    'The same sales line was named twice. The split was not stored.'
                ))
            seen.add(sale_line.id)
            reason = service._sale_line_rejection(line, sale_line)
            if reason:
                raise UserError(self.env._(
                    'The sales line does not match this invoice line.'
                ))
            if native_ids and sale_line.id not in native_ids:
                raise UserError(self.env._(
                    'The sales line is not one of the native invoice links.'
                ))
            quantity = _decimal(quantity_text)
            if quantity is None or quantity <= 0:
                raise UserError(self.env._(
                    'Each allocated quantity must be greater than zero.'
                ))
            invoice_qty = _decimal(line.quantity)
            if invoice_qty is None:
                raise UserError(self.env._('The invoice line has no quantity.'))
            total = _arithmetic('add', total, quantity)
            built = service._allocation_from_native(line, sale_line, locks)
            if built.get('exception'):
                raise UserError(self.env._(
                    'The sales line could not be converted onto the invoice unit.'
                ))
            values = built['values']
            values['allocated_quantity_exact'] = _text(quantity)
            values['signed_quantity_exact'] = _text(quantity)
            values['allocation_method'] = 'documentary_quantity'
            if line.product_uom_id == sale_line.product_uom_id:
                values['converted_sale_quantity_exact'] = _text(quantity)
            else:
                converted = self.env['cpla.pricing.quantity'].convert_quantity(
                    _text(quantity),
                    line.product_uom_id.factor,
                    sale_line.product_uom_id.factor,
                )
                if not converted.get('ok'):
                    raise UserError(self.env._(
                        'The allocated quantity could not be converted to the sales unit.'
                    ))
                parsed = _decimal(converted.get('exact'))
                if parsed is None:
                    raise UserError(self.env._(
                        'The allocated quantity could not be converted to the sales unit.'
                    ))
                values['converted_sale_quantity_exact'] = _text(parsed)
            if built.get('context_exceptions'):
                raise UserError(self.env._(
                    'Historical pricing evidence for this split is incomplete.'
                ))
            allocations.append(values)
        invoice_qty = _decimal(line.quantity)
        if total != invoice_qty:
            raise UserError(self.env._(
                'The allocated quantities do not equal the invoice line quantity.'
            ))
        payload = service._line_payload(
            line,
            service.document_class(line.move_id),
            service.commercial_sign(line.move_id),
            service.line_class(line),
        )
        payload['provenance'] = (
            'NATIVE_RELATION_VERIFIED' if native_ids else 'DOCUMENTARY_LINK_VERIFIED'
        )
        payload['mapping_status'] = (
            'MULTI_SOURCE_VERIFIED' if len(allocations) > 1 else 'SOURCE_VERIFIED'
        )
        payload['mapping_method'] = 'documentary'
        payload['documentary_reference'] = reference
        payload['verified_by_id'] = self.env.user.id
        payload['verified_on'] = fields.Datetime.now()
        payload['exception_codes'] = False
        payload['reassessment_required'] = False
        service._finish(payload)
        if not payload.get('audit_ready'):
            raise UserError(self.env._(
                'The split still has blocking source exceptions. It was not stored as verified.'
            ))
        return service._persist(payload, allocations, replacing=True)


class InvoiceSourceAllocation(models.Model):
    _name = 'cpla.invoice.source.allocation'
    _description = 'Invoice Source Allocation'
    _order = 'id'
    _check_company_auto = True

    _map_sale_line_unique = models.Constraint(
        'UNIQUE(map_id, sale_line_id)',
        'This source line is already allocated on the mapping.',
    )

    map_id = fields.Many2one(
        'cpla.invoice.source.map', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    sale_order_id = fields.Many2one('sale.order', readonly=True, index=True, check_company=True)
    sale_line_id = fields.Many2one('sale.order.line', readonly=True, index=True)
    allocated_quantity_exact = fields.Char(readonly=True)
    signed_quantity_exact = fields.Char(readonly=True)
    allocation_uom_id = fields.Many2one('uom.uom', readonly=True)
    converted_sale_quantity_exact = fields.Char(readonly=True)
    sale_uom_id = fields.Many2one('uom.uom', readonly=True)
    allocation_method = fields.Selection(
        selection=[
            ('native_line_quantity', 'Native invoice line quantity'),
            ('documentary_quantity', 'Documentary quantity'),
        ],
        readonly=True,
    )
    ordered_quantity_exact = fields.Char(readonly=True)
    delivered_quantity_exact = fields.Char(readonly=True)
    odoo_invoiced_quantity_exact = fields.Char(readonly=True)
    price_lock_id = fields.Many2one('cpla.sale.price.lock', readonly=True)
    confirmed_version_id = fields.Many2one('cpla.customer.contract.version', readonly=True)
    version_id = fields.Many2one('cpla.customer.contract.version', readonly=True)
    contract_id = fields.Many2one('cpla.customer.contract', readonly=True)
    pricing_date_policy_snapshot = fields.Char(readonly=True)
    order_date_lock_candidate = fields.Boolean(readonly=True)
    applicable_pricing_date = fields.Date(readonly=True)
    lock_pricing_date = fields.Date(readonly=True)
    confirmed_unit_price_exact = fields.Char(readonly=True)
    approved_unit_price_exact = fields.Char(readonly=True)
    origin_move_line_id = fields.Many2one('account.move.line', readonly=True)
    product_match = fields.Boolean(readonly=True)
    partner_match = fields.Boolean(readonly=True)
    company_match = fields.Boolean(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env['cpla.invoice.source']._can_map():
            raise AccessError(self.env._(
                'You cannot create invoice source allocations.'
            ))
        for vals in vals_list:
            mapping = self.env['cpla.invoice.source.map'].browse(vals.get('map_id')).exists()
            sale_line = self.env['sale.order.line'].browse(vals.get('sale_line_id')).exists()
            if not mapping or not sale_line:
                raise UserError(self.env._(
                    'An allocation needs a source mapping and a sales line.'
                ))
            if mapping.company_id != sale_line.order_id.company_id:
                raise UserError(self.env._(
                    'The sales line belongs to another company.'
                ))
            if vals.get('company_id') and vals['company_id'] != mapping.company_id.id:
                raise UserError(self.env._(
                    'The allocation company does not match the invoice.'
                ))
            vals['company_id'] = mapping.company_id.id
        return super().create(vals_list)

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        raise UserError(self.env._(
            'Source allocations cannot be overwritten.'
        ))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.check_access('unlink')
        raise UserError(self.env._(
            'Source allocations cannot be deleted.'
        ))


class InvoiceSourceVerification(models.TransientModel):
    _name = 'cpla.invoice.source.verification'
    _description = 'Invoice Source Documentary Verification'

    map_id = fields.Many2one('cpla.invoice.source.map', required=True)
    company_id = fields.Many2one(related='map_id.company_id', store=True)
    documentary_reference = fields.Char(required=True)
    line_ids = fields.One2many(
        'cpla.invoice.source.verification.line',
        'verification_id',
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group(FINANCE_MANAGER_GROUP) and not self.env.su:
            raise AccessError(self.env._(
                'Only a finance manager can verify documentary source evidence.'
            ))
        pairs = [
            (line.sale_line_id.id, line.quantity_exact)
            for line in self.line_ids
        ]
        record = self.map_id.action_verify_documentary(pairs, self.documentary_reference)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Invoice source evidence'),
            'res_model': 'cpla.invoice.source.map',
            'res_id': record.id,
            'view_mode': 'form',
        }


class InvoiceSourceVerificationLine(models.TransientModel):
    _name = 'cpla.invoice.source.verification.line'
    _description = 'Invoice Source Documentary Quantity'

    verification_id = fields.Many2one(
        'cpla.invoice.source.verification', required=True, ondelete='cascade',
    )
    company_id = fields.Many2one(related='verification_id.company_id', store=True)
    sale_line_id = fields.Many2one('sale.order.line', required=True)
    quantity_exact = fields.Char(
        required=True,
        string='Quantity in the invoice unit',
    )


class AccountMoveSourceEvidence(models.Model):
    _inherit = 'account.move'

    cpla_source_map_count = fields.Integer(compute='_compute_cpla_source_map_count')

    def _compute_cpla_source_map_count(self):
        Map = self.env['cpla.invoice.source.map']
        for move in self:
            try:
                move.cpla_source_map_count = Map.search_count([
                    ('move_id', '=', move.id),
                    ('is_current', '=', True),
                ])
            except AccessError:
                move.cpla_source_map_count = 0

    def action_cpla_open_source_maps(self):
        self.ensure_one()
        self.check_access('read')
        if not self.env['cpla.invoice.source.map'].has_access('read'):
            raise AccessError(self.env._(
                'You cannot read invoice source evidence.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Source evidence'),
            'res_model': 'cpla.invoice.source.map',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
            'context': {'create': False, 'search_default_filter_current': 1},
        }

    def action_cpla_map_source(self):
        """Build source evidence for this invoice. The invoice is not edited."""
        records = self
        for move in records:
            move.check_access('read')
            amount = move.amount_total
            state = move.state
            partner = move.partner_id
            company = move.company_id
            self.env['cpla.invoice.source'].map_move(move)
            if (
                move.amount_total != amount
                or move.state != state
                or move.partner_id != partner
                or move.company_id != company
            ):
                raise UserError(self.env._(
                    'Source mapping must not change the accounting document.'
                ))
        if len(records) == 1:
            return records.action_cpla_open_source_maps()
        return True
