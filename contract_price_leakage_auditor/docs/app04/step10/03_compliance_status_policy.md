# Compliance status and company mode

Company mode is `cpla.company.policy.quotation_compliance_mode`. It is copied onto a new policy revision. It does not approve a price, store a tolerance, or recover cash. `operationally_approved` stays false. DEC-01 through DEC-20 stay open. The company discount candidate stays non-operational.

Stored keys: `unconfigured`, `disabled`, `warning`, `approval_required`, `block`. Default is `unconfigured`.

## Line statuses

`COMPLIANT`, `COMPLIANT_AUTHORIZED_OVERRIDE`, `BELOW_APPROVED_PRICE`, `APPROVAL_PENDING`, `APPROVAL_REJECTED`, `APPROVAL_EXPIRED`, `CONTRACT_CONFLICT`, `CONTRACT_NOT_FOUND`, `MISSING_PRICING_EVIDENCE`, `PRICE_ABOVE_APPROVED_RATE`, `NOT_APPLICABLE`, `REVIEW_REQUIRED`, `TECHNICAL_ERROR`.

A missing contract is not an invented price. A technical failure is not compliant. A submitted request is not approved.

Section, subsection, note, down payment, delivery, global discount, and reward lines are `NOT_APPLICABLE`. Combo and expense lines are `REVIEW_REQUIRED`. No contract price is invented for them.

## What blocks confirmation

| Mode | Behavior |
| --- | --- |
| `disabled`, `warning` | Confirmation is allowed. A warning is not recorded as an authorized override. |
| `unconfigured` | A reader who sees below-price, pending, rejected, expired, conflict, missing evidence, review, or technical error is blocked. `CONTRACT_NOT_FOUND` is allowed. Access denied is allowed and stored as review, without prices. |
| `approval_required` | Price problems and uncertain results block. `CONTRACT_NOT_FOUND` is allowed. Access denied blocks. |
| `block` | Anything other than compliant, authorized override, not applicable, or above-rate blocks, including a missing contract. Access denied blocks. |

`COMPLIANT`, `COMPLIANT_AUTHORIZED_OVERRIDE`, `NOT_APPLICABLE`, and `PRICE_ABOVE_APPROVED_RATE` do not block in any mode.

If the policy record itself cannot be read, the line blocks unless it is not applicable.

A confirming user who cannot read the contract cannot prove a product line in `block` or `approval_required`. Contract User is owner-scoped, so a salesperson who does not own the contract sees no approved contract. That is the existing owner rule. It was not widened.

Order headline priority is technical error, conflict, missing evidence, review, rejected, expired, pending, below price, missing contract, above rate, authorized override, then compliant. Not-applicable lines do not hide a commercial line. Exposure is summed only when every valued line shares one comparison currency. Review lines are not inserted as zero. Overpricing is not netted off.
