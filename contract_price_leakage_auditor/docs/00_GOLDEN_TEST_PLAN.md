# Golden test plan

Superseded for acceptance by `docs/app04/step00/05_financial_invariants_and_golden_tests.md`. Use GOLD-FIN-* and GOLD-REC-001. GT-* ids are retired aliases. This file is the preserved first pass.

Status: planned. **Not executed.** No test module, fixture file, database, or Odoo process was created.

These cases are the financial oracle list for a later test phase. A case whose decision is open cannot be marked passed by choosing a convenient expected value.

## Execution rules for the later test phase

- Use a disposable database. Do not point tests at a production database.
- Build synthetic partners, products, currencies, and contracts. Do not copy customer contracts into the repository.
- Assert on stored source fields: `price_unit`, `discount`, `quantity`, `price_subtotal`, `price_total`, `currency_id`, `product_uom_id`, `tax_ids`, `state`, and `move_type`.
- Record the contract version id and the rate id used in the expected result.
- Run the Odoo 19 oracle first. Re-express UoM cases for Odoo 18 and Odoo 20 before calling them the same test.
- A skipped blocked case is not a pass.

## Currency and quantity oracles

For a fixture currency with `rounding = 0.01` and `decimal_places = 2`, expected money is the value after `float_round` to that rounding. Product Price digits and Discount digits ship as 2 and may be changed in a database, so tests set the precision they require instead of assuming the data file.

Quantity uses Product Unit precision. Tests that need a three-decimal quantity set that precision explicitly.

## Case catalog

| ID | Situation | Expected result | Gate |
| --- | --- | --- | --- |
| GT-01 | Posted `out_invoice` product line, one approved contract version, same company, partner, variant, UoM, currency, and tax basis. Normalized amounts equal. | No leakage amount. A matched audit line with both source ids. | Ready to specify once OD-01 and OD-02 are fixed. |
| GT-02 | Same as GT-01, invoice normalized amount below the approved price by a currency-rounded difference. | Underpricing candidate equal to that rounded difference. Label is candidate, not recovered cash. | OD-01, OD-02, OD-06, OD-13. |
| GT-03 | Draft invoice, cancelled invoice, `entry`, `out_receipt`, `in_invoice`. | None of these create a customer-invoice finding. | Credit notes remain blocked by OD-03. Vendor bills remain blocked by OD-04. |
| GT-04 | Tax-excluded contract price compared only after tax normalization against a line whose tax is price-included. | The test names `price_subtotal` or `price_total` and the tax mode. A raw mix of those fields fails the oracle. | Blocked by OD-02 and OD-21. |
| GT-05 | Invoice price above the approved price. | No expected amount until OD-05 chooses a class. | Blocked by OD-05. |
| GT-06 | Two versions. Only the older one is effective on the pricing date. The newer one is effective later. | The older approved price is the baseline. | Blocked by OD-01 until the date field is chosen. The selection rule is I-06. |
| GT-07 | Version superseded before the pricing date. | The superseded version is not the baseline. It remains readable. | I-07. Date field still OD-01. |
| GT-08 | Quantity sits on a tier boundary, one unit below, and one unit above. | Each fixture has one expected tier. The measured quantity is the one OD-10 names. | Blocked by OD-10. |
| GT-09 | Line `discount` set, with and without an approved discount rule. | The approved case uses the approved net. The unapproved case is an exception or a candidate according to B-05, not a silent omission. | Blocked by OD-12. |
| GT-10 | Odoo 19/20: invoice UoM and contract UoM share a `relative_uom_id` chain. Quantities convert by stored `factor`. | One expected quantity in the contract UoM, rounded with Product Unit precision. | OD-20 should confirm the rule. The formula is verified in source. |
| GT-11 | UoMs that do not share a chain (19/20) or a category (18). | Exception. No leakage amount. | I-10. Separate 18 fixture using `uom.category`. |
| GT-12 | Invoice currency differs. A company `res.currency.rate` exists on the named date. | Converted amount stores rate id, date, company, and direction. | Blocked by OD-07 and OD-17. |
| GT-13 | Currencies differ and no rate evidence exists. | Exception. No converted amount. | I-09. |
| GT-14 | Contract company A, invoice company B, same partner and product. User belongs to both companies. | No match. Company B cannot read the company A contract. | I-08, S-01. |
| GT-15 | Two approved prices match the same scope and date. | Conflict exception. No chosen price. | I-12. |
| GT-16 | Unapproved or draft contract price would otherwise match. | Missing-baseline exception. Expected amount is empty. | I-05, I-11. |
| GT-17 | Matching product with no contract. | Exception. Expected amount is empty. Current pricelist is not consulted as a fallback. | I-11, I-06. |
| GT-18 | Section line and tax line on the same move as a product line. | Only the product line is compared. | I-16. |
| GT-19 | `payment_state` in `partial`, `paid`, and `not_paid` for the same price difference. | The candidate amount does not change because the customer paid the invoice. | I-13. |
| GT-20 | A partial reconciliation exists for an unrelated payment. | It does not certify leakage recovery. | I-13. Recovery design is OD-14. |
| GT-21 | Multi-company user with company A active reads company B findings through the ORM, not only through the UI. | Access error or empty result set. | S-01. |
| GT-22 | User without the invoice read group. | Cannot start an audit that reads `account.move`. | S-02. Exact group waits for OD-08. |
| GT-23 | Same numeric fixture on Odoo 18 using category UoM, and on Odoo 20 where `uom.rounding` does not exist. | 18 and 20 expected quantities are computed by that series' API. A 19-only `uom.rounding` read is a port failure. | Port gate, not a business pass. |

## Worked numeric sketch for GT-02

This sketch shows the shape of a future oracle. It is not an approved tolerance and it is not a test result.

Fixture, after OD-02 chooses tax-excluded extended price:

- Contract approved net unit price: 10.00 contract currency.
- Quantity: 3, same UoM.
- Approved extended price: 30.00.
- Invoice `price_subtotal`: 27.00.
- Currency rounding: 0.01.
- Candidate underpricing: 3.00.
- Recovered amount: empty.

If the line is tax-included, this sketch is invalid until the tax normalization in OD-02 produces the 27.00 comparison amount from the stored tax fields.

## Exit criteria for the future test phase

- Every unblocked GT row has an automated assertion on Odoo 19.
- Blocked rows are listed as skipped with the open-decision id, not deleted.
- GT-10, GT-11, and GT-23 have separate 18 and 20 notes before those series are called supported.
- A company-isolation failure fails the phase.
- No production credentials or customer documents are in the fixture files.

## What this plan does not cover

Case management, waiver, dispute, dashboard, cron, and executive report tests are not specified. Those capabilities are product intent without received P0 acceptance text.
