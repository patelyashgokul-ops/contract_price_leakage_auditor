# Root causes and outcomes

The detector category on the finding is not the investigator's root cause. `create_from_findings` does not copy it into `root_cause`. Recording a root cause requires `action_record_root_cause` with a category and an explanation. The owner or a contract manager may record it while the case is open.

## Root-cause categories

`missed_contract_price_increase`, `unauthorized_manual_discount`, `incorrect_sales_order_price`, `invoice_price_changed_after_order`, `wrong_contract_version`, `wrong_pricing_date`, `invalid_grandfathering`, `wrong_quantity_tier`, `uom_or_packaging_error`, `fx_rate_policy_error`, `tax_basis_error`, `approval_evidence_missing`, `contract_coverage_gap`, `credit_or_reversal_mapping_error`, `master_data_error`, `other`, `undetermined`.

None of these labels say fraud. `unauthorized_manual_discount` is a pricing classification, not a misconduct finding.

## Outcomes

`likely_unauthorized_underpricing`, `likely_missed_price_increase`, `possible_authorized_concession`, `contract_interpretation_dispute`, `duplicate_finding`, `source_mapping_error`, `needs_additional_evidence`, `not_applicable_to_contract_audit`, `ready_for_finance_review`, `undetermined`.

`action_record_outcome` stores the selection and an event. If `investigation_summary` is empty, the explanation is copied there as a note. The note does not replace `potential_leakage_exact` on the finding or the case exposure.

An outcome of `not_applicable_to_contract_audit` does not write off an invoice, create a waiver, or close the case. Closure is a separate manager action with its own reason.

`ready_for_finance_review` as an outcome is the investigator's statement that the package is ready. The state changes to `ready_for_finance_review` only in `action_submit_for_finance`, after the checklist and evidence gates.

Both actions are refused when the case is in finance review or closed (`_check_open_for_edit`).
