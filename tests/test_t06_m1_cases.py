"""T06 M1: the corpus revisions under `benchmarks/t06/cases/` are schema-valid, and each flowsheet
binds in the declaration and stream order the specification gives.

Spec `docs/derivations/T06-corpus-spec.md` §4.1 (encoding), §4.2 (diagnosis fixtures), §4.3 (the
ten new flowsheets), §9.2 (REF-01…REF-07 and, from W8, PC-2's `SYN-001-T06-PC2`); encoding
`docs/design/T05-generalization.md` §1.3.

As in T05 W11, the strongest check is the twin's: at `ref.closed_form.corpus_cases.<case>` every
row of the spec assembled from the case file vanishes within K04's per-kind tolerance, so the ten
new flowsheets are checked against the specification's equations, not against themselves. The
diagnosis fixtures are checked to differ from their parent by exactly the one stated change; what
validation or binding does with them is T06 W1/W5's to assert.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_json, load_yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.units import check_quantity
from openflowsheet.verify.checks import KIND_TOLERANCE

Document = dict[str, Any]

CASE_DIR = REPO_ROOT / "benchmarks" / "t06" / "cases"
REFERENCE = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")

_V, _L, _P = "U-SINK-V", "U-SINK-L", "U-SINK-P"

#: Spec §4.3 and §9.2: `(instances in declaration order, streams in allocation order)`.
FLOWSHEETS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "SYN-001-T06-THM01": (("U-FEED", "U-FLASH", _V, _L), ("S1", "S2", "S3")),
    "SYN-001-T06-THM02": (("U-FEED", "U-PHF", _V, _L), ("S1", "S2", "S3")),
    "SYN-001-T06-THM10": (("U-FEED", "U-PHF", _V, _L), ("S1", "S2", "S3")),
    "SYN-001-T06-STA02": (
        ("U-FEED", "U-HX", "U-MIX", "U-PHF", "U-SPLIT", "U-PROD", "U-SINK"),
        ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"),
    ),
    "SYN-001-T06-NET02": (
        ("U-FEED", "U-MIX", "U-HEAT", "U-PHF", "U-SPLIT", _V, _P),
        ("S1", "S6", "S2", "S3", "S4", "S5", "S7"),
    ),
    "SYN-001-T06-NET03": (
        ("U-FEED", "U-MIX1", "U-MIX2", "U-HEAT", "U-PHF", "U-SPLIT", "U-COOL", "U-FL2", _P, _V),
        ("S1", "S10", "S2", "S7", "S3", "S4", "S6", "S5", "S9", "S8", "S11"),
    ),
    "SYN-001-T06-NET06": (
        ("U-FEED", "U-HX", "U-PHF", _V, _L),
        ("S1", "S2", "S3", "S4", "S5"),
    ),
    "SYN-001-T06-NET09": (
        ("U-FEED", "U-MIX", "U-RX", "U-FLASH", "U-SPLIT", _V, _P),
        ("S1", "S6", "S2", "S3", "S4", "S5", "S7"),
    ),
    "SYN-001-T06-NET10": (
        ("U-FEED", "U-MIX", "U-FL1", "U-COOL", "U-FL2", "U-SPLIT", _L, _V, _P),
        ("S1", "S8", "S2", "S3", "S4", "S5", "S6", "S7", "S9"),
    ),
    "SYN-001-T06-NET11": (
        ("U-FEED", "U-MIX", "U-PUMP", "U-HEAT", "U-VLV", "U-PHF", "U-SPLIT", _V, _P),
        ("S1", "S8", "S2", "S3", "S4", "S5", "S6", "S7", "S9"),
    ),
    "SYN-001-T06-REF01": (("U-FEED", "U-FEED2", "U-MIX", "U-SINK"), ("S1", "S2", "S3")),
    "SYN-001-T06-REF02": (("U-FEED", "U-SPLIT", "U-SINK-R", _P), ("S1", "S2", "S3")),
    "SYN-001-T06-REF03": (("U-FEED", "U-HEAT", "U-SINK"), ("S1", "S2")),
    "SYN-001-T06-REF04": (("U-FEED", "U-FLASH", _V, _L), ("S1", "S2", "S3")),
    "SYN-001-T06-REF05": (("U-FEED", "U-VLV", "U-SINK"), ("S1", "S2")),
    "SYN-001-T06-REF06": (("U-FEED", "U-PUMP", "U-SINK"), ("S1", "S2")),
    "SYN-001-T06-REF07": (("U-FEED", "U-RX", "U-SINK"), ("S1", "S2")),
    # Positive control PC-2 (§9.2's PC-2 row, Amendment 1): REF-04 at 1.5e5 Pa and 370 K (T06 W8).
    "SYN-001-T06-PC2": (("U-FEED", "U-FLASH", _V, _L), ("S1", "S2", "S3")),
}
NEW_CASES = tuple(case for case in FLOWSHEETS if "REF" not in case and "PC2" not in case)


def _specification(document: Document, name: str) -> Document:
    (entry,) = (s for s in document["specifications"] if s["id"] == name)
    return entry


def _without_heater_temperature(document: Document) -> None:
    document["specifications"] = [
        s for s in document["specifications"] if s["id"] != "SPEC-heater-outlet-T"
    ]


def _component_d(document: Document) -> None:
    _specification(document, "SPEC-feed-n-B")["target"]["component"] = "D"


def _kilograms(document: Document) -> None:
    _specification(document, "SPEC-feed-n-A").update(value=0.1, unit="kg/s")


def _celsius(document: Document) -> None:
    _specification(document, "SPEC-feed-T").update(value=26.85, unit="degC")


def _permuted(document: Document) -> None:
    document["component_set"]["components"] = ["C", "A", "B"]


_NOMINAL = REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"
_C2 = REPO_ROOT / "benchmarks" / "t05" / "cases" / "SYN-001-UL-C2.yaml"

#: Spec §3.2 and §4.2: each diagnosis fixture is its parent with exactly this one change.
DIAGNOSIS: dict[str, tuple[Any, Callable[[Document], None]]] = {
    "SYN-001-T06-STR02": (_NOMINAL, _without_heater_temperature),
    "SYN-001-T06-STR06": (_NOMINAL, _component_d),
    "SYN-001-T06-STA03-kgs": (_NOMINAL, _kilograms),
    "SYN-001-T06-STA03-degC": (_NOMINAL, _celsius),
    "SYN-001-T06-STA04": (_C2, _permuted),
}
ALL_CASES = (*FLOWSHEETS, *DIAGNOSIS)


def _schema_registry() -> Registry:
    resources = []
    for path in sorted((REPO_ROOT / "schemas").glob("*.schema.json")):
        document = load_json(path)
        resources.append((document["$id"], Resource(contents=document, specification=DRAFT202012)))
    return Registry().with_resources(resources)


_REVISION_VALIDATOR = Draft202012Validator(
    load_json(REPO_ROOT / "schemas" / "process-revision.schema.json"), registry=_schema_registry()
)
_DOCUMENTS: dict[str, Document] = {case: load_yaml(CASE_DIR / f"{case}.yaml") for case in ALL_CASES}


def case_document(case: str) -> Document:
    """A fresh copy of a case revision; callers may mutate it."""
    return copy.deepcopy(_DOCUMENTS[case])


def test_the_case_directory_holds_exactly_the_registered_revisions() -> None:
    assert sorted(path.stem for path in CASE_DIR.glob("*.yaml")) == sorted(ALL_CASES)


@pytest.mark.parametrize("case", ALL_CASES)
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


@pytest.fixture(scope="module")
def bindings() -> dict[str, RevisionBinding]:
    out = {}
    for case in FLOWSHEETS:
        binding = bind_revision_flowsheet(case_document(case))
        assert isinstance(binding, RevisionBinding), f"{case}: {binding}"
        out[case] = binding
    return out


@pytest.mark.parametrize("case", FLOWSHEETS)
def test_case_binds_in_declaration_and_stream_order(
    case: str, bindings: dict[str, RevisionBinding]
) -> None:
    binding = bindings[case]
    units, streams = FLOWSHEETS[case]
    assert tuple(u.unit_id for u in binding.flowsheet.units()) == units
    assert binding.graph.units == units
    assert binding.flowsheet.streams == streams
    assert set(binding.row_units) == set(binding.spec.equation_ids)


def reference_state(case: str) -> dict[str, float]:
    """`ref.closed_form.corpus_cases.<case>` as doubles, by column id.

    Streams give `(n, T, P)` and the total `N`; a lifted stream its `vap`/`liq` flows and their
    totals `V`, `L`; duties, work and extent their unit's `Q`, `W`, `xi`.
    """
    entry = REFERENCE["closed_form"]["corpus_cases"][case]
    x: dict[str, float] = {}
    for stream, state in entry["streams"].items():
        flows = [float(n) for n in state["n_mol_per_s"]]
        for component, n in zip("ABC", flows, strict=True):
            x[f"{stream}.n.{component}"] = n
        x[f"{stream}.T"] = float(state["T_K"])
        x[f"{stream}.P"] = float(state["P_Pa"])
        x[f"{stream}.N"] = sum(flows)
        if "vapor_mol_per_s" in state:
            for phase, key, total in (("vap", "vapor", "V"), ("liq", "liquid", "L")):
                values = [float(n) for n in state[f"{key}_mol_per_s"]]
                for component, n in zip("ABC", values, strict=True):
                    x[f"{stream}.{phase}.{component}"] = n
                x[f"{stream}.{total}"] = sum(values)
    for field, suffix in (("duty_W", "Q"), ("work_W", "W"), ("extent_mol_per_s", "xi")):
        for unit, value in (entry.get(field) or {}).items():
            x[f"{unit}.{suffix}"] = float(value)
    return x


@pytest.mark.parametrize("case", NEW_CASES)
def test_every_row_vanishes_at_the_reference_state(
    case: str, bindings: dict[str, RevisionBinding]
) -> None:
    """The twin's 20-digit root makes every assembled row vanish within K04's `τ`.

    A mis-wired port, a swapped pin or a wrong parameter moves some row by decades more."""
    spec = bindings[case].spec
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
    ratio, row = max(
        (abs(float(value)) / KIND_TOLERANCE[spec.row_kinds[row]], row)
        for row, value in zip(residual.equation_ids, residual.values, strict=True)
    )
    assert ratio <= 1.0, f"{case}: {row} at {ratio:.3g} of its tolerance"


_MODEL_KEYS = ("component_set", "instances", "connections", "specifications")


@pytest.mark.parametrize("case", DIAGNOSIS)
def test_diagnosis_fixture_is_its_parent_with_one_change(case: str) -> None:
    parent_path, change = DIAGNOSIS[case]
    parent = load_yaml(parent_path)
    expected = copy.deepcopy(parent)
    change(expected)
    assert expected != parent
    document = case_document(case)
    assert {key: document[key] for key in _MODEL_KEYS} == {
        key: expected[key] for key in _MODEL_KEYS
    }
    assert document["schema_version"] == expected["schema_version"]
    assert document["parent_revision"] is None
