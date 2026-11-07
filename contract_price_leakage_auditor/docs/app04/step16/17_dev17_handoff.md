# DEV-17 handoff

This file is the boundary. DEV-17 is not implemented. No recovery invoice, debit note, credit note, journal entry, payment, reconciliation, or write-off is created here.

## Read API

`cpla.recovery.request.accounting_handoff_payload()` returns a dictionary. `action_authorize_handoff(reason)` may set `billing_state` to `ready_for_accounting` and write `handoff_key` when the blockers are clear and a handoff level authorizes the user. A second call returns the same payload and the same key.

| Key | Meaning |
| --- | --- |
| `status` | `READY_FOR_ACCOUNTING` or `NOT_READY_WITH_REASONS` |
| `reasons` | Blocker sentences when not ready |
| `recovery_request_id`, `reference` | The commercial request |
| `company_id`, `partner_id`, `case_id` | Company, customer, investigation case |
| `validation_id`, `validation_reference` | DEV-15 decision |
| `currency_id` | Request currency |
| `authorized_amount` | Handoff amount, or `0` when not ready |
| `current_recovery_target` | Current approved target |
| `lines` | Finding identity, fingerprint, revision, authorized amount, original authorized amount, source `move_line_id` |
| `waivers`, `disputes` | Current commercial rows |
| `settlement_id` | Current settlement, if any |
| `customer_acceptance_state`, `internal_settlement_state` | Separate dimensions |
| `source_fingerprint`, `source_revision`, `approval_snapshot` | Bound evidence |
| `handoff_key`, `handoff_revision` | Idempotency. Not an invoice number |
| `fx_rate_exact`, `fx_rate_date` | Recorded rate, or empty |
| `billed_amount`, `collected_amount` | Always `0` |
| `creates_account_move`, `creates_customer_receivable`, `proves_cash_collection` | Always false |

## Blockers implemented

The request must be approved. The finance source must be current and not stale. The commercial policy must be current. When `dispute_blocks_handoff` is true, a current dispute blocks handoff of that request. A current settlement that is not accepted, withdrawn, or rejected blocks handoff. A zero target blocks handoff. Non-zero billed or collected figures block handoff because this phase must not pretend accounting has posted them.

## Deferred

Posted billing, debit notes, credit notes, payment registration, reconciliation, write-offs, collection reminder crons, and the accounting callback that would store a real move id are `DEFERRED_TO_DEV17`. Do not start that phase from this file.

## Open decisions

Business acceptance of DEV-16 is pending. License remains `BLOCKER_LICENSE_DECISION_REQUIRED`. Commercial release is NO-GO. Each company must approve its own commercial matrix. No production ceiling was invented. Odoo 18 and Odoo 20 were not installed or tested.
