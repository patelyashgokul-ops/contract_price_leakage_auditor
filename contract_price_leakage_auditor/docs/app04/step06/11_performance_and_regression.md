# 11 — Performance and regression

## What was measured

DET06-T009 creates one matching contract and eight contracts for other customers, then resolves the original customer once. The assertion is `elapsed < 5.0` seconds. The passing run does not print the elapsed value. The ceiling passed on the upgrade rerun and the fresh install. That is not a throughput number.

DET06-T012 repeats one lookup with the same ceiling. No queries-per-second figure was recorded.

No result cache exists. The cache key includes company, customer, product, dates, cutoff, unit, group reference, and the template flag. It is not stored. After a new approval, the next call sees the new version.

Candidate search uses a domain on company, product, approved state, partner, and the date window. Existing version and line indexes were left in place. No new index was added.

## Installation

| Check | Result |
| --- | --- |
| Update `cpla_dev05_20261028` from `19.0.1.3.0` to `19.0.1.4.0` | Run 1 failed 2 tests. Run 2: `0 failed, 0 error(s) of 366 tests`. |
| Fresh `cpla_dev06_20261028` | Modules loaded 2026-10-28 08:34:25. `0 failed, 0 error(s) of 366 tests`. |
| Prior contract, version, policy, and security tests | Included in those 366. No separate failure. |
| Accounting rows created by the resolver | None asserted by REG06-T011 and GFD06-T010. |
| Cron | No module cron. |

`cpla_dev04_20261028` and `cpla_dev05_20261028` were not dropped. `cpla_dev06_20261028` is listed in `local_testing/disposable_databases.txt`.

## Odoo 18 and 20

Not converted and not tested. Areas to retest later: search domains, company checks, product variant creation, partner parent fields, date fields, record rules, abstract model registration, the diagnostic view, and the test tag. Odoo 19 remains the master.
