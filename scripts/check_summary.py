"""Check that every $ figure and % in a run's summary.md traces to its artifacts."""

import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from cashapp.run import latest_run
from cashapp.traceability import untraceable

if __name__ == "__main__":
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()
    summary = run_dir / "summary.md"
    if not summary.exists():
        print(f"No summary.md in {run_dir}", file=sys.stderr)
        sys.exit(1)
    bad = untraceable(summary.read_text(), run_dir)
    if bad:
        print(f"FAIL: untraceable figures: {', '.join(bad)}", file=sys.stderr)
        sys.exit(1)
    print(f"PASS: every figure in {summary.name} traces to the run artifacts")
