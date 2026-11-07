# 03 — UoM conversion architecture

Date: 2026-10-28. Verified against Odoo 19 Community source `addons/uom/models/uom_uom.py` and `addons/product/models/product_template.py`.

## Installed model

The unit model is `uom.uom`.

| Field or method | Role |
| --- | --- |
| `relative_uom_id` | Parent unit. |
| `relative_factor` | Factor toward that parent. A database check rejects zero. |
| `factor` | Stored computed absolute factor. Reference unit factor is `relative_factor`. A child is `relative_factor * parent.factor`. |
| `parent_path` | Used by `_has_common_reference`. |
| `_compute_quantity(qty, to_unit, round=True, ...)` | `qty * self.factor / to_unit.factor`, then optional rounding. A falsy `qty`, including zero, returns `qty` unchanged. |
| `_compute_price(price, to_unit)` | `price * to_unit.factor / self.factor` using binary floats. A falsy price returns unchanged. |

Reference unit XML id: `uom.product_uom_unit`. Kilogram XML id: `uom.product_uom_kgm`. Dozen is inactive in the standard data. This phase does not activate or rewrite those records.

There is no `uom.category` on this runtime. Family membership is the shared reference path.

## What the pricing service uses

`cpla.pricing.quantity.convert_quantity` and `convert_price` use `Decimal`, not `_compute_quantity` or `_compute_price`.

Quantity: `quantity * from_factor / to_factor`.

Normalized unit price: `contract_price * target_factor / contract_factor`.

Example: 2400 per box, box factor 12, piece factor 1. Normalized price per piece is `2400 * 1 / 12 = 200`. One hundred pieces are `100 * 1 / 12` boxes. The text is the exact decimal. It is not rounded to 8 boxes.

Approved tier evaluation uses the factors stored on the tier. It does not reread `uom.factor` after approval. A comparison unit that is not the snapshotted product unit, quantity unit, or pricing unit is `MISSING_HISTORICAL_CONVERSION` even when the live units share a family. A different family is `INCOMPATIBLE_UOM`.

A non-positive factor returns `ok: false` and no amount. It does not raise a price.

Standalone lines have no factor snapshot. A different quantity unit or comparison unit clears the price. The current unit factor is not applied.

## Odoo 18 and Odoo 20

Not converted. The Odoo 19 parent/factor shape must be re-checked on those versions before any port. Do not copy `_compute_quantity`’s default rounding or its falsy-zero shortcut into the pricing path.
