# Finding uniqueness and idempotency

## Canonical identity

```
c{company}|l{invoice line}|a{allocation or 0}|k{cutoff token}|sUNDERBILLING
```

The cutoff token is `none` when the run's `knowledge_cutoff` is empty. An explicit cutoff uses `fields.Datetime.to_string`. The audit run id, the revision, and the prices are not part of the key.

`UNIQUE(current_identity)` is a PostgreSQL constraint. `current_identity` is set only while `is_current` is true, so a superseded row can clear the key. PostgreSQL would otherwise allow several null keys.

An unchanged fingerprint updates `last_evaluated_at` and `run_id` on the same row. A changed fingerprint sets the old row to `is_current` false, clears its identity, marks it `superseded_by_reassessment`, and inserts the new current row.

`_release_other_findings` supersedes other current findings on the same company and invoice line that carry the same cutoff token. A different explicit cutoff is left in place. That is how an as-known result and a later restated result can both exist.

A repeated audit of unchanged evidence therefore has one current potential finding. Historical result rows stay append-only and can differ by run.

Compliant and overbilling outcomes do not insert a potential finding. If a potential finding already exists for that identity, it is superseded and a `no_longer_current` row with amount zero can hold the identity.

Review findings use status `review_required` and a blank amount. They are not included in the exposure sum. The exposure sum includes only current `potential` rows with a numeric amount, and only when those rows share one currency.

## Concurrency

`IDM12-T005` raises `psycopg2.IntegrityError` inside a savepoint when a second insert uses the same `current_identity`. `TransactionCase` is one database transaction. It is not two worker processes. Two-session proof was not executed.

A failed move uses a savepoint. The run is not marked `completed` when that move fails and nothing else succeeded. A retry uses the same identity and does not add a second current exposure.

## What was fixed before the green class run

The first class run kept a second current finding when a later audit crossed a clock second, because every run wrote `knowledge_cutoff` to `now()`. The identity then changed even though the user had not asked for a historical cutoff. The engine now leaves a blank cutoff blank and uses the token `none`. Explicit cutoffs still stay distinct. That fix is what the green class, full, upgrade, and fresh runs executed.
