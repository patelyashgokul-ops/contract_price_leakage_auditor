# 09 — Golden financial scenarios

Date: 2026-10-28.

Amounts are company currency. The figures match the wholesale examples. INR was not activated. No leakage amount is computed. A normalized price is not an invoice difference.

The schedule used by the boundary cases is `[1, 100)` at 1200, `[100, 500)` at 1150, and `[500, open)` at 1100. The line’s standalone price in those tests is 1000 and is not the selected tier rate.

| ID | Setup | Expected | Result |
| --- | --- | --- | --- |
| QT-REF-001 | Boundaries 99, 100, 499, 500 | 1200, 1150, 1150, 1100 | Passed |
| QT-REF-002 | Order 500, five billed slices of 100, basis sales order | Each slice 1100. Billed quantity 100. | Passed |
| QT-REF-003 | Order 500, invoice line 100, basis invoice line | 1150 | Passed |
| QT-REF-004 | 2400 per box of 12, compare per piece | 200 per piece | Passed |
| QT-REF-005 | Product A box 12, product B box 24, both priced 2400 per box | 200 and 100 per piece | Passed |
| QT-REF-006 | Approved factor 12, live factor later 10 | Still 200 per piece | Passed |
| QT-REF-007 | Quantity 99.999 | 1200, not 1150 | Passed |
| QT-REF-008 | Piece contract, kilogram comparison, no product conversion | `INCOMPATIBLE_UOM`, no price | Passed |
| QT-REF-009 | Billed 200, 200, and 100 against order 500 | Qualified 500 each time. Billed slices sum to 500. Unit price is not 1100 × 500. | Passed |
| QT-REF-010 | Return 20, policy order-tier lock | Qualifying quantity stays 500. Price 1100. | Passed |
| QT-REF-011 | Return 20, policy net quantity | Qualifying quantity 480. Price 1150. | Passed |
| QT-REF-012 | Sales-order basis, only invoice quantity supplied | `MISSING_QUALIFYING_QUANTITY`, no price | Passed |
| QT-REF-013 | Ranges `[1, 200)` and `[100, 500)` | `ValidationError` | Passed |
| QT-REF-014 | Gap `[1, 100)` then `[200, 500)`, quantity 150 | Approval blocked. No price. | Passed |
| QT-REF-015 | Bearing A 300 and Bearing B 200, no basket rule | Each selects 1150. Not combined to 500. | Passed |

QT-REF-004, 005, 006, 007, 008, 009, 010, 011, 013, and 014 call the matching UOM, QTY, PAR, or TIER test. They are separate test methods, so each ran.

These are not GOLD-FIN-001, GOLD-FIN-003, or GOLD-REC-001. Those invoice and recovery oracles were not run.
