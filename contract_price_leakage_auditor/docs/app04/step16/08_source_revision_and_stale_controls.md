# Source revision and stale controls

Every material commercial record stores the company, the finance validation, the finding identity, the source fingerprint, and the source revision taken from the current finance line. The line must be `counts_current`. Acceptable finance evidence is the current approved or partially approved decision. `manual_authorized_review` is not treated as a fresh commercial source by this phase. The finance bind still requires the validation payload to be current and not stale.

## When the source changes

`cpla.finance.validation._flag_one()` calls `_flag_recovery_authority()` when `cpla.recovery.request` is in the registry. That hook calls `_flag_finance_source()`. It does not import the recovery module from the finance module at file load. It does not flag a finance record that is already superseded. `_mark_in_progress_stale()` does not call the hook.

The hook sets current balances to `counts_current` false. An approved request stays `approved`, with `stale_source` true, and its `approved_recovery_exact` is kept. Open requests move to `stale_source`. A new recovery or waiver prepare against that validation raises `STALE_FINANCIAL_EVIDENCE`. Historical events stay.

The hook does not create a credit note and does not change a posted invoice. If a later DEV-17 document has already billed an allocation, this phase has no billing document to revise. `billed_amount_exact` remains `0`, so that accounting-impact path is `DEFERRED_TO_DEV17`.

A finance reviewer who is not a contract manager and who reruns an audit that supersedes a finding with an open recovery can receive an access error on the hook write. The hook runs as the current user. Superuser audit tests are not that case. No extra write ACL was granted to hide it.
