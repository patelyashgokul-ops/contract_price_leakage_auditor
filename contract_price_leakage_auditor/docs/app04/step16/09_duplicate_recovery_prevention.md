# Duplicate recovery prevention

The canonical slice is the current DEV-15 finance validation line. One `cpla.recovery.balance` row exists per line (`UNIQUE(validation_line_id)`). Approved waiver plus approved recovery cannot exceed that line's validated amount. Open drafts reserve the same room, so two full proposals of the same line cannot both be prepared.

Partial requests on one line are allowed when the amounts do not overlap. A 12000 request and an 8000 request on a 20000 line can both be approved. A second 10000 request against a line that already has a current 10000 proposal or approval raises `ALLOCATION_EXCEEDS_VALIDATED`.

Rejected and withdrawn requests release the reservation. A later prepare can use the room. The rejected row is kept and is not counted in the current target.

## Concurrency

Approval locks the shared balance with `lock_for_update()` in ascending id order. Odoo 19 uses `FOR UPDATE SKIP LOCKED` and raises `LockError` for the waiter. A concurrent update can also raise a serialization error. The losing worker must not commit a second slice. The code does not catch that serialization error and retry into another allocation. The waiver level index does not cover `waiver_approved`, so the balance lock is the double-waiver control. The request level index covers `recovery_level_approved`, `handoff_authorized`, and `settlement_level_approved` where `level_sequence > 0`.

`test_rec16_concurrent_waiver_allocation` runs two worker threads against the committed concurrency pool. The log shows `could not serialize access due to concurrent update` on `cpla_recovery_balance` and the test still passed: only one current allocation of that slice. A specific winning amount is not claimed.

## Handoff identity

`handoff_key` is `c{company}|v{validation}|r{request}|rev{revision}`. A partial unique index rejects a second non-null key. Repeating `action_authorize_handoff()` returns the same key and does not create a second authorization. The key is not an invoice number.
