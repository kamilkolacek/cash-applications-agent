"""Show the state of the latest run (or a given run)."""

import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from cashapp.run import RUNS_DIR, describe, latest_run

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        for p in sorted(RUNS_DIR.glob("*_r*")):
            print(describe(p))
    else:
        print(describe(Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()))
