# Automated test results

Executed means the test method ran inside a green Odoo 19 process. The class tag on `cpla_dev10_20261028` was 0 failed, 0 errors of 66 tests (`cpla_dev10_class4.log`). The full tag on that database was 0 failed, 0 errors of 676 tests (`cpla_dev10_full3.log`). The upgrade of `cpla_dev09_20261028` was 0 failed, 0 errors of 676 tests (`cpla_dev10_upgrade.log`). The fresh rerun of `cpla_dev10_fresh_20261028` was 0 failed, 0 errors of 676 tests (`cpla_dev10_fresh2.log`).

Earlier red runs are in `11_installation_upgrade_regression.md`. They are not counted as passes.

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| PRICE10-T001 | Yes | Pass | `test_price10_t001_compliant_price` |
| PRICE10-T002 | Yes | Pass | `test_price10_t002_below_approved_price` |
| PRICE10-T003 | Yes | Pass | `test_price10_t003_additional_exposure_is_not_the_gross_gap`. Exposure `25000`, not `50000`. |
| PRICE10-T004 | Yes | Pass | `test_price10_t004_approved_special_price_is_not_unauthorized` |
| PRICE10-T005 | Yes | Pass | `test_price10_t005_native_discount_is_the_effective_price`. Effective `1140`. |
| PRICE10-T006 | Yes | Pass | `test_price10_t006_discount_already_in_price_unit_is_not_subtracted_again` |
| PRICE10-T007 | Yes | Pass | `test_price10_t007_order_quantity_selects_the_tier` |
| PRICE10-T008 | Yes | Pass | `test_price10_t008_and_t009_uom_and_fx_are_not_raw_box_values` |
| PRICE10-T009 | Yes | Pass | Same method as T008. Compared value is not the raw box price `50`. |
| PRICE10-T010 | Yes | Pass | `test_price10_t010_tax_included_price_is_not_compared` |
| PRICE10-T011 | Yes | Pass | `test_price10_t011_no_unapproved_tolerance_suppresses_a_difference`. `1149.99` stays below. |
| PRICE10-T012 | Yes | Pass | `test_price10_t012_overpricing_is_not_positive_leakage` |
| PRICE10-T013 | Yes | Pass | `test_price10_t013_note_line_is_not_a_contract_sale` |
| PRICE10-T014 | Yes | Pass | `test_price10_t014_missing_contract_is_not_an_invented_price` |
| PRICE10-T015 | Yes | Pass | `test_price10_t015_two_approved_contracts_conflict` |
| CONF10-T001 | Yes | Pass | `test_conf10_t001_compliant_order_confirms` |
| CONF10-T002 | Yes | Pass | `test_conf10_t002_block_mode_rejects_underpricing` |
| CONF10-T003 | Yes | Pass | `test_conf10_t003_warning_mode_allows_confirmation_without_an_override` |
| CONF10-T004 | Yes | Pass | `test_conf10_t004_pending_approval_blocks_when_approval_is_required` |
| CONF10-T005 | Yes | Pass | `test_conf10_t005_valid_override_permits_confirmation` |
| CONF10-T006 | Yes | Pass | `test_conf10_t006_rejected_override_does_not_authorize` |
| CONF10-T007 | Yes | Pass | `test_conf10_t007_expired_override_does_not_authorize` |
| CONF10-T008 | Yes | Pass | `test_conf10_t008_changed_price_invalidates_the_override` |
| CONF10-T009 | Yes | Pass | `test_conf10_t009_changed_quantity_is_not_covered` |
| CONF10-T010 | Yes | Pass | `test_conf10_t010_changed_product_invalidates_the_override` |
| CONF10-T011 | Yes | Pass | `test_conf10_t011_changed_customer_invalidates_the_override` |
| CONF10-T012 | Yes | Pass | `test_conf10_t012_changed_currency_is_not_compared_raw` |
| CONF10-T013 | Yes | Pass | `test_conf10_t013_direct_call_enforces_the_gate` |
| CONF10-T014 | Yes | Pass | `test_conf10_t014_batch_confirmation_does_not_confirm_a_blocked_order` |
| CONF10-T015 | Yes | Pass | `test_conf10_t015_failed_confirmation_stores_no_price_lock` |
| CONF10-T016 | Yes | Pass | `test_conf10_t016_standard_confirmation_still_reaches_sale` |
| HIS10-T001 | Yes | Pass | `test_his10_t001_through_t007_confirmed_order_stores_the_pricing_basis` |
| HIS10-T002 | Yes | Pass | Same method. Version id stored. |
| HIS10-T003 | Yes | Pass | Same method. Confirmation timestamp stored. |
| HIS10-T004 | Yes | Pass | Same method. `order_confirmation` snapshot and lock candidate. |
| HIS10-T005 | Yes | Pass | Same method. Tier id stored. |
| HIS10-T006 | Yes | Pass | Same method. `NO_ADDITIONAL_DISCOUNT` stored. |
| HIS10-T007 | Yes | Pass | Same method. Financial status `SAME_CURRENCY_NO_CONVERSION`. |
| HIS10-T008 | Yes | Pass | `test_his10_t008_later_contract_price_does_not_rewrite_the_lock` |
| HIS10-T009 | Yes | Pass | `test_his10_t009_invoice_date_policy_does_not_lock_the_order_date` |
| HIS10-T010 | Yes | Pass | `test_his10_t010_amendment_keeps_the_original_evidence` |
| HIS10-T011 | Yes | Pass | `test_his10_t011_repeated_confirmation_does_not_duplicate_the_lock` |
| HIS10-T012 | Yes | Pass | `test_his10_t012_snapshot_can_be_read_for_a_later_comparison` |
| APP10-T001 | Yes | Pass | `test_app10_t001_request_is_linked_to_the_exact_line` |
| APP10-T002 | Yes | Pass | `test_app10_t002_requester_cannot_self_approve` |
| APP10-T003 | Yes | Pass | `test_app10_t003_and_t007_approver_authority_and_other_order` |
| APP10-T004 | Yes | Pass | `test_app10_t004_amount_limit_is_enforced` |
| APP10-T005 | Yes | Pass | `test_app10_t005_and_t006_company_customer_and_product_scope` |
| APP10-T006 | Yes | Pass | Same method as T005. |
| APP10-T007 | Yes | Pass | Same method as T003. Other order is refused. |
| APP10-T008 | Yes | Pass | `test_app10_t008_lower_price_than_the_override_is_not_authorized` |
| APP10-T009 | Yes | Pass | `test_app10_t009_quantity_scope_is_enforced` |
| APP10-T010 | Yes | Pass | `test_app10_t010_effective_period_is_enforced` |
| SEC10-T001 | Yes | Pass | `test_sec10_t001_and_t010_company_boundary` |
| SEC10-T002 | Yes | Pass | `test_sec10_t002_company_b_override_cannot_authorize_company_a` |
| SEC10-T003 | Yes | Pass | `test_sec10_t003_restricted_user_does_not_receive_the_baseline` |
| SEC10-T004 | Yes | Pass | `test_sec10_t004_rpc_cannot_skip_the_server_gate` |
| SEC10-T005 | Yes | Pass | `test_sec10_t005_price_lock_mutation_is_denied` |
| SEC10-T006 | Yes | Pass | `test_sec10_t006_and_t007_and_t008_separation_of_duties` |
| SEC10-T007 | Yes | Pass | Same method. Application Administrator has no commercial approval row. |
| SEC10-T008 | Yes | Pass | Same method. Combined groups do not self-approve. |
| SEC10-T009 | Yes | Pass | `test_sec10_t009_export_of_pricing_evidence_is_restricted` |
| SEC10-T010 | Yes | Pass | Same method as T001. |
| CON10-T001 | Partial | Sequential pass only | `test_con10_t001_second_store_returns_the_same_lock`. Two database sessions were not run. `TransactionCase` cannot commit. |
| CON10-T002 | Yes | Pass | `test_con10_t002_price_change_after_approval_is_rechecked` |
| CON10-T003 | Yes | Pass | `test_con10_t003_repeated_evaluation_creates_no_exposure_rows` |
| CON10-T004 | Yes | Pass | `test_con10_t004_failure_does_not_leave_confirmation_evidence` |
| CON10-T005 | Yes | Pass | `test_con10_t005_confirmation_reads_the_current_price` |
| REG10-T001 | Yes | Pass | Fresh `-i` then `-u` of `cpla_dev10_fresh_20261028`. Final log `cpla_dev10_fresh2.log`, 0 failed of 676. |
| REG10-T002 | Yes | Pass | `-u` of `cpla_dev09_20261028`. Log `cpla_dev10_upgrade.log`, 0 failed of 676. |
| REG10-T003 | Yes | Pass | Prior contract tests inside the 676. |
| REG10-T004 | Yes | Pass | Prior version tests inside the 676. |
| REG10-T005 | Yes | Pass | Prior quantity and UoM tests inside the 676. |
| REG10-T006 | Yes | Pass | Prior FX and tax tests inside the 676. |
| REG10-T007 | Yes | Pass | Prior discount tests inside the 676. |
| REG10-T008 | Yes | Pass | `test_reg10_installation_views_and_no_recovery_documents` and standard sale creation inside the class. |
| REG10-T009 | Yes | Pass | `test_conf10_t016_standard_confirmation_still_reaches_sale` |
| REG10-T010 | Yes | Pass | Same installation test. Sales form contains Recheck Compliance and Contract Compliance. |
| REG10-T011 | Yes | Pass | `test_sec_t007_no_public_portal_or_unrestricted_acl` on the fresh rerun. |
| REG10-T012 | Yes | Pass | Prior-phase tests are included in the 676. |
| REG10-T013 | Yes | Pass | Installation test asserts no `account.move` data from this module. Confirmation test asserts the move count does not change. |
| REG10-T014 | Yes | Pass | Installation test asserts no recovery or waiver model. |

Invoice-audit, leakage-finding, finance-validation, recovery, and waiver tests are deferred. They were not executed and are not passed.

A two-worker confirmation was not executed. No queries-per-second figure was measured. Odoo 18 and Odoo 20 were not tested.
