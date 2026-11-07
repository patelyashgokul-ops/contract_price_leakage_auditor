# 04 — Installation and smoke tests

Date: 2026-10-28.
Secrets from `odoo.conf` are not copied here. `admin_passwd` and `db_password` were not printed.

## Environment

| Item | Value |
| --- | --- |
| Odoo source | `C:\PycharmProjects\odoo19\odoo-19.0` |
| Version | 19.0.0 final. Log line: `Odoo version 19.0`. |
| Interpreter | `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe` (Python 3.11.9). |
| Configuration | `C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf` |
| Database user / host | `odoo` at `localhost:5432`. Password redacted. |
| Addons paths in the log | Odoo `odoo/addons`, the user OpenERP 19.0 addons directory, `odoo-19.0\addons`, and `custom_addons`. |
| Database | `cpla_dev01_foundation_20261028` |
| Database origin | Created empty for this phase from `template1` after existing databases were listed and left untouched. |
| Production | Not used. The database was not selected because its name contained "test". |

The system Python 3.11.9 can print the Odoo version, but an install attempt with it failed before schema creation: `AttributeError: module 'lib' has no attribute 'GEN_EMAIL'` in the user-site `OpenSSL` package while Odoo imported mail-server code. That is an interpreter packaging mismatch, not an addon defect. The failed attempt did not initialize the new database. All successful commands used the project virtualenv, where the OpenSSL import works.

## Install

Command:

```text
C:\PycharmProjects\odoo19\.venv\Scripts\python.exe C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin -c C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf -d cpla_dev01_foundation_20261028 -i contract_price_leakage_auditor --test-enable --stop-after-init --without-demo=True --http-port=8079
```

`--without-demo=all` was not used. Odoo 19 logs that `all` is an invalid boolean and assumes True. `--http-port=8079` avoided the default port. This first command did not pass `--http-interface`, so Odoo warned that it used `0.0.0.0` and that Odoo 20 will default to `127.0.0.1`.

Log evidence:

- `Initializing database cpla_dev01_foundation_20261028`
- Missing-author warning for this addon.
- `Loading module contract_price_leakage_auditor (2/15)`
- `loading contract_price_leakage_auditor/security/security_groups.xml`
- `Module contract_price_leakage_auditor loaded in 0.08s, 70 queries (+70 other)`
- `Registry loaded in 233.864s`
- All eight `TestDev01Foundation` methods started. No FAIL or ERROR line was logged for them.

The process was then stopped. `--test-enable` on a fresh database also runs the standard suite of auto-installed Community modules. That suite was still running, and it had already logged failures that are not part of this addon:

- `Module base: 3 failures, 14 errors of 983 tests`
- `Module base_import_module: 1 failures, 0 errors of 8 tests`

Those core results were not treated as APP 04 defects and core was not edited. Because the process was stopped, that first command has no successful process exit code. The database had already committed the install: a later read showed `contract_price_leakage_auditor` state `installed`, version `19.0.1.0.0`.

## Update

Command, exit code 0:

```text
C:\PycharmProjects\odoo19\.venv\Scripts\python.exe C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin -c C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf -d cpla_dev01_foundation_20261028 -u contract_price_leakage_auditor --stop-after-init --without-demo=True --http-port=8079 --http-interface=127.0.0.1
```

Log evidence:

- `Loading module contract_price_leakage_auditor (2/15)`
- `loading contract_price_leakage_auditor/security/security_groups.xml`
- `Module contract_price_leakage_auditor loaded in 0.22s, 71 queries (+71 other)`
- `Modules loaded.`
- `Registry loaded in 5.876s`
- `Initiating shutdown`
- No XML ID duplication error.

A read-only query after the update, with the password not printed, showed:

- Module still `installed`, `19.0.1.0.0`, license `Other proprietary`, author empty.
- 15 XML IDs, 0 duplicates.
- `account` and `sale` still `uninstalled`.
- 0 business models in the reserved name prefixes.
- 0 access rows and 0 crons owned by the module.

## Module-scoped tests

Command, exit code 0:

```text
C:\PycharmProjects\odoo19\.venv\Scripts\python.exe C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin -c C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf -d cpla_dev01_foundation_20261028 --test-tags=/contract_price_leakage_auditor --stop-after-init --without-demo=True --http-port=8079 --http-interface=127.0.0.1
```

Log evidence:

- `Starting post tests`
- `TestDev01Foundation.test_smoke_001` through `test_smoke_008` started, with no failure traceback.
- `8 post-tests in 0.30s, 112 queries`
- `odoo.tests.result: 0 failed, 0 error(s) of 8 tests when loading database 'cpla_dev01_foundation_20261028'`
- `odoo.tests.stats: contract_price_leakage_auditor: 10 tests 0.27s 112 queries`

The result line is the assertion count: 8 tests, 0 failures, 0 errors. The stats line counts 10 stat entries for the same run. Odoo logs a per-module failure summary only when a module's tests are not successful. No such error line was written.

## Smoke results

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| SMOKE-001 | Yes | Pass | `test_smoke_001_module_installation_state`. Module state `installed`. Result line: 0 failed, 0 errors of 8 tests. Exit 0. |
| SMOKE-002 | Yes | Pass | `test_smoke_002_manifest_metadata`. `Manifest.for_addon` checks name, `19.0` series, depends `base`, license guard, empty author, flags. |
| SMOKE-003 | Yes | Pass | `test_smoke_003_import_initialization`. Package imports and does not expose a models package. |
| SMOKE-004 | Yes | Pass | `test_smoke_004_declared_data_references`. Data files exist. Category, privilege, and group XML IDs resolve. |
| SMOKE-005 | Yes | Pass | `test_smoke_005_initial_security_groups`. Eight groups, six privileges, no users, menus, rules, access rows, or account implications. |
| SMOKE-006 | Yes | Pass | `test_smoke_006_no_unauthorized_business_tables`. No owned model, field, access, menu, view, cron, or action records. No reserved business models in the registry. |
| SMOKE-007 | Yes | Pass | `test_smoke_007_registry_and_dependency_loading`. `registry.ready` is true. Dependency `base` is installed. |
| SMOKE-008 | Yes | Pass | In-test cardinality check plus the separate `-u` command. Post-update query: 15 XML IDs, 0 duplicates. |

## Static checks

| Check | Command outcome |
| --- | --- |
| `py_compile` on `__init__.py`, `__manifest__.py`, `tests/__init__.py`, `tests/test_foundation_smoke.py` | Exit 0 |
| `ast.parse` of `__manifest__.py` and `xml.etree.ElementTree.parse` of `security/security_groups.xml` | Printed `static ok`, exit 0 |
| Search for `sudo()` in addon Python | No matches |
| Secret scan of the new addon source | No password, token, or connection string was written into the addon |

No repository-wide formatter was run. No new lint dependency was added.

## Financial tests

GOLD-FIN and GOLD-REC were not executed. The foundation has no pricing or recovery code. Their status remains NOT_IMPLEMENTED.

## Reconfirmation

The same module-scoped command was run again at 2026-10-28 03:49 on `cpla_dev01_foundation_20261028`. Exit code 0. Log lines:

- `8 post-tests in 0.33s, 111 queries`
- `odoo.tests.stats: contract_price_leakage_auditor: 10 tests 0.27s 111 queries`
- `odoo.tests.result: 0 failed, 0 error(s) of 8 tests when loading database 'cpla_dev01_foundation_20261028'`

The missing-author warning was logged again. No addon file changed between the 03:44 run and this run.

## Unexecuted items

| Item | Status | Reason |
| --- | --- | --- |
| First `--test-enable` process exit code | Not a clean exit | Process stopped after install and after the eight foundation tests had started without a failure, while unrelated standard tests were still running. |
| Odoo 18 and Odoo 20 install | NOT_EXECUTED | Out of scope for DEV-01. |
| Production or pre-existing databases | NOT_EXECUTED | Not authorized. |
