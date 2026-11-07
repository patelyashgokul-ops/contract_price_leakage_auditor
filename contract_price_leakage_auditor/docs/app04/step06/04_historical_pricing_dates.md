# 04 — Historical pricing dates

The resolver does not read the live policy selection as the pricing date. It does not use today's date, the quotation date, the product list price, or the customer pricelist.

An explicit `pricing_date` on the request wins. Its rule is `explicit_date`.

If no date and no basis are supplied, the status is `POLICY_REVIEW_REQUIRED`, reason `pricing_date_policy_not_approved`.

| Requested basis | Date used | Missing date |
| --- | --- | --- |
| `order_confirmation` | `order_confirmation_date` after `order_confirmed` is true | `MISSING_CONTEXT` |
| `delivery` | The single delivery date | `delivery_missing` |
| `invoice` | `invoice_date` | `invoice_date_missing` |

An unconfirmed quotation returns `order_not_confirmed`. The quotation date is not substituted.

Two delivery dates return `PARTITION_REVIEW_REQUIRED`, reason `delivery_allocation_required`. One version is not applied to the combined quantity. Allocation is not implemented.

Commercial dates are calendar dates. `effective_from` is inclusive. The day before the next version stays on the earlier version. The effective day selects the later version. Tests use `context_today` and `fields.Date.add`. On this database, 28 October 2026 is today, so a June 2026 amendment would be retroactive and cannot be approved. Today versus tomorrow is the tested boundary.

A contract-specific snapshot does not choose a different date for each candidate. Both candidates are evaluated on the supplied date. If both remain eligible, the result is a conflict. The snapshot text is echoed and `policy_operationally_approved` stays false.

The knowledge cutoff is separate from the pricing date. A version whose `approved_at` is after the cutoff is invisible. `approved_at` is stored to the second, so two approvals in the same second cannot be separated. The as-known tests wait 1.1 seconds between approvals.
