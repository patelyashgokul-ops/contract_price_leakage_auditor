# 04 — Financial approval security

Date: 2026-10-28.

No approval workflow, approval amount, or approval model was created.

## Categories that need a later check

| Category | Provisional actor | Not sufficient |
| --- | --- | --- |
| Contract approval | Contract Manager, after a method exists | Contract User, Application Administrator |
| Amendment approval | Same gate as contract approval | A write on the version |
| Special discount approval | Policy still open | Sales Pricing Reviewer create access |
| Leakage validation | Finance Manager | Finance Reviewer |
| Recovery approval | Finance Manager | Recovery Operator |
| Waiver approval | Separate from recovery approval. DEC-11 is open. | Recovery Operator, self-approval |
| Settlement authorization | Not defined. No accounting post from this module. | Any APP 04 group |

CRUD on a future model is not approval. A group that can write a draft cannot approve it unless the method checks a separate approval right.

## Checks every later approval method must perform

The method runs as the current user. It does not accept a caller-supplied user, role name, company, amount, or target state as proof.

It must consider:

- The authenticated user and the user's groups from the server.
- The record company and the user's allowed companies.
- The approval category.
- The approved limit for that category, once a policy exists.
- Whether the user created or requested the same concession.
- The current state.
- Currency normalization, which is not decided.
- Required evidence.
- Separation of duties.

There is no numeric limit in this module. DEC-11 is unapproved. Inventing an amount would be a business rule, not a security control.

## Self-approval

The user who requests a restricted discount, waiver, or recovery concession cannot be the only approver of that request. A later test must call the method as that user and receive a rejection. SEC-T019 is planned.

Finance write access does not imply that approval. Recovery Operator does not imply Finance Manager. Tests SEC-T030 and SEC-T031 cover that group split now. They do not execute an approval method.

## Direct calls

When an approval method exists, RPC and ORM calls use the same check as the form button. Hiding the button is not the control. SEC-T021 is planned.

## Extension point

The later policy belongs with the approval workflow, not in a guessed settings record. DEV-03 must not add a silent monetary default to fill DEC-11.
