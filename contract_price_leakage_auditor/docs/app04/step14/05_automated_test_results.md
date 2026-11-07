# DEV-14 automated test results

Date: 2026-11-05. Version: `19.0.1.12.0`. Odoo version in every log below: `19.0`. HTTP port `8093`. Port `8071` stayed on PID `7328` and was not stopped. The logs in this file are the pre-37 runs. Later results are in `13_automated_test_results.md`.

The selector `--test-tags=rev14` is not a pass. Method tags replace the class `post_install` tag and are not copied onto the test instance, so that selector ran 0 tests. The working selector is `/contract_price_leakage_auditor:TestDev12InvoiceAudit` for the audit class, or `/contract_price_leakage_auditor` for the addon. The 11 REV14 methods have no extra tag.

Caught unique-constraint errors in the logs are the existing idempotency tests. They are not failures when the result line is 0 failed and 0 errors.

Two-worker concurrency was not run. Currency was not asserted to be INR. The amounts are decimal texts in the company currency.

## Runs

| Run | Database | Command | Log | Result |
| --- | --- | --- | --- | --- |
| Tag probe | `cpla_dev14_20261105` | `-i`, `--test-tags=rev14` | `cpla_dev14_rev14.log` | 0 failed, 0 errors of 0 tests at 2026-11-05 05:39:24, PID 21428. Not a functional pass. |
| Class, before the assertion fix | `cpla_dev14_20261105` | class selector, no `-u` | `cpla_dev14_class.log` | 1 failed, 0 errors of 111 tests at 2026-11-05 05:44:56, PID 7620. |
| One method after the fix | `cpla_dev14_20261105` | exact `test_rev14_t007` | `cpla_dev14_t007.log` | 0 failed, 0 errors of 1 test. 1 post-test in 21.24s, 5277 queries. 2026-11-05 05:46:12, PID 21440. |
| Class rerun | `cpla_dev14_20261105` | class selector, no `-u` | `cpla_dev14_class2.log` | 0 failed, 0 errors of 111 tests. 111 post-tests in 294.09s, 70958 queries. Stats: 113 tests, 293.82s, 70958 queries. 2026-11-05 05:51:37, PID 16612. |
| Full addon | `cpla_dev14_20261105` | addon tag, no `-u` | `cpla_dev14_full.log` | 0 failed, 0 errors of 909 tests. 909 post-tests in 845.61s, 275496 queries. Stats: 935 tests, 845.03s, 275496 queries. 2026-11-05 06:06:22, PID 18716. |
| Upgrade from `19.0.1.11.0` | `cpla_dev13_20261105` | `-u`, addon tag | `cpla_dev14_upgrade.log` | 0 failed, 0 errors of 909 tests. 909 post-tests in 654.31s, 275465 queries. Stats: 935 tests, 653.99s, 275465 queries. 2026-11-05 06:18:45, PID 18636. Exit 0. |
| Fresh install | `cpla_dev14_fresh_20261105` | `-i`, addon tag | `cpla_dev14_fresh.log` | 0 failed, 0 errors of 909 tests. 909 post-tests in 519.41s, 275483 queries. Stats: 935 tests, 519.13s, 275483 queries. 2026-11-05 06:32:49, PID 17528. Exit 0. |

909 post-tests are the previous 898 plus the 11 REV14 methods. The stats line also counts tests that are not in the post-install result line. That split was already present before DEV-14.

## The one failed assertion

`test_rev14_t007` first required one current finding after a full reversal. The engine clears a zero outcome and then releases that row, so no current finding remains. The test now requires current exposure `0`, no current potential finding, the historical `5000` rows not current, a successor result of `0`, and the original result still `5000`. The engine was not changed. The isolated rerun and the later class, full, upgrade, and fresh runs passed.

## What the passing REV14 methods cover

| Test | Covered result |
| --- | --- |
| `test_rev14_t001` | Quantity 20 return. Preview `4000` and delta `-1000` do not insert a finding. Acceptance leaves one current finding of `4000`, one superseded `5000`, and the original result `5000`. Exposure is not `9000`. Open request is reused. Company B cannot read it. The manager cannot accept. Invoice and payment counts stay. |
| `test_rev14_t002` | A tampered proposal amount blocks acceptance. The finding stays current at `5000`. The original digest stays. |
| `test_rev14_t003` | An open case keeps reviewed exposure `5000` and state `new` after acceptance. The investigator copy is a separate action. |
| `test_rev14_t004` | A submitted case stays `ready_for_finance_review`, `finance_package_stale` becomes true, and retarget is refused. The submission row stays. |
| `test_rev14_t005` | The requester cannot accept, including a user with both manager and finance-manager groups. |
| `test_rev14_t006` | An amount-only credit is not a quantity return and is not converted into returned pieces. |
| `test_rev14_t007` | Full reversal acceptance clears current exposure without a second current finding. |
| `test_rev14_t008` | Cutoff `2026-07-01` proposes `0` on V1 and is not subtracted from the current `20000` on the later version. A backdated amendment stays unapproved. |
| `test_rev14_t009` | A finance reviewer can reject and cannot evaluate or accept. |
| `test_rev14_t010` | A replacement without a verified reversal is not forced to zero. After a mapped full credit, acceptance clears exposure and does not create a payment. |
| `test_rev14_t011` | Manifest `19.0.1.12.0`, form, menu, sequence, finding wizard, the old reread button still present, no finance-validated field, and no module cron. |

## Not executed

Two Odoo workers racing the same finding were not started. A second database session was not opened. The partial unique index was exercised by the open-row reuse in `test_rev14_t001`, not by two concurrent inserts.
