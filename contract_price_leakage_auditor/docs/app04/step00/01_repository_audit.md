# 01 — Repository audit

Inspection date: 2026-10-28.
Method: directory listing and static file reads. No Git write. No database connection. No module install. No test run.

## Existing APP 04 implementation: NOT FOUND

Workspace: `C:\PycharmProjects\odoo19\custom_addons\contract_price_leakage_auditor`

At the start of step 00 the directory existed and contained no files and no subdirectories. There was no manifest, model, view, menu, security file, cron, report, test, or experimental prototype.

| Path | APP 04 module |
| --- | --- |
| `C:\PycharmProjects\odoo19\custom_addons\contract_price_leakage_auditor` | Empty directory at start. Now contains planning documents only. |
| `C:\PycharmProjects\odoo18\custom_addons` | Technical name absent. |
| `C:\PycharmProjects\odoo20\custom_addons` | Technical name absent. |

## Git

| Path | `.git` |
| --- | --- |
| This addon | Absent. |
| `C:\PycharmProjects\odoo19\custom_addons` | Absent. |
| `C:\PycharmProjects\odoo19` | Absent. |
| `C:\PycharmProjects` | Absent. |

Branch, commit, tags, and a diff against a base revision are **NOT VERIFIED**. No reset, clean, checkout, or merge was run.

## Odoo trees read statically

| Series | Path | `version_info` | Server license |
| --- | --- | --- | --- |
| 19 master | `C:\PycharmProjects\odoo19\odoo-19.0` | `(19, 0, 0, final, 0, '')` in `odoo/release.py` | LGPL-3 |
| 18 | `C:\PycharmProjects\odoo18\odoo-18.0` | `(18, 0, 0, final, 0, '')` | LGPL-3 |
| 20 | `C:\PycharmProjects\odoo20\odoo-20.0` | `(20, 0, 0, final, 0, '')` | LGPL-3 |

Odoo 19 Community addons: `C:\PycharmProjects\odoo19\odoo-19.0\addons` (630 directories). Python range declared in Odoo 19 `odoo/release.py`: 3.10 through 3.14. Odoo 18 `setup.py` declares `python_requires >= 3.10`. Odoo 18 `release.py` has no `MIN_PY_VERSION`. Odoo 20 `release.py` minimum is 3.12.

`C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf` exists. It was not opened. No database name, host, or password was copied.

## Manifest audit

APP 04 has no `__manifest__.py`. The following are therefore absent, not assumed:

| Item | Result |
| --- | --- |
| Technical name | Directory name only: `contract_price_leakage_auditor`. Not declared to Odoo. |
| Manifest version | Absent. |
| Declared license | Absent. |
| Dependencies | Absent. |
| External Python dependencies | Absent. |
| External binaries | Absent. |
| Data and demo paths | Absent. |
| Installable flag | Absent. The directory is not an installable addon. |
| Version mismatch | Not applicable. |
| Missing referenced paths | Not applicable. |
| Incompatible third-party code | None copied. None vendored. |

## Files created during step 00

These files did not exist before step 00. They are planning artifacts.

First pass, before the rest of the prompt arrived:

- `README.md`
- `DEVELOPMENT_PROGRESS.md`
- `docs/README.md`
- `docs/00_REPOSITORY_AUDIT.md`
- `docs/00_REQUIREMENTS_SOURCE_INVENTORY.md`
- `docs/00_P0_REQUIREMENTS_REGISTER.md`
- `docs/00_COMMUNITY_DEPENDENCY_VERIFICATION.md`
- `docs/00_FINANCIAL_SECURITY_INVARIANTS.md`
- `docs/00_OPEN_DECISIONS.md`
- `docs/00_GOLDEN_TEST_PLAN.md`
- `docs/00_RELEASE_READINESS.md`

Canonical package, this completion:

- `docs/app04/step00/` and the files indexed by its `README.md`

No Python, XML, CSV security file, or manifest was added. No pre-existing product file was deleted.

## Nearby addon that is not APP 04

`C:\PycharmProjects\odoo19\custom_addons\freight_invoice_audit_recovery`

Odoo 19 manifest, read only: name "Freight Audit & Recovery", version `19.0.1.28.0`, license `OPL-1`, category Inventory/Logistics, depends `base`, `mail`, `web`, external Python `xlsxwriter`. The same directory name exists under the Odoo 18 and Odoo 20 `custom_addons` trees. Those copies were not version-audited.

That product audits carrier freight bills. It was not renamed, merged, or edited. Its license, tolerances, and workflows are not APP 04 decisions. No source was copied from it.

Odoo 19 `custom_addons` contains only that addon and this directory.

## Requirements documents found on disk

None for APP 04, other than the step 00 prompt supplied in the working session and the planning files this step wrote. No approved decision log, UAT script, or signed commercial brief was found.

## Limits

- No Odoo process was started, so installability was not executed.
- Full-text search of every Odoo 19 file for the product name was not used. Addon directories were listed directly.
- Upstream Odoo `.github` is the Odoo project, not an APP 04 CI pipeline.
