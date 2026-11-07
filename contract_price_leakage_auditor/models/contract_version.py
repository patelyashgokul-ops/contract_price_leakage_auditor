import base64
import binascii
import hashlib
import json
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MODULE = 'contract_price_leakage_auditor'
USER_GROUP = f'{MODULE}.group_contract_user'
MANAGER_GROUP = f'{MODULE}.group_contract_manager'
FINANCE_MANAGER_GROUP = f'{MODULE}.group_finance_manager'

AMOUNT_THRESHOLD_POLICY = 'not_configured'
RETROACTIVITY_POLICY = 'not_authorized'

VERSION_STATES = [
    ('draft', 'Draft'),
    ('ready_for_review', 'Ready for Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
]
EFFECTIVE_STATES = [
    ('scheduled', 'Scheduled'),
    ('currently_effective', 'Currently Effective'),
    ('superseded', 'Superseded'),
    ('expired', 'Expired'),
]
EVENT_TYPES = [
    ('draft_created', 'Version Draft Created'),
    ('amendment_created', 'Amendment Created'),
    ('submitted', 'Submitted for Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
    ('supersession_recorded', 'Supersession Recorded'),
    ('historical_reassessment_required', 'Historical Reassessment Required'),
    ('evidence_correction_requested', 'Evidence Correction Requested'),
]
CLIENT_APPROVAL_FIELDS = {
    'state', 'approved_by_id', 'approved_at', 'approval_reference',
    'snapshot_sha256', 'submitted_by_id', 'rejected_by_id',
    'supersedes_version_id', 'version_number', 'reference',
    'contract_id', 'company_id', 'source_version_id', 'requested_by_id',
    'partner_name', 'covered_partner_names', 'commercial_partner_name',
    'policy_version_snapshot', 'pricing_date_policy_snapshot',
    'precedence_policy_snapshot', 'coverage_policy_snapshot',
    'amount_threshold_policy', 'retroactivity_policy',
}


class CustomerContractVersion(models.Model):
    """Approved commercial snapshot of one customer contract.

    The contract header stays a draft or a review submission. This row is
    the historical price. A later amendment creates a new row. It does not
    edit an approved row. Effective From is inclusive. Effective To, when
    stored on the validity dates, is inclusive. Approval time is a separate
    timestamp. No invoice is repriced from this model.
    """

    _name = 'cpla.customer.contract.version'
    _description = 'Customer Contract Version'
    _order = 'contract_id, version_number, id'
    _rec_name = 'reference'
    _check_company_auto = True

    _version_number_unique = models.Constraint(
        'UNIQUE(contract_id, version_number)',
        'The version number is already used on this contract.',
    )
    _reference_unique = models.Constraint(
        'UNIQUE(company_id, reference)',
        'The version reference is already used in this company.',
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
    version_number = fields.Integer(
        string='Version',
        required=True,
        index=True,
        readonly=True,
    )
    reference = fields.Char(
        string='Version Reference',
        required=True,
        index=True,
        readonly=True,
    )
    state = fields.Selection(
        selection=VERSION_STATES,
        string='Approval Status',
        required=True,
        default='draft',
        index=True,
        readonly=True,
        copy=False,
    )
    effective_status = fields.Selection(
        selection=EFFECTIVE_STATES,
        string='Effective Status',
        compute='_compute_effective_status',
        search='_search_effective_status',
        help='Derived from the approval state and the effective dates. A scheduled job does not rewrite this history.',
    )
    historically_effective = fields.Boolean(
        string='Historically Effective',
        compute='_compute_effective_status',
    )
    authority_to = fields.Date(
        string='Authority To',
        compute='_compute_effective_status',
        help='Inclusive last day of this approved version. It is the day before the next approved effective date, or Valid To when no later version exists.',
    )
    reassessment_required = fields.Boolean(
        string='Reassessment Required',
        compute='_compute_reassessment_required',
        help='An amendment asks for an effective date before the approval calendar date. Retroactive approval is not authorized. Invoices are not recalculated.',
    )
    effective_from = fields.Date(
        string='Effective From',
        index=True,
        help='Inclusive commercial start of this version. This is a calendar date, not the approval timestamp.',
    )
    valid_from = fields.Date(string='Valid From', index=True)
    valid_to = fields.Date(string='Valid To', index=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        ondelete='restrict',
        check_company=True,
        index=True,
    )
    partner_name = fields.Char(
        string='Customer Name Snapshot',
        readonly=True,
        help='Customer name recorded for this version. A later rename of the contact does not rewrite it after approval.',
    )
    commercial_partner_name = fields.Char(
        string='Commercial Partner Snapshot',
        readonly=True,
    )
    covered_partner_ids = fields.Many2many(
        'res.partner',
        'cpla_version_covered_partner_rel',
        'version_id',
        'partner_id',
        string='Proposed Covered Entities',
        check_company=True,
    )
    covered_partner_names = fields.Text(
        string='Covered Customer Snapshot',
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Pricing Currency',
        help='Currency of the snapshotted unit prices. Amounts are not converted.',
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True,
    )
    policy_id = fields.Many2one(
        'cpla.company.policy',
        string='Company Policy',
        check_company=True,
        ondelete='restrict',
        index=True,
        help='Policy row referenced at preparation. Operational approval of that policy is a separate open decision.',
    )
    policy_version_snapshot = fields.Integer(
        string='Policy Version Snapshot',
        readonly=True,
    )
    pricing_date_policy_snapshot = fields.Char(
        string='Pricing Date Candidate',
        readonly=True,
        help='Candidate copied at approval. It is not an operational pricing-date rule and it does not match invoices.',
    )
    precedence_policy_snapshot = fields.Char(
        string='Precedence Candidate',
        readonly=True,
    )
    coverage_policy_snapshot = fields.Char(
        string='Coverage Candidate',
        readonly=True,
    )
    amount_threshold_policy = fields.Char(
        string='Amount Threshold Policy',
        default=AMOUNT_THRESHOLD_POLICY,
        readonly=True,
        help='No approved amount ceiling exists. Amount-limited approval is unavailable. This value does not grant an unlimited financial matrix.',
    )
    retroactivity_policy = fields.Char(
        string='Retroactivity Policy',
        default=RETROACTIVITY_POLICY,
        readonly=True,
        help='Retroactive amendments stay blocked until a company authorizes a policy. This field does not switch that authorization on.',
    )
    description = fields.Text(string='Description')
    amendment_reason = fields.Text(string='Amendment Reason')
    external_amendment_reference = fields.Char(
        string='External Amendment Reference',
        index=True,
    )
    approval_note = fields.Text(string='Approval Note')
    rejection_reason = fields.Text(string='Rejection Reason')
    cancel_reason = fields.Text(string='Cancel Reason')
    requested_by_id = fields.Many2one(
        'res.users',
        string='Requested By',
        readonly=True,
        ondelete='restrict',
        index=True,
    )
    submitted_by_id = fields.Many2one(
        'res.users',
        string='Submitted By',
        readonly=True,
        ondelete='restrict',
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        ondelete='restrict',
        index=True,
    )
    rejected_by_id = fields.Many2one(
        'res.users',
        string='Rejected By',
        readonly=True,
        ondelete='restrict',
    )
    approved_at = fields.Datetime(
        string='Approval Date',
        readonly=True,
        copy=False,
        help='Server timestamp of the approval event. It is not the commercial effective date.',
    )
    approval_reference = fields.Char(
        string='Approval Reference',
        readonly=True,
        copy=False,
        index=True,
    )
    source_version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Source Version',
        ondelete='restrict',
        index=True,
        copy=False,
        help='Approved version this amendment was prepared from. It is not edited.',
    )
    supersedes_version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Supersedes',
        ondelete='restrict',
        index=True,
        copy=False,
        help='Previous approved version whose future authority this approval replaces. The previous row is not rewritten.',
    )
    superseded_by_ids = fields.One2many(
        'cpla.customer.contract.version',
        'supersedes_version_id',
        string='Superseded By',
    )
    snapshot_sha256 = fields.Char(
        string='Snapshot Checksum',
        readonly=True,
        copy=False,
        help='Checksum of the commercial snapshot text. It is not legal proof and it is not a tamper-proof archive.',
    )
    change_summary = fields.Char(
        string='Price Change Summary',
        compute='_compute_change_summary',
        help='Unit-price comparison against the source version. It is not recovered cash.',
    )
    line_ids = fields.One2many(
        'cpla.customer.contract.version.line',
        'version_id',
        string='Pricing Snapshot',
        copy=False,
    )
    evidence_ids = fields.One2many(
        'cpla.customer.contract.version.evidence',
        'version_id',
        string='Supporting Evidence',
        copy=False,
    )
    event_ids = fields.One2many(
        'cpla.customer.contract.version.event',
        'version_id',
        string='Audit History',
        copy=False,
    )

    @api.depends(
        'state', 'effective_from', 'valid_to', 'version_number', 'contract_id',
    )
    def _compute_effective_status(self):
        today = fields.Date.context_today(self)
        contracts = self.mapped('contract_id')
        approved = self.search([
            ('contract_id', 'in', contracts.ids),
            ('state', '=', 'approved'),
        ]) if contracts else self.browse()
        by_contract = {}
        for item in approved:
            by_contract.setdefault(item.contract_id.id, []).append(item)
        for version in self:
            version.effective_status = False
            version.historically_effective = False
            version.authority_to = False
            if version.state != 'approved' or not version.effective_from:
                continue
            siblings = [
                item for item in by_contract.get(version.contract_id.id, [])
                if item.id != version.id and item.effective_from
            ]
            next_versions = [
                item for item in siblings
                if item.version_number > version.version_number
            ]
            next_versions.sort(key=lambda item: (item.effective_from, item.version_number))
            if next_versions:
                version.authority_to = fields.Date.add(next_versions[0].effective_from, days=-1)
            else:
                version.authority_to = version.valid_to
            later_started = [
                item for item in next_versions if item.effective_from <= today
            ]
            if version.effective_from > today:
                version.effective_status = 'scheduled'
            elif later_started:
                version.effective_status = 'superseded'
            elif version.valid_to and version.valid_to < today:
                version.effective_status = 'expired'
            else:
                version.effective_status = 'currently_effective'
            version.historically_effective = version.effective_status in ('superseded', 'expired')

    def _search_effective_status(self, operator, value):
        if operator == '=':
            wanted = {value}
        elif operator == 'in':
            wanted = set(value or [])
        else:
            return [('id', '=', 0)]
        approved = self.search([('state', '=', 'approved')])
        matched = approved.filtered(lambda version: version.effective_status in wanted)
        return [('id', 'in', matched.ids)]

    @api.depends('source_version_id', 'effective_from', 'state')
    def _compute_reassessment_required(self):
        today = fields.Date.context_today(self)
        for version in self:
            version.reassessment_required = bool(
                version.source_version_id
                and version.state != 'approved'
                and version.effective_from
                and version.effective_from < today
            )

    @api.depends(
        'source_version_id', 'currency_id', 'partner_id', 'valid_from', 'valid_to',
        'effective_from', 'line_ids.price_unit', 'line_ids.product_id', 'line_ids.uom_id',
    )
    def _compute_change_summary(self):
        for version in self:
            if not version.source_version_id:
                version.change_summary = 'Initial snapshot. No prior approved price.'
                continue
            comparison = version.source_version_id.compare_with(version)
            counts = {}
            for row in comparison['lines']:
                counts[row['category']] = counts.get(row['category'], 0) + 1
            parts = ['%s: %s' % (label, count) for label, count in sorted(counts.items())]
            parts.append('Unit price difference only. This is not recovered cash.')
            version.change_summary = '; '.join(parts) if parts else 'No pricing lines.'

    @api.constrains('valid_from', 'valid_to')
    def _check_dates(self):
        for version in self:
            if version.valid_from and version.valid_to and version.valid_from > version.valid_to:
                raise ValidationError(self.env._(
                    'Valid To cannot be earlier than Valid From. The dates were not swapped.'
                ))

    @api.constrains('contract_id', 'company_id', 'partner_id', 'policy_id', 'source_version_id')
    def _check_company_alignment(self):
        for version in self:
            company = version.company_id
            contract = version.contract_id
            if contract and company and contract.company_id != company:
                raise UserError(self.env._(
                    'The version company must match the parent contract. Cross-company versions are rejected.'
                ))
            partner = version.partner_id
            if partner and partner.company_id and company and partner.company_id not in company.parent_ids:
                raise UserError(self.env._(
                    'The customer belongs to another company and is not a shared contact.'
                ))
            policy = version.policy_id
            if policy and company and policy.company_id != company:
                raise UserError(self.env._(
                    'The selected policy belongs to another company.'
                ))
            source = version.source_version_id
            if source and (source.contract_id != contract or source.company_id != company):
                raise UserError(self.env._(
                    'The source version belongs to another contract or another company.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        pending_numbers = {}
        prepared = [
            self._prepare_version_values(vals, pending_numbers) for vals in vals_list
        ]
        records = super().create(prepared)
        for record in records:
            event_type = 'amendment_created' if record.source_version_id else 'draft_created'
            record._log(event_type, record.amendment_reason or 'Draft version created.')
        return records

    def write(self, vals):
        vals = dict(vals)
        illegal = sorted(CLIENT_APPROVAL_FIELDS & set(vals))
        if illegal:
            raise UserError(self.env._(
                'These version fields are server-controlled and were not written: %(fields)s. '
                'An approved snapshot cannot be edited. Client approval values are rejected.',
                fields=', '.join(illegal),
            ))
        if not self.env.user.has_group(USER_GROUP):
            editable = {'rejection_reason', 'approval_note'}
            if not (
                self.env.user.has_group(FINANCE_MANAGER_GROUP)
                and set(vals) <= editable
                and all(version.state == 'ready_for_review' for version in self)
            ):
                raise AccessError(self.env._(
                    'You are not allowed to change commercial version terms.'
                ))
        for version in self:
            if version.state == 'draft':
                if not self.env.user.has_group(USER_GROUP):
                    raise AccessError(self.env._(
                        'You are not allowed to change commercial version terms.'
                    ))
                continue
            if (
                version.state == 'ready_for_review'
                and set(vals) <= {'rejection_reason', 'approval_note', 'cancel_reason'}
                and (
                    self.env.user.has_group(MANAGER_GROUP)
                    or self.env.user.has_group(FINANCE_MANAGER_GROUP)
                )
            ):
                continue
            raise UserError(self.env._(
                'An approved snapshot cannot be edited. Create an amendment. '
                'The historical price stays unchanged. This version is %(state)s.',
                state=version.state,
            ))
        if 'partner_id' in vals:
            partner = self.env['res.partner'].browse(vals['partner_id']).exists()
            vals = dict(vals)
            vals['partner_name'] = partner.display_name or ''
            vals['commercial_partner_name'] = partner.commercial_partner_id.display_name or ''
        written = super().write(vals)
        self.invalidate_recordset(['change_summary', 'reassessment_required'])
        return written

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._(
            'Versions are not deleted. Cancel a draft if it should not proceed. '
            'An approved version cannot be deleted. Approved history remains available for audit.'
        ))

    def copy(self, default=None):
        raise UserError(self.env._(
            'Copy an approved version with Create Amendment. '
            'Copying would reuse approval identity, and that is rejected.'
        ))

    @api.model
    def approve_initial(self, contract):
        """Create and approve the first snapshot from a review-ready contract.

        The header state is not changed to approved. The requester and the
        submitter are the contract owner, so the approving manager is not
        recorded as having submitted their own approval.
        """
        contract.ensure_one()
        contract.check_access('read')
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to approve the initial version. '
                'A Contract Manager creates the first snapshot. '
                'A Finance Manager can approve a version that is already ready for review.'
            ))
        if self.env.user == contract.owner_id or self.env.user == contract.create_uid:
            raise AccessError(self.env._(
                'Self-approval is prohibited. The approver must be an independent '
                'Contract Manager or Finance Manager, not the owner and not the user who created the contract.'
            ))
        existing = self._approved_for(contract)
        if existing:
            return existing[:1]
        if contract.state != 'ready_for_review':
            raise UserError(self.env._(
                'Unapproved source contract. Submit the draft for review before creating '
                'an approved version. Saving the draft does not approve it.'
            ))
        contract.lock_for_update()
        if contract.line_ids:
            contract.line_ids.lock_for_update()
        if contract.evidence_ids:
            contract.evidence_ids.lock_for_update()
        existing = self._approved_for(contract)
        if existing:
            return existing[:1]
        blockers = contract._review_blockers()
        if blockers:
            details = '\n'.join('- %s' % item for item in blockers)
            raise UserError(self.env._(
                'Unapproved source contract %(reference)s cannot be snapshotted:\n%(details)s',
                reference=contract.reference,
                details=details,
            ))
        with self.env.cr.savepoint():
            version = self.create(self._initial_values(contract))
            line_model = self.env['cpla.customer.contract.version.line']
            for line in contract.line_ids:
                line_model.create(line_model._values_from_contract_line(version, line))
            evidence_model = self.env['cpla.customer.contract.version.evidence']
            for evidence in contract.evidence_ids:
                evidence_model.create(evidence_model._values_from_contract_evidence(version, evidence))
            super(CustomerContractVersion, version).write({
                'state': 'ready_for_review',
                'submitted_by_id': contract.owner_id.id,
            })
            version._log(
                'submitted',
                'Initial version submitted with the contract owner as the requester.',
            )
            version.action_approve()
        return version

    def create_amendment(self):
        """Copy an approved version into a new draft. The source stays as it was."""
        self.ensure_one()
        self.check_access('read')
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to create an amendment.'
            ))
        if self.state != 'approved':
            raise UserError(self.env._(
                'Unapproved source version. Create an amendment from an approved version only.'
            ))
        today = fields.Date.context_today(self)
        effective = self.effective_from if self.effective_from and self.effective_from >= today else fields.Date.add(today, days=1)
        if self.valid_to and effective > self.valid_to:
            effective = self.valid_to
        new = self.create({
            'contract_id': self.contract_id.id,
            'source_version_id': self.id,
            'partner_id': self.partner_id.id,
            'covered_partner_ids': [fields.Command.set(self.covered_partner_ids.ids)],
            'currency_id': self.currency_id.id,
            'policy_id': self.policy_id.id,
            'description': self.description,
            'valid_from': self.valid_from,
            'valid_to': self.valid_to,
            'effective_from': effective,
            'external_amendment_reference': False,
        })
        line_model = self.env['cpla.customer.contract.version.line']
        for line in self.line_ids:
            line_model.create(line_model._values_from_version_line(new, line))
        evidence_model = self.env['cpla.customer.contract.version.evidence']
        for evidence in self.evidence_ids:
            evidence_model.create(evidence_model._values_from_version_evidence(new, evidence))
        return new

    def action_create_amendment(self):
        version = self.create_amendment()
        return version.get_formview_action()

    def action_submit_for_review(self):
        self.ensure_one()
        self.check_access('write')
        if self.state == 'ready_for_review':
            return True
        if self.state != 'draft':
            raise UserError(self.env._(
                'Only a draft version can be submitted for review.'
            ))
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to submit this version for review.'
            ))
        if (
            not self.env.user.has_group(MANAGER_GROUP)
            and self.contract_id.owner_id != self.env.user
            and self.requested_by_id != self.env.user
        ):
            raise AccessError(self.env._(
                'You can submit only your own draft amendment.'
            ))
        self.lock_for_update()
        messages = self._readiness_messages()
        if messages:
            details = '\n'.join('- %s' % item for item in messages)
            raise UserError(self.env._(
                'Version %(reference)s cannot be submitted for review:\n%(details)s',
                reference=self.reference,
                details=details,
            ))
        super().write({
            'state': 'ready_for_review',
            'submitted_by_id': self.env.user.id,
        })
        self._log('submitted', self.amendment_reason or 'Submitted for review.')
        return True

    def action_approve(self):
        """Approve one ready version.

        A repeated call after approval does not create another snapshot,
        event, or supersession. Two concurrent callers serialize on the
        contract row. The caller that does not get the lock receives
        LockError from the database lock. A later retry finds the version
        already approved and stops.
        """
        self.ensure_one()
        self.check_access('write')
        self._check_approver()
        self.contract_id.lock_for_update()
        self.lock_for_update()
        if self.line_ids:
            self.line_ids.lock_for_update()
        if self.evidence_ids:
            self.evidence_ids.lock_for_update()
        if self.state == 'approved':
            return True
        if self.state != 'ready_for_review':
            raise UserError(self.env._(
                'Only a version that is ready for review can be approved. '
                'A draft, rejected, or cancelled version is not an approved price.'
            ))
        messages = self._readiness_messages()
        if not self.submitted_by_id:
            messages.append(self.env._(
                'The version must be submitted for review before approval.'
            ))
        if messages:
            details = '\n'.join('- %s' % item for item in messages)
            raise UserError(self.env._(
                'Version %(reference)s was not approved:\n%(details)s',
                reference=self.reference,
                details=details,
            ))
        if self._is_retroactive():
            self._record_retroactive_block()
            raise UserError(self.env._(
                'Retroactive amendment is not authorized. The company retroactivity policy '
                'is undecided, so this approval is blocked. A historical reassessment is required. '
                'Posted invoices are not recalculated, and the previous approved snapshot is unchanged.'
            ))
        self._apply_approval()
        return True

    def action_reject(self):
        self.ensure_one()
        self.check_access('write')
        if self.state == 'rejected':
            return True
        if self.state != 'ready_for_review':
            raise UserError(self.env._(
                'Only a version that is ready for review can be rejected.'
            ))
        if not (
            self.env.user.has_group(MANAGER_GROUP)
            or self.env.user.has_group(FINANCE_MANAGER_GROUP)
        ):
            raise AccessError(self.env._(
                'You are not allowed to reject this version.'
            ))
        if not (self.rejection_reason or '').strip():
            raise UserError(self.env._(
                'A rejection reason is required. The version was not approved.'
            ))
        super().write({
            'state': 'rejected',
            'rejected_by_id': self.env.user.id,
        })
        self._log('rejected', self.rejection_reason)
        return True

    def action_cancel(self):
        self.ensure_one()
        self.check_access('write')
        if self.state == 'cancelled':
            return True
        if self.state == 'approved':
            raise UserError(self.env._(
                'An approved snapshot cannot be cancelled in place. Create an amendment. '
                'Approved history is not deleted.'
            ))
        if self.state == 'rejected':
            raise UserError(self.env._(
                'A rejected version stays in the history. It was not approved and it was not deleted.'
            ))
        if self.state == 'draft':
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._('You are not allowed to cancel this draft.'))
            if (
                not self.env.user.has_group(MANAGER_GROUP)
                and self.contract_id.owner_id != self.env.user
                and self.requested_by_id != self.env.user
            ):
                raise AccessError(self.env._('You can cancel only your own draft amendment.'))
        elif self.state == 'ready_for_review':
            if not self.env.user.has_group(MANAGER_GROUP):
                raise AccessError(self.env._(
                    'Only a Contract Manager can cancel a version that is ready for review.'
                ))
        else:
            raise UserError(self.env._('This version cannot be cancelled.'))
        super().write({'state': 'cancelled'})
        self._log('cancelled', self.cancel_reason or 'Draft cancelled.')
        return True

    def action_request_evidence_correction(self, reason):
        """Record a correction request. The approved file bytes stay in place."""
        self.ensure_one()
        self.check_access('read')
        if self.state != 'approved':
            raise UserError(self.env._(
                'Evidence correction is recorded against an approved version. The file was not replaced.'
            ))
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._(
                'Only a Contract Manager can request an evidence correction. The file was not replaced.'
            ))
        if not (reason or '').strip():
            raise UserError(self.env._(
                'An evidence correction needs a reason. The file was not replaced.'
            ))
        existing = self.event_ids.filtered(
            lambda event: event.event_type == 'evidence_correction_requested'
        )
        if existing:
            raise UserError(self.env._(
                'An evidence correction request is already recorded. The file was not replaced.'
            ))
        self._log('evidence_correction_requested', reason.strip())
        return True

    def action_view_history(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Version History',
            'res_model': 'cpla.customer.contract.version.event',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.contract_id.id)],
            'target': 'current',
        }

    def action_open_compare(self):
        self.ensure_one()
        self.check_access('read')
        baseline = self.source_version_id or self
        return {
            'type': 'ir.actions.act_window',
            'name': 'Compare Versions',
            'res_model': 'cpla.customer.contract.version.compare',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_baseline_version_id': baseline.id,
                'default_candidate_version_id': self.id,
            },
        }

    def history_rows(self):
        """Read-only history. Approval timestamps come from approval events, not write dates."""
        self.ensure_one()
        self.check_access('read')
        versions = self.search([
            ('contract_id', '=', self.contract_id.id),
        ], order='version_number asc, id asc')
        rows = []
        for version in versions:
            version.check_access('read')
            rows.append({
                'contract': version.contract_id.reference,
                'customer': version.partner_name or version.partner_id.display_name,
                'company': version.company_id.display_name,
                'reference': version.reference,
                'version_number': version.version_number,
                'state': version.state,
                'effective_status': version.effective_status,
                'effective_from': fields.Date.to_string(version.effective_from) if version.effective_from else False,
                'valid_from': fields.Date.to_string(version.valid_from) if version.valid_from else False,
                'valid_to': fields.Date.to_string(version.valid_to) if version.valid_to else False,
                'approved_by': version.approved_by_id.login or False,
                'approved_at': fields.Datetime.to_string(version.approved_at) if version.approved_at else False,
                'supersedes': version.supersedes_version_id.reference or False,
                'change_summary': version.change_summary,
                'evidence': version.evidence_ids.mapped('name'),
                'policy_version_snapshot': version.policy_version_snapshot,
                'pricing_date_policy_snapshot': version.pricing_date_policy_snapshot,
                'events': [{
                    'event_type': event.event_type,
                    'actor': event.actor_id.login,
                    'occurred_at': fields.Datetime.to_string(event.occurred_at),
                    'reason': event.reason or '',
                } for event in version.event_ids.sorted(key=lambda item: (item.occurred_at, item.id))],
            })
        return rows

    def compare_with(self, other):
        """Compare this baseline with another version of the same contract.

        A unit-price delta is not recovered cash. Differing currency or
        pricing units are marked as requiring normalization.
        """
        self.ensure_one()
        other.ensure_one()
        self.check_access('read')
        other.check_access('read')
        if self.contract_id != other.contract_id:
            raise UserError(self.env._(
                'Compare versions of the same contract. No price was selected.'
            ))
        currency_changed = self.currency_id != other.currency_id
        validity_changed = (
            self.valid_from != other.valid_from
            or self.valid_to != other.valid_to
            or self.effective_from != other.effective_from
        )
        customer_scope_changed = (
            self.partner_id != other.partner_id
            or set(self.covered_partner_ids.ids) != set(other.covered_partner_ids.ids)
        )
        rows = []
        if currency_changed:
            rows.append(self._comparison_row(
                'Currency Changed',
                self.currency_id.display_name,
                False,
                False,
                None,
                True,
            ))
        if validity_changed:
            rows.append(self._comparison_row(
                'Contract Validity Changed',
                '%s .. %s' % (self.valid_from or '', self.valid_to or ''),
                False,
                False,
                None,
                False,
            ))
        if customer_scope_changed:
            rows.append(self._comparison_row(
                'Customer Scope Changed',
                self.partner_name or self.partner_id.display_name,
                False,
                False,
                None,
                False,
            ))
        left = {}
        for line in self.line_ids:
            left.setdefault(line.product_id.id, []).append(line)
        right = {}
        for line in other.line_ids:
            right.setdefault(line.product_id.id, []).append(line)
        for product_id in list(dict.fromkeys(list(left) + list(right))):
            old_lines = left.get(product_id, [])
            new_lines = right.get(product_id, [])
            if old_lines and not new_lines:
                for line in old_lines:
                    rows.append(self._comparison_row(
                        'Removed Product',
                        line.product_name or line.product_id.display_name,
                        line.price_unit,
                        False,
                        None,
                        False,
                    ))
                continue
            if new_lines and not old_lines:
                for line in new_lines:
                    rows.append(self._comparison_row(
                        'Added Product',
                        line.product_name or line.product_id.display_name,
                        False,
                        line.price_unit,
                        None,
                        False,
                    ))
                continue
            old_by_uom = {line.uom_id.id: line for line in old_lines}
            new_by_uom = {line.uom_id.id: line for line in new_lines}
            if (
                len(old_lines) == 1
                and len(new_lines) == 1
                and old_lines[0].uom_id != new_lines[0].uom_id
            ):
                rows.append(self._comparison_row(
                    'UoM Changed',
                    old_lines[0].product_name or old_lines[0].product_id.display_name,
                    old_lines[0].price_unit,
                    new_lines[0].price_unit,
                    None,
                    True,
                ))
                continue
            for uom_id, line in old_by_uom.items():
                if uom_id not in new_by_uom:
                    rows.append(self._comparison_row(
                        'Removed Product',
                        line.product_name or line.product_id.display_name,
                        line.price_unit,
                        False,
                        None,
                        False,
                    ))
                    continue
                rows.append(self._price_row(line, new_by_uom[uom_id], currency_changed))
            for uom_id, line in new_by_uom.items():
                if uom_id not in old_by_uom:
                    rows.append(self._comparison_row(
                        'Added Product',
                        line.product_name or line.product_id.display_name,
                        False,
                        line.price_unit,
                        None,
                        False,
                    ))
        return {
            'baseline': self.reference,
            'candidate': other.reference,
            'currency_changed': currency_changed,
            'validity_changed': validity_changed,
            'customer_scope_changed': customer_scope_changed,
            'normalization_required': any(row['normalization_required'] for row in rows),
            'is_recovered_cash': False,
            'lines': rows,
        }

    @api.model
    def _approved_for(self, contract):
        return self.search([
            ('contract_id', '=', contract.id),
            ('state', '=', 'approved'),
        ], order='version_number desc, id desc')

    @api.model
    def _initial_values(self, contract):
        return {
            'contract_id': contract.id,
            'partner_id': contract.partner_id.id,
            'covered_partner_ids': [fields.Command.set(contract.covered_partner_ids.ids)],
            'currency_id': contract.currency_id.id,
            'policy_id': contract.policy_id.id,
            'description': contract.description,
            'valid_from': contract.valid_from,
            'valid_to': contract.valid_to,
            'effective_from': contract.valid_from,
            'amendment_reason': 'Initial approved snapshot.',
            'requested_by_id': contract.owner_id.id,
        }

    def _prepare_version_values(self, vals, pending_numbers):
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(self.env._(
                'You are not allowed to create a contract version.'
            ))
        values = dict(vals)
        forbidden = {
            'state', 'approved_by_id', 'approved_at', 'approval_reference',
            'snapshot_sha256', 'submitted_by_id', 'rejected_by_id',
            'supersedes_version_id',
        }
        if forbidden & set(values):
            raise UserError(self.env._(
                'A version cannot be created as approved. Approval identity is recorded by the server. '
                'Client approval values are rejected.'
            ))
        if values.get('state') not in (None, False, 'draft'):
            raise UserError(self.env._(
                'A version cannot be created as approved. Use the approval action.'
            ))
        contract = self.env['cpla.customer.contract'].browse(values.get('contract_id')).exists()
        if not contract:
            raise ValidationError(self.env._('A version needs its parent contract.'))
        contract.check_access('read')
        if values.get('company_id') and values['company_id'] != contract.company_id.id:
            raise UserError(self.env._(
                'The version company must match the parent contract. Another company was rejected.'
            ))
        values.pop('company_id', None)
        source = self.browse(values.get('source_version_id')).exists()
        if values.get('source_version_id'):
            if (
                not source
                or source.contract_id != contract
                or source.state != 'approved'
            ):
                raise UserError(self.env._(
                    'Unapproved source version. An amendment must start from an approved version of the same contract.'
                ))
            source.check_access('read')
        elif self._approved_for(contract):
            raise UserError(self.env._(
                'An approved version already exists. Create an amendment from that version. '
                'The approved snapshot was not edited.'
            ))
        requested = values.get('requested_by_id') or self.env.user.id
        if requested != self.env.user.id:
            if not (
                self.env.user.has_group(MANAGER_GROUP)
                and requested == contract.owner_id.id
                and not values.get('source_version_id')
            ):
                raise AccessError(self.env._(
                    'The requesting user is the authenticated user. A client cannot assign another requester.'
                ))
        number = self._allocate_version_number(contract, pending_numbers)
        partner = self.env['res.partner'].browse(values.get('partner_id')).exists()
        values.update({
            'state': 'draft',
            'version_number': number,
            'reference': '%s/V%04d' % (contract.reference, number),
            'requested_by_id': requested,
            'amount_threshold_policy': AMOUNT_THRESHOLD_POLICY,
            'retroactivity_policy': RETROACTIVITY_POLICY,
            'partner_name': partner.display_name or '',
            'commercial_partner_name': partner.commercial_partner_id.display_name or '',
            'approved_by_id': False,
            'approved_at': False,
            'approval_reference': False,
            'snapshot_sha256': False,
            'submitted_by_id': False,
            'rejected_by_id': False,
            'supersedes_version_id': False,
        })
        return values

    def _allocate_version_number(self, contract, pending_numbers):
        """Next number for this contract.

        The contract row is locked so two creators cannot take the same
        number. The database lock does not wait: the other transaction
        receives LockError. Cancelled numbers are not reused. The unique
        constraint is the backstop. pending_numbers covers several new
        rows in the same create call, before those rows are visible.
        """
        contract.lock_for_update()
        if contract.id in pending_numbers:
            number = pending_numbers[contract.id]
        else:
            latest = self.search([
                ('contract_id', '=', contract.id),
            ], order='version_number desc, id desc', limit=1)
            number = (latest.version_number or 0) + 1
        pending_numbers[contract.id] = number + 1
        return number

    def _check_approver(self):
        self.ensure_one()
        user = self.env.user
        if not (user.has_group(MANAGER_GROUP) or user.has_group(FINANCE_MANAGER_GROUP)):
            raise AccessError(self.env._(
                'You are not allowed to approve this contract version.'
            ))
        blocked = {
            self.requested_by_id.id,
            self.submitted_by_id.id,
            self.contract_id.owner_id.id,
        }
        if not self.source_version_id:
            blocked.add(self.contract_id.create_uid.id)
        blocked.discard(False)
        if user.id in blocked:
            raise AccessError(self.env._(
                'Self-approval is prohibited. The approver must be an independent '
                'Contract Manager or Finance Manager.'
            ))

    def _is_retroactive(self):
        self.ensure_one()
        if not self.source_version_id or not self.effective_from:
            return False
        return self.effective_from < fields.Date.context_today(self)

    def _record_retroactive_block(self):
        existing = self.env['cpla.customer.contract.version.event'].search([
            ('version_id', '=', self.id),
            ('event_type', '=', 'historical_reassessment_required'),
        ], limit=1)
        if existing:
            return
        self._log(
            'historical_reassessment_required',
            'Retroactive amendment is not authorized. The open decision is recorded. '
            'Posted invoices are not recalculated.',
        )
        self.invalidate_recordset(['event_ids'])

    def _readiness_messages(self):
        self.ensure_one()
        messages = []
        stale = self._stale_message()
        if stale:
            messages.append(stale)
        if not self.partner_id:
            messages.append(self.env._('The customer is missing.'))
        elif (
            self.partner_id.company_id
            and self.company_id
            and self.partner_id.company_id not in self.company_id.parent_ids
        ):
            messages.append(self.env._(
                'The customer belongs to another company and is not a shared contact.'
            ))
        if self.source_version_id and self.partner_id != self.source_version_id.partner_id:
            messages.append(self.env._(
                'Customer scope changes are not authorized while DEC-03 is open. No price was selected.'
            ))
        if self.covered_partner_ids:
            messages.append(self.env._(
                'Extra covered customers are recorded while DEC-03 is open. '
                'Coverage stays limited to the selected customer, so approval is blocked.'
            ))
        if not self.currency_id:
            messages.append(self.env._('The contract currency is missing.'))
        elif not self.currency_id.active:
            messages.append(self.env._(
                'The contract currency is inactive. This module does not activate currencies or create exchange rates.'
            ))
        if not self.valid_from or not self.valid_to:
            messages.append(self.env._(
                'Valid From and Valid To are required. An open-ended contract is not an approved policy.'
            ))
        elif self.valid_from > self.valid_to:
            messages.append(self.env._('Valid To is earlier than Valid From.'))
        if not self.effective_from:
            messages.append(self.env._('The effective date is required.'))
        elif self.valid_from and self.valid_to and not (
            self.valid_from <= self.effective_from <= self.valid_to
        ):
            messages.append(self.env._(
                'Invalid effective date. It is outside the version validity period.'
            ))
        source = self.source_version_id
        if source:
            if self.valid_from and source.valid_from and self.valid_from < source.valid_from:
                messages.append(self.env._(
                    'The amendment extends validity earlier than the approved version. That extension is not authorized.'
                ))
            if self.valid_to and source.valid_to and self.valid_to > source.valid_to:
                messages.append(self.env._(
                    'The amendment extends validity beyond the approved version. That extension is not authorized.'
                ))
            if not (self.amendment_reason or '').strip():
                messages.append(self.env._('An amendment reason is required.'))
        if not self.policy_id:
            messages.append(self.env._(
                'A current company policy reference is required. The policy is not an operational approval.'
            ))
        elif not self.policy_id.is_current:
            messages.append(self.env._('The selected policy is not the current revision.'))
        elif self.company_id and self.policy_id.company_id != self.company_id:
            messages.append(self.env._('The selected policy belongs to another company.'))
        if not self.line_ids:
            messages.append(self.env._('At least one negotiated product line is required.'))
        if not any(evidence._has_support() for evidence in self.evidence_ids):
            messages.append(self.env._(
                'Missing amendment evidence. Link existing evidence or add a supporting file.'
            ))
        for line in self.line_ids:
            messages.extend(line.approval_messages())
        messages.extend(self._chronology_messages())
        return messages

    def _stale_message(self):
        self.ensure_one()
        latest = self._approved_for(self.contract_id)[:1]
        if not self.source_version_id:
            if latest and latest != self:
                return self.env._(
                    'Stale amendment draft. An approved version already exists. '
                    'Create an amendment from %(latest)s. This draft was not approved.',
                    latest=latest.reference,
                )
            return False
        if self.source_version_id.state != 'approved':
            return self.env._(
                'Unapproved source version. An amendment must start from an approved version.'
            )
        if latest and latest != self.source_version_id:
            return self.env._(
                'Stale amendment draft. The source is %(source_version)s but %(latest)s is the latest approved version. '
                'Approval was not applied. Cancel this draft and create a new amendment. The original draft is unchanged.',
                source_version=self.source_version_id.reference,
                latest=latest.reference,
            )
        return False

    def _chronology_messages(self):
        self.ensure_one()
        if not self.effective_from:
            return []
        messages = []
        same = self.search([
            ('id', '!=', self.id),
            ('contract_id', '=', self.contract_id.id),
            ('state', '=', 'approved'),
            ('effective_from', '=', self.effective_from),
        ], limit=1)
        if same:
            messages.append(self.env._(
                'Conflicting supersession: %(other)s is already approved for this effective date. No price was selected.',
                other=same.reference,
            ))
        later = self.search([
            ('id', '!=', self.id),
            ('contract_id', '=', self.contract_id.id),
            ('state', '=', 'approved'),
            ('effective_from', '>', self.effective_from),
        ], limit=1)
        if later:
            messages.append(self.env._(
                'Conflicting supersession: %(other)s is a later approved version. '
                'This draft cannot insert an earlier authority. No price was selected.',
                other=later.reference,
            ))
        return messages

    def _assert_supersession(self, source):
        self.ensure_one()
        if source.contract_id != self.contract_id or source.company_id != self.company_id:
            raise UserError(self.env._(
                'Conflicting supersession. The previous version belongs to another contract or company.'
            ))
        if source.state != 'approved':
            raise UserError(self.env._(
                'Unapproved source version. Supersession requires an approved previous version.'
            ))
        if source.version_number >= self.version_number or source == self:
            raise UserError(self.env._(
                'Conflicting supersession. A version cannot supersede itself or a later version.'
            ))
        seen = {self.id}
        cursor = source
        while cursor:
            if cursor.id in seen:
                raise UserError(self.env._(
                    'Conflicting supersession. The relationship would be circular.'
                ))
            seen.add(cursor.id)
            cursor = cursor.supersedes_version_id

    def _apply_approval(self):
        self.ensure_one()
        source = self.source_version_id
        if source:
            self._assert_supersession(source)
        with self.env.cr.savepoint():
            lines = self.line_ids
            if lines:
                # Freeze the product name after approval authority has been
                # checked. Public line writes stay limited to Contract Users.
                # A Finance Manager does not receive that access. Only this
                # name column is updated, and only inside the approval savepoint.
                lines._write_multi([
                    {'product_name': line.product_id.display_name}
                    for line in lines
                ])
                lines.invalidate_recordset(['product_name'])
            partner_name = self.partner_id.display_name or ''
            covered = ', '.join(self.covered_partner_ids.mapped('display_name'))
            commercial = self.partner_id.commercial_partner_id.display_name or ''
            policy = self.policy_id
            super(CustomerContractVersion, self).write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_at': fields.Datetime.now(),
                'approval_reference': '%s/APR' % self.reference,
                'partner_name': partner_name,
                'covered_partner_names': covered,
                'commercial_partner_name': commercial,
                'policy_version_snapshot': policy.version if policy else 0,
                'pricing_date_policy_snapshot': policy.pricing_date_policy if policy else 'unconfigured',
                'precedence_policy_snapshot': policy.contract_precedence_policy if policy else 'unconfigured',
                'coverage_policy_snapshot': policy.customer_coverage_policy if policy else 'unconfigured',
                'snapshot_sha256': self._checksum(partner_name, covered),
                'supersedes_version_id': source.id if source else False,
                'amount_threshold_policy': AMOUNT_THRESHOLD_POLICY,
                'retroactivity_policy': RETROACTIVITY_POLICY,
            })
            self._log('approved', self.approval_note or 'Approved snapshot recorded.')
            if source:
                self._log(
                    'supersession_recorded',
                    'Supersession recorded from %s. The previous snapshot was not edited.' % source.reference,
                )
            siblings = self.search([('contract_id', '=', self.contract_id.id)])
            siblings.invalidate_recordset([
                'effective_status', 'historically_effective', 'authority_to',
                'change_summary', 'reassessment_required',
            ])

    def _checksum(self, partner_name, covered_names):
        self.ensure_one()
        lines = []
        for line in self.line_ids.sorted(key=lambda item: (item.product_id.id, item.uom_id.id, item.id)):
            lines.append({
                'product_id': line.product_id.id,
                'product_name': line.product_name or '',
                'uom_id': line.uom_id.id,
                'price_unit': '%.6f' % line.price_unit,
                'currency_id': line.currency_id.id,
            })
        payload = {
            'contract': self.contract_id.reference,
            'version_number': self.version_number,
            'partner_name': partner_name,
            'covered_partner_names': covered_names,
            'currency_id': self.currency_id.id,
            'effective_from': fields.Date.to_string(self.effective_from) if self.effective_from else '',
            'valid_from': fields.Date.to_string(self.valid_from) if self.valid_from else '',
            'valid_to': fields.Date.to_string(self.valid_to) if self.valid_to else '',
            'lines': lines,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _log(self, event_type, reason):
        self.ensure_one()
        self.env['cpla.customer.contract.version.event'].create({
            'version_id': self.id,
            'event_type': event_type,
            'reason': reason or '',
        })

    def _comparison_row(self, category, product, old_price, new_price, price_delta, normalization_required):
        return {
            'category': category,
            'product': product or '',
            'old_price': old_price,
            'new_price': new_price,
            'price_delta': price_delta,
            'normalization_required': normalization_required,
        }

    def _price_row(self, old_line, new_line, currency_changed):
        product = old_line.product_name or old_line.product_id.display_name
        if currency_changed or old_line.currency_id != new_line.currency_id or old_line.uom_id != new_line.uom_id:
            category = 'Currency Changed' if currency_changed or old_line.currency_id != new_line.currency_id else 'UoM Changed'
            return self._comparison_row(
                category, product, old_line.price_unit, new_line.price_unit, None, True,
            )
        compared = new_line.currency_id.compare_amounts(new_line.price_unit, old_line.price_unit)
        if compared > 0:
            category = 'Price Increased'
            delta = new_line.price_unit - old_line.price_unit
        elif compared < 0:
            category = 'Price Decreased'
            delta = new_line.price_unit - old_line.price_unit
        else:
            category = 'No Change'
            delta = 0.0
        return self._comparison_row(
            category, product, old_line.price_unit, new_line.price_unit, delta, False,
        )


class CustomerContractVersionLine(models.Model):
    """One snapshotted negotiated unit price.

    The figure is copied from the contract or the source version. It is not
    the product list price, cost, pricelist, or last sale.
    """

    _name = 'cpla.customer.contract.version.line'
    _description = 'Customer Contract Version Line'
    _order = 'sequence, id'
    _check_company_auto = True

    _exact_line_unique = models.Constraint(
        'UNIQUE(version_id, product_id, uom_id)',
        'This product and pricing unit are already on the version.',
    )

    version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Version',
        required=True,
        ondelete='restrict',
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
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product',
        string='Product Variant',
        required=True,
        ondelete='restrict',
        check_company=True,
        index=True,
    )
    product_name = fields.Char(string='Product Name Snapshot')
    product_tmpl_id = fields.Many2one(
        'product.template',
        related='product_id.product_tmpl_id',
        store=True,
        string='Product Template',
        readonly=True,
    )
    name = fields.Char(string='Description')
    price_unit = fields.Monetary(
        string='Negotiated Price',
        currency_field='currency_id',
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='version_id.currency_id',
        store=True,
        readonly=True,
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Pricing Unit',
        required=True,
        ondelete='restrict',
    )
    external_line_reference = fields.Char(string='External Line Reference')
    notes = fields.Text(string='Notes')
    contract_line_id = fields.Many2one(
        'cpla.customer.contract.line',
        string='Source Contract Line',
        ondelete='restrict',
        index=True,
    )
    origin_line_id = fields.Many2one(
        'cpla.customer.contract.version.line',
        string='Source Version Line',
        ondelete='restrict',
        index=True,
    )

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

    @api.model
    def _values_from_contract_line(self, version, line):
        return {
            'version_id': version.id,
            'product_id': line.product_id.id,
            'product_name': line.product_id.display_name,
            'name': line.name,
            'price_unit': line.price_unit,
            'uom_id': line.uom_id.id,
            'external_line_reference': line.external_line_reference,
            'notes': line.notes,
            'sequence': line.sequence,
            'contract_line_id': line.id,
        }

    @api.model
    def _values_from_version_line(self, version, line):
        return {
            'version_id': version.id,
            'product_id': line.product_id.id,
            'product_name': line.product_name or line.product_id.display_name,
            'name': line.name,
            'price_unit': line.price_unit,
            'uom_id': line.uom_id.id,
            'external_line_reference': line.external_line_reference,
            'notes': line.notes,
            'sequence': line.sequence,
            'origin_line_id': line.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        seen = set()
        for vals in vals_list:
            values = dict(vals)
            version = self._draft_version(values.get('version_id'))
            if values.get('company_id') and values['company_id'] != version.company_id.id:
                raise UserError(self.env._(
                    'The line company comes from the version and cannot be reassigned to another company.'
                ))
            values.pop('company_id', None)
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to add pricing lines.'
                ))
            product = self.env['product.product'].browse(values.get('product_id')).exists()
            values['product_name'] = values.get('product_name') or (product.display_name if product else '')
            key = (version.id, values.get('product_id'), values.get('uom_id'))
            if all(key) and (key in seen or self.search([
                ('version_id', '=', key[0]),
                ('product_id', '=', key[1]),
                ('uom_id', '=', key[2]),
            ], limit=1)):
                raise ValidationError(self.env._(
                    'This product and pricing unit are already on the version.'
                ))
            seen.add(key)
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        self.check_access('write')
        if 'company_id' in vals and any(vals['company_id'] != line.company_id.id for line in self):
            raise UserError(self.env._(
                'The line company comes from the version and cannot be reassigned to another company.'
            ))
        vals.pop('company_id', None)
        if 'version_id' in vals and any(vals['version_id'] != line.version_id.id for line in self):
            raise UserError(self.env._(
                'A version line cannot be moved to another version.'
            ))
        for line in self:
            if line.version_id.state != 'draft':
                raise UserError(self.env._(
                    'An approved snapshot cannot be edited. Direct changes to a version line are rejected. '
                    'The historical price stays unchanged.'
                ))
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to change pricing lines.'
                ))
        if vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id']).exists()
            vals['product_name'] = product.display_name if product else ''
        written = super().write(vals)
        self.version_id.invalidate_recordset(['change_summary'])
        return written

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        for line in self:
            if line.version_id.state != 'draft':
                raise UserError(self.env._(
                    'An approved version line cannot be deleted. The historical price stays unchanged.'
                ))
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to remove pricing lines.'
                ))
        versions = self.version_id
        removed = super().unlink()
        versions.invalidate_recordset(['change_summary'])
        return removed

    def _draft_version(self, version_id):
        version = self.env['cpla.customer.contract.version'].browse(version_id).exists()
        if not version:
            raise ValidationError(self.env._('The version line needs its parent version.'))
        version.check_access('write')
        if version.state != 'draft':
            raise UserError(self.env._(
                'Lines cannot be changed after the version leaves draft.'
            ))
        return version

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

    def approval_messages(self):
        self.ensure_one()
        label = self.product_name or self.product_id.display_name or self.env._('A line')
        messages = []
        if not self.product_id:
            return [self.env._('A pricing line has no product variant.')]
        if not self.product_id.active:
            messages.append(self.env._(
                '%(product)s is archived. The historical product is retained and cannot be submitted as a current negotiated price.',
                product=label,
            ))
        issue = self._uom_issue()
        if issue == 'missing':
            messages.append(self.env._('%(product)s has no valid pricing unit.', product=label))
        elif issue == 'packaging':
            messages.append(self.env._(
                '%(product)s uses a packaging unit. That unit is not the default price unit.',
                product=label,
            ))
        elif issue == 'non_default':
            messages.append(self.env._(
                '%(product)s uses %(uom)s instead of its default unit. Unit conversion is not part of this phase.',
                product=label,
                uom=self.uom_id.display_name,
            ))
        elif issue:
            messages.append(self.env._(
                '%(product)s has a pricing-unit problem (%(issue)s).',
                product=label,
                issue=issue,
            ))
        currency = self.currency_id
        if currency and currency.is_zero(self.price_unit):
            messages.append(self.env._(
                '%(product)s has a zero negotiated price. Zero is not an approved selling price.',
                product=label,
            ))
        elif self.price_unit < 0:
            messages.append(self.env._(
                '%(product)s has a negative negotiated price.',
                product=label,
            ))
        if self.company_id and self.version_id.company_id and self.company_id != self.version_id.company_id:
            messages.append(self.env._(
                'Inconsistent pricing lines. %(product)s is filed under another company.',
                product=label,
            ))
        return messages


class CustomerContractVersionEvidence(models.Model):
    """Evidence linked to one version.

    Binary files already stored on the contract or an earlier version are
    referenced, not copied. A checksum records the bytes that were read.
    It is not legal proof.
    """

    _name = 'cpla.customer.contract.version.evidence'
    _description = 'Customer Contract Version Evidence'
    _order = 'id'
    _check_company_auto = True

    version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Version',
        required=True,
        ondelete='restrict',
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
    source_evidence_id = fields.Many2one(
        'cpla.customer.contract.evidence',
        string='Contract Evidence',
        ondelete='restrict',
        index=True,
    )
    origin_evidence_id = fields.Many2one(
        'cpla.customer.contract.version.evidence',
        string='Prior Version Evidence',
        ondelete='restrict',
        index=True,
    )
    name = fields.Char(string='Document Title', required=True)
    document_type = fields.Selection(
        selection=[
            ('signed_agreement', 'Signed pricing agreement'),
            ('purchase_agreement', 'Customer purchase agreement'),
            ('price_schedule', 'Price schedule'),
            ('confirmation', 'Contract confirmation'),
            ('amendment', 'Contract amendment'),
            ('acceptance', 'Customer acceptance'),
            ('internal_approval', 'Internal approval record'),
            ('other', 'Other evidence'),
        ],
        string='Document Type',
        required=True,
        default='amendment',
    )
    source_reference = fields.Char(string='Source Document Reference')
    description = fields.Text(string='Evidence Description')
    datas = fields.Binary(string='File', attachment=True)
    content_sha256 = fields.Char(
        string='Content Checksum',
        readonly=True,
        help='Checksum of file bytes when those bytes were read. It is not legal proof.',
    )

    @api.model
    def _values_from_contract_evidence(self, version, evidence):
        return {
            'version_id': version.id,
            'source_evidence_id': evidence.id,
            'name': evidence.name,
            'document_type': evidence.document_type,
            'source_reference': evidence.source_reference,
            'description': evidence.description,
        }

    @api.model
    def _values_from_version_evidence(self, version, evidence):
        return {
            'version_id': version.id,
            'source_evidence_id': evidence.source_evidence_id.id,
            'origin_evidence_id': evidence.id,
            'name': evidence.name,
            'document_type': evidence.document_type,
            'source_reference': evidence.source_reference,
            'description': evidence.description,
            'content_sha256': evidence.content_sha256,
        }

    def _has_support(self):
        self.ensure_one()
        return bool(self.source_evidence_id or self.origin_evidence_id or self.datas)

    @api.constrains('source_evidence_id', 'origin_evidence_id', 'datas')
    def _check_support(self):
        for evidence in self:
            if not evidence._has_support():
                raise ValidationError(self.env._(
                    'Missing amendment evidence. Link an existing file or add a new one.'
                ))

    @api.constrains('source_evidence_id', 'origin_evidence_id', 'version_id')
    def _check_evidence_company(self):
        for evidence in self:
            company = evidence.version_id.company_id
            source = evidence.source_evidence_id
            if source and source.company_id != company:
                raise UserError(self.env._(
                    'Evidence cannot be filed under another company.'
                ))
            origin = evidence.origin_evidence_id
            if origin and origin.company_id != company:
                raise UserError(self.env._(
                    'Evidence cannot be filed under another company.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            version = self.env['cpla.customer.contract.version'].browse(values.get('version_id')).exists()
            if not version:
                raise ValidationError(self.env._('Evidence must be attached to a version.'))
            version.check_access('write')
            if version.state != 'draft':
                raise UserError(self.env._(
                    'Evidence cannot be added after the version leaves draft.'
                ))
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._('You are not allowed to add version evidence.'))
            if values.get('company_id') and values['company_id'] != version.company_id.id:
                raise UserError(self.env._(
                    'Evidence cannot be filed under another company.'
                ))
            values.pop('company_id', None)
            values['content_sha256'] = self._checksum_for_values(values)
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        if 'content_sha256' in vals:
            raise UserError(self.env._(
                'The evidence checksum is server-controlled. The historical file was not replaced.'
            ))
        if 'company_id' in vals and any(vals['company_id'] != evidence.company_id.id for evidence in self):
            raise UserError(self.env._('Evidence cannot be moved to another company.'))
        vals.pop('company_id', None)
        if 'version_id' in vals and any(vals['version_id'] != evidence.version_id.id for evidence in self):
            raise UserError(self.env._('Evidence cannot be moved to another version.'))
        for evidence in self:
            if evidence.version_id.state != 'draft':
                raise UserError(self.env._(
                    'Evidence supporting an approved version cannot be replaced. '
                    'Request an evidence correction. The file was not changed.'
                ))
            evidence.version_id.check_access('write')
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._('You are not allowed to change version evidence.'))
        if 'datas' in vals or 'source_evidence_id' in vals:
            vals['content_sha256'] = self._checksum_for_values(vals)
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        for evidence in self:
            if evidence.version_id.state != 'draft':
                raise UserError(self.env._(
                    'Evidence supporting an approved version cannot be deleted.'
                ))
            if not self.env.user.has_group(USER_GROUP):
                raise AccessError(self.env._('You are not allowed to delete version evidence.'))
        return super().unlink()

    @api.model
    def _checksum_for_values(self, values):
        raw = values.get('datas')
        if raw:
            return self._hash_binary(raw)
        if values.get('content_sha256'):
            return values['content_sha256']
        source = self.env['cpla.customer.contract.evidence'].browse(values.get('source_evidence_id')).exists()
        if source and source.datas:
            return self._hash_binary(source.datas)
        origin = self.browse(values.get('origin_evidence_id')).exists()
        if origin and origin.datas:
            return self._hash_binary(origin.datas)
        if origin and origin.content_sha256:
            return origin.content_sha256
        return False

    @api.model
    def _hash_binary(self, raw):
        if isinstance(raw, str):
            try:
                raw = base64.b64decode(raw)
            except binascii.Error as error:
                raise UserError(self.env._(
                    'The evidence file could not be read. It was not stored.'
                )) from error
        return hashlib.sha256(raw).hexdigest()


class CustomerContractVersionEvent(models.Model):
    """Append-only approval and amendment event.

    Ordinary users cannot edit or delete these rows. The actor and the
    timestamp are the authenticated user and the server clock. A client
    cannot supply either one. Context flags are not treated as permission.
    """

    _name = 'cpla.customer.contract.version.event'
    _description = 'Customer Contract Version Event'
    _order = 'occurred_at, id'
    _check_company_auto = True

    _event_type_once = models.Constraint(
        'UNIQUE(version_id, event_type)',
        'This version already has that history event.',
    )

    version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Version',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True,
    )
    contract_id = fields.Many2one(
        'cpla.customer.contract',
        related='version_id.contract_id',
        store=True,
        index=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='version_id.company_id',
        store=True,
        index=True,
        readonly=True,
    )
    event_type = fields.Selection(
        selection=EVENT_TYPES,
        string='Event',
        required=True,
        index=True,
    )
    actor_id = fields.Many2one(
        'res.users',
        string='Actor',
        required=True,
        readonly=True,
        ondelete='restrict',
        index=True,
    )
    occurred_at = fields.Datetime(
        string='Event Time',
        required=True,
        readonly=True,
        index=True,
    )
    reason = fields.Text(string='Reason')
    source_version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Source Version',
        readonly=True,
        ondelete='restrict',
    )
    supersedes_version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Superseded Version',
        readonly=True,
        ondelete='restrict',
    )
    approval_reference = fields.Char(string='Approval Reference', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            version = self.env['cpla.customer.contract.version'].browse(values.get('version_id')).exists()
            if not version:
                raise ValidationError(self.env._('A history event needs its version.'))
            version.check_access('read')
            event_type = values.get('event_type')
            self._assert_event_allowed(version, event_type)
            if values.get('company_id') and values['company_id'] != version.company_id.id:
                raise UserError(self.env._(
                    'A history event cannot be filed under another company.'
                ))
            values.pop('company_id', None)
            values['actor_id'] = self.env.user.id
            values['occurred_at'] = fields.Datetime.now()
            values['source_version_id'] = version.source_version_id.id
            values['supersedes_version_id'] = version.supersedes_version_id.id
            values['approval_reference'] = version.approval_reference
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals):
        raise UserError(self.env._(
            'Historical approval events cannot be edited.'
        ))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._(
            'Historical approval events cannot be deleted.'
        ))

    @api.model
    def _assert_event_allowed(self, version, event_type):
        allowed = {
            'draft': {'draft_created', 'amendment_created'},
            'ready_for_review': {
                'submitted', 'historical_reassessment_required', 'rejected', 'cancelled',
            },
            'approved': {'approved', 'supersession_recorded', 'evidence_correction_requested'},
            'rejected': {'rejected'},
            'cancelled': {'cancelled'},
        }
        if event_type not in allowed.get(version.state, set()):
            raise UserError(self.env._(
                'This history event does not match the version state. It was not recorded.'
            ))
        user = self.env.user
        if event_type in ('draft_created', 'amendment_created'):
            if user != version.requested_by_id and not user.has_group(MANAGER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to record this draft history event.'
                ))
        elif event_type == 'submitted':
            if user != version.submitted_by_id and not (
                user.has_group(MANAGER_GROUP) or user.has_group(FINANCE_MANAGER_GROUP)
            ):
                raise AccessError(self.env._(
                    'You are not allowed to record this submission event.'
                ))
        elif event_type in ('approved', 'supersession_recorded'):
            if user != version.approved_by_id:
                raise AccessError(self.env._(
                    'You are not allowed to record an approval event for another approver.'
                ))
        elif event_type == 'rejected':
            if user != version.rejected_by_id:
                raise AccessError(self.env._(
                    'You are not allowed to record a rejection event for another reviewer.'
                ))
        elif event_type == 'historical_reassessment_required':
            if not (user.has_group(MANAGER_GROUP) or user.has_group(FINANCE_MANAGER_GROUP)):
                raise AccessError(self.env._(
                    'You are not allowed to record a reassessment requirement.'
                ))
            version._check_approver()
        elif event_type == 'cancelled':
            if user != version.contract_id.owner_id and user != version.requested_by_id and not user.has_group(MANAGER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to record this cancellation.'
                ))
        elif event_type == 'evidence_correction_requested':
            if not user.has_group(MANAGER_GROUP):
                raise AccessError(self.env._(
                    'You are not allowed to record an evidence correction.'
                ))
        else:
            raise UserError(self.env._('This history event is not recognized.'))


class CustomerContractVersionCompare(models.TransientModel):
    """Read-only comparison of two versions the user can already read."""

    _name = 'cpla.customer.contract.version.compare'
    _description = 'Compare Contract Versions'

    baseline_version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Baseline Version',
        required=True,
    )
    candidate_version_id = fields.Many2one(
        'cpla.customer.contract.version',
        string='Candidate Version',
        required=True,
    )
    result_text = fields.Text(string='Comparison', readonly=True)
    result_html = fields.Html(string='Comparison Table', readonly=True, sanitize=True)

    def action_compare(self):
        self.ensure_one()
        baseline = self.baseline_version_id
        candidate = self.candidate_version_id
        baseline.check_access('read')
        candidate.check_access('read')
        if baseline.version_number > candidate.version_number:
            baseline, candidate = candidate, baseline
        comparison = baseline.compare_with(candidate)
        lines = ['%s -> %s' % (comparison['baseline'], comparison['candidate'])]
        lines.append('Recovered cash: no. A price delta is not cash recovered.')
        html_rows = [
            '<table class="table table-sm">',
            '<thead><tr><th>Category</th><th>Product</th><th>Baseline</th><th>Candidate</th><th>Unit delta</th><th>Normalization</th></tr></thead>',
            '<tbody>',
        ]
        for row in comparison['lines']:
            delta = '' if row['price_delta'] is None else row['price_delta']
            lines.append('%s | %s | %s | %s | %s' % (
                row['category'], row['product'], row['old_price'], row['new_price'], delta,
            ))
            html_rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                escape(row['category']),
                escape(row['product']),
                escape(self._money(row['old_price'])),
                escape(self._money(row['new_price'])),
                escape(self._money(delta)),
                escape('Required' if row['normalization_required'] else ''),
            ))
        html_rows.append('</tbody></table>')
        self.write({
            'baseline_version_id': baseline.id,
            'candidate_version_id': candidate.id,
            'result_text': '\n'.join(lines),
            'result_html': Markup(''.join(html_rows)),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    @staticmethod
    def _money(value):
        if value is None or value is False or value == '':
            return ''
        return str(value)
