# Invoice audit architecture

DEV-12 adds a read-only historical audit of posted customer invoices. It calculates potential contract-price leakage. It does not validate a finance amount, bill a recovery, collect cash, or schedule a recurring job.

Addon: `contract_price_leakage_auditor`, version `19.0.1.10.0`. Odoo 19 Community. Engine version string: `dev12.1`.

## Models

| Model | Role |
| --- | --- |
| `cpla.invoice.audit.run` | One authorized read of posted customer documents for one company and one date window. The engine methods live here. |
| `cpla.invoice.audit.result` | Append-only evaluation of one invoice line or one verified source allocation. |
| `cpla.leakage.finding` | One current detector finding for one economic underbilling identity. |

There is no abstract `cpla.invoice.audit` model. Public `create` on a result or a finding is refused after the access check. The engine inserts rows with `models.Model.create`.

## Pipeline

1. `action_run` checks the runner group and the company, then moves the run to `running`.
2. `_select_moves` reads posted `out_invoice` and `out_refund` rows for that company and date window. Customer invoices are processed before credit notes. There is no user-supplied domain.
3. Each move is mapped with `cpla.invoice.source.map_move` inside a savepoint. A failure rolls back that move only and increments `failure_count`.
4. Commercial lines with a trusted allocation are priced. Excluded lines and ineligible documents are counted as excluded. Review outcomes store no invented amount.
5. A priced underbilling row is upserted on `cpla.leakage.finding`. An exact match or an overbilling row does not create a current potential finding. A prior current finding for that identity is superseded when the new reading is no longer a positive exposure.
6. The run stores counts and the sum of current `potential` findings that belong to this run. Mixed currencies leave the exposure blank.

## Services reused

The engine does not reimplement these services:

- `cpla.invoice.source` for eligibility, source allocation, and credit classification.
- `cpla.pricing.applicability.resolve` for invoice-date contract selection.
- `cpla.pricing.quantity.evaluate` and `convert_price` / `convert_quantity` for tiers and units.
- `cpla.pricing.financial.normalize` and `_convert_clause` for an approved FX clause. `res.currency._convert` is not called.
- `cpla.discount.evaluator.evaluate` for approved concessions and transaction overrides.

The order-date path does not call the resolver again. It prices the confirmed lock version at `lock_pricing_date` or `applicable_pricing_date`. A missing lock date is `MISSING_PRICING_EVIDENCE`.

## Explicit non-goals

Manual invoices stay `SOURCE_ALLOCATION_REVIEW_REQUIRED`. Delivery-date pricing stays `MISSING_PRICING_EVIDENCE`. The company policy stores no numeric tolerance, so `WITHIN_APPROVED_TOLERANCE` is never written. No `ir.cron` is registered. No posted `account.move` is written. No `account.payment` is created.
