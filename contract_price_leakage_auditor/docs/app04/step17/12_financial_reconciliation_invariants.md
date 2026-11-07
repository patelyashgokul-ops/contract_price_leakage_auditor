# Financial reconciliation invariants

Amounts are Char decimals. Comparisons use `Decimal`. The company currency is whatever the company record uses. Example figures below are decimal texts, not a claim that the company currency is INR.

## Separate names

| Metric | Meaning |
| --- | --- |
| Current approved recovery target | DEV-16 `current_recovery_exact` |
| Posted gross recovery principal | Current posted `posted_principal_exact` before a reversal releases the row |
| Net current billed recovery principal | Same as current posted principal. A partial credit does not reduce it |
| Authorized unbilled principal | Target minus current posted principal, floored at 0 |
| Accounting receivable outstanding | Native residual, tax included |
| Verified cash recovery principal | Bank-verified allocations attributed to principal |
| Noncash settlements | Credit notes, write-offs, other settlements, and advances |
| Pending payment verification | Matched or registered payments that are not bank-verified |
| Realized FX | Company-currency exchange partials, principal 0 |

`document_is_cash` and `draft_is_posted` are always false. DEV-16 billed and collected on the position stay `0`.

## Equations

For one currency, with every target slice classified and no open revision: approved target = net billed principal + authorized unbilled principal.

For one tax-free currency, when every settlement is in exactly one reducing class: net billed principal = verified cash principal + other verified settlement principal + remaining principal outstanding.

Pending bank verification is outside that cash term. If the native residual does not match the model, the position adds an exception and does not change the stored amounts.

## Invariants

- FIN-17A. A draft is not posted billing.
- FIN-17B. Posted billing is not cash.
- FIN-17C. A credit or write-off is not cash.
- FIN-17D. Recovery principal excludes tax.
- FIN-17E. An FX difference is not principal.
- FIN-17F. A payment allocation is the partial on that receivable.
- FIN-17G. Outstanding follows the classified accounting basis. A failed read is `TECHNICAL_ACCOUNTING_FAILURE`, not zero.

Negative outstanding adds `OVERCOLLECTION_REVIEW_REQUIRED` and the reported outstanding is floored at 0 for display. The evidence rows are kept.
