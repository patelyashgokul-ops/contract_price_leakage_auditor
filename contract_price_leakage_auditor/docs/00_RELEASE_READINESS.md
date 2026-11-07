# Release readiness

Superseded for acceptance by `docs/app04/step00/08_testing_and_release_gates.md` and `10_phase00_progress_and_signoff.md`. This file is the preserved first pass.

Decision: **NO-GO**

APP 04 is not a module, not a tested build, and not a store candidate. Step 00 is a draft baseline. It is not authorized, and it must not be described as an accepted phase.

Inspection date: 2026-10-28.

## Evidence summary

| Gate | Evidence | Result |
| --- | --- | --- |
| Repository identified | Empty addon directory. No manifest. | Implementation NOT FOUND. |
| Existing work protected | No pre-existing files. Freight addon not modified. | Held. |
| Git provenance | No repository. | NOT VERIFIED. |
| Requirements source | Prompt sections 1–6 and a partial section 7. No on-disk specification. | Partial. |
| P0 register | 24 supplied bullets. Seven of ten announced packages not received. | Incomplete. |
| Community dependencies | Manifests and cited fields read on local 18, 19, and 20 trees. | Static pass for the cited facts. |
| Enterprise dependency | `account_accountant` and `sale_subscription` absent on all three trees. | None introduced. |
| Financial invariants | Drafted and tied to source fields. | Not implemented and not tested. |
| Multi-company | Rule drafted. Native invoice rule confirmed in source. | Not tested. |
| Golden tests | 23 cases planned. | Not executed. |
| Database | Not contacted. | No migration, install, or production test. |
| Open money rules | OD-01, OD-02, OD-05, OD-06, OD-07, and related rows. | Unresolved. |

## Release blockers

1. The master prompt stopped during P0-C. The rest of the ten-package register is missing.
2. The blocking open decisions are unresolved. A leakage amount cannot be defined without them.
3. No installable module exists, by instruction of this phase.
4. No automated test has run on Odoo 19, 18, or 20.
5. Git history cannot identify a base commit.
6. License and author are undecided (OD-15). The USD $599 figure is a prompt statement, not store metadata.
7. UoM behavior differs across the three series. A single compatibility claim would be false.
8. Phase 00 has no review authorization (OD-24).

## Conditions for a later GO

A development phase that adds models can start only after all of the following are true:

- A reviewer accepts this package or supplies the missing prompt text and an updated register.
- The blocking decisions in `00_OPEN_DECISIONS.md` are written down as decisions, each with an owner.
- The first implementation phase still has an explicit file list. Step 00 does not authorize menus, crons, or accounting workflows by implication.
- Tests for the implemented slice run on a disposable Odoo 19 database.
- Odoo 18 and Odoo 20 remain unwired until their own phases. Static presence of a dependency is not compatibility.

A store release additionally needs a license, a maintainer, an install test, a security test, a multi-company test, and the golden cases that the implemented scope claims.

## Risks carried forward

| Risk | Why it matters |
| --- | --- |
| Pricelist used as the contract | Optional company, no approval chain, current partner assignment. Findings would move when someone edits today's price. |
| Tax basis chosen in code | `price_include` is computed. A wrong basis invents leakage. |
| UoM port copied from Odoo 18 examples | `uom.category` does not exist on 19 or 20. `uom.rounding` does not exist on 20. |
| `sudo()` in a future cron | Breaks company isolation even if record rules exist. |
| Payment state treated as recovery | Customer payment of the invoice does not prove that a price difference was recovered. |
| Freight addon used as a template without a new decision log | Its domain is carrier bills, its license is already chosen, and its tolerances are not APP 04 policy. |
| Truncated prompt filled by assumption | The next packages may contradict a reconstructed rule. |

## Authorization block

| Item | State |
| --- | --- |
| Step 00 package prepared | Yes, 2026-10-28. |
| Reviewer | Not named. |
| Authorization | Not granted. |
| Phase 00 accepted | No. |

## Files added by step 00

- `README.md`
- `DEVELOPMENT_PROGRESS.md`
- `docs/README.md`
- `docs/00_REPOSITORY_AUDIT.md`
- `docs/00_REQUIREMENTS_SOURCE_INVENTORY.md`
- `docs/00_P0_REQUIREMENTS_REGISTER.md`
- `docs/00_COMMUNITY_DEPENDENCY_VERIFICATION.md`
- `docs/00_FINANCIAL_SECURITY_INVARIANTS.md`
- `docs/00_OPEN_DECISIONS.md`
- `docs/00_GOLDEN_TEST_PLAN.md`
- `docs/00_RELEASE_READINESS.md`

No Python, XML, CSV, or manifest file was added.
