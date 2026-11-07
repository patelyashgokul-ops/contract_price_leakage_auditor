# DEV-14 handoff

DEV-14 is not implemented. This file is the evidence and reassessment contract DEV-14 can read. Do not start that phase from this step.

## Case model

`cpla.leakage.case`.

## Case-to-finding relationship

`cpla.leakage.case.membership`. Many findings can sit on one case. A finding has at most one row with `is_current` true. Historical rows stay, with `removed_at` set.

`cpla.leakage.finding.current_case_id` is computed from the current membership. It is not a stored owner column on the finding.

## Canonical active membership

The current membership is the row with `is_current` true. Operational close does not clear it. Split, merge, and accept-source do. The partial unique index is `(finding_id) WHERE is_current IS TRUE`.

The finding's own current economic key remains `current_identity`:

`c{company}|l{invoice line}|a{allocation or 0}|k{cutoff token}|sUNDERBILLING`

DEV-13 does not allocate that key. The audit engine does.

## Grouping, merge, and split

Default is one current finding, one case. Explicit bases: `same_sales_order`, `same_contract_version`, `same_invoice`, `explicit_same_issue`. All require one company, one customer, one case type, and one comparable currency. Customer alone is refused.

Merge supersedes the source case. It does not delete it. Split must leave one finding behind.

## Workflow states

`new`, `assigned`, `under_investigation`, `evidence_pending`, `ready_for_finance_review`, `returned_for_rework`, `closed_with_reason`.

`ready_for_finance_review` is not finance validation. `closed_with_reason` is not recovery.

## Investigator access

Eligible owner: active internal user with `group_contract_user` or `group_contract_manager`, and the case company in `company_ids`.

Contract user ACL on membership is read, write, and create, no unlink, so accept-source can retire and insert rows without `sudo()`. Direct create and write methods still raise.

## Evidence checklist

Seeded from `CHECKLIST` in `models/leakage_case.py`. Potential cases require invoice eligibility, customer identity, duplicate check, calculation evidence, exposure reconciliation, root cause, and finance-ready. Exception cases require a visible reason, a blank amount, disclosed missing evidence, and a root cause. Other questions are optional.

## Source evidence references

Evidence lines point at `cpla.leakage.finding`, `cpla.invoice.audit.result`, `account.move` id, and `cpla.customer.contract.version` when those records exist. They do not copy invoice binaries. Membership stores `reviewed_identity`, `reviewed_fingerprint`, `reviewed_revision`, `reviewed_status`, and `reviewed_exposure_exact`.

## History model

`cpla.leakage.case.event`. Append-only through the ORM. Not a cryptographic archive.

## Source finding revision strategy

`action_refresh_source_status` sets `source_reassessment_required` and blanks the current display when the linked finding is stale or a successor with the same `current_identity` exists. `reviewed_exposure_exact` stays.

`action_accept_current_source` retargets the membership onto that successor and copies the successor amount text. It does not run the audit engine.

DEV-14 should produce the successor finding, or an equivalent current row, through the DEV-12 engine. DEV-13 will then flag and accept it. DEV-14 should not add a second calculator inside the case write method.

## Current potential exposure

Sum of `potential_leakage_exact` on current memberships whose finding is still `potential` with a decimal amount, one currency, via `_arithmetic` / `_text`. Blank stays blank. Mixed currency blanks the display. Historical revisions are not in the current membership.

## Finance submission snapshot

`cpla.leakage.case.submission`, including `finding_snapshot` JSON. Return fills return fields and keeps the JSON. A later submit inserts a new row.

## Missing evidence and reassessment statuses

Evidence line statuses: `not_requested`, `requested`, `received`, `verified`, `rejected`, `not_applicable`.

Case flag: `source_reassessment_required`.

Exception queues are on the case. See `08_exception_queues.md`. `discount_approval_review` and `security_or_company_exception` are unused by the detector map.

## Multi-company

Global rule `[('company_id', 'in', company_ids)]` on the case, membership, event, checklist, evidence, submission, and wizard. No cross-company grouping. Attachment read follows the case.

## Tests already executed

Class `TestDev13LeakageCase`: 0 failed, 0 errors of 20 tests, database `cpla_dev13_20261105`, log `cpla_dev13_class4.log`, 2026-11-05. Two-worker concurrency: `NOT_EXECUTED`.

Full tag on `cpla_dev13_20261105`: 0 failed, 0 errors of 898 tests, log `cpla_dev13_full.log`, exit `EXIT:0`.

Upgrade `-u` of `cpla_dev12_20261028` from `19.0.1.10.0`: 0 failed, 0 errors of 898 tests, log `cpla_dev13_upgrade.log`.

Fresh `-i` of `cpla_dev13_fresh_20261105`: 0 failed, 0 errors of 898 tests, log `cpla_dev13_fresh.log`.

Commands and the stats lines are in `13_automated_test_results.md` and `14_installation_and_regression.md`.

## Open business decisions

- Grouping beyond the four explicit bases is not approved.
- No priority amount thresholds.
- No SLA day counts.
- License remains `BLOCKER_LICENSE_DECISION_REQUIRED` (`Other proprietary` in the manifest).
- Contract users cannot read `account.move`. Invoice navigation from the case is denied for them.
- Finance validation, recovery, waivers, customer claims, and escalation crons are later phases.

## DEV-14 requirements

1. Reassess a posted invoice only through the existing audit engine and finding identity.
2. Supersede the previous current finding instead of editing its amount in place.
3. Leave the case flag and the reviewed snapshot alone until an investigator accepts the successor.
4. Do not sum historical revisions into the case.
5. Do not mark the case finance-validated.
6. Preserve company isolation on any new evidence row.
