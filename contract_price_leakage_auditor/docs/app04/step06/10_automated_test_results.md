# 10 — Automated test results

Odoo 19.0 final, Community tree, LGPL-3 `odoo/release.py`. Interpreter: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`. Port 8071. The freight server on port 8069 was not stopped.

## Runs

| Run | Database | Command | When (log) | Result line | Stats line |
| --- | --- | --- | --- | --- | --- |
| 1 | `cpla_dev05_20261028` | `-u` | 2026-10-28 08:30:56 to 08:31:15 | `2 failed, 0 error(s) of 366 tests` | `378 tests 54.03s 53544 queries`; `366 post-tests in 54.14s, 53544 queries` |
| 2 | `cpla_dev05_20261028` | `-u` | 2026-10-28 08:31:49 to 08:33:00 | `0 failed, 0 error(s) of 366 tests` | `378 tests 63.01s 53560 queries`; `366 post-tests in 63.04s, 53560 queries` |
| 3 | `cpla_dev06_20261028` | `-i` | 2026-10-28 08:33:16 to 08:35:23 | `0 failed, 0 error(s) of 366 tests` | `378 tests 58.21s 53610 queries`; `366 post-tests in 58.29s, 53610 queries` |

Logs: `C:\Users\Admin\AppData\Local\Temp\cpla_dev06_upgrade.log`, `cpla_dev06_upgrade2.log`, `cpla_dev06_fresh.log`.

Run 1 failed `test_app_013_knowledge_cutoff_hides_a_later_approval` and `test_dat06_t011_as_known_cutoff_keeps_v1`. Both approvals were stored in the same second, so `approved_at` could not be ordered. The tests now wait 1.1 seconds. Runs 2 and 3 passed.

Runs 2 and 3 each log one `could not serialize access due to concurrent update` from the existing DEV-05 concurrency test. The result line is still 0 failed. That losing transaction is not a second approval.

The 366 post-tests are the previous 242 plus 124 methods in `tests/test_pricing_applicability.py`. The stats count is higher than the result line, which is the same pattern as DEV-04 and DEV-05.

UI evidence is `get_view` in SEC06-T010 and REG06-T008. A browser was not used.

## DEV-06 methods

Evidence for every row below is run 2 and run 3, both `0 failed, 0 error(s) of 366 tests`, except APP-013 and DAT06-T011, which failed on run 1 and passed on runs 2 and 3.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| APP-001 | Yes | PASS | `test_app_001_exact_customer_and_exact_variant` |
| APP-002 | Yes | PASS | `test_app_002_branch_is_not_covered_by_the_parent_contract` |
| APP-003 | Yes | PASS | Approval of extra covered partners is blocked. No match. |
| APP-004 | Yes | PASS | Exact match. Group reference is not a second authority. |
| APP-005 | Yes | PASS | Template price is not invented. `POLICY_REVIEW_REQUIRED`. |
| APP-006 | Yes | PASS | Today keeps V1. Stands in for 30 June. |
| APP-007 | Yes | PASS | Tomorrow selects V2. Stands in for 1 July. |
| APP-008 | Yes | PASS | Confirmed order date keeps V1. Grandfathering flag true. |
| APP-009 | Yes | PASS | Invoice date selects V2. |
| APP-010 | Yes | PASS | Unconfirmed quotation is missing context. Confirmed date is used. |
| APP-011 | Yes | PASS | Future effective version is not used early. |
| APP-012 | Yes | PASS | Draft amendment price is excluded. |
| APP-013 | Yes | FAIL then PASS | Run 1 same-second cutoff. Runs 2 and 3 pass. |
| APP-014 | Yes | PASS | Retroactive approval raises `UserError`. V1 remains. |
| APP-015 | Yes | PASS | Two contracts. Conflict. No price. |
| APP-016 | Yes | PASS | Missing delivery date. |
| APP-017 | Yes | PASS | Company B contract is not selected for Company A. |
| APP-018 | Yes | PASS | Sibling price is not a template fallback. |
| APP-019 | Yes | PASS | Current parent does not prove earlier coverage. |
| APP-020 | Yes | PASS | Two delivery dates. Partition review. No price. |
| CUS06-T001–T012 | Yes | PASS | Exact customer, branch-as-customer, rejected parent coverage, group review, company isolation, two-contract conflict. |
| PRD06-T001–T010 | Yes | PASS | Exact variant, sibling rejection, no template price, archive, other-company product, category review, two lines on one version, quantity left for DEV-07. |
| DAT06-T001–T010 | Yes | PASS | Order, quotation, invoice, delivery, missing date, boundaries, future version, expiry, cutoff before approval. |
| DAT06-T011 | Yes | FAIL then PASS | Same first-run cause as APP-013. Runs 2 and 3 pass. |
| DAT06-T012–T016 | Yes | PASS | Retroactive block, snapshot does not pick a date, partition, calendar boundary, supersession. |
| GFD06-T001–T010 | Yes | PASS | Order lock, same-day increase, unconfirmed quotation, missing date, scope, unapproved limit, quantity flag, no leakage amount. |
| PRE06-T001–T016 | Yes | PASS | Single authority, no id or price tie-break, conflict, rejected and draft excluded, repeatable result, owner-only price. |
| SEC06-T001–T015 | Yes | PASS | Role, company, wizard, export, `read_group`, combined roles, no `sudo(`. |
| DET06-T001–T008 | Yes | PASS | Repeatable result, no id winner, list price ignored, parent change ignored, snapshot kept, cache key not stored, next call sees a new approval, line belongs to the version. |
| DET06-T009 | Yes | PASS | One lookup after 8 extra contracts. Ceiling 5 seconds. Exact seconds were not printed. |
| DET06-T010–T011 | Yes | PASS | No new version rows. `write_date` unchanged. |
| DET06-T012 | Yes | PASS | Same 5-second ceiling. No throughput claim. |
| REG06-T001 | Yes | PASS | Fresh `-i` on `cpla_dev06_20261028` and the version assertion `19.0.1.4.0`. |
| REG06-T002 | Yes | PASS | `-u` from installed `19.0.1.3.0` on `cpla_dev05_20261028`. Not a restored older backup. |
| REG06-T003–T012 | Yes | PASS | Header, snapshot, events, company rules, unapproved policy, views, imports, no leakage model, no cron. |
| GOLD-FIN-002 | Yes | PASS as selection only | Order date keeps 1000. The 1200 line remains. `leakage_amount` is false. |
| GOLD-FIN-001 | No | NOT_EXECUTED | Leakage of 25,000 was not calculated. |
| GOLD-FIN-003 | No | NOT_EXECUTED | FX, unit, and discount leakage of 760 was not calculated. |
| GOLD-REC-001 | No | NOT_EXECUTED | Recovery amounts were not calculated. |

Prior DEV-01 through DEV-05 methods ran in the same 366 and passed on runs 2 and 3.
