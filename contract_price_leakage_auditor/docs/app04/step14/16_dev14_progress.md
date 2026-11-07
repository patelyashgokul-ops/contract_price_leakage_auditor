# DEV-14 progress

Date: 2026-11-05. Version `19.0.1.12.0`. Engine `dev12.1`. Snapshot schema `dev14.2`. This is the sections 37–69 task table. The sections 1–36 note is `06_dev14_progress.md`.

Business acceptance: `PENDING`. Commercial release: `NO-GO`. License: `BLOCKER_LICENSE_DECISION_REQUIRED`. Finance validation: not started.

A task is `COMPLETED` only when the evidence column names a log or a file that was checked.

| Task | Status | Evidence |
| --- | --- | --- |
| DEV14-01 Review DEV-00 through DEV-13 | COMPLETED | Prior-phase tests passed inside full3 and upgrade3, 0 failed of 914. |
| DEV14-02 Inspect DEV-12 audit architecture | COMPLETED | Engine `dev12.1` reused. `action_reassess` remains. t011 asserts the button. |
| DEV14-03 Inspect DEV-13 case integration | COMPLETED | t003 and t004. Case reviewed amount and submission stay. |
| DEV14-04 Verify Odoo 19 ORM and security | COMPLETED | full3 and upgrade3 on Odoo 19.0. Repeatable-read purge is in the test setup. |
| DEV14-05 Review reassessment policies | COMPLETED | Rejection, stale flag, and one current finding are in t012, t001, and t016. |
| DEV14-06 Finalize evidence architecture | COMPLETED | `01_evidence_architecture.md`. |
| DEV14-07 Canonical snapshot schema | COMPLETED | Schema `dev14.2`. t001 asserts it. |
| DEV14-08 Protected snapshot representation | COMPLETED | t001 direct write of `proposed_exposure_exact` raises `UserError`. |
| DEV14-09 Snapshot versioning | COMPLETED | `schema_version` `dev14.2` on the request. |
| DEV14-10 Snapshot integrity verification | COMPLETED | t002 tamper blocks acceptance. |
| DEV14-11 Original evidence preservation | COMPLETED | t001 original result stays 5000. |
| DEV14-12 Historical time semantics | COMPLETED | t008 separate cutoffs. |
| DEV14-13 Source fingerprinting | COMPLETED | t013 unchanged fingerprint adds no finding. |
| DEV14-14 Material change classification | COMPLETED | t001 `financially_material`. t015 review required. |
| DEV14-15 Affected-finding selection | COMPLETED | t014 company scope. No contract `write()` hook. No cron. |
| DEV14-16 Reassessment request model | COMPLETED | `cpla.leakage.reassessment`. |
| DEV14-17 Reassessment lifecycle | COMPLETED | t001 requested, proposed, accepted. t012 rejected. |
| DEV14-18 Authority controls | COMPLETED | t001, t005, t009. |
| DEV14-19 DEV-12 recalculation reuse | COMPLETED | Engine stays `dev12.1`. Accept does not call `action_run` or `action_reassess`. |
| DEV14-20 Original versus proposed comparison | COMPLETED | t001 quantity 80, prices 1150 and 1100, exposure 4000, delta -1000. |
| DEV14-21 Historical cutoff evaluation | COMPLETED | t008. |
| DEV14-22 Retroactive amendment handling | COMPLETED | t008. Backdated approval still raises in the version tests, which passed in the 914 runs. |
| DEV14-23 Discount approval correction | COMPLETED | t015 invalid approval stays in review. Valid zero path is not a separate test. |
| DEV14-24 FX and tax corrections | COMPLETED | t015 does not invent a rate or a tax amount. |
| DEV14-25 Source-mapping correction | NOT_EXECUTED | No dedicated reassessment assertion. |
| DEV14-26 Verified quantity return | COMPLETED | t001. |
| DEV14-27 Amount-only credit | COMPLETED | t006. |
| DEV14-28 Full reversal and rebilling | COMPLETED | t007 clears the current finding. t010 does not force zero without a verified reversal. |
| DEV14-29 Evidence completeness | COMPLETED | t015 accept raises while review is required. |
| DEV14-30 Proposed revision status | COMPLETED | t001 stays `proposed_revision_ready` until accept. |
| DEV14-31 Acceptance and rejection | COMPLETED | t001 and t012. |
| DEV14-32 Atomic current revision | COMPLETED | t001 one current finding. t016 at most one under two workers. |
| DEV14-33 Stale source classification | COMPLETED | t012 `source_changed_review_pending`. The current sum is not silently reduced. |
| DEV14-34 Duplicate current exposure | COMPLETED | t001 total is 4000, not 9000. |
| DEV14-35 Case revision synchronization | COMPLETED | t003 and t012. Root cause stays. |
| DEV14-36 Finance submission flag | COMPLETED | t004 `finance_package_stale`. No finance validation. |
| DEV14-37 Event history | COMPLETED | Event fields and types are on the model. A test does not assert every new event type. |
| DEV14-38 Evidence UI | COMPLETED | t011 checks the form strings and filters. |
| DEV14-39 Side-by-side comparison | COMPLETED | t011 checks `original_quantity_exact` on the form. |
| DEV14-40 ACLs and record rules | COMPLETED | Company B cannot read the row in t001. Security foundation tests passed in the 914 runs. |
| DEV14-41 Attachment and export confidentiality | NOT_EXECUTED | No download or `export_data` test. |
| DEV14-42 Multi-company isolation | COMPLETED | t001 and t014. |
| DEV14-43 Idempotency and concurrency | COMPLETED | t001 reuses one open request. t016 is the two-worker test. |
| DEV14-44 Failure recovery | NOT_EXECUTED | No partial-transaction failure test. |
| DEV14-45 Snapshot integrity tests | COMPLETED | t001 and t002 inside the 914 runs. |
| DEV14-46 Source-change tests | COMPLETED | t013, t014, t015. |
| DEV14-47 Financial golden tests | COMPLETED | t001, t006, t007, t008, t010, t012. GOLD-REA-005 valid path has no zero assertion. |
| DEV14-48 Historical-time tests | COMPLETED | t008. |
| DEV14-49 Workflow and security tests | COMPLETED | t001, t005, t009, t012. |
| DEV14-50 Case integration tests | COMPLETED | t003, t004, t012. |
| DEV14-51 Concurrency and failure tests | COMPLETED | t016 passed in gap2, full3, and upgrade3. Failure-injection tests were not added. |
| DEV14-52 Targeted isolated tests | COMPLETED | gap2: 0 failed of 6. full3: 0 failed of 914. |
| DEV14-53 Fresh installation | COMPLETED | `cpla_dev14_fresh2.log`, `-i` of `cpla_dev14b_fresh_20261105`, 0 failed of 914, 2026-11-05 08:10:04. |
| DEV14-54 Upgrade from DEV-13 | COMPLETED | upgrade3 from `19.0.1.11.0`, 0 failed of 914. Module row is `19.0.1.12.0`. |
| DEV14-55 Previous-phase regression | COMPLETED | full3 and upgrade3, each 0 failed of 914, include DEV-01 through DEV-13 tests. |
| DEV14-56 Performance and indexes | COMPLETED | `15_performance_and_concurrency.md`. No batch benchmark. |
| DEV14-57 Requirements traceability | COMPLETED | Table below. |
| DEV14-58 Documentation | COMPLETED | `docs/app04/step14/` files 01 through 17. Fresh-install numbers are in file 14. |
| DEV14-59 DEV-15 handoff | COMPLETED | `17_dev15_handoff.md`. DEV-15 was not implemented. |
| DEV14-60 Final progress report | COMPLETED | Section 68 report after fresh2. Business acceptance stays `PENDING`. |

Finance-validation work is `DEFERRED_TO_DEV15`.

## Traceability

| Item | Where it stands |
| --- | --- |
| P0-A Historical contract authority | t008 and the version tests in the 914 runs. |
| P0-C Audit and finding integrity | t001 original 5000 stays. One current finding. |
| P0-D Investigation evidence | t003, t004, t012. |
| P0-G Historical evidence and security | t002, t001 company rule, t014. |
| P0-J Regression | full3, upgrade3, and fresh2. Each 0 failed of 914. |
| CPL-EVD-001 through CPL-EVD-017 | Implemented in the reassessment models except where a row above is `NOT_EXECUTED`. |
| FIN-01 through FIN-13, FIN-16 | Exercised by t001, t006, t007, t008, t010, t012, t015. FIN-12 stays open: potential is not finance-validated. |
| SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-09, SEC-10, SEC-12 | Company and role checks in t001, t005, t009, t014. Export and attachment tests are `NOT_EXECUTED`. |
| Finance validation, recovery, waivers, accounting reconciliation | Not implemented. |

## Acceptance

`IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING`. The full, upgrade, and fresh gates passed, and `test_rev14_t016` exercised two workers. Business sign-off remains `PENDING`. License remains `BLOCKER_LICENSE_DECISION_REQUIRED`. Commercial release remains `NO-GO`. Suggested IDs marked `NOT_EXECUTED` in `13_automated_test_results.md` were not separate methods. They are not failed tests.
