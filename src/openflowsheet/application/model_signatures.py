"""Unit-model signatures: what each model's builder reads, declared once (T07 §4.2, §15 W5c).

`ModelSignature` lists a model's ports, its required and zero-only parameters, the pins it always
reads and its one-of specification choices; `MODEL_SIGNATURES` holds one per model id, and
`MODEL_BASES` the component bases each model binds on. Beside them: the pin encodings
(`pin_encodings`, `render_encoding`), the pin readers the builders share, `instance_contract`, the
target-path table, and the `Builder` and `Configuration` types, so that the plugin modules
`column_binding` and `thermal_binding` import this module and never `model_builders`. Nothing here
constructs a unit or imports another application module; `revision_binding` re-exports every
public name.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import Port, UnitModel, duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.c1 import feed as c1_feed
from openflowsheet.models.c1 import flash as c1_flash
from openflowsheet.models.c1 import heater as c1_heater
from openflowsheet.models.c1 import mixer as c1_mixer
from openflowsheet.models.c1 import reactor as c1_reactor
from openflowsheet.models.c1 import sink as c1_sink
from openflowsheet.models.c1 import splitter as c1_splitter
from openflowsheet.models.revision_flowsheet import (
    PHASE_CAPABILITIES,
    TARGET_PATH_KINDS,
    WILSON_BASIS,
    InstanceView,
    RevisionError,
    required_kind,
    si_unit,
)
from openflowsheet.models.syn001 import PROVIDER_ID as SYN001_PROVIDER_ID
from openflowsheet.models.syn001 import (
    column_unit,
    component_separator,
    conversion_reactor,
    feed,
    flash,
    heat_exchanger,
    heater,
    kinetic_cstr,
    mixer,
    ph_flash,
    pump,
    sink,
    splitter,
    valve,
)
from openflowsheet.models.syn001.column import MODEL_ID as COLUMN_MODEL_ID
from openflowsheet.models.thermal import flash as thermal_flash
from openflowsheet.models.thermal import heater as thermal_heater
from openflowsheet.models.thermal import machines as thermal_machines
from openflowsheet.models.thermal import mixer as thermal_mixer
from openflowsheet.models.thermal import valve as thermal_valve
from openflowsheet.studies.surrogate import reactor as c1_surrogate
from openflowsheet.thermo import Phase, PropertyProvider
from openflowsheet.thermo.pr_c1 import PROVIDER_ID as C1_PROVIDER_ID

Configuration = Mapping[str, str | None]
Builder = Callable[
    [InstanceView, PropertyProvider, EvaluationContext, tuple[str, ...]],
    tuple[UnitModel, Configuration],
]


# -- model signatures (T07 design note §4.2 `list_models`, §15 W5c) -----------------------------

PinQuantity = Literal["flow", "temperature", "pressure", "duty"]


@dataclass(frozen=True)
class PinColumn:
    """A pinned column a builder reads, by what it is rather than by its id.

    `quantity` of the stream wired to `port` (`flow` is one column per component, in the
    provider's order), or the unit's own `duty` column, which has no port.
    """

    #: The builder's name for the value: its constructor argument, or the configuration label
    #: of a `SpecificationChoice` option.
    name: str
    quantity: PinQuantity
    port: str | None = None

    def __post_init__(self) -> None:
        if (self.quantity == "duty") != (self.port is None):
            raise ValueError(f"pin {self.name}: a duty has no port and a stream quantity has one")


@dataclass(frozen=True)
class SpecificationChoice:
    """Exactly one of `options` is pinned; the pinned option's `name` configures the unit."""

    #: The name `specification_missing`/`specification_conflict` report (`<unit>.<name>`).
    name: str
    options: tuple[PinColumn, ...]


@dataclass(frozen=True)
class ModelSignature:
    """What a model's builder reads from a revision instance, declared (§1.3's table, R5, R6).

    Parameter names in `required` are templates: `{component}` stands for each component in the
    provider's order, and a trailing `{key}` for every parameter the instance declares with that
    prefix (the conversion reactor's `conversion.<k>`, of which its builder admits exactly one).
    The order of `required`, `pins` and `choices` is the order they are read, so it is the order
    in which a missing one is reported.
    """

    model_id: str
    #: The unit's `ports()`, which is its module's `PORTS`.
    ports: tuple[Port, ...]
    #: R6: parameters that must be present.
    required: tuple[str, ...] = ()
    #: R6: parameters that may be present only as `0.0`.
    zero: tuple[str, ...] = ()
    #: Pins the builder always reads (R5: each one consumed).
    pins: tuple[PinColumn, ...] = ()
    #: One-of specifications: exactly one option pinned, and consumed.
    choices: tuple[SpecificationChoice, ...] = ()

    def pin(self, name: str) -> PinColumn:
        for pin in self.pins:
            if pin.name == name:
                return pin
        raise KeyError(f"{self.model_id} declares no pin {name!r}")

    def choice(self, name: str) -> SpecificationChoice:
        for choice in self.choices:
            if choice.name == name:
                return choice
        raise KeyError(f"{self.model_id} declares no choice {name!r}")


# -- encodings: how a revision pins what a builder reads (T07 ruling round 6, B2) ----------------


@dataclass(frozen=True)
class Encoding:
    """One way a revision's `role: fixed` specification pins a `PinColumn` (ruling round 6, B2).

    `object_id` is a template: `{instance}` is the instance's id, `{connection:<port>}` the
    connection wired to that port; `component` is `{component}` for a flow (one specification per
    component of the revision's set) and `None` otherwise. `kind` is `required_kind(path)` and
    `si_unit` that kind's SI unit. `fixes` names the pins one such specification pins: the pin
    itself, then any other the form reaches, in signature order.
    """

    object_type: Literal["instance", "connection"]
    object_id: str
    path: str
    component: str | None
    kind: str
    si_unit: str
    fixes: tuple[str, ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_id": self.object_id,
            "path": self.path,
            "component": self.component,
            "kind": self.kind,
            "si_unit": self.si_unit,
            "fixes": list(self.fixes),
        }


_QUANTITY_SUFFIX: Final[Mapping[str, str]] = {"temperature": "T", "pressure": "P"}


def _encoding(
    object_type: Literal["instance", "connection"],
    object_id: str,
    path: str,
    component: str | None,
    fixes: tuple[str, ...],
) -> Encoding:
    kind = required_kind(path)
    assert kind is not None, path
    return Encoding(object_type, object_id, path, component, kind, si_unit(kind), fixes)


def pin_encodings(signature: ModelSignature, pin: PinColumn) -> tuple[Encoding, ...]:
    """The encodings of `pin`, an entry of `signature.pins` or an option of one of its choices,
    that the revision binder reads (ruling round 6, B2 item 1): the one source the messages, the
    tool descriptions and `list_models` derive what they show from.

    - a duty: the instance's `duty.Q`;
    - a flow on port p: the connection wired to p, `state.n`, one specification per component;
    - a temperature or pressure on port p: the connection's `state.T|P`; then, for an entry of
      `pins` only, never a choice option, and only when every outlet port of the model carries a
      `pins` entry of the same quantity, the instance's `outlet.T|P`, which pins that quantity on
      every outlet (so it also fixes the others, listed after the pin in signature order).
    """
    if pin.quantity == "duty":
        return (_encoding("instance", "{instance}", "duty.Q", None, (pin.name,)),)
    connection = f"{{connection:{pin.port}}}"
    if pin.quantity == "flow":
        return (_encoding("connection", connection, "state.n", "{component}", (pin.name,)),)
    suffix = _QUANTITY_SUFFIX[pin.quantity]
    forms = [_encoding("connection", connection, f"state.{suffix}", None, (pin.name,))]
    outlets = [port.name for port in signature.ports if port.direction == "outlet"]
    same = [entry for entry in signature.pins if entry.quantity == pin.quantity]
    if (
        pin in signature.pins
        and pin.port in outlets
        and {entry.port for entry in same} >= set(outlets)
    ):
        others = tuple(entry.name for entry in same if entry.port in outlets and entry != pin)
        forms.append(
            _encoding("instance", "{instance}", f"outlet.{suffix}", None, (pin.name, *others))
        )
    return tuple(forms)


def _object_id(template: str, view: InstanceView) -> str:
    """An encoding's `object_id` on this instance: its id, or the stream wired to the port."""
    if template == "{instance}":
        return view.unit_id
    port = template.removeprefix("{connection:").removesuffix("}")
    connected = view.ports.get(port, ())
    return connected[0] if connected else template


def _pin_column_ids(
    view: InstanceView, signature: ModelSignature, name: str, components: Sequence[str]
) -> tuple[str, ...]:
    """The column ids of `signature`'s pin `name` on this instance, for a hint only: an unwired
    port is named by its template rather than refused."""
    pin = signature.pin(name)
    if pin.port is not None and not view.ports.get(pin.port):
        return (f"{{connection:{pin.port}}}",)
    return _columns(view, pin, components)


def render_encoding(
    encoding: Encoding,
    view: InstanceView,
    signature: ModelSignature,
    components: Sequence[str],
    component: str | None = None,
) -> str:
    """One encoding in a hint's words, on this instance (ruling round 6, B2's table): `kind K,
    unit U, target {object_type: T, object_id: ID, path: P[, component: C]}`, a flow `one per
    component (…)`, and `(also fixes X)` when it pins more than the pin, X as column ids."""
    target = (
        f"object_type: {encoding.object_type}, object_id: {_object_id(encoding.object_id, view)}, "
        f"path: {encoding.path}"
    )
    if encoding.component is not None:
        target += f", component: {component if component is not None else encoding.component}"
    text = f"kind {encoding.kind}, unit {encoding.si_unit}, target {{{target}}}"
    if encoding.component is not None:
        text += f", one per component ({', '.join(components)})"
    also = [
        column
        for name in encoding.fixes[1:]
        for column in _pin_column_ids(view, signature, name, components)
    ]
    if also:
        text += f" (also fixes {', '.join(also)})"
    return text


def _missing_pin_hint(
    view: InstanceView,
    signature: ModelSignature,
    pin: PinColumn,
    components: Sequence[str],
    component: str | None = None,
) -> str:
    """`specification_missing(<column>)`'s hint for a pin."""
    return "Pin it with one fixed specification: " + "; or ".join(
        render_encoding(encoding, view, signature, components, component)
        for encoding in pin_encodings(signature, pin)
    )


def _named_first(
    view: InstanceView, signature: ModelSignature, pin: PinColumn, components: Sequence[str]
) -> str:
    """`<pin name>: <its first encoding>`, on this instance."""
    first = pin_encodings(signature, pin)[0]
    return f"{pin.name}: {render_encoding(first, view, signature, components)}"


def _missing_choice_hint(
    view: InstanceView, signature: ModelSignature, choice: SpecificationChoice
) -> str:
    """`specification_missing(<unit>.<choice>)`'s hint."""
    return "Pin exactly one of: " + "; ".join(
        _named_first(view, signature, option, ()) for option in choice.options
    )


def _phase_hint(view: InstanceView, port: str, accepted: str) -> str:
    """`port_phase_unsupported(<unit>.<port>)`'s hint, in the document's words."""
    declared = PHASE_CAPABILITIES[view.phases[port]] if port in view.phases else "none"
    return (
        f"Port {port} of {view.model_id} takes phase {accepted}; the connection declares "
        f"{declared}."
    )


#: The target-path table's heading and closing line in the tool descriptions (B2 item 3).
TARGET_PATH_HEADING: Final = "Specification targets (object_type path: kind, SI unit; pins):"
LIST_MODELS_LINE: Final = "Each list_models pin lists the specifications that pin it."


def target_path_table() -> str:
    """The six-row target-path table the tool descriptions carry (ruling round 6, B2 item 3),
    generated from `TARGET_PATH_KINDS`: object type, path, kind, SI unit, what it pins; between
    its heading and the line pointing at `list_models`."""
    pins = {
        "state.n": "that component's flow",
        "state.T": "the stream's T",
        "state.P": "the stream's P",
        "outlet.T": "T of every outlet",
        "outlet.P": "P of every outlet",
        "duty.Q": "the unit's duty",
    }
    rows = [
        f"- {'connection' if path.startswith('state.') else 'instance'} "
        f"{path}{' + component' if path == 'state.n' else ''}: {kind}, {si_unit(kind)}; "
        f"{pins[path]}"
        for path, kind in TARGET_PATH_KINDS.items()
    ]
    return "\n".join([TARGET_PATH_HEADING, *rows, LIST_MODELS_LINE])


# -- pin readers and the instance contract -----------------------------------------------------


def _expand(template: str, view: InstanceView, components: Sequence[str]) -> tuple[str, ...]:
    """A `required` template's parameter names on this instance (`ModelSignature`)."""
    if "{component}" in template:
        return tuple(template.format(component=c) for c in components)
    if template.endswith("{key}"):
        prefix = template.removesuffix("{key}")
        return tuple(name for name in view.parameters if name.startswith(prefix))
    return (template,)


def _parameters(
    view: InstanceView, signature: ModelSignature, components: Sequence[str]
) -> dict[str, float]:
    """R6: the required parameters, and the optional ones that must be `0.0`; nothing else.

    A parameter the model does not read is refused rather than ignored: an input that changes
    nothing is a label for a function the revision's author did not get.
    """
    required = tuple(
        name for template in signature.required for name in _expand(template, view, components)
    )
    zero = signature.zero
    unknown = [name for name in view.parameters if name not in (*required, *zero)]
    if unknown:
        raise RevisionError("unsupported", f"parameter_unsupported({view.unit_id}.{unknown[0]})")
    missing = [name for name in required if name not in view.parameters]
    if missing:
        raise RevisionError("incomplete", f"parameter_missing({view.unit_id}.{missing[0]})")
    for name in zero:
        if view.parameters.get(name, 0.0) != 0.0:
            raise RevisionError(
                "unsupported", f"parameter_value_unsupported({view.unit_id}.{name})"
            )
    return {name: view.parameters[name] for name in required}


def _stream(view: InstanceView, port: str) -> str:
    connected = view.ports.get(port, ())
    if not connected:
        raise RevisionError("incomplete", f"port_unwired({view.unit_id}.{port})")
    return connected[0]


def _pin(view: InstanceView, column: str, hint: Callable[[], str] | None = None) -> float:
    """The value pinned to `column`; missing, `specification_missing(<column>)` with `hint()`,
    the encodings that would pin it (ruling round 6, B2), computed only on a miss."""
    if column not in view.pins:
        raise RevisionError(
            "incomplete", f"specification_missing({column})", None if hint is None else hint()
        )
    return view.pins[column]


def _columns(view: InstanceView, pin: PinColumn, components: Sequence[str]) -> tuple[str, ...]:
    """The column ids `pin` names on this instance: one per component for a flow, else one."""
    if pin.port is None:
        return (duty_id(view.unit_id),)
    stream = _stream(view, pin.port)
    if pin.quantity == "flow":
        return tuple(flow_id(stream, c) for c in components)
    return (temperature_id(stream) if pin.quantity == "temperature" else pressure_id(stream),)


def _column(view: InstanceView, pin: PinColumn) -> str:
    (column,) = _columns(view, pin, ())
    return column


def _pinned(view: InstanceView, signature: ModelSignature, name: str) -> float:
    """The value of `signature`'s scalar pin `name`."""
    pin = signature.pin(name)
    return _pin(view, _column(view, pin), lambda: _missing_pin_hint(view, signature, pin, ()))


def _require_phase(view: InstanceView, port: str, phase: Phase | None) -> None:
    """A port phase rule of §1.3's table, on a wired port."""
    if port in view.phases and view.phases[port] != phase:
        raise RevisionError(
            "unsupported",
            f"port_phase_unsupported({view.unit_id}.{port})",
            _phase_hint(view, port, PHASE_CAPABILITIES[phase]),
        )


#: Each model's fixed port-phase rules (§1.3's table), in the order its builder applied them:
#: a declared port's phase must be the one given (`None`: lifted, `vapor_liquid`); `*` is every
#: wired port. A rule that depends on another port's declared phase (the exchanger's outlet is its
#: inlet's) or that requires one of two phases (`_declared_phase`) stays with its builder.
_PORT_PHASES: Final[Mapping[str, tuple[tuple[str, Phase | None], ...]]] = {
    mixer.MODEL_ID: (("*", "LIQUID"),),
    heater.MODEL_ID: (("outlet", None),),
    flash.MODEL_ID: (("vapor", "VAPOR"), ("liquid", "LIQUID")),
    ph_flash.MODEL_ID: (("vapor", "VAPOR"), ("liquid", "LIQUID")),
    valve.MODEL_ID: (("outlet", None),),
    pump.MODEL_ID: (("inlet", "LIQUID"), ("outlet", "LIQUID")),
    conversion_reactor.MODEL_ID: (("outlet", None),),
    c1_mixer.MODEL_ID: (("*", "VAPOR"),),
    c1_heater.MODEL_ID: (("inlet", "VAPOR"), ("outlet", "VAPOR")),
    c1_flash.MODEL_ID: (("inlet", "VAPOR"), ("vapor", "VAPOR"), ("liquid", "LIQUID")),
    c1_reactor.REACTOR_MODEL_ID: (("inlet", "VAPOR"), ("outlet", "VAPOR")),
    c1_reactor.STANDIN_MODEL_ID: (("inlet", "VAPOR"), ("outlet", "VAPOR")),
}


def instance_contract(
    view: InstanceView, signature: ModelSignature, components: Sequence[str]
) -> dict[str, float]:
    """What an instance must satisfy under the model it names, apart from its pins (T07 ruling
    round 6, R6-W6): R6's parameter rule (`_parameters`, and exactly one parameter per `{key}`
    template), the model's fixed port-phase rules, and R4's converse — a declared `vapor_liquid`
    outlet only on the `outlet` port of an `outlet`-style lifting model (note §1.3, review S1).
    Returns the required parameters. Raises `RevisionError`.

    Every builder calls it first, and the legacy binder calls it on each instance it matches, so
    the legacy route solves a document only under everything the models it names read — a
    fallback may change the method, never the problem (ruling round 6, B1).
    """
    from openflowsheet.orchestrator.splits import SPLIT_RULES

    parameters = _parameters(view, signature, components)
    _require_one_keyed(view, signature, components)
    for port, phase in _PORT_PHASES.get(signature.model_id, ()):
        for each in tuple(view.ports) if port == "*" else (port,):
            _require_phase(view, each, phase)
    # Note §1.3 R4, the converse (review S1): a `vapor_liquid` connection is read as
    # `<S>.vap.*`/`<S>.liq.*`, which only the `outlet` port of an `outlet`-style lifting model
    # allocates. Any other producer declared so would bind and then fail untyped.
    rule = SPLIT_RULES.get(view.model_id)
    lifting = rule is not None and rule.style == "outlet"
    for port, phase in view.phases.items():
        if view.directions[port] != "outlet" or phase is not None:
            continue
        if not (lifting and port == "outlet"):
            raise RevisionError(
                "unsupported",
                f"port_phase_unsupported({view.unit_id}.{port})",
                _phase_hint(view, port, _ONE_PHASE),
            )
    return parameters


def _require_one_keyed(
    view: InstanceView, signature: ModelSignature, components: Sequence[str]
) -> None:
    """R6's `{key}` rule: each `{key}` template in `signature.required` names exactly one of
    `view`'s parameters. Raises `RevisionError` for the first template that names none
    (`parameter_missing`) or several (`parameter_unsupported`, naming the second)."""
    for template in signature.required:
        if not template.endswith("{key}"):
            continue
        keyed = _expand(template, view, components)
        if not keyed:
            name = template.removesuffix("{key}").removesuffix(".")
            raise RevisionError("incomplete", f"parameter_missing({view.unit_id}.{name})")
        if len(keyed) > 1:
            raise RevisionError("unsupported", f"parameter_unsupported({view.unit_id}.{keyed[1]})")


# -- the six K02 signatures (§1.3's table) ------------------------------------------------------


_FEED_SOURCE: Final = ModelSignature(
    model_id=feed.MODEL_ID,
    ports=feed.PORTS,
    pins=(
        PinColumn("flows", "flow", "outlet"),
        PinColumn("temperature", "temperature", "outlet"),
        PinColumn("pressure", "pressure", "outlet"),
    ),
)


_ADIABATIC_MIXER: Final = ModelSignature(
    model_id=mixer.MODEL_ID, ports=mixer.PORTS, zero=("pressure_drop",)
)


_TP_HEATER: Final = ModelSignature(
    model_id=heater.MODEL_ID,
    ports=heater.PORTS,
    zero=("pressure_drop",),
    pins=(PinColumn("outlet_temperature", "temperature", "outlet"),),
)


#: The liquid outlet's temperature and pressure are read to be refused when they differ from the
#: vapour's, which set the flash's.
_TP_FLASH: Final = ModelSignature(
    model_id=flash.MODEL_ID,
    ports=flash.PORTS,
    zero=("pressure_drop",),
    pins=(
        PinColumn("temperature", "temperature", "vapor"),
        PinColumn("pressure", "pressure", "vapor"),
        PinColumn("liquid_temperature", "temperature", "liquid"),
        PinColumn("liquid_pressure", "pressure", "liquid"),
    ),
)


_STREAM_SPLITTER: Final = ModelSignature(
    model_id=splitter.MODEL_ID, ports=splitter.PORTS, required=("split_fraction",)
)


_PRODUCT_SINK: Final = ModelSignature(model_id=sink.MODEL_ID, ports=sink.PORTS)


# -- the six T05 signatures (§1.3's table, W11) --------------------------------------------------


#: A port whose rule is `liquid` or `vapor` (not lifted), in the document's words.
_ONE_PHASE: Final = f"{PHASE_CAPABILITIES['LIQUID']} or {PHASE_CAPABILITIES['VAPOR']}"


_PH_FLASH: Final = ModelSignature(
    model_id=ph_flash.MODEL_ID,
    ports=ph_flash.PORTS,
    required=("pressure_drop",),
    pins=(PinColumn("duty", "duty"),),
)


_VALVE: Final = ModelSignature(
    model_id=valve.MODEL_ID,
    ports=valve.PORTS,
    pins=(PinColumn("outlet_pressure", "pressure", "outlet"),),
)


_LIQUID_PUMP: Final = ModelSignature(
    model_id=pump.MODEL_ID,
    ports=pump.PORTS,
    required=("efficiency",),
    pins=(PinColumn("outlet_pressure", "pressure", "outlet"),),
)


_CONVERSION_REACTOR: Final = ModelSignature(
    model_id=conversion_reactor.MODEL_ID,
    ports=conversion_reactor.PORTS,
    required=("nu.{component}", "conversion.{key}", "pressure_drop"),
    choices=(
        SpecificationChoice(
            "energy_specification",
            (PinColumn("outlet_temperature", "temperature", "outlet"), PinColumn("duty", "duty")),
        ),
    ),
)


#: T08 build-first §A1.2. `damkohler.<k>` names the key `k`, as `conversion.<k>` does the
#: conversion reactor's: the one reaction has exactly one. The outlet's declared phase is the
#: `phase` configuration; the unit reads no stream or duty pin (`Q` is `CSTR-cooling`'s).
_KINETIC_CSTR: Final = ModelSignature(
    model_id=kinetic_cstr.MODEL_ID,
    ports=kinetic_cstr.PORTS,
    required=(
        "nu.{component}",
        "damkohler.{key}",
        "T_ref",
        "T_scale",
        "coolant_flow",
        "coolant_cp",
        "T_coolant",
        "pressure_drop",
    ),
)


#: S11 design §4.7.1 (registered at I1): `syn001.column`'s signature. Its end specifications are not
#: `PinColumn`s (a pin is a stream quantity or a duty), so the signature names its one fixed
#: parameter and no choice; the rest is `column_unit`'s to read and refuse. Its optional parameters
#: — `stage_pressure.<j>`, `stage_duty.<j>`, `feed_stage.<stream>` and the twelve end parameters
#: (§10.5) — have no `ModelSignature` field to be listed in (`docs/S11B_DECISIONS.md`, B3b).
#: Defined here beside the others, because `column_binding` imports this module.
_COLUMN: Final = ModelSignature(
    model_id=COLUMN_MODEL_ID, ports=column_unit.PORTS, required=(column_unit.STAGE_COUNT,)
)


_COMPONENT_SEPARATOR: Final = ModelSignature(
    model_id=component_separator.MODEL_ID,
    ports=component_separator.PORTS,
    required=("split.{component}",),
)


_HEAT_EXCHANGER: Final = ModelSignature(
    model_id=heat_exchanger.MODEL_ID,
    ports=heat_exchanger.PORTS,
    choices=(
        SpecificationChoice(
            "specification",
            (
                PinColumn("hot_outlet_temperature", "temperature", "hot_outlet"),
                PinColumn("cold_outlet_temperature", "temperature", "cold_outlet"),
                PinColumn("duty", "duty"),
            ),
        ),
    ),
)


# -- the six M02 C1 signatures (design note §8, §14.2; WO-8.2) ----------------------------------
#
# The C1 units are their own classes (`models.c1`): SYN-001's carry SYN-001 constants in their
# manifests and row origins. Their signatures read what SYN-001's read, port for port, so the
# verifier's rules (`verify.table`) read the same pins. They bind only on the C1 basis, which
# `MODEL_BASES` states and the binder enforces (R-288); the builders do not check it.


_C1_FEED_SOURCE: Final = ModelSignature(
    model_id=c1_feed.MODEL_ID,
    ports=c1_feed.PORTS,
    pins=(
        PinColumn("flows", "flow", "outlet"),
        PinColumn("temperature", "temperature", "outlet"),
        PinColumn("pressure", "pressure", "outlet"),
    ),
)


_C1_ADIABATIC_MIXER: Final = ModelSignature(
    model_id=c1_mixer.MODEL_ID, ports=c1_mixer.PORTS, zero=("pressure_drop",)
)


_C1_TP_HEATER: Final = ModelSignature(
    model_id=c1_heater.MODEL_ID,
    ports=c1_heater.PORTS,
    zero=("pressure_drop",),
    pins=(PinColumn("outlet_temperature", "temperature", "outlet"),),
)


#: As `_TP_FLASH`: the liquid product's T and P are read to be refused when they differ from the
#: vapour's, which set the flash's.
_C1_TP_FLASH: Final = ModelSignature(
    model_id=c1_flash.MODEL_ID,
    ports=c1_flash.PORTS,
    zero=("pressure_drop",),
    pins=(
        PinColumn("temperature", "temperature", "vapor"),
        PinColumn("pressure", "pressure", "vapor"),
        PinColumn("liquid_temperature", "temperature", "liquid"),
        PinColumn("liquid_pressure", "pressure", "liquid"),
    ),
)


_C1_STREAM_SPLITTER: Final = ModelSignature(
    model_id=c1_splitter.MODEL_ID, ports=c1_splitter.PORTS, required=("split_fraction",)
)


_C1_PRODUCT_SINK: Final = ModelSignature(model_id=c1_sink.MODEL_ID, ports=c1_sink.PORTS)


#: M02 WO-9 (design note §4.1; ADR 0034 D1, D9): `c1.reactor` and `c1.reactor_standin` are one
#: embedded unit. `n_tubes` is the one parameter it reads; no row depends on it, so it is carried in
#: the unit's configuration for the experiment request. Both are variant-backed, so the binder has
#: already resolved the instance's pinned variant (`model_variant_mismatch` otherwise). The coupling
#: parameters start at that variant's `coupling.initial`; the coupled route moves them (WO-10).
#: Optional `coupling_initial.X` / `.dT` parameters are not admitted (build log D46).
_C1_REACTOR: Final = ModelSignature(
    model_id=c1_reactor.REACTOR_MODEL_ID, ports=c1_reactor.PORTS, required=("n_tubes",)
)
_C1_REACTOR_STANDIN: Final = ModelSignature(
    model_id=c1_reactor.STANDIN_MODEL_ID, ports=c1_reactor.PORTS, required=("n_tubes",)
)


#: M04 WO-7 (spec §8.1, §8.2; ADR 0037 D1, D2): `c1.reactor_surrogate` is M02's embedded unit with
#: (X̂, ΔT̂) the frozen quadratic of its SurrogateManifest, pinned by the manifest's SHA-256. It
#: reads `n_tubes` (the surrogate's per-tube flow). The binder resolves and checks the manifest
#: before building (`_resolve_surrogate`) and hands it to `_c1_reactor_surrogate_of`; the
#: registered builder, called without one, refuses as an unresolved manifest does.
_C1_REACTOR_SURROGATE: Final = ModelSignature(
    model_id=c1_surrogate.MODEL_ID, ports=c1_surrogate.PORTS, required=("n_tubes",)
)


#: SYN-001's thirteen models: the six K02 ones, the six T05 ones (§1.3's table) and T08's kinetic
#: CSTR (build-first §A1). They bind on SYN-001's basis only (R-288).
_SYN001_SIGNATURES: Final[tuple[ModelSignature, ...]] = (
    _FEED_SOURCE,
    _ADIABATIC_MIXER,
    _TP_HEATER,
    _TP_FLASH,
    _STREAM_SPLITTER,
    _PRODUCT_SINK,
    _PH_FLASH,
    _VALVE,
    _LIQUID_PUMP,
    _CONVERSION_REACTOR,
    _COMPONENT_SEPARATOR,
    _HEAT_EXCHANGER,
    _KINETIC_CSTR,
)


# -- the `thermal.*` family (S11 units design §4.4, §5.4 I1b) -----------------------------------

#: The seven `thermal.*` signatures, defined here beside the others because `thermal_binding`
#: imports this module (as `_COLUMN` is for `column_binding`). What they cannot list: the heater's
#: optional `pressure_drop` and `outlet_vapor_fraction` (`thermal_binding`'s docstring).
_THERMAL_HEATER: Final = ModelSignature(
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
_THERMAL_VALVE: Final = ModelSignature(
    model_id=thermal_valve.MODEL_ID,
    ports=thermal_valve.PORTS,
    pins=(PinColumn("outlet_pressure", "pressure", "outlet"),),
)
_THERMAL_MIXER: Final = ModelSignature(model_id=thermal_mixer.MODEL_ID, ports=thermal_mixer.PORTS)
_THERMAL_FLASH: Final = ModelSignature(
    model_id=thermal_flash.MODEL_ID,
    ports=thermal_flash.PORTS,
    required=("pressure_drop",),
    pins=(PinColumn("duty", "duty"),),
)
#: Machine (`pump`, `compressor`, `turbine`) -> its signature.
_THERMAL_MACHINES: Final[Mapping[str, ModelSignature]] = {
    machine: ModelSignature(
        model_id=model_id,
        ports=thermal_machines.PORTS[machine],
        required=("efficiency",),
        pins=(PinColumn("outlet_pressure", "pressure", "outlet"),),
    )
    for machine, model_id in thermal_machines.MACHINE_MODEL_IDS.items()
}
_THERMAL_SIGNATURES: Final[tuple[ModelSignature, ...]] = (
    _THERMAL_HEATER,
    _THERMAL_VALVE,
    _THERMAL_MIXER,
    _THERMAL_FLASH,
    *_THERMAL_MACHINES.values(),
)


#: M02's eight C1 models: the six units (design note §8) and the reactor's two ids (§4.1, WO-9),
#: and M04's surrogate of the reactor (W27 Amendment 3, R-301). They bind on the C1 basis only
#: (R-288).
_C1_SIGNATURES: Final[tuple[ModelSignature, ...]] = (
    _C1_FEED_SOURCE,
    _C1_ADIABATIC_MIXER,
    _C1_TP_HEATER,
    _C1_TP_FLASH,
    _C1_STREAM_SPLITTER,
    _C1_PRODUCT_SINK,
    _C1_REACTOR,
    _C1_REACTOR_STANDIN,
    _C1_REACTOR_SURROGATE,
)

#: Model id -> signature: what each builder reads (§1.3's table), for `list_models` (T07 §4.2):
#: SYN-001's thirteen, S11's column (§4.7) and, since M02's join (R-280), the eight C1 models;
#: M04's surrogate (R-301); the seven `thermal.*` models (S11 units design §5.4 I1b).
MODEL_SIGNATURES: Final[Mapping[str, ModelSignature]] = {
    signature.model_id: signature
    for signature in (*_SYN001_SIGNATURES, _COLUMN, *_C1_SIGNATURES, *_THERMAL_SIGNATURES)
}

_IAPWS95: Final = "iapws95-v1"
_COOLPROP: Final = "coolprop-heos-v1"
#: Units design §4.6 (WO-D5): the Wilson record source selects `wilson-ig-v2`.
_WILSON: Final = WILSON_BASIS.provider_id
#: The provider ids of the bases S11 makes selectable (ADR 0050 D1).
S11_BASES: Final = (_IAPWS95, _COOLPROP, _WILSON)
#: S11 design §4.4: the models that hold no provider and evaluate no property.
ROUTING_MODELS: Final = (feed.MODEL_ID, sink.MODEL_ID, splitter.MODEL_ID)
#: Units design §4.5, §4.7: the five K02/T05 units with γ–φ faces, which bind on Wilson too.
_GAMMA_PHI_MODELS: Final = (
    _TP_HEATER.model_id,
    _TP_FLASH.model_id,
    _PH_FLASH.model_id,
    _VALVE.model_id,
    _ADIABATIC_MIXER.model_id,
)
#: Units design §4.7: the pure-fluid bases every `thermal.*` model binds on, and the vapour
#: machines that bind on Wilson as well (L-GP-2).
_PURE_FLUID_BASES: Final = frozenset({_IAPWS95, _COOLPROP})
_WILSON_MACHINES: Final = (
    thermal_machines.MACHINE_MODEL_IDS["compressor"],
    thermal_machines.MACHINE_MODEL_IDS["turbine"],
)

#: Model id -> the provider ids of the bases it binds on (register R-288, design note §14.4 D3):
#: each `syn001.*` model on SYN-001's basis only, each `c1.*` model on the C1 basis only. The one
#: source of which basis accepts which model: the binder's `model_unsupported(<model id>)` pass
#: reads it, and so does W27's registry snapshot (W27-R63 `bases-v1`). Every builder has a row
#: (`set(MODEL_BASES) == set(MODEL_BUILDERS)`, asserted by the tests).
MODEL_BASES: Final[Mapping[str, frozenset[str]]] = {
    **{s.model_id: frozenset({SYN001_PROVIDER_ID}) for s in _SYN001_SIGNATURES},
    **{s.model_id: frozenset({C1_PROVIDER_ID}) for s in _C1_SIGNATURES},
    # S11 design §4.4 (ADR 0050 D3): the three routing models hold no provider and bind on every
    # basis except C1's, which has their namesakes.
    **dict.fromkeys(ROUTING_MODELS, frozenset({SYN001_PROVIDER_ID, *S11_BASES})),
    # S11 design §4.7, §9 (I1): the column binds on SYN-001's basis and on the provider id the
    # Wilson registry row holds (`WILSON_BASIS`); C1's is vapour-only and a pure fluid has no
    # stage composition (`_UNADMITTED`).
    _COLUMN.model_id: frozenset({SYN001_PROVIDER_ID, WILSON_BASIS.provider_id}),
    # Units design §4.7 (I1b): the five γ–φ-faced units on Wilson as well (track D), and the seven
    # `thermal.*` models on the pure-fluid bases, the compressor and turbine also on Wilson.
    **{model_id: frozenset({SYN001_PROVIDER_ID, _WILSON}) for model_id in _GAMMA_PHI_MODELS},
    **{
        s.model_id: _PURE_FLUID_BASES | ({_WILSON} if s.model_id in _WILSON_MACHINES else set())
        for s in _THERMAL_SIGNATURES
    },
}
