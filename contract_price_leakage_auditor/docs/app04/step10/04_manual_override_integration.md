# Manual override integration

There is one approval model: `cpla.discount.approval`, request kind `transaction_override`. The wizard does not submit and does not approve. Confirming the quotation does not approve.

`Request Override` opens `cpla.quotation.override.request`. The wizard requires Contract User, a saved line, a resolved version, and a comparable actual price. It refuses a compliant line, an authorized override, a not-applicable line, and a second draft, submitted, or approved request for the same line.

The draft request stores company, sales order, sales order line, customer, product, version, proposed price, currency, UoM, quantity, reason, and evidence reference. Sale references are the string ids of the order and the line. An approval on order A does not authorize order B.

Approval still follows DEV-09. Finance Manager approves. The requester and the submitter cannot approve. Application Administrator is not a commercial approver. An empty limit still blocks approval. Company A cannot use a Company B version.

## Scope

The material fingerprint is company, customer, product, quantity text, UoM, currency, sorted tax ids, effective unit, and discount, joined by `|`.

A submitted or rejected request on that line is reported as pending or rejected even when a contractual special price is still authoritative. An approved override whose `quantity_exact` is below the line quantity is `REVIEW_REQUIRED` with reason `override_quantity_not_covered`. An expired override cannot authorize the line.

After approval, a lower price, a larger quantity, a different product, a different customer, or a different currency is evaluated again. The old approval is not reused. Changing the price further below the approved override price is below-price, not an authorized override.
