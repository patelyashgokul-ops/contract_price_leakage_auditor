# DEV-10 progress

Addon `contract_price_leakage_auditor` version `19.0.1.8.0`. Odoo 19.0 Community (`version_info` `(19, 0, 0, final, 0, '')`). Business acceptance is pending. License remains `BLOCKER_LICENSE_DECISION_REQUIRED`. Release remains NO-GO. DEV-11 was not started.

Implementation status: `IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING` after the green runs in `11_installation_upgrade_regression.md`. Formal business acceptance still needs a reviewer.

The full tag on `cpla_dev10_20261028` and the upgrade of `cpla_dev09_20261028` passed before the registry assertion was relaxed from equality to a subset. The fresh rerun passed the final assertion: 0 failed, 0 errors of 676 tests.

## Task status

| Task | Status | Evidence |
| --- | --- | --- |
| DEV10-01 | COMPLETED | DEV-00 through DEV-09 models were reviewed. Prior tests pass inside the 676. |
| DEV10-02 | COMPLETED | Odoo 19 `sale.order` and `sale.order.line` were read. `action_confirm` writes state and `date_order` before `_action_confirm`. |
| DEV10-03 | COMPLETED | Gate runs before `super()`. Failed validation does not store a lock. |
| DEV10-04 | COMPLETED | `quotation_compliance_mode` on the company policy. Default `unconfigured`. Not an approved rule. |
| DEV10-05 | COMPLETED | `01_sales_quotation_architecture.md`. |
| DEV10-06 | COMPLETED | Evaluator dict. `leakage_amount` and `is_recovered_cash` stay false. |
| DEV10-07 | COMPLETED | Product, section, note, down payment, delivery, reward, discount, combo, expense. |
| DEV10-08 | COMPLETED | `price_unit × (1 - discount / 100)`. |
| DEV10-09 | COMPLETED | Resolver call. Forged prices are still dropped by the resolver. |
| DEV10-10 | COMPLETED | Quantity and both UoM ids come from the sales line. Invoice quantity is not invented. |
| DEV10-11 | COMPLETED | Financial normalizer. Non-success becomes missing evidence. |
| DEV10-12 | COMPLETED | Discount evaluator. Authoritative statuses only. |
| DEV10-13 | COMPLETED | Thirteen statuses in `03_compliance_status_policy.md`. |
| DEV10-14 | COMPLETED | Additional exposure. Special-price case is 25,000, not 50,000. |
| DEV10-15 | COMPLETED | Company modes. Missing contract is not a universal block. |
| DEV10-16 | COMPLETED | Order summary. Incompatible currencies are not summed. |
| DEV10-17 | COMPLETED | Wizard creates a draft `transaction_override` only. |
| DEV10-18 | COMPLETED | Sale order and line links plus the material fingerprint. |
| DEV10-19 | COMPLETED | Price, quantity, product, customer, and currency changes re-evaluate. |
| DEV10-20 | COMPLETED | `action_confirm` raises `UserError` before `super()`. |
| DEV10-21 | COMPLETED | Direct call and batch call use the same method. `skip_price_check` is not read. |
| DEV10-22 | COMPLETED | `cpla.sale.price.lock`. One row per line. |
| DEV10-23 | COMPLETED | Order-date candidate only when the version snapshot is `order_confirmation`. |
| DEV10-24 | COMPLETED | Original row kept. `revalidation_required` on a material change. |
| DEV10-25 | COMPLETED | Global company rules. Cross-company approval rejected. |
| DEV10-26 | COMPLETED | `views/sale_quotation_views.xml`. |
| DEV10-27 | COMPLETED | PRICE10 tests passed. |
| DEV10-28 | COMPLETED | CONF10 and APP10 tests passed. |
| DEV10-29 | COMPLETED | HIS10 tests passed. |
| DEV10-30 | COMPLETED | SEC10 tests passed. |
| DEV10-31 | COMPLETED | Sequential CON10 tests passed. Two sessions were not run. |
| DEV10-32 | COMPLETED | Class 66 and full 676 on `cpla_dev10_20261028`. |
| DEV10-33 | COMPLETED | Fresh database. Final rerun 0 failed of 676. |
| DEV10-34 | COMPLETED | Upgrade of `cpla_dev09_20261028`, 0 failed of 676. |
| DEV10-35 | COMPLETED | Prior-phase tests inside those 676. |
| DEV10-36 | COMPLETED | `12_performance_findings.md`. No queries-per-second claim. |
| DEV10-37 | COMPLETED | Traceability in this file. Invoice audit is not complete. |
| DEV10-38 | COMPLETED | `docs/app04/step10/` files 01 through 14. |
| DEV10-39 | COMPLETED | `14_dev11_handoff.md`. |
| DEV10-40 | COMPLETED | This file and the final report. |

## Deferred

| Work | Status |
| --- | --- |
| Posted-invoice comparison and invoice-line allocation | Deferred to DEV-11 and later. Not started. |
| Leakage findings, finance validation, recovery, waivers, debit notes | Not started. |
| Invoice-audit cron and executive dashboard | Not started. |
| Two-session confirmation race | Not executed. |
| Odoo 18 and Odoo 20 conversion | Not started. |

## Requirements touched

P0-B, P0-E, P0-G, and P0-J are advanced for quotation compliance only.

CPL-C04, CPL-C06, and CPL-C08 are reused. The confirmed lock stores the version and the pricing-date snapshot. CPL-C08 is not an invoice-date engine.

CPL-P03, CPL-P04, CPL-P05, CPL-P06, CPL-P07, CPL-P08, CPL-P09, and CPL-P10 are reused for the quotation comparison. They are not closed for invoice audit.

FIN-01, FIN-02, FIN-03, FIN-04, FIN-05, FIN-06, FIN-07, FIN-08, FIN-09, and FIN-11 hold for this quotation gate. Preventive exposure is not `leakage_amount`. FIN-08 still forbids an unsupported financial conclusion. No cash recovery is claimed.

SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-09, and SEC-10 hold for the new records. SEC-03 still separates finance approval from the salesperson request.

Invoice-audit requirements and recovery requirements are not complete.

## Known limits

- A confirming user who cannot read the contract cannot prove a product line when the mode is `block` or `approval_required`.
- Contract User remains owner-scoped. A salesperson who does not own the contract sees no approved contract.
- `unconfigured` blocks a detected reduction for a reader and does not block a missing contract.
- Two concurrent confirmations were not executed. The unique constraint on `sale_line_id` is the database guard.
- The full and upgrade logs used a stricter registry assertion than the final test file. The fresh rerun used the final file.
