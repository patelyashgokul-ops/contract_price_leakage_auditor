# Golden reassessment fixtures

Date: 2026-11-05. Amounts are company-currency decimal texts. The tests do not assert the currency name INR.

The full tag on `cpla_dev14_20261105` in `cpla_dev14_full3.log` finished at 2026-11-05 07:37:40. Result: `0 failed, 0 error(s) of 914 tests`. `914 post-tests in 1142.10s, 282679 queries`. Shell exit 0. That run includes `test_rev14_t001` through `test_rev14_t016`. The stats line counts 940 tests; the post-install result line is 914.

| ID | Expected | Where it is tested |
| --- | --- | --- |
| GOLD-REA-001 | Original 5000 kept. Return of 20 proposes 4000. Delta -1000. Not cash. | `test_rev14_t001`. Passed in `cpla_dev14_gap2.log` on 2026-11-05. |
| GOLD-REA-002 | Full reversal proposes 0. Original result stays 5000. No current potential finding after accept. | `test_rev14_t007`. Passed in the pre-37 class log. Included again in the release-gate rerun. |
| GOLD-REA-003 | Replacement without a verified reversal is not forced to zero. With a verified reversal, the engine does not keep both as current loss. | `test_rev14_t010` and DEV-12 `test_ref12_t005`. |
| GOLD-REA-004 | Retroactive 1200 on quantity 100 proposes 20000 on the current cutoff. The earlier cutoff stays a separate identity. | `test_rev14_t008`. |
| GOLD-REA-005 | A visible approved discount is priced by the DEV-12 evaluator. DEV-14 does not invent the zero. | No dedicated reassessment test forces the zero. The invalid path is t015. Valid path is NOT a separate executed GOLD assertion in DEV-14. |
| GOLD-REA-006 | Missing authority stays in review. The previous price is not replaced. | `test_rev14_t015`. Passed in `cpla_dev14_gap2.log`. |
| GOLD-REA-007 | Corrected source mapping keeps the original evidence and prices the corrected source. | DEV-12 source tests and trigger `invoice_source_mapping_correction`. No new DEV-14 method name beyond the engine reuse. |
| GOLD-REA-008 | Missing FX or tax evidence does not fabricate an amount. Accept raises. | `test_rev14_t015`. Passed in `cpla_dev14_gap2.log`. |
| GOLD-REA-009 | Amount-only credit does not change eligible quantity. | `test_rev14_t006`. |
| GOLD-REA-010 | The same source event does not create three active requests or three adjustments. | Open unique index. `test_ref12_t013` and `test_idm12_t012` cover repeated refund processing. |
| GOLD-REA-011 | Reject 3000-style proposal. Current stays 5000. Reason and reviewer stay. Verification is `source_changed_review_pending`. Root cause stays. | `test_rev14_t012` uses a 4000 proposal rejected for insufficient evidence. Passed in `cpla_dev14_gap2.log`. The 3000 figure in the prompt is the same rule. The executed proposal is 4000. |
| GOLD-REA-012 | Accepted current 4000. Historical 5000. Not 9000. | `test_rev14_t001`. Passed in `cpla_dev14_gap2.log`. |
| GOLD-REA-013 | Two proposals, one current finding, exposure not 9000. | `test_rev14_t016`, two threads. Passed in `cpla_dev14_gap2.log`. The log records `could not serialize access due to concurrent update` on the finding supersede. |
| GOLD-REA-014 | Case records the source revision. Reviewed amount and root cause stay until the investigator accepts the new source. | `test_rev14_t003` and `test_rev14_t012`. |
| GOLD-REA-015 | Submitted finance package stays. `finance_package_stale` is set. No finance validation. | `test_rev14_t004`. |
| GOLD-REA-016 | Company A cannot use Company B's version. | `test_rev14_t014`. Passed in `cpla_dev14_gap2.log`. |
| GOLD-REA-017 | Same fingerprint does not add a finding. | `test_rev14_t013`. Passed in `cpla_dev14_gap2.log`. |
| GOLD-REA-018 | Tampered payload does not accept. | `test_rev14_t002`. |
| GOLD-REA-019 | Incomplete evidence cannot be accepted. | `test_rev14_t015` for discount, FX, and tax. Digest and evidence gaps block other incomplete proposals. |
| GOLD-REA-020 | Potential can change. Finance-validated, approved recovery, and collected cash fields are not created. | `test_gold_aud_020` and the reassessment alerts. `is_recovered_cash` stays false. |

`test_rev14_t011` checks the form contains `original_quantity_exact`, the finding form contains `revision_verification` and "not a fresh verification", the case form contains `reinvestigation_required`, and the finding search contains `filter_source_review`. It also checks that `action_reassess` is still on the run form.
