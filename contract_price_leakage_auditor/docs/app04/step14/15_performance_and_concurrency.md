# Performance and concurrency

Date: 2026-11-05. No separate batch benchmark was run. The figures below are the test logs that exist. They are not a forecast.

## What is bounded

`affected_findings` filters by company and optional version, partner, and product. It does not scan other companies. Contract `write()` is not hooked. No reassessment cron exists.

Indexes used by this path include `current_identity` unique, reassessment `company_id`, `finding_id`, `state`, `trigger_type`, and the partial unique index on an open request. Event `reassessment_id`, `company_id`, `event_type`, and `finding_id` are indexed.

Acceptance takes a savepoint. The finding upsert writes the old row and inserts the new one. Two workers that update the same finding row collide in PostgreSQL instead of both committing a current row.

## Measured concurrency

`cpla_dev14_gap2.log`, database `cpla_dev14_20261105`, Odoo 19.0, port 8093, PID 22492, 2026-11-05 06:59:45.

Command: module tests for `test_rev14_t001` and `test_rev14_t012` through `test_rev14_t016`, no `-u`, `--stop-after-init`.

Result: `0 failed, 0 error(s) of 6 tests`. `6 post-tests in 26.42s, 12281 queries`. Shell exit 0.

`test_rev14_t016` starts two threads on two cursors, with a `threading.Barrier`, after committing the fixture on a third cursor. One worker's `UPDATE cpla_leakage_finding` (clearing `current_identity` on id 459) logged:

`ERROR: could not serialize access due to concurrent update`

The test still passed: at most one current potential finding for that company, the exposure total was not 9000, and one or both requests were `accepted`. This is a real concurrent conflict, not a sequential replay.

The same conflict was logged again in `cpla_dev14_full3.log` during `test_rev14_t016`, and that suite still finished `0 failed, 0 error(s) of 914 tests` (`914 post-tests in 1142.10s, 282679 queries`, 2026-11-05 07:37:40, database `cpla_dev14_20261105`, port 8093, PID 23288).

The upgrade log `cpla_dev14_upgrade3.log` recorded the same serialization error and the same three expected unique-constraint errors. That run finished `0 failed, 0 error(s) of 914 tests` (`914 post-tests in 1003.76s, 282511 queries`, 2026-11-05 07:56:41, database `cpla_dev13_fresh_20261105`, port 8094, PID 12488).

The fresh log `cpla_dev14_fresh2.log` recorded the same four lines. That run finished `0 failed, 0 error(s) of 914 tests` (`914 post-tests in 537.29s, 282519 queries`, 2026-11-05 08:10:04, database `cpla_dev14b_fresh_20261105`, port 8095, PID 7420).

The earlier `cpla_dev14_rev14.log` (`0 failed, 0 error(s) of 0 tests`) is not a pass. Method tags were not selected.

## Not measured

No timing was taken for a large contract amendment across many findings. `affected_findings` was not benchmarked. Do not treat the 26.42 second six-test run as a batch-reassessment rate.
