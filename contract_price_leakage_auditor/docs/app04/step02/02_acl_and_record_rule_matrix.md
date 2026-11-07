# 02 — ACL and record-rule matrix

Date: 2026-10-28.

## Actual models

APP 04 owns no ORM model. `ir.model.data` for this module contains one category, six privileges, and eight groups.

## Actual ACLs

None. Searches of `ir.model.access` by these groups return no rows. There is no access row with an empty `group_id` for an APP 04 model, because there is no APP 04 model.

An empty `group_id` on a future sensitive ACL is forbidden. It would widen access beyond the role.

## Actual record rules

None. `ir.rule` is not linked to these groups. No global rule was added.

Odoo combines rules as follows, and later phases must keep that behavior:

- Global rules, those with no group, are combined with AND.
- Rules for the groups of the current user are combined with OR.
- The global result and the group result are combined with AND.
- Superuser bypasses record rules.

A future company rule should be global for the confidential model, with domain `[('company_id', 'in', company_ids)]`, and with read, write, create, and unlink enabled. It must not be paired with a second global domain that denies every row. Group ACLs still decide who may call the model. The rule decides which companies they can reach.

## Planned model security

These rows are requirements. They are not installed records. CRUD here does not include approval.

| Future model family | Company field | Read | Create | Write | Delete | Approval |
| --- | --- | --- | --- | --- | --- | --- |
| Customer contract | Required `company_id` | Contract User and above, Finance Reviewer and above, Auditor read-only | Contract User, Contract Manager | Contract User on drafts only; Manager where policy allows | No group by default | Contract Manager only after an approval method exists. Administrator no. |
| Contract version | Same company as the contract | Same as the parent contract | Contract Manager | No silent overwrite of an approved version | No group by default | Same approval method as the contract |
| Pricing line | Same company as the version | Groups allowed to see negotiated prices | Contract Manager, and Sales Pricing Reviewer only where a later rule allows | Same as create, never Auditor | No group by default | Not CRUD |
| Special discount | Company of the contract | Sales Pricing Reviewer, Contract Manager, Finance roles that a later rule names | Sales Pricing Reviewer | Requester cannot approve | No group by default | Separate from create. DEC-11 is open. |
| Invoice audit | Invoice company | Finance Reviewer and above, Auditor read-only | Not a user create. A later engine creates it. | Finance Reviewer for investigation notes only | No group by default | Not validate |
| Leakage finding | Invoice company | Finance Reviewer and above, Auditor read-only | Engine, not a general user | Investigation notes only | No group by default | Finance Manager for validation. Reviewer cannot validate. |
| Finance validation | Finding company | Finance Reviewer and above, Auditor read-only | Finance Manager | No rewrite of an approved row | No group by default | Finance Manager, not the requester |
| Recovery claim | Invoice company | Finance Manager, Recovery Operator need-based, Auditor read-only | Finance Manager | Operator cannot approve | No group by default | Finance Manager. Operator cannot approve. |
| Waiver | Claim company | Finance Manager, Auditor read-only | Finance Manager | Separate from claim write | No group by default | A later matrix. Not the operator. Not self-approval. |
| Customer dispute | Claim company | Finance roles and Auditor read-only | Finance Reviewer | No approval fields | No group by default | None on this row |
| Audit evidence | Parent company | Readers of the parent who also have evidence access | Users who can write the parent | No overwrite while a hold exists | No group by default | None |
| Audit batch | Explicit company | Finance Reviewer and above, Auditor read-only | Later scheduler identity, company-scoped | No cross-company rewrite | No group by default | None |
| Configuration | Company-owned where it stores financial defaults | Application Administrator | Application Administrator | Application Administrator | Restricted | Configuration is not approval |

Sales Pricing Reviewer, Recovery Operator, and Application Administrator do not receive a general read of every future model. "Limited" and "need-based" in the prompt stay limited until the model phase names the fields.

Internal users who only have `base.group_user` receive no APP 04 ACL.

## Delete policy

Historical versions, findings, validations, and evidence are not deletable by business groups. A later hold rule (SEC-09, DEC-17) must block unlink. DEV-02 does not invent the retention period.
