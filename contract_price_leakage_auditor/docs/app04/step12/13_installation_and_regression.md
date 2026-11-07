# Installation and regression

Commands ran from `C:\PycharmProjects\odoo19\odoo-19.0` with the project virtualenv Python. `--without-demo=True`, `--http-interface=127.0.0.1`, `--http-port=8071`, `--stop-after-init`. Disposable names were appended to `local_testing/disposable_databases.txt` before use. DEV-04 through DEV-11 databases were not dropped.

## Fresh installation

```
python -u odoo-bin -c odoo.conf -d cpla_dev12_fresh_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev12_fresh1.log`. Odoo version 19.0. Registry loaded in 155.639s. Result: 0 failed, 0 errors of 878 tests. Stats: 902 tests, 457.22s, 248,189 queries. `audit_sequence.xml`, `invoice_audit_rules.xml`, and `invoice_audit_views.xml` loaded with the module. No duplicate menu error was logged.

## Upgrade from DEV-11

```
python -u odoo-bin -c odoo.conf -d cpla_dev11_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev12_upgrade.log`. The database is the retained DEV-11 database. The update loaded `invoice_audit_rules.xml`, `data/audit_sequence.xml`, and `views/invoice_audit_views.xml`, which were not part of DEV-11. Result: 0 failed, 0 errors of 878 tests. Stats: 902 tests, 507.43s, 248,168 queries. The version assertion in the prior-phase tests expects `19.0.1.10.0` and passed. The starting row in `ir_module_module` was not printed before the update. The database had been left by the DEV-11 fresh and update runs at `19.0.1.9.0`.

## Prior-phase regression

The full tag on `cpla_dev12_20261028` was 0 failed, 0 errors of 878 tests (`cpla_dev12_full1.log`, 391.73s, 248,197 queries). That tag includes DEV-01 through DEV-11 tests plus DEV-12. The same count passed on the upgrade and on the fresh install.

`test_reg12_views_security_and_no_cron` checks that the audit views load, the security rows exist, and this module has no `ir.cron`. `test_reg12_prior_gate_still_blocks_a_low_price` checks that the quotation confirmation gate still blocks an unauthorized low price.

Posted invoices are not mutated. `INT12-T012` compares state, total, unit price, and quantity. No payment and no recovery invoice are created. The discount and source-mapping tests still assert that those phases create zero `cpla.leakage.finding` rows. Recovery, waiver, and case model prefixes remain absent.

## After the green logs

The help text on `knowledge_cutoff` was corrected so it no longer says an empty cutoff means the run start. The tested behavior was already the blank cutoff and the identity token `none`. No test was rerun for that string.
