# Retroactive contract and discount rules

Date: 2026-11-05.

## Contract amendments

A retroactive price is an approved contract version whose commercial `effective_from` can be earlier than its approval, only when `action_approve` allows it. DEV-14 does not bypass that method. A backdated amendment without that authority still raises `UserError` and stays unapproved.

For an as-known cutoff, a version approved after the cutoff is not the price at that cutoff. The original audit result for the earlier version stays. The later version can apply to a current reading whose cutoff is blank or falls after `approved_at`.

GOLD-REA-004 shape: V1 approved price 1000, V2 retroactive 1200, invoice 1000, quantity 100. The current approved restatement is 20000 when the retroactive version is a valid approved version at the evaluation cutoff. The original as-known result is a different identity when its cutoff excludes V2. Those two amounts are not added.

## Discount corrections

`approved_discount_correction` does not treat a missing approval as a new price. The gate requires an approved `cpla.discount.approval` for the same company, customer, and product. If `knowledge_cutoff` is set, `approved_at` must be on or before the cutoff. Otherwise the request is `evidence_review_required` and cannot be accepted.

When an approval is visible, the gate returns no review reason and the DEV-12 evaluator prices the line. The evaluator already skips approvals after the cutoff and does not grant retroactive effect unless that approval's own retroactive flag allows it. DEV-14 does not invent a zero. If the engine returns a non-authoritative outcome, the request stays in review.

A revoked or later-superseded approval does not delete the earlier approval history. The original audit result row remains.

## FX and tax

No verified replacement rate or tax evidence is supplied by these triggers. The request stays in review. No corrected amount is stored as authoritative. Acceptance raises `UserError`.
