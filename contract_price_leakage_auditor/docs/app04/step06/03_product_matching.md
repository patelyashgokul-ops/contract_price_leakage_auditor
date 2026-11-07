# 03 — Product matching

Every approved version line stores a `product.product`. `product_tmpl_id` is a related field. There is no template-scope flag and no category price.

An exact variant matches only that variant. A sibling variant does not receive the price. Archiving the product after approval does not drop the stored line. The resolver browses the product with `active_test` disabled.

If the caller sets `template_fallback_requested` and a sibling variant has an approved price, the status is `POLICY_REVIEW_REQUIRED`, reason `product_template_scope_not_represented`. The sibling price is not copied. Without that flag, the same case is `NO_APPLICABLE_CONTRACT`.

A request that supplies only `category_id` is `POLICY_REVIEW_REQUIRED`, reason `product_category_not_supported`.

Two approved lines for one product are possible only with different units. A non-default unit cannot pass review, so DEV-06 does not approve a second unit. If a request quantity is present, `tier_status` is `pending_dev07`. The stored unit price is returned with the sentence that it is not a qualified tier price. Quantity is not multiplied. DEV-07 owns tier qualification and unit conversion.

A product whose `company_id` is another company is rejected. A product with an empty company is allowed. The contract's company still limits the search.
