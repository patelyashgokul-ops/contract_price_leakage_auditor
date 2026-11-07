# Discount architecture

Addon `contract_price_leakage_auditor` `19.0.1.7.0`. Odoo 19.0 Community. The authorized price is a concession on an approved contract version, or a separate approved request whose snapshot was stored at approval. A company discount candidate is not a rule. A native pricelist or a sales-line discount is not contractual authority.

## Source of authority

| Record | Model | What it authorizes |
| --- | --- | --- |
| Contractual concession | `cpla.discount.concession` | A percentage, a fixed per-unit reduction, a fixed special price, or an unsupported benefit, stored on one `cpla.customer.contract.version`. |
| Discretionary request | `cpla.discount.approval` | An additional concession, or one transaction-scoped price override. Authority exists only in state `approved`. |
| Approval event | `cpla.discount.event` | Append-only actor and timestamp. Write and unlink are refused. |
| Evaluator | `cpla.discount.evaluator` | Read-only abstract model. No access row. It does not create approvals, invoices, or leakage findings. |

The version approval is the authority for rows on `cpla.discount.concession`. A second workflow is not required for those rows. `cpla.discount.approval` is the workflow for a concession that was not on the approved version, and for a manual price that applies to one sales reference and one line reference.

`sale` and `loyalty` are not dependencies. `sale.order.line.discount` and `product.pricelist.item` were inspected in the Odoo 19 Community tree and are not read by the evaluator. `product.pricelist.item.compute_price` is `fixed`, `percentage`, or `formula`. That current rule is not a historical contract.

## Evaluation order

`cpla.pricing.applicability.resolve` selects the approved version, then calls quantity evaluation. On a successful quantity result it calls `cpla.pricing.financial.normalize` and then `cpla.discount.evaluator.evaluate`. The evaluator calls normalize again and calls quantity evaluation again. Both calls are read-only. `leakage_amount` and `is_recovered_cash` are forced false after the merge.

The evaluator returns an adjusted unit price only for:

- `AUTHORIZED_PRICE_RESOLVED`
- `NO_ADDITIONAL_DISCOUNT`
- `SPECIAL_PRICE_APPLICABLE`
- `APPROVED_OVERRIDE_APPLICABLE`

Any other status clears `approved_adjusted_unit_price_exact` and sets `discount_applied` false. `discount_rate` on the request is removed before evaluation. An entered percent or an entered unit price without an approved concession returns `DISCOUNT_EVIDENCE_REVIEW_REQUIRED`.

## Pipeline

1. DEV-06 selects one approved version line, or a review outcome with no price.
2. DEV-07 selects the standalone line price or one full-volume tier, and the comparison unit.
3. DEV-08 produces `comparable_unit_price_exact` when `financial_status` is `NORMALIZED` or `SAME_CURRENCY_NO_CONVERSION`.
4. DEV-09 applies only concessions that match company, customer, product, quantity, dates, and the historical cutoff.
5. The approved adjusted unit price is that comparable price after the named concessions. The gross difference, the authorized concession, and the potential unauthorized difference are separate extensions. They are not added into `leakage_amount`.

If financial normalization is not successful, no discount is applied. A financial status of `COMPANY_ACCESS_DENIED` is returned as the same discount status, with no prices.

## Version clause

These fields live on the contract version and are copied onto an amendment:

- `discount_stacking_policy`
- `tier_discount_policy`
- `authority_limit_basis` and the matching limit amounts
- `retroactive_discount_authority`

`unconfigured` is the default. The company field `discount_approval_policy` remains a candidate. The evaluator does not read it. Setting it to `approval_reference_required` does not combine two concessions.

The version checksum includes `_discount_signature()`. An empty signature stays the same across versions that have no concessions, so comparison does not report a discount change where none exists. A different signature appends “Discount Clause Changed”.

## What this phase does not store

No leakage finding model. No recovery, waiver, or settlement model. No invoice-audit cron. No sale-order foreign key. No rewrite of `sale.order.line` or of a posted invoice. Quotation blocking is DEV-10. Invoice-source evidence is DEV-11. Posted-invoice findings are DEV-12.
