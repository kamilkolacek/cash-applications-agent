"""PostToolUse hook: block a summary.md or resolutions.json rationale whose figures don't trace.

Fires after Write/Edit. Acts only on summary.md and resolutions.json inside a run directory.
Exit 2 returns the message on stderr to Claude so it can fix the file.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / "src"))

from cashapp.traceability import untraceable  # noqa: E402


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    path = Path(event.get("tool_input", {}).get("file_path", ""))
    if path.name not in ("summary.md", "resolutions.json") or not path.exists():
        return 0
    text = path.read_text()
    if path.suffix == ".json":
        try:
            items = json.loads(text).get("resolutions", [])
        except json.JSONDecodeError:
            print("resolutions.json is not valid JSON.", file=sys.stderr)
            return 2
        text = "\n".join(f"{x.get('rationale', '')} {x.get('follow_up', '')}" for x in items)
    bad = untraceable(text, path.parent)
    if not bad:
        return 0
    print(
        f"Blocked by number-traceability check: {', '.join(bad)} in {path.name} do not appear "
        f"in the run artifacts in {path.parent.name}/ (facts.md, summary.json, exceptions.json, "
        "*.csv). Use figures exactly as written there. Do not compute new totals in prose.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
