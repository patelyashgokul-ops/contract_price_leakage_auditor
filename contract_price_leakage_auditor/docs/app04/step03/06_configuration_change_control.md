# 06 — Configuration change control

Date: 2026-10-28.

## Revision metadata

Each `cpla.company.policy` row stores:

| Item | Field |
| --- | --- |
| Company | `company_id` |
| Policy selections | The ten policy fields |
| Previous revision | `supersedes_id` on the new row |
| Later rows | `revision_ids` |
| Requester | `requested_by`, defaulted to the creating user when omitted |
| Timestamp | `requested_on` |
| Reason | `change_reason`, required |
| Approver | `approved_by`, always empty in this phase |
| Approval status | `state`, never `approved_ready` |
| Effective dates | `effective_from`, `effective_to` |
| Version | `version`, assigned as one more than the highest version for that company |

No credentials are stored on the row.

Effective dates must be ordered. An end date before the start date raises `ValidationError` on create, write, and the constraint.

## How a change is saved

- Create inserts version 1 as the current row when the company has no current row. A second current row raises `ValidationError`. The partial unique index `cpla_company_policy_one_current_idx` is the database backstop.
- Write of policy fields, the reason, or the dates updates that same current row and recomputes `state` to `draft` or `not_configured`. Repeated saves do not create another version (CFG-T010).
- `action_submit_for_review` sets `ready_for_business_review` through `super().write` so the public state guard does not block the button. The row is still not operationally approved.
- `action_new_revision` runs in a savepoint. It freezes the current row with private `_freeze_current` (`super().write({'is_current': False})`) and creates the next draft. RPC cannot pass a context flag into that private method. The new reason says the draft is not approved. Candidate values are copied and stay unapproved (CFG-T044, CFG-T045).
- `action_request_activation` raises before any write. A failed check leaves state, version, and `is_current` unchanged (CFG-T043).

Direct create or write of `approved_ready` is rejected. A constraint rejects the state if it is stored another way through the ORM.

## Who can change history

Application Administrator can edit the current draft only. A historical row raises `UserError` on write and unlink (CFG-T039). Internal Auditor read does not include write. Contract Manager write raises `AccessError`.

The database owner and the Odoo superuser with context `_force_unlink` are outside this application control. Uninstall uses that flag so user-created rows do not block dropping the model. Routine forms set `delete="false"` and `duplicate="false"`.

## Readiness

`get_configuration_readiness` returns company id and name, `validated_at`, `revision`, `policy_id`, `state`, `is_current`, `operationally_approved` false, `missing`, `invalid`, `blocking`, `warnings`, `candidates`, `next_action`, and `codes`.

`blocking` lists all ten open decisions even when every candidate is filled. Sensitive fields the user cannot read are omitted from `candidates` and mentioned as a warning. The next action tells a business owner to resolve the open decisions. Technical completeness is not approval.

The form banner states that the policy is not operationally approved. The status bar does not offer `approved_ready` and is readonly, so a click cannot write the state.
