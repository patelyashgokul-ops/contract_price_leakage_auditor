# Case management architecture

Version `19.0.1.11.0`. Addon `contract_price_leakage_auditor`. Odoo 19 Community. Direct depends remain `base`, `product`, and `sale`. `mail.thread` and `mail.activity.mixin` come through `product`. `mail` and `account` are not direct dependencies.

An investigation case organizes DEV-12 findings. It does not calculate a second leakage amount, validate a finance figure, bill a recovery, or collect cash.

## Models

| Model | Role |
| --- | --- |
| `cpla.leakage.case` | Investigation container. One company, one customer, one case type. |
| `cpla.leakage.case.membership` | Link from a case to a `cpla.leakage.finding`. `is_current` is the live membership. |
| `cpla.leakage.case.event` | Append-only event row. Chatter is not the financial history. |
| `cpla.leakage.case.checklist` | Investigation questions. Required lines depend on case type. |
| `cpla.leakage.case.evidence` | Source link or investigator evidence, with a review status. |
| `cpla.leakage.case.submission` | Immutable finance-review package. A return fills return fields and does not delete the row. |
| `cpla.leakage.case.wizard` | Transient helper for assign, priority, merge, split, and related actions. |

`cpla.leakage.finding` is unchanged as the detector record. `LeakageFindingCase` only adds `current_case_id` and the open/view actions.

## Source of truth

| Fact | Owner |
| --- | --- |
| Potential leakage amount | Current `cpla.leakage.finding.potential_leakage_exact` |
| Economic identity | Finding `current_identity` |
| Audit calculation | `cpla.invoice.audit.result` and the finding snapshot |
| Current investigation owner of that finding | One membership with `is_current` true |
| Case exposure display | Copy of the comparable sum, stored by `_sync_exposure` |
| Reviewed exposure | Last accepted case snapshot in `reviewed_exposure_exact` |
| Finance-validated amount | Not stored. Not this phase. |
| Recovered cash | Not stored. Finding `is_recovered_cash` stays false. |

`create_from_findings` is the only way to open a case. `cpla.leakage.case.create` raises. Public `write` cannot set state, owner, exposure, root cause, or closure.

## Boundaries

DEV-13 does not reprice invoices, post entries, create debit notes, register payments, email customers, or run a cron. There is no `ir.cron`, `ir.actions.server`, or `ir.actions.report` owned by this module for cases.

DEV-14 owns a full historical reassessment engine. This step only flags `source_reassessment_required` and lets an investigator accept a successor finding.

DEV-15 owns finance validation. Submission sets `ready_for_finance_review` and stores a snapshot. It does not set a validated amount.

DEV-16 owns recovery. Closure reasons do not mean cash was collected.

DEV-18 owns scheduled reminders. `target_review_date` is optional and has no default. `escalation_policy_reference` is a label only.
