# Multi-currency and exchange differences

Recovery currency, company currency, and billing currency are stored separately. A policy whose currency is not the company currency requires the caller to supply `fx_rate_exact`, the rate date, and a note. Missing that basis raises `CURRENCY_BASIS_REVIEW_REQUIRED`. Amounts in different currencies are not added. `reconciliation_report` sets `mixed_currency` when the rows do not share one currency and always returns `totals` false.

## Realized FX

A partial whose counterpart move is `partial.exchange_move_id` is `fx_difference`. Its principal is 0. The company-currency `amount` is kept as `fx_company_amount`. A payment partial that also has an exchange move is still cash or unconfirmed payment. The exchange difference is not added to recovered principal. The position adds `FX_DIFFERENCE_REVIEW_REQUIRED`. This addon does not create `res.currency` or a second FX journal entry.

## Not executed

GOLD-ACC17-014 describes a USD 100 billing, an invoice-date company equivalent of 8400, and a payment-date equivalent of 8500. No inactive currency with a stored rate was used, and this phase does not create `res.currency`. That scenario is `NOT_EXECUTED`. The selection key `fx_difference` is present. A passing assertion that the currency count is unchanged is not a USD collection result.

The original recovery authorization is not rewritten when a later payment-date rate differs.
