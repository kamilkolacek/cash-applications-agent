---
description: Walk through the exception queue for the latest run, one exception at a time
argument-hint: "[exception_id]"
---

Use the `exception-resolution` skill.

1. Find the latest run: `python scripts/status.py`. RUN is `outputs/runs/<run_id>/`.
2. Read `RUN/exceptions.json` (and `RUN/resolutions.json` if it exists).
3. For the exception in `$ARGUMENTS`, or each exception in turn if none is given, show:
   payer, amount, method and remittance text; the evidence; each option with what it
   would do; and your recommended option with a one-paragraph rationale.
4. If the user overrides a recommendation, record their choice in `RUN/resolutions.json`
   with their reason in the rationale and `"owner"` set to who decided. Only options the
   engine offered are allowed.
5. If the run was already finalized, tell the user to re-run
   `python scripts/finalize_run.py RUN` after changes. That works until a person approves.

Never run `scripts/approve.py`.
