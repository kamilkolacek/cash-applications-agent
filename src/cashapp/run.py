"""Run lifecycle: match -> resolve exceptions -> human approval.

States (state.json):
  FAILED_VALIDATION      inputs did not tie out; nothing matched
  AWAITING_RESOLUTION    engine ran; exceptions need a recommended resolution
  PENDING_APPROVAL       every deposit has a plan; journal is built and fingerprinted
  APPROVED / REJECTED    a named person decided; only APPROVED produces an ERP import file
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from cashapp import audit
from cashapp.config import ROOT, Config, load_config
from cashapp.data import Inputs, load_inputs, validate
from cashapp.facts import facts_md, figures
from cashapp.matching import AUTO, EXCEPTION, Plan, Result, match_all
from cashapp.money import ZERO, D, fmt, s
from cashapp.postings import ar_after, check_plans, journal_lines

DATA_DIR = ROOT / "data" / "synthetic"
RUNS_DIR = ROOT / "outputs" / "runs"
MIN_RATIONALE = 40


class RunError(RuntimeError):
    pass


# --------------------------------------------------------------------------- io


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n")


def read_state(run_dir: Path) -> dict:
    return json.loads((run_dir / "state.json").read_text())


def write_state(run_dir: Path, state: dict) -> None:
    write_json(run_dir / "state.json", state)


def new_run_dir(value_date: str, runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    n = len(list(runs_dir.glob(f"{value_date}_r*"))) + 1
    run_dir = runs_dir / f"{value_date}_r{n:02d}"
    run_dir.mkdir()
    return run_dir


# --------------------------------------------------------------------------- serializers


def result_row(r: Result, inputs: Inputs, plan: Plan | None, decision: str = "") -> dict:
    cust = inputs.customers.get(r.customer_id)
    p = plan or r.plan
    return {
        "deposit_id": r.deposit.deposit_id,
        "method": r.deposit.method,
        "amount": s(r.deposit.amount),
        "payer_name": r.deposit.payer_name,
        "customer_id": r.customer_id,
        "customer_name": cust.name if cust else "",
        "status": r.status,
        "rule": r.rule,
        "exception_type": r.exception_type,
        "confidence": f"{r.confidence:.2f}",
        "decision": decision or ("ENGINE_AUTO" if r.status == AUTO else "PENDING"),
        "docs": "|".join(d for d, _ in p.applications) if p else "",
        "cash_applied": s(p.applied) if p else "",
        "adjustments": s(sum((a.amount for a in p.adjustments), ZERO)) if p else "",
        "on_account": s(p.on_account) if p else "",
        "unapplied": s(p.unapplied) if p else "",
        "evidence": " | ".join(r.evidence),
    }


def exception_record(r: Result, inputs: Inputs) -> dict:
    cust = inputs.customers.get(r.customer_id)
    return {
        "exception_id": r.exception_id,
        "deposit_id": r.deposit.deposit_id,
        "exception_type": r.exception_type,
        "amount": s(r.deposit.amount),
        "method": r.deposit.method,
        "payer_name": r.deposit.payer_name,
        "remittance_text": r.deposit.remittance_text,
        "customer_id": r.customer_id,
        "customer_name": cust.name if cust else "",
        "evidence": r.evidence,
        "options": [o.to_dict() for o in r.options],
    }


# --------------------------------------------------------------------------- step 1: match


def run_engine(
    value_date: str,
    data_dir: Path = DATA_DIR,
    runs_dir: Path = RUNS_DIR,
    cfg: Config | None = None,
) -> Path:
    cfg = cfg or load_config()
    inputs = load_inputs(data_dir, value_date)
    run_dir = new_run_dir(value_date, runs_dir)
    hashes = audit.fingerprints(inputs.files)
    state = {
        "run_id": run_dir.name,
        "value_date": value_date,
        "company": cfg.company,
        "data_dir": _portable(data_dir),
        "input_hashes": hashes,
        "code_version": audit.code_version(),
    }
    audit.log(run_dir, "run_started", "engine", {"inputs": hashes, "code": state["code_version"]})

    v = validate(inputs)
    write_json(run_dir / "validation.json", v)
    audit.log(run_dir, "validation", "engine", {"verdict": v["verdict"]})
    if v["verdict"] == "FAIL":
        state["status"] = "FAILED_VALIDATION"
        write_state(run_dir, state)
        _set_latest(runs_dir, run_dir)
        return run_dir

    results = match_all(inputs, cfg)
    write_csv(run_dir / "match_results.csv", [result_row(r, inputs, None) for r in results])
    exc = [exception_record(r, inputs) for r in results if r.status == EXCEPTION]
    write_json(run_dir / "exceptions.json", {"run_id": run_dir.name, "exceptions": exc})
    f = figures(results, inputs, cfg)
    write_json(run_dir / "summary.json", f)
    (run_dir / "facts.md").write_text(facts_md(f, results))
    audit.log(
        run_dir,
        "matching",
        "engine",
        {"auto": f["auto_count"], "exceptions": f["exception_count"]},
    )
    state["status"] = "AWAITING_RESOLUTION" if exc else "READY_TO_FINALIZE"
    write_state(run_dir, state)
    _set_latest(runs_dir, run_dir)
    return run_dir


def _portable(path: Path) -> str:
    """Store paths inside the project relative to it, so a committed run works anywhere."""
    p = path.resolve()
    try:
        return str(p.relative_to(ROOT.resolve()))
    except ValueError:
        return str(p)


def _set_latest(runs_dir: Path, run_dir: Path) -> None:
    (runs_dir / "LATEST").write_text(run_dir.name + "\n")


def latest_run(runs_dir: Path = RUNS_DIR) -> Path:
    p = runs_dir / "LATEST"
    if not p.exists():
        raise RunError("No runs yet. Run scripts/run_cash_app.py first.")
    return runs_dir / p.read_text().strip()


# --------------------------------------------------------------------------- step 2: resolve


def _reload(run_dir: Path, cfg: Config) -> tuple[dict, Inputs, list[Result]]:
    """Re-run the deterministic engine on the same inputs, after checking they're unchanged.

    Options are taken from this fresh run, never from files in the run directory, so an
    edited exceptions.json cannot change an amount.
    """
    state = read_state(run_dir)
    data_dir = Path(state["data_dir"])
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    inputs = load_inputs(data_dir, state["value_date"])
    now = audit.fingerprints(inputs.files)
    if now != state["input_hashes"]:
        changed = [k for k in now if now[k] != state["input_hashes"].get(k)]
        raise RunError(f"Input files changed since the run: {', '.join(changed)}. Start a new run.")
    return state, inputs, match_all(inputs, cfg)


def finalize(run_dir: Path, cfg: Config | None = None) -> dict:
    """Validate resolutions.json, build final plans, journal, AR after, facts."""
    cfg = cfg or load_config()
    state, inputs, results = _reload(run_dir, cfg)
    if state["status"] not in ("AWAITING_RESOLUTION", "READY_TO_FINALIZE", "PENDING_APPROVAL"):
        raise RunError(f"Run is {state['status']}; it can no longer be changed.")

    exc = {r.exception_id: r for r in results if r.status == EXCEPTION}
    chosen: dict[str, str] = {}
    res_doc: dict = {"resolutions": []}
    res_path = run_dir / "resolutions.json"
    if exc:
        if not res_path.exists():
            raise RunError(f"{len(exc)} exceptions need resolutions.json before finalizing.")
        res_doc = json.loads(res_path.read_text())
        errors = []
        seen = set()
        for item in res_doc.get("resolutions", []):
            eid, oid = item.get("exception_id", ""), item.get("option_id", "")
            if eid not in exc:
                errors.append(f"{eid}: not an exception in this run")
                continue
            if eid in seen:
                errors.append(f"{eid}: resolved more than once")
            seen.add(eid)
            if oid not in {o.option_id for o in exc[eid].options}:
                errors.append(f"{eid}: option '{oid}' is not one of the engine's options")
            if len(item.get("rationale", "").strip()) < MIN_RATIONALE:
                errors.append(f"{eid}: rationale missing or too short")
            chosen[eid] = oid
        missing = sorted(set(exc) - seen)
        if missing:
            errors.append(f"unresolved: {', '.join(missing)}")
        if errors:
            audit.log(run_dir, "resolutions_rejected", "engine", {"errors": errors})
            raise RunError("resolutions.json rejected:\n  - " + "\n  - ".join(errors))

    plans: dict[str, Plan] = {}
    decisions: dict[str, str] = {}
    for r in results:
        dep_id = r.deposit.deposit_id
        if r.status == AUTO:
            assert r.plan is not None
            plans[dep_id] = r.plan
            decisions[dep_id] = "ENGINE_AUTO"
        else:
            opt = next(o for o in r.options if o.option_id == chosen[r.exception_id])
            plans[dep_id] = opt.plan
            decisions[dep_id] = f"RECOMMENDED:{opt.option_id}"
    check_plans(plans, inputs)
    lines = journal_lines(plans, inputs, cfg)
    ar_rows = ar_after(plans, inputs)

    write_csv(
        run_dir / "applications.csv",
        [
            result_row(r, inputs, plans[r.deposit.deposit_id], decisions[r.deposit.deposit_id])
            for r in results
        ],
    )
    write_csv(run_dir / "journal_entries.csv", lines)
    write_csv(run_dir / "ar_after.csv", ar_rows)
    f = figures(results, inputs, cfg, plans, ar_rows)
    dr = sum((D(x["debit"]) for x in lines), ZERO)
    f["journal_lines"] = len(lines)
    f["journal_entries"] = len({x["je_id"] for x in lines})
    f["journal_total_debits"] = f"{dr:.2f}"
    write_json(run_dir / "summary.json", f)
    (run_dir / "facts.md").write_text(facts_md(f, results, chosen))

    from cashapp.workbook import build_workbook

    build_workbook(run_dir, results, inputs, plans, decisions, lines, ar_rows, f, res_doc, cfg)

    state["status"] = "PENDING_APPROVAL"
    state["approval_basis_sha256"] = audit.sha256(run_dir / "journal_entries.csv")
    write_state(run_dir, state)
    audit.log(
        run_dir,
        "resolutions_accepted",
        res_doc.get("prepared_by", "unknown"),
        {"resolutions": chosen},
    )
    audit.log(
        run_dir,
        "journal_built",
        "engine",
        {
            "entries": f["journal_entries"],
            "lines": f["journal_lines"],
            "total_debits": f["journal_total_debits"],
            "journal_sha256": state["approval_basis_sha256"],
        },
    )
    return f


# --------------------------------------------------------------------------- step 3: approve


def approve(run_dir: Path, approver: str, confirmation: str, cfg: Config | None = None) -> Path:
    """Human approval gate. Produces the ERP import file; nothing is posted before this."""
    cfg = cfg or load_config()
    state = read_state(run_dir)
    if state["status"] != "PENDING_APPROVAL":
        raise RunError(f"Run is {state['status']}; only PENDING_APPROVAL runs can be approved.")
    name = approver.strip()
    if name.lower() in cfg.blocked_approvers or len(name) < 3:
        raise RunError(f"'{approver}' is not an accepted approver. Approval needs a named person.")
    expected = f"APPROVE {state['run_id']}"
    if confirmation.strip() != expected:
        raise RunError(f"Confirmation must be exactly: {expected}")
    _, inputs, _ = _reload(run_dir, cfg)  # inputs unchanged since the run
    journal = run_dir / "journal_entries.csv"
    if audit.sha256(journal) != state.get("approval_basis_sha256"):
        raise RunError("journal_entries.csv changed after it was built. Re-run finalize.")
    with journal.open() as fh:
        lines = list(csv.DictReader(fh))
    dr = sum((D(x["debit"]) for x in lines), ZERO)
    cr = sum((D(x["credit"]) for x in lines), ZERO)
    if dr != cr:
        raise RunError("Journal does not balance.")

    erp = [{**x, "approved_by": name, "batch_id": f"CASHAPP-{state['run_id']}"} for x in lines]
    write_csv(run_dir / "erp_import.csv", erp)
    record = {
        "run_id": state["run_id"],
        "decision": "APPROVED",
        "approver": name,
        "journal_sha256": state["approval_basis_sha256"],
        "erp_import_sha256": audit.sha256(run_dir / "erp_import.csv"),
        "entries": len({x["je_id"] for x in lines}),
        "total_debits": f"{dr:.2f}",
    }
    write_json(run_dir / "approval.json", record)
    state["status"] = "APPROVED"
    state["approved_by"] = name
    write_state(run_dir, state)
    audit.log(run_dir, "approved", f"human:{name}", record)
    return run_dir / "erp_import.csv"


def reject(run_dir: Path, approver: str, reason: str, cfg: Config | None = None) -> None:
    cfg = cfg or load_config()
    state = read_state(run_dir)
    if state["status"] != "PENDING_APPROVAL":
        raise RunError(f"Run is {state['status']}; only PENDING_APPROVAL runs can be rejected.")
    if approver.strip().lower() in cfg.blocked_approvers:
        raise RunError("Rejection needs a named person.")
    state["status"] = "REJECTED"
    write_state(run_dir, state)
    write_json(
        run_dir / "approval.json", {"decision": "REJECTED", "approver": approver, "reason": reason}
    )
    audit.log(run_dir, "rejected", f"human:{approver}", {"reason": reason})


def describe(run_dir: Path) -> str:
    st = read_state(run_dir)
    f = (
        json.loads((run_dir / "summary.json").read_text())
        if (run_dir / "summary.json").exists()
        else {}
    )
    parts = [f"{run_dir.name}: {st['status']}"]
    if f:
        parts.append(
            f"{f['deposit_count']} deposits {fmt_d(f['deposit_total'])}; "
            f"{f['auto_count']} auto, {f['exception_count']} exceptions"
        )
    return " | ".join(parts)


def fmt_d(x: str) -> str:
    return fmt(D(x))


__all__ = ["run_engine", "finalize", "approve", "reject", "latest_run", "RunError", "s"]
