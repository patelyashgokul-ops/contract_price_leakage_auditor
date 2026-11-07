# Quotation pricing comparison

The commercial pre-tax unit on a standard Odoo 19 line is:

```text
price_unit × (1 - discount / 100)
```

`discount` is the native percent on `sale.order.line`. A reduction already stored in `price_unit` is not subtracted a second time. A percent outside -100 to 100 is not compared.

Empty taxes, or taxes whose `price_include_override` is only `tax_excluded`, use the tax-excluded basis. A tax-included tax or a mix returns `REVIEW_REQUIRED` with reason `quotation_tax_not_compared`. No exposure is stored for that line.

The quotation currency must equal the version comparison currency. A mismatch returns `REVIEW_REQUIRED` with reason `quotation_currency_not_comparison_currency` and clears the compared amounts. No raw foreign amount is treated as the contract currency.

## What is reused

The request sent to `cpla.pricing.applicability.resolve` contains company, customer, product, pricing date, quantity, order quantity, both UoM ids from the sales line, and the sales order and line references. It does not send a forged version, contract, or unit price. The resolver still drops those keys.

Quantity and UoM stay in DEV-07. Currency, tax basis, and rounding stay in DEV-08. Special prices and overrides stay in DEV-09. A matching Odoo pricelist is not a contract price.

On confirmation the pricing date is `context_today`. On a draft it is the calendar date of `date_order`, or today when that date is empty. Invoice quantity and delivery quantity are not invented. An invoice-basis tier stays review at quotation time.

## Exposure

When the approved adjusted unit is above the effective quotation unit:

```text
preventive exposure = (approved adjusted unit - effective unit) × quantity
```

If the discount evaluator already returned `potential_unauthorized_extended_exact`, that text is kept. The amount is quote-stage exposure. `leakage_amount` and `is_recovered_cash` stay false.

A higher quotation price is `PRICE_ABOVE_APPROVED_RATE`. Its difference is not stored as exposure and is not subtracted from another line.

Worked case used by the tests: base 1,200, approved special 1,150, quotation 1,100, quantity 500. Authorized concession 25,000. Additional exposure 25,000. The check does not ask for approval of 50,000.
