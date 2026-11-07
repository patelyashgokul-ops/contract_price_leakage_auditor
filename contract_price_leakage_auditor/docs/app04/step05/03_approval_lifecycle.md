# 03 — Approval lifecycle

Date: 2026-10-28.

Approval state and commercial effectiveness are different fields. A scheduled job does not flip history.

## Header

Header states stay `draft`, `ready_for_review`, and `cancelled`. Public `write` cannot set `state`. Ready for review is not approval. Module upgrade does not approve existing headers.

`action_approve_initial` on the header asks `cpla.customer.contract.version.approve_initial` to create version 1. The button returns a window action, or `True` when several headers are selected. It does not return a recordset.

After an approved version exists, header cancel and reset-to-draft are refused. The header stays `ready_for_review`. `audit_authoritative` becomes true.

## Version approval states

`draft` → `ready_for_review` → `approved` / `rejected` / `cancelled`.

| State | Meaning |
| --- | --- |
| `draft` | Editable proposal. Not a price authority. |
| `ready_for_review` | Submitted. Commercial fields are frozen. Not a price authority. |
| `approved` | Formally approved snapshot. May be scheduled, current, superseded, or expired. |
| `rejected` | Not approved. Reason is required. Prior approved version is unchanged. |
| `cancelled` | Draft or review copy withdrawn. Its number is not reused. |

There is no reset-to-draft on a version. A rejected or approved version is not cancelled in place.

## Who may act

The approver is always `env.user`. Client user ids, timestamps, and state values are rejected.

| Role | Prepare draft / amendment | Submit | Reject | Approve initial snapshot | Approve a ready amendment |
| --- | --- | --- | --- | --- | --- |
| Contract User | Own contract | Own draft | No | No | No |
| Contract Manager | Company scope | Yes | Yes, with a reason | Yes, if not the owner and not the contract creator | Yes, if not owner, requester, or submitter |
| Finance Reviewer | No | No | No | No | No |
| Finance Manager | No line create | No | Yes, with a reason | No. This role cannot create the first lines. | Yes, if not owner, requester, or submitter |
| Internal Auditor | Read | No | No | No | No |
| Application Administrator | No contract access | No | No | No | No |
| Sales Pricing Reviewer | No access | No | No | No | No |
| Recovery Operator | No access | No | No | No | No |

This is not an approved amount matrix. No numeric ceiling exists. Amount-limited approval is unavailable. The constant `amount_threshold_policy = not_configured` records that gap. It does not authorize every amount.

Self-approval is prohibited. The message is `Self-approval is prohibited.` The blocked people are the contract owner, the requester, and the submitter. For the first version, the contract creator is also blocked. Initial approval therefore records the contract owner as requester and submitter, so the manager who approves is not stored as having submitted their own request.

`operationally_approved` on the company policy stays false. Approval stores the current same-company policy id and copies its candidate strings. That pointer is not operational pricing approval. `check_approval_reference` on the policy model does not grant financial authority.

## What approval checks

Before the approval savepoint, the server checks:

- caller may write the version and is an allowed approver
- state is ready for review, unless the row is already approved
- customer, currency, both validity dates, and effective date
- effective date inside validity
- amendment does not start before or end after the source validity
- current same-company policy
- at least one line and supporting evidence
- zero price, inactive currency, packaging unit, and non-default unit block approval
- negative price and an incompatible unit are rejected on save
- customer change and extra covered partners are blocked (DEC-03)
- source version is still the latest approved version
- no other approved version has the same effective date or a later effective date
- a retroactive amendment is blocked (see `06_retroactive_amendment_policy.md`)

An already approved row returns without a second snapshot, event, or supersession. That idempotent return still requires the caller to pass the approver check. A contract user does not get a success result.

A failure before or inside the savepoint leaves the version unapproved. Database integrity errors are not turned into a success message.

## Derived effective status

Computed only for `approved` versions. It is not stored and no cron writes it.

| Status | Rule |
| --- | --- |
| `scheduled` | `effective_from` is after the context calendar date. |
| `currently_effective` | `effective_from` is today or earlier, no later approved version has started, and `valid_to` is today or later. |
| `superseded` | A later approved version has an `effective_from` on or before today. |
| `expired` | No later version has started, and `valid_to` is before today. |

`historically_effective` is true for superseded and expired.

`authority_to` is the inclusive day before the next approved version's `effective_from`, or `valid_to` when no later approved version exists. The previous snapshot's own `effective_from`, approver, and checksum are not rewritten to record that later version.

Effective From is inclusive. `authority_to` and Valid To are inclusive. Approval timestamps stay datetimes. Commercial dates are dates. The code does not convert those dates through a timezone that would change the calendar day.

Same-day `effective_from` equal to the context date is not retroactive and is not scheduled.

## Buttons

Version form, enforced again on the server:

- Submit for Review
- Approve
- Reject
- Cancel Draft
- Create Amendment
- Compare Versions
- View History

The contract form has Approve Initial Version while the header is ready for review and `audit_authoritative` is false. Hiding a button is not the security control.

## Screens

Menus under Contracts, same visibility as Customer Pricing Contracts:

- Contract Versions (`menu_cpla_contract_versions`)
- Amendment Review (`menu_cpla_amendment_review`), domain `state = ready_for_review`

Version list columns include contract, reference, version number, company, customer, effective date, approval status, derived effective status, and approver.

Version form pages: Pricing Snapshot, Amendment Changes, Approval Details, Supporting Evidence, Supersession History, Internal Audit History.

Search filters include approval status, future-dated approved versions, historical effective status, effective date, and group-by customer, company, status, and approver.

Compare Versions opens the transient wizard. The lower version number is the baseline. The result says a unit delta is not recovered cash. No custom JavaScript.

History is `history_rows()` plus the event list. It uses `approved_at` and event `occurred_at`, not the row's later write date. It is not an executive leakage report.

Browser click-through was not run. View loading is covered by `get_view` in the automated suite.
