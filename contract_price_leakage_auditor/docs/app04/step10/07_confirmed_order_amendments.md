# Confirmed order amendments

The original lock is not overwritten when a confirmed line changes.

Watched line writes are `product_id`, `product_uom_qty`, `product_uom_id`, `price_unit`, `discount`, and `tax_ids`. Watched order writes are `partner_id`, `pricelist_id`, and `company_id`. The confirmation write of `state` and `date_order` is not watched. `qty_delivered` is not watched. A delivery quantity change does not flag revalidation.

When a watched value changes on a line in `sale` or `done`, and the fingerprint differs, the lock gets `revalidation_required` and reason `material_change_after_confirmation`. The approved amounts, version, and confirmation timestamp stay as stored.

The flag cannot be cleared while the current fingerprint still differs from the stored fingerprint. A second confirmation does not create another lock, so the original evidence remains the only row.

This phase does not block an operational delivery update. It does not rebuild the order price. It does not implement an amendment approval workflow beyond the existing override request. DEV-11 can use the flag and the original row together.
