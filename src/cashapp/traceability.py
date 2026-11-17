"""Every $ figure and percentage in summary.md must exist in the run's artifacts.

Standard library only, so the Claude Code hook can import it without the project venv.
A figure matches if some artifact value rounds to it at the precision written:
"$3,400.00" matches 3400.00; "$6.19M" matches 6,188,951.06; "73.7%" matches "73.7%".
Signs are ignored.
"""

from __future__ import annotations

import contextlib
import csv
import json
import re
from pathlib import Path

MONEY = re.compile(
    r"\$\s?(?P<num>\d[\d,]*(?:\.\d+)?)\s?(?P<unit>[MK]\b|million\b|thousand\b)?", re.IGNORECASE
)
PCT = re.compile(r"(?<![\w.])(?P<num>\d+(?:\.\d+)?)\s?%")
NUM = re.compile(r"-?\d[\d,]*\.?\d*")
SCALE = {"m": 1e6, "million": 1e6, "k": 1e3, "thousand": 1e3}
SOURCES = (
    "facts.md",
    "summary.json",
    "exceptions.json",
    "applications.csv",
    "ar_after.csv",
    "journal_entries.csv",
    "match_results.csv",
)


def _dec(num: str) -> int:
    return len(num.split(".")[1]) if "." in num else 0


def figures(text: str) -> list[tuple[str, float, float, str]]:
    out = []
    for m in MONEY.finditer(text):
        num, unit = m.group("num"), (m.group("unit") or "").lower()
        scale = SCALE.get(unit, 1.0)
        out.append(
            (
                m.group(0).strip(),
                float(num.replace(",", "")) * scale,
                0.5 * 10 ** (-_dec(num)) * scale + 1e-6,
                "money",
            )
        )
    for m in PCT.finditer(text):
        num = m.group("num")
        out.append((m.group(0), float(num), 0.5 * 10 ** (-_dec(num)) + 1e-9, "pct"))
    return out


def _walk(obj: object, acc: list[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):  # noqa: UP038  (hook may run on older python3)
        acc.append(abs(float(obj)))
    elif isinstance(obj, str):
        for n in NUM.findall(obj.replace("$", "")):
            with contextlib.suppress(ValueError):
                acc.append(abs(float(n.replace(",", ""))))
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, acc)


def pool(run_dir: Path) -> list[float]:
    acc: list[float] = []
    for name in SOURCES:
        p = run_dir / name
        if not p.exists():
            continue
        if p.suffix == ".json":
            _walk(json.loads(p.read_text()), acc)
        elif p.suffix == ".csv":
            with p.open(newline="") as fh:
                for row in csv.DictReader(fh):
                    _walk(list(row.values()), acc)
        else:
            _walk(p.read_text(), acc)
    return acc


def untraceable(text: str, run_dir: Path) -> list[str]:
    values = pool(run_dir)
    bad = []
    for token, value, tol, _ in figures(text):
        if not any(abs(v - value) <= tol for v in values):
            bad.append(token)
    return sorted(set(bad))
