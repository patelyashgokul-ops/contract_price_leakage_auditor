# Historical price context

The mapper reads `cpla.sale.price.lock` for the linked sales lines. It does not overwrite the lock. It does not call the resolver for an order-confirmation snapshot.

| Snapshot on the lock | Behavior |
| --- | --- |
| `order_confirmation` | Applicable version, date, and approved unit come from the lock. `order_date_lock_candidate` stays true only when the lock itself says so. A later approved amendment does not replace that version. |
| `invoice` | The resolver is called with the invoice date, the order quantity from the lock, and no invoice price. The lock version stays `confirmed_version_id`. The applicable version is the resolver result only when status is `MATCHED_AUTHORITATIVE`. The order-date lock flag stays false. A missing invoice date is `PRICING_DATE_MISSING`. Today is not substituted. |
| `delivery` | `DELIVERY_DATE_NOT_ALLOCATED`. No first or latest delivery is chosen. `stock` is not a dependency. The lock date may be stored as `lock_pricing_date` and is not presented as the delivery date. |
| `unconfigured`, `contract_specific`, `custom_rule` | `PRICING_DATE_POLICY_NOT_OPERATIONAL`. No date is invented. |

A missing lock is `HISTORICAL_CONTRACT_MISSING` and `CONTRACT_CONTEXT_REVIEW_REQUIRED`. The native sales link can still be recorded as provenance, and no allocation version is invented.

Invoice price evidence is separate from the confirmed price:

- `price_unit_exact` and `discount_exact` come from the posted invoice line.
- `effective_unit_exact` is `price_unit × (1 - discount / 100)` through the DEV-10 helper. The discount is not removed twice.
- `confirmed_unit_price_exact` is the lock's actual unit.
- `approved_unit_price_exact` is the historical approved unit for the pricing-date rule above.
- Currency, company currency, `invoice_currency_rate` when present, tax ids, fiscal position, untaxed subtotal, and total are stored as evidence.
- Tax basis uses the DEV-10 helper. Empty taxes or an all-excluded basis stay `tax_excluded`. Included, mixed, or unknown taxes add `TAX_INCLUDED_REVIEW` and are not recalculated.
- A currency different from the company currency without `invoice_currency_rate` adds `MISSING_FX_EVIDENCE`. Accounting rates are not converted with `res.currency._convert`.
- The product list price is not read as the source price.

Invoice date and posting date are both stored. The posting date is not the contractual pricing date unless the approved snapshot says so.

An invoice price that differs from the confirmed order price is preserved. No leakage finding is created.
