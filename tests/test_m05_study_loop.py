"""M05 WO-6 on fakes (design note §7.2-§7.5, §6.8, §9.1; R-279, R-299): the parent checks P1-P5,
the poll and its noise floor, every candidate status and their precedence, the loop's stages,
retries, budgets and study statuses, the record, and readiness's start half.

Default gate: no Pyomo, no solve. The parent is a closed form in one decision T with an interior
maximum at 673 K; its inner objective is linear in w, so the noise floor's central differences
are exact.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import pytest

from openflowsheet.studies.trust_region import checks
from openflowsheet.studies.trust_region.checks import (
    NOT_CHECKED,
    NOT_STATIONARY_AT_DELTA,
    PARENT_CHECK_FAILED,
    PARENT_CONSTRAINT_VIOLATED,
    PARENT_LOCAL_EVIDENCE,
    PROJECTION_DISAGREES,
    REGIME_CHANGED,
    ConstraintValue,
    Decision,
    P2Reference,
    ParentSolve,
    TrfPoint,
    check_candidate,
    poll_points,
)
from openflowsheet.studies.trust_region.study import (
    BUDGET_EXHAUSTED,
    BUDGET_REFUSAL,
    DECISION_STABLE,
    IN_PROCESS_BUDGET,
    ITERATION_LIMIT,
    REAL_BUDGET,
    Budgets,
    StageRun,
    StudyBudget,
    disposition,
    run_study,
    trust_region_readiness,
)
from openflowsheet.studies.trust_region.trf_state import (
    TRF_CONVERGED,
    TRF_EXIT_WITHOUT_STEP,
    TRF_FEASIBLE_STALLED,
    TRF_MAX_ITERATIONS,
    TRF_STALLED_INCONSISTENT,
    TRF_SUBPROBLEM_FAILED,
    FrameworkReadiness,
    ReadinessReason,
    trf_error,
    truth_refused,
)

T: str = "heater.T_spec"
BOX = (653.15, 693.15)
DELTA = 0.5
DECISIONS = (Decision(T, *BOX, DELTA),)
#: The fake inner objective's slopes in w, and every solve's achieved coupling residuals.
DJ_DX, DJ_DT = 0.8, -0.002
RESIDUALS = (1e-6, 1e-4)
#: e_i = 2 (|∂J/∂X̂| ΔX + |∂J/∂ΔT̂| ΔT) for every fake solve.
E = 2.0 * (abs(DJ_DX) * RESIDUALS[0] + abs(DJ_DT) * RESIDUALS[1])


def objective(t: float) -> float:
    return 0.5 - ((t - 673.0) / 10.0) ** 2


@dataclass
class FakeParent:
    """J(T) = 0.5 − ((T − 673)/10)²; one execution per solve; each behaviour a predicate on T."""

    sense: Literal["maximize", "minimize"] = "maximize"
    uncertified: Callable[[float], bool] = lambda t: False
    regime: Callable[[float], str] = lambda t: "two_phase"
    violated: Callable[[float], bool] = lambda t: False
    j: Callable[[float], float] = objective
    calls: list[str] = field(default_factory=list)
    inner_calls: int = 0

    def solve(self, decisions: Mapping[str, float], *, solve_id: str, purpose: str) -> ParentSolve:
        t = decisions[T]
        self.calls.append(solve_id)
        bad = self.uncertified(t)
        return ParentSolve(
            solve_id=solve_id,
            purpose=purpose,
            decisions=dict(decisions),
            revision_sha256=f"rev-{t!r}",
            outcome="FAILED" if bad else "CONVERGED",
            certificate=None if bad else "VERIFIED",
            objective=None if bad else self.j(t),
            state=None if bad else {"x": t / 100.0, "y": 2.0},
            coupling=(0.2, 50.0),
            coupling_residuals=RESIDUALS,
            regimes={"flash": self.regime(t), "heater": "single"},
            constraints=(
                ConstraintValue("g", 1.0 if self.violated(t) else 0.0, 0.0, "<=", 1.0),
                ConstraintValue("T.upper", t, BOX[1], "<=", BOX[1]),
            ),
            executions=1,
            store_hits=0,
            coupling_record_sha256=f"cr-{solve_id}",
            limitations=("synthetic",),
        )

    def inner_objective(self, solve: ParentSolve, coupling: tuple[float, float]) -> float:
        self.inner_calls += 1
        assert solve.objective is not None
        return solve.objective + DJ_DX * (coupling[0] - 0.2) + DJ_DT * (coupling[1] - 50.0)


def budget(
    cold: int = 10_000, wall: float = 1e9, clock: Callable[[], float] | None = None
) -> StudyBudget:
    return StudyBudget(
        Budgets("test", cold, wall, None, None, "evaluations"),
        clock if clock is not None else (lambda: 0.0),
    )


def point(
    t: float, *, objective_shift: float = 0.0, state_shift: float = 0.0, **final: bool
) -> TrfPoint:
    return TrfPoint(
        objective(t) + objective_shift,
        {"x": t / 100.0 + state_shift, "y": 2.0},
        {"x": 1.0, "y": 1.0},
        final,
    )


def check(parent: FakeParent, t: float, gate: StudyBudget | None = None, **options: Any) -> Any:
    return check_candidate(
        parent,
        candidate_id="cand",
        stage="C",
        decisions=DECISIONS,
        at={T: t},
        reference_regimes={"flash": "two_phase", "heater": "single"},
        budget=gate if gate is not None else budget(),
        **options,
    )


# == the candidate statuses and their precedence (§7.4) ===========================================


def test_parent_local_evidence_at_the_optimum_with_every_check_recorded() -> None:
    parent = FakeParent()
    found = check(parent, 673.0, trf_point=point(673.0))
    assert found.status == PARENT_LOCAL_EVIDENCE
    assert [name for name in checks.CHECK_ORDER if name in found.checks] == list(checks.CHECK_ORDER)
    assert all(found.checks[name].passed for name in checks.CHECK_ORDER)
    assert [p.decisions[T] for p in found.poll] == [672.5, 673.5]
    assert parent.inner_calls == 4  # the noise floor: four inner solves, reused for the poll
    assert found.noise_floor is not None
    assert found.noise_floor.dj_dx == pytest.approx(DJ_DX, rel=1e-9)
    assert found.noise_floor.dj_dt == pytest.approx(DJ_DT, rel=1e-6)
    assert found.noise_floor.e_star == pytest.approx(E, rel=1e-6)
    assert all(p.e == pytest.approx(E, rel=1e-6) for p in found.poll)
    # Reported, not judged: c = −2/100 per K², half-width √(2(e* + e)/|c|).
    assert found.curvature[T] == pytest.approx(-0.02, rel=1e-9)
    assert found.indifference_halfwidth[T] == pytest.approx(
        math.sqrt(2.0 * (2.0 * found.noise_floor.e_star) / 0.02), rel=1e-9
    )
    assert found.limitations == ("synthetic",)


def test_not_stationary_at_delta_away_from_the_optimum() -> None:
    found = check(FakeParent(), 670.0, trf_point=point(670.0))
    assert found.status == NOT_STATIONARY_AT_DELTA
    rows = found.checks["P5"].values["points"]
    assert [row["pass"] for row in rows] == [True, False]  # 669.5 is worse, 670.5 better


def test_p5_is_judged_at_e_star_plus_e_j_exactly() -> None:
    """A poll point improving by just under e* + e_j passes; by just over it, fails."""
    for factor, status in ((0.99, PARENT_LOCAL_EVIDENCE), (1.01, NOT_STATIONARY_AT_DELTA)):

        def j(t: float, factor: float = factor) -> float:
            return 0.25 + (factor * 2.0 * E if t > 673.0 else 0.0)

        assert check(FakeParent(j=j), 673.0).status == status


def test_parent_check_failed_stops_at_p1() -> None:
    parent = FakeParent(uncertified=lambda t: True)
    found = check(parent, 673.0, trf_point=point(673.0))
    assert found.status == PARENT_CHECK_FAILED
    assert list(found.checks) == ["P1"] and found.poll == () and parent.calls == ["cand-P1"]


def test_regime_changed_precedes_constraints_and_projection() -> None:
    parent = FakeParent(regime=lambda t: "liquid", violated=lambda t: True)
    found = check(parent, 673.0, trf_point=point(673.0, objective_shift=1.0))
    assert found.status == REGIME_CHANGED
    assert [found.checks[n].passed for n in ("P4", "P3", "P2")] == [False, False, False]
    assert "P5" not in found.checks and found.poll == ()
    assert found.checks["P4"].values["changed"] == {
        "flash": {"reference": "two_phase", "found": "liquid"}
    }


def test_constraint_violated_precedes_projection_disagrees() -> None:
    found = check(
        FakeParent(violated=lambda t: True), 673.0, trf_point=point(673.0, objective_shift=1.0)
    )
    assert found.status == PARENT_CONSTRAINT_VIOLATED
    assert found.checks["P3"].values["violated"] == ["g"]
    assert found.checks["P2"].passed is False


def test_p3_tolerance_is_1e_9_of_the_scale_without_margin() -> None:
    within = ConstraintValue("c", 1.0 + 0.9e-9 * 2.0, 1.0, "<=", 2.0)
    beyond = ConstraintValue("c", 1.0 + 1.1e-9 * 2.0, 1.0, "<=", 2.0)
    lower = ConstraintValue("c", -1.1e-9, 0.0, ">=", 1.0)
    assert (within.holds, beyond.holds, lower.holds) == (True, False, False)
    assert ConstraintValue("c", math.nan, 0.0, "<=", 1.0).holds is False


@pytest.mark.parametrize(
    ("trf", "failed_on"),
    [
        (point(673.0, objective_shift=1.1e-3 * 0.5), "objective"),
        (point(673.0, state_shift=1.1e-3), "state"),
        (point(673.0, omitted_rows=False), "final_state_checks"),
        (TrfPoint(0.5, {"z": 1.0}, {"z": 1.0}), "no_mapped_variable"),
    ],
)
def test_projection_disagrees_on_each_p2_criterion(trf: TrfPoint, failed_on: str) -> None:
    found = check(FakeParent(), 673.0, trf_point=trf)
    assert found.status == PROJECTION_DISAGREES, failed_on
    assert "P5" not in found.checks  # no poll after an earlier failure


def test_p2_passes_within_its_tolerances_and_is_not_applicable_without_a_trf_point() -> None:
    near = point(673.0, objective_shift=0.9e-3 * 0.5, state_shift=0.9e-3)
    assert check(FakeParent(), 673.0, trf_point=near).checks["P2"].passed is True
    assert check(FakeParent(), 673.0).checks["P2"].as_document() == {
        "pass": None,
        "values": {"applicable": False},
    }


def test_p2_reads_the_supplied_reference_for_stage_a() -> None:
    def surrogate(solve: ParentSolve) -> P2Reference:
        assert solve.objective is not None
        return P2Reference("surrogate_revision_eo", solve.objective + 1.0, {"x": 6.73, "y": 2.0})

    found = check(FakeParent(), 673.0, trf_point=point(673.0), p2_reference=surrogate)
    assert found.status == PROJECTION_DISAGREES
    assert found.checks["P2"].values["reference"] == "surrogate_revision_eo"


def test_not_checked_when_the_budget_runs_out_before_and_during_the_check() -> None:
    parent = FakeParent()
    gate = budget(cold=0)
    found = check(parent, 673.0, gate)
    assert (found.status, found.stopped_by, parent.calls) == (NOT_CHECKED, "cold", [])
    gate = budget(cold=2)  # the targeted check and the minus point, then nothing
    found = check(parent, 673.0, gate, trf_point=point(673.0))
    assert (found.status, found.stopped_by, len(found.poll)) == (NOT_CHECKED, "cold", 1)
    assert found.checks["P1"].passed and "P5" not in found.checks


def test_minimizing_reverses_the_poll_s_improvement() -> None:
    found = check(FakeParent(sense="minimize"), 673.0)
    assert found.status == NOT_STATIONARY_AT_DELTA  # both neighbours are lower: improvements


# == the poll (§7.4) ===============================================================================


def test_the_poll_polls_only_inward_at_a_bound_and_clips_at_the_box() -> None:
    assert [(d, p[T], c) for _, d, p, c in poll_points(DECISIONS, {T: BOX[0]})] == [
        (1, BOX[0] + DELTA, False)
    ]
    near = BOX[1] - 0.2  # within δ of the bound, not at it
    assert [(d, p[T], c) for _, d, p, c in poll_points(DECISIONS, {T: near})] == [
        (-1, near - DELTA, False),
        (1, BOX[1], True),
    ]
    at = BOX[1] - 1e-6 * 20.0 * 0.5  # within 1e-6 scaled of the bound: at it
    assert [d for _, d, _, _ in poll_points(DECISIONS, {T: at})] == [-1]


def test_infeasible_poll_points_are_ignored_and_the_curvature_needs_both() -> None:
    parent = FakeParent(violated=lambda t: t > 673.0)
    found = check(parent, 673.0)
    assert found.status == PARENT_LOCAL_EVIDENCE
    assert [p.feasible for p in found.poll] == [True, False]
    assert found.checks["P5"].values["n_feasible"] == 1
    assert found.curvature[T] is None and found.indifference_halfwidth[T] is None


def test_p5_is_vacuous_without_a_feasible_poll_point() -> None:
    parent = FakeParent(uncertified=lambda t: t != 673.0)
    found = check(parent, 673.0)
    assert found.status == PARENT_LOCAL_EVIDENCE and found.checks["P5"].values["n_feasible"] == 0


# == the loop (§7.3) ===============================================================================


@dataclass
class FakeStage:
    """A scripted stage runner: each call pops (outcome, T or None, objective shift)."""

    script: list[tuple[str, float | None]]
    cold: int = 3
    calls: list[tuple[str, float, str]] = field(default_factory=list)

    def __call__(
        self, start: ParentSolve, *, run_id: str, radius_factor: float, budget: StudyBudget
    ) -> StageRun:
        outcome, t = self.script.pop(0)
        self.calls.append((run_id, radius_factor, start.solve_id))
        budget.charge(self.cold)
        return StageRun(
            run_id=run_id,
            outcome=outcome,
            decisions=None if t is None else {T: t},
            point=None if t is None else point(t),
            cold=self.cold,
            document={"iterations": [], "outcome_note": outcome},
        )


def ready() -> FrameworkReadiness:
    return FrameworkReadiness("READY", ())


def study(parent: FakeParent, stage_c: FakeStage, **options: Any) -> Any:
    options.setdefault("budget", budget())
    return run_study(
        parent,
        decisions=DECISIONS,
        start={T: 668.0},
        stage_c=stage_c,
        framework=ready,
        limitations=("synthetic",),
        **options,
    )


def test_decision_stable_from_stage_c_with_stage_a_recorded_skipped() -> None:
    stage = FakeStage([(TRF_CONVERGED, 673.0)])
    found = study(FakeParent(), stage)
    assert found.status == DECISION_STABLE
    assert found.stage_a == {"executed": False, "reason": "surrogate_not_promoted"}
    assert stage.calls == [("C1", 1.0, "S0")]
    assert found.best is not None and found.best.decisions == {T: 673.0}


@pytest.mark.parametrize(
    "outcome", [TRF_EXIT_WITHOUT_STEP, TRF_FEASIBLE_STALLED, TRF_MAX_ITERATIONS]
)
def test_every_outcome_with_a_model_goes_to_stage_b(outcome: str) -> None:
    """R-279: an exit without a step is a candidate; build log W2: so is max-iterations."""
    assert study(FakeParent(), FakeStage([(outcome, 673.0)])).status == DECISION_STABLE


def test_not_stationary_restarts_from_the_best_feasible_poll_point_until_the_limit() -> None:
    stage = FakeStage([(TRF_CONVERGED, 660.0), (TRF_CONVERGED, 662.0), (TRF_CONVERGED, 664.0)])
    found = study(FakeParent(), stage)
    assert found.status == ITERATION_LIMIT
    assert [c[2] for c in stage.calls] == [
        "S0",
        "cand-C1-poll-heater.T_spec-plus",
        "cand-C2-poll-heater.T_spec-plus",
    ]
    assert found.best is not None and found.best.decisions == {T: 664.5}
    assert (
        found.as_document(spec={}, environment={}, trf_theory="assumptions_hold")["best"]["stable"]
        is False
    )


@pytest.mark.parametrize(
    "abort", [TRF_STALLED_INCONSISTENT, TRF_SUBPROBLEM_FAILED, truth_refused("model_exception:x")]
)
def test_an_abort_is_retried_once_with_a_quarter_radius(abort: str) -> None:
    stage = FakeStage([(abort, None), (TRF_CONVERGED, 673.0)])
    found = study(FakeParent(), stage)
    assert found.status == DECISION_STABLE
    assert stage.calls == [("C1", 1.0, "S0"), ("C1-retry", 0.25, "S0")]
    assert [run["retry"] for run in found.runs] == [0, 1]
    assert (
        found.candidates[0].candidate_id == "cand-C1" and found.candidates[0].run_id == "C1-retry"
    )


def test_a_second_abort_fails_the_study() -> None:
    stage = FakeStage([(TRF_STALLED_INCONSISTENT, None), (TRF_SUBPROBLEM_FAILED, None)])
    found = study(FakeParent(), stage)
    assert found.status == f"FAILED(trf_aborted:{TRF_SUBPROBLEM_FAILED})"
    assert found.candidates == []


def test_a_trf_error_is_a_defect_and_never_retried() -> None:
    stage = FakeStage([(trf_error("exit_mismatch"), None), (TRF_CONVERGED, 673.0)])
    found = study(FakeParent(), stage)
    assert found.status == "FAILED(trf_aborted:TRF_ERROR(exit_mismatch))"
    assert len(stage.calls) == 1


def test_a_candidate_failure_other_than_p5_fails_the_study_with_its_status() -> None:
    parent = FakeParent(regime=lambda t: "liquid" if t > 670.0 else "two_phase")
    found = study(parent, FakeStage([(TRF_CONVERGED, 673.0)]))
    assert found.status == f"FAILED({REGIME_CHANGED})"


def test_start_not_certified() -> None:
    parent = FakeParent(uncertified=lambda t: t == 668.0)
    stage = FakeStage([])
    found = study(parent, stage)
    assert found.status == "FAILED(start_not_certified)" and stage.calls == []


def test_unsupported_when_the_framework_is_not_ready_and_nothing_runs() -> None:
    parent = FakeParent()

    def unpinned() -> FrameworkReadiness:
        return FrameworkReadiness(
            "UNSUPPORTED", (ReadinessReason("TRUST_REGION_FRAMEWORK_UNPINNED", "6.9"),)
        )

    found = run_study(
        parent,
        decisions=DECISIONS,
        start={T: 668.0},
        stage_c=FakeStage([]),
        budget=budget(),
        framework=unpinned,
    )
    assert found.status == "UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNPINNED)" and parent.calls == []


@pytest.mark.parametrize("cold", [0, 1, 4])
def test_budget_exhausted_before_s0_before_a_run_and_during_a_check(cold: int) -> None:
    """cold 0: before S0; 1: S0 spends it, before run C1; 4: S0 + the run's 3, then the check."""
    found = study(FakeParent(), FakeStage([(TRF_CONVERGED, 673.0)]), budget=budget(cold=cold))
    assert found.status == BUDGET_EXHAUSTED
    if cold == 4:
        assert found.candidates[0].status == NOT_CHECKED


def test_budget_exhausted_by_the_wall_clock() -> None:
    times = iter([0.0, 0.0, 0.0, 7200.0])
    gate = budget(wall=3600.0, clock=lambda: next(times, 7200.0))
    found = study(FakeParent(), FakeStage([(TRF_CONVERGED, 660.0)]), budget=gate)
    assert found.status == BUDGET_EXHAUSTED and gate.exhausted() == "wall"


def test_a_budget_refusal_is_the_study_s_only_when_the_study_cap_is_reached() -> None:
    gate = budget(cold=5)
    assert disposition(BUDGET_REFUSAL, gate) == "abort"  # the run's own cap
    gate.charge(5)
    assert disposition(BUDGET_REFUSAL, gate) == "budget"
    stage = FakeStage([(BUDGET_REFUSAL, None)], cold=10)
    assert study(FakeParent(), stage, budget=budget(cold=8)).status == BUDGET_EXHAUSTED


def test_stage_a_stable_stops_before_stage_c() -> None:
    stage_a, stage_c = FakeStage([(TRF_CONVERGED, 673.0)]), FakeStage([])
    found = study(FakeParent(), stage_c, stage_a=stage_a)
    assert found.status == DECISION_STABLE and stage_c.calls == []
    assert found.stage_a == {"executed": True, "runs": ["A0"]}
    assert found.candidates[0].stage == "A"


def test_stage_a_not_stable_hands_stage_c_the_best_checked_point() -> None:
    """best := argmax J over {S0, u_A, the feasible poll points} passing P1, P3 and P4."""
    stage_a, stage_c = FakeStage([(TRF_CONVERGED, 670.0)]), FakeStage([(TRF_CONVERGED, 673.0)])
    found = study(FakeParent(), stage_c, stage_a=stage_a)
    assert found.status == DECISION_STABLE
    assert stage_c.calls == [("C1", 1.0, "cand-A0-poll-heater.T_spec-plus")]


def test_stage_a_s_point_is_excluded_from_the_argmax_when_its_regime_changed() -> None:
    parent = FakeParent(regime=lambda t: "liquid" if t >= 670.0 else "two_phase")
    stage_a = FakeStage([(TRF_CONVERGED, 670.0)])
    stage_c = FakeStage([(trf_error("stop"), None)])
    found = study(parent, stage_c, stage_a=stage_a)
    assert stage_c.calls[0][2] == "S0"
    assert found.candidates[0].status == REGIME_CHANGED


def test_a_stage_a_abort_twice_leaves_stage_c_to_start_from_s0() -> None:
    stage_a = FakeStage([(TRF_SUBPROBLEM_FAILED, None), (TRF_SUBPROBLEM_FAILED, None)])
    stage_c = FakeStage([(TRF_CONVERGED, 673.0)])
    found = study(FakeParent(), stage_c, stage_a=stage_a)
    assert found.status == DECISION_STABLE and stage_c.calls[0][2] == "S0"
    assert found.stage_a["outcome"] == f"FAILED(trf_aborted:{TRF_SUBPROBLEM_FAILED})"


def test_a_stage_a_defect_still_fails_the_study() -> None:
    stage_a, stage_c = FakeStage([(trf_error("exit_mismatch"), None)]), FakeStage([])
    found = study(FakeParent(), stage_c, stage_a=stage_a)
    assert found.status == "FAILED(trf_aborted:TRF_ERROR(exit_mismatch))" and stage_c.calls == []


# == the record (§8.3, §9.1) =======================================================================


def test_the_record_s_accounting_adds_up_and_the_record_is_deterministic() -> None:
    def make() -> dict[str, Any]:
        stage = FakeStage(
            [(TRF_STALLED_INCONSISTENT, None), (TRF_CONVERGED, 670.0), (TRF_CONVERGED, 673.0)]
        )
        found = study(FakeParent(), stage)
        assert found.status == DECISION_STABLE
        document: dict[str, Any] = found.as_document(
            spec={"case": "fake"}, environment={}, trf_theory="assumptions_hold"
        )
        return document

    document = make()
    assert document == make()
    accounting = document["accounting"]
    totals = accounting["totals"]
    assert totals == {
        "trf_cold": 9,  # 3 runs × 3
        "parent_executions": 1 + 3 + 3,  # S0, two candidates (targeted + two poll points each)
        "store_hits": 0,
        "parent_solves": 7,
        "trf_runs": 3,
    }
    for name in ("trf_cold", "parent_executions"):
        assert sum(row[name] for row in accounting["by_stage"].values()) == totals[name]
        assert sum(row[name] for row in accounting["by_iteration"].values()) == totals[name]
    assert accounting["by_candidate"]["cand-C1"] == {
        "produce_trf_cold": 6,
        "check_parent_executions": 3,
    }
    assert accounting["budgets"]["cold_used"] == 9 + 7
    assert document["claims"] == {
        "global_optimality": False,
        "trf_theory": "assumptions_hold",
        "stationarity": "poll_at_delta",
    }
    assert [c["status"] for c in document["candidates"]] == [
        NOT_STATIONARY_AT_DELTA,
        PARENT_LOCAL_EVIDENCE,
    ]
    assert document["limitations"] == ["synthetic"]
    assert len(document["artifacts"]["coupled_runs"]) == 7


def test_the_registered_budgets() -> None:
    assert (REAL_BUDGET.study_cold, REAL_BUDGET.study_wall_s, REAL_BUDGET.run_cold) == (
        400,
        14400.0,
        250,
    )
    assert (IN_PROCESS_BUDGET.study_cold, IN_PROCESS_BUDGET.study_wall_s) == (2000, 3600.0)
    cap = StudyBudget(REAL_BUDGET).run_cap("C1")
    assert cap is not None and cap.cap == 250
    assert StudyBudget(IN_PROCESS_BUDGET).run_cap("C1") is None


# == readiness: the framework and start halves (§6.8; the projection half is nlp-tier) =========


def unavailable() -> FrameworkReadiness:
    return FrameworkReadiness(
        "UNSUPPORTED", (ReadinessReason("TRUST_REGION_FRAMEWORK_UNAVAILABLE", "no pyomo"),)
    )


def test_readiness_without_the_nlp_environment_is_unavailable_alone() -> None:
    parent = FakeParent(uncertified=lambda t: True)
    found = trust_region_readiness(
        start=lambda: parent.solve({T: 673.0}, solve_id="start", purpose="start"),
        framework=unavailable,
    )
    assert found.codes == ("TRUST_REGION_FRAMEWORK_UNAVAILABLE",) and parent.calls == []


def test_readiness_lists_every_failing_reason() -> None:
    def broken() -> FrameworkReadiness:
        return FrameworkReadiness(
            "UNSUPPORTED",
            (
                ReadinessReason("TRUST_REGION_FRAMEWORK_UNPINNED", "version"),
                ReadinessReason("TRSP_SOLVER_UNAUDITED", "sha"),
            ),
        )

    parent = FakeParent(uncertified=lambda t: True)
    found = trust_region_readiness(
        start=lambda: parent.solve({T: 673.0}, solve_id="start", purpose="start"),
        framework=broken,
    )
    assert found.status == "UNSUPPORTED"
    assert found.codes == (
        "TRUST_REGION_FRAMEWORK_UNPINNED",
        "TRSP_SOLVER_UNAUDITED",
        "START_NOT_CERTIFIED",
    )


def test_readiness_is_ready_with_a_certified_start() -> None:
    parent = FakeParent()
    found = trust_region_readiness(
        start=lambda: parent.solve({T: 673.0}, solve_id="start", purpose="start"),
        framework=ready,
    )
    assert found.as_document() == {"status": "READY", "reasons": []}


def test_the_default_install_answers_unavailable() -> None:
    """G12's readiness half, in whatever environment the gate runs: without Pyomo the answer is
    the unavailable reason alone."""
    import importlib.util

    if importlib.util.find_spec("pyomo") is not None:
        pytest.skip("Pyomo is installed here: the default-install answer is not observable")
    assert trust_region_readiness().codes == ("TRUST_REGION_FRAMEWORK_UNAVAILABLE",)


def test_a_replaced_field_keeps_the_solve_certified() -> None:
    """ParentSolve.certified needs a finite objective as well as the outcome and certificate."""
    solve = FakeParent().solve({T: 673.0}, solve_id="s", purpose="start")
    assert solve.certified and not replace(solve, objective=math.inf).certified


def test_decisions_of_the_fake_cover_the_sequence_type() -> None:
    sequence: Sequence[Decision] = DECISIONS
    assert sequence[0].half_width == 20.0
