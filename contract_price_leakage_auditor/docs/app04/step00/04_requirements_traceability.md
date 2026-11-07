# 04 — Requirements traceability

Provisional mapping only. No requirement ID was previously approved, so none was renumbered. Acceptance owner for every row is **UNASSIGNED**. Product behavior is **NOT_IMPLEMENTED**.

Phase names are the 22-phase list from the step 00 prompt. Assignment of a requirement to a phase is a planning label, not authorization to start that phase.

## Phase index

| Phase | Name |
| --- | --- |
| DEV-00 | Pre-development handoff. This package. |
| DEV-01 | Community compatibility and module foundation. |
| DEV-02 | Security and multi-company foundation. |
| DEV-03 | Configuration and master data. |
| DEV-04 | Customer contract master. |
| DEV-05 | Contract versions and amendments. |
| DEV-06 | Contract applicability and precedence. |
| DEV-07 | Quantity tiers and UoM. |
| DEV-08 | Currency, tax, precision, and rounding. |
| DEV-09 | Approved discounts and overrides. |
| DEV-10 | Sales quotation controls. |
| DEV-11 | Invoice and refund integration. |
| DEV-12 | Historical invoice audit engine. |
| DEV-13 | Leakage cases and exceptions. |
| DEV-14 | Evidence and reassessment. |
| DEV-15 | Finance validation. |
| DEV-16 | Recovery, waiver, and customer disputes. |
| DEV-17 | Accounting and payment reconciliation. |
| DEV-18 | Scheduled audits, alerts, and batch reliability. |
| DEV-19 | Dashboards, reports, and SOP controls. |
| DEV-20 | Automated regression, security, and performance. |
| DEV-21 | Odoo 19 UAT, packaging, and release readiness. |

DEV-10 has no dedicated P0 requirement beyond the order-date lock illustrated by GOLD-FIN-002. Quotation behavior stays out of scope until a decision approves it.

## Matrix

| Business step | Requirement | Priority | Phase | Planned test | Invariant |
| --- | --- | --- | --- | --- | --- |
| Contract governance | A-01 | P0 | DEV-04 | PLANNED-SEC-01 | SEC-01 |
| Contract governance | A-02 | P0 | DEV-04 | PLANNED-A-02 | FIN-01 |
| Contract governance | A-03 | P0 | DEV-04 | GOLD-FIN-008 | FIN-08 |
| Contract governance | A-04 | P0 | DEV-06 | GOLD-FIN-007 | FIN-08 |
| Contract governance | A-05 | P0 | DEV-05 | GOLD-FIN-002 | FIN-02 |
| Contract governance | A-06 | P0 | DEV-06 | PLANNED-A-06 | SEC-04 |
| Contract governance | A-07 | P0 | DEV-05 | GOLD-FIN-002 | FIN-11 |
| Contract governance | A-08 | P0 | DEV-05 | PLANNED-A-08 | FIN-11 |
| Contract governance | A-09 | P0 | DEV-05 | GOLD-FIN-002 | FIN-01 |
| Contract governance | A-10 | P0 | DEV-06 | GOLD-FIN-007 | FIN-08 |
| Contract governance | A-11 | P0 | DEV-14 | PLANNED-SEC-06 | SEC-06 |
| Pricing rules | B-01 | P0 | DEV-06 | GOLD-FIN-008 | FIN-01 |
| Pricing rules | B-02 | P0 | DEV-07 | GOLD-FIN-006 | FIN-04 |
| Pricing rules | B-03 | P0 | DEV-07 | GOLD-FIN-003, GOLD-FIN-004 | FIN-04 |
| Pricing rules | B-04 | P0 | DEV-08 | GOLD-FIN-003 | FIN-05 |
| Pricing rules | B-05 | P0 | DEV-09 | GOLD-FIN-001 | FIN-03 |
| Pricing rules | B-06 | P0 | DEV-08 | GOLD-FIN-005 | FIN-06 |
| Pricing rules | B-07 | P0 | DEV-08 | GOLD-FIN-003 | FIN-07 |
| Pricing rules | B-08 | P0 | DEV-08 | GOLD-FIN-004 | FIN-07 |
| Pricing rules | B-09 | P0 | DEV-08 | GOLD-FIN-002 | FIN-02 |
| Pricing rules | B-10 | P0 | DEV-12 | GOLD-FIN-007, GOLD-FIN-008 | FIN-08 |
| Invoice auditing | C-01 | P0 | DEV-11 | PLANNED-C-01 | FIN-15 |
| Invoice auditing | C-02 | P0 | DEV-12 | PLANNED-C-02 | FIN-16 |
| Invoice auditing | C-03 | P0 | DEV-12 | GOLD-FIN-002 | FIN-01 |
| Invoice auditing | C-04 | P0 | DEV-12 | GOLD-FIN-002 | FIN-02 |
| Invoice auditing | C-05 | P0 | DEV-12 | GOLD-FIN-001 | FIN-03 |
| Invoice auditing | C-06 | P0 | DEV-11 | GOLD-FIN-006 | FIN-10 |
| Invoice auditing | C-07 | P0 | DEV-11 | PLANNED-C-07 | FIN-10 |
| Invoice auditing | C-08 | P0 | DEV-12 | GOLD-FIN-009 | FIN-09 |
| Invoice auditing | C-09 | P0 | DEV-12 | GOLD-FIN-009 | OPS-02 |
| Invoice auditing | C-10 | P0 | DEV-12 | PLANNED-C-10 | FIN-11 |
| Leakage cases | D-01 | P0 | DEV-13 | GOLD-FIN-001 | FIN-12 |
| Leakage cases | D-02 | P0 | DEV-13 | PLANNED-D-02 | OPS-05 |
| Leakage cases | D-03 | P0 | DEV-13 | GOLD-FIN-007, GOLD-FIN-008 | FIN-08 |
| Leakage cases | D-04 | P0 | DEV-15 | GOLD-REC-001 | FIN-12 |
| Leakage cases | D-05 | P0 | DEV-15 | PLANNED-D-05 | FIN-11 |
| Leakage cases | D-06 | P0 | DEV-13 | PLANNED-SEC-03 | SEC-03 |
| Leakage cases | D-07 | P0 | DEV-14 | PLANNED-D-07 | OPS-09 |
| Leakage cases | D-08 | P0 | DEV-14 | PLANNED-SEC-10 | SEC-10 |
| Leakage cases | D-09 | P0 | DEV-14 | PLANNED-SEC-06 | SEC-06 |
| Recovery | E-01 | P0 | DEV-16 | GOLD-REC-001 | FIN-12 |
| Recovery | E-02 | P0 | DEV-16 | PLANNED-SEC-04 | SEC-04 |
| Recovery | E-03 | P0 | DEV-16 | GOLD-REC-001 | FIN-12 |
| Recovery | E-04 | P0 | DEV-16 | PLANNED-SEC-05 | SEC-05 |
| Recovery | E-05 | P0 | DEV-16 | PLANNED-E-05 | FIN-11 |
| Recovery | E-06 | P0 | DEV-16 | GOLD-REC-001 | FIN-13 |
| Recovery | E-07 | P0 | DEV-16 | GOLD-REC-001 | FIN-13 |
| Recovery | E-08 | P0 | DEV-16 | PLANNED-SEC-04 | SEC-04 |
| Accounting | F-01 | P0 | DEV-17 | PLANNED-F-01 | FIN-15 |
| Accounting | F-02 | P0 | DEV-17 | PLANNED-C-10 | FIN-11 |
| Accounting | F-03 | P0 | DEV-17 | GOLD-REC-001 | FIN-13 |
| Accounting | F-04 | P0 | DEV-17 | GOLD-FIN-010 | FIN-14 |
| Accounting | F-05 | P0 | DEV-17 | GOLD-REC-001 | FIN-12 |
| Accounting | F-06 | P0 | DEV-17 | GOLD-FIN-010 | FIN-14 |
| Accounting | F-07 | P0 | DEV-17 | GOLD-FIN-006 | FIN-10 |
| Accounting | F-08 | P0 | DEV-17 | GOLD-REC-001 | FIN-06 |
| Security | PG-01 | P0 | DEV-02 | PLANNED-SEC-11 | SEC-11 |
| Security | PG-02 | P0 | DEV-02 | PLANNED-SEC-01 | SEC-01 |
| Security | PG-03 | P0 | DEV-02 | PLANNED-SEC-02 | SEC-02 |
| Security | PG-04 | P0 | DEV-02 | PLANNED-SEC-03 | SEC-03 |
| Security | PG-05 | P0 | DEV-02 | PLANNED-SEC-07 | SEC-07 |
| Security | PG-06 | P0 | DEV-14 | PLANNED-SEC-10 | SEC-10 |
| Security | PG-07 | P0 | DEV-14 | PLANNED-SEC-09 | FIN-11 |
| Security | PG-08 | P0 | DEV-21 | PLANNED-SEC-09 | SEC-09 |
| Operations | H-01 | P0 | DEV-18 | PLANNED-OPS-08 | OPS-08 |
| Operations | H-02 | P0 | DEV-18 | PLANNED-OPS-01 | OPS-01 |
| Operations | H-03 | P0 | DEV-18 | PLANNED-OPS-04 | OPS-04 |
| Operations | H-04 | P0 | DEV-18 | PLANNED-OPS-04 | OPS-06 |
| Operations | H-05 | P0 | DEV-18 | PLANNED-OPS-03 | OPS-03 |
| Operations | H-06 | P0 | DEV-18 | PLANNED-OPS-05 | OPS-05 |
| Operations | H-07 | P0 | DEV-18 | PLANNED-SEC-12 | SEC-12 |
| Operations | H-08 | P0 | DEV-18 | PLANNED-OPS-07 | OPS-07 |
| Reports | RPT-01 | P0 | DEV-19 | PLANNED-RPT-01 | FIN-16 |
| Reports | RPT-02 | P0 | DEV-19 | PLANNED-RPT-02 | FIN-16 |
| Reports | RPT-03 | P0 | DEV-19 | GOLD-FIN-008 | FIN-08 |
| Reports | RPT-04 | P0 | DEV-19 | GOLD-REC-001 | FIN-13 |
| Reports | RPT-05 | P0 | DEV-19 | PLANNED-OPS-07 | OPS-07 |
| Reports | RPT-06 | P0 | DEV-19 | PLANNED-SEC-01 | SEC-01 |
| Reports | RPT-07 | P0 | DEV-19 | PLANNED-RPT-07 | FIN-16 |
| Reports | RPT-08 | P0 | DEV-19 | PLANNED-RPT-08 | OPS-10 |
| Reports | RPT-09 | P0 | DEV-19 | PLANNED-SEC-07 | SEC-07 |
| Release | PJ-01 | P0 | DEV-01, rechecked DEV-21 | PLANNED-PJ-01 | G13 |
| Release | PJ-02 | P0 | DEV-21 | PLANNED-PJ-02 | G13 |
| Release | PJ-03 | P0 | DEV-21 | PLANNED-PJ-03 | SEC-12 |
| Release | PJ-04 | P0 | DEV-21 | PLANNED-PJ-04 | G15 |
| Release | PJ-05 | P0 | DEV-21 | PLANNED-PJ-05 | G07 |
| Release | PJ-06 | P0 | DEV-20 | GOLD-FIN-001–010, GOLD-REC-001 | G01–G09 |
| Release | PJ-07 | P0 | DEV-20 | PLANNED-SEC-01–12 | G10 |
| Release | PJ-08 | P0 | DEV-20 | PLANNED-VOL-* | G11 |
| Release | PJ-09 | P0 | DEV-21 | PLANNED-UAT | G14 |
| Release | PJ-10 | P0 | DEV-21 | PLANNED-PJ-10 | G15 |
| Release | PJ-11 | P0 | DEV-21 | PLANNED-PJ-11 | G15 |

P1-01 through P1-10 have priority P1, no phase, and no test. X-01 through X-07 are exclusions and have no phase.

## First-pass alias

`docs/00_*.md` used OD-01 and GT-01 style IDs and a private I-01 invariant list. Those aliases are retired. Current IDs are DEC-*, GOLD-FIN-*, FIN-*, SEC-*, and OPS-*. The crosswalk is in files 05 and 07.
