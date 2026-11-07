# Snapshot schema and integrity

Date: 2026-11-05. Schema version `dev14.2`. Engine `dev12.1`.

## Canonical payload

`_payload` builds a dict. `_canonical` serializes it with `json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True)` and stores the SHA-256 hex digest. The stored `schema_version` is `SNAPSHOT_SCHEMA` (`dev14.2`).

Payload keys include `schema`, `engine`, `company_id`, `finding_id`, `trigger`, `source_model`, `source_res_id`, `original_identity`, `original_fingerprint`, `original_exposure`, `original_quantity`, `original_adjusted`, `original_actual`, `original_revision`, `cutoff`, `proposed_identity`, `proposed_fingerprint`, `classification`, `version_id`, `pricing_date`, `adjusted`, `actual`, `eligible`, `exposure`, `currency_id`, `delta`, `delta_class`, `credit_class`, `authoritative`, `is_recovered_cash`, and `is_writeoff`.

Empty numeric text becomes JSON `null` through `_none`. Amounts stay decimal text. The company currency is not renamed to INR.

`dev14.1` payloads did not include `original_quantity`, `original_adjusted`, or `original_actual`. New requests use `dev14.2`. A digest is recomputed from the current `_payload`, so a `dev14.2` row verifies against `dev14.2`.

## What is protected

- Reassessment and event forms are `create="false" edit="false" delete="false"`.
- Event `create`, `write`, and `unlink` raise for ordinary callers. The model writes events with `models.Model.create`.
- Finding subclass `write` allows only `is_current`, `current_identity`, and `finding_status` for the supersede path. Financial text on the finding is not in that allow-list.
- `models.Model.write` and `models.Model.create` are used where the subclass override must not block the engine. They still pass access checks. They are not `sudo()`.
- The addon Python has no `sudo(` and no `.execute(`.
- A digest mismatch sets `digest_mismatch` and `verification_outcome` `mismatch`. Acceptance of a mismatched or empty digest moves the request to `blocked` inside the acceptance attempt. It does not become `accepted`.

The digest detects a changed stored proposal. It is not a legal archive and it does not prove the upstream invoice or contract file is unchanged.

## Acceptance and the digest

`action_accept` calls `action_verify_digest` and recomputes the outcome. If the fresh fingerprint, exposure, or identity differs from the stored proposal, the request becomes `blocked` with the source-changed reason. The previous current finding is left in place.
