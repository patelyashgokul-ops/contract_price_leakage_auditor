import hashlib
import json
from decimal import Decimal, InvalidOperation

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MODULE = 'contract_price_leakage_auditor'
USER_GROUP = f'{MODULE}.group_contract_user'

TIER_METHODS = [
    ('none', 'Standalone price'),
    ('full_volume', 'Full-volume tier'),
    ('graduated', 'Graduated tier'),
]
QUANTITY_BASES = [
    ('unconfigured', 'Not configured'),
    ('sales_order', 'Sales order quantity'),
    ('invoice_line', 'Invoice line quantity'),
    ('delivery', 'Delivery quantity'),
    ('cumulative', 'Contract-period cumulative volume'),
]
RETURN_POLICIES = [
    ('unconfigured', 'Not configured'),
    ('order_tier_lock', 'Original qualifying quantity stays locked'),
    ('net_quantity', 'Net retained quantity selects the tier'),
]
APPROVED_BASES = ('sales_order', 'invoice_line', 'delivery')
BASIS_FIELD = {
    'sales_order': 'order_quantity',
    'invoice_line': 'invoice_quantity',
    'delivery': 'delivery_quantity',
}


def _missing(value):
    """Blank context only. Zero is a supplied quantity, not a missing one."""
    return value is None or value is False or value == ''


def _D(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class CustomerContractVersionTier(models.Model):
    """One quantity break on a contract version line.

    Ranges are minimum inclusive and maximum exclusive. An empty maximum
    is open-ended. Factors are captured again at approval and are the
    historical conversion evidence. The live unit record is not reread
    when an approved tier is priced.
    """

    _name = 'cpla.customer.contract.version.tier'
    _description = 'Customer Contract Version Quantity Tier'
    _order = 'min_quantity, id'
    _check_company_auto = True

    version_line_id = fields.Many2one(
        'cpla.customer.contract.version.line',
        string='Version Line',
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    version_id = fields.Many2one(
        'cpla.customer.contract.version',
        related='version_line_id.version_id',
        store=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='version_line_id.company_id',
        store=True,
        index=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        related='version_line_id.product_id',
        store=True,
        index=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='version_line_id.currency_id',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    min_quantity = fields.Float(
        string='Minimum Quantity',
        required=True,
        digits=0,
        help='Inclusive start of the tier. The range is [minimum, maximum).',
    )
    has_maximum = fields.Boolean(
        string='Has Maximum',
        help='When this is clear, the tier has no upper bound.',
    )
    max_quantity = fields.Float(
        string='Maximum Quantity',
        digits=0,
        help='Exclusive end of the tier. Quantity equal to this value falls in the next tier.',
    )
    quantity_uom_id = fields.Many2one(
        'uom.uom',
        string='Quantity Unit',
        required=True,
        ondelete='restrict',
        index=True,
    )
    price_unit = fields.Monetary(
        string='Tier Price',
        currency_field='currency_id',
        required=True,
    )
    pricing_uom_id = fields.Many2one(
        'uom.uom',
        string='Pricing Unit',
        required=True,
        ondelete='restrict',
        index=True,
    )
    quantity_uom_factor = fields.Float(
        string='Quantity Unit Factor',
        digits=0,
        help='Absolute factor captured for the quantity unit. Approved pricing does not reread the live unit.',
    )
    pricing_uom_factor = fields.Float(
        string='Pricing Unit Factor',
        digits=0,
    )
    product_uom_factor = fields.Float(
        string='Product Unit Factor',
        digits=0,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Product Unit Snapshot',
        ondelete='restrict',
    )
    reference_uom_id = fields.Many2one(
        'uom.uom',
        string='Reference Unit Snapshot',
        ondelete='restrict',
    )
    factor_captured_at = fields.Datetime(
        string='Factor Captured At',
    )

    @api.depends(
        'min_quantity', 'has_maximum', 'max_quantity',
        'quantity_uom_id', 'price_unit',
    )
    def _compute_display_name(self):
        for tier in self:
            end = 'open' if not tier.has_maximum else ('%s' % tier.max_quantity)
            unit = tier.quantity_uom_id.display_name or ''
            tier.display_name = '[%s, %s) %s' % (tier.min_quantity, end, unit)

    def _draft_line(self, line):
        if not line:
            raise ValidationError(self.env._('The quantity tier needs its version line.'))
        line.check_access('write')
        if line.version_id.state != 'draft':
            raise UserError(self.env._(
                'An approved quantity tier cannot be edited. The historical tier stays unchanged.'
            ))
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to edit quantity tiers.'
            ))
        return line

    def _factor_values(self, capture=False):
        self.ensure_one()
        quantity_uom = self.quantity_uom_id
        pricing_uom = self.pricing_uom_id
        product_uom = self.product_id.uom_id
        values = {
            'quantity_uom_factor': quantity_uom.factor if quantity_uom else 0.0,
            'pricing_uom_factor': pricing_uom.factor if pricing_uom else 0.0,
            'product_uom_factor': product_uom.factor if product_uom else 0.0,
            'product_uom_id': product_uom.id if product_uom else False,
            'reference_uom_id': self._root_uom(quantity_uom).id if quantity_uom else False,
        }
        if capture:
            values['factor_captured_at'] = fields.Datetime.now()
        return values

    @api.model
    def _root_uom(self, uom):
        seen = set()
        while uom.relative_uom_id and uom.id not in seen:
            seen.add(uom.id)
            uom = uom.relative_uom_id
        return uom

    def _values_for_line(self, line):
        self.ensure_one()
        return {
            'version_line_id': line.id,
            'sequence': self.sequence,
            'min_quantity': self.min_quantity,
            'has_maximum': self.has_maximum,
            'max_quantity': self.max_quantity if self.has_maximum else 0.0,
            'quantity_uom_id': self.quantity_uom_id.id,
            'price_unit': self.price_unit,
            'pricing_uom_id': self.pricing_uom_id.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            for forged in (
                'quantity_uom_factor', 'pricing_uom_factor', 'product_uom_factor',
                'product_uom_id', 'reference_uom_id', 'factor_captured_at',
                'company_id', 'version_id', 'product_id', 'currency_id',
            ):
                values.pop(forged, None)
            line = self.env['cpla.customer.contract.version.line'].browse(
                values.get('version_line_id')
            )
            if not values.get('version_line_id'):
                raise ValidationError(self.env._('The quantity tier needs its version line.'))
            line.check_access('write')
            line = line.exists()
            if not line:
                raise AccessError(self.env._(
                    'You are not allowed to edit quantity tiers.'
                ))
            line = self._draft_line(line)
            line.lock_for_update()
            if line.tier_ids:
                line.tier_ids.lock_for_update()
            prepared.append(values)
        records = super().create(prepared)
        for record in records:
            super(CustomerContractVersionTier, record).write(record._factor_values())
        records._check_tier_shape()
        return records

    def write(self, vals):
        vals = dict(vals)
        for forged in (
            'quantity_uom_factor', 'pricing_uom_factor', 'product_uom_factor',
            'product_uom_id', 'reference_uom_id', 'factor_captured_at',
            'company_id', 'version_id', 'product_id', 'currency_id',
        ):
            vals.pop(forged, None)
        if 'version_line_id' in vals and any(
            vals['version_line_id'] != tier.version_line_id.id for tier in self
        ):
            raise UserError(self.env._(
                'A quantity tier cannot be moved to another version line.'
            ))
        for tier in self:
            self._draft_line(tier.version_line_id)
            tier.version_line_id.lock_for_update()
        written = super().write(vals)
        for tier in self:
            super(CustomerContractVersionTier, tier).write(tier._factor_values())
        self._check_tier_shape()
        return written

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        for tier in self:
            self._draft_line(tier.version_line_id)
        lines = self.version_line_id
        removed = super().unlink()
        lines.tier_ids._check_tier_shape()
        return removed

    def _check_tier_shape(self):
        for tier in self:
            issue = tier._shape_issue()
            if issue:
                raise ValidationError(issue)
        lines = self.version_line_id
        for line in lines:
            issue = line._tier_overlap_issue()
            if issue:
                raise ValidationError(issue)

    def _shape_issue(self):
        self.ensure_one()
        if self.price_unit < 0:
            return self.env._('A negative tier price is not allowed.')
        if self.currency_id and self.currency_id.is_zero(self.price_unit):
            return self.env._(
                'A zero tier price is not an approved selling price.'
            )
        try:
            minimum = _D(self.min_quantity)
        except InvalidOperation:
            return self.env._('The minimum quantity is not a valid number.')
        if minimum < 0:
            return self.env._('The minimum quantity cannot be negative.')
        if self.has_maximum:
            try:
                maximum = _D(self.max_quantity)
            except InvalidOperation:
                return self.env._('The maximum quantity is not a valid number.')
            if maximum <= minimum:
                return self.env._(
                    'The maximum quantity must be greater than the minimum. '
                    'The maximum is exclusive.'
                )
        product = self.product_id
        for uom, label in (
            (self.quantity_uom_id, 'quantity'),
            (self.pricing_uom_id, 'pricing'),
        ):
            issue = self._uom_text(product, uom, label)
            if issue:
                return issue
        return False

    def _uom_text(self, product, uom, label):
        if not uom or not product or not product.uom_id:
            return self.env._('The %(label)s unit is missing.', label=label)
        if not uom.active:
            return self.env._(
                'The %(label)s unit is inactive and was not activated.',
                label=label,
            )
        if uom.relative_factor is None or uom.relative_factor <= 0 or uom.factor <= 0:
            return self.env._(
                'The %(label)s unit factor must be positive. A zero or negative factor is rejected.',
                label=label,
            )
        if not uom._has_common_reference(product.uom_id):
            return self.env._(
                'The %(label)s unit is not in the same family as the product unit. No conversion was invented.',
                label=label,
            )
        other = self.env['product.template'].search([
            ('uom_ids', 'in', uom.id),
            ('id', '!=', product.product_tmpl_id.id),
        ], limit=1)
        own = product.product_tmpl_id.uom_ids
        if other and uom not in own and uom != product.uom_id:
            return self.env._(
                'That packaging unit belongs to another product. It was not used.'
            )
        return False

    def _bounds(self):
        self.ensure_one()
        factor = _D(self.quantity_uom_factor or self.quantity_uom_id.factor or 0)
        if factor <= 0:
            return None
        start = _D(self.min_quantity) * factor
        if not self.has_maximum:
            return (start, None)
        return (start, _D(self.max_quantity) * factor)

    def _same_bounds(self, other):
        return (
            self.quantity_uom_id == other.quantity_uom_id
            and _D(self.min_quantity) == _D(other.min_quantity)
            and bool(self.has_maximum) == bool(other.has_maximum)
            and (
                not self.has_maximum
                or _D(self.max_quantity) == _D(other.max_quantity)
            )
        )


class CustomerContractVersionLineQuantity(models.Model):
    _inherit = 'cpla.customer.contract.version.line'

    tier_method = fields.Selection(
        selection=TIER_METHODS,
        string='Tier Method',
        default='none',
        required=True,
        help='The method is stored on the line. It is not inferred from the number of tier rows.',
    )
    quantity_basis = fields.Selection(
        selection=QUANTITY_BASES,
        string='Quantity Basis',
        default='unconfigured',
        required=True,
        help='Contract term for this line. The company quantity candidate is not applied.',
    )
    return_policy = fields.Selection(
        selection=RETURN_POLICIES,
        string='Return Quantity Policy',
        default='unconfigured',
        required=True,
        help='A return does not change the tier unless this line says so.',
    )
    tier_ids = fields.One2many(
        'cpla.customer.contract.version.tier',
        'version_line_id',
        string='Quantity Tiers',
    )

    @api.model
    def _values_from_version_line(self, version, line):
        values = super()._values_from_version_line(version, line)
        values.update({
            'tier_method': line.tier_method,
            'quantity_basis': line.quantity_basis,
            'return_policy': line.return_policy,
        })
        return values

    def approval_messages(self):
        messages = super().approval_messages()
        messages.extend(self._tier_approval_messages())
        return messages

    def _tier_approval_messages(self):
        self.ensure_one()
        messages = []
        label = self.product_name or self.product_id.display_name or self.env._('A line')
        method = self.tier_method
        tiers = self.tier_ids
        if method == 'graduated':
            messages.append(self.env._(
                '%(product)s uses graduated tiers. That method is not approved. '
                'Full-volume pricing was not applied in its place.',
                product=label,
            ))
            return messages
        if method == 'none':
            if tiers:
                messages.append(self.env._(
                    '%(product)s has quantity tiers but the tier method is not identified. '
                    'The number of rows does not choose a method.',
                    product=label,
                ))
            return messages
        if method != 'full_volume':
            messages.append(self.env._(
                '%(product)s has an unsupported tier method.',
                product=label,
            ))
            return messages
        if not tiers:
            messages.append(self.env._(
                '%(product)s says full-volume pricing but has no quantity tiers.',
                product=label,
            ))
            return messages
        if self.quantity_basis == 'cumulative':
            messages.append(self.env._(
                '%(product)s uses cumulative volume. That quantity policy is not implemented.',
                product=label,
            ))
        elif self.quantity_basis not in APPROVED_BASES:
            messages.append(self.env._(
                '%(product)s has quantity tiers and no approved quantity basis. '
                'The company quantity candidate was not used.',
                product=label,
            ))
        if self.return_policy not in ('unconfigured', 'order_tier_lock', 'net_quantity'):
            messages.append(self.env._(
                '%(product)s has an unsupported return quantity policy.',
                product=label,
            ))
        overlap = self._tier_overlap_issue()
        if overlap:
            messages.append(overlap)
        gap = self._tier_gap_issue()
        if gap:
            messages.append(gap)
        return messages

    def _tier_overlap_issue(self):
        self.ensure_one()
        tiers = list(self.tier_ids)
        for index, tier in enumerate(tiers):
            for other in tiers[index + 1:]:
                if tier._same_bounds(other):
                    return self.env._(
                        'Duplicate quantity tier. The same range is already on this line.'
                    )
                if _ranges_overlap(tier._bounds(), other._bounds()):
                    return self.env._(
                        'Overlapping quantity tiers. No tier price was selected.'
                    )
        return False

    def _tier_gap_issue(self):
        self.ensure_one()
        spans = []
        for tier in self.tier_ids:
            bounds = tier._bounds()
            if not bounds:
                return self.env._(
                    'A quantity tier is missing its historical conversion factor.'
                )
            spans.append(bounds)
        spans.sort(key=lambda item: (item[0], item[1] is None, item[1] or Decimal(0)))
        previous_end = None
        for start, end in spans:
            if previous_end is not None and start > previous_end:
                return self.env._(
                    'Quantity tiers leave a gap. No rate was invented for the missing range.'
                )
            if end is None:
                previous_end = None
                break
            if previous_end is None or end > previous_end:
                previous_end = end
        return False


class CustomerContractVersionQuantity(models.Model):
    _inherit = 'cpla.customer.contract.version'

    def create_amendment(self):
        new = super().create_amendment()
        tier_model = self.env['cpla.customer.contract.version.tier']
        for line in new.line_ids:
            origin = line.origin_line_id
            if not origin:
                continue
            for tier in origin.tier_ids:
                tier_model.create(tier._values_for_line(line))
        return new

    def _apply_approval(self):
        for version in self:
            tiers = version.line_ids.tier_ids
            if not tiers:
                continue
            version.line_ids.lock_for_update()
            tiers.lock_for_update()
            tiers._write_multi([
                tier._factor_values(capture=True) for tier in tiers
            ])
            tiers.invalidate_recordset()
        return super()._apply_approval()

    def _checksum(self, partner_name, covered_names):
        base = super()._checksum(partner_name, covered_names)
        payload = {
            'base': base,
            'tiers': self._tier_checksum_rows(),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _tier_checksum_rows(self):
        rows = []
        for line in self.line_ids.sorted(key=lambda item: (item.product_id.id, item.id)):
            for tier in line.tier_ids.sorted(key=lambda item: (item.min_quantity, item.id)):
                rows.append({
                    'product_id': line.product_id.id,
                    'method': line.tier_method,
                    'basis': line.quantity_basis,
                    'return_policy': line.return_policy,
                    'min': '%s' % _D(tier.min_quantity),
                    'max': '' if not tier.has_maximum else '%s' % _D(tier.max_quantity),
                    'price': '%s' % _D(tier.price_unit),
                    'quantity_uom_id': tier.quantity_uom_id.id,
                    'pricing_uom_id': tier.pricing_uom_id.id,
                    'quantity_factor': '%s' % _D(tier.quantity_uom_factor or 0),
                    'pricing_factor': '%s' % _D(tier.pricing_uom_factor or 0),
                    'product_factor': '%s' % _D(tier.product_uom_factor or 0),
                })
        return rows

    def _tier_signature(self):
        return tuple(self._tier_checksum_rows())

    def compare_with(self, other):
        result = super().compare_with(other)
        if self._tier_signature() != other._tier_signature():
            result['lines'].append(self._comparison_row(
                'Quantity Tiers Changed',
                'Quantity tiers',
                False,
                False,
                None,
                True,
            ))
        return result


class PricingQuantity(models.AbstractModel):
    """Read-only quantity tier selection and unit normalization.

    Company policy candidates are not read. The approved version line
    states the method, the quantity basis, and the return rule.
    """

    _name = 'cpla.pricing.quantity'
    _description = 'Contract Quantity and Unit Normalization'

    @api.model
    def convert_quantity(self, quantity, from_factor, to_factor):
        """Convert a quantity between two snapshotted absolute factors.

        The result keeps the exact decimal text. It does not round to a
        whole package.
        """
        return self._divide(quantity, from_factor, to_factor, price=False)

    @api.model
    def convert_price(self, price, contract_factor, target_factor):
        """Price per target unit from a price per contract unit.

        Normalized price = contract price * target factor / contract factor.
        """
        return self._divide(price, target_factor, contract_factor, price=True)

    @api.model
    def _divide(self, amount, numerator_factor, denominator_factor, price=False):
        try:
            amount_d = _D(amount)
            numerator = _D(numerator_factor)
            denominator = _D(denominator_factor)
        except (InvalidOperation, ValueError):
            return self._conversion_failure('invalid_number')
        if numerator <= 0 or denominator <= 0:
            return self._conversion_failure('non_positive_factor')
        exact = amount_d * numerator / denominator
        return {
            'ok': True,
            'exact': format(exact, 'f'),
            'amount': float(exact) if price else False,
        }

    @api.model
    def _conversion_failure(self, reason):
        return {
            'ok': False,
            'reason': reason,
            'exact': False,
            'amount': False,
        }

    @api.model
    def evaluate(self, line, request):
        """Select a tier or the standalone rate. This does not write."""
        line = self.env[line._name].browse(line.ids)
        line.check_access('read')
        line = line.exists()
        line.ensure_one()
        request = dict(request or {})
        for forged in (
            'unit_price', 'tier_id', 'normalized_unit_price', 'contract_unit_price',
            'version_id', 'contract_id',
        ):
            request.pop(forged, None)
        if line.tier_method == 'graduated':
            return self._unsupported(line, self.env._(
                'Graduated pricing is not approved. Full-volume pricing was not applied.'
            ))
        if line.quantity_basis == 'cumulative':
            return self._unsupported(line, self.env._(
                'Cumulative contract volume is not implemented. Today purchases were not used.'
            ))
        if line.version_id.state != 'approved':
            return self._quantity_result(
                authoritative=False,
                quantity_status='missing_historical_conversion',
                reason_code='version_not_approved',
                status='HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                explanation=self.env._(
                    'The version is not approved. No tier price was released.'
                ),
                line=line,
            )
        if self._aggregation_block(request):
            return self._quantity_result(
                authoritative=False,
                quantity_status='source_allocation_review_required',
                reason_code='product_aggregation_not_approved',
                status='POLICY_REVIEW_REQUIRED',
                explanation=self.env._(
                    'Quantities of different products or variants were not added together. '
                    'No combined tier price was selected.'
                ),
                line=line,
            )
        if self._allocation_block(request):
            return self._quantity_result(
                authoritative=False,
                quantity_status='source_allocation_review_required',
                reason_code='source_allocation_review_required',
                status='SOURCE_ALLOCATION_REVIEW_REQUIRED',
                explanation=self.env._(
                    'The source allocation is missing or lists more than one quantity. '
                    'Those quantities were not summed.'
                ),
                line=line,
            )
        if request.get('document_type') == 'credit_note':
            return self._quantity_result(
                authoritative=False,
                quantity_status='negative_quantity_review',
                reason_code='credit_note_not_a_sale',
                status='NEGATIVE_QUANTITY_REVIEW',
                explanation=self.env._(
                    'A credit note was not treated as a new positive sale. No tier price was selected.'
                ),
                line=line,
            )
        if not line.tier_ids and line.tier_method in (False, 'none'):
            return self._standalone(line, request)
        family = self._family_failure(line, request)
        if family:
            return family
        if line.tier_method != 'full_volume':
            return self._unsupported(line, self.env._(
                'The tier method is not an approved full-volume method. No tier price was selected.'
            ))
        if line.quantity_basis not in APPROVED_BASES:
            return self._unsupported(line, self.env._(
                'The quantity basis on this line is not set. The company quantity candidate was not used.'
            ))
        if not line.tier_ids:
            return self._unsupported(line, self.env._(
                'Full-volume pricing has no tier rows. The standalone price was not substituted.'
            ))
        quantity = self._qualifying_quantity(line, request)
        if quantity == 'missing':
            return self._quantity_result(
                authoritative=False,
                quantity_status='missing_qualifying_quantity',
                reason_code='missing_qualifying_quantity',
                status='MISSING_QUALIFYING_QUANTITY',
                explanation=self.env._(
                    'The approved quantity basis needs a quantity that was not supplied. '
                    'A different quantity was not substituted.'
                ),
                line=line,
            )
        try:
            quantity_d = _D(quantity)
        except (InvalidOperation, ValueError):
            return self._quantity_result(
                authoritative=False,
                quantity_status='missing_qualifying_quantity',
                reason_code='missing_qualifying_quantity',
                status='MISSING_QUALIFYING_QUANTITY',
                explanation=self.env._('The qualifying quantity is not a valid number.'),
                line=line,
            )
        if quantity_d < 0:
            return self._negative(line)
        returned = request.get('returned_quantity')
        if not _missing(returned):
            try:
                returned_d = _D(returned)
            except (InvalidOperation, ValueError):
                returned_d = None
            if returned_d is None or returned_d < 0:
                return self._negative(line)
            if returned_d > 0:
                if line.return_policy == 'unconfigured':
                    return self._quantity_result(
                        authoritative=False,
                        quantity_status='source_allocation_review_required',
                        reason_code='return_policy_not_approved',
                        status='POLICY_REVIEW_REQUIRED',
                        explanation=self.env._(
                            'A return was supplied and this line does not say whether the original '
                            'tier stays locked. No tier was changed.'
                        ),
                        line=line,
                    )
                if line.return_policy == 'net_quantity':
                    quantity_d = quantity_d - returned_d
                    if quantity_d < 0:
                        return self._negative(line)
        if quantity_d == 0:
            return self._quantity_result(
                authoritative=False,
                quantity_status='no_matching_tier',
                reason_code='zero_quantity',
                status='NO_MATCHING_TIER',
                explanation=self.env._(
                    'A zero quantity is not a positive sale. No tier price was selected.'
                ),
                line=line,
            )
        source_factor = self._quantity_factor(line, request)
        if source_factor == 'incompatible':
            return self._incompatible(line)
        if source_factor is None:
            return self._missing_factor(line)
        matches = []
        for tier in line.tier_ids:
            if not tier.factor_captured_at or _D(tier.quantity_uom_factor or 0) <= 0:
                return self._missing_factor(line)
            if _D(tier.pricing_uom_factor or 0) <= 0 or _D(tier.product_uom_factor or 0) <= 0:
                return self._missing_factor(line)
            converted = self.convert_quantity(
                format(quantity_d, 'f'),
                format(source_factor, 'f'),
                format(_D(tier.quantity_uom_factor), 'f'),
            )
            if not converted['ok']:
                return self._missing_factor(line)
            qty_in_tier = _D(converted['exact'])
            if self._contains(tier, qty_in_tier):
                matches.append((tier, qty_in_tier))
        if len(matches) > 1:
            return self._quantity_result(
                authoritative=False,
                quantity_status='tier_conflict_review_required',
                reason_code='tier_conflict_review_required',
                status='TIER_CONFLICT_REVIEW_REQUIRED',
                explanation=self.env._(
                    'More than one quantity tier covers this quantity. No price was selected.'
                ),
                line=line,
            )
        if not matches:
            return self._quantity_result(
                authoritative=False,
                quantity_status='no_matching_tier',
                reason_code='no_matching_tier',
                status='NO_MATCHING_TIER',
                explanation=self.env._(
                    'The quantity is outside every approved tier. The nearest tier was not used.'
                ),
                line=line,
            )
        tier, qty_in_tier = matches[0]
        return self._price_tier(line, request, tier, quantity_d, qty_in_tier, source_factor)

    @api.model
    def _standalone(self, line, request):
        family = self._family_failure(line, request)
        if family:
            return family
        for key in ('quantity', 'order_quantity', 'invoice_quantity', 'delivery_quantity', 'returned_quantity'):
            if _missing(request.get(key)):
                continue
            try:
                if _D(request.get(key)) < 0:
                    return self._negative(line)
            except (InvalidOperation, ValueError):
                return self._quantity_result(
                    authoritative=False,
                    quantity_status='missing_qualifying_quantity',
                    reason_code='missing_qualifying_quantity',
                    status='MISSING_QUALIFYING_QUANTITY',
                    explanation=self.env._('The qualifying quantity is not a valid number.'),
                    line=line,
                )
        returned = request.get('returned_quantity')
        if not _missing(returned):
            try:
                returned_d = _D(returned)
            except (InvalidOperation, ValueError):
                returned_d = Decimal(0)
            if returned_d > 0 and line.return_policy != 'order_tier_lock':
                return self._quantity_result(
                    authoritative=False,
                    quantity_status='source_allocation_review_required',
                    reason_code='return_policy_not_approved',
                    status='POLICY_REVIEW_REQUIRED',
                    explanation=self.env._(
                        'A return was supplied and this line does not keep the original tier locked. '
                        'No price was selected.'
                    ),
                    line=line,
                )
        has_quantity = self._any_quantity(request)
        comparison = request.get('comparison_uom_id')
        quantity_uom = request.get('quantity_uom_id')
        if quantity_uom and quantity_uom != line.uom_id.id:
            return self._quantity_result(
                authoritative=False,
                quantity_status='missing_historical_conversion',
                reason_code='missing_historical_conversion',
                status='MISSING_HISTORICAL_CONVERSION',
                explanation=self.env._(
                    'The standalone price has no approved conversion for that quantity unit. '
                    'The current unit factor was not applied.'
                ),
                line=line,
            )
        if comparison and comparison != line.uom_id.id:
            return self._quantity_result(
                authoritative=False,
                quantity_status='missing_historical_conversion',
                reason_code='missing_historical_conversion',
                status='MISSING_HISTORICAL_CONVERSION',
                explanation=self.env._(
                    'The standalone price has no approved conversion to the requested unit. '
                    'The current unit factor was not applied.'
                ),
                line=line,
            )
        if not has_quantity:
            return self._quantity_result(
                authoritative=True,
                quantity_status='not_applicable',
                reason_code=False,
                status=False,
                explanation=False,
                line=line,
                unit_price=line.price_unit,
                uom_id=line.uom_id.id,
            )
        return self._quantity_result(
            authoritative=True,
            quantity_status='base_price_applicable',
            reason_code='base_price_applicable',
            status=False,
            explanation=self.env._(
                'No quantity tier is approved on this line. The supplied quantity was not evaluated as a tier. '
                'The stored unit price is not a qualified tier price.'
            ),
            line=line,
            unit_price=line.price_unit,
            uom_id=line.uom_id.id,
            contract_unit_price=line.price_unit,
            contract_uom_id=line.uom_id.id,
            normalized_unit_price=line.price_unit,
            normalized_unit_price_exact=format(_D(line.price_unit), 'f'),
            normalized_uom_id=line.uom_id.id,
        )

    @api.model
    def _price_tier(self, line, request, tier, quantity_d, qty_in_tier, source_factor):
        packaging = request.get('packaging_uom_id')
        if packaging and packaging not in (
            tier.pricing_uom_id.id,
            tier.quantity_uom_id.id,
            tier.product_uom_id.id,
            line.product_id.uom_id.id,
        ):
            return self._quantity_result(
                authoritative=False,
                quantity_status='packaging_review_required',
                reason_code='packaging_review_required',
                status='PACKAGING_REVIEW_REQUIRED',
                explanation=self.env._(
                    'The requested packaging is not the approved pricing unit for this product. '
                    'It was not used.'
                ),
                line=line,
            )
        target = self._target_uom(line, request, tier)
        if target == 'incompatible':
            return self._quantity_result(
                authoritative=False,
                quantity_status='incompatible_uom',
                reason_code='incompatible_uom',
                status='INCOMPATIBLE_UOM',
                explanation=self.env._(
                    'The requested unit is not in the same family. No conversion was invented.'
                ),
                line=line,
            )
        if target == 'missing':
            return self._missing_factor(line)
        target_uom, target_factor = target
        priced = self.convert_price(
            format(_D(tier.price_unit), 'f'),
            format(_D(tier.pricing_uom_factor), 'f'),
            format(target_factor, 'f'),
        )
        if not priced['ok']:
            return self._missing_factor(line)
        normalized_qty = self.convert_quantity(
            format(quantity_d, 'f'),
            format(source_factor, 'f'),
            format(target_factor, 'f'),
        )
        factor_text = format(target_factor / _D(tier.pricing_uom_factor), 'f')
        billed = request.get('billed_quantity')
        billed_exact = False if _missing(billed) else format(_D(billed), 'f')
        return self._quantity_result(
            authoritative=True,
            quantity_status='tier_matched',
            reason_code='tier_matched',
            status=False,
            explanation=self.env._(
                'One full-volume tier covers the qualifying quantity. '
                'The qualifying quantity and the billed quantity are separate. '
                'The standalone line price was not added. '
                'This is not an invoice audit and it is not a leakage amount.'
            ),
            line=line,
            unit_price=float(_D(priced['exact'])),
            uom_id=target_uom.id,
            tier_id=tier.id,
            qualified_quantity_exact=format(quantity_d, 'f'),
            qualified_uom_id=self._qualified_uom_id(line, request, tier),
            normalized_unit_price=float(_D(priced['exact'])),
            normalized_unit_price_exact=priced['exact'],
            normalized_quantity_exact=normalized_qty['exact'] if normalized_qty['ok'] else False,
            normalized_uom_id=target_uom.id,
            conversion_factor_exact=factor_text,
            contract_unit_price=tier.price_unit,
            contract_uom_id=tier.pricing_uom_id.id,
            billed_quantity_exact=billed_exact,
            historical_factor_used=True,
            tier_quantity_exact=format(qty_in_tier, 'f'),
        )

    @api.model
    def _qualified_uom_id(self, line, request, tier):
        requested = request.get('quantity_uom_id')
        if requested:
            return requested
        return tier.quantity_uom_id.id or line.product_id.uom_id.id

    @api.model
    def _quantity_factor(self, line, request):
        """Return the snapshotted absolute factor for the supplied quantity unit."""
        tier = line.tier_ids[:1]
        requested = request.get('quantity_uom_id')
        if not requested:
            product_uom = line.product_id.uom_id
            if all(item.quantity_uom_id == product_uom for item in line.tier_ids):
                factor = _D(tier.product_uom_factor or 0)
                return factor if factor > 0 else None
            return None
        factors = []
        for item in line.tier_ids:
            if requested == item.quantity_uom_id.id:
                factors.append(_D(item.quantity_uom_factor or 0))
            elif requested == item.product_uom_id.id or requested == line.product_id.uom_id.id:
                factors.append(_D(item.product_uom_factor or 0))
            elif requested == item.pricing_uom_id.id:
                factors.append(_D(item.pricing_uom_factor or 0))
        if not factors or any(factor <= 0 for factor in factors):
            if requested and not self._known_uom(line, requested):
                live = self.env['uom.uom'].browse(requested).exists()
                product_uom = line.product_id.uom_id
                if live and product_uom and not live._has_common_reference(product_uom):
                    return 'incompatible'
            return None
        if len(set(factors)) != 1:
            return None
        return factors[0]

    @api.model
    def _known_uom(self, line, uom_id):
        for item in line.tier_ids:
            if uom_id in (
                item.quantity_uom_id.id,
                item.pricing_uom_id.id,
                item.product_uom_id.id,
            ):
                return True
        return uom_id == line.product_id.uom_id.id or uom_id == line.uom_id.id

    @api.model
    def _target_uom(self, line, request, tier):
        requested = request.get('comparison_uom_id') or tier.pricing_uom_id.id
        if requested == tier.pricing_uom_id.id:
            return tier.pricing_uom_id, _D(tier.pricing_uom_factor)
        if requested in (tier.product_uom_id.id, line.product_id.uom_id.id, line.uom_id.id):
            return line.product_id.uom_id, _D(tier.product_uom_factor)
        if requested == tier.quantity_uom_id.id:
            return tier.quantity_uom_id, _D(tier.quantity_uom_factor)
        live = self.env['uom.uom'].browse(requested).exists()
        product_uom = line.product_id.uom_id
        if live and product_uom and not live._has_common_reference(product_uom):
            return 'incompatible'
        return 'missing'

    @api.model
    def _contains(self, tier, qty_in_tier):
        minimum = _D(tier.min_quantity)
        if qty_in_tier < minimum:
            return False
        if tier.has_maximum and qty_in_tier >= _D(tier.max_quantity):
            return False
        return True

    @api.model
    def _qualifying_quantity(self, line, request):
        basis = line.quantity_basis
        specific_key = BASIS_FIELD[basis]
        specific = request.get(specific_key)
        if not _missing(specific):
            return specific
        if _missing(request.get('quantity')):
            return 'missing'
        if request.get('qualification_basis') not in (None, False, '', basis):
            return 'missing'
        for key in BASIS_FIELD.values():
            if key != specific_key and not _missing(request.get(key)):
                return 'missing'
        return request.get('quantity')

    @api.model
    def _any_quantity(self, request):
        keys = (
            'quantity', 'order_quantity', 'invoice_quantity',
            'delivery_quantity', 'returned_quantity', 'billed_quantity',
        )
        return any(not _missing(request.get(key)) for key in keys)

    @api.model
    def _aggregation_block(self, request):
        return any(not _missing(request.get(key)) for key in (
            'other_product_quantity', 'variant_quantity',
        ))

    @api.model
    def _allocation_block(self, request):
        if request.get('allocation_unverified'):
            return True
        for key in ('invoice_line_quantities', 'delivery_quantities'):
            values = request.get(key)
            if isinstance(values, (list, tuple)) and len(values) > 1:
                return True
        return False

    @api.model
    def _unsupported(self, line, explanation):
        return self._quantity_result(
            authoritative=False,
            quantity_status='unsupported_quantity_policy',
            reason_code='unsupported_quantity_policy',
            status='UNSUPPORTED_QUANTITY_POLICY',
            explanation=explanation,
            line=line,
        )

    @api.model
    def _family_failure(self, line, request):
        product_uom = line.product_id.uom_id
        if not product_uom:
            return False
        for key in ('comparison_uom_id', 'quantity_uom_id', 'packaging_uom_id'):
            uom_id = request.get(key)
            if not uom_id:
                continue
            uom = self.env['uom.uom'].browse(uom_id).exists()
            if uom and not uom._has_common_reference(product_uom):
                return self._incompatible(line)
        return False

    @api.model
    def _incompatible(self, line):
        return self._quantity_result(
            authoritative=False,
            quantity_status='incompatible_uom',
            reason_code='incompatible_uom',
            status='INCOMPATIBLE_UOM',
            explanation=self.env._(
                'The requested unit is not in the same family. No conversion was invented.'
            ),
            line=line,
        )

    @api.model
    def _missing_factor(self, line):
        return self._quantity_result(
            authoritative=False,
            quantity_status='missing_historical_conversion',
            reason_code='missing_historical_conversion',
            status='MISSING_HISTORICAL_CONVERSION',
            explanation=self.env._(
                'The approved conversion factor is missing. The current unit factor was not applied.'
            ),
            line=line,
        )

    @api.model
    def _negative(self, line):
        return self._quantity_result(
            authoritative=False,
            quantity_status='negative_quantity_review',
            reason_code='negative_quantity',
            status='NEGATIVE_QUANTITY_REVIEW',
            explanation=self.env._(
                'A negative quantity was not treated as a positive sale. No tier price was selected.'
            ),
            line=line,
        )

    @api.model
    def _quantity_result(
        self, authoritative, quantity_status, reason_code, status, explanation, line,
        unit_price=False, uom_id=False, tier_id=False, qualified_quantity_exact=False,
        qualified_uom_id=False, normalized_unit_price=False, normalized_unit_price_exact=False,
        normalized_quantity_exact=False, normalized_uom_id=False, conversion_factor_exact=False,
        contract_unit_price=False, contract_uom_id=False, billed_quantity_exact=False,
        historical_factor_used=False, tier_quantity_exact=False,
    ):
        return {
            'authoritative': authoritative,
            'quantity_status': quantity_status,
            'tier_status': quantity_status,
            'reason_code': reason_code,
            'status': status,
            'explanation': explanation,
            'unit_price': unit_price if authoritative else False,
            'uom_id': uom_id if authoritative else False,
            'tier_id': tier_id if authoritative else False,
            'qualified_quantity_exact': qualified_quantity_exact if authoritative else False,
            'qualified_uom_id': qualified_uom_id if authoritative else False,
            'normalized_unit_price': normalized_unit_price if authoritative else False,
            'normalized_unit_price_exact': normalized_unit_price_exact if authoritative else False,
            'normalized_quantity_exact': normalized_quantity_exact if authoritative else False,
            'normalized_uom_id': normalized_uom_id if authoritative else False,
            'conversion_factor_exact': conversion_factor_exact if authoritative else False,
            'contract_unit_price': contract_unit_price if authoritative else False,
            'contract_uom_id': contract_uom_id if authoritative else False,
            'billed_quantity_exact': billed_quantity_exact,
            'tier_method': line.tier_method,
            'quantity_basis': line.quantity_basis,
            'return_policy': line.return_policy,
            'historical_factor_used': historical_factor_used,
            'tier_quantity_exact': tier_quantity_exact if authoritative else False,
            'leakage_amount': False,
            'is_recovered_cash': False,
        }


def _ranges_overlap(left, right):
    if not left or not right:
        return False
    left_start, left_end = left
    right_start, right_end = right
    if left_end is not None and left_end <= right_start:
        return False
    if right_end is not None and right_end <= left_start:
        return False
    return True
