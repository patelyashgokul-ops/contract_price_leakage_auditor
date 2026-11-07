# 02 — Environment and Community dependencies

Master evidence: `C:\PycharmProjects\odoo19\odoo-19.0\odoo\release.py` version info `(19, 0, 0, final, 0, '')`, license LGPL-3.

Odoo 18.0 final and Odoo 20.0 final were inspected separately. A fact for one series is not assumed for another. No dependency was installed. No application code was refactored.

Classifications: `VERIFIED_AVAILABLE`, `VERIFIED_MISSING`, `REQUIRES_VALIDATION`, `OPTIONAL`, `NOT_APPLICABLE`.

## Dependency table

| Dependency | Required purpose | Community availability | Existing repository evidence | Risk |
| --- | --- | --- | --- | --- |
| `base` | Users, companies, currency, cron, groups | VERIFIED_AVAILABLE on 18, 19, 20 | `odoo/addons/base`. `res.company`, `res.users`, `res.currency`, `ir.cron` (`odoo/addons/base/models/ir_cron.py`), `base.group_user` in `base_groups.xml` | Low for presence. APP 04 still has no manifest. |
| `mail` | Chatter and activities where a later phase justifies them | VERIFIED_AVAILABLE. Odoo 19 `mail` 1.19 depends on `base`, `base_setup`, `bus`, `web_tour`, `html_editor`. Odoo 18 `mail` is 1.18 with the same depends. Odoo 20 `mail` is 1.19. | `addons/mail/models/mail_activity.py` `_name = mail.activity` | OPTIONAL until a phase needs activities. Direct dependency is justified for chatter. Already transitive through `product`. |
| `uom` | Quantity normalization | VERIFIED_AVAILABLE. LGPL-3. Depends `base`. | See UoM break below. | High port risk. Not a missing module. |
| `product` | Products, variants, pricelists | VERIFIED_AVAILABLE 1.2 on 18, 19, 20. Depends `base`, `mail`, `uom`. | `product.pricelist`, `product.pricelist.item`, `res.partner.property_product_pricelist` | Pricelist is not an approved contract. Using it as the system of record is an architecture risk. |
| `analytic` | Transitive from `account` | VERIFIED_AVAILABLE 1.2. Depends `base`, `mail`, `uom`. | Manifest only. | Not a P0 pricing dependency. Do not require it directly unless a later decision says so. |
| `account` | Posted customer invoices, taxes, partial reconciliation | VERIFIED_AVAILABLE. 18 version 1.3, 19 version 1.4, 20 version 1.5. Depends `base_setup`, `onboarding`, `product`, `analytic`, `portal`, `digest`. Application name Invoicing. | `account.move`, `account.move.line`, `account.tax`, `account.partial.reconcile`, `account.invoice.report` | Required when a module is eventually created. Pulls `portal`. Portal publication of prices is not authorized by that dependency. |
| `contacts` | Contacts application shell | VERIFIED_AVAILABLE, but Odoo 20 depends change to `base_address_extended`, `mail`, `web_hierarchy` | Manifest parse | OPTIONAL. `res.partner` does not need this application. A hard dependency changes the Odoo 20 install set. |
| `sale` | Quotations and sale orders, only if DEC-09 / sales evidence requires them | VERIFIED_AVAILABLE 1.2. Depends `sales_team`, `account_payment`, `utm` | `sale.order.pricelist_id` exists | OPTIONAL. Not required to read a posted invoice. DEV-10 has no P0 requirement row yet. |
| `sale_management` | Sales application shell | VERIFIED_AVAILABLE. Depends `sale`, `digest`. Odoo 20 manifest has no version key. | Manifest parse | OPTIONAL. |
| `account_payment` | Payments, only if sale is required | VERIFIED_AVAILABLE 2.0. Depends `account`, `payment` | Manifest | OPTIONAL. Partial reconciliation already lives on `account`. |
| `purchase` | Vendor bills | VERIFIED_AVAILABLE 1.2. Depends `account` | Manifest | OPTIONAL. Customer-invoice scope does not require it. DEC-04 in the commercial sense is not this module. Vendor scope is not a P0 population. |
| `loyalty`, `sale_loyalty` | Promotions | VERIFIED_AVAILABLE, LGPL-3 | Manifests | NOT_APPLICABLE as the contract engine. |
| `account_accountant` | Enterprise accounting | VERIFIED_MISSING on 18, 19, and 20 | Manifest path absent | Must not become a dependency. |
| `accountant` | Enterprise accounting shell | VERIFIED_MISSING on 18, 19, and 20 | Manifest path absent | Must not become a dependency. |
| `sale_subscription` | Subscription contracts | VERIFIED_MISSING on 18, 19, and 20 | Manifest path absent | Must not be used as the contract register. |
| `account_reports` | Enterprise financial statements | VERIFIED_MISSING on the Odoo 19 tree checked | Path absent | P0 dashboards must not depend on it. Community alternative: APP 04 read models plus QWeb, CSV, and a later XLSX choice. |
| `web_studio`, `documents`, `sign`, `helpdesk`, `approvals` | Enterprise-style extras | VERIFIED_MISSING on the Odoo 19 tree checked | Paths absent | NOT_APPLICABLE. |
| `ir.cron` | Scheduled audits | VERIFIED_AVAILABLE in `base` | `ir.cron` model | Behavior of a future job is untested. Sudo across companies is forbidden by SEC-08. |
| Community invoice QWeb | Standard invoice print | VERIFIED_AVAILABLE as XML under `addons/account/views/report_invoice.xml` and related files | File list | This is not the leakage report. |
| `account.invoice.report` | Community invoice analysis view | VERIFIED_AVAILABLE | `addons/account/report/account_invoice_report.py` | Not a leakage ledger. KPI definitions remain APP 04 work. |
| wkhtmltopdf | PDF rendering binary used by report actions | REQUIRES_VALIDATION | `ir.actions.report._run_wkhtmltopdf` is referenced from `odoo/tests/common.py` and `odoo/tools/pdf` | External binary and its license are LEGAL_OR_LICENSE_REVIEW_REQUIRED before a PDF gate is called passed. Not added in this step. |
| XLSX library | P0-I controlled XLSX export | REQUIRES_VALIDATION | No APP 04 dependency. The freight addon declares `xlsxwriter`. That declaration was not copied. | Choose later. CSV can use the Python standard library. Do not vendor third-party code in DEV-00. |
| `l10n_generic_coa` | Generic chart sometimes used in demos | VERIFIED_MISSING on 18, 19, and 20 | Path absent | Demo data must not require it. |

## Platform facts used by later invariants

Verified on Odoo 19 source unless a series difference is stated. Odoo 18 and 20 match the selection values below.

`account.move.state`: `draft`, `posted`, `cancel`.

`account.move.move_type`: `entry`, `out_invoice`, `out_refund`, `in_invoice`, `in_refund`, `out_receipt`, `in_receipt`.

`payment_state`: `not_paid`, `in_payment`, `paid`, `partial`, `reversed`, `blocked`, `invoicing_legacy`.

Odoo 20 also defines accounting `REVIEW_STATE_SELECTION`: `todo`, `reviewed`, `supervised`, `anomaly`. That is not an APP 04 audit state.

`account.move.line` has `product_uom_id`. The name `product_uom` is absent on the line in all three series. `price_unit` uses Product Price display precision. `price_subtotal` and `price_total` are monetary. `quantity` uses Product Unit precision. `discount` uses Discount precision.

Shipped decimal defaults, which a database can change: Product Price 2, Discount 2 (`addons/product/data/product_data.xml`), Product Unit 2 (`addons/uom/data/uom_data.xml`).

`account.tax.price_include` is computed. `price_include_override` is `tax_included` or `tax_excluded`. `amount_type` includes `group`, `fixed`, `percent`, and `division`.

Company rules on moves: `account_move_comp_rule` and `account_move_line_comp_rule` use `[('company_id', 'in', company_ids)]` in `addons/account/security/account_security.xml`.

`res.currency.rate` is dated and company-scoped. `company_id` defaults from the company root.

`product.pricelist.company_id` is optional. Partner pricelist assignment is current, not a historical approved version.

### UoM break

| Fact | Odoo 18 | Odoo 19 | Odoo 20 |
| --- | --- | --- | --- |
| Models | `uom.uom` and `uom.category` | `uom.uom` | `uom.uom` |
| Graph | `category_id`, `factor`, `factor_inv`, `uom_type` | `relative_uom_id`, `relative_factor`, stored `factor` | Same graph as 19 |
| `rounding` field | Stored per unit | Computed from Product Unit precision | Field absent. `uom.uom.round()` still uses Product Unit precision |

## Would P0 require Enterprise?

No P0 row requires `account_accountant`, `account_reports`, `sale_subscription`, or another Enterprise module that is missing from these trees.

Community-compatible alternatives, for later review, not for implementation now:

| Need | Do not use | Community alternative |
| --- | --- | --- |
| Approved versioned customer contract | `sale_subscription`, bare `product.pricelist` | A future APP 04 contract model with required `company_id`, approval, and effective versions. |
| Finance validation and recovery ledger | Enterprise accounting statements | APP 04 amounts that reference posted `account.move` and `account.partial.reconcile` without posting new moves until a phase is authorized. |
| Executive dashboard | `account_reports` | APP 04 read-only aggregates in a later phase. |
| PDF | None required in DEV-00 | Community QWeb report action, after the wkhtmltopdf runtime is actually verified. |

`account` depending on `portal` is a confidentiality risk to design against, not an Enterprise blocker.

## License questions

Status of every APP 04 licensing choice: **LEGAL_OR_LICENSE_REVIEW_REQUIRED**.

| Topic | Evidence | Review needed |
| --- | --- | --- |
| Odoo server and Community addons | LGPL-3 in `release.py` and the parsed manifests | A commercial module may depend on LGPL code only if the legal obligations are met. This step does not decide that. |
| APP 04 license | No `LICENSE` file | Do not assume OPL, LGPL, AGPL, or a proprietary grant. |
| Proposed price USD $599 | Prompt statement | Commercial hypothesis. Not store metadata and not a license. |
| Freight addon `OPL-1` | Its manifest | Not transferable to APP 04. |
| Future `xlsxwriter` or wkhtmltopdf | Not adopted | Third-party notices and binary license before packaging. |
| Mixing OCA or other copyleft into this addon | No such code present | Do not copy it in later phases without a recorded license review. |

This step did not change any license file.
