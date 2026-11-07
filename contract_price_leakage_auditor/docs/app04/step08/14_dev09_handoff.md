# DEV-09 handoff

DEV-09 is not started. This file is the interface an authorized discount must use.

## Service

`cpla.pricing.financial.normalize(line, request)`.

Read the approved version line. Do not trust request prices, rates, tax percents, or tolerances. Those keys are removed.

## Pre-discount price

Use `comparable_unit_price_exact` only when `financial_status` is `NORMALIZED` or `SAME_CURRENCY_NO_CONVERSION`.

The price is in `comparable_currency_id`, in the DEV-07 comparison unit, on a tax-excluded basis when tax normalization succeeded. `discount_applied` is false. Do not multiply by 0.95 inside DEV-08.

GOLD-INT-001 stops at 1008 per piece. A later 5 percent would be 957.60, and 100 pieces at a 7.60 difference would be 760. Those two numbers are not results of this phase.

If `financial_status` is anything else, do not invent a starting price for a discount. Propagate the review status.

## Inputs a discount phase must not redo

- Historical FX policy and frozen rate text on the version.
- Comparison currency policy. Invoice currency is not selected yet.
- Supported tax structures: excluded with `none`, and one ordinary included percent. Complex taxes stay unsupported until a verified Odoo tax context exists. `account` is still not a dependency.
- Rounding stage already applied. Do not round the unit again unless the approved discount policy names that stage.
- Tolerance. DEC-08 is open. Do not suppress a discount difference.

## Evidence to keep

`version_id`, `version_line_id`, `policy_revision_id`, `fx_rate_exact`, `fx_rate_direction`, `fx_date_used`, `fx_evidence`, `tax_component_exact`, and `calculation_trace`.

Company A must not receive Company B's price. Payment-date FX stays `PAYMENT_FX_NOT_CONTRACT_LEAKAGE`.

## Open decisions

DEC-06, DEC-07, and DEC-08 stay open. Company candidates are not operational. Document-date FX is not snapshotted. Fiscal positions are review-required. No leakage finding is created.
