# Commercial evidence and communications

Customer evidence is recorded only when a user calls a server method with a channel, a date where required, and a text explanation. Channels are email correspondence, formal letter reference, meeting notes, phone-call summary, customer-signed proposal, authorized negotiation record, and other approved evidence. The module does not invent a message and does not deliver one.

No demand letter, settlement term, or price evidence is emailed. Recovery submit creates one internal `mail.activity` on `cpla.leakage.case` when `mail.mail_activity_data_todo` exists. The summary is exactly `Review recovery request`. The note says the date is the review request date and not a collection deadline. The amount is not in the summary. Context `mail_activity_quick_update` and `mail_notrack` are set. If the activity type is missing, the activity is skipped. The targeted full-recovery test observed an unchanged `mail.mail` count and an unchanged follower set.

Signup mail logged while tests create users comes from `auth_signup`. It is not a customer demand.

## Attachments

`IrAttachmentCaseGuard` includes recovery request, waiver, dispute, settlement, and event. A public or tokenized attachment on those models raises `UserError` (`Investigation evidence cannot be public.`). The wizard, the policy, the balance, and the request line are not in that list.

Internal comments and the external evidence text are different fields. Dispute explanation, counteroffer evidence, and acceptance evidence are stored on the commercial record. They are not posted to the customer.

Confidential export of a recovery request is limited to a contract manager or an internal auditor who also has `base.group_allow_export`. Other users, including the superuser, get `COMPANY_ACCESS_DENIED` before the export runs.
