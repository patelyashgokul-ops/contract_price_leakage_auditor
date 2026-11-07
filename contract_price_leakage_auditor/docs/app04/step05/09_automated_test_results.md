# 09 — Automated test results

Date: 2026-10-28.

Runner: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe` (Python 3.11.9) and `odoo-bin`. Config: `C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf`. Tag: `--test-tags=/contract_price_leakage_auditor`. Flags: `--without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init`. No production database. Product code has no `sudo()` and no `.execute(`.

The pass/fail line is `odoo.tests.result`. The same process also logs `odoo.tests.stats` with a higher count. Both lines are quoted. The result line is the failure count. Odoo logged `Odoo version 19.0` at the start of each run.

## Runs

| Run | When (UTC) | Database | Command | Result line |
| --- | --- | --- | --- | --- |
| 1 | 2026-10-28 06:33:23 | `cpla_dev04_20261028` | `-u` | `1 failed, 77 error(s) of 242 tests` |
| 2 | 2026-10-28 06:49:44–06:52:21 | `cpla_dev04_20261028` | `-u` | `7 failed, 19 error(s) of 242 tests` |
| 3 | 2026-10-28 07:16:18–07:16:57 | `cpla_dev04_20261028` | `-u` | `3 failed, 4 error(s) of 242 tests` |
| 4 | 2026-10-28 07:30:43–07:31:22 | `cpla_dev04_20261028` | `-u` | `0 failed, 0 error(s) of 242 tests` |
| 5 | 2026-10-28 07:32:23–07:34:08 | `cpla_dev05_20261028` | fresh `-i` | `0 failed, 0 error(s) of 242 tests` |

Run 1 stats: `242 post-tests in 55.24s, 22334 queries`. Wrapper exit 1. Log `C:\Users\Admin\AppData\Local\Temp\cpla_dev05_upgrade.log`.

Run 2 stats: `242 post-tests in 149.00s, 29546 queries`. Result logger level ERROR. Log `cpla_dev05_upgrade2.log`.

Run 3 stats: `242 post-tests in 30.86s, 30276 queries`. Result logger level ERROR. Log `cpla_dev05_upgrade3.log`.

Run 4 stats: `contract_price_leakage_auditor: 252 tests 31.45s 30317 queries` and `242 post-tests in 31.48s, 30317 queries`. Result logger level INFO. Wrapper exit 0. Log `cpla_dev05_upgrade4.log`.

Run 5 stats: `contract_price_leakage_auditor: 252 tests 31.91s 30369 queries` and `242 post-tests in 32.00s, 30369 queries`. Result logger level INFO. Wrapper exit 0. Log `cpla_dev05_fresh.log`. Modules loaded at 07:33:36 before the tests.

Runs 1–3 are failures. Runs 4 and 5 are the passing evidence. The 242 count is 155 prior-phase post-tests plus 87 methods in `tests/test_contract_version.py`.

## Failures fixed before run 4

| Run | What failed | Fix that run 4 executed |
| --- | --- | --- |
| 1 | Version create called a method named `_prepare_create_values`, which Odoo already uses. One view assertion also missed Approve because the superuser lacks the button group. | Renamed the helper to `_prepare_version_values`. REG05-T006 loads the form as a Contract Manager. |
| 2 | Finance Manager approval wrote `product_name` through the public line `write()` and had no line write ACL. Concurrent workers blocked on `Registry._lock`. Committed pool users left the role groups non-empty. AMD-T016 expected a rolled-back event row. | Product-name freeze uses `_write_multi` inside the approval savepoint. Workers swap in `DummyRLock` only while they run. Class cleanup strips the pool membership. |
| 3 | CFG-T048 saw one committed pool policy. AMD-T016 still looked for an event inside `assertRaises`, which rolls a savepoint back. Stale text used a `source` placeholder that collides with `Environment._`. CON05-T001 rejected a PostgreSQL serialization abort. CONTRACT-V008 read the version after its cursor closed. | Pool companies are deleted with SQL before the next process. AMD-T016 records `reassessment_required` and creates the event before `assertRaises`. The placeholder is `source_version`. SerializationFailure is an accepted non-duplicate outcome. The state is read inside the open cursor. |

Run 4 and run 5 each log one `could not serialize access due to concurrent update` during `test_con05_t001_simultaneous_approvals_do_not_duplicate`. The next test starts immediately afterward, and the result line is 0 failed. That error is the losing transaction. The test requires one approved version.

## DEV-05 tests

Every ID below was executed in run 4 and again in run 5. Result: pass. Evidence: both result lines, plus the `Starting TestDev05ContractVersion.<method>` line in each log.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| VER-T001 | Yes | Pass | `test_ver_t001_initial_version_from_ready_contract`. Runs 4 and 5. |
| VER-T002 | Yes | Pass | `test_ver_t002_version_number_unique_within_contract`. |
| VER-T003 | Yes | Pass | `test_ver_t003_version_reference_is_stable`. |
| VER-T004 | Yes | Pass | `test_ver_t004_company_ownership_matches_parent`. |
| VER-T005 | Yes | Pass | `test_ver_t005_source_contract_relationship`. |
| VER-T006 | Yes | Pass | `test_ver_t006_customer_scope_snapshot`. |
| VER-T007 | Yes | Pass | `test_ver_t007_currency_snapshot_is_not_converted`. |
| VER-T008 | Yes | Pass | `test_ver_t008_product_line_snapshots`. |
| VER-T009 | Yes | Pass | `test_ver_t009_effective_date`. |
| VER-T010 | Yes | Pass | `test_ver_t010_missing_evidence_is_rejected`. |
| VER-T011 | Yes | Pass | `test_ver_t011_failed_approval_leaves_no_partial_snapshot`. |
| VER-T012 | Yes | Pass | `test_ver_t012_approved_version_survives_parent_edits`. |
| AMD-T001 | Yes | Pass | `test_amd_t001_authorized_draft_amendment`. |
| AMD-T002 | Yes | Pass | `test_amd_t002_source_approved_version_is_preserved`. |
| AMD-T003 | Yes | Pass | `test_amd_t003_draft_amendment_is_not_approved`. |
| AMD-T004 | Yes | Pass | `test_amd_t004_changed_product_price_is_proposed`. |
| AMD-T005 | Yes | Pass | `test_amd_t005_unchanged_product_price_is_retained`. |
| AMD-T006 | Yes | Pass | `test_amd_t006_removed_product_is_explicit_in_comparison`. |
| AMD-T007 | Yes | Pass | `test_amd_t007_new_product_is_included`. |
| AMD-T008 | Yes | Pass | `test_amd_t008_invalid_effective_date_is_rejected`. |
| AMD-T009 | Yes | Pass | `test_amd_t009_approval_requires_authority`. |
| AMD-T010 | Yes | Pass | `test_amd_t010_rejected_amendment_does_not_affect_prior_version`. |
| AMD-T011 | Yes | Pass | `test_amd_t011_future_dated_amendment_stays_scheduled`. |
| AMD-T012 | Yes | Pass | `test_amd_t012_supersession_relationship`. |
| AMD-T013 | Yes | Pass | `test_amd_t013_amendment_draft_cannot_modify_approved_snapshot`. |
| AMD-T014 | Yes | Pass | `test_amd_t014_direct_child_line_write_cannot_mutate_history`. |
| AMD-T015 | Yes | Pass | `test_amd_t015_retroactive_amendment_requires_policy`. |
| AMD-T016 | Yes | Pass | `test_amd_t016_retroactive_attempt_preserves_as_known_at_history`. |
| AMD-T017 | Yes | Pass | `test_amd_t017_reassessment_does_not_run_invoice_audits`. |
| AMD-T018 | Yes | Pass | `test_amd_t018_stale_draft_is_not_approved`. |
| HIS-T001 | Yes | Pass | `test_his_t001_v1_price_preserved_after_v2`. |
| HIS-T002 | Yes | Pass | `test_his_t002_v2_price_is_independent`. |
| HIS-T003 | Yes | Pass | `test_his_t003_list_price_change_does_not_mutate_version_price`. |
| HIS-T004 | Yes | Pass | `test_his_t004_product_archival_does_not_erase_snapshot`. |
| HIS-T005 | Yes | Pass | `test_his_t005_contract_description_update_does_not_rewrite_history`. |
| HIS-T006 | Yes | Pass | `test_his_t006_approved_version_write_is_rejected`. |
| HIS-T007 | Yes | Pass | `test_his_t007_approved_line_write_is_rejected`. |
| HIS-T008 | Yes | Pass | `test_his_t008_approved_version_unlink_is_rejected`. |
| HIS-T009 | Yes | Pass | `test_his_t009_approved_line_unlink_is_rejected`. |
| HIS-T010 | Yes | Pass | `test_his_t010_approval_event_history_is_preserved`. |
| HIS-T011 | Yes | Pass | `test_his_t011_comparison_identifies_changed_terms`. |
| HIS-T012 | Yes | Pass | `test_his_t012_repeated_approval_does_not_duplicate_authority`. |
| HIS-T013 | Yes | Pass | `test_his_t013_history_remains_after_parent_cancel_is_refused`. Archive is not a field. Cancel after approval is refused. |
| HIS-T014 | Yes | Pass | `test_his_t014_effective_date_boundaries`. |
| HIS-T015 | Yes | Pass | `test_his_t015_overlapping_approved_authority_is_rejected`. |
| HIS-T016 | Yes | Pass | `test_his_t016_supersession_does_not_erase_prior_snapshot`. |
| SEC05-T001 | Yes | Pass | `test_sec05_t001_manager_can_review_permitted_version`. Review, not an extra approval grant. |
| SEC05-T002 | Yes | Pass | `test_sec05_t002_contract_user_cannot_approve`. |
| SEC05-T003 | Yes | Pass | `test_sec05_t003_self_approval_is_prohibited`. |
| SEC05-T004 | Yes | Pass | `test_sec05_t004_finance_reviewer_cannot_approve`. |
| SEC05-T005 | Yes | Pass | `test_sec05_t005_application_administrator_cannot_approve`. |
| SEC05-T006 | Yes | Pass | `test_sec05_t006_company_a_user_cannot_read_company_b_version`. |
| SEC05-T007 | Yes | Pass | `test_sec05_t007_company_a_cannot_approve_company_b`. |
| SEC05-T008 | Yes | Pass | `test_sec05_t008_cross_company_line_is_rejected`. |
| SEC05-T009 | Yes | Pass | `test_sec05_t009_unauthorized_evidence_read_is_rejected`. |
| SEC05-T010 | Yes | Pass | `test_sec05_t010_direct_rpc_approval_bypass_is_rejected`. |
| SEC05-T011 | Yes | Pass | `test_sec05_t011_child_line_mutation_cannot_bypass_immutability`. |
| SEC05-T012 | Yes | Pass | `test_sec05_t012_combined_groups_stay_inside_company_and_owner`. |
| SEC05-T013 | Yes | Pass | `test_sec05_t013_auditor_cannot_alter_approved_price`. |
| SEC05-T014 | Yes | Pass | `test_sec05_t014_unauthorized_history_export_is_denied`. |
| SEC05-T015 | Yes | Pass | `test_sec05_t015_restricted_cancel_and_reject_are_denied`. |
| CON05-T001 | Yes | Pass | `test_con05_t001_simultaneous_approvals_do_not_duplicate`. Two threads, two cursors, one barrier. |
| CON05-T002 | Yes | Pass | `test_con05_t002_concurrent_version_numbers_stay_unique`. |
| CON05-T003 | Yes | Pass | `test_con05_t003_concurrent_amendments_detect_stale_source`. |
| CON05-T004 | Yes | Pass | `test_con05_t004_failed_approval_does_not_leave_partial_snapshot`. |
| CON05-T005 | Yes | Pass | `test_con05_t005_repeated_approval_is_idempotent`. |
| CON05-T006 | Yes | Pass | `test_con05_t006_supersession_chronology_stays_consistent`. |
| REG05-T001 | Yes | Pass | `test_reg05_t001_installed_module_matches_manifest` inside both suites. The fresh database command is run 5. |
| REG05-T002 | Yes | Pass | The `-u` command on `cpla_dev04_20261028` is run 4. There is no separate method with this id. |
| REG05-T003 | Yes | Pass | `test_reg05_t003_existing_contract_model_is_preserved`. |
| REG05-T004 | Yes | Pass | `test_reg05_t004_existing_contract_lines_are_preserved`. |
| REG05-T005 | Yes | Pass | `test_reg05_t005_prior_test_modules_remain_loaded`. The 155 earlier post-tests are inside the same 242. |
| REG05-T006 | Yes | Pass | `test_reg05_t006_views_menus_and_security_load`. Form loaded as Contract Manager. |
| REG05-T007 | Yes | Pass | `test_reg05_t007_version_xml_ids_are_unique`. |
| REG05-T008 | Yes | Pass | `test_reg05_t008_no_accounting_records_are_created`. |
| REG05-T009 | Yes | Pass | `test_reg05_t009_no_invoice_audit_jobs_are_created`. |
| REG05-T010 | Yes | Pass | `test_reg05_t010_configuration_policies_remain_intact`. |
| CONTRACT-V001 | Yes | Pass | `test_contract_v001_draft_save_does_not_approve`. |
| CONTRACT-V002 | Yes | Pass | `test_contract_v002_prospective_increase_keeps_both_versions`. |
| CONTRACT-V003 | Yes | Pass | `test_contract_v003_multiple_products_comparison`. |
| CONTRACT-V004 | Yes | Pass | `test_contract_v004_rejected_amendment`. |
| CONTRACT-V005 | Yes | Pass | `test_contract_v005_contract_user_cannot_approve`. |
| CONTRACT-V006 | Yes | Pass | `test_contract_v006_future_dated_version_is_not_effective_early`. |
| CONTRACT-V007 | Yes | Pass | `test_contract_v007_retroactive_amendment_is_blocked`. |
| CONTRACT-V008 | Yes | Pass | `test_contract_v008_and_con05_concurrent_approval`. Same helper as CON05-T001. |
| CONTRACT-V009 | Yes | Pass | `test_contract_v009_stale_source_blocks_automatic_supersession`. |
| CONTRACT-V010 | Yes | Pass | `test_contract_v010_cross_company_approval_is_denied`. |
| GOLD-FIN-002 preservation | Yes | Pass | `test_gold_fin_002_both_prices_and_policy_are_preserved`. Both prices and the policy snapshot string remain. `is_recovered_cash` is false. |

## Not executed as financial calculations

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| GOLD-FIN-001 leakage amount | No | NOT_EXECUTED | No test computes INR 25,000 or compares an invoice price of 1,100. DEV-05 does not implement that difference. |
| GOLD-FIN-002 applicability | No | NOT_EXECUTED | The June order grandfathering outcome is not selected. DEV-06 owns applicability. The two approved prices are preserved by the row above. |
| GOLD-REC-001 | No | NOT_EXECUTED | No waiver, recovery target, cash, or outstanding balance is calculated. |

Dates in the automated examples are offsets from `fields.Date.context_today`, because the machine date is 2026-10-28. A literal July 2026 effective date would be retroactive on this machine and would be blocked.

No browser click-through was run. REG05-T006 loads the version views with `get_view`.
