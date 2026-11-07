# 05 — Contract evidence and security

Date: 2026-10-28.

Signed pricing agreements are confidential. This phase links a file to one contract. It does not claim an immutable legal archive. DEV-05 and later governance can add snapshots and retention. Until then, protection is access control plus a freeze after the contract leaves draft.

## Storage

`cpla.customer.contract.evidence.datas` is `fields.Binary(attachment=True)`. Odoo stores the bytes as `ir.attachment` with `res_model` and `res_id` pointing at the evidence row. The module does not create attachment XML, a public token, or a report that prints the file.

`public` is left at the Odoo default, which is false. There is no unsecured binary on the header.

Metadata on the evidence row:

- Document title (`name`), also the filename.
- Document type.
- Source document reference.
- Description.
- `create_uid` and `create_date` (uploaded by / uploaded on).
- Parent contract and the contract company.

## Who can reach a file

Evidence ACL:

| Group | Read | Write | Create | Unlink |
| --- | --- | --- | --- | --- |
| Contract User | Yes | Yes | Yes | Yes |
| Contract Manager | Yes | Yes | Yes | Yes |
| Finance Reviewer | Yes | No | No | No |
| Finance Manager | Yes | No | No | No |
| Internal Auditor | Yes | No | No | No |
| Sales Pricing Reviewer | No row | | | |
| Recovery Operator | No row | | | |
| Application Administrator | No row | | | |
| Public, portal, blank group | No row | | | |

Record rules still apply. A global rule limits evidence to `company_id in company_ids`. A Contract User rule limits evidence to contracts they own. A Contract Manager rule is `(1, '=', 1)` and, because the manager implies Contract User, the two group rules are OR'd and then AND'd with the company rule. A manager therefore sees evidence in the active companies, not only their own contracts.

Finance and auditor users have no group rule on evidence. They see evidence in the active companies, read-only. A user who is both Contract User and Finance Reviewer or Internal Auditor is narrowed by the owner rule. Combined groups do not open another company's contracts.

`ir.attachment` access follows the evidence record. A user who cannot read the evidence cannot read the attachment. SEC04-T011 and SEC04-T012 cover unauthorized read and search. `export_data` by a user without export rights raises `UserError` before the records are read. That error is Odoo's export gate. Company isolation is the record rule, which is what the read and search tests assert.

## Freeze

Evidence can be added, edited, or deleted only while the parent is draft. Create, write, and unlink check write access on the parent first, then reject a non-draft parent. A submitted file cannot be replaced or removed by a Contract User or a Contract Manager. Reset to draft is a separate manager action and is the only path back to editing. Cancel keeps the file.

Module uninstall is the only unlink bypass, and it still calls `super().unlink`.

## What is not claimed

- No write-once storage.
- No hash chain.
- No legal hold.
- No customer portal download.
- No smart-button count of contracts on the partner form. That button was not added, so a customer form cannot leak a hidden contract count or a negotiated price.
