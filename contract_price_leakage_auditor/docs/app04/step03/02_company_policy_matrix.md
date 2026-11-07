# 02 — Company policy matrix

Date: 2026-10-28.

Model: `cpla.company.policy`.

Every selection defaults to `unconfigured`. A non-default value is a draft candidate. It does not set `operationally_approved`. Business owner for every row below is **UNASSIGNED**. DEC-01 through DEC-08, DEC-11, and DEC-12 stay open.

Missing-state behavior for every policy field: the readiness payload lists the field under `missing`, adds the open-decision codes under `blocking`, and returns `operationally_approved: false`.

| Field | Allowed values | Default | Sensitive read groups | Decision |
| --- | --- | --- | --- | --- |
| `state` | `not_configured`, `draft`, `review_required` (reserved, never assigned), `ready_for_business_review`, `approved_ready` (rejected) | `not_configured` | Readers of the record | Not a business approval. |
| `pricing_date_policy` | `unconfigured`, `order_confirmation`, `delivery`, `invoice`, `contract_specific`, `custom_rule` | `unconfigured` | Record readers | DEC-01. Code `PRICING_DATE_POLICY_REQUIRES_APPROVAL`. Invoice date is not a default. |
| `contract_precedence_policy` | `unconfigured`, `exact_customer`, `customer_group`, `product_specific`, `special_price`, `historical_amendment` | `unconfigured` | Record readers | DEC-02. Overlap stays `CONTRACT_CONFLICT_REVIEW_REQUIRED`. Lowest and highest price are not selections. |
| `customer_coverage_policy` | `unconfigured`, `exact_customer`, `authorized_parent`, `covered_branches`, `covered_subsidiaries`, `customer_group` | `unconfigured` | Record readers | DEC-03. A child contact does not inherit a parent contract. |
| `quantity_basis_policy` | `unconfigured`, `sales_order`, `invoice`, `delivery`, `period_volume`, `customer_group` | `unconfigured` | Record readers | DEC-04. No tier calculation. |
| `discount_approval_policy` | `unconfigured`, `approval_reference_required` | `unconfigured` | Finance reviewer, finance manager, internal auditor, application administrator | DEC-05. No stacking rule and no amount. |
| `fx_basis_policy` | `unconfigured`, `pricing_date`, `order_date`, `invoice_date`, `fixed_rate`, `historical_rate` | `unconfigured` | Same sensitive groups | DEC-06. No rate number. `propose_fixed_rate` always raises. |
| `tax_comparison_policy` | `unconfigured`, `tax_excluded`, `tax_included`, `normalize_required` | `unconfigured` | Same sensitive groups | DEC-07. No tax calculation. |
| `monetary_precision_policy` | `unconfigured`, `company_currency_rounding` | `unconfigured` | Same sensitive groups | Technical draft only. Uses `res.currency.round`. |
| `tolerance_policy` | `unconfigured`, `do_not_suppress` | `unconfigured` | Same sensitive groups | DEC-08. No numeric threshold. |
| `missing_evidence_policy` | `unconfigured`, `review_required` | `unconfigured` | Record readers | Missing evidence stays in review. |

Record readers are Contract Manager, Finance Reviewer (and therefore Finance Manager through implication), Internal Auditor, and Application Administrator. Contract User, Sales Pricing Reviewer, and Recovery Operator have no access row.

Controlled fields that public `write` rejects: `company_id`, `version`, `is_current`, `supersedes_id`, `approved_by`, `requested_on`, `name`, `operationally_approved`, and direct `state`.

`approved_by` is never set. There is no `approval_limit` and no `tolerance_amount`.
