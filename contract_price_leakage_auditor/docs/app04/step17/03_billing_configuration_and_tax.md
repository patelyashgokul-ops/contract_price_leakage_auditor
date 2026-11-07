# Billing configuration and tax

`cpla.recovery.billing.policy` is a company record. Sequences are `CPL-BPO/%(year)s/` and `CPL-BIL/%(year)s/`. No journal, account, tax, fiscal position, or payment term is loaded from XML.

## Required before a document is created

Creating or posting a standalone invoice or debit note requires an approved current policy, a sales journal of the same company, an income account of the same company, and a tax treatment other than `unresolved`. Missing configuration raises `ACCOUNTING_CONFIGURATION_INCOMPLETE`. A journal or account from another company is rejected by `check_company`.

## Tax treatments

| Treatment | Effect |
| --- | --- |
| `unresolved` | Blocks document creation. |
| `untaxed_explicit` | Draft lines have no taxes. Reported principal is the untaxed amount. |
| `taxes_on_policy` | The policy `tax_ids` are set on the draft line. Principal stays the untaxed amount. Tax and gross receivable are stored separately. |

An 18 percent sale tax used in a test is created by that test for the company. It is not a statutory rate and it is not seeded. For a principal of 20000 the tax engine produces tax 3600 and gross 23600. A later partial payment is split by `matched * posted principal / gross`. The whole payment is not reported as principal.

`fiscal_position_id` and `payment_term_id` are optional company fields. When set, they are copied onto the draft. They are not invented when empty.

## Who may post

`_check_accounting_user` requires both `contract_price_leakage_auditor.group_finance_manager` and `account.group_account_invoice`. Either group alone raises `POSTING_AUTHORITY_DENIED`. The superuser is not a member of those groups. When `four_eyes_posting` is true, the commercial requester cannot post or credit the document.
