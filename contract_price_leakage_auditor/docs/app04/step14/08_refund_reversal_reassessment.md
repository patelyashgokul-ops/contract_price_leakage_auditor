# Refund and reversal reassessment

Date: 2026-11-05.

Credit triggers require a posted customer credit note in the same company, mapped to the finding's invoice line. The credit class comes from `cpla.invoice.source.map`. DEV-14 does not invent a class.

| Trigger | Required class | If it does not match |
| --- | --- | --- |
| `verified_quantity_return` | `QUANTITY_RETURN` and `quantity_trusted` | Evidence review. "No returned quantity was invented." |
| `full_invoice_reversal` | `FULL_REVERSAL` and `quantity_trusted` | Evidence review. Exposure is not forced to zero. |
| `price_adjustment_credit` | `PRICE_ADJUSTMENT` | Evidence review. Eligible quantity must stay equal to the original eligible quantity or the monetary credit is not accepted as a quantity change. |
| `replacement_invoice` | A separate posted customer invoice plus a trusted full reversal of the original line | Evidence review. "Exposure was not forced to zero." |

## Quantity return

A posted credit of 20 on an original quantity of 100, with no retier, proposes eligible 80 and exposure 4000 from an original 5000. Delta -1000. The credit is not collected cash. Processing the same source again hits the open-request unique index or the unchanged-fingerprint refusal. It does not subtract 20 twice.

## Full reversal and replacement

A verified full reversal proposes 0. Acceptance clears the current potential finding and keeps 0 on the result. The original result stays 5000. The reversed invoice and a replacement are not both current exposure: the replacement path audits the reversal and the replacement, and the engine's identity rules keep one current reading per identity. A replacement without a verified reversal is not forced to zero.

## Amount-only credit

An amount-only customer credit stays `PRICE_ADJUSTMENT`. The eligible quantity is not reduced. If the engine's eligible quantity differs from the original, the request is evidence review and the quantity change is not accepted.

## Company boundary

A credit note whose company differs from the reassessment is not a trusted source. The gate says the credit note belongs to another company.
