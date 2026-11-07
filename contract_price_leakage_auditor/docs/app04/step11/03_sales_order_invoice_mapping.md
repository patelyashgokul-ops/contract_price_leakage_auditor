# Sales order and invoice mapping

The preferred source is `account.move.line.sale_line_ids`. Free text in `invoice_origin` is never enough to mark a source verified.

| Provenance | Meaning |
| --- | --- |
| `NATIVE_RELATION_VERIFIED` | The sales lines are the native many-to-many links, and company, customer, and product checks passed. |
| `DOCUMENTARY_LINK_VERIFIED` | A finance manager stored an exact quantity split. The native `sale_line_ids` field is not rewritten. |
| `CANDIDATE_ONLY` | `invoice_origin` text matched a possible order name. No allocation is stored. |
| `UNLINKED_MANUAL_INVOICE` | No native sales line and no usable origin text. |
| `CONFLICTING_SOURCE_RELATIONS` | A linked sales line failed company, product, or customer checks. |
| `NOT_APPLICABLE` | The document or line is outside commercial mapping. |

Customer match uses `commercial_partner_id` on both the invoice and the sales order. Company must be the same. Product variant must be the same.

One accepted native sales line allocates the invoice line quantity, not the ordered quantity. Two or more accepted native sales lines produce `SOURCE_ALLOCATION_REVIEW_REQUIRED`, codes `MULTIPLE_SALES_SOURCES` and `ALLOCATION_NOT_VERIFIED`, and no stored split. If those lines carry different confirmed contract versions, `CONTRACT_VERSION_CONFLICT` is added and no version is chosen for the whole line.

A candidate search looks up `sale.order` by exact name and company, limit 2. It stores `candidate_order_name` only when one order matches the commercial partner. It does not create a sales order and it does not set `audit_ready`.

`audit_ready` is true only for `SOURCE_VERIFIED` or `MULTI_SOURCE_VERIFIED` when there is no blocking exception and `quantity_trusted` is true.
