# 03 — Security foundation

Date: 2026-10-28.
Schema checked against Odoo 19 Community `res.groups` and `res.groups.privilege` before the XML was written. Odoo 19 groups use `privilege_id` and `implied_ids`. The old category field on `res.groups` is not the Odoo 19 shape. Groups that share one privilege behave as levels. Independent roles therefore use separate privileges.

## Role architecture

Eight groups, six privileges, one module category. No model access, no record rules, no menus, no users, and no implied Community accounting groups.

| XML ID | Record | Privilege | Implies |
| --- | --- | --- | --- |
| `module_category_contract_price_leakage` | Category "Contract Price Leakage" | — | — |
| `privilege_contract_access` | Contract Access | — | — |
| `group_contract_user` | Contract User | Contract Access | nothing |
| `group_contract_manager` | Contract Manager | Contract Access | Contract User only |
| `privilege_sales_pricing_review` | Sales Pricing Review | — | — |
| `group_sales_pricing_reviewer` | Sales Pricing Reviewer | Sales Pricing Review | nothing |
| `privilege_finance` | Leakage Finance | — | — |
| `group_finance_reviewer` | Finance Reviewer | Leakage Finance | nothing |
| `group_finance_manager` | Finance Manager | Leakage Finance | Finance Reviewer only |
| `privilege_recovery` | Recovery Operation | — | — |
| `group_recovery_operator` | Recovery Operator | Recovery Operation | nothing |
| `privilege_internal_audit` | Internal Audit | — | — |
| `group_internal_auditor` | Internal Auditor | Internal Audit | nothing |
| `privilege_application_admin` | Application Administration | — | — |
| `group_app_admin` | Application Administrator | Application Administration | nothing |

Full external IDs are prefixed with `contract_price_leakage_auditor.`.

The two ladders are Contract User / Contract Manager and Finance Reviewer / Finance Manager. Sales Pricing Reviewer, Recovery Operator, Internal Auditor, and Application Administrator can be combined because each has its own privilege. Application Administrator does not imply the other roles, Settings, or an accounting administrator.

None of these groups implies `base.group_user` or an `account` group. Assigning one does not by itself make an internal user or an accountant. That is intentional while no business model exists. DEV-02 must decide whether each role should imply `base.group_user` once real access rights exist.

## What was verified

On database `cpla_dev01_foundation_20261028` after install and again after update:

- 15 XML IDs: 1 category, 6 privileges, 8 groups.
- 0 duplicate XML IDs.
- 0 `ir.model.access` rows for these groups.
- 0 cron records owned by the module.
- 0 business models named `contract.price.*`, `cpla.*`, or `contract_price_leakage.*`.
- Smoke test 005 passed: no users, no menu access, no record rules, no account groups implied, and the privilege split above.

No new Python code calls `sudo()`.

## Assumptions

- Standard Odoo groups such as Internal User, Invoicing, and Settings stay the owners of core accounting and administration rights.
- These new groups reserve stable identifiers. They do not grant business permission.
- No public or portal user received these groups.
- No core user and no company setting was modified by the XML.

## Multi-company policy

Planned, not implemented:

- Contract records will belong to an authorized company.
- Finance and recovery records will keep company ownership.
- Scheduled actions, when a later phase adds them, must keep company boundaries.
- Cross-company consolidated reporting will require an explicit permission.

There is no `ir.rule` yet because there is no business model to isolate. Multi-company security is not complete.

## Current limitations

- No access rights exist, so the groups cannot yet be tested against contract, invoice, or recovery records.
- No record rule enforces company isolation.
- Group comments state the lack of rights. Comments are not a security control.
- This is not a DEV-02 access-control certification and it does not satisfy SEC-01 through SEC-12.

## DEV-02 work still open

- Decide whether each role implies `base.group_user`.
- Add `ir.model.access` only for models that exist, with no public access.
- Add company record rules when company-owned models exist.
- Do not grant Invoicing or Accounting administrator as a shortcut.
- Do not assign the new groups to the default admin as a blanket grant.
- Review separation between Finance Reviewer, Finance Manager, Recovery Operator, and Internal Auditor against the still-open recovery and waiver decisions.
