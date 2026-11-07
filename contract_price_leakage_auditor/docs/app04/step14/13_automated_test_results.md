# Automated test results

Date: 2026-11-05. Odoo 19.0. Addon `contract_price_leakage_auditor` `19.0.1.12.0`. Amounts are company-currency decimal texts.

A suggested ID that has no method of its own is `NOT_EXECUTED` as that ID. A related `test_rev14_*` method is named only when that method asserts the same outcome. The 914-test runs below include `test_rev14_t001` through `test_rev14_t016`.

## Executed commands

| Log | Database | Command | Result |
| --- | --- | --- | --- |
| `cpla_dev14_gap2.log` | `cpla_dev14_20261105` | Six methods: t001, t012, t013, t014, t015, t016. No `-u`. Port 8093. PID 22492. | 2026-11-05 06:59:45. `0 failed, 0 error(s) of 6 tests`. `6 post-tests in 26.42s, 12281 queries`. Shell exit 0. |
| `cpla_dev14_full3.log` | `cpla_dev14_20261105` | `-u contract_price_leakage_auditor --test-tags=/contract_price_leakage_auditor`. Port 8093. PID 23288. | 2026-11-05 07:37:40. `0 failed, 0 error(s) of 914 tests`. `914 post-tests in 1142.10s, 282679 queries`. Stats line: 940 tests. Shell exit 0. |
| `cpla_dev14_upgrade3.log` | `cpla_dev13_fresh_20261105` | `-u` from installed `19.0.1.11.0`. Same addon tag. Port 8094. PID 12488. | 2026-11-05 07:56:41. `0 failed, 0 error(s) of 914 tests`. `914 post-tests in 1003.76s, 282511 queries`. Stats line: 940 tests. After the run the module row is `19.0.1.12.0` / `installed`. Shell exit 0. |
| `cpla_dev14_fresh2.log` | `cpla_dev14b_fresh_20261105` | `-i contract_price_leakage_auditor`. Same addon tag. Port 8095. PID 7420. | 2026-11-05 08:10:04. `0 failed, 0 error(s) of 914 tests`. `914 post-tests in 537.29s, 282519 queries`. Stats line: 940 tests. Shell exit 0. |

`cpla_dev14_full2.log` and `cpla_dev14_upgrade2.log` were stopped after leftover concurrency-pool rows failed later absolute-zero counts. They have no final pass line. They are not results.

`cpla_dev14_rev14.log` is `0 failed, 0 error(s) of 0 tests`. It is not a pass.

`cpla_dev14_gap.log` is `0 failed, 1 error of 6 tests` (`test_rev14_t016`, `A company is required.`). The fixture was then committed before the workers ran. That log is not a pass.

Pre-37 logs `cpla_dev14_class2.log`, `cpla_dev14_full.log`, `cpla_dev14_upgrade.log`, and `cpla_dev14_fresh.log` are each `0 failed, 0 error(s) of 111 or 909 tests`. They do not cover sections 37–69. The 909 figure is historical. The current post-install count is 914.

Logged `duplicate key` and `could not serialize access due to concurrent update` lines in gap2, full3, and upgrade3 are the tests hitting a uniqueness or concurrency conflict. The result lines stayed `0 failed, 0 error(s)`.

## REV14 methods

| Method | In the 914-test runs | Result |
| --- | --- | --- |
| `test_rev14_t001` through `test_rev14_t016` | Yes, full3 and upgrade3 | PASS |

t016 is two threads, a barrier, and separate cursors. It is the concurrency evidence. The winning amount is not in the log.

## Suggested IDs

| Test ID | Executed | Result | Evidence |
| --- | --- | --- | --- |
| SNP14-T001 | Yes | PASS | t001 creates the request and records schema `dev14.2`. |
| SNP14-T002 | Yes | PASS | t001 keeps the original result at 5000 after acceptance. |
| SNP14-T003 | No | NOT_EXECUTED | No assertion that the stored original version id is unchanged. |
| SNP14-T004 | Yes | PASS | t008 keeps a separate cutoff from the later cutoff. |
| SNP14-T005 | Yes | PASS | t013 does not add a finding when the fingerprint is unchanged. |
| SNP14-T006 | Yes | PASS | t001 asserts `schema_version == dev14.2`. |
| SNP14-T007 | No | NOT_EXECUTED | t001 rejects a direct write of `proposed_exposure_exact`. That is not a write of the original audit result. |
| SNP14-T008 | No | NOT_EXECUTED | No child-row mutation test. |
| SNP14-T009 | Yes | PASS | t001 reads the original 5000 result and the superseded 5000 finding after acceptance. |
| SNP14-T010 | No | NOT_EXECUTED | t001 stores a digest. It does not call digest verification. |
| SNP14-T011 | Yes | PASS | t002 blocks acceptance after the payload is tampered. |
| SNP14-T012 | Yes | PASS | t015 leaves FX and tax corrections in review and does not invent an amount. |
| SRC14-T001 | No | NOT_EXECUTED | No reassessment test that a contract amendment alone opens a request. `affected_findings` is explicit. |
| SRC14-T002 | No | NOT_EXECUTED | No non-material contract-note test. |
| SRC14-T003 | Yes | PASS | t015: an unapproved discount correction stays in review. |
| SRC14-T004 | Yes | PASS | t015: historical FX correction does not fabricate a rate. |
| SRC14-T005 | No | NOT_EXECUTED | No dedicated mapping-correction reassessment assertion. |
| SRC14-T006 | Yes | PASS | t001 detects the posted 20-piece return and proposes 4000. |
| SRC14-T007 | Yes | PASS | t007 proposes 0 for a verified full reversal. |
| SRC14-T008 | Yes | PASS | t010 does not force zero when the replacement has no verified reversal. |
| SRC14-T009 | Yes | PASS | t001 calls the same source twice and reuses one open request. |
| SRC14-T010 | Yes | PASS | t014 selects only the calling company's current findings. |
| SRC14-T011 | Yes | PASS | t014 raises when the version belongs to the other company. |
| SRC14-T012 | Yes | PASS | t013: same fingerprint, finding count unchanged. |
| FIN14-T001 | Yes | PASS | t001 original result stays 5000. |
| FIN14-T002 | Yes | PASS | t001 proposed exposure 4000, quantity 80. |
| FIN14-T003 | Yes | PASS | t001 delta `-1000`. |
| FIN14-T004 | Yes | PASS | t007 proposed 0, and no current potential finding after accept. |
| FIN14-T005 | Yes | PASS | t010 does not count an unverified replacement as a second current loss. A verified pair is not a separate zero assertion in this method. |
| FIN14-T006 | Yes | PASS | t008 current cutoff exposure stays 20000 and is not added to the earlier cutoff. |
| FIN14-T007 | No | NOT_EXECUTED | No test that a valid retroactive discount proposes zero. |
| FIN14-T008 | Yes | PASS | t015: discount without a visible approval stays in review. Accept raises. |
| FIN14-T009 | Yes | PASS | t006 does not treat an amount-only credit as a quantity return. |
| FIN14-T010 | Yes | PASS | t015 does not invent a replacement FX rate. |
| FIN14-T011 | No | NOT_EXECUTED | No new tier assertion inside a reassessment. DEV-12 tier tests ran inside the 914 suite. |
| FIN14-T012 | Yes | PASS | t015 does not invent a tax correction. |
| FIN14-T013 | No | NOT_EXECUTED | No separate currency-rounding reassessment assertion. |
| FIN14-T014 | No | NOT_EXECUTED | No separate tolerance assertion on a revision. |
| FIN14-T015 | Yes | PASS | t001 exposure after accept is 4000, not 9000. |
| FIN14-T016 | Yes | PASS | t001 `is_recovered_cash` stays false. Payment count is unchanged. |
| FIN14-T017 | Yes | PASS | t001 posted line price and quantity are unchanged. Move count is unchanged. |
| HIS14-T001 | No | NOT_EXECUTED | No new commercial-date versus approval-date assertion beyond DEV-12. `test_his12_*` ran in the 914 suite. |
| HIS14-T002 | Yes | PASS | t008: the July cutoff does not take the later approval. |
| HIS14-T003 | Yes | PASS | t008: the later cutoff keeps the 20000 current finding. |
| HIS14-T004 | Yes | PASS | t001 original result remains 5000. |
| HIS14-T005 | Yes | PASS | t008 keeps both cutoff identities. The earlier one is not subtracted from 20000. |
| HIS14-T006 | No | NOT_EXECUTED | No revoked-discount history assertion in a reassessment. |
| HIS14-T007 | No | NOT_EXECUTED | No supersession-chain assertion beyond the separate cutoff. |
| HIS14-T008 | Yes | PASS | t008: the two cutoffs are different identities. |
| HIS14-T009 | No | NOT_EXECUTED | No test that a missing approval time stays blank. |
| HIS14-T010 | No | NOT_EXECUTED | No test that a later policy write rewrites an older result. |
| WF14-T001 | Yes | PASS | t001 manager request is stored as `requested`. |
| WF14-T002 | No | NOT_EXECUTED | No reassessment test for a user without the manager group. |
| WF14-T003 | Yes | PASS | t001 stores the trigger and the request reason. |
| WF14-T004 | Yes | PASS | t001 evaluate moves the request to `proposed_revision_ready`. |
| WF14-T005 | Yes | PASS | t001 the current finding stays 5000 until accept. |
| WF14-T006 | Yes | PASS | t015 accept of `evidence_review_required` raises. |
| WF14-T007 | Yes | PASS | t001 finance manager accept sets state `accepted` and current exposure 4000. |
| WF14-T008 | Yes | PASS | t001 contract manager accept raises `AccessError`. t009 reviewer cannot accept. |
| WF14-T009 | Yes | PASS | t005 the requester cannot accept, including when that user also has the finance-manager group. |
| WF14-T010 | Yes | PASS | t012 rejection keeps the proposal, the reason, and the previous 5000 current amount. |
| WF14-T011 | No | NOT_EXECUTED | No test that a calculation exception stays `failed`. |
| WF14-T012 | No | NOT_EXECUTED | No test that a source change during review invalidates the proposal. |
| WF14-T013 | Yes | PASS | t001 accept leaves one current finding at 4000. |
| WF14-T014 | Yes | PASS | t001 superseded finding and original result stay 5000. |
| WF14-T015 | Yes | PASS | t001 a second request for the same open source returns the same record. Repeated accept of an already accepted row is not a separate assertion. |
| WF14-T016 | Yes | PASS | t001 stores `decision_by_id`. t012 stores the rejection reason. |
| CASE14-T001 | Yes | PASS | t003 finds the open case for the finding. |
| CASE14-T002 | Yes | PASS | t003 records the source revision change on the case. |
| CASE14-T003 | Yes | PASS | t003 reviewed exposure stays 5000 until the investigator accepts the new source. |
| CASE14-T004 | Yes | PASS | t012 sets `reinvestigation_required` and does not change root cause. |
| CASE14-T005 | Yes | PASS | t003 the investigator can retarget onto the accepted 4000 finding. The flag then clears. |
| CASE14-T006 | Yes | PASS | t001 one current finding. t008 the other cutoff is not added. |
| CASE14-T007 | Yes | PASS | t004 the submission snapshot remains after the source change. |
| CASE14-T008 | Yes | PASS | t004 sets `finance_package_stale`. |
| CASE14-T009 | Yes | PASS | t012 root cause and explanation stay. |
| CASE14-T010 | Yes | PASS | t004 does not create a finance-validated amount. The package is flagged, not approved. |
| CASE14-T011 | Yes | PASS | t001 creates no payment. No recovery model is written. |
| CASE14-T012 | No | NOT_EXECUTED | No test that case synchronization across companies is rejected. t014 rejects cross-company finding selection. |
| SEC14-T001 | Yes | PASS | t001 company B cannot read the company A reassessment. |
| SEC14-T002 | Yes | PASS | t001 company B `read` raises `AccessError`. |
| SEC14-T003 | Yes | PASS | t014 cross-company version selection raises. |
| SEC14-T004 | No | NOT_EXECUTED | Direct write of the original audit result is not asserted. t001 rejects a write of the proposal amount. |
| SEC14-T005 | Yes | PASS | t001 manager cannot accept. t009 reviewer cannot accept. |
| SEC14-T006 | Yes | PASS | t001 `action_accept` checks the group and raises for the manager. |
| SEC14-T007 | Yes | PASS | t005 self-approval raises. |
| SEC14-T008 | No | NOT_EXECUTED | No attachment-download denial test on a reassessment. |
| SEC14-T009 | No | NOT_EXECUTED | No comparison test that another company's rate is hidden. Company B cannot read the reassessment in t001. |
| SEC14-T010 | No | NOT_EXECUTED | No auditor read-only assertion on the reassessment models in these methods. Auditor ACLs are in the security foundation tests, which passed inside the 914 suite. |
| SEC14-T011 | No | NOT_EXECUTED | No technical-administrator approval denial inside a reassessment. The security foundation test that the administrator has no commercial groups passed inside the 914 suite. |
| SEC14-T012 | Yes | PASS | t005 a user with both manager and finance-manager groups still cannot accept their own request. |
| SEC14-T013 | No | NOT_EXECUTED | `export_data` refusal is not called by these tests. |
| SEC14-T014 | No | NOT_EXECUTED | No test searches the addon for `sudo(`. Review of the addon found no `sudo(` in product Python. That is a review, not this table's test. |
| CON14-T001 | Yes | PASS | t001 the second call for the same source returns the same open request. This call is sequential. |
| CON14-T002 | Yes | PASS | t001 evaluate does not change the finding count, and accept leaves one current finding. |
| CON14-T003 | Yes | PASS | t016, two threads. full3 and upgrade3 log `could not serialize access due to concurrent update`. At most one current finding. Total is not 9000. |
| CON14-T004 | No | NOT_EXECUTED | No test that a failed accept leaves the previous current row unchanged under a database error. |
| CON14-T005 | No | NOT_EXECUTED | No concurrent source-change test. |
| CON14-T006 | Yes | PASS | t001 one open request for the same credit. The credit is not applied twice. |
| CON14-T007 | No | NOT_EXECUTED | No assertion of revision numbers under concurrency. |
| CON14-T008 | No | NOT_EXECUTED | No digest check after a retry. |
| CON14-T009 | No | NOT_EXECUTED | No second case synchronization asserting the same case event is not duplicated. |
| CON14-T010 | No | NOT_EXECUTED | No partial-transaction failure test. |
| REG14-T001 | Yes | PASS | `cpla_dev14_fresh2.log`. `-i` of `cpla_dev14b_fresh_20261105`. Port 8095. PID 7420. 2026-11-05 08:10:04. `0 failed, 0 error(s) of 914 tests`. `914 post-tests in 537.29s, 282519 queries`. Stats line: 940 tests. Shell exit 0. |
| REG14-T002 | Yes | PASS | upgrade3, `-u` of `cpla_dev13_fresh_20261105` from `19.0.1.11.0` to `19.0.1.12.0`, 0 failed of 914. |
| REG14-T003 | No | NOT_EXECUTED | No before/after count of contract versions that existed before the upgrade. |
| REG14-T004 | No | NOT_EXECUTED | No before/after count of audit results that existed before the upgrade. |
| REG14-T005 | No | NOT_EXECUTED | No before/after count of findings that existed before the upgrade. |
| REG14-T006 | No | NOT_EXECUTED | No before/after count of case history that existed before the upgrade. |
| REG14-T007 | No | NOT_EXECUTED | No before/after count of discount approvals that existed before the upgrade. |
| REG14-T008 | No | NOT_EXECUTED | No before/after count of refund mappings that existed before the upgrade. |
| REG14-T009 | Yes | PASS | full3 and upgrade3 loaded the module and ran the reassessment tests. |
| REG14-T010 | Yes | PASS | Security foundation tests passed inside both 914-test runs. |
| REG14-T011 | Yes | PASS | t011 view checks passed inside both 914-test runs. |
| REG14-T012 | Yes | PASS | DEV-12 tests, including the golden audit methods, passed inside both 914-test runs. Individual expected amounts are not restated here. |
| REG14-T013 | Yes | PASS | DEV-13 case tests passed inside both 914-test runs. |
| REG14-T014 | Yes | PASS | The addon tag is the DEV-01 through DEV-14 suite. Both runs were 0 failed of 914. |
| REG14-T015 | Yes | PASS | t001 posted price, quantity, and move count stay unchanged. |
| REG14-T016 | Yes | PASS | t001 payment count stays unchanged. No recovery document is created. |
| REG14-T017 | Yes | PASS | t001 finds no `ir.cron` data for this module. |

## Not a finance-validation result

These runs do not approve a finance-validated amount, a recovery, a waiver, or a cash collection.
