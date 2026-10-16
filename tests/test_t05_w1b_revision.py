"""T05 W1.b: the revision-built flowsheet — parse, assemble, label, traverse, refuse.

Design note `docs/design/T05-generalization.md` §1.3–§1.5, §7 (W1.b). The reference is SYN-001
itself: the SYN-001-shaped revision (`t05_syn001_shaped`) bound through the general machinery
must give `Syn001Flowsheet`'s declaration field for field, and its two-pass traversal must give
the legacy traversal from the registered initializer **bitwise** (design Q-F: the torn recycle's
dormant label is 300 K here and 360 K in the legacy pass, and the equality says no unit reads it).
Every refusal of R1–R6 is pinned by kind and code.
"""

from __future__ import annotations

import copy
import struct
from collections.abc import Callable
from typing import Any

import pytest
from t05_syn001_shaped import shaped_revision
from t05_w12_support import Feed, Outlet, connection_pin, duty_pin, mini_revision, unit_instance

from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    MODEL_BUILDERS,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import RevisionError, parse_revision
from openflowsheet.models.syn001.flowsheet import MODEL_LABEL, Syn001Flowsheet
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.syn001 import Syn001Provider

Document = dict[str, Any]


def _bind(document: Document) -> RevisionBinding:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    return binding


def _legacy() -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t05-w1b", constants_sha256="0" * 64, phase_signature=None
        ),
    )


def _bits(state: StreamState) -> tuple[bytes, ...]:
    return tuple(struct.pack("<d", x) for x in (*state.n, state.temperature, state.pressure))


def _connection(document: Document, stream: str) -> dict[str, Any]:
    (entry,) = (c for c in document["connections"] if c["id"] == stream)
    return entry


def _instance(document: Document, unit: str) -> dict[str, Any]:
    (entry,) = (i for i in document["instances"] if i["id"] == unit)
    return entry


def _specification(document: Document, name: str) -> dict[str, Any]:
    (entry,) = (s for s in document["specifications"] if s["id"] == name)
    return entry


@pytest.fixture(scope="module")
def shaped() -> RevisionBinding:
    return _bind(shaped_revision())


# -- the declaration ---------------------------------------------------------------------------


def test_builders_hold_the_thirteen_models_of_the_table() -> None:
    """The six K02 models (W1.b), the six T05 ones (W11) and T08's kinetic CSTR (build-first
    §A1.7, §E.4: "the thirteen of `MODEL_BUILDERS`"). Since M02's join (R-280; design note §14.4
    D5, B13's rule) restricted to the `syn001.` keys, the literal unchanged;
    `tests/test_m02_join.py` pins all twenty-one."""
    assert {model for model in MODEL_BUILDERS if model.startswith("syn001.")} == {
        "syn001.feed_source",
        "syn001.adiabatic_mixer",
        "syn001.tp_heater",
        "syn001.tp_flash",
        "syn001.stream_splitter",
        "syn001.product_sink",
        "syn001.ph_flash",
        "syn001.valve",
        "syn001.liquid_pump",
        "syn001.conversion_reactor",
        "syn001.component_separator",
        "syn001.heat_exchanger",
        "syn001.kinetic_cstr",
    }


@pytest.mark.parametrize(
    "field",
    [
        "variable_ids",
        "equation_ids",
        "parameter_ids",
        "parameters",
        "variable_kinds",
        "row_kinds",
        "row_accumulation",
    ],
)
def test_shaped_spec_is_syn001s(shaped: RevisionBinding, field: str) -> None:
    legacy = _legacy().spec()
    assert getattr(shaped.spec, field) == getattr(legacy, field)
    if field in ("variable_ids", "equation_ids", "parameter_ids"):
        assert list(getattr(shaped.spec, field)) == list(getattr(legacy, field))


def test_only_the_label_differs(shaped: RevisionBinding) -> None:
    legacy = _legacy().spec()
    assert shaped.spec.label != legacy.label
    assert shaped.spec.label == shaped.flowsheet.label


def test_binding_carries_graph_and_row_attribution(shaped: RevisionBinding) -> None:
    assert shaped.graph.units == (
        "U-FEED",
        "U-MIX",
        "U-HEAT",
        "U-FLASH",
        "U-SPLIT",
        "U-PROD",
        "U-PURGE",
    )
    assert [(c.stream_id, c.producer, c.consumer) for c in shaped.graph.connections] == [
        ("S1", "U-FEED", "U-MIX"),
        ("S2", "U-MIX", "U-HEAT"),
        ("S3", "U-HEAT", "U-FLASH"),
        ("S4", "U-FLASH", "U-PROD"),
        ("S5", "U-FLASH", "U-SPLIT"),
        ("S6", "U-SPLIT", "U-MIX"),
        ("S7", "U-SPLIT", "U-PURGE"),
    ]
    assert set(shaped.row_units) == set(shaped.spec.equation_ids)
    assert shaped.row_units["U-HEAT:HEAT-equilibrium:A"] == "U-HEAT"
    assert shaped.graph.column_owners["S3.vap.A"] == "U-HEAT"
    assert shaped.graph.column_owners["U-FLASH.Q"] == "U-FLASH"


# -- the label ---------------------------------------------------------------------------------


def test_label_shape(shaped: RevisionBinding) -> None:
    label = shaped.flowsheet.label
    capabilities = shaped.flowsheet.provider.describe()
    assert label == (
        f"FSR1-{shaped.flowsheet.configuration_sha256[:12]}-{capabilities.provider_id}"
        f"-{capabilities.implementation_sha256[:12]}-{capabilities.data_sha256[:12]}"
    )
    assert len(label) <= 64
    assert len(label) == 50
    assert MODEL_LABEL.match(label)


def test_label_is_unchanged_by_a_pinned_value(shaped: RevisionBinding) -> None:
    document = shaped_revision()
    _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["value"] = 0.7
    _specification(document, "SPEC-splitter-r")["value"] = 0.7
    moved = _bind(document)
    assert moved.spec.label == shaped.spec.label
    assert moved.spec.parameters != shaped.spec.parameters


def _once_through() -> Document:
    """Feed -> heater -> flash -> two sinks: a revision where a phase capability can move and
    still bind (every port of the shaped revision's mixer is fixed `liquid` by R-038)."""
    document = shaped_revision()
    document["instances"] = [
        i for i in document["instances"] if i["id"] not in ("U-MIX", "U-SPLIT")
    ]
    connections = {c["id"]: c for c in document["connections"]}
    connections["S1"]["to"] = {"instance": "U-HEAT", "port": "inlet"}
    connections["S5"]["to"] = {"instance": "U-PURGE", "port": "inlet"}
    document["connections"] = [connections[s] for s in ("S1", "S3", "S4", "S5")]
    document["specifications"] = [
        s for s in document["specifications"] if s["id"] != "SPEC-splitter-r"
    ]
    return document


def test_label_changes_with_a_phase_capability() -> None:
    liquid = _bind(_once_through())
    document = _once_through()
    _connection(document, "S1")["phase_capability"] = "vapor"
    vapor = _bind(document)
    assert vapor.spec.label != liquid.spec.label
    # The capability selected other expressions: the heater's inlet enthalpy block.
    assert vapor.spec.variable_ids == liquid.spec.variable_ids
    assert [b.block_id for b in vapor.spec.blocks] != [b.block_id for b in liquid.spec.blocks]


def test_label_changes_with_a_parameter_name(shaped: RevisionBinding) -> None:
    """Renaming an instance renames every parameter it declares (`<unit>.<name>`)."""
    document = shaped_revision()
    _instance(document, "U-SPLIT")["id"] = "U-SPLITTER"
    for connection in document["connections"]:
        for end in ("from", "to"):
            if connection[end]["instance"] == "U-SPLIT":
                connection[end]["instance"] = "U-SPLITTER"
    _specification(document, "SPEC-splitter-r")["target"]["object_id"] = "U-SPLITTER"
    renamed = _bind(document)
    assert set(renamed.spec.parameter_ids) != set(shaped.spec.parameter_ids)
    assert renamed.spec.label != shaped.spec.label


def test_label_changes_with_the_mixer_inlet_order(shaped: RevisionBinding) -> None:
    document = shaped_revision()
    connections = document["connections"]
    first, recycle = (
        next(i for i, c in enumerate(connections) if c["id"] == s) for s in ("S1", "S6")
    )
    connections[first], connections[recycle] = connections[recycle], connections[first]
    swapped = _bind(document)
    (mixer,) = (i for i in parse_revision(document).instances if i.unit_id == "U-MIX")
    assert mixer.ports["inlet"] == ("S6", "S1")
    assert swapped.spec.label != shaped.spec.label


# -- the traversal -----------------------------------------------------------------------------


def test_pass_one_tears_the_recycle_only(shaped: RevisionBinding) -> None:
    first = shaped.flowsheet.traverse()
    assert first.status == "ok"
    assert first.torn == ("S6",)
    assert first.order == ("U-FEED", "U-MIX", "U-HEAT", "U-FLASH", "U-SPLIT", "U-PROD", "U-PURGE")
    # The dormant guess is labelled with the mixer's first computed inlet, S1.
    assert first.streams["S6"] == StreamState(n=(0.0, 0.0, 0.0), temperature=300.0, pressure=1e5)


def test_pass_two_is_the_legacy_traversal_bitwise(shaped: RevisionBinding) -> None:
    legacy = _legacy()
    recycle = legacy.initial_recycle()
    reference = legacy.traverse(recycle)
    first = shaped.flowsheet.traverse()
    # G(0) from a 300 K dormant recycle is the registered initializer, computed from a 360 K one.
    assert _bits(first.computed_torn["S6"]) == _bits(recycle)
    second = shaped.flowsheet.traverse(first.computed_torn)
    assert second.status == "ok"
    assert second.torn == first.torn
    assert set(second.streams) == set(reference.streams)
    for stream, state in reference.streams.items():
        assert _bits(second.streams[stream]) == _bits(state), stream
    assert reference.computed_recycle is not None
    assert _bits(second.computed_torn["S6"]) == _bits(reference.computed_recycle)
    assert second.evaluations["U-HEAT"].duty == reference.duties["U-HEAT"]
    assert second.evaluations["U-FLASH"].duty == reference.duties["U-FLASH"]


def test_a_failing_unit_is_reported_typed() -> None:
    """The feed at 400 K: an equimolar liquid above its bubble point, refused by the mixer."""
    document = shaped_revision()
    _specification(document, "SPEC-feed-T")["value"] = 400.0
    failed = _bind(document).flowsheet.traverse()
    assert failed.status != "ok"
    assert failed.failed_unit == "U-MIX"
    assert failed.code and "\n" not in failed.code
    assert failed.order == ("U-FEED",)


# -- refusals, R1-R6 (kind and code) -----------------------------------------------------------


def _refused(document: Document) -> tuple[str, str]:
    result = bind_revision_flowsheet(document)
    assert isinstance(result, Unbound), result
    return result.kind, result.detail


def _edit(change: Callable[[Document], None]) -> Document:
    document = shaped_revision()
    change(document)
    return document


def _set_instance_id(document: Document) -> None:
    _instance(document, "U-FEED")["id"] = "U.FEED"


def _drop_split_fraction(document: Document) -> None:
    del _instance(document, "U-SPLIT")["parameters"]["split_fraction"]
    document["specifications"] = [
        s for s in document["specifications"] if s["id"] != "SPEC-splitter-r"
    ]


def _add_unconsumed_pin(document: Document) -> None:
    extra = dict(_specification(document, "SPEC-heater-outlet-T"))
    extra["id"] = "SPEC-mixer-outlet-T"
    extra["target"] = {"object_type": "connection", "object_id": "S2", "path": "state.T"}
    document["specifications"].append(extra)


def _extra_sink(document: Document, producer: dict[str, str], capability: str) -> None:
    """A second product sink `U-SINK-X`, fed by a new stream `S8` from `producer`."""
    sink = dict(copy.deepcopy(_instance(document, "U-PURGE")), id="U-SINK-X")
    document["instances"].append(sink)
    stream = dict(copy.deepcopy(_connection(document, "S7")), id="S8")
    stream.update(phase_capability=capability, to={"instance": "U-SINK-X", "port": "inlet"})
    stream["from"] = producer
    document["connections"].append(stream)


def _reverse_purge(document: Document) -> None:
    """S7 wired sink → splitter: the splitter's `purge` becomes an inlet."""
    purge = _connection(document, "S7")
    purge["from"], purge["to"] = (
        {"instance": purge["to"]["instance"], "port": "inlet"},
        {"instance": "U-SPLIT", "port": "purge"},
    )


def _drop_connection(document: Document, stream: str) -> None:
    document["connections"] = [c for c in document["connections"] if c["id"] != stream]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        # Review S5: the codes of R1-R5 and the port check no test named before.
        (
            lambda d: d.__setitem__("instances", []),
            ("incomplete", "instances_missing"),
        ),
        (
            lambda d: _connection(d, "S3").__setitem__("phase_capability", "solid"),
            ("unsupported", "phase_capability_unsupported(S3)"),
        ),
        (
            lambda d: _connection(d, "S3").__setitem__("to", {"instance": "U-FLASH"}),
            ("incomplete", "endpoint_missing(S3.to)"),
        ),
        (
            lambda d: _connection(d, "S4").__setitem__(
                "from", {"instance": "U-FLASH", "port": "inlet"}
            ),
            ("conflict", "port_direction_conflict(U-FLASH.inlet)"),
        ),
        (
            lambda d: _specification(d, "SPEC-feed-T").__setitem__("value", "360"),
            ("unsupported", "specification_value_unreadable(SPEC-feed-T)"),
        ),
        (
            lambda d: _specification(d, "SPEC-feed-T")["target"].__setitem__("object_id", "S99"),
            ("incomplete", "specification_target_unknown(SPEC-feed-T)"),
        ),
        (
            lambda d: _specification(d, "SPEC-splitter-r")["target"].__setitem__(
                "object_id", "U-NOWHERE"
            ),
            ("incomplete", "specification_target_unknown(SPEC-splitter-r)"),
        ),
        (
            lambda d: _specification(d, "SPEC-feed-T")["target"].__setitem__("path", "state.H"),
            ("unsupported", "specification_unsupported(SPEC-feed-T)"),
        ),
        (
            lambda d: _specification(d, "SPEC-splitter-r")["target"].__setitem__(
                "path", "holdup.M"
            ),
            ("unsupported", "specification_unsupported(SPEC-splitter-r)"),
        ),
        (
            lambda d: _specification(d, "SPEC-feed-T")["target"].__setitem__("object_type", "port"),
            ("unsupported", "specification_unsupported(SPEC-feed-T)"),
        ),
        (
            lambda d: _instance(d, "U-HEAT")["parameters"].__setitem__("pressure_drop", 0.0),
            ("unsupported", "parameter_unreadable(U-HEAT.pressure_drop)"),
        ),
        (
            lambda d: _drop_connection(d, "S7"),
            ("incomplete", "port_unwired(U-SPLIT.purge)"),
        ),
        (
            lambda d: d["instances"].append(
                dict(copy.deepcopy(_instance(d, "U-PURGE")), id="U-SINK-X")
            ),
            ("incomplete", "port_unwired(U-SINK-X.inlet)"),
        ),
        (
            lambda d: _extra_sink(d, {"instance": "U-FLASH", "port": "side"}, "liquid"),
            ("unsupported", "port_unsupported(U-FLASH.side)"),
        ),
        (
            _reverse_purge,
            ("unsupported", "port_direction_unsupported(U-SPLIT.purge)"),
        ),
        (
            lambda d: _extra_sink(d, {"instance": "U-FLASH", "port": "vapor"}, "vapor"),
            ("unsupported", "port_multiplicity_unsupported(U-FLASH.vapor)"),
        ),
        # R1: ids without `.` or `:`, unique.
        (_set_instance_id, ("unsupported", "id_unsupported(U.FEED)")),
        (
            lambda d: _connection(d, "S2").__setitem__("id", "S1"),
            ("conflict", "id_duplicate(S1)"),
        ),
        # R2: exactly [A, B, C].
        (
            lambda d: d["component_set"].__setitem__("components", ["A", "B"]),
            ("unsupported", "components_unsupported"),
        ),
        # R3: material connections with both endpoints and a capability.
        (
            lambda d: _connection(d, "S3").__setitem__("kind", "energy"),
            ("unsupported", "connection_kind_unsupported(S3)"),
        ),
        (
            lambda d: _connection(d, "S3").pop("phase_capability"),
            ("incomplete", "phase_capability_missing(S3)"),
        ),
        (
            lambda d: _connection(d, "S3").__setitem__(
                "to", {"instance": "U-NOWHERE", "port": "inlet"}
            ),
            ("incomplete", "instance_missing(U-NOWHERE)"),
        ),
        # R4: one declared phase per port, and each model's port phase rule.
        (
            lambda d: _connection(d, "S6").__setitem__("phase_capability", "vapor"),
            ("unsupported", "port_phase_ambiguous(U-MIX.inlet)"),
        ),
        (
            lambda d: _connection(d, "S4").__setitem__("phase_capability", "liquid"),
            ("unsupported", "port_phase_unsupported(U-FLASH.vapor)"),
        ),
        # R5: fixed specifications only, routed, consumed, consistent.
        (
            lambda d: _specification(d, "SPEC-feed-T").__setitem__("role", "free"),
            ("unsupported", "specification_role_unsupported(SPEC-feed-T)"),
        ),
        (_add_unconsumed_pin, ("unsupported", "specification_unconsumed(SPEC-mixer-outlet-T)")),
        (
            lambda d: _specification(d, "SPEC-splitter-r").__setitem__("value", 0.7),
            ("conflict", "specification_conflict(SPEC-splitter-r, U-SPLIT.split_fraction)"),
        ),
        (
            lambda d: d["specifications"].remove(_specification(d, "SPEC-heater-outlet-T")),
            ("incomplete", "specification_missing(S3.T)"),
        ),
        # R6: required parameters, no defaults, nothing unread.
        (
            _drop_split_fraction,
            ("incomplete", "parameter_missing(U-SPLIT.split_fraction)"),
        ),
        (
            lambda d: _instance(d, "U-HEAT")["parameters"]["pressure_drop"].__setitem__(
                "value", 100.0
            ),
            ("unsupported", "parameter_value_unsupported(U-HEAT.pressure_drop)"),
        ),
        (
            # A whole, valid Quantity (W11 checks it at parse time), read by no builder.
            lambda d: _instance(d, "U-FEED")["parameters"].__setitem__(
                "pressure_drop", dict(_instance(d, "U-HEAT")["parameters"]["pressure_drop"])
            ),
            ("unsupported", "parameter_unsupported(U-FEED.pressure_drop)"),
        ),
        # The builder table.
        (
            lambda d: _instance(d, "U-HEAT")["model"].__setitem__("id", "syn001.compressor"),
            ("unsupported", "model_unsupported(syn001.compressor)"),
        ),
    ],
    ids=[
        "S5-R1-instances-missing",
        "S5-R3-capability-unsupported",
        "S5-R3-endpoint-missing",
        "S5-R3-direction-conflict",
        "S5-R5-value-unreadable",
        "S5-R5-target-unknown-connection",
        "S5-R5-target-unknown-instance",
        "S5-R5-unsupported-connection-path",
        "S5-R5-unsupported-instance-path",
        "S5-R5-unsupported-object-type",
        "S5-R6-parameter-unreadable",
        "S5-port-unwired",
        "S5-port-unwired-lone-unit",
        "S5-port-unsupported",
        "S5-port-direction-unsupported",
        "S5-port-multiplicity-unsupported",
        "R1-id",
        "R1-duplicate",
        "R2-components",
        "R3-kind",
        "R3-capability",
        "R3-endpoint",
        "R4-ambiguous",
        "R4-port-rule",
        "R5-role",
        "R5-unconsumed",
        "R5-parameter-conflict",
        "R5-missing-pin",
        "R6-missing",
        "R6-nonzero-drop",
        "R6-unread",
        "builders",
    ],
)
def test_refusal(change: Callable[[Document], None], expected: tuple[str, str]) -> None:
    assert _refused(_edit(change)) == expected


@pytest.mark.parametrize(
    ("case", "unit", "outlets", "pins"),
    [
        (
            "SYN-001-UL-C1",
            "U-VLV",
            [Outlet("outlet", "S2", "vapor_liquid")],
            [connection_pin("SPEC-valve-P", "S2", "state.P", 1.0e5)],
        ),
        (
            "SYN-001-UL-C1",
            "U-PHF",
            [Outlet("vapor", "S2", "vapor"), Outlet("liquid", "S3", "liquid")],
            [duty_pin("SPEC-phf-Q", "U-PHF", 1.0e4)],
        ),
        (
            "SYN-001-UL-C2",
            "U-SEP",
            [Outlet("top", "S2", "liquid"), Outlet("bottom", "S3", "liquid")],
            [],
        ),
    ],
    ids=["valve", "ph_flash", "separator"],
)
def test_a_lifted_connection_from_a_non_lifting_producer_is_refused(
    case: str, unit: str, outlets: list[Outlet], pins: list[Document]
) -> None:
    """Note §1.3 R4's converse (ruling round, review S1, probe P1): a feed declared
    `vapor_liquid` used to bind and then fail with an untyped `KeyError` in `plan_revision`,
    because only the `outlet` port of an `outlet`-style lifting model allocates `<S>.vap/liq.*`."""
    feed = Feed("inlet", "S1", "vapor_liquid", (1.0, 1.0, 1.0), 360.0, 1.8e5)
    document = mini_revision(f"S1-{unit}", unit_instance(case, unit), [feed], outlets, pins)
    assert bind_revision_flowsheet(document) == Unbound(
        "unsupported", "port_phase_unsupported(U-FEED-0.outlet)"
    )


def test_a_parameter_specification_supplies_an_absent_parameter(shaped: RevisionBinding) -> None:
    """R5: `parameters.<name>` supplies the parameter when the instance does not declare it."""
    document = shaped_revision()
    del _instance(document, "U-SPLIT")["parameters"]["split_fraction"]
    assert _bind(document).spec.parameters == shaped.spec.parameters


def test_a_constructor_refusal_is_inadmissible_with_its_first_line() -> None:
    document = shaped_revision()
    _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["value"] = 1.0
    _specification(document, "SPEC-splitter-r")["value"] = 1.0
    kind, detail = _refused(document)
    assert kind == "inadmissible"  # T07 ruling round 5, S3: a fixed value the model refuses
    # T07 ruling round 5, S3: the refusal names itself, then the model's first line.
    assert detail.startswith("value_outside_model_domain: U-SPLIT: ")
    assert "\n" not in detail


def test_parse_errors_carry_kind_and_code() -> None:
    document = shaped_revision()
    document["component_set"]["components"] = ["A", "B", "C", "D"]
    with pytest.raises(RevisionError) as raised:
        parse_revision(document)
    assert (raised.value.kind, raised.value.code) == ("unsupported", "components_unsupported")
