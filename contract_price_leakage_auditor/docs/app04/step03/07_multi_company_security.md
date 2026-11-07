# 07 — Multi-company security

Date: 2026-10-28.

## Permissions on `cpla.company.policy`

Access file: `security/ir.model.access.csv`. Five rows. No empty `group_id`. Unlink is 0 on every row.

| XML ID | Read | Write | Create | Unlink |
| --- | --- | --- | --- | --- |
| `group_contract_manager` | 1 | 0 | 0 | 0 |
| `group_finance_reviewer` | 1 | 0 | 0 | 0 |
| `group_finance_manager` | 1 | 0 | 0 | 0 |
| `group_internal_auditor` | 1 | 0 | 0 | 0 |
| `group_app_admin` | 1 | 1 | 1 | 0 |

`group_contract_user`, `group_sales_pricing_reviewer`, and `group_recovery_operator` have no model access and no menu.

Record rule `cpla_company_policy_company_rule`: global, all four permissions, domain `[('company_id', 'in', company_ids)]`.

Sensitive fields use groups `group_finance_reviewer`, `group_finance_manager`, `group_internal_auditor`, and `group_app_admin`. Contract Manager can read the row and cannot read discount, FX, tax, precision, or tolerance fields. Explicit read raises `AccessError`. `export_data` for a Contract User raises `UserError` because that user is not an administrator and does not have `base.group_allow_export`. Field access is a second gate for users who can export.

Menus `menu_cpla_root` (Contract Price Leakage) and `menu_cpla_configuration` (Configuration) use the five reader groups. `application` stays false. There is no Contract, Audit, or Recovery menu.

Groups still do not imply `base.group_user`, portal, public, Settings, or accounting groups. Tests assign `base.group_user` separately. No users are assigned by XML.

## Isolation tests

Fictional companies ABC India and ABC UAE are created inside `TransactionCase` and rolled back. They are not production companies.

| Test | Observed outcome |
| --- | --- |
| CFG-T001, CFG-T002 | Each company can have its own current policy. |
| CFG-T003, CFG-T019 | Writing Company A's pricing-date or FX candidate leaves Company B unchanged. |
| CFG-T036 | Company A Application Administrator write of Company B raises `AccessError`. The log recorded a record-rule read denial. Company B's candidate stayed `delivery`. |
| CFG-T037 | Create for the other company raises `AccessError`. A multi-company user with only Company A active cannot write Company B. Moving `company_id` raises `UserError`. The same user with both companies active can edit Company B's reason and does not change Company A's pricing-date candidate. |
| CFG-T034 | Contract User, Recovery Operator, and Sales Pricing Reviewer cannot write or search. ACL read denials were logged. |
| CFG-T040 | Contract User cannot read `fx_basis_policy`. Contract Manager `read()` omits sensitive fields. Readiness `candidates` omit them. |

These CFG tests are not a retroactive pass of the planned identifiers SEC-T008 through SEC-T015. Those identifiers were never executed under those names. `test_company_context_does_not_change_group_membership` still only checks that company context does not change group membership.

## Cross-company references

`check_approval_reference` rejects an approver who is not a member of the policy company. A shared partner or product (`company_id` false) is a warning, not a contract grant. A product or partner owned by the other company is `BLOCKING_CONFIGURATION_ERROR` when it can be read, and `CUSTOMER_NOT_ACCESSIBLE` or `PRODUCT_NOT_ACCESSIBLE` when the record rule hides it.

Client-supplied `company_id` is checked with `_check_target_company` before insert.
