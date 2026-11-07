# 05 — Future module architecture

Date: 2026-10-28.

This is a boundary note. None of the packages below were created.

## Current foundation

The addon package imports nothing beyond the test loader. There is no `models` package. Security data loads only the role records in `security/security_groups.xml`. Tests live in `tests/` and are tagged `post_install` and `-at_install`.

## Proposed later boundaries

| Area | Later home | Not in DEV-01 |
| --- | --- | --- |
| Contracts | Contract, version, and amendment models. Company-owned. | No contract model. |
| Historical pricing | Pricing service that selects a version by the approved date rule. | No price method. DEC-01 and DEC-02 stay open. |
| Audit engine | Comparison of posted customer invoice lines with the selected contract price. | No invoice read or write. |
| Finance cases | Leakage finding and investigation records. One current exposure. | No case model. |
| Recovery | Claim, waiver, dispute, and settlement records, separate from payments. | No recovery workflow. |
| Reporting | Read models and exports after the figures exist. | No dashboard and no OWL view. |
| Background processing | Scheduled audit batches with company scope. | No `ir.cron`. |
| Security | Access rights and record rules on the models above. | DEV-02. Groups exist only as identifiers. |

Suggested future Python packages, when a phase actually needs them:

- `models/` for persisted business records.
- A pricing service module that does not post accounting entries.
- An audit service that reads invoices and writes only APP 04 records.
- `security/ir.model.access.csv` and record-rule XML added with the models they protect.
- `views/` and menus only when a user workflow is accepted.
- `data/` for non-secret configuration that has an approved default.

Do not put calculation, posting, and security rules in one file.

## Version compatibility risks

The Odoo 19 foundation is the reference. It was not copied to Odoo 18 or Odoo 20.

| Topic | Risk |
| --- | --- |
| Manifest | `19.0.1.0.0` is a series-specific version. Odoo 18 and 20 need their own series prefixes. |
| Dependencies | `account` is Community on 18, 19, and 20, but its version and dependency list differ. `contacts` changes again on Odoo 20. |
| Security XML | `res.groups.privilege` and `privilege_id` are the Odoo 19 shape verified for this file. Odoo 18 group XML is not the same and must not be assumed compatible. |
| ORM and views | Later views and tests must be checked on each series. |
| Accounting fields | Invoice price, tax, and unit-of-measure fields already differ across 18, 19, and 20. That matters for the audit phase, not for this foundation. |
| Tests | `--test-tags` and `TransactionCase` were used on Odoo 19. Repeat them on each target series. |

## Financial invariants

FIN-01 through FIN-16 and the golden fixtures remain future tests. DEV-01 did not select a pricing date, discount rule, FX rule, tax basis, tolerance, or recovery split. Those decisions stay unapproved.
