# 08 — Installation and regression

Date: 2026-10-28.

Environment:

- Odoo log: `Odoo version 19.0`
- Interpreter: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`
- Server: `C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin`
- Config: `C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf`
- Database user in the log: `odoo@localhost:5432`
- Addon: `contract_price_leakage_auditor` `19.0.1.2.0`
- Disposable database: `cpla_dev04_20261028`
- Flags: `--without-demo=True --http-interface=127.0.0.1 --stop-after-init`
- Test tag: `--test-tags=/contract_price_leakage_auditor`

The HTTP service bound `DESKTOP-U954VF2:8069` for the stop-after-init process and then shut down. That was not a browser session.

Expected manifest warning, seen on the fresh install at 2026-10-28 05:31:03 (twice) and 05:31:15:

`Missing author key in manifest for 'contract_price_leakage_auditor', defaulting to ''`

Author stays empty on purpose.

## Fresh installation of the corrected module

Before the command, `python local_testing/free_space.py` dropped only names listed in `local_testing/disposable_databases.txt` that start with `cpla_`:

- `cpla_dev01_foundation_20261028` (already absent; `DROP DATABASE IF EXISTS` still reported dropped)
- `cpla_dev03_fresh_20261028` (same)
- `cpla_dev04_20261028` (the earlier test database and its filestore)

No other database name was passed to `DROP DATABASE`.

Command shape:

`-d cpla_dev04_20261028 -i contract_price_leakage_auditor`

Started 2026-10-28 05:31:00. Database initialization log: `Initializing database cpla_dev04_20261028`.

`Module contract_price_leakage_auditor loaded in 0.74s, 503 queries (+503 other)` at 05:31:33.

Exit code 0 at 05:32:17.

`0 failed, 0 error(s) of 155 tests when loading database 'cpla_dev04_20261028'`

`account` was not installed. REG04-T010 asserts `account.move` is absent from the registry.

## Earlier install and the upgrade that found the defect

First `-i` on the same database name, 2026-10-28 05:24:50–05:26:06, loaded the module and then failed tests: `3 failed, 2 error(s) of 155 tests`, exit 1. The module rows were committed. The five failures are listed in file 07.

After the owner-constraint and assertion fixes, `-u contract_price_leakage_auditor` on that database, 2026-10-28 05:29:41–05:30:04, exit 0:

`0 failed, 0 error(s) of 155 tests when loading database 'cpla_dev04_20261028'`

That database was then dropped so the fresh `-i` above could create it again. The upgrade log is the evidence that `-u` loaded the corrected Python.

## REG04-T002

Upgrade from an accepted DEV-03 database was **not executed**.

`cpla_dev01_foundation_20261028` and `cpla_dev03_fresh_20261028` were removed in the earlier local-testing cleanup. This phase did not recreate a `19.0.1.1.0` database. The `-u` above started from `19.0.1.2.0` after a failed test run of that same version. It shows that the module update path loads. It does not show a migration from the DEV-03 schema to the contract schema on a preserved DEV-03 copy.

Company policy behavior was still exercised inside the green suites: current revision, submit for business review, activation refused, eight groups, and the original policy ACL rows plus the one new read-only Contract User row.

## Regression

The green fresh install ran the addon tag, which includes:

- `tests/test_foundation_smoke.py`
- `tests/test_security_foundation.py`
- `tests/test_company_policy.py`
- `tests/test_customer_contract.py`

No failure. Historical step 03 documents still describe their own 73-test runs. Those documents were not edited to pretend this install happened earlier.

## Views

REG04-T005 calls `get_view` for the contract list, form, and search, and for the policy form. The form architecture contains the not-an-approved-price banner and does not contain `decoration-success`. No browser tool was used. Click-through of the menu was not verified.

## What was not installed

No invoice audit cron. No dashboard. No accounting records. No currency was activated. No exchange rate was inserted by the contract tests that assert rate counts.
