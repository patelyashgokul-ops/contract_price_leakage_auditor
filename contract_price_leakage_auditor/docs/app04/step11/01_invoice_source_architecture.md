# Invoice source architecture

Addon `contract_price_leakage_auditor` version `19.0.1.9.0`. Odoo 19.0 Community. The run log prints `Odoo version 19.0`. Direct dependencies stay `base`, `product`, and `sale`. `account` is not a direct dependency. It is available because `sale` depends on it. `stock`, `delivery`, `sale_management`, and `loyalty` were not added.

The mapper is the abstract model `cpla.invoice.source`. Persistent evidence is `cpla.invoice.source.map`. Quantity splits are `cpla.invoice.source.allocation`. A finance manager can enter a split through the transient models `cpla.invoice.source.verification` and `cpla.invoice.source.verification.line`. `account.move` is extended only to count and open existing evidence. `account.move.line` is not extended.

## Native relations used

These relations were exercised by the DEV-11 tests on this Odoo 19 install.

- `sale.order.line.invoice_lines` is a many-to-many to `account.move.line` through `sale_order_line_invoice_rel`.
- The reverse field is `account.move.line.sale_line_ids`. It is read-only in the sales addon and is not rewritten by this mapper.
- Standard `_prepare_invoice_line` links one sales line to the invoice line it creates. The relation table stores no quantity.
- `account.move.invoice_line_ids` holds display types `product`, `line_section`, `line_subsection`, and `line_note`. Tax, receivable, rounding, and early-payment lines stay on `line_ids`.
- `account.move.reversed_entry_id` points at the original document. `reversal_move_ids` is the reverse collection. There is no native line-level reversal field. `_reverse_moves` copies `sale_line_ids` because business fields are included.
- Customer credit quantity is normally positive. Commercial sign in this addon is `+1` for `out_invoice` and `-1` for `out_refund`. Odoo `direction_sign` is not reused.

## What the service does

`map_move` reads one accounting document and stores APP 04 evidence. `map_moves` wraps each document in a savepoint. A failure on one document does not mark that document verified and does not undo earlier documents in the same call. The batch method does not open a second database session.

The service does not post, edit, refund, reconcile, or delete accounting documents. `leakage_amount` and `is_recovered_cash` are stored as false. No leakage, recovery, payment, or cron model is created.

## Odoo 18 and Odoo 20

No conversion was done. Later versions need their own check of `sale_line_ids`, display types, `reversed_entry_id`, credit quantity sign, UoM `factor`, and test tags.
