# Commercial waiver policy

`cpla.recovery.waiver` records a decision not to pursue part of a current finance-validated amount. The reason is one of: relationship preservation, small balance, contractual settlement, dispute compromise, strategic account, management concession, cost of pursuit, or other documented reason. The reason text is required. A waiver is not stored as a chatter comment.

A normal waiver consumes unallocated validated amount. A settlement concession (`reduces_recovery`) adds waiver and subtracts the current recovery target in one balance move. The original waiver row stays. The request line `approved_recovery_exact` stays the original authorization. The current target is `current_recovery_exact` and the balance. The event `recovery_target_revised` stores the old and new texts.

## Lifecycle

States: draft, submitted, pending_approval, approved, rejected, withdrawn, superseded, stale_source. The first level of a multi-level waiver logs `waiver_level_approved` and does not finalize. The last level logs `waiver_approved` and writes the approved amount. A retry by the same approver after `waiver_approved` does not move the balance again.

An approved waiver cannot be edited through public `write`. A correction is a new waiver that supersedes the previous current row. The original event remains.

## What a waiver is not

A finance rejection is not a waiver. `rejected_exact` on the finance validation is excluded from the commercial balance. An unapproved waiver does not reduce the recovery target. An approved waiver does not create an accounting write-off, a credit note, or a payment. No waiver ceiling is seeded. An empty `maximum_exact` on a level that has a ceiling blocks policy approval.
