# Partial payment and allocation

Principal attributed to one partial is the invoice-currency matched amount, limited to the remaining posted principal. Each partial key is stored once.

## One recovery, several payments

Three bank-verified allocations of 5000, 7000, and 8000 on a 20000 tax-free billing add to 20000. After the first two, verified cash is 12000 and outstanding principal is 8000. The recovery is not marked fully collected until the residual principal is zero.

## One payment, several invoices

The recovery keeps only the partial amount on its own receivable. A 50000 customer payment that allocates 12000 to the recovery invoice and 38000 to another invoice contributes 12000. `group_payment` is how Odoo 19 puts both invoices on one payment. The payment total is not copied onto every invoice.

## Tax

When tax was billed, principal is `quantize(matched * posted principal / gross)`. A payment of 11800 on a 23600 gross invoice with 20000 principal attributes 10000 to principal. The rest is tax collection and is not recovered principal. When the invoice is fully settled by verified cash and nothing else, recovered principal may equal the full untaxed principal and the tax is reported separately.

## Residual

`accounting_residual` is the native `amount_residual`, which includes tax. `outstanding_principal` is the tax-exclusive recovery figure after reducing classifications. They are equal in a tax-free example with no unknown credit and no unconfirmed payment. A gap larger than currency rounding adds `RECEIVABLE_RESIDUAL_MISMATCH`. The figures are not forced to match.

## Reversal

After `remove_move_reconcile` on the receivable, the next refresh drops that partial from current cash and keeps the old evidence row as `REVERSAL`.
