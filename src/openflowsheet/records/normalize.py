"""The record normaliser (ADR 0061 D2 steps 1 to 5, D6), run on every path that hashes.

`normalize` parses a record (step 1), detaches `volatile` (2), removes the optional members equal
to `null`, `[]` or `{}` (2a), brings every string and key to Unicode NFC (3), sorts the set-valued
arrays and `formation` (4) and derives a component's `anchor_phase` when it is absent (5).
Validation (6) and the identity SHA (7) are `validate`'s and `identity`'s. Which members are
optional is read from `schemas/record-v2.schema.json`, so step 2a is a schema fact as the volatile
set is.

Nothing is dropped silently: two distinct elements with one key are left in place for step 6 to
refuse, and two object keys that collide after NFC keep the second key as written and are
reported here as `record_schema_invalid(<pointer>)`.
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from typing import Any, NamedTuple

import yaml
from jsonschema import Draft202012Validator

from openflowsheet.canonical import canonical_json, first_noncanonical
from openflowsheet.records.model import (
    ANCHOR,
    VOLATILE,
    is_phase,
    phase_class,
    pointer,
    record_schema,
)
from openflowsheet.registry.tokens import Coded


class Normalized(NamedTuple):
    """Steps 1 to 5's result: the identity projection (`record`), the detached `volatile` block
    (`None` when absent, `null` or `{}`), the refusals found while normalising (`errors`: a parse
    failure or an NFC key collision) and D6's notices (`findings`). Step 6 checks the anchor
    whether stated or derived, so validity is a function of the normalised record (review M1)."""

    record: dict[str, Any]
    volatile: Any
    errors: tuple[Coded, ...]
    findings: tuple[Coded, ...]


def schema_invalid(at: str) -> Coded:
    """D7's `record_schema_invalid(<pointer>)`."""
    return Coded("record_schema_invalid", {"pointer": at})


def normalize(source: str | bytes | Mapping[str, Any]) -> Normalized:
    """D2 steps 1 to 5 on one record: JSON or YAML text, or a parsed document. A document that
    is not a JSON object, or holds a value outside the JSON data model, is returned empty with
    its `record_schema_invalid` error (step 1)."""
    document = _parsed(source)
    if isinstance(document, Coded):
        return Normalized({}, None, (document,), ())
    volatile = document.pop(VOLATILE, None)
    stripped = strip_empty(document, record_schema())
    record, collisions = nfc(stripped, "")
    record = sort_sets(record)
    findings: tuple[Coded, ...] = ()
    if record.get("record_type") == "component" and ANCHOR not in record:
        record[ANCHOR], findings = derive_anchor(record)
    return Normalized(
        record,
        None if volatile in (None, {}) else volatile,
        tuple(schema_invalid(at) for at in collisions),
        findings,
    )


def _parsed(source: str | bytes | Mapping[str, Any]) -> dict[str, Any] | Coded:
    """Step 1: the record as a fresh `dict`, or `record_schema_invalid` at the root (not an
    object; a repeated key) or at the first node outside the JSON data model (a YAML
    date, a non-finite float; `canonical.first_noncanonical`). JSON is text starting with `{`
    after an optional byte-order mark; anything else is YAML (`yaml.safe_load`'s loader). A
    repeated key is refused in either."""
    document: object = source
    if isinstance(document, bytes):
        document = document.decode("utf-8")
    if isinstance(document, str):
        try:
            document = _loaded(document)
        except (ValueError, yaml.YAMLError):
            return schema_invalid("")
    if not isinstance(document, Mapping):
        return schema_invalid("")
    bad = first_noncanonical(document)
    if bad is not None:
        return schema_invalid(bad)
    copied: dict[str, Any] = json.loads(canonical_json(document))
    return copied


def _loaded(text: str) -> object:
    """JSON or YAML text, parsed, a leading byte-order mark ignored; a repeated key raises
    (`ValueError` in JSON, `yaml.YAMLError` in YAML, review S2)."""
    text = text.removeprefix("\ufeff")
    if text.lstrip().startswith("{"):
        return json.loads(text, object_pairs_hook=_unique_members)
    return yaml.load(text, Loader=_UniqueKeySafeLoader)  # noqa: S506 (a SafeLoader subclass)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` that refuses a mapping with a repeated key, as the JSON path does,
    instead of keeping the last value. A merge key (`<<`) is not a member."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        keys = [
            self.construct_object(key, deep=True)
            for key, _ in node.value
            if key.tag != "tag:yaml.org,2002:merge"
        ]
        try:
            repeated = len(set(keys)) != len(keys)
        except TypeError:  # an unhashable key: the base constructor refuses it
            repeated = False
        if repeated:
            raise yaml.constructor.ConstructorError(
                None, None, "a repeated mapping key", node.start_mark
            )
        return super().construct_mapping(node, deep=deep)


def _unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    members = dict(pairs)
    if len(members) != len(pairs):
        raise ValueError("a repeated key")
    return members


# -- step 2a: optional empty members ------------------------------------------------------------


def strip_empty(node: Any, schema: Any) -> Any:
    """Step 2a: `node` without its optional members equal to `null`, `[]` or `{}`, recursively
    and bottom-up, so a member emptied by the removal goes too. An optional member is one an
    applicable subschema names in `properties` and none lists as `required`; required members,
    the entries of a map (`additionalProperties`) and members the schema does not describe stay
    in place for step 6 (review M3). `schema` is the node's schema in the record schema."""
    if isinstance(node, list):
        return [
            strip_empty(item, _item_schema(schema, index, item)) for index, item in enumerate(node)
        ]
    if not isinstance(node, dict):
        return node
    members, other, required = _object_rules(schema, node)
    kept = {}
    for key, value in node.items():
        child = strip_empty(value, members.get(key, other))
        if key in required or key not in members or not _empty(child):
            kept[key] = child
    return kept


def _empty(value: object) -> bool:
    return value is None or (isinstance(value, list | dict) and not value)


def _item_schema(schema: Any, index: int, item: object) -> Any:
    """The schema of element `index` of an array: the first applicable `prefixItems` or `items`."""
    for part in _applicable(schema, item):
        prefix = part.get("prefixItems", [])
        if index < len(prefix):
            return prefix[index]
        if isinstance(part.get("items"), dict):
            return part["items"]
    return {}


def _object_rules(schema: Any, node: dict[str, Any]) -> tuple[dict[str, Any], Any, set[str]]:
    """The member schemas (`properties`, the first applicable one per name), the schema of other
    members (the first applicable `additionalProperties` object, else none) and the union of the
    applicable `required` lists, for the object `node`."""
    members: dict[str, Any] = {}
    other: Any = {}
    required: set[str] = set()
    for part in _applicable(schema, node):
        for key, member in part.get("properties", {}).items():
            members.setdefault(key, member)
        if isinstance(part.get("additionalProperties"), dict) and other == {}:
            other = part["additionalProperties"]
        required.update(part.get("required", ()))
    return members, other, required


def _applicable(schema: Any, node: object) -> Iterator[dict[str, Any]]:
    """Every subschema that applies to `node`: the schema, its `$ref` target, its `allOf` parts,
    the `then` or `else` its `if` selects, and the `anyOf` and `oneOf` branches whose `type`
    admits the node (the record schema never offers two branches of one type)."""
    if not isinstance(schema, dict):
        return
    yield schema
    if "$ref" in schema:
        yield from _applicable(_target(schema["$ref"]), node)
    for part in schema.get("allOf", ()):
        yield from _applicable(part, node)
    if "if" in schema:
        branch = "then" if Draft202012Validator(schema["if"]).is_valid(node) else "else"
        yield from _applicable(schema.get(branch), node)
    for part in (*schema.get("anyOf", ()), *schema.get("oneOf", ())):
        if _admits(part, node):
            yield from _applicable(part, node)


def _target(reference: str) -> Any:
    """A local `$ref` (`#/$defs/<name>`) of the record schema."""
    found: Any = record_schema()
    for part in reference.removeprefix("#/").split("/"):
        found = found[part]
    return found


_JSON_TYPES: dict[type, tuple[str, ...]] = {
    type(None): ("null",),
    bool: ("boolean",),
    int: ("integer", "number"),
    float: ("number",),
    str: ("string",),
    list: ("array",),
    dict: ("object",),
}


def _admits(schema: Any, node: object) -> bool:
    """Whether `schema`'s `type` (through a `$ref`) admits `node`'s JSON type; no `type` admits."""
    if isinstance(schema, dict) and "$ref" in schema:
        return _admits(_target(schema["$ref"]), node)
    if not isinstance(schema, dict) or "type" not in schema:
        return True
    declared = schema["type"]
    names = (declared,) if isinstance(declared, str) else tuple(declared)
    return any(name in names for name in _JSON_TYPES[type(node)])


# -- step 3: NFC ----------------------------------------------------------------------------------


def nfc(node: Any, at: str) -> tuple[Any, list[str]]:
    """Step 3: `node` with every string value and key in Unicode NFC, and the pointers (by the
    NFC spelling) of the keys that collide after NFC. Colliding keys are all kept as written, so
    step 6 sees every member."""
    if isinstance(node, str):
        return unicodedata.normalize("NFC", node), []
    if isinstance(node, list):
        items = [nfc(item, pointer(at, index)) for index, item in enumerate(node)]
        return [item for item, _ in items], [at for _, found in items for at in found]
    if not isinstance(node, dict):
        return node, []
    return _nfc_members(node, at)


def _nfc_members(node: dict[str, Any], at: str) -> tuple[dict[str, Any], list[str]]:
    """Step 3 on an object at `at`: its keys and members in NFC, a key that collides with another
    after NFC kept as written, and the collision pointers, those of this object first."""
    names = Counter(unicodedata.normalize("NFC", key) for key in node)
    clashing = sorted(name for name, count in names.items() if count > 1)
    members: dict[str, Any] = {}
    collisions = [pointer(at, name) for name in clashing]
    for key, value in node.items():
        name = unicodedata.normalize("NFC", key)
        name = key if name in clashing else name
        members[name], found = nfc(value, pointer(at, name))
        collisions.extend(found)
    return members, collisions


# -- step 4: set-valued arrays --------------------------------------------------------------------


def sort_sets(record: dict[str, Any]) -> dict[str, Any]:
    """Step 4 on a `component` or `parameter_set` record: `synonyms`, `entries` (by property,
    phase, indices), `transitions` (by from, to) and `components` (by key) sorted by the
    canonical-JSON bytes of their keys, and every provenance's `origin` and `inputs` by their
    elements' (the provenance sets first, review S1); canonically identical elements removed,
    distinct elements with one key kept.
    `formation` is sorted by phase class, stably. Another record type is returned as it is."""
    if record.get("record_type") not in ("component", "parameter_set"):
        return record
    for _, holder in quantities(record):  # inner sets first, so outer elements compare normalised
        if isinstance(holder.get("provenance"), dict):
            holder["provenance"] = _provenance_sets(holder["provenance"])
    for name, key in _SET_KEYS.items():
        if isinstance(record.get(name), list):
            record[name] = _as_set(record[name], key)
    if isinstance(record.get("formation"), list):
        record["formation"] = sorted(record["formation"], key=_formation_class)
    return record


def _provenance_sets(provenance: dict[str, Any]) -> dict[str, Any]:
    """A provenance with its `origin` and `inputs` as sets (`_as_set` by whole element)."""
    return {
        name: _as_set(value, _whole)
        if name in ("origin", "inputs") and isinstance(value, list)
        else value
        for name, value in provenance.items()
    }


def _whole(element: object) -> object:
    return element


def _entry_key(element: object) -> object:
    entry = element if isinstance(element, dict) else {}
    return [entry.get("property"), entry.get("phase"), entry.get("indices")]


def _transition_key(element: object) -> object:
    transition = element if isinstance(element, dict) else {}
    return [transition.get("from"), transition.get("to")]


def _component_key(element: object) -> object:
    return element.get("key") if isinstance(element, dict) else None


#: Step 4: the top-level set-valued arrays and the key each is sorted by.
_SET_KEYS: dict[str, Callable[[object], object]] = {
    "synonyms": _whole,
    "entries": _entry_key,
    "transitions": _transition_key,
    "components": _component_key,
}


def _as_set(elements: list[Any], key: Callable[[object], object]) -> list[Any]:
    """`elements` sorted by (key bytes, element bytes), canonically identical ones removed."""
    ordered = sorted(
        ((canonical_json(key(element)), canonical_json(element), element) for element in elements),
        key=lambda row: (row[0], row[1]),
    )
    kept: list[Any] = []
    previous: bytes | None = None
    for _, whole, element in ordered:
        if whole != previous:
            kept.append(element)
        previous = whole
    return kept


def _formation_class(element: object) -> int:
    return phase_class(element.get("phase") if isinstance(element, dict) else None)


def quantities(record: Mapping[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Every Constant and entry of a `component` or `parameter_set` record, with its pointer:
    `molar_mass`, each formation and transition `h` and `s`, each entry, each segment type's
    `molar_mass`, in that order. Members of the wrong JSON type are skipped (step 6 refuses
    them)."""
    if isinstance(record.get("molar_mass"), dict):
        yield "/molar_mass", record["molar_mass"]
    yield from _members(record, "formation", ("h", "s"))
    yield from _members(record, "transitions", ("h", "s"))
    for index, item in _objects(record.get("entries")):
        yield f"/entries/{index}", item
    yield from _members(record, "segment_types", ("molar_mass",))


def _members(
    record: Mapping[str, Any], name: str, parts: tuple[str, ...]
) -> Iterator[tuple[str, dict[str, Any]]]:
    """The object members `parts` of each object element of `record[name]`, with pointers."""
    for index, item in _objects(record.get(name)):
        for part in parts:
            if isinstance(item.get(part), dict):
                yield f"/{name}/{index}/{part}", item[part]


def _objects(value: object) -> Iterator[tuple[int, dict[str, Any]]]:
    if isinstance(value, list):
        yield from ((index, item) for index, item in enumerate(value) if isinstance(item, dict))


# -- step 5: the anchor (D6) ----------------------------------------------------------------------


def derive_anchor(record: Mapping[str, Any]) -> tuple[str | None, tuple[Coded, ...]]:
    """D6 on a normalised component without `anchor_phase`: `aq` when charged (1); else the first
    phase, in class order and then record order, with a formation entry (2); else the first
    phase-tagged entry's (3); else `ig` with `anchor_defaulted` on the `mol` basis (4); else
    `None` with `anchor_undetermined` (5). Steps 2 and 3 read the arrays as step 4 sorted them."""
    component = {"component": str(record.get("id", ""))}
    charge = record.get("charge")
    if isinstance(charge, int | float) and not isinstance(charge, bool) and charge != 0:
        return "aq", ()
    for name in ("formation", "entries"):
        phases = [
            item["phase"] for _, item in _objects(record.get(name)) if is_phase(item.get("phase"))
        ]
        if phases:
            return min(phases, key=phase_class), ()  # `min` keeps the first of the lowest class
    if record.get("amount_basis") == "mol":
        return "ig", (Coded("anchor_defaulted", component),)
    return None, (Coded("anchor_undetermined", component),)
