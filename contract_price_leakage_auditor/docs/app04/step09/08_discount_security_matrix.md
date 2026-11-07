# Discount security matrix

Groups are unchanged. XML ids are unchanged. None of the APP 04 groups imply `base.group_user`. Application Administrator does not receive the new models. Sales Pricing Reviewer and Recovery Operator still have no model access. The evaluator `cpla.discount.evaluator` has no access row. The financial abstract model `cpla.pricing.financial` still has no access row.

## Access rows

| Model | Contract user and manager | Finance reviewer | Finance manager | Auditor |
| --- | --- | --- | --- | --- |
| `cpla.discount.concession` | read, write, create, unlink | read | read, write | read |
| `cpla.discount.approval` | read, write, create, unlink | read | read, write | read |
| `cpla.discount.event` | read, create | read | read, create | read |

Python still refuses unlink of an approved concession, write of an approved concession, write or unlink of an event, and approval by anyone other than a finance manager who is not the requester. Finance manager has no create on concession or approval, so a finance manager cannot insert a request. Finance manager write on an approval is limited to `rejection_reason` while the state is submitted, plus the server methods that use `models.Model.write` after their own checks.

Auditor model access length is 13: the previous 10 rows plus the three discount models, all read-only. Export of a discount approval by the auditor raises `UserError` because the test user does not have `base.group_allow_export`.

## Record rules

Each stored discount model has:

- A global company rule: `[('company_id', 'in', company_ids)]`.
- A contract-user rule. Concessions match `version_id.contract_id.owner_id`. Approvals match the requester or the version owner. Events match the approval requester or the concession’s contract owner.
- A contract-manager rule `(1, '=', 1)`, so the manager implication of contract user does not hide other owners inside the same company.

No discount rule is attached to finance, auditor, sales, recovery, or application-administrator groups. Company isolation for those groups is the global company rule.

## Executed isolation

Company B’s contract manager cannot search Company A’s concession. Evaluating a Company A line as that user raises `AccessError`. Passing `company_id` of Company B on a Company A line returns `COMPANY_ACCESS_DENIED` with empty price fields. The strings `1150` and `1200` are absent from that result.

An auditor cannot write `percent_exact` on a concession. Application Administrator’s access-row count stays 1. Finance manager `perm_create` on `cpla.discount.approval` is false.

An attachment on a Company A approval is not returned by a Company B search. A user allowed in both companies cannot create an approval in Company A that points at a Company B version. The create raises `UserError`.

Confidential rates are not written to the log by the evaluator. The performance line in the test log is the elapsed time only.

## RPC

`action_approve`, `action_reject`, `action_submit`, `action_revoke`, and `evaluate` check the user on the server. Invisible buttons are not the control. Direct create of an event with a forged actor is refused. `sudo(` is not used in the discount implementation.
