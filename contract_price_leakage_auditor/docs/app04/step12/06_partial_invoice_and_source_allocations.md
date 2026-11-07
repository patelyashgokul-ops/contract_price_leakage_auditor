# Partial invoices and source allocations

The billed quantity is the verified allocated quantity on the posted invoice line, minus verified returns. The original ordered quantity is not billed again on every invoice.

## Partial invoices

`GOLD-AUD-009` orders 500 pieces at an approved 1,150 and invoices 200, 200, and 100 at 1,100. The three current findings are 10,000, 10,000, and 5,000. The total is 25,000. Repeating the audit does not add a second current finding for the same allocation.

The order quantity remains available as the tier qualification quantity. It is stored on the result as `qualified_quantity_exact` and is not the eligible quantity.

## Several sales lines on one invoice line

Each verified allocation is priced on its own contract version and quantity. The invoice line's recorded unit price is applied to each allocation after unit normalization.

If several native sales lines exist and no documentary split was verified, the mapper returns `SOURCE_ALLOCATION_REVIEW_REQUIRED`. The audit does not spread one price across the line and does not invent proportions. The amount stays blank.

Allocated quantities must reconcile to the invoice line in the supported UoM. A missing allocated quantity is review.

A contract filter on the run skips an allocation whose contract is a different contract. It does not treat a line with no allocation as a contract mismatch.

## Product and UoM

`GOLD-AUD-007` prices 2,400 per box of 12 and invoices 190 per piece. The approved comparable price is 200 per piece. Potential leakage is 1,000 on 100 pieces.

An isolated UoM that does not share a reference with the product unit is `MISSING_PRICING_EVIDENCE`. No amount is stored. `FIN12-T016` creates that isolated unit and asserts a blank exposure.
