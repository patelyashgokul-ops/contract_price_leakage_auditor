from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

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

STATUSES = (
    'MATCHED_AUTHORITATIVE',
    'NO_APPLICABLE_CONTRACT',
    'CONFLICT_REVIEW_REQUIRED',
    'MISSING_CONTEXT',
    'POLICY_REVIEW_REQUIRED',
    'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
    'PARTITION_REVIEW_REQUIRED',
)

BASIS = ('order_confirmation', 'delivery', 'invoice', 'explicit_date')


class PricingApplicability(models.AbstractModel):
    """Read-only selection of one approved contract version.

    A stored policy candidate is not an operational rule. Exact customer and
    exact variant matches can be selected. Branch, group, template, and
    price-based choices are not invented.
    """

    _name = 'cpla.pricing.applicability'
    _description = 'Contract Applicability Resolver'

    @api.model
    def cache_key(self, request):
        """Identity of a request. Results are not stored under this key."""
        request = request or {}
        delivery = request.get('delivery_dates') or []
        return (
            request.get('company_id') or False,
            request.get('partner_id') or False,
            request.get('product_id') or False,
            str(request.get('pricing_date') or ''),
            request.get('basis') or '',
            str(request.get('order_confirmation_date') or ''),
            bool(request.get('order_confirmed')),
            str(request.get('invoice_date') or ''),
            tuple(str(item) for item in delivery),
            str(request.get('knowledge_cutoff') or ''),
            request.get('uom_id') or False,
            request.get('customer_group_ref') or '',
            bool(request.get('template_fallback_requested')),
            str(request.get('quantity') if request.get('quantity') is not None else ''),
            str(request.get('order_quantity') if request.get('order_quantity') is not None else ''),
            str(request.get('invoice_quantity') if request.get('invoice_quantity') is not None else ''),
            str(request.get('delivery_quantity') if request.get('delivery_quantity') is not None else ''),
            request.get('comparison_uom_id') or False,
            request.get('quantity_uom_id') or False,
        )

    @api.model
    def resolve(self, request):
        """Return a plain result. This method does not write business records."""
        self._check_caller()
        request = dict(request or {})
        for forged in (
            'version_id', 'contract_id', 'unit_price', 'tier_id',
            'normalized_unit_price', 'contract_unit_price',
        ):
            request.pop(forged, None)
        company = self._require_company(request)
        if isinstance(company, dict):
            return company
        partner = self._require_partner(request, company)
        if isinstance(partner, dict):
            return partner
        product = self._require_product(request, company)
        if isinstance(product, dict):
            return product
        dated = self._pricing_context(request)
        if dated.get('status'):
            return dated
        pricing_date = dated['pricing_date']
        versions = self._candidate_versions(company, partner, product, pricing_date, request)
        if isinstance(versions, dict):
            return versions
        selected, reason = self._select_versions(versions, pricing_date)
        if reason == 'equal_authority_conflict':
            return self._outcome(
                'CONFLICT_REVIEW_REQUIRED',
                reason,
                self._conflict_text(selected),
                request,
                dated,
                conflicting=selected,
            )
        if reason in (
            'chronology_conflict',
            'circular_supersession',
            'cross_contract_supersession',
        ):
            return self._outcome(
                'CONFLICT_REVIEW_REQUIRED',
                reason,
                self.env._(
                    'The approved version chronology is ambiguous. No price was selected.'
                ),
                request,
                dated,
            )
        if reason == 'supersession_evidence_missing':
            return self._outcome(
                'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                reason,
                self.env._(
                    'A later approved version has no supersession evidence. No price was selected.'
                ),
                request,
                dated,
            )
        if reason == 'approval_evidence_missing':
            return self._outcome(
                'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                reason,
                self.env._(
                    'An approved version has no approval timestamp. No price was selected.'
                ),
                request,
                dated,
            )
        if not selected:
            if request.get('customer_group_ref'):
                return self._outcome(
                    'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                    'customer_group_not_approved',
                    self.env._(
                        'Customer-group coverage has no approved historical membership. '
                        'The current partner hierarchy was not used. No price was selected.'
                    ),
                    request,
                    dated,
                )
            if request.get('template_fallback_requested') and self._template_sibling_exists(
                company, partner, product, pricing_date,
            ):
                return self._outcome(
                    'POLICY_REVIEW_REQUIRED',
                    'product_template_scope_not_represented',
                    self.env._(
                        'A sibling variant has an approved price. Product-template scope is not '
                        'an approved contract term, so that price was not applied.'
                    ),
                    request,
                    dated,
                )
            return self._outcome(
                'NO_APPLICABLE_CONTRACT',
                'no_eligible_contract',
                self.env._(
                    'No approved contract version covers this company, customer, product, and pricing date.'
                ),
                request,
                dated,
            )
        line = self._select_line(selected, product, request, dated)
        if isinstance(line, dict):
            return line
        return self._matched(selected, line, request, dated, partner, product)

    @api.model
    def _check_caller(self):
        # Odoo 19 does not put the technical superuser in business groups.
        # Superuser already bypasses record rules, so a system confirmation
        # can still read the approved price. A normal user cannot set this.
        if self.env.su:
            return
        user = self.env.user
        if not any(user.has_group(group) for group in READ_GROUPS):
            raise AccessError(self.env._(
                'You are not allowed to resolve contract applicability.'
            ))

    @api.model
    def _require_company(self, request):
        company_id = request.get('company_id')
        if not company_id:
            return self._outcome(
                'MISSING_CONTEXT',
                'company_missing',
                self.env._('The company is required. No pricing date was assumed.'),
                request,
            )
        company = self.env['res.company'].browse(company_id).exists()
        if not company or company not in self.env.companies:
            raise AccessError(self.env._(
                'You are not allowed to resolve contracts for this company.'
            ))
        return company

    @api.model
    def _require_partner(self, request, company):
        partner_id = request.get('partner_id')
        if not partner_id:
            return self._outcome(
                'MISSING_CONTEXT',
                'customer_missing',
                self.env._('The customer is required. No pricing date was assumed.'),
                request,
            )
        partner = self.env['res.partner'].with_context(active_test=False).browse(partner_id).exists()
        if not partner:
            raise AccessError(self.env._(
                'You are not allowed to use this customer.'
            ))
        if partner.company_id and partner.company_id != company:
            raise UserError(self.env._(
                'The customer is not available for this company. No price was selected.'
            ))
        return partner

    @api.model
    def _require_product(self, request, company):
        product_id = request.get('product_id')
        if not product_id:
            if request.get('category_id'):
                return self._outcome(
                    'POLICY_REVIEW_REQUIRED',
                    'product_category_not_supported',
                    self.env._(
                        'Product-category pricing is not an approved contract scope. No price was selected.'
                    ),
                    request,
                )
            return self._outcome(
                'MISSING_CONTEXT',
                'product_missing',
                self.env._('The product variant is required. No pricing date was assumed.'),
                request,
            )
        product = self.env['product.product'].with_context(active_test=False).browse(product_id).exists()
        if not product:
            raise AccessError(self.env._(
                'You are not allowed to use this product.'
            ))
        if product.company_id and product.company_id != company:
            raise UserError(self.env._(
                'The product is not available for this company. No price was selected.'
            ))
        return product

    @api.model
    def _pricing_context(self, request):
        explicit = self._as_date(request.get('pricing_date'))
        if request.get('pricing_date') and explicit is None:
            return self._outcome(
                'MISSING_CONTEXT',
                'pricing_date_missing',
                self.env._('The pricing date is not a valid calendar date.'),
                request,
            )
        basis = request.get('basis') or False
        if basis and basis not in BASIS:
            return self._outcome(
                'MISSING_CONTEXT',
                'pricing_date_missing',
                self.env._('The requested pricing-date basis is not recognized.'),
                request,
            )
        if explicit:
            return {
                'pricing_date': explicit,
                'pricing_date_rule': 'explicit_date',
                'basis_source': 'explicit_date',
                'grandfathering_applied': False,
            }
        if not basis:
            return self._outcome(
                'POLICY_REVIEW_REQUIRED',
                'pricing_date_policy_not_approved',
                self.env._(
                    'No explicit pricing date was supplied. The stored pricing-date candidate '
                    'is not operationally approved, so today was not used and no price was selected.'
                ),
                request,
            )
        if basis == 'order_confirmation':
            if request.get('grandfather_limit'):
                return self._outcome(
                    'POLICY_REVIEW_REQUIRED',
                    'grandfather_limit_not_approved',
                    self.env._(
                        'A grandfathering time limit was supplied. No approved limit exists, '
                        'so no price was selected.'
                    ),
                    request,
                )
            if not request.get('order_confirmed'):
                return self._outcome(
                    'MISSING_CONTEXT',
                    'order_not_confirmed',
                    self.env._(
                        'Sales-order pricing needs a confirmed order. A quotation date was not used.'
                    ),
                    request,
                )
            confirmed = self._as_date(request.get('order_confirmation_date'))
            if not confirmed:
                return self._outcome(
                    'MISSING_CONTEXT',
                    'pricing_date_missing',
                    self.env._(
                        'The confirmed sales-order date is missing. The quotation date was not used.'
                    ),
                    request,
                )
            return {
                'pricing_date': confirmed,
                'pricing_date_rule': 'order_confirmation',
                'basis_source': 'request',
                'grandfathering_applied': False,
            }
        if basis == 'delivery':
            dates = []
            for value in request.get('delivery_dates') or []:
                parsed = self._as_date(value)
                if parsed is None:
                    return self._outcome(
                        'MISSING_CONTEXT',
                        'delivery_missing',
                        self.env._('A delivery date is not a valid calendar date.'),
                        request,
                    )
                dates.append(parsed)
            unique = sorted(set(dates))
            if not unique:
                return self._outcome(
                    'MISSING_CONTEXT',
                    'delivery_missing',
                    self.env._(
                        'Delivery-date pricing needs a delivery date. No date was assumed.'
                    ),
                    request,
                )
            if len(unique) > 1:
                return self._outcome(
                    'PARTITION_REVIEW_REQUIRED',
                    'delivery_allocation_required',
                    self.env._(
                        'More than one delivery date was supplied. One version was not applied '
                        'to the combined quantity. Quantity partitioning belongs to a later phase.'
                    ),
                    request,
                )
            return {
                'pricing_date': unique[0],
                'pricing_date_rule': 'delivery',
                'basis_source': 'request',
                'grandfathering_applied': False,
            }
        invoice = self._as_date(request.get('invoice_date'))
        if not invoice:
            return self._outcome(
                'MISSING_CONTEXT',
                'invoice_date_missing',
                self.env._(
                    'Invoice-date pricing needs an invoice date. A posting timestamp was not used.'
                ),
                request,
            )
        return {
            'pricing_date': invoice,
            'pricing_date_rule': 'invoice',
            'basis_source': 'request',
            'grandfathering_applied': False,
        }

    @api.model
    def _candidate_versions(self, company, partner, product, pricing_date, request):
        lines = self.env['cpla.customer.contract.version.line'].search([
            ('company_id', '=', company.id),
            ('product_id', '=', product.id),
            ('version_id.company_id', '=', company.id),
            ('version_id.state', '=', 'approved'),
            ('version_id.partner_id', '=', partner.id),
            ('version_id.effective_from', '<=', pricing_date),
            ('version_id.valid_from', '<=', pricing_date),
            ('version_id.valid_to', '>=', pricing_date),
        ])
        cutoff = self._as_datetime(request.get('knowledge_cutoff'))
        if request.get('knowledge_cutoff') and cutoff is None:
            return self._outcome(
                'MISSING_CONTEXT',
                'pricing_date_missing',
                self.env._('The historical evaluation cutoff is not a valid timestamp.'),
                request,
            )
        versions = self.env['cpla.customer.contract.version']
        for line in lines:
            version = line.version_id
            if version.company_id != company or version.partner_id != partner:
                continue
            if not version.approved_at:
                return self._outcome(
                    'HISTORICAL_EVIDENCE_REVIEW_REQUIRED',
                    'approval_evidence_missing',
                    self.env._(
                        'An approved version has no approval timestamp. No price was selected.'
                    ),
                    request,
                )
            if cutoff and version.approved_at > cutoff:
                continue
            if self._retroactive_blocked(version):
                continue
            versions |= version
        return versions

    @api.model
    def _retroactive_blocked(self, version):
        if not version.source_version_id or not version.approved_at or not version.effective_from:
            return False
        if version.retroactivity_policy != 'not_authorized':
            return False
        return version.effective_from < fields.Date.to_date(version.approved_at)

    @api.model
    def _select_versions(self, versions, pricing_date):
        if not versions:
            return versions, 'no_eligible_contract'
        chosen = self.env['cpla.customer.contract.version']
        by_contract = {}
        for version in versions:
            by_contract.setdefault(version.contract_id.id, self.env['cpla.customer.contract.version'])
            by_contract[version.contract_id.id] |= version
        for contract_versions in by_contract.values():
            issue = self._chronology_issue(contract_versions)
            if issue:
                return contract_versions, issue
            match = self._version_on(contract_versions, pricing_date)
            if match:
                chosen |= match
        if len(chosen) > 1:
            return chosen, 'equal_authority_conflict'
        if len(chosen) == 1:
            return chosen, False
        return chosen, 'no_eligible_contract'

    @api.model
    def _chronology_issue(self, versions):
        for version in versions:
            if version.supersedes_version_id and version.supersedes_version_id.contract_id != version.contract_id:
                return 'cross_contract_supersession'
            if version.version_number > 1 and not version.supersedes_version_id:
                return 'supersession_evidence_missing'
            seen = set()
            node = version
            while node.supersedes_version_id:
                nxt = node.supersedes_version_id.id
                if nxt in seen:
                    return 'circular_supersession'
                seen.add(nxt)
                node = node.supersedes_version_id
                if len(seen) > 20:
                    return 'circular_supersession'
        dates = [version.effective_from for version in versions]
        if any(not day for day in dates) or len(dates) != len(set(dates)):
            return 'chronology_conflict'
        return False

    @api.model
    def _version_on(self, versions, pricing_date):
        started = versions.filtered(
            lambda version: version.effective_from
            and version.valid_from
            and version.valid_to
            and version.valid_from <= pricing_date <= version.valid_to
            and version.effective_from <= pricing_date
        )
        if not started:
            return started
        if len(set(started.mapped('effective_from'))) != len(started):
            return started.browse()
        return started.sorted(key=lambda version: version.effective_from)[-1:]

    @api.model
    def _select_line(self, version, product, request, dated):
        lines = version.line_ids.filtered(lambda line: line.product_id.id == product.id)
        uom_id = request.get('uom_id')
        if uom_id:
            lines = lines.filtered(lambda line: line.uom_id.id == uom_id)
        if len(lines) > 1:
            return self._outcome(
                'POLICY_REVIEW_REQUIRED',
                'pricing_unit_unresolved',
                self.env._(
                    'More than one pricing unit is approved for this product. '
                    'No unit was selected and no quantity tier was calculated.'
                ),
                request,
                dated,
            )
        if not lines:
            return self._outcome(
                'NO_APPLICABLE_CONTRACT',
                'no_eligible_contract',
                self.env._(
                    'No approved contract version covers this company, customer, product, and pricing date.'
                ),
                request,
                dated,
            )
        return lines

    @api.model
    def _template_sibling_exists(self, company, partner, product, pricing_date):
        if not product.product_tmpl_id:
            return False
        return bool(self.env['cpla.customer.contract.version.line'].search_count([
            ('company_id', '=', company.id),
            ('product_id.product_tmpl_id', '=', product.product_tmpl_id.id),
            ('product_id', '!=', product.id),
            ('version_id.partner_id', '=', partner.id),
            ('version_id.state', '=', 'approved'),
            ('version_id.effective_from', '<=', pricing_date),
            ('version_id.valid_to', '>=', pricing_date),
        ]))

    @api.model
    def _matched(self, version, line, request, dated, partner, product):
        version.ensure_one()
        line.ensure_one()
        grandfathering = self._grandfathering(version, request, dated)
        dated = dict(dated)
        dated['grandfathering_applied'] = grandfathering
        price = line.price_unit
        explanation = self.env._(
            'Version %(version)s was selected. It is the only approved version visible for this '
            'company, customer, and product on %(pricing_date)s. The pricing date came from the request. '
            'The company policy is not operationally approved. This is not an invoice audit.',
            version=version.reference,
            pricing_date=fields.Date.to_string(dated['pricing_date']),
        )
        result = self._outcome(
            'MATCHED_AUTHORITATIVE',
            'single_eligible_authority',
            explanation,
            request,
            dated,
            version=version,
            line=line,
        )
        result.update({
            'contract_id': version.contract_id.id,
            'version_id': version.id,
            'version_line_id': line.id,
            'unit_price': price,
            'currency_id': line.currency_id.id,
            'uom_id': line.uom_id.id,
            'customer_scope': 'exact_customer',
            'product_specificity': 'exact_variant',
            'effective_from': fields.Date.to_string(version.effective_from),
            'authority_to': fields.Date.to_string(self._authority_to(version, request)),
            'policy_id': version.policy_id.id,
            'policy_version_snapshot': version.policy_version_snapshot,
            'pricing_date_policy_snapshot': version.pricing_date_policy_snapshot,
            'precedence_policy_snapshot': version.precedence_policy_snapshot,
            'coverage_policy_snapshot': version.coverage_policy_snapshot,
            'policy_operationally_approved': False,
            'evidence_ids': version.evidence_ids.ids,
            'grandfathering_applied': grandfathering,
            'partner_name': version.partner_name or partner.display_name,
            'product_name': line.product_name or product.display_name,
        })
        return self._apply_quantity(result, line, request)

    @api.model
    def _apply_quantity(self, result, line, request):
        quantity = self.env['cpla.pricing.quantity'].evaluate(line, request)
        result.update({
            'tier_status': quantity['tier_status'],
            'quantity_status': quantity['quantity_status'],
            'tier_id': quantity['tier_id'],
            'qualified_quantity_exact': quantity['qualified_quantity_exact'],
            'qualified_uom_id': quantity['qualified_uom_id'],
            'normalized_unit_price': quantity['normalized_unit_price'],
            'normalized_unit_price_exact': quantity['normalized_unit_price_exact'],
            'normalized_quantity_exact': quantity['normalized_quantity_exact'],
            'normalized_uom_id': quantity['normalized_uom_id'],
            'conversion_factor_exact': quantity['conversion_factor_exact'],
            'contract_unit_price': quantity['contract_unit_price'],
            'contract_uom_id': quantity['contract_uom_id'],
            'billed_quantity_exact': quantity['billed_quantity_exact'],
            'tier_method': quantity['tier_method'],
            'quantity_basis': quantity['quantity_basis'],
            'return_policy': quantity['return_policy'],
            'historical_factor_used': quantity['historical_factor_used'],
        })
        if quantity['status']:
            result['status'] = quantity['status']
            result['reason_code'] = quantity['reason_code']
            result['unit_price'] = False
            result['precedence_rule'] = False
            result['explanation'] = quantity['explanation']
            return result
        if quantity['explanation']:
            result['explanation'] = '%s %s' % (result['explanation'], quantity['explanation'])
        if quantity['quantity_status'] == 'tier_matched':
            result['unit_price'] = quantity['unit_price']
            result['uom_id'] = quantity['uom_id']
        result.update(self.env['cpla.pricing.financial'].normalize(line, request))
        result.update(self.env['cpla.discount.evaluator'].evaluate(line, request))
        result['leakage_amount'] = False
        result['is_recovered_cash'] = False
        return result

    @api.model
    def _grandfathering(self, version, request, dated):
        if dated.get('pricing_date_rule') != 'order_confirmation':
            return False
        invoice = self._as_date(request.get('invoice_date'))
        pricing_date = dated['pricing_date']
        if not invoice or invoice == pricing_date:
            return False
        cutoff = self._as_datetime(request.get('knowledge_cutoff'))
        later = self.env['cpla.customer.contract.version'].search([
            ('contract_id', '=', version.contract_id.id),
            ('state', '=', 'approved'),
            ('effective_from', '>', pricing_date),
            ('effective_from', '<=', invoice),
            ('id', '!=', version.id),
        ])
        return bool(later.filtered(lambda item: self._known_at(item, cutoff)))

    @api.model
    def _known_at(self, version, cutoff):
        if not version.approved_at:
            return False
        if cutoff and version.approved_at > cutoff:
            return False
        if self._retroactive_blocked(version):
            return False
        return True

    @api.model
    def _authority_to(self, version, request):
        cutoff = self._as_datetime(request.get('knowledge_cutoff'))
        later = self.env['cpla.customer.contract.version'].search([
            ('contract_id', '=', version.contract_id.id),
            ('state', '=', 'approved'),
            ('effective_from', '>', version.effective_from),
        ], order='effective_from, id')
        visible = later.filtered(lambda item: self._known_at(item, cutoff))
        if visible:
            return fields.Date.add(visible[0].effective_from, days=-1)
        return version.valid_to

    @api.model
    def _conflict_text(self, versions):
        references = ', '.join(versions.mapped('reference'))
        return self.env._(
            'More than one approved contract covers this customer and product on the pricing date. '
            'No price was selected. Visible references: %(references)s.',
            references=references,
        )

    @api.model
    def _outcome(self, status, reason, explanation, request, dated=None, version=None, line=None, conflicting=None):
        dated = dated or {}
        result = {
            'status': status,
            'reason_code': reason,
            'explanation': explanation,
            'company_id': request.get('company_id') or False,
            'partner_id': request.get('partner_id') or False,
            'product_id': request.get('product_id') or False,
            'contract_id': False,
            'version_id': False,
            'version_line_id': False,
            'unit_price': False,
            'currency_id': False,
            'uom_id': False,
            'customer_scope': False,
            'product_specificity': False,
            'pricing_date': fields.Date.to_string(dated['pricing_date']) if dated.get('pricing_date') else False,
            'pricing_date_rule': dated.get('pricing_date_rule') or False,
            'basis_source': dated.get('basis_source') or False,
            'policy_operationally_approved': False,
            'policy_id': False,
            'effective_from': False,
            'authority_to': False,
            'knowledge_cutoff': str(request.get('knowledge_cutoff') or '') or False,
            'grandfathering_applied': False,
            'precedence_rule': reason if status == 'MATCHED_AUTHORITATIVE' else False,
            'tier_status': 'not_applicable',
            'quantity_status': 'not_applicable',
            'tier_id': False,
            'qualified_quantity_exact': False,
            'qualified_uom_id': False,
            'normalized_unit_price': False,
            'normalized_unit_price_exact': False,
            'normalized_quantity_exact': False,
            'normalized_uom_id': False,
            'conversion_factor_exact': False,
            'contract_unit_price': False,
            'contract_uom_id': False,
            'billed_quantity_exact': False,
            'tier_method': False,
            'quantity_basis': False,
            'return_policy': False,
            'historical_factor_used': False,
            'evidence_ids': [],
            'conflicting_version_ids': conflicting.ids if conflicting else [],
            'resolution_purpose': request.get('resolution_purpose') or (
                'historical' if request.get('knowledge_cutoff') else 'prospective'
            ),
            'is_recovered_cash': False,
            'leakage_amount': False,
        }
        result.update(self.env['cpla.pricing.financial'].blank())
        result.update(self.env['cpla.discount.evaluator'].blank())
        return result

    @api.model
    def _as_date(self, value):
        if not value:
            return None
        if hasattr(value, 'year') and not hasattr(value, 'hour'):
            return value
        try:
            return fields.Date.to_date(value)
        except (TypeError, ValueError):
            return None

    @api.model
    def _as_datetime(self, value):
        if not value:
            return None
        if hasattr(value, 'hour'):
            return value
        try:
            return fields.Datetime.to_datetime(value)
        except (TypeError, ValueError):
            return None


class PricingApplicabilityCheck(models.TransientModel):
    """Authorized applicability check. It does not audit invoices."""

    _name = 'cpla.pricing.applicability.check'
    _description = 'Contract Applicability Check'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    partner_id = fields.Many2one('res.partner', string='Customer', check_company=True)
    product_id = fields.Many2one('product.product', string='Product Variant', check_company=True)
    pricing_date = fields.Date(string='Explicit Pricing Date')
    basis = fields.Selection(
        selection=[
            ('order_confirmation', 'Sales order confirmation date'),
            ('delivery', 'Delivery date'),
            ('invoice', 'Customer invoice date'),
        ],
        string='Requested Date Basis',
    )
    order_confirmation_date = fields.Date(string='Order Confirmation Date')
    order_confirmed = fields.Boolean(string='Order Confirmed')
    quotation_date = fields.Date(string='Quotation Date')
    invoice_date = fields.Date(string='Invoice Date')
    delivery_date = fields.Date(string='Delivery Date')
    delivery_date_2 = fields.Date(string='Second Delivery Date')
    knowledge_cutoff = fields.Datetime(string='Knowledge Cutoff')
    customer_group_ref = fields.Char(string='Customer Group Reference')
    template_fallback_requested = fields.Boolean(string='Ask About Template Scope')
    quantity = fields.Float(string='Quantity Context')
    uom_id = fields.Many2one('uom.uom', string='Pricing Unit')
    quantity_uom_id = fields.Many2one('uom.uom', string='Quantity Unit')
    comparison_uom_id = fields.Many2one('uom.uom', string='Comparison Unit')
    qualification_basis = fields.Selection(
        selection=[
            ('sales_order', 'Sales order quantity'),
            ('invoice_line', 'Invoice line quantity'),
            ('delivery', 'Delivery quantity'),
        ],
        string='Supplied Quantity Basis',
    )
    order_quantity = fields.Float(string='Order Quantity', digits=0)
    invoice_quantity = fields.Float(string='Invoice Quantity', digits=0)
    delivery_quantity = fields.Float(string='Delivery Quantity', digits=0)
    billed_quantity = fields.Float(string='Billed Quantity', digits=0)
    returned_quantity = fields.Float(string='Returned Quantity', digits=0)
    document_type = fields.Selection(
        selection=[('credit_note', 'Credit note')],
        string='Document Type',
    )
    status = fields.Char(string='Result', readonly=True)
    reason_code = fields.Char(string='Reason', readonly=True)
    explanation = fields.Text(string='Explanation', readonly=True)
    contract_id = fields.Many2one('cpla.customer.contract', string='Selected Contract', readonly=True)
    version_id = fields.Many2one('cpla.customer.contract.version', string='Selected Version', readonly=True)
    version_line_id = fields.Many2one(
        'cpla.customer.contract.version.line',
        string='Selected Line',
        readonly=True,
    )
    unit_price = fields.Monetary(string='Approved Unit Price', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', readonly=True)
    customer_scope = fields.Char(string='Customer Scope', readonly=True)
    product_specificity = fields.Char(string='Product Scope', readonly=True)
    grandfathering_applied = fields.Boolean(string='Grandfathering Applied', readonly=True)
    tier_status = fields.Char(string='Quantity Tier', readonly=True)
    quantity_status = fields.Char(string='Quantity Status', readonly=True)
    normalized_unit_price = fields.Float(string='Normalized Unit Price', readonly=True, digits=0)
    normalized_uom_id = fields.Many2one('uom.uom', string='Normalized Unit', readonly=True)
    qualified_quantity_exact = fields.Char(string='Qualified Quantity', readonly=True)
    contract_unit_price = fields.Float(string='Contract Unit Price', readonly=True, digits=0)

    def action_resolve(self):
        self.ensure_one()
        self.env['cpla.pricing.applicability']._check_caller()
        if self.company_id not in self.env.companies:
            raise AccessError(self.env._(
                'You are not allowed to resolve contracts for this company.'
            ))
        delivery_dates = [day for day in (self.delivery_date, self.delivery_date_2) if day]
        result = self.env['cpla.pricing.applicability'].resolve({
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'product_id': self.product_id.id,
            'pricing_date': self.pricing_date,
            'basis': self.basis,
            'order_confirmation_date': self.order_confirmation_date,
            'order_confirmed': self.order_confirmed,
            'quotation_date': self.quotation_date,
            'invoice_date': self.invoice_date,
            'delivery_dates': delivery_dates,
            'knowledge_cutoff': self.knowledge_cutoff,
            'customer_group_ref': self.customer_group_ref,
            'template_fallback_requested': self.template_fallback_requested,
            'quantity': self.quantity or False,
            'uom_id': self.uom_id.id,
            'quantity_uom_id': self.quantity_uom_id.id,
            'comparison_uom_id': self.comparison_uom_id.id,
            'qualification_basis': self.qualification_basis,
            'order_quantity': self.order_quantity or False,
            'invoice_quantity': self.invoice_quantity or False,
            'delivery_quantity': self.delivery_quantity or False,
            'billed_quantity': self.billed_quantity or False,
            'returned_quantity': self.returned_quantity or False,
            'document_type': self.document_type,
        })
        matched = result['status'] == 'MATCHED_AUTHORITATIVE'
        self.write({
            'status': result['status'],
            'reason_code': result['reason_code'],
            'explanation': result['explanation'],
            'contract_id': result['contract_id'] if matched else False,
            'version_id': result['version_id'] if matched else False,
            'version_line_id': result['version_line_id'] if matched else False,
            'unit_price': result['unit_price'] if matched else False,
            'currency_id': result['currency_id'] if matched else False,
            'customer_scope': result['customer_scope'],
            'product_specificity': result['product_specificity'],
            'grandfathering_applied': result['grandfathering_applied'],
            'tier_status': result['tier_status'],
            'quantity_status': result.get('quantity_status'),
            'normalized_unit_price': result.get('normalized_unit_price') if matched else False,
            'normalized_uom_id': result.get('normalized_uom_id') if matched else False,
            'qualified_quantity_exact': result.get('qualified_quantity_exact') if matched else False,
            'contract_unit_price': result.get('contract_unit_price') if matched else False,
            'financial_status': result.get('financial_status'),
            'financial_reason': result.get('financial_reason'),
            'financial_explanation': result.get('financial_explanation'),
            'comparable_unit_price_exact': (
                result.get('comparable_unit_price_exact')
                if result.get('financial_status') in ('NORMALIZED', 'SAME_CURRENCY_NO_CONVERSION')
                else False
            ),
            'comparable_currency_id': (
                result.get('comparable_currency_id')
                if result.get('financial_status') in ('NORMALIZED', 'SAME_CURRENCY_NO_CONVERSION')
                else False
            ),
            'fx_rate_exact': (
                result.get('fx_rate_exact')
                if result.get('financial_status') in ('NORMALIZED', 'SAME_CURRENCY_NO_CONVERSION')
                else False
            ),
            'fx_rate_direction': result.get('fx_rate_direction') if matched else False,
            'fx_date_used': result.get('fx_date_used') if matched else False,
            'tax_basis_result': result.get('tax_basis') if matched else False,
            'rounding_stage_result': result.get('rounding_stage') if matched else False,
            'discount_status': result.get('discount_status'),
            'discount_reason': result.get('discount_reason'),
            'discount_applied': bool(result.get('discount_applied')),
            'price_exception_indicator': result.get('price_exception_indicator') or False,
            'approved_adjusted_unit_price_exact': (
                result.get('approved_adjusted_unit_price_exact')
                if result.get('discount_status') in (
                    'AUTHORIZED_PRICE_RESOLVED',
                    'NO_ADDITIONAL_DISCOUNT',
                    'SPECIAL_PRICE_APPLICABLE',
                    'APPROVED_OVERRIDE_APPLICABLE',
                )
                else False
            ),
        })
        return True
