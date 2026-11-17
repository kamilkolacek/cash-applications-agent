"""Step 2: check resolutions.json against the engine's options and build the journal.

Leaves the run PENDING_APPROVAL. Nothing is posted.
"""

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from cashapp.money import D, fmt
from cashapp.postings import PlanError
from cashapp.run import RunError, finalize, latest_run

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", nargs="?", help="run directory (default: latest)")
    args = ap.parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else latest_run()
    try:
        f = finalize(run_dir)
    except (RunError, PlanError) as e:
        print(f"NOT FINALIZED: {e}", file=sys.stderr)
        sys.exit(1)
    print(
        f"{run_dir.name}: PENDING_APPROVAL | {f['journal_entries']} entries, "
        f"debits {fmt(D(f['journal_total_debits']))} | left unapplied {fmt(D(f['left_unapplied']))}"
    )
    print(run_dir)
