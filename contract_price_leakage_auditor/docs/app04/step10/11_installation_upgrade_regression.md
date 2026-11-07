# Installation and regression

Odoo 19.0 Community, `odoo/release.py` `version_info` `(19, 0, 0, final, 0, '')`. Python is the project virtualenv. Commands run from `C:\PycharmProjects\odoo19\odoo-19.0`. HTTP port 8071. `--without-demo=True`. Addon tag `/contract_price_leakage_auditor` unless noted. No production database was opened. `cpla_dev04_20261028` through `cpla_dev09_fresh_20261028` were not dropped.

`sale` is a direct dependency. Installing or upgrading this addon also installs the modules `sale` already depends on, including `account`. That is expected. This addon does not create `account.move` data.

## Commands

Class tag on `cpla_dev10_20261028`:

```text
python -u odoo-bin -c odoo.conf -d cpla_dev10_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor:TestDev10QuotationCompliance --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

First class run failed at import: `SUCCESS_FINANCIAL` is defined in `discount_authority.py`, not in `financial_normalization.py`. Log `cpla_dev10_class.log`.

Second class run, after the import fix: 19 failed, 23 error(s) of 66 tests. Log `cpla_dev10_class2.log`. Superuser evaluation never reached the resolver, and contract-only users could not read `sale.order.line`.

Class tag after those fixes:

```text
66 post-tests
0 failed, 0 error(s) of 66 tests when loading database 'cpla_dev10_20261028'
DEV10 evaluate x30 elapsed 0.4383508000028087
```

Log `cpla_dev10_class4.log`. One earlier rerun (`cpla_dev10_class3.log`) had 0 failed, 1 error of 66 because the timing test indexed an abstract model.

Full tag on the same database, before the registry assertion treated inherited Sales models separately: 1 failed, 0 error(s) of 676 tests. `test_sec_t007` saw `sale.order` and `sale.order.line` tagged with this module. Log `cpla_dev10_full.log`.

Full tag after that split, while a contract reference `CPL/2026/01200` still counted as a hidden price: 1 failed, 0 error(s) of 676 tests. Log `cpla_dev10_full2.log`.

Full tag after the reference list is excluded from the hidden-price scan:

```text
676 post-tests in 217.90s, 138185 queries
0 failed, 0 error(s) of 676 tests when loading database 'cpla_dev10_20261028'
DEV10 evaluate x30 elapsed 0.4635331000026781
```

Log `cpla_dev10_full3.log`. This run used the stricter registry equality. The final test allows either Sales model to be attributed to a later module. That final assertion was not re-run on this database. It passed on the fresh rerun below.

Upgrade of the DEV-09 database `cpla_dev09_20261028` from `19.0.1.7.0` to `19.0.1.8.0`:

```text
python -u odoo-bin -c odoo.conf -d cpla_dev09_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

```text
Registry loaded in 49.535s
676 post-tests in 261.97s, 142995 queries
0 failed, 0 error(s) of 676 tests when loading database 'cpla_dev09_20261028'
DEV10 evaluate x30 elapsed 0.33119180001085624
```

Log `cpla_dev10_upgrade.log`. Same registry assertion as `cpla_dev10_full3.log`.

Fresh `-i` of `cpla_dev10_fresh_20261028`:

```text
python -u odoo-bin -c odoo.conf -d cpla_dev10_fresh_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

First result: 1 failed, 0 error(s) of 676 tests. `sale.order` was not attributed to this module. Log `cpla_dev10_fresh.log`. The module had installed. The rerun used `-u` and the subset assertion:

```text
Registry loaded in 16.324s
676 post-tests in 301.56s, 143004 queries
0 failed, 0 error(s) of 676 tests when loading database 'cpla_dev10_fresh_20261028'
DEV10 evaluate x30 elapsed 0.9602049999957671
```

Log `cpla_dev10_fresh2.log`.

## What the green runs show

- The module updates from the DEV-09 schema. The new lock table, wizard, policy field, access rows, rules, and Sales view load.
- Prior contract, version, quantity, FX, tax, and discount tests pass inside the 676.
- No leakage finding, recovery record, or waiver is created.
- A fresh database can install the addon with `sale`.

Odoo 18 and Odoo 20 were not installed.
