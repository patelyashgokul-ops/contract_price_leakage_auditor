# Tax normalization

`account` is not a dependency. `account.tax` and `account.fiscal.position` are absent on a fresh Community database that has not installed invoicing. This phase does not call `compute_all`, does not post tax entries, and does not file returns.

The contract clause names the commercial basis. The product's current taxes are not read.

## Supported structures

| Basis | Structure | Result |
| --- | --- | --- |
| `tax_excluded` | `none` | Net equals the source amount. Tax component is `0`. |
| `tax_included` | `single_ordinary_percent` | `net = amount * 100 / (100 + percent)`. Example: 1180 at 18 percent is 1000. The 180 is not lost revenue. |
| `unconfigured` | any | `TAX_BASIS_REVIEW_REQUIRED`. Included and excluded amounts are not compared. |
| `tax_included` | `fixed`, `division`, `group`, `tax_on_tax`, `complex` | `UNSUPPORTED_TAX_STRUCTURE`. The price is not divided by one plus a percent. |

A missing percent on a simple included tax is review, not an invented rate. Tax is removed in the source currency before FX.

## Fiscal position

A request `fiscal_position_id` returns `TAX_BASIS_REVIEW_REQUIRED` / `fiscal_position_not_verified`. Product default tax is not treated as the invoice tax. DEV-11 owns the verified invoice tax context.

## Comparable basis

Successful results set `normalized_tax_basis` to `tax_excluded`. Gross, tax, and net stay separate fields. `tax_component_exact` is evidence. It is not `leakage_amount`.

GOLD-TAX-003, executed as `test_tax08_gold_tax_003_included_gross_net_and_extended_difference`: contract net 1000 and included gross 1062 at 18 percent become unit nets 1000 and 900. At quantity 100 the signed extended difference is 10000. That number is diagnostic. No finding is created.
