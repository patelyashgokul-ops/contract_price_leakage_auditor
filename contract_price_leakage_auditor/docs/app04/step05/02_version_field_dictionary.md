# 02 — Version field dictionary

Date: 2026-10-28.

Security for every model is in `07_version_security_matrix.md`. Public `write` rejects the server-controlled fields listed here even when the ACL allows write.

## `cpla.customer.contract.version`

Constraints: `UNIQUE(contract_id, version_number)`, `UNIQUE(company_id, reference)`. Dates: Valid To cannot be earlier than Valid From.

| Field | Type | Notes |
| --- | --- | --- |
| `contract_id` | Many2one, required, indexed | Parent. `check_company`. Not reassigned. |
| `company_id` | Many2one, related stored, indexed | Parent company. Readonly. |
| `version_number` | Integer, required, indexed | Server allocated. Readonly. |
| `reference` | Char, required, indexed | `{contract}/V0001`. Readonly. |
| `state` | Selection, required, indexed | Approval state. Readonly. Not a client write. |
| `effective_status` | Selection, computed, searchable | `scheduled`, `currently_effective`, `superseded`, `expired`. |
| `historically_effective` | Boolean, computed | Superseded or expired. |
| `authority_to` | Date, computed | Inclusive end. Day before the next approved effective date, else Valid To. |
| `reassessment_required` | Boolean, computed | Unapproved amendment dated before today. |
| `effective_from` | Date, indexed | Inclusive commercial start. Not the approval timestamp. |
| `valid_from`, `valid_to` | Date, indexed | Overall validity copied onto the snapshot. |
| `partner_id` | Many2one, indexed | `check_company`. Draft edits update the name snapshots. |
| `partner_name` | Char | Frozen again at approval. |
| `commercial_partner_name` | Char | Frozen at approval. |
| `covered_partner_ids` | Many2many | Proposal only. Blocks approval while DEC-03 is open. `check_company`. |
| `covered_partner_names` | Text | Frozen at approval. |
| `currency_id` | Many2one | Price currency. Amounts are not converted. |
| `company_currency_id` | Many2one, related | Company currency. Not the price currency. |
| `policy_id` | Many2one, indexed | `check_company`. Current revision required before review. |
| `policy_version_snapshot` | Integer | Copied at approval. |
| `pricing_date_policy_snapshot` | Char | Candidate string. Not an invoice rule. |
| `precedence_policy_snapshot` | Char | Candidate string. Not a precedence engine. |
| `coverage_policy_snapshot` | Char | Candidate string. |
| `amount_threshold_policy` | Char | Constant `not_configured`. Readonly. |
| `retroactivity_policy` | Char | Constant `not_authorized`. Readonly. |
| `description` | Text | Copied text. Not a price. |
| `amendment_reason` | Text | Required on an amendment before review. |
| `external_amendment_reference` | Char, indexed | Customer or file reference. Not the approval id. |
| `approval_note` | Text | Optional note while ready for review. |
| `rejection_reason` | Text | Required to reject. |
| `cancel_reason` | Text | Stored on cancel when provided. |
| `requested_by_id` | Many2one, indexed | Authenticated user, or the owner for the manager's first snapshot. |
| `submitted_by_id` | Many2one | User who submitted. Owner on the first snapshot. |
| `approved_by_id` | Many2one, indexed | `env.user` at approval. |
| `rejected_by_id` | Many2one | User who rejected. |
| `approved_at` | Datetime | Server time. Not `effective_from`. |
| `approval_reference` | Char, indexed | `{reference}/APR`. |
| `source_version_id` | Many2one, indexed | Approved version the draft was copied from. |
| `supersedes_version_id` | Many2one, indexed | Set only inside approval. |
| `superseded_by_ids` | One2many | Inverse. Does not rewrite the old row. |
| `snapshot_sha256` | Char | SHA-256 of the commercial JSON. Not legal proof. |
| `change_summary` | Char, computed | Category counts. Not recovered cash. |
| `line_ids`, `evidence_ids`, `event_ids` | One2many | Children. `copy=False`. |

Depends for the computed status: `state`, `effective_from`, `valid_to`, `version_number`, `contract_id`, and the other approved versions of that contract. Reassessment depends on `source_version_id`, `effective_from`, and `state`.

## `cpla.customer.contract.version.line`

Constraint: `UNIQUE(version_id, product_id, uom_id)`. Negative `price_unit` is rejected. Incompatible, inactive, or factorless units are rejected on save. Packaging units and non-default units can be stored on a draft and block approval.

| Field | Type | Notes |
| --- | --- | --- |
| `version_id` | Many2one, required, indexed | `check_company`. Not moved. |
| `company_id` | Many2one, related stored, indexed | Version company. |
| `sequence` | Integer | Display order. |
| `product_id` | Many2one, required, indexed | `check_company`. `ondelete=restrict`. |
| `product_name` | Char | Copied, then frozen at approval from the product name. |
| `product_tmpl_id` | Many2one, related stored | Not a second price. |
| `name` | Char | Line description. Not a price. |
| `price_unit` | Monetary, required | Explicit negotiated unit price. |
| `currency_id` | Many2one, related stored | Version currency. |
| `uom_id` | Many2one, required | Pricing unit. `ondelete=restrict`. |
| `external_line_reference` | Char | Optional. |
| `notes` | Text | Optional. |
| `contract_line_id` | Many2one, indexed | Set on the first snapshot. |
| `origin_line_id` | Many2one, indexed | Set when copied from a version line. |

Writable only while the parent version is `draft`, and only by a Contract User (a manager implies that group).

## `cpla.customer.contract.version.evidence`

Must have `source_evidence_id`, `origin_evidence_id`, or `datas`. Source and origin must belong to the same company.

| Field | Type | Notes |
| --- | --- | --- |
| `version_id` | Many2one, required, indexed | `check_company`. |
| `company_id` | Many2one, related stored, indexed | Version company. |
| `source_evidence_id` | Many2one, indexed | Header evidence. Bytes are not copied. |
| `origin_evidence_id` | Many2one, indexed | Prior version evidence. |
| `name` | Char, required | Document title. |
| `document_type` | Selection, required | Agreement, schedule, confirmation, amendment, acceptance, internal approval, or other. |
| `source_reference` | Char | External document id. |
| `description` | Text | Note. |
| `datas` | Binary, attachment | New file only. Not copied on every amendment. |
| `content_sha256` | Char | Server checksum. Client writes are rejected. |

Approved evidence cannot be edited or deleted. A manager records a correction event instead.

## `cpla.customer.contract.version.event`

Constraint: `UNIQUE(version_id, event_type)`. `write` and `unlink` always raise, except uninstall.

| Field | Type | Notes |
| --- | --- | --- |
| `version_id` | Many2one, required, indexed | `check_company`. |
| `company_id` | Many2one, related stored, indexed | Version company. A client company is rejected. |
| `contract_id` | Many2one, related stored | Parent contract. |
| `event_type` | Selection, required | See the event table in file 05. |
| `occurred_at` | Datetime, required | Forced to server now. |
| `actor_id` | Many2one, required | Forced to `env.user`. |
| `reason` | Text | Business reason. |
| `source_version_id` | Many2one | Copied from the version at insert. |
| `supersedes_version_id` | Many2one | Copied from the version at insert. |
| `approval_reference` | Char | Copied from the version at insert. |

Create is allowed only when the type matches the version state and the actor is the person who performed that action.

## `cpla.customer.contract.version.compare`

Transient. Fields: `baseline_version_id`, `candidate_version_id`, `result_text`, `result_html`. Both versions must be readable. The lower version number becomes the baseline inside `action_compare`. `result_html` is sanitized. `is_recovered_cash` is not a stored field. The comparison dict always sets it false.

## Header fields added for this phase

On `cpla.customer.contract`:

| Field | Type | Notes |
| --- | --- | --- |
| `version_ids` | One2many | Child versions. |
| `audit_authoritative` | Boolean, computed | True only when a child state is `approved`. |

No approved, active, superseded, or amended value was added to the header state selection.
