# 09 — DEV-04 progress

Date: 2026-10-28.

**DEV-04 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**DEV-04 BUSINESS ACCEPTANCE: PENDING**

Ready for review is not commercial approval. No contract in this phase is an invoice-audit price. Formal business acceptance was not granted. Open decisions stay open. Owners remain UNASSIGNED.

`BLOCKER_LICENSE_DECISION_REQUIRED` remains. Manifest license `Other proprietary` is a loader guard so Odoo does not stamp LGPL-3. It is not OPL-1 and not permission to distribute. Author is empty. That blocker limits commercial packaging. It did not stop the contract master.

## Prerequisites

| Item | Result |
| --- | --- |
| DEV-00 | Reviewed. Implementation PARTIAL. Business acceptance PENDING. `docs/app04/step00/`. |
| DEV-01 | Reviewed. Installable foundation. Direct depends remain `base` and `product`. |
| DEV-02 | Reviewed. Eight group XML IDs preserved. |
| DEV-03 | Reviewed. `cpla.company.policy` preserved. `operationally_approved` stays false. |
| Addon | `contract_price_leakage_auditor` |
| Path | `C:\PycharmProjects\odoo19\custom_addons\contract_price_leakage_auditor` |
| Odoo | 19.0 Community, log line `Odoo version 19.0`. Python venv `C:\PycharmProjects\odoo19\.venv`. |
| Git | No `.git` directory. No git init and no commit. |
| Sibling addon | `freight_invoice_audit_recovery` was not modified. |
| Prior contract model | None. New models use the `cpla` prefix and do not start with `cpla.contract`. |

No `DEV04_BLOCKED_BY_PREREQUISITES` stop.

The DEV-03 disposable databases had already been dropped before this phase. Their names stayed in `local_testing/disposable_databases.txt`. Upgrade from those databases was not re-run. See file 08.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| DEV04-01 Verify DEV-00 through DEV-03 | COMPLETED | Step documents and the installed policy module. |
| DEV04-02 Inspect existing contract master | COMPLETED | No prior contract model. |
| DEV04-03 Confirm model names | COMPLETED | `cpla.customer.contract`, `.line`, `.evidence`. |
| DEV04-04 Contract header | COMPLETED | `models/customer_contract.py`. |
| DEV04-05 Contract lines | COMPLETED | Same file. |
| DEV04-06 Company and customer | COMPLETED | Required company. Exact partner. Shared contacts allowed. |
| DEV04-07 Contract reference | COMPLETED | `data/ir_sequence.xml`. Unique per company. |
| DEV04-08 Date validity | COMPLETED | Constraint and review blockers. Dates are not swapped. |
| DEV04-09 Contract currency | COMPLETED | Separate from company currency. Change with lines is blocked. |
| DEV04-10 Product, variant, UoM | COMPLETED | Variant identity. Default unit required for review. |
| DEV04-11 Negotiated price | COMPLETED | No list-price default. Negative rejected. Zero blocks review. |
| DEV04-12 Customer coverage | COMPLETED | Exact customer. Extra entities block review. DEC-03 open. |
| DEV04-13 Draft lifecycle | COMPLETED | `draft`, `ready_for_review`, `cancelled`. |
| DEV04-14 Review checks | COMPLETED | `action_submit_for_review` and `_review_blockers`. |
| DEV04-15 State protection | COMPLETED | Header write, line write, evidence write. |
| DEV04-16 Evidence | COMPLETED | Binary attachment. Freeze after draft. |
| DEV04-17 ACLs and rules | COMPLETED | CSV and `security/customer_contract_rules.xml`. |
| DEV04-18 Multi-company | COMPLETED | Global company rules and create checks. |
| DEV04-19 Views and menu | COMPLETED | `views/customer_contract_views.xml`. |
| DEV04-20 Functional tests | COMPLETED | `tests/test_customer_contract.py`. |
| DEV04-21 Negative and security tests | COMPLETED | Same module, SEC04 cases. |
| DEV04-22 Execute isolated suite | COMPLETED | File 07. Fresh `-i` at 05:32:17, 0 failed, 0 errors of 155. The earlier `-u` was also green. |
| DEV04-23 Install and upgrade | COMPLETED | File 08. Fresh `-i` passed. DEV-03 snapshot upgrade is NOT_EXECUTED. |
| DEV04-24 Regression | COMPLETED | Smoke, SEC, and CFG tests in the same 155-test result. |
| DEV04-25 Traceability | COMPLETED | Matrix below. |
| DEV04-26 Documentation | COMPLETED | `docs/app04/step04/01` through `10`. |
| DEV04-27 DEV-05 handoff | COMPLETED | File 10. DEV-05 was not started. |

## Requirements traceability

| ID | Position |
| --- | --- |
| P0-A Contract governance | IMPLEMENTED as a draft master. Approval is not implemented. |
| P0-G Security and evidence | IMPLEMENTED for contract ACL, company rules, and linked files. Not a legal archive. |
| P0-J Release readiness | VERIFIED as far as install and tests of this draft. Release remains NO-GO. License still open. |
| CPL-C01 Company-specific customer contract | IMPLEMENTED. |
| CPL-C02 Contract lines by product variant | IMPLEMENTED. |
| CPL-C03 Effective start and end dates | IMPLEMENTED as proposed dates. Not approval. |
| CPL-C04 Historical versioning readiness | PLANNED_FOR_DEV05. Structure does not block a later version model. Versioning is not complete. |
| CPL-C05 Amendment architecture readiness | PLANNED_FOR_DEV05. No amendment model. |
| CPL-C06 Approval lifecycle readiness | PLANNED_FOR_DEV05. `ready_for_review` is not approval. |
| CPL-C07 Quantity-tier architecture readiness | PLANNED_FOR_DEV07. No product-only unique key. Tiers are not implemented. |
| CPL-C08 Pricing-date policy reference | IMPLEMENTED as a required current `policy_id` pointer. The date rule itself stays DEC-01 and is not applied to invoices. |
| CPL-C09 Conflict review readiness | IMPLEMENTED as `overlap_warning` only. No precedence. PLANNED_FOR_DEV06 for the decision. |
| CPL-C10 Contract evidence | IMPLEMENTED as linked files with access control. Not an immutable archive. |

## Preserved

`cpla.company.policy` fields, states, and activation refusal. Eight group XML IDs. Policy ACLs for manager, finance, auditor, and application administrator. Policy global rule. Step 00 through step 03 documents. No accounting models. No DEV-05 states.

## Deferred

Customer smart button on `res.partner`. It was not built, so contract counts and prices are not shown on the customer form.

Odoo 18 and Odoo 20 conversion. Not started. Likely touch points: Odoo 18 `category_id` and `groups_id` versus Odoo 19 `res.groups.privilege` and `implied_ids`; UoM `relative_factor` and `_has_common_reference`; `product.template.uom_ids`; list view XML; attachment access; constraint execution on a sudo recordset. Compatibility was not tested.
