# Historical FX policy

Company DEC-06 stays open. A company FX candidate is not a conversion rule. Only an explicit clause on the approved contract version can select a rate.

## Clause values

| `fx_policy` | Behavior |
| --- | --- |
| `unconfigured` | Different currencies return `FX_RATE_REVIEW_REQUIRED`. Same currency needs no rate. |
| `fixed_rate` | Uses `fx_multiplier_exact`: target units for one source unit. The pair is `fx_source_currency_id` and `fx_target_currency_id`. A market row is not substituted. |
| `historical_exact_date` | Uses the rate whose date equals the clause date. Another day is `MISSING_HISTORICAL_FX`. |
| `historical_last_known_prior` | Uses the latest row on or before the clause date. The row's own date is recorded. A later future row is ignored. |

## Date source

| `fx_date_source` | Snapshot at approval |
| --- | --- |
| `explicit_date` | Yes, from `fx_explicit_date`. |
| `contract_effective_date` | Yes, from `effective_from`. |
| `pricing_date`, `order_confirmation_date`, `invoice_date` | No. Normalization returns `HISTORICAL_EVIDENCE_REVIEW_REQUIRED` / `document_date_not_snapshotted` and does not read a live rate. |
| `unconfigured` | A historical policy cannot be submitted. Invoice date is not selected automatically. |

A missing rate at approval does not block approval. The snapshot stays empty and normalization returns `MISSING_HISTORICAL_FX`. An incomplete fixed-rate or historical pair is blocked at submit.

## Company scope

Rate rows are read for the version company's root company. A company-specific row is preferred over a shared row on the same date. Another root company's row is not used. No rate is created.

## Cutoff

If `knowledge_cutoff` is before `approved_at`, the clause is not applied. The same approved clause and the same cutoff return the same result. A rate whose `create_date` is after the cutoff is skipped. A rate corrected after the cutoff returns `HISTORICAL_EVIDENCE_REVIEW_REQUIRED` from `select_rate`. Normalization of an already approved snapshot still uses the frozen text.

## Payment FX

`fx_source` `payment_date` or `document_type` `payment` returns `PAYMENT_FX_NOT_CONTRACT_LEAKAGE`. No price is returned. `leakage_amount` stays false.

## Native conversion

`res.currency._convert` and `_get_rates` are not called. In this Odoo 19 Community build, `_get_rates` can select a future row and then the number one when no row exists. `_convert` also defaults the date to today and rounds. Those behaviors do not match the clause.
