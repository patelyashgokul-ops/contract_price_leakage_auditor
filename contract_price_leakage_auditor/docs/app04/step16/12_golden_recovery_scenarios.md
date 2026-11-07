# Golden recovery scenarios

Amounts are decimal texts in the company currency of the fixture. The company currency is not renamed to INR. Each scenario below is asserted inside a `test_rec16_*` method. Those methods passed on 2026-11-05 in `local_testing/dev16_targeted_2.log` (13 tests), `local_testing/dev16_full_1.log` (941 tests), and `local_testing/dev16_upgrade_1.log` (941 tests).

| ID | Expected | Where it passed |
| --- | --- | --- |
| GOLD-REC16-001 | Validated 25000, waiver 0, target 25000, billed 0, collected 0 | `test_rec16_full_recovery_and_partial_waiver` |
| GOLD-REC16-002 | 25000 = 5000 waiver + 20000 target | `test_rec16_partial_waiver_reconciliation` |
| GOLD-REC16-003 | 25000 = 5000 + 12000 + 8000 unallocated | `test_rec16_undecided_and_unapproved_waiver` |
| GOLD-REC16-004 | Dispute 8000 stays inside target 20000 | `test_rec16_dispute_acknowledgement_silence` |
| GOLD-REC16-005 | Waivers 8000 and revised target 17000. Original 5000 waiver remains | `test_rec16_settlement_counteroffer_and_extra_waiver` |
| GOLD-REC16-006 | Draft waiver does not reduce the target | `test_rec16_undecided_and_unapproved_waiver` |
| GOLD-REC16-007 | Unallocated 5000 rejects a new waiver of 8000 | `test_rec16_excess_waiver_and_duplicate_and_partial_split` after the approved target is withdrawn |
| GOLD-REC16-008 | Two current 10000 allocations of one 10000 line are refused | Same method, before withdrawal |
| GOLD-REC16-009 | 12000 and 8000 on one 20000 line both approve | `test_rec16_nonoverlapping_partial_requests` |
| GOLD-REC16-010 | Finance-validated 18000 can be allocated. Rejected 7000 is not a waiver | `test_rec16_finance_rejection_not_waiver` |
| GOLD-REC16-011 | Stale finance source blocks a new approval. Historical target remains | `test_rec16_stale_blocks_new_approval` |
| GOLD-REC16-012 | Company B cannot allocate Company A | `test_rec16_wrong_company_and_security` |
| GOLD-REC16-013 | Counteroffer 15000 does not change the target | `test_rec16_settlement_counteroffer_and_extra_waiver` |
| GOLD-REC16-014 | Acknowledgement 12000 is not collected cash | `test_rec16_dispute_acknowledgement_silence` |
| GOLD-REC16-015 | Discussion without a response is not acceptance | Same method |
| GOLD-REC16-016 | Internal settlement approval is not customer acceptance | `test_rec16_settlement_counteroffer_and_extra_waiver` |
| GOLD-REC16-017 | Accepted settlement can be handed off. No invoice or cash is created | Same method. Handoff status `READY_FOR_ACCOUNTING`, authorized amount 17000, billed and collected 0 |
| GOLD-REC16-018 | Two workers cannot approve the same 5000 waiver twice | `test_rec16_concurrent_waiver_allocation` |
| GOLD-REC16-019 | Repeating handoff keeps one key | `test_rec16_full_recovery_and_partial_waiver` |
| GOLD-REC16-020 | Validated, waiver, target, dispute, acknowledgement, billed, and collected stay distinct | Dispute method plus billed and collected assertions on the approved requests |

The first targeted log, `local_testing/dev16_targeted_1.log`, is not a pass. It was 1 failed and 3 errors of 11 tests. The three errors were a second sale inside one test, which reopened a case already submitted to finance. The failure was a cross-company prepare that raised `AccessError` without the code `RECOVERY_SOURCE_NOT_READY`. The rerun split those sales and expects the access error.
