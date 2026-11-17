---
description: Daily cash application - match deposits, resolve exceptions, independent review, finalize, approver summary
argument-hint: "[--date YYYY-MM-DD]"
---

Run cash application for the day end to end. Use the `cash-application` and
`exception-resolution` skills.

1. **Match.** Run `python scripts/run_cash_app.py $ARGUMENTS`. The last line printed is
   the run directory; call it RUN. If the status is `FAILED_VALIDATION`, read
   `RUN/validation.json`, report the failed checks, and stop.
2. **Read the queue.** Read `RUN/facts.md` and `RUN/exceptions.json`. If there are no
   exceptions, skip to step 5.
3. **Recommend.** For every exception, follow the `exception-resolution` playbook for its
   type and choose one `option_id` from that exception's `options`. Write
   `RUN/resolutions.json`:
   ```json
   {"run_id": "<RUN name>", "prepared_by": "claude",
    "resolutions": [{"exception_id": "EX-...", "option_id": "...",
                     "rationale": "...", "follow_up": "...", "owner": "..."}]}
   ```
   The rationale cites the evidence (references, amounts as written in `exceptions.json`,
   dates, customer-master relationships). `follow_up` is the next action for a person;
   `owner` is the team (AR, Ad Sales, Partner Finance, Treasury).
4. **Independent review.** Use the `resolution-reviewer` subagent on RUN. It writes
   `RUN/review.md`. For each CHALLENGE, either change the resolution or add the reason you
   disagree to the rationale. Do not accept a challenge that asks for an option the engine
   did not offer.
5. **Finalize.** Run `python scripts/finalize_run.py RUN`. If it rejects the resolutions,
   fix them and run it again. The run is now `PENDING_APPROVAL`.
6. **Summary.** Write `RUN/summary.md` from the template in the `cash-application` skill,
   using figures exactly as written in `RUN/facts.md`. A hook checks every figure; if it
   blocks, fix the figure from `facts.md`. Then run `python scripts/check_summary.py RUN`.
7. **Report back** in under 120 words: deposits and total, auto-match rate, exceptions by
   outcome, cash left unapplied, the reviewer's verdict, and the approval step:
   `python scripts/approve.py RUN --approver "<name>"` (for a person to run; never run it).
