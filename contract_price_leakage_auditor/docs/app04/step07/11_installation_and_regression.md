# 11 — Installation and regression

Date: 2026-10-28.

Interpreter: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`.

Server: `C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin` with `odoo.conf`. Database user `odoo` at `localhost:5432`. Odoo 19.0. Community. License of the server is LGPL-3. The addon license key remains `Other proprietary`.

## Commands

Upgrade, after the four test fixes:

`python -u odoo-bin -c odoo.conf -d cpla_dev06_20261028 -u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init`

Fresh:

`python -u odoo-bin -c odoo.conf -d cpla_dev07_20261028 -i contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor --without-demo=True --http-interface=127.0.0.1 --http-port=8071 --stop-after-init`

Both exited 0. Results are in `10_automated_test_results.md`.

`cpla_dev07_20261028` is listed in `local_testing/disposable_databases.txt`. `cpla_dev04_20261028`, `cpla_dev05_20261028`, and `cpla_dev06_20261028` were not dropped.

## What the upgrade kept

The module update added `cpla.customer.contract.version.tier` and the line fields `tier_method`, `quantity_basis`, and `return_policy`. Existing approved version rows were not given tier records. Header states are still draft, ready for review, and cancelled. Depends remain `base` and `product`. No cron was added. No recovery model was added.

REG07-T006 still returns one authority for one approved contract and `CONFLICT_REVIEW_REQUIRED` when two approved contracts cover the same customer and product. Neither explanation is a price.

Version pins in the older test modules expect `19.0.1.5.0`. They passed.

## Not claimed

No production database was updated. No posted invoice was edited by this addon. The regression test checks `account.move` only when that model is already in the registry, and it does not install accounting. Browser verification was not done. Odoo 18 and Odoo 20 were not installed.
