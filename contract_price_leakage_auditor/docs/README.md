# Documentation index

Step 00 source of truth: [app04/step00/README.md](app04/step00/README.md). Its business acceptance is pending.

Step 01 evidence: [app04/step01/06_dev01_progress.md](app04/step01/06_dev01_progress.md). The foundation is installable. Technical acceptance is partial because the license is not decided.

Step 02 evidence: [app04/step02/08_dev02_progress.md](app04/step02/08_dev02_progress.md). Role security is implemented for the groups that exist. Business acceptance is pending. That file is the historical step 02 record.

Step 03 evidence: [app04/step03/09_dev03_progress.md](app04/step03/09_dev03_progress.md). Company policy revisions and readiness checks are implemented. Business acceptance is pending. Draft choices are not approved policies.

Step 04 evidence: [app04/step04/09_dev04_progress.md](app04/step04/09_dev04_progress.md). Draft customer contracts, negotiated lines, and evidence files are implemented. Business acceptance is pending. Ready for review is not an approved price.

Step 05 evidence: [app04/step05/11_dev05_progress.md](app04/step05/11_dev05_progress.md). Approved contract versions, amendments, and supersession are implemented. Business acceptance is pending. Version chronology is not invoice matching.

Step 06 evidence: [app04/step06/12_dev06_progress.md](app04/step06/12_dev06_progress.md). The applicability resolver selects one approved version or returns an explicit review outcome. Business acceptance is pending. A match is not an invoice-audit price.

Step 07 evidence: [app04/step07/12_dev07_progress.md](app04/step07/12_dev07_progress.md). Approved full-volume quantity tiers and snapshotted unit conversion are implemented. Business acceptance is pending. A normalized price is not an invoice-audit price.

Step 08 evidence: [app04/step08/13_dev08_progress.md](app04/step08/13_dev08_progress.md). An explicit contract clause can normalize currency, a simple tax basis, and rounding. Business acceptance is pending. A comparable price is not an invoice-audit price.

Step 09 evidence: [app04/step09/13_dev09_progress.md](app04/step09/13_dev09_progress.md). An approved concession or override can adjust that comparable price. Business acceptance is pending. The adjusted price is not an invoice-audit price.

Step 10 evidence: [app04/step10/13_dev10_progress.md](app04/step10/13_dev10_progress.md). A sales quotation is checked against that adjusted price before confirmation. Business acceptance is pending. Preventive exposure is not recovered cash.

Step 11 evidence: [app04/step11/14_dev11_progress.md](app04/step11/14_dev11_progress.md). Posted customer invoice lines are mapped to sales sources and historical price evidence. Business acceptance is pending. A source mapping is not a leakage finding.

Step 12 evidence: [app04/step12/15_dev12_progress.md](app04/step12/15_dev12_progress.md). Posted customer invoices are compared with the approved historical price. Business acceptance is pending. Potential leakage is not finance-validated leakage.

The `00_*.md` files in this directory are the first-pass notes from the truncated prompt. They are preserved. Where they disagree with `app04/step00/`, the step 00 package wins. The truncation they describe was closed when the rest of the prompt arrived.

| Document | Contents |
| --- | --- |
| [00_REPOSITORY_AUDIT.md](00_REPOSITORY_AUDIT.md) | What exists on disk, Git limitation, nearby addons, source trees. |
| [00_REQUIREMENTS_SOURCE_INVENTORY.md](00_REQUIREMENTS_SOURCE_INVENTORY.md) | Where each requirement came from, and what was not available. |
| [00_P0_REQUIREMENTS_REGISTER.md](00_P0_REQUIREMENTS_REGISTER.md) | Normalized register for the P0 text that was actually received. |
| [00_COMMUNITY_DEPENDENCY_VERIFICATION.md](00_COMMUNITY_DEPENDENCY_VERIFICATION.md) | Odoo 18, 19, and 20 Community modules checked in the local trees. |
| [00_FINANCIAL_SECURITY_INVARIANTS.md](00_FINANCIAL_SECURITY_INVARIANTS.md) | Release-blocking money, evidence, and company-isolation rules. |
| [00_OPEN_DECISIONS.md](00_OPEN_DECISIONS.md) | Business rules that step 00 does not decide. |
| [00_GOLDEN_TEST_PLAN.md](00_GOLDEN_TEST_PLAN.md) | Planned financial oracles. None have been executed. |
| [00_RELEASE_READINESS.md](00_RELEASE_READINESS.md) | NO-GO position and the authorization checklist. |

Read the repository audit and the source inventory before the register. The register does not fill gaps by invention.
