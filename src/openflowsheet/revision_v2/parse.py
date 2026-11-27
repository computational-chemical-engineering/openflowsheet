"""Reading a v2 revision (ADR 0062 D11, D12's `schema_version: 2` branch).

`parse` takes JSON or YAML text, or a parsed document, and returns a `RevisionV2` or raises
`RevisionV2Error` with one typed refusal: `schema_invalid(<pointer>)` at the root for text that is
not one JSON object (a repeated key, a YAML alias, bytes that are not UTF-8), at the first node
outside the JSON data model, at `/schema_version` for a document that is not v2 (never read as the
other version, ADR 0002 D7.5), or at the first schema error by path. A `RevisionV2` holds a fresh
copy of the document as given; `canonical` gives its normal form.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

import yaml

from openflowsheet.canonical import canonical_json, first_noncanonical
from openflowsheet.material.definitions import LEGACY_TEMPLATE
from openflowsheet.material.layout import ConnectionInput
from openflowsheet.records.normalize import loaded
from openflowsheet.registry.tokens import Coded
from openflowsheet.schema_check import DocumentSchemaError, validate_document

__all__ = ["SCHEMA_NAME", "RevisionV2", "RevisionV2Error", "parse"]

#: The v2 revision schema, under `schemas/` (package data `_data/schemas/`).
SCHEMA_NAME: Final = "process-revision-v2.schema.json"


class RevisionV2Error(ValueError):
    """A v2 document `parse` refuses; `coded` is the typed refusal."""

    def __init__(self, coded: Coded) -> None:
        super().__init__(f"{coded.code}({', '.join(coded.params.values())})")
        self.coded = coded


def _refused(pointer: str) -> RevisionV2Error:
    return RevisionV2Error(Coded("schema_invalid", {"pointer": pointer}))


@dataclass(frozen=True, slots=True)
class RevisionV2:
    """A schema-valid v2 document, as given (a private copy)."""

    document: Mapping[str, Any]

    @property
    def components(self) -> tuple[str, ...]:
        """The component set's ids, in its order."""
        return tuple(c["id"] for c in self.document["component_set"]["components"])

    def definition(self, connection: Mapping[str, Any]) -> dict[str, Any] | None:
        """`connection`'s definition instance (D3; a `materials` entry without its id), `None`
        when its `definition` names no `materials.definitions` entry."""
        name = connection["definition"]
        if connection["kind"] == "signal":
            return {"template": name, "quantity_kind": connection["quantity_kind"]}
        if connection["kind"] == "energy" or name == LEGACY_TEMPLATE:
            return {"template": name}
        for entry in self.document["materials"]["definitions"]:
            if entry["id"] == name:
                return {key: value for key, value in entry.items() if key != "id"}
        return None

    def connection_inputs(
        self, definition_sha256: Mapping[str, str] | None = None
    ) -> tuple[ConnectionInput, ...]:
        """Every connection whose definition resolves, as the layout takes it (D8); the SHAs by
        definition reference (`definition`), empty when not given."""
        shas = definition_sha256 or {}
        found = []
        for connection in self.document["connections"]:
            instance = self.definition(connection)
            if instance is not None:
                name = connection["definition"]
                found.append(ConnectionInput(connection["id"], name, instance, shas.get(name, "")))
        return tuple(found)


def _document(source: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    try:
        document = loaded(source) if isinstance(source, str | bytes) else source
        if not isinstance(document, Mapping):
            raise _refused("")
        bad = first_noncanonical(document)
        if bad is not None:
            raise _refused(bad)
        copied: dict[str, Any] = json.loads(canonical_json(document))
    except (ValueError, yaml.YAMLError, RecursionError) as error:
        if isinstance(error, RevisionV2Error):
            raise
        raise _refused("") from error
    return copied


def parse(source: str | bytes | Mapping[str, Any]) -> RevisionV2:
    """A v2 revision from `source`, schema-checked; `RevisionV2Error` otherwise."""
    document = _document(source)
    if document.get("schema_version") != 2:
        raise _refused("/schema_version")
    try:
        validate_document(SCHEMA_NAME, document)
    except DocumentSchemaError as error:
        raise _refused(error.pointer) from error
    return RevisionV2(document)
