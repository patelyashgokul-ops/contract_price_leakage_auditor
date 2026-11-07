# 09 — Multi-company security

Callers must have one of: Contract User, Contract Manager, Finance Reviewer, Finance Manager, Internal Auditor. Sales Pricing Reviewer, Recovery Operator, and Application Administrator receive `AccessError`.

The company on the request must be in `env.companies`. The search domain sets the line company and the version company before record rules apply. There is no `sudo(`.

Wizard access is read, write, create, and unlink for the five roles above. That satisfies the contract-user access test, which requires full rights on models other than policy, header, version, and event. The auditor remains read-only on commercial records. The wizard is the only auditor row with write, create, and unlink, and it is a transient check.

Two global rules apply together: company in the active companies, and `create_uid` is the current user. They are not attached to finance, auditor, sales, recovery, or administrator groups.

The menu Applicability Check is under Contracts, sequence 40. It is not named Customer Pricing Contracts or Configuration. Application Administrator, sales, and recovery do not receive it.

Company A does not resolve Company B. A shared partner or a multi-company user does not change that. A product assigned to Company B cannot be used for a Company A request. Export and `read_group` from Company A do not return Company B prices.

The diagnostic form was checked with `get_view` in the test transaction. A browser session was not opened.
