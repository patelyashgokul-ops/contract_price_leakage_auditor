# Case security matrix

Groups are the DEV-02 groups. No new group was added. ACLs are rows in `security/ir.model.access.csv`. Implied groups do not copy ACLs, so finance manager has its own rows.

Record rules in `security/leakage_case_rules.xml` are global. The domain is `[('company_id', 'in', company_ids)]`. No group is set on the rules, so they apply to every user, including users in several companies. `company_ids` is the allowed companies on the environment.

## ACL summary

Read, write, create, unlink. Contract user is the investigator group. Contract manager implies the user group in XML, and also has its own ACL rows.

| Model | Contract user | Contract manager | Finance reviewer | Finance manager | Auditor |
| --- | --- | --- | --- | --- | --- |
| Case | R W | R W C | R W | R W | R |
| Membership | R W C | R W C | R | R | R |
| Event | R C | R C | R C | R C | R |
| Checklist | R W | R W C | R | R | R |
| Evidence | R W | R W C | R | R | R |
| Submission | R C | R C | R W | R W | R |
| Wizard | R W C U | R W C U | R W C U | R W C U | none |

No unlink on the persistent case models. No rows for sales, recovery, or application admin.

Application admin keeps only `cpla.company.policy` access and the root plus configuration menus. The admin cannot read a case through the ACL.

## Why membership create and write exist for the contract user

The investigator accepts a successor finding. That retires one membership and inserts another. `models.Model.write` and `models.Model.create` check ACLs, and the code does not use `sudo()`. The contract user therefore has create and write on membership.

The model methods still reject every direct create, write, and unlink with `UserError`. An RPC write cannot clear `is_current`. The class test calls `membership.write` and `membership.create` as the investigator and expects `UserError`.

Finance case write works the same way: the ACL allows write, and `LeakageCase.write` rejects finance users so they must call Return for rework.

## Server checks beyond ACLs

| Check | Effect |
| --- | --- |
| `_check_manager` | Assign, merge, split, close, reopen, priority, severity, participants, and `create_from_findings`. |
| `_check_investigator_actor` | Start, resume, checklist, evidence, root cause, outcome, submit, activity, accept source. Owner or contract manager. |
| `_check_finance_actor` | Return only. |
| `_eligible_investigator` | Owner and activity user must have the case company and a contract group. |
| `_partner_may_follow` | Followers and `message_post` recipients. Customer and share users fail. |
| Submitter lock | The user on `submission.submitted_by_id` cannot return that submission. |
| Company on the finding | A finding from another company cannot be linked. |
| Attachment guard | No public flag, no access token, no unlink, for case and evidence attachments. |
| `export_data` | Standard Odoo denial unless the user has export rights. The class test expects `UserError` for the investigator. No second export gate was added. |

`leakage_case.py` does not call `sudo(` or `.execute(`. The security source scan in the class test reads the file and asserts both are absent.

## Menus

Investigation menus are under `menu_cpla_root`, sequence 30: Investigation, Leakage Cases, My Cases (`owner_id = uid`), Unassigned, Evidence Pending, Ready for Finance Review, Exception Queue (`exception_queue != False`), Case History.

Groups on those menus: contract user, contract manager, finance reviewer, finance manager, internal auditor. Not application admin, sales, or recovery. The auditor still does not have the Audits menu.

## Invoice smart button

`action_view_invoices` opens `account.move`. Contract users do not have that model's read right. The button count uses finding `move_id` ids and does not read the journal entry. Opening the invoice is denied by Accounting ACLs. That denial is intentional. The case does not grant accounting groups.
