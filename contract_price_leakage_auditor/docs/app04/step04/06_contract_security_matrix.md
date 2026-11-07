# 06 — Contract security matrix

Date: 2026-10-28.

Group XML IDs are unchanged from DEV-02. No `group_cpl_*` records were created. No group implies `base.group_user`, portal, public, `base.group_system`, or an accounting group. Tests assign `base.group_user` themselves.

## ACL

Model access rows for the three contract models, from `security/ir.model.access.csv`. Permissions are read, write, create, unlink.

| Group | Header | Line | Evidence |
| --- | --- | --- | --- |
| `group_contract_user` | 1, 1, 1, 0 | 1, 1, 1, 1 | 1, 1, 1, 1 |
| `group_contract_manager` | 1, 1, 1, 0 | 1, 1, 1, 1 | 1, 1, 1, 1 |
| `group_finance_reviewer` | 1, 0, 0, 0 | 1, 0, 0, 0 | 1, 0, 0, 0 |
| `group_finance_manager` | 1, 0, 0, 0 | 1, 0, 0, 0 | 1, 0, 0, 0 |
| `group_internal_auditor` | 1, 0, 0, 0 | 1, 0, 0, 0 | 1, 0, 0, 0 |
| `group_sales_pricing_reviewer` | none | none | none |
| `group_recovery_operator` | none | none | none |
| `group_app_admin` | none | none | none |

Header unlink is also rejected in `unlink()`. Line and evidence unlink still require a draft parent.

One additional policy row was added: `access_cpla_company_policy_contract_user` is read-only on `cpla.company.policy` for `group_contract_user`. The Contract User can select a current policy. Sensitive policy fields remain grouped. The previous five policy rows are unchanged, including Application Administrator `1,1,1,0` and no unlink. Policy record rules remain the single global company rule. CFG-T048 expects six policy ACL rows and one policy rule.

## Record rules

File: `security/customer_contract_rules.xml`.

Global rules have no groups. They AND with every access:

| XML ID | Model | Domain |
| --- | --- | --- |
| `cpla_customer_contract_company_rule` | header | `[('company_id', 'in', company_ids)]` |
| `cpla_customer_contract_line_company_rule` | line | `[('company_id', 'in', company_ids)]` |
| `cpla_customer_contract_evidence_company_rule` | evidence | `[('company_id', 'in', company_ids)]` |

Group rules. Odoo ORs the rules of groups the user belongs to, then ANDs the global rules. Rules for groups the user does not have are skipped. If the user has no matching group rule, only the global rule applies.

| XML ID | Groups | Domain |
| --- | --- | --- |
| `cpla_customer_contract_owner_rule` | Contract User | `[('owner_id', '=', user.id)]` |
| `cpla_customer_contract_line_owner_rule` | Contract User | `[('contract_id.owner_id', '=', user.id)]` |
| `cpla_customer_contract_evidence_owner_rule` | Contract User | `[('contract_id.owner_id', '=', user.id)]` |
| `cpla_customer_contract_manager_rule` | Contract Manager | `[(1, '=', 1)]` |
| `cpla_customer_contract_line_manager_rule` | Contract Manager | `[(1, '=', 1)]` |
| `cpla_customer_contract_evidence_manager_rule` | Contract Manager | `[(1, '=', 1)]` |

All nine rules grant read, write, create, and unlink in the rule itself. The ACL still removes write and unlink where the table above says so.

Contract Manager implies Contract User, so a manager matches both the owner rule and the manager rule. The OR keeps company-wide access inside the global company rule.

Finance Reviewer, Finance Manager, and Internal Auditor have no contract group rule. They read every contract in the active companies and cannot write. Sales, Recovery, and Application Administrator have neither a contract ACL nor a contract group rule.

A Contract User who is also a finance reviewer or an internal auditor matches the owner rule, so the combination does not widen access to other owners or other companies.

## Menus

| Menu | XML ID | Who sees it |
| --- | --- | --- |
| Contract Price Leakage | `menu_cpla_root` | Contract User, Contract Manager, Finance Reviewer, Finance Manager, Internal Auditor, Application Administrator |
| Configuration | `menu_cpla_configuration` | Contract Manager, Finance Reviewer, Finance Manager, Internal Auditor, Application Administrator |
| Contracts | `menu_cpla_contracts` | Contract User, Contract Manager, Finance Reviewer, Finance Manager, Internal Auditor |
| Customer Pricing Contracts | `menu_cpla_customer_contracts` | Same as Contracts |

Sales Pricing Reviewer and Recovery Operator do not see these menus. Application Administrator does not see Contracts. Hiding a menu is not the access control. The ACL and rules apply to direct ORM calls.

No Invoice Audit, Recovery, or dashboard menu was created.

## Server checks that ACLs do not express

- Company on create must be in the user's companies and in the active company selection.
- Company, reference, and currency-with-lines cannot be rewritten.
- Owner must be an eligible Contract User in the company.
- State changes only through actions.
- Submitted terms, lines, and evidence are frozen.
- `audit_authoritative` is always false.
- No sudo and no SQL `execute` in product Python. `local_testing/free_space.py` uses a database cursor and is outside the SEC-T007 scan, together with tests, docs, and `__pycache__`.
