# Installation and regression

Odoo 19.0 Community, `odoo/release.py` `version_info` `(19, 0, 0, final, 0)`. Python is the project virtualenv. Commands run from `C:\PycharmProjects\odoo19\odoo-19.0`. HTTP port 8071. `--without-demo=True`. Addon tag `/contract_price_leakage_auditor` unless noted. No production database was opened. `cpla_dev04_20261028` through `cpla_dev07_20261028` were not dropped.

## Commands

Class tag, first install of `cpla_dev09_20261028`:

```text
python -u odoo-bin -c odoo.conf -d cpla_dev09_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor:TestDev09DiscountAuthority --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

Result: 2 failed, 3 error(s) of 57 tests. Log `C:\Users\Admin\AppData\Local\Temp\cpla_dev09_class.log`. The module installed. The failures were a missing approval limit in one fixture, two amendments on the same effective date, and company denial reported as `not_applicable`.

Class tag after the fixes, same database, `-u`:

```text
57 post-tests in 44.93s, 18199 queries
0 failed, 0 error(s) of 57 tests
```

Log `cpla_dev09_class2.log`. `DEV09 evaluate x30 elapsed 0.2757461000001058`.

Full tag, same database, before the smoke expectation named `cpla.discount.event`:

```text
1 failed, 0 error(s) of 610 tests
```

`test_smoke_005_initial_security_groups` expected `perm_write` on the event row. The event access row stays read and create only. Log `cpla_dev09_full.log`.

Full tag after that test expectation:

```text
610 post-tests in 194.95s, 116475 queries
0 failed, 0 error(s) of 610 tests when loading database 'cpla_dev09_20261028'
```

Log `cpla_dev09_full2.log`. `DEV09 evaluate x30 elapsed 0.1725739999965299`. `DEV08 normalize x30 elapsed 0.037931500002741814`.

Upgrade of the DEV-08 database `cpla_dev08_20261028` from `19.0.1.6.0` to `19.0.1.7.0`:

```text
python -u odoo-bin -c odoo.conf -d cpla_dev08_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

```text
Registry loaded in 14.028s
610 post-tests in 188.80s, 116472 queries
0 failed, 0 error(s) of 610 tests when loading database 'cpla_dev08_20261028'
```

Log `cpla_dev09_upgrade.log`. `DEV09 evaluate x30 elapsed 0.1882162999972934`. `DEV08 normalize x30 elapsed 0.05509889998938888`.

## What the green runs show

- The module updates from the DEV-08 schema. New discount tables, access rows, rules, and views load.
- Contract versions, quantity tiers, and FX and tax normalization tests pass, including INT08-T008.
- `test_reg09_views_manifest_and_no_audit_cron` finds version `19.0.1.7.0`, depends `base` and `product`, the Authorized Discounts page, the applicability adjusted-price field, and Submit for Approval. It finds no invoice-audit cron and no `account.move` data record from this module.
- No leakage finding is created. Evaluation does not change a version line price.

## Fresh database

Clean install of `cpla_dev09_fresh_20261028` from the final tree:

```text
python -u odoo-bin -c odoo.conf -d cpla_dev09_fresh_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

```text
610 post-tests in 243.13s, 116534 queries
0 failed, 0 error(s) of 610 tests when loading database 'cpla_dev09_fresh_20261028'
```

Log `C:\Users\Admin\AppData\Local\Temp\cpla_dev09_fresh.log`. `DEV09 evaluate x30 elapsed 0.23730459999933373`. `DEV08 normalize x30 elapsed 0.06467040001007263`.

REG09-T001 passed on this database. The name is listed in `local_testing/disposable_databases.txt`.
