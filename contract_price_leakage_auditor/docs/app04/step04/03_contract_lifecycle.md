# 03 — Contract lifecycle

Date: 2026-10-28.

## States

| State | Meaning |
| --- | --- |
| `draft` | Preparation. Incomplete data may be saved. Not an audit price. |
| `ready_for_review` | The draft passed the server readiness checks. A person may review it. Not approval, not activation, and not an audit price. |
| `cancelled` | The draft or the review submission was cancelled. Evidence is kept. Not a deletion. |

There is no `approved`, `active`, `superseded`, `amended`, or `expired` state. A date that falls inside `valid_from` and `valid_to` does not change the state.

`state` cannot be written through `write` or a One2many command. Actions call `_write_state`, which uses `super().write` for that field only. RPC cannot call methods whose names start with `_`.

The form statusbar is read-only. Badge colors are info, warning, and muted. There is no success decoration and no Approved label.

## Who can act

| Action | Contract User | Contract Manager | Other roles |
| --- | --- | --- | --- |
| Create and edit own draft | Yes | Yes, in company scope | No contract write ACL |
| Submit own draft | Yes, if owner | Yes | No |
| Submit someone else's draft | No | Yes | No |
| Cancel own draft | Yes | Yes | No |
| Cancel another user's draft or a review submission | No | Yes | No |
| Reset review submission to draft | No | Yes, after `reset_reason` is stored | No |
| Reassign owner | No | Yes, to an eligible contract user in the company | No |

Application Administrator has no contract ACL and no approval method.

## Submit for review

`action_submit_for_review` checks write access, locks the header and its lines and evidence, and then validates. A contract already in `ready_for_review` returns true and does not create another record. A cancelled contract cannot be submitted. The transition is one write of the state. It does not insert a review route, a duplicate header, or duplicate lines.

The error lists the blockers. Examples:

- The contract currency is missing.
- Valid To is required before review. An open-ended contract is not an approved policy.
- At least one negotiated product line is required.
- A supporting evidence file is required before review.
- Extra covered customers are recorded while DEC-03 is open.

Review also requires a company, an exact customer compatible with that company, a reference, an eligible owner, both dates in order, a current same-company policy, an active currency, and lines with a positive price and the product's default unit. A shared contact or shared product is compatible. The policy does not need `operationally_approved`. No current policy is operationally approved.

An overlap warning does not block submission and does not pick the lower or higher price.

## Protection after submission

While the state is `ready_for_review`, `write` rejects changes to commercial terms. A Contract Manager may write only `reset_reason` and `cancel_reason`.

Line create, write, and unlink, and evidence create, write, and unlink, call `check_access('write')` on the parent first. If the parent is not draft, they raise `UserError`. Reassigning `contract_id` or a different `company_id` is rejected. One2many commands use the same methods.

Reset to draft does not rewrite prices. It requires a stored reset reason and the manager group. After reset, the record is draft again and can be edited.

## Cancellation and deletion

Cancel does not delete the header, the lines, or the evidence. Cancelling an already cancelled contract does nothing.

`unlink` on the header raises `UserError` for every business user. The only bypass is Odoo's module-uninstall context, which still goes through `super().unlink` and access checks. The header ACL has no unlink permission. There is no archive flag. A permissive delete path was not created for later approved history.

Physical deletion of a never-submitted draft is not allowed. The approved deletion policy is still open, so the safe behavior is cancel, not delete.

## DEV-05 boundary

This lifecycle stops at review readiness. DEV-05 must add approval and versioning explicitly. It must not treat `ready_for_review` as approved, and it must not infer approval from the calendar.
