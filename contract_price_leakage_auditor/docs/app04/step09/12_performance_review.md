# Performance review

Measurements are wall-clock times printed by the tests. They are not a throughput claim. No query-per-second figure is reported. No price cache is used.

## Discount evaluation

`test_dev09_repeated_evaluation_stays_under_the_ceiling` calls `cpla.discount.evaluator.evaluate` 30 times on one approved 5 percent line.

| Run | Elapsed seconds for 30 calls |
| --- | --- |
| Class tag, `cpla_dev09_20261028` | 0.2757461000001058 |
| Full tag, `cpla_dev09_20261028` | 0.1725739999965299 |
| Upgrade tag, `cpla_dev08_20261028` | 0.1882162999972934 |
| Fresh `-i`, `cpla_dev09_fresh_20261028` | 0.23730459999933373 |

Each call is under the five-second ceiling asserted by the test. The evaluator searches approvals by company, version, partner, product, and state. It does not scan every approval in the database and it does not load attachments.

## Financial normalization, same runs

DEV-08 `normalize` × 30:

| Run | Elapsed seconds |
| --- | --- |
| Full tag, `cpla_dev09_20261028` | 0.037931500002741814 |
| Upgrade tag, `cpla_dev08_20261028` | 0.05509889998938888 |
| Fresh `-i`, `cpla_dev09_fresh_20261028` | 0.06467040001007263 |

The resolver calls normalize once, and the discount evaluator calls it again. Both calls are read-only. The second call is the cost of keeping the discount service usable without a resolver. It is accepted for this phase.

## What is not cached

An adjusted price is not cached by customer and product. A later cutoff, quantity, currency, unit, version, or stacking mode would make that cache wrong. This phase does not add a cache.

## Suite size

The green full run executed 610 post-tests in 194.95s and 116,475 queries. The green upgrade run executed 610 post-tests in 188.80s and 116,472 queries. Registry load on the upgrade was 14.028s. The fresh install executed 610 post-tests in 243.13s and 116,534 queries. Those figures include user creation and contract approval, not only the discount formula.
