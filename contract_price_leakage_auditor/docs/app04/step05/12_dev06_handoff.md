# 12 — DEV-06 handoff

Date: 2026-10-28.

DEV-06 is not started. Applicability, precedence, and invoice matching are not implemented.

## Models

| Item | Technical name |
| --- | --- |
| Contract header | `cpla.customer.contract` |
| Contract line | `cpla.customer.contract.line` |
| Contract evidence | `cpla.customer.contract.evidence` |
| Version | `cpla.customer.contract.version` |
| Version line | `cpla.customer.contract.version.line` |
| Version evidence | `cpla.customer.contract.version.evidence` |
| Version event | `cpla.customer.contract.version.event` |
| Policy | `cpla.company.policy` |

Header states: `draft`, `ready_for_review`, `cancelled`. Do not treat ready for review as approved.

Version approval states: `draft`, `ready_for_review`, `approved`, `rejected`, `cancelled`.

Only `state = approved` may be used as pricing authority.

## Effective dates

- `effective_from` is inclusive.
- `authority_to` is inclusive. It is the day before the next approved version's `effective_from`, otherwise `valid_to`.
- `valid_from` and `valid_to` are the snapshot's overall validity. They are not the approval timestamp.
- `approved_at` is a datetime and is not a commercial date.
- Derived status: `scheduled`, `currently_effective`, `superseded`, `expired`.
- Do not add a cron that rewrites these rows when a date arrives.
- A past `effective_from` on version 1 is the first snapshot. A past `effective_from` on an amendment is retroactive and is not approved.

## Supersession

Read `supersedes_version_id` on the newer approved version. Do not expect the older row's commercial fields to change when the newer one is approved. `superseded_by_ids` is the inverse.

Two approved versions with the same `effective_from` are rejected at approval time. A candidate that would start before an already approved later version is rejected. DEV-06 must not pick the lowest price, highest price, latest write, or highest id if bad data is ever present.

## Price fields

Use `cpla.customer.contract.version.line.price_unit` with that line's `currency_id` and `uom_id`, and `product_name` as the frozen label.

Do not use:

- the header line price as the historical price once a version exists
- product list price, cost, pricelist, or last sale
- `change_summary` or `price_delta` as recovered cash
- a simple delta when `normalization_required` would be true

Customer scope is `partner_id` plus `partner_name`. Extra `covered_partner_ids` are not an approved coverage expansion. DEC-03 is open, and approval blocks those proposals.

Company scope is `company_id` on the version. Do not attach a version from another company.

## Policy fields to read

Use the snapshot characters on the approved version:

- `policy_id` as the pointer that was current at approval
- `policy_version_snapshot`
- `pricing_date_policy_snapshot`
- `precedence_policy_snapshot`
- `coverage_policy_snapshot`

The live policy row can change later. `operationally_approved` is false. Those strings are candidates, not an operational pricing-date decision (DEC-01) and not a precedence decision (DEC-02).

`amount_threshold_policy` and `retroactivity_policy` do not grant authority.

## Security

| XML ID | DEV-06 must keep |
| --- | --- |
| `contract_price_leakage_auditor.group_contract_user` | Own-contract read. Not approval. |
| `contract_price_leakage_auditor.group_contract_manager` | Company read. Implies Contract User. |
| `contract_price_leakage_auditor.group_finance_reviewer` | Read. No approval. |
| `contract_price_leakage_auditor.group_finance_manager` | Implies reviewer. Approval of a ready version only under the DEV-05 rule. |
| `contract_price_leakage_auditor.group_internal_auditor` | Read-only. |
| `contract_price_leakage_auditor.group_app_admin` | No version ACL. |
| `contract_price_leakage_auditor.group_sales_pricing_reviewer` | No version ACL. |
| `contract_price_leakage_auditor.group_recovery_operator` | No version ACL. |

Global rule on the version models: `[('company_id', 'in', company_ids)]`. Contract User owner rules and Contract Manager `(1, '=', 1)` are OR-combined, then AND-combined with the company rule. Do not put a wide group rule on auditor or finance.

## Fixtures

`tests/test_contract_version.py`. Companies ABC India and ABC UAE. Users are created with `new_test_user`, password `cpla-test`, plus `base.group_user`. Concurrent tests commit on a separate cursor and must not be replaced by a second call in the same transaction.

Passed and deferred test ids are listed in `09_automated_test_results.md`. The green runs on 2026-10-28 are the upgrade `-u` at 07:31:22 UTC and the fresh `-i` at 07:34:08 UTC. Each result line is `0 failed, 0 error(s) of 242 tests`. GOLD-FIN-001, GOLD-FIN-002 applicability, and GOLD-REC-001 are NOT_EXECUTED.

## Unresolved decisions

| ID | Effect on DEV-06 |
| --- | --- |
| DEC-01 pricing date | Snapshot stores a candidate only. |
| DEC-02 precedence | Snapshot stores a candidate only. Do not invent a winner. |
| DEC-03 coverage | Extra customers and partner changes are blocked at approval. |
| DEC-04 quantity basis | No tier math. |
| DEC-05 discount stacking | Not implemented. |
| DEC-06 FX | No conversion. Comparison marks normalization. |
| DEC-07 tax | Not implemented. |
| DEC-08 rounding and tolerance | Not implemented. |
| DEC-11 recovery | Not implemented. |
| DEC-12 waiver | Not implemented. |
| Amount ceilings | `not_configured`. Do not invent thresholds. |
| Retroactivity | Blocked. Do not approve a backdated amendment in DEV-06 either, unless a later authorized policy exists. |
| Zero price, open end, packaging as the price unit | Still blocked at approval. |
| License | `BLOCKER_LICENSE_DECISION_REQUIRED`. Manifest guard remains `Other proprietary`. |

## Limits DEV-06 must not inherit as completed work

- No invoice selection, pricing-date match, or grandfathering outcome.
- No leakage amount, including the illustrative 25,000.
- No recovery, waiver, or accounting write.
- Effective status is a calendar view of approved rows, not the applicability engine.
- Odoo 18 and Odoo 20 were not converted.
