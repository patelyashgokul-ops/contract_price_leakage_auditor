# 04 — Amendment and supersession

Date: 2026-10-28.

## Starting an amendment

`create_amendment` copies an approved version into a new draft. The source row is not edited.

The copy keeps:

- parent contract, company, customer, currency, and policy pointer
- validity dates and description
- source version id
- pricing lines, with `origin_line_id`
- evidence links, with `origin_evidence_id` and the prior checksum

The copy does not keep:

- `approved` state
- approver, approval timestamp, or approval reference
- `supersedes_version_id`
- the previous submitter as the new submitter

The requester is the authenticated user. The default effective date is the source effective date when that date is still today or later. Otherwise it is the next calendar day, and it is not placed after Valid To. The user may set another date before submit. The server validates it.

A Contract User may create an amendment on a contract they own. A Contract Manager may create one in the company. Creating an amendment does not approve it.

There is no rebase operation. A stale draft is cancelled, and a new amendment is created from the latest approved version. One user's draft is not overwritten with another version.

## Change scope on a draft

Editable while the version is `draft`, by a Contract User:

- product lines: price, product, unit, description
- add a line or remove a draft line
- currency, as a new explicit snapshot, with no conversion
- validity dates and effective date, inside the rules below
- customer and covered partners, as a proposal that approval will block while DEC-03 is open
- policy pointer, amendment reason, and external amendment reference
- evidence link or a new file

Not editable through public write at any time: state, version number, reference, contract, company, source version, supersedes, requester, submitter, approver, approval timestamp, approval reference, snapshot checksum, and the frozen policy characters.

After submit, only a rejection reason, an approval note, or a cancel reason may be written, and only by a Contract Manager or Finance Manager.

## Date rules

Valid From and Valid To are required before review. Valid To earlier than Valid From is a validation error. The dates are not swapped.

The effective date must sit inside that validity range. Effective From is inclusive.

An amendment cannot set Valid From earlier than the source, or Valid To later than the source. Extending the overall contract is not authorized in this phase.

## Stale drafts

On submit and on approve, the source must still be the latest approved version of the contract, ordered by version number.

If a newer version was approved while the draft was open, the message starts with `Stale amendment draft`. The draft is not approved and its lines are not replaced. The user cancels it and starts again from the latest approved version.

## Supersession

Supersession is stored on the new version at approval: `supersedes_version_id`. The previous version's snapshot fields stay as they were. `superseded_by_ids` is the inverse. It is not a rewrite of the old row.

An event `supersession_recorded` is written on the new version in the same savepoint as the approval.

The relationship records:

- previous approved version
- new approved version
- effective date on the new version
- approval event and approver
- amendment reason
- contract and company scope
- historical event rows

A version cannot supersede itself, a later number, another contract, or another company. A walk of `supersedes_version_id` that returns to a seen id is rejected as circular.

## Conflicts

These are rejected. The server does not choose the lowest price, the highest price, the latest edit, or the highest database id.

- Another approved version of the same contract already uses the same `effective_from`.
- An approved version already has a later `effective_from` than the candidate. The candidate cannot insert an earlier authority.
- Parent contract or company does not match.
- Source version is not approved, or is no longer the latest.
- The supersession chain would be circular.

The conflict text includes `Conflicting supersession` and `No price was selected.`

Different products are not given separate approved chronologies in this phase. The snapshot is one version for the contract. A removed or added product is a line difference inside that version, not a second authority calendar.

## Future-dated approval

A manager may approve a version whose `effective_from` is after today. The state is `approved`. The derived status is `scheduled`. The earlier version stays `currently_effective` until that later date is reached by the calendar comparison. Nothing reprices orders, invoices, or pricelists, and nothing waits on a cron to become approved.

## Activation

Approval is not the same as effectiveness. A version can be approved and scheduled, approved and current, historically superseded, or expired by `valid_to`. Only `approved` versions qualify as pricing authority. Draft, rejected, and cancelled versions do not.

Becoming effective does not rewrite invoices, reprice posted transactions, create leakage findings, generate debit notes, create recovery claims, or change accounting entries.
