import json

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    AUDITOR_GROUP,
    FINANCE_MANAGER_GROUP,
    MANAGER_GROUP,
    REVIEWER_GROUP,
    USER_GROUP,
    _arithmetic,
    _decimal,
    _text,
)
from odoo.addons.contract_price_leakage_auditor.models.invoice_audit import (
    LEAKAGE_CLASSES,
    REVIEW_CLASSES,
)

MODULE = 'contract_price_leakage_auditor'
CASE_SEQUENCE = 'cpla.leakage.case'
ZERO = _decimal('0')

INVESTIGATOR_GROUPS = (USER_GROUP, MANAGER_GROUP)
FINANCE_GROUPS = (REVIEWER_GROUP, FINANCE_MANAGER_GROUP)
CHATTER_GROUPS = (USER_GROUP, MANAGER_GROUP, REVIEWER_GROUP, FINANCE_MANAGER_GROUP)
READ_GROUPS = CHATTER_GROUPS + (AUDITOR_GROUP,)
CASE_ATTACHMENT_MODELS = frozenset({
    'cpla.leakage.case',
    'cpla.leakage.case.evidence',
    'cpla.leakage.reassessment',
    'cpla.recovery.request',
    'cpla.recovery.waiver',
    'cpla.recovery.dispute',
    'cpla.recovery.settlement',
    'cpla.recovery.event',
    'cpla.recovery.billing',
    'cpla.recovery.collection.evidence',
    'cpla.recovery.accounting.adjustment',
})
OPEN_STATES = frozenset({
    'new',
    'assigned',
    'under_investigation',
    'evidence_pending',
    'returned_for_rework',
})
GROUPING_BASES = frozenset({
    'same_sales_order',
    'same_contract_version',
    'same_invoice',
    'explicit_same_issue',
})
MANAGER_WRITABLE = frozenset({
    'title',
    'investigation_summary',
    'target_review_date',
    'outstanding_qualification',
    'escalation_policy_reference',
})

CASE_TYPES = [
    ('potential_leakage', 'Potential leakage'),
    ('contract_coverage_exception', 'Contract coverage exception'),
    ('pricing_evidence_exception', 'Pricing evidence exception'),
    ('conflict_review', 'Conflict review'),
    ('refund_reassessment_exception', 'Refund reassessment exception'),
    ('other_control_exception', 'Other control exception'),
]
CASE_STATES = [
    ('new', 'New'),
    ('assigned', 'Assigned'),
    ('under_investigation', 'Under investigation'),
    ('evidence_pending', 'Evidence pending'),
    ('ready_for_finance_review', 'Ready for finance review'),
    ('returned_for_rework', 'Returned for rework'),
    ('closed_with_reason', 'Closed with reason'),
]
PRIORITIES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]
ROOT_CAUSES = [
    ('missed_contract_price_increase', 'Missed contract price increase'),
    ('unauthorized_manual_discount', 'Unauthorized manual discount'),
    ('incorrect_sales_order_price', 'Incorrect sales order price'),
    ('invoice_price_changed_after_order', 'Invoice price changed after order'),
    ('wrong_contract_version', 'Wrong contract version'),
    ('wrong_pricing_date', 'Wrong pricing date'),
    ('invalid_grandfathering', 'Invalid grandfathering'),
    ('wrong_quantity_tier', 'Wrong quantity tier'),
    ('uom_or_packaging_error', 'UoM or packaging error'),
    ('fx_rate_policy_error', 'FX rate policy error'),
    ('tax_basis_error', 'Tax basis error'),
    ('approval_evidence_missing', 'Approval evidence missing'),
    ('contract_coverage_gap', 'Contract coverage gap'),
    ('credit_or_reversal_mapping_error', 'Credit or reversal mapping error'),
    ('master_data_error', 'Master data error'),
    ('other', 'Other'),
    ('undetermined', 'Undetermined'),
]
OUTCOMES = [
    ('likely_unauthorized_underpricing', 'Likely unauthorized underpricing'),
    ('likely_missed_price_increase', 'Likely missed price increase'),
    ('possible_authorized_concession', 'Possible authorized concession'),
    ('contract_interpretation_dispute', 'Contract interpretation dispute'),
    ('duplicate_finding', 'Duplicate finding'),
    ('source_mapping_error', 'Source mapping error'),
    ('needs_additional_evidence', 'Needs additional evidence'),
    ('not_applicable_to_contract_audit', 'Not applicable to contract audit'),
    ('ready_for_finance_review', 'Ready for finance review'),
    ('undetermined', 'Undetermined'),
]
CLOSURE_REASONS = [
    ('duplicate_case', 'Duplicate case'),
    ('source_error', 'Source error'),
    ('not_in_scope', 'Not in scope'),
    ('superseded_by_case', 'Superseded by case'),
    ('withdrawn_after_review', 'Withdrawn after review'),
    ('no_action_required_after_authorized_review', 'No action required after authorized review'),
]
EVIDENCE_STATUSES = [
    ('not_requested', 'Not requested'),
    ('requested', 'Requested'),
    ('received', 'Received'),
    ('verified', 'Verified'),
    ('rejected', 'Rejected'),
    ('not_applicable', 'Not applicable'),
]
QUEUES = [
    ('contract_review', 'Contract review'),
    ('pricing_date_review', 'Pricing date review'),
    ('discount_approval_review', 'Discount approval review'),
    ('financial_normalization_review', 'Financial normalization review'),
    ('source_mapping_review', 'Source mapping review'),
    ('credit_refund_review', 'Credit or refund review'),
    ('security_or_company_exception', 'Security or company exception'),
    ('other_evidence_review', 'Other evidence review'),
]
EVENT_TYPES = [
    ('created', 'Case created'),
    ('finding_linked', 'Finding linked'),
    ('finding_removed', 'Finding removed'),
    ('assigned', 'Case assigned'),
    ('owner_changed', 'Owner changed'),
    ('priority_changed', 'Priority changed'),
    ('severity_changed', 'Severity changed'),
    ('evidence_requested', 'Evidence requested'),
    ('evidence_verified', 'Evidence verified'),
    ('evidence_rejected', 'Evidence rejected'),
    ('state_changed', 'State changed'),
    ('root_cause_recorded', 'Root cause recorded'),
    ('outcome_recorded', 'Outcome recorded'),
    ('source_revision_detected', 'Source revision detected'),
    ('source_revision_accepted', 'Source revision accepted'),
    ('separate_interpretation_recorded', 'Separate cutoff interpretation recorded'),
    ('submitted_to_finance', 'Submitted to finance'),
    ('returned_for_rework', 'Returned for rework'),
    ('closed', 'Closed'),
    ('reopened', 'Reopened'),
    ('merged', 'Merged'),
    ('split', 'Split'),
    ('participant_added', 'Participant added'),
    ('finance_decision_recorded', 'Finance decision recorded'),
]
TYPE_BY_CATEGORY = {
    'UNAUTHORIZED_UNDERPRICING': 'potential_leakage',
    'MISSED_CONTRACT_PRICE_INCREASE': 'potential_leakage',
    'UNAUTHORIZED_DISCOUNT_INDICATOR': 'potential_leakage',
    'CONTRACT_COVERAGE_EXCEPTION': 'contract_coverage_exception',
    'CONTRACT_CONFLICT_REVIEW_REQUIRED': 'conflict_review',
    'MISSING_PRICING_EVIDENCE': 'pricing_evidence_exception',
    'FX_OR_TAX_REVIEW_REQUIRED': 'pricing_evidence_exception',
    'SOURCE_ALLOCATION_REVIEW_REQUIRED': 'pricing_evidence_exception',
    'REFUND_REASSESSMENT_REQUIRED': 'refund_reassessment_exception',
    'UNSUPPORTED_TRANSACTION': 'other_control_exception',
    'TECHNICAL_AUDIT_FAILURE': 'other_control_exception',
}
QUEUE_BY_CATEGORY = {
    'CONTRACT_COVERAGE_EXCEPTION': 'contract_review',
    'CONTRACT_CONFLICT_REVIEW_REQUIRED': 'contract_review',
    'MISSING_PRICING_EVIDENCE': 'pricing_date_review',
    'FX_OR_TAX_REVIEW_REQUIRED': 'financial_normalization_review',
    'SOURCE_ALLOCATION_REVIEW_REQUIRED': 'source_mapping_review',
    'REFUND_REASSESSMENT_REQUIRED': 'credit_refund_review',
    'UNSUPPORTED_TRANSACTION': 'other_evidence_review',
    'TECHNICAL_AUDIT_FAILURE': 'other_evidence_review',
}
CHECKLIST = (
    ('invoice_posted_eligible', 'Is the invoice posted and eligible?', 'potential'),
    ('customer_identity', 'Is the customer identity correct?', 'potential'),
    ('product_variant', 'Is the product variant correct?', 'optional'),
    ('source_sales_order', 'Is the source sales order verified?', 'optional'),
    ('contract_version_selected', 'Is the correct contract version selected?', 'optional'),
    ('pricing_date', 'Is the contractual pricing date correct?', 'optional'),
    ('grandfathering', 'Was grandfathering valid?', 'optional'),
    ('quantity_tier', 'Is the quantity-tier basis correct?', 'optional'),
    ('uom_packaging', 'Is UoM or packaging conversion supported?', 'optional'),
    ('fx_rate', 'Is the historical FX rate valid?', 'optional'),
    ('tax_basis', 'Is the tax basis comparable?', 'optional'),
    ('authorized_concessions', 'Are authorized concessions included?', 'optional'),
    ('override_approval', 'Does an override approval cover the transaction?', 'optional'),
    ('credit_notes', 'Were credit notes or returns considered?', 'optional'),
    ('duplicate_economic_issue_checked', 'Is the finding a duplicate economic issue?', 'potential'),
    ('later_amendment', 'Did a later amendment change the historical reading?', 'optional'),
    ('calculation_evidence_complete', 'Is the calculation evidence complete?', 'potential'),
    ('exposure_reconciled', 'Does the case exposure match the current findings?', 'potential'),
    ('root_cause_explained', 'Is the root cause explained?', 'both'),
    ('uncertainties_recorded', 'Are remaining uncertainties recorded?', 'optional'),
    ('ready_for_finance_review', 'Is the case ready for finance review?', 'potential'),
    ('exception_reason_visible', 'Is the exception reason visible?', 'exception'),
    ('amount_not_fabricated', 'Was a leakage amount left blank instead of invented?', 'exception'),
    ('missing_evidence_disclosed', 'Is missing evidence disclosed?', 'exception'),
)


def _blank(value):
    return value is False or value is None or value == ''


class LeakageCase(models.Model):
    """Investigation container for current DEV-12 findings.

    The case copies no second leakage calculation. Exposure is the sum of
    the linked current finding amounts when those amounts are comparable.
    A blank amount stays blank. Submission is not finance validation, and
    closure is not recovered cash.
    """

    _name = 'cpla.leakage.case'
    _description = 'Leakage Investigation Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _check_company_auto = True
    _mail_thread_customer = False

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This case reference already exists.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    title = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True, readonly=True)
    case_type = fields.Selection(selection=CASE_TYPES, required=True, readonly=True, index=True)
    state = fields.Selection(
        selection=CASE_STATES, required=True, default='new', readonly=True, index=True, copy=False,
        tracking=True,
    )
    primary_category = fields.Char(readonly=True, index=True)
    exception_queue = fields.Selection(selection=QUEUES, readonly=True, index=True)
    owner_id = fields.Many2one('res.users', readonly=True, index=True, copy=False)
    participant_ids = fields.Many2many(
        'res.users',
        'cpla_leakage_case_participant_rel',
        'case_id',
        'user_id',
        string='Participants',
        readonly=True,
    )
    priority = fields.Selection(selection=PRIORITIES, readonly=True, index=True, copy=False)
    priority_reason = fields.Char(readonly=True, copy=False)
    severity = fields.Selection(selection=PRIORITIES, readonly=True, copy=False)
    severity_reason = fields.Char(readonly=True, copy=False)
    grouping_basis = fields.Char(readonly=True, copy=False)
    first_detected_at = fields.Datetime(readonly=True)
    opened_at = fields.Datetime(required=True, readonly=True, copy=False)
    assigned_at = fields.Datetime(readonly=True, copy=False)
    target_review_date = fields.Date(
        copy=False,
        help='Set only when an authorized user enters a date. No SLA default is applied.',
    )
    last_activity_at = fields.Datetime(readonly=True, copy=False)
    evidence_requested_at = fields.Datetime(readonly=True, copy=False)
    finance_submitted_at = fields.Datetime(readonly=True, copy=False)
    age_calendar_days = fields.Integer(
        compute='_compute_age',
        help='Calendar days from opened_at. This is not a business-day SLA.',
    )
    is_overdue = fields.Boolean(
        compute='_compute_overdue',
        search='_search_overdue',
        help='True only when a user-entered target review date is before today.',
    )
    escalation_policy_reference = fields.Char(
        help='Optional label for a later SLA phase. DEV-13 does not escalate from it.',
    )
    membership_ids = fields.One2many('cpla.leakage.case.membership', 'case_id')
    current_potential_exposure_exact = fields.Char(
        readonly=True,
        copy=False,
        help='Sum of unique current finding amounts when the currency is comparable. Blank means unknown, not zero.',
    )
    reviewed_exposure_exact = fields.Char(
        readonly=True,
        copy=False,
        help='Exposure accepted for this investigation. A later source change does not replace it by itself.',
    )
    exposure_currency_id = fields.Many2one('res.currency', readonly=True)
    exposure_comparable = fields.Boolean(readonly=True, default=False)
    exposure_unknown_count = fields.Integer(readonly=True, default=0)
    source_reassessment_required = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    finance_package_stale = fields.Boolean(
        readonly=True,
        default=False,
        copy=False,
        help='The finance submission snapshot is older than a later source revision. The submission row is kept. This is not a finance rejection.',
    )
    reinvestigation_required = fields.Boolean(
        readonly=True,
        default=False,
        copy=False,
        index=True,
        help='A material reassessment is open or was rejected. The root cause and the reviewed amount stay as the investigator left them. This is not a finance rejection.',
    )
    root_cause = fields.Selection(selection=ROOT_CAUSES, readonly=True, copy=False)
    root_cause_explanation = fields.Text(readonly=True, copy=False)
    investigation_outcome = fields.Selection(selection=OUTCOMES, readonly=True, copy=False)
    investigation_summary = fields.Text()
    outstanding_qualification = fields.Text(
        help='Disclose a required answer of No, or missing evidence, before finance submission.',
    )
    evidence_status = fields.Selection(
        selection=EVIDENCE_STATUSES, readonly=True, default='not_requested', copy=False,
    )
    submitted_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    return_reason = fields.Text(readonly=True, copy=False)
    return_required_action = fields.Text(readonly=True, copy=False)
    returned_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    returned_at = fields.Datetime(readonly=True, copy=False)
    closed_at = fields.Datetime(readonly=True, copy=False)
    closed_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    closure_reason = fields.Selection(selection=CLOSURE_REASONS, readonly=True, copy=False)
    closure_note = fields.Text(readonly=True, copy=False)
    reopened_at = fields.Datetime(readonly=True, copy=False)
    superseded_by_case_id = fields.Many2one('cpla.leakage.case', readonly=True, copy=False, index=True)
    case_revision = fields.Integer(readonly=True, default=1, copy=False)
    checklist_ids = fields.One2many('cpla.leakage.case.checklist', 'case_id')
    evidence_ids = fields.One2many('cpla.leakage.case.evidence', 'case_id')
    submission_ids = fields.One2many('cpla.leakage.case.submission', 'case_id')
    event_ids = fields.One2many('cpla.leakage.case.event', 'case_id')
    finding_count = fields.Integer(compute='_compute_counts')
    result_count = fields.Integer(compute='_compute_counts')
    invoice_count = fields.Integer(compute='_compute_counts')
    version_count = fields.Integer(compute='_compute_counts')
    order_count = fields.Integer(compute='_compute_counts')

    @api.depends('opened_at', 'closed_at')
    def _compute_age(self):
        now = fields.Datetime.now()
        for case in self:
            if not case.opened_at:
                case.age_calendar_days = 0
                continue
            end = case.closed_at or now
            case.age_calendar_days = (end - case.opened_at).days

    @api.depends('target_review_date', 'state')
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for case in self:
            case.is_overdue = bool(
                case.target_review_date
                and case.state != 'closed_with_reason'
                and case.target_review_date < today
            )

    def _search_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        overdue = [
            ('target_review_date', '!=', False),
            ('target_review_date', '<', today),
            ('state', '!=', 'closed_with_reason'),
        ]
        wants = (operator == '=' and bool(value)) or (operator == '!=' and not value)
        if wants:
            return overdue
        return [
            '|', '|',
            ('target_review_date', '=', False),
            ('target_review_date', '>=', today),
            ('state', '=', 'closed_with_reason'),
        ]

    @api.depends('membership_ids.is_current', 'membership_ids.finding_id')
    def _compute_counts(self):
        result_model = self.env['cpla.invoice.audit.result']
        for case in self:
            findings = case.membership_ids.filtered('is_current').finding_id
            case.finding_count = len(findings)
            case.invoice_count = len(findings.mapped('move_id'))
            case.version_count = len(findings.mapped('version_id'))
            orders = self.env['sale.order']
            for finding in findings:
                order = self._sale_order(finding)
                if order:
                    orders |= order
            case.order_count = len(orders)
            case.result_count = result_model.search_count([
                ('finding_id', 'in', findings.ids),
                ('company_id', '=', case.company_id.id),
            ]) if findings else 0

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._(
            'Open an investigation from a current finding. A case is not created from a free-form amount.'
        ))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        if not vals:
            return True
        user = self.env.user
        if not (self.env.su or user._is_superuser() or user.has_group(MANAGER_GROUP)):
            raise UserError(self.env._(
                'Finance review does not edit the investigation record. Use Return for rework.'
            ))
        blocked = set(vals) - MANAGER_WRITABLE
        if blocked:
            raise UserError(self.env._(
                'Those case fields are changed only by an investigation action.'
            ))
        if any(case.state in ('ready_for_finance_review', 'closed_with_reason') for case in self):
            raise UserError(self.env._(
                'Notes stay as they were once the case is with finance review or closed.'
            ))
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._('An investigation case cannot be deleted.'))

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        return []

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        partner_ids = list(partner_ids or [])
        for case in self:
            case.check_access('read')
            for partner_id in partner_ids:
                if not case._partner_may_follow(partner_id):
                    raise AccessError(self.env._(
                        'That contact cannot follow a leakage investigation.'
                    ))
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

    def message_post(self, **kwargs):
        for case in self:
            case._require_chatter_actor()
            case.check_access('read')
        raw = list(kwargs.get('partner_ids') or [])
        if raw and not all(isinstance(partner_id, int) for partner_id in raw):
            raise UserError(self.env._('Recipients must be partner ids.'))
        allowed = []
        for partner_id in raw:
            if all(case._partner_may_follow(partner_id) for case in self):
                allowed.append(partner_id)
        kwargs['partner_ids'] = allowed
        kwargs.setdefault('subtype_xmlid', 'mail.mt_note')
        return super().message_post(**kwargs)

    @api.model
    def create_from_findings(self, finding_ids, grouping_basis=None, grouping_note=None):
        """Open or reuse one investigation for the given current findings.

        One finding is the default. Several findings stay separate unless
        ``grouping_basis`` is one of the explicit bases. The same call is
        safe to repeat.
        """
        findings = self.env['cpla.leakage.finding'].browse(finding_ids).exists()
        if not findings or len(findings) != len(set(finding_ids)):
            raise UserError(self.env._('Choose current findings before opening a case.'))
        self._check_manager()
        for finding in findings:
            finding.check_access('read')
            self._check_eligible(finding)
        if len(findings) > 1:
            if not grouping_basis:
                raise UserError(self.env._(
                    'Matching customer is not a grouping rule. Choose an explicit basis or open one case per finding.'
                ))
            self._assert_groupable(findings, grouping_basis)
        memberships = self.env['cpla.leakage.case.membership'].search([
            ('finding_id', 'in', findings.ids),
            ('is_current', '=', True),
        ])
        if len(findings) == 1 and memberships:
            return memberships.case_id
        if memberships:
            same_case = len(memberships.case_id) == 1
            same_findings = set(memberships.finding_id.ids) == set(findings.ids)
            if same_case and same_findings and len(memberships) == len(findings):
                return memberships.case_id
            raise UserError(self.env._(
                'A selected finding already has a current investigation case.'
            ))
        try:
            with self.env.cr.savepoint():
                case = self._create_case(findings, grouping_basis, grouping_note)
                for finding in findings:
                    self._link(case, finding, event=False)
                self._seed_checklist(case)
                self._seed_evidence(case, findings)
                self._sync_exposure(case, update_reviewed=True)
                self._log(case, 'created', reason=grouping_note or grouping_basis or '', bump=False)
                for finding in findings:
                    self._log(
                        case, 'finding_linked',
                        source_model='cpla.leakage.finding', source_res_id=finding.id,
                    )
        except IntegrityError:
            if len(findings) == 1:
                membership = self._canonical_membership(findings)
                if membership:
                    return membership.case_id
            raise UserError(self.env._(
                'Those findings could not be linked without duplicating a current investigation.'
            ))
        return case

    def action_assign(self, user_id, reason):
        user = self.env['res.users'].browse(user_id).exists()
        if not user or not reason or not str(reason).strip():
            raise UserError(self.env._('Assignment needs an investigator and a reason.'))
        for case in self:
            case._check_manager()
            case._check_open_for_edit()
            if not case._eligible_investigator(user):
                raise AccessError(self.env._(
                    'That user cannot own this company investigation.'
                ))
            previous = case.owner_id
            values = {
                'owner_id': user.id,
                'assigned_at': case.assigned_at or fields.Datetime.now(),
            }
            event = 'assigned' if case.state == 'new' else 'owner_changed'
            if case.state == 'new':
                values['state'] = 'assigned'
            models.Model.write(case, values)
            if user.partner_id and case._partner_may_follow(user.partner_id.id):
                case.message_subscribe(partner_ids=[user.partner_id.id])
            case._log(
                case, event, reason=str(reason).strip(),
                previous=previous.display_name or '',
                new=user.display_name,
            )
            if case.state == 'assigned' and event == 'assigned':
                case._log(case, 'state_changed', previous='new', new='assigned', bump=False)
        return True

    def action_start(self):
        for case in self:
            case._check_investigator_actor()
            if case.state not in ('assigned', 'returned_for_rework'):
                raise UserError(self.env._('Investigation can start from Assigned or Returned for rework.'))
            previous = case.state
            models.Model.write(case, {'state': 'under_investigation'})
            case._log(case, 'state_changed', previous=previous, new='under_investigation')
        return True

    def action_mark_evidence_pending(self, reason):
        if not reason or not str(reason).strip():
            raise UserError(self.env._('Say which evidence is missing.'))
        for case in self:
            case._check_investigator_actor()
            if case.state != 'under_investigation':
                raise UserError(self.env._('Evidence pending starts during investigation.'))
            models.Model.write(case, {
                'state': 'evidence_pending',
                'evidence_requested_at': fields.Datetime.now(),
            })
            case._log(case, 'state_changed', reason=str(reason).strip(), previous='under_investigation', new='evidence_pending')
        return True

    def action_resume_investigation(self):
        for case in self:
            case._check_investigator_actor()
            if case.state != 'evidence_pending':
                raise UserError(self.env._('Only an evidence-pending case returns to investigation this way.'))
            models.Model.write(case, {'state': 'under_investigation'})
            case._log(case, 'state_changed', previous='evidence_pending', new='under_investigation')
        return True

    def action_set_priority(self, priority, reason):
        if priority not in dict(PRIORITIES) or not reason or not str(reason).strip():
            raise UserError(self.env._('Priority needs an approved label and a reason. No amount sets it.'))
        for case in self:
            case._check_manager()
            case._check_open_for_edit()
            previous = case.priority or ''
            models.Model.write(case, {'priority': priority, 'priority_reason': str(reason).strip()})
            case._log(case, 'priority_changed', reason=str(reason).strip(), previous=previous, new=priority)
        return True

    def action_set_severity(self, severity, reason):
        if severity not in dict(PRIORITIES) or not reason or not str(reason).strip():
            raise UserError(self.env._('Severity needs an approved label and a reason. No amount sets it.'))
        for case in self:
            case._check_manager()
            case._check_open_for_edit()
            previous = case.severity or ''
            models.Model.write(case, {'severity': severity, 'severity_reason': str(reason).strip()})
            case._log(case, 'severity_changed', reason=str(reason).strip(), previous=previous, new=severity)
        return True

    def action_record_root_cause(self, root_cause, explanation):
        if root_cause not in dict(ROOT_CAUSES) or not explanation or not str(explanation).strip():
            raise UserError(self.env._('A root cause needs a category and an explanation.'))
        for case in self:
            case._check_investigator_actor()
            case._check_open_for_edit()
            models.Model.write(case, {
                'root_cause': root_cause,
                'root_cause_explanation': str(explanation).strip(),
            })
            case._log(case, 'root_cause_recorded', reason=str(explanation).strip(), new=root_cause)
        return True

    def action_record_outcome(self, outcome, explanation):
        if outcome not in dict(OUTCOMES) or not explanation or not str(explanation).strip():
            raise UserError(self.env._('An investigation outcome needs a category and an explanation.'))
        for case in self:
            case._check_investigator_actor()
            case._check_open_for_edit()
            models.Model.write(case, {'investigation_outcome': outcome})
            if not case.investigation_summary:
                models.Model.write(case, {'investigation_summary': str(explanation).strip()})
            case._log(case, 'outcome_recorded', reason=str(explanation).strip(), new=outcome)
        return True

    def action_add_participant(self, user_id, reason):
        user = self.env['res.users'].browse(user_id).exists()
        if not user or not reason or not str(reason).strip():
            raise UserError(self.env._('A participant needs a user and a reason.'))
        for case in self:
            case._check_manager()
            case._check_open_for_edit()
            if not case._partner_may_follow(user.partner_id.id):
                raise AccessError(self.env._(
                    'That user cannot be added to this company investigation.'
                ))
            models.Model.write(case, {'participant_ids': [(4, user.id)]})
            case.message_subscribe(partner_ids=[user.partner_id.id])
            case._log(case, 'participant_added', reason=str(reason).strip(), new=user.display_name)
        return True

    def action_answer_checklist(self, code, answer, note=None):
        if answer not in ('yes', 'no', 'not_applicable'):
            raise UserError(self.env._('Answer yes, no, or not applicable.'))
        for case in self:
            case._check_investigator_actor()
            case._check_open_for_edit()
            line = case.checklist_ids.filtered(lambda item: item.code == code)[:1]
            if not line:
                raise UserError(self.env._('That checklist question is not on this case.'))
            if answer == 'not_applicable' and not note:
                raise UserError(self.env._('Not applicable needs a note.'))
            models.Model.write(line, {
                'answer': answer,
                'note': note or False,
                'answered_by_id': self.env.user.id,
                'answered_at': fields.Datetime.now(),
            })
        return True

    def action_request_evidence(self, evidence_id, note):
        if not note or not str(note).strip():
            raise UserError(self.env._('Say what evidence is requested.'))
        evidence = self._own_evidence(evidence_id)
        self._check_investigator_actor()
        self._check_open_for_edit()
        models.Model.write(evidence, {
            'status': 'requested',
            'status_note': str(note).strip(),
            'requested_by_id': self.env.user.id,
            'requested_at': fields.Datetime.now(),
        })
        if not self.evidence_requested_at:
            models.Model.write(self, {'evidence_requested_at': fields.Datetime.now()})
        self._refresh_evidence_status()
        self._log(self, 'evidence_requested', reason=str(note).strip(), source_model=evidence._name, source_res_id=evidence.id)
        return True

    def action_verify_evidence(self, evidence_id, note=None):
        evidence = self._own_evidence(evidence_id)
        self._check_investigator_actor()
        self._check_open_for_edit()
        models.Model.write(evidence, {
            'status': 'verified',
            'status_note': note or evidence.status_note,
            'reviewed_by_id': self.env.user.id,
            'reviewed_at': fields.Datetime.now(),
        })
        self._refresh_evidence_status()
        self._log(self, 'evidence_verified', reason=note or '', source_model=evidence._name, source_res_id=evidence.id)
        return True

    def action_reject_evidence(self, evidence_id, reason):
        if not reason or not str(reason).strip():
            raise UserError(self.env._('Rejected evidence needs a reason.'))
        evidence = self._own_evidence(evidence_id)
        self._check_investigator_actor()
        self._check_open_for_edit()
        models.Model.write(evidence, {
            'status': 'rejected',
            'status_note': str(reason).strip(),
            'reviewed_by_id': self.env.user.id,
            'reviewed_at': fields.Datetime.now(),
        })
        self._refresh_evidence_status()
        self._log(self, 'evidence_rejected', reason=str(reason).strip(), source_model=evidence._name, source_res_id=evidence.id)
        return True

    def action_mark_evidence_not_applicable(self, evidence_id, reason):
        if not reason or not str(reason).strip():
            raise UserError(self.env._('Not applicable evidence needs a reason.'))
        evidence = self._own_evidence(evidence_id)
        self._check_investigator_actor()
        self._check_open_for_edit()
        models.Model.write(evidence, {
            'status': 'not_applicable',
            'status_note': str(reason).strip(),
            'reviewed_by_id': self.env.user.id,
            'reviewed_at': fields.Datetime.now(),
        })
        self._refresh_evidence_status()
        return True

    def action_refresh_source_status(self):
        for case in self:
            case._check_case_reader()
            case._mark_source_revision()
        return True

    def action_accept_current_source(self, reason):
        if not reason or not str(reason).strip():
            raise UserError(self.env._('Accepting a new source revision needs a reason.'))
        for case in self:
            case._check_investigator_actor()
            if case.state not in OPEN_STATES:
                raise UserError(self.env._('A finance-submitted or closed case is not retargeted here.'))
            previous = case.reviewed_exposure_exact or ''
            changed = False
            for membership in case.membership_ids.filtered('is_current'):
                successor = case._successor(membership)
                if not successor:
                    continue
                models.Model.write(membership, {'is_current': False, 'removed_at': fields.Datetime.now()})
                membership.flush_recordset(['is_current'])
                case._link(case, successor, event=False)
                case._log(
                    case, 'finding_removed',
                    source_model='cpla.leakage.finding', source_res_id=membership.finding_id.id,
                    previous=membership.reviewed_exposure_exact or '',
                )
                changed = True
            if not changed:
                raise UserError(self.env._('No current successor finding is available to accept.'))
            case._sync_exposure(case, update_reviewed=True)
            models.Model.write(case, {'reinvestigation_required': False})
            case._log(
                case, 'source_revision_accepted', reason=str(reason).strip(),
                previous=previous, new=case.current_potential_exposure_exact or '',
            )
        return True

    def action_open_finance_validations(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Finance validation'),
            'res_model': 'cpla.finance.validation',
            'view_mode': 'list,form',
            'domain': [('case_id', '=', self.id), ('company_id', '=', self.company_id.id)],
            'target': 'current',
        }

    def action_submit_for_finance(self):
        for case in self:
            case._check_investigator_actor()
            if case.state != 'under_investigation':
                raise UserError(self.env._(
                    'Submit for finance review from Under investigation, after the checklist is complete.'
                ))
            case.action_refresh_source_status()
            if case.source_reassessment_required:
                raise UserError(self.env._(
                    'The source finding changed. Review that revision before finance submission.'
                ))
            if not case.root_cause or not case.root_cause_explanation:
                raise UserError(self.env._('Record a root cause and an explanation before submission.'))
            if not case.investigation_outcome:
                raise UserError(self.env._('Record an investigation outcome before submission.'))
            missing = case.checklist_ids.filtered(
                lambda line: line.required_for_submission and line.answer == 'unanswered'
            )
            if missing:
                raise UserError(self.env._(
                    'Required checklist questions are still unanswered.'
                ))
            denied = case.checklist_ids.filtered(
                lambda line: line.required_for_submission and line.answer == 'no'
            )
            if denied and not (case.outstanding_qualification or '').strip():
                raise UserError(self.env._(
                    'A required No answer must be disclosed in the outstanding qualification.'
                ))
            if case.case_type == 'potential_leakage':
                if not case.exposure_comparable or case.exposure_unknown_count:
                    raise UserError(self.env._(
                        'Potential exposure is not comparable. It was not submitted as a certified amount.'
                    ))
                if _blank(case.current_potential_exposure_exact):
                    raise UserError(self.env._(
                        'This leakage case has no current finding amount to show finance.'
                    ))
                pending = case.evidence_ids.filtered(
                    lambda item: item.evidence_kind == 'source' and item.status not in ('verified', 'not_applicable')
                )
                if pending:
                    raise UserError(self.env._(
                        'Verify the source evidence, or mark a line not applicable with a reason.'
                    ))
            else:
                if not _blank(case.current_potential_exposure_exact):
                    raise UserError(self.env._(
                        'An exception case cannot be submitted with a fabricated leakage amount.'
                    ))
                if not (case.outstanding_qualification or '').strip():
                    raise UserError(self.env._(
                        'Disclose the missing evidence before submitting an exception case.'
                    ))
            snapshot = case._submission_snapshot()
            submission = models.Model.create(self.env['cpla.leakage.case.submission'], [snapshot])
            models.Model.write(case, {
                'state': 'ready_for_finance_review',
                'finance_submitted_at': submission.submitted_at,
                'submitted_by_id': self.env.user.id,
                'finance_package_stale': False,
            })
            case._log(
                case, 'submitted_to_finance',
                new=case.current_potential_exposure_exact or '',
                source_model=submission._name, source_res_id=submission.id,
            )
            case._log(case, 'state_changed', previous='under_investigation', new='ready_for_finance_review', bump=False)
            case.message_post(body=str(self.env._(
                'Submitted for finance review. This is not a finance-validated amount.'
            )))
        return True

    def action_return_for_rework(self, reason, required_action):
        if not reason or not str(reason).strip() or not required_action or not str(required_action).strip():
            raise UserError(self.env._('A finance return needs a reason and the required action.'))
        for case in self:
            case._check_finance_actor()
            if case.state != 'ready_for_finance_review':
                raise UserError(self.env._('Only a case waiting for finance review can be returned.'))
            submission = case.submission_ids.sorted('id')[-1:]
            if not submission:
                raise UserError(self.env._('There is no submission snapshot to return.'))
            if submission.submitted_by_id == self.env.user:
                raise AccessError(self.env._(
                    'The person who submitted this case cannot return it.'
                ))
            now = fields.Datetime.now()
            models.Model.write(submission, {
                'returned_by_id': self.env.user.id,
                'returned_at': now,
                'return_reason': str(reason).strip(),
                'required_action': str(required_action).strip(),
            })
            models.Model.write(case, {
                'state': 'returned_for_rework',
                'returned_by_id': self.env.user.id,
                'returned_at': now,
                'return_reason': str(reason).strip(),
                'return_required_action': str(required_action).strip(),
            })
            case._log(
                case, 'returned_for_rework', reason=str(reason).strip(),
                new=str(required_action).strip(),
                source_model=submission._name, source_res_id=submission.id,
            )
            case._log(case, 'state_changed', previous='ready_for_finance_review', new='returned_for_rework', bump=False)
        return True

    def action_close(self, closure_reason, note):
        if closure_reason not in dict(CLOSURE_REASONS) or not note or not str(note).strip():
            raise UserError(self.env._('Closure needs an approved reason and a note.'))
        if closure_reason == 'superseded_by_case':
            raise UserError(self.env._('Superseded closure is recorded by merge.'))
        for case in self:
            case._check_manager()
            if case.state == 'ready_for_finance_review':
                raise UserError(self.env._(
                    'A case waiting for finance review cannot be closed from the investigation side.'
                ))
            if case.state == 'closed_with_reason':
                raise UserError(self.env._('This case is already closed.'))
            now = fields.Datetime.now()
            previous = case.state
            models.Model.write(case, {
                'state': 'closed_with_reason',
                'closure_reason': closure_reason,
                'closure_note': str(note).strip(),
                'closed_at': now,
                'closed_by_id': self.env.user.id,
            })
            case._log(case, 'closed', reason=str(note).strip(), previous=previous, new=closure_reason)
        return True

    def action_reopen(self, reason):
        if not reason or not str(reason).strip():
            raise UserError(self.env._('Reopening needs a reason.'))
        for case in self:
            case._check_manager()
            if case.state != 'closed_with_reason':
                raise UserError(self.env._('Only a closed case can be reopened.'))
            if case.closure_reason == 'superseded_by_case':
                raise UserError(self.env._(
                    'A merged case stays closed. Continue on the surviving case.'
                ))
            current = case.membership_ids.filtered('is_current')
            if not current:
                raise UserError(self.env._('This case has no current finding membership to reopen.'))
            previous_reason = case.closure_reason or ''
            models.Model.write(case, {
                'state': 'under_investigation',
                'reopened_at': fields.Datetime.now(),
            })
            case._log(case, 'reopened', reason=str(reason).strip(), previous=previous_reason, new='under_investigation')
        return True

    def action_merge(self, source_case_id, reason):
        self.ensure_one()
        source = self.env['cpla.leakage.case'].browse(source_case_id).exists()
        if not source or source == self or not reason or not str(reason).strip():
            raise UserError(self.env._('Merge needs a different source case and a reason.'))
        self._check_manager()
        source.check_access('read')
        for case in self | source:
            if case.state not in OPEN_STATES:
                raise UserError(self.env._(
                    'Merge is refused while a case is with finance review or already closed.'
                ))
        if source.company_id != self.company_id or source.partner_id != self.partner_id:
            raise UserError(self.env._('Only the same company and customer can share a case.'))
        if source.case_type != self.case_type:
            raise UserError(self.env._('Those cases are not the same investigation type.'))
        if not self._currency_compatible(self, source):
            raise UserError(self.env._(
                'The exposures are not in one comparable currency. They were not added.'
            ))
        source_members = source.membership_ids.filtered('is_current')
        if not source_members:
            raise UserError(self.env._('The source case has no current finding to move.'))
        try:
            with self.env.cr.savepoint():
                for membership in source_members:
                    finding = membership.finding_id
                    models.Model.write(membership, {
                        'is_current': False,
                        'removed_at': fields.Datetime.now(),
                    })
                    membership.flush_recordset(['is_current'])
                    self._link(self, finding, event=False)
                    self._log(
                        self, 'finding_linked', reason=str(reason).strip(),
                        source_model='cpla.leakage.finding', source_res_id=finding.id,
                    )
                now = fields.Datetime.now()
                models.Model.write(source, {
                    'state': 'closed_with_reason',
                    'closure_reason': 'superseded_by_case',
                    'closure_note': str(reason).strip(),
                    'closed_at': now,
                    'closed_by_id': self.env.user.id,
                    'superseded_by_case_id': self.id,
                })
                self._sync_exposure(self, update_reviewed=True)
                self._sync_exposure(source, update_reviewed=False)
                self._log(self, 'merged', reason=str(reason).strip(), previous=source.reference, new=self.reference)
                source._log(source, 'merged', reason=str(reason).strip(), previous=source.reference, new=self.reference)
                source._log(source, 'closed', reason=str(reason).strip(), new='superseded_by_case', bump=False)
        except IntegrityError:
            raise UserError(self.env._(
                'Merge stopped because a finding already has a current investigation.'
            ))
        return True

    def action_split(self, finding_ids, reason):
        self.ensure_one()
        if not reason or not str(reason).strip():
            raise UserError(self.env._('A split needs a reason.'))
        self._check_manager()
        if self.state not in OPEN_STATES:
            raise UserError(self.env._(
                'Split is refused while the case is with finance review or closed.'
            ))
        current = self.membership_ids.filtered('is_current')
        selected = current.filtered(lambda membership: membership.finding_id.id in set(finding_ids))
        if not selected or len(selected) == len(current):
            raise UserError(self.env._(
                'Leave at least one current finding on this case and move at least one.'
            ))
        findings = selected.finding_id
        try:
            with self.env.cr.savepoint():
                for membership in selected:
                    models.Model.write(membership, {
                        'is_current': False,
                        'removed_at': fields.Datetime.now(),
                    })
                selected.flush_recordset(['is_current'])
                spawned = self._create_case(findings, self.grouping_basis, str(reason).strip())
                for finding in findings:
                    self._link(spawned, finding, event=False)
                self._seed_checklist(spawned)
                self._seed_evidence(spawned, findings)
                self._sync_exposure(self, update_reviewed=True)
                self._sync_exposure(spawned, update_reviewed=True)
                self._log(self, 'split', reason=str(reason).strip(), new=spawned.reference)
                spawned._log(spawned, 'created', reason=str(reason).strip(), previous=self.reference, bump=False)
                for finding in findings:
                    self._log(
                        self, 'finding_removed', reason=str(reason).strip(),
                        source_model='cpla.leakage.finding', source_res_id=finding.id,
                    )
                    spawned._log(
                        spawned, 'finding_linked',
                        source_model='cpla.leakage.finding', source_res_id=finding.id,
                    )
        except IntegrityError:
            raise UserError(self.env._('Split stopped because a current membership already exists.'))
        return spawned

    def action_schedule_activity(self, user_id, date_deadline, summary, note=None):
        self.ensure_one()
        user = self.env['res.users'].browse(user_id).exists()
        if not user or not date_deadline or not summary or not str(summary).strip():
            raise UserError(self.env._(
                'A follow-up needs a user, a due date, and a summary. No default deadline is applied.'
            ))
        self._check_investigator_actor()
        self._check_open_for_edit()
        if not self._eligible_investigator(user):
            raise AccessError(self.env._('That user cannot be assigned this company follow-up.'))
        if isinstance(date_deadline, str):
            date_deadline = fields.Date.to_date(date_deadline)
        activity = self.activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            date_deadline=date_deadline,
            summary=str(summary).strip(),
            note=note or '',
            user_id=user.id,
            automated=False,
        )
        return activity

    def action_open_assign_wizard(self):
        return self._wizard('assign')

    def action_open_priority_wizard(self):
        return self._wizard('priority')

    def action_open_severity_wizard(self):
        return self._wizard('severity')

    def action_open_evidence_pending_wizard(self):
        return self._wizard('evidence_pending')

    def action_open_accept_wizard(self):
        return self._wizard('accept_source')

    def action_open_root_cause_wizard(self):
        return self._wizard('root_cause')

    def action_open_outcome_wizard(self):
        return self._wizard('outcome')

    def action_open_close_wizard(self):
        return self._wizard('close')

    def action_open_reopen_wizard(self):
        return self._wizard('reopen')

    def action_open_return_wizard(self):
        return self._wizard('return')

    def action_open_merge_wizard(self):
        return self._wizard('merge')

    def action_open_split_wizard(self):
        return self._wizard('split')

    def action_open_activity_wizard(self):
        return self._wizard('activity')

    def action_view_findings(self):
        self.ensure_one()
        self.check_access('read')
        return self._window(
            'cpla.leakage.finding',
            [('id', 'in', self.membership_ids.filtered('is_current').finding_id.ids)],
            self.env._('Linked findings'),
        )

    def action_view_results(self):
        self.ensure_one()
        self.check_access('read')
        findings = self.membership_ids.filtered('is_current').finding_id
        return self._window(
            'cpla.invoice.audit.result',
            [('finding_id', 'in', findings.ids), ('company_id', '=', self.company_id.id)],
            self.env._('Audit results'),
        )

    def action_view_invoices(self):
        self.ensure_one()
        self.check_access('read')
        moves = self.membership_ids.filtered('is_current').finding_id.mapped('move_id')
        return self._window('account.move', [('id', 'in', moves.ids)], self.env._('Source invoices'))

    def action_view_versions(self):
        self.ensure_one()
        self.check_access('read')
        versions = self.membership_ids.filtered('is_current').finding_id.mapped('version_id')
        return self._window(
            'cpla.customer.contract.version',
            [('id', 'in', versions.ids)],
            self.env._('Contract versions'),
        )

    def action_view_orders(self):
        self.ensure_one()
        self.check_access('read')
        orders = self.env['sale.order']
        for finding in self.membership_ids.filtered('is_current').finding_id:
            order = self._sale_order(finding)
            if order:
                orders |= order
        return self._window('sale.order', [('id', 'in', orders.ids)], self.env._('Sales orders'))

    def _wizard(self, operation):
        self.ensure_one()
        self.check_access('read')
        wizard = self.env['cpla.leakage.case.wizard'].create({
            'case_id': self.id,
            'company_id': self.company_id.id,
            'operation': operation,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Investigation action'),
            'res_model': 'cpla.leakage.case.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _window(self, model, domain, name):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def _create_case(self, findings, grouping_basis, grouping_note):
        company = findings.company_id
        if len(company) != 1:
            raise UserError(self.env._('A case belongs to one company.'))
        reference = self.env['ir.sequence'].with_company(company).next_by_code(CASE_SEQUENCE)
        if not reference:
            raise UserError(self.env._(
                'The investigation case sequence is missing. No reference was invented.'
            ))
        categories = list(dict.fromkeys(findings.mapped('leakage_category')))
        case_type = TYPE_BY_CATEGORY[findings[0].leakage_category]
        detected = [item.first_detected_at for item in findings if item.first_detected_at]
        values = {
            'reference': reference,
            'title': '%s / %s' % (findings[0].partner_id.display_name, categories[0]),
            'company_id': company.id,
            'partner_id': findings[0].partner_id.id,
            'case_type': case_type,
            'state': 'new',
            'primary_category': categories[0] if len(categories) == 1 else 'MIXED',
            'exception_queue': False if case_type == 'potential_leakage' else QUEUE_BY_CATEGORY.get(categories[0]),
            'grouping_basis': grouping_basis or False,
            'first_detected_at': min(detected) if detected else False,
            'opened_at': fields.Datetime.now(),
            'case_revision': 1,
            'investigation_summary': grouping_note or False,
        }
        return models.Model.create(self, [values])

    @api.model
    def _link(self, case, finding, event=True):
        if finding.company_id != case.company_id or finding.partner_id != case.partner_id:
            raise UserError(self.env._(
                'A finding from another company or customer cannot join this case.'
            ))
        models.Model.create(self.env['cpla.leakage.case.membership'], [{
            'case_id': case.id,
            'finding_id': finding.id,
            'company_id': case.company_id.id,
            'is_current': True,
            'reviewed_exposure_exact': finding.potential_leakage_exact or False,
            'reviewed_fingerprint': finding.input_fingerprint or False,
            'reviewed_revision': finding.calculation_revision or 0,
            'reviewed_status': finding.finding_status,
            'reviewed_identity': finding.current_identity or False,
            'linked_at': fields.Datetime.now(),
        }])
        if event:
            self._log(
                case, 'finding_linked',
                source_model='cpla.leakage.finding', source_res_id=finding.id,
            )

    @api.model
    def _seed_checklist(self, case):
        rows = []
        for sequence, (code, label, applicability) in enumerate(CHECKLIST, start=1):
            required = (
                (case.case_type == 'potential_leakage' and applicability in ('potential', 'both'))
                or (case.case_type != 'potential_leakage' and applicability in ('exception', 'both'))
            )
            rows.append({
                'case_id': case.id,
                'company_id': case.company_id.id,
                'sequence': sequence,
                'code': code,
                'name': label,
                'required_for_submission': required,
                'answer': 'unanswered',
            })
        models.Model.create(self.env['cpla.leakage.case.checklist'], rows)

    @api.model
    def _seed_evidence(self, case, findings):
        rows = []
        for finding in findings:
            rows.append(self._source_row(
                case, 'Potential finding %s' % finding.reference,
                'cpla.leakage.finding', finding.id,
            ))
            result = self._latest_result(finding)
            if result:
                rows.append(self._source_row(
                    case, 'Audit result %s' % result.id,
                    'cpla.invoice.audit.result', result.id,
                ))
            if finding.move_id:
                move = finding.move_id
                # The invoice number is an account.move field. Contract managers
                # do not have that read right. Keep the link and use the id.
                label = move.name if move.has_access('read') else move.id
                rows.append(self._source_row(
                    case, 'Invoice %s' % label,
                    'account.move', move.id,
                ))
            if finding.version_id:
                rows.append(self._source_row(
                    case, 'Contract version %s' % (finding.version_id.reference or finding.version_id.id),
                    'cpla.customer.contract.version', finding.version_id.id,
                ))
        rows.append({
            'case_id': case.id,
            'company_id': case.company_id.id,
            'evidence_kind': 'investigation',
            'name': 'Additional investigation evidence',
            'status': 'not_requested',
        })
        models.Model.create(self.env['cpla.leakage.case.evidence'], rows)
        self._refresh_evidence_status_for(case)

    @api.model
    def _source_row(self, case, name, model_name, res_id):
        return {
            'case_id': case.id,
            'company_id': case.company_id.id,
            'evidence_kind': 'source',
            'name': name,
            'source_model': model_name,
            'source_res_id': res_id,
            'status': 'received',
        }

    def _sync_exposure(self, cases, update_reviewed):
        for case in cases:
            values = self._exposure_values(case)
            if update_reviewed and values['exposure_comparable'] and not values['exposure_unknown_count']:
                values['reviewed_exposure_exact'] = values['current_potential_exposure_exact']
            models.Model.write(case, values)

    def _exposure_values(self, case):
        comparable = []
        unknown = 0
        currencies = set()
        stale = False
        for membership in case.membership_ids.filtered('is_current'):
            finding = membership.finding_id
            successor = self._successor(membership)
            if successor or self._membership_stale(membership):
                stale = True
            if (
                not finding.is_current
                or finding.finding_status not in ('potential', 'review_required')
            ):
                unknown += 1
                continue
            amount = _decimal(finding.potential_leakage_exact)
            if finding.finding_status != 'potential' or amount is None:
                unknown += 1
                continue
            comparable.append(amount)
            if finding.currency_id:
                currencies.add(finding.currency_id.id)
        mixed_currency = len(currencies) > 1
        if mixed_currency or unknown or not comparable:
            return {
                'current_potential_exposure_exact': False,
                'exposure_currency_id': False,
                'exposure_comparable': not mixed_currency and not unknown,
                'exposure_unknown_count': unknown + (len(comparable) if mixed_currency else 0),
                'source_reassessment_required': stale or mixed_currency,
            }
        total = ZERO
        for amount in comparable:
            total = _arithmetic('add', total, amount)
        return {
            'current_potential_exposure_exact': _text(total),
            'exposure_currency_id': next(iter(currencies)) if currencies else False,
            'exposure_comparable': True,
            'exposure_unknown_count': 0,
            'source_reassessment_required': stale,
        }

    def _membership_stale(self, membership):
        finding = membership.finding_id
        return any((
            (finding.input_fingerprint or False) != (membership.reviewed_fingerprint or False),
            (finding.potential_leakage_exact or False) != (membership.reviewed_exposure_exact or False),
            (finding.calculation_revision or 0) != (membership.reviewed_revision or 0),
            finding.finding_status != membership.reviewed_status,
            not finding.is_current,
        ))

    def _mark_source_revision(self):
        self.ensure_one()
        values = self._exposure_values(self)
        write_values = {
            'source_reassessment_required': values['source_reassessment_required'],
            'current_potential_exposure_exact': values['current_potential_exposure_exact'],
            'exposure_currency_id': values['exposure_currency_id'],
            'exposure_comparable': values['exposure_comparable'],
            'exposure_unknown_count': values['exposure_unknown_count'],
        }
        if self.state == 'ready_for_finance_review' and values['source_reassessment_required']:
            write_values['finance_package_stale'] = True
        models.Model.write(self, write_values)
        if values['source_reassessment_required']:
            already = self.event_ids.filtered(
                lambda event: event.event_type == 'source_revision_detected' and event.case_revision == self.case_revision
            )
            if not already:
                self._log(self, 'source_revision_detected', previous=self.reviewed_exposure_exact or '')

    def _successor(self, membership):
        identity = membership.reviewed_identity
        if not identity:
            return self.env['cpla.leakage.finding']
        return self.env['cpla.leakage.finding'].search([
            ('current_identity', '=', identity),
            ('is_current', '=', True),
            ('company_id', '=', membership.company_id.id),
            ('id', '!=', membership.finding_id.id),
        ], limit=1)

    def _submission_snapshot(self):
        self.ensure_one()
        findings = []
        for membership in self.membership_ids.filtered('is_current'):
            finding = membership.finding_id
            findings.append({
                'finding_id': finding.id,
                'reference': finding.reference,
                'identity': finding.current_identity,
                'revision': finding.calculation_revision,
                'fingerprint': finding.input_fingerprint,
                'exposure': finding.potential_leakage_exact or '',
                'currency': finding.currency_id.name or '',
                'status': finding.finding_status,
            })
        return {
            'case_id': self.id,
            'company_id': self.company_id.id,
            'case_revision': self.case_revision,
            'submitted_by_id': self.env.user.id,
            'submitted_at': fields.Datetime.now(),
            'potential_exposure_exact': self.current_potential_exposure_exact or False,
            'currency_id': self.exposure_currency_id.id,
            'root_cause': self.root_cause,
            'root_cause_explanation': self.root_cause_explanation,
            'investigation_outcome': self.investigation_outcome,
            'evidence_status': self.evidence_status,
            'outstanding_qualification': self.outstanding_qualification,
            'finding_snapshot': json.dumps(findings, sort_keys=True),
        }

    def _refresh_evidence_status(self):
        self.ensure_one()
        self._refresh_evidence_status_for(self)

    @api.model
    def _refresh_evidence_status_for(self, case):
        source = case.evidence_ids.filtered(lambda item: item.evidence_kind == 'source')
        if not source:
            status = 'not_requested'
        elif any(item.status == 'rejected' for item in source):
            status = 'rejected'
        elif all(item.status in ('verified', 'not_applicable') for item in source):
            status = 'verified'
        elif any(item.status == 'requested' for item in source):
            status = 'requested'
        elif any(item.status == 'received' for item in source):
            status = 'received'
        else:
            status = 'not_requested'
        models.Model.write(case, {'evidence_status': status})

    def _own_evidence(self, evidence_id):
        self.ensure_one()
        evidence = self.evidence_ids.filtered(lambda item: item.id == evidence_id)[:1]
        if not evidence:
            raise UserError(self.env._('That evidence line is not on this case.'))
        return evidence

    def _log(self, case, event_type, reason='', previous='', new='', source_model=False, source_res_id=0, bump=True):
        if bump:
            revision = (case.case_revision or 0) + 1
            models.Model.write(case, {
                'case_revision': revision,
                'last_activity_at': fields.Datetime.now(),
            })
        else:
            revision = case.case_revision
            models.Model.write(case, {'last_activity_at': fields.Datetime.now()})
        models.Model.create(self.env['cpla.leakage.case.event'], [{
            'case_id': case.id,
            'company_id': case.company_id.id,
            'event_type': event_type,
            'actor_id': self.env.user.id,
            'occurred_at': fields.Datetime.now(),
            'reason': reason or False,
            'previous_value': previous or False,
            'new_value': new or False,
            'source_model': source_model or False,
            'source_res_id': source_res_id or 0,
            'case_revision': revision,
        }])
        if event_type == 'state_changed':
            case.message_post(body=str(self.env._(
                'Investigation state changed from %s to %s.',
                previous or '',
                new or '',
            )))

    @api.model
    def _canonical_membership(self, finding):
        return self.env['cpla.leakage.case.membership'].search([
            ('finding_id', '=', finding.id),
            ('is_current', '=', True),
        ], limit=1)

    @api.model
    def _check_eligible(self, finding):
        if not self.env.su and finding.company_id not in self.env.companies:
            raise AccessError(self.env._('You cannot open a case for that company.'))
        if not finding.is_current:
            raise UserError(self.env._('Only a current finding can open an investigation.'))
        if not finding.partner_id:
            raise UserError(self.env._('The finding has no customer.'))
        if finding.finding_status == 'potential':
            if finding.leakage_category not in LEAKAGE_CLASSES:
                raise UserError(self.env._('That finding is not a potential leakage investigation.'))
            if _decimal(finding.potential_leakage_exact) is None:
                raise UserError(self.env._(
                    'A potential finding without an amount cannot open a leakage case.'
                ))
            return
        if finding.finding_status == 'review_required':
            if finding.leakage_category not in REVIEW_CLASSES:
                raise UserError(self.env._('That review finding has no investigation category.'))
            if _decimal(finding.potential_leakage_exact) is not None:
                raise UserError(self.env._(
                    'A review exception cannot carry a leakage amount into a case.'
                ))
            return
        raise UserError(self.env._('This finding is not eligible for a new investigation.'))

    @api.model
    def _assert_groupable(self, findings, basis):
        if basis not in GROUPING_BASES:
            raise UserError(self.env._(
                'That grouping basis is not approved. Customer alone is not a basis.'
            ))
        if len(findings.company_id) != 1:
            raise UserError(self.env._('Findings from different companies cannot share one case.'))
        if len(findings.partner_id) != 1:
            raise UserError(self.env._(
                'Findings for different customers are investigated separately.'
            ))
        types = {TYPE_BY_CATEGORY.get(finding.leakage_category) for finding in findings}
        if len(types) != 1 or False in types:
            raise UserError(self.env._('Those findings are not the same case type.'))
        currencies = set()
        has_amount = False
        has_unknown = False
        for finding in findings:
            amount = _decimal(finding.potential_leakage_exact)
            if finding.finding_status == 'potential' and amount is not None:
                has_amount = True
                if finding.currency_id:
                    currencies.add(finding.currency_id.id)
            else:
                has_unknown = True
        if has_amount and has_unknown:
            raise UserError(self.env._(
                'An unknown amount cannot be added to a known leakage total.'
            ))
        if len(currencies) > 1:
            raise UserError(self.env._(
                'Findings in different currencies are not added together.'
            ))
        if basis == 'same_sales_order':
            orders = set()
            for finding in findings:
                order = self._sale_order(finding)
                if not order:
                    raise UserError(self.env._('Every finding needs a verified sales order for this grouping.'))
                orders.add(order.id)
            if len(orders) != 1:
                raise UserError(self.env._('Those findings are not the same sales order.'))
        elif basis == 'same_contract_version':
            versions = set(findings.mapped('version_id').ids)
            if not versions or False in versions or len(versions) != 1:
                raise UserError(self.env._('Those findings are not the same contract version.'))
        elif basis == 'same_invoice':
            moves = set(findings.mapped('move_id').ids)
            if not moves or False in moves or len(moves) != 1:
                raise UserError(self.env._('Those findings are not the same invoice.'))

    @api.model
    def _currency_compatible(self, left, right):
        if left.exposure_unknown_count or right.exposure_unknown_count:
            return _blank(left.current_potential_exposure_exact) and _blank(right.current_potential_exposure_exact)
        if _blank(left.current_potential_exposure_exact) and _blank(right.current_potential_exposure_exact):
            return True
        return (
            left.exposure_comparable
            and right.exposure_comparable
            and left.exposure_currency_id
            and left.exposure_currency_id == right.exposure_currency_id
        )

    @api.model
    def _sale_order(self, finding):
        if finding.allocation_id and finding.allocation_id.sale_order_id:
            return finding.allocation_id.sale_order_id
        result = self._latest_result(finding)
        return result.sale_order_id if result else self.env['sale.order']

    @api.model
    def _latest_result(self, finding):
        return self.env['cpla.invoice.audit.result'].search([
            ('finding_id', '=', finding.id),
            ('company_id', '=', finding.company_id.id),
        ], order='id desc', limit=1)

    def _eligible_investigator(self, user):
        self.ensure_one()
        if not user or user.share or not user.active:
            return False
        if self.company_id not in user.company_ids:
            return False
        return any(user.has_group(group) for group in INVESTIGATOR_GROUPS)

    def _partner_may_follow(self, partner_id):
        self.ensure_one()
        partner = self.env['res.partner'].browse(partner_id).exists()
        users = partner.user_ids
        if not partner or not users or any(user.share for user in users):
            return False
        for user in users:
            if self.company_id not in user.company_ids:
                return False
            if not any(user.has_group(group) for group in READ_GROUPS):
                return False
        return True

    def _check_manager(self):
        user = self.env.user
        if self.env.su or user._is_superuser() or user.has_group(MANAGER_GROUP):
            return
        raise AccessError(self.env._('Only a contract manager can perform that case action.'))

    def _check_investigator_actor(self):
        self.ensure_one()
        self._check_company_actor()
        user = self.env.user
        if self.env.su or user._is_superuser() or user.has_group(MANAGER_GROUP):
            return
        if user == self.owner_id and self._eligible_investigator(user):
            return
        raise AccessError(self.env._('You are not the investigator for this case.'))

    def _check_finance_actor(self):
        self.ensure_one()
        self._check_company_actor()
        user = self.env.user
        if self.env.su or user._is_superuser():
            return
        if any(user.has_group(group) for group in FINANCE_GROUPS):
            return
        raise AccessError(self.env._('Only a finance reviewer can return this case.'))

    def _check_case_reader(self):
        self.ensure_one()
        self.check_access('read')
        self._check_company_actor()

    def _check_company_actor(self):
        self.ensure_one()
        if self.env.su or self.env.user._is_superuser():
            return
        if self.company_id not in self.env.companies:
            raise AccessError(self.env._('You cannot act on that company case.'))

    def _check_open_for_edit(self):
        self.ensure_one()
        if self.state in ('ready_for_finance_review', 'closed_with_reason'):
            raise UserError(self.env._(
                'This case is with finance review or closed. The investigation fields stay as submitted.'
            ))

    def _require_chatter_actor(self):
        user = self.env.user
        if self.env.su or user._is_superuser():
            return
        if any(user.has_group(group) for group in CHATTER_GROUPS):
            return
        raise AccessError(self.env._('You cannot post on this investigation.'))

    def _check_creator(self):
        self._check_manager()


class LeakageCaseMembership(models.Model):
    """One finding in one case.

    ``is_current`` is the canonical investigation membership, including a
    closed case. Historical rows stay after a merge, split, or accepted
    source revision. The partial unique index allows only one current row
    per finding.
    """

    _name = 'cpla.leakage.case.membership'
    _description = 'Leakage Case Membership'
    _order = 'id desc'
    _check_company_auto = True

    _current_finding_unique = models.UniqueIndex(
        '(finding_id) WHERE is_current IS TRUE',
        'This finding already has a current investigation membership.',
    )

    case_id = fields.Many2one(
        'cpla.leakage.case', required=True, index=True, readonly=True, ondelete='restrict',
    )
    finding_id = fields.Many2one(
        'cpla.leakage.finding', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    is_current = fields.Boolean(readonly=True, index=True, default=False)
    reviewed_exposure_exact = fields.Char(readonly=True)
    reviewed_fingerprint = fields.Char(readonly=True)
    reviewed_revision = fields.Integer(readonly=True)
    reviewed_status = fields.Char(readonly=True)
    reviewed_identity = fields.Char(readonly=True, index=True)
    linked_at = fields.Datetime(readonly=True)
    removed_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._('Case membership is created by the investigation workflow.'))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        raise UserError(self.env._('Case membership cannot be edited directly.'))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._('Case membership cannot be deleted.'))


class LeakageCaseEvent(models.Model):
    """Append-only investigation event.

    Application code rejects writes and deletes. That is not a cryptographic
    archive. The actor and the time come from the server, not the client.
    """

    _name = 'cpla.leakage.case.event'
    _description = 'Leakage Case Event'
    _order = 'id'
    _check_company_auto = True

    case_id = fields.Many2one(
        'cpla.leakage.case', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    event_type = fields.Selection(selection=EVENT_TYPES, required=True, readonly=True, index=True)
    actor_id = fields.Many2one('res.users', required=True, readonly=True, index=True)
    occurred_at = fields.Datetime(required=True, readonly=True, index=True)
    reason = fields.Text(readonly=True)
    previous_value = fields.Char(readonly=True)
    new_value = fields.Char(readonly=True)
    source_model = fields.Char(readonly=True)
    source_res_id = fields.Integer(readonly=True)
    case_revision = fields.Integer(readonly=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._('Case history is recorded by the investigation workflow.'))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        raise UserError(self.env._('Investigation history cannot be edited.'))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._('Investigation history cannot be deleted.'))


class LeakageCaseChecklist(models.Model):
    _name = 'cpla.leakage.case.checklist'
    _description = 'Leakage Case Checklist'
    _order = 'sequence, id'
    _check_company_auto = True

    case_id = fields.Many2one(
        'cpla.leakage.case', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    sequence = fields.Integer(readonly=True)
    code = fields.Char(required=True, readonly=True, index=True)
    name = fields.Char(required=True, readonly=True)
    required_for_submission = fields.Boolean(readonly=True)
    answer = fields.Selection(
        selection=[
            ('unanswered', 'Unanswered'),
            ('yes', 'Yes'),
            ('no', 'No'),
            ('not_applicable', 'Not applicable'),
        ],
        required=True,
        default='unanswered',
    )
    note = fields.Text()
    answered_by_id = fields.Many2one('res.users', readonly=True)
    answered_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._('The checklist is created with the case.'))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        if set(vals) - {'answer', 'note'}:
            raise UserError(self.env._('Only the checklist answer and note can be saved.'))
        for line in self:
            line.case_id._check_investigator_actor()
            line.case_id._check_open_for_edit()
            if vals.get('answer') == 'not_applicable' and not (vals.get('note') or line.note):
                raise UserError(self.env._('Not applicable needs a note.'))
        values = dict(vals)
        if 'answer' in values:
            values['answered_by_id'] = self.env.user.id
            values['answered_at'] = fields.Datetime.now()
        return super().write(values)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._('Checklist lines cannot be deleted.'))


class LeakageCaseEvidence(models.Model):
    _name = 'cpla.leakage.case.evidence'
    _description = 'Leakage Case Evidence'
    _order = 'id'
    _check_company_auto = True

    case_id = fields.Many2one(
        'cpla.leakage.case', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    evidence_kind = fields.Selection(
        selection=[('source', 'Source evidence'), ('investigation', 'Investigation evidence')],
        required=True,
        readonly=True,
    )
    name = fields.Char(required=True, readonly=True)
    source_model = fields.Char(readonly=True)
    source_res_id = fields.Integer(readonly=True)
    status = fields.Selection(selection=EVIDENCE_STATUSES, required=True, readonly=True)
    status_note = fields.Text(readonly=True)
    requested_by_id = fields.Many2one('res.users', readonly=True)
    requested_at = fields.Datetime(readonly=True)
    reviewed_by_id = fields.Many2one('res.users', readonly=True)
    reviewed_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._('Evidence lines are created by the investigation workflow.'))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        raise UserError(self.env._('Evidence status is changed by the investigation action.'))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._('Investigation evidence lines cannot be deleted.'))

    def action_verify(self):
        self.ensure_one()
        return self.case_id.action_verify_evidence(self.id)

    def action_reject(self):
        self.ensure_one()
        return self.case_id.action_open_evidence_wizard(self.id, 'reject_evidence')

    def action_request(self):
        self.ensure_one()
        return self.case_id.action_open_evidence_wizard(self.id, 'request_evidence')


class LeakageCaseSubmission(models.Model):
    """Finance handoff snapshot.

    The row is the package the investigator submitted. A later return fills
    the return fields and does not delete the package. Nothing on this row
    is a finance-validated amount.
    """

    _name = 'cpla.leakage.case.submission'
    _description = 'Leakage Case Finance Submission'
    _order = 'id'
    _check_company_auto = True

    case_id = fields.Many2one(
        'cpla.leakage.case', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    case_revision = fields.Integer(readonly=True)
    submitted_by_id = fields.Many2one('res.users', readonly=True)
    submitted_at = fields.Datetime(readonly=True)
    potential_exposure_exact = fields.Char(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    root_cause = fields.Char(readonly=True)
    root_cause_explanation = fields.Text(readonly=True)
    investigation_outcome = fields.Char(readonly=True)
    evidence_status = fields.Char(readonly=True)
    outstanding_qualification = fields.Text(readonly=True)
    finding_snapshot = fields.Text(readonly=True)
    returned_by_id = fields.Many2one('res.users', readonly=True)
    returned_at = fields.Datetime(readonly=True)
    return_reason = fields.Text(readonly=True)
    required_action = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._('A finance snapshot is created by submission.'))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        raise UserError(self.env._('A finance snapshot cannot be edited directly.'))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        raise UserError(self.env._('A finance snapshot cannot be deleted.'))


class LeakageCaseWizard(models.TransientModel):
    _name = 'cpla.leakage.case.wizard'
    _description = 'Leakage Case Action'
    _check_company_auto = True

    case_id = fields.Many2one('cpla.leakage.case')
    company_id = fields.Many2one('res.company', required=True)
    operation = fields.Selection(
        selection=[
            ('assign', 'Assign'),
            ('priority', 'Priority'),
            ('severity', 'Severity'),
            ('root_cause', 'Root cause'),
            ('outcome', 'Outcome'),
            ('close', 'Close'),
            ('reopen', 'Reopen'),
            ('return', 'Return for rework'),
            ('merge', 'Merge'),
            ('split', 'Split'),
            ('activity', 'Schedule follow-up'),
            ('group_findings', 'Group findings'),
            ('request_evidence', 'Request evidence'),
            ('reject_evidence', 'Reject evidence'),
            ('evidence_pending', 'Evidence pending'),
            ('accept_source', 'Accept source revision'),
        ],
        required=True,
    )
    user_id = fields.Many2one('res.users')
    reason = fields.Text()
    note = fields.Text()
    priority = fields.Selection(selection=PRIORITIES)
    severity = fields.Selection(selection=PRIORITIES)
    root_cause = fields.Selection(selection=ROOT_CAUSES)
    outcome = fields.Selection(selection=OUTCOMES)
    closure_reason = fields.Selection(selection=CLOSURE_REASONS)
    required_action = fields.Text()
    source_case_id = fields.Many2one('cpla.leakage.case')
    finding_ids = fields.Many2many('cpla.leakage.finding')
    grouping_basis = fields.Selection(selection=[
        ('same_sales_order', 'Same sales order'),
        ('same_contract_version', 'Same contract version'),
        ('same_invoice', 'Same invoice'),
        ('explicit_same_issue', 'Explicit same issue'),
    ])
    date_deadline = fields.Date()
    summary = fields.Char()
    evidence_id = fields.Many2one('cpla.leakage.case.evidence')

    def action_apply(self):
        self.ensure_one()
        operation = self.operation
        case = self.case_id
        if operation == 'group_findings':
            cases = self.env['cpla.leakage.case'].create_from_findings(
                self.finding_ids.ids, grouping_basis=self.grouping_basis, grouping_note=self.reason,
            )
            return self._open_cases(cases)
        if not case:
            raise UserError(self.env._('Choose a case.'))
        if case.company_id != self.company_id:
            raise UserError(self.env._('The wizard company does not match the case.'))
        case.check_access('read')
        if operation == 'assign':
            case.action_assign(self.user_id.id, self.reason)
        elif operation == 'priority':
            case.action_set_priority(self.priority, self.reason)
        elif operation == 'severity':
            case.action_set_severity(self.severity, self.reason)
        elif operation == 'root_cause':
            case.action_record_root_cause(self.root_cause, self.reason)
        elif operation == 'outcome':
            case.action_record_outcome(self.outcome, self.reason)
        elif operation == 'close':
            case.action_close(self.closure_reason, self.reason)
        elif operation == 'reopen':
            case.action_reopen(self.reason)
        elif operation == 'return':
            case.action_return_for_rework(self.reason, self.required_action)
        elif operation == 'merge':
            case.action_merge(self.source_case_id.id, self.reason)
        elif operation == 'split':
            case.action_split(self.finding_ids.ids, self.reason)
        elif operation == 'activity':
            case.action_schedule_activity(self.user_id.id, self.date_deadline, self.summary, self.note)
        elif operation == 'request_evidence':
            case.action_request_evidence(self.evidence_id.id, self.reason)
        elif operation == 'reject_evidence':
            case.action_reject_evidence(self.evidence_id.id, self.reason)
        elif operation == 'evidence_pending':
            case.action_mark_evidence_pending(self.reason)
        elif operation == 'accept_source':
            case.action_accept_current_source(self.reason)
        else:
            raise UserError(self.env._('That investigation action is not available.'))
        return {'type': 'ir.actions.act_window_close'}

    def _open_cases(self, cases):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Leakage cases'),
            'res_model': 'cpla.leakage.case',
            'view_mode': 'list,form',
            'domain': [('id', 'in', cases.ids)],
            'target': 'current',
        }


class LeakageFindingCase(models.Model):
    _inherit = 'cpla.leakage.finding'

    case_membership_ids = fields.One2many('cpla.leakage.case.membership', 'finding_id')
    current_case_id = fields.Many2one('cpla.leakage.case', compute='_compute_current_case')

    @api.depends('case_membership_ids.is_current')
    def _compute_current_case(self):
        memberships = self.env['cpla.leakage.case.membership'].search([
            ('finding_id', 'in', self.ids),
            ('is_current', '=', True),
        ])
        by_finding = {membership.finding_id.id: membership.case_id for membership in memberships}
        for finding in self:
            finding.current_case_id = by_finding.get(finding.id, False)

    def action_open_investigation_case(self):
        cases = self.env['cpla.leakage.case'].create_from_findings(self.ids)
        if len(cases) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': self.env._('Investigation case'),
                'res_model': 'cpla.leakage.case',
                'res_id': cases.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Investigation cases'),
            'res_model': 'cpla.leakage.case',
            'view_mode': 'list,form',
            'domain': [('id', 'in', cases.ids)],
            'target': 'current',
        }

    def action_view_investigation_case(self):
        self.ensure_one()
        self.check_access('read')
        case = self.current_case_id
        if not case:
            raise UserError(self.env._('This finding has no current investigation case.'))
        case.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Investigation case'),
            'res_model': 'cpla.leakage.case',
            'res_id': case.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_prepare_group(self):
        if not self:
            raise UserError(self.env._('Select findings to group.'))
        for finding in self:
            finding.check_access('read')
        wizard = self.env['cpla.leakage.case.wizard'].create({
            'company_id': self[0].company_id.id,
            'operation': 'group_findings',
            'finding_ids': [(6, 0, self.ids)],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Group findings'),
            'res_model': 'cpla.leakage.case.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }


class LeakageCaseEvidenceWizard(models.Model):
    _inherit = 'cpla.leakage.case'

    def action_open_evidence_wizard(self, evidence_id, operation):
        self.ensure_one()
        wizard = self.env['cpla.leakage.case.wizard'].create({
            'case_id': self.id,
            'company_id': self.company_id.id,
            'operation': operation,
            'evidence_id': evidence_id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Evidence'),
            'res_model': 'cpla.leakage.case.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }


class IrAttachmentCaseGuard(models.Model):
    """Block public tokens and deletion of investigation files.

    Read access still follows the linked case company rule. This guard does
    not create a legal hold.
    """

    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('res_model') in CASE_ATTACHMENT_MODELS and vals.get('public'):
                raise UserError(self.env._(
                    'Investigation evidence cannot be public.'
                ))
        records = super().create(vals_list)
        leaked = records.filtered(
            lambda attachment: attachment.res_model in CASE_ATTACHMENT_MODELS and attachment.access_token
        )
        if leaked:
            raise UserError(self.env._('Investigation evidence is not shared by token.'))
        return records

    def write(self, vals):
        protected = self.filtered(lambda attachment: attachment.res_model in CASE_ATTACHMENT_MODELS)
        if protected and (vals.get('public') or vals.get('access_token')):
            raise UserError(self.env._(
                'Investigation evidence cannot be published or shared by token.'
            ))
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        protected = self.filtered(lambda attachment: attachment.res_model in CASE_ATTACHMENT_MODELS)
        if protected:
            raise UserError(self.env._(
                'Investigation evidence files cannot be deleted.'
            ))
        return super().unlink()

    def generate_access_token(self):
        protected = self.filtered(lambda attachment: attachment.res_model in CASE_ATTACHMENT_MODELS)
        if protected:
            raise UserError(self.env._('Investigation evidence is not shared by token.'))
        return super().generate_access_token()
