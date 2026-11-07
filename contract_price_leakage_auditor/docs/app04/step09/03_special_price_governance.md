# Special price governance

A fixed special price is an entitled unit price. It is not a reduction computed by subtracting the special price from the base.

## Example

Base approved price 1,200. Approved special price 1,150. Quantity 500. Reference actual price 1,100.

| Measure | Formula | Executed result |
| --- | --- | --- |
| Approved adjusted unit price | The special price | 1,150 |
| Concession per unit | 1,200 − 1,150 | 50 |
| Authorized concession | 50 × 500 | 25,000 |
| Gross difference | (1,200 − 1,100) × 500 | 50,000 |
| Potential unauthorized difference | (1,150 − 1,100) × 500 | 25,000 |

Status is `SPECIAL_PRICE_APPLICABLE`. `discount_applied` is true. `price_exception_indicator` is `UNAUTHORIZED_DISCOUNT_INDICATOR` because the supplied actual price is below the approved adjusted price. `leakage_amount` is false. `leakage_finding_created` is false. The indicator is a pricing exception. It is not a finding and it does not describe employee misconduct.

Test `test_disc09_t001_gold_disc_001_special_price_and_reconciliation` passed inside the 610-test runs on `cpla_dev09_20261028` and `cpla_dev08_20261028`.

## Evidence kept on the concession

Company, version, optional version line, customer scope, product scope, currency, pricing unit, quantity bounds, effective dates, exclusivity, precedence rank, sequence, evidence reference, and the unit factors snapshotted at version approval (`concession_uom_factor_exact`, `product_uom_factor_exact`).

Factors are captured when the version is approved. Evaluation uses those snapshots. A monetary concession whose snapshot cannot be normalized returns `DISCOUNT_EVIDENCE_REVIEW_REQUIRED`. A foreign amount in a third currency, with no conversion path onto the comparison currency, is not subtracted from the base. That case returned reason `concession_fx_missing`.

## Exclusivity

An exclusive special price of 1,150 is the adjusted price even when a general 5 percent concession also matches. The 5 percent is not applied on top. Two exclusive special prices with rank 0 return `DISCOUNT_AUTHORITY_CONFLICT` and no adjusted price. Unique ranks select the lowest rank. In the executed case, rank 1 at 1,180 won over rank 2 at 1,100. The lower price was not selected.

## Dates and scope

A special price for one customer does not apply to another customer (`DISCOUNT_SCOPE_MISMATCH`). A special price for one variant does not apply to another variant. The trace for the mismatched variant does not include the special price 1,150.

An effective end before the pricing date returns `DISCOUNT_EXPIRED`. An effective start after the pricing date returns `DISCOUNT_NOT_YET_EFFECTIVE`. The same concession applies on its own start date.

## Historical protection

An approved concession cannot be edited or deleted by a contract user. Python `write` and `unlink` refuse the change while the version is approved. An amendment copies the row onto a new draft. Changing the copy does not change the source percent. The executed amendment case kept the source at 5 percent (adjusted 1,140 on the day before the new version) and the new version at 9 percent (adjusted 1,092 on the new version’s effective date). The new version starts the next day because two approved versions cannot share one effective date.

Revocation stores who revoked, when, the effective date, and the reason. The original percent stays. The revoker must be a finance manager and must not be the user who approved the version. A pricing date before the revocation date still receives the concession. A pricing date on or after that date returns to the base price.
