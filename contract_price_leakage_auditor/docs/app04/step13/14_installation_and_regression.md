# Installation and regression

Commands ran from `C:\PycharmProjects\odoo19\odoo-19.0` with `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`. `--without-demo=True`, `--http-interface=127.0.0.1`, `--http-port=8093`, `--stop-after-init`. Port 8071 is in use by another project and was not used for these runs. Disposable names were already listed in `local_testing/disposable_databases.txt`. `cpla_dev12_20261028` and `cpla_dev12_fresh_20261028` were not dropped.

Each log prints `Odoo version 19.0`. Each result line is 0 failed, 0 errors of 898 tests. The exit files are `EXIT:0`.

## Full tag on the DEV-13 database

```
python -u odoo-bin -c odoo.conf -d cpla_dev13_20261105 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8093 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev13_full.log`. Started 2026-11-05 03:51:14. Result 2026-11-05 04:00:28. `898 post-tests in 534.42s, 264920 queries`. Stats line: `924 tests 534.14s 264920 queries`.

## Upgrade from DEV-12

Before the command, `ir_module_module` on `cpla_dev12_20261028` was `19.0.1.10.0`, state `installed`.

```
python -u odoo-bin -c odoo.conf -d cpla_dev12_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8093 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev13_upgrade.log`. Started 2026-11-05 04:02:31. Registry loaded in 24.910s. The update loaded `security/leakage_case_rules.xml`, `data/case_sequence.xml`, and `views/leakage_case_views.xml`. Result 2026-11-05 04:12:53. `898 post-tests in 594.87s, 264892 queries`. Stats line: `924 tests 594.60s 264892 queries`.

After the command, the same module row was `19.0.1.11.0`, state `installed`. Case tables present: `cpla_leakage_case`, membership, event, checklist, evidence, submission, and the wizard. Module-owned `ir.cron` rows: 0. No before-and-after count of existing audit-run rows was taken.

## Fresh installation

`cpla_dev13_fresh_20261105` did not exist before this command. Odoo initialized it.

```
python -u odoo-bin -c odoo.conf -d cpla_dev13_fresh_20261105 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8093 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev13_fresh.log`. Started 2026-11-05 04:13:39. The log says `Initializing database cpla_dev13_fresh_20261105`. Registry loaded in 163.992s. `case_sequence.xml` and `leakage_case_views.xml` loaded. Result 2026-11-05 04:27:34. `898 post-tests in 663.73s, 264909 queries`. Stats line: `924 tests 663.35s 264909 queries`.

## Prior-phase regression

The 898 count is the DEV-12 full-tag count of 878 plus the 20 methods in `TestDev13LeakageCase`. The same 898 passed on the DEV-13 database, on the upgrade from `19.0.1.10.0`, and on the fresh install. DEV-01 through DEV-12 tests are inside that tag.

`test_reg13_views_upgrade_shape_and_no_accounting_side_effects` checks version `19.0.1.11.0`, depends `base`, `product`, `sale`, case menus, the case sequence, global company rules, no module cron, and no change to the invoice price, move count, or payment count when a case opens.

## Log lines that are not failures

Each full log contains PostgreSQL `ERROR: duplicate key value` lines for `cpla_leakage_finding_current_identity_unique`, `cpla_invoice_source_map_current_line_unique`, and `cpla_leakage_case_membership_current_finding_unique`. Those statements run inside tests that expect `IntegrityError` and roll the savepoint back. The result line remains 0 failed, 0 errors.

## Odoo 18 and Odoo 20

Not installed and not converted. The Odoo 19 pieces that would need a separate pass are `models.Constraint`, `models.UniqueIndex` with a WHERE clause, `mail.thread`, `mail.activity.mixin`, the form `<chatter/>` tag, kanban `t-name="card"`, attachment checks, and the test APIs used here. Odoo 19 remains the master implementation.

## Class run that preceded these tags

Accepted class log `cpla_dev13_class4.log`: 0 failed, 0 errors of 20 tests, 20 post-tests in 42.22s, 16706 queries, port 8093, database `cpla_dev13_20261105`. Earlier class logs on that database were 7 errors, then 2 errors, then 1 error. Those are not the acceptance runs. Detail is in `13_automated_test_results.md`.
