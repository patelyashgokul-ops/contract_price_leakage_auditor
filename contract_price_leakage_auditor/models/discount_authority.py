import hashlib
import json
from decimal import Decimal

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    _arithmetic,
    _decimal,
    _text,
)

MODULE = 'contract_price_leakage_auditor'
USER_GROUP = f'{MODULE}.group_contract_user'
MANAGER_GROUP = f'{MODULE}.group_contract_manager'
REVIEWER_GROUP = f'{MODULE}.group_finance_reviewer'
FINANCE_MANAGER_GROUP = f'{MODULE}.group_finance_manager'
AUDITOR_GROUP = f'{MODULE}.group_internal_auditor'
APP_ADMIN_GROUP = f'{MODULE}.group_app_admin'

READ_GROUPS = (
    USER_GROUP,
    MANAGER_GROUP,
    REVIEWER_GROUP,
    FINANCE_MANAGER_GROUP,
    AUDITOR_GROUP,
)

AUTHORITATIVE = (
    'AUTHORIZED_PRICE_RESOLVED',
    'NO_ADDITIONAL_DISCOUNT',
    'SPECIAL_PRICE_APPLICABLE',
    'APPROVED_OVERRIDE_APPLICABLE',
)
SUCCESS_FINANCIAL = ('NORMALIZED', 'SAME_CURRENCY_NO_CONVERSION')
HUNDRED = Decimal(100)
ZERO = Decimal(0)

CONCESSION_SERVER_FIELDS = frozenset({
    'concession_uom_factor_exact',
    'product_uom_factor_exact',
    'revocation_state',
    'revocation_effective_on',
    'revoked_at',
    'revoked_by_id',
    'revocation_reason',
    'revocation_retroactive',
    'superseded_by_id',
})
APPROVAL_SERVER_FIELDS = frozenset({
    'requester_id',
    'submitted_by_id',
    'approver_id',
    'approved_at',
    'rejected_by_id',
    'state',
    'baseline_unit_price_exact',
    'exposure_exact',
    'exposure_currency_id',
    'snapshot_json',
    'limit_snapshot_json',
    'retroactive_granted',
    'revocation_state',
    'revocation_effective_on',
    'revoked_at',
    'revoked_by_id',
    'revocation_reason',
    'revocation_retroactive',
    'superseded_by_id',
})
FORGED_DISCOUNT_KEYS = (
    'discount_rate',
    'discount_percent',
    'approved_adjusted_unit_price_exact',
    'concession_id',
    'approver_id',
    'approved_by',
    'approved_by_id',
    'exposure_exact',
    'baseline_unit_price_exact',
    'leakage_amount',
    'stacking_policy',
)


def _as_date(value):
    if not value:
        return None
    if hasattr(value, 'year') and not hasattr(value, 'hour'):
        return value
    try:
        return fields.Date.to_date(value)
    except (TypeError, ValueError):
        return None


def _as_datetime(value):
    if not value:
        return None
    if hasattr(value, 'hour'):
        return value
    try:
        return fields.Datetime.to_datetime(value)
    except (TypeError, ValueError):
        return None


class DiscountConcession(models.Model):
    """One contractual concession on an approved contract version.

    The version approval is the authority for these rows. A company
    discount candidate is not read. Draft rows have no pricing authority.
    """

    _name = 'cpla.discount.concession'
    _description = 'Contractual Discount Concession'
    _order = 'sequence, id'
    _check_company_auto = True

    version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Contract Version',
        required=True,
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='version_id.company_id',
        store=True,
        index=True,
        readonly=True,
    )
    version_line_id = fields.Many2one(
        'cpla.customer.contract.version.line',
        string='Version Line',
        ondelete='cascade',
        index=True,
        check_company=True,
    )
    sequence = fields.Integer(default=10, index=True)
    concession_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage discount'),
            ('fixed_per_unit', 'Fixed amount per unit'),
            ('fixed_special_price', 'Fixed special price'),
            ('unsupported', 'Unsupported benefit'),
        ],
        required=True,
        default='percentage',
        index=True,
    )
    percent_exact = fields.Char(string='Percent')
    amount_exact = fields.Char(string='Amount')
    currency_id = fields.Many2one('res.currency', string='Currency', ondelete='restrict')
    uom_id = fields.Many2one('uom.uom', string='Pricing Unit', ondelete='restrict')
    customer_scope = fields.Selection(
        selection=[
            ('version_customer', 'Version customer only'),
            ('exact_partner', 'Named customer or branch'),
        ],
        required=True,
        default='version_customer',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Named Customer',
        check_company=True,
        index=True,
    )
    product_scope = fields.Selection(
        selection=[
            ('version_line', 'Version line variant'),
            ('exact_variant', 'Named variant'),
            ('product_template', 'Named product template'),
        ],
        required=True,
        default='version_line',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Variant',
        check_company=True,
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        check_company=True,
        index=True,
    )
    effective_from = fields.Date(string='Effective From', index=True)
    effective_to = fields.Date(string='Effective To', index=True)
    exclusive = fields.Boolean(
        string='Exclusive',
        help='An exclusive concession is not combined with another concession.',
    )
    precedence_rank = fields.Integer(
        string='Precedence',
        help='Used only when more than one exclusive concession matches. Rank 0 is unset. A lower rank wins only when every rank is set and unique. Price is not a tie-break.',
    )
    quantity_min_exact = fields.Char(string='Minimum Quantity')
    quantity_max_exact = fields.Char(string='Maximum Quantity')
    quantity_uom_id = fields.Many2one('uom.uom', string='Quantity Unit', ondelete='restrict')
    evidence_reference = fields.Char(string='Evidence Reference')
    unsupported_reason = fields.Char(string='Why This Benefit Is Unsupported')
    concession_uom_factor_exact = fields.Char(
        string='Concession Unit Factor',
        readonly=True,
    )
    product_uom_factor_exact = fields.Char(
        string='Product Unit Factor',
        readonly=True,
    )
    revocation_state = fields.Selection(
        selection=[
            ('none', 'Not revoked'),
            ('revoked', 'Revoked'),
            ('superseded', 'Superseded'),
        ],
        default='none',
        required=True,
        index=True,
    )
    revocation_effective_on = fields.Date(string='Revocation Effective On', readonly=True)
    revoked_at = fields.Datetime(string='Revoked At', readonly=True)
    revoked_by_id = fields.Many2one('res.users', string='Revoked By', readonly=True)
    revocation_reason = fields.Char(string='Revocation Reason', readonly=True)
    revocation_retroactive = fields.Boolean(string='Retroactive Revocation', readonly=True)
    superseded_by_id = fields.Many2one(
        'cpla.discount.concession',
        string='Superseded By',
        readonly=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            illegal = sorted(CONCESSION_SERVER_FIELDS & set(vals))
            if illegal:
                raise UserError(self.env._(
                    'Concession evidence is server-controlled and was not written: %(fields)s.',
                    fields=', '.join(illegal),
                ))
            version = self.env['cpla.customer.contract.version'].browse(vals.get('version_id'))
            if not version or version.state != 'draft':
                raise UserError(self.env._(
                    'A concession can be added only on a draft contract version.'
                ))
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to prepare a contractual concession.'
                ))
        records = super().create(vals_list)
        records._check_shape()
        return records

    def write(self, vals):
        self.check_access('write')
        illegal = sorted(CONCESSION_SERVER_FIELDS & set(vals))
        if illegal:
            raise UserError(self.env._(
                'Concession evidence is server-controlled and was not written: %(fields)s.',
                fields=', '.join(illegal),
            ))
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to change a contractual concession.'
            ))
        for concession in self:
            if concession.version_id.state != 'draft':
                raise UserError(self.env._(
                    'An approved concession snapshot cannot be edited. '
                    'The historical amount stays unchanged.'
                ))
        written = super().write(vals)
        self._check_shape()
        return written

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        for concession in self:
            if concession.version_id.state != 'draft':
                raise UserError(self.env._(
                    'An approved concession snapshot cannot be deleted.'
                ))
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to delete a contractual concession.'
                ))
        return super().unlink()

    def _check_shape(self):
        for concession in self:
            issue = concession._shape_issue()
            if issue:
                raise ValidationError(issue)

    def _shape_issue(self):
        self.ensure_one()
        if self.concession_type == 'percentage':
            percent = _decimal(self.percent_exact)
            if percent is None or percent <= 0 or percent >= 100:
                return self.env._(
                    'A percentage concession must be greater than 0 and less than 100. '
                    'No price was invented.'
                )
        elif self.concession_type in ('fixed_per_unit', 'fixed_special_price'):
            amount = _decimal(self.amount_exact)
            if amount is None or amount <= 0:
                return self.env._(
                    'A monetary concession must be a positive exact amount.'
                )
            if not self.currency_id or not self.uom_id:
                return self.env._(
                    'A monetary concession needs its currency and pricing unit.'
                )
        elif self.concession_type == 'unsupported' and not (self.unsupported_reason or '').strip():
            return self.env._(
                'An unsupported benefit needs a reason. It was not stored as a per-unit discount.'
            )
        if self.customer_scope == 'exact_partner' and not self.partner_id:
            return self.env._('The named customer or branch is missing.')
        if self.partner_id and self.partner_id.company_id and self.partner_id.company_id != self.company_id:
            return self.env._(
                'The named customer belongs to another company. The concession was not saved.'
            )
        if self.product_scope == 'version_line':
            if not self.version_line_id or self.version_line_id.version_id != self.version_id:
                return self.env._(
                    'A line concession must point at a line of the same contract version.'
                )
        elif self.product_scope == 'exact_variant' and not self.product_id:
            return self.env._('The named product variant is missing.')
        elif self.product_scope == 'product_template' and not self.product_tmpl_id:
            return self.env._(
                'Template scope applies only when the product template is named.'
            )
        if self.product_id and self.product_id.company_id and self.product_id.company_id != self.company_id:
            return self.env._(
                'The product belongs to another company. The concession was not saved.'
            )
        start = self.effective_from
        end = self.effective_to
        if start and end and end < start:
            return self.env._('The concession end date is before the start date.')
        for label, raw in (
            ('minimum quantity', self.quantity_min_exact),
            ('maximum quantity', self.quantity_max_exact),
        ):
            if raw:
                number = _decimal(raw)
                if number is None or number < 0:
                    return self.env._(
                        'The %(label)s is not a positive exact quantity.',
                        label=label,
                    )
        if self.quantity_min_exact or self.quantity_max_exact:
            if not self.quantity_uom_id:
                return self.env._('A quantity bound needs its quantity unit.')
            minimum = _decimal(self.quantity_min_exact) or ZERO
            maximum = _decimal(self.quantity_max_exact)
            if maximum is not None and maximum <= minimum:
                return self.env._(
                    'The maximum quantity must be greater than the minimum. The maximum is exclusive.'
                )
        return False

    def _copy_vals(self, version):
        self.ensure_one()
        line = False
        if self.version_line_id:
            line = version.line_ids.filtered(
                lambda item: item.origin_line_id == self.version_line_id
            )[:1]
        return {
            'version_id': version.id,
            'version_line_id': line.id if line else False,
            'sequence': self.sequence,
            'concession_type': self.concession_type,
            'percent_exact': self.percent_exact,
            'amount_exact': self.amount_exact,
            'currency_id': self.currency_id.id,
            'uom_id': self.uom_id.id,
            'customer_scope': self.customer_scope,
            'partner_id': self.partner_id.id,
            'product_scope': self.product_scope,
            'product_id': self.product_id.id,
            'product_tmpl_id': self.product_tmpl_id.id,
            'effective_from': self.effective_from,
            'effective_to': self.effective_to,
            'exclusive': self.exclusive,
            'precedence_rank': self.precedence_rank,
            'quantity_min_exact': self.quantity_min_exact,
            'quantity_max_exact': self.quantity_max_exact,
            'quantity_uom_id': self.quantity_uom_id.id,
            'evidence_reference': self.evidence_reference,
            'unsupported_reason': self.unsupported_reason,
        }

    def action_revoke(self, effective_on, reason, retroactive=False):
        """Record a later revocation without rewriting the approved amount."""
        self.ensure_one()
        self._check_revoker()
        if self.revocation_state != 'none':
            return True
        if self.version_id.state != 'approved':
            raise UserError(self.env._(
                'Only an approved concession can be revoked. The draft was not changed.'
            ))
        day = _as_date(effective_on)
        if not day:
            raise UserError(self.env._('A revocation effective date is required.'))
        if retroactive and self.version_id.retroactive_discount_authority != 'explicitly_allowed':
            raise UserError(self.env._(
                'Retroactive revocation is not authorized on this contract version. '
                'Earlier discounts were not reclassified.'
            ))
        if not retroactive and day < fields.Date.context_today(self):
            raise UserError(self.env._(
                'A prospective revocation cannot start in the past. '
                'Retroactive authority was not assumed.'
            ))
        if not (reason or '').strip():
            raise UserError(self.env._('A revocation reason is required.'))
        self.lock_for_update()
        if self.revocation_state != 'none':
            return True
        models.Model.write(self, {
            'revocation_state': 'revoked',
            'revocation_effective_on': day,
            'revoked_at': fields.Datetime.now(),
            'revoked_by_id': self.env.user.id,
            'revocation_reason': reason.strip(),
            'revocation_retroactive': bool(retroactive),
        })
        self.env['cpla.discount.event']._record(self.env._(
            'Concession revoked from %(day)s.',
            day=fields.Date.to_string(day),
        ), concession=self, event_type='revoked')
        return True

    def _check_revoker(self):
        self.ensure_one()
        user = self.env.user
        if not user.has_group(FINANCE_MANAGER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to revoke this concession.'
            ))
        if user.has_group(APP_ADMIN_GROUP) and not user.has_group(FINANCE_MANAGER_GROUP):
            raise AccessError(self.env._(
                'Application administration is not commercial approval.'
            ))
        if user == self.version_id.approved_by_id:
            raise AccessError(self.env._(
                'The user who approved this concession cannot revoke it. '
                'An independent Finance Manager is required.'
            ))


class DiscountApproval(models.Model):
    """Discretionary concession or one transaction-scoped price override.

    Approval limits come from the approved contract version. An empty limit
    blocks approval. The client cannot supply the approver.
    """

    _name = 'cpla.discount.approval'
    _description = 'Discount Approval Request'
    _order = 'id desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    request_kind = fields.Selection(
        selection=[
            ('additional_concession', 'Additional concession'),
            ('transaction_override', 'Transaction price override'),
        ],
        required=True,
        default='transaction_override',
        index=True,
    )
    version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Contract Version',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        index=True,
        check_company=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        required=True,
        index=True,
        check_company=True,
    )
    concession_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage discount'),
            ('fixed_per_unit', 'Fixed amount per unit'),
            ('fixed_special_price', 'Fixed special price'),
            ('unsupported', 'Unsupported benefit'),
        ],
        string='Concession Type',
    )
    percent_exact = fields.Char(string='Percent')
    amount_exact = fields.Char(string='Amount')
    proposed_price_exact = fields.Char(string='Proposed Unit Price')
    currency_id = fields.Many2one('res.currency', string='Currency', ondelete='restrict')
    uom_id = fields.Many2one('uom.uom', string='Pricing Unit', ondelete='restrict')
    quantity_exact = fields.Char(string='Quantity')
    quantity_uom_id = fields.Many2one('uom.uom', string='Quantity Unit', ondelete='restrict')
    sale_reference = fields.Char(string='Sales Order Reference', index=True)
    sale_line_reference = fields.Char(string='Sales Order Line Reference', index=True)
    effective_from = fields.Date(string='Effective From')
    effective_to = fields.Date(string='Effective To')
    exclusive = fields.Boolean(string='Exclusive')
    precedence_rank = fields.Integer(string='Precedence')
    sequence = fields.Integer(default=10)
    reason = fields.Char(string='Reason')
    evidence_reference = fields.Char(string='Evidence Reference')
    requester_id = fields.Many2one('res.users', string='Requester', readonly=True, index=True)
    submitted_by_id = fields.Many2one('res.users', string='Submitted By', readonly=True)
    approver_id = fields.Many2one('res.users', string='Approver', readonly=True)
    approved_at = fields.Datetime(string='Approved At', readonly=True)
    rejected_by_id = fields.Many2one('res.users', string='Rejected By', readonly=True)
    rejection_reason = fields.Char(string='Rejection Reason')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
            ('superseded', 'Superseded'),
            ('revoked', 'Revoked'),
        ],
        default='draft',
        required=True,
        index=True,
        readonly=True,
    )
    baseline_unit_price_exact = fields.Char(string='Approved Baseline', readonly=True)
    exposure_exact = fields.Char(string='Exposure', readonly=True)
    exposure_currency_id = fields.Many2one('res.currency', string='Exposure Currency', readonly=True)
    snapshot_json = fields.Text(string='Approved Snapshot', readonly=True)
    limit_snapshot_json = fields.Text(string='Limit Snapshot', readonly=True)
    retroactive_granted = fields.Boolean(string='Retroactive Authority Granted', readonly=True)
    revocation_state = fields.Selection(
        selection=[
            ('none', 'Not revoked'),
            ('revoked', 'Revoked'),
            ('superseded', 'Superseded'),
        ],
        default='none',
        required=True,
    )
    revocation_effective_on = fields.Date(readonly=True)
    revoked_at = fields.Datetime(readonly=True)
    revoked_by_id = fields.Many2one('res.users', readonly=True)
    revocation_reason = fields.Char(readonly=True)
    revocation_retroactive = fields.Boolean(readonly=True)
    superseded_by_id = fields.Many2one('cpla.discount.approval', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        for vals in vals_list:
            vals = dict(vals)
            illegal = sorted(APPROVAL_SERVER_FIELDS & set(vals))
            if illegal:
                raise UserError(self.env._(
                    'Approval identity is server-controlled and was not written: %(fields)s.',
                    fields=', '.join(illegal),
                ))
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to prepare a discount request.'
                ))
            vals['requester_id'] = self.env.user.id
            vals['state'] = 'draft'
            cleaned.append(vals)
        records = super().create(cleaned)
        for record in records:
            record._check_company_links()
        return records

    def write(self, vals):
        self.check_access('write')
        illegal = sorted(APPROVAL_SERVER_FIELDS & set(vals))
        if illegal:
            raise UserError(self.env._(
                'Approval identity is server-controlled and was not written: %(fields)s.',
                fields=', '.join(illegal),
            ))
        rejection_only = (
            set(vals) <= {'rejection_reason'}
            and self.env.user.has_group(FINANCE_MANAGER_GROUP)
            and all(record.state == 'submitted' for record in self)
        )
        if not rejection_only and not self.env.user.has_group(USER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to change this discount request.'
            ))
        for record in self:
            if record.state != 'draft':
                if (
                    record.state == 'submitted'
                    and set(vals) <= {'rejection_reason'}
                    and self.env.user.has_group(FINANCE_MANAGER_GROUP)
                ):
                    continue
                raise UserError(self.env._(
                    'This discount request is no longer a draft. Approved terms were not overwritten.'
                ))
        written = super().write(vals)
        for record in self:
            record._check_company_links()
        return written

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        for record in self:
            if record.state != 'draft':
                raise UserError(self.env._(
                    'Only a draft discount request can be deleted.'
                ))
        return super().unlink()

    def _check_company_links(self):
        self.ensure_one()
        version = self.version_id
        if version.company_id != self.company_id:
            raise UserError(self.env._(
                'The contract version belongs to another company. The request was not saved.'
            ))
        if self.partner_id.company_id and self.partner_id.company_id != self.company_id:
            raise UserError(self.env._(
                'The customer belongs to another company. The request was not saved.'
            ))
        if self.product_id.company_id and self.product_id.company_id != self.company_id:
            raise UserError(self.env._(
                'The product belongs to another company. The request was not saved.'
            ))

    def action_submit(self):
        self.ensure_one()
        self.check_access('write')
        if self.state == 'submitted':
            return True
        if self.state != 'draft':
            raise UserError(self.env._(
                'Only a draft request can be submitted.'
            ))
        if self.env.user != self.requester_id and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._(
                'You can submit only your own discount request.'
            ))
        self._require_submission_details()
        self.lock_for_update()
        if self.state == 'submitted':
            return True
        models.Model.write(self, {
            'state': 'submitted',
            'submitted_by_id': self.env.user.id,
        })
        self.env['cpla.discount.event']._record(
            'Submitted for approval.',
            approval=self,
            event_type='submitted',
        )
        return True

    def _require_submission_details(self):
        self.ensure_one()
        missing = []
        if not (self.reason or '').strip():
            missing.append('reason')
        if not (self.evidence_reference or '').strip():
            missing.append('evidence')
        if self.version_id.state != 'approved':
            missing.append('approved contract version')
        if not self.partner_id or not self.product_id:
            missing.append('customer and product')
        if self.request_kind == 'transaction_override':
            if not (self.sale_reference or '').strip() or not (self.sale_line_reference or '').strip():
                missing.append('sales order and line reference')
            if _decimal(self.proposed_price_exact) is None:
                missing.append('proposed price')
            if _decimal(self.quantity_exact) is None or _decimal(self.quantity_exact) <= 0:
                missing.append('quantity')
            if not self.currency_id or not self.uom_id:
                missing.append('currency and unit')
        elif self.concession_type == 'percentage':
            percent = _decimal(self.percent_exact)
            if percent is None or percent <= 0 or percent >= 100:
                missing.append('percent')
        elif self.concession_type in ('fixed_per_unit', 'fixed_special_price'):
            if _decimal(self.amount_exact) is None or _decimal(self.amount_exact) <= 0:
                missing.append('amount')
            if not self.currency_id or not self.uom_id:
                missing.append('currency and unit')
        else:
            missing.append('supported concession type')
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            missing.append('valid effective dates')
        if missing:
            raise UserError(self.env._(
                'The request is incomplete (%(missing)s). It was not submitted and it was not approved.',
                missing=', '.join(missing),
            ))
        if self.partner_id != self.version_id.partner_id:
            raise UserError(self.env._(
                'The customer is not the customer on the approved contract version.'
            ))
        if self.product_id not in self.version_id.line_ids.product_id:
            raise UserError(self.env._(
                'The product variant is not on the approved contract version.'
            ))

    def action_approve(self):
        """Approve within the version limit. A repeated call does not grant twice."""
        self.ensure_one()
        self.check_access('read')
        self._check_approver()
        self.version_id.lock_for_update()
        self.lock_for_update()
        if self.state == 'approved':
            return True
        if self.state != 'submitted':
            raise UserError(self.env._(
                'Only a submitted request can be approved.'
            ))
        self.version_id.invalidate_recordset(['effective_status', 'authority_to'])
        if self.version_id.effective_status == 'superseded':
            raise UserError(self.env._(
                'This contract version is superseded. The request was not approved against the old version.'
            ))
        self._require_submission_details()
        if self.effective_from and self.effective_from < fields.Date.context_today(self):
            if self.version_id.retroactive_discount_authority != 'explicitly_allowed':
                raise UserError(self.env._(
                    'This effective date is retrospective. The contract version does not '
                    'authorize retroactive discount approval. The request stays submitted.'
                ))
        line = self.version_id.line_ids.filtered(lambda item: item.product_id == self.product_id)[:1]
        if not line:
            raise UserError(self.env._(
                'The approved version has no line for this product. No authority was granted.'
            ))
        evaluation = self.env['cpla.discount.evaluator'].evaluate(line, {
            'partner_id': self.partner_id.id,
            'product_id': self.product_id.id,
            'pricing_date': self.effective_from or fields.Date.context_today(self),
            'quantity': self.quantity_exact,
            'comparison_uom_id': self.uom_id.id,
            'baseline_only': True,
        })
        if evaluation.get('discount_status') not in AUTHORITATIVE:
            raise UserError(self.env._(
                'The approved baseline is not available (%(status)s). '
                'The request was not approved.',
                status=evaluation.get('discount_status') or 'missing',
            ))
        baseline = _decimal(evaluation.get('approved_adjusted_unit_price_exact'))
        if baseline is None or baseline <= 0:
            raise UserError(self.env._(
                'The approved baseline price is missing. The request was not approved.'
            ))
        self._check_limit(baseline, evaluation)
        self._check_conflict()
        proposed = self._approved_price_text(baseline)
        snapshot = {
            'request_kind': self.request_kind,
            'concession_type': self.concession_type or '',
            'percent_exact': self.percent_exact or '',
            'amount_exact': self.amount_exact or '',
            'proposed_price_exact': proposed,
            'currency_id': self.currency_id.id or 0,
            'uom_id': self.uom_id.id or 0,
            'quantity_exact': self.quantity_exact or '',
            'sale_reference': self.sale_reference or '',
            'sale_line_reference': self.sale_line_reference or '',
            'effective_from': fields.Date.to_string(self.effective_from) or '',
            'effective_to': fields.Date.to_string(self.effective_to) or '',
            'exclusive': bool(self.exclusive),
            'precedence_rank': self.precedence_rank or 0,
            'sequence': self.sequence or 0,
            'baseline_unit_price_exact': _text(baseline),
            'partner_id': self.partner_id.id,
            'product_id': self.product_id.id,
            'version_id': self.version_id.id,
        }
        limit_snapshot = {
            'authority_limit_basis': self.version_id.authority_limit_basis,
            'authority_max_percent_exact': self.version_id.authority_max_percent_exact or '',
            'authority_max_unit_reduction_exact': self.version_id.authority_max_unit_reduction_exact or '',
            'authority_max_exposure_exact': self.version_id.authority_max_exposure_exact or '',
            'authority_exposure_quantity_exact': self.version_id.authority_exposure_quantity_exact or '',
        }
        retroactive = bool(
            self.effective_from and self.effective_from < fields.Date.context_today(self)
        )
        models.Model.write(self, {
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approved_at': fields.Datetime.now(),
            'baseline_unit_price_exact': _text(baseline),
            'exposure_exact': self._exposure_text(baseline),
            'exposure_currency_id': evaluation.get('comparison_currency_id') or self.currency_id.id,
            'snapshot_json': json.dumps(snapshot, sort_keys=True),
            'limit_snapshot_json': json.dumps(limit_snapshot, sort_keys=True),
            'retroactive_granted': retroactive,
            'proposed_price_exact': proposed,
        })
        self.env['cpla.discount.event']._record(
            'Approved within the contract authority limit.',
            approval=self,
            event_type='approved',
        )
        return True

    def _approved_price_text(self, baseline):
        self.ensure_one()
        if self.request_kind == 'transaction_override':
            return self.proposed_price_exact
        if self.concession_type == 'fixed_special_price':
            return self.amount_exact
        return _text(baseline)

    def _exposure_text(self, baseline):
        self.ensure_one()
        if self.request_kind != 'transaction_override':
            proposed = self._concession_unit(baseline)
        else:
            proposed = _decimal(self.proposed_price_exact)
        quantity = _decimal(self.quantity_exact)
        if proposed is None or quantity is None:
            return False
        delta = _arithmetic('sub', baseline, proposed)
        if delta <= 0:
            return False
        return _text(_arithmetic('mul', delta, quantity))

    def _concession_unit(self, baseline):
        self.ensure_one()
        if self.concession_type == 'percentage':
            return _percent_of(baseline, _decimal(self.percent_exact))
        if self.concession_type == 'fixed_per_unit':
            amount = _decimal(self.amount_exact)
            if amount is None:
                return None
            return _arithmetic('sub', baseline, amount)
        if self.concession_type == 'fixed_special_price':
            return _decimal(self.amount_exact)
        return None

    def _check_limit(self, baseline, evaluation):
        self.ensure_one()
        version = self.version_id
        basis = version.authority_limit_basis
        if basis == 'unconfigured':
            raise UserError(self.env._(
                'No approval limit is stored on the approved contract version. '
                'Unlimited approval was not granted.'
            ))
        currency = self.env['res.currency'].browse(evaluation.get('comparison_currency_id')).exists()
        if self.currency_id and currency and self.currency_id != currency:
            raise UserError(self.env._(
                'The request currency does not match the approved comparison currency. '
                'The amounts were not compared directly.'
            ))
        line_uom = self.version_id.line_ids.filtered(
            lambda item: item.product_id == self.product_id
        )[:1].uom_id
        if self.uom_id and line_uom and self.uom_id != line_uom:
            raise UserError(self.env._(
                'The request unit does not match the approved contract unit. '
                'No unit conversion was invented for the approval limit.'
            ))
        if self.request_kind == 'transaction_override':
            proposed = _decimal(self.proposed_price_exact)
            quantity = _decimal(self.quantity_exact)
            if proposed is None or quantity is None or quantity <= 0:
                raise UserError(self.env._(
                    'The override quantity or price is incomplete. No exposure was invented.'
                ))
            delta = _arithmetic('sub', baseline, proposed)
            if delta <= 0:
                raise UserError(self.env._(
                    'The proposed price is not below the approved baseline. '
                    'It was not treated as a discount.'
                ))
            exposure = _arithmetic('mul', delta, quantity)
            self._assert_within_limit(basis, version, baseline, delta, exposure, quantity)
            return
        proposed = self._concession_unit(baseline)
        if proposed is None or proposed <= 0 or proposed >= baseline:
            raise UserError(self.env._(
                'The concession does not produce a positive price below the baseline. '
                'It was not approved.'
            ))
        delta = _arithmetic('sub', baseline, proposed)
        quantity = _decimal(self.quantity_exact)
        if basis == 'stated_exposure' and (quantity is None or quantity <= 0):
            raise UserError(self.env._(
                'The exposure limit needs a verified quantity. A forecast was not used.'
            ))
        exposure = _arithmetic('mul', delta, quantity) if quantity is not None else None
        self._assert_within_limit(basis, version, baseline, delta, exposure, quantity)

    def _assert_within_limit(self, basis, version, baseline, delta, exposure, quantity):
        if basis == 'per_unit_reduction':
            limit = _decimal(version.authority_max_unit_reduction_exact)
            if limit is None or limit <= 0:
                raise UserError(self.env._(
                    'The per-unit approval limit is missing. Unlimited approval was not granted.'
                ))
            if delta > limit:
                raise UserError(self.env._(
                    'The unit reduction is above the approved limit. The request was not approved.'
                ))
            return
        if basis == 'percent_reduction':
            limit = _decimal(version.authority_max_percent_exact)
            if limit is None or limit <= 0:
                raise UserError(self.env._(
                    'The percent approval limit is missing. Unlimited approval was not granted.'
                ))
            percent = _arithmetic('mul', _arithmetic('div', delta, baseline), HUNDRED)
            if percent > limit:
                raise UserError(self.env._(
                    'The percent reduction is above the approved limit. The request was not approved.'
                ))
            return
        if basis == 'stated_exposure':
            limit = _decimal(version.authority_max_exposure_exact)
            cap_quantity = _decimal(version.authority_exposure_quantity_exact)
            if limit is None or limit <= 0:
                raise UserError(self.env._(
                    'The exposure approval limit is missing. Unlimited approval was not granted.'
                ))
            if exposure is None:
                raise UserError(self.env._(
                    'Exposure cannot be calculated without a verified quantity.'
                ))
            if cap_quantity is not None and quantity is not None and quantity > cap_quantity:
                raise UserError(self.env._(
                    'The quantity is above the quantity named on the approval limit.'
                ))
            if version.authority_exposure_currency_id and self.currency_id and (
                version.authority_exposure_currency_id != self.currency_id
            ):
                raise UserError(self.env._(
                    'The exposure limit is in another currency. It was not compared without a rate.'
                ))
            if exposure > limit:
                raise UserError(self.env._(
                    'The exposure is above the approved limit. The request was not approved.'
                ))
            return
        raise UserError(self.env._(
            'The approval limit basis is not an approved rule. The request was not approved.'
        ))

    def _check_conflict(self):
        self.ensure_one()
        if self.request_kind != 'additional_concession' or not self.exclusive:
            if self.request_kind == 'transaction_override':
                existing = self.search([
                    ('id', '!=', self.id),
                    ('company_id', '=', self.company_id.id),
                    ('version_id', '=', self.version_id.id),
                    ('partner_id', '=', self.partner_id.id),
                    ('product_id', '=', self.product_id.id),
                    ('request_kind', '=', 'transaction_override'),
                    ('state', '=', 'approved'),
                    ('sale_reference', '=', self.sale_reference),
                    ('sale_line_reference', '=', self.sale_line_reference),
                ], limit=1)
                if existing:
                    raise UserError(self.env._(
                        'An override is already approved for this order line. '
                        'A second authority was not created.'
                    ))
            return
        rivals = self.search([
            ('id', '!=', self.id),
            ('company_id', '=', self.company_id.id),
            ('version_id', '=', self.version_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('product_id', '=', self.product_id.id),
            ('request_kind', '=', 'additional_concession'),
            ('exclusive', '=', True),
            ('state', '=', 'approved'),
        ])
        for rival in rivals:
            if not _dates_overlap(self.effective_from, self.effective_to, rival.effective_from, rival.effective_to):
                continue
            if not self.precedence_rank or not rival.precedence_rank or self.precedence_rank == rival.precedence_rank:
                raise UserError(self.env._(
                    'Another exclusive concession is already approved for this scope '
                    'and no precedence is stored. This request was not approved.'
                ))

    def _check_approver(self):
        self.ensure_one()
        user = self.env.user
        if not user.has_group(FINANCE_MANAGER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to approve this discount request.'
            ))
        if user == self.requester_id or user == self.submitted_by_id:
            raise AccessError(self.env._(
                'Self-approval is prohibited. The requester cannot approve this concession.'
            ))

    def action_reject(self, reason=None):
        self.ensure_one()
        self.check_access('read')
        if self.state == 'rejected':
            return True
        if self.state != 'submitted':
            raise UserError(self.env._('Only a submitted request can be rejected.'))
        if not self.env.user.has_group(FINANCE_MANAGER_GROUP):
            raise AccessError(self.env._('You are not allowed to reject this discount request.'))
        if self.env.user == self.requester_id:
            raise AccessError(self.env._(
                'The requester cannot reject this request in place of an approver.'
            ))
        text = (reason or self.rejection_reason or '').strip()
        if not text:
            raise UserError(self.env._('A rejection reason is required.'))
        self.lock_for_update()
        if self.state == 'rejected':
            return True
        models.Model.write(self, {
            'state': 'rejected',
            'rejected_by_id': self.env.user.id,
            'rejection_reason': text,
        })
        self.env['cpla.discount.event']._record(
            self.rejection_reason,
            approval=self,
            event_type='rejected',
        )
        return True

    def action_cancel(self):
        self.ensure_one()
        self.check_access('write')
        if self.state == 'cancelled':
            return True
        if self.state not in ('draft', 'submitted'):
            raise UserError(self.env._(
                'An approved request cannot be cancelled in place.'
            ))
        if self.env.user != self.requester_id and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._('You are not allowed to cancel this request.'))
        self.lock_for_update()
        models.Model.write(self, {'state': 'cancelled'})
        self.env['cpla.discount.event']._record(
            'Draft cancelled.',
            approval=self,
            event_type='cancelled',
        )
        return True

    def action_revoke(self, effective_on, reason, retroactive=False):
        self.ensure_one()
        user = self.env.user
        if not user.has_group(FINANCE_MANAGER_GROUP):
            raise AccessError(self.env._('You are not allowed to revoke this approval.'))
        if user == self.approver_id:
            raise AccessError(self.env._(
                'The approving user cannot revoke this approval.'
            ))
        if self.state != 'approved' or self.revocation_state != 'none':
            raise UserError(self.env._(
                'Only an open approved request can be revoked.'
            ))
        day = _as_date(effective_on)
        if not day or not (reason or '').strip():
            raise UserError(self.env._('Revocation needs an effective date and a reason.'))
        if retroactive and self.version_id.retroactive_discount_authority != 'explicitly_allowed':
            raise UserError(self.env._(
                'Retroactive revocation is not authorized. Earlier use was not reclassified.'
            ))
        if not retroactive and day < fields.Date.context_today(self):
            raise UserError(self.env._(
                'A prospective revocation cannot start in the past.'
            ))
        self.lock_for_update()
        models.Model.write(self, {
            'revocation_state': 'revoked',
            'revocation_effective_on': day,
            'revoked_at': fields.Datetime.now(),
            'revoked_by_id': user.id,
            'revocation_reason': reason.strip(),
            'revocation_retroactive': bool(retroactive),
        })
        self.env['cpla.discount.event']._record(
            'Approval revoked.',
            approval=self,
            event_type='revoked',
        )
        return True

    def action_view_history(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Approval History'),
            'res_model': 'cpla.discount.event',
            'view_mode': 'list,form',
            'domain': [('approval_id', '=', self.id)],
            'target': 'current',
        }


class DiscountEvent(models.Model):
    """Append-only approval history. Rows are not edited."""

    _name = 'cpla.discount.event'
    _description = 'Discount Approval Event'
    _order = 'occurred_at, id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True, index=True)
    approval_id = fields.Many2one(
        'cpla.discount.approval',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    concession_id = fields.Many2one(
        'cpla.discount.concession',
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    event_type = fields.Selection(
        selection=[
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
            ('revoked', 'Revoked'),
            ('superseded', 'Superseded'),
        ],
        required=True,
        index=True,
    )
    actor_id = fields.Many2one('res.users', required=True, index=True)
    occurred_at = fields.Datetime(required=True, index=True)
    note = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        for vals in vals_list:
            vals = dict(vals)
            approval = self.env['cpla.discount.approval'].browse(vals.get('approval_id')).exists()
            concession = self.env['cpla.discount.concession'].browse(vals.get('concession_id')).exists()
            parent_company = approval.company_id if approval else concession.company_id
            if not parent_company or parent_company not in self.env.companies:
                raise AccessError(self.env._(
                    'You are not allowed to record discount history for this company.'
                ))
            vals['company_id'] = parent_company.id
            vals['actor_id'] = self.env.user.id
            vals['occurred_at'] = fields.Datetime.now()
            self._assert_parent(vals, approval, concession)
            cleaned.append(vals)
        return super().create(cleaned)

    @api.model
    def _assert_parent(self, vals, approval, concession):
        event_type = vals.get('event_type')
        if approval:
            if self.search_count([
                ('approval_id', '=', approval.id),
                ('event_type', '=', event_type),
            ]):
                raise UserError(self.env._(
                    'This discount history event is already recorded.'
                ))
            allowed = {
                'submitted': approval.state == 'submitted' and approval.submitted_by_id == self.env.user,
                'approved': approval.state == 'approved' and approval.approver_id == self.env.user,
                'rejected': approval.state == 'rejected' and approval.rejected_by_id == self.env.user,
                'cancelled': approval.state == 'cancelled',
                'revoked': (
                    approval.revocation_state == 'revoked'
                    and approval.revoked_by_id == self.env.user
                ),
            }
            if not allowed.get(event_type):
                raise UserError(self.env._(
                    'This history event does not match the discount request. It was not recorded.'
                ))
            return
        if concession and event_type == 'revoked':
            if self.search_count([
                ('concession_id', '=', concession.id),
                ('event_type', '=', 'revoked'),
            ]):
                raise UserError(self.env._(
                    'This revocation is already recorded.'
                ))
            if concession.revocation_state != 'revoked' or concession.revoked_by_id != self.env.user:
                raise UserError(self.env._(
                    'Concession history can be recorded only by the user who revoked it.'
                ))
            return
        raise UserError(self.env._(
            'Discount history must follow an approval or a revocation. It was not recorded.'
        ))

    @api.model
    def _record(self, note, approval=None, concession=None, event_type='approved'):
        company = False
        if approval:
            company = approval.company_id
        elif concession:
            company = concession.company_id
        return self.create({
            'company_id': company.id,
            'approval_id': approval.id if approval else False,
            'concession_id': concession.id if concession else False,
            'event_type': event_type,
            'actor_id': self.env.user.id,
            'occurred_at': fields.Datetime.now(),
            'note': note,
        })

    def write(self, vals):
        raise UserError(self.env._('Discount approval history cannot be edited.'))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._('Discount approval history cannot be deleted.'))


class CustomerContractVersionDiscount(models.Model):
    _inherit = 'cpla.customer.contract.version'

    concession_ids = fields.One2many(
        'cpla.discount.concession',
        'version_id',
        string='Concessions',
    )
    discount_stacking_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('no_stacking', 'Do not combine'),
            ('exclusive_only', 'Exclusive concessions only'),
            ('additive_percentage', 'Additive percentages'),
            ('sequential_percentage', 'Sequential percentages'),
            ('percentage_then_fixed', 'Percentage, then fixed amount'),
            ('fixed_then_percentage', 'Fixed amount, then percentage'),
            ('fixed_price_replaces_base', 'Fixed special price replaces the base'),
            ('explicit_rule_order', 'Explicit sequence on each concession'),
        ],
        default='unconfigured',
        required=True,
        string='Discount stacking',
        help='Used only when this approved version names the mode. A company candidate is not a stacking rule. One concession does not need a mode. Two concessions without a mode stay in review.',
    )
    tier_discount_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('discount_after_tier', 'Apply the concession after the tier price'),
            ('exclusive_tier', 'Tier price excludes further concessions'),
        ],
        default='unconfigured',
        required=True,
        string='Tier and discount',
        help='When a tier matches and this clause is empty, a further concession stays in review.',
    )
    authority_limit_basis = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('per_unit_reduction', 'Maximum unit reduction'),
            ('percent_reduction', 'Maximum percent reduction'),
            ('stated_exposure', 'Stated exposure for a named quantity'),
        ],
        default='unconfigured',
        required=True,
        string='Discretionary approval limit',
        help='Empty means a later discretionary request cannot be approved. This is not a company-wide threshold.',
    )
    authority_max_percent_exact = fields.Char(string='Maximum percent')
    authority_max_unit_reduction_exact = fields.Char(string='Maximum unit reduction')
    authority_max_exposure_exact = fields.Char(string='Maximum exposure')
    authority_exposure_currency_id = fields.Many2one(
        'res.currency',
        string='Exposure currency',
        ondelete='restrict',
    )
    authority_exposure_quantity_exact = fields.Char(string='Exposure quantity')
    retroactive_discount_authority = fields.Selection(
        selection=[
            ('not_authorized', 'Not authorized'),
            ('explicitly_allowed', 'Explicitly allowed on this version'),
        ],
        default='not_authorized',
        required=True,
        string='Retroactive discount authority',
        help='This does not authorize a retroactive contract amendment. It covers only a later discount approval whose commercial date is earlier than the approval date.',
    )

    def create_amendment(self):
        new = super().create_amendment()
        new.write({
            'discount_stacking_policy': self.discount_stacking_policy,
            'tier_discount_policy': self.tier_discount_policy,
            'authority_limit_basis': self.authority_limit_basis,
            'authority_max_percent_exact': self.authority_max_percent_exact,
            'authority_max_unit_reduction_exact': self.authority_max_unit_reduction_exact,
            'authority_max_exposure_exact': self.authority_max_exposure_exact,
            'authority_exposure_currency_id': self.authority_exposure_currency_id.id,
            'authority_exposure_quantity_exact': self.authority_exposure_quantity_exact,
            'retroactive_discount_authority': self.retroactive_discount_authority,
        })
        for concession in self.concession_ids:
            self.env['cpla.discount.concession'].create(concession._copy_vals(new))
        return new

    def action_approve(self):
        self.ensure_one()
        if self.concession_ids:
            self.concession_ids.lock_for_update()
        return super().action_approve()

    def _apply_approval(self):
        for version in self:
            version._snapshot_concession_factors()
        return super()._apply_approval()

    def _snapshot_concession_factors(self):
        self.ensure_one()
        for concession in self.concession_ids:
            product_uom = concession.version_line_id.product_id.uom_id or (
                concession.product_id.uom_id if concession.product_id else False
            )
            values = {
                'concession_uom_factor_exact': _factor_text(concession.uom_id),
                'product_uom_factor_exact': _factor_text(product_uom),
            }
            models.Model.write(concession, values)

    def _readiness_messages(self):
        messages = super()._readiness_messages()
        messages.extend(self._discount_readiness_messages())
        return messages

    def _discount_readiness_messages(self):
        self.ensure_one()
        messages = []
        basis = self.authority_limit_basis
        if basis == 'per_unit_reduction' and not _positive(self.authority_max_unit_reduction_exact):
            messages.append(self.env._(
                'The per-unit approval limit is missing. No unlimited limit was stored.'
            ))
        if basis == 'percent_reduction' and not _positive(self.authority_max_percent_exact):
            messages.append(self.env._(
                'The percent approval limit is missing. No unlimited limit was stored.'
            ))
        if basis == 'stated_exposure':
            if not _positive(self.authority_max_exposure_exact) or not self.authority_exposure_currency_id:
                messages.append(self.env._(
                    'The exposure limit needs a positive amount and a currency.'
                ))
            if not _positive(self.authority_exposure_quantity_exact):
                messages.append(self.env._(
                    'The exposure limit needs the quantity it was approved against. A forecast was not stored.'
                ))
        for concession in self.concession_ids:
            issue = concession._shape_issue()
            if issue:
                messages.append(issue)
        return messages

    def _discount_signature(self):
        self.ensure_one()
        rows = []
        for concession in self.concession_ids.sorted(key=lambda item: (item.sequence, item.id)):
            rows.append({
                'sequence': concession.sequence,
                'type': concession.concession_type,
                'percent': concession.percent_exact or '',
                'amount': concession.amount_exact or '',
                'currency_id': concession.currency_id.id or 0,
                'uom_id': concession.uom_id.id or 0,
                'customer_scope': concession.customer_scope,
                'partner_id': concession.partner_id.id or 0,
                'product_scope': concession.product_scope,
                'product_id': concession.product_id.id or 0,
                'product_tmpl_id': concession.product_tmpl_id.id or 0,
                'line_product_id': concession.version_line_id.product_id.id or 0,
                'effective_from': fields.Date.to_string(concession.effective_from) or '',
                'effective_to': fields.Date.to_string(concession.effective_to) or '',
                'exclusive': bool(concession.exclusive),
                'precedence_rank': concession.precedence_rank or 0,
                'quantity_min': concession.quantity_min_exact or '',
                'quantity_max': concession.quantity_max_exact or '',
                'uom_factor': concession.concession_uom_factor_exact or '',
                'product_factor': concession.product_uom_factor_exact or '',
            })
        return {
            'stacking': self.discount_stacking_policy,
            'tier': self.tier_discount_policy,
            'limit': self.authority_limit_basis,
            'max_percent': self.authority_max_percent_exact or '',
            'max_unit': self.authority_max_unit_reduction_exact or '',
            'max_exposure': self.authority_max_exposure_exact or '',
            'exposure_currency_id': self.authority_exposure_currency_id.id or 0,
            'exposure_quantity': self.authority_exposure_quantity_exact or '',
            'retroactive': self.retroactive_discount_authority,
            'concessions': rows,
        }

    def _checksum(self, partner_name, covered_names):
        base = super()._checksum(partner_name, covered_names)
        payload = {
            'base': base,
            'discount_clause': self._discount_signature(),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def compare_with(self, other):
        result = super().compare_with(other)
        if self._discount_signature() != other._discount_signature():
            result['lines'].append(self._comparison_row(
                'Discount Clause Changed',
                'Concession, stacking, or approval-limit clause',
                False,
                False,
                None,
                True,
            ))
        return result


class PricingApplicabilityCheckDiscount(models.TransientModel):
    _inherit = 'cpla.pricing.applicability.check'

    discount_status = fields.Char(string='Discount Status', readonly=True)
    discount_reason = fields.Char(string='Discount Reason', readonly=True)
    approved_adjusted_unit_price_exact = fields.Char(
        string='Approved Adjusted Unit Price',
        readonly=True,
    )
    discount_applied = fields.Boolean(string='Discount Applied', readonly=True)
    price_exception_indicator = fields.Char(string='Price Exception', readonly=True)


class DiscountEvaluator(models.AbstractModel):
    """Read-only authorized discount evaluation.

    The starting price is the DEV-08 comparable unit. Company discount
    candidates are not rules. This service does not write approvals,
    invoices, or leakage findings.
    """

    _name = 'cpla.discount.evaluator'
    _description = 'Authorized Discount Evaluator'

    @api.model
    def blank(self):
        return {
            'discount_status': 'not_applicable',
            'discount_reason': 'not_applicable',
            'discount_applied': False,
            'pre_discount_unit_price_exact': False,
            'approved_adjusted_unit_price_exact': False,
            'concession_per_unit_exact': False,
            'authorized_concession_extended_exact': False,
            'gross_difference_extended_exact': False,
            'potential_unauthorized_extended_exact': False,
            'stacking_policy': False,
            'selected_concession_ids': [],
            'inapplicable_concession_ids': [],
            'approval_ids': [],
            'calculation_stages': [],
            'discount_trace': [],
            'historical_cutoff': False,
            'price_exception_indicator': False,
            'comparison_currency_id': False,
            'comparison_uom_id': False,
            'leakage_amount': False,
            'is_recovered_cash': False,
            'leakage_finding_created': False,
        }

    @api.model
    def evaluate(self, line, request=None):
        self._check_caller()
        request = dict(request or {})
        for key in FORGED_DISCOUNT_KEYS:
            request.pop(key, None)
        contractual_only = bool(request.pop('contractual_only', False))
        baseline_only = bool(request.pop('baseline_only', False))
        financial = self.env['cpla.pricing.financial'].normalize(line, request)
        result = self.blank()
        result['historical_cutoff'] = str(request.get('knowledge_cutoff') or '') or False
        if financial.get('financial_status') not in SUCCESS_FINANCIAL:
            if financial.get('financial_status') == 'COMPANY_ACCESS_DENIED':
                denied = self.blank()
                denied['discount_status'] = 'COMPANY_ACCESS_DENIED'
                denied['discount_reason'] = 'company_mismatch'
                denied['discount_trace'] = ['No price was returned.']
                return self._sealed(denied)
            result['discount_reason'] = financial.get('financial_reason') or 'pre_discount_not_normalized'
            result['discount_trace'] = [
                'No discount was applied because the pre-discount price is not normalized.',
            ]
            return self._sealed(result)
        base = _decimal(financial.get('comparable_unit_price_exact'))
        if base is None or base <= 0:
            result['discount_status'] = 'DISCOUNT_EVIDENCE_REVIEW_REQUIRED'
            result['discount_reason'] = 'pre_discount_missing'
            return self._sealed(result)
        result['pre_discount_unit_price_exact'] = _text(base)
        result['comparison_currency_id'] = financial.get('comparable_currency_id') or False
        quantity_result = self.env['cpla.pricing.quantity'].evaluate(line, request)
        target_uom_id = quantity_result.get('normalized_uom_id') or line.uom_id.id
        result['comparison_uom_id'] = target_uom_id
        version = line.version_id
        partner = self.env['res.partner'].browse(request.get('partner_id') or version.partner_id.id).exists()
        product = self.env['product.product'].browse(request.get('product_id') or line.product_id.id).exists()
        if not partner or not product:
            result['discount_status'] = 'DISCOUNT_EVIDENCE_REVIEW_REQUIRED'
            result['discount_reason'] = 'customer_or_product_missing'
            return self._sealed(result)
        if version.company_id not in self.env.companies or (
            request.get('company_id') and request.get('company_id') != version.company_id.id
        ):
            denied = self.blank()
            denied['discount_status'] = 'COMPANY_ACCESS_DENIED'
            denied['discount_reason'] = 'company_mismatch'
            denied['discount_trace'] = ['No price was returned.']
            return self._sealed(denied)
        pricing_date = _as_date(request.get('pricing_date')) or fields.Date.context_today(self)
        cutoff = _as_datetime(request.get('knowledge_cutoff'))
        tier_id = quantity_result.get('tier_id')
        if tier_id and version.tier_discount_policy == 'unconfigured' and version.concession_ids:
            scoped = self._scoped_concessions(
                version, line.product_id, partner, product, pricing_date, cutoff, request,
            )
            if scoped['applicable'] or scoped['unsupported']:
                result['discount_status'] = 'DISCOUNT_STACKING_REVIEW_REQUIRED'
                result['discount_reason'] = 'tier_discount_policy_missing'
                result['discount_trace'] = [
                    'A tier price and a concession both match. No combination rule is stored.',
                ]
                return self._sealed(result)
        if tier_id and version.tier_discount_policy == 'exclusive_tier':
            result.update(self._authoritative(
                'NO_ADDITIONAL_DISCOUNT',
                'exclusive_tier',
                base,
                base,
                version,
                [],
                ['The tier price excludes a further concession.'],
            ))
            return self._with_actual(result, request, base)
        prepared = self._prepare_concessions(
            version, line.product_id, partner, product, pricing_date, cutoff, request,
            base, target_uom_id, financial,
        )
        if prepared.get('stop'):
            result.update(prepared['stop'])
            return self._sealed(result)
        rows = list(prepared['rows'])
        if not contractual_only and not (request.get('sale_reference') or request.get('sale_line_reference')):
            extra = self._approval_rows(
                version, partner, product, pricing_date, cutoff, baseline_only=baseline_only,
            )
            if extra.get('stop') and not rows:
                result.update(extra['stop'])
                return self._sealed(result)
            rows.extend(extra.get('rows') or [])
        contractual = self._combine(version, base, rows, financial, request)
        contractual['comparison_currency_id'] = financial.get('comparable_currency_id') or False
        contractual['approval_ids'] = [row['approval_id'] for row in rows if row.get('approval_id')]
        if contractual.get('discount_status') not in AUTHORITATIVE:
            result.update(contractual)
            return self._sealed(result)
        if contractual_only:
            result.update(contractual)
            return self._with_actual(result, request, base)
        override = self._apply_override(
            version, partner, product, pricing_date, cutoff, request, contractual, base,
        )
        contractual_concession = (
            contractual.get('discount_status') in AUTHORITATIVE
            and contractual.get('discount_status') != 'NO_ADDITIONAL_DISCOUNT'
        )
        if override and (
            override.get('discount_status') in AUTHORITATIVE or not contractual_concession
        ):
            result.update(override)
        else:
            result.update(contractual)
            if override and override.get('discount_trace'):
                result['discount_trace'] = (result.get('discount_trace') or []) + override['discount_trace']
        if result.get('discount_status') in AUTHORITATIVE:
            return self._with_actual(result, request, base)
        return self._sealed(result)

    @api.model
    def _check_caller(self):
        # Same technical-superuser rule as the applicability resolver.
        if self.env.su:
            return
        user = self.env.user
        if not any(user.has_group(group) for group in READ_GROUPS):
            raise AccessError(self.env._(
                'You are not allowed to evaluate authorized discounts.'
            ))

    @api.model
    def _sealed(self, result):
        result['leakage_amount'] = False
        result['is_recovered_cash'] = False
        result['leakage_finding_created'] = False
        result['discount_applied'] = bool(
            result.get('discount_applied') and result.get('discount_status') in AUTHORITATIVE
        )
        if result.get('discount_status') not in AUTHORITATIVE:
            result['approved_adjusted_unit_price_exact'] = False
            result['discount_applied'] = False
        return result

    @api.model
    def _authoritative(self, status, reason, base, adjusted, version, stages, trace, selected=None):
        concession = _arithmetic('sub', base, adjusted)
        return {
            'discount_status': status,
            'discount_reason': reason,
            'discount_applied': status != 'NO_ADDITIONAL_DISCOUNT',
            'approved_adjusted_unit_price_exact': _text(adjusted),
            'concession_per_unit_exact': _text(concession),
            'stacking_policy': version.discount_stacking_policy,
            'selected_concession_ids': selected or [],
            'calculation_stages': stages,
            'discount_trace': trace,
        }

    @api.model
    def _scoped_concessions(self, version, line_product, partner, product, pricing_date, cutoff, request):
        rows = version.concession_ids.sorted(key=lambda item: (item.sequence, item.id))
        applicable = []
        mismatched = []
        expired = []
        future = []
        unsupported = []
        quantity_missing = []
        for concession in rows:
            if not self._known(concession, version, cutoff):
                continue
            if self._revoked_for(concession, pricing_date, cutoff):
                continue
            targets_line = self._product_match(concession, line_product)
            targets_request = self._product_match(concession, product)
            if not targets_line and not targets_request:
                continue
            if not targets_request or not self._customer_match(concession, version, partner):
                mismatched.append(concession)
                continue
            if concession.concession_type == 'unsupported':
                unsupported.append(concession)
                continue
            window = self._window(concession, version)
            if pricing_date < window[0]:
                future.append(concession)
                continue
            if window[1] and pricing_date > window[1]:
                expired.append(concession)
                continue
            quantity_state = self._quantity_state(concession, request)
            if quantity_state == 'missing':
                quantity_missing.append(concession)
                continue
            if quantity_state == 'out':
                mismatched.append(concession)
                continue
            applicable.append(concession)
        return {
            'applicable': applicable,
            'mismatched': mismatched,
            'expired': expired,
            'future': future,
            'unsupported': unsupported,
            'quantity_missing': quantity_missing,
        }

    @api.model
    def _known(self, concession, version, cutoff):
        if not cutoff:
            return True
        approved_at = version.approved_at
        return bool(approved_at and approved_at <= cutoff)

    @api.model
    def _revoked_for(self, concession, pricing_date, cutoff):
        if concession.revocation_state == 'none':
            return False
        if cutoff and concession.revoked_at and concession.revoked_at > cutoff:
            return False
        day = concession.revocation_effective_on
        if not day:
            return False
        return pricing_date >= day

    @api.model
    def _product_match(self, concession, product):
        if concession.product_scope == 'version_line':
            line = concession.version_line_id
            return bool(line and line.product_id == product)
        if concession.product_scope == 'exact_variant':
            return concession.product_id == product
        if concession.product_scope == 'product_template':
            return bool(
                concession.product_tmpl_id
                and product.product_tmpl_id == concession.product_tmpl_id
            )
        return False

    @api.model
    def _customer_match(self, concession, version, partner):
        if concession.customer_scope == 'version_customer':
            return partner == version.partner_id
        if concession.customer_scope == 'exact_partner':
            return bool(concession.partner_id and partner == concession.partner_id)
        return False

    @api.model
    def _window(self, concession, version):
        start = concession.effective_from or version.effective_from
        end = concession.effective_to or version.authority_to or version.valid_to
        return start, end

    @api.model
    def _quantity_state(self, concession, request):
        if not concession.quantity_min_exact and not concession.quantity_max_exact:
            return 'ok'
        quantity = _decimal(request.get('quantity'))
        if quantity is None:
            return 'missing'
        if concession.quantity_uom_id and request.get('quantity_uom_id') not in (
            False, None, concession.quantity_uom_id.id,
        ):
            return 'missing'
        minimum = _decimal(concession.quantity_min_exact) or ZERO
        if quantity < minimum:
            return 'out'
        maximum = _decimal(concession.quantity_max_exact)
        if maximum is not None and quantity >= maximum:
            return 'out'
        return 'ok'

    @api.model
    def _prepare_concessions(
        self, version, line_product, partner, product, pricing_date, cutoff, request,
        base, target_uom_id, financial,
    ):
        scoped = self._scoped_concessions(
            version, line_product, partner, product, pricing_date, cutoff, request,
        )
        if scoped['unsupported']:
            return {'stop': self._review(
                'UNSUPPORTED_CONCESSION_TYPE',
                'unsupported_benefit',
                ['An unsupported benefit matches this scope. It was not converted into a unit discount.'],
                [item.id for item in scoped['unsupported']],
            )}
        if not scoped['applicable']:
            if scoped['quantity_missing']:
                return {'stop': self._review(
                    'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                    'quantity_missing',
                    ['A quantity-qualified concession has no verified quantity. No amount was invented.'],
                    [item.id for item in scoped['quantity_missing']],
                )}
            if scoped['future']:
                return {'stop': self._review(
                    'DISCOUNT_NOT_YET_EFFECTIVE',
                    'future_effective',
                    ['The concession is approved and is not yet effective on the pricing date.'],
                    [item.id for item in scoped['future']],
                )}
            if scoped['expired']:
                return {'stop': self._review(
                    'DISCOUNT_EXPIRED',
                    'expired',
                    ['The concession end date is before the pricing date. It was not applied.'],
                    [item.id for item in scoped['expired']],
                )}
            if scoped['mismatched']:
                return {'stop': self._review(
                    'DISCOUNT_SCOPE_MISMATCH',
                    'scope_mismatch',
                    ['A concession on this version does not cover this customer, product, or quantity.'],
                    [item.id for item in scoped['mismatched']],
                )}
            entered = request.get('entered_discount_percent') or request.get('entered_unit_price_exact')
            if entered:
                return {'stop': self._review(
                    'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                    'entered_discount_without_approval',
                    ['A discount was supplied without an approved concession. It was not authorized.'],
                    [],
                )}
            return {'rows': []}
        rows = []
        for concession in scoped['applicable']:
            prepared = self._normalize_concession(
                concession, base, target_uom_id, version, financial, request,
            )
            if prepared.get('stop'):
                return prepared
            rows.append(prepared['row'])
        return {'rows': rows}

    @api.model
    def _normalize_concession(self, concession, base, target_uom_id, version, financial, request):
        if concession.concession_type == 'percentage':
            percent = _decimal(concession.percent_exact)
            return {'row': {
                'id': concession.id,
                'kind': 'percentage',
                'percent': percent,
                'sequence': concession.sequence,
                'exclusive': concession.exclusive,
                'precedence_rank': concession.precedence_rank or 0,
                'source': 'concession:%s' % concession.id,
            }}
        amount = _decimal(concession.amount_exact)
        currency = self.env['res.currency'].browse(financial.get('comparable_currency_id')).exists()
        comparable = self._to_comparison_amount(
            amount, concession, target_uom_id, version, currency, financial, request,
        )
        if comparable.get('stop'):
            return comparable
        return {'row': {
            'id': concession.id,
            'kind': concession.concession_type,
            'amount': comparable['amount'],
            'sequence': concession.sequence,
            'exclusive': concession.exclusive,
            'precedence_rank': concession.precedence_rank or 0,
            'source': 'concession:%s' % concession.id,
        }}

    @api.model
    def _to_comparison_amount(self, amount, concession, target_uom_id, version, currency, financial, request):
        if amount is None or amount <= 0 or not concession.uom_id or not concession.currency_id or not currency:
            return {'stop': self._review(
                'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                'concession_currency_or_uom_missing',
                ['The concession currency or unit is missing. No conversion was invented.'],
                [concession.id],
            )}
        source_factor = _decimal(concession.concession_uom_factor_exact)
        if concession.uom_id.id == target_uom_id:
            per_target = amount
        else:
            target_factor = _decimal(concession.product_uom_factor_exact)
            if target_uom_id != (concession.version_line_id.product_id.uom_id.id or 0):
                return {'stop': self._review(
                    'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                    'concession_uom_not_snapshotted',
                    ['The concession unit and the comparison unit differ, and no snapshot covers that pair.'],
                    [concession.id],
                )}
            if source_factor is None or target_factor is None or source_factor <= 0 or target_factor <= 0:
                return {'stop': self._review(
                    'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                    'concession_uom_factor_missing',
                    ['The historical unit factor is missing. The live unit was not reread.'],
                    [concession.id],
                )}
            converted = self.env['cpla.pricing.quantity'].convert_price(
                _text(amount), _text(source_factor), _text(target_factor),
            )
            if not converted.get('ok'):
                return {'stop': self._review(
                    'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                    'concession_uom_not_converted',
                    ['The concession unit could not be converted with the snapshotted factors.'],
                    [concession.id],
                )}
            per_target = _decimal(converted['exact'])
        if concession.currency_id == currency:
            return {'amount': per_target}
        converted = self.env['cpla.pricing.financial']._convert_clause(
            per_target, concession.currency_id, currency, version, request,
        )
        if converted.get('error'):
            return {'stop': self._review(
                'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                'concession_fx_missing',
                ['The concession currency has no approved rate onto the comparison currency.'],
                [concession.id],
            )}
        return {'amount': converted['amount']}

    @api.model
    def _combine(self, version, base, rows, financial, request):
        if not rows:
            trace = ['No additional approved concession applies.']
            return self._authoritative(
                'NO_ADDITIONAL_DISCOUNT', 'no_additional_discount', base, base, version, [], trace,
            )
        exclusive = [row for row in rows if row['exclusive']]
        if exclusive:
            chosen = self._choose_exclusive(exclusive)
            if chosen.get('stop'):
                return chosen['stop']
            rows = chosen['rows']
            return self._apply_rows(version, base, rows, 'exclusive_concession', financial, request)
        if len(rows) == 1:
            return self._apply_rows(version, base, rows, 'single_concession', financial, request)
        mode = version.discount_stacking_policy
        if mode in ('unconfigured', 'no_stacking', 'exclusive_only'):
            return self._review(
                'DISCOUNT_STACKING_REVIEW_REQUIRED',
                'stacking_policy_missing',
                ['More than one concession matches and this version does not name a combination rule.'],
                [row['id'] for row in rows],
            )
        return self._apply_rows(version, base, rows, mode, financial, request)

    @api.model
    def _choose_exclusive(self, rows):
        if len(rows) == 1:
            return {'rows': rows}
        ranks = [row['precedence_rank'] for row in rows]
        if any(not rank for rank in ranks) or len(set(ranks)) != len(ranks):
            return {'stop': self._review(
                'DISCOUNT_AUTHORITY_CONFLICT',
                'exclusive_without_precedence',
                ['Two exclusive concessions match and no unique precedence is stored. The lower price was not selected.'],
                [row['id'] for row in rows],
            )}
        winner = sorted(rows, key=lambda row: (row['precedence_rank'], row['sequence'], row['id']))[0]
        return {'rows': [winner]}

    @api.model
    def _apply_rows(self, version, base, rows, mode, financial, request):
        ordered = sorted(rows, key=lambda row: (row['sequence'], row['id']))
        if mode in ('exclusive_concession', 'single_concession'):
            mode = self._single_mode(ordered[0])
        try:
            adjusted, stages = self._run_mode(base, ordered, mode)
        except UserError as error:
            return self._review(
                'DISCOUNT_STACKING_REVIEW_REQUIRED',
                'stacking_not_applicable',
                [str(error)],
                [row['id'] for row in ordered],
            )
        if adjusted is None or adjusted <= 0:
            return self._review(
                'DISCOUNT_PRICE_INVALID',
                'non_positive_price',
                ['The concession would remove the selling price. No negative price was authorized.'],
                [row['id'] for row in ordered],
            )
        rounded = self.env['cpla.pricing.financial']._apply_rounding(
            adjusted, self.env['res.currency'].browse(financial.get('comparable_currency_id')), version, request,
        )
        if rounded.get('error'):
            return self._review(
                'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                'rounding_not_applied',
                ['The approved rounding stage could not be applied to the adjusted price.'],
                [row['id'] for row in ordered],
            )
        final_amount = _decimal(rounded['unit_exact'])
        status = 'SPECIAL_PRICE_APPLICABLE' if any(
            row['kind'] == 'fixed_special_price' for row in ordered
        ) and len(ordered) == 1 else 'AUTHORIZED_PRICE_RESOLVED'
        trace = ['Approved stacking mode %s.' % mode, rounded['trace']]
        return self._authoritative(
            status,
            mode,
            base,
            final_amount,
            version,
            stages,
            trace,
            [row['id'] for row in ordered],
        )

    @api.model
    def _single_mode(self, row):
        if row['kind'] == 'fixed_special_price':
            return 'fixed_price_replaces_base'
        if row['kind'] == 'percentage':
            return 'sequential_percentage'
        return 'fixed_then_percentage'

    @api.model
    def _run_mode(self, base, rows, mode):
        if mode == 'sequential_percentage':
            self._require_kinds(rows, {'percentage'})
            running = base
            stages = []
            for row in rows:
                running = _percent_of(running, row['percent'])
                stages.append(self._stage(row, running))
            return running, stages
        if mode == 'additive_percentage':
            self._require_kinds(rows, {'percentage'})
            total = ZERO
            for row in rows:
                total = _arithmetic('add', total, row['percent'])
            if total <= 0 or total >= 100:
                return None, []
            running = _percent_of(base, total)
            return running, [self._stage(row, running) for row in rows]
        if mode == 'percentage_then_fixed':
            self._require_kinds(rows, {'percentage', 'fixed_per_unit'})
            running = base
            stages = []
            for row in rows:
                if row['kind'] != 'percentage':
                    continue
                running = _percent_of(running, row['percent'])
                stages.append(self._stage(row, running))
            for row in rows:
                if row['kind'] != 'fixed_per_unit':
                    continue
                running = _arithmetic('sub', running, row['amount'])
                stages.append(self._stage(row, running))
            return running, stages
        if mode == 'fixed_then_percentage':
            self._require_kinds(rows, {'percentage', 'fixed_per_unit'})
            running = base
            stages = []
            for row in rows:
                if row['kind'] != 'fixed_per_unit':
                    continue
                running = _arithmetic('sub', running, row['amount'])
                stages.append(self._stage(row, running))
            for row in rows:
                if row['kind'] != 'percentage':
                    continue
                running = _percent_of(running, row['percent'])
                stages.append(self._stage(row, running))
            return running, stages
        if mode == 'fixed_price_replaces_base':
            specials = [row for row in rows if row['kind'] == 'fixed_special_price']
            if len(specials) != 1 or len(rows) != 1:
                raise UserError(self.env._(
                    'A fixed special price replaces the base only when it is the only selected concession.'
                ))
            return specials[0]['amount'], [self._stage(specials[0], specials[0]['amount'])]
        if mode == 'explicit_rule_order':
            sequences = [row['sequence'] for row in rows]
            if len(set(sequences)) != len(sequences):
                raise UserError(self.env._(
                    'Explicit rule order needs a unique sequence on every concession.'
                ))
            running = base
            stages = []
            for row in rows:
                if row['kind'] == 'percentage':
                    running = _percent_of(running, row['percent'])
                elif row['kind'] == 'fixed_per_unit':
                    running = _arithmetic('sub', running, row['amount'])
                elif row['kind'] == 'fixed_special_price':
                    running = row['amount']
                else:
                    raise UserError(self.env._('This concession type is not in the explicit order.'))
                stages.append(self._stage(row, running))
            return running, stages
        raise UserError(self.env._('This stacking mode is not an approved rule.'))

    @api.model
    def _require_kinds(self, rows, allowed):
        found = {row['kind'] for row in rows}
        if not found <= allowed:
            raise UserError(self.env._(
                'The concessions are not all of the type this stacking mode can combine.'
            ))

    @api.model
    def _stage(self, row, running):
        return {
            'source': row['source'],
            'kind': row['kind'],
            'running_exact': _text(running),
        }

    @api.model
    def _review(self, status, reason, trace, concession_ids):
        return {
            'discount_status': status,
            'discount_reason': reason,
            'discount_applied': False,
            'approved_adjusted_unit_price_exact': False,
            'selected_concession_ids': [],
            'inapplicable_concession_ids': concession_ids,
            'calculation_stages': [],
            'discount_trace': trace,
            'stacking_policy': False,
        }

    @api.model
    def _apply_override(self, version, partner, product, pricing_date, cutoff, request, contractual, base):
        reference = (request.get('sale_reference') or '').strip()
        line_reference = (request.get('sale_line_reference') or '').strip()
        if not reference or not line_reference:
            return None
        overrides = self._matching_approvals(version, partner, product, 'transaction_override')
        matched = overrides.filtered(
            lambda item: (item.sale_reference or '') == reference
            and (item.sale_line_reference or '') == line_reference
        )
        if not matched:
            return None
        usable = []
        expired = []
        pending = []
        rejected = []
        for approval in matched:
            if approval.state == 'submitted':
                pending.append(approval)
                continue
            if approval.state == 'rejected':
                rejected.append(approval)
                continue
            if approval.state != 'approved':
                continue
            if cutoff and (not approval.approved_at or approval.approved_at > cutoff):
                continue
            if approval.revocation_state != 'none':
                if not (cutoff and approval.revoked_at and approval.revoked_at > cutoff):
                    day = approval.revocation_effective_on
                    if day and pricing_date >= day:
                        expired.append(approval)
                        continue
            window_start = approval.effective_from or version.effective_from
            window_end = approval.effective_to
            if pricing_date < window_start:
                continue
            if window_end and pricing_date > window_end:
                expired.append(approval)
                continue
            if not approval.retroactive_granted and approval.effective_from and approval.approved_at:
                if approval.effective_from < fields.Date.to_date(approval.approved_at) and cutoff is None:
                    pass
            quantity = _decimal(request.get('quantity'))
            allowed = _decimal(approval.quantity_exact)
            if quantity is None or allowed is None or quantity <= 0 or quantity > allowed:
                return self._review(
                    'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                    'override_quantity_not_covered',
                    ['The override does not cover this quantity. A larger quantity was not authorized.'],
                    [],
                )
            usable.append(approval)
        if len(usable) > 1:
            return self._review(
                'DISCOUNT_AUTHORITY_CONFLICT',
                'duplicate_override',
                ['More than one override matches this order line. No price was selected.'],
                [],
            )
        if len(usable) == 1:
            approval = usable[0]
            price = _decimal(approval.proposed_price_exact)
            if price is None or price <= 0:
                return self._review(
                    'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                    'override_price_missing',
                    ['The approved override price is missing.'],
                    [],
                )
            rounded = self.env['cpla.pricing.financial']._apply_rounding(
                price,
                self.env['res.currency'].browse(contractual.get('comparison_currency_id')),
                version,
                request,
            )
            if rounded.get('error'):
                return self._review(
                    'DISCOUNT_EVIDENCE_REVIEW_REQUIRED',
                    'override_rounding_missing',
                    ['The override could not be rounded with the approved stage.'],
                    [],
                )
            final_amount = _decimal(rounded['unit_exact'])
            payload = self._authoritative(
                'APPROVED_OVERRIDE_APPLICABLE',
                'transaction_override',
                base,
                final_amount,
                version,
                [{'source': 'approval:%s' % approval.id, 'kind': 'transaction_override', 'running_exact': _text(final_amount)}],
                ['Approved transaction override applied for the named order line only.'],
            )
            payload['approval_ids'] = [approval.id]
            payload['comparison_currency_id'] = contractual.get('comparison_currency_id')
            return payload
        if pending:
            return self._review(
                'DISCOUNT_APPROVAL_PENDING',
                'override_pending',
                ['A matching override is still submitted. The proposed price was not used.'],
                [],
            )
        if rejected:
            stopped = self._review(
                'DISCOUNT_APPROVAL_REJECTED',
                'override_rejected',
                ['A matching override was rejected. The proposed price was not used.'],
                [],
            )
            stopped['approval_ids'] = [item.id for item in rejected]
            return stopped
        if expired:
            return self._review(
                'DISCOUNT_EXPIRED',
                'override_expired',
                ['The matching override is outside its effective dates.'],
                [],
            )
        return None

    @api.model
    def _approval_rows(self, version, partner, product, pricing_date, cutoff, baseline_only=False):
        approvals = self._matching_approvals(version, partner, product, 'additional_concession')
        considered = []
        pending = []
        rejected = []
        for approval in approvals:
            if approval.state == 'submitted':
                pending.append(approval)
                continue
            if approval.state == 'rejected':
                rejected.append(approval)
                continue
            if approval.state != 'approved':
                continue
            if self._approval_revoked(approval, pricing_date, cutoff):
                continue
            if cutoff and (not approval.approved_at or approval.approved_at > cutoff):
                continue
            start = approval.effective_from or version.effective_from
            end = approval.effective_to or version.authority_to or version.valid_to
            if start and pricing_date < start:
                continue
            if end and pricing_date > end:
                continue
            if approval.retroactive_granted and cutoff and approval.approved_at > cutoff:
                continue
            considered.append(approval)
        if baseline_only:
            pending = []
            rejected = []
        if pending and not considered:
            return {'stop': self._review(
                'DISCOUNT_APPROVAL_PENDING',
                'concession_pending',
                ['A concession request is submitted and is not approved.'],
                [],
            )}
        if rejected and not considered:
            return {'stop': self._review(
                'DISCOUNT_APPROVAL_REJECTED',
                'concession_rejected',
                ['The matching concession request was rejected.'],
                [],
            )}
        rows = []
        for approval in considered:
            kind = approval.concession_type
            if kind not in ('percentage', 'fixed_per_unit', 'fixed_special_price'):
                continue
            row = {
                'id': approval.id,
                'approval_id': approval.id,
                'kind': kind,
                'sequence': approval.sequence,
                'exclusive': approval.exclusive,
                'precedence_rank': approval.precedence_rank or 0,
                'source': 'approval:%s' % approval.id,
            }
            if kind == 'percentage':
                row['percent'] = _decimal(approval.percent_exact)
            else:
                row['amount'] = _decimal(approval.amount_exact)
            rows.append(row)
        return {'rows': rows}

    @api.model
    def _approval_revoked(self, approval, pricing_date, cutoff):
        if approval.revocation_state == 'none':
            return False
        if cutoff and approval.revoked_at and approval.revoked_at > cutoff:
            return False
        day = approval.revocation_effective_on
        if not day:
            return True
        return pricing_date >= day

    @api.model
    def _matching_approvals(self, version, partner, product, kind):
        return self.env['cpla.discount.approval'].search([
            ('company_id', '=', version.company_id.id),
            ('version_id', '=', version.id),
            ('partner_id', '=', partner.id),
            ('product_id', '=', product.id),
            ('request_kind', '=', kind),
            ('state', 'in', ('submitted', 'approved', 'rejected')),
        ])

    @api.model
    def _with_actual(self, result, request, base):
        result = self._sealed(result)
        if result.get('discount_status') not in AUTHORITATIVE:
            return result
        adjusted = _decimal(result.get('approved_adjusted_unit_price_exact'))
        quantity = _decimal(request.get('quantity'))
        if adjusted is not None and quantity is not None and quantity > 0:
            result['authorized_concession_extended_exact'] = _text(
                _arithmetic('mul', _arithmetic('sub', base, adjusted), quantity)
            )
        actual = _decimal(request.get('actual_unit_price_exact'))
        if actual is None or adjusted is None:
            return result
        if quantity is not None and quantity > 0:
            result['gross_difference_extended_exact'] = _text(
                _arithmetic('mul', _arithmetic('sub', base, actual), quantity)
            )
        gap = _arithmetic('sub', adjusted, actual)
        if gap > 0:
            result['price_exception_indicator'] = 'UNAUTHORIZED_DISCOUNT_INDICATOR'
            if quantity is not None and quantity > 0:
                result['potential_unauthorized_extended_exact'] = _text(
                    _arithmetic('mul', gap, quantity)
                )
        else:
            result['potential_unauthorized_extended_exact'] = False
            result['price_exception_indicator'] = False
        return self._sealed(result)


def _percent_of(base, percent):
    rate = _arithmetic('div', percent, HUNDRED)
    keep = _arithmetic('sub', Decimal(1), rate)
    return _arithmetic('mul', base, keep)


def _positive(value):
    number = _decimal(value)
    return number is not None and number > 0


def _factor_text(uom):
    if not uom or not uom.factor or uom.factor <= 0:
        return False
    number = _decimal(uom.factor)
    if number is None or number <= 0:
        return False
    return _text(number)


def _dates_overlap(start_a, end_a, start_b, end_b):
    left = start_a or fields.Date.from_string('1970-01-01')
    right = start_b or fields.Date.from_string('1970-01-01')
    if end_a and right > end_a:
        return False
    if end_b and left > end_b:
        return False
    return True
