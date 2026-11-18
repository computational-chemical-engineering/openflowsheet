"""The user-file adapter (ADR 0061 D12; the `data_source` `user-file` 1.0.0), F3-WO5a.

`import_user_file` reads one file a client submits to `register_record` (F3-WO5b) and returns one
D2 outcome per record, ready to store (`RecordStore.register`): the record's identity projection,
its volatile block, its errors and findings, and its SHA when nothing refuses it. Three formats:

- `record-v2-json`, `record-v2-yaml`: one v2 record or a list of them, each through D2 as it is;
- `component-record-v1-yaml`: a v1 component file (`schema_version: 1`, `record_schema:
  schemas/component-record.schema.json`, `reference_convention` (dropped), `components`), each
  component first checked against `schemas/component-record.schema.json`. A component maps by D12's
  component rows (`amount_basis` `mol`, `charge` 0, identifiers copied, the molar mass a Constant
  whose `note` ends with its `rights.source`), and each parameter by D12's parameter rows where
  D12 names it (`critical_temperature`, `critical_pressure`, `acentric_factor`; `ideal_gas_cp_b0…b4`
  with or without both `ideal_gas_cp_*_temperature` bounds; `vapour_pressure_a…d`;
  `standard_formation_enthalpy`), through `importers.legacy`'s functions, else as a constant entry
  `user.<name>`, phase null. Every value's provenance comes from the request's `defaults {origin,
  derivation, source_id, source_version, citation}`: `{origin, derivation, source: source_id,
  inputs: [], transformation: null}`, and the record's `sources` is `{source_id: {version:
  source_version, citation, licence_stated: null, url: null}}`. Without complete `defaults` no
  value has provenance: every Constant and entry is `provenance_invalid(<entry>)` (pointers into
  the normalised record), and the record has no SHA. A v1 record has no `legacy` member (D1: the
  legacy importer's only).

Every record's `volatile` is `{retrieved_at, local_path (when given), adapter_version}`, replacing
any the file states; `retrieved_at` is the caller's (the operation passes the time of the request).
Text that is not one JSON or YAML document, and each list element that is not an object, is one
refused outcome `record_schema_invalid("")`; a v1 file or component off its format is one refused
outcome `record_schema_invalid(<pointer into the file>)`, its first error (F3 decision WO5a-5).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

import yaml

from openflowsheet.records.identity import identify
from openflowsheet.records.importers import legacy
from openflowsheet.records.importers.legacy import LegacyImportError
from openflowsheet.records.model import RECORD_FORMAT, RECORD_TYPES, VOLATILE, RecordOutcome
from openflowsheet.records.model import pointer as member_pointer
from openflowsheet.records.normalize import loaded, normalize, quantities, schema_invalid
from openflowsheet.registry.tokens import Coded
from openflowsheet.schema_check import DocumentSchemaError, validate_document

if TYPE_CHECKING:
    from openflowsheet.registry import Registry

#: D12: the `user-file` data source's version, each record's `volatile.adapter_version`.
ADAPTER_VERSION: Final = "1.0.0"
FORMATS: Final = ("component-record-v1-yaml", "record-v2-json", "record-v2-yaml")
V1_COMPONENT_SCHEMA: Final = "component-record.schema.json"
#: D12: the members of `defaults`, all required for a v1 file.
DEFAULTS: Final = ("origin", "derivation", "source_id", "source_version", "citation")
_V1_FILE_KEYS: Final = frozenset(
    {"schema_version", "record_schema", "reference_convention", "components"}
)
_CP_NAMES: Final = frozenset(legacy.CP_COEFFICIENTS.values())
_BOUNDS: Final = frozenset(legacy.CP_BOUNDS)
_PSAT_NAMES: Final = frozenset(legacy.PSAT_COEFFICIENTS.values())
#: The v1 parameter names D12's parameter rows map; any other is `user.<name>`.
MAPPED: Final = frozenset({*legacy.CRITICAL, *_CP_NAMES, *_BOUNDS, *_PSAT_NAMES, legacy.FORMATION})


def import_user_file(
    file_format: str,
    content: str | bytes,
    *,
    retrieved_at: str,
    defaults: Mapping[str, Any] | None = None,
    local_path: str | None = None,
    registry: Registry | None = None,
) -> tuple[RecordOutcome, ...]:
    """D12's user-file adapter on `content` in `file_format` (one of `FORMATS`; another is a
    caller's `ValueError`): one D2 outcome per record, in file order, against `registry` (the
    process registry when `None`). `defaults` is read for a v1 file only."""
    if file_format not in FORMATS:
        raise ValueError(f"{file_format!r} is not a user-file format {FORMATS}")
    volatile = {
        "retrieved_at": retrieved_at,
        **({} if local_path is None else {"local_path": local_path}),
        "adapter_version": ADAPTER_VERSION,
    }
    syntax: Literal["json", "yaml"] = "json" if file_format == "record-v2-json" else "yaml"
    try:
        document = loaded(content, syntax=syntax)
    except (ValueError, yaml.YAMLError, RecursionError):
        return (_refused(""),)
    if file_format == "component-record-v1-yaml":
        return _v1_file(document, _Defaults.read(defaults), volatile, registry)
    items = document if isinstance(document, list) else [document]
    return tuple(
        identify({**item, VOLATILE: dict(volatile)}, registry=registry)
        if isinstance(item, Mapping)
        else _refused("")
        for item in items
    )


def _refused(at: str) -> RecordOutcome:
    """The outcome of text or a v1 component that gives no record: `record_schema_invalid(at)`."""
    return RecordOutcome({}, None, None, (schema_invalid(at),))


@dataclass(frozen=True)
class _Defaults:
    """The request's `defaults`, complete: a v1 value's provenance and the record's source."""

    origin: tuple[str, ...]
    derivation: str
    source_id: str
    source_version: str
    citation: str

    @classmethod
    def read(cls, defaults: Mapping[str, Any] | None) -> _Defaults | None:
        """The defaults when `defaults` has exactly D12's five members, `origin` a list of strings
        and the others strings; else `None` (every value then `provenance_invalid`). Their
        values are D7's to judge: an empty `origin` is `provenance_invalid`, an unknown one or a
        `derivation` off the enum `record_schema_invalid`."""
        if not isinstance(defaults, Mapping) or set(defaults) != set(DEFAULTS):
            return None
        origin = defaults["origin"]
        texts = [defaults[name] for name in DEFAULTS[1:]]
        if not isinstance(origin, list) or not all(isinstance(o, str) for o in [*origin, *texts]):
            return None
        return cls(tuple(origin), *texts)

    def provenance(self, field: str) -> dict[str, Any]:  # noqa: ARG002 (one class for all)
        """D4's provenance of every v1 value (`legacy.Classifier`)."""
        return {
            "origin": list(self.origin),
            "derivation": self.derivation,
            "source": self.source_id,
            "inputs": [],
            "transformation": None,
        }

    def sources(self) -> dict[str, Any]:
        """D1's `sources` member of every record of the file."""
        entry = {
            "version": self.source_version,
            "citation": self.citation,
            "licence_stated": None,
            "url": None,
        }
        return {self.source_id: entry}


class _Unclassified:
    """The `legacy.Classifier` of a v1 file without complete `defaults`: no provenance."""

    def provenance(self, field: str) -> dict[str, Any]:  # noqa: ARG002
        return {}


def _v1_file(
    document: object,
    defaults: _Defaults | None,
    volatile: Mapping[str, Any],
    registry: Registry | None,
) -> tuple[RecordOutcome, ...]:
    """A v1 file: its envelope, then each component."""
    refused = _envelope_pointer(document)
    if refused is not None:
        return (_refused(refused),)
    assert isinstance(document, Mapping)
    return tuple(
        _v1_component(component, f"/components/{index}", defaults, volatile, registry)
        for index, component in enumerate(document["components"])
    )


def _envelope_pointer(document: object) -> str | None:
    """The pointer of the first member of a v1 file's envelope off D12's file row, `None` when
    there is none: an object of `_V1_FILE_KEYS`, `schema_version` 1, `record_schema` the v1
    schema, `components` a list."""
    if not isinstance(document, Mapping):
        return ""
    unknown = sorted(str(key) for key in set(document) - _V1_FILE_KEYS)
    if unknown:
        return member_pointer("", unknown[0])
    expected = {
        "schema_version": legacy.V1_SCHEMA_VERSION,
        "record_schema": legacy.V1_RECORD_SCHEMA,
    }
    for name, value in expected.items():
        if document.get(name) != value:
            return member_pointer("", name)
    return None if isinstance(document.get("components"), list) else "/components"


def _v1_component(
    component: object,
    at: str,
    defaults: _Defaults | None,
    volatile: Mapping[str, Any],
    registry: Registry | None,
) -> RecordOutcome:
    """One v1 component: the v1 schema, D12's rows, then D2 (with `defaults`) or the
    `provenance_invalid` of every value (without)."""
    try:
        validate_document(V1_COMPONENT_SCHEMA, component)
    except DocumentSchemaError as error:
        return _refused(at + error.pointer)
    assert isinstance(component, Mapping)
    classifier: legacy.Classifier = _Unclassified() if defaults is None else defaults
    try:
        mass = legacy.molar_mass(classifier, component, f"{at}/molecular_weight")
    except LegacyImportError:
        return _refused(f"{at}/molecular_weight")
    try:
        mapped = _parameters(classifier, component["parameters"], f"{at}/parameters")
    except LegacyImportError:
        return _refused(f"{at}/parameters")
    record = {
        "record_format": RECORD_FORMAT,
        "record_type": "component",
        "type_version": RECORD_TYPES["component"].version,
        "id": component["id"],
        "name": component["name"],
        **({} if defaults is None else {"sources": defaults.sources()}),
        **{
            name: component[name]
            for name in ("synthetic", "elemental_verification")
            if name in component
        },
        "identifiers": dict(component.get("identifiers", {})),
        "amount_basis": "mol",
        "charge": 0,
        "molar_mass": mass,
        "elements": component["elemental_composition"],
        **mapped,
        VOLATILE: dict(volatile),
    }
    if defaults is not None:
        return identify(record, registry=registry)
    return _unprovenanced(record)


def _unprovenanced(record: Mapping[str, Any]) -> RecordOutcome:
    """D2 steps 1 to 5 on a v1 record built without `defaults`, refused
    `provenance_invalid(<entry>)` for each of its Constants and entries (no SHA)."""
    normalized = normalize(record)
    found = [Coded("provenance_invalid", {"entry": at}) for at, _ in quantities(normalized.record)]
    errors = tuple(sorted([*normalized.errors, *found], key=Coded.sort_key))
    return RecordOutcome(normalized.record, normalized.volatile, None, errors, normalized.findings)


def _parameters(
    classifier: legacy.Classifier, parameters: Mapping[str, Any], where: str
) -> dict[str, list[dict[str, Any]]]:
    """A v1 component's `parameters` by name: D12's parameter rows for the names it maps (a
    correlation's coefficients all or none, the `ideal_gas_cp` bounds both or none and only with
    its coefficients: else `LegacyImportError`), every other name a constant entry
    `user.<name>`."""
    names = set(parameters)
    entries = [
        legacy.constant_entry(classifier, name, name, parameters[name], f"{where}/{name}")
        for name in legacy.CRITICAL
        if name in names
    ]
    if names & (_CP_NAMES | _BOUNDS):
        _all_of(names, _CP_NAMES, where)
        validity = None
        if names & _BOUNDS:
            _all_of(names, _BOUNDS, where)
            bounds = [
                legacy.number(parameters[name], "K", "temperature", f"{where}/{name}")
                for name in legacy.CP_BOUNDS
            ]
            validity = {"T": bounds}
        entries.append(
            legacy.correlation_entry(classifier, legacy.CP, parameters, where, validity=validity)
        )
    if names & _PSAT_NAMES:
        _all_of(names, _PSAT_NAMES, where)
        entries.append(
            legacy.correlation_entry(classifier, legacy.PSAT, parameters, where, validity=None)
        )
    entries += [
        legacy.constant_entry(classifier, f"user.{name}", name, parameter, f"{where}/{name}")
        for name, parameter in parameters.items()
        if name not in MAPPED
    ]
    mapped: dict[str, list[dict[str, Any]]] = {"entries": entries}
    if legacy.FORMATION in names:
        mapped["formation"] = legacy.formation(classifier, parameters, where)
    return mapped


def _all_of(names: set[str], group: frozenset[str], where: str) -> None:
    """`LegacyImportError` unless `names` holds every name of `group`."""
    missing = sorted(group - names)
    if missing:
        raise LegacyImportError(f"{where}: missing {missing}")
