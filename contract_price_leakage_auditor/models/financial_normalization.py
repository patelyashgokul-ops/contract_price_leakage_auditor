import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

MODULE = 'contract_price_leakage_auditor'
USER_GROUP = f'{MODULE}.group_contract_user'
MANAGER_GROUP = f'{MODULE}.group_contract_manager'
REVIEWER_GROUP = f'{MODULE}.group_finance_reviewer'
FINANCE_MANAGER_GROUP = f'{MODULE}.group_finance_manager'
AUDITOR_GROUP = f'{MODULE}.group_internal_auditor'

READ_GROUPS = (
    USER_GROUP,
    MANAGER_GROUP,
    REVIEWER_GROUP,
    FINANCE_MANAGER_GROUP,
    AUDITOR_GROUP,
)

SUCCESS_STATUSES = ('NORMALIZED', 'SAME_CURRENCY_NO_CONVERSION')
HISTORICAL_POLICIES = ('historical_exact_date', 'historical_last_known_prior')
DOCUMENT_DATE_SOURCES = ('pricing_date', 'order_confirmation_date', 'invoice_date')
COMPLEX_TAX_STRUCTURES = ('fixed', 'division', 'group', 'tax_on_tax', 'complex')
SERVER_FX_FIELDS = frozenset({
    'fx_policy_date',
    'fx_rate_date_used',
    'fx_rate_id',
    'fx_target_rate_id',
    'fx_company_per_source_exact',
    'fx_company_per_target_exact',
})
FORGED_REQUEST_KEYS = (
    'version_id', 'contract_id', 'unit_price', 'tier_id',
    'normalized_unit_price', 'contract_unit_price', 'source_price_exact',
    'comparable_unit_price', 'comparable_unit_price_exact', 'fx_rate',
    'fx_rate_id', 'fx_date', 'fx_policy',
    'fx_multiplier', 'fx_multiplier_exact', 'tax_percent', 'tax_basis',
    'tolerance', 'tolerance_amount', 'tolerance_percent', 'rounding',
    'financial_status', 'leakage_amount',
)


def _decimal(value):
    """Finite decimal, or None. Boolean and blank values are not numbers."""
    if isinstance(value, bool) or value is None or value is False or value == '':
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None
    if not number.is_finite():
        return None
    return number


def _text(number):
    """Canonical exact text. 84.0 and 84 are the same rate."""
    text = format(number, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    if text in ('', '-0'):
        return '0'
    return text


def _arithmetic(operator, left, right):
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        if operator == 'mul':
            return + (left * right)
        if operator == 'div':
            return + (left / right)
        if operator == 'add':
            return + (left + right)
        if operator == 'sub':
            return + (left - right)
    return None


class CustomerContractVersionFinancial(models.Model):
    """Contract-level financial clause. Company policy candidates are not applied."""

    _inherit = 'cpla.customer.contract.version'

    fx_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('fixed_rate', 'Contractually fixed rate'),
            ('historical_exact_date', 'Exact historical rate date'),
            ('historical_last_known_prior', 'Latest eligible prior rate'),
        ],
        default='unconfigured',
        required=True,
        string='Contract FX clause',
        help='Company FX candidates are not an approved policy. A blank clause does not select a rate.',
    )
    fx_date_source = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('explicit_date', 'Explicit date on this version'),
            ('contract_effective_date', 'Contract effective date'),
            ('pricing_date', 'Contract pricing date'),
            ('order_confirmation_date', 'Sales order confirmation date'),
            ('invoice_date', 'Invoice date'),
        ],
        default='unconfigured',
        required=True,
        string='FX date source',
        help='Invoice date and pricing date are not defaults. A document date is not snapshotted until that date is known.',
    )
    fx_explicit_date = fields.Date(
        string='Explicit FX date',
        help='Used only when the FX date source is the explicit date on this version.',
    )
    fx_source_currency_id = fields.Many2one(
        'res.currency',
        string='FX source currency',
    )
    fx_target_currency_id = fields.Many2one(
        'res.currency',
        string='FX target currency',
    )
    fx_multiplier_exact = fields.Char(
        string='Fixed rate exact',
        help='Target currency units for one source currency unit. Only a fixed-rate clause stores this number. A historical clause snapshots its own evidence at approval.',
    )
    fx_policy_date = fields.Date(
        string='FX policy date',
        readonly=True,
        copy=False,
        help='Date the approved clause asked for. It is not replaced by today.',
    )
    fx_rate_date_used = fields.Date(
        string='FX rate date used',
        readonly=True,
        copy=False,
        help='Date of the rate row that was frozen. A later prior rate is not a silent substitute.',
    )
    fx_rate_id = fields.Many2one(
        'res.currency.rate',
        string='Frozen source rate',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    fx_target_rate_id = fields.Many2one(
        'res.currency.rate',
        string='Frozen target rate',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    fx_company_per_source_exact = fields.Char(
        string='Frozen company units per source',
        readonly=True,
        copy=False,
    )
    fx_company_per_target_exact = fields.Char(
        string='Frozen company units per target',
        readonly=True,
        copy=False,
    )
    comparison_currency_policy = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('contract_currency', 'Contract currency'),
            ('company_currency', 'Company currency'),
            ('explicit_currency', 'Explicit comparison currency'),
        ],
        default='unconfigured',
        required=True,
        string='Comparison currency',
        help='Contract currency, company currency, and an explicit comparison currency are different choices.',
    )
    comparison_currency_id = fields.Many2one(
        'res.currency',
        string='Explicit comparison currency',
    )
    tax_basis = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('tax_excluded', 'Tax excluded'),
            ('tax_included', 'Tax included'),
        ],
        default='unconfigured',
        required=True,
        string='Contract tax basis',
        help='Tax-included and tax-excluded prices are not compared directly. This clause is not a tax filing.',
    )
    tax_structure = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('none', 'No tax in the price'),
            ('single_ordinary_percent', 'One ordinary percentage'),
            ('fixed', 'Fixed tax'),
            ('division', 'Division tax'),
            ('group', 'Group of taxes'),
            ('tax_on_tax', 'Tax on tax'),
            ('complex', 'Complex or unverified'),
        ],
        default='unconfigured',
        required=True,
        string='Contract tax structure',
    )
    tax_percent_exact = fields.Char(
        string='Ordinary tax percent',
        help='Used only for one ordinary percentage. A group, fixed amount, or division tax is not divided by one plus this percent.',
    )
    rounding_stage = fields.Selection(
        selection=[
            ('unconfigured', 'Not configured'),
            ('preserve_exact', 'Preserve exact decimals'),
            ('per_unit', 'Round the comparable unit'),
            ('extended_amount', 'Round the extended amount'),
        ],
        default='unconfigured',
        required=True,
        string='Rounding stage',
        help='Unconfigured keeps the exact decimal. Company currency rounding is not applied unless this clause names a stage. It is not a tolerance.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            illegal = sorted(SERVER_FX_FIELDS & set(vals))
            if illegal:
                raise UserError(self.env._(
                    'Historical FX evidence is recorded at approval. '
                    'Client values were rejected: %(fields)s.',
                    fields=', '.join(illegal),
                ))
        return super().create(vals_list)

    def write(self, vals):
        illegal = sorted(SERVER_FX_FIELDS & set(vals))
        if illegal:
            raise UserError(self.env._(
                'Historical FX evidence is recorded at approval. '
                'Client values were rejected: %(fields)s.',
                fields=', '.join(illegal),
            ))
        if vals.get('fx_multiplier_exact'):
            policy = vals.get('fx_policy')
            for version in self:
                selected = policy or version.fx_policy
                if selected != 'fixed_rate':
                    raise UserError(self.env._(
                        'A fixed exchange number is stored only on a fixed-rate clause. '
                        'No historical rate was invented.'
                    ))
        return super().write(vals)

    def create_amendment(self):
        new = super().create_amendment()
        new.write({
            'fx_policy': self.fx_policy,
            'fx_date_source': self.fx_date_source,
            'fx_explicit_date': self.fx_explicit_date,
            'fx_source_currency_id': self.fx_source_currency_id.id,
            'fx_target_currency_id': self.fx_target_currency_id.id,
            'fx_multiplier_exact': self.fx_multiplier_exact if self.fx_policy == 'fixed_rate' else False,
            'comparison_currency_policy': self.comparison_currency_policy,
            'comparison_currency_id': self.comparison_currency_id.id,
            'tax_basis': self.tax_basis,
            'tax_structure': self.tax_structure,
            'tax_percent_exact': self.tax_percent_exact,
            'rounding_stage': self.rounding_stage,
        })
        return new

    def _readiness_messages(self):
        messages = super()._readiness_messages()
        messages.extend(self._financial_readiness_messages())
        return messages

    def _financial_readiness_messages(self):
        self.ensure_one()
        messages = []
        if self.fx_policy == 'fixed_rate':
            multiplier = _decimal(self.fx_multiplier_exact)
            if multiplier is None or multiplier <= 0:
                messages.append(self.env._(
                    'The fixed exchange rate must be a positive exact number. No rate was invented.'
                ))
            if not self.fx_source_currency_id or not self.fx_target_currency_id:
                messages.append(self.env._(
                    'The fixed exchange rate needs both currencies in the pair.'
                ))
            elif not self.fx_source_currency_id.active or not self.fx_target_currency_id.active:
                messages.append(self.env._(
                    'An inactive currency is not activated for this fixed rate.'
                ))
        elif self.fx_policy in HISTORICAL_POLICIES:
            if self.fx_date_source == 'unconfigured':
                messages.append(self.env._(
                    'The historical FX clause has no date source. Invoice date was not selected automatically.'
                ))
            elif self.fx_date_source == 'explicit_date' and not self.fx_explicit_date:
                messages.append(self.env._('The explicit FX date is missing.'))
            if not self.fx_source_currency_id or not self.fx_target_currency_id:
                messages.append(self.env._(
                    'The historical FX clause needs both currencies in the pair.'
                ))
        if self.comparison_currency_policy == 'explicit_currency' and not self.comparison_currency_id:
            messages.append(self.env._('The explicit comparison currency is missing.'))
        if (
            self.tax_basis == 'tax_included'
            and self.tax_structure == 'single_ordinary_percent'
        ):
            percent = _decimal(self.tax_percent_exact)
            if percent is None or percent <= 0:
                messages.append(self.env._(
                    'The ordinary included tax percent must be a positive exact number. '
                    'No tax rate was invented.'
                ))
        if self.tax_basis == 'tax_included' and self.tax_structure in ('unconfigured', 'none'):
            messages.append(self.env._(
                'A tax-included price needs its tax structure. The price was not treated as tax-excluded.'
            ))
        return messages

    def _apply_approval(self):
        for version in self:
            version._snapshot_fx()
        return super()._apply_approval()

    def _snapshot_fx(self):
        """Freeze rate evidence once. Later edits of currency rates do not rewrite it."""
        self.ensure_one()
        empty = {
            'fx_policy_date': False,
            'fx_rate_date_used': False,
            'fx_rate_id': False,
            'fx_target_rate_id': False,
            'fx_company_per_source_exact': False,
            'fx_company_per_target_exact': False,
        }
        if self.fx_policy not in HISTORICAL_POLICIES:
            models.Model.write(self, empty)
            return
        on_date = self._fx_clause_date()
        if not on_date or not self.fx_source_currency_id or not self.fx_target_currency_id:
            models.Model.write(self, empty)
            return
        service = self.env['cpla.pricing.financial']
        mode = 'exact' if self.fx_policy == 'historical_exact_date' else 'prior'
        source = service.lookup_company_per_unit(
            self.company_id, self.fx_source_currency_id, on_date, mode, cutoff=None,
        )
        target = service.lookup_company_per_unit(
            self.company_id, self.fx_target_currency_id, on_date, mode, cutoff=None,
        )
        if not source.get('ok') or not target.get('ok'):
            models.Model.write(self, empty)
            return
        rate_dates = [day for day in (source.get('rate_date'), target.get('rate_date')) if day]
        models.Model.write(self, {
            'fx_policy_date': on_date,
            'fx_rate_date_used': max(rate_dates) if rate_dates else on_date,
            'fx_rate_id': source.get('rate_id') or False,
            'fx_target_rate_id': target.get('rate_id') or False,
            'fx_company_per_source_exact': source.get('company_per_unit_exact') or False,
            'fx_company_per_target_exact': target.get('company_per_unit_exact') or False,
        })

    def _fx_clause_date(self):
        self.ensure_one()
        if self.fx_date_source == 'explicit_date':
            return self.fx_explicit_date
        if self.fx_date_source == 'contract_effective_date':
            return self.effective_from
        return None

    def _financial_signature(self):
        self.ensure_one()
        return {
            'fx_policy': self.fx_policy,
            'fx_date_source': self.fx_date_source,
            'fx_explicit_date': fields.Date.to_string(self.fx_explicit_date) or '',
            'fx_source_currency_id': self.fx_source_currency_id.id or 0,
            'fx_target_currency_id': self.fx_target_currency_id.id or 0,
            'fx_multiplier_exact': self.fx_multiplier_exact or '',
            'fx_policy_date': fields.Date.to_string(self.fx_policy_date) or '',
            'fx_rate_date_used': fields.Date.to_string(self.fx_rate_date_used) or '',
            'fx_company_per_source_exact': self.fx_company_per_source_exact or '',
            'fx_company_per_target_exact': self.fx_company_per_target_exact or '',
            'comparison_currency_policy': self.comparison_currency_policy,
            'comparison_currency_id': self.comparison_currency_id.id or 0,
            'tax_basis': self.tax_basis,
            'tax_structure': self.tax_structure,
            'tax_percent_exact': self.tax_percent_exact or '',
            'rounding_stage': self.rounding_stage,
        }

    def _checksum(self, partner_name, covered_names):
        base = super()._checksum(partner_name, covered_names)
        payload = {
            'base': base,
            'financial_clause': self._financial_signature(),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def compare_with(self, other):
        result = super().compare_with(other)
        if self._financial_signature() != other._financial_signature():
            result['lines'].append(self._comparison_row(
                'Financial Clause Changed',
                'Currency, tax, or rounding clause',
                False,
                False,
                None,
                True,
            ))
        return result


class PricingApplicabilityCheckFinancial(models.TransientModel):
    _inherit = 'cpla.pricing.applicability.check'

    financial_status = fields.Char(string='Financial Status', readonly=True)
    financial_reason = fields.Char(string='Financial Reason', readonly=True)
    financial_explanation = fields.Text(string='Financial Explanation', readonly=True)
    comparable_unit_price_exact = fields.Char(string='Comparable Unit Price', readonly=True)
    comparable_currency_id = fields.Many2one('res.currency', string='Comparison Currency', readonly=True)
    fx_rate_exact = fields.Char(string='Applied FX Rate', readonly=True)
    fx_rate_direction = fields.Char(string='FX Direction', readonly=True)
    fx_date_used = fields.Char(string='FX Date Used', readonly=True)
    tax_basis_result = fields.Char(string='Tax Basis Result', readonly=True)
    rounding_stage_result = fields.Char(string='Rounding Stage Result', readonly=True)


class PricingFinancial(models.AbstractModel):
    """Read-only currency, tax-basis, and precision normalization.

    Company policy candidates are not read as rules. A missing rate, tax
    basis, or rounding choice stays in review. This service does not write
    contracts, invoices, taxes, or leakage findings.
    """

    _name = 'cpla.pricing.financial'
    _description = 'Contract Financial Price Normalization'

    @api.model
    def blank(self):
        return {
            'financial_status': 'not_applicable',
            'financial_reason': 'not_applicable',
            'financial_explanation': False,
            'comparable_unit_price_exact': False,
            'comparable_currency_id': False,
            'source_price_exact': False,
            'source_currency_id': False,
            'comparison_currency_id': False,
            'fx_policy': False,
            'fx_date_used': False,
            'fx_rate_exact': False,
            'fx_rate_direction': False,
            'fx_rate_id': False,
            'fx_evidence': False,
            'currency_status': False,
            'price_after_fx_exact': False,
            'tax_basis': False,
            'tax_status': False,
            'tax_structure': False,
            'normalized_tax_basis': False,
            'tax_component_exact': False,
            'rounding_stage': False,
            'rounding_applied': False,
            'extended_amount_exact': False,
            'extended_amount_rounded_exact': False,
            'precision_policy': 'exact_preserved',
            'policy_revision_id': False,
            'policy_version_snapshot': False,
            'historical_cutoff': False,
            'fx_reassessment_required': False,
            'discount_applied': False,
            'within_tolerance': False,
            'raw_difference_exact': False,
            'tolerance_suppressed': False,
            'calculation_trace': [],
            'leakage_amount': False,
            'is_recovered_cash': False,
        }

    @api.model
    def _result(self, status, reason, explanation, **extra):
        result = self.blank()
        result.update({
            'financial_status': status,
            'financial_reason': reason,
            'financial_explanation': explanation,
        })
        result.update(extra)
        result['leakage_amount'] = False
        result['is_recovered_cash'] = False
        result['discount_applied'] = False
        result['tolerance_suppressed'] = False
        result['within_tolerance'] = False
        return result

    @api.model
    def _check_caller(self):
        # Same technical-superuser rule as the applicability resolver.
        if self.env.su:
            return
        user = self.env.user
        if not any(user.has_group(group) for group in READ_GROUPS):
            raise AccessError(self.env._(
                'You are not allowed to normalize contract prices.'
            ))

    @api.model
    def normalize(self, line, request=None):
        """Return a comparable pre-discount unit price, or a review status.

        The line is re-read with the caller's rights. Caller rates, tax
        percents, tolerances, and prices are ignored.
        """
        self._check_caller()
        request = dict(request or {})
        for key in FORGED_REQUEST_KEYS:
            request.pop(key, None)
        if request.get('fx_source') == 'payment_date' or request.get('document_type') == 'payment':
            return self.classify_fx_source('payment_date')
        line = self.env[line._name].browse(line.ids)
        line.check_access('read')
        line = line.exists()
        if not line:
            raise AccessError(self.env._(
                'You are not allowed to normalize contract prices.'
            ))
        line.ensure_one()
        version = line.version_id
        if request.get('company_id') and request.get('company_id') != version.company_id.id:
            return self._result(
                'COMPANY_ACCESS_DENIED',
                'company_mismatch',
                self.env._(
                    'The company on the request does not match the contract version. '
                    'No price was returned.'
                ),
            )
        if version.company_id not in self.env.companies:
            raise AccessError(self.env._(
                'You are not allowed to normalize contract prices for this company.'
            ))
        cutoff = request.get('knowledge_cutoff')
        if cutoff and version.approved_at and self._as_datetime(cutoff) and version.approved_at > self._as_datetime(cutoff):
            return self._result(
                'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                'version_not_known_at_cutoff',
                self.env._(
                    'This approved version was not known at the historical cutoff. '
                    'Its FX clause was not applied.'
                ),
                historical_cutoff=str(cutoff),
            )
        if version.state != 'approved':
            return self._result(
                'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                'version_not_approved',
                self.env._(
                    'Only an approved version can supply a comparable price. '
                    'This draft clause was not applied.'
                ),
            )
        quantity = self.env['cpla.pricing.quantity'].evaluate(line, request)
        if quantity.get('status'):
            return self._result(
                'not_applicable',
                'quantity_not_normalized',
                self.env._(
                    'The unit price was not normalized because the quantity result is not authoritative.'
                ),
            )
        source_exact = quantity.get('normalized_unit_price_exact')
        if not source_exact and quantity.get('unit_price'):
            source_exact = _text(_decimal(quantity['unit_price']))
        source_amount = _decimal(source_exact)
        if source_amount is None or source_amount <= 0:
            return self._result(
                'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                'source_price_missing',
                self.env._('The approved unit price is missing. No comparable price was produced.'),
            )
        source_currency = line.currency_id
        target = self._comparison_currency(version)
        if target.get('error'):
            return target['error']
        target_currency = target['currency']
        if not source_currency or not source_currency.active or not target_currency.active:
            return self._result(
                'INVALID_CURRENCY_CONTEXT',
                'inactive_or_missing_currency',
                self.env._(
                    'The currency is missing or inactive. It was not activated, and no price was produced.'
                ),
            )
        tax = self._normalize_tax(source_amount, version, request)
        if tax.get('error'):
            return tax['error']
        net_amount = tax['net']
        converted = self._convert_clause(net_amount, source_currency, target_currency, version, request)
        if converted.get('error'):
            return converted['error']
        rounded = self._apply_rounding(
            converted['amount'], target_currency, version, request,
        )
        if rounded.get('error'):
            return rounded['error']
        trace = [
            'Source unit %s %s.' % (_text(source_amount), source_currency.name),
            tax['trace'],
            converted['trace'],
            rounded['trace'],
            'Pre-discount comparable unit %s %s.' % (
                rounded['unit_exact'], target_currency.name,
            ),
            'No authorized discount was applied.',
            'Company FX, tax, and tolerance candidates were not applied.',
        ]
        status = converted['status']
        return self._result(
            status,
            converted['reason'],
            self.env._(
                'The comparable unit price is the pre-discount amount in the comparison currency and tax basis. '
                'It is not an invoice audit and it is not a leakage amount.'
            ),
            comparable_unit_price_exact=rounded['unit_exact'],
            comparable_currency_id=target_currency.id,
            source_price_exact=_text(source_amount),
            source_currency_id=source_currency.id,
            comparison_currency_id=target_currency.id,
            fx_policy=version.fx_policy,
            fx_date_used=converted.get('fx_date_used') or False,
            fx_rate_exact=converted.get('fx_rate_exact') or False,
            fx_rate_direction=converted.get('fx_rate_direction') or False,
            fx_rate_id=converted.get('fx_rate_id') or False,
            fx_evidence=converted.get('fx_evidence') or False,
            currency_status=converted['status'],
            price_after_fx_exact=converted.get('price_after_fx_exact') or False,
            tax_basis=version.tax_basis,
            tax_status=tax['status'],
            tax_structure=version.tax_structure,
            normalized_tax_basis='tax_excluded',
            tax_component_exact=tax['tax_exact'],
            rounding_stage=rounded['stage'],
            rounding_applied=rounded['applied'],
            extended_amount_exact=rounded.get('extended_exact') or False,
            extended_amount_rounded_exact=rounded.get('extended_rounded_exact') or False,
            precision_policy=rounded['precision_policy'],
            policy_revision_id=version.policy_id.id or False,
            policy_version_snapshot=version.policy_version_snapshot or False,
            historical_cutoff=str(cutoff or '') or False,
            fx_reassessment_required=converted.get('fx_reassessment_required') or False,
            calculation_trace=trace,
        )

    @api.model
    def _comparison_currency(self, version):
        policy = version.comparison_currency_policy
        if policy == 'contract_currency':
            currency = version.currency_id
        elif policy == 'company_currency':
            currency = version.company_id.currency_id
        elif policy == 'explicit_currency':
            currency = version.comparison_currency_id
        else:
            return {
                'error': self._result(
                    'INVALID_CURRENCY_CONTEXT',
                    'comparison_currency_unconfigured',
                    self.env._(
                        'The comparison currency is not set on the approved version. '
                        'Company currency was not assumed.'
                    ),
                ),
            }
        if not currency:
            return {
                'error': self._result(
                    'INVALID_CURRENCY_CONTEXT',
                    'comparison_currency_missing',
                    self.env._('The comparison currency record is missing. No price was produced.'),
                ),
            }
        return {'currency': currency, 'error': None}

    @api.model
    def _normalize_tax(self, amount, version, request):
        if request.get('fiscal_position_id'):
            return {
                'error': self._result(
                    'TAX_BASIS_REVIEW_REQUIRED',
                    'fiscal_position_not_verified',
                    self.env._(
                        'A fiscal position was supplied. Product taxes were not mapped, '
                        'and no net price was guessed. Invoice tax context belongs to a later phase.'
                    ),
                ),
            }
        structure = version.tax_structure
        if structure in COMPLEX_TAX_STRUCTURES:
            return {
                'error': self._result(
                    'UNSUPPORTED_TAX_STRUCTURE',
                    'unsupported_tax_structure',
                    self.env._(
                        'This tax structure is not a single ordinary percentage. '
                        'The price was not divided by one plus a rate.'
                    ),
                    tax_structure=structure,
                    tax_status='UNSUPPORTED_TAX_STRUCTURE',
                ),
            }
        if version.tax_basis == 'unconfigured' or structure == 'unconfigured':
            return {
                'error': self._result(
                    'TAX_BASIS_REVIEW_REQUIRED',
                    'tax_basis_unconfigured',
                    self.env._(
                        'The contract tax basis is not set. '
                        'Tax-included and tax-excluded amounts were not compared.'
                    ),
                ),
            }
        if version.tax_basis == 'tax_excluded':
            return {
                'error': None,
                'net': amount,
                'tax_exact': '0',
                'status': 'TAX_EXCLUDED',
                'trace': 'Tax basis is tax excluded. The tax amount is not part of the unit price.',
            }
        if version.tax_basis == 'tax_included' and structure == 'single_ordinary_percent':
            percent = _decimal(version.tax_percent_exact)
            if percent is None or percent <= 0:
                return {
                    'error': self._result(
                        'TAX_BASIS_REVIEW_REQUIRED',
                        'tax_percent_missing',
                        self.env._(
                            'The ordinary included tax percent is missing. No percent was invented.'
                        ),
                    ),
                }
            net = _arithmetic('div', amount * Decimal(100), Decimal(100) + percent)
            tax_amount = _arithmetic('sub', amount, net)
            return {
                'error': None,
                'net': net,
                'tax_exact': _text(tax_amount),
                'status': 'TAX_INCLUDED_SIMPLE',
                'trace': 'One ordinary included percent %s was removed. The tax amount is not lost revenue.' % _text(percent),
            }
        return {
            'error': self._result(
                'UNSUPPORTED_TAX_STRUCTURE',
                'unsupported_tax_structure',
                self.env._(
                    'The tax structure is not supported for a comparable net price. No net price was guessed.'
                ),
                tax_structure=structure,
            ),
        }

    @api.model
    def _convert_clause(self, amount, source_currency, target_currency, version, request):
        if source_currency == target_currency:
            return {
                'error': None,
                'amount': amount,
                'status': 'SAME_CURRENCY_NO_CONVERSION',
                'reason': 'same_currency',
                'fx_rate_exact': False,
                'fx_rate_direction': 'none',
                'fx_date_used': False,
                'fx_rate_id': False,
                'fx_evidence': 'same_currency',
                'price_after_fx_exact': _text(amount),
                'fx_reassessment_required': False,
                'trace': 'Source and comparison currencies match. No exchange rate was required.',
            }
        if version.fx_policy == 'unconfigured':
            return {
                'error': self._result(
                    'FX_RATE_REVIEW_REQUIRED',
                    'fx_policy_unconfigured',
                    self.env._(
                        'The currencies differ and the approved version has no FX clause. '
                        'Today\'s rate was not used.'
                    ),
                ),
            }
        if version.fx_policy == 'fixed_rate':
            return self._convert_fixed(amount, source_currency, target_currency, version)
        if version.fx_policy in HISTORICAL_POLICIES:
            return self._convert_historical(amount, source_currency, target_currency, version)
        return {
            'error': self._result(
                'FX_RATE_REVIEW_REQUIRED',
                'fx_policy_unconfigured',
                self.env._('The FX clause is not an approved conversion. No rate was used.'),
            ),
        }

    @api.model
    def _convert_fixed(self, amount, source_currency, target_currency, version):
        multiplier = _decimal(version.fx_multiplier_exact)
        pair_source = version.fx_source_currency_id
        pair_target = version.fx_target_currency_id
        if multiplier is None or multiplier <= 0 or not pair_source or not pair_target:
            return {
                'error': self._result(
                    'MISSING_HISTORICAL_FX',
                    'fixed_rate_missing',
                    self.env._(
                        'The fixed exchange rate is missing. The market rate was not substituted.'
                    ),
                ),
            }
        if source_currency == pair_source and target_currency == pair_target:
            converted = _arithmetic('mul', amount, multiplier)
            direction = 'multiply'
            rate_exact = _text(multiplier)
        elif source_currency == pair_target and target_currency == pair_source:
            converted = _arithmetic('div', amount, multiplier)
            direction = 'divide'
            rate_exact = _text(multiplier)
        else:
            return {
                'error': self._result(
                    'FX_RATE_REVIEW_REQUIRED',
                    'fixed_pair_mismatch',
                    self.env._(
                        'The fixed rate is for a different currency pair. It was not applied.'
                    ),
                ),
            }
        return {
            'error': None,
            'amount': converted,
            'status': 'NORMALIZED',
            'reason': 'fixed_contract_rate',
            'fx_rate_exact': rate_exact,
            'fx_rate_direction': direction,
            'fx_date_used': False,
            'fx_rate_id': False,
            'fx_evidence': 'contract_fixed_rate',
            'price_after_fx_exact': _text(converted),
            'fx_reassessment_required': False,
            'trace': 'Fixed contract rate %s was applied by %s. A different market rate was not used.' % (
                rate_exact, direction,
            ),
        }

    @api.model
    def _convert_historical(self, amount, source_currency, target_currency, version):
        if version.fx_date_source in DOCUMENT_DATE_SOURCES and not version.fx_company_per_source_exact:
            return {
                'error': self._result(
                    'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                    'document_date_not_snapshotted',
                    self.env._(
                        'This FX date comes from a document that is not on the approved snapshot. '
                        'A live rate was not used.'
                    ),
                    fx_policy=version.fx_policy,
                ),
            }
        per_source = _decimal(version.fx_company_per_source_exact)
        per_target = _decimal(version.fx_company_per_target_exact)
        pair_source = version.fx_source_currency_id
        pair_target = version.fx_target_currency_id
        if per_source is None or per_target is None or per_source <= 0 or per_target <= 0:
            return {
                'error': self._result(
                    'MISSING_HISTORICAL_FX',
                    'missing_historical_fx',
                    self.env._(
                        'No frozen historical rate is available for this clause. '
                        'No rate was invented and today\'s rate was not used.'
                    ),
                    fx_policy=version.fx_policy,
                    fx_date_used=fields.Date.to_string(version.fx_policy_date) if version.fx_policy_date else False,
                ),
            }
        if not self._pair_matches(source_currency, target_currency, pair_source, pair_target):
            return {
                'error': self._result(
                    'FX_RATE_REVIEW_REQUIRED',
                    'historical_pair_mismatch',
                    self.env._(
                        'The frozen rate is for a different currency pair. Another company rate was not used.'
                    ),
                ),
            }
        if source_currency == pair_source and target_currency == pair_target:
            converted = _arithmetic('div', _arithmetic('mul', amount, per_source), per_target)
            direction = 'company_triangulation'
        else:
            converted = _arithmetic('div', _arithmetic('mul', amount, per_target), per_source)
            direction = 'inverse_company_triangulation'
        mode = 'exact' if version.fx_policy == 'historical_exact_date' else 'prior'
        live_source = self.lookup_company_per_unit(
            version.company_id, pair_source, version.fx_policy_date, mode, cutoff=None,
        )
        live_target = self.lookup_company_per_unit(
            version.company_id, pair_target, version.fx_policy_date, mode, cutoff=None,
        )
        differs = (
            not live_source.get('ok')
            or not live_target.get('ok')
            or live_source.get('company_per_unit_exact') != version.fx_company_per_source_exact
            or live_target.get('company_per_unit_exact') != version.fx_company_per_target_exact
        )
        rate_exact = _text(per_source) if direction == 'company_triangulation' else _text(per_target)
        return {
            'error': None,
            'amount': converted,
            'status': 'NORMALIZED',
            'reason': 'frozen_historical_rate',
            'fx_rate_exact': rate_exact,
            'fx_rate_direction': direction,
            'fx_date_used': fields.Date.to_string(version.fx_rate_date_used) if version.fx_rate_date_used else False,
            'fx_rate_id': version.fx_rate_id.id or False,
            'fx_evidence': 'frozen_rate_snapshot',
            'price_after_fx_exact': _text(converted),
            'fx_reassessment_required': bool(differs),
            'trace': 'Frozen historical rate evidence was applied. A later rate correction was not substituted.',
        }

    @api.model
    def _pair_matches(self, source_currency, target_currency, pair_source, pair_target):
        return (
            (source_currency == pair_source and target_currency == pair_target)
            or (source_currency == pair_target and target_currency == pair_source)
        )

    @api.model
    def _apply_rounding(self, amount, currency, version, request):
        stage = version.rounding_stage
        if stage in ('unconfigured', 'preserve_exact'):
            extended = self._extended(amount, request)
            return {
                'error': None,
                'unit_exact': _text(amount),
                'stage': 'preserve_exact',
                'applied': False,
                'extended_exact': extended,
                'extended_rounded_exact': False,
                'precision_policy': 'exact_preserved',
                'trace': 'Exact decimals were preserved. Currency rounding was not applied early.',
            }
        increment = _decimal(currency.rounding)
        if increment is None or increment <= 0:
            return {
                'error': self._result(
                    'PRECISION_POLICY_REVIEW_REQUIRED',
                    'invalid_rounding_increment',
                    self.env._(
                        'The comparison currency has no positive rounding increment. '
                        'Two decimal places were not assumed.'
                    ),
                ),
            }
        if stage == 'per_unit':
            rounded_unit = self._round_to_increment(amount, increment)
            if rounded_unit is None:
                return {
                    'error': self._result(
                        'PRECISION_POLICY_REVIEW_REQUIRED',
                        'invalid_rounding_increment',
                        self.env._('The unit amount could not be rounded with the currency increment.'),
                    ),
                }
            return {
                'error': None,
                'unit_exact': _text(rounded_unit),
                'stage': 'per_unit',
                'applied': True,
                'extended_exact': self._extended(amount, request),
                'extended_rounded_exact': self._extended(rounded_unit, request),
                'precision_policy': 'currency_rounding_per_unit',
                'trace': 'The comparable unit was rounded with the comparison currency increment %s.' % _text(increment),
            }
        if stage == 'extended_amount':
            extended = self._extended(amount, request)
            if extended is False:
                return {
                    'error': None,
                    'unit_exact': _text(amount),
                    'stage': 'extended_amount',
                    'applied': False,
                    'extended_exact': False,
                    'extended_rounded_exact': False,
                    'precision_policy': 'extended_amount_quantity_missing',
                    'trace': 'The unit stayed exact because the extended quantity was not supplied.',
                }
            rounded_extended = self._round_to_increment(_decimal(extended), increment)
            return {
                'error': None,
                'unit_exact': _text(amount),
                'stage': 'extended_amount',
                'applied': True,
                'extended_exact': extended,
                'extended_rounded_exact': _text(rounded_extended),
                'precision_policy': 'currency_rounding_extended_amount',
                'trace': 'The extended amount was rounded. The unit price was not rounded first.',
            }
        return {
            'error': self._result(
                'PRECISION_POLICY_REVIEW_REQUIRED',
                'rounding_stage_unknown',
                self.env._('The rounding stage is not an approved clause.'),
            ),
        }

    @api.model
    def _extended(self, unit_amount, request):
        quantity = _decimal(request.get('extended_quantity'))
        if quantity is None:
            quantity = _decimal(request.get('quantity'))
        if quantity is None:
            return False
        return _text(_arithmetic('mul', unit_amount, quantity))

    @api.model
    def _round_to_increment(self, amount, increment):
        amount = _decimal(amount)
        increment = _decimal(increment)
        if amount is None or increment is None or increment <= 0:
            return None
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_UP
            units = (amount / increment).quantize(Decimal('1'))
            return units * increment

    @api.model
    def lookup_company_per_unit(self, company, currency, on_date, mode, cutoff=None):
        """Company-currency units for one unit of ``currency``.

        Native currency conversion is not used. Its date lookup can select a
        future rate and then the number one when no row exists.
        """
        if not company or not currency or not on_date or mode not in ('exact', 'prior'):
            return {'ok': False, 'reason': 'invalid_currency_context'}
        if not currency.active:
            return {'ok': False, 'reason': 'inactive_currency'}
        if currency == company.currency_id:
            anchor = self._table_rate(company, currency, on_date, mode, cutoff)
            if anchor.get('ok') and not self._is_one(anchor.get('table_rate')):
                return {'ok': False, 'reason': 'company_currency_rate_not_identity'}
            if not anchor.get('ok') and not anchor.get('missing'):
                return anchor
            return {
                'ok': True,
                'company_per_unit_exact': '1',
                'rate_id': False,
                'rate_date': on_date,
                'reason': 'company_currency_identity',
            }
        foreign = self._table_rate(company, currency, on_date, mode, cutoff)
        if not foreign.get('ok'):
            return foreign
        anchor = self._table_rate(company, company.currency_id, on_date, mode, cutoff)
        if anchor.get('ok') and not self._is_one(anchor.get('table_rate')):
            return {'ok': False, 'reason': 'company_currency_rate_not_identity'}
        if not anchor.get('ok') and not anchor.get('missing'):
            return anchor
        foreign_table = float(foreign['table_rate'])
        if not foreign_table:
            return {'ok': False, 'reason': 'missing_historical_fx'}
        per_unit = _decimal(str(1.0 / foreign_table))
        if per_unit is None or per_unit <= 0:
            return {'ok': False, 'reason': 'missing_historical_fx'}
        return {
            'ok': True,
            'company_per_unit_exact': _text(per_unit),
            'rate_id': foreign.get('rate_id') or False,
            'rate_date': foreign.get('rate_date'),
            'reason': 'historical_row',
        }

    @api.model
    def _table_rate(self, company, currency, on_date, mode, cutoff):
        root = company.root_id
        specific = self._best_rate_row(currency, root.id, on_date, mode, cutoff)
        shared = self._best_rate_row(currency, False, on_date, mode, cutoff)
        if specific.get('reason') == 'rate_corrected_after_cutoff' or shared.get('reason') == 'rate_corrected_after_cutoff':
            return {'ok': False, 'reason': 'rate_corrected_after_cutoff'}
        chosen = self._prefer_rate(specific, shared)
        if not chosen:
            if currency == company.currency_id:
                return {'ok': False, 'missing': True, 'reason': 'company_currency_identity'}
            return {'ok': False, 'reason': 'missing_historical_fx'}
        return {
            'ok': True,
            'table_rate': chosen.rate,
            'use_float_inverse': True,
            'rate_id': chosen.id,
            'rate_date': chosen.name,
            'rate_company_id': chosen.company_id.id or False,
        }

    @api.model
    def _prefer_rate(self, specific, shared):
        rows = []
        if specific.get('row'):
            rows.append(specific['row'])
        if shared.get('row'):
            rows.append(shared['row'])
        if not rows:
            return None
        rows.sort(key=lambda row: (row.name, bool(row.company_id)))
        return rows[-1]

    @api.model
    def _best_rate_row(self, currency, company_id, on_date, mode, cutoff):
        domain = [
            ('currency_id', '=', currency.id),
            ('rate', '>', 0),
            ('company_id', '=', company_id),
        ]
        if mode == 'exact':
            domain.append(('name', '=', on_date))
        else:
            domain.append(('name', '<=', on_date))
        rows = self.env['res.currency.rate'].search(domain, order='name desc, id desc', limit=50)
        if len(rows) >= 50 and mode == 'prior':
            older = rows[-1]
            more = self.env['res.currency.rate'].search_count(domain + [('name', '<', older.name)])
            if more and cutoff:
                return {'ok': False, 'reason': 'rate_history_not_bounded', 'row': None}
        cutoff_dt = self._as_datetime(cutoff) if cutoff else None
        for row in rows:
            if row.name and on_date and row.name > on_date:
                continue
            if cutoff_dt and row.create_date and row.create_date > cutoff_dt:
                continue
            if (
                cutoff_dt
                and row.write_date
                and row.create_date
                and row.write_date > cutoff_dt
                and row.write_date > row.create_date
            ):
                return {'ok': False, 'reason': 'rate_corrected_after_cutoff', 'row': None}
            return {'ok': True, 'row': row}
        return {'ok': False, 'reason': 'missing_historical_fx', 'row': None}

    @api.model
    def select_rate(self, company, currency, on_date, mode='exact', cutoff=None):
        """Read-only rate selection for one company. It does not create a rate."""
        self._check_caller()
        company = self.env['res.company'].browse(company.id if hasattr(company, 'id') else company).exists()
        currency = self.env['res.currency'].browse(currency.id if hasattr(currency, 'id') else currency).exists()
        if not company or company not in self.env.companies:
            raise AccessError(self.env._(
                'You are not allowed to read exchange rates for this company.'
            ))
        found = self.lookup_company_per_unit(company, currency, on_date, mode, cutoff=cutoff)
        if not found.get('ok'):
            return {
                'ok': False,
                'status': 'HISTORICAL_EVIDENCE_REVIEW_REQUIRED' if found.get('reason') == 'rate_corrected_after_cutoff' else 'MISSING_HISTORICAL_FX',
                'reason': found.get('reason') or 'missing_historical_fx',
                'rate_id': False,
                'rate_date': False,
                'company_per_unit_exact': False,
                'leakage_amount': False,
            }
        return {
            'ok': True,
            'status': 'RATE_SELECTED',
            'reason': found.get('reason'),
            'rate_id': found.get('rate_id') or False,
            'rate_date': fields.Date.to_string(found.get('rate_date')) if found.get('rate_date') else False,
            'company_per_unit_exact': found.get('company_per_unit_exact'),
            'leakage_amount': False,
        }

    @api.model
    def classify_fx_source(self, source):
        self._check_caller()
        if source == 'payment_date':
            return self._result(
                'PAYMENT_FX_NOT_CONTRACT_LEAKAGE',
                'payment_fx_not_contract_leakage',
                self.env._(
                    'A payment-date exchange gain or loss is not contract price leakage.'
                ),
                currency_status='PAYMENT_FX_NOT_CONTRACT_LEAKAGE',
            )
        return self._result(
            'FX_RATE_REVIEW_REQUIRED',
            'fx_source_not_a_price',
            self.env._('This exchange source is not a contract price conversion.'),
        )

    @api.model
    def classify_difference(self, expected_exact, actual_exact, quantity=None, tolerance_amount=None):
        """Signed expected-minus-actual difference. Nothing is suppressed."""
        self._check_caller()
        if tolerance_amount not in (None, False, ''):
            tolerance = _decimal(tolerance_amount)
            if tolerance is None or tolerance < 0:
                raise ValidationError(self.env._(
                    'A negative or invalid tolerance is rejected. No difference was suppressed.'
                ))
        expected = _decimal(expected_exact)
        actual = _decimal(actual_exact)
        if expected is None or actual is None:
            return self._result(
                'PRECISION_POLICY_REVIEW_REQUIRED',
                'invalid_difference',
                self.env._('The difference needs two finite amounts. No tolerance was applied.'),
            )
        signed = _arithmetic('sub', expected, actual)
        extended = False
        qty = _decimal(quantity)
        if qty is not None:
            extended = _text(_arithmetic('mul', signed, qty))
        return self._result(
            'DIFFERENCE_RECORDED',
            'tolerance_not_approved',
            self.env._(
                'No numeric tolerance is approved. The signed difference was kept. '
                'A negative difference was not turned into positive leakage.'
            ),
            raw_difference_exact=_text(signed),
            extended_amount_exact=extended,
            within_tolerance=False,
            tolerance_suppressed=False,
            precision_policy='raw_difference_preserved',
        )

    @api.model
    def _is_one(self, value):
        number = _decimal(str(value))
        if number is None:
            return False
        return number == 1

    def _as_datetime(self, value):
        if not value:
            return None
        if hasattr(value, 'hour'):
            return value
        try:
            return fields.Datetime.to_datetime(value)
        except (TypeError, ValueError):
            return None
