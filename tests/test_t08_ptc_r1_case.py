"""T08 W3: PTC-R1's registration (`C_case`) — T08.B20 and the harness's pure parts.

Design `docs/derivations/T08-build-first-spec.md` §A4.2–§A4.6 as amended by Amendment 1 (§Am1.1,
§Am1.C B20/B21), ADR 0023 D5. B13–B15 on the registered revision are in
`test_t08_kinetic_cstr.py` (parametrized over `case`).

**Nothing here runs either method** (§A4.6): the harness's `run_start` is called only with
`execute_plan` replaced by a stub that solves nothing, and `--run` only up to its refusals. The
tests recompute `case.json`, check the git order, build the 441 start vectors, and exercise the
classification, the record path and the summary on synthetic results.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import test_t07_w5c_signatures as signatures
from conftest import REPO_ROOT, require_archived_history
from t08_cstr_support import ptc_r1_revision

from benchmarks.t08.ptc_r1 import compare
from openflowsheet.application.policies import (
    APPLICATION_POLICIES,
    T06_REVISION_V2,
    T08_PTC_V1,
    T08_WARM_V1,
)
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.revisions import content_hash
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.executor import PlanResult
from openflowsheet.orchestrator.trace import Counters, PtcPolicy, Trace
from openflowsheet.run.manifest import policy_sha256

CASE_DIR = REPO_ROOT / "benchmarks" / "t08" / "ptc_r1"
#: Amendment 1 §Am1.1: the starts' digest (B07), superseding `b77df2fe…`.
STARTS_SHA256 = "0262bebcb9c5af890d770663d1e5a7cd059159bf0eb6f58bd40c04641c49a17c"
TRACE = 2.0**-10
VARIABLES = (
    "S1.n.A",
    "S1.n.B",
    "S1.n.C",
    "S1.T",
    "S1.P",
    "S2.n.A",
    "S2.n.B",
    "S2.n.C",
    "S2.T",
    "S2.P",
    "U-CSTR.Q",
)


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout


def _is_ancestor(older: str, newer: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer], cwd=REPO_ROOT, check=False
    )
    return completed.returncode == 0


def _binding() -> RevisionBinding:
    bound = bind_revision_flowsheet(compare.revision_document())
    assert isinstance(bound, RevisionBinding), bound
    return bound


# -- B20: the registration record -------------------------------------------------------------


def test_b20_case_json_recomputes() -> None:
    """Every member of `case.json` recomputes from the code and the files it names (B20)."""
    assert compare.case_differences() == []


def test_b20_case_json_carries_the_amended_registration() -> None:
    case = compare.case_document()
    assert case["git_order"] == {
        "C_reg": "9f5f29d7063ae5102c535d94d5f18f20db6480c2",
        "C_A1": "30243f9c9956fb7ec6970f62156f864cd35d0aa0",
    }
    assert case["starts"] == {"count": 441, "sha256_of_compact_json": STARTS_SHA256}
    # The YAML's sha256 as committed at `C_A1` (§A4.6 as amended).
    require_archived_history(compare.C_A1)
    at_c_a1 = subprocess.run(
        ["git", "show", f"{compare.C_A1}:benchmarks/t08/build_first_reference.yaml"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    assert case["reference"]["sha256"] == hashlib.sha256(at_c_a1).hexdigest()
    assert case["revision"]["content_sha256"] == content_hash(compare.revision_document())
    assert case["policies"] == {
        "T08-PTC-R1-newton": policy_sha256(compare.NEWTON_ARM),
        "T08-PTC-R1-ptc": policy_sha256(compare.PTC_ARM),
        "T08-ptc-v1": policy_sha256(T08_PTC_V1),
        "T08-warm-v1": policy_sha256(T08_WARM_V1),
    }
    assert case["arms"] == {"newton": "T08-PTC-R1-newton", "ptc": "T08-PTC-R1-ptc"}


def _without(document: dict[str, Any], *globalization: str) -> dict[str, Any]:
    rest = {key: value for key, value in document.items() if key != "policy_id"}
    rest["globalization"] = {
        key: value for key, value in document["globalization"].items() if key not in globalization
    }
    return rest


def test_the_policies_are_t06_revision_v2_with_only_the_registered_changes() -> None:
    """§A2: `T08-ptc-v1` changes only `eo_core` to `ptc`, at `PtcPolicy`'s registered constants;
    §A4.5: each arm changes only `eo_core` and sets `eo_recovery = none`, and is not offered."""
    base = T06_REVISION_V2.as_document()
    assert T08_PTC_V1.globalization.eo_core == "ptc"
    assert T08_PTC_V1.globalization.ptc == PtcPolicy()
    assert _without(T08_PTC_V1.as_document(), "eo_core") == _without(base, "eo_core")
    for arm, policy in compare.ARMS.items():
        assert policy.globalization.eo_core == arm
        assert policy.globalization.eo_recovery == "none"
        assert policy == replace(
            T06_REVISION_V2,
            policy_id=policy.policy_id,
            globalization=replace(T06_REVISION_V2.globalization, eo_core=arm, eo_recovery="none"),
        )
        assert policy.policy_id not in APPLICATION_POLICIES


def test_b20_git_order() -> None:
    """`C_reg → C_A1 → C_case`, and every committed result file descends from `C_case`, the
    commit that added `case.json` (§A4.6 as amended). No result file exists at `C_case`."""
    require_archived_history(compare.C_REG, compare.C_A1, in_history_of_head=True)
    assert _is_ancestor(compare.C_REG, compare.C_A1)
    case_path = str(compare.CASE_FILE.relative_to(REPO_ROOT))
    (c_case,) = _git("log", "--diff-filter=A", "--format=%H", "--", case_path).split()
    assert _is_ancestor(compare.C_A1, c_case) and c_case != compare.C_A1
    at_c_case = _git("ls-tree", "-r", "--name-only", c_case, "--", "benchmarks/t08/ptc_r1")
    assert [p for p in at_c_case.split() if Path(p).name.startswith("results-")] == []
    results = _git("log", "--diff-filter=A", "--format=%H", "--", "benchmarks/t08/ptc_r1/results-*")
    for commit in results.split():
        assert _is_ancestor(c_case, commit) and commit != c_case, commit


# -- the registered revision ------------------------------------------------------------------


def test_the_registered_revision_binds_to_the_w2_fixtures_problem() -> None:
    """`revision.json` binds on the eleven variables §A1.5 and §A4.2 name, and its bound
    structure is the W2 fixture's except the revision's own hash, so B11–B19 on the fixture are
    statements about the registered revision (§A2)."""
    bound = _binding()
    assert bound.spec.variable_ids == VARIABLES
    registered = signatures._structure(bound)
    fixture = bind_revision_flowsheet(ptc_r1_revision())
    assert isinstance(fixture, RevisionBinding)
    expected = signatures._structure(fixture)
    assert {k for k in registered if registered[k] != expected[k]} == {"revision_sha256"}


# -- the starts (§A4.2 as amended) ------------------------------------------------------------


def test_the_starts_cover_the_declaration_and_carry_the_trace() -> None:
    rows = compare.start_rows()
    assert compare.starts_sha256(rows) == STARTS_SHA256
    assert [(row[0], row[1]) for row in rows] == [(i, j) for j in range(21) for i in range(21)]
    vectors = [compare.start_vector(row) for row in rows]
    assert len({tuple(sorted(v.items())) for v in vectors}) == 441
    feed = {"S1.n.A": 0.4990234375, "S1.n.B": 0.5, "S1.n.C": TRACE, "S1.T": 360.0, "S1.P": 1e5}
    for (i, j, *_), vector in zip(rows, vectors, strict=True):
        assert tuple(sorted(vector)) == tuple(sorted(VARIABLES))
        assert {k: vector[k] for k in feed} == feed
        assert vector["S2.n.C"] == TRACE and vector["S2.P"] == 1e5
        assert vector["S2.n.A"] == (20 + i) / 40 - TRACE  # exact in binary64 (B01)
        assert vector["S2.n.B"] == (20 - i) / 40
        assert vector["S2.n.A"] + vector["S2.n.B"] + vector["S2.n.C"] == 1.0
        assert vector["S2.T"] == 360.0 + 1.25 * j
        assert vector["U-CSTR.Q"] == -37.5 * j == 30.0 * (360.0 - vector["S2.T"])
        # §A1.5's map puts the start on the registered grid: x₁ = i/20 (to the rounding of the
        # quotient `n_B`), x₂ = 0.4 j (exactly: `T` is exact as written).
        assert abs(1 - Fraction(vector["S2.n.B"]) / Fraction(1, 2) - Fraction(i, 20)) <= 2**-53
        assert (Fraction(vector["S2.T"]) - 360) / Fraction(25, 8) == Fraction(2 * j, 5)


# -- the classification (§A4.3) and the summary -----------------------------------------------


def _state(x1: float, x2: float) -> dict[str, float]:
    return {"S2.n.B": 0.5 * (1.0 - x1), "S2.T": 360.0 + 3.125 * x2}


@pytest.mark.parametrize("name", compare.ROOTS)
def test_classify_by_the_registered_radius(name: str) -> None:
    root = compare.reference()["closed_form"]["steady_states"][name]
    x1, x2 = float(root["x1"]), float(root["x2"])
    assert compare.classify("CONVERGED", _state(x1, x2))[0] == name
    assert compare.classify("CONVERGED", _state(x1 + 1.9e-3, x2 - 1.9e-3))[0] == name
    assert compare.classify("CONVERGED", _state(x1, x2 + 2.1e-3))[0] == "FAIL"
    assert compare.classify("PTC_STALLED", _state(x1, x2))[0] == "FAIL"
    assert compare.classify("CONVERGED", None) == ("FAIL", None)


def _record(arm: str, i: int, j: int, klass: str, **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "arm": arm,
        "i": i,
        "j": j,
        "outcome": "CONVERGED" if klass != "FAIL" else "PTC_STALLED",
        "accepted_steps": 3,
        "class": klass,
        "certificate": {"verdict": "VERIFIED"} if klass != "FAIL" else None,
        "attempts": [["CONVERGED", "CONVERGED", 3]],
        "counters": {"property_calls": 10},
        "budget": None,
        "c_final": {"S1.n.C": TRACE, "S2.n.C": TRACE},
        "bound_blocks": [],
        "c_blockers": [],
        "crash": None,
    }
    record.update(overrides)
    return record


def test_the_summary_reports_classes_maps_and_b21_facts() -> None:
    records = [
        _record("newton", 0, 0, "LOW"),
        _record("ptc", 0, 0, "LOW"),
        _record("newton", 1, 0, "FAIL"),
        _record("ptc", 1, 0, "HIGH", c_final={"S1.n.C": TRACE, "S2.n.C": TRACE + 1e-13}),
        _record("newton", 0, 20, "MID"),
        _record("ptc", 0, 20, "MID", c_blockers=[{"core": "ptc", "columns": ["S2.n.C"]}]),
    ]
    summary = compare.summarize(records)
    assert summary["arms"]["ptc"]["classes"] == {"LOW": 1, "MID": 1, "HIGH": 1, "FAIL": 0}
    assert summary["arms"]["newton"]["map_rows_j0_to_j20"][0] == "LF" + "." * 19
    assert summary["arms"]["ptc"]["map_rows_j0_to_j20"][20] == "M" + "." * 20
    # The physical labels at (0, 0) and (1, 0) are both `L` (B08): only (0, 0) LOW agrees.
    assert summary["arms"]["ptc"]["agrees_with_physical_label"] == 1
    assert summary["ptc_reached_newton_not"] == [[1, 0]]
    assert summary["ptc_mid_starts"] == [[0, 20]]
    assert summary["b21"]["converged_unclassified"] == 0
    assert summary["b21"]["runs_with_c_blockers"] == 1
    assert summary["b21"]["c_final_max_abs_deviation_mol_s"] == pytest.approx(1e-13, rel=1e-3)
    assert summary["b21"]["runs_with_unattributed_bound_blocks"] == 0
    assert summary["b21"]["budget_exhausted"] == {}
    assert summary["b21"]["max_attempts_per_run"] == 1
    assert summary["b21"]["max_property_calls_per_run"] == 10
    document = {
        "host": {"machine_class": "synthetic"},
        "provenance": {"commit": "0" * 40, "tree_clean": True},
        "case_sha256": "0" * 64,
        "summary": summary,
    }
    assert "Starts PTC reaches and Newton does not: 1" in compare.render(document)


def test_the_harness_needs_an_explicit_action_and_restores_the_newton_core() -> None:
    with pytest.raises(SystemExit):
        compare.main([])
    original = region_module.solve_newton
    captured: list[tuple[str, ...]] = []
    with compare._newton_blocks(captured):
        assert region_module.solve_newton is not original
    assert region_module.solve_newton is original and captured == []


def test_b21_records_the_p_budget_facts_and_unattributed_blocks() -> None:
    """Review S2 / §3.1: a polish bound block (columns not recorded) is counted, and
    `BUDGET_EXHAUSTED` runs are split by budget, beside the most attempts and property calls."""
    polish = {"core": "ptc_polish", "attempt": 0, "columns": None}
    records = [
        _record("ptc", 0, 0, "LOW", bound_blocks=[polish]),
        _record(
            "ptc",
            1,
            0,
            "FAIL",
            outcome="BUDGET_EXHAUSTED",
            budget="ptc_steps",
            counters={"property_calls": 5300},
        ),
        _record(
            "newton",
            1,
            0,
            "FAIL",
            outcome="BUDGET_EXHAUSTED",
            budget="property_calls",
            attempts=[["BUDGET_EXHAUSTED", "BUDGET_EXHAUSTED", 50]] * 2,
            counters={"property_calls": 10000},
        ),
        _record("newton", 0, 0, "FAIL", crash="ValueError: x", counters=None, attempts=[]),
    ]
    b21 = compare.summarize(records)["b21"]
    assert b21["runs_with_unattributed_bound_blocks"] == 1
    assert b21["runs_with_c_blockers"] == 0
    assert b21["budget_exhausted"] == {"property_calls": 1, "ptc_steps": 1}
    assert b21["max_attempts_per_run"] == 2
    assert b21["max_property_calls_per_run"] == 10000
    assert b21["runs_without_exactly_one_attempt"] == 2
    assert b21["crashes_with_typed_outcome"] == 1


def test_results_json_is_strict_on_non_finite_values() -> None:
    """Review N7: a non-finite float is written as null, so the results file is strict JSON."""
    document = {"a": float("nan"), "b": [1.0, float("inf"), {"c": -float("inf")}], "d": 2}
    assert compare._finite(document) == {"a": None, "b": [1.0, None, {"c": None}], "d": 2}


def test_a_typed_end_without_a_solve_eo_step_keeps_its_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review S1: the outcome, message and meter are recorded before the step is read, so a plan
    that ends before its region is a crash that still carries its typed end. No method runs:
    `execute_plan` is a stub."""
    ended = PlanResult(
        outcome="INITIALIZATION_FAILED",
        state=None,
        steps=(),
        trace=Trace(),
        counters=Counters(property_calls=7),
        message="no opening\nsecond line",
    )
    monkeypatch.setattr(compare, "execute_plan", lambda **_: ended)
    record = compare.run_start("ptc", compare.start_rows()[0])
    assert record["outcome"] == "INITIALIZATION_FAILED"
    assert record["message"] == "no opening"
    assert record["counters"]["property_calls"] == 7
    assert record["crash"] is not None and record["crash"].startswith("ValueError")
    assert record["class"] == "FAIL" and record["accepted_steps"] is None


def _refuse_to_run(*_: Any) -> Any:
    raise AssertionError("--run started a run past its preconditions")


def test_run_refuses_a_dirty_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Review S3: a result from a modified tree is not attributable to its commit."""
    monkeypatch.setattr(compare, "provenance", lambda _: {"tree_clean": False})
    monkeypatch.setattr(compare, "run_start", _refuse_to_run)
    assert compare._run(tmp_path) == 1
    assert list(tmp_path.iterdir()) == []


def test_run_refuses_to_overwrite_a_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Review S3: a second invocation never replaces a first result."""
    monkeypatch.setattr(compare, "provenance", lambda _: {"tree_clean": True})
    monkeypatch.setattr(compare, "host", lambda: {"machine_class": "synthetic"})
    monkeypatch.setattr(compare, "run_start", _refuse_to_run)
    existing = tmp_path / "results-synthetic.json"
    existing.write_text("{}\n", encoding="utf-8")
    assert compare._run(tmp_path) == 1
    assert existing.read_text(encoding="utf-8") == "{}\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["results-synthetic.json"]
