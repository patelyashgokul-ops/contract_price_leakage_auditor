# Golden accounting fixtures

These are the DEV-17 fixtures. Amounts are decimal texts. The test company currency is the company record, not a seeded INR currency. A row is executed only when an automated test asserts it. GOLD-ACC17-014 is `NOT_EXECUTED`.

| ID | Expected |
| --- | --- |
| GOLD-ACC17-001 | Validated 25000, waiver 5000, target 20000, posted principal 20000, verified cash 12000, outstanding principal 8000. No tax, credit, or FX. |
| GOLD-ACC17-002 | Target 20000 with only a draft. Posted principal 0. |
| GOLD-ACC17-003 | Posted principal 20000. Cash stays 0 until a bank-verified allocation exists. |
| GOLD-ACC17-004 | Posted 12000 and draft 8000. Posted principal 12000. Unbilled 8000. |
| GOLD-ACC17-005 | The same allocation prepared twice returns one billing and one current link. |
| GOLD-ACC17-006 | Principal 20000, tax 3600, gross 23600. Reported billed principal is 20000. |
| GOLD-ACC17-007 | Posted 20000, bank-verified allocation 12000, outstanding 8000. |
| GOLD-ACC17-008 | Bank-verified 5000 + 7000 + 8000. Cash 20000. Outstanding 0. Three partial keys. |
| GOLD-ACC17-009 | One grouped payment. Recovery allocation 12000. The other invoice's 38000 is not recovery cash. |
| GOLD-ACC17-010 | A payment with no statement line stays `PAYMENT_PENDING_BANK_VERIFICATION`. |
| GOLD-ACC17-011 | Principal 20000, supported credit 5000, bank cash 10000, outstanding 5000. Cash is not 15000. |
| GOLD-ACC17-012 | A classified full noncash offset leaves residual 0, cash 0, and posted principal 20000. |
| GOLD-ACC17-013 | A classified write-off is not cash. The method does not create a move. |
| GOLD-ACC17-014 | `NOT_EXECUTED`. No stored rate was applied. Currency count must stay unchanged. |
| GOLD-ACC17-015 | A Company B move cannot be linked to a Company A recovery. |
| GOLD-ACC17-016 | A different customer's posted invoice is `BILLING_DOCUMENT_MISMATCH`. |
| GOLD-ACC17-017 | Full supported reversal keeps historical principal, clears current principal, and does not create cash. |
| GOLD-ACC17-018 | After unreconcile, current cash is 0 and the old evidence row remains `REVERSAL`. |
| GOLD-ACC17-019 | Two receivable maturities are aged separately. Not-yet-due is not the whole principal. |
| GOLD-ACC17-020 | Validated 25000, waiver 5000, target 20000, posted 20000, cash 12000, outstanding 8000 stay on separate keys. DEV-16 billed and collected stay 0. |

The reconciliation report row for the 25000 / 5000 / 20000 case uses those same keys and returns `totals` false.
