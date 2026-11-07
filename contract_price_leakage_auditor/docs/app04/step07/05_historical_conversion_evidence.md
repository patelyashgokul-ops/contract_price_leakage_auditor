# 05 — Historical conversion evidence

Date: 2026-10-28.

## What is snapshotted

Each tier stores:

| Field | Meaning |
| --- | --- |
| `quantity_uom_factor` | Absolute factor of the tier quantity unit. |
| `pricing_uom_factor` | Absolute factor of the price unit. |
| `product_uom_factor` | Absolute factor of the product unit at capture. |
| `product_uom_id` | Product unit at capture. |
| `reference_uom_id` | Root of the quantity unit’s relative chain. |
| `factor_captured_at` | Set at approval. |

Draft `create` and `write` refresh the factors from the live unit and clear any client-supplied factor, product, company, or version. `factor_captured_at` stays empty until approval.

Approval locks the line and the tiers, then `_write_multi` writes `_factor_values(capture=True)`. That path does not call `write()`, so the draft-only guard does not wipe the capture. The tier cache is invalidated after the write.

## After approval

Evaluation of an approved tier requires `factor_captured_at` and positive stored factors on every tier of the line. A zero or missing factor is `MISSING_HISTORICAL_CONVERSION`. The live `uom.factor` is not substituted.

UOM07-T011 / T012 and HIS07-T003 / T004 change the live box from 12 to 10 after approval. The normalized January-style price stays 200 per piece, not 240.

An amendment copies the business range and price. Its own `create` reads the live factor again. That new draft, once approved, is a new snapshot. The previous version’s stored factors stay.

## What is not rewritten

Existing approved versions gained no tier rows during upgrade. Their standalone prices and checksums stay as stored. New approvals include tiers in the checksum. Old checksums are not recomputed.

A draft that tries to take effect before a later approved version cannot be submitted. The message says the draft cannot insert an earlier authority. HIS07-T006 covers that case. The approved 1200 rate for quantity 99 stays.

Same inputs, same approved snapshot, and same request produce the same `normalized_unit_price_exact`. The service does not create business records.
