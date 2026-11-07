# 09 — Development roadmap handoff

DEV-00 does not authorize DEV-01. No phase below had started when this handoff was written. The later DEV-01 prompt authorized the foundation only. Its result is in `docs/app04/step01/`.

## Dependency order

```text
DEV-00 review
  -> DEV-01 foundation
    -> DEV-02 security
      -> DEV-03 configuration
        -> DEV-04 contracts
          -> DEV-05 versions
            -> DEV-06 applicability
              -> DEV-07 UoM and tiers
              -> DEV-08 currency, tax, rounding
                -> DEV-09 discounts
                  -> DEV-11 invoices and refunds
                    -> DEV-12 audit engine
                      -> DEV-13 cases
                        -> DEV-14 evidence
                          -> DEV-15 finance validation
                            -> DEV-16 recovery and disputes
                              -> DEV-17 accounting links
                                -> DEV-18 scheduling
                                  -> DEV-19 reports
                                    -> DEV-20 regression
                                      -> DEV-21 UAT and packaging
```

DEV-10 sits beside DEV-11 and starts only if a decision puts sales quotations in scope. It is not on the critical path of posted-invoice audit.

## Acceptance milestone for each phase

| Phase | May be called complete only when |
| --- | --- |
| DEV-00 | This package exists, statuses are honest, and a reviewer accepts or rejects it. Acceptance is still pending. |
| DEV-01 | Installable Community manifest. Depends limited to the approved set from DEC-19. No pricing methods, menus, or cron. Install test on a disposable Odoo 19 database. |
| DEV-02 | Groups and record rules for the models that exist. PLANNED-SEC-01 passes. No user needs `account.group_account_manager` merely to read. |
| DEV-03 | Company-owned configuration. No silent financial default for an open DEC. |
| DEV-04 | Contract header, parties, products, evidence reference. Cannot approve without A-06. |
| DEV-05 | Versions, amendments, supersession. History remains. |
| DEV-06 | Precedence from DEC-02. Conflicts return `BUSINESS_REVIEW_REQUIRED`. |
| DEV-07 | GOLD-FIN-004 on Odoo 19. Incompatible UoM is an exception. |
| DEV-08 | GOLD-FIN-003 and GOLD-FIN-005 only after DEC-06, DEC-07, and DEC-08 are approved. |
| DEV-09 | GOLD-FIN-001. |
| DEV-10 | Only the approved quotation rules. Otherwise the phase is not started. |
| DEV-11 | Posted `out_invoice` selection. Credit notes only under DEC-09. No writes to posted moves. |
| DEV-12 | Historical selection, duplicate prevention, traceability. GOLD-FIN-002, 007, 008, 009. |
| DEV-13 | Potential leakage and exceptions are distinct. |
| DEV-14 | Reassessment keeps the prior decision. |
| DEV-15 | Potential and finance-validated amounts are different fields. |
| DEV-16 | GOLD-REC-001 stored fields. Self-approval test passes. |
| DEV-17 | Links to posted documents. Cash proof matches DEC-13. No new journal entry unless a new decision allows it. |
| DEV-18 | Interrupt, restart, duplicate schedule, and company-safe cron tests. |
| DEV-19 | Report totals reconcile. Exports obey SEC-07. |
| DEV-20 | Automated GOLD-FIN, SEC, and measured volume runs. Results committed as evidence, not as marketing numbers. |
| DEV-21 | G13, G14, and G15 evidence for Odoo 19 only, unless 18 and 20 have their own records. |

## Odoo 18 and Odoo 20

No conversion is done in DEV-00. No 18.0 or 20.0 addon copy is created.

Each future series needs its own dependency check, ORM and view check, accounting check, security regression, golden tests, cron test, fresh install, upgrade test, export check, and release artifact.

Known conversion risks, from the static read:

| Area | 18 | 19 master | 20 |
| --- | --- | --- | --- |
| UoM | `uom.category`, `factor_inv`, per-unit rounding | `relative_uom_id`, computed `rounding` | Same graph as 19, no `rounding` field |
| Python | `setup.py` requires >= 3.10 | 3.10–3.14 | Minimum 3.12 |
| `contacts` depends | `base`, `mail` | `base`, `mail` | Adds `base_address_extended`, `web_hierarchy` |
| Accounting review state | Not in the 18 selection block read | Not in the 19 selection block read | `REVIEW_STATE_SELECTION` exists and is not an APP 04 state |
| `models.Constraint` | UoM file still uses older constraint style | Used by UoM and currency rate | Used by UoM |

A version may not be advertised as supported before its own gates pass. Today no version is supported.

## Suggested DEV-01 boundary, after acceptance only

Create an installable shell: manifest, `__init__.py`, and a README pointing here. Dependencies proposed in DEC-19, still subject to that decision's approval. No contract model, no audit method, no recovery method, no menu, no cron, no demo prices.

That work is not started by this file.
