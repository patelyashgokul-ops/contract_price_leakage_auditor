# Finance workflow and states

`state` is the workflow. `decision_type` is the financial conclusion. They are not the same field.

## States

`draft`, `submitted`, `under_finance_review`, `additional_evidence_required`, `proposed_decision`, `pending_approval`, `partially_approved`, `approved`, `rejected`, `stale_source_review_required`, `superseded`.

Open states, which block a second package for the same case, are draft through pending approval, plus `stale_source_review_required`.

## Path

1. `prepare_from_case` creates a draft. Each line starts unresolved for the full accepted potential. Proposed and approved validated amounts are `0`.
2. `action_submit` requires a ready case, an accepted revision, one currency, and one current approved policy. It stores the requester and the server time. It does not approve.
3. `action_start_review` sets `under_finance_review` and the reviewer.
4. `action_request_evidence` calls the case `action_return_for_rework` and sets `additional_evidence_required`. The note is stored.
5. `action_propose` writes proposed amounts only. Approved amounts stay `0`.
6. `action_request_approval` resolves the required levels. A line coded `ADDITIONAL_EVIDENCE_REQUIRED` cannot move to approval. A wholly unresolved package cannot be finalized.
7. `action_approve` records one level. If a later level is required, the state stays `pending_approval` and validated stays `0`. The last level copies the proposal into the approved amounts.
8. `action_deny_level` sets `rejected` and `level_denied`. Validated stays `0`. This is not a full financial rejection of the potential.
9. `action_retire_stale_package` is only from `stale_source_review_required`. It sets `superseded` and leaves validated at `0`.
10. `action_create_correction` opens a new draft bound to the current findings. The old decision stays current until the new one is finalized, then the old row becomes `superseded`.

A repeated successful approve by the same user returns the existing decision and does not add another approved event.

## Final mapping

After the last approval level:

- Validated equals potential, rejected `0`, unresolved `0`: `approved` / `full_validation`.
- Validated greater than `0` and rejected or unresolved greater than `0`: `partially_approved` / `partial_validation`.
- Validated `0`, rejected equals potential, unresolved `0`: `rejected` / `full_rejection`.

Full rejection does not require `partial_validation_allowed`. It does not erase the finding potential.
