# DEV-17 progress

Manifest in code: `19.0.1.15.0`. Odoo 19.0 Community. Addon `contract_price_leakage_auditor`. Business acceptance: PENDING. License: `BLOCKER_LICENSE_DECISION_REQUIRED`. Commercial release: NO-GO. DEV-18 is not started.

Implementation of billing, collection classification, security, and the 28 automated methods is in the addon. Targeted, full, upgrade, and fresh logs are in `15_automated_test_results.md` and `16_installation_upgrade_regression.md`. Each of the three full gates was 0 failed, 0 errors of 969 tests.

| Task | Status | Evidence |
| --- | --- | --- |
| DEV17-01 | COMPLETED | DEV-16 remains `position_for()` billed and collected `0`. Finance source is unchanged. |
| DEV17-02 | COMPLETED | Payment, partial reconcile, statement, and reversal behavior used by the tests is the installed Odoo 19 Accounting code. |
| DEV17-03 | COMPLETED | `account.debit.note` is absent. `test_bill17_debit_note_method` blocks that method. |
| DEV17-04 | COMPLETED | `test_bill17_multi_invoice_payment_uses_this_receivable` and the bank-match helper. |
| DEV17-05 | COMPLETED | Policy model. No seeded journal, account, or tax. |
| DEV17-06 | COMPLETED | `01_accounting_recovery_architecture.md`. |
| DEV17-07 through DEV17-22 | COMPLETED | Billing header, lines, links, policy, handoff checks, four methods, draft, debit-note guard, existing link, posting gate, tax split, currency guard, post state, partial slices, identity unique index, credit linkage. |
| DEV17-23 through DEV17-38 | COMPLETED | Evidence resolver, partial keys, allocation, bank labels, pending payments, advances, noncash credits, write-off classification without creating a move, FX key, cash principal, unbilled, outstanding, aging, exceptions, stale posted flag, evidence history. |
| DEV17-39 through DEV17-40 | COMPLETED | Menus under Recovery Management and `reconciliation_report`. Partially collected, outstanding, and exception menus were not given a stored Paid flag. |
| DEV17-41 through DEV17-44 | COMPLETED | 30 ACL rows, six company rules, export gate, no `sudo(`, identity lock. |
| DEV17-45 through DEV17-52 | COMPLETED | 28 `test_bill17_*` methods bound on `TestDev12InvoiceAudit`. Catalog IDs that are not separate methods are listed in `15_automated_test_results.md`. |
| DEV17-53 | COMPLETED | Full `-u`: 0 failed, 0 errors of 969 tests in 853.41s. `local_testing/dev17_full_1.log`. |
| DEV17-54 | COMPLETED | Fresh `-i` of `cpla_dev17_fresh_20261105`: 0 failed, 0 errors of 969 in 1063.04s. Installed `19.0.1.15.0`. `local_testing/dev17_fresh_1.log`. |
| DEV17-55 | COMPLETED | Upgrade `-u` of `cpla_dev16_fresh_20261105` from `19.0.1.14.0`: 0 failed, 0 errors of 969 in 1075.90s. `local_testing/dev17_upgrade_1.log`. |
| DEV17-56 | COMPLETED | The 969-test run includes the earlier-phase regression. |
| DEV17-57 | COMPLETED | Targeted golden, tax, credit, and cash assertions passed. FX collection scenario remains `NOT_EXECUTED`. |
| DEV17-58 | COMPLETED | Measured targeted timings are in `17_performance_concurrency_review.md`. No invented benchmark. |
| DEV17-59 | COMPLETED | Traceability below. |
| DEV17-60 | COMPLETED | `docs/app04/step17/` files 01 through 19. Result files name logs that exist and mark the rest `NOT_EXECUTED` or in progress. |
| DEV17-61 | COMPLETED | `19_dev18_handoff.md`. No cron was added. |
| DEV17-62 | COMPLETED | Decision `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING`. Business acceptance is pending. GOLD-ACC17-014 remains `NOT_EXECUTED`. |

## Traceability

| Item | Status |
| --- | --- |
| P0-E | DEV-16 authorization is the billing source. Unapproved, stale, waived, disputed, and open-settlement requests are blocked. |
| P0-F | Draft and posted recovery documents, native payment partials, bank verification, credits, and outstanding principal. |
| P0-G | Historical posted principal, reversal rows, and source fingerprints stay. A stale source flags review and does not rewrite the invoice. |
| P0-H | Idempotent prepare and one concurrent billing test. No scheduler. |
| P0-J | 28 methods in the targeted pass. Full, upgrade, and fresh each 0 failed, 0 errors of 969. |
| CPL-ACC-001 through CPL-ACC-012, CPL-ACC-014 through CPL-ACC-020 | Exercised by the methods named in `14_golden_accounting_fixtures.md` and `15_automated_test_results.md`. |
| CPL-ACC-013 | FX classification key only. The USD 100 / 8400 / 8500 case is `NOT_EXECUTED`. |
| FIN-08, FIN-09, FIN-11 through FIN-16 | Targeted tests keep evidence, one current slice, and separate validated, billed, and cash figures. |
| FIN-10 | Supported reversal and payment unreconcile update the current view and keep history. |
| FIN-17A through FIN-17G | Draft versus posted, posted versus cash, credit versus cash, tax versus principal, FX versus principal, invoice-specific allocation, and failed-read behavior. |
| SEC-01 through SEC-06, SEC-08 through SEC-10, SEC-12 | Company rules, export gate, four-eyes, and protected writes. SEC-08 batch processing is the prepare path, not a cron. |

## Acceptance

Decision: `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING`. Full, upgrade, and fresh each passed with 0 failed, 0 errors of 969. Formal business acceptance still needs a reviewer. License remains `BLOCKER_LICENSE_DECISION_REQUIRED`. Commercial release remains NO-GO. GOLD-ACC17-014 was not executed because no stored exchange rate was used and this phase does not create `res.currency`. Several catalog concurrency IDs were not separate two-worker tests. This phase does not make APP 04 production-ready. DEV-18 was not started.

## Odoo 18 and Odoo 20

Not converted. Retest move posting, debit notes, refunds, payments, partial reconciles, `payment_state`, outstanding accounts, statement lines, taxes, exchange moves, journals, company fields, views, groups, and the financial tests before claiming either version.

## User interface

Recovery Management children added in `views/billing_views.xml`: Recovery Billing, Recovery Billing Policies, Recovery Billing Requests, Draft Recovery Documents, Posted Recovery Documents, Recovery Accounting Links, Recovery Collections, Bank Verification Pending, Recovery Credits and Adjustments, Overdue Recovery. Groups are contract user, contract manager, finance reviewer, finance manager, and internal auditor. Smart buttons on the billing form open the request, the original invoice, and the accounting document. There is no cron.
