# Discount policy matrix

A concession applies only when the approved version, or an approved request snapshot, names the type, the scope, and the dates. Missing policy stays in review. It does not become “approve all”.

## Concession types

| Type | Stored value | Adjusted unit price |
| --- | --- | --- |
| Percentage | `percentage` and `percent_exact` | Comparable base × (1 − percent / 100). The percent refers to the DEV-08 comparable price, which may already be a tier price when `tier_discount_policy` is `discount_after_tier`. |
| Fixed per unit | `fixed_per_unit` and `amount_exact` | Comparable base minus the concession after currency and unit normalization. |
| Fixed special price | `fixed_special_price` and `amount_exact` | The approved amount, after the same normalization. It is not computed as base minus amount. |
| Unsupported | `unsupported` plus `unsupported_reason` | `UNSUPPORTED_CONCESSION_TYPE`. A matching buy-x-get-y style benefit stops the evaluation. Other rows on that version are not applied in its place. |

A percentage must be greater than 0 and less than 100. A monetary amount must be positive and must name a currency and a pricing unit. A result that is not a positive selling price returns `DISCOUNT_PRICE_INVALID` or is refused at save. No policy stores a negative selling price.

## Scope

| Dimension | Rule |
| --- | --- |
| Customer | `version_customer` matches the version partner. `exact_partner` matches only the named partner, including a named branch. A parent contract does not cover an unnamed branch. |
| Product | `version_line` matches that line’s variant. `exact_variant` matches the named variant. `product_template` matches variants of the named template. A concession for another product on the same version is ignored. A concession that targets the requested product but fails the customer, variant, or quantity test returns `DISCOUNT_SCOPE_MISMATCH`. |
| Quantity | Minimum is inclusive. Maximum is exclusive. A bound without a verified quantity, or with a different quantity unit, returns `DISCOUNT_EVIDENCE_REVIEW_REQUIRED` and reason `quantity_missing`. |
| Dates | Start is `effective_from` or the version `effective_from`, inclusive. End is `effective_to`, else version `authority_to`, else `valid_to`, inclusive. A later pricing date returns `DISCOUNT_EXPIRED`. An earlier pricing date returns `DISCOUNT_NOT_YET_EFFECTIVE`. |
| Company | The version company must be one of the caller’s companies, and a request `company_id` must equal the version company. Otherwise `COMPANY_ACCESS_DENIED` and no prices. |

## Stacking modes stored on the version

| Mode | Behavior |
| --- | --- |
| `unconfigured`, `no_stacking`, `exclusive_only` | One matching non-exclusive concession applies. Two or more without an exclusive winner return `DISCOUNT_STACKING_REVIEW_REQUIRED`. |
| `additive_percentage` | Base × (1 − r1 − r2 − …) for percentage rows. |
| `sequential_percentage` | Base × (1 − r1) × (1 − r2) × … in sequence order. |
| `percentage_then_fixed` | All percentages first, then fixed per-unit reductions. |
| `fixed_then_percentage` | Fixed per-unit reductions first, then percentages. |
| `fixed_price_replaces_base` | Used when the selected row is one fixed special price. |
| `explicit_rule_order` | Sequence must be unique. A special price replaces the running amount. |

One exclusive concession is used alone, including when the stacking mode is still `unconfigured`. Two exclusive concessions apply together only when every one has a unique non-zero `precedence_rank`. The lowest rank wins. Rank 0 is unset. Price is not a tie-break. A tie returns `DISCOUNT_AUTHORITY_CONFLICT`.

`BEST_SINGLE` is not implemented. The lower price is not chosen in order to favor the customer.

## Tier interaction

| `tier_discount_policy` | When a tier matched and a concession also matches |
| --- | --- |
| `unconfigured` | `DISCOUNT_STACKING_REVIEW_REQUIRED`, reason `tier_discount_policy_missing`. |
| `discount_after_tier` | The percent or amount uses the tier price as the base. |
| `exclusive_tier` | `NO_ADDITIONAL_DISCOUNT`, reason `exclusive_tier`. The tier price stands. `discount_applied` is false. |

A tier gap is not a second discount. The same concession row is not applied twice.

## Approval limits stored on the version

| Basis | What is compared |
| --- | --- |
| `unconfigured` | Approval is refused. Unlimited approval is not granted. |
| `per_unit_reduction` | Unit reduction against `authority_max_unit_reduction_exact`. |
| `percent_reduction` | Percent reduction against `authority_max_percent_exact`. |
| `stated_exposure` | (baseline − proposed) × verified quantity, in the request currency, against `authority_max_exposure_exact`, and the quantity against `authority_exposure_quantity_exact`. |

A price increase is not turned into a discount. A missing quantity does not become a forecast. A different currency or a different unit from the version line is not converted at approval time.
