# 07 — Open decisions and risks

No decision is approved. Owner of every decision: **UNASSIGNED**. Approval evidence: none. A recommendation is a proposal for review, not a default that later code may apply.

First-pass IDs OD-01 through OD-24 in `docs/00_OPEN_DECISIONS.md` are retired aliases. Use DEC-01 through DEC-20.

## Decision register

| ID | Question | Why it matters | Options | Proposal, unapproved | Class | Needed before |
| --- | --- | --- | --- | --- | --- | --- |
| DEC-01 | Which date selects the contract version, in which time zone, and is the end date inclusive? | FIN-02. GOLD-FIN-002 shows three different policies. | Invoice date. Verified order-date lock. Delivery date. No grandfathering. | Do not pick one in code. Record the policy on the audit run. "Effective from 1 July" includes 1 July in V2 only inside that fixture. | BLOCKING_NOW | DEV-05 and DEV-12 |
| DEC-02 | How is precedence decided among matching approved prices? | FIN-08. Two matches must not become a silent winner. | Specificity order. Explicit rank. Always `BUSINESS_REVIEW_REQUIRED` until a rank exists. | Until a rank is approved, GOLD-FIN-007 applies: no confirmed leakage. | BLOCKING_NOW | DEV-06 |
| DEC-03 | Do parent, invoice, delivery, and branch partners share coverage? | A wrong party applies the wrong price. | Invoice partner only. Commercial partner. Explicit list including children. | Require an explicit covered-party list. Do not imply children. | BLOCKING_NOW | DEV-04 |
| DEC-04 | Which quantity qualifies a tier, and what happens when a return crosses a tier? | GOLD-FIN-006A is blocked. | Line quantity. Period cumulative. Contract commitment. Reprice or freeze the original tier. | Freeze the original tier unless a written rule says otherwise. GOLD-FIN-006 itself assumes no repricing. | BLOCKING_BEFORE_PHASE | DEV-07 |
| DEC-05 | How do special prices, percents, and invoice discounts stack, and when does approval expire? | FIN-03. GOLD-FIN-001 treats the special price as the approved net. | Net special price replaces the base. Percents stack. Invoice discount must match an approval id. | Treat an unmatched invoice discount as potential leakage, not as authorized. | BLOCKING_NOW | DEV-09 |
| DEC-06 | Which FX document is historical evidence, and on which date? | FIN-05. Live rates can disagree with the invoice. | `invoice_currency_rate` on the move. Company `res.currency.rate` on a named date. Rate stored on the contract. | Store the rate identity. Refuse conversion when none of the approved sources exists. | BLOCKING_NOW | DEV-08 |
| DEC-07 | Which tax basis is compared, and how are groups and included taxes removed? | FIN-06. GOLD-FIN-005 is illustrative. | Tax-excluded subtotal. Tax-included total. Normalize both to net using the line's actual taxes. | Compare one declared basis. Do not mix `price_subtotal` with `price_total`. Validate the 18% example against the real tax before any test is called passed. | BLOCKING_NOW | DEV-08 |
| DEC-08 | Rounding mode, residue owner, and any tolerance beyond currency rounding. | FIN-07. No tolerance amount was supplied. | Currency rounding only. A stated commercial tolerance. | Do not invent a tolerance. Currency rounding is the only numeric rule already present on `res.currency`. | BLOCKING_NOW | DEV-08 |
| DEC-09 | Which moves are eligible, including credit notes, partial invoices, receipts, and vendor bills? | FIN-10. P0-C names returns, credit notes, and partial invoices without the exact filter. | Posted `out_invoice` only. Plus linked `out_refund`. Plus `out_receipt`. Vendor bills out. | Start from posted `out_invoice`. Add `out_refund` only when the link rule is approved. Leave vendor bills out. | BLOCKING_NOW | DEV-11 |
| DEC-10 | What identifies one current exposure? | FIN-09 and OPS-02. | Company + invoice line + policy version. Include contract version. Include a human merge key. | Uniqueness must include company and invoice line at minimum. The full key waits for approval. | BLOCKING_NOW | DEV-12 |
| DEC-11 | Who may approve recovery, at which amounts? | SEC-04 and SEC-05. | Single finance role. Amount bands. Dual control. | No approval action exists until the matrix is approved. Self-approval is already forbidden by SEC-05. | BLOCKING_BEFORE_PHASE | DEV-16 |
| DEC-12 | Who may approve a waiver, at which amounts? | A waiver is not cash, but it reduces the target. | Same matrix as recovery. A stricter matrix. | Separate from recovery approval until one matrix is explicitly shared. | BLOCKING_BEFORE_PHASE | DEV-16 |
| DEC-13 | Which posted document proves cash recovery? | FIN-13 and FIN-14. | `account.partial.reconcile` on the recovery receivable. Bank statement line. Credit note alone. | Credit notes and original-invoice payment status do not prove recovery. The positive proof waits for approval. | BLOCKING_BEFORE_PHASE | DEV-17 |
| DEC-14 | What evidence must exist before a contract or a finding is confirmed? | FIN-08 and SEC-06. | Attachment required. Structured reference enough. Both. | Missing required evidence stays an exception. The checklist itself is not written. | BLOCKING_BEFORE_PHASE | DEV-14 |
| DEC-15 | How are historical contracts and invoices loaded? | Bad imports create false leakage. | Manual entry. CSV with a staging state. One-time migration. | Staging cannot become an approved version without the normal approval. | BLOCKING_BEFORE_PHASE | DEV-04 if import is in that phase, otherwise the phase that adds import |
| DEC-16 | What operational SLA is required for audit backlog and alerts? | OPS-08. No target was supplied. | Business days by company calendar. A stated hour limit. | Do not invent an SLA. Visibility of failure is still required. | OPTIONAL_ENHANCEMENT for the number. Visibility itself stays P0 via H-08. | DEV-18 |
| DEC-17 | Retention and legal hold. | SEC-09. Destruction rules are legal. | Years by document type. Hold flag. External policy. | Do not delete audit history in any phase before this decision. | BLOCKING_BEFORE_PHASE | DEV-21 packaging must not claim a retention period |
| DEC-18 | Performance pass thresholds. | Volume tests have no pass line. | Time and hardware for each volume id. | Measure and record. Do not publish a supported volume. | BLOCKING_BEFORE_PHASE | DEV-20 |
| DEC-19 | Which Community modules are hard dependencies? | DEV-01 manifest. | `account` plus `mail`. Add `sale` only if quotations are in scope. Never Enterprise accounting. | Propose `account` and `mail` only. Re-read manifests at DEV-01. `contacts`, `sale`, and `purchase` stay optional. | BLOCKING_BEFORE_PHASE | DEV-01 |
| DEC-20 | Is USD $599 the price buyers will pay, and against which alternatives? | The figure is a hypothesis. | Validate with wholesalers. Change the price. Park the product. | Do not print ROI or uniqueness claims. Differentiate only by the capabilities that are actually built and tested. | COMMERCIAL_VALIDATION | Before store listing, not before an internal DEV-01 design review |

Financial and security implication for every BLOCKING_NOW row: implementing a calculator before the decision approves a rule would present an unapproved amount as leakage.

## Risks

| ID | Risk | Severity | Dependency | Proposed handling |
| --- | --- | --- | --- | --- |
| R-01 | Pricing date coded as invoice date without DEC-01 | High | FIN-02 | Block DEV-12 calculation merge. |
| R-02 | Pricelist used as the contract | High | A-06, SEC-01 | APP 04 contract model in DEV-04. Pricelist may be cited, not stored as the version of record. |
| R-03 | UoM port copied from Odoo 18 examples | High | FIN-04 | Separate oracles for 18, 19, and 20. No conversion in DEV-00. |
| R-04 | Enterprise `account_reports` assumed | High | RPT-01 | Absent from the tree. Build Community read models later. |
| R-05 | License assumed from the freight addon or from LGPL of Odoo | High | PJ-10 | LEGAL_OR_LICENSE_REVIEW_REQUIRED. |
| R-06 | Golden INR examples treated as universal tax law | High | GOLD-FIN-005 | Mark illustrative. Validate per transaction. |
| R-07 | Recovery billed reported as cash | High | FIN-13 | GOLD-REC-001 equations are release-blocking once implemented. |
| R-08 | Cross-company sudo in cron | High | SEC-08 | Forbidden. Test in DEV-18. |
| R-09 | Git history unavailable | Medium | Audit trail of this repo | Record file hashes at the first commit, whenever Git exists. |
| R-10 | Two documentation generations | Medium | This package versus `docs/00_*.md` | `docs/app04/step00/` wins. |
| R-11 | P1 row implemented because it was listed | Medium | Section 8 | P1 stays unapproved. |
| R-12 | wkhtmltopdf or xlsxwriter added without notice | Medium | RPT-09 | REQUIRES_VALIDATION and license review. |

No risk above is accepted. No owner is assigned.
