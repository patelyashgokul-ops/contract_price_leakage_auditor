# 02 — Quantity qualification policies

Date: 2026-10-28.

## What is not the rule

`cpla.company.policy.quantity_basis_policy` is still a candidate. Default `unconfigured`. Values remain `unconfigured`, `sales_order`, `invoice`, `delivery`, `period_volume`, and `customer_group`.

The help text now says the candidate is not the contract quantity rule. `operationally_approved` stays false. DEC-04 is not decided. The resolver does not read this candidate when it selects a tier.

## What is the rule

The approved version line stores `quantity_basis`:

| Line value | Qualifying field | Priced in DEV-07 |
| --- | --- | --- |
| `unconfigured` | None. Tiers cannot be approved. | No |
| `sales_order` | `order_quantity`, or bare `quantity` only when no other basis-specific number is present and the request basis is empty or `sales_order` | Yes |
| `invoice_line` | `invoice_quantity`, with the same bare-`quantity` limit | Yes. One invoice line. Not an invoice total. |
| `delivery` | `delivery_quantity`, with the same bare-`quantity` limit | Yes, when the caller supplies the quantity |
| `cumulative` | Not used | `UNSUPPORTED_QUANTITY_POLICY`. Approval refused. |

The company value `invoice` is not the line value `invoice_line`. They are different fields. A company candidate of `invoice` does not change a line whose basis is `sales_order`.

## Substitution is refused

If the line says sales order and the request has only `invoice_quantity`, the status is `MISSING_QUALIFYING_QUANTITY`. The invoice quantity is not used. The same applies to delivery.

`invoice_line_quantities` or `delivery_quantities` with more than one number, or `allocation_unverified`, returns `SOURCE_ALLOCATION_REVIEW_REQUIRED`. Those lists are not summed.

`other_product_quantity` or `variant_quantity` returns `POLICY_REVIEW_REQUIRED` with reason `product_aggregation_not_approved`. Bearing A and Bearing B are not added together.

## Qualifying quantity and billed quantity

`billed_quantity` is echoed as `billed_quantity_exact`. It is not added to the qualifying quantity and it is not multiplied into the unit price.

An order of 500 with five billed slices of 100, under `sales_order`, qualifies at the 500+ tier for each slice. Each result still reports billed quantity 100.

## Cumulative volume

Not implemented. The service does not read today’s purchases. A line set to `cumulative` returns `UNSUPPORTED_QUANTITY_POLICY` and no price, including a draft line, so the refusal can be tested before approval.

Covered customers, products, returns, threshold dates, and retroactive versus prospective effect are not designed as an engine. They stay deferred until a contract period and acceptance fixtures exist.

## Return policy

`return_policy` on the line:

| Value | Behavior |
| --- | --- |
| `unconfigured` | A positive `returned_quantity` is `POLICY_REVIEW_REQUIRED`. No price. |
| `order_tier_lock` | The original qualifying quantity stays. A return of 20 from 500 still qualifies as 500. |
| `net_quantity` | Qualifying quantity minus the returned quantity. 500 − 20 = 480, which selects the 100–499 tier at 1150. |

A credit note is not a new positive sale, even when the line locks the original tier.
