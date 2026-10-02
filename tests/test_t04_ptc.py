"""T04 W5: the generic PTC core with safeguarded SER, on synthetic problems (T04 §7, §9.4, §9.9).

A19 (the seeds PTC-S1…S5), A20's seed rows (the ablations a policy value or the core's two
ablation seams can express), and the record shapes of §7.8. Every expectation is
`benchmarks/t04/reference_values.yaml`'s — the design lane's 40-digit twin of the same rules,
never this code's output. Tolerances are T04 §12's: outcomes, counts, rejection reasons and their
order exact; Δτ and φ 1e-12 relative (a different retry or step moves them by ≥ 1e-2); PTC-S1's
Δτ are exact powers of two and PTC-S4's landing is `+0.0` by its bit pattern.

The seeds are unscaled (every scale 1) one- and two-variable problems. PTC-S5 runs under a bare
controller built on the one `phase_contract.decide` (T03 §6.6's), because the tear path's
controller runs K03's cores and the region's is SYN-001's.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
import yaml
from jsonschema import Draft202012Validator

from openflowsheet.numerics.newton import Evaluation, NewtonResult, Problem
from openflowsheet.numerics.ptc import (
    PTC_ROW_SIGN,
    PtcProblem,
    PtcRecord,
    solve_ptc,
)
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.phase_contract import (
    Candidate,
    Conversion,
    WallObserver,
    decide,
)
from openflowsheet.orchestrator.trace import (
    PtcPolicy,
    SolvePolicy,
    Trace,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RELATIVE = 1e-12
SETTINGS = PtcPolicy()
POLICY = SolvePolicy(policy_id="T04-ptc-seeds", residual_tolerances={}, scales={})
UNIT = "U-SYN"


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t04" / "reference_values.yaml").read_text()
    )
    return loaded


# ------------------------------------------------------------------ the seeds (T04 §9.4)


@dataclass(frozen=True)
class Seed:
    ids: tuple[str, ...]
    rows: tuple[str, ...]
    accumulation: Mapping[str, str]
    residual: Callable[[np.ndarray], tuple[float, ...] | None]
    jacobian: Callable[[np.ndarray], np.ndarray]
    mass: np.ndarray
    tolerance: Mapping[str, float]
    lower: Mapping[str, float]
    x0: tuple[float, ...]
    #: The regime a state is in, when the seed has one (PTC-S2, PTC-S5).
    regime: Callable[[float], str] | None = None


def _band(x: float) -> str:
    """T03's PHS-SYN-1 bands: LIQUID below 1, TWO_PHASE below 2, VAPOR above."""
    return "LIQUID" if x < 1.0 else "TWO_PHASE" if x < 2.0 else "VAPOR"


HOLD = {"hold": "holdup_balance"}
SEEDS: dict[str, Seed] = {
    # S1: one vessel filling from empty, F = 1 − x, holdup θx
    "PTC-S1": Seed(
        ("x",), ("hold",), HOLD,
        lambda x: (1.0 - x[0],),
        lambda x: np.array([[-1.0]]),
        np.array([[1.0]]),
        {"hold": 1e-8}, {"x": 0.0}, (0.0,),
    ),
    # S2: F = 1 − x³ with a regime wall at x > 1.05
    "PTC-S2": Seed(
        ("x",), ("hold",), HOLD,
        lambda x: (1.0 - x[0] ** 3,),
        lambda x: np.array([[-3.0 * x[0] ** 2]]),
        np.array([[1.0]]),
        {"hold": 1e-8}, {"x": 0.0}, (0.1,),
        lambda x: "LIQUID" if x <= 1.05 else "VAPOR",
    ),
    # S3: an algebraic row whose Newton target y = 10 lies outside the evaluator's y ≤ 5
    "PTC-S3": Seed(
        ("x", "y"), ("hold", "alg"), {"hold": "holdup_balance", "alg": "algebraic"},
        lambda x: None if x[1] > 5.0 else (1.0 - x[0], x[1] - 10.0),
        lambda x: np.array([[-1.0, 0.0], [0.0, 1.0]]),
        np.array([[1.0, 0.0], [0.0, 0.0]]),
        {"hold": 1e-8, "alg": 1e-8}, {"x": 0.0}, (0.0, 0.0),
    ),
    # S4: a holdup whose steady state (−0.5) lies below its bound 0
    "PTC-S4": Seed(
        ("x",), ("hold",), HOLD,
        lambda x: (-0.5 - x[0],),
        lambda x: np.array([[-1.0]]),
        np.array([[1.0]]),
        {"hold": 1e-8}, {"x": 0.0}, (1.0,),
    ),
    # S5: T03's PHS-SYN-1 bands with F = 3 − x, holdup θx
    "PTC-S5": Seed(
        ("x",), ("hold",), HOLD,
        lambda x: (3.0 - x[0],),
        lambda x: np.array([[-1.0]]),
        np.array([[1.0]]),
        {"hold": 1e-12}, {}, (0.0,),
        _band,
    ),
}  # fmt: skip


def seed_problem(seed: Seed, evaluated: list[float] | None = None) -> PtcProblem:
    def residual(x: np.ndarray) -> Evaluation:
        if evaluated is not None:
            evaluated.append(float(x[0]))
        values = seed.residual(x)
        if values is None:
            return Evaluation(status="invalid_trial_state", message="y > 5: outside the domain")
        signature = ((UNIT, seed.regime(float(x[0]))),) if seed.regime is not None else None
        return Evaluation(status="ok", values=values, signature=signature)  # type: ignore[arg-type]

    problem = Problem(
        variable_ids=seed.ids,
        row_ids=seed.rows,
        residual=residual,
        jacobian=lambda x: sp.csc_matrix(seed.jacobian(x)),
        scaling=Scaling(column=dict.fromkeys(seed.ids, 1.0), row=dict.fromkeys(seed.rows, 1.0)),
        row_tolerance=seed.tolerance,
        lower_bounds=seed.lower,
    )
    return PtcProblem(problem, lambda x: sp.csc_matrix(seed.mass), seed.accumulation)


@dataclass
class SeedAttempt:
    regime: str | None
    result: NewtonResult
    record: PtcRecord


class SeedOps:
    """The bare controller's `PathOps` (T03 §6.6): a restart opens at the chosen phase-rejected
    trial in the regime it reported; no lifted conversions, no opening refusals."""

    lifted = False

    def converged(self, result: Any) -> None:
        return None

    def blocked(self, result: Any) -> None:
        return None

    def kernel_disagrees(self, result: Any) -> None:
        return None

    def at_candidate(self, candidate: Candidate, cause: str) -> Conversion:
        return Conversion(
            candidate.signature, candidate.x, "phase_rejected_trial", cause, trial=candidate
        )

    def opening_check(self, conversion: Any) -> None:
        return None


def run_seed(
    name: str,
    settings: PtcPolicy = SETTINGS,
    *,
    reset: bool = True,
    sign: Mapping[str, int] = PTC_ROW_SIGN,
    trace: Trace | None = None,
) -> tuple[str, list[SeedAttempt]]:
    """One seed under the generic core. PTC-S2 runs one attempt in its frozen regime; PTC-S5 runs
    the bare controller, which restarts through `decide` and — unless the reset ablation — opens
    every attempt's SER state at `tau_initial` (T04 §7.4)."""
    seed = SEEDS[name]
    ptc = seed_problem(seed)
    run = trace if trace is not None else Trace()
    x = np.array(seed.x0, dtype=np.float64)
    if name != "PTC-S5":
        signature = ((UNIT, "LIQUID"),) if seed.regime is not None else ()
        wall = WallObserver(POLICY)
        result, record = solve_ptc(
            ptc, x, settings, trace=run, signature=signature, observer=wall, sign=sign
        )
        regime = "LIQUID" if seed.regime is not None else None
        return result.outcome, [SeedAttempt(regime, result, record)]

    assert seed.regime is not None
    regime = seed.regime(float(x[0]))
    used: list[Any] = []
    attempts: list[SeedAttempt] = []
    carried: float | None = None
    for index in range(POLICY.max_attempts):
        signature = ((UNIT, regime),)
        used.append(signature)
        wall = WallObserver(POLICY)
        result, record = solve_ptc(
            ptc,
            x,
            settings,
            trace=run,
            signature=signature,  # type: ignore[arg-type]
            attempt=index,
            observer=wall,
            tau_start=None if reset else carried,
            sign=sign,
        )
        carried = record.tau_end
        attempts.append(SeedAttempt(regime, result, record))
        decision = decide(
            result,
            attempt_index=index,
            frozen=signature,  # type: ignore[arg-type]
            wall=wall,
            ops=SeedOps(),
            policy=POLICY,
            used=used,
        )
        if decision.kind != "restart":
            return decision.outcome, attempts
        assert decision.conversion is not None
        x = np.array(decision.conversion.opening, dtype=np.float64)
        regime = dict(decision.conversion.signature)[UNIT]
    raise AssertionError("unreachable: the restart gate ends the solve at max_attempts")


def events(record: PtcRecord) -> list[tuple[Any, ...]]:
    """Every trial of the attempt in order: `(step, tau, result, ...)` as the YAML lists them."""
    merged: list[tuple[Any, ...]] = [
        (r.index, r.retry, r.tau, r.reason, None) for r in record.rejections
    ]
    merged += [(s.index, s.retries, s.tau, "accepted", s) for s in record.steps]
    return sorted(merged, key=lambda entry: (entry[0], entry[1]))


def close(value: float, expected: Any) -> bool:
    target = float(expected)
    return abs(value - target) <= RELATIVE * abs(target)


#: T04 §12 as amended (F13): φ to max(1e-12 |φ|, 1e-15). φ is formed by cancellation against O(1)
#: operands (`1 − x`, `3 − x`, `1 − x³`), so its rounding is absolute, a few ulps of 1: measured
#: ≤ 1.7e-16 on every accepted step of the five seeds.
PHI_ABSOLUTE = 1e-15


def phi_close(value: float, expected: Any) -> bool:
    target = float(expected)
    return abs(value - target) <= max(RELATIVE * abs(target), PHI_ABSOLUTE)


def trajectory(name: str, ref: dict[str, Any]) -> list[tuple[Any, Mapping[str, Any]]]:
    """Every accepted pseudo-step of the seed paired with its registered event, after checking
    everything the registration fixes exactly: outcomes, counts, `blocked_by`, the order and
    reason of every trial, and Δτ, α and x at 1e-12 relative."""
    expected = ref["policy_simulation"]["ptc_seeds"][name]
    outcome, attempts = run_seed(name)
    assert outcome == expected["outcome"]
    assert len(attempts) == len(expected["attempts"])
    pairs: list[tuple[Any, Mapping[str, Any]]] = []
    for attempt, registered in zip(attempts, expected["attempts"], strict=True):
        assert attempt.regime == registered["regime"]
        assert attempt.result.outcome == registered["outcome"]
        assert attempt.result.iterations == registered["pseudo_steps"]
        assert list(attempt.result.blocked_by) == registered["blocked_by"]
        seen = events(attempt.record)
        assert len(seen) == len(registered["events"])
        for (step, _, tau, result, accepted), event in zip(seen, registered["events"], strict=True):
            assert (step, result) == (event["step"], event["result"])
            assert close(tau, event["tau"]), (name, step, tau, event["tau"])
            if accepted is None:
                continue
            (x,) = event["x"].values()
            assert close(accepted.alpha, event["alpha"])
            assert abs(float(accepted.x[0]) - float(x)) <= RELATIVE * max(1.0, abs(float(x)))
            if event["tau_next"] is None:
                assert accepted.tau_next is None and accepted.ser_ratio is None
            else:
                assert accepted.tau_next is not None and close(accepted.tau_next, event["tau_next"])
            pairs.append((accepted, event))
    return pairs


@pytest.mark.parametrize("name", ["PTC-S1", "PTC-S2", "PTC-S3", "PTC-S4", "PTC-S5"])
def test_a19_the_seed_takes_the_registered_trajectory(name: str, ref: dict[str, Any]) -> None:
    trajectory(name, ref)


@pytest.mark.parametrize("name", ["PTC-S1", "PTC-S2", "PTC-S4", "PTC-S5"])
def test_a19_phi_at_the_registered_tolerance(name: str, ref: dict[str, Any]) -> None:
    """T04 §12 (amended, F13): φ on every accepted pseudo-step within max(1e-12 |φ|, 1e-15)."""
    for accepted, event in trajectory(name, ref):
        assert phi_close(accepted.phi, event["phi"]), (name, accepted.index, accepted.phi)


def test_a19_ptc_s1_is_the_analytic_limit() -> None:
    """T04 §9.4: `e_{k+1} = e_k θ/(θ + Δτ_k)`, the SER ratio `1 + Δτ_k/θ ≥ 2` clipped to 2, so
    `Δτ_k = 2^k` exactly and `φ_{k+1} = 1/∏_{j≤k}(1 + 2^j)`; `CONVERGED` at pseudo-step 8."""
    _, (attempt,) = run_seed("PTC-S1")
    assert attempt.result.outcome == "CONVERGED" and attempt.result.iterations == 8
    product = 1.0
    for step in attempt.record.steps:
        assert step.tau == 2.0**step.index, "an exact power of two"
        product *= 1.0 + 2.0**step.index
        assert phi_close(step.phi, 1.0 / product)
    ratios = [step.ser_ratio for step in attempt.record.steps if step.ser_ratio is not None]
    assert ratios == [2.0] * 7
    assert attempt.record.polish == "accepted"


def test_a19_ptc_s4_lands_on_plus_zero_and_is_blocked() -> None:
    """T04 §9.4: Δτ = 2 lands `x` on `+0.0` exactly at `α_max = 1/2`; then every trial from Δτ = 3
    down to 3·2⁻¹⁰ is `bound_blocked` → `BOUND_BLOCKED` with `blocked_by = (x)`."""
    _, (attempt,) = run_seed("PTC-S4")
    landing = attempt.record.steps[1]
    assert landing.alpha == 0.5
    assert landing.x[0] == 0.0 and math.copysign(1.0, float(landing.x[0])) == 1.0
    assert landing.landing == ("x",)
    assert [r.reason for r in attempt.record.rejections] == ["bound_blocked"] * 11
    assert attempt.record.rejections[-1].tau == 3.0 * 2.0**-10
    assert attempt.result.blocked_by == ("x",)
    assert attempt.record.polish is None


def test_a19_ptc_s3_the_algebraic_stall() -> None:
    """§6.7 in two variables: every trial has `y = 10` whatever Δτ, outside `y ≤ 5`."""
    _, (attempt,) = run_seed("PTC-S3")
    assert attempt.result.outcome == "PTC_STALLED" and attempt.result.iterations == 0
    assert [r.tau for r in attempt.record.rejections] == [2.0**-k for k in range(11)]
    assert {r.reason for r in attempt.record.rejections} == {"invalid_trial"}


def test_a19_an_already_valid_root_stops_at_pseudo_step_0() -> None:
    """§7.4: the stop precedes everything — no Jacobian, no factorization, no polish."""
    seed = replace(SEEDS["PTC-S1"], x0=(1.0,))
    trace = Trace()
    result, record = solve_ptc(seed_problem(seed), np.array(seed.x0), SETTINGS, trace=trace)
    assert result.outcome == "CONVERGED" and result.iterations == 0
    assert result.counters.jacobian_calls == 0 and result.counters.factorizations == 0
    assert record.polish is None and record.steps == ()
    assert [event.kind for event in trace.events] == ["attempt_closed"]


def test_a19_the_step_budget() -> None:
    """§7.4: `max_steps_per_attempt` accepted pseudo-steps → `BUDGET_EXHAUSTED(ptc_steps)`."""
    _, (attempt,) = run_seed("PTC-S1", replace(SETTINGS, max_steps_per_attempt=5))
    assert attempt.result.outcome == "BUDGET_EXHAUSTED"
    assert attempt.result.budget == "ptc_steps"
    assert attempt.result.iterations == len(attempt.record.steps) == 5


# ------------------------------------------------------------------ A20: the seed ablations


@pytest.mark.parametrize(
    ("name", "seed", "settings", "reset", "sign"),
    [
        (
            "no_gamma_clip (PTC-S1)",
            "PTC-S1",
            replace(SETTINGS, gamma_min=0.0, gamma_max=math.inf),
            True,
            PTC_ROW_SIGN,
        ),
        (
            "row_sign_plus_one (PTC-S1)",
            "PTC-S1",
            SETTINGS,
            True,
            {"holdup_balance": 1, "zero_holdup_balance": 1, "algebraic": 1},
        ),
        (
            "tau_max_16 (PTC-S1, a policy override, not an ablation)",
            "PTC-S1",
            replace(SETTINGS, tau_max_s=16.0),
            True,
            PTC_ROW_SIGN,
        ),
        ("no_reset_on_restart (PTC-S5)", "PTC-S5", SETTINGS, False, PTC_ROW_SIGN),
    ],
)
def test_a20_the_registered_seed_ablations(
    name: str,
    seed: str,
    settings: PtcPolicy,
    reset: bool,
    sign: Mapping[str, int],
    ref: dict[str, Any],
) -> None:
    """T04 §9.9's rows a policy value or one of the core's two ablation seams expresses: the γ clip
    and the row sign are load-bearing, τ_max caps the growth, and the per-attempt reset is
    load-bearing (without it PTC-S5's third attempt ends `BUDGET_EXHAUSTED`).

    The rows the policy cannot express — the stop on ‖F̂‖ ≤ φ_floor, the proposed Δτ or the
    rejected residual in the update — are not implemented: that would put an unregistered rule
    into the core."""
    expected = ref["policy_simulation"]["ablations"][name]
    outcome, attempts = run_seed(seed, settings, reset=reset, sign=sign)
    assert outcome == expected["outcome"]
    assert [attempt.result.iterations for attempt in attempts] == expected["pseudo_steps"]


def test_a20_the_row_sign_ablation_meets_an_exactly_singular_matrix() -> None:
    """σ = +1 on PTC-S1: the first matrix is `θ/Δτ − 1 = 0` exactly at Δτ = θ, and the step
    toward the anti-dynamical side leaves the bound at every smaller pseudo-step."""
    _, (attempt,) = run_seed(
        "PTC-S1", sign={"holdup_balance": 1, "zero_holdup_balance": 1, "algebraic": 1}
    )
    reasons = [r.reason for r in attempt.record.rejections]
    assert reasons == ["linear_solve_failed"] + ["bound_blocked"] * 10
    assert attempt.result.outcome == "BOUND_BLOCKED" and attempt.result.blocked_by == ("x",)


@pytest.mark.parametrize("name", ["PTC-S1", "PTC-S2", "PTC-S3", "PTC-S4", "PTC-S5"])
def test_a20_the_phi_floor_is_inert(name: str, ref: dict[str, Any]) -> None:
    """§7.4's proof: a ratio is formed only when some row exceeds its tolerance, so φ ≥ τ̂_min ≫
    φ_floor. Removing the floor (φ_floor = 0) changes no count and no Δτ on any seed."""
    registered = [
        (attempt.result.iterations, [s.tau for s in attempt.record.steps])
        for attempt in run_seed(name)[1]
    ]
    unfloored = [
        (attempt.result.iterations, [s.tau for s in attempt.record.steps])
        for attempt in run_seed(name, replace(SETTINGS, phi_floor=0.0))[1]
    ]
    assert unfloored == registered
    assert ref["policy_simulation"]["ablations"]["no_phi_floor (every seed)"]["outcome"] == (
        "CONVERGED"
    )


# ------------------------------------------------------------------ records (§7.8)


def test_the_records_of_a_ptc_attempt_validate_and_carry_the_pseudo_steps() -> None:
    """§7.8: a rejected trial carries its Δτ and reason; `step_accepted` carries Δτ used, the SER
    proposal and the clipped ratio (null at the stop); the polish is a `trial` with message
    `polish` and no `pseudo_step`. Every event validates against the schema."""
    import json

    schema = json.loads((REPO_ROOT / "schemas" / "solve-event.schema.json").read_text())
    validator = Draft202012Validator(schema)
    trace = Trace()
    run_seed("PTC-S2", trace=trace)
    for event in trace.events:
        validator.validate(event.as_document())
    rejected = [event for event in trace.of_kind("trial") if event.pseudo_step is not None]
    assert [(e.pseudo_step, e.rejection_reason) for e in rejected] == [
        (1.0, "phase_update_required")
    ]
    accepted = trace.of_kind("step_accepted")
    assert [e.pseudo_step for e in accepted][:2] == [0.5, pytest.approx(0.630362669484680)]
    assert accepted[-1].pseudo_step_next is None and accepted[-1].ser_ratio is None
    assert all(e.pseudo_step_next is not None for e in accepted[:-1])
    (polish,) = [event for event in trace.of_kind("trial") if event.message.startswith("polish")]
    assert polish.message == "polish" and polish.trial_status == "accepted"
    assert polish.pseudo_step is None
    closed = trace.of_kind("attempt_closed")
    assert closed[-1].outcome == "CONVERGED" and closed[-1].iteration == 8


def test_the_row_sign_is_one_constant_applied_in_one_place() -> None:
    """A13's grep: `PTC_ROW_SIGN` is defined once, and σ is applied to `F` and `J` in the one
    function that builds the step (`row_signs`), not re-derived anywhere."""
    source = REPO_ROOT / "src" / "openflowsheet"
    definitions = [
        path
        for path in source.rglob("*.py")
        if "PTC_ROW_SIGN: Final" in path.read_text() or "PTC_ROW_SIGN =" in path.read_text()
    ]
    assert [path.name for path in definitions] == ["ptc.py"]
    assert dict(PTC_ROW_SIGN) == {"holdup_balance": -1, "zero_holdup_balance": 1, "algebraic": 1}


@pytest.mark.parametrize("name", ["PTC-S1", "PTC-S2", "PTC-S3", "PTC-S4", "PTC-S5"])
def test_every_factorization_carries_its_record(name: str) -> None:
    """ADR 0004 D2/D3: every factorization of a PTC attempt — one per trial, one for the polish —
    is counted, and every one that factorized carries its record on a `linear_solve` event; one
    that did not is a `linear_solve_failed` trial."""
    trace = Trace()
    _, attempts = run_seed(name, trace=trace)
    counted = sum(attempt.result.counters.factorizations for attempt in attempts)
    solved = len(trace.of_kind("linear_solve"))
    failed = sum(
        1 for event in trace.of_kind("trial") if event.rejection_reason == "linear_solve_failed"
    )
    assert counted == solved + failed > 0
    assert all(event.linear is not None for event in trace.of_kind("linear_solve"))


def test_the_row_sign_ablations_failed_factorization_is_a_trial_not_an_event() -> None:
    trace = Trace()
    run_seed(
        "PTC-S1",
        sign={"holdup_balance": 1, "zero_holdup_balance": 1, "algebraic": 1},
        trace=trace,
    )
    (failed,) = [e for e in trace.of_kind("trial") if e.rejection_reason == "linear_solve_failed"]
    assert failed.pseudo_step == 1.0 and failed.alpha is None and failed.state_sha256 == ""
    assert "exactly_singular" in failed.message or "singular" in failed.message


@pytest.mark.parametrize(
    ("status", "outcome", "polish"),
    [
        ("invalid_trial_state", "CONVERGED", "rejected:invalid_trial"),
        ("out_of_domain", "CONVERGED", "rejected:invalid_trial"),
        ("error", "EVALUATION_ERROR", "rejected:error"),
    ],
)
def test_the_polish_trial_rejected_or_a_defect(status: str, outcome: str, polish: str) -> None:
    """T04 §7.5 as ruled (F15 h): a polish trial that evaluates neither `ok` nor `error` is a
    rejected polish — the stopped iterate stands and the attempt is `CONVERGED`; an `error` is a
    defect and ends the attempt `EVALUATION_ERROR`. PTC-S1's pseudo-steps stay below
    x = 1 − 1e-10 (x₈ = 0.999 999 999 2); the polish's Newton step lands on 1 exactly, where this
    evaluator refuses."""
    seed = SEEDS["PTC-S1"]

    def residual(x: np.ndarray) -> Evaluation:
        if float(x[0]) >= 1.0 - 1e-10:
            return Evaluation(status=status, message="refused at the polish")  # type: ignore[arg-type]
        return Evaluation(status="ok", values=(1.0 - float(x[0]),))

    base = seed_problem(seed)
    ptc = replace(base, problem=replace(base.problem, residual=residual))
    trace = Trace()
    result, record = solve_ptc(ptc, np.array(seed.x0), SETTINGS, trace=trace)
    assert result.outcome == outcome
    assert result.iterations == 8 and record.polish == polish
    assert record.stopped_x is not None
    assert np.array_equal(result.x, record.stopped_x), "x_c stands"
    (trial,) = [e for e in trace.of_kind("trial") if e.message.startswith("polish")]
    assert trial.message == f"polish({polish})" and trial.trial_status == "rejected"
