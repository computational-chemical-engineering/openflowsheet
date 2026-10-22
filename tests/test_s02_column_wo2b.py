"""S02 WO-2b — the bubble-point easy endpoint and ADR 0044's trigger: spec §18.6.

Expectations are values of `docs/derivations/scripts/s02_reference.json` (the design lane's
50-digit generator: `cases.*.bubble_point`, `.bubble_point_continued`,
`variants.*.*.bubble_point`, `variants.M2.duty+duty.second_root`), codes and rules of
`docs/derivations/S02-spec.md` §18 and ADR 0044, or arithmetic done here. Each test names the
assertion of §18.6 it closes. WO-2's strict xfails on §7.3's Newton pre-solve (A05 ×4, A06 ×4,
A07 ×5) are replaced by A05, A06 and A07 here (`docs/S02_DECISIONS.md`, WO-2b).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, get_args

import pytest
from test_s02_column_wo1 import CASES, PROVIDER, REFERENCE, SPECS, UNIT, _variant
from test_s02_column_wo2 import (
    FLOW_REL,
    Q_ABS,
    assert_a06,
    deviation,
    deviation_from,
    stages_state,
)

import openflowsheet.models.syn001.cascade_solve as cascade_solve_module
import openflowsheet.models.syn001.column_solve as solve_module
import openflowsheet.orchestrator.region as region_module
from openflowsheet.compile.reference import row_values
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    liquid_total_id,
    stage_temperature_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.column import ColumnSpec, distillate_total_id, profile_initial
from openflowsheet.models.syn001.column_solve import (
    DECLARATION_CONTEXT,
    MAX_SWEEPS,
    PRESOLVE_ID,
    SWEEP_TOLERANCE,
    BubblePointEndpoint,
    ColumnSolution,
    bubble_point_endpoint,
    compile_column,
    continuation,
    slots,
    solve_column,
)
from openflowsheet.models.syn001.saturation_band import BandTemperature
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.recovery import (
    EO_CORE_FAILURES,
    EO_RECOVERY_TRIGGERS,
    eo_recovery_due,
    solver_outcomes,
)
from openflowsheet.orchestrator.region import KIND_TOLERANCE, SolveOutcome
from openflowsheet.orchestrator.roots import same_root

#: §18.6 A05: the endpoints the generator registers — M1–M4 and the six regular variant sets
#: (WO-G's DECISION: M1 ×4, M2 `(duty, duty)` and `(D, BR)`; the spec's "five" is flagged).
ENDPOINTS: tuple[tuple[str, str | None], ...] = (
    *((case, None) for case in CASES),
    *(
        (case, variant)
        for case in ("M1", "M2")
        for variant, record in REFERENCE["variants"][case].items()
        if "bubble_point" in record
    ),
)
#: §18.6 A07: the variant sets whose returned root is their case's `ref.target`; and `R2`'s.
R2 = ("M2", "duty+duty")
MATCHED = tuple(pair for pair in ENDPOINTS if pair[1] is not None and pair != R2)


def _spec(case: str, variant: str | None) -> ColumnSpec:
    return SPECS[case] if variant is None else _variant(case, variant)


def _record(case: str, variant: str | None) -> dict[str, Any]:
    record: dict[str, Any] = (
        REFERENCE["cases"][case] if variant is None else REFERENCE["variants"][case][variant]
    )
    return record


_ENDPOINT: dict[tuple[str, str | None], BubblePointEndpoint | CascadeFailure] = {}
_SOLVED: dict[tuple[str, str | None], ColumnSolution] = {}


def endpoint(case: str, variant: str | None = None) -> BubblePointEndpoint:
    """§18.2 on `(case, variant)`, once per session."""
    if (case, variant) not in _ENDPOINT:
        spec = _spec(case, variant)
        initial = profile_initial(spec, PROVIDER, DECLARATION_CONTEXT)
        assert not isinstance(initial, CascadeFailure)
        _ENDPOINT[(case, variant)] = bubble_point_endpoint(spec, PROVIDER, initial)
    found = _ENDPOINT[(case, variant)]
    assert isinstance(found, BubblePointEndpoint), found
    return found


def solved(case: str, variant: str | None = None) -> ColumnSolution:
    """`solve_column` on `(case, variant)`, once per session."""
    if (case, variant) not in _SOLVED:
        answer = solve_column(_spec(case, variant), PROVIDER)
        assert isinstance(answer, ColumnSolution), answer
        _SOLVED[(case, variant)] = answer
    return _SOLVED[(case, variant)]


def _regimes(spec: ColumnSpec, answer: ColumnSolution) -> dict[int, Any]:
    return dict(zip(spec.equilibrium_stages(), answer.signature, strict=True))


def _same(spec: ColumnSpec, a: ColumnSolution, b: ColumnSolution) -> str:
    target = compile_column(spec, PROVIDER).spec
    assert a.result.root_fingerprint is not None and b.result.root_fingerprint is not None
    return same_root(
        a.result.root_fingerprint,
        a.state,
        b.result.root_fingerprint,
        b.state,
        Scaling.from_spec(target).column,
        target.variable_ids,
    )


def _p0_tolerance(record: dict[str, str]) -> float:
    """§18.6 A05's `p⁰` tolerance: Q abs 1e-2 W, rates rel 1e-6."""
    return Q_ABS if record["kind"] == "Q" else FLOW_REL * abs(float(record["p0"]))


# -- A05: the easy endpoint ----------------------------------------------------------------------


@pytest.mark.parametrize(("case", "variant"), ENDPOINTS)
def test_a05_the_bubble_point_endpoint(case: str, variant: str | None) -> None:
    """A05: §18.2's `x⁰` equals the generator's (`bubble_point`: flows, `T`, `Q`, `φ`) within the
    state tolerance; `ρ` and `φ` as recorded (rel 1e-6); every target row except the continued
    slot rows within its kind tolerance at `x⁰`; every stage `L, V > 0`; the sweeps stopped
    within the cap at `max |ΔT| ≤ 1e-9 K` (the count is recorded, not asserted exactly)."""
    spec = _spec(case, variant)
    record = _record(case, variant)["bubble_point"]
    found = endpoint(case, variant)
    worst = deviation_from(spec, stages_state(spec, record["stages"]), found.state)
    assert max(worst.values()) <= 1.0, worst
    assert sorted(found.rho) == sorted(int(j) for j in record["rho"])
    for stage, rho in record["rho"].items():
        assert abs(found.rho[int(stage)] - float(rho)) <= FLOW_REL * abs(float(rho)), stage
    if spec.total_condenser:
        assert found.phi is not None
        assert abs(found.phi - float(record["phi"])) <= FLOW_REL * abs(float(record["phi"]))
    else:
        assert found.phi is None and "phi" not in record
    assert 1 <= found.sweeps <= MAX_SWEEPS and found.last_delta <= SWEEP_TOLERANCE
    target = compile_column(spec, PROVIDER).spec
    profile = [float(t) for t in REFERENCE["cases"][case]["initializer"]["profile"]]
    continued_rows = {slot.target_row for slot in slots(spec, profile) if slot.parameter}
    values = row_values(target, found.state)
    assert continued_rows <= set(values)
    over = {
        row: abs(value) / KIND_TOLERANCE[target.row_kinds[row]]
        for row, value in values.items()
        if row not in continued_rows
    }
    assert max(over.values()) <= 1.0, max(over.items(), key=lambda item: item[1])
    for stage in spec.equilibrium_stages():
        assert found.state[liquid_total_id(UNIT, stage)] > 0.0
        assert found.state[vapor_total_id(UNIT, stage)] > 0.0


@pytest.mark.parametrize("case", CASES)
def test_a05_the_continued_slots_and_p0(case: str) -> None:
    """A05: the continued slots are `ref.cases.*.bubble_point_continued`'s stages and kinds, in
    stage order, and `p⁰` (the slot's column at `x⁰`, as `solve_column` records it) is its
    `p0`."""
    spec = SPECS[case]
    record = REFERENCE["cases"][case]["bubble_point_continued"]
    answer = solved(case)
    replaced = {s.stage: s for s in slots(spec, answer.initial.profile) if s.parameter}
    assert sorted(replaced) == sorted(int(j) for j in record)
    assert tuple(answer.continued) == continuation(spec, answer.initial.profile).parameter_ids
    for stage, expected in record.items():
        slot = replaced[int(stage)]
        assert slot.continued == expected["kind"]
        p0 = answer.continued[slot.parameter]
        assert p0 == endpoint(case).state[slot.variable]
        assert abs(p0 - float(expected["p0"])) <= _p0_tolerance(expected), stage


# -- A06, A07, A21: through solve_column ---------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_a06_the_target_root_through_solve_column(case: str) -> None:
    """A06 (replaces WO-2's strict xfails, Q-S02-WO2-1): §7 from `x_K` through §18.2's endpoint
    returns `ref.cases.*.target` — outcome, signature 2P×n, products, `spec_values`, root; the
    target's initializer source is `s02-bubble-point-v1`."""
    spec = SPECS[case]
    answer = solved(case)
    assert answer.outcome == "CONVERGED"
    assert answer.signature == ("TWO_PHASE",) * len(spec.equilibrium_stages())
    assert_a06(case, answer.state, _regimes(spec, answer))
    assert answer.result.branch_provenance[0]["initializer_source"] == PRESOLVE_ID


@pytest.mark.parametrize(("case", "variant"), MATCHED)
def test_a07_each_matched_set_returns_the_cases_root(case: str, variant: str) -> None:
    """A07 (replaces WO-2's strict xfails): each matched set through `solve_column` returns
    `ref.cases.<case>.target` within the state tolerance (no cross-set `same_root`, §18.4)."""
    answer = solved(case, variant)
    assert answer.outcome == "CONVERGED" and set(answer.signature) == {"TWO_PHASE"}
    worst = deviation(case, answer.state)
    assert max(worst.values()) <= 1.0, worst


def test_a07_m2_duty_duty_returns_the_second_root() -> None:
    """A07: V-M2 `(duty, duty)` returns `R2` (`ref.variants.M2.duty+duty.second_root`)."""
    spec = _spec(*R2)
    answer = solved(*R2)
    assert answer.outcome == "CONVERGED" and set(answer.signature) == {"TWO_PHASE"}
    expected = stages_state(spec, _record(*R2)["second_root"]["stages"])
    worst = deviation_from(spec, expected, answer.state)
    assert max(worst.values()) <= 1.0, worst


def test_a21_multiplicity() -> None:
    """A21: the returned `R2` differs from M2's root by more than 5 K in `T_c` and 0.1 mol/s in
    `D`; both roots are regular by the generator's `σ_min` claims (> 1e-4)."""
    answer = solved(*R2)
    m2 = stages_state(SPECS["M2"], REFERENCE["cases"]["M2"]["target"]["stages"])
    t_c, d = stage_temperature_id(UNIT, 1), distillate_total_id(UNIT)
    assert abs(answer.state[t_c] - m2[t_c]) > 5.0
    assert abs(answer.state[d] - m2[d]) > 0.1
    assert float(REFERENCE["cases"]["M2"]["sigma_min"]) > 1e-4
    assert float(_record(*R2)["second_root"]["sigma_min"]) > 1e-4


# -- A13: edge 3 on solve_column's own path ------------------------------------------------------

#: §18.5: the failed solve edge 3 recovers from on `solve_column`'s path.
RECOVERED_FROM = {"M1": "ACTIVE_SET_CYCLING", "M2": "LINEAR_SOLVE_FAILED"}


def _dyadic(value: Fraction) -> bool:
    return 0 <= value <= 1 and value.denominator & (value.denominator - 1) == 0


@pytest.mark.parametrize("case", ["M1", "M2"])
def test_a13_edge_3_on_solve_columns_own_path(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    """A13 (no forcing): edge 3 runs after §18.5's outcome; every re-binding names exactly the
    continued parameters (the ratio rows' `RR*`, `BR*` never move); `p⁰ =
    ref.cases.*.bubble_point_continued`; dyadic λ; the λ = 1 instance is the target's; a second
    run's root is `SAME` and bit-identical."""
    rebound: list[dict[str, float]] = []
    real = region_module.rebind

    def rebind(spec: Any, values: dict[str, float]) -> Any:
        rebound.append(dict(values))
        return real(spec, values)

    monkeypatch.setattr(region_module, "rebind", rebind)
    spec = SPECS[case]
    answer = solve_column(spec, PROVIDER)
    assert isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"
    failed, result = answer.recovered_from, answer.result
    assert failed is not None and failed.outcome == RECOVERED_FROM[case]
    expected = continuation(spec, answer.initial.profile).parameter_ids
    assert rebound and all(tuple(level) == expected for level in rebound)
    by_id = {s.parameter: s for s in slots(spec, answer.initial.profile) if s.parameter}
    for name, value in rebound[0].items():
        record = REFERENCE["cases"][case]["bubble_point_continued"][str(by_id[name].stage)]
        assert abs(value - float(record["p0"])) <= _p0_tolerance(record), name
        assert value == answer.continued[name]
    homotopy = result.homotopy
    assert homotopy is not None and homotopy.lambda_reached == 1
    assert all(_dyadic(trial.lambda_value) for trial in homotopy.trials)
    assert result.branch_provenance[len(failed.branch_provenance)]["core"] == "homotopy"
    compiled = compile_column(spec, PROVIDER).compiled.metadata
    at_one = result.contexts[0].evaluation_context
    assert (at_one.model_version, at_one.constants_sha256) == (
        compiled.model_version,
        compiled.constants_sha256,
    )
    second = solved(case)
    assert _same(spec, answer, second) == "SAME"
    assert answer.final_sha256 == second.final_sha256


# -- A14: M1 from perturbed endpoints ------------------------------------------------------------


@pytest.mark.parametrize("shift", [-5.0, 5.0])
def test_a14_a_shifted_sweep_start_reaches_the_same_endpoint(shift: float) -> None:
    """A14: the sweeps from `T⁰ ± 5 K` give A05's `x⁰` within 1e-8 K; the target converges within
    the state tolerance of `ref.target`, `same_root = SAME` with A06's run."""
    spec, base = SPECS["M1"], solved("M1")
    answer = solve_column(spec, PROVIDER, profile_shift=shift)
    assert isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"
    for stage in spec.equilibrium_stages():
        name = stage_temperature_id(UNIT, stage)
        assert abs(answer.endpoint.state[name] - base.endpoint.state[name]) <= 1e-8, stage
    worst = deviation("M1", answer.state)
    assert max(worst.values()) <= 1.0, worst
    assert _same(spec, answer, base) == "SAME"


#: Measured (WO-2b, `docs/S02_DECISIONS.md` Q-S02-WO2b-1): x⁰ from the shifted start is not
#: bit-identical (91 columns differ; max |ΔT| 2.3e-10 K, −5 K; 1.4e-10 K, +5 K; sweeps 24 / 25
#: against 25), so the answer differs in the last bits (max 1.1e-11 / 3.6e-12; `SAME`).
SHIFT_MEASURED = {
    -5.0: "x⁰ max |ΔT| 2.28e-10 K, answer max |Δx| 1.09e-11",
    5.0: "x⁰ max |ΔT| 1.36e-10 K, answer max |Δx| 3.64e-12",
}


@pytest.mark.parametrize(
    "shift",
    [
        pytest.param(
            shift,
            marks=pytest.mark.xfail(
                strict=True, reason=f"Q-S02-WO2b-1, measured: {SHIFT_MEASURED[shift]}"
            ),
        )
        for shift in (-5.0, 5.0)
    ],
)
def test_a14_a_shifted_sweep_start_gives_the_same_final_state_sha256(shift: float) -> None:
    """A14's last clause as written: the same final `state_sha256` as A06's run."""
    answer = solve_column(SPECS["M1"], PROVIDER, profile_shift=shift)
    assert isinstance(answer, ColumnSolution)
    assert answer.final_sha256 == solved("M1").final_sha256


@pytest.mark.parametrize("scale", [0.5, 2.0])
def test_a14_scaled_stage_ratios_reach_the_same_root(scale: float) -> None:
    """A14: every stage ratio no ratio specification holds (M1: all but the RR condenser and
    the BR reboiler) ×0.5 and ×2: `x⁰` differs, the target is `CONVERGED` within the state
    tolerance of `ref.target`, and `same_root = SAME` with A06's run."""
    spec, base = SPECS["M1"], solved("M1")
    answer = solve_column(spec, PROVIDER, ratio_scale=scale)
    assert isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"
    held = (1, spec.stage_count)
    for stage, rho in answer.endpoint.rho.items():
        assert rho == (1.0 if stage in held else scale) * base.endpoint.rho[stage], stage
    assert answer.endpoint_sha256 != base.endpoint_sha256
    worst = deviation("M1", answer.state)
    assert max(worst.values()) <= 1.0, worst
    assert _same(spec, answer, base) == "SAME"


# -- A20: ADR 0044's trigger ---------------------------------------------------------------------


def test_a20_the_trigger_table() -> None:
    """A20 (§19 item 1, R-550): every ADR 0010 D3 trigger is due whatever the attempts;
    `LINEAR_SOLVE_FAILED` is due iff the failed solve ran two or more attempts **and** attempt 0
    ended in a core globalization failure (`EO_CORE_FAILURES`); every other outcome is never due."""
    assert EO_CORE_FAILURES == {
        "LINE_SEARCH_FAILED",
        "STAGNATION",
        "BOUND_BLOCKED",
        "PTC_STALLED",
        "BUDGET_EXHAUSTED",
    }
    budgets = {"BUDGET_EXHAUSTED": "newton_iterations"}
    outcomes = get_args(SolveOutcome)
    histories = [
        (first, *rest)
        for first in outcomes
        for rest in ((), ("LINEAR_SOLVE_FAILED",), ("STAGNATION", "LINEAR_SOLVE_FAILED"))
    ]
    for outcome in outcomes:
        for history in histories:
            due = eo_recovery_due(outcome, budgets.get(outcome), attempts=history)
            if outcome in EO_RECOVERY_TRIGGERS:
                assert due, (outcome, history)
            elif outcome == "LINEAR_SOLVE_FAILED":
                assert due == (len(history) >= 2 and history[0] in EO_CORE_FAILURES), history
            else:
                assert not due, (outcome, history)
    # §19 item 1's rows, by name.
    assert not eo_recovery_due("LINEAR_SOLVE_FAILED", None, attempts=("LINEAR_SOLVE_FAILED",))
    assert not eo_recovery_due(
        "LINEAR_SOLVE_FAILED", None, attempts=("CONVERGED", "LINEAR_SOLVE_FAILED")
    )
    assert eo_recovery_due(
        "LINEAR_SOLVE_FAILED", None, attempts=("BOUND_BLOCKED", "LINEAR_SOLVE_FAILED")
    )
    assert not eo_recovery_due("LINEAR_SOLVE_FAILED", None, attempts=())
    assert not eo_recovery_due(
        "BUDGET_EXHAUSTED", "property_calls", attempts=("BOUND_BLOCKED",) * 3
    )
    # N1: the attempts are required and keyword-only; no call site keeps the old predicate.
    with pytest.raises(TypeError):
        eo_recovery_due("LINEAR_SOLVE_FAILED", None)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        eo_recovery_due("LINEAR_SOLVE_FAILED", None, ("BOUND_BLOCKED", "LINEAR_SOLVE_FAILED"))  # type: ignore[misc]
    assert "LINEAR_SOLVE_FAILED" not in EO_RECOVERY_TRIGGERS


def test_a20_m2_recovers_after_linear_solve_failed_in_a_restart() -> None:
    """A20 on M2's path: the target ends `LINEAR_SOLVE_FAILED` in a restart-opened attempt
    ((2P×5, V), §4.2's end-stage singularity) and edge 3 recovers it to `CONVERGED`."""
    answer = solved("M2")
    failed = answer.recovered_from
    assert failed is not None and failed.outcome == "LINEAR_SOLVE_FAILED"
    assert len(failed.attempts) >= 2
    # §19 item 1 (R-550): attempt 0 ended in a core globalization failure, so the narrowed
    # predicate is what makes this recovery due.
    assert failed.attempts[0].solver_outcome == "BOUND_BLOCKED"
    assert eo_recovery_due(failed.outcome, failed.budget, attempts=solver_outcomes(failed.attempts))
    assert answer.outcome == "CONVERGED" and answer.result.homotopy is not None


# -- A22: typed construction failures ------------------------------------------------------------


def _no_region_solve(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("A22: solve_region was called")

    monkeypatch.setattr(cascade_solve_module, "solve_region", refuse)


def test_a22_a_bubble_point_outside_the_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """A22: `band_temperature` answering `below` at one stage (the third call: stage 3 of sweep
    1) ends M1 `initialization_failed(s02-bubble-point-v1, bubble_point_outside_domain)` before
    any region solve."""
    _no_region_solve(monkeypatch)
    real = solve_module.band_temperature
    calls: list[float] = []

    def below_once(provider: Any, flows: Any, pressure: float, *rest: Any, **kw: Any) -> Any:
        calls.append(pressure)
        if len(calls) == 3:
            return BandTemperature("below", evaluations=1)
        return real(provider, flows, pressure, *rest, **kw)

    monkeypatch.setattr(solve_module, "band_temperature", below_once)
    answer = solve_column(SPECS["M1"], PROVIDER)
    assert isinstance(answer, CascadeFailure)
    assert answer.outcome == "INITIALIZATION_FAILED"
    assert answer.cause == f"initialization_failed({PRESOLVE_ID}, bubble_point_outside_domain)"
    assert len(calls) == 3


def test_a22_sweeps_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A22: with `max_sweeps = 1`, M1 ends `initialization_failed(s02-bubble-point-v1,
    sweeps_exhausted)` before any region solve."""
    _no_region_solve(monkeypatch)
    answer = solve_column(SPECS["M1"], PROVIDER, max_sweeps=1)
    assert isinstance(answer, CascadeFailure)
    assert answer.outcome == "INITIALIZATION_FAILED"
    assert answer.cause == f"initialization_failed({PRESOLVE_ID}, sweeps_exhausted)"
