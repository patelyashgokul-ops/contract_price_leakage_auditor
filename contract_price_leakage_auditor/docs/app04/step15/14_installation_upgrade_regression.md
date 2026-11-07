# Installation, upgrade, and regression

## Upgrade already applied

The first DEV-15 command used `-u contract_price_leakage_auditor` on `cpla_dev14_20261105`, Odoo 19.0, port 8096, process 11060, starting `2026-11-05 09:05:47`.

Log: `local_testing/cpla_dev15_targeted.log`.

The module update loaded `security/finance_validation_rules.xml`, `data/finance_validation_sequence.xml`, and the finance views. The test result of that command was `1 failed, 13 error(s) of 14 tests`, `EXIT:1`. That is not a regression pass. It does show the schema update ran.

Databases still at `19.0.1.12.0` before any later `-u`, read from `ir_module_module` on 2026-11-05:

- `cpla_dev14b_fresh_20261105`
- `cpla_dev14_fresh_20261105`
- `cpla_dev13_fresh_20261105`

## Full regression after the allowlist fix

The first full log, `local_testing/cpla_dev15_full.log`, was `3 failed, 0 error(s) of 928 tests` in 666.59s. It is not the pass.

The gap recheck, `local_testing/cpla_dev15_gap.log`, process 15132, `2026-11-05 09:37:37`, was `0 failed, 0 error(s) of 4 tests` in 32.67s, 9100 queries.

The repeat full run used `-u` on `cpla_dev14_20261105`, port 8096, process 16220.

Log: `local_testing/cpla_dev15_full2.log`.

`2026-11-05 09:52:48`. `928 post-tests in 865.85s, 298539 queries`.

`0 failed, 0 error(s) of 928 tests`. `EXIT:0`.

`odoo.tests.stats` counted 954 tests. The post-install line is the result.

## Upgrade from 19.0.1.12.0

Database `cpla_dev14b_fresh_20261105` was installed at `19.0.1.12.0` before this command. The command used `-u contract_price_leakage_auditor`, port 8096, process 22276.

Log: `local_testing/cpla_dev15_upgrade.log`.

`2026-11-05 10:08:25`. `928 post-tests in 863.88s, 298075 queries`.

`0 failed, 0 error(s) of 928 tests`. `EXIT:0`.

## Fresh install

Database `cpla_dev15_fresh_20261105` was created for this command and is listed in `local_testing/disposable_databases.txt`. The command used `-i contract_price_leakage_auditor`, port 8096, process 23332.

Log: `local_testing/cpla_dev15_fresh.log`.

`2026-11-05 10:22:55`. `928 post-tests in 679.39s, 297975 queries`.

`0 failed, 0 error(s) of 928 tests`. `EXIT:0`.

No finance cron was loaded. The passing tests did not create a recovery invoice or a payment.

No posted invoice, recovery invoice, or payment is created by the finance models. The passing finance tests compared `account.move` and `account.payment` counts around the finance actions and left them unchanged, except where the test itself posted a credit note before the comparison.
