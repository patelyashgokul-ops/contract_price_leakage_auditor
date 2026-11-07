# 09 — DEV-03 progress

Date: 2026-10-28.

**DEV-03 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**DEV-03 BUSINESS ACCEPTANCE: PENDING**

Pricing policy is not operationally approved. `approved_ready` cannot be stored. Open decisions stay open. Formal business acceptance was not granted.

`BLOCKER_LICENSE_DECISION_REQUIRED` remains. Manifest license `Other proprietary` is a loader guard so Odoo does not stamp LGPL-3. It is not a license grant. Author is empty. That blocker limits commercial packaging. It did not stop this configuration work.

## Prerequisites

| Item | Result |
| --- | --- |
| DEV-00 | Reviewed. Implementation PARTIAL. Business acceptance PENDING. `docs/app04/step00/`. |
| DEV-01 | Reviewed. Installable foundation. Business acceptance PENDING. |
| DEV-02 | Reviewed. Eight groups and the role tests. Business acceptance PENDING. Step 02 files stay the historical record of that phase. |
| Addon | `contract_price_leakage_auditor` |
| Odoo 19 Community | Available. Disposable databases used. |
| Git | Still no `.git` directory. No destructive git operation. |
| Sibling addon | `freight_invoice_audit_recovery` was not modified. |

No `DEV03_BLOCKED_BY_PREREQUISITES` stop. The license issue is not an unsafe configuration defect.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| DEV03-01 Review DEV-00/01/02 | COMPLETED | Step 00, 01, and 02 documents and the installed groups. |
| DEV03-02 Inspect models and settings | COMPLETED | No prior policy model. Groups had no ACL before this phase. |
| DEV03-03 Verify Odoo 19 APIs | COMPLETED | `uom.uom` relative factors, `product.template.uom_ids`, no `product.packaging`, currency rounding, field groups, global record rules. |
| DEV03-04 Persistence architecture | COMPLETED | `cpla.company.policy` only. File 01. |
| DEV03-05 Company configuration | COMPLETED | Model, views, ACL, rule. |
| DEV03-06 Pricing-date policy | COMPLETED | Draft candidates. DEC-01 stays open. |
| DEV03-07 Precedence and quantity | COMPLETED | Candidates and `CONTRACT_CONFLICT_REVIEW_REQUIRED`. No matching. |
| DEV03-08 FX and currency readiness | COMPLETED | `validate_currency`. No rates created. |
| DEV03-09 Customer validation | COMPLETED | `validate_customer`. |
| DEV03-10 Product and UoM validation | COMPLETED | `validate_product`, `validate_uom_conversion`, `classify_pricing_unit`. |
| DEV03-11 Tax and precision | COMPLETED | `classify_tax_bases`, `assess_monetary_difference`, `propose_tolerance`. |
| DEV03-12 Approval references | COMPLETED | `check_approval_reference`. No limits. File 05. |
| DEV03-13 Readiness | COMPLETED | `get_configuration_readiness`. Never operationally approved. |
| DEV03-14 Change control | COMPLETED | Revisions, freeze, activation refusal. File 06. |
| DEV03-15 Configuration UI | COMPLETED | One list, form, search, and two menus. Server `get_view` passed. No browser session. |
| DEV03-16 Security and ACLs | COMPLETED | File 07. Company tests passed. |
| DEV03-17 Automated tests | COMPLETED | `tests/test_company_policy.py` plus updated smoke and security tests. |
| DEV03-18 Execute tests | COMPLETED | File 08. Both databases, 0 failed, 0 errors of 73. |
| DEV03-19 Install and update | COMPLETED | Fresh `-i` and upgrade `-u`. File 08. |
| DEV03-20 Traceability | COMPLETED | Matrix in this file. |
| DEV03-21 Documentation | COMPLETED | `docs/app04/step03/01` through `10`. |
| DEV03-22 DEV-04 handoff | COMPLETED | File 10. DEV-04 was not started. |

## Requirements traceability

| ID | DEV-03 position |
| --- | --- |
| P0-B Pricing rules foundation | Draft candidates and explicit incomplete states. No pricing engine. |
| P0-G Security and evidence | Company rule, ACLs, field groups, frozen revisions. Not a full evidence store for invoices. |
| P0-J Configuration and release readiness | Readiness payload exists. Release remains NO-GO. License still open. |
| DEC-01 through DEC-08, DEC-11, DEC-12 | Open. Activation refused. Owners UNASSIGNED. |
| FIN-02 Pricing date | Candidate only. `PRICING_DATE_POLICY_REQUIRES_APPROVAL`. |
| FIN-04 UoM | Conversion and packaging checks. No contract quantity. |
| FIN-05 FX | Basis candidate. No historical rate selection on transactions. |
| FIN-06 Tax normalization | Inclusive and exclusive are not comparable. No tax math. |
| FIN-07 Monetary precision | Currency rounding without suppression. |
| FIN-08 Missing evidence | `missing_evidence_policy` and readiness `missing` / `blocking`. |
| SEC-01 Company isolation | Policy rows isolated in CFG-T003, T019, T036, T037. Contract records do not exist yet. |
| SEC-03 Role separation | Preserved. App admin cannot activate. Finance reviewer cannot write. |
| SEC-04 Approval authority | Activation and approval-reference checks refuse. No workflow. |
| SEC-09 Unauthorized modification | ACL, rule, frozen history, and direct RPC tests passed. |

Invoice audit and recovery compliance are not complete.

## Files

Added: `models/__init__.py`, `models/company_policy.py`, `security/ir.model.access.csv`, `security/company_policy_rules.xml`, `views/company_policy_views.xml`, `tests/test_company_policy.py`, `docs/app04/step03/01` through `10`.

Modified: `__init__.py`, `__manifest__.py`, `security/security_groups.xml` (comment only), `tests/__init__.py`, `tests/test_foundation_smoke.py`, `tests/test_security_foundation.py`, `README.md`, `DEVELOPMENT_PROGRESS.md`, `docs/README.md`.

Not modified: `docs/app04/step00/`, `docs/app04/step01/`, `docs/app04/step02/`, and `freight_invoice_audit_recovery`.

## Defects

No open critical defect from the DEV-03 list. The 04:32 test errors were a bad `assertRaises` tuple and were fixed before the passing runs.

Remaining risks are in the handoff: unreachable `approved_ready` by design, reserved unused `review_required` state, database-administrator trust boundary, transitive `mail`, no browser pass, no git history, and the license blocker.
