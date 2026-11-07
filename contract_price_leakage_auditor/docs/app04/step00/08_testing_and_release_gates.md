# 08 — Testing and release gates

**TEST EXECUTION: NOT PERFORMED — DEV-00 PLANNING ONLY.**

No test output is claimed. No database was created or migrated. `odoo.conf` was not opened, so an isolated test database is **NOT VERIFIED**.

## What the repository has today

| Check | Evidence | Result |
| --- | --- | --- |
| APP 04 `tests/` package | Directory listing | Missing. |
| Financial fixtures in APP 04 | No Python files | Missing. |
| APP 04 CI | No `.github` or script in this addon | Missing. |
| Installation state of APP 04 | No manifest | Not installed. Not installable. |
| Security tests | None | Missing. |
| Odoo 19 test framework | `odoo/tests/common.py` contains `TransactionCase` (line 990), `SingleTransactionCase`, `HttpCase`, and `tagged` | Present in the server tree. Not executed for APP 04. |
| Official testing reference | Odoo 19.0 documentation, Testing Odoo, `https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html` | Read during this step. Tests live in a `tests` package imported from `tests/__init__.py`. Methods start with `test_`. `--test-tags` selects tests and implies `--test-enable`. Default tags include `standard` and `at_install`. |

## Later test strategy

Use `odoo.tests.TransactionCase` for financial oracles so each method rolls back. Tag financial cases `post_install` with `-at_install` once the module depends on `account`. Use `--test-tags /contract_price_leakage_auditor` only after a manifest exists.

Planned selector examples, not run:

- Financial: `--test-tags /contract_price_leakage_auditor:TestGoldFin`
- Security: `--test-tags /contract_price_leakage_auditor:TestCompanyIsolation`
- Install: fresh database, `-i contract_price_leakage_auditor --test-enable`

`HttpCase` and tours belong to UI phases. They are not a substitute for GOLD-FIN arithmetic.

Demo data must be synthetic. Golden INR and USD amounts may be demo numbers. Customer contracts must not be copied into the addon.

Volume cases PLANNED-VOL-5000, PLANNED-VOL-50000, PLANNED-VOL-100000, PLANNED-VOL-500000, and PLANNED-VOL-1000000 are measurement plans. They are not acceptance criteria until DEC-18 sets a threshold.

## Release gates

A failed critical gate blocks release. It is not waived to meet a date.

| Gate | Rule | Critical failure it catches |
| --- | --- | --- |
| G01 | Historical price matches the approved version and the approved date rule. | Wrong applicable contract. |
| G02 | Approved discounts are excluded. Unapproved discounts remain potential leakage. | Wrong financial calculation. |
| G03 | Currency, UoM, tax, and rounding follow the approved policy and the series' UoM API. | Wrong financial calculation. |
| G04 | One current exposure per identity key. | Duplicate leakage. |
| G05 | Finance validation is a separate, authorized transition. | Unauthorized financial approval. |
| G06 | Recovery and waiver use the matrices and block self-approval. | Unauthorized waiver or approval. |
| G07 | Billed, waived, cash, and outstanding satisfy the GOLD-REC equations. | Incorrect recovered cash. |
| G08 | Replay and concurrency do not double-bill or double-count. | Duplicate recovery billing. |
| G09 | Prior audit evidence and decisions remain readable. | Lost historical evidence. |
| G10 | Cross-company ORM access fails. | Cross-company exposure. |
| G11 | Interrupted and repeated jobs obey OPS-04 and OPS-06. | False "audited" status. |
| G12 | Dashboard totals equal the source findings for the same as-of time. | Inconsistent KPIs. |
| G13 | Clean install and the supported upgrade path pass on a disposable database. | Uninstallable or non-upgradeable build. |
| G14 | UAT evidence maps to requirement IDs. | Release without business proof. |
| G15 | Named business sign-off after G01–G14. | Unapproved release. |

## Version rules

Odoo 19 is the first series that may be submitted to these gates. Odoo 18 and Odoo 20 need the same gates on their own databases. A pass on 19 does not pass 18 or 20.

Current result for every gate: **not run**.
