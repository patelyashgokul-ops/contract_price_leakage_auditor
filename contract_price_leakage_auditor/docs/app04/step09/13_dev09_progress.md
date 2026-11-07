# DEV-09 progress

Addon `contract_price_leakage_auditor` version `19.0.1.7.0`. Odoo 19.0 Community (`version_info` 19, 0, 0, final). Business acceptance is pending. License remains `BLOCKER_LICENSE_DECISION_REQUIRED`. Release remains NO-GO. DEV-10 was not started.

Implementation status: `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING` after the green full-module runs recorded in `11_installation_regression.md`. Formal business acceptance still needs a reviewer.

## Task status

| Task | Status | Evidence |
| --- | --- | --- |
| DEV09-01 | COMPLETED | DEV-00 through DEV-08 models and the open DEC-06/07/08 decisions were reviewed. Prior-phase tests passed inside the 610-test runs. |
| DEV09-02 | COMPLETED | `sale.order.line.discount` and `product.pricelist.item` were read in the Odoo 19 Community tree. Neither is a dependency or a contract authority. |
| DEV09-03 | COMPLETED | Stacking runs only when the version names it. An empty limit blocks approval. Company `discount_approval_policy` is not operational. |
| DEV09-04 | COMPLETED | `01_discount_architecture.md`. |
| DEV09-05 | COMPLETED | `cpla.discount.concession`, `cpla.discount.approval`, `cpla.discount.event`. |
| DEV09-06 | COMPLETED | GOLD-DISC-002 = 1,140. |
| DEV09-07 | COMPLETED | GOLD-DISC-003 = 1,150. |
| DEV09-08 | COMPLETED | GOLD-DISC-001 = 1,150, with 25,000 authorized and 25,000 potential. |
| DEV09-09 | COMPLETED | GOLD-DISC-010 through GOLD-DISC-013. |
| DEV09-10 | COMPLETED | APP09-T001 through T003, T011, T012, T018. |
| DEV09-11 | COMPLETED | APP09-T006 through T008. |
| DEV09-12 | COMPLETED | APP09-T004 and T005. |
| DEV09-13 | COMPLETED | GOLD-DISC-014 exposure 25,000. Cross-currency and cross-unit approval refused. |
| DEV09-14 | COMPLETED | GOLD-DISC-004 and GOLD-DISC-005. Missing mode stays in review. |
| DEV09-15 | COMPLETED | GOLD-DISC-006. |
| DEV09-16 | COMPLETED | GOLD-DISC-018. |
| DEV09-17 | COMPLETED | Override request, exposure, and order-line scope. No sale-line write. |
| DEV09-18 | COMPLETED | Snapshot JSON, limit snapshot, and approved-term write refusal. |
| DEV09-19 | COMPLETED | HIS09-T011 and HIS09-T012. |
| DEV09-20 | COMPLETED | GOLD-DISC-017. Version retroactivity policy stays `not_authorized`. |
| DEV09-21 | COMPLETED | HIS09-T008 and the as-known half of GOLD-DISC-017. |
| DEV09-22 | COMPLETED | `cpla.discount.evaluator.evaluate`. |
| DEV09-23 | COMPLETED | INT09 and the resolver hook after a successful quantity result. |
| DEV09-24 | COMPLETED | Adjusted price only for the four authoritative statuses. |
| DEV09-25 | COMPLETED | `calculation_stages` and `discount_trace`. |
| DEV09-26 | COMPLETED | `08_discount_security_matrix.md` and SEC09. |
| DEV09-27 | COMPLETED | Approve, reject, submit, and event create check the server user. |
| DEV09-28 | COMPLETED | Discount page, approval form, three menus. `get_view` passed. No browser pass. |
| DEV09-29 | COMPLETED | DISC09-T001 through T016. |
| DEV09-30 | COMPLETED | Stacking and conflict tests inside DISC09 and GOLD-DISC-018. |
| DEV09-31 | COMPLETED | APP09 and SEC09. |
| DEV09-32 | COMPLETED | OVR09-T001 through T014. |
| DEV09-33 | COMPLETED | HIS09-T001 through T016. |
| DEV09-34 | COMPLETED | CON09 inside one transaction. No second worker. |
| DEV09-35 | COMPLETED | 0 failed, 0 error(s) of 610 tests on `cpla_dev09_20261028`. |
| DEV09-36 | COMPLETED | Upgrade of `cpla_dev08_20261028` and fresh `-i` of `cpla_dev09_fresh_20261028` are each 0 failed, 0 error(s) of 610 tests. |
| DEV09-37 | COMPLETED | DEV-06, DEV-07, and DEV-08 tests are inside the same 610. INT08-T008 still runs. |
| DEV09-38 | COMPLETED | `12_performance_review.md`. |
| DEV09-39 | COMPLETED | Traceability section below. |
| DEV09-40 | COMPLETED | `docs/app04/step09/` files 01 through 14. |
| DEV09-41 | COMPLETED | `14_dev10_handoff.md`. DEV-10 code was not added. |
| DEV09-42 | COMPLETED | This file. |

## Deferred

| Work | Status |
| --- | --- |
| Quotation warnings, override submission on a sales order, and confirmation blocking | `DEFERRED_TO_DEV10_DEV11_DEV12` |
| Invoice-source discount fields and sales-to-invoice changes | `DEFERRED_TO_DEV10_DEV11_DEV12` |
| Posted-invoice leakage findings | `DEFERRED_TO_DEV10_DEV11_DEV12` |
| Finance-case validation, recovery, waivers, settlements, and accounting adjustments | `DEFERRED_TO_DEV10_DEV11_DEV12` |
| Reassessment of an earlier finding after a retroactive approval | `DEFERRED_TO_DEV10_DEV11_DEV12` |
| Odoo 18 and Odoo 20 conversion | Not started. Not supported. |

## Requirements touched

P0-B, P0-E, P0-G, and P0-J are advanced for the discount foundation only.

CPL-C06, CPL-P01, CPL-P02, CPL-P03, CPL-P04, CPL-P06, CPL-P07, CPL-P08, CPL-P09, and CPL-P10 are implemented for an approved adjusted unit price. They are not closed for invoice audit.

FIN-01, FIN-02, FIN-03, FIN-05, FIN-06, FIN-07, FIN-08, and FIN-11 hold for this foundation. An authorized concession is excluded from `leakage_amount` because `leakage_amount` is still false. FIN-03 is not an invoice-audit completion.

SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-09, and SEC-10 hold for the new models. SEC-03 still separates finance approval of a discount request from contract ownership.

Invoice-audit requirements and recovery requirements are not complete.

## Defects closed during the run

| Defect | Evidence | Disposition |
| --- | --- | --- |
| Additional approval on a version with no limit | APP09-T015 error: unlimited approval was not granted. | Test now stores a 10 percent limit. The empty-limit guard stays. |
| Second amendment on the same effective date | UserError conflicting supersession. | Tests use the initial past snapshot, or the next day. The chronology rule stays. |
| Company mismatch reported as `not_applicable` | HIS09-T002 and SEC09. | Financial `COMPANY_ACCESS_DENIED` is now the discount status, with no prices. |
| Smoke test required write on every other contract-user model | `perm_write` false on `cpla.discount.event`. | The event row is named. Create and read stay. Write and unlink stay false. |

## Residual risks

- Business acceptance is pending. No reviewer signed this phase.
- License is still `BLOCKER_LICENSE_DECISION_REQUIRED`.
- DEC-06, DEC-07, and DEC-08 are open. Tolerance does not suppress a discount gap.
- Two-worker approval races were not executed.
- Forms were not clicked in a browser.
- Odoo 18 and Odoo 20 were not installed.
