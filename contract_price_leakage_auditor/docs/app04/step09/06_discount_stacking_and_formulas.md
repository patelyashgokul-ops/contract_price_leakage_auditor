# Discount stacking and formulas

Formulas run only when the approved version names the mode, or when a single matching concession needs no mode. Intermediate percentages are not rounded. DEV-08 rounding runs once on the final adjusted unit when the version rounding stage says so. `preserve_exact` keeps the exact decimal. `_text` stores `1105.80` as `1105.8`.

Currency and unit conversion of a monetary concession happen before the subtraction: unit conversion in the concession currency, then the version FX clause into the comparison currency, then one final rounding. USD is not activated in tests. The foreign currency is the fictional code `Q9A`.

## Executed formulas

| Case | Policy | Result |
| --- | --- | --- |
| 5 percent of 1,200 | One percentage. No stacking mode required. | 1,140. Status `AUTHORIZED_PRICE_RESOLVED`. |
| Fixed 50 off 1,200 | One fixed per-unit reduction. | 1,150. Concession per unit 50. |
| 5 percent then 3 percent | `sequential_percentage` | 1,200 × 0.95 × 0.97 = 1,105.8. Two stages. |
| 5 percent + 3 percent | `additive_percentage` | 1,200 × 0.92 = 1,104. |
| Exclusive special 1,150 and a 5 percent row | Exclusivity, stacking left unconfigured | 1,150. One selected concession. |
| 10 percent then 50 | `percentage_then_fixed` | 1,200 × 0.90 − 50 = 1,030. |
| 50 then 10 percent | `fixed_then_percentage` | (1,200 − 50) × 0.90 = 1,035. |
| 5 and 3 with no mode | Stacking `unconfigured`. Company candidate set to `approval_reference_required`. | `DISCOUNT_STACKING_REVIEW_REQUIRED`. No adjusted price. |
| 33.33 percent of 10, stage `per_unit`, currency rounding 0.01 | One percentage. | 6.67. |
| Fixed 1,200 off a 1,200 base | Reduction consumes the price. | `DISCOUNT_PRICE_INVALID`. |
| Percent 100 | Refused at save. | `ValidationError`. The version is not approved. |
| 5 percent applied once | One selected id. | 1,140, which is not 1,083. |

## Foreign unit concession

Contract price 100 per piece in `Q9A`. Fixed concession 5 `Q9A` per box. The box factor snapshot is 10 times the piece factor. Historical fixed FX is 84 company currency per `Q9A`. Comparison currency is the company currency.

Pre-discount comparable price 8,400. Concession per piece 42. Adjusted price 8,358.

A fixed 5 in a third currency, with no rate onto the comparison currency, returns `DISCOUNT_EVIDENCE_REVIEW_REQUIRED` and reason `concession_fx_missing`. The 5 is not subtracted from the converted price.

## Tier

Tier 1,100 from quantity 500, policy `discount_after_tier`, then 5 percent: pre-discount 1,100, adjusted 1,045.

The same tier with `exclusive_tier`: status `NO_ADDITIONAL_DISCOUNT`, reason `exclusive_tier`, price 1,100, `discount_applied` false.

The same tier with `tier_discount_policy` left `unconfigured`: `DISCOUNT_STACKING_REVIEW_REQUIRED`, reason `tier_discount_policy_missing`, no adjusted price.

## Reconciliation

These three extensions describe one comparison. They are not three losses.

- Gross difference = (pre-discount − actual) × quantity
- Authorized concession = (pre-discount − adjusted) × quantity
- Potential unauthorized difference = (adjusted − actual) × quantity, only when the difference is positive

A higher actual price leaves the potential difference empty. Absolute value is not applied. `leakage_amount` stays false.
