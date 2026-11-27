"""Lowering a v1-expressible v2 revision to its v1 document (ADR 0062 D12).

A v2 document is *v1-expressible* iff its convention is the legacy provider's native one, every
material connection is `nTP-v1`, it has no energy or signal connection, reaction set, section, probe
or parameter endpoint, and every component record is a legacy record (ADR 0061 D12) of one file,
named by its id there (F2 decision WO6a-2: D12's "whose component list equals `component_set` in
order" is read as the lowered `components` being the set's ids in its order, which admits a permuted
set, as v1 does, and CoolProp's one fluid of 123). `lower` maps it field by field to the v1 document
the untouched v1 path compiles: `component_set` becomes `{record_source: that file, components: the
ids in order}`; a connection's `definition: nTP-v1` becomes `state_definition: nTP-v1`,
`component_mapping: revision_component_set`, with `phase_capability`, `initialization_hint` and
`notes` copied; instances, specifications in v1's target form and the provenance are copied;
`convention`, `materials`, `property_methods`, `reaction_sets` and `sections` are dropped, after
checking that `property_methods.default` is the provider ADR 0050 D1 assigns to the file and that
there are no overrides. A document's `content_hash`, when it carries one, is recomputed for the v1
document by v1's rule (the field names its own document; it is outside the hash either way).

Anything else is refused with every `construct_unavailable(<construct>, <foundation>)` found,
sorted as `validate` sorts (`LoweringError.refusals`). The constructs and their foundations:
`convention:<id>` and `property_methods` (F4, as `validate` names them), `component:<id>` (a
record that is not a legacy component record of that id) and `component_set` (records of more
than one file), F4; `definition:<id>` (a material definition other than `nTP-v1`), `energy:<c>`,
`signal:<c>`, `probe:<c>` and `parameter:<instance>.<parameter>` (D9), `reaction_set:<id>`,
`section:<namespace>` and `target:<specification>` (a v2 target form), F6; `derived:<id>` (D10),
F4. Whether a refusal is reported once per fault follows F2 decision WO4-6: the convention and the
property methods are checked only when the component set names one file.

D11 fields D12 does not classify, and v1 has no field for, are refused too (F2 decision WO6a-3):
`semantic_role:<role>` for ADR 0062 D11's four roles outside v1's vocabulary (`utility`,
`controller`, `shaft`, `relief_device`; ADR-F6 owns it), `template:<instance>` and
`references:<instance>` (F6), `phase_assertion:<connection>` (F5) and a non-empty
`parameter_sets` (`parameter_sets`, F4). `materials` is dropped as D12 says, whatever it holds: a
valid document whose connections are all `nTP-v1` uses none of its definitions.

`lower` reads the document as parsed; the validator's refusals (`validate`) come first. The legacy
records are the committed legacy index's (`records.importers.legacy.committed_index`); the
provider selection is the caller's `LegacyProviders` (F2 decision WO6a-1).
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


def _methods(document: Mapping[str, Any], provider: LegacyProvider, refusals: list[Coded]) -> None:
    convention = document["convention"]
    if convention != provider.convention:
        refusals.append(_refused(f"convention:{convention}", "F4"))
    methods = document["property_methods"]
    if methods["overrides"] or methods["default"] != provider.provider:
        refusals.append(_refused("property_methods", "F4"))


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
    """D11's fields D12 does not classify and v1 has no field for (F2 decision WO6a-3)."""
    for instance in document["instances"]:
        if instance["semantic_role"] not in V1_ROLES:
            refusals.append(_refused(f"semantic_role:{instance['semantic_role']}", "F6"))
        for key in ("template", "references"):
            if key in instance:
                refusals.append(_refused(f"{key}:{instance['id']}", "F6"))
    for connection in document["connections"]:
        if "phase_assertion" in connection:
            refusals.append(_refused(f"phase_assertion:{connection['id']}", "F5"))
    if document["component_set"]["parameter_sets"]:
        refusals.append(_refused("parameter_sets", "F4"))


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
        _methods(document, providers.select(source), refusals)
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
