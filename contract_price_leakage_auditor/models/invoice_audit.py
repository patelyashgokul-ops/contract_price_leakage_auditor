import hashlib
import json
import logging

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.contract_price_leakage_auditor.models.discount_authority import (
    AUTHORITATIVE,
)
from odoo.addons.contract_price_leakage_auditor.models.financial_normalization import (
    FINANCE_MANAGER_GROUP,
    MANAGER_GROUP,
    _arithmetic,
    _decimal,
    _text,
)
from odoo.addons.contract_price_leakage_auditor.models.invoice_source import (
    EXCLUDED_LINE_CLASSES,
)

_logger = logging.getLogger(__name__)

MODULE = 'contract_price_leakage_auditor'
RUN_GROUPS = (MANAGER_GROUP, FINANCE_MANAGER_GROUP)
ENGINE_VERSION = 'dev12.1'
BATCH_CAP = 200
ZERO = _decimal('0')
HUNDRED = _decimal('100')

RUN_SEQUENCE = 'cpla.invoice.audit.run'
FINDING_SEQUENCE = 'cpla.leakage.finding'

LEAKAGE_CLASSES = frozenset({
    'UNAUTHORIZED_UNDERPRICING',
    'MISSED_CONTRACT_PRICE_INCREASE',
    'UNAUTHORIZED_DISCOUNT_INDICATOR',
})
MONETARY_CLASSES = LEAKAGE_CLASSES | frozenset({
    'PRICING_COMPLIANT',
    'PRICE_ABOVE_APPROVED_RATE',
})
REVIEW_CLASSES = frozenset({
    'CONTRACT_COVERAGE_EXCEPTION',
    'CONTRACT_CONFLICT_REVIEW_REQUIRED',
    'MISSING_PRICING_EVIDENCE',
    'FX_OR_TAX_REVIEW_REQUIRED',
    'SOURCE_ALLOCATION_REVIEW_REQUIRED',
    'REFUND_REASSESSMENT_REQUIRED',
    'UNSUPPORTED_TRANSACTION',
    'TECHNICAL_AUDIT_FAILURE',
})
# Map flags that still allow a recomputation. Odoo's own missing rate is not
# a contract FX clause, and a tax-included invoice can be normalized here.
SOFT_BLOCKS = frozenset({
    'TAX_INCLUDED_REVIEW',
    'MISSING_FX_EVIDENCE',
    'RESOLVER_NOT_AUTHORITATIVE',
})
RUN_STATES = [
    ('draft', 'Draft'),
    ('queued', 'Queued'),
    ('running', 'Running'),
    ('completed', 'Completed'),
    ('completed_with_exceptions', 'Completed with exceptions'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
]
CLASSIFICATIONS = [
    ('UNAUTHORIZED_UNDERPRICING', 'Unauthorized underpricing'),
    ('MISSED_CONTRACT_PRICE_INCREASE', 'Missed contract price increase'),
    ('UNAUTHORIZED_DISCOUNT_INDICATOR', 'Unauthorized discount indicator'),
    ('PRICING_COMPLIANT', 'Pricing compliant'),
    ('PRICE_ABOVE_APPROVED_RATE', 'Price above approved rate'),
    ('WITHIN_APPROVED_TOLERANCE', 'Within approved tolerance'),
    ('CONTRACT_COVERAGE_EXCEPTION', 'Contract coverage exception'),
    ('CONTRACT_CONFLICT_REVIEW_REQUIRED', 'Contract conflict review'),
    ('MISSING_PRICING_EVIDENCE', 'Missing pricing evidence'),
    ('FX_OR_TAX_REVIEW_REQUIRED', 'FX or tax review'),
    ('SOURCE_ALLOCATION_REVIEW_REQUIRED', 'Source allocation review'),
    ('REFUND_REASSESSMENT_REQUIRED', 'Refund reassessment'),
    ('UNSUPPORTED_TRANSACTION', 'Unsupported transaction'),
    ('TECHNICAL_AUDIT_FAILURE', 'Technical audit failure'),
]
FINDING_STATES = [
    ('potential', 'Potential'),
    ('within_tolerance', 'Within tolerance'),
    ('review_required', 'Review required'),
    ('superseded_by_reassessment', 'Superseded by reassessment'),
    ('no_longer_current', 'No longer current'),
]


def _stamp(value):
    if not value:
        return ''
    return fields.Datetime.to_string(value)


def _hash(payload):
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class InvoiceAuditRun(models.Model):
    """One authorized read of posted customer invoices.

    The run stores potential leakage. It does not validate finance amounts,
    bill a recovery, collect cash, or schedule a recurring job.
    """

    _name = 'cpla.invoice.audit.run'
    _description = 'Invoice Audit Run'
    _order = 'id desc'
    _check_company_auto = True

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    mode = fields.Selection(
        selection=[
            ('on_demand', 'On demand'),
            ('historical_review', 'Historical review'),
            ('reassessment', 'Reassessment'),
            ('controlled_batch', 'Controlled batch'),
        ],
        required=True,
        default='on_demand',
    )
    state = fields.Selection(
        selection=RUN_STATES, required=True, default='draft', readonly=True, index=True,
        copy=False,
    )
    date_basis = fields.Selection(
        selection=[
            ('invoice_date', 'Invoice date'),
            ('posting_date', 'Posting date'),
        ],
        required=True,
        default='invoice_date',
        help='This selects which documents are read. It is not the contractual pricing date.',
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    partner_id = fields.Many2one('res.partner', check_company=True)
    product_id = fields.Many2one('product.product', check_company=True)
    contract_id = fields.Many2one('cpla.customer.contract', check_company=True)
    knowledge_cutoff = fields.Datetime(
        copy=False,
        help='Leave this empty for the current approved history. A timestamp excludes versions approved after it. The clock is not stamped on every repeat.',
    )
    batch_size = fields.Integer(default=50)
    initiated_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    started_on = fields.Datetime(readonly=True, copy=False)
    finished_on = fields.Datetime(readonly=True, copy=False)
    selected_count = fields.Integer(readonly=True, copy=False)
    processed_count = fields.Integer(readonly=True, copy=False)
    completed_count = fields.Integer(readonly=True, copy=False)
    review_count = fields.Integer(readonly=True, copy=False)
    finding_count = fields.Integer(readonly=True, copy=False)
    excluded_count = fields.Integer(readonly=True, copy=False)
    failure_count = fields.Integer(readonly=True, copy=False)
    potential_exposure_exact = fields.Char(
        readonly=True,
        copy=False,
        help='Sum of current potential leakage for this run. Not finance-validated, not billed, and not collected.',
    )
    error_summary = fields.Char(readonly=True, copy=False)
    result_ids = fields.One2many('cpla.invoice.audit.result', 'run_id')
    finding_ids = fields.One2many('cpla.leakage.finding', 'run_id')

    @api.model
    def _can_run(self):
        if self.env.su or self.env.user._is_superuser():
            return True
        return any(self.env.user.has_group(group) for group in RUN_GROUPS)

    @api.model
    def _check_runner(self):
        if self._can_run():
            return True
        raise AccessError(self.env._(
            'You are not allowed to run a posted-invoice audit.'
        ))

    def _check_company_scope(self):
        self.ensure_one()
        if self.company_id not in self.env.companies and not self.env.su:
            raise AccessError(self.env._(
                'You cannot audit invoices for this company.'
            ))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_runner()
        cleaned = []
        for vals in vals_list:
            company = self.env['res.company'].browse(vals.get('company_id')).exists()
            if not company:
                raise UserError(self.env._('An audit run needs a company.'))
            if company not in self.env.companies and not self.env.su:
                raise AccessError(self.env._(
                    'You cannot audit invoices for this company.'
                ))
            date_from = vals.get('date_from')
            date_to = vals.get('date_to')
            if not date_from or not date_to or date_to < date_from:
                raise UserError(self.env._(
                    'The audit needs a start and an end. An open-ended invoice scan was not started.'
                ))
            reference = self.env['ir.sequence'].with_company(company).next_by_code(RUN_SEQUENCE)
            if not reference:
                raise UserError(self.env._(
                    'The audit run sequence is missing. No reference was invented.'
                ))
            mode = vals.get('mode') or 'on_demand'
            if mode not in ('on_demand', 'historical_review', 'reassessment', 'controlled_batch'):
                raise UserError(self.env._('This audit mode is not supported.'))
            basis = vals.get('date_basis') or 'invoice_date'
            if basis not in ('invoice_date', 'posting_date'):
                raise UserError(self.env._('The selection date basis is not supported.'))
            batch = vals.get('batch_size') or 50
            cleaned.append({
                'reference': reference,
                'company_id': company.id,
                'mode': mode,
                'state': 'draft',
                'date_basis': basis,
                'date_from': date_from,
                'date_to': date_to,
                'partner_id': vals.get('partner_id') or False,
                'product_id': vals.get('product_id') or False,
                'contract_id': vals.get('contract_id') or False,
                'knowledge_cutoff': vals.get('knowledge_cutoff') or False,
                'batch_size': batch,
                'initiated_by_id': self.env.user.id,
            })
        return super().create(cleaned)

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        draft_fields = {
            'mode', 'date_basis', 'date_from', 'date_to', 'partner_id',
            'product_id', 'contract_id', 'knowledge_cutoff', 'batch_size',
        }
        if set(vals) <= draft_fields and all(run.state == 'draft' for run in self):
            if not self._can_run():
                raise AccessError(self.env._('You cannot change this audit run.'))
            return super().write(vals)
        raise UserError(self.env._(
            'Accepted audit run evidence cannot be overwritten.'
        ))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.check_access('unlink')
        raise UserError(self.env._('An audit run cannot be deleted.'))

    def action_queue(self):
        self._check_runner()
        for run in self:
            run._check_company_scope()
            if run.state != 'draft':
                raise UserError(self.env._('Only a draft audit can be queued.'))
            models.Model.write(run, {'state': 'queued'})
        return True

    def action_cancel(self):
        self._check_runner()
        for run in self:
            run._check_company_scope()
            if run.state not in ('draft', 'queued'):
                raise UserError(self.env._(
                    'A running or finished audit cannot be cancelled from this screen.'
                ))
            models.Model.write(run, {'state': 'cancelled'})
        return True

    def action_run(self):
        """Audit the selected posted customer documents. Accounting records stay unchanged."""
        self.ensure_one()
        self._check_runner()
        self._check_company_scope()
        if self.state not in ('draft', 'queued'):
            raise UserError(self.env._(
                'This audit has already been started. Start a new run to read the documents again.'
            ))
        if self.date_to < self.date_from:
            raise UserError(self.env._('The audit end is before the start.'))
        # A blank cutoff is the current reading. Stamping "now" on every run
        # would make each repeat a new current exposure key.
        models.Model.write(self, {
            'state': 'running',
            'started_on': fields.Datetime.now(),
            'failure_count': 0,
            'error_summary': False,
        })
        stats = {
            'selected': 0,
            'processed': 0,
            'completed': 0,
            'review': 0,
            'findings': 0,
            'excluded': 0,
            'failures': 0,
        }
        try:
            moves = self._select_moves()
            stats['selected'] = len(moves)
            size = self.batch_size or 50
            if size < 1:
                size = 50
            if size > BATCH_CAP:
                size = BATCH_CAP
            ordered = moves.filtered(lambda move: move.move_type == 'out_invoice')
            ordered |= moves.filtered(lambda move: move.move_type == 'out_refund')
            pending = list(ordered)
            index = 0
            while index < len(pending):
                window = pending[index:index + size]
                index += size
                for move in window:
                    try:
                        with self.env.cr.savepoint():
                            outcome = self._audit_move(move)
                    except Exception:
                        stats['failures'] += 1
                        _logger.info(
                            'CPLA audit move failed run=%s move=%s',
                            self.reference,
                            move.id,
                        )
                        continue
                    stats['processed'] += 1
                    stats['completed'] += outcome['completed']
                    stats['review'] += outcome['review']
                    stats['findings'] += outcome['findings']
                    stats['excluded'] += outcome['excluded']
        except Exception:
            models.Model.write(self, {
                'state': 'failed',
                'finished_on': fields.Datetime.now(),
                'failure_count': stats['failures'] + 1,
                'error_summary': 'The audit run failed before every selected document was read.',
                'selected_count': stats['selected'],
                'processed_count': stats['processed'],
            })
            _logger.info('CPLA audit run failed reference=%s', self.reference)
            raise
        exposure = self._exposure_text()
        stats['findings'] = self.env['cpla.leakage.finding'].search_count([
            ('run_id', '=', self.id),
            ('is_current', '=', True),
            ('finding_status', '=', 'potential'),
            ('company_id', '=', self.company_id.id),
        ])
        if stats['failures'] and not stats['processed']:
            state = 'failed'
        elif stats['failures'] or stats['review']:
            state = 'completed_with_exceptions'
        else:
            state = 'completed'
        summary = False
        if stats['failures']:
            summary = '%s technical failures. Completed documents were not rolled back.' % stats['failures']
        models.Model.write(self, {
            'state': state,
            'finished_on': fields.Datetime.now(),
            'selected_count': stats['selected'],
            'processed_count': stats['processed'],
            'completed_count': stats['completed'],
            'review_count': stats['review'],
            'finding_count': stats['findings'],
            'excluded_count': stats['excluded'],
            'failure_count': stats['failures'],
            'potential_exposure_exact': exposure,
            'error_summary': summary,
        })
        return True

    def action_reassess(self):
        """Open a new run for the same selection. The previous results stay."""
        self.ensure_one()
        self._check_runner()
        self._check_company_scope()
        fresh = self.create({
            'company_id': self.company_id.id,
            'mode': 'reassessment',
            'date_basis': self.date_basis,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'partner_id': self.partner_id.id,
            'product_id': self.product_id.id,
            'contract_id': self.contract_id.id,
            'batch_size': self.batch_size,
        })
        fresh.action_run()
        return fresh.action_open_form()

    def action_open_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.reference,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_results(self):
        self.ensure_one()
        self._check_company_scope()
        return self._window('cpla.invoice.audit.result', [('run_id', '=', self.id)], 'Audit results')

    def action_view_findings(self):
        self.ensure_one()
        self._check_company_scope()
        return self._window(
            'cpla.leakage.finding',
            [('run_id', '=', self.id), ('is_current', '=', True)],
            'Potential leakage findings',
        )

    def action_view_exceptions(self):
        self.ensure_one()
        self._check_company_scope()
        return self._window(
            'cpla.invoice.audit.result',
            [
                ('run_id', '=', self.id),
                ('result_classification', 'in', tuple(REVIEW_CLASSES)),
            ],
            'Audit exceptions',
        )

    def _window(self, model, domain, name):
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
        }

    def _select_moves(self):
        self.ensure_one()
        self._check_company_scope()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
        ]
        if self.date_basis == 'posting_date':
            domain += [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        else:
            domain += [
                ('invoice_date', '>=', self.date_from),
                ('invoice_date', '<=', self.date_to),
            ]
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.product_id:
            domain.append(('invoice_line_ids.product_id', '=', self.product_id.id))
        return self.env['account.move'].search(domain, order='invoice_date, id')

    def _audit_move(self, move):
        self.ensure_one()
        move = move.exists()
        if not move or len(move) != 1:
            raise UserError(self.env._('The invoice to audit does not exist.'))
        if move.company_id != self.company_id:
            raise AccessError(self.env._('The invoice is outside this audit run.'))
        move.check_access('read')
        if move.company_id not in self.env.companies and not self.env.su:
            raise AccessError(self.env._('The invoice is outside this audit run.'))
        maps = self.env['cpla.invoice.source'].map_move(move)
        outcome = {'completed': 0, 'review': 0, 'findings': 0, 'excluded': 0}
        current = maps.filtered('is_current')
        for mapping in current.sorted('id'):
            piece = self._audit_mapping(mapping)
            for key in outcome:
                outcome[key] += piece[key]
        return outcome

    def _audit_mapping(self, mapping):
        self.ensure_one()
        if self.product_id and mapping.product_id and mapping.product_id != self.product_id:
            return {'completed': 0, 'review': 0, 'findings': 0, 'excluded': 1}
        if self.contract_id and mapping.allocation_ids and mapping.contract_scope_mismatch(self.contract_id):
            return {'completed': 0, 'review': 0, 'findings': 0, 'excluded': 1}
        document = mapping.document_class
        if document not in ('ELIGIBLE_CUSTOMER_INVOICE', 'ELIGIBLE_CUSTOMER_CREDIT'):
            self._store_result(mapping, self._plain(
                'UNSUPPORTED_TRANSACTION',
                'The document is not a posted customer invoice or credit.',
            ), False)
            return {'completed': 0, 'review': 0, 'findings': 0, 'excluded': 1}
        if mapping.line_class in EXCLUDED_LINE_CLASSES or mapping.mapping_status == 'UNSUPPORTED_LINE_TYPE':
            note = 'This line is not a commercial product or service line.'
            if mapping.credit_class == 'TAX_ONLY_CORRECTION':
                note = 'A tax-only credit is not a product return and it is not collected cash.'
            self._store_result(mapping, self._plain('UNSUPPORTED_TRANSACTION', note), False)
            return {'completed': 0, 'review': 0, 'findings': 0, 'excluded': 1}
        if document == 'ELIGIBLE_CUSTOMER_CREDIT':
            return self._audit_credit(mapping)
        return self._audit_invoice_line(mapping)

    def _audit_invoice_line(self, mapping):
        allocations = mapping.allocation_ids
        if not mapping.quantity_trusted or not allocations:
            outcome = self._review_from_mapping(mapping)
            finding = self._store_review(mapping, False, outcome)
            self._store_result(mapping, outcome, finding)
            self._release_other_findings(mapping, [finding] if finding else [])
            return {
                'completed': 0,
                'review': 1,
                'findings': 0,
                'excluded': 0,
            }
        if self.contract_id and any(
            allocation.contract_id and allocation.contract_id != self.contract_id
            for allocation in allocations
        ):
            return {'completed': 0, 'review': 0, 'findings': 0, 'excluded': 1}
        invoice_qty = _decimal(mapping.source_quantity_exact)
        allocated = ZERO
        for allocation in allocations:
            part = _decimal(allocation.allocated_quantity_exact)
            if part is None:
                outcome = self._plain(
                    'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                    'An allocated quantity is missing. No price was spread across the line.',
                )
                finding = self._store_review(mapping, False, outcome)
                self._store_result(mapping, outcome, finding)
                return {'completed': 0, 'review': 1, 'findings': 0, 'excluded': 0}
            allocated = _arithmetic('add', allocated, part)
        if invoice_qty is None or allocated != invoice_qty:
            outcome = self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'Allocated quantities do not equal the invoice line. No proportional split was invented.',
            )
            finding = self._store_review(mapping, False, outcome)
            self._store_result(mapping, outcome, finding)
            self._release_other_findings(mapping, [finding] if finding else [])
            return {'completed': 0, 'review': 1, 'findings': 0, 'excluded': 0}
        completed = 0
        review = 0
        findings = 0
        kept = []
        for allocation in allocations:
            outcome = self._price_allocation(mapping, allocation)
            finding = False
            if outcome.get('authoritative') and outcome.get('persist_finding'):
                finding = self._upsert_priced(mapping, allocation, outcome)
                if finding and finding.finding_status == 'potential':
                    findings += 1
                completed += 1
            elif not outcome.get('authoritative'):
                finding = self._store_review(mapping, allocation, outcome)
                review += 1
            else:
                self._clear_priced(mapping, allocation, outcome)
                completed += 1
            if finding:
                kept.append(finding)
            self._store_result(mapping, outcome, finding, allocation)
        if completed and not review:
            pass
        self._release_other_findings(mapping, kept)
        return {
            'completed': completed,
            'review': review,
            'findings': findings,
            'excluded': 0,
        }

    def _audit_credit(self, mapping):
        kind = mapping.credit_class or 'UNKNOWN_CREDIT_REASON'
        if kind in ('QUANTITY_RETURN', 'FULL_REVERSAL') and mapping.quantity_trusted and mapping.origin_line_id:
            note = (
                'Verified reversal applied to the original invoice line. '
                'This credit is not a new sale and it is not collected cash.'
            )
            outcome = self._plain('PRICING_COMPLIANT', note)
            outcome['credit_treatment'] = (
                'verified_full_reversal' if kind == 'FULL_REVERSAL' else 'verified_quantity_return'
            )
            outcome['authoritative'] = True
            outcome['persist_finding'] = False
            self._store_result(mapping, outcome, False)
            self._reprice_origin(mapping.origin_line_id)
            return {'completed': 1, 'review': 0, 'findings': 0, 'excluded': 0}
        if kind == 'PRICE_ADJUSTMENT':
            note = (
                'This credit changes the amount owed and was not converted into returned units. '
                'It was not treated as cash recovered from the customer.'
            )
        elif kind == 'TAX_ONLY_CORRECTION':
            note = 'A tax-only credit is not a product return and it is not collected cash.'
        else:
            note = (
                'The credit could not be tied to one original quantity. '
                'No exposure was reduced and no cash recovery was recorded.'
            )
        outcome = self._plain('REFUND_REASSESSMENT_REQUIRED', note)
        outcome['credit_treatment'] = kind.lower()
        finding = self._store_review(mapping, False, outcome)
        self._store_result(mapping, outcome, finding)
        return {'completed': 0, 'review': 1, 'findings': 0, 'excluded': 0}

    def _reprice_origin(self, origin_line):
        origin_line.check_access('read')
        if origin_line.move_id.company_id != self.company_id:
            raise AccessError(self.env._('The original invoice is outside this audit run.'))
        maps = self.env['cpla.invoice.source'].map_line(origin_line)
        current = maps.filtered(lambda item: item.is_current and item.move_line_id == origin_line)
        for mapping in current:
            self._audit_invoice_line(mapping)

    def _price_allocation(self, mapping, allocation):
        blockers = set(self._codes(mapping.exception_codes)) - SOFT_BLOCKS
        if 'HISTORICAL_SOURCE_CHANGED' in blockers or not mapping.quantity_trusted:
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'Source evidence changed and has not been accepted. The previous audit result was kept.',
            )
        lock = allocation.price_lock_id
        version = allocation.confirmed_version_id
        if not lock or not version:
            return self._plain(
                'CONTRACT_COVERAGE_EXCEPTION',
                'No confirmed contract price is stored for this sales line. No price was invented.',
            )
        if lock.company_id != mapping.company_id or version.company_id != mapping.company_id:
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'The confirmed price belongs to another company. It was not applied.',
            )
        policy = allocation.pricing_date_policy_snapshot or 'unconfigured'
        eligible = self._eligible_quantity(mapping, allocation)
        if eligible is None:
            return self._plain(
                'REFUND_REASSESSMENT_REQUIRED',
                'Returned quantity could not be reconciled to this invoice line.',
            )
        if eligible < ZERO:
            return self._plain(
                'REFUND_REASSESSMENT_REQUIRED',
                'Returned quantity is larger than the billed quantity. No negative sale was created.',
            )
        original = _decimal(allocation.allocated_quantity_exact)
        if original is None or original <= ZERO:
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'The allocated quantity is not a positive billed quantity.',
            )
        request = self._price_request(mapping, allocation, original)
        line = version.line_ids.filtered(lambda item: item.product_id == mapping.product_id)[:1]
        returned = _arithmetic('sub', original, eligible)
        if policy == 'order_confirmation' and allocation.order_date_lock_candidate:
            lock_date = allocation.lock_pricing_date or allocation.applicable_pricing_date
            if not lock_date:
                return self._plain(
                    'MISSING_PRICING_EVIDENCE',
                    'The confirmed order has no pricing date. Today was not used.',
                )
            request['pricing_date'] = lock_date
            if not line:
                return self._plain(
                    'MISSING_PRICING_EVIDENCE',
                    'The locked contract version has no line for this product.',
                )
            self._apply_return_tier(request, line, eligible, returned)
            priced = self._price_locked(line, request)
        elif policy == 'invoice':
            priced = self._price_invoice_date(mapping, allocation, request)
            line = self.env['cpla.customer.contract.version.line'].browse(
                priced.get('version_line_id')
            ).exists()
            if priced.get('authoritative') and self._apply_return_tier(request, line, eligible, returned):
                priced = self._price_invoice_date(mapping, allocation, request)
                line = self.env['cpla.customer.contract.version.line'].browse(
                    priced.get('version_line_id')
                ).exists()
        else:
            return self._plain(
                'MISSING_PRICING_EVIDENCE',
                'The pricing-date rule on the confirmed order is not an operational invoice or order-date rule.',
            )
        if not priced.get('authoritative'):
            return priced
        actual, actual_problem = self._actual_unit(mapping, priced)
        if actual_problem:
            return actual_problem
        return self._waterfall(mapping, allocation, line, priced, actual, original, eligible)

    def _price_request(self, mapping, allocation, quantity):
        sale_line = allocation.sale_line_id
        order_qty = allocation.price_lock_id.quantity_exact or allocation.ordered_quantity_exact
        return {
            'company_id': mapping.company_id.id,
            'partner_id': mapping.partner_id.id,
            'product_id': mapping.product_id.id,
            'pricing_date': False,
            'quantity': _text(quantity),
            'order_quantity': order_qty,
            'invoice_quantity': _text(quantity),
            'quantity_uom_id': mapping.uom_id.id,
            'comparison_uom_id': mapping.uom_id.id,
            'sale_reference': str(sale_line.order_id.id) if sale_line else '',
            'sale_line_reference': str(sale_line.id) if sale_line else '',
            'knowledge_cutoff': self.knowledge_cutoff,
            'invoice_date': mapping.invoice_date,
        }

    def _apply_return_tier(self, request, line, eligible, returned):
        """Retier only when the selected line says net quantity and a tier exists.

        A zero eligible quantity is not sent back into tier selection. A line
        without an approved net-quantity rule keeps its original unit price.
        """
        if not line or eligible <= ZERO or returned <= ZERO:
            return False
        if line.return_policy != 'net_quantity' or not line.tier_ids:
            return False
        request['returned_quantity'] = _text(returned)
        return True

    def _price_locked(self, line, request):
        request = dict(request)
        if not request.get('pricing_date'):
            return self._plain(
                'MISSING_PRICING_EVIDENCE',
                'The confirmed order has no pricing date. Today was not used.',
            )
        quantity_result = self.env['cpla.pricing.quantity'].evaluate(line, request)
        if quantity_result.get('status'):
            return self._quantity_review(quantity_result)
        priced = self.env['cpla.discount.evaluator'].evaluate(line, request)
        if priced.get('discount_status') not in AUTHORITATIVE:
            return self._discount_review(priced)
        priced = dict(priced)
        priced['authoritative'] = True
        priced['version_id'] = line.version_id.id
        priced['version_line_id'] = line.id
        priced['contract_id'] = line.version_id.contract_id.id
        priced['tier_id'] = quantity_result.get('tier_id') or False
        priced['qualified_quantity_exact'] = quantity_result.get('qualified_quantity_exact') or False
        priced['grandfathering_applied'] = bool(
            line.version_id.pricing_date_policy_snapshot == 'order_confirmation'
        )
        priced['pricing_date'] = request['pricing_date']
        priced['quantity_status'] = quantity_result.get('quantity_status')
        return priced

    def _price_invoice_date(self, mapping, allocation, request):
        if not mapping.invoice_date:
            return self._plain(
                'MISSING_PRICING_EVIDENCE',
                'The invoice has no invoice date. Today was not used as the pricing date.',
            )
        payload = dict(request)
        payload['pricing_date'] = mapping.invoice_date
        resolved = self.env['cpla.pricing.applicability'].resolve(payload)
        status = resolved.get('status')
        if status != 'MATCHED_AUTHORITATIVE':
            return self._resolver_review(resolved)
        if resolved.get('discount_status') not in AUTHORITATIVE:
            return self._discount_review(resolved)
        if resolved.get('version_id'):
            version = self.env['cpla.customer.contract.version'].browse(resolved['version_id']).exists()
            if not version or version.company_id != mapping.company_id:
                return self._plain(
                    'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                    'The selected contract version is not in this company. No price was applied.',
                )
        priced = dict(resolved)
        priced['authoritative'] = True
        priced['pricing_date'] = mapping.invoice_date
        return priced

    def _waterfall(self, mapping, allocation, line, priced, actual, original, eligible):
        pre = _decimal(priced.get('pre_discount_unit_price_exact'))
        adjusted = _decimal(priced.get('approved_adjusted_unit_price_exact'))
        if pre is None or adjusted is None or adjusted <= ZERO or pre <= ZERO:
            return self._plain(
                'MISSING_PRICING_EVIDENCE',
                'The approved unit price is missing. No leakage amount was produced.',
            )
        version = self.env['cpla.customer.contract.version'].browse(priced.get('version_id')).exists()
        comparison_currency = self.env['res.currency'].browse(
            priced.get('comparison_currency_id')
        ).exists()
        comparison_uom = self.env['uom.uom'].browse(priced.get('comparison_uom_id')).exists()
        money_qty = eligible
        if comparison_uom and mapping.uom_id and comparison_uom != mapping.uom_id:
            converted = self.env['cpla.pricing.quantity'].convert_quantity(
                _text(eligible), mapping.uom_id.factor, comparison_uom.factor,
            )
            if not converted.get('ok'):
                return self._plain(
                    'MISSING_PRICING_EVIDENCE',
                    'The billed quantity could not be converted to the comparison unit.',
                )
            money_qty = _decimal(converted.get('exact'))
            if money_qty is None:
                return self._plain(
                    'MISSING_PRICING_EVIDENCE',
                    'The billed quantity could not be converted to the comparison unit.',
                )
        gross_unit = _arithmetic('sub', pre, actual)
        concession_unit = _arithmetic('sub', pre, adjusted)
        raw_unit = _arithmetic('sub', adjusted, actual)
        gross = _arithmetic('mul', gross_unit, money_qty)
        concession = _arithmetic('mul', concession_unit, money_qty)
        raw = _arithmetic('mul', raw_unit, money_qty)
        potential = raw if raw > ZERO else ZERO
        discount_applied = bool(priced.get('discount_applied'))
        earlier = self._matches_earlier_price(version, mapping.product_id, actual, comparison_currency, comparison_uom)
        classification, causes = self._classify_gap(raw_unit, discount_applied, earlier)
        pricing_date = priced.get('pricing_date') or allocation.applicable_pricing_date
        trace = self._trace(
            version, priced, mapping, actual, money_qty, gross, concession, raw, classification, causes,
        )
        return {
            'authoritative': True,
            'classification': classification,
            'causes': causes,
            'persist_finding': classification in LEAKAGE_CLASSES and potential > ZERO,
            'review_reason': False,
            'trace': trace,
            'pre': pre,
            'adjusted': adjusted,
            'actual': actual,
            'gross': gross,
            'concession': concession,
            'raw': raw,
            'potential': potential,
            'eligible': money_qty,
            'original_quantity': original,
            'qualified_quantity_exact': priced.get('qualified_quantity_exact') or False,
            'version': version,
            'line': line,
            'contract': version.contract_id if version else False,
            'tier_id': priced.get('tier_id') or False,
            'comparison_currency': comparison_currency,
            'comparison_uom': comparison_uom,
            'pricing_date': pricing_date,
            'fx_rate_exact': priced.get('fx_rate_exact') or False,
            'fx_date': priced.get('fx_date_used') or False,
            'tax_basis': priced.get('tax_basis') or False,
            'discount_status': priced.get('discount_status') or False,
            'grandfathering_applied': bool(priced.get('grandfathering_applied')),
            'credit_treatment': False,
            'snapshot': self._snapshot(mapping, allocation, priced, classification, causes),
        }

    def _classify_gap(self, raw_unit, discount_applied, earlier):
        if raw_unit == ZERO:
            return 'PRICING_COMPLIANT', []
        if raw_unit < ZERO:
            return 'PRICE_ABOVE_APPROVED_RATE', []
        causes = []
        if earlier:
            causes.append('MISSED_CONTRACT_PRICE_INCREASE')
        if discount_applied:
            causes.append('UNAUTHORIZED_DISCOUNT_INDICATOR')
            primary = 'UNAUTHORIZED_DISCOUNT_INDICATOR'
        elif earlier:
            primary = 'MISSED_CONTRACT_PRICE_INCREASE'
        else:
            primary = 'UNAUTHORIZED_UNDERPRICING'
        extra = [item for item in causes if item != primary]
        return primary, extra

    def _matches_earlier_price(self, version, product, actual, currency, uom):
        if not version or not product or actual is None:
            return False
        priors = self.env['cpla.customer.contract.version'].search([
            ('contract_id', '=', version.contract_id.id),
            ('company_id', '=', version.company_id.id),
            ('state', '=', 'approved'),
            ('id', '!=', version.id),
            ('effective_from', '<', version.effective_from),
        ])
        cutoff = self.knowledge_cutoff
        resolver = self.env['cpla.pricing.applicability']
        for prior in priors:
            if cutoff and (not prior.approved_at or prior.approved_at > cutoff):
                continue
            if resolver._retroactive_blocked(prior):
                continue
            prior_line = prior.line_ids.filtered(lambda item: item.product_id == product)[:1]
            if not prior_line or prior_line.tier_method not in (False, 'none'):
                continue
            if currency and prior_line.currency_id != currency:
                continue
            if uom and prior_line.uom_id != uom:
                continue
            if _decimal(prior_line.price_unit) == actual:
                return True
        return False

    def _actual_unit(self, mapping, priced):
        effective = _decimal(mapping.effective_unit_exact)
        if effective is None:
            return None, self._plain(
                'MISSING_PRICING_EVIDENCE',
                'The posted unit price could not be read. No leakage amount was produced.',
            )
        net, problem = self._strip_tax(mapping, effective)
        if problem:
            return None, problem
        comparison_currency = self.env['res.currency'].browse(
            priced.get('comparison_currency_id')
        ).exists()
        version = self.env['cpla.customer.contract.version'].browse(priced.get('version_id')).exists()
        if comparison_currency and mapping.currency_id and mapping.currency_id != comparison_currency:
            if not version:
                return None, self._plain(
                    'FX_OR_TAX_REVIEW_REQUIRED',
                    'The invoice currency differs and no approved version supplies a rate.',
                )
            converted = self.env['cpla.pricing.financial']._convert_clause(
                net, mapping.currency_id, comparison_currency, version, {},
            )
            if converted.get('error'):
                return None, self._plain(
                    'FX_OR_TAX_REVIEW_REQUIRED',
                    'No approved exchange rate converts the invoice price. Today\'s rate was not used.',
                )
            net = converted.get('amount')
            priced['fx_rate_exact'] = converted.get('fx_rate_exact') or priced.get('fx_rate_exact')
            priced['fx_date_used'] = converted.get('fx_date_used') or False
        comparison_uom = self.env['uom.uom'].browse(priced.get('comparison_uom_id')).exists()
        if comparison_uom and mapping.uom_id and comparison_uom != mapping.uom_id:
            converted = self.env['cpla.pricing.quantity'].convert_price(
                _text(net), mapping.uom_id.factor, comparison_uom.factor,
            )
            if not converted.get('ok'):
                return None, self._plain(
                    'MISSING_PRICING_EVIDENCE',
                    'The invoice unit could not be converted. No leakage amount was produced.',
                )
            net = _decimal(converted.get('exact'))
        if net is None:
            return None, self._plain(
                'MISSING_PRICING_EVIDENCE',
                'The invoice unit price could not be normalized.',
            )
        return net, False

    def _strip_tax(self, mapping, effective):
        if mapping.tax_basis == 'tax_excluded':
            return effective, False
        taxes = mapping.move_line_id.tax_ids
        if len(taxes) != 1 or taxes.amount_type != 'percent':
            return None, self._plain(
                'FX_OR_TAX_REVIEW_REQUIRED',
                'The invoice tax is not one ordinary percent. No net price was guessed.',
            )
        tax = taxes
        if 'price_include_override' not in tax._fields or tax.price_include_override in (
            False, 'tax_excluded',
        ):
            return None, self._plain(
                'FX_OR_TAX_REVIEW_REQUIRED',
                'The invoice tax inclusion flag is not a verified included percent.',
            )
        percent = _decimal(tax.amount)
        if percent is None or percent <= ZERO:
            return None, self._plain(
                'FX_OR_TAX_REVIEW_REQUIRED',
                'The included tax percent is missing. No percent was invented.',
            )
        net = _arithmetic('div', effective * HUNDRED, HUNDRED + percent)
        return net, False

    def _eligible_quantity(self, mapping, allocation):
        original = _decimal(allocation.allocated_quantity_exact)
        if original is None:
            return None
        returned = self._returned_quantity(mapping.move_line_id)
        if returned is None:
            return None
        return _arithmetic('sub', original, returned)

    def _returned_quantity(self, origin_line):
        credits = self.env['cpla.invoice.source.map'].search([
            ('origin_line_id', '=', origin_line.id),
            ('company_id', '=', origin_line.move_id.company_id.id),
            ('is_current', '=', True),
            ('quantity_trusted', '=', True),
            ('credit_class', 'in', ('QUANTITY_RETURN', 'FULL_REVERSAL')),
        ])
        total = ZERO
        for credit in credits:
            if credit.uom_id and origin_line.product_uom_id and credit.uom_id != origin_line.product_uom_id:
                return None
            part = _decimal(credit.returned_quantity_exact)
            if part is None or part < ZERO:
                return None
            total = _arithmetic('add', total, part)
        return total

    def _review_from_mapping(self, mapping):
        status = mapping.mapping_status
        codes = set(self._codes(mapping.exception_codes))
        if status == 'MANUAL_INVOICE_REVIEW_REQUIRED' or 'INVOICE_WITHOUT_SALES_ORDER' in codes:
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'This invoice has no verified sales order. No order date and no contract price were invented.',
            )
        if status in ('SOURCE_ALLOCATION_REVIEW_REQUIRED', 'SOURCE_RELATION_CONFLICT'):
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'The invoice line has no single verified source allocation. No price was applied to the whole line.',
            )
        if 'CONTRACT_VERSION_CONFLICT' in codes:
            return self._plain(
                'CONTRACT_CONFLICT_REVIEW_REQUIRED',
                'More than one contract version is tied to this line. No price was selected.',
            )
        if 'WRONG_COMPANY_SOURCE' in codes:
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'A source from another company was rejected. No price was applied.',
            )
        if codes & {
            'DELIVERY_DATE_NOT_ALLOCATED', 'PRICING_DATE_MISSING',
            'PRICING_DATE_POLICY_NOT_OPERATIONAL',
        }:
            return self._plain(
                'MISSING_PRICING_EVIDENCE',
                'The pricing date is not available under the approved rule. Today was not substituted.',
            )
        if 'HISTORICAL_CONTRACT_MISSING' in codes or status == 'CONTRACT_CONTEXT_REVIEW_REQUIRED':
            if 'TAX_INCLUDED_REVIEW' in codes and not (codes - SOFT_BLOCKS - {'TAX_INCLUDED_REVIEW'}):
                return self._plain(
                    'FX_OR_TAX_REVIEW_REQUIRED',
                    'Included tax could not be normalized. No leakage amount was produced.',
                )
            return self._plain(
                'CONTRACT_COVERAGE_EXCEPTION',
                'No approved contract covers this posted line. No price was invented.',
            )
        if status == 'CREDIT_ORIGIN_REVIEW_REQUIRED':
            return self._plain(
                'REFUND_REASSESSMENT_REQUIRED',
                'The credit origin is not verified. No exposure was changed.',
            )
        return self._plain(
            'SOURCE_ALLOCATION_REVIEW_REQUIRED',
            'The invoice line is not ready for a price comparison.',
        )

    def _resolver_review(self, resolved):
        status = resolved.get('status') or ''
        reason = resolved.get('reason_code') or ''
        if status == 'CONFLICT_REVIEW_REQUIRED':
            return self._plain(
                'CONTRACT_CONFLICT_REVIEW_REQUIRED',
                'More than one approved contract matches. No price was selected.',
            )
        if status == 'NO_APPLICABLE_CONTRACT':
            return self._plain(
                'CONTRACT_COVERAGE_EXCEPTION',
                'No approved contract covers this company, customer, product, and pricing date.',
            )
        if 'FX' in status or 'TAX' in status or 'CURRENCY' in reason:
            return self._plain(
                'FX_OR_TAX_REVIEW_REQUIRED',
                'Currency or tax evidence is incomplete. No leakage amount was produced.',
            )
        if status == 'COMPANY_ACCESS_DENIED':
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'The contract is not available in this company. No price was returned.',
            )
        return self._plain(
            'MISSING_PRICING_EVIDENCE',
            'Historical contract evidence is incomplete. No leakage amount was produced.',
        )

    def _discount_review(self, priced):
        status = priced.get('discount_status') or priced.get('financial_status') or ''
        reason = '%s %s' % (priced.get('discount_reason') or '', priced.get('financial_reason') or '')
        if 'FX' in status or 'TAX' in status or 'CURRENCY' in reason.upper() or 'FX' in reason.upper():
            return self._plain(
                'FX_OR_TAX_REVIEW_REQUIRED',
                'The approved price could not be normalized. No leakage amount was produced.',
            )
        if status == 'COMPANY_ACCESS_DENIED':
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'The contract is not available in this company. No price was returned.',
            )
        return self._plain(
            'MISSING_PRICING_EVIDENCE',
            'The approved discount or price evidence is incomplete. No leakage amount was produced.',
        )

    def _quantity_review(self, quantity_result):
        status = quantity_result.get('status') or ''
        if status in ('INCOMPATIBLE_UOM', 'MISSING_HISTORICAL_CONVERSION'):
            return self._plain(
                'MISSING_PRICING_EVIDENCE',
                'The quantity unit cannot be compared. No leakage amount was produced.',
            )
        if 'ALLOCATION' in status:
            return self._plain(
                'SOURCE_ALLOCATION_REVIEW_REQUIRED',
                'The quantity allocation is not verified. No tier price was applied.',
            )
        return self._plain(
            'MISSING_PRICING_EVIDENCE',
            'The quantity tier could not be selected. No leakage amount was produced.',
        )

    def _plain(self, classification, reason):
        return {
            'authoritative': False,
            'classification': classification,
            'causes': [],
            'persist_finding': False,
            'review_reason': reason,
            'trace': reason,
            'pre': None,
            'adjusted': None,
            'actual': None,
            'gross': None,
            'concession': None,
            'raw': None,
            'potential': None,
            'eligible': None,
            'original_quantity': None,
            'qualified_quantity_exact': False,
            'version': self.env['cpla.customer.contract.version'],
            'line': self.env['cpla.customer.contract.version.line'],
            'contract': self.env['cpla.customer.contract'],
            'tier_id': False,
            'comparison_currency': self.env['res.currency'],
            'comparison_uom': self.env['uom.uom'],
            'pricing_date': False,
            'fx_rate_exact': False,
            'fx_date': False,
            'tax_basis': False,
            'discount_status': False,
            'grandfathering_applied': False,
            'credit_treatment': False,
            'snapshot': {'classification': classification, 'reason': reason, 'engine': ENGINE_VERSION},
        }

    def _trace(self, version, priced, mapping, actual, quantity, gross, concession, raw, classification, causes):
        lines = [
            'Version %s was selected. Pricing date %s. Selection date basis %s. Pricing-date policy %s.' % (
                version.reference if version else '',
                priced.get('pricing_date') or '',
                self.date_basis,
                version.pricing_date_policy_snapshot if version else '',
            ),
            'Pre-discount unit %s. Approved adjusted unit %s. Actual comparable unit %s.' % (
                priced.get('pre_discount_unit_price_exact') or '',
                priced.get('approved_adjusted_unit_price_exact') or '',
                _text(actual),
            ),
            'Eligible quantity %s. Ordered quantity was not reused as the billed quantity.' % _text(quantity),
            (
                'Eligible quantity is zero after a verified reversal. Current exposure is zero. '
                'This is not collected cash.'
                if quantity == ZERO else
                'Eligible quantity is the billed quantity that remains after verified quantity returns.'
            ),
            'Gross difference %s. Authorized concession %s. Signed unauthorized difference %s.' % (
                _text(gross), _text(concession), _text(raw),
            ),
            'Classification %s. Contributing causes: %s.' % (
                classification, ', '.join(causes) if causes else 'none',
            ),
            'Discount status %s. Tax basis %s. FX rate %s.' % (
                priced.get('discount_status') or '',
                priced.get('tax_basis') or mapping.tax_basis or '',
                priced.get('fx_rate_exact') or 'none',
            ),
            'Potential leakage is not finance-validated, billed recovery, or collected cash.',
            'Invoice %s line %s.' % (mapping.move_id.id, mapping.move_line_id.id),
        ]
        if priced.get('grandfathering_applied'):
            lines.append('An order-date lock was applied. A later version was not substituted.')
        return '\n'.join(lines)

    def _snapshot(self, mapping, allocation, priced, classification, causes):
        version_id = priced.get('version_id') or False
        return {
            'engine': ENGINE_VERSION,
            'classification': classification,
            'causes': causes,
            'move_id': mapping.move_id.id,
            'move_line_id': mapping.move_line_id.id,
            'allocation_id': allocation.id if allocation else 0,
            'version_id': version_id,
            'pricing_date': str(priced.get('pricing_date') or ''),
            'cutoff': self._cutoff_token(),
            'discount_status': priced.get('discount_status') or '',
            'fx_rate_exact': priced.get('fx_rate_exact') or '',
            'tax_basis': priced.get('tax_basis') or mapping.tax_basis or '',
            'source_fingerprint': mapping.source_fingerprint or '',
            'source_revision': mapping.revision or 0,
        }

    def _store_result(self, mapping, outcome, finding, allocation=None):
        self.ensure_one()
        allocation = allocation or mapping.allocation_ids[:1]
        version = outcome.get('version')
        contract = outcome.get('contract')
        values = {
            'run_id': self.id,
            'company_id': self.company_id.id,
            'move_id': mapping.move_id.id,
            'move_line_id': mapping.move_line_id.id,
            'map_id': mapping.id,
            'allocation_id': allocation.id if allocation else False,
            'partner_id': mapping.partner_id.id,
            'product_id': mapping.product_id.id,
            'sale_order_id': allocation.sale_order_id.id if allocation and allocation.sale_order_id else False,
            'sale_line_id': allocation.sale_line_id.id if allocation and allocation.sale_line_id else False,
            'contract_id': contract.id if contract else (allocation.contract_id.id if allocation else False),
            'version_id': version.id if version else False,
            'version_line_id': outcome['line'].id if outcome.get('line') else False,
            'tier_id': outcome.get('tier_id') or False,
            'finding_id': finding.id if finding else False,
            'pricing_date': outcome.get('pricing_date') or False,
            'invoice_date': mapping.invoice_date,
            'posting_date': mapping.posting_date,
            'knowledge_cutoff': self.knowledge_cutoff,
            'actual_quantity_exact': mapping.source_quantity_exact or False,
            'eligible_quantity_exact': _text(outcome['eligible']) if outcome.get('eligible') is not None else False,
            'qualified_quantity_exact': outcome.get('qualified_quantity_exact') or False,
            'comparison_uom_id': outcome['comparison_uom'].id if outcome.get('comparison_uom') else mapping.uom_id.id,
            'comparison_currency_id': (
                outcome['comparison_currency'].id if outcome.get('comparison_currency') else mapping.currency_id.id
            ),
            'approved_pre_concession_exact': _text(outcome['pre']) if outcome.get('pre') is not None else False,
            'approved_adjusted_exact': _text(outcome['adjusted']) if outcome.get('adjusted') is not None else False,
            'actual_unit_exact': _text(outcome['actual']) if outcome.get('actual') is not None else False,
            'gross_difference_exact': _text(outcome['gross']) if outcome.get('gross') is not None else False,
            'authorized_concession_exact': (
                _text(outcome['concession']) if outcome.get('concession') is not None else False
            ),
            'raw_difference_exact': _text(outcome['raw']) if outcome.get('raw') is not None else False,
            'potential_exposure_exact': (
                _text(outcome['potential']) if outcome.get('potential') is not None else False
            ),
            'result_classification': outcome['classification'],
            'contributing_causes': ','.join(outcome.get('causes') or []) or False,
            'review_reason': outcome.get('review_reason') or False,
            'calculation_trace': outcome.get('trace') or False,
            'evidence_snapshot': json.dumps(outcome.get('snapshot') or {}, sort_keys=True, default=str),
            'calculation_revision': finding.calculation_revision if finding else 1,
            'input_fingerprint': self._fingerprint(mapping, allocation, outcome),
            'source_revision': mapping.revision or 1,
            'credit_treatment': outcome.get('credit_treatment') or False,
            'engine_version': ENGINE_VERSION,
            'is_recovered_cash': False,
        }
        models.Model.create(self.env['cpla.invoice.audit.result'], [values])

    def _store_review(self, mapping, allocation, outcome):
        identity = self._identity(mapping.move_line_id, allocation)
        fingerprint = self._fingerprint(mapping, allocation, outcome)
        values = self._finding_values(mapping, allocation, outcome, 'review_required', False)
        return self._upsert(identity, fingerprint, values)

    def _upsert_priced(self, mapping, allocation, outcome):
        identity = self._identity(mapping.move_line_id, allocation)
        fingerprint = self._fingerprint(mapping, allocation, outcome)
        amount = _text(outcome['potential']) if outcome.get('potential') is not None else False
        values = self._finding_values(mapping, allocation, outcome, 'potential', amount)
        return self._upsert(identity, fingerprint, values)

    def _clear_priced(self, mapping, allocation, outcome):
        identity = self._identity(mapping.move_line_id, allocation)
        existing = self.env['cpla.leakage.finding'].search([
            ('current_identity', '=', identity),
        ], limit=1)
        if not existing:
            return False
        fingerprint = self._fingerprint(mapping, allocation, outcome)
        values = self._finding_values(mapping, allocation, outcome, 'no_longer_current', '0')
        return self._upsert(identity, fingerprint, values)

    def _finding_values(self, mapping, allocation, outcome, status, amount):
        version = outcome.get('version')
        return {
            'company_id': self.company_id.id,
            'move_id': mapping.move_id.id,
            'move_line_id': mapping.move_line_id.id,
            'allocation_id': allocation.id if allocation else False,
            'map_id': mapping.id,
            'run_id': self.id,
            'partner_id': mapping.partner_id.id,
            'product_id': mapping.product_id.id,
            'contract_id': version.contract_id.id if version else False,
            'version_id': version.id if version else False,
            'leakage_category': outcome['classification'],
            'contributing_causes': ','.join(outcome.get('causes') or []) or False,
            'approved_adjusted_exact': _text(outcome['adjusted']) if outcome.get('adjusted') is not None else False,
            'actual_unit_exact': _text(outcome['actual']) if outcome.get('actual') is not None else False,
            'eligible_quantity_exact': _text(outcome['eligible']) if outcome.get('eligible') is not None else False,
            'currency_id': (
                outcome['comparison_currency'].id if outcome.get('comparison_currency') else mapping.currency_id.id
            ),
            'potential_leakage_exact': amount,
            'finding_status': status,
            'review_reason': outcome.get('review_reason') or False,
            'evidence_snapshot': json.dumps(outcome.get('snapshot') or {}, sort_keys=True, default=str),
            'calculation_trace': outcome.get('trace') or False,
            'knowledge_cutoff': self.knowledge_cutoff,
            'source_revision': mapping.revision or 1,
            'engine_version': ENGINE_VERSION,
            'is_recovered_cash': False,
        }

    def _upsert(self, identity, fingerprint, values):
        finding_model = self.env['cpla.leakage.finding']
        existing = finding_model.search([('current_identity', '=', identity)], limit=1)
        if existing and existing.input_fingerprint == fingerprint:
            models.Model.write(existing, {
                'last_evaluated_at': fields.Datetime.now(),
                'run_id': self.id,
            })
            return existing
        revision = (existing.calculation_revision + 1) if existing else 1
        first_detected = existing.first_detected_at if existing else fields.Datetime.now()
        if existing:
            existing.write({
                'is_current': False,
                'current_identity': False,
                'finding_status': 'superseded_by_reassessment',
            })
            if 'cpla.finance.validation' in self.env.registry:
                self.env['cpla.finance.validation']._flag_source_change(existing)
        reference = self.env['ir.sequence'].with_company(self.company_id).next_by_code(FINDING_SEQUENCE)
        if not reference:
            raise UserError(self.env._(
                'The leakage finding sequence is missing. No public reference was invented.'
            ))
        values = dict(values)
        values.update({
            'reference': reference,
            'current_identity': identity,
            'is_current': True,
            'input_fingerprint': fingerprint,
            'calculation_revision': revision,
            'first_detected_at': first_detected,
            'last_evaluated_at': fields.Datetime.now(),
            'is_recovered_cash': False,
        })
        try:
            with self.env.cr.savepoint():
                return models.Model.create(finding_model, [values])
        except IntegrityError:
            current = finding_model.search([('current_identity', '=', identity)], limit=1)
            if current and current.input_fingerprint == fingerprint:
                return current
            raise

    def _cutoff_token(self):
        """Identity token for this run's historical cutoff.

        An empty cutoff is one stable current reading. An explicit cutoff
        stays distinct and is not merged with that current reading.
        """
        if not self.knowledge_cutoff:
            return 'none'
        return _stamp(self.knowledge_cutoff)

    def _release_other_findings(self, mapping, kept):
        kept_ids = {finding.id for finding in kept if finding}
        stamp = '|k%s|' % self._cutoff_token()
        current = self.env['cpla.leakage.finding'].search([
            ('company_id', '=', self.company_id.id),
            ('move_line_id', '=', mapping.move_line_id.id),
            ('is_current', '=', True),
        ])
        for finding in current:
            if finding.id in kept_ids:
                continue
            if stamp not in (finding.current_identity or ''):
                continue
            finding.write({
                'is_current': False,
                'current_identity': False,
                'finding_status': 'superseded_by_reassessment',
            })

    def _identity(self, line, allocation):
        alloc = allocation.id if allocation else 0
        return 'c%s|l%s|a%s|k%s|sUNDERBILLING' % (
            self.company_id.id, line.id, alloc, self._cutoff_token(),
        )

    def _fingerprint(self, mapping, allocation, outcome):
        version = outcome.get('version')
        payload = {
            'engine': ENGINE_VERSION,
            'company_id': self.company_id.id,
            'line_id': mapping.move_line_id.id,
            'allocation_id': allocation.id if allocation else 0,
            'cutoff': self._cutoff_token(),
            'source_fingerprint': mapping.source_fingerprint or '',
            'source_revision': mapping.revision or 0,
            'version_id': version.id if version else 0,
            'classification': outcome.get('classification'),
            'pre': _text(outcome['pre']) if outcome.get('pre') is not None else '',
            'adjusted': _text(outcome['adjusted']) if outcome.get('adjusted') is not None else '',
            'actual': _text(outcome['actual']) if outcome.get('actual') is not None else '',
            'eligible': _text(outcome['eligible']) if outcome.get('eligible') is not None else '',
            'potential': _text(outcome['potential']) if outcome.get('potential') is not None else '',
            'pricing_date': str(outcome.get('pricing_date') or ''),
            'discount_status': outcome.get('discount_status') or '',
            'fx_rate_exact': outcome.get('fx_rate_exact') or '',
            'tax_basis': outcome.get('tax_basis') or mapping.tax_basis or '',
            'credit_treatment': outcome.get('credit_treatment') or '',
        }
        return _hash(payload)

    def _exposure_text(self):
        self.ensure_one()
        findings = self.env['cpla.leakage.finding'].search([
            ('run_id', '=', self.id),
            ('is_current', '=', True),
            ('finding_status', '=', 'potential'),
            ('company_id', '=', self.company_id.id),
        ])
        total = ZERO
        seen = set()
        for finding in findings:
            if finding.current_identity in seen:
                continue
            seen.add(finding.current_identity)
            amount = _decimal(finding.potential_leakage_exact)
            if amount is None:
                continue
            if finding.currency_id and findings.filtered(
                lambda item: item.currency_id and item.currency_id != finding.currency_id
            ):
                return False
            total = _arithmetic('add', total, amount)
        return _text(total)

    @api.model
    def _codes(self, value):
        if not value:
            return []
        return [item.strip() for item in str(value).split(',') if item.strip()]

class InvoiceSourceMapAudit(models.Model):
    _inherit = 'cpla.invoice.source.map'

    def contract_scope_mismatch(self, contract):
        self.ensure_one()
        if not self.allocation_ids:
            return True
        return any(
            allocation.contract_id and allocation.contract_id != contract
            for allocation in self.allocation_ids
        )


class InvoiceAuditResult(models.Model):
    """One historical evaluation of an invoice line or source allocation.

    Rows are append-only. A later run does not rewrite this calculation.
    """

    _name = 'cpla.invoice.audit.result'
    _description = 'Invoice Audit Result'
    _order = 'id desc'
    _check_company_auto = True

    run_id = fields.Many2one(
        'cpla.invoice.audit.run', required=True, index=True, readonly=True, ondelete='restrict',
    )
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    move_id = fields.Many2one('account.move', readonly=True, index=True, ondelete='restrict')
    move_line_id = fields.Many2one('account.move.line', readonly=True, index=True, ondelete='restrict')
    map_id = fields.Many2one('cpla.invoice.source.map', readonly=True, index=True, ondelete='restrict')
    allocation_id = fields.Many2one(
        'cpla.invoice.source.allocation', readonly=True, index=True, ondelete='restrict',
    )
    partner_id = fields.Many2one('res.partner', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    sale_order_id = fields.Many2one('sale.order', readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', readonly=True)
    contract_id = fields.Many2one('cpla.customer.contract', readonly=True)
    version_id = fields.Many2one('cpla.customer.contract.version', readonly=True, index=True)
    version_line_id = fields.Many2one('cpla.customer.contract.version.line', readonly=True)
    tier_id = fields.Many2one('cpla.customer.contract.version.tier', readonly=True)
    finding_id = fields.Many2one('cpla.leakage.finding', readonly=True, index=True)
    pricing_date = fields.Date(readonly=True)
    invoice_date = fields.Date(readonly=True, index=True)
    posting_date = fields.Date(readonly=True)
    knowledge_cutoff = fields.Datetime(readonly=True)
    actual_quantity_exact = fields.Char(readonly=True)
    eligible_quantity_exact = fields.Char(readonly=True)
    qualified_quantity_exact = fields.Char(readonly=True)
    comparison_uom_id = fields.Many2one('uom.uom', readonly=True)
    comparison_currency_id = fields.Many2one('res.currency', readonly=True)
    approved_pre_concession_exact = fields.Char(readonly=True)
    approved_adjusted_exact = fields.Char(readonly=True)
    actual_unit_exact = fields.Char(readonly=True)
    gross_difference_exact = fields.Char(readonly=True)
    authorized_concession_exact = fields.Char(readonly=True)
    raw_difference_exact = fields.Char(readonly=True)
    potential_exposure_exact = fields.Char(readonly=True)
    result_classification = fields.Selection(selection=CLASSIFICATIONS, readonly=True, index=True)
    contributing_causes = fields.Char(readonly=True)
    review_reason = fields.Char(readonly=True)
    calculation_trace = fields.Text(readonly=True)
    evidence_snapshot = fields.Text(readonly=True)
    calculation_revision = fields.Integer(readonly=True, default=1)
    input_fingerprint = fields.Char(readonly=True, index=True)
    source_revision = fields.Integer(readonly=True, index=True)
    credit_treatment = fields.Char(readonly=True)
    engine_version = fields.Char(readonly=True)
    is_recovered_cash = fields.Boolean(readonly=True, default=False)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._(
            'Audit results are stored by the audit engine. Client amounts are ignored.'
        ))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        raise UserError(self.env._('An accepted audit result cannot be overwritten.'))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.check_access('unlink')
        raise UserError(self.env._('An audit result cannot be deleted.'))

    def action_view_evidence(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Calculation evidence'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class LeakageFinding(models.Model):
    """Current detector finding for one economic underbilling identity.

    Status values stop at potential, review, or no longer current.
    Finance validation and recovery are later phases.
    """

    _name = 'cpla.leakage.finding'
    _description = 'Potential Leakage Finding'
    _order = 'id desc'
    _check_company_auto = True

    _current_identity_unique = models.Constraint(
        'UNIQUE(current_identity)',
        'This economic source already has a current leakage finding.',
    )

    reference = fields.Char(required=True, readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True, readonly=True)
    move_id = fields.Many2one('account.move', readonly=True, index=True, ondelete='restrict')
    move_line_id = fields.Many2one(
        'account.move.line', required=True, readonly=True, index=True, ondelete='restrict',
    )
    allocation_id = fields.Many2one(
        'cpla.invoice.source.allocation', readonly=True, index=True, ondelete='restrict',
    )
    map_id = fields.Many2one('cpla.invoice.source.map', readonly=True, ondelete='restrict')
    run_id = fields.Many2one('cpla.invoice.audit.run', readonly=True, index=True, ondelete='restrict')
    partner_id = fields.Many2one('res.partner', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    contract_id = fields.Many2one('cpla.customer.contract', readonly=True)
    version_id = fields.Many2one('cpla.customer.contract.version', readonly=True, index=True)
    leakage_category = fields.Selection(selection=CLASSIFICATIONS, readonly=True, index=True)
    contributing_causes = fields.Char(readonly=True)
    approved_adjusted_exact = fields.Char(readonly=True)
    actual_unit_exact = fields.Char(readonly=True)
    eligible_quantity_exact = fields.Char(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    potential_leakage_exact = fields.Char(readonly=True)
    finding_status = fields.Selection(
        selection=FINDING_STATES, required=True, readonly=True, index=True,
    )
    review_reason = fields.Char(readonly=True)
    evidence_snapshot = fields.Text(readonly=True)
    calculation_trace = fields.Text(readonly=True)
    knowledge_cutoff = fields.Datetime(readonly=True, index=True)
    source_revision = fields.Integer(readonly=True, index=True)
    calculation_revision = fields.Integer(readonly=True, default=1)
    input_fingerprint = fields.Char(readonly=True, index=True)
    current_identity = fields.Char(readonly=True, index=True, copy=False)
    is_current = fields.Boolean(readonly=True, index=True, copy=False)
    first_detected_at = fields.Datetime(readonly=True)
    last_evaluated_at = fields.Datetime(readonly=True)
    engine_version = fields.Char(readonly=True)
    is_recovered_cash = fields.Boolean(readonly=True, default=False)

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access('create')
        raise UserError(self.env._(
            'Potential findings are stored by the audit engine. Client amounts are ignored.'
        ))

    def write(self, vals):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().write(vals)
        self.check_access('write')
        allowed = {'is_current', 'current_identity', 'finding_status'}
        engine_touch = {'last_evaluated_at', 'run_id'}
        if set(vals) <= engine_touch and self.env['cpla.invoice.audit.run']._can_run():
            return super().write(vals)
        if (
            set(vals) <= allowed
            and vals.get('is_current') is False
            and not vals.get('current_identity')
            and self.env['cpla.invoice.audit.run']._can_run()
        ):
            return super().write(vals)
        raise UserError(self.env._(
            'Accepted leakage evidence cannot be overwritten.'
        ))

    def unlink(self):
        from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super().unlink()
        self.check_access('unlink')
        raise UserError(self.env._('A leakage finding cannot be deleted.'))

    def action_view_evidence(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Calculation evidence'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class AccountMoveAudit(models.Model):
    _inherit = 'account.move'

    cpla_audit_result_count = fields.Integer(compute='_compute_cpla_audit_result_count')

    def _compute_cpla_audit_result_count(self):
        result_model = self.env['cpla.invoice.audit.result']
        for move in self:
            move.cpla_audit_result_count = result_model.search_count([
                ('move_id', '=', move.id),
            ])

    def action_cpla_open_audit_results(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Invoice audit'),
            'res_model': 'cpla.invoice.audit.result',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
            'target': 'current',
        }
