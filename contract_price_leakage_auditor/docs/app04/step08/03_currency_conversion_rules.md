# Currency conversion rules

Amounts in the golden tests use fictional currency codes Q8A, Q8B, and Q8C. INR, USD, and AED are not activated and no production rate rows are created.

## Direction

Odoo stores `res.currency.rate.rate` as the technical table rate. For these tests, `inverse_company_rate` 84 stores a table rate whose reciprocal is 84. The normalizer stores company units per one foreign unit as `Decimal(str(1.0 / table_rate))`, then a canonical text such as `84`. It does not divide `Decimal(1)` by the tiny table rate, because that path produced `84.000000000000005376` in a local check.

| Direction | Formula |
| --- | --- |
| Fixed, source to target | `amount * multiplier` |
| Fixed, target to source | `amount / multiplier` |
| Historical, source to target | `amount * company_per_source / company_per_target` |
| Historical, inverse | `amount * company_per_target / company_per_source` |
| Same currency | No rate. Status `SAME_CURRENCY_NO_CONVERSION`. |

A fixed pair that does not match the source and comparison currencies returns `FX_RATE_REVIEW_REQUIRED` / `fixed_pair_mismatch`. USD 100 at 84 becomes 8400, not about 1.190476.

## Company currency

The company currency is identity `1` unless a non-identity rate row exists for it. That non-identity row returns `company_currency_rate_not_identity` and no price. Cross-currency conversion uses the two company-per-unit snapshots. No third rate is invented.

## Comparison currency

| Policy | Target |
| --- | --- |
| `unconfigured` | `INVALID_CURRENCY_CONTEXT`. Company currency is not assumed. |
| `contract_currency` | Version currency. |
| `company_currency` | Version company currency. |
| `explicit_currency` | `comparison_currency_id` on the version. |

Invoice currency and a reporting currency are not selectable yet. They are not interchangeable with the contract currency. Final reporting aggregation belongs to a later phase.

## Rounding of the conversion

FX multiplication uses `decimal` localcontext precision 28 and half-up. The currency increment is not applied during the conversion. Currency rounding happens only when the version's `rounding_stage` is `per_unit` or `extended_amount`.
