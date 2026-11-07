# 01 — Contract master architecture

Date: 2026-10-28.

Module: `contract_price_leakage_auditor` `19.0.1.2.0`.

Odoo 19 Community is the master. This phase does not convert the addon to Odoo 18 or Odoo 20.

A customer contract in this phase is a company-owned draft of negotiated product prices. `ready_for_review` means the draft is complete enough for a person to review. It is not commercial approval, not an active price, and not an invoice-audit source. `audit_authoritative` is a computed flag and is always false.

## Models

| Technical name | Class | Role |
| --- | --- | --- |
| `cpla.customer.contract` | `CustomerContract` | Agreement header. |
| `cpla.customer.contract.line` | `CustomerContractLine` | One negotiated unit price for one product variant and one pricing unit. |
| `cpla.customer.contract.evidence` | `CustomerContractEvidence` | File and metadata linked to one header. |
| `cpla.company.policy` | unchanged | Current company policy reference. Not modified in this phase. |

The names do not start with `cpla.contract`. That prefix stays forbidden so later audit models are not confused with this draft master.

No model was added for versions, amendments, quantity tiers, invoice findings, leakage cases, recoveries, or waivers.

## Relationships

```
res.company
    └── cpla.customer.contract (required company_id)
            ├── res.partner partner_id (exact customer)
            ├── res.partner commercial_partner_id (related, identity only)
            ├── res.partner covered_partner_ids (proposal; blocks review)
            ├── res.currency currency_id (price currency)
            ├── res.currency company_currency_id (related)
            ├── res.users owner_id
            ├── cpla.company.policy policy_id
            ├── cpla.customer.contract.line line_ids
            │       ├── product.product product_id
            │       ├── product.template product_tmpl_id (related)
            │       ├── uom.uom uom_id
            │       └── res.currency currency_id (related, stored)
            └── cpla.customer.contract.evidence evidence_ids
                    └── ir.attachment (Binary attachment=True on datas)
```

The header owns the commercial agreement. The line owns the product price. The line company is a stored related field from the header. A caller cannot assign a different company on the line or on the evidence.

`_check_company_auto` is set on all three models. `check_company=True` is used on the customer, covered partners, policy, parent contract, and product. It is not used on `res.users` or `res.currency`. Shared contacts and shared products (`company_id` false) stay allowed. A partner or product owned by another company is rejected by Odoo's company check with `UserError`.

## Company ownership

Every contract requires `company_id`. The default is the active company. On create, a non-superuser company must be in both `user.company_ids` and the active company selection (`env.companies`). The company cannot be changed after create. There is no shared-contract policy.

## Reference

`ir.sequence` XML ID `seq_cpla_customer_contract`, code `cpla.customer.contract`, prefix `CPL/%(year)s/`, padding 5, implementation `standard`, `company_id` false, `noupdate="1"`.

Numbers come from `next_by_code`. The module does not use `max(reference)+1`. The sequence is not gapless. The same sequence is shared across companies, so values do not restart per company. Uniqueness is still enforced per company by `UNIQUE(company_id, reference)` and a Python check before create. The reference is required, `copy=False`, and a later write of a different reference is rejected. Existing references are not regenerated.

## Future versioning

DEV-05 can add historical versions without renaming these models. The stable reference, frozen submitted terms, and evidence rows are the inputs. This phase does not store an approved snapshot, a superseding link, or an amendment. `write_date` is ordinary Odoo traceability. It is not a legal price history.

Quantity tiers are not stored. The line uniqueness key is `(contract_id, product_id, uom_id)`, not product alone, so a later child tier model can hang from the line. A second line with the same variant and a different unit can be stored. Review still accepts only the product's default unit. That limitation is intentional. See file 04.

## What this phase does not do

No pricing evaluation, no contract precedence choice, no foreign-exchange conversion, no invoice comparison, no leakage case, no recovery, no waiver, no accounting write, no cron, and no dashboard.
