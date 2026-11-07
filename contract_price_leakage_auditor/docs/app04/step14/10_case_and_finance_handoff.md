# Case synchronization and finance handoff

Date: 2026-11-05. DEV-15 is not implemented.

## Same identity

When the accepted proposal keeps the original identity, `_sync_cases` finds current case memberships for that finding and company. It calls `_mark_source_revision`, sets `reinvestigation_required` with `models.Model.write`, and logs `case_flagged`. Root cause, root-cause explanation, case state, and `reviewed_exposure_exact` are not rewritten. If `finance_package_stale` is already true, it also logs `finance_package_flagged`.

`reinvestigation_required` is readonly and is not in the case manager's writable field set. It means the source changed and someone should look again. It is not a finance rejection. It does not by itself block finance submit. `source_reassessment_required` remains the hard submit gate from DEV-13.

The investigator clears the flag by `action_accept_current_source` after retargeting the case to the current finding. A full reversal that leaves no current finding cannot be retargeted. The zero lives on the audit result. The flag can remain until another open material reassessment is gone. That limit is for DEV-15 to respect.

## Different cutoff

A different proposed identity logs `separate_interpretation_recorded` on the case. The reviewed amount stays. The new identity is not added into the case total. `_refresh_reinvestigation_flag` then sets the flag only if some other open or rejected material reassessment still exists. An accepted row is not counted as pending.

## Open and rejected requests

`_refresh_reinvestigation_flag` sets the flag when the case has a material reassessment in an open state or `rejected`. Cancelling or rejecting calls this refresh. Accepting a separate cutoff also calls it. Same-identity acceptance forces the flag true for that event.

## Finance package

DEV-13 already preserves the submission package and sets `finance_package_stale` when the source revision changes after submit. DEV-14 does not delete that package, does not auto-approve the amount, and does not start finance validation. The old package remains the historical submission. `finance_package_stale` says it is not the current fully supported evidence.

## DEV-15 boundary

No finance-validated amount, recovery target, waiver, debit note, payment, or reconciliation is created. `action_accept` does not post the invoice.
