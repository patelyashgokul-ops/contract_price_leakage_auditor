# Golden source fixtures

These cases ran inside `TestDev11InvoiceSource` on Odoo 19.0. The class result after the fixes is 0 failed, 0 errors of 102 tests. The first class run failed and is recorded in `11_automated_test_results.md`.

| Fixture | Expected | Actual |
| --- | --- | --- |
| SRC-REF-001 | Native sales line linked to the invoice line. | `sale_line_ids` and the allocation match the order line. |
| SRC-REF-002 | 500 pieces invoiced 200 + 200 + 100. | Three allocations, trusted net `500`. Ordered quantity stays `500` on each row. |
| SRC-REF-003 | 300 pieces split 200 + 100. | Finance-manager documentary split stores `200` and `100`. Status `MULTI_SOURCE_VERIFIED`. |
| SRC-REF-004 | Two native lines and no quantities. | `SOURCE_ALLOCATION_REVIEW_REQUIRED`. No `150` row. |
| SRC-REF-005 | Manual invoice. | `UNLINKED_MANUAL_INVOICE`. No sales order created. |
| SRC-REF-006 | Order confirmed on V1 before V2. | Allocation version stays V1. Approved unit `1000`. |
| SRC-REF-007 | Invoice-date policy. | Applicable version is the later version. Order-date lock flag is false. |
| SRC-REF-008 | Confirmed 1150, invoice 1100. | Both prices stored. `leakage_amount` false. |
| SRC-REF-009 | Full credit of 100. | `FULL_REVERSAL`. Net trusted quantity `0`. Original invoice remains. |
| SRC-REF-010 | Credit of 20 from 100. | Net trusted quantity `80`. |
| SRC-REF-011 | Amount credit without a returned quantity. | `PRICE_ADJUSTMENT`. Returned quantity empty. Commercial quantity `0`. |
| SRC-REF-012 | Invoice A, credit, invoice B. | Three documents. Reversed original is not a second positive exposure. |
| SRC-REF-013 | Credit with no original. | `CREDIT_ORIGIN_REVIEW_REQUIRED`. |
| SRC-REF-014 | Company A invoice and Company B sales line. | `WRONG_COMPANY_SOURCE`. Documentary cross-company call raises `UserError`. |
| SRC-REF-015 | Draft invoice. | `DRAFT_EXCLUDED`. |
| SRC-REF-016 | Vendor bill. | `NON_CUSTOMER_DOCUMENT`. |
| SRC-REF-017 | Same invoice mapped twice. | One current row. |
| SRC-REF-018 | Product, section, note, shipping-style display, tax. | Product stays commercial. Display and tax lines have no contract. |
| SRC-REF-019 | Order in a 10-piece box, invoice in pieces. | Allocated `10`, converted sale quantity `1`. |
| SRC-REF-020 | Delivery-date policy and no delivery split. | `DELIVERY_DATE_NOT_ALLOCATED`. No date invented. |

Prices in the tests are contract fixtures, not an approved commercial tariff.
