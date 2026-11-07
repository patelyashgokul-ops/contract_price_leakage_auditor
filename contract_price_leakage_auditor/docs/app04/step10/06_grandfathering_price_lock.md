# Grandfathering and price lock

A lock is written only after `action_confirm` succeeds. It is not inferred from the live quotation fields. Later contract prices do not rewrite the row.

`order_date_lock_candidate` is true only when the approved version's `pricing_date_policy_snapshot` is `order_confirmation`. That snapshot is the candidate copied at version approval. It is not a new operational pricing-date rule. Company `pricing_date_policy` stays a candidate.

An invoice-date snapshot stays false for the order-date lock. A June quotation does not lock a June rate for a later invoice when the stored snapshot is `invoice`.

`grandfathering_applied` is the resolver flag. It is true only under the DEV-06 rule: pricing-date rule `order_confirmation`, an invoice date that differs, and a later approved version effective between those dates. Quotation confirmation passes today's date, so this flag is stored as the resolver returned it. It is not a second grandfathering engine.

The row stores the order, the line, confirmation timestamp, customer, company, product, quantity, UoM, currency, pricing date, pricing-date rule, policy snapshot, contract, version, tier, quantity basis, FX rate text, tax basis, financial status, discount status, approval, approved adjusted unit, actual unit, preventive exposure, authorized concession, compliance status, control mode, policy, policy version, and the line fingerprint.

There is no invoice foreign key. This row does not modify a posted invoice and does not allocate invoice lines. DEV-11 can read `version_id` and `order_date_lock_candidate` when it matches a later invoice.

`leakage_amount` and `is_recovered_cash` are false.
