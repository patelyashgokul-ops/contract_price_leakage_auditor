# 05 — Financial invariants and golden tests

APP 04 has no calculation code. Every FIN row is **NOT_IMPLEMENTED**. The rule text is specified by prompt section 12. Platform facts that support a later test are marked source-verified in the note. That is not a test pass.

No row is TESTED_PASS, TESTED_FAIL, IMPLEMENTED_UNVERIFIED, or SOURCE_VERIFIED as an APP 04 control.

**TEST EXECUTION: NOT PERFORMED — DEV-00 PLANNING ONLY.**

## FIN-01 through FIN-16

| ID | Rule | Status | Platform evidence | Planned test |
| --- | --- | --- | --- | --- |
| FIN-01 | Select the correct historical contract version. | NOT_IMPLEMENTED | `product.pricelist` has dates and optional company. It has no approval or supersession chain. Partner pricelist is current, not historical. | GOLD-FIN-002 |
| FIN-02 | Apply the approved pricing-date rule. | NOT_IMPLEMENTED | `account.move.invoice_date` exists. Which date governs is DEC-01, status not approved. | GOLD-FIN-002 |
| FIN-03 | Exclude approved discounts from unauthorized leakage. | NOT_IMPLEMENTED | `account.move.line.discount` exists. Stacking rules are DEC-05. | GOLD-FIN-001, GOLD-FIN-003 |
| FIN-04 | Normalize comparable UoM values. | NOT_IMPLEMENTED | Odoo 18 uses categories. Odoo 19 and 20 use `relative_uom_id`. Odoo 20 has no `uom.rounding` field. | GOLD-FIN-003, GOLD-FIN-004 |
| FIN-05 | Apply a verified historical currency policy. | NOT_IMPLEMENTED | `res.currency.rate` is dated and company-scoped. `account.move.invoice_currency_rate` exists on Odoo 19. Source choice is DEC-06. | GOLD-FIN-003 |
| FIN-06 | Normalize tax-inclusive and tax-exclusive prices. | NOT_IMPLEMENTED | `price_include` is computed. `price_include_override` is `tax_included` or `tax_excluded`. Basis is DEC-07. | GOLD-FIN-005 |
| FIN-07 | Respect approved precision and tolerance. | NOT_IMPLEMENTED | Currency `rounding` and `decimal_places` exist. Shipped Product Price, Discount, and Product Unit digits are 2 and can be changed. Tolerance amount is DEC-08. | GOLD-FIN-003, GOLD-FIN-004 |
| FIN-08 | Missing or conflicting evidence cannot become confirmed leakage. | NOT_IMPLEMENTED | No APP 04 exception model exists. | GOLD-FIN-007, GOLD-FIN-008 |
| FIN-09 | One current financial exposure for the same underlying issue. | NOT_IMPLEMENTED | Identity key is DEC-10. | GOLD-FIN-009 |
| FIN-10 | Handle reversals, returns, and credit notes. | NOT_IMPLEMENTED | `out_refund` exists. Eligibility detail is DEC-09. | GOLD-FIN-006 |
| FIN-11 | Preserve original and revised audit evidence. | NOT_IMPLEMENTED | No audit record exists to revise. | PLANNED-D-07 |
| FIN-12 | Keep validated leakage, waived amount, and approved recovery distinct. | NOT_IMPLEMENTED | No ledger exists. | GOLD-REC-001 |
| FIN-13 | Billing is not cash collection. | NOT_IMPLEMENTED | `payment_state` values include `paid` and `partial`. Paying the original invoice is not leakage recovery. | GOLD-REC-001 |
| FIN-14 | Reversed payments are not left as verified cash. | NOT_IMPLEMENTED | `account.partial.reconcile` exists in Community `account`. | GOLD-FIN-010 |
| FIN-15 | Do not silently rewrite posted financial documents. | NOT_IMPLEMENTED | No APP 04 write path exists. The prohibition still binds later phases. | PLANNED-F-01 |
| FIN-16 | Dashboards and source records reconcile. | NOT_IMPLEMENTED | Community `account.invoice.report` is not a leakage ledger. Enterprise `account_reports` is absent. | PLANNED-RPT-01 |

Display lines are not merchandise lines. `account.move.line.display_type` separates sections, notes, and tax lines from product lines. Only product lines enter a price comparison. This is a constraint on C-02, not a seventeenth FIN id.

## Golden fixture common rules

- Currency labels INR and USD are fixture names. Tests must create the currencies. Rounding 0.01 is assumed only where the prompt's arithmetic is exact to the paisa.
- Results are potential until finance validation, except where the fixture states an exception code or a zero.
- Reviewer for every fixture: **UNASSIGNED**.
- Version applicability: specified against Odoo 19 field names. Odoo 18 and 20 are not covered until UoM and tax fixtures are re-expressed. No series is supported today.
- Automated test: not written.

## GOLD-FIN-001 — Approved special discount

| Item | Value |
| --- | --- |
| Source rule | B-05, C-05, D-01, FIN-03, FIN-12 |
| Inputs | Base contract INR 1,200 / piece. Approved special price INR 1,150 / piece. Invoice INR 1,100 / piece. Quantity 500 pieces. Same company, UoM, currency, and tax basis. |
| Assumptions | No tier change. No FX. No tax gross-up. Special price is the approved net. The INR 50 cut from 1,200 to 1,150 is authorized. The further INR 50 is not. |
| Gross contract difference | (1,200 − 1,100) × 500 = INR 50,000 |
| Authorized discount | (1,200 − 1,150) × 500 = INR 25,000 |
| Potential unauthorized leakage | (1,150 − 1,100) × 500 = INR 25,000 |
| Financial status | Potential leakage. Not finance-validated. Not cash. |
| Edge cases | Expired special price. Second discount stacked (DEC-05). Quantity that crosses a tier (DEC-04). |
| Planned test | `tests/test_gold_fin_001.py`, not created. |

## GOLD-FIN-002 — Historical grandfathering

| Item | Value |
| --- | --- |
| Source rule | A-05, A-07, A-09, B-09, C-03, C-04, FIN-01, FIN-02 |
| Inputs | V1 INR 1,000. V2 INR 1,200 effective from 1 July 2026. Order confirmed before 1 July 2026. Invoice price INR 1,000. |
| Policy for this numeric case | Order-date price-lock, and that lock is explicitly verified. |
| Applicable price | INR 1,000 |
| Unauthorized leakage | 0 |
| Assumptions | "Effective from 1 July" means 1 July uses V2. Time zone is not specified. The lock must be evidenced. A mere earlier quotation date without the verified rule does not grandfather. |

Separate planned cases, applicable price only. Invoice amounts for these variants were not supplied, so leakage amounts are not invented.

| Variant | Policy | Pricing date | Applicable price |
| --- | --- | --- | --- |
| GOLD-FIN-002A | Invoice date | Before 1 July 2026 | INR 1,000 |
| GOLD-FIN-002A | Invoice date | On or after 1 July 2026 | INR 1,200 |
| GOLD-FIN-002B | No grandfathering | On or after 1 July 2026 | INR 1,200 |

Edge cases: order before the date and invoice after it. Unverified lock. V2 effective time at midnight. Company time zone.

## GOLD-FIN-003 — USD, UoM, and discount

| Item | Value |
| --- | --- |
| Source rule | B-03, B-04, B-05, B-07, FIN-03, FIN-04, FIN-05 |
| Inputs | Contract USD 120 / box. 1 box = 10 pieces. Approved FX INR 84 per USD. Approved discount 5%. Invoice INR 950 / piece. Quantity 100 pieces. |
| Order of operations, as specified | Convert, then split the box, then apply the percent: 120 × 84 ÷ 10 = INR 1,008 before discount. 1,008 × 0.95 = INR 957.60 after discount. |
| Potential leakage | (957.60 − 950) × 100 = INR 760 |
| Assumptions | The 84 rate is approved historical evidence, not a live rate. 957.60 is exact at 0.01. A different rounding stage would be a different policy and is not this fixture. Units share one UoM chain. |
| Financial status | Potential leakage. |
| Edge cases | Missing rate. Rate from another company. Discount stacked. Box size changed after invoicing. Odoo 18 category boundary. |

## GOLD-FIN-004 — UoM conversion

| Item | Value |
| --- | --- |
| Source rule | B-03, FIN-04 |
| Inputs | INR 2,400 / box. 1 box = 12 pieces. Invoice INR 190 / piece. Quantity 100 pieces. Same currency. No discount. No tax adjustment. |
| Expected unit price | 2,400 ÷ 12 = INR 200 / piece |
| Potential leakage | (200 − 190) × 100 = INR 1,000 |
| Edge cases | Incompatible units produce an exception and no amount. Non-divisible factors. Odoo 20 code must not read `uom.rounding`. |

## GOLD-FIN-005 — Tax normalization

| Item | Value |
| --- | --- |
| Source rule | B-06, FIN-06 |
| Inputs | Contract net INR 1,000. Invoice gross INR 1,062. Stated invoice net INR 900. Quantity 100. |
| Arithmetic check | 900 × 1.18 = 1,062. This holds only for a single 18% included percent tax and no other tax. |
| Difference | (1,000 − 900) × 100 = INR 10,000 |
| Assumptions | The 18% treatment is illustrative. It is not validated for a live tax configuration. Fiscal positions, tax groups, and `division` taxes are outside this fixture. |
| Financial status | Potential difference on the net basis stated above. Not confirmed for a real tax setup. |
| Edge cases | Tax excluded invoice. Multiple taxes. Price-included override disagreeing with the company default. |

## GOLD-FIN-006 — Partial return

| Item | Value |
| --- | --- |
| Source rule | C-06, B-02, FIN-10 |
| Inputs | Underbilling INR 50 / piece. Invoiced quantity 100. Fully returned quantity 20. No tier repricing and no other adjustment. |
| Eligible quantity | 80 |
| Remaining exposure | 50 × 80 = INR 4,000 |
| Assumptions | The return is fully credited for those 20 pieces. The credit note is not cash recovered. |
| Edge case | A return that drops the remaining quantity into another tier. Expected result for that case is not numeric until DEC-04 is approved. Planned id: GOLD-FIN-006A, blocked on DEC-04. |

## GOLD-FIN-007 — Contract conflict

| Item | Value |
| --- | --- |
| Source rule | A-10, B-10, FIN-08 |
| Inputs | Two equally applicable approved prices. No verified precedence. |
| Expected result | `BUSINESS_REVIEW_REQUIRED`. Confirmed leakage is empty. |
| Edge cases | A later approved precedence rule may reassess. It must not rewrite the original exception. |

## GOLD-FIN-008 — Missing contract

| Item | Value |
| --- | --- |
| Source rule | B-10, D-03, FIN-08 |
| Inputs | No verified applicable contract and no approved alternative pricing policy. |
| Expected result | `CONTRACT_COVERAGE_EXCEPTION`. No invented expected price. |
| Edge cases | A current pricelist exists. It is still not a fallback. |

## GOLD-FIN-009 — Repeated audit

| Item | Value |
| --- | --- |
| Source rule | C-08, C-09, FIN-09, OPS-02 |
| Inputs | Same invoice line, unchanged source, unchanged policy, more than one audit run. |
| Expected result | One unique current financial exposure. |
| Edge cases | Concurrent workers (OPS-03). A changed contract version is a reassessment, not a duplicate (OPS-09). |

## GOLD-FIN-010 — Payment reversal

| Item | Value |
| --- | --- |
| Source rule | F-04, F-06, FIN-14 |
| Inputs | A previously verified cash recovery is reversed. |
| Expected result | Verified cash decreases and outstanding recovery increases by the reversed verified amount. The original verification record remains history. |
| Assumptions | The amount reversed is the verified portion, not an unrelated customer payment of the original invoice. |
| Edge cases | Partial reversal. Reversal in another currency. Reversal posted in another company. |

## GOLD-REC-001 — Recovery lifecycle

| Item | Value |
| --- | --- |
| Source rule | D-04, E-01, E-03, E-07, F-03, F-04, F-05, F-08, FIN-12, FIN-13 |
| Finance-validated leakage | INR 25,000 |
| Approved waiver | INR 5,000 |
| Approved recovery target | INR 20,000 |
| Recovery billed | INR 20,000 |
| Verified net cash | INR 12,000 |
| Remaining approved recovery | INR 8,000 |
| Equations | 25,000 = 5,000 + 20,000. 20,000 = 12,000 + 8,000. |

Required conclusions:

- Billed recovery is not cash recovered.
- Waived amount is not recovered cash.
- Tax on the recovery document is reported apart from net revenue recovery. This fixture states no tax component, so the tax line is zero and still separate.
- A credit note is not automatically recovered cash.
- Repeating the billing operation must not create a second INR 20,000 billed amount.
- A later payment reversal adjusts the INR 12,000 and the INR 8,000. See GOLD-FIN-010.

Independent check, still not executed: a finance reviewer recomputes the two equations from stored fields, and an accounting reviewer matches billed and cash figures to posted Community document ids. Reviewer: UNASSIGNED.

## Blocked numeric work

DEC-01, DEC-04, DEC-05, DEC-06, DEC-07, DEC-08, DEC-09, DEC-10, and DEC-13 are not approved. Fixtures above use only the numbers and policies the prompt stated. They do not fill those decisions for other transactions.
