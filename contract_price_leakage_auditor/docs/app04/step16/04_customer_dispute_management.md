# Customer dispute management

`cpla.customer.dispute` was not added. The model is `cpla.recovery.dispute`. A dispute links to an approved recovery request and one recovery line in the same company and for the same customer. The disputed amount is not new leakage and does not reduce the recovery target.

## Categories

Price not accepted, increase not communicated, claims discount, wrong version, wrong product or quantity, tax disagreement, FX disagreement, credit or refund not reflected, invoice already corrected, duplicate demand, prior settlement, missing purchase-order reference, other contractual dispute, and undetermined.

Opening a dispute requires an explanation. The channel and evidence text are stored on the dispute. The module does not send email and does not subscribe the customer. `message_post` is not called from the recovery model.

## States

Open, evidence requested, under internal review, customer response pending, negotiating, settlement proposed, resolved agreed, resolved rejected, withdrawn, and escalated. `action_request_source_review()` sets the dispute to escalated and `reassessment_requested`. It does not call `action_run` or `action_reassess`, and it does not change the finding.

## Positions inside the target

Acknowledgement is additive and requires a channel, a date, and evidence text. Silence is not acceptance. `action_mark_discussion()` records that discussion is open and does not set an acknowledged amount. Acknowledgement plus dispute cannot exceed the current recovery target. A second active dispute that would push the sum over the target raises `DISPUTE_EXCEEDS_TARGET`. Withdrawal sets `counts_current` false and releases that dispute slice. The row remains.

Unresolved customer position is `unanswered` on `position_for()`: recovery target minus dispute minus acknowledgement. It is not marked acknowledged or disputed by default.
