# 03 — Customer, product, and unit-of-measure validation

Date: 2026-10-28.

Validators are methods on `cpla.company.policy`. They return a dictionary. They do not write partners, products, units, currencies, or taxes.

Classifications: `VALID`, `WARNING`, `REVIEW_REQUIRED`, `BLOCKING_CONFIGURATION_ERROR`.

Every payload includes `operationally_approved: false`.

## Customer — `validate_customer(partner, company)`

| Condition | Classification | Code |
| --- | --- | --- |
| Partner or company missing | `BLOCKING_CONFIGURATION_ERROR` | `CUSTOMER_OR_COMPANY_MISSING` |
| Record not readable | `BLOCKING_CONFIGURATION_ERROR` | `CUSTOMER_NOT_ACCESSIBLE` |
| `company_id` set and not in `company.parent_ids` | `BLOCKING_CONFIGURATION_ERROR` | `WRONG_COMPANY_CUSTOMER` |
| Archived | `REVIEW_REQUIRED` | `ARCHIVED_CUSTOMER_RETAINED` |
| Child contact or commercial partner different from the record | `REVIEW_REQUIRED` | `CHILD_CONTACT_DOES_NOT_INHERIT_CONTRACT` |
| Empty `company_id` (shared contact) | `WARNING` | `SHARED_CUSTOMER_NO_CONTRACT_INHERITANCE` |
| Company-owned customer with no parent | `VALID` | `CUSTOMER_IDENTITY_OK` |

`parent_ids` on `res.company` includes the company itself, so the same company is compatible. An empty partner `company_id` is shared visibility under Odoo's multi-company rules. It is not rejected, and it does not grant contract inheritance. `inherits_parent_contract` and `coverage_approved` are false in every result. Archived customers are not deleted.

## Product — `validate_product` and `validate_products`

The direct dependency `product` supplies `product.template` and `product.product`. `product` itself depends on `base`, `mail`, and `uom`, so `mail` and `uom` install with this module. APP 04 does not depend on `account` or `sale`, and it does not inherit `mail.thread`.

| Condition | Classification | Code |
| --- | --- | --- |
| Product or company missing, or unsupported model | `BLOCKING_CONFIGURATION_ERROR` | `PRODUCT_OR_COMPANY_MISSING` or `PRODUCT_MODEL_UNSUPPORTED` |
| Not readable | `BLOCKING_CONFIGURATION_ERROR` | `PRODUCT_NOT_ACCESSIBLE` |
| Template company outside `company.parent_ids` | `BLOCKING_CONFIGURATION_ERROR` | `WRONG_COMPANY_PRODUCT` |
| Template with `product_variant_count` other than 1 | `REVIEW_REQUIRED` | `AMBIGUOUS_PRODUCT_VARIANT` |
| Archived | `REVIEW_REQUIRED` | `ARCHIVED_PRODUCT_RETAINED` |
| No `uom_id` | `BLOCKING_CONFIGURATION_ERROR` | `MISSING_UOM` |
| Empty template `company_id` | `WARNING` | `SHARED_PRODUCT_NO_CONTRACT_INHERITANCE` |
| Same-company variant with a default unit | `VALID` | `PRODUCT_IDENTITY_OK` |

`VALID` means the identity can be used later. It does not select a contract price. Archived products are not deleted or rewritten. `validate_products` maps `validate_product` and does not batch-write.

## Units — `validate_uom_conversion`

Odoo 19 `uom.uom` uses `relative_uom_id` and `relative_factor`. `_compute_quantity` multiplies factors and does not reject a different family, so this method requires `_has_common_reference` first.

| Condition | Classification | Code |
| --- | --- | --- |
| Missing unit | `BLOCKING_CONFIGURATION_ERROR` | `MISSING_UOM` |
| `relative_factor` missing, zero, or negative | `BLOCKING_CONFIGURATION_ERROR` | `INVALID_CONVERSION_FACTOR` |
| Inactive unit | `BLOCKING_CONFIGURATION_ERROR` | `INACTIVE_UOM` |
| No common reference | `BLOCKING_CONFIGURATION_ERROR` | `INCOMPATIBLE_UOM` |
| Shared reference and a positive quantity | `VALID` | `UOM_CONVERSION_OK` |

Inactive units are not activated.

## Packaging — `classify_pricing_unit`

`product.template.uom_ids` is the Odoo 19 Packagings list. Those rows are extra `uom.uom` records. `product.packaging` is not in this Community build.

| Condition | Classification | Code |
| --- | --- | --- |
| Pricing unit equals the product `uom_id` | `VALID` | `DEFAULT_PRICE_UOM` |
| Pricing unit is only on `uom_ids` | `REVIEW_REQUIRED` | `PACKAGING_UOM_NOT_PRICE_UNIT` |
| Compatible unit that is not the default | `REVIEW_REQUIRED` | `EXPLICIT_UOM_NOT_THE_DEFAULT_PRICE_UNIT` |
| Incompatible or invalid conversion | The conversion result | Conversion code |

A packaging size is not invented. No invoice leakage finding is created.
