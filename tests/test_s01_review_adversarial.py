"""S01 review (design lane, `reviewer`): adversarial tests that kill mutants the WO suites let live.

Each test pins a path the WO-1..WO-3 suites never drove to its failing side; the mutant it kills is
named in its docstring (`docs/reviews/S01-review.md`, findings S-1 to S-4). All pass on `ea12548`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from test_s01_cascade_wo1 import REFERENCE, UNIT, _spec
from test_s01_cascade_wo2 import PROVIDER, solved
from test_s01_cascade_wo3 import _registered_partial_dormancy_root

from openflowsheet.models.syn001.cascade import (
    DormantAnswer,
    _enthalpy_flow,
    energy_precheck,
    label_row_id,
    stage_temperature_id,
)
from openflowsheet.models.syn001.cascade_solve import (
    DECLARATION_CONTEXT,
    AcceptanceDefectError,
    acceptance_failures,
    compile_cascade,
    solve_cascade,
)
from openflowsheet.models.syn001.cascade_solve import run_region as real_run_region
from openflowsheet.thermo.syn001 import T_MIN

solve_module = __import__("openflowsheet.models.syn001.cascade_solve", fromlist=["run_region"])


def test_a09_section_8_refuses_an_inadmissible_single_phase_stage() -> None:
    """§8's admissibility branch on its failing side (kills: the admissibility check removed).
    C4's root with stage 3 (LIQUID, 320 K, criterion 0.37) heated 60 K is a liquid above its
    bubble point (criterion 1.87)."""
    spec = _spec(REFERENCE["cases"]["C4"])
    state = dict(solved("C4").state)
    state[stage_temperature_id(UNIT, 3)] += 60.0
    declared = compile_cascade(spec, PROVIDER).spec
    failures = acceptance_failures(spec, PROVIDER, declared, state, solved("C4").signature)
    assert any(f.startswith("LIQUID stage 3 inadmissible") for f in failures), failures


def test_a09_section_8_refuses_a_broken_zero_flow_label() -> None:
    """§8's label rows on their failing side (kills: label rows left out of §8). The A19 root
    under (ZERO_FLOW, ZERO_FLOW, LIQUID) with `T_2` moved off `T_1` by 5 K."""
    record = REFERENCE["partial_dormancy"]
    spec = _spec(record)
    state = _registered_partial_dormancy_root(spec)
    state[stage_temperature_id(UNIT, 2)] += 5.0
    declared = compile_cascade(spec, PROVIDER).spec
    failures = acceptance_failures(spec, PROVIDER, declared, state, tuple(record["signature"]))
    assert any(label_row_id(UNIT, 2) in f for f in failures), failures


def test_a09_solve_cascade_raises_on_a_converged_answer_that_fails_section_8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§8 is enforced inside `solve_cascade` (kills: the `AcceptanceDefectError` raise removed).
    The target's `CONVERGED` state is moved 1e-3 K off the root after `solve_region` returns."""

    def tampered(target: Any, *args: Any, **kwargs: Any) -> Any:
        result = real_run_region(target, *args, **kwargs)
        if target.problem != "target":
            return result
        state = dict(result.state)
        state[stage_temperature_id(UNIT, 2)] += 1e-3
        return replace(result, state=state)

    monkeypatch.setattr(solve_module, "run_region", tampered)
    with pytest.raises(AcceptanceDefectError):
        solve_cascade(_spec(REFERENCE["cases"]["C2"]), PROVIDER)


@pytest.mark.parametrize("name", ["D1", "D2"])
def test_a13_a14_solve_cascade_routes_an_all_dormant_cascade_to_section_4_6(name: str) -> None:
    """§7.1 through the public entry point (kills: the dormant route removed from
    `solve_cascade`, which then raises in the initializer)."""
    record = REFERENCE["dormant"][name]
    answer = solve_cascade(_spec(record), PROVIDER)
    assert isinstance(answer, DormantAnswer)
    assert answer.outcome == record["outcome"]


def test_a16_the_lower_energy_bound_is_taken_at_the_bottom_stage_pressure() -> None:
    """R7's lower bound is the closure's minimum: all of F leaves as liquid from stage N, at
    `(T_min, P_N)` (kills: the bound taken at `P_1`). C3's pressures differ (1.00–1.08 bar)."""
    spec = _spec(REFERENCE["cases"]["C3"])
    totals = [sum(inlet.state.n[i] for inlet in spec.inlets()) for i in range(3)]

    def liquid_at(pressure: float) -> float:
        return _enthalpy_flow(
            PROVIDER, DECLARATION_CONTEXT, spec.components, totals, T_MIN, pressure, "LIQUID"
        )

    assert spec.pressures[0] != spec.pressures[-1]
    assert liquid_at(spec.pressures[0]) != liquid_at(spec.pressures[-1])
    precheck = energy_precheck(spec, PROVIDER, DECLARATION_CONTEXT)
    assert precheck.lower == liquid_at(spec.pressures[-1])
