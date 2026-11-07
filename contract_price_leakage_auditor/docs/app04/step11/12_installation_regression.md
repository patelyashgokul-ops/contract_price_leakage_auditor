# Installation and regression

Commands ran from `C:\PycharmProjects\odoo19\odoo-19.0` with the project virtualenv. HTTP port 8071. `--without-demo=True`. Addon tag `/contract_price_leakage_auditor` unless noted. Databases `cpla_dev04_20261028` through `cpla_dev10_fresh_20261028` were not dropped. `cpla_dev10_20261028` was upgraded in place and kept.

## REG11-T001 fresh install

```
python -u odoo-bin -c odoo.conf -d cpla_dev11_fresh_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev11_fresh1.log`.

Registry loaded in 118.931s. `778 post-tests in 275.41s, 187791 queries`. Result: `0 failed, 0 error(s) of 778 tests`. `DEV11 map x30 0.14030500000808388`.

## REG11-T002 upgrade from DEV-10

`cpla_dev10_20261028` was at `19.0.1.8.0` before this phase.

```
python -u odoo-bin -c odoo.conf -d cpla_dev10_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev11_upgrade.log`.

Registry loaded in 10.782s. `778 post-tests in 252.96s, 182559 queries`. Result: `0 failed, 0 error(s) of 778 tests`. `DEV11 map x30 0.12942329999350477`.

## Full tag on the DEV-11 database

```
python -u odoo-bin -c odoo.conf -d cpla_dev11_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init
```

Log: `C:\Users\Admin\AppData\Local\Temp\cpla_dev11_full1.log`.

`778 post-tests in 300.23s, 187805 queries`. Result: `0 failed, 0 error(s) of 778 tests`. `DEV11 map x30 0.14899830000649672`.

The 778 tests include the prior-phase suite that previously reported 676, plus the DEV-11 class. Security XML, views, and the confirmation gate ran inside that tag. The class also asserts that `account` is not a direct dependency and that no invoice-audit cron exists.

Standard invoice posting and credit-note creation were used as test setup. Mapping did not add a journal entry of its own. The freight server on port 8069 was not changed.
