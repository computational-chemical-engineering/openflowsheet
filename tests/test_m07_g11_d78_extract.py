"""G11 at C′ with D78's values from the registered extract (M07 spec §24.3, R-480).

D78's record (`g11-exp.json`, sha256 `afa7325a…`) is lost; `docs/derivations/scripts/
m07_g11_d78_extract.py` rebuilds the values `g11_coverage_v3.py` reads from it out of four
committed records. (i) runs the generator's own `--check` (its self-claims E1–E5). (ii) is S12.1:
at each alpha RC, the script's own `summarise` over the committed raw runs and the extract, and its
`inertness` over `--previous` without `--previous-runs` (D100's fallback), reproduce that RC's
committed summary exactly, except `G11v3-12` (not computed here) and `G11v3-11.stage_steps_from`,
which reads `"points"` where the record says `"raw runs"`.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "m07_g11_d78_extract.py"
EXTRACT = ROOT / "docs" / "derivations" / "scripts" / "m07_g11_d78_extract.json"
G11 = ROOT / "benchmarks" / "m02" / "g11_coverage_v3.py"
G11_COVERAGE = ROOT / "benchmarks" / "m02" / "g11-coverage.json"
PREVIOUS_GIT = "bd446ab:benchmarks/m02/g11-coverage-v3.json"
ALPHA_RCS = (
    "e0e198e4632224612671db5b07445639d272d6da",
    "cc73219a77f6a54579c8acb151ed6fae228c8a4c",
    "6fec82232e1c47308a5e1d67338058f352992800",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def g11() -> ModuleType:
    spec = importlib.util.spec_from_file_location("m07_g11_coverage_v3", G11)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def previous() -> Any:
    shown = subprocess.run(
        ["git", "show", PREVIOUS_GIT], cwd=ROOT, capture_output=True, check=True
    ).stdout
    return json.loads(shown)


def test_i_the_extract_generator_check_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("rc", ALPHA_RCS, ids=lambda rc: rc[:7])
def test_ii_s12_1_the_extract_replays_each_alpha_summary(
    g11: ModuleType, previous: Any, rc: str
) -> None:
    step12 = ROOT / "evidence" / "M07a" / rc / "rc" / "step12"
    record = _json(step12 / "g11-coverage-v3.json")
    runs = _json(step12 / "g11-coverage-v3.runs.json")
    computed = {
        **g11.summarise(runs, record["timing"], _json(G11_COVERAGE), _json(EXTRACT)),
        "G11v3-11": g11.inertness(runs, previous, None),
    }
    expected = copy.deepcopy(record["summary"])
    del expected["G11v3-12"]
    assert expected["G11v3-11"]["stage_steps_from"] == "raw runs"
    assert computed["G11v3-11"]["stage_steps_from"] == "points"
    expected["G11v3-11"]["stage_steps_from"] = "points"
    assert sorted(computed) == sorted(expected)
    for member in sorted(expected):
        assert computed[member] == expected[member], member
