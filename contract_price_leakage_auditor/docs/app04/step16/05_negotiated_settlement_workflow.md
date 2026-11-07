# Negotiated settlement workflow

`cpla.recovery.settlement` keeps three dimensions.

| Dimension | Values |
| --- | --- |
| Internal | draft, submitted, under_review, approved, rejected |
| Customer | not_sent, proposed, response_pending, accepted, rejected, counteroffer, withdrawn |
| Execution | not_ready, pending_conditions, ready_for_dev17, suspended_source_changed, superseded |

`propose()` does not approve the settlement and does not change the waiver or the recovery target. When an additional waiver is greater than zero, the proposed settlement amount plus that waiver must equal the current recovery target. The additional waiver is a separate `cpla.recovery.waiver` with `reduces_recovery` set. That waiver still needs its own approval. Until it is approved, the target does not change.

## Counteroffer and acceptance

`action_record_counteroffer()` stores the customer amount, the channel, and the evidence text. It sets `customer_state` to `counteroffer`. It does not change the approved recovery target, create a waiver, or set billed or collected amounts.

Internal approval uses the settlement levels on the company policy. The proposer cannot approve when four-eyes is required. Internal approval does not set customer acceptance.

Customer acceptance requires evidence text, a channel, and a date. It sets `customer_state` to `accepted` and `execution_state` to `pending_conditions`. It does not create cash. Handoff authorization later sets `execution_state` to `ready_for_dev17` on the current accepted settlement. That still does not create an invoice.

A second current proposal must pass `supersedes_id`. The previous current settlement is marked superseded and drops out of current totals. The original proposal row and its amounts stay.
