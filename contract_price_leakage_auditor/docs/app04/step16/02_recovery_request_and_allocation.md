# Recovery request and allocation

A recovery request is created only by `cpla.recovery.request.prepare_from_validation()`. The caller must be a contract manager in the validation company. The finance validation must be `approved` or `partially_approved`, current, and not stale. A draft or other unapproved state raises `RECOVERY_SOURCE_NOT_READY`. A previously approved decision that is no longer current raises `STALE_FINANCIAL_EVIDENCE`.

`prepare_from_validation()` with no line amounts proposes the full current validated amount of each line, not the unallocated remainder. Callers that want a smaller slice pass `line_amounts`. The same prepare key returns the existing open request. `force_new` creates another request only when the balance still has room. Rejected, withdrawn, superseded, and stale requests do not reserve room.

## Balance

`cpla.recovery.balance` has `UNIQUE(validation_line_id)`. Amounts are Char exact texts. `_move()` refuses a negative allocation and refuses waiver plus recovery above the validated amount. Dispute plus acknowledgement cannot exceed the current recovery target. Open proposals reserve room before approval. An approved request counts in the recovery target. A rejected request does not.

Withdrawal of an approved request releases the recovery allocation only when `handoff_key` is empty. The historical request row stays, with state `withdrawn`.

## What approval checks

Approval locks the request, checks the company, the current finance source, the fingerprint, the unallocated room, the currency, the policy level, and the authenticated user. The approver must be in `contract_price_leakage_auditor.group_contract_manager`. Finance reviewer, finance manager, recovery operator, auditor, and application administrator are not selectable commercial approvers. Superuser and `env.su` are not group members. Self-approval raises `SELF_APPROVAL_PROHIBITED` when `four_eyes_required` is set. A missing level raises `APPROVAL_MATRIX_MISSING`. An amount above every ceiling raises `APPROVAL_LIMIT_EXCEEDED`.

Approving a request does not create `account.move` or `account.payment`. `billed_amount_exact` and `collected_amount_exact` stay `0`.
