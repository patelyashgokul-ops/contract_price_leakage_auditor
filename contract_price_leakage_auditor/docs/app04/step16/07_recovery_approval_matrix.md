# Recovery approval matrix

Authority is a company-approved `cpla.recovery.policy`. No ceiling amount is seeded in XML or in Python defaults. `has_ceiling` defaults to true, and `maximum_exact` is empty until a user enters it. Policy approval is blocked while a ceiling level has no amount. Tests pass a fixture ceiling such as `100000`. That figure is not a product limit.

## Separate actions

Each level has `action_kind` of recovery, waiver, settlement, or handoff. A level applies when `applies_from_exact` is less than or equal to the amount being approved. No level for that action raises `APPROVAL_MATRIX_MISSING`. An amount above every ceiling for that action raises `APPROVAL_LIMIT_EXCEEDED`.

The only selectable authority group is Contract Manager (`contract_price_leakage_auditor.group_contract_manager`). A finance validator does not become a waiver approver by validating the exposure. Recovery Operator has no model access and is not an approver. Application Administrator is not a commercial approver. Technical administration does not grant waiver approval.

## Separation

`four_eyes_required` defaults to true. The requester cannot approve. One user cannot complete two levels of the same document. Combined group membership does not bypass that identity check. The actor is `env.user`. Client-supplied approver ids are not trusted.

`dispute_blocks_handoff` defaults to true. It is a boolean gate for that recovery request. It is not a monetary threshold and not a customer-level aggregate. There is no percent-of-exposure threshold.

A new approved policy supersedes the previous current policy. Older approval snapshots keep the policy reference they used. Historical approvals are not reinterpreted when a later ceiling changes.

Company A limits do not apply to Company B. The policy is company-scoped by the global company record rule.
