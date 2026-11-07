# 04 — Customer and product scope

Date: 2026-10-28.

DEC-03 (customer coverage), DEC-01 (pricing date), DEC-02 (precedence), and DEC-04 (quantity basis) stay open. This phase records scope. It does not match an invoice.

## Exact customer

`partner_id` is the contracting party. A parent company's agreement is not applied to branches or subsidiaries. `commercial_partner_id` is the related commercial entity and is stored only as identity context.

A child contact may be the contracting customer. That contract covers that child, not the parent and not the siblings. The test `test_extra_covered_entities_block_submission_while_dec03_is_open` stores a child as `partner_id` and leaves `covered_partner_ids` empty.

Shared contacts (`company_id` false) are accepted. A contact restricted to another company is rejected. The module does not write `res.partner` company or identity in order to create a contract.

## Covered entities

`covered_partner_ids` can store proposed extra customers with a company-compatible domain. While DEC-03 is open, any extra entity blocks `action_submit_for_review`. The message names DEC-03. No customer group, branch rollup, or parent rollup is applied.

DEV-06 will decide which invoice customer is covered. Until that decision is approved, coverage is the selected customer only.

## Product variant

`product_id` is `product.product`. `product_tmpl_id` is derived and stored. Variants of one template are different price identities. The module does not copy a template price onto every variant.

Shared products are accepted. A product restricted to another company is rejected with `UserError` from the company check. An archived product can remain on a draft line and blocks review. The product record is not deleted or rewritten. `list_price` is not read into `price_unit`. Changing `list_price` later does not change the contract line.

## Pricing unit

The line stores `uom_id` and `price_unit` together. Example retained for a later phase: a contract may say 2,400 per box. This phase stores 2,400 and the selected unit. It does not compute an equivalent piece price.

On save:

- A unit in another family is rejected. `uom.uom._compute_quantity` is not used as a silent converter.
- An inactive unit is rejected and is not activated.
- A non-positive `relative_factor` is rejected.
- A packaging unit from `product.template.uom_ids`, or any other compatible unit that is not the product default, is stored and blocks review.

`product.packaging` does not exist in this Odoo 19 Community build and is not used.

Only the product's default unit can be submitted. Financial conversion belongs to DEV-07.

## Price

`price_unit` is monetary in the header currency. It has no default. Negative prices raise `ValidationError`. Zero is kept on a draft and blocks review, because a free-of-charge policy is not approved. The message says zero is not an approved selling price.

Company currency stays on `company_currency_id`. Changing the contract currency while lines exist is blocked. Numbers are not reinterpreted and no exchange rate is written.

## Duplicate lines and overlapping contracts

Exact duplicate means the same contract, the same variant, and the same unit. It is rejected. The same variant with a different unit is not rejected by a product-only unique key. That second line still cannot be submitted when the unit is not the product default.

Several contracts for one customer are allowed. When two non-cancelled contracts in the same company share the customer, an overlapping period, and a product, `overlap_warning` is:

`CONTRACT_CONFLICT_REVIEW_REQUIRED: <references> share this customer, period, and product. No price was selected.`

The warning uses the caller's record rules. It does not search with sudo and does not choose a price. Precedence remains DEV-06.

## Future tier shape

Recommended DEV-07 shape: one contract line per variant and pricing unit, with child tier rows for quantity breaks. Do not add `UNIQUE(contract_id, product_id)` in a later phase without a migration plan. This phase does not create the child model and does not audit tiers.
