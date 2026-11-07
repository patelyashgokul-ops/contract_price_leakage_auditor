# 08 — Quantity security matrix

Date: 2026-10-28.

## Access on `cpla.customer.contract.version.tier`

| Group | Read | Write | Create | Unlink |
| --- | --- | --- | --- | --- |
| Contract User | yes | yes | yes | yes |
| Contract Manager | yes | yes | yes | yes |
| Finance Reviewer | yes | no | no | no |
| Finance Manager | yes | no | no | no |
| Internal Auditor | yes | no | no | no |
| Application Administrator | no row | | | |
| Sales Pricing Reviewer | no row | | | |
| Recovery Operator | no row | | | |

`cpla.pricing.quantity` is an abstract model. It has no access row. Calling `evaluate` still checks read access on the version line in the caller’s environment. An application administrator without that read right receives `AccessError`. The message does not contain the tier rate.

There is no public, portal, or blank-group access row. SEC-T007 still scans product Python for `sudo(` and `.execute(`. `local_testing/` stays excluded because `free_space.py` uses a cursor.

## Record rules

Global company rule: `[('company_id', 'in', company_ids)]`.

Contract User: `[('version_id.contract_id.owner_id', '=', user.id)]`.

Contract Manager: `[(1, '=', 1)]`, still combined with the company rule.

Company A cannot search or group Company B tiers. Export without `base.group_allow_export` raises `UserError` before any rate is written. The test users do not have that group.

## Server guards

Tier `create`, `write`, and `unlink` require the contract-user group and a draft version. Approved tiers cannot be edited, deleted, or moved, including through a one2many command on the line.

Version-line `write` calls `check_access('write')` before the approved-snapshot message. A finance reviewer therefore gets `AccessError` on the line and on the company policy, not a path that changes the price.

Approval still freezes factors with `_write_multi` as the finance manager. That does not grant the finance manager a write ACL.

Cross-company create checks the line before it is dropped by `exists()`, so a hidden line is `AccessError`.

## What a result may show

A failed quantity evaluation may keep `version_id` so the caller knows which authority was inspected. `unit_price` is cleared. The wizard shows contract and normalized prices only when the status is `MATCHED_AUTHORITATIVE` and the tier status is `tier_matched`. Explanations for conflicts and quantity failures do not include the tier rate.

Combined contract-user and finance-reviewer rights do not make an approved tier writable.
