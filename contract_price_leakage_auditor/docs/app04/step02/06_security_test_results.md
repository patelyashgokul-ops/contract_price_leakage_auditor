# 06 — Security test results

Date: 2026-10-28.
Database: `cpla_dev01_foundation_20261028`.
Odoo 19.0. Interpreter: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`.

Update command, exit 0, at 03:58:

```text
C:\PycharmProjects\odoo19\.venv\Scripts\python.exe C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin -c C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf -d cpla_dev01_foundation_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --stop-after-init --without-demo=True --http-port=8079 --http-interface=127.0.0.1
```

The update loaded `security/security_groups.xml` and then ran the tests. Result line: `0 failed, 0 error(s) of 20 tests`.

The test file was then changed to close the file it reads. The same test command without `-u` was run again at 03:59. Exit 0. Result line: `0 failed, 0 error(s) of 20 tests` in 1.54s, 705 queries. The stats line says `24 tests` for the same run. The assertion count is 20: eight DEV-01 smoke tests and twelve DEV-02 tests.

No production database was used.

## Executed tests

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| SEC-T001 | Yes | Pass | `test_sec_t001_groups_exist_with_stable_ids`. Eight distinct group XML IDs. |
| SEC-T002 | Yes | Pass | `test_sec_t002_group_definitions_are_installed`. Module state `installed`. |
| SEC-T003 | Yes | Pass | `test_sec_t003_privilege_assignment_matches_odoo19`. Six privileges, category not exclusive, two ladders. |
| SEC-T004 | Yes | Pass | `test_sec_t004_inheritance_follows_two_ladders_only`. |
| SEC-T005 | Yes | Pass | `test_sec_t005_auditor_has_no_financial_write_authority`. |
| SEC-T006 | Yes | Pass | `test_sec_t006_administrator_has_no_commercial_approval_groups`. |
| SEC-T007 | Yes | Pass | `test_sec_t007_no_public_portal_or_unrestricted_acl`. |
| SEC-T029 | Yes | Pass | Contract User plus Finance Reviewer does not gain manager, operator, or administrator. |
| SEC-T030 | Yes | Pass | Finance Manager plus Recovery Operator keeps both and does not merge the groups. |
| SEC-T031 | Yes | Pass | Auditor plus Contract User does not gain approval groups. |
| SEC-T032 | Yes | Pass | Unlinking Finance Reviewer removes that group and leaves Contract User. |
| Company-context group check | Yes | Pass | `test_company_context_does_not_change_group_membership`. Not a pass of SEC-T008–SEC-T015. |
| SMOKE-001–008 | Yes | Pass | Re-run in the same 20-test result. |

## Planned tests

These were not executed and are not passed.

| Test ID | Status | Reason |
| --- | --- | --- |
| SEC-T008 | PLANNED_FOR_FUTURE_PHASE | No contract model. |
| SEC-T009 | PLANNED_FOR_FUTURE_PHASE | No case model. |
| SEC-T010 | PLANNED_FOR_FUTURE_PHASE | No company-owned business rows. |
| SEC-T011 | PLANNED_FOR_FUTURE_PHASE | No contract-to-invoice link. |
| SEC-T012 | PLANNED_FOR_FUTURE_PHASE | No recovery-to-payment link. |
| SEC-T013 | PLANNED_FOR_FUTURE_PHASE | No record rule exists yet. |
| SEC-T014 | PLANNED_FOR_FUTURE_PHASE | Record-rule bypass cannot be tested yet. Group membership was checked separately. |
| SEC-T015 | PLANNED_FOR_FUTURE_PHASE | No background job. |
| SEC-T016 | PLANNED_FOR_FUTURE_PHASE | No contract approval method. |
| SEC-T017 | PLANNED_FOR_FUTURE_PHASE | No discount approval method. |
| SEC-T018 | PLANNED_FOR_FUTURE_PHASE | No recovery approval method. |
| SEC-T019 | PLANNED_FOR_FUTURE_PHASE | No request or approval record. |
| SEC-T020 | PLANNED_FOR_FUTURE_PHASE | No waiver amount policy. DEC-11 is open. |
| SEC-T021 | PLANNED_FOR_FUTURE_PHASE | No restricted public method. |
| SEC-T022 | PLANNED_FOR_FUTURE_PHASE | No protected decision field. |
| SEC-T023 | PLANNED_FOR_FUTURE_PHASE | No price field. |
| SEC-T024 | PLANNED_FOR_FUTURE_PHASE | No evidence attachment. |
| SEC-T025 | PLANNED_FOR_FUTURE_PHASE | No case evidence. |
| SEC-T026 | PLANNED_FOR_FUTURE_PHASE | No export. |
| SEC-T027 | PLANNED_FOR_FUTURE_PHASE | No aggregate of confidential amounts. |
| SEC-T028 | PLANNED_FOR_FUTURE_PHASE | No public document surface. |

## Failures

No APP 04 test failed in the 03:58 update run or the 03:59 rerun.
