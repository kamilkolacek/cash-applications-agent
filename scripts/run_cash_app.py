"""Step 1: validate inputs and match the day's deposits. Prints the run directory last."""

import argparse
import sys

import _bootstrap  # noqa: F401
from cashapp.run import describe, run_engine
from cashapp.synthetic import VALUE_DATE

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=VALUE_DATE, help="bank value date (YYYY-MM-DD)")
    args = ap.parse_args()
    run_dir = run_engine(args.date)
    print(describe(run_dir))
    if "FAILED" in describe(run_dir):
        print("Validation failed; see validation.json. Nothing was matched.", file=sys.stderr)
        print(run_dir)
        sys.exit(1)
    print(run_dir)
