# Evidence review and checklists

## Checklist

`_seed_checklist` creates one row per question in `CHECKLIST`. Applicability is `potential`, `exception`, `both`, or `optional`.

Required for `potential_leakage`:

- `invoice_posted_eligible`
- `customer_identity`
- `duplicate_economic_issue_checked`
- `calculation_evidence_complete`
- `exposure_reconciled`
- `root_cause_explained`
- `ready_for_finance_review`

Required for every other case type:

- `exception_reason_visible`
- `amount_not_fabricated`
- `missing_evidence_disclosed`
- `root_cause_explained`

The other questions are stored and are not a submission gate. Answers start as `unanswered`. Nothing is pre-checked from the detector.

`action_answer_checklist` accepts `yes`, `no`, or `not_applicable`. Not applicable needs a note. The owner or a contract manager answers while the case is open. The line stores `answered_by_id` and `answered_at`. A direct write may change only `answer` and `note`, and it runs the same actor and state checks.

A required `no` blocks finance submission until `outstanding_qualification` is filled. A required `unanswered` always blocks.

## Source evidence

`_seed_evidence` adds received source rows for:

- The finding (`cpla.leakage.finding`).
- The latest `cpla.invoice.audit.result` for that finding and company, when one exists.
- The invoice id (`account.move`), when `move_id` is set.
- The contract version, when `version_id` is set.

The invoice label uses `account.move.name` only when the acting user `has_access('read')` on that move. Contract managers do not have journal-entry read. The row still stores `source_model` `account.move` and `source_res_id`. It does not copy the invoice PDF.

One extra investigation row is created with status `not_requested` and no source record. Received is not verified. Verification is `action_verify_evidence` with a note. Reject and request need a reason and open the evidence wizard from the line buttons.

Statuses: `not_requested`, `requested`, `received`, `verified`, `rejected`, `not_applicable`.

## Attachments

`IrAttachmentCaseGuard` blocks, for `res_model` in `cpla.leakage.case` and `cpla.leakage.case.evidence`:

- `public` on create or write.
- `access_token` on create or write.
- `generate_access_token`.
- `unlink`, except during module uninstall.

Read still follows the related record. A company B user who cannot read the case cannot read the attachment. The class test denies `datas` for the other company manager.

Chatter `message_post` forces subtype `mail.mt_note` and drops partner ids that fail `_partner_may_follow`. The customer partner is rejected. An internal auditor may follow and may not post. A contract user may post an internal note. The body is `str(self.env._(...))` for the state and submission messages.

## What is not proof

A file on the case is not a contract approval. A verified status means the investigator marked that line reviewed. It does not approve a price and it does not validate leakage.
