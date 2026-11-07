# Grouping and duplicate prevention

Grouping policy was not approved as an automatic rule. The safe behavior is one current finding to one current case. Several findings share a case only when the caller passes an explicit basis.

## Bases

| Basis | What must match |
| --- | --- |
| `same_invoice` | Same `move_id`, plus the common rules below. |
| `same_sales_order` | Same sales order on the allocation or the latest audit result. |
| `same_contract_version` | Same `version_id`. |
| `explicit_same_issue` | An authorized user attests that the findings are one issue. Same customer is not enough. The common rules still apply. |

Common rules for every multi-finding call:

- One company.
- One customer.
- One case type.
- One currency when amounts are present.
- A known amount is not added to an unknown amount.
- `same_customer` is not a basis and raises.

Cross-company findings raise, including when the user is allowed into both companies.

Calling `create_from_findings` with several findings and no basis raises.

## Current membership

`cpla.leakage.case.membership` has unique index `(finding_id) WHERE is_current IS TRUE`.

One finding has at most one current membership. Historical rows remain after merge, split, or an accepted source revision, with `is_current` false and `removed_at` set.

Operational close does not clear `is_current`. A second `create_from_findings` for that finding returns the same case, including a closed case. That avoids a second active exposure for the same current finding.

A repeated call with the same full set of findings returns that case. A partial overlap raises instead of attaching the finding to a second case.

## Idempotency and failure

The create and link run inside one savepoint. `IntegrityError` on a single finding returns the canonical current case when one exists. A multi-finding conflict rolls back and raises `UserError`. A checklist seed failure rolls the membership back with the savepoint. The class test covers that rollback.

Before a new current membership is inserted, the code flushes `is_current = false` on the row being retired. The database unique index then sees the retire. Merge and split do this inside the savepoint, so a failed link rolls the retire back.

## Merge and split

Merge is contract-manager only. Both cases must be open (not in finance review and not closed), same company, same customer, same case type, and compatible currency. The source case is closed with `superseded_by_case` and `superseded_by_case_id`. It is not deleted. Findings stay. Exposure is recomputed on both cases. The source current exposure drops because its memberships are no longer current.

Split moves at least one current finding and must leave at least one. The new case is created with the same grouping note as the reason. Totals are recomputed. History events `split`, `finding_removed`, and `finding_linked` are stored.

## Exposure

Current case exposure is the sum of `potential_leakage_exact` on current memberships whose finding is still `potential` with a decimal amount, in one currency. The sum uses `_arithmetic` and `_text` from the DEV-08 helpers. It does not multiply price by quantity again.

Blank amounts increment `exposure_unknown_count` and are not added as zero. Mixed currencies blank the display and set `source_reassessment_required`. Superseded findings are not in the current membership set, so their old amounts are not added.
