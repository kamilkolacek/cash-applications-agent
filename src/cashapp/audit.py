"""Append-only audit log for each run, plus file fingerprints."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from cashapp.config import ROOT


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprints(paths: list[Path]) -> dict[str, str]:
    return {p.name: sha256(p) for p in paths}


def code_version() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "uncommitted"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def log(run_dir: Path, step: str, actor: str, detail: dict) -> None:
    """Append one event. Never rewrites earlier lines."""
    event = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "run_id": run_dir.name,
        "step": step,
        "actor": actor,
        **detail,
    }
    with (run_dir / "audit.jsonl").open("a") as fh:
        fh.write(json.dumps(event, sort_keys=False) + "\n")
