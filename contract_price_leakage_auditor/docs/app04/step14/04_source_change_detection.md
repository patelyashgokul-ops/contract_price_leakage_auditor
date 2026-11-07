# Source change detection

Date: 2026-11-05.

## Fingerprint

The DEV-12 fingerprint is the hash of the engine inputs for one line, allocation, cutoff, version, and outcome. The reassessment stores `original_fingerprint` from the finding and `proposed_fingerprint` from the fresh outcome. Same fingerprint and same identity is `no_material_change`. Acceptance then does not create another current finding.

A fingerprint changes when a relevant input changes: quantity, price, version, cutoff, credit class, currency, tax basis, or UoM outcome. An unrelated contract note that does not enter those inputs does not by itself change the fingerprint. DEV-14 does not hook `write()` on the contract and does not add a cron.

## Material class

`change_class` is set from the trigger. `MATERIAL_CHANGE` is `financially_material`, `authority_material`, and `source_mapping_material`. A material rejection with no later acceptance leaves the finding at `source_changed_review_pending`. A non-material open request is still an open reassessment and is not displayed as `current_verified`.

## Affected findings

`affected_findings(company, version=None, partner=None, product=None)` searches current findings in that company only. Optional version, partner, and product narrow the domain. A version from another company raises `UserError`: "That contract version is not in this company. No finding was selected." A user whose companies do not include the target company gets `AccessError`, unless the caller is superuser. The method does not create a reassessment. Callers pass the contract, product, customer, and period they already know. It does not scan every finding in every company.

## Triggers that do not invent a number

`approved_discount_correction` stays in evidence review unless an approved `cpla.discount.approval` exists for the same company, customer, and product, and, when a cutoff is set, `approved_at` is on or before that cutoff. The reason is: "No approved discount correction is visible at this cutoff. The previous price was not replaced."

`historical_fx_correction` and `tax_basis_correction` always return evidence review: "No verified replacement FX rate or tax evidence was supplied. No corrected amount was fabricated." They do not call the engine to fill in a rate. Acceptance of `evidence_review_required` raises `UserError` because the state is not `proposed_revision_ready`.
