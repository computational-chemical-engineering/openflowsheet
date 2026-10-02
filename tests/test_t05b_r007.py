"""T05b W3: R-007 admits a temperature-degenerate stream in either single phase (spec §10).

B19 (spec §14): in the unit layer (`tp_state.single_phase_admissible`, and through it T05's
declared ports, `ph_kernel.port_enthalpy` and `admission.admitted_enthalpy`) R7-1 is admitted with
reported gap `0.0`; R7-3 admitted with `5e-7 K`; R7-2 refused `inadmissible_phase(<port>, LIQUID)`;
R7-4 refused as registered; T05's five registered refusals stay refused — their own tests
(`test_t05_ph_flash.py`, `test_t05_pump.py`, `test_t05_separator.py`, `test_t05_exchanger.py`,
T05 A07–A12) run unchanged, and here each refused stream's degeneracy distance is checked against
`ref.t05_registered_refusals_degeneracy_K` so the margin that keeps them refused is measured, not
assumed.

Every expected value is `ref.r007_states` (the design lane's 40-digit twin). The reported gap of
an admitted degenerate stream is `δ`, compared to 1e-12 K (B19's tolerance: bisection to adjacent
doubles near 360 K, a few 1e-14 K).
"""

from __future__ import annotations

from typing import Any

import pytest
from t05_support import CONTEXT, PROVIDER, first_line
from t05_support import REF as T05_REF
from t05b_support import REF, error, number

from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.admission import admitted_enthalpy
from openflowsheet.models.syn001.ph_kernel import port_enthalpy
from openflowsheet.models.syn001.saturation_band import degeneracy_distance
from openflowsheet.models.syn001.tp_state import enthalpy_flow, single_phase_admissible
from openflowsheet.thermo import Phase, StreamState

COMPONENTS = PROVIDER.describe().components
STATES: dict[str, Any] = REF["r007_states"]
#: B19: the reported gap of an admitted degenerate stream is `δ`, to this, K.
GAP_TOLERANCE = 1e-12


def _stream(entry: dict[str, Any]) -> StreamState:
    flows = tuple(number(value) for value in entry["n_mol_per_s"])
    return StreamState(n=flows, temperature=number(entry["T_K"]), pressure=number(entry["P_Pa"]))


def _phase(entry: dict[str, Any]) -> Phase:
    phase = entry["declared_phase"]
    assert phase in ("LIQUID", "VAPOR")
    return phase  # type: ignore[no-any-return]


@pytest.mark.parametrize("state_id", sorted(STATES))
def test_b19_single_phase_admissible_matches_the_registered_verdict(state_id: str) -> None:
    entry = STATES[state_id]
    stream, phase = _stream(entry), _phase(entry)
    admissible, enthalpy, gap, status, message = single_phase_admissible(
        PROVIDER, stream, phase, COMPONENTS, CONTEXT
    )
    assert (status, message) == ("ok", "")
    assert admissible is entry["admitted"], (state_id, gap)
    # The enthalpy returned is always the declared phase's, admitted or not (the rows' form).
    assert enthalpy == enthalpy_flow(PROVIDER, stream, phase, COMPONENTS, CONTEXT)[1]
    if admissible:
        # Admitted only through the degeneracy test: the TP gap is ~300 K (`ref.tp_gap_K`), so
        # the reported gap is `δ`, which the unit layer's own band gives.
        assert number(entry["tp_gap_K"]) > TEMPERATURE_TOLERANCE
        assert error(gap, entry["degeneracy_K"]) <= GAP_TOLERANCE, gap
        assert gap == degeneracy_distance(
            PROVIDER, stream.n, stream.temperature, stream.pressure, CONTEXT
        )
    else:
        # Refused: the reported gap is the TP gap, unchanged by T05b.
        assert error(gap, entry["tp_gap_K"]) <= 1e-6 * number(entry["tp_gap_K"]), gap
        distance = degeneracy_distance(
            PROVIDER, stream.n, stream.temperature, stream.pressure, CONTEXT
        )
        assert error(distance, entry["degeneracy_K"]) <= 1e-9, distance
        assert distance > TEMPERATURE_TOLERANCE


def test_b19_r7_1_is_admitted_with_gap_exactly_zero() -> None:
    """Pure B vapour at `T_sat = 360 K` exactly: the band is the point 360 K, which the first
    bisection midpoint of `[280, 440]` hits (`ln K_B = 0` there), so `δ` is exactly `0.0`."""
    admissible, _, gap, _, _ = single_phase_admissible(
        PROVIDER, _stream(STATES["R7-1"]), "VAPOR", COMPONENTS, CONTEXT
    )
    assert admissible and gap == 0.0


@pytest.mark.parametrize("state_id", sorted(STATES))
def test_b19_t05_declared_ports_carry_the_verdict(state_id: str) -> None:
    """The two T05 routes into R-007: `port_enthalpy` (the PH flash, valve, reactor, pump inlet)
    reports the gap as its causal admissibility; `admitted_enthalpy` (the separator, the
    exchanger) returns the enthalpy or the typed refusal. A refusal's first line is the
    registered code `inadmissible_phase(<port>, <PHASE>)`."""
    entry = STATES[state_id]
    stream, phase = _stream(entry), _phase(entry)
    port = port_enthalpy(PROVIDER, stream, phase, COMPONENTS, CONTEXT, port="inlet")
    admitted = admitted_enthalpy(
        PROVIDER, COMPONENTS, CONTEXT, unit_id="U-TEST", port="inlet", stream=stream, phase=phase
    )
    if entry["admitted"]:
        assert port.status == "ok" and port.failure is None
        assert port.admissibility is not None
        assert error(port.admissibility, entry["degeneracy_K"]) <= GAP_TOLERANCE
        assert admitted == port.enthalpy_flow
    else:
        code = f"inadmissible_phase(inlet, {phase})"
        assert port.status == "unsupported" and port.failure is not None
        assert first_line(port.failure.message) == code
        assert not isinstance(admitted, float)
        assert admitted.status == "unsupported"
        assert first_line(admitted.message) == code


# -- T05's registered refusals: non-degenerate, so still refused (spec §10, B19) -------------

#: The stream each registered refusal judges, from `benchmarks/t05/reference_values.yaml`'s
#: inputs: PHF-F3's and the pump cases' inlet; SEP-F2's top product (the inlet split by 0.5 at
#: its temperature); HX-F4's cold outlet at its specified 350 K.
_REFUSED: dict[str, tuple[str, str, float, float]] = {
    "PHF-F3": ("inlet", "LIQUID", 1.0, 0.0),
    "PUMP-F1": ("inlet", "LIQUID", 1.0, 0.0),
    "PUMP-F2": ("inlet", "LIQUID", 1.0, 0.0),
    "SEP-F2": ("inlet", "VAPOR", 0.5, 0.0),
    "HX-F4": ("cold_inlet", "LIQUID", 1.0, 350.0),
}


@pytest.mark.parametrize("case", sorted(_REFUSED))
def test_b19_t05_registered_refusals_are_non_degenerate_and_refused(case: str) -> None:
    port, phase, fraction, temperature = _REFUSED[case]
    inputs = T05_REF["unit_cases"][case]["inputs"][port]
    stream = StreamState(
        n=tuple(fraction * number(value) for value in inputs["n_mol_per_s"]),
        temperature=temperature or number(inputs["T_K"]),
        pressure=number(inputs["P_Pa"]),
    )
    distance = degeneracy_distance(PROVIDER, stream.n, stream.temperature, stream.pressure, CONTEXT)
    # Registered to six decimals by the twin.
    assert error(distance, REF["t05_registered_refusals_degeneracy_K"][case]) <= 1e-6, distance
    assert distance >= 14.0
    admissible, _, gap, status, _ = single_phase_admissible(
        PROVIDER,
        stream,
        phase,
        COMPONENTS,
        CONTEXT,  # type: ignore[arg-type]
    )
    assert status == "ok" and not admissible and gap > TEMPERATURE_TOLERANCE


# -- T05b W6: the pre-screen before the band test ----------------------------------------------


class _CountingLnK:
    """SYN-001, counting the `lnK` evaluations a call asks for."""

    def __init__(self) -> None:
        self.calls = 0

    def describe(self) -> Any:
        return PROVIDER.describe()

    def evaluate_phase(self, request: Any, context: Any) -> Any:
        if "lnK" in request.properties:
            self.calls += 1
        return PROVIDER.evaluate_phase(request, context)

    def flash(self, request: Any, context: Any) -> Any:
        return PROVIDER.flash(request, context)


def _sweep() -> list[tuple[tuple[float, ...], float]]:
    """B19's states, and near-pure and ternary streams at their band ends and mid-band, offset
    by multiples of `τ_T` around the pre-screen's `2τ` (the full sweep is recorded in
    `docs/t05b-measurements.md`, W6)."""
    from openflowsheet.models.syn001.saturation_band import band_temperature

    found = [(_stream(entry).n, _stream(entry).temperature) for entry in STATES.values()]
    for n in (
        (0.0, 2.0, 0.0),
        (1e-12, 2.0, 0.0),
        (0.0, 2.0, 1e-8),
        (4.7e-8, 2.0, 0.0),
        (1e-6, 2.0, 0.0),
        (1.0, 1.0, 1.0),
    ):
        ends = [band_temperature(PROVIDER, n, 1e5, beta, CONTEXT).temperature for beta in (0, 1)]
        assert ends[0] is not None and ends[1] is not None
        for anchor in (ends[0], ends[1], 0.5 * (ends[0] + ends[1])):
            for k in (0.0, 0.5, 1.0, 1.5, 1.9, 2.0, 2.1, 3.0, 100.0):
                for sign in (1.0, -1.0):
                    found.append((n, anchor + sign * k * TEMPERATURE_TOLERANCE))
    return found


def test_w6_the_pre_screen_only_decides_non_degenerate_streams() -> None:
    """`outside_the_degeneracy_window` is a sufficient condition for `δ > τ_T`: wherever it
    answers `True`, the band test's `δ` exceeds `τ_T` — and on this sweep it answers for every
    stream whose band ends both lie more than `2τ` on the same side as its screen."""
    from openflowsheet.models.syn001.saturation_band import outside_the_degeneracy_window

    decided = 0
    for n, temperature in _sweep():
        excluded = outside_the_degeneracy_window(PROVIDER, n, temperature, 1e5, CONTEXT)
        distance = degeneracy_distance(PROVIDER, n, temperature, 1e5, CONTEXT)
        if excluded:
            decided += 1
            assert distance > TEMPERATURE_TOLERANCE, (n, temperature, distance)
    assert decided > 0


def test_w6_a_far_refusal_costs_two_lnk_calls() -> None:
    """R7-4 (`δ = 26.82 K`): refused on the pre-screen's first sign test alone, where the band
    test took two bisections (~100 `lnK` calls)."""
    entry = STATES["R7-4"]
    counting = _CountingLnK()
    admissible, *_ = single_phase_admissible(
        counting, _stream(entry), _phase(entry), COMPONENTS, CONTEXT
    )
    assert admissible is False
    assert 1 <= counting.calls <= 2
