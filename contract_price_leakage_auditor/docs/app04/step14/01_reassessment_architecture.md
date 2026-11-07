# DEV-14 reassessment architecture

Date: 2026-11-05. Version: `19.0.1.12.0`. This note is the sections 1–36 description. Sections 37–69 are in `01_evidence_architecture.md` through `17_dev15_handoff.md`. Finance validation is not implemented.

Potential leakage is not finance-validated, billed, or collected. Accepting a reassessment is not finance validation. A delta is an evidence correction. It is not recovered cash and it is not an approved write-off.

## What is preserved

DEV-12 remains the only price engine. `ENGINE_VERSION` stays `dev12.1`. The reassessment model does not recompute `(adjusted - actual) * quantity`. Preview calls `cpla.invoice.audit.run._price_allocation`. Acceptance calls `cpla.invoice.audit.run._audit_mapping` on the documents for that request. It does not call `action_run` or `action_reassess`.

DEV-12 audit results stay append-only. The original result row is not rewritten. A finding identity stays:

`c{company}|l{invoice line}|a{allocation or 0}|k{cutoff token}|sUNDERBILLING`

A blank cutoff token is `none`. A different cutoff is a different identity. The same cutoff with a changed fingerprint supersedes that identity. One `current_identity` is current at a time. A cleared identity can have no current finding. That is described in `03_historical_cutoff_and_returns.md`.

DEV-13 cases stay the investigation record. Acceptance does not move case membership and does not change `reviewed_exposure_exact`.

## Records

| Record | Role |
| --- | --- |
| Posted invoice, credit note, contract version, discount, source map | Source evidence. Odoo business records. DEV-14 does not post, edit, or reconcile them. |
| `cpla.invoice.audit.result` | Calculation evidence. Append-only. This is the stored calculation snapshot. |
| `cpla.leakage.finding` with `is_current` false and status `superseded_by_reassessment` | Historical finding row. The amount text stays. |
| `cpla.leakage.finding` with `is_current` true | Current accepted interpretation for that identity, when the engine still persists a potential finding. |
| `cpla.leakage.reassessment` | Proposed or decided reread. It does not replace the current finding until a finance manager accepts it. |
| `cpla.leakage.reassessment.event` | Append-only decision log. Public create, write, and unlink raise `UserError`. |
| `cpla.leakage.reassessment.wizard` | Transient reason form. It is not evidence. |

No model uses the prefixes `cpla.audit.`, `cpla.recovery.`, or `cpla.waiver.`.

## Proposal snapshot

Schema `dev14.1` is stored on `schema_version`. The engine copy is `engine_version` = `dev12.1`.

The first official evaluation writes `original_proposal_payload` and `original_proposal_digest` once. Later evaluations update `proposal_payload` and `proposal_digest` only. `action_verify_digest` rebuilds the payload from the stored fields, compares SHA-256, and sets `digest_mismatch` and `verification_outcome`. It does not replace either digest.

Canonical JSON uses `sort_keys`, separators `(',', ':')`, and `ensure_ascii`. Missing values are JSON null. Zero stays the text `0`. The payload records company, finding, trigger, source, original and proposed identity and fingerprint, cutoff token, version, pricing date, adjusted price, actual price, eligible quantity, exposure, currency, delta, delta class, credit class, whether the calculation was authoritative, and the two false flags `is_recovered_cash` and `is_writeoff`. State is not inside the digest.

A digest in this database detects an unexpected change to the stored proposal. It does not prove the business documents were accurate. It is not an external archive and it is not a legal certification. No external hash service was added.

## Current pointer

Acceptance runs inside one savepoint:

1. Create a limited audit run in mode `reassessment`. The date window is the invoice date plus or minus 30 days. That window selects documents for the engine. It is not a pricing date and it is not an SLA.
2. Set the run to `running` with `models.Model.write`.
3. Audit only the mapped documents for the trigger.
4. Require the stored successor to match the proposal fingerprint and amount.
5. Mark the reassessment `accepted` in that same savepoint.
6. Synchronize the case flag.

If the check fails, the savepoint rolls the engine writes back and the reassessment is set to `blocked` after the savepoint, so the blocked state remains.

For the same identity, the engine supersedes the previous current finding and inserts the new one. For a zero outcome, the engine does not leave a current finding. Acceptance then requires an audit-result row on that run whose fingerprint matches and whose potential exposure text is `0`.

A different cutoff is not subtracted from the other cutoff and does not replace it.

## What a runner reread still does

The audit-run form still has `action_reassess`, labeled as a changed-source reread. That button opens a run and calls `action_run`. It can move the current finding before a DEV-14 decision. DEV-14 does not remove that button. `test_rev14_t011` asserts it is still on the run form. Use the reassessment request when the decision must be separate from the calculation.

## Not in this phase

No finance-validated amount. No recovery invoice, debit note, waiver, payment, or reconciliation. No recurring cron. No executive dashboard. No Odoo 18 or Odoo 20 conversion. No numerical confidence score. No monetary approval threshold. The only evaluation policy is `as_known_at_cutoff`.
