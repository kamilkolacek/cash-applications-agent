"""The deterministic half of EVALS.md: every deposit gets the expected outcome."""

import pytest

from cashapp.evals import grade_engine, grade_judgment, load_key
from tests.conftest import SAMPLE, write_resolutions


def test_answer_key_covers_every_deposit(inputs):
    assert set(load_key()) == {d.deposit_id for d in inputs.deposits}


def test_engine_matches_answer_key(run_dir):
    results = grade_engine(run_dir)
    failed = [r for r in results if not r["pass"]]
    assert not failed, failed
    assert len(results) == 38


@pytest.mark.parametrize("case", [f"E{i:02d}" for i in range(1, 17)])
def test_planted_case(run_dir, case):
    rows = [r for r in grade_engine(run_dir) if r["case"] == case]
    assert rows and all(r["pass"] for r in rows), rows


def test_sample_resolutions_pass_judgment_key(run_dir, resolutions):
    write_resolutions(run_dir, resolutions)
    results = grade_judgment(run_dir)
    assert len(results) == 10
    assert all(r["pass"] and r["best"] for r in results), results


def test_judgment_grader_catches_a_bad_choice(run_dir, resolutions):
    for x in resolutions["resolutions"]:
        if x["exception_id"] == "EX-DEP-20261116-021":
            x["option_id"] = "ON_ACCOUNT_TO_CANDIDATE"  # cash on a look-alike customer
    write_resolutions(run_dir, resolutions)
    bad = [r for r in grade_judgment(run_dir) if not r["pass"]]
    assert [r["case"] for r in bad] == ["E12"]


def test_committed_sample_is_graded_clean():
    text = (SAMPLE / "evals.md").read_text()
    assert "Engine: 38/38" in text and "Judgment: 10/10" in text
