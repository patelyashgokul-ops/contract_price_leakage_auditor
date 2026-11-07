# DEV-14 historical cutoff and returns

Date: 2026-11-05. Version: `19.0.1.12.0`. Amounts below are decimal texts in the company currency of the disposable chart. This file does not claim that currency is INR. Later cutoff and refund notes are in `03_historical_time_semantics.md` and `08_refund_reversal_reassessment.md`.

The supported cutoff is approval-time knowledge. DEV-14 does not approve a backdated amendment. `cpla.customer.contract.version.action_approve` still refuses an amendment whose effective date is before the approval day, logs `historical_reassessment_required`, and leaves the amendment unapproved.

## Quantity return

`test_rev14_t001`.

Posted sale of 100 at unit price 1100 against an approved unit price 1150. The first audit result and the current finding are both `5000`.

A posted customer credit of quantity 20 on that invoice is classified `QUANTITY_RETURN` with `quantity_trusted`. The trigger is `verified_quantity_return`.

Preview, before acceptance:

| Item | Value |
| --- | --- |
| Eligible quantity | `80` |
| Approved unit price | `1150` |
| Actual unit price | `1100` |
| Proposed exposure | `4000` |
| Delta | `-1000` |
| Delta class | `exposure_decreased` |
| Current finding | Still `5000` |
| Original result row | Still `5000` |

No finding row and no result row is inserted by the preview. Acceptance makes one current finding of `4000` on eligible quantity `80`. The previous finding stays at `5000` with status `superseded_by_reassessment` and `is_current` false. Current exposure is `4000`, not `9000`. The invoice line price and quantity are unchanged. Payment count and move count are unchanged. `is_recovered_cash` and `is_writeoff` stay false. The explanation says the difference is an evidence correction, not recovered cash, and not an approved write-off.

A second open request for the same finding, trigger, and credit returns the same row. A superseded finding cannot be requested again.

## Amount-only credit

`test_rev14_t006`.

A quantity-return trigger on a credit that is not a trusted quantity return stays `evidence_review_required`. The review text says no returned quantity was invented. A `price_adjustment_credit` trigger that keeps eligible quantity 100 can propose exposure `5000` and says the credit was not converted into returned pieces. That test does not accept the price-adjustment proposal. A monetary credit is not turned into returned pieces.

## Full reversal

`test_rev14_t007`.

A posted full credit of the original invoice is a trusted `FULL_REVERSAL`. Preview proposes `0`, delta `-5000`, class `exposure_eliminated`. Until acceptance, the finding stays current at `5000`.

Acceptance does not leave a second current finding of `0`. The DEV-12 engine clears the priced row and then releases it, because a zero outcome is not persisted as a current potential finding. DEV-14 does not change that engine. After acceptance:

- Current exposure is `0`.
- No current potential finding remains on the invoice.
- The historical finding text `5000` stays, and those rows are not current.
- `successor_result_id` points at the audit result whose potential exposure is `0`.
- The original result row is still `5000`.
- The result and the reassessment are not recovered cash and not a write-off.

## Replacement

`test_rev14_t010`.

A posted replacement invoice without a trusted full reversal stays `evidence_review_required`. The review text says exposure was not forced to zero. The current finding stays `5000`.

After a posted full credit is mapped by the finance user, a new evaluation can propose `0`. Acceptance clears current exposure. The replacement invoice has no current potential finding of its own in that test. The original result stays `5000`. Payment count is unchanged. Corrected billing is not collected cash.

## Separate knowledge cutoff

`test_rev14_t008`.

Invoice policy. Version V1 price `1000`, approved under freeze `2026-06-01`, effective `2026-06-02`. Later version price `1200`, approved under freeze `2026-07-20`, effective `2026-07-20`. Invoice date `2026-07-25` at unit price `1000`, quantity 100.

| Cutoff | Version | Result |
| --- | --- | --- |
| `2026-07-01` | V1 | Exposure `0` on the audit result. No current potential finding, because the engine does not persist a zero finding. |
| `2026-07-21` | Later version | Current finding `20000`. |

A reassessment of the later finding with trigger `approved_retroactive_amendment` and cutoff `2026-07-01` proposes version V1, exposure `0`, a different identity, a blank delta, and class `undetermined`. The explanation says the amounts were not subtracted and the other cutoff was not replaced.

Acceptance leaves the later finding current at `20000` on the later version. Current exposure stays `20000`. The early result row, version, amount, and fingerprint stay as they were. The case is not flagged `source_reassessment_required`. Membership still points at the later finding. Reviewed exposure stays `20000`. The case logs `separate_interpretation_recorded`.

A further amendment with `effective_from` ten days in the past still raises `UserError` on approval and stays unapproved. The current finding version stays the later approved version.

## FX, tax, discount, tier, and mapping triggers

Those triggers are stored and classified. The preview sends the requested cutoff into the existing engine. It does not force a caller-chosen contract version. It does not invent an FX rate, a tax rule, or an approval timestamp. If the engine result is not authoritative, the reassessment stays in evidence review and cannot be accepted.

Duplicate-finding correction does not merge cases and does not change an amount by itself.

## Time dimensions

`knowledge_cutoff` is the as-known cutoff passed to the engine. The commercial effective date and the invoice date stay on the contract version and the invoice. `evaluated_at` and `decision_at` are the times of this reassessment. Those fields are not substitutes for each other.
