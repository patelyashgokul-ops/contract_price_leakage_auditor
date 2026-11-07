# Segregation of duties

Authority is `_in_group`. It returns false for the superuser and for `env.su`, then checks `all_group_ids`. `res.users.has_group` is not used for finance actions, because that method returns true for every group when the user is the superuser.

| Actor | What they can do |
| --- | --- |
| Contract user or manager | Read finance records in their companies. They do not approve. |
| Finance reviewer | Prepare, submit, review, propose, and request evidence. They approve a level only when that level names `finance_reviewer` and the other gates pass. |
| Finance manager | The reviewer actions, policy maintenance, and a level that names `finance_manager`. The manager group implies the reviewer group, so one manager can approve a reviewer level. |
| Internal auditor | Read and, with `base.group_allow_export`, export. No approval and no policy write. |
| App admin, sales pricing reviewer, recovery operator | No finance menu and no finance approval. Admin model access stays the company policy row only. |
| Technical superuser | Not a finance approver. Prepare and approve raise `APPROVAL_MATRIX_MISSING`. |

When `four_eyes_required` is true (the default):

- `requested_by_id` cannot approve.
- The case `submitted_by_id` cannot approve.
- A user who already has an approved event on the package cannot approve the next level.

Holding both the reviewer and the manager groups does not skip a level. The actor stored on the event is `env.user`. Client fields `approved_by`, `approved_at`, `approval_level`, and `company_id` are not accepted as proof.

The case method `action_return_for_rework` still uses `has_group` for its own finance-actor check. Finance validation methods do not.
