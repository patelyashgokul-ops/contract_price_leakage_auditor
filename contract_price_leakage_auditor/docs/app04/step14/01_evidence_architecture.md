# Evidence architecture

Date: 2026-11-05. Addon `contract_price_leakage_auditor` version `19.0.1.12.0`. Odoo 19 Community. Direct depends remain `base`, `product`, and `sale`.

This file covers the evidence records used by DEV-14. The earlier note `01_reassessment_architecture.md` described sections 1–36. It is still in this directory. Where the two differ, this file is the later description. Schema version is `dev14.2`. Engine version stays `dev12.1`.

Potential leakage is not finance-validated leakage, billed recovery, or collected cash. Accepting a reassessment is not finance validation.

## Source of truth

| Record | Owns |
| --- | --- |
| Posted `account.move` and its product lines | Invoice and credit-note facts. DEV-14 reads them. It does not post, edit, or reconcile them. |
| `cpla.customer.contract.version` | Approved contract terms, effective date, and approval time. Current mutable contract rows are not historical fact. |
| `cpla.discount.approval` | An approved discount, including `approved_at`. |
| `cpla.invoice.source.map` | Current link from an invoice or credit line back to its source line, with credit class and quantity trust. |
| `cpla.invoice.audit.result` | One stored calculation. Rows are appended. The original result is not rewritten when a later revision is accepted. |
| `cpla.leakage.finding` | One row per stored interpretation. `is_current` and `current_identity` say which row is the current reading for that identity. |
| `cpla.leakage.reassessment` | The request, the copied original figures, the proposal, and the decision. It does not replace the finding until acceptance. |
| `cpla.leakage.reassessment.event` | Append-only event row. Ordinary create, write, and unlink raise. |
| `cpla.leakage.case` | DEV-13 investigation. DEV-14 flags source changes. It does not replace the investigator's root cause. |

There is no second price engine. Preview calls `cpla.invoice.audit.run._price_allocation`. Acceptance calls `_audit_mapping` for the documents on that request. Acceptance does not call `action_run` or the run-form `action_reassess`.

## Identity

A current economic reading is:

`c{company}|l{invoice line}|a{allocation or 0}|k{cutoff token}|sUNDERBILLING`

A blank cutoff token is `none`. A different cutoff is a different identity and is not added to the current exposure of the blank-cutoff finding. PostgreSQL `UNIQUE(current_identity)` allows many nulls, so a superseded row clears `current_identity`. One non-null identity has one current row.

A zero outcome does not keep a current potential finding. The zero is stored on the audit result. The previous finding is marked `superseded_by_reassessment`.

## What a request copies

`request_for_finding` copies the finding's exposure, quantity, adjusted price, actual price, contract version, fingerprint, and identity onto the reassessment. Those original fields stay on the request after a later acceptance. The original audit result row stays readable.

## Navigation

Reassessments stay under the existing Investigation menu: `menu_cpla_reassessments` parent `menu_cpla_investigation`. No second Audit Evidence root was added. Findings stay on their existing menu. The finding form shows `revision_verification`. The case form shows `reinvestigation_required` next to `finance_package_stale`.
