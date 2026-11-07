# Installation, upgrade, and regression

Odoo 19.0 Community. Interpreter `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`. Config `C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf`. Direct depends stay `base`, `product`, and `sale`.

## Versions read from PostgreSQL on 2026-11-05

| Database | `ir_module_module.latest_version` |
| --- | --- |
| `cpla_dev14_20261105` | `19.0.1.15.0` installed. This is the database under the DEV-17 `-u` runs |
| `cpla_dev14b_fresh_20261105` | `19.0.1.14.0` installed |
| `cpla_dev16_fresh_20261105` | `19.0.1.14.0` installed |
| `cpla_dev15_fresh_20261105` | `19.0.1.13.0` installed |

The upgrade source for DEV-17 is a database still at `19.0.1.14.0`. `cpla_dev16_fresh_20261105` is the intended target. It has not been upgraded in this phase yet.

## Executed

Targeted `-u` on `cpla_dev14_20261105` passed. See `15_automated_test_results.md`. Module update to `19.0.1.15.0` was committed by those `-u` runs before the tests.

## Full regression

`-u contract_price_leakage_auditor --test-tags /contract_price_leakage_auditor` on `cpla_dev14_20261105`, port 8096. 0 failed, 0 errors of 969 tests in 853.41s, 351857 queries. Process 20972. 2026-11-05 15:16:45. `EXIT:0`. Log `local_testing/dev17_full_1.log`. The DEV-16 baseline on this database was 941 tests. The added 28 `test_bill17_*` methods account for 969.

## Upgrade from DEV-16

`-u contract_price_leakage_auditor --test-tags /contract_price_leakage_auditor` on `cpla_dev16_fresh_20261105`, which was `19.0.1.14.0` before this run. Port 8096. 0 failed, 0 errors of 969 tests in 1075.90s, 351079 queries. Process 8268. 2026-11-05 15:35:57. `EXIT:0`. Log `local_testing/dev17_upgrade_1.log`.

## Fresh installation

`-i contract_price_leakage_auditor --test-tags /contract_price_leakage_auditor` on `cpla_dev17_fresh_20261105`, port 8097. The name was appended to `local_testing/disposable_databases.txt` before `-d`. 0 failed, 0 errors of 969 tests in 1063.04s, 350953 queries. Process 17760. 2026-11-05 15:38:47. `EXIT:0`. Log `local_testing/dev17_fresh_1.log`. PostgreSQL readback: `latest_version` `19.0.1.15.0`, state `installed`.

No production database was used. Databases listed as preserved in earlier phases were not dropped.
