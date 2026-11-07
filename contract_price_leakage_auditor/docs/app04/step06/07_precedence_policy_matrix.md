# 07 — Precedence policy matrix

No precedence matrix is approved. `contract_precedence_policy` defaults to `unconfigured`. The snapshot is stored and echoed. It is not applied as a ranking.

| Situation | Result |
| --- | --- |
| One approved exact customer and exact variant | `MATCHED_AUTHORITATIVE`, rule `single_eligible_authority` |
| Two approved contracts for the same company, customer, variant, and date | `CONFLICT_REVIEW_REQUIRED`, reason `equal_authority_conflict` |
| Exact contract plus a group reference | Exact match. The group is not an authority. |
| Exact variant plus a requested template fallback for a sibling | `POLICY_REVIEW_REQUIRED`. No weighted rank. |
| Different pricing-date snapshots on two eligible contracts | Both use the request date. If both match, conflict. |
| Lower price, higher price, lower id, or higher version number | Not used to break a tie. |

Conflict text lists version references. It does not list prices.

Customer-specific before group, and variant before template, are not implemented as winners. Those scopes are not stored as competing approved terms. Inventing that matrix would apply an unapproved policy.
