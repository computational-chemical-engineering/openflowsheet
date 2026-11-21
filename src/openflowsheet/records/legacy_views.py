"""Loader views over imported legacy records (ADR 0061 D12, the R18 adapter), F3-WO3.

Each view rebuilds a legacy loader's frozen dataclass from v2 records (normalised identity
projections, as the legacy import or a store gives them), so a provider that reads
`pr_c1.C1Records`, `pr_lib.LibraryRecords` or `wilson_ig.WilsonRecords` can be built from
records; E-F3-1 holds each view equal to its loader field by field. No legacy module changes:
the views construct the loaders' dataclasses, with every float as the record holds it.
`legacy_path_for` serves the constructors that take a path only.

The records of one view are one legacy file's, in any order; they are put in file order by
`legacy.position`. A view refuses (`ValueError`) records of several files, a missing or repeated
position, or a parameter set whose components are not the given records.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from openflowsheet.records.identity import record_sha256
from openflowsheet.records.importers.legacy import committed_index
from openflowsheet.thermo import pr_c1, pr_lib, wilson_ig

Record = Mapping[str, Any]


def c1_records(records: Iterable[Record]) -> pr_c1.C1Records:
    """`pr_c1.C1Records` from the imported `m01` component records."""
    ordered, sha = _file_order(records)
    return pr_c1.C1Records(
        components=tuple(pr_c1.C1Component(**_critical_fields(record)) for record in ordered),
        sha256=sha,
    )


def library_records(records: Iterable[Record]) -> pr_lib.LibraryRecords:
    """`pr_lib.LibraryRecords` from the imported `l01` component records."""
    ordered, sha = _file_order(records)
    return pr_lib.LibraryRecords(
        components=tuple(pr_lib.LibraryComponent(**_critical_fields(record)) for record in ordered),
        sha256=sha,
    )


def wilson_records(components: Iterable[Record], parameter_set: Record) -> wilson_ig.WilsonRecords:
    """`wilson_ig.WilsonRecords` from the imported `s10` (or `s10-verification`) component
    records and the file's parameter set: Λ in component position order with Λ_ii = 1.0, the
    domains from the set's validity, `reference_convention` and `data_provenance` from its
    `legacy.file_fields`, `sha256` the file's `file_sha256`."""
    ordered, sha = _file_order(components)
    if parameter_set["legacy"]["file_sha256"] != sha:
        raise ValueError("the parameter set is not of the components' file")
    ids = tuple(record["id"] for record in ordered)
    _check_matched(parameter_set, ordered)
    fields = parameter_set["legacy"]["file_fields"]
    validity = parameter_set["validity"]
    return wilson_ig.WilsonRecords(
        components=ids,
        cp=tuple(_cp(record) for record in ordered),
        formation_enthalpy=tuple(_formation_h(record) for record in ordered),
        vapour_pressure=tuple(_psat(record) for record in ordered),
        wilson_lambda=_lambda(parameter_set, ids),
        temperature_domain=_pair(validity["T"]),
        pressure_domain=_pair(validity["P"]),
        reference_convention=fields["reference_convention"],
        synthetic=parameter_set["synthetic"],
        data_set=parameter_set["data_set"],
        uncertainty=parameter_set["uncertainty_statement"],
        data_provenance=fields["data_provenance"],
        sha256=sha,
    )


def legacy_path_for(records: Iterable[Record]) -> str:
    """The packaged path of the legacy file whose indexed records are exactly `records` (by
    SHA, in any order); `ValueError` when they are not one file's whole set."""
    shas = sorted(record_sha256(record) for record in records)
    for entry in committed_index()["files"]:
        if sorted(record["sha256"] for record in entry["records"]) == shas:
            return str(entry["path"])
    raise ValueError("the records are not exactly one legacy file's indexed records")


def _file_order(records: Iterable[Record]) -> tuple[list[Record], str]:
    """`records` in `legacy.position` order, and their one `file_sha256`; `ValueError` unless
    they are of one file with positions 0 to n - 1."""
    listed = list(records)
    files = {record["legacy"]["file_sha256"] for record in listed}
    if len(files) != 1:
        raise ValueError(f"the records are of {len(files)} legacy files, not one")
    ordered = sorted(listed, key=lambda record: record["legacy"]["position"])
    if [record["legacy"]["position"] for record in ordered] != list(range(len(ordered))):
        raise ValueError("the records' positions are not 0 to n - 1")
    return ordered, files.pop()


def _critical_fields(record: Record) -> dict[str, Any]:
    """The fields `pr_c1.C1Component` and `pr_lib.LibraryComponent` share, from a `critical`
    profile's component record."""
    entries = _entries(record)
    cp = entries["ideal_gas_cp"]
    return {
        "id": record["id"],
        "name": record["name"],
        "molar_mass": float(record["molar_mass"]["value"]),
        "critical_temperature": float(entries["critical_temperature"]["value"]),
        "critical_pressure": float(entries["critical_pressure"]["value"]),
        "acentric_factor": float(entries["acentric_factor"]["value"]),
        "formation_enthalpy": _formation_h(record),
        "cp_coefficients": _cp(record),
        "cp_temperature_range": _pair(cp["validity"]["T"]),
        "elemental_composition": dict(record["elements"]),
    }


def _entries(record: Record) -> dict[str, Record]:
    """A component's entries by property (each property once: the profiles state no phase
    twice)."""
    return {entry["property"]: entry for entry in record["entries"]}


def _cp(record: Record) -> tuple[float, float, float, float, float]:
    """b_0 to b_4 of the `ideal_gas_cp` entry."""
    b = _entries(record)["ideal_gas_cp"]["coefficients"]
    return float(b["b0"]), float(b["b1"]), float(b["b2"]), float(b["b3"]), float(b["b4"])


def _psat(record: Record) -> tuple[float, float, float, float]:
    """a, b, c and d of the `vapour_pressure` entry."""
    c = _entries(record)["vapour_pressure"]["coefficients"]
    return float(c["a"]), float(c["b"]), float(c["c"]), float(c["d"])


def _formation_h(record: Record) -> float:
    """Δf h° of the `ig` formation entry."""
    (found,) = [item for item in record["formation"] if item["phase"] == "ig"]
    return float(found["h"]["value"])


def _pair(bounds: Iterable[Any]) -> tuple[float, float]:
    lo, hi = bounds
    return float(lo), float(hi)


def _check_matched(parameter_set: Record, ordered: list[Record]) -> None:
    """`ValueError` unless the set's components are the records, by key and SHA."""
    matched = {item["key"]: item["match"].get("record") for item in parameter_set["components"]}
    given = {record["id"]: record_sha256(record) for record in ordered}
    if matched != given:
        raise ValueError("the parameter set's components are not the given records")


def _lambda(parameter_set: Record, ids: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
    """Λ[i][j] in `ids` order from the set's `wilson_lambda` entries; Λ_ii = 1.0 (implied)."""
    values = {
        tuple(entry["indices"]): float(entry["value"])
        for entry in parameter_set["entries"]
        if entry["property"] == "wilson_lambda"
    }
    return tuple(tuple(1.0 if i == j else values[(i, j)] for j in ids) for i in ids)
