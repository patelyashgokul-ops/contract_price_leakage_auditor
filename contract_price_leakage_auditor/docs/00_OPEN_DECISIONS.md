# Open decisions

Superseded for acceptance by `docs/app04/step00/07_open_decisions_and_risks.md`. Use DEC-01 through DEC-20. OD-* ids are retired aliases. This file is the preserved first pass.

Step 00 does not select these rules. A later phase that implements pricing or audit behavior before the blocking rows are decided will be treating a proposal as a requirement.

| ID | Decision | Why it is open | Blocks |
| --- | --- | --- | --- |
| OD-01 | Pricing date: invoice date, sale-order date, delivery date, or another commercial date. Time zone and whether the end date is inclusive. | P0-B requires a basis and does not name one. | I-06, GT-06, any historical finding. |
| OD-02 | Comparison basis: tax-excluded line subtotal, tax-included line total, or normalized unit price. Treatment of fiscal positions and `division` taxes. | P0-B requires normalization and does not choose the target basis. | I-03, GT-04, GT-09. |
| OD-03 | Whether posted `out_refund` credit notes are in the audit population, and how they pair to invoice lines. | P0-C names customer invoices only. | I-01, I-15, GT-03. |
| OD-04 | Whether vendor bills are in scope. The category text says Revenue & Purchasing. The product text says customer invoices. | Those two statements are not the same scope. | Purchase dependency, a second population. |
| OD-05 | Whether a price above the contract is a finding, a separate informational class, or out of scope. The product intent names unauthorized underpricing. | Overpricing was not given a P0 rule. | I-15, GT-05. |
| OD-06 | Commercial tolerance, if any, beyond currency rounding. No amount was supplied. | Choosing 0.01 or a percentage would be an invented policy. | Any "within tolerance" test. |
| OD-07 | FX evidence: `account.move.invoice_currency_rate`, a company `res.currency.rate` on a named date, or a rate written on the contract. | All three exist or could exist. They can disagree. | I-09, GT-12. |
| OD-08 | Who may approve a contract, run an audit, authorize a waiver, and verify recovery. | No role list was supplied. | S-03. Group design. |
| OD-09 | Whether `sale.order` is an evidence source. | Posted invoices can exist without a sale order. | `sale` dependency. |
| OD-10 | Quantity used for tiers: line quantity, period cumulative quantity, or contracted commitment. UoM of that quantity. | P0-B names tiers and does not name the measure. | GT-08. |
| OD-11 | Covered parties: invoice partner, commercial partner, delivery partner, or an explicit list on the contract. Child contacts. | P0-A names the scope and does not define membership. | Match tests. |
| OD-12 | Approved discount shape: net price, line percent, or a separate allowance. Interaction with `account.move.line.discount`. | Community stores several discount mechanisms. | B-05. |
| OD-13 | Which side absorbs a rounding residue, and the compare epsilon when both amounts are already currency-rounded. | Not supplied. | I-04. |
| OD-14 | Meaning of a later recovery record: memo, link to an existing credit note, or something stronger. | I-13 already forbids calling a difference recovered cash. The operational design is not specified in the received P0 text. | Recovery phases. |
| OD-15 | Module license and author. Proposed price USD $599 was supplied. The freight addon's `OPL-1` license is not an APP 04 decision. | No APP 04 license file exists. | Store package. |
| OD-16 | Whether a Community pricelist may be cited as supporting evidence, while the approved contract remains an APP 04 record. | Pricelists lack approval, supersession, and required company ownership. | Contract model boundary. |
| OD-17 | Contracts that are not in the invoice currency: convert, or exception until currencies match. | B-04 allows historical conversion and does not say it is always permitted. | I-09. |
| OD-18 | Overlapping amendments: reject on approval, or accept and raise a conflict at audit time. | A-08 and A-10 both apply. The operational choice is open. | Contract workflow. |
| OD-19 | Schedule, batch size, and failure behavior for SC-17. | No volume target was supplied. Cron is out of step 00. | Performance phase. |
| OD-20 | Confirm the UoM compatibility rule for each series as the implementation rule. | The source difference is verified. Product owners still need to accept it as the business rule. | I-10, GT-10, GT-11. |
| OD-21 | Tax group and price-included normalization algorithm. | `price_include` is computed from the company default and an override. Several taxes can sit on one line. | OD-02. |
| OD-22 | Evidence retention, hash, and immutability standard. | A-11 requires references and does not define the control. | Evidence phase. |
| OD-23 | P0 versus later scope for SC-08 through SC-18. | The ten-package list was truncated. | Backlog ranking. |
| OD-24 | Authorization of this step 00 package, or replacement of the truncated register. | The prompt forbids marking phase 00 accepted without review. | Start of implementation. |

## Blocking set before pricing or audit code

Implementation of calculation or audit code waits for OD-01, OD-02, OD-03, OD-05, OD-06, OD-07, OD-10, OD-11, OD-12, OD-13, OD-17, and OD-24.

Dependency and security design also wait for OD-04, OD-08, and OD-09.

OD-16 is the recommended planning boundary: APP 04 owns the approved contract. Community pricelists remain a possible evidence citation, not the system of record. That sentence is a proposal. It is not a decision until OD-16 is accepted.
