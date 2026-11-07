# Recovery billing lifecycle

States on `cpla.recovery.billing`: draft, handoff_verified, accounting_review, document_prepared, draft_document_created, ready_to_post, posted, partially_reversed, fully_reversed, blocked, cancelled, superseded.

Open reserve is draft through ready_to_post. Current posted is posted and partially_reversed. Released is cancelled, superseded, and fully_reversed.

## Draft is not posted

`posted_principal_exact` stays `0` until `action_post` succeeds. Open-reserve principal is reserved so a second overlapping slice raises `BILLING_EXCEEDS_AUTHORIZED`. It is not included in posted principal or in unbilled reduction. A draft of 8000 beside a posted 12000 leaves posted principal 12000 and authorized unbilled 8000.

## Posted

Posting records `posted_by_id`, `posted_at`, `posted_on`, the untaxed principal, tax, and gross. The original leakage invoice lines are not written. Accounting lock dates are the native `action_post` check. A lock-date `UserError` leaves the draft unposted. This addon does not catch that error and post anyway.

## Reversal

A supported credit whose principal covers the posted amount sets `fully_reversed`, marks billing lines `counts_current` false, and keeps `posted_principal_exact` as historical evidence. Current posted sums skip that billing, so the authorized amount can be billed again. A smaller supported credit sets `partially_reversed`. Net billed principal stays the current posted principal. The partial credit reduces outstanding and does not increase unbilled.

## Cancel

`action_cancel` before posting releases the slice and unlinks a draft move. It does not cancel a posted move.

## Source change after posting

A later stale source does not rewrite or delete the posted invoice. `billing_position()` adds `ACCOUNTING_IMPACT_REVIEW_REQUIRED` and `RECOVERY_SOURCE_STALE`. A new post of a stale draft is still blocked by `_assert_still_fresh`. No refund is invented for cash already collected.

## Superseded

Superseded and cancelled rows stay in the database and are excluded from the current identity unique index.
