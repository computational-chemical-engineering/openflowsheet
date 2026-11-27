"""F2-WO4: `ProcessRevision` v2 and `Specification` v2 (ADR 0062 D9 to D11, D13).

- **Schemas.** `process-revision-v2.schema.json` and `specification-v2.schema.json` are draft
  2020-12, registered (`schemas/registry.json`), and admit the valid fixtures under
  `tests/fixtures/schemas/v2/`; each invalid fixture is refused for its stated reason.
- **E-F2-2.** The valid fixtures hold all three connection kinds, all four endpoint kinds, a
  `mat-v1` definition with `mixed` and `solid` substreams, a group basis, a classed attribute on a
  grid, a reaction set and a section: parse -> canonical -> parse is a fixed point, `content_hash`
  is stable under key reordering (and under D3's normalised list orders) and moved by every core
  field change, not by an excluded one.
- **E-F2-9.** One refusal fixture per code of ADR 0062's catalogue table, each refused with exactly
  that code and params (`state_degenerate_in_definition` excepted: it needs a state-point
  evaluation, ADR-F5's, F2 decision WO4-9).
- **E-F2-8.** Q7.A1, A4, A5 and Q8.A1, A6 by their fixtures; Q7.A2 (ṁ bitwise) on the fixtures'
  states; Q8.A2's definition-level part (`mixed_solid_candidates`); Q8.A4 with a stub model.
- **E-F2-6, extended.** Every material connection of the fixtures reads, through the layout, the
  state built independently from its definition (`tests/test_f2_vid_layout.py`'s builder).
"""

from __future__ import annotations

import copy
import json
import random
import struct
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from test_f2_vid_layout import _bits, _expected, _expected_state

from openflowsheet.application.revisions import CONTENT_HASH_EXCLUDED as V1_EXCLUDED
from openflowsheet.application.revisions import content_hash as v1_content_hash
from openflowsheet.material.layout import (
    AttributeKind,
    ComponentFacts,
    LayoutRefusalError,
    MaterialFacts,
    MaterialLayout,
    draft_connection,
)
from openflowsheet.registry.tokens import Coded
from openflowsheet.revision_v2 import (
    CONTENT_HASH_EXCLUDED,
    ModelFacts,
    PortFacts,
    RevisionV2,
    RevisionV2Error,
    ValidationContext,
    canonical_bytes,
    canonical_document,
    content_hash,
    mixed_solid_candidates,
    parse,
    state_refusals,
    validate,
)
from openflowsheet.schema_check import schema_errors

V2 = REPO_ROOT / "tests" / "fixtures" / "schemas" / "v2"
SCHEMAS = ("process-revision-v2.schema.json", "specification-v2.schema.json")
VALID = sorted((V2 / "process_revision" / "valid").glob("*.yaml"))
INVALID = sorted((V2 / "process_revision" / "invalid").glob("*.yaml"))
REFUSALS = sorted((V2 / "refusals").glob("*.yaml"))
#: ADR 0062, "New catalogue codes (ADR 0058 C3)".
CATALOGUE_TABLE = frozenset(
    {
        "solid_role_conflict",
        "species_basis_redundant",
        "species_basis_incompatible",
        "species_basis_not_monotone",
        "group_amount_negative",
        "molar_mass_inconsistent",
        "feed_not_electroneutral",
        "attribute_redundant",
        "attribute_grid_mismatch",
        "attribute_on_zero_parent",
        "amount_basis_mismatch",
        "thermal_coordinate_mismatch",
        "unit_coordinate_unsupported",
        "definition_incompatible",
        "signal_kind_mismatch",
        "parameter_not_manipulable",
        "parameter_binding_conflict",
        "state_degenerate_in_definition",
        "construct_unavailable",
        "quantity_kind_mismatch",
    }
)
#: F2 decision WO4-9: decided at a state point by ADR-F5's service, not by the validator.
NOT_BUILT = frozenset({"state_degenerate_in_definition"})


def _yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@cache
def context() -> ValidationContext:
    found = _yaml(V2 / "context.yaml")
    models = {
        model: ModelFacts(
            {
                name: PortFacts(
                    port["kind"],
                    port["direction"],
                    frozenset(port["definitions"]),
                    port.get("quantity_kind"),
                )
                for name, port in facts["ports"].items()
            },
            facts.get("manipulable", {}),
            facts.get("one_definition", False),
        )
        for model, facts in found["models"].items()
    }
    return ValidationContext(
        {c: ComponentFacts(**facts) for c, facts in found["components"].items()},
        {k: AttributeKind(**facts) for k, facts in found["attribute_kinds"].items()},
        models,
        frozenset(found["providers"]),
        frozenset(found["conventions"]),
        frozenset(found["confined"]),
        frozenset(found["solid_candidates"]),
    )


def _tokens(path: str) -> list[str]:
    return [t.replace("~1", "/").replace("~0", "~") for t in path.split("/")[1:]]


def _apply(document: dict[str, Any], change: Mapping[str, Any]) -> None:
    *parents, last = _tokens(change["path"])
    node: Any = document
    for token in parents:
        node = node[int(token)] if isinstance(node, list) else node[token]
    op, value = change["op"], copy.deepcopy(change.get("value"))
    if isinstance(node, list):
        if op == "add":
            node.insert(len(node) if last == "-" else int(last), value)
        elif op == "replace":
            node[int(last)] = value
        else:
            del node[int(last)]
    elif op == "remove":
        del node[last]
    else:
        assert op == "add" or last in node, change
        node[last] = value


def _patched(fixture: Mapping[str, Any]) -> dict[str, Any]:
    document = _yaml(V2 / "process_revision" / "valid" / f"{fixture['base']}.yaml")
    for change in fixture.get("changes", ()):
        _apply(document, change)
    return document


def _documents(found: tuple[Coded, ...]) -> list[dict[str, Any]]:
    return [c.as_document() for c in found]


def _facts(revision: RevisionV2) -> MaterialFacts:
    known = context().components
    return MaterialFacts(
        revision.components,
        {c: known[c] for c in revision.components},
        context().attribute_kinds,
    )


def _layout(revision: RevisionV2) -> tuple[MaterialLayout, list[str]]:
    facts = _facts(revision)
    ids = [
        draft.variable_id(slot)
        for draft in (draft_connection(g, facts) for g in revision.connection_inputs())
        for slot in draft.slots
    ]
    return MaterialLayout.build(revision.connection_inputs(), facts, ids), ids


# -------------------------------------------------------------------------------- the schemas


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_is_draft_2020_12_registered_and_described(name: str) -> None:
    schema = load_json(REPO_ROOT / "schemas" / name)
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].endswith("/" + name)
    assert len(schema["description"]) > 80
    assert name in load_json(REPO_ROOT / "schemas" / "registry.json")


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_fixture_parses_and_validates_clean(path: Path) -> None:
    revision = parse(path.read_text(encoding="utf-8"))
    assert validate(revision, context()) == ((), ())


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixture_is_refused_for_its_stated_reason(path: Path) -> None:
    fixture = _yaml(path)
    document = _patched(fixture)
    problems = " | ".join(schema_errors(SCHEMAS[0], document))
    assert fixture["expect_error"] in problems
    with pytest.raises(RevisionV2Error) as refused:
        parse(document)
    assert refused.value.coded.code == "schema_invalid"


@pytest.mark.parametrize(
    "path", sorted((V2 / "specification").glob("*/*.yaml")), ids=lambda p: p.parent.name + p.stem
)
def test_specification_v2_fixture(path: Path) -> None:
    found = _yaml(path)
    if path.parent.name == "valid":
        assert schema_errors(SCHEMAS[1], found) == []
        return
    assert found["expect_error"] in " | ".join(schema_errors(SCHEMAS[1], found["document"]))


def test_parse_reads_v2_only_and_refuses_text_outside_json() -> None:
    v1 = _yaml(REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml")
    for source, pointer in (
        (v1, "/schema_version"),
        ("[1, 2]", ""),
        ('{"a": 1, "a": 2}', ""),
        (b"\xff\xfe", ""),
        ({**_yaml(VALID[0]), "x": float("nan")}, "/x"),
    ):
        with pytest.raises(RevisionV2Error) as refused:
            parse(source)
        assert refused.value.coded.as_document() == {
            "code": "schema_invalid",
            "params": {"pointer": pointer},
        }


# ---------------------------------------------------------------------------------- E-F2-2


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_e_f2_2_parse_canonical_parse_is_a_fixed_point(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    first = parse(text)
    once = canonical_bytes(first.document)
    second = parse(once)
    assert canonical_bytes(second.document) == once
    assert second.document == canonical_document(first.document)
    assert canonical_document(second.document) == second.document
    assert parse(json.dumps(first.document)).document == first.document
    assert content_hash(second.document) == content_hash(first.document)


def test_e_f2_2_the_fixtures_cover_every_construct() -> None:
    documents = [parse(p.read_text(encoding="utf-8")).document for p in VALID]
    connections = [c for d in documents for c in d["connections"]]
    assert {c["kind"] for c in connections} == {"material", "energy", "signal"}
    assert {c["definition"] for c in connections} >= {"nTP-v1", "heat-v1", "signal-v1"}
    ends = {
        next(iter(set(c[end]) - {"instance"}), "") for c in connections for end in ("from", "to")
    }
    assert ends == {"port", "probe", "parameter", "specification"}
    definitions = [m for d in documents for m in d["materials"]["definitions"]]
    substreams = [s for m in definitions for s in m["substreams"]]
    assert {s["kind"] for s in substreams} >= {"mixed", "solid"}
    assert any("groups" in s["conserved_basis"] for s in substreams)
    attributes = [a for s in substreams for a in s["attributes"]]
    assert any(a["grid"] is not None for a in attributes)
    assert any(d["reaction_sets"] for d in documents) and any(d["sections"] for d in documents)
    forms = {"variable", "derived", "energy", "signal", "object_type"}
    targets = {(set(s["target"]) & forms).pop() for d in documents for s in d["specifications"]}
    assert targets >= {"variable", "object_type", "energy", "signal"}


def _shuffled(node: Any, rng: random.Random) -> Any:
    if isinstance(node, dict):
        keys = list(node)
        rng.shuffle(keys)
        return {key: _shuffled(node[key], rng) for key in keys}
    if isinstance(node, list):
        return [_shuffled(item, rng) for item in node]
    return node


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_e_f2_2_content_hash_is_stable_under_reordering(path: Path) -> None:
    """Key order (canonical JSON) and D3's normalised orders (groups, attributes) leave the
    content hash and the canonical bytes alone."""
    document = _yaml(path)
    expected = (content_hash(document), canonical_bytes(document))
    rng = random.Random(4062)
    for _ in range(50):
        moved = _shuffled(document, rng)
        for definition in moved["materials"]["definitions"]:
            for substream in definition["substreams"]:
                rng.shuffle(substream["attributes"])
                rng.shuffle(substream["conserved_basis"].get("groups", []))
        assert (content_hash(moved), canonical_bytes(moved)) == expected


#: One change per core field of D11's table (and its members): each moves the hash.
CORE_CHANGES = [
    ("/schema_version", 3),
    ("/convention", "PR-native-v1"),
    ("/component_set/components/0/record", "c" * 64),
    ("/component_set/components/0/id", "W"),
    ("/component_set/parameter_sets", []),
    ("/materials/thermal_coordinate", "T"),
    ("/materials/phase_order_keys", ["Na_p"]),
    ("/materials/definitions/0/id", "brine2"),
    ("/materials/definitions/0/substreams/0/conserved_basis/groups/0/content/Na_p", 2),
    ("/materials/definitions/0/substreams/1/grids/0/edges/1", 0.3),
    ("/materials/definitions/0/substreams/1/attributes/0/version", "1.0.1"),
    ("/materials/definitions/1/substreams/0/components", ["sucrose", "H2O"]),
    ("/reaction_sets/0/reactions/0/stoichiometry/NaCl", [-1, 2]),
    ("/reaction_sets/0/reactions/0/scope", ["liq"]),
    ("/reaction_sets/0/kinetics", {"kind": "x.rate", "version": "1.0.0"}),
    ("/property_methods/default", "pr-c1"),
    ("/instances/3/model/version", "1.0.1"),
    ("/instances/3/semantic_role", "reactor"),
    ("/instances/3/parameters", {"x": 1}),
    ("/instances/3/template", "x"),
    ("/connections/0/definition", "syrup"),
    ("/connections/1/notes", "changed"),
    ("/connections/5/phase_capability", "vapor"),
    ("/connections/5/initialization_hint", {}),
    ("/connections/7/from", {"probe": {"variable": "S5~P"}}),
    ("/specifications/0/value", 11.0),
    ("/specifications/0/target", {"variable": "S1@liq~n[Na]"}),
    ("/sections/x.notes/body", {"text": "another"}),
]


@pytest.mark.parametrize(("pointer", "value"), CORE_CHANGES, ids=[p for p, _ in CORE_CHANGES])
def test_e_f2_2_every_core_field_change_moves_the_content_hash(pointer: str, value: Any) -> None:
    document = _yaml(V2 / "process_revision" / "valid" / "crystallizer.yaml")
    before = content_hash(document)
    _apply(document, {"op": "add", "path": pointer, "value": value})
    assert content_hash(document) != before


@pytest.mark.parametrize("member", sorted(CONTENT_HASH_EXCLUDED))
def test_e_f2_2_an_excluded_field_leaves_the_content_hash(member: str) -> None:
    document = _yaml(V2 / "process_revision" / "valid" / "crystallizer.yaml")
    before = content_hash(document)
    document[member] = {"changed": member}
    assert content_hash(document) == before


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_content_hash_is_v1s_rule_over_the_canonical_document(path: Path) -> None:
    """D11: v1's rule, `CONTENT_HASH_EXCLUDED` unchanged in name and members."""
    assert CONTENT_HASH_EXCLUDED == V1_EXCLUDED
    document = _yaml(path)
    assert content_hash(document) == v1_content_hash(canonical_document(document))


# ---------------------------------------------------------------------------------- E-F2-9


@pytest.mark.parametrize("path", REFUSALS, ids=lambda p: p.stem)
def test_e_f2_9_each_fixture_is_refused_with_exactly_its_code(path: Path) -> None:
    fixture = _yaml(path)
    revision = parse(_patched(fixture))
    errors, notices = validate(revision, context())
    assert _documents(errors) == fixture["errors"]
    assert _documents(notices) == fixture.get("notices", [])
    if "state" not in fixture:
        return
    state = fixture["state"]
    layout, ids = _layout(revision)
    x = [float(state["values"].get(vid, 1.0)) for vid in ids]
    found = state_refusals(revision, context(), layout, x, state["connection"], feed=state["feed"])
    assert _documents(found) == fixture["state_refusals"]
    neutral = [1.0] * len(ids)
    assert (
        state_refusals(revision, context(), layout, neutral, state["connection"], feed=True) == ()
    )


def test_e_f2_9_one_fixture_per_code_of_the_catalogue_table() -> None:
    covered = set()
    for path in REFUSALS:
        fixture = _yaml(path)
        for key in ("errors", "notices", "state_refusals"):
            covered |= {found["code"] for found in fixture.get(key, ())}
    assert covered >= CATALOGUE_TABLE - NOT_BUILT
    assert covered.isdisjoint(NOT_BUILT)


def test_wo3_6_the_layout_refuses_with_the_validators_code() -> None:
    """F2 decision WO3-6, typed: where ADR 0062's table names the reason, the layout's refusal
    carries the code the validator reports for the same definition."""
    cases = {
        "attribute_grid_mismatch": "attribute_grid_mismatch.yaml",
        "attribute_redundant": None,
    }
    grid = parse(_patched(_yaml(V2 / "refusals" / cases["attribute_grid_mismatch"])))
    twice = _yaml(V2 / "process_revision" / "valid" / "crystallizer.yaml")
    partition = {"kind": "probe.partition", "version": "1.0.0", "components": ["sucrose"]}
    twice["materials"]["definitions"][1]["substreams"][1]["attributes"].append(
        {**partition, "grid": "L"}
    )
    for revision in (grid, parse(twice)):
        (error,) = validate(revision, context())[0]
        with pytest.raises(LayoutRefusalError) as refused:
            _layout(revision)
        assert refused.value.coded == error


# ---------------------------------------------------------------------------------- E-F2-8


def _refusal(name: str) -> dict[str, Any]:
    return dict(_yaml(V2 / "refusals" / f"{name}.yaml"))


@pytest.mark.parametrize(
    ("assertion", "fixture", "code"),
    [
        ("Q7.A1", "quantity_kind_mismatch", "quantity_kind_mismatch"),
        ("Q7.A4", "signal_kind_mismatch_specific_enthalpy", "signal_kind_mismatch"),
        ("Q7.A5", "amount_basis_mismatch", "amount_basis_mismatch"),
        ("Q8.A1", "solid_role_conflict", "solid_role_conflict"),
        ("Q8.A6", "solid_role_conflict_equilibrium_phase", "solid_role_conflict"),
    ],
)
def test_e_f2_8_refused_at_validation(assertion: str, fixture: str, code: str) -> None:
    errors, _ = validate(parse(_patched(_refusal(fixture))), context())
    assert [e.code for e in errors] == [code], assertion


def test_e_f2_8_q7_a1_and_q8_a1_admit_their_counterparts() -> None:
    """Q7.A1: a molar specification on a molar amount is admitted (the crystallizer's `f_water`);
    Q8.A1: sucrose dissolved in `mixed` with its crystals in `solid` is admitted (`syrup`)."""
    document = parse((V2 / "process_revision" / "valid" / "crystallizer.yaml").read_text())
    assert validate(document, context()) == ((), ())
    syrup = document.document["materials"]["definitions"][1]
    held = [set(s["components"]) for s in syrup["substreams"]]
    assert held[0] & held[1] == {"sucrose"}


def test_e_f2_8_q8_a2_no_solid_candidate_for_a_solid_substream_component() -> None:
    document = _yaml(V2 / "process_revision" / "valid" / "crystallizer.yaml")
    brine, syrup = document["materials"]["definitions"]
    assert mixed_solid_candidates(syrup, ["sucrose", "H2O", "NaCl"]) == ("H2O",)
    assert mixed_solid_candidates(brine, ["NaCl", "Na_p", "H2O"]) == ("Na_p", "H2O")


def test_e_f2_8_q8_a4_temperature_comes_from_the_flowing_substreams() -> None:
    """Q8.A4 with a stub model per substream, T(ĥ) = ĥ / c_p: `mixed` dormant and `solid`
    flowing takes the solid's T; the reverse takes `mixed`'s; both flowing fix T jointly
    (Q8.R6, F2 review S1), so both are named in instance order; a dormant stream has none."""
    revision = parse((V2 / "process_revision" / "valid" / "crystallizer.yaml").read_text())
    layout, ids = _layout(revision)
    stub = {"liq": lambda h: h / 4180.0, "cryst": lambda h: h / 1250.0}

    def state(liquid: float, solid: float) -> list[float]:
        values = {"S3~h": 418_000.0, "S3~P": 1e5}
        for vid in ids:
            if vid.startswith("S3@liq~n"):
                values[vid] = liquid
            elif vid.startswith("S3@cryst~n"):
                values[vid] = solid
        return [values.get(vid, 0.0) for vid in ids]

    for liquid, solid, expected in ((0.0, 2.0, "cryst"), (3.0, 0.0, "liq")):
        (found,) = layout.thermal_substreams(state(liquid, solid), "S3")
        assert found == expected
        assert stub[found](418_000.0) == {"liq": 100.0, "cryst": 334.4}[found]
    assert layout.thermal_substreams(state(3.0, 2.0), "S3") == ("liq", "cryst")
    assert layout.thermal_substreams(state(0.0, -0.0), "S3") == ()


def _independent_masses(instance: Mapping[str, Any], facts: MaterialFacts) -> list[float]:
    """M per carried amount in D3's order, from the instance and the record masses alone: a
    charged group (one species, coefficient 1, the fixtures' only group basis) has M_g = M_s."""

    def mass(component: str) -> float:
        found = facts.component_facts[component].molar_mass
        return 1.0 if found is None else found

    if instance["template"] == "nTP-v1":
        return [mass(c) for c in facts.components]
    masses: list[float] = []
    for substream in instance["substreams"]:
        basis = substream["conserved_basis"]
        if "groups" in basis:
            for group in sorted(basis["groups"], key=lambda g: g["id"].encode()):
                ((species, units),) = group["content"].items()
                assert units == 1
                masses.append(mass(species))
            continue
        grids = {g["id"]: len(g["edges"]) - 1 for g in substream["grids"]}
        classes = {
            c: grids[a["grid"]]
            for a in substream["attributes"]
            if facts.attribute_kinds[a["kind"]].partition
            for c in a["components"]
        }
        for component in substream["components"]:
            masses += [mass(component)] * classes.get(component, 1)
    return masses


def test_e_f2_8_q7_a2_mass_flow_from_the_layout_is_the_independent_sum() -> None:
    """ṁ = Σ M n in carried order from the layout's masses equals the fixed-order sum over the
    independently built carried ids with each record's mass, one rounding per term, bitwise."""
    rng = random.Random(7202)
    checked = 0
    for path in VALID:
        revision = parse(path.read_text(encoding="utf-8"))
        facts = _facts(revision)
        layout, ids = _layout(revision)
        for _ in range(20):
            x = [rng.uniform(0.0, 50.0) for _ in ids]
            value = dict(zip(ids, x, strict=True))
            for given in revision.connection_inputs():
                placed = layout.connection(given.connection)
                if placed.thermal_coordinate is None:
                    continue
                found = 0.0
                for substream in placed.substreams:
                    for position, mass in zip(
                        substream.carried, substream.molar_masses, strict=True
                    ):
                        found += mass * x[placed.slots[position].variable_index]
                carried = [
                    v
                    for v, _, role in _expected(given.connection, given.instance, facts)
                    if role == "carried"
                ]
                masses = _independent_masses(given.instance, facts)
                expected = 0.0
                for vid, mass in zip(carried, masses, strict=True):
                    expected += mass * value[vid]
                assert struct.pack("<d", found) == struct.pack("<d", expected)
                checked += 1
    assert checked > 100


# --------------------------------------------------------------------------- E-F2-6, extended


@pytest.mark.parametrize(
    "path",
    [
        *VALID,
        V2 / "refusals" / "species_basis_not_monotone.yaml",
        V2 / "refusals" / "molar_mass_inconsistent.yaml",
    ],
    ids=lambda p: p.stem,
)
def test_e_f2_6_the_fixtures_states_read_as_built_from_their_definitions(path: Path) -> None:
    found = _yaml(path)
    document = _patched(found) if "base" in found else found
    revision = parse(document)
    facts = _facts(revision)
    given = revision.connection_inputs(
        {d: f"{i:064x}" for i, d in enumerate(("brine", "syrup", "nTP-v1"))}
    )
    expected = {g.connection: _expected(g.connection, g.instance, facts) for g in given}
    rng = random.Random(6206)
    ids = [v for rows in expected.values() for v, _, _ in rows]
    for _ in range(25):
        rng.shuffle(ids)
        x = [rng.choice([0.0, -0.0, 5e-324, 1.0, rng.uniform(-1e3, 1e3)]) for _ in ids]
        value = dict(zip(ids, x, strict=True))
        layout = MaterialLayout.build(given, facts, ids)
        for item in given:
            rows = expected[item.connection]
            placed = layout.connection(item.connection)
            assert [ids[s.variable_index] for s in placed.slots] == [v for v, _, _ in rows]
            if placed.thermal_coordinate is None:
                continue
            state = layout.state(x, item.connection)
            built = _expected_state(
                item.connection, item.instance, item.definition_sha256, rows, value
            )
            assert state == built and _bits(state) == _bits(built)
