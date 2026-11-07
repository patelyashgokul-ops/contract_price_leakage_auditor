import json
from decimal import ROUND_HALF_UP, Decimal

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, LockError, UserError

from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    AUDITOR_GROUP,
    MANAGER_GROUP,
    _arithmetic,
    _decimal,
    _text,
)

MODULE = 'contract_price_leakage_auditor'
POLICY_SEQUENCE = 'cpla.recovery.policy'
REQUEST_SEQUENCE = 'cpla.recovery.request'
WAIVER_SEQUENCE = 'cpla.recovery.waiver'
DISPUTE_SEQUENCE = 'cpla.recovery.dispute'
SETTLEMENT_SEQUENCE = 'cpla.recovery.settlement'
ZERO = Decimal('0')
APP_ADMIN_GROUP = f'{MODULE}.group_app_admin'
AUTHORITY_GROUPS = {
    'contract_manager': MANAGER_GROUP,
}
OPEN_REQUEST = (
    'draft',
    'submitted',
    'under_review',
    'evidence_required',
    'pending_approval',
)
FINAL_ALLOCATING = ('approved',)
WAIVER_REASONS = [
    ('relationship_preservation', 'Commercial relationship preservation'),
    ('small_balance', 'Small balance commercial decision'),
    ('contractual_settlement', 'Contractual settlement'),
    ('dispute_compromise', 'Customer dispute compromise'),
    ('strategic_account', 'Strategic account decision'),
    ('management_concession', 'Management-approved concession'),
    ('cost_of_pursuit', 'Cost of pursuit'),
    ('other_documented', 'Other documented commercial reason'),
]
DISPUTE_CATEGORIES = [
    ('price_not_accepted', 'Contract price not accepted'),
    ('increase_not_communicated', 'Price increase not communicated'),
    ('claims_discount', 'Customer claims approved discount'),
    ('wrong_version', 'Wrong contract version'),
    ('wrong_product_quantity', 'Wrong product or quantity'),
    ('tax', 'Tax disagreement'),
    ('fx', 'FX rate disagreement'),
    ('credit_not_reflected', 'Credit or refund not reflected'),
    ('invoice_corrected', 'Invoice already corrected'),
    ('duplicate_demand', 'Duplicate recovery demand'),
    ('prior_settlement', 'Customer claims prior settlement'),
    ('missing_purchase_order', 'Missing purchase order reference'),
    ('other_contractual', 'Other contractual dispute'),
    ('undetermined', 'Undetermined'),
]
CHANNELS = [
    ('email', 'Email correspondence'),
    ('letter', 'Formal letter reference'),
    ('meeting', 'Meeting notes'),
    ('phone', 'Phone-call summary'),
    ('signed_proposal', 'Customer-signed proposal'),
    ('negotiation_record', 'Authorized negotiation record'),
    ('other', 'Other approved evidence'),
]
REQUEST_STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('under_review', 'Under commercial review'),
    ('evidence_required', 'Evidence required'),
    ('pending_approval', 'Pending approval'),
    ('approved', 'Approved for recovery'),
    ('rejected', 'Rejected'),
    ('withdrawn', 'Withdrawn'),
    ('superseded', 'Superseded'),
    ('stale_source', 'Stale source'),
]
WAIVER_STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('pending_approval', 'Pending approval'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('withdrawn', 'Withdrawn'),
    ('superseded', 'Superseded'),
    ('stale_source', 'Stale source'),
]
DISPUTE_STATES = [
    ('open', 'Open'),
    ('evidence_requested', 'Evidence requested'),
    ('under_review', 'Under internal review'),
    ('response_pending', 'Customer response pending'),
    ('negotiating', 'Negotiating'),
    ('settlement_proposed', 'Settlement proposed'),
    ('resolved_agreed', 'Resolved agreed'),
    ('resolved_rejected', 'Resolved rejected'),
    ('withdrawn', 'Withdrawn'),
    ('escalated', 'Escalated for authorized review'),
]
ACTION_KINDS = [
    ('recovery', 'Recovery approval'),
    ('waiver', 'Waiver approval'),
    ('settlement', 'Settlement approval'),
    ('handoff', 'Accounting handoff authorization'),
]


def _fail(env, code, sentence):
    raise UserError(env._('%s: %s', code, sentence))


def _in_group(env, user, xmlid):
    """Group membership without the superuser short-circuit."""
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


def _money(value):
    amount = _decimal(value)
    return ZERO if amount is None else amount


class RecoveryPolicy(models.Model):
    """Company matrix for commercial recovery, waiver, settlement, and handoff.

    A draft is not authority. No amount is seeded. Formal approval stays
    blocked until this company approves a revision that names levels.
    """

    _name = 'cpla.recovery.policy'
    _description = 'Commercial Recovery Policy'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This commercial recovery policy reference already exists.',
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
        help='Ceilings are compared in this currency. A different document currency needs a recorded rate.',
    )
    four_eyes_required = fields.Boolean(
        default=True,
        help='The requester cannot approve. One user cannot complete two levels.',
    )
    dispute_blocks_handoff = fields.Boolean(
        default=True,
        help='When set, an open dispute blocks accounting handoff of that recovery request. This is not a monetary threshold.',
    )
    change_reason = fields.Text(required=True)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    supersedes_id = fields.Many2one('cpla.recovery.policy', readonly=True, copy=False, index=True)
    is_current = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    level_ids = fields.One2many('cpla.recovery.policy.level', 'policy_id')

    @api.model_create_multi
    def create(self, vals_list):
        self._check_policy_editor()
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            company = self.env['res.company'].browse(vals.get('company_id')).exists()
            if len(company) != 1:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A company is required on the commercial policy.')
            self._require_company(company)
            if not (vals.get('change_reason') or '').strip():
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The commercial policy needs a change reason.')
            if not (vals.get('name') or '').strip():
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The commercial policy needs a name.')
            reference = self.env['ir.sequence'].with_company(company).next_by_code(POLICY_SEQUENCE)
            if not reference:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The commercial policy sequence is missing.')
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
                'An approved commercial policy revision cannot be edited. Create a new revision.',
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
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A commercial policy revision cannot be deleted.')

    def action_approve_policy(self):
        """Make this draft the current commercial authority. It does not waive or bill."""
        self._check_policy_editor()
        for policy in self:
            policy._require_company(policy.company_id)
            if policy.state != 'draft':
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Only a draft policy revision can be approved.')
            if not policy.level_ids:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'Add at least one approval level before approving the policy.')
            seen = set()
            for level in policy.level_ids:
                key = (level.action_kind, level.level_sequence)
                if key in seen:
                    _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'Approval levels need distinct sequences for each action.')
                seen.add(key)
                if level.authority_group not in AUTHORITY_GROUPS:
                    _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'An approval level names an unknown commercial role.')
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

    @api.model
    def current_for(self, company):
        return self.search([
            ('company_id', '=', company.id),
            ('state', '=', 'approved'),
            ('is_current', '=', True),
        ], limit=1)

    def _required_levels(self, action_kind, amount):
        self.ensure_one()
        if self.state != 'approved' or not self.is_current:
            _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The commercial policy is not the current approved revision.')
        levels = self.level_ids.filtered(lambda level: level.action_kind == action_kind).sorted('level_sequence')
        if not levels:
            _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'No approved level covers this commercial action.')
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
        if _in_group(self.env, user, MANAGER_GROUP):
            return
        if user._is_superuser() or _in_group(self.env, user, APP_ADMIN_GROUP):
            raise AccessError(self.env._(
                'APPROVAL_MATRIX_MISSING: A technical administrator is not a commercial approver.'
            ))
        raise AccessError(self.env._(
            'APPROVAL_MATRIX_MISSING: Only a contract manager can maintain the commercial matrix.'
        ))

    def _require_company(self, company):
        if self.env.user._is_superuser():
            return
        if company not in self.env.companies:
            raise AccessError(self.env._('COMPANY_ACCESS_DENIED: You cannot use that company policy.'))

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


class RecoveryPolicyLevel(models.Model):
    _name = 'cpla.recovery.policy.level'
    _description = 'Commercial Recovery Policy Level'
    _order = 'action_kind, level_sequence, id'
    _check_company_auto = True

    policy_id = fields.Many2one(
        'cpla.recovery.policy', required=True, index=True, ondelete='restrict',
    )
    company_id = fields.Many2one(related='policy_id.company_id', store=True, index=True)
    name = fields.Char(required=True)
    action_kind = fields.Selection(selection=ACTION_KINDS, required=True, index=True)
    level_sequence = fields.Integer(required=True, default=1)
    authority_group = fields.Selection(
        selection=[('contract_manager', 'Contract Manager')],
        required=True,
        help='Finance validation authority is not commercial waiver authority. Recovery Operator is not an approver.',
    )
    applies_from_exact = fields.Char(required=True, default='0')
    has_ceiling = fields.Boolean(
        default=True,
        help='When set, maximum_exact is the highest document amount this level can cover. No amount is seeded.',
    )
    maximum_exact = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        self.env['cpla.recovery.policy']._check_policy_editor()
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            policy = self.env['cpla.recovery.policy'].browse(vals.get('policy_id')).exists()
            if len(policy) != 1 or policy.state != 'draft':
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Add levels only on a draft commercial policy.')
            policy._require_company(policy.company_id)
            if vals.get('authority_group') not in AUTHORITY_GROUPS:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The commercial level must name Contract Manager.')
            if vals.get('action_kind') not in dict(ACTION_KINDS):
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The commercial level needs a known action.')
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.env['cpla.recovery.policy']._check_policy_editor()
        if any(level.policy_id.state != 'draft' for level in self):
            _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An approved commercial level cannot be edited.')
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A commercial approval level cannot be deleted.')


class RecoveryBalance(models.Model):
    """Commercial allocation for one finance-validation line. Not a journal."""

    _name = 'cpla.recovery.balance'
    _description = 'Commercial Allocation Balance'
    _order = 'id'
    _check_company_auto = True

    _line_unique = models.Constraint(
        'UNIQUE(validation_line_id)',
        'This finance line already has a commercial allocation balance.',
    )

    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    validation_id = fields.Many2one('cpla.finance.validation', required=True, index=True, readonly=True, ondelete='restrict')
    validation_line_id = fields.Many2one(
        'cpla.finance.validation.line', required=True, index=True, readonly=True, ondelete='restrict',
    )
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    validated_exact = fields.Char(required=True, readonly=True, default='0')
    waiver_exact = fields.Char(required=True, readonly=True, default='0')
    recovery_exact = fields.Char(required=True, readonly=True, default='0')
    dispute_exact = fields.Char(required=True, readonly=True, default='0')
    acknowledged_exact = fields.Char(required=True, readonly=True, default='0')
    counts_current = fields.Boolean(readonly=True, default=False, index=True)
    source_fingerprint = fields.Char(readonly=True, index=True)
    source_revision = fields.Integer(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Allocation balances are created with the commercial action.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An allocation balance cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An allocation balance cannot be deleted.')


class RecoveryRequest(models.Model):
    """Authorized commercial pursuit of finance-validated leakage. Not an invoice."""

    _name = 'cpla.recovery.request'
    _description = 'Commercial Recovery Request'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This recovery request reference already exists.',
    )
    _handoff_key_unique = models.UniqueIndex(
        '(handoff_key) WHERE handoff_key IS NOT NULL',
        'This accounting handoff authorization already exists.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True, readonly=True)
    case_id = fields.Many2one('cpla.leakage.case', required=True, index=True, readonly=True, ondelete='restrict')
    validation_id = fields.Many2one(
        'cpla.finance.validation', required=True, index=True, readonly=True, ondelete='restrict',
    )
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    state = fields.Selection(selection=REQUEST_STATES, required=True, default='draft', readonly=True, index=True, copy=False)
    customer_state = fields.Selection(
        selection=[
            ('none', 'No customer position'),
            ('discussion', 'Customer discussion'),
            ('acknowledged', 'Customer acknowledged'),
            ('disputed', 'Customer disputed'),
            ('partial', 'Partly acknowledged and disputed'),
        ],
        required=True,
        default='none',
        readonly=True,
        index=True,
        copy=False,
    )
    billing_state = fields.Selection(
        selection=[
            ('not_ready', 'Not ready for accounting'),
            ('ready_for_accounting', 'Ready for accounting handoff'),
        ],
        required=True,
        default='not_ready',
        readonly=True,
        index=True,
        copy=False,
    )
    requested_by_id = fields.Many2one('res.users', required=True, readonly=True, index=True)
    requested_at = fields.Datetime(required=True, readonly=True)
    owner_id = fields.Many2one('res.users', required=True, readonly=True, index=True)
    requested_amount_exact = fields.Char(required=True, readonly=True, default='0')
    approved_recovery_exact = fields.Char(
        required=True, readonly=True, default='0',
        help='Original authorized target. A later concession does not erase this figure.',
    )
    current_recovery_exact = fields.Char(required=True, readonly=True, default='0')
    policy_id = fields.Many2one('cpla.recovery.policy', readonly=True, ondelete='restrict')
    policy_reference = fields.Char(readonly=True)
    required_level_count = fields.Integer(readonly=True, default=0)
    approval_level_done = fields.Integer(readonly=True, default=0)
    next_level_sequence = fields.Integer(readonly=True, default=0)
    stale_source = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    source_revision = fields.Integer(readonly=True)
    source_fingerprint = fields.Char(readonly=True, index=True)
    approval_snapshot = fields.Text(readonly=True, copy=False)
    prepare_key = fields.Char(readonly=True, index=True)
    fx_rate_exact = fields.Char(readonly=True, copy=False)
    fx_rate_date = fields.Date(readonly=True, copy=False)
    fx_rate_note = fields.Text(readonly=True, copy=False)
    handoff_key = fields.Char(readonly=True, copy=False, index=True)
    handoff_amount_exact = fields.Char(readonly=True, default='0', copy=False)
    handoff_revision = fields.Integer(readonly=True, default=0, copy=False)
    billed_amount_exact = fields.Char(readonly=True, default='0', copy=False)
    collected_amount_exact = fields.Char(readonly=True, default='0', copy=False)
    supersedes_id = fields.Many2one('cpla.recovery.request', readonly=True, copy=False, index=True)
    line_ids = fields.One2many('cpla.recovery.request.line', 'request_id')
    waiver_ids = fields.One2many('cpla.recovery.waiver', 'request_id')
    dispute_ids = fields.One2many('cpla.recovery.dispute', 'request_id')
    settlement_ids = fields.One2many('cpla.recovery.settlement', 'request_id')
    event_ids = fields.One2many('cpla.recovery.event', 'request_id')

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A recovery request is prepared from a current finance validation.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A recovery request cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A recovery request cannot be deleted.')

    def export_data(self, fields_to_export):
        user = self.env.user
        if user.share or not user.active:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A public user cannot export a recovery request.')
        allowed = _in_group(self.env, user, MANAGER_GROUP) or _in_group(self.env, user, AUDITOR_GROUP)
        if not allowed:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'You cannot export a commercial recovery decision.')
        self.check_access('read')
        return super().export_data(fields_to_export)

    @api.model
    def prepare_from_validation(self, validation_id, line_amounts=None, force_new=False):
        """Open a draft recovery proposal. The draft is not an approved target."""
        self._check_requester()
        validation = self.env['cpla.finance.validation'].browse(validation_id).exists()
        if len(validation) != 1:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Choose one finance validation.')
        validation.check_access('read')
        self._require_company(validation.company_id)
        self._assert_validation_current(validation)
        amounts = self._proposal_amounts(validation, line_amounts)
        prepare_key = _canonical({
            'validation_id': validation.id,
            'lines': sorted((line_id, amount) for line_id, amount in amounts.items()),
        })
        if not force_new:
            existing = self.search([
                ('validation_id', '=', validation.id),
                ('prepare_key', '=', prepare_key),
                ('state', 'not in', ('rejected', 'withdrawn', 'superseded', 'stale_source')),
            ], limit=1)
            if existing:
                return existing
        self._assert_proposal_room(validation, amounts, extra_open=True)
        reference = self.env['ir.sequence'].with_company(validation.company_id).next_by_code(REQUEST_SEQUENCE)
        if not reference:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'The recovery request sequence is missing.')
        fingerprints = []
        revision = 0
        for line in validation.line_ids:
            if line.id not in amounts:
                continue
            fingerprints.append(line.source_fingerprint or '')
            revision = max(revision, line.source_revision or 0)
        requested = ZERO
        for amount in amounts.values():
            requested = _arithmetic('add', requested, _decimal(amount))
        request = models.Model.create(self, [{
            'reference': reference,
            'company_id': validation.company_id.id,
            'partner_id': validation.partner_id.id,
            'case_id': validation.case_id.id,
            'validation_id': validation.id,
            'currency_id': validation.review_currency_id.id,
            'state': 'draft',
            'customer_state': 'none',
            'billing_state': 'not_ready',
            'requested_by_id': self.env.user.id,
            'requested_at': fields.Datetime.now(),
            'owner_id': self.env.user.id,
            'requested_amount_exact': _text(_quantize(requested, validation.review_currency_id)),
            'approved_recovery_exact': '0',
            'current_recovery_exact': '0',
            'stale_source': False,
            'source_revision': revision,
            'source_fingerprint': _canonical(sorted(fingerprints)),
            'prepare_key': prepare_key,
            'billed_amount_exact': '0',
            'collected_amount_exact': '0',
            'handoff_amount_exact': '0',
        }])
        for line in validation.line_ids.sorted('id'):
            if line.id not in amounts:
                continue
            balance = self.env['cpla.recovery.balance']._ensure(line)
            models.Model.create(self.env['cpla.recovery.request.line'], [{
                'request_id': request.id,
                'company_id': line.company_id.id,
                'validation_line_id': line.id,
                'balance_id': balance.id,
                'finding_id': line.finding_id.id,
                'finding_identity': line.finding_identity or '',
                'source_fingerprint': line.source_fingerprint or '',
                'source_revision': line.source_revision or 0,
                'currency_id': line.currency_id.id,
                'validated_available_exact': line.approved_validated_exact or '0',
                'proposed_recovery_exact': amounts[line.id],
                'approved_recovery_exact': '0',
                'current_recovery_exact': '0',
                'counts_current': False,
            }])
        self._log(request, 'recovery_requested', 'Draft recovery request prepared from the current finance validation.', '0', request.requested_amount_exact)
        return request

    def action_submit(self):
        self._check_requester()
        for record in self:
            record._require_company(record.company_id)
            if record.state != 'draft':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Submit a draft recovery request.')
            if record.requested_by_id != self.env.user:
                _fail(self.env, 'COMMERCIAL_AUTHORITY_DENIED', 'Only the requester can submit this draft.')
            record._assert_validation_current(record.validation_id)
            models.Model.write(record, {'state': 'submitted'})
            record._schedule_internal_activity()
            self._log(record, 'recovery_submitted', 'Submitted for commercial review. This is not approval and not billing.', record.requested_amount_exact, record.requested_amount_exact)
        return True

    def action_mark_under_review(self):
        self._check_requester()
        for record in self:
            record._require_company(record.company_id)
            if record.state != 'submitted':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Start review from a submitted request.')
            models.Model.write(record, {'state': 'under_review'})
        return True

    def action_request_evidence(self, reason):
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'An evidence request needs a reason.')
        self._check_requester()
        for record in self:
            record._require_company(record.company_id)
            if record.state not in ('submitted', 'under_review', 'pending_approval'):
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Evidence can be requested before approval.')
            models.Model.write(record, {'state': 'evidence_required'})
            self._log(record, 'evidence_requested', str(reason).strip(), record.state, 'evidence_required')
        return True

    def action_resume(self):
        self._check_requester()
        for record in self:
            record._require_company(record.company_id)
            if record.state != 'evidence_required':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Resume a request that is waiting for evidence.')
            record._assert_validation_current(record.validation_id)
            models.Model.write(record, {'state': 'submitted'})
        return True

    def action_request_approval(self):
        self._check_requester()
        for record in self:
            record.lock_for_update()
            record._require_company(record.company_id)
            if record.state not in ('submitted', 'under_review'):
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Request approval from commercial review.')
            record._assert_validation_current(record.validation_id)
            record._assert_lines_fresh()
            policy = self.env['cpla.recovery.policy'].current_for(record.company_id)
            if not policy:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'This company has no approved commercial matrix.')
            amount = record._policy_amount(policy, _money(record.requested_amount_exact))
            levels = policy._required_levels('recovery', amount)
            models.Model.write(record, {
                'state': 'pending_approval',
                'policy_id': policy.id,
                'policy_reference': policy.reference,
                'required_level_count': len(levels),
                'approval_level_done': 0,
                'next_level_sequence': levels[0].level_sequence,
            })
            self._log(record, 'recovery_submitted', 'Submitted for recovery approval. No target is authorized yet.', '0', record.requested_amount_exact)
        return True

    def action_approve(self, reason):
        """Approve the next recovery level. A retry does not allocate the amount twice."""
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Approval needs a reason.')
        for record in self:
            record._require_company(record.company_id)
            record.check_access('read')
            user = self.env.user
            if record.state == 'approved':
                if record.event_ids.filtered(
                    lambda event: event.event_type == 'recovery_level_approved' and event.actor_id == user
                ):
                    continue
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'This recovery decision is already recorded.')
            if record.state != 'pending_approval':
                _fail(self.env, 'APPROVAL_LEVEL_PENDING', 'Approve only a recovery request that is pending approval.')
            record._assert_level_ready(user, 'recovery', _money(record.requested_amount_exact), str(reason).strip())
        return True

    def action_reject(self, reason):
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A rejection needs a reason.')
        for record in self:
            record._require_company(record.company_id)
            record.check_access('read')
            if record.state != 'pending_approval':
                _fail(self.env, 'APPROVAL_LEVEL_PENDING', 'Reject a recovery request only while approval is pending.')
            policy = record.policy_id
            levels = policy._required_levels('recovery', record._policy_amount(policy, _money(record.requested_amount_exact)))
            done = record._approved_level_events('recovery_level_approved')
            level = levels[len(done)]
            record._assert_level_actor(self.env.user, level, done)
            self._log(record, 'recovery_rejected', str(reason).strip(), record.requested_amount_exact, '0', level=level)
            models.Model.write(record, {'state': 'rejected'})
        return True

    def action_withdraw(self, reason):
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Withdrawal needs a reason.')
        self._check_requester()
        for record in self:
            record._require_company(record.company_id)
            if record.handoff_key:
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An authorized accounting handoff cannot be withdrawn here.')
            if record.state in ('withdrawn', 'rejected', 'superseded', 'stale_source'):
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'This recovery request is already closed.')
            if record.state == 'approved':
                with self.env.cr.savepoint():
                    for line in record.line_ids.sorted(lambda item: item.balance_id.id):
                        current = _money(line.current_recovery_exact)
                        if current:
                            self.env['cpla.recovery.balance']._move(
                                line.balance_id, ZERO, _arithmetic('sub', ZERO, current), ZERO, ZERO,
                            )
                        models.Model.write(line, {'counts_current': False, 'current_recovery_exact': '0'})
            models.Model.write(record, {'state': 'withdrawn', 'current_recovery_exact': '0'})
            self._log(record, 'recovery_withdrawn', str(reason).strip(), record.approved_recovery_exact, '0')
        return True

    def action_mark_discussion(self):
        """Record that customer discussion is open. Silence is not acceptance."""
        self._check_requester()
        for record in self:
            record._require_company(record.company_id)
            if record.state != 'approved':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Customer discussion follows an approved recovery target.')
            if record.customer_state == 'none':
                models.Model.write(record, {'customer_state': 'discussion'})
                self._log(record, 'customer_discussion', 'Customer discussion is open. No response has been recorded.', '0', '0')
        return True

    def action_set_review_rate(self, rate_exact, rate_date, note):
        """Store a rate the user supplied. This does not look up a market rate."""
        self._check_requester()
        rate = _decimal(rate_exact)
        if rate is None or rate <= ZERO:
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The review rate must be a positive recorded rate.')
        if not rate_date or not (note or '').strip():
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The review rate needs a date and a note.')
        for record in self:
            record._require_company(record.company_id)
            if record.state not in ('draft', 'submitted', 'under_review', 'evidence_required'):
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'The review rate cannot change after approval is requested.')
            models.Model.write(record, {
                'fx_rate_exact': _text(rate),
                'fx_rate_date': rate_date,
                'fx_rate_note': str(note).strip(),
            })
        return True

    def action_authorize_handoff(self, reason):
        """Authorize DEV-17 to read this allocation. This does not create an invoice."""
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Handoff authorization needs a reason.')
        payloads = []
        for record in self:
            record._require_company(record.company_id)
            record.check_access('read')
            if record.handoff_key and record.billing_state == 'ready_for_accounting':
                payloads.append(record.accounting_handoff_payload())
                continue
            blockers = record._handoff_blockers()
            if blockers:
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', blockers[0])
            policy = record.policy_id or self.env['cpla.recovery.policy'].current_for(record.company_id)
            amount = record._policy_amount(policy, _money(record.current_recovery_exact))
            levels = policy._required_levels('handoff', amount)
            done = record._approved_level_events('handoff_authorized')
            if done:
                payloads.append(record.accounting_handoff_payload())
                continue
            level = levels[0]
            record._assert_level_actor(self.env.user, level, done)
            key = 'c%s|v%s|r%s|rev%s' % (
                record.company_id.id,
                record.validation_id.id,
                record.id,
                record.source_revision or 0,
            )
            try:
                with self.env.cr.savepoint():
                    record.lock_for_update()
                    if record.handoff_key:
                        continue
                    self._log(
                        record, 'handoff_authorized', str(reason).strip(),
                        '0', record.current_recovery_exact, level=level,
                    )
                    models.Model.write(record, {
                        'handoff_key': key,
                        'handoff_amount_exact': record.current_recovery_exact,
                        'handoff_revision': 1,
                        'billing_state': 'ready_for_accounting',
                        'billed_amount_exact': '0',
                        'collected_amount_exact': '0',
                    })
                    accepted = record.settlement_ids.filtered(
                        lambda item: item.counts_current and item.customer_state == 'accepted'
                    )
                    if accepted:
                        models.Model.write(accepted, {'execution_state': 'ready_for_dev17'})
            except IntegrityError:
                record.invalidate_recordset()
            payloads.append(record.accounting_handoff_payload())
        return payloads[0] if len(self) == 1 else payloads

    def accounting_handoff_payload(self):
        """Read-only handoff contract. Never creates an account.move."""
        self.ensure_one()
        self.check_access('read')
        self._require_company(self.company_id)
        blockers = [] if self.handoff_key else self._handoff_blockers()
        ready = bool(self.handoff_key) and self.billing_state == 'ready_for_accounting' and not blockers
        lines = []
        for line in self.line_ids:
            lines.append({
                'request_line_id': line.id,
                'validation_line_id': line.validation_line_id.id,
                'finding_id': line.finding_id.id,
                'finding_identity': line.finding_identity or '',
                'source_fingerprint': line.source_fingerprint or '',
                'source_revision': line.source_revision or 0,
                'authorized_amount': line.current_recovery_exact or '0',
                'original_authorized_amount': line.approved_recovery_exact or '0',
                'currency_id': line.currency_id.id,
                'move_line_id': line.validation_line_id.move_line_id.id,
            })
        waivers = [{
            'waiver_id': waiver.id,
            'reference': waiver.reference,
            'approved_amount': waiver.approved_amount_exact or '0',
            'state': waiver.state,
            'counts_current': waiver.counts_current,
        } for waiver in self.waiver_ids]
        disputes = [{
            'dispute_id': dispute.id,
            'reference': dispute.reference,
            'amount': dispute.disputed_amount_exact or '0',
            'state': dispute.state,
            'counts_current': dispute.counts_current,
        } for dispute in self.dispute_ids]
        settlement = self.settlement_ids.filtered(lambda item: item.counts_current)[:1]
        return {
            'status': 'READY_FOR_ACCOUNTING' if ready else 'NOT_READY_WITH_REASONS',
            'reasons': [] if ready else (blockers or ['Handoff has not been authorized.']),
            'recovery_request_id': self.id,
            'reference': self.reference,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'case_id': self.case_id.id,
            'validation_id': self.validation_id.id,
            'validation_reference': self.validation_id.reference,
            'currency_id': self.currency_id.id,
            'authorized_amount': self.handoff_amount_exact or '0' if ready else '0',
            'current_recovery_target': self.current_recovery_exact or '0',
            'lines': lines,
            'waivers': waivers,
            'disputes': disputes,
            'settlement_id': settlement.id,
            'customer_acceptance_state': settlement.customer_state if settlement else 'not_sent',
            'internal_settlement_state': settlement.internal_state if settlement else 'draft',
            'source_fingerprint': self.source_fingerprint or '',
            'source_revision': self.source_revision or 0,
            'approval_snapshot': self.approval_snapshot or '',
            'handoff_key': self.handoff_key or '',
            'handoff_revision': self.handoff_revision or 0,
            'fx_rate_exact': self.fx_rate_exact or '',
            'fx_rate_date': self.fx_rate_date,
            'billed_amount': '0',
            'collected_amount': '0',
            'creates_account_move': False,
            'creates_customer_receivable': False,
            'proves_cash_collection': False,
        }

    def commercial_position(self):
        """Current V = W + T + U for this request's finance validation."""
        self.ensure_one()
        self.check_access('read')
        return self.env['cpla.recovery.balance'].position_for(self.validation_id)

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

    def action_open_approve_wizard(self):
        return self._open_commercial_wizard('approve_recovery')

    def action_open_reject_wizard(self):
        return self._open_commercial_wizard('reject_recovery')

    def action_open_withdraw_wizard(self):
        return self._open_commercial_wizard('withdraw_recovery')

    def action_open_handoff_wizard(self):
        return self._open_commercial_wizard('handoff')

    def _open_commercial_wizard(self, operation):
        """Open a reason wizard. The wizard does not post an invoice."""
        self.ensure_one()
        self.check_access('read')
        line = self.line_ids[:1]
        wizard = self.env['cpla.recovery.wizard'].create({
            'company_id': self.company_id.id,
            'operation': operation,
            'validation_id': self.validation_id.id,
            'validation_line_id': line.validation_line_id.id,
            'request_id': self.id,
            'request_line_id': line.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.reference,
            'res_model': 'cpla.recovery.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def _flag_finance_source(self, validation):
        """Keep historical commercial decisions and stop current allocation."""
        if not validation:
            return
        requests = self.search([('validation_id', 'in', validation.ids)])
        balances = self.env['cpla.recovery.balance'].search([
            ('validation_id', 'in', validation.ids),
            ('counts_current', '=', True),
        ])
        if balances:
            models.Model.write(balances, {'counts_current': False})
        for request in requests:
            if request.state == 'approved':
                models.Model.write(request, {'stale_source': True})
                models.Model.write(request.line_ids, {'counts_current': False})
                self._log(request, 'source_stale', 'The finance source changed. The historical target is kept and is not current.', request.current_recovery_exact, request.current_recovery_exact)
            elif request.state in OPEN_REQUEST and request.state != 'stale_source':
                models.Model.write(request, {'state': 'stale_source', 'stale_source': True})
        waivers = self.env['cpla.recovery.waiver'].search([
            ('validation_id', 'in', validation.ids),
            ('state', 'not in', ('superseded', 'rejected', 'withdrawn')),
        ])
        for waiver in waivers:
            if waiver.state == 'approved':
                models.Model.write(waiver, {'stale_source': True, 'counts_current': False})
            elif waiver.state in ('draft', 'submitted', 'pending_approval'):
                models.Model.write(waiver, {'state': 'stale_source', 'stale_source': True, 'counts_current': False})
        settlements = self.env['cpla.recovery.settlement'].search([
            ('validation_id', 'in', validation.ids),
            ('counts_current', '=', True),
        ])
        if settlements:
            models.Model.write(settlements, {
                'execution_state': 'suspended_source_changed',
                'counts_current': False,
            })

    def _assert_level_ready(self, user, action_kind, amount, reason):
        self.ensure_one()
        event_type = {
            'recovery': 'recovery_level_approved',
            'handoff': 'handoff_authorized',
        }[action_kind]
        try:
            self._assert_lines_fresh()
        except UserError:
            if self.state in OPEN_REQUEST:
                models.Model.write(self, {'state': 'stale_source', 'stale_source': True})
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The finance source changed. The old amount was not approved.')
        policy = self.policy_id
        if not policy or not policy.is_current:
            _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'The commercial policy on this request is not current.')
        basis = self._policy_amount(policy, amount)
        levels = policy._required_levels(action_kind, basis)
        done = self._approved_level_events(event_type)
        if len(done) >= len(levels):
            return
        level = levels[len(done)]
        self._assert_level_actor(user, level, done)
        try:
            with self.env.cr.savepoint():
                self._lock_balances()
                self._assert_lines_fresh()
                self._log(self, event_type, reason, '0', _text(amount), level=level)
                if len(done) + 1 < len(levels):
                    nxt = levels[len(done) + 1]
                    models.Model.write(self, {
                        'approval_level_done': len(done) + 1,
                        'next_level_sequence': nxt.level_sequence,
                        'state': 'pending_approval',
                    })
                else:
                    self._finalize_recovery(user, reason)
        except IntegrityError:
            self.invalidate_recordset()
            if self.state == 'approved':
                return
            _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'Another approval was recorded for this recovery level.')
        except LockError:
            _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'Another commercial allocation is being recorded.')

    def _finalize_recovery(self, user, reason):
        self.ensure_one()
        total = ZERO
        for line in self.line_ids.sorted(lambda item: item.balance_id.id):
            amount = _money(line.proposed_recovery_exact)
            self.env['cpla.recovery.balance']._move(line.balance_id, ZERO, amount, ZERO, ZERO)
            models.Model.write(line, {
                'approved_recovery_exact': _text(_quantize(amount, line.currency_id)),
                'current_recovery_exact': _text(_quantize(amount, line.currency_id)),
                'counts_current': True,
            })
            total = _arithmetic('add', total, amount)
        snapshot = _canonical({
            'validation': self.validation_id.reference,
            'fingerprint': self.source_fingerprint,
            'source_revision': self.source_revision,
            'amount': _text(_quantize(total, self.currency_id)),
            'policy': self.policy_reference,
            'actor_id': user.id,
        })
        models.Model.write(self, {
            'state': 'approved',
            'approved_recovery_exact': _text(_quantize(total, self.currency_id)),
            'current_recovery_exact': _text(_quantize(total, self.currency_id)),
            'approval_level_done': self.required_level_count,
            'approval_snapshot': snapshot,
            'billed_amount_exact': '0',
            'collected_amount_exact': '0',
        })
        self._log(self, 'recovery_approved', reason, '0', _text(_quantize(total, self.currency_id)))

    def _lock_balances(self):
        balances = self.line_ids.mapped('balance_id').sorted('id')
        if balances:
            balances.lock_for_update()

    def _approved_level_events(self, event_type):
        return self.event_ids.filtered(
            lambda event: event.event_type == event_type and event.level_sequence > 0
        )

    def _assert_level_actor(self, user, level, done):
        self.ensure_one()
        xmlid = AUTHORITY_GROUPS.get(level.authority_group)
        if not xmlid or not _in_group(self.env, user, xmlid):
            if user._is_superuser() or _in_group(self.env, user, APP_ADMIN_GROUP):
                raise AccessError(self.env._(
                    'APPROVAL_MATRIX_MISSING: A technical administrator is not a commercial approver.'
                ))
            raise AccessError(self.env._(
                'APPROVAL_LIMIT_EXCEEDED: You are not the approver for this commercial level.'
            ))
        if self.policy_id.four_eyes_required:
            if user == self.requested_by_id:
                raise AccessError(self.env._(
                    'SELF_APPROVAL_PROHIBITED: The requester cannot approve this commercial action.'
                ))
            if user in done.mapped('actor_id'):
                raise AccessError(self.env._(
                    'SELF_APPROVAL_PROHIBITED: One user cannot complete two approval levels.'
                ))

    def _policy_amount(self, policy, amount):
        self.ensure_one()
        amount = _quantize(amount, self.currency_id)
        if self.currency_id == policy.currency_id:
            return amount
        rate = _decimal(self.fx_rate_exact)
        if rate is None or rate <= ZERO or not self.fx_rate_date or not (self.fx_rate_note or '').strip():
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'A recorded rate is required before this currency can be approved.')
        return _quantize(_arithmetic('mul', amount, rate), policy.currency_id)

    def _assert_lines_fresh(self):
        self.ensure_one()
        self._assert_validation_current(self.validation_id)
        if self.stale_source:
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'This recovery request is bound to a stale finance source.')
        for line in self.line_ids:
            finance_line = line.validation_line_id
            if not finance_line.counts_current or finance_line.validation_id.stale_source:
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'A source line is no longer the current finance decision.')
            if (finance_line.source_fingerprint or '') != (line.source_fingerprint or ''):
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The source fingerprint changed.')
            if not line.balance_id.counts_current:
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The allocation balance is not current.')

    def _handoff_blockers(self):
        self.ensure_one()
        reasons = []
        if self.state != 'approved':
            reasons.append('The recovery request is not approved.')
        if self.stale_source or not self.validation_id.is_current or self.validation_id.stale_source:
            reasons.append('The finance source is stale.')
        if self.validation_id.state not in ('approved', 'partially_approved'):
            reasons.append('The finance validation is not an approved decision.')
        policy = self.policy_id or self.env['cpla.recovery.policy'].current_for(self.company_id)
        if not policy or not policy.is_current:
            reasons.append('The commercial policy is not current.')
        elif policy.dispute_blocks_handoff and self.dispute_ids.filtered('counts_current'):
            reasons.append('An open dispute blocks accounting handoff under the current policy.')
        open_settlement = self.settlement_ids.filtered(
            lambda item: item.counts_current and item.customer_state not in ('accepted', 'withdrawn', 'rejected')
            and item.internal_state != 'rejected'
        )
        if open_settlement:
            reasons.append('A current settlement has no customer acceptance.')
        if _money(self.current_recovery_exact) <= ZERO:
            reasons.append('The current recovery target is zero.')
        if _money(self.billed_amount_exact) or _money(self.collected_amount_exact):
            reasons.append('Billing figures must stay at zero until accounting records them.')
        return reasons

    def _schedule_internal_activity(self):
        """Internal reminder only. The summary has no amount and no customer send."""
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return
        model = self.env['ir.model']._get('cpla.leakage.case')
        if not model:
            return
        self.env['mail.activity'].with_context(
            mail_activity_quick_update=True,
            mail_notrack=True,
        ).create({
            'res_model_id': model.id,
            'res_id': self.case_id.id,
            'activity_type_id': activity_type.id,
            'summary': 'Review recovery request',
            'note': 'Internal commercial review. This date is the review request date, not a collection deadline. Do not send this to the customer.',
            'user_id': self.owner_id.id,
            'date_deadline': fields.Date.context_today(self),
        })

    def _refresh_customer_state(self):
        self.ensure_one()
        position = self.env['cpla.recovery.balance'].position_for(self.validation_id)
        acknowledged = _money(position['acknowledged'])
        disputed = _money(position['disputed'])
        if acknowledged and disputed:
            state = 'partial'
        elif disputed:
            state = 'disputed'
        elif acknowledged:
            state = 'acknowledged'
        elif self.customer_state == 'discussion':
            state = 'discussion'
        else:
            state = 'none'
        models.Model.write(self, {'customer_state': state})

    @api.model
    def _check_requester(self):
        user = self.env.user
        if _in_group(self.env, user, MANAGER_GROUP):
            return
        if user._is_superuser() or _in_group(self.env, user, APP_ADMIN_GROUP):
            raise AccessError(self.env._(
                'APPROVAL_MATRIX_MISSING: A technical administrator is not a commercial approver.'
            ))
        raise AccessError(self.env._(
            'COMMERCIAL_AUTHORITY_DENIED: Only a contract manager can prepare a commercial recovery action.'
        ))

    def _require_company(self, company):
        if self.env.user._is_superuser():
            return
        if company not in self.env.companies:
            raise AccessError(self.env._('COMPANY_ACCESS_DENIED: You cannot use that company.'))

    @api.model
    def _assert_validation_current(self, validation):
        payload = validation.decision_payload()
        if validation.state not in ('approved', 'partially_approved'):
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Recovery cannot start from an unapproved finance decision.')
        if not payload['current'] or payload['stale_source']:
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The finance validation is not a current approved decision.')
        if payload['recovery_authority']:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Finance validation must not itself authorize recovery.')
        if validation.company_id != validation.case_id.company_id:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The finance validation company does not match the case.')

    @api.model
    def _proposal_amounts(self, validation, line_amounts):
        current_lines = validation.line_ids.filtered(
            lambda line: line.counts_current and _money(line.approved_validated_exact) > ZERO
        )
        if not current_lines:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'This finance decision has no current validated amount to allocate.')
        if any(line.currency_id != validation.review_currency_id for line in current_lines):
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The finance line currency does not match the validation currency.')
        if line_amounts is None:
            return {
                line.id: _text(_quantize(_money(line.approved_validated_exact), line.currency_id))
                for line in current_lines
            }
        unknown = set(line_amounts) - set(current_lines.ids)
        if unknown:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A proposed line is not a current validated finance line.')
        amounts = {}
        for line in current_lines:
            if line.id not in line_amounts:
                continue
            amount = _decimal(line_amounts[line.id])
            if amount is None or amount <= ZERO:
                _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'A recovery amount must be positive.')
            quantized = _quantize(amount, line.currency_id)
            if quantized <= ZERO:
                _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'A recovery amount must be positive after currency rounding.')
            if quantized > _money(line.approved_validated_exact):
                _fail(self.env, 'ALLOCATION_EXCEEDS_VALIDATED', 'The proposed recovery exceeds the validated line.')
            amounts[line.id] = _text(quantized)
        if not amounts:
            _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'Choose at least one positive recovery amount.')
        return amounts

    @api.model
    def _assert_proposal_room(self, validation, amounts, extra_open=False, releasing=ZERO):
        for line_id, amount_text in amounts.items():
            line = validation.line_ids.filtered(lambda item: item.id == line_id)
            balance = self.env['cpla.recovery.balance'].search([
                ('validation_line_id', '=', line.id),
            ], limit=1)
            used = ZERO
            if balance and balance.counts_current:
                used = _arithmetic('add', _money(balance.waiver_exact), _money(balance.recovery_exact))
            if releasing:
                used = _arithmetic('sub', used, releasing)
                if used < ZERO:
                    used = ZERO
            if extra_open:
                open_lines = self.env['cpla.recovery.request.line'].search([
                    ('validation_line_id', '=', line.id),
                    ('request_id.state', 'in', list(OPEN_REQUEST)),
                ])
                for open_line in open_lines:
                    used = _arithmetic('add', used, _money(open_line.proposed_recovery_exact))
                open_waivers = self.env['cpla.recovery.waiver'].search([
                    ('validation_line_id', '=', line.id),
                    ('state', 'in', ('draft', 'submitted', 'pending_approval')),
                    ('reduces_recovery', '=', False),
                ])
                for waiver in open_waivers:
                    used = _arithmetic('add', used, _money(waiver.proposed_amount_exact))
            available = _arithmetic('sub', _money(line.approved_validated_exact), used)
            if _money(amount_text) > available:
                _fail(self.env, 'ALLOCATION_EXCEEDS_VALIDATED', 'The proposal exceeds the unallocated validated balance.')

    @api.model
    def _log(self, request, event_type, reason, old_value, new_value, level=None, waiver=None, dispute=None, settlement=None, evidence_note='', channel=False, response_on=False):
        models.Model.create(request.env['cpla.recovery.event'], [{
            'company_id': request.company_id.id,
            'request_id': request.id,
            'waiver_id': waiver.id if waiver else False,
            'dispute_id': dispute.id if dispute else False,
            'settlement_id': settlement.id if settlement else False,
            'event_type': event_type,
            'actor_id': request.env.user.id,
            'acted_at': fields.Datetime.now(),
            'old_value': old_value or '0',
            'new_value': new_value or '0',
            'currency_id': request.currency_id.id,
            'reason': reason,
            'evidence_note': evidence_note or '',
            'channel': channel or False,
            'response_on': response_on or False,
            'level_sequence': level.level_sequence if level else 0,
            'subject': level.action_kind if level else event_type,
            'source_fingerprint': request.source_fingerprint or '',
        }])


class RecoveryRequestLine(models.Model):
    _name = 'cpla.recovery.request.line'
    _description = 'Commercial Recovery Request Line'
    _order = 'id'
    _check_company_auto = True

    request_id = fields.Many2one('cpla.recovery.request', required=True, index=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    validation_line_id = fields.Many2one(
        'cpla.finance.validation.line', required=True, index=True, readonly=True, ondelete='restrict',
    )
    balance_id = fields.Many2one('cpla.recovery.balance', required=True, index=True, readonly=True, ondelete='restrict')
    finding_id = fields.Many2one('cpla.leakage.finding', required=True, index=True, readonly=True, ondelete='restrict')
    finding_identity = fields.Char(readonly=True, index=True)
    source_fingerprint = fields.Char(readonly=True, index=True)
    source_revision = fields.Integer(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    validated_available_exact = fields.Char(readonly=True)
    proposed_recovery_exact = fields.Char(readonly=True)
    approved_recovery_exact = fields.Char(readonly=True, default='0')
    current_recovery_exact = fields.Char(readonly=True, default='0')
    counts_current = fields.Boolean(readonly=True, default=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Recovery lines are created with the recovery request.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A recovery line cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A recovery line cannot be deleted.')


class RecoveryWaiver(models.Model):
    """Authorized decision not to pursue part of a validated amount. Not a write-off."""

    _name = 'cpla.recovery.waiver'
    _description = 'Commercial Waiver'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This commercial waiver reference already exists.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True, readonly=True)
    validation_id = fields.Many2one('cpla.finance.validation', required=True, index=True, readonly=True, ondelete='restrict')
    validation_line_id = fields.Many2one(
        'cpla.finance.validation.line', required=True, index=True, readonly=True, ondelete='restrict',
    )
    request_id = fields.Many2one('cpla.recovery.request', index=True, readonly=True, ondelete='restrict')
    request_line_id = fields.Many2one('cpla.recovery.request.line', index=True, readonly=True, ondelete='restrict')
    balance_id = fields.Many2one('cpla.recovery.balance', required=True, index=True, readonly=True, ondelete='restrict')
    settlement_id = fields.Many2one('cpla.recovery.settlement', index=True, readonly=True, ondelete='restrict')
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    proposed_amount_exact = fields.Char(required=True, readonly=True)
    approved_amount_exact = fields.Char(required=True, readonly=True, default='0')
    reason_code = fields.Selection(selection=WAIVER_REASONS, required=True, readonly=True)
    explanation = fields.Text(required=True, readonly=True)
    evidence_note = fields.Text(readonly=True)
    state = fields.Selection(selection=WAIVER_STATES, required=True, default='draft', readonly=True, index=True, copy=False)
    requested_by_id = fields.Many2one('res.users', required=True, readonly=True, index=True)
    requested_at = fields.Datetime(required=True, readonly=True)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    policy_id = fields.Many2one('cpla.recovery.policy', readonly=True, ondelete='restrict')
    policy_reference = fields.Char(readonly=True)
    required_level_count = fields.Integer(readonly=True, default=0)
    approval_level_done = fields.Integer(readonly=True, default=0)
    reduces_recovery = fields.Boolean(readonly=True, default=False)
    stale_source = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    counts_current = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    source_fingerprint = fields.Char(readonly=True)
    source_revision = fields.Integer(readonly=True)
    approval_snapshot = fields.Text(readonly=True, copy=False)
    supersedes_id = fields.Many2one('cpla.recovery.waiver', readonly=True, copy=False, index=True)
    fx_rate_exact = fields.Char(readonly=True, copy=False)
    fx_rate_date = fields.Date(readonly=True, copy=False)
    fx_rate_note = fields.Text(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A waiver is prepared from a current finance validation line.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An approved waiver cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A waiver cannot be deleted.')

    @api.model
    def prepare(self, validation_line_id, amount, reason_code, explanation, request_line_id=None, reduces_recovery=False, settlement_id=None, supersedes_id=None):
        self.env['cpla.recovery.request']._check_requester()
        if reason_code not in dict(WAIVER_REASONS):
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Choose a documented waiver reason.')
        if not (explanation or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A waiver needs an explanation.')
        line = self.env['cpla.finance.validation.line'].browse(validation_line_id).exists()
        if len(line) != 1:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Choose one finance validation line.')
        line.check_access('read')
        validation = line.validation_id
        self.env['cpla.recovery.request']._require_company(validation.company_id)
        self.env['cpla.recovery.request']._assert_validation_current(validation)
        if not line.counts_current or _money(line.approved_validated_exact) <= ZERO:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A waiver applies only to a current validated amount. A finance rejection is not a waiver.')
        number = _decimal(amount)
        if number is None or number <= ZERO:
            _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'A waiver amount must be positive.')
        quantized = _quantize(number, line.currency_id)
        request_line = self.env['cpla.recovery.request.line']
        if request_line_id:
            request_line = request_line.browse(request_line_id).exists()
            if len(request_line) != 1 or request_line.validation_line_id != line:
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'The waiver line does not match the finance line.')
            if request_line.company_id != line.company_id:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The waiver company does not match the finance line.')
        if reduces_recovery:
            if not request_line or _money(request_line.current_recovery_exact) < quantized:
                _fail(self.env, 'ALLOCATION_EXCEEDS_VALIDATED', 'A concession cannot reduce more than the current recovery target.')
        else:
            releasing = ZERO
            if supersedes_id:
                previous = self.browse(supersedes_id).exists()
                if previous and previous.counts_current and previous.validation_line_id == line:
                    releasing = _money(previous.approved_amount_exact)
            self.env['cpla.recovery.request']._assert_proposal_room(
                validation, {line.id: _text(quantized)}, extra_open=True, releasing=releasing,
            )
        balance = self.env['cpla.recovery.balance']._ensure(line)
        reference = self.env['ir.sequence'].with_company(line.company_id).next_by_code(WAIVER_SEQUENCE)
        if not reference:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'The waiver sequence is missing.')
        waiver = models.Model.create(self, [{
            'reference': reference,
            'company_id': line.company_id.id,
            'partner_id': validation.partner_id.id,
            'validation_id': validation.id,
            'validation_line_id': line.id,
            'request_id': request_line.request_id.id if request_line else False,
            'request_line_id': request_line.id if request_line else False,
            'balance_id': balance.id,
            'settlement_id': settlement_id or False,
            'currency_id': line.currency_id.id,
            'proposed_amount_exact': _text(quantized),
            'approved_amount_exact': '0',
            'reason_code': reason_code,
            'explanation': str(explanation).strip(),
            'state': 'draft',
            'requested_by_id': self.env.user.id,
            'requested_at': fields.Datetime.now(),
            'reduces_recovery': bool(reduces_recovery),
            'stale_source': False,
            'counts_current': False,
            'source_fingerprint': line.source_fingerprint or '',
            'source_revision': line.source_revision or 0,
            'supersedes_id': supersedes_id or False,
        }])
        if request_line:
            self.env['cpla.recovery.request']._log(
                request_line.request_id, 'waiver_requested', waiver.explanation,
                '0', waiver.proposed_amount_exact, waiver=waiver,
            )
        if settlement_id and reduces_recovery:
            settlement = self.env['cpla.recovery.settlement'].browse(settlement_id).exists()
            if (
                settlement
                and settlement.company_id == waiver.company_id
                and settlement.request_id == waiver.request_id
                and not settlement.additional_waiver_id
            ):
                models.Model.write(settlement, {'additional_waiver_id': waiver.id})
        return waiver

    def action_submit(self):
        self.env['cpla.recovery.request']._check_requester()
        for waiver in self:
            waiver._require_company()
            if waiver.state != 'draft':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Submit a draft waiver.')
            if waiver.requested_by_id != self.env.user:
                _fail(self.env, 'COMMERCIAL_AUTHORITY_DENIED', 'Only the requester can submit this waiver.')
            self.env['cpla.recovery.request']._assert_validation_current(waiver.validation_id)
            models.Model.write(waiver, {'state': 'submitted'})
        return True

    def action_request_approval(self):
        self.env['cpla.recovery.request']._check_requester()
        for waiver in self:
            waiver._require_company()
            if waiver.state != 'submitted':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Request waiver approval from a submitted waiver.')
            self.env['cpla.recovery.request']._assert_validation_current(waiver.validation_id)
            if not waiver.balance_id.counts_current:
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The allocation balance is not current.')
            policy = self.env['cpla.recovery.policy'].current_for(waiver.company_id)
            if not policy:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'This company has no approved commercial matrix.')
            amount = waiver._policy_amount(policy, _money(waiver.proposed_amount_exact))
            levels = policy._required_levels('waiver', amount)
            models.Model.write(waiver, {
                'state': 'pending_approval',
                'policy_id': policy.id,
                'policy_reference': policy.reference,
                'required_level_count': len(levels),
                'approval_level_done': 0,
            })
        return True

    def action_approve(self, reason):
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Waiver approval needs a reason.')
        for waiver in self:
            waiver._require_company()
            waiver.check_access('read')
            user = self.env.user
            approved_events = waiver._events('waiver_level_approved')
            if waiver.state == 'approved':
                acted = self.env['cpla.recovery.event'].search_count([
                    ('waiver_id', '=', waiver.id),
                    ('event_type', 'in', ('waiver_level_approved', 'waiver_approved')),
                    ('actor_id', '=', user.id),
                ])
                if acted:
                    continue
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'This waiver decision is already recorded.')
            if waiver.state != 'pending_approval':
                _fail(self.env, 'APPROVAL_LEVEL_PENDING', 'Approve only a waiver that is pending approval.')
            if waiver.stale_source or not waiver.balance_id.counts_current:
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'A stale finance source cannot take a new waiver approval.')
            policy = waiver.policy_id
            amount = waiver._policy_amount(policy, _money(waiver.proposed_amount_exact))
            levels = policy._required_levels('waiver', amount)
            done = approved_events
            if len(done) >= len(levels):
                continue
            level = levels[len(done)]
            waiver._assert_level_actor(user, level, done)
            try:
                with self.env.cr.savepoint():
                    waiver.balance_id.lock_for_update()
                    if len(done) + 1 < len(levels):
                        self._log(waiver, 'waiver_level_approved', str(reason).strip(), level)
                        models.Model.write(waiver, {'approval_level_done': len(done) + 1})
                    else:
                        waiver._finalize(user, str(reason).strip(), level)
            except IntegrityError:
                waiver.invalidate_recordset()
                if waiver.state == 'approved':
                    continue
                _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'Another waiver approval was recorded.')
            except LockError:
                _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'Another commercial allocation is being recorded.')
        return True

    def action_reject(self, reason):
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A waiver rejection needs a reason.')
        for waiver in self:
            waiver._require_company()
            waiver.check_access('read')
            if waiver.state != 'pending_approval':
                _fail(self.env, 'APPROVAL_LEVEL_PENDING', 'Reject a waiver only while approval is pending.')
            levels = waiver.policy_id._required_levels('waiver', waiver._policy_amount(waiver.policy_id, _money(waiver.proposed_amount_exact)))
            done = waiver._events('waiver_level_approved')
            level = levels[len(done)]
            waiver._assert_level_actor(self.env.user, level, done)
            self._log(waiver, 'waiver_rejected', str(reason).strip(), level)
            models.Model.write(waiver, {'state': 'rejected', 'approved_amount_exact': '0'})
        return True

    def action_open_correction(self, amount, explanation):
        """A new waiver revision. The original approved amount stays on the original record."""
        self.ensure_one()
        self.env['cpla.recovery.request']._check_requester()
        if self.state != 'approved' or not self.counts_current:
            _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Correct the current approved waiver.')
        return self.prepare(
            self.validation_line_id.id,
            amount,
            self.reason_code,
            explanation,
            request_line_id=self.request_line_id.id or None,
            reduces_recovery=self.reduces_recovery,
            settlement_id=self.settlement_id.id or None,
            supersedes_id=self.id,
        )

    def _finalize(self, user, reason, level):
        self.ensure_one()
        amount = _money(self.proposed_amount_exact)
        if self.supersedes_id and self.supersedes_id.state == 'approved' and self.supersedes_id.counts_current:
            previous = _money(self.supersedes_id.approved_amount_exact)
            delta = _arithmetic('sub', amount, previous)
            if self.reduces_recovery:
                self.env['cpla.recovery.balance']._move(self.balance_id, delta, _arithmetic('sub', ZERO, delta), ZERO, ZERO)
            else:
                self.env['cpla.recovery.balance']._move(self.balance_id, delta, ZERO, ZERO, ZERO)
            models.Model.write(self.supersedes_id, {'state': 'superseded', 'counts_current': False})
        elif self.reduces_recovery:
            self.env['cpla.recovery.balance']._move(
                self.balance_id, amount, _arithmetic('sub', ZERO, amount), ZERO, ZERO,
            )
        else:
            self.env['cpla.recovery.balance']._move(self.balance_id, amount, ZERO, ZERO, ZERO)
        if self.reduces_recovery and self.request_line_id:
            revised = _arithmetic('sub', _money(self.request_line_id.current_recovery_exact), amount)
            if self.supersedes_id and self.supersedes_id.reduces_recovery:
                revised = _arithmetic(
                    'sub',
                    _arithmetic('add', _money(self.request_line_id.current_recovery_exact), _money(self.supersedes_id.approved_amount_exact)),
                    amount,
                )
            models.Model.write(self.request_line_id, {
                'current_recovery_exact': _text(_quantize(revised, self.currency_id)),
            })
            request_total = ZERO
            for line in self.request_id.line_ids:
                current = _money(line.current_recovery_exact)
                if line == self.request_line_id:
                    current = revised
                request_total = _arithmetic('add', request_total, current)
            old_target = self.request_id.current_recovery_exact
            models.Model.write(self.request_id, {
                'current_recovery_exact': _text(_quantize(request_total, self.request_id.currency_id)),
            })
            self.env['cpla.recovery.request']._log(
                self.request_id, 'recovery_target_revised', reason,
                old_target, _text(_quantize(request_total, self.request_id.currency_id)),
                waiver=self,
            )
        text = _text(_quantize(amount, self.currency_id))
        snapshot = _canonical({
            'validation': self.validation_id.reference,
            'line_id': self.validation_line_id.id,
            'fingerprint': self.source_fingerprint,
            'amount': text,
            'policy': self.policy_reference,
            'reduces_recovery': self.reduces_recovery,
            'actor_id': user.id,
        })
        models.Model.write(self, {
            'state': 'approved',
            'approved_amount_exact': text,
            'approved_by_id': user.id,
            'approved_at': fields.Datetime.now(),
            'counts_current': True,
            'approval_level_done': self.required_level_count,
            'approval_snapshot': snapshot,
        })
        self._log(self, 'waiver_approved', reason, level)

    def _policy_amount(self, policy, amount):
        amount = _quantize(amount, self.currency_id)
        if self.currency_id == policy.currency_id:
            return amount
        rate = _decimal(self.fx_rate_exact)
        if rate is None or rate <= ZERO:
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'A recorded rate is required before this waiver currency can be approved.')
        return _quantize(_arithmetic('mul', amount, rate), policy.currency_id)

    def _assert_level_actor(self, user, level, done):
        xmlid = AUTHORITY_GROUPS.get(level.authority_group)
        if not xmlid or not _in_group(self.env, user, xmlid):
            if user._is_superuser() or _in_group(self.env, user, APP_ADMIN_GROUP):
                raise AccessError(self.env._(
                    'APPROVAL_MATRIX_MISSING: A technical administrator is not a commercial approver.'
                ))
            raise AccessError(self.env._(
                'APPROVAL_LIMIT_EXCEEDED: You are not the approver for this waiver level.'
            ))
        if self.policy_id.four_eyes_required:
            if user == self.requested_by_id:
                raise AccessError(self.env._(
                    'SELF_APPROVAL_PROHIBITED: The requester cannot approve this waiver.'
                ))
            if user in done.mapped('actor_id'):
                raise AccessError(self.env._(
                    'SELF_APPROVAL_PROHIBITED: One user cannot complete two waiver levels.'
                ))

    def _require_company(self):
        self.env['cpla.recovery.request']._require_company(self.company_id)

    def _events(self, event_type):
        return self.env['cpla.recovery.event'].search([
            ('waiver_id', '=', self.id),
            ('event_type', '=', event_type),
            ('level_sequence', '>', 0),
        ])

    def _log(self, waiver, event_type, reason, level):
        if not waiver.request_id:
            models.Model.create(self.env['cpla.recovery.event'], [{
                'company_id': waiver.company_id.id,
                'waiver_id': waiver.id,
                'event_type': event_type,
                'actor_id': self.env.user.id,
                'acted_at': fields.Datetime.now(),
                'old_value': '0',
                'new_value': waiver.proposed_amount_exact,
                'currency_id': waiver.currency_id.id,
                'reason': reason,
                'level_sequence': level.level_sequence if level else 0,
                'subject': 'waiver',
                'source_fingerprint': waiver.source_fingerprint or '',
            }])
            return
        self.env['cpla.recovery.request']._log(
            waiver.request_id, event_type, reason, '0', waiver.proposed_amount_exact,
            level=level, waiver=waiver,
        )

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

    def action_open_approve_wizard(self):
        return self._open_waiver_wizard('approve_waiver')

    def action_open_reject_wizard(self):
        return self._open_waiver_wizard('reject_waiver')

    def _open_waiver_wizard(self, operation):
        self.ensure_one()
        self.check_access('read')
        wizard = self.env['cpla.recovery.wizard'].create({
            'company_id': self.company_id.id,
            'operation': operation,
            'validation_id': self.validation_id.id,
            'validation_line_id': self.validation_line_id.id,
            'request_id': self.request_id.id,
            'request_line_id': self.request_line_id.id,
            'waiver_id': self.id,
        })
        return self._wizard_action(wizard.id)

    def _wizard_action(self, wizard_id):
        return {
            'type': 'ir.actions.act_window',
            'name': self.reference,
            'res_model': 'cpla.recovery.wizard',
            'res_id': wizard_id,
            'view_mode': 'form',
            'target': 'new',
        }


class RecoveryDispute(models.Model):
    """Customer challenge inside an approved recovery target. Not new leakage."""

    _name = 'cpla.recovery.dispute'
    _description = 'Customer Dispute'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This customer dispute reference already exists.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True, readonly=True)
    request_id = fields.Many2one('cpla.recovery.request', required=True, index=True, readonly=True, ondelete='restrict')
    request_line_id = fields.Many2one('cpla.recovery.request.line', required=True, index=True, readonly=True, ondelete='restrict')
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    disputed_amount_exact = fields.Char(required=True, readonly=True)
    category = fields.Selection(selection=DISPUTE_CATEGORIES, required=True, readonly=True)
    explanation = fields.Text(required=True, readonly=True)
    evidence_note = fields.Text(readonly=True)
    company_position = fields.Text(readonly=True)
    channel = fields.Selection(selection=CHANNELS, readonly=True)
    response_on = fields.Date(readonly=True)
    customer_contact = fields.Char(readonly=True)
    state = fields.Selection(selection=DISPUTE_STATES, required=True, default='open', readonly=True, index=True, copy=False)
    owner_id = fields.Many2one('res.users', required=True, readonly=True)
    reassessment_requested = fields.Boolean(readonly=True, default=False, copy=False)
    resolution_reason = fields.Text(readonly=True)
    resolved_at = fields.Datetime(readonly=True, copy=False)
    source_fingerprint = fields.Char(readonly=True)
    source_revision = fields.Integer(readonly=True)
    counts_current = fields.Boolean(readonly=True, default=False, index=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A dispute is opened from an approved recovery line.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A customer dispute cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A customer dispute cannot be deleted.')

    @api.model
    def open_dispute(self, request_line_id, amount, category, explanation, evidence_note, channel, response_on, customer_contact=''):
        self.env['cpla.recovery.request']._check_requester()
        self._require_evidence(explanation, evidence_note, channel, response_on)
        if category not in dict(DISPUTE_CATEGORIES):
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Choose a dispute category.')
        line = self.env['cpla.recovery.request.line'].browse(request_line_id).exists()
        if len(line) != 1:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Choose one approved recovery line.')
        line.check_access('read')
        request = line.request_id
        self.env['cpla.recovery.request']._require_company(request.company_id)
        if request.state != 'approved' or not line.counts_current:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A dispute must sit inside an approved current recovery target.')
        if request.partner_id != request.validation_id.partner_id or line.company_id != request.company_id:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The dispute customer or company does not match the recovery request.')
        number = _decimal(amount)
        if number is None or number <= ZERO:
            _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'A disputed amount must be positive.')
        quantized = _quantize(number, line.currency_id)
        if quantized > _money(line.current_recovery_exact):
            _fail(self.env, 'DISPUTE_EXCEEDS_TARGET', 'The disputed amount exceeds the current recovery target on this line.')
        reference = self.env['ir.sequence'].with_company(request.company_id).next_by_code(DISPUTE_SEQUENCE)
        if not reference:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'The dispute sequence is missing.')
        with self.env.cr.savepoint():
            line.balance_id.lock_for_update()
            self.env['cpla.recovery.balance']._move(line.balance_id, ZERO, ZERO, quantized, ZERO)
            dispute = models.Model.create(self, [{
                'reference': reference,
                'company_id': request.company_id.id,
                'partner_id': request.partner_id.id,
                'request_id': request.id,
                'request_line_id': line.id,
                'currency_id': line.currency_id.id,
                'disputed_amount_exact': _text(quantized),
                'category': category,
                'explanation': str(explanation).strip(),
                'evidence_note': str(evidence_note).strip(),
                'channel': channel,
                'response_on': response_on,
                'customer_contact': (customer_contact or '').strip(),
                'state': 'open',
                'owner_id': self.env.user.id,
                'reassessment_requested': False,
                'source_fingerprint': line.source_fingerprint or '',
                'source_revision': line.source_revision or 0,
                'counts_current': True,
            }])
        self.env['cpla.recovery.request']._log(
            request, 'dispute_opened', dispute.explanation, '0', dispute.disputed_amount_exact,
            dispute=dispute, evidence_note=dispute.evidence_note, channel=channel, response_on=response_on,
        )
        request._refresh_customer_state()
        return dispute

    @api.model
    def record_acknowledgement(self, request_line_id, amount, evidence_note, channel, response_on, customer_contact=''):
        """Record an evidenced customer acknowledgement. This is not cash and not an invoice."""
        self.env['cpla.recovery.request']._check_requester()
        if not (evidence_note or '').strip() or channel not in dict(CHANNELS) or not response_on:
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Acknowledgement needs evidence, a channel, and the date it happened.')
        line = self.env['cpla.recovery.request.line'].browse(request_line_id).exists()
        if len(line) != 1 or line.request_id.state != 'approved' or not line.counts_current:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Acknowledge an amount on an approved current recovery line.')
        line.check_access('read')
        self.env['cpla.recovery.request']._require_company(line.company_id)
        number = _decimal(amount)
        if number is None or number <= ZERO:
            _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'An acknowledged amount must be positive.')
        quantized = _quantize(number, line.currency_id)
        with self.env.cr.savepoint():
            line.balance_id.lock_for_update()
            self.env['cpla.recovery.balance']._move(line.balance_id, ZERO, ZERO, ZERO, quantized)
            self.env['cpla.recovery.request']._log(
                line.request_id, 'customer_acknowledged', str(evidence_note).strip(),
                '0', _text(quantized), evidence_note=str(evidence_note).strip(),
                channel=channel, response_on=response_on,
            )
        line.request_id._refresh_customer_state()
        return True

    def action_request_source_review(self, reason):
        """Flag the dispute for DEV-14/15 review. This does not rerun the audit."""
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A source-review request needs a reason.')
        self.env['cpla.recovery.request']._check_requester()
        for dispute in self:
            self.env['cpla.recovery.request']._require_company(dispute.company_id)
            if dispute.state in ('withdrawn', 'resolved_agreed', 'resolved_rejected'):
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'This dispute is already closed.')
            models.Model.write(dispute, {
                'state': 'escalated',
                'reassessment_requested': True,
                'company_position': str(reason).strip(),
            })
            self.env['cpla.recovery.request']._log(
                dispute.request_id, 'dispute_escalated', str(reason).strip(),
                dispute.disputed_amount_exact, dispute.disputed_amount_exact, dispute=dispute,
            )
        return True

    def action_withdraw(self, reason):
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Dispute withdrawal needs a reason.')
        self.env['cpla.recovery.request']._check_requester()
        for dispute in self:
            self.env['cpla.recovery.request']._require_company(dispute.company_id)
            if dispute.state == 'withdrawn':
                continue
            if not dispute.counts_current:
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'This dispute is not a current allocation.')
            with self.env.cr.savepoint():
                dispute.request_line_id.balance_id.lock_for_update()
                self.env['cpla.recovery.balance']._move(
                    dispute.request_line_id.balance_id,
                    ZERO, ZERO, _arithmetic('sub', ZERO, _money(dispute.disputed_amount_exact)), ZERO,
                )
                models.Model.write(dispute, {
                    'state': 'withdrawn',
                    'counts_current': False,
                    'resolution_reason': str(reason).strip(),
                    'resolved_at': fields.Datetime.now(),
                })
            self.env['cpla.recovery.request']._log(
                dispute.request_id, 'dispute_withdrawn', str(reason).strip(),
                dispute.disputed_amount_exact, '0', dispute=dispute,
            )
            dispute.request_id._refresh_customer_state()
        return True

    @api.model
    def _require_evidence(self, explanation, evidence_note, channel, response_on):
        if not (explanation or '').strip() or not (evidence_note or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A customer position needs an explanation and evidence.')
        if channel not in dict(CHANNELS) or not response_on:
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Record the channel and the date of the customer communication.')


class RecoverySettlement(models.Model):
    """Negotiation record. Internal approval is not customer acceptance and not cash."""

    _name = 'cpla.recovery.settlement'
    _description = 'Negotiated Settlement'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This settlement reference already exists.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True, readonly=True)
    request_id = fields.Many2one('cpla.recovery.request', required=True, index=True, readonly=True, ondelete='restrict')
    validation_id = fields.Many2one('cpla.finance.validation', required=True, index=True, readonly=True, ondelete='restrict')
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    proposed_amount_exact = fields.Char(required=True, readonly=True)
    additional_waiver_exact = fields.Char(required=True, readonly=True, default='0')
    revised_target_exact = fields.Char(required=True, readonly=True, default='0')
    counteroffer_exact = fields.Char(readonly=True, copy=False)
    summary = fields.Text(required=True, readonly=True)
    reason = fields.Text(required=True, readonly=True)
    internal_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('under_review', 'Under review'),
            ('approved', 'Internally approved'),
            ('rejected', 'Rejected'),
        ],
        required=True,
        default='draft',
        readonly=True,
        index=True,
        copy=False,
    )
    customer_state = fields.Selection(
        selection=[
            ('not_sent', 'Not sent'),
            ('proposed', 'Proposed to customer'),
            ('response_pending', 'Response pending'),
            ('accepted', 'Accepted with evidence'),
            ('rejected', 'Rejected'),
            ('counteroffer', 'Counteroffer received'),
            ('withdrawn', 'Withdrawn'),
        ],
        required=True,
        default='not_sent',
        readonly=True,
        index=True,
        copy=False,
    )
    execution_state = fields.Selection(
        selection=[
            ('not_ready', 'Not ready'),
            ('pending_conditions', 'Pending conditions'),
            ('ready_for_dev17', 'Ready for DEV-17'),
            ('suspended_source_changed', 'Suspended because the source changed'),
            ('superseded', 'Superseded'),
        ],
        required=True,
        default='not_ready',
        readonly=True,
        index=True,
        copy=False,
    )
    proposed_by_id = fields.Many2one('res.users', required=True, readonly=True)
    proposed_at = fields.Datetime(required=True, readonly=True)
    policy_id = fields.Many2one('cpla.recovery.policy', readonly=True, ondelete='restrict')
    policy_reference = fields.Char(readonly=True)
    required_level_count = fields.Integer(readonly=True, default=0)
    approval_level_done = fields.Integer(readonly=True, default=0)
    acceptance_evidence = fields.Text(readonly=True, copy=False)
    acceptance_channel = fields.Selection(selection=CHANNELS, readonly=True, copy=False)
    acceptance_on = fields.Date(readonly=True, copy=False)
    counteroffer_evidence = fields.Text(readonly=True, copy=False)
    source_fingerprint = fields.Char(readonly=True)
    source_revision = fields.Integer(readonly=True)
    approval_snapshot = fields.Text(readonly=True, copy=False)
    counts_current = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    supersedes_id = fields.Many2one('cpla.recovery.settlement', readonly=True, copy=False, index=True)
    additional_waiver_id = fields.Many2one('cpla.recovery.waiver', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A settlement is proposed from an approved recovery request.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A settlement cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A settlement cannot be deleted.')

    @api.model
    def propose(self, request_id, proposed_amount, additional_waiver, summary, reason, supersedes_id=None):
        self.env['cpla.recovery.request']._check_requester()
        if not (summary or '').strip() or not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A settlement proposal needs a summary and a commercial reason.')
        request = self.env['cpla.recovery.request'].browse(request_id).exists()
        if len(request) != 1 or request.state != 'approved':
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Propose a settlement from an approved recovery request.')
        request.check_access('read')
        self.env['cpla.recovery.request']._require_company(request.company_id)
        if request.stale_source or not request.validation_id.is_current:
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'A stale finance source cannot take a new settlement proposal.')
        proposed = _decimal(proposed_amount)
        extra = _decimal(additional_waiver if additional_waiver not in (None, False, '') else '0')
        if proposed is None or proposed <= ZERO or extra is None or extra < ZERO:
            _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'The settlement amount must be positive. An extra waiver cannot be negative.')
        proposed = _quantize(proposed, request.currency_id)
        extra = _quantize(extra, request.currency_id)
        current_target = _money(request.current_recovery_exact)
        if extra and _arithmetic('sub', current_target, extra) != proposed and _arithmetic('add', proposed, extra) != current_target:
            _fail(
                self.env,
                'ALLOCATION_EXCEEDS_VALIDATED',
                'The proposed settlement plus the additional waiver must equal the current recovery target.',
            )
        if not extra and proposed != current_target:
            _fail(self.env, 'ALLOCATION_EXCEEDS_VALIDATED', 'A settlement without a waiver cannot change the recovery target.')
        reference = self.env['ir.sequence'].with_company(request.company_id).next_by_code(SETTLEMENT_SEQUENCE)
        if not reference:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'The settlement sequence is missing.')
        previous = self.browse(supersedes_id).exists() if supersedes_id else self.env['cpla.recovery.settlement']
        if previous:
            models.Model.write(previous, {'counts_current': False, 'execution_state': 'superseded'})
        settlement = models.Model.create(self, [{
            'reference': reference,
            'company_id': request.company_id.id,
            'partner_id': request.partner_id.id,
            'request_id': request.id,
            'validation_id': request.validation_id.id,
            'currency_id': request.currency_id.id,
            'proposed_amount_exact': _text(proposed),
            'additional_waiver_exact': _text(extra),
            'revised_target_exact': _text(proposed),
            'summary': str(summary).strip(),
            'reason': str(reason).strip(),
            'internal_state': 'draft',
            'customer_state': 'not_sent',
            'execution_state': 'not_ready',
            'proposed_by_id': self.env.user.id,
            'proposed_at': fields.Datetime.now(),
            'source_fingerprint': request.source_fingerprint or '',
            'source_revision': request.source_revision or 0,
            'counts_current': True,
            'supersedes_id': previous.id if previous else False,
        }])
        self.env['cpla.recovery.request']._log(
            request, 'settlement_proposed', settlement.summary,
            request.current_recovery_exact, settlement.proposed_amount_exact, settlement=settlement,
        )
        return settlement

    def action_submit(self):
        self.env['cpla.recovery.request']._check_requester()
        for settlement in self:
            self.env['cpla.recovery.request']._require_company(settlement.company_id)
            if settlement.internal_state != 'draft':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Submit a draft settlement.')
            if settlement.proposed_by_id != self.env.user:
                _fail(self.env, 'COMMERCIAL_AUTHORITY_DENIED', 'Only the proposer can submit this settlement.')
            models.Model.write(settlement, {'internal_state': 'submitted'})
        return True

    def action_request_approval(self):
        self.env['cpla.recovery.request']._check_requester()
        for settlement in self:
            self.env['cpla.recovery.request']._require_company(settlement.company_id)
            if settlement.internal_state != 'submitted':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Request settlement approval from a submitted proposal.')
            if settlement.request_id.stale_source:
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The finance source is stale.')
            policy = self.env['cpla.recovery.policy'].current_for(settlement.company_id)
            if not policy:
                _fail(self.env, 'APPROVAL_MATRIX_MISSING', 'This company has no approved commercial matrix.')
            amount = _money(settlement.additional_waiver_exact) or _money(settlement.proposed_amount_exact)
            levels = policy._required_levels('settlement', amount)
            models.Model.write(settlement, {
                'internal_state': 'under_review',
                'policy_id': policy.id,
                'policy_reference': policy.reference,
                'required_level_count': len(levels),
                'approval_level_done': 0,
            })
        return True

    def action_approve_internal(self, reason):
        """Internal approval only. Customer acceptance stays separate."""
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Internal settlement approval needs a reason.')
        for settlement in self:
            self.env['cpla.recovery.request']._require_company(settlement.company_id)
            settlement.check_access('read')
            user = self.env.user
            done = settlement._events('settlement_level_approved')
            if settlement.internal_state == 'approved' and done.filtered(lambda event: event.actor_id == user):
                continue
            if settlement.internal_state != 'under_review':
                _fail(self.env, 'APPROVAL_LEVEL_PENDING', 'Approve a settlement only while internal review is open.')
            if settlement.customer_state == 'accepted':
                _fail(self.env, 'SETTLEMENT_NOT_ACCEPTED', 'Customer acceptance cannot be recorded before internal approval, and approval does not invent it.')
            policy = settlement.policy_id
            amount = _money(settlement.additional_waiver_exact) or _money(settlement.proposed_amount_exact)
            levels = policy._required_levels('settlement', amount)
            if len(done) >= len(levels):
                continue
            level = levels[len(done)]
            settlement._assert_level_actor(user, level, done)
            try:
                with self.env.cr.savepoint():
                    self.env['cpla.recovery.request']._log(
                        settlement.request_id, 'settlement_level_approved', str(reason).strip(),
                        settlement.request_id.current_recovery_exact, settlement.request_id.current_recovery_exact,
                        level=level, settlement=settlement,
                    )
                    if len(done) + 1 < len(levels):
                        models.Model.write(settlement, {'approval_level_done': len(done) + 1})
                    else:
                        models.Model.write(settlement, {
                            'internal_state': 'approved',
                            'approval_level_done': len(levels),
                            'approval_snapshot': _canonical({
                                'proposed': settlement.proposed_amount_exact,
                                'additional_waiver': settlement.additional_waiver_exact,
                                'customer_state': settlement.customer_state,
                                'policy': settlement.policy_reference,
                                'actor_id': user.id,
                            }),
                        })
            except IntegrityError:
                settlement.invalidate_recordset()
                if settlement.internal_state == 'approved':
                    continue
                _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'Another settlement approval was recorded.')
        return True

    def action_record_counteroffer(self, amount, evidence_note, channel, response_on):
        """Store the customer offer. It does not change the target, the waiver, or cash."""
        self.ensure_one()
        self.env['cpla.recovery.request']._check_requester()
        if not (evidence_note or '').strip() or channel not in dict(CHANNELS) or not response_on:
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A counteroffer needs evidence, a channel, and the date it happened.')
        number = _decimal(amount)
        if number is None or number <= ZERO:
            _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'A counteroffer must be a positive amount.')
        self.env['cpla.recovery.request']._require_company(self.company_id)
        quantized = _quantize(number, self.currency_id)
        before = self.request_id.current_recovery_exact
        models.Model.write(self, {
            'counteroffer_exact': _text(quantized),
            'counteroffer_evidence': str(evidence_note).strip(),
            'customer_state': 'counteroffer',
        })
        self.env['cpla.recovery.request']._log(
            self.request_id, 'counteroffer_recorded', str(evidence_note).strip(),
            before, _text(quantized), settlement=self, evidence_note=str(evidence_note).strip(),
            channel=channel, response_on=response_on,
        )
        if self.request_id.current_recovery_exact != before:
            _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A counteroffer must not change the recovery target.')
        return True

    def action_record_customer_acceptance(self, evidence_note, channel, response_on):
        """Evidence of customer agreement. This is not collected cash and not an invoice."""
        self.ensure_one()
        self.env['cpla.recovery.request']._check_requester()
        if self.internal_state != 'approved':
            _fail(self.env, 'SETTLEMENT_NOT_ACCEPTED', 'Internal approval must be recorded before customer acceptance.')
        if not (evidence_note or '').strip() or channel not in dict(CHANNELS) or not response_on:
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Customer acceptance needs evidence, a channel, and the date it happened.')
        self.env['cpla.recovery.request']._require_company(self.company_id)
        if self.request_id.stale_source:
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'Customer acceptance cannot refresh a stale finance source.')
        models.Model.write(self, {
            'customer_state': 'accepted',
            'acceptance_evidence': str(evidence_note).strip(),
            'acceptance_channel': channel,
            'acceptance_on': response_on,
            'execution_state': 'pending_conditions',
        })
        self.env['cpla.recovery.request']._log(
            self.request_id, 'customer_acceptance_recorded', str(evidence_note).strip(),
            self.proposed_amount_exact, self.proposed_amount_exact, settlement=self,
            evidence_note=str(evidence_note).strip(), channel=channel, response_on=response_on,
        )
        return True

    def _assert_level_actor(self, user, level, done):
        xmlid = AUTHORITY_GROUPS.get(level.authority_group)
        if not xmlid or not _in_group(self.env, user, xmlid):
            if user._is_superuser() or _in_group(self.env, user, APP_ADMIN_GROUP):
                raise AccessError(self.env._(
                    'APPROVAL_MATRIX_MISSING: A technical administrator is not a commercial approver.'
                ))
            raise AccessError(self.env._(
                'APPROVAL_LIMIT_EXCEEDED: You are not the approver for this settlement level.'
            ))
        if self.policy_id.four_eyes_required:
            if user == self.proposed_by_id:
                raise AccessError(self.env._(
                    'SELF_APPROVAL_PROHIBITED: The proposer cannot approve this settlement.'
                ))
            if user in done.mapped('actor_id'):
                raise AccessError(self.env._(
                    'SELF_APPROVAL_PROHIBITED: One user cannot complete two settlement levels.'
                ))

    def _events(self, event_type):
        return self.env['cpla.recovery.event'].search([
            ('settlement_id', '=', self.id),
            ('event_type', '=', event_type),
            ('level_sequence', '>', 0),
        ])

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

    def action_open_approve_wizard(self):
        self.ensure_one()
        self.check_access('read')
        wizard = self.env['cpla.recovery.wizard'].create({
            'company_id': self.company_id.id,
            'operation': 'approve_settlement',
            'request_id': self.request_id.id,
            'validation_id': self.validation_id.id,
            'settlement_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': self.reference,
            'res_model': 'cpla.recovery.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }


class RecoveryEvent(models.Model):
    """Append-only commercial event. The actor and the time come from the server."""

    _name = 'cpla.recovery.event'
    _description = 'Commercial Recovery Event'
    _order = 'id'
    _check_company_auto = True

    _request_level_unique = models.UniqueIndex(
        "(request_id, level_sequence, subject) WHERE event_type IN ('recovery_level_approved', 'handoff_authorized', 'settlement_level_approved') AND level_sequence > 0",
        'This commercial approval level is already recorded.',
    )
    _waiver_level_unique = models.UniqueIndex(
        "(waiver_id, level_sequence) WHERE event_type = 'waiver_level_approved' AND level_sequence > 0",
        'This waiver approval level is already recorded.',
    )

    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    request_id = fields.Many2one('cpla.recovery.request', index=True, readonly=True, ondelete='restrict')
    waiver_id = fields.Many2one('cpla.recovery.waiver', index=True, readonly=True, ondelete='restrict')
    dispute_id = fields.Many2one('cpla.recovery.dispute', index=True, readonly=True, ondelete='restrict')
    settlement_id = fields.Many2one('cpla.recovery.settlement', index=True, readonly=True, ondelete='restrict')
    event_type = fields.Selection(
        selection=[
            ('recovery_requested', 'Recovery request created'),
            ('recovery_submitted', 'Recovery submitted'),
            ('evidence_requested', 'Evidence requested'),
            ('recovery_level_approved', 'Recovery level approved'),
            ('recovery_approved', 'Recovery approved'),
            ('recovery_rejected', 'Recovery rejected'),
            ('recovery_withdrawn', 'Recovery withdrawn'),
            ('customer_discussion', 'Customer discussion opened'),
            ('waiver_requested', 'Waiver requested'),
            ('waiver_level_approved', 'Waiver level approved'),
            ('waiver_approved', 'Waiver approved'),
            ('waiver_rejected', 'Waiver rejected'),
            ('dispute_opened', 'Dispute opened'),
            ('dispute_escalated', 'Dispute escalated'),
            ('dispute_withdrawn', 'Dispute withdrawn'),
            ('customer_acknowledged', 'Customer acknowledgement recorded'),
            ('counteroffer_recorded', 'Customer counteroffer recorded'),
            ('settlement_proposed', 'Settlement proposed'),
            ('settlement_level_approved', 'Settlement level approved'),
            ('customer_acceptance_recorded', 'Customer acceptance recorded'),
            ('recovery_target_revised', 'Recovery target revised'),
            ('source_stale', 'Source marked stale'),
            ('handoff_authorized', 'Accounting handoff authorized'),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    actor_id = fields.Many2one('res.users', readonly=True, index=True)
    acted_at = fields.Datetime(readonly=True, index=True)
    old_value = fields.Char(readonly=True)
    new_value = fields.Char(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    reason = fields.Text(readonly=True)
    evidence_note = fields.Text(readonly=True)
    channel = fields.Selection(selection=CHANNELS, readonly=True)
    response_on = fields.Date(readonly=True)
    level_sequence = fields.Integer(readonly=True, default=0)
    subject = fields.Char(readonly=True)
    source_fingerprint = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Commercial events are recorded by the commercial action.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A commercial event cannot be edited.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A commercial event cannot be deleted.')


class RecoveryBalanceService(models.Model):
    _inherit = 'cpla.recovery.balance'

    @api.model
    def _ensure(self, line):
        if line.company_id != line.validation_id.company_id:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The finance line company does not match the validation.')
        balance = self.search([('validation_line_id', '=', line.id)], limit=1)
        if balance:
            if not balance.counts_current or balance.company_id != line.company_id:
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The commercial balance for this finance line is not current.')
            return balance
        try:
            with self.env.cr.savepoint():
                balance = models.Model.create(self, [{
                    'company_id': line.company_id.id,
                    'validation_id': line.validation_id.id,
                    'validation_line_id': line.id,
                    'currency_id': line.currency_id.id,
                    'validated_exact': _text(_quantize(_money(line.approved_validated_exact), line.currency_id)),
                    'waiver_exact': '0',
                    'recovery_exact': '0',
                    'dispute_exact': '0',
                    'acknowledged_exact': '0',
                    'counts_current': True,
                    'source_fingerprint': line.source_fingerprint or '',
                    'source_revision': line.source_revision or 0,
                }])
        except IntegrityError:
            balance = self.search([('validation_line_id', '=', line.id)], limit=1)
            if not balance:
                _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'The commercial balance could not be recorded.')
        return balance

    @api.model
    def _move(self, balance, waiver_delta, recovery_delta, dispute_delta, acknowledgement_delta):
        if not balance.counts_current:
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'A stale allocation balance cannot take a new amount.')
        balance.invalidate_recordset()
        currency = balance.currency_id
        validated = _money(balance.validated_exact)
        waiver = _quantize(_arithmetic('add', _money(balance.waiver_exact), waiver_delta), currency)
        recovery = _quantize(_arithmetic('add', _money(balance.recovery_exact), recovery_delta), currency)
        dispute = _quantize(_arithmetic('add', _money(balance.dispute_exact), dispute_delta), currency)
        acknowledged = _quantize(_arithmetic('add', _money(balance.acknowledged_exact), acknowledgement_delta), currency)
        if min(waiver, recovery, dispute, acknowledged) < ZERO:
            _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'A commercial allocation cannot be negative.')
        if _arithmetic('add', waiver, recovery) > validated:
            _fail(self.env, 'ALLOCATION_EXCEEDS_VALIDATED', 'Waiver plus recovery exceeds the finance-validated amount.')
        if _arithmetic('add', dispute, acknowledged) > recovery:
            _fail(self.env, 'DISPUTE_EXCEEDS_TARGET', 'Dispute plus acknowledgement exceeds the current recovery target.')
        models.Model.write(balance, {
            'waiver_exact': _text(waiver),
            'recovery_exact': _text(recovery),
            'dispute_exact': _text(dispute),
            'acknowledged_exact': _text(acknowledged),
        })
        return balance

    @api.model
    def position_for(self, validation):
        validated = waiver = recovery = dispute = acknowledged = ZERO
        currency = validation.review_currency_id
        for line in validation.line_ids.filtered('counts_current'):
            if line.validation_id.stale_source or not line.validation_id.is_current:
                continue
            validated = _arithmetic('add', validated, _money(line.approved_validated_exact))
            balance = self.search([
                ('validation_line_id', '=', line.id),
                ('counts_current', '=', True),
            ], limit=1)
            if not balance:
                continue
            waiver = _arithmetic('add', waiver, _money(balance.waiver_exact))
            recovery = _arithmetic('add', recovery, _money(balance.recovery_exact))
            dispute = _arithmetic('add', dispute, _money(balance.dispute_exact))
            acknowledged = _arithmetic('add', acknowledged, _money(balance.acknowledged_exact))
        unallocated = _arithmetic('sub', validated, _arithmetic('add', waiver, recovery))
        unanswered = _arithmetic('sub', recovery, _arithmetic('add', dispute, acknowledged))
        return {
            'validated': _text(_quantize(validated, currency)) if currency else _text(validated),
            'waiver': _text(_quantize(waiver, currency)) if currency else _text(waiver),
            'recovery_target': _text(_quantize(recovery, currency)) if currency else _text(recovery),
            'unallocated': _text(_quantize(unallocated, currency)) if currency else _text(unallocated),
            'disputed': _text(_quantize(dispute, currency)) if currency else _text(dispute),
            'acknowledged': _text(_quantize(acknowledged, currency)) if currency else _text(acknowledged),
            'unanswered': _text(_quantize(unanswered, currency)) if currency else _text(unanswered),
            'billed': '0',
            'collected': '0',
            'currency_id': currency.id,
        }


class RecoveryWizard(models.TransientModel):
    """Typed commercial amounts. The wizard does not post an invoice."""

    _name = 'cpla.recovery.wizard'
    _description = 'Commercial Recovery Wizard'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True)
    operation = fields.Selection(
        selection=[
            ('recovery', 'Prepare recovery'),
            ('waiver', 'Prepare waiver'),
            ('dispute', 'Open dispute'),
            ('acknowledgement', 'Record acknowledgement'),
            ('settlement', 'Propose settlement'),
            ('counteroffer', 'Record counteroffer'),
            ('acceptance', 'Record customer acceptance'),
            ('approve_recovery', 'Approve recovery'),
            ('reject_recovery', 'Reject recovery'),
            ('withdraw_recovery', 'Withdraw recovery'),
            ('handoff', 'Authorize accounting handoff'),
            ('approve_waiver', 'Approve waiver'),
            ('reject_waiver', 'Reject waiver'),
            ('approve_settlement', 'Approve settlement internally'),
        ],
        required=True,
    )
    validation_id = fields.Many2one('cpla.finance.validation')
    validation_line_id = fields.Many2one('cpla.finance.validation.line')
    request_id = fields.Many2one('cpla.recovery.request')
    request_line_id = fields.Many2one('cpla.recovery.request.line')
    waiver_id = fields.Many2one('cpla.recovery.waiver')
    settlement_id = fields.Many2one('cpla.recovery.settlement')
    amount_exact = fields.Char()
    additional_waiver_exact = fields.Char()
    reason_code = fields.Selection(selection=WAIVER_REASONS)
    category = fields.Selection(selection=DISPUTE_CATEGORIES)
    explanation = fields.Text()
    evidence_note = fields.Text()
    summary = fields.Text()
    channel = fields.Selection(selection=CHANNELS)
    response_on = fields.Date()
    reduces_recovery = fields.Boolean(default=False)

    def action_apply(self):
        self.ensure_one()
        self.env['cpla.recovery.request']._check_requester()
        self.env['cpla.recovery.request']._require_company(self.company_id)
        if self.operation == 'recovery':
            amounts = None
            if self.validation_line_id and self.amount_exact:
                amounts = {self.validation_line_id.id: self.amount_exact}
            request = self.env['cpla.recovery.request'].prepare_from_validation(self.validation_id.id, amounts)
            return request.action_open_form()
        if self.operation == 'waiver':
            waiver = self.env['cpla.recovery.waiver'].prepare(
                self.validation_line_id.id,
                self.amount_exact,
                self.reason_code,
                self.explanation,
                request_line_id=self.request_line_id.id or None,
                reduces_recovery=self.reduces_recovery,
            )
            return waiver.action_open_form()
        if self.operation == 'dispute':
            dispute = self.env['cpla.recovery.dispute'].open_dispute(
                self.request_line_id.id, self.amount_exact, self.category,
                self.explanation, self.evidence_note, self.channel, self.response_on,
            )
            return dispute.request_id.action_open_form()
        if self.operation == 'acknowledgement':
            self.env['cpla.recovery.dispute'].record_acknowledgement(
                self.request_line_id.id, self.amount_exact, self.evidence_note,
                self.channel, self.response_on,
            )
            return self.request_line_id.request_id.action_open_form()
        if self.operation == 'settlement':
            settlement = self.env['cpla.recovery.settlement'].propose(
                self.request_id.id, self.amount_exact, self.additional_waiver_exact or '0',
                self.summary, self.explanation,
            )
            return settlement.action_open_form()
        if self.operation == 'counteroffer':
            self.settlement_id.action_record_counteroffer(
                self.amount_exact, self.evidence_note, self.channel, self.response_on,
            )
            return self.settlement_id.action_open_form()
        if self.operation == 'acceptance':
            self.settlement_id.action_record_customer_acceptance(
                self.evidence_note, self.channel, self.response_on,
            )
            return self.settlement_id.action_open_form()
        reason = (self.explanation or '').strip()
        if self.operation == 'approve_recovery':
            self.request_id.action_approve(reason)
            return self.request_id.action_open_form()
        if self.operation == 'reject_recovery':
            self.request_id.action_reject(reason)
            return self.request_id.action_open_form()
        if self.operation == 'withdraw_recovery':
            self.request_id.action_withdraw(reason)
            return self.request_id.action_open_form()
        if self.operation == 'handoff':
            self.request_id.action_authorize_handoff(reason)
            return self.request_id.action_open_form()
        if self.operation == 'approve_waiver':
            self.waiver_id.action_approve(reason)
            return self.waiver_id.action_open_form()
        if self.operation == 'reject_waiver':
            self.waiver_id.action_reject(reason)
            return self.waiver_id.action_open_form()
        if self.operation == 'approve_settlement':
            self.settlement_id.action_approve_internal(reason)
            return self.settlement_id.action_open_form()
        _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Choose a commercial operation.')
