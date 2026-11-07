# Finance review handoff

`action_submit_for_finance` is the only path into `ready_for_finance_review`. It does not write a finance-validated amount.

## Gates

The case must be `under_investigation`. The actor is the owner or a contract manager, in the case company.

Then:

1. `action_refresh_source_status` runs. If `source_reassessment_required` is true, submission raises.
2. `root_cause` and `root_cause_explanation` are set.
3. `investigation_outcome` is set.
4. Every required checklist line is answered.
5. A required answer of `no` requires `outstanding_qualification`.
6. For `potential_leakage`: exposure is comparable, `exposure_unknown_count` is 0, the current exposure text is not blank, and every source evidence line is `verified` or `not_applicable`.
7. For every other case type: the exposure text is blank, and `outstanding_qualification` is set.

## Snapshot

`cpla.leakage.case.submission` stores:

| Field | Content |
| --- | --- |
| `case_id`, `company_id` | The case and its company. |
| `case_revision` | Revision at submit time. |
| `submitted_by_id`, `submitted_at` | Server user and server time. |
| `potential_exposure_exact` | The case display text. Not a certified amount. |
| `currency_id` | `exposure_currency_id`. |
| `root_cause`, `root_cause_explanation` | Investigator conclusion. |
| `investigation_outcome` | Investigator outcome. |
| `evidence_status` | Rolled-up evidence status. |
| `outstanding_qualification` | Disclosed gaps. |
| `finding_snapshot` | JSON list of current memberships: finding id, reference, identity, calculation revision, fingerprint, exposure text, currency name, status. |

A later submit creates another row. It does not overwrite the earlier row.

## Return

`action_return_for_rework` requires a finance reviewer or finance manager, state `ready_for_finance_review`, a reason, and a required action. The submitter of the latest snapshot cannot return that same case, even if that user also has the finance reviewer group.

The return writes `returned_by_id`, `returned_at`, `return_reason`, and `required_action` on the latest submission and on the case. The snapshot JSON, exposure text, and `case_revision` on the submission stay. State becomes `returned_for_rework`. The case is not closed.

Finance reviewers have write access on the case model so the screen can load, and `cpla.leakage.case.write` rejects their field writes with the message to use Return for rework. They do not have create or unlink on the case. They have write on the submission model. Public `submission.write` still raises. The return action uses `models.Model.write`.

There is no finance-reviewer routing matrix beyond the security groups. The case does not pick a named finance user. Any finance reviewer who can read the company may return it, except the submitter.

## What the handoff is not

The state name is ready for finance review. The chatter body is: "Submitted for finance review. This is not a finance-validated amount." No method approves, waives, bills, or collects.
