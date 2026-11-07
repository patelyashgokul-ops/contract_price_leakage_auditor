# Financial normalization architecture

DEV-08 adds a read-only financial normalizer on top of the DEV-06 resolver and the DEV-07 quantity normalizer. It does not create leakage findings, discounts, invoices, tax entries, or recovery records.

## Service

Technical name: `cpla.pricing.financial` (`models/financial_normalization.py`).

It is an abstract model. It has no table and no access-control row. Callers must belong to contract user, contract manager, finance reviewer, finance manager, or internal auditor.

Public methods:

| Method | Role |
| --- | --- |
| `normalize(line, request)` | Comparable pre-discount unit price, or a review status. |
| `select_rate(company, currency, on_date, mode, cutoff)` | Company-scoped historical rate lookup. It does not create a rate. |
| `lookup_company_per_unit(...)` | Company-currency units for one unit of a currency. |
| `classify_fx_source(source)` | Payment-date FX is not contract price leakage. |
| `classify_difference(expected, actual, quantity, tolerance_amount)` | Signed difference. Nothing is suppressed. |

`normalize` re-reads the version line with the caller's rights. It drops caller-supplied prices, rates, tax percents, tolerances, currencies, and policy names before it reads the approved version.

## Order

1. DEV-06 selects one approved version, or a review outcome. A financial review does not replace that status.
2. DEV-07 selects the full-volume tier and the normalized source unit price. A quantity failure stops before FX.
3. DEV-08 removes a supported included tax in the source currency, converts that net with the approved clause, then applies the approved rounding stage.
4. DEV-09 will apply authorized discounts to `comparable_unit_price_exact`. This phase always sets `discount_applied` false.
5. DEV-12 will create leakage findings. This phase always sets `leakage_amount` false.

## Clause storage

The clause lives on `cpla.customer.contract.version`. Defaults are `unconfigured`. Company policy fields `fx_basis_policy`, `tax_comparison_policy`, `monetary_precision_policy`, and `tolerance_policy` stay candidates. `propose_fixed_rate` and `propose_tolerance` still raise. An approved version with no clause returns `INVALID_CURRENCY_CONTEXT` or `TAX_BASIS_REVIEW_REQUIRED` and no price.

Historical rate numbers are written once at approval through the base model write, so the version's own write guard cannot accept a client-supplied rate. Later edits of `res.currency.rate` do not change the frozen text. If the live row differs, `fx_reassessment_required` is true and the frozen number is still used. DEV-14 owns reassessment cases.

## Output

Successful currency statuses are `NORMALIZED` and `SAME_CURRENCY_NO_CONVERSION`.

Review statuses include `FX_RATE_REVIEW_REQUIRED`, `MISSING_HISTORICAL_FX`, `TAX_BASIS_REVIEW_REQUIRED`, `UNSUPPORTED_TAX_STRUCTURE`, `PRECISION_POLICY_REVIEW_REQUIRED`, `INVALID_CURRENCY_CONTEXT`, `COMPANY_ACCESS_DENIED`, `HISTORICAL_EVIDENCE_REVIEW_REQUIRED`, and `PAYMENT_FX_NOT_CONTRACT_LEAKAGE`.

A review result does not use zero as a price. `comparable_unit_price_exact` stays false.

The resolver keeps `status` as `MATCHED_AUTHORITATIVE` when the version is selected and the quantity result is authoritative. Financial keys are added beside it. `unit_price` remains the DEV-07 price.

## What is not in this phase

Invoice currency as a comparison target, fiscal-position mapping, `account.tax` computation, document-date FX snapshots, numeric tolerance classification, authorized discounts, leakage cases, and Odoo 18 or 20 conversion.
