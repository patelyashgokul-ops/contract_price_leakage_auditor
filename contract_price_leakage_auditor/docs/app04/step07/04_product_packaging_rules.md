# 04 — Product packaging rules

Date: 2026-10-28.

## What packaging is here

Odoo 19 Community in this build has no `product.packaging` model. UOM07-T015 asserts that name is absent from the registry, and that the tier model has no `package_id` or `quant_package_id`. The test passed.

Product packaging for sales is `product.template.uom_ids`: extra `uom.uom` records, help text “Additional packagings for this product which can be used for sales”. The product’s own `uom_id` remains the inventory unit. A normal test product uses Units.

A commercial box is a `uom.uom` whose `relative_uom_id` is the product unit and whose `relative_factor` is the number of pieces. Tests create units such as `CPLA07 Box 12`. They do not change the reference Units record.

## Product-specific factors

A box linked on another template, and not on this product, and not the product’s own unit, is rejected at tier create. Product A at 12 pieces and Product B at 24 pieces stay separate. The same name “Box” is not a universal factor.

A custom unit that is not on any other template is allowed. The contract still snapshots the numeric factor. Later edits to `relative_factor` do not change an approved tier.

## What is not a price unit

Physical shipping containers are not read. `stock.quant.package` is not a conversion source.

The version line still cannot be approved on a non-default unit. That DEV-06 rule is unchanged, so a pack unit on the line still blocks submit. The box price lives on the tier. The line stays on the product’s default unit.

`cpla.company.policy` still computes `PACKAGING_UOM_IS_NOT_A_PRICE_UNIT`. That flag is not an approval of packaging-as-price. The tier is the place a pack unit is authorized, and only with a snapshotted factor.

## Price example

Contract tier: 2400 per box of 12 pieces. Comparison unit: piece. Normalized price: 200 per piece. The line’s standalone price is not added.
