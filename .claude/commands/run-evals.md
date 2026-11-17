---
description: Grade the latest run against the eval answer key (engine and judgment)
---

1. Run `python scripts/run_evals.py`. It grades the latest run and writes `RUN/evals.md`.
   You cannot read the answer key itself; the script grades for you.
2. Report the engine score, the judgment score (if `resolutions.json` exists), and any
   FAIL rows with expected vs got.
3. For a judgment FAIL, re-read that exception's evidence and explain what you missed.
   Do not change a finalized run's resolutions just to pass an eval; tell the user.
