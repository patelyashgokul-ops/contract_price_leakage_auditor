# Historical time semantics

Date: 2026-11-05.

Four times stay distinct.

| Time | Where it lives | What it decides |
| --- | --- | --- |
| Commercial effective date | Contract version `effective_from`, discount `effective_from` | Which price applies to a pricing date. |
| Approval time | Version `approved_at`, discount `approved_at` | Whether that term was known at a cutoff. |
| Knowledge cutoff | Reassessment `knowledge_cutoff`, audit run `knowledge_cutoff` | As-known-at evaluation. Stored in the identity as `k{token}`. |
| Evaluation time | Server `fields.Datetime.now()` on the event and the decision | When the user acted. It is not backdated to the commercial date. |

A blank cutoff is the token `none` and is the current reading. An explicit cutoff is a different identity. Accepting that identity logs `separate_interpretation_recorded` on the case and does not add the amount to the blank-cutoff exposure. The delta between those identities is blank and the class is `undetermined`.

An as-known cutoff excludes an approval whose `approved_at` is after the cutoff. The current reading, with a blank cutoff, can see a later approval that was valid when it was approved.

`cpla.customer.contract.version.action_approve` still raises `UserError` for a backdated amendment that lacks approval authority. DEV-14 does not catch that error and does not invent an approved version or an approval timestamp.

If the historical approval time is missing, the discount gate and the engine do not invent one. The request stays in evidence review when the required approval is not visible.

The mutable company policy is snapshotted onto the approved version. A later policy edit does not rewrite an older calculation row.
