# Investigation workflow

Every transition is checked in Python. Hiding a button is not the control. The actor must pass the role check, the company check, and the current state check.

## States

| State | Meaning |
| --- | --- |
| `new` | Opened from current findings. No owner. |
| `assigned` | An eligible investigator is `owner_id`. |
| `under_investigation` | The owner started the review. |
| `evidence_pending` | More evidence was requested. The case stays open. |
| `ready_for_finance_review` | The investigator submitted a package. Finance has not validated an amount. |
| `returned_for_rework` | A finance reviewer sent it back. The previous snapshot remains. |
| `closed_with_reason` | Operational close with a reason. Not recovered cash. |

## Who may move the case

| Action | Who | From | To |
| --- | --- | --- | --- |
| `action_assign` | Contract manager | `new` or another open state except finance review and closed | `assigned` on the first assign. Later assigns keep the state and log `owner_changed`. |
| `action_start` | Owner or contract manager | `assigned` or `returned_for_rework` | `under_investigation`. `evidence_pending` is refused. |
| `action_mark_evidence_pending` | Owner or contract manager | `under_investigation` | `evidence_pending`. A reason is required. |
| `action_resume_investigation` | Owner or contract manager | `evidence_pending` | `under_investigation` |
| `action_submit_for_finance` | Owner or contract manager | `under_investigation` only | `ready_for_finance_review` |
| `action_return_for_rework` | Finance reviewer or finance manager, not the submitter | `ready_for_finance_review` | `returned_for_rework` |
| `action_close` | Contract manager | Any open state except `ready_for_finance_review` | `closed_with_reason` |
| `action_reopen` | Contract manager | `closed_with_reason`, except `superseded_by_case` | `under_investigation` |

`action_resume_investigation` is the return from `evidence_pending`. The evidence-pending wizard calls `action_mark_evidence_pending`. Checklist and evidence edits stay available in `evidence_pending` because that state is in `OPEN_STATES`. Submission requires `under_investigation`, so a case left pending cannot be submitted.

## Close and reopen

Close requires a reason in `duplicate_case`, `source_error`, `not_in_scope`, `withdrawn_after_review`, or `no_action_required_after_authorized_review`, plus a note. `superseded_by_case` is rejected on `action_close`. Merge writes that reason itself.

Close does not delete the finding, does not clear `is_current` on the membership, and does not set recovered cash.

Reopen requires a reason, a current membership, and a closure reason other than `superseded_by_case`. The prior closure fields stay on the record. A new event stores the previous reason.

A direct RPC write of `state` raises. `create` on the case model raises. Context flags are not a second authorization path.

## Finance handoff is not validation

Submit checks the list in `09_finance_review_handoff.md`. The chatter note says the submission is not a finance-validated amount. No method on the case sets a validated, billed, or collected figure.
