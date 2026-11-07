# Full, partial, rejection, and unresolved amounts

For each finding, after the accepted source is already in one currency:

- `P` is the current accepted potential.
- `V` is the finance-validated amount.
- `R` is the rejected amount.
- `U` is the unresolved amount.

A complete proposal must satisfy `P = V + R + U` at the review currency rounding.

Also required: `P`, `V`, `R`, and `U` are at least `0`; `V` is not above `P`; `R` is not above `P`; `V + R` is not above `P`.

`V` above `P` raises `VALIDATION_EXCEEDS_POTENTIAL`. The ordinary form cannot type a larger number. A larger exposure goes back through DEV-14 reassessment and a new accepted finding.

A negative amount raises `INVALID_VALIDATION_AMOUNT`.

`FULLY_SUPPORTED` is allowed only when `V = P`, `R = 0`, and `U = 0`. Any rejected amount needs its own reason and an explanation of at least 8 characters when the decision is not a full match.

Unresolved is stored on `unresolved_exact`. It is not copied into `rejected_exact`.

`AUTHORIZED_DISCOUNT_CONFIRMED` is refused unless an approved `cpla.discount.approval` exists for the same company, contract version, and product. A typed claim does not zero the finding.

A verified return is already in the accepted potential. Finance validation does not subtract that credit again.

Rounding uses the currency increment and `ROUND_HALF_UP`. A dusty proposal is stored at the quantized amount. No silent tolerance skips validation.

Header totals are the sums of the lines. `current_validated_amount` adds only lines with `counts_current` true in that company. It does not add rejected or unresolved amounts, and it does not add another company's exposure.
