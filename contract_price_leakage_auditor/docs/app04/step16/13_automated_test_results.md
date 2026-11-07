# Automated test results

Odoo 19.0. Module `contract_price_leakage_auditor`. Port 8096 except the fresh install, which used port 8097. `--log-level` was not set to warn. The shell `EXIT:` line is the process exit code appended by the launcher. The Odoo line below is the result that counts.

| Run | Command shape | Database | Result | Log |
| --- | --- | --- | --- | --- |
| Targeted rerun | `-u`, 13 `test_rec16_*` tags | `cpla_dev14_20261105` | 0 failed, 0 errors of 13 tests in 179.40s, 22586 queries. Process 25680. 2026-11-05 12:25:36. `EXIT:0` | `local_testing/dev16_targeted_2.log` |
| Full regression | `-u --test-tags /contract_price_leakage_auditor` | `cpla_dev14_20261105` | 0 failed, 0 errors of 941 tests in 1338.02s, 314495 queries. Process 26144. 2026-11-05 12:49:26. `EXIT:0` | `local_testing/dev16_full_1.log` |
| Upgrade from `19.0.1.13.0` | `-u`, same tag | `cpla_dev14b_fresh_20261105` | 0 failed, 0 errors of 941 tests in 1018.84s, 313948 queries. Process 24464. 2026-11-05 13:08:09. `EXIT:0` | `local_testing/dev16_upgrade_1.log` |
| Fresh install | `-i`, same tag | `cpla_dev16_fresh_20261105` | 0 failed, 0 errors of 941 tests in 875.64s, 313771 queries. Process 17800. 2026-11-05 13:10:05. `EXIT:0` | `local_testing/dev16_fresh_1.log` |

`local_testing/dev16_targeted_1.log` is the failed first targeted run: 1 failed, 3 errors of 11 tests, process 21996, `EXIT:1`. It is not a pass.

The 13 methods are bound onto `TestDev12InvoiceAudit` from `tests/test_recovery_authorization.py`. They are not a second chart. Catalog IDs in the prompt are not separate methods. Coverage:

| Prompt group | Executed as | Result |
| --- | --- | --- |
| REC16-T001 through T012 | `test_rec16_full_recovery_and_partial_waiver`, `test_rec16_partial_waiver_reconciliation`, `test_rec16_excess_waiver_and_duplicate_and_partial_split`, `test_rec16_nonoverlapping_partial_requests`, `test_rec16_finance_rejection_not_waiver`, `test_rec16_stale_blocks_new_approval` | Pass inside the 13 and the 941 |
| WAV16-T001 through T016 | Waiver paths in the partial-waiver, undecided, excess, finance-rejection, and concurrent methods | Pass. Multi-level waiver is the partial-waiver method. No accounting write-off is the unchanged move count |
| DSP16-T001 through T014 | `test_rec16_dispute_acknowledgement_silence` | Pass. Source reassessment is requested and does not call `action_reassess` |
| SET16-T001 through T014 | `test_rec16_settlement_counteroffer_and_extra_waiver` and the stale waiver prepare | Pass |
| FIN16-T001 through T016 | Equation assertions in the golden methods, plus `test_rec16_currency_ceiling` | Pass. Billed and collected stay 0 |
| INT16-T001 through T012 | Finance, case, and finding links on the request lines. Handoff payload in the full-recovery and settlement methods. Move counts unchanged | Pass. INT16-T010 has no posted DEV-17 bill to block. The zero billed fields are the guard |
| SEC16-T001 through T016 | `test_rec16_wrong_company_and_security` plus self-approval and finance-denial assertions in the recovery and waiver methods | Pass |
| CON16 | See `15_performance_and_concurrency.md` | CON16-T002, T007, and T008 executed. The other concurrent IDs were not two-worker tests |
| REG16-T001 through T018 | Fresh, upgrade, and full runs | Pass. No recovery cron. Prior financial tests are inside the 941 |

No test was marked passed without one of the logs above.
