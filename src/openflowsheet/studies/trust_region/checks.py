"""The parent checks `M05-parent-checks-v1` (M05 design note §7.4): P1-P5 at a candidate, the
poll at the decision tolerance, its noise floor, and the candidate statuses.

A **candidate** is a decision vector u* (TRF's returned decisions, or S0's). Every check solves
the **parent** at it — the C1 revision with the heater specification at u*'s binary64 value,
canonicalized and solved through the route the document selects, uncommitted, labelled
`targeted_check` — through the `Parent` protocol, so the checks never see the route or the truth
(the parent adapter owns them; tests drive the checks with fakes):

- **P1**, targeted check: outcome `CONVERGED` and certificate `VERIFIED`;
- **P2**, gross agreement of TRF's state with the re-solve (a defect detector):
  |J_TRF − J*| ≤ 1e-3 · max(|J*|, 1e-12), max over the mapped variables of
  |x_TRF − x*| / column_scale ≤ 1e-3, and the run's own final-state checks (R-274 fact 4, R-296);
- **P3**, constraints on the certified state: every §7.1 inequality and bound within 1e-9 × its
  scale (no margin);
- **P4**, regimes: every unit's phase-regime label equals S0's;
- **P5**, poll at δ: for every feasible poll point j, s·(J_j − J*) ≤ e* + e_j (s = +1 maximizing).

**Order and status.** P1, P4, P3, P2 and P5 are evaluated in that order and the status is the
first failure (§7.4's table). A failed P1 leaves no certified state, so nothing after it is
evaluated. P4, P3 and P2 cost no solve and are always evaluated together on a certified state;
P5 (two coupled solves and four inner solves) only when they all pass — its only consumer is a
candidate that passed them (`NOT_STATIONARY_AT_DELTA` hands the study its best poll point). P2
does not apply to a candidate no TRF run produced (S0); it is then recorded with `pass: null`.

**The poll.** u* ± δ_j for each decision j. A decision within 1e-6 (scaled by its half-width)
of a bound is at the bound and only the inward point is polled; a point that would leave the box
is clipped to the bound. A point failing P1 or P3 is infeasible and ignored (extreme barrier).

**The noise floor.** For each solve i, e_i = 2 (|∂J/∂X̂| ΔX_i + |∂J/∂ΔT̂| ΔT_i) with (ΔX_i, ΔT_i)
the solve's *achieved* coupling residuals (the parent reads them from the certificate's
`EXT-COUPLING` checks) and the derivatives central differences of the parent's **inner** solve at
the candidate's converged w (h_X = 1e-4, h_T = 1e-2 K: four inner solves, reused for the poll
points). A parent without a coupling (no external unit) has e_i = 0.

**Reported, not judged.** Per decision, the curvature c = (J₊ − 2J* + J₋)/δ² when both poll points
are feasible and unclipped, and the indifference half-width √(2(e* + max e_j)/|c|) when s·c < 0.

**The budget** is checked before every solve (`BudgetGate`); a check it stops is `NOT_CHECKED`,
with everything evaluated before the stop recorded.

Pyomo-free (M03 G6): the default install imports this module.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol

__all__ = [
    "CHECKS_ID",
    "CHECK_ORDER",
    "NOT_CHECKED",
    "NOT_STATIONARY_AT_DELTA",
    "PARENT_CHECK_FAILED",
    "PARENT_CONSTRAINT_VIOLATED",
    "PARENT_LOCAL_EVIDENCE",
    "PROJECTION_DISAGREES",
    "REGIME_CHANGED",
    "BudgetGate",
    "CandidateCheck",
    "CheckResult",
    "ConstraintValue",
    "Decision",
    "NoiseFloor",
    "P2Reference",
    "Parent",
    "ParentSolve",
    "PollPoint",
    "TrfPoint",
    "check_candidate",
    "constraint_check",
    "gross_agreement",
    "noise_floor",
    "noise_term",
    "poll_points",
    "regime_check",
    "stationarity_check",
    "targeted_check",
]

CHECKS_ID: Final = "M05-parent-checks-v1"
#: P1: the outcome and certificate a certified solve has.
CERTIFIED_OUTCOME: Final = "CONVERGED"
CERTIFIED: Final = "VERIFIED"
#: P2's relative tolerances and the objective's floor.
P2_TOLERANCE: Final = 1e-3
P2_OBJECTIVE_FLOOR: Final = 1e-12
#: P3: a constraint holds within this fraction of its scale (no margin).
P3_TOLERANCE: Final = 1e-9
#: The poll: a decision this close to a bound, scaled by its half-width, is at the bound.
AT_BOUND_SCALED: Final = 1e-6
#: The noise floor: the factor on the linearized error, and the inner central-difference steps.
NOISE_FACTOR: Final = 2.0
H_CONVERSION: Final = 1e-4
H_RISE_K: Final = 1e-2

PARENT_CHECK_FAILED: Final = "PARENT_CHECK_FAILED"
REGIME_CHANGED: Final = "REGIME_CHANGED"
PARENT_CONSTRAINT_VIOLATED: Final = "PARENT_CONSTRAINT_VIOLATED"
PROJECTION_DISAGREES: Final = "PROJECTION_DISAGREES"
NOT_STATIONARY_AT_DELTA: Final = "NOT_STATIONARY_AT_DELTA"
PARENT_LOCAL_EVIDENCE: Final = "PARENT_LOCAL_EVIDENCE"
NOT_CHECKED: Final = "NOT_CHECKED"
#: §7.4: the evaluation order, and the status of each check's failure.
CHECK_ORDER: Final = ("P1", "P4", "P3", "P2", "P5")
FAILURE_STATUS: Final[Mapping[str, str]] = {
    "P1": PARENT_CHECK_FAILED,
    "P4": REGIME_CHANGED,
    "P3": PARENT_CONSTRAINT_VIOLATED,
    "P2": PROJECTION_DISAGREES,
    "P5": NOT_STATIONARY_AT_DELTA,
}

Sense = Literal["maximize", "minimize"]


@dataclass(frozen=True)
class Decision:
    """A decision, its box and its tolerance δ (§7.1: δ_T = 0.5 K)."""

    name: str
    lower: float
    upper: float
    tolerance: float

    @property
    def half_width(self) -> float:
        return 0.5 * (self.upper - self.lower)


@dataclass(frozen=True)
class ConstraintValue:
    """One §7.1 inequality or bound at a solved state: `value sense bound`, judged by P3 within
    `P3_TOLERANCE · scale`."""

    constraint_id: str
    value: float
    bound: float
    sense: Literal["<=", ">="]
    scale: float

    @property
    def violation(self) -> float:
        excess = self.value - self.bound if self.sense == "<=" else self.bound - self.value
        return max(0.0, excess)

    @property
    def holds(self) -> bool:
        return math.isfinite(self.value) and self.violation <= P3_TOLERANCE * self.scale

    def as_document(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "value": self.value,
            "bound": self.bound,
            "sense": self.sense,
            "scale": self.scale,
            "violation": self.violation,
            "holds": self.holds,
        }


@dataclass(frozen=True)
class ParentSolve:
    """One parent solve at `decisions` (§7.4; §8.2's coupled-check summary).

    `coupling` is the converged w = (X̂, ΔT̂) and `coupling_residuals` the achieved
    (ΔX, ΔT) of the certificate's `EXT-COUPLING` checks, both `None` for a parent without an
    external unit. `executions` and `store_hits` are the solve's experiments (they come from the
    run's coupling record, ADR 0034 D6); `executions` is what a budget is charged."""

    solve_id: str
    purpose: str
    decisions: Mapping[str, float]
    revision_sha256: str
    outcome: str
    certificate: str | None
    objective: float | None = None
    state: Mapping[str, float] | None = None
    coupling: tuple[float, float] | None = None
    coupling_residuals: tuple[float, float] | None = None
    regimes: Mapping[str, str] = field(default_factory=dict)
    constraints: tuple[ConstraintValue, ...] = ()
    executions: int = 0
    store_hits: int = 0
    coupling_record_sha256: str | None = None
    limitations: tuple[str, ...] = ()
    wall_s: float = 0.0

    @property
    def certified(self) -> bool:
        return (
            self.outcome == CERTIFIED_OUTCOME
            and self.certificate == CERTIFIED
            and self.objective is not None
            and math.isfinite(self.objective)
        )

    def as_document(self) -> dict[str, Any]:
        """§8.2's coupled-check summary, plus what the checks read (never the state)."""
        return {
            "check_id": self.solve_id,
            "purpose": self.purpose,
            "decisions": dict(self.decisions),
            "revision_sha256": self.revision_sha256,
            "outcome": self.outcome,
            "certificate": self.certificate,
            "objective": self.objective,
            "coupling": None if self.coupling is None else list(self.coupling),
            "coupling_residuals": (
                None if self.coupling_residuals is None else list(self.coupling_residuals)
            ),
            "regimes": dict(sorted(self.regimes.items())),
            "coupling_record_sha256": self.coupling_record_sha256,
            "experiments": {"executions": self.executions, "store_hits": self.store_hits},
            "limitations": list(self.limitations),
            "wall_s": self.wall_s,
        }


class Parent(Protocol):
    """The parent model the checks solve (§7.4). `solve` never raises for a failed solve: it
    returns the failure as `outcome`/`certificate`, which P1 judges."""

    @property
    def sense(self) -> Sense: ...

    def solve(
        self, decisions: Mapping[str, float], *, solve_id: str, purpose: str
    ) -> ParentSolve: ...

    def inner_objective(self, solve: ParentSolve, coupling: tuple[float, float]) -> float:
        """J of the parent's inner solve at `solve.decisions` with the coupling pinned at
        `coupling` (no reactor call): the noise floor's central differences."""
        ...


class BudgetGate(Protocol):
    """The study budget as the checks see it: asked before every solve, charged after it."""

    def exhausted(self) -> str | None: ...

    def charge_solve(self, solve: ParentSolve) -> None: ...


@dataclass(frozen=True)
class TrfPoint:
    """What P2 compares: a TRF run's returned objective (in the problem's units and sense) and
    state (every spec variable, `Projection.state_of`), the projection's column scales (R-275),
    and the run's own final-state checks by name (R-274 fact 4 `omitted_rows`, R-296
    `zero_pins`), `True` for pass."""

    objective: float
    state: Mapping[str, float]
    column_scales: Mapping[str, float]
    final_state_checks: Mapping[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class P2Reference:
    """P2's reference re-solve: the targeted parent solve itself (stage C), or the
    surrogate-backed `revision_eo` re-solve at u_A (stage A, §7.3)."""

    source: str
    objective: float
    state: Mapping[str, float]


@dataclass(frozen=True)
class CheckResult:
    check: str
    passed: bool | None
    values: Mapping[str, Any]

    def as_document(self) -> dict[str, Any]:
        return {"pass": self.passed, "values": dict(self.values)}


@dataclass(frozen=True)
class NoiseFloor:
    """∂J/∂X̂ and ∂J/∂ΔT̂ at the candidate's converged w, the four inner values they came from,
    and the candidate's e*."""

    dj_dx: float
    dj_dt: float
    e_star: float
    inner: tuple[tuple[tuple[float, float], float], ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "dJ_dX": self.dj_dx,
            "dJ_dT": self.dj_dt,
            "e_star": self.e_star,
            "h_X": H_CONVERSION,
            "h_T": H_RISE_K,
            "inner": [{"w": list(w), "J": value} for w, value in self.inner],
        }


@dataclass(frozen=True)
class PollPoint:
    decision: str
    direction: Literal[-1, 1]
    decisions: Mapping[str, float]
    clipped: bool
    solve: ParentSolve
    #: P1 and P3 at the point (the extreme barrier), and P4 (the study's argmax reads it, §7.3).
    feasible: bool
    regimes_match: bool
    e: float | None

    @property
    def objective(self) -> float | None:
        return self.solve.objective if self.feasible else None

    def as_document(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "direction": self.direction,
            "decisions": dict(self.decisions),
            "clipped": self.clipped,
            "check_id": self.solve.solve_id,
            "J": self.solve.objective,
            "e": self.e,
            "feasible": self.feasible,
            "regimes_match": self.regimes_match,
        }


@dataclass(frozen=True)
class CandidateCheck:
    """A candidate and its checks (§9.1's `candidates[]` entry)."""

    candidate_id: str
    run_id: str | None
    stage: str
    decisions: Mapping[str, float]
    status: str
    checks: Mapping[str, CheckResult]
    solves: tuple[ParentSolve, ...]
    poll: tuple[PollPoint, ...] = ()
    noise_floor: NoiseFloor | None = None
    curvature: Mapping[str, float | None] = field(default_factory=dict)
    indifference_halfwidth: Mapping[str, float | None] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    #: Why the check stopped early: the budget that ran out (`NOT_CHECKED`), else `None`.
    stopped_by: str | None = None

    @property
    def targeted(self) -> ParentSolve | None:
        return self.solves[0] if self.solves else None

    @property
    def objective(self) -> float | None:
        targeted = self.targeted
        return None if targeted is None or not targeted.certified else targeted.objective

    def as_document(self) -> dict[str, Any]:
        targeted = self.targeted
        return {
            "candidate_id": self.candidate_id,
            "run_id": self.run_id,
            "stage": self.stage,
            "decisions": dict(self.decisions),
            "label": "targeted_check",
            "revision_sha256": None if targeted is None else targeted.revision_sha256,
            "checks": {
                name: self.checks[name].as_document() for name in CHECK_ORDER if name in self.checks
            },
            "poll": [point.as_document() for point in self.poll],
            "noise_floor": None if self.noise_floor is None else self.noise_floor.as_document(),
            "curvature": dict(self.curvature),
            "indifference_halfwidth": dict(self.indifference_halfwidth),
            "status": self.status,
            "stopped_by": self.stopped_by,
            "limitations": list(self.limitations),
            "solves": [solve.as_document() for solve in self.solves],
        }


# -- the single checks ---------------------------------------------------------------------------


def targeted_check(solve: ParentSolve) -> CheckResult:
    """P1."""
    return CheckResult(
        "P1",
        solve.certified,
        {"check_id": solve.solve_id, "outcome": solve.outcome, "certificate": solve.certificate},
    )


def regime_check(solve: ParentSolve, reference: Mapping[str, str]) -> CheckResult:
    """P4: the same units with the same regime labels as S0's."""
    changed = sorted(
        unit
        for unit in set(reference) | set(solve.regimes)
        if reference.get(unit) != solve.regimes.get(unit)
    )
    return CheckResult(
        "P4",
        not changed,
        {
            "changed": {
                unit: {"reference": reference.get(unit), "found": solve.regimes.get(unit)}
                for unit in changed
            }
        },
    )


def constraint_check(solve: ParentSolve) -> CheckResult:
    """P3: every constraint the parent evaluated at the certified state holds within
    1e-9 × its scale. A parent that evaluated none fails (nothing was checked)."""
    violated = [item.constraint_id for item in solve.constraints if not item.holds]
    worst = max(
        (item.violation / item.scale for item in solve.constraints if item.scale > 0.0),
        default=0.0,
    )
    return CheckResult(
        "P3",
        bool(solve.constraints) and not violated,
        {"n": len(solve.constraints), "violated": violated, "worst_scaled_violation": worst},
    )


def gross_agreement(point: TrfPoint, reference: P2Reference) -> CheckResult:
    """P2: TRF's returned objective and state against the reference re-solve, over the variables
    both hold, plus the run's own final-state checks. No variable in common is a failure."""
    objective_error = abs(point.objective - reference.objective)
    objective_bound = P2_TOLERANCE * max(abs(reference.objective), P2_OBJECTIVE_FLOOR)
    mapped = sorted(set(point.state) & set(reference.state) & set(point.column_scales))
    worst_name, worst = None, 0.0
    for name in mapped:
        scaled = abs(point.state[name] - reference.state[name]) / point.column_scales[name]
        scaled = scaled if math.isfinite(scaled) else math.inf
        if worst_name is None or scaled > worst:
            worst_name, worst = name, scaled
    failed_final = sorted(name for name, ok in point.final_state_checks.items() if not ok)
    passed = (
        bool(mapped)
        and objective_error <= objective_bound
        and worst <= P2_TOLERANCE
        and not failed_final
    )
    return CheckResult(
        "P2",
        passed,
        {
            "reference": reference.source,
            "objective_trf": point.objective,
            "objective_reference": reference.objective,
            "objective_error": objective_error,
            "objective_bound": objective_bound,
            "n_mapped": len(mapped),
            "worst_state": worst,
            "worst_state_variable": worst_name,
            "final_state_checks_failed": failed_final,
        },
    )


def noise_term(floor: NoiseFloor | None, solve: ParentSolve) -> float:
    """e_i = 2 (|∂J/∂X̂| ΔX_i + |∂J/∂ΔT̂| ΔT_i); 0 for a parent without a coupling."""
    if floor is None or solve.coupling_residuals is None:
        return 0.0
    dx, dt = solve.coupling_residuals
    return NOISE_FACTOR * (abs(floor.dj_dx) * abs(dx) + abs(floor.dj_dt) * abs(dt))


def noise_floor(parent: Parent, solve: ParentSolve) -> NoiseFloor | None:
    """The candidate's derivatives of J in w by central differences of the inner solve at its
    converged w (four inner solves), and its e*. `None` without a coupling."""
    if solve.coupling is None:
        return None
    x, t = solve.coupling
    points = ((x + H_CONVERSION, t), (x - H_CONVERSION, t), (x, t + H_RISE_K), (x, t - H_RISE_K))
    values = tuple(parent.inner_objective(solve, w) for w in points)
    dj_dx = (values[0] - values[1]) / (points[0][0] - points[1][0])
    dj_dt = (values[2] - values[3]) / (points[2][1] - points[3][1])
    partial = NoiseFloor(dj_dx, dj_dt, 0.0, tuple(zip(points, values, strict=True)))
    return NoiseFloor(dj_dx, dj_dt, noise_term(partial, solve), partial.inner)


def poll_points(
    decisions: Sequence[Decision], at: Mapping[str, float]
) -> tuple[tuple[str, Literal[-1, 1], dict[str, float], bool], ...]:
    """The coordinate poll about `at`: (decision, direction, point, clipped), minus first."""
    points: list[tuple[str, Literal[-1, 1], dict[str, float], bool]] = []
    for decision in decisions:
        value = at[decision.name]
        scale = decision.half_width if decision.half_width > 0.0 else 1.0
        directions: tuple[Literal[-1, 1], ...] = (-1, 1)
        for direction in directions:
            bound = decision.lower if direction < 0 else decision.upper
            if abs(value - bound) / scale <= AT_BOUND_SCALED:
                continue  # at this bound: only the inward point
            moved = value + direction * decision.tolerance
            clipped = moved < decision.lower or moved > decision.upper
            point = dict(at)
            point[decision.name] = bound if clipped else moved
            points.append((decision.name, direction, point, clipped))
    return tuple(points)


def stationarity_check(
    sense: Sense, solve: ParentSolve, e_star: float, poll: Sequence[PollPoint]
) -> CheckResult:
    """P5 over the feasible poll points (vacuous when there is none)."""
    sign = 1.0 if sense == "maximize" else -1.0
    assert solve.objective is not None
    rows = []
    passed = True
    for point in poll:
        if not point.feasible:
            continue
        assert point.objective is not None and point.e is not None
        improvement = sign * (point.objective - solve.objective)
        allowance = e_star + point.e
        ok = improvement <= allowance
        passed = passed and ok
        rows.append(
            {
                "check_id": point.solve.solve_id,
                "improvement": improvement,
                "allowance": allowance,
                "pass": ok,
            }
        )
    return CheckResult("P5", passed, {"points": rows, "n_feasible": len(rows)})


def _curvatures(
    sense: Sense,
    decisions: Sequence[Decision],
    solve: ParentSolve,
    e_star: float,
    poll: Sequence[PollPoint],
) -> tuple[dict[str, float | None], dict[str, float | None]]:
    sign = 1.0 if sense == "maximize" else -1.0
    curvature: dict[str, float | None] = {}
    halfwidth: dict[str, float | None] = {}
    for decision in decisions:
        pair = {
            point.direction: point
            for point in poll
            if point.decision == decision.name and point.feasible and not point.clipped
        }
        if len(pair) != 2 or solve.objective is None:
            curvature[decision.name] = halfwidth[decision.name] = None
            continue
        minus, plus = pair[-1], pair[1]
        assert minus.objective is not None and plus.objective is not None
        c = (plus.objective - 2.0 * solve.objective + minus.objective) / decision.tolerance**2
        curvature[decision.name] = c
        e_max = max(point.e or 0.0 for point in poll if point.feasible)
        halfwidth[decision.name] = (
            math.sqrt(2.0 * (e_star + e_max) / abs(c)) if sign * c < 0.0 else None
        )
    return curvature, halfwidth


# -- the candidate -------------------------------------------------------------------------------


def check_candidate(
    parent: Parent,
    *,
    candidate_id: str,
    stage: str,
    decisions: Sequence[Decision],
    at: Mapping[str, float],
    reference_regimes: Mapping[str, str],
    budget: BudgetGate,
    run_id: str | None = None,
    trf_point: TrfPoint | None = None,
    p2_reference: Callable[[ParentSolve], P2Reference] | None = None,
    limitations: Sequence[str] = (),
) -> CandidateCheck:
    """Stage B at the candidate `at` (module docstring). `p2_reference` gives P2's reference
    re-solve (stage A's surrogate-backed one); without it the targeted solve is the reference."""
    checks: dict[str, CheckResult] = {}
    solves: list[ParentSolve] = []

    def result(
        status: str,
        stopped_by: str | None = None,
        poll: Sequence[PollPoint] = (),
        floor: NoiseFloor | None = None,
        curvature: Mapping[str, float | None] | None = None,
        halfwidth: Mapping[str, float | None] | None = None,
    ) -> CandidateCheck:
        stated = {item for solve in solves for item in solve.limitations}
        return CandidateCheck(
            candidate_id=candidate_id,
            run_id=run_id,
            stage=stage,
            decisions=dict(at),
            status=status,
            checks=dict(checks),
            solves=tuple(solves),
            poll=tuple(poll),
            noise_floor=floor,
            curvature=dict(curvature or {}),
            indifference_halfwidth=dict(halfwidth or {}),
            limitations=tuple(sorted(stated | set(limitations))),
            stopped_by=stopped_by,
        )

    def solve(point: Mapping[str, float], solve_id: str, purpose: str) -> ParentSolve | None:
        if budget.exhausted() is not None:
            return None
        solved = parent.solve(point, solve_id=solve_id, purpose=purpose)
        budget.charge_solve(solved)
        solves.append(solved)
        return solved

    targeted = solve(at, f"{candidate_id}-P1", "targeted_check")
    if targeted is None:
        return result(NOT_CHECKED, budget.exhausted())
    checks["P1"] = targeted_check(targeted)
    if not checks["P1"].passed:
        return result(PARENT_CHECK_FAILED)
    checks["P4"] = regime_check(targeted, reference_regimes)
    checks["P3"] = constraint_check(targeted)
    if trf_point is None:
        checks["P2"] = CheckResult("P2", None, {"applicable": False})
    else:
        assert targeted.state is not None and targeted.objective is not None
        reference = (
            p2_reference(targeted)
            if p2_reference is not None
            else P2Reference("parent_targeted_check", targeted.objective, targeted.state)
        )
        checks["P2"] = gross_agreement(trf_point, reference)
    for name in ("P4", "P3", "P2"):
        if checks[name].passed is False:
            return result(FAILURE_STATUS[name])

    stop = budget.exhausted()
    if stop is not None:
        return result(NOT_CHECKED, stop)
    floor = noise_floor(parent, targeted)
    e_star = 0.0 if floor is None else floor.e_star
    poll: list[PollPoint] = []
    for name, direction, point, clipped in poll_points(decisions, at):
        sign = "plus" if direction > 0 else "minus"
        solved = solve(point, f"{candidate_id}-poll-{name}-{sign}", "poll")
        if solved is None:
            return result(NOT_CHECKED, budget.exhausted(), poll, floor)
        feasible = targeted_check(solved).passed is True and constraint_check(solved).passed is True
        poll.append(
            PollPoint(
                decision=name,
                direction=direction,
                decisions=point,
                clipped=clipped,
                solve=solved,
                feasible=feasible,
                regimes_match=bool(regime_check(solved, reference_regimes).passed),
                e=noise_term(floor, solved) if feasible else None,
            )
        )
    sense = parent.sense
    checks["P5"] = stationarity_check(sense, targeted, e_star, poll)
    curvature, halfwidth = _curvatures(sense, decisions, targeted, e_star, poll)
    status = PARENT_LOCAL_EVIDENCE if checks["P5"].passed else NOT_STATIONARY_AT_DELTA
    return result(status, None, poll, floor, curvature, halfwidth)
