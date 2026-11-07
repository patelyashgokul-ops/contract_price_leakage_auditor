# 10 — Automated test results

Date: 2026-10-28.

Class: `TestDev07QuantityTier` in `tests/test_quantity_tier.py`. Tag: post-install. 98 new methods. Prior suite was 366 tests. Both green runs are 464 tests.

## Runs

| Run | Database | Command | Result |
| --- | --- | --- | --- |
| 1 | `cpla_dev06_20261028` | `-u contract_price_leakage_auditor` | 2 failed, 2 error(s) of 464 tests. Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev07_upgrade.log`. 464 post-tests in 99.00s, 79438 queries. |
| 2 | `cpla_dev06_20261028` | same `-u` after the four fixes | 0 failed, 0 error(s) of 464 tests. Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev07_upgrade2.log`. 464 post-tests in 139.07s, 79502 queries. |
| 3 | `cpla_dev07_20261028` | `-i contract_price_leakage_auditor` | 0 failed, 0 error(s) of 464 tests. Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev07_fresh.log`. 464 post-tests in 98.76s, 79553 queries. |

Port 8071. `--without-demo=True`. `--stop-after-init`. The freight server on port 8069 was not changed.

Run 1 failures, all fixed before run 2:

- HIS07-T006 raised on submit because a later approved version already existed. The test now expects that block. The former tier stays.
- QTY07-T008 treated zero as missing because `0 == False`. Zero is now a supplied quantity and returns `NO_MATCHING_TIER`.
- SEC07-T003 hit the approved-line message before the access check. Line `write` now checks access first. The reviewer gets `AccessError`.
- UOM07-T013 wrote factors with `_write_multi` and then read a stale cache. The test invalidates the record before resolve.

No `SerializationFailure` line was present in the green upgrade log.

## Results

Every ID below was executed in runs 2 and 3. Result: pass. Evidence: the two green logs. Where two IDs share one method, both assertions are in that method.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| TIER07-T001–T015 | Yes | Pass | `test_tier07_*`. T015 did not start a second database worker. Overlap is rejected in one transaction under the line lock. |
| QTY07-T001–T012 | Yes | Pass | `test_qty07_*` |
| UOM07-T001–T016 | Yes | Pass | T011 and T012 share one method |
| PAR07-T001–T013 | Yes | Pass | Explicit request context. Not a posted invoice. |
| HIS07-T001–T010 | Yes | Pass | T001 with T002, and T003 with T004, share methods |
| SEC07-T001–T012 | Yes | Pass | T001 calls TIER07-T001. T002 calls TIER07-T010. T012 is `evaluate` as the application administrator. |
| REG07-T001–T013 | Yes | Pass | Shared methods as named in the test file. Prior modules stay imported. |
| QT-REF-001–015 | Yes | Pass | Several call the earlier methods and still run as their own tests |
| `test_det07_lookup_stays_under_the_ceiling` | Yes | Pass | Asserts under 5 seconds. The measured seconds are not in the log. |

Real sales-order, picking, and invoice document linkage was not executed. Those cases are `DEFERRED_TO_DEV11_OR_DEV12`. They are not marked passed.

UI evidence is `get_view` on the version form and the applicability check. No browser session was run. There is no invoice-audit screen.
