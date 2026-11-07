# Automated test results

Odoo log line: `Odoo version 19.0`.

Runtime: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe` and `C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin`. Port 8071. `--without-demo=True`. No browser was available. Views were checked with `get_view` in REG08-T007.

## Commands

Upgrade from the DEV-07 database:

`python.exe -u odoo-bin -c odoo.conf -d cpla_dev07_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init`

Fresh database:

`python.exe -u odoo-bin -c odoo.conf -d cpla_dev08_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init`

## Outcomes

| Log | Result |
| --- | --- |
| `C:\Users\Admin\AppData\Local\Temp\cpla_dev08_upgrade.log` | `2 failed, 0 error(s) of 552 tests` on `cpla_dev07_20261028`. `552 post-tests in 134.65s, 97516 queries`. Failures were `84.0` versus `84`, and `False == 0`. |
| `C:\Users\Admin\AppData\Local\Temp\cpla_dev08_upgrade2.log` | `0 failed, 0 error(s) of 552 tests`. `552 post-tests in 125.69s, 97519 queries`. |
| `C:\Users\Admin\AppData\Local\Temp\cpla_dev08_fresh.log` | `Initializing database cpla_dev08_20261028`. `0 failed, 0 error(s) of 552 tests`. `552 post-tests in 228.81s, 97574 queries`. |
| `C:\Users\Admin\AppData\Local\Temp\cpla_dev08_upgrade3.log` | `0 failed, 0 error(s) of 553 tests`. `553 post-tests in 174.88s, 97850 queries`. This run includes `test_tax08_gold_tax_003_included_gross_net_and_extended_difference`. |

The fresh database was created before that one extra test method existed. The service behavior was already in that install. The dedicated GOLD-TAX-003 assertion passed on the final upgrade.

DEV-07's prior green count was 464. This phase adds 89 tests. 464 + 89 = 553.

## DEV-08 tests

Every ID below passed in `cpla_dev08_upgrade3.log`. Evidence for each row is that log line: `0 failed, 0 error(s) of 553 tests`.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| FX08-T001 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T002 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T003 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T004 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T005 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T006 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T007 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T008 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T009 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T010 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T011 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T012 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T013 | Yes | Pass | upgrade3, 553 tests, 0 failed. Failed on the first upgrade as text `84.0`. |
| FX08-T014 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T015 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T016 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T017 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| FX08-T018 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T001 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T002 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T003 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T004 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T005 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T006 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T007 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T008 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T009 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T010 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T011 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T012 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T013 | Yes | Pass | upgrade3, 553 tests, 0 failed. Failed on the first upgrade because `False == 0`. |
| TAX08-T014 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| TAX08-T015 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| GOLD-TAX-003 | Yes | Pass | upgrade3 only. Not in the 552-test fresh log. |
| PREC08-T001 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T002 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T003 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T004 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T005 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T006 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T007 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T008 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T009 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T010 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T011 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T012 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T013 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T014 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T015 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| PREC08-T016 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T001 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T002 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T003 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T004 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T005 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T006 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T007 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T008 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T009 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T010 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T011 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| SEC08-T012 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| HIS08-T001 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| HIS08-T002 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| HIS08-T003 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| HIS08-T004 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| HIS08-T005 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| HIS08-T006 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T001 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T002 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T003 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T004 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T005 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T006 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T007 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T008 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T009 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| INT08-T010 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T001 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T002 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T003 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T004 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T005 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T006 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T007 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T008 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T009 | Yes | Pass | upgrade3, 553 tests, 0 failed |
| REG08-T010 | Yes | Pass | upgrade3, 553 tests, 0 failed |

Prior DEV-01 through DEV-07 tests ran inside the same 553 and passed. They are not re-labeled as DEV-08 financial tests.

Not executed as passing leakage or discount tests: GOLD-FIN-001, GOLD-FIN-003, GOLD-REC-001, invoice-line audit, authorized-discount application, and DEV-14 reassessment orchestration. Those remain deferred.
