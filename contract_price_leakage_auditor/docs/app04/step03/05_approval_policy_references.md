# 05 — Approval policy references

Date: 2026-10-28.

No approval workflow is implemented. A setting does not grant financial authority.

## Who can do what

| Group XML ID | Policy access | Activation |
| --- | --- | --- |
| `group_contract_user` | None | No |
| `group_contract_manager` | Read, except sensitive fields | No |
| `group_sales_pricing_reviewer` | None | No |
| `group_finance_reviewer` | Read, including sensitive fields | No. Write raises `AccessError`. |
| `group_finance_manager` | Read, including sensitive fields. Implied group includes Finance Reviewer. | May call `action_request_activation`. The call still refuses while decisions are open. |
| `group_recovery_operator` | None | No |
| `group_internal_auditor` | Read, including sensitive fields | No. Cannot rewrite history. |
| `group_app_admin` | Create and write current drafts. Read sensitive fields. | No. Not a commercial approver. |

XML IDs were not renamed. The prompt aliases `group_cpl_*` are names only. No `group_cpl_*` records exist.

`action_request_activation` requires Finance Manager or the superuser. If `requested_by` is the current user, it raises `AccessError` (self-approval) before the open-decision error. Otherwise it raises `UserError` and writes nothing. `approved_by` stays empty.

`check_approval_reference(user)` rejects a user outside the policy company with `ValidationError` (`Cross-company approval reference is rejected`). A same-company user raises `UserError`: DEC-11 and DEC-12 are open, and no limit was stored.

There is no unlimited-approval flag and no numeric approval limit.

## Deferred workflows

Contract approval, special-discount approval, finance validation, recovery approval, and waiver approval remain later phases. Recovery Operator does not approve and does not post. Application Administrator does not imply Finance Manager, Recovery Operator, or Settings.

Server methods check the user, the group, the company, and the open decisions. Menu visibility is not the authorization check.
