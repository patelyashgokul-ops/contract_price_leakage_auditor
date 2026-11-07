import json
from decimal import ROUND_HALF_UP, Decimal

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    AUDITOR_GROUP,
    FINANCE_MANAGER_GROUP,
    REVIEWER_GROUP,
    _arithmetic,
    _decimal,
    _text,
)

MODULE = 'contract_price_leakage_auditor'
POLICY_SEQUENCE = 'cpla.finance.validation.policy'
VALIDATION_SEQUENCE = 'cpla.finance.validation'
ZERO = Decimal('0')
APP_ADMIN_GROUP = f'{MODULE}.group_app_admin'

AUTHORITY_GROUPS = {
    'finance_reviewer': REVIEWER_GROUP,
    'finance_manager': FINANCE_MANAGER_GROUP,
}
OPEN_STATES = (
    'draft',
    'submitted',
    'under_finance_review',
    'additional_evidence_required',
    'proposed_decision',
    'pending_approval',
    'stale_source_review_required',
)
FINAL_STATES = ('approved', 'partially_approved', 'rejected')
ACCEPTABLE_REVISION = frozenset({'current_verified', 'reassessment_accepted'})
REASON_CODES = [
    ('FULLY_SUPPORTED', 'Fully supported'),
    ('PARTIALLY_SUPPORTED', 'Partially supported'),
    ('CONTRACT_SCOPE_NOT_PROVEN', 'Contract scope not proven'),
    ('AUTHORIZED_DISCOUNT_CONFIRMED', 'Authorized discount confirmed'),
    ('WRONG_HISTORICAL_PRICE', 'Wrong historical price'),
    ('VALID_GRANDFATHERING', 'Valid grandfathering'),
    ('INVOICE_SOURCE_INCORRECT', 'Invoice source incorrect'),
    ('QUANTITY_ALLOCATION_ERROR', 'Quantity allocation error'),
    ('VERIFIED_RETURN_NOT_REFLECTED', 'Verified return not reflected'),
    ('TAX_BASIS_INCORRECT', 'Tax basis incorrect'),
    ('FX_CONVERSION_INCORRECT', 'FX conversion incorrect'),
    ('UOM_CONVERSION_INCORRECT', 'UoM conversion incorrect'),
    ('DUPLICATE_FINANCIAL_EXPOSURE', 'Duplicate financial exposure'),
    ('APPROVAL_EVIDENCE_MISSING', 'Approval evidence missing'),
    ('CONTRACTUAL_RECOVERY_RIGHT_UNCLEAR', 'Contractual recovery right unclear'),
    ('ADDITIONAL_EVIDENCE_REQUIRED', 'Additional evidence required'),
    ('OTHER_DOCUMENTED_REASON', 'Other documented reason'),
]
STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('under_finance_review', 'Under finance review'),
    ('additional_evidence_required', 'Additional evidence required'),
    ('proposed_decision', 'Proposed decision'),
    ('pending_approval', 'Pending approval'),
    ('partially_approved', 'Partially approved'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('stale_source_review_required', 'Stale source review required'),
    ('superseded', 'Superseded'),
]
DECISION_TYPES = [
    ('unset', 'Not decided'),
    ('full_validation', 'Full validation'),
    ('partial_validation', 'Partial validation'),
    ('full_rejection', 'Full rejection'),
]
THRESHOLD_BASES = [
    ('validated_amount', 'Proposed validated amount'),
    ('accepted_potential', 'Accepted potential exposure'),
    ('proposed_adjustment', 'Amount not proposed as validated'),
    ('customer_open_validated', 'Customer open validated amount in this company'),
]


def _fail(env, code, sentence):
    raise UserError(env._('%s: %s', code, sentence))


def _in_group(env, user, xmlid):
    """Group membership without the superuser short-circuit.

    ``has_group`` returns true for the superuser for every group. That must
    not count as finance approval authority.
    """
    if not user or user._is_superuser() or env.su:
        return False
    return env.ref(xmlid) in user.all_group_ids


def _quantize(amount, currency):
    increment = _decimal(currency.rounding) if currency else None
    if increment is None or increment <= ZERO:
        return amount
    return amount.quantize(increment, rounding=ROUND_HALF_UP)


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)


class FinanceValidationPolicy(models.Model):
    """Company approval matrix for finance validation.

    A draft row is not authority. No amount is seeded. Formal approval is
    blocked until a finance manager approves a revision that names levels.
    """

    _name = 'cpla.finance.validation.policy'
    _description = 'Finance Validation Policy'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This finance validation policy reference already exists.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    name = fields.Char(required=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('superseded', 'Superseded'),
        ],
        required=True,
        default='draft',
        readonly=True,
        index=True,
        copy=False,
    )
    currency_id = fields.Many2one(
        'res.currency',
        required=True,
        string='Limit currency',
        help='Approval ceilings are compared in this currency. A different review currency needs a recorded rate.',
    )
    threshold_basis = fields.Selection(
        selection=THRESHOLD_BASES,
        required=True,
        default='accepted_potential',
        help='Draft default only. It is not an approved limit until this policy revision is approved.',
    )
    partial_validation_allowed = fields.Boolean(
        default=False,
        help='When set, a decision may validate only part of the accepted potential. The rest must be rejected or left unresolved.',
    )
    four_eyes_required = fields.Boolean(
        default=True,
        help='The requester and the case submitter cannot approve. One user cannot complete two levels.',
    )
    change_reason = fields.Text(required=True)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    supersedes_id = fields.Many2one('cpla.finance.validation.policy', readonly=True, copy=False, index=True)
    is_current = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    level_ids = fields.One2many('cpla.finance.validation.policy.level', 'policy_id')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_policy_editor()
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            company = self.env['res.company'].browse(vals.get('company_id')).exists()
            if len(company) != 1:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A company is required on the approval policy.')
            self._require_company(company)
            if not (vals.get('change_reason') or '').strip():
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The approval policy needs a change reason.')
            if not (vals.get('name') or '').strip():
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The approval policy needs a name.')
            reference = self.env['ir.sequence'].with_company(company).next_by_code(POLICY_SEQUENCE)
            if not reference:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The finance policy sequence is missing.')
            vals['reference'] = reference
            vals['state'] = 'draft'
            vals['is_current'] = False
            vals.pop('approved_by_id', None)
            vals.pop('approved_at', None)
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self._check_policy_editor()
        if any(policy.state != 'draft' for policy in self):
            _fail(
                self.env,
                'HISTORICAL_APPROVAL_PROTECTED',
                'An approved finance policy revision cannot be edited. Create a new revision.',
            )
        blocked = set(vals) & {
            'reference', 'state', 'approved_by_id', 'approved_at', 'is_current', 'company_id', 'supersedes_id',
        }
        if blocked:
            _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Those policy fields are set by the server.')
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A finance policy revision cannot be deleted.')

    def action_approve_policy(self):
        """Make this draft the current authority. It does not validate a leakage amount."""
        self._check_policy_editor()
        for policy in self:
            policy._require_company(policy.company_id)
            if policy.state != 'draft':
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Only a draft policy revision can be approved.')
            if not policy.level_ids:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'Add at least one approval level before approving the policy.')
            sequences = policy.level_ids.mapped('level_sequence')
            if len(sequences) != len(set(sequences)):
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'Approval levels need distinct sequences.')
            for level in policy.level_ids:
                if level.authority_group not in AUTHORITY_GROUPS:
                    _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'An approval level names an unknown role.')
                if _decimal(level.applies_from_exact) is None:
                    _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'Each level needs an applies-from amount.')
                if level.has_ceiling and _decimal(level.maximum_exact) is None:
                    _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'A level with a ceiling needs a maximum amount.')
            current = self.search([
                ('company_id', '=', policy.company_id.id),
                ('is_current', '=', True),
                ('state', '=', 'approved'),
            ])
            if current:
                models.Model.write(current, {'state': 'superseded', 'is_current': False})
            models.Model.write(policy, {
                'state': 'approved',
                'is_current': True,
                'approved_by_id': self.env.user.id,
                'approved_at': fields.Datetime.now(),
                'supersedes_id': current[:1].id,
            })
        return True

    def action_new_revision(self):
        self.ensure_one()
        self._check_policy_editor()
        self._require_company(self.company_id)
        if self.state != 'approved' or not self.is_current:
            _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'Revise the current approved policy.')
        revision = self.create({
            'company_id': self.company_id.id,
            'name': self.name,
            'currency_id': self.currency_id.id,
            'threshold_basis': self.threshold_basis,
            'partial_validation_allowed': self.partial_validation_allowed,
            'four_eyes_required': self.four_eyes_required,
            'change_reason': 'New draft revision. Not approved until a finance manager approves it.',
        })
        for level in self.level_ids:
            self.env['cpla.finance.validation.policy.level'].create({
                'policy_id': revision.id,
                'name': level.name,
                'level_sequence': level.level_sequence,
                'authority_group': level.authority_group,
                'applies_from_exact': level.applies_from_exact,
                'has_ceiling': level.has_ceiling,
                'maximum_exact': level.maximum_exact,
            })
        return revision.action_open_form()

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

    @api.model
    def current_for(self, company):
        return self.search([
            ('company_id', '=', company.id),
            ('state', '=', 'approved'),
            ('is_current', '=', True),
        ], limit=1)

    def _required_levels(self, amount):
        self.ensure_one()
        if self.state != 'approved' or not self.is_current:
            _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The approval policy is not the current approved revision.')
        levels = self.level_ids.sorted('level_sequence')
        if not levels:
            _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The approved policy has no levels.')
        required = []
        ceilings = []
        unlimited = False
        for level in levels:
            start = _decimal(level.applies_from_exact)
            if start is None:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'An approval level has no applies-from amount.')
            if amount + ZERO < start:
                continue
            required.append(level)
            if level.has_ceiling:
                ceiling = _decimal(level.maximum_exact)
                if ceiling is None:
                    _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'An approval level ceiling is missing.')
                ceilings.append(ceiling)
            else:
                unlimited = True
        if not required:
            _fail(self.env, 'APPROVAL_LIMIT_EXCEEDED', 'No approval level covers this amount.')
        if not unlimited and amount > max(ceilings):
            _fail(self.env, 'APPROVAL_LIMIT_EXCEEDED', 'The amount is above every configured approval ceiling.')
        return required

    @api.model
    def _check_policy_editor(self):
        user = self.env.user
        if _in_group(self.env, user, FINANCE_MANAGER_GROUP):
            return
        if user._is_superuser() or _in_group(self.env, user, APP_ADMIN_GROUP):
            raise AccessError(self.env._(
                'APPROVAL_MATRIX_MISSING: A technical administrator is not a finance approver.'
            ))
        raise AccessError(self.env._(
            'APPROVAL_MATRIX_MISSING: Only a finance manager can maintain the validation matrix.'
        ))

    def _require_company(self, company):
        if self.env.user._is_superuser():
            return
        if company not in self.env.companies:
            raise AccessError(self.env._('COMPANY_ACCESS_DENIED: You cannot use that company policy.'))


class FinanceValidationPolicyLevel(models.Model):
    _name = 'cpla.finance.validation.policy.level'
    _description = 'Finance Validation Policy Level'
    _order = 'level_sequence, id'
    _check_company_auto = True

    policy_id = fields.Many2one(
        'cpla.finance.validation.policy', required=True, index=True, ondelete='restrict',
    )
    company_id = fields.Many2one(related='policy_id.company_id', store=True, index=True)
    name = fields.Char(required=True)
    level_sequence = fields.Integer(required=True, default=1)
    authority_group = fields.Selection(
        selection=[
            ('finance_reviewer', 'Finance Reviewer'),
            ('finance_manager', 'Finance Manager'),
        ],
        required=True,
    )
    applies_from_exact = fields.Char(
        required=True,
        default='0',
        help='This level is required when the threshold basis is greater than or equal to this amount.',
    )
    has_ceiling = fields.Boolean(
        default=True,
        help='When set, maximum_exact is the highest basis this level can cover. Leave it off only by an explicit company choice.',
    )
    maximum_exact = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        self.env['cpla.finance.validation.policy']._check_policy_editor()
        for vals in vals_list:
            policy = self.env['cpla.finance.validation.policy'].browse(vals.get('policy_id')).exists()
            if len(policy) != 1 or policy.state != 'draft':
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Levels are added on a draft policy only.')
        return super().create(vals_list)

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.env['cpla.finance.validation.policy']._check_policy_editor()
        if any(level.policy_id.state != 'draft' for level in self):
            _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Approved policy levels cannot be edited.')
        if 'policy_id' in vals or 'company_id' in vals:
            _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A level cannot move to another policy.')
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.env['cpla.finance.validation.policy']._check_policy_editor()
        if any(level.policy_id.state != 'draft' for level in self):
            _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Approved policy levels cannot be deleted.')
        return super().unlink()


class FinanceValidation(models.Model):
    """Finance decision on accepted leakage evidence.

    Potential leakage stays on the finding. This record stores only the
    finance decision. It does not create a receivable, a waiver, or a payment.
    """

    _name = 'cpla.finance.validation'
    _description = 'Finance Validation'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This finance validation reference already exists.',
    )
    _open_case_unique = models.UniqueIndex(
        "(case_id) WHERE state IN ('draft', 'submitted', 'under_finance_review', "
        "'additional_evidence_required', 'proposed_decision', 'pending_approval', "
        "'stale_source_review_required')",
        'An open finance validation already exists for this case.',
    )
    _current_decision_unique = models.UniqueIndex(
        "(case_id) WHERE is_current IS TRUE AND state IN ('approved', 'partially_approved', 'rejected')",
        'This case already has a current finance decision.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    case_id = fields.Many2one('cpla.leakage.case', required=True, index=True, readonly=True, ondelete='restrict')
    partner_id = fields.Many2one('res.partner', readonly=True, index=True)
    submission_id = fields.Many2one('cpla.leakage.case.submission', readonly=True, ondelete='restrict')
    state = fields.Selection(selection=STATES, required=True, default='draft', readonly=True, index=True, copy=False)
    decision_type = fields.Selection(
        selection=DECISION_TYPES, required=True, default='unset', readonly=True, copy=False,
    )
    requested_by_id = fields.Many2one('res.users', readonly=True, index=True, copy=False)
    requested_at = fields.Datetime(readonly=True, copy=False)
    reviewer_id = fields.Many2one('res.users', readonly=True, index=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)
    policy_id = fields.Many2one('cpla.finance.validation.policy', readonly=True, index=True, ondelete='restrict')
    policy_reference = fields.Char(readonly=True)
    policy_snapshot = fields.Text(readonly=True)
    review_currency_id = fields.Many2one('res.currency', readonly=True)
    fx_rate_exact = fields.Char(readonly=True, help='Recorded only when a user supplies a rate. No rate is invented.')
    fx_rate_date = fields.Date(readonly=True)
    fx_rate_note = fields.Char(readonly=True)
    accepted_potential_exact = fields.Char(readonly=True)
    proposed_validated_exact = fields.Char(readonly=True)
    proposed_rejected_exact = fields.Char(readonly=True)
    proposed_unresolved_exact = fields.Char(readonly=True)
    validated_exact = fields.Char(readonly=True)
    rejected_exact = fields.Char(readonly=True)
    unresolved_exact = fields.Char(readonly=True)
    evidence_completeness = fields.Selection(
        selection=[
            ('incomplete', 'Incomplete'),
            ('complete', 'Complete'),
            ('review_required', 'Review required'),
        ],
        required=True,
        default='incomplete',
        readonly=True,
        copy=False,
    )
    decision_reason = fields.Text(readonly=True, copy=False)
    decision_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    decision_at = fields.Datetime(readonly=True, copy=False)
    approval_level_done = fields.Integer(readonly=True, default=0, copy=False)
    next_level_sequence = fields.Integer(readonly=True, copy=False)
    required_level_count = fields.Integer(readonly=True, default=0, copy=False)
    stale_source = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    is_current = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    level_denied = fields.Boolean(readonly=True, default=False, copy=False)
    missing_evidence_note = fields.Text(readonly=True, copy=False)
    submission_snapshot = fields.Text(readonly=True, copy=False)
    supersedes_id = fields.Many2one('cpla.finance.validation', readonly=True, index=True, copy=False)
    superseded_by_id = fields.Many2one('cpla.finance.validation', readonly=True, index=True, copy=False)
    creates_customer_receivable = fields.Boolean(readonly=True, default=False)
    proves_cash_collection = fields.Boolean(readonly=True, default=False)
    is_waiver = fields.Boolean(readonly=True, default=False)
    is_recovery_billed = fields.Boolean(readonly=True, default=False)
    is_cash_recovered = fields.Boolean(readonly=True, default=False)
    line_ids = fields.One2many('cpla.finance.validation.line', 'validation_id')
    approval_ids = fields.One2many('cpla.finance.validation.approval', 'validation_id')

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(
            self.env,
            'FINANCE_SOURCE_NOT_READY',
            'A finance validation is prepared from a case. Client amounts and approval flags are ignored.',
        )

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(
            self.env,
            'HISTORICAL_APPROVAL_PROTECTED',
            'Finance validation amounts are changed only by a finance action.',
        )

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.check_access('unlink')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A finance validation cannot be deleted.')

    def export_data(self, fields_to_export):
        user = self.env.user
        if user.share or not user.active:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A public user cannot export a finance validation.')
        allowed = (
            _in_group(self.env, user, REVIEWER_GROUP)
            or _in_group(self.env, user, FINANCE_MANAGER_GROUP)
            or _in_group(self.env, user, AUDITOR_GROUP)
        )
        if not allowed:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'You cannot export a finance validation.')
        self.check_access('read')
        return super().export_data(fields_to_export)

    @api.model
    def prepare_from_case(self, case_id):
        """Open a draft. The draft validated amount is not an approved total."""
        self._check_finance_actor()
        case = self.env['cpla.leakage.case'].browse(case_id).exists()
        if len(case) != 1:
            _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Choose one investigation case.')
        case.check_access('read')
        self._require_company(case.company_id)
        self._assert_case_ready(case)
        open_request = self.search([
            ('case_id', '=', case.id),
            ('state', 'in', list(OPEN_STATES)),
        ], limit=1)
        if open_request:
            _fail(self.env, 'DUPLICATE_VALIDATION_REQUEST', 'This case already has an open finance validation.')
        current = self.search([
            ('case_id', '=', case.id),
            ('is_current', '=', True),
            ('state', 'in', list(FINAL_STATES)),
        ], limit=1)
        if current:
            _fail(
                self.env,
                'DUPLICATE_VALIDATION_REQUEST',
                'This case already has a current finance decision. Correct it with a new revision.',
            )
        lines = self._line_commands(case)
        if not lines:
            _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'The case has no current finding to review.')
        currencies = {line['currency_id'] for line in lines}
        if len(currencies) != 1:
            _fail(
                self.env,
                'CURRENCY_BASIS_REVIEW_REQUIRED',
                'Findings in different currencies were not added together.',
            )
        reference = self.env['ir.sequence'].with_company(case.company_id).next_by_code(VALIDATION_SEQUENCE)
        if not reference:
            _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'The finance validation sequence is missing.')
        submission = case.submission_ids.sorted('id')[-1:]
        potential = self._sum(line['potential_exact'] for line in lines)
        try:
            with self.env.cr.savepoint():
                record = models.Model.create(self, [{
                    'reference': reference,
                    'company_id': case.company_id.id,
                    'case_id': case.id,
                    'partner_id': case.partner_id.id,
                    'submission_id': submission.id,
                    'state': 'draft',
                    'decision_type': 'unset',
                    'review_currency_id': next(iter(currencies)),
                    'accepted_potential_exact': _text(potential),
                    'proposed_validated_exact': '0',
                    'proposed_rejected_exact': '0',
                    'proposed_unresolved_exact': _text(potential),
                    'validated_exact': '0',
                    'rejected_exact': '0',
                    'unresolved_exact': '0',
                    'evidence_completeness': 'incomplete',
                    'stale_source': False,
                    'is_current': False,
                    'creates_customer_receivable': False,
                    'proves_cash_collection': False,
                    'is_waiver': False,
                    'is_recovery_billed': False,
                    'is_cash_recovered': False,
                    'submission_snapshot': self._snapshot_text(case, lines, submission),
                }])
                for line in lines:
                    line['validation_id'] = record.id
                    models.Model.create(self.env['cpla.finance.validation.line'], [line])
        except IntegrityError as error:
            _fail(self.env, 'DUPLICATE_VALIDATION_REQUEST', 'This case already has an open finance validation.')
            raise error
        return record

    def action_submit(self):
        """Send the draft for review. This does not approve the amount."""
        self._check_finance_actor()
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            if record.state != 'draft':
                _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Submit a draft finance validation.')
            record._assert_case_ready(record.case_id)
            record._assert_lines_fresh()
            policy = self.env['cpla.finance.validation.policy'].current_for(record.company_id)
            if not policy:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'Approve a finance validation policy before submission.')
            record._assert_same_currency(policy)
            models.Model.write(record, {
                'state': 'submitted',
                'requested_by_id': self.env.user.id,
                'requested_at': fields.Datetime.now(),
                'policy_id': policy.id,
                'policy_reference': policy.reference,
                'evidence_completeness': 'complete',
                'validated_exact': '0',
                'rejected_exact': '0',
                'unresolved_exact': '0',
                'decision_type': 'unset',
                'decision_by_id': False,
                'decision_at': False,
            })
            record._log_case('Finance review requested. This is not a finance-validated amount.')
        return True

    def action_start_review(self):
        self._check_finance_actor()
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            if record.state != 'submitted':
                _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Review starts from a submitted request.')
            record._assert_lines_fresh()
            models.Model.write(record, {
                'state': 'under_finance_review',
                'reviewer_id': self.env.user.id,
                'reviewed_at': fields.Datetime.now(),
            })
        return True

    def action_request_evidence(self, reason, required_action):
        if not (reason or '').strip() or not (required_action or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'An evidence request needs a reason and the required action.')
        self._check_finance_actor()
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            if record.state not in ('submitted', 'under_finance_review', 'proposed_decision'):
                _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Evidence can be requested during review, before approval.')
            record.case_id.action_return_for_rework(str(reason).strip(), str(required_action).strip())
            models.Model.write(record, {
                'state': 'additional_evidence_required',
                'evidence_completeness': 'incomplete',
                'missing_evidence_note': str(reason).strip(),
                'decision_type': 'unset',
                'validated_exact': '0',
            })
            record._event('evidence_requested', str(reason).strip(), amount='0')
        return True

    def action_propose(self, decisions):
        """Store a proposal. Approved totals stay at zero until the matrix is complete."""
        self._check_finance_actor()
        if not isinstance(decisions, (list, tuple)):
            _fail(self.env, 'INVALID_VALIDATION_AMOUNT', 'The proposal must list one decision per finding.')
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            if record.state not in ('under_finance_review', 'proposed_decision'):
                _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Propose a decision during finance review.')
            record._assert_lines_fresh()
            by_id = {}
            for item in decisions:
                if not isinstance(item, dict) or not item.get('line_id'):
                    _fail(self.env, 'INVALID_VALIDATION_AMOUNT', 'Each finding decision needs a line.')
                by_id[int(item['line_id'])] = item
            if set(by_id) != set(record.line_ids.ids):
                _fail(self.env, 'INVALID_VALIDATION_AMOUNT', 'Every finding on this request needs its own decision.')
            policy = record.policy_id
            if not policy or not policy.is_current:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The approval policy is no longer current.')
            proposed_v = ZERO
            proposed_r = ZERO
            proposed_u = ZERO
            kinds = set()
            for line in record.line_ids:
                item = by_id[line.id]
                parsed = record._parse_line_decision(line, item, policy)
                kinds.add(parsed['decision_type'])
                proposed_v = _arithmetic('add', proposed_v, parsed['validated'])
                proposed_r = _arithmetic('add', proposed_r, parsed['rejected'])
                proposed_u = _arithmetic('add', proposed_u, parsed['unresolved'])
                models.Model.write(line, {
                    'proposed_validated_exact': _text(parsed['validated']),
                    'proposed_rejected_exact': _text(parsed['rejected']),
                    'proposed_unresolved_exact': _text(parsed['unresolved']),
                    'approved_validated_exact': '0',
                    'approved_rejected_exact': '0',
                    'approved_unresolved_exact': '0',
                    'decision_type': parsed['decision_type'],
                    'reason_code': parsed['reason_code'],
                    'explanation': parsed['explanation'],
                    'counts_current': False,
                })
            header_type = record._header_type(proposed_v, proposed_r, proposed_u, kinds)
            models.Model.write(record, {
                'state': 'proposed_decision',
                'decision_type': header_type,
                'proposed_validated_exact': _text(proposed_v),
                'proposed_rejected_exact': _text(proposed_r),
                'proposed_unresolved_exact': _text(proposed_u),
                'validated_exact': '0',
                'rejected_exact': '0',
                'unresolved_exact': '0',
                'decision_by_id': False,
                'decision_at': False,
                'approval_level_done': 0,
                'level_denied': False,
            })
        return True

    def action_request_approval(self):
        self._check_finance_actor()
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            if record.state != 'proposed_decision':
                _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Request approval from a proposed decision.')
            record._assert_lines_fresh()
            if record.decision_type == 'unset':
                _fail(self.env, 'EVIDENCE_INCOMPLETE', 'The proposal does not decide the accepted potential.')
            if any(line.reason_code == 'ADDITIONAL_EVIDENCE_REQUIRED' for line in record.line_ids):
                _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Additional evidence is still required. Do not approve this package.')
            basis = record._threshold_amount()
            levels = record.policy_id._required_levels(basis)
            models.Model.write(record, {
                'state': 'pending_approval',
                'required_level_count': len(levels),
                'approval_level_done': 0,
                'next_level_sequence': levels[0].level_sequence,
                'policy_snapshot': record._policy_snapshot(levels),
                'validated_exact': '0',
            })
        return True

    def action_approve(self, reason):
        """Approve the next required level. A retry does not add a second amount."""
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Approval needs a reason.')
        self._check_finance_actor()
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            user = self.env.user
            if record.state in FINAL_STATES and record.decision_by_id:
                if record.approval_ids.filtered(lambda event: event.decision == 'approved' and event.actor_id == user):
                    continue
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'This finance decision is already recorded.')
            if record.state != 'pending_approval':
                _fail(self.env, 'APPROVAL_LEVEL_PENDING', 'Approve only a request that is pending approval.')
            try:
                record._assert_lines_fresh()
            except UserError:
                record._mark_in_progress_stale()
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The source changed. The old amount was not approved.')
            if record.stale_source or record.case_id.finance_package_stale:
                record._mark_in_progress_stale()
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The finance package is stale. The old amount was not approved.')
            basis = record._threshold_amount()
            levels = record.policy_id._required_levels(basis)
            done = record.approval_ids.filtered(lambda event: event.decision == 'approved')
            if len(done) >= len(levels):
                continue
            level = levels[len(done)]
            if level.level_sequence != record.next_level_sequence:
                _fail(self.env, 'APPROVAL_LEVEL_PENDING', 'The next approval level cannot be skipped.')
            record._assert_level_actor(user, level, done)
            if record.approval_ids.filtered(lambda event: event.level_sequence == level.level_sequence and event.decision == 'approved'):
                continue
            try:
                with self.env.cr.savepoint():
                    record._create_event(level, 'approved', str(reason).strip(), record.proposed_validated_exact)
                    if len(done) + 1 < len(levels):
                        nxt = levels[len(done) + 1]
                        models.Model.write(record, {
                            'approval_level_done': len(done) + 1,
                            'next_level_sequence': nxt.level_sequence,
                            'state': 'pending_approval',
                        })
                    else:
                        record._finalize(str(reason).strip(), user)
            except IntegrityError:
                record.invalidate_recordset()
                if record.state in FINAL_STATES:
                    continue
                _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'Another approval was recorded for this level.')
        return True

    def action_deny_level(self, reason):
        """Refuse the proposal at this level. This does not classify the potential as a waiver."""
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A denial needs a reason.')
        self._check_finance_actor()
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            if record.state != 'pending_approval':
                _fail(self.env, 'APPROVAL_LEVEL_PENDING', 'Deny a level only while approval is pending.')
            basis = record._threshold_amount()
            levels = record.policy_id._required_levels(basis)
            done = record.approval_ids.filtered(lambda event: event.decision == 'approved')
            if len(done) >= len(levels):
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'The required levels are already complete.')
            level = levels[len(done)]
            record._assert_level_actor(self.env.user, level, done)
            record._create_event(level, 'denied', str(reason).strip(), '0')
            models.Model.write(record, {
                'state': 'rejected',
                'level_denied': True,
                'is_current': True,
                'decision_reason': str(reason).strip(),
                'decision_by_id': self.env.user.id,
                'decision_at': fields.Datetime.now(),
                'validated_exact': '0',
                'rejected_exact': '0',
                'unresolved_exact': '0',
                'approval_level_done': len(done),
            })
            record._log_case('A finance approver denied this proposal. No validated amount was recorded.')
        return True

    def action_mark_stale(self):
        for record in self:
            record._flag_one()
        return True

    def action_retire_stale_package(self):
        """Close an unapproved stale package so a refreshed request can be prepared."""
        self._check_finance_actor()
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            if record.state != 'stale_source_review_required':
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'Only a stale unapproved package can be retired.')
            if _decimal(record.validated_exact) not in (None, ZERO):
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An approved amount cannot be retired in place.')
            models.Model.write(record, {
                'state': 'superseded',
                'is_current': False,
                'stale_source': True,
            })
        return True

    def action_create_correction(self, reason):
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A correction needs a reason.')
        self._check_finance_actor()
        self.ensure_one()
        self.lock_for_update()
        self._require_company(self.company_id)
        if self.state not in FINAL_STATES:
            _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Correct a recorded finance decision.')
        if self.superseded_by_id:
            _fail(self.env, 'DUPLICATE_VALIDATION_REQUEST', 'A later revision already exists.')
        open_request = self.search([
            ('case_id', '=', self.case_id.id),
            ('state', 'in', list(OPEN_STATES)),
        ], limit=1)
        if open_request:
            _fail(self.env, 'DUPLICATE_VALIDATION_REQUEST', 'Finish or retire the open finance validation first.')
        reference = self.env['ir.sequence'].with_company(self.company_id).next_by_code(VALIDATION_SEQUENCE)
        if not reference:
            _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'The finance validation sequence is missing.')
        revision = models.Model.create(self, [{
            'reference': reference,
            'company_id': self.company_id.id,
            'case_id': self.case_id.id,
            'partner_id': self.partner_id.id,
            'submission_id': self.submission_id.id,
            'state': 'draft',
            'decision_type': 'unset',
            'review_currency_id': self.review_currency_id.id,
            'accepted_potential_exact': self.accepted_potential_exact,
            'proposed_validated_exact': '0',
            'proposed_rejected_exact': '0',
            'proposed_unresolved_exact': self.accepted_potential_exact,
            'validated_exact': '0',
            'rejected_exact': '0',
            'unresolved_exact': '0',
            'evidence_completeness': 'incomplete',
            'supersedes_id': self.id,
            'is_current': False,
            'stale_source': False,
            'creates_customer_receivable': False,
            'proves_cash_collection': False,
            'is_waiver': False,
            'is_recovery_billed': False,
            'is_cash_recovered': False,
            'decision_reason': str(reason).strip(),
        }])
        for line in self.line_ids:
            fresh = self._fresh_line_source(line)
            models.Model.create(self.env['cpla.finance.validation.line'], [{
                'validation_id': revision.id,
                'company_id': line.company_id.id,
                'finding_id': fresh['finding'].id,
                'result_id': fresh['result'].id,
                'membership_id': line.membership_id.id,
                'finding_identity': fresh['finding'].current_identity,
                'source_fingerprint': fresh['finding'].input_fingerprint,
                'source_revision': fresh['finding'].source_revision,
                'version_id': fresh['finding'].version_id.id,
                'product_id': fresh['finding'].product_id.id,
                'move_line_id': fresh['finding'].move_line_id.id,
                'allocation_id': fresh['finding'].allocation_id.id,
                'potential_exact': fresh['finding'].potential_leakage_exact,
                'currency_id': fresh['finding'].currency_id.id,
                'proposed_validated_exact': '0',
                'proposed_rejected_exact': '0',
                'proposed_unresolved_exact': fresh['finding'].potential_leakage_exact,
                'approved_validated_exact': '0',
                'approved_rejected_exact': '0',
                'approved_unresolved_exact': '0',
                'decision_type': 'unset',
                'counts_current': False,
            }])
        potential = self._sum(line.potential_exact for line in revision.line_ids)
        models.Model.write(revision, {
            'accepted_potential_exact': _text(potential),
            'proposed_unresolved_exact': _text(potential),
        })
        return revision

    def action_set_review_rate(self, rate_exact, rate_date, note):
        """Store a rate the user supplied. This does not look up or invent a rate."""
        self._check_finance_actor()
        rate = _decimal(rate_exact)
        if rate is None or rate <= ZERO:
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The review rate must be a positive recorded rate.')
        if not rate_date or not (note or '').strip():
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The review rate needs a date and a note.')
        for record in self:
            record._require_company(record.company_id)
            if record.state not in ('draft', 'submitted', 'under_finance_review'):
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'The review rate cannot change after the proposal.')
            models.Model.write(record, {
                'fx_rate_exact': _text(rate),
                'fx_rate_date': rate_date,
                'fx_rate_note': str(note).strip(),
            })
        return True

    def decision_payload(self):
        """Current decision for a later recovery phase. This does not authorize billing."""
        self.ensure_one()
        self.check_access('read')
        self._require_company(self.company_id)
        current = bool(
            self.is_current
            and not self.stale_source
            and self.state in ('approved', 'partially_approved')
            and not self.level_denied
        )
        validated = self.validated_exact if self.state in ('approved', 'partially_approved') and not self.level_denied else '0'
        rejected = self.rejected_exact if self.state in ('approved', 'partially_approved', 'rejected') and not self.level_denied else '0'
        unresolved = self.unresolved_exact if self.state in ('approved', 'partially_approved') and not self.level_denied else '0'
        return {
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'case_id': self.case_id.id,
            'reference': self.reference,
            'finding_ids': self.line_ids.mapped('finding_id').ids,
            'result_ids': self.line_ids.mapped('result_id').ids,
            'state': self.state,
            'decision_type': self.decision_type,
            'approved_amount': validated or '0',
            'rejected_amount': rejected or '0',
            'unresolved_amount': unresolved or '0',
            'currency_id': self.review_currency_id.id,
            'approval_levels_done': self.approval_level_done,
            'approval_levels_required': self.required_level_count,
            'approval_complete': self.state in ('approved', 'partially_approved') and not self.level_denied and not self.stale_source and self.is_current,
            'policy_reference': self.policy_reference or '',
            'decision_at': self.decision_at,
            'decision_by_id': self.decision_by_id.id,
            'current': current,
            'stale_source': self.stale_source,
            'evidence_completeness': self.evidence_completeness,
            'reason': self.decision_reason or '',
            'supersedes_id': self.supersedes_id.id,
            'superseded_by_id': self.superseded_by_id.id,
            'recovery_authority': False,
            'creates_customer_receivable': False,
            'proves_cash_collection': False,
            'is_waiver': False,
            'is_recovery_billed': False,
            'is_cash_recovered': False,
        }

    @api.model
    def current_validated_amount(self, company, partner=None):
        """Sum of current non-stale validated lines in one company. Drafts are excluded."""
        if not company:
            return '0'
        if not (self.env.user._is_superuser()) and company not in self.env.companies:
            raise AccessError(self.env._('COMPANY_ACCESS_DENIED: You cannot read that company total.'))
        domain = [
            ('company_id', '=', company.id),
            ('counts_current', '=', True),
        ]
        if partner:
            domain.append(('validation_id.partner_id', '=', partner.id))
        lines = self.env['cpla.finance.validation.line'].search(domain)
        seen = set()
        total = ZERO
        for line in lines:
            if line.validation_id.stale_source or not line.validation_id.is_current:
                continue
            if line.validation_id.state not in ('approved', 'partially_approved'):
                continue
            identity = line.finding_identity or str(line.finding_id.id)
            if identity in seen:
                continue
            seen.add(identity)
            amount = _decimal(line.approved_validated_exact)
            if amount is None:
                continue
            total = _arithmetic('add', total, amount)
        return _text(total)

    @api.model
    def _flag_source_change(self, findings):
        """Preserve an approved decision and stop an in-progress approval of the old basis."""
        if not findings:
            return
        lines = self.env['cpla.finance.validation.line'].search([
            ('finding_id', 'in', findings.ids),
        ])
        for record in lines.validation_id:
            record._flag_one()

    def _flag_one(self):
        self.ensure_one()
        if self.state == 'superseded':
            return
        if self.state in ('approved', 'partially_approved', 'rejected') and self.decision_by_id:
            models.Model.write(self, {
                'stale_source': True,
                'is_current': False,
            })
            models.Model.write(self.line_ids, {'counts_current': False})
            self._flag_recovery_authority()
            return
        if self.state in OPEN_STATES and self.state != 'stale_source_review_required':
            models.Model.write(self, {
                'state': 'stale_source_review_required',
                'stale_source': True,
                'is_current': False,
                'evidence_completeness': 'review_required',
            })
            self._flag_recovery_authority()

    def _mark_in_progress_stale(self):
        self.ensure_one()
        if self.state in OPEN_STATES:
            models.Model.write(self, {
                'state': 'stale_source_review_required',
                'stale_source': True,
                'is_current': False,
                'evidence_completeness': 'review_required',
            })

    def _flag_recovery_authority(self):
        if 'cpla.recovery.request' in self.env.registry:
            self.env['cpla.recovery.request']._flag_finance_source(self)

    def action_prepare_recovery_request(self):
        """Open a commercial draft. This does not approve recovery or create an invoice."""
        self.ensure_one()
        self.check_access('read')
        request = self.env['cpla.recovery.request'].prepare_from_validation(self.id)
        return request.action_open_form()

    def action_open_case(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cpla.leakage.case',
            'res_id': self.case_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_findings(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Source findings'),
            'res_model': 'cpla.leakage.finding',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.line_ids.mapped('finding_id').ids)],
            'target': 'current',
        }

    def action_open_wizard(self, operation):
        self.ensure_one()
        self.check_access('read')
        self._check_finance_actor()
        line = self.line_ids[:1]
        wizard = self.env['cpla.finance.validation.wizard'].create({
            'validation_id': self.id,
            'company_id': self.company_id.id,
            'line_id': line.id,
            'operation': operation,
            'validated_exact': line.potential_exact or '0',
            'rejected_exact': '0',
            'unresolved_exact': '0',
            'reason_code': 'FULLY_SUPPORTED',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Finance decision'),
            'res_model': 'cpla.finance.validation.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_evidence_wizard(self):
        return self.action_open_wizard('evidence')

    def action_open_propose_wizard(self):
        return self.action_open_wizard('propose')

    def action_open_approve_wizard(self):
        return self.action_open_wizard('approve')

    def action_open_deny_wizard(self):
        return self.action_open_wizard('deny')

    def action_open_correction_wizard(self):
        return self.action_open_wizard('correct')

    def _finalize(self, reason, user):
        self.ensure_one()
        validated = _decimal(self.proposed_validated_exact) or ZERO
        rejected = _decimal(self.proposed_rejected_exact) or ZERO
        unresolved = _decimal(self.proposed_unresolved_exact) or ZERO
        for line in self.line_ids:
            models.Model.write(line, {
                'approved_validated_exact': line.proposed_validated_exact,
                'approved_rejected_exact': line.proposed_rejected_exact,
                'approved_unresolved_exact': line.proposed_unresolved_exact,
                'counts_current': self.decision_type in ('full_validation', 'partial_validation') and (_decimal(line.proposed_validated_exact) or ZERO) >= ZERO,
                'decision_by_id': user.id,
                'decision_at': fields.Datetime.now(),
            })
        state = {
            'full_validation': 'approved',
            'partial_validation': 'partially_approved',
            'full_rejection': 'rejected',
        }.get(self.decision_type)
        if not state:
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'This proposal cannot be finalized.')
        if self.supersedes_id and self.supersedes_id.is_current:
            models.Model.write(self.supersedes_id, {
                'is_current': False,
                'state': 'superseded',
                'superseded_by_id': self.id,
            })
            models.Model.write(self.supersedes_id.line_ids, {'counts_current': False})
        models.Model.write(self, {
            'state': state,
            'is_current': True,
            'stale_source': False,
            'level_denied': False,
            'validated_exact': _text(validated),
            'rejected_exact': _text(rejected),
            'unresolved_exact': _text(unresolved),
            'decision_reason': reason,
            'decision_by_id': user.id,
            'decision_at': fields.Datetime.now(),
            'approval_level_done': self.required_level_count,
            'creates_customer_receivable': False,
            'proves_cash_collection': False,
            'is_waiver': False,
            'is_recovery_billed': False,
            'is_cash_recovered': False,
        })
        if self.decision_type in ('full_validation', 'partial_validation'):
            models.Model.write(self.line_ids, {'counts_current': True})
            models.Model.write(self.line_ids.filtered(
                lambda line: (_decimal(line.approved_validated_exact) or ZERO) == ZERO
                and self.decision_type == 'full_rejection'
            ), {'counts_current': False})
        else:
            models.Model.write(self.line_ids, {'counts_current': False})
        self._log_case('Finance decision recorded. It is not a receivable, a waiver, or collected cash.')

    def _create_event(self, level, decision, reason, amount):
        self.ensure_one()
        models.Model.create(self.env['cpla.finance.validation.approval'], [{
            'validation_id': self.id,
            'company_id': self.company_id.id,
            'policy_id': self.policy_id.id,
            'policy_reference': self.policy_id.reference,
            'level_sequence': level.level_sequence,
            'authority_group': level.authority_group,
            'decision': decision,
            'amount_exact': amount or '0',
            'currency_id': self.review_currency_id.id,
            'actor_id': self.env.user.id,
            'acted_at': fields.Datetime.now(),
            'reason': reason,
            'source_fingerprint': ','.join(self.line_ids.mapped('source_fingerprint')),
            'evidence_snapshot': self.submission_snapshot or '',
        }])

    def _event(self, decision, reason, amount):
        self.ensure_one()
        models.Model.create(self.env['cpla.finance.validation.approval'], [{
            'validation_id': self.id,
            'company_id': self.company_id.id,
            'policy_id': self.policy_id.id,
            'policy_reference': self.policy_reference or '',
            'level_sequence': 0,
            'authority_group': 'finance_reviewer',
            'decision': decision,
            'amount_exact': amount or '0',
            'currency_id': self.review_currency_id.id,
            'actor_id': self.env.user.id,
            'acted_at': fields.Datetime.now(),
            'reason': reason,
            'source_fingerprint': ','.join(self.line_ids.mapped('source_fingerprint')),
            'evidence_snapshot': self.missing_evidence_note or '',
        }])

    def _assert_level_actor(self, user, level, done):
        self.ensure_one()
        xmlid = AUTHORITY_GROUPS.get(level.authority_group)
        if not xmlid or not _in_group(self.env, user, xmlid):
            if user._is_superuser() or _in_group(self.env, user, APP_ADMIN_GROUP):
                raise AccessError(self.env._(
                    'APPROVAL_MATRIX_MISSING: A technical administrator is not a finance approver.'
                ))
            raise AccessError(self.env._(
                'APPROVAL_LIMIT_EXCEEDED: You are not the approver for this level.'
            ))
        policy = self.policy_id
        if policy.four_eyes_required:
            if user == self.requested_by_id or user == self.case_id.submitted_by_id:
                raise AccessError(self.env._(
                    'SELF_APPROVAL_PROHIBITED: The requester cannot approve this finance validation.'
                ))
            if user in done.mapped('actor_id'):
                raise AccessError(self.env._(
                    'SELF_APPROVAL_PROHIBITED: One user cannot complete two approval levels.'
                ))

    def _threshold_amount(self):
        self.ensure_one()
        potential = _decimal(self.accepted_potential_exact) or ZERO
        validated = _decimal(self.proposed_validated_exact) or ZERO
        rejected = _decimal(self.proposed_rejected_exact) or ZERO
        unresolved = _decimal(self.proposed_unresolved_exact) or ZERO
        basis = self.policy_id.threshold_basis
        if basis == 'validated_amount':
            amount = validated
        elif basis == 'proposed_adjustment':
            amount = _arithmetic('add', rejected, unresolved)
        elif basis == 'customer_open_validated':
            existing = _decimal(self.current_validated_amount(self.company_id, self.partner_id)) or ZERO
            amount = _arithmetic('add', existing, validated)
        else:
            amount = potential
        return self._amount_in_policy_currency(amount)

    def _amount_in_policy_currency(self, amount):
        self.ensure_one()
        policy_currency = self.policy_id.currency_id
        review_currency = self.review_currency_id
        if not policy_currency or not review_currency:
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The approval currency is missing.')
        if policy_currency == review_currency:
            return amount
        rate = _decimal(self.fx_rate_exact)
        if rate is None or rate <= ZERO or not self.fx_rate_date:
            _fail(
                self.env,
                'CURRENCY_BASIS_REVIEW_REQUIRED',
                'The review currency and the policy currency differ. No raw total was compared with the limit.',
            )
        return _arithmetic('mul', amount, rate)

    def _assert_same_currency(self, policy):
        self.ensure_one()
        currencies = set(self.line_ids.mapped('currency_id').ids)
        review_id = self.review_currency_id.id
        if len(currencies) != 1 or (review_id and currencies != {review_id}):
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'Findings in different currencies were not added together.')
        if policy.currency_id != self.review_currency_id and not _decimal(self.fx_rate_exact):
            _fail(
                self.env,
                'CURRENCY_BASIS_REVIEW_REQUIRED',
                'Record a review rate before comparing this amount with the policy currency.',
            )

    def _parse_line_decision(self, line, item, policy):
        potential = _decimal(line.potential_exact)
        validated = _decimal(item.get('validated'))
        rejected = _decimal(item.get('rejected'))
        unresolved = _decimal(item.get('unresolved'))
        if None in (potential, validated, rejected, unresolved):
            _fail(self.env, 'INVALID_VALIDATION_AMOUNT', 'Each amount must be a number.')
        if potential < ZERO or validated < ZERO or rejected < ZERO or unresolved < ZERO:
            _fail(self.env, 'INVALID_VALIDATION_AMOUNT', 'A finance amount cannot be negative.')
        currency = line.currency_id
        q_potential = _quantize(potential, currency)
        q_validated = _quantize(validated, currency)
        q_rejected = _quantize(rejected, currency)
        q_unresolved = _quantize(unresolved, currency)
        if q_validated > q_potential or q_rejected > q_potential:
            _fail(
                self.env,
                'VALIDATION_EXCEEDS_POTENTIAL',
                'The validated amount is above the accepted potential. Request a DEV-14 reassessment.',
            )
        if _quantize(_arithmetic('add', q_validated, q_rejected), currency) > q_potential:
            _fail(self.env, 'VALIDATION_EXCEEDS_POTENTIAL', 'Validated and rejected amounts exceed the accepted potential.')
        total = _arithmetic('add', _arithmetic('add', q_validated, q_rejected), q_unresolved)
        if _quantize(total, currency) != q_potential:
            _fail(
                self.env,
                'INVALID_VALIDATION_AMOUNT',
                'Accepted potential must equal validated plus rejected plus unresolved.',
            )
        reason = item.get('reason_code')
        if reason not in dict(REASON_CODES):
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Choose a finance reason code.')
        explanation = (item.get('explanation') or '').strip()
        material = q_validated != q_potential or q_rejected > ZERO or q_unresolved > ZERO
        if material and len(explanation) < 8:
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Explain a partial, rejected, or unresolved amount.')
        if q_rejected > ZERO and reason == 'FULLY_SUPPORTED':
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A rejected amount needs its own reason.')
        if reason == 'AUTHORIZED_DISCOUNT_CONFIRMED':
            self._assert_discount_evidence(line)
        if not policy.partial_validation_allowed and (q_unresolved > ZERO or (q_validated > ZERO and q_validated < q_potential)):
            _fail(
                self.env,
                'INVALID_VALIDATION_AMOUNT',
                'This company policy does not allow a partial finance validation.',
            )
        if q_validated == q_potential and q_rejected == ZERO and q_unresolved == ZERO:
            kind = 'full_validation'
        elif q_validated == ZERO and q_rejected == q_potential and q_unresolved == ZERO:
            kind = 'full_rejection'
        elif q_validated == ZERO and q_rejected == ZERO and q_unresolved == q_potential and q_unresolved > ZERO:
            kind = 'partial_validation'
        elif q_validated == ZERO and q_rejected == ZERO:
            kind = 'unset'
        else:
            kind = 'partial_validation'
        if kind == 'unset':
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Leave no finding without a validated, rejected, or unresolved amount.')
        return {
            'validated': q_validated,
            'rejected': q_rejected,
            'unresolved': q_unresolved,
            'decision_type': kind,
            'reason_code': reason,
            'explanation': explanation,
        }

    def _assert_discount_evidence(self, line):
        approval = self.env['cpla.discount.approval'].search([
            ('company_id', '=', line.company_id.id),
            ('version_id', '=', line.version_id.id),
            ('product_id', '=', line.product_id.id),
            ('state', '=', 'approved'),
        ], limit=1)
        if not approval:
            _fail(
                self.env,
                'APPROVAL_EVIDENCE_MISSING',
                'An authorized-discount reason needs an approved discount record. The amount was not reduced automatically.',
            )

    def _header_type(self, validated, rejected, unresolved, kinds):
        if 'unset' in kinds:
            return 'unset'
        potential = _decimal(self.accepted_potential_exact) or ZERO
        if validated == potential and rejected == ZERO and unresolved == ZERO:
            return 'full_validation'
        if validated == ZERO and rejected == potential and unresolved == ZERO:
            return 'full_rejection'
        if validated > ZERO or rejected > ZERO:
            return 'partial_validation'
        return 'unset'

    def _assert_case_ready(self, case):
        if case.state != 'ready_for_finance_review':
            _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'The investigation case is not ready for finance review.')
        if case.finance_package_stale or case.source_reassessment_required or case.reinvestigation_required:
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The case source is stale or still under reassessment.')
        if case.company_id != case.partner_id.company_id and case.partner_id.company_id:
            if case.partner_id.company_id != case.company_id:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The customer company does not match the case.')
        if not case.exposure_comparable or _decimal(case.current_potential_exposure_exact) is None:
            _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'The case exposure is not a comparable amount.')

    def _assert_lines_fresh(self):
        self.ensure_one()
        if not self.line_ids:
            _fail(self.env, 'ACCEPTED_AUDIT_REVISION_MISSING', 'The finance validation has no source lines.')
        for line in self.line_ids:
            finding = line.finding_id
            if finding.company_id != self.company_id:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A finding from another company cannot be validated here.')
            if not finding.is_current or finding.finding_status != 'potential':
                _fail(self.env, 'SOURCE_REVISION_CHANGED', 'The finding is no longer the current potential.')
            if finding.revision_verification not in ACCEPTABLE_REVISION:
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The accepted audit revision is not current.')
            if (finding.input_fingerprint or '') != (line.source_fingerprint or ''):
                _fail(self.env, 'SOURCE_REVISION_CHANGED', 'The source fingerprint changed after this request was prepared.')
            if not line.result_id or line.result_id.company_id != self.company_id:
                _fail(self.env, 'ACCEPTED_AUDIT_REVISION_MISSING', 'The accepted audit result is missing.')
            if not finding.version_id:
                _fail(self.env, 'EVIDENCE_INCOMPLETE', 'The finding has no contract version.')
            if (_decimal(finding.potential_leakage_exact) or ZERO) != (_decimal(line.potential_exact) or ZERO):
                _fail(self.env, 'SOURCE_REVISION_CHANGED', 'The accepted potential changed after this request was prepared.')

    def _line_commands(self, case):
        commands = []
        for membership in case.membership_ids.filtered('is_current'):
            finding = membership.finding_id
            if finding.company_id != case.company_id:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A finding from another company cannot be added.')
            if not finding.is_current or finding.finding_status != 'potential':
                _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Only a current potential finding can be prepared.')
            if finding.revision_verification not in ACCEPTABLE_REVISION:
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The finding revision is not accepted current evidence.')
            if not finding.version_id:
                _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Contract evidence is missing on a finding.')
            result = self.env['cpla.invoice.audit.result'].search([
                ('finding_id', '=', finding.id),
                ('company_id', '=', finding.company_id.id),
            ], order='id desc', limit=1)
            if not result:
                _fail(self.env, 'ACCEPTED_AUDIT_REVISION_MISSING', 'The finding has no audit result.')
            potential = _decimal(finding.potential_leakage_exact)
            if potential is None or potential < ZERO:
                _fail(self.env, 'INVALID_VALIDATION_AMOUNT', 'The accepted potential is not a usable amount.')
            if not finding.currency_id:
                _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The finding has no currency.')
            commands.append({
                'company_id': case.company_id.id,
                'finding_id': finding.id,
                'result_id': result.id,
                'membership_id': membership.id,
                'finding_identity': finding.current_identity or '',
                'source_fingerprint': finding.input_fingerprint or '',
                'source_revision': finding.source_revision or 0,
                'version_id': finding.version_id.id,
                'product_id': finding.product_id.id,
                'move_line_id': finding.move_line_id.id,
                'allocation_id': finding.allocation_id.id,
                'potential_exact': finding.potential_leakage_exact,
                'currency_id': finding.currency_id.id,
                'proposed_validated_exact': '0',
                'proposed_rejected_exact': '0',
                'proposed_unresolved_exact': finding.potential_leakage_exact,
                'approved_validated_exact': '0',
                'approved_rejected_exact': '0',
                'approved_unresolved_exact': '0',
                'decision_type': 'unset',
                'counts_current': False,
            })
        return commands

    def _fresh_line_source(self, line):
        identity = line.finding_identity
        finding = self.env['cpla.leakage.finding'].search([
            ('current_identity', '=', identity),
            ('is_current', '=', True),
            ('company_id', '=', line.company_id.id),
            ('finding_status', '=', 'potential'),
        ], limit=1)
        if not finding:
            finding = line.finding_id if line.finding_id.is_current else self.env['cpla.leakage.finding']
        if not finding:
            _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'No current finding remains for this correction.')
        result = self.env['cpla.invoice.audit.result'].search([
            ('finding_id', '=', finding.id),
            ('company_id', '=', finding.company_id.id),
        ], order='id desc', limit=1)
        if not result:
            _fail(self.env, 'ACCEPTED_AUDIT_REVISION_MISSING', 'The current finding has no audit result.')
        return {'finding': finding, 'result': result}

    def _snapshot_text(self, case, lines, submission):
        payload = {
            'case': case.reference,
            'case_revision': case.case_revision,
            'submission_id': submission.id,
            'potential': case.current_potential_exposure_exact or '',
            'lines': [
                {
                    'finding_id': line['finding_id'],
                    'result_id': line['result_id'],
                    'identity': line['finding_identity'],
                    'fingerprint': line['source_fingerprint'],
                    'potential': line['potential_exact'],
                    'currency_id': line['currency_id'],
                    'version_id': line['version_id'],
                }
                for line in lines
            ],
        }
        return _canonical(payload)

    def _policy_snapshot(self, levels):
        policy = self.policy_id
        payload = {
            'policy_id': policy.id,
            'reference': policy.reference,
            'basis': policy.threshold_basis,
            'currency_id': policy.currency_id.id,
            'partial': policy.partial_validation_allowed,
            'four_eyes': policy.four_eyes_required,
            'levels': [
                {
                    'sequence': level.level_sequence,
                    'group': level.authority_group,
                    'applies_from': level.applies_from_exact,
                    'has_ceiling': level.has_ceiling,
                    'maximum': level.maximum_exact or '',
                }
                for level in levels
            ],
        }
        return _canonical(payload)

    def _log_case(self, reason):
        self.ensure_one()
        case = self.case_id
        if not case:
            return
        case._log(
            case,
            'finance_decision_recorded',
            reason=reason,
            new=self.reference,
            source_model=self._name,
            source_res_id=self.id,
            bump=False,
        )

    @api.model
    def _sum(self, values):
        total = ZERO
        for value in values:
            amount = _decimal(value)
            if amount is None:
                _fail(self.env, 'INVALID_VALIDATION_AMOUNT', 'A source amount is missing.')
            total = _arithmetic('add', total, amount)
        return total

    @api.model
    def _check_finance_actor(self):
        user = self.env.user
        if _in_group(self.env, user, REVIEWER_GROUP) or _in_group(self.env, user, FINANCE_MANAGER_GROUP):
            return
        if user._is_superuser() or _in_group(self.env, user, APP_ADMIN_GROUP) or _in_group(self.env, user, AUDITOR_GROUP):
            raise AccessError(self.env._(
                'APPROVAL_MATRIX_MISSING: A technical administrator is not a finance approver.'
            ))
        raise AccessError(self.env._('COMPANY_ACCESS_DENIED: You cannot act on a finance validation.'))

    def _require_company(self, company):
        if self.env.user._is_superuser():
            return
        if company not in self.env.companies:
            raise AccessError(self.env._('COMPANY_ACCESS_DENIED: You cannot act on that company.'))

    @api.model
    def _require_currency_basis(self, left, right, rate_exact):
        """Refuse a raw comparison of two currencies when no rate was recorded."""
        if not left or not right or left == right:
            return True
        rate = _decimal(rate_exact)
        if rate is None or rate <= ZERO:
            _fail(
                self.env,
                'CURRENCY_BASIS_REVIEW_REQUIRED',
                'Those currencies were not added together.',
            )
        return True


class FinanceValidationLine(models.Model):
    _name = 'cpla.finance.validation.line'
    _description = 'Finance Validation Line'
    _order = 'id'
    _check_company_auto = True

    _current_identity_unique = models.UniqueIndex(
        '(finding_identity, company_id) WHERE counts_current IS TRUE',
        'This finding already has a current finance-validated amount.',
    )

    validation_id = fields.Many2one(
        'cpla.finance.validation', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    finding_id = fields.Many2one('cpla.leakage.finding', required=True, index=True, readonly=True, ondelete='restrict')
    result_id = fields.Many2one('cpla.invoice.audit.result', required=True, readonly=True, ondelete='restrict')
    membership_id = fields.Many2one('cpla.leakage.case.membership', readonly=True, ondelete='restrict')
    finding_identity = fields.Char(readonly=True, index=True)
    source_fingerprint = fields.Char(readonly=True)
    source_revision = fields.Integer(readonly=True)
    version_id = fields.Many2one('cpla.customer.contract.version', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    move_line_id = fields.Many2one('account.move.line', readonly=True)
    allocation_id = fields.Many2one('cpla.invoice.source.allocation', readonly=True)
    potential_exact = fields.Char(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    proposed_validated_exact = fields.Char(readonly=True)
    proposed_rejected_exact = fields.Char(readonly=True)
    proposed_unresolved_exact = fields.Char(readonly=True)
    approved_validated_exact = fields.Char(readonly=True)
    approved_rejected_exact = fields.Char(readonly=True)
    approved_unresolved_exact = fields.Char(readonly=True)
    decision_type = fields.Selection(selection=DECISION_TYPES, readonly=True, default='unset')
    reason_code = fields.Selection(selection=REASON_CODES, readonly=True)
    explanation = fields.Text(readonly=True)
    counts_current = fields.Boolean(readonly=True, default=False, index=True)
    decision_by_id = fields.Many2one('res.users', readonly=True)
    decision_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'Validation lines are created with the finance request.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A finance validation line cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A finance validation line cannot be deleted.')


class FinanceValidationApproval(models.Model):
    """Append-only approval event. The actor and the time come from the server."""

    _name = 'cpla.finance.validation.approval'
    _description = 'Finance Validation Approval'
    _order = 'id'
    _check_company_auto = True

    _level_unique = models.UniqueIndex(
        "(validation_id, level_sequence) WHERE decision = 'approved' AND level_sequence > 0",
        'This approval level is already recorded.',
    )

    validation_id = fields.Many2one(
        'cpla.finance.validation', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    policy_id = fields.Many2one('cpla.finance.validation.policy', readonly=True, ondelete='restrict')
    policy_reference = fields.Char(readonly=True)
    level_sequence = fields.Integer(readonly=True)
    authority_group = fields.Selection(
        selection=[
            ('finance_reviewer', 'Finance Reviewer'),
            ('finance_manager', 'Finance Manager'),
        ],
        readonly=True,
    )
    decision = fields.Selection(
        selection=[
            ('approved', 'Approved'),
            ('denied', 'Denied'),
            ('evidence_requested', 'Evidence requested'),
        ],
        required=True,
        readonly=True,
    )
    amount_exact = fields.Char(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    actor_id = fields.Many2one('res.users', readonly=True, index=True)
    acted_at = fields.Datetime(readonly=True)
    reason = fields.Text(readonly=True)
    source_fingerprint = fields.Char(readonly=True)
    evidence_snapshot = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Approval events are recorded by the finance action.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An approval event cannot be edited.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An approval event cannot be deleted.')


class FinanceValidationWizard(models.TransientModel):
    _name = 'cpla.finance.validation.wizard'
    _description = 'Finance Validation Wizard'

    validation_id = fields.Many2one('cpla.finance.validation', required=True)
    company_id = fields.Many2one('res.company', required=True)
    line_id = fields.Many2one('cpla.finance.validation.line')
    operation = fields.Selection(
        selection=[
            ('evidence', 'Request evidence'),
            ('propose', 'Propose'),
            ('approve', 'Approve'),
            ('deny', 'Deny'),
            ('correct', 'Correct'),
        ],
        required=True,
    )
    reason = fields.Text()
    required_action = fields.Text()
    validated_exact = fields.Char()
    rejected_exact = fields.Char()
    unresolved_exact = fields.Char()
    reason_code = fields.Selection(selection=REASON_CODES)
    explanation = fields.Text()

    def action_apply(self):
        self.ensure_one()
        record = self.validation_id
        record.check_access('read')
        if self.operation == 'evidence':
            return record.action_request_evidence(self.reason, self.required_action)
        if self.operation == 'approve':
            return record.action_approve(self.reason)
        if self.operation == 'deny':
            return record.action_deny_level(self.reason)
        if self.operation == 'correct':
            revision = record.action_create_correction(self.reason)
            return revision.action_open_case() and {
                'type': 'ir.actions.act_window',
                'res_model': revision._name,
                'res_id': revision.id,
                'view_mode': 'form',
                'target': 'current',
            }
        if self.operation == 'propose':
            decisions = []
            for line in record.line_ids:
                if line == self.line_id:
                    decisions.append({
                        'line_id': line.id,
                        'validated': self.validated_exact,
                        'rejected': self.rejected_exact,
                        'unresolved': self.unresolved_exact,
                        'reason_code': self.reason_code,
                        'explanation': self.explanation or self.reason,
                    })
                else:
                    decisions.append({
                        'line_id': line.id,
                        'validated': line.proposed_validated_exact or '0',
                        'rejected': line.proposed_rejected_exact or '0',
                        'unresolved': line.proposed_unresolved_exact or line.potential_exact,
                        'reason_code': line.reason_code or 'OTHER_DOCUMENTED_REASON',
                        'explanation': line.explanation or 'Recorded with the other finding on this request.',
                    })
            return record.action_propose(decisions)
        _fail(self.env, 'FINANCE_SOURCE_NOT_READY', 'That finance action is not available.')
