# Approval authority matrix

Contract-version approval is unchanged. A Contract Manager or a Finance Manager approves a version. The owner and the submitter cannot approve it. Application Administrator still has one access row, on company policy, and cannot approve a discount.

Discount-request approval is a separate check on `cpla.discount.approval`.

## Who can do what

| Action | Who | Server check |
| --- | --- | --- |
| Create a draft request | Contract user, for a version in their company. Requester is `env.user`. | Client values for requester, approver, state, baseline, exposure, and snapshot are rejected. |
| Submit | The requester, or a contract manager. | Reason, evidence, approved version, customer equal to the version customer, and a product on a version line. An override also needs both sales references, a proposed price, a positive quantity, a currency, and a unit. |
| Approve | Finance manager who is not the requester and not the submitter. | Group, company, limit, currency, unit, conflict, and superseded-version checks. Approver is `env.user`. `approved_at` is `fields.Datetime.now()`. |
| Reject | Finance manager, with a reason. | A finance manager may write only `rejection_reason` while the request is submitted. |
| Cancel | Draft or submitted, under the request write rules. | State becomes `cancelled`. The concession is not applied. |
| Configure the limit | Contract user, on a draft version. | An empty limit blocks later approval. It does not grant unlimited approval. |

A user who holds both Contract User and Finance Manager cannot approve their own request. `test_app09_t005_combined_role_cannot_self_approve` passed. A Contract Manager, a Finance Reviewer, and an Application Administrator cannot call `action_approve`. The button is limited to the finance manager group, and the method checks the group again.

## State

`draft`, `submitted`, `approved`, `rejected`, `cancelled`, `superseded`, `revoked`.

Commercial `effective_from` is separate from the approval timestamp. A future effective date can be approved and stays unused until the pricing date reaches it. An effective date before today requires `retroactive_discount_authority` = `explicitly_allowed` on the version. The version field `retroactivity_policy` stays `not_authorized`. That field still blocks a retroactive contract amendment.

## Limit check

Before approval the server:

1. Locks the version and the request.
2. Returns immediately when the request is already approved, without a second event.
3. Refuses a superseded version. The request stays submitted.
4. Builds the baseline with `baseline_only=True`, so approved contractual concessions count and pending requests do not.
5. Refuses when the baseline status is not authoritative or the price is missing.
6. Compares the reduction with the limit stored on the version.
7. Refuses a second exclusive concession for the same scope when precedence is missing, and a second override for the same sales reference and line reference.
8. Writes the snapshot and the limit snapshot, then records one `approved` event.

The snapshot is the authority used later. Tightening the version limit after approval does not change an approval that was already granted.

## Exposure

Override exposure is (approved adjusted baseline − proposed unit price) × verified quantity, when both prices share currency and unit and the difference is positive.

Executed case: baseline 1,150, proposed 1,100, quantity 500, exposure 25,000. The baseline is the special price, not the gross 1,200. The approver stored on the request was the finance user, not the requester.

A stated-exposure limit also refuses a quantity above `authority_exposure_quantity_exact`. Cross-currency exposure is not compared without a rate. A request unit that differs from the version-line unit is refused. No conversion is invented at approval time.
