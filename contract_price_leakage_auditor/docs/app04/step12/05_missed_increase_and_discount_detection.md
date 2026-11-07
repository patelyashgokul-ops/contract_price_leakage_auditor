# Missed increase and unauthorized discount detection

One economic underbilling quantity produces one potential amount. A second category is a contributing-cause tag, not a second finding.

## Classification

`_classify_gap` uses the signed raw unit difference:

| Raw unit | Concession on the approved price | Actual equals an earlier approved standalone price | Primary | Cause tag |
| --- | --- | --- | --- | --- |
| Zero | — | — | `PRICING_COMPLIANT` | none |
| Negative | — | — | `PRICE_ABOVE_APPROVED_RATE` | none |
| Positive | Yes | Yes | `UNAUTHORIZED_DISCOUNT_INDICATOR` | `MISSED_CONTRACT_PRICE_INCREASE` |
| Positive | Yes | No | `UNAUTHORIZED_DISCOUNT_INDICATOR` | none |
| Positive | No | Yes | `MISSED_CONTRACT_PRICE_INCREASE` | none |
| Positive | No | No | `UNAUTHORIZED_UNDERPRICING` | none |

An earlier price matches only an approved line on the same contract, with an earlier `effective_from`, the same currency and UoM, no quantity tier, known at the cutoff, and not blocked as retroactive.

An unauthorized price is a control exception. The labels do not say fraud.

## Worked cases that the tests executed

`GOLD-AUD-001`: base 1,200, approved special price 1,150, invoice 1,100, quantity 500. Gross 50,000. Concession 25,000. Potential 25,000. Primary `UNAUTHORIZED_DISCOUNT_INDICATOR`. One finding.

`GOLD-AUD-004`: version 1 at 1,000 effective 1 June 2026, version 2 at 1,200 effective 1 July 2026, invoice date 15 July 2026 at 1,000, quantity 100, invoice-date policy, no grandfathering. Potential 20,000. `MISSED_CONTRACT_PRICE_INCREASE`.

`GOLD-AUD-003`: a verified transaction override authorizes 1,100 against a normal 1,150. The invoice is 1,100 inside that scope. Unauthorized leakage is zero.

`GOLD-AUD-005`: the same July invoice stays compliant at 1,000 when the 25 June confirmation locked the order-date price.

A version is not applied before its effective date. A retroactive amendment is not approved. `HIS12-T011` expects `UserError` on submit or approval of a backdated amendment, and the earlier approved price remains.

The tests compared `Decimal` results. The class, full, upgrade, and fresh logs recorded 0 failed after the fixture dates were separated from the initial version's effective date.
