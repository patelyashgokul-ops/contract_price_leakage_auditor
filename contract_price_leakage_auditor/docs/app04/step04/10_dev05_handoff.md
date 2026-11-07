# 10 — DEV-05 handoff

Date: 2026-10-28.

DEV-05 was not started. Do not treat a `ready_for_review` contract as an approved historical price.

## Technical names

| Item | Value |
| --- | --- |
| Header | `cpla.customer.contract` |
| Line | `cpla.customer.contract.line` |
| Evidence | `cpla.customer.contract.evidence` |
| Policy reference | `cpla.company.policy` |
| Sequence code | `cpla.customer.contract` |
| Sequence XML ID | `contract_price_leakage_auditor.seq_cpla_customer_contract` |

Field dictionary: `02_contract_field_dictionary.md`.

## Lifecycle states

`draft`, `ready_for_review`, `cancelled`.

Do not reuse `ready_for_review` as `approved`. Add approval and version states, or a separate version model, in DEV-05. `audit_authoritative` must stay false until that phase has an approved snapshot.

Actions to keep: `action_submit_for_review`, `action_cancel`, `action_reset_to_draft`. State must remain unreachable through public `write`.

## Security groups

| XML ID | Contract business right in DEV-04 |
| --- | --- |
| `contract_price_leakage_auditor.group_contract_user` | Own drafts. Not approval. |
| `contract_price_leakage_auditor.group_contract_manager` | Company scope. Reset to draft. Not approval. |
| `contract_price_leakage_auditor.group_finance_reviewer` | Read in active companies. |
| `contract_price_leakage_auditor.group_finance_manager` | Read in active companies. Implies reviewer only. |
| `contract_price_leakage_auditor.group_internal_auditor` | Read in active companies. |
| `contract_price_leakage_auditor.group_sales_pricing_reviewer` | No contract access. |
| `contract_price_leakage_auditor.group_recovery_operator` | No contract access. |
| `contract_price_leakage_auditor.group_app_admin` | Policy configuration only. No contract write and no approval. |

Company rules are global: `[('company_id', 'in', company_ids)]` on header, line, and evidence. Contract User is limited to `owner_id`. Contract Manager adds `(1, '=', 1)`. Do not attach a wide group rule to auditor, finance, or application administrator. Combined membership with Contract User must stay owner-limited.

## Dates and prices

- `valid_from` and `valid_to` are proposed dates. Both are required before review. `valid_from <= valid_to`. Open-ended is not approved.
- `currency_id` is the price currency. `company_currency_id` is separate.
- `price_unit` is an explicit amount. It is not the product list price.
- `uom_id` is the pricing unit. Review accepts only the product default unit.
- Do not convert currency or units in DEV-05 unless a later approved phase owns that math. FX is DEV-08. Unit money conversion is DEV-07.

## Evidence

Files live on `cpla.customer.contract.evidence` through `datas` (`attachment=True`). They freeze when the header leaves draft. DEV-05 should snapshot this link on the approved version. Do not describe the current rows as a legal archive.

## Tests and fixtures

Module: `tests/test_customer_contract.py`.

Disposable database name used for DEV-04: `cpla_dev04_20261028`.

Illustrative fixtures, not invoice audits:

| ID | What the test stores |
| --- | --- |
| CONTRACT-REF-001 | Company ABC India, customer XYZ Manufacturing, product Industrial Bearing, 1,200 per the product default unit, 2026-07-01 through 2026-12-31. Currency is INR when that currency is already active, otherwise the company currency. INR is not activated. Submit waits for a file. |
| CONTRACT-REF-002 | USD 100. Company currency unchanged. No currency rate inserted. USD active flag unchanged. |
| CONTRACT-REF-003 | Company A price 1,200 in the company currency. Company B price AED 50. Company A user cannot read the Company B contract. |
| CONTRACT-REF-004 | 2026-12-31 through 2026-07-01 is rejected. |
| CONTRACT-REF-005 | Valid lines without a file stay draft. |
| CONTRACT-REF-006 | One customer, Bearing A 1,200, Bearing B 1,400, Bearing C 1,600, one company. |

Passed on the green runs in file 07: CTH-T001–T015, CTL-T001–T018, LFC-T001–T014, SEC04-T001–T015, REG04-T001 and REG04-T003–T010, plus the overlap, currency-change, DEC-03, archived-product, and non-current-policy tests.

Deferred:

| Item | Position |
| --- | --- |
| REG04-T002 from a preserved DEV-03 database | NOT_EXECUTED. `cpla_dev01_foundation_20261028` and `cpla_dev03_fresh_20261028` were already dropped. |
| Customer smart button | Not built. |
| Browser click-through | Not run. `get_view` covered list, form, and search. |
| Odoo 18 and Odoo 20 | Not converted and not tested. |
| Invoice audit of the golden fixtures | Out of scope. |

## Open business decisions

Still unapproved, owners UNASSIGNED:

DEC-01 pricing date, DEC-02 precedence, DEC-03 customer coverage, DEC-04 quantity basis, DEC-05 discount stacking, DEC-06 historical FX, DEC-07 tax basis, DEC-08 rounding and tolerance, DEC-11 recovery authority, DEC-12 waiver authority.

Also open, and not invented here:

- Whether a zero price may be a real selling price.
- Whether an open-ended contract may be approved.
- Whether a packaging unit may be an approved price unit.
- Physical deletion of a never-submitted draft. Current behavior is refuse `unlink`.
- License (`BLOCKER_LICENSE_DECISION_REQUIRED`).

## Versioning recommendations

- Keep `cpla.customer.contract` as the working agreement. Add a version model that copies header, lines, currency, UoM, and evidence links at approval time.
- Do not rewrite `reference` when a version is approved.
- Do not change `company_id` or `partner_id` on an approved version.
- Do not let a draft write replace an approved snapshot.
- Reset-to-draft may apply only before approval, or only by creating a new draft revision. Do not silently edit the approved copy.
- Amendments should be new version rows with a predecessor, not an in-place price overwrite.
- Overlap warning stays a warning until DEV-06 has an approved precedence rule.
- Quantity tiers should be children of the line, not a unique constraint on product alone.
- Application Administrator must not gain approval authority by default.
- Self-approval and blanket approval stay out of scope until a human policy names the authority.

## DEV-05 acceptance prerequisites

- This handoff and a green DEV-04 suite.
- An approved definition of who may approve, including whether the owner may approve their own contract.
- A decision that `ready_for_review` is the input to approval and is not itself approval.
- A version identity that survives later amendments.
- Company isolation on every new version and amendment row.
- No invoice matching, tier math, FX, recovery, or waiver inside DEV-05.
