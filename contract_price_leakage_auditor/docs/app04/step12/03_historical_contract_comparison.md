# Historical contract comparison

The audit does not use only the current contract version.

## Invoice-date policy

When the confirmed version snapshot says `invoice`, the engine calls `cpla.pricing.applicability.resolve` with the invoice date, the run's knowledge cutoff, the order quantity for tier qualification, and the original billed quantity. The invoice price is not passed in. Forged version, contract, and price keys are popped by the resolver.

A cutoff that excludes a later version does not use the source map's stored approved price.

## Order-date lock

When the snapshot says `order_confirmation` and the allocation is an order-date lock candidate, the engine prices the locked version line at `lock_pricing_date` or `applicable_pricing_date`. It does not resolve a later version. A missing date returns `MISSING_PRICING_EVIDENCE`. Today is not substituted.

`GOLD-AUD-005` confirms an order on 25 June 2026 and invoices on 15 July 2026. The locked price stays in force. The July increase is not leakage.

## Other date rules

`delivery`, `unconfigured`, `contract_specific`, and `custom_rule` are not operational invoice prices. The result is `MISSING_PRICING_EVIDENCE` and the amount is blank.

## Version selection

The resolver ignores draft and rejected versions. It respects effective dates, the contract validity window, product variant, customer coverage, company, supersession, and `knowledge_cutoff` through `_known_at`. Retroactivity on an amendment is `not_authorized`. A version whose effective date is before its approval day is excluded. An initial version has no source version and is not treated as retroactive.

Two equally applicable contracts return `CONTRACT_CONFLICT_REVIEW_REQUIRED`. No price is chosen. A missing contract returns `CONTRACT_COVERAGE_EXCEPTION`. No monetary leakage is invented.

A missing sales-order lock is a coverage or missing-evidence outcome. The engine does not call the resolver to invent coverage for a manual invoice or for a sale line with no lock.

## Quantity, FX, tax, and discounts

Quantity tiers and UoM conversion come from `cpla.pricing.quantity`. The order quantity can qualify a tier. The eligible billed quantity extends the difference. They are stored separately.

FX uses the approved clause on the version (`fx_multiplier_exact` and the declared pair). A missing clause is `FX_OR_TAX_REVIEW_REQUIRED`.

Tax-excluded contract prices are compared with a net invoice price. A single included percent tax is stripped as `gross × 100 / (100 + percent)` when that division is exact for the fixture. Mixed or unknown tax is review, with no amount.

Approved concessions and transaction overrides come from `cpla.discount.evaluator`. The authorized adjusted price is the comparison price. The concession is not leakage.
