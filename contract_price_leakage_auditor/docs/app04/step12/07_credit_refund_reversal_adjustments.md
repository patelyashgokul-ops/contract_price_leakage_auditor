# Credit notes, refunds, and reversals

Posted customer credit notes are adjustment evidence. They are not new positive sales and they are not collected cash.

The mapper classifies the credit. DEV-12 does not reclassify every line type on its own.

| Mapper class | Audit effect |
| --- | --- |
| `QUANTITY_RETURN` | Trusted link to the original line. Eligible quantity on that line is reduced by the returned quantity. The credit row itself has no second monetary exposure. |
| `FULL_REVERSAL` | Eligible quantity on the original line becomes zero. The former current finding is superseded or marked no longer current. The original audit result remains. |
| `PRICE_ADJUSTMENT` | `REFUND_REASSESSMENT_REQUIRED`. The amount is not converted into returned units and is not subtracted from leakage. |
| `TAX_ONLY_CORRECTION` | Excluded or review. Not a product return. |
| `UNKNOWN_CREDIT_REASON` or a missing origin | `REFUND_REASSESSMENT_REQUIRED`. No exposure change. |

Customer invoices are processed before credit notes. When a verified return or full reversal is mapped, `_reprice_origin` recalculates the linked original line in the same company. That is the linked document, not a scan of every historical invoice. If the origin is outside the run's date filter, that linked reprice still runs.

## Quantity return

`GOLD-AUD-010`: 100 pieces, approved 1,150, invoice 1,100, verified return of 20, no retiering. Current exposure is 4,000. The credit's gross amount is not subtracted.

Retiering runs only when the selected line has tiers, `return_policy` is `net_quantity`, and the eligible quantity is still positive. `returned_quantity` is not sent for `order_tier_lock`, for a line with no tiers, or when the eligible quantity is zero. `REF12-T011` uses an invoice-line basis and expects the net quantity to select the lower tier. `REF12-T012` keeps the original tier under `order_tier_lock`.

## Full reversal and replacement

`GOLD-AUD-011`: a full verified reversal leaves current exposure at zero. The historical finding remains searchable as superseded.

`GOLD-AUD-012`: the reversed invoice is replaced by a posted invoice at the approved price. Current leakage is zero. No payment is created. Corrected billing is not collected cash.

A credit is not linked to an invoice merely because the amounts match. The mapper uses `reversed_entry_id` and a unique product and UoM match.

An existing corrective customer invoice is classified only when its source is verified. DEV-12 does not create a debit note.

## Repeated processing

A second audit of the same verified return updates the current finding or supersedes the previous current row. It does not subtract the return twice. `REF12-T013` and `IDM12-T014` assert one current potential amount.
