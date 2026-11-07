# DEV-14 progress

Date: 2026-11-05. Version: `19.0.1.12.0`. This file is the sections 1–36 progress note. The later task table is `16_dev14_progress.md`. Business acceptance stays `PENDING`. Release stays `NO-GO`. License stays `BLOCKER_LICENSE_DECISION_REQUIRED`. Finance validation was not started.

Potential leakage is not finance-validated, billed, or collected. Accepting a reassessment is not finance validation. A lower amount is not recovered cash and it is not a write-off. The two-worker result is in `15_performance_and_concurrency.md`, not in this sections 1–36 note. The schema used by the later tests is `dev14.2`.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| Review DEV-12 and DEV-13 before new models | COMPLETED | Engine, finding identity, and case membership were reused. |
| Reassessment record | COMPLETED | `cpla.leakage.reassessment`. No `cpla.audit.*` model. |
| Append-only event | COMPLETED | `cpla.leakage.reassessment.event`. Public create raises `UserError`. |
| Reason wizard | COMPLETED | `cpla.leakage.reassessment.wizard`. |
| Sequence | COMPLETED | `CPL-REASS/%(year)s/`, padding 5, `noupdate`. |
| Snapshot schema | COMPLETED | `dev14.1`. Engine stays `dev12.1`. |
| Digest | COMPLETED | SHA-256 of canonical JSON. Original digest is not replaced. |
| Preview without storing a finding | COMPLETED | `test_rev14_t001` finding and result counts stay through evaluate. |
| Accept through the engine | COMPLETED | `_audit_mapping` inside one savepoint. `action_run` and `action_reassess` are not called. |
| Quantity return 5000 to 4000 | COMPLETED | `test_rev14_t001`. Original result stays `5000`. Exposure is not `9000`. |
| Full reversal to zero | COMPLETED | `test_rev14_t007`. No current finding remains. Successor result is `0`. |
| Separate cutoff | COMPLETED | `test_rev14_t008`. Amounts are not subtracted. Backdated approval still raises. |
| Amount-only credit | COMPLETED | `test_rev14_t006`. No invented returned quantity. |
| Replacement without reversal | COMPLETED | `test_rev14_t010`. Exposure is not forced to zero. |
| Case reviewed amount | COMPLETED | `test_rev14_t003`. Engine acceptance does not copy the new amount onto the case. |
| Finance package staleness | COMPLETED | `test_rev14_t004`. Submission row stays. |
| Self-approval | COMPLETED | `test_rev14_t005`. |
| Reviewer boundary | COMPLETED | `test_rev14_t009`. |
| Company rule | COMPLETED | Ungrouped `company_ids` rule. Company B cannot read company A. |
| Old reread button | LEFT IN PLACE | `test_rev14_t011` asserts `action_reassess` remains. It can still move a finding without this decision. |
| Class tests | COMPLETED | Rerun 0 failed of 111. The first class run was 1 failed of 111. |
| Full, upgrade, and fresh | COMPLETED | Each 0 failed of 909. See `05_automated_test_results.md`. |
| Two-worker race | NOT_EXECUTED | No second worker was started. |
| Documentation | COMPLETED | This directory, 7 files. |
| DEV-15 | NOT_STARTED | `07_dev15_handoff.md` only. |

## Traceability

| Prompt question | Result in this build |
| --- | --- |
| Original calculation | The first `cpla.invoice.audit.result` row stays. |
| Invoice, contract, and approval evidence | The proposal stores version, prices, quantity, cutoff, fingerprint, and credit class from the engine. |
| Knowledge at the original cutoff | `original_cutoff` and the original identity token. |
| Source change | A new fingerprint is a new proposal. The same open request is reused. |
| Later amendment on an earlier cutoff | Only if that version was already approved at the cutoff. A rejected backdate is not applied. |
| Credit note quantity | Trusted `QUANTITY_RETURN` only. |
| Who requested and why | `requested_by_id`, `requested_at`, `reason`, and the event. |
| Recalculated amount and why it differs | Proposal fields, `delta_exact` when comparable, and `difference_explanation`. |
| Who may accept | Finance manager who did not request it. |
| Current revision | The current finding for that identity, or no current finding when the accepted exposure is zero. |
| Both amounts reproducible | Original result row plus the accepted proposal and successor result. |
| Case review | `source_reassessment_required` on the same identity. A different cutoff is logged and not added. |
| Company isolation | Record rule and `test_rev14_t001`. |
| No duplicate exposure | One current identity. Different cutoffs are not summed. |
| Ready for later finance validation | `finance_package_stale` marks an old submission. This phase does not validate it. |

## Known limits

The audit-run button `action_reassess` still performs a runner reread. A database administrator can change stored rows. The digest is not an external archive. A cleared finding has no current successor for `action_accept_current_source`. Business acceptance is pending. The license value `Other proprietary` is a loader guard, not a license grant.
