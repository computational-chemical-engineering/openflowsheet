"""Raising a v1 revision to the v2 document that lowers back to it (ADR 0062 D12; test and tooling
only).

`raise_v1` inverts `lower`'s field map: each component id becomes `{id, record}` with the SHA of
its legacy record in `component_set.record_source` (the committed legacy index; ADR 0061 D12), and
`parameter_sets` lists that file's legacy parameter-set records (`file_parameter_sets`);
`convention` is the native convention of the provider ADR 0050 D1 assigns to that file and
`property_methods` is `{default: that provider, overrides: []}`;
`materials` is `{thermal_coordinate: T, definitions: []}` (D11: `T` admits `nTP-v1` and legacy
units), with no reaction set and no section; a connection's `state_definition` and
`component_mapping` become `definition: nTP-v1`. A stated `content_hash` is recomputed for the v2
document. A v1 document outside that inverse (a record source the legacy index does not hold, a
component that file has no record of, a connection of another kind than `material`) raises
`ValueError`: no production path raises, so it has no typed refusal.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any, Final

from openflowsheet.material.definitions import LEGACY_TEMPLATE
from openflowsheet.revision_v2.canonical import content_hash
from openflowsheet.revision_v2.lower import (
    LegacyProviders,
    file_parameter_sets,
    legacy_records,
)

__all__ = ["THERMAL_COORDINATE", "raise_v1"]

#: The thermal coordinate of a raised document (D11).
THERMAL_COORDINATE: Final = "T"
#: The v1 connection fields `lower` maps; every other one is copied.
_MAPPED_CONNECTION_FIELDS: Final = frozenset({"state_definition", "component_mapping"})


def _record_shas(record_source: str) -> dict[str, str]:
    shas = {
        record.component: sha
        for sha, record in legacy_records().items()
        if record.file == record_source
    }
    if not shas:
        raise ValueError(f"{record_source!r} is not a file of the legacy index")
    return shas


def _connection(connection: Mapping[str, Any]) -> dict[str, Any]:
    if connection["kind"] != "material":
        raise ValueError(f"connection {connection['id']!r} is not a material connection")
    raised: dict[str, Any] = {}
    for key, value in connection.items():
        if key in _MAPPED_CONNECTION_FIELDS:
            if key == "state_definition":
                raised["definition"] = LEGACY_TEMPLATE
        else:
            raised[key] = copy.deepcopy(value)
    return raised


def raise_v1(document: Mapping[str, Any], providers: LegacyProviders) -> dict[str, Any]:
    """The v2 document `lower` maps back to the schema-valid v1 `document` (module docstring)."""
    component_set = document["component_set"]
    source = component_set["record_source"]
    shas = _record_shas(source)
    components = []
    for component in component_set["components"]:
        if component not in shas:
            raise ValueError(f"{source!r} holds no record of component {component!r}")
        components.append({"id": component, "record": shas[component]})
    provider = providers.select(source)
    raised: dict[str, Any] = {
        "schema_version": 2,
        "revision_id": document["revision_id"],
        "parent_revision": document["parent_revision"],
    }
    for key in ("title", "description"):
        if key in document:
            raised[key] = document[key]
    raised["convention"] = provider.convention
    raised["component_set"] = {
        "components": components,
        "parameter_sets": list(file_parameter_sets(source)),
    }
    raised["materials"] = {"thermal_coordinate": THERMAL_COORDINATE, "definitions": []}
    raised["reaction_sets"] = []
    raised["property_methods"] = {"default": provider.provider, "overrides": []}
    raised["instances"] = copy.deepcopy(list(document["instances"]))
    raised["connections"] = [_connection(c) for c in document["connections"]]
    raised["specifications"] = copy.deepcopy(list(document["specifications"]))
    raised["sections"] = {}
    raised["provenance"] = copy.deepcopy(dict(document["provenance"]))
    if "content_hash" in document:
        stated = document["content_hash"]
        raised["content_hash"] = None if stated is None else content_hash(raised)
    return raised
