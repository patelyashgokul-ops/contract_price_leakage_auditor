# 07 — Financial precision and formulas

Date: 2026-10-28.

## Formula

Normalized price per target unit = contract price per contract unit × (target unit factor / contract unit factor).

Both factors are the approved absolute factors, not a guessed ratio.

Quantity in the target unit = qualifying quantity × source factor / target factor.

The tier decision uses the qualifying quantity converted into the tier’s quantity unit. The billed quantity is a separate number. The price unit may be a box while the qualifying quantity is in pieces.

## Decimal

Comparisons use `Decimal(str(value))`. They do not use binary float equality. Results that must stay exact are returned as `normalized_unit_price_exact`, `qualified_quantity_exact`, `normalized_quantity_exact`, and `conversion_factor_exact`.

`100 / 12` stays the exact decimal string. It is not stored as 8.

`99.999` is not rounded to 100 before the boundary test. The first tier is `[1, 100)`, so 99.999 selects 1200.

## What this phase does not round

There is no monetary rounding policy, no tax rounding, and no tolerance. A small difference is not suppressed. `leakage_amount` stays false. Extended invoice value is not computed.

DEV-08 owns final monetary rounding, currency, and tax. The exact strings are the input for that phase.

Odoo’s `_compute_quantity` defaults to rounding and treats a zero quantity as “return unchanged”. The pricing service does not call it.

## No fabricated price

Review and unsupported outcomes set unit price, normalized price, and contract unit price to false. A programming error is not caught and replaced with the line price.
