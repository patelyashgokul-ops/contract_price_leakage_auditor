# Financial and security invariants

Superseded for acceptance by `docs/app04/step00/05_financial_invariants_and_golden_tests.md` and `06_security_and_operational_invariants.md`. First-pass I-01 and S-01 numbers are retired. Use FIN-* and SEC-*. This file is the preserved first pass.

These rules are release-blocking for any later implementation. They constrain the design. They do not choose the open business decisions in `00_OPEN_DECISIONS.md`.

A later phase that needs to break an invariant must record an explicit, reviewed exception. Silent relaxation is a failed release.

## Financial invariants

### I-01 Eligible invoice population

A customer-invoice audit candidate has `account.move.state = posted` and `account.move.move_type = out_invoice`.

Draft and cancelled moves are not candidates. Journal entries are not candidates. Sales receipts (`out_receipt`) are not candidates under the received P0-C text.

Customer credit notes and vendor bills stay out of the population until OD-03 and OD-04 are decided. They must not be folded in by a default.

### I-02 Source documents stay intact

The auditor reads `account.move` and `account.move.line`. It does not write invoice prices, taxes, discounts, quantities, or reconciliation rows. An audit result is a separate record that references the source ids and the values it used.

### I-03 One monetary basis per comparison

Each finding names its basis. The permitted bases are the line's tax-excluded `price_subtotal` or the line's tax-included `price_total`, after an explicit normalization rule.

A contract net price must not be compared with a tax-included line total. A unit price must not be compared with an extended amount. The basis itself is OD-02 and remains undecided. Until it is decided, a finding cannot be marked financially valid.

`price_unit` is a float using Product Price display precision. `price_subtotal` and `price_total` are monetary fields in the move currency. The implementation must say which of those it used.

### I-04 Rounding is part of the oracle

Money is rounded with `res.currency.rounding` for the currency of the amount being stored.

Quantities are compared with Product Unit decimal precision. Odoo 19 and 20 UoM rounding methods use that precision. Odoo 18 also has a per-unit `rounding` field. A golden test must name which rounding it applied.

Float equality is not a pass condition. The comparison epsilon is OD-13. Until OD-13 is decided, tests may assert exact scaled integers for fixtures they control, and they may not invent a commercial tolerance.

### I-05 Only an approved price is a baseline

A draft, proposed, or rejected contract price cannot explain an invoice line. If no approved price applies, the result is a missing-baseline exception (I-11), not a zero expected price and not a current list price.

### I-06 Historical selection

The baseline is the approved version effective on the pricing date. The partner's current `property_product_pricelist`, the current contract version, and a pricelist recomputed today are not historical baselines.

The pricing date is OD-01. Until it is chosen, the audit must not pick a date on its own and then present the result as final.

### I-07 Supersession preserves evidence

When a version is superseded, later audits stop applying it. The old version, its approval, and its evidence references remain readable. Rebuilds of a past audit use the version that was applicable on that historical pricing date, not the successor.

### I-08 Company isolation

Every APP 04 contract, version, audit run, finding, exception, and evidence row carries a required `company_id`.

A record of company A is not readable, writable, or usable as a baseline for company B. Record rules must enforce this even when the user belongs to both companies. Shared `product.pricelist` rows with empty `company_id` must not be treated as an approved contract for every company.

Currency rates used as evidence are company-scoped `res.currency.rate` rows, or a rate stored on the source move, according to OD-07. A rate from another company is not evidence.

Odoo already limits `account.move` with `[('company_id', 'in', company_ids)]`. APP 04 must not widen that visibility.

### I-09 No silent currency conversion

If the contract currency and the invoice currency differ, conversion happens only with a named rate, a rate date, a company, and a direction. Missing rate evidence produces an exception. The audit must not call `res.currency` rate lookup and then drop the rate identity.

`account.move.invoice_currency_rate` exists on Odoo 19. Whether it is the documentary rate is OD-07, not an assumption.

### I-10 No silent unit conversion

Conversion is allowed only inside one compatible chain:

- Odoo 18: the same `uom.category`.
- Odoo 19 and 20: one `relative_uom_id` chain.

Units that do not meet are an exception. The audit must not compare a quantity in kilograms with a quantity in units by treating both as raw numbers.

Odoo 18, 19, and 20 need separate conversion oracles. One numeric fixture is not automatically valid on all three.

### I-11 Missing evidence is an exception

Missing contract, missing approval, missing applicable version, ambiguous match, missing rate, incompatible unit, or missing tax basis produces an exception state. It does not produce a leakage amount.

### I-12 Conflicts do not pick a winner

If two approved prices apply to the same company, covered party, product scope, quantity, and pricing date, the result is a conflict exception. The lower price must not be chosen because it is convenient, and the higher price must not be chosen because it increases a leakage total.

### I-13 A difference is not recoverable cash

Unauthorized underpricing, once the open decisions allow a number, is a candidate difference. It is not revenue, not a receivable, and not a recovered amount.

Recovery, waiver, dispute, and accounting-adjustment records are outside the received P0 fragment. Any later amount called recovered requires a separate finance verification that cites a posted Community document, such as an `account.partial.reconcile` row or a posted credit note. Payment status `partial` or `in_payment` is not verification of a leakage recovery.

### I-14 The auditor does not post accounting entries

Step 00 forbids accounting workflows. Later phases may store a reference to an existing move. Creating or posting `account.move` rows from an audit finding requires a new authorized decision. It is not implied by "accounting adjustment references."

### I-15 Sign and population are explicit

A customer invoice line that was billed below the approved price is the underpricing direction named in the product intent. A line billed above the approved price is not automatically the same kind of finding. OD-05 decides whether overpricing is reported.

Credit notes must not be subtracted from findings until OD-03 says they are in the population, and then only once, with a link to the original line.

### I-16 Display lines are not merchandise lines

`account.move.line.display_type` distinguishes section, note, and tax lines from product lines. Only product lines with a product and a quantity enter a price comparison. Tax lines are inputs to tax normalization, not extra leakage lines.

## Security invariants

### S-01 Company record rules on every APP 04 model

Models that store commercial or financial data define `company_id` and an `ir.rule`. The rule is not replaced by hiding a menu.

### S-02 Accounting groups are not copied onto auditors

Community Invoicing exposes `account.group_account_invoice` and `account.group_account_manager` for invoice work. Readonly and full accountant groups also exist in the same file and are described there as deeper accounting access.

An APP 04 auditor who only needs to read posted invoices must not be placed in `account.group_account_manager` to make the screen work. The later access design must name the smallest account group that can read the source moves, and must test a user who does not have it.

### S-03 Separate duties stay separate

Contract approval, audit execution, waiver authorization, and finance verification are different authorities (OD-08). One user must not be able to approve the price, waive the finding, and certify the recovery while those duties remain unassigned. The group design is not chosen in step 00. The invariant is that the design may not collapse them by default.

### S-04 Evidence is company-bound

Attachments and chatter messages on contracts and findings follow the parent record's company. A multi-company user does not receive evidence for a company that is not active in the record rule.

### S-05 Portal and exports are closed until specified

`account` depends on `portal`. That dependency does not authorize a portal page for contract prices. Export of contract prices and findings is privileged. There is no supplied public-report requirement.

### S-06 Secrets stay out of logs and reports

Database passwords, API keys, customer contract files, and production invoice extracts are not written into development reports, test fixtures committed to the addon, or exception messages. Fixtures are synthetic.

### S-07 Scheduled work is company-aware

No cron is created in step 00. A later scheduled audit must run with an explicit company and must not use `sudo` to cross companies. A failure in one company must not mark another company's run successful.

### S-08 Read-only accounting

Privileges granted to APP 04 users on `account.move`, `account.move.line`, `account.partial.reconcile`, and `res.currency.rate` are read privileges unless a later phase is explicitly authorized to create accounting documents.

## Invariants that are intentionally not rules yet

The following are not invariants, because choosing them would decide an open business question:

- the pricing date
- tax-included versus tax-excluded as the standard basis
- a commercial tolerance other than currency rounding
- the FX document to trust
- whether overpricing is a finding
- whether credit notes reduce leakage
- the approval role names
