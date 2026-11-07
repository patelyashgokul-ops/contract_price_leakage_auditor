# 07 — Automated test results

Date: 2026-10-28.

Runner: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe` (Python 3.11.9) and `odoo-bin`. Config: `C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf`. Tag: `--test-tags=/contract_price_leakage_auditor`. Flags: `--without-demo=True --http-interface=127.0.0.1 --stop-after-init`. Database: `cpla_dev04_20261028`. No production database. No sudo in product code.

The pass/fail line is `odoo.tests.result`. The same process also logs `odoo.tests.stats` with a higher test count. Both lines are quoted. The result line is the failure count.

## Runs

| Run | When | Command | Exit | Result line |
| --- | --- | --- | --- | --- |
| 1 | 2026-10-28 05:24:50–05:26:06 | `-i` of the first contract build | 1 | `3 failed, 2 error(s) of 155 tests` |
| 2 | 2026-10-28 05:29:41–05:30:04 | `-u` after the fixes below | 0 | `0 failed, 0 error(s) of 155 tests` |
| 3 | 2026-10-28 05:31:00–05:32:17 | Fresh `-i` of the corrected module, after dropping only the listed `cpla_` databases | 0 | `0 failed, 0 error(s) of 155 tests` |

Run 2 stats: `contract_price_leakage_auditor: 163 tests 15.48s 12266 queries`.
Run 3 stats: `contract_price_leakage_auditor: 163 tests 14.36s 12269 queries`.
Run 3 also logged `155 post-tests in 14.43s, 12269 queries`.

Odoo version logged at the start of run 3: `Odoo version 19.0`.

Run 1 failures, all fixed before run 2:

| Test | What happened | Fix |
| --- | --- | --- |
| CFG-T046 | Expected manifest `19.0.1.1.0`, actual `19.0.1.2.0` | Expectation updated to `19.0.1.2.0` |
| CFG-T048 | Policy ACL count 6, test expected 5 | Expect 6 and assert the extra row is Contract User read-only |
| CTH-T008 | Wrong-company customer raised `UserError` from `_check_company`, test expected `AccessError` | Assert `UserError` and the word company |
| CTH-T015 | Finance reviewer was stored as owner | Constraint had returned immediately because Odoo runs constraints as sudo. The skip was removed |
| CTL-T011 | Wrong-company product raised `UserError`, first assertion expected `AccessError` | Assert `UserError` and the word company |

No other FAIL or ERROR line was in run 1. Runs 2 and 3 had no FAIL or ERROR line.

## DEV-04 tests

Every ID below was executed in run 3. Result: pass. Evidence: the run 3 result line. The same methods also passed in run 2.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| CTH-T001 | Yes | Pass | Run 3, 0 failed, 0 errors of 155 |
| CTH-T002 | Yes | Pass | Run 3 |
| CTH-T003 | Yes | Pass | Run 3. Reference matches `CPL/2026/` plus 5 digits |
| CTH-T004 | Yes | Pass | Run 3 |
| CTH-T005 | Yes | Pass | Run 3 |
| CTH-T006 | Yes | Pass | Run 3 |
| CTH-T007 | Yes | Pass | Run 3 |
| CTH-T008 | Yes | Pass | Run 3. Failed on run 1 as the wrong exception type. Rejected on all three runs |
| CTH-T009 | Yes | Pass | Run 3. No currency rate created |
| CTH-T010 | Yes | Pass | Run 3 |
| CTH-T011 | Yes | Pass | Run 3 |
| CTH-T012 | Yes | Pass | Run 3 |
| CTH-T013 | Yes | Pass | Run 3. Open end stays draft and cannot be submitted |
| CTH-T014 | Yes | Pass | Run 3. Owner is not the superuser |
| CTH-T015 | Yes | Pass | Run 3. Failed on run 1 before the owner constraint was fixed |
| CTL-T001 | Yes | Pass | Run 3 |
| CTL-T002 | Yes | Pass | Run 3 |
| CTL-T003 | Yes | Pass | Run 3 |
| CTL-T004 | Yes | Pass | Run 3 |
| CTL-T005 | Yes | Pass | Run 3 |
| CTL-T006 | Yes | Pass | Run 3. Zero stays on the draft and blocks review |
| CTL-T007 | Yes | Pass | Run 3 |
| CTL-T008 | Yes | Pass | Run 3 |
| CTL-T009 | Yes | Pass | Run 3 |
| CTL-T010 | Yes | Pass | Run 3 |
| CTL-T011 | Yes | Pass | Run 3. Failed on run 1 as the wrong exception type. Rejected on all three runs |
| CTL-T012 | Yes | Pass | Run 3 |
| CTL-T013 | Yes | Pass | Run 3 |
| CTL-T014 | Yes | Pass | Run 3 |
| CTL-T015 | Yes | Pass | Run 3. Same variant with another unit is stored. Review still requires the default unit |
| CTL-T016 | Yes | Pass | Run 3 |
| CTL-T017 | Yes | Pass | Run 3 |
| CTL-T018 | Yes | Pass | Run 3 |
| LFC-T001 | Yes | Pass | Run 3 |
| LFC-T002 | Yes | Pass | Run 3 |
| LFC-T003 | Yes | Pass | Run 3 |
| LFC-T004 | Yes | Pass | Run 3 |
| LFC-T005 | Yes | Pass | Run 3 |
| LFC-T006 | Yes | Pass | Run 3 |
| LFC-T007 | Yes | Pass | Run 3 |
| LFC-T008 | Yes | Pass | Run 3. `audit_authoritative` is false |
| LFC-T009 | Yes | Pass | Run 3 |
| LFC-T010 | Yes | Pass | Run 3 |
| LFC-T011 | Yes | Pass | Run 3. Second submit does not duplicate lines |
| LFC-T012 | Yes | Pass | Run 3 |
| LFC-T013 | Yes | Pass | Run 3 |
| LFC-T014 | Yes | Pass | Run 3. Selection is only draft, ready for review, cancelled |
| SEC04-T001 | Yes | Pass | Run 3 |
| SEC04-T002 | Yes | Pass | Run 3 |
| SEC04-T003 | Yes | Pass | Run 3 |
| SEC04-T004 | Yes | Pass | Run 3 |
| SEC04-T005 | Yes | Pass | Run 3 |
| SEC04-T006 | Yes | Pass | Run 3 |
| SEC04-T007 | Yes | Pass | Run 3 |
| SEC04-T008 | Yes | Pass | Run 3 |
| SEC04-T009 | Yes | Pass | Run 3 |
| SEC04-T010 | Yes | Pass | Run 3. Application administrator cannot read or write the contract |
| SEC04-T011 | Yes | Pass | Run 3 |
| SEC04-T012 | Yes | Pass | Run 3 |
| SEC04-T013 | Yes | Pass | Run 3 |
| SEC04-T014 | Yes | Pass | Run 3. Header unlink is refused |
| SEC04-T015 | Yes | Pass | Run 3. Contract User plus finance and auditor stays on owned records |
| REG04-T001 | Yes | Pass | Run 3 fresh `-i`, module `installed`, `latest_version` `19.0.1.2.0` |
| REG04-T002 | Not as a DEV-03 upgrade | NOT_EXECUTED | No preserved `19.0.1.1.0` database. See file 08 |
| REG04-T003 | Yes | Pass | Run 3. Policy can reach ready for business review and stays not operationally approved |
| REG04-T004 | Yes | Pass | Run 3. Eight groups. Same two implication ladders |
| REG04-T005 | Yes | Pass | Run 3. `get_view` for list, form, and search. No success badge. Banner text present |
| REG04-T006 | Yes | Pass | Run 3 |
| REG04-T007 | Yes | Pass | Run 3. One Customer Pricing Contracts menu. No partner view from this module |
| REG04-T008 | Yes | Pass | Run 3 |
| REG04-T009 | Yes | Pass | Run 3. Activation still raises `AccessError` |
| REG04-T010 | Yes | Pass | Run 3. `account.move` is not in the registry. No `cpla.leakage`, `cpla.recovery`, or `cpla.audit` model |
| CONTRACT-REF-001 | Yes | Pass | Run 3. Not an invoice audit |
| CONTRACT-REF-002 | Yes | Pass | Run 3. No FX rate written |
| CONTRACT-REF-003 | Yes | Pass | Run 3 |
| CONTRACT-REF-004 | Yes | Pass | Run 3 |
| CONTRACT-REF-005 | Yes | Pass | Run 3 |
| CONTRACT-REF-006 | Yes | Pass | Run 3 |

Additional methods in the same class, also passed in run 3:

- `test_overlap_warning_does_not_choose_a_price`
- `test_currency_change_with_lines_is_blocked`
- `test_extra_covered_entities_block_submission_while_dec03_is_open`
- `test_archived_product_is_retained_and_blocks_review`
- `test_non_current_policy_blocks_submission`

## Earlier phases inside the same tag

Run 3 loaded the whole addon tag, not only the new file. Smoke SMOKE-001–008, the DEV-02 security tests, and CFG-T001–CFG-T050 ran in that 155-test result. None failed. This does not rewrite the historical step 03 record, which was 73 tests on databases that have since been dropped.

## Not executed

| Item | Reason |
| --- | --- |
| REG04-T002 from `cpla_dev01_foundation_20261028` or `cpla_dev03_fresh_20261028` | Those databases were dropped before DEV-04. They were not recreated from a `19.0.1.1.0` backup. |
| Browser walkthrough | No browser session. Server-side `get_view` passed. |
| Invoice audit of CONTRACT-REF fixtures | Out of scope. `audit_authoritative` stayed false. |
| Odoo 18 or Odoo 20 test run | Not converted. |
