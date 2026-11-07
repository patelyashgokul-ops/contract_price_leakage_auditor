# 12 — DEV-06 progress

Date: 2026-10-28.

Implementation: `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING`.

Business acceptance: `PENDING`.

License: `BLOCKER_LICENSE_DECISION_REQUIRED`. The manifest value remains `Other proprietary`.

`operationally_approved` remains false. DEC-01, DEC-02, and DEC-03 are not decided. Amount thresholds are not configured. This is not an approved invoice-audit price.

## Traceability

| ID | State |
| --- | --- |
| P0-A Contract governance | Preserved. Header states are unchanged. Approved authority is the version snapshot. |
| P0-B Pricing applicability | Partially implemented. Exact company, customer, and variant selection is tested. Template, group, branch, and category scope are review or no-match. |
| P0-G Security and historical evidence | Company isolation and cutoff tests passed. Retroactive restatement is not authorized. |
| P0-J Test readiness | 366 post-tests passed on update run 2 and on the fresh database. |
| CPL-C01 Company-specific contract | Tested. |
| CPL-C02 Product and variant scope | Exact variant tested. Template scope is not a stored term. |
| CPL-C03 Contract validity | Inclusive effective dates and expiry tested. |
| CPL-C04 Approved historical version | Draft, rejected, and future versions excluded. |
| CPL-C05 Amendment and supersession | Later effective date selects the superseding version. |
| CPL-C08 Pricing-date policy | Request date only. Stored candidates are not operational. |
| CPL-C09 Conflict detection | Equal authorities conflict. No price tie-break. |
| CPL-C10 Contract evidence | Evidence ids are returned on a match. Files are not a legal archive. |
| FIN-01 Historical version | Tested as selection. |
| FIN-02 Pricing-date rules | Request basis tested. Policy text is not the rule. |
| FIN-08 No unsupported financial conclusion | `leakage_amount` is false. |
| FIN-09 Unique current authority | One match, or an explicit conflict. |
| FIN-11 Historical evidence | Cutoff uses `approved_at`. |
| SEC-01 Company isolation | Tested. |
| SEC-02 Confidential pricing | Other-company prices are absent from explanations and errors. |
| SEC-08 Safe background scope | Allowed companies do not broaden the requested company. |
| SEC-09 Unauthorized change | Resolution does not write the version. |

Invoice audit, leakage math, recovery, and waiver requirements are not complete.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| DEV06-01 Review DEV-00 through DEV-05 | COMPLETED | Version models, policy candidates, and the green DEV-05 runs were the base. |
| DEV06-02 Inspect contracts and versions | COMPLETED | Exact partner and variant line. Extra covered partners block approval. |
| DEV06-03 Review pricing policies | COMPLETED | Defaults stay `unconfigured`. `operationally_approved` is false. |
| DEV06-04 Resolver architecture | COMPLETED | `cpla.pricing.applicability` and the check wizard. |
| DEV06-05 Input and output schema | COMPLETED | Documented in `01_applicability_architecture.md`. |
| DEV06-06 Input validation | COMPLETED | Missing company, customer, product, and dates. |
| DEV06-07 Company filtering | COMPLETED | Domain plus record rules. SEC06-T002, T003, T015. |
| DEV06-08 Exact customer matching | COMPLETED | APP-001, CUS06-T001. |
| DEV06-09 Branch, parent, and group coverage | COMPLETED | Implemented as no-match or historical review. Not an approved coverage grant. |
| DEV06-10 Historical customer coverage | COMPLETED | APP-019, CUS06-T008, CUS06-T009. |
| DEV06-11 Variant matching | COMPLETED | PRD06-T001, T002. |
| DEV06-12 Template matching | COMPLETED | Refused unless a real template term exists. None does. |
| DEV06-13 Pricing-date resolution | COMPLETED | DAT06-T001 through T005. |
| DEV06-14 Grandfathering | COMPLETED | GFD06. No approved time limit. |
| DEV06-15 Version approval filtering | COMPLETED | APP-012, PRE06-T012, T013. |
| DEV06-16 Effective-date selection | COMPLETED | APP-006, APP-007, DAT06-T015. |
| DEV06-17 Historical approval cutoff | COMPLETED | APP-013 and DAT06-T011 passed after the one-second gap. |
| DEV06-18 Retroactive amendments | COMPLETED | Approval stays blocked. Former authority remains. No restated V2. |
| DEV06-19 Supersession | COMPLETED | DAT06-T016. |
| DEV06-20 Deterministic precedence | COMPLETED | Single authority or conflict. |
| DEV06-21 Conflict classification | COMPLETED | APP-015, PRE06-T006, T007. |
| DEV06-22 Missing-context outcomes | COMPLETED | APP-016, DAT06-T005. |
| DEV06-23 Resolution explanation | COMPLETED | Match text and conflict references. |
| DEV06-24 Security and company isolation | COMPLETED | SEC06. |
| DEV06-25 Candidate discovery | COMPLETED | Domain search. No new index. |
| DEV06-26 Diagnostic UI | COMPLETED | Wizard and menu. Evidence is `get_view`, not a browser. |
| DEV06-27 Customer and product tests | COMPLETED | CUS06, PRD06. |
| DEV06-28 Date and grandfathering tests | COMPLETED | DAT06, GFD06. |
| DEV06-29 Precedence tests | COMPLETED | PRE06. |
| DEV06-30 Security tests | COMPLETED | SEC06. |
| DEV06-31 Determinism and performance tests | COMPLETED | DET06. Ceiling only. |
| DEV06-32 Execute tests | COMPLETED | Runs 2 and 3: 0 failed of 366. Run 1: 2 failed of 366. |
| DEV06-33 Installation and update | COMPLETED | `-u` on `cpla_dev05_20261028`. `-i` on `cpla_dev06_20261028`. |
| DEV06-34 Prior-phase regression | COMPLETED | Previous tests are inside the same 366. |
| DEV06-35 Requirements traceability | COMPLETED | This file. |
| DEV06-36 Documentation | COMPLETED | `docs/app04/step06/` files 01–13. |
| DEV06-37 DEV-07 handoff | COMPLETED | `13_dev07_handoff.md`. DEV-07 was not started. |
| DEV06-38 Final progress report | COMPLETED | This file and the session report. |

## Defects

Run 1 cutoff comparisons failed because `approved_at` has one-second precision. Fixed in the tests by waiting 1.1 seconds. Not a product change.

The DEV-05 concurrency test still logs one serialization error. The suite result stays 0 failed. The losing user can see a database error. It was not wrapped into an approval.

No critical selection defect remained open after run 2.
