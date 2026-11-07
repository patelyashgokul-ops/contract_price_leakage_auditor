# Installation, upgrade, and regression

Date: 2026-11-05. Odoo 19.0. Interpreter `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`. Config `C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf`. Addon `contract_price_leakage_auditor` `19.0.1.12.0`.

## Update and full tag

Database `cpla_dev14_20261105`. The database already had the addon at `19.0.1.12.0` before this run. The command still used `-u`.

```
odoo-bin -c odoo.conf -d cpla_dev14_20261105 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8093 --stop-after-init
```

Log `cpla_dev14_full3.log`. PID 23288. 2026-11-05 07:37:40.

`0 failed, 0 error(s) of 914 tests`. `914 post-tests in 1142.10s, 282679 queries`. Stats line: 940 tests. Shell exit 0.

An earlier `-u` on this database, `cpla_dev14_full2.log`, was stopped. It failed company-policy and finding counts because the concurrency fixture had been committed. That log is not a result. The fixture is now removed at the start of `TestDev03CompanyPolicy` and again when `TestDev12InvoiceAudit` ends.

## Upgrade from 19.0.1.11.0

Database `cpla_dev13_fresh_20261105`. Before the command, `ir_module_module.latest_version` was `19.0.1.11.0` and state was `installed`. This database had no concurrency-pool company.

```
odoo-bin -c odoo.conf -d cpla_dev13_fresh_20261105 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8094 --stop-after-init
```

Log `cpla_dev14_upgrade3.log`. PID 12488. 2026-11-05 07:56:41.

`0 failed, 0 error(s) of 914 tests`. `914 post-tests in 1003.76s, 282511 queries`. Stats line: 940 tests. Shell exit 0.

After the run, `latest_version` is `19.0.1.12.0` and state is `installed`.

`cpla_dev13_20261105` was already `19.0.1.12.0` from the earlier pre-37 upgrade. It was not the database for this from-11.0 run. `cpla_dev14_upgrade2.log` on that database was stopped and is not a result.

No before/after counts were stored for contract versions, audit results, findings, cases, discount approvals, or refund mappings that already existed in the database. The passing suite shows those models still load and their tests pass. It is not a row-preservation audit.

## Fresh install

`cpla_dev14b_fresh_20261105` is listed in `local_testing/disposable_databases.txt`. It did not exist before this command.

```
odoo-bin -c odoo.conf -d cpla_dev14b_fresh_20261105 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8095 --stop-after-init
```

Log `cpla_dev14_fresh2.log`. PID 7420. 2026-11-05 08:10:04.

`0 failed, 0 error(s) of 914 tests`. `914 post-tests in 537.29s, 282519 queries`. Stats line: 940 tests. Shell exit 0. The log also records the expected finding, source-map, and case unique-constraint errors, and `could not serialize access due to concurrent update`. Those lines did not fail the run.

The earlier fresh install `cpla_dev14_fresh.log` on `cpla_dev14_fresh_20261105` was 0 failed of 909 tests on the pre-37 code. It is not evidence for sections 37–69.

## What the 914 runs include

The addon tag runs the DEV-01 through DEV-14 test modules. Both finished runs include the DEV-12 financial tests and the DEV-13 case tests. Neither run posted a recovery document or registered a payment in `test_rev14_t001`. That method also asserts that this module has no `ir.cron` data.

## Databases left in place

Do not drop `cpla_dev12_20261028`, `cpla_dev12_fresh_20261028`, `cpla_dev13_20261105`, `cpla_dev13_fresh_20261105`, `cpla_dev14_20261105`, `cpla_dev14_fresh_20261105`, or `cpla_dev14b_fresh_20261105`.
