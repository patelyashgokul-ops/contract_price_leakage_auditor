# Reassessment calculation

Date: 2026-11-05. Engine `dev12.1`.

DEV-14 does not reimplement `(adjusted - actual) * eligible quantity`. `_price_values` builds a virtual run and calls `_price_allocation`. `_apply` creates a run in mode `reassessment` and calls `_audit_mapping` on the credit maps or the origin map for that trigger. The run is not a second audit of the whole company.

## Comparison fields

Copied at request time: `original_quantity_exact`, `original_adjusted_exact`, `original_actual_exact`, `original_exposure_exact`, `original_version_id`, `original_cutoff`.

Proposed by the engine: `proposed_quantity_exact`, `proposed_adjusted_exact`, `proposed_actual_exact`, `proposed_exposure_exact`, `proposed_version_id`, `proposed_cutoff_token`.

`delta_exact` is proposed exposure minus original exposure when both identities are the same family and both amounts exist. A separate cutoff leaves the delta blank and `delta_class` `undetermined`. The form group "Revision comparison" shows original and proposed side by side, then `difference_explanation`. The reviewer sees the reason text, not only a new amount.

## Worked company-currency figures

These are the texts the tests assert. They are company-currency decimal texts from `generic_coa`. They are not labeled INR.

Quantity return, no retier: quantity 100, approved 1150, invoice 1100, original potential 5000. Verified posted return of 20. Proposed eligible 80, proposed exposure 4000, delta -1000. Class `exposure_decreased`. `is_recovered_cash` and `is_writeoff` stay false.

Full reversal: proposed 0, delta -5000, class `exposure_eliminated`. After acceptance the current potential finding for that identity is gone. The successor result stores 0. The original result still stores 5000.

Unchanged fingerprint: proposed 5000, class `no_material_change`. Acceptance does not add a finding. Exposure stays 5000.

Separate cutoff: V1 at 1000 and a later approved 1200 are not summed. Cutoff before the later approval proposes the earlier version. The current finding at 20000 stays the current reading for the blank cutoff.

## What acceptance stores

The engine `_upsert` supersedes the previous row for that identity when the fingerprint changed, then inserts one current row. If the unique index conflicts and the existing row already has the same fingerprint, the insert returns that row. Two current rows with the same identity are rejected by `UNIQUE(current_identity)`.
