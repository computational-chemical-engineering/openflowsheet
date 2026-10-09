"""Binding a `ProcessRevision` to a compiled declaration, for structural analysis.

T01 specification §5. This is **not** the general revision compiler: assembling unit equations
from `ModelManifest` documents is not delivered by T01 (§16), and the obligation ADR 0002 D2.7
attaches to whichever package first does it is still outstanding. What is delivered is the
narrow binding the registered cases need — a SYN-001 revision to the SYN-001 declaration — plus
the one rule that makes the conflicting case reachable at all.

**The rule (§5.1).** A revision specification with `role: fixed` whose target is a free column
that no unit row already pins becomes an assembler-authored specification row `SPEC:<id>` over
that column, `accumulation: "algebraic"`, origin `revision#<id>`. The unit is not told: the
heater's own refusal of a `specified_duty` must not be the path by which the conflicting case is
rejected, because a `SpecificationError` from a constructor is not a structural finding and does
not name what is wrong in the vocabulary a report can carry.

**Instances are matched to units by topology, not by name.** Each revision instance is identified
with the compiled unit that produces and consumes exactly the same streams. Two `product_sink`
instances differ only in what feeds them, and a name table would have had to encode that; the
wiring already does.

A revision this module cannot bind returns `None` rather than a guess, and the caller reports the
analysis as unsupported. That is the same limitation K06's CLI already carries.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Final, Literal

from openflowsheet.canonical import document_sha256, first_noncanonical
from openflowsheet.compile.spec import EquationSpec, ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.process import Connection, ProcessGraph
from openflowsheet.models import SpecificationError
from openflowsheet.models.revision_flowsheet import (
    InputMapping,
    RevisionError,
    canonical_components,
    convert_specification,
    read_parameter,
)
from openflowsheet.units import UnitConversion, read_number

if TYPE_CHECKING:
    from openflowsheet.application.revision_binding import SurrogateResolver

__all__ = [
    "Binding",
    "Unbound",
    "bind_revision",
    "bind_revision_or_reason",
    "instance_named",
    "legacy_admission",
    "legacy_answers",
    "refusal_code",
    "revision_probe",
]

_SPEC_ROW_PREFIX = "SPEC:"


def instance_named(identifier: str, instance_of: Mapping[str, str]) -> str:
    """T08 D1 as ruled for `STR-03`, `STR-04` and `STR-05` (T08 review §3.3): an id the binder
    formed from one of its unit ids — the unit itself, a row `<unit>:<equation>[:<port>]` or a
    parameter `<unit>.<parameter>` — named by the revision instance that authored the unit
    (`instance_of`, the graph's `instance_ids`), its suffix kept: the equation id, the port and
    the parameter name are the model's contract. Any other id — a specification, a connection, a
    column of a stream — is returned unchanged."""
    unit = identifier.split(":", 1)[0].split(".", 1)[0]
    instance = instance_of.get(unit)
    return identifier if instance is None else instance + identifier[len(unit) :]


@dataclass(frozen=True)
class Binding:
    """What the structural analysis needs: the declaration, the graph, and the revision's names."""

    spec: ProblemSpec
    graph: ProcessGraph
    #: Row id -> the instance that authored it, taken from each unit's own contribution. The
    #: structural layer is never asked to read this off an id (T01 A15).
    row_units: Mapping[str, str]
    #: Row id -> the `ProcessRevision` specification id it carries. Covers both the unit rows that
    #: already pin a specification and the promoted rows of §5.1.
    specification_ids: Mapping[str, str]
    model_version: str
    constants_sha256: str
    #: Unit rows removed because the revision *frees* the column they pin (T02 §7.1): a `role:
    #: free` specification on it. Distinct from a specification that is simply absent, which is
    #: an incomplete revision (R-022).
    removed_specification_rows: tuple[str, ...] = ()
    #: Column -> the starting value a `role: free` specification gives it (T02 §7.5): blueprint
    #: §4.3's "tentative initial guess", kept apart from the fixed specifications.
    guesses: Mapping[str, float] = field(default_factory=dict)
    #: Freed columns whose `role: free` specification carries no value (T03 §9): no start exists.
    missing_guesses: tuple[str, ...] = ()
    #: Removed row -> the column it pinned (the adjusted variable of a cross-unit specification).
    freed: Mapping[str, str] = field(default_factory=dict)
    #: Promoted row -> the column it pins (the target of a cross-unit specification, §5.1).
    promoted: Mapping[str, str] = field(default_factory=dict)
    #: The flowsheet the declaration was assembled from, with every freed coordinate at its guess:
    #: exactly the pre-solve's flowsheet (T02 §7.5), and the one a registered revision solves on.
    flowsheet: Any = None
    #: Revision specification id -> the columns it targets, for every `role: fixed` and `role: free`
    #: specification (ADR 0010 D9): how the verifier reads a specification's value from the
    #: revision, never from the flowsheet, which carries a freed coordinate at its guess.
    specification_targets: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: ADR 0002's canonical SHA-256 of the revision document this binding was bound from, so that a
    #: consumer handed the document again can tell it is this binding's (T04 review S2).
    revision_sha256: str = ""
    #: How the revision's inputs were read (T06 spec §8.5, §8.6): the declared component order,
    #: which the binding maps onto the provider's, and the `unit-conversion-v2` conversions of its
    #: specification values and instance parameters, in ADR 0016 D6's order.
    input_mapping: InputMapping = field(default_factory=InputMapping)


def _connections(document: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    for entry in document.get("connections", ()) or ():
        if entry.get("kind") != "material":
            continue
        source, target = entry.get("from") or {}, entry.get("to") or {}
        edges.append(
            (str(entry.get("id")), str(source.get("instance")), str(target.get("instance")))
        )
    return edges


def _topology(
    edges: Sequence[tuple[str, str, str]],
) -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    produced: dict[str, set[str]] = {}
    consumed: dict[str, set[str]] = {}
    for stream, source, target in edges:
        produced.setdefault(source, set()).add(stream)
        consumed.setdefault(target, set()).add(stream)
        produced.setdefault(target, set())
        consumed.setdefault(source, set())
    return {
        name: (frozenset(produced[name]), frozenset(consumed.get(name, set()))) for name in produced
    }


def _match_instances(
    revision_edges: Sequence[tuple[str, str, str]],
    wiring: Mapping[str, tuple[frozenset[str], frozenset[str]]],
) -> dict[str, str] | None:
    """Compiled unit id -> revision instance id, matched on identical stream topology."""
    revision = _topology(revision_edges)
    by_signature: dict[tuple[frozenset[str], frozenset[str]], list[str]] = {}
    for instance, signature in revision.items():
        by_signature.setdefault(signature, []).append(instance)

    matched: dict[str, str] = {}
    for unit, signature in wiring.items():
        candidates = by_signature.get(signature, [])
        if len(candidates) != 1:
            return None
        matched[unit] = candidates[0]
    if len(set(matched.values())) != len(matched) or len(matched) != len(revision):
        return None
    return matched


def _column_targets(
    specification: Mapping[str, Any], graph: ProcessGraph, units_by_instance: Mapping[str, str]
) -> tuple[str, ...]:
    """The declaration columns a revision specification pins, or `()` when it pins none.

    A specification on an instance's outlet state pins that coordinate on *every* stream the
    instance produces, which is why a single isothermal flash specification reaches two rows.
    """
    target = specification.get("target") or {}
    object_type = str(target.get("object_type", ""))
    object_id = str(target.get("object_id", ""))
    path = str(target.get("path", ""))
    component = target.get("component")

    if object_type == "connection":
        coordinate = path.removeprefix("state.")
        if coordinate == "n" and component is not None:
            return (f"{object_id}.n.{component}",)
        if coordinate in {"T", "P"}:
            return (f"{object_id}.{coordinate}",)
        return ()

    if object_type != "instance":
        return ()
    unit = units_by_instance.get(object_id)
    if unit is None:
        return ()
    if path.startswith("duty."):
        return (f"{unit}.{path.removeprefix('duty.')}",)
    if path.startswith("outlet."):
        coordinate = path.removeprefix("outlet.")
        if coordinate not in {"T", "P"}:
            return ()
        outlets = [
            connection.stream_id for connection in graph.connections if connection.producer == unit
        ]
        return tuple(f"{stream}.{coordinate}" for stream in outlets)
    return ()


def _promotion_row(column: str, parameter: str) -> Any:
    def build(
        variables: Mapping[str, Any],
        blocks: Mapping[str, Any],
        parameters: Mapping[str, float],
        algebra: Any,
    ) -> Any:
        return variables[column] - parameters[parameter]

    return build


def structural_inputs(flowsheet: Any) -> tuple[ProblemSpec, ProcessGraph, dict[str, str]]:
    """The declaration, the process graph and the row attribution of an assembled flowsheet.

    The structural layer is never asked to read an authoring unit off a row id or a state
    coordinate off a column id (T01 A15), so both come from here, where the wiring and the unit
    instances are in hand. This is the flowsheet-side entry; `bind_revision` is the revision-side
    one and they produce the same three things.
    """
    from openflowsheet.models.syn001.flowsheet import STREAMS, WIRING

    edges = _wiring_edges(WIRING)
    states = {
        stream: (
            *(f"{stream}.n.{component}" for component in flowsheet.components),
            *(f"{stream}.{coordinate}" for coordinate in _STATE_COORDINATES["nTP-v1"]),
        )
        for stream in STREAMS
    }
    spec: ProblemSpec = flowsheet.spec()
    graph = ProcessGraph(
        units=tuple(WIRING),
        connections=tuple(
            Connection(
                stream_id=stream,
                producer=source,
                consumer=target,
                state_columns=states.get(stream, ()),
            )
            for stream, source, target in sorted(set(edges))
        ),
        instance_ids={unit: unit for unit in WIRING},
        column_owners=_column_owners(
            spec.variable_ids, {stream: source for stream, source, _ in edges}, tuple(WIRING)
        ),
    )
    row_units = {
        equation.equation_id: unit.unit_id
        for unit in flowsheet.units()
        for equation in unit.contribute(WIRING[unit.unit_id], flowsheet.components).equations
    }
    return spec, graph, row_units


@dataclass(frozen=True)
class Unbound:
    """Why a revision could not be bound, in the kinds that call for different statuses.

    Decided by Frank on 2026-09-24 (register R-022), refining F1 of the T01 review. The kinds are
    not interchangeable: a revision whose specifications contradict each other has a real defect;
    one missing a specification is incomplete, which blueprint §4.3 calls `DRAFT` in so many
    words; and one this binding cannot read may be perfectly fine, so reporting it as a fault
    would repeat the old `UNSUPPORTED_RANK_STRUCTURE` mistake of describing the tool as if it were
    the revision.

    T07 ruling round 5, S3 adds `inadmissible`: a value the document *fixes* that the model it
    names refuses at construction (`SpecificationError`), outside that model's declared domain.
    A finding about the document, like `conflict`. A refused *start* is `incomplete` (blueprint
    §4.3: "a poor guess is not proof that the specified process is impossible").
    """

    kind: Literal["conflict", "inadmissible", "incomplete", "unsupported"]
    detail: str
    implicated: tuple[str, ...] = ()
    #: What would be accepted (T07 ruling round 6, B2), beside the unchanged code in `detail`;
    #: bounded to `HINT_LIMIT` code points by `bound_text` (§10.4). Not part of equality: two
    #: refusals with one code are one refusal.
    hint: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.hint is not None:
            from openflowsheet.application.projection import bound_text

            object.__setattr__(self, "hint", bound_text(self.hint, HINT_LIMIT))


#: Ruling round 6, B2: `bound_text` bounds each hint to 512 code points.
HINT_LIMIT: Final = 512


def refusal_code(detail: str) -> str:
    """A refusal's code token: its `detail` up to the first `(` (T07 ruling round 6, B1)."""
    return detail.split("(", 1)[0]


def legacy_answers(document: Mapping[str, Any], refusal: Unbound) -> bool:
    """Whether `legacy_eo` may solve a revision the revision binder refused with `refusal` (T07
    design note ruling round 6, B1, amending R2.1): only a refusal of `role: free`, on a revision
    whose every non-`fixed` specification is `free`. That is what `legacy_eo` was admitted for —
    the same document, solved another way; for any other refusal the legacy binder would solve a
    different problem (SYN-001's closure of what the document leaves open, a declared phase
    ignored). A fallback may change the method, never the problem. `decision` is outside the
    class: the legacy binder does not read it."""
    roles = {entry.get("role") for entry in document.get("specifications") or ()}
    return (
        refusal.kind == "unsupported"
        and refusal_code(refusal.detail) == "specification_role_unsupported"
        and roles - {"fixed"} == {"free"}
    )


def _argument(detail: str) -> str:
    """A refusal's argument: its `detail` between the first `(` and the last `)` (round 7)."""
    return detail[detail.find("(") + 1 : detail.rfind(")")]


def revision_probe(
    document: Mapping[str, Any],
    binding: Binding | None,
    *,
    surrogates: SurrogateResolver | None = None,
) -> tuple[Unbound | None, tuple[tuple[str, Unbound], ...]]:
    """The revision binder's reading of `document` with every `role: free` specification read as
    `fixed` (T07 design note, ruling round 7, M1 and M2): `None` when it binds once the cross-unit
    targets it refuses as `specification_unconsumed` are removed, one at a time, else its refusal;
    and those targets, each with the refusal that named it, in order.

    A free specification without a value starts where the legacy binder assembled it
    (`_declared_default` of its first column, in SI), so on the admission path the probe builds
    exactly what `binding` was built with. Such a specification with no `binding` is a caller
    error. The loop runs the revision binder at most once more than there are fixed
    specifications; only a specification the document itself fixes can be a target."""
    from openflowsheet.application.revision_binding import bind_revision_flowsheet
    from openflowsheet.models.revision_flowsheet import si_unit

    probe = copy.deepcopy(dict(document))
    specifications = list(probe.get("specifications") or ())
    fixed = {str(entry.get("id")) for entry in specifications if entry.get("role") == "fixed"}
    for entry in specifications:
        if entry.get("role") != "free":
            continue
        entry["role"] = "fixed"
        if entry.get("value") is None:
            if binding is None:
                raise ValueError(
                    f"revision_probe: free specification {entry.get('id')!r} has no value and "
                    "no legacy binding gives its start"
                )
            entry["value"] = _declared_default(binding.specification_targets[str(entry["id"])][0])
            entry["unit"] = si_unit(str(entry.get("kind")))
            entry.pop("bounds", None)

    targets: list[tuple[str, Unbound]] = []
    while True:
        removed = {name for name, _ in targets}
        result = bind_revision_flowsheet(
            {
                **copy.deepcopy(probe),
                "specifications": [
                    copy.deepcopy(entry)
                    for entry in specifications
                    if str(entry.get("id")) not in removed
                ],
            },
            surrogates=surrogates,
        )
        if not isinstance(result, Unbound):
            return None, tuple(targets)
        name = _argument(result.detail)
        if (
            result.kind == "unsupported"
            and refusal_code(result.detail) == "specification_unconsumed"
            and name in fixed
            and name not in removed
        ):
            targets.append((name, result))
            continue
        return result, tuple(targets)


def _free_unused(name: str, hint: str) -> Unbound:
    """Ruling round 7's one new code: a `role: free` specification that the legacy formulation
    does not free, with what would be accepted."""
    return Unbound("unsupported", f"specification_free_unused({name})", hint=hint)


def _document_column(column: str, binding: Binding) -> str:
    """A legacy column in the document's ids (ruling round 7): a stream column as it is
    (`<connection>.T|P|n.<component>`), a unit column through the graph's instance ids
    (`<instance id>.Q`)."""
    owner, _, rest = column.partition(".")
    instance = binding.graph.instance_ids.get(owner)
    return column if instance is None else f"{instance}.{rest}"


def _hint_no_coordinate(name: str, path: str) -> str:
    """`specification_free_unused`'s hint when the free specification reaches no coordinate (C1):
    the paths a free specification can release, generated from the target-path table."""
    from openflowsheet.models.revision_flowsheet import TARGET_PATH_KINDS

    def listed(paths: Sequence[str]) -> str:
        return paths[0] if len(paths) == 1 else f"{', '.join(paths[:-1])} or {paths[-1]}"

    connection = [path for path in TARGET_PATH_KINDS if path.startswith("state.")]
    instance = [path for path in TARGET_PATH_KINDS if not path.startswith("state.")]
    return (
        "A free specification releases a coordinate that a fixed specification could pin: "
        f"path {listed(connection)} on a connection, or {listed(instance)} on an instance. "
        f"{name} targets {path}."
    )


def legacy_admission(
    document: Mapping[str, Any], refusal: Unbound, binding: Binding
) -> Unbound | None:
    """Whether `legacy_eo` may solve `document` (T07 design note, ruling round 7, M1 and M2,
    replacing round 6's predicate): `None` when it may, else the refusal `validate()` reports.
    `refusal` is the revision binder's, `binding` the legacy binder's.

    A fallback may change the method, never the problem. So the legacy formulation must state the
    document's problem under the models it names:

    - **C0** round 6's class holds (`legacy_answers`);
    - **C1** every free specification reaches a coordinate, and none that a fixed one reaches;
    - **C2** the revision binder binds the document with every free specification read as fixed,
      once the cross-unit targets it refuses as unconsumed are removed (`revision_probe`);
    - **C3** the legacy binding frees every free specification's columns;
    - **C4** it promotes exactly those targets' columns;
    - **C5** it frees exactly one column and promotes exactly one (review-2 S3: T02 §7.1's v0.1
      pairing, which the legacy plan requires).

    The first failing clause's refusal is returned."""
    if not legacy_answers(document, refusal):
        return refusal
    specifications = list(document.get("specifications") or ())
    columns = binding.specification_targets
    free = [entry for entry in specifications if entry.get("role") == "free"]
    fixed_by: dict[str, str] = {}
    for entry in specifications:
        if entry.get("role") == "fixed":
            for column in columns.get(str(entry.get("id")), ()):
                fixed_by.setdefault(column, str(entry.get("id")))

    for entry in free:
        name = str(entry.get("id"))
        reached = columns.get(name, ())
        if not reached:
            path = str((entry.get("target") or {}).get("path", ""))
            return _free_unused(name, _hint_no_coordinate(name, path))
        shared = next((column for column in reached if column in fixed_by), None)
        if shared is not None:
            return _free_unused(
                name,
                f"{name} and fixed specification {fixed_by[shared]} both target "
                f"{_document_column(shared, binding)}. A coordinate is fixed or free, not both: "
                "remove one of them.",
            )

    probed, targets = revision_probe(document, binding)
    if probed is not None:
        return probed

    freed = set(binding.freed.values())
    for entry in free:
        name = str(entry.get("id"))
        unfreed = next((column for column in columns[name] if column not in freed), None)
        if unfreed is not None:
            return _free_unused(
                name,
                f"{name} targets {_document_column(unfreed, binding)}, which the SYN-001 "
                "formulation that solves free specifications does not pin, so it cannot be freed.",
            )

    promoted = set(binding.promoted.values())
    for name, target_refusal in targets:
        reached = columns.get(name, ())
        if not reached or not set(reached) <= promoted:
            return target_refusal
    if promoted != {column for name, _ in targets for column in columns.get(name, ())}:
        return refusal

    if len(binding.freed) != 1 or len(binding.promoted) != 1:
        return _unpaired(free, targets, binding)
    return None


def _unpaired(
    free: Sequence[Mapping[str, Any]],
    targets: Sequence[tuple[str, Unbound]],
    binding: Binding,
) -> Unbound:
    """C5's refusal (review-2 S3): the legacy binding does not pair exactly one freed coordinate
    with one promoted target, T02 §7.1's v0.1 form, which `specification_regions` would refuse at
    plan time — after `validate()` had said `READY`. The hint names every free specification's
    coordinates and every target's, so the pair beyond the first is named whichever it is."""

    def listed(items: Sequence[str]) -> str:
        return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"

    def named(name: str) -> str:
        return listed(
            [
                _document_column(column, binding)
                for column in binding.specification_targets.get(name, ())
            ]
        )

    freed, promoted = len(binding.freed), len(binding.promoted)
    pairs = [f"{entry.get('id')} frees {named(str(entry.get('id')))}" for entry in free]
    pairs += [f"{name} targets {named(name)}" for name, _ in targets]
    return Unbound(
        "unsupported",
        f"specification_pairing_unsupported({freed},{promoted})",
        hint=(
            "The SYN-001 formulation that solves free specifications pairs exactly one freed "
            "coordinate with exactly one target (T02 §7.1); this revision frees "
            f"{freed} against {promoted or 'no target'}: {', '.join(pairs)}. State one free "
            "coordinate and one target: fix the other free specifications or remove the other "
            "targets."
        ),
    )


class _IncompleteError(Exception):
    def __init__(self, missing: Sequence[str]) -> None:
        super().__init__(missing)
        self.missing = tuple(missing)


class _DeclaredConflictError(Exception):
    def __init__(self, parameter: str, first: str, second: str, a: float, b: float) -> None:
        super().__init__(parameter)
        self.parameter, self.first, self.second, self.a, self.b = parameter, first, second, a, b


def bind_revision(document: Mapping[str, Any]) -> Binding | None:
    """Bind a SYN-001 `ProcessRevision` to its declaration, or `None` if it cannot be bound.

    Callers that need to know *why* use `bind_revision_or_reason`.
    """
    result = bind_revision_or_reason(document)
    return result if isinstance(result, Binding) else None


def bind_revision_or_reason(document: Mapping[str, Any]) -> Binding | Unbound:
    """Bind a SYN-001 `ProcessRevision`, or say which of the three reasons prevented it."""
    # R-088 Q29 (T07 design note §12.5): a non-canonical number is refused typed at entry,
    # whether or not a reader reads its field; in a field nothing reads, a digest would
    # otherwise raise untyped.
    pointer = first_noncanonical(document)
    if pointer is not None:
        return Unbound("unsupported", f"document_not_canonical({pointer})")

    from openflowsheet.models.syn001.flowsheet import WIRING

    instances = document.get("instances") or ()
    if not instances or any(
        not str((entry.get("model") or {}).get("id", "")).startswith("syn001.")
        for entry in instances
    ):
        return Unbound(
            "unsupported",
            "the structural analysis binds the registered SYN-001 revisions only; this revision "
            "uses models it does not know (T01 specification §5, §16)",
        )

    edges = _connections(document)
    if not edges:
        return Unbound(
            "unsupported", "the revision declares no material connection the binding can read"
        )

    wiring_edges = _wiring_edges(WIRING)
    matched = _match_instances(edges, _topology(wiring_edges))
    if matched is None:
        return Unbound(
            "unsupported",
            "the revision's connections do not match the SYN-001 flowsheet's topology, which is "
            "the only one the binding knows",
        )
    units_by_instance = {instance: unit for unit, instance in matched.items()}

    # T06 spec §8.6: a permuted component set is mapped onto the provider's order before any
    # column is named or any flowsheet value read, so `Syn001Flowsheet` never sees the declared
    # order (F7: it did, and the tear path crashed on the permuted inner system).
    declared = tuple((document.get("component_set") or {}).get("components") or ())
    try:
        components = canonical_components(declared)
    except RevisionError as error:
        return Unbound(error.kind, error.code, hint=error.hint)
    inputs = _read_inputs(document, components)
    if isinstance(inputs, Unbound):
        return inputs
    contract = _instance_contracts(document, components)
    if contract is not None:
        return contract
    converted, parameter_values, conversions = inputs
    states = _state_columns(document, components)
    graph = ProcessGraph(
        units=tuple(WIRING),
        connections=tuple(
            Connection(
                stream_id=stream,
                producer=source,
                consumer=target,
                state_columns=states.get(stream, ()),
            )
            for stream, source, target in sorted(set(wiring_edges))
        ),
        instance_ids=matched,
    )

    specifications = [
        entry for entry in (document.get("specifications") or ()) if entry.get("role") == "fixed"
    ]
    targets = {
        str(entry.get("id")): _column_targets(entry, graph, units_by_instance)
        for entry in specifications
    }
    values = {
        str(entry.get("id")): converted.get(str(entry.get("id")), 0.0) for entry in specifications
    }
    # T02 §7.5, made binding by T03 §9: a `role: free` specification frees its column whether or
    # not it carries a value; with a value, that is the start. Without one (a specification then
    # carries `bounds`), the column is still freed and the missing start is recorded, so the solve
    # ends INITIALIZATION_FAILED instead of silently keeping the column fixed (T02 review N9).
    freed = [
        entry for entry in (document.get("specifications") or ()) if entry.get("role") == "free"
    ]
    guesses = {
        column: converted[str(entry.get("id"))]
        for entry in freed
        if entry.get("value") is not None
        for column in _column_targets(entry, graph, units_by_instance)
    }
    missing_guesses = tuple(
        column
        for entry in freed
        if entry.get("value") is None
        for column in _column_targets(entry, graph, units_by_instance)
    )
    # The flowsheet object is parameterized by every coordinate it models; a freed coordinate with
    # no guess takes the flowsheet's own declared default *for assembly only*: it reaches the
    # removed pin row's parameter, which is then dropped from the declaration with the row (no
    # remaining row reads it), and the executor refuses before a pre-solve could use it as a
    # start (`missing_guesses`).
    defaults = {column: _declared_default(column) for column in missing_guesses}
    undefaulted = [column for column, value in defaults.items() if value is None]
    if undefaulted:
        # A coordinate the flowsheet cannot be assembled without, and with no start given: a
        # typed reason, never an exception (review M2).
        return Unbound(
            "incomplete",
            "a role: free specification without a value frees a coordinate the flowsheet has no "
            "declared default for: " + ", ".join(undefaulted),
            tuple(undefaulted),
        )
    assembly = {
        **guesses,
        **{column: value for column, value in defaults.items() if value is not None},
    }

    try:
        # The flowsheet object needs a value for every coordinate it is parameterized by. A freed
        # one takes its guess, which is also where the pre-solve pins it (§7.5).
        settings = _flowsheet_settings(
            document,
            components,
            {**targets, **{f"guess:{column}": (column,) for column in assembly}},
            {**values, **{f"guess:{column}": value for column, value in assembly.items()}},
            parameter_values,
        )
    except _IncompleteError as incomplete:
        return Unbound(
            "incomplete",
            "a specification the flowsheet needs is not declared: " + ", ".join(incomplete.missing),
            incomplete.missing,
        )

    try:
        flowsheet, spec, row_units = _assemble(settings)
    except SpecificationError as error:
        # T07 ruling round 5, S3: a model refused a value at construction. Typed, never raised,
        # and attributed to a start or to a fixed value (item 3).
        return _refused_at_construction(
            error,
            document=document,
            components=components,
            targets=targets,
            values=values,
            parameter_values=parameter_values,
            assembly=assembly,
            guesses=guesses,
            freed=freed,
            graph=graph,
            units_by_instance=units_by_instance,
        )

    # Column ownership is given to the structural layer, never inferred there (R-019). It needs
    # the assembled column set, so the graph gains it once the flowsheet exists.
    graph = replace(
        graph,
        column_owners=_column_owners(
            spec.variable_ids,
            {stream: source for stream, source, _ in wiring_edges},
            tuple(WIRING),
        ),
    )

    pinned = _pinned_columns(spec)
    specification_ids: dict[str, str] = {}
    for row_id, column in pinned.items():
        for name, columns in targets.items():
            if column in columns:
                specification_ids[row_id] = name

    # A unit row pinning a column the revision *frees* is removed: the adjusted variable of a
    # cross-unit specification (T02 §7.1). Only a column no fixed specification also targets.
    fixed_columns = {column for columns in targets.values() for column in columns}
    removed = tuple(
        row_id
        for row_id, column in pinned.items()
        if column in assembly and column not in fixed_columns
    )
    freed_columns = {row_id: pinned[row_id] for row_id in removed}
    if removed:
        spec = replace(
            spec,
            equations=tuple(
                equation for equation in spec.equations if equation.equation_id not in removed
            ),
            row_kinds={row: kind for row, kind in spec.row_kinds.items() if row not in removed},
        )
        pinned = {row_id: column for row_id, column in pinned.items() if row_id not in removed}
        for row_id in removed:
            row_units.pop(row_id, None)
        # A removed row's parameter that no remaining row reads is not part of the function any
        # more. Left in, it would carry the freed coordinate's guess (or, with no guess, the
        # flowsheet's declared default) into `constants_sha256`, and two revisions differing only
        # in their initial guess would be two problems — `same_root` NOT_COMPARABLE (T03 A20).
        from openflowsheet.graph.trace import parameters_read

        still_read = set().union(*parameters_read(spec).values())
        orphaned = [name for name in spec.parameter_ids if name not in still_read]
        if orphaned:
            spec = replace(
                spec,
                parameter_ids=tuple(n for n in spec.parameter_ids if n not in set(orphaned)),
                parameters={n: v for n, v in spec.parameters.items() if n not in set(orphaned)},
            )

    # The declaration must carry the values the *revision* declares, not the ones the flowsheet
    # happens to be parameterized by. `Syn001Flowsheet` takes a single pressure, so a revision
    # specifying the flash at 150 kPa against a feed at 100 kPa — K03 §7.2's registered conflict
    # — silently bound both to 100 kPa and validated clean. The Fable review of T01 measured it
    # (M2). Each pinned row's parameter is discovered by recording what its constant reads, and
    # then solved for the value that makes the row pin what the revision says.
    try:
        overridden = _honour_declared_values(spec, pinned, specification_ids, targets, values)
    except _DeclaredConflictError as conflict:
        return Unbound(
            "conflict",
            f"SPECIFICATION_CONFLICT: {conflict.first} and {conflict.second} both fix "
            f"{instance_named(conflict.parameter, graph.instance_ids)}, to {conflict.a:g} and "
            f"{conflict.b:g}; no state satisfies both",
            (conflict.first, conflict.second),
        )
    spec = replace(spec, parameters=overridden)

    promoted: list[EquationSpec] = []
    promoted_columns: dict[str, str] = {}
    parameters = dict(spec.parameters)
    parameter_ids = list(spec.parameter_ids)
    for name, columns in targets.items():
        for column in columns:
            if column in pinned.values() or column not in spec.variable_ids:
                continue
            row_id = f"{_SPEC_ROW_PREFIX}{name}"
            parameter = f"{_SPEC_ROW_PREFIX}{name}"
            promoted.append(
                EquationSpec(
                    equation_id=row_id,
                    build=_promotion_row(column, parameter),
                    accumulation="algebraic",
                    origin=f"revision#{name}",
                )
            )
            parameter_ids.append(parameter)
            parameters[parameter] = values[name]
            specification_ids[row_id] = name
            promoted_columns[row_id] = column
            row_units[row_id] = column.split(".", 1)[0] if column.split(".", 1)[0] in WIRING else ""

    if promoted:
        spec = replace(
            spec,
            equations=(*spec.equations, *promoted),
            parameter_ids=tuple(parameter_ids),
            parameters=parameters,
            # A specification row pins one column, so it is that column's kind: a duty row is
            # scaled and judged as a duty. Without it the row has no scale, and K03 §4 refuses a
            # silent 1.0 (SCALE_UNAVAILABLE) — correctly.
            row_kinds={
                **spec.row_kinds,
                **{row: spec.variable_kinds[column] for row, column in promoted_columns.items()},
            },
        )

    return Binding(
        spec=spec,
        graph=graph,
        row_units={row: unit for row, unit in row_units.items() if unit},
        specification_ids=specification_ids,
        removed_specification_rows=removed,
        guesses=guesses,
        missing_guesses=missing_guesses,
        freed=freed_columns,
        promoted=promoted_columns,
        flowsheet=flowsheet,
        revision_sha256=document_sha256(document),
        specification_targets={
            **{name: tuple(columns) for name, columns in targets.items()},
            **{
                str(entry.get("id")): tuple(_column_targets(entry, graph, units_by_instance))
                for entry in freed
            },
        },
        model_version="T01-structural",
        constants_sha256="0" * 64,
        input_mapping=InputMapping(declared_components=declared, conversions=conversions),
    )


def _instance_contracts(document: Mapping[str, Any], components: Sequence[str]) -> Unbound | None:
    """T07 ruling round 6, R6-W6: every matched instance satisfies `instance_contract` under the
    model it names — the parameters that model reads and the port phases it takes — or the first
    refusal, with the revision binder's kind, code and hint. This binder reads SYN-001's
    parameters and roles only; without the contract a document that states what its models
    refuse (a pressure drop, a declared phase, a parameter nobody reads) would be solved as
    SYN-001's problem instead. The views are the document's with `specifications` emptied: the
    roles this binder reads (`free`) are what the revision binder refuses, and pins are not part
    of the contract."""
    from openflowsheet.application.revision_binding import MODEL_SIGNATURES, instance_contract
    from openflowsheet.models.revision_flowsheet import parse_revision

    try:
        view = parse_revision({**document, "specifications": []})
        for instance in view.instances:
            signature = MODEL_SIGNATURES.get(instance.model_id)
            if signature is not None:
                instance_contract(instance, signature, components)
    except RevisionError as error:
        return Unbound(error.kind, error.code, hint=error.hint)
    return None


def _assemble(settings: Mapping[str, Any]) -> tuple[Any, ProblemSpec, dict[str, str]]:
    """The SYN-001 flowsheet at `settings`, its declaration and its row attribution. Raises the
    models' `SpecificationError` for a value a unit refuses at construction."""
    from openflowsheet.models.syn001.flowsheet import WIRING, Syn001Flowsheet
    from openflowsheet.orchestrator.budget import PropertyMeter
    from openflowsheet.thermo.syn001 import Syn001Provider

    flowsheet = Syn001Flowsheet(
        # Metered from construction, because the declaration's property blocks capture the
        # provider here and a plan run must count their calls (T02; `PropertyMeter`).
        provider=PropertyMeter(Syn001Provider()),
        context=EvaluationContext(
            model_version="T01-structural", constants_sha256="0" * 64, phase_signature=None
        ),
        **settings,
    )
    spec: ProblemSpec = flowsheet.spec()
    row_units = {
        equation.equation_id: unit.unit_id
        for unit in flowsheet.units()
        for equation in unit.contribute(WIRING[unit.unit_id], flowsheet.components).equations
    }
    return flowsheet, spec, row_units


def _first_line(error: Exception) -> str:
    return (str(error).splitlines() or [""])[0]


def _refused_at_construction(
    error: SpecificationError,
    *,
    document: Mapping[str, Any],
    components: tuple[str, ...],
    targets: Mapping[str, tuple[str, ...]],
    values: Mapping[str, float],
    parameter_values: Mapping[tuple[str, str], float],
    assembly: Mapping[str, float],
    guesses: Mapping[str, float],
    freed: Sequence[Mapping[str, Any]],
    graph: ProcessGraph,
    units_by_instance: Mapping[str, str],
) -> Unbound:
    """T07 ruling round 5, S3, item 3: whether the value a model refused is a start or a fixed
    value. Only this binder reads starts at construction.

    With no start at construction the refused value is fixed. Otherwise the flowsheet is built
    again with every guessed column at `_declared_default` — the constructor's own default, which
    the binder already uses for a free coordinate with no value. If that builds, the start was
    refused: `incomplete` (R-022's "incomplete" row, so `DRAFT`), naming the `role: free`
    specifications that gave the starts. If it is refused too, a fixed value is out of range
    whatever the start, and the rebuild's refusal is reported, because it names that value. If a
    guessed column has no declared default, the refusal cannot be attributed and states no
    defect (`unsupported`)."""
    first = _first_line(error)
    if guesses:
        defaults = {column: _declared_default(column) for column in guesses}
        if any(value is None for value in defaults.values()):
            return Unbound("unsupported", f"value_outside_model_domain_unattributed: {first}")
        rebuilt = {**assembly, **{c: v for c, v in defaults.items() if v is not None}}
        settings = _flowsheet_settings(
            document,
            components,
            {**targets, **{f"guess:{column}": (column,) for column in rebuilt}},
            {**values, **{f"guess:{column}": value for column, value in rebuilt.items()}},
            parameter_values,
        )
        try:
            _assemble(settings)
        except SpecificationError as fixed:
            first = _first_line(fixed)
        else:
            starts = tuple(
                str(entry.get("id"))
                for entry in freed
                if entry.get("value") is not None
                and any(
                    column in guesses for column in _column_targets(entry, graph, units_by_instance)
                )
            )
            return Unbound(
                "incomplete", f"start_outside_model_domain({', '.join(starts)}): {first}", starts
            )
    # A SYN-001 unit names itself first (`U-FLASH: specified pressure …`): its matched instance
    # is implicated; any other message implicates none.
    unit = first.split(":", 1)[0] if ":" in first else ""
    instance = graph.instance_ids.get(unit)
    return Unbound(
        "inadmissible",
        f"value_outside_model_domain: {first}",
        (instance,) if instance is not None else (),
    )


def _read_inputs(
    document: Mapping[str, Any], components: Sequence[str]
) -> tuple[dict[str, float], dict[tuple[str, str], float], tuple[UnitConversion, ...]] | Unbound:
    """Every specification value in SI, by id, every instance parameter in SI, by (instance,
    name), with the conversions made, or the refusal.

    ADR 0016 D5, reader R1: the values of `role: fixed` and the guesses of `role: free` go
    through `unit-conversion-v2` as the revision layer reads them, and so does every instance
    parameter (R6, `read_parameter`); this binding refuses what validation's `DIM-01` fails, with
    the revision binding's codes and the id implicated — defence in depth, because it is callable
    without `validate`. A specification naming a component outside the component set is refused
    for its component, typed `conflict`, whatever its unit: the component is judged first.
    """
    converted: dict[str, float] = {}
    conversions: list[UnitConversion] = []
    for entry in document.get("specifications") or ():
        name = str(entry.get("id"))
        component = (entry.get("target") or {}).get("component")
        if component is not None and component not in components:
            return Unbound("conflict", f"component_unknown({name}, {component})", (name,))
        raw = entry.get("value")
        # A number is read by S5's one reading (T06 §8.5 (A5)). A `value` that is present and
        # not a number — a string, a bool, null — is refused typed with the revision binding's
        # code (T07 design note §12.5, R-088): `float()` accepted `"300"` and `True` as numbers
        # and raised untyped on `"abc"`. An absent `value` is still a `role: free`
        # specification's missing guess (T02 §7.5).
        number = read_number(raw)
        if number is None and "value" in entry:
            return Unbound("unsupported", f"specification_value_unreadable({name})", (name,))
        try:
            value, conversion = convert_specification(entry, number)
        except RevisionError as error:
            return Unbound(error.kind, error.code, (name,), error.hint)
        if value is not None:
            converted[name] = value
        if conversion is not None:
            conversions.append(conversion)
    parameters: dict[tuple[str, str], float] = {}
    for instance in document.get("instances") or ():
        unit = str(instance.get("id"))
        converted_here: list[UnitConversion] = []
        for parameter, quantity in (instance.get("parameters") or {}).items():
            try:
                value, conversion = read_parameter(unit, str(parameter), quantity)
            except RevisionError as error:
                return Unbound(error.kind, error.code, (f"{unit}.{parameter}",), error.hint)
            parameters[(unit, str(parameter))] = value
            if conversion is not None:
                converted_here.append(conversion)
        conversions.extend(sorted(converted_here, key=lambda conversion: conversion.input_id))
    return converted, parameters, tuple(conversions)


#: The state definitions this binding knows how to name coordinates for. `nTP-v1` is ADR 0001
#: D2.1: component molar flows, a temperature and a pressure. A connection declaring anything else
#: gets no state columns, so no tear candidate is built from it rather than one being guessed.
_STATE_COORDINATES: Mapping[str, tuple[str, ...]] = {"nTP-v1": ("T", "P")}


def _state_columns(
    document: Mapping[str, Any], components: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """The declared state coordinates of each material connection, as column ids.

    Read from the connection's own `state_definition` rather than assumed, so the graph layer
    never has to know a coordinate naming convention and a future state definition is a table
    entry here rather than a rule spread through the analysis.
    """
    columns: dict[str, tuple[str, ...]] = {}
    for entry in document.get("connections", ()) or ():
        if entry.get("kind") != "material":
            continue
        definition = str(entry.get("state_definition", ""))
        scalars = _STATE_COORDINATES.get(definition)
        if scalars is None:
            continue
        stream = str(entry.get("id"))
        columns[stream] = (
            *(f"{stream}.n.{component}" for component in components),
            *(f"{stream}.{coordinate}" for coordinate in scalars),
        )
    return columns


class _Recorder(dict[str, float]):
    """A parameter mapping that records what is looked up. Every miss reads as zero."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[str] = []

    def __missing__(self, key: str) -> float:
        self.seen.append(key)
        return 0.0


def _honour_declared_values(
    spec: ProblemSpec,
    pinned: Mapping[str, str],
    specification_ids: Mapping[str, str],
    targets: Mapping[str, tuple[str, ...]],
    values: Mapping[str, float],
) -> dict[str, float]:
    """Set each pinned row's parameter so the row pins the value the revision declares.

    A pinned row is `c x + k(p) = 0` for one column `x`, one literal coefficient `c` and a
    constant affine in one parameter `p`. Measuring `k` at `p = 0` and `p = 1` gives the offset
    and the slope without assuming a sign convention, and the row pins `value` when
    `p = -(c*value + k0) / (k1 - k0)`.

    Raises `_DeclaredConflictError` when two specifications with different values reach the same
    parameter. Picking one would be a guess about which the author meant.
    """
    from openflowsheet.graph.trace import trace_declaration

    declaration = trace_declaration(spec)
    parameters = dict(spec.parameters)
    assigned: dict[str, tuple[float, str]] = {}

    for row_id, column in pinned.items():
        name = specification_ids.get(row_id)
        if name is None or column not in targets.get(name, ()):
            continue
        row = declaration.rows[row_id]
        if row.coefficients is None or len(row.coefficients) != 1:
            continue
        (coefficient,) = row.coefficients.values()

        recorder = _Recorder()
        row.constant(recorder)
        read = set(recorder.seen)
        if len(read) != 1:
            continue
        parameter = read.pop()

        offset = row.constant({**parameters, parameter: 0.0})
        slope = row.constant({**parameters, parameter: 1.0}) - offset
        if slope == 0.0:
            continue
        resolved = -(coefficient * values[name] + offset) / slope

        previous = assigned.get(parameter)
        if previous is not None and previous[0] != resolved:
            raise _DeclaredConflictError(parameter, previous[1], name, previous[0], resolved)
        assigned[parameter] = (resolved, name)
        parameters[parameter] = resolved

    return parameters


def _column_owners(
    columns: Sequence[str], streams: Mapping[str, str], units: Sequence[str]
) -> dict[str, str]:
    """Which unit owns each column: the producer of its stream, or the unit its id names.

    The naming convention lives here, in the layer that knows this flowsheet, and not in the
    structural layer (register R-019). `streams` maps a stream id to its producing unit; a column
    belongs to a stream when its id begins with that stream and a separator, which covers the
    lifted split (`<stream>.vap.<component>`) as well as the declared state.
    """
    owners: dict[str, str] = {}
    for column in columns:
        head = column.split(".", 1)[0]
        if head in units:
            owners[column] = head
        elif head in streams:
            owners[column] = streams[head]
    return owners


def _wiring_edges(wiring: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """The material edges of the compiled flowsheet, producer to consumer.

    The `Wiring` convention names the input port `inlet`; every other port is an outlet, whatever
    the unit calls it (`outlet`, `vapor`, `liquid`, `recycle`, `purge`). So a stream's producer is
    the unit carrying it on a non-`inlet` port and its consumer is the one carrying it on `inlet`.
    """
    producers: dict[str, str] = {}
    consumers: dict[str, list[str]] = {}
    for unit, entry in wiring.items():
        for port, streams in entry.streams.items():
            for stream in streams:
                if port == "inlet":
                    consumers.setdefault(stream, []).append(unit)
                else:
                    producers[stream] = unit
    return sorted(
        (stream, producer, consumer)
        for stream, producer in producers.items()
        for consumer in consumers.get(stream, ())
    )


def _pinned_columns(spec: ProblemSpec) -> dict[str, str]:
    """Rows that already pin exactly one column to a parameter, by row id.

    Read from the structural trace rather than from an id convention: a row pins a column when it
    is affine in that one column with coefficient +/-1 and a parameter-dependent constant.
    """
    from openflowsheet.graph.trace import trace_declaration

    declaration = trace_declaration(spec)
    return {
        row_id: declaration.rows[row_id].columns[0]
        for row_id in declaration.row_ids
        if declaration.rows[row_id].is_specification_row
    }


#: The coordinates the SYN-001 flowsheet object is parameterized by, and the constructor field
#: each sets (`_flowsheet_settings` reads them in the same terms).
_FLOWSHEET_FIELDS: Final[Mapping[str, str]] = {
    "S1.T": "feed_temperature",
    "S1.P": "pressure",
    "S3.T": "heater_temperature",
    # The flash's `outlet.T` is both outlets' temperature: one parameter, two columns.
    "S4.T": "flash_temperature",
    "S5.T": "flash_temperature",
}


def _declared_default(column: str) -> float | None:
    """The flowsheet class's own constructor default for a coordinate it is parameterized by, or
    `None` when it declares none (review M2: introspected, not a table of our own)."""
    from dataclasses import MISSING, fields

    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet

    name = _FLOWSHEET_FIELDS.get(column)
    if name is None:
        return None
    default = next((f.default for f in fields(Syn001Flowsheet) if f.name == name), MISSING)
    return None if default is MISSING else float(default)


def _flowsheet_settings(
    document: Mapping[str, Any],
    components: tuple[str, ...],
    targets: Mapping[str, tuple[str, ...]],
    values: Mapping[str, float],
    parameters: Mapping[tuple[str, str], float],
) -> dict[str, Any]:
    """Read the five parameters SYN-001 is parameterized by, from the specifications' targets,
    with the feed flows in `components`' order (the provider's, T06 spec §8.6), and the split
    fraction from its instance parameter as `read_parameter` read it (in SI, ADR 0016 D5)."""

    def value_for(column: str) -> float | None:
        for name, columns in targets.items():
            if column in columns:
                return values[name]
        return None

    flows = tuple(value_for(f"S1.n.{component}") for component in components)
    feed_temperature = value_for("S1.T")
    pressure = value_for("S1.P")
    heater_temperature = value_for("S3.T")
    flash_temperature = value_for("S4.T")

    split_fraction: float | None = None
    for entry in document.get("instances") or ():
        if "split_fraction" in (entry.get("parameters") or {}):
            split_fraction = parameters[(str(entry.get("id")), "split_fraction")]

    missing = [
        label
        for label, value in (
            ("component set", components or None),
            *(
                (f"feed flow of {component}", flow)
                for component, flow in zip(components, flows, strict=True)
            ),
            ("feed temperature", feed_temperature),
            ("feed pressure", pressure),
            ("heater outlet temperature", heater_temperature),
            ("flash temperature", flash_temperature),
            ("split fraction", split_fraction),
        )
        if value is None
    ]
    if missing:
        raise _IncompleteError(missing)

    return {
        "components": components,
        "feed_flows": tuple(float(flow) for flow in flows if flow is not None),
        "feed_temperature": feed_temperature,
        "pressure": pressure,
        "heater_temperature": heater_temperature,
        "flash_temperature": flash_temperature,
        "split_fraction": split_fraction,
    }
