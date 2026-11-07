# 07 — Security risks

Date: 2026-10-28.

No critical defect was found in the implemented group foundation. The open items are unimplemented controls and inherited release decisions.

| ID | Severity | Item | Where | Required action | Phase |
| --- | --- | --- | --- | --- | --- |
| R-SEC-01 | High if ignored when models appear | No record rule can exist yet, so the first business model would be unprotected if it shipped without a rule. | Future models | Add the company rule and ACLs in the same change as the model. | DEV-04 and each later model phase |
| R-SEC-02 | High if ignored | Price fields could be exposed through read and aggregation. | No price field today | Server-side field or method checks. | Pricing phases |
| R-SEC-03 | High if ignored | Approval could be confused with group membership. | No approval method | Separate method checks. Do not invent DEC-11 amounts. | DEV-16 |
| R-SEC-04 | Medium | Superuser and database owner bypass record rules. | Odoo platform | Documented. Do not claim otherwise. | Ongoing |
| R-SEC-05 | Medium | `account` portal templates could show a price if a later view inherits them. | Not applicable while `account` is not a dependency | Review portal views before depending on `account`. | Before invoice audit |
| R-SEC-06 | Medium | Odoo 18 uses `res.groups.category_id` and `res.users.groups_id`. This XML uses `res.groups.privilege` and `res.users.group_ids`. | Odoo 19 source verified. Odoo 18 source differs. | Do not copy this XML to Odoo 18. | Later port |
| R-SEC-07 | Medium | Odoo 20 still has `res.groups.privilege`, but the privilege label is Scope and base access is `ir.access`, not `ir.model.access`. `ir.rule` was not found under the Odoo 20 base models path checked on 2026-10-28. | Local Odoo 20 tree, static read only | Re-test security on Odoo 20 before any port. | Later port |
| R-SEC-08 | Low | License and author are still unset as legal identity. | `__manifest__.py` | `BLOCKER_LICENSE_DECISION_REQUIRED`. Not a group defect. | Packaging |
| R-SEC-09 | Low | No Git history. | Workspace | Provenance remains unverified. | Repository owner |

Owner of every row: UNASSIGNED.

No public ACL, cross-company business row, approval bypass, unsafe `sudo()`, or export exists in this addon today.
