# Native payment matching

Collection evidence is read from Accounting. It is not typed into a cash field.

## Records read

- The recovery `account.move` receivable lines (`account_type` `asset_receivable`).
- `matched_debit_ids` and `matched_credit_ids` (`account.partial.reconcile`).
- The counterpart move line and its `account.move`.
- `account.move.origin_payment_id` when the counterpart is a payment.
- `account.payment.reconciled_statement_line_ids` for bank evidence.
- `statement_line_id` when the counterpart itself is a bank statement line.
- `partial.exchange_move_id` when the counterpart is that exchange move.

The customer invoice receivable is the debit. The amount in invoice currency is `debit_amount_currency`. `amount` on the partial is company currency.

## What is not proof of cash

Community `_get_invoice_in_payment_state` returns `paid`. `payment_state = paid` is not bank-verified cash. A registered payment without a statement line is `unconfirmed_payment` when `bank_verification_required` is true.

Odoo 19 payment registration does not put two invoices on one payment unless `group_payment` is true. The allocation used here is the partial amount on this receivable, not `payment.amount`.

## Refresh

`action_refresh_collections` calls `_sync_evidence`. Current partials are upserted by `partial_reconcile_key`. A partial that is no longer in the reconcile set is marked `counts_current` false, `is_verified_cash` false, and `verification_state` `REVERSAL`. The row is not deleted. This method does not call `remove_move_reconcile`.

## Failed read

Reading `account.move` without Accounting rights raises `TECHNICAL_ACCOUNTING_FAILURE`. The position is not returned as outstanding zero.
