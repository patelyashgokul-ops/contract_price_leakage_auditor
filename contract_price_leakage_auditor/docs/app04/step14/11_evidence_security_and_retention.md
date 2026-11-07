# Evidence security and retention

Date: 2026-11-05.

## Access

Company record rules on `cpla.leakage.reassessment`, `cpla.leakage.reassessment.event`, and `cpla.leakage.reassessment.wizard` use `[('company_id', 'in', company_ids)]`. Finding and case rules from DEV-12 and DEV-13 stay in place.

ACL summary for the reassessment models:

| Group | Reassessment | Event | Wizard |
| --- | --- | --- | --- |
| Contract user | read | read | none |
| Contract manager | read, write, create | read, create | full |
| Finance reviewer | read, write | read, create | full |
| Finance manager | read, write | read, create | full |
| Internal auditor | read | read | none |

Write on the reassessment does not grant a way around `action_accept`. The public methods check the role, the company, the state, and self-approval again. Event rows have no write or unlink ACL. The model methods raise as well.

A user in both companies still uses the company on the record. Company A evidence is not readable under a Company B context. `affected_findings` rejects a version from the other company.

## Public methods

Request, evaluate, accept, reject, cancel, verify digest, open original result, and open case call `check_access` or the role helpers. Export uses `export_data`, which refuses a public user. There is no public URL for contract terms. Attachment access stays on the existing contract, invoice, and case rules.

No `sudo()` was added. Technical administrator is not given finance-manager rights by this module. A combined manager and finance-manager user still cannot accept a request they created.

## Retention

Original audit results, superseded findings, rejected proposals, and events are not deleted by a cron. No reassessment cron was added. DEV-18 would schedule operational jobs. Customer recovery letters are not generated.

The digest and the stored payload are operational evidence in PostgreSQL. They are not a legal archive and they are not a retention-policy engine. Deleting original history is not automatic.
