# Performance and concurrency

## Measured

| Measurement | Result |
| --- | --- |
| Commercial approval elapsed inside `test_rec16_full_recovery_and_partial_waiver` | `DEV16 commercial approval elapsed_seconds=5.88` at 2026-11-05 12:25:04 in `local_testing/dev16_targeted_2.log`, process 25680 |
| Targeted 13 post-tests | 179.40s, 22586 queries, database `cpla_dev14_20261105` |
| Full 941 post-tests | 1338.02s, 314495 queries, same database, `local_testing/dev16_full_1.log` |
| Upgrade 941 post-tests | 1018.84s, 313948 queries, `cpla_dev14b_fresh_20261105`, `local_testing/dev16_upgrade_1.log` |
| Fresh 941 post-tests | 875.64s, 313771 queries, `cpla_dev16_fresh_20261105`, `local_testing/dev16_fresh_1.log` |

No list-view timing, no queue benchmark, and no throughput figure was measured. Those section 52 benchmarks are `NOT_EXECUTED`.

Stored totals on the balance are what `position_for()` reads. The recovery list does not reprice invoices. Superseded rows are excluded by `counts_current`.

## Locking that executed

`test_rec16_concurrent_waiver_allocation` uses two threads, swaps `Registry._lock` to `DummyRLock` for the workers, and restores it. The pool company is the existing `CPLA14 Conc Pool` company. The test does not create users with `new_test_user` on the side cursor. The log records `FOR UPDATE SKIP LOCKED` and `could not serialize access due to concurrent update` during that test, and the test passed. The losing worker did not leave a second current waiver of the same slice.

Other concurrent cases were not separate two-worker tests:

| Prompt ID | What ran |
| --- | --- |
| CON16-T001 | Sequential over-allocation is refused in `test_rec16_excess_waiver_and_duplicate_and_partial_split`. Two-worker recovery allocation was not run. |
| CON16-T002 | Executed by `test_rec16_concurrent_waiver_allocation`. |
| CON16-T003 | Not a two-worker test. The equation is checked after sequential approvals. |
| CON16-T004 | Not a two-worker settlement test. A second current proposal must name `supersedes_id`. |
| CON16-T005 | Stale blocking is sequential in `test_rec16_stale_blocks_new_approval`. |
| CON16-T006 | Self-approval raises before the amount is approved. A killed transaction was not injected. |
| CON16-T007 | Repeating a finished recovery approval does not add a second level event. Asserted in the full-recovery test. |
| CON16-T008 | Repeating handoff keeps one key. Asserted in the full-recovery test. |
| CON16-T009 | A second dispute that would exceed the target is refused in one transaction. Two-worker disputes were not run. |
| CON16-T010 | Event rows are append-only. A dedicated identity race was not run. |

Indexes used by the models: company, finance line, request, waiver, dispute, settlement, `counts_current`, source fingerprint, and the partial unique indexes for handoff key and approval level. No extra index was added from a measured slow query.
