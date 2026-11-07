# Historical financial evidence

The approved version is the evidence record. DEV-08 does not add a second calculation table and does not write a row during normalization. Repeated calls do not create versions or rate rows.

## Frozen at approval

For `historical_exact_date` and `historical_last_known_prior`, approval stores:

- `fx_policy_date` — the clause date, not today.
- `fx_rate_date_used` — the date of the row that was frozen.
- `fx_rate_id` and `fx_target_rate_id` — pointers. Deleting a rate sets them null and does not rewrite the numbers below.
- `fx_company_per_source_exact` and `fx_company_per_target_exact`.

Fixed-rate clauses store the user-entered multiplier. They do not snapshot a market row.

Client creates and writes cannot set the server snapshot fields. A fixed multiplier can be written only while the policy is `fixed_rate` and the version is still draft. Approved versions remain read-only under the existing version rules.

## Corrections

Changing `inverse_company_rate` after approval leaves the frozen text and `snapshot_sha256` unchanged. The next normalization still uses the frozen number and sets `fx_reassessment_required` when the live lookup differs. That flag does not create a case. DEV-14 owns controlled reassessment.

## As-known cutoff

A cutoff before `approved_at` returns `HISTORICAL_EVIDENCE_REVIEW_REQUIRED` and no price. A later approval is not applied to an earlier cutoff. Two approvals in the same second compare equal, so the cutoff test waits more than one second between approvals.

## Amendments

`create_amendment` copies clause inputs. It copies `fx_multiplier_exact` only when the policy is `fixed_rate`. It does not copy server snapshot fields. The new draft is snapshotted again if it is approved. `compare_with` adds "Financial Clause Changed" when the financial signatures differ.

## Checksum

The financial signature wraps the DEV-07 quantity checksum, which wraps the DEV-05 version checksum. Existing approved rows are not rewritten on upgrade. New approvals include the clause in the hash. Upgrade of an unconfigured version leaves `fx_policy` at `unconfigured` and does not invent a rate.
