# Partial invoice allocation

These quantities stay separate on `cpla.invoice.source.allocation`.

| Field | Meaning |
| --- | --- |
| `source_quantity_exact` on the map | Quantity stored on the invoice line. |
| `commercial_quantity_exact` | That quantity with the document sign. Customer credit is negative. |
| `allocated_quantity_exact` | Quantity attributed to one sales line, in the invoice unit. |
| `signed_quantity_exact` | Allocated quantity with the document sign. |
| `converted_sale_quantity_exact` | The same allocation converted to the sales-line unit with `cpla.pricing.quantity.convert_quantity`. The text is canonical, so `1.0` is stored as `1`. |
| `ordered_quantity_exact` | `product_uom_qty` on the sales line. It is copied onto every invoice allocation and is not added again as billed quantity. |
| `delivered_quantity_exact` | `qty_delivered` at mapping time. It does not choose a pricing date. |
| `odoo_invoiced_quantity_exact` | Odoo `qty_invoiced` at mapping time. |
| `returned_quantity_exact` | Returned units only when the credit is a verified quantity return or full reversal. |

`net_quantity_for_sale_line` sums `signed_quantity_exact` on current allocations whose map has `quantity_trusted`. Review rows and reassessment rows are omitted. The method does not map invoices by itself. Callers map the posted invoices first.

A verified documentary split must name each sales line once, use quantities in the invoice unit, and sum exactly to the invoice line quantity. If native links already exist, the documentary lines must be a subset of those links. A 300-piece line linked to two sales lines is not split 150/150.

Partial invoices of 200, 200, and 100 against one 500-piece order keep three allocations. Their trusted signed sum is 500. The ordered quantity on each allocation remains 500.
