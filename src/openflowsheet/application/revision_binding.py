"""Binding a `ProcessRevision` to a revision-built flowsheet. T05 design note §1.3, §1.4.

`application.binding` binds the registered SYN-001 revisions to `Syn001Flowsheet` by topology and
stays as it is. This module builds the flowsheet *from* the revision: every instance's unit is
constructed by the builder registered for its model id (`MODEL_BUILDERS`), from the instance's
parameters and pins read by §1.3's rules, with no default (D5). Each builder returns the unit and
its `configuration` — the part of the revision that selects expressions without changing ids,
which the flowsheet's label digests (register R-047).

**A pin is consumed when its builder reads it.** The builder is handed the instance view with a
pin mapping that records every value read; a pin nobody read is a specification the flowsheet
would silently ignore, and is refused `specification_unconsumed(<spec id>)` (R5). Membership
tests (`in`) do not count as a read.

Every refusal is an `Unbound` with R-022's kind and a stable code, never an exception: a revision
the rules cannot read may be perfectly fine, and says so as `unsupported`.

**What a builder reads is declared, once, in its `ModelSignature`** (T07 design note §4.2
`list_models`, §15 W5c): the model's ports, its required and zero-only parameters, the pins it
always reads and the one-of specification choices. The builders take those lists from
`MODEL_SIGNATURES` rather than from literals, so what `list_models` reports is what binding reads;
the signature constructs nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import partial
from typing import Any, Final, Literal

from openflowsheet.application.binding import Unbound, _column_owners
from openflowsheet.canonical import document_sha256, first_noncanonical
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.process import Connection, ProcessGraph
from openflowsheet.graph.trace import Declaration
from openflowsheet.models import (
    Port,
    SpecificationError,
    UnitModel,
    duty_id,
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.revision_flowsheet import (
    PHASE_CAPABILITIES,
    TARGET_PATH_KINDS,
    InputMapping,
    InstanceView,
    RevisionError,
    RevisionFlowsheet,
    configuration_sha256,
    parse_revision,
    pin_specifications,
    required_kind,
    si_unit,
)
from openflowsheet.models.syn001 import (
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
from openflowsheet.models.syn001.component_separator import ComponentSeparator
from openflowsheet.models.syn001.conversion_reactor import ConversionReactor
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.models.syn001.flash import TPFlash
from openflowsheet.models.syn001.heat_exchanger import HeatExchanger
from openflowsheet.models.syn001.heater import TPHeater
from openflowsheet.models.syn001.kinetic_cstr import KineticCSTR
from openflowsheet.models.syn001.mixer import AdiabaticMixer
from openflowsheet.models.syn001.ph_flash import PHFlash
from openflowsheet.models.syn001.pump import LiquidPump
from openflowsheet.models.syn001.sink import ProductSink
from openflowsheet.models.syn001.splitter import StreamSplitter
from openflowsheet.models.syn001.valve import Valve
from openflowsheet.thermo import Phase, PropertyProvider

__all__ = [
    "MODEL_BUILDERS",
    "MODEL_SIGNATURES",
    "Builder",
    "Encoding",
    "ModelSignature",
    "PinColumn",
    "RevisionBinding",
    "SpecificationChoice",
    "bind_revision_flowsheet",
    "instance_contract",
    "pin_encodings",
    "render_encoding",
    "specification_rows",
    "target_path_table",
]

#: The context a revision-built flowsheet's units are constructed with (§1.4).
_CONTEXT = EvaluationContext(
    model_version="revision-structural", constants_sha256="0" * 64, phase_signature=None
)

Configuration = Mapping[str, str | None]
Builder = Callable[
    [InstanceView, PropertyProvider, EvaluationContext, tuple[str, ...]],
    tuple[UnitModel, Configuration],
]


@dataclass(frozen=True)
class RevisionBinding:
    """A revision-built flowsheet with what the structural layer and the verifier need."""

    flowsheet: RevisionFlowsheet
    #: `flowsheet.spec()`, computed once.
    spec: ProblemSpec
    graph: ProcessGraph
    #: Row id -> the instance that authored it, from each unit's own contribution (T01 A15).
    row_units: Mapping[str, str]
    #: ADR 0002's `document_sha256` of the revision this binding was built from.
    revision_sha256: str
    #: How the revision's inputs were read (T06 spec §8.5): `parse_revision`'s record, which is
    #: also what `verify_revision` reads. Empty for every registered revision.
    input_mapping: InputMapping = field(default_factory=InputMapping)
    #: Instance id -> {pinned column -> the specification that pins it}: what each builder was
    #: handed and consumed, recorded where the units are built (M06 design note §4.1, R3). The
    #: first specification in document order names a column two equal specifications pin, as
    #: `specification_unconsumed` and `specification_conflict` name it. Read only by
    #: `specification_rows`, for `inspect_structure`'s index; never by the structural analysis.
    specification_pins: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


def specification_rows(binding: RevisionBinding, declaration: Declaration) -> dict[str, str]:
    """Row id -> the revision specification the row realises, on `revision_eo` (M06 design note
    §4.1): a specification row (`TracedRow.is_specification_row`) whose one column is a pin its
    authoring instance consumed. Joined on the row's traced incidence and the binder's own
    routing record, never on id text (R-019). For `inspect_structure`'s index only: the route's
    analysis is given no specification ids on `revision_eo`, and its report does not change."""
    attributed: dict[str, str] = {}
    for row_id in declaration.row_ids:
        row = declaration.rows[row_id]
        if row.unit is None or row.coefficients is None or not row.is_specification_row:
            continue
        (column,) = row.coefficients
        specification = binding.specification_pins.get(row.unit, {}).get(column)
        if specification is not None:
            attributed[row_id] = specification
    return attributed


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


def _first_encodings(
    view: InstanceView, signature: ModelSignature, components: Sequence[str]
) -> str:
    """Each of `signature`'s pins with its first encoding, then each choice's options."""
    parts = [_named_first(view, signature, pin, components) for pin in signature.pins]
    parts += [
        f"one of {choice.name} ("
        + "; ".join(_named_first(view, signature, option, components) for option in choice.options)
        + ")"
        for choice in signature.choices
    ]
    return "; ".join(parts) if parts else "no pinned column"


def _unconsumed_hint(view: InstanceView, column: str, components: Sequence[str]) -> str | None:
    """`specification_unconsumed(<id>)`'s hint: what the instance's model reads instead; `None`
    for a model with no signature."""
    signature = MODEL_SIGNATURES.get(view.model_id)
    if signature is None:
        return None
    return (
        f"{view.unit_id} ({signature.model_id}) does not read column {column}; it reads "
        f"{_first_encodings(view, signature, components)}"
    )


def _phase_hint(view: InstanceView, port: str, accepted: str) -> str:
    """`port_phase_unsupported(<unit>.<port>)`'s hint, in the document's words."""
    declared = PHASE_CAPABILITIES[view.phases[port]] if port in view.phases else "none"
    return (
        f"Port {port} of {view.model_id} takes phase {accepted}; the connection declares "
        f"{declared}."
    )


def _instance_targets(signature: ModelSignature) -> str:
    """What an instance of `signature`'s model takes as a target path: the distinct instance-form
    encodings of its pins and options, then `parameters.<name>` for its required and zero-only
    parameters (a `specification_unsupported` hint on an instance target)."""
    paths: dict[str, str] = {}
    for pin in (*signature.pins, *(o for c in signature.choices for o in c.options)):
        for encoding in pin_encodings(signature, pin):
            if encoding.object_type == "instance":
                paths.setdefault(
                    encoding.path, f"{encoding.path} ({encoding.kind}, {encoding.si_unit})"
                )
    names = [*paths.values(), *(f"parameters.{p}" for p in (*signature.required, *signature.zero))]
    if not names:
        return "takes no target path"
    return "takes path " + (
        names[0] if len(names) == 1 else f"{', '.join(names[:-1])} or {names[-1]}"
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


# -- builder helpers ---------------------------------------------------------------------------


def _expand(template: str, view: InstanceView, components: Sequence[str]) -> tuple[str, ...]:
    """A `required` template's parameter names on this instance (`ModelSignature`)."""
    if "{component}" in template:
        return tuple(template.format(component=c) for c in components)
    if template.endswith("{key}"):
        prefix = template.removesuffix("{key}")
        return tuple(name for name in view.parameters if name.startswith(prefix))
    return (template,)


def _names(
    signature: ModelSignature, template: str, view: InstanceView, components: Sequence[str]
) -> tuple[str, ...]:
    """The names one of `signature`'s required templates expands to on this instance."""
    if template not in signature.required:
        raise ValueError(f"{signature.model_id} does not require {template!r}")
    return _expand(template, view, components)


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


def _inlet_phase(view: InstanceView) -> Phase | None:
    _stream(view, "inlet")
    return view.phases["inlet"]


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
    for template in signature.required:
        if not template.endswith("{key}"):
            continue
        keyed = _expand(template, view, components)
        if not keyed:
            name = template.removesuffix("{key}").removesuffix(".")
            raise RevisionError("incomplete", f"parameter_missing({view.unit_id}.{name})")
        if len(keyed) > 1:
            raise RevisionError("unsupported", f"parameter_unsupported({view.unit_id}.{keyed[1]})")
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


# -- the six K02 builders (§1.3's table) --------------------------------------------------------


_FEED_SOURCE: Final = ModelSignature(
    model_id=feed.MODEL_ID,
    ports=feed.PORTS,
    pins=(
        PinColumn("flows", "flow", "outlet"),
        PinColumn("temperature", "temperature", "outlet"),
        PinColumn("pressure", "pressure", "outlet"),
    ),
)


def _feed_source(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _FEED_SOURCE
    instance_contract(view, signature, components)
    pin = signature.pin("flows")
    flows = _columns(view, pin, components)
    unit = FeedSource(
        unit_id=view.unit_id,
        flows=tuple(
            _pin(view, column, partial(_missing_pin_hint, view, signature, pin, components, c))
            for c, column in zip(components, flows, strict=True)
        ),
        temperature=_pinned(view, signature, "temperature"),
        pressure=_pinned(view, signature, "pressure"),
        components=components,
    )
    return unit, {}


_ADIABATIC_MIXER: Final = ModelSignature(
    model_id=mixer.MODEL_ID, ports=mixer.PORTS, zero=("pressure_drop",)
)


def _adiabatic_mixer(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    instance_contract(view, _ADIABATIC_MIXER, components)
    unit = AdiabaticMixer(
        unit_id=view.unit_id, provider=provider, context=context, components=components
    )
    return unit, {}


_TP_HEATER: Final = ModelSignature(
    model_id=heater.MODEL_ID,
    ports=heater.PORTS,
    zero=("pressure_drop",),
    pins=(PinColumn("outlet_temperature", "temperature", "outlet"),),
)


def _tp_heater(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _TP_HEATER
    instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    unit = TPHeater(
        unit_id=view.unit_id,
        provider=provider,
        outlet_temperature=_pinned(view, signature, "outlet_temperature"),
        context=context,
        inlet_phase=inlet_phase,
        pressure_drop=0.0,
        components=components,
    )
    return unit, {"inlet_phase": inlet_phase}


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


def _tp_flash(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _TP_FLASH
    instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    # Both outlets wired before either is read.
    _stream(view, "vapor")
    _stream(view, "liquid")
    temperature = _pinned(view, signature, "temperature")
    pressure = _pinned(view, signature, "pressure")
    if _pinned(view, signature, "liquid_temperature") != temperature:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.T)")
    if _pinned(view, signature, "liquid_pressure") != pressure:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.P)")
    unit = TPFlash(
        unit_id=view.unit_id,
        provider=provider,
        temperature=temperature,
        pressure=pressure,
        context=context,
        inlet_phase=inlet_phase,
        components=components,
    )
    return unit, {"inlet_phase": inlet_phase}


_STREAM_SPLITTER: Final = ModelSignature(
    model_id=splitter.MODEL_ID, ports=splitter.PORTS, required=("split_fraction",)
)


def _stream_splitter(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    parameters = instance_contract(view, _STREAM_SPLITTER, components)
    unit = StreamSplitter(
        unit_id=view.unit_id,
        split_fraction=parameters["split_fraction"],
        components=components,
    )
    return unit, {}


_PRODUCT_SINK: Final = ModelSignature(model_id=sink.MODEL_ID, ports=sink.PORTS)


def _product_sink(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    instance_contract(view, _PRODUCT_SINK, components)
    return ProductSink(unit_id=view.unit_id, components=components), {}


# -- the six T05 builders (§1.3's table, W11) ----------------------------------------------------


#: A port whose rule is `liquid` or `vapor` (not lifted), in the document's words.
_ONE_PHASE: Final = f"{PHASE_CAPABILITIES['LIQUID']} or {PHASE_CAPABILITIES['VAPOR']}"


def _declared_phase(view: InstanceView, port: str) -> Phase:
    """A port whose rule is `liquid` or `vapor`: wired, and not lifted."""
    _stream(view, port)
    phase = view.phases[port]
    if phase is None:
        raise RevisionError(
            "unsupported",
            f"port_phase_unsupported({view.unit_id}.{port})",
            _phase_hint(view, port, _ONE_PHASE),
        )
    return phase


def _one_specification(
    view: InstanceView, signature: ModelSignature, name: str
) -> tuple[PinColumn, str]:
    """Exactly one of the choice's options is pinned; returns it and its column, unread.

    Options are keyed by column, a later option taking an earlier one's column.
    """
    choice = signature.choice(name)
    candidates = {_column(view, option): option for option in choice.options}
    pinned = [column for column in candidates if column in view.pins]
    if not pinned:
        raise RevisionError(
            "incomplete",
            f"specification_missing({view.unit_id}.{choice.name})",
            _missing_choice_hint(view, signature, choice),
        )
    if len(pinned) > 1:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.{choice.name})")
    return candidates[pinned[0]], pinned[0]


_PH_FLASH: Final = ModelSignature(
    model_id=ph_flash.MODEL_ID,
    ports=ph_flash.PORTS,
    required=("pressure_drop",),
    pins=(PinColumn("duty", "duty"),),
)


def _ph_flash(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _PH_FLASH
    parameters = instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    unit = PHFlash(
        unit_id=view.unit_id,
        provider=provider,
        duty=_pinned(view, signature, "duty"),
        context=context,
        pressure_drop=parameters["pressure_drop"],
        inlet_phase=inlet_phase,
        components=components,
    )
    return unit, {"inlet_phase": inlet_phase}


_VALVE: Final = ModelSignature(
    model_id=valve.MODEL_ID,
    ports=valve.PORTS,
    pins=(PinColumn("outlet_pressure", "pressure", "outlet"),),
)


def _valve(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _VALVE
    instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    unit = Valve(
        unit_id=view.unit_id,
        provider=provider,
        outlet_pressure=_pinned(view, signature, "outlet_pressure"),
        context=context,
        inlet_phase=inlet_phase,
        components=components,
    )
    return unit, {"inlet_phase": inlet_phase}


_LIQUID_PUMP: Final = ModelSignature(
    model_id=pump.MODEL_ID,
    ports=pump.PORTS,
    required=("efficiency",),
    pins=(PinColumn("outlet_pressure", "pressure", "outlet"),),
)


def _liquid_pump(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _LIQUID_PUMP
    parameters = instance_contract(view, signature, components)
    unit = LiquidPump(
        unit_id=view.unit_id,
        provider=provider,
        outlet_pressure=_pinned(view, signature, "outlet_pressure"),
        efficiency=parameters["efficiency"],
        context=context,
        components=components,
    )
    return unit, {}


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


def _conversion_reactor(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """`conversion.<k>` names the key `k`: the one reaction has exactly one."""
    signature = _CONVERSION_REACTOR
    stoichiometry = _names(signature, "nu.{component}", view, components)
    conversions = _names(signature, "conversion.{key}", view, components)
    parameters = instance_contract(view, signature, components)
    (conversion,) = conversions
    inlet_phase = _inlet_phase(view)
    option, column = _one_specification(view, signature, "energy_specification")
    energy_specification = option.name
    key_component = conversion.removeprefix("conversion.")
    unit = ConversionReactor(
        unit_id=view.unit_id,
        provider=provider,
        stoichiometry=tuple(parameters[name] for name in stoichiometry),
        key_component=key_component,
        conversion=parameters[conversion],
        energy_specification=energy_specification,
        value=_pin(view, column),
        context=context,
        pressure_drop=parameters["pressure_drop"],
        inlet_phase=inlet_phase,
        components=components,
    )
    return unit, {
        "inlet_phase": inlet_phase,
        "key_component": key_component,
        "energy_specification": energy_specification,
    }


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


def _kinetic_cstr(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """`damkohler.<k>` names the key `k`; the outlet is declared `vapor` or `liquid`."""
    signature = _KINETIC_CSTR
    stoichiometry = _names(signature, "nu.{component}", view, components)
    rates = _names(signature, "damkohler.{key}", view, components)
    parameters = instance_contract(view, signature, components)
    (rate,) = rates
    inlet_phase = _inlet_phase(view)
    phase = _declared_phase(view, "outlet")
    key_component = rate.removeprefix("damkohler.")
    unit = KineticCSTR(
        unit_id=view.unit_id,
        provider=provider,
        stoichiometry=tuple(parameters[name] for name in stoichiometry),
        key_component=key_component,
        damkohler=parameters[rate],
        reference_temperature=parameters["T_ref"],
        temperature_scale=parameters["T_scale"],
        coolant_flow=parameters["coolant_flow"],
        coolant_cp=parameters["coolant_cp"],
        coolant_temperature=parameters["T_coolant"],
        phase=phase,
        context=context,
        pressure_drop=parameters["pressure_drop"],
        inlet_phase=inlet_phase,
        components=components,
    )
    return unit, {"inlet_phase": inlet_phase, "key_component": key_component, "phase": phase}


_COMPONENT_SEPARATOR: Final = ModelSignature(
    model_id=component_separator.MODEL_ID,
    ports=component_separator.PORTS,
    required=("split.{component}",),
)


def _component_separator(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _COMPONENT_SEPARATOR
    split = _names(signature, "split.{component}", view, components)
    parameters = instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    top_phase = _declared_phase(view, "top")
    bottom_phase = _declared_phase(view, "bottom")
    unit = ComponentSeparator(
        unit_id=view.unit_id,
        provider=provider,
        split=tuple(parameters[name] for name in split),
        context=context,
        inlet_phase=inlet_phase,
        top_phase=top_phase,
        bottom_phase=bottom_phase,
        components=components,
    )
    return unit, {"inlet_phase": inlet_phase, "top_phase": top_phase, "bottom_phase": bottom_phase}


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


def _heat_exchanger(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """Each side keeps its declared phase: its outlet's rule is its inlet's."""
    signature = _HEAT_EXCHANGER
    instance_contract(view, signature, components)
    phases: dict[str, Phase] = {}
    for side in ("hot", "cold"):
        phases[side] = _declared_phase(view, f"{side}_inlet")
        _stream(view, f"{side}_outlet")
        _require_phase(view, f"{side}_outlet", phases[side])
    option, column = _one_specification(view, signature, "specification")
    unit = HeatExchanger(
        unit_id=view.unit_id,
        provider=provider,
        specification=option.name,
        value=_pin(view, column),
        context=context,
        hot_phase=phases["hot"],
        cold_phase=phases["cold"],
        components=components,
    )
    return unit, {
        "specification": option.name,
        "hot_phase": phases["hot"],
        "cold_phase": phases["cold"],
    }


#: Model id -> signature: what each builder reads (§1.3's table), for `list_models` (T07 §4.2).
MODEL_SIGNATURES: Final[Mapping[str, ModelSignature]] = {
    signature.model_id: signature
    for signature in (
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
}

#: Model id -> what an instance of it takes as a target path, for `parse_revision`'s
#: `specification_unsupported` hint on an instance target (ruling round 6, B2).
_INSTANCE_TARGETS: Final[Mapping[str, str]] = {
    model_id: _instance_targets(signature) for model_id, signature in MODEL_SIGNATURES.items()
}

#: Model id -> builder: the six K02 models, the six T05 ones (§1.3's table) and T08's kinetic
#: CSTR (build-first §A1).
MODEL_BUILDERS: Final[Mapping[str, Builder]] = {
    _FEED_SOURCE.model_id: _feed_source,
    _ADIABATIC_MIXER.model_id: _adiabatic_mixer,
    _TP_HEATER.model_id: _tp_heater,
    _TP_FLASH.model_id: _tp_flash,
    _STREAM_SPLITTER.model_id: _stream_splitter,
    _PRODUCT_SINK.model_id: _product_sink,
    _PH_FLASH.model_id: _ph_flash,
    _VALVE.model_id: _valve,
    _LIQUID_PUMP.model_id: _liquid_pump,
    _CONVERSION_REACTOR.model_id: _conversion_reactor,
    _COMPONENT_SEPARATOR.model_id: _component_separator,
    _HEAT_EXCHANGER.model_id: _heat_exchanger,
    _KINETIC_CSTR.model_id: _kinetic_cstr,
}


class _PinReader(Mapping[str, float]):
    """An instance's pins, recording which the builder read."""

    def __init__(self, pins: Mapping[str, float]) -> None:
        self._pins = dict(pins)
        self.read: set[str] = set()

    def __getitem__(self, key: str) -> float:
        value = self._pins[key]
        self.read.add(key)
        return value

    def __contains__(self, key: object) -> bool:
        return key in self._pins

    def __iter__(self) -> Iterator[str]:
        return iter(self._pins)

    def __len__(self) -> int:
        return len(self._pins)


def _first_line(error: Exception) -> str:
    return (str(error).splitlines() or [""])[0]


def _inadmissible(error: SpecificationError, instance: str | None) -> Unbound:
    """T07 ruling round 5, S3: a value the document fixes, refused by the model it names at
    construction, implicating that model's instance."""
    return Unbound(
        "inadmissible",
        f"value_outside_model_domain: {_first_line(error)}",
        () if instance is None else (instance,),
    )


def _refusing_unit(flowsheet: RevisionFlowsheet) -> str | None:
    """The first instance whose own contribution raises `SpecificationError`, or `None` when the
    refusal is the assembled flowsheet's rather than one unit's."""
    for unit in flowsheet.units():
        try:
            unit.contribute(flowsheet.wiring[unit.unit_id], flowsheet.components)
        except SpecificationError:
            return unit.unit_id
    return None


def bind_revision_flowsheet(document: Mapping[str, Any]) -> RevisionBinding | Unbound:
    """Build and bind a revision's flowsheet, or say which of R-022's kinds prevented it (§1.4)."""
    from openflowsheet.orchestrator.budget import PropertyMeter
    from openflowsheet.thermo.syn001 import Syn001Provider

    # R-088 Q29 (T07 design note §12.5): a non-canonical number is refused typed at entry,
    # whether or not a reader reads its field; in a field nothing reads, a digest would
    # otherwise raise untyped.
    pointer = first_noncanonical(document)
    if pointer is not None:
        return Unbound("unsupported", f"document_not_canonical({pointer})")

    try:
        view = parse_revision(document, _INSTANCE_TARGETS)
        sources = pin_specifications(document)
    except RevisionError as error:
        return Unbound(error.kind, error.code, hint=error.hint)

    for instance in view.instances:
        if instance.model_id not in MODEL_BUILDERS:
            return Unbound("unsupported", f"model_unsupported({instance.model_id})")

    # Metered from construction: the declaration's property blocks capture the provider here,
    # and a plan run counts their calls (T02; `PropertyMeter`).
    provider = PropertyMeter(Syn001Provider())
    built: list[tuple[InstanceView, UnitModel, Configuration, _PinReader]] = []
    for instance in view.instances:
        reader = _PinReader(instance.pins)
        try:
            unit, configuration = MODEL_BUILDERS[instance.model_id](
                replace(instance, pins=reader), provider, _CONTEXT, view.components
            )
        except RevisionError as error:
            return Unbound(error.kind, error.code, hint=error.hint)
        except SpecificationError as error:
            # T07 ruling round 5, S3: this binder refuses `role: free`, so every value a model
            # refuses here is one the document fixes.
            return _inadmissible(error, instance.unit_id)
        if unit.model_id != instance.model_id or unit.unit_id != instance.unit_id:
            raise ValueError(
                f"builder for {instance.model_id} built {unit.model_id} {unit.unit_id!r}"
            )
        built.append((instance, unit, configuration, reader))

    for instance, unit, _, _ in built:
        declared = {port.name: port for port in unit.ports()}
        for port, connected in instance.ports.items():
            spec_port = declared.get(port)
            where = f"{instance.unit_id}.{port}"
            if spec_port is None or spec_port.kind != "material":
                return Unbound("unsupported", f"port_unsupported({where})")
            if spec_port.direction != instance.directions[port]:
                return Unbound("unsupported", f"port_direction_unsupported({where})")
            if spec_port.multiplicity == 1 and len(connected) != 1:
                return Unbound("unsupported", f"port_multiplicity_unsupported({where})")
        for name, spec_port in declared.items():
            if spec_port.kind == "material" and name not in instance.ports:
                return Unbound("incomplete", f"port_unwired({instance.unit_id}.{name})")

    for instance, _, _, reader in built:
        unread = [column for column in instance.pins if column not in reader.read]
        if unread:
            return Unbound(
                "unsupported",
                f"specification_unconsumed({sources[unread[0]][0]})",
                hint=_unconsumed_hint(instance, unread[0], view.components),
            )

    flowsheet = RevisionFlowsheet(
        provider=provider,
        context=_CONTEXT,
        components=view.components,
        instances=tuple(unit for _, unit, _, _ in built),
        wiring={instance.unit_id: instance.wiring for instance in view.instances},
        streams=view.streams,
        configuration_sha256=configuration_sha256(
            view, {instance.unit_id: configuration for instance, _, configuration, _ in built}
        ),
    )
    try:
        spec = flowsheet.spec()
        row_units = {
            equation.equation_id: unit.unit_id
            for unit in flowsheet.units()
            for equation in unit.contribute(
                flowsheet.wiring[unit.unit_id], flowsheet.components
            ).equations
        }
    except SpecificationError as error:
        return _inadmissible(error, _refusing_unit(flowsheet))

    units = tuple(instance.unit_id for instance in view.instances)
    producers = {stream: producer for stream, producer, _ in view.edges}
    graph = ProcessGraph(
        units=units,
        connections=tuple(
            Connection(
                stream_id=stream,
                producer=producer,
                consumer=consumer,
                state_columns=(
                    *(flow_id(stream, c) for c in view.components),
                    temperature_id(stream),
                    pressure_id(stream),
                ),
            )
            for stream, producer, consumer in sorted(set(view.edges))
        ),
        instance_ids={unit: unit for unit in units},
        column_owners=_column_owners(spec.variable_ids, producers, units),
    )
    return RevisionBinding(
        flowsheet=flowsheet,
        spec=spec,
        graph=graph,
        row_units=row_units,
        revision_sha256=document_sha256(document),
        input_mapping=view.input_mapping,
        specification_pins={
            instance.unit_id: {column: sources[column][0] for column in instance.pins}
            for instance in view.instances
        },
    )
