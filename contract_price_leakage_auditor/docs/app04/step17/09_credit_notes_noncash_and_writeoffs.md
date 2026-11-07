# Credit notes, noncash settlements, and write-offs

A credit reduces recovery principal only when `reversed_entry_id` is this billing's move, or a posted `cpla.recovery.accounting.adjustment` links that move. Any other reconciled `out_refund` is `unknown_credit`.

## Categories

| Category | When |
| --- | --- |
| `PARTIAL_RECOVERY_BILL_REVERSAL` | Supported credit principal is above zero and below posted principal. |
| `FULL_RECOVERY_BILL_REVERSAL` | Supported credit principal covers posted principal. The stored category is rewritten to this value when the credit sum reaches the posted amount. |
| `TAX_ONLY_CREDIT` | Supported credit with zero principal. |
| `SETTLEMENT_CREDIT` | An evidence row reclassified to `other_settlement` keeps this category. |
| `UNRELATED_CUSTOMER_CREDIT` | The refund reverses a different move. |
| `UNKNOWN_CREDIT_ALLOCATION` | The refund has no reversal link to this billing. |
| `DUPLICATE_BILLING_CORRECTION` | Selection value only. No automatic duplicate correction is posted. |

`unknown_credit` has principal 0, does not reduce outstanding, and adds `CREDIT_ALLOCATION_AMBIGUOUS`. The native residual may still fall. The report does not force the equation.

## Example that stays split

Posted principal 20000, supported credit 5000, bank-verified cash 10000. Verified cash is 10000. Noncash credit is 5000. Outstanding principal is 5000. Unbilled stays 0. Verification state contains both `BANK_VERIFIED_CASH` and `CREDIT_NOTE_SETTLEMENT`.

## Full noncash offset

An unrelated credit reconciled to the receivable is not cash and does not reduce principal until `action_classify_settlement` labels that partial `other_settlement` or `write_off`. The method writes the override and the reason. It does not create an `account.move`. A commercial waiver does not prove a write-off.

## Full reversal

A supported credit for the full principal sets `fully_reversed`, retains historical posted principal, and releases the slice. Verified cash stays 0 unless a real bank allocation exists.
