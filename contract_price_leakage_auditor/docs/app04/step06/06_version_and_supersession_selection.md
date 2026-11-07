# 06 — Version and supersession selection

Only `state = approved` lines are searched. Draft, ready for review, rejected, and cancelled versions are ignored.

The search domain requires the line company, the version company, the exact partner, the exact variant, `effective_from <= pricing date`, and `valid_from` / `valid_to` covering that date.

A version with no `approved_at` returns `HISTORICAL_EVIDENCE_REVIEW_REQUIRED`. A version approved after the cutoff is skipped. An amendment whose `effective_from` is earlier than the calendar date of `approved_at` is skipped while `retroactivity_policy` is `not_authorized`. Initial versions have no source and may start in the past. The approval API still refuses a retroactive amendment, so the skip is defensive.

Inside one contract, the resolver reports:

- `cross_contract_supersession` when `supersedes_version_id` points at another contract.
- `supersession_evidence_missing` when `version_number` is greater than 1 and `supersedes_version_id` is empty.
- `circular_supersession` when the supersession chain repeats.
- `chronology_conflict` when an effective date is missing or duplicated.

The approval API already blocks those shapes. The resolver does not repair them by picking an id or a price.

Among the remaining versions of one contract, the winner is the greatest `effective_from` that has started. Version number, price, and database id are not the rule.

`authority_to` is the day before the next visible approved `effective_from`, or `valid_to` when no later version is visible at the cutoff. A version hidden by the cutoff does not shorten the earlier interval.

An expired window with no covering version is `NO_APPLICABLE_CONTRACT`. The latest expired price is not reused.

A future `effective_from` is outside the search. Approval today does not make it effective today.

Because retroactive approval is blocked, a later cutoff cannot restate a July price that was never approved. The prior approved version remains the authority. APP-014 does not forge `approved_at`.
