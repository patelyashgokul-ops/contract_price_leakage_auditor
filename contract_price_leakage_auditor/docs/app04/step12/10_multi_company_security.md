# Multi-company security

Company isolation uses the DEV-02 groups and global company rules. The new rules are in `security/invoice_audit_rules.xml`. They have no groups, so they stay outside the grouped-rule set checked by `SEC-T007`. The domain is `[('company_id', 'in', company_ids)]` for the run, the result, and the finding. Read, write, create, and unlink are all restricted by that domain.

## Access rows

`security/ir.model.access.csv` adds fifteen rows:

| Group | Run, result, and finding |
| --- | --- |
| Contract user | Read |
| Internal auditor | Read |
| Finance reviewer | Read |
| Contract manager | Read, write, create. No unlink. |
| Finance manager | Read, write, create. No unlink. |

Sales pricing reviewer, recovery operator, and application administrator have no rows on these models. The administrator still has access only to `cpla.company.policy`. The auditor's model-access count is 19. Write for the auditor remains only on `cpla.pricing.applicability.check`.

`write` on a run, result, or finding calls `check_access` before a `UserError`, so a read-only user receives `AccessError`. Result writes are refused. Finding writes allow only the engine supersede of `is_current`, `current_identity`, and `finding_status`, or a runner update of `last_evaluated_at` and `run_id`. Unlink is refused except during module uninstall.

`action_run` requires a contract manager, a finance manager, or the superuser. The company must be in `env.companies`. Search does not use `sudo`, so a contract manager who cannot read an invoice does not see it. The tests create finance users with `account.group_account_invoice`.

## Menus

`Contract Price Leakage Auditor → Audits` contains Invoice Audit Runs, Audit Results, Potential Leakage Findings, and Audit Exceptions. Those menu items are granted to the contract user, contract manager, finance reviewer, and finance manager. They are not granted to the auditor or the application administrator, because the auditor menu test is an exact equality that does not include this menu.

The invoice form smart button `Invoice Audit` is visible to those groups and to the internal auditor. It opens results for that invoice.

Export of a result uses Odoo's `export_data`. Without `base.group_allow_export` it raises `UserError`. `SEC12-T011` covers that denial.

## Negative tests that passed in the green suite

Company A does not return Company B findings. A Company B contract version is not applied to a Company A invoice. A cross-company sales line is rejected by the mapper. A user with no audit group cannot read a finding (`AccessError`). A sales user cannot write protected evidence. The auditor has no method that validates finance recovery. The administrator is not given finance-manager rights by these rows. Combined groups still cannot read the other company's result. Product code outside tests does not call `sudo(` or `.execute(` for this audit.

Error text does not include the other company's price. Logs record the run reference, counts, and the move id.
