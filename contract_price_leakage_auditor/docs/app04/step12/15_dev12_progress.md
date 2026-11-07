# DEV-12 progress

Date: 2026-10-28. Version: `19.0.1.10.0`. Technical status: `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING`. Business acceptance: `PENDING`. Release: `NO-GO`. License: `BLOCKER_LICENSE_DECISION_REQUIRED`.

Potential leakage is not finance-validated, billed, or collected. DEV-13 was not started.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| DEV12-01 Review DEV-00 through DEV-11 | COMPLETED | DEV-11 closed as acceptance pending. This step reuses its mapper. |
| DEV12-02 Verify Odoo 19 source fields | COMPLETED | Posted `out_invoice` / `out_refund`, `price_unit`, `discount`, `price_include_override`, `sale_line_ids`. Tests posted real moves. |
| DEV12-03 Review audit policies | COMPLETED | Manual invoices, delivery dates, and numeric tolerance stay review. |
| DEV12-04 Finalize architecture | COMPLETED | `01_invoice_audit_architecture.md`. |
| DEV12-05 Audit run model | COMPLETED | `cpla.invoice.audit.run`. |
| DEV12-06 Audit result model | COMPLETED | `cpla.invoice.audit.result`. |
| DEV12-07 Finding model | COMPLETED | `cpla.leakage.finding`. |
| DEV12-08 Input and output contracts | COMPLETED | Fingerprint, snapshot, and waterfall fields. |
| DEV12-09 Posted invoice eligibility | COMPLETED | ELG12-T001–T005, T010–T012. |
| DEV12-10 Commercial line filter | COMPLETED | ELG12-T006–T009. |
| DEV12-11 Source mapping | COMPLETED | INT12 and PAR12. |
| DEV12-12 Historical contract resolution | COMPLETED | HIS12. |
| DEV12-13 Tiers and UoM | COMPLETED | FIN12-T007, PAR12-T008, REF12-T011. |
| DEV12-14 FX, tax, rounding | COMPLETED | FIN12-T006, T008, T013–T017. |
| DEV12-15 Authorized discounts | COMPLETED | FIN12-T001, T003, T010. |
| DEV12-16 Actual unit price | COMPLETED | FIN12-T008, T009. |
| DEV12-17 Signed difference | COMPLETED | FIN12-T018. |
| DEV12-18 Concession separation | COMPLETED | FIN12-T001, T019. |
| DEV12-19 Missed increase | COMPLETED | GOLD-AUD-004 and GOLD-AUD-005. |
| DEV12-20 Unauthorized discount | COMPLETED | GOLD-AUD-001. |
| DEV12-21 Overbilling | COMPLETED | GOLD-AUD-015. |
| DEV12-22 Tolerance | COMPLETED | No numeric tolerance. FIN12-T012 keeps the raw difference. |
| DEV12-23 Partial invoices | COMPLETED | GOLD-AUD-009. |
| DEV12-24 Quantity returns | COMPLETED | GOLD-AUD-010. |
| DEV12-25 Price-only credits | COMPLETED | GOLD-AUD-017. |
| DEV12-26 Reversal and replacement | COMPLETED | GOLD-AUD-011 and GOLD-AUD-012. |
| DEV12-27 Canonical identity | COMPLETED | `08_finding_uniqueness_idempotency.md`. |
| DEV12-28 Duplicate prevention | COMPLETED | GOLD-AUD-016. IDM12-T001. |
| DEV12-29 Fingerprints and revisions | COMPLETED | IDM12-T008–T011. |
| DEV12-30 Evidence snapshots | COMPLETED | INT12-T011. |
| DEV12-31 Review statuses | COMPLETED | HIS12-T007–T009, T013. |
| DEV12-32 On-demand execution | COMPLETED | `action_run`. |
| DEV12-33 Batch processing | COMPLETED | Cap 200, savepoint per move. |
| DEV12-34 Concurrency and retry | COMPLETED | IDM12-T005–T007. Two workers not run. |
| DEV12-35 Views and actions | COMPLETED | `views/invoice_audit_views.xml`. |
| DEV12-36 Role security | COMPLETED | SEC12. |
| DEV12-37 Multi-company | COMPLETED | SEC12-T001–T004, T012, T015. |
| DEV12-38 Eligibility tests | COMPLETED | ELG12. |
| DEV12-39 Historical matching tests | COMPLETED | HIS12. |
| DEV12-40 Golden financial tests | COMPLETED | FIN12 and GOLD-AUD-001–020. |
| DEV12-41 Partial-invoice tests | COMPLETED | PAR12. |
| DEV12-42 Credit tests | COMPLETED | REF12. |
| DEV12-43 Duplicate tests | COMPLETED | IDM12. |
| DEV12-44 Security tests | COMPLETED | SEC12. |
| DEV12-45 Concurrency and failure tests | COMPLETED | IDM12-T005–T007. Not two processes. |
| DEV12-46 Isolated automated tests | COMPLETED | Class, full, upgrade, fresh. See `12_automated_test_results.md`. |
| DEV12-47 Fresh installation | COMPLETED | `cpla_dev12_fresh_20261028`, 0 failed of 878. |
| DEV12-48 Upgrade from DEV-11 | COMPLETED | `cpla_dev11_20261028`, 0 failed of 878. |
| DEV12-49 DEV-01 through DEV-11 regression | COMPLETED | Same 878 on full, upgrade, and fresh. |
| DEV12-50 Indexes and performance | COMPLETED | Indexes listed. Only the x10 timing was measured. |
| DEV12-51 Traceability | COMPLETED | Table below. |
| DEV12-52 Documentation | COMPLETED | This directory. |
| DEV12-53 DEV-13 handoff | COMPLETED | `16_dev13_handoff.md`. DEV-13 not implemented. |
| DEV12-54 Evidence report | COMPLETED | This file and the test log. |

## Traceability

| Item | Status |
| --- | --- |
| P0-A, P0-B, P0-C, P0-G, P0-H, P0-J | IMPLEMENTED and TESTED_PASS for the audit scope in the green logs |
| CPL-A01–A12 | TESTED_PASS |
| FIN-01–FIN-12, FIN-16 | TESTED_PASS for potential leakage. FIN-12 separates potential from validated by not storing validated amounts. |
| FIN-13 | DEFERRED_TO_DEV17. No recovery is created, so double recovery is not calculated. |
| SEC-01, SEC-02, SEC-03, SEC-04, SEC-06, SEC-08, SEC-09, SEC-10, SEC-12 | TESTED_PASS |
| Finance validation | DEFERRED_TO_DEV15 |
| Investigation case, assignment, SLA | DEFERRED_TO_DEV13 and DEFERRED_TO_DEV14 |
| Recovery billing and cash | DEFERRED_TO_DEV17 |
| Recurring audit cron | DEFERRED_TO_DEV18 |
| Odoo 18 and Odoo 20 | Not tested |

## Defects closed before acceptance logs

The class1 log was 9 failed and 11 errors. The blank cutoff identity, the fixture effective dates, the override owner, and the assertions that did not match Odoo 19 were fixed. Class2 and the three full tags are the acceptance logs.

## Open risks

- Two-worker audits were not run.
- Large histories were not timed.
- Manual invoices, delivery-date pricing, and numeric tolerance remain review by design.
- Business acceptance is pending. The license decision is still open.
- The cutoff help string was edited after the green logs. Behavior was already tested.

## Files added

`models/invoice_audit.py`, `data/audit_sequence.xml`, `security/invoice_audit_rules.xml`, `views/invoice_audit_views.xml`, `tests/test_invoice_audit.py`, and this `docs/app04/step12/` set.

## Files updated

`__manifest__.py`, `models/__init__.py`, `security/ir.model.access.csv`, `tests/__init__.py`, version pins in the nine prior test modules, `tests/test_security_foundation.py`, `tests/test_foundation_smoke.py`, and the older assertions that forbade any `cpla.leakage` model. Those phases still create zero finding rows. README, `docs/README.md`, and `DEVELOPMENT_PROGRESS.md` were updated after the green logs.
