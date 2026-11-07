# Manual invoice policy

A posted customer invoice with no `sale_line_ids` is `UNLINKED_MANUAL_INVOICE` and `MANUAL_INVOICE_REVIEW_REQUIRED`, with exception `INVOICE_WITHOUT_SALES_ORDER`.

If `invoice_origin` contains text, provenance becomes `CANDIDATE_ONLY` and exception `CANDIDATE_ORIGIN_ONLY` is added. The text is not proof.

No sales order is created for a manual invoice. The applicability resolver is not called to invent a verified contract for an unlinked invoice. A direct invoice cannot claim an order-date grandfather lock.

A finance manager may verify a documentary split when company, commercial partner, product, and exact quantities match. Provenance becomes `DOCUMENTARY_LINK_VERIFIED`, never `NATIVE_RELATION_VERIFIED`, unless native links were already present. `verified_by_id`, `verified_on`, and `documentary_reference` are stored. Client-supplied prices on `create` are ignored. The create path accepts an invoice or an invoice line and recomputes the evidence.

Contract managers, contract users, auditors, and application administrators cannot verify a split. Context flags are not the security boundary. The finance-manager group is checked inside the method.

Company policy does not yet approve automatic contract-only auditing of direct invoices. That remains a review outcome.
