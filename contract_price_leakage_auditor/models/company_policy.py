from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.sql import create_index

MODULE = 'contract_price_leakage_auditor'


class CompanyPolicy(models.Model):
    """Company-owned policy revisions for later contract comparison.

    Draft selections are candidates only. Open business decisions block
    operational approval. This model does not store contracts, invoices,
    leakage cases, or recovery documents.
    """

    _name = 'cpla.company.policy'
    _description = 'Contract Price Leakage Company Policy'
    _order = 'company_id, version desc, id desc'
    _rec_name = 'name'

    OPEN_DECISIONS = (
        ('DEC-01', 'Pricing date'),
        ('DEC-02', 'Contract precedence'),
        ('DEC-03', 'Customer coverage'),
        ('DEC-04', 'Quantity basis'),
        ('DEC-05', 'Discount stacking'),
        ('DEC-06', 'Historical foreign exchange'),
        ('DEC-07', 'Tax basis'),
        ('DEC-08', 'Rounding and tolerance'),
        ('DEC-11', 'Recovery authority'),
        ('DEC-12', 'Waiver authority'),
    )
    CONFLICT_CODE = 'CONTRACT_CONFLICT_REVIEW_REQUIRED'
    PRICING_DATE_CODE = 'PRICING_DATE_POLICY_REQUIRES_APPROVAL'
    CONTRACT_PRIORITY_RULE = (
        'CONTRACT_SPECIFIC_TERMS_MAY_OVERRIDE_THE_COMPANY_DEFAULT_ONLY_AFTER_A_LATER_APPROVED_CONTRACT'
    )
    VALID = 'VALID'
    WARNING = 'WARNING'
    REVIEW_REQUIRED = 'REVIEW_REQUIRED'
    BLOCKING = 'BLOCKING_CONFIGURATION_ERROR'
    POLICY_FIELDS = (
        'pricing_date_policy',
        'contract_precedence_policy',
        'customer_coverage_policy',
        'quantity_basis_policy',
        'discount_approval_policy',
        'fx_basis_policy',
        'tax_comparison_policy',
        'monetary_precision_policy',
        'tolerance_policy',
        'missing_evidence_policy',
        'quotation_compliance_mode',
    )
    SENSITIVE_FIELDS = frozenset({
        'discount_approval_policy',
        'fx_basis_policy',
        'tax_comparison_policy',
        'monetary_precision_policy',
        'tolerance_policy',
    })
    READER_GROUPS = (
        f'{MODULE}.group_contract_manager,'
        f'{MODULE}.group_finance_reviewer,'
        f'{MODULE}.group_internal_auditor,'
        f'{MODULE}.group_app_admin'
    )
    SENSITIVE_GROUPS = (
        f'{MODULE}.group_finance_reviewer,'
        f'{MODULE}.group_finance_manager,'
        f'{MODULE}.group_internal_auditor,'
        f'{MODULE}.group_app_admin'
    )
    GOLDEN_FIXTURES = (
        {
            'code': 'GOLD-FIN-001',
            'approved_price': 1150.0,
            'invoice_price': 1100.0,
            'quantity': 500.0,
            'expected_difference': 25000.0,
        },
        {
            'code': 'GOLD-FIN-003',
            'box_price': 120.0,
            'pieces_per_box': 10.0,
            'fx_rate': 84.0,
            'discount_rate': 0.05,
            'invoice_piece_price': 950.0,
            'quantity': 100.0,
            'expected_difference': 760.0,
        },
        {
            'code': 'GOLD-FIN-004',
            'box_price': 2400.0,
            'pieces_per_box': 12.0,
            'invoice_piece_price': 190.0,
            'quantity': 100.0,
            'expected_difference': 1000.0,
        },
        {
            'code': 'GOLD-FIN-005',
            'expected_net_price': 1000.0,
            'invoice_net_price': 900.0,
            'quantity': 100.0,
            'expected_difference': 10000.0,
        },
    )

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        ondelete='restrict',
    )
    version = fields.Integer(required=True, default=1, readonly=True, copy=False)
    is_current = fields.Boolean(
        string='Current revision',
        default=True,
        index=True,
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        selection=[
            ('not_configured', 'Not configured'),
            ('draft', 'Draft configuration'),
            ('review_required', 'Review required'),
            ('ready_for_business_review', 'Ready for business review'),
            ('approved_ready', 'Approved ready'),
        ],
        required=True,
        default='not_configured',
        copy=False,
        help='Approved ready cannot be selected while business decisions are open. Ready for business review means a person must review those decisions. It is not operational approval.',
    )
    supersedes_id = fields.Many2one(
        'cpla.company.policy',
        string='Supersedes',
        ondelete='restrict',
        index=True,
        copy=False,
        check_company=True,
        readonly=True,
    )
    revision_ids = fields.One2many(
        'cpla.company.policy',
        'supersedes_id',
        string='Later revisions',
    )
    effective_from = fields.Date(string='Effective from')
    effective_to = fields.Date(string='Effective to')
    change_reason = fields.Text(required=True, string='Change reason')
    requested_by = fields.Many2one('res.users', string='Requested by', ondelete='restrict', readonly=True)
    requested_on = fields.Datetime(string='Requested on', default=fields.Datetime.now, readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', string='Approved by', readonly=True, copy=False, ondelete='restrict')
    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Company currency',
        readonly=True,
    )
    pricing_date_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('order_confirmation', 'Sales order confirmation date'),
            ('delivery', 'Delivery date'),
            ('invoice', 'Customer invoice date'),
            ('contract_specific', 'Contract-specific date rule'),
            ('custom_rule', 'Explicit custom rule'),
        ],
        default='unconfigured',
        required=True,
        string='Pricing date basis',
        help='A selected candidate is stored on the draft only. It is not an approved pricing-date policy. Invoice date is not a default.',
    )
    contract_precedence_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('exact_customer', 'Exact customer agreement'),
            ('customer_group', 'Customer-group agreement'),
            ('product_specific', 'Product-specific agreement'),
            ('special_price', 'Approved special-price agreement'),
            ('historical_amendment', 'Historical amendment'),
        ],
        default='unconfigured',
        required=True,
        string='Contract precedence candidate',
        help='This does not choose the lowest or highest price. Unresolved overlap stays in review.',
    )
    customer_coverage_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('exact_customer', 'Exact customer'),
            ('authorized_parent', 'Authorized parent company'),
            ('covered_branches', 'Covered branches'),
            ('covered_subsidiaries', 'Covered subsidiaries'),
            ('customer_group', 'Explicit customer group'),
        ],
        default='unconfigured',
        required=True,
        string='Customer coverage candidate',
        help='A child contact does not automatically inherit a parent contract.',
    )
    quantity_basis_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('sales_order', 'Sales order quantity'),
            ('invoice', 'Invoice quantity'),
            ('delivery', 'Delivery quantity'),
            ('period_volume', 'Contract-period accumulated volume'),
            ('customer_group', 'Customer-group quantity'),
        ],
        default='unconfigured',
        required=True,
        string='Quantity qualification candidate',
        help='This candidate is not the contract quantity rule. An approved version line records its own basis. The candidate is not operationally approved.',
    )
    discount_approval_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('approval_reference_required', 'Approval reference required'),
        ],
        default='unconfigured',
        required=True,
        string='Discount approval candidate',
        groups=SENSITIVE_GROUPS,
        help='No stacking rule and no discount amount are stored.',
    )
    fx_basis_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('pricing_date', 'Contract pricing date'),
            ('order_date', 'Sales order date'),
            ('invoice_date', 'Invoice date'),
            ('fixed_rate', 'Contractually fixed rate'),
            ('historical_rate', 'Approved historical rate'),
        ],
        default='unconfigured',
        required=True,
        string='Historical FX candidate',
        groups=SENSITIVE_GROUPS,
        help='No exchange rate is stored. A current rate is not substituted for missing history. A fixed-rate candidate does not authorize a number.',
    )
    tax_comparison_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('tax_excluded', 'Tax-exclusive prices'),
            ('tax_included', 'Tax-inclusive prices'),
            ('normalize_required', 'Normalization required before comparison'),
        ],
        default='unconfigured',
        required=True,
        string='Tax comparison candidate',
        groups=SENSITIVE_GROUPS,
        help='Tax-inclusive and tax-exclusive prices are not treated as comparable. This module does not calculate tax.',
    )
    monetary_precision_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('company_currency_rounding', 'Use company currency rounding'),
        ],
        default='unconfigured',
        required=True,
        string='Monetary precision candidate',
        groups=SENSITIVE_GROUPS,
        help='Company currency rounding is a draft technical preference. It does not approve a tolerance and it does not round a material difference to zero.',
    )
    tolerance_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('do_not_suppress', 'Do not suppress differences'),
        ],
        default='unconfigured',
        required=True,
        string='Leakage tolerance candidate',
        groups=SENSITIVE_GROUPS,
        help='No numeric tolerance is stored. Missing and explicit do-not-suppress both leave differences visible.',
    )
    quotation_compliance_mode = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('disabled', 'Diagnostic only'),
            ('warning', 'Warn and allow confirmation'),
            ('approval_required', 'Approval required for a price reduction'),
            ('block', 'Block unresolved pricing exceptions'),
        ],
        default='unconfigured',
        required=True,
        string='Quotation compliance mode',
        help=(
            'Company confirmation control for sales quotations. It does not approve a price, '
            'store a tolerance, or recover cash. Unconfigured does not grant a free pass for a '
            'detected price reduction, and it is not a universal block of ordinary sales.'
        ),
    )
    missing_evidence_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('review_required', 'Review required'),
        ],
        default='unconfigured',
        required=True,
        string='Missing evidence candidate',
        help='Missing evidence stays in review. It does not become a confirmed price.',
    )
    operationally_approved = fields.Boolean(
        string='Operationally approved',
        compute='_compute_operationally_approved',
        help='Stays false while business decisions are open. Technical completeness is not approval.',
    )
    conflict_behavior = fields.Char(
        string='Conflict behavior',
        compute='_compute_fixed_rules',
    )
    contract_priority_rule = fields.Char(
        string='Contract priority rule',
        compute='_compute_fixed_rules',
    )
    packaging_rule = fields.Char(
        string='Packaging rule',
        compute='_compute_fixed_rules',
    )
    open_decision_text = fields.Text(
        string='Open decisions',
        compute='_compute_open_decision_text',
    )
    readiness_display = fields.Text(
        string='Configuration readiness',
        compute='_compute_readiness_display',
    )

    def init(self):
        create_index(
            self.env.cr,
            'cpla_company_policy_one_current_idx',
            self._table,
            ['company_id'],
            unique=True,
            where='is_current',
        )

    @api.depends('company_id', 'version')
    def _compute_name(self):
        for policy in self:
            policy.name = '%s policy v%s' % (policy.company_id.name or '', policy.version or 0)

    @api.depends('state')
    def _compute_operationally_approved(self):
        for policy in self:
            policy.operationally_approved = False

    @api.depends('state')
    def _compute_fixed_rules(self):
        for policy in self:
            policy.conflict_behavior = self.CONFLICT_CODE
            policy.contract_priority_rule = self.CONTRACT_PRIORITY_RULE
            policy.packaging_rule = 'PACKAGING_UOM_IS_NOT_A_PRICE_UNIT'

    @api.depends('state')
    def _compute_open_decision_text(self):
        text = '\n'.join(
            '%s: %s — not approved' % (code, label)
            for code, label in self.OPEN_DECISIONS
        )
        for policy in self:
            policy.open_decision_text = text

    @api.depends(
        'state', 'version', 'company_id', 'effective_from', 'effective_to',
        'pricing_date_policy', 'contract_precedence_policy',
        'customer_coverage_policy', 'quantity_basis_policy',
        'missing_evidence_policy',
    )
    def _compute_readiness_display(self):
        for policy in self:
            if not policy.company_id:
                policy.readiness_display = (
                    'Select a company. This policy is not operationally approved.'
                )
                continue
            policy.readiness_display = policy._format_readiness(
                policy.get_configuration_readiness()
            )

    @api.constrains('effective_from', 'effective_to')
    def _check_effective_range(self):
        for policy in self:
            if (
                policy.effective_from
                and policy.effective_to
                and policy.effective_to < policy.effective_from
            ):
                raise ValidationError(self.env._(
                    'The effective end date is before the effective start date.'
                ))

    @api.constrains('is_current', 'company_id')
    def _check_one_current(self):
        for policy in self.filtered('is_current'):
            duplicate = self.search([
                ('id', '!=', policy.id),
                ('company_id', '=', policy.company_id.id),
                ('is_current', '=', True),
            ], limit=1)
            if duplicate:
                raise ValidationError(self.env._(
                    'Company %(company)s already has a current policy revision.',
                    company=policy.company_id.display_name,
                ))

    @api.constrains('state')
    def _check_state_not_approved(self):
        if any(policy.state == 'approved_ready' for policy in self):
            raise UserError(self.env._(
                'Approved ready is refused while pricing decisions are open. No approved revision was stored.'
            ))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_editor()
        cleaned = []
        for incoming in vals_list:
            vals = dict(incoming)
            company = self.env['res.company'].browse(vals.get('company_id'))
            self._check_target_company(company)
            if not (vals.get('change_reason') or '').strip():
                raise ValidationError(self.env._(
                    'A change reason is required. An empty reason is not stored.'
                ))
            if vals.get('state') in (
                'approved_ready',
                'ready_for_business_review',
                'review_required',
            ):
                raise UserError(self.env._(
                    'This state cannot be set on a new revision. Activation is refused.'
                ))
            if vals.get('is_current') is False:
                raise UserError(self.env._(
                    'A new policy revision must be the current revision.'
                ))
            current = self.search([
                ('company_id', '=', company.id),
                ('is_current', '=', True),
            ], limit=1)
            if current:
                raise ValidationError(self.env._(
                    'Company %(company)s already has a current policy revision.',
                    company=company.display_name,
                ))
            last = self.search([
                ('company_id', '=', company.id),
            ], order='version desc', limit=1)
            vals['version'] = (last.version if last else 0) + 1
            vals['is_current'] = True
            vals['approved_by'] = False
            vals['state'] = self._state_from_values(vals)
            if not vals.get('requested_by'):
                vals['requested_by'] = self.env.user.id
            self._check_requested_user(
                self.env['res.users'].browse(vals['requested_by']),
                company,
            )
            self._check_dates(None, vals)
            cleaned.append(vals)
        return super().create(cleaned)

    def write(self, vals):
        self._check_editor()
        vals = dict(vals)
        if 'state' in vals:
            raise UserError(self.env._(
                'Policy state is not written directly. Use the review action. Activation is refused.'
            ))
        blocked = {
            'company_id', 'version', 'is_current', 'supersedes_id',
            'approved_by', 'requested_on', 'name', 'operationally_approved',
        }
        illegal = sorted(blocked & set(vals))
        if illegal:
            raise UserError(self.env._(
                'These fields are controlled by the revision process: %(fields)s.',
                fields=', '.join(illegal),
            ))
        for record in self:
            if not record.is_current:
                raise UserError(self.env._(
                    'Historical policy revisions are frozen.'
                ))
            self._check_dates(record, vals)
            if 'requested_by' in vals:
                if not vals['requested_by']:
                    raise ValidationError(self.env._(
                        'The requesting user is required.'
                    ))
                self._check_requested_user(
                    self.env['res.users'].browse(vals['requested_by']),
                    record.company_id,
                )
        watched = set(self.POLICY_FIELDS) | {
            'change_reason', 'effective_from', 'effective_to',
        }
        if len(self) > 1 and (watched & set(vals)):
            for record in self:
                record.write(dict(vals))
            return True
        if watched & set(vals):
            vals['state'] = self._merged_state(self, vals)
        return super().write(vals)

    def unlink(self):
        if self.env.context.get('_force_unlink') and self.env.su:
            return super().unlink()
        raise UserError(self.env._(
            'Policy revisions cannot be deleted. Create a new revision. A database administrator can still change rows outside the application.'
        ))

    def copy(self, default=None):
        raise UserError(self.env._(
            'Duplicate the policy through a new revision. Copying would create a second current revision.'
        ))

    def action_submit_for_review(self):
        self._check_editor()
        for policy in self:
            if not policy.is_current:
                raise UserError(self.env._(
                    'Only the current revision can be submitted for business review.'
                ))
            if not (policy.change_reason or '').strip():
                raise ValidationError(self.env._(
                    'A change reason is required before business review.'
                ))
        super().write({'state': 'ready_for_business_review'})
        return True

    def action_new_revision(self):
        self._check_editor()
        self.ensure_one()
        if not self.is_current:
            raise UserError(self.env._(
                'Only the current revision can start a new revision.'
            ))
        vals = {
            'company_id': self.company_id.id,
            'change_reason': self.env._(
                'Revision of version %(version)s. This draft is not approved.',
                version=self.version,
            ),
            'supersedes_id': self.id,
            'effective_from': self.effective_from,
            'effective_to': self.effective_to,
        }
        for field_name in self.POLICY_FIELDS:
            vals[field_name] = self[field_name]
        with self.env.cr.savepoint():
            self._freeze_current()
            new = self.create(vals)
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Company policy revision'),
            'res_model': self._name,
            'res_id': new.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_request_activation(self):
        """Refuse activation. Open decisions are not an approval."""
        self.ensure_one()
        if not self.is_current:
            raise UserError(self.env._(
                'Only the current revision can be checked for activation.'
            ))
        if not self.env.su and not self.env.user.has_group(f'{MODULE}.group_finance_manager'):
            raise AccessError(self.env._(
                'Only a Finance Manager can request activation. The Application Administrator is not a commercial approver.'
            ))
        if self.requested_by and self.requested_by == self.env.user:
            raise AccessError(self.env._(
                'The requesting user cannot approve the same policy revision.'
            ))
        if not self.env.su and self.company_id not in self.env.user.company_ids:
            raise AccessError(self.env._(
                'The policy company is outside this user\'s companies.'
            ))
        codes = ', '.join(code for code, _label in self.OPEN_DECISIONS)
        raise UserError(self.env._(
            'Activation is refused. These decisions are not approved: %(codes)s. No approved revision was created.',
            codes=codes,
        ))

    def check_approval_reference(self, user):
        self.ensure_one()
        self._check_reader()
        if isinstance(user, int):
            user = self.env['res.users'].browse(user)
        if not user or self.company_id not in user.company_ids:
            raise ValidationError(self.env._(
                'Cross-company approval reference is rejected.'
            ))
        raise UserError(self.env._(
            'An approval reference does not grant financial authority. DEC-11 and DEC-12 are open. No approval limit was stored.'
        ))

    def get_configuration_readiness(self):
        self.ensure_one()
        self._check_reader()
        missing = []
        invalid = []
        warnings = []
        candidates = {}
        if not self.effective_from:
            missing.append('effective_from')
        if not self.effective_to:
            missing.append('effective_to')
        currency = self.company_id.currency_id
        if not currency:
            missing.append('company_currency')
        elif not currency.active:
            invalid.append('company_currency_inactive')
        for field_name in self.POLICY_FIELDS:
            value = self._policy_value(field_name)
            if value is None:
                warnings.append('%s is restricted for this role' % field_name)
                continue
            candidates[field_name] = value
            if value == 'unconfigured':
                missing.append(field_name)
            else:
                warnings.append(
                    '%s is a draft candidate and is not an approved policy' % field_name
                )
        blocking = [
            '%s is not approved. %s.' % (code, label)
            for code, label in self.OPEN_DECISIONS
        ]
        codes = [code for code, _label in self.OPEN_DECISIONS]
        codes.append(self.CONFLICT_CODE)
        codes.append(self.PRICING_DATE_CODE)
        return {
            'company_id': self.company_id.id,
            'company_name': self.company_id.name,
            'validated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'revision': self.version,
            'policy_id': self.id,
            'state': self.state,
            'is_current': self.is_current,
            'operationally_approved': False,
            'missing': missing,
            'invalid': invalid,
            'blocking': blocking,
            'warnings': warnings,
            'candidates': candidates,
            'next_action': (
                'A business owner must resolve the open decisions before any policy can be approved. '
                'Technical completeness is not approval.'
            ),
            'codes': codes,
        }

    def validate_currency(self, currency):
        self.ensure_one()
        self._check_reader()
        if not currency:
            return self._result(
                self.BLOCKING,
                'CURRENCY_MISSING',
                'The currency reference is missing.',
                fx_basis='MISSING',
                activated=False,
                rates_created=False,
            )
        if not currency.active:
            return self._result(
                self.BLOCKING,
                'CURRENCY_INACTIVE',
                'An inactive currency is not activated by this check.',
                fx_basis='MISSING',
                activated=False,
                rates_created=False,
            )
        fx_value = self._policy_value('fx_basis_policy')
        if fx_value in (None, 'unconfigured'):
            fx_basis = 'MISSING'
            message = 'The currency exists and is active. The historical FX basis is missing.'
        else:
            fx_basis = 'DRAFT_NOT_APPROVED'
            message = 'The currency exists and is active. The FX candidate is not an approved policy.'
        return self._result(
            self.VALID,
            'CURRENCY_REFERENCE_OK',
            message,
            fx_basis=fx_basis,
            activated=False,
            rates_created=False,
        )

    def assess_monetary_difference(self, difference, currency=None):
        self.ensure_one()
        self._check_reader()
        currency = currency or self.company_currency_id
        if not currency:
            raise ValidationError(self.env._('The company currency is missing.'))
        return {
            'rounded_difference': currency.round(difference),
            'suppressed': False,
            'operationally_approved': False,
            'audited': False,
        }

    @api.model
    def propose_tolerance(self, amount):
        self._check_reader()
        if amount is None:
            return 'unconfigured'
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise ValidationError(self.env._('Tolerance must be a number. No tolerance was stored.'))
        if amount < 0:
            raise ValidationError(self.env._(
                'A negative tolerance is rejected. No tolerance was stored.'
            ))
        raise UserError(self.env._(
            'DEC-08 is open. A numeric tolerance is not stored, so a difference cannot be suppressed.'
        ))

    @api.model
    def propose_fixed_rate(self, rate):
        self._check_reader()
        raise UserError(self.env._(
            'DEC-06 is open. A fixed exchange rate is not stored, and a current rate is not substituted.'
        ))

    @api.model
    def classify_exchange_difference(self, source):
        self._check_reader()
        if source == 'payment_date':
            return self._result(
                self.REVIEW_REQUIRED,
                'PAYMENT_FX_NOT_CONTRACT_LEAKAGE',
                'A payment-date exchange gain or loss is not contract price leakage.',
                pricing_leakage=False,
            )
        if source in (
            'pricing_date', 'order_date', 'invoice_date', 'fixed_rate', 'historical_rate',
        ):
            return self._result(
                self.REVIEW_REQUIRED,
                'FX_POLICY_NOT_APPROVED',
                'This exchange-rate source is not an approved policy.',
                pricing_leakage=False,
            )
        return self._result(
            self.BLOCKING,
            'FX_SOURCE_UNKNOWN',
            'The exchange-rate source is not a recognized policy candidate.',
            pricing_leakage=False,
        )

    @api.model
    def classify_tax_bases(self, left, right):
        self._check_reader()
        known = {'tax_excluded', 'tax_included'}
        if left not in known or right not in known:
            return self._result(
                self.REVIEW_REQUIRED,
                'TAX_BASIS_UNKNOWN',
                'The tax basis is not verified. Product tax and fiscal position are not inferred.',
                comparable=False,
            )
        if left != right:
            return self._result(
                self.REVIEW_REQUIRED,
                'TAX_INCLUSIVE_EXCLUSIVE_NOT_COMPARABLE',
                'Tax-inclusive and tax-exclusive prices are not compared directly.',
                comparable=False,
            )
        return self._result(
            self.REVIEW_REQUIRED,
            'TAX_TREATMENT_UNVERIFIED',
            'The same tax label is still not an approved tax policy. DEC-07 is open.',
            comparable=False,
        )

    @api.model
    def validate_customer(self, partner, company):
        self._check_reader()
        if not partner or not company:
            return self._result(
                self.BLOCKING,
                'CUSTOMER_OR_COMPANY_MISSING',
                'The customer and company are required.',
                inherits_parent_contract=False,
                coverage_approved=False,
            )
        try:
            owner = partner.company_id
            parent = partner.parent_id
            commercial = partner.commercial_partner_id
            active = partner.active
        except AccessError:
            return self._result(
                self.BLOCKING,
                'CUSTOMER_NOT_ACCESSIBLE',
                'The customer cannot be read in this company scope.',
                inherits_parent_contract=False,
                coverage_approved=False,
            )
        if owner and owner not in company.parent_ids:
            return self._result(
                self.BLOCKING,
                'WRONG_COMPANY_CUSTOMER',
                'The customer belongs to another company and is not a shared contact.',
                inherits_parent_contract=False,
                coverage_approved=False,
            )
        if not active:
            return self._result(
                self.REVIEW_REQUIRED,
                'ARCHIVED_CUSTOMER_RETAINED',
                'An archived customer is retained for historical review and is not deleted.',
                inherits_parent_contract=False,
                coverage_approved=False,
            )
        if parent or (commercial and commercial != partner):
            return self._result(
                self.REVIEW_REQUIRED,
                'CHILD_CONTACT_DOES_NOT_INHERIT_CONTRACT',
                'A child contact or address does not inherit the parent contract.',
                inherits_parent_contract=False,
                coverage_approved=False,
            )
        if not owner:
            return self._result(
                self.WARNING,
                'SHARED_CUSTOMER_NO_CONTRACT_INHERITANCE',
                'A shared contact is visible to more than one company. That does not grant contract inheritance.',
                inherits_parent_contract=False,
                coverage_approved=False,
            )
        return self._result(
            self.VALID,
            'CUSTOMER_IDENTITY_OK',
            'The customer identity is usable for a later coverage decision. Coverage is not approved.',
            inherits_parent_contract=False,
            coverage_approved=False,
        )

    @api.model
    def validate_product(self, product, company):
        self._check_reader()
        if not product or not company:
            return self._result(
                self.BLOCKING,
                'PRODUCT_OR_COMPANY_MISSING',
                'The product and company are required.',
            )
        if product._name not in ('product.product', 'product.template'):
            return self._result(
                self.BLOCKING,
                'PRODUCT_MODEL_UNSUPPORTED',
                'The record is not a product template or variant.',
            )
        try:
            template = product if product._name == 'product.template' else product.product_tmpl_id
            owner = template.company_id
            variant_count = template.product_variant_count
            active = product.active
            uom = template.uom_id
        except AccessError:
            return self._result(
                self.BLOCKING,
                'PRODUCT_NOT_ACCESSIBLE',
                'The product cannot be read in this company scope.',
            )
        if owner and owner not in company.parent_ids:
            return self._result(
                self.BLOCKING,
                'WRONG_COMPANY_PRODUCT',
                'The product belongs to another company.',
            )
        if product._name == 'product.template' and variant_count != 1:
            return self._result(
                self.REVIEW_REQUIRED,
                'AMBIGUOUS_PRODUCT_VARIANT',
                'The product template has more than one variant. Choose a variant.',
            )
        if not active:
            return self._result(
                self.REVIEW_REQUIRED,
                'ARCHIVED_PRODUCT_RETAINED',
                'An archived product is retained for historical review and is not deleted.',
            )
        if not uom:
            return self._result(
                self.BLOCKING,
                'MISSING_UOM',
                'The product has no unit of measure.',
            )
        if not owner:
            return self._result(
                self.WARNING,
                'SHARED_PRODUCT_NO_CONTRACT_INHERITANCE',
                'A shared product is visible to more than one company. That does not grant a contract price.',
            )
        return self._result(
            self.VALID,
            'PRODUCT_IDENTITY_OK',
            'The product identity and default unit are usable. No contract price was selected.',
        )

    @api.model
    def validate_products(self, products, company):
        self._check_reader()
        return [self.validate_product(product, company) for product in products]

    @api.model
    def validate_uom_conversion(self, from_uom, to_uom):
        self._check_reader()
        if not from_uom or not to_uom:
            return self._result(
                self.BLOCKING,
                'MISSING_UOM',
                'Both units of measure are required.',
            )
        for uom in (from_uom, to_uom):
            if uom.relative_factor is None or uom.relative_factor <= 0:
                return self._result(
                    self.BLOCKING,
                    'INVALID_CONVERSION_FACTOR',
                    'A zero or negative conversion factor is rejected.',
                )
            if uom.id and not uom.active:
                return self._result(
                    self.BLOCKING,
                    'INACTIVE_UOM',
                    'An inactive unit is not activated by this check.',
                )
        if not from_uom._has_common_reference(to_uom):
            return self._result(
                self.BLOCKING,
                'INCOMPATIBLE_UOM',
                'The units do not share a reference unit. No conversion was invented.',
            )
        quantity = from_uom._compute_quantity(1.0, to_uom, round=False)
        if not quantity or quantity <= 0:
            return self._result(
                self.BLOCKING,
                'INVALID_CONVERSION_FACTOR',
                'The conversion quantity is not positive.',
            )
        return self._result(
            self.VALID,
            'UOM_CONVERSION_OK',
            'The units share a reference unit.',
            quantity=quantity,
        )

    @api.model
    def classify_pricing_unit(self, product, pricing_uom):
        self._check_reader()
        if not product or product._name not in ('product.product', 'product.template'):
            return self._result(
                self.BLOCKING,
                'PRODUCT_OR_COMPANY_MISSING',
                'A product is required before its pricing unit can be classified.',
            )
        template = product if product._name == 'product.template' else product.product_tmpl_id
        if not pricing_uom:
            return self._result(self.BLOCKING, 'MISSING_UOM', 'The pricing unit is missing.')
        if pricing_uom == template.uom_id:
            return self._result(
                self.VALID,
                'DEFAULT_PRICE_UOM',
                'The pricing unit is the product default unit.',
            )
        if pricing_uom in template.uom_ids:
            return self._result(
                self.REVIEW_REQUIRED,
                'PACKAGING_UOM_NOT_PRICE_UNIT',
                'Odoo 19 stores extra sales packagings on the product unit list. That packaging unit is not the default price unit, and there is no product.packaging model in this Community build.',
            )
        conversion = self.validate_uom_conversion(template.uom_id, pricing_uom)
        if conversion['classification'] != self.VALID:
            return conversion
        return self._result(
            self.REVIEW_REQUIRED,
            'EXPLICIT_UOM_NOT_THE_DEFAULT_PRICE_UNIT',
            'A compatible unit is not automatically the contract price unit.',
            quantity=conversion.get('quantity'),
        )

    @api.model
    def golden_fixture_reference(self):
        """Return preserved reference numbers. This does not audit invoices."""
        self._check_reader()
        return {
            'audited': False,
            'implemented': False,
            'fixtures': [dict(row) for row in self.GOLDEN_FIXTURES],
        }

    def _freeze_current(self):
        self.ensure_one()
        if not self.is_current:
            raise UserError(self.env._('Only the current revision can be frozen.'))
        super().write({'is_current': False})

    def _check_editor(self):
        if self.env.su:
            return
        if not self.env.user.has_group(f'{MODULE}.group_app_admin'):
            raise AccessError(self.env._(
                'Only an Application Administrator can edit a draft policy. This is not commercial approval.'
            ))

    def _check_reader(self):
        if self.env.su:
            return
        if not self.env.user.has_groups(self.READER_GROUPS):
            raise AccessError(self.env._(
                'You cannot read company policy or run a readiness check.'
            ))

    def _check_target_company(self, company):
        if not company or not company.exists():
            raise ValidationError(self.env._('A company is required.'))
        if self.env.su:
            return
        if company not in self.env.user.company_ids:
            raise AccessError(self.env._(
                'You cannot configure a company that is not assigned to you.'
            ))
        if company not in self.env.companies:
            raise AccessError(self.env._(
                'You cannot configure a company that is not in the active company selection.'
            ))

    def _check_requested_user(self, user, company):
        if not user:
            raise ValidationError(self.env._('The requesting user is required.'))
        if company in user.company_ids:
            return
        if self.env.su and user == self.env.user:
            return
        raise ValidationError(self.env._(
            'The requesting user is not a member of %(company)s. Cross-company references are rejected.',
            company=company.display_name,
        ))

    def _check_dates(self, record, vals):
        start = vals['effective_from'] if 'effective_from' in vals else (
            record.effective_from if record else False
        )
        end = vals['effective_to'] if 'effective_to' in vals else (
            record.effective_to if record else False
        )
        start = fields.Date.to_date(start) if start else False
        end = fields.Date.to_date(end) if end else False
        if start and end and end < start:
            raise ValidationError(self.env._(
                'The effective end date is before the effective start date.'
            ))

    @api.model
    def _state_from_values(self, vals):
        for field_name in self.POLICY_FIELDS:
            if vals.get(field_name, 'unconfigured') not in (False, 'unconfigured'):
                return 'draft'
        return 'not_configured'

    def _merged_state(self, record, vals):
        for field_name in self.POLICY_FIELDS:
            value = vals[field_name] if field_name in vals else record[field_name]
            if value and value != 'unconfigured':
                return 'draft'
        return 'not_configured'

    def _policy_value(self, field_name):
        field = self._fields[field_name]
        if not self._has_field_access(field, 'read'):
            return None
        return self[field_name]

    def _can_read_sensitive(self):
        if self.env.su:
            return True
        return self.env.user.has_groups(self.SENSITIVE_GROUPS)

    def _result(self, classification, code, message, **extra):
        payload = {
            'classification': classification,
            'code': code,
            'message': message,
            'operationally_approved': False,
        }
        payload.update(extra)
        return payload

    def _format_readiness(self, data):
        lines = [
            'Company: %s' % data['company_name'],
            'Revision: %s' % data['revision'],
            'State: %s' % data['state'],
            'Operationally approved: no',
            'Validated at: %s' % data['validated_at'],
            'Missing: %s' % ', '.join(data['missing']),
            'Invalid: %s' % ', '.join(data['invalid']),
            'Blocking: %s' % ' | '.join(data['blocking']),
            'Warnings: %s' % ' | '.join(data['warnings']),
            'Next action: %s' % data['next_action'],
        ]
        return '\n'.join(lines)
