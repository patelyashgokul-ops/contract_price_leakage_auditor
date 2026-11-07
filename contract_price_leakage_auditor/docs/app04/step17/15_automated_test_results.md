# Automated test results

Odoo 19.0. Module `contract_price_leakage_auditor` at `19.0.1.15.0`. Port 8096. `--log-level` was not set to warn. The shell `EXIT:` line is the process exit code. The `odoo.tests.result` line is the result that counts.

| Run | Database | Result | Log |
| --- | --- | --- | --- |
| Targeted, first | `cpla_dev14_20261105` | 2 failed, 1 error of 20 tests in 74.84s, 31520 queries. Process 24176. 2026-11-05 14:34:52. `EXIT:1` | `local_testing/dev17_targeted_1.log` |
| Targeted, second | `cpla_dev14_20261105` | 1 failed, 1 error of 30 tests in 121.86s, 45161 queries. Process 23032. 2026-11-05 14:54:06. `EXIT:1` | `local_testing/dev17_targeted_2.log` |
| Targeted, third | `cpla_dev14_20261105` | 0 failed, 0 errors of 30 tests in 100.75s, 45173 queries. Process 19644. 2026-11-05 15:00:42. `EXIT:0` | `local_testing/dev17_targeted_3.log` |
| Full regression | `cpla_dev14_20261105` | 0 failed, 0 errors of 969 tests in 853.41s, 351857 queries. Process 20972. 2026-11-05 15:16:45. `EXIT:0` | `local_testing/dev17_full_1.log` |
| Upgrade from `19.0.1.14.0` | `cpla_dev16_fresh_20261105` | 0 failed, 0 errors of 969 tests in 1075.90s, 351079 queries. Process 8268. 2026-11-05 15:35:57. `EXIT:0` | `local_testing/dev17_upgrade_1.log` |
| Fresh `-i` | `cpla_dev17_fresh_20261105` | 0 failed, 0 errors of 969 tests in 1063.04s, 350953 queries. Process 17760. 2026-11-05 15:38:47. `EXIT:0`. Installed version read back as `19.0.1.15.0`. | `local_testing/dev17_fresh_1.log` |

The first two targeted logs are not passes. The third targeted log is the pass for the 28 `test_bill17_*` methods plus `test_rec16_views_and_no_accounting` and `TestDev02Security.test_sec_t005_auditor_has_no_financial_write_authority`.

Catalog IDs are not separate test methods. Coverage inside the passing targeted run:

| Prompt group | Executed as | Result |
| --- | --- | --- |
| BIL17-T001 through T016 and T018 | Policy, draft, post, partial slice, existing document, stale post, security, and lock-date methods | Pass |
| BIL17-T017 | `test_bill17_debit_note_method` | Pass. `account.debit.note` is not installed, so the method raises `ACCOUNTING_METHOD_UNAVAILABLE` and does not create a standalone invoice |
| TAX17-T001 through T004 | `test_bill17_tax_is_not_principal` | Pass. Principal 20000, tax 3600, gross 23600, payment 11800 attributes principal 10000 |
| TAX17-T005 through T007 | No separate fiscal-position or tax-included fixture | Not a separate executed method |
| FX17-T001 through T007 | `test_bill17_fx_difference_not_executed` | The selection key exists and no `res.currency` is created. GOLD-ACC17-014 remains `NOT_EXECUTED` |
| PAY17-T001 through T009, T011 through T016 | Payment, multi-invoice, three-payment, advance, reversal, and security methods | Pass |
| PAY17-T010 | `test_bill17_advance_is_not_new_cash` | Pass. The advance is not verified cash |
| CRD17-T001 through T012 | Credit, unrelated credit, full offset, write-off, and credit-plus-cash methods | Pass |
| AGE17-T001 through T008 | Partial slices, golden cash, tax residual, and installment aging | Pass |
| AGE17-T009 through T012 | Future-due and dispute are fields on the position. No separate method asserts a future due date or an unknown residual source by itself | Partial |
| FIN17-T001 through T016 | `test_bill17_golden_posted_and_bank_cash` and the credit, write-off, and FX methods | Pass for the executed amounts. FX principal separation is the selection key only |
| SEC17-T001 through T008 and T012 | `test_bill17_security_company_and_four_eyes` and `test_sec_t005_auditor_has_no_financial_write_authority` | Pass |
| SEC17-T009 through T011 | Export denial is inside the security method. Attachment and confidential payment reference checks are the existing guards, not new methods | Partial |
| CON17-T001 and T003 | `test_bill17_concurrent_prepare` | Pass. The unique index rejected the second insert |
| CON17-T009 | `test_bill17_failed_read_is_not_zero` | Pass. The error text contains `TECHNICAL_ACCOUNTING_FAILURE` |
| CON17-T002, T004 through T008, T010 | Not separate two-worker methods | `NOT_EXECUTED` as distinct tests. The passing suite does not prove those races |
| REG17-T001 through T018 | Full, upgrade, and fresh | Each passed: 0 failed, 0 errors of 969 |

No catalog row above is a pass unless this table says Pass.
