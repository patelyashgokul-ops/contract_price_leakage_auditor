# Leakage calculation formulas

Arithmetic uses `Decimal` with precision 28 and `ROUND_HALF_UP`, through the existing `_decimal`, `_text`, and `_arithmetic` helpers. `_text` strips trailing zeros, so `957.60` is stored as `957.6`. Tests compare `Decimal` values. Float subtraction is not used for the golden amounts.

The unit prices are evaluated on the original allocated quantity so tiers and overrides see the billed or order basis. The extended amounts use the net eligible quantity.

For one verified eligible allocation, after UoM, currency, and tax normalization:

- Gross unit difference = approved pre-concession unit price − actual comparable unit price.
- Concession unit = approved pre-concession unit price − approved adjusted unit price.
- Raw unit difference = approved adjusted unit price − actual comparable unit price.
- Gross extended = gross unit × eligible quantity.
- Authorized concession extended = concession unit × eligible quantity.
- Raw extended = raw unit × eligible quantity.
- Potential underbilling = raw extended when raw extended is positive, otherwise zero.

The signed raw extended amount is stored. Absolute value is not applied. The three stages are not added into a fourth exposure. For the simple positive case, gross extended = authorized concession + potential unauthorized difference. That identity is not used for tax mismatches, refunds, or overbilling.

Overbilling (raw unit below zero) is `PRICE_ABOVE_APPROVED_RATE`. Potential exposure is zero. It does not offset another finding.

An exact match is `PRICING_COMPLIANT`. No finding is created.

A positive raw unit is classified by `_classify_gap`. See `05_missed_increase_and_discount_detection.md`.

Eligible quantity of zero after a verified reversal still classifies the unit gap, but the extended potential is zero, so no current potential finding remains.

## Actual unit price

The starting point is the source map's effective unit: `price_unit × (1 − discount / 100)`. A discount already inside `price_unit` is not subtracted again. A simple included tax is then removed. Currency conversion uses the approved FX clause only. UoM conversion uses `convert_price`. If any of those steps fails, the result is review and the amount is blank.

## Tolerance

`propose_tolerance` still refuses to store a number. There is no invented 1 currency unit or 1 percent tolerance. A small positive raw difference stays `potential`. The raw amount is not erased. `WITHIN_APPROVED_TOLERANCE` is a selection value only.

## What is not summed

Potential leakage, a future finance-validated amount, a recovery target, billed recovery, and collected cash are different concepts. DEV-12 stores only potential leakage. `is_recovered_cash` is forced false. No field records a validated, waived, billed, or collected amount.
