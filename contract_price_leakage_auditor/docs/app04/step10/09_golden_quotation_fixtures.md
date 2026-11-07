# Golden quotation fixtures

Dates in the tests are relative to `context_today`. The environment date for these runs was 2026-10-28. June 25 and July 1 were not hardcoded.

| Fixture | Setup | Result in the green runs |
| --- | --- | --- |
| QUOTE-REF-001 | Approved 1,150, quote 1,150, quantity 500 | `COMPLIANT`. Confirmation reaches `sale` in block mode when the confirmer can read the contract. |
| QUOTE-REF-002 | Approved 1,150, quote 1,100, quantity 500 | Exposure `25000`. Block mode raises `UserError`. No lock. |
| QUOTE-REF-003 | Same prices with an approved override at 1,100 for 500 | `COMPLIANT_AUTHORIZED_OVERRIDE`. Confirmation allowed. |
| QUOTE-REF-004 | Request submitted, not approved | `APPROVAL_PENDING`. `approval_required` blocks. |
| QUOTE-REF-005 | Request rejected | `APPROVAL_REJECTED`. Block mode does not confirm. |
| QUOTE-REF-006 | Approved 1,100, then price 1,050 | Old approval does not authorize. Status is below price. |
| QUOTE-REF-007 | Approved quantity 100, line quantity 1,000 | `REVIEW_REQUIRED`, reason `override_quantity_not_covered`. |
| QUOTE-REF-008 | `price_unit` 1,200, discount 5, baseline 1,140 | Effective `1140`. `COMPLIANT`. |
| QUOTE-REF-009 | Two approved contracts | `CONTRACT_CONFLICT`. No selected price. |
| QUOTE-REF-010 | No contract for that customer | `CONTRACT_NOT_FOUND`. No invented price. |
| QUOTE-REF-011 | Underpriced quote, mode `warning` | Confirms. Lock status `BELOW_APPROVED_PRICE`. No approval. |
| QUOTE-REF-012 | Order-confirmation snapshot, later higher version | Lock keeps the confirmation version. |
| QUOTE-REF-013 | Invoice-date snapshot | `order_date_lock_candidate` false. |
| QUOTE-REF-014 | Company B approval on a Company A line | `UserError`. |
| QUOTE-REF-015 | Compliant quotation | Standard confirmation reaches `sale`. One lock. |
| QUOTE-REF-016 | Approved 1,150, quote 1,200 | `PRICE_ABOVE_APPROVED_RATE`. Exposure empty. Confirm allowed. |
| QUOTE-REF-017 | Price change after confirmation | Original amounts kept. `revalidation_required` true. |
| QUOTE-REF-018 | Second store of the same line | Same lock id. Count stays 1. |
| QUOTE-REF-019 | Compliant line, underpriced line, note | Note is `NOT_APPLICABLE`. Order status is below price. Exposure `25000`. |
| QUOTE-REF-020 | USD per box, INR per piece, factor path | Compared value is not the raw box price `50`. |

Preventive exposure in these fixtures is not recovered cash. No recovery document and no `account.move` from this module is created.
