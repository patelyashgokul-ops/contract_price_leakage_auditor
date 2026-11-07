# 11 — DEV-05 progress

Date: 2026-10-28.

**DEV-05 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**DEV-05 BUSINESS ACCEPTANCE: PENDING**

Approved prices live on contract versions. The header is still not an approved price. Ready for review is not approval. Formal business acceptance was not granted. No reviewer signed this phase. Open decisions stay open. Owners remain UNASSIGNED.

`BLOCKER_LICENSE_DECISION_REQUIRED` remains. Manifest license `Other proprietary` is a loader guard. It is not OPL-1 and not permission to distribute. Author and website are empty. That blocker limits commercial packaging. It did not stop the version models.

Invoice matching, leakage findings, recovery, waivers, and accounting entries were not implemented. DEV-06 was not started.

## Prerequisites

| Item | Result |
| --- | --- |
| DEV-00 | Reviewed. Implementation PARTIAL. Business acceptance PENDING. |
| DEV-01 | Reviewed. Direct depends remain `base` and `product`. |
| DEV-02 | Reviewed. Eight group XML IDs preserved. |
| DEV-03 | Reviewed. `cpla.company.policy` preserved. `operationally_approved` stays false. |
| DEV-04 | Reviewed. Header states remain `draft`, `ready_for_review`, `cancelled`. Green DEV-04 evidence stays the 2026-10-28 fresh `-i`: 0 failed, 0 errors of 155 tests. |

No prerequisite made the foundation unsafe to extend. The license decision is still open.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| DEV05-01 Review DEV-00 through DEV-04 | COMPLETED | This file and `docs/app04/step04/`. |
| DEV05-02 Inspect Contract Master | COMPLETED | Header, lines, and evidence kept. `audit_authoritative` is true only when an approved version exists. |
| DEV05-03 Versioning architecture | COMPLETED | `01_versioning_architecture.md`. Full snapshot. No mixed deltas. |
| DEV05-04 Contract Version model | COMPLETED | `cpla.customer.contract.version`. |
| DEV05-05 Version line snapshot | COMPLETED | `cpla.customer.contract.version.line`. |
| DEV05-06 Stable numbering | COMPLETED | Unique `(contract_id, version_number)` plus a row lock. Cancelled numbers are not reused. |
| DEV05-07 Initial approval lifecycle | COMPLETED | `approve_initial`. Header state does not become approved. |
| DEV05-08 Approval authority | COMPLETED | Independent Contract Manager, or Finance Manager on an existing ready version. No amount ceiling was invented. |
| DEV05-09 Self-approval prevention | COMPLETED | SEC05-T003. |
| DEV05-10 Approved snapshot creation | COMPLETED | One savepoint writes the version, lines, supersession, and events. |
| DEV05-11 Immutable approved data | COMPLETED | HIS-T006 through HIS-T009. |
| DEV05-12 Draft amendment creation | COMPLETED | `create_amendment`. Source row is not edited. |
| DEV05-13 Effective-dated amendments | COMPLETED | `effective_from` inclusive. Approval datetime is separate. |
| DEV05-14 Supersession | COMPLETED | `supersedes_version_id` on the new approved version. |
| DEV05-15 Future-dated effectiveness | COMPLETED | Derived status `scheduled`. No cron. |
| DEV05-16 Retroactive governance | COMPLETED | Approval blocked. `retroactivity_policy` is `not_authorized`. |
| DEV05-17 Stale draft detection | COMPLETED | AMD-T018 and CONTRACT-V009. No automatic rebase. |
| DEV05-18 Conflict handling | COMPLETED | HIS-T015. No price is selected. |
| DEV05-19 Version comparison | COMPLETED | `compare_with` and the transient wizard. |
| DEV05-20 Approval event history | COMPLETED | `cpla.customer.contract.version.event`. No write or unlink for ordinary users. |
| DEV05-21 Version evidence | COMPLETED | Linked files and checksum. Bytes of an approved file are not replaced. |
| DEV05-22 ACLs and record rules | COMPLETED | `07_version_security_matrix.md`. |
| DEV05-23 Multi-company | COMPLETED | SEC05-T006 through SEC05-T008 and SEC05-T012. |
| DEV05-24 Views and menus | COMPLETED | `views/contract_version_views.xml`. |
| DEV05-25 Automated version tests | COMPLETED | `tests/test_contract_version.py`. |
| DEV05-26 Negative and security tests | COMPLETED | SEC05-T001 through SEC05-T015. |
| DEV05-27 Concurrency tests | COMPLETED | CON05-T001 through CON05-T003 use threads and separate cursors. |
| DEV05-28 Isolated suite | COMPLETED | `09_automated_test_results.md`. Runs 4 and 5: 0 failed, 0 errors of 242. |
| DEV05-29 Fresh installation | COMPLETED | `cpla_dev05_20261028`, 2026-10-28 07:34:08 UTC. |
| DEV05-30 Upgrade from DEV-04 | COMPLETED | Passing `-u` on `cpla_dev04_20261028`, 07:31:22 UTC. See the migration limit in file 10. |
| DEV05-31 Prior-phase regression | COMPLETED | Same 242 includes the earlier post-tests. |
| DEV05-32 Traceability | COMPLETED | Matrix below. |
| DEV05-33 Documentation | COMPLETED | `docs/app04/step05/01` through `12`. |
| DEV05-34 DEV-06 handoff | COMPLETED | `12_dev06_handoff.md`. DEV-06 was not started. |
| DEV05-35 Final progress report | COMPLETED | This file and the DEV-05 session report. |

## Requirements traceability

Applicability and precedence are PLANNED_FOR_DEV06 even where a version chronology test passed.

| ID | Status |
| --- | --- |
| P0-A Contract governance | PARTIALLY_IMPLEMENTED. Version approval, amendments, and supersession are tested. Operational policy approval and invoice use are not. |
| P0-G Security and historical evidence | TESTED_PASS for version ACL, company rules, immutable snapshots, and append-only events. Not a legal archive. |
| P0-J Release readiness | PARTIALLY_IMPLEMENTED. Fresh install and upgrade tests passed. Business acceptance is pending. License remains blocked. Release stays NO-GO. |
| CPL-C01 Company-specific contract | TESTED_PASS. Version company follows the parent. Cross-company approval is denied. |
| CPL-C03 Effective dates | TESTED_PASS for inclusive commercial dates, scheduled status, and invalid ranges. Pricing-date selection is PLANNED_FOR_DEV06. |
| CPL-C04 Approved historical versions | TESTED_PASS. Full snapshots remain after later amendments. |
| CPL-C05 Amendments and supersession | TESTED_PASS for draft copy, stale source, and append-only supersession. |
| CPL-C06 Contract approval | PARTIALLY_IMPLEMENTED. Independent Contract Manager or Finance Manager can approve. Amount ceilings are not configured. The company policy is not operationally approved. |
| CPL-C08 Pricing-date policy reference | PARTIALLY_IMPLEMENTED. Approval stores `policy_id` and frozen candidate strings. DEC-01 is not applied to invoices. |
| CPL-C09 Contract conflict readiness | PARTIALLY_IMPLEMENTED. Same effective start and a later approved start are rejected. No price is chosen. Precedence is PLANNED_FOR_DEV06. |
| CPL-C10 Contract evidence | TESTED_PASS for version-linked files, company access, and correction events. A checksum is not legal proof. |
| FIN-01 Correct historical contract version | PARTIALLY_IMPLEMENTED. The approved snapshot is stored and protected. Choosing it for a transaction is PLANNED_FOR_DEV06. |
| FIN-02 Correct pricing-date policy | PARTIALLY_IMPLEMENTED. The candidate string is snapshotted. GOLD-FIN-002 applicability is NOT_EXECUTED. |
| FIN-08 No false financial conclusion | TESTED_PASS as a refusal. Comparison sets `is_recovered_cash` false. GOLD-FIN-001 and GOLD-REC-001 were not calculated. |
| FIN-11 Preserve original and revised evidence | TESTED_PASS. Prior snapshots and events stay. Approved file bytes are not replaced. |
| SEC-01 Company isolation | TESTED_PASS. SEC05-T006, SEC05-T007, SEC05-T008, SEC05-T012. |
| SEC-02 Contract confidentiality | TESTED_PASS. Owner rule plus company rule. SEC05-T006 and SEC05-T009. |
| SEC-03 Role separation | TESTED_PASS. SEC05-T002, SEC05-T004, SEC05-T005, SEC05-T013. |
| SEC-04 Approval authority | TESTED_PASS for the documented independent-approver rule. No numeric matrix exists. |
| SEC-05 Self-approval prevention | TESTED_PASS. SEC05-T003. |
| SEC-06 Evidence security | TESTED_PASS. SEC05-T009. No public attachment link. |
| SEC-09 Unauthorized modification prevention | TESTED_PASS. HIS-T006 through HIS-T009 and SEC05-T011. |
| SEC-10 Historical approval trace | TESTED_PASS. HIS-T010. Events cannot be edited or deleted by ordinary users. |

## Odoo 18 and Odoo 20

Not converted. Compatibility notes are in `01_versioning_architecture.md`. Odoo 19 remains the master.

## Blockers that remain open

- License: `BLOCKER_LICENSE_DECISION_REQUIRED`.
- Business acceptance of this phase: pending. No sign-off.
- DEC-01 through DEC-08, DEC-11, and DEC-12: unresolved. Owners UNASSIGNED.
- Amount thresholds: `not_configured`.
- Retroactive amendments: `not_authorized`.
- Zero price, open end, and packaging as a price unit: still blocked at approval.
- Physical deletion of drafts: not authorized. Version unlink is refused except during module uninstall.

## Critical defects

None of the twenty release-blocking defects is open on the run 4 and run 5 evidence. The serialization error in CON05-T001 aborts the losing transaction and leaves one approved version. It does not create a second snapshot.
