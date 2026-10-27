"""The revision builders of the `thermal.*` family (S11 units design §4.4; ADR 0051; WO-C4).

`SIGNATURES` holds the seven models' signatures, `BUILDERS` their builders in the `Builder` shape of
`revision_binding`, and `BASES` the bases they bind on. They enter `MODEL_SIGNATURES`,
`MODEL_BUILDERS` and `MODEL_BASES` at the integration WO I1b, not here (units design §5.4); until
then a test registers them in monkeypatched tables, as `test_m02_wo8_region` does.

**A port's form is its connection's declared `phase_capability`** (ADR 0051 D1): `liquid` and
`vapor` are single-phase, `vapor_liquid` is SATURATED, a stream on the saturation line whose
carried split the producing `thermal.*` unit owns (D2-D4). So these builders do not apply
`instance_contract`'s converse of R4, which reads a `vapor_liquid` outlet as a lifted split that
only an `outlet`-style lifting model allocates; each builder reads its parameters and wiring
itself, with the binder's codes.

**The bind refusals of §4.4** are `Unbound("unsupported", "specification_unsupported(<U>.<what>)")`
with the table's hint. The units raise each one at construction (`SpecificationError`, its first
line the code and the rest the hint; S11C build decisions C2/C3-7), so a builder translates
exactly those into `RevisionError` and leaves every other construction refusal to the binder's
`value_outside_model_domain` (T07 ruling round 5, S3), as the SYN-001 builders do. Two refusals
are the binder's own: the heater's one-of specification, which the binder's missing and conflict
codes report, and a Wilson machine's non-vapour port, which no unit can see once its provider is
refused (C3-4).

What the signatures cannot list (as `column_binding`'s cannot; S11B build decision): the heater's
optional parameters `pressure_drop` (default 0) and `outlet_vapor_fraction` (its quality mode).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Final

from openflowsheet.application.revision_binding import (
    Builder,
    Configuration,
    ModelSignature,
    PinColumn,
    SpecificationChoice,
    _column,
    _missing_choice_hint,
    _pin,
    _pinned,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import Port, SpecificationError, UnitModel
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionError
from openflowsheet.models.thermal import ADDITIVE_VAPOUR, Form, machines
from openflowsheet.models.thermal import flash as thermal_flash
from openflowsheet.models.thermal import heater as thermal_heater
from openflowsheet.models.thermal import mixer as thermal_mixer
from openflowsheet.models.thermal import valve as thermal_valve
from openflowsheet.models.thermal.flash import ThermalFlash
from openflowsheet.models.thermal.heater import ThermalHeater
from openflowsheet.models.thermal.machines import ThermalMachine
from openflowsheet.models.thermal.mixer import ThermalMixer
from openflowsheet.models.thermal.valve import ThermalValve
from openflowsheet.thermo import PropertyProvider

__all__ = ["BASES", "BUILDERS", "OUTLET_VAPOR_FRACTION", "SIGNATURES"]

#: The heater's quality-mode parameter (`_PARAMETER_KINDS`: dimensionless; units design §2.4).
OUTLET_VAPOR_FRACTION: Final = "outlet_vapor_fraction"
_PRESSURE_DROP: Final = "pressure_drop"
_EFFICIENCY: Final = "efficiency"

#: A connection's declared phase (R4; `None` is `vapor_liquid`) as a pure-fluid form (ADR 0051 D1).
_FORM: Final[Mapping[str | None, Form]] = {
    "LIQUID": "LIQUID",
    "VAPOR": "VAPOR",
    None: "SATURATED",
}

_SPECIFICATION_REFUSAL: Final = "specification_unsupported("


# -- helpers -----------------------------------------------------------------------------------


def _parameters(
    view: InstanceView, required: Sequence[str], optional: Sequence[str] = ()
) -> dict[str, float]:
    """R6 with the binder's codes: the required parameters must be present, the optional ones may
    be, and nothing else is read. Returns those present."""
    unknown = [name for name in view.parameters if name not in (*required, *optional)]
    if unknown:
        raise RevisionError("unsupported", f"parameter_unsupported({view.unit_id}.{unknown[0]})")
    missing = [name for name in required if name not in view.parameters]
    if missing:
        raise RevisionError("incomplete", f"parameter_missing({view.unit_id}.{missing[0]})")
    return {
        name: view.parameters[name] for name in (*required, *optional) if name in view.parameters
    }


def _wired(
    view: InstanceView, ports: Sequence[Port]
) -> tuple[dict[str, tuple[str, ...]], dict[str, Form]]:
    """The unit's material ports -> their streams, and each stream's declared form.

    The ports are checked here, with the binder's codes and in its order (wired, direction,
    multiplicity), because a unit reads its streams at construction; the binder's own pass after
    construction then finds them in order. A port the unit does not have is left to that pass."""
    streams: dict[str, tuple[str, ...]] = {}
    forms: dict[str, Form] = {}
    for port in ports:
        if port.kind != "material":
            continue
        where = f"{view.unit_id}.{port.name}"
        connected = tuple(view.ports.get(port.name, ()))
        if not connected:
            raise RevisionError("incomplete", f"port_unwired({where})")
        if view.directions[port.name] != port.direction:
            raise RevisionError("unsupported", f"port_direction_unsupported({where})")
        if port.multiplicity == 1 and len(connected) != 1:
            raise RevisionError("unsupported", f"port_multiplicity_unsupported({where})")
        streams[port.name] = connected
        for stream in connected:
            forms[stream] = _FORM[view.phases[port.name]]
    return streams, forms


def _port_forms(streams: Mapping[str, tuple[str, ...]], forms: Mapping[str, Form]) -> Configuration:
    """Each material port's form (R4 gives one per port): the configuration's form labels."""
    return {port: forms[connected[0]] for port, connected in streams.items()}


def _construct(build: Callable[[], UnitModel]) -> UnitModel:
    """The unit, with a §4.4 bind refusal it raises at construction as the binder's `unsupported`
    (code, then hint); any other `SpecificationError` passes to the binder unchanged."""
    try:
        return build()
    except SpecificationError as error:
        code, _, hint = str(error).partition("\n")
        if code.startswith(_SPECIFICATION_REFUSAL):
            raise RevisionError("unsupported", code, hint or None) from error
        raise


# -- thermal.heater ------------------------------------------------------------------------------

_HEATER: Final = ModelSignature(
    model_id=thermal_heater.MODEL_ID,
    ports=thermal_heater.PORTS,
    choices=(
        SpecificationChoice(
            "specification",
            (
                PinColumn("outlet_temperature", "temperature", "outlet"),
                PinColumn("duty", "duty"),
            ),
        ),
    ),
)


def _heater(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """Exactly one of the pinned `outlet.T`, the pinned `duty.Q` and the parameter
    `outlet_vapor_fraction` (§4.4); the binder's missing and conflict codes otherwise."""
    signature = _HEATER
    parameters = _parameters(view, (), (_PRESSURE_DROP, OUTLET_VAPOR_FRACTION))
    streams, forms = _wired(view, signature.ports)
    choice = signature.choice("specification")
    options = {_column(view, option): option for option in choice.options}
    pinned = [column for column in options if column in view.pins]
    given = len(pinned) + (OUTLET_VAPOR_FRACTION in parameters)
    if given == 0:
        raise RevisionError(
            "incomplete",
            f"specification_missing({view.unit_id}.{choice.name})",
            _missing_choice_hint(view, signature, choice)
            + f"; or give the parameter {OUTLET_VAPOR_FRACTION} (a vapor_liquid outlet)",
        )
    if given > 1:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.{choice.name})")
    if pinned:
        option = options[pinned[0]]
        name = option.name
        value = _pin(view, pinned[0])
    else:
        name = OUTLET_VAPOR_FRACTION
        value = parameters[OUTLET_VAPOR_FRACTION]
    unit = _construct(
        lambda: ThermalHeater(
            unit_id=view.unit_id,
            provider=provider,
            context=context,
            streams=streams,
            forms=forms,
            outlet_temperature=value if name == "outlet_temperature" else None,
            duty=value if name == "duty" else None,
            outlet_vapor_fraction=value if name == OUTLET_VAPOR_FRACTION else None,
            pressure_drop=parameters.get(_PRESSURE_DROP, 0.0),
        )
    )
    return unit, {"specification": name, **_port_forms(streams, forms)}


# -- thermal.valve -------------------------------------------------------------------------------

_VALVE: Final = ModelSignature(
    model_id=thermal_valve.MODEL_ID,
    ports=thermal_valve.PORTS,
    pins=(PinColumn("outlet_pressure", "pressure", "outlet"),),
)


def _valve(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _VALVE
    _parameters(view, ())
    streams, forms = _wired(view, signature.ports)
    unit = _construct(
        lambda: ThermalValve(
            unit_id=view.unit_id,
            provider=provider,
            context=context,
            streams=streams,
            forms=forms,
            outlet_pressure=_pinned(view, signature, "outlet_pressure"),
        )
    )
    return unit, _port_forms(streams, forms)


# -- thermal.mixer -------------------------------------------------------------------------------

_MIXER: Final = ModelSignature(model_id=thermal_mixer.MODEL_ID, ports=thermal_mixer.PORTS)


def _mixer(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """Adiabatic, no parameter (§4.4). R4 declares one phase per port, so a revision's inlets
    share one form."""
    _parameters(view, ())
    streams, forms = _wired(view, _MIXER.ports)
    unit = _construct(
        lambda: ThermalMixer(
            unit_id=view.unit_id, provider=provider, context=context, streams=streams, forms=forms
        )
    )
    return unit, _port_forms(streams, forms)


# -- thermal.flash -------------------------------------------------------------------------------

_FLASH: Final = ModelSignature(
    model_id=thermal_flash.MODEL_ID,
    ports=thermal_flash.PORTS,
    required=(_PRESSURE_DROP,),
    pins=(PinColumn("duty", "duty"),),
)


def _flash(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """A pinned duty and the parameter `pressure_drop`, as `syn001.ph_flash`; both products
    `vapor_liquid` (ADR 0051 D4)."""
    signature = _FLASH
    parameters = _parameters(view, signature.required)
    streams, forms = _wired(view, signature.ports)
    unit = _construct(
        lambda: ThermalFlash(
            unit_id=view.unit_id,
            provider=provider,
            context=context,
            streams=streams,
            forms=forms,
            duty=_pinned(view, signature, "duty"),
            pressure_drop=parameters[_PRESSURE_DROP],
        )
    )
    return unit, _port_forms(streams, forms)


# -- thermal.pump, thermal.compressor, thermal.turbine -------------------------------------------

_MACHINES: Final[Mapping[str, ModelSignature]] = {
    machine: ModelSignature(
        model_id=model_id,
        ports=machines.PORTS[machine],
        required=(_EFFICIENCY,),
        pins=(PinColumn("outlet_pressure", "pressure", "outlet"),),
    )
    for machine, model_id in machines.MODEL_IDS.items()
}

#: §4.4: an additive-vapour (Wilson) machine has no γ–φ two-phase PS closure.
_WILSON_PORT_HINT: Final = "no γ–φ two-phase PS closure (L-GP-2)"


def _machine(
    machine: str,
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """A pinned `outlet.P` and the parameter `efficiency` (§4.4). The turbine's isentropic phase
    is its outlet's form: a revision has no field that chooses another (S11C build decision
    C4-3)."""
    signature = _MACHINES[machine]
    parameters = _parameters(view, signature.required)
    streams, forms = _wired(view, signature.ports)
    described = provider.describe()
    if (described.provider_id, described.reference_convention) in ADDITIVE_VAPOUR:
        for port, connected in streams.items():
            if forms[connected[0]] != "VAPOR":
                raise RevisionError(
                    "unsupported",
                    f"specification_unsupported({view.unit_id}.{port})",
                    _WILSON_PORT_HINT,
                )
    unit = _construct(
        lambda: ThermalMachine(
            unit_id=view.unit_id,
            machine=machine,  # type: ignore[arg-type]
            provider=provider,
            context=context,
            streams=streams,
            forms=forms,
            outlet_pressure=_pinned(view, signature, "outlet_pressure"),
            efficiency=parameters[_EFFICIENCY],
        )
    )
    return unit, _port_forms(streams, forms)


def _machine_builder(machine: str) -> Builder:
    def build(
        view: InstanceView,
        provider: PropertyProvider,
        context: EvaluationContext,
        components: tuple[str, ...],
    ) -> tuple[UnitModel, Configuration]:
        return _machine(machine, view, provider, context, components)

    return build


# -- the registry rows I1b merges ----------------------------------------------------------------

#: Model id -> signature: what each builder reads, for `list_models` (T07 §4.2).
SIGNATURES: Final[Mapping[str, ModelSignature]] = {
    signature.model_id: signature
    for signature in (_HEATER, _VALVE, _MIXER, _FLASH, *_MACHINES.values())
}

#: Model id -> builder.
BUILDERS: Final[Mapping[str, Builder]] = {
    _HEATER.model_id: _heater,
    _VALVE.model_id: _valve,
    _MIXER.model_id: _mixer,
    _FLASH.model_id: _flash,
    **{model_id: _machine_builder(machine) for machine, model_id in machines.MODEL_IDS.items()},
}

#: Model id -> the provider ids of the bases it binds on (units design §4.7): the two pure-fluid
#: bases. The compressor and turbine gain `wilson-ig-v2` when WO-D5 selects it.
BASES: Final[Mapping[str, frozenset[str]]] = dict.fromkeys(
    SIGNATURES, frozenset({"iapws95-v1", "coolprop-heos-v1"})
)
