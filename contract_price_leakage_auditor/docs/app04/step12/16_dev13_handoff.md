# DEV-13 handoff

DEV-13 is not implemented. This file describes the detector records an investigation case can read. It does not assign a case, set an SLA, or escalate.

## Models

| Role | Model |
| --- | --- |
| Audit run | `cpla.invoice.audit.run` |
| Audit result | `cpla.invoice.audit.result` |
| Potential finding | `cpla.leakage.finding` |

## Canonical finding identity

`c{company}|l{invoice line}|a{allocation or 0}|k{cutoff token}|sUNDERBILLING`

The cutoff token is `none` unless the run stored `knowledge_cutoff`. One current row holds that key. `UNIQUE(current_identity)` enforces it. A repeated audit of the same evidence updates that row. A changed fingerprint supersedes it and inserts a new current row. A different explicit cutoff is a different key.

## Calculation input and output

Inputs: posted invoice line, verified allocation, pricing date, knowledge cutoff, approved version, tier, FX clause, tax basis, approved concession or override, actual effective unit price, and net eligible quantity.

Outputs on the result, when authoritative:

- `approved_pre_concession_exact`
- `approved_adjusted_exact`
- `actual_unit_exact`
- `gross_difference_exact`
- `authorized_concession_exact`
- `raw_difference_exact` (signed)
- `potential_exposure_exact` (positive raw extended, otherwise zero)
- `eligible_quantity_exact`
- `comparison_currency_id`, `comparison_uom_id`
- `result_classification`, `contributing_causes`
- `calculation_trace`, `evidence_snapshot`, `input_fingerprint`, `engine_version` (`dev12.1`)

A blank amount means the figure was not produced. It is not a stored zero price.

## Finding status

`potential`, `review_required`, `superseded_by_reassessment`, `no_longer_current`.

`within_tolerance` is not written. There is no finance-validated, billed, or collected status. `is_recovered_cash` is false.

## Leakage categories

`UNAUTHORIZED_UNDERPRICING`, `MISSED_CONTRACT_PRICE_INCREASE`, `UNAUTHORIZED_DISCOUNT_INDICATOR`, `PRICING_COMPLIANT`, `PRICE_ABOVE_APPROVED_RATE`, `CONTRACT_COVERAGE_EXCEPTION`, `CONTRACT_CONFLICT_REVIEW_REQUIRED`, `MISSING_PRICING_EVIDENCE`, `FX_OR_TAX_REVIEW_REQUIRED`, `SOURCE_ALLOCATION_REVIEW_REQUIRED`, `REFUND_REASSESSMENT_REQUIRED`, `UNSUPPORTED_TRANSACTION`, `TECHNICAL_AUDIT_FAILURE`.

A classification does not imply a monetary amount. Review classes store a blank amount. Only a positive unauthorized difference becomes a `potential` finding. One quantity has one primary category. A second cause is `contributing_causes`, not a second amount.

## Evidence a case can cite

Invoice, invoice line, company, customer, product, sales order, sales line, source map, allocation, contract, approved version, version line, tier, pricing date, knowledge cutoff, FX rate text, tax basis, trace, snapshot, fingerprint, calculation revision, and source revision.

## Refunds and reversals

Verified quantity returns reduce eligible quantity on the original line. Full reversal sets current exposure to zero and keeps the historical finding. Amount-only, tax-only, and unknown credits are `REFUND_REASSESSMENT_REQUIRED` and do not change origin quantity. A credit is not collected cash. A replacement invoice at the approved price leaves current leakage at zero and does not record a payment.

## Reassessment

New run, mode `reassessment`. Previous result rows stay. The current finding moves only through the identity rules above.

## Source exceptions that must not become a case amount

Missing contract, conflicting contracts, missing pricing date, incompatible UoM, missing FX, unsupported tax, ambiguous allocation, unlinked refund, cross-company source. The finding status is `review_required` and the amount is blank.

## Company and reviewer access

Global company rule: `[('company_id', 'in', company_ids)]`. Contract user, finance reviewer, and internal auditor can read. Contract manager and finance manager can create and run audits. They cannot unlink. Sales reviewer, recovery operator, and application administrator have no audit access rows. The Audits menu is not granted to the auditor. The invoice smart button is.

A case workflow must keep that company boundary. It must not mark a finding finance-validated.

## Golden fixtures and tests

GOLD-AUD-001 through GOLD-AUD-020 passed inside the green class, full, upgrade, and fresh logs. Details are in `11_golden_financial_fixtures.md` and `12_automated_test_results.md`.

Deferred and not executed: two-worker concurrency, large-history throughput, Odoo 18, Odoo 20, finance validation, recovery, and cron.

## Open business decisions

Manual-invoice auto pricing, delivery-date allocation, and a numeric tolerance are not approved. They stay review. DEC-08 is still open. Retroactive amendments stay unauthorized.

## What DEV-13 still has to build

An investigation case that references `cpla.leakage.finding` without copying the exposure into a second current amount. Assignment, SLA, and escalation were requested for a later step and are not in this addon. The case must not treat potential leakage as validated leakage or as collected cash.
