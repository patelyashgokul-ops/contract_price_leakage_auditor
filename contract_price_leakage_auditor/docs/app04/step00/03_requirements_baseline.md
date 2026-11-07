# 03 — Requirements baseline

Status of every row: requirement text **SPECIFIED** by the step 00 prompt. Product behavior **NOT_IMPLEMENTED**. No formal approval exists. Proposed business owner for every row: **UNASSIGNED**.

Priority P0 is the prompt's package label. It is not permission to build before the mapped decision is approved.

Source key: `P7` is prompt section 7. `P5` is the product-intent list in section 5. `P8` is section 8.

Columns used below: ID, business objective, expected result, dependencies, invariant, planned test. Workstream and priority sit in the section heading. Source is P7 unless noted.

Provisional IDs A-01–A-11, B-01–B-10, and C-01–C-03 are unchanged from the first-pass register. New bullets continue from C-04. Nothing approved was renumbered.

## P0-A — Contract governance

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| A-01 | Keep each contract inside one company. | A contract without `company_id` cannot be approved or used as a baseline. | `base`, `account` company rules. DEC-19. | SEC-01, FIN-08 | PLANNED-SEC-01 |
| A-02 | State which customers are covered. | Coverage is an explicit party list. A name match alone does not apply a price. | DEC-03. | SEC-02, FIN-01 | PLANNED-A-02 |
| A-03 | Match contract lines to products. | A line names the product scope it prices. Unmatched products do not inherit a silent price. | A-04, DEC-02. | FIN-01, FIN-08 | GOLD-FIN-008 |
| A-04 | Price variants separately when required. | A variant rule beats a template rule only under an approved precedence. Otherwise the result is a conflict, not a guess. | DEC-02. | FIN-08 | GOLD-FIN-007 |
| A-05 | Bound prices with effective dates. | A version applies only inside its effective interval, using the approved pricing date. | DEC-01. | FIN-01, FIN-02 | GOLD-FIN-002 |
| A-06 | Require approval before use. | Draft, rejected, and pending prices are not baselines. | DEC-11, SEC-04. | FIN-08, SEC-04 | PLANNED-A-06 |
| A-07 | Keep historical versions. | Past audits still resolve the version that was applicable on their pricing date. | A-05, A-09. | FIN-01, FIN-11 | GOLD-FIN-002 |
| A-08 | Represent amendments. | An amendment is a new version or an explicit change record. It does not erase the prior version. | A-07, DEC-02. | FIN-11 | PLANNED-A-08 |
| A-09 | Represent supersession. | After the supersession point, the old version is not the applicable price. It remains readable. | DEC-01. | FIN-01, FIN-11 | GOLD-FIN-002 |
| A-10 | Detect conflicts. | Two equally applicable approved prices produce `BUSINESS_REVIEW_REQUIRED` and no confirmed leakage. | DEC-02. | FIN-08 | GOLD-FIN-007 |
| A-11 | Point at contract evidence. | Approval and version records reference the evidence used. Missing required evidence blocks confirmation. | DEC-14, DEC-17. | SEC-06, SEC-10 | PLANNED-SEC-06 |

## P0-B — Pricing rules

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| B-01 | Apply a contract only inside its scope. | Company, party, product, dates, and approval all pass, or the line is not priced. | A-01, A-02, A-05, A-06. | FIN-01, FIN-02 | GOLD-FIN-008 |
| B-02 | Support quantity tiers. | The tier uses the approved quantity basis. A return that changes the tier is a separate case, not a hidden change. | DEC-04. | FIN-04, FIN-10 | GOLD-FIN-006 |
| B-03 | Convert compatible units. | Compatible units convert with the series UoM graph. Incompatible units are an exception and have no leakage amount. | DEC-19, UoM break in file 02. | FIN-04 | GOLD-FIN-003, GOLD-FIN-004 |
| B-04 | Convert currency only with historical evidence. | The result stores rate, date, company, and direction. A missing rate does not become a computed guess. | DEC-06. | FIN-05 | GOLD-FIN-003 |
| B-05 | Count only approved discounts. | The authorized discount is removed from gross difference. An extra unapproved reduction remains potential leakage. | DEC-05. | FIN-03 | GOLD-FIN-001 |
| B-06 | Normalize tax before comparing. | Tax-included and tax-excluded amounts are converted onto one declared basis. Mixed fields are not compared. | DEC-07. | FIN-06 | GOLD-FIN-005 |
| B-07 | Use approved monetary precision. | Money uses currency rounding. Quantity uses Product Unit precision. Product Price digits are not a second currency. | DEC-08. | FIN-07 | GOLD-FIN-003 |
| B-08 | Round explicitly. | The rounding mode and any tolerance are the approved policy. Float equality is not the oracle. | DEC-08. | FIN-07 | GOLD-FIN-003, GOLD-FIN-004 |
| B-09 | Declare the pricing date. | Invoice-date, order-date lock, and no-grandfathering are distinct policies. The fixture states which one it used. | DEC-01. | FIN-02 | GOLD-FIN-002 |
| B-10 | Refuse invented prices. | Missing or conflicting evidence yields an exception code and an empty expected price. | A-10, A-11. | FIN-08 | GOLD-FIN-007, GOLD-FIN-008 |

## P0-C — Invoice auditing

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| C-01 | Audit posted customer invoices. | Population starts at `state = posted` and `move_type = out_invoice`. Draft and cancel are out. | DEC-09. | FIN-15 | PLANNED-C-01 |
| C-02 | Compare at line level. | Each product line is compared. Header totals do not replace the line. | C-01, I-16 display-line rule in file 05. | FIN-16 | PLANNED-C-02 |
| C-03 | Use the approved historical price. | Today's partner pricelist is not the baseline. | A-07, B-09. | FIN-01, FIN-02 | GOLD-FIN-002 |
| C-04 | Detect missed price increases. | When the historical applicable price is higher than the invoice and the increase was already in force, the gap is potential underpricing, not an automatic recovery. | DEC-01, B-05. | FIN-02, FIN-12 | GOLD-FIN-002 |
| C-05 | Detect unauthorized discounts. | A reduction beyond the approved special price or approved percent is potential unauthorized leakage. | DEC-05. | FIN-03 | GOLD-FIN-001, GOLD-FIN-003 |
| C-06 | Handle returns and credit notes. | Returned quantity reduces eligible quantity only under the approved return rule. A credit note is not recovered cash. | DEC-09, DEC-13. | FIN-10, FIN-13 | GOLD-FIN-006, GOLD-REC-001 |
| C-07 | Handle partial invoices. | Only the invoiced eligible quantity on the posted line is compared. Uninvoiced order quantity is not leakage by itself. | DEC-09, DEV-10 boundary. | FIN-10 | PLANNED-C-07 |
| C-08 | Prevent duplicate findings. | One current financial exposure exists for the same underlying issue. | DEC-10. | FIN-09 | GOLD-FIN-009 |
| C-09 | Support re-audit. | A repeated run with unchanged source and policy does not create a second exposure. A real source or policy change reassesses under OPS-09. | C-08, H-02. | FIN-09, FIN-11, OPS-02 | GOLD-FIN-009 |
| C-10 | Trace source documents. | Each finding stores move id, line id, contract version id, and the input values used. | F-02. | FIN-11, SEC-10 | PLANNED-C-10 |

## P0-D — Leakage cases

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| D-01 | Record potential leakage. | The amount is labeled potential until finance validation. It is not cash and not waived. | C-05, FIN-12. | FIN-12 | GOLD-FIN-001 |
| D-02 | Investigate financially. | An investigation case is separate from the technical audit log. | OPS-05. | OPS-05, SEC-03 | PLANNED-D-02 |
| D-03 | Hold missing and conflicting contracts. | Results are `CONTRACT_COVERAGE_EXCEPTION` or `BUSINESS_REVIEW_REQUIRED`. Confirmed leakage stays empty. | B-10. | FIN-08 | GOLD-FIN-007, GOLD-FIN-008 |
| D-04 | Validate through finance. | Only a finance action moves potential leakage to finance-validated leakage. | DEC-11, SEC-03. | FIN-12, SEC-04 | GOLD-REC-001 |
| D-05 | Clear findings explicitly. | A cleared finding keeps its original amount and records the clearing reason. It is not deleted. | D-08. | FIN-11 | PLANNED-D-05 |
| D-06 | Assign cases. | Assignment does not grant approval authority. | SEC-03, SEC-11. | SEC-03 | PLANNED-SEC-03 |
| D-07 | Reassess when inputs change. | Reassessment creates a revision and keeps the prior decision. | OPS-09. | FIN-11 | PLANNED-D-07 |
| D-08 | Keep original decision history. | Prior potential, validated, waived, and recovered figures remain readable. | SEC-10. | FIN-11, SEC-10 | PLANNED-SEC-10 |
| D-09 | Attach financial evidence to the case. | Evidence is company-bound and referenced by the decision that used it. | DEC-14. | SEC-06 | PLANNED-SEC-06 |

## P0-E — Recovery and disputes

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| E-01 | Propose recovery separately from leakage. | A proposal cannot exceed finance-validated leakage minus approved waivers. | D-04, DEC-11. | FIN-12 | GOLD-REC-001 |
| E-02 | Approve recovery on a matrix. | Approval records the matrix rule and the approver. | DEC-11. | SEC-04, SEC-05 | PLANNED-SEC-04 |
| E-03 | Record waivers. | An approved waiver reduces the recovery target and is not recovered cash. | DEC-12. | FIN-12 | GOLD-REC-001 |
| E-04 | Prevent self-approval. | The proposer cannot be the sole approver of that proposal or waiver. | DEC-11, DEC-12. | SEC-05 | PLANNED-SEC-05 |
| E-05 | Record customer disputes. | A dispute references the finding and does not change validated leakage by itself. | E-01. | FIN-11 | PLANNED-E-05 |
| E-06 | Keep settlement evidence. | Settlement amounts cite evidence. Conversation text alone is not verified cash. | DEC-13. | FIN-13, SEC-06 | GOLD-REC-001 |
| E-07 | Allow partial recovery. | Billed, collected, and outstanding are stored as separate figures. | F-03, F-04, F-05. | FIN-12, FIN-13 | GOLD-REC-001 |
| E-08 | Use approval matrices. | Thresholds and roles come from an approved matrix. No matrix means no financial approval. | DEC-11, DEC-12. | SEC-04 | PLANNED-SEC-04 |

## P0-F — Accounting and reconciliation

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| F-01 | Link authorized adjustments. | APP 04 stores a reference to an existing posted document. It does not post a move in this baseline. | DEC-13. Creating moves is not authorized. | FIN-15 | PLANNED-F-01 |
| F-02 | Reference posted documents. | Invoice, credit note, and payment links store database ids and the company. | C-10. | FIN-11, SEC-01 | PLANNED-C-10 |
| F-03 | Track recovery billed. | Billed amount is the posted billing document's applicable net. It is not cash. | DEC-13. | FIN-13 | GOLD-REC-001 |
| F-04 | Track verified net cash. | Cash is recognized only from the approved payment evidence, net of reversals. | DEC-13. | FIN-13, FIN-14 | GOLD-FIN-010, GOLD-REC-001 |
| F-05 | Track outstanding recovery. | Outstanding approved recovery equals approved target minus verified net cash. | E-07. | FIN-12 | GOLD-REC-001 |
| F-06 | Reassess reversed payments. | A reversed verified collection reduces verified cash and increases outstanding. | DEC-13. | FIN-14 | GOLD-FIN-010 |
| F-07 | Keep credit notes distinct. | A customer credit note reduces eligible exposure or is settlement evidence only when the approved rule says so. It is not automatically cash. | C-06, DEC-09. | FIN-10, FIN-13 | GOLD-FIN-006 |
| F-08 | Separate tax from revenue recovery. | Tax on a recovery document is reported apart from net revenue recovery. | DEC-07. | FIN-06 | GOLD-REC-001 |

## P0-G — Security and evidence

IDs use `PG-` so they are not confused with release gates G01–G15.

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| PG-01 | Enforce role-based access. | Each action checks a group. A hidden menu is not the control. | DEC-11, SEC-11. | SEC-11 | PLANNED-SEC-11 |
| PG-02 | Isolate companies. | Record rules and tests block cross-company read and write, including from the ORM. | A-01. | SEC-01 | PLANNED-SEC-01 |
| PG-03 | Keep contract prices confidential. | Users without the pricing group cannot read prices, exports, or chatter payloads that contain them. | SEC-02. | SEC-02, SEC-12 | PLANNED-SEC-02 |
| PG-04 | Restrict financial actions. | Validate, waive, bill, and cash-verify are separate privileges. | SEC-03. | SEC-03 | PLANNED-SEC-03 |
| PG-05 | Restrict attachments and exports. | Download and export rights are explicit. Portal users do not receive contract prices. | `account` portal dependency. | SEC-06, SEC-07 | PLANNED-SEC-06, PLANNED-SEC-07 |
| PG-06 | Keep approval history. | Approver, timestamp, from-state, to-state, and comment are stored and not rewritten. | SEC-10. | SEC-10 | PLANNED-SEC-10 |
| PG-07 | Keep historical evidence available to the audit that used it. | Superseded evidence remains readable to authorized users of that company. | A-07. | FIN-11, SEC-09 | PLANNED-SEC-09 |
| PG-08 | Respect retention and legal hold. | A hold blocks destruction. The policy itself is DEC-17 and is not invented here. | DEC-17. | SEC-09 | PLANNED-SEC-09 |

## P0-H — Audit operations

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| H-01 | Run scheduled audits. | A cron names its company and its scope. Failure is visible. | `ir.cron`, DEC-16. | OPS-08, SEC-08 | PLANNED-OPS-08 |
| H-02 | Run incremental audits. | The increment definition is stable. A line is not skipped and also not double-counted. | DEC-10. | OPS-01, FIN-09 | PLANNED-OPS-01 |
| H-03 | Process historical batches. | A batch has an explicit as-of policy and checkpoint. | OPS-04. | OPS-04, OPS-10 | PLANNED-OPS-04 |
| H-04 | Retry and resume. | Interrupted work continues from committed checkpoints. Unprocessed lines are not marked audited. | OPS-06. | OPS-04, OPS-06 | PLANNED-OPS-04 |
| H-05 | Protect concurrency. | Two workers do not create two current exposures or two recovery billings. | FIN-09. | OPS-03 | GOLD-FIN-009, PLANNED-OPS-03 |
| H-06 | Classify technical failures apart from business exceptions. | A crash is not `CONTRACT_COVERAGE_EXCEPTION`. A missing contract is not a traceback. | OPS-05. | OPS-05 | PLANNED-OPS-05 |
| H-07 | Govern notifications. | Recipients, company, and content rules are configured. Price data is not mailed to an unauthorized party. | SEC-12, DEC-16. | SEC-12 | PLANNED-SEC-12 |
| H-08 | Monitor operations. | Backlog, failure, and progress categories reconcile to the eligible set. | OPS-07, OPS-08. | OPS-07, OPS-08 | PLANNED-OPS-07 |

## P0-I — Reports

IDs use `RPT-`.

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| RPT-01 | Show an executive dashboard. | Figures drill to findings and match the source ledger for the same as-of timestamp. | FIN-16, OPS-10. | FIN-16, OPS-10 | PLANNED-RPT-01 |
| RPT-02 | Show a finance investigation dashboard. | Counts of potential, exception, validated, waived, and outstanding reconcile to cases. | D-01, E-07. | FIN-12, FIN-16 | PLANNED-RPT-02 |
| RPT-03 | Report contract coverage. | Lines with no contract are coverage exceptions, not zero leakage. | D-03. | FIN-08 | GOLD-FIN-008 |
| RPT-04 | Report recovery. | Billed, cash, waived, and outstanding match GOLD-REC equations on the fixture. | F-03, F-04, F-05. | FIN-13 | GOLD-REC-001 |
| RPT-05 | Report audit coverage. | Audited, failed, unprocessed, and excluded reconcile to the eligible population. | OPS-07. | OPS-06, OPS-07 | PLANNED-OPS-07 |
| RPT-06 | Break down by customer and product. | Totals equal the sum of the same findings. No cross-company rows. | SEC-01. | SEC-01, FIN-16 | PLANNED-SEC-01 |
| RPT-07 | Define financial KPIs. | Each KPI names numerator, denominator, currency treatment, and as-of rule before it is shown. | OPS-10. | FIN-16 | PLANNED-RPT-07 |
| RPT-08 | Snapshot historical reports. | A snapshot records policy version and does not change when today's contract changes. | FIN-11. | FIN-11, OPS-10 | PLANNED-RPT-08 |
| RPT-09 | Control PDF, XLSX, and CSV exports. | Export requires SEC-07. PDF runtime and XLSX library stay REQUIRES_VALIDATION. | File 02. | SEC-07 | PLANNED-SEC-07 |

## P0-J — Release readiness

IDs use `PJ-`.

| ID | Business objective | Expected result | Dependencies | Invariant | Planned test |
| --- | --- | --- | --- | --- | --- |
| PJ-01 | Install on Community without Enterprise. | Fresh install with the approved dependency set succeeds. | DEC-19. | G13 | PLANNED-PJ-01 |
| PJ-02 | Validate install and upgrade. | Install and a later upgrade pass on a disposable database. | PJ-01. | G13 | PLANNED-PJ-02 |
| PJ-03 | Ship demo data that cannot be mistaken for a customer. | Demo uses synthetic companies and the golden numbers. It does not require `l10n_generic_coa`. | File 02. | SEC-12 | PLANNED-PJ-03 |
| PJ-04 | Explain configuration. | The guide names every undecided policy that an administrator must not invent. | DEC-01–DEC-20. | G15 | PLANNED-PJ-04 |
| PJ-05 | Explain user work. | Users can distinguish potential leakage, waiver, billed recovery, and cash. | FIN-12, FIN-13. | G07 | PLANNED-PJ-05 |
| PJ-06 | Run financial regression. | GOLD-FIN and GOLD-REC are automated on Odoo 19 before release. | File 05. | G01–G09 | GOLD-FIN-001–010, GOLD-REC-001 |
| PJ-07 | Run security tests. | SEC planned tests pass, including ORM cross-company access. | File 06. | G10 | PLANNED-SEC-01–12 |
| PJ-08 | Measure performance. | Volume cases are timed on a stated database. Untimed claims are forbidden. | DEC-18. | G11 | PLANNED-VOL-5000 through PLANNED-VOL-1000000 |
| PJ-09 | Complete business UAT. | UAT scripts trace to requirement IDs. Verbal acceptance is not enough. | G14. | G14 | PLANNED-UAT |
| PJ-10 | Package for distribution. | License, third-party notices, and series are stated. Missing license blocks the package. | LEGAL review. | G15 | PLANNED-PJ-10 |
| PJ-11 | Approve each Odoo version separately. | 19, 18, and 20 each need their own release record. Absence of a record means not supported. | File 09. | G15 | PLANNED-PJ-11 |

## P1 backlog

These are not P0. Promoting any row requires a documented business approval that does not yet exist.

| ID | Area | Source | Priority | Phase | Status |
| --- | --- | --- | --- | --- | --- |
| P1-01 | Advanced historical COGS attribution | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-02 | Customer profitability allocation | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-03 | Predictive pricing risk scoring | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-04 | Prevention ROI attribution | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-05 | Commodity-index formulas | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-06 | Dispute negotiation analytics | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-07 | Advanced executive BI | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-08 | Complex SLA calendars | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-09 | Optional external integrations | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |
| P1-10 | Contract onboarding assistants | P8 | P1 | Not assigned | NOT_IMPLEMENTED. Not approved. |

## Explicit exclusions

| ID | Exclusion | What this means |
| --- | --- | --- |
| X-01 | Full ERP replacement | APP 04 does not become the accounting system. |
| X-02 | Universal tax filing automation | Tax normalization for a price comparison is not a filing engine. |
| X-03 | Guaranteed legal recovery | A finding is not a legal entitlement to cash. |
| X-04 | General litigation management | Disputes in E-05 are pricing disputes, not a case-management suite for lawsuits. |
| X-05 | Complete debt-collection platform | Outstanding recovery is not a collections product. |
| X-06 | Generic AI pricing optimization | No model suggests or changes selling prices in this product. |
| X-07 | Untested Odoo versions | Only a version with its own passed release record may be called supported. Today none are supported. |

## Coverage notes

Section 5 capabilities SC-01 through SC-18 from the first-pass inventory are covered by the P0 rows above or by P1/X rows. DEV-10 (sales quotation controls) is a roadmap phase. The only supplied quotation-related rule is the order-date price-lock inside GOLD-FIN-002. No additional quotation requirement was invented.

Verification status for the whole baseline: **SPECIFIED**, **NOT_IMPLEMENTED**, approvals **absent**.
