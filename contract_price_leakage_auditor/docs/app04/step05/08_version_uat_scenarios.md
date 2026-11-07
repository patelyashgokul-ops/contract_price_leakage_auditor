# 08 — Version UAT scenarios

Date: 2026-10-28.

The narrative dates in the prompt (January, June, July, August 2026) are examples. The automated cases use dates relative to the database context date, because a fixed June or July 2026 date is retroactive when that context date is later. Currency amounts use the company currency. The tests do not activate INR, USD, or AED. They do not assert a currency name.

Execution evidence is in `09_automated_test_results.md`. This file records the expected business result. It is not a sign-off.

| ID | Setup | Expected |
| --- | --- | --- |
| CONTRACT-V001 | XYZ Manufacturing, Bearing A, unit price 1000, effective from a past valid-from inside the contract. Manager approves the ready header. | Version V1 is approved with one line. Approver and timestamp are stored. Header stays ready for review. Ordinary save does not approve. List price is not the contract price. |
| CONTRACT-V002 | V1 at 1000. V2 at 1200, approved now, effective later. | Both rows remain. V2 is scheduled. V1 stays the earlier authority. A supersession event exists. No invoice model is written. |
| CONTRACT-V003 | V1 Bearing A 1000 and Bearing B 1500. V2 changes only Bearing A to 1200. | Both snapshots keep their products. Comparison: Bearing A Price Increased by 200. Bearing B No Change. The delta is not recovered cash. V1 lines stay 1000 and 1500. |
| CONTRACT-V004 | Draft proposes 900 and is rejected with a reason. | State is rejected. No supersession. V1 stays authoritative. |
| CONTRACT-V005 | Contract User submits and calls approve. | AccessError. State stays ready for review. No supersession. |
| CONTRACT-V006 | V2 approved now with a later effective date. | State approved. Effective status scheduled. Effective date is after today. |
| CONTRACT-V007 | Amendment effective yesterday. | Approval raises. Policy constant stays `not_authorized`. Reassessment is required. V1 price and state stay. No invoice recalculation. |
| CONTRACT-V008 | Two authorized users approve the same ready amendment in two transactions. | One approved row, one approval event, one supersession event. The other outcome is success, `LockError`, or a stale/already-approved refusal. |
| CONTRACT-V009 | Draft V3 is based on V1. V2 is approved first. | Approve of V3 raises. V3 is not approved. |
| CONTRACT-V010 | Company A manager approves Company B's ready contract through the Company A environment. | AccessError. No approved version on that contract. |

## Automated map

| Business id | Test method |
| --- | --- |
| CONTRACT-V001 | `test_contract_v001_draft_save_does_not_approve` and `test_ver_t001_initial_version_from_ready_contract` |
| CONTRACT-V002 | `test_contract_v002_prospective_increase_keeps_both_versions` |
| CONTRACT-V003 | `test_contract_v003_multiple_products_comparison` |
| CONTRACT-V004 | `test_contract_v004_rejected_amendment` |
| CONTRACT-V005 | `test_contract_v005_contract_user_cannot_approve` |
| CONTRACT-V006 | `test_contract_v006_future_dated_version_is_not_effective_early` |
| CONTRACT-V007 | `test_contract_v007_retroactive_amendment_is_blocked` |
| CONTRACT-V008 | `test_contract_v008_and_con05_concurrent_approval` |
| CONTRACT-V009 | `test_contract_v009_stale_source_blocks_automatic_supersession` |
| CONTRACT-V010 | `test_contract_v010_cross_company_approval_is_denied` |

## Golden fixtures that are not financial tests

| ID | What DEV-05 stores | What it does not do |
| --- | --- | --- |
| GOLD-FIN-001 | Not calculated here. The approved historical price source is the version line. | Does not compute 500 × (1150 − 1100) = 25000. Does not mark a leakage test passed. |
| GOLD-FIN-002 | V1 1000 and V2 1200, with `pricing_date_policy_snapshot` `order_confirmation` when that candidate was on the policy. | Does not apply grandfathering to a June order. Does not treat the summary as cash. |
| GOLD-REC-001 | Not implemented. | Waiver, recovery target, verified cash, and outstanding are not calculated and are not marked passed. |

Customer names in the unit tests are XYZ Manufacturing and UAE Buyer. Companies are ABC India and ABC UAE for the isolation cases. Concurrent cases use separate company names so they do not share the ABC India rows.
