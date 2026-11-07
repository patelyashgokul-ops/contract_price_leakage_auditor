# Accounting recovery architecture

Date: 2026-11-05. Addon `contract_price_leakage_auditor`, manifest `19.0.1.15.0`. Odoo 19 Community. Direct depends remain `base`, `product`, and `sale`. `account` is not a direct dependency. It is present because `sale` depends on it. `application` is false. License remains `Other proprietary` with `BLOCKER_LICENSE_DECISION_REQUIRED`.

DEV-17 reads an approved DEV-16 handoff and classifies native Accounting documents. It does not recompute leakage, rewrite a posted customer invoice line, post a write-off by itself, or send a collection demand.

## Models

| Model | Role |
| --- | --- |
| `cpla.recovery.billing.policy` | Company journal, account, tax treatment, and billing method. Nothing is seeded. |
| `cpla.recovery.billing` | One billing slice of an authorized recovery request. |
| `cpla.recovery.billing.line` | Principal allocated to one current recovery request line. |
| `cpla.recovery.accounting.link` | Link from that slice to one `account.move`. |
| `cpla.recovery.collection.evidence` | One partial reconciliation classification. History is kept when the match is removed. |
| `cpla.recovery.accounting.adjustment` | A credit document prepared against this billing. It is not cash. |

`cpla.recovery.request` gains `action_prepare_billing()` and `accounting_position()`. There is no model named `cpla.recovery`, `cpla.waiver`, or `cpla.audit`. Methods live on the models. There is no service class.

## Source of truth

| Question | Source |
| --- | --- |
| Validated amount | `cpla.finance.validation.decision_payload()` and `current_validated_amount()` |
| Authorized target, waiver, dispute, settlement | DEV-16 request and `cpla.recovery.balance.position_for()` |
| DEV-16 billed and collected | Always `0` on `position_for()` and on `accounting_handoff_payload()` |
| Posted recovery principal | Current posted `cpla.recovery.billing` rows |
| Cash, credit, write-off, advance, FX | `account.partial.reconcile` rows read from the recovery receivable |
| Outstanding principal | Posted principal minus verified reducing classifications. Not the raw tax-inclusive residual |

`recovery_authority`, `creates_customer_receivable`, `proves_cash_collection`, `is_waiver`, `is_recovery_billed`, and `is_cash_recovered` stay false on the earlier records. ENGINE_VERSION stays `dev12.1`. Snapshot schema stays `dev14.2`.

## Native Accounting used

`account.move`, `account.move.line`, `account.payment`, `account.partial.reconcile`, `account.bank.statement.line`, `account.payment.register`, and, when installed, `account.debit.note`. Credit notes use `account.move` `out_refund` with `reversed_entry_id`. This addon does not copy those tables into new accounting journals.

## What this phase does not do

No `ir.cron`. No reminder or escalation. No executive dashboard. No Odoo 18 or Odoo 20 conversion. No automatic unreconcile to make a report balance. No production data change.
