# Financial revision and current exposure

Date: 2026-11-05.

## One current row

For one identity (`company`, invoice line, allocation, cutoff token, underbilling), at most one finding has `is_current` true and a non-null `current_identity`. Historical rows keep their amount text with `is_current` false, `current_identity` null, and status `superseded_by_reassessment`.

The current exposure sum used by DEV-12 adds current potential findings. It does not add a superseded 5000 to a current 4000. A proposed 4000 is not in that sum until acceptance creates or updates the current finding. After a verified return is accepted, the current potential text is 4000 and the historical row still shows 5000.

A rejected proposal leaves the previous current amount in place.

## Verification state

`revision_verification` is computed, not stored, and searchable. The search method classifies in Python and returns an id domain. It does not call `search` with the computed field inside the domain.

| State | When |
| --- | --- |
| `historical_superseded` | `is_current` is false. |
| `reassessment_proposed` | An open row is `proposed_revision_ready`. |
| `current_result_uncertain` | An open row is `evidence_review_required`, `blocked`, or `failed`. |
| `source_changed_review_pending` | Another open row, or a material rejection with no later acceptance. |
| `reassessment_accepted` | This finding is the successor of an accepted reassessment and nothing above applies. |
| `current_verified` | Current finding with no open or unresolved material rejection. |

Search filters `filter_source_review` and `filter_accepted_revision` are on the finding search view. The finding form says that a pending source review is the last accepted result and is not a fresh verification.

Stale findings stay in the current-exposure sum until a new revision is accepted or the engine clears the identity. They are visible through `revision_verification` so a report can list `source_changed_review_pending`, `reassessment_proposed`, and `current_result_uncertain` separately. The sum is not silently reduced and the stale rows are not dropped from the database.

## Repeated acceptance

Accepting the same fingerprint again does not insert another current row. `_upsert` updates `last_evaluated_at` when the fingerprint matches. The partial unique index blocks a second open request for the same finding, trigger, and source.
