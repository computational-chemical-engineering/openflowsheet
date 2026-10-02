"""T03: the phase-attempt contract on the A02 family (ADR 0005; T03 specification §4–§6).

Every expectation comes from `benchmarks/t03/reference_values.yaml`, which the specification's
generator emits from a 40-digit twin of the contract on an exact reduction of the A02 region
(T03 §6.1) — never from this code. Per T03 §11's conventions: trial temperatures, restart points,
β and `α_max` at 1e-9 relative (the 53-bit floor of the same algorithm is 1.5e-16, a different
halving moves a trial by ≥ 0.1 K); counts, halvings, signatures, sources, causes and outcomes
exactly; final states by T02 A28's per-kind allowances.

The trial temperatures are not on the trace (a trial event carries its state's hash), so the
region's per-attempt residual is observed: every call it receives is logged with the attempt and
`S3.T`, and matched in order against the trace's `trial` / `step_accepted` events. The observer
changes nothing the solver computes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
import yaml

import openflowsheet.orchestrator.region as region_module
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.orchestrator.region import RegionResult, solve_region, syn001_lifted_splits
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy, Trace

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES = REPO_ROOT / "benchmarks" / "syn001" / "cases"
POLICY = SolvePolicy(policy_id="T03", residual_tolerances={}, scales={})
RELATIVE = 1e-9
TEMPERATURE, DUTY, FLOW = 1e-5, 1e-2, 3.1e-7


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t03" / "reference_values.yaml").read_text()
    )
    return loaded


@dataclass(frozen=True)
class Run:
    result: RegionResult
    trace: Trace
    #: per attempt, the `S3.T` of every residual call after the opening, in call order
    trials: dict[int, list[float]]


def run_case(case_id: str, monkeypatch: pytest.MonkeyPatch) -> Run:
    """The A02 revision's region solve from its pre-solve (T02 §7.5), observed."""
    from test_t02_a02 import revision, structure, the_region

    item = structure(revision(case_id))
    flowsheet = item.binding.flowsheet
    pre, _ = solve_tear(flowsheet)
    assert pre.final_state is not None

    calls: dict[int, list[float]] = {}
    original = region_module._region_problem

    def observed(compiled, context, spec, scaling, base, free, rows, screen=None, opening=None):  # type: ignore[no-untyped-def]
        problem = original(compiled, context, spec, scaling, base, free, rows, screen, opening)
        attempt = len(calls)
        calls[attempt] = []
        where = list(free).index("S3.T")
        inner = problem.residual

        def residual(x):  # type: ignore[no-untyped-def]
            calls[attempt].append(float(x[where]))
            return inner(x)

        return replace(problem, residual=residual)

    monkeypatch.setattr(region_module, "_region_problem", observed)
    trace = Trace()
    result = solve_region(
        compiled=compile_problem(item.binding.spec),
        spec=item.binding.spec,
        region=the_region(item),
        state=dict(pre.final_state),
        splits=syn001_lifted_splits(flowsheet.components),
        provider=flowsheet.provider,
        policy=POLICY,
        trace=trace,
        initializer_source="user_guess",
    )
    # The first call of an attempt is its opening state; the rest are its trials, in order.
    return Run(result, trace, {k: v[1:] for k, v in calls.items()})


def close(value: float, expected: Any, relative: float = RELATIVE) -> bool:
    target = float(expected)
    return abs(value - target) <= relative * max(1.0, abs(target))


def assert_attempt(run: Run, index: int, registered: Mapping[str, Any]) -> None:
    """One attempt against its registered record: every trial, the opening, the closure."""
    trace = run.trace
    item = run.result.branch_provenance[index]
    signature = ",".join(f"{unit}:{regime}" for unit, regime in item["signature"])
    assert signature == registered["signature"]
    assert item["opening_source"] == registered["opening_source"]
    assert item["opening_trial"] == registered["opening_trial"]
    assert item["core_outcome"] == registered["core_outcome"]
    assert item["iterations"] == registered["core_iterations"]
    assert item["decision"] == registered["decision"]
    if registered["decision"] == "restart":
        assert item["cause"] == registered["cause"]

    (opened,) = [e for e in trace.events if e.kind == "attempt_opened" and e.attempt == index]
    if registered["opening_alpha"] is None:
        assert opened.alpha is None
    else:
        assert opened.alpha is not None and close(opened.alpha, registered["opening_alpha"])
    attempt = run.result.attempts[index]
    assert close(attempt.end_state["S3.T"], registered["end_S3_T_K"])

    events = [
        e
        for e in trace.events
        if e.attempt == index and e.kind in ("trial", "step_accepted") and e.iteration >= 0
    ]
    temperatures = run.trials[index]
    trials = registered.get("trials")
    if trials is not None:
        assert len(events) == len(trials), "every trial, and only those"
        assert len(temperatures) == len(events), "each observed residual call is one trial"
        for event, temperature, expected in zip(events, temperatures, trials, strict=True):
            verdict = "accepted" if event.kind == "step_accepted" else event.rejection_reason
            assert (event.iteration, verdict) == (expected["iteration"], expected["verdict"])
            assert close(float(event.alpha), expected["alpha"])
            assert close(temperature, expected["S3_T_K"]), (event.iteration, temperature)
            if expected["verdict"] == "phase_update_required":
                reported = dict(event.signature)["U-HEAT"]
                assert reported == expected["reported_heater_regime"]
    prej = sum(
        1 for e in events if e.kind == "trial" and e.rejection_reason == "phase_update_required"
    )
    invalid = sum(1 for e in events if e.kind == "trial" and e.rejection_reason == "invalid_trial")
    assert prej == registered["phase_rejections"]
    assert invalid == registered["invalid_trials"]
    for landing in registered.get("landings") or ():
        # T03 §4.6: a landing is an overshoot — the step is accepted at `α_max` and the attempt
        # carries on past it (it closes later, or converges), never at the landing iteration.
        (landed,) = [
            e for e in events if e.kind == "step_accepted" and e.iteration == landing["iteration"]
        ]
        assert close(float(landed.alpha), landing["alpha_max"])
        assert item["iterations"] >= landing["iteration"] + 1


def assert_final(run: Run, final: Mapping[str, Any]) -> None:
    state = run.result.state
    assert abs(state["S3.T"] - float(final["S3_T_K"])) <= TEMPERATURE
    assert abs(state["U-HEAT.Q"] - float(final["U_HEAT_Q_W"])) <= DUTY
    assert abs(state["U-FLASH.Q"] - float(final["U_FLASH_Q_W"])) <= DUTY
    for index, component in enumerate(("A", "B", "C")):
        assert abs(state[f"S3.vap.{component}"] - float(final["S3_vapor_mol_per_s"][index])) <= FLOW
        assert (
            abs(state[f"S3.liq.{component}"] - float(final["S3_liquid_mol_per_s"][index])) <= FLOW
        )


@pytest.mark.parametrize(
    "case_id",
    ["SYN-001-A02-355-liquid-guess", "SYN-001-A02-360-liquid-guess"],
)
def test_a06_a09_the_liquid_guess_cases_converge_through_an_adjacent_restart(
    case_id: str, ref: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """PHS-01 and PHS-02 (T02 A30/A31 re-registered, T03 §10.1): LIQUID walls against the
    two-phase region, restarts TWO_PHASE at the largest-α *adjacent* candidate (the α = 1 VAPOR
    trial, or the domain-refused one, is skipped), lands a vapour component on its bound on the
    way down, does not close there, and converges to T02's sweep row."""
    registered = ref["policy_simulation"]["cases"][case_id]
    run = run_case(case_id, monkeypatch)
    assert run.result.outcome == registered["outcome"] == "CONVERGED"
    assert len(run.result.attempts) == len(registered["attempts"]) == 2
    for index, attempt in enumerate(registered["attempts"]):
        assert_attempt(run, index, attempt)
    assert_final(run, registered["final"])
    (opened,) = [e for e in run.trace.events if e.kind == "attempt_opened" and e.attempt == 1]
    assert opened.message == "phase_update(phase_wall(patience, U-HEAT:LIQUID->TWO_PHASE))"


@pytest.mark.parametrize(
    "case_id",
    ["SYN-001-A02-360-vapor-guess", "SYN-001-A02-340-two-phase-guess"],
)
def test_a10_a11_the_vapour_appearance_and_the_genuine_disappearance(
    case_id: str, ref: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """PHS-03: the liquid phase appears coming down from 400 K (far LIQUID candidates skipped).
    PHS-04: a TWO_PHASE attempt lands `S3.vap.C`, is `BOUND_BLOCKED` on it at the next iteration
    — the phase really left — restarts LIQUID from the pinned iterate, whose screen value is above
    1 (the opening is not screened), and converges in one affine step to 340 K."""
    registered = ref["policy_simulation"]["cases"][case_id]
    run = run_case(case_id, monkeypatch)
    assert run.result.outcome == registered["outcome"] == "CONVERGED"
    assert len(run.result.attempts) == len(registered["attempts"])
    for index, attempt in enumerate(registered["attempts"]):
        assert_attempt(run, index, attempt)
    assert_final(run, registered["final"])
    if case_id == "SYN-001-A02-340-two-phase-guess":
        first, second = run.result.attempts
        assert first.solver_outcome == "BOUND_BLOCKED"
        assert second.end_state["S3.V"] == 0.0
        (opened,) = [e for e in run.trace.events if e.kind == "attempt_opened" and e.attempt == 1]
        assert opened.message == "phase_update(phase_disappeared(U-HEAT, vapor, S3.vap.C))"
        assert run.result.branch_provenance[1]["opening_source"] == "pinned_iterate"


def test_a12_the_dew_guess_cycles_honestly_and_is_handed_to_t04(
    ref: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """PHS-05, an expected failure: the two-step overshoot of `S3.vap.C` reads as a disappearance
    fourteen kelvin inside the two-phase band; the LIQUID attempt's 21 trials are all
    phase-rejected, its line search fails at iteration 0, and the adjacent restart is TWO_PHASE
    again."""
    case_id = "SYN-001-A02-355-dew-guess"
    registered = ref["policy_simulation"]["cases"][case_id]
    run = run_case(case_id, monkeypatch)
    assert run.result.outcome == registered["outcome"] == "ACTIVE_SET_CYCLING"
    for index, attempt in enumerate(registered["attempts"]):
        assert_attempt(run, index, attempt)
    assert run.result.message == (
        "active_set_cycling(U-HEAT:TWO_PHASE,U-FLASH:TWO_PHASE; "
        "phase_wall(stall, U-HEAT:LIQUID->TWO_PHASE))"
    )
    assert run.result.checkpoint is not None and run.result.checkpoint.label == "partial"
    second = run.result.attempts[1]
    assert second.solver_outcome == "LINE_SEARCH_FAILED"


def test_a24_a_freed_variable_with_no_guess_fails_initialization_and_is_never_kept_fixed() -> None:
    """T03 §9 (T02 review N9): the column is freed — the plan's region lists `S3.T` as adjusted —
    and with no user guess and no later source for a temperature the solve ends
    `INITIALIZATION_FAILED` naming it: no attempt, no Jacobian, no `CONVERGED` anywhere."""
    from test_t02_executor import revision_run

    run = revision_run("SYN-001-A02-360-no-guess")
    (region,) = [step for step in run.plan.steps if step.kind == "solve_eo"]
    assert region.region is not None and "S3.T" in region.region.adjusted_variables
    result = run.result
    assert result.outcome == "INITIALIZATION_FAILED"
    assert result.message == "missing_initial_guess(S3.T)"
    events = result.trace.events
    (rejected,) = [event for event in events if event.kind == "initializer_rejected"]
    assert rejected.message == "missing_initial_guess(S3.T)"
    assert not [event for event in events if event.kind == "attempt_opened"]
    assert result.counters.jacobian_calls == 0
    assert all(event.outcome != "CONVERGED" for event in events)


def test_m2_the_no_guess_refusal_holds_whoever_runs_the_plan() -> None:
    """Review M2 (P10): the plan itself carries the missing guess — `execute_plan` has no opt-in
    argument left to forget — so the no-guess revision fails `INITIALIZATION_FAILED` from any
    caller, and never converges from the flowsheet's declared default."""
    import inspect

    from test_t02_executor import revision_run

    from openflowsheet.orchestrator.executor import execute_plan

    assert "missing_guesses" not in inspect.signature(execute_plan).parameters
    run = revision_run("SYN-001-A02-360-no-guess")
    (region,) = [step for step in run.plan.steps if step.kind == "solve_eo"]
    assert region.region is not None and region.region.missing_guesses == ("S3.T",)
    assert run.result.outcome == "INITIALIZATION_FAILED"


def test_m2_a_value_less_free_specification_binds_on_every_freeable_coordinate() -> None:
    """Review M2 (P4): `role: free` without a value on the flash temperature binds with the
    missing start recorded — never a `ValueError`."""
    from openflowsheet.application.binding import Binding, bind_revision_or_reason

    document = yaml.safe_load((CASES / "SYN-001-A02-360.yaml").read_text())
    for entry in document["specifications"]:
        if entry["id"] == "SPEC-flash-T":
            entry["role"] = "free"
            entry.pop("value")
            entry["bounds"] = {"lower": 280.0, "upper": 440.0}
    bound = bind_revision_or_reason(document)
    assert isinstance(bound, Binding)
    # `outlet.T` of the flash instance is both outlets' temperature (one parameter, two columns).
    assert bound.missing_guesses == ("S4.T", "S5.T")
