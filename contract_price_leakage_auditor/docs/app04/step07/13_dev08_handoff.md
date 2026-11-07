# 13 — DEV-08 handoff

DEV-08 was not started. Currency, tax, and final rounding are not implemented.

`docs/app04/step06/13_dev07_handoff.md` said DEV-07 was not started. That sentence is the historical step 06 record. This file replaces it for the next phase.

## Models

- Tier: `cpla.customer.contract.version.tier`, child of `cpla.customer.contract.version.line`.
- Service: `cpla.pricing.quantity`.
- Resolver: `cpla.pricing.applicability.resolve(request)`.
- Wizard: `cpla.pricing.applicability.check`.

## Tier method and range

Approved priced method: `full_volume` only. `graduated` and `cumulative` return `UNSUPPORTED_QUANTITY_POLICY` and no price.

Range: minimum inclusive, maximum exclusive. Open end is `has_maximum = False`.

If the line has no tiers and method `none`, `unit_price` stays the line price. `tier_status` is `not_applicable` when no quantity was supplied, and `base_price_applicable` when a quantity was supplied. The explanation then says the price is not a qualified tier price.

## Quantity modes that price

Line `quantity_basis`: `sales_order`, `invoice_line`, `delivery`.

Company `quantity_basis_policy` is not applied. DEC-04 is open.

Return modes that price: `order_tier_lock` and `net_quantity`. `unconfigured` plus a return is review.

## Request fields that matter

`quantity`, `order_quantity`, `invoice_quantity`, `delivery_quantity`, `billed_quantity`, `returned_quantity`, `quantity_uom_id`, `comparison_uom_id`, `qualification_basis`, `document_type`, `allocation_unverified`, `invoice_line_quantities`, `delivery_quantities`, `other_product_quantity`, `variant_quantity`.

Ignored if the client sends them: `version_id`, `contract_id`, `unit_price`, `tier_id`, `normalized_unit_price`, `contract_unit_price`.

The wizard turns a blank float into false with `or False`. Do not use the wizard to test a literal zero. Call `resolve`.

## Output added on every resolver result

`quantity_status`, `tier_id`, `qualified_quantity_exact`, `qualified_uom_id`, `normalized_unit_price`, `normalized_unit_price_exact`, `normalized_quantity_exact`, `normalized_uom_id`, `conversion_factor_exact`, `contract_unit_price`, `contract_uom_id`, `billed_quantity_exact`, `tier_method`, `quantity_basis`, `return_policy`, `historical_factor_used`.

`tier_status` matches `quantity_status`. Default when quantity is not evaluated: `not_applicable`.

On a tier match, `status` stays `MATCHED_AUTHORITATIVE`, `unit_price` becomes the normalized price, and `uom_id` becomes the comparison unit. `contract_unit_price` stays the tier price in the tier pricing unit.

On a quantity failure after one authority was found, `status` becomes the quantity status, `unit_price` is false, and `version_id` may still identify the inspected version. `leakage_amount` and `is_recovered_cash` stay false. `precedence_rule` is cleared.

A DEV-06 conflict is unchanged. DEV-07 does not pick the cheaper contract.

## Conversion

Do not call `uom.uom._compute_quantity` or `_compute_price` for this price. Use the snapshotted factors.

`normalized = contract_price * target_factor / contract_factor` as `Decimal`.

Approved factors live on the tier: `quantity_uom_factor`, `pricing_uom_factor`, `product_uom_factor`, captured at `factor_captured_at`. Missing or non-positive stored factors are `MISSING_HISTORICAL_CONVERSION`. Do not reread the live unit.

Packaging is a product-specific `uom.uom`, not `product.packaging` and not a physical package.

## Precision DEV-08 must add

Keep the exact strings until the approved rounding rule exists. Do not invent a tolerance. Do not convert currency. Do not apply tax. Do not apply discounts. Do not compare an invoice price. Do not create a leakage finding.

## Security

Same company boundary as DEV-06. Tier ACLs are in `08_quantity_security_matrix.md`. Do not add `sudo(`.

## Tests still open

Document linkage for partial invoices, deliveries, and credit notes: `DEFERRED_TO_DEV11_OR_DEV12`.

A second database worker for concurrent tier approval was not run. The in-transaction overlap check passed.

The lookup ceiling test passed at under 5 seconds. Exact seconds and queries per lookup were not logged. There is no result cache.
