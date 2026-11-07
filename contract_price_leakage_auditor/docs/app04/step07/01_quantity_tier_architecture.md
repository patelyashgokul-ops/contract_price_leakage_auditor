# 01 — Quantity tier architecture

Date: 2026-10-28. Addon `contract_price_leakage_auditor` `19.0.1.5.0`. Odoo 19 Community `19.0.0` final.

## Models

| Model | Role |
| --- | --- |
| `cpla.customer.contract.version.line` | Stores `tier_method`, `quantity_basis`, and `return_policy`. The standalone `price_unit` stays on the line. |
| `cpla.customer.contract.version.tier` | One quantity break for that line. |
| `cpla.pricing.quantity` | Read-only selector and unit normalizer. No table of results. |

The tier model name does not start with `cpla.contract`. There is no second contract header.

Tiers hang off the version line. Company, version, product, and currency are related stored fields from that line. They are not a second source of ownership.

## Methods

`tier_method` is stored. The number of rows does not choose a method.

| Value | Meaning |
| --- | --- |
| `none` | No tier. The line `price_unit` remains the rate when no tier rows exist. |
| `full_volume` | One rate applies to the whole qualifying quantity. This is the only priced method. |
| `graduated` | Not priced. Evaluation returns `UNSUPPORTED_QUANTITY_POLICY`. Approval is refused. |

A line with tier rows and method `none` cannot be approved. A `full_volume` line with no rows cannot be approved.

## Base price and tier price

Zero tier rows and method `none` keep the stored line price. A supplied quantity does not select another rate. The result says `base_price_applicable` and the explanation says the stored price is not a qualified tier price.

When any tier row exists, the line price is informational. It is not a fallback, not a nearest tier, and not stacked with a tier rate. A quantity outside every tier is `NO_MATCHING_TIER` with no price.

## Range

Minimum inclusive, maximum exclusive: `[minimum, maximum)`.

`has_maximum` is required because an empty Odoo float is `0.0` and cannot mean “no upper bound”.

The reference schedule, in company currency, is:

| Range | Rate |
| --- | --- |
| `[1, 100)` | 1200 |
| `[100, 500)` | 1150 |
| `[500, open)` | 1100 |

So 1 and 99 select 1200, 100 and 499 select 1150, and 500 and 501 select 1100. `99.999` stays in the first tier.

Minimum must be nonnegative. When `has_maximum` is set, maximum must be greater than minimum. Overlap and a duplicate range raise `ValidationError` under a row lock on the parent line. A gap between tiers blocks approval. Nothing fills the gap. Quantity below the first tier is `NO_MATCHING_TIER`, not an approval error.

Zero quantity is `NO_MATCHING_TIER` with reason `zero_quantity`. It is not a positive sale. A negative quantity and a `credit_note` document type are `NEGATIVE_QUANTITY_REVIEW`.

## Draft and approved

Contract users and contract managers may create and edit tiers only while the version is draft. Approval calls `_write_multi` to freeze conversion factors, then the existing approval path. Ordinary `write` and `unlink` on an approved tier raise `UserError`.

`create_amendment` copies tier business fields onto the new draft. `create` recomputes factors from the live unit at that moment. The previous approved version keeps its stored factors. Initial `approve_initial` still copies contract lines and does not invent tiers. Upgrade does not add tiers to versions that were already approved.

## Checksum

New approvals hash the previous snapshot plus the tier rows. Stored hashes on versions approved before this change are not recomputed. Comparison adds a “Quantity Tiers Changed” row only when the tier signatures differ.
