# Golden finance scenarios

The company currency is whatever `generic_coa` loaded for the test company. The figures below are the decimal texts the tests asserted. They are not a statement that the company currency is INR. Ceilings and the rate `2` are test fixtures, not seeded policy.

Executed in `TestDev12InvoiceAudit` on 2026-11-05. Result line: `0 failed, 0 error(s) of 14 tests` in `local_testing/cpla_dev15_targeted7.log`.

| ID | Expected | Actual method | Result |
| --- | --- | --- | --- |
| GOLD-FV-001 | Validate `25000` of `25000` | `test_fv15_full_then_partial_correction` | Passed. Finding potential stayed `25000`. |
| GOLD-FV-002 | Later correction validates `18000` and rejects `7000` | same method | Passed. Old row stays `25000` and `superseded`. Current total `18000`, not `43000`. `is_waiver` false. |
| GOLD-FV-003 | `18000` / `2000` / `5000` | `test_fv15_unresolved_portion_stays_unresolved` | Passed. Unresolved stayed unresolved. |
| GOLD-FV-004 | Validate `0`, reject `25000` | `test_fv15_full_rejection_is_not_a_waiver` | Passed. Not a waiver. Finding potential stayed `25000`. |
| GOLD-FV-005 | Proposed `30000` refused | `test_fv15_full_then_partial_correction` | Passed. `VALIDATION_EXCEEDS_POTENTIAL`. |
| GOLD-FV-006 | Three findings `10000`, `8000` of `10000`, and `0` of `5000` | `test_fv15_many_findings_reconcile` | Passed. Totals `18000` / `2000` / `5000`. |
| GOLD-FV-007 | Three audit runs, one current validation | `test_fv15_repeated_audits_validate_once` | Passed. |
| GOLD-FV-008 | Basis falls from `25000` to `20000` before approval | `test_fv15_stale_before_approval_uses_the_new_basis` | Passed. Old package retired. New approval is `20000`. |
| GOLD-FV-009 | Approved `25000` kept after a later return | `test_fv15_stale_after_approval_keeps_history` | Passed. `current` false. No second accounting document from the finance hook. |
| GOLD-FV-010 | Discount claim without an approved discount | `test_fv15_discount_evidence_and_reassessment_block` | Passed. `APPROVAL_EVIDENCE_MISSING`. |
| GOLD-FV-011 | Incomplete package is not approved | same method, `action_request_evidence` | Passed. Case returned for rework. No final amount. |
| GOLD-FV-012 | Finance manager inside the company and ceiling | full-validation path | Passed. |
| GOLD-FV-013 | User without finance authority | same method | Passed. Superuser and app admin get `APPROVAL_MATRIX_MISSING`. |
| GOLD-FV-014 | Submitter cannot approve | `test_fv15_full_rejection_is_not_a_waiver` and `test_fv15_two_levels_and_self_approval` | Passed. `SELF_APPROVAL_PROHIBITED`. |
| GOLD-FV-015 | Two levels | `test_fv15_two_levels_and_self_approval` | Passed. After level 1, validated stays `0`. |
| GOLD-FV-016 | Company B cannot approve Company A | full-validation path | Passed. Record rule `AccessError`. Search is empty. |
| GOLD-FV-017 | No raw cross-currency sum | `test_fv15_currency_ceiling_and_missing_matrix` | Passed for a tampered line currency and for a policy currency that needs a recorded rate. A real two-invoice case in two currencies is not what this test created. Case grouping already refuses mixed currencies. |
| GOLD-FV-018 | Accepted basis `4000` after a return, not `5000` and not `3000` | `test_fv15_refund_uses_accepted_basis` | Passed. Original result row stays `5000`. |
| GOLD-FV-019 | One approval when the action is repeated | full-validation idempotent approve, and `test_fv15_concurrent_approval_keeps_one_decision` | Passed. The concurrent method used two threads. |
| GOLD-FV-020 | No waiver, bill, or cash | full-validation payload flags and unchanged payment count | Passed. |

`test_fv15_level_denial_records_no_amount` recorded a denied level with validated `0` and no waiver. A second prepare while that decision is current raises `DUPLICATE_VALIDATION_REQUEST`.
