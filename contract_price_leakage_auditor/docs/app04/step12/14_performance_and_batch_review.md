# Performance and batch review

## Measured

Only these timings were measured. They are ten extra audits of one already audited invoice inside `test_dev12_repeat_audit_timing_is_logged`.

| Log | Timing | Invoice count in that test |
| --- | --- | --- |
| `cpla_dev12_class2.log` | 0.5543640999967465 seconds | 1 |
| `cpla_dev12_full1.log` | 0.37981510000827257 seconds | 1 |
| `cpla_dev12_upgrade.log` | 0.4739525000040885 seconds | 1 |
| `cpla_dev12_fresh1.log` | 0.2962407000013627 seconds | 1 |

No throughput in lines per second is claimed. Runs of 1,000, 10,000, 50,000, and 100,000 invoice lines were not executed.

Suite totals, which include every prior phase:

| Run | Tests on the result line | Stats | Queries |
| --- | --- | --- | --- |
| Class rerun | 100 in 113.13s | 102 tests, 113.09s | 60,385 |
| Full update | 878 | 902 tests, 391.73s | 248,197 |
| Upgrade | 878 | 902 tests, 507.43s | 248,168 |
| Fresh | 878 | 902 tests, 457.22s | 248,189 |

## Batching

`batch_size` defaults to 50. `action_run` processes at most 200 moves. Each move has its own savepoint. Customer invoices run before credit notes. A failed move does not mark the remaining moves audited and does not mark the run completed when nothing succeeded.

The selector filters posted customer invoices and credit notes by company and by invoice date or posting date, plus optional customer, product, and contract. It does not scan every move type.

## Indexes

`index=True` is set on company, run, invoice, invoice line, classification, invoice date, finding status, current identity, contract version, allocation, knowledge cutoff, source revision, and input fingerprint, where those fields exist on the run, result, or finding. No further indexes were added. Query plans for a large history were not measured.

## Query risks that remain

Each move calls `map_move`, then the resolver or the lock evaluator, then quantity, financial, and discount services. That is bounded per move, not a load of the full invoice history into one Python list. It is still one service chain per line. A large history will spend time in those existing services. This step did not add a prefetch cache across moves.

Two-worker concurrency was not timed and was not executed.
