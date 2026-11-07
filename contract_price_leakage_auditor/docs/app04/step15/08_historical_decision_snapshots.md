# Historical decision snapshots

An approval event stores the actor from `env.user`, `acted_at` from the server, the policy reference, the decision, the amount, the currency, the reason, the source fingerprint, and `evidence_snapshot` JSON.

Ordinary users cannot write those fields. Finance groups have no write or unlink access on `cpla.finance.validation.approval`. The model `write` still raises `HISTORICAL_APPROVAL_PROTECTED` if access rules are bypassed. Header and line `write` do the same after their own access check. No group has unlink on the header. Uninstall is the only `unlink` path that calls `super`.

A correction is a new validation row. The original keeps its validated amount, approver, time, policy, and reason. It becomes `superseded` and `is_current` false only when the new row is finalized. A second current approved amount for the same case is rejected by the partial unique index.

`current_validated_amount` ignores superseded, stale, draft, and fully rejected rows. A denied level stays `is_current` so it occupies the current-decision slot, and its lines do not count as validated.

This is application and access-rule protection. It is not a claim that the database row is legally immutable.
