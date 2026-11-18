"""S19 W5 WO-1: the W5 gate mode (`scripts/w5_gate.py`, ruling `docs/briefs/S19-W5-ruling.md` 6.2).

Outside the gate (acceptance A2 of the WO-1 tooling brief): the subset rule of the tests tier
(W5-S6), the scope rule (W5-S1), the frozen exemption of `scripts/codehealth_frozen.py`, the
batch-file validation with each refusal, and batch P refused (W5-S2 is not implemented). The
tiers and sets are those of the base 94840fb3 (`w5_identity.py sets`: tiers 16/28/6/1).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import w5_gate as gate  # noqa: E402

BASE = "94840fb3a4bd7a26458dabc90a4143deb488cbc7"
PARENT = "977dd608"  # BASE's first parent's first parent: an ancestor, never a descendant
TOOL = ROOT / "scripts" / "w5_gate.py"
FROZEN = ROOT / "scripts" / "codehealth_frozen.py"
SRC = "src/openflowsheet"
PR_LIB = f"{SRC}/thermo/pr_lib.py"
CONTRIBUTOR = f"{SRC}/assessment/cost/contributor.py"
FEED = f"{SRC}/models/c1/feed.py"
SYN001 = f"{SRC}/thermo/syn001.py"


@pytest.fixture(scope="module")
def sets() -> dict[str, Any]:
    return gate.sets_at(BASE)


@pytest.fixture
def batch(sets: dict[str, Any]) -> dict[str, Any]:
    """Batch N as WO-1 fixes it: the 16 tier 1 files and `thermo/pr_lib.py`."""
    return {
        "batch": "N",
        "base": BASE,
        "max_tier": 2,
        "admitted": [*sets["tiers"]["1"], PR_LIB],
        "generator": ["scripts/registry_builtin.py"],
        "retarget": ["tests/test_t07_w5a_inspection.py"],
        "expected_failures": [
            "tests/test_a.py::test_identity",
            "tests/test_b.py::test_hash[x - y]",
        ],
        "standing_failures": ["tests/test_c.py::test_standing"],
    }


def _write(path: Path, document: Any) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


# -- the base's sets, as WO-1 names them -----------------------------------------------------------


def test_the_sets_at_the_base(sets: dict[str, Any]) -> None:
    assert [len(sets["tiers"][t]) for t in "1234"] == [16, 28, 6, 1]
    assert sets["tiers"]["4"] == [SYN001]
    assert CONTRIBUTOR in sets["tiers"]["1"]
    assert PR_LIB in sets["tiers"]["2"] and FEED in sets["tiers"]["2"]


# -- W5-S6: the tests tier's subset rule -----------------------------------------------------------


def test_s6_failures_inside_l_b_and_standing_pass(batch: dict[str, Any]) -> None:
    failed = {"tests/test_a.py::test_identity", "tests/test_c.py::test_standing"}
    code, lines = gate.tests_verdict(1, failed, batch)
    assert code == 0
    assert "EXPECTED-FAILED tests/test_a.py::test_identity" in lines
    assert "EXPECTED-NOT-FAILED tests/test_b.py::test_hash[x - y]" in lines
    assert "STANDING-FAILED tests/test_c.py::test_standing" in lines
    assert lines[-1].startswith("w5 tests (W5-S6) PASS")
    assert "expected failures failed 1/2" in lines[-1]


def test_s6_an_extra_failure_fails_naming_it(batch: dict[str, Any]) -> None:
    failed = {"tests/test_a.py::test_identity", "tests/test_d.py::test_new"}
    code, lines = gate.tests_verdict(1, failed, batch)
    assert code == 1
    assert "UNEXPECTED tests/test_d.py::test_new" in lines
    assert [line for line in lines if line.startswith("UNEXPECTED")] == [
        "UNEXPECTED tests/test_d.py::test_new"
    ]
    assert lines[-1].startswith("w5 tests (W5-S6) FAIL: 1 failure(s) outside L_B")


def test_s6_a_clean_run_passes_and_reports_no_expected_failure(batch: dict[str, Any]) -> None:
    code, lines = gate.tests_verdict(0, set(), batch)
    assert code == 0 and "expected failures failed 0/2" in lines[-1]


@pytest.mark.parametrize("exit_code", [2, 3, 124])
def test_s6_other_exit_codes_stay_failures(batch: dict[str, Any], exit_code: int) -> None:
    code, lines = gate.tests_verdict(exit_code, {"tests/test_a.py::test_identity"}, batch)
    assert code == exit_code and "not a test failure" in lines[-1]


def test_s6_exit_1_without_a_node_id_fails(batch: dict[str, Any]) -> None:
    code, lines = gate.tests_verdict(1, set(), batch)
    assert code == 1 and "no failed node id" in lines[-1]


def test_s6_the_node_ids_of_a_real_pytest_short_summary(tmp_path: Path) -> None:
    """pytest's own `-rsfE` output: FAILED and ERROR entries, a parameter id holding ' - ', and
    a captured log line starting with ERROR outside the summary, which is not a node."""
    (tmp_path / "test_sample.py").write_text(
        "import logging\n"
        "import pytest\n"
        "def test_pass():\n    pass\n"
        "def test_fail():\n    logging.getLogger('x').error('noise')\n    assert False, 'a - b'\n"
        "@pytest.mark.parametrize('v', ['x - y'])\n"
        "def test_param(v):\n    assert not v\n"
        "@pytest.fixture\n"
        "def broken():\n    raise RuntimeError('fixture')\n"
        "def test_error(broken):\n    pass\n"
        "@pytest.mark.skip(reason='skipped')\n"
        "def test_skip():\n    pass\n",
        encoding="utf-8",
    )
    environment = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", "-rsfE"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 1
    assert gate.failed_nodes(done.stdout) == {
        "test_sample.py::test_fail",
        "test_sample.py::test_param[x - y]",
        "test_sample.py::test_error",
    }


# -- W5-S1: the scope rule -------------------------------------------------------------------------


def test_s1_admitted_paths_pass(batch: dict[str, Any], sets: dict[str, Any]) -> None:
    files = [CONTRIBUTOR, PR_LIB, "scripts/registry_builtin.py", "tests/test_t07_w5a_inspection.py"]
    assert gate.scope_problems(files, batch, sets["tiers"]["4"]) == []


def test_s1_a_tier_2_file_outside_admitted_fails_naming_it(
    batch: dict[str, Any], sets: dict[str, Any]
) -> None:
    problems = gate.scope_problems([CONTRIBUTOR, FEED], batch, sets["tiers"]["4"])
    assert problems == [f"{FEED}: outside the batch's admitted, generator and retarget sets"]


def test_s1_syn001_fails_even_when_admitted(batch: dict[str, Any], sets: dict[str, Any]) -> None:
    assert gate.scope_problems([SYN001], batch, sets["tiers"]["4"]) == [
        f"{SYN001}: tier 4 (excluded, ruling R1)"
    ]
    batch["admitted"].append(SYN001)
    assert gate.scope_problems([SYN001], batch, sets["tiers"]["4"]) == [
        f"{SYN001}: tier 4 (excluded, ruling R1)"
    ]


# -- W5-S3: the F0 summary line of batches N and L -----------------------------------------------


def test_s3_only_m9_may_fail() -> None:
    passing = "F0 PASS: M1 50/50, M2 105/105, M9 35/35"
    assert gate.f0_line_problems(passing) == []
    assert gate.f0_line_problems("F0 FAIL: M1 50/50, M8 105/105, M9 FAIL 1/35") == []
    assert gate.f0_line_problems("F0 FAIL: M1 50/50, M6 FAIL 2/77, M9 FAIL 1/35") == [
        "summary line: 'M6 FAIL 2/77' (in batches N and L only M9 may fail)"
    ]
    assert gate.f0_line_problems("no summary") == ["summary line 'no summary': not an F0 summary"]


# -- the frozen exemption --------------------------------------------------------------------------


def _frozen(batch_file: Path | None) -> list[str]:
    environment = {k: v for k, v in os.environ.items() if k != gate.VARIABLE}
    if batch_file is not None:
        environment[gate.VARIABLE] = str(batch_file)
    done = subprocess.run(
        [sys.executable, str(FROZEN)], env=environment, capture_output=True, text=True, check=True
    )
    return done.stdout.split()


def test_the_frozen_exemption_drops_admitted_paths_only(
    batch: dict[str, Any], tmp_path: Path
) -> None:
    unset = _frozen(None)
    exempt = _frozen(_write(tmp_path / "batch.json", batch))
    assert len(unset) == 35 and PR_LIB in unset
    assert exempt == [path for path in unset if path != PR_LIB]
    assert FEED in exempt and SYN001 in exempt


# -- the batch file --------------------------------------------------------------------------------


def _refused(document: Any, sets: dict[str, Any], head: str = BASE) -> list[str]:
    problems = gate.structure(document)
    if not problems:
        problems = gate.ancestry(document["base"], head)
    if not problems:
        problems = gate.membership(document, sets)
    return problems


def test_batch_n_is_valid(batch: dict[str, Any], sets: dict[str, Any]) -> None:
    assert _refused(batch, sets) == []


def _without(document: dict[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in document.items() if k != key}


REFUSALS: dict[str, tuple[Callable[[dict[str, Any]], Any], str]] = {
    "not an object": (lambda b: [b], "the batch file is not a JSON object"),
    "missing key": (lambda b: _without(b, "retarget"), "missing key 'retarget'"),
    "unknown key": (lambda b: {**b, "extra": 1}, "unknown key 'extra'"),
    "batch P": (lambda b: {**b, "batch": "P"}, "batch P needs W5-S2"),
    "unknown batch": (lambda b: {**b, "batch": "X"}, "batch 'X': not one of N, L"),
    "short base": (lambda b: {**b, "base": BASE[:12]}, "not a 40-hex commit sha"),
    "max_tier 3": (lambda b: {**b, "max_tier": 3}, "max_tier 3: not one of (1, 2)"),
    "max_tier bool": (lambda b: {**b, "max_tier": True}, "max_tier True: not one of"),
    "list type": (lambda b: {**b, "generator": "x"}, "generator: not a list of strings"),
    "duplicates": (
        lambda b: {**b, "admitted": [PR_LIB, PR_LIB]},
        "admitted: duplicate entries",
    ),
    "no commit": (lambda b: {**b, "base": "0" * 40}, f"base {'0' * 40}: no such commit"),
    "not R": (
        lambda b: {**b, "admitted": [*b["admitted"], f"{SRC}/numerics/ptc.py"]},
        f"admitted {SRC}/numerics/ptc.py: not in R at the base",
    ),
    "tier 4": (
        lambda b: {**b, "admitted": [*b["admitted"], SYN001]},
        f"admitted {SYN001}: tier 4 (excluded, ruling R1)",
    ),
    "above max_tier": (
        lambda b: {**b, "max_tier": 1},
        f"admitted {PR_LIB}: tier 2, above max_tier 1",
    ),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_each_refusal(batch: dict[str, Any], sets: dict[str, Any], case: str) -> None:
    change, expected = REFUSALS[case]
    problems = _refused(change(copy.deepcopy(batch)), sets)
    assert len(problems) == 1 and expected in problems[0], problems


def test_a_base_that_is_not_an_ancestor_of_the_head_is_refused(batch: dict[str, Any]) -> None:
    problems = gate.ancestry(BASE, PARENT)
    assert problems == [f"base {BASE[:12]}: not an ancestor of the head {PARENT}"]


def _cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {k: v for k, v in os.environ.items() if k != gate.VARIABLE}
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, str(TOOL), *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_validate_accepts_batch_n_and_exits_2_on_a_refusal(
    batch: dict[str, Any], tmp_path: Path
) -> None:
    good = _cli("validate", str(_write(tmp_path / "n.json", batch)), "--head", BASE)
    assert good.returncode == 0, good.stdout
    assert good.stdout.strip().endswith("expected failures 2, standing 1")
    bad = {**batch, "admitted": [*batch["admitted"], SYN001]}
    refused = _cli("validate", str(_write(tmp_path / "bad.json", bad)), "--head", BASE)
    assert refused.returncode == 2
    assert refused.stdout.startswith("W5 batch REFUSED: admitted") and "tier 4" in refused.stdout


@pytest.mark.parametrize("command", ["validate", "batch"])
def test_batch_p_is_refused_naming_w5_s2(
    batch: dict[str, Any], tmp_path: Path, command: str
) -> None:
    path = _write(tmp_path / "p.json", {**batch, "batch": "P"})
    done = _cli(command, str(path), *(["--head", BASE] if command == "validate" else []))
    assert done.returncode == 2 and "W5-S2" in done.stdout


@pytest.mark.parametrize("tier", ["f0", "registry", "scope", "coverage"])
def test_a_tier_refuses_batch_p(batch: dict[str, Any], tmp_path: Path, tier: str) -> None:
    path = _write(tmp_path / "p.json", {**batch, "batch": "P"})
    environment = {**os.environ, gate.VARIABLE: str(path), "PYTHONPATH": str(ROOT / "src")}
    done = subprocess.run(
        [sys.executable, str(TOOL), tier], cwd=ROOT, env=environment, capture_output=True, text=True
    )
    assert done.returncode == 2 and "W5-S2" in done.stdout


# -- the queue -------------------------------------------------------------------------------------


def test_the_queue_gates_a_w5_job_as_a_step() -> None:
    spec = importlib.util.spec_from_file_location(
        "gate_queue", ROOT / ".claude" / "skills" / "s19-refactor" / "gate_queue.py"
    )
    assert spec is not None and spec.loader is not None
    queue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(queue)
    job = {"mode": "w5", "base": BASE, "label": "x", "batch": "/b.json"}
    assert "w5" in queue.MODES
    assert queue.gate_command(job) == queue.gate_command({**job, "mode": "step"})
