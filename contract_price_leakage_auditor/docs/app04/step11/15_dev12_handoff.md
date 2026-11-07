# DEV-12 handoff

DEV-12 was not started. This file is the input contract only.

## Mapper

Technical name: `cpla.invoice.source`.

Entry points: `map_move(move)`, `map_line(line)`, `map_moves(moves)`, `document_class(move)`, `line_class(line)`, `commercial_sign(move)`, `net_quantity_for_sale_line(sale_line)`.

Persistent current evidence: `cpla.invoice.source.map` where `is_current` is true. Allocations: `cpla.invoice.source.allocation`.

Use a row for a later price comparison only when `audit_ready` is true. Other rows are review evidence.

## Eligible documents

- Posted `account.move` with `move_type = out_invoice` and `state = posted`: `ELIGIBLE_CUSTOMER_INVOICE`, commercial sign `+1`.
- Posted `out_refund`: `ELIGIBLE_CUSTOMER_CREDIT`, commercial sign `-1`.
- Draft, cancel, vendor bill, vendor refund, receipt, and miscellaneous entry are excluded.

## Commercial lines

Compare `COMMERCIAL_PRODUCT`, `COMMERCIAL_SERVICE`, and `ZERO_PRICE_COMMERCIAL` only when `audit_ready` is true. A zero price is evidence, not an error. Display, tax, receivable, rounding, early-payment, global discount, down payment, shipping, COGS, and technical lines are `UNSUPPORTED_LINE_TYPE`.

## Sales relation

Read `account.move.line.sale_line_ids` and `sale.order.line.invoice_lines`. Do not treat `invoice_origin` or `candidate_order_name` as verified. Do not create a sales order.

One native sales line: allocation quantity is the invoice line quantity. Several native sales lines without a documentary split: `SOURCE_ALLOCATION_REVIEW_REQUIRED`. Do not split proportionally.

## Historical context

- `allocation.price_lock_id` is the DEV-10 lock.
- `confirmed_version_id` is the lock version.
- `version_id` is the applicable version for the pricing-date rule.
- `pricing_date_policy_snapshot` is copied from the lock.
- `order_date_lock_candidate` is true only for a valid order-confirmation lock.
- `applicable_pricing_date` is the lock date or the invoice date. It is empty when the policy is delivery, unconfigured, or not authoritative.
- `approved_unit_price_exact` is the historical approved unit. `confirmed_unit_price_exact` is the locked sales price. `price_unit_exact`, `discount_exact`, and `effective_unit_exact` are the posted invoice.

Do not replace a missing value with the current product price, the current contract version, or today's date.

## Refunds

Net quantity is `net_quantity_for_sale_line` over current trusted allocations. Price adjustments contribute no returned quantity. Ambiguous reversal lines are not allocated. A credit is not recovered cash. `is_recovered_cash` is false.

## Idempotency

Identity is the current map for one invoice line, plus zero or more allocations. Repeat mapping of an unchanged fingerprint returns that row. A material change opens a new revision and clears trust until a finance manager accepts it.

## Security

Company rules and the access table are in `09_multi_company_security.md`. Do not use unrestricted `sudo()` to read another company's invoices or contracts.

## Open decisions for DEV-12

- Manual invoices are review-only. Contract-only auditing is not approved.
- Delivery-date pricing has no stock allocation.
- `COMMERCIAL_CREDIT` is unused by the automatic classifier.
- Two-session mapping was not executed.
- Large invoice volumes were not benchmarked.
- Odoo 18 and Odoo 20 were not converted.

## Not in this handoff

No leakage finding, no tolerance decision, no finance case, no recovery claim, no waiver, no debit note, no payment, and no cron.
