# DEV-13 progress

Date: 2026-11-05. Version: `19.0.1.11.0`. Technical status: `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING`. Business acceptance: `PENDING`. Release: `NO-GO`. License: `BLOCKER_LICENSE_DECISION_REQUIRED`.

Potential leakage is not finance-validated, billed, or collected. Submitting a case is not financial approval. Closing a case is not recovered cash. DEV-14 was not started.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| DEV13-01 Review DEV-00 through DEV-12 | COMPLETED | Finding model, identity, and groups were read before case code. |
| DEV13-02 Inspect findings | COMPLETED | `cpla.leakage.finding` stays the amount source. |
| DEV13-03 Mail and activity | COMPLETED | `mail.thread` and `mail.activity.mixin` through `product`. `mail` is not a direct depend. |
| DEV13-04 Grouping and ownership | COMPLETED | No approved auto-group. One current finding, one case, unless an explicit basis is passed. No auto owner. |
| DEV13-05 Architecture | COMPLETED | `01_case_management_architecture.md`. |
| DEV13-06 Case model | COMPLETED | `cpla.leakage.case`. |
| DEV13-07 Sequence | COMPLETED | `CPL-CASE/%(year)s/` padding 5. Existing references are not regenerated. |
| DEV13-08 Finding relationship | COMPLETED | `cpla.leakage.case.membership`. |
| DEV13-09 Current membership | COMPLETED | Partial unique index on current `finding_id`. |
| DEV13-10 Idempotent create | COMPLETED | `create_from_findings`. Repeat returns the same case. |
| DEV13-11 Grouping | COMPLETED | `same_sales_order`, `same_contract_version`, `same_invoice`, `explicit_same_issue`. |
| DEV13-12 Merge and split | COMPLETED | GRP13 merge and split. Source case is kept. |
| DEV13-13 Lifecycle | COMPLETED | Seven states in `03_investigation_workflow.md`. |
| DEV13-14 Transition authority | COMPLETED | Python checks. WF13. |
| DEV13-15 Assignment | COMPLETED | Manager assigns an eligible investigator. |
| DEV13-16 Assignment history | COMPLETED | `assigned` and `owner_changed` events. |
| DEV13-17 Priority and severity | COMPLETED | Empty until a manager sets them. No amount threshold. |
| DEV13-18 Root cause | COMPLETED | Investigator conclusion with an explanation. Not copied from the detector. |
| DEV13-19 Checklist | COMPLETED | 24 questions. Required set depends on case type. |
| DEV13-20 Evidence status | COMPLETED | Six statuses. Received is not verified. |
| DEV13-21 Attachments | COMPLETED | No public flag, token, or unlink on case evidence. |
| DEV13-22 Chatter | COMPLETED | Internal followers only. Customer subscribe is denied. |
| DEV13-23 Activities | COMPLETED | Explicit user and date. `automated` false. Completing one does not close the case. |
| DEV13-24 Exception queues | COMPLETED | Nonmonetary categories. Blank amount. |
| DEV13-25 Exposure | COMPLETED | Sum of unique current comparable finding texts. |
| DEV13-26 Revision awareness | COMPLETED | `source_reassessment_required`. Accept copies the successor text. |
| DEV13-27 Event history | COMPLETED | `cpla.leakage.case.event`. Direct write is rejected. |
| DEV13-28 Finance readiness | COMPLETED | Submit only from `under_investigation` after the checklist. |
| DEV13-29 Submission snapshot | COMPLETED | `cpla.leakage.case.submission`. |
| DEV13-30 Return for rework | COMPLETED | Finance reviewer, not the submitter. Snapshot kept. |
| DEV13-31 Close and reopen | COMPLETED | Reason required. Finding remains. Merged case cannot reopen. |
| DEV13-32 SLA readiness | COMPLETED | Optional target date. Calendar age. No default deadline. No cron. |
| DEV13-33 Views | COMPLETED | `views/leakage_case_views.xml`. |
| DEV13-34 Smart buttons | COMPLETED | Counts only. Invoice open still needs Accounting read. |
| DEV13-35 ACLs and rules | COMPLETED | `11_case_security_matrix.md`. |
| DEV13-36 Multi-company | COMPLETED | SEC13 company A and company B. |
| DEV13-37 RPC and attachments | COMPLETED | SEC13 and EVD13. No `sudo(` in `leakage_case.py`. |
| DEV13-38 Creation tests | COMPLETED | CASE13. |
| DEV13-39 Grouping tests | COMPLETED | GRP13. |
| DEV13-40 Workflow tests | COMPLETED | WF13. |
| DEV13-41 Ownership tests | COMPLETED | OWN13. |
| DEV13-42 Evidence tests | COMPLETED | EVD13. |
| DEV13-43 Financial tests | COMPLETED | FIN13. |
| DEV13-44 Security tests | COMPLETED | SEC13. |
| DEV13-45 Concurrency tests | COMPLETED | CON13 in one transaction. Two workers: `NOT_EXECUTED`. |
| DEV13-46 Isolated tests | COMPLETED | Class 0 failed of 20. Full tag 0 failed of 898. |
| DEV13-47 Fresh installation | COMPLETED | `cpla_dev13_fresh_20261105`, 0 failed of 898. |
| DEV13-48 Upgrade from DEV-12 | COMPLETED | `cpla_dev12_20261028` from `19.0.1.10.0`, 0 failed of 898. |
| DEV13-49 Prior-phase regression | COMPLETED | Same 898 on full, upgrade, and fresh. |
| DEV13-50 Performance | COMPLETED | Measured times in `15_performance_and_concurrency.md`. No threshold. |
| DEV13-51 Traceability | COMPLETED | Table below. |
| DEV13-52 Documentation | COMPLETED | This directory, 17 files. |
| DEV13-53 DEV-14 handoff | COMPLETED | `17_dev14_handoff.md`. DEV-14 not implemented. |
| DEV13-54 Evidence report | COMPLETED | This file and `13_automated_test_results.md`. |

## Traceability

| Item | Status |
| --- | --- |
| P0-C, P0-D, P0-G, P0-J | IMPLEMENTED and TESTED_PASS for the case scope in the green logs |
| CPL-CASE-001–CPL-CASE-016 | TESTED_PASS |
| FIN-08 | TESTED_PASS. Unknown exposure stays blank. |
| FIN-09 | TESTED_PASS. One current membership per finding. |
| FIN-10 | TESTED_PASS for the refresh flag and the retained snapshot. The reassessment engine is DEFERRED_TO_DEV14. |
| FIN-11 | TESTED_PASS. Events, reviewed exposure, and submission rows stay. |
| FIN-12 | TESTED_PASS. No finance-validated field is stored. |
| FIN-13 | TESTED_PASS that a case writes no recovery and no collected cash. A recovery ledger is DEFERRED_TO_DEV16. |
| FIN-16 | TESTED_PASS for the case sum of current finding texts. |
| SEC-01, SEC-02, SEC-03, SEC-06, SEC-09, SEC-10, SEC-12 | TESTED_PASS |
| SEC-04, SEC-05 | TESTED_PASS for submit versus return. Finance validation authority is DEFERRED_TO_DEV15. |
| Finance validation | DEFERRED_TO_DEV15 |
| Historical reassessment engine | DEFERRED_TO_DEV14 |
| Recovery billing and cash | DEFERRED_TO_DEV16 |
| Recurring escalation cron | DEFERRED_TO_DEV18 |
| Odoo 18 and Odoo 20 | Not tested |

## Not claimed

- Business sign-off.
- Two database workers.
- An INR company currency. The tests copy amount text and do not assert the currency name.
- A before-and-after count of audit rows that already existed on `cpla_dev12_20261028`.
- Production readiness of APP 04.
