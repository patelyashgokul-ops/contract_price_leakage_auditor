# Part of Contract Price Leakage Auditor.
{
    'name': 'Contract Price Leakage Auditor',
    'version': '19.0.1.15.0',
    'summary': 'Authorized recovery can be billed and reconciled. A draft is not posted cash.',
    'description': """
Contract Price Leakage Auditor — posted invoice audit.

Eligible posted customer invoices are compared with the approved
historical contract price. The audit stores potential leakage, review
exceptions, and the calculation evidence. An investigation case can
reference those findings. A reassessment proposes a new reading and
keeps the original result. Potential leakage is not finance-validated
leakage, billed recovery, or collected cash. A finance validation may
approve only a supportable portion of the accepted evidence. That
approval is not a receivable, a waiver, or collected cash. A commercial
recovery request, waiver, dispute, or settlement allocates that validated
amount. That authorization does not post an invoice. After an approved
accounting handoff and an approved billing policy, a finance manager
with invoice rights can prepare a draft recovery invoice or link a
posted document. Posting is a separate action. A draft is not posted
recovery. A posted invoice is not collected cash. A credit note is not
incoming cash. Accepting a reassessment is not finance validation.
Submission for finance review is not approval. Closing a case is not
recovery. The module does not schedule a recurring job.
""",
    'category': 'Sales',
    # BLOCKER_LICENSE_DECISION_REQUIRED.
    # Odoo 19 assigns LGPL-3 when this key is omitted
    # (odoo/modules/module.py, _load_manifest). That default is not an
    # approved legal choice. "Other proprietary" is a loader guard so the
    # module is not silently stamped LGPL-3. It is not OPL-1, not a license
    # grant, and not permission to sell or distribute the module.
    'license': 'Other proprietary',
    'depends': ['base', 'product', 'sale'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/company_policy_rules.xml',
        'security/customer_contract_rules.xml',
        'security/contract_version_rules.xml',
        'security/pricing_applicability_rules.xml',
        'security/discount_rules.xml',
        'security/sale_price_lock_rules.xml',
        'security/invoice_source_rules.xml',
        'security/invoice_audit_rules.xml',
        'security/leakage_case_rules.xml',
        'security/leakage_reassessment_rules.xml',
        'security/finance_validation_rules.xml',
        'security/recovery_rules.xml',
        'security/billing_rules.xml',
        'data/ir_sequence.xml',
        'data/audit_sequence.xml',
        'data/case_sequence.xml',
        'data/reassessment_sequence.xml',
        'data/finance_validation_sequence.xml',
        'data/recovery_sequence.xml',
        'data/billing_sequence.xml',
        'views/company_policy_views.xml',
        'views/customer_contract_views.xml',
        'views/contract_version_views.xml',
        'views/pricing_applicability_views.xml',
        'views/discount_views.xml',
        'views/sale_quotation_views.xml',
        'views/invoice_source_views.xml',
        'views/invoice_audit_views.xml',
        'views/leakage_case_views.xml',
        'views/leakage_reassessment_views.xml',
        'views/finance_validation_views.xml',
        'views/recovery_views.xml',
        'views/billing_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
