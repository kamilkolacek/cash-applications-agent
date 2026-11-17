"""Grade a run against tests/evals/answer_key.yaml.

Two layers:
  engine   - every deposit gets the expected status, rule or exception type, and documents.
  judgment - every exception gets an acceptable recommended option, and the rationale
             mentions the evidence that should drive it.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from cashapp.config import ROOT

KEY = ROOT / "tests" / "evals" / "answer_key.yaml"


def load_key(path: Path = KEY) -> dict:
    return yaml.safe_load(path.read_text())["deposits"]


def grade_engine(run_dir: Path, key: dict | None = None) -> list[dict]:
    key = key or load_key()
    rows = {r["deposit_id"]: r for r in csv.DictReader((run_dir / "match_results.csv").open())}
    out = []
    for dep_id, k in key.items():
        r = rows.get(dep_id)
        if r is None:
            out.append(
                {"deposit_id": dep_id, "case": k["case"], "pass": False, "detail": "missing"}
            )
            continue
        if k["status"] == "AUTO":
            ok = (
                r["status"] == "AUTO"
                and r["rule"] == k["rule"]
                and sorted(r["docs"].split("|")) == sorted(k["docs"])
            )
            want = f"AUTO {k['rule']} {'+'.join(sorted(k['docs']))}"
            got = f"{r['status']} {r['rule'] or r['exception_type']} {'+'.join(sorted(r['docs'].split('|')))}"
        else:
            ok = r["status"] == "EXCEPTION" and r["exception_type"] == k["exception_type"]
            want = f"EXCEPTION {k['exception_type']}"
            got = f"{r['status']} {r['exception_type'] or r['rule']}"
        out.append(
            {"deposit_id": dep_id, "case": k["case"], "pass": ok, "expected": want, "got": got}
        )
    return out


def grade_judgment(run_dir: Path, key: dict | None = None) -> list[dict]:
    key = key or load_key()
    path = run_dir / "resolutions.json"
    res = (
        {x["exception_id"]: x for x in json.loads(path.read_text()).get("resolutions", [])}
        if path.exists()
        else {}
    )
    out = []
    for dep_id, k in key.items():
        if k["status"] != "EXCEPTION":
            continue
        x = res.get(f"EX-{dep_id}")
        if x is None:
            out.append(
                {
                    "case": k["case"],
                    "deposit_id": dep_id,
                    "pass": False,
                    "best": False,
                    "detail": "no resolution",
                }
            )
            continue
        opt = x.get("option_id", "")
        text = (x.get("rationale", "") + " " + x.get("follow_up", "")).lower()
        missing = [m for m in k.get("rationale_mentions", []) if m.lower() not in text]
        ok = opt in k["acceptable_options"] and not missing
        out.append(
            {
                "case": k["case"],
                "deposit_id": dep_id,
                "pass": ok,
                "best": opt == k["expected_option"],
                "expected": k["expected_option"],
                "got": opt,
                "detail": f"rationale missing: {missing}" if missing else "",
            }
        )
    return sorted(out, key=lambda r: r["case"])


def scorecard(run_dir: Path) -> tuple[str, bool]:
    key = load_key()
    eng = grade_engine(run_dir, key)
    jud = grade_judgment(run_dir, key) if (run_dir / "resolutions.json").exists() else []
    planted = sorted((r for r in eng if r["case"] != "E00"), key=lambda r: r["case"])
    routine = [r for r in eng if r["case"] == "E00"]
    lines = [
        f"# Eval scorecard: {run_dir.name}",
        "",
        f"Engine: {sum(r['pass'] for r in eng)}/{len(eng)} deposits as expected "
        f"(planted cases {sum(r['pass'] for r in planted)}/{len(planted)}, "
        f"routine payments {sum(r['pass'] for r in routine)}/{len(routine)})",
    ]
    if jud:
        lines.append(
            f"Judgment: {sum(r['pass'] for r in jud)}/{len(jud)} exceptions resolved acceptably "
            f"({sum(r['best'] for r in jud)}/{len(jud)} chose the preferred option)"
        )
    lines += [
        "",
        "## Engine (planted cases)",
        "",
        "| Case | Deposit | Expected | Got | Result |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['case']} | {r['deposit_id']} | {r['expected']} | {r['got']} | "
        f"{'PASS' if r['pass'] else 'FAIL'} |"
        for r in planted
    ]
    fails = [r for r in routine if not r["pass"]]
    lines += ["", f"Routine payments: {len(routine) - len(fails)}/{len(routine)} pass"]
    lines += [f"- FAIL {r['deposit_id']}: expected {r['expected']}, got {r['got']}" for r in fails]
    if jud:
        lines += [
            "",
            "## Judgment (exceptions)",
            "",
            "| Case | Deposit | Preferred | Recommended | Result |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {r['case']} | {r['deposit_id']} | {r.get('expected', '')} | {r.get('got', '')} | "
            f"{'PASS' if r['pass'] else 'FAIL'}{' ' + r['detail'] if r['detail'] else ''} |"
            for r in jud
        ]
    all_pass = all(r["pass"] for r in eng) and all(r["pass"] for r in jud)
    return "\n".join(lines) + "\n", all_pass
