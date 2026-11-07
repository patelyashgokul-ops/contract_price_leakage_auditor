# Performance and concurrency

Only measurements from executed DEV-13 runs are listed here. No threshold was invented.

## Sequential open

`test_case_ref_015_and_activity_do_not_schedule_a_cron` opened 20 cases in one transaction.

Log line, database `cpla_dev13_20261105`, 2026-11-05 03:50:20:

`DEV13 sequential case open count=20 elapsed_seconds=5.196`

The same log line on the later full tags, still 20 opens and no speed assertion:

| Log | Database | elapsed_seconds |
| --- | --- | --- |
| `cpla_dev13_class4.log` | `cpla_dev13_20261105` | 5.196 |
| `cpla_dev13_full.log` | `cpla_dev13_20261105` | 3.122 |
| `cpla_dev13_upgrade.log` | `cpla_dev12_20261028` | 4.361 |
| `cpla_dev13_fresh.log` | `cpla_dev13_fresh_20261105` | 13.435 |

The test asserts the count is 20 and the elapsed time is greater than zero. It does not assert a speed limit. Each open posts an invoice and inserts a finding before `create_from_findings`, so these figures are not case-insert time alone. The fresh database was slower. No cause beyond that measurement was isolated.

The same test asserts no `ir.cron` with model `cpla.leakage.case`.

## What the code avoids

- Case create does not call the invoice audit engine.
- Exposure is a sum of stored finding texts through `_arithmetic`. It is not a new price-times-quantity calculation.
- `_sync_exposure` runs on the cases being linked, not on every case in the company.
- Evidence seed stores record ids. It does not read invoice binaries.
- The invoice label does not read `account.move` when the user has no read right, so case create does not pull journal-entry rows into the contract-manager cache.

Indexes used for the hot checks: unique `reference`, partial unique current membership on `finding_id`, unique `current_identity` on the finding, and indexes on company, state, owner, and `source_reassessment_required`.

## Full addon tag

Database `cpla_dev13_20261105`, log `C:\Users\Admin\AppData\Local\Temp\cpla_dev13_full.log`, 2026-11-05.

`898 post-tests in 534.42s, 264920 queries`

`contract_price_leakage_auditor: 924 tests 534.14s 264920 queries`

`0 failed, 0 error(s) of 898 tests`

The 898 count is the executed post-install tests. The 924 count is the Odoo stats line for the same run. This is wall time for the whole addon tag, not a case-only benchmark.

The upgrade tag on `cpla_dev12_20261028` was 898 post-tests in 594.87s, 264892 queries. The fresh tag on `cpla_dev13_fresh_20261105` was 898 post-tests in 663.73s, 264909 queries. Registry load was 24.910s on the upgrade and 163.992s on the fresh database. Detail is in `14_installation_and_regression.md`.

## Concurrency

Two PostgreSQL workers were not started.

`test_con13_duplicate_index_rollback_and_idempotent_sync` logs:

`CON13 two-worker concurrency was NOT_EXECUTED. This test uses one transaction.`

What that test did exercise in one transaction:

- A patched membership search that hides `finding_id in ...`, plus `_create_case` raising `IntegrityError`, returns the existing case.
- A second current membership for the same finding raises `IntegrityError` inside a savepoint. After the savepoint, one current membership remains.
- A checklist seed that raises leaves no membership for that finding.
- A patched `_link` that raises `IntegrityError` during merge rolls back. The source case stays `new`, keeps its current membership, and the target exposure stays `1500`.
- Close then close again raises. Reopen leaves one current membership.

The partial unique index is the database guard. The savepoint is the application guard so a failed create does not keep a half-linked membership. That is not a two-session proof. A two-worker run remains `NOT_EXECUTED`.
