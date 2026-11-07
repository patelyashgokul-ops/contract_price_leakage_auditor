# 01 — Configuration architecture

Date: 2026-10-28.

Module: `contract_price_leakage_auditor` `19.0.1.1.0`.

Odoo: 19.0 Community, `version_info` `(19, 0, 0, 'final', 0, '')`.

## Source of truth

Company policy lives on one model, `cpla.company.policy` (`models/company_policy.py`).

Each row belongs to one `res.company` through required `company_id`. A company has at most one current row. Older rows stay in the same table with `is_current` false and `supersedes_id` pointing at the row they replace. Future audit records can store `policy_id` and `version`.

`operationally_approved` is a computed boolean and is always false. Selecting a candidate, filling the form, or submitting for review does not approve a policy.

## Why this store

Historical policy versioning is required. A later price check must be able to name the revision that was current when a decision was made. A single set of fields on `res.company` would overwrite that history. `ir.config_parameter` is global, so it cannot hold confidential company pricing policy. `res.config.settings` is a transient settings screen and would need a second store. This phase does not use it, so there is no second source of truth to synchronize.

`res.company` is still the company and currency master. `company_currency_id` is a related readonly field. Currency rates, units of measure, products, and partners stay on their standard models. This module does not copy those engines.

## Lifecycle

| State | Meaning in this phase |
| --- | --- |
| `not_configured` | Every policy selection is `unconfigured`. |
| `draft` | At least one candidate is stored. The candidate is not approved. |
| `review_required` | Reserved on the selection. No method assigns it. Validator results use the separate classification `REVIEW_REQUIRED`. |
| `ready_for_business_review` | An Application Administrator submitted the current draft. A person still has to resolve open decisions. |
| `approved_ready` | Present so the forbidden outcome has a name. Create, write, and a constraint reject it. |

`action_request_activation` checks the user, blocks self-approval, and then raises `UserError` listing DEC-01, DEC-02, DEC-03, DEC-04, DEC-05, DEC-06, DEC-07, DEC-08, DEC-11, and DEC-12. It does not write.

Open decisions are constants. This phase does not close them and does not invent amounts, stacking, an FX basis, a tax basis, a tolerance, coverage, a quantity basis, or precedence.

Conflict behavior is the constant `CONTRACT_CONFLICT_REVIEW_REQUIRED`. Contract-specific priority is the constant `CONTRACT_SPECIFIC_TERMS_MAY_OVERRIDE_THE_COMPANY_DEFAULT_ONLY_AFTER_A_LATER_APPROVED_CONTRACT`. Neither constant executes matching.

## Company and security boundary

The record rule `cpla_company_policy_company_rule` is global (no groups) and uses `[('company_id', 'in', company_ids)]`. `company_ids` is the active company set on the environment, not a value trusted from the client alone.

Python also requires the target company to be in `user.company_ids` and in `env.companies` for non-superuser creates. Writes of another company's row fail the record rule on read before the business write proceeds.

One current row per company is enforced by `_check_one_current` and by the partial unique index `cpla_company_policy_one_current_idx` on `(company_id) WHERE is_current`.

## Audit trail

There is no `mail.thread` and no chatter. The revision row is the history: previous values, requester, timestamp, reason, version, and `supersedes_id`. Public `write` on a non-current row raises `UserError`. `unlink` raises `UserError` unless the environment is superuser and the context key is `_force_unlink` (Odoo's module-uninstall flag). `copy` raises `UserError`.

This trail is not tamperproof. A database administrator, or the Odoo superuser with that uninstall context, can change rows outside the application. That trust boundary is explicit.

## What this phase does not store

No customer contract, contract line, price version, invoice audit, leakage case, recovery, waiver, settlement, cron, dashboard, accounting entry, numeric tolerance, numeric FX rate, or approval limit.

Import and export of configuration files are not implemented. A later phase would have to restrict confidential fields, bind company and version, and refuse to overwrite an approved historical row.

## Odoo 18 and Odoo 20

Odoo 19 remains the master. This phase did not convert the module and did not re-test Odoo 18 or Odoo 20.

Step 02 already recorded that Odoo 18 groups use `category_id` and `res.users.groups_id`, while this addon uses `res.groups.privilege` and `res.users.group_ids`. Odoo 20 still has privileges, with a different privilege label, and the base access filename checked on 2026-10-28 was `ir.access` rather than `ir.model.access`. Those notes still stand.

This phase additionally depends on Odoo 19 `uom.uom.relative_factor`, `uom.uom._has_common_reference`, and `product.template.uom_ids` (the Packagings list). `product.packaging` is not in the Odoo 19 Community addons registry used here. Those models must be read from the target version before any port. `res.config.settings` and company-dependent fields were not used as the policy store.
