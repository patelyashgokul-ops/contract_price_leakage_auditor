# Golden financial fixtures

These fixtures ran inside `TestDev12InvoiceAudit`. The comparison currency is the company currency loaded by `generic_coa`. A custom `res.currency` stands in for a foreign currency. Amounts below are the expected values. The class rerun, the full update, the DEV-11 upgrade, and the fresh install each finished at 0 failed, 0 errors, so these assertions passed on those runs.

| Fixture | Expected | Test |
| --- | --- | --- |
| GOLD-AUD-001 | Gross 50,000, concession 25,000, potential 25,000. `UNAUTHORIZED_DISCOUNT_INDICATOR`. | `test_fin12_t001_gold_aud_001_special_price_leakage_is_25000` |
| GOLD-AUD-002 | Potential 0. No finding. `PRICING_COMPLIANT`. | `test_fin12_t002_gold_aud_002_compliant_invoice_has_zero_leakage` |
| GOLD-AUD-003 | Override authorizes the invoice price. Unauthorized leakage 0. | `test_fin12_t003_gold_aud_003_authorized_override_is_not_leakage` |
| GOLD-AUD-004 | Missed increase 20,000. | `test_fin12_t004_gold_aud_004_missed_increase_is_20000` |
| GOLD-AUD-005 | Order-date lock. Leakage 0. | `test_his12_t006_order_date_grandfathering_keeps_the_locked_price` |
| GOLD-AUD-006 | Approved adjusted 957.6 per piece. Leakage 760. | `test_fin12_t006_gold_aud_006_fx_uom_discount_is_760` |
| GOLD-AUD-007 | Approved 200 per piece. Leakage 1,000. | `test_fin12_t007_gold_aud_007_packaging_is_1000` |
| GOLD-AUD-008 | Net 900 from gross 1,062 at 18 percent included. Leakage 10,000. | `test_fin12_t008_gold_aud_008_tax_included_is_10000` |
| GOLD-AUD-009 | 10,000 + 10,000 + 5,000 = 25,000. | `test_par12_t001_partial_quantities_reconcile` and `test_par12_t002_gold_aud_009_partial_exposure_is_25000` |
| GOLD-AUD-010 | Net 80 pieces. Current exposure 4,000. | `test_ref12_t001_and_t002_gold_aud_010_return_is_4000` |
| GOLD-AUD-011 | Current exposure 0. Historical finding remains. | `test_ref12_t003_and_t004_gold_aud_011_full_reversal_clears_current_exposure` |
| GOLD-AUD-012 | Replacement at the approved price. Current leakage 0. No payment. | `test_ref12_t005_gold_aud_012_replacement_does_not_duplicate_exposure` |
| GOLD-AUD-013 | Coverage exception. Blank amount. | `test_his12_t009_missing_contract_produces_no_fabricated_leakage` |
| GOLD-AUD-014 | Conflict review. Blank amount. | `test_his12_t008_conflicting_contract_authority_is_flagged` |
| GOLD-AUD-015 | Positive leakage 0. `PRICE_ABOVE_APPROVED_RATE`. Signed raw is negative. | `test_fin12_t011_gold_aud_015_overbilling_is_not_positive_leakage` |
| GOLD-AUD-016 | Three runs. One current finding. | `test_gold_aud_016_three_runs_do_not_triple_count` |
| GOLD-AUD-017 | Amount-only credit is review. Origin quantity is not reduced. Not cash. | `test_ref12_t007_gold_aud_017_amount_only_credit_is_not_a_quantity_return` |
| GOLD-AUD-018 | Cutoff before and after the later version. Early result preserved. | `test_his12_t010_historical_cutoff_is_respected` |
| GOLD-AUD-019 | Company B version is not applied to Company A. | `test_gold_aud_019_company_b_version_is_not_applied` |
| GOLD-AUD-020 | Only potential leakage is stored. No validated, waiver, recovery-target, billed, or collected fields. | `test_gold_aud_020_later_lifecycle_amounts_are_not_created` |

`FIN12-T019` reuses GOLD-AUD-001 and checks that the gross, concession, and potential amounts reconcile for that positive case.
