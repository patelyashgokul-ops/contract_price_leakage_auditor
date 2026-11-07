# Contract Price Leakage Auditor

APP 04 — B2B revenue assurance for Odoo Community.

**Status:** Odoo 19 Community foundation through recovery billing and payment classification. The module installs. Ready for review is not approval. An approved version is not by itself an invoice-audit price. A resolver match, a normalized tier price, a comparable currency price, and an approved concession are not unauthorized leakage. Preventive quotation exposure is not recovered cash. A source mapping is not a leakage finding. A potential leakage amount is not finance-validated, not billed, and not collected. An investigation case is not finance validation. Closing a case is not recovered cash. Accepting a reassessment is not finance validation. A revised amount is not recovered cash. A finance-validated amount is not a waiver, a receivable, or collected cash. An approved recovery target is not a posted invoice and is not collected cash. A draft recovery document is not posted billing. A posted recovery invoice is not bank-verified cash. A credit, write-off, or exchange difference is not recovered principal.

The step 00 source of truth remains [docs/app04/step00/README.md](docs/app04/step00/README.md). Step 00 business acceptance is still pending.

The step 01 record is [docs/app04/step01/06_dev01_progress.md](docs/app04/step01/06_dev01_progress.md).

The step 02 record is [docs/app04/step02/08_dev02_progress.md](docs/app04/step02/08_dev02_progress.md). Business acceptance is pending.

The step 03 record is [docs/app04/step03/09_dev03_progress.md](docs/app04/step03/09_dev03_progress.md). Company policy revisions exist. Business acceptance is pending. Pricing is not operationally approved.

The step 04 record is [docs/app04/step04/09_dev04_progress.md](docs/app04/step04/09_dev04_progress.md). Draft customer contracts and negotiated lines exist. Business acceptance is pending. A ready-for-review contract is not an audit price.

The step 05 record is [docs/app04/step05/11_dev05_progress.md](docs/app04/step05/11_dev05_progress.md). Approved contract versions, amendments, and supersession exist. Business acceptance is pending. Version chronology is not invoice matching.

The step 06 record is [docs/app04/step06/12_dev06_progress.md](docs/app04/step06/12_dev06_progress.md). The resolver selects one approved historical version or returns a review outcome. Business acceptance is pending. The match is not an invoice audit.

The step 07 record is [docs/app04/step07/12_dev07_progress.md](docs/app04/step07/12_dev07_progress.md). Approved full-volume quantity tiers and snapshotted unit conversion are implemented. Business acceptance is pending. The normalized price is not an invoice audit.

The step 08 record is [docs/app04/step08/13_dev08_progress.md](docs/app04/step08/13_dev08_progress.md). An explicit contract clause can produce a pre-discount comparable price. Business acceptance is pending. That price is not an invoice audit.

The step 09 record is [docs/app04/step09/13_dev09_progress.md](docs/app04/step09/13_dev09_progress.md). An approved concession or an approved override can produce an adjusted unit price. Business acceptance is pending. That price is not an invoice audit.

The step 10 record is [docs/app04/step10/13_dev10_progress.md](docs/app04/step10/13_dev10_progress.md). A sales quotation can be compared with that adjusted price before confirmation. Business acceptance is pending. Preventive exposure is not recovered cash.

The step 11 record is [docs/app04/step11/14_dev11_progress.md](docs/app04/step11/14_dev11_progress.md). Posted customer invoice lines can be mapped to verified sales lines and historical price evidence. Business acceptance is pending. A source mapping is not a leakage finding.

The step 12 record is [docs/app04/step12/15_dev12_progress.md](docs/app04/step12/15_dev12_progress.md). Posted customer invoices can be compared with the approved historical price. Business acceptance is pending. Potential leakage is not finance-validated leakage.

The step 13 record is [docs/app04/step13/16_dev13_progress.md](docs/app04/step13/16_dev13_progress.md). A current finding can open one investigation case. Business acceptance is pending. A case is not finance validation, and closing it is not recovered cash.

The step 14 record is [docs/app04/step14/06_dev14_progress.md](docs/app04/step14/06_dev14_progress.md). A finance manager can accept a new reading without rewriting the original audit result. Business acceptance is pending. That acceptance is not finance validation, and the difference is not recovered cash.

The step 15 record is [docs/app04/step15/16_dev15_progress.md](docs/app04/step15/16_dev15_progress.md). Finance can approve a supportable portion of accepted evidence. Business acceptance is pending. That approval is not a receivable, a waiver, or collected cash.

The step 16 record is [docs/app04/step16/16_dev16_progress.md](docs/app04/step16/16_dev16_progress.md). A contract manager can authorize recovery, a waiver, a dispute, or a settlement against a current finance validation. Business acceptance is pending. That authorization is not a posted invoice and is not collected cash.

The step 17 record is [docs/app04/step17/18_dev17_progress.md](docs/app04/step17/18_dev17_progress.md). A finance manager with invoice rights can prepare and post a recovery document from an approved handoff, and can classify native payments, credits, and residuals. Business acceptance is pending. Posted billing is not cash. DEV-18 has not started.

Odoo 19 Community is the master target. Odoo 18 Community and Odoo 20 Community are later compatibility targets and were not converted.

## What this is

The intended product compares posted customer invoice prices with approved historical customer contract prices. It is a revenue-assurance record. It does not replace Odoo accounting, and a price difference is not recoverable cash.

This build compares eligible posted customer invoice lines with the approved historical contract price and stores potential leakage. It registers the addon, eight internal role identifiers, one company-policy revision model, a draft customer contract with negotiated lines and evidence files, immutable approved contract versions, a read-only applicability resolver, quantity tiers on an approved version line, a financial clause on that version, authorized concessions plus discount-approval requests, a sales-quotation compliance gate with a confirmed-order price lock, a read-only source map from posted customer invoice lines to sales lines, an invoice audit run with append-only results and one current potential finding per economic identity, and an investigation case that references those findings. Those roles grant no payment or accounting-posting rights. A stored policy candidate is not an approved price rule. A contract in ready for review is not an approved price. An approved version is the historical price source the resolver can select. A tier match normalizes that source to the requested unit. A financial clause can express that unit in the comparison currency and tax basis. An approved concession can adjust that comparable price. A quotation check can warn or block confirmation. A source map records the posted price and the historical basis. The audit finding is potential leakage only. The case copies that current amount for investigation. A reassessment proposes a later reading and keeps the original result. It is not finance-validated and it is not recovered cash.

## What is in this directory

| Path | Purpose |
| --- | --- |
| `__manifest__.py` | Odoo 19 manifest `19.0.1.15.0`. Direct depends: `base`, `product`, and `sale`. |
| `models/company_policy.py` | Company policy revisions and readiness checks. |
| `models/customer_contract.py` | Draft contract header, lines, and evidence. |
| `models/contract_version.py` | Approved version snapshots, lines, evidence links, events, and comparison. |
| `models/quantity_tier.py` | Draft and approved quantity tiers, and the read-only unit normalizer. |
| `models/financial_normalization.py` | Read-only FX, tax-basis, rounding, and tolerance classification. |
| `models/discount_authority.py` | Contract concessions, discount approvals, approval events, and the read-only discount evaluator. |
| `models/sale_quotation_compliance.py` | Quotation compliance evaluator, confirmed price lock, override wizard, and `sale.order` confirmation gate. |
| `models/invoice_source.py` | Posted-invoice source mapper, source evidence, allocations, and documentary verification. |
| `models/invoice_audit.py` | Invoice audit run, append-only audit result, potential leakage finding, and the read-only audit engine. |
| `models/leakage_case.py` | Investigation case, membership, checklist, evidence, events, and finance-review snapshot. |
| `models/leakage_reassessment.py` | Reassessment request, proposal digest, acceptance, and append-only events. |
| `models/finance_validation.py` | Finance validation of accepted leakage evidence. Not a receivable, a waiver, or collected cash. |
| `models/recovery_authorization.py` | Recovery request, waiver, dispute, settlement, allocation balance, and the accounting handoff. Billed and collected stay 0 on that handoff. |
| `models/recovery_billing.py` | Recovery billing, policy, accounting link, collection evidence, and credit classification. A draft is not posted cash. |
| `models/pricing_applicability.py` | Read-only contract applicability resolver and diagnostic check. |
| `security/security_groups.xml` | Eight role records. |
| `security/ir.model.access.csv` | Policy, contract, version, applicability-check, and discount access rows. Contract header and approved versions have no unlink. Discount events have no write or unlink. |
| `security/pricing_applicability_rules.xml` | Company and creator rules for the diagnostic check. |
| `security/discount_rules.xml` | Company and owner rules for concessions, approvals, and events. |
| `security/sale_price_lock_rules.xml` | Global company rules for the price lock and the override wizard. |
| `security/invoice_source_rules.xml` | Global company rules for invoice source evidence and the verification wizard. |
| `security/invoice_audit_rules.xml` | Global company rules for audit runs, audit results, and potential findings. |
| `security/leakage_case_rules.xml` | Global company rules for investigation cases and related records. |
| `security/leakage_reassessment_rules.xml` | Global company rules for reassessment requests, events, and the wizard. |
| `security/finance_validation_rules.xml` | Global company rules for finance policies, validations, lines, approvals, and the wizard. |
| `security/recovery_rules.xml` | Global company rules for recovery policies, requests, waivers, disputes, settlements, events, balances, and the wizard. |
| `security/billing_rules.xml` | Global company rules for billing policies, billings, lines, links, collection evidence, and adjustments. |
| `security/contract_version_rules.xml` | Company and owner rules for versions. |
| `security/company_policy_rules.xml` | Company record rule for policy. |
| `security/customer_contract_rules.xml` | Company and owner rules for contracts. |
| `data/ir_sequence.xml` | Contract reference sequence. |
| `data/audit_sequence.xml` | Audit-run and leakage-finding reference sequences. |
| `data/case_sequence.xml` | Investigation case reference sequence. |
| `data/reassessment_sequence.xml` | Reassessment reference sequence. |
| `data/finance_validation_sequence.xml` | Finance policy and validation reference sequences. No amount is seeded. |
| `data/recovery_sequence.xml` | Recovery policy, request, waiver, dispute, and settlement sequences. No amount is seeded. |
| `data/billing_sequence.xml` | Billing policy and billing reference sequences. No journal, tax, or amount is seeded. |
| `views/company_policy_views.xml` | Configuration list, form, search, and menus. |
| `views/customer_contract_views.xml` | Contract list, form, search, and menus. |
| `views/contract_version_views.xml` | Version list, form, comparison wizard, and menus. |
| `views/pricing_applicability_views.xml` | Applicability check form, list, and menu. |
| `views/discount_views.xml` | Discount page, approval form, and menus. |
| `views/sale_quotation_views.xml` | Sales quotation compliance page, line warnings, and override buttons. |
| `views/invoice_source_views.xml` | Invoice source list, form, verification wizard, and invoice smart button. |
| `views/invoice_audit_views.xml` | Audit run, result, finding, and exception views, plus the invoice audit smart button. |
| `views/leakage_case_views.xml` | Investigation case list, form, kanban, search, wizard, and menus. |
| `views/leakage_reassessment_views.xml` | Reassessment list, form, decision wizard, and menu. |
| `views/finance_validation_views.xml` | Finance review queues, validation form, policy form, and decision wizard. |
| `views/recovery_views.xml` | Recovery, waiver, dispute, settlement, and commercial-policy screens. The prepare button does not itself post an invoice. |
| `views/billing_views.xml` | Recovery billing, collection, credit, and overdue screens. No stored Paid flag. |
| `tests/test_foundation_smoke.py` | Foundation smoke tests. |
| `tests/test_security_foundation.py` | Role and group security tests. |
| `tests/test_company_policy.py` | Company policy tests CFG-T001–CFG-T050. |
| `tests/test_customer_contract.py` | Contract header, line, lifecycle, and security tests. |
| `tests/test_contract_version.py` | Version, amendment, history, security, and concurrency tests. |
| `tests/test_pricing_applicability.py` | Applicability, date, grandfathering, precedence, and security tests. |
| `tests/test_quantity_tier.py` | Quantity tier, boundary, conversion, partial-quantity, and security tests. |
| `tests/test_financial_normalization.py` | FX, tax, precision, tolerance, security, and regression tests. |
| `tests/test_discount_authority.py` | Discount, approval, override, history, and security tests. |
| `tests/test_sale_quotation_compliance.py` | Quotation price, confirmation, price-lock, approval, and security tests. |
| `tests/test_invoice_source.py` | Posted-invoice eligibility, source mapping, allocation, credit, and security tests. |
| `tests/test_invoice_audit.py` | Posted-invoice potential leakage, historical price, credit, duplicate, reassessment, and security tests. |
| `tests/test_leakage_case.py` | Investigation case, grouping, workflow, evidence, and security tests. |
| `tests/test_recovery_authorization.py` | Commercial recovery, waiver, dispute, settlement, handoff, and security tests bound onto the invoice-audit class. |
| `tests/test_recovery_billing.py` | Recovery billing, tax, payment, credit, aging, and security tests bound onto the invoice-audit class. |
| `docs/app04/step02/` | Step 02 security evidence. |
| `docs/app04/step03/` | Step 03 configuration evidence. |
| `docs/app04/step04/` | Step 04 contract master evidence. |
| `docs/app04/step05/` | Step 05 version and amendment evidence. |
| `docs/app04/step06/` | Step 06 applicability evidence. |
| `docs/app04/step07/` | Step 07 quantity tier and unit-normalization evidence. |
| `docs/app04/step08/` | Step 08 financial normalization evidence. |
| `docs/app04/step09/` | Step 09 authorized discount evidence. |
| `docs/app04/step10/` | Step 10 quotation compliance evidence. |
| `docs/app04/step11/` | Step 11 invoice source-mapping evidence. |
| `docs/app04/step12/` | Step 12 posted-invoice potential-leakage evidence. |
| `docs/app04/step13/` | Step 13 investigation-case evidence. |
| `docs/app04/step14/` | Step 14 reassessment evidence. |
| `docs/app04/step15/` | Step 15 finance-validation evidence. |
| `docs/app04/step16/` | Step 16 recovery, waiver, dispute, and settlement evidence. |
| `docs/app04/step17/` | Step 17 recovery billing and collection evidence. DEV-18 is not implemented. |
| `DEVELOPMENT_PROGRESS.md` | Phase tracker. |
| `docs/app04/step00/` | Step 00 baseline. Not a sign-off. |
| `docs/app04/step01/` | Step 01 evidence. |

## Boundaries

- Community Edition only. Enterprise accounting is not a dependency.
- License decision is still open (`BLOCKER_LICENSE_DECISION_REQUIRED`). The manifest value `Other proprietary` is a loader guard, not a license grant.
- Do not install this addon into a production database.
- Local test databases and cache belong in `local_testing/`. That directory is omitted from publication. `python local_testing/free_space.py` removes only the `cpla_` databases named in that folder.
- Do not treat step 00 or step 01 as an approved financial design.
- Accepting a reassessment does not validate, bill, or collect the amount. The original audit result stays.
