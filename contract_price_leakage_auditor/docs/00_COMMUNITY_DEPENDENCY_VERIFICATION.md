# Odoo Community dependency verification

Superseded for acceptance by `docs/app04/step00/02_environment_community_dependencies.md`. This file is the preserved first pass.

Method: parsed each `__manifest__.py` with Python `ast.literal_eval` and read the cited model fields. No module was installed. Presence in the local tree is not a runtime test.

Master target: Odoo 19.0 Community, LGPL-3, version info `(19, 0, 0, final, 0, '')`.
Future targets were checked separately. A module present in one series is not assumed present in another. In this inspection, the compared modules were present in all three series except the Enterprise names, which were absent in all three.

## Enterprise modules that must not be required

| Technical name | Odoo 18 | Odoo 19 | Odoo 20 |
| --- | --- | --- | --- |
| `account_accountant` | Absent | Absent | Absent |
| `accountant` | Absent | Absent | Absent |
| `sale_subscription` | Absent | Absent | Absent |

`l10n_generic_coa` is also absent from all three community trees. A future demo or test must not require that localization module.

## Community modules inspected

License on every present manifest below is `LGPL-3`.

| Module | 18 version | 18 depends | 19 version | 19 depends | 20 version | 20 depends |
| --- | --- | --- | --- | --- | --- | --- |
| `account` | 1.3 | base_setup, onboarding, product, analytic, portal, digest | 1.4 | same as 18 | 1.5 | same as 18 |
| `sale` | 1.2 | sales_team, account_payment, utm | 1.2 | same | 1.2 | same |
| `sale_management` | 1.0 | sale, digest | 1.0 | same | manifest has no version | sale, digest |
| `product` | 1.2 | base, mail, uom | 1.2 | same | 1.2 | same |
| `uom` | 1.0 | base | 1.0 | base | manifest has no version | base |
| `mail` | 1.18 | base, base_setup, bus, web_tour, html_editor | 1.19 | same | 1.19 | same |
| `analytic` | 1.2 | base, mail, uom | 1.2 | same | 1.2 | same |
| `contacts` | none declared | base, mail | none declared | base, mail | none declared | base_address_extended, mail, web_hierarchy |
| `account_payment` | 2.0 | account, payment | 2.0 | same | 2.0 | same |
| `purchase` | 1.2 | account | 1.2 | account | 1.2 | account |
| `loyalty` | 1.0 | product, portal, account | 1.0 | same | none declared | same |
| `sale_loyalty` | 1.0 | sale, loyalty | 1.0 | same | none declared | same |

`contacts` is the dependency that changes in Odoo 20. A hard dependency on the Contacts application would pull `web_hierarchy` and `base_address_extended` on Odoo 20 only.

## What Community already provides for a future audit

These Odoo 19 facts were read from source. The same field names were confirmed on Odoo 18 and Odoo 20 unless a difference is stated.

### Customer invoices

`account.move` in `addons/account/models/account_move.py`:

| Field | Odoo 19 fact |
| --- | --- |
| `state` | `draft`, `posted`, `cancel` |
| `move_type` | `entry`, `out_invoice`, `out_refund`, `in_invoice`, `in_refund`, `out_receipt`, `in_receipt` |
| `payment_state` | `not_paid`, `in_payment`, `paid`, `partial`, `reversed`, `blocked`, `invoicing_legacy` |
| Amounts | `amount_untaxed`, `amount_tax`, `amount_total`, `amount_residual` are Monetary |
| Other | `invoice_date`, `currency_id`, `company_id`, `partner_id`, `commercial_partner_id`, `invoice_line_ids`, `fiscal_position_id`, `invoice_currency_rate` |

Odoo 18 and Odoo 20 use the same `state` values, `move_type` values, and `payment_state` values. Odoo 20 also defines `REVIEW_STATE_SELECTION` (`todo`, `reviewed`, `supervised`, `anomaly`) on the accounting move. That review state is an Odoo 20 accounting feature. It is not an APP 04 audit result.

`account.move.line` stores `price_unit` (float, display digits `Product Price`), `discount` (digits `Discount`), `quantity` (digits `Product Unit`), `product_id`, `product_uom_id`, `price_subtotal`, `price_total`, `tax_ids`, `display_type`, `currency_id`, `company_id`. The legacy name `product_uom` is absent on the line in all three series.

Company rules `account_move_comp_rule` and `account_move_line_comp_rule` restrict rows with `[('company_id', 'in', company_ids)]`.

Posted payment evidence exists in Community `account` as `account.partial.reconcile`, with `debit_move_id`, `credit_move_id`, `amount`, and `company_id`. Reading it does not require Enterprise accounting.

### Pricelists are not contracts

`product.pricelist` has optional `company_id`, required `currency_id`, and `item_ids`. `product.pricelist.item` can target a category, template, or variant, with `min_quantity`, `date_start`, `date_end`, and `compute_price` of `fixed`, `percentage`, or `formula`.

`res.partner.property_product_pricelist` is the partner's current pricelist. It is company-aware. It is not an approved historical contract version.

`sale.order.pricelist_id` exists in Community Sales. Sales is not required to read a posted invoice. Whether sale orders are evidence is OD-09.

There is no Community model in the inspected manifests for an approved customer-contract amendment chain. `sale_subscription` is absent. APP 04 cannot treat a pricelist item as an approved contract version.

### Tax, currency, and precision

`account.tax.price_include` is a computed boolean in Odoo 18, 19, and 20. `price_include_override` is a selection: `tax_included` or `tax_excluded`. Company default is `res.company.account_price_include`. Tax `amount_type` includes `group`, `fixed`, `percent`, and `division`.

`res.currency` has `rounding`, `decimal_places`, `rate`, and `inverse_rate`. `res.currency.rate` is dated, company-scoped, and defaults `company_id` from the company root. A rate row is not global evidence for every company.

Data defaults, which a database administrator can change:

| Precision name | Shipped digits | Source |
| --- | --- | --- |
| Product Price | 2 | `addons/product/data/product_data.xml` |
| Discount | 2 | same file |
| Product Unit | 2 | `addons/uom/data/uom_data.xml` |

Money comparisons use currency rounding. Quantity comparisons use Product Unit precision. Those are different precisions.

### Unit of measure, the compatibility break

| Fact | Odoo 18 | Odoo 19 | Odoo 20 |
| --- | --- | --- | --- |
| Model | `uom.uom` and `uom.category` | `uom.uom` only | `uom.uom` only |
| Conversion graph | `category_id`, `factor`, `factor_inv`, `uom_type` | `relative_uom_id`, `relative_factor`, stored computed `factor` | same graph as 19 |
| `uom.rounding` field | stored per unit | computed alias of Product Unit precision | field absent |
| Quantity rounding API | category-limited `_compute_quantity` | `uom.uom.round()` using Product Unit digits | `uom.uom.round()` using Product Unit digits |

Odoo 19 keeps `rounding` as a computed compatibility value. Odoo 20 removes that field and still rounds through `decimal.precision` name `Product Unit`. A later port cannot share one UoM implementation unchanged across 18, 19, and 20.

Reference units in Odoo 19 are `relative_factor = 1` with no parent. A child such as Pack of 6 stores `relative_factor = 6` and `relative_uom_id` pointing at Units. Conversion across two chains that do not meet is not a valid conversion.

## Proposed future dependency set

This is a planning proposal. No manifest was created.

| Dependency | Proposal | Reason |
| --- | --- | --- |
| `account` | Required when the module is eventually created | Posted customer invoices, taxes, partial reconciliation, and company rules. It already depends on `product`, so `uom`, `mail`, and `analytic` come with it. |
| `mail` | Direct dependency is justified when chatter is used | Already transitive through `product`. A direct dependency makes the intent obvious. |
| `sale` | Out of the required set until OD-09 | Pulls `account_payment`, `payment`, `sales_team`, and `utm`. |
| `sale_management` | Out of the required set | Sales application shell. Not needed to read invoices. |
| `purchase` | Out of the required set until OD-04 | Vendor bills are a different population. |
| `contacts` | Do not require the application | `res.partner` is already available. Odoo 20 changes this module's dependencies. |
| `loyalty` / `sale_loyalty` | Do not use as the contract engine | Promotional programs are not approved customer contracts. |
| Enterprise accounting | Forbidden as a requirement | Not in the Community trees. |

`account` also depends on `portal`. Portal access to contract prices is not a supplied requirement. A later module must not publish contract prices to the portal as a side effect of that dependency.

## Static-check limits

- Manifest `installable` flags were read and were not exercised.
- No database was created, so record rules were not executed.
- Odoo 18 and Odoo 20 field checks were name checks plus the selection blocks cited above. They were not a line-by-line port review.
- Python syntax and ORM differences such as `models.Constraint` in the 19/20 UoM files were noted only as port risk. Step 00 writes no ORM code.
