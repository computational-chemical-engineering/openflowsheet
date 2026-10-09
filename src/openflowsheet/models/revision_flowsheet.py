"""A flowsheet built from a `ProcessRevision`: parsing, the label, and the sequential traversal.

T05 design note `docs/design/T05-generalization.md` §1.3–§1.5 (register R-045, R-047).
`Syn001Flowsheet` is SYN-001's and stays so; every later flowsheet is built here, from a revision
document read by the fixed rules R1–R6 of §1.3 — no new schema field, and no default: an input the
revision does not state is refused, never supplied (D5).

**Three things live here.** `parse_revision` reads the document into a `RevisionView` — instances
in declaration order, streams in allocation order, each instance's wired ports, declared phases,
parameters and the *pins* the revision's `role: fixed` specifications route to it — and refuses,
typed (`RevisionError`, R-022's three kinds), what the rules cannot read. `RevisionFlowsheet`
holds the constructed units and assembles them with K02's `assemble`, unchanged, under a label
that carries `configuration_sha256`: the revision minus every pinned value, i.e. exactly what
selects expressions without changing ids (ADR 0002 D2.7, met by the label as SYN-001 meets it).
And `traverse` runs the units causally in declaration order, tearing a stream only where the
graph deadlocks — the start of the one EO region a revision-built flowsheet is solved as (D2).

Constructing the units is not here: the builder table is the application layer's
(`application.revision_binding.MODEL_BUILDERS`), which is where a revision meets the model zoo.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, overload

from openflowsheet.canonical import document_sha256
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    PortDirection,
    SpecificationError,
    UnitEvaluation,
    UnitModel,
    Wiring,
    assemble,
    duty_id,
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.syn001 import PROVIDER_ID as SYN001_PROVIDER_ID
from openflowsheet.models.syn001.flowsheet import MODEL_LABEL
from openflowsheet.thermo import Phase, PropertyProvider, PropertyStatus, StreamState, pr_c1
from openflowsheet.units import (
    CONVERSION_ROWS,
    KIND_SI_UNITS,
    UnitConversion,
    UnitConversionError,
    check_quantity,
    convert_input_value,
    read_number,
)

__all__ = [
    "MOLECULAR_WEIGHTS",
    "SYN001_BASIS",
    "ComponentBasis",
    "PHASE_CAPABILITIES",
    "TARGET_PATH_KINDS",
    "FlowsheetPass",
    "InputMapping",
    "InstanceView",
    "RevisionError",
    "RevisionFlowsheet",
    "RevisionView",
    "canonical_components",
    "component_basis",
    "configuration_sha256",
    "convert_specification",
    "parse_revision",
    "pin_specifications",
    "read_parameter",
    "required_kind",
    "si_unit",
]

#: R1: no `.` or `:`, which K02's variable and row ids use as separators.
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
#: R2: the verifier's `stream_of` and `k_values` assume exactly these. The provider's own
#: `describe().components`, which a test asserts this equals, so the two cannot drift; a declared
#: component set is mapped onto it (`canonical_components`, T06 spec §8.6).
_COMPONENTS = ("A", "B", "C")
#: SYN-001's `ComponentRecord.molecular_weight`, kg/mol, **by component id** (plan §3.1;
#: `benchmarks/syn001/components.yaml`, which a test asserts this equals, as it asserts
#: `conversion_reactor.MOLAR_MASSES` equals it in the provider's order). `unit-conversion-v2`'s
#: mass basis reads it (ADR 0016 D3; T06 spec §8.5); never indexed by position. A revision whose
#: `component_set.record_source` names the C1 records reads the C1 basis instead (ADR 0034 D8).
MOLECULAR_WEIGHTS: Mapping[str, float] = MappingProxyType({"A": 0.100, "B": 0.100, "C": 0.100})


@dataclass(frozen=True)
class ComponentBasis:
    """The component set, molar masses and property provider a revision binds on (ADR 0034 D8).

    Selected by the revision's `component_set.record_source` (`component_basis`): the C1 records'
    path (`benchmarks/m01/components.yaml`, the string `pr_c1.RECORDS_PATH` names) selects
    `pr-c1-v1`; **every other value**, absent included, selects SYN-001 exactly as before M02, when
    `record_source` was not read at bind time (T06 spec §15's v0.1 limit).
    """

    #: The provider's `describe().provider_id`; the binder and the verifier construct it.
    provider_id: str
    #: The provider's component order, onto which a declared permutation is mapped (§8.6).
    components: tuple[str, ...]
    #: kg/mol by component id, `unit-conversion-v2`'s mass basis (ADR 0016 D3).
    molecular_weights: Mapping[str, float]


#: SYN-001's basis: every revision whose `record_source` does not name the C1 records.
SYN001_BASIS: ComponentBasis = ComponentBasis(SYN001_PROVIDER_ID, _COMPONENTS, MOLECULAR_WEIGHTS)


def _c1_basis() -> ComponentBasis:
    """`pr-c1-v1`'s basis: its components and the records' molar masses (`load_records` reads the
    file once per process)."""
    records = pr_c1.load_records()
    return ComponentBasis(
        pr_c1.PROVIDER_ID,
        pr_c1.COMPONENTS,
        MappingProxyType({record.id: record.molar_mass for record in records.components}),
    )


def component_basis(document: Mapping[str, Any]) -> ComponentBasis:
    """The basis `document`'s `component_set.record_source` selects (ADR 0034 D8, R-231)."""
    source = (document.get("component_set") or {}).get("record_source")
    return _c1_basis() if source == pr_c1.RECORDS_PATH else SYN001_BASIS


#: R4: a connection's `phase_capability` as the declared phase of the ports it joins.
_DECLARED: Mapping[str, Phase | None] = {"liquid": "LIQUID", "vapor": "VAPOR", "vapor_liquid": None}
#: R6: the kind each parameter of §1.3's table is a value of, by its name up to the first `.`
#: (`nu.A` is `nu`). A value in another unit is converted to that kind's SI unit by
#: `unit-conversion-v2` (ADR 0016) or refused, never read as SI. A name not here is its builder's
#: to refuse.
_PARAMETER_KINDS: Mapping[str, str] = {
    "pressure_drop": "pressure",
    "split_fraction": "dimensionless",
    "efficiency": "dimensionless",
    "nu": "dimensionless",
    "conversion": "dimensionless",
    "split": "dimensionless",
    # T08 build-first §A1.2: the kinetic CSTR's pins, in kinds that already exist (§A1.1 (2)).
    "damkohler": "dimensionless",
    "T_ref": "temperature",
    "T_scale": "temperature_difference",
    "coolant_flow": "molar_flow",
    "coolant_cp": "molar_heat_capacity",
    "T_coolant": "temperature",
}
#: R5: the kind of the value a specification of each target path pins.
_PATH_KINDS: Mapping[str, str] = {
    "state.n": "molar_flow",
    "state.T": "temperature",
    "state.P": "pressure",
    "outlet.T": "temperature",
    "outlet.P": "pressure",
    "duty.Q": "heat_rate",
}
#: The target-path table, read-only: what `list_models`, the tool descriptions and the hints of
#: ruling round 6 (B2) derive the accepted encodings from.
TARGET_PATH_KINDS: Mapping[str, str] = MappingProxyType(_PATH_KINDS)
#: R4 in the document's words: a declared phase as the `phase_capability` that declares it.
PHASE_CAPABILITIES: Mapping[Phase | None, str] = MappingProxyType(
    {phase: capability for capability, phase in _DECLARED.items()}
)
#: The configuration digest's scheme tag, and the label's prefix.
_SCHEME = "FSR1"

RevisionErrorKind = Literal["conflict", "incomplete", "unsupported"]


class RevisionError(ValueError):
    """A revision the rules of §1.3 cannot build, in R-022's three kinds, with a stable code.

    `hint` (T07 design note ruling round 6, B2) says what would be accepted, computed where the
    rule compared: the encodings a missing pin takes, the kind and units a target path takes. It
    travels beside the code and never changes it: the codes are registered strings.
    """

    def __init__(self, kind: RevisionErrorKind, code: str, hint: str | None = None) -> None:
        super().__init__(f"{kind}: {code}")
        self.kind: RevisionErrorKind = kind
        self.code = code
        self.hint = hint


@dataclass(frozen=True)
class InstanceView:
    """One revision instance as the builder reads it."""

    unit_id: str
    model_id: str
    #: Wired material port -> its streams, in connection order (R1).
    ports: Mapping[str, tuple[str, ...]]
    #: From `to.port` (inlet) and `from.port` (outlet).
    directions: Mapping[str, Literal["inlet", "outlet"]]
    #: R4, per wired port: `None` is a lifted (`vapor_liquid`) port.
    phases: Mapping[str, Phase | None]
    #: R6: instance `parameters`, each Quantity's `value`.
    parameters: Mapping[str, float]
    #: R5: column id -> the value a `role: fixed` specification pins it to, routed here.
    pins: Mapping[str, float]
    #: `model.version` and `model.artifact_ref` as declared, `None` when absent (M02 design note
    #: §6.1): a variant-backed model's variant id and its SHA-256, which the binder resolves.
    model_version: str | None = None
    model_artifact_ref: str | None = None

    @property
    def wiring(self) -> Wiring:
        return Wiring(dict(self.ports))


@dataclass(frozen=True)
class InputMapping:
    """How a binding read its revision's inputs (T06 spec §8.5 *Records*).

    Recorded where the binding is recorded, never in the certificate, which judges the
    declaration (R-035). Every registered revision declares the canonical order and has no
    conversion (ADR 0016 D7).
    """

    #: `component_set.components` as declared: a permutation of the provider's order, which the
    #: binding uses instead (T06 spec §8.6). Always recorded, the canonical order included.
    #: Presenting results in this order is T07's.
    declared_components: tuple[str, ...] = ()
    #: Every `unit-conversion-v2` conversion (ADR 0016 D6): specifications in document order,
    #: then parameters by instance declaration order and, within an instance, by parameter name in
    #: code-point order — a function of the canonical revision, not of a mapping's key order.
    conversions: tuple[UnitConversion, ...] = ()


@dataclass(frozen=True)
class RevisionView:
    components: tuple[str, ...]
    #: Declaration order.
    instances: tuple[InstanceView, ...]
    #: Allocation order.
    streams: tuple[str, ...]
    #: `(stream, producer, consumer)`, in connection order.
    edges: tuple[tuple[str, str, str], ...]
    input_mapping: InputMapping = InputMapping()
    #: The basis `component_set.record_source` selected (ADR 0034 D8).
    basis: ComponentBasis = SYN001_BASIS


def parse_revision(
    document: Mapping[str, Any], instance_targets: Mapping[str, str] | None = None
) -> RevisionView:
    """Read a revision by R1–R5. Raises `RevisionError`; R6 is each builder's to apply.

    `instance_targets` (model id -> the instance target paths that model takes, as a phrase) is
    the builder table's, handed in so that a refused instance target's hint can name what its
    model reads (ruling round 6, B2); without it that hint is `None`. It changes no code.
    """
    return _read(document, instance_targets)[0]


def pin_specifications(document: Mapping[str, Any]) -> Mapping[str, tuple[str, ...]]:
    """Column id -> the ids of the specifications that pin it, as `parse_revision` routed them.

    What a refusal names when a builder leaves a pin unconsumed: the user wrote a specification,
    not a column.
    """
    return _read(document)[1]


def _require_id(value: Any) -> str:
    text = str(value if value is not None else "")
    if not _ID.match(text):
        raise RevisionError("unsupported", f"id_unsupported({text})")
    return text


def canonical_components(declared: Any, basis: ComponentBasis = SYN001_BASIS) -> tuple[str, ...]:
    """The provider's component order for a declared `component_set.components` (T06 spec §8.6,
    ADR 0014 D9, register R-076).

    A declared list is accepted iff it is a permutation of `basis.components` (SYN-001's
    `_COMPONENTS` unless the revision names the C1 records, ADR 0034 D8) — same length, no
    repetition, same members — and the provider's order is returned: every component-keyed input
    (`target.component`, `nu.<c>`, `conversion.<c>`, `split.<c>`, `<S>.n.<c>`) is keyed by id, so
    nothing is re-keyed and nothing downstream sees the declared order. Anything else (a missing,
    extra, unknown or repeated component) raises `RevisionError("unsupported",
    "components_unsupported")`. Called by `_read` and by the legacy binding, so both paths and
    the verifier's own `parse_revision` see one order.
    """
    members = tuple(declared or ())
    if (
        len(members) != len(basis.components)
        or not all(isinstance(member, str) for member in members)
        or set(members) != set(basis.components)
    ):
        raise RevisionError("unsupported", "components_unsupported")
    return basis.components


def _connection_hint() -> str:
    """The `specification_unsupported` hint of a connection target, from the target-path table
    (ruling round 6, B2); `{components}` is filled with the document's component set."""

    def path(name: str) -> str:
        kind = _PATH_KINDS[name]
        return f"{name} ({kind}, {KIND_SI_UNITS[kind]})"

    kind = _PATH_KINDS["state.n"]
    return (
        f"A connection target takes path {path('state.T')}, {path('state.P')} or state.n with a "
        f"component of {{components}} ({kind}, {KIND_SI_UNITS[kind]})."
    )


_CONNECTION_HINT = _connection_hint()


def _instance_hint(unit: str, model: str, targets: Mapping[str, str]) -> str | None:
    """The `specification_unsupported` hint of an instance target: what its model reads, from
    the builder table's `targets`; `None` for a model not handed in."""
    return f"Instance {unit} ({model}) {targets[model]}." if model in targets else None


def _read(
    document: Mapping[str, Any], instance_targets: Mapping[str, str] | None = None
) -> tuple[RevisionView, dict[str, tuple[str, ...]]]:
    declared_components = tuple((document.get("component_set") or {}).get("components") or ())
    basis = component_basis(document)
    components = canonical_components(declared_components, basis)
    component_set = ", ".join(str(component) for component in declared_components)
    targets = instance_targets or {}

    # R1: instances, in declaration order; R6 reads each parameter in SI (ADR 0016 D5).
    instances: dict[str, dict[str, Any]] = {}
    parameter_conversions: list[UnitConversion] = []
    for entry in document.get("instances") or ():
        unit = _require_id(entry.get("id"))
        if unit in instances:
            raise RevisionError("conflict", f"id_duplicate({unit})")
        parameters, converted = _parameters(
            unit, entry.get("parameters") or {}, basis.molecular_weights
        )
        parameter_conversions.extend(converted)
        model = entry.get("model") or {}
        instances[unit] = {
            "model": str(model.get("id", "")),
            "version": model.get("version"),
            "artifact_ref": model.get("artifact_ref"),
            "parameters": parameters,
            "ports": {},
            "directions": {},
            "capabilities": {},
            "pins": {},
        }
    if not instances:
        raise RevisionError("incomplete", "instances_missing")

    # R1, R3: material connections, in stream order.
    streams: list[str] = []
    edges: list[tuple[str, str, str]] = []
    for entry in document.get("connections") or ():
        stream = _require_id(entry.get("id"))
        if stream in streams:
            raise RevisionError("conflict", f"id_duplicate({stream})")
        if entry.get("kind") != "material":
            raise RevisionError("unsupported", f"connection_kind_unsupported({stream})")
        capability = entry.get("phase_capability")
        if capability is None:
            raise RevisionError("incomplete", f"phase_capability_missing({stream})")
        if capability not in _DECLARED:
            raise RevisionError("unsupported", f"phase_capability_unsupported({stream})")
        ends: list[str] = []
        for end, direction in (("from", "outlet"), ("to", "inlet")):
            endpoint = entry.get(end) or {}
            owner, port = endpoint.get("instance"), endpoint.get("port")
            if not owner or not port:
                raise RevisionError("incomplete", f"endpoint_missing({stream}.{end})")
            if owner not in instances:
                raise RevisionError("incomplete", f"instance_missing({owner})")
            record = instances[owner]
            if record["directions"].setdefault(port, direction) != direction:
                raise RevisionError("conflict", f"port_direction_conflict({owner}.{port})")
            record["ports"].setdefault(port, []).append(stream)
            record["capabilities"].setdefault(port, set()).add(capability)
            ends.append(str(owner))
        streams.append(stream)
        edges.append((stream, ends[0], ends[1]))
    producers = {stream: producer for stream, producer, _ in edges}

    # R4: one declared phase per port.
    phases: dict[str, dict[str, Phase | None]] = {}
    for unit, record in instances.items():
        phases[unit] = {}
        for port, capabilities in record["capabilities"].items():
            if len(capabilities) != 1:
                raise RevisionError("unsupported", f"port_phase_ambiguous({unit}.{port})")
            (capability,) = capabilities
            phases[unit][port] = _DECLARED[capability]

    # R5: fixed specifications become pins, routed to the owner of the column they fix. Each
    # value is read in SI by `unit-conversion-v2` (ADR 0016 D5, reader R2), after its component:
    # a component outside the set is refused as such whatever the unit (ADR 0016 D5).
    sources: dict[str, list[str]] = {}
    conversions: list[UnitConversion] = []
    for entry in document.get("specifications") or ():
        name = str(entry.get("id", ""))
        if entry.get("role") != "fixed":
            raise RevisionError("unsupported", f"specification_role_unsupported({name})")
        target = entry.get("target") or {}
        object_type, object_id = target.get("object_type"), str(target.get("object_id", ""))
        path = str(target.get("path", ""))
        if target.get("component") is not None and target.get("component") not in components:
            raise RevisionError(
                "unsupported",
                f"specification_unsupported({name})",
                f"Component {target.get('component')} is not in the component set {component_set}.",
            )
        value, conversion = convert_specification(
            entry,
            _number(entry.get("value"), f"specification_value_unreadable({name})"),
            basis.molecular_weights,
        )
        if conversion is not None:
            conversions.append(conversion)
        if object_type == "connection":
            if object_id not in producers:
                raise RevisionError("incomplete", f"specification_target_unknown({name})")
            owner = producers[object_id]
            component = target.get("component")
            if path == "state.n" and component in components:
                columns: tuple[str, ...] = (flow_id(object_id, str(component)),)
            elif path == "state.T" and component is None:
                columns = (temperature_id(object_id),)
            elif path == "state.P" and component is None:
                columns = (pressure_id(object_id),)
            else:
                raise RevisionError(
                    "unsupported",
                    f"specification_unsupported({name})",
                    _CONNECTION_HINT.format(components=component_set),
                )
        elif object_type == "instance":
            if object_id not in instances:
                raise RevisionError("incomplete", f"specification_target_unknown({name})")
            owner = object_id
            record = instances[owner]
            if path.startswith("parameters."):
                parameter = path.removeprefix("parameters.")
                declared = record["parameters"].setdefault(parameter, value)
                if declared != value:
                    raise RevisionError(
                        "conflict", f"specification_conflict({name}, {owner}.{parameter})"
                    )
                continue
            if path in ("outlet.T", "outlet.P"):
                outlets = [
                    stream
                    for port, direction in record["directions"].items()
                    if direction == "outlet"
                    for stream in record["ports"][port]
                ]
                if not outlets:
                    raise RevisionError(
                        "unsupported",
                        f"specification_unsupported({name})",
                        _instance_hint(owner, record["model"], targets),
                    )
                identify = temperature_id if path == "outlet.T" else pressure_id
                columns = tuple(identify(stream) for stream in outlets)
            elif path == "duty.Q":
                columns = (duty_id(owner),)
            else:
                raise RevisionError(
                    "unsupported",
                    f"specification_unsupported({name})",
                    _instance_hint(owner, record["model"], targets),
                )
        else:
            raise RevisionError("unsupported", f"specification_unsupported({name})")
        pins: dict[str, float] = instances[owner]["pins"]
        for column in columns:
            if column in pins and pins[column] != value:
                raise RevisionError(
                    "conflict", f"specification_conflict({sources[column][0]}, {name})"
                )
            pins[column] = value
            sources.setdefault(column, []).append(name)

    view = RevisionView(
        components=components,
        instances=tuple(
            InstanceView(
                unit_id=unit,
                model_id=record["model"],
                ports={port: tuple(connected) for port, connected in record["ports"].items()},
                directions=dict(record["directions"]),
                phases=phases[unit],
                parameters=dict(record["parameters"]),
                pins=dict(record["pins"]),
                model_version=_optional_text(record["version"]),
                model_artifact_ref=_optional_text(record["artifact_ref"]),
            )
            for unit, record in instances.items()
        ),
        streams=tuple(streams),
        edges=tuple(edges),
        input_mapping=InputMapping(
            declared_components=declared_components,
            conversions=(*conversions, *parameter_conversions),
        ),
        basis=basis,
    )
    return view, {column: tuple(names) for column, names in sources.items()}


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _number(value: Any, code: str) -> float:
    number = read_number(value)
    if number is None:
        raise RevisionError("unsupported", code)
    return number


def required_kind(path: str) -> str | None:
    """The kind of the value a specification of target `path` pins (R5, R6), or `None` where
    neither table names the path. The one target-path table: every reader of a specification
    value asks it here (T06 spec §8.5)."""
    return _PATH_KINDS.get(path) or _PARAMETER_KINDS.get(
        path.removeprefix("parameters.").split(".")[0]
    )


@overload
def convert_specification(
    entry: Mapping[str, Any],
    value: float,
    molecular_weights: Mapping[str, float] = MOLECULAR_WEIGHTS,
) -> tuple[float, UnitConversion | None]: ...


@overload
def convert_specification(
    entry: Mapping[str, Any],
    value: None,
    molecular_weights: Mapping[str, float] = MOLECULAR_WEIGHTS,
) -> tuple[None, None]: ...


def convert_specification(
    entry: Mapping[str, Any],
    value: float | None,
    molecular_weights: Mapping[str, float] = MOLECULAR_WEIGHTS,
) -> tuple[float | None, UnitConversion | None]:
    """A specification's `value` (as its reader read it) in its target's SI unit, by
    `unit-conversion-v2` (ADR 0016), with the conversion's record or `None`.

    Every reader of a specification value goes through here: the legacy binding (R1), `_read`
    (R2), `verify_bound`'s `_revision_values` (R3) and validation's `DIM-01` (R4); each judges the
    target's component first, in its own vocabulary (ADR 0016 D5). Refusals are the revision
    binding's registered codes, `specification_kind_unsupported(<id>)`,
    `specification_unit_unsupported(<id>)` and `specification_value_unsupported(<id>)`, raised as
    `RevisionError`. `molecular_weights` is the revision's basis's (`component_basis`), SYN-001's
    by default.
    """
    name = str(entry.get("id", ""))
    target = entry.get("target") or {}
    path = str(target.get("path", ""))
    component = target.get("component")
    try:
        return convert_input_value(
            name,
            value,
            entry.get("unit"),
            entry.get("kind"),
            required_kind(path),
            path,
            None if component is None else str(component),
            molecular_weights,
        )
    except UnitConversionError as error:
        hint = None
        if error.reason == "kind":
            hint = kind_hint(path, required_kind(path), entry.get("kind"))
        elif error.reason == "unit":
            hint = units_hint(required_kind(path) or entry.get("kind"))
        raise RevisionError(
            "unsupported", f"specification_{error.reason}_unsupported({name})", hint
        ) from None


def si_unit(kind: str) -> str:
    """The SI unit `unit-conversion-v2` converts `kind` to (ADR 0001 D1.1, ADR 0016 D3)."""
    return KIND_SI_UNITS[kind]


#: How a row of ADR 0016 D3 restricts its target, in a hint's words.
_TARGET_CLASS_WORDS: Mapping[str, str] = MappingProxyType(
    {
        "any": "",
        "component": " (one component)",
        "mass": " (one component, mass basis)",
        "fraction": " (a fraction parameter)",
    }
)


def kind_hint(path: str, required: str | None, declared: Any) -> str | None:
    """`specification_kind_unsupported`'s hint (ruling round 6, B2): the kind target `path`
    takes and its SI unit, then any other kind a row of `unit-conversion-v2` converts to it, with
    what that row asks of the target (ADR 0016 D3); and the kind the specification declares."""
    if required is None:
        return None
    others = {
        kind: _TARGET_CLASS_WORDS[row.target_class]
        for (target, _), row in CONVERSION_ROWS.items()
        if target == required
        for kind in sorted(row.declared_kinds)
        if kind != required
    }
    also = "".join(f", or kind {kind}{words}" for kind, words in others.items())
    return (
        f"Target path {path} takes kind {required} (SI unit {si_unit(required)}){also}; "
        f"this specification has kind {declared}."
    )


def units_hint(kind: Any) -> str | None:
    """`specification_unit_unsupported`'s hint (ruling round 6, B2): `kind`'s SI unit, then its
    units in ADR 0016 D3's table, each with what the row asks of its target."""
    if not isinstance(kind, str) or kind not in KIND_SI_UNITS:
        return None
    units = [si_unit(kind)] + [
        f"{unit}{_TARGET_CLASS_WORDS[row.target_class]}"
        for (target, unit), row in CONVERSION_ROWS.items()
        if target == kind
    ]
    return f"Kind {kind} takes the units {', '.join(units)}."


def _parameters(
    unit: str, parameters: Mapping[str, Any], molecular_weights: Mapping[str, float]
) -> tuple[dict[str, float], list[UnitConversion]]:
    """R6: each parameter's Quantity `value` in its kind's SI unit, from a Quantity whose SI twin
    `check_quantity` passes whole; and the conversions, by parameter name in code-point order
    (ADR 0016 D6)."""
    values: dict[str, float] = {}
    conversions: list[UnitConversion] = []
    for name, quantity in parameters.items():
        values[str(name)], conversion = read_parameter(unit, str(name), quantity, molecular_weights)
        if conversion is not None:
            conversions.append(conversion)
    return values, sorted(conversions, key=lambda conversion: conversion.input_id)


def read_parameter(
    unit: str,
    name: str,
    quantity: Any,
    molecular_weights: Mapping[str, float] = MOLECULAR_WEIGHTS,
) -> tuple[float, UnitConversion | None]:
    """R6 for one instance parameter (ADR 0016 D1, D5): its Quantity `value` in the SI unit of the
    kind its name requires, converted by `unit-conversion-v2` when written in a unit of ADR 0016's
    table, with the conversion's record or `None`; the Quantity must pass `check_quantity` as its
    **SI twin** (`value`, `bounds` and `nominal` converted by the same row, `unit` the SI unit).
    Raises `RevisionError`: `parameter_kind_unsupported(<instance>.<name>)`,
    `parameter_unit_unsupported(…)`, `parameter_quantity_invalid(…)` (a nonfinite or overflowing
    value included, and an integer in `value`, `bounds` or `nominal` that is not the canonical
    spelling of a binary64: `read_number`, T06 §8.5 (A5), ADR 0002 Amendment 1). The legacy
    binding and `DIM-01` read parameters here too, so all three refuse with the same codes."""
    where = f"{unit}.{name}"
    if not isinstance(quantity, Mapping):
        raise RevisionError("unsupported", f"parameter_unreadable({where})")
    codes = {
        "kind": f"parameter_kind_unsupported({where})",
        "unit": f"parameter_unit_unsupported({where})",
        "value": f"parameter_quantity_invalid({where})",
    }

    def convert(raw: Any) -> tuple[Any, UnitConversion | None]:
        # A value that is not a number is not a unit's fault: its unit and kind are still judged,
        # and `check_quantity` reports it.
        number = read_number(raw)
        converted, conversion = convert_input_value(
            where,
            number,
            quantity.get("unit"),
            quantity.get("kind"),
            _PARAMETER_KINDS.get(name.split(".")[0]),
            f"parameters.{name}",
            None,
            molecular_weights,
            source="parameter",
        )
        return (raw if number is None else converted), conversion

    try:
        _, conversion = convert(quantity.get("value"))
        twin: Mapping[str, Any] = quantity
        if conversion is not None:
            converted = {**quantity, "value": conversion.si_value, "unit": conversion.si_unit}
            bounds = quantity.get("bounds")
            if isinstance(bounds, Mapping):
                converted["bounds"] = {
                    **bounds,
                    **{
                        side: convert(bounds[side])[0]
                        for side in ("lower", "upper")
                        if bounds.get(side) is not None
                    },
                }
            if quantity.get("nominal") is not None:
                converted["nominal"] = convert(quantity["nominal"])[0]
            twin = converted
    except UnitConversionError as error:
        raise RevisionError("unsupported", codes[error.reason]) from None
    if check_quantity(twin):
        raise RevisionError("unsupported", codes["value"])
    return _number(twin.get("value"), f"parameter_unreadable({where})"), conversion


def configuration_sha256(
    view: RevisionView, configurations: Mapping[str, Mapping[str, str | None]]
) -> str:
    """ADR 0002's `document_sha256` of the revision minus every pinned value.

    What selects expressions without changing ids: the components, the streams in allocation
    order, and per instance in declaration order its model, its wired ports with their streams in
    connection order, and the configuration its builder reported (§1.3's last column).
    """
    return document_sha256(
        {
            "scheme": _SCHEME,
            "components": list(view.components),
            "streams": list(view.streams),
            "instances": [
                {
                    "unit": instance.unit_id,
                    "model": instance.model_id,
                    "ports": {port: list(connected) for port, connected in instance.ports.items()},
                    "configuration": dict(configurations[instance.unit_id]),
                }
                for instance in view.instances
            ],
        }
    )


@dataclass(frozen=True)
class FlowsheetPass:
    """One sequential pass over a revision-built flowsheet (§1.5)."""

    status: PropertyStatus
    #: Every stream's value in this pass; a torn stream carries its guess.
    streams: Mapping[str, StreamState]
    #: By unit id.
    evaluations: Mapping[str, UnitEvaluation]
    #: Evaluation order.
    order: tuple[str, ...]
    #: Streams used before they were produced, in first-use order.
    torn: tuple[str, ...]
    #: `G(guess)` of each torn stream.
    computed_torn: Mapping[str, StreamState]
    failed_unit: str = ""
    #: The first line of the failing unit's message.
    code: str = ""


@dataclass(frozen=True)
class RevisionFlowsheet:
    """A flowsheet assembled from a revision's instances, by `assemble`, unchanged."""

    #: `PropertyMeter(Syn001Provider())`, metered from construction (as `bind_revision` does).
    provider: PropertyProvider
    context: EvaluationContext
    components: tuple[str, ...]
    #: Declaration order.
    instances: tuple[UnitModel, ...]
    wiring: Mapping[str, Wiring]
    #: Allocation order.
    streams: tuple[str, ...]
    configuration_sha256: str

    def units(self) -> tuple[UnitModel, ...]:
        return self.instances

    @property
    def label(self) -> str:
        """`FSR1-<configuration[:12]>-<provider>-<impl[:12]>-<data[:12]>` (register R-047).

        The provider half is `Syn001Flowsheet.label`'s, for its reason: the property package is
        part of the equations. The configuration half replaces SYN-001's fixed `SYN001-fs1`,
        because here the equation set is whatever the revision wired and configured. Pinned
        values are not in it (ADR 0008 D4.1): they are `constants_sha256`'s.
        """
        capabilities = self.provider.describe()
        label = (
            f"{_SCHEME}-{self.configuration_sha256[:12]}"
            f"-{capabilities.provider_id}"
            f"-{capabilities.implementation_sha256[:12]}"
            f"-{capabilities.data_sha256[:12]}"
        )
        if not MODEL_LABEL.match(label):
            raise SpecificationError(
                f"the flowsheet label {label!r} ({len(label)} characters) does not fit ADR "
                "0002's model_version pattern: at most 64 characters of letters, digits, dot, "
                "dash and underscore"
            )
        return label

    def spec(self) -> ProblemSpec:
        """The whole flowsheet as one `ProblemSpec`, assembled exactly as declared."""
        return assemble(
            label=self.label,
            units=list(self.instances),
            wiring=self.wiring,
            streams=self.streams,
            components=self.components,
        )

    def _streams(self, unit: UnitModel, direction: PortDirection) -> tuple[str, ...]:
        """A unit's material streams in one direction: ports in `ports()` order, then R1 order."""
        connected = self.wiring[unit.unit_id].streams
        return tuple(
            stream for port in _material(unit, direction) for stream in connected.get(port, ())
        )

    def traverse(self, guesses: Mapping[str, StreamState] = MappingProxyType({})) -> FlowsheetPass:
        """One causal pass in declaration order, tearing where the graph deadlocks (§1.5).

        A unit runs when every inlet stream has a value. When none can, the first pending unit
        with a computed inlet runs, and each of its inlets without a value is torn: it takes its
        guess, or a dormant stream labelled with that computed inlet's `(T, P)` — a legal inlet
        for every unit (ADR 0001 D3.4), and one a mixer's equal-pressure rule accepts. The
        deadlock depends only on the graph, so a second pass from the first's `computed_torn`
        tears the same streams. Nothing is solved and nothing iterated.
        """
        value: dict[str, StreamState] = {}
        computed: set[str] = set()
        torn: list[str] = []
        computed_torn: dict[str, StreamState] = {}
        evaluations: dict[str, UnitEvaluation] = {}
        order: list[str] = []

        def fail(unit: str, status: PropertyStatus, code: str) -> FlowsheetPass:
            return FlowsheetPass(
                status=status,
                streams=dict(value),
                evaluations=dict(evaluations),
                order=tuple(order),
                torn=tuple(torn),
                computed_torn=dict(computed_torn),
                failed_unit=unit,
                code=code,
            )

        pending = list(self.instances)
        while pending:
            ready = [u for u in pending if all(s in value for s in self._streams(u, "inlet"))]
            if ready:
                unit = ready[0]
            else:
                started = [
                    u for u in pending if any(s in computed for s in self._streams(u, "inlet"))
                ]
                if not started:
                    return fail(pending[0].unit_id, "error", "no_computed_inlet")
                unit = started[0]
                inlets = self._streams(unit, "inlet")
                label = value[next(s for s in inlets if s in computed)]
                for stream in inlets:
                    if stream in value:
                        continue
                    value[stream] = (
                        guesses[stream]
                        if stream in guesses
                        else StreamState(
                            n=(0.0,) * len(self.components),
                            temperature=label.temperature,
                            pressure=label.pressure,
                        )
                    )
                    torn.append(stream)

            connected = self.wiring[unit.unit_id].streams
            evaluation = unit.evaluate(
                {
                    port: tuple(value[s] for s in connected.get(port, ()))
                    for port in _material(unit, "inlet")
                },
                self.context,
            )
            if evaluation.status != "ok":
                return fail(
                    unit.unit_id,
                    evaluation.status,
                    (evaluation.message.splitlines() or [""])[0],
                )
            for port in _material(unit, "outlet"):
                for stream in connected.get(port, ()):
                    if stream in torn:
                        computed_torn[stream] = evaluation.outlets[port]
                    else:
                        value[stream] = evaluation.outlets[port]
                    computed.add(stream)
            evaluations[unit.unit_id] = evaluation
            order.append(unit.unit_id)
            pending = [u for u in pending if u is not unit]

        return FlowsheetPass(
            status="ok",
            streams=dict(value),
            evaluations=dict(evaluations),
            order=tuple(order),
            torn=tuple(torn),
            computed_torn=dict(computed_torn),
        )


def _material(unit: UnitModel, direction: PortDirection) -> tuple[str, ...]:
    """A unit's material port names in one direction, in its `ports()` order."""
    return tuple(
        port.name
        for port in unit.ports()
        if port.kind == "material" and port.direction == direction
    )
