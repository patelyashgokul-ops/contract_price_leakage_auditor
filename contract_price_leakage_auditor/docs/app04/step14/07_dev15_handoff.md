# DEV-15 handoff

DEV-15 is not implemented. Do not start finance validation from this file. The later handoff is `17_dev15_handoff.md`. This file remains the sections 1–36 package list.

Business acceptance: `PENDING`. Release: `NO-GO`. License: `BLOCKER_LICENSE_DECISION_REQUIRED`. The two-worker result is in `15_performance_and_concurrency.md`, not in this older note.

The DEV-14 prompt ended at section 36.3. Nothing after that heading was specified, and nothing after it was built.

## What a finance reviewer can already see

`cpla.leakage.case` can be `ready_for_finance_review`. That state is not finance validation. The submission row is `cpla.leakage.case.submission`. It copies the exposure text, currency, root cause, and finding identity that existed at submit time.

`finance_package_stale` becomes true when a same-identity reassessment is accepted while the case is already in `ready_for_finance_review`. The submission row is kept. The flag is not a finance rejection. A new submit clears it, and submit refuses while `source_reassessment_required` is true.

`reviewed_exposure_exact` is the investigator's accepted text. Engine acceptance does not change it. `action_accept_current_source` copies a current successor and only from an open investigation state. A finance-submitted case must be returned before that copy.

## Accepted calculation

The current economic amount for one identity is the current `cpla.leakage.finding` when one exists. A full reversal or other zero outcome leaves no current finding. The accepted zero is `cpla.leakage.reassessment.successor_result_id` and the new `cpla.invoice.audit.result` row. The original result row is still the earlier amount. Do not add those rows together. Do not invent a current zero finding. Do not treat the delta as recovered cash or a write-off. `is_recovered_cash` and `is_writeoff` are stored false and acceptance refuses the row if either is true.

A different knowledge cutoff is a different identity. Its amount was not subtracted from the other cutoff. The case event is `separate_interpretation_recorded`. That finding was not added to the case.

## Authority already enforced

A contract manager requests. A finance manager evaluates and accepts. The requester cannot accept. A finance reviewer can reject and cannot accept. DEV-15 must not reuse acceptance as the finance-validation decision, and it must not grant that decision to the requester.

## Do not rebuild

Do not add a second price engine. `ENGINE_VERSION` is `dev12.1`. The proposal schema is `dev14.1`. Do not call `action_reassess` or `action_run` to accept a proposal. The run form still has `action_reassess`. That button can move the current finding without a DEV-14 decision. DEV-15 should treat that as an open control, not as finance approval.

Do not post invoices, credits, payments, or recovery documents. Do not approve a backdated contract amendment. The version workflow still refuses that approval.

## Still open for a later phase

Finance validation itself. Recovery, waivers, and collection. A numerical confidence score. Monetary approval thresholds. An external evidence archive. A recurring source monitor. An executive dashboard. Odoo 18 and Odoo 20. A second worker proving the open-request unique index under concurrency. Business sign-off. The license decision.
