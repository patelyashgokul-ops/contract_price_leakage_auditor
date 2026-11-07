# 02 — Contract field dictionary

Date: 2026-10-28.

Standard Odoo fields `create_uid`, `create_date`, `write_uid`, and `write_date` are present and are not duplicated. There is no `active` flag. Archived is not used as a stand-in for expired or approved.

Access is the model ACL plus the record rules in file 06. Sensitive policy fields stay on `cpla.company.policy` and are not copied here.

## `cpla.customer.contract`

| Field | Type | Required | Default | Rule |
| --- | --- | --- | --- | --- |
| `reference` | Char, indexed | Yes | Sequence on create | Immutable after assignment. Unique with `company_id`. |
| `name` | Char | No | Empty | Agreement title. Not the stable identifier. |
| `company_id` | Many2one `res.company`, indexed | Yes | Active company | Cannot change after create. |
| `partner_id` | Many2one `res.partner`, indexed, `check_company` | No on draft | Empty | Exact customer. Required before review. |
| `commercial_partner_id` | Many2one, related stored, indexed | Computed | From customer | Identity context only. Does not expand coverage. |
| `covered_partner_ids` | Many2many `res.partner`, `check_company` | No | Empty | Any row blocks review while DEC-03 is open. |
| `currency_id` | Many2one `res.currency` | No on draft | Empty | Price currency. Required before review. Inactive currency blocks review. No rate is created. |
| `company_currency_id` | Many2one, related | Computed | Company currency | Independent of `currency_id`. |
| `valid_from` | Date, indexed | No on draft | Empty | Required before review. |
| `valid_to` | Date, indexed | No on draft | Empty | Required before review. Open end is not an approved policy. |
| `state` | Selection, indexed | Yes | `draft` | `draft`, `ready_for_review`, `cancelled`. Changed only by actions. |
| `owner_id` | Many2one `res.users`, indexed | Yes | Current user | Must belong to the company and have Contract User (a manager implies that group). |
| `external_reference` | Char | No | Empty | Customer agreement number. |
| `description` | Text | No | Empty | Commercial notes. |
| `policy_id` | Many2one `cpla.company.policy`, `check_company`, indexed | No on draft | Empty | Must be the current revision of the same company before review. |
| `policy_version` | Integer, related | Computed | Policy version | Read-only. |
| `line_ids` | One2many lines | No on draft | Empty | At least one line before review. |
| `evidence_ids` | One2many evidence | No on draft | Empty | At least one file before review. Not copied. |
| `reset_reason` | Text | No | Empty | Required before a manager returns a review submission to draft. |
| `cancel_reason` | Text | No | Empty | Optional note. |
| `overlap_warning` | Text, computed | Computed | False | Visibility only. Does not choose a price. |
| `review_blocker_text` | Text, computed | Computed | False | Current readiness gaps. |
| `audit_authoritative` | Boolean, computed | Computed | False | Always false. Not stored. |

Date constraint: when both dates are set, `valid_from <= valid_to`. Invalid ranges raise `ValidationError`. Dates are not swapped.

Currency write: if lines exist and `currency_id` would change, `UserError`. Amounts stay as entered. No conversion.

Owner constraint: company membership and Contract User group. Odoo runs constraints on a sudo recordset, so the check does not return early when `env.su` is set. A finance reviewer, auditor, or application administrator cannot be the owner.

A Contract User cannot reassign `owner_id`. A Contract Manager can reassign it to another eligible user in the company.

## `cpla.customer.contract.line`

| Field | Type | Required | Default | Rule |
| --- | --- | --- | --- | --- |
| `contract_id` | Many2one header, `check_company` | Yes | Parent | Cannot be moved to another contract. |
| `company_id` | Many2one, related stored, indexed | Computed | Header company | Caller value is discarded when it matches. A different company is rejected. |
| `sequence` | Integer | No | 10 | Display order. |
| `product_id` | Many2one `product.product`, `check_company` | Yes | Empty | Price identity is the variant. |
| `product_tmpl_id` | Many2one, related stored | Computed | Variant template | Not a second price identity. |
| `name` | Char | No | Onchange display name | Description. Not a price. |
| `price_unit` | Monetary | Yes | None | No default from list price, cost, pricelist, or last sale. Negative values are rejected on save. |
| `currency_id` | Many2one, related stored | Computed | Header currency | Read-only. |
| `uom_id` | Many2one `uom.uom` | Yes | Onchange product unit | Incompatible family, inactive unit, or non-positive factor is rejected on save. |
| `external_line_reference` | Char | No | Empty | Price-schedule reference. |
| `notes` | Text | No | Empty | Conditions. Not a tier. |

SQL constraint: `UNIQUE(contract_id, product_id, uom_id)`. The same check also runs in Python before insert so a duplicate raises `ValidationError` without aborting the test transaction on the SQL error alone.

## `cpla.customer.contract.evidence`

| Field | Type | Required | Default | Rule |
| --- | --- | --- | --- | --- |
| `contract_id` | Many2one header, `check_company` | Yes | Parent | Cannot be moved. |
| `company_id` | Many2one, related stored | Computed | Header company | Cannot be reassigned. |
| `name` | Char | Yes | Empty | Document title. Also the download filename. |
| `document_type` | Selection | Yes | `signed_agreement` | `signed_agreement`, `purchase_agreement`, `price_schedule`, `confirmation`, `other`. |
| `source_reference` | Char | No | Empty | Source document number. |
| `description` | Text | No | Empty | Evidence note. |
| `datas` | Binary, `attachment=True` | Yes | Empty | Stored as `ir.attachment`. `public` stays false. |

`create_uid` and `create_date` are the upload user and time.

## Future-phase ownership

| Concern | Owner |
| --- | --- |
| Approved version, amendment, supersession | DEV-05. Not these states. |
| Which invoice customer matches a contract | DEV-06. |
| Quantity tiers and UoM money conversion | DEV-07. |
| Historical exchange rates | DEV-08. |
| Invoice audit, leakage, recovery, waiver | Later phases. Not these models. |
