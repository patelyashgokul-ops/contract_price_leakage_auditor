# Finance evidence checklist

`prepare_from_case` and `action_submit` refuse the package unless every current case membership passes these gates:

- The case state is `ready_for_finance_review`.
- `reinvestigation_required`, `finance_package_stale`, and `source_reassessment_required` are false.
- The finding is current, `finding_status` is `potential`, and `revision_verification` is `current_verified` or `reassessment_accepted`.
- A proposed DEV-14 reassessment is not accepted evidence. `reassessment_proposed`, `source_changed_review_pending`, and `current_result_uncertain` block the package.
- The finding has a contract version, a latest audit result, a stored fingerprint, and a potential of at least zero.
- The case customer and company match the findings. A shared partner with no company is allowed. A partner tied to another company is not.
- Line currencies are exactly the stored review currency.
- An approved current policy exists before submit.

`action_submit` sets `evidence_completeness` to `complete` and stores `submission_snapshot`. That flag means the gates above passed. It does not mean a human reviewed a signed contract image.

`action_request_evidence` sets `review_required`, records the missing note, and returns the case to investigation. A line reason `ADDITIONAL_EVIDENCE_REQUIRED` blocks `action_request_approval` even when the amounts add up.

`AUTHORIZED_DISCOUNT_CONFIRMED` requires an approved discount record for the same company, version, and product. Missing approval evidence stays `APPROVAL_EVIDENCE_MISSING`.
