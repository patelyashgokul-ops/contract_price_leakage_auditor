# 01 — Security architecture

Date: 2026-10-28.
Odoo 19.0.0 final. Addon `contract_price_leakage_auditor`.

This phase validates the role foundation. It does not approve a commercial authority matrix, and it does not add contract, pricing, audit, or recovery behavior.

## Role architecture

Eight groups under six privileges. Privileges are separate, so a user can hold a contract role and a finance role together. Two privileges are ladders. The other four are single roles.

Odoo 19 presents the groups of one privilege as one selection. The higher group implies the lower group. A user who selects Contract Manager also receives Contract User. A user who selects Finance Manager also receives Finance Reviewer.

`ir.module.category.exclusive` stays false. In Odoo 19 that flag constrains which modules may be installed together. It is not the switch that makes application roles mutually exclusive.

## Preserved identifiers

DEV-01 already created the groups. DEV-02 keeps those external IDs. The names proposed in the DEV-02 prompt are aliases, not new records.

| Proposed ID | Preserved XML ID | Record name | Privilege |
| --- | --- | --- | --- |
| `group_cpl_contract_user` | `group_contract_user` | Contract User | `privilege_contract_access` |
| `group_cpl_contract_manager` | `group_contract_manager` | Contract Manager | `privilege_contract_access` |
| `group_cpl_sales_pricing_reviewer` | `group_sales_pricing_reviewer` | Sales Pricing Reviewer | `privilege_sales_pricing_review` |
| `group_cpl_finance_reviewer` | `group_finance_reviewer` | Finance Reviewer | `privilege_finance` |
| `group_cpl_finance_manager` | `group_finance_manager` | Finance Manager | `privilege_finance` |
| `group_cpl_accounting_operator` | `group_recovery_operator` | Recovery Operator | `privilege_recovery` |
| `group_cpl_internal_auditor` | `group_internal_auditor` | Internal Auditor | `privilege_internal_audit` |
| `group_cpl_administrator` | `group_app_admin` | Application Administrator | `privilege_application_admin` |

Full IDs use the module prefix `contract_price_leakage_auditor.`.

## Inheritance

| Group | Direct `implied_ids` | Does not imply |
| --- | --- | --- |
| Contract Manager | Contract User | Finance, recovery, auditor, administrator, `base.group_user` |
| Finance Manager | Finance Reviewer | Recovery Operator, accounting groups, administrator |
| Contract User, Sales Pricing Reviewer, Finance Reviewer, Recovery Operator, Internal Auditor, Application Administrator | nothing | Every other application group and the standard user, portal, public, and settings groups |

`all_implied_ids` includes the group itself. Tests compare that closure.

APP 04 groups do not imply `base.group_user`. An internal user is created by assigning `base.group_user` separately. Assigning an APP 04 group does not by itself turn a portal or public user into an internal user, and it does not grant every internal-user right of other apps.

No group is assigned to existing users by the XML.

## Provisional boundaries

The Phase 00 matrix is not an approved authorization policy. DEC-11, which decides who may approve recovery and at which amounts, is unapproved and blocks DEV-16.

Until that decision exists:

- No group can approve a contract, discount, leakage amount, recovery, or waiver, because those actions do not exist.
- Finance Manager is only the higher finance group. It is not an unlimited approval right.
- Recovery Operator does not approve recovery and does not post accounting documents.
- Application Administrator does not receive finance, contract, recovery, or auditor groups, and does not receive Settings / Administration.
- Internal Auditor does not receive finance or recovery groups.
- Posting an accounting document remains an Odoo accounting-group right. This module does not imply those groups. `account` is not installed for this addon.

## Technical administrator boundary

Odoo superuser and database owner access bypass ordinary record rules. APP 04 cannot claim to stop that. Ordinary users are limited by group membership. There is no business method that calls `sudo()`.

## What this phase did not create

No `ir.model.access` row, no `ir.rule`, no menu, no report, no attachment, no cron, and no business model.
