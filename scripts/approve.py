"""Step 3 (human only): approve or reject a run. Approval writes erp_import.csv.

Claude Code is denied permission to run this script (.claude/settings.json).

  python scripts/approve.py --approver "Jane Doe"            # prompts for confirmation
  python scripts/approve.py --approver "Jane Doe" --reject "reason"
"""

import argparse
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from cashapp.run import RunError, approve, describe, latest_run, read_state, reject

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("run_dir", nargs="?", help="run directory (default: latest)")
    ap.add_argument("--approver", required=True, help="your full name")
    ap.add_argument("--reject", metavar="REASON", help="reject the run instead of approving")
    args = ap.parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else latest_run()
    print(describe(run_dir))
    try:
        if args.reject:
            reject(run_dir, args.approver, args.reject)
            print("REJECTED. Nothing will be posted.")
            sys.exit(0)
        run_id = read_state(run_dir)["run_id"]
        print(f"Review {run_dir}/cash_application_*.xlsx before approving.")
        confirmation = input(f"Type 'APPROVE {run_id}' to approve: ")
        out = approve(run_dir, args.approver, confirmation)
    except (RunError, EOFError) as e:
        print(f"NOT APPROVED: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"APPROVED by {args.approver}. ERP import file: {out}")
