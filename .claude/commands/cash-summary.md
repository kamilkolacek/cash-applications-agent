---
description: Write or rewrite the approver summary for the latest finalized run
---

Use the `cash-application` skill.

1. Find the latest run with `python scripts/status.py`. It must be `PENDING_APPROVAL`
   (or later); if it is still `AWAITING_RESOLUTION`, say so and stop.
2. Read `RUN/facts.md`, `RUN/resolutions.json`, `RUN/review.md` (if present) and
   `RUN/validation.json`.
3. Write `RUN/summary.md` using `.claude/skills/cash-application/templates/summary.md`.
   Every figure comes from `facts.md` or `exceptions.json` as written.
4. Run `python scripts/check_summary.py RUN` and confirm it passes.
