# 06 — Retroactive amendment policy

Date: 2026-10-28.

## Rule

An amendment is retroactive when it has a source version and `effective_from` is earlier than `fields.Date.context_today`. The first snapshot may use a past Valid From. That first snapshot is not a retroactive amendment.

Same-day effective date is not retroactive.

There is no company switch that turns retroactive approval on. `retroactivity_policy` is the constant `not_authorized`. Inventing an allow-retroactive flag would hide the open decision.

## What a blocked attempt records

On approve, before any approval write:

- the version stays `ready_for_review`
- approver, approval timestamp, approval reference, and checksum stay empty
- `reassessment_required` is true because the effective date is before today and the version is not approved
- one event `historical_reassessment_required` is inserted in the approval transaction
- the error states that the retroactivity policy is undecided, approval is blocked, a historical reassessment is required, and posted invoices are not recalculated

The event stores the contract, version, company, server time, authenticated actor, and the reason. The previous approved version id remains the source. The new row does not become the authority.

That event is part of the approval transaction. A web request that raises the block rolls the event back with the request. Odoo 19 `assertRaises` does the same with a savepoint. The marker that remains is `reassessment_required` on the unapproved amendment. A second attempt does not insert a second event of the same type while the first event is still in the transaction.

## What is not done

- Posted invoices are not read and not repriced.
- Leakage findings are not created.
- Debit notes, recovery claims, waivers, and accounting entries are not created.
- The previous approved price, approval timestamp, and checksum are not rewritten.
- The prior published history is not replaced.

## Future reassessment

DEV-05 records that a historical period may need reassessment. It does not identify invoice ids and it does not calculate an amount. Later audit phases own that work and need their own approval.

Until a company policy is actually authorized, retroactive approval stays blocked. That open decision is not assigned an owner in this repository.
