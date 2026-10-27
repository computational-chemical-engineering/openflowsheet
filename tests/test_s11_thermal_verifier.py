"""S11 WO-C5: the verifier's `thermal.*` rows and saturated streams (S11 units design §4.8).

The functions of `verify.thermal` are called directly (they enter the table at I1b) on states the
C2/C3 units produce: each test binds a revision with the C4 builders (the binder's tables since
I1b), runs
the units' own `evaluate` in order, and judges that state with a fresh provider. S11.A64's check
set on these states, A65's mutations, A66's independence from `models.thermal.kernel`.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest
from m02_c1_support import connection, revision
from test_s11_thermal_binding import (
    dimensionless,
    duty,
    feed,
    instance,
    outlet_pressure,
    outlet_temperature,
    pascal,
)
from test_s11_thermal_machines import ADDITIVE_STATES, CP, _closed_form, _IdealGas

from openflowsheet.application.revision_binding import (
    _CONTEXT,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import IAPWS95_RECORDS, RevisionView, parse_revision
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.thermal import kernel
from openflowsheet.models.thermal.state import liquid_id, vapor_id
from openflowsheet.thermo import PropertyProvider, StreamState
from openflowsheet.thermo.iapws95 import Iapws95Provider
from openflowsheet.verify import CheckResult
from openflowsheet.verify import thermal as vt
from openflowsheet.verify.checks import KIND_TOLERANCE, qualification
from openflowsheet.verify.forms import declared_phases, stream_admissibility
from openflowsheet.verify.table import Unit

TAU_FLOW = KIND_TOLERANCE["molar_flow"]
CONTEXT = _CONTEXT


# -- documents: the C6 cases' unit chains, evaluated once by the units themselves ----------------


def _document(
    instances: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    specifications: list[dict[str, Any]],
) -> dict[str, Any]:
    return revision(
        instances,
        connections,
        specifications,
        components=("H2O",),
        record_source=IAPWS95_RECORDS,
        revision_id="S11-THERMAL-VERIFY-r1",
    )


def rankine() -> dict[str, Any]:
    """TH-C1's chain (S11.A59): liquid at 10 kPa, 318.15 K → pump (3 MPa, 0.75) → boiler (T,
    673.15 K, vapour) → turbine (10 kPa, 0.85, wet) → condenser (quality 0) → sink."""
    return _document(
        [
            instance("F", "syn001.feed_source"),
            instance("P", "thermal.pump", {"efficiency": dimensionless(0.75)}),
            instance("B", "thermal.heater"),
            instance("T", "thermal.turbine", {"efficiency": dimensionless(0.85)}),
            instance("C", "thermal.heater", {"outlet_vapor_fraction": dimensionless(0.0)}),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("P", "inlet"), "liquid"),
            connection("S2", ("P", "outlet"), ("B", "inlet"), "liquid"),
            connection("S3", ("B", "outlet"), ("T", "inlet"), "vapor"),
            connection("S4", ("T", "outlet"), ("C", "inlet"), "vapor_liquid"),
            connection("S5", ("C", "outlet"), ("K", "inlet"), "vapor_liquid"),
        ],
        [
            *feed("S1", "H2O", 318.15, 1.0e4),
            outlet_pressure("P", 3.0e6),
            outlet_temperature("B", 673.15),
            outlet_pressure("T", 1.0e4),
        ],
    )


def valve_drum() -> dict[str, Any]:
    """TH-V1's chain: liquid at 1 MPa, 450 K → valve (0.2 MPa, wet) → drum (Q = 0) → sinks."""
    return _document(
        [
            instance("F", "syn001.feed_source"),
            instance("V", "thermal.valve"),
            instance("D", "thermal.flash", {"pressure_drop": pascal(0.0)}),
            instance("K1", "syn001.product_sink"),
            instance("K2", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("V", "inlet"), "liquid"),
            connection("S2", ("V", "outlet"), ("D", "inlet"), "vapor_liquid"),
            connection("S3", ("D", "vapor"), ("K1", "inlet"), "vapor_liquid"),
            connection("S4", ("D", "liquid"), ("K2", "inlet"), "vapor_liquid"),
        ],
        [*feed("S1", "H2O", 450.0, 1.0e6), outlet_pressure("V", 2.0e5), duty("D", 0.0)],
    )


def mixer_compressor() -> dict[str, Any]:
    """Two vapour feeds at 1 bar → mixer → compressor (3 bar, 0.8) → heater (duty) → sink."""
    return _document(
        [
            instance("F1", "syn001.feed_source"),
            instance("F2", "syn001.feed_source"),
            instance("M", "thermal.mixer"),
            instance("G", "thermal.compressor", {"efficiency": dimensionless(0.8)}),
            instance("H", "thermal.heater", {"pressure_drop": pascal(1.0e3)}),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F1", "outlet"), ("M", "inlet"), "vapor"),
            connection("S2", ("F2", "outlet"), ("M", "inlet"), "vapor"),
            connection("S3", ("M", "outlet"), ("G", "inlet"), "vapor"),
            connection("S4", ("G", "outlet"), ("H", "inlet"), "vapor"),
            connection("S5", ("H", "outlet"), ("K", "inlet"), "vapor"),
        ],
        [
            *feed("S1", "H2O", 400.0, 1.0e5),
            *feed("S2", "H2O", 450.0, 1.0e5),
            outlet_pressure("G", 3.0e5),
            duty("H", -500.0),
        ],
    )


CASES: Mapping[str, Callable[[], dict[str, Any]]] = {
    "rankine": rankine,
    "valve_drum": valve_drum,
    "mixer_compressor": mixer_compressor,
}


def evaluated_state(document: Mapping[str, Any]) -> dict[str, float]:
    """The units' own sequential evaluation (instances are listed upstream first), as x_final's
    columns: every stream's (n, T, P), the owned carried splits, the duties and works."""
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    components = binding.flowsheet.components
    streams: dict[str, StreamState] = {}
    state: dict[str, float] = {}
    for unit in binding.flowsheet.units():
        wiring = binding.flowsheet.wiring[unit.unit_id].streams
        inlets = {"inlet": [streams[s] for s in wiring["inlet"]]} if "inlet" in wiring else {}
        answer = unit.evaluate(inlets, CONTEXT)
        assert answer.status == "ok", (unit.unit_id, answer.message)
        for port, outlet in answer.outlets.items():
            (stream,) = wiring[port]
            streams[stream] = outlet
        state.update(getattr(answer, "owned", {}))
        if answer.duty is not None:
            state[duty_id(unit.unit_id)] = answer.duty
        if answer.work is not None:
            state[work_id(unit.unit_id)] = answer.work
    for stream, carried in streams.items():
        for component, flow in zip(components, carried.n, strict=True):
            state[flow_id(stream, component)] = flow
        state[temperature_id(stream)] = carried.temperature
        state[pressure_id(stream)] = carried.pressure
    return state


def verifier_checks(
    view: RevisionView, state: Mapping[str, float], provider: PropertyProvider | None = None
) -> list[CheckResult]:
    """The thermal rows, the saturated streams' checks and the single-phase admissibility, with
    a fresh provider (IAPWS-95 unless given), as the I1b hook will assemble them."""
    provider = Iapws95Provider() if provider is None else provider
    note = qualification(provider)
    enthalpy, notes = vt.enthalpy_map(view, state, provider, CONTEXT)
    checks: list[CheckResult] = []
    for instance_view in view.instances:
        entry = vt.MODEL_CHECKS.get(instance_view.model_id)
        if entry is None:
            continue
        unit = Unit(
            view=instance_view,
            state=state,
            enthalpy=enthalpy,
            tolerances=KIND_TOLERANCE,
            energy_note=note,
            provider=provider,
            context=CONTEXT,
            notes=notes,
            components=tuple(view.components),
        )
        for rule in (entry.material, entry.energy, entry.specification, entry.bounds):
            checks += rule(unit, view.components)
    checks += vt.saturated_stream_checks(view, state, provider, CONTEXT, KIND_TOLERANCE, note)
    checks += stream_admissibility(view, declared_phases(view), state, provider, CONTEXT, note)
    return checks


def by_id(checks: Sequence[CheckResult]) -> dict[str, CheckResult]:
    found = {check.id: check for check in checks}
    assert len(found) == len(checks), "duplicate check ids"
    return found


@pytest.fixture
def judged() -> Any:
    """Returns `(view, state, checks)` for a case name."""

    def judge(case: str) -> tuple[RevisionView, dict[str, float], dict[str, CheckResult]]:
        document = CASES[case]()
        state = evaluated_state(document)
        view = parse_revision(document)
        return view, state, by_id(verifier_checks(view, state))

    return judge


# -- S11.A64 on the C2/C3 states -----------------------------------------------------------------

EXPECTED_SATURATED = {
    "rankine": ("S4", "S5"),
    "valve_drum": ("S2", "S3", "S4"),
    "mixer_compressor": (),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_a64_every_check_passes_on_the_units_state(judged: Any, case: str) -> None:
    view, _, checks = judged(case)
    assert vt.saturated_streams(view) == EXPECTED_SATURATED[case]
    for check in checks.values():
        if check.category == "independent_split":
            assert (check.result, check.reason) == ("not_applicable", "temperature_degenerate")
            continue
        assert check.result == "pass", (check.id, check.result, check.value, check.reason)
    for stream in EXPECTED_SATURATED[case]:
        assert checks[f"phase_admissibility.stream.{stream}.saturation"].result == "pass"
        assert checks[f"phase_admissibility.stream.{stream}.fraction"].result == "pass"


def test_a64_the_expected_rows_are_present(judged: Any) -> None:
    _, _, checks = judged("rankine")
    for identifier in (
        "material_balance.P.H2O",
        "energy_balance.P",
        "specification.P.P",
        "specification.P.isentropic_work",
        "bounds_and_domain.P.direction",
        "bounds_and_domain.P.work_sign",
        "bounds_and_domain.P.efficiency",
        "specification.B.T",
        "specification.B.P",
        "specification.T.isentropic_work",
        "specification.C.vapor_fraction",
        "independent_split.S4",
    ):
        assert identifier in checks, identifier
    _, _, drum_checks = judged("valve_drum")
    for identifier in (
        "specification.D.duty",
        "specification.D.P.vapor",
        "specification.D.P.liquid",
        "specification.D.vapor_fraction.vapor",
        "specification.D.vapor_fraction.liquid",
        "bounds_and_domain.V.direction",
        "specification.V.P",
    ):
        assert identifier in drum_checks, identifier
    _, _, mixed = judged("mixer_compressor")
    assert {"specification.M.P.0", "specification.M.P.1", "specification.H.duty"} <= set(mixed)


def test_a64_energy_checks_reading_a_saturated_stream_carry_the_qualification(
    judged: Any,
) -> None:
    _, _, checks = judged("rankine")
    for unit in ("T", "C"):
        text = checks[f"energy_balance.{unit}"].independence_qualification
        assert text is not None
        assert "; enthalpy of S4 from its carried split (ADR 0051 D2)" in text
    boiler = checks["energy_balance.B"].independence_qualification
    assert boiler is not None and "carried split" not in boiler


# -- S11.A65 mutations ---------------------------------------------------------------------------


def _mutated(judged: Any, change: Callable[[dict[str, float]], None]) -> dict[str, CheckResult]:
    view, state, _ = judged("rankine")
    changed = dict(state)
    change(changed)
    return by_id(verifier_checks(view, changed))


def test_a65_moving_vapour_into_liquid_fails_both_energy_balances(judged: Any) -> None:
    def shift(state: dict[str, float]) -> None:
        state[vapor_id("S4")] += 10 * TAU_FLOW
        state[liquid_id("S4")] -= 10 * TAU_FLOW

    checks = _mutated(judged, shift)
    assert checks["energy_balance.T"].result == "fail"
    assert checks["energy_balance.C"].result == "fail"
    assert checks["phase_admissibility.stream.S4.fraction"].result == "pass"


def test_a65_a_saturated_temperature_off_the_line_fails_saturation(judged: Any) -> None:
    def warm(state: dict[str, float]) -> None:
        state[temperature_id("S4")] += 2e-6

    checks = _mutated(judged, warm)
    assert checks["phase_admissibility.stream.S4.saturation"].result == "fail"


def test_a65_turbine_work_off_by_a_millionth_fails_the_isentropic_work(judged: Any) -> None:
    def scale(state: dict[str, float]) -> None:
        state[work_id("T")] *= 1 + 1e-6

    checks = _mutated(judged, scale)
    check = checks["specification.T.isentropic_work"]
    assert check.result == "fail"
    assert check.value is not None and abs(check.value) > 10 * KIND_TOLERANCE["heat_rate"]


# -- S11.A66 independence ------------------------------------------------------------------------


def test_a66_the_checks_do_not_call_the_kernel(
    judged: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    view, state, before = judged("rankine")

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the verifier called models.thermal.kernel")

    for name, value in vars(kernel).items():
        if callable(value) and getattr(value, "__module__", None) == kernel.__name__:
            monkeypatch.setattr(kernel, name, refuse)
    after = by_id(verifier_checks(view, state))
    assert after == before


# -- the verifier's own isentropic state ---------------------------------------------------------


def test_the_verifiers_isentropic_states_agree_with_the_units(judged: Any) -> None:
    """The units' work relations hold at the verifier's own Ḣ_s: the isentropic_work values are
    the difference of two independent isentropic solves, far inside τ_E."""
    _, _, checks = judged("rankine")
    for unit in ("P", "T"):
        value = checks[f"specification.{unit}.isentropic_work"].value
        assert value is not None and abs(value) < 1e-6
    _, _, mixed = judged("mixer_compressor")
    value = mixed["specification.G.isentropic_work"].value
    assert value is not None and abs(value) < 1e-6


def test_a_single_phase_side_without_the_root_is_refused() -> None:
    """Saturated steam at 3 MPa expanded to 10 kPa is wet: no vapour root, and a saturated side
    asked for a superheated isentropic state has beta_s > 1."""
    provider = Iapws95Provider()
    t_sat = vt._saturation_temperature(provider, CONTEXT, 3.0e6)
    s_vapor = vt._properties(provider, CONTEXT, t_sat, 3.0e6, "VAPOR", ("s",))["s"]
    with pytest.raises(vt.IsentropicStateError, match="is not VAPOR"):
        vt.isentropic_enthalpy(provider, CONTEXT, s_vapor, 1.0e4, "VAPOR")
    s_hot = vt._properties(provider, CONTEXT, 673.15, 3.0e6, "VAPOR", ("s",))["s"]
    with pytest.raises(vt.IsentropicStateError, match="beta_s"):
        vt.isentropic_enthalpy(provider, CONTEXT, s_hot, 2.0e6, None)


def test_a_dormant_saturated_stream(judged: Any) -> None:
    """At zero flow `.saturation` is not applicable and `.fraction` is still judged: V = −L ≠ 0,
    which a nonzero duty would force (§4.9), fails it."""
    view, state, _ = judged("rankine")
    dormant_state = dict(state)
    for stream in ("S4",):
        dormant_state[flow_id(stream, "H2O")] = 0.0
        dormant_state[vapor_id(stream)] = 0.0
        dormant_state[liquid_id(stream)] = 0.0
    checks = by_id(
        vt.saturated_stream_checks(
            view, dormant_state, Iapws95Provider(), CONTEXT, KIND_TOLERANCE, "note"
        )
    )
    assert checks["phase_admissibility.stream.S4.saturation"].result == "not_applicable"
    assert checks["phase_admissibility.stream.S4.fraction"].result == "pass"
    dormant_state[vapor_id("S4")] = 1e-3
    dormant_state[liquid_id("S4")] = -1e-3
    checks = by_id(
        vt.saturated_stream_checks(
            view, dormant_state, Iapws95Provider(), CONTEXT, KIND_TOLERANCE, "note"
        )
    )
    assert checks["phase_admissibility.stream.S4.fraction"].result == "fail"


# -- the additive-vapour (Wilson) isentropic enthalpy flow, the verifier's own (S11.A80) ----------


def test_the_additive_isentropic_enthalpy_is_the_ideal_gas_isentrope() -> None:
    """`vt.additive_isentropic_enthalpy` against the closed-form isentrope of a constant-c_p ideal
    gas (the fake `test_s11_thermal_machines` uses for the block): T_s within the bisection's
    floor, a bracket of 4ε·T_s, so Ḣ_s within Σ n_j c_p,j · 4ε·T_s plus rounding, 8ε·|Ḣ_s|
    (measured: worst |ΔḢ_s| 2.9e-11 W)."""
    gas = _IdealGas(("A", "B", "C"))
    for state in ADDITIVE_STATES:
        *flows, t_in, p_in, p_out = state
        t_s, expected = _closed_form(state)
        found = vt.additive_isentropic_enthalpy(gas, CONTEXT, flows, t_in, p_in, p_out)
        slope = sum(n * CP[name] for n, name in zip(flows, ("A", "B", "C"), strict=True))
        floor = slope * 4.0 * sys.float_info.epsilon * t_s
        assert abs(found - expected) <= floor + 8.0 * sys.float_info.epsilon * max(
            abs(expected), 1.0e3
        ), (
            state,
            found - expected,
            floor,
        )


def test_an_additive_isentropic_state_outside_the_domain_is_refused() -> None:
    """A root at an end of the provider's T domain is not inside it: `IsentropicStateError`."""
    gas = _IdealGas(("A", "B", "C"))
    with pytest.raises(vt.IsentropicStateError, match="at an end of"):
        vt.additive_isentropic_enthalpy(gas, CONTEXT, (0.2, 0.5, 0.3), 1900.0, 1.0e5, 1.0e6)
