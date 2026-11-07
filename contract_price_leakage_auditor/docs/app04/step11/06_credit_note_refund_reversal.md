# Credit notes, refunds, and reversals

A posted `out_refund` is `ELIGIBLE_CUSTOMER_CREDIT` with commercial sign `-1`. A positive line quantity does not make it a second sale. A draft credit is `DRAFT_EXCLUDED` and is not a posted adjustment.

`reversed_entry_id` is document-level. The mapper does not treat it as proof of one original invoice line.

Origin line matching, only inside the reversed document and only when that document is the same company and readable:

1. Commercial lines with the same product and the same unit.
2. If several match, one line with the same quantity may be used.
3. Otherwise `REVERSAL_LINE_AMBIGUOUS` and `CREDIT_ORIGIN_REVIEW_REQUIRED`. No original invoice is chosen by product search across the database.

Credit class when a unique origin line is found:

| Class | Rule |
| --- | --- |
| `FULL_REVERSAL` | Same effective unit, same quantity, and the origin document has one commercial line. |
| `QUANTITY_RETURN` | Same effective unit and a smaller quantity. |
| `PRICE_ADJUSTMENT` | Same quantity and a different effective unit. Returned quantity is empty. Commercial quantity is `0`. `quantity_trusted` is false. |
| `UNKNOWN_CREDIT_REASON` | Quantity above the origin, or both price and quantity differ. |
| `TAX_ONLY_CORRECTION` | A tax display line on a customer credit. Not a physical return. |

`COMMERCIAL_CREDIT` exists on the selection and forces `quantity_trusted` false. The automatic classifier does not assign it.

A credit with no reversed document and no sales lines is `REFUND_ORIGIN_MISSING`. A reversed document in another company is `WRONG_COMPANY_SOURCE`.

A full reversal keeps the original posted invoice. Net trusted quantity for that sales line can be zero when both the invoice allocation and the credit allocation are quantity-trusted. A later replacement invoice is a separate document. Similar amounts or narration do not link it.

No recovery journal, payment, or credit note is created by mapping. Repeated mapping of an unchanged credit does not apply the refund twice.

Amount-only credits cannot use quantity zero. Odoo recomputes a falsy product quantity to 1. A price difference at the same quantity is the supported classification, and no returned units are invented.
