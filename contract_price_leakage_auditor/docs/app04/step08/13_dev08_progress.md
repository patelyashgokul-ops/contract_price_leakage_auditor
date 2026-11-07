# DEV-08 progress

Addon `contract_price_leakage_auditor` version `19.0.1.6.0`. Odoo 19.0 Community tree. Business acceptance is pending. License remains `BLOCKER_LICENSE_DECISION_REQUIRED`. Release remains NO-GO. DEV-09 was not started.

## Task status

| Task | Status | Evidence |
| --- | --- | --- |
| DEV08-01 | COMPLETED | DEV-00 through DEV-07 models, tests, and open DEC-06/07/08 reviewed before code changes. |
| DEV08-02 | COMPLETED | `res.currency`, `res.currency.rate`, `_convert`, and `_get_rates` read in the Odoo 19 tree. `account.tax` exists only if Invoicing is installed and is not a dependency. |
| DEV08-03 | COMPLETED | Company candidates stay open. Only an explicit version clause normalizes. |
| DEV08-04 | COMPLETED | Normalization input and output live on `cpla.pricing.financial`. |
| DEV08-05 | COMPLETED | Same statuses documented in `01_financial_normalization_architecture.md`. |
| DEV08-06 | COMPLETED | Company, currency, approval, and forged request keys are checked. |
| DEV08-07 | COMPLETED | Exact date, prior date, and fixed rate. Document dates are review, not a silent invoice date. |
| DEV08-08 | COMPLETED | Root-company rate lookup. Other companies are not used. FX08-T005, SEC08-T002. |
| DEV08-09 | COMPLETED | Fixed multiplier. Market 84 does not replace fixed 83. FX08-T011. |
| DEV08-10 | COMPLETED | Multiply, divide, and company triangulation. FX08-T002, T003, T017. |
| DEV08-11 | COMPLETED | `MISSING_HISTORICAL_FX` with no price. FX08-T009. |
| DEV08-12 | COMPLETED | Snapshot fields frozen at approval. FX08-T013, T014. |
| DEV08-13 | COMPLETED | Contract, company, or explicit currency. Unconfigured does not assume company currency. |
| DEV08-14 | COMPLETED | Missing basis is `TAX_BASIS_REVIEW_REQUIRED`. |
| DEV08-15 | COMPLETED | One ordinary included percent. 1180 at 18 percent is 1000. |
| DEV08-16 | COMPLETED | Tax-excluded net stays the source amount. Tax component 0. |
| DEV08-17 | COMPLETED | Fiscal position returns review. Native mapping is deferred to DEV-11. |
| DEV08-18 | COMPLETED | Fixed, division, group, tax-on-tax, and complex return `UNSUPPORTED_TAX_STRUCTURE`. |
| DEV08-19 | COMPLETED | Decimal arithmetic. Currency increment is read from the currency. |
| DEV08-20 | COMPLETED | Preserve, per-unit, and extended stages. PREC08-T005 and T016. |
| DEV08-21 | COMPLETED | Signed difference only. No approved numeric tolerance. DEC-08 stays open. |
| DEV08-22 | COMPLETED | Cutoff, snapshot, and reassessment flag. HIS08-T003 and T004. |
| DEV08-23 | COMPLETED | `calculation_trace` and financial explanation. Discount text says none was applied. |
| DEV08-24 | COMPLETED | Resolver calls normalize after a successful quantity result. INT08-T001 through T004. |
| DEV08-25 | COMPLETED | SEC08-T001 through T012. |
| DEV08-26 | COMPLETED | Financial Clause page and applicability diagnostic fields. No new OWL client. |
| DEV08-27 | COMPLETED | FX08-T001 through T018 passed in upgrade3. |
| DEV08-28 | COMPLETED | TAX08-T001 through T015 and GOLD-TAX-003 passed in upgrade3. |
| DEV08-29 | COMPLETED | PREC08-T001 through T016 passed in upgrade3. |
| DEV08-30 | COMPLETED | HIS08-T001 through T006 passed in upgrade3. |
| DEV08-31 | COMPLETED | SEC08-T001 through T012 passed in upgrade3. |
| DEV08-32 | COMPLETED | INT08-T001 through T010 passed in upgrade3. |
| DEV08-33 | COMPLETED | Final log: 0 failed, 0 errors of 553 tests. |
| DEV08-34 | COMPLETED | Fresh `-i` of `cpla_dev08_20261028`: 0 failed of 552 tests. |
| DEV08-35 | COMPLETED | `-u` of `cpla_dev07_20261028`. First run failed two assertions. Final run passed 553. |
| DEV08-36 | COMPLETED | Prior tests are inside the 553 and passed. |
| DEV08-37 | COMPLETED | 30 calls measured at about 0.045 seconds. No QPS claim. |
| DEV08-38 | COMPLETED | Traceability table below. |
| DEV08-39 | COMPLETED | `docs/app04/step08/` files 01 through 14. |
| DEV08-40 | COMPLETED | `14_dev09_handoff.md`. DEV-09 code was not written. |
| DEV08-41 | COMPLETED | This file and the final report. |

## Traceability

| Item | Status |
| --- | --- |
| CPL-P05 / FIN-04 UoM compatibility | IMPLEMENTED. DEV-07 price is the FX source. |
| CPL-P06 / FIN-05 Historical FX | IMPLEMENTED for an explicit clause. Document-date FX is review-required. |
| CPL-P07 / FIN-06 Tax equivalence | IMPLEMENTED for excluded and one ordinary included percent. Complex tax is explicit review. |
| CPL-P08 / FIN-07 Precision | IMPLEMENTED. |
| CPL-P09 / FIN-08 Missing evidence | IMPLEMENTED. No invented rate, tax, or tolerance. |
| CPL-P10 / FIN-11 Reproducible calculation | IMPLEMENTED as a frozen version snapshot. |
| CPL-P04 / FIN-03 Discount separation | IMPLEMENTED as `discount_applied` false. Discount math is DEFERRED_TO_DEV09. |
| FIN-16 Reporting reconciliation | DEFERRED. Reporting currency is not selected. |
| SEC-01 Company isolation | IMPLEMENTED. |
| SEC-02 Confidential prices | IMPLEMENTED. Access errors do not return the price. |
| SEC-04 Approval authority | UNCHANGED. Finance manager still approves. Self-approval stays forbidden. |
| SEC-09 Unauthorized changes | IMPLEMENTED for snapshot fields and approved versions. |
| Invoice leakage findings | DEFERRED_TO_DEV12. |
| Invoice tax context | DEFERRED_TO_DEV11. |
| Reassessment cases | DEFERRED_TO_DEV14. |
| P0-B, P0-G, P0-J for this slice | IMPLEMENTED for the clause engine. Not a commercial release. |

## Odoo 18 and 20

Not converted. Risks to retest later: `_get_rates` future-row fallback, `inverse_company_rate` inverse methods, currency `rounding`, tax `compute_all` if a later phase depends on `account`, view expression syntax, and `has_group` versus `has_groups`. Odoo 19 behavior is not assumed to be stable in 18 or 20.

## Files

Added: `models/financial_normalization.py`, `tests/test_financial_normalization.py`, `docs/app04/step08/01` through `14`.

Modified: `models/__init__.py`, `models/pricing_applicability.py`, `__manifest__.py`, version-pin tests, smoke and security model lists, `tests/__init__.py`, `views/contract_version_views.xml`, `views/pricing_applicability_views.xml`, `local_testing/disposable_databases.txt`, `README.md`, `docs/README.md`, `DEVELOPMENT_PROGRESS.md`.

Not modified: step 00 through step 07 documents, the freight addon, license, depends, and approval groups.
