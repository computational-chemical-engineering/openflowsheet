"""S19 W5 WO-1: the W5 gate mode (`scripts/w5_gate.py`, ruling `docs/briefs/S19-W5-ruling.md` 6.2).

Outside the gate (acceptance A2 of the WO-1 tooling brief): the subset rule of the tests tier
(W5-S6), the scope rule (W5-S1), the frozen exemption of `scripts/codehealth_frozen.py`, the
batch-file validation with each refusal, and batch P's W5-S2 and W5-K5 wiring (WO-P0; the pin
itself is tested in `test_s19_w5_identity.py`). The tiers and sets are those of the base 94840fb3
(`w5_identity.py sets`: tiers 16/28/6/1).
"""

from __future__ import annotations

import contextlib
import copy
import json
import os
import subprocess
import sys
import tomllib
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
INTERFACE = "interface/*.toml"  # and the interface plans' (review R-W5-N-close item 4a)


def test_s1_a_tier_1_split_and_a_restructure_plan_pass(
    batch: dict[str, Any], sets: dict[str, Any]
) -> None:
    files = [CONTRIBUTOR, CONTRIBUTOR_PART, "plans/r1-split.toml"]
    added = [CONTRIBUTOR_PART, "plans/r1-split.toml"]
    assert gate.scope_problems(files, batch, sets["tiers"], added, [PLANS]) == []


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
    assert gate.scope_problems(files, batch, sets["tiers"], added, [PLANS]) == [
        f"{path}{outside}" for path in sorted(files)
    ]
    # without the plans glob, or for a file that exists at B, a plan-like path is refused too
    assert gate.scope_problems([CONTRIBUTOR_PART], batch, sets["tiers"]) == [
        f"{CONTRIBUTOR_PART}{outside}"
    ]
    assert gate.scope_problems(["plans/r1.toml"], batch, sets["tiers"], ["plans/r1.toml"]) == [
        f"plans/r1.toml{outside}"
    ]


def test_s1_an_added_plan_under_either_glob_passes_a_modified_one_fails(
    batch: dict[str, Any], sets: dict[str, Any]
) -> None:
    """Item 4a: a plan file passes by glob only if absent at B; an existing plan file is in
    scope only when the batch names it (batch N's retarget list names its interface plans)."""
    plans = [PLANS, INTERFACE]
    added = ["plans/r2-split.toml", "interface/w5l1.toml"]
    assert gate.scope_problems(added, batch, sets["tiers"], added, plans) == []
    modified = ["plans/r1-split.toml", "interface/w5n2.toml"]
    outside = ": outside the batch's admitted, generator and retarget sets"
    assert gate.scope_problems([*added, *modified], batch, sets["tiers"], added, plans) == [
        f"interface/w5n2.toml{outside}",
        f"plans/r1-split.toml{outside}",
    ]
    batch["retarget"].append("interface/w5n2.toml")
    assert gate.scope_problems(modified, batch, sets["tiers"], added, plans) == [
        f"plans/r1-split.toml{outside}"
    ]


def test_s1_the_scope_command_takes_plans_repeatedly(
    batch: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}

    def problems(files, document, tiers, added, plans):  # type: ignore[no-untyped-def]
        seen.update(files=files, added=added, plans=list(plans))
        return []

    monkeypatch.setattr(gate, "from_environment", lambda: batch)
    monkeypatch.setattr(gate, "changed", lambda base, added=False: ["b"] if added else ["a", "b"])
    monkeypatch.setattr(gate, "sets_at", lambda base: {"tiers": {}})
    monkeypatch.setattr(gate, "scope_problems", problems)
    assert gate.main(["scope", "--plans", PLANS, "--plans", INTERFACE]) == 0
    assert seen == {"files": ["a", "b"], "added": ["b"], "plans": [PLANS, INTERFACE]}
    assert gate.main(["scope"]) == 0
    assert seen["plans"] == []
    assert capsys.readouterr().out.splitlines()[-1].startswith("w5 scope (W5-S1) PASS")


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
    "batch P tier 2": (lambda b: {**b, "batch": "P"}, "max_tier 2: batch P's is 3"),
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


# -- batch P: W5-S2 and W5-K5 (WO-P0) ------------------------------------------------------------


def _batch_p(sets: dict[str, Any]) -> dict[str, Any]:
    """Batch P: the six tier 3 files and B7's generator, at max_tier 3."""
    return {
        "batch": "P",
        "base": BASE,
        "max_tier": 3,
        "admitted": sets["tiers"]["3"],
        "generator": ["docs/derivations/scripts/s07_reference.py"],
        "retarget": [],
        "expected_failures": [],
        "standing_failures": [],
    }


def test_batch_p_at_tier_3_validates(sets: dict[str, Any], tmp_path: Path) -> None:
    path = _write(tmp_path / "p.json", _batch_p(sets))
    done = _cli("validate", str(path), "--head", BASE)
    assert done.returncode == 0, done.stdout
    assert done.stdout.startswith("W5 batch P valid: base 94840fb3a4bd, max_tier 3, admitted 6")
    over = {**_batch_p(sets), "admitted": [*sets["tiers"]["3"], SYN001]}
    assert _refused(over, sets) == [f"admitted {SYN001}: tier 4 (excluded, ruling R1)"]


def test_s3_batch_p_may_also_fail_m2_m3_and_m6() -> None:
    """W5-S3: M1, M4, M5, M7 and M8 pass in every batch; batch P's line may fail M2, M3, M6."""
    line = (
        "F0 FAIL: M1 50/50, M2 FAIL 1/61, M3 FAIL 1/61, M4 61/61, M5 61/61, M6 FAIL 2/85, "
        "M7 52/52, M8 105/105, M9 FAIL 1/35"
    )
    assert gate.f0_line_problems(line, "P") == []
    assert gate.f0_line_problems(line) == [
        f"summary line: {part!r} (in batches N and L only M9 may fail)"
        for part in ("M2 FAIL 1/61", "M3 FAIL 1/61", "M6 FAIL 2/85")
    ]
    assert gate.f0_line_problems(line.replace("M4 61/61", "M4 FAIL 1/61"), "P") == [
        "summary line: 'M4 FAIL 1/61' (in batch P only M2, M3, M6 and M9 may fail)"
    ]


@pytest.mark.parametrize("close", [False, True])
def test_the_pin_is_not_applicable_to_batch_n(
    batch: dict[str, Any], tmp_path: Path, close: bool
) -> None:
    path = _write(tmp_path / "n.json", batch)
    environment = {**os.environ, gate.VARIABLE: str(path), "PYTHONPATH": str(ROOT / "src")}
    done = subprocess.run(
        [sys.executable, str(TOOL), "pin", *(["--close"] if close else [])],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    check = "W5-K5" if close else "W5-S2"
    assert done.returncode == 0, done.stdout
    assert done.stdout == f"w5 pin ({check}) PASS: not applicable to batch N (batch P only)\n"


PIN_LINE = "F0 PASS: M1 50/50, M9 35/35"


def _fake_identity(
    calls: list[tuple[str, ...]], pin_exit: int, unpinned: list[str], predict_exit: int
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """`w5_identity.py` as the gate calls it: `pin` writes its record and F0's log, `predict`
    answers `predict_exit`; every call is recorded."""

    def identity(*arguments: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        if arguments[0] == "pin":
            out = Path(arguments[arguments.index("--json") + 1])
            log = Path(arguments[arguments.index("--log") + 1])
            log.write_text(f"{PIN_LINE}\nplatform ref-x86-64\n", encoding="utf-8")
            pinned = [] if unpinned else [f"{SRC}/thermo/pr_c1.py"]
            record = {"pinned": pinned, "unpinned": unpinned, "moved_files": unpinned}
            out.write_text(json.dumps(record), encoding="utf-8")
            return subprocess.CompletedProcess(arguments, pin_exit)
        return subprocess.CompletedProcess(arguments, predict_exit)

    return identity


COOLPROP = [f"{SRC}/thermo/_coolprop_heos_fluids.py", f"{SRC}/thermo/coolprop_heos.py"]
PIN_CASES: dict[str, tuple[int, list[str], int, int, str]] = {
    "pass": (0, [], 0, 0, "PASS: pinned 1, none unpinned, the pinned F0 is the prediction at "),
    "coolprop": (1, COOLPROP, 0, 0, "PASS: pinned 0, unpinned 2 (CoolProp), "),
    "vacuous": (3, [], 0, 3, "FAIL: pin exit 3 (a vacuous or foreign read)"),
    "outside": (0, [FEED], 0, 1, f"FAIL: {FEED}: unpinned (hash scope changed since B), "),
    "predicted": (0, [], 1, 1, f"FAIL: predict exit 1; {PIN_LINE}"),
}


@pytest.mark.parametrize("close", [False, True])
@pytest.mark.parametrize("case", sorted(PIN_CASES))
def test_s2_and_k5_judge_the_pin(
    sets: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: str,
    close: bool,
) -> None:
    """W5-S2 (a step) and W5-K5 (`--close`, F0's registry from B): the pin's exit 3 fails; a file
    left unpinned outside the CoolProp pair fails; else the pinned log must be `predict --base B
    --files <the files the pin left to the head>` both ways."""
    pin_exit, unpinned, predict_exit, expected, verdict = PIN_CASES[case]
    path = _write(tmp_path / "p.json", _batch_p(sets))
    monkeypatch.setenv(gate.VARIABLE, str(path))
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(gate, "identity", _fake_identity(calls, pin_exit, unpinned, predict_exit))
    assert gate.main(["pin", *(["--close"] if close else [])]) == expected
    check = "W5-K5" if close else "W5-S2"
    assert f"w5 pin ({check}) {verdict}" in capsys.readouterr().out.splitlines()[-1]
    pin = calls[0]
    assert pin[:5] == ("pin", "--base", BASE, "--json", pin[4])
    assert ("--registry" in pin) == close and (
        not close or pin[pin.index("--registry") + 1] == BASE
    )
    assert pin[pin.index("--") + 1 :][:2] == ("scripts/corpus_identity.py", "--check")
    if pin_exit == 3:
        assert len(calls) == 1
        return
    (predict,) = calls[1:]
    files = list(predict[predict.index("--files") + 1 : predict.index("--against-log")])
    assert predict[:5] == ("predict", "--base", BASE, "--max-tier", "3") and files == unpinned


# -- W5-K1: the batch close K (review R-W5-N-close item 4d) ---------------------------------------

B_N = "605d332fc062701ff658aaef45a31dd68c9f3739"  # batch N's base
K_N = "4178e4bcd508dd839f11618610a55feffa578f86"  # batch N's close
K_N_FIXTURE = "tests/test_f1_legacy_builtins.py"  # the factory's expected value (WO-N4's L_B)


def _repository(path: Path) -> Callable[..., str]:
    def git(*arguments: str) -> str:
        done = subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        return done.stdout.strip()

    git("init", "-q")
    return git


def _commit(path: Path, git: Callable[..., str], files: dict[str, str]) -> str:
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text)
    git("add", *files)
    git("commit", "-q", "-m", "c")
    return git("rev-parse", "HEAD")


def test_k1_an_extra_file_or_a_moved_m6_request_fails_a_clean_close_passes(
    tmp_path: Path,
) -> None:
    git = _repository(tmp_path)
    corpus, m6, golden = gate.CLOSE_PATHS[0], gate.M6_REQUESTS, "tests/fixtures/st/golden.json"
    base = _commit(tmp_path, git, {corpus: "0\n", m6: "r\n", golden: "g\n", "src/a.py": "a\n"})
    clean = _commit(tmp_path, git, {corpus: "1\n", gate.CLOSE_PATHS[4]: "t\n"})
    assert gate.close_problems(base, clean, [], tmp_path) == []
    extra = _commit(tmp_path, git, {corpus: "2\n", golden: "h\n", "src/a.py": "b\n"})
    assert gate.close_problems(base, extra, [golden], tmp_path) == [
        "src/a.py: outside W5-K1's list (and no --fixture)"
    ]
    assert gate.close_problems(base, extra, [], tmp_path) == [
        f"{path}: outside W5-K1's list (and no --fixture)" for path in ("src/a.py", golden)
    ]
    _commit(tmp_path, git, {m6: "s\n"})
    moved = _commit(tmp_path, git, {corpus: "3\n"})  # K itself is clean, B..K moved a request
    assert gate.close_problems(base, moved, [], tmp_path) == [
        f"{m6}: not byte-identical between B {base[:12]} and K {moved[:12]}"
    ]


def test_k1_replays_batch_n_and_records_its_close(batch: dict[str, Any], tmp_path: Path) -> None:
    """Batch N's K: without its L_B fixture it fails naming it; with it, PASS and K recorded.
    The same K again passes; another K for the same base is refused."""
    path = _write(tmp_path / "n.json", {**batch, "base": B_N})
    queue = tmp_path / "queue"
    close = ("close", "--k", K_N[:8], "--batch", str(path), "--queue-dir", str(queue))
    failed = _cli(*close)
    assert failed.returncode == 1, failed.stdout
    assert failed.stdout.splitlines() == [
        f"{K_N_FIXTURE}: outside W5-K1's list (and no --fixture)",
        f"W5-K1 FAIL: K {K_N[:12]} of batch N (base {B_N[:12]}), 1 path(s) outside the close",
    ]
    assert not queue.exists()
    passed = _cli(*close, "--fixture", K_N_FIXTURE)
    assert passed.returncode == 0, passed.stdout
    record = gate.closed_record(queue, B_N)
    assert passed.stdout.strip() == (
        f"W5-K1 PASS: K {K_N[:12]} of batch N (base {B_N[:12]}), 1 fixture path(s); "
        f"recorded in {record}"
    )
    assert json.loads(record.read_text()) == {
        "batch": "N",
        "base": B_N,
        "k": K_N,
        "batch_sha256": gate.digest(path),
        "fixtures": [K_N_FIXTURE],
    }
    assert _cli(*close, "--fixture", K_N_FIXTURE).returncode == 0
    with pytest.raises(gate.BatchRefusedError, match="already closed at another K"):
        gate.record_close(queue, {"batch": "N", "base": B_N}, "f" * 40, "a" * 64, [])
    assert json.loads(record.read_text())["k"] == K_N


def test_k1_needs_a_batch_and_a_k_that_descends_from_b(
    batch: dict[str, Any], tmp_path: Path
) -> None:
    queue = str(tmp_path / "queue")
    no_batch = _cli("close", "--k", K_N, "--queue-dir", queue)
    assert no_batch.returncode == 2 and "S19_W5_BATCH is not set" in no_batch.stdout
    path = str(_write(tmp_path / "n.json", {**batch, "base": K_N}))
    before = _cli("close", "--k", B_N, "--batch", path, "--queue-dir", queue)
    assert before.returncode == 2 and "not an ancestor of the head" in before.stdout
    assert _cli("close", "--k", "0" * 40, "--batch", path, "--queue-dir", queue).returncode == 2


# -- W5-S2 and W5-K5 reach the gate (review R-W5-P0-pin, fix 1) -----------------------------------


def _tier(name: str) -> dict[str, Any]:
    config = tomllib.loads((ROOT / ".codehealth" / "config.toml").read_text(encoding="utf-8"))
    (tier,) = [t for t in config["gate"]["tier"] if t["name"] == name]
    return tier


def test_s2_the_w5_pin_step_tier_runs_the_pin_and_passes_outside_a_w5_step() -> None:
    """The gate runs W5-S2 at every step: tier `w5_pin` calls `w5_gate.py pin` when
    S19_W5_BATCH is set (batches N and L: not applicable) and passes at once when it is not."""
    tier = _tier("w5_pin")
    assert tier["cadence"] == "step" and tier["detect_exit"] == [1, 124]
    assert tier["cmd"].endswith('; PYTHONPATH=src "$V/python" scripts/w5_gate.py pin')
    guard = _tier("w5_registry")["cmd"].split("; PYTHONPATH=src")[0]
    assert tier["cmd"].split("; PYTHONPATH=src")[0] == guard.replace("w5_registry", "w5_pin")
    environment = {k: v for k, v in os.environ.items() if k != gate.VARIABLE}
    done = subprocess.run(
        ["sh", "-c", tier["cmd"]], cwd=ROOT, env=environment, capture_output=True, text=True
    )
    assert done.returncode == 0 and done.stdout == (
        "w5_pin: S19_W5_BATCH unset, not a W5 step: pass\n"
    )


def _close_p(
    sets: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    k: str = "HEAD",
    pin_exit: int = 0,
    predict_exit: int = 0,
    k1: list[str] | None = None,
    tree: str = "",
) -> tuple[int, list[str], list[tuple[str, ...]], Path]:
    """`close` of a batch P at K in this tree, its K1 and the identity tool faked: (exit, the
    lines, the identity calls, the close record's path)."""
    tmp_path.mkdir()
    path = _write(tmp_path / "p.json", _batch_p(sets))
    queue = tmp_path / "queue"
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(gate, "identity", _fake_identity(calls, pin_exit, [], predict_exit))
    monkeypatch.setattr(gate, "close_problems", lambda *_: list(k1 or []))
    monkeypatch.setattr(gate, "dirty", lambda *_: tree)
    output = tmp_path / "out.txt"
    with output.open("w", encoding="utf-8") as stream, contextlib.redirect_stdout(stream):
        code = gate.main(["close", "--k", k, "--batch", str(path), "--queue-dir", str(queue)])
    return code, output.read_text().splitlines(), calls, gate.closed_record(queue, BASE)


def test_k5_a_batch_p_close_runs_the_pin_at_k_and_records_k_only_if_it_passes(
    sets: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`close` of batch P: after W5-K1, W5-K5 (`pin --close`, F0's registry from B) in this tree;
    K is recorded only on PASS, and a failed pin keeps its exit code."""
    head = gate._git("rev-parse", "HEAD").stdout.strip()
    where = f"K {head[:12]} of batch P (base {BASE[:12]})"
    code, lines, calls, record = _close_p(sets, tmp_path / "pass", monkeypatch)
    assert code == 0, lines
    assert lines[0].startswith("w5 pin (W5-K5) PASS: pinned 1, none unpinned")
    assert lines[1] == f"W5-K1 PASS: {where}, 0 fixture path(s); recorded in {record}"
    assert json.loads(record.read_text())["k"] == head
    assert calls[0][calls[0].index("--registry") + 1] == BASE
    for pin_exit, predict_exit, expected in ((0, 1, 1), (3, 0, 3)):
        code, lines, _, record = _close_p(
            sets,
            tmp_path / f"fail{pin_exit}",
            monkeypatch,
            pin_exit=pin_exit,
            predict_exit=predict_exit,
        )
        assert code == expected and lines[0].startswith("w5 pin (W5-K5) FAIL: "), lines
        assert lines[1] == f"W5-K1 PASS, W5-K5 FAIL: {where}; K not recorded"
        assert not record.exists()


def test_k5_needs_k_checked_out_clean_and_waits_for_k1(
    sets: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W5-K5 runs F0 in this tree: K must be its HEAD and the tree clean (else refused, exit 2);
    a W5-K1 failure stops the close before the pin."""
    for case, options in {
        "another K": {"k": "HEAD^"},
        "dirty": {"tree": " M src/openflowsheet/thermo/pr_c1.py"},
    }.items():
        code, lines, calls, record = _close_p(sets, tmp_path / case, monkeypatch, **options)
        assert code == gate.REFUSED and lines[-1].startswith("W5 batch REFUSED: close: W5-K5 ")
        assert calls == [] and not record.exists(), case
    code, lines, calls, record = _close_p(sets, tmp_path / "k1", monkeypatch, k1=["src/a.py: x"])
    assert code == 1 and lines[-1].startswith("W5-K1 FAIL: ") and calls == []
    assert not record.exists()


def _reference_class() -> str:
    import corpus_identity  # noqa: PLC0415  (scripts/, on sys.path above)

    return str(corpus_identity.reference_class())


#: The pinned F0's line is the reference platform's (as the full-F0 tests of
#: test_s19_w5_identity.py).
reference_only = pytest.mark.skipif(
    _reference_class() != "ref-x86-64", reason="the pinned F0's line is the reference platform's"
)
#: The tree under test's files a scratch base takes, so that the chain runs this tree's tools.
CHAIN_TOOLS = (
    ".codehealth/config.toml",
    "scripts/corpus_identity.py",
    "scripts/w5_gate.py",
    "scripts/w5_identity.py",
)


@reference_only
def test_s2_the_real_chain_passes_a_comment_edited_tier_3_step(
    sets: dict[str, Any], tmp_path: Path
) -> None:
    """Review R-W5-P0-pin, item 4: the gate's `w5_pin` tier -> `w5_gate.py pin` ->
    `w5_identity.py pin` -> F0, unfaked, on a scratch batch P step. B is HEAD with this tree's
    tools; the step comment-edits `thermo/pr_c1.py`; the pinned F0 is B's line."""
    tree = tmp_path / "tree"
    git = ["git", "-c", "user.name=w5", "-c", "user.email=w5@invalid"]
    subprocess.run([*git, "worktree", "add", "--detach", str(tree), "HEAD"], cwd=ROOT, check=True)
    try:
        for name in CHAIN_TOOLS:
            (tree / name).write_bytes((ROOT / name).read_bytes())
        subprocess.run([*git, "add", *CHAIN_TOOLS], cwd=tree, check=True)
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "B"], cwd=tree, check=True)
        base = gate._git("rev-parse", "HEAD", cwd=tree).stdout.strip()
        pr_c1 = tree / SRC / "thermo" / "pr_c1.py"
        pr_c1.write_text(
            pr_c1.read_text(encoding="utf-8") + "# W5-S2 chain test: a comment-only edit.\n",
            encoding="utf-8",
        )
        subprocess.run([*git, "commit", "-q", "-am", "a tier 3 step"], cwd=tree, check=True)
        path = _write(tmp_path / "p.json", {**_batch_p(sets), "base": base})
        environment = {
            **os.environ,
            gate.VARIABLE: str(path),
            "OPENFLOWSHEET_VENV": sys.prefix,
        }
        environment.pop("PYTHONPATH", None)
        done = subprocess.run(
            ["sh", "-c", _tier("w5_pin")["cmd"]],
            cwd=tree,
            env=environment,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    finally:
        subprocess.run([*git, "worktree", "remove", "--force", str(tree)], cwd=ROOT, check=False)
        subprocess.run([*git, "worktree", "prune"], cwd=ROOT, check=False)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    verdict = done.stdout.splitlines()[-1]
    assert verdict.startswith(
        f"w5 pin (W5-S2) PASS: pinned 1, none unpinned, the pinned F0 is the prediction at "
        f"{base[:12]} for 0 file(s); F0 PASS: "
    ), verdict
