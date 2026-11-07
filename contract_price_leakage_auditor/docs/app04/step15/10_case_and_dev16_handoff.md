# Case synchronization and DEV-16 handoff

DEV-13 still owns the case. Finance code does not write `current_potential_exposure_exact`, `reviewed_exposure_exact`, or the root cause.

| Finance action | Case effect |
| --- | --- |
| Prepare and submit | Reads the case in `ready_for_finance_review` and stores `submission_id`. Does not approve an amount. |
| Request evidence | `action_return_for_rework` with the missing note. |
| Final approval or formal rejection | Appends event type `finance_decision_recorded`. `new_value` is the validation reference. The reason text says the decision is not a receivable, a waiver, or collected cash. The case is not closed. |
| Stale source | The validation is flagged. The case flags already set by DEV-14 (`finance_package_stale`, `source_reassessment_required`, `reinvestigation_required`) stay in place until the investigator accepts the successor. |

`action_open_finance_validations` opens the linked validations from the case.

DEV-16 may read `decision_payload()` only when `current` is true. That payload's `approved_amount` is the finance-validated amount. It is not a recovery target, a waiver, a billed receivable, or collected cash. A stale or superseded payload must not be treated as fresh recovery authority. `current_validated_amount(company, partner)` is the company total of current non-stale line amounts, and the same finding identity is not added twice.

Recovery, waiver, dispute, debit note, and payment methods are not implemented.
