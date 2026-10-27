"""S11 WO-C4: the `thermal.*` builders through `bind_revision_flowsheet` (S11 units design §4.4).

The seven builders, signatures and bases (`application.thermal_binding`) enter the binder's tables
at I1b; here each test registers them in monkeypatched tables, as `test_m02_wo8_region` does.
Every admitted mode and form binds to a square `ProblemSpec`, and every bind refusal of §4.4 gives
its code and hint. CoolProp cases skip cleanly without the extra.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from m02_c1_support import connection, quantity, revision, specification

from openflowsheet.application import revision_binding, thermal_binding
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import (
    COOLPROP_RECORDS,
    IAPWS95_RECORDS,
    InstanceView,
    RevisionError,
    required_kind,
)
from openflowsheet.models.thermal.flash import ThermalFlash
from openflowsheet.models.thermal.heater import ThermalHeater
from openflowsheet.models.thermal.machines import ThermalMachine
from openflowsheet.models.thermal.mixer import ThermalMixer
from openflowsheet.models.thermal.valve import ThermalValve

needs_coolprop = pytest.mark.skipif(
    importlib.util.find_spec("CoolProp") is None,
    reason="the coolprop extra is not installed (CoolProp==8.0.0)",
)

THERMAL = (
    "thermal.heater",
    "thermal.valve",
    "thermal.mixer",
    "thermal.flash",
    "thermal.pump",
    "thermal.compressor",
    "thermal.turbine",
)
UNIT_CLASS: Mapping[str, type[Any]] = {
    "thermal.heater": ThermalHeater,
    "thermal.valve": ThermalValve,
    "thermal.mixer": ThermalMixer,
    "thermal.flash": ThermalFlash,
    "thermal.pump": ThermalMachine,
    "thermal.compressor": ThermalMachine,
    "thermal.turbine": ThermalMachine,
}
FORM = {"liquid": "LIQUID", "vapor": "VAPOR", "vapor_liquid": "SATURATED"}


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> None:
    register(monkeypatch)


def register(monkeypatch: pytest.MonkeyPatch) -> None:
    """The seven models in the binder's tables, as I1b will register them."""
    for model_id in THERMAL:
        monkeypatch.setitem(
            revision_binding.MODEL_BUILDERS,
            model_id,
            thermal_binding.BUILDERS[model_id],
        )
        monkeypatch.setitem(
            revision_binding.MODEL_SIGNATURES,
            model_id,
            thermal_binding.SIGNATURES[model_id],
        )
        monkeypatch.setitem(
            revision_binding.MODEL_BASES,
            model_id,
            thermal_binding.BASES[model_id],
        )


# -- documents -----------------------------------------------------------------------------------


def instance(unit: str, model: str, parameters: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": unit,
        "model": {"id": model, "version": "0.0.0-declared", "artifact_ref": None},
        "semantic_role": "other",
        "parameters": dict(parameters or {}),
        "policy": {"fidelity": "test", "validity": "test"},
    }


def dimensionless(value: float) -> dict[str, Any]:
    return quantity(value, "1", "dimensionless", [0] * 7)


def pascal(value: float) -> dict[str, Any]:
    return quantity(value, "Pa", "pressure", [-1, 1, -2, 0, 0, 0, 0])


def feed(stream: str, component: str, temperature: float, pressure: float) -> list[dict[str, Any]]:
    return [
        specification(
            f"SPEC-{stream}-n",
            "connection",
            stream,
            "state.n",
            1.0,
            "molar_flow",
            component=component,
        ),
        specification(
            f"SPEC-{stream}-T", "connection", stream, "state.T", temperature, "temperature"
        ),
        specification(f"SPEC-{stream}-P", "connection", stream, "state.P", pressure, "pressure"),
    ]


def outlet_temperature(unit: str, value: float) -> dict[str, Any]:
    return specification(f"SPEC-{unit}-T", "instance", unit, "outlet.T", value, "temperature")


def outlet_pressure(unit: str, value: float) -> dict[str, Any]:
    return specification(f"SPEC-{unit}-P", "instance", unit, "outlet.P", value, "pressure")


def duty(unit: str, value: float) -> dict[str, Any]:
    return specification(f"SPEC-{unit}-Q", "instance", unit, "duty.Q", value, "heat_rate")


#: The basis of each case: record source, the component, a liquid and a vapour feed state (T, P).
BASIS = {
    "iapws95": (IAPWS95_RECORDS, "H2O", (300.0, 1.0e5), (500.0, 1.0e5)),
    "coolprop": (COOLPROP_RECORDS, "CO2", (250.0, 5.0e6), (300.0, 1.0e5)),
}


def through(
    model: str,
    inlet: str,
    outlet: str,
    parameters: Mapping[str, Any] | None = None,
    specifications: Sequence[dict[str, Any]] = (),
    *,
    basis: str = "iapws95",
) -> dict[str, Any]:
    """F → U (`model`) → K, U's inlet declared `inlet` and its outlet `outlet`. A `vapor_liquid`
    inlet comes from a quality-mode heater H0 between F (liquid) and U, at beta 0.0 for a pump
    and 1.0 otherwise (§4.4's stated inlet beta)."""
    source, component, liquid, vapor = BASIS[basis]
    instances = [instance("F", "syn001.feed_source")]
    connections = []
    if inlet == "vapor_liquid":
        beta = 0.0 if model == "thermal.pump" else 1.0
        instances.append(
            instance("H0", "thermal.heater", {"outlet_vapor_fraction": dimensionless(beta)})
        )
        connections += [
            connection("S0", ("F", "outlet"), ("H0", "inlet"), "liquid"),
            connection("S1", ("H0", "outlet"), ("U", "inlet"), "vapor_liquid"),
        ]
        fed = feed("S0", component, *liquid)
    else:
        connections.append(connection("S1", ("F", "outlet"), ("U", "inlet"), inlet))
        fed = feed("S1", component, *(liquid if inlet == "liquid" else vapor))
    instances += [instance("U", model, parameters), instance("K", "syn001.product_sink")]
    connections.append(connection("S2", ("U", "outlet"), ("K", "inlet"), outlet))
    return revision(
        instances,
        connections,
        [*fed, *specifications],
        components=(component,),
        record_source=source,
        revision_id="S11-THERMAL-BIND-r1",
    )


def mixing(inlet: str, outlet: str) -> dict[str, Any]:
    """F1, F2 → M → K, both inlets declared `inlet` (R4: one phase per port)."""
    source, component, liquid, vapor = BASIS["iapws95"]
    state = liquid if inlet == "liquid" else vapor
    return revision(
        [
            instance("F1", "syn001.feed_source"),
            instance("F2", "syn001.feed_source"),
            instance("U", "thermal.mixer"),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F1", "outlet"), ("U", "inlet"), inlet),
            connection("S3", ("F2", "outlet"), ("U", "inlet"), inlet),
            connection("S2", ("U", "outlet"), ("K", "inlet"), outlet),
        ],
        [*feed("S1", component, *state), *feed("S3", component, *state)],
        components=(component,),
        record_source=source,
        revision_id="S11-THERMAL-BIND-r1",
    )


def drum(
    inlet: str = "liquid",
    vapor: str = "vapor_liquid",
    liquid: str = "vapor_liquid",
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """F → D (`thermal.flash`, Q pinned) → K1 (vapour), K2 (liquid)."""
    source, component, liquid_state, vapor_state = BASIS["iapws95"]
    state = liquid_state if inlet == "liquid" else vapor_state
    return revision(
        [
            instance("F", "syn001.feed_source"),
            instance(
                "U",
                "thermal.flash",
                {"pressure_drop": pascal(0.0)} if parameters is None else parameters,
            ),
            instance("K1", "syn001.product_sink"),
            instance("K2", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("U", "inlet"), inlet),
            connection("S2", ("U", "vapor"), ("K1", "inlet"), vapor),
            connection("S3", ("U", "liquid"), ("K2", "inlet"), liquid),
        ],
        [*feed("S1", component, *state), duty("U", 2.0e4)],
        components=(component,),
        record_source=source,
        revision_id="S11-THERMAL-BIND-r1",
    )


def bound(document: Mapping[str, Any], excess: int = 0) -> RevisionBinding:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    # Square: every unit's DOF statement of §4.4 holds within the flowsheet (feeds pin their
    # outlets; the sinks author nothing). A mixer's K inlets add K - 1 pressure rows (C2-4).
    assert len(binding.spec.equation_ids) == len(binding.spec.variable_ids) + excess
    return binding


def unit_of(binding: RevisionBinding, unit_id: str = "U") -> Any:
    (unit,) = (unit for unit in binding.flowsheet.units() if unit.unit_id == unit_id)
    return unit


def refused(document: Mapping[str, Any]) -> Unbound:
    answer = bind_revision_flowsheet(document)
    assert isinstance(answer, Unbound), answer
    return answer


# -- the tables ----------------------------------------------------------------------------------


def test_the_three_tables_name_the_seven_models() -> None:
    assert set(thermal_binding.SIGNATURES) == set(THERMAL)
    assert set(thermal_binding.BUILDERS) == set(THERMAL)
    assert set(thermal_binding.BASES) == set(THERMAL)
    assert all(
        bases == {"iapws95-v1", "coolprop-heos-v1"} for bases in thermal_binding.BASES.values()
    )


def test_until_i1b_the_binder_refuses_the_family() -> None:
    """Not registered on this branch: the binder's library-only refusal, as before S11 C4."""
    answer = refused(
        through("thermal.valve", "liquid", "liquid", None, [outlet_pressure("U", 5e4)])
    )
    assert answer == Unbound("unsupported", "model_unsupported(thermal.valve)")


def test_outlet_vapor_fraction_is_a_dimensionless_parameter() -> None:
    """Units design §2.4: the one `_PARAMETER_KINDS` entry S11 adds."""
    assert required_kind("parameters.outlet_vapor_fraction") == "dimensionless"


# -- every admitted mode and form binds ----------------------------------------------------------

HEATER_CASES = [
    pytest.param(
        "liquid",
        "liquid",
        {},
        [outlet_temperature("U", 350.0)],
        "outlet_temperature",
        id="T-liquid",
    ),
    pytest.param(
        "liquid", "vapor", {}, [outlet_temperature("U", 450.0)], "outlet_temperature", id="T-vapor"
    ),
    pytest.param("liquid", "liquid", {}, [duty("U", 1.0e3)], "duty", id="duty-liquid"),
    pytest.param("liquid", "vapor", {}, [duty("U", 5.0e4)], "duty", id="duty-vapor"),
    pytest.param("liquid", "vapor_liquid", {}, [duty("U", 3.0e4)], "duty", id="duty-saturated"),
    pytest.param(
        "liquid",
        "vapor_liquid",
        {"outlet_vapor_fraction": dimensionless(0.5)},
        [],
        "outlet_vapor_fraction",
        id="quality",
    ),
    pytest.param(
        "vapor",
        "vapor",
        {"pressure_drop": pascal(1.0e3)},
        [duty("U", 1.0e3)],
        "duty",
        id="duty-vapor-dP",
    ),
    pytest.param(
        "vapor_liquid",
        "vapor",
        {},
        [outlet_temperature("U", 450.0)],
        "outlet_temperature",
        id="saturated-in-T",
    ),
    pytest.param(
        "vapor_liquid",
        "vapor_liquid",
        {"outlet_vapor_fraction": dimensionless(0.0)},
        [],
        "outlet_vapor_fraction",
        id="saturated-in-quality",
    ),
]


@pytest.mark.parametrize(("inlet", "outlet", "parameters", "specs", "mode"), HEATER_CASES)
def test_heater_binds_every_mode_and_form(
    registered: None,
    inlet: str,
    outlet: str,
    parameters: dict[str, Any],
    specs: list[dict[str, Any]],
    mode: str,
) -> None:
    unit = unit_of(bound(through("thermal.heater", inlet, outlet, parameters, specs)))
    assert isinstance(unit, ThermalHeater)
    assert unit.mode == {"outlet_temperature": "T", "duty": "duty"}.get(mode, "quality")
    assert unit.forms == {"S1": FORM[inlet], "S2": FORM[outlet]}
    if "pressure_drop" in parameters:
        assert unit.pressure_drop == 1.0e3


def test_heater_quality_from_a_parameter_specification(registered: None) -> None:
    """A `role: fixed` specification of `parameters.outlet_vapor_fraction` lands on the
    parameter (R6), in the kind `_PARAMETER_KINDS` gives it."""
    beta = dict(
        specification(
            "SPEC-U-beta", "instance", "U", "parameters.outlet_vapor_fraction", 0.25, "molar_flow"
        )
    )
    beta.update(kind="dimensionless", unit="1", tolerance={"absolute": 1.0e-9})
    unit = unit_of(bound(through("thermal.heater", "liquid", "vapor_liquid", None, [beta])))
    assert unit.outlet_vapor_fraction == 0.25


@pytest.mark.parametrize(
    ("inlet", "outlet"),
    [
        ("liquid", "liquid"),
        ("liquid", "vapor_liquid"),
        ("vapor", "vapor"),
        ("vapor_liquid", "vapor_liquid"),
        ("vapor_liquid", "vapor"),
    ],
)
def test_valve_binds_every_form(registered: None, inlet: str, outlet: str) -> None:
    unit = unit_of(
        bound(through("thermal.valve", inlet, outlet, None, [outlet_pressure("U", 5e4)]))
    )
    assert isinstance(unit, ThermalValve)
    assert unit.outlet_pressure == 5e4
    assert unit.forms == {"S1": FORM[inlet], "S2": FORM[outlet]}


@pytest.mark.parametrize(
    ("inlet", "outlet"), [("liquid", "liquid"), ("liquid", "vapor_liquid"), ("vapor", "vapor")]
)
def test_mixer_binds_every_form(registered: None, inlet: str, outlet: str) -> None:
    unit = unit_of(bound(mixing(inlet, outlet), excess=1))
    assert isinstance(unit, ThermalMixer)
    assert unit.forms == {"S1": FORM[inlet], "S3": FORM[inlet], "S2": FORM[outlet]}


@pytest.mark.parametrize("inlet", ["liquid", "vapor"])
def test_flash_binds(registered: None, inlet: str) -> None:
    unit = unit_of(bound(drum(inlet)))
    assert isinstance(unit, ThermalFlash)
    assert (unit.duty, unit.pressure_drop) == (2.0e4, 0.0)
    assert unit.forms == {"S1": FORM[inlet], "S2": "SATURATED", "S3": "SATURATED"}


MACHINE_CASES = [
    pytest.param("thermal.pump", "liquid", "liquid", 3.0e6, id="pump"),
    pytest.param("thermal.pump", "vapor_liquid", "liquid", 3.0e6, id="pump-saturated-in"),
    pytest.param("thermal.compressor", "vapor", "vapor", 5.0e5, id="compressor"),
    pytest.param(
        "thermal.compressor", "vapor_liquid", "vapor", 5.0e5, id="compressor-saturated-in"
    ),
    pytest.param("thermal.turbine", "vapor", "vapor", 2.0e4, id="turbine"),
    pytest.param("thermal.turbine", "vapor", "vapor_liquid", 2.0e4, id="turbine-wet"),
    pytest.param("thermal.turbine", "vapor_liquid", "vapor", 2.0e4, id="turbine-saturated-in"),
    pytest.param(
        "thermal.turbine", "vapor_liquid", "vapor_liquid", 2.0e4, id="turbine-saturated-in-wet"
    ),
]


@pytest.mark.parametrize(("model", "inlet", "outlet", "pressure"), MACHINE_CASES)
def test_machines_bind_every_form(
    registered: None, model: str, inlet: str, outlet: str, pressure: float
) -> None:
    document = through(
        model, inlet, outlet, {"efficiency": dimensionless(0.8)}, [outlet_pressure("U", pressure)]
    )
    unit = unit_of(bound(document))
    assert isinstance(unit, ThermalMachine)
    assert (unit.model_id, unit.outlet_pressure, unit.efficiency) == (model, pressure, 0.8)
    assert unit.forms == {"S1": FORM[inlet], "S2": FORM[outlet]}
    # C4-3: a revision cannot choose the turbine's isentropic phase; it is the outlet's form.
    assert unit.isentropic_phase is None


@needs_coolprop
@pytest.mark.parametrize(
    ("model", "inlet", "outlet", "parameters", "specs"),
    [
        pytest.param(
            "thermal.compressor",
            "vapor",
            "vapor",
            {"efficiency": dimensionless(0.8)},
            [outlet_pressure("U", 5.0e5)],
            id="compressor",
        ),
        pytest.param(
            "thermal.valve",
            "liquid",
            "vapor_liquid",
            None,
            [outlet_pressure("U", 2.0e6)],
            id="valve",
        ),
        pytest.param(
            "thermal.heater",
            "vapor",
            "vapor_liquid",
            {"outlet_vapor_fraction": dimensionless(1.0)},
            [],
            id="heater",
        ),
    ],
)
def test_coolprop_basis_binds(
    registered: None,
    model: str,
    inlet: str,
    outlet: str,
    parameters: dict[str, Any] | None,
    specs: list[dict[str, Any]],
) -> None:
    unit = unit_of(bound(through(model, inlet, outlet, parameters, specs, basis="coolprop")))
    assert isinstance(unit, UNIT_CLASS[model])
    assert unit.provider.describe().provider_id == "coolprop-heos-v1"


def test_the_configuration_names_the_mode_and_forms(registered: None) -> None:
    """Two revisions that differ only in a declared form or the mode label differently."""
    labels = {
        bound(through("thermal.heater", "liquid", outlet, None, [duty("U", 1.0e3)])).spec.label
        for outlet in ("liquid", "vapor", "vapor_liquid")
    }
    assert len(labels) == 3


# -- the bind refusals of §4.4 -------------------------------------------------------------------

HEATER_HINT_T = (
    "a pure-fluid outlet at a specified temperature is single-phase; specify "
    "outlet_vapor_fraction or the duty"
)


@pytest.mark.parametrize(
    ("outlet", "parameters", "specs", "what", "hint"),
    [
        pytest.param(
            "vapor_liquid",
            {},
            [outlet_temperature("U", 372.0)],
            "outlet.T",
            HEATER_HINT_T,
            id="T-saturated",
        ),
        pytest.param(
            "liquid",
            {"outlet_vapor_fraction": dimensionless(0.0)},
            [],
            "outlet_vapor_fraction",
            "declare the outlet vapor_liquid",
            id="quality-liquid",
        ),
        pytest.param(
            "vapor",
            {"outlet_vapor_fraction": dimensionless(1.0)},
            [],
            "outlet_vapor_fraction",
            "declare the outlet vapor_liquid",
            id="quality-vapor",
        ),
        pytest.param(
            "vapor_liquid",
            {"outlet_vapor_fraction": dimensionless(1.5)},
            [],
            "outlet_vapor_fraction",
            "1.5 is outside [0, 1]",
            id="quality-above",
        ),
        pytest.param(
            "vapor_liquid",
            {"outlet_vapor_fraction": dimensionless(-0.25)},
            [],
            "outlet_vapor_fraction",
            "-0.25 is outside [0, 1]",
            id="quality-below",
        ),
    ],
)
def test_heater_refusals(
    registered: None,
    outlet: str,
    parameters: dict[str, Any],
    specs: list[dict[str, Any]],
    what: str,
    hint: str,
) -> None:
    answer = refused(through("thermal.heater", "liquid", outlet, parameters, specs))
    assert answer == Unbound("unsupported", f"specification_unsupported(U.{what})")
    assert answer.hint == hint


def test_heater_without_a_specification_is_missing(registered: None) -> None:
    answer = refused(through("thermal.heater", "liquid", "vapor_liquid"))
    assert answer == Unbound("incomplete", "specification_missing(U.specification)")
    assert answer.hint is not None
    assert answer.hint.startswith("Pin exactly one of: outlet_temperature: ")
    assert answer.hint.endswith(
        "; or give the parameter outlet_vapor_fraction (a vapor_liquid outlet)"
    )


@pytest.mark.parametrize(
    ("parameters", "specs"),
    [
        pytest.param({}, [outlet_temperature("U", 350.0), duty("U", 1.0)], id="T-duty"),
        pytest.param(
            {"outlet_vapor_fraction": dimensionless(0.5)}, [duty("U", 1.0)], id="duty-quality"
        ),
        pytest.param(
            {"outlet_vapor_fraction": dimensionless(0.5)},
            [outlet_temperature("U", 350.0)],
            id="T-quality",
        ),
    ],
)
def test_heater_with_two_specifications_conflicts(
    registered: None, parameters: dict[str, Any], specs: list[dict[str, Any]]
) -> None:
    answer = refused(through("thermal.heater", "liquid", "vapor_liquid", parameters, specs))
    assert answer == Unbound("conflict", "specification_conflict(U.specification)")


@pytest.mark.parametrize(
    ("vapor", "liquid", "port"),
    [("vapor", "vapor_liquid", "vapor"), ("vapor_liquid", "liquid", "liquid")],
)
def test_flash_products_must_be_saturated(
    registered: None, vapor: str, liquid: str, port: str
) -> None:
    answer = refused(drum(vapor=vapor, liquid=liquid))
    assert answer == Unbound("unsupported", f"specification_unsupported(U.{port})")
    assert answer.hint == "a drum's products are saturated (ADR 0051 D4)"


@pytest.mark.parametrize(
    ("model", "inlet", "outlet", "what", "hint"),
    [
        pytest.param(
            "thermal.pump",
            "vapor",
            "liquid",
            "inlet",
            "a pump's inlet is liquid or saturated (vapor_liquid at beta = 0.0), declared vapor",
            id="pump-inlet",
        ),
        pytest.param(
            "thermal.pump",
            "liquid",
            "vapor",
            "outlet",
            "a pump's outlet is liquid, declared vapor",
            id="pump-outlet-vapor",
        ),
        pytest.param(
            "thermal.pump",
            "liquid",
            "vapor_liquid",
            "outlet",
            "a pump's outlet is liquid, declared saturated",
            id="pump-outlet-saturated",
        ),
        pytest.param(
            "thermal.compressor",
            "liquid",
            "vapor",
            "inlet",
            "a compressor's inlet is vapor or saturated (vapor_liquid at beta = 1.0), "
            "declared liquid",
            id="compressor-inlet",
        ),
        pytest.param(
            "thermal.compressor",
            "vapor",
            "liquid",
            "outlet",
            "a compressor's outlet is vapor, declared liquid",
            id="compressor-outlet",
        ),
        pytest.param(
            "thermal.compressor",
            "vapor",
            "vapor_liquid",
            "outlet",
            "a compressor's outlet is vapor, declared saturated",
            id="compressor-outlet-saturated",
        ),
        pytest.param(
            "thermal.turbine",
            "liquid",
            "vapor",
            "inlet",
            "a turbine's inlet is vapor or saturated (vapor_liquid at beta = 1.0), declared liquid",
            id="turbine-inlet",
        ),
        pytest.param(
            "thermal.turbine",
            "vapor",
            "liquid",
            "outlet",
            "a turbine's outlet is vapor or saturated, declared liquid",
            id="turbine-outlet",
        ),
    ],
)
def test_machine_port_refusals(
    registered: None, model: str, inlet: str, outlet: str, what: str, hint: str
) -> None:
    document = through(
        model, inlet, outlet, {"efficiency": dimensionless(0.8)}, [outlet_pressure("U", 1.0e5)]
    )
    answer = refused(document)
    assert answer == Unbound("unsupported", f"specification_unsupported(U.{what})")
    assert answer.hint == hint


def test_the_turbine_takes_no_isentropic_phase_parameter(registered: None) -> None:
    """C4-3: `isentropic_phase` is a choice of words, which a Quantity parameter cannot carry; a
    parameter of that name is refused as any parameter the model does not read."""
    document = through(
        "thermal.turbine",
        "vapor",
        "vapor_liquid",
        {"efficiency": dimensionless(0.8), "isentropic_phase": dimensionless(1.0)},
        [outlet_pressure("U", 2.0e4)],
    )
    assert refused(document) == Unbound("unsupported", "parameter_unsupported(U.isentropic_phase)")


def _wilson_v2() -> Any:
    """A provider that only describes itself as `wilson-ig-v2` (the C3-4 refusal comes first)."""
    described = SimpleNamespace(
        provider_id="wilson-ig-v2",
        reference_convention="WILSON-IG-ref-v1",
        components=("benzene", "toluene"),
    )
    return SimpleNamespace(describe=lambda: described)


def _view(model: str, inlet: str | None, outlet: str | None) -> InstanceView:
    return InstanceView(
        unit_id="U",
        model_id=model,
        ports={"inlet": ("S1",), "outlet": ("S2",)},
        directions={"inlet": "inlet", "outlet": "outlet"},
        phases={"inlet": inlet, "outlet": outlet},  # type: ignore[dict-item]
        parameters={"efficiency": 0.8},
        pins={"S2.P": 1.0e5},
    )


_CONTEXT = EvaluationContext(model_version="t", constants_sha256="0" * 64, phase_signature=None)


@pytest.mark.parametrize("model", ["thermal.compressor", "thermal.turbine"])
@pytest.mark.parametrize(
    ("inlet", "outlet", "port"),
    [("LIQUID", "VAPOR", "inlet"), (None, "VAPOR", "inlet"), ("VAPOR", None, "outlet")],
)
def test_a_wilson_machine_port_must_be_vapour(
    model: str, inlet: str | None, outlet: str | None, port: str
) -> None:
    with pytest.raises(RevisionError) as raised:
        thermal_binding.BUILDERS[model](
            _view(model, inlet, outlet), _wilson_v2(), _CONTEXT, ("benzene", "toluene")
        )
    assert (raised.value.kind, raised.value.code) == (
        "unsupported",
        f"specification_unsupported(U.{port})",
    )
    assert raised.value.hint == "no γ–φ two-phase PS closure (L-GP-2)"


@pytest.mark.parametrize("model", ["thermal.compressor", "thermal.turbine"])
def test_an_all_vapour_wilson_machine_is_refused_until_d5(model: str) -> None:
    """C3-4: the unit refuses the additive-vapour provider until WO-D4/D5; the builder reports it
    as the binder's `unsupported`."""
    with pytest.raises(RevisionError) as raised:
        thermal_binding.BUILDERS[model](
            _view(model, "VAPOR", "VAPOR"), _wilson_v2(), _CONTEXT, ("benzene", "toluene")
        )
    assert (raised.value.kind, raised.value.code) == (
        "unsupported",
        "specification_unsupported(U.provider)",
    )


# -- the binder's other codes, unchanged for the family ------------------------------------------


def test_an_efficiency_outside_the_interval_is_outside_the_domain(registered: None) -> None:
    """As the SYN-001 pump's: a value the unit refuses at construction (T07 round 5, S3)."""
    document = through(
        "thermal.pump",
        "liquid",
        "liquid",
        {"efficiency": dimensionless(1.5)},
        [outlet_pressure("U", 3.0e6)],
    )
    assert refused(document) == Unbound(
        "inadmissible", "value_outside_model_domain: efficiency_outside_interval", ("U",)
    )


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        pytest.param(
            through("thermal.pump", "liquid", "liquid", {}, [outlet_pressure("U", 3.0e6)]),
            Unbound("incomplete", "parameter_missing(U.efficiency)"),
            id="efficiency-missing",
        ),
        pytest.param(
            drum(parameters={}),
            Unbound("incomplete", "parameter_missing(U.pressure_drop)"),
            id="drum-pressure-drop-missing",
        ),
        pytest.param(
            through(
                "thermal.valve",
                "liquid",
                "liquid",
                {"pressure_drop": pascal(0.0)},
                [outlet_pressure("U", 5e4)],
            ),
            Unbound("unsupported", "parameter_unsupported(U.pressure_drop)"),
            id="valve-parameter",
        ),
        pytest.param(
            through("thermal.valve", "liquid", "liquid"),
            Unbound("incomplete", "specification_missing(S2.P)"),
            id="valve-pin-missing",
        ),
        pytest.param(
            through(
                "thermal.compressor",
                "vapor",
                "vapor",
                {"efficiency": dimensionless(0.8)},
                [outlet_pressure("U", 5e5), duty("U", 1.0)],
            ),
            Unbound("unsupported", "specification_unconsumed(SPEC-U-Q)"),
            id="machine-duty-unconsumed",
        ),
    ],
)
def test_the_binder_codes(registered: None, document: dict[str, Any], expected: Unbound) -> None:
    assert refused(document) == expected


def test_mixed_inlet_declarations_are_ambiguous(registered: None) -> None:
    """R4 declares one phase per port, so a revision's mixer cannot take a liquid and a vapour
    inlet together (S11.A56's first case is a direct-construction case)."""
    document = mixing("liquid", "vapor_liquid")
    document["connections"][1]["phase_capability"] = "vapor"
    assert refused(document) == Unbound("unsupported", "port_phase_ambiguous(U.inlet)")
