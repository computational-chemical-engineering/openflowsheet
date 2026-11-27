"""F3-WO1: the v2 record model, ADR 0061 exit tests E-F3-3, E-F3-4 and E-F3-13 (synthetic part),
and D7's refusals one by one.

Expectations come from the ADR's rules: the leaf paths are read from the schema by this module's
own walker (not the normaliser's), the anchors from an oracle that transcribes D6, and each D7 row
from the rule it names. The three fixtures under `tests/fixtures/records/` are maximal: together
they reach every leaf of `schemas/record-v2.schema.json` (the `assay` payload is preview and has
none). All three register since ADR 0062 D1 (F2-WO1) registered `molar_entropy` (ADR 0061 risk
6) and `segment_molar_mass` and admitted the `segment_mol` and `kg` bases (risk 4, Q2.A10 (b)).
E-F3-3 is a property of the identity function, so it hashes the normalised projection whether or
not step 6 refuses.
"""

from __future__ import annotations

import copy
import json
import math
import random
import unicodedata
from collections.abc import Iterator
from typing import Any

import pytest
from conftest import REPO_ROOT
from jsonschema import Draft202012Validator

from openflowsheet.records import identify, record_sha256
from openflowsheet.records.normalize import normalize
from openflowsheet.registry import Coded

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "records"
SCHEMA = json.loads((REPO_ROOT / "schemas" / "record-v2.schema.json").read_text(encoding="utf-8"))
MAXIMAL = ("component-maximal", "parameter-set-maximal", "component-segment")


def _fixture(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return document


def _sha(document: Any) -> str:
    """The identity function (D2 steps 1 to 5 and 7), whatever step 6 says."""
    normalized = normalize(copy.deepcopy(document))
    assert normalized.errors == ()
    return record_sha256(normalized.record)


def _codes(found: tuple[Coded, ...]) -> list[tuple[str, dict[str, str]]]:
    return [(item.code, dict(item.params)) for item in found]


# -- the schema's leaves --------------------------------------------------------------------------


def _resolve(node: Any) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {}
    if "$ref" in node:
        target: Any = SCHEMA
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return {**{k: v for k, v in node.items() if k != "$ref"}, **_resolve(target)}
    return node


def _parts(node: Any) -> Iterator[dict[str, Any]]:
    """The node and every subschema that can apply to the same instance (all branches)."""
    node = _resolve(node)
    yield node
    for name in ("allOf", "anyOf", "oneOf"):
        for part in node.get(name, ()):
            yield from _parts(part)
    for name in ("then", "else"):
        if name in node:
            yield from _parts(node[name])


def _children(node: Any) -> dict[str, list[Any]]:
    """Child path segments (`*` for a map key or an array index) and their schemas."""
    found: dict[str, list[Any]] = {}
    for part in _parts(node):
        for key, child in part.get("properties", {}).items():
            found.setdefault(key, []).append(child)
        if isinstance(part.get("additionalProperties"), dict):
            found.setdefault("*", []).append(part["additionalProperties"])
        for index, child in enumerate(part.get("prefixItems", ())):
            found.setdefault(str(index), []).append(child)
        if isinstance(part.get("items"), dict):
            found.setdefault("*", []).append(part["items"])
    return found


def _enums(node: Any) -> list[Any]:
    return [value for part in _parts(node) for value in part.get("enum", ())]


def schema_leaves(node: Any = SCHEMA, at: tuple[str, ...] = ()) -> dict[tuple[str, ...], list[Any]]:
    """Every leaf path pattern of the schema (a node with no member, item or element schema: a
    scalar or a free object) and the enum values declared there."""
    children = _children(node)
    if not children:
        return {at: _enums(node)}
    leaves: dict[tuple[str, ...], list[Any]] = {}
    for key, schemas in children.items():
        for child in schemas:
            for path, enums in schema_leaves(child, (*at, key)).items():
                leaves.setdefault(path, []).extend(enums)
    return leaves


LEAVES = schema_leaves()


def pattern_leaves(node: Any = SCHEMA, at: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    """The leaf path patterns of the schema at which a subschema declares a `pattern`."""
    children = _children(node)
    if not children:
        return {at} if any("pattern" in part for part in _parts(node)) else set()
    return {
        path
        for key, schemas in children.items()
        for child in schemas
        for path in pattern_leaves(child, (*at, key))
    }


PATTERNED = pattern_leaves()


def document_leaves(node: Any, at: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    """Every leaf of a document (a scalar, or an empty array or object) and its path."""
    if isinstance(node, dict) and node:
        for key, value in node.items():
            yield from document_leaves(value, (*at, key))
    elif isinstance(node, list) and node:
        for index, value in enumerate(node):
            yield from document_leaves(value, (*at, str(index)))
    else:
        yield at, node


def _pattern_of(path: tuple[str, ...]) -> tuple[str, ...] | None:
    """The schema leaf pattern a document leaf falls under (a free object's members fall under
    the object), or `None`."""
    for length in range(len(path), 0, -1):
        for pattern in LEAVES:
            if len(pattern) == length and all(
                p in ("*", s) for p, s in zip(pattern, path, strict=False)
            ):
                return pattern
    return None


def _mutated(value: Any, enums: list[Any]) -> Any:
    """One change of a leaf: `null` made 0, a boolean flipped, an integer + 1, a float by one ulp,
    another enum value, else a character appended."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return math.nextafter(value, math.inf)
    others = [item for item in enums if item != value]
    return others[0] if others else value + "x"


def _set(document: dict[str, Any], path: tuple[str, ...], value: Any) -> dict[str, Any]:
    changed = copy.deepcopy(document)
    node: Any = changed
    for part in path[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    if isinstance(node, list):
        node[int(path[-1])] = value
    else:
        node[path[-1]] = value
    return changed


# -- E-F3-3 ---------------------------------------------------------------------------------------


def test_e_f3_3_the_fixtures_reach_every_leaf_of_the_schema() -> None:
    """Every leaf pattern of the schema is a leaf (or inside a free-object leaf) of a fixture."""
    reached = {_pattern_of(path) for name in MAXIMAL for path, _ in document_leaves(_fixture(name))}
    assert None not in reached
    assert set(LEAVES) - reached == set()
    assert ("volatile", "request", "query", "*", "1") in LEAVES  # the walker reads prefixItems


def test_e_f3_3_the_fixtures_register_since_adr_0062_d1() -> None:
    """F2-WO1 flips this test: the component fixture's entropies have their kind (risk 6), and the
    segment record its basis and `segment_molar_mass` (risk 4); before, the component was refused
    `record_unit_invalid` at its three `s` Constants and the segment record
    `amount_basis_unsupported(segment_mol)`. The segment record, on a basis other than `mol` with
    nothing phase-tagged, has no anchor (D6 step 4 is `mol` only)."""
    for name in ("parameter-set-maximal", "component-maximal", "component-segment"):
        outcome = identify(_fixture(name))
        assert outcome.errors == (), name
        assert outcome.record_sha256 == _sha(_fixture(name)), name
    assert identify(_fixture("parameter-set-maximal")).findings == ()
    assert identify(_fixture("component-maximal")).findings == ()
    segment = identify(_fixture("component-segment"))
    undetermined = ("anchor_undetermined", {"component": segment.record["id"]})
    assert _codes(segment.findings) == [undetermined]
    assert segment.record["anchor_phase"] is None


@pytest.mark.parametrize("name", MAXIMAL)
def test_e_f3_3_volatile_closure(name: str) -> None:
    """Q9.A1 [gen]: a change to any `/volatile/...` leaf leaves the SHA; a change to any other
    leaf (one ulp, a character, an enum value, an origin, a validity bound, a source version,
    `licence_stated`) changes it. Limits (review S5): the leaves are values, not map keys; leaf
    patterns merge across record types; and the SHA is `normalize` plus `record_sha256`, since
    two fixtures are refused by design."""
    document = _fixture(name)
    base = _sha(document)
    changed = unchanged = 0
    for path, value in document_leaves(document):
        pattern = _pattern_of(path)
        assert pattern is not None, path
        mutated = _sha(_set(document, path, _mutated(value, LEAVES[pattern])))
        if path[0] == "volatile":
            assert mutated == base, path
            unchanged += 1
        else:
            assert mutated != base, path
            changed += 1
    assert changed > 0
    assert unchanged == {"component-maximal": 17, "parameter-set-maximal": 2}.get(name, 0)


# -- E-F3-4 ---------------------------------------------------------------------------------------


def _shuffled(node: Any, rng: random.Random) -> Any:
    """Every object's member order permuted, recursively; arrays keep their order."""
    if isinstance(node, dict):
        keys = list(node)
        rng.shuffle(keys)
        return {key: _shuffled(node[key], rng) for key in keys}
    if isinstance(node, list):
        return [_shuffled(item, rng) for item in node]
    return node


def _nfd(node: Any) -> Any:
    if isinstance(node, str):
        return unicodedata.normalize("NFD", node)
    if isinstance(node, dict):
        return {unicodedata.normalize("NFD", key): _nfd(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_nfd(item) for item in node]
    return node


#: D2 step 4: the set-valued arrays of the fixtures, each with at least two elements.
SET_ARRAYS = {
    "component-maximal": [
        ("synonyms",),
        ("entries",),
        ("molar_mass", "provenance", "inputs"),
        ("formation", "0", "h", "provenance", "origin"),
        ("entries", "3", "provenance", "origin"),
    ],
    "parameter-set-maximal": [("components",), ("entries",)],
}


def _get(document: Any, path: tuple[str, ...]) -> Any:
    for part in path:
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


@pytest.mark.parametrize("name", sorted(SET_ARRAYS))
def test_e_f3_4_order_signed_zero_sets_and_nfc_give_one_sha(name: str) -> None:
    """Q9.A3: field-order permutations, permutations of every set-valued array, and NFD against
    NFC strings give one SHA."""
    document = _fixture(name)
    base = _sha(document)
    rng = random.Random(20261118)
    for _ in range(5):
        assert _sha(_shuffled(document, rng)) == base
    for path in SET_ARRAYS[name]:
        elements = _get(document, path)
        assert len(elements) >= 2, path
        assert _sha(_set(document, path, list(reversed(elements)))) == base, path
    assert _sha(_set(document, ("name",), document["name"] + " é")) == _sha(
        _nfd(_set(document, ("name",), document["name"] + " é"))
    )


def test_e_f3_4_negative_zero_is_zero() -> None:
    document = _fixture("component-maximal")
    coefficients = ("entries", "1", "coefficients", "b4")
    assert _sha(_set(document, coefficients, -0.0)) == _sha(_set(document, coefficients, 0.0))
    assert _sha(_set(document, coefficients, -0.0)) != _sha(document)


#: D2 step 2a: optional members, by container path (all optional in the schema).
OPTIONAL_MEMBERS = [
    ((), "synonyms"),
    ((), "identifiers"),
    ((), "formation"),
    ((), "transitions"),
    ((), "entries"),
    ((), "uncertainty_statement"),
    ((), "elements"),
    (("molar_mass",), "uncertainty"),
    (("molar_mass",), "meaning"),
    (("molar_mass",), "note"),
    (("molar_mass", "provenance"), "inputs"),
    (("molar_mass", "provenance"), "transformation"),
    (("sources", "s"), "licence_stated"),
]


def _minimal() -> dict[str, Any]:
    """A valid component with only its required members."""
    return {
        "record_format": "openflowsheet-record-v2",
        "record_type": "component",
        "type_version": "1.0.0",
        "id": "M",
        "name": "minimal",
        "sources": {"s": {"version": "1"}},
        "synthetic": True,
        "amount_basis": "mol",
        "charge": 0,
        "elemental_verification": "NOT_APPLICABLE",
        "molar_mass": {
            "value": 0.05,
            "unit": "kg/mol",
            "kind": "molar_mass",
            "provenance": {"origin": ["synthetic"], "derivation": "direct", "source": "s"},
        },
    }


@pytest.mark.parametrize(("container", "member"), OPTIONAL_MEMBERS)
@pytest.mark.parametrize("empty", [None, [], {}])
def test_e_f3_4_absent_null_and_empty_optional_members_give_one_sha(
    container: tuple[str, ...], member: str, empty: Any
) -> None:
    """D2 step 2a (review finding 4): absent, `null`, `[]` and `{}` give one SHA, and the record
    is accepted either way."""
    base = identify(_minimal())
    assert base.errors == () and base.record_sha256 is not None
    document = _minimal()
    _get(document, container)[member] = empty
    outcome = identify(document)
    assert outcome.errors == ()
    assert outcome.record_sha256 == base.record_sha256


@pytest.mark.parametrize("member", ["position", "file_fields"])
def test_e_f3_4_legacy_position_and_file_fields_have_one_empty_spelling(member: str) -> None:
    """Review M4: `legacy.position` and `legacy.file_fields` are optional, so absent, `null` and
    `{}` give one SHA (D1 does not make them required)."""
    document = _fixture("component-maximal")
    del document["legacy"][member]
    spellings = {_sha(_set(document, ("legacy", member), empty)) for empty in (None, {}, [])}
    assert spellings == {_sha(document)}


def _validator(schema: Any) -> Draft202012Validator:
    """A validator of a subschema of the record schema (its `$ref`s are local `$defs`)."""
    return Draft202012Validator({**schema, "$defs": SCHEMA["$defs"]})


def _applying(schema: Any, instance: Any) -> Iterator[dict[str, Any]]:
    """The test's own applicability (not the normaliser's): the schema, its `$ref` target, its
    `allOf` parts, the `if` branch the instance selects, and the `anyOf`/`oneOf` branches it is
    valid against. `not` describes no member."""
    node = _resolve(schema)
    yield node
    for part in node.get("allOf", ()):
        yield from _applying(part, instance)
    if "if" in node:
        branch = "then" if _validator(node["if"]).is_valid(instance) else "else"
        yield from _applying(node.get(branch, {}), instance)
    for part in (*node.get("anyOf", ()), *node.get("oneOf", ())):
        if _validator(part).is_valid(instance):
            yield from _applying(part, instance)


def member_slots(
    document: Any, schema: Any = SCHEMA, at: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], str, list[Any], bool]]:
    """Every (object path, member name, member schemas, required) the schema names at an object
    of `document`, whether the member is present or not, walking the document's own members."""
    parts = list(_applying(schema, document))
    if isinstance(document, dict):
        required = {name for part in parts for name in part.get("required", ())}
        named: dict[str, list[Any]] = {}
        for part in parts:
            for name, member in part.get("properties", {}).items():
                named.setdefault(name, []).append(member)
        for name, members in named.items():
            yield at, name, members, name in required
        other = [
            part["additionalProperties"]
            for part in parts
            if isinstance(part.get("additionalProperties"), dict)
        ]
        for key, value in document.items():
            for member in named.get(key, other):
                yield from member_slots(value, member, (*at, key))
    elif isinstance(document, list):
        for index, value in enumerate(document):
            for part in parts:
                prefix = part.get("prefixItems", [])
                item = prefix[index] if index < len(prefix) else part.get("items")
                if isinstance(item, dict):
                    yield from member_slots(value, item, (*at, str(index)))


def _slot_pattern(at: tuple[str, ...], name: str) -> tuple[str, ...]:
    return (*("*" if part.isdigit() else part for part in at), name)


SLOT_DOCUMENTS = ("minimal", *MAXIMAL)


def _slot_document(name: str) -> dict[str, Any]:
    return _minimal() if name == "minimal" else _fixture(name)


@pytest.mark.parametrize("name", SLOT_DOCUMENTS)
def test_e_f3_4_every_optional_member_has_one_empty_spelling(name: str) -> None:
    """D2 step 2a, review S5: every optional member the schema names at an object of the
    fixture (derived from the schema, not a hand list) gives one SHA absent, `null`, `[]` and
    `{}`, once per (path pattern, member)."""
    document = _slot_document(name)
    seen: set[tuple[str, ...]] = set()
    for at, member, _, required in member_slots(document):
        pattern = _slot_pattern(at, member)
        if required or pattern in seen or at[:1] == ("volatile",):
            continue
        seen.add(pattern)
        absent = copy.deepcopy(document)
        _get(absent, at).pop(member, None)
        spellings = {_sha(_set(absent, (*at, member), empty)) for empty in (None, [], {})}
        assert spellings == {_sha(absent)}, pattern
    assert len(seen) > {"minimal": 10, "parameter-set-maximal": 20}.get(name, 30)


@pytest.mark.parametrize("name", SLOT_DOCUMENTS)
def test_e_f3_4_no_required_member_has_two_empty_spellings(name: str) -> None:
    """Review S5 (it would have caught M4): a required member keeps its value at step 2a, so
    its schema admits at most one of `null`, `[]` and `{}`."""
    checked = 0
    for at, member, schemas, required in member_slots(_slot_document(name)):
        if required:
            admitted = [
                empty
                for empty in (None, [], {})
                if all(_validator(schema).is_valid(empty) for schema in schemas)
            ]
            assert len(admitted) <= 1, (at, member, admitted)
            checked += 1
    assert checked > 0


#: The keywords `normalize._applicable` and step 2a interpret, and those that only assert or
#: annotate. A keyword outside both (`patternProperties`, `dependentRequired`, ...) would change
#: what step 2a strips, so SHAs, without failing a test: it must be classified here first.
STEP_2A_KEYWORDS = frozenset(
    {
        "$ref", "allOf", "if", "then", "else", "anyOf", "oneOf",
        "properties", "additionalProperties", "prefixItems", "items", "required",
    }
)  # fmt: skip
ASSERTION_KEYWORDS = frozenset(
    {
        "$defs", "$id", "$schema", "title", "description", "type", "enum", "const", "pattern",
        "minLength", "maxLength", "minimum", "exclusiveMinimum", "minItems", "minProperties",
        "maxProperties", "propertyNames", "unevaluatedProperties", "not",
    }
)  # fmt: skip


def _keywords(node: Any) -> set[str]:
    """Every keyword of every subschema of `node`, through every applicator."""
    if not isinstance(node, dict):
        return set()
    found = set(node)
    for name in ("properties", "$defs"):
        for child in node.get(name, {}).values():
            found |= _keywords(child)
    for name in ("additionalProperties", "items", "if", "then", "else", "not", "propertyNames"):
        found |= _keywords(node.get(name))
    for name in ("allOf", "anyOf", "oneOf", "prefixItems"):
        for child in node.get(name, ()):
            found |= _keywords(child)
    return found


def test_d2_step_2a_reads_a_closed_keyword_set() -> None:
    """Review S5: the record schema uses no keyword step 2a does not classify."""
    assert _keywords(SCHEMA) <= STEP_2A_KEYWORDS | ASSERTION_KEYWORDS
    assert "if" in _keywords(SCHEMA)


def test_e_f3_4_permuting_transitions_gives_one_sha() -> None:
    """E-F3-4 on `transitions` (review S5: the fixture has one, so it is never permuted)."""
    document = _fixture("component-maximal")
    second = copy.deepcopy(document["transitions"][0])
    second["from"], second["to"] = "s:I", "l"
    document["transitions"].append(second)
    permuted = _set(document, ("transitions",), list(reversed(document["transitions"])))
    assert _sha(permuted) == _sha(document)


def test_e_f3_4_a_required_empty_member_is_kept() -> None:
    """Required members keep their values: an empty `origin` stays and is `provenance_invalid`
    (D7), not a missing member."""
    document = _minimal()
    document["molar_mass"]["provenance"]["origin"] = []
    assert _codes(identify(document).errors) == [("provenance_invalid", {"entry": "/molar_mass"})]


@pytest.mark.parametrize(
    ("base", "changes", "at"),
    [
        ("water", {("elements", "H"): None}, "/elements/H"),
        ("water", {("entries", "1", "validity", "T"): []}, "/entries/1/validity/T"),
        ("minimal", {("colour",): None}, ""),
        ("minimal", {("sources", "ghost"): None}, "/sources/ghost"),
    ],
)
def test_e_f3_4_step_2a_keeps_map_entries_and_undescribed_members(
    base: str, changes: dict[tuple[str, ...], Any], at: str
) -> None:
    """Review M3: step 2a removes only members the schema names and does not require; an empty
    map entry or an undescribed member stays and step 6 refuses it, never another content's
    SHA."""
    outcome = identify(_with(changes, _water() if base == "water" else None))
    assert _codes(outcome.errors) == [("record_schema_invalid", {"pointer": at})]
    assert outcome.record_sha256 is None


def test_e_f3_4_permuting_two_solid_forms_changes_the_sha_and_the_anchor() -> None:
    """`formation` is sorted by phase class stably (D2 step 4): two solid forms keep record order,
    so permuting them is a different record with a different anchor (D6 step 2)."""
    document = _minimal()
    document["formation"] = [_formation("s:beta"), _formation("s:alpha")]
    permuted = _set(document, ("formation",), list(reversed(document["formation"])))
    first, second = identify(document), identify(permuted)
    assert (first.errors, second.errors) == ((), ())
    assert first.record["anchor_phase"] == "s:beta"
    assert second.record["anchor_phase"] == "s:alpha"
    assert first.record_sha256 != second.record_sha256


def _formation(phase: str) -> dict[str, Any]:
    return {
        "phase": phase,
        "h": {
            "value": -1000.0,
            "unit": "J/mol",
            "kind": "molar_enthalpy",
            "provenance": {"origin": ["synthetic"], "derivation": "direct", "source": "s"},
        },
    }


#: (h kind, unit), (s kind, unit) per amount basis: ADR 0062 D1's kinds (F2 decision WO1-9).
BASIS_FORMATION_KINDS = {
    "mol": (("molar_enthalpy", "J/mol"), ("molar_entropy", "J/(mol K)")),
    "segment_mol": (("segment_molar_enthalpy", "J/mol"), ("segment_molar_entropy", "J/(mol K)")),
    "kg": (("specific_enthalpy", "J/kg"), ("specific_entropy", "J/(kg K)")),
}


@pytest.mark.parametrize("basis", BASIS_FORMATION_KINDS)
def test_d7_formation_kinds_follow_the_amount_basis(basis: str) -> None:
    """D3: Δf h° and s° are per unit amount, so of the basis's kind; the kinds of another basis
    are `record_unit_invalid` at `h` and at `s` (F2-WO1, decision WO1-9)."""
    for other, ((h_kind, h_unit), (s_kind, s_unit)) in BASIS_FORMATION_KINDS.items():
        document = _anchor_record(0, basis, ["ig"], [])
        if basis == "segment_mol":
            document["molar_mass"]["kind"] = "segment_molar_mass"
        formation = document["formation"][0]
        formation["h"].update(kind=h_kind, unit=h_unit)
        formation["s"] = {**formation["h"], "value": 100.0, "kind": s_kind, "unit": s_unit}
        outcome = identify(document)
        refused = [("record_unit_invalid", {"entry": f"/formation/0/{p}"}) for p in ("h", "s")]
        assert _codes(outcome.errors) == ([] if other == basis else refused), (basis, other)


# -- E-F3-13 (synthetic part) ---------------------------------------------------------------------


def _anchor_record(
    charge: int,
    basis: str,
    formation: list[str],
    tagged: list[str],
    stated: str | None = None,
    names: list[str] | None = None,
) -> dict[str, Any]:
    """A component with formation in `formation` and one entry tagged with each of `tagged`,
    named by `names` (default `user.p0`, `user.p1`, ... in list order)."""
    document = _minimal()
    document["charge"] = charge
    document["amount_basis"] = basis
    if basis == "kg":
        del document["molar_mass"]
    document["formation"] = [_formation(phase) for phase in formation]
    document["entries"] = [
        {
            "property": f"user.p{index}" if names is None else names[index],
            "phase": phase,
            "form": "constant",
            "value": 1.0,
            "unit": "1",
            "kind": "dimensionless",
            "provenance": {"origin": ["synthetic"], "derivation": "direct", "source": "s"},
        }
        for index, phase in enumerate(tagged)
    ]
    if stated is not None:
        document["anchor_phase"] = stated
    return document


def _oracle(
    charge: int, basis: str, formation: list[str], tagged: list[str]
) -> tuple[str | None, str | None]:
    """D6 transcribed: (anchor, notice code). Order: `ig`, `aq`, `l`, then `s:` forms; the
    formation's solid forms in record order; of the entries' solid forms the smallest token
    (review S4; for these ASCII tokens `str` order is canonical-JSON byte order), whatever the
    entries' order or property names."""
    if charge != 0:
        return "aq", None
    for phases in (formation, tagged):
        for wanted in ("ig", "aq", "l"):
            if wanted in phases:
                return wanted, None
        solids = [phase for phase in phases if phase.startswith("s:")]
        if solids:
            return (solids[0] if phases is formation else min(solids)), None
    if basis == "mol":
        return "ig", "anchor_defaulted"
    return None, "anchor_undetermined"


ANCHOR_CASES = [
    ("charged", -1, "mol", [], [], "aq"),
    ("formation in l only", 0, "mol", ["l"], [], "l"),
    ("formation in ig and l", 0, "mol", ["l", "ig"], [], "ig"),
    ("two solid forms", 0, "mol", ["s:II", "s:I"], [], "s:II"),
    ("a phase-tagged entry", 0, "mol", [], ["aq"], "aq"),
    ("two tagged solid forms", 0, "mol", [], ["s:beta", "s:alpha"], "s:alpha"),
    ("nothing phase-tagged, mol", 0, "mol", [], [], "ig"),
    ("nothing phase-tagged, kg", 0, "kg", [], [], None),
]


@pytest.mark.parametrize(
    ("charge", "basis", "formation", "tagged", "anchor"),
    [case[1:] for case in ANCHOR_CASES],
    ids=[case[0] for case in ANCHOR_CASES],
)
def test_e_f3_13_anchor_derivation(
    charge: int, basis: str, formation: list[str], tagged: list[str], anchor: str | None
) -> None:
    outcome = identify(_anchor_record(charge, basis, formation, tagged))
    assert outcome.record["anchor_phase"] == anchor
    assert _oracle(charge, basis, formation, tagged)[0] == anchor


def test_e_f3_13_tagged_solid_forms_anchor_on_the_smallest_token() -> None:
    """Review S4: with entries tagged `s:alpha` and `s:beta`, one more entry on `s:beta` whose
    property sorts first does not re-anchor: the anchor is a function of the set of phases."""
    two = identify(_anchor_record(0, "mol", [], ["s:alpha", "s:beta"]))
    three = identify(
        _anchor_record(
            0, "mol", [], ["s:alpha", "s:beta", "s:beta"], names=["user.p0", "user.p1", "user.aa"]
        )
    )
    assert two.record["anchor_phase"] == three.record["anchor_phase"] == "s:alpha"
    assert two.errors == three.errors == ()


def test_e_f3_13_a_defaulted_ig_is_the_record_that_states_ig() -> None:
    """Q2.R9: `mol` with nothing phase-tagged takes `ig` with `anchor_defaulted`; the same record
    stating `ig` has the same SHA and no notice."""
    defaulted = identify(_anchor_record(0, "mol", [], []))
    stated = identify(_anchor_record(0, "mol", [], [], stated="ig"))
    assert _codes(defaulted.findings) == [("anchor_defaulted", {"component": "M"})]
    assert stated.findings == ()
    assert defaulted.errors == stated.errors == ()
    assert defaulted.record_sha256 == stated.record_sha256 is not None


def test_e_f3_13_kg_has_no_anchor_and_registers_since_adr_f2() -> None:
    """E-F3-13 and Q2.A10 (b), the `kg` branch: D6 gives `null` and `anchor_undetermined`; since
    ADR 0062 D1 (F2-WO1) the record registers (before, `amount_basis_unsupported(kg)`)."""
    outcome = identify(_anchor_record(0, "kg", [], []))
    assert outcome.record["anchor_phase"] is None
    assert _codes(outcome.findings) == [("anchor_undetermined", {"component": "M"})]
    assert outcome.errors == ()
    assert outcome.record_sha256 == _sha(_anchor_record(0, "kg", [], []))
    _assert_idempotent(outcome)


@pytest.mark.parametrize(
    ("charge", "formation", "stated"),
    [(0, ["ig"], "l"), (0, ["s:I", "l"], "s:II"), (1, [], "ig"), (-2, ["aq"], "l")],
)
def test_e_f3_13_a_stated_anchor_the_rules_refuse(
    charge: int, formation: list[str], stated: str
) -> None:
    """D6: a stated anchor without formation there while formation exists elsewhere, or a charged
    component's anchor other than `aq`, is `anchor_phase_invalid`."""
    outcome = identify(_anchor_record(charge, "mol", formation, [], stated=stated))
    assert ("anchor_phase_invalid", {"component": "M", "phase": stated}) in _codes(outcome.errors)


def _assert_idempotent(outcome: Any) -> None:
    """Review M1: the normalised record of an accepted record is accepted, with the same SHA and
    anchor (validity is a function of the normalised record)."""
    again = identify(outcome.record)
    assert again.errors == (), again.errors
    assert again.record_sha256 == outcome.record_sha256
    assert again.record.get("anchor_phase") == outcome.record.get("anchor_phase")


def test_e_f3_13_a_derived_anchor_obeys_the_stated_anchor_rule() -> None:
    """Review M1: `charge` 1 with formation in `ig` only derives `aq` (D6 step 1), which has no
    formation entry: refused at first submission, as the same record stating `aq` is."""
    derived = identify(_anchor_record(1, "mol", ["ig"], []))
    stated = identify(_anchor_record(1, "mol", ["ig"], [], stated="aq"))
    invalid = [("anchor_phase_invalid", {"component": "M", "phase": "aq"})]
    assert _codes(derived.errors) == _codes(stated.errors) == invalid
    assert derived.record_sha256 is None


@pytest.mark.parametrize("name", ["water", "minimal", "parameter-set-maximal"])
def test_d2_an_accepted_record_s_normal_form_is_accepted_with_its_sha(name: str) -> None:
    document = {"water": _water, "minimal": _minimal}.get(name, lambda: _fixture(name))()
    outcome = identify(document)
    assert outcome.errors == ()
    _assert_idempotent(outcome)


def test_e_f3_13_generated_anchors_follow_d6() -> None:
    """[gen] 300 random records (charge, basis, formation phases and entry phase tags in random
    order, entries under shuffled property names, review S5) against the D6 oracle: anchor,
    notice, and D6's anchor rule on the derived anchor (review M1: a charged component with
    formation data and none in `aq` is refused). Every accepted record's normal form is
    accepted with the same SHA and anchor."""
    rng = random.Random(61)
    pool = ["ig", "aq", "l", "s:I", "s:II", "s:III"]
    accepted = 0
    for _ in range(300):
        charge = rng.choice([0, 0, 0, 1, -1])
        basis = rng.choice(["mol", "mol", "kg", "segment_mol"])
        formation = rng.sample(pool, rng.randint(0, 3))
        tagged = rng.sample(pool, rng.randint(0, 3))
        names = [f"user.p{index}" for index in rng.sample(range(10), len(tagged))]
        document = _anchor_record(charge, basis, formation, tagged, names=names)
        outcome = identify(document)
        if charge == 0 and not formation:  # step 3 or later: entries are a set (E-F3-4)
            permuted = _set(document, ("entries",), list(reversed(document["entries"])))
            assert identify(permuted).record == outcome.record
        anchor, notice = _oracle(charge, basis, formation, tagged)
        assert outcome.record["anchor_phase"] == anchor, (charge, basis, formation, tagged)
        anchor_notices = [
            code for code, _ in _codes(outcome.findings) if code.startswith("anchor_")
        ]
        assert anchor_notices == ([] if notice is None else [notice])
        refused = charge != 0 and bool(formation) and "aq" not in formation
        invalid = ("anchor_phase_invalid", {"component": "M", "phase": "aq"})
        assert (invalid in _codes(outcome.errors)) == refused
        if outcome.record_sha256 is not None:
            accepted += 1
            _assert_idempotent(outcome)
    assert accepted >= 50


# -- D7, rule by rule -----------------------------------------------------------------------------


def _with(
    changes: dict[tuple[str, ...], Any], base: dict[str, Any] | None = None
) -> dict[str, Any]:
    document = copy.deepcopy(base) if base is not None else _minimal()
    for path, value in changes.items():
        document = _set(document, path, value)
    return document


def _water() -> dict[str, Any]:
    """The component fixture without its entropies: a valid, maximal component."""
    document = _fixture("component-maximal")
    for item in (*document["formation"], *document["transitions"]):
        del item["s"]
    return document


def test_the_water_record_is_valid() -> None:
    outcome = identify(_water())
    assert (outcome.errors, outcome.findings) == ((), ())
    assert outcome.volatile is not None and outcome.volatile["host"] == "fixture-host"
    assert "volatile" not in outcome.record


D7_ROWS: list[tuple[str, dict[tuple[str, ...], Any], tuple[str, dict[str, str]]]] = [
    ("unknown member", {("colour",): "blue"}, ("record_schema_invalid", {"pointer": ""})),
    (
        "volatile outside the set",
        {("volatile",): {"cookie": "x"}},
        ("record_schema_invalid", {"pointer": "/volatile"}),
    ),
    (
        "bad element",
        {("elements",): {"Xx": 1}},
        ("record_schema_invalid", {"pointer": "/elements"}),
    ),
    ("unit", {("entries", "0", "unit"): "degC"}, ("record_unit_invalid", {"entry": "/entries/0"})),
    (
        "core kind",
        {("entries", "0", "kind"): "pressure", ("entries", "0", "unit"): "Pa"},
        ("record_unit_invalid", {"entry": "/entries/0"}),
    ),
    (
        "molar mass absent",
        {("molar_mass",): None},
        ("amount_basis_invalid", {"component": "fixture.water", "rule": "molar_mass_absent"}),
    ),
    (
        "molar mass kind",
        {("molar_mass", "kind"): "molar_volume", ("molar_mass", "unit"): "m3/mol"},
        ("amount_basis_invalid", {"component": "fixture.water", "rule": "molar_mass_kind"}),
    ),
    (
        "CAS check digit",
        {("identifiers", "cas"): "7732-18-6"},
        ("identifier_invalid", {"component": "fixture.water", "scheme": "cas"}),
    ),
    (
        "InChIKey",
        {("identifiers", "inchikey"): "XLYOFNOQVPJJNP-UHFFFAOYSA"},
        ("identifier_invalid", {"component": "fixture.water", "scheme": "inchikey"}),
    ),
    (
        "synthetic with identifiers",
        {("synthetic",): True},
        ("identifier_invalid", {"component": "fixture.water", "scheme": "smiles"}),
    ),
    (
        "formula",
        {("identifiers", "formula"): "H2O2"},
        ("formula_elements_invalid", {"component": "fixture.water"}),
    ),
    (
        "form unknown",
        {("entries", "3", "form"): "acme.antoine", ("entries", "3", "coefficients"): {"a": 1.0}},
        ("correlation_form_unknown", {"entry": "/entries/3", "form": "acme.antoine"}),
    ),
    (
        "coefficients",
        {("entries", "1", "coefficients", "b5"): 1.0},
        ("correlation_coefficients_invalid", {"entry": "/entries/1", "form": "cp_ig_poly4_theta"}),
    ),
    (
        "range order",
        {("entries", "1", "validity", "T"): [1000.0, 200.0]},
        ("validity_range_invalid", {"entry": "/entries/1", "variable": "T"}),
    ),
    (
        "range variable",
        {("entries", "1", "validity", "P"): [1.0, 2.0]},
        ("validity_range_invalid", {"entry": "/entries/1", "variable": "P"}),
    ),
    (
        "source",
        {("entries", "0", "provenance", "source"): "elsewhere"},
        ("provenance_invalid", {"entry": "/entries/0"}),
    ),
    (
        "core form",
        {
            ("entries", "0", "form"): "cp_ig_poly4_theta",
            ("entries", "0", "coefficients"): {"b0": 1.0},
        },
        ("record_schema_invalid", {"pointer": "/entries/0"}),
    ),
    (
        "core phase",
        {("entries", "3", "phase"): "aq"},
        ("record_schema_invalid", {"pointer": "/entries/3/phase"}),
    ),
    (
        "unknown core id",
        {("entries", "0", "property"): "boiling_point"},
        ("record_schema_invalid", {"pointer": "/entries/0/property"}),
    ),
    (
        "verification",
        {("elemental_verification",): "NOT_APPLICABLE"},
        ("record_schema_invalid", {"pointer": "/elemental_verification"}),
    ),
]


@pytest.mark.parametrize(
    ("changes", "expected"), [row[1:] for row in D7_ROWS], ids=[row[0] for row in D7_ROWS]
)
def test_d7_refusals(
    changes: dict[tuple[str, ...], Any], expected: tuple[str, dict[str, str]]
) -> None:
    """Each row breaks one D7 rule of the valid water record and gets that refusal (pointers are
    into the normalised record: entries sort by property, so `/entries/0` is
    `critical_temperature`, 1 `ideal_gas_cp`, 2 `user.surface_tension`, 3 `vapour_pressure`)."""
    outcome = identify(_with(changes, _water()))
    assert expected in _codes(outcome.errors)
    assert outcome.record_sha256 is None


@pytest.mark.parametrize("name", MAXIMAL)
def test_d7_a_trailing_newline_matches_no_pattern(name: str) -> None:
    """Review M2: every schema leaf with a `pattern` refuses its fixture value plus `"\\n"` (a
    YAML block scalar spells one), so no non-token is hashed and D6 never misreads `"l\\n"`. The
    fixtures' own refusals are not `record_schema_invalid`, which is the only error a schema
    failure gives."""
    document = _fixture(name)
    assert "record_schema_invalid" not in {code for code, _ in _codes(identify(document).errors)}
    for path, value in document_leaves(document):
        if _pattern_of(path) in PATTERNED and isinstance(value, str):
            outcome = identify(_set(document, path, value + "\n"))
            assert [code for code, _ in _codes(outcome.errors)] == ["record_schema_invalid"], path
            assert outcome.record_sha256 is None


def test_d7_the_fixtures_reach_every_patterned_leaf() -> None:
    reached = {_pattern_of(path) for name in MAXIMAL for path, _ in document_leaves(_fixture(name))}
    assert PATTERNED <= reached
    assert ("formation", "*", "phase") in PATTERNED


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({("identifiers", "cas"): "7732-18-5\n"}, ("identifier_invalid", "cas")),
        (
            {("identifiers", "inchikey"): "XLYOFNOQVPJJNP-UHFFFAOYSA-N\n"},
            ("identifier_invalid", "inchikey"),
        ),
        ({("identifiers", "formula"): "H2O\n"}, ("formula_elements_invalid", None)),
    ],
)
def test_d7_a_trailing_newline_fails_the_identifier_rules(
    changes: dict[tuple[str, ...], Any], expected: tuple[str, str | None]
) -> None:
    """Review M2: the CAS, InChIKey and formula readers match the whole string."""
    code, scheme = expected
    params = {"component": "fixture.water"} | ({} if scheme is None else {"scheme": scheme})
    outcome = identify(_with(changes, _water()))
    assert _codes(outcome.errors) == [(code, params)]


def test_d7_a_source_key_with_a_trailing_newline_is_refused() -> None:
    document = _minimal()
    document["sources"] = {"s\n": {"version": "1"}}
    document["molar_mass"]["provenance"]["source"] = "s\n"
    outcome = identify(document)
    assert [code for code, _ in _codes(outcome.errors)] == ["record_schema_invalid"]


def test_d7_a_duplicate_key_is_refused_never_dropped() -> None:
    """D2 step 4: two distinct entries with one (property, phase) are kept and refused."""
    document = _water()
    twin = copy.deepcopy(document["entries"][0])
    twin["value"] = 650.0
    document["entries"].append(twin)
    outcome = identify(document)
    assert len(outcome.record["entries"]) == 5
    assert ("record_schema_invalid", {"pointer": "/entries/1"}) in _codes(outcome.errors)
    identical = _water()
    identical["entries"].append(copy.deepcopy(identical["entries"][0]))
    assert identify(identical).record_sha256 == identify(_water()).record_sha256


def test_e_f3_4_entries_equal_after_their_inner_sets_are_sorted_are_one_entry() -> None:
    """Review S1: two entries that differ only in the order of `provenance.origin` are
    canonically identical after step 4, so one is removed and the record is the one-entry
    record."""
    single = _water()
    single["entries"][0]["provenance"]["origin"] = ["measured", "computed"]
    twins = copy.deepcopy(single)
    twin = copy.deepcopy(single["entries"][0])
    twin["provenance"]["origin"] = ["computed", "measured"]
    twins["entries"].append(twin)
    outcome = identify(twins)
    assert outcome.errors == ()
    assert outcome.record_sha256 == identify(single).record_sha256 is not None


def test_d7_colliding_keys_after_nfc_are_refused() -> None:
    document = _minimal()
    document["sources"] = {"café": {"version": "1"}, "café": {"version": "2"}}
    outcome = identify(document)
    assert ("record_schema_invalid", {"pointer": "/sources/café"}) in _codes(outcome.errors)


def _where(entries: list[dict[str, Any]], member: str, value: Any) -> str:
    """The normalised pointer of the one entry whose `member` is `value` (step 4 re-sorts)."""
    [index] = [i for i, entry in enumerate(entries) if entry.get(member) == value]
    return f"/entries/{index}"


@pytest.mark.parametrize(
    ("member", "value", "suffix"),
    [
        ("indices", ["A", "A"], "/indices"),
        ("indices", ["A", "C"], "/indices/1"),
        ("value", 0.0, "/value"),
    ],
)
def test_d7_parameter_set_entry_rules(member: str, value: Any, suffix: str) -> None:
    """D5: entry indices are component keys; `wilson_lambda` has two distinct indices and a value
    above 0."""
    outcome = identify(_with({("entries", "2", member): value}, _fixture("parameter-set-maximal")))
    at = _where(outcome.record["entries"], member, value)
    assert ("record_schema_invalid", {"pointer": at + suffix}) in _codes(outcome.errors)


def test_d7_parameter_set_keys_and_domain() -> None:
    base = _fixture("parameter-set-maximal")
    twin = identify(_with({("components", "1", "key"): "A"}, base))
    assert ("record_schema_invalid", {"pointer": "/components/1"}) in _codes(twin.errors)
    outside = identify(_with({("validity", "x"): [0.0, 1.0]}, base))
    assert _codes(outside.errors) == [
        ("validity_range_invalid", {"entry": "/validity", "variable": "x"})
    ]


def test_d7_a_set_component_matched_by_inchikey_has_d3_pattern() -> None:
    """Review S8: `components[].match.inchikey` carries D3's InChIKey pattern."""
    base = _fixture("parameter-set-maximal")
    outcome = identify(_with({("components", "1", "match", "inchikey"): "x"}, base))
    assert _codes(outcome.errors) == [
        ("record_schema_invalid", {"pointer": "/components/1/match/inchikey"})
    ]


def test_d7_fit_inputs_unhashed_is_a_finding() -> None:
    document = _water()
    del document["entries"][1]["provenance"]["inputs"]
    outcome = identify(document)
    assert outcome.errors == ()
    assert _codes(outcome.findings) == [("fit_inputs_unhashed", {"entry": "/entries/1"})]


@pytest.mark.parametrize(
    "text",
    ["[1, 2]", '{"a": 1, "a": 2}', "id: x\ndate: 2026-11-18\n", "{not json"],
)
def test_step_1_refuses_text_outside_the_json_data_model(text: str) -> None:
    outcome = identify(text)
    assert outcome.errors and outcome.errors[0].code == "record_schema_invalid"
    assert outcome.record_sha256 is None


def test_step_1_refuses_a_repeated_key_in_yaml_and_behind_a_byte_order_mark() -> None:
    """Review S2: YAML refuses a repeated key as JSON does; JSON text behind a BOM is JSON."""
    import yaml

    as_yaml = yaml.safe_dump(_minimal()) + "name: other\n"
    as_json = "\ufeff" + json.dumps(_minimal())[:-1] + ', "name": "other"}'
    for text in (as_yaml, as_json, as_json.encode("utf-8")):
        outcome = identify(text)
        assert _codes(outcome.errors) == [("record_schema_invalid", {"pointer": ""})]
        assert outcome.record_sha256 is None
    base = identify(_minimal()).record_sha256
    assert identify("\ufeff" + json.dumps(_minimal())).record_sha256 == base is not None
    merged = normalize("b:\n  <<: {k: 1}\n  k: 2\n")  # a merge key is no repeat
    assert (merged.errors, merged.record) == ((), {"b": {"k": 2}})
    # A merge key through an alias is refused as every alias is (R-1057, F3 review 2 C1).
    aliased = normalize("a: &x {k: 1}\nb:\n  <<: *x\n  k: 2\n")
    assert _codes(aliased.errors) == [("record_schema_invalid", {"pointer": ""})]


def test_step_1_refuses_and_never_raises_on_undecodable_or_unbounded_input() -> None:
    """Review S3: bytes that are not UTF-8, a recursive YAML alias, and JSON text or a parsed
    document nested beyond the recursion limit are `record_schema_invalid("")`."""
    nested: list[Any] = []
    deep = {**_minimal(), "x": nested}
    for _ in range(100_000):
        nested.append([])
        nested = nested[0]
    for source in (
        b"\xff\xfe{",
        "a: &x [*x]\n",
        '{"a": ' + "[" * 100_000 + "]" * 100_000 + "}",
        deep,
    ):
        outcome = identify(source)
        assert _codes(outcome.errors) == [("record_schema_invalid", {"pointer": ""})]
        assert outcome.record_sha256 is None


def test_text_and_document_give_one_sha() -> None:
    import yaml

    document = _water()
    as_json = identify(json.dumps(document))
    as_yaml = identify(yaml.safe_dump(document, allow_unicode=True))
    assert as_json.record_sha256 == as_yaml.record_sha256 == identify(document).record_sha256
