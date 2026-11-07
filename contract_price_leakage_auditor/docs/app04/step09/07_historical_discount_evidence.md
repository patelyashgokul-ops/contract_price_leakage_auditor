# Historical discount evidence

An approved concession stays reconstructable from the version snapshot and, for a discretionary grant, from `snapshot_json` and `limit_snapshot_json` written at approval. Later edits of the approval matrix do not rewrite those JSON values. Evaluation of an already approved override uses the granted snapshot.

## What is frozen

On the version: stacking mode, tier interaction, limit basis, limit amounts, retroactive discount authority, concession rows, and unit factors. The version checksum includes that signature.

On an approval: proposed concession, approved price, baseline, currency, unit, quantity, sales references, dates, exclusivity, rank, sequence, partner, product, version, the limit basis and amounts, whether the grant was retroactive, the approver, and `approved_at`.

On an event: event type, actor = `env.user`, server timestamp, and parent company. A second `approved` event for the same request is refused. A forged event whose actor or parent state does not match is refused. Write and unlink of an event are refused.

## Cutoff

`knowledge_cutoff` hides a version, a concession, or an approval whose `approved_at` is after the cutoff. The executed retroactive case approved a 5 percent concession effective five days earlier, after the cutoff had been taken. As-known evaluation returned the base 1,200 with `discount_applied` false. Evaluation without that cutoff returned 1,140. `retroactive_granted` was true. The version `retroactivity_policy` remained `not_authorized`.

A cutoff taken before the version itself was approved returns discount status `not_applicable` and reason `version_not_known_at_cutoff`, with no adjusted price. The financial layer reports the historical review; the discount layer does not invent a price.

## Revocation and supersession

Revocation is additional fields and one `revoked` event. The original percent remains. A prospective revocation leaves earlier pricing dates authorized. Retroactive revocation requires `retroactive_discount_authority` = `explicitly_allowed`. The user who approved the version cannot revoke the concession.

A request against a superseded version is not approved. The executed case used the initial snapshot, whose effective date is the contract start, and a later amendment effective today. The initial version’s effective status became `superseded`. `action_approve` raised and left the request submitted, with no approver and no approved event.

An amendment does not rewrite the previous concession. The executed case kept 5 percent on the source and 9 percent on the amendment. The amendment effective date is the next day, because an approved version already occupied today. Historical evaluation of the source on the previous day returned 1,140. Evaluation of the amendment on its effective date returned 1,092.

## Native prices

A current `product.pricelist` item at 50 percent off the same variant did not change the contract evaluation. The adjusted price stayed the contract base 1,200 and `discount_applied` stayed false. The pricelist was not stored as approval evidence.

## Posted documents

No posted invoice is rewritten. No historical leakage finding is created or reassessed. Reassessment of an earlier finding is DEV-14.
