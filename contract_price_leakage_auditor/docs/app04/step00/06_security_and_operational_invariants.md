# 06 — Security and operational invariants

No APP 04 model, access file, record rule, cron, or public method exists. Static inspection cannot certify security. Every SEC and OPS control is **NOT_IMPLEMENTED**.

Community facts that later tests must respect:

- `account.move` and `account.move.line` company rules use `[('company_id', 'in', company_ids)]`.
- Invoice groups in `addons/account/security/account_security.xml` include `group_account_invoice`, `group_account_readonly`, `group_account_user`, and `group_account_manager`. Hiding a menu does not replace these.
- `account` depends on `portal`. That does not authorize a portal page for contract prices.
- `ir.cron` exists on `base`. No APP 04 cron was created.

## SEC-01 through SEC-12

| ID | Invariant | Status | Future test |
| --- | --- | --- | --- |
| SEC-01 | Company isolation on every APP 04 business model, enforced in the ORM. | NOT_IMPLEMENTED | PLANNED-SEC-01. User in both companies, only company A active, cannot read company B contracts, findings, or evidence. |
| SEC-02 | Contract prices are confidential. | NOT_IMPLEMENTED | PLANNED-SEC-02. User without the pricing group gets no price via read, export, name_search, or chatter. |
| SEC-03 | Finance duties are separate from audit and from case assignment. | NOT_IMPLEMENTED | PLANNED-SEC-03. Assignee cannot validate leakage. |
| SEC-04 | Approval uses the approved matrix. No matrix means no financial approval. | NOT_IMPLEMENTED | PLANNED-SEC-04. Attempted approval without a matching matrix row is rejected. |
| SEC-05 | The proposer is not the sole approver of that same proposal or waiver. | NOT_IMPLEMENTED | PLANNED-SEC-05. |
| SEC-06 | Attachments follow the parent company and the parent's read group. | NOT_IMPLEMENTED | PLANNED-SEC-06. |
| SEC-07 | PDF, XLSX, and CSV export check the export group. | NOT_IMPLEMENTED | PLANNED-SEC-07. |
| SEC-08 | Background jobs run with an explicit company and do not use sudo to cross companies. | NOT_IMPLEMENTED | PLANNED-OPS-08 together with a company-mismatch fixture. |
| SEC-09 | Approved history and evidence cannot be overwritten or deleted while a hold or audit reference exists. | NOT_IMPLEMENTED | PLANNED-SEC-09. |
| SEC-10 | Approval history stores actor, time, from-state, to-state, and the evidence id. | NOT_IMPLEMENTED | PLANNED-SEC-10. |
| SEC-11 | Privileges are consolidated into named groups. One implied admin group is not the design. | NOT_IMPLEMENTED | PLANNED-SEC-11. A standard internal user does not inherit finance approval. |
| SEC-12 | Logs, notifications, and demo data do not expose customer prices or credentials. | NOT_IMPLEMENTED | PLANNED-SEC-12. |

## Security risk register

| Risk | Current exposure | Later impact if ignored | Classification |
| --- | --- | --- | --- |
| No module, so no APP 04 data to leak | None today | A first implementation that adds models without rules ships open prices. | Future. Gate before DEV-04 data entry. |
| Menu-only security | No menus exist | Record rules and method checks would be skipped. | Forbidden by SEC-01 and PG-01. |
| `sudo()` in a future cron | No cron exists | Cross-company reads and writes. | SEC-08. Release-blocking if introduced. |
| Portal inherited from `account` | Not applicable until a module depends on `account` | Contract prices could be rendered on a portal template by mistake. | Design constraint for DEV-01 and DEV-02. |
| Shared pricelist with empty `company_id` | Platform behavior, source-verified | One price list would apply to every company. | Do not use pricelists as the contract register. |
| Auditor placed in `account.group_account_manager` | No users exist | Broad accounting power granted to read invoices. | SEC-11. Smallest read group only, decided in DEV-02. |
| Export of findings | No export exists | Bulk extraction of confidential prices. | SEC-07. |
| Public methods on models | No models exist | RPC would bypass buttons. | Every state change checks groups, not only the UI. |
| Full certification claimed from this file | This file is a baseline, not a test | False assurance. | Not claimed. |

## OPS-01 through OPS-10

| ID | Invariant | Status | Future test |
| --- | --- | --- | --- |
| OPS-01 | Incremental scope is stable and defined. | NOT_IMPLEMENTED | PLANNED-OPS-01. Second increment does not drop or double-count a line. |
| OPS-02 | Repeated audit with unchanged inputs is idempotent. | NOT_IMPLEMENTED | GOLD-FIN-009 |
| OPS-03 | Concurrent workers do not duplicate exposures or recovery billing. | NOT_IMPLEMENTED | PLANNED-OPS-03 |
| OPS-04 | Committed batches survive process death. | NOT_IMPLEMENTED | PLANNED-OPS-04 interrupt and restart. |
| OPS-05 | Technical failures and business exceptions are different states. | NOT_IMPLEMENTED | PLANNED-OPS-05 |
| OPS-06 | Failed or unprocessed invoices are not shown as successfully audited. | NOT_IMPLEMENTED | PLANNED-OPS-06 |
| OPS-07 | Progress categories sum to the eligible population. | NOT_IMPLEMENTED | PLANNED-OPS-07 |
| OPS-08 | Cron failure and backlog are visible inside the company. | NOT_IMPLEMENTED | PLANNED-OPS-08 |
| OPS-09 | A historical contract change triggers reassessment and keeps the prior result. | NOT_IMPLEMENTED | PLANNED-D-07 |
| OPS-10 | Every report names its as-of time and policy version. | NOT_IMPLEMENTED | PLANNED-RPT-08 |

## Volume cases

These are plans. No database was loaded. No throughput is claimed. No supported volume is claimed.

| Planned id | Eligible invoice lines | Also exercise |
| --- | --- | --- |
| PLANNED-VOL-5000 | 5,000 | Incremental rerun |
| PLANNED-VOL-50000 | 50,000 | Restart after interrupt |
| PLANNED-VOL-100000 | 100,000 | Duplicate scheduler fire |
| PLANNED-VOL-500000 | 500,000 | Two workers |
| PLANNED-VOL-1000000 | 1,000,000 historical lines, only if the environment can hold them | Stale contract version reassessment |

DEC-18 owns the pass threshold. Until it is approved, a measurement may be recorded and may not be called a pass.
