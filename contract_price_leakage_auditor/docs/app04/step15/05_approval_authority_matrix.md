# Approval authority matrix

No approval amount is seeded. XML data contains no INR 50000 or INR 500000 ceiling. A missing current approved policy, or a policy with no levels, raises `APPROVAL_MATRIX_MISSING` and blocks formal approval.

## Who maintains the matrix

Only a user in `group_finance_manager` can create or approve a policy revision. `has_group` is not used. Superuser and `group_app_admin` are not finance managers. A finance reviewer can read the policy and cannot write it.

An approved policy cannot be edited. A later revision supersedes it. Historical decisions keep `policy_reference` and `policy_snapshot`.

## How a level applies

A level is required when the threshold basis is greater than or equal to `applies_from_exact`. Bases:

| Basis | Amount compared with the ceiling |
| --- | --- |
| `validated_amount` | Proposed validated amount. |
| `accepted_potential` | Accepted potential. |
| `proposed_adjustment` | Rejected plus unresolved. |
| `customer_open_validated` | This company's current non-stale validated total for the same customer, plus this proposal. |

If any required level has a ceiling, the amount must be at or under the highest of those ceilings. Otherwise the result is `APPROVAL_LIMIT_EXCEEDED`. Levels approve in `level_sequence` order. A later level cannot be skipped.

## Currency

The policy currency and the review currency must match, or the user must have recorded `fx_rate_exact`, a date, and a note through `action_set_review_rate`. The module does not look up a market rate. A raw comparison of two currencies raises `CURRENCY_BASIS_REVIEW_REQUIRED`. Different companies are not added together to reach a ceiling.

Test ceilings such as `100000`, `30000`, and rate `2` exist only inside tests. They are not product configuration.
