# DEV-18 handoff

DEV-18 is not implemented. This file is the read boundary. There is no `ir.cron`, no reminder, no escalation, and no dashboard.

## Models

| Name | Technical name |
| --- | --- |
| Recovery billing | `cpla.recovery.billing` |
| Billing line | `cpla.recovery.billing.line` |
| Accounting link | `cpla.recovery.accounting.link` |
| Collection evidence | `cpla.recovery.collection.evidence` |
| Adjustment | `cpla.recovery.accounting.adjustment` |
| Billing policy | `cpla.recovery.billing.policy` |

## Methods a later scheduler may call

All of these re-read Accounting. None of them posts, unreconciles, writes off, or emails a customer.

| Need | Call |
| --- | --- |
| Prepare a slice | `cpla.recovery.billing.prepare_from_request(request_id, line_amounts=None, slice_key=None, existing_move_id=None)` |
| Draft, post, cancel | `action_create_draft`, `action_post`, `action_cancel(reason)` |
| Current posted and net principal | `billing_position()` or `cpla.recovery.request.accounting_position()`. `posted_principal` and `net_billed_principal` |
| Unbilled target | `unbilled_target` on that position |
| Outstanding principal | `outstanding_principal`. Native residual is `accounting_residual` |
| Verified cash principal | `verified_cash_principal` |
| Bank verification | `verification_state`. Labels are comma-separated. `BANK_VERIFIED_CASH` is the cash label |
| Noncash | `credit_note_principal`, `write_off_principal`, `other_settlement_principal`, `advance_principal` |
| FX | `fx_company_amount`. Principal is not increased |
| Aging | `aging` dict and `overdue_days`. Due date is `due_date` |
| Report | `reconciliation_report(company_id)`. `totals` is always false |
| Refresh one billing | `action_refresh_collections` |

`position_for()` on `cpla.recovery.balance` still returns billed `0` and collected `0`. Do not write cash back into those fields.

## Billing methods

`manual_handoff`, `standalone_invoice`, `debit_note`, `existing_document`. Debit notes require `account.debit.note` in the registry. Absence raises `ACCOUNTING_METHOD_UNAVAILABLE`.

## Payment evidence fields

`account.partial.reconcile` id is `partial_reconcile_key`. Counterpart move, statement line, matched amount, principal, company amount, classification, credit category, and verification state are stored on the evidence row. `is_verified_cash` is true only for `verified_cash`.

## Reversal

A missing partial is marked `REVERSAL` and `counts_current` false. History stays. DEV-18 must not unreconcile a payment to refresh a report.

## Duplicate billing

Identity is company, request, handoff key, source revision, method, slice key, and line amounts. Released states are outside the unique index. The same identity returns the existing row.

## Company

Record rules restrict every billing model to `company_ids`. Posting requires finance manager and `account.group_account_invoice`. The commercial requester cannot post when four-eyes is on.

## Open policy

Each company still approves its own journal, account, taxes, fiscal position, and whether bank verification is required. No statutory tax was seeded. GOLD-ACC17-014 FX collection was `NOT_EXECUTED`. Business acceptance of DEV-17 is not this file. License remains `BLOCKER_LICENSE_DECISION_REQUIRED`. Commercial release remains NO-GO.

## What DEV-18 must not assume

A draft is not posted billing. Posted billing is not cash. A reconciled credit, write-off, or FX gain is not cash. `payment_state = paid` is not bank verification. One payment amount is not allocated in full to every matched invoice. A failed accounting read is not zero outstanding.

Alert suppression, deadline rules, and executive dashboards are not built. A scheduler that only calls the read APIs above is the safe next step, and it is not started here.

## Odoo 18 and Odoo 20

Not installed and not converted. A later port has to retest `account.move`, debit notes, `account.move.reversal`, `account.payment`, `account.partial.reconcile`, `payment_state`, outstanding accounts, statement reconciliation, taxes, exchange moves, journals, company rules, list views, and groups. Odoo 19 remains the master.
