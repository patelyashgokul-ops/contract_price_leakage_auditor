# Sales quotation architecture

Odoo 19 Community `sale.order.action_confirm` writes `state` to `sale` and sets `date_order` to now, then calls `_action_confirm`. This addon does not copy an older `action_confirm`. It inherits `sale.order` and `sale.order.line` and calls `super()` only after the price gate.

Direct dependencies are `base`, `product`, and `sale`. `account` is available because `sale` depends on it. `account` is not a direct dependency. `sale_management` is not a dependency. There is no loyalty or delivery module in this build. `_is_delivery()` stays the core method, which returns false. A reward line is recognized only when `reward_id` exists.

## Services

| Model | Role |
| --- | --- |
| `cpla.quotation.compliance` | Abstract, read-only evaluator. No access row. |
| `cpla.sale.price.lock` | One row per confirmed sales order line. |
| `cpla.quotation.override.request` | Transient wizard. Creates a draft `cpla.discount.approval` only. |
| `cpla.discount.approval` | Existing DEV-09 request, with optional `sale_order_id` and `sale_line_id`. |

`evaluate_order` and `evaluate_line` do not write `price_unit`, do not clear `discount`, do not confirm the order, do not approve a request, and do not create an invoice.

The evaluator calls the existing resolver. The resolver still calls quantity normalization, financial normalization, and discount evaluation. Those calculations are not copied into `sale.order`.

## Confirmation order

1. Read access on the order.
2. `with_company` of the order company.
3. `evaluate_order(..., confirmation=True)` for every order in the call.
4. `UserError` if any line blocks. `super()` is not called.
5. Standard `action_confirm`.
6. `cpla.sale.price.lock.create({'sale_line_id': line.id})` for lines that do not already have a lock.

A context key such as `skip_price_check` is not read. One blocking order in a batch raises before `super()`, so the other orders in that call stay draft.

## UI

`views/sale_quotation_views.xml` inherits `sale.view_order_form`.

- Header button `Recheck Compliance` before the confirm button.
- Smart button `Price Evidence` when a lock exists.
- Line status, message, prices, and approval state after `price_unit`.
- `Request Override` and `View Approval` for `group_contract_user`.
- Page `Contract Compliance` before Other Info.

There is no Apply Approved Contract Price button. There is no invoice-audit menu and no leakage dashboard.
