# Invoice eligibility policy

A document is classified from its current `move_type` and `state`.

| Class | Rule |
| --- | --- |
| `ELIGIBLE_CUSTOMER_INVOICE` | Posted `out_invoice`. |
| `ELIGIBLE_CUSTOMER_CREDIT` | Posted `out_refund`. It is not a new positive sale. |
| `DRAFT_EXCLUDED` | Any document whose state is not `posted` and not `cancel`. |
| `CANCELLED_EXCLUDED` | State `cancel`. Status `REVERSED_OR_CANCELLED`. |
| `NON_CUSTOMER_DOCUMENT` | `in_invoice` and `in_refund`, including posted vendor bills and vendor refunds. |
| `UNSUPPORTED_DOCUMENT_TYPE` | Other types, including `out_receipt`, `in_receipt`, and `entry`. |

Draft and cancelled documents are not posted audit sources. Vendor bills are not customer sales.

## Line classes

Product lines are `COMMERCIAL_PRODUCT`. Service products are `COMMERCIAL_SERVICE`. A product line with unit price zero is `ZERO_PRICE_COMMERCIAL`. That zero is not treated as a technical error and it is not given an invented contract price.

Excluded classes, status `UNSUPPORTED_LINE_TYPE`, with no source allocation:

- `EXCLUDED_DISPLAY` for section, subsection, and note.
- `EXCLUDED_TAX`.
- `EXCLUDED_RECEIVABLE` for `payment_term`.
- `EXCLUDED_ROUNDING`.
- `EXCLUDED_EARLY_PAYMENT_DISCOUNT` for `epd`.
- `EXCLUDED_GLOBAL_DISCOUNT` for display type `discount`. The discount is not spread across product lines.
- `EXCLUDED_DOWN_PAYMENT` when `is_downpayment` is set.
- `EXCLUDED_SHIPPING` only when a linked sales line has `is_delivery` and that field exists. The delivery addon is not installed here, so ordinary product lines are not guessed to be shipping.
- `EXCLUDED_COGS` and `EXCLUDED_TECHNICAL`.

A tax line on a customer credit is `TAX_ONLY_CORRECTION`. It is not a physical return.
