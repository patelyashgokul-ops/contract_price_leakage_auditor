# 10 — Installation and regression

Date: 2026-10-28.

Odoo logged `Odoo version 19.0`. Interpreter: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`. Addon: `contract_price_leakage_auditor` `19.0.1.3.0`. HTTP port 8071. The freight addon server on port 8069 was not stopped and was not modified.

## Fresh installation

Database: `cpla_dev05_20261028`. Listed in `local_testing/disposable_databases.txt`. Created by this `-i`. It did not exist before 2026-10-28 07:32 UTC.

```text
C:\PycharmProjects\odoo19\.venv\Scripts\python.exe -u C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin -c C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf -d cpla_dev05_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev05_fresh.log`.

- Start: 2026-10-28 07:32:23 UTC. `Initializing database cpla_dev05_20261028`.
- Module load: 07:33:03 UTC. `Modules loaded.` at 07:33:36 UTC.
- Result: 2026-10-28 07:34:08 UTC. `0 failed, 0 error(s) of 242 tests when loading database 'cpla_dev05_20261028'`.
- Stats: `252 tests 31.91s 30369 queries` and `242 post-tests in 32.00s, 30369 queries`.
- Wrapper exit code: 0.

## Upgrade from the DEV-04 database

Database: `cpla_dev04_20261028`. This database was the green DEV-04 fresh install. It was not dropped.

The first `-u` on 2026-10-28 06:33 UTC loaded the DEV-05 models and ran 242 tests. That run failed (`1 failed, 77 error(s) of 242 tests`). Two later `-u` runs also failed. The passing `-u` at 07:30 UTC is a repeat update of that same database after the code fixes. It is not a restore of an untouched `19.0.1.2.0` backup. No such backup was kept. The passing command:

```text
C:\PycharmProjects\odoo19\.venv\Scripts\python.exe -u C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin -c C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf -d cpla_dev04_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev05_upgrade4.log`.

- Start: 2026-10-28 07:30:43 UTC.
- Registry: `module contract_price_leakage_auditor: creating or updating database tables` at 07:30:48 UTC.
- Result: 2026-10-28 07:31:22 UTC. `0 failed, 0 error(s) of 242 tests when loading database 'cpla_dev04_20261028'`.
- Stats: `252 tests 31.45s 30317 queries` and `242 post-tests in 31.48s, 30317 queries`.
- Wrapper exit code: 0.

`cpla_dev01_foundation_20261028` and `cpla_dev03_fresh_20261028` were already gone before DEV-05. An upgrade from those databases was not run. Status: NOT_EXECUTED.

## Checks from section 44

| Check | Evidence |
| --- | --- |
| Fresh installation | Run 5, exit 0, 0 failed. |
| Upgrade from the DEV-04 database | Run 4, exit 0, 0 failed. First migration attempt was run 1 and its tests failed. |
| Contract header and lines preserved | REG05-T003 and REG05-T004 passed inside both green suites. DEV-04 did not leave committed business contracts in that database. |
| No automatic false approvals | CONTRACT-V001 passed. Header states are still draft, ready for review, and cancelled. |
| Version, line, and event models installed | Run 5 loaded the module. SEC-T007's model set includes the four version models and the compare wizard. |
| ACLs, rules, and views load | REG05-T006 and REG05-T007 passed. |
| No duplicate menus | New menus are Contract Versions and Amendment Review. They do not reuse Customer Pricing Contracts or Configuration. |
| Prior-phase tests | The same 242 includes the earlier post-tests. Result 0 failed. |
| No accounting or invoice-audit jobs | REG05-T008 and REG05-T009 passed. |

Before run 4, two committed policies on companies named `CPLA05 Conc Pool …` were deleted from `cpla_dev04_20261028`. Those rows were concurrency-test leftovers from runs 2 and 3. The companies themselves were left in place. No other company policy was deleted. The class cleanup now repeats that delete for pool companies only, using SQL that nulls restrict foreign keys first.

## Concurrency note

`lock_for_update` is `FOR UPDATE SKIP LOCKED`. It raises `LockError` immediately. It does not wait. Two approvers can also receive PostgreSQL `SerializationFailure: could not serialize access due to concurrent update`. Product code does not catch that error and does not turn it into a second approval. The losing transaction aborts. Runs 4 and 5 each show that error once, inside CON05-T001, and the test still passes with one approved version.
