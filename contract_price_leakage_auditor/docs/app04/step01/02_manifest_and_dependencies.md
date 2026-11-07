# 02 — Manifest and dependencies

Date: 2026-10-28.
Runtime: Odoo 19.0.0 final (`odoo/release.py` `version_info = (19, 0, 0, final, 0, '')`). The server log printed `Odoo version 19.0`.
Python used for install and tests: 3.11.9 from `C:\PycharmProjects\odoo19\.venv\Scripts\python.exe`.

## Final manifest values

| Field | Value |
| --- | --- |
| `name` | Contract Price Leakage Auditor |
| `version` | `19.0.1.0.0` |
| `summary` | Odoo 19 Community foundation. Contract audit and recovery are not available yet. |
| `description` | States that this build registers the module and initial internal roles. It does not compare prices, store contracts, post entries, or recover cash. |
| `category` | `Sales` (existing Community category string). |
| `author` | Omitted. |
| `website` | Omitted. |
| `license` | `Other proprietary` |
| `depends` | `['base']` |
| `data` | `security/security_groups.xml` |
| `demo` | Omitted. No demo data. |
| `installable` | `True` |
| `application` | `False` |
| `auto_install` | `False` |

Odoo stored `latest_version` `19.0.1.0.0` and license `Other proprietary` on `ir.module.module` in the disposable database. The stored author value is empty.

## License and author

`BLOCKER_LICENSE_DECISION_REQUIRED`

Odoo 19 sets a missing `license` key to LGPL-3 inside `_load_manifest`. That default is not an approved legal choice for this commercial module. The manifest therefore sets `Other proprietary`, which is one of the license values Odoo already offers on `ir.module.module`.

That string is a loader guard. It is not OPL-1, not LGPL-3, not AGPL-3, and not a license grant. It is not permission to sell or distribute the module. The proposed USD $599 price does not choose a license.

No author, legal entity, website, or support contact is recorded for APP 04. The freight addon's publisher was not copied. Odoo logs `Missing author key in manifest for 'contract_price_leakage_auditor', defaulting to ''`.

Both gaps block full DEV-01 technical acceptance and later packaging (PJ-10). They do not stop the local foundation from installing.

## Dependency classification

| Addon | Classification | Evidence |
| --- | --- | --- |
| `base` | REQUIRED | Only declared dependency. State `installed` on the disposable database. Version stored as `19.0.1.3`. |
| `account` | OPTIONAL_LATER | Present in the Odoo 19 Community tree. State on the test database: `uninstalled`. Not required until invoice models exist. |
| `sale` | OPTIONAL_LATER | Present in Community. State `uninstalled`. Not required for the foundation. |
| `product` | OPTIONAL_LATER | Not declared. No pricing model exists yet. |
| `mail` | OPTIONAL_LATER | Not declared. No chatter or activity exists yet. |
| `website`, `stock`, `purchase`, `crm`, `contacts` | REJECTED for DEV-01 | No current feature needs them. `contacts` is also a later compatibility risk because Odoo 20 changes its dependencies. |
| `account_accountant`, `accountant`, `account_reports`, `sale_subscription` | REJECTED | Not in the Community dependency set and not declared. |

DEC-19, which suggested `account` and `mail`, is not approved. The foundation does not adopt it.

## Community compatibility

The declared graph is `contract_price_leakage_auditor` -> `base`. `base` exists in Odoo 19 Community. No Enterprise module is required.

A fresh Odoo database also auto-installs Community modules whose own manifests request it. The install log loaded 15 modules: `base`, this addon, `rpc`, `web`, `api_doc`, `auth_totp`, `base_import`, `base_import_module`, `base_setup`, `bus`, `web_tour`, `auth_passkey`, `html_editor`, `iap`, and `web_unsplash`. Those are Odoo auto-install modules. They are not APP 04 dependencies.

Every path in `data` exists. There is no circular dependency.

## Unresolved dependency risks

- Adding `account` or `sale` later must be a separate, justified manifest change. It will install the Community invoicing or sales stack on databases that do not already have it.
- Odoo 18 and Odoo 20 were not used as the implementation target. Their manifests and security schemas need their own tests before a port.
- The license and author gaps remain release blockers even though `base` installs.
