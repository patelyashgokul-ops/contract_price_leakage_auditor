# 01 — Applicability architecture

Date: 2026-10-28. Addon `contract_price_leakage_auditor` `19.0.1.4.0`.

The resolver is `cpla.pricing.applicability`, an abstract model. The diagnostic screen is the transient model `cpla.pricing.applicability.check`. Neither name starts with `cpla.contract`, `cpla.leakage`, `cpla.recovery`, or `cpla.audit`.

`resolve(request)` is read-only. It does not approve versions, write invoices, or cache a match. `cache_key(request)` returns a tuple and is not used as a store.

## Boundaries

1. Validate the caller, company, customer, and product.
2. Choose a pricing date from the request.
3. Search approved version lines for that company, customer, product, and date.
4. Apply the knowledge cutoff and reject unauthorized retroactive amendments.
5. Keep one version per contract by the latest started `effective_from`.
6. If more than one contract remains, return a conflict and no price.
7. Return the stored line price, currency, and unit only for a single match.

A stored policy candidate is not an operational rule. `policy_operationally_approved` is always false. `leakage_amount` is always false.

## Request fields that are used

Company, customer, product variant, explicit pricing date, requested basis (`order_confirmation`, `delivery`, or `invoice`), confirmation flag and date, quotation date (never used as the pricing date), invoice date, delivery dates, knowledge cutoff, customer-group reference, template-fallback flag, quantity, and optional unit of measure.

`version_id`, `contract_id`, and `unit_price` on the request are discarded.

## Result fields

`status`, `reason_code`, `explanation`, company, partner, product, contract, version, version line, `unit_price`, currency, unit of measure, `customer_scope`, `product_specificity`, pricing date, pricing-date rule, basis source, policy pointer and snapshot text, effective interval, knowledge cutoff, grandfathering flag, precedence rule, `tier_status`, evidence ids, conflicting version ids, resolution purpose, `is_recovered_cash`, and `leakage_amount`.

Statuses: `MATCHED_AUTHORITATIVE`, `NO_APPLICABLE_CONTRACT`, `CONFLICT_REVIEW_REQUIRED`, `MISSING_CONTEXT`, `POLICY_REVIEW_REQUIRED`, `HISTORICAL_EVIDENCE_REVIEW_REQUIRED`, `PARTITION_REVIEW_REQUIRED`.
