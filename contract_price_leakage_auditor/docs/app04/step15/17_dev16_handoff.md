# DEV-16 handoff

DEV-16 is not started. This phase does not create a recovery claim, a waiver, a dispute, a debit note, a payment, or a reconciliation.

## Records DEV-16 can read

| Item | Actual name |
| --- | --- |
| Finance validation | `cpla.finance.validation` |
| Finding decision | `cpla.finance.validation.line` |
| Approval event | `cpla.finance.validation.approval` |
| Current amount API | `decision_payload()` and `current_validated_amount(company, partner=None)` |
| Accepted source | `finding_id`, `result_id`, `finding_identity`, `source_fingerprint`, `source_revision` |
| Policy | `policy_id`, `policy_reference`, `policy_snapshot`, `threshold_basis` |
| Case | `case_id`, `submission_id`. Case event `finance_decision_recorded` stores the reference in `new_value`. |

Use a payload only when `current` is true. `approved_amount` is the finance-validated amount in `currency_id`. `rejected_amount` and `unresolved_amount` are separate. `stale_source` true means the historical amount is not fresh recovery authority.

`recovery_authority`, `creates_customer_receivable`, `proves_cash_collection`, `is_waiver`, `is_recovery_billed`, and `is_cash_recovered` are false.

## What DEV-16 must add before it can bill or waive

- An authorized recovery-target decision, distinct from `validated_exact`.
- A commercial waiver decision, distinct from `rejected_exact`.
- Customer dispute records.
- A posted receivable path that this module does not call.
- Payment matching and collected-cash evidence.
- A rule for a stale finance decision: do not bill the old amount without a new current validation.
- Company approval limits for waiver and recovery. None are seeded here.
- No double count of the same `finding_identity` across cases.

## Separation

Potential leakage is the finding amount. Finance-validated leakage is the current non-stale approved amount. A rejected amount is not a waiver. A validated amount is not billed and is not collected.

## Open decisions

Business acceptance of DEV-15 is pending. License remains `Other proprietary` with `BLOCKER_LICENSE_DECISION_REQUIRED`. Commercial release is NO-GO. Companies still have to approve their own finance matrix before a production approval can succeed. No production ceiling was invented.

## Odoo 18 and 20

Odoo 19 remains the master. This phase did not convert the module. A later port must re-test finance arithmetic and role security, and must separately verify:

- Security group APIs, including `group_ids` and `all_group_ids`, and the superuser `has_group` short-circuit.
- ACLs and record rules, including `company_ids` in the rule context.
- Currency rounding and any conversion helper that replaces a user-recorded rate.
- ORM constraints and `models.UniqueIndex` WHERE clauses.
- Approval workflow method names and button types.
- Chatter and activity integration. This phase does not inherit `mail.thread` on the validation and does not schedule activities.
- XML view types (`list` versus `tree`) and the inherited case form.
- Company-dependent fields and `with_company`.
- Historical evidence JSON canonicalization.
- Server datetimes and the rule that the actor is `env.user`.
- Partial unique indexes for one open package and one current decision.
- The automated test tag selector. Method-level `@tagged` must not replace the class selector.

Do not start DEV-16 from this file.
