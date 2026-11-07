# Multi-company security

Global record rules in `security/recovery_rules.xml` use `[('company_id', 'in', company_ids)]` on all ten commercial models, including the wizard. The rules have no group. There is no unrestricted cross-company `sudo()`.

`_require_company()` checks `env.companies` for a normal user and returns immediately for the superuser. It does not replace the ORM `_check_company`. `_check_company_auto` stays true.

## Access

`security/ir.model.access.csv` grants read to contract user, contract manager, finance reviewer, finance manager, and internal auditor on the persistent commercial models. Contract manager also has write. Create and unlink stay off for those rows because public create and unlink are refused in Python. The event row for contract manager is read and write only (`1,0,1,0`). The wizard row is contract manager only (`1,1,1,1`). Recovery Operator and Application Administrator have no commercial ACL rows. Application Administrator still has only `cpla.company.policy` among business models.

Menus under Recovery Management use the same five groups as the read roles. Recovery Operator, Application Administrator, and the sales pricing reviewer are not on those menus.

## Negative results that passed

`test_rec16_wrong_company_and_security` runs as part of the 13 targeted tests, the 941-test full run, and the 941-test upgrade. Company B's contract manager gets an empty search and `AccessError` on read of a Company A recovery request and finance validation. `prepare_from_validation()` of that validation also raises `AccessError`. The message is the multi-company access denial. It does not contain `RECOVERY_SOURCE_NOT_READY`. A Company B user cannot read the Company A negotiation attachment. Direct event create raises `HISTORICAL_APPROVAL_PROTECTED` for a contract manager. Export without the commercial role is denied. The auditor export path links `base.group_allow_export` inside the test.

A finance reviewer who tries to approve a waiver is denied by the matrix, not by a seeded money limit. Self-approval is denied for recovery and for waiver.
