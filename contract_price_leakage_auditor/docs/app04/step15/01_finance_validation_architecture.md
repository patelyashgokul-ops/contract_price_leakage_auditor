# Finance validation architecture

Date: 2026-11-05. Addon `contract_price_leakage_auditor`, manifest `19.0.1.13.0`. Odoo 19 Community. Direct depends remain `base`, `product`, and `sale`.

DEV-15 decides how much of the current accepted potential leakage is financially supportable. It does not recalculate prices, post invoices, create payments, or start recovery.

## Source of truth

| Amount | Owner |
| --- | --- |
| Potential leakage | `cpla.leakage.finding.potential_leakage_exact`, produced by the DEV-12 engine and replaced only by an accepted DEV-14 reassessment. |
| Accepted revision | `revision_verification` of `current_verified` or `reassessment_accepted` on that current finding, plus the linked `cpla.invoice.audit.result`. |
| Finance-validated leakage | `cpla.finance.validation.validated_exact` after the last required approval level, and only while `is_current` is true and `stale_source` is false. |
| Rejected and unresolved | The same validation header. They are not waivers and they are not cash. |

`decision_payload()` and `current_validated_amount()` are the downstream read API. There is no class named `FinanceValidationDecisionService`. `recovery_authority` is always false.

## Models

| Model | Role |
| --- | --- |
| `cpla.finance.validation.policy` | Company approval matrix. A draft is not authority. No amount is seeded. |
| `cpla.finance.validation.policy.level` | One ordered level: role, applies-from, and optional ceiling. |
| `cpla.finance.validation` | One finance review package for one investigation case. |
| `cpla.finance.validation.line` | One finding decision. Amounts stay on the line. |
| `cpla.finance.validation.approval` | Server-written approval, denial, or evidence event. |
| `cpla.finance.validation.wizard` | Transient form for the authorized buttons. |

Public `create`, `write`, and `unlink` on the validation, the line, and the approval event raise. Server methods use `models.Model.create` and `models.Model.write`. The model does not inherit `mail.thread`. It does not schedule `mail.activity`. The case event `finance_decision_recorded` stores the validation reference, not the amount.

## What this phase does not own

Recovery target, commercial waiver, customer dispute, debit note, posted recovery invoice, payment, and reconciliation stay out. `creates_customer_receivable`, `proves_cash_collection`, `is_waiver`, `is_recovery_billed`, and `is_cash_recovered` are stored false and are not writable by a client.
