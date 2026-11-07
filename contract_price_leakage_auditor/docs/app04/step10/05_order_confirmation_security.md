# Order confirmation security

The gate is `sale.order.action_confirm`. Form, list, RPC, and a multi-record call all use that method. The check runs on the server before `super()`.

`with_company(order.company_id)` puts the order company in the evaluation environment. A normal user whose companies do not include that company gets AccessError from the environment. The technical superuser can read the company. Odoo 19 `has_group` does not treat the superuser as a member of the pricing groups, so the resolver, the financial normalizer, and the discount evaluator return immediately when `env.su` is set. A normal user cannot set that flag through RPC. This is not `sudo()`.

Failed validation raises `UserError` and does not call `super()`. No price lock is written. The database transaction rolls the attempt back.

If standard confirmation raises, the lock loop does not run. If lock creation raises, the confirmation write is in the same transaction and rolls back with it.

Repeated confirmation searches for an existing lock on the line and does not create a second row. The database constraint is `UNIQUE(sale_line_id)`.

Client values on lock create are ignored. The row is rebuilt from `lock_values`. Create is refused unless the line state is `sale` or `done`. Write accepts only `revalidation_required` and `revalidation_reason`. Clearing the flag while the fingerprint differs is refused. Unlink is refused except during module uninstall.

Draft compliance fields are computed and not stored. Repeated evaluation does not insert warning rows or exposure documents.
