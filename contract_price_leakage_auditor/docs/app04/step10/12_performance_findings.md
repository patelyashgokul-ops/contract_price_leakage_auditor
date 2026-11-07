# Performance findings

No `ormcache` was added. The evaluator does not load attachments. It does not scan contract history itself. The resolver still does the version search.

Measured `evaluate_order` of one priced quotation, 30 calls, `time.perf_counter`:

| Run | Database | Elapsed seconds |
| --- | --- | --- |
| Class tag, green | `cpla_dev10_20261028` | 0.4383508000028087 |
| Full tag, green | `cpla_dev10_20261028` | 0.4635331000026781 |
| Upgrade tag, green | `cpla_dev09_20261028` | 0.33119180001085624 |
| Fresh update, green | `cpla_dev10_fresh_20261028` | 0.9602049999957671 |

These are wall times for 30 evaluations inside the test transaction. They are not queries per second. They are not a multi-user benchmark.

Full-suite query counts are in `11_installation_upgrade_regression.md`. A quotation with hundreds of lines was not generated. N+1 behavior of the resolver on a large order was not measured separately.

Computed form fields call the resolver for the lines on the order. A note line is classified without a contract search. An unrelated note still sits on an order whose commercial lines are recomputed when order dependencies change.

A two-worker confirmation race was not executed. `TransactionCase` cannot commit. The `UNIQUE(sale_line_id)` constraint is the cross-transaction guard. It was not proven with two database sessions.
