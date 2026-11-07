# Source change and idempotency

One current row exists per invoice line. `current_line_id` is unique while `is_current` is set. A move with no lines uses `current_header_move_id`, also unique. PostgreSQL allows multiple nulls, so the pointer is set only on the current row. A second current row for the same line raises `IntegrityError`. The persist path catches that inside a savepoint and returns the winning row when the fingerprint matches.

The fingerprint is a SHA-256 of invoice identity, type, state, company, customer, product, quantity, unit, price, discount, currency, tax ids, sales-line ids, reversed document, invoice date, accounting date, and each related lock id, lock fingerprint, revalidation flag, and version. `write_date` alone is not the fingerprint.

Unchanged evidence returns the same current row, including a documentary verification. A changed fingerprint supersedes the old row. The old row stays. The new revision gets `reassessment_required`, `HISTORICAL_SOURCE_CHANGED`, `audit_ready` false, and `quantity_trusted` false. A previously verified status becomes `HISTORICAL_EVIDENCE_INCOMPLETE`.

`action_accept_reassessment` is finance-manager only. It creates another revision when the live fingerprint still matches and the evaluation has no blocking exception. It does not overwrite the previous row.

`write` cannot set status or prices. After the access check, the only ordinary write is clearing `is_current` and the current pointers, and only for a user who can map. `unlink` is refused except during module uninstall, and it also checks unlink access first. Users without write access receive `AccessError` before the overwrite message.

`MAPPING_FAILED` is a status value. The batch savepoint does not currently insert a row with that status. The failure signal is the absence of a new verified row.

Two database sessions were not run. The unique constraint is the cross-transaction guard. A sequential `TransactionCase` does not prove concurrent workers. `self.cr.commit` is forbidden in that test class.

The fingerprint lookup searches locks per line. That is an N+1 query risk for a large batch. Unchanged rows are not validated again beyond the fingerprint compare.
