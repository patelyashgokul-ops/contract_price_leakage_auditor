# DEV-14 reassessment workflow

Date: 2026-11-05. Version: `19.0.1.12.0`. A completed calculation is not acceptance. Later workflow, rejection, and verification states are in `05_reassessment_workflow.md`.

## States

| State | Meaning |
| --- | --- |
| `requested` | A contract manager recorded a trigger, a source, and a reason. |
| `under_evaluation` | A finance manager started the DEV-12 preview. |
| `proposed_revision_ready` | The preview returned an authoritative amount. The current finding is unchanged. |
| `evidence_review_required` | A required fact is missing or conflicts. No authoritative amount is stored. |
| `accepted` | A different finance manager accepted the proposal. The engine stored the successor inside that decision. |
| `rejected` | A finance reviewer or finance manager rejected the proposal. The proposal fields stay. |
| `blocked` | The digest, the fingerprint, or another gate failed. No successor was kept. |
| `failed` | The calculation raised an unexpected technical error. The log records the reassessment id only. No amount was accepted. |
| `cancelled` | The contract manager cancelled an open request. |

Evaluate is allowed from `requested`, `under_evaluation`, `proposed_revision_ready`, `evidence_review_required`, `blocked`, and `failed`. Accept is allowed only from `proposed_revision_ready`. Reject is allowed from `proposed_revision_ready` and `evidence_review_required`. Cancel is allowed from the evaluable states.

## Who may act

| Action | Who | Server check |
| --- | --- | --- |
| Request | Contract manager | `_check_requester`. The finding must be current. |
| Cancel | Contract manager | Same check, plus a reason. |
| Evaluate | Finance manager who can run an audit and map invoice sources | `_check_finance_manager`. |
| Accept | That same finance manager, and not the requester | `requested_by_id` must differ from the current user. Superuser is not exempt from that rule. |
| Reject | Finance reviewer or finance manager | `_check_finance_reviewer`, plus a reason. |
| Verify digest | Any user who can read the row | Recomputes. Does not accept. |

Context flags are not authorization. The UI Accept, Reject, and Cancel buttons open the wizard because those methods require a reason. Evaluate and Verify Digest are direct buttons.

A contract manager cannot accept. A finance reviewer cannot evaluate or accept. A user who holds both contract manager and finance manager cannot accept a request they created.

## Request identity

Reference sequence: `CPL-REASS/%(year)s/`, padding 5, standard implementation, no company on the sequence. If the sequence is missing, the request raises `UserError`. It does not invent a reference.

An open row is reused when the finding, trigger, source model, source id, and company match a state in `requested`, `under_evaluation`, `proposed_revision_ready`, `evidence_review_required`, `blocked`, or `failed`. The partial unique index covers the first five of those states. `failed` is reused by search and is not in that index. A second concurrent insert of a `failed` row was not separately tested. Accepted, rejected, and cancelled rows are not reused.

A new request after acceptance is refused while the current finding fingerprint still equals the accepted proposal fingerprint.

Credit and replacement triggers require `account.move` and a positive id. Other triggers default to the finding itself when no source is passed. `source_res_id` is not required at the field level, because Odoo treats integer `0` as empty.

## Triggers

Stored change class at creation:

| Trigger | Class |
| --- | --- |
| Verified quantity return, price-adjustment credit, full reversal, replacement invoice, quantity-tier requalification | `financially_material` |
| Approved retroactive amendment, approved discount correction, contract precedence, historical FX, tax basis, UoM conversion | `authority_material` |
| Invoice source-mapping correction, duplicate-finding correction | `source_mapping_material` |
| Manual authorized review, other documented trigger | `unknown_impact` |

`evidence_material` and `non_material` exist on the selection. No trigger writes them. Unrelated ORM writes are not hooked. One request does not rescan every invoice.

A trigger is not an automatic increase or decrease. The engine amount decides the delta. A non-authoritative engine result stays in evidence review.

## Preview and accept

Preview builds an unsaved run with `new()`, maps the named credit when the trigger needs it, and prices the current allocation. It does not call `_upsert`, `_audit_credit`, or `action_run`. Finding and result counts stay the same during preview.

Accept previews again. If the fresh fingerprint, identity, amount, or authority differs from the stored proposal, the row becomes `blocked` and the stored proposal is not refreshed. Finance must evaluate again. Accept then stores through `_apply` only when the digest still matches and the evidence gaps are empty.

## Delta

`delta_exact` is proposed exposure minus the previously accepted exposure only when the identity matches, the currency matches, and both amounts are decimals. Otherwise `delta_exact` is blank and `delta_class` is `undetermined`. The explanation says the amounts were not subtracted.

| Class | Rule |
| --- | --- |
| `exposure_eliminated` | Proposed is 0 and the previous amount is greater than 0, same identity and currency. |
| `exposure_increased` | Positive comparable delta. |
| `exposure_decreased` | Negative comparable delta. |
| `amount_unchanged_evidence_changed` | Delta is 0 and the fingerprint changed. |
| `no_material_change` | Delta is 0 and the fingerprint matches. |
| `undetermined` | Missing amount, different identity, or different currency. |

`is_recovered_cash` and `is_writeoff` stay false. Acceptance refuses a row if either flag is true.

## Case effect

Same identity: each current membership of the original finding gets `_mark_source_revision`. The case state stays. `reviewed_exposure_exact` stays. `current_potential_exposure_exact` follows the current finding and goes blank when that finding is no longer current. `source_reassessment_required` becomes true when the membership is stale.

Different identity: the case logs `separate_interpretation_recorded`. The new finding is not added. `source_reassessment_required` is not set for that reason. The reviewed amount stays.

If the case is `ready_for_finance_review` and the same-identity revision is stale, `finance_package_stale` becomes true. The submission row stays. Submit already refuses while `source_reassessment_required` is true. A new submission clears `finance_package_stale`. `action_accept_current_source` still refuses `ready_for_finance_review`. Finance must return the case before an investigator can retarget it.

An investigator retarget copies the successor finding and its amount. That copy is not this acceptance. A cleared identity with no current successor cannot be retargeted. The zero evidence then stays on the audit-result row. DEV-15 must not treat that missing finding as permission to invent a finance-validated zero.
