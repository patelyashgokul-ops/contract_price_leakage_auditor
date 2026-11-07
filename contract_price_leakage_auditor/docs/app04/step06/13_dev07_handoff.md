# 13 — DEV-07 handoff

DEV-07 was not started.

## Resolver

Technical name: `cpla.pricing.applicability`.

Call: `env['cpla.pricing.applicability'].resolve(request)`.

The check wizard is `cpla.pricing.applicability.check`. Use it for a person. Batch invoice work should call `resolve` and must not assume the wizard.

## Input

Required for a match: `company_id`, `partner_id`, `product_id`, and either `pricing_date` or a supported `basis` with its date.

Optional: `order_confirmed`, `order_confirmation_date`, `quotation_date` (ignored as a pricing date), `invoice_date`, `delivery_dates`, `knowledge_cutoff`, `customer_group_ref`, `template_fallback_requested`, `quantity`, `uom_id`, `resolution_purpose`.

Ignored if supplied: `version_id`, `contract_id`, `unit_price`.

`grandfather_limit` currently forces `POLICY_REVIEW_REQUIRED`. Do not treat that as an approved window.

## Output

On `MATCHED_AUTHORITATIVE`: contract id, version id, line id, `unit_price`, `currency_id`, `uom_id`, `customer_scope = exact_customer`, `product_specificity = exact_variant`, pricing date, effective interval, policy snapshot strings, evidence ids.

`policy_operationally_approved` is false. `leakage_amount` is false. `is_recovered_cash` is false.

If `quantity` is set, `tier_status` is `pending_dev07`. The stored unit price is not a qualified tier price. Do not multiply it.

## Rules DEV-07 must not undo

- Exact customer only. No parent, branch, subsidiary, or group inheritance.
- Exact variant only. No template or category price.
- Approved versions only. Inclusive `effective_from`. Cutoff uses `approved_at`.
- One contract, or `CONFLICT_REVIEW_REQUIRED` with no price.
- Do not rank by price or database id.
- Two delivery dates stay `PARTITION_REVIEW_REQUIRED` until a real allocation exists.
- Do not convert units. A non-default unit cannot be approved in the current review rules.
- Do not calculate leakage, FX, tax, or discounts.

## Security

Same five read roles. Company domain first. No `sudo(`. Hide prices from users who cannot read the version.

## Tests already passing

APP-001 through APP-020, CUS06, PRD06, DAT06, GFD06, PRE06, SEC06, DET06, and REG06 passed on the 2026-10-28 upgrade rerun and the fresh install. See `10_automated_test_results.md`.

## Open decisions

DEC-01 pricing date, DEC-02 precedence, DEC-03 coverage, DEC-04 quantity basis, and the unit-conversion rule are still open. Retroactivity is `not_authorized`. License decision is still required.
