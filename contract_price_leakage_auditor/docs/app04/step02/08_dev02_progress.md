# 08 — DEV-02 progress

Date: 2026-10-28.

**DEV-02 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**DEV-02 BUSINESS ACCEPTANCE: PENDING**

APP 04 security is not complete. Business models, record rules, approval methods, attachments, and exports do not exist. The role foundation that can exist now is installed and tested.

DEV-03 was not started.

## Prerequisites

| Item | Class | Evidence |
| --- | --- | --- |
| DEV-00 package | VERIFIED as a baseline. Business acceptance PENDING. | `docs/app04/step00/` |
| DEV-01 foundation | VERIFIED install. Business acceptance PENDING. License still `BLOCKER_LICENSE_DECISION_REQUIRED`. | `docs/app04/step01/` |
| Odoo 19 schema | VERIFIED | `res.groups.privilege_id`, `res.groups.implied_ids`, `res.groups.all_implied_ids`, `res.users.group_ids`, `ir.model.access`, `ir.rule`. No `category_id` on `res.groups`. |
| Addon identity | VERIFIED | `contract_price_leakage_auditor` |
| Safe database | VERIFIED | `cpla_dev01_foundation_20261028` |
| Critical install defect | None found | Update exit 0 on 2026-10-28 03:58 |
| Git | NOT_AVAILABLE | No `.git` directory |

The license blocker prevents a commercial package. It does not make the group XML unsafe to update. DEV-02 was not stopped for that reason.

## Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| DEV02-01 Review prerequisites | COMPLETED | This file. |
| DEV02-02 Inspect security files | COMPLETED | One security XML. No ACL file. |
| DEV02-03 Verify Odoo 19 schema | COMPLETED | Source fields listed above. |
| DEV02-04 Role architecture | COMPLETED | Existing IDs preserved. Alias map in file 01. |
| DEV02-05 Groups | COMPLETED | Comments and `exclusive` set false. No new group records. |
| DEV02-06 Inheritance | COMPLETED | SEC-T004 passed. |
| DEV02-07 Model ACLs | COMPLETED | None exist. None were added. |
| DEV02-08 Record rules | COMPLETED | None exist. None were added. |
| DEV02-09 Approval security | COMPLETED as a design | File 04. No workflow. |
| DEV02-10 Price field access | COMPLETED as a design | No fields exist. |
| DEV02-11 Attachments | COMPLETED as a design | File 05. |
| DEV02-12 Exports | COMPLETED as a design | File 05. |
| DEV02-13 Public methods and sudo | COMPLETED | None found. SEC-T007. |
| DEV02-14 Future security matrices | COMPLETED | Files 02 and 03. |
| DEV02-15 Automated tests | COMPLETED for current surfaces | `tests/test_security_foundation.py`. |
| DEV02-16 Execute tests | COMPLETED | 0 failed, 0 errors of 20 tests. Planned IDs were not marked passed. |
| DEV02-17 Update regression | COMPLETED | `-u` exit 0. Security XML loaded. |
| DEV02-18 Traceability | COMPLETED | Table below. |
| DEV02-19 Documentation | COMPLETED | This directory. |
| DEV02-20 DEV-03 handoff | COMPLETED | End of this file. DEV-03 not started. |

## Changed files

- `security/security_groups.xml`
- `tests/__init__.py`
- `tests/test_security_foundation.py`
- `docs/app04/step02/01_security_architecture.md` through `08_dev02_progress.md`
- `README.md`
- `DEVELOPMENT_PROGRESS.md`

Preserved: `__init__.py`, `__manifest__.py`, `tests/test_foundation_smoke.py`, and the step 00 and step 01 documents. No other addon was edited.

## Traceability

| Invariant | State | Current evidence | Future test | Phase |
| --- | --- | --- | --- | --- |
| SEC-01 Company isolation | NOT_IMPLEMENTED | Policy in file 03. | SEC-T008–SEC-T014 | First company-owned model |
| SEC-02 Price confidentiality | NOT_IMPLEMENTED | No price field. | SEC-T023, SEC-T027 | Pricing phases |
| SEC-03 Finance separation | PARTIAL groups only | SEC-T005, SEC-T030, SEC-T031. No business action. | SEC-T018 | DEV-15 and DEV-16 |
| SEC-04 Approval authority | NOT_IMPLEMENTED | No method and no amount. DEC-11 open. | SEC-T016, SEC-T017, SEC-T020 | DEV-16 |
| SEC-05 Self-approval | NOT_IMPLEMENTED | Rule recorded. No request record. | SEC-T019 | DEV-16 |
| SEC-06 Evidence access | NOT_IMPLEMENTED | No attachment model. | SEC-T024, SEC-T025 | DEV-14 |
| SEC-07 Export security | NOT_IMPLEMENTED | No export. | SEC-T026 | DEV-19 |
| SEC-08 Background company | NOT_IMPLEMENTED | No cron. | SEC-T015 | DEV-18 |
| SEC-09 History hold | NOT_IMPLEMENTED | Delete policy recorded. DEC-17 open. | PLANNED-SEC-09 | DEV-14 |
| SEC-10 Approval history | NOT_IMPLEMENTED | No history model. | PLANNED-SEC-10 | DEV-14 |
| SEC-11 Group consolidation | PARTIAL | Eight stable groups. SEC-T001–SEC-T007. Not a full access certification. | PLANNED-SEC-11 | Continues with ACLs |
| SEC-12 Sensitive logs | NOT_IMPLEMENTED | No business log. | PLANNED-SEC-12 | DEV-18 |

Owner of each invariant: UNASSIGNED.

## Quality gates

| Gate | Result |
| --- | --- |
| SG-01 Groups valid on Odoo 19 | Met. Update and SEC-T003. |
| SG-02 Implications preserved | Met. SEC-T004. |
| SG-03 No public ACL | Met. No ACL rows. |
| SG-04 Sensitive models company-secured | Not applicable. No sensitive model. |
| SG-05 No approval bypass | Not applicable. No approval method. |
| SG-06 Public methods | Met. None exist. |
| SG-07 Evidence download | Not applicable. None exist. |
| SG-08 Exports | Not applicable. None exist. |
| SG-09 Multi-company design | Met as documentation. |
| SG-10 Applicable tests | Met. 20 tests, 0 failures. |
| SG-11 Update | Met. Exit 0. |
| SG-12 Future requirements traced | Met. Files 02, 03, 04, and 06. |

## DEV-03 handoff

DEV-03 may configure company-owned settings only when a later prompt authorizes it. It must not add contract masters, prices, audits, recovery, cron, or dashboards.

Prerequisites for that later work:

- Keep the XML IDs in file 01. Do not rename them to `group_cpl_*`.
- Assign `base.group_user` separately from APP 04 groups.
- Do not imply accounting or Settings groups.
- A confidential model needs required `company_id`, an ACL with a group, and the company record rule in the same change.
- Do not store a financial default that decides an open DEC.
- DEC-11 remains the blocker for approval amounts.
- Re-run `--test-tags=/contract_price_leakage_auditor` on the disposable database after the change.

## Readiness

`IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING`

Business acceptance is PENDING. A reviewer has not accepted this phase.
