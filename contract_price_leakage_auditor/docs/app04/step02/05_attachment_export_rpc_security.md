# 05 — Attachments, exports, and RPC

Date: 2026-10-28.

## Surfaces reviewed

| Surface | Result |
| --- | --- |
| APP 04 models and public methods | None. The registry has no model whose `_module` is this addon. |
| `sudo()` | No call in addon Python outside `tests/` and `docs/`. Classification: NOT_APPLICABLE. |
| Raw SQL | No `cursor.execute` or `cr.execute` in that same Python. |
| `ir.attachment` records owned by the module | None. |
| Reports and server actions | None in `ir.model.data`. |
| Menus | None. |
| Cron | None. |

`test_sec_t007_no_public_portal_or_unrestricted_acl` asserts those absences and walks the addon Python.

## Sensitive fields to protect later

Negotiated unit price, discount, margin or cost, recovery amount, and waiver reason are confidential. Contract existence and non-price metadata can be visible to a wider contract role.

View `invisible` and `groups` on a form are not enough. The field, or the method that returns it, must enforce the group on the server. `read`, `search_read`, `read_group`, `name_search`, and export paths have to be covered when the fields exist. SEC-T023 and SEC-T027 are planned.

## Evidence and attachments

Future evidence files use `ir.attachment` linked to the parent record. Access follows the parent company and the parent read group. This phase does not change standard Odoo attachment rules.

When evidence models exist, the tests must show:

- A user who cannot read the parent cannot download the file.
- No public token is created for a contract or price file.
- Attachment search does not return another company's evidence.
- A hold blocks deletion. The hold period is DEC-17 and is not set here.

## Exports

No PDF, XLSX, or CSV export exists. A later export must recheck the user, the company, and field access on the server, use the record rules of the source model, and avoid `sudo()`. A dashboard group must not automatically read every underlying financial row. SEC-T026 is planned for DEV-19.

## RPC

There is no business method to call. The rule for later methods is that company, user, role, price, amount, and state come from the server-side record and the current user, not from the client payload.

## `sudo()` rule

Any later `sudo()` needs a written reason, a record scope, and an authorization check before the elevated call. A test failure is not a reason to add `sudo()`.
