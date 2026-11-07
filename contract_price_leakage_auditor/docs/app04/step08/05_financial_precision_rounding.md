# Financial precision and rounding

Display decimals and calculation decimals are different. Intermediate FX and unit conversion stay exact until the clause names a rounding stage.

## Stages

| `rounding_stage` | Behavior |
| --- | --- |
| `unconfigured` or `preserve_exact` | The unit text is the exact decimal. `currency.round` is not called. |
| `per_unit` | The unit is quantized to `currency.rounding` with half-up, then an extended amount may use that rounded unit. |
| `extended_amount` | The unit stays exact. `unit * quantity` is quantized. Missing quantity leaves the unit exact and does not invent a quantity. |

The increment comes from the comparison currency. It is not hardcoded to 0.01. Q8C uses rounding 1.0, so 100.6 per unit becomes 101. A zero or negative increment returns `PRECISION_POLICY_REVIEW_REQUIRED`.

## Example

Exact unit 1.005 and quantity 100:

- Extended stage: unit stays 1.005. Extended amount rounds to 100.50.
- Per-unit stage: unit becomes 1.01. Extended amount of the rounded unit is 101.

Those stages are not interchangeable.

## Arithmetic

Prices and rates use `decimal.Decimal`. Boolean and blank values are not numbers. NaN and infinity are rejected. Equality checks in the tests compare `Decimal` values, including `0.1 + 0.2` against `0.3`.

Canonical text strips insignificant trailing zeros, so a reciprocal of 84 is stored as `84`, not `84.0`. The numeric value is unchanged.
