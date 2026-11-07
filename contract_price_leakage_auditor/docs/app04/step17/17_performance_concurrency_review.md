# Performance and concurrency

Measured runs only. No benchmark number was invented.

| Run | Evidence |
| --- | --- |
| Targeted pass | 30 post-tests in 100.75s, 45173 queries. Process 19644. Database `cpla_dev14_20261105`. 2026-11-05 15:00:42. `local_testing/dev17_targeted_3.log`. `EXIT:0` |
| Failed targeted runs | `dev17_targeted_1.log`: 74.84s, 31520 queries, process 24176, `EXIT:1`. `dev17_targeted_2.log`: 121.86s, 45161 queries, process 23032, `EXIT:1` |
| Full regression | 969 post-tests in 853.41s, 351857 queries. Process 20972. Database `cpla_dev14_20261105`. 2026-11-05 15:16:45. `local_testing/dev17_full_1.log`. `EXIT:0` |
| Upgrade from `19.0.1.14.0` | 969 post-tests in 1075.90s, 351079 queries. Process 8268. Database `cpla_dev16_fresh_20261105`. 2026-11-05 15:35:57. `local_testing/dev17_upgrade_1.log`. `EXIT:0` |
| Fresh install | 969 post-tests in 1063.04s, 350953 queries. Process 17760. Database `cpla_dev17_fresh_20261105`. 2026-11-05 15:38:47. `local_testing/dev17_fresh_1.log`. `EXIT:0` |

## Indexes

Current billing identity is unique except cancelled, superseded, and fully_reversed. Current billing lines are unique on `(request_line_id, slice_key)`. Current collection evidence is unique on `partial_reconcile_key`. Company id is indexed on the billing models. List views do not load attachments.

Collection refresh reads the receivable lines and their partials for that billing. It does not scan every bank statement in the company. A failed `account.move` read raises `TECHNICAL_ACCOUNTING_FAILURE` instead of returning outstanding zero.

## Concurrency that ran

`test_bill17_concurrent_prepare` commits one authorized request on a side cursor, then two workers call `prepare_from_request` for the same slice. Odoo 19 `lock_for_update()` is `FOR UPDATE SKIP LOCKED` and raises `LockError`. The loser also hits `cpla_recovery_billing_billing_identity_unique`. The passing run logged that duplicate key during the test and the test assertions passed: one current billing, no second posted document. The test cursor may use `cursor.execute` for `lock_timeout`. Addon Python uses `lock_for_update()` and does not call `cr.execute`.

The same payment partial key cannot be inserted twice while `counts_current` is true. A reversed partial is kept with `counts_current` false, so a later match can be stored again without counting the old row as current cash.

These races were not run as two-worker tests: concurrent posting, payment refresh, credit plus payment, stale authorization during post, and a failed reconciliation read during a retry. `test_bill17_failed_read_is_not_zero` covers the failed read on one cursor.

No queue timing was measured.
