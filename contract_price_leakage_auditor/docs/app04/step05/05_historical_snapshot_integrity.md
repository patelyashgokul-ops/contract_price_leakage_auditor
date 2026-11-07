# 05 — Historical snapshot integrity

Date: 2026-10-28.

## What stays unchanged

After approval, ordinary create, write, and unlink cannot change:

- the version's commercial fields, approval identity, checksum, or supersession pointer
- version lines, including through a one2many write
- version evidence bytes
- approval events

Header line edits do not write version lines. Product list price, cost, pricelist, and last price are not contract prices. Renaming a customer does not change `partner_name` on an approved version. Archiving a product does not delete the line. The stored `product_name` remains. Changing the header description is refused once the header has left draft, so that write cannot replace the copied description.

`copy()` on a version is refused. Use Create Amendment.

## Deletion and archive

`unlink` on a version always raises, except during module uninstall. ACL unlink is 0 for every role. Approved lines and approved evidence cannot be deleted. Draft lines and draft evidence can be removed by a Contract User or Contract Manager.

Physical deletion of a draft version is not authorized. Cancel it. The cancel event remains. The version number is not reused.

There is no `active` flag on the contract. Archiving is not implemented. Once an approved version exists, cancelling the parent is refused, so the historical rows stay reachable. A universal legal retention period is not implemented. Evidence is kept with the version. This is not a legal hold product.

## Evidence

Evidence is linked to the version, not only to the parent contract.

- Initial approval points `source_evidence_id` at the header file and stores a checksum of those bytes.
- An amendment points `origin_evidence_id` at the previous version evidence and keeps the checksum.
- A new file may be added on the draft. Its bytes are hashed. They are not copied forward as a second binary when a later amendment only references them.

Approved evidence cannot be replaced. `action_request_evidence_correction` appends one `evidence_correction_requested` event and leaves the bytes in place. A second request is refused.

Only roles with read access on the evidence model, inside the company and owner rules, can read the file. There is no public attachment link and no portal ACL. Sales and recovery roles have no row. A user in the other company cannot read the evidence.

The checksum is SHA-256 of the file bytes or of the commercial snapshot JSON. It does not prove legal validity or tamper-proof storage.

## Events

`cpla.customer.contract.version.event` is append-only. `write` and `unlink` raise. Actor is `env.user`. `occurred_at` is the server time. Client values for both are discarded.

`UNIQUE(version_id, event_type)` allows one row of each type on a version.

| Event | When it is recorded |
| --- | --- |
| `draft_created` | Initial draft version created. |
| `amendment_created` | Amendment draft created. |
| `submitted` | Submitted for review. This is the approval request. |
| `approved` | Approval savepoint. Also used when an amendment is approved. |
| `rejected` | Rejection, with the reason. |
| `cancelled` | Draft or review cancellation. |
| `supersession_recorded` | Approval of a version that has a source. |
| `historical_reassessment_required` | Retroactive approval was blocked. |
| `evidence_correction_requested` | Manager asked for a file correction. The file was not replaced. |

There is no `retroactive_change_approved` event. Retroactive amendments are not approved.

The event type must match the version state, and the actor must be the person who actually performed that step. Context flags are not permission. `sudo()` is not used.

## Two historical perspectives

`AS_KNOWN_AT` is the set of approved rows and events that existed before a later attempt. Those rows are not overwritten.

`CURRENT_APPROVED_HISTORY` is the current set of approved versions after later authorized amendments. A blocked retroactive attempt does not add a new approved row, so the two views stay the same until a non-retroactive amendment is approved.

The computed flag `reassessment_required` is true on an unapproved amendment whose effective date is before today. It survives without being an approval. The blocked approval also inserts `historical_reassessment_required` in that same transaction. Odoo 19 `assertRaises` rolls back a savepoint around the raised error, and a web request rolls the request back too, so the event row from inside the failed call does not remain. The durable marker is `reassessment_required`. This is not invoice recalculation.

## Comparison

`compare_with` treats the called version as the baseline. The wizard orders by version number and uses the lower number as the baseline.

Categories: Added Product, Removed Product, Price Increased, Price Decreased, UoM Changed, Currency Changed, Contract Validity Changed, Customer Scope Changed, No Change.

A simple `price_delta` is set only when currency and unit match. Otherwise `normalization_required` is true and the delta is empty. `is_recovered_cash` is always false. A price increase is not recovered revenue and is not a forecast of future sales.

Cross-currency and unit conversion are not implemented. They belong to later phases.

## Known limits

- Effective status is computed in Python from the visible approved versions. A very large contract history is read when that status is searched. This phase does not claim a measured throughput.
- `change_summary` calls the comparison when the field is read. It is not a stored rollup and it is not cash.
- `lock_for_update` does not wait. A concurrent caller receives `LockError` and must retry. A retry of an already approved row is idempotent for an authorized approver.
- No legal archive, no external timestamp service, and no blockchain.
