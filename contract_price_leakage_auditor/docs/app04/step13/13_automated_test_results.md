# Automated test results

Odoo 19.0. Interpreter: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`. Working directory: `C:\PycharmProjects\odoo19\odoo-19.0`. `--without-demo=True`. `--http-interface=127.0.0.1`. `--stop-after-init`.

The first class run used port 8071. Later runs used port 8093 because 8071 is held by a different project. Those earlier class runs are not acceptance.

| Run | Database | Port | Result line | Stats line |
| --- | --- | --- | --- | --- |
| Class, first | `cpla_dev13_20261105` | 8071 | 0 failed, 7 errors of 20 tests (`cpla_dev13_class.log`) | Not used |
| Class, second | `cpla_dev13_20261105` | 8093 | 0 failed, 2 errors of 20 tests (`cpla_dev13_class2.log`) | Not used |
| Class, third | `cpla_dev13_20261105` | 8093 | 0 failed, 1 error of 20 tests (`cpla_dev13_class3.log`) | Not used |
| Class, accepted | `cpla_dev13_20261105` | 8093 | 0 failed, 0 errors of 20 tests (`cpla_dev13_class4.log`) | 20 post-tests in 42.22s, 16706 queries. Stats line: 22 tests, 42.19s, 16706 queries |
| Full tag | `cpla_dev13_20261105` | 8093 | 0 failed, 0 errors of 898 tests (`cpla_dev13_full.log`). Exit file `cpla_dev13_full.exit` is `EXIT:0` | 898 post-tests in 534.42s, 264920 queries. Stats line: 924 tests, 534.14s, 264920 queries |

The accepted class command was `-u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor:TestDev13LeakageCase`. The full command was the same database and `-u`, with `--test-tags=/contract_price_leakage_auditor`. Both logs print `Odoo version 19.0`.

The 7 errors were `account.move` reads during evidence seeding and unflushed finding identities. The 2 errors were a manager-only assignment called as the investigator, and a membership write the contract user could not perform. The last error was membership create for the same accept path. Those were fixed before the accepted class run. The full tag then loaded `security/ir.model.access.csv` and passed, including the smoke assertion for membership create.

Upgrade from `cpla_dev12_20261028` and fresh `-i` of `cpla_dev13_fresh_20261105` also finished at 0 failed, 0 errors of 898 tests. Commands and stats are in `14_installation_and_regression.md`. The case IDs below ran again inside both of those tags.

## Case test IDs

Every ID below ran inside `tests/test_leakage_case.py` on the accepted class run and again inside the 898-test tag. Result: PASS. One method covers more than one ID.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| CASE13-T001, T002, T003, T005, T006, T007, T008, T012 | Yes | PASS | `test_case13_creation_company_reference_and_reuse` |
| CASE13-T004 | Yes | PASS | `test_case13_t004_only_a_manager_opens_a_case` |
| CASE13-T009, T010 | Yes | PASS | `test_case13_t009_t010_exception_case_keeps_a_blank_amount` |
| CASE13-T011 | Yes | PASS | `test_case13_t011_historical_revision_is_not_a_second_case` |
| GRP13-T001, T003, T004, T005, T006, T007, T008 | Yes | PASS | `test_grp13_three_findings_sum_and_customer_company_currency_guards` |
| GRP13-T002 | Yes | PASS | That method, plus `test_grp13_same_invoice_order_and_version_bases` |
| GRP13-T009, T010, T011, T012 | Yes | PASS | `test_grp13_merge_and_split_preserve_findings` |
| GRP13-T013, T014 | Yes, one transaction | PASS | `test_con13_duplicate_index_rollback_and_idempotent_sync`. Not two workers |
| WF13-T001–T009, T011–T016 | Yes | PASS | `test_wf13_lifecycle_submission_return_close_and_reopen` |
| WF13-T006, T007 | Yes | PASS | That method, plus `test_wf13_required_no_answer_must_be_disclosed` |
| WF13-T010 | Yes | PASS | `test_wf13_t010_submitter_cannot_return_the_same_case` and the lifecycle method |
| OWN13-T001–T012 | Yes | PASS | `test_own13_assignment_priority_activity_and_no_threshold` |
| EVD13-T001–T011, T013, T014 | Yes | PASS | `test_evd13_evidence_history_snapshot_and_chatter` |
| EVD13-T012 | Yes | PASS | `test_evd13_submission_snapshot_survives_return` |
| FIN13-T001, T003–T005, T007–T014 | Yes | PASS | `test_fin13_exposure_revision_and_downstream_amounts` |
| FIN13-T002 | Yes | PASS | `test_fin13_t002_authorized_price_is_not_opened_as_leakage` |
| FIN13-T006 | Yes | PASS | `test_fin13_t006_credit_reassessment_does_not_invent_cash` |
| SEC13-T001–T016 | Yes | PASS | `test_sec13_company_roles_rpc_and_history` |
| CON13-T001–T008 | Yes, one transaction | PASS | `test_con13_duplicate_index_rollback_and_idempotent_sync` |
| REG13-T003–T014 | Yes | PASS | `test_reg13_views_upgrade_shape_and_no_accounting_side_effects`, plus the prior-phase tests in each 898-test tag |
| REG13-T001 | Yes | PASS | Fresh `-i` of `cpla_dev13_fresh_20261105`, 0 failed of 898. `14_installation_and_regression.md` |
| REG13-T002 | Yes | PASS | `-u` of `cpla_dev12_20261028` from `19.0.1.10.0` to `19.0.1.11.0`, 0 failed of 898 |

`test_case_ref_015_and_activity_do_not_schedule_a_cron` also passed. It logged `DEV13 sequential case open count=20 elapsed_seconds=5.196` and asserted no case cron.

## Not executed

- Two OS processes creating or merging the same case. The concurrency test logs `CON13 two-worker concurrency was NOT_EXECUTED. This test uses one transaction.`
- A before-and-after row count of audit runs already stored in `cpla_dev12_20261028`.
- Odoo 18 and Odoo 20 installation.
- A numeric speed limit. The 5.196 second figure includes invoice posting and finding insert.
