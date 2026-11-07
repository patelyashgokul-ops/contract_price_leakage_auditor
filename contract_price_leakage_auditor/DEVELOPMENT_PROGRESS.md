# Development progress

Product: APP 04 — Contract Price Leakage Auditor
Master target: Odoo 19 Community (`19.0.0` final)
Future targets: Odoo 18 Community and Odoo 20 Community
Update date: 2026-11-05

Step 00 record: `docs/app04/step00/10_phase00_progress_and_signoff.md`
Step 01 record: `docs/app04/step01/06_dev01_progress.md`
Step 02 record: `docs/app04/step02/08_dev02_progress.md`
Step 03 record: `docs/app04/step03/09_dev03_progress.md`
Step 04 record: `docs/app04/step04/09_dev04_progress.md`
Step 05 record: `docs/app04/step05/11_dev05_progress.md`
Step 06 record: `docs/app04/step06/12_dev06_progress.md`
Step 07 record: `docs/app04/step07/12_dev07_progress.md`
Step 08 record: `docs/app04/step08/13_dev08_progress.md`
Step 09 record: `docs/app04/step09/13_dev09_progress.md`
Step 10 record: `docs/app04/step10/13_dev10_progress.md`
Step 11 record: `docs/app04/step11/14_dev11_progress.md`
Step 12 record: `docs/app04/step12/15_dev12_progress.md`
Step 13 record: `docs/app04/step13/16_dev13_progress.md`
Step 14 record: `docs/app04/step14/16_dev14_progress.md`
Step 15 record: `docs/app04/step15/16_dev15_progress.md`
Step 16 record: `docs/app04/step16/16_dev16_progress.md`

**PHASE 00 IMPLEMENTATION: PARTIAL**

**PHASE 00 BUSINESS ACCEPTANCE: PENDING**

**PHASE 01 IMPLEMENTATION: PARTIALLY_COMPLETE_WITH_BLOCKERS**

**PHASE 01 BUSINESS ACCEPTANCE: PENDING**

**PHASE 02 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 02 BUSINESS ACCEPTANCE: PENDING**

**PHASE 03 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 03 BUSINESS ACCEPTANCE: PENDING**

**PHASE 04 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 04 BUSINESS ACCEPTANCE: PENDING**

**PHASE 05 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 05 BUSINESS ACCEPTANCE: PENDING**

**PHASE 06 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 06 BUSINESS ACCEPTANCE: PENDING**

**PHASE 07 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 07 BUSINESS ACCEPTANCE: PENDING**

**PHASE 08 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 08 BUSINESS ACCEPTANCE: PENDING**

**PHASE 09 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 09 BUSINESS ACCEPTANCE: PENDING**

**PHASE 10 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 10 BUSINESS ACCEPTANCE: PENDING**

**PHASE 11 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 11 BUSINESS ACCEPTANCE: PENDING**

**PHASE 12 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 12 BUSINESS ACCEPTANCE: PENDING**

**PHASE 13 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 13 BUSINESS ACCEPTANCE: PENDING**

**PHASE 14 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 14 BUSINESS ACCEPTANCE: PENDING**

**PHASE 15 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 15 BUSINESS ACCEPTANCE: PENDING**

**PHASE 16 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 16 BUSINESS ACCEPTANCE: PENDING**

**PHASE 17 IMPLEMENTATION: IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING**

**PHASE 17 BUSINESS ACCEPTANCE: PENDING**

The technical addon name is `contract_price_leakage_auditor`, version `19.0.1.12.0`. Direct dependencies are `base`, `product`, and `sale`. `uom` and `mail` install because `product` depends on them. `account` installs because `sale` depends on it. `account` is not a direct dependency. The addon has company-policy revisions, a configuration menu, draft customer contracts with negotiated lines, approved contract-version snapshots, a read-only applicability resolver, approved quantity-tier snapshots with unit normalization, a read-only financial normalizer for an explicit contract FX and tax clause, authorized concessions with discount-approval requests, a sales-quotation compliance gate with a confirmed-order price lock, posted customer-invoice source mapping, a posted-invoice potential-leakage audit, an investigation case for a current finding, and a controlled reassessment that keeps the original audit result. Ready for review is not approval. An approved version is not an invoice-audit price. A resolver match is not a leakage amount. A normalized tier price is not a leakage amount. A currency-converted price is not a leakage amount. An approved concession is not unauthorized leakage. Preventive quotation exposure is not recovered cash. A source mapping is not a leakage finding. The invoice audit stores potential leakage on posted customer invoices. That amount is not finance-validated, not billed, and not collected. The case organizes that finding. A reassessment can propose a later reading. Accepting that reading is not finance validation. The module has no finance-validation workflow, recovery workflow, or cron.

Full DEV-01 technical acceptance is blocked by `BLOCKER_LICENSE_DECISION_REQUIRED`. No author identity is approved. DEV-02 role tests passed again on 2026-10-28. DEV-02 business acceptance is pending. DEV-03 company-policy tests passed on the upgrade database and on a fresh database. DEV-03 business acceptance is pending. Stored policy candidates are not approved rules. DEV-04 contract tests passed on a fresh disposable database on 2026-10-28: 0 failed, 0 errors of 155 tests. DEV-04 business acceptance is pending. A draft contract is not an audit price. DEV-05 version tests passed on 2026-10-28: upgrade `-u` of `cpla_dev04_20261028` and fresh `-i` of `cpla_dev05_20261028`, each 0 failed, 0 errors of 242 tests. DEV-05 business acceptance is pending. Version chronology is not invoice matching. DEV-06 applicability tests passed on 2026-10-28 after one failed update run: upgrade rerun of `cpla_dev05_20261028` and fresh `-i` of `cpla_dev06_20261028`, each 0 failed, 0 errors of 366 tests. The first update run was 2 failed, 0 errors of 366 tests. DEV-06 business acceptance is pending. A selected version is not an invoice-audit price. DEV-07 quantity-tier tests passed on 2026-10-28 after one failed update run: upgrade rerun of `cpla_dev06_20261028` and fresh `-i` of `cpla_dev07_20261028`, each 0 failed, 0 errors of 464 tests. The first update run was 2 failed, 2 errors of 464 tests. DEV-07 business acceptance is pending. A normalized unit price is not a leakage amount. DEV-08 financial tests passed on 2026-10-28 after one failed update run: upgrade rerun of `cpla_dev07_20261028` was 0 failed, 0 errors of 552 tests, then a final upgrade of the same database was 0 failed, 0 errors of 553 tests after the GOLD-TAX-003 assertion was added. Fresh `-i` of `cpla_dev08_20261028` was 0 failed, 0 errors of 552 tests before that extra assertion. DEV-08 business acceptance is pending. A comparable pre-discount price is not a leakage amount. DEV-09 discount tests passed on 2026-10-28: `-u` of `cpla_dev09_20261028`, `-u` of `cpla_dev08_20261028`, and fresh `-i` of `cpla_dev09_fresh_20261028`, each 0 failed, 0 errors of 610 tests. An earlier class run on `cpla_dev09_20261028` was 2 failed, 3 errors of 57 tests, and an earlier full run was 1 failed, 0 errors of 610 tests. Both were fixed and rerun. DEV-09 business acceptance is pending. An approved adjusted price is not a leakage amount. DEV-10 quotation tests passed on 2026-10-28. The class tag on `cpla_dev10_20261028` was 0 failed, 0 errors of 66 tests. The full tag on that database was 0 failed, 0 errors of 676 tests. The upgrade `-u` of `cpla_dev09_20261028` was 0 failed, 0 errors of 676 tests. The fresh `-i` of `cpla_dev10_fresh_20261028` was 1 failed, 0 errors of 676 tests, then the final `-u` rerun was 0 failed, 0 errors of 676 tests. Earlier class and full runs failed and were fixed before those green results. DEV-10 business acceptance is pending. Preventive exposure is not recovered cash. DEV-11 source-mapping tests passed on 2026-10-28 after one failed class run. That class run on `cpla_dev11_20261028` was 2 failed, 4 errors of 102 tests. The class rerun was 0 failed, 0 errors of 102 tests. The full tag on that database, the upgrade `-u` of `cpla_dev10_20261028` from `19.0.1.8.0`, and the fresh `-i` of `cpla_dev11_fresh_20261028` were each 0 failed, 0 errors of 778 tests. DEV-11 business acceptance is pending. A source mapping is not a leakage finding. DEV-12 audit tests passed on 2026-10-28 after one failed class run. That class run on `cpla_dev12_20261028` was 9 failed, 11 errors of 100 tests. The class rerun was 0 failed, 0 errors of 100 tests in 113.13s. The full tag on that database, the upgrade `-u` of `cpla_dev11_20261028`, and the fresh `-i` of `cpla_dev12_fresh_20261028` were each 0 failed, 0 errors of 878 tests. DEV-12 business acceptance is pending. Potential leakage is not finance-validated leakage. DEV-13 case tests passed on 2026-11-05 after three failed class runs on `cpla_dev13_20261105`: 7 errors, then 2 errors, then 1 error, each of 20 tests. The class rerun was 0 failed, 0 errors of 20 tests. The full tag on that database, the upgrade `-u` of `cpla_dev12_20261028` from `19.0.1.10.0`, and the fresh `-i` of `cpla_dev13_fresh_20261105` were each 0 failed, 0 errors of 898 tests. DEV-13 business acceptance is pending. A case is not finance validation. Two-worker case creation was not run. DEV-14 reassessment tests passed on 2026-11-05 after one failed class run on `cpla_dev14_20261105`: 1 failed, 0 errors of 111 tests. The assertion expected a current zero finding after a full reversal. The engine releases that row, and the assertion was aligned with that result. The class rerun was 0 failed, 0 errors of 111 tests. The full tag on that database was 0 failed, 0 errors of 909 tests. The upgrade `-u` of `cpla_dev13_20261105` from `19.0.1.11.0` was 0 failed, 0 errors of 909 tests. The fresh `-i` of `cpla_dev14_fresh_20261105` was 0 failed, 0 errors of 909 tests. An earlier `--test-tags=rev14` run was 0 failed of 0 tests and is not a pass. DEV-14 business acceptance is pending. Accepting a reassessment is not finance validation. Two-worker reassessment was not run.

| Step | Title | Code | Tests | Acceptance |
| --- | --- | --- | --- | --- |
| 00 | Repository audit and baseline | Documentation only. | Not run in step 00. | Implementation PARTIAL. Business acceptance PENDING. |
| 01 | Odoo 19 foundation | Manifest, role XML, smoke tests. | SMOKE-001–008 passed on disposable database `cpla_dev01_foundation_20261028`. | Implementation PARTIALLY_COMPLETE_WITH_BLOCKERS. Business acceptance PENDING. |
| 02 | Role security foundation | Group boundaries and security tests. Historical record: no business model at the end of that phase. | SEC-T001–T007 and SEC-T029–T032 passed, and they passed again with step 03. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. |
| 03 | Company policy and master-data readiness | `cpla.company.policy`, configuration UI, readiness checks. | CFG-T001–CFG-T050 passed. Upgrade and fresh install, 0 failed, 0 errors of 73 tests. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. Policies are not operationally approved. |
| 04 | Customer contract master | `cpla.customer.contract`, lines, and evidence. Draft, ready for review, cancelled. | CTH, CTL, LFC, SEC04, and golden fixtures passed inside the addon tag. Fresh `-i` on `cpla_dev04_20261028`, 0 failed, 0 errors of 155 tests. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. Contracts are not approved prices. |
| 05 | Contract versions and amendments | `cpla.customer.contract.version`, lines, evidence links, events. Full snapshots. | VER, AMD, HIS, SEC05, CON05, REG05, and CONTRACT-V tests passed inside the addon tag. Upgrade and fresh install, 0 failed, 0 errors of 242 tests. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. Versions are not invoice-audit prices. |
| 06 | Contract applicability and precedence | `cpla.pricing.applicability` and a diagnostic check. Exact customer and exact variant only. | APP, CUS06, PRD06, DAT06, GFD06, PRE06, SEC06, DET06, REG06. Update rerun and fresh install, 0 failed, 0 errors of 366 tests. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. A match is not leakage. |
| 07 | Quantity tiers and unit normalization | `cpla.customer.contract.version.tier` and `cpla.pricing.quantity`. Full-volume tiers, snapshotted factors, explicit quantity basis. | TIER07, QTY07, UOM07, PAR07, HIS07, SEC07, REG07, QT-REF-001–015. Update rerun and fresh install, 0 failed, 0 errors of 464 tests. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. A normalized price is not leakage. |
| 08 | Financial price normalization | `cpla.pricing.financial` on the contract version. Explicit FX clause, tax basis, rounding stage, and signed difference. | FX08, TAX08, PREC08, SEC08, HIS08, INT08, REG08. Final update 0 failed, 0 errors of 553 tests. Fresh install 0 failed, 0 errors of 552 tests. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. A comparable price is not leakage. |
| 09 | Authorized discounts and special prices | `cpla.discount.concession`, `cpla.discount.approval`, `cpla.discount.event`, and `cpla.discount.evaluator`. | DISC09, APP09, HIS09, OVR09, SEC09, INT09, CON09, REG09, GOLD-DISC-001–020. Update, upgrade, and fresh install, each 0 failed, 0 errors of 610 tests. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. An approved concession is not leakage. |
| 10 | Sales quotation compliance | `cpla.quotation.compliance`, `cpla.sale.price.lock`, and a draft override request on `cpla.discount.approval`. Company mode on the policy. `sale.order.action_confirm` gate. | PRICE10, CONF10, HIS10, APP10, SEC10, CON10 sequential, REG10. Full, upgrade, and fresh rerun, each 0 failed, 0 errors of 676 tests. Two-session confirmation was not run. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. Preventive exposure is not recovered cash. |
| 11 | Posted invoice source mapping | `cpla.invoice.source`, `cpla.invoice.source.map`, and `cpla.invoice.source.allocation`. Read-only evidence. No leakage finding. | INV11, MAP11, PAR11, REF11, FIN11, SEC11, IDM11. Class rerun 0 failed of 102. Full, upgrade, and fresh install, each 0 failed of 778. Two-session mapping was not run. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. A source mapping is not a leakage finding. |
| 12 | Posted invoice potential leakage | `cpla.invoice.audit.run`, `cpla.invoice.audit.result`, and `cpla.leakage.finding`. Detector findings only. | ELG12, HIS12, FIN12, PAR12, REF12, IDM12, SEC12, INT12, GOLD-AUD-001–020. Class rerun 0 failed of 100. Full, upgrade, and fresh install, each 0 failed of 878. Two-worker audit was not run. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. Potential leakage is not finance-validated leakage. |
| 13 | Investigation cases | `cpla.leakage.case` and membership, checklist, evidence, events, and finance-review snapshots. No finance validation. | CASE13, GRP13, WF13, OWN13, EVD13, FIN13, SEC13, CON13, REG13. Class rerun 0 failed of 20. Full, upgrade, and fresh install, each 0 failed of 898. Two-worker case creation was not run. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. A case is not recovered cash. |
| 14 | Historical evidence and controlled reassessment | `cpla.leakage.reassessment`, its event, and a reason wizard. Original audit results stay. Schema `dev14.2`. No finance validation. | REV14 t001–t016. Full `-u` on `cpla_dev14_20261105`, upgrade `-u` of `cpla_dev13_fresh_20261105` from `19.0.1.11.0`, and fresh `-i` of `cpla_dev14b_fresh_20261105`. Each 0 failed, 0 errors of 914 tests on 2026-11-05. Two-worker acceptance is `test_rev14_t016`. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. A reassessment is not finance validation. |
| 15 | Finance validation of accepted evidence | `cpla.finance.validation`, line, approval event, and company policy matrix. No seeded ceiling. No recovery, waiver, bill, or cash. | `test_fv15_*` on `cpla_dev14_20261105`: 0 failed, 0 errors of 14 tests, `local_testing/cpla_dev15_targeted7.log`. Full `-u` `cpla_dev15_full2.log` on `cpla_dev14_20261105`, upgrade `-u` `cpla_dev15_upgrade.log` of `cpla_dev14b_fresh_20261105` from `19.0.1.12.0`, and fresh `-i` `cpla_dev15_fresh.log` of `cpla_dev15_fresh_20261105`. Each 0 failed, 0 errors of 928 tests on 2026-11-05. Two-worker approval is `test_fv15_concurrent_approval_keeps_one_decision`. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. A validated amount is not billed and is not collected cash. |
| 16 | Commercial recovery, waiver, dispute, and settlement | `cpla.recovery.request`, line, waiver, dispute, settlement, balance, event, policy, and wizard. No seeded ceiling. No invoice, debit note, or payment. | `test_rec16_*`: targeted 0 failed of 13, `local_testing/dev16_targeted_2.log`. Full, upgrade from `19.0.1.13.0`, and fresh `-i` of `cpla_dev16_fresh_20261105`, each 0 failed, 0 errors of 941 tests on 2026-11-05. Two-worker waiver allocation is `test_rec16_concurrent_waiver_allocation`. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. An approved recovery target is not billed and is not collected cash. |
| 17 | Recovery billing and payment classification | `cpla.recovery.billing`, line, accounting link, collection evidence, adjustment, and billing policy. No seeded journal or tax. No cron. | `test_bill17_*`: targeted 0 failed of 30, `local_testing/dev17_targeted_3.log`. Full `-u` `dev17_full_1.log`, upgrade `-u` `dev17_upgrade_1.log` of `cpla_dev16_fresh_20261105` from `19.0.1.14.0`, and fresh `-i` `dev17_fresh_1.log` of `cpla_dev17_fresh_20261105`. Each 0 failed, 0 errors of 969 tests on 2026-11-05. Two-worker billing is `test_bill17_concurrent_prepare`. GOLD-ACC17-014 is `NOT_EXECUTED`. | Implementation IMPLEMENTATION_COMPLETE_ACCEPTANCE_PENDING. Business acceptance PENDING. Posted billing is not cash. |
| 18–22 | Not started. | No reminder cron, escalation, or executive dashboard. | No DEV-18 tests. | Not started. |

## Step 00 result

Step 00 found no existing APP 04 implementation and did not approve financial rules. That finding is unchanged. Step 00 did not itself authorize DEV-01. The later DEV-01 prompt authorized the foundation only.

Git history is still not available. The sibling addon `freight_invoice_audit_recovery` was not modified.

## Release position

Posted-invoice potential leakage is implemented. Investigation cases are implemented. Finance validation of accepted evidence is implemented. Commercial recovery, waiver, dispute, and settlement decisions are implemented. Recovery billing and payment classification are implemented. A posted recovery invoice is not bank-verified cash. Company policy storage is a draft configuration record. Customer contracts are draft agreements. Approved prices are version snapshots. The applicability resolver can name one approved snapshot or an explicit review outcome. Quantity tiers can name one full-volume rate and a normalized unit price. An explicit contract clause can name a pre-discount comparable price in one currency and one tax basis. An approved concession can name an adjusted unit price from that comparable price. A quotation gate can compare a sales order with that price and store the confirmed basis. A source map can name the posted invoice line, the sales line, and the historical basis. The audit finding is potential leakage for one current economic identity. It is not finance-validated and it is not recovered cash. The commercial release position remains NO-GO. Open decisions DEC-01 through DEC-20 are not approved. DEC-04 is not an operational quantity rule. DEC-06, DEC-07, and DEC-08 are not operational financial rules. The company discount candidate is not a stacking rule. The quotation compliance mode is not an approved tolerance. Manual invoices are not matched to a contract automatically. DEV-12 potential leakage is implemented and is not finance-validated. DEV-13 investigation cases are implemented. Submitting a case is not financial approval. Closing a case is not recovered cash. DEV-14 controlled reassessment is implemented. The 2026-11-05 full, upgrade, and fresh runs were each 0 failed of 914 tests. Two-worker acceptance was run in `test_rev14_t016`. Accepting a reassessment is not finance validation, and the delta is not recovered cash. The audit-run reread button can still move a finding without that decision. DEV-15 finance validation is implemented at `19.0.1.13.0`. The 2026-11-05 full, upgrade, and fresh runs were each 0 failed of 928 tests. A finance-validated amount is not a receivable, a waiver, or collected cash. No approval ceiling is seeded. DEV-16 commercial recovery is implemented at `19.0.1.14.0`. The 2026-11-05 targeted rerun was 0 failed of 13 tests. The full, upgrade-from-13.0, and fresh runs were each 0 failed of 941 tests. An approved recovery target is not a posted invoice and is not collected cash. No commercial ceiling is seeded. DEV-17 recovery billing is implemented at `19.0.1.15.0`. The 2026-11-05 targeted rerun was 0 failed of 30 tests. The full, upgrade-from-14.0, and fresh runs were each 0 failed of 969 tests. A draft is not posted billing. A posted invoice is not bank-verified cash. A credit, write-off, or exchange difference is not recovered principal. DEV-16 billed and collected stay 0. GOLD-ACC17-014 was not executed. DEV-18 has not started.
