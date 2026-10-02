"""T05 W11: the coupled-case revisions, the six T05 builders, and the registry family.

Design note `docs/design/T05-generalization.md` §1.3 (R1–R6 and the per-model table), §2.4 (each
case's instances, connections, pins and parameters), §8 (W11); spec
`docs/derivations/T05-unit-models-spec.md` §11, §21 and A25.

The strongest check here is the last one: the twin's solution state of each solvable case
(`ref.coupled_cases`) makes every row of the spec assembled from the case file vanish within K04's
per-kind tolerance. A mis-wired port, a swapped pin or a wrong parameter moves some row by decades
more than that (spec §11.5), so the case files are checked against the spec's equations, not
against themselves.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_json, load_yaml, sha256_of
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from t05_support import REF
from t05_syn001_shaped import shaped_revision

from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models import Wiring
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.orchestrator.splits import check_agreement, lifted_splits
from openflowsheet.units import check_quantity
from openflowsheet.verify.checks import KIND_TOLERANCE

Document = dict[str, Any]

CASE_DIR = REPO_ROOT / "benchmarks" / "t05" / "cases"
CASES = ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X")
REFERENCE = REPO_ROOT / "benchmarks" / "t05" / "reference_values.yaml"
REFERENCE_SHA256 = "af4a543f8dab3d95c32764117be00afbc9e8d49478998e8538a1daf359385a6a"

#: Design note §2.4, the instances in declaration order.
DECLARATION_ORDER = {
    "SYN-001-UL-C1": ("U-FEED", "U-PUMP", "U-HEAT", "U-VLV", "U-PHF", "U-SINK-V", "U-SINK-L"),
    "SYN-001-UL-C2": ("U-FEED", "U-MIX", "U-RX", "U-SEP", "U-PROD"),
    "SYN-001-UL-C3": ("U-FEED", "U-HX", "U-MIX", "U-PHF", "U-SPLIT", "U-PROD", "U-SINK"),
    "SYN-001-UL-C3X": ("U-FEED", "U-HX", "U-MIX", "U-PHF", "U-SPLIT", "U-PROD", "U-SINK"),
}
_C3_EDGES = (
    ("S1", "U-FEED", "U-HX"),
    ("S2", "U-HX", "U-MIX"),
    ("S3", "U-MIX", "U-PHF"),
    ("S4", "U-PHF", "U-PROD"),
    ("S5", "U-PHF", "U-SPLIT"),
    ("S6", "U-SPLIT", "U-MIX"),
    ("S7", "U-SPLIT", "U-HX"),
    ("S8", "U-HX", "U-SINK"),
)
#: Design note §2.4, `(stream, producer, consumer)` in stream order.
EDGES = {
    "SYN-001-UL-C1": (
        ("S1", "U-FEED", "U-PUMP"),
        ("S2", "U-PUMP", "U-HEAT"),
        ("S3", "U-HEAT", "U-VLV"),
        ("S4", "U-VLV", "U-PHF"),
        ("S5", "U-PHF", "U-SINK-V"),
        ("S6", "U-PHF", "U-SINK-L"),
    ),
    "SYN-001-UL-C2": (
        ("S1", "U-FEED", "U-MIX"),
        ("S2", "U-MIX", "U-RX"),
        ("S3", "U-RX", "U-SEP"),
        ("S4", "U-SEP", "U-MIX"),
        ("S5", "U-SEP", "U-PROD"),
    ),
    "SYN-001-UL-C3": _C3_EDGES,
    "SYN-001-UL-C3X": _C3_EDGES,
}
#: A26's units, in declaration order (design note §2.4's `branch_found`).
LIFTED_UNITS = {
    "SYN-001-UL-C1": ["U-HEAT", "U-VLV", "U-PHF"],
    "SYN-001-UL-C2": ["U-RX"],
    "SYN-001-UL-C3": ["U-PHF"],
    "SYN-001-UL-C3X": ["U-PHF"],
}
#: `(rows, columns)` of each assembled spec. C1 is square; in C2 and C3 the pressure rows around
#: the recycle are one more than the pressure columns they fix (the loop makes one redundant, as
#: in SYN-001's 49 over 47) — T01 puts them in the over-determined block and closes the system.
SHAPES = {
    "SYN-001-UL-C1": (51, 51),
    "SYN-001-UL-C2": (37, 36),
    "SYN-001-UL-C3": (45, 44),
    "SYN-001-UL-C3X": (45, 44),
}


def _schema_registry() -> Registry:
    resources = []
    for path in sorted((REPO_ROOT / "schemas").glob("*.schema.json")):
        document = load_json(path)
        resources.append((document["$id"], Resource(contents=document, specification=DRAFT202012)))
    return Registry().with_resources(resources)


_REVISION_VALIDATOR = Draft202012Validator(
    load_json(REPO_ROOT / "schemas" / "process-revision.schema.json"), registry=_schema_registry()
)


def case_document(case: str) -> Document:
    """A fresh copy of a case revision; callers may mutate it."""
    return copy.deepcopy(_DOCUMENTS[case])


_DOCUMENTS: dict[str, Document] = {case: load_yaml(CASE_DIR / f"{case}.yaml") for case in CASES}


def _bind(document: Document) -> RevisionBinding:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    return binding


@pytest.fixture(scope="module")
def bindings() -> dict[str, RevisionBinding]:
    return {case: _bind(case_document(case)) for case in CASES}


def _instances(binding: RevisionBinding) -> list[tuple[str, str, Wiring]]:
    flowsheet = binding.flowsheet
    return [(u.unit_id, u.model_id, flowsheet.wiring[u.unit_id]) for u in flowsheet.units()]


def _connection(document: Document, stream: str) -> dict[str, Any]:
    (entry,) = (c for c in document["connections"] if c["id"] == stream)
    return entry


def _instance(document: Document, unit: str) -> dict[str, Any]:
    (entry,) = (i for i in document["instances"] if i["id"] == unit)
    return entry


def _specification(document: Document, name: str) -> dict[str, Any]:
    (entry,) = (s for s in document["specifications"] if s["id"] == name)
    return entry


def _refused(document: Document) -> tuple[str, str]:
    result = bind_revision_flowsheet(document)
    assert isinstance(result, Unbound), result
    return result.kind, result.detail


# -- the unit check (the W1.b follow-up): a value is read in its kind's SI unit or refused -------
#
# ADR 0016 D9.1 (T06 A73): `unit-conversion-v2` converts `kPa`, `bar` and `%` (on a fraction), so
# the four unit mutations are re-pointed to units that stay refused, with the same codes; the four
# old mutations are registered with their new outcomes in `tests/test_t06_w12_units_v2.py`.


def test_the_shaped_revision_still_binds() -> None:
    assert isinstance(bind_revision_flowsheet(shaped_revision()), RevisionBinding)


def _millimetre_of_mercury_drop(document: Document) -> None:
    drop = _instance(document, "U-HEAT")["parameters"]["pressure_drop"]
    drop["unit"] = "mmHg"


def _drop_as_temperature(document: Document) -> None:
    drop = _instance(document, "U-HEAT")["parameters"]["pressure_drop"]
    drop.update(kind="temperature_difference", unit="K", dimension=[0, 0, 0, 1, 0, 0, 0])


def _drop_with_wrong_dimension(document: Document) -> None:
    _instance(document, "U-HEAT")["parameters"]["pressure_drop"]["dimension"] = [0] * 7


def _drop_without_meaning(document: Document) -> None:
    del _instance(document, "U-HEAT")["parameters"]["pressure_drop"]["meaning"]


def _ppm_split(document: Document) -> None:
    _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["unit"] = "ppm"


def _feed_pressure_in_barg(document: Document) -> None:
    _specification(document, "SPEC-feed-P")["unit"] = "barg"


def _feed_temperature_as_pressure(document: Document) -> None:
    _specification(document, "SPEC-feed-T").update(kind="pressure", unit="Pa")


def _split_specification_in_ppm(document: Document) -> None:
    _specification(document, "SPEC-splitter-r")["unit"] = "ppm"


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            _millimetre_of_mercury_drop,
            ("unsupported", "parameter_unit_unsupported(U-HEAT.pressure_drop)"),
        ),
        (
            _drop_as_temperature,
            ("unsupported", "parameter_kind_unsupported(U-HEAT.pressure_drop)"),
        ),
        (
            _drop_with_wrong_dimension,
            ("unsupported", "parameter_quantity_invalid(U-HEAT.pressure_drop)"),
        ),
        (
            _drop_without_meaning,
            ("unsupported", "parameter_quantity_invalid(U-HEAT.pressure_drop)"),
        ),
        (_ppm_split, ("unsupported", "parameter_unit_unsupported(U-SPLIT.split_fraction)")),
        (_feed_pressure_in_barg, ("unsupported", "specification_unit_unsupported(SPEC-feed-P)")),
        (
            _feed_temperature_as_pressure,
            ("unsupported", "specification_kind_unsupported(SPEC-feed-T)"),
        ),
        (
            _split_specification_in_ppm,
            ("unsupported", "specification_unit_unsupported(SPEC-splitter-r)"),
        ),
    ],
    ids=[
        "mmHg-drop",
        "drop-kind",
        "drop-dimension",
        "drop-incomplete",
        "ppm-split",
        "barg-pin",
        "pin-kind",
        "parameter-pin-ppm",
    ],
)
def test_a_value_outside_its_si_unit_is_refused(change: Any, expected: tuple[str, str]) -> None:
    document = shaped_revision()
    change(document)
    assert _refused(document) == expected


# -- the case documents (design note §1.3, §2.4) -------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_case_document_is_schema_valid(case: str) -> None:
    document = case_document(case)
    errors = [
        f"{list(error.absolute_path)}: {error.message}"
        for error in _REVISION_VALIDATOR.iter_errors(document)
    ]
    assert not errors, errors
    assert document["revision_id"] == f"{case}-r1"
    for instance in document["instances"]:
        for name, quantity in instance["parameters"].items():
            assert check_quantity(quantity) == (), f"{instance['id']}.{name}"


@pytest.mark.parametrize("case", CASES)
def test_case_binds_in_declaration_and_stream_order(
    case: str, bindings: dict[str, RevisionBinding]
) -> None:
    binding = bindings[case]
    assert tuple(u.unit_id for u in binding.flowsheet.units()) == DECLARATION_ORDER[case]
    assert binding.graph.units == DECLARATION_ORDER[case]
    assert binding.flowsheet.streams == tuple(stream for stream, _, _ in EDGES[case])
    assert tuple((c.stream_id, c.producer, c.consumer) for c in binding.graph.connections) == tuple(
        sorted(EDGES[case])
    )
    assert set(binding.row_units) == set(binding.spec.equation_ids)


def _feed(flows: tuple[float, float, float]) -> dict[str, float]:
    return {
        **{f"U-FEED.n_spec.{c}": n for c, n in zip("ABC", flows, strict=True)},
        "U-FEED.T_spec": 300.0,
        "U-FEED.P_spec": 1e5,
    }


def _c3(hot_outlet: float) -> dict[str, float]:
    return {
        **_feed((1.0, 1.0, 1.0)),
        "U-HX.T_spec": hot_outlet,
        "U-PHF.Q_spec": 48000.0,
        "U-PHF.pressure_drop": 0.0,
        "U-SPLIT.split_fraction": 0.6,
    }


#: Design note §2.4's pins and parameters, as the assembled spec's pinned inputs.
PINNED = {
    "SYN-001-UL-C1": {
        **_feed((1.0, 1.0, 1.0)),
        "U-PUMP.P_spec": 1.8e5,
        "U-PUMP.efficiency": 0.75,
        "U-HEAT.T_spec": 360.0,
        "U-HEAT.pressure_drop": 0.0,
        "U-VLV.P_spec": 1e5,
        "U-PHF.Q_spec": 10000.0,
        "U-PHF.pressure_drop": 0.0,
    },
    "SYN-001-UL-C2": {
        **_feed((2.0, 1.0, 0.0)),
        "U-RX.nu.A": -2.0,
        "U-RX.nu.B": -1.0,
        "U-RX.nu.C": 3.0,
        "U-RX.conversion": 0.5,
        "U-RX.pressure_drop": 0.0,
        "U-RX.T_spec": 315.0,
        "U-SEP.split.A": 0.9,
        "U-SEP.split.B": 0.8,
        "U-SEP.split.C": 0.05,
    },
    "SYN-001-UL-C3": _c3(310.0),
    "SYN-001-UL-C3X": _c3(290.0),
}


@pytest.mark.parametrize("case", CASES)
def test_case_pins_and_parameters_are_the_designs(
    case: str, bindings: dict[str, RevisionBinding]
) -> None:
    spec = bindings[case].spec
    assert set(spec.parameter_ids) == set(spec.parameters)
    assert dict(spec.parameters) == PINNED[case]


def test_case_configurations_are_the_designs(bindings: dict[str, RevisionBinding]) -> None:
    """§1.3's last column, read off the constructed units (spec §11)."""

    def unit(case: str, unit_id: str) -> Any:
        (found,) = (u for u in bindings[case].flowsheet.units() if u.unit_id == unit_id)
        return found

    assert unit("SYN-001-UL-C1", "U-HEAT").inlet_phase == "LIQUID"
    assert unit("SYN-001-UL-C1", "U-VLV").inlet_phase is None
    assert unit("SYN-001-UL-C1", "U-PHF").inlet_phase is None
    reactor = unit("SYN-001-UL-C2", "U-RX")
    assert (reactor.inlet_phase, reactor.key_component, reactor.energy_specification) == (
        "LIQUID",
        "A",
        "outlet_temperature",
    )
    separator = unit("SYN-001-UL-C2", "U-SEP")
    assert (separator.inlet_phase, separator.top_phase, separator.bottom_phase) == (
        None,
        "LIQUID",
        "LIQUID",
    )
    for case in ("SYN-001-UL-C3", "SYN-001-UL-C3X"):
        exchanger = unit(case, "U-HX")
        assert (exchanger.specification, exchanger.hot_phase, exchanger.cold_phase) == (
            "hot_outlet_temperature",
            "LIQUID",
            "LIQUID",
        )
        assert unit(case, "U-PHF").inlet_phase == "LIQUID"


# -- structure: T01 and the lifted-split agreement (design note §3.3) ----------------------------


@pytest.mark.parametrize("case", CASES)
def test_case_is_structurally_closed(case: str, bindings: dict[str, RevisionBinding]) -> None:
    binding = bindings[case]
    assert (len(binding.spec.equation_ids), len(binding.spec.variable_ids)) == SHAPES[case]
    model_version, constants = declaration_identity(binding.spec)
    report = analyse(
        binding.spec,
        binding.graph,
        model_version=model_version,
        constants_sha256=constants,
        row_units=binding.row_units,
    )
    assert report.finding == "STRUCTURALLY_CLOSED", case
    assert report.excess == 0 and report.deficit == 0
    assert report.structural_counts is not None
    assert report.structural_counts["matched"] == len(binding.spec.variable_ids)


@pytest.mark.parametrize("case", CASES)
def test_lifted_splits_agree_with_the_rows(case: str, bindings: dict[str, RevisionBinding]) -> None:
    """§3.3 (a)–(e), and A26's units in declaration order."""
    binding = bindings[case]
    instances = _instances(binding)
    splits = lifted_splits(instances, binding.flowsheet.components)
    assert [split.unit for split in splits] == LIFTED_UNITS[case]
    model_version, constants = declaration_identity(binding.spec)
    declaration = trace_declaration(
        binding.spec,
        model_version=model_version,
        constants_sha256=constants,
        row_units=binding.row_units,
    )
    check_agreement(instances, splits, binding.spec, binding.row_units, declaration)


# -- the rows at the twin's coupled solution states ----------------------------------------------


def reference_state(case: str) -> dict[str, float]:
    """`ref.coupled_cases.<case>` as doubles, by column id.

    Streams give `(n, T, P)`; a lifted stream its `vap`/`liq` flows and their totals `V`, `L`; a
    flash product its total `N`; duties, work and extent their unit's `Q`, `W`, `xi`.
    """
    entry = REF["coupled_cases"][case]
    x: dict[str, float] = {}
    for stream, state in entry["streams"].items():
        flows = [float(n) for n in state["n_mol_per_s"]]
        for component, n in zip("ABC", flows, strict=True):
            x[f"{stream}.n.{component}"] = n
        x[f"{stream}.T"] = float(state["T_K"])
        x[f"{stream}.P"] = float(state["P_Pa"])
        x[f"{stream}.N"] = sum(float(n) for n in state["n_mol_per_s"])
        if "vapor_n_mol_per_s" in state:
            for phase, key, total in (("vap", "vapor", "V"), ("liq", "liquid", "L")):
                values = [float(n) for n in state[f"{key}_n_mol_per_s"]]
                for component, n in zip("ABC", values, strict=True):
                    x[f"{stream}.{phase}.{component}"] = n
                x[f"{stream}.{total}"] = sum(values)
    for field, suffix in (("duty_W", "Q"), ("work_W", "W"), ("extent_mol_per_s", "xi")):
        for unit, value in (entry.get(field) or {}).items():
            x[f"{unit}.{suffix}"] = float(value)
    return x


def rows_at_reference(binding: RevisionBinding, case: str) -> tuple[float, str]:
    """The worst `|row| / KIND_TOLERANCE[kind]` at the reference state, and its row.

    Compiled and evaluated exactly as `t05_trial_states` does: K01's CasADi adapter on the
    assembled spec, at the spec's own pinned inputs.
    """
    spec = binding.spec
    x = reference_state(case)
    missing = [column for column in spec.variable_ids if column not in x]
    assert not missing, f"{case}: the reference has no value for {missing}"
    problem = compile_problem(spec)
    context = EvaluationContext(
        model_version=problem.metadata.model_version,
        constants_sha256=problem.metadata.constants_sha256,
    )
    residual = problem.residual(np.array([x[column] for column in spec.variable_ids]), context)
    assert residual.status == "ok" and residual.values is not None, residual.message
    assert list(residual.equation_ids) == list(spec.equation_ids)
    return max(
        (abs(float(value)) / KIND_TOLERANCE[spec.row_kinds[row]], row)
        for row, value in zip(residual.equation_ids, residual.values, strict=True)
    )


@pytest.mark.parametrize("case", CASES)
def test_every_row_vanishes_at_the_reference_state(
    case: str, bindings: dict[str, RevisionBinding]
) -> None:
    """C1–C3's solutions, and C3X's (its rows have a solution; spec §11.4), within K04's `τ`.

    Measured worst ratios (`docs/t05-measurements.md`, W11) are ~1e-8: the double conversion of
    the 20-digit reference. A wiring or pin error is at least decades above 1.
    """
    ratio, row = rows_at_reference(bindings[case], case)
    assert ratio <= 1.0, f"{case}: {row} at {ratio:.3g} of its tolerance"


def test_a_miswired_case_does_not_vanish_at_the_reference() -> None:
    """The negative control: the splitter's outlets swapped (spec §11.3's reason for r = 0.6)."""
    document = case_document("SYN-001-UL-C3")
    _connection(document, "S6")["from"]["port"] = "purge"
    _connection(document, "S7")["from"]["port"] = "recycle"
    ratio, _ = rows_at_reference(_bind(document), "SYN-001-UL-C3")
    assert ratio > 1e3


# -- the six T05 builders: refusals, one test per model ------------------------------------------


def _add_pin(document: Document, name: str, stream: str, path: str, value: float) -> None:
    kind, unit = {"state.T": ("temperature", "K"), "state.P": ("pressure", "Pa")}[path]
    document["specifications"].append(
        {
            "id": name,
            "target": {
                "object_type": "connection",
                "object_id": stream,
                "path": path,
                "component": None,
            },
            "kind": kind,
            "unit": unit,
            "value": value,
            "tolerance": {"absolute": 1.0e-6},
            "role": "fixed",
            "provenance": "tests/test_t05_w11_cases.py",
        }
    )


def _drop_parameter(unit: str, name: str) -> Callable[[Document], None]:
    def change(document: Document) -> None:
        del _instance(document, unit)["parameters"][name]

    return change


def _drop_specification(name: str) -> Callable[[Document], None]:
    def change(document: Document) -> None:
        document["specifications"].remove(_specification(document, name))

    return change


def _pin(name: str, stream: str, path: str, value: float) -> Callable[[Document], None]:
    def change(document: Document) -> None:
        _add_pin(document, name, stream, path, value)

    return change


def _capability(stream: str, capability: str) -> Callable[[Document], None]:
    def change(document: Document) -> None:
        _connection(document, stream)["phase_capability"] = capability

    return change


def _set_value(unit: str, name: str, value: float) -> Callable[[Document], None]:
    def change(document: Document) -> None:
        _instance(document, unit)["parameters"][name]["value"] = value

    return change


def _second_conversion(document: Document) -> None:
    parameters = _instance(document, "U-RX")["parameters"]
    parameters["conversion.B"] = dict(parameters["conversion.A"])


def _no_conversion(document: Document) -> None:
    del _instance(document, "U-RX")["parameters"]["conversion.A"]


def _reactor_duty_too(document: Document) -> None:
    extra = dict(_specification(document, "SPEC-feed-T"))
    extra.update(
        id="SPEC-reactor-Q",
        target={"object_type": "instance", "object_id": "U-RX", "path": "duty.Q"},
        kind="heat_rate",
        unit="W",
        value=4500.0,
    )
    document["specifications"].append(extra)


REFUSALS: dict[str, tuple[str, list[tuple[Callable[[Document], None], tuple[str, str]]]]] = {
    "syn001.ph_flash": (
        "SYN-001-UL-C1",
        [
            (
                _drop_parameter("U-PHF", "pressure_drop"),
                ("incomplete", "parameter_missing(U-PHF.pressure_drop)"),
            ),
            (
                _pin("SPEC-phf-T", "S5", "state.T", 350.0),
                ("unsupported", "specification_unconsumed(SPEC-phf-T)"),
            ),
            (_drop_specification("SPEC-phf-Q"), ("incomplete", "specification_missing(U-PHF.Q)")),
            (_capability("S5", "liquid"), ("unsupported", "port_phase_unsupported(U-PHF.vapor)")),
        ],
    ),
    "syn001.valve": (
        # No parameter: the required input is the outlet-pressure pin.
        "SYN-001-UL-C1",
        [
            (_drop_specification("SPEC-valve-P"), ("incomplete", "specification_missing(S4.P)")),
            (
                _pin("SPEC-valve-T", "S4", "state.T", 350.0),
                ("unsupported", "specification_unconsumed(SPEC-valve-T)"),
            ),
            (_capability("S4", "liquid"), ("unsupported", "port_phase_unsupported(U-VLV.outlet)")),
        ],
    ),
    "syn001.liquid_pump": (
        "SYN-001-UL-C1",
        [
            (
                _drop_parameter("U-PUMP", "efficiency"),
                ("incomplete", "parameter_missing(U-PUMP.efficiency)"),
            ),
            (
                _pin("SPEC-pump-T", "S2", "state.T", 301.0),
                ("unsupported", "specification_unconsumed(SPEC-pump-T)"),
            ),
            (_capability("S1", "vapor"), ("unsupported", "port_phase_unsupported(U-PUMP.inlet)")),
            (
                # T07 ruling round 5, S3: a fixed parameter the model refuses at construction.
                _set_value("U-PUMP", "efficiency", 0.0),
                ("inadmissible", "value_outside_model_domain: efficiency_outside_interval"),
            ),
        ],
    ),
    "syn001.conversion_reactor": (
        "SYN-001-UL-C2",
        [
            (_drop_parameter("U-RX", "nu.B"), ("incomplete", "parameter_missing(U-RX.nu.B)")),
            (_no_conversion, ("incomplete", "parameter_missing(U-RX.conversion)")),
            (_second_conversion, ("unsupported", "parameter_unsupported(U-RX.conversion.B)")),
            (
                _pin("SPEC-reactor-P", "S3", "state.P", 1e5),
                ("unsupported", "specification_unconsumed(SPEC-reactor-P)"),
            ),
            (
                _drop_specification("SPEC-reactor-outlet-T"),
                ("incomplete", "specification_missing(U-RX.energy_specification)"),
            ),
            (_reactor_duty_too, ("conflict", "specification_conflict(U-RX.energy_specification)")),
            (_capability("S3", "liquid"), ("unsupported", "port_phase_unsupported(U-RX.outlet)")),
            # T07 ruling round 5, S3: a fixed parameter the model refuses at construction.
            (
                _set_value("U-RX", "nu.C", 2.0),
                ("inadmissible", "value_outside_model_domain: stoichiometry_not_mass_conserving"),
            ),
        ],
    ),
    "syn001.component_separator": (
        "SYN-001-UL-C2",
        [
            (
                _drop_parameter("U-SEP", "split.C"),
                ("incomplete", "parameter_missing(U-SEP.split.C)"),
            ),
            (
                _pin("SPEC-sep-T", "S5", "state.T", 315.0),
                ("unsupported", "specification_unconsumed(SPEC-sep-T)"),
            ),
            (
                _capability("S5", "vapor_liquid"),
                ("unsupported", "port_phase_unsupported(U-SEP.bottom)"),
            ),
        ],
    ),
    "syn001.heat_exchanger": (
        # No parameter: the required input is exactly one of three pins.
        "SYN-001-UL-C3",
        [
            (
                _drop_specification("SPEC-hx-hot-outlet-T"),
                ("incomplete", "specification_missing(U-HX.specification)"),
            ),
            (
                _pin("SPEC-hx-cold-outlet-T", "S2", "state.T", 330.0),
                ("conflict", "specification_conflict(U-HX.specification)"),
            ),
            (
                _pin("SPEC-hx-cold-outlet-P", "S2", "state.P", 1e5),
                ("unsupported", "specification_unconsumed(SPEC-hx-cold-outlet-P)"),
            ),
            (
                _capability("S8", "vapor"),
                ("unsupported", "port_phase_unsupported(U-HX.hot_outlet)"),
            ),
        ],
    ),
}


@pytest.mark.parametrize("model", sorted(REFUSALS))
def test_builder_refusals(model: str) -> None:
    """A missing required input and an unconsumed pin, per model; and its port phase rule."""
    case, refusals = REFUSALS[model]
    for change, expected in refusals:
        document = case_document(case)
        change(document)
        assert _refused(document) == expected, expected


# -- A03's flowsheet-level half: configuration moves the label, a pinned value does not -----------


def _label(document: Document) -> tuple[str, str]:
    """The flowsheet label and the `model_version` it heads."""
    binding = _bind(document)
    return binding.flowsheet.label, declaration_identity(binding.spec)[0]


def _once_through(unit: Document, ports: tuple[str, ...], capability: str) -> Document:
    """feed(s) -> `unit` -> one sink per outlet: a revision where every port phase may move.

    `ports` alternate inlet, outlet; each pair gets a feed `F<k>` and a sink `K<k>`. The feed and
    sink instances, and the feed specifications, are C3's.
    """
    source = case_document("SYN-001-UL-C3")
    feed, sink = _instance(source, "U-FEED"), _instance(source, "U-SINK")
    instances: list[dict[str, Any]] = [unit]
    connections: list[dict[str, Any]] = []
    specifications: list[dict[str, Any]] = []
    template = _connection(source, "S1")
    for k in range(0, len(ports), 2):
        inlet, outlet = ports[k], ports[k + 1]
        feed_id, sink_id, into, out = f"U-F{k}", f"U-K{k}", f"S{k}i", f"S{k}o"
        instances += [dict(feed, id=feed_id), dict(sink, id=sink_id)]
        connections += [
            dict(
                template,
                id=into,
                phase_capability=capability,
                **{"from": {"instance": feed_id, "port": "outlet"}},
                to={"instance": unit["id"], "port": inlet},
            ),
            dict(
                template,
                id=out,
                phase_capability=capability,
                **{"from": {"instance": unit["id"], "port": outlet}},
                to={"instance": sink_id, "port": "inlet"},
            ),
        ]
        for specification in source["specifications"]:
            if specification["target"]["object_id"] == "S1":
                pinned = copy.deepcopy(specification)
                pinned["id"] = f"{specification['id']}-{k}"
                pinned["target"]["object_id"] = into
                specifications.append(pinned)
    source.update(instances=instances, connections=connections, specifications=specifications)
    return source


def _exchanger(capability: str = "liquid") -> Document:
    document = _once_through(
        copy.deepcopy(_instance(case_document("SYN-001-UL-C3"), "U-HX")),
        ("hot_inlet", "hot_outlet", "cold_inlet", "cold_outlet"),
        capability,
    )
    for specification in document["specifications"]:  # the hot feed at 360 K
        if specification["id"] == "SPEC-feed-T-0":
            specification["value"] = 360.0
    _add_pin(document, "SPEC-hx-T", "S0o", "state.T", 320.0)
    return document


def _separator_like(unit: Document, ports: tuple[str, str]) -> Document:
    """feed -> `unit` -> two sinks, the second on the separator's `bottom` port."""
    document = _once_through(unit, ports, "liquid")
    document["instances"].append(dict(_instance(document, "U-K0"), id="U-K1"))
    document["connections"].append(
        dict(
            _connection(document, "S0o"),
            id="S1o",
            **{"from": {"instance": unit["id"], "port": "bottom"}},
            to={"instance": "U-K1", "port": "inlet"},
        )
    )
    return document


def _separator() -> Document:
    return _separator_like(
        copy.deepcopy(_instance(case_document("SYN-001-UL-C2"), "U-SEP")), ("inlet", "top")
    )


def _reactor_by_duty(document: Document) -> None:
    _drop_specification("SPEC-reactor-outlet-T")(document)
    _reactor_duty_too(document)


def _hx_spec_to_cold_outlet(document: Document) -> None:
    _drop_specification("SPEC-hx-T")(document)
    _add_pin(document, "SPEC-hx-T", "S2o", "state.T", 330.0)


def _hx_side(side: str) -> Callable[[Document], None]:
    streams = {"hot": ("S0i", "S0o"), "cold": ("S2i", "S2o")}[side]

    def change(document: Document) -> None:
        for stream in streams:
            _connection(document, stream)["phase_capability"] = "vapor"

    return change


def _flash() -> Document:
    """feed -> PH flash -> vapour and liquid sinks, with C1's flash and duty pin."""
    source = case_document("SYN-001-UL-C1")
    document = _separator_like(copy.deepcopy(_instance(source, "U-PHF")), ("inlet", "vapor"))
    _connection(document, "S0o")["phase_capability"] = "vapor"
    _connection(document, "S1o")["from"]["port"] = "liquid"
    document["specifications"].append(_specification(source, "SPEC-phf-Q"))
    return document


def _hot_outlet_value(document: Document) -> None:
    _specification(document, "SPEC-hx-T")["value"] = 330.0


def _rename_conversion_key(document: Document) -> None:
    parameters = _instance(document, "U-RX")["parameters"]
    parameters["conversion.B"] = parameters.pop("conversion.A")


#: `(base, change)` pairs that change a configuration of §1.3's last column.
CONFIGURATION_CHANGES: dict[str, tuple[Callable[[], Document], Callable[[Document], None]]] = {
    "reactor-key": (lambda: case_document("SYN-001-UL-C2"), _rename_conversion_key),
    "reactor-energy-specification": (lambda: case_document("SYN-001-UL-C2"), _reactor_by_duty),
    "separator-top-phase": (_separator, _capability("S0o", "vapor")),
    "separator-bottom-phase": (_separator, _capability("S1o", "vapor")),
    "exchanger-hot-phase": (_exchanger, _hx_side("hot")),
    "exchanger-cold-phase": (_exchanger, _hx_side("cold")),
    "exchanger-specification": (_exchanger, _hx_spec_to_cold_outlet),
    "ph-flash-inlet-phase": (_flash, _capability("S0i", "vapor")),
}
#: `(base, change)` pairs that change only a pinned value.
VALUE_CHANGES: dict[str, tuple[Callable[[], Document], Callable[[Document], None]]] = {
    "reactor-conversion": (
        lambda: case_document("SYN-001-UL-C2"),
        _set_value("U-RX", "conversion.A", 0.4),
    ),
    "separator-split": (
        lambda: case_document("SYN-001-UL-C2"),
        _set_value("U-SEP", "split.A", 0.7),
    ),
    "pump-efficiency": (
        lambda: case_document("SYN-001-UL-C1"),
        _set_value("U-PUMP", "efficiency", 0.6),
    ),
    "ph-flash-duty": (
        lambda: case_document("SYN-001-UL-C1"),
        lambda d: _specification(d, "SPEC-phf-Q").__setitem__("value", 9000.0),
    ),
    "exchanger-outlet-temperature": (_exchanger, _hot_outlet_value),
    "c3x-is-c3-with-another-value": (
        lambda: case_document("SYN-001-UL-C3"),
        lambda d: _specification(d, "SPEC-hx-hot-outlet-T").__setitem__("value", 290.0),
    ),
}


@pytest.mark.parametrize("name", sorted(CONFIGURATION_CHANGES))
def test_a03_flowsheet_label_moves_with_a_configuration(name: str) -> None:
    """Spec A03's flowsheet-level half (register R-047).

    At unit level a configuration change moves no row id (the W9 finding), so `model_version`
    carries it through the revision flowsheet's label, `configuration_sha256`.
    """
    make, change = CONFIGURATION_CHANGES[name]
    base = make()
    changed = make()
    change(changed)
    (label, version), (moved, moved_version) = _label(base), _label(changed)
    assert moved != label
    assert moved_version != version


@pytest.mark.parametrize("name", sorted(VALUE_CHANGES))
def test_a03_flowsheet_label_is_unchanged_by_a_pinned_value(name: str) -> None:
    make, change = VALUE_CHANGES[name]
    base = make()
    changed = make()
    change(changed)
    first, second = _bind(base), _bind(changed)
    assert _label(changed) == _label(base)
    assert declaration_identity(second.spec)[1] != declaration_identity(first.spec)[1]


def test_c3x_differs_from_c3_in_one_pinned_value_only(bindings: dict[str, RevisionBinding]) -> None:
    c3, c3x = bindings["SYN-001-UL-C3"], bindings["SYN-001-UL-C3X"]
    assert c3.flowsheet.label == c3x.flowsheet.label
    assert c3.spec.parameter_ids == c3x.spec.parameter_ids
    differing = [
        pid for pid in c3.spec.parameter_ids if c3.spec.parameters[pid] != c3x.spec.parameters[pid]
    ]
    assert differing == ["U-HX.T_spec"]


# -- the registry (spec §21, A25) --------------------------------------------------------------


def test_a25_registry_family_and_cases() -> None:
    registry = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    (family,) = (f for f in registry["families"] if f["id"] == "SYN-001-UL")
    (syn001,) = (f for f in registry["families"] if f["id"] == "SYN-001")
    assert family["title"] == "Synthetic unit-library cases on the SYN-001 thermodynamics (T05)"
    assert family["kind"] == "synthetic"
    assert (
        family["specification"]
        == family["derivation"]
        == ("docs/derivations/T05-unit-models-spec.md")
    )
    assert family["oracle"] is None and family["oracle_absent_reason"]
    assert family["reference"] == "benchmarks/t05/reference_values.yaml"
    assert family["reference_sha256"] == REFERENCE_SHA256 == sha256_of(REFERENCE)
    assert "ADR 0011 D2" in family["independence_limits"]
    for semantics in family["semantics"]:
        assert (REPO_ROOT / semantics).is_file()
    for key in ("components", "property_domain", "reference_convention", "state_definition"):
        assert family[key] == syn001[key], key
    for key in ("component_balance", "energy_balance", "temperature", "pressure"):
        assert family["tolerances"][key] == syn001["tolerances"][key], key
    for key in ("tear_component_flow", "temperature", "pressure", "duty"):
        assert family["scales"][key] == syn001["scales"][key], key
    budgets = ("property_calls", "newton_iterations_per_attempt", "attempts")
    assert {k: family["budgets"][k] for k in budgets} == {k: syn001["budgets"][k] for k in budgets}

    cases = {case["case_id"]: case for case in registry["cases"] if case["family"] == "SYN-001-UL"}
    assert sorted(cases) == sorted(CASES)
    for case_id, case in cases.items():
        assert case["revision"] == f"benchmarks/t05/cases/{case_id}.yaml"
        assert (REPO_ROOT / case["revision"]).is_file()
        assert case["reference"] == family["reference"]
        assert case["reference_sha256"] == REFERENCE_SHA256
        assert case["reference_key"] == f"coupled_cases.{case_id}"
        assert case_id in REF["coupled_cases"]
        assert case["initializer"]["id"] == "traversal-G0-v1"
        expected = case["expected"]
        if case_id == "SYN-001-UL-C3X":
            assert expected["outcome"] == "typed_failure_or_failed_certificate"
            assert expected["in_success_denominator"] is False
            typed, certificate = expected["accepted"]
            assert typed["message"] == "initializer_failed(U-HX): temperature_cross(cold_end)"
            assert certificate["failing_checks"] == ["bounds_and_domain.U-HX.cold_end"]
            assert certificate["value_K"] == 10.0 and certificate["value_allowance_K"] == 1e-5
        else:
            assert expected["outcome"] == "oracle_values"
            assert expected["in_success_denominator"] is True
            assert [unit for unit, _ in expected["branch_found"]] == LIFTED_UNITS[case_id]
            assert expected["branch_found"] == [
                [unit, REF["coupled_cases"][case_id]["signatures"][unit]]
                for unit in LIFTED_UNITS[case_id]
            ]
