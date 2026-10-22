"""S01 WO-4 — the review's fixes at their boundaries: spec §17.3 (R-512) and §17.9 (R-518).

Each test names the §10 assertion whose rule it pins at the boundary the review found: A15 (§5's
R5), A09 (§8's admissibility), A13 and A14 (§4.6's swapped energy rows).
"""

from __future__ import annotations

import math
from dataclasses import replace

from test_s01_cascade_wo1 import CONTEXT, REFERENCE, UNIT, _spec
from test_s01_cascade_wo2 import PROVIDER, solved

from openflowsheet.models.syn001.cascade import (
    CascadeSpec,
    DormantAnswer,
    _k_values,
    dormant_answer,
    liquid_id,
    stage_pressure_id,
    stage_temperature_id,
    validate,
)
from openflowsheet.models.syn001.cascade_solve import (
    DECLARATION_CONTEXT,
    acceptance_failures,
    compile_cascade,
    solve_cascade,
)
from openflowsheet.orchestrator.region import KIND_TOLERANCE

#: Probe E1 of the review: C2's `top` at the upper adjacent double of its bubble temperature.
E1_TEMPERATURE = 359.1106267639602


def _bubble_sum(n: tuple[float, ...], temperature: float, pressure: float) -> float:
    """The struck sum test, `Σ z K − 1`, at `(T, P)`."""
    k = _k_values(PROVIDER, CONTEXT, ("A", "B", "C"), temperature, pressure)
    total = sum(n)
    return sum(a / total * ki for a, ki in zip(n, k, strict=True)) - 1.0


def _upper_bubble_double(n: tuple[float, ...], pressure: float, low: float, high: float) -> float:
    """The smallest double at which `Σ z K > 1` (`K` rises with `T`), by bisection on doubles."""
    assert _bubble_sum(n, low, pressure) <= 0.0 < _bubble_sum(n, high, pressure)
    while math.nextafter(low, high) < high:
        middle = low + (high - low) / 2
        if middle in (low, high):
            middle = math.nextafter(low, high)
        if _bubble_sum(n, middle, pressure) > 0.0:
            high = middle
        else:
            low = middle
    return high


# -- R-512: R5 is R-007 --------------------------------------------------------------------------


def test_a15_a_saturated_liquid_top_passes_section_5() -> None:
    """A15 (R-512, review MF1 failure 1): the C2 `top` inlet at the upper adjacent double of its
    bubble temperature fails the struck sum test by 2.2e-16 and is admitted by R-007."""
    spec = _spec(REFERENCE["cases"]["C2"])
    top = spec.top
    assert _upper_bubble_double(top.n, top.pressure, 340.0, 380.0) == E1_TEMPERATURE
    assert _bubble_sum(top.n, E1_TEMPERATURE, top.pressure) > 0.0
    saturated = replace(spec, top=replace(top, temperature=E1_TEMPERATURE))
    assert validate(saturated, PROVIDER, CONTEXT) is None


def test_a15_r5_still_refuses_a_superheated_liquid_and_a_subcooled_vapour() -> None:
    """A15: off the boundary R-007 and the sum test agree (spec §17.3); the refusals name the
    equivalent temperature error."""
    spec = _spec(REFERENCE["cases"]["C2"])
    for inlet, temperature, cause in (
        ("top", 380.0, "inadmissible_inlet(top, LIQUID)"),
        ("bottom", 330.0, "inadmissible_inlet(bottom, VAPOR)"),
    ):
        changed: CascadeSpec = replace(
            spec, **{inlet: replace(getattr(spec, inlet), temperature=temperature)}
        )
        failure = validate(changed, PROVIDER, CONTEXT)
        assert failure is not None and failure.cause == cause
        assert "equivalent temperature error" in failure.message


# -- R-512: §8 judges the outlet with R-007 ------------------------------------------------------


def test_a09_section_8_admits_a_liquid_stage_at_its_bubble_point() -> None:
    """A09 (R-512, review MF1 failure 2): C4's LIQUID stage 3 moved to the upper adjacent double
    of its outlet `l_3`'s bubble temperature fails the struck sum test and passes §8's
    admissibility; its other rows are off the root, so only the admissibility verdict is read."""
    spec = _spec(REFERENCE["cases"]["C4"])
    answer = solved("C4")
    assert answer.signature[2] == "LIQUID"
    state = dict(answer.state)
    n = tuple(float(state[liquid_id(UNIT, 3, c)]) for c in "ABC")
    pressure = float(state[stage_pressure_id(UNIT, 3)])
    bubble = _upper_bubble_double(n, pressure, 300.0, 420.0)
    assert _bubble_sum(n, bubble, pressure) > 0.0
    state[stage_temperature_id(UNIT, 3)] = bubble
    declared = compile_cascade(spec, PROVIDER).spec
    failures = acceptance_failures(spec, PROVIDER, declared, state, answer.signature)
    assert not any("inadmissible" in failure for failure in failures), failures
    assert failures  # the energy and equilibrium rows are off the root


# -- R-518: a swapped energy row holds within τ_heat_rate ----------------------------------------


def _dormant_with(duties: tuple[float, ...]) -> CascadeSpec:
    return replace(_spec(REFERENCE["dormant"]["D1"]), duties=duties)


def test_a13_a_swapped_energy_row_within_tau_heat_rate_holds() -> None:
    """A13 (R-518, review SF2): every inlet dormant and `Q* = (0, 5e-4, 0)` W, under
    `τ_heat_rate`, is `CONVERGED` by the closed form and by `solve_cascade`'s §7.1 route."""
    assert 5e-4 < KIND_TOLERANCE["heat_rate"] < 2e-3
    spec = _dormant_with((0.0, 5e-4, 0.0))
    for answer in (
        dormant_answer(spec, PROVIDER, DECLARATION_CONTEXT),
        solve_cascade(spec, PROVIDER),
    ):
        assert isinstance(answer, DormantAnswer)
        assert (answer.outcome, answer.cause) == ("CONVERGED", None)
        assert answer.swapped_energy == (0.0, 5e-4, 0.0)


def test_a14_a_swapped_energy_row_beyond_tau_heat_rate_is_a_conflict() -> None:
    """A14 (R-518): `Q* = (0, 2e-3, 0)` W, over `τ_heat_rate`, is `SPECIFICATION_CONFLICT`,
    `zero_flow_conflict(<U>:stage:2:energy)`."""
    spec = _dormant_with((0.0, 2e-3, 0.0))
    answer = dormant_answer(spec, PROVIDER, DECLARATION_CONTEXT)
    assert answer.outcome == "SPECIFICATION_CONFLICT"
    assert answer.cause == f"zero_flow_conflict({UNIT}:stage:2:energy)"
