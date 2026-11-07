# Financial lifecycle reconciliation

`cpla.recovery.balance.position_for()` is the current commercial position of one finance validation.

Validated amount = approved waiver + approved recovery target + unallocated.

Dispute, acknowledgement, and unanswered are inside the recovery target:

recovery target = disputed + acknowledged + unanswered, when those positions have been recorded. An unclassified remainder stays unanswered. It is not waived.

Billed and collected are fixed at `0` in this phase. There is no field write that sets them to another value. A handoff payload also returns billed `0`, collected `0`, `creates_account_move` false, `creates_customer_receivable` false, and `proves_cash_collection` false.

## Examples exercised by tests

Amounts are decimal texts in the company currency. They are not a claim that the currency is INR.

| Position | Validated | Waiver | Target | Unallocated | Inside the target |
| --- | --- | --- | --- | --- | --- |
| Full recovery | 25000 | 0 | 25000 | 0 | No dispute |
| Partial waiver | 25000 | 5000 | 20000 | 0 | Waiver approved before the target |
| Undecided | 25000 | 5000 | 12000 | 8000 | Draft waiver is not in the waiver total |
| Dispute | 25000 | 5000 | 20000 | 0 | Acknowledged 12000 and disputed 8000 |
| Extra settlement waiver | 25000 | 8000 | 17000 | 0 | Original 5000 waiver row remains |
| Partial finance | 18000 | 0 | 18000 | 0 | Finance-rejected 7000 is not a waiver |

Cross-currency addition is refused unless the user records `fx_rate_exact`, a date, and a note. The policy compares the converted amount with the level ceiling in the policy currency. The recorded rate is stored. The module does not look up a market rate.

Superseded and stale balances have `counts_current` false and are omitted from `position_for()`.
