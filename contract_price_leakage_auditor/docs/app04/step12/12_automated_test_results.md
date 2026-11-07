# Automated test results

Odoo 19.0. Interpreter: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`. Working directory: `C:\PycharmProjects\odoo19\odoo-19.0`. Port 8071. `--without-demo=True`. `--stop-after-init`.

The first class run is not acceptance. `C:\Users\Admin\AppData\Local\Temp\cpla_dev12_class1.log` recorded 9 failed, 11 errors of 100 tests. Causes were excluded-line counts, posted invoice dates, amendment effective dates that collided with the initial version, an override the salesman record rule blocked, a second current finding when the cutoff clock moved, and a few assertions that did not match Odoo 19 behavior. Those were fixed. The runs below executed the fixed code.

| Run | Database | Command shape | Result line | Stats line | Repeat timing |
| --- | --- | --- | --- | --- | --- |
| Class rerun | `cpla_dev12_20261028` | `-u`, tag `TestDev12InvoiceAudit` | 0 failed, 0 errors of 100 tests in 113.13s, 60,385 queries | 102 tests, 113.09s, 60,385 queries | `DEV12 audit x10 0.5543640999967465` |
| Full update | `cpla_dev12_20261028` | `-u`, tag `/contract_price_leakage_auditor` | 0 failed, 0 errors of 878 tests | 902 tests, 391.73s, 248,197 queries | `DEV12 audit x10 0.37981510000827257` |
| Upgrade | `cpla_dev11_20261028` | `-u`, same tag | 0 failed, 0 errors of 878 tests | 902 tests, 507.43s, 248,168 queries | `DEV12 audit x10 0.4739525000040885` |
| Fresh install | `cpla_dev12_fresh_20261028` | `-i`, same tag | 0 failed, 0 errors of 878 tests | 902 tests, 457.22s, 248,189 queries | `DEV12 audit x10 0.2962407000013627` |

Logs: `cpla_dev12_class2.log`, `cpla_dev12_full1.log`, `cpla_dev12_upgrade.log`, `cpla_dev12_fresh1.log` under `C:\Users\Admin\AppData\Local\Temp`. Fresh registry load: 155.639s. Full and fresh logs print `Odoo version 19.0`.

Every ID below was executed inside `tests/test_invoice_audit.py` on the class rerun and again inside the three full tags. Result: PASS. Evidence: those four logs. One method can cover more than one ID. `IDM12-T005` proves the unique constraint with `IntegrityError` in a savepoint. It is not two-worker evidence.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| ELG12-T001–T012 | Yes | PASS | `test_elg12_t001` through `test_elg12_t012` |
| HIS12-T001–T014 | Yes | PASS | `test_his12_t001` through `test_his12_t014` |
| FIN12-T001–T020 | Yes | PASS | `test_fin12_t001` through `test_fin12_t020` |
| PAR12-T001–T010 | Yes | PASS | `test_par12_t001` through `test_par12_t010` |
| REF12-T001–T015 | Yes | PASS | `test_ref12_t001` through `test_ref12_t015` |
| IDM12-T001–T014 | Yes | PASS | `test_idm12_t001` through `test_idm12_t014` |
| SEC12-T001–T015 | Yes | PASS | `test_sec12_t001` through `test_sec12_t015` |
| INT12-T001–T012 | Yes | PASS | `test_int12_t001_through_t010`, `test_int12_t011`, `test_int12_t012` |
| REG12-T001 | Yes | PASS | Fresh `-i` of `cpla_dev12_fresh_20261028`, 0 failed of 878 |
| REG12-T002 | Yes | PASS | `-u` of `cpla_dev11_20261028`, 0 failed of 878. New audit XML loaded. |
| REG12-T003–T013 | Yes | PASS | `test_reg12_views_security_and_no_cron` and `test_reg12_prior_gate_still_blocks_a_low_price`, plus the prior-phase tests in the 878 |

`REG12-T001` and `REG12-T002` are the shell runs, not a fake pass inside `TransactionCase`.

Not executed, and not claimed:

- Two OS processes auditing the same invoice line.
- 1,000, 10,000, 50,000, or 100,000 invoice lines.
- Odoo 18 and Odoo 20 installation.
