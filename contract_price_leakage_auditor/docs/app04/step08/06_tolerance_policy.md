# Tolerance policy

DEC-08 is open. No numeric tolerance is approved. `propose_tolerance` still raises for any number. The company field `tolerance_policy` is a candidate and is not read by the normalizer.

## Evaluator

`classify_difference` returns the signed value `expected - actual`.

| Input | Result |
| --- | --- |
| Expected 1000, actual 999.98 | Raw difference `0.02`. `within_tolerance` false. `tolerance_suppressed` false. |
| Expected 1000.02, actual 1000, tolerance argument `0.05` | Raw difference `0.02` is kept. The argument does not classify the difference as within tolerance. |
| Expected 1000, actual 1100 | Raw difference `-100`. Overbilling is not turned into positive leakage. |
| Negative tolerance | `ValidationError`. No difference is stored. |
| No tolerance | The raw difference is kept. No 1 percent or 1 currency-unit threshold is invented. |

`leakage_amount` is false on every difference result. DEV-12 decides whether a difference becomes a finding. Absolute and percentage combination rules are not implemented, because no combination is approved.
