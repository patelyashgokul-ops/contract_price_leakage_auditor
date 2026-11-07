# Reassessment workflow

Date: 2026-11-05.

## States

`requested`, `under_evaluation`, `proposed_revision_ready`, `evidence_review_required`, `accepted`, `rejected`, `blocked`, `failed`, `cancelled`.

A completed calculation is `proposed_revision_ready` or `evidence_review_required`. It is not `accepted`. Only `action_accept` moves a `proposed_revision_ready` row to `accepted`, and only after the evidence, digest, and fresh-outcome checks pass.

## Who may act

| Action | Rule |
| --- | --- |
| Request | Contract manager, or superuser. Recorded `requested_by_id` and `requested_at`. |
| Evaluate and accept | Finance manager who can run the audit and read invoice source maps. |
| Reject | Finance reviewer or finance manager. |
| Cancel | The requester path used by contract managers, while the state is still open. |
| Self-approval | `requested_by_id` cannot accept, including superuser and a user who has both manager and finance-manager groups. |

Company scope is checked with `env.companies`. A record rule limits reassessments, events, and wizards to `company_id in company_ids`.

## Rejection

`action_reject` requires a reason. It stores `decision_by_id`, `decision_at`, and `decision_reason`, logs `rejected` with prior and new state, and refreshes the case reinvestigation flag. The proposed amounts, original amounts, and events stay. The current finding amount is not replaced. If the rejection is a material change and nothing later was accepted, `revision_verification` is `source_changed_review_pending`. The list and the finding alert say this is the last accepted result, not a fresh verification.

## Acceptance

Acceptance runs in a savepoint. It applies the engine, requires the stored successor to match the proposal, writes `accepted`, syncs the case, and logs `accepted` and `current_revision_changed`. A `UserError` from the apply path marks the request `blocked` and does not leave an accepted row without its evidence. `failed` is not relabeled `accepted`.

## Open duplicate

Partial unique index on `(finding_id, trigger_type, source_model, source_res_id, company_id)` where state is `requested`, `under_evaluation`, `proposed_revision_ready`, `evidence_review_required`, or `blocked`. The same open source event cannot have two active requests. A repeated evaluate of an unchanged fingerprint does not add a second current finding.

## Buttons that exist

Evaluate, Accept Proposal, Reject Proposal, Cancel Request, Verify Digest, View Original Snapshot, Open Investigation Case. Accept, Reject, and Cancel open the wizard because those methods require a reason. The wizard button is Request Reassessment. No button was added without a server method.

The run form still has `action_reassess`. That DEV-12 button was not removed.
