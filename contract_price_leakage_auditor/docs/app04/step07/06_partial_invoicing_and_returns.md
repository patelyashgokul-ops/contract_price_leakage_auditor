# 06 — Partial invoicing and returns

Date: 2026-10-28.

## Implemented now

The service accepts an explicit request. It does not create or read `sale.order`, `account.move`, or stock pickings. Linking those documents is `DEFERRED_TO_DEV11_OR_DEV12`. The tests are service tests. They are not integration tests against posted invoices.

| Request field | Use |
| --- | --- |
| `quantity` | Bare qualifying quantity, only when it does not contradict the line basis. |
| `order_quantity` | Sales-order qualification. |
| `invoice_quantity` | One invoice line. |
| `delivery_quantity` | Delivered quantity supplied by the caller. |
| `billed_quantity` | Echo only. |
| `returned_quantity` | Applied only under an explicit return policy. |
| `document_type = credit_note` | Never a new positive sale. |
| `qualification_basis` | Must be empty or equal to the line. It does not override the line. |
| `allocation_unverified` | Review, no sum. |
| `invoice_line_quantities` / `delivery_quantities` | A list longer than one is review. Not summed. |
| `source_reference` | Ignored for the rate. |

## Order lock

Confirmed quantity 500, basis `sales_order`, open tier 1100. Allocations 100, or 200 + 200 + 100, each return qualified quantity 500, billed quantity equal to that slice, and unit price 1100. The 500 is not billed five times. `unit_price` is not `1100 * 500`.

## Invoice basis

Order 500 and invoice line 100, basis `invoice_line`, select 1150. The order quantity is present and is not used.

## Delivery

Order 500 and delivered 300, basis `delivery`, select 1150. The service does not assume the order quantity was delivered. It does not create a picking.

## Returns

Order-tier lock keeps 500 and price 1100 after a return of 20. Net retier uses 480 and price 1150 only when the line says `net_quantity`. An unconfigured return policy returns review and no price.

The net eligible financial exposure on a credit note is not calculated here. The credit note itself is not priced as a sale.

## Qualification key

Company, contract version, customer, product variant, and the source quantity the line names. No family, basket, or variant rollup is approved. Two products on one order stay two qualifications.
