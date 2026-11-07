from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MODULE = 'contract_price_leakage_auditor'
SEQUENCE_CODE = 'cpla.customer.contract'
MANAGER_GROUP = f'{MODULE}.group_contract_manager'
USER_GROUP = f'{MODULE}.group_contract_user'


class CustomerContract(models.Model):
    """Company-owned draft of a customer pricing agreement.

    Ready for review means the draft is complete enough to be reviewed.
    It is not commercial approval and it is not an invoice-audit price.
    """

    _name = 'cpla.customer.contract'
    _description = 'Customer Pricing Contract'
    _order = 'reference desc, id desc'
    _rec_name = 'reference'
    _rec_names_search = ['reference', 'name', 'external_reference']
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(company_id, reference)',
        'The contract reference is already used in this company.',
    )

    reference = fields.Char(
        string='Contract Reference',
        required=True,
        copy=False,
        index=True,
        help='Stable company reference assigned from the contract sequence. It is not rewritten after creation.',
    )
    name = fields.Char(
        string='Agreement Name',
        help='Commercial title of the agreement. The reference remains the stable identifier.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        help='Legal entity that owns this negotiated pricing agreement.',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        index=True,
        ondelete='restrict',
        check_company=True,
        help='Exact contracting customer. A parent agreement is not applied to branches or subsidiaries.',
    )
    commercial_partner_id = fields.Many2one(
        'res.partner',
        string='Commercial Partner',
        related='partner_id.commercial_partner_id',
        store=True,
        index=True,
        help='Identity context only. This does not extend coverage to related entities.',
    )
    covered_partner_ids = fields.Many2many(
        'res.partner',
        'cpla_customer_contract_covered_partner_rel',
        'contract_id',
        'partner_id',
        string='Proposed Covered Entities',
        check_company=True,
        help='DEC-03 is open. Extra entities are a proposal only and block review submission.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Contract Currency',
        help='Currency of the negotiated unit prices. Company currency is stored separately. No exchange rate is calculated here.',
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True,
    )
    valid_from = fields.Date(
        string='Valid From',
        index=True,
        help='Proposed effective start. A date inside this period does not approve the contract.',
    )
    valid_to = fields.Date(
        string='Valid To',
        index=True,
        help='Proposed effective end. An open end date is not an approved policy and blocks review.',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('ready_for_review', 'Ready for Review'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='draft',
        copy=False,
        index=True,
        help='Ready for Review means a person can review the draft. It is not approval, activation, or an audit price.',
    )
    owner_id = fields.Many2one(
        'res.users',
        string='Contract Owner',
        required=True,
        index=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
        help='Commercial user responsible for this draft. The default is the current user, not the system administrator.',
    )
    external_reference = fields.Char(
        string='External Agreement Reference',
        help='Customer or signed-document agreement number.',
    )
    description = fields.Text(string='Description')
    policy_id = fields.Many2one(
        'cpla.company.policy',
        string='Company Policy',
        check_company=True,
        ondelete='restrict',
        index=True,
        help='Current company policy reference. A policy revision is not operational approval.',
    )
    policy_version = fields.Integer(
        related='policy_id.version',
        string='Policy Version',
        readonly=True,
    )
    line_ids = fields.One2many(
        'cpla.customer.contract.line',
        'contract_id',
        string='Negotiated Prices',
        copy=True,
    )
    evidence_ids = fields.One2many(
        'cpla.customer.contract.evidence',
        'contract_id',
        string='Supporting Evidence',
        copy=False,
    )
    version_ids = fields.One2many(
        'cpla.customer.contract.version',
        'contract_id',
        string='Versions',
    )
    reset_reason = fields.Text(
        string='Reset Reason',
        copy=False,
        help='Required when a Contract Manager returns a review submission to draft.',
    )
    cancel_reason = fields.Text(string='Cancel Reason', copy=False)
    overlap_warning = fields.Text(
        string='Overlap Warning',
        compute='_compute_overlap_warning',
        help='Another non-cancelled contract shares this customer, period, and product. No price is chosen.',
    )
    review_blocker_text = fields.Text(
        string='Review Blockers',
        compute='_compute_review_blockers',
    )
    audit_authoritative = fields.Boolean(
        string='Audit Authoritative',
        compute='_compute_audit_authoritative',
        help='True only when an approved version snapshot exists. The header itself is not the historical price.',
    )

    @api.depends('reference', 'name')
    def _compute_display_name(self):
        for contract in self:
            if contract.reference and contract.name:
                contract.display_name = '%s — %s' % (contract.reference, contract.name)
            else:
                contract.display_name = contract.reference or contract.name or ''

    @api.depends('version_ids.state')
    def _compute_audit_authoritative(self):
        for contract in self:
            contract.audit_authoritative = any(
                version.state == 'approved' for version in contract.version_ids
            )

    @api.depends(
        'company_id', 'partner_id', 'currency_id', 'valid_from', 'valid_to',
        'policy_id', 'owner_id', 'covered_partner_ids', 'line_ids',
        'line_ids.product_id', 'line_ids.uom_id', 'line_ids.price_unit',
        'evidence_ids', 'evidence_ids.datas',
    )
    def _compute_review_blockers(self):
        for contract in self:
            blockers = contract._review_blockers()
            contract.review_blocker_text = '\n'.join(blockers) if blockers else False

    @api.depends(
        'company_id', 'partner_id', 'valid_from', 'valid_to', 'state',
        'line_ids.product_id',
    )
    def _compute_overlap_warning(self):
        for contract in self:
            contract.overlap_warning = contract._overlap_warning()

    @api.constrains('valid_from', 'valid_to')
    def _check_dates(self):
        for contract in self:
            if contract.valid_from and contract.valid_to and contract.valid_from > contract.valid_to:
                raise ValidationError(self.env._(
                    'Valid To cannot be earlier than Valid From. The dates were not swapped.'
                ))

    @api.constrains('owner_id', 'company_id')
    def _check_owner(self):
        # Odoo calls constraints on a sudo recordset. Do not skip this check
        # when env.su is set, or an ineligible owner is stored.
        for contract in self:
            owner = contract.owner_id
            company = contract.company_id
            if not owner or not company:
                continue
            if company not in owner.company_ids:
                raise ValidationError(self.env._(
                    'The contract owner must belong to %(company)s.',
                    company=company.display_name,
                ))
            if not owner.has_group(USER_GROUP):
                raise ValidationError(self.env._(
                    'The contract owner must be a Contract User or Contract Manager.'
                ))

    @api.constrains('company_id', 'reference')
    def _check_reference_unique(self):
        for contract in self:
            if not contract.reference or not contract.company_id:
                continue
            duplicate = self.search([
                ('id', '!=', contract.id),
                ('company_id', '=', contract.company_id.id),
                ('reference', '=', contract.reference),
            ], limit=1)
            if duplicate:
                raise ValidationError(self.env._(
                    'Contract reference %(reference)s is already used in %(company)s.',
                    reference=contract.reference,
                    company=contract.company_id.display_name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            if not values.get('company_id'):
                values['company_id'] = self.env.company.id
            company = self._check_company_assignment(values['company_id'])
            self._check_owner_assignment(values.get('owner_id'))
            if not values.get('reference'):
                values['reference'] = self._next_reference(company)
            self._check_reference_available(company, values['reference'])
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals):
        if 'state' in vals:
            raise UserError(self.env._(
                'Use the contract actions to change the status. Ready for Review is not approval.'
            ))
        if 'company_id' in vals and any(vals['company_id'] != contract.company_id.id for contract in self):
            raise UserError(self.env._(
                'The contract company cannot be changed. Create a separate contract for the other company.'
            ))
        if 'reference' in vals and any(vals['reference'] != contract.reference for contract in self):
            raise UserError(self.env._(
                'The contract reference cannot be changed after it is assigned.'
            ))
        if 'currency_id' in vals:
            for contract in self:
                if contract.line_ids and vals['currency_id'] != contract.currency_id.id:
                    raise UserError(self.env._(
                        'Review or remove the negotiated lines before changing the contract currency. '
                        'The existing amounts are not converted.'
                    ))
        if (
            not self.env.su
            and 'owner_id' in vals
            and not self.env.user.has_group(MANAGER_GROUP)
            and any(vals['owner_id'] != contract.owner_id.id for contract in self)
        ):
            raise UserError(self.env._(
                'Only a Contract Manager can reassign the contract owner.'
            ))
        annotations = {'reset_reason', 'cancel_reason'}
        for contract in self:
            if contract.state == 'draft':
                continue
            if (
                contract.state == 'ready_for_review'
                and set(vals) <= annotations
                and self.env.user.has_group(MANAGER_GROUP)
            ):
                continue
            raise UserError(self.env._(
                'Submitted contract terms cannot be changed. A Contract Manager can return '
                'a review submission to draft. This record is not an approved price.'
            ))
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._(
            'Customer contracts are not deleted. Cancel the draft instead. '
            'This draft is not an approved historical agreement.'
        ))

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('reference', False)
        default.setdefault('state', 'draft')
        return super().copy(default)

    def action_approve_initial(self):
        """Create the first approved snapshot. Ready for review is not approval."""
        versions = self.env['cpla.customer.contract.version']
        approved = versions.browse()
        for contract in self:
            approved |= versions.approve_initial(contract)
        if len(approved) == 1:
            return approved.get_formview_action()
        return True

    def action_submit_for_review(self):
        """Mark a complete draft ready for review.

        A repeated call on a contract that is already ready does nothing.
        The resulting status is not commercial approval.
        """
        self.check_access('write')
        self.lock_for_update()
        if self.line_ids:
            self.line_ids.lock_for_update()
        if self.evidence_ids:
            self.evidence_ids.lock_for_update()
        for contract in self:
            if contract.state == 'ready_for_review':
                continue
            if contract.state != 'draft':
                raise UserError(self.env._(
                    'Only a draft contract can be submitted for review.'
                ))
            contract._check_submit_actor()
            blockers = contract._review_blockers()
            if blockers:
                details = '\n'.join('- %s' % item for item in blockers)
                raise UserError(self.env._(
                    'Contract %(reference)s cannot be submitted for review:\n%(details)s',
                    reference=contract.reference,
                    details=details,
                ))
            contract._write_state('ready_for_review')
        return True

    def action_cancel(self):
        """Cancel a draft or a review submission without deleting evidence."""
        self.check_access('write')
        is_manager = self.env.su or self.env.user.has_group(MANAGER_GROUP)
        for contract in self:
            if contract.version_ids.filtered(lambda version: version.state == 'approved'):
                raise UserError(self.env._(
                    'An approved version exists. Cancel it only through a later amendment. '
                    'Approved history is not deleted.'
                ))
            if contract.state == 'cancelled':
                continue
            if contract.state == 'draft':
                if not is_manager and contract.owner_id != self.env.user:
                    raise AccessError(self.env._(
                        'You can cancel only your own draft contract.'
                    ))
            elif contract.state == 'ready_for_review':
                if not is_manager:
                    raise AccessError(self.env._(
                        'Only a Contract Manager can cancel a contract that is ready for review.'
                    ))
            else:
                raise UserError(self.env._('This contract cannot be cancelled.'))
            contract._write_state('cancelled')
        return True

    def action_reset_to_draft(self):
        """Return a review submission to draft. Contract Managers only."""
        self.check_access('write')
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._(
                'Only a Contract Manager can return a contract to draft.'
            ))
        for contract in self:
            if contract.version_ids.filtered(lambda version: version.state == 'approved'):
                raise UserError(self.env._(
                    'A contract with an approved version cannot return to draft. '
                    'Create an amendment. The approved snapshot stays unchanged.'
                ))
            if contract.state != 'ready_for_review':
                raise UserError(self.env._(
                    'Only a contract that is ready for review can return to draft.'
                ))
            if not (contract.reset_reason or '').strip():
                raise UserError(self.env._(
                    'Enter a reset reason before returning the contract to draft.'
                ))
            contract._write_state('draft')
        return True

    def _write_state(self, state):
        self.ensure_one()
        self.check_access('write')
        return super(CustomerContract, self).write({'state': state})

    def _check_company_assignment(self, company_id):
        company = self.env['res.company'].browse(company_id).exists()
        if not company:
            raise ValidationError(self.env._('A company is required.'))
        if self.env.su:
            return company
        if company not in self.env.user.company_ids or company not in self.env.companies:
            raise AccessError(self.env._(
                'You cannot use a company that is outside your active company selection.'
            ))
        return company

    def _check_owner_assignment(self, owner_id):
        if self.env.su or self.env.user.has_group(MANAGER_GROUP) or not owner_id:
            return
        if owner_id != self.env.user.id:
            raise AccessError(self.env._(
                'A Contract User cannot assign a contract to another owner.'
            ))

    def _check_submit_actor(self):
        self.ensure_one()
        if self.env.su or self.env.user.has_group(MANAGER_GROUP):
            return
        if self.env.user.has_group(USER_GROUP) and self.owner_id == self.env.user:
            return
        raise AccessError(self.env._(
            'You are not allowed to submit this contract for review.'
        ))

    def _next_reference(self, company):
        reference = self.env['ir.sequence'].with_company(company).next_by_code(SEQUENCE_CODE)
        if not reference:
            raise UserError(self.env._(
                'The customer contract sequence is missing. No reference was invented.'
            ))
        return reference

    def _check_reference_available(self, company, reference):
        duplicate = self.search([
            ('company_id', '=', company.id),
            ('reference', '=', reference),
        ], limit=1)
        if duplicate:
            raise ValidationError(self.env._(
                'Contract reference %(reference)s is already used in %(company)s.',
                reference=reference,
                company=company.display_name,
            ))

    def _review_blockers(self):
        self.ensure_one()
        blockers = []
        if not self.company_id:
            blockers.append(self.env._('The company is missing.'))
        if not self.partner_id:
            blockers.append(self.env._('The customer is missing.'))
        elif self.partner_id.company_id and self.company_id and self.partner_id.company_id not in self.company_id.parent_ids:
            blockers.append(self.env._(
                'The customer belongs to another company and is not a shared contact.'
            ))
        if not self.reference:
            blockers.append(self.env._('The contract reference is missing.'))
        if not self.currency_id:
            blockers.append(self.env._('The contract currency is missing.'))
        elif not self.currency_id.active:
            blockers.append(self.env._(
                'The contract currency is inactive. This module does not activate currencies or create exchange rates.'
            ))
        if not self.valid_from:
            blockers.append(self.env._('Valid From is required before review.'))
        if not self.valid_to:
            blockers.append(self.env._(
                'Valid To is required before review. An open-ended contract is not an approved policy.'
            ))
        elif self.valid_from and self.valid_from > self.valid_to:
            blockers.append(self.env._('Valid To is earlier than Valid From.'))
        if not self.policy_id:
            blockers.append(self.env._(
                'A current company policy reference is required. The policy is not an operational approval.'
            ))
        elif not self.policy_id.is_current:
            blockers.append(self.env._('The selected policy is not the current revision.'))
        elif self.company_id and self.policy_id.company_id != self.company_id:
            blockers.append(self.env._('The selected policy belongs to another company.'))
        if not self.owner_id:
            blockers.append(self.env._('The contract owner is missing.'))
        if self.covered_partner_ids:
            blockers.append(self.env._(
                'Extra covered customers are recorded while DEC-03 is open. '
                'Coverage stays limited to the selected customer, so review is blocked.'
            ))
        if not self.line_ids:
            blockers.append(self.env._('At least one negotiated product line is required.'))
        for line in self.line_ids:
            blockers.extend(line._review_blockers())
        if not any(evidence.datas for evidence in self.evidence_ids):
            blockers.append(self.env._(
                'A supporting evidence file is required before review.'
            ))
        return blockers

    def _overlap_warning(self):
        self.ensure_one()
        if not isinstance(self.id, int) or not self.partner_id or not self.company_id:
            return False
        if self.state == 'cancelled' or not self.valid_from or not self.line_ids:
            return False
        product_ids = self.line_ids.product_id.ids
        if not product_ids:
            return False
        domain = [
            ('id', '!=', self.id),
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('state', '!=', 'cancelled'),
            ('line_ids.product_id', 'in', product_ids),
            ('valid_from', '!=', False),
        ]
        if self.valid_to:
            domain += [
                ('valid_from', '<=', self.valid_to),
                '|', ('valid_to', '=', False), ('valid_to', '>=', self.valid_from),
            ]
        else:
            domain += ['|', ('valid_to', '=', False), ('valid_to', '>=', self.valid_from)]
        others = self.search(domain)
        if not others:
            return False
        return self.env._(
            'CONTRACT_CONFLICT_REVIEW_REQUIRED: %(references)s share this customer, period, and product. No price was selected.',
            references=', '.join(others.mapped('reference')),
        )


class CustomerContractLine(models.Model):
    """One negotiated unit price for one product variant.

    Quantity tiers are not stored here. The same variant may appear again
    only with a different pricing unit, so a later tier model is not blocked
    by a product-only uniqueness rule. A non-default unit cannot be submitted.
    """

    _name = 'cpla.customer.contract.line'
    _description = 'Customer Pricing Contract Line'
    _order = 'sequence, id'
    _check_company_auto = True

    _exact_line_unique = models.Constraint(
        'UNIQUE(contract_id, product_id, uom_id)',
        'This product and pricing unit are already on the contract.',
    )

    contract_id = fields.Many2one(
        'cpla.customer.contract',
        string='Contract',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='contract_id.company_id',
        store=True,
        index=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        required=True,
        ondelete='restrict',
        check_company=True,
        index=True,
        help='Exact variant. A template with several variants is not a price identity.',
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        related='product_id.product_tmpl_id',
        store=True,
        string='Product Template',
        readonly=True,
    )
    name = fields.Char(
        string='Description',
        help='Agreed product description. This is not a price.',
    )
    price_unit = fields.Monetary(
        string='Negotiated Price',
        currency_field='currency_id',
        required=True,
        help='Explicit negotiated unit price. The product list price, cost, pricelist, and last sale are not used.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='contract_id.currency_id',
        store=True,
        readonly=True,
        string='Currency',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Pricing Unit',
        required=True,
        ondelete='restrict',
        help='Unit the negotiated price applies to. A compatible packaging unit is stored but cannot be submitted in this phase.',
    )
    external_line_reference = fields.Char(string='External Line Reference')
    notes = fields.Text(string='Notes')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.uom_id:
            self.uom_id = self.product_id.uom_id
        if self.product_id and not self.name:
            self.name = self.product_id.display_name

    @api.constrains('price_unit')
    def _check_price_unit(self):
        for line in self:
            if line.price_unit < 0:
                raise ValidationError(self.env._(
                    'A negative negotiated price is not allowed.'
                ))

    @api.constrains('product_id', 'uom_id')
    def _check_uom(self):
        for line in self:
            issue = line._uom_issue()
            if issue == 'incompatible':
                raise ValidationError(self.env._(
                    '%(product)s cannot use %(uom)s. The units are not in the same family, and no conversion was invented.',
                    product=line.product_id.display_name,
                    uom=line.uom_id.display_name,
                ))
            if issue == 'inactive':
                raise ValidationError(self.env._(
                    'The pricing unit %(uom)s is inactive and was not activated.',
                    uom=line.uom_id.display_name,
                ))
            if issue == 'factor':
                raise ValidationError(self.env._(
                    'The pricing unit has no positive conversion factor.'
                ))

    @api.constrains('contract_id', 'product_id', 'uom_id')
    def _check_exact_duplicate(self):
        for line in self:
            if not line.contract_id or not line.product_id or not line.uom_id:
                continue
            duplicate = self.search([
                ('id', '!=', line.id),
                ('contract_id', '=', line.contract_id.id),
                ('product_id', '=', line.product_id.id),
                ('uom_id', '=', line.uom_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(self.env._(
                    '%(product)s with %(uom)s is already on this contract. A different pricing unit can be stored, but it is not a quantity tier.',
                    product=line.product_id.display_name,
                    uom=line.uom_id.display_name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        seen = set()
        for vals in vals_list:
            contract = self._editable_contract(vals.get('contract_id'))
            if vals.get('company_id') and vals['company_id'] != contract.company_id.id:
                raise UserError(self.env._(
                    'The line company comes from the contract and cannot be reassigned.'
                ))
            vals.pop('company_id', None)
            key = (vals.get('contract_id'), vals.get('product_id'), vals.get('uom_id'))
            if all(key) and (key in seen or self.search([
                ('contract_id', '=', key[0]),
                ('product_id', '=', key[1]),
                ('uom_id', '=', key[2]),
            ], limit=1)):
                raise ValidationError(self.env._(
                    'This product and pricing unit are already on the contract.'
                ))
            seen.add(key)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if 'company_id' in vals and any(vals['company_id'] != line.company_id.id for line in self):
            raise UserError(self.env._(
                'The line company comes from the contract and cannot be reassigned.'
            ))
        vals.pop('company_id', None)
        if 'contract_id' in vals and any(vals['contract_id'] != line.contract_id.id for line in self):
            raise UserError(self.env._(
                'A contract line cannot be moved to another contract.'
            ))
        self._require_draft_parent()
        if vals.get('contract_id'):
            self._editable_contract(vals['contract_id'])
        for line in self:
            product_id = vals.get('product_id', line.product_id.id)
            uom_id = vals.get('uom_id', line.uom_id.id)
            contract_id = vals.get('contract_id', line.contract_id.id)
            if product_id and uom_id and contract_id and self.search([
                ('id', '!=', line.id),
                ('contract_id', '=', contract_id),
                ('product_id', '=', product_id),
                ('uom_id', '=', uom_id),
            ], limit=1):
                raise ValidationError(self.env._(
                    'This product and pricing unit are already on the contract.'
                ))
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self._require_draft_parent()
        return super().unlink()

    def _editable_contract(self, contract_id):
        contract = self.env['cpla.customer.contract'].browse(contract_id).exists()
        if not contract:
            raise ValidationError(self.env._('The contract line needs its parent contract.'))
        contract.check_access('write')
        if contract.state != 'draft':
            raise UserError(self.env._(
                'Lines cannot be changed after the contract leaves draft. '
                'Ready for Review is not approval.'
            ))
        return contract

    def _require_draft_parent(self):
        for line in self:
            line.contract_id.check_access('write')
            if line.contract_id.state != 'draft':
                raise UserError(self.env._(
                    'Lines on a %(state)s contract are protected. '
                    'Ready for Review is not approval.',
                    state=line.contract_id.state,
                ))

    def _uom_issue(self):
        self.ensure_one()
        pricing = self.uom_id
        product_uom = self.product_id.uom_id
        if not pricing or not product_uom:
            return 'missing'
        if not pricing.active:
            return 'inactive'
        if pricing.relative_factor is None or pricing.relative_factor <= 0:
            return 'factor'
        if not pricing._has_common_reference(product_uom):
            return 'incompatible'
        packaging = self.product_id.product_tmpl_id.uom_ids
        if pricing in packaging:
            return 'packaging'
        if pricing != product_uom:
            return 'non_default'
        return None

    def _review_blockers(self):
        self.ensure_one()
        label = self.product_id.display_name or self.env._('A line')
        blockers = []
        if not self.product_id:
            blockers.append(self.env._('A product line has no product variant.'))
            return blockers
        if not self.product_id.active:
            blockers.append(self.env._(
                '%(product)s is archived. The historical product is retained and cannot be submitted as a current negotiated price.',
                product=label,
            ))
        issue = self._uom_issue()
        if issue == 'missing':
            blockers.append(self.env._(
                '%(product)s has no valid pricing unit.',
                product=label,
            ))
        elif issue == 'packaging':
            blockers.append(self.env._(
                '%(product)s uses a packaging unit. That unit is not the default price unit.',
                product=label,
            ))
        elif issue == 'non_default':
            blockers.append(self.env._(
                '%(product)s uses %(uom)s instead of its default unit. Unit conversion is not part of this phase.',
                product=label,
                uom=self.uom_id.display_name,
            ))
        elif issue:
            blockers.append(self.env._(
                '%(product)s has a pricing-unit problem (%(issue)s).',
                product=label,
                issue=issue,
            ))
        currency = self.currency_id
        if currency and currency.is_zero(self.price_unit):
            blockers.append(self.env._(
                '%(product)s has a zero negotiated price. Zero is not an approved selling price.',
                product=label,
            ))
        elif self.price_unit < 0:
            blockers.append(self.env._(
                '%(product)s has a negative negotiated price.',
                product=label,
            ))
        return blockers


class CustomerContractEvidence(models.Model):
    """File linked to one customer contract.

    Access follows the contract company and, for a Contract User, the owner.
    Submission freezes the file. This is not an immutable legal archive.
    """

    _name = 'cpla.customer.contract.evidence'
    _description = 'Customer Contract Evidence'
    _order = 'id'
    _check_company_auto = True

    contract_id = fields.Many2one(
        'cpla.customer.contract',
        string='Contract',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='contract_id.company_id',
        store=True,
        index=True,
        readonly=True,
    )
    name = fields.Char(string='Document Title', required=True)
    document_type = fields.Selection(
        selection=[
            ('signed_agreement', 'Signed pricing agreement'),
            ('purchase_agreement', 'Customer purchase agreement'),
            ('price_schedule', 'Price schedule'),
            ('confirmation', 'Contract confirmation'),
            ('other', 'Other evidence'),
        ],
        string='Document Type',
        required=True,
        default='signed_agreement',
    )
    source_reference = fields.Char(string='Source Document Reference')
    description = fields.Text(string='Evidence Description')
    datas = fields.Binary(string='File', attachment=True, required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            contract = self.env['cpla.customer.contract'].browse(vals.get('contract_id')).exists()
            if not contract:
                raise ValidationError(self.env._('Evidence must be attached to a contract.'))
            contract.check_access('write')
            if contract.state != 'draft':
                raise UserError(self.env._(
                    'Evidence cannot be added after the contract leaves draft.'
                ))
            if 'company_id' in vals and vals['company_id'] != contract.company_id.id:
                raise UserError(self.env._(
                    'Evidence cannot be filed under a different company.'
                ))
            vals.pop('company_id', None)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if 'company_id' in vals and any(vals['company_id'] != evidence.company_id.id for evidence in self):
            raise UserError(self.env._(
                'Evidence cannot be moved to another company.'
            ))
        vals.pop('company_id', None)
        if 'contract_id' in vals and any(vals['contract_id'] != evidence.contract_id.id for evidence in self):
            raise UserError(self.env._(
                'Evidence cannot be moved to another contract.'
            ))
        for evidence in self:
            evidence.contract_id.check_access('write')
            if evidence.contract_id.state != 'draft':
                raise UserError(self.env._(
                    'Evidence on a submitted contract cannot be replaced or edited.'
                ))
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        for evidence in self:
            evidence.contract_id.check_access('write')
            if evidence.contract_id.state != 'draft':
                raise UserError(self.env._(
                    'Evidence on a submitted contract cannot be deleted.'
                ))
        return super().unlink()
