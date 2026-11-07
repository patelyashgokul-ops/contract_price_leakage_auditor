# DEV-15 handoff

Date: 2026-11-05. DEV-15 is not started. Finance validation, recovery, waivers, debit notes, payments, and reconciliation are not implemented here.

## Records DEV-15 can read

| Item | Actual name |
| --- | --- |
| Evidence snapshot | `cpla.invoice.audit.result` plus the payload on `cpla.leakage.reassessment` (`proposal_digest`, `schema_version` `dev14.2`). |
| Reassessment | `cpla.leakage.reassessment`. |
| Calculation revision | `cpla.leakage.finding` rows. Current row: `is_current` true and `current_identity` set. Historical row: `superseded_by_reassessment`. |
| Events | `cpla.leakage.reassessment.event`. |
| Case link | `cpla.leakage.case` and membership. `reinvestigation_required`, `finance_package_stale`, `source_reassessment_required`, `reviewed_exposure_exact`. |

## Behavior DEV-15 must keep

- Current accepted potential is the current finding for that identity, or the zero on the audit result when the identity was cleared.
- A proposed amount is not accepted potential.
- `revision_verification` other than `current_verified` or `reassessment_accepted` means the stored current amount is not a fresh verification. `source_changed_review_pending` and `current_result_uncertain` should be reported separately from unquestioned current exposure.
- `finance_package_stale` means the submitted package is historical. It is not current support for a finance decision.
- `reinvestigation_required` does not overwrite root cause. A cleared full reversal may leave no current finding to retarget. The zero is on the result row.
- Self-approval stays blocked. Company rules stay in force. No sudo path was added for pricing.
- Digest mismatch and `evidence_review_required` are not acceptable as a finance-validated figure.
- Original result rows and superseded findings remain.

## Decision dependencies still open

Business acceptance of DEV-14 is pending. License remains `Other proprietary` with `BLOCKER_LICENSE_DECISION_REQUIRED`. The commercial release is NO-GO. DEV-15 still needs an approval matrix for who may mark an amount finance-validated, and a rule for a stale package after that mark. Those decisions are not made in this module.

## Odoo 18 and 20

The module was not converted. Odoo 19 is the master. The following need a separate port and a financial regression before either version is claimed:

- `models.Constraint` and `models.UniqueIndex` syntax.
- `group_ids` on `res.users` and the record-rule `company_ids` context.
- `account.move._reverse_moves` and credit-note line quantities.
- `Command` and company context on `res.partner` and `account.move`.
- Decimal text stored in `Char` fields, not floats.
- JSON canonicalization and digest fields.
- View types `list` versus `tree`.
- Test tags and `TransactionCase` cursor commit rules.
- Chart template `try_loading('generic_coa', ...)`.

None of those were executed on Odoo 18 or Odoo 20.
