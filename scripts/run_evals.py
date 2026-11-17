"""Grade a run against the answer key and write evals.md into the run directory.

python scripts/run_evals.py              # latest run
python scripts/run_evals.py --fresh      # new engine run on the synthetic data, then grade
"""

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from cashapp.evals import scorecard
from cashapp.run import latest_run, run_engine
from cashapp.synthetic import VALUE_DATE

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--fresh", action="store_true", help="start a new engine run first")
    args = ap.parse_args()
    if args.fresh:
        run_dir = run_engine(VALUE_DATE)
    else:
        run_dir = Path(args.run_dir) if args.run_dir else latest_run()
    text, ok = scorecard(run_dir)
    (run_dir / "evals.md").write_text(text)
    print(text)
    sys.exit(0 if ok else 1)
