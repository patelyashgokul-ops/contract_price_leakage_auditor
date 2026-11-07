# 08 — Automated test results

Date: 2026-10-28.

Runner: `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe` and `C:\PycharmProjects\odoo19\odoo-19.0\odoo-bin`.

Config: `C:\PycharmProjects\odoo19\odoo-19.0\odoo.conf`. Flags: `--without-demo=True`, `--http-interface=127.0.0.1`, `--stop-after-init`, `--test-tags=/contract_price_leakage_auditor`.

The authoritative line is Odoo's `odoo.tests.result` count. The stats line counts 79 entries for the same run. This document uses 73.

An earlier upgrade at 04:32 on `cpla_dev01_foundation_20261028` reported `0 failed, 4 error(s) of 73 tests`. All four were `TypeError` in Odoo's `assertRaises` because the test passed a tuple of exception classes. That test bug was fixed. The two runs below are the evidence for this phase. No model change was required after that fix.

## Commands

Upgrade, database `cpla_dev01_foundation_20261028`, port 8079, `-u contract_price_leakage_auditor`.

Started 2026-10-28 04:36:15. Result at 04:36:31:

`0 failed, 0 error(s) of 73 tests when loading database 'cpla_dev01_foundation_20261028'`

`73 post-tests in 6.68s, 4681 queries`. Process exit 0.

Fresh install, database `cpla_dev03_fresh_20261028`, created from `template1` for this run, port 8080, `-i contract_price_leakage_auditor`.

Database initialization logged at 04:37:30. `uom` loaded as module 3/30, `mail` as 15/30, `product` as 26/30. `Module contract_price_leakage_auditor loaded` at 04:38:10. `Modules loaded.` at 04:38:43. Result at 04:38:50:

`0 failed, 0 error(s) of 73 tests when loading database 'cpla_dev03_fresh_20261028'`

`73 post-tests in 6.77s, 4683 queries`. Process exit 0.

Both logs include the expected warning `Missing author key ... defaulting to ''`. No production database was used.

## CFG results

Every row below executed inside both commands. Result Pass means the suite result line was `0 failed, 0 error(s)` and the method logged `Starting` with no following failure.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| CFG-T001 | Yes | Pass | `test_cfg_t001_company_a_configuration_can_be_created` |
| CFG-T002 | Yes | Pass | `test_cfg_t002_company_b_configuration_is_independent` |
| CFG-T003 | Yes | Pass | `test_cfg_t003_company_a_changes_do_not_alter_company_b` |
| CFG-T004 | Yes | Pass | `test_cfg_t004_unapproved_policies_do_not_become_operational` |
| CFG-T005 | Yes | Pass | `test_cfg_t005_required_configuration_fields_are_validated` |
| CFG-T006 | Yes | Pass | `test_cfg_t006_invalid_policy_selection_is_rejected` |
| CFG-T007 | Yes | Pass | `test_cfg_t007_duplicate_active_policy_versions_are_prevented` |
| CFG-T008 | Yes | Pass | `test_cfg_t008_historical_policy_remains_traceable` |
| CFG-T009 | Yes | Pass | `test_cfg_t009_invalid_effective_date_is_rejected` |
| CFG-T010 | Yes | Pass | `test_cfg_t010_repeated_save_does_not_duplicate_revisions` |
| CFG-T011 | Yes | Pass | `test_cfg_t011_valid_pricing_date_candidate_is_draft_only` |
| CFG-T012 | Yes | Pass | `test_cfg_t012_unresolved_pricing_date_stays_incomplete` |
| CFG-T013 | Yes | Pass | `test_cfg_t013_contract_specific_priority_is_documented_only` |
| CFG-T014 | Yes | Pass | `test_cfg_t014_invalid_precedence_configuration_is_rejected` |
| CFG-T015 | Yes | Pass | `test_cfg_t015_conflict_state_does_not_produce_false_readiness` |
| CFG-T016 | Yes | Pass | `test_cfg_t016_company_currency_is_identified` |
| CFG-T017 | Yes | Pass | `test_cfg_t017_currency_reference_is_validated_without_activation` |
| CFG-T018 | Yes | Pass | `test_cfg_t018_missing_fx_basis_is_flagged` |
| CFG-T019 | Yes | Pass | `test_cfg_t019_fx_policy_is_isolated_by_company` |
| CFG-T020 | Yes | Pass | `test_cfg_t020_payment_date_fx_is_not_pricing_leakage`. Policy fixture only. |
| CFG-T021 | Yes | Pass | `test_cfg_t021_valid_product_master_is_accepted` |
| CFG-T022 | Yes | Pass | `test_cfg_t022_wrong_company_product_is_rejected` |
| CFG-T023 | Yes | Pass | `test_cfg_t023_shared_product_is_accepted_without_contract_inheritance` |
| CFG-T024 | Yes | Pass | `test_cfg_t024_product_variant_mapping_is_validated` |
| CFG-T025 | Yes | Pass | `test_cfg_t025_valid_uom_conversion_is_accepted` |
| CFG-T026 | Yes | Pass | `test_cfg_t026_invalid_or_incompatible_conversion_is_flagged` |
| CFG-T027 | Yes | Pass | `test_cfg_t027_packaging_is_not_treated_as_the_price_uom` |
| CFG-T028 | Yes | Pass | `test_cfg_t028_archived_product_is_reviewed_not_deleted` |
| CFG-T029 | Yes | Pass | `test_cfg_t029_precision_candidate_does_not_round_away_a_difference` |
| CFG-T030 | Yes | Pass | `test_cfg_t030_negative_tolerance_is_rejected_and_positive_is_not_stored` |
| CFG-T031 | Yes | Pass | `test_cfg_t031_missing_tax_comparison_policy_is_flagged` |
| CFG-T032 | Yes | Pass | `test_cfg_t032_tax_inclusive_and_exclusive_are_not_comparable` |
| CFG-T033 | Yes | Pass | `test_cfg_t033_unverified_tax_treatment_cannot_be_approved_ready` |
| CFG-T034 | Yes | Pass | `test_cfg_t034_contract_user_cannot_edit_company_policy` |
| CFG-T035 | Yes | Pass | `test_cfg_t035_finance_reviewer_cannot_alter_approval_limits` |
| CFG-T036 | Yes | Pass | `test_cfg_t036_company_a_user_cannot_modify_company_b` |
| CFG-T037 | Yes | Pass | `test_cfg_t037_direct_configuration_update_outside_scope_is_rejected` |
| CFG-T038 | Yes | Pass | `test_cfg_t038_configuration_manager_can_edit_a_draft` |
| CFG-T039 | Yes | Pass | `test_cfg_t039_historical_change_records_cannot_be_rewritten` |
| CFG-T040 | Yes | Pass | `test_cfg_t040_sensitive_settings_are_not_exposed_to_unauthorized_readers` |
| CFG-T041 | Yes | Pass | `test_cfg_t041_valid_draft_change_is_recorded` |
| CFG-T042 | Yes | Pass | `test_cfg_t042_activation_does_not_create_an_approved_revision`. Activation refused. |
| CFG-T043 | Yes | Pass | `test_cfg_t043_failed_activation_leaves_no_partial_active_state` |
| CFG-T044 | Yes | Pass | `test_cfg_t044_unapproved_change_does_not_supersede_into_an_approval` |
| CFG-T045 | Yes | Pass | `test_cfg_t045_previous_policy_snapshot_remains_traceable` |
| CFG-T046 | Yes | Pass | Fresh `-i` exit 0 on `cpla_dev03_fresh_20261028`, plus `test_cfg_t046_module_install_state_is_consistent` (`latest_version` `19.0.1.1.0`). |
| CFG-T047 | Yes | Pass | Upgrade `-u` exit 0 on `cpla_dev01_foundation_20261028`, plus `test_cfg_t047_updated_module_keeps_dev02_groups`. |
| CFG-T048 | Yes | Pass | `test_cfg_t048_security_and_policy_records_are_not_duplicated`. Five ACL rows, one rule, eight groups, zero XML policy rows. |
| CFG-T049 | Yes | Pass | `test_cfg_t049_foundation_remains_operational` and SMOKE-001–008 in the same run. |
| CFG-T050 | Yes | Pass | `test_cfg_t050_views_and_fields_load`. Form and list `get_view`, including Contract Manager. |

Extra methods in the same class, also passed in both runs:

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| Customer identity | Yes | Pass | `test_cfg_customer_identity_and_archived_history` |
| Cross-company approver | Yes | Pass | `test_cfg_cross_company_approval_reference_is_rejected` |
| Golden fixtures | Yes | Pass | `test_cfg_golden_fixtures_remain_reference_only`. `audited` false and `implemented` false. Arithmetic only. |

## Regression of earlier tests

SMOKE-001–008, SEC-T001–T007, and SEC-T029–T032 ran again in both commands and are included in the 73 passing tests. SEC-T008–T015 remain unexecuted under those IDs.

## Not measured

No browser session opened the settings form. CFG-T050 loads the view architecture on the server. No production-scale timing was measured. The only timings are the post-test figures above. Readiness does not search invoices.
