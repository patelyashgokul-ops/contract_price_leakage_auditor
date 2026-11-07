# Billing idempotency and allocations

## Identity

The billing identity is a canonical JSON of company, request, handoff key, source revision, method, slice key, and line amounts. `models.UniqueIndex` on `billing_identity` excludes cancelled, superseded, and fully_reversed rows.

`prepare_from_request` searches that identity first. The same call returns the existing record. `IntegrityError` on that unique index returns the existing record. It does not create a second slice. `LockError` from `lock_for_update()` raises `FINANCIAL_DECISION_CONFLICT`. A serialization failure is not retried into a second allocation.

The line unique index is `(request_line_id, slice_key) WHERE counts_current`.

## Slice key

If the caller omits `slice_key`, it is the canonical JSON of `(line_id, amount)` pairs. Partial billing passes an explicit slice. Reserved and posted current lines count toward the line's `current_recovery_exact`. The next slice must fit in what remains.

## Room

`_assert_room` sums current billing lines for the request line, including drafts. Posted principal for reporting uses only current posted states. A draft therefore blocks a duplicate slice and does not count as posted billing.

## One economic exposure

The original leakage invoice and the recovery invoice stay linked by `origin_move_id` and the accounting link. The recovery amount is not added back onto the DEV-12 finding. DEV-16 `billed_amount_exact` and `collected_amount_exact` stay `0`. DEV-17 amounts live only on the billing position.

## Full reversal and a later bill

A fully reversed billing drops out of the unique index because its state is released and its lines are not current. A new prepare for the same authorized identity can create the next document. Historical posted principal remains on the reversed row and is reported as `historical_posted_principal`.
