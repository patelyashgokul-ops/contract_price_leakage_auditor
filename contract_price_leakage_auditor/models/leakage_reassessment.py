import hashlib
import json
import logging

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    FINANCE_MANAGER_GROUP,
    MANAGER_GROUP,
    REVIEWER_GROUP,
    _arithmetic,
    _decimal,
    _text,
)
from odoo.addons.contract_price_leakage_auditor.models.invoice_audit import (
    ENGINE_VERSION,
)

_logger = logging.getLogger(__name__)

MODULE = 'contract_price_leakage_auditor'
SEQUENCE = 'cpla.leakage.reassessment'
SNAPSHOT_SCHEMA = 'dev14.2'
ZERO = _decimal('0')

CREDIT_TRIGGERS = frozenset({
    'verified_quantity_return',
    'price_adjustment_credit',
    'full_invoice_reversal',
})
OPEN_STATES = (
    'requested',
    'under_evaluation',
    'proposed_revision_ready',
    'evidence_review_required',
    'blocked',
    'failed',
)
EVALUABLE_STATES = OPEN_STATES
SOURCE_MODELS = (
    'account.move',
    'cpla.customer.contract.version',
    'cpla.leakage.finding',
)
TRIGGER_CLASS = {
    'verified_quantity_return': 'financially_material',
    'price_adjustment_credit': 'financially_material',
    'full_invoice_reversal': 'financially_material',
    'replacement_invoice': 'financially_material',
    'quantity_tier_requalification': 'financially_material',
    'approved_retroactive_amendment': 'authority_material',
    'approved_discount_correction': 'authority_material',
    'contract_precedence_correction': 'authority_material',
    'historical_fx_correction': 'authority_material',
    'tax_basis_correction': 'authority_material',
    'uom_conversion_correction': 'authority_material',
    'invoice_source_mapping_correction': 'source_mapping_material',
    'duplicate_finding_correction': 'source_mapping_material',
    'manual_authorized_review': 'unknown_impact',
    'other_documented_trigger': 'unknown_impact',
}
TRIGGERS = [
    ('verified_quantity_return', 'Verified quantity return'),
    ('price_adjustment_credit', 'Price adjustment credit'),
    ('full_invoice_reversal', 'Full invoice reversal'),
    ('replacement_invoice', 'Replacement invoice'),
    ('approved_retroactive_amendment', 'Approved retroactive amendment'),
    ('approved_discount_correction', 'Approved discount correction'),
    ('contract_precedence_correction', 'Contract precedence correction'),
    ('historical_fx_correction', 'Historical FX correction'),
    ('tax_basis_correction', 'Tax basis correction'),
    ('uom_conversion_correction', 'UoM conversion correction'),
    ('invoice_source_mapping_correction', 'Invoice source mapping correction'),
    ('quantity_tier_requalification', 'Quantity tier requalification'),
    ('duplicate_finding_correction', 'Duplicate finding correction'),
    ('manual_authorized_review', 'Manual authorized review'),
    ('other_documented_trigger', 'Other documented trigger'),
]
STATES = [
    ('requested', 'Requested'),
    ('under_evaluation', 'Under evaluation'),
    ('proposed_revision_ready', 'Proposed revision ready'),
    ('evidence_review_required', 'Evidence review required'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
    ('blocked', 'Blocked'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
]
DELTA_CLASSES = [
    ('exposure_increased', 'Exposure increased'),
    ('exposure_decreased', 'Exposure decreased'),
    ('exposure_eliminated', 'Exposure eliminated'),
    ('amount_unchanged_evidence_changed', 'Amount unchanged, evidence changed'),
    ('no_material_change', 'No material change'),
    ('undetermined', 'Undetermined'),
]
CHANGE_CLASSES = [
    ('financially_material', 'Financially material'),
    ('authority_material', 'Authority material'),
    ('source_mapping_material', 'Source mapping material'),
    ('evidence_material', 'Evidence material'),
    ('non_material', 'Non material'),
    ('unknown_impact', 'Unknown impact'),
]
NOT_RECOVERY = (
    'The difference is an evidence correction. It is not recovered cash and it is not an approved write-off.'
)
MATERIAL_CHANGE = frozenset({
    'financially_material',
    'authority_material',
    'source_mapping_material',
})
VERIFICATION_STATES = [
    ('current_verified', 'Current verified'),
    ('source_changed_review_pending', 'Source changed, review pending'),
    ('reassessment_proposed', 'Reassessment proposed'),
    ('reassessment_accepted', 'Reassessment accepted'),
    ('historical_superseded', 'Historical superseded'),
    ('current_result_uncertain', 'Current result uncertain'),
]


def _canonical(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return raw, hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _none(value):
    if value is False or value is None or value == '':
        return None
    return value


class LeakageReassessment(models.Model):
    """A controlled proposal to reread one current leakage finding.

    Preview uses the DEV-12 price pipeline and does not store a finding.
    Acceptance is a separate finance-manager decision. The original audit
    result row is not rewritten. A digest in this database is not a legal archive.
    """

    _name = 'cpla.leakage.reassessment'
    _description = 'Leakage Reassessment'
    _order = 'id desc'
    _check_company_auto = True

    _open_request_unique = models.UniqueIndex(
        "(finding_id, trigger_type, source_model, source_res_id, company_id) "
        "WHERE state IN ('requested', 'under_evaluation', 'proposed_revision_ready', "
        "'evidence_review_required', 'blocked')",
        'An open reassessment already exists for this finding, trigger, and source.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    finding_id = fields.Many2one(
        'cpla.leakage.finding', required=True, index=True, readonly=True, ondelete='restrict',
    )
    partner_id = fields.Many2one(
        'res.partner', related='finding_id.partner_id', readonly=True,
    )
    case_id = fields.Many2one('cpla.leakage.case', readonly=True, index=True, ondelete='restrict')
    trigger_type = fields.Selection(selection=TRIGGERS, required=True, readonly=True, index=True)
    change_class = fields.Selection(selection=CHANGE_CLASSES, required=True, readonly=True)
    source_model = fields.Selection(
        selection=[
            ('account.move', 'Invoice or credit note'),
            ('cpla.customer.contract.version', 'Contract version'),
            ('cpla.leakage.finding', 'Leakage finding'),
        ],
        required=True,
        readonly=True,
    )
    source_res_id = fields.Integer(readonly=True, index=True)
    state = fields.Selection(selection=STATES, required=True, default='requested', readonly=True, index=True)
    evaluation_policy = fields.Selection(
        selection=[('as_known_at_cutoff', 'As known at the requested cutoff')],
        required=True,
        default='as_known_at_cutoff',
        readonly=True,
    )
    knowledge_cutoff = fields.Datetime(
        readonly=True,
        help='Knowledge cutoff sent to the DEV-12 engine. It is not the invoice date and it is not a pricing date.',
    )
    reason = fields.Text(required=True, readonly=True)
    requested_by_id = fields.Many2one('res.users', readonly=True, index=True)
    requested_at = fields.Datetime(readonly=True)
    evaluated_by_id = fields.Many2one('res.users', readonly=True)
    evaluated_at = fields.Datetime(readonly=True)
    decision_by_id = fields.Many2one('res.users', readonly=True)
    decision_at = fields.Datetime(readonly=True)
    decision_reason = fields.Text(readonly=True)
    original_result_id = fields.Many2one('cpla.invoice.audit.result', readonly=True, ondelete='restrict')
    original_identity = fields.Char(readonly=True, index=True)
    original_fingerprint = fields.Char(readonly=True)
    original_revision = fields.Integer(readonly=True)
    original_cutoff = fields.Datetime(readonly=True)
    original_exposure_exact = fields.Char(readonly=True)
    original_currency_id = fields.Many2one('res.currency', readonly=True)
    original_quantity_exact = fields.Char(readonly=True)
    original_adjusted_exact = fields.Char(readonly=True)
    original_actual_exact = fields.Char(readonly=True)
    original_version_id = fields.Many2one('cpla.customer.contract.version', readonly=True)
    proposed_identity = fields.Char(readonly=True, index=True)
    proposed_fingerprint = fields.Char(readonly=True)
    proposed_cutoff_token = fields.Char(readonly=True)
    proposed_classification = fields.Char(readonly=True)
    proposed_version_id = fields.Many2one('cpla.customer.contract.version', readonly=True)
    proposed_pricing_date = fields.Date(readonly=True)
    proposed_adjusted_exact = fields.Char(readonly=True)
    proposed_actual_exact = fields.Char(readonly=True)
    proposed_quantity_exact = fields.Char(readonly=True)
    proposed_exposure_exact = fields.Char(readonly=True)
    comparison_currency_id = fields.Many2one('res.currency', readonly=True)
    delta_exact = fields.Char(
        readonly=True,
        help='Proposed potential exposure minus the previously accepted amount when the identity and currency match. Blank means the amounts were not subtracted.',
    )
    delta_class = fields.Selection(selection=DELTA_CLASSES, readonly=True)
    credit_class_observed = fields.Char(readonly=True)
    credit_quantity_trusted = fields.Boolean(readonly=True)
    calculation_authoritative = fields.Boolean(readonly=True)
    difference_explanation = fields.Text(readonly=True)
    review_reason = fields.Text(readonly=True)
    proposal_payload = fields.Text(readonly=True)
    proposal_digest = fields.Char(readonly=True)
    original_proposal_payload = fields.Text(readonly=True)
    original_proposal_digest = fields.Char(
        readonly=True,
        help='Digest of the first proposal. Later evaluations do not replace it. A matching digest is not a legal certification.',
    )
    digest_mismatch = fields.Boolean(readonly=True)
    verification_outcome = fields.Char(readonly=True)
    verified_at = fields.Datetime(readonly=True)
    schema_version = fields.Char(readonly=True, default=SNAPSHOT_SCHEMA)
    engine_version = fields.Char(readonly=True, default=ENGINE_VERSION)
    apply_run_id = fields.Many2one('cpla.invoice.audit.run', readonly=True, ondelete='restrict')
    successor_finding_id = fields.Many2one('cpla.leakage.finding', readonly=True, ondelete='restrict')
    successor_result_id = fields.Many2one('cpla.invoice.audit.result', readonly=True, ondelete='restrict')
    is_recovered_cash = fields.Boolean(readonly=True, default=False)
    is_writeoff = fields.Boolean(readonly=True, default=False)
    error_summary = fields.Text(readonly=True)
    event_ids = fields.One2many('cpla.leakage.reassessment.event', 'reassessment_id')

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._(
            'A reassessment is requested from a current finding. Client amounts are ignored.'
        ))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        raise UserError(self.env._('Reassessment evidence cannot be overwritten.'))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.check_access('unlink')
        raise UserError(self.env._('A reassessment cannot be deleted.'))

    def export_data(self, fields_to_export):
        if self.env.user.share or not self.env.user.active:
            raise UserError(self.env._('Reassessment evidence cannot be exported by a public user.'))
        self.check_access('read')
        return super().export_data(fields_to_export)

    @api.model
    def request_for_finding(self, finding_id, trigger_type, reason, source_model=None,
                            source_res_id=None, knowledge_cutoff=None, case_id=None):
        """Record a request. This does not price the invoice and does not accept a result."""
        self._check_requester()
        finding = self.env['cpla.leakage.finding'].browse(finding_id).exists()
        if len(finding) != 1:
            raise UserError(self.env._('Choose one current leakage finding.'))
        finding.check_access('read')
        self._check_company_record(finding.company_id)
        if not finding.is_current:
            raise UserError(self.env._(
                'Reassessment starts from the current finding. A superseded row was not reopened.'
            ))
        if trigger_type not in TRIGGER_CLASS:
            raise UserError(self.env._('That reassessment trigger is not supported.'))
        if not reason or not str(reason).strip():
            raise UserError(self.env._('A reassessment request needs a reason.'))
        source_model, source_res_id = self._normalize_source(
            finding, trigger_type, source_model, source_res_id,
        )
        cutoff = finding.knowledge_cutoff if knowledge_cutoff is None else (knowledge_cutoff or False)
        case = self._case_for(finding, case_id)
        existing = self._open_match(finding, trigger_type, source_model, source_res_id)
        if existing:
            return existing
        self._refuse_duplicate_acceptance(finding, trigger_type, source_model, source_res_id)
        reference = self.env['ir.sequence'].with_company(finding.company_id).next_by_code(SEQUENCE)
        if not reference:
            raise UserError(self.env._(
                'The reassessment sequence is missing. No reference was invented.'
            ))
        origin = self.env['cpla.invoice.audit.result'].search([
            ('finding_id', '=', finding.id),
            ('company_id', '=', finding.company_id.id),
        ], order='id desc', limit=1)
        values = {
            'reference': reference,
            'company_id': finding.company_id.id,
            'finding_id': finding.id,
            'case_id': case.id if case else False,
            'trigger_type': trigger_type,
            'change_class': TRIGGER_CLASS[trigger_type],
            'source_model': source_model,
            'source_res_id': source_res_id,
            'state': 'requested',
            'evaluation_policy': 'as_known_at_cutoff',
            'knowledge_cutoff': cutoff,
            'reason': str(reason).strip(),
            'requested_by_id': self.env.user.id,
            'requested_at': fields.Datetime.now(),
            'original_result_id': origin.id if origin else False,
            'original_identity': finding.current_identity,
            'original_fingerprint': finding.input_fingerprint,
            'original_revision': finding.calculation_revision or 0,
            'original_cutoff': finding.knowledge_cutoff,
            'original_exposure_exact': finding.potential_leakage_exact or False,
            'original_currency_id': finding.currency_id.id,
            'original_quantity_exact': finding.eligible_quantity_exact or False,
            'original_adjusted_exact': finding.approved_adjusted_exact or False,
            'original_actual_exact': finding.actual_unit_exact or False,
            'original_version_id': finding.version_id.id,
            'schema_version': SNAPSHOT_SCHEMA,
            'engine_version': ENGINE_VERSION,
            'is_recovered_cash': False,
            'is_writeoff': False,
        }
        try:
            with self.env.cr.savepoint():
                record = models.Model.create(self, [values])
        except IntegrityError:
            existing = self._open_match(finding, trigger_type, source_model, source_res_id)
            if existing:
                return existing
            raise
        record._log('requested', values['reason'], prior_state=False, new_state='requested')
        record._refresh_reinvestigation_flag()
        return record

    def action_evaluate(self):
        """Price a proposal with DEV-12. The current finding stays where it is."""
        for record in self:
            record._check_finance_manager()
            record._check_company_record(record.company_id)
            if record.state not in EVALUABLE_STATES:
                raise UserError(self.env._(
                    'This reassessment cannot be evaluated from its current state.'
                ))
            finding = record.finding_id
            if not finding.is_current or finding.input_fingerprint != record.original_fingerprint:
                record._set_state('blocked', (
                    'The current finding changed before evaluation. '
                    'Request a new reassessment from the current finding.'
                ))
                continue
            models.Model.write(record, {'state': 'under_evaluation', 'error_summary': False})
            try:
                outcome = record._evaluate_outcome()
            except AccessError:
                raise
            except UserError as error:
                outcome = record._review_values(str(error))
            except Exception:
                _logger.info('CPLA reassessment evaluation failed id=%s', record.id)
                record._set_state('failed', (
                    'The reassessment calculation failed. No amount was accepted.'
                ))
                continue
            record._store_outcome(outcome)
        return True

    def action_verify_digest(self):
        """Recompute the proposal digest. The stored digest is not replaced."""
        for record in self:
            record.check_access('read')
            record._check_company_record(record.company_id)
            _text_value, current_hash = _canonical(record._payload())
            mismatch = current_hash != (record.proposal_digest or '')
            if record.original_proposal_payload and record.original_proposal_digest:
                original_hash = hashlib.sha256(
                    record.original_proposal_payload.encode('utf-8')
                ).hexdigest()
                if original_hash != record.original_proposal_digest:
                    mismatch = True
            models.Model.write(record, {
                'digest_mismatch': mismatch,
                'verification_outcome': 'mismatch' if mismatch else 'match',
                'verified_at': fields.Datetime.now(),
            })
        return True

    def action_accept(self, reason):
        """Accept a ready proposal. The engine stores the successor only after the checks pass."""
        if not reason or not str(reason).strip():
            raise UserError(self.env._('Accepting a reassessment needs a reason.'))
        for record in self:
            record._check_finance_manager()
            record._check_company_record(record.company_id)
            if record.requested_by_id == self.env.user:
                raise AccessError(self.env._(
                    'The person who requested this reassessment cannot accept it.'
                ))
            if record.state != 'proposed_revision_ready':
                raise UserError(self.env._(
                    'Only a proposed revision can be accepted. A completed calculation is not acceptance.'
                ))
            if record.is_recovered_cash or record.is_writeoff:
                raise UserError(self.env._(
                    'A reassessment cannot be marked as recovered cash or a write-off.'
                ))
            gaps = record._evidence_gaps()
            if gaps:
                record._set_state('blocked', ' '.join(gaps))
                continue
            record.action_verify_digest()
            if record.digest_mismatch or not record.proposal_digest:
                record._set_state('blocked', 'The stored proposal no longer matches its digest.')
                continue
            fresh = record._evaluate_outcome()
            if (
                not fresh.get('authoritative')
                or fresh.get('fingerprint') != record.proposed_fingerprint
                or _none(fresh.get('exposure')) != _none(record.proposed_exposure_exact)
                or fresh.get('identity') != record.proposed_identity
            ):
                record._set_state('blocked', (
                    'Source evidence changed after the proposal. Evaluate again before acceptance.'
                ))
                continue
            prior = record.state
            try:
                with self.env.cr.savepoint():
                    run = record._apply()
                    successor, result = record._stored_successor(run)
                    record._require_successor(successor, result)
                    models.Model.write(record, {
                        'state': 'accepted',
                        'decision_by_id': self.env.user.id,
                        'decision_at': fields.Datetime.now(),
                        'decision_reason': str(reason).strip(),
                        'apply_run_id': run.id,
                        'successor_finding_id': successor.id if successor else False,
                        'successor_result_id': result.id if result else False,
                        'error_summary': False,
                        'is_recovered_cash': False,
                        'is_writeoff': False,
                    })
                    record._sync_cases()
                    record._log(
                        'accepted', str(reason).strip(),
                        prior_state=prior, new_state='accepted',
                    )
                    record._log(
                        'current_revision_changed', str(reason).strip(),
                        prior_state=prior, new_state='accepted',
                    )
            except UserError as error:
                record._set_state('blocked', str(error))
        return True

    def action_reject(self, reason):
        if not reason or not str(reason).strip():
            raise UserError(self.env._('Rejecting a reassessment needs a reason.'))
        for record in self:
            record._check_finance_reviewer()
            record._check_company_record(record.company_id)
            if record.state not in ('proposed_revision_ready', 'evidence_review_required'):
                raise UserError(self.env._('This reassessment is not waiting for a decision.'))
            prior = record.state
            models.Model.write(record, {
                'state': 'rejected',
                'decision_by_id': self.env.user.id,
                'decision_at': fields.Datetime.now(),
                'decision_reason': str(reason).strip(),
            })
            record._log('rejected', str(reason).strip(), prior_state=prior, new_state='rejected')
            record._refresh_reinvestigation_flag()
        return True

    def action_cancel(self, reason):
        if not reason or not str(reason).strip():
            raise UserError(self.env._('Cancelling a reassessment needs a reason.'))
        for record in self:
            record._check_requester()
            record._check_company_record(record.company_id)
            if record.state not in EVALUABLE_STATES:
                raise UserError(self.env._('This reassessment can no longer be cancelled.'))
            prior = record.state
            models.Model.write(record, {
                'state': 'cancelled',
                'decision_by_id': self.env.user.id,
                'decision_at': fields.Datetime.now(),
                'decision_reason': str(reason).strip(),
            })
            record._log('cancelled', str(reason).strip(), prior_state=prior, new_state='cancelled')
            record._refresh_reinvestigation_flag()
        return True

    def action_open_form(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.reference,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _decision_wizard(self, operation):
        self.ensure_one()
        self.check_access('read')
        wizard = self.env['cpla.leakage.reassessment.wizard'].create({
            'company_id': self.company_id.id,
            'finding_id': self.finding_id.id,
            'reassessment_id': self.id,
            'operation': operation,
            'trigger_type': self.trigger_type,
            'reason': 'Record the decision reason.',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Reassessment decision'),
            'res_model': 'cpla.leakage.reassessment.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_accept_wizard(self):
        return self._decision_wizard('accept')

    def action_open_reject_wizard(self):
        return self._decision_wizard('reject')

    def action_open_cancel_wizard(self):
        return self._decision_wizard('cancel')

    @api.model
    def _check_requester(self):
        user = self.env.user
        if self.env.su or user._is_superuser() or user.has_group(MANAGER_GROUP):
            return
        raise AccessError(self.env._('Only a contract manager can request a reassessment.'))

    def _check_finance_manager(self):
        user = self.env.user
        if self.env.su or user._is_superuser() or user.has_group(FINANCE_MANAGER_GROUP):
            if not self.env['cpla.invoice.audit.run']._can_run():
                raise AccessError(self.env._('You cannot run the audit calculation.'))
            if not self.env['cpla.invoice.source']._can_map():
                raise AccessError(self.env._('You cannot read invoice source evidence.'))
            return
        raise AccessError(self.env._(
            'Only a finance manager can evaluate or accept a reassessment.'
        ))

    def _check_finance_reviewer(self):
        user = self.env.user
        if self.env.su or user._is_superuser():
            return
        if user.has_group(FINANCE_MANAGER_GROUP) or user.has_group(REVIEWER_GROUP):
            return
        raise AccessError(self.env._('Only finance review can reject a reassessment.'))

    def _check_company_record(self, company):
        if self.env.su or self.env.user._is_superuser():
            return
        if company not in self.env.companies:
            raise AccessError(self.env._('You cannot use a reassessment for this company.'))

    @api.model
    def _normalize_source(self, finding, trigger_type, source_model, source_res_id):
        if trigger_type in CREDIT_TRIGGERS or trigger_type == 'replacement_invoice':
            if source_model != 'account.move' or not source_res_id:
                raise UserError(self.env._(
                    'This trigger needs the posted credit note or replacement invoice.'
                ))
            return 'account.move', int(source_res_id)
        if source_model or source_res_id:
            if source_model not in SOURCE_MODELS or not source_res_id:
                raise UserError(self.env._(
                    'That source cannot be used as reassessment evidence.'
                ))
            return source_model, int(source_res_id)
        return 'cpla.leakage.finding', finding.id

    @api.model
    def _case_for(self, finding, case_id):
        if case_id:
            case = self.env['cpla.leakage.case'].browse(case_id).exists()
            if len(case) != 1 or case.company_id != finding.company_id:
                raise UserError(self.env._('The investigation case is not in this company.'))
            case.check_access('read')
            return case
        case = finding.current_case_id
        if case and case.company_id == finding.company_id:
            return case
        return self.env['cpla.leakage.case']

    @api.model
    def _open_match(self, finding, trigger_type, source_model, source_res_id):
        return self.search([
            ('finding_id', '=', finding.id),
            ('trigger_type', '=', trigger_type),
            ('source_model', '=', source_model),
            ('source_res_id', '=', source_res_id),
            ('company_id', '=', finding.company_id.id),
            ('state', 'in', list(OPEN_STATES)),
        ], limit=1)

    @api.model
    def _refuse_duplicate_acceptance(self, finding, trigger_type, source_model, source_res_id):
        accepted = self.search([
            ('finding_id', '=', finding.id),
            ('trigger_type', '=', trigger_type),
            ('source_model', '=', source_model),
            ('source_res_id', '=', source_res_id),
            ('company_id', '=', finding.company_id.id),
            ('state', '=', 'accepted'),
        ], order='id desc', limit=1)
        if accepted and finding.input_fingerprint == accepted.proposed_fingerprint:
            raise UserError(self.env._(
                'This trigger was already accepted and the current evidence fingerprint has not changed.'
            ))

    def _evaluate_outcome(self):
        self.ensure_one()
        gate = self._source_gate()
        if gate.get('reason'):
            return self._review_values(gate['reason'], gate.get('credit_class'), gate.get('trusted'))
        return self._price_values(gate)

    def _source_gate(self):
        self.ensure_one()
        trigger = self.trigger_type
        if trigger in CREDIT_TRIGGERS:
            move, reason = self._readable_source_move()
            if reason:
                return {'reason': reason, 'credit_class': '', 'trusted': False}
            if move.state != 'posted' or move.move_type != 'out_refund':
                return {
                    'reason': 'The source is not a posted customer credit note.',
                    'credit_class': '',
                    'trusted': False,
                }
            if move.company_id != self.company_id:
                return {
                    'reason': 'The credit note belongs to another company.',
                    'credit_class': '',
                    'trusted': False,
                }
            self.env['cpla.invoice.source'].map_move(move)
            current = self._credit_maps(move)
            if not current:
                return {
                    'reason': 'The credit note is not linked to this invoice line.',
                    'credit_class': '',
                    'trusted': False,
                }
            mapping = current[:1]
            kind = mapping.credit_class or ''
            trusted = bool(mapping.quantity_trusted)
            product_reason = self._credit_product_reason(mapping)
            if product_reason:
                return {'reason': product_reason, 'credit_class': kind, 'trusted': trusted}
            if trigger == 'verified_quantity_return' and not (kind == 'QUANTITY_RETURN' and trusted):
                return {
                    'reason': (
                        'The credit is not a verified quantity return. '
                        'No returned quantity was invented.'
                    ),
                    'credit_class': kind,
                    'trusted': trusted,
                }
            if trigger == 'full_invoice_reversal' and not (kind == 'FULL_REVERSAL' and trusted):
                return {
                    'reason': (
                        'The credit is not a verified full reversal. Exposure was not forced to zero.'
                    ),
                    'credit_class': kind,
                    'trusted': trusted,
                }
            if trigger == 'price_adjustment_credit' and kind != 'PRICE_ADJUSTMENT':
                return {
                    'reason': 'The credit is not an amount-only price adjustment.',
                    'credit_class': kind,
                    'trusted': trusted,
                }
            return {'reason': '', 'credit_class': kind, 'trusted': trusted, 'move': move}
        if trigger == 'replacement_invoice':
            return self._replacement_gate()
        if trigger == 'approved_discount_correction':
            return self._discount_correction_gate()
        if trigger in ('historical_fx_correction', 'tax_basis_correction'):
            return {
                'reason': (
                    'No verified replacement FX rate or tax evidence was supplied. '
                    'No corrected amount was fabricated.'
                ),
                'credit_class': '',
                'trusted': False,
            }
        return {'reason': '', 'credit_class': '', 'trusted': False}

    def _discount_correction_gate(self):
        finding = self.finding_id
        approvals = self.env['cpla.discount.approval'].search([
            ('company_id', '=', self.company_id.id),
            ('partner_id', '=', finding.partner_id.id),
            ('product_id', '=', finding.product_id.id),
            ('state', '=', 'approved'),
        ])
        cutoff = self.knowledge_cutoff
        if cutoff:
            approvals = approvals.filtered(
                lambda approval: approval.approved_at and approval.approved_at <= cutoff
            )
        if not approvals:
            return {
                'reason': (
                    'No approved discount correction is visible at this cutoff. '
                    'The previous price was not replaced.'
                ),
                'credit_class': '',
                'trusted': False,
            }
        return {'reason': '', 'credit_class': '', 'trusted': False}

    def _replacement_gate(self):
        move, reason = self._readable_source_move()
        if reason:
            return {'reason': reason, 'credit_class': '', 'trusted': False}
        if move.state != 'posted' or move.move_type != 'out_invoice':
            return {
                'reason': 'The replacement source is not a posted customer invoice.',
                'credit_class': '',
                'trusted': False,
            }
        if move == self.finding_id.move_id or move.company_id != self.company_id:
            return {
                'reason': 'The replacement invoice is not a separate document in this company.',
                'credit_class': '',
                'trusted': False,
            }
        self.env['cpla.invoice.source'].map_move(move)
        credits = self.env['cpla.invoice.source.map'].search([
            ('origin_line_id', '=', self.finding_id.move_line_id.id),
            ('company_id', '=', self.company_id.id),
            ('is_current', '=', True),
            ('quantity_trusted', '=', True),
            ('credit_class', '=', 'FULL_REVERSAL'),
        ])
        if not credits:
            return {
                'reason': (
                    'No verified full reversal links this invoice to a replacement. '
                    'Exposure was not forced to zero.'
                ),
                'credit_class': '',
                'trusted': False,
            }
        return {'reason': '', 'credit_class': 'FULL_REVERSAL', 'trusted': True, 'move': move}

    def _readable_source_move(self):
        if self.source_model != 'account.move' or not self.source_res_id:
            return self.env['account.move'], 'The source document is missing.'
        move = self.env['account.move'].browse(self.source_res_id).exists()
        if len(move) != 1:
            return self.env['account.move'], 'The source document does not exist.'
        try:
            move.check_access('read')
        except AccessError:
            return self.env['account.move'], 'The source document is not readable in this company.'
        return move, ''

    def _credit_maps(self, move):
        maps = self.env['cpla.invoice.source.map'].search([
            ('move_id', '=', move.id),
            ('company_id', '=', self.company_id.id),
            ('is_current', '=', True),
            ('origin_line_id', '=', self.finding_id.move_line_id.id),
        ])
        return maps

    def _credit_product_reason(self, mapping):
        finding = self.finding_id
        if mapping.product_id and finding.product_id and mapping.product_id != finding.product_id:
            return 'The credit product does not match the finding.'
        origin_uom = finding.move_line_id.product_uom_id
        if mapping.uom_id and origin_uom and mapping.uom_id != origin_uom:
            return 'The credit unit does not match the invoice line.'
        return ''

    def _price_values(self, gate):
        self.ensure_one()
        origin = self._origin_map()
        allocation = self._allocation(origin)
        if not origin or not allocation:
            return self._review_values(
                'The invoice line has no current source allocation.',
                gate.get('credit_class'),
                gate.get('trusted'),
            )
        run = self._virtual_run()
        outcome = run._price_allocation(origin, allocation)
        if not outcome.get('authoritative') or outcome.get('potential') is None:
            reason = outcome.get('review_reason') or 'The audit engine did not return an authoritative amount.'
            return self._review_values(reason, gate.get('credit_class'), gate.get('trusted'), outcome)
        if self.trigger_type == 'price_adjustment_credit':
            eligible = _decimal(_text(outcome.get('eligible')) if outcome.get('eligible') is not None else False)
            original_qty = _decimal(self.finding_id.eligible_quantity_exact)
            if eligible is None or original_qty is None or eligible != original_qty:
                return self._review_values(
                    'A monetary credit changed the eligible quantity. That reduction was not accepted.',
                    gate.get('credit_class'),
                    gate.get('trusted'),
                    outcome,
                )
        return self._values_from_engine(outcome, gate, review=False)

    def _review_values(self, reason, credit_class='', trusted=False, outcome=None):
        values = self._empty_proposal(reason, credit_class, trusted)
        if outcome and outcome.get('classification'):
            values['proposed_classification'] = outcome.get('classification')
        values['state'] = 'evidence_review_required'
        values['calculation_authoritative'] = False
        values['delta_class'] = 'undetermined'
        return {
            'values': values,
            'event': 'evidence_review',
            'log_reason': reason,
            'authoritative': False,
            'fingerprint': '',
            'identity': '',
            'exposure': None,
        }

    def _values_from_engine(self, outcome, gate, review):
        run = self._virtual_run()
        origin = self._origin_map()
        allocation = self._allocation(origin)
        identity = run._identity(origin.move_line_id, allocation)
        fingerprint = run._fingerprint(origin, allocation, outcome)
        currency = outcome.get('comparison_currency') or origin.currency_id
        version = outcome.get('version')
        exposure = _text(outcome['potential']) if outcome.get('potential') is not None else False
        same_identity = identity == (self.original_identity or '')
        same_currency = bool(
            currency and self.original_currency_id and currency == self.original_currency_id
        )
        delta_text, delta_class = self._delta(
            self.original_exposure_exact, exposure, same_currency, same_identity, fingerprint,
        )
        explanation = self._explanation(outcome, exposure, delta_text, delta_class, same_identity, run)
        values = {
            'state': 'evidence_review_required' if review or not outcome.get('authoritative') else 'proposed_revision_ready',
            'calculation_authoritative': bool(outcome.get('authoritative')) and not review,
            'proposed_identity': identity,
            'proposed_fingerprint': fingerprint,
            'proposed_cutoff_token': run._cutoff_token(),
            'proposed_classification': outcome.get('classification') or False,
            'proposed_version_id': version.id if version else False,
            'proposed_pricing_date': self._as_date(outcome.get('pricing_date')),
            'proposed_adjusted_exact': _text(outcome['adjusted']) if outcome.get('adjusted') is not None else False,
            'proposed_actual_exact': _text(outcome['actual']) if outcome.get('actual') is not None else False,
            'proposed_quantity_exact': _text(outcome['eligible']) if outcome.get('eligible') is not None else False,
            'proposed_exposure_exact': exposure or False,
            'comparison_currency_id': currency.id if currency else False,
            'delta_exact': delta_text or False,
            'delta_class': delta_class,
            'credit_class_observed': gate.get('credit_class') or False,
            'credit_quantity_trusted': bool(gate.get('trusted')),
            'difference_explanation': explanation,
            'review_reason': False,
        }
        if not values['calculation_authoritative']:
            values['state'] = 'evidence_review_required'
            values['delta_class'] = 'undetermined'
            values['delta_exact'] = False
        return {
            'values': values,
            'event': 'proposal_ready' if values['state'] == 'proposed_revision_ready' else 'evidence_review',
            'log_reason': values['difference_explanation'],
            'authoritative': values['calculation_authoritative'],
            'fingerprint': fingerprint,
            'identity': identity,
            'exposure': exposure or None,
        }

    def _empty_proposal(self, reason, credit_class, trusted):
        return {
            'proposed_identity': False,
            'proposed_fingerprint': False,
            'proposed_cutoff_token': False,
            'proposed_classification': False,
            'proposed_version_id': False,
            'proposed_pricing_date': False,
            'proposed_adjusted_exact': False,
            'proposed_actual_exact': False,
            'proposed_quantity_exact': False,
            'proposed_exposure_exact': False,
            'comparison_currency_id': False,
            'delta_exact': False,
            'delta_class': 'undetermined',
            'credit_class_observed': credit_class or False,
            'credit_quantity_trusted': bool(trusted),
            'difference_explanation': reason,
            'review_reason': reason,
            'calculation_authoritative': False,
        }

    def _delta(self, original_text, proposed_text, same_currency, same_identity, fingerprint):
        if not same_identity or not same_currency:
            return False, 'undetermined'
        original = _decimal(original_text)
        proposed = _decimal(proposed_text)
        if original is None or proposed is None:
            return False, 'undetermined'
        difference = _arithmetic('sub', proposed, original)
        if proposed == ZERO and original > ZERO:
            klass = 'exposure_eliminated'
        elif difference > ZERO:
            klass = 'exposure_increased'
        elif difference < ZERO:
            klass = 'exposure_decreased'
        elif fingerprint != (self.original_fingerprint or ''):
            klass = 'amount_unchanged_evidence_changed'
        else:
            klass = 'no_material_change'
        return _text(difference), klass

    def _explanation(self, outcome, exposure, delta_text, delta_class, same_identity, run):
        version = outcome.get('version')
        lines = [
            'Knowledge cutoff %s. Engine %s. Schema %s.' % (
                run._cutoff_token(), ENGINE_VERSION, SNAPSHOT_SCHEMA,
            ),
            'Previously accepted exposure %s. Proposed exposure %s.' % (
                self.original_exposure_exact or 'missing',
                exposure or 'missing',
            ),
        ]
        if version:
            lines.append('Engine contract version %s.' % (version.reference or version.id))
        if outcome.get('trace'):
            lines.append(outcome['trace'])
        if not same_identity:
            lines.append(
                'This cutoff is a different economic identity. The amounts were not subtracted '
                'and the other cutoff was not replaced.'
            )
        elif delta_text:
            lines.append('Comparable delta %s (%s).' % (delta_text, delta_class or ''))
        else:
            lines.append('The amounts were not subtracted.')
        lines.append(NOT_RECOVERY)
        if self.trigger_type == 'price_adjustment_credit':
            lines.append('The credit was not converted into returned pieces.')
        return '\n'.join(lines)

    def _store_outcome(self, outcome):
        values = dict(outcome['values'])
        values.update({
            'evaluated_by_id': self.env.user.id,
            'evaluated_at': fields.Datetime.now(),
            'error_summary': False,
            'is_recovered_cash': False,
            'is_writeoff': False,
        })
        models.Model.write(self, values)
        text, digest = _canonical(self._payload())
        extra = {
            'proposal_payload': text,
            'proposal_digest': digest,
            'digest_mismatch': False,
            'verification_outcome': 'match',
            'verified_at': fields.Datetime.now(),
        }
        if not self.original_proposal_digest:
            extra['original_proposal_payload'] = text
            extra['original_proposal_digest'] = digest
        models.Model.write(self, extra)
        self._log(outcome['event'], outcome.get('log_reason') or '')

    def _payload(self):
        self.ensure_one()
        return {
            'schema': SNAPSHOT_SCHEMA,
            'engine': ENGINE_VERSION,
            'company_id': self.company_id.id,
            'finding_id': self.finding_id.id,
            'trigger': self.trigger_type,
            'source_model': self.source_model,
            'source_res_id': self.source_res_id or 0,
            'original_identity': self.original_identity or '',
            'original_fingerprint': self.original_fingerprint or '',
            'original_exposure': _none(self.original_exposure_exact),
            'original_quantity': _none(self.original_quantity_exact),
            'original_adjusted': _none(self.original_adjusted_exact),
            'original_actual': _none(self.original_actual_exact),
            'original_revision': self.original_revision or 0,
            'cutoff': self.proposed_cutoff_token or '',
            'proposed_identity': self.proposed_identity or '',
            'proposed_fingerprint': self.proposed_fingerprint or '',
            'classification': self.proposed_classification or '',
            'version_id': self.proposed_version_id.id or 0,
            'pricing_date': str(self.proposed_pricing_date or ''),
            'adjusted': _none(self.proposed_adjusted_exact),
            'actual': _none(self.proposed_actual_exact),
            'eligible': _none(self.proposed_quantity_exact),
            'exposure': _none(self.proposed_exposure_exact),
            'currency_id': self.comparison_currency_id.id or 0,
            'delta': _none(self.delta_exact),
            'delta_class': self.delta_class or '',
            'credit_class': self.credit_class_observed or '',
            'authoritative': bool(self.calculation_authoritative),
            'is_recovered_cash': bool(self.is_recovered_cash),
            'is_writeoff': bool(self.is_writeoff),
        }

    def _evidence_gaps(self):
        gaps = []
        finding = self.finding_id
        if not finding or not finding.exists():
            gaps.append('The original finding is missing.')
        elif finding.company_id != self.company_id:
            gaps.append('The finding company does not match the reassessment.')
        if not self.proposal_digest or not self.proposed_fingerprint or not self.proposed_identity:
            gaps.append('The proposed calculation is incomplete.')
        if _none(self.proposed_exposure_exact) is None:
            gaps.append('The proposed amount is missing.')
        if not (self.reason or '').strip():
            gaps.append('The request has no reason.')
        if not self.calculation_authoritative:
            gaps.append('The proposal is not authoritative.')
        if self.trigger_type == 'verified_quantity_return' and self.credit_class_observed != 'QUANTITY_RETURN':
            gaps.append('The credit classification is not a verified quantity return.')
        if self.trigger_type == 'full_invoice_reversal' and self.credit_class_observed != 'FULL_REVERSAL':
            gaps.append('The credit classification is not a verified full reversal.')
        if self.proposed_identity == self.original_identity:
            if not finding.is_current or finding.input_fingerprint != self.original_fingerprint:
                gaps.append('Another revision is already current for this finding.')
        return gaps

    def _virtual_run(self):
        invoice_date = self.finding_id.move_id.invoice_date or fields.Date.context_today(self)
        return self.env['cpla.invoice.audit.run'].new({
            'company_id': self.company_id.id,
            'mode': 'reassessment',
            'state': 'draft',
            'date_basis': 'invoice_date',
            'date_from': invoice_date,
            'date_to': invoice_date,
            'knowledge_cutoff': self.knowledge_cutoff,
            'partner_id': self.finding_id.partner_id.id,
            'product_id': self.finding_id.product_id.id,
            'batch_size': 50,
        })

    def _origin_map(self):
        self.env['cpla.invoice.source'].map_line(self.finding_id.move_line_id)
        return self.env['cpla.invoice.source.map'].search([
            ('company_id', '=', self.company_id.id),
            ('move_line_id', '=', self.finding_id.move_line_id.id),
            ('is_current', '=', True),
        ], limit=1)

    def _allocation(self, mapping):
        if not mapping:
            return self.env['cpla.invoice.source.allocation']
        if self.finding_id.allocation_id:
            match = mapping.allocation_ids.filtered(
                lambda row: row.id == self.finding_id.allocation_id.id
            )[:1]
            if match:
                return match
        return mapping.allocation_ids[:1]

    def _apply(self):
        """Store the proposal through the official engine. This is not action_run."""
        self.ensure_one()
        invoice_date = self.finding_id.move_id.invoice_date or fields.Date.context_today(self)
        run = self.env['cpla.invoice.audit.run'].create({
            'company_id': self.company_id.id,
            'mode': 'reassessment',
            'date_basis': 'invoice_date',
            'date_from': fields.Date.add(invoice_date, days=-30),
            'date_to': fields.Date.add(invoice_date, days=30),
            'partner_id': self.finding_id.partner_id.id,
            'product_id': self.finding_id.product_id.id,
            'knowledge_cutoff': self.knowledge_cutoff or False,
        })
        models.Model.write(run, {
            'state': 'running',
            'started_on': fields.Datetime.now(),
        })
        self._apply_documents(run)
        models.Model.write(run, {
            'state': 'completed',
            'finished_on': fields.Datetime.now(),
            'error_summary': False,
        })
        return run

    def _apply_documents(self, run):
        trigger = self.trigger_type
        if trigger in ('verified_quantity_return', 'full_invoice_reversal', 'price_adjustment_credit'):
            move = self.env['account.move'].browse(self.source_res_id).exists()
            move.check_access('read')
            maps = self._credit_maps(move)
            if not maps:
                raise UserError(self.env._('The credit mapping is no longer current.'))
            for mapping in maps:
                run._audit_mapping(mapping)
            return
        if trigger == 'replacement_invoice':
            credits = self.env['cpla.invoice.source.map'].search([
                ('origin_line_id', '=', self.finding_id.move_line_id.id),
                ('company_id', '=', self.company_id.id),
                ('is_current', '=', True),
                ('quantity_trusted', '=', True),
                ('credit_class', '=', 'FULL_REVERSAL'),
            ])
            if not credits:
                raise UserError(self.env._('The verified reversal is no longer current.'))
            for mapping in credits:
                run._audit_mapping(mapping)
            replacement = self.env['account.move'].browse(self.source_res_id).exists()
            replacement.check_access('read')
            self.env['cpla.invoice.source'].map_move(replacement)
            maps = self.env['cpla.invoice.source.map'].search([
                ('move_id', '=', replacement.id),
                ('company_id', '=', self.company_id.id),
                ('is_current', '=', True),
            ])
            for mapping in maps.filtered('move_line_id'):
                run._audit_mapping(mapping)
            return
        origin = self._origin_map()
        if not origin:
            raise UserError(self.env._('The invoice line mapping is not current.'))
        run._audit_mapping(origin)

    def _stored_successor(self, run):
        finding = self.env['cpla.leakage.finding'].search([
            ('current_identity', '=', self.proposed_identity),
            ('is_current', '=', True),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        result = self.env['cpla.invoice.audit.result'].search([
            ('run_id', '=', run.id),
            ('company_id', '=', self.company_id.id),
            ('move_line_id', '=', self.finding_id.move_line_id.id),
            ('input_fingerprint', '=', self.proposed_fingerprint),
        ], order='id desc', limit=1)
        return finding, result

    def _require_successor(self, successor, result):
        expected = self.proposed_exposure_exact or ''
        if successor:
            actual = successor.potential_leakage_exact or ''
            if actual != expected or successor.input_fingerprint != self.proposed_fingerprint:
                raise UserError(self.env._(
                    'The engine result does not match the accepted proposal.'
                ))
            return
        if _decimal(expected) == ZERO and result and (result.potential_exposure_exact or '') == expected:
            if result.input_fingerprint == self.proposed_fingerprint:
                return
        raise UserError(self.env._('The engine did not store the proposed revision.'))

    def _sync_cases(self):
        memberships = self.env['cpla.leakage.case.membership'].search([
            ('finding_id', '=', self.finding_id.id),
            ('is_current', '=', True),
            ('company_id', '=', self.company_id.id),
        ])
        separate = self.proposed_identity != self.original_identity
        for membership in memberships:
            case = membership.case_id
            if separate:
                case._log(
                    case,
                    'separate_interpretation_recorded',
                    reason=(
                        'A different knowledge cutoff was accepted as its own identity. '
                        'It was not added to this case and the reviewed amount was not changed.'
                    ),
                    source_model=self._name,
                    source_res_id=self.id,
                )
                self._refresh_reinvestigation_flag()
            else:
                case._mark_source_revision()
                models.Model.write(case, {'reinvestigation_required': True})
                self._log(
                    'case_flagged',
                    'The case needs another look at the source. The root cause was not replaced.',
                )
                if case.finance_package_stale:
                    self._log(
                        'finance_package_flagged',
                        'The finance submission is older than this accepted source revision.',
                    )

    def _set_state(self, state, reason):
        event = {
            'blocked': 'blocked',
            'failed': 'failed',
            'cancelled': 'cancelled',
        }.get(state, 'blocked')
        prior = self.state
        models.Model.write(self, {
            'state': state,
            'error_summary': reason,
        })
        self._log(event, reason, prior_state=prior, new_state=state)

    def _refresh_reinvestigation_flag(self):
        """Flag the linked case without changing its conclusion or reviewed amount."""
        case = self.case_id
        if not case or case.company_id != self.company_id:
            return
        pending = self.search_count([
            ('case_id', '=', case.id),
            ('company_id', '=', case.company_id.id),
            ('change_class', 'in', list(MATERIAL_CHANGE)),
            ('state', 'in', list(OPEN_STATES) + ['rejected']),
        ])
        models.Model.write(case, {'reinvestigation_required': bool(pending)})

    @api.model
    def affected_findings(self, company, version=None, partner=None, product=None):
        """Current findings for one company scope. This does not rescan other companies."""
        if not company:
            return self.env['cpla.leakage.finding']
        if not (self.env.su or self.env.user._is_superuser()) and company not in self.env.companies:
            raise AccessError(self.env._('You cannot select findings for this company.'))
        domain = [
            ('company_id', '=', company.id),
            ('is_current', '=', True),
        ]
        if version:
            version.check_access('read')
            if version.company_id != company:
                raise UserError(self.env._(
                    'That contract version is not in this company. No finding was selected.'
                ))
            domain.append(('version_id', '=', version.id))
        if partner:
            domain.append(('partner_id', '=', partner.id))
        if product:
            domain.append(('product_id', '=', product.id))
        return self.env['cpla.leakage.finding'].search(domain)

    def action_open_original_result(self):
        self.ensure_one()
        self.check_access('read')
        result = self.original_result_id
        if not result:
            raise UserError(self.env._('The original audit result is not linked.'))
        result.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Original audit result'),
            'res_model': result._name,
            'res_id': result.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_case(self):
        self.ensure_one()
        self.check_access('read')
        case = self.case_id
        if not case:
            raise UserError(self.env._('This reassessment has no investigation case.'))
        case.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': case.reference,
            'res_model': case._name,
            'res_id': case.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _log(self, event_type, reason='', prior_state=False, new_state=False):
        models.Model.create(self.env['cpla.leakage.reassessment.event'], [{
            'reassessment_id': self.id,
            'company_id': self.company_id.id,
            'finding_id': self.finding_id.id,
            'event_type': event_type,
            'actor_id': self.env.user.id,
            'occurred_at': fields.Datetime.now(),
            'prior_state': prior_state or False,
            'new_state': new_state or self.state,
            'source_revision': self.original_revision or 0,
            'evidence_model': self.source_model,
            'evidence_res_id': self.source_res_id or 0,
            'reason': (reason or '')[:4000] or False,
        }])

    @staticmethod
    def _as_date(value):
        if not value:
            return False
        if isinstance(value, str):
            return fields.Date.to_date(value)
        return value


class LeakageReassessmentEvent(models.Model):
    _name = 'cpla.leakage.reassessment.event'
    _description = 'Leakage Reassessment Event'
    _order = 'id desc'
    _check_company_auto = True

    reassessment_id = fields.Many2one(
        'cpla.leakage.reassessment', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    event_type = fields.Selection(
        selection=[
            ('requested', 'Requested'),
            ('proposal_ready', 'Proposal ready'),
            ('evidence_review', 'Evidence review'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('blocked', 'Blocked'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
            ('current_revision_changed', 'Current revision changed'),
            ('case_flagged', 'Case flagged'),
            ('finance_package_flagged', 'Finance package flagged'),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    finding_id = fields.Many2one('cpla.leakage.finding', readonly=True, index=True, ondelete='restrict')
    actor_id = fields.Many2one('res.users', readonly=True)
    occurred_at = fields.Datetime(readonly=True)
    prior_state = fields.Char(readonly=True)
    new_state = fields.Char(readonly=True)
    source_revision = fields.Integer(readonly=True)
    evidence_model = fields.Char(readonly=True)
    evidence_res_id = fields.Integer(readonly=True)
    reason = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._('Reassessment history is written by the reassessment workflow.'))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        raise UserError(self.env._('Reassessment history cannot be overwritten.'))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.check_access('unlink')
        raise UserError(self.env._('Reassessment history cannot be deleted.'))


class LeakageReassessmentWizard(models.TransientModel):
    _name = 'cpla.leakage.reassessment.wizard'
    _description = 'Leakage Reassessment Request'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True)
    finding_id = fields.Many2one('cpla.leakage.finding', required=True)
    reassessment_id = fields.Many2one('cpla.leakage.reassessment')
    operation = fields.Selection(
        selection=[
            ('request', 'Request'),
            ('accept', 'Accept'),
            ('reject', 'Reject'),
            ('cancel', 'Cancel'),
        ],
        required=True,
        default='request',
    )
    trigger_type = fields.Selection(selection=TRIGGERS, required=True, default='manual_authorized_review')
    reason = fields.Text(required=True)
    source_model = fields.Selection(
        selection=[
            ('account.move', 'Invoice or credit note'),
            ('cpla.customer.contract.version', 'Contract version'),
            ('cpla.leakage.finding', 'Leakage finding'),
        ],
    )
    source_res_id = fields.Integer()
    knowledge_cutoff = fields.Datetime(
        help='Leave this empty to use the finding cutoff. A value is the as-known-at cutoff, not the invoice date.',
    )

    def action_request(self):
        self.ensure_one()
        if self.operation == 'accept':
            self.reassessment_id.action_accept(self.reason)
        elif self.operation == 'reject':
            self.reassessment_id.action_reject(self.reason)
        elif self.operation == 'cancel':
            self.reassessment_id.action_cancel(self.reason)
        else:
            finding = self.finding_id
            finding.check_access('read')
            kwargs = {
                'source_model': self.source_model,
                'source_res_id': self.source_res_id or None,
            }
            if self.knowledge_cutoff:
                kwargs['knowledge_cutoff'] = self.knowledge_cutoff
            record = self.env['cpla.leakage.reassessment'].request_for_finding(
                finding.id, self.trigger_type, self.reason, **kwargs,
            )
            return record.action_open_form()
        return {'type': 'ir.actions.act_window_close'}


class LeakageFindingReassessment(models.Model):
    _inherit = 'cpla.leakage.finding'

    reassessment_ids = fields.One2many('cpla.leakage.reassessment', 'finding_id')
    revision_verification = fields.Selection(
        selection=VERIFICATION_STATES,
        compute='_compute_revision_verification',
        search='_search_revision_verification',
        help=(
            'Last accepted result while a material reassessment is open or rejected. '
            'This is not a finance validation and it is not recovered cash.'
        ),
    )

    @api.depends(
        'is_current',
        'reassessment_ids.state',
        'reassessment_ids.change_class',
        'reassessment_ids.successor_finding_id',
    )
    def _compute_revision_verification(self):
        Reassessment = self.env['cpla.leakage.reassessment']
        for finding in self:
            finding.revision_verification = self._verification_value(finding, Reassessment)

    @api.model
    def _verification_value(self, finding, reassessment_model):
        if not finding.is_current:
            return 'historical_superseded'
        rows = finding.reassessment_ids
        open_rows = rows.filtered(lambda row: row.state in OPEN_STATES)
        if any(row.state == 'proposed_revision_ready' for row in open_rows):
            return 'reassessment_proposed'
        if any(row.state in ('evidence_review_required', 'blocked', 'failed') for row in open_rows):
            return 'current_result_uncertain'
        if open_rows:
            return 'source_changed_review_pending'
        if rows.filtered(lambda row: row.state == 'rejected' and row.change_class in MATERIAL_CHANGE):
            latest_rejection = max(rows.filtered(
                lambda row: row.state == 'rejected' and row.change_class in MATERIAL_CHANGE
            ).mapped('id'))
            later_acceptance = rows.filtered(
                lambda row: row.state == 'accepted' and row.id > latest_rejection
            )
            if not later_acceptance:
                return 'source_changed_review_pending'
        accepted_here = reassessment_model.search_count([
            ('successor_finding_id', '=', finding.id),
            ('state', '=', 'accepted'),
            ('company_id', '=', finding.company_id.id),
        ])
        if accepted_here:
            return 'reassessment_accepted'
        return 'current_verified'

    def _search_revision_verification(self, operator, value):
        if operator not in ('=', '!='):
            return [('id', '=', 0)]
        findings = self.env['cpla.leakage.finding'].search([
            ('company_id', 'in', self.env.companies.ids),
        ])
        matched = findings.filtered(lambda finding: finding.revision_verification == value)
        if operator == '=':
            return [('id', 'in', matched.ids)]
        return [('id', 'not in', matched.ids)]

    def action_open_reassessment_wizard(self):
        self.ensure_one()
        self.check_access('read')
        user = self.env.user
        if not (self.env.su or user._is_superuser() or user.has_group(MANAGER_GROUP)):
            raise AccessError(self.env._('Only a contract manager can request a reassessment.'))
        if not self.is_current:
            raise UserError(self.env._('Reassessment starts from the current finding.'))
        wizard = self.env['cpla.leakage.reassessment.wizard'].create({
            'company_id': self.company_id.id,
            'finding_id': self.id,
            'trigger_type': 'manual_authorized_review',
            'reason': 'Document the evidence that should be reread.',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Request reassessment'),
            'res_model': 'cpla.leakage.reassessment.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
