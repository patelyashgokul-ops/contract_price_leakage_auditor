# 12 — DEV-07 progress

Date: 2026-10-28.

Implementation: `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING`.

Business acceptance: `PENDING`. Formal sign-off was not given.

License: `BLOCKER_LICENSE_DECISION_REQUIRED`. Manifest value remains `Other proprietary`.

`operationally_approved` remains false. DEC-04 is not decided. The company quantity candidate is not the contract rule. A normalized unit price is not a leakage amount. Invoice comparison, FX, tax, discounts, recovery, and waivers are not in this phase.

## Traceability

| ID | State |
| --- | --- |
| P0-A Historical contract terms | TESTED_PASS. Approved snapshots stay immutable. New tiers are version lines, not a second contract. |
| P0-B Quantity tiers and UoM | TESTED_PASS for full-volume selection and snapshotted conversion. Graduated pricing and cumulative volume are explicit unsupported outcomes. |
| P0-G Security and historical evidence | TESTED_PASS for tier ACL, company rules, and frozen factors. |
| P0-J Automated tests | TESTED_PASS for this phase. 0 failed of 464 on the upgrade rerun and the fresh install. Not release readiness. |
| CPL-C02 Product and variant scope | TESTED_PASS. Mixed products are not aggregated. |
| CPL-C04 Approved historical versions | TESTED_PASS. V1 without tiers stays a standalone price. Amendments do not rewrite it. |
| CPL-C07 Quantity-based pricing | TESTED_PASS for full-volume. Graduated is unsupported. |
| CPL-P02 Variant pricing | TESTED_PASS. Exact variant only. |
| CPL-P03 Quantity tier selection | TESTED_PASS. Boundaries, gaps, and overlaps. |
| CPL-P05 UoM conversion | TESTED_PASS for snapshotted factors. A compatible unit without a snapshot is missing historical evidence, not a live conversion. |
| CPL-P08 Monetary precision | DEFERRED_TO_DEV08. Exact decimals are preserved. Final rounding is not implemented. |
| CPL-P09 Missing or conflicting evidence | TESTED_PASS. No fabricated price. |
| CPL-P10 Pricing calculation evidence | TESTED_PASS as resolver fields. No stored audit finding. |
| FIN-01 Historical terms | TESTED_PASS. |
| FIN-04 UoM normalization | TESTED_PASS. |
| FIN-07 Precision | PARTIALLY_IMPLEMENTED. Intermediate exactness is tested. Final money rounding is DEFERRED_TO_DEV08. |
| FIN-08 No unsupported conclusion | TESTED_PASS. `leakage_amount` is false. |
| FIN-09 No duplicate exposure | PARTIALLY_IMPLEMENTED. Billed quantity is not added to the qualifying quantity. Document allocation is DEFERRED_TO_DEV11_OR_DEV12. |
| FIN-10 Return and credit readiness | PARTIALLY_IMPLEMENTED. Explicit lock and net retier are tested. Credit-note document linkage is DEFERRED_TO_DEV11_OR_DEV12. |
| FIN-11 Historical evidence | TESTED_PASS. Live packaging changes do not rewrite approved factors. |
| SEC-01 Company isolation | TESTED_PASS. |
| SEC-02 Confidential pricing | TESTED_PASS. |
| SEC-06 Evidence access | TESTED_PASS. Diagnostics do not return a rate to an unauthorized user. |
| SEC-09 Unauthorized modification | TESTED_PASS. |

GOLD-FIN-001, GOLD-FIN-003, and GOLD-REC-001 were not run. GOLD-FIN-002 remains grandfathering selection only.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| DEV07-01 Review DEV-00 through DEV-06 | COMPLETED | Addon, version snapshots, and the resolver were present. DEV-06 had passed 366 tests. |
| DEV07-02 Inspect versions and resolver | COMPLETED | Line price, UoM block on the line, and `pending_dev07` were the starting point. |
| DEV07-03 Verify Odoo 19 UoM and packaging | COMPLETED | `uom.uom` relative factor and factor. `product.template.uom_ids`. No `product.packaging` in the test registry. |
| DEV07-04 Review quantity-policy decisions | COMPLETED | DEC-04 stays open. The line basis is explicit. The company candidate is unused. |
| DEV07-05 Finalize tier architecture | COMPLETED | `01_quantity_tier_architecture.md`. |
| DEV07-06 Draft quantity tiers | COMPLETED | TIER07-T001. |
| DEV07-07 Approved tier snapshots | COMPLETED | TIER07-T009, T010, T011. |
| DEV07-08 Range validation | COMPLETED | TIER07-T002 through T006 and T015. |
| DEV07-09 Tier boundaries | COMPLETED | QTY07-T001 through T007. QT-REF-001. |
| DEV07-10 Full-volume logic | COMPLETED | TIER07-T007. Graduated is TIER07-T008. |
| DEV07-11 Qualification input | COMPLETED | Resolver fields and `cpla.pricing.quantity.evaluate`. |
| DEV07-12 Sales-order qualification | COMPLETED | PAR07-T001, T002. QT-REF-002. |
| DEV07-13 Invoice-line qualification | COMPLETED | PAR07-T003. QT-REF-003. One line, not an invoice aggregate. |
| DEV07-14 Delivery quantity | COMPLETED | PAR07-T008. Caller-supplied quantity only. No picking is created. |
| DEV07-15 Partial-invoice context | COMPLETED | PAR07-T004. QT-REF-009. Service context only. |
| DEV07-16 Returns and credit notes | COMPLETED | PAR07-T010, T011, T012. Document linkage is deferred. |
| DEV07-17 Cumulative volume boundary | COMPLETED | PAR07-T013 returns unsupported. No engine. |
| DEV07-18 UoM conversion service | COMPLETED | UOM07-T001, T002, T008, T009, T010, T016. |
| DEV07-19 Product packaging conversion | COMPLETED | UOM07-T003 through T007 and T015. |
| DEV07-20 Historical factors | COMPLETED | UOM07-T011, T012, T013. HIS07-T003, T004, T007. |
| DEV07-21 Normalized unit price | COMPLETED | Exact decimal strings on a tier match. |
| DEV07-22 DEV-06 integration | COMPLETED | `_apply_quantity`. Conflicts stay conflicts. REG07-T006. |
| DEV07-23 Explainable statuses | COMPLETED | Quantity failures clear the price. Match text says this is not an invoice audit. |
| DEV07-24 Views | COMPLETED | Quantity Tiers page and wizard fields. Evidence is `get_view`. |
| DEV07-25 ACLs and rules | COMPLETED | Five tier access rows and three record rules. |
| DEV07-26 Multi-company validation | COMPLETED | SEC07-T004, T005, T010. |
| DEV07-27 Tier and boundary tests | COMPLETED | TIER07 and QTY07. |
| DEV07-28 UoM and packaging tests | COMPLETED | UOM07. |
| DEV07-29 Partial invoice and return tests | COMPLETED | PAR07. Document integration deferred. |
| DEV07-30 Historical integrity tests | COMPLETED | HIS07. |
| DEV07-31 Security tests | COMPLETED | SEC07. |
| DEV07-32 Execute tests | COMPLETED | Run 1 failed 4 of 464. Runs 2 and 3 passed 464. |
| DEV07-33 Installation and update | COMPLETED | `-u` on `cpla_dev06_20261028`. `-i` on `cpla_dev07_20261028`. |
| DEV07-34 Prior-phase regression | COMPLETED | The previous tests are inside the same 464. |
| DEV07-35 Performance review | COMPLETED | Suite timings are recorded. One lookup stayed under 5 seconds. Exact lookup time was not logged. No result cache. |
| DEV07-36 Requirements traceability | COMPLETED | This file. |
| DEV07-37 Documentation | COMPLETED | `docs/app04/step07/` files 01–13. |
| DEV07-38 DEV-08 handoff | COMPLETED | `13_dev08_handoff.md`. DEV-08 was not started. |
| DEV07-39 Final progress report | COMPLETED | This file and the phase tracker. |

## Defects found and fixed before the green runs

| Item | Evidence | Action |
| --- | --- | --- |
| Zero quantity classified as missing | Run 1, QTY07-T008 | `_missing` no longer treats 0 as false. |
| Retroactive draft blocked at submit, not only at approval | Run 1, HIS07-T006 | Test expects the existing earlier-authority block. |
| Reviewer write reached the snapshot message | Run 1, SEC07-T003 | Line `write` checks access first. |
| Zeroed factors were still read from cache | Run 1, UOM07-T013 | Test invalidates after `_write_multi`. |

No open critical defect from the DEV-07 list remains in the green runs. A second-worker overlap race was not executed. That is a test limit, not a passed concurrency proof.
