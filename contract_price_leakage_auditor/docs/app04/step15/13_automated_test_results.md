# Automated test results

Odoo 19.0. Addon `contract_price_leakage_auditor`. Database `cpla_dev14_20261105`. Port 8096. No `--log-level` override. The post-install line is the result. The stats line counts more tests and is not the pass count.

## Targeted finance run

Command directory: `C:\PycharmProjects\odoo19\odoo-19.0`.

Log: `local_testing/cpla_dev15_targeted7.log`.

Process 3104. `2026-11-05 09:22:47`. `14 post-tests in 41.85s, 22041 queries`.

`0 failed, 0 error(s) of 14 tests`. `EXIT:0`.

This run did not use `-u`. The database had already been upgraded to `19.0.1.13.0` by the earlier `-u` on the same database.

Earlier targeted logs are failures, not passes:

| Log | Result |
| --- | --- |
| `local_testing/cpla_dev15_targeted.log` | `1 failed, 13 error(s) of 14 tests`. `EXIT:1`. Company check replaced Odoo's `_check_company`. |
| `local_testing/cpla_dev15_targeted2.log` | `3 failed, 0 error(s) of 14 tests`. `EXIT:1`. |
| `local_testing/cpla_dev15_targeted3.log` through `cpla_dev15_targeted6.log` | `1 failed` or `1 error` of 14 tests. `EXIT:1`. Assertion and access-rule mismatches fixed before targeted7. |

## Executed methods

| Method | Result | Evidence |
| --- | --- | --- |
| `test_fv15_views_sequence_and_menus` | Passed | targeted7 |
| `test_fv15_full_then_partial_correction` | Passed | targeted7 |
| `test_fv15_unresolved_portion_stays_unresolved` | Passed | targeted7 |
| `test_fv15_full_rejection_is_not_a_waiver` | Passed | targeted7 |
| `test_fv15_many_findings_reconcile` | Passed | targeted7 |
| `test_fv15_repeated_audits_validate_once` | Passed | targeted7 |
| `test_fv15_refund_uses_accepted_basis` | Passed | targeted7 |
| `test_fv15_discount_evidence_and_reassessment_block` | Passed | targeted7 |
| `test_fv15_stale_before_approval_uses_the_new_basis` | Passed | targeted7 |
| `test_fv15_stale_after_approval_keeps_history` | Passed | targeted7 |
| `test_fv15_two_levels_and_self_approval` | Passed | targeted7 |
| `test_fv15_currency_ceiling_and_missing_matrix` | Passed | targeted7 |
| `test_fv15_level_denial_records_no_amount` | Passed | targeted7 |
| `test_fv15_concurrent_approval_keeps_one_decision` | Passed | targeted7. Two threads. |

## Catalog IDs

The suggested WF15, FIN15, APP15, HIS15, CASE15, SEC15, CON15, and REG15 identifiers are not separate test methods. Behavior that the 14 methods asserted is recorded in `12_golden_finance_scenarios.md`. The following were not executed as their own tests:

- A two-invoice case with two real currencies. GOLD-FV-017 used a tampered line currency and a recorded policy rate.
- Unauthorized attachment access as its own case.
- A measured large finance queue.
- `test_sec12_t013` was not in the 14-method run. It ran inside the 928-test gates below and those gates passed.

## Full, upgrade, and fresh gates

Each line is `0 failed, 0 error(s) of 928 tests`. Odoo 19.0. Port 8096. Details are in `14_installation_upgrade_regression.md`.

| Gate | Database | Log | When | Duration |
| --- | --- | --- | --- | --- |
| Full `-u` | `cpla_dev14_20261105` | `local_testing/cpla_dev15_full2.log` | 2026-11-05 09:52:48 | 865.85s, 298539 queries |
| Upgrade `-u` from `19.0.1.12.0` | `cpla_dev14b_fresh_20261105` | `local_testing/cpla_dev15_upgrade.log` | 2026-11-05 10:08:25 | 863.88s, 298075 queries |
| Fresh `-i` | `cpla_dev15_fresh_20261105` | `local_testing/cpla_dev15_fresh.log` | 2026-11-05 10:22:55 | 679.39s, 297975 queries |

`local_testing/cpla_dev15_full.log` is `3 failed, 0 error(s) of 928 tests`. It is not a pass. `local_testing/cpla_dev15_gap.log` is the four-test recheck after that failure: `0 failed, 0 error(s) of 4 tests`.

`CON15-T002` is the two-thread method above. The same-user approve retry inside `test_fv15_full_then_partial_correction` is sequential. It is not a second concurrency proof.
