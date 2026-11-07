from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.contract_price_leakage_auditor.models.discount_authority import (
    AUTHORITATIVE,
    READ_GROUPS,
    SUCCESS_FINANCIAL,
    USER_GROUP,
)
from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    _arithmetic,
    _decimal,
    _text,
)

HUNDRED = _decimal('100')
OPEN_STATUSES = frozenset({
    'COMPLIANT',
    'COMPLIANT_AUTHORIZED_OVERRIDE',
    'NOT_APPLICABLE',
    'PRICE_ABOVE_APPROVED_RATE',
})
PRICE_PROBLEMS = frozenset({
    'BELOW_APPROVED_PRICE',
    'APPROVAL_PENDING',
    'APPROVAL_REJECTED',
    'APPROVAL_EXPIRED',
})
UNCERTAIN = frozenset({
    'CONTRACT_CONFLICT',
    'MISSING_PRICING_EVIDENCE',
    'REVIEW_REQUIRED',
    'TECHNICAL_ERROR',
})
PUBLIC_MESSAGE = {
    'COMPLIANT': 'Approved contract price found.',
    'COMPLIANT_AUTHORIZED_OVERRIDE': 'Approved override applied.',
    'BELOW_APPROVED_PRICE': 'Below approved price. An override is required before this reduction is authorized.',
    'APPROVAL_PENDING': 'Override approval is pending. Submission is not approval.',
    'APPROVAL_REJECTED': 'The override was rejected. The reduced price is not authorized.',
    'APPROVAL_EXPIRED': 'The override is expired. The reduced price is not authorized.',
    'CONTRACT_CONFLICT': 'More than one approved contract matches. No price was selected.',
    'CONTRACT_NOT_FOUND': 'No approved contract was found. No contract price was invented.',
    'MISSING_PRICING_EVIDENCE': 'Pricing evidence is incomplete. No contract price was invented.',
    'PRICE_ABOVE_APPROVED_RATE': 'The quoted price is above the approved rate. This is not recovered revenue.',
    'NOT_APPLICABLE': 'This line is not a contract product sale.',
    'REVIEW_REQUIRED': 'Pricing policy requires review.',
    'TECHNICAL_ERROR': 'The pricing check failed. The line was not treated as compliant.',
}


def _reference(record):
    if not record or not isinstance(record.id, int):
        return ''
    return str(record.id)


class QuotationCompliance(models.AbstractModel):
    """Read-only sales-quotation check.

    The approved price comes from the applicability resolver, quantity
    normalizer, financial normalizer, and discount evaluator. This service
    does not write the sales price, approve a request, or post an invoice.
    """

    _name = 'cpla.quotation.compliance'
    _description = 'Sales Quotation Compliance Evaluator'

    @api.model
    def evaluate_order(self, order, confirmation=False):
        order.ensure_one()
        lines = []
        for line in order.order_line:
            lines.append(self.evaluate_line(line, confirmation=confirmation))
        return self._summary(order, lines)

    @api.model
    def evaluate_line(self, line, confirmation=False):
        line.ensure_one()
        mode, policy, policy_readable = self._mode(line.order_id.company_id)
        kind = self._line_kind(line)
        result = self._blank(line, kind)
        result['control_mode'] = mode
        result['policy_readable'] = policy_readable
        result['policy_id'] = policy.id if policy else False
        result['policy_version'] = policy.version if policy else False
        if kind != 'product':
            result['status'] = 'NOT_APPLICABLE' if kind in (
                'section', 'note', 'down_payment', 'delivery', 'discount', 'reward',
            ) else 'REVIEW_REQUIRED'
            result['reason'] = kind
            result['message'] = PUBLIC_MESSAGE[result['status']]
            result['blocks_confirmation'] = self._blocks(mode, result)
            return result
        if not line.order_id.partner_id or not line.product_id or not line.product_uom_id:
            result['status'] = 'REVIEW_REQUIRED'
            result['reason'] = 'line_context_missing'
            result['message'] = PUBLIC_MESSAGE['REVIEW_REQUIRED']
            result['blocks_confirmation'] = self._blocks(mode, result)
            return result
        try:
            line.check_access('read')
            resolved = self.env['cpla.pricing.applicability'].resolve(
                self._request(line, confirmation=confirmation)
            )
        except AccessError:
            result['access_denied'] = True
            result['status'] = 'REVIEW_REQUIRED'
            result['reason'] = 'pricing_authority_not_readable'
            result['message'] = (
                'Contract pricing cannot be read with this access. No baseline was shown.'
            )
            result['blocks_confirmation'] = self._blocks(mode, result)
            return result
        self._apply_resolution(result, line, resolved)
        result['blocks_confirmation'] = self._blocks(mode, result)
        return result

    @api.model
    def lock_values(self, line):
        """Evidence captured for a line that is already confirmed."""
        evaluated = self.evaluate_line(line, confirmation=True)
        if evaluated['status'] == 'NOT_APPLICABLE':
            return None
        order = line.order_id
        return {
            'company_id': order.company_id.id,
            'sale_order_id': order.id,
            'sale_line_id': line.id,
            'partner_id': order.partner_id.id,
            'product_id': line.product_id.id,
            'quantity_exact': _text(_decimal(line.product_uom_qty) or _decimal('0')),
            'uom_id': line.product_uom_id.id,
            'currency_id': order.currency_id.id,
            'confirmed_at': fields.Datetime.now(),
            'pricing_date': evaluated.get('pricing_date') or False,
            'pricing_date_rule': evaluated.get('pricing_date_rule') or False,
            'pricing_date_policy_snapshot': evaluated.get('pricing_date_policy_snapshot') or False,
            'order_date_lock_candidate': bool(evaluated.get('order_date_lock_candidate')),
            'grandfathering_applied': bool(evaluated.get('grandfathering_applied')),
            'contract_id': evaluated.get('contract_id') or False,
            'version_id': evaluated.get('version_id') or False,
            'tier_id': evaluated.get('tier_id') or False,
            'quantity_basis': evaluated.get('quantity_basis') or False,
            'fx_rate_exact': evaluated.get('fx_rate_exact') or False,
            'tax_basis': evaluated.get('tax_basis') or False,
            'financial_status': evaluated.get('financial_status') or False,
            'discount_status': evaluated.get('discount_status') or False,
            'approval_id': (evaluated.get('approval_ids') or [False])[0],
            'approved_adjusted_unit_price_exact': evaluated.get('approved_adjusted_unit_price_exact') or False,
            'actual_unit_price_exact': evaluated.get('actual_unit_price_exact') or False,
            'preventive_exposure_exact': evaluated.get('preventive_exposure_exact') or False,
            'authorized_concession_extended_exact': evaluated.get('authorized_concession_extended_exact') or False,
            'compliance_status': evaluated['status'],
            'compliance_reason': evaluated.get('reason') or False,
            'control_mode': evaluated.get('control_mode') or 'unconfigured',
            'policy_id': evaluated.get('policy_id') or False,
            'policy_version': evaluated.get('policy_version') or 0,
            'line_fingerprint': line._cpla_material_signature(),
            'leakage_amount': False,
            'is_recovered_cash': False,
        }

    @api.model
    def _blank(self, line, kind):
        return {
            'line_id': line.id if isinstance(line.id, int) else False,
            'kind': kind,
            'applicable': kind == 'product',
            'status': 'REVIEW_REQUIRED',
            'reason': 'not_evaluated',
            'message': PUBLIC_MESSAGE['REVIEW_REQUIRED'],
            'access_denied': False,
            'policy_readable': True,
            'approved_adjusted_unit_price_exact': False,
            'actual_unit_price_exact': False,
            'preventive_exposure_exact': False,
            'authorized_concession_extended_exact': False,
            'gross_difference_extended_exact': False,
            'comparison_currency_id': False,
            'version_id': False,
            'contract_id': False,
            'version_reference': False,
            'contract_reference': False,
            'approval_ids': [],
            'approval_state': False,
            'control_mode': 'unconfigured',
            'blocks_confirmation': False,
            'pricing_date': False,
            'pricing_date_rule': False,
            'pricing_date_policy_snapshot': False,
            'order_date_lock_candidate': False,
            'grandfathering_applied': False,
            'tier_id': False,
            'quantity_basis': False,
            'fx_rate_exact': False,
            'tax_basis': False,
            'financial_status': False,
            'discount_status': False,
            'policy_id': False,
            'policy_version': False,
            'leakage_amount': False,
            'is_recovered_cash': False,
        }

    @api.model
    def _line_kind(self, line):
        if line.display_type in ('line_section', 'line_subsection'):
            return 'section'
        if line.display_type == 'line_note':
            return 'note'
        if line.is_downpayment:
            return 'down_payment'
        if line._is_delivery():
            return 'delivery'
        if 'reward_id' in line._fields and line.reward_id:
            return 'reward'
        if line._is_global_discount() or line._is_discount_line():
            return 'discount'
        if line.combo_item_id or line.product_type == 'combo':
            return 'combo'
        if line.is_expense:
            return 'expense'
        if line.product_id:
            return 'product'
        return 'empty'

    @api.model
    def _request(self, line, confirmation=False):
        order = line.order_id
        quantity = _text(_decimal(line.product_uom_qty) or _decimal('0'))
        effective, _reason = self._effective_unit(line)
        pricing_date = self._pricing_date(order, confirmation=confirmation)
        payload = {
            'company_id': order.company_id.id,
            'partner_id': order.partner_id.id,
            'product_id': line.product_id.id,
            'pricing_date': pricing_date,
            'quantity': quantity,
            'order_quantity': quantity,
            'quantity_uom_id': line.product_uom_id.id,
            'comparison_uom_id': line.product_uom_id.id,
            'sale_reference': _reference(order),
            'sale_line_reference': _reference(line),
        }
        if effective is not None and self._sale_tax_basis(line) == 'tax_excluded':
            payload['actual_unit_price_exact'] = _text(effective)
        return payload

    @api.model
    def _pricing_date(self, order, confirmation=False):
        if confirmation:
            return fields.Date.context_today(order)
        if order.date_order:
            return fields.Date.to_date(order.date_order)
        return fields.Date.context_today(order)

    @api.model
    def _effective_unit(self, line):
        """Odoo 19 pre-tax commercial unit: price_unit times one minus the line percent.

        The percent lives on ``discount``. A reduction already stored in
        ``price_unit`` is not subtracted again.
        """
        price = _decimal(line.price_unit)
        discount = _decimal(line.discount)
        if discount is None:
            discount = _decimal('0')
        if price is None or discount is None:
            return None, 'price_missing'
        if discount < _decimal('-100') or discount > HUNDRED:
            return None, 'discount_not_a_simple_percent'
        keep = _arithmetic('sub', _decimal('1'), _arithmetic('div', discount, HUNDRED))
        return _arithmetic('mul', price, keep), False

    @api.model
    def _sale_tax_basis(self, line):
        taxes = line.tax_ids
        if not taxes:
            return 'tax_excluded'
        if 'price_include_override' not in taxes._fields:
            return 'tax_unknown'
        modes = set(taxes.mapped('price_include_override'))
        if modes <= {'tax_excluded'}:
            return 'tax_excluded'
        return 'tax_included_or_mixed'

    @api.model
    def _mode(self, company):
        policy_model = self.env['cpla.company.policy']
        try:
            policy = policy_model.search([
                ('company_id', '=', company.id),
                ('is_current', '=', True),
            ], limit=1)
        except AccessError:
            return 'unconfigured', policy_model.browse(), False
        if not policy:
            return 'unconfigured', policy, True
        return policy.quotation_compliance_mode or 'unconfigured', policy, True

    @api.model
    def _apply_resolution(self, result, line, resolved):
        result['pricing_date'] = resolved.get('pricing_date') or self._request(line).get('pricing_date')
        result['pricing_date_rule'] = resolved.get('pricing_date_rule') or False
        result['grandfathering_applied'] = bool(resolved.get('grandfathering_applied'))
        result['version_id'] = resolved.get('version_id') or False
        result['contract_id'] = resolved.get('contract_id') or False
        result['tier_id'] = resolved.get('tier_id') or False
        result['quantity_basis'] = resolved.get('quantity_basis') or False
        result['fx_rate_exact'] = resolved.get('fx_rate_exact') or False
        result['tax_basis'] = resolved.get('tax_basis') or False
        result['financial_status'] = resolved.get('financial_status') or False
        result['discount_status'] = resolved.get('discount_status') or False
        result['comparison_currency_id'] = resolved.get('comparison_currency_id') or False
        result['approval_ids'] = list(resolved.get('approval_ids') or [])
        version = self.env['cpla.customer.contract.version'].browse(result['version_id']).exists()
        if version:
            result['version_reference'] = version.reference
            result['contract_reference'] = version.contract_id.reference
            result['pricing_date_policy_snapshot'] = version.pricing_date_policy_snapshot or False
            result['order_date_lock_candidate'] = (
                version.pricing_date_policy_snapshot == 'order_confirmation'
            )
        resolver_status = resolved.get('status')
        if resolver_status == 'CONFLICT_REVIEW_REQUIRED':
            self._set_status(result, 'CONTRACT_CONFLICT', resolved.get('reason_code'))
            return
        if resolver_status == 'NO_APPLICABLE_CONTRACT':
            self._set_status(result, 'CONTRACT_NOT_FOUND', resolved.get('reason_code'))
            return
        if resolver_status != 'MATCHED_AUTHORITATIVE':
            self._set_unmatched(result, resolved)
            return
        if self._sale_tax_basis(line) != 'tax_excluded':
            self._set_status(result, 'REVIEW_REQUIRED', 'quotation_tax_not_compared')
            return
        financial = resolved.get('financial_status')
        if financial == 'COMPANY_ACCESS_DENIED':
            result['access_denied'] = True
            self._clear_prices(result)
            self._set_status(result, 'TECHNICAL_ERROR', 'company_mismatch')
            return
        if financial not in SUCCESS_FINANCIAL:
            self._set_status(result, 'MISSING_PRICING_EVIDENCE', resolved.get('financial_reason') or financial)
            return
        comparison_currency = resolved.get('comparison_currency_id') or False
        order_currency = line.order_id.currency_id.id
        if comparison_currency and comparison_currency != order_currency:
            self._clear_prices(result)
            self._set_status(result, 'REVIEW_REQUIRED', 'quotation_currency_not_comparison_currency')
            return
        discount_status = resolved.get('discount_status')
        if discount_status not in AUTHORITATIVE:
            self._set_discount_block(result, resolved)
            return
        adjusted = _decimal(resolved.get('approved_adjusted_unit_price_exact'))
        effective, price_reason = self._effective_unit(line)
        if adjusted is None or adjusted <= 0 or effective is None:
            self._set_status(result, 'MISSING_PRICING_EVIDENCE', price_reason or 'adjusted_price_missing')
            return
        result['approved_adjusted_unit_price_exact'] = _text(adjusted)
        result['actual_unit_price_exact'] = _text(effective)
        result['authorized_concession_extended_exact'] = resolved.get(
            'authorized_concession_extended_exact'
        ) or False
        result['gross_difference_extended_exact'] = resolved.get(
            'gross_difference_extended_exact'
        ) or False
        gap = _arithmetic('sub', adjusted, effective)
        quantity = _decimal(line.product_uom_qty)
        if gap > 0 and quantity is not None and quantity > 0:
            exposure = resolved.get('potential_unauthorized_extended_exact')
            result['preventive_exposure_exact'] = exposure or _text(
                _arithmetic('mul', gap, quantity)
            )
        if gap == 0 and discount_status == 'APPROVED_OVERRIDE_APPLICABLE':
            self._set_status(result, 'COMPLIANT_AUTHORIZED_OVERRIDE', 'transaction_override')
        elif gap == 0:
            self._set_status(result, 'COMPLIANT', 'price_matches_approved_baseline')
        elif gap < 0:
            self._set_status(result, 'PRICE_ABOVE_APPROVED_RATE', 'quoted_above_approved_rate')
            result['preventive_exposure_exact'] = False
        else:
            self._set_reduction_status(result, line, resolved)
        result['leakage_amount'] = False
        result['is_recovered_cash'] = False

    @api.model
    def _set_unmatched(self, result, resolved):
        reason = resolved.get('reason_code') or resolved.get('status') or 'review'
        evidence = {
            'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
            'INVALID_CURRENCY_CONTEXT',
            'MISSING_HISTORICAL_CONVERSION',
        }
        if resolved.get('status') in evidence or resolved.get('financial_status') in evidence:
            self._set_status(result, 'MISSING_PRICING_EVIDENCE', reason)
            return
        self._set_status(result, 'REVIEW_REQUIRED', reason)

    @api.model
    def _set_discount_block(self, result, resolved):
        status = resolved.get('discount_status')
        reason = resolved.get('discount_reason') or status
        if status == 'DISCOUNT_APPROVAL_PENDING':
            self._set_status(result, 'APPROVAL_PENDING', reason)
        elif status == 'DISCOUNT_APPROVAL_REJECTED':
            self._set_status(result, 'APPROVAL_REJECTED', reason)
        elif status == 'DISCOUNT_EXPIRED':
            self._set_status(result, 'APPROVAL_EXPIRED', reason)
        elif status == 'COMPANY_ACCESS_DENIED':
            result['access_denied'] = True
            self._clear_prices(result)
            self._set_status(result, 'TECHNICAL_ERROR', 'company_mismatch')
        elif status == 'DISCOUNT_STACKING_REVIEW_REQUIRED':
            self._set_status(result, 'REVIEW_REQUIRED', reason)
        else:
            self._set_status(result, 'REVIEW_REQUIRED', reason)

    @api.model
    def _set_reduction_status(self, result, line, resolved):
        order = line.order_id
        approvals = self.env['cpla.discount.approval']
        if isinstance(line.id, int) and isinstance(order.id, int):
            approvals = approvals.search([
                ('company_id', '=', order.company_id.id),
                ('partner_id', '=', order.partner_id.id),
                ('product_id', '=', line.product_id.id),
                ('sale_reference', '=', str(order.id)),
                ('sale_line_reference', '=', str(line.id)),
                ('request_kind', '=', 'transaction_override'),
                ('state', 'in', ('submitted', 'approved', 'rejected')),
            ])
        result['approval_ids'] = approvals.ids or result['approval_ids']
        if approvals.filtered(lambda item: item.state == 'submitted'):
            result['approval_state'] = 'submitted'
            self._set_status(result, 'APPROVAL_PENDING', 'override_pending')
            return
        if resolved.get('discount_status') == 'DISCOUNT_EXPIRED' or (
            approvals and not approvals.filtered(lambda item: item.state == 'approved')
            and resolved.get('discount_reason') == 'override_expired'
        ):
            result['approval_state'] = 'expired'
            self._set_status(result, 'APPROVAL_EXPIRED', 'override_expired')
            return
        rejected = approvals.filtered(lambda item: item.state == 'rejected')
        approved = approvals.filtered(lambda item: item.state == 'approved')
        if rejected and not approved:
            result['approval_state'] = 'rejected'
            self._set_status(result, 'APPROVAL_REJECTED', 'override_rejected')
            return
        quantity = _decimal(line.product_uom_qty)
        covered = approved.filtered(
            lambda item: (
                _decimal(item.quantity_exact) is not None
                and quantity is not None
                and quantity <= _decimal(item.quantity_exact)
            )
        )
        if approved and not covered or resolved.get('discount_reason') == 'override_quantity_not_covered':
            result['approval_state'] = 'quantity_not_covered'
            self._set_status(result, 'REVIEW_REQUIRED', 'override_quantity_not_covered')
            return
        result['approval_state'] = 'not_authorized'
        self._set_status(result, 'BELOW_APPROVED_PRICE', 'below_approved_adjusted_price')

    @api.model
    def _set_status(self, result, status, reason):
        result['status'] = status
        result['reason'] = reason or status
        result['message'] = PUBLIC_MESSAGE[status]
        result['leakage_amount'] = False
        result['is_recovered_cash'] = False

    @api.model
    def _clear_prices(self, result):
        result['approved_adjusted_unit_price_exact'] = False
        result['actual_unit_price_exact'] = False
        result['preventive_exposure_exact'] = False
        result['authorized_concession_extended_exact'] = False
        result['gross_difference_extended_exact'] = False

    @api.model
    def _blocks(self, mode, result):
        status = result['status']
        if not result.get('policy_readable'):
            return status not in ('NOT_APPLICABLE',)
        if result.get('access_denied'):
            return mode in ('block', 'approval_required')
        if status in OPEN_STATUSES:
            return False
        if status == 'CONTRACT_NOT_FOUND':
            return mode == 'block'
        if mode in ('disabled', 'warning'):
            return False
        if mode in ('unconfigured', 'approval_required', 'block'):
            return status in PRICE_PROBLEMS or status in UNCERTAIN
        return True

    @api.model
    def _summary(self, order, lines):
        def count(status):
            return len([line for line in lines if line['status'] == status])

        commercial = [line for line in lines if line['status'] != 'NOT_APPLICABLE']
        blocking = [line for line in lines if line['blocks_confirmation']]
        currencies = {
            line['comparison_currency_id']
            for line in lines
            if line.get('preventive_exposure_exact') and line.get('comparison_currency_id')
        }
        exposure = _decimal('0')
        valued = False
        for line in lines:
            amount = _decimal(line.get('preventive_exposure_exact'))
            if amount is None:
                continue
            valued = True
            exposure = _arithmetic('add', exposure, amount)
        incomplete = any(
            line['applicable'] and line['status'] in UNCERTAIN
            for line in lines
        )
        headline_pool = commercial or lines
        headline = 'NOT_APPLICABLE'
        for status in (
            'TECHNICAL_ERROR', 'CONTRACT_CONFLICT', 'MISSING_PRICING_EVIDENCE',
            'REVIEW_REQUIRED', 'APPROVAL_REJECTED', 'APPROVAL_EXPIRED',
            'APPROVAL_PENDING', 'BELOW_APPROVED_PRICE', 'CONTRACT_NOT_FOUND',
            'PRICE_ABOVE_APPROVED_RATE', 'COMPLIANT_AUTHORIZED_OVERRIDE', 'COMPLIANT',
        ):
            if any(line['status'] == status for line in headline_pool):
                headline = status
                break
        mode = lines[0]['control_mode'] if lines else self._mode(order.company_id)[0]
        return {
            'status': headline,
            'message': PUBLIC_MESSAGE.get(headline, PUBLIC_MESSAGE['REVIEW_REQUIRED']),
            'control_mode': mode,
            'eligible_count': len(commercial),
            'compliant_count': count('COMPLIANT'),
            'override_count': count('COMPLIANT_AUTHORIZED_OVERRIDE'),
            'below_count': count('BELOW_APPROVED_PRICE'),
            'missing_count': count('CONTRACT_NOT_FOUND'),
            'review_count': count('REVIEW_REQUIRED') + count('MISSING_PRICING_EVIDENCE') + count('TECHNICAL_ERROR'),
            'pending_count': count('APPROVAL_PENDING'),
            'blocking_count': len(blocking),
            'preventive_exposure_exact': _text(exposure) if valued and len(currencies) <= 1 else False,
            'exposure_currency_id': currencies.pop() if len(currencies) == 1 else False,
            'exposure_complete': bool(valued) and not incomplete and len(currencies) <= 1,
            'leakage_amount': False,
            'is_recovered_cash': False,
            'lines': lines,
        }

    @api.model
    def _sees_prices(self):
        user = self.env.user
        if self.env.su or user._is_superuser():
            return True
        return any(user.has_group(group) for group in READ_GROUPS)


class SalePriceLock(models.Model):
    """Pricing basis stored when a sales order is confirmed.

    Later contract prices do not rewrite this row. A material change flags
    revalidation and leaves the confirmed amounts in place. This is not an
    invoice allocation and it is not recovered cash.
    """

    _name = 'cpla.sale.price.lock'
    _description = 'Confirmed Sales Order Price Lock'
    _order = 'id desc'
    _check_company_auto = True

    _sale_line_unique = models.Constraint(
        'UNIQUE(sale_line_id)',
        'This confirmed line already has pricing evidence.',
    )

    company_id = fields.Many2one(
        'res.company', required=True, index=True, readonly=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order', required=True, ondelete='restrict', index=True, readonly=True,
        check_company=True,
    )
    sale_line_id = fields.Many2one(
        'sale.order.line', required=True, ondelete='restrict', index=True, readonly=True,
    )
    partner_id = fields.Many2one('res.partner', readonly=True, index=True)
    product_id = fields.Many2one('product.product', readonly=True, index=True)
    quantity_exact = fields.Char(readonly=True)
    uom_id = fields.Many2one('uom.uom', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    confirmed_at = fields.Datetime(readonly=True)
    pricing_date = fields.Date(readonly=True)
    pricing_date_rule = fields.Char(readonly=True)
    pricing_date_policy_snapshot = fields.Char(
        readonly=True,
        help='Candidate copied from the approved version. It is not a separate pricing-date approval.',
    )
    order_date_lock_candidate = fields.Boolean(
        readonly=True,
        help='True only when the approved version snapshot says order confirmation. Invoice-date evidence stays false.',
    )
    grandfathering_applied = fields.Boolean(readonly=True)
    contract_id = fields.Many2one('cpla.customer.contract', readonly=True)
    version_id = fields.Many2one('cpla.customer.contract.version', readonly=True)
    tier_id = fields.Many2one('cpla.customer.contract.version.tier', readonly=True)
    quantity_basis = fields.Char(readonly=True)
    fx_rate_exact = fields.Char(readonly=True)
    tax_basis = fields.Char(readonly=True)
    financial_status = fields.Char(readonly=True)
    discount_status = fields.Char(readonly=True)
    approval_id = fields.Many2one('cpla.discount.approval', readonly=True)
    approved_adjusted_unit_price_exact = fields.Char(readonly=True)
    actual_unit_price_exact = fields.Char(readonly=True)
    preventive_exposure_exact = fields.Char(
        readonly=True,
        help='Quote-stage preventive exposure. Not recovered cash and not an invoice leakage amount.',
    )
    authorized_concession_extended_exact = fields.Char(readonly=True)
    compliance_status = fields.Char(readonly=True, index=True)
    compliance_reason = fields.Char(readonly=True)
    control_mode = fields.Char(readonly=True)
    policy_id = fields.Many2one('cpla.company.policy', readonly=True)
    policy_version = fields.Integer(readonly=True)
    line_fingerprint = fields.Char(readonly=True)
    revalidation_required = fields.Boolean(readonly=True)
    revalidation_reason = fields.Char(readonly=True)
    leakage_amount = fields.Boolean(readonly=True, default=False)
    is_recovered_cash = fields.Boolean(readonly=True, default=False)

    @api.model_create_multi
    def create(self, vals_list):
        kept = self.browse()
        evaluator = self.env['cpla.quotation.compliance']
        for vals in vals_list:
            line = self.env['sale.order.line'].browse(vals.get('sale_line_id')).exists()
            if not line or line.order_id.state not in ('sale', 'done'):
                raise UserError(self.env._(
                    'Pricing evidence is stored only after the sales order is confirmed.'
                ))
            line.check_access('read')
            if line.order_id.company_id not in self.env.companies and not self.env.su:
                raise AccessError(self.env._(
                    'You cannot store pricing evidence for another company.'
                ))
            existing = self.search([('sale_line_id', '=', line.id)], limit=1)
            if existing:
                kept |= existing
                continue
            payload = evaluator.lock_values(line)
            if not payload:
                continue
            kept |= models.Model.create(self, [payload])
        return kept

    def write(self, vals):
        allowed = {'revalidation_required', 'revalidation_reason'}
        if set(vals) - allowed:
            raise UserError(self.env._(
                'Confirmed pricing evidence cannot be overwritten.'
            ))
        if vals.get('revalidation_required') is False:
            for lock in self:
                if lock.sale_line_id._cpla_material_signature() != lock.line_fingerprint:
                    raise UserError(self.env._(
                        'Revalidation stays required while the confirmed line differs from the stored evidence.'
                    ))
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._(
            'Confirmed pricing evidence cannot be deleted.'
        ))


class DiscountApprovalSaleLink(models.Model):
    _inherit = 'cpla.discount.approval'

    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order', index=True, check_company=True,
    )
    sale_line_id = fields.Many2one(
        'sale.order.line', string='Sales Order Line', index=True,
    )

    def _check_company_links(self):
        super()._check_company_links()
        order = self.sale_order_id
        line = self.sale_line_id
        if order and order.company_id != self.company_id:
            raise UserError(self.env._(
                'The sales order belongs to another company. The request was not saved.'
            ))
        if line and line.order_id.company_id != self.company_id:
            raise UserError(self.env._(
                'The sales order line belongs to another company. The request was not saved.'
            ))
        if order and line and line.order_id != order:
            raise UserError(self.env._(
                'The sales order line is not on that sales order. The request was not saved.'
            ))


class QuotationOverrideRequest(models.TransientModel):
    _name = 'cpla.quotation.override.request'
    _description = 'Quotation Price Override Request'

    sale_line_id = fields.Many2one(
        'sale.order.line', required=True, check_company=False,
    )
    company_id = fields.Many2one(
        'res.company', related='sale_line_id.order_id.company_id', store=True, readonly=True,
    )
    reason = fields.Char(required=True)
    evidence_reference = fields.Char(required=True, string='Evidence reference')

    def action_create_request(self):
        self.ensure_one()
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to request a price override.'
            ))
        line = self.sale_line_id
        line.check_access('read')
        if not isinstance(line.id, int):
            raise UserError(self.env._(
                'Save the quotation before requesting an override.'
            ))
        evaluated = self.env['cpla.quotation.compliance'].evaluate_line(line)
        if not evaluated.get('version_id'):
            raise UserError(self.env._(
                'No approved contract version is available for this line. An override was not created.'
            ))
        if evaluated['status'] in ('COMPLIANT', 'COMPLIANT_AUTHORIZED_OVERRIDE', 'NOT_APPLICABLE'):
            raise UserError(self.env._(
                'This line does not need a new price override.'
            ))
        if not evaluated.get('actual_unit_price_exact'):
            raise UserError(self.env._(
                'The quoted price is not comparable yet. An override was not created.'
            ))
        existing = self.env['cpla.discount.approval'].search([
            ('company_id', '=', line.order_id.company_id.id),
            ('sale_line_reference', '=', str(line.id)),
            ('state', 'in', ('draft', 'submitted', 'approved')),
        ], limit=1)
        if existing:
            raise UserError(self.env._(
                'A request already exists for this line. It was not duplicated and it was not approved.'
            ))
        version = self.env['cpla.customer.contract.version'].browse(evaluated['version_id'])
        approval = self.env['cpla.discount.approval'].create({
            'company_id': line.order_id.company_id.id,
            'request_kind': 'transaction_override',
            'version_id': version.id,
            'partner_id': line.order_id.partner_id.id,
            'product_id': line.product_id.id,
            'proposed_price_exact': evaluated['actual_unit_price_exact'],
            'currency_id': line.order_id.currency_id.id,
            'uom_id': line.product_uom_id.id,
            'quantity_exact': _text(_decimal(line.product_uom_qty)),
            'quantity_uom_id': line.product_uom_id.id,
            'sale_reference': str(line.order_id.id),
            'sale_line_reference': str(line.id),
            'sale_order_id': line.order_id.id,
            'sale_line_id': line.id,
            'reason': self.reason,
            'evidence_reference': self.evidence_reference,
            'effective_from': fields.Date.context_today(self),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Price override request'),
            'res_model': 'cpla.discount.approval',
            'res_id': approval.id,
            'view_mode': 'form',
            'target': 'current',
        }


class SaleOrderQuotationCompliance(models.Model):
    _inherit = 'sale.order'

    cpla_compliance_status = fields.Char(
        string='Contract compliance', compute='_compute_cpla_summary',
    )
    cpla_compliance_message = fields.Char(
        string='Compliance message', compute='_compute_cpla_summary',
    )
    cpla_control_mode = fields.Char(
        string='Compliance mode', compute='_compute_cpla_summary',
    )
    cpla_eligible_count = fields.Integer(compute='_compute_cpla_summary')
    cpla_compliant_count = fields.Integer(compute='_compute_cpla_summary')
    cpla_override_count = fields.Integer(compute='_compute_cpla_summary')
    cpla_below_count = fields.Integer(compute='_compute_cpla_summary')
    cpla_missing_count = fields.Integer(compute='_compute_cpla_summary')
    cpla_review_count = fields.Integer(compute='_compute_cpla_summary')
    cpla_pending_count = fields.Integer(compute='_compute_cpla_summary')
    cpla_blocking_count = fields.Integer(compute='_compute_cpla_summary')
    cpla_preventive_exposure_exact = fields.Char(
        string='Preventive exposure',
        compute='_compute_cpla_summary',
        help='Potential quote-stage exposure. Not recovered cash. Blank when this user cannot read contract prices.',
    )
    cpla_exposure_complete = fields.Boolean(compute='_compute_cpla_summary')
    cpla_price_lock_count = fields.Integer(compute='_compute_cpla_price_lock_count')

    @api.depends(
        'company_id', 'partner_id', 'currency_id', 'pricelist_id', 'date_order', 'state',
        'order_line.product_id', 'order_line.product_uom_qty', 'order_line.product_uom_id',
        'order_line.price_unit', 'order_line.discount', 'order_line.tax_ids',
        'order_line.display_type', 'order_line.is_downpayment',
    )
    def _compute_cpla_summary(self):
        service = self.env['cpla.quotation.compliance']
        for order in self:
            if not order.company_id:
                order._cpla_assign_summary(service._summary(order, []))
                continue
            summary = service.evaluate_order(order)
            order._cpla_assign_summary(summary)

    def _cpla_assign_summary(self, summary):
        sees = self.env['cpla.quotation.compliance']._sees_prices()
        self.cpla_compliance_status = summary['status']
        self.cpla_compliance_message = summary['message']
        self.cpla_control_mode = summary['control_mode']
        self.cpla_eligible_count = summary['eligible_count']
        self.cpla_compliant_count = summary['compliant_count']
        self.cpla_override_count = summary['override_count']
        self.cpla_below_count = summary['below_count']
        self.cpla_missing_count = summary['missing_count']
        self.cpla_review_count = summary['review_count']
        self.cpla_pending_count = summary['pending_count']
        self.cpla_blocking_count = summary['blocking_count']
        self.cpla_preventive_exposure_exact = (
            summary['preventive_exposure_exact'] or False
        ) if sees else False
        self.cpla_exposure_complete = summary['exposure_complete'] if sees else False

    def _compute_cpla_price_lock_count(self):
        counts = {}
        if self.ids:
            locks = self.env['cpla.sale.price.lock'].search([
                ('sale_order_id', 'in', self.ids),
            ])
            for lock in locks:
                counts[lock.sale_order_id.id] = counts.get(lock.sale_order_id.id, 0) + 1
        for order in self:
            order.cpla_price_lock_count = counts.get(order.id, 0)

    def write(self, vals):
        watched = set(vals) & {'partner_id', 'pricelist_id', 'company_id'}
        before = {}
        if watched:
            for line in self.order_line.filtered(
                lambda item: item.state in ('sale', 'done') and not item.display_type
            ):
                before[line.id] = line._cpla_material_signature()
        result = super().write(vals)
        if before:
            self.order_line._cpla_flag_revalidation(before)
        return result

    def action_confirm(self):
        """Server-side price gate. A context flag cannot skip it."""
        for order in self:
            order._cpla_check_confirmation()
        result = super().action_confirm()
        for order in self:
            order._cpla_store_price_locks()
        return result

    def _cpla_check_confirmation(self):
        self.ensure_one()
        self.check_access('read')
        scoped = self.with_company(self.company_id)
        if scoped.company_id not in scoped.env.companies and not scoped.env.su:
            raise AccessError(self.env._(
                'You cannot confirm a sales order for another company.'
            ))
        summary = scoped.env['cpla.quotation.compliance'].evaluate_order(
            scoped, confirmation=True,
        )
        blocked = [line for line in summary['lines'] if line['blocks_confirmation']]
        if not blocked:
            return True
        sees_prices = self.env['cpla.quotation.compliance']._sees_prices()
        parts = []
        for line in blocked:
            if sees_prices and line.get('preventive_exposure_exact'):
                parts.append(self.env._(
                    '%(message)s Preventive exposure %(amount)s. This is not recovered cash.',
                    message=line['message'],
                    amount=line['preventive_exposure_exact'],
                ))
            else:
                parts.append(line['message'])
        raise UserError(self.env._(
            'This sales order was not confirmed.\n%(details)s',
            details='\n'.join(parts),
        ))

    def _cpla_store_price_locks(self):
        self.ensure_one()
        if self.state not in ('sale', 'done'):
            return
        scoped = self.with_company(self.company_id)
        locks = scoped.env['cpla.sale.price.lock']
        for line in scoped.order_line:
            if not isinstance(line.id, int):
                continue
            if locks.search_count([('sale_line_id', '=', line.id)]):
                continue
            locks.create({'sale_line_id': line.id})

    def action_cpla_recheck(self):
        self.ensure_one()
        summary = self.env['cpla.quotation.compliance'].evaluate_order(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Contract compliance'),
                'message': summary['message'],
                'type': 'warning' if summary['blocking_count'] else 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_cpla_view_price_locks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Confirmed pricing evidence'),
            'res_model': 'cpla.sale.price.lock',
            'view_mode': 'list,form',
            'domain': [
                ('sale_order_id', '=', self.id),
                ('company_id', '=', self.company_id.id),
            ],
        }


class SaleOrderLineQuotationCompliance(models.Model):
    _inherit = 'sale.order.line'

    cpla_compliance_status = fields.Char(
        string='Contract compliance', compute='_compute_cpla_line',
    )
    cpla_compliance_message = fields.Char(
        string='Compliance message', compute='_compute_cpla_line',
    )
    cpla_approved_price_exact = fields.Char(
        string='Approved adjusted price',
        compute='_compute_cpla_line',
    )
    cpla_actual_price_exact = fields.Char(
        string='Effective quoted price',
        compute='_compute_cpla_line',
    )
    cpla_preventive_exposure_exact = fields.Char(
        string='Preventive exposure',
        compute='_compute_cpla_line',
    )
    cpla_contract_reference = fields.Char(
        string='Contract',
        compute='_compute_cpla_line',
    )
    cpla_version_reference = fields.Char(
        string='Contract version',
        compute='_compute_cpla_line',
    )
    cpla_approval_state = fields.Char(
        string='Override status', compute='_compute_cpla_line',
    )

    @api.depends(
        'order_id.company_id', 'order_id.partner_id', 'order_id.currency_id',
        'order_id.date_order', 'order_id.state',
        'product_id', 'product_uom_qty', 'product_uom_id', 'price_unit',
        'discount', 'tax_ids', 'display_type', 'is_downpayment', 'is_expense',
    )
    def _compute_cpla_line(self):
        service = self.env['cpla.quotation.compliance']
        for line in self:
            if not line.order_id or not line.order_id.company_id:
                line._cpla_assign_line(service._blank(line, 'empty'))
                continue
            line._cpla_assign_line(service.evaluate_line(line))

    def _cpla_assign_line(self, result):
        sees = self.env['cpla.quotation.compliance']._sees_prices()
        self.cpla_compliance_status = result['status']
        self.cpla_compliance_message = result['message']
        self.cpla_approved_price_exact = (
            result.get('approved_adjusted_unit_price_exact') or False
        ) if sees else False
        self.cpla_actual_price_exact = (
            result.get('actual_unit_price_exact') or False
        ) if sees else False
        self.cpla_preventive_exposure_exact = (
            result.get('preventive_exposure_exact') or False
        ) if sees else False
        self.cpla_contract_reference = (
            result.get('contract_reference') or False
        ) if sees else False
        self.cpla_version_reference = (
            result.get('version_reference') or False
        ) if sees else False
        self.cpla_approval_state = result.get('approval_state') or result.get('discount_status') or False

    def _cpla_material_signature(self):
        self.ensure_one()
        order = self.order_id
        effective, _reason = self.env['cpla.quotation.compliance']._effective_unit(self)
        taxes = ','.join(str(tax_id) for tax_id in sorted(self.tax_ids.ids))
        return '|'.join((
            str(order.company_id.id or 0),
            str(order.partner_id.id or 0),
            str(self.product_id.id or 0),
            _text(_decimal(self.product_uom_qty) or _decimal('0')),
            str(self.product_uom_id.id or 0),
            str(order.currency_id.id or 0),
            taxes,
            _text(effective) if effective is not None else '',
            _text(_decimal(self.discount) or _decimal('0')),
        ))

    def _cpla_flag_revalidation(self, before):
        locks = self.env['cpla.sale.price.lock'].search([
            ('sale_line_id', 'in', list(before)),
        ])
        for lock in locks:
            line = lock.sale_line_id
            if not line or line._cpla_material_signature() == before.get(line.id):
                continue
            if lock.revalidation_required:
                continue
            lock.write({
                'revalidation_required': True,
                'revalidation_reason': 'material_change_after_confirmation',
            })

    def write(self, vals):
        watched = set(vals) & {
            'product_id', 'product_uom_qty', 'product_uom_id',
            'price_unit', 'discount', 'tax_ids',
        }
        before = {}
        if watched:
            for line in self.filtered(lambda item: item.state in ('sale', 'done') and not item.display_type):
                before[line.id] = line._cpla_material_signature()
        result = super().write(vals)
        if before:
            self._cpla_flag_revalidation(before)
        return result

    def action_cpla_request_override(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Request price override'),
            'res_model': 'cpla.quotation.override.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_line_id': self.id},
        }

    def action_cpla_view_approvals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Price overrides'),
            'res_model': 'cpla.discount.approval',
            'view_mode': 'list,form',
            'domain': [
                ('company_id', '=', self.order_id.company_id.id),
                ('sale_line_reference', '=', str(self.id) if isinstance(self.id, int) else ''),
            ],
        }
