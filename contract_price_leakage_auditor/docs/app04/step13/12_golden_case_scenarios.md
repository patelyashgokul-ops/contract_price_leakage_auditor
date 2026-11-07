# Golden case scenarios

These rows are what `TestDev13LeakageCase` asserted on database `cpla_dev13_20261105`. Amounts are the finding text copied onto the case. The company currency is the `generic_coa` currency of company ABC India. The test did not assert that currency name is INR. The text `25000` is the exposure, not a finance-validated amount.

| ID | Expected | Actual in the class test |
| --- | --- | --- |
| CASE-REF-001 | One case, exposure text `25000`, state `new`, no finance validation, posted invoice unchanged. | `test_case13_creation_company_reference_and_reuse` posted a sale invoice at 1100 for quantity 500 after an approved price of 1150, audited it, and opened one case. Exposure and reviewed exposure were `25000`. Repeat open returned the same case. Reference matched `CPL-CASE/YYYY/#####`. Invoice price, posted state, move count, and payment count were unchanged. |
| CASE-REF-002 | Three findings, one case, text `25000`. | `explicit_same_issue` grouped `10000`, `10000`, and `5000`. Three current memberships. Total `25000`. Repeat returned the same case. |
| CASE-REF-003 | One current membership after another audit of the same economics. | Historical revision is superseded and is not a second case. A successor identity opens a different case only after the old identity is cleared. The closed case keeps `is_current`, so a second open returns that case. |
| CASE-REF-004 | Different customers stay apart. | `explicit_same_issue` across two customers raises. Separate opens create two cases. |
| CASE-REF-005 | No mixed-company case. | A user in both companies cannot group company A and company B. |
| CASE-REF-006 | Assign records the owner and an event. | State `assigned`. Event type `assigned`. |
| CASE-REF-007 | Other-company assign is denied. | Company B user cannot read the company A case. A company B owner is rejected. |
| CASE-REF-008 | Missing evidence stays pending and does not invent an approval. | Missing pricing evidence opens `pricing_evidence_exception` with a blank amount and queue `pricing_date_review`. Evidence pending is a state with a required reason. |
| CASE-REF-009 | Contract conflict has no authoritative amount. | `conflict_review`, queue `contract_review`, blank exposure. |
| CASE-REF-010 | Root cause is recorded with an explanation and is not finance validation. | Root cause is not the detector category. No finance-validated field exists. |
| CASE-REF-011 | Complete checklist submits and keeps a snapshot. Validated amount stays unset. | State `ready_for_finance_review`. Snapshot fields survive. No validated field. |
| CASE-REF-012 | Finance return keeps the snapshot. | `returned_for_rework`. Reason and time stored. Snapshot text unchanged. A second submit adds a row. |
| CASE-REF-013 | Merge keeps findings and one exposure. | `10000 + 10000 + 5000` becomes `25000` on the survivor. Source case remains, closed `superseded_by_case`. |
| CASE-REF-014 | Split keeps every finding and the parts sum to the original. | After the merge, a split yields `20000` and `5000`. Splitting every finding raises. |
| CASE-REF-015 | Source revision is flagged. Old snapshot kept. Accept copies the successor text. | Successor text `4000`. Refresh blanks the current display and keeps reviewed `25000`. Accept sets both texts to `4000`, not `9000`. Event `previous_value` is `25000`. |
| CASE-REF-016 | Duplicate close leaves the finding and does not record cash. | Closure `duplicate_case`. Finding remains. One current membership. `is_recovered_cash` stays false. No payment. |
| CASE-REF-017 | Reopen needs a reason and does not create a second case. | State returns to `under_investigation`. One current membership. A merged case cannot be reopened. |
| CASE-REF-018 | An activity has the requested user and date and does not recover cash. | `mail.activity` with the given date, `automated` false. `action_feedback` leaves state and amount. No new cron. |
| CASE-REF-019 | Other-company attachment read is denied. | Company B manager `read(['datas'])` raises `AccessError`. Public create, token, and unlink raise `UserError`. |
| CASE-REF-020 | Potential text is shown. Validated, billed, and collected amounts are absent. | Those field names are not on the case. Close does not mark recovered cash. |

Two database workers were not started. The concurrency test logs `CON13 two-worker concurrency was NOT_EXECUTED` and uses one transaction, a hidden membership search, and `IntegrityError` inside a savepoint.
