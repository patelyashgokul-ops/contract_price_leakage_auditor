# Automated test results

Odoo 19.0 Community. Python is the project virtualenv. Working directory `C:\PycharmProjects\odoo19\odoo-19.0`. Port 8071. `--without-demo=True`. No production database was opened.

The result line is the count used below. The stats line on the same runs says 104 tests for the class and 800 tests for the full tag. Those higher counts are not used.

## Failed run, then the fix

`C:\Users\Admin\AppData\Local\Temp\cpla_dev11_class1.log` on new database `cpla_dev11_20261028` with `-i` and tag `TestDev11InvoiceSource`.

Result: `2 failed, 4 error(s) of 102 tests`. Queries on the stats line were 44646. `DEV11 map x30` on that failed run was `0.24204209999879822`. That timing is not the acceptance measurement.

Failures:

- Vendor bill and vendor refund posting required a bill date.
- `net_quantity_for_sale_line` was called before the three partial invoices were mapped, so the sum was `0`.
- Converted box quantity was stored as `1.0` instead of canonical `1`.
- A contract user `write` raised `UserError` before the access check.
- The plain-user read used `approved_unit_price_exact` on the map. That field is on the allocation.

Those were fixed. The class was rerun.

## Green class

`C:\Users\Admin\AppData\Local\Temp\cpla_dev11_class2.log`. `-u` of `cpla_dev11_20261028`, same class tag.

`102 post-tests in 106.97s, 44759 queries`. Result: `0 failed, 0 error(s) of 102 tests`. `DEV11 map x30 0.13581469999917317`.

Every test method in `tests/test_invoice_source.py` started in that log, and the result line reports no failure. The rows below use that evidence.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| INV11-T001–T012 | Yes | Pass | class2, 0 failed of 102 |
| MAP11-T001–T014 | Yes | Pass | class2, 0 failed of 102 |
| PAR11-T001–T012 | Yes | Pass | class2, 0 failed of 102 |
| REF11-T001–T016 | Yes | Pass | class2, 0 failed of 102 |
| FIN11-T001–T016 | Yes | Pass | class2, 0 failed of 102 |
| SEC11-T001–T014 | Yes | Pass | class2, 0 failed of 102 |
| IDM11-T001–T010 | Yes | Pass | class2, 0 failed of 102 |
| SRC-REF-007, 018, 020 | Yes | Pass | class2 extra methods |
| IDM11-T003 two sessions | No | Not a two-session proof | Unique-constraint insert inside one `TransactionCase` |

IDM11-T003 did raise the unique violation in the log (`cpla_invoice_source_map_current_line_unique`) and the test passed. It does not start two workers.

No leakage finding model was created. No recovery accounting document was created. Posted invoice price, partner, company, and state were unchanged by mapping in FIN11-T015.

Invoice-audit and leakage-detection tests are `DEFERRED_TO_DEV12`.
