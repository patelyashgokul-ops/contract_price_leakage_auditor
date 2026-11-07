# DEV-14 security

Date: 2026-11-05. Version: `19.0.1.12.0`. Direct depends remain `base`, `product`, and `sale`. No accounting group is implied by a contract group. No `sudo(` and no `.execute(` were added in the addon Python. Later ACL and retention notes are in `11_evidence_security_and_retention.md`.

## Access bits

CSV order is read, write, create, unlink.

| Group | Reassessment | Event | Wizard |
| --- | --- | --- | --- |
| Contract user | 1, 0, 0, 0 | 1, 0, 0, 0 | no row |
| Contract manager | 1, 1, 1, 0 | 1, 0, 1, 0 | 1, 1, 1, 1 |
| Finance reviewer | 1, 1, 0, 0 | 1, 0, 1, 0 | 1, 1, 1, 1 |
| Finance manager | 1, 1, 0, 0 | 1, 0, 1, 0 | 1, 1, 1, 1 |
| Internal auditor | 1, 0, 0, 0 | 1, 0, 0, 0 | no row |

Sales pricing reviewer, recovery operator, and app admin have no reassessment access row. Nobody has unlink.

The model `create`, `write`, and `unlink` raise `UserError`. Event `create` raises `UserError` for a public call. Workflow methods call `models.Model.create` and `models.Model.write`, which still honor these access bits. A finance manager can write a proposal and cannot create the request through ACL. The contract manager creates it.

## Record rules

`security/leakage_reassessment_rules.xml` adds one ungrouped rule on each of the three models:

`[('company_id', 'in', company_ids)]`

`test_rev14_t001` shows a company B contract user cannot search or read a company A reassessment. `test_sec_t007` still forbids grouped rules outside the existing contract-model set.

## Server decisions

Evaluate and accept require the finance-manager group, audit-run authority, and source-map authority. The finance reviewer has invoice read in the test fixture and still cannot evaluate or accept (`test_rev14_t009`).

Accept raises `AccessError` when `requested_by_id` is the current user. That includes a superuser and a user who has both manager and finance-manager groups (`test_rev14_t005`).

Company is checked against `env.companies` unless the user is superuser. Source moves are read with `check_access('read')`. A credit in another company is a review reason, not a remapped price. The request stores a credit id and does not require the contract manager to read `account.move`. Evaluation reads it as the finance manager.

## What acceptance does not change

Posted invoice lines, posted credit notes, payments, and confirmed order prices stay as they were. `test_rev14_t001` compares price, quantity, payment count, and move count before and after acceptance. `test_rev14_t010` compares payment count. No module `ir.cron` is loaded.

Investigators do not write finding amounts. The case copy of a successor amount remains `action_accept_current_source`, and only while the case is in an open investigation state.

## Attachments and export

`CASE_ATTACHMENT_MODELS` includes `cpla.leakage.reassessment`. Public flag, access token, and unlink stay blocked for that model, as they are for the case. The reassessment does not copy invoice or contract attachments onto itself.

`export_data` refuses a share user or an inactive user and calls `check_access('read')`.

## Integrity limits

Readonly form flags are not the control. Public write raises before a normal user can change an amount. A digest mismatch blocks acceptance and leaves the current finding in place (`test_rev14_t002`). The original digest is kept.

Application checks do not stop a database administrator from changing rows. The digest is stored in the same database. The documentation does not call that a legal archive.

## Menus

`menu_cpla_reassessments` is under the investigation menu, sequence 80. Groups are contract user, contract manager, finance reviewer, finance manager, and internal auditor. App admin is not on that menu. The finding form has Request Reassessment for the contract manager. The run form still has the older reread button. See `01_reassessment_architecture.md`.
