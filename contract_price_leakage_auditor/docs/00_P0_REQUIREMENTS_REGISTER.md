# P0 requirements register

Superseded for acceptance by `docs/app04/step00/03_requirements_baseline.md`. IDs A-01 through C-03 were kept. Later packages are registered there. This file is the preserved first pass.

Source: step 00 prompt section 7, as far as it was received on the first pass.
Status: draft for review. Not accepted.
Norm: one row is one supplied bullet. Detail that would choose a financial rule is recorded as an open decision, not as a requirement.

Priority P0 means the prompt placed the bullet in a P0 package. It does not mean the design is complete enough to build.

## Package coverage

| Package | Prompt status | Rows |
| --- | --- | --- |
| P0-A Contract Governance | Received in full. | A-01 to A-11 |
| P0-B Pricing Rules | Received in full. | B-01 to B-10 |
| P0-C Invoice Auditing | Received only through "Approved historical pricing." | C-01 to C-03 |
| Remaining packages needed to reach ten | Not received. | No IDs assigned. |

## P0-A — Contract Governance

| ID | Requirement | Source | Design gate |
| --- | --- | --- | --- |
| A-01 | Contracts are company-specific. | SUPPLIED | Native `product.pricelist.company_id` is optional. A shared pricelist is not a company contract. See invariant I-08. |
| A-02 | Customer and covered-entity scope is explicit. | SUPPLIED | Who is covered is OD-11. |
| A-03 | Contract lines match products. | SUPPLIED | Match key is not fully specified beyond product and variant. |
| A-04 | Product variants are matchable separately from templates. | SUPPLIED | Community pricelist items already distinguish template and variant. That mechanism has no approval or version chain. |
| A-05 | Effective dates bound applicability. | SUPPLIED | Date basis is OD-01. Inclusive and exclusive endpoints are not specified. |
| A-06 | Approval authority is required before a price can be used. | SUPPLIED | Roles are OD-08. An unapproved price is not an audit baseline. Invariant I-05. |
| A-07 | Historical versions are retained. | SUPPLIED | The version in force on the pricing date is the baseline. The current price is not a substitute. Invariant I-06. |
| A-08 | Amendments are represented. | SUPPLIED | Overlap behavior is OD-18. |
| A-09 | Supersession is represented. | SUPPLIED | A superseded version remains evidence and stops being the applicable price. Invariant I-07. |
| A-10 | Contract conflicts are detectable. | SUPPLIED | Two applicable approved prices for the same scope are a conflict exception, not a silent pick. |
| A-11 | Evidence references are kept on the contract record. | SUPPLIED | Retention and immutability standard is OD-22. |

## P0-B — Pricing Rules

| ID | Requirement | Source | Design gate |
| --- | --- | --- | --- |
| B-01 | A contract applies only inside its approved scope. | SUPPLIED | Depends on A-01, A-02, A-05, A-06. |
| B-02 | Quantity tiers are supported. | SUPPLIED | Which quantity is measured is OD-10. |
| B-03 | Unit of measure conversion is supported when the units are compatible. | SUPPLIED | Odoo 18 and Odoo 19/20 do not share a UoM graph. Invariant I-10. Incompatible units become missing-evidence exceptions. |
| B-04 | Historical currency conversion is supported when rate evidence exists. | SUPPLIED | Rate source is OD-07. A missing rate is an exception. Invariant I-09. |
| B-05 | Only approved discount rules count. | SUPPLIED | How a discount is stored is OD-12. An invoice discount without an approved rule is not ignored and is not automatically leakage. |
| B-06 | Tax-inclusive and tax-exclusive prices are normalized before comparison. | SUPPLIED | The comparison basis is OD-02. Mixed `price_subtotal` and `price_total` comparisons are forbidden. Invariant I-03. |
| B-07 | Monetary precision follows the currencies involved. | SUPPLIED | `res.currency.rounding` and `res.currency.decimal_places` are the money precision. Product Price digits are a display precision, not a second currency. |
| B-08 | Rounding is explicit. | SUPPLIED | Residue ownership and compare epsilon are OD-13. Bare float equality is forbidden. Invariant I-04. |
| B-09 | The pricing-date basis is declared. | SUPPLIED | The basis itself is OD-01 and is not selected in this step. |
| B-10 | Missing evidence produces an exception, not a fabricated price. | SUPPLIED | Invariant I-11. |

## P0-C — Invoice Auditing

| ID | Requirement | Source | Design gate |
| --- | --- | --- | --- |
| C-01 | Eligibility starts from posted customer invoices. | SUPPLIED | Odoo 19 `account.move.state = posted` and `move_type = out_invoice`. Draft and cancel are outside this bullet. Credit notes, receipts, and vendor bills are OD-03 and OD-04. |
| C-02 | Comparison is at invoice-line level. | SUPPLIED | Header totals are a reconciliation check, not a substitute for the line. |
| C-03 | The baseline is the approved historical price. | SUPPLIED | Today's partner pricelist and today's contract version are not historical baselines. Invariant I-06. |

Further P0-C bullets were not in the received prompt.

## Supplied capabilities that are not yet P0 rows

SC-08 through SC-18 in the source inventory are in the product intent. They do not have acceptance criteria in the received text. They stay outside this register until a later authorized package names them.

In particular, this register does not yet require:

- a case-management workflow
- a recovery ledger
- a waiver workflow
- dispute documents
- accounting entry creation
- payment matching
- dashboards or executive reports
- scheduled jobs
- a performance target

Those themes appear in the prompt's future-scope list. Building them in step 00 was prohibited. Promoting them to P0 without the missing package text would be a silent scope decision.

## Trace to invariants and planned tests

| Requirements | Invariants | Planned tests |
| --- | --- | --- |
| A-01, A-10 | I-08, I-12 | GT-14, GT-15 |
| A-05, A-06, A-07, A-09, B-01, B-09, C-03 | I-05, I-06, I-07 | GT-06, GT-07, GT-08, GT-16 |
| B-03 | I-10 | GT-10, GT-11 |
| B-04 | I-09 | GT-12, GT-13 |
| B-06, B-07, B-08 | I-03, I-04 | GT-04, GT-05, GT-09 |
| B-10 | I-11 | GT-17 |
| C-01, C-02 | I-01, I-02 | GT-01, GT-02, GT-03 |

## Register control

- Rows are not marked implemented.
- Rows are not marked tested.
- A reviewer must accept the register, or replace it, before application models are added.
