# Multi-company finance security

Record rules in `security/finance_validation_rules.xml` are global, with no group, and domain `[('company_id', 'in', company_ids)]` on the policy, the level, the validation, the line, the approval, and the wizard.

`_require_company` raises `COMPANY_ACCESS_DENIED` when the company is not in `env.companies`. The superuser skips that check inside the method. Approval methods still refuse the superuser through `_in_group`.

A Company B user does not reach that code when reading a Company A case or validation. The record rule raises `AccessError` first. Search returns an empty set.

Access rows in `security/ir.model.access.csv`:

- Contract user and contract manager: read on the policy, level, validation, line, and approval.
- Finance reviewer: read on the policy and levels. Write and create, no unlink, on the validation and the line. Read and create, no write or unlink, on the approval. Full wizard access.
- Finance manager: the reviewer rights, plus write and create, no unlink, on the policy and levels.
- Internal auditor: read on the five models. No wizard row.
- App admin, sales pricing reviewer, and recovery operator: no finance rows.

No group has unlink on the header or write on an approval event. Public create still raises after the access check.

`export_data` allows a finance reviewer, finance manager, or internal auditor, then calls `super()`. Odoo 19 `super()` also requires administrator or `base.group_allow_export`. Owner and superuser are denied by the finance check. The module does not email a customer.

Menus under Finance Review are not granted to the app admin, the sales pricing reviewer, or the recovery operator. There is no finance cron.

`test_sec12_t013` still forbids `sudo(` and `.execute(` in addon Python outside tests. Finance code uses `lock_for_update()` rather than `cr.execute`.
