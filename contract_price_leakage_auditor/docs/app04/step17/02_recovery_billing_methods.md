# Recovery billing methods

The approved billing policy chooses one method. The code does not switch methods when the chosen one is unavailable.

| Method | Behavior |
| --- | --- |
| `manual_handoff` | State `document_prepared`. No `account.move`. `handoff_package()` returns `MANUAL_ACCOUNTING_HANDOFF` and `creates_account_move` false. `action_post` raises `ACCOUNTING_METHOD_UNAVAILABLE`. |
| `standalone_invoice` | `action_create_draft` creates a draft `out_invoice` in the policy journal. Posting is a later call. |
| `debit_note` | Uses `account.debit.note` only when that model is in the registry. `create_debit` is called with `copy_lines` false. The document stays `out_invoice` and keeps `debit_origin_id`. If the model is absent, the method raises `ACCOUNTING_METHOD_UNAVAILABLE` and does not create a standalone invoice. |
| `existing_document` | Links a posted `out_invoice` that already matches company, commercial partner, currency, and untaxed amount. It must not be the original leakage invoice and must not already have a current link. Posted lines are not written. |

`prepare_from_request` does not post. The same identity returns the existing billing record. A second current link of the same move from a different slice raises `DUPLICATE_BILLING_ALLOCATION`.

Draft price is the untaxed principal. When the policy treatment is `taxes_on_policy`, the selected taxes are applied by the tax engine. The gross price is not passed again as `price_unit` on top of tax-excluded taxes.

`action_post` calls `move.action_post()` as the current user. It does not use `sudo`. A second freshness check and the four-eyes check run before that call. If the draft untaxed amount is not the requested principal, posting raises `BILLING_DOCUMENT_MISMATCH` and leaves the draft unposted.
