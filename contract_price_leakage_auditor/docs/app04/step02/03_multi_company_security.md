# 03 — Multi-company security

Date: 2026-10-28.

No APP 04 model has `company_id`. Company isolation for contracts and finance is not implemented. This file is the rule for the phase that creates those models.

## Company ownership

Confidential contract, version, price, finding, validation, recovery, waiver, dispute, evidence, and batch records get a required `company_id`.

`company_id` empty is not a shared contract. A missing company is invalid for those models. Shared products and customers stay the standard Odoo records. They are not copied into one company just so a contract can point at them.

## Allowed companies and the active company

`res.users.company_ids` is the set of companies a user may enter. `company_id` is the default company. The context key `allowed_company_ids` is the active subset. Odoo record-rule evaluation uses `company_ids` from `env.companies`, and the cache key includes `allowed_company_ids`.

A test user created for Company A, with only that company on `company_ids`, keeps the same APP 04 groups when the environment context is switched to Company B. That check is `test_company_context_does_not_change_group_membership`. It does not prove record isolation. SEC-T008 through SEC-T015 stay planned.

## Read access is not a cross-company link

A user who may read Company A and Company B may read both companies' rows. That user must still be blocked from connecting a Company B contract to a Company A invoice, and from connecting a Company B recovery to a Company A payment.

The later models use Odoo 19 company consistency where the relation is company-owned:

- `_check_company_auto = True` on the model.
- `check_company=True` on relational fields whose target is company-owned and must match.

Do not set `check_company=True` on a partner or product field when that target is a normal shared record. Doing so would reject valid shared customers and products.

Planned consistency checks:

1. Contract version company matches the contract company.
2. An invoice may be matched only to a contract of the same company.
3. A leakage finding stores the invoice company.
4. A recovery case stores that same company and does not point at another company's invoice.
5. A payment or accounting link uses the accounting document's company.
6. A user with two companies does not get a match across those companies from the allowed-company list alone.

Consolidated reporting needs a later, explicit permission. It must not be implemented by removing the company rule.

## Record rule to add with the first confidential model

Global `ir.rule` on that model:

- Domain `[('company_id', 'in', company_ids)]`.
- Read, create, write, and unlink all true.
- No group on the rule, so it applies to every non-superuser.
- No second global rule that contradicts it.

ACLs still list the roles. The rule does not grant access by itself.

## Test companies

`ABC India` and `ABC UAE` are names for disposable test fixtures only. The executed test creates them inside a transaction and rolls them back. They were not written as master data.

## Background jobs

No cron exists. A later job must receive an explicit company and must not use `sudo()` to cross companies. SEC-08 remains planned for DEV-18.
