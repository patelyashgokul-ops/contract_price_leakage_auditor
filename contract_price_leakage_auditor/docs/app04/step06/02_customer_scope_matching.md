# 02 — Customer scope matching

The only customer scope that can be approved today is the exact `partner_id` on an approved version.

`commercial_partner_id` does not widen a contract. A child contact or branch does not inherit the parent agreement. A shared partner record does not share another company's price.

Extra `covered_partner_ids` still block submission and approval while DEC-03 is open. A draft that lists a branch is not read as coverage. APP-003 therefore ends as no applicable contract, not as a match.

There is no customer-group model. If the request carries `customer_group_ref` and an exact contract matches, the exact contract is returned and the group is not consulted. If the group reference is set and no exact contract matches, the status is `HISTORICAL_EVIDENCE_REVIEW_REQUIRED` with reason `customer_group_not_approved`. Current `parent_id` is not historical membership.

A contract whose customer is the branch itself is an exact-customer match for that branch. It does not cover the parent or a sibling branch.
