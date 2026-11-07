# Multi-company security

No new group and no new access-control row were added. The abstract service has zero `ir.model.access` rows. Header unlink, version approval, and the eight role XML IDs are unchanged.

## Who can normalize

`normalize` and `select_rate` require one of: contract user, contract manager, finance reviewer, finance manager, internal auditor.

Sales pricing reviewer and recovery operator receive `AccessError`. The error text does not include the comparable price. Company A cannot read Company B's version line. The record rule denies the read before a price is computed.

A request `company_id` that does not match the version returns `COMPANY_ACCESS_DENIED` and no price. A multi-company user still converts each version with that version's own clause. Company A's rate 84 is not applied to Company B.

## Writes

An approved fixed multiplier cannot be rewritten by the contract owner. A finance reviewer cannot write the clause. Snapshot fields are rejected on create and write for every caller, including a manager, because the guard runs before the state check's super call only for those field names. Ordinary users do not receive a path that updates frozen evidence.

The service file contains no `sudo(` and no `.execute(`. SEC08-T007 reads the file. Currency rate rows in tests are created by the test superuser, which is the same right Odoo gives `base.group_system`, not an APP 04 group.

## Export

`export_data` of `fx_multiplier_exact` by a contract user raises `UserError` because the user does not have `base.group_allow_export`.

## Isolation that stays in review

Company policy records remain company-owned. A candidate FX basis on Company A is not read for Company B. Cross-company tax percentages are not copied into another company's result explanation.
