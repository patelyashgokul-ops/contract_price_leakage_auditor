# Installation and regression

## Fresh installation

Database `cpla_dev08_20261028` did not exist before `-i`. The log says `Initializing database cpla_dev08_20261028`.

Command shape: venv `python.exe -u odoo-bin -c odoo.conf -d cpla_dev08_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init`.

Result in `C:\Users\Admin\AppData\Local\Temp\cpla_dev08_fresh.log`: `0 failed, 0 error(s) of 552 tests`, `552 post-tests in 228.81s, 97574 queries`, exit 0.

Depends remained `base` and `product`. No `account.move` data and no `ir.cron` were created by the module. REG08-T009 and REG08-T010 assert that.

## Update from DEV-07

Database `cpla_dev07_20261028` was the fresh 19.0.1.5.0 database. It was updated in place to `19.0.1.6.0`. It was not dropped. `cpla_dev04_20261028`, `cpla_dev05_20261028`, and `cpla_dev06_20261028` were not dropped. Port 8069 was not used.

| Log | Outcome |
| --- | --- |
| `cpla_dev08_upgrade.log` | `2 failed, 0 error(s) of 552 tests`, exit 1 |
| `cpla_dev08_upgrade2.log` | `0 failed, 0 error(s) of 552 tests`, `125.69s`, `97519 queries`, exit 0 |
| `cpla_dev08_upgrade3.log` | `0 failed, 0 error(s) of 553 tests`, `174.88s`, `97850 queries`, exit 0 |

The first failure did not change contract prices. The two assertions compared text shape and `False` with `0`. The reruns passed, including existing version, tier, security, and applicability tests.

Unconfigured upgraded versions stay `fx_policy = unconfigured`. No rate row is created for them. Approved quantity tiers remain. Company policy `operationally_approved` stays false.

`cpla_dev08_20261028` is listed in `local_testing/disposable_databases.txt`.
