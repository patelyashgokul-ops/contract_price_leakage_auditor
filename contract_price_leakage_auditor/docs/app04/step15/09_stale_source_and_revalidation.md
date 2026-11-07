# Stale source and revalidation

When the DEV-12 upsert supersedes a current finding, it calls `cpla.finance.validation._flag_source_change` for that finding. The same-fingerprint path that only refreshes `last_evaluated` does not flag finance rows.

For an open package, the state becomes `stale_source_review_required`, `stale_source` is true, and `is_current` is false. `action_approve` then fails because the state is no longer `pending_approval`. `action_retire_stale_package` marks that package `superseded` and leaves validated at `0`.

Renewal uses the existing case methods. A finance user who is not the case submitter calls `action_return_for_rework`. The investigator calls `action_accept_current_source`, starts the case, and submits again. A new validation is prepared against the successor finding. The old package is not reused.

If the package was already approved, the hook keeps the state and the validated amount, sets `stale_source` true and `is_current` false, and clears `counts_current` on the lines. `decision_payload()['current']` becomes false. `approved_amount` still returns the historical validated amount. `recovery_authority` stays false. No accounting document is rewritten.

A later approval of the old package is not created. Retrying approve as the same user on an already final row returns before a second event is written.
