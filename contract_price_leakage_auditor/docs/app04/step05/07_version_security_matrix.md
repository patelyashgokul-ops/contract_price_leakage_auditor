# 07 — Version security matrix

Date: 2026-10-28.

ACL file: `security/ir.model.access.csv`. Rules: `security/contract_version_rules.xml`. Group XML ids were not renamed. No public, portal, blank-group, sales, recovery, or application-administrator row was added for these models. Application administrator stays on the single policy ACL from DEV-03.

`sudo()` is not used. Approval methods call `check_access` and then the role checks. Client approval values are ignored.

## ACL

Permissions are read, write, create, unlink.

| Model | Contract User | Contract Manager | Finance Reviewer | Finance Manager | Internal Auditor |
| --- | --- | --- | --- | --- | --- |
| version | 1,1,1,0 | 1,1,1,0 | 1,0,0,0 | 1,1,0,0 | 1,0,0,0 |
| version line | 1,1,1,1 | 1,1,1,1 | 1,0,0,0 | 1,0,0,0 | 1,0,0,0 |
| version evidence | 1,1,1,1 | 1,1,1,1 | 1,0,0,0 | 1,0,0,0 | 1,0,0,0 |
| version event | 1,0,1,0 | 1,0,1,0 | 1,0,0,0 | 1,0,1,0 | 1,0,0,0 |
| compare wizard | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 | 1,1,1,1 | no row |

Finance Manager write on the version exists so `action_approve` can pass `check_access('write')`. `write()` still rejects commercial edits. The version row is stored with `super().write` only after the role, company, date, evidence, and conflict checks. The product-name freeze uses a low-level column update on the lines, because a Finance Manager has no line write ACL. It changes only `product_name`, only after the approver check, and only inside the approval savepoint. Public line `write()` still rejects a Finance Manager and still rejects every edit after the version leaves draft.

No role has unlink on the version. Draft line and draft evidence unlink is allowed for Contract User and Contract Manager. Approved children refuse unlink in Python.

The auditor has no wizard ACL, so auditor access stays read-only on the business models plus the policy model.

## Record rules

Global, no group, on version, line, evidence, and event:

`[('company_id', 'in', company_ids)]`

Contract User, AND-combined with the global rule:

| Model | Domain |
| --- | --- |
| version | `[('contract_id.owner_id', '=', user.id)]` |
| line | `[('version_id.contract_id.owner_id', '=', user.id)]` |
| evidence | `[('version_id.contract_id.owner_id', '=', user.id)]` |
| event | `[('version_id.contract_id.owner_id', '=', user.id)]` |

Contract Manager, OR-combined with the user rule, then AND with the company rule:

`[(1, '=', 1)]` on version, line, evidence, and event.

Finance Reviewer, Finance Manager, Internal Auditor, Sales, Recovery, and Application Administrator do not have a group rule on these models. A Finance Manager who is not also a Contract User is limited by the company rule only. A user who also has Contract User stays owner-limited, including when Finance Reviewer or Auditor is added.

Wizard rule, no group: `[('create_uid', '=', user.id)]`.

Company mismatch checks in Python raise `UserError`. A record the user cannot read raises `AccessError` from the record rule before those checks.

## Server checks that ACL does not replace

- Create requires Contract User.
- Approve requires Contract Manager or, for an existing ready version, Finance Manager.
- Initial snapshot creation requires Contract Manager, because Finance Manager cannot create lines.
- Self-approval checks owner, requester, submitter, and, for version 1, the contract creator.
- Events can be created only for the matching state and actor.
- Evidence reads follow the evidence ACL and rules. There is no public link.

## Tests that exercise this

SEC05-T001 through SEC05-T015 in `tests/test_contract_version.py`, using non-admin users. Menu visibility is not the assertion. Outcomes are in `09_automated_test_results.md` after the run.
