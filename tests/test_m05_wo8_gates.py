"""M05 WO-8e and WO-8b: gates G5, G5b, G6, G7, G8 and G9 judged on the committed `M05-basis-v2`
records (design note §20.7 as restated by R-403 and R-404, G8 and G9 as restated by R-430 and
R-435 in §21.6; §13 for G7; build log S59-S63).

Each record under `benchmarks/m05/records/` was written by `scripts/m05_wo8_runs.py <CASE>` at
`OMP_NUM_THREADS=1` in the environment its `<stem>.environment.json` names; G10 is that script's
`--replay` in the same environment (nlp tier; the numbers are in the build log). The criteria are
read from §20.7's rows, never loosened here: a gate that fails stays failing.

Default gate: reads the committed files; nothing runs.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable, Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m05_replay as replay  # noqa: E402

RECORDS = REPO_ROOT / "benchmarks" / "m05" / "records"
CASES = ("TR-E2", "TR-E2-FAR", "TR-E2-FD", "LOOP-R", "LOOP-S")
T = "preheater.T_spec"
LINK = "link:reactor"
#: The golden-section reference optimum of TR-E2's loop, independent of TRF
#: (`tests/test_m05_c1_reference.py`, recorded on this machine), K.
T_REF = 673.6434377969885
#: §7.2's box [653.15, 693.15] K: lower bound and the scale h of d = (T − 673.15 K)/h, K.
T_LB, H = 653.15, 20.0
#: §7.4 (R-404, kept by R-430): "at the bound" is within 1e-6 scaled; reported by G8 and G9,
#: never gated (§21.1: the offset is Ipopt's, μ_k/z_L, not a property of the problem).
AT_BOUND_SCALED = 1e-6
#: §21.6 (R-435): G8's and G9's |T* − T_lb| ≤ δ_T, K.
DELTA_T = 0.5
#: §7.5: the study's iteration limit.
K_MAX = 3
#: §5.2's TR-E2 column of A1-A7 as build log S47 encodes it (G5 (e)).
TR_E2_ASSUMPTIONS = [
    {"id": "A1", "status": "holds_by_construction"},
    {"id": "A2", "status": "holds_by_construction"},
    {"id": "A3", "status": "holds_by_construction"},
    {"id": "A4", "status": "limitation"},
    {"id": "A5", "status": "holds_by_construction"},
    {"id": "A6", "status": "limitation"},
    {"id": "A7", "status": "limitation"},
]
ENDS = ("TRF_CONVERGED", "TRF_EXIT_WITHOUT_STEP")


def _stem(case: str) -> str:
    return f"trust-region-study-{case.lower()}"


def _read(name: str) -> Any:
    return json.loads((RECORDS / name).read_text(encoding="utf-8"))


def record(case: str) -> dict[str, Any]:
    return _read(f"{_stem(case)}.json")


def t_star(document: Mapping[str, Any]) -> float:
    return float(document["best"]["decisions"][T])


def candidate_of(document: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    (found,) = [item for item in document["candidates"] if item["run_id"] == run_id]
    return found


def stage_c(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [run for run in document["runs"] if run["stage"] == "C"]


def test_the_records_are_the_v2_set() -> None:
    """WO-8e and WO-8b: exactly the five cases, each under `M05-basis-v2` with its sidecars, in
    one environment at one OpenMP thread (S59)."""
    stems = {path.name.split(".")[0] for path in RECORDS.iterdir()}
    # WO-9's REAL record (`tests/test_m05_wo9_gates.py`) shares the directory, not this set.
    assert stems == {_stem(case) for case in CASES} | {"trust-region-study-real"}
    environments = []
    for case in CASES:
        document = record(case)
        assert document["spec"]["case"] == case
        assert document["spec"]["configs"]["basis"] == "M05-basis-v2"
        environments.append(_read(f"{_stem(case)}.environment.json"))
    assert all(item == environments[0] for item in environments)
    assert environments[0]["omp_num_threads"] == "1"


# -- G5: TR-E2 ---------------------------------------------------------------------------------


def _judge_registered_start(document: Mapping[str, Any]) -> None:
    """G5 (a)-(c) and G6 (a)-(c): the shared rows of a TR-E2 study from 673.15 K."""
    assert document["start"]["decisions"] == {T: 673.15}
    (run,) = stage_c(document)  # (c): one stage-C run
    assert run["run_id"] == "C1"
    assert run["outcome"] in ENDS  # (a)
    assert max(item["k"] for item in run["iterations"]) <= 30
    assert run["theta_recheck"] <= 1e-5  # (b)
    candidate = candidate_of(document, "C1")
    p2 = candidate["checks"]["P2"]
    assert p2["judged"] is True and p2["pass"] is True
    assert candidate["candidate_id"] == "cand-C1"  # (c)
    assert candidate["status"] == "PARENT_LOCAL_EVIDENCE"
    assert document["status"] == "DECISION_STABLE"


def test_g5_tr_e2() -> None:
    """G5 (§20.7): (a) C1 ends converged or without a step in ≤ 30 iterations, `basis.status`
    ok, a central stencil, c_X < 0; (b) θ_recheck ≤ 1e-5, P2 judged and passed; (c) cand-C1
    `PARENT_LOCAL_EVIDENCE`, `DECISION_STABLE` after one stage-C run; (d) |T* − T_ref| ≤ 0.5 K;
    (e) the assumptions block is §5.2's TR-E2 column."""
    document = record("TR-E2")
    _judge_registered_start(document)
    (run,) = stage_c(document)
    link = run["basis"]["links"][LINK]
    assert link["status"] == "ok" and link["stencil"] == "central"
    assert link["c"][0] < 0.0  # c_X: the conversion's curvature along the decision path
    assert abs(t_star(document) - T_REF) <= 0.5  # (d)
    assert run["assumptions"] == TR_E2_ASSUMPTIONS  # (e)


# -- G5b: TR-E2-FAR ----------------------------------------------------------------------------


def test_g5b_tr_e2_far() -> None:
    """G5b (§20.7, R-403): TR-E2 from 663.15 K: (a) `DECISION_STABLE` within K_max = 3; (b)
    |T* − T_ref| ≤ 0.5 K; (c) at least one run ends `TRF_CONVERGED`, each such run with
    `final_step_ratio` < 0.99 and a `PARENT_LOCAL_EVIDENCE` candidate; (d) no run ends
    `TRF_MAX_ITERATIONS` or aborts."""
    document = record("TR-E2-FAR")
    assert document["start"]["decisions"] == {T: 663.15}
    assert document["status"] == "DECISION_STABLE"  # (a)
    assert max(run["study_iteration"] for run in document["runs"]) <= K_MAX
    assert abs(t_star(document) - T_REF) <= 0.5  # (b)
    converged = [run for run in stage_c(document) if run["outcome"] == "TRF_CONVERGED"]
    assert converged  # (c)
    for run in converged:
        assert run["final_step_ratio"] < 0.99
        assert candidate_of(document, run["run_id"])["status"] == "PARENT_LOCAL_EVIDENCE"
    for run in document["runs"]:  # (d)
        assert not run["outcome"].startswith("TRF_MAX_ITERATIONS")
        assert run["error"] is None
    assert not document["status"].startswith("FAILED(")


# -- G6: TR-E2-FD ------------------------------------------------------------------------------


def test_g6_tr_e2_fd() -> None:
    """G6 (§20.7): (a)-(c) as G5's; (d) |T*_FD − T*_E2| ≤ 0.1 K against G5's record; (e)
    `fd_check` (`M05-fd-v2`) passes at η = 2⁻¹⁴, class `clean` or `truncation_dominated`, no
    escalation; (f) §8.3's identity with `basis_curvature_point` = 2 and R-406's
    `fdcheck_point` (the whole identity is `test_m05_study_record`'s, on every committed record)."""
    document = record("TR-E2-FD")
    _judge_registered_start(document)
    assert abs(t_star(document) - t_star(record("TR-E2"))) <= 0.1  # (d)
    check = document["fd_check"]  # (e)
    assert check["policy"] == "M05-fd-v2"
    assert check["selected_eta"] == 2.0**-14
    assert check["class"] in ("clean", "truncation_dominated")
    assert check["result"] == "pass" and check["stopped"] == "passed"
    assert len(check["candidates"]) == 1
    (run,) = stage_c(document)  # (f)
    counts = run["ledger"]["summary"][LINK]["by_purpose"]
    assert counts["basis_curvature_point"] == 2
    assert counts["fdcheck_point"] == 1 + 7 * 3  # one η: G(η/4), G(η), G(4η) over 7 inputs


# -- G7: accounting on every record ------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_g7_accounting(case: str) -> None:
    """G7 (§13, §20.7): the store bijection holds (S60); every holder's cold + store + memo
    requests equal its requests; no request served a non-finite output (every ledger entry `ok`);
    cold requests ≤ the study cap. The cap test itself (exactly cap cold requests and the budget
    refusal, serial value requests, R-405) is WO-8c's, in `test_m05_holders.py`."""
    stem = _stem(case)
    document = record(case)
    ledger = _read(f"{stem}.ledger.json")
    couplings = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (RECORDS / f"{stem}.coupling").glob("*.json")
    }
    store = _read(f"{stem}.store.json")
    assert store, "an empty store would make the bijection vacuous"
    assert replay.store_bijection_violations(store, ledger, couplings) == []
    for run in document["runs"]:
        for summary in run["ledger"]["summary"].values():
            served = sum(
                summary[f"{call}_{how}"]
                for call in ("value", "jacobian")
                for how in ("cold", "store_hit", "memo_hit")
            )
            assert served == summary["requests"] and summary["refused"] == 0
    assert all(entry["status"] == "ok" for block in ledger for entry in block["requests"])
    budgets = document["accounting"]["budgets"]
    assert budgets["cold_used"] <= budgets["study_cold"]
    assert not document["accounting"]["exhausted"]


# -- G9: LOOP-R --------------------------------------------------------------------------------


def _at_the_bound(
    document: Mapping[str, Any], record_property: Callable[[str, object], None]
) -> None:
    """§21.6's two rows of G8 and G9 (R-430, R-435): |T* − 653.15 K| ≤ δ_T (0.5 K); and P5's
    evidence contains the bound — no minus point (§7.4 read the candidate at the bound, so P5
    polled inward only), or the minus point clipped to exactly 653.15 K, feasible and passed.
    |d* − d_lb| and §7.4's reading are reported (`record_property`), not judged."""
    t = t_star(document)
    assert math.isfinite(t) and abs(t - T_LB) <= DELTA_T
    distance = abs(t - T_LB) / H
    at_bound = distance <= AT_BOUND_SCALED
    record_property("d_star_minus_d_lb_scaled", distance)
    record_property("section_7_4_at_the_bound", at_bound)
    candidate = candidate_of(document, document["runs"][-1]["run_id"])
    p5 = {point["check_id"]: point for point in candidate["checks"]["P5"]["values"]["points"]}
    minus = [point for point in candidate["poll"] if point["direction"] == -1]
    if not minus:
        assert at_bound  # §7.4's inward-only rule is the only way to have no minus point
        return
    (point,) = minus
    assert point["clipped"] is True and point["decisions"] == {T: T_LB}
    assert point["feasible"] is True
    assert p5[point["check_id"]]["pass"] is True


def test_g9_loop_r(record_property: Callable[[str, object], None]) -> None:
    """G9 (§21.6, R-435): stage A skipped with `surrogate_not_promoted`; stage C with
    `M05-basis-v2`; `DECISION_STABLE`; then G8's two rows (`_at_the_bound`). As committed: T*
    1.06e-6 K above the bound (5.3e-8 scaled, §7.4 at the bound), no minus point."""
    document = record("LOOP-R")
    assert document["stage_a"] == {"executed": False, "reason": "surrogate_not_promoted"}
    assert all(run["basis"]["policy"] == "M05-basis-v2" for run in stage_c(document))
    assert document["status"] == "DECISION_STABLE"
    _at_the_bound(document, record_property)


# -- G8: LOOP-S --------------------------------------------------------------------------------

#: F-22: M04.A19's PROMOTABLE smooth-synthetic prefix-plan manifest, as M04 committed it.
A19 = REPO_ROOT / "tests" / "fixtures" / "schemas" / "surrogate_manifest" / "valid"
A19_MANIFEST = A19 / "a19_smooth_prefix.json"


def _stage_a(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [run for run in document["runs"] if run["stage"] == "A"]


def test_g8_loop_s_stage_a_and_p2_a() -> None:
    """G8 (§20.7; R-407, R-408), first rows: stage A executed with the PROMOTABLE prefix-plan
    manifest; its run ends `TRF_EXIT_WITHOUT_STEP` or `TRF_CONVERGED` with P2_A judged and passed
    against the surrogate-backed `revision_eo` re-solve; `DECISION_STABLE`."""
    from openflowsheet.canonical import document_sha256

    document = record("LOOP-S")
    manifest = json.loads(A19_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["promotion"]["verdict"] == "PROMOTABLE" and manifest["plan_id"] == "it1-prefix"
    assert document["spec"]["surrogate"] == {
        "manifest_sha256": document_sha256(manifest),
        "verdict": "PROMOTABLE",
    }
    assert document["stage_a"]["executed"] is True
    (run,) = _stage_a(document)
    assert run["outcome"] in ENDS
    assert [truth["kind"] for truth in run["truth"]] == ["surrogate"]
    assert set(run["basis"].values()) == {"affine_taylor", "surrogate"}
    assert [run["basis"][name] for name in ("ef_ext_0", "ef_ext_1")] == ["surrogate"] * 2
    assert run["assumptions"] == TR_E2_ASSUMPTIONS  # §5.2: the surrogate as truth is eligible
    candidate = candidate_of(document, run["run_id"])
    p2 = candidate["checks"]["P2"]
    assert p2["judged"] is True and p2["pass"] is True
    assert p2["values"]["reference"] == "surrogate_revision_eo"
    assert document["status"] == "DECISION_STABLE"


def test_g8_loop_s_at_the_bound(record_property: Callable[[str, object], None]) -> None:
    """G8 (§21.6, R-430, R-435), last rows: `_at_the_bound` on LOOP-S, replacing R-404's
    |d* − d_lb| ≤ 1e-6 scaled and inward-only rows (build log S63, S64). As committed: T*
    653.150021930406 K, 2.193e-5 K above the bound (1.0965e-6 scaled, §7.4 interior), so P5 polled
    both sides and the minus point is clipped to 653.15 K, feasible and passed."""
    _at_the_bound(record("LOOP-S"), record_property)
