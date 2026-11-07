# APP 04 step 00 documentation

Contract Price Leakage Auditor. Odoo 19 Community is the master target.

This directory is the source of truth for development step 00. It is a planning baseline. It is not business acceptance.

DEV-01 later added an installable foundation. Current foundation evidence is `docs/app04/step01/`. This step 00 package was not rewritten into an approval.

## Source-of-truth hierarchy

1. `docs/app04/step00/` controls when two DEV-00 documents disagree.
2. `docs/00_*.md` is the first-pass evidence note written before the remainder of the step 00 prompt arrived. Those files are preserved. They are not a second baseline.
3. Odoo 19 Community source under `C:\PycharmProjects\odoo19\odoo-19.0` is the evidence for platform facts cited here.
4. At the close of step 00, no APP 04 model, manifest, or test existed. Code added in DEV-01 is recorded under `docs/app04/step01/`.

Later phases must cite a requirement ID, a decision ID, and an invariant ID from this package before adding behavior. A P1 row is not P0. An open decision is not an approval.

## Files

| File | Contents |
| --- | --- |
| [01_repository_audit.md](01_repository_audit.md) | Disk, Git, manifests, pre-existing files. |
| [02_environment_community_dependencies.md](02_environment_community_dependencies.md) | Odoo 18/19/20 Community dependency table and license questions. |
| [03_requirements_baseline.md](03_requirements_baseline.md) | Provisional P0, P1, and exclusions. |
| [04_requirements_traceability.md](04_requirements_traceability.md) | Requirement to phase, test, and invariant. |
| [05_financial_invariants_and_golden_tests.md](05_financial_invariants_and_golden_tests.md) | FIN-01–FIN-16, GOLD-FIN-001–010, GOLD-REC-001. |
| [06_security_and_operational_invariants.md](06_security_and_operational_invariants.md) | SEC-01–SEC-12, OPS-01–OPS-10, security risks. |
| [07_open_decisions_and_risks.md](07_open_decisions_and_risks.md) | DEC-01–DEC-20 and risks. |
| [08_testing_and_release_gates.md](08_testing_and_release_gates.md) | Test strategy and gates G01–G15. |
| [09_development_roadmap_handoff.md](09_development_roadmap_handoff.md) | DEV-00–DEV-21 and the 18/20 strategy. |
| [10_phase00_progress_and_signoff.md](10_phase00_progress_and_signoff.md) | Task status and the two phase statuses. |

## ID rules

| Prefix | Meaning |
| --- | --- |
| A- through F-, H- | Provisional P0 requirement IDs continued from the first-pass register. |
| PG-, RPT-, PJ- | Provisional IDs for P0-G, P0-I, and P0-J. They avoid collision with gates G01–G15 and with FIN/SEC/OPS. |
| P1-, X- | Provisional enhancement and exclusion IDs. |
| FIN, SEC, OPS, DEC, GOLD-FIN, GOLD-REC, G01 | IDs fixed by the step 00 prompt. |
| GT-, OD-, I- from `docs/00_*.md` | First-pass aliases only. Do not use them as the current IDs. |

No requirement ID in this package is an approved business ID. None has been renumbered.

## How later phases use these records

- Implement only the requirement IDs mapped to that phase in `04_requirements_traceability.md`.
- Stop when a row depends on a decision whose status is not APPROVED. None are APPROVED today.
- Golden fixtures are expected calculations for future tests. They are not test results.
- Odoo 18 and Odoo 20 are not supported targets until their own validation exists.

**TEST EXECUTION: NOT PERFORMED — DEV-00 PLANNING ONLY.**
