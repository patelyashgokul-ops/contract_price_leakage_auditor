# Installation and upgrade regression

Odoo 19.0 Community. Addon `contract_price_leakage_auditor` at manifest `19.0.1.14.0`. Configuration file `C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf`. Database user `odoo` on localhost port 5432. No database was dropped.

## Fresh install — REG16-T001

Database `cpla_dev16_fresh_20261105` was appended to `local_testing/disposable_databases.txt` before use. Command shape:

`python -u odoo-bin -c odoo.conf -d cpla_dev16_fresh_20261105 -i contract_price_leakage_auditor --stop-after-init --http-port=8097 --test-tags /contract_price_leakage_auditor`

Result: 0 failed, 0 errors of 941 post-tests in 875.64s. Process 17800. 2026-11-05 13:10:05. `EXIT:0`. Log `local_testing/dev16_fresh_1.log`. The log line `Initializing database cpla_dev16_fresh_20261105` records the create. Sequences, views, ACLs, and record rules loaded as part of that install. The 941 count includes the previous financial tests and the 13 recovery methods.

## Upgrade from DEV-15 — REG16-T002

`cpla_dev14b_fresh_20261105` was `19.0.1.13.0` installed, confirmed by `ir_module_module.latest_version` before the run. Command shape:

`python -u odoo-bin -c odoo.conf -d cpla_dev14b_fresh_20261105 -u contract_price_leakage_auditor --stop-after-init --http-port=8096 --test-tags /contract_price_leakage_auditor`

Result: 0 failed, 0 errors of 941 post-tests in 1018.84s. Process 24464. 2026-11-05 13:08:09. `EXIT:0`. Log `local_testing/dev16_upgrade_1.log`.

## Full regression on the development database — REG16-T018

`cpla_dev14_20261105` had already been updated to `19.0.1.14.0` by the targeted `-u`. The full command used `-u` and port 8096. Result: 0 failed, 0 errors of 941 post-tests in 1338.02s. Process 26144. 2026-11-05 12:49:26. `EXIT:0`. Log `local_testing/dev16_full_1.log`.

## What the passing regression shows

DEV-12 findings, DEV-13 cases, DEV-14 accepted revisions, and DEV-15 finance decisions still have passing tests inside the 941. Recovery, waiver, dispute, and settlement models are registered. The views test finds the recovery menus and finds no module cron, server action, or report. Move and payment counts asserted in the recovery tests stay unchanged except where an older test posts its own invoice. No recovery invoice is created by DEV-16. No payment is registered. Port 8071 was not used.
