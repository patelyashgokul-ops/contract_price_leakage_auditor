# Historical audit evidence

Every authoritative result stores a calculation trace and an evidence snapshot. A review result stores the reason and does not invent the missing numbers.

## Trace

The trace names the contract version reference, why that version applied, the approved adjusted unit price, the actual invoice unit price, the eligible quantity, the gross difference, the authorized concession, and the potential unauthorized difference. It also names the FX, UoM, and tax basis that the pricing services returned. It states that potential leakage is not finance-validated, billed, or collected.

`INT12-T011` asserts the version reference and the amounts 50,000 and 25,000 for the special-price fixture.

## Snapshot and fingerprint

The snapshot is canonical JSON. It includes company, invoice line, allocation, version, pricing date, cutoff token, discount status, FX rate text, tax basis, source fingerprint, and source revision. Prices in that snapshot are hashed inputs for reproducibility. They are not placed in the public `AUD/` or `LKF/` reference.

The input fingerprint is SHA-256 of canonical JSON (`sort_keys`, stable separators). It includes the engine version, company, line, allocation, cutoff token, source fingerprint, source revision, version, classification, and the exact price and quantity texts. It does not use `write_date` or an arbitrary record order.

A different explicit knowledge cutoff is a different fingerprint and a different current identity. `GOLD-AUD-018` audits the same July invoice with a cutoff before the later version and a cutoff after it. The early result stays on the earlier version. The later result can show the increase. The early result row is not overwritten.

## Reassessment

`action_reassess` opens a new run. It does not edit the previous result. A material source change creates a new finding revision and supersedes the previous current row. `IDM12-T009` changes the sale-line price after the first audit and asserts that the first result still exists with its original classification and that the new result has a different fingerprint.

A programming failure is `TECHNICAL_AUDIT_FAILURE` or a failed run state. It is not stored as `PRICING_COMPLIANT`.

## What a later finance reviewer can read

The result and the finding keep the version, the tier, the pricing date, the cutoff, the three waterfall amounts, the eligible quantity, the currency, the trace, and the snapshot. DEV-15 is not implemented. Nothing in these rows is marked finance-validated.
