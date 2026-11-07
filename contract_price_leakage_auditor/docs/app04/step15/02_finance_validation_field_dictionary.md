# Finance validation field dictionary

Amounts are decimal text in `Char` fields. They use the review currency rounding (`ROUND_HALF_UP`). They are not floats.

## Header `cpla.finance.validation`

| Field | Meaning |
| --- | --- |
| `reference` | Sequence `CPL-FV/%(year)s/`, padding 5. Not company-specific. |
| `company_id` | Legal entity of the case. Not taken from the client as proof of authority. |
| `case_id` | DEV-13 investigation case. |
| `partner_id` | Customer copied from the case. |
| `submission_id` | Case submission snapshot reviewed by this package. |
| `state` | Workflow state. Separate from `decision_type`. |
| `decision_type` | `unset`, `full_validation`, `partial_validation`, or `full_rejection`. |
| `requested_by_id`, `requested_at` | Authenticated user and server time at submit. |
| `reviewer_id`, `reviewed_at` | User who started review, and server time. |
| `policy_id`, `policy_reference`, `policy_snapshot` | Approved matrix revision bound at submission. |
| `review_currency_id` | Currency of the findings. Mixed currencies are not added. |
| `fx_rate_exact`, `fx_rate_date`, `fx_rate_note` | User-recorded rate. Empty unless a user supplied one. |
| `accepted_potential_exact` | Sum of current accepted finding potential. Not overwritten by the decision. |
| `proposed_validated_exact`, `proposed_rejected_exact`, `proposed_unresolved_exact` | Proposal. Not an approved total. |
| `validated_exact`, `rejected_exact`, `unresolved_exact` | Copied from the proposal only when the last level approves. A denied level leaves validated at `0`. |
| `evidence_completeness` | `incomplete`, `complete`, or `review_required`. |
| `decision_reason`, `decision_by_id`, `decision_at` | Final explanation, actor, and server time. |
| `approval_level_done`, `next_level_sequence`, `required_level_count` | Matrix progress. |
| `stale_source` | Accepted evidence changed after this package was opened. |
| `is_current` | This row is the current decision for the case. A stale or superseded row is not current. |
| `level_denied` | A required level denied the proposal. Validated stays `0`. |
| `missing_evidence_note` | What the reviewer asked the case to supply. |
| `submission_snapshot` | Canonical JSON of the package at submit. |
| `supersedes_id`, `superseded_by_id` | Controlled correction chain. |
| `creates_customer_receivable`, `proves_cash_collection`, `is_waiver`, `is_recovery_billed`, `is_cash_recovered` | Always false. |

## Line `cpla.finance.validation.line`

`finding_id`, `result_id`, `membership_id`, `finding_identity`, `source_fingerprint`, `source_revision`, `version_id`, `product_id`, `move_line_id`, `allocation_id`, `potential_exact`, `currency_id`, proposed and approved validated/rejected/unresolved amounts, `decision_type`, `reason_code`, `explanation`, `counts_current`, `decision_by_id`, `decision_at`.

`counts_current` is true only for lines of a current non-stale full or partial approval. A zero-validated line in a partial package still occupies the identity so the same finding is not validated twice. A full rejection does not count as current validated exposure.

## Approval event `cpla.finance.validation.approval`

`level_sequence`, `authority_group`, `decision` (`approved`, `denied`, `evidence_requested`), `amount_exact`, `currency_id`, `actor_id`, `acted_at`, `reason`, `source_fingerprint`, `evidence_snapshot`, `policy_id`, `policy_reference`. Evidence requests use level sequence `0` so they do not collide with the unique approved-level index.

## Policy

`cpla.finance.validation.policy`: `reference` (`CPL-FVP/%(year)s/`), `company_id`, `currency_id`, `threshold_basis`, `partial_validation_allowed`, `four_eyes_required` (default true), `change_reason`, `state`, `approved_by_id`, `approved_at`, `is_current`, `supersedes_id`.

Level: `level_sequence`, `authority_group` (`finance_reviewer` or `finance_manager`), `applies_from_exact`, `has_ceiling`, `maximum_exact`.
