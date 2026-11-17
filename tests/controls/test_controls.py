"""Controls: nothing gets posted without valid resolutions, an intact journal and a person."""

import csv
import json
from decimal import Decimal

import pytest

from cashapp.run import RunError, approve, finalize, read_state, reject, run_engine
from cashapp.synthetic import VALUE_DATE
from cashapp.traceability import untraceable
from tests.conftest import SAMPLE, write_resolutions


def _ok(run_dir):
    return f"APPROVE {run_dir.name}"


def test_validation_failure_stops_the_run(workspace):
    data, runs = workspace
    p = data / f"bank_statement_{VALUE_DATE}.json"
    stmt = json.loads(p.read_text())
    stmt["credit_total"] = "1.00"
    p.write_text(json.dumps(stmt))
    run_dir = run_engine(VALUE_DATE, data_dir=data, runs_dir=runs)
    assert read_state(run_dir)["status"] == "FAILED_VALIDATION"
    assert not (run_dir / "match_results.csv").exists()


def test_finalize_requires_resolutions(run_dir):
    with pytest.raises(RunError, match="need resolutions.json"):
        finalize(run_dir)


def test_finalize_rejects_invented_option(run_dir, resolutions):
    resolutions["resolutions"][0]["option_id"] = "WRITE_OFF"
    write_resolutions(run_dir, resolutions)
    with pytest.raises(RunError, match="not one of the engine's options"):
        finalize(run_dir)


def test_finalize_rejects_missing_or_thin_rationale(run_dir, resolutions):
    resolutions["resolutions"][0]["rationale"] = "ok"
    resolutions["resolutions"].pop()
    write_resolutions(run_dir, resolutions)
    with pytest.raises(RunError) as e:
        finalize(run_dir)
    assert "too short" in str(e.value) and "unresolved" in str(e.value)


def test_edited_exceptions_file_cannot_change_amounts(run_dir, resolutions):
    p = run_dir / "exceptions.json"
    doc = json.loads(p.read_text())
    for ex in doc["exceptions"]:
        for opt in ex["options"]:
            for a in opt["plan"]["applications"]:
                a["amount"] = "1.00"
    p.write_text(json.dumps(doc))
    write_resolutions(run_dir, resolutions)
    finalize(run_dir)
    lines = list(csv.DictReader((run_dir / "journal_entries.csv").open()))
    assert all(x["debit"] != "1.00" and x["credit"] != "1.00" for x in lines)


def test_changed_inputs_block_finalize(workspace, resolutions):
    data, runs = workspace
    run_dir = run_engine(VALUE_DATE, data_dir=data, runs_dir=runs)
    with (data / "ar_open_items.csv").open("a") as fh:
        fh.write("INV-99999,INV,C001,2026-11-01,2026-12-01,PO-X,1.00,1.00,OPEN,,\n")
    write_resolutions(run_dir, resolutions)
    with pytest.raises(RunError, match="Input files changed"):
        finalize(run_dir)


def test_every_entry_balances(run_dir, resolutions):
    write_resolutions(run_dir, resolutions)
    finalize(run_dir)
    by_je: dict[str, Decimal] = {}
    for x in csv.DictReader((run_dir / "journal_entries.csv").open()):
        by_je[x["je_id"]] = (
            by_je.get(x["je_id"], Decimal(0)) + Decimal(x["debit"]) - Decimal(x["credit"])
        )
    assert by_je and all(v == 0 for v in by_je.values())


@pytest.fixture
def finalized(run_dir, resolutions):
    write_resolutions(run_dir, resolutions)
    finalize(run_dir)
    return run_dir


@pytest.mark.parametrize("name", ["claude", "Agent", "AI", ""])
def test_approval_needs_a_named_person(finalized, name):
    with pytest.raises(RunError, match="not an accepted approver"):
        approve(finalized, name, _ok(finalized))
    assert not (finalized / "erp_import.csv").exists()


def test_approval_needs_exact_confirmation(finalized):
    with pytest.raises(RunError, match="Confirmation must be exactly"):
        approve(finalized, "Dana Controller", "yes")


def test_tampered_journal_cannot_be_approved(finalized):
    p = finalized / "journal_entries.csv"
    p.write_text(p.read_text().replace("Relieve unapplied cash", "Relieve unapplied cash.", 1))
    with pytest.raises(RunError, match="changed after it was built"):
        approve(finalized, "Dana Controller", _ok(finalized))


def test_approval_produces_erp_file_and_locks_the_run(finalized, resolutions):
    out = approve(finalized, "Dana Controller", _ok(finalized))
    assert out.exists()
    rows = list(csv.DictReader(out.open()))
    assert rows and {r["approved_by"] for r in rows} == {"Dana Controller"}
    assert read_state(finalized)["status"] == "APPROVED"
    with pytest.raises(RunError):
        approve(finalized, "Dana Controller", _ok(finalized))
    with pytest.raises(RunError, match="can no longer be changed"):
        finalize(finalized)
    steps = [json.loads(x)["step"] for x in (finalized / "audit.jsonl").read_text().splitlines()]
    assert steps == [
        "run_started",
        "validation",
        "matching",
        "resolutions_accepted",
        "journal_built",
        "approved",
    ]


def test_rejection_produces_no_erp_file(finalized):
    reject(finalized, "Dana Controller", "Hold Pinecrest until they confirm")
    assert read_state(finalized)["status"] == "REJECTED"
    assert not (finalized / "erp_import.csv").exists()


def test_traceability_flags_invented_figures():
    text = "Applied $6,143,235.39 (99.3%), roughly $6.1M, and $1,000,000.00 more at 12.5%."
    assert untraceable(text, SAMPLE) == ["$1,000,000.00", "12.5%"]


def test_committed_sample_is_pending_approval():
    state = json.loads((SAMPLE / "state.json").read_text())
    assert state["status"] == "PENDING_APPROVAL"
    assert not (SAMPLE / "erp_import.csv").exists()
    assert untraceable((SAMPLE / "summary.md").read_text(), SAMPLE) == []
