"""P01 schemas: self-validity, round-trip fixtures, deliberate rejections, and the unit rules.

Delivers the plan §2.2 P01 row — ProcessRevision, Quantity, ComponentRecord, ModelManifest,
Specification, ValidationReport — with round-trip fixtures under `tests/fixtures/schemas/`
(plan §2.2, `docs/interfaces-frozen.md` §2), plus the ADR 0001 D1 unit rules implemented by
`openflowsheet.units`.

Round trip means: load the YAML fixture, validate it, dump it to JSON, reload it, validate it
again, and require the two decoded documents to be equal. Every valid fixture is also run
through `check_quantity` for each Quantity it embeds, because JSON Schema cannot reject a
decoded NaN and cannot check that `dimension` and `unit` are the ones registered for `kind`.

The ProcessRevision fixtures are the SYN-001 case files themselves, and the ComponentRecord
fixtures are the SYN-001 component records: the documents the rest of the package uses are the
documents the schema is exercised against, so the two cannot drift apart.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT, load_json, load_yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.units import (
    DIMENSION_ORDER,
    KIND_LOWER_BOUNDS_EXCLUSIVE,
    KIND_SI_UNITS,
    KINDS,
    UnknownKindError,
    check_quantity,
    combine_kinds,
    dimension_of,
    normalize_zero,
)

SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"
CASE_DIR = REPO_ROOT / "benchmarks" / "syn001" / "cases"

P01_SCHEMAS = {
    "quantity": "quantity.schema.json",
    "component_record": "component-record.schema.json",
    "specification": "specification.schema.json",
    "model_manifest": "model-manifest.schema.json",
    "process_revision": "process-revision.schema.json",
    "validation_report": "validation-report.schema.json",
}


# --------------------------------------------------------------------------------------------
# Schema loading and $ref resolution
# --------------------------------------------------------------------------------------------


def _all_schema_documents() -> list[dict[str, Any]]:
    documents = []
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        loaded = load_json(path)
        assert isinstance(loaded, dict)
        documents.append(loaded)
    return documents


_REGISTRY = Registry().with_resources(
    (document["$id"], Resource(contents=document, specification=DRAFT202012))
    for document in _all_schema_documents()
)


def validator_for(name: str) -> Draft202012Validator:
    schema = load_json(SCHEMA_DIR / P01_SCHEMAS[name])
    return Draft202012Validator(schema, registry=_REGISTRY)


def schema_errors(name: str, document: Any) -> list[str]:
    validator = validator_for(name)
    return [
        f"{list(error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]


# --------------------------------------------------------------------------------------------
# Semantic checks that JSON Schema cannot express
# --------------------------------------------------------------------------------------------


def embedded_quantities(name: str, document: Any) -> Iterator[tuple[str, Any]]:
    """Yield (path, quantity) for every Quantity a document of this schema embeds."""
    if name == "quantity":
        yield "$", document
    elif name == "component_record":
        if isinstance(document, dict):
            if "molecular_weight" in document:
                yield "$.molecular_weight", document["molecular_weight"]
            for key, value in (document.get("parameters") or {}).items():
                yield f"$.parameters.{key}", value
    elif name == "process_revision":
        if isinstance(document, dict):
            for index, instance in enumerate(document.get("instances") or []):
                for key, value in (instance.get("parameters") or {}).items():
                    yield f"$.instances[{index}].parameters.{key}", value
            for index, connection in enumerate(document.get("connections") or []):
                for key, value in (connection.get("initialization_hint") or {}).items():
                    yield f"$.connections[{index}].initialization_hint.{key}", value


def specification_problems(specification: Any, path: str = "$") -> list[str]:
    """Kind/unit agreement for a Specification, the analogue of `check_quantity`."""
    problems: list[str] = []
    if not isinstance(specification, dict):
        return [f"{path}: specification is not an object"]
    kind = specification.get("kind")
    if not isinstance(kind, str) or kind not in KIND_SI_UNITS:
        return [f"{path}: unknown or missing specification kind {kind!r}"]
    expected_unit = KIND_SI_UNITS[kind]
    if specification.get("unit") != expected_unit:
        problems.append(
            f"{path}: unit {specification.get('unit')!r} is not the internal SI unit "
            f"{expected_unit!r} for kind {kind!r}"
        )
    for field in ("value",):
        if field in specification:
            value = specification[field]
            if not isinstance(value, int | float) or not math.isfinite(float(value)):
                problems.append(f"{path}.{field}: must be a finite number, got {value!r}")
    return problems


TIME_INDEX = DIMENSION_ORDER.index("time")


def accumulation_problems(document: Any) -> list[str]:
    """ADR 0008 D3.2: a holdup_balance row's dimension is its holdup's dimension per second."""
    problems: list[str] = []
    if not isinstance(document, dict):
        return problems
    equations = (document.get("mathematics") or {}).get("equations") or []
    for index, equation in enumerate(equations):
        accumulation = equation.get("accumulation") if isinstance(equation, dict) else None
        if not isinstance(accumulation, dict) or accumulation.get("kind") != "holdup_balance":
            continue
        holdup_dimension = (accumulation.get("holdup") or {}).get("dimension")
        row_dimension = equation.get("dimension")
        if not isinstance(holdup_dimension, list) or not isinstance(row_dimension, list):
            continue  # the schema reports these
        expected = list(holdup_dimension)
        expected[TIME_INDEX] -= 1
        if row_dimension != expected:
            problems.append(
                f"$.mathematics.equations[{index}] ({equation.get('id')}): holdup_balance row "
                f"dimension {row_dimension} must equal the holdup dimension {holdup_dimension} "
                f"with the time exponent lowered by one"
            )
    return problems


def semantic_problems(name: str, document: Any) -> list[str]:
    problems: list[str] = []
    for path, quantity in embedded_quantities(name, document):
        problems.extend(f"{path}: {problem}" for problem in check_quantity(quantity))
    if name == "model_manifest":
        problems.extend(accumulation_problems(document))
    if name == "specification":
        problems.extend(specification_problems(document))
    if name == "process_revision" and isinstance(document, dict):
        for index, specification in enumerate(document.get("specifications") or []):
            problems.extend(specification_problems(specification, f"$.specifications[{index}]"))
    return problems


def all_problems(name: str, document: Any) -> list[str]:
    return schema_errors(name, document) + semantic_problems(name, document)


# --------------------------------------------------------------------------------------------
# Fixture discovery
# --------------------------------------------------------------------------------------------


def valid_fixtures(name: str) -> list[Path]:
    """Valid fixtures for a schema. Two schemas use the real documents rather than copies."""
    if name == "process_revision":
        return sorted(CASE_DIR.glob("*.yaml"))
    paths = sorted((FIXTURE_DIR / name / "valid").glob("*.yaml"))
    return paths


def invalid_fixtures(name: str) -> list[Path]:
    return sorted((FIXTURE_DIR / name / "invalid").glob("*.yaml"))


def component_records() -> list[dict[str, Any]]:
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "components.yaml")
    assert isinstance(loaded, dict)
    records = loaded["components"]
    assert isinstance(records, list) and len(records) == 3
    return records


def _fixture_id(path: Path) -> str:
    return f"{path.parent.parent.name}/{path.stem}"


ALL_VALID = [
    pytest.param(name, path, id=f"{name}-{path.stem}")
    for name in P01_SCHEMAS
    for path in valid_fixtures(name)
]
ALL_INVALID = [
    pytest.param(name, path, id=f"{name}-{path.stem}")
    for name in P01_SCHEMAS
    for path in invalid_fixtures(name)
]


# --------------------------------------------------------------------------------------------
# The schemas themselves
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(P01_SCHEMAS))
def test_schema_is_itself_a_valid_draft_2020_12_schema(name: str) -> None:
    Draft202012Validator.check_schema(load_json(SCHEMA_DIR / P01_SCHEMAS[name]))


def test_the_frozen_p01_schema_list_is_delivered() -> None:
    """Plan §2.2 and docs/interfaces-frozen.md §2: exactly these six schemas in P01."""
    expected = {
        "ProcessRevision",
        "Quantity",
        "ComponentRecord",
        "ModelManifest",
        "Specification",
        "ValidationReport",
    }
    delivered = {load_json(SCHEMA_DIR / filename)["title"] for filename in P01_SCHEMAS.values()}
    assert delivered == expected


@pytest.mark.parametrize("name", sorted(P01_SCHEMAS))
def test_schema_has_an_id_and_a_description(name: str) -> None:
    schema = load_json(SCHEMA_DIR / P01_SCHEMAS[name])
    assert schema["$id"].endswith(P01_SCHEMAS[name])
    assert len(schema["description"]) > 80, "a schema states what it is for and where it is from"


# --------------------------------------------------------------------------------------------
# ADR 0001 D1: the unit table and the kind rules
# --------------------------------------------------------------------------------------------


def test_units_json_and_the_python_table_agree() -> None:
    """`schemas/units.json` is used by validation; `openflowsheet.units` by code.

    They must be the same table, or a document could pass schema validation and fail the
    runtime check for a reason that is only a bookkeeping difference.
    """
    table = load_json(SCHEMA_DIR / "units.json")
    assert tuple(table["dimension_order"]) == DIMENSION_ORDER
    assert set(table["kinds"]) == set(KINDS)
    for kind, entry in table["kinds"].items():
        assert tuple(entry["dimension"]) == dimension_of(kind), kind
        assert entry["si_unit"] == KIND_SI_UNITS[kind], kind
        assert entry["lower_bound_exclusive"] == KIND_LOWER_BOUNDS_EXCLUSIVE[kind], kind


def test_quantity_schema_kind_enum_matches_the_unit_table() -> None:
    schema = load_json(SCHEMA_DIR / P01_SCHEMAS["quantity"])
    assert set(schema["$defs"]["kind"]["enum"]) == set(KINDS)


def test_dimension_order_is_the_adr_order() -> None:
    """ADR 0001 D1.2, frozen at P01."""
    assert DIMENSION_ORDER == (
        "length",
        "mass",
        "time",
        "temperature",
        "amount",
        "current",
        "luminous_intensity",
    )
    assert dimension_of("pressure") == (-1, 1, -2, 0, 0, 0, 0)
    assert dimension_of("molar_flow") == (0, 0, -1, 0, 1, 0, 0)
    assert dimension_of("molar_enthalpy") == (2, 1, -2, 0, -1, 0, 0)


def test_unknown_kind_is_not_defaulted() -> None:
    with pytest.raises(UnknownKindError):
        dimension_of("mass_density")


def test_temperature_and_temperature_difference_share_a_dimension_and_differ_as_kinds() -> None:
    """ADR 0001 D1.3: same dimension, different kinds, not interchangeable."""
    assert dimension_of("temperature") == dimension_of("temperature_difference")
    assert KIND_LOWER_BOUNDS_EXCLUSIVE["temperature"] == 0.0
    assert KIND_LOWER_BOUNDS_EXCLUSIVE["temperature_difference"] is None


@pytest.mark.parametrize(
    ("left", "operator", "right", "expected"),
    [
        ("temperature", "-", "temperature", "temperature_difference"),
        ("temperature", "+", "temperature_difference", "temperature"),
        ("temperature", "-", "temperature_difference", "temperature"),
        ("temperature_difference", "+", "temperature", "temperature"),
        ("temperature_difference", "+", "temperature_difference", "temperature_difference"),
        ("temperature_difference", "-", "temperature_difference", "temperature_difference"),
        ("pressure", "+", "pressure", "pressure"),
        ("molar_flow", "-", "molar_flow", "molar_flow"),
    ],
)
def test_kind_arithmetic_follows_adr_d1_3(
    left: str, operator: str, right: str, expected: str
) -> None:
    assert combine_kinds(left, operator, right) == expected


def test_adding_two_absolute_temperatures_is_a_validation_error() -> None:
    """ADR 0001 D1.3: `temperature + temperature` has no meaning and is rejected."""
    with pytest.raises(ValueError, match="not a defined operation"):
        combine_kinds("temperature", "+", "temperature")


def test_subtracting_a_temperature_from_a_difference_is_a_validation_error() -> None:
    with pytest.raises(ValueError, match="not a defined operation"):
        combine_kinds("temperature_difference", "-", "temperature")


def test_kinds_sharing_a_dimension_do_not_silently_combine() -> None:
    """`heat_rate` and `power` are both W; combining them needs a declared conversion."""
    with pytest.raises(ValueError, match="distinct kinds"):
        combine_kinds("heat_rate", "+", "power")
    with pytest.raises(ValueError, match="dimensions differ"):
        combine_kinds("pressure", "+", "temperature_difference")


def test_signed_zero_is_normalized_and_flagged() -> None:
    """ADR 0001 D1.5: -0.0 and +0.0 are the same state; canonical form is +0.0."""
    assert normalize_zero(-0.0) == 0.0
    assert math.copysign(1.0, normalize_zero(-0.0)) > 0.0
    assert math.copysign(1.0, normalize_zero(0.0)) > 0.0
    assert normalize_zero(-1.5) == -1.5

    negative_zero = {
        "value": -0.0,
        "unit": "mol/s",
        "dimension": list(dimension_of("molar_flow")),
        "kind": "molar_flow",
        "meaning": "a dormant component flow",
        "role": "free",
    }
    problems = check_quantity(negative_zero)
    assert any("-0.0" in problem for problem in problems)
    positive_zero = dict(negative_zero, value=0.0)
    assert check_quantity(positive_zero) == ()


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_check_quantity_rejects_nonfinite_values(bad: float) -> None:
    """The runtime check JSON Schema's `type: number` cannot perform (ADR 0001 D1.5)."""
    problems = check_quantity(
        {
            "value": bad,
            "unit": "K",
            "dimension": list(dimension_of("temperature")),
            "kind": "temperature",
            "meaning": "a temperature that was never computed",
            "role": "fixed",
        }
    )
    assert any("finite" in problem for problem in problems)


def test_check_quantity_rejects_a_non_positive_absolute_temperature() -> None:
    problems = check_quantity(
        {
            "value": 0.0,
            "unit": "K",
            "dimension": list(dimension_of("temperature")),
            "kind": "temperature",
            "meaning": "absolute zero, outside the open lower bound",
            "role": "fixed",
        }
    )
    assert any("value > 0.0" in problem for problem in problems)


def test_check_quantity_accepts_a_zero_temperature_difference() -> None:
    """The same number is fine as a difference: the bound belongs to the kind, not the value."""
    assert (
        check_quantity(
            {
                "value": 0.0,
                "unit": "K",
                "dimension": list(dimension_of("temperature_difference")),
                "kind": "temperature_difference",
                "meaning": "no temperature change across a unit",
                "role": "derived",
            }
        )
        == ()
    )


# --------------------------------------------------------------------------------------------
# Round trip
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "path"), ALL_VALID)
def test_valid_fixture_round_trips_through_json(name: str, path: Path) -> None:
    """YAML -> validate -> JSON -> reload -> validate -> deep-equal (plan §2.2)."""
    document = load_yaml(path)
    assert all_problems(name, document) == [], f"{path} did not validate"

    encoded = json.dumps(document, allow_nan=False, sort_keys=True)
    reloaded = json.loads(encoded)

    assert all_problems(name, reloaded) == [], f"{path} did not validate after the round trip"
    assert reloaded == document, f"{path} did not survive the JSON round trip unchanged"

    # And back out through YAML, so neither serialization is privileged.
    assert yaml.safe_load(yaml.safe_dump(reloaded, sort_keys=True)) == document


@pytest.mark.parametrize("record", component_records(), ids=lambda record: str(record["id"]))
def test_component_record_round_trips(record: dict[str, Any]) -> None:
    """The SYN-001 component records are the ComponentRecord fixtures."""
    assert all_problems("component_record", record) == []
    reloaded = json.loads(json.dumps(record, allow_nan=False, sort_keys=True))
    assert all_problems("component_record", reloaded) == []
    assert reloaded == record


@pytest.mark.parametrize(("name", "path"), ALL_INVALID)
def test_invalid_fixture_is_rejected_for_the_stated_reason(name: str, path: Path) -> None:
    """Each deliberately invalid fixture must be rejected, and for the reason it declares."""
    fixture = load_yaml(path)
    assert set(fixture) == {"expect_error", "document"}, (
        f"{path}: an invalid fixture is `expect_error` plus `document`"
    )
    problems = all_problems(name, fixture["document"])
    assert problems, f"{path} was accepted; it must be rejected"
    joined = " | ".join(problems)
    assert fixture["expect_error"] in joined, (
        f"{path} was rejected, but not for the stated reason "
        f"{fixture['expect_error']!r}; got: {joined}"
    )


@pytest.mark.parametrize("name", sorted(P01_SCHEMAS))
def test_every_schema_has_at_least_one_valid_and_one_invalid_fixture(name: str) -> None:
    """Plan §2.2: a schema is delivered with round-trip fixtures, including a rejection."""
    valid = valid_fixtures(name) or (component_records() if name == "component_record" else [])
    assert valid, f"{name} has no valid fixture"
    assert invalid_fixtures(name), f"{name} has no deliberately invalid fixture"


# --------------------------------------------------------------------------------------------
# Cross-document consistency
# --------------------------------------------------------------------------------------------

SYN001_UNIT_MODELS = {
    "syn001.feed_source",
    "syn001.adiabatic_mixer",
    "syn001.tp_heater",
    "syn001.tp_flash",
    "syn001.stream_splitter",
    "syn001.product_sink",
}


def declared_manifests() -> dict[str, dict[str, Any]]:
    manifests = {}
    for path in valid_fixtures("model_manifest"):
        document = load_yaml(path)
        manifests[document["id"]] = document
    return manifests


def test_one_declared_manifest_per_syn001_unit_type() -> None:
    assert set(declared_manifests()) == SYN001_UNIT_MODELS


def test_declared_manifests_claim_nothing_that_is_implemented() -> None:
    """P01 implements no unit model, so every manifest says so in three places."""
    for model_id, manifest in declared_manifests().items():
        assert manifest["status"] == "declared", model_id
        assert manifest["implementation_artifact"]["state"] == "not_implemented", model_id
        assert manifest["implementation_artifact"]["module"] is None, model_id
        assert manifest["implementation_artifact"]["artifact_hash"] is None, model_id
        for entry in manifest["derivatives"]:
            assert entry["method"] == "unavailable", (model_id, entry["output"])


def test_declared_manifests_state_a_validity_domain_and_its_limits() -> None:
    for model_id, manifest in declared_manifests().items():
        domain = manifest["validity"]["domain"]
        assert domain["temperature_K"] == {"min": 280.0, "max": 440.0}, model_id
        assert domain["pressure_Pa"] == {"min": 50000.0, "max": 200000.0}, model_id
        assert domain["components"] == ["A", "B", "C"], model_id
        assert manifest["validity"]["limitations"], (
            f"{model_id} claims no limitations; an empty list is a positive assertion"
        )


def test_material_ports_declare_the_frozen_state_definition() -> None:
    """ADR 0001 D2.1: `nTP-v1` is the default state definition, and it is declared."""
    for model_id, manifest in declared_manifests().items():
        for port in manifest["ports"]:
            if port["kind"] == "material":
                assert port["state_definition"] == "nTP-v1", (model_id, port["name"])
                assert port["component_mapping"] == "revision_component_set", (
                    model_id,
                    port["name"],
                )
            else:
                assert port["state_definition"] is None, (model_id, port["name"])


def case_revisions() -> dict[str, dict[str, Any]]:
    return {path.stem: load_yaml(path) for path in sorted(CASE_DIR.glob("*.yaml"))}


def test_every_case_revision_references_declared_models_and_known_components() -> None:
    known_components = {record["id"] for record in component_records()}
    manifests = declared_manifests()
    for case_id, revision in case_revisions().items():
        assert set(revision["component_set"]["components"]) == known_components, case_id
        assert revision["component_set"]["components"] == ["A", "B", "C"], (
            f"{case_id}: the component-set order fixes the component flow vector order"
        )
        for instance in revision["instances"]:
            assert instance["model"]["id"] in manifests, (case_id, instance["id"])


def test_every_case_revision_omits_the_content_hash() -> None:
    """Canonical hashing is ADR 0002 / K01. A hash written before it exists would be fake."""
    for case_id, revision in case_revisions().items():
        assert "content_hash" not in revision, case_id


def test_case_connections_form_the_derivation_flowsheet() -> None:
    """Streams S1-S7 wired as docs/derivations/SYN-001.md §4 names them."""
    expected = {
        "S1": (("feed", "outlet"), ("mixer", "inlet")),
        "S2": (("mixer", "outlet"), ("heater", "inlet")),
        "S3": (("heater", "outlet"), ("flash", "inlet")),
        "S4": (("flash", "vapor"), ("vapor_product", "inlet")),
        "S5": (("flash", "liquid"), ("splitter", "inlet")),
        "S6": (("splitter", "recycle"), ("mixer", "inlet")),
        "S7": (("splitter", "purge"), ("purge", "inlet")),
    }
    manifests = declared_manifests()
    for case_id, revision in case_revisions().items():
        instances = {instance["id"]: instance for instance in revision["instances"]}
        wiring = {
            connection["id"]: (
                (connection["from"]["instance"], connection["from"]["port"]),
                (connection["to"]["instance"], connection["to"]["port"]),
            )
            for connection in revision["connections"]
        }
        assert wiring == expected, case_id
        for connection in revision["connections"]:
            for endpoint, direction in (
                (connection["from"], "outlet"),
                (connection["to"], "inlet"),
            ):
                instance = instances[endpoint["instance"]]
                ports = manifests[instance["model"]["id"]]["ports"]
                match = [port for port in ports if port["name"] == endpoint["port"]]
                assert match, (case_id, endpoint)
                assert match[0]["direction"] == direction, (case_id, endpoint)


def test_splitter_parameter_and_specification_agree() -> None:
    """The parameter binding and the specification that pins it are one number, checked."""
    for case_id, revision in case_revisions().items():
        splitter = next(i for i in revision["instances"] if i["id"] == "splitter")
        bound = splitter["parameters"]["split_fraction"]["value"]
        specification = next(s for s in revision["specifications"] if s["id"] == "SPEC-splitter-r")
        assert bound == specification["value"], case_id


def test_only_the_conflicting_case_over_specifies_the_heater() -> None:
    """ADR 0001 D4.4: outlet temperature and duty may not both be fixed.

    T02's A02 family frees the heater outlet temperature on purpose (T02 spec §7.3): the heater
    carries neither specification, and its temperature is a `role: free` guess.
    """
    for case_id, revision in case_revisions().items():
        ids = {s["id"] for s in revision["specifications"]}
        if case_id.startswith("SYN-001-A02-"):
            assert "SPEC-heater-outlet-T" not in ids, case_id
            (guess,) = (s for s in revision["specifications"] if s["id"] == "GUESS-heater-outlet-T")
            assert guess["role"] == "free", case_id
        else:
            assert "SPEC-heater-outlet-T" in ids, case_id
        has_duty = "SPEC-heater-duty" in ids
        assert has_duty == (case_id == "SYN-001-conflicting-heater-spec"), case_id


def test_registry_cases_point_at_existing_revisions() -> None:
    registry = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    for case in registry["cases"]:
        revision = case.get("revision")
        if revision is None:
            assert case.get("revision_absent_reason"), case["case_id"]
            continue
        assert (REPO_ROOT / revision).is_file(), case["case_id"]


def test_capped_budget_case_reuses_the_nominal_revision_unchanged() -> None:
    """A budget is a solve-policy choice; it must not change the process being solved."""
    registry = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    cases = {case["case_id"]: case for case in registry["cases"]}
    capped = cases["SYN-001-capped-budget"]
    assert capped["revision"] == cases["SYN-001-nominal"]["revision"]
    assert capped["solve_policy_overrides"] == {"max_property_calls": 20}
    assert capped["expected"]["outcome"] == "typed_failure"
    assert capped["expected"]["code"] == "BUDGET_EXHAUSTED"
    assert capped["expected"]["certificate"] == "none"
    assert capped["expected"]["in_success_denominator"] is False


def test_the_outcome_type_cases_are_outside_the_success_denominator() -> None:
    """Plan §5.1: a case that must fail is never counted as a success, and never removed.

    K03 (register R-014) added a third case outside the denominator that does *not* fail:
    `SYN-001-inadmissible-guess` converges to the nominal answer after a logged initializer
    rejection, and is excluded because its physics duplicates the nominal case (plan §6.1).
    """
    registry = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    outside = {
        case["case_id"]
        for case in registry["cases"]
        if case["expected"]["in_success_denominator"] is False
    }
    assert outside == {
        "SYN-001-conflicting-heater-spec",
        "SYN-001-capped-budget",
        "SYN-001-inadmissible-guess",
        # T03 phase-controller cases (T03 Q3): outside the denominator by class — the two
        # re-registered liquid-guess successes, the new appearance and disappearance cases, the
        # expected failure handed to T04, and the missing-guess refusal.
        "SYN-001-A02-360-liquid-guess",
        "SYN-001-A02-355-liquid-guess",
        "SYN-001-A02-360-vapor-guess",
        "SYN-001-A02-340-two-phase-guess",
        "SYN-001-A02-355-dew-guess",
        "SYN-001-A02-360-no-guess",
        # T02 §7.4: the capability refusal (ADR 0009 D6).
        "CAP-1",
        # T04 §13.1 (Q7): globalization cases, outside the denominator by class — PHS-05 above,
        # re-registered to CONVERGED via edge 3, and the cases and study T04 adds.
        "SYN-001-A02-355-dew-guess-377",
        "SYN-001-A02-352-vapor-guess-410",
        "SYN-001-A02-340-two-phase-guess-capped",
        "SYN-001-A02-360-iteration-capped",
        "SYN-001-nominal-eo-iteration-capped",
        "SYN-001-high-recycle-ptc-basin",
        # T05 §21: the adversarial second-law case (A20), never VERIFIED.
        "SYN-001-UL-C3X",
    }


#: Every `expected.outcome` the registry uses, and the only ones it may. T05 spec §21 adds
#: `typed_failure_or_failed_certificate`: its accepted outcomes are exactly A20's two.
REGISTRY_OUTCOMES = {
    "oracle_values",
    "analytic_values",
    "reference_values",
    "typed_failure",
    "validation_rejection",
    "study",
    "typed_failure_or_failed_certificate",
}


def test_registry_outcomes_are_a_closed_vocabulary() -> None:
    registry = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    used = {case["expected"]["outcome"] for case in registry["cases"]}
    assert used == REGISTRY_OUTCOMES
    for case in registry["cases"]:
        expected = case["expected"]
        if expected["outcome"] == "typed_failure_or_failed_certificate":
            assert expected["in_success_denominator"] is False, case["case_id"]
            assert [entry["outcome"] for entry in expected["accepted"]] == [
                "typed_failure",
                "failed_certificate",
            ], case["case_id"]


#: Every corpus `expected.outcome` (T06 spec §3.1 rule 2, as the twin's `corpus.cases` spells
#: each kind), and the only ones it may. The corpus is counted by its own rule (§3.1 rule 3), so its
#: outcomes are a vocabulary of their own, not `REGISTRY_OUTCOMES`; a control (NET-02 under
#: `T05b-v2`/`T05-W13`, ADV-01's HOM-N) is a `typed_failure` and never counted.
CORPUS_OUTCOMES = {
    "verified_at_reference",
    "converged_to_closed_form",
    "typed_failure",
    "validation",
    "construction_refusal",
    "certificate_unverified_rank",
    "certificate_failed",
    "certificate_relaxed",
    "regularity_inconclusive",
    "regularity_fixtures",
    "structural_finding",
    "multiple_roots",
    "invariant",
    "noise_levels",
}


def test_corpus_outcomes_are_a_closed_vocabulary() -> None:
    registry = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    cases = registry["corpus"]["cases"]
    assert {case["expected"]["outcome"] for case in cases} == CORPUS_OUTCOMES
    for case in cases:
        in_denominator = case["expected"]["outcome"] in (
            "verified_at_reference",
            "converged_to_closed_form",
        )
        assert case["in_success_denominator"] is in_denominator, case["id"]
        for control in case.get("controls", ()):
            assert control["outcome"] == "typed_failure", case["id"]


def test_registry_blueprint_hash_matches_the_ledger() -> None:
    registry = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    ledger = load_yaml(REPO_ROOT / "docs" / "requirements.yaml")
    assert registry["blueprint_sha256"] == ledger["blueprint"]["sha256"]


def test_component_records_carry_the_syn001_constants() -> None:
    """The component records and the oracle constants are the same numbers."""
    from benchmarks.syn001.oracle import SYN001

    for index, record in enumerate(component_records()):
        parameters = record["parameters"]
        assert record["molecular_weight"]["value"] == SYN001.M[index], record["id"]
        assert parameters["reference_boiling_temperature"]["value"] == SYN001.T_b[index]
        assert parameters["vapor_reference_enthalpy_offset"]["value"] == SYN001.L[index]
        assert parameters["heat_capacity"]["value"] == SYN001.c_p[index]
        assert parameters["liquid_molar_volume"]["value"] == SYN001.v[index]


def test_component_records_are_synthetic_with_no_elemental_claim() -> None:
    """Plan §3.1: no real chemical identifiers, elemental verification NOT_APPLICABLE."""
    for record in component_records():
        assert record["synthetic"] is True, record["id"]
        assert "identifiers" not in record, record["id"]
        assert record["elemental_composition"] is None, record["id"]
        assert record["elemental_verification"] == "NOT_APPLICABLE", record["id"]
        assert record["rights"]["redistribution"] == "synthetic; no restrictions", record["id"]
        for name, parameter in record["parameters"].items():
            assert parameter["provenance"] == "plan v1.1 §3.1, synthetic", (record["id"], name)


def test_validation_report_fixtures_declare_that_no_validator_produced_them() -> None:
    """A hand-authored expectation must never read as a verdict some code reached."""
    for path in valid_fixtures("validation_report"):
        report = load_yaml(path)
        produced_by = report["provenance"]["produced_by"]
        assert "no validator" in produced_by, _fixture_id(path)
        assert report["structural_counts"] is None, _fixture_id(path)
        assert report["structural_counts_absent_reason"], _fixture_id(path)


def test_the_conflicting_case_expectation_names_the_conflicting_specifications() -> None:
    report = load_yaml(FIXTURE_DIR / "validation_report" / "valid" / "conflicting-heater-spec.yaml")
    assert report["status"] == "INVALID"
    failures = [check for check in report["checks"] if check["result"] == "FAIL"]
    assert len(failures) == 1
    failure = failures[0]
    assert failure["id"] == "STR-03"
    assert failure["stage"] == "structural_analysis"
    assert failure["evidence_class"] == "structural"
    assert set(failure["implicated_objects"]) == {
        "SPEC-heater-outlet-T",
        "SPEC-heater-duty",
        "heater",
    }
    revision = load_yaml(CASE_DIR / "SYN-001-conflicting-heater-spec.yaml")
    assert report["revision_id"] == revision["revision_id"]
