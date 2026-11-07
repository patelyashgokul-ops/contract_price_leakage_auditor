# 04 — Currency, tax, and precision

Date: 2026-10-28.

This phase stores policy candidates and runs non-destructive checks. It does not create `res.currency.rate` rows, activate currencies, calculate tax, or post entries. Payment-date exchange differences are not contract price leakage.

## Currency and FX

`company_currency_id` follows `res.company.currency_id`.

`validate_currency(currency)`:

| Condition | Classification | Code | `fx_basis` |
| --- | --- | --- | --- |
| No currency | `BLOCKING_CONFIGURATION_ERROR` | `CURRENCY_MISSING` | `MISSING` |
| Inactive currency | `BLOCKING_CONFIGURATION_ERROR` | `CURRENCY_INACTIVE` | `MISSING` |
| Active currency, FX policy `unconfigured` or hidden | `VALID` for existence only | `CURRENCY_REFERENCE_OK` | `MISSING` |
| Active currency, FX candidate selected | `VALID` for existence only | `CURRENCY_REFERENCE_OK` | `DRAFT_NOT_APPROVED` |

`activated` and `rates_created` are false. Existence `VALID` does not mean the FX policy is approved.

`fx_basis_policy` candidates are `pricing_date`, `order_date`, `invoice_date`, `fixed_rate`, and `historical_rate`. None is a hardcoded audit basis. `propose_fixed_rate` raises `UserError` because DEC-06 is open. No numeric rate field exists.

`classify_exchange_difference('payment_date')` returns `REVIEW_REQUIRED`, code `PAYMENT_FX_NOT_CONTRACT_LEAKAGE`, `pricing_leakage: false`. Other known source names return `FX_POLICY_NOT_APPROVED`. An unknown source returns `FX_SOURCE_UNKNOWN`. This is a policy fixture, not an invoice audit. CFG-T020 covers the payment-date case.

## Tax comparison

`classify_tax_bases(left, right)` never sets `comparable` true.

| Input | Code |
| --- | --- |
| Either side outside `tax_excluded` and `tax_included` | `TAX_BASIS_UNKNOWN` |
| One inclusive and one exclusive | `TAX_INCLUSIVE_EXCLUSIVE_NOT_COMPARABLE` |
| Both the same known label | `TAX_TREATMENT_UNVERIFIED` |

Product taxes and fiscal positions are not inferred. The module is not a tax-law engine. Selecting `tax_excluded` and submitting the form still leaves `operationally_approved` false (CFG-T033). There is no dependency on `account`.

## Precision and tolerance

`monetary_precision_policy = company_currency_rounding` tells `assess_monetary_difference` to call `currency.round`. The method always returns `suppressed: false`, `operationally_approved: false`, and `audited: false`.

Company currency rounding of 25000 stays 25000 at the standard 0.01 rounding. That is the GOLD-FIN-001 scale used in CFG-T029. The method does not audit the invoice.

`propose_tolerance(None)` returns `unconfigured`. A negative number raises `ValidationError`. Any other number raises `UserError` because DEC-08 is open. Nothing is stored. An undefined tolerance cannot suppress a difference because there is no threshold to apply.

Per-line versus document rounding is not configured. Display rounding is not separated from calculation precision beyond Odoo's own currency rounding.
