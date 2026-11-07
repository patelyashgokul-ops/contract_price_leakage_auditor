# 10 — DEV-04 handoff

Date: 2026-10-28.

DEV-04 Customer Contract Master was not started.

## Verified settings model

`cpla.company.policy`.

Required and identity fields: `company_id`, `version`, `is_current`, `state`, `supersedes_id`, `effective_from`, `effective_to`, `change_reason`, `requested_by`, `requested_on`, `approved_by`.

Policy fields, all default `unconfigured`: `pricing_date_policy`, `contract_precedence_policy`, `customer_coverage_policy`, `quantity_basis_policy`, `discount_approval_policy`, `fx_basis_policy`, `tax_comparison_policy`, `monetary_precision_policy`, `tolerance_policy`, `missing_evidence_policy`.

Computed: `name`, `operationally_approved` (always false), `conflict_behavior`, `contract_priority_rule`, `packaging_rule`, `open_decision_text`, `readiness_display`, `company_currency_id`, `revision_ids`.

## Security group XML IDs

Use these records. Do not create `group_cpl_*` duplicates.

- `group_contract_user`
- `group_contract_manager`
- `group_sales_pricing_reviewer`
- `group_finance_reviewer`
- `group_finance_manager`
- `group_recovery_operator`
- `group_internal_auditor`
- `group_app_admin`

Any new confidential model needs `company_id`, an access row per allowed group, and a company record rule in the same change. Do not add an empty-group access row. Do not use `sudo()` to bypass access.

## Approved policy choices

None. Every non-`unconfigured` value is a draft candidate. These codes stay in force:

- `PRICING_DATE_POLICY_REQUIRES_APPROVAL`
- `CONTRACT_CONFLICT_REVIEW_REQUIRED`
- `CONTRACT_SPECIFIC_TERMS_MAY_OVERRIDE_THE_COMPANY_DEFAULT_ONLY_AFTER_A_LATER_APPROVED_CONTRACT`

Do not pick invoice date, the lowest price, or the highest price as a silent default.

## Unresolved decisions

DEC-01 pricing date, DEC-02 precedence, DEC-03 customer coverage, DEC-04 quantity basis, DEC-05 discount stacking, DEC-06 historical FX, DEC-07 tax basis, DEC-08 rounding and tolerance, DEC-11 recovery authority, DEC-12 waiver authority. Owners remain UNASSIGNED. `action_request_activation` must keep refusing until a later accepted phase has an explicit decision and a server-side approval check.

## Master-data readiness API

Call these on `cpla.company.policy`. They do not correct master data.

- `get_configuration_readiness()`
- `validate_customer(partner, company)`
- `validate_product(product, company)`
- `validate_products(products, company)`
- `validate_uom_conversion(from_uom, to_uom)`
- `classify_pricing_unit(product, pricing_uom)`
- `validate_currency(currency)`
- `assess_monetary_difference(difference, currency=None)`
- `classify_exchange_difference(source)`
- `classify_tax_bases(left, right)`
- `check_approval_reference(user)`
- `propose_tolerance(amount)` and `propose_fixed_rate(rate)` currently refuse stored numbers
- `golden_fixture_reference()` returns `audited: false` and `implemented: false`

A contract record must store the company, the customer coverage choice as an explicit contract term later, the product variant, and the price unit. It must not treat `product.template.uom_ids` or a missing `product.packaging` model as a price unit. Shared contacts (`company_id` false) do not inherit a contract.

## Revision strategy

Future contract or audit rows should reference `cpla.company.policy` id and `version`. They must not copy policy onto the contract in a way that rewrites history when the current draft changes. A new policy revision freezes `is_current` on the old row. Do not overwrite frozen rows.

## Tests passed and deferred

Passed on 2026-10-28: CFG-T001–CFG-T050, the three extra policy tests, SMOKE-001–008, SEC-T001–T007, and SEC-T029–T032. Databases: upgrade `cpla_dev01_foundation_20261028` and fresh `cpla_dev03_fresh_20261028`. See `08_automated_test_results.md`.

Deferred: customer contract CRUD, contract versions, historical matching, discount calculation, invoice audit, leakage cases, recovery and waiver workflows, scheduled jobs, dashboards, configuration file import/export, and Odoo 18/20 ports. SEC-T008–T015 were not run under those IDs. Golden fixtures GOLD-FIN-001, GOLD-FIN-003, GOLD-FIN-004, and GOLD-FIN-005 are reference numbers only.

| Fixture | Reference expectation, not an audit result |
| --- | --- |
| GOLD-FIN-001 | `(1150 - 1100) * 500 = 25000` |
| GOLD-FIN-003 | Box 120 USD, 10 pieces, FX 84, discount 5 percent, invoice 950, quantity 100, difference 760 |
| GOLD-FIN-004 | `2400 / 12 = 200`, invoice 190, quantity 100, difference 1000 |
| GOLD-FIN-005 | `(1000 - 900) * 100 = 10000` |

## Customer Contract Master prerequisites

1. Business acceptance of DEV-03 is still pending. Do not treat this handoff as that acceptance.
2. A contract model needs company, customer, product variant, UoM, currency, and dates. It must call the readiness API and refuse a confirmed price while `operationally_approved` is false.
3. Coverage must be an explicit contract term. Child contacts and shared partners do not inherit prices.
4. Ambiguous matches stay `CONTRACT_CONFLICT_REVIEW_REQUIRED`.
5. Do not post accounting entries and do not scan invoices to save a contract.
6. Keep the license marker until a person decides it. Do not add an author.
7. Direct dependencies stay `base` and `product` unless a later prompt accepts `account` or `sale`. `mail` is already installed transitively and must not be used to add chatter on the policy model without a security review.
