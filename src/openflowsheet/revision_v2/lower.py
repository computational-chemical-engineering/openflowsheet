"""Lowering a v1-expressible v2 revision to its v1 document (ADR 0062 D12, as corrected by F2-R1).

D12: a v2 document is *v1-expressible* iff (a) its convention is the native one of the legacy
provider ADR 0050 D1 assigns to its record source, and `property_methods.default` is that provider
with no override; (b) `materials.thermal_coordinate` is `T`; (c) every material connection is
`nTP-v1`, and it has no energy or signal connection, reaction set, section, probe or parameter
endpoint, specification target outside v1's form, connection `phase_assertion`, instance
`template` or `references`, or `semantic_role` outside v1's vocabulary; (d) its component set is
legacy: every component record is the legacy component record (ADR 0061 D12) of one file, under
the component's own id there, in any order and for any subset of that file's components (as v1's
`record_source` binds them), and `parameter_sets` lists exactly that file's legacy parameter-set
records, in the legacy index's order. The criterion stands without `validate`. Such a document
lowers to the v1 document with `record_source` = that file and `components` = the set's ids in
the set's order (ADR 0001 D2.1); anything else is refused with every construct found, once each,
as `construct_unavailable(<construct>, <foundation>)`: `convention:<id>`, `property_methods`,
`component:<id>`, `component_set` (records of two files), `parameter_sets`, `derived:<id>` (F4);
`phase_assertion:<connection>` (F5); `thermal_coordinate:<coordinate>`, `definition:<id>`,
`energy:<c>`, `signal:<c>`, `probe:<c>`, `parameter:<instance>.<parameter>`, `reaction_set:<id>`,
`section:<namespace>`, `target:<specification>`, `semantic_role:<role>`, `template:<instance>`,
`references:<instance>` (F6). `convention`, `property_methods` and `parameter_sets` are checked
only when the component set names one file. Lowering is a field map. A connection with
`definition: nTP-v1` becomes `state_definition: nTP-v1`, `component_mapping:
revision_component_set`. `phase_capability`, `initialization_hint` and `notes` are copied.
Instances and specifications in v1's target form are copied. `convention`, `materials` (whatever
its definitions and `phase_order_keys` hold: no `nTP-v1` connection reads them) and
`property_methods` are dropped. A field v1 has no counterpart for lowers only in its content-free
form, absent when optional and empty when required: admitting a construct later moves no byte of
a document accepted now, and giving a dropped one meaning later would. Lowering does not
anticipate the v1 binder: a lowered document the binder refuses is refused as its v1 twin is.

Here: the refusals are sorted as `validate` sorts them (`LoweringError.refusals`). A document's
`content_hash`, when it carries one, is recomputed for the v1 document by v1's rule (the field
names its own document; it is outside the hash either way). `lower` reads the document as parsed.
The legacy records, component and parameter-set, are the committed legacy index's
(`records.importers.legacy.committed_index`); the provider selection is the caller's
`LegacyProviders` (F2 decision WO6a-1).
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any, Final, NamedTuple

from openflowsheet.material.definitions import LEGACY_TEMPLATE
from openflowsheet.records.importers.legacy import committed_index
from openflowsheet.registry.tokens import Coded
from openflowsheet.revision_v2.canonical import content_hash
from openflowsheet.revision_v2.parse import RevisionV2

__all__ = [
    "COMPONENT_MAPPING",
    "LegacyProvider",
    "LegacyProviders",
    "LegacyRecord",
    "LoweringError",
    "file_components",
    "file_parameter_sets",
    "legacy_records",
    "lower",
]

#: v1's one component mapping (`process-revision.schema.json`).
COMPONENT_MAPPING: Final = "revision_component_set"
#: The connection fields D12 copies; every other v2 connection field is mapped or refused.
_COPIED_CONNECTION_FIELDS: Final = ("phase_capability", "initialization_hint", "notes")
#: The optional top-level fields v1 and v2 share.
_OPTIONAL_FIELDS: Final = ("title", "description")


class LoweringError(ValueError):
    """A v2 document `lower` refuses; `refusals` are the typed `construct_unavailable`s, sorted."""

    def __init__(self, refusals: Iterable[Coded]) -> None:
        unique = {(c.code, tuple(sorted(c.params.items()))): c for c in refusals}
        self.refusals: tuple[Coded, ...] = tuple(sorted(unique.values(), key=Coded.sort_key))
        super().__init__(
            "; ".join(f"{c.code}({', '.join(c.params.values())})" for c in self.refusals)
        )


@dataclass(frozen=True, slots=True)
class LegacyProvider:
    """A legacy provider's id (`describe().provider_id`) and its native convention (ADR 0001 D5)."""

    provider: str
    convention: str


@dataclass(frozen=True, slots=True)
class LegacyProviders:
    """ADR 0050 D1's selection by record source: the registered sources, by string equality, and
    `otherwise` for every other source (SYN-001's)."""

    registered: Mapping[str, LegacyProvider]
    otherwise: LegacyProvider

    def select(self, record_source: str) -> LegacyProvider:
        """The provider ADR 0050 D1 assigns to `record_source`."""
        return self.registered.get(record_source, self.otherwise)


class LegacyRecord(NamedTuple):
    """A legacy component record (ADR 0061 D12): its file (`legacy.file`) and its id there."""

    file: str
    component: str


@cache
def legacy_records() -> Mapping[str, LegacyRecord]:
    """Every legacy component record of the committed legacy index, by record SHA-256."""
    found: dict[str, LegacyRecord] = {}
    for entry in committed_index()["files"]:
        for record in entry["records"]:
            if record["record_type"] == "component":
                found[record["sha256"]] = LegacyRecord(entry["path"], record["id"])
    return found


def _refused(construct: str, foundation: str) -> Coded:
    return Coded("construct_unavailable", {"construct": construct, "foundation": foundation})


def _record_source(document: Mapping[str, Any], refusals: list[Coded]) -> str | None:
    """The one legacy file the component records come from, or `None` (with the refusals)."""
    records = legacy_records()
    files: set[str] = set()
    for component in document["component_set"]["components"]:
        found = records.get(component["record"])
        if found is None or found.component != component["id"]:
            refusals.append(_refused(f"component:{component['id']}", "F4"))
        else:
            files.add(found.file)
    if len(files) > 1:
        refusals.append(_refused("component_set", "F4"))
    if refusals or not files:
        return None
    (source,) = files
    return source


@cache
def file_components(path: str) -> tuple[str, ...]:
    """The component ids of legacy file `path` in file order (`legacy.position`); `()` for a
    path the legacy index does not hold."""
    for entry in committed_index()["files"]:
        if entry["path"] == path:
            ordered = sorted(
                (r for r in entry["records"] if r["record_type"] == "component"),
                key=lambda r: int(r["position"]),
            )
            return tuple(r["id"] for r in ordered)
    return ()


@cache
def file_parameter_sets(path: str) -> tuple[str, ...]:
    """The record SHA-256s of legacy file `path`'s parameter-set records (ADR 0061 D12), in the
    legacy index's order; `()` for a file with none or a path the legacy index does not hold."""
    for entry in committed_index()["files"]:
        if entry["path"] == path:
            return tuple(
                r["sha256"] for r in entry["records"] if r["record_type"] == "parameter_set"
            )
    return ()


def _one_file(
    document: Mapping[str, Any], source: str, provider: LegacyProvider, refusals: list[Coded]
) -> None:
    """D12 (a) and (d)'s parameter sets, checked only when the component set names one file."""
    convention = document["convention"]
    if convention != provider.convention:
        refusals.append(_refused(f"convention:{convention}", "F4"))
    methods = document["property_methods"]
    if methods["overrides"] or methods["default"] != provider.provider:
        refusals.append(_refused("property_methods", "F4"))
    if document["component_set"]["parameter_sets"] != list(file_parameter_sets(source)):
        refusals.append(_refused("parameter_sets", "F4"))


#: v1's `semantic_role` vocabulary (`process-revision.schema.json`); D11 adds four to it.
V1_ROLES: Final = frozenset(
    {
        "feed",
        "product_sink",
        "mixer",
        "heater",
        "flash",
        "splitter",
        "reactor",
        "separator",
        "valve",
        "pump",
        "heat_exchanger",
        "compressor",
        "turbine",
        "other",
    }
)


def _unclassified(document: Mapping[str, Any], refusals: list[Coded]) -> None:
    """D11's fields v1 has no field for (F2 decision WO6a-3, ruling F2-R1)."""
    coordinate = document["materials"]["thermal_coordinate"]
    if coordinate != "T":
        refusals.append(_refused(f"thermal_coordinate:{coordinate}", "F6"))
    for instance in document["instances"]:
        if instance["semantic_role"] not in V1_ROLES:
            refusals.append(_refused(f"semantic_role:{instance['semantic_role']}", "F6"))
        for key in ("template", "references"):
            if key in instance:
                refusals.append(_refused(f"{key}:{instance['id']}", "F6"))
    for connection in document["connections"]:
        if "phase_assertion" in connection:
            refusals.append(_refused(f"phase_assertion:{connection['id']}", "F5"))


def _structure(document: Mapping[str, Any], refusals: list[Coded]) -> None:
    """D12's constructs a v1 document has no field for."""
    for reaction_set in document["reaction_sets"]:
        refusals.append(_refused(f"reaction_set:{reaction_set['id']}", "F6"))
    for namespace in document["sections"]:
        refusals.append(_refused(f"section:{namespace}", "F6"))
    for connection in document["connections"]:
        name, kind = connection["id"], connection["kind"]
        if kind in ("energy", "signal"):
            refusals.append(_refused(f"{kind}:{name}", "F6"))
        elif connection["definition"] != LEGACY_TEMPLATE:
            refusals.append(_refused(f"definition:{connection['definition']}", "F6"))
        if "probe" in connection["from"]:
            refusals.append(_refused(f"probe:{name}", "F6"))
        if "parameter" in connection["to"]:
            sink = connection["to"]
            refusals.append(_refused(f"parameter:{sink['instance']}.{sink['parameter']}", "F6"))
    for specification in document["specifications"]:
        target = specification["target"]
        if "derived" in target:
            refusals.append(_refused(f"derived:{target['derived']}", "F4"))
        elif "object_type" not in target:
            refusals.append(_refused(f"target:{specification['id']}", "F6"))


def _connection(connection: Mapping[str, Any]) -> dict[str, Any]:
    lowered = {key: copy.deepcopy(connection[key]) for key in ("id", "kind", "from", "to")}
    lowered["state_definition"] = LEGACY_TEMPLATE
    lowered["component_mapping"] = COMPONENT_MAPPING
    for key in _COPIED_CONNECTION_FIELDS:
        if key in connection:
            lowered[key] = copy.deepcopy(connection[key])
    return lowered


def lower(revision: RevisionV2, providers: LegacyProviders) -> dict[str, Any]:
    """The v1 document of a v1-expressible `revision` (module docstring); `LoweringError` with
    every refusal otherwise. `revision` is not changed."""
    document = revision.document
    refusals: list[Coded] = []
    _structure(document, refusals)
    _unclassified(document, refusals)
    source_refusals: list[Coded] = []
    source = _record_source(document, source_refusals)
    refusals += source_refusals
    if source is not None:
        _one_file(document, source, providers.select(source), refusals)
    if refusals or source is None:
        raise LoweringError(refusals)
    lowered: dict[str, Any] = {
        "schema_version": 1,
        "revision_id": document["revision_id"],
        "parent_revision": document["parent_revision"],
    }
    for key in _OPTIONAL_FIELDS:
        if key in document:
            lowered[key] = document[key]
    lowered["component_set"] = {"record_source": source, "components": list(revision.components)}
    lowered["instances"] = copy.deepcopy(list(document["instances"]))
    lowered["connections"] = [_connection(c) for c in document["connections"]]
    lowered["specifications"] = copy.deepcopy(list(document["specifications"]))
    lowered["provenance"] = copy.deepcopy(dict(document["provenance"]))
    if "content_hash" in document:
        stated = document["content_hash"]
        lowered["content_hash"] = None if stated is None else content_hash(lowered)
    return lowered
