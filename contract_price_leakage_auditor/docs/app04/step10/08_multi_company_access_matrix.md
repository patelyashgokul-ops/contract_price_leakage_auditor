# Multi-company access

Company rules on `cpla.sale.price.lock` and `cpla.quotation.override.request` are global: `company_id in company_ids`. They have no groups. They do not enter the contract-user rule set.

Contract versions stay owner-scoped for Contract User and company-wide for Contract Manager. Finance and Auditor read through their own access rows. Those rules were not widened.

| Role | Policy mode | Price lock | Override wizard | Contract prices on a draft |
| --- | --- | --- | --- | --- |
| Sales / User | Read | Read, write, create, no unlink | No | Status text only. Amounts blank. |
| Contract User | Existing read | Read | Full | Amounts when the user can read the contract. Owner rule still applies. |
| Contract Manager | Existing read | Read | Full | Company contracts. |
| Finance Reviewer / Finance Manager / Auditor | Existing read | Read | No new approval right | Existing read groups. |
| Application Administrator | Existing policy write | No row | No | Not a commercial approver. |
| Sales Pricing Reviewer / Recovery Operator | No | No | No | No model access. |

`_sees_prices` is true for the technical superuser and for Contract User, Contract Manager, Finance Reviewer, Finance Manager, and Internal Auditor. Other users get the public message. Public messages do not contain amounts.

A Company B version cannot be stored on a Company A approval. The sale-link constraint rejects a line from another company or another order.

Export of a lock uses core `export_data`. A user without `base.group_allow_export` is refused. No new download action was added.

Sales / User can read a confirmed lock, including amounts, because that role stores the evidence. Draft quotation amounts stay blank for that role.
