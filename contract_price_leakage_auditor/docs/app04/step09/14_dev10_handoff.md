# DEV-10 handoff

DEV-10 is not started. This file is the contract a quotation control must call. Do not treat this phase as quotation blocking.

## Models

| Name | Role |
| --- | --- |
| `cpla.discount.concession` | Contractual term on `cpla.customer.contract.version`. |
| `cpla.discount.approval` | `additional_concession` or `transaction_override`. |
| `cpla.discount.event` | Append-only. |
| `cpla.discount.evaluator` | Abstract, read-only, no access row. |

## Adjusted-price API

```text
cpla.discount.evaluator.evaluate(line, request)
```

`line` is one `cpla.customer.contract.version.line`. The caller must already be allowed to read it.

Request keys that are kept: `partner_id`, `product_id`, `pricing_date`, `quantity`, `quantity_uom_id`, `comparison_uom_id`, `knowledge_cutoff`, `sale_reference`, `sale_line_reference`, `actual_unit_price_exact`, `entered_discount_percent`, `entered_unit_price_exact`, `company_id`.

Keys that are removed and have no effect: `discount_rate`, `discount_percent`, `approved_adjusted_unit_price_exact`, `concession_id`, approver fields, `exposure_exact`, `baseline_unit_price_exact`, `leakage_amount`, `stacking_policy`.

`baseline_only` is internal. Quotation code should not send it.

An adjusted price is present only when `discount_status` is one of `AUTHORIZED_PRICE_RESOLVED`, `NO_ADDITIONAL_DISCOUNT`, `SPECIAL_PRICE_APPLICABLE`, `APPROVED_OVERRIDE_APPLICABLE`.

Other statuses used by this phase: `DISCOUNT_APPROVAL_PENDING`, `DISCOUNT_APPROVAL_REJECTED`, `DISCOUNT_EXPIRED`, `DISCOUNT_NOT_YET_EFFECTIVE`, `DISCOUNT_SCOPE_MISMATCH`, `DISCOUNT_STACKING_REVIEW_REQUIRED`, `DISCOUNT_AUTHORITY_CONFLICT`, `DISCOUNT_EVIDENCE_REVIEW_REQUIRED`, `UNAUTHORIZED_DISCOUNT_INDICATOR` (on `price_exception_indicator`), `UNSUPPORTED_CONCESSION_TYPE`, `DISCOUNT_PRICE_INVALID`, `COMPANY_ACCESS_DENIED`, `not_applicable`.

`UNAUTHORIZED_DISCOUNT_INDICATOR` is an exception flag when an authoritative adjusted price exists and `actual_unit_price_exact` is lower. It is not a leakage finding.

## Application order

1. Resolver selects the version.
2. Quantity tier or standalone price.
3. Financial comparable price. Stop if financial status is not `NORMALIZED` or `SAME_CURRENCY_NO_CONVERSION`.
4. Contractual concessions, combined under the version stacking mode.
5. Approved additional concessions on the same combination, unless the caller passed a sales reference (those go to the override step).
6. One matching approved override for that sales reference and line reference.

Supported stacking values are on the version: `additive_percentage`, `sequential_percentage`, `percentage_then_fixed`, `fixed_then_percentage`, `fixed_price_replaces_base`, `explicit_rule_order`, plus one exclusive row or one ordinary row without a mode. Two rows and `unconfigured` return `DISCOUNT_STACKING_REVIEW_REQUIRED`.

## Approval and override

Create `cpla.discount.approval` as the authenticated user. Call `action_submit`, then `action_approve` as a different finance manager. The limit must already be stored on the approved version. An empty limit raises and leaves the request submitted.

An override applies only when both reference strings match and the quantity is within `quantity_exact`. DEV-10 must not copy that approval onto another order line and must not write the sales price from this module’s evaluator.

## Security

Company A’s concession is invisible to Company B. Cross-company `version_id` on an approval is rejected. The diagnostic result for a company mismatch contains no rate. Quotation warnings must use the status and must not print another company’s price.

## Open decisions

DEC-01 through DEC-20 and DEC-04 stay open. DEC-06, DEC-07, and DEC-08 stay open. Company `discount_approval_policy` is not a stacking rule and not an amount. No numeric approval threshold was invented beyond the limit fields a user stores on a draft version. `BEST_SINGLE` is not a mode. Buy-x-get-y stays `unsupported`.

## Odoo 18 and Odoo 20

No conversion was done. These surfaces need their own check before either series is claimed:

- `sale.order.line.discount` is a stored computed float in this Odoo 19 tree. DEV-10 must re-read it on 18 and 20.
- `product.pricelist.item.compute_price` in this tree is `fixed`, `percentage`, `formula`.
- Loyalty exists in the tree and is not a dependency.
- Group fields are `group_ids` / `all_group_ids`.
- Version snapshots, currency rates, and record rules are Odoo 19 behavior.
- Tests use `TransactionCase` and `Manifest.for_addon`.

## Quotation work that remains

- Warn when the typed price is below `approved_adjusted_unit_price_exact`.
- Offer a draft override for that order line only.
- Block confirmation only where a later approved policy says so. This phase does not block.
- Keep native discount behavior. Do not overwrite `price_unit` from the evaluator.
- Keep invoice comparison, leakage cases, recovery, and crons out of DEV-10 unless that prompt asks for them.

## Fixtures to keep

GOLD-DISC-001 through GOLD-DISC-020 in `09_golden_financial_fixtures.md`. The pre-discount GOLD-INT-001 amount 1,008 is unchanged. A 5 percent contractual example in this phase is 1,140 from a 1,200 base.
