# Case field dictionary

Fields below are the stored or computed fields on `cpla.leakage.case` unless another model is named. Readonly fields change through action methods that call `models.Model.write`. A client write of those fields raises `UserError`.

## Identity and parties

| Field | Type | Rule |
| --- | --- | --- |
| `reference` | Char, unique | `ir.sequence` code `cpla.leakage.case`, prefix `CPL-CASE/%(year)s/`, padding 5. `noupdate`. Company is empty on the sequence so references are not regenerated per company. Existing references are not rewritten. |
| `title` | Char | Set at creation. A contract manager may edit it while the case is open. |
| `company_id` | Many2one `res.company` | Required. Taken from the findings. Not editable. |
| `partner_id` | Many2one `res.partner` | Required. One customer. Not editable. |
| `case_type` | Selection | Mapped from the finding category. See `TYPE_BY_CATEGORY`. |
| `primary_category` | Char | The finding category, or `MIXED` when a grouped case has more than one category. |
| `grouping_basis` | Char | Empty for a single finding. Otherwise one of `same_sales_order`, `same_contract_version`, `same_invoice`, `explicit_same_issue`. |

## Lifecycle

| Field | Type | Rule |
| --- | --- | --- |
| `state` | Selection | `new`, `assigned`, `under_investigation`, `evidence_pending`, `ready_for_finance_review`, `returned_for_rework`, `closed_with_reason`. Default `new`. |
| `owner_id` | Many2one `res.users` | Empty until a contract manager assigns an eligible investigator. |
| `participant_ids` | Many2many `res.users` | Extra internal users. Not a second owner. |
| `assigned_at` | Datetime | First assignment time. Later reassignment does not clear it. |
| `opened_at` | Datetime | Case creation time. |
| `first_detected_at` | Datetime | Earliest finding `first_detected_at`. |
| `closed_at`, `closed_by_id`, `closure_reason`, `closure_note` | | Set by close or by merge (`superseded_by_case`). |
| `reopened_at` | Datetime | Set on authorized reopen. |
| `superseded_by_case_id` | Many2one case | Set when merge closes the source case. |
| `case_revision` | Integer | Starts at 1. Material events increment it. |

## Exposure

| Field | Type | Rule |
| --- | --- | --- |
| `current_potential_exposure_exact` | Char | Sum of unique current eligible finding texts when one currency is comparable. Blank when unknown or mixed. Never a fabricated `0`. |
| `reviewed_exposure_exact` | Char | Last accepted snapshot. A later source change does not replace it until accept. |
| `exposure_currency_id` | Many2one `res.currency` | Set only when the sum is comparable. |
| `exposure_comparable` | Boolean | False when the sum was refused. |
| `exposure_unknown_count` | Integer | Findings skipped because the amount is blank, the finding is not current, or currencies were mixed. |
| `source_reassessment_required` | Boolean | True when a current membership is stale, a successor exists, or currencies mixed on refresh. |

There is no `finance_validated_exact`, `billed_recovery_exact`, `collected_recovery_exact`, or recovered-cash flag on the case.

## Investigation

| Field | Type | Rule |
| --- | --- | --- |
| `priority`, `priority_reason` | Selection / Char | Empty until a manager sets them. No amount threshold. |
| `severity`, `severity_reason` | Selection / Char | Same labels as priority. Independent of the amount. |
| `root_cause`, `root_cause_explanation` | Selection / Text | Investigator conclusion. Not copied from the detector category. Explanation required. |
| `investigation_outcome` | Selection | Investigator conclusion. Not a finance decision. |
| `investigation_summary` | Text | Manager-editable note, or the outcome explanation when the summary is still empty. |
| `outstanding_qualification` | Text | Required when a required checklist answer is No, and for every exception submission. |
| `evidence_status` | Selection | Rolled up from evidence lines. |
| `exception_queue` | Selection | Set for non-monetary case types. False for `potential_leakage`. |

## Dates and SLA readiness

| Field | Type | Rule |
| --- | --- | --- |
| `target_review_date` | Date | Only if a manager types one. No default of 1, 3, or 7 days. |
| `age_calendar_days` | Integer, computed | Calendar days from `opened_at` to `closed_at` or now. The help text says this is not a business-day SLA. |
| `is_overdue` | Boolean, computed, searchable | True only when `target_review_date` is before today and the case is not closed. |
| `evidence_requested_at` | Datetime | First evidence request. |
| `finance_submitted_at`, `submitted_by_id` | | Latest submission action. |
| `returned_at`, `returned_by_id`, `return_reason`, `return_required_action` | | Latest return. The submission row keeps its own copy. |
| `last_activity_at` | Datetime | Updated by material events. |
| `escalation_policy_reference` | Char | Optional label. No cron reads it. |

## Membership (`cpla.leakage.case.membership`)

| Field | Rule |
| --- | --- |
| `case_id`, `finding_id`, `company_id` | Required. Company matches the case. |
| `is_current` | Partial unique index `(finding_id) WHERE is_current IS TRUE`. Stays true after operational close so a second case is not opened for the same finding. |
| `reviewed_exposure_exact`, `reviewed_fingerprint`, `reviewed_revision`, `reviewed_status`, `reviewed_identity` | Values copied from the finding at link time. |
| `linked_at`, `removed_at` | Link and retire timestamps. |

Public `create`, `write`, and `unlink` raise. The workflow uses `models.Model.create` and `models.Model.write`, which still check ACLs.

## Event, checklist, evidence, submission

Event rows store `event_type`, `actor_id` (the server user), `occurred_at` (server time), `reason`, `previous_value`, `new_value`, `source_model`, `source_res_id`, and `case_revision`. Public write and unlink raise.

Checklist rows store `code`, `name`, `required_for_submission`, `answer` (`unanswered`, `yes`, `no`, `not_applicable`), `note`, `answered_by_id`, and `answered_at`. Direct write allows only `answer` and `note`.

Evidence rows store `evidence_kind` (`source` or `investigation`), `name`, `source_model`, `source_res_id`, `status`, `status_note`, and reviewer timestamps. Source lines are references, not copied invoice binaries.

Submission rows store the package fields listed in `09_finance_review_handoff.md`. Public create, write, and unlink raise. Return metadata is written by the return action.
