# 05 — Grandfathering rules

Grandfathering is not a company-policy approval. It applies only when all of the following are true:

- The request basis is `order_confirmation`.
- `order_confirmed` is true and the confirmation date is present.
- An invoice date is present and differs from the confirmation date.
- A later approved version of the same contract starts after the confirmation date and on or before the invoice date.
- That later version is visible at the knowledge cutoff and is not an unauthorized retroactive amendment.

The selected version is the one in force on the confirmation date. The flag `grandfathering_applied` is true. The later invoice date does not replace that version.

A confirmation on the later version's effective date selects that later version, and the flag is false.

A draft quotation does not qualify. A missing confirmation date is `MISSING_CONTEXT`. A caller-supplied `grandfather_limit` is `POLICY_REVIEW_REQUIRED`, reason `grandfather_limit_not_approved`. No time limit was invented.

The lock does not cross customers or products. There is no sales-order record link in this phase. The dates are request evidence, not a posted order. Partial invoice quantities are not allocated. A quantity on the request sets `tier_status` to `pending_dev07` and does not calculate leakage.

This is the GOLD-FIN-002 selection case only: V1 at 1000 remains the authority when the order date is before V2 at 1200. No leakage amount is calculated.
