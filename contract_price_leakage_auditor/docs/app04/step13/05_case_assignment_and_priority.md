# Assignment and priority

No automatic routing is implemented. Opening a case leaves `owner_id`, `priority`, `severity`, and `target_review_date` empty. Sales team, customer account owner, contract manager, product unit, and workload are not used as hidden assignment rules.

## Eligible investigator

`_eligible_investigator` requires all of the following:

- The user exists, is active, and is not a share or portal user.
- The case company is in `user.company_ids`.
- The user has `group_contract_user` or `group_contract_manager`.

Rejected by that check: company-other users, application administrators with only `group_app_admin`, finance-only users, sales-only users, and recovery operators.

Assignment and reassignment are `action_assign`, contract manager only. The method stores the previous owner name, the new owner name, the reason, the actor, and the time on a case event. The first assign also sets state `assigned` and logs `state_changed`. A later assign logs `owner_changed` and does not reset `assigned_at`.

The new owner is subscribed on the case chatter only when `_partner_may_follow` accepts that partner. The customer is not subscribed. `_mail_thread_customer` is false. `_message_auto_subscribe_followers` returns an empty list. `mail.thread` still inserts the creating user as a follower unless `mail_create_nosubscribe` is set. Case creation uses the manager environment, so that follower is the manager who opened the case, not the customer.

## Participants

`action_add_participant` is contract manager only. The user must pass `_partner_may_follow`: an internal user in contract user, contract manager, finance reviewer, finance manager, or internal auditor, with the case company. The participant is not a second owner. The event type is `participant_added`.

## Priority and severity

Labels are `low`, `medium`, `high`, and `critical`. They are the same selection for priority and severity. Neither label is tied to an amount. A high exposure does not become critical by itself. A missing amount does not become low.

`action_set_priority` and `action_set_severity` require a contract manager, an open case, a label, and a reason. The previous value is stored on the event.

## Deadlines

`target_review_date` is a normal date field a contract manager may write while the case is open. The code does not default it. `is_overdue` is true only when that date is before today and the state is not `closed_with_reason`. `age_calendar_days` counts calendar days. The field help says it is not a business-day count.

`escalation_policy_reference` can be stored. No method reads it to notify or escalate. No `ir.cron` is created for cases.

## Activities

`action_schedule_activity` uses `mail.activity` type `mail.mail_activity_data_todo`. The caller must pass `user_id`, `date_deadline`, and `summary`. There is no default date. `automated` is false. The assignee must be an eligible investigator. Completing the activity with `action_feedback` does not change the case state or the exposure. The class test covers that.
