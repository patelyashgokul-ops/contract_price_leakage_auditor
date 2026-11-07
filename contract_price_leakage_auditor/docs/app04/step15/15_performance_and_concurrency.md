# Performance and concurrency

No list-view timing and no queue throughput were measured. Those section 55 benchmarks are NOT_EXECUTED. No throughput number is claimed.

Header totals are stored fields. List views do not call the DEV-12 price engine. Approval does not re-read every invoice history. `current_validated_amount` searches `counts_current` lines for one company.

## Measured targeted run

Command from `C:\PycharmProjects\odoo19\odoo-19.0`, Odoo 19.0, database `cpla_dev14_20261105`, port 8096, process 3104, no `--log-level` override.

Log: `local_testing/cpla_dev15_targeted7.log`.

`2026-11-05 09:22:47` `14 post-tests in 41.85s, 22041 queries`.

`odoo.tests.result`: `0 failed, 0 error(s) of 14 tests`.

`odoo.tests.stats` counted 16 tests in 41.73s. The post-install result line is the one reported. The stats count is higher and is not the pass count.

The log has no `could not serialize` line. That absence is not a claim that the database never waited on a lock.

## Concurrency test

`test_fv15_concurrent_approval_keeps_one_decision` opens a committed pool cursor, swaps `Registry._lock` for a dummy lock while two threads call `action_approve`, then restores the lock. Both threads use the finance user. The test asserts one approved event, one validation, and one validated amount. It does not name a winning thread. It is not a sequential replay of the same cursor.

The class cleanup deletes the pool's finance rows. The pool company is not dropped by the test method.
