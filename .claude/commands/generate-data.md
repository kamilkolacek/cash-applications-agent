---
description: Rebuild the synthetic Lumina Streaming Co. dataset and eval answer key
---

Run `python scripts/generate_data.py`. It is deterministic (fixed seed), so the files
should not change unless the generator did. Report the deposit count and total, then run
`python scripts/run_evals.py --fresh` and confirm the engine score is 38/38.
