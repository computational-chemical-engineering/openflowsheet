"""S01 WO-3 — phases, continuation, perturbation: spec §4.2–§4.7, §7.5 and §10.

Every expectation is a value of `docs/derivations/scripts/s01_reference.json` (the design lane's
50-digit generator) or a rule of `docs/derivations/S01-spec.md`. Each test names the §10 assertion
it closes: A11, A12, A17, A18, A19.
"""

from __future__ import annotations

import typing
from collections.abc import Callable
from fractions import Fraction
from typing import Any

import pytest
from test_s01_cascade_wo1 import REFERENCE, UNIT, _spec
from test_s01_cascade_wo2 import PROVIDER, Q_ABS, deviation, solved

import openflowsheet.models.syn001.cascade_solve as solve_module
from openflowsheet.canonical import state_sha256
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    is_dormant,
    kremser_initial,
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_duty_id,
    stage_pressure_id,
    stage_temperature_id,
    validate,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade_solve import (
    DECLARATION_CONTEXT,
    PRESOLVE_ID,
    S01_DEFAULT_V1,
    CascadeSolution,
    acceptance_failures,
    compile_cascade,
    solve_cascade,
)
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.roots import same_root
from openflowsheet.orchestrator.trace import SolveOutcome, Trace

#: The single-phase regime a stage reaches, and the phase whose disappearance takes it there.
VANISHED = {"LIQUID": "vapor", "VAPOR": "liquid"}


def compare_with_a06(answer: CascadeSolution) -> str:
    """T03 §8.3's `same_root` of `answer` against A06's root (C2, solved from `x_K`), in the
    target's own column scales."""
    spec = _spec(REFERENCE["cases"]["C2"])
    reference = solved("C2")
    assert reference.result is not None and answer.result is not None
    target = compile_cascade(spec, PROVIDER)
    first, second = reference.result.root_fingerprint, answer.result.root_fingerprint
    assert first is not None and second is not None
    return same_root(
        first,
        reference.state,
        second,
        answer.state,
        Scaling.from_spec(target.spec).column,
        target.spec.variable_ids,
    )


# -- A11, A12: disappearance ---------------------------------------------------------------------


@pytest.mark.parametrize("case", ["C4", "C5"])
def test_a11_a12_the_registered_single_phase_stages_are_reached(case: str) -> None:
    """A11 (C4 → 2P, L, L) and A12 (C5 → VAPOR, 2P): from the all-TWO_PHASE pre-solve root the
    target reaches the registered signature exactly, within `max_attempts = 5`, after at least one
    restart caused by disappearance; every restart is a disappearance at a stage the registered
    signature makes single-phase, of the phase it loses; the root is `ref`'s within the state
    tolerance. (Spec §15.2, answered by measurement: C4 in 3 attempts, C5 in 2.)"""
    record = REFERENCE["cases"][case]
    answer = solved(case)
    assert answer.outcome == "CONVERGED"
    assert answer.presolve_summary.signature == ("TWO_PHASE",) * record["N"]
    assert answer.signature == tuple(record["signature"])
    assert answer.recovered_from is None and answer.result is not None
    items = answer.result.branch_provenance
    assert len(items) <= S01_DEFAULT_V1.max_attempts
    assert items[0]["initializer_source"] == PRESOLVE_ID
    assert items[-1]["decision"] == "converged"
    restarts = [item for item in items if item["decision"] == "restart"]
    assert len(restarts) >= 1
    assert len(restarts) == len(items) - 1
    single = {
        f"{UNIT}.stage.{j}": VANISHED[regime]
        for j, regime in enumerate(record["signature"], start=1)
        if regime != "TWO_PHASE"
    }
    vanished: dict[str, str] = {}
    for item in restarts:
        cause = str(item["cause"])
        assert cause.startswith("phase_disappeared("), cause
        stage, phase, _column = cause[len("phase_disappeared(") : -1].split(", ")
        vanished[stage] = phase
    assert vanished == single
    worst = deviation(answer.state, record["target"])
    assert max(worst.values()) <= 1.0, worst


# -- A17: recovery edge 3, forced from x⁰ --------------------------------------------------------


def _forced_edge_3(monkeypatch: pytest.MonkeyPatch) -> tuple[CascadeSolution, Trace, list[Any]]:
    """C2 with ADR 0010 D3's trigger forced: `eo_recovery_due` answers yes, so `solve_cascade`
    runs edge 3 from the target's item-0 opening, `x⁰`, under the unchanged policy. The λ-level
    re-bindings are spied on (T04's A10 pattern)."""
    rebound: list[dict[str, float]] = []
    real_rebind = region_module.rebind

    def rebind(spec: Any, values: dict[str, float]) -> Any:
        rebound.append(dict(values))
        return real_rebind(spec, values)

    # Fill the session memo with A06's root before the trigger is forced: `compare_with_a06`
    # would otherwise fill it under the patch when this runs first in a process (S08b review F1).
    solved("C2")
    monkeypatch.setattr(solve_module, "eo_recovery_due", lambda outcome, budget, *, attempts: True)
    monkeypatch.setattr(region_module, "rebind", rebind)
    trace = Trace()
    answer = solve_cascade(_spec(REFERENCE["cases"]["C2"]), PROVIDER, trace=trace)
    assert isinstance(answer, CascadeSolution)
    return answer, trace, rebound


def _dyadic(value: Fraction) -> bool:
    denominator = value.denominator
    return 0 <= value <= 1 and denominator & (denominator - 1) == 0


def test_a17_forced_edge_3_from_the_presolve_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """A17: edge 3 forced on C2 opens at `x⁰`; `p⁰ = Q⁰` (`ref`'s pre-solve Q within 1e-2 W, and
    the λ = 0 re-binding is exactly `Q(x⁰)`); every λ is dyadic; the λ = 1 instance is the
    target's `(model_version, constants_sha256)`, every other level is another instance of the
    same model; the final root is `SAME` as A06's."""
    answer, trace, rebound = _forced_edge_3(monkeypatch)
    spec = _spec(REFERENCE["cases"]["C2"])
    stages = range(1, spec.stage_count + 1)
    assert answer.outcome == "CONVERGED"
    assert answer.signature == ("TWO_PHASE",) * 3
    failed, recovery = answer.recovered_from, answer.result
    assert failed is not None and recovery is not None and failed.opening is not None
    # The opening is x⁰: the pre-solve root, as the target's item 0 opened from it.
    opening, regimes = failed.opening
    assert set(regimes.values()) == {"TWO_PHASE"}
    duties = {
        stage_duty_id(UNIT, j): float(answer.presolve.state[stage_duty_id(UNIT, j)]) for j in stages
    }
    assert {name: opening[name] for name in duties} == duties
    for j, presolved in zip(stages, REFERENCE["cases"]["C2"]["presolve"], strict=True):
        assert abs(duties[stage_duty_id(UNIT, j)] - float(presolved["Q"])) <= Q_ABS
    # p(0) = Q⁰ exactly, by id; the λ < 1 levels are the only re-bindings.
    assert rebound[0] == {f"{name}*": value for name, value in duties.items()}
    record = recovery.homotopy
    assert record is not None and record.lambda_reached == 1 and record.stalled_at is None
    assert record.trials[0].lambda_value == 0
    assert all(_dyadic(trial.lambda_value) for trial in record.trials)
    assert all(_dyadic(trial.delta_lambda) for trial in record.trials[1:])
    assert record.lambda_levels[-1] == 1
    assert len(rebound) == len({t.lambda_value for t in record.trials if t.lambda_value != 1})
    # Provenance: the target's item 0, then edge 3's homotopy item continuing it densely.
    items = recovery.branch_provenance
    assert items[0]["initializer_source"] == PRESOLVE_ID
    recovered = items[len(failed.branch_provenance)]
    assert recovered["core"] == "homotopy"
    assert recovered["opening_source"] == "eo_recovery_start"
    assert recovered["initializer_source"] == PRESOLVE_ID
    assert recovered["continuation"]["parameter_ids"] == [f"{name}*" for name in duties]
    # The λ = 1 instance is the target; λ < 1 levels share the model, not the constants.
    target = failed.contexts[0].evaluation_context
    at_one = recovery.contexts[0].evaluation_context
    assert (at_one.model_version, at_one.constants_sha256) == (
        target.model_version,
        target.constants_sha256,
    )
    compiled = compile_cascade(spec, PROVIDER).compiled.metadata
    assert (target.model_version, target.constants_sha256) == (
        compiled.model_version,
        compiled.constants_sha256,
    )
    steps = trace.of_kind("homotopy_step")
    assert {event.lambda_value for event in steps} >= {"0", "1"}
    for event in steps:
        at_target = event.lambda_value == "1"
        assert (event.level_constants_sha256 == target.constants_sha256) is at_target
    fingerprint = recovery.root_fingerprint
    assert fingerprint is not None
    assert (fingerprint["model_version"], fingerprint["constants_sha256"]) == (
        target.model_version,
        target.constants_sha256,
    )
    assert compare_with_a06(answer) == "SAME"


# -- A18: four perturbed openings ----------------------------------------------------------------


def _perturbed(kind: str, change: Callable[[float], float]) -> Callable[[Any], dict[str, float]]:
    """`x_K` with every *stage* column of `kind` changed; inlet columns are pinned by their
    specification rows and stay as given."""

    def opening(spec: Any) -> dict[str, float]:
        initial = kremser_initial(spec, PROVIDER, DECLARATION_CONTEXT)
        kinds = compile_cascade(spec, PROVIDER).spec.variable_kinds
        assert not isinstance(initial, CascadeFailure)
        return {
            name: change(value) if kinds[name] == kind and ".stage." in name else value
            for name, value in initial.state.items()
        }

    return opening


OPENINGS: dict[str, Callable[[Any], dict[str, float]]] = {
    "Tbar+10K": _perturbed("temperature", lambda t: t + 10.0),
    "Tbar-10K": _perturbed("temperature", lambda t: t - 10.0),
    "flows*0.5": _perturbed("molar_flow", lambda n: n * 0.5),
    "flows*2": _perturbed("molar_flow", lambda n: n * 2.0),
}


@pytest.mark.parametrize("label", list(OPENINGS))
def test_a18_c2_from_a_perturbed_opening_is_the_a06_root(label: str) -> None:
    """A18: C2 from `x_K` with `T̄ ± 10 K` or the initializer's flows ×0.5, ×2 converges, 2P ×3,
    to a root `SAME` as A06's; the perturbed opening is the one the pre-solve opened from."""
    spec = _spec(REFERENCE["cases"]["C2"])
    opening = OPENINGS[label](spec)
    answer = solve_cascade(spec, PROVIDER, opening=opening)
    assert isinstance(answer, CascadeSolution)
    assert answer.outcome == "CONVERGED"
    assert answer.signature == ("TWO_PHASE",) * 3
    unperturbed = solved("C2").presolve.branch_provenance[0]["opening_state_sha256"]
    assert answer.presolve.branch_provenance[0]["opening_state_sha256"] != unperturbed
    # Review N2: the record is the opening's hash, not `x_K`'s.
    order = compile_cascade(spec, PROVIDER).spec.variable_ids
    assert answer.opening_sha256 == state_sha256(opening, order) != answer.initial_sha256
    assert solved("C2").opening_sha256 == solved("C2").initial_sha256
    assert compare_with_a06(answer) == "SAME"


@pytest.mark.parametrize("shift", [10.0, -10.0], ids=["Tbar+10K", "Tbar-10K"])
def test_a18_c2_from_a_shifted_presolve_level_is_the_a06_root(shift: float) -> None:
    """A18 (spec §17.8, R-517): `T̄ ± 10 K` is the pre-solve's isothermal level, so `x⁰` is the
    isothermal root at `T̄ ± 10 K`: it differs from A06's pre-solve root by more than 1 K in
    every stage `T`, and the target from it converges, 2P ×3, to a root `SAME` as A06's."""
    spec = _spec(REFERENCE["cases"]["C2"])
    initial = kremser_initial(spec, PROVIDER, DECLARATION_CONTEXT)
    assert not isinstance(initial, CascadeFailure)
    answer = solve_cascade(spec, PROVIDER, tbar=initial.tbar + shift)
    assert isinstance(answer, CascadeSolution)
    assert answer.presolve_summary.outcome == "CONVERGED"
    reference = solved("C2").presolve.state
    for j in range(1, spec.stage_count + 1):
        column = stage_temperature_id(UNIT, j)
        assert abs(answer.presolve.state[column] - reference[column]) > 1.0
    assert answer.presolve_sha256 != solved("C2").presolve_sha256
    assert answer.outcome == "CONVERGED"
    assert answer.signature == ("TWO_PHASE",) * 3
    assert compare_with_a06(answer) == "SAME"


# -- A19: the partial-dormancy probe -------------------------------------------------------------

#: Spec §4.5's typed outcomes: every `SolveOutcome` (`INITIALIZATION_FAILED` and
#: `SPECIFICATION_CONFLICT` among them).
TYPED_OUTCOMES = frozenset(typing.get_args(SolveOutcome))


def _registered_partial_dormancy_root(spec: Any) -> dict[str, float]:
    """`ref.partial_dormancy.target` as a full state: its stage columns, the inlets' pinned ones."""
    initial = kremser_initial(spec, PROVIDER, DECLARATION_CONTEXT)
    assert not isinstance(initial, CascadeFailure)
    state = dict(initial.state)
    for record in REFERENCE["partial_dormancy"]["target"]:
        j = record["stage"]
        for i, c in enumerate("ABC"):
            state[liquid_id(UNIT, j, c)] = float(record["l"][i])
            state[vapor_id(UNIT, j, c)] = float(record["v"][i])
            state[mixed_id(UNIT, j, c)] = float(record["m"][i])
        state[liquid_total_id(UNIT, j)] = float(record["L"])
        state[vapor_total_id(UNIT, j)] = float(record["V"])
        state[stage_temperature_id(UNIT, j)] = float(record["T"])
        state[stage_pressure_id(UNIT, j)] = float(record["P"])
        state[stage_duty_id(UNIT, j)] = float(record["Q"])
    return state


def test_a19_the_registered_root_passes_section_8() -> None:
    """A19's premise (generator claim `accepted_by_section_8`), checked by this implementation's
    §8: the analytic root under (ZERO_FLOW, ZERO_FLOW, LIQUID) is accepted; under all-TWO_PHASE
    it is not (its pinned zero flows would be declared phases with `V_j = L_j = 0`)."""
    record = REFERENCE["partial_dormancy"]
    assert record["accepted_by_section_8"] is True
    spec = _spec(record)
    declared = compile_cascade(spec, PROVIDER).spec
    state = _registered_partial_dormancy_root(spec)
    signature = tuple(record["signature"])
    assert acceptance_failures(spec, PROVIDER, declared, state, signature) == ()
    two_phase = ("TWO_PHASE",) * 3
    assert acceptance_failures(spec, PROVIDER, declared, state, two_phase) != ()  # type: ignore[arg-type]


def test_a19_the_partial_dormancy_probe_is_never_a_false_success() -> None:
    """A19: the probe passes §5 and is not §4.6's all-dormant case; the solve returns a typed
    §4.5 outcome other than a §5 refusal, or a `CONVERGED` root that passed §8 (a failing one
    raises `AcceptanceDefectError`) and, under (ZERO_FLOW, ZERO_FLOW, LIQUID), is `ref`'s.

    Measured (WO-3): `INITIALIZATION_FAILED`, `initialization_failed(s01-isothermal-presolve-v1,
    not_two_phase)` — the pre-solve converges at `T̄` with stages 1 and 2 VAPOR. Partial dormancy
    stays unclaimed (spec §14); the exact outcome is held as a regression value."""
    record = REFERENCE["partial_dormancy"]
    spec = _spec(record)
    assert validate(spec, PROVIDER, DECLARATION_CONTEXT) is None
    assert not is_dormant(spec)
    answer = solve_cascade(spec, PROVIDER)
    assert isinstance(answer, CascadeSolution), answer
    assert answer.outcome in TYPED_OUTCOMES
    if answer.outcome == "CONVERGED":
        declared = compile_cascade(spec, PROVIDER).spec
        assert acceptance_failures(spec, PROVIDER, declared, answer.state, answer.signature) == ()
        if answer.signature == tuple(record["signature"]):
            worst = deviation(answer.state, record["target"])
            assert max(worst.values()) <= 1.0, worst
    assert answer.outcome == "INITIALIZATION_FAILED"
    assert answer.cause == f"initialization_failed({PRESOLVE_ID}, not_two_phase)"
    assert answer.result is None
    assert answer.presolve_summary.outcome == "CONVERGED"
    assert answer.presolve_summary.signature == ("VAPOR", "VAPOR", "TWO_PHASE")
