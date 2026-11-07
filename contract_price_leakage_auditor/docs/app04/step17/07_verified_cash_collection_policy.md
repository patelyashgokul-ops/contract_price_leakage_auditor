# Verified cash collection policy

`bank_verification_required` defaults to true on the billing policy. A company can turn it off only by approving that policy. Tests use the default.

## Classification

| Kind | Verification label | Counts as verified cash | Reduces outstanding principal |
| --- | --- | --- | --- |
| `verified_cash` | `BANK_VERIFIED_CASH` | Yes | Yes |
| `unconfirmed_payment` | `PAYMENT_PENDING_BANK_VERIFICATION` | No | No |
| `credit_note` | `CREDIT_NOTE_SETTLEMENT` | No | Yes |
| `write_off` | `WRITE_OFF_SETTLEMENT` | No | Yes |
| `advance` | `NONCASH_OFFSET` | No | Yes |
| `other_settlement` | `NONCASH_OFFSET` | No | Yes |
| `unknown_credit` | `UNVERIFIED_SETTLEMENT` | No | No |
| `fx_difference` | not a collection label | No | No |

When several kinds are present, `verification_state` joins the labels with commas. It is not collapsed to one Paid flag. No rows and historical evidence returns `REVERSAL`. No rows and no history returns `UNPAID`. `PAYMENT_REGISTERED` is not produced from `payment_state`.

## Bank evidence

A payment is verified cash when `reconciled_statement_line_ids` is set, or when `bank_verification_required` is false. A statement line reconciled directly to the receivable, with no payment, is verified cash. The test bank match sets the suspense line to the payment liquidity account and reconciles suspense with liquidity only. It does not add a second partial onto the invoice receivable.

A payment dated before `posted_on` is an `advance` before the bank check. The receipt date stays on the payment. The allocation date is the reconciliation. The advance reduces outstanding and is not new cash on the allocation date.

## Direct bank journals

A payment method that uses the bank account directly can reach `paid` without the outstanding-account statement match used above. That status is still not treated as verified cash unless the statement or the policy exception is actually present.
