# Golden financial fixtures

Currencies in the tests are Q8A, Q8B, and Q8C. The labels USD and INR in the prompt are the source and company currencies of the example. They were not activated.

A normalized price is not a leakage amount. The 5 percent discount and the 760 extended leakage are not computed.

| Fixture | Input | Expected | Test |
| --- | --- | --- | --- |
| GOLD-FX-001 | 100 at fixed 84 | 8400 | FX08-T002 |
| GOLD-FX-002 | 8400, inverse of fixed 84 | 100 | FX08-T003 |
| GOLD-FX-003 | 120 per box of 10, fixed 84, comparison unit is the piece | 12 then 1008 | PREC08-T004, INT08-T004 |
| GOLD-FX-004 | Fixed 83 while a market row is 84 | 8300, evidence `contract_fixed_rate` | FX08-T011 |
| GOLD-FX-005 | 1150 in the company currency | 1150, no rate | FX08-T001 |
| GOLD-FX-006 | Historical exact date with no row | `MISSING_HISTORICAL_FX`, price false | FX08-T009 |
| GOLD-FX-007 | Company A row 84, Company B clause, no Company B row | `MISSING_HISTORICAL_FX` | SEC08-T002 |
| GOLD-FX-008 | `fx_source` payment_date | `PAYMENT_FX_NOT_CONTRACT_LEAKAGE` | FX08-T018 |
| GOLD-TAX-001 | Included 1180 at 18 percent | Net 1000, tax 180 | TAX08-T002 |
| GOLD-TAX-002 | Excluded 1000 and included 1180 at 18 percent | Both nets 1000, difference 0 | TAX08-T003, TAX08-T004 |
| GOLD-TAX-003 | Excluded 1000 and included 1062 at 18 percent, quantity 100 | Unit nets 1000 and 900. Signed extended difference 10000. No finding. | `test_tax08_gold_tax_003_included_gross_net_and_extended_difference` |
| GOLD-TAX-004 | Group, fixed, division, tax-on-tax, or complex | `UNSUPPORTED_TAX_STRUCTURE` | TAX08-T006 through T010 and T013 |
| GOLD-ROUND-001 | 1.005 times 100, extended stage | Unit 1.005, extended 100.50. Per-unit stage is 1.01 and 101. | PREC08-T005, T006, T016 |
| GOLD-ROUND-002 | Q8C rounding 1.0, price 100.6, per unit | 101. Not 0.01 rounding. | PREC08-T002 |
| GOLD-TOL-001 | Raw 0.02, argument 0.05 | Raw 0.02 kept. Not classified within tolerance. DEC-08 is open. | PREC08-T011 |
| GOLD-TOL-002 | No approved tolerance | Raw difference kept. No invented threshold. | PREC08-T010 |
| GOLD-INT-001 | 120 per box, 10 pieces, rate 84, requested discount 0.05 | Pre-discount 1008. Not 957.60. `discount_applied` false. | INT08-T008 |

Wrong-direction conversion of 100 at 84 is rejected by FX08-T004: the result is greater than 100 and equal to 8400.

Future rate rows are not a fallback (FX08-T010). Exact date does not borrow another day (FX08-T007). Prior mode keeps the earlier row date (FX08-T008).
