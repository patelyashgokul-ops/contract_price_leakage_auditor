"""DEV-17 accounting recovery billing.

Commercial authorization stays on the DEV-16 request. This file creates or
links the accounting document and classifies what Odoo actually posted and
reconciled. It does not recompute leakage, post a write-off, or send a
collection demand. A credit reduces recovery principal only when the credit
document is the reversal of this billing or a posted adjustment of it.
"""
import json
from decimal import Decimal

from psycopg2 import IntegrityError

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, LockError, UserError

from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    AUDITOR_GROUP,
    FINANCE_MANAGER_GROUP,
    _arithmetic,
    _decimal,
    _text,
)
from odoo.addons.contract_price_leakage_auditor.models.recovery_authorization import (
    _fail,
    _in_group,
    _money,
    _quantize,
)

MODULE = 'contract_price_leakage_auditor'
INVOICE_GROUP = 'account.group_account_invoice'
POLICY_SEQUENCE = 'cpla.recovery.billing.policy'
BILLING_SEQUENCE = 'cpla.recovery.billing'
ZERO = Decimal('0')
OPEN_RESERVE = (
    'draft',
    'handoff_verified',
    'accounting_review',
    'document_prepared',
    'draft_document_created',
    'ready_to_post',
)
CURRENT_POSTED = ('posted', 'partially_reversed')
RELEASED = ('cancelled', 'superseded', 'fully_reversed')
CREATING_METHODS = ('standalone_invoice', 'debit_note')
REDUCING = ('verified_cash', 'credit_note', 'write_off', 'other_settlement', 'advance')
BILLING_METHODS = [
    ('existing_document', 'Link an existing posted document'),
    ('debit_note', 'Customer debit note'),
    ('standalone_invoice', 'Standalone recovery invoice'),
    ('manual_handoff', 'Manual accounting handoff'),
]
TAX_TREATMENTS = [
    ('unresolved', 'Unresolved'),
    ('untaxed_explicit', 'Untaxed recovery principal'),
    ('taxes_on_policy', 'Taxes selected on this policy'),
]
BILLING_STATES = [
    ('draft', 'Draft'),
    ('handoff_verified', 'Handoff verified'),
    ('accounting_review', 'Accounting review'),
    ('document_prepared', 'Document prepared'),
    ('draft_document_created', 'Draft document created'),
    ('ready_to_post', 'Ready to post'),
    ('posted', 'Posted'),
    ('partially_reversed', 'Partially reversed'),
    ('fully_reversed', 'Fully reversed'),
    ('blocked', 'Blocked'),
    ('cancelled', 'Cancelled before posting'),
    ('superseded', 'Superseded'),
]
LINK_SOURCES = [
    ('created_by_app', 'Created by this billing action'),
    ('existing_verified', 'Existing verified accounting document'),
]
EVIDENCE_KINDS = [
    ('verified_cash', 'Bank-verified cash principal'),
    ('unconfirmed_payment', 'Payment without the required bank evidence'),
    ('credit_note', 'Customer credit note'),
    ('write_off', 'Classified write-off'),
    ('fx_difference', 'Exchange difference'),
    ('advance', 'Customer advance applied'),
    ('other_settlement', 'Other accounting settlement'),
    ('unknown_credit', 'Credit whose recovery link is not supported'),
]
CREDIT_CATEGORIES = [
    ('FULL_RECOVERY_BILL_REVERSAL', 'Full recovery bill reversal'),
    ('PARTIAL_RECOVERY_BILL_REVERSAL', 'Partial recovery bill reversal'),
    ('SETTLEMENT_CREDIT', 'Settlement credit'),
    ('TAX_ONLY_CREDIT', 'Tax-only credit'),
    ('DUPLICATE_BILLING_CORRECTION', 'Duplicate billing correction'),
    ('UNRELATED_CUSTOMER_CREDIT', 'Unrelated customer credit'),
    ('UNKNOWN_CREDIT_ALLOCATION', 'Unknown credit allocation'),
]
VERIFICATION_STATES = {
    'verified_cash': 'BANK_VERIFIED_CASH',
    'unconfirmed_payment': 'PAYMENT_PENDING_BANK_VERIFICATION',
    'credit_note': 'CREDIT_NOTE_SETTLEMENT',
    'write_off': 'WRITE_OFF_SETTLEMENT',
    'advance': 'NONCASH_OFFSET',
    'other_settlement': 'NONCASH_OFFSET',
    'unknown_credit': 'UNVERIFIED_SETTLEMENT',
}
AGING_LABELS = ('not_yet_due', 'days_1_30', 'days_31_60', 'days_61_90', 'days_over_90')


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)


def _sum_text(values):
    total = ZERO
    for value in values:
        total = _arithmetic('add', total, _money(value))
    return total


class RecoveryBillingPolicy(models.Model):
    """Company billing policy. Nothing here is seeded."""

    _name = 'cpla.recovery.billing.policy'
    _description = 'Recovery Billing Policy'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This recovery billing policy reference already exists.',
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
    is_current = fields.Boolean(readonly=True, default=False, index=True, copy=False)
    billing_method = fields.Selection(selection=BILLING_METHODS, required=True, default='manual_handoff')
    journal_id = fields.Many2one('account.journal', check_company=True)
    revenue_account_id = fields.Many2one('account.account', check_company=True)
    product_id = fields.Many2one('product.product', check_company=True)
    tax_ids = fields.Many2many(
        'account.tax',
        'cpla_billing_policy_tax_rel',
        'policy_id',
        'tax_id',
        string='Recovery taxes',
        check_company=True,
    )
    tax_treatment = fields.Selection(selection=TAX_TREATMENTS, required=True, default='unresolved')
    payment_term_id = fields.Many2one('account.payment.term', check_company=True)
    fiscal_position_id = fields.Many2one('account.fiscal.position', check_company=True)
    four_eyes_posting = fields.Boolean(
        default=True,
        help='The commercial requester cannot post the accounting document.',
    )
    bank_verification_required = fields.Boolean(
        default=True,
        help='A customer payment counts as cash only when bank evidence matches it.',
    )
    dispute_blocks_billing = fields.Boolean(
        default=True,
        help='A current dispute blocks new billing. This is not a monetary threshold.',
    )
    change_reason = fields.Text(required=True)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    supersedes_id = fields.Many2one('cpla.recovery.billing.policy', readonly=True, copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_policy_editor()
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            company = self.env['res.company'].browse(vals.get('company_id')).exists()
            if len(company) != 1:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A company is required on the billing policy.')
            self._require_company(company)
            if not (vals.get('change_reason') or '').strip():
                _fail(self.env, 'ACCOUNTING_CONFIGURATION_INCOMPLETE', 'The billing policy needs a change reason.')
            if not (vals.get('name') or '').strip():
                _fail(self.env, 'ACCOUNTING_CONFIGURATION_INCOMPLETE', 'The billing policy needs a name.')
            reference = self.env['ir.sequence'].with_company(company).next_by_code(POLICY_SEQUENCE)
            if not reference:
                _fail(self.env, 'ACCOUNTING_CONFIGURATION_INCOMPLETE', 'The billing policy sequence is missing.')
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
                self.env, 'HISTORICAL_APPROVAL_PROTECTED',
                'An approved billing policy cannot be edited. Create a new revision.',
            )
        blocked = set(vals) & {
            'reference', 'state', 'approved_by_id', 'approved_at', 'is_current', 'company_id', 'supersedes_id',
        }
        if blocked:
            _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Those billing policy fields are set by the server.')
        return super().write(vals)

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A billing policy revision cannot be deleted.')

    def action_approve_policy(self):
        """Approve this draft. It does not create an invoice."""
        self._check_policy_editor()
        for policy in self:
            policy._require_company(policy.company_id)
            if policy.state != 'draft':
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Only a draft billing policy can be approved.')
            policy._assert_configuration()
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

    def _assert_configuration(self):
        self.ensure_one()
        if self.billing_method not in dict(BILLING_METHODS):
            _fail(self.env, 'ACCOUNTING_METHOD_UNAVAILABLE', 'Choose a supported billing method.')
        if self.tax_treatment == 'unresolved':
            _fail(self.env, 'TAX_TREATMENT_UNRESOLVED', 'Choose the tax treatment before this policy can be approved.')
        if self.tax_treatment == 'untaxed_explicit' and self.tax_ids:
            _fail(self.env, 'TAX_TREATMENT_UNRESOLVED', 'An untaxed recovery policy cannot carry taxes.')
        if self.tax_treatment == 'untaxed_explicit' and self.fiscal_position_id:
            _fail(
                self.env, 'TAX_TREATMENT_UNRESOLVED',
                'An untaxed recovery policy cannot apply a fiscal position.',
            )
        if self.tax_treatment == 'taxes_on_policy' and not self.tax_ids:
            _fail(self.env, 'TAX_TREATMENT_UNRESOLVED', 'Select the recovery taxes on this policy.')
        for tax in self.tax_ids:
            if tax.company_id != self.company_id:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A recovery tax belongs to another company.')
            if tax.type_tax_use != 'sale':
                _fail(self.env, 'TAX_TREATMENT_UNRESOLVED', 'Recovery billing uses a customer sale tax.')
        if self.billing_method == 'debit_note' and 'account.debit.note' not in self.env.registry:
            _fail(
                self.env, 'ACCOUNTING_METHOD_UNAVAILABLE',
                'Customer debit notes are not installed. The method was not changed.',
            )
        if self.billing_method in CREATING_METHODS:
            journal = self.journal_id
            account = self.revenue_account_id
            if not journal or journal.type != 'sale' or journal.company_id != self.company_id:
                _fail(
                    self.env, 'ACCOUNTING_CONFIGURATION_INCOMPLETE',
                    'A customer sales journal of this company is required before a document can be created.',
                )
            if not account or account.account_type not in ('income', 'income_other'):
                _fail(
                    self.env, 'ACCOUNTING_CONFIGURATION_INCOMPLETE',
                    'An income account of this company is required. No account was selected automatically.',
                )
            if self.company_id not in account.company_ids and account.company_id != self.company_id:
                _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The recovery income account belongs to another company.')
        if self.journal_id and self.journal_id.company_id != self.company_id:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The billing journal belongs to another company.')
        if self.payment_term_id and self.payment_term_id.company_id and self.payment_term_id.company_id != self.company_id:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The payment terms belong to another company.')
        if self.fiscal_position_id and self.fiscal_position_id.company_id != self.company_id:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The fiscal position belongs to another company.')
        if self.product_id and self.product_id.company_id and self.product_id.company_id != self.company_id:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'The recovery product belongs to another company.')

    @api.model
    def _check_policy_editor(self):
        _check_accounting_user(self.env)

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


class RecoveryBilling(models.Model):
    """One authorized billing slice. A draft move is not posted recovery."""

    _name = 'cpla.recovery.billing'
    _description = 'Recovery Billing'
    _order = 'id desc'
    _check_company_auto = True

    _reference_unique = models.Constraint(
        'UNIQUE(reference)',
        'This recovery billing reference already exists.',
    )
    _billing_identity_unique = models.UniqueIndex(
        "(billing_identity) WHERE billing_identity IS NOT NULL AND state NOT IN ('cancelled', 'superseded', 'fully_reversed')",
        'This recovery billing slice already exists.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True, readonly=True)
    request_id = fields.Many2one('cpla.recovery.request', required=True, index=True, readonly=True, ondelete='restrict')
    validation_id = fields.Many2one('cpla.finance.validation', required=True, index=True, readonly=True, ondelete='restrict')
    policy_id = fields.Many2one('cpla.recovery.billing.policy', required=True, index=True, readonly=True, ondelete='restrict')
    policy_reference = fields.Char(readonly=True)
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    billing_method = fields.Selection(selection=BILLING_METHODS, required=True, readonly=True)
    state = fields.Selection(selection=BILLING_STATES, required=True, default='draft', readonly=True, index=True, copy=False)
    journal_id = fields.Many2one('account.journal', readonly=True, check_company=True)
    revenue_account_id = fields.Many2one('account.account', readonly=True, check_company=True)
    tax_treatment = fields.Selection(selection=TAX_TREATMENTS, required=True, readonly=True)
    four_eyes_posting = fields.Boolean(readonly=True, default=True)
    bank_verification_required = fields.Boolean(readonly=True, default=True)
    dispute_blocks_billing = fields.Boolean(readonly=True, default=True)
    requested_principal_exact = fields.Char(required=True, readonly=True, default='0')
    posted_principal_exact = fields.Char(required=True, readonly=True, default='0')
    tax_exact = fields.Char(required=True, readonly=True, default='0')
    gross_exact = fields.Char(required=True, readonly=True, default='0')
    expected_tax_exact = fields.Char(required=True, readonly=True, default='0')
    expected_gross_exact = fields.Char(required=True, readonly=True, default='0')
    move_id = fields.Many2one('account.move', readonly=True, copy=False, index=True, ondelete='restrict')
    origin_move_id = fields.Many2one('account.move', readonly=True, copy=False, index=True, ondelete='restrict')
    link_source = fields.Selection(selection=LINK_SOURCES, readonly=True, copy=False)
    source_fingerprint = fields.Char(readonly=True, index=True)
    source_revision = fields.Integer(readonly=True)
    handoff_key = fields.Char(readonly=True, index=True)
    handoff_revision = fields.Integer(readonly=True)
    billing_identity = fields.Char(readonly=True, copy=False, index=True)
    slice_key = fields.Char(readonly=True, index=True)
    prepared_by_id = fields.Many2one('res.users', readonly=True, index=True)
    prepared_at = fields.Datetime(readonly=True)
    posted_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    posted_at = fields.Datetime(readonly=True, copy=False)
    posted_on = fields.Date(readonly=True, copy=False)
    due_date = fields.Date(readonly=True, copy=False)
    blocker = fields.Text(readonly=True, copy=False)
    supersedes_id = fields.Many2one('cpla.recovery.billing', readonly=True, copy=False, index=True)
    line_ids = fields.One2many('cpla.recovery.billing.line', 'billing_id')
    link_ids = fields.One2many('cpla.recovery.accounting.link', 'billing_id')
    evidence_ids = fields.One2many('cpla.recovery.collection.evidence', 'billing_id')
    adjustment_ids = fields.One2many('cpla.recovery.accounting.adjustment', 'billing_id')
    exception_code = fields.Char(compute='_compute_financial_readout')
    verification_state = fields.Char(compute='_compute_financial_readout')
    overdue_days = fields.Integer(compute='_compute_financial_readout')

    @api.depends(
        'state', 'move_id', 'due_date', 'posted_principal_exact', 'tax_exact',
        'source_revision', 'source_fingerprint',
        'request_id.stale_source', 'request_id.source_revision', 'request_id.source_fingerprint',
        'evidence_ids.classification', 'evidence_ids.counts_current', 'evidence_ids.verification_state',
    )
    def _compute_financial_readout(self):
        """Display values. A failed accounting read stays an exception, not a zero balance."""
        for billing in self:
            try:
                billing.move_id.check_access('read') if billing.move_id else None
            except AccessError:
                billing.exception_code = 'TECHNICAL_ACCOUNTING_FAILURE'
                billing.verification_state = 'UNVERIFIED_SETTLEMENT'
                billing.overdue_days = 0
                continue
            codes = billing._exception_codes()
            billing.exception_code = codes[0] if codes else False
            billing.verification_state = billing._verification_summary()
            billing.overdue_days = billing._overdue_days()

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A recovery billing is prepared from an authorized handoff.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A recovery billing cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A recovery billing cannot be deleted.')

    def export_data(self, fields_to_export):
        user = self.env.user
        if user.share or not user.active:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'A public user cannot export recovery billing.')
        allowed = _in_group(self.env, user, FINANCE_MANAGER_GROUP) or _in_group(self.env, user, AUDITOR_GROUP)
        if not allowed:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'You cannot export recovery billing evidence.')
        self.check_access('read')
        return super().export_data(fields_to_export)

    @api.model
    def prepare_from_request(self, request_id, line_amounts=None, slice_key=None, existing_move_id=None):
        """Reserve one non-overlapping slice. This does not post."""
        _check_accounting_user(self.env)
        request = self.env['cpla.recovery.request'].browse(request_id).exists()
        if len(request) != 1:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Choose one recovery request.')
        request.check_access('read')
        self._require_company(request.company_id)
        policy = self.env['cpla.recovery.billing.policy'].current_for(request.company_id)
        if not policy:
            _fail(
                self.env, 'ACCOUNTING_CONFIGURATION_INCOMPLETE',
                'This company has no approved recovery billing policy.',
            )
        self._assert_request_billable(request, policy)
        amounts = self._slice_amounts(request, line_amounts)
        if not slice_key:
            slice_key = _canonical(sorted((line_id, amount) for line_id, amount in amounts.items()))
        identity = _canonical({
            'company_id': request.company_id.id,
            'request_id': request.id,
            'handoff_key': request.handoff_key or '',
            'source_revision': request.source_revision or 0,
            'method': policy.billing_method,
            'slice_key': slice_key,
            'lines': sorted((line_id, amount) for line_id, amount in amounts.items()),
        })
        existing = self._find_identity(identity)
        if existing:
            return existing
        if policy.billing_method == 'debit_note' and 'account.debit.note' not in self.env.registry:
            _fail(
                self.env, 'ACCOUNTING_METHOD_UNAVAILABLE',
                'Customer debit notes are not installed. The method was not changed.',
            )
        if policy.billing_method == 'existing_document' and not existing_move_id:
            _fail(
                self.env, 'BILLING_DOCUMENT_MISMATCH',
                'Link an existing posted customer invoice. A new document was not created.',
            )
        try:
            with self.env.cr.savepoint():
                request.lock_for_update()
                existing = self._find_identity(identity)
                if existing:
                    return existing
                self._assert_room(request, amounts)
                billing = self._create_header(request, policy, amounts, identity, slice_key)
                if policy.billing_method == 'manual_handoff':
                    models.Model.write(billing, {'state': 'document_prepared'})
                elif policy.billing_method == 'existing_document':
                    billing._link_existing(self.env['account.move'].browse(existing_move_id))
                else:
                    models.Model.write(billing, {'state': 'handoff_verified'})
        except IntegrityError:
            existing = self._find_identity(identity)
            if existing:
                return existing
            _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'Another billing slice was recorded for this allocation.')
        except LockError:
            _fail(self.env, 'FINANCIAL_DECISION_CONFLICT', 'Another billing slice is being recorded.')
        return billing

    def action_create_draft(self):
        """Create the draft accounting document. This does not post it."""
        _check_accounting_user(self.env)
        for billing in self:
            billing._require_company(billing.company_id)
            if billing.move_id:
                continue
            if billing.billing_method not in CREATING_METHODS:
                _fail(
                    self.env, 'ACCOUNTING_METHOD_UNAVAILABLE',
                    'This billing method does not create an accounting document.',
                )
            if billing.state not in ('handoff_verified', 'accounting_review', 'ready_to_post'):
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Create a draft from a verified handoff that is not already posted.')
            billing._assert_request_billable(billing.request_id, billing.policy_id)
            billing._assert_still_fresh()
            if billing.billing_method == 'debit_note':
                move = billing._create_debit_note()
                source = 'created_by_app'
            else:
                move = billing._create_standalone()
                source = 'created_by_app'
            billing._store_draft_preview(move, source)
        return True

    def action_mark_ready(self):
        _check_accounting_user(self.env)
        for billing in self:
            billing._require_company(billing.company_id)
            if billing.state != 'draft_document_created' or not billing.move_id or billing.move_id.state != 'draft':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Mark ready only a draft recovery document.')
            models.Model.write(billing, {'state': 'ready_to_post'})
        return True

    def action_post(self):
        """Post the draft. Recheck authority and the source immediately before posting."""
        _check_accounting_user(self.env)
        for billing in self:
            billing._require_company(billing.company_id)
            billing.check_access('read')
            if billing.state in CURRENT_POSTED or billing.state == 'fully_reversed':
                continue
            if billing.link_source == 'existing_verified':
                _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An existing posted document is linked. It was not posted again.')
            if billing.billing_method == 'manual_handoff':
                _fail(self.env, 'ACCOUNTING_METHOD_UNAVAILABLE', 'A manual handoff does not post an accounting document.')
            move = billing.move_id
            if not move or billing.state not in ('draft_document_created', 'ready_to_post'):
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Post only a draft recovery document created for this slice.')
            billing._assert_four_eyes()
            billing._assert_request_billable(billing.request_id, billing.policy_id)
            billing._assert_still_fresh()
            if move.state == 'posted':
                billing._recognize_posted_move(move, billing.link_source or 'created_by_app')
                continue
            if move.state != 'draft':
                _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The recovery document is not a draft that can be posted.')
            billing._assert_draft_amounts(move)
            # Native action_post enforces lock dates and tax rules. Do not catch and continue.
            move.action_post()
            billing._recognize_posted_move(move, 'created_by_app')
        return True

    def action_cancel(self, reason):
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'Cancellation needs a reason.')
        _check_accounting_user(self.env)
        for billing in self:
            billing._require_company(billing.company_id)
            if billing.state in CURRENT_POSTED or billing.state == 'fully_reversed' or _money(billing.posted_principal_exact):
                _fail(
                    self.env, 'HISTORICAL_APPROVAL_PROTECTED',
                    'A posted recovery document is corrected with a credit note, not by cancellation.',
                )
            move = billing.move_id
            models.Model.write(billing, {
                'state': 'cancelled',
                'move_id': False,
                'blocker': str(reason).strip(),
            })
            if billing.line_ids:
                models.Model.write(billing.line_ids, {'counts_current': False})
            if move and move.state == 'draft':
                move.unlink()
        return True

    def action_refresh_collections(self):
        """Store the current classification of accounting reconciliations."""
        _check_accounting_user(self.env)
        for billing in self:
            billing._require_company(billing.company_id)
            billing._sync_evidence()
        return True

    def action_prepare_credit(self, amount, reason):
        """Draft a credit note. It is not cash and it is not posted here."""
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'A credit note needs a reason.')
        _check_accounting_user(self.env)
        created = self.env['cpla.recovery.accounting.adjustment']
        for billing in self:
            billing._require_company(billing.company_id)
            billing._assert_four_eyes()
            if billing.state not in CURRENT_POSTED or not billing.move_id or billing.move_id.state != 'posted':
                _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'Credit a posted recovery document.')
            principal = _quantize(_money(amount), billing.currency_id)
            if principal <= ZERO:
                _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'The credit principal must be positive.')
            outstanding = _money(billing.billing_position()['outstanding_principal'])
            if principal > outstanding:
                _fail(self.env, 'BILLING_EXCEEDS_AUTHORIZED', 'The credit is above the outstanding recovery principal.')
            price = billing._credit_price(principal)
            credit = self.env['account.move'].with_company(billing.company_id).create({
                'move_type': 'out_refund',
                'partner_id': billing.partner_id.id,
                'company_id': billing.company_id.id,
                'currency_id': billing.currency_id.id,
                'journal_id': billing.move_id.journal_id.id,
                'invoice_date': fields.Date.context_today(self),
                'reversed_entry_id': billing.move_id.id,
                'ref': billing.reference,
                'invoice_line_ids': [Command.create(billing._line_vals(price, 'Credit of recovery %s. Not incoming cash.' % billing.reference))],
            })
            adjustment = models.Model.create(self.env['cpla.recovery.accounting.adjustment'], [{
                'billing_id': billing.id,
                'company_id': billing.company_id.id,
                'currency_id': billing.currency_id.id,
                'move_id': credit.id,
                'adjustment_kind': 'credit_note',
                'state': 'draft',
                'principal_exact': _text(principal),
                'reason': str(reason).strip(),
                'is_cash': False,
            }])
            created |= adjustment
        return created

    def action_post_credit(self):
        """Post a prepared credit note and reconcile it to the recovery receivable."""
        _check_accounting_user(self.env)
        for billing in self:
            billing._require_company(billing.company_id)
            billing._assert_four_eyes()
            drafts = billing.adjustment_ids.filtered(lambda item: item.state == 'draft' and item.move_id.state == 'draft')
            if not drafts:
                continue
            for adjustment in drafts:
                credit = adjustment.move_id
                credit.action_post()
                billing._reconcile_refund(credit)
                models.Model.write(adjustment, {
                    'state': 'posted',
                    'posted_by_id': self.env.user.id,
                    'posted_at': fields.Datetime.now(),
                })
            billing._sync_evidence()
        return True

    def action_classify_settlement(self, partial_id, classification, reason):
        """Record a write-off or netting label on an existing reconciliation. This does not post one."""
        if classification not in ('write_off', 'other_settlement'):
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'Choose write-off or other settlement. Neither one is cash.')
        if not (reason or '').strip():
            _fail(self.env, 'EVIDENCE_INCOMPLETE', 'The settlement classification needs a reason.')
        _check_accounting_user(self.env)
        for billing in self:
            billing._require_company(billing.company_id)
            billing._sync_evidence()
            evidence = billing.evidence_ids.filtered(
                lambda item: item.counts_current and item.partial_reconcile_key == partial_id
            )[:1]
            if not evidence:
                _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'That reconciliation is not on this recovery document.')
            if evidence.classification not in ('other_settlement', 'write_off', 'unconfirmed_payment', 'unknown_credit'):
                _fail(
                    self.env, 'BILLING_DOCUMENT_MISMATCH',
                    'Bank-verified cash, a supported credit note, an advance, and an exchange difference keep their classification.',
                )
            category = evidence.credit_category
            if evidence.classification == 'unknown_credit' and classification == 'other_settlement':
                category = 'SETTLEMENT_CREDIT'
            elif classification == 'write_off':
                category = False
            models.Model.write(evidence, {
                'classification': classification,
                'classification_override': classification,
                'override_reason': str(reason).strip(),
                'is_verified_cash': False,
                'reduces_outstanding': True,
                'credit_category': category,
                'verification_state': VERIFICATION_STATES.get(classification) or 'UNVERIFIED_SETTLEMENT',
            })
        return True

    def handoff_package(self):
        """Controlled package for an accountant. It does not create a move."""
        self.ensure_one()
        self.check_access('read')
        self._require_company(self.company_id)
        return {
            'status': 'MANUAL_ACCOUNTING_HANDOFF' if self.billing_method == 'manual_handoff' else 'BILLING_PACKAGE',
            'creates_account_move': False,
            'posts_account_move': False,
            'proves_cash_collection': False,
            'billing_id': self.id,
            'reference': self.reference,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id,
            'method': self.billing_method,
            'state': self.state,
            'requested_principal': self.requested_principal_exact,
            'posted_principal': self.posted_principal_exact,
            'journal_id': self.journal_id.id,
            'revenue_account_id': self.revenue_account_id.id,
            'tax_treatment': self.tax_treatment,
            'policy_reference': self.policy_reference,
            'source_revision': self.source_revision or 0,
            'handoff_key': self.handoff_key or '',
            'move_id': self.move_id.id,
            'link_source': self.link_source or '',
            'lines': [{
                'request_line_id': line.request_line_id.id,
                'finding_id': line.finding_id.id,
                'principal': line.principal_exact,
                'origin_move_id': line.origin_move_id.id,
            } for line in self.line_ids],
        }

    def billing_position(self):
        """Live classification. Drafts are not posted principal and payments are not principal by themselves."""
        self.ensure_one()
        self.check_access('read')
        try:
            rows = self._classified_rows() if self.state in CURRENT_POSTED or self.state == 'fully_reversed' else []
            position = _position_from_rows(self, rows)
            position['exception_codes'] = self._exception_codes(rows)
            position['verification_state'] = self._verification_summary(rows)
            position['overdue_days'] = self._overdue_days()
            position['aging'] = {
                label: _text(_quantize(amount, self.currency_id))
                for label, amount in self._aging_buckets().items()
            }
        except AccessError:
            _fail(
                self.env, 'TECHNICAL_ACCOUNTING_FAILURE',
                'Accounting evidence could not be read. Outstanding was not set to zero.',
            )
        position['net_billed_principal'] = position['posted_principal']
        return position

    def accounting_position(self):
        return self.billing_position()

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

    def action_open_request(self):
        """Open the commercial recovery request. This does not change it."""
        self.ensure_one()
        self.check_access('read')
        self.request_id.check_access('read')
        return self.request_id.get_formview_action()

    def action_open_move(self):
        """Open the recovery accounting document when the user may read it."""
        self.ensure_one()
        self.check_access('read')
        if not self.move_id:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'This billing has no accounting document.')
        self.move_id.check_access('read')
        return self.move_id.get_formview_action()

    def action_open_origin(self):
        """Open the original customer invoice when the user may read it."""
        self.ensure_one()
        self.check_access('read')
        if not self.origin_move_id:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'This billing has no original customer invoice.')
        self.origin_move_id.check_access('read')
        return self.origin_move_id.get_formview_action()

    @api.model
    def reconciliation_report(self, company_id):
        """One row per recovery request. Currencies are not added together."""
        company = self.env['res.company'].browse(company_id).exists()
        if len(company) != 1:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'Choose one company for the recovery report.')
        self._require_company(company)
        requests = self.env['cpla.recovery.request'].search([
            ('company_id', '=', company.id),
            ('state', 'in', ('approved', 'stale_source')),
        ])
        rows = []
        currencies = set()
        for request in requests:
            position = self.position_for_request(request)
            commercial = request.env['cpla.recovery.balance'].position_for(request.validation_id)
            currencies.add(position['currency_id'])
            noncash = _sum_text((
                position['credit_note_principal'],
                position['write_off_principal'],
                position['other_settlement_principal'],
                position['advance_principal'],
            ))
            rows.append({
                'company_id': company.id,
                'partner_id': request.partner_id.id,
                'request_id': request.id,
                'currency_id': position['currency_id'],
                'finance_validated': commercial['validated'],
                'approved_waiver': commercial['waiver'],
                'approved_target': position['authorized_target'],
                'posted_principal': position['posted_principal'],
                'net_billed_principal': position['net_billed_principal'],
                'tax_billed': position['tax_billed'],
                'gross_receivable': position['gross_receivable'],
                'verified_cash_principal': position['verified_cash_principal'],
                'pending_verification': position['unconfirmed_principal'],
                'noncash_adjustment': _text(_quantize(noncash, request.currency_id)),
                'fx_difference': position['fx_company_amount'],
                'unbilled_principal': position['unbilled_target'],
                'receivable_outstanding': position['outstanding_principal'],
                'accounting_residual': position['accounting_residual'],
                'due_date': position['due_date'],
                'overdue_days': position['overdue_days'],
                'dispute_open': position['dispute_open'],
                'exception_codes': position['exception_codes'],
            })
        return {
            'rows': rows,
            'mixed_currency': len(currencies) > 1,
            'totals': False,
        }

    @api.model
    def _find_identity(self, identity):
        return self.search([
            ('billing_identity', '=', identity),
            ('state', 'not in', list(RELEASED) + ['blocked']),
        ], limit=1)

    @api.model
    def _slice_amounts(self, request, line_amounts):
        current = request.line_ids.filtered(lambda line: line.counts_current and _money(line.current_recovery_exact) > ZERO)
        if not current:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'The recovery request has no current amount to bill.')
        if line_amounts is None:
            return {
                line.id: _text(_quantize(_money(line.current_recovery_exact), line.currency_id))
                for line in current
            }
        unknown = set(line_amounts) - set(current.ids)
        if unknown:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A billing line is not a current recovery allocation.')
        amounts = {}
        for line in current:
            if line.id not in line_amounts:
                continue
            amount = _decimal(line_amounts[line.id])
            if amount is None or amount <= ZERO:
                _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'A billing amount must be positive.')
            quantized = _quantize(amount, line.currency_id)
            if quantized <= ZERO:
                _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'A billing amount must be positive after currency rounding.')
            if quantized > _money(line.current_recovery_exact):
                _fail(self.env, 'BILLING_EXCEEDS_AUTHORIZED', 'The billing slice exceeds the current authorized recovery on this line.')
            amounts[line.id] = _text(quantized)
        if not amounts:
            _fail(self.env, 'INVALID_RECOVERY_AMOUNT', 'Choose at least one positive billing amount.')
        return amounts

    @api.model
    def _assert_room(self, request, amounts):
        for line_id, amount_text in amounts.items():
            line = request.line_ids.filtered(lambda item: item.id == line_id)
            reserved = self.env['cpla.recovery.billing.line'].search([
                ('request_line_id', '=', line.id),
                ('counts_current', '=', True),
            ])
            taken = _sum_text(reserved.mapped('principal_exact'))
            if _arithmetic('add', taken, _money(amount_text)) > _money(line.current_recovery_exact):
                _fail(
                    self.env, 'BILLING_EXCEEDS_AUTHORIZED',
                    'This slice overlaps recovery principal that is already reserved or posted.',
                )

    @api.model
    def _create_header(self, request, policy, amounts, identity, slice_key):
        total = _sum_text(amounts.values())
        origins = request.env['account.move']
        for line in request.line_ids:
            if line.id in amounts and line.validation_line_id.move_line_id:
                origins |= line.validation_line_id.move_line_id.move_id
        reference = self.env['ir.sequence'].with_company(request.company_id).next_by_code(BILLING_SEQUENCE)
        if not reference:
            _fail(self.env, 'ACCOUNTING_CONFIGURATION_INCOMPLETE', 'The recovery billing sequence is missing.')
        billing = models.Model.create(self, [{
            'reference': reference,
            'company_id': request.company_id.id,
            'partner_id': request.partner_id.id,
            'request_id': request.id,
            'validation_id': request.validation_id.id,
            'policy_id': policy.id,
            'policy_reference': policy.reference,
            'currency_id': request.currency_id.id,
            'billing_method': policy.billing_method,
            'state': 'draft',
            'journal_id': policy.journal_id.id,
            'revenue_account_id': policy.revenue_account_id.id,
            'tax_treatment': policy.tax_treatment,
            'four_eyes_posting': policy.four_eyes_posting,
            'bank_verification_required': policy.bank_verification_required,
            'dispute_blocks_billing': policy.dispute_blocks_billing,
            'requested_principal_exact': _text(_quantize(total, request.currency_id)),
            'posted_principal_exact': '0',
            'tax_exact': '0',
            'gross_exact': '0',
            'expected_tax_exact': '0',
            'expected_gross_exact': '0',
            'origin_move_id': origins[:1].id if len(origins) == 1 else False,
            'source_fingerprint': request.source_fingerprint or '',
            'source_revision': request.source_revision or 0,
            'handoff_key': request.handoff_key or '',
            'handoff_revision': request.handoff_revision or 0,
            'billing_identity': identity,
            'slice_key': slice_key,
            'prepared_by_id': self.env.user.id,
            'prepared_at': fields.Datetime.now(),
        }])
        for line in request.line_ids.sorted('id'):
            if line.id not in amounts:
                continue
            origin = line.validation_line_id.move_line_id.move_id
            models.Model.create(self.env['cpla.recovery.billing.line'], [{
                'billing_id': billing.id,
                'company_id': line.company_id.id,
                'request_line_id': line.id,
                'validation_line_id': line.validation_line_id.id,
                'finding_id': line.finding_id.id,
                'currency_id': line.currency_id.id,
                'principal_exact': amounts[line.id],
                'slice_key': slice_key,
                'origin_move_id': origin.id,
                'source_fingerprint': line.source_fingerprint or '',
                'source_revision': line.source_revision or 0,
                'counts_current': True,
            }])
        return billing

    @api.model
    def _assert_request_billable(self, request, policy):
        if policy.company_id != request.company_id or not policy.is_current or policy.state != 'approved':
            _fail(self.env, 'ACCOUNTING_CONFIGURATION_INCOMPLETE', 'The billing policy is not the current revision for this company.')
        payload = request.accounting_handoff_payload()
        if payload['status'] != 'READY_FOR_ACCOUNTING':
            reason = (payload.get('reasons') or ['The accounting handoff is not authorized.'])[0]
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', reason)
        if payload['creates_account_move'] or payload['proves_cash_collection'] or _money(payload['billed_amount']) or _money(payload['collected_amount']):
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'The commercial handoff must not claim an invoice or cash collection.')
        request._assert_validation_current(request.validation_id)
        if request.stale_source or request.state != 'approved':
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The recovery authorization is not a current approved target.')
        if request.currency_id != request.validation_id.review_currency_id:
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The recovery currency does not match the finance validation currency.')
        if policy.journal_id and policy.journal_id.currency_id and policy.journal_id.currency_id != request.currency_id:
            _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'The billing journal currency does not match the recovery currency.')
        if policy.dispute_blocks_billing and request.dispute_ids.filtered('counts_current'):
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A current dispute blocks recovery billing under the approved policy.')
        open_settlement = request.settlement_ids.filtered(
            lambda item: item.counts_current and item.customer_state not in ('accepted', 'withdrawn', 'rejected')
            and item.internal_state != 'rejected'
        )
        if open_settlement:
            _fail(self.env, 'RECOVERY_SOURCE_NOT_READY', 'A current settlement has no customer acceptance, so billing stays blocked.')
        if _money(request.current_recovery_exact) <= ZERO:
            _fail(self.env, 'BILLING_EXCEEDS_AUTHORIZED', 'The current recovery target is zero, so there is nothing to bill.')
        for line in request.line_ids.filtered('counts_current'):
            if line.currency_id != request.currency_id:
                _fail(self.env, 'CURRENCY_BASIS_REVIEW_REQUIRED', 'A recovery line uses a different currency.')
            if (line.source_fingerprint or '') != (line.validation_line_id.source_fingerprint or ''):
                _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The finance source fingerprint changed.')

    def _assert_still_fresh(self):
        self.ensure_one()
        request = self.request_id
        if request.stale_source or not request.validation_id.is_current or request.validation_id.stale_source:
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The finance source changed. The draft was not posted.')
        if (request.handoff_key or '') != (self.handoff_key or ''):
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The accounting handoff key changed.')
        if (request.source_revision or 0) != (self.source_revision or 0):
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The recovery source revision changed.')
        if (request.source_fingerprint or '') != (self.source_fingerprint or ''):
            _fail(self.env, 'STALE_FINANCIAL_EVIDENCE', 'The recovery source fingerprint changed.')

    def _assert_four_eyes(self):
        self.ensure_one()
        if self.four_eyes_posting and self.env.user == self.request_id.requested_by_id:
            raise AccessError(self.env._(
                'POSTING_AUTHORITY_DENIED: The commercial requester cannot post or credit this recovery document.'
            ))

    def _require_company(self, company):
        if self.env.user._is_superuser():
            return
        if company not in self.env.companies:
            raise AccessError(self.env._('COMPANY_ACCESS_DENIED: You cannot use that company.'))

    def _line_vals(self, price, label):
        self.ensure_one()
        taxes = [Command.clear()]
        if self.tax_treatment == 'taxes_on_policy':
            taxes = [Command.set(self.policy_id.tax_ids.ids)]
        vals = {
            'name': label,
            'quantity': 1.0,
            'price_unit': float(price),
            'account_id': self.revenue_account_id.id,
            'tax_ids': taxes,
        }
        if self.policy_id.product_id:
            vals['product_id'] = self.policy_id.product_id.id
        return vals

    def _move_commands(self):
        self.ensure_one()
        return [Command.create(self._line_vals(
            _money(line.principal_exact),
            'Authorized recovery %s. Not a second shipment.' % self.reference,
        )) for line in self.line_ids]

    def _create_standalone(self):
        self.ensure_one()
        company = self.company_id
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'company_id': company.id,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': self.reference,
            'invoice_line_ids': self._move_commands(),
        }
        if self.policy_id.payment_term_id:
            vals['invoice_payment_term_id'] = self.policy_id.payment_term_id.id
        if self.tax_treatment == 'taxes_on_policy' and self.policy_id.fiscal_position_id:
            vals['fiscal_position_id'] = self.policy_id.fiscal_position_id.id
        return self.env['account.move'].with_company(company).create(vals)

    def _create_debit_note(self):
        self.ensure_one()
        if 'account.debit.note' not in self.env.registry:
            _fail(
                self.env, 'ACCOUNTING_METHOD_UNAVAILABLE',
                'Customer debit notes are not installed. The method was not changed.',
            )
        origins = self.line_ids.mapped('origin_move_id')
        if len(origins) != 1 or origins.state != 'posted' or origins.move_type != 'out_invoice':
            _fail(
                self.env, 'BILLING_DOCUMENT_MISMATCH',
                'A customer debit note needs one posted source customer invoice. No other document was created.',
            )
        if origins.company_id != self.company_id or origins.partner_id.commercial_partner_id != self.partner_id.commercial_partner_id:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The source invoice company or customer does not match this recovery.')
        try:
            wizard = self.env['account.debit.note'].with_company(self.company_id).with_context(
                active_model='account.move',
                active_ids=origins.ids,
            ).create({
                'move_ids': [Command.set(origins.ids)],
                'copy_lines': False,
                'journal_id': self.journal_id.id,
                'date': fields.Date.context_today(self),
                'reason': self.reference,
            })
            action = wizard.create_debit()
        except UserError as error:
            _fail(self.env, 'ACCOUNTING_METHOD_UNAVAILABLE', str(error))
        move = self.env['account.move'].browse(action.get('res_id'))
        if len(move) != 1:
            _fail(self.env, 'ACCOUNTING_METHOD_UNAVAILABLE', 'The debit note wizard did not return one draft. No substitute invoice was created.')
        move.write({'ref': self.reference, 'invoice_line_ids': self._move_commands()})
        return move

    def _store_draft_preview(self, move, source):
        self.ensure_one()
        self._assert_draft_amounts(move)
        currency = self.currency_id
        models.Model.write(self, {
            'move_id': move.id,
            'link_source': source,
            'state': 'draft_document_created',
            'expected_tax_exact': _text(_quantize(_decimal(move.amount_tax) or ZERO, currency)),
            'expected_gross_exact': _text(_quantize(_decimal(move.amount_total) or ZERO, currency)),
            'posted_principal_exact': '0',
            'tax_exact': '0',
            'gross_exact': '0',
            'due_date': move.invoice_date_due,
        })
        self._link_move(move, source, posted=False)

    def _assert_draft_amounts(self, move):
        self.ensure_one()
        currency = self.currency_id
        untaxed = _quantize(_decimal(move.amount_untaxed) or ZERO, currency)
        tax = _quantize(_decimal(move.amount_tax) or ZERO, currency)
        if move.company_id != self.company_id or move.currency_id != currency:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The draft document company or currency does not match the recovery.')
        if move.partner_id.commercial_partner_id != self.partner_id.commercial_partner_id:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The draft document customer does not match the recovery.')
        if untaxed != _money(self.requested_principal_exact):
            _fail(
                self.env, 'BILLING_DOCUMENT_MISMATCH',
                'The draft untaxed amount does not match the authorized recovery principal.',
            )
        if self.tax_treatment == 'untaxed_explicit' and tax != ZERO:
            _fail(self.env, 'TAX_TREATMENT_UNRESOLVED', 'The draft added tax. Untaxed recovery was not posted.')

    def _link_existing(self, move):
        self.ensure_one()
        move = move.exists()
        if len(move) != 1:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'Choose one existing accounting document.')
        if move.state != 'posted' or move.move_type != 'out_invoice':
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'Link a posted customer invoice or debit note. A draft is not posted billing.')
        if move.company_id != self.company_id or move.currency_id != self.currency_id:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The existing document company or currency does not match the recovery.')
        if move.partner_id.commercial_partner_id != self.partner_id.commercial_partner_id:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The existing document customer does not match the recovery.')
        origins = self.line_ids.mapped('origin_move_id')
        if move in origins:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The source customer invoice is not the recovery billing document.')
        if 'debit_origin_id' in move._fields and move.debit_origin_id and origins and move.debit_origin_id not in origins:
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The debit note points at a different source invoice.')
        untaxed = _quantize(_decimal(move.amount_untaxed) or ZERO, self.currency_id)
        tax = _quantize(_decimal(move.amount_tax) or ZERO, self.currency_id)
        if untaxed != _money(self.requested_principal_exact):
            _fail(
                self.env, 'BILLING_DOCUMENT_MISMATCH',
                'The posted untaxed amount must equal this recovery slice. The document was not changed.',
            )
        if self.tax_treatment == 'untaxed_explicit' and tax != ZERO:
            _fail(self.env, 'TAX_TREATMENT_UNRESOLVED', 'The existing document has tax. Untaxed recovery was not linked.')
        linked = self.env['cpla.recovery.accounting.link'].search([
            ('move_id', '=', move.id),
            ('counts_current', '=', True),
        ], limit=1)
        if linked:
            _fail(self.env, 'DUPLICATE_BILLING_ALLOCATION', 'That accounting document is already linked to a recovery slice.')
        self._recognize_posted_move(move, 'existing_verified')

    def _recognize_posted_move(self, move, source):
        self.ensure_one()
        currency = self.currency_id
        untaxed = _quantize(_decimal(move.amount_untaxed) or ZERO, currency)
        tax = _quantize(_decimal(move.amount_tax) or ZERO, currency)
        gross = _quantize(_decimal(move.amount_total) or ZERO, currency)
        if move.state != 'posted':
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'Posted recovery requires a posted accounting document.')
        if untaxed != _money(self.requested_principal_exact):
            _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The posted untaxed amount does not match the authorized principal.')
        models.Model.write(self, {
            'move_id': move.id,
            'link_source': source,
            'state': 'posted',
            'posted_principal_exact': _text(untaxed),
            'tax_exact': _text(tax),
            'gross_exact': _text(gross),
            'expected_tax_exact': _text(tax),
            'expected_gross_exact': _text(gross),
            'posted_by_id': self.env.user.id,
            'posted_at': fields.Datetime.now(),
            'posted_on': move.invoice_date or move.date,
            'due_date': move.invoice_date_due,
            'journal_id': move.journal_id.id,
        })
        self._link_move(move, source, posted=True)
        self._sync_evidence()

    def _link_move(self, move, source, posted):
        self.ensure_one()
        product_lines = move.invoice_line_ids
        previous = self.link_ids.filtered('counts_current')
        if previous:
            models.Model.write(previous, {'counts_current': False})
        for index, line in enumerate(self.line_ids):
            move_line = product_lines[index] if index < len(product_lines) else product_lines[:1]
            models.Model.create(self.env['cpla.recovery.accounting.link'], [{
                'billing_id': self.id,
                'billing_line_id': line.id,
                'company_id': self.company_id.id,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
                'move_id': move.id,
                'move_line_id': move_line.id,
                'origin_move_id': line.origin_move_id.id,
                'validation_id': self.validation_id.id,
                'move_type': move.move_type,
                'posting_state': move.state,
                'link_source': source,
                'source_revision': self.source_revision or 0,
                'counts_current': True,
                'posted': posted,
            }])
            if move_line:
                models.Model.write(line, {'move_line_id': move_line.id})

    def _credit_price(self, principal):
        """Untaxed credit price. A policy tax, when selected, is added by the tax engine."""
        self.ensure_one()
        return principal

    def _reconcile_refund(self, credit):
        """Match the credit to the recovery receivable unless posting already did."""
        self.ensure_one()
        invoice_lines = self.move_id.line_ids.filtered(
            lambda line: line.account_type == 'asset_receivable' and not line.reconciled
        )
        credit_lines = credit.line_ids.filtered(
            lambda line: line.account_type == 'asset_receivable' and not line.reconciled
        )
        if invoice_lines and credit_lines:
            (invoice_lines + credit_lines).reconcile()
            return
        credit_receivable = credit.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')
        invoice_receivable = self.move_id.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')
        partials = credit_receivable.matched_debit_ids | credit_receivable.matched_credit_ids
        counterparts = partials.debit_move_id | partials.credit_move_id
        if counterparts & invoice_receivable:
            return
        _fail(self.env, 'BILLING_DOCUMENT_MISMATCH', 'The credit note could not be matched to the recovery receivable.')

    def _classified_rows(self):
        self.ensure_one()
        try:
            move = self.move_id
            if not move or move.state != 'posted':
                return []
            move.check_access('read')
        except AccessError:
            _fail(
                self.env, 'TECHNICAL_ACCOUNTING_FAILURE',
                'Accounting evidence could not be read. Outstanding was not set to zero.',
            )
        receivables = move.line_ids.filtered(lambda line: line.account_type == 'asset_receivable')
        partials = (receivables.matched_debit_ids | receivables.matched_credit_ids).sorted('id')
        overrides = {
            evidence.partial_reconcile_key: evidence.classification_override
            for evidence in self.evidence_ids.filtered(lambda item: item.classification_override)
        }
        posted = _money(self.posted_principal_exact)
        gross = _money(self.gross_exact) or posted
        remaining = posted
        rows = []
        for partial in partials:
            if partial.debit_move_id in receivables:
                counterpart = partial.credit_move_id
                matched = _money(partial.debit_amount_currency)
            else:
                counterpart = partial.debit_move_id
                matched = _money(partial.credit_amount_currency)
            kind = overrides.get(partial.id) or self._kind_for(partial, counterpart)
            if kind in ('fx_difference', 'unknown_credit'):
                principal = ZERO
            else:
                principal = self._principal_portion(matched, posted, gross)
                principal = min(principal, remaining)
                remaining = _arithmetic('sub', remaining, principal)
            principal = _quantize(principal, self.currency_id)
            rows.append({
                'partial': partial,
                'counterpart': counterpart,
                'kind': kind,
                'matched': _quantize(matched, self.currency_id),
                'principal': principal,
                'company_amount': _quantize(_decimal(partial.amount) or ZERO, self.company_id.currency_id),
                'statement': self._statement_line(counterpart),
                'reduces': kind in REDUCING,
                'credit_category': self._credit_category_for(kind, principal, counterpart),
                'verification_state': VERIFICATION_STATES.get(kind) or False,
            })
        return rows

    def _kind_for(self, partial, counterpart):
        self.ensure_one()
        move = counterpart.move_id
        payment = move.origin_payment_id
        if partial.exchange_move_id and move == partial.exchange_move_id:
            return 'fx_difference'
        if move.move_type == 'out_refund':
            linked = self.adjustment_ids.filtered(lambda item: item.move_id == move and item.state == 'posted')
            if move.reversed_entry_id == self.move_id or linked:
                return 'credit_note'
            return 'unknown_credit'
        if payment:
            if self.posted_on and payment.date and payment.date < self.posted_on:
                return 'advance'
            if payment.reconciled_statement_line_ids:
                return 'verified_cash'
            if self.bank_verification_required:
                return 'unconfirmed_payment'
            return 'verified_cash'
        if move.statement_line_id or counterpart.statement_line_id:
            return 'verified_cash'
        return 'other_settlement'

    def _statement_line(self, counterpart):
        payment = counterpart.move_id.origin_payment_id
        if payment and payment.reconciled_statement_line_ids:
            return payment.reconciled_statement_line_ids[:1]
        return counterpart.statement_line_id or counterpart.move_id.statement_line_id

    def _principal_portion(self, matched, posted, gross):
        self.ensure_one()
        matched = _quantize(matched, self.currency_id)
        if matched <= ZERO or posted <= ZERO:
            return ZERO
        if self.tax_treatment == 'untaxed_explicit' or gross == posted:
            return matched
        return _quantize(_arithmetic('div', _arithmetic('mul', matched, posted), gross), self.currency_id)

    def _sync_evidence(self):
        self.ensure_one()
        if self.state not in CURRENT_POSTED and self.state != 'fully_reversed':
            return
        rows = self._classified_rows()
        seen = set()
        Evidence = self.env['cpla.recovery.collection.evidence']
        for row in rows:
            partial = row['partial']
            seen.add(partial.id)
            vals = {
                'classification': row['kind'],
                'matched_exact': _text(row['matched']),
                'principal_exact': _text(row['principal']),
                'company_amount_exact': _text(row['company_amount']),
                'statement_line_id': row['statement'].id if row['statement'] else False,
                'counterpart_move_id': row['counterpart'].move_id.id,
                'is_verified_cash': row['kind'] == 'verified_cash',
                'reduces_outstanding': row['reduces'],
                'counts_current': True,
                'partial_reconcile_id': partial.id,
                'credit_category': row['credit_category'],
                'verification_state': row['verification_state'],
            }
            evidence = self.evidence_ids.filtered(lambda item: item.partial_reconcile_key == partial.id)[:1]
            if evidence:
                if evidence.classification_override:
                    vals['classification'] = evidence.classification_override
                    vals['is_verified_cash'] = False
                    vals['reduces_outstanding'] = evidence.classification_override in REDUCING
                    vals['verification_state'] = VERIFICATION_STATES.get(evidence.classification_override) or 'UNVERIFIED_SETTLEMENT'
                    if evidence.credit_category:
                        vals['credit_category'] = evidence.credit_category
                models.Model.write(evidence, vals)
            else:
                vals.update({
                    'billing_id': self.id,
                    'company_id': self.company_id.id,
                    'currency_id': self.currency_id.id,
                    'partial_reconcile_key': partial.id,
                })
                models.Model.create(Evidence, [vals])
        stale = self.evidence_ids.filtered(lambda item: item.counts_current and item.partial_reconcile_key not in seen)
        if stale:
            models.Model.write(stale, {
                'counts_current': False,
                'is_verified_cash': False,
                'reduces_outstanding': False,
                'verification_state': 'REVERSAL',
            })
        credit = _sum_text(
            self.evidence_ids.filtered(lambda item: item.counts_current and item.classification == 'credit_note').mapped('principal_exact')
        )
        posted = _money(self.posted_principal_exact)
        if posted > ZERO and credit >= posted:
            state = 'fully_reversed'
        elif credit > ZERO and self.state in CURRENT_POSTED:
            state = 'partially_reversed'
        elif self.state == 'partially_reversed' and credit == ZERO:
            state = 'posted'
        else:
            state = self.state
        if state == 'fully_reversed':
            credits = self.evidence_ids.filtered(
                lambda item: item.counts_current and item.classification == 'credit_note'
            )
            if credits:
                models.Model.write(credits, {'credit_category': 'FULL_RECOVERY_BILL_REVERSAL'})
        due = self._current_due_date()
        if state != self.state or due != self.due_date:
            models.Model.write(self, {'state': state, 'due_date': due})
        if state == 'fully_reversed' and self.line_ids.filtered('counts_current'):
            models.Model.write(self.line_ids, {'counts_current': False})

    def _credit_category_for(self, kind, principal, counterpart):
        self.ensure_one()
        if kind not in ('credit_note', 'unknown_credit'):
            return False
        move = counterpart.move_id
        if kind == 'unknown_credit':
            if move.reversed_entry_id and move.reversed_entry_id != self.move_id:
                return 'UNRELATED_CUSTOMER_CREDIT'
            return 'UNKNOWN_CREDIT_ALLOCATION'
        if principal <= ZERO:
            return 'TAX_ONLY_CREDIT'
        if principal >= _money(self.posted_principal_exact):
            return 'FULL_RECOVERY_BILL_REVERSAL'
        return 'PARTIAL_RECOVERY_BILL_REVERSAL'

    def _open_receivable_lines(self):
        self.ensure_one()
        try:
            move = self.move_id
            if not move or move.state != 'posted' or self.state not in CURRENT_POSTED:
                return self.env['account.move.line']
            move.check_access('read')
        except AccessError:
            _fail(
                self.env, 'TECHNICAL_ACCOUNTING_FAILURE',
                'Accounting evidence could not be read. Outstanding was not set to zero.',
            )
        return move.line_ids.filtered(
            lambda line: line.account_type == 'asset_receivable' and not line.reconciled
            and (_money(line.amount_residual_currency) or _money(line.amount_residual))
        )

    def _current_due_date(self):
        self.ensure_one()
        dates = [line.date_maturity for line in self._open_receivable_lines() if line.date_maturity]
        if dates:
            return min(dates)
        try:
            move = self.move_id
            residual = _money(move.amount_residual) if move else ZERO
            due = move.invoice_date_due if move else False
        except AccessError:
            _fail(
                self.env, 'TECHNICAL_ACCOUNTING_FAILURE',
                'Accounting evidence could not be read. Outstanding was not set to zero.',
            )
        if residual > ZERO:
            return due
        return False

    def _aging_buckets(self):
        self.ensure_one()
        buckets = {label: ZERO for label in AGING_LABELS}
        if self.state not in CURRENT_POSTED:
            return buckets
        posted = _money(self.posted_principal_exact)
        gross = _money(self.gross_exact) or posted
        today = fields.Date.context_today(self)
        for line in self._open_receivable_lines():
            residual = abs(_money(line.amount_residual_currency) or _money(line.amount_residual))
            principal = self._principal_portion(residual, posted, gross)
            if principal <= ZERO:
                continue
            maturity = line.date_maturity or self.due_date
            if not maturity:
                continue
            days = (today - maturity).days
            if days <= 0:
                label = 'not_yet_due'
            elif days <= 30:
                label = 'days_1_30'
            elif days <= 60:
                label = 'days_31_60'
            elif days <= 90:
                label = 'days_61_90'
            else:
                label = 'days_over_90'
            buckets[label] = _arithmetic('add', buckets[label], principal)
        return buckets

    def _overdue_days(self):
        self.ensure_one()
        if self.state not in CURRENT_POSTED:
            return 0
        today = fields.Date.context_today(self)
        dates = [line.date_maturity for line in self._open_receivable_lines() if line.date_maturity]
        overdue = [day for day in dates if day < today]
        if not overdue:
            return 0
        return (today - min(overdue)).days

    def _verification_summary(self, rows=None):
        self.ensure_one()
        if self.state not in CURRENT_POSTED and self.state != 'fully_reversed':
            return 'UNPAID'
        if rows is None:
            rows = self._classified_rows() if self.move_id else []
        kinds = {row['kind'] for row in rows}
        if not kinds:
            historical = self.evidence_ids.filtered(lambda item: not item.counts_current)
            return 'REVERSAL' if historical else 'UNPAID'
        labels = []
        for kind in (
            'unknown_credit', 'unconfirmed_payment', 'verified_cash', 'credit_note',
            'write_off', 'advance', 'other_settlement',
        ):
            label = VERIFICATION_STATES.get(kind)
            if kind in kinds and label and label not in labels:
                labels.append(label)
        return ','.join(labels) if labels else 'UNPAID'

    def _exception_codes(self, rows=None):
        """Read-only exception labels. This does not rewrite the accounting document."""
        self.ensure_one()
        codes = []
        request = self.request_id
        posted_state = self.state in CURRENT_POSTED or self.state == 'fully_reversed'
        if posted_state and (
            request.stale_source
            or not request.validation_id.is_current
            or request.validation_id.stale_source
            or (request.source_revision or 0) != (self.source_revision or 0)
            or (request.source_fingerprint or '') != (self.source_fingerprint or '')
        ):
            codes.append('ACCOUNTING_IMPACT_REVIEW_REQUIRED')
            codes.append('RECOVERY_SOURCE_STALE')
        try:
            move = self.move_id
        except AccessError:
            _fail(
                self.env, 'TECHNICAL_ACCOUNTING_FAILURE',
                'Accounting evidence could not be read. Outstanding was not set to zero.',
            )
        if self.state not in CURRENT_POSTED or not move:
            return codes
        if rows is None:
            rows = self._classified_rows()
        if any(row['kind'] == 'unknown_credit' for row in rows):
            codes.append('CREDIT_ALLOCATION_AMBIGUOUS')
        if any(row['kind'] == 'fx_difference' for row in rows):
            codes.append('FX_DIFFERENCE_REVIEW_REQUIRED')
        if _money(self.tax_exact) == ZERO:
            unknown_matched = _sum_text(row['matched'] for row in rows if row['kind'] == 'unknown_credit')
            outstanding = _money(self.posted_principal_exact)
            for row in rows:
                if row['reduces']:
                    outstanding = _arithmetic('sub', outstanding, row['principal'])
            if outstanding < ZERO:
                codes.append('OVERCOLLECTION_REVIEW_REQUIRED')
                outstanding = ZERO
            expected = _arithmetic('sub', outstanding, _sum_text(
                row['principal'] for row in rows if row['kind'] == 'unconfirmed_payment'
            ))
            expected = _arithmetic('sub', expected, unknown_matched)
            try:
                residual_value = move.amount_residual
            except AccessError:
                _fail(
                    self.env, 'TECHNICAL_ACCOUNTING_FAILURE',
                    'Accounting evidence could not be read. Outstanding was not set to zero.',
                )
            residual = _quantize(_decimal(residual_value) or ZERO, self.currency_id)
            gap = abs(_arithmetic('sub', residual, expected))
            tolerance = _decimal(self.currency_id.rounding) or Decimal('0.01')
            if gap > tolerance:
                codes.append('RECEIVABLE_RESIDUAL_MISMATCH')
        elif _sum_text(row['principal'] for row in rows if row['kind'] == 'verified_cash') > _money(self.posted_principal_exact):
            codes.append('OVERCOLLECTION_REVIEW_REQUIRED')
        return codes

    @api.model
    def position_for_request(self, request):
        request.check_access('read')
        billings = self.search([('request_id', '=', request.id)])
        posted = ZERO
        historical = ZERO
        tax = ZERO
        gross = ZERO
        draft = ZERO
        cash = unconfirmed = credit = write_off = other = advance = fx = ZERO
        outstanding = ZERO
        residual = ZERO
        due = False
        overdue = False
        overdue_days = 0
        exceptions = []
        verification_labels = []
        aging = {label: ZERO for label in AGING_LABELS}
        today = fields.Date.context_today(self)
        currency = request.currency_id
        for billing in billings:
            if billing.state in OPEN_RESERVE:
                draft = _arithmetic('add', draft, _money(billing.requested_principal_exact))
            if billing.state in ('posted', 'partially_reversed', 'fully_reversed'):
                historical = _arithmetic('add', historical, _money(billing.posted_principal_exact))
            if billing.state not in CURRENT_POSTED:
                continue
            position = billing.billing_position()
            posted = _arithmetic('add', posted, _money(position['posted_principal']))
            tax = _arithmetic('add', tax, _money(position['tax_billed']))
            gross = _arithmetic('add', gross, _money(position['gross_receivable']))
            cash = _arithmetic('add', cash, _money(position['verified_cash_principal']))
            unconfirmed = _arithmetic('add', unconfirmed, _money(position['unconfirmed_principal']))
            credit = _arithmetic('add', credit, _money(position['credit_note_principal']))
            write_off = _arithmetic('add', write_off, _money(position['write_off_principal']))
            other = _arithmetic('add', other, _money(position['other_settlement_principal']))
            advance = _arithmetic('add', advance, _money(position['advance_principal']))
            fx = _arithmetic('add', fx, _money(position['fx_company_amount']))
            outstanding = _arithmetic('add', outstanding, _money(position['outstanding_principal']))
            for label in (position.get('verification_state') or '').split(','):
                label = label.strip()
                if label and label != 'UNPAID' and label not in verification_labels:
                    verification_labels.append(label)
            try:
                move = billing.move_id
                if move:
                    residual = _arithmetic(
                        'add', residual, _quantize(_decimal(move.amount_residual) or ZERO, currency),
                    )
            except AccessError:
                _fail(
                    self.env, 'TECHNICAL_ACCOUNTING_FAILURE',
                    'Accounting evidence could not be read. Outstanding was not set to zero.',
                )
            for label, amount_text in position['aging'].items():
                aging[label] = _arithmetic('add', aging[label], _money(amount_text))
            exceptions.extend(position['exception_codes'])
            if position['overdue_days'] > overdue_days:
                overdue_days = position['overdue_days']
            open_due = billing._current_due_date()
            if _money(position['outstanding_principal']) > ZERO and open_due:
                if not due or open_due < due:
                    due = open_due
                if open_due < today:
                    overdue = True
        target = _money(request.current_recovery_exact)
        unbilled = _arithmetic('sub', target, posted)
        if unbilled < ZERO:
            unbilled = ZERO
        commercial = request.env['cpla.recovery.balance'].position_for(request.validation_id)
        return {
            'authorized_target': _text(_quantize(target, currency)),
            'posted_principal': _text(_quantize(posted, currency)),
            'historical_posted_principal': _text(_quantize(historical, currency)),
            'draft_reserved_principal': _text(_quantize(draft, currency)),
            'unbilled_target': _text(_quantize(unbilled, currency)),
            'tax_billed': _text(_quantize(tax, currency)),
            'gross_receivable': _text(_quantize(gross, currency)),
            'verified_cash_principal': _text(_quantize(cash, currency)),
            'unconfirmed_principal': _text(_quantize(unconfirmed, currency)),
            'credit_note_principal': _text(_quantize(credit, currency)),
            'write_off_principal': _text(_quantize(write_off, currency)),
            'other_settlement_principal': _text(_quantize(other, currency)),
            'advance_principal': _text(_quantize(advance, currency)),
            'fx_company_amount': _text(_quantize(fx, currency)),
            'outstanding_principal': _text(_quantize(outstanding, currency)),
            'accounting_residual': _text(_quantize(residual, currency)),
            'net_billed_principal': _text(_quantize(posted, currency)),
            'verification_state': ','.join(verification_labels) if verification_labels else 'UNPAID',
            'due_date': due,
            'overdue': overdue,
            'overdue_days': overdue_days,
            'dispute_open': bool(request.dispute_ids.filtered('counts_current')),
            'exception_codes': list(dict.fromkeys(exceptions)),
            'aging': {
                label: _text(_quantize(amount, currency))
                for label, amount in aging.items()
            },
            'currency_id': currency.id,
            'dev16_billed': commercial['billed'],
            'dev16_collected': commercial['collected'],
            'document_is_cash': False,
            'draft_is_posted': False,
        }


class RecoveryBillingLine(models.Model):
    _name = 'cpla.recovery.billing.line'
    _description = 'Recovery Billing Line'
    _order = 'id'
    _check_company_auto = True

    _slice_unique = models.UniqueIndex(
        '(request_line_id, slice_key) WHERE counts_current',
        'This recovery allocation slice is already reserved.',
    )

    billing_id = fields.Many2one('cpla.recovery.billing', required=True, index=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    request_line_id = fields.Many2one('cpla.recovery.request.line', required=True, index=True, readonly=True, ondelete='restrict')
    validation_line_id = fields.Many2one('cpla.finance.validation.line', required=True, index=True, readonly=True, ondelete='restrict')
    finding_id = fields.Many2one('cpla.leakage.finding', required=True, index=True, readonly=True, ondelete='restrict')
    currency_id = fields.Many2one('res.currency', readonly=True)
    principal_exact = fields.Char(required=True, readonly=True, default='0')
    slice_key = fields.Char(required=True, readonly=True, index=True)
    origin_move_id = fields.Many2one('account.move', readonly=True, ondelete='restrict')
    move_line_id = fields.Many2one('account.move.line', readonly=True, ondelete='set null')
    source_fingerprint = fields.Char(readonly=True)
    source_revision = fields.Integer(readonly=True)
    counts_current = fields.Boolean(readonly=True, default=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Billing lines are created with the billing slice.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A billing line cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'A billing line cannot be deleted.')


class RecoveryAccountingLink(models.Model):
    _name = 'cpla.recovery.accounting.link'
    _description = 'Recovery Accounting Link'
    _order = 'id desc'
    _check_company_auto = True

    billing_id = fields.Many2one('cpla.recovery.billing', required=True, index=True, readonly=True, ondelete='restrict')
    billing_line_id = fields.Many2one('cpla.recovery.billing.line', required=True, index=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    partner_id = fields.Many2one('res.partner', required=True, readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    move_id = fields.Many2one('account.move', required=True, index=True, readonly=True, ondelete='restrict')
    move_line_id = fields.Many2one('account.move.line', readonly=True, ondelete='set null')
    origin_move_id = fields.Many2one('account.move', readonly=True, ondelete='restrict')
    validation_id = fields.Many2one('cpla.finance.validation', readonly=True, ondelete='restrict')
    move_type = fields.Char(readonly=True)
    posting_state = fields.Char(readonly=True)
    link_source = fields.Selection(selection=LINK_SOURCES, required=True, readonly=True)
    source_revision = fields.Integer(readonly=True)
    counts_current = fields.Boolean(readonly=True, default=True, index=True)
    posted = fields.Boolean(readonly=True, default=False)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Accounting links are recorded by the billing action.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An accounting link cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An accounting link cannot be deleted.')


class RecoveryCollectionEvidence(models.Model):
    _name = 'cpla.recovery.collection.evidence'
    _description = 'Recovery Collection Evidence'
    _order = 'id desc'
    _check_company_auto = True

    _partial_unique = models.UniqueIndex(
        '(partial_reconcile_key) WHERE counts_current',
        'This reconciliation is already classified.',
    )

    billing_id = fields.Many2one('cpla.recovery.billing', required=True, index=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    partial_reconcile_id = fields.Many2one('account.partial.reconcile', readonly=True, index=True, ondelete='set null')
    partial_reconcile_key = fields.Integer(required=True, readonly=True, index=True)
    counterpart_move_id = fields.Many2one('account.move', readonly=True, ondelete='set null')
    statement_line_id = fields.Many2one('account.bank.statement.line', readonly=True, ondelete='set null')
    classification = fields.Selection(selection=EVIDENCE_KINDS, required=True, readonly=True, index=True)
    classification_override = fields.Selection(selection=EVIDENCE_KINDS, readonly=True)
    credit_category = fields.Selection(selection=CREDIT_CATEGORIES, readonly=True)
    verification_state = fields.Char(readonly=True)
    override_reason = fields.Text(readonly=True)
    matched_exact = fields.Char(required=True, readonly=True, default='0')
    principal_exact = fields.Char(required=True, readonly=True, default='0')
    company_amount_exact = fields.Char(required=True, readonly=True, default='0')
    is_verified_cash = fields.Boolean(readonly=True, default=False)
    reduces_outstanding = fields.Boolean(readonly=True, default=False)
    counts_current = fields.Boolean(readonly=True, default=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Collection evidence is recorded from accounting reconciliations.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Collection evidence cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'Collection evidence cannot be deleted.')

    def export_data(self, fields_to_export):
        user = self.env.user
        allowed = _in_group(self.env, user, FINANCE_MANAGER_GROUP) or _in_group(self.env, user, AUDITOR_GROUP)
        if user.share or not user.active or not allowed:
            _fail(self.env, 'COMPANY_ACCESS_DENIED', 'You cannot export collection evidence.')
        self.check_access('read')
        return super().export_data(fields_to_export)


class RecoveryAccountingAdjustment(models.Model):
    _name = 'cpla.recovery.accounting.adjustment'
    _description = 'Recovery Accounting Adjustment'
    _order = 'id desc'
    _check_company_auto = True

    billing_id = fields.Many2one('cpla.recovery.billing', required=True, index=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    move_id = fields.Many2one('account.move', readonly=True, index=True, ondelete='restrict')
    adjustment_kind = fields.Selection(
        selection=[
            ('credit_note', 'Customer credit note'),
            ('reversal', 'Reversal'),
        ],
        required=True,
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        default='draft',
        readonly=True,
    )
    principal_exact = fields.Char(required=True, readonly=True, default='0')
    reason = fields.Text(required=True, readonly=True)
    is_cash = fields.Boolean(readonly=True, default=False)
    posted_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    posted_at = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An adjustment is prepared by the billing action.')

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An adjustment cannot be edited directly.')

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        _fail(self.env, 'HISTORICAL_APPROVAL_PROTECTED', 'An adjustment cannot be deleted.')


class RecoveryRequestBilling(models.Model):
    _inherit = 'cpla.recovery.request'

    def action_prepare_billing(self):
        """Open a billing slice for the current target. This does not create an invoice."""
        self.ensure_one()
        self.check_access('read')
        billing = self.env['cpla.recovery.billing'].prepare_from_request(self.id)
        return billing.action_open_form()

    def accounting_position(self):
        """Billing ledger. DEV-16 billed and collected stay zero."""
        self.ensure_one()
        self.check_access('read')
        return self.env['cpla.recovery.billing'].position_for_request(self)


def _check_accounting_user(env):
    user = env.user
    if not _in_group(env, user, FINANCE_MANAGER_GROUP) or not _in_group(env, user, INVOICE_GROUP):
        raise AccessError(env._(
            'POSTING_AUTHORITY_DENIED: Accounting preparation requires a finance manager who already has invoice rights.'
        ))


def _position_from_rows(billing, rows):
    currency = billing.currency_id

    def total(kind):
        return _sum_text(row['principal'] for row in rows if row['kind'] == kind)

    posted = _money(billing.posted_principal_exact) if billing.state in CURRENT_POSTED else ZERO
    cash = total('verified_cash')
    credit = total('credit_note')
    write_off = total('write_off')
    other = total('other_settlement')
    advance = total('advance')
    outstanding = _arithmetic('sub', posted, _sum_text((cash, credit, write_off, other, advance)))
    if outstanding < ZERO:
        outstanding = ZERO
    fx = _sum_text(row['company_amount'] for row in rows if row['kind'] == 'fx_difference')
    return {
        'posted_principal': _text(_quantize(posted, currency)),
        'tax_billed': billing.tax_exact if billing.state in CURRENT_POSTED else '0',
        'gross_receivable': billing.gross_exact if billing.state in CURRENT_POSTED else '0',
        'verified_cash_principal': _text(_quantize(cash, currency)),
        'unconfirmed_principal': _text(_quantize(total('unconfirmed_payment'), currency)),
        'credit_note_principal': _text(_quantize(credit, currency)),
        'write_off_principal': _text(_quantize(write_off, currency)),
        'other_settlement_principal': _text(_quantize(other, currency)),
        'advance_principal': _text(_quantize(advance, currency)),
        'fx_company_amount': _text(_quantize(fx, currency)),
        'outstanding_principal': _text(_quantize(outstanding, currency)),
        'document_is_cash': False,
    }
