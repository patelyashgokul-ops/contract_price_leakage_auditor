# Repository audit

Superseded for acceptance by `docs/app04/step00/01_repository_audit.md`. This file is the preserved first pass.

Inspection date: 2026-10-28
Method: directory listing and static source reads. No Git write operations. No database connection. No module install. No test run.

## Existing APP 04 implementation: NOT FOUND

The workspace `C:\PycharmProjects\odoo19\custom_addons\contract_price_leakage_auditor` existed as an empty directory. A forced listing showed no files and no subdirectories before this documentation package.

Searches of the local addon paths found no second copy:

| Location | `contract_price_leakage_auditor` |
| --- | --- |
| `C:\PycharmProjects\odoo19\custom_addons` | Empty directory, now holding this documentation only. |
| `C:\PycharmProjects\odoo18\custom_addons` | Absent. |
| `C:\PycharmProjects\odoo20\custom_addons` | Absent. |

There is no APP 04 manifest, model, view, menu, security file, cron, report, test, or unfinished prototype to preserve.

## Git

Git is not available for this project.

| Path | `.git` |
| --- | --- |
| `contract_price_leakage_auditor` | Absent. |
| `C:\PycharmProjects\odoo19\custom_addons` | Absent. |
| `C:\PycharmProjects\odoo19` | Absent. |
| `C:\PycharmProjects` | Absent. |

Current branch, commit, tags, and uncommitted diffs are **NOT VERIFIED** because there is no repository. No reset, clean, checkout, or merge was run.

## Odoo source trees

These trees were present and were read statically.

| Series | Path | `version_info` | Server license | Python declaration found |
| --- | --- | --- | --- | --- |
| 19 master | `C:\PycharmProjects\odoo19\odoo-19.0` | `(19, 0, 0, final, 0, '')` | LGPL-3 | `odoo/release.py`: minimum 3.10, maximum 3.14 |
| 18 future | `C:\PycharmProjects\odoo18\odoo-18.0` | `(18, 0, 0, final, 0, '')` | LGPL-3 | `setup.py`: `python_requires >= 3.10`. `release.py` has no `MIN_PY_VERSION`. |
| 20 future | `C:\PycharmProjects\odoo20\odoo-20.0` | `(20, 0, 0, final, 0, '')` | LGPL-3 | `odoo/release.py`: minimum 3.12 |

Community addons live in each tree's `addons` directory. Odoo 19 has 630 addon directories there. Enterprise modules `account_accountant`, `accountant`, and `sale_subscription` are absent from all three trees.

`C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf` exists. It was not opened, so no database name, host, or password was copied into this package.

## Nearby addon that is not APP 04

`C:\PycharmProjects\odoo19\custom_addons\freight_invoice_audit_recovery` is a separate application. Its Odoo 19 manifest name is "Freight Audit & Recovery", technical category Inventory/Logistics, license `OPL-1`, version `19.0.1.28.0`, dependencies `base`, `mail`, and `web`. The same technical directory name also exists under the Odoo 18 and Odoo 20 `custom_addons` folders. Those copies were not version-audited.

That addon audits carrier freight bills. It is not a customer contract-price auditor. It was not renamed, merged, or edited. Its business rules are not reused here.

Odoo 19 `custom_addons` contains only these two directories.

## APP 04 technical inventory

| Item | Finding |
| --- | --- |
| Technical name | Directory name `contract_price_leakage_auditor`. Not declared in a manifest. |
| Manifest version | None. |
| License declaration | None. The proposed commercial price in the step 00 prompt is USD $599. That price is not a license choice. |
| Python package | None. No `__init__.py`. |
| Models | None. |
| XML views, menus, actions | None. |
| Security | None. |
| Automated tests | None. |
| Scheduled jobs | None. |
| Reports and exports | None. |
| Prior development notes | None in this directory. |

## What step 00 changed

Step 00 created this documentation package and `README.md` plus `DEVELOPMENT_PROGRESS.md`. It did not create an installable addon.

## Audit limits

- No runtime was started, so module installability is not proven by an Odoo process.
- No production or test database was queried.
- Full-text search of the entire Odoo 19 tree for the product name was not completed; the addon directories and manifests were enumerated directly.
- The master prompt supplied in the working session is truncated. See the requirements source inventory.
