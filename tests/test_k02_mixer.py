"""K02: the adiabatic mixer and its v0.0 subcooled-liquid restriction.

The mixer is the only v0.0 unit whose outlet is not given by a specification, so it is the only
one whose evaluator has to solve something. Two independent expectations are used and they are
independent of each other as well as of the code:

- **derivation §4.1's closed form.** With equal `c_p` in both phases, both inlets liquid and a
  common pressure, the closure is linear in T and `T_out = (sum_k n_k T_k) / sum_k n_k`. Fable
  states it as "a check on the K02 bracketed mixer solve, not a substitute for it".
- **Fable's 20-digit `T_mix_K`** for each registered variant, generated with mpmath at 40 digits.

Derivation §7 finding 5 records that no registered r-variant leaves the subcooled-liquid domain,
so K02 "needs a separate case (for example a fresh feed hotter than its bubble point) to test the
typed mixer-domain failure". Both halves of that failure are exercised here: an inlet that is not
liquid, and two liquid inlets whose *mixture* is not.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    SpecificationError,
    Wiring,
    assemble,
    flow_id,
    origin,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.mixer import BEHAVIOURAL_EQUATIONS, AdiabaticMixer
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.syn001 import Syn001Provider

CONTEXT = EvaluationContext(
    model_version="K02-unit-evaluator@" + "0" * 64, constants_sha256="0" * 64
)
PROVIDER = Syn001Provider()
MIXER = AdiabaticMixer(unit_id="U-MIX", provider=PROVIDER, context=CONTEXT)

#: ADR 0001 D6, registered for SYN-001 only.
TEMPERATURE_TOLERANCE = 1e-6
FLOW_TOLERANCE = 1e-9 + 1e-8 * 3.0

FRESH_FEED = StreamState(n=(1.0, 1.0, 1.0), temperature=300.0, pressure=100_000.0)

CASE_IDS = [
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
]


def variants(reference_values: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {entry["case_id"]: entry for entry in reference_values["variants"]}


def recycle_of(case: Mapping[str, Any]) -> StreamState:
    return StreamState(
        n=tuple(float(value) for value in case["recycle_mol_per_s"]),
        temperature=float(case["T_flash_K"]),
        pressure=float(case["P_Pa"]),
    )


# ------------------------------------------------------------------- against the reference


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_mixer_outlet_temperature_matches_the_twenty_digit_reference(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    case = variants(reference_values)[case_id]
    result = MIXER.evaluate({"inlet": (FRESH_FEED, recycle_of(case))}, CONTEXT)
    assert result.status == "ok", result.message
    outlet = result.outlets["outlet"]
    assert outlet.temperature == pytest.approx(float(case["T_mix_K"]), abs=TEMPERATURE_TOLERANCE)
    assert result.phase_signature == case["mixer_outlet_state"]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_mixer_outlet_temperature_matches_the_analytic_closed_form(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """Derivation §4.1: with equal c_p and a common pressure the closure is linear in T.

    Independent of the reference values above and of the solver: a flow-weighted mean, computed
    here from the inlet states alone.
    """
    case = variants(reference_values)[case_id]
    recycle = recycle_of(case)
    result = MIXER.evaluate({"inlet": (FRESH_FEED, recycle)}, CONTEXT)
    weighted = sum(FRESH_FEED.n) * FRESH_FEED.temperature + sum(recycle.n) * recycle.temperature
    expected = weighted / (sum(FRESH_FEED.n) + sum(recycle.n))
    assert result.outlets["outlet"].temperature == pytest.approx(
        expected, abs=TEMPERATURE_TOLERANCE
    )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_mixer_component_balance_is_exact(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    case = variants(reference_values)[case_id]
    recycle = recycle_of(case)
    result = MIXER.evaluate({"inlet": (FRESH_FEED, recycle)}, CONTEXT)
    outlet = result.outlets["outlet"]
    for index in range(len(COMPONENTS)):
        assert outlet.n[index] == FRESH_FEED.n[index] + recycle.n[index]
    for index, value in enumerate(case["mixed_feed_mol_per_s"]):
        assert outlet.n[index] == pytest.approx(float(value), abs=FLOW_TOLERANCE)


def test_a_single_inlet_temperature_is_returned_exactly() -> None:
    """SYN-001 at r = 0: the recycle is dormant, so T_mix is 300 K and not 300 K plus a residue.

    The bracket collapses to a point and the closure is not iterated at all, which is why this
    is an exact equality rather than a tolerance.
    """
    dormant = StreamState(n=(0.0, 0.0, 0.0), temperature=360.0, pressure=100_000.0)
    result = MIXER.evaluate({"inlet": (FRESH_FEED, dormant)}, CONTEXT)
    assert result.status == "ok"
    assert result.outlets["outlet"].temperature == 300.0
    assert result.iterations == 0


# ------------------------------------------------------------------------------ zero flow


class SpyProvider:
    """Counts provider traffic, so "its composition is never evaluated" can be asserted."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.states: list[StreamState] = []

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.states.append(request.state)
        return self.inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self.states.append(request.state)
        return self.inner.flash(request, context)


def test_mix_dormant_inlet_is_honoured_by_never_evaluating_the_dormant_stream() -> None:
    """`MIX-dormant-inlet`, as behaviour: exactly zero contribution, no property evaluated."""
    spy = SpyProvider(Syn001Provider())
    mixer = AdiabaticMixer(unit_id="U-MIX", provider=spy, context=CONTEXT)
    dormant = StreamState(n=(0.0, 0.0, 0.0), temperature=360.0, pressure=100_000.0)
    result = mixer.evaluate({"inlet": (FRESH_FEED, dormant)}, CONTEXT)
    assert result.status == "ok"
    assert result.outlets["outlet"].n == FRESH_FEED.n
    assert not any(state.is_dormant for state in spy.states), (
        "the dormant inlet reached the provider; D3.1 says no property is evaluated for it"
    )


def test_every_inlet_dormant_gives_a_dormant_outlet_and_no_solve() -> None:
    spy = SpyProvider(Syn001Provider())
    mixer = AdiabaticMixer(unit_id="U-MIX", provider=spy, context=CONTEXT)
    dormant = StreamState(n=(0.0, 0.0, 0.0), temperature=330.0, pressure=100_000.0)
    other = StreamState(n=(0.0, 0.0, 0.0), temperature=360.0, pressure=100_000.0)
    result = mixer.evaluate({"inlet": (dormant, other)}, CONTEXT)
    assert result.status == "ok"
    assert result.phase_signature == "ZERO_FLOW"
    assert result.outlets["outlet"].is_dormant
    assert spy.states == [], "nothing was there to evaluate"


def test_a_zero_component_passes_through_the_mixer_exactly() -> None:
    """ADR 0001 D3.3 (STA-02): n_tot > 0 with n_B == 0 in both inlets."""
    first = StreamState(n=(1.0, 0.0, 1.0), temperature=300.0, pressure=100_000.0)
    second = StreamState(n=(0.5, 0.0, 0.5), temperature=320.0, pressure=100_000.0)
    result = MIXER.evaluate({"inlet": (first, second)}, CONTEXT)
    assert result.status == "ok", result.message
    assert result.outlets["outlet"].n[1] == 0.0


# ---------------------------------------------------------------- the v0.0 domain restriction


def test_two_liquid_inlets_whose_mixture_is_not_liquid_are_also_refused() -> None:
    """The other half of the restriction, and the one a naive inlet check would miss.

    Pure A at 300 K is liquid (K_A = 0.534) and pure C at 395 K is liquid (K_C < 1, since
    K_C(400 K, P_r) = 1 exactly). Their equal-flow mixture sits at 347.5 K with z = (0.5, 0, 0.5),
    where sum z_i K_i is about 1.15 — two-phase. The closure is solved, the final admissibility
    check catches it, and the unit reports rather than returning a liquid enthalpy for a state
    that is not liquid.
    """
    pure_a = StreamState(n=(1.0, 0.0, 0.0), temperature=300.0, pressure=100_000.0)
    pure_c = StreamState(n=(0.0, 0.0, 1.0), temperature=395.0, pressure=100_000.0)
    result = MIXER.evaluate({"inlet": (pure_a, pure_c)}, CONTEXT)
    assert result.status == "unsupported"
    assert "T05" in result.message
    assert "347" in result.message, "the message should say where the closure put the outlet"
    assert result.outlets == {}


def test_inlets_at_different_pressures_are_a_validation_failure() -> None:
    """ADR 0001 D4.5: the unit never silently repairs an invalid pressure network."""
    low = StreamState(n=(1.0, 1.0, 1.0), temperature=300.0, pressure=90_000.0)
    result = MIXER.evaluate({"inlet": (FRESH_FEED, low)}, CONTEXT)
    assert result.status == "error"
    assert result.outlets == {}


def test_an_inlet_outside_the_declared_domain_is_reported_not_extrapolated() -> None:
    cold = StreamState(n=(1.0, 1.0, 1.0), temperature=200.0, pressure=100_000.0)
    result = MIXER.evaluate({"inlet": (FRESH_FEED, cold)}, CONTEXT)
    assert result.status == "out_of_domain"
    assert result.outlets == {}


def test_a_mixer_wired_to_one_inlet_is_refused() -> None:
    """It would still produce a plausible number, which is exactly why it is refused."""
    with pytest.raises(SpecificationError, match="two or more"):
        MIXER.evaluate({"inlet": (FRESH_FEED,)}, CONTEXT)
    with pytest.raises(SpecificationError, match="plausible number"):
        MIXER.contribute(Wiring({"inlet": ("S1",), "outlet": ("S2",)}), COMPONENTS)


# ------------------------------------------------------------------------------------ rows

MIX_STREAMS = ("S1", "S6", "S2")
MIX_WIRING = {"U-MIX": Wiring({"inlet": ("S1", "S6"), "outlet": ("S2",)})}


def build_mixer_spec() -> Any:
    return assemble(
        label="K02-M3-mixer",
        units=[MIXER],
        wiring=MIX_WIRING,
        streams=MIX_STREAMS,
        components=COMPONENTS,
    )


def mixer_state(spec: Any) -> dict[str, float]:
    state = {name: 0.0 for name in spec.variable_ids}
    for stream, temperature in (("S1", 300.0), ("S6", 360.0), ("S2", 321.2)):
        state[temperature_id(stream)] = temperature
        state[pressure_id(stream)] = 100_000.0
        for index, component in enumerate(COMPONENTS):
            state[flow_id(stream, component)] = 1.0 + 0.1 * index
    return state


def test_d4_3_mix_mole_is_exactly_minus_one_half() -> None:
    """ADR 0008 D4.3, verbatim: two inlets at 0.25 and an outlet at 1.0 give -0.5 mol/s."""
    spec = build_mixer_spec()
    state = mixer_state(spec)
    state[flow_id("S1", "A")] = 0.25
    state[flow_id("S6", "A")] = 0.25
    state[flow_id("S2", "A")] = 1.0
    assert row_values(spec, state)[row_id("U-MIX", "MIX-mole", "A")] == -0.5


def test_mix_energy_has_the_inflow_minus_outflow_orientation() -> None:
    """More enthalpy in than out is a positive residual (ADR 0008 D3.3)."""
    spec = build_mixer_spec()
    hot = mixer_state(spec)
    hot[temperature_id("S1")] = 340.0
    hot[temperature_id("S2")] = 300.0
    assert row_values(spec, hot)[row_id("U-MIX", "MIX-energy")] > 0.0

    # Both inlets at the reference temperature carry zero enthalpy flow (h^L(T_r, P_r) = 0),
    # so a warm outlet makes the residual negative. The fixture gives each inlet the outlet's
    # full flow, so the inlet sum would otherwise always dominate.
    cold = mixer_state(spec)
    cold[temperature_id("S1")] = 300.0
    cold[temperature_id("S6")] = 300.0
    cold[temperature_id("S2")] = 340.0
    assert row_values(spec, cold)[row_id("U-MIX", "MIX-energy")] < 0.0


def test_mix_energy_vanishes_at_the_reference_mix(reference_values: Mapping[str, Any]) -> None:
    """The registered nominal state, with Fable's T_mix: the closure is satisfied there."""
    case = variants(reference_values)["SYN-001-nominal"]
    recycle = recycle_of(case)
    spec = build_mixer_spec()
    state = {name: 0.0 for name in spec.variable_ids}
    for stream in MIX_STREAMS:
        state[pressure_id(stream)] = 100_000.0
    state[temperature_id("S1")] = 300.0
    state[temperature_id("S6")] = float(case["T_flash_K"])
    state[temperature_id("S2")] = float(case["T_mix_K"])
    for index, component in enumerate(COMPONENTS):
        state[flow_id("S1", component)] = FRESH_FEED.n[index]
        state[flow_id("S6", component)] = recycle.n[index]
        state[flow_id("S2", component)] = FRESH_FEED.n[index] + recycle.n[index]
    rows = row_values(spec, state)
    # Registered energy tolerance, ADR 0001 D6.
    assert rows[row_id("U-MIX", "MIX-energy")] == pytest.approx(0.0, abs=1e-5 + 1e-8 * 1e5)
    for component in COMPONENTS:
        assert rows[row_id("U-MIX", "MIX-mole", component)] == 0.0
    assert rows[row_id("U-MIX", "MIX-pressure", "0")] == 0.0
    assert rows[row_id("U-MIX", "MIX-pressure", "1")] == 0.0


def test_the_mixer_authors_one_pressure_row_per_inlet() -> None:
    """`P_in(k) - P_out = 0` for every inlet k, not one row for the first one."""
    spec = build_mixer_spec()
    state = mixer_state(spec)
    state[pressure_id("S6")] = 90_000.0
    rows = row_values(spec, state)
    assert rows[row_id("U-MIX", "MIX-pressure", "0")] == 0.0
    assert rows[row_id("U-MIX", "MIX-pressure", "1")] == -10_000.0


def test_mix_dormant_inlet_authors_no_row_and_says_so() -> None:
    """A declared equation with no residual is legitimate only when the model declares it."""
    spec = build_mixer_spec()
    produced = {equation.origin for equation in spec.equations}
    declared = {origin(MIXER.model_id, eq.equation_id) for eq in MIXER.declared_equations()}
    behavioural = {origin(MIXER.model_id, name) for name in BEHAVIOURAL_EQUATIONS}
    assert produced == declared - behavioural
    assert behavioural == {origin(MIXER.model_id, "MIX-dormant-inlet")}


def test_the_mixer_owns_no_variable_because_it_is_adiabatic() -> None:
    """No duty port, no duty variable, no source term in MIX-energy."""
    contribution = MIXER.contribute(MIX_WIRING["U-MIX"], COMPONENTS)
    assert contribution.variable_ids == ()
    assert contribution.parameter_ids == ()
    assert not any(port.kind == "energy" for port in MIXER.ports())


def test_the_registered_recycle_is_saturated_and_the_label_disagrees_with_the_reference(
    reference_values: Mapping[str, Any],
) -> None:
    """A measured finding, pinned so it cannot be rediscovered by accident.

    The SYN-001 recycle is the flash's own liquid at the flash temperature, so it sits exactly on
    its bubble point. In double precision `sum_i z_i K_i` evaluates to 1.0000000000000002 and the
    provider — correctly, by its registered classification order — calls the stream `TWO_PHASE`
    with a vapour fraction of about 1.3e-17. Fable's 20-digit reference registers the same stream
    as `LIQUID`.

    Both are right at their own precision. The consequence is that a unit which gates on the
    phase *label* rejects the nominal registered variant, which is why the mixer gates on the
    enthalpy instead. K03's phase-attempt controller will meet the same boundary.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    assert case["recycle_phase_signature"] == "LIQUID"

    recycle = recycle_of(case)
    from openflowsheet.models.syn001.tp_state import tp_state

    state = tp_state(PROVIDER, recycle, CONTEXT)
    assert state.phase_signature == "TWO_PHASE"
    assert state.vapor_fraction is not None
    assert 0.0 < state.vapor_fraction < 1e-15

    # And the enthalpy consequence, which is what the mixer actually gates on.
    from openflowsheet.models.syn001.tp_state import enthalpy_flow

    status, liquid, _ = enthalpy_flow(PROVIDER, recycle, "LIQUID", COMPONENTS, CONTEXT)
    assert status == "ok"
    assert state.enthalpy_flow is not None
    assert abs(state.enthalpy_flow - liquid) < 1e-9
    # Fable's registered value for this stream, which is the liquid enthalpy.
    assert liquid == pytest.approx(float(case["H_recycle_W"]), abs=1e-5 + 1e-8 * 1e5)


def test_an_inlet_carrying_real_latent_heat_is_still_refused() -> None:
    """The admissibility bound is a registered tolerance, not a licence to ignore a vapour phase.

    An equimolar feed at 350 K is above its 347.44 K bubble point and carries about 8.5 kW of
    latent heat at 3 mol/s — seven orders of magnitude past the bound the saturated recycle
    misses by.
    """
    boiling = StreamState(n=(1.0, 1.0, 1.0), temperature=350.0, pressure=100_000.0)
    result = MIXER.evaluate({"inlet": (boiling, FRESH_FEED)}, CONTEXT)
    assert result.status == "unsupported"
    assert "T05" in result.message
    assert result.outlets == {}


def test_the_admissibility_bound_is_the_registered_temperature_tolerance() -> None:
    """A barely-boiling inlet, measured against the bound that actually applies.

    The equimolar feed boils at 347.44118 K. At 347.45 K its vapour fraction is 3.65e-4 and
    treating it as liquid loses 29.4 W, which at this throughput's dH/dT of 300 W/K is an
    outlet temperature wrong by about 0.098 K — five orders of magnitude past ADR 0001 D6's
    registered 1e-6 K.
    """
    from openflowsheet.models.syn001.tp_state import enthalpy_flow, tp_state

    barely = StreamState(n=(1.0, 1.0, 1.0), temperature=347.45, pressure=100_000.0)
    state = tp_state(PROVIDER, barely, CONTEXT)
    status, liquid, _ = enthalpy_flow(PROVIDER, barely, "LIQUID", COMPONENTS, CONTEXT)
    assert status == "ok"
    assert state.enthalpy_flow is not None
    gap = abs(state.enthalpy_flow - liquid)
    assert 1.0 < gap < 1000.0, f"the discriminating case moved: gap is now {gap} W"

    result = MIXER.evaluate({"inlet": (barely, FRESH_FEED)}, CONTEXT)
    assert result.status == "unsupported"
    assert "T05" in result.message


class DecreasingEnthalpyProvider:
    """A provider whose liquid enthalpy *falls* with temperature.

    Physically absurd and deliberately so: it breaks the one assumption the inlet-temperature
    bracket rests on, which is the only way to reach the closure's non-convergence path without
    waiting for a solver to misbehave. The point is that the mixer says so rather than returning
    whatever the bracket happened to hold.
    """

    def __init__(self) -> None:
        self.inner = Syn001Provider()

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        real = self.inner.evaluate_phase(request, context)
        if real.status != "ok":
            return real
        values = {name: -value for name, value in real.values.items()}
        derivatives = {
            name: {key: -value for key, value in entry.items()}
            for name, entry in real.derivatives.items()
        }
        return PropertyResult(
            status="ok",
            phase_signature=real.phase_signature,
            values=values,
            derivatives=derivatives,
            provider_id=real.provider_id,
            reference_convention=real.reference_convention,
        )

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return self.inner.flash(request, context)


def test_a_closure_that_cannot_be_bracketed_is_reported_not_answered() -> None:
    """`not_converged`, with the bracket values in the message.

    Never a midpoint dressed as a root.
    """
    mixer = AdiabaticMixer(unit_id="U-MIX", provider=DecreasingEnthalpyProvider(), context=CONTEXT)
    warm = StreamState(n=(1.0, 1.0, 1.0), temperature=330.0, pressure=100_000.0)
    result = mixer.evaluate({"inlet": (FRESH_FEED, warm)}, CONTEXT)
    assert result.status == "not_converged"
    assert "bracket" in result.message
    assert result.outlets == {}
    assert result.duty is None


def test_the_admissibility_criterion_is_intensive_not_extensive() -> None:
    """The defect the Fable review of K02 measured, kept measured.

    The first version of this check bounded the enthalpy gap in **watts** against the registered
    energy tolerance. That is an extensive bound on an intensive question: it passes whenever
    the throughput is small enough. At 1e-8 mol/s a 45%-vapour inlet carries only 3.8e-4 W of
    latent heat, sails under a 1.01e-3 W bound, and the mixer returned `ok`, `LIQUID` and an
    outlet temperature of 330.0 K where the true liquid closure gives 393.9 K — a plausible
    wrong number, 64 K out.

    The criterion now converts the gap to the temperature error it would cause and compares
    against the registered 1e-6 K, so the same stream is refused at every throughput.
    """
    tiny = 1e-8
    boiling = StreamState(n=(tiny, tiny, tiny), temperature=360.0, pressure=100_000.0)
    cold = StreamState(n=(tiny, tiny, tiny), temperature=300.0, pressure=100_000.0)

    from openflowsheet.models.syn001.tp_state import enthalpy_flow, tp_state

    state = tp_state(PROVIDER, boiling, CONTEXT)
    status, liquid, _ = enthalpy_flow(PROVIDER, boiling, "LIQUID", COMPONENTS, CONTEXT)
    assert status == "ok"
    assert state.vapor_fraction is not None and state.vapor_fraction > 0.4
    gap = abs(state.enthalpy_flow - liquid)  # type: ignore[operator]
    assert gap < 1e-5 + 1e-8 * 1e5, (
        "this case only discriminates while the gap is under the old energy bound; "
        f"it is now {gap} W"
    )

    result = MIXER.evaluate({"inlet": (boiling, cold)}, CONTEXT)
    assert result.status == "unsupported"
    assert result.outlets == {}


def test_the_same_stream_is_judged_the_same_way_at_any_throughput() -> None:
    """Intensive means scale-free: the verdict must not depend on how much is flowing."""
    for scale in (1e-8, 1e-3, 1.0, 1e3):
        hot = StreamState(n=(scale, scale, scale), temperature=350.0, pressure=100_000.0)
        cold = StreamState(n=(scale, scale, scale), temperature=300.0, pressure=100_000.0)
        assert MIXER.evaluate({"inlet": (hot, cold)}, CONTEXT).status == "unsupported", scale
        both_cold = StreamState(n=(scale, scale, scale), temperature=310.0, pressure=100_000.0)
        assert MIXER.evaluate({"inlet": (both_cold, cold)}, CONTEXT).status == "ok", scale


def test_the_heater_and_the_mixer_agree_about_what_is_liquid() -> None:
    """They share one criterion, so neither can refuse what the other admits.

    Before the Fable review of K02 the heater compared phase *labels* while the mixer compared
    enthalpies, so the heater would have refused the registered saturated recycle that the mixer
    accepts. The flowsheet never put the recycle into the heater, so nothing caught it.
    """
    from openflowsheet.models.syn001.heater import TPHeater

    recycle = StreamState(
        n=(0.29777671393051394767, 0.54639697692561612246, 0.79501723992071829724),
        temperature=360.0,
        pressure=100_000.0,
    )
    heater = TPHeater(
        unit_id="U-HEAT",
        provider=PROVIDER,
        outlet_temperature=365.0,
        context=CONTEXT,
        inlet_phase="LIQUID",
    )
    assert heater.evaluate({"inlet": (recycle,)}, CONTEXT).status == "ok"
    assert MIXER.evaluate({"inlet": (recycle, FRESH_FEED)}, CONTEXT).status == "ok"

    boiling = StreamState(n=(1.0, 1.0, 1.0), temperature=350.0, pressure=100_000.0)
    assert heater.evaluate({"inlet": (boiling,)}, CONTEXT).status == "unsupported"
    assert MIXER.evaluate({"inlet": (boiling, FRESH_FEED)}, CONTEXT).status == "unsupported"


def test_the_bound_is_the_registered_tolerance_and_not_a_looser_one() -> None:
    """A stream measured to sit between the registered 1e-6 K and a bound a thousand times wider.

    Anti-vacuity for the bound itself. Every other case in this file is far to one side or the
    other, so widening the tolerance by a factor of a thousand would leave them all passing —
    measured, in a mutation sweep, before this test existed.

    The equimolar feed boils at 347.44118198 K. Two hundredths of a millikelvin above that, at
    347.4412 K, its vapour fraction is small enough that treating it as liquid costs an outlet
    temperature error of 2.0e-4 K: two hundred times the registered bound, and five times
    *inside* a bound a thousand times wider.
    """
    from openflowsheet.models.syn001.tp_state import single_phase_admissible

    marginal = StreamState(n=(1.0, 1.0, 1.0), temperature=347.4412, pressure=100_000.0)
    admissible, _, equivalent, status, _ = single_phase_admissible(
        PROVIDER, marginal, "LIQUID", COMPONENTS, CONTEXT
    )
    assert status == "ok"
    assert 1e-6 < equivalent < 1e-3, (
        f"the discriminating case moved: the equivalent error is now {equivalent} K, which no "
        "longer separates the registered bound from a thousandfold one"
    )
    assert not admissible

    result = MIXER.evaluate({"inlet": (marginal, FRESH_FEED)}, CONTEXT)
    assert result.status == "unsupported"
    assert result.outlets == {}


def test_a_stream_just_inside_the_registered_bound_is_admitted() -> None:
    """The other side of the same edge, so the bound is pinned from both directions.

    Without this, refusing everything would pass the test above.
    """
    from openflowsheet.models.syn001.tp_state import single_phase_admissible

    subcooled = StreamState(n=(1.0, 1.0, 1.0), temperature=347.441, pressure=100_000.0)
    admissible, _, equivalent, status, _ = single_phase_admissible(
        PROVIDER, subcooled, "LIQUID", COMPONENTS, CONTEXT
    )
    assert status == "ok"
    assert equivalent <= 1e-6
    assert admissible
    assert MIXER.evaluate({"inlet": (subcooled, FRESH_FEED)}, CONTEXT).status == "ok"
