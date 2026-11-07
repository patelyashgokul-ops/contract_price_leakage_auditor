# Requirements source inventory

Superseded for acceptance by `docs/app04/step00/03_requirements_baseline.md`. The truncation described below was closed by the remainder of the step 00 prompt. This file is the preserved first pass.

Inspection date: 2026-10-28

Four labels are used everywhere in this package.

| Label | Meaning |
| --- | --- |
| VERIFIED | Read from a file on disk during this inspection. |
| SUPPLIED | Stated in the step 00 prompt received in this session. |
| PROPOSED | Planning reconstruction. Not an approved rule. |
| MISSING | Named by the prompt, or required for a safe design, and not available to read. |

No separate requirements document, acceptance record, roadmap file, or business-decision log for APP 04 was found in the addon directory.

## Sources

| ID | Source | Status | Use |
| --- | --- | --- | --- |
| SRC-01 | Step 00 prompt, sections 1–6, received in this session | SUPPLIED | Role, prohibitions, product purpose, and the 18-item future scope. |
| SRC-02 | Step 00 prompt, section 7, packages P0-A and P0-B | SUPPLIED | Requirement bullets transcribed into the register. |
| SRC-03 | Step 00 prompt, section 7, P0-C, three bullets | SUPPLIED, partial | Register stops where the prompt stops. |
| SRC-04 | Remainder of the step 00 prompt after "Approved historical pricing." | MISSING | The prompt says there are ten P0 packages. Packages after the P0-C fragment were not received. |
| SRC-05 | Local Odoo 19.0 Community source | VERIFIED | Dependency and field facts for the master target. |
| SRC-06 | Local Odoo 18.0 and 20.0 Community source | VERIFIED | Compatibility differences. Not a statement that behavior was executed. |
| SRC-07 | Empty APP 04 directory and addon listings | VERIFIED | Implementation status. |
| SRC-08 | Freight addon manifest | VERIFIED | Identity check only. Not an APP 04 requirement. |
| SRC-09 | Formal business-understanding pack of 30 topics named in section 6 | MISSING | Topics are listed below as a backlog. They were not performed. |

## Product intent from SRC-01

APP 04 compares posted customer invoice prices with applicable, approved historical customer contract prices for B2B wholesalers and distributors.

The prompt says the product must eventually support:

| ID | Supplied future capability |
| --- | --- |
| SC-01 | Approved customer pricing agreements. |
| SC-02 | Effective-dated contract versions. |
| SC-03 | Contract amendments and supersession. |
| SC-04 | Customer, product, variant, and quantity matching. |
| SC-05 | Approved special prices and discounts. |
| SC-06 | Currency, unit-of-measure, tax, and rounding normalization. |
| SC-07 | Historical posted-invoice auditing. |
| SC-08 | Unauthorized underpricing detection. |
| SC-09 | Business exception handling. |
| SC-10 | Evidence-based finance validation. |
| SC-11 | Recovery and waiver authorization. |
| SC-12 | Customer pricing disputes. |
| SC-13 | Accounting adjustment references. |
| SC-14 | Verified customer payment reconciliation. |
| SC-15 | Financial and historical evidence traceability. |
| SC-16 | Multi-company security. |
| SC-17 | Scheduled and high-volume audits. |
| SC-18 | Executive and financial reporting. |

These are product intent. They are not detailed acceptance criteria, and they are not marked P0 or P1 except where a received P0 package repeats them.

The prompt also states:

- The application does not replace Odoo accounting.
- It is not a universal legal-compliance engine.
- A speculative difference must not be described as guaranteed recoverable cash.
- Odoo 19 Community is the master target.
- Odoo 18 and Odoo 20 are separate future targets.
- Financial correctness and multi-company isolation are release-blocking.
- Enterprise-only modules must not become mandatory dependencies.

Proposed commercial price: USD $599. Author, license text, and store listing copy were not supplied.

## Business-understanding backlog from section 6

Section 6 names 30 topics of planned business work. None of those studies is present as a finished document. Status of each item: **not performed**.

1. Core module purpose.
2. Customer contracts.
3. Price comparisons.
4. Historical versions.
5. Pricing rules.
6. Discount approvals.
7. Automated audits.
8. Case management.
9. Recovery and accounting.
10. Dashboards.
11. Evidence.
12. Notifications.
13. Multi-company security.
14. Configuration governance.
15. Business UAT.
16. Financial accuracy.
17. Performance.
18. Exception management.
19. Prevention.
20. Profitability.
21. Customer disputes.
22. Compliance.
23. Operational SOPs.
24. Reporting.
25. Competition and value proposition.
26. P0/P1 scope.
27. Acceptance.
28. Development roadmap.
29. Prompt roadmap.
30. Pre-development audit.

Item 30 is this step. It is drafted, not authorized.

## Truncation

The received prompt ends inside section 7 at the following bullets under **P0-C — Invoice Auditing**:

- Posted customer invoice eligibility.
- Invoice line-level comparison.
- Approved historical pricing.

The sentence "Prepare a normalized requirements register grouped into these ten packages" was received. Only P0-A, P0-B, and a fragment of P0-C were received. This package does not assign IDs P0-D through P0-J, because those titles were not received.

## What was not invented

- No claim that a full specification was read.
- No completed development percentage.
- No test result.
- No tolerance amount, FX formula, tax basis, pricing date, or approval matrix.
- No statement that the freight addon's design applies to customer contracts.
