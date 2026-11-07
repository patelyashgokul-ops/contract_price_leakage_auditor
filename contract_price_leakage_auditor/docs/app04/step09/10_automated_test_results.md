# Automated test results

Class `TestDev09DiscountAuthority` in `tests/test_discount_authority.py`. Tag `post_install`. Password `cpla-test`. Companies ABC India and ABC UAE.

Authoritative counts are the Odoo lines `N post-tests` and `0 failed, 0 error(s) of N tests`.

## Runs that contain these tests

| Run | Database | Command | Result |
| --- | --- | --- | --- |
| Class, before the five fixture and company fixes | `cpla_dev09_20261028` | `-i`, tag `TestDev09DiscountAuthority` | 2 failed, 3 error(s) of 57 tests. Log `C:\Users\Admin\AppData\Local\Temp\cpla_dev09_class.log`. |
| Class, after those fixes | `cpla_dev09_20261028` | `-u`, same tag | 57 post-tests in 44.93s, 18,199 queries. 0 failed, 0 error(s) of 57 tests. Log `cpla_dev09_class2.log`. |
| Full module, before the smoke access expectation | `cpla_dev09_20261028` | `-u`, tag `/contract_price_leakage_auditor` | 1 failed, 0 error(s) of 610 tests. `test_smoke_005_initial_security_groups` expected write on `cpla.discount.event`. Log `cpla_dev09_full.log`. |
| Full module | `cpla_dev09_20261028` | `-u`, same tag | 610 post-tests in 194.95s, 116,475 queries. 0 failed, 0 error(s) of 610 tests. Log `cpla_dev09_full2.log`. |
| Upgrade from DEV-08 | `cpla_dev08_20261028` | `-u`, same tag | 610 post-tests in 188.80s, 116,472 queries. 0 failed, 0 error(s) of 610 tests. Log `cpla_dev09_upgrade.log`. |

The fresh database command is recorded in `11_installation_regression.md`. Every row below passed inside the two green 610-test runs. The class methods also passed in the green 57-test run.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| DISC09-T001 / GOLD-DISC-001 | Yes | PASS | `test_disc09_t001_gold_disc_001_special_price_and_reconciliation` |
| DISC09-T002 / GOLD-DISC-002 | Yes | PASS | `test_disc09_t002_gold_disc_002_percentage` |
| DISC09-T003 / GOLD-DISC-003 | Yes | PASS | `test_disc09_t003_gold_disc_003_fixed_reduction` |
| DISC09-T004 | Yes | PASS | `test_disc09_t004_foreign_amount_is_not_subtracted_without_a_rate` |
| DISC09-T005 / GOLD-DISC-009 | Yes | PASS | `test_disc09_t005_gold_disc_009_box_discount_converts_then_fx` |
| DISC09-T006 / GOLD-DISC-004 | Yes | PASS | `test_disc09_t006_gold_disc_004_sequential_percentages` |
| DISC09-T007 / GOLD-DISC-005 | Yes | PASS | `test_disc09_t007_gold_disc_005_additive_percentages` |
| DISC09-T008 / GOLD-DISC-006 | Yes | PASS | `test_disc09_t008_gold_disc_006_exclusive_special_is_not_discounted_again` |
| DISC09-T009 / GOLD-DISC-007 | Yes | PASS | `test_disc09_t009_gold_disc_007_percentage_then_fixed` |
| DISC09-T010 / GOLD-DISC-008 | Yes | PASS | `test_disc09_t010_gold_disc_008_fixed_then_percentage` |
| DISC09-T011 | Yes | PASS | `test_disc09_t011_one_percent_is_not_applied_twice` |
| DISC09-T012 | Yes | PASS | `test_disc09_t012_two_concessions_without_a_mode_stay_in_review` |
| DISC09-T013 | Yes | PASS | `test_disc09_t013_unsupported_benefit_is_not_converted` |
| DISC09-T014 | Yes | PASS | `test_disc09_t014_exact_stack_is_not_rounded_early_and_per_unit_rounds_once` |
| DISC09-T015 | Yes | PASS | `test_disc09_t015_a_non_positive_price_is_refused` |
| DISC09-T016 / GOLD-DISC-001 reconciliation | Yes | PASS | Same method as T001. Extensions 25,000 / 50,000 / 25,000. |
| GOLD-DISC-010, GOLD-DISC-011 | Yes | PASS | `test_gold_disc_010_and_011_expired_and_future_dates` |
| GOLD-DISC-012, GOLD-DISC-013 | Yes | PASS | `test_gold_disc_012_and_013_wrong_customer_and_variant` |
| GOLD-DISC-014 | Yes | PASS | `test_gold_disc_014_override_exposure_uses_the_adjusted_baseline` |
| GOLD-DISC-015 | Yes | PASS | `test_gold_disc_015_rejected_override_is_not_a_price` |
| GOLD-DISC-016 | Yes | PASS | `test_gold_disc_016_an_entered_discount_without_approval_is_not_authorized` |
| GOLD-DISC-017 | Yes | PASS | `test_gold_disc_017_his09_retroactive_grant_respects_the_cutoff` |
| GOLD-DISC-018 | Yes | PASS | `test_gold_disc_018_exclusive_prices_without_precedence_conflict` |
| GOLD-DISC-019 | Yes | PASS | `test_gold_disc_019_tier_policy_is_explicit` |
| GOLD-DISC-020 | Yes | PASS | `test_gold_disc_020_no_recovery_or_accounting_document` |
| APP09-T001 | Yes | PASS | `test_app09_t001_owner_creates_a_draft_and_cannot_set_the_approver` |
| APP09-T002 | Yes | PASS | `test_app09_t002_submit_requires_evidence_and_scope` |
| APP09-T003 | Yes | PASS | `test_app09_t003_finance_manager_approves_within_the_limit` |
| APP09-T004 | Yes | PASS | `test_app09_t004_manager_reviewer_and_admin_cannot_approve` |
| APP09-T005 | Yes | PASS | `test_app09_t005_combined_role_cannot_self_approve` |
| APP09-T006 | Yes | PASS | `test_app09_t006_unit_percent_and_exposure_limits_block` |
| APP09-T007 | Yes | PASS | `test_app09_t007_cross_currency_and_uom_are_not_invented` |
| APP09-T008 | Yes | PASS | `test_app09_t008_an_empty_limit_does_not_approve` |
| APP09-T009, APP09-T010 | Yes | PASS | `test_app09_t009_t010_approver_and_timestamp_come_from_the_server` |
| APP09-T011, APP09-T012 | Yes | PASS | `test_app09_t011_and_t012_rejected_and_cancelled_are_excluded` |
| APP09-T013, APP09-T014 | Yes | PASS | `test_app09_t013_and_t014_future_and_expired_requests_are_not_applied` |
| APP09-T015 | Yes | PASS | `test_app09_t015_approved_terms_and_history_cannot_be_rewritten` |
| APP09-T016, APP09-T017 | Yes | PASS | `test_app09_t016_t017_repeat_and_conflict_do_not_duplicate_authority` |
| APP09-T018 | Yes | PASS | `test_app09_t018_events_follow_the_real_actor` |
| HIS09-T001 | Yes | PASS | `test_his09_t001_version_customer_only` |
| HIS09-T002, HIS09-T003 | Yes | PASS | `test_his09_t002_t003_branch_is_named_and_another_company_is_not` |
| HIS09-T004, HIS09-T005 | Yes | PASS | `test_his09_t004_t005_variant_and_template_scope` |
| HIS09-T006 | Yes | PASS | `test_his09_t006_quantity_bounds` |
| HIS09-T007, HIS09-T008 | Yes | PASS | `test_his09_t007_and_t008_pricing_date_and_knowledge_cutoff` |
| HIS09-T009, HIS09-T010 | Yes | PASS | `test_gold_disc_017_his09_retroactive_grant_respects_the_cutoff` |
| HIS09-T011 | Yes | PASS | `test_his09_t011_revocation_keeps_the_original_amount` |
| HIS09-T012 | Yes | PASS | `test_his09_t012_con09_t006_amendment_does_not_change_the_old_amount` |
| HIS09-T013 | Yes | PASS | `test_his09_t013_a_pricelist_discount_is_not_contract_authority` |
| HIS09-T014, HIS09-T015, HIS09-T016 | Yes | PASS | `test_his09_t014_t015_t016_snapshot_repeatability_and_conflict` |
| OVR09-T001, OVR09-T002, OVR09-T003 | Yes | PASS | `test_ovr09_t001_t002_exposure_and_company` |
| OVR09-T004, OVR09-T005, OVR09-T006 | Yes | PASS | `test_ovr09_t004_t005_t006_wrong_scope_is_rejected` |
| OVR09-T007 through OVR09-T011 | Yes | PASS | `test_ovr09_t007_through_t011_quantity_dates_and_order_scope` |
| OVR09-T012, OVR09-T013, OVR09-T014 | Yes | PASS | `test_ovr09_t012_t013_t014_evaluation_creates_nothing` |
| SEC09-T001 through SEC09-T003, SEC09-T006, SEC09-T007, SEC09-T014 | Yes | PASS | `test_sec09_company_isolation_and_read_only_roles` |
| SEC09-T004 | Yes | PASS | `test_app09_t004_manager_reviewer_and_admin_cannot_approve` |
| SEC09-T005 | Yes | PASS | `test_app09_t005_combined_role_cannot_self_approve` |
| SEC09-T008, SEC09-T009, SEC09-T010 | Yes | PASS | `test_sec09_attachment_export_and_forged_event` |
| SEC09-T011 | Yes | PASS | Existing SEC-T007 source scan, included in the 610 tests. |
| SEC09-T012, SEC09-T013 | Yes | PASS | `test_app09_t015_approved_terms_and_history_cannot_be_rewritten` and the event unlink assertion. |
| INT09-T001 through INT09-T014 | Yes | PASS | `test_int09_resolver_keeps_dev06_dev07_and_dev08`, plus GOLD-DISC-009, GOLD-DISC-019, and GOLD-DISC-020. |
| CON09-T001, CON09-T002 | Yes | PASS | `test_app09_t016_t017_repeat_and_conflict_do_not_duplicate_authority` |
| CON09-T003 | Yes | PASS | `test_app09_t008_an_empty_limit_does_not_approve` |
| CON09-T004 | Yes | PASS | `test_ovr09_t012_t013_t014_evaluation_creates_nothing` and `test_dev09_repeated_evaluation_stays_under_the_ceiling` |
| CON09-T005 | Yes | PASS | `test_con09_stale_superseded_request_is_not_approved` |
| CON09-T006 | Yes | PASS | `test_his09_t012_con09_t006_amendment_does_not_change_the_old_amount` |
| REG09-T001 | Yes | PASS | Fresh `-i` of `cpla_dev09_fresh_20261028`: 0 failed, 0 error(s) of 610 tests. |
| REG09-T002 through REG09-T012 | Yes | PASS | Upgrade log plus `test_reg09_views_manifest_and_no_audit_cron` and the prior-phase tests inside the 610. |

A second database worker was not started. Concurrent approval is covered by a repeated call and by a conflicting second request inside one `TransactionCase`. PostgreSQL serialization across two workers was not executed.

Browser tools were not available. Forms were loaded with `get_view` in `test_reg09_views_manifest_and_no_audit_cron`. That is not browser verification.
