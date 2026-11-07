# Recovery governance architecture

Date: 2026-11-05. Addon `contract_price_leakage_auditor`, manifest `19.0.1.14.0`. Odoo 19 Community. Direct depends remain `base`, `product`, and `sale`. `application` is false. License remains `Other proprietary` with `BLOCKER_LICENSE_DECISION_REQUIRED`.

DEV-16 turns a current finance-validated amount into a commercial decision. It does not post an invoice, a debit note, a credit note, a journal entry, or a payment. Finance validation stays the source of the validated amount. `decision_payload()` and `current_validated_amount()` are unchanged. `recovery_authority` on a finance validation stays false.

## Models

| Model | Role |
| --- | --- |
| `cpla.recovery.policy` | Company approval matrix. A draft is not authority. |
| `cpla.recovery.policy.level` | One level for recovery, waiver, settlement, or handoff. |
| `cpla.recovery.balance` | One current commercial balance per finance validation line. |
| `cpla.recovery.request` | Commercial pursuit of a validated amount. Not an invoice. |
| `cpla.recovery.request.line` | Slice of one finance decision line. |
| `cpla.recovery.waiver` | Authorized decision not to pursue a validated slice. |
| `cpla.recovery.dispute` | Customer challenge inside an approved recovery target. |
| `cpla.recovery.settlement` | Proposal, internal approval, and customer acceptance as separate fields. |
| `cpla.recovery.event` | Append-only commercial event. Actor and time come from the server. |
| `cpla.recovery.wizard` | Transient reason form. It does not post an `account.move`. |

There is no model named `cpla.recovery`, `cpla.waiver`, or `cpla.audit`. Methods live on the models. There is no second finance engine and no service class.

## Boundaries

Potential leakage remains the DEV-12 finding. An accepted reading remains DEV-14. A finance-validated amount remains DEV-15. A commercial waiver is not a finance rejection and not an accounting write-off. An approved recovery target is not a posted receivable. Customer acknowledgement is not cash. A settlement proposal is not customer acceptance. Internal approval is not customer acceptance. Billing and cash collection are `DEFERRED_TO_DEV17`.

The commercial equation for a current balance is validated = waiver + recovery target + unallocated. Dispute and acknowledgement are classifications inside the recovery target. `position_for()` always returns billed `0` and collected `0`.

## Workflow dimensions

Recovery state, customer discussion, and billing readiness are separate. Request states are draft, submitted, under_review, evidence_required, pending_approval, approved, rejected, withdrawn, superseded, and stale_source. `billing_state` is only `not_ready` or `ready_for_accounting`.

Direct `create`, `write`, and `unlink` on the commercial records raise `HISTORICAL_APPROVAL_PROTECTED` after the access check, except uninstall. Server methods use `models.Model.create` and `models.Model.write`.

Odoo 18 and Odoo 20 were not converted. A later port must retest company rules, `group_ids`, monetary Char amounts, `models.UniqueIndex` WHERE clauses, list views, activities, and the handoff payload.
