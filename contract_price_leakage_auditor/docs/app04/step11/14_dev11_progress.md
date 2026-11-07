# DEV-11 progress

Addon `contract_price_leakage_auditor` version `19.0.1.9.0`. Odoo 19.0 Community. Business acceptance is pending. License remains `BLOCKER_LICENSE_DECISION_REQUIRED`. Release remains NO-GO. DEV-12 was not started.

Implementation status: `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING` after the green runs in `12_installation_regression.md`. Formal business acceptance still needs a reviewer.

The first class run failed: 2 failed, 4 errors of 102 tests. The rerun, the full tag, the upgrade of `cpla_dev10_20261028`, and the fresh install each passed. The full and fresh result lines are 0 failed, 0 errors of 778 tests.

## Task status

| Task | Status | Evidence |
| --- | --- | --- |
| DEV11-01 | COMPLETED | DEV-00 through DEV-10 models remain. Prior tests pass inside the 778. |
| DEV11-02 | COMPLETED | Native `sale_line_ids` and `invoice_lines` exercised by MAP11. |
| DEV11-03 | COMPLETED | `out_invoice`, `out_refund`, draft, cancel, vendor bill, vendor refund. |
| DEV11-04 | COMPLETED | Manual invoices stay in review. No automatic contract match. |
| DEV11-05 | COMPLETED | `cpla.invoice.source` and `cpla.invoice.source.map`. |
| DEV11-06 | COMPLETED | Posted customer invoice eligibility. |
| DEV11-07 | COMPLETED | Commercial, display, tax, receivable, down payment, and zero-price classes. |
| DEV11-08 | COMPLETED | Native sales-line mapping. Origin text is candidate only. |
| DEV11-09 | COMPLETED | Multiple native lines stay in allocation review. |
| DEV11-10 | COMPLETED | Documentary split must sum exactly. No proportional guess. |
| DEV11-11 | COMPLETED | 200 + 200 + 100 net 500. |
| DEV11-12 | COMPLETED | Manual and candidate classification. |
| DEV11-13 | COMPLETED | Lock linked. Confirmed price kept apart from the invoice price. |
| DEV11-14 | COMPLETED | Order-date snapshot keeps the lock version. |
| DEV11-15 | COMPLETED | Invoice-date snapshot calls the resolver with the invoice date. |
| DEV11-16 | COMPLETED | Grandfather flag only from an order-confirmation lock. |
| DEV11-17 | COMPLETED | Unit price, discount, and effective unit stored. |
| DEV11-18 | COMPLETED | Currency, UoM, tax basis, subtotal, and total stored. |
| DEV11-19 | COMPLETED | Delivery-date policy returns review. Stock was not added. |
| DEV11-20 | COMPLETED | Customer credit is sign `-1`. |
| DEV11-21 | COMPLETED | Document reversal stored. Line match is separate. |
| DEV11-22 | COMPLETED | Full net zero and partial net 80 when the line match is unique. |
| DEV11-23 | COMPLETED | Price adjustment does not invent returned units. |
| DEV11-24 | COMPLETED | Cancelled documents excluded. Replacement invoice stays separate. |
| DEV11-25 | COMPLETED | Sign comes from `move_type`, not from quantity. |
| DEV11-26 | COMPLETED | Exception codes and review statuses. |
| DEV11-27 | COMPLETED | Finance-manager documentary verification. |
| DEV11-28 | COMPLETED | Fingerprint and a new revision on change. |
| DEV11-29 | COMPLETED | Unique current pointer. Two sessions were not run. |
| DEV11-30 | COMPLETED | List, form, wizard, and invoice smart button. |
| DEV11-31 | COMPLETED | ACLs and global company rules. |
| DEV11-32 | COMPLETED | Cross-company sales line rejected. |
| DEV11-33 | COMPLETED | INV11 and MAP11 passed. |
| DEV11-34 | COMPLETED | PAR11 passed. |
| DEV11-35 | COMPLETED | REF11 passed. |
| DEV11-36 | COMPLETED | FIN11 passed. No leakage finding. |
| DEV11-37 | COMPLETED | SEC11 passed. |
| DEV11-38 | COMPLETED | IDM11 passed inside one transaction. |
| DEV11-39 | COMPLETED | Class rerun 0 failed of 102. Full tag 0 failed of 778. |
| DEV11-40 | COMPLETED | Fresh `-i` of `cpla_dev11_fresh_20261028`, 0 failed of 778. |
| DEV11-41 | COMPLETED | Upgrade `-u` of `cpla_dev10_20261028`, 0 failed of 778. |
| DEV11-42 | COMPLETED | Prior-phase tests inside those 778. |
| DEV11-43 | COMPLETED | `13_performance_findings.md`. No large-dataset benchmark. |
| DEV11-44 | COMPLETED | Traceability in this file. The invoice audit engine is not implemented. |
| DEV11-45 | COMPLETED | `docs/app04/step11/` files 01 through 15. |
| DEV11-46 | COMPLETED | `15_dev12_handoff.md`. |
| DEV11-47 | COMPLETED | This file and the final report. |

## Deferred

| Work | Status |
| --- | --- |
| Posted-invoice price comparison and leakage findings | `DEFERRED_TO_DEV12`. Not started. |
| Finance validation, recovery, waivers, debit notes, payments | Not started. |
| Invoice-audit cron and executive dashboard | Not started. |
| Two-session mapping race | Not executed. |
| 5,000-line and larger benchmarks | Not executed. |
| Odoo 18 and Odoo 20 conversion | Not started. |
| Automatic contract match for a manual invoice | Not approved. Remains review. |

## Requirements touched

P0-A, P0-B, P0-C, P0-G, and P0-J are advanced for source identification only.

CPL-A01 posted-customer scope is classified. CPL-A02 historical version evidence is stored when a lock or an invoice-date resolver match exists. CPL-A03 and CPL-A04 detection are not implemented. CPL-A05 stores the invoice discount and does not judge it. CPL-A06 leaves missing and ambiguous sources in review. CPL-A07 classifies credits and does not call them recovered cash. CPL-A08 keeps a prior mapping row when the fingerprint changes. CPL-A09 does not create a finding identity. CPL-A10 company rules passed. CPL-A11 stores the source fields listed in `07_historical_price_context.md`. CPL-A12 has no scheduled audit.

FIN-01 through FIN-06 are inputs on the allocation and the map. FIN-08 still forbids a leakage conclusion. FIN-09 is the current-row uniqueness. FIN-10 is the credit classification. FIN-11 is the revision row. No cash recovery is claimed.

SEC-01, SEC-02, SEC-06, SEC-08, and SEC-09 hold for the new records. Background processes are not implemented. The mapper is company-filtered so a later scheduled caller can use the same methods.

## Known limits

- A price-adjustment credit can stay `SOURCE_VERIFIED` while `audit_ready` and `quantity_trusted` are false. Returned quantity is empty.
- `COMMERCIAL_CREDIT` is not assigned by the automatic classifier.
- `MAPPING_FAILED` is not written when a batch document raises.
- A mapper can clear `is_current` without creating a replacement. That user cannot set `SOURCE_VERIFIED` through `write`.
- Fingerprint evaluation searches locks per line.
- Direct invoices are not matched to a contract automatically.
- Delivery-date pricing is review-only.
