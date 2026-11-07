# Multi-company accounting security

Six record rules in `security/billing_rules.xml` use `[('company_id', 'in', company_ids)]` on the policy, billing, billing line, accounting link, collection evidence, and adjustment.

## ACL

`security/ir.model.access.csv` adds 30 rows: five groups times six models. Finance manager is `1,1,1,0`. Contract user, contract manager, finance reviewer, and internal auditor are `1,0,0,0`. Recovery operator and app admin receive no new rows. App admin model access stays `cpla.company.policy` only. Direct create, write, and unlink on the billing models raise `HISTORICAL_APPROVAL_PROTECTED` after the access check, except during uninstall. Server methods call `models.Model.create` and `models.Model.write`.

## Server checks

`_require_company` rejects a company that is not in `env.companies`. Superuser skips that check and still fails `_in_group`, so superuser cannot post. Cross-company journal and account assignment fails `check_company`. A Company B user reading a Company A request is denied by the recovery record rule.

`export_data` on billing and collection evidence requires finance manager or internal auditor, then `check_access('read')`, then the base export. A contract manager who is not a finance manager receives `COMPANY_ACCESS_DENIED` before the base export check. The auditor export test also needs `base.group_allow_export`.

`billing_position` and the move smart buttons call `check_access('read')` on `account.move`. A finance manager without an invoice group does not receive the move through this API. The failure is `TECHNICAL_ACCOUNTING_FAILURE`. There is no `sudo(` and no `.execute(` in the addon Python.

Attachment models for the billing, collection evidence, and adjustment records are included in the existing attachment guard. No new role was added.
