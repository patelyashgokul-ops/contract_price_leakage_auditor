# Multi-company security

Global record rules, with no groups, domain `[('company_id', 'in', company_ids)]`, on:

- `cpla.invoice.source.map`
- `cpla.invoice.source.allocation`
- `cpla.invoice.source.verification`
- `cpla.invoice.source.verification.line`

XML ids: `cpla_invoice_source_map_company_rule`, `cpla_invoice_source_allocation_company_rule`, `cpla_invoice_source_verification_company_rule`, `cpla_invoice_source_verification_line_company_rule`.

Access rows:

| Group | Map and allocation | Verification wizard |
| --- | --- | --- |
| Contract user | Read | None |
| Contract manager | Read, create, write, no unlink | None |
| Finance reviewer | Read | None |
| Finance manager | Read, create, write, no unlink | Full CRUD |
| Internal auditor | Read | None |

No public, portal, salesman, application-administrator, sales-pricing-reviewer, or recovery-operator row. The abstract service has no access row.

`map_move` checks invoice read access and requires the invoice company to be in `env.companies` unless the environment is superuser. A linked sales line in another company is `WRONG_COMPANY_SOURCE` and is not allocated. A documentary split of a foreign sales line is rejected. A shared customer does not open the other company's invoice or contract.

The menu Invoice Source Evidence is under Customer Contracts for contract user, contract manager, finance reviewer, and finance manager. The auditor is not on that menu. The auditor can open Source Evidence from the invoice smart button, which also checks map read access. Application administrators are not on the menu and have no map access row.

Contract price fields on the allocation are not granted to a plain internal user. The tests read `approved_unit_price_exact` as that user and get `AccessError`. Export of the map by a contract user without `base.group_allow_export` raises `UserError`.

No `sudo(` and no `.execute(` appear in `models/invoice_source.py`.
