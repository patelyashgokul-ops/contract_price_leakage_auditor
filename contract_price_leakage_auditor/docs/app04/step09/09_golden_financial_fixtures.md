# Golden financial fixtures

Amounts below are the assertions that passed in `tests/test_discount_authority.py`. The company currency is the test company currency. INR and USD are not activated. Foreign money uses `Q9A` and, where a third currency is required, `Q9B`. Quantity 500 and the 1,200 / 1,150 / 1,100 example use that company currency.

`leakage_amount`, `is_recovered_cash`, and `leakage_finding_created` stayed false in every case that asserts them. No leakage finding model exists.

| Fixture | Expected and actual |
| --- | --- |
| GOLD-DISC-001 | Special price 1,150. Status `SPECIAL_PRICE_APPLICABLE`. Pre-discount 1,200. Concession per unit 50. Authorized extension 25,000. Gross extension 50,000. Potential unauthorized extension 25,000. Indicator `UNAUTHORIZED_DISCOUNT_INDICATOR`. |
| GOLD-DISC-002 | 5 percent of 1,200 = 1,140. Status `AUTHORIZED_PRICE_RESOLVED`. |
| GOLD-DISC-003 | Fixed 50 off 1,200 = 1,150. Concession per unit 50. |
| GOLD-DISC-004 | Sequential 5 percent then 3 percent = `1105.8`. Two calculation stages. |
| GOLD-DISC-005 | Additive 5 percent + 3 percent = 1,104. |
| GOLD-DISC-006 | Exclusive special 1,150 plus a 5 percent row = 1,150. One selected concession. |
| GOLD-DISC-007 | 10 percent then 50 = 1,030. |
| GOLD-DISC-008 | 50 then 10 percent = 1,035. |
| GOLD-DISC-009 | 5 `Q9A` per box of 10, fixed FX 84. Factor ratio 10. Pre-discount 8,400. Concession 42. Adjusted 8,358. |
| GOLD-DISC-010 | End date yesterday. Pricing date today. Status `DISCOUNT_EXPIRED`. No adjusted price. |
| GOLD-DISC-011 | Start date five days ahead. Today is `DISCOUNT_NOT_YET_EFFECTIVE`. The start date itself is 1,140. |
| GOLD-DISC-012 | Other customer. Status `DISCOUNT_SCOPE_MISMATCH`. No adjusted price. |
| GOLD-DISC-013 | Other variant. Status `DISCOUNT_SCOPE_MISMATCH`. The trace does not contain `1150`. |
| GOLD-DISC-014 | Baseline stored as `1150`. Exposure stored as `25000`. Approver is the finance user. |
| GOLD-DISC-015 | Rejected override. Status `DISCOUNT_APPROVAL_REJECTED`. No adjusted price. |
| GOLD-DISC-016 | `entered_discount_percent` without a concession is `DISCOUNT_EVIDENCE_REVIEW_REQUIRED`, reason `entered_discount_without_approval`. `discount_rate` alone leaves the price at 1,200 and `discount_applied` false. |
| GOLD-DISC-017 | Retroactive 5 percent approved after the cutoff. As-known price 1,200. Current price 1,140. `retroactive_granted` true. |
| GOLD-DISC-018 | Two exclusive prices with rank 0: `DISCOUNT_AUTHORITY_CONFLICT`, no price. Unique ranks: rank 1 at 1,180 wins over rank 2 at 1,100. |
| GOLD-DISC-019 | Discount after tier: base 1,100, adjusted 1,045. Exclusive tier: 1,100 and `discount_applied` false. Missing tier policy: `DISCOUNT_STACKING_REVIEW_REQUIRED`. |
| GOLD-DISC-020 | Special price 1,150 with an actual price of 1,100. No `account.move` created. `cpla.leakage.finding` is absent. No sale order with reference `SO-020`. |

GOLD-INT-001 from DEV-08 remains the pre-discount result. INT08-T008 still starts, and the next test starts after it, in both 610-test logs. A request key `discount_rate` does not apply 5 percent to that price.

The 5 percent example in this phase is 1,200 × 0.95 = 1,140. It is a different scenario from a 5 percent reduction of the DEV-08 amount 1,008.
