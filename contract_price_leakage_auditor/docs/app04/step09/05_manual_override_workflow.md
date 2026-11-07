# Manual override workflow

A price typed below the approved adjusted contract price is not an approved special price. DEV-09 stores the authorization request and evaluates it. DEV-10 will enforce it on a quotation. This phase does not write `sale.order.line`.

## Request

Model `cpla.discount.approval` with `request_kind` = `transaction_override`.

The draft records company, customer, contract version, product variant, currency, unit, proposed price, quantity, `sale_reference`, `sale_line_reference`, effective dates, reason, and evidence reference. There is no `sale.order` foreign key because `sale` is not a dependency. The two references are exact strings.

On approval the server stores:

- `baseline_unit_price_exact` from the evaluator, with contractual concessions already applied
- `exposure_exact` and `exposure_currency_id`
- `snapshot_json` and `limit_snapshot_json`
- approver and `approved_at`

## When it changes the adjusted price

The evaluator applies an approved override only when the request supplies both `sale_reference` and `sale_line_reference` and both match the approval. A different order keeps the contractual price. A quantity above `quantity_exact` returns `DISCOUNT_EVIDENCE_REVIEW_REQUIRED` from the override step. If a contractual concession is already authoritative, that contractual price stands.

A rejected, cancelled, expired, or still-submitted override does not replace an approved contractual price. When the only authority would have been the override, the status is `DISCOUNT_APPROVAL_REJECTED`, `DISCOUNT_APPROVAL_PENDING`, or `DISCOUNT_EXPIRED`, and `approved_adjusted_unit_price_exact` is false.

An approved override returns `APPROVED_OVERRIDE_APPLICABLE`.

## Executed exposure

Special price 1,150. Proposed 1,100. Quantity 500.

`baseline_unit_price_exact` = `1150`. `exposure_exact` = `25000`. The gross 100 per unit is not the amount submitted for this approval. Fifty of that gap is already the contractual concession.

Repeated evaluation of the same line does not create another approval. The executed count of `cpla.discount.approval` was unchanged after two evaluations. The version line `price_unit` stayed 1,200. No `account.move` was created by the evaluation.

## Boundary for DEV-10

DEV-10 may call `cpla.discount.evaluator.evaluate` and may open `cpla.discount.approval` for the current order line. It must not treat a native line discount as approval. It must not copy one line’s override onto another line. Confirmation blocking, warning text, and any write to the sales line belong to that phase and are not implemented here.
