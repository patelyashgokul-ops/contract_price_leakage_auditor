# Outstanding recovery and aging

Two balances stay separate.

Authorized unbilled principal is the current DEV-16 recovery target minus current posted principal. Drafts do not reduce it. A full reversal removes that billing from the current posted sum, so the unbilled amount returns.

Outstanding principal is current posted principal minus verified cash, supported credit notes, write-offs, other settlements, and advances. Unconfirmed payments, unknown credits, and FX do not reduce it. A draft is not outstanding.

Accounting receivable outstanding is the native residual of the posted receivable lines, including tax. It is reported as `accounting_residual` and is not renamed to principal.

## Example

Target 20000, posted 12000, draft 8000, no collection: posted 12000, unbilled 8000, outstanding 12000.

Target 20000, posted 20000, verified cash 12000, nothing else: unbilled 0, outstanding principal 8000.

## Due date

`_current_due_date` is the earliest open receivable `date_maturity`. If no open line remains but residual does, it falls back to `invoice_date_due`. A fully collected invoice stores no due date, so it leaves the overdue menu. The stored `due_date` is written during `_sync_evidence`, not on every read.

## Aging buckets

Open receivable lines are aged from their own `date_maturity`: not yet due when days are 0 or less, then 1–30, 31–60, 61–90, and more than 90. The amount in the bucket is the principal portion of that line's residual. One invoice with two payment-term lines is not aged entirely at the first date. A future maturity is not overdue. `overdue_days` is the age of the earliest overdue open maturity.

Commercial aging from the approval date is not calculated here. No scheduler and no dashboard are installed.

A disputed request sets `dispute_open` from current dispute rows. The dispute does not clear the due date.
