# Audit run and result models

Money fields are `Char` exact text from the financial normalizer. `False` means the amount was not produced. A review result does not store zero as a fabricated price.

## `cpla.invoice.audit.run`

| Field | Meaning |
| --- | --- |
| `reference` | Sequence `cpla.invoice.audit.run`, prefix `AUD/%(year)s/`, padding 5. |
| `company_id` | Required. Set on create. `write` does not allow a later company change. |
| `mode` | `on_demand`, `historical_review`, `reassessment`, `controlled_batch`. |
| `state` | `draft`, `queued`, `running`, `completed`, `completed_with_exceptions`, `failed`, `cancelled`. |
| `date_basis` | `invoice_date` or `posting_date`. This selects documents. It is not the contractual pricing date. |
| `date_from`, `date_to` | Required. An open-ended scan is refused. |
| `partner_id`, `product_id`, `contract_id` | Optional filters, always combined with the company. |
| `knowledge_cutoff` | Optional. Empty means the current approved history and the identity token `none`. A timestamp excludes versions approved after it. The engine does not stamp the clock on every repeat. |
| `batch_size` | Default 50. The engine caps a run at 200 moves. |
| `initiated_by_id`, `started_on`, `finished_on` | Who started the run and when. |
| `selected_count`, `processed_count`, `completed_count`, `review_count`, `finding_count`, `excluded_count`, `failure_count` | Progress. `finding_count` is a search of current `potential` findings for this run at the end. |
| `potential_exposure_exact` | Sum of those current potential amounts when they share one currency. |
| `error_summary` | A short failure note. Unit prices are not written here. |

`action_run` is allowed from `draft` or `queued`. `action_cancel` is allowed from `draft` or `queued`. `action_queue` moves a draft to `queued`. `action_reassess` creates a new run in mode `reassessment` and runs it. The previous run is not rewritten.

Any technical failure, or any review result, finishes as `completed_with_exceptions`. Failures with no successful calculation finish as `failed`. An empty selection finishes as `completed`.

## `cpla.invoice.audit.result`

One row per evaluated line or allocation. Later runs append. `write` and `unlink` are refused after the access check, except during module uninstall.

Stored links: run, company, invoice, invoice line, source map, allocation, customer, product, sales order, sales line, contract, contract version, version line, tier, and finding.

Stored amounts, when the calculation is authoritative: actual quantity, eligible quantity, qualified quantity, comparison UoM, comparison currency, pre-concession unit price, approved adjusted unit price, actual comparable unit price, gross difference, authorized concession, signed raw difference, and potential exposure.

Also stored: pricing date, invoice date, posting date, knowledge cutoff, classification, contributing causes, review reason, calculation trace, evidence snapshot, calculation revision, input fingerprint, source revision, credit treatment, and `engine_version`. `is_recovered_cash` stays false.

## `cpla.leakage.finding`

See `08_finding_uniqueness_idempotency.md` for the identity. Status values are `potential`, `review_required`, `superseded_by_reassessment`, and `no_longer_current`. `within_tolerance` exists on the selection and is never written. There is no finance-validated status.

Public reference sequence: `cpla.leakage.finding`, prefix `LKF/%(year)s/`, padding 5. The reference does not contain a price.
