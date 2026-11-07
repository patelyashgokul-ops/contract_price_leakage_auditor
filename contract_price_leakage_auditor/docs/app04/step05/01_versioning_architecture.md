# 01 — Versioning architecture

Date: 2026-10-28.

Addon: `contract_price_leakage_auditor` `19.0.1.3.0`. Odoo 19 Community. Direct depends: `base`, `product`.

## Source of truth

The stable contract identity stays on `cpla.customer.contract`. That header is not the approved price. Its states remain `draft`, `ready_for_review`, and `cancelled`.

Approved commercial terms live on a child version:

| Model | Technical name | Role |
| --- | --- | --- |
| Contract header | `cpla.customer.contract` | Identity, owner, company, proposed header terms. |
| Contract line | `cpla.customer.contract.line` | Proposed negotiated lines. Not the historical price. |
| Contract evidence | `cpla.customer.contract.evidence` | Header file. Frozen when the header leaves draft. |
| Version | `cpla.customer.contract.version` | One full commercial snapshot and its approval state. |
| Version line | `cpla.customer.contract.version.line` | Snapshotted product, unit, and unit price. |
| Version evidence | `cpla.customer.contract.version.evidence` | Link to header or prior-version evidence, or a new file. |
| Version event | `cpla.customer.contract.version.event` | Append-only action history. |
| Comparison wizard | `cpla.customer.contract.version.compare` | Transient read-only comparison. |

`audit_authoritative` on the header is true only when at least one child version is `approved`. Saving a draft, or moving a header to ready for review, does not set it.

## Snapshot strategy

Chosen strategy: a complete approved contract-version snapshot.

Why:

- Each approved version can be read without replaying a chain of deltas.
- Unchanged lines are stored on the new version, so a missing line means the product was removed.
- Version-to-version comparison does not guess inherited values.
- DEV-06 can point at one version row and its lines.
- The previous approved row is not edited when a later version is approved.

This is not mixed with partial deltas. There is no second reconstruction policy.

Unchanged lines are copied onto the new draft with `origin_line_id` set to the source line. Their price, product, and unit stay as copied until a user edits the draft.

Removed products are absent from the new snapshot. Comparison reports them as Removed Product. The source lines stay on the source version.

New products are new draft lines. Comparison reports them as Added Product.

Historical versions are the approved rows themselves, plus their lines, evidence links, and events. Recovery does not rebuild a price from the live header or from the product list price.

Binary attachments are not copied into each version. Version evidence stores `source_evidence_id` and/or `origin_evidence_id`. A new file may be stored on that evidence row. `content_sha256` is a checksum of bytes that were read. It is not legal proof and it does not use an external cryptographic service.

## What is frozen at approval

`action_approve` writes, in one savepoint:

- approval state, approver, approval timestamp, and approval reference
- customer name, commercial partner name, and covered-name text
- policy version number and the pricing-date, precedence, and coverage candidate strings
- snapshot checksum
- `supersedes_version_id` when the version has a source
- product name text on each line

The policy row itself stays editable by the DEV-03 configuration path. DEV-06 must use the snapshot characters, not the live policy text, as the approval-time candidate.

`amount_threshold_policy` is the constant `not_configured`. `retroactivity_policy` is the constant `not_authorized`. Neither value grants an amount ceiling or a retroactive approval.

## Numbering and references

Version numbers are sequential per contract, including cancelled numbers. Numbers are not reused and are not promised to be gapless under a failed transaction.

Allocation locks the parent contract with `lock_for_update` (`FOR UPDATE SKIP LOCKED`). The other transaction receives `LockError` immediately. It does not wait. A memory counter covers several rows created in one `create()` call. `UNIQUE(contract_id, version_number)` is the database backstop.

The version reference is `{contract.reference}/V0001`. The approval reference is `{version.reference}/APR`. Both are server-assigned.

## Company and customer scope

`company_id` on the version, line, evidence, and event is the parent contract company. A version cannot be filed on another company's contract. Shared partners and products (`company_id` false) remain allowed. A partner or product owned by another company is rejected.

Customer changes and extra covered partners are stored on a draft only as a proposal. Approval is blocked while DEC-03 is open. No price is selected.

## What this phase does not decide

DEV-06 applicability, pricing-date selection, grandfathering, precedence, quantity tiers, currency conversion, tax, invoice comparison, leakage, recovery, waivers, and accounting entries are not implemented. No cron rewrites effective status. No action reprices sales orders, invoices, or pricelists.

## Odoo 18 and Odoo 20

Odoo 19 is the master. This phase does not convert the module.

Items that need their own check on Odoo 18 and Odoo 20:

- `models.Constraint` versus older `_sql_constraints`
- `check_company` and related stored `company_id` during create
- record-rule evaluation order against global and group rules
- `res.groups` privilege and implied-group XML
- `fields.Date.context_today` and inclusive calendar dates
- `fields.Monetary` and currency comparison
- list/form view syntax, including `edit` on `<list>`
- object-button methods that must return `True` or an action dict
- `TransactionCase`, `new_test_user`, and `lock_for_update` / `LockError`
- `Binary` `attachment=True` access
- migration of version rows if a later branch upgrades a database

Do not assume these Odoo 19 calls work unchanged on the other versions.
