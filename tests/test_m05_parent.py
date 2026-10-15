"""M05 build decision S3: the C1 parent adapter `studies/trust_region/parent.py` (design note §7.4,
§7.2, §6.4) on the stand-in loop `C1-LOOP-M02-v1`.

- A solve is the revision with the heater's outlet-temperature specification at the decision,
  solved through `revision_coupled` on the study's runner: `CONVERGED`, `VERIFIED`, J the flash's
  liquid NH₃, w the final inner binding's, (ΔX, ΔT) the certificate's `EXT-COUPLING` values with
  ΔX per n_N₂,in, the experiments counted from `external-coupling.json`.
- The same decision again is served by the store: no execution, the same state bitwise.
- P4's labels are the units' own phase signatures; P3's constraints hold at S0.
- The inner objective at the solve's own w is J (an inner solve from the certified state).
- Stage B (`check_candidate`) and the loop (`run_study`, a stage C that returns its start) run
  end to end on the adapter.
- A refused route and a refusing verifier are outcomes, never raised.

Default gate: no Pyomo, the stand-in is in-process. `project_at` (the `nlp` environment) and the
real reactor v3 (`c1-loop-real.json`, the `pymrm` environment) are opt-in.
"""

from __future__ import annotations

import json
import math
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application import revision_run
from openflowsheet.application.revision_run import RunUnsupportedError
from openflowsheet.canonical import document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.studies.trust_region import parent as parent_module
from openflowsheet.studies.trust_region.checks import (
    NOT_STATIONARY_AT_DELTA,
    PARENT_LOCAL_EVIDENCE,
    ParentSolve,
    TrfPoint,
    check_candidate,
    constraint_check,
    regime_check,
    stationarity_check,
)
from openflowsheet.studies.trust_region.parent import C1Parent, coupling_counts
from openflowsheet.studies.trust_region.study import (
    DECISION_STABLE,
    IN_PROCESS_BUDGET,
    ITERATION_LIMIT,
    REAL_BOX,
    TR_E2_BOX,
    StageRun,
    StudyBudget,
    run_study,
)
from openflowsheet.studies.trust_region.trf_state import TRF_CONVERGED, FrameworkReadiness
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.verify.checks import VerifierError

LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
REAL_LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-real.json"
DECISION = "preheater.T_spec"
NOMINAL = 673.15


def loop(path: Path = LOOP_PATH) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def runner_in(root: Path) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(root, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="m05-parent", constants_sha256="0" * 64),
    )


def standin(root: Path) -> C1Parent:
    return C1Parent(loop(), runner_in(root), TR_E2_BOX)


@cache
def nominal(root: str) -> tuple[C1Parent, ParentSolve]:
    """The stand-in parent on a fresh store and its solve at the nominal decision (cached per
    root: a coupled solve per test is avoidable cost)."""
    built = standin(Path(root))
    return built, built.solve({DECISION: NOMINAL}, solve_id="S0", purpose="start")


@pytest.fixture(scope="module")
def s0(tmp_path_factory: pytest.TempPathFactory) -> tuple[C1Parent, ParentSolve]:
    return nominal(str(tmp_path_factory.mktemp("m05-parent")))


# == the solve =====================================================================================


def test_a_solve_is_the_certified_coupled_route_at_the_decision(
    s0: tuple[C1Parent, ParentSolve],
) -> None:
    built, solved = s0
    assert (solved.outcome, solved.certificate, solved.certified) == ("CONVERGED", "VERIFIED", True)
    assert solved.state is not None and solved.coupling is not None
    assert solved.state["S3.T"] == NOMINAL
    assert solved.objective == solved.state["S6.n.NH3"]
    assert solved.revision_sha256 == document_sha256(built.document_at({DECISION: NOMINAL}))
    # M02 G8 (a): the stand-in converges at k = 1 with exactly two experiments, none cached.
    assert (solved.executions, solved.store_hits) == (2, 0)
    assert solved.limitations == ("synthetic",)  # the stand-in is a synthetic variant
    assert solved.coupling_record_sha256 is not None


def test_w_and_the_achieved_residuals_are_the_coupling_records(
    s0: tuple[C1Parent, ParentSolve],
) -> None:
    """w is the record's final iterate; ΔX = |ξ_E − X̂ n_N₂,in| / n_N₂,in and
    ΔT = |T_E − T_in − ΔT̂| at it (§7.4), recomputed here from the record and the state."""
    built, solved = s0
    route = revision_run.select_route(built.document_at({DECISION: NOMINAL}))
    assert isinstance(route, revision_run.Route)
    result = revision_run.solve_route(
        route,
        built.document_at({DECISION: NOMINAL}),
        policy=built.policy,
        check_policy=built.check_policy,
        experiments=built.experiments,
    )
    assert result.coupling is not None and result.state is not None
    final = result.coupling["iterations"][-1]
    assert [float(v) for v in final["w"]] == list(solved.coupling or ())
    entry = final["units"]["reactor"]
    assert solved.state == dict(result.state)
    x_hat, dt_hat = solved.coupling or (math.nan, math.nan)
    n_n2 = solved.state["S3.n.N2"]
    dx = abs(entry["xi_E"] - x_hat * n_n2) / n_n2
    dt = abs(entry["T_E"] - solved.state["S3.T"] - dt_hat)
    assert solved.coupling_residuals is not None
    assert solved.coupling_residuals[1] == dt
    assert solved.coupling_residuals[0] == pytest.approx(dx, rel=1e-12, abs=1e-300)
    # The record served from the store: both experiments are hits, none executes.
    assert coupling_counts(result.coupling) == (0, 2)


def test_the_same_decision_again_is_served_by_the_store(s0: tuple[C1Parent, ParentSolve]) -> None:
    built, solved = s0
    again = built.solve({DECISION: NOMINAL}, solve_id="again", purpose="poll")
    assert (again.executions, again.store_hits) == (0, 2)
    assert again.state == solved.state and again.objective == solved.objective
    assert again.coupling == solved.coupling


def test_a_decision_edits_the_heater_specification_only(tmp_path: Path) -> None:
    built = standin(tmp_path)
    moved = built.solve({DECISION: 663.15}, solve_id="m", purpose="poll")
    assert moved.certified and moved.state is not None
    assert moved.state["S3.T"] == 663.15
    edited = built.document_at({DECISION: 663.15})
    changed = [
        item["id"]
        for item, base in zip(
            edited["specifications"], built.document["specifications"], strict=True
        )
        if item != base
    ]
    assert changed == ["SPEC-S3-T"]
    with pytest.raises(ValueError, match="not the study's"):
        built.document_at({"flash.T_spec": 253.15})


def test_the_parent_decision_and_its_box() -> None:
    built = C1Parent(loop(), runner_in(Path("/nonexistent-never-run")), REAL_BOX)
    (decision,) = built.decisions
    assert (decision.name, decision.lower, decision.upper, decision.tolerance) == (
        DECISION,
        653.15,
        693.15,
        0.5,
    )
    assert built.sense == "maximize"


# == what the checks read ==========================================================================


def test_p4_s_labels_are_the_units_phase_signatures(s0: tuple[C1Parent, ParentSolve]) -> None:
    _, solved = s0
    assert set(solved.regimes) == {
        "makeup",
        "mixer",
        "preheater",
        "flash",
        "splitter",
        "NH3",
        "purge",
    }
    assert solved.regimes["flash"] == "TWO_PHASE"
    assert solved.regimes["preheater"] == "VAPOR"
    assert regime_check(solved, solved.regimes).passed is True
    assert regime_check(solved, {**solved.regimes, "flash": "VAPOR"}).passed is False


def test_p3_s_constraints_hold_at_s0(s0: tuple[C1Parent, ParentSolve]) -> None:
    built, solved = s0
    assert solved.constraints
    assert [c.constraint_id for c in solved.constraints if not c.holds] == []
    assert constraint_check(solved).passed is True
    ids = {c.constraint_id for c in solved.constraints}
    assert {f"decision.{DECISION}.lower", "admissibility.X.upper", "hard_domain.S3.T.upper"} <= ids


def test_the_inner_objective_at_the_solves_own_w_is_j(s0: tuple[C1Parent, ParentSolve]) -> None:
    built, solved = s0
    assert solved.coupling is not None and solved.objective is not None
    inner = built.inner_objective(solved, solved.coupling)
    assert inner == pytest.approx(solved.objective, rel=1e-12)
    x, t = solved.coupling
    assert math.isfinite(built.inner_objective(solved, (x + 1e-4, t)))


# == stage B and the loop on the adapter ===========================================================


def test_stage_b_runs_end_to_end_on_the_adapter(s0: tuple[C1Parent, ParentSolve]) -> None:
    built, solved = s0
    budget = StudyBudget(IN_PROCESS_BUDGET)
    checked = check_candidate(
        built,
        candidate_id="cand-B",
        stage="C",
        decisions=built.decisions,
        at={DECISION: NOMINAL},
        reference_regimes=solved.regimes,
        budget=budget,
    )
    assert checked.status in (PARENT_LOCAL_EVIDENCE, NOT_STATIONARY_AT_DELTA)
    assert [checked.checks[name].passed for name in ("P1", "P4", "P3")] == [True] * 3
    assert len(checked.solves) == 3 and len(checked.poll) == 2
    assert all(point.feasible and point.regimes_match for point in checked.poll)
    floor = checked.noise_floor
    assert floor is not None and math.isfinite(floor.e_star) and floor.e_star >= 0.0
    targeted = checked.targeted
    assert targeted is not None and targeted.objective == solved.objective
    again = stationarity_check("maximize", targeted, floor.e_star, checked.poll)
    assert again.passed is (checked.status == PARENT_LOCAL_EVIDENCE)
    assert budget.cold.used == sum(s.executions for s in checked.solves)


def test_the_loop_runs_on_the_adapter(tmp_path: Path) -> None:
    """`run_study` with a stage C that returns its start: S0 on the adapter, then stage B at the
    start (P2 against its own state passes), until a stable decision or the iteration limit."""
    built = standin(tmp_path)

    def stay(
        start: ParentSolve, *, run_id: str, radius_factor: float, budget: StudyBudget
    ) -> StageRun:
        assert start.state is not None and start.objective is not None
        point = TrfPoint(start.objective, start.state, dict.fromkeys(start.state, 1.0))
        return StageRun(run_id, TRF_CONVERGED, dict(start.decisions), point, 0, {})

    budget = StudyBudget(IN_PROCESS_BUDGET)
    result = run_study(
        built,
        decisions=built.decisions,
        start={DECISION: NOMINAL},
        stage_c=stay,
        budget=budget,
        framework=lambda: FrameworkReadiness("READY", ()),
    )
    assert result.status in (DECISION_STABLE, ITERATION_LIMIT)
    assert result.s0 is not None and result.s0.certified
    assert result.candidates and result.candidates[0].checks["P2"].passed is True
    executed = result.s0.executions + sum(
        solve.executions for candidate in result.candidates for solve in candidate.solves
    )
    assert budget.cold.used == executed


# == refusals are outcomes =========================================================================


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (
            RunUnsupportedError("external_runner_unavailable"),
            "unsupported(external_runner_unavailable)",
        ),
        (VerifierError("cannot judge"), "verifier_refused(cannot judge)"),
    ],
)
def test_a_refused_solve_is_an_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception, outcome: str
) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise error

    monkeypatch.setattr(parent_module, "solve_route", refuse)
    refused = standin(tmp_path).solve({DECISION: NOMINAL}, solve_id="x", purpose="start")
    assert (refused.outcome, refused.certificate, refused.state) == (outcome, None, None)
    assert not refused.certified and refused.executions == 0


# == opt-in ========================================================================================


@pytest.mark.nlp
def test_project_at_s0_links_the_parent_truth(s0: tuple[C1Parent, ParentSolve]) -> None:
    """Stage C's projection at S0: one link EF, the parent truth on the study's runner, at the
    certified state, so the first truth evaluation at w₀ is the coupled solve's store hit."""
    built, solved = s0
    projection = built.project_at(solved)
    (link,) = [holder for holder in projection.holders if holder.kind == "truth"]
    assert link.truth_identity["kind"] == built.truth.describe()["kind"]
    assert built.truth.runner is built.runner


@pytest.mark.pymrm
def test_the_real_reactor_v3_parent_solves_at_the_nominal_decision(tmp_path: Path) -> None:
    built = C1Parent(loop(REAL_LOOP_PATH), runner_in(tmp_path), REAL_BOX)
    assert built.variant.variant_id == "pymrm-6089593-g2-nz800-s123-v3"
    solved = built.solve({DECISION: NOMINAL}, solve_id="S0", purpose="start")
    assert (solved.outcome, solved.certificate) == ("CONVERGED", "VERIFIED"), solved
    assert solved.executions > 0 and solved.coupling_residuals is not None
    assert constraint_check(solved).passed is True
