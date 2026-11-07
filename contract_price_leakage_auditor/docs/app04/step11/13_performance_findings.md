# Performance findings

No queries-per-second figure is claimed. Datasets of 5,000, 50,000, 100,000, and 500,000 invoice lines were not loaded.

The only measured repeat-map timings are `DEV11 map x30` from `time.perf_counter` around thirty mappings of one unchanged posted invoice:

| Run | Log | Seconds |
| --- | --- | --- |
| Failed class, not acceptance | `cpla_dev11_class1.log` | 0.24204209999879822 |
| Green class | `cpla_dev11_class2.log` | 0.13581469999917317 |
| Full tag | `cpla_dev11_full1.log` | 0.14899830000649672 |
| Upgrade | `cpla_dev11_upgrade.log` | 0.12942329999350477 |
| Fresh install | `cpla_dev11_fresh1.log` | 0.14030500000808388 |

`_locks_for` searches locks once per move for the initial evaluation. `_fingerprint` searches locks again per line. That second search is an N+1 risk on a large invoice. Candidate origin lookup is an exact name and company search with limit 2. Attachments are not scanned. Unchanged fingerprints return the current row without a new allocation.

There is no cron. Batch mapping is `map_moves`, one savepoint per document. It is not a scheduled audit.
