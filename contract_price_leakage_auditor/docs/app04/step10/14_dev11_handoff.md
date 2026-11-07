# DEV-11 handoff

DEV-11 is not started. Do not treat a quotation lock as an invoice audit.

## What DEV-11 can read

`sale.order` and `sale.order.line` are extended. The evaluator is `cpla.quotation.compliance`.

`evaluate_line(line, confirmation=False)` returns a plain dict. Important keys: `status`, `reason`, `message`, `approved_adjusted_unit_price_exact`, `actual_unit_price_exact`, `preventive_exposure_exact`, `version_id`, `contract_id`, `tier_id`, `approval_ids`, `control_mode`, `blocks_confirmation`, `order_date_lock_candidate`, `pricing_date_policy_snapshot`, `leakage_amount`, `is_recovered_cash`.

Effective unit: `price_unit × (1 - discount / 100)` when the discount is a simple percent and the tax basis is tax-excluded.

Company modes: `unconfigured`, `disabled`, `warning`, `approval_required`, `block`.

Override linkage: `cpla.discount.approval.sale_order_id`, `sale_line_id`, `sale_reference`, `sale_line_reference`, `request_kind = transaction_override`.

Confirmed evidence: `cpla.sale.price.lock`, one row per `sale_line_id`. Use `version_id`, `pricing_date`, `pricing_date_policy_snapshot`, and `order_date_lock_candidate`. Do not infer grandfathering from the live quotation.

`order_date_lock_candidate` is true only for snapshot `order_confirmation`. Snapshot `invoice` must not lock the order date for a later invoice.

A material change sets `revalidation_required` and does not replace the stored amounts.

## Security

Company rules are global. Contract User remains owner-scoped. Draft amounts are blank unless the user is in the pricing read groups or is the technical superuser. Do not pass `company_id`, `contract_id`, or `approved` from the client into the resolver.

## Not done

Invoice-line allocation, posted-invoice comparison, leakage findings, finance validation, recovery, waivers, debit notes, and invoice-audit crons are not implemented. Tests for those remain deferred.

Two database sessions confirming one order were not executed.

Odoo 18 and Odoo 20 were not installed. `action_confirm`, line pricing fields, list views, and this snapshot need their own regression there.

## Open decisions

DEC-01 through DEC-20 remain open. No tolerance, FX, tax, coverage, or approval threshold was invented. `operationally_approved` is false. The company discount candidate is not a stacking rule. Preventive exposure is not recovered cash.
