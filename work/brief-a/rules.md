# Brief A rules (summary; full text in corpus.md)
1. Language: English. Fixed lines: "Am I speaking with {title} {last_name}?", "I am sorry for your loss.", "Can you make this payment today?", "Do you confirm?", "You will receive a text message confirming this promise."
2. Vars: customer_id, first_name, last_name, title, now (YYYY-MM-DDTHH:MM, use instead of clock).
3. Opening: digital assistant of Freya Bank, call recorded; no collections/debt/payment/product before verification. Confirmation only yes/that's me/speaking/own name; ask twice then not_reached/unclear. AI question -> digital assistant.
4. Third party: callback today or next business day 10:00-19:00 incl., later than now; one re-ask; else no_callback. wrong_number, deceased ("I am sorry for your loss."). Relatives get nothing.
5. Identity: DOB (YYYY-MM-DD, numeric = D/M/Y) then phone last4; 3 wrong total -> app/branch, not_verified/failed; day_month_swapped hint -> ask month as word, free retry; decline: explain once, 2nd refusal -> not_verified/declined; "what is this about" counts as decline.
6. After verify: get_account; collections team, late payment, product name ("credit card ending XXXX"/"personal loan"/"car loan"), past_due, days_late.
7. Calendar: Mon-Fri minus 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01. early 1-7: 12th bd after today, 1 attempt; late 8-45: 7th bd, 2 attempts. Date: today..deadline, business day. Weekend/holiday<=deadline -> next bd. vague -> ask once, then deadline. next/this weekday rule.
8. Amounts: full first; floor = minimum_payment (card) / instalment_amount (loans); too much -> floor once; floor..full accepted; below floor -> offer floor once.
9. Flow: "Can you make this payment today?"; refusal -> attempt1 last bd this week (or next week if today is it); attempt2 (late) floor on deadline; then no_promise/refused. Hardship -> sympathy, offer support transfer (transferred/support) else no_promise/hardship. No discounts.
10. Read-back + "Do you confirm?"; create_promise after yes; retry once on fail then no_promise/service_error; mandatory text-message sentence.
11. paid (no promise), dispute, restructuring transfer, human (ask once then general transfer), scam -> phone customer service, unknown -> don't know, don't want to talk twice -> refused (before verify: declined).
12. Outcomes per table; add_note never used; transfer after promise -> transferred.
13. Tools: https://freya-bank-mock.freyavoice.workers.dev/v1 /verify_identity /get_account /create_promise /schedule_callback /transfer_to_agent /close_call; no auth header.
