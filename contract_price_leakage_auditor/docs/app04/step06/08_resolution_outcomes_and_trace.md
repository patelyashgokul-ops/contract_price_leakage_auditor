# 08 — Resolution outcomes and trace

A match explanation names the version reference and the pricing date. It states that the company policy is not operationally approved and that the check is not an invoice audit. When a quantity is supplied, it adds that the quantity was not evaluated and the stored unit price is not a qualified tier price.

| Status | When |
| --- | --- |
| `MATCHED_AUTHORITATIVE` | One visible approved version and one line |
| `NO_APPLICABLE_CONTRACT` | No eligible approved line |
| `CONFLICT_REVIEW_REQUIRED` | More than one contract, or a broken chronology |
| `MISSING_CONTEXT` | Company, customer, product, or required date is absent or invalid |
| `POLICY_REVIEW_REQUIRED` | Unapproved date policy, template scope, category scope, unresolved unit, or an unapproved grandfather limit |
| `HISTORICAL_EVIDENCE_REVIEW_REQUIRED` | Group coverage, missing approval time, or missing supersession evidence |
| `PARTITION_REVIEW_REQUIRED` | More than one delivery date |

Access failures raise `AccessError` or `UserError`. They do not return the other company's price. A contract user who does not own the contract gets no match, and the explanation does not contain the price. Record rules hide the line.

The wizard stores the price, contract, version, and line only when the status is `MATCHED_AUTHORITATIVE`. `action_resolve` returns true. The form says the check is not an approved price and does not audit invoices. There is no Run Invoice Audit button.

The result dict is the provenance shape for a later audit phase. This phase does not store an audit row.
