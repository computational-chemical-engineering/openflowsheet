"""The legacy importer (ADR 0061 D12; the `data_source` `legacy-yaml` 1.0.0), F3-WO3.

One profile per v1 record file (`records/legacy_profiles.yaml`): the seven files give 147
component records and 2 parameter sets. D12's mapping is a closed table, so a v1 key it neither
maps nor drops, in any file, is a `LegacyImportError`, and every record passes D2 (`identify`)
or the import fails. The files are read, never edited; their loaders (`pr_c1`, `pr_lib`,
`wilson_ig`) are untouched, and `records.legacy_views` rebuilds their dataclasses from the
imported records.

The committed **legacy index** (`records/legacy_index.json`, written by
`scripts/records_legacy_index.py`) pins each file's SHA-256, each record's SHA and its findings.
`available_records` is the legacy store's loader (`records.stack.LegacyStore`): it imports the
profiled files available here (package data, or a source checkout) and refuses a file whose
bytes or records differ from the index `legacy_record_drift(<file>, <id>)`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from itertools import zip_longest
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import yaml

from openflowsheet import resources
from openflowsheet.records.identity import identify
from openflowsheet.records.model import RECORD_FORMAT, RECORD_TYPES, RecordOutcome
from openflowsheet.records.store import RecordStoreError
from openflowsheet.records.validate import identifier_ok
from openflowsheet.registry.selfhash import lf
from openflowsheet.registry.tokens import Coded

if TYPE_CHECKING:
    from openflowsheet.registry import Registry

PROFILES_FORMAT: Final = "openflowsheet-legacy-profiles-v1"
INDEX_FORMAT: Final = "openflowsheet-legacy-record-index-v1"
PROFILES_NAME: Final = "legacy_profiles.yaml"
INDEX_NAME: Final = "legacy_index.json"
#: D12: the v1 envelope, dropped; `record_schema` selects the files `--check` requires profiled.
V1_SCHEMA_VERSION: Final = 1
V1_RECORD_SCHEMA: Final = "schemas/component-record.schema.json"

#: D12's closed table, file level: the keys of every file, and those of a `wilson` file's set.
_FILE_KEYS: Final = frozenset(
    {"schema_version", "record_schema", "reference_convention", "components"}
)
_SET_FILE_KEYS: Final = frozenset(
    {"data_set", "synthetic", "uncertainty", "domain", "data_provenance", "wilson_lambda"}
)
#: D12's closed table, component level (`identifiers` optional, the rest required).
_COMPONENT_KEYS: Final = frozenset(
    {
        "id",
        "name",
        "synthetic",
        "molecular_weight",
        "elemental_composition",
        "elemental_verification",
        "parameters",
        "rights",
    }
)
_IDENTIFIER_KEYS: Final = frozenset({"cas", "inchi", "inchikey", "formula"})
#: The identifier schemes D3 reads, the only ones a profile may drop (F3 ruling round 1 B3).
_CHECKED_SCHEMES: Final = frozenset({"cas", "inchikey"})
_RIGHTS_KEYS: Final = frozenset({"source", "redistribution", "notes"})
#: D12: a parameter's keys; `dimension` and `role` (always `fixed`) are dropped.
_PARAMETER_KEYS: Final = frozenset(
    {"value", "unit", "dimension", "kind", "meaning", "role", "provenance"}
)
_LAMBDA_KEYS: Final = frozenset({"i", "j", "value", "provenance"})

#: D4's correlation coefficients by form, each with the v1 parameter it is read from.
_CP_COEFFICIENTS: Final = {f"b{k}": f"ideal_gas_cp_b{k}" for k in range(5)}
_PSAT_COEFFICIENTS: Final = {name: f"vapour_pressure_{name}" for name in "abcd"}
_CP_BOUNDS: Final = ("ideal_gas_cp_lower_temperature", "ideal_gas_cp_upper_temperature")
_CRITICAL: Final = ("critical_temperature", "critical_pressure", "acentric_factor")
_FORMATION: Final = "standard_formation_enthalpy"


class LegacyImportError(ValueError):
    """A legacy file off D12's closed mapping, or a record D2 refuses: the message says where."""


@dataclass(frozen=True)
class Profile:
    """One `legacy_profiles.yaml` profile: its file, source id, the file's citation (F3 decision
    WO4-0), D12 parameter rule (`mapping`), provenance classification by field, and the
    identifiers it drops by component id (F3 decision WO3-2: a v1 `cas` or `inchikey` D3
    refuses, ruling round 1 B3)."""

    profile: str
    file: str
    source: str
    citation: str
    mapping: str
    provenance: Mapping[str, Mapping[str, Any]]
    dropped_identifiers: Mapping[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportedFile:
    """One imported file: its D12 SHA-256 (of the LF-normalised bytes), its
    `reference_convention` (`None` when it states none), its records' D2 outcomes, the
    components in file order and then the parameter set, if the file has one, and the v1
    `rights.redistribution` text its components share (not identity: D11's seed row reads it)."""

    profile: str
    path: str
    file_sha256: str
    reference_convention: str | None
    records: tuple[RecordOutcome, ...]
    redistribution: str

    def projections(self) -> list[Mapping[str, Any]]:
        """The records' normalised identity projections, in `records` order."""
        return [outcome.record for outcome in self.records]


@cache
def profiles() -> tuple[Profile, ...]:
    """The profiles of `records/legacy_profiles.yaml` (package data), in file order."""
    text = files("openflowsheet.records").joinpath(PROFILES_NAME).read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    if document.get("profiles_format") != PROFILES_FORMAT:
        raise LegacyImportError(f"{PROFILES_NAME}: profiles_format is not {PROFILES_FORMAT}")
    return tuple(Profile(**entry) for entry in document["profiles"])


def profile_named(name: str) -> Profile:
    """The profile `name`; `KeyError` when there is none."""
    for found in profiles():
        if found.profile == name:
            return found
    raise KeyError(name)


def file_sha256(data: bytes) -> str:
    """D12's `file_sha256`: the SHA-256 of the LF-normalised bytes."""
    return hashlib.sha256(lf(data)).hexdigest()


def import_file(profile: Profile, data: bytes, *, registry: Registry | None = None) -> ImportedFile:
    """D12 on the bytes of `profile`'s file: every component, then the parameter set of a
    `wilson` file (matched to the components by their SHAs), each through D2 against `registry`
    (the process registry when `None`). Raises `LegacyImportError` for a key D12 does not
    map, a parameter the profile does not list, or a record D2 refuses."""
    document = yaml.safe_load(data.decode("utf-8"))
    context = _File(profile, file_sha256(data))
    _check_envelope(document, profile)
    components = tuple(
        _identified(_component(context, record, position), registry)
        for position, record in enumerate(document["components"])
    )
    records = components
    if profile.mapping == "wilson":
        records += (_identified(_parameter_set(context, document, components), registry),)
    return ImportedFile(
        profile.profile,
        profile.file,
        context.file_sha256,
        document.get("reference_convention"),
        records,
        _redistribution(document["components"], profile.file),
    )


def _redistribution(components: Iterable[Mapping[str, Any]], where: str) -> str:
    """The one v1 `rights.redistribution` text of a file's components (D11 seeds one row per
    legacy source); `LegacyImportError` when they state several."""
    texts = {component["rights"]["redistribution"] for component in components}
    if len(texts) != 1:
        raise LegacyImportError(f"{where}: the components state {len(texts)} redistribution texts")
    return str(texts.pop())


def _check_envelope(document: Mapping[str, Any], profile: Profile) -> None:
    """D12's file row: the keys of the profile's mapping, a v1 envelope."""
    allowed = _FILE_KEYS | (_SET_FILE_KEYS if profile.mapping == "wilson" else frozenset())
    _known(document, allowed, profile.file)
    if document.get("schema_version") != V1_SCHEMA_VERSION:
        raise LegacyImportError(f"{profile.file}: schema_version is not {V1_SCHEMA_VERSION}")
    if document.get("record_schema") != V1_RECORD_SCHEMA:
        raise LegacyImportError(f"{profile.file}: record_schema is not {V1_RECORD_SCHEMA}")


def _known(mapping: object, allowed: frozenset[str], where: str) -> None:
    """`LegacyImportError` unless `mapping` is a mapping whose keys are all in `allowed`."""
    if not isinstance(mapping, Mapping):
        raise LegacyImportError(f"{where} is not a mapping")
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise LegacyImportError(f"{where}: keys {unknown} are not in D12's mapping table")


def _identified(record: Mapping[str, Any], registry: Registry | None) -> RecordOutcome:
    """D2 on one built record; `LegacyImportError` with its codes when D2 refuses it."""
    outcome = identify(record, registry=registry)
    if outcome.refused:
        codes = [error.as_document() for error in outcome.errors]
        raise LegacyImportError(f"{record['legacy']['file']}: {record['id']} is refused {codes}")
    return outcome


@dataclass(frozen=True)
class _File:
    """What every record of one file shares: its profile and `file_sha256`."""

    profile: Profile
    file_sha256: str

    def envelope(self, record_type: str, ident: str, name: str) -> dict[str, Any]:
        """D1's envelope members of a record of this file, without `sources` and `legacy`."""
        return {
            "record_format": RECORD_FORMAT,
            "record_type": record_type,
            "type_version": RECORD_TYPES[record_type].version,
            "id": ident,
            "name": name,
        }

    def sources(self) -> dict[str, Any]:
        """D1's `sources` member of every record of this file, its components' and its parameter
        set's alike (F3 decisions WO4-0, WO3-5 as ruled in F3 ruling round 1: one `source_sha256`
        per legacy source): the profile's source id with `version` the `file_sha256`, the
        profile's `citation`, `licence_stated` and `url` null."""
        entry = {
            "version": self.file_sha256,
            "citation": self.profile.citation,
            "licence_stated": None,
            "url": None,
        }
        return {self.profile.source: entry}

    def legacy(self, position: int | None, file_fields: Mapping[str, Any] | None) -> dict[str, Any]:
        """D12's `legacy` member."""
        return {
            "profile": self.profile.profile,
            "file": self.profile.file,
            "file_sha256": self.file_sha256,
            "position": position,
            "file_fields": file_fields,
        }

    def provenance(self, field: str) -> dict[str, Any]:
        """D12's classification of `field` (the profile's row): origin, derivation and inputs,
        this file's source, `transformation` null. `LegacyImportError` when the profile has no
        row for it."""
        row = self.profile.provenance.get(field)
        if row is None:
            raise LegacyImportError(f"profile {self.profile.profile} classifies no {field}")
        return {
            "origin": list(row["origin"]),
            "derivation": row["derivation"],
            "source": self.profile.source,
            "inputs": [dict(item) for item in row.get("inputs", ())],
            "transformation": None,
        }


# -- a component (D12's component rows) ---------------------------------------------------------


def _component(context: _File, record: Mapping[str, Any], position: int) -> dict[str, Any]:
    """D12's component rows on the v1 record at `position`: `amount_basis` `mol`, `charge` 0,
    the file's `sources` entry (F3 decision WO4-0: one citation per file, so one `source_sha256`
    per legacy source), the molar mass a Constant whose `note` ends with the component's v1
    `rights.source`, and the entries and formation of the profile's mapping."""
    where = f"{context.profile.file}: components[{position}]"
    _known(record, _COMPONENT_KEYS | {"identifiers"}, where)
    identifiers = _identifiers(context.profile, record, f"{where}.identifiers")
    _known(record["rights"], _RIGHTS_KEYS, f"{where}.rights")
    return {
        **context.envelope("component", record["id"], record["name"]),
        "sources": context.sources(),
        "legacy": context.legacy(position, None),
        "synthetic": record["synthetic"],
        "identifiers": identifiers,
        "amount_basis": "mol",
        "charge": 0,
        "molar_mass": _molar_mass(context, record, where),
        "elements": record["elemental_composition"],
        "elemental_verification": record["elemental_verification"],
        **_MAPPINGS[context.profile.mapping](context, record["parameters"], where),
    }


def _identifiers(profile: Profile, record: Mapping[str, Any], where: str) -> dict[str, Any]:
    """D12: the v1 identifiers copied, less those the profile drops for this component, each of
    which must be stated and be one D3 refuses: a `cas` or `inchikey` whose stated value fails
    `validate.identifier_ok` (F3 decision WO3-2, F3 ruling round 1 B3)."""
    identifiers = record.get("identifiers", {})
    _known(identifiers, _IDENTIFIER_KEYS, where)
    dropped = set(profile.dropped_identifiers.get(record["id"], ()))
    if not dropped <= set(identifiers):
        raise LegacyImportError(f"{where}: dropped identifiers {sorted(dropped)} are not stated")
    kept = sorted(
        scheme
        for scheme in dropped
        if scheme not in _CHECKED_SCHEMES or identifier_ok(identifiers, scheme)
    )
    if kept:
        raise LegacyImportError(f"{where}: dropped identifiers {kept} are not ones D3 refuses")
    return {scheme: value for scheme, value in identifiers.items() if scheme not in dropped}


def _molar_mass(context: _File, record: Mapping[str, Any], where: str) -> dict[str, Any]:
    """The Constant of `molecular_weight`, its `note` ending with the component's v1
    `rights.source` (F3 decision WO4-0)."""
    constant = _constant(context, "molar_mass", record["molecular_weight"], where)
    constant["note"] = _note([record["molecular_weight"]], record["rights"]["source"])
    return constant


def _constant(
    context: _File, field: str, parameter: Mapping[str, Any], where: str
) -> dict[str, Any]:
    """A Constant from one v1 parameter (D12's parameter rows): `value`, `unit`, `kind`,
    `meaning`, the provenance text as `note`, `uncertainty` null."""
    _parameter(parameter, where)
    return {
        "value": parameter["value"],
        "unit": parameter["unit"],
        "kind": parameter["kind"],
        "uncertainty": None,
        "provenance": context.provenance(field),
        "meaning": parameter.get("meaning"),
        "note": _note([parameter]),
    }


def _parameter(parameter: object, where: str) -> None:
    """`LegacyImportError` unless `parameter` has D12's parameter keys only, with `value`,
    `unit` and `kind`, and `role` `fixed` when stated."""
    _known(parameter, _PARAMETER_KEYS, where)
    assert isinstance(parameter, Mapping)
    missing = sorted({"value", "unit", "kind"} - set(parameter))
    if missing:
        raise LegacyImportError(f"{where}: missing {missing}")
    if parameter.get("role", "fixed") != "fixed":
        raise LegacyImportError(f"{where}: role {parameter['role']!r} is not fixed")


def _note(parameters: Iterable[Mapping[str, Any]], *more: str) -> str | None:
    """D12's `note`: the distinct provenance texts of `parameters`, in their order, then the
    distinct texts of `more` (F3 decision WO4-0: a component's `rights.source`), joined by a
    newline; `None` when there is none."""
    texts = dict.fromkeys([*(p["provenance"] for p in parameters if "provenance" in p), *more])
    return "\n".join(texts) if texts else None


def _namespaced(
    context: _File, parameters: Mapping[str, Any], where: str
) -> dict[str, list[dict[str, Any]]]:
    """D12 `syn001`: each parameter `p` a constant entry `<profile>.p`, phase null."""
    if not isinstance(parameters, Mapping):
        raise LegacyImportError(f"{where}.parameters is not a mapping")
    entries = [
        _constant_entry(
            context, f"{context.profile.profile}.{name}", "parameters", parameter, f"{where}.{name}"
        )
        for name, parameter in parameters.items()
    ]
    return {"entries": entries}


def _critical(
    context: _File, parameters: Mapping[str, Any], where: str
) -> dict[str, list[dict[str, Any]]]:
    """D12 `m01`, `l01`: Tc, Pc and the acentric factor constant entries; `ideal_gas_cp` with
    validity `{T: [lower, upper]}`; formation `ig`."""
    _exactly(parameters, {*_CRITICAL, *_CP_COEFFICIENTS.values(), *_CP_BOUNDS, _FORMATION}, where)
    entries = [
        _constant_entry(context, name, name, parameters[name], f"{where}.{name}")
        for name in _CRITICAL
    ]
    bounds = [
        _number(parameters[name], "K", "temperature", f"{where}.{name}") for name in _CP_BOUNDS
    ]
    entries.append(_correlation_entry(context, _CP, parameters, where, validity={"T": bounds}))
    return {"entries": entries, "formation": _formation(context, parameters, where)}


def _wilson(
    context: _File, parameters: Mapping[str, Any], where: str
) -> dict[str, list[dict[str, Any]]]:
    """D12 `s10`, `s10-verification`: `ideal_gas_cp` (validity null), `vapour_pressure`,
    formation `ig`."""
    _exactly(
        parameters, {*_CP_COEFFICIENTS.values(), *_PSAT_COEFFICIENTS.values(), _FORMATION}, where
    )
    entries = [
        _correlation_entry(context, _CP, parameters, where, validity=None),
        _correlation_entry(context, _PSAT, parameters, where, validity=None),
    ]
    return {"entries": entries, "formation": _formation(context, parameters, where)}


def _none(
    context: _File, parameters: Mapping[str, Any], where: str
) -> dict[str, list[dict[str, Any]]]:
    """D12 `s05`, `s07`: no parameters."""
    _exactly(parameters, set(), where)
    return {}


def _exactly(parameters: object, names: set[str], where: str) -> None:
    """`LegacyImportError` unless `parameters` names exactly `names` (a parameter the profile
    does not list, or one of its group missing, fails)."""
    _known(parameters, frozenset(names), f"{where}.parameters")
    assert isinstance(parameters, Mapping)
    missing = sorted(names - set(parameters))
    if missing:
        raise LegacyImportError(f"{where}.parameters: missing {missing}")


def _constant_entry(
    context: _File, prop: str, field: str, parameter: Mapping[str, Any], where: str
) -> dict[str, Any]:
    """A constant entry of property `prop` from one parameter, classified as `field`."""
    return {
        "property": prop,
        "phase": None,
        "form": "constant",
        "validity": None,
        **_constant(context, field, parameter, where),
    }


@dataclass(frozen=True)
class _Correlation:
    """A core property built from several parameters: its form, phase and coefficients."""

    property: str
    form: str
    phase: str
    coefficients: Mapping[str, str]


_CP: Final = _Correlation("ideal_gas_cp", "cp_ig_poly4_theta", "ig", _CP_COEFFICIENTS)
_PSAT: Final = _Correlation("vapour_pressure", "ln_psat_abcd_theta", "l", _PSAT_COEFFICIENTS)


def _correlation_entry(
    context: _File,
    correlation: _Correlation,
    parameters: Mapping[str, Any],
    where: str,
    *,
    validity: Mapping[str, list[float]] | None,
) -> dict[str, Any]:
    """An entry merged from several parameters: each coefficient the value of its dimensionless
    parameter; `meaning` null; `note` the distinct provenance texts of the parameters it is
    built from (the coefficients, and the validity bounds of `ideal_gas_cp`) in file order."""
    coefficients = {
        name: _number(parameters[source], "1", "dimensionless", f"{where}.{source}")
        for name, source in correlation.coefficients.items()
    }
    used = {*correlation.coefficients.values(), *(_CP_BOUNDS if validity else ())}
    return {
        "property": correlation.property,
        "phase": correlation.phase,
        "form": correlation.form,
        "coefficients": coefficients,
        "validity": validity,
        "uncertainty": None,
        "provenance": context.provenance(correlation.property),
        "meaning": None,
        "note": _note(parameters[name] for name in parameters if name in used),
    }


def _number(parameter: object, unit: str, kind: str, where: str) -> Any:
    """The value of a parameter that must state `unit` and `kind` (a coefficient, a bound)."""
    _parameter(parameter, where)
    assert isinstance(parameter, Mapping)
    if parameter["unit"] != unit or parameter["kind"] != kind:
        raise LegacyImportError(f"{where}: unit and kind are not {unit!r}, {kind!r}")
    return parameter["value"]


def _formation(context: _File, parameters: Mapping[str, Any], where: str) -> list[dict[str, Any]]:
    """D12: `standard_formation_enthalpy` as formation `ig`, `s` null."""
    h = _constant(context, "formation", parameters[_FORMATION], f"{where}.{_FORMATION}")
    return [{"phase": "ig", "h": h, "s": None}]


_MAPPINGS: Final[
    Mapping[str, Callable[[_File, Mapping[str, Any], str], dict[str, list[dict[str, Any]]]]]
] = {"namespaced": _namespaced, "critical": _critical, "wilson": _wilson, "none": _none}


# -- the parameter set (D12's `wilson_lambda` row) ----------------------------------------------


def _parameter_set(
    context: _File, document: Mapping[str, Any], components: tuple[RecordOutcome, ...]
) -> dict[str, Any]:
    """D12: the file's `wilson_lambda` as one `parameter_set`, id and name its `data_set`, the
    `sources` entry of its components (one per legacy source), its components matched by the
    component records' SHAs, `validity` from `domain`, `synthetic`
    and `data_set` from the file, `uncertainty_statement` from `uncertainty`, and
    `legacy.file_fields` `{reference_convention, data_provenance}`."""
    file_fields = {
        "reference_convention": document["reference_convention"],
        "data_provenance": document["data_provenance"],
    }
    where = f"{context.profile.file}: wilson_lambda"
    return {
        **context.envelope("parameter_set", document["data_set"], document["data_set"]),
        "sources": context.sources(),
        "legacy": context.legacy(None, file_fields),
        "uncertainty_statement": document["uncertainty"],
        "components": [
            {"key": outcome.record["id"], "match": {"record": outcome.record_sha256}}
            for outcome in components
        ],
        "entries": [
            _lambda_entry(context, entry, f"{where}[{n}]")
            for n, entry in enumerate(document["wilson_lambda"])
        ],
        "validity": {name: list(bounds) for name, bounds in document["domain"].items()},
        "synthetic": document["synthetic"],
        "data_set": document["data_set"],
    }


def _lambda_entry(context: _File, entry: Mapping[str, Any], where: str) -> dict[str, Any]:
    """D12: `i`, `j`, `value`, `provenance` → entry `indices: [i, j]`, `value`, `note`;
    `meaning` null; D4's `wilson_lambda` is dimensionless."""
    _known(entry, _LAMBDA_KEYS, where)
    return {
        "property": "wilson_lambda",
        "phase": None,
        "form": "constant",
        "value": entry["value"],
        "unit": "1",
        "kind": "dimensionless",
        "indices": [entry["i"], entry["j"]],
        "validity": None,
        "uncertainty": None,
        "provenance": context.provenance("wilson_lambda"),
        "meaning": None,
        "note": _note([entry]),
    }


# -- the legacy index (D12) ---------------------------------------------------------------------


def index_document(imported: Iterable[ImportedFile]) -> dict[str, Any]:
    """D12's legacy index of `imported`, files sorted by path (UTF-8): each record's type, id,
    position, SHA and findings (`{code, params}`, in D2's order)."""
    entries = sorted((_index_file(item) for item in imported), key=lambda f: f["path"].encode())
    return {"index_format": INDEX_FORMAT, "files": entries}


def _index_file(imported: ImportedFile) -> dict[str, Any]:
    return {
        "path": imported.path,
        "profile": imported.profile,
        "file_sha256": imported.file_sha256,
        "reference_convention": imported.reference_convention,
        "records": [
            {
                "record_type": outcome.record["record_type"],
                "id": outcome.record["id"],
                "position": outcome.record["legacy"].get("position"),
                "sha256": outcome.record_sha256,
                "findings": [finding.as_document() for finding in outcome.findings],
            }
            for outcome in imported.records
        ],
    }


def import_all(
    read: Callable[[str], bytes], *, registry: Registry | None = None
) -> list[ImportedFile]:
    """Every profile's file, read by `read(<repository path>)`, imported in profile order."""
    return [import_file(found, read(found.file), registry=registry) for found in profiles()]


@cache
def committed_index() -> Mapping[str, Any]:
    """The committed legacy index (`records/legacy_index.json`, package data)."""
    text = files("openflowsheet.records").joinpath(INDEX_NAME).read_text(encoding="utf-8")
    document: Mapping[str, Any] = json.loads(text)
    return document


# -- the legacy store's loader (D8, WO2-9) -----------------------------------------------------


def available_records() -> list[Mapping[str, Any]]:
    """The legacy store's loader: the identity projections of every indexed file available
    here (`available_bytes`), in index order. A file that is not available contributes nothing.
    Raises `RecordStoreError(legacy_record_drift(<file>, <id>))` for the first record whose
    file bytes or SHA differ from the committed index (the file's first record when its bytes
    differ)."""
    found: list[Mapping[str, Any]] = []
    for entry in committed_index()["files"]:
        data = available_bytes(entry["path"])
        if data is not None:
            found += _held(entry, data)
    return found


def available_bytes(path: str) -> bytes | None:
    """The bytes of the legacy file at repository path `path`: its packaged copy when the
    package carries it (`resources.PACKAGED`), else the source checkout's file; `None` when
    neither exists."""
    if path in resources.PACKAGED:
        copy = resources.packaged(path)
        if copy.is_file():
            return copy.read_bytes()
    root = _checkout_root()
    target = None if root is None else root.joinpath(*path.split("/"))
    return target.read_bytes() if target is not None and target.is_file() else None


def _checkout_root() -> Path | None:
    """The repository root when this module runs from a source checkout
    (`<root>/src/openflowsheet/records/importers/legacy.py`), else `None`."""
    here = Path(__file__).resolve()
    root = here.parents[4]
    return root if here.parents[2] == root / "src" / "openflowsheet" else None


def _held(entry: Mapping[str, Any], data: bytes) -> list[Mapping[str, Any]]:
    """The projections of the indexed file `entry` imported from `data`, checked against the
    index: its bytes first, then each record's id and SHA in index order."""
    indexed = entry["records"]
    if file_sha256(data) != entry["file_sha256"]:
        raise RecordStoreError(drift(entry["path"], indexed[0]["id"]))
    imported = import_file(profile_named(entry["profile"]), data)
    held = [(record["id"], record["sha256"]) for record in indexed]
    got = [(outcome.record["id"], outcome.record_sha256) for outcome in imported.records]
    for want, have in zip_longest(held, got):
        if want != have:
            raise RecordStoreError(drift(entry["path"], (want or have)[0]))
    return imported.projections()


def drift(path: str, ident: str) -> Coded:
    """`legacy_record_drift(<file>, <id>)`: a legacy file's record no longer has its indexed
    SHA (a bug: the files are byte-frozen and the index is regenerated with any importer
    change)."""
    return Coded("legacy_record_drift", {"file": path, "id": ident})
