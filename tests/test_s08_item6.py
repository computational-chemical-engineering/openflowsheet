"""S08 WO-1: S02 §8 item 6, two-phase saturation consistency (S08-design §5.5).

Every `TWO_PHASE` stage of an accepted column state lies within `τ₆ = 1e-4 K` of the bubble
temperature of its liquid and the dew temperature of its vapour. The division-free equilibrium
rows alone admit a near-trivial split, `V_j → 0` far from saturation (§3 F4); item 6 rejects it.

- S08.A12: item 6 passes on all 42 registered `CONVERGED` column roots (the 47 configurations of
  §3 F3), the largest error ≤ 1e-5 K; `saturation_errors` flags F1's Stage-A state at stage 4
  (≥ 0.3 K), and item 6 is the only §8 item that state fails (the premise of §5.1 trigger (ii)).
- A constructed near-trivial state: every equilibrium row of the stage ≪ its kind tolerance,
  `V_j > 0`, `T_j` 0.5 K below the bubble temperature of its liquid; item 6 flags it.
- A band position other than `inside`, and a band refusal, are failures (`inf`).
"""

from __future__ import annotations

import math
import sys
from collections.abc import Mapping
from dataclasses import replace
from functools import cache
from typing import Any

import pytest
from conftest import REPO_ROOT
from test_s02_column_wo1 import FEED, PROVIDER, REFERENCE, SPECS, _variant
from test_s06_column_wo1 import J_CASES, U_SETS, V_SETS

import openflowsheet.models.syn001.column_solve as column_solve_module
from openflowsheet.models.syn001.cascade import (
    InletState,
    SideFeed,
    _k_values,
    liquid_id,
    stage_pressure_id,
    stage_temperature_id,
    vapor_id,
)
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
from openflowsheet.models.syn001.column import ColumnSpec
from openflowsheet.models.syn001.column_solve import (
    TWO_PHASE_SATURATION_TOLERANCE,
    ColumnSolution,
    acceptance_failures,
    saturation_errors,
    solve_column,
)
from openflowsheet.models.syn001.saturation_band import BandError, BandTemperature
from openflowsheet.orchestrator.region import KIND_TOLERANCE, Regime

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import s03_references_ours as s03_ours  # noqa: E402

#: §6.2's F1: M4 with no bottom vapour, a cold liquid bottom inlet and a vapour side feed at stage
#: 3 (a flooded bottom below a vapour feed). Inline until WO-G registers it.
F1 = replace(
    SPECS["M4"],
    sides=(SideFeed("feed", 3, InletState(FEED, 385.0, 1.02e5, "VAPOR")),),
    bottom=InletState((0.03, 0.04, 0.03), 330.0, 1.04e5, "LIQUID"),
)


def _registered() -> dict[str, ColumnSpec]:
    """§3 F3's 47 registered column configurations: S02 M1–M4 and P1, the `ref.variants`, S06
    J1–J8, V and U, and S03's cases."""
    cases: dict[str, ColumnSpec] = {f"S02.{case}": SPECS[case] for case in SPECS}
    for case, variants in REFERENCE["variants"].items():
        for variant in variants:
            cases[f"S02.V-{case}.{variant}"] = _variant(case, variant)
    cases.update({f"S06.{case}": spec for case, spec in J_CASES.items()})
    cases.update({f"S06.V.{case}": spec for case, spec in V_SETS.items()})
    cases.update({f"S06.U.{case}": spec for case, spec in U_SETS.items()})
    s03: dict[str, Any] = s03_ours.load_cases()
    components = tuple(s03["components"])
    for case, record in s03["cases"].items():
        cases[f"S03.{case}"] = s03_ours.column_spec(record, components)
    return cases


def _regimes(spec: ColumnSpec, answer: ColumnSolution) -> dict[int, Regime]:
    return dict(zip(spec.equilibrium_stages(), answer.signature, strict=True))


def _solve_recording(spec: ColumnSpec, *, accept: bool) -> tuple[ColumnSolution, tuple[Any, ...]]:
    """`spec` solved with `acceptance_failures` wrapped: returns the answer and the arguments
    acceptance was called with at the `CONVERGED` state. `accept` bypasses acceptance (`()`),
    which yields today's Stage-A state where §8 would reject it."""
    seen: list[tuple[Any, ...]] = []
    real = column_solve_module.acceptance_failures

    def record(*args: Any) -> tuple[str, ...]:
        seen.append(args)
        return () if accept else real(*args)

    patch = pytest.MonkeyPatch()
    patch.setattr(column_solve_module, "acceptance_failures", record)
    try:
        answer = solve_column(spec, PROVIDER)
    finally:
        patch.undo()
    assert isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"
    assert len(seen) == 1
    return answer, seen[0]


@cache
def _stage_a_f1() -> tuple[Any, ...]:
    """F1 on today's path (Stage A), acceptance bypassed: `acceptance_failures`'s arguments."""
    answer, args = _solve_recording(F1, accept=True)
    assert answer.signature == ("TWO_PHASE",) * 4 + ("LIQUID",)
    return args


@cache
def _m1() -> tuple[ColumnSolution, tuple[Any, ...]]:
    return _solve_recording(SPECS["M1"], accept=False)


def test_the_tolerance_is_the_registered_one() -> None:
    assert TWO_PHASE_SATURATION_TOLERANCE == 1e-4


def test_a12_item_6_passes_on_every_registered_converged_root() -> None:
    cases = _registered()
    assert len(cases) == 47
    worst, converged = 0.0, 0
    for name, spec in cases.items():
        answer = solve_column(spec, PROVIDER)
        if not (isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"):
            continue
        if answer.reentry is not None:
            # S08 §6.1: P1 now converges through Stage B, at LIQUID ×5: no TWO_PHASE stage, so
            # item 6 holds vacuously. The 42 are the roots Stage A converges to (`reentry` None).
            assert name == "S02.P1", name
            assert saturation_errors(spec, PROVIDER, answer.state, _regimes(spec, answer)) == {}
            continue
        converged += 1
        errors = saturation_errors(spec, PROVIDER, answer.state, _regimes(spec, answer))
        assert errors, name
        assert all(error <= TWO_PHASE_SATURATION_TOLERANCE for error in errors.values()), name
        worst = max(worst, *errors.values())
    assert converged == 42
    # §7 A12's bound; the value is recorded in docs/S08_DECISIONS.md (MEASURED).
    print(f"S08.A12 worst registered item-6 error {worst!r} K")
    assert worst <= 1e-5


def test_a12_f1_stage_a_is_flagged_at_stage_4_only() -> None:
    spec, provider, declared, state, regimes = _stage_a_f1()
    errors = saturation_errors(spec, provider, state, regimes)
    assert set(errors) == {1, 2, 3, 4}
    assert errors[4] >= 0.3
    assert all(errors[j] <= TWO_PHASE_SATURATION_TOLERANCE for j in (1, 2, 3))
    failures = acceptance_failures(spec, provider, declared, state, regimes)
    assert failures, "F1's Stage-A state is rejected"
    assert all(failure.startswith("§8.6: TWO_PHASE stage 4: ") for failure in failures)
    assert f"§8.6: TWO_PHASE stage 4: bubble error {errors[4]!r} K" in failures or (
        f"§8.6: TWO_PHASE stage 4: dew error {errors[4]!r} K" in failures
    )


def _near_trivial(
    spec: ColumnSpec, state: Mapping[str, float], stage: int, offset: float, scale: float
) -> dict[str, float]:
    """`state` with stage `stage` moved `offset` K off its temperature and its vapour replaced by
    `v_i = scale · K_i(T, P) · l_i`: the stage's equilibrium rows `v_i L − K_i l_i V` are then
    `scale · K_i l_i L (1 − Σ K x)`, as small as `scale` makes them, at any `T`."""
    unit, components = spec.unit_id, spec.components
    moved = dict(state)
    temperature = state[stage_temperature_id(unit, stage)] + offset
    pressure = state[stage_pressure_id(unit, stage)]
    liquid = tuple(state[liquid_id(unit, stage, c)] for c in components)
    k = _k_values(PROVIDER, DECLARATION_CONTEXT, components, temperature, pressure)
    moved[stage_temperature_id(unit, stage)] = temperature
    for c, l_i, k_i in zip(components, liquid, k, strict=True):
        moved[vapor_id(unit, stage, c)] = scale * k_i * l_i
    return moved


def test_a_constructed_near_trivial_split_is_flagged() -> None:
    answer, (spec, _, declared, _, regimes) = _m1()
    stage = 3
    assert regimes[stage] == "TWO_PHASE"
    state = _near_trivial(spec, answer.state, stage, -0.5, 1e-9)
    unit, components = spec.unit_id, spec.components
    # The construction is what F4 describes: V > 0, every equilibrium row of the stage far
    # inside its kind tolerance, yet T 0.5 K under the bubble temperature of the liquid.
    temperature = state[stage_temperature_id(unit, stage)]
    pressure = state[stage_pressure_id(unit, stage)]
    liquid = [state[liquid_id(unit, stage, c)] for c in components]
    vapor = [state[vapor_id(unit, stage, c)] for c in components]
    big_l, big_v = sum(liquid), sum(vapor)
    assert big_v > 0.0
    k = _k_values(PROVIDER, DECLARATION_CONTEXT, components, temperature, pressure)
    rows = [v * big_l - k_i * x * big_v for v, x, k_i in zip(vapor, liquid, k, strict=True)]
    assert max(abs(row) for row in rows) <= 1e-3 * KIND_TOLERANCE["molar_flow_squared"]
    before = saturation_errors(spec, PROVIDER, answer.state, regimes)
    after = saturation_errors(spec, PROVIDER, state, regimes)
    assert after[stage] >= 0.5 - before[stage]
    assert {j for j, e in after.items() if e > TWO_PHASE_SATURATION_TOLERANCE} == {stage}
    pairs = column_solve_module._saturation_pairs(spec, PROVIDER, state, regimes)
    bubble = pairs[stage][0]
    assert abs(bubble - 0.5) <= before[stage] + 1e-9
    failures = acceptance_failures(spec, PROVIDER, declared, state, regimes)
    assert f"§8.6: TWO_PHASE stage {stage}: bubble error {bubble!r} K" in failures


@pytest.mark.parametrize("outside", ["below", "above", "refused"])
def test_a_band_answer_other_than_inside_is_a_failure(
    monkeypatch: pytest.MonkeyPatch, outside: str
) -> None:
    answer, (spec, _, declared, _, regimes) = _m1()

    def band(*args: Any, **kwargs: Any) -> BandTemperature:
        if outside == "refused":
            raise BandError("not_converged", "stubbed")
        return BandTemperature(outside, evaluations=1)  # type: ignore[arg-type]

    monkeypatch.setattr(column_solve_module, "band_temperature", band)
    errors = saturation_errors(spec, PROVIDER, answer.state, regimes)
    two_phase = [j for j, regime in regimes.items() if regime == "TWO_PHASE"]
    assert two_phase and errors == {j: math.inf for j in two_phase}
    failures = acceptance_failures(spec, PROVIDER, declared, answer.state, regimes)
    for j in two_phase:
        for side in ("bubble", "dew"):
            assert f"§8.6: TWO_PHASE stage {j}: {side} error inf K" in failures
