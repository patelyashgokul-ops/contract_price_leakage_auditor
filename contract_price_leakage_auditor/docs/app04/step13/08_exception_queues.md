# Exception queues

Non-monetary DEV-12 categories open a case with a blank `current_potential_exposure_exact`. The blank is not the string `0`. `exposure_unknown_count` is at least 1.

`exception_queue` is false for `potential_leakage`, including `UNAUTHORIZED_DISCOUNT_INDICATOR`. That category is a monetary finding. The queue value `discount_approval_review` exists on the selection and is not assigned by the detector map. `security_or_company_exception` is also on the selection and is not auto-assigned. A cross-company attempt raises. It does not open a security-queue case.

## Map

| Finding category | Case type | Queue |
| --- | --- | --- |
| `CONTRACT_COVERAGE_EXCEPTION` | `contract_coverage_exception` | `contract_review` |
| `CONTRACT_CONFLICT_REVIEW_REQUIRED` | `conflict_review` | `contract_review` |
| `MISSING_PRICING_EVIDENCE` | `pricing_evidence_exception` | `pricing_date_review` |
| `FX_OR_TAX_REVIEW_REQUIRED` | `pricing_evidence_exception` | `financial_normalization_review` |
| `SOURCE_ALLOCATION_REVIEW_REQUIRED` | `pricing_evidence_exception` | `source_mapping_review` |
| `REFUND_REASSESSMENT_REQUIRED` | `refund_reassessment_exception` | `credit_refund_review` |
| `UNSUPPORTED_TRANSACTION` | `other_control_exception` | `other_evidence_review` |
| `TECHNICAL_AUDIT_FAILURE` | `other_control_exception` | `other_evidence_review` |

The menu `menu_cpla_exception_queue` filters `exception_queue != False`.

## Submission of an exception

An exception case cannot be submitted with a non-blank exposure. `outstanding_qualification` is required so the missing evidence is written down. The required exception checklist must be answered. A required No still needs that qualification field.

Submitting an exception does not invent a zero leakage amount and does not mark the invoice compliant.
