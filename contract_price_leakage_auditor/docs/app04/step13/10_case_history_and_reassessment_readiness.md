# History and reassessment readiness

## Event log

`cpla.leakage.case.event` is the material history. Chatter messages are additional and are not the authority for exposure or state.

Event types: `created`, `finding_linked`, `finding_removed`, `assigned`, `owner_changed`, `priority_changed`, `severity_changed`, `evidence_requested`, `evidence_verified`, `evidence_rejected`, `state_changed`, `root_cause_recorded`, `outcome_recorded`, `source_revision_detected`, `source_revision_accepted`, `submitted_to_finance`, `returned_for_rework`, `closed`, `reopened`, `merged`, `split`, `participant_added`.

The actor is `env.user`. The time is `fields.Datetime.now()`. Client values for actor and time are not accepted. Public write and unlink raise `UserError`. This is application enforcement. It is not a cryptographic archive. A database superuser outside the ORM can still change rows.

`case_revision` increments on events that pass `bump` true. State-change companions of an action that already logged use `bump` false so one action does not count twice.

## Source revision

At link time the membership stores `reviewed_identity`, `reviewed_fingerprint`, `reviewed_revision`, `reviewed_status`, and `reviewed_exposure_exact`.

`_membership_stale` is true when the finding's fingerprint, amount text, calculation revision, status, or `is_current` no longer matches that snapshot.

`_successor` searches a different current finding with the same `current_identity`, same company, and `is_current` true.

`action_refresh_source_status` recomputes exposure. If the membership is stale or a successor exists, `source_reassessment_required` is set and the current display amount is blank when the old finding is no longer a current potential amount. `reviewed_exposure_exact` is left as it was. The method does not write the finding and does not invent zero.

`action_accept_current_source` requires a reason, an open case, and a successor. It retires the old membership (`is_current` false, flushed before the insert), links the successor, recomputes exposure, and logs `source_revision_accepted` with the previous reviewed amount. The old finding row remains.

Refresh and accept do not run the DEV-12 engine and do not recompute price times quantity.

## What DEV-14 still has to do

This step does not rebuild audit results, does not choose a new contract version, and does not apply a return quantity. It only notices that the current finding identity or fingerprint moved, and it can point the case at a successor the audit engine already stored. A full reassessment engine remains DEV-14.
