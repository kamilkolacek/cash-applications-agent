import json
import shutil
from pathlib import Path

import pytest

from cashapp.config import ROOT, load_config
from cashapp.data import load_inputs
from cashapp.run import run_engine
from cashapp.synthetic import VALUE_DATE

SAMPLE = ROOT / "docs" / "examples" / "sample_run"


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def inputs():
    return load_inputs(ROOT / "data" / "synthetic", VALUE_DATE)


@pytest.fixture
def workspace(tmp_path: Path):
    """A private copy of the synthetic data and an empty runs directory."""
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "synthetic", data)
    runs = tmp_path / "runs"
    return data, runs


@pytest.fixture
def run_dir(workspace):
    data, runs = workspace
    return run_engine(VALUE_DATE, data_dir=data, runs_dir=runs)


@pytest.fixture
def resolutions():
    return json.loads((SAMPLE / "resolutions.json").read_text())


def write_resolutions(run_dir: Path, doc: dict) -> None:
    (run_dir / "resolutions.json").write_text(json.dumps(doc, indent=2))
