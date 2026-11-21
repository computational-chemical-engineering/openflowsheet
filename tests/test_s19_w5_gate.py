"""S19 W5 WO-1: the W5 gate mode (`scripts/w5_gate.py`, ruling `docs/briefs/S19-W5-ruling.md` 6.2).

Outside the gate (acceptance A2 of the WO-1 tooling brief): the subset rule of the tests tier
(W5-S6), the scope rule (W5-S1), the frozen exemption of `scripts/codehealth_frozen.py`, the
batch-file validation with each refusal, and batch P refused (W5-S2 is not implemented). The
tiers and sets are those of the base 94840fb3 (`w5_identity.py sets`: tiers 16/28/6/1).
"""

from __future__ import annotations

import copy
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
    # X07a platform limit (docs/X07a_DECISIONS.md): the sets at `BASE` import that tree, which
    # predates the platform layer and imports `fcntl` (run 44618922484).
    if sys.platform == "win32":
        pytest.skip("the W5 base tree imports fcntl (it predates openflowsheet._platform)")
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


TWO_CALLS = (
    "$ python -m pytest -q -n 8 @/tmp/run.0.args\n"
    "........F\n"
    "FAILED tests/test_a.py::test_identity - assert 1 == 2\n"
    "1 failed, 8 passed in 4.20s\n"
    "$ python -m pytest -q @/tmp/run.1.args\n"
    "....\n"
)


def test_s6_a_call_without_its_closing_counts_line_fails_naming_it(
    batch: dict[str, Any],
) -> None:
    """A crashed or killed pytest leaves no counts line: exit 1 with expected failures only, or
    exit 0, still fails, and so does test_impact's exit 3 for a killed call."""
    assert gate.unclosed_calls(TWO_CALLS) == ["call 1: python -m pytest -q @/tmp/run.1.args"]
    closed = TWO_CALLS + "4 passed in 0.10s\n"
    assert gate.unclosed_calls(closed) == []
    assert gate.unclosed_calls("$ pytest -q -k nothing\nno tests ran in 0.01s\n") == []
    failed = gate.failed_nodes(
        "=== short test summary info ===\n" + TWO_CALLS.splitlines()[2] + "\n"
    )
    for code in (0, 1, 3):
        result, lines = gate.tests_verdict(code, failed, batch, gate.unclosed_calls(TWO_CALLS))
        assert result == (code or 1), lines
        assert "NO-PYTEST-SUMMARY call 1: python -m pytest -q @/tmp/run.1.args" in lines
        assert lines[-1].startswith(f"w5 tests (W5-S6) FAIL: exit {code}, 1 pytest call(s)")
    assert gate.tests_verdict(1, failed, batch, gate.unclosed_calls(closed))[0] == 0


def test_s6_an_expected_failure_not_selected_is_told_from_one_that_passed(
    batch: dict[str, Any], tmp_path: Path
) -> None:
    """test_impact's `@<log>.N.args` listings are the selection: tests/test_b.py's node is in a
    listed file (selected, passed), tests/test_a.py is not listed. Neither fails the step; a call
    without a listing (a full suite or a fallback) selects everything."""
    (tmp_path / "run.0.args").write_text("tests/test_b.py\ntests/test_c.py::test_standing\n")
    (tmp_path / "run.1.args").write_text("tests/test_d.py::test_serial[p]\n")
    log = (
        f"$ python -m pytest -q -n 8 @{tmp_path}/run.0.args\n3 passed in 1.00s\n"
        f"$ python -m pytest -q @{tmp_path}/run.1.args\n1 passed in 0.10s\n"
    )
    entries = gate.selection(log)
    assert entries == {
        "tests/test_b.py",
        "tests/test_c.py::test_standing",
        "tests/test_d.py::test_serial[p]",
    }
    assert gate.selected("tests/test_b.py::test_hash[x - y]", entries)
    assert not gate.selected("tests/test_bb.py::test_x", entries)
    assert not gate.selected("tests/test_d.py::test_serial[q]", entries)
    code, lines = gate.tests_verdict(0, set(), batch, gate.unclosed_calls(log), entries)
    assert code == 0, lines
    assert "EXPECTED-NOT-SELECTED tests/test_a.py::test_identity" in lines
    assert "EXPECTED-NOT-FAILED tests/test_b.py::test_hash[x - y]" in lines
    assert lines[-1].endswith("expected failures failed 0/2, not selected 1")
    full = "$ python -m pytest -q -n 8 --ignore=tests/test_s.py\n9 passed in 9.00s\n"
    assert gate.selection(full) is None
    lines = gate.tests_verdict(0, set(), batch, [], gate.selection(full))[1]
    assert [line for line in lines if line.startswith("EXPECTED-NOT-")] == [
        "EXPECTED-NOT-FAILED tests/test_a.py::test_identity",
        "EXPECTED-NOT-FAILED tests/test_b.py::test_hash[x - y]",
    ]


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
    assert gate.unclosed_calls(f"$ pytest -q\n{done.stdout}") == []  # pytest's own counts line


# -- W5-S1: the scope rule -------------------------------------------------------------------------


def test_s1_admitted_paths_pass(batch: dict[str, Any], sets: dict[str, Any]) -> None:
    files = [CONTRIBUTOR, PR_LIB, "scripts/registry_builtin.py", "tests/test_t07_w5a_inspection.py"]
    assert gate.scope_problems(files, batch, sets["tiers"]) == []


def test_s1_a_tier_2_file_outside_admitted_fails_naming_it(
    batch: dict[str, Any], sets: dict[str, Any]
) -> None:
    problems = gate.scope_problems([CONTRIBUTOR, FEED], batch, sets["tiers"])
    assert problems == [f"{FEED}: outside the batch's admitted, generator and retarget sets"]


CONTRIBUTOR_PART = f"{SRC}/assessment/cost/contributor_terms.py"  # a new module in its directory
PLANS = "plans/*.toml"  # config.toml passes the restructure plans' directory


def test_s1_a_tier_1_split_and_a_restructure_plan_pass(
    batch: dict[str, Any], sets: dict[str, Any]
) -> None:
    files = [CONTRIBUTOR, CONTRIBUTOR_PART, "plans/r1-split.toml"]
    added = [CONTRIBUTOR_PART, "plans/r1-split.toml"]
    assert gate.scope_problems(files, batch, sets["tiers"], added, PLANS) == []


def test_s1_new_paths_outside_a_tier_1_directory_and_unadmitted_tiers_fail(
    batch: dict[str, Any], sets: dict[str, Any]
) -> None:
    """A new module beside a tier 2 file, a new non-module beside a tier 1 file, a tier 1 file
    not admitted that exists at B, a tier 3 file, a plan in another directory: each refused."""
    beside_feed = f"{SRC}/models/c1/feed_terms.py"
    data = f"{SRC}/assessment/cost/terms.json"
    tier_1 = sets["tiers"]["1"][-1]
    tier_3 = sets["tiers"]["3"][0]
    batch["admitted"] = [CONTRIBUTOR, PR_LIB]
    assert tier_1 != CONTRIBUTOR
    files = [beside_feed, data, tier_1, tier_3, "plans/sub/r1.toml", "other/r1.toml"]
    added = [beside_feed, data, "plans/sub/r1.toml", "other/r1.toml"]
    outside = ": outside the batch's admitted, generator and retarget sets"
    assert gate.scope_problems(files, batch, sets["tiers"], added, PLANS) == [
        f"{path}{outside}" for path in sorted(files)
    ]
    # without the plans glob, or for a file that exists at B, a plan-like path is refused too
    assert gate.scope_problems([CONTRIBUTOR_PART], batch, sets["tiers"]) == [
        f"{CONTRIBUTOR_PART}{outside}"
    ]
    assert gate.scope_problems(["plans/r1.toml"], batch, sets["tiers"], ["plans/r1.toml"]) == [
        f"plans/r1.toml{outside}"
    ]


def test_s1_syn001_fails_even_when_admitted(batch: dict[str, Any], sets: dict[str, Any]) -> None:
    assert gate.scope_problems([SYN001], batch, sets["tiers"]) == [
        f"{SYN001}: tier 4 (excluded, ruling R1)"
    ]
    batch["admitted"].append(SYN001)
    assert gate.scope_problems([SYN001], batch, sets["tiers"]) == [
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
    "generator in R": (
        lambda b: {**b, "generator": [*b["generator"], FEED]},
        f"generator {FEED}: in R at the base but not admitted",
    ),
    "retarget in R": (
        lambda b: {**b, "retarget": [*b["retarget"], SYN001]},
        f"retarget {SYN001}: in R at the base but not admitted",
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
    digest = gate.digest(tmp_path / "n.json")
    assert good.stdout.strip().endswith(f"expected failures 2, standing 1, sha256 {digest}")
    bad = {**batch, "admitted": [*batch["admitted"], SYN001]}
    refused = _cli("validate", str(_write(tmp_path / "bad.json", bad)), "--head", BASE)
    assert refused.returncode == 2
    assert refused.stdout.startswith("W5 batch REFUSED: admitted") and "tier 4" in refused.stdout


def test_batch_prints_the_sha256_and_refuses_a_dirty_tree(
    batch: dict[str, Any], tmp_path: Path, monkeypatch, capsys
) -> None:
    path = _write(tmp_path / "n.json", batch)
    monkeypatch.setattr(gate, "dirty", lambda: "")
    assert gate.main(["batch", str(path)]) == 0
    assert (
        capsys.readouterr().out.strip() == f"W5 batch N base {BASE[:12]} sha256 {gate.digest(path)}"
    )
    monkeypatch.setattr(gate, "dirty", lambda: "?? stray.py")
    assert gate.main(["batch", str(path)]) == 2
    assert "the tree under test is not clean:\n?? stray.py" in capsys.readouterr().out


def test_dirty_reads_the_porcelain_status(tmp_path: Path) -> None:
    def git(*arguments: str) -> None:
        subprocess.run(["git", *arguments], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "a.txt").write_text("a\n")
    git("add", "a.txt")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "a")
    assert gate.dirty(tmp_path) == ""
    (tmp_path / "a.txt").write_text("b\n")
    assert gate.dirty(tmp_path) == "M a.txt"
    git("checkout", "-q", "a.txt")
    (tmp_path / "new.txt").write_text("n\n")
    assert gate.dirty(tmp_path) == "?? new.txt"


def _job(queue: Path, state: str, label: str, base: str | None, sha256: str | None) -> None:
    (queue / state).mkdir(parents=True, exist_ok=True)
    job = {"label": label, "mode": "step", "batch_base": base, "batch_sha256": sha256}
    _write(queue / state / f"{label}.json", job)


def test_batch_check_finds_one_batch_file_per_base(tmp_path: Path) -> None:
    """Jobs of one B with one hash pass; a second hash for B fails naming both; jobs of another
    B, without a batch, or withdrawn do not count."""
    queue, other = tmp_path / "queue", "1" * 40
    _job(queue, "done", "n1", BASE, "a" * 64)
    _job(queue, "running", "n2", BASE, "a" * 64)
    _job(queue, "done", "elsewhere", other, "b" * 64)
    _job(queue, "done", "plain", None, None)
    _job(queue, "withdrawn", "gone", BASE, "c" * 64)
    one = _cli("batch-check", "--queue-dir", str(queue), "--base", BASE[:12])
    assert one.returncode == 0, one.stdout
    assert one.stdout.splitlines() == [
        f"sha256 {'a' * 64}: n1, n2",
        f"w5 batch-check PASS: base {BASE[:12]}, 2 job(s), 1 distinct batch file(s)",
    ]
    _job(queue, "pending", "n3", BASE, "d" * 64)
    two = _cli("batch-check", "--queue-dir", str(queue), "--base", BASE)
    assert two.returncode == 1
    assert f"sha256 {'d' * 64}: n3" in two.stdout.splitlines()
    assert two.stdout.splitlines()[-1].endswith("3 job(s), 2 distinct batch file(s)")
    assert two.stdout.splitlines()[-1].startswith("w5 batch-check FAIL")
    refused = _cli("batch-check", "--queue-dir", str(queue), "--base", "zz")
    assert refused.returncode == 2


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
