# Performance findings

The only measurement is a ceiling test, `test_dev08_repeated_normalization_stays_under_the_ceiling`. It calls `normalize` 30 times on one approved fixed-rate line and requires elapsed time under 5 seconds. It does not report transactions per second.

| Run | Log line |
| --- | --- |
| Upgrade rerun `cpla_dev08_upgrade2.log` | `DEV08 normalize x30 elapsed 0.0349525999990874` |
| Fresh `cpla_dev08_fresh.log` | `DEV08 normalize x30 elapsed 0.039431600001989864` |
| Final upgrade `cpla_dev08_upgrade3.log` | `DEV08 normalize x30 elapsed 0.04503139999724226` |

Normalization does not search every currency rate. Historical conversion reads the frozen text. Live reassessment lookup is limited to 50 rows and returns review if an older cutoff history is unbounded. Identical calls do not write cache rows. There is no persistent result cache, so a corrected rate cannot leave a stale stored answer. The cost is a repeated read of the version line.

No throughput promise is made for a future invoice audit. Loading contract attachments is not part of normalization.
