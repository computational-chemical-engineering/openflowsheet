"""The C1 component records: the five real components of the ammonia synthesis loop (M01 spec §3).

**The records are data, read at run time, never transcribed into code.**
`benchmarks/m01/components.yaml` holds the five ComponentRecords (H2, N2, NH3, Ar, CH4, in that
order: the identity order of every n-vector), each value with its primary reference (spec §3.1,
ADR 0026 D5). The package carries the
file's bytes as package data (`openflowsheet.resources`), so a checkout and an installed wheel read
the same records; `data_sha256` is the SHA-256 of exactly those bytes (M01.A03).

**Typed, and checked when read.** `load_records` parses the file into `C1Component`s and refuses a
file whose component order, units or reference convention are not the registered ones, because a
permuted or re-unitted record would otherwise become a plausible wrong number. The values are the
parsed floats unchanged (M01.A03: bitwise).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any, Final

import yaml

from openflowsheet.resources import packaged

#: The records' repository path, one of `openflowsheet.resources.PACKAGED`.
RECORDS_PATH: Final = "benchmarks/m01/components.yaml"

#: The identity order of every C1 n-vector (spec §3.1).
COMPONENTS: Final[tuple[str, ...]] = ("H2", "N2", "NH3", "Ar", "CH4")

#: The reference convention the records' formation enthalpies define (spec §6, ADR 0026 D4).
REFERENCE_CONVENTION: Final = "PR-C1-ref-v1"

#: Parameter name -> the unit the record must state. `ideal_gas_cp_b<k>` are dimensionless:
#: c_p^ig/R = sum_k b_k (T / 1000 K)^k (spec §3.1).
_UNITS: Final[Mapping[str, str]] = {
    "critical_temperature": "K",
    "critical_pressure": "Pa",
    "acentric_factor": "1",
    "standard_formation_enthalpy": "J/mol",
    **{f"ideal_gas_cp_b{k}": "1" for k in range(5)},
    "ideal_gas_cp_lower_temperature": "K",
    "ideal_gas_cp_upper_temperature": "K",
}


@dataclass(frozen=True)
class C1Component:
    """One C1 component record, as the provider reads it. SI throughout."""

    id: str
    name: str
    #: kg/mol, the only route to a mass basis (ADR 0001 D1.4).
    molar_mass: float
    #: K, Pa and the Pitzer acentric factor of the component's reference equation of state.
    critical_temperature: float
    critical_pressure: float
    acentric_factor: float
    #: J/mol, ideal gas at 298.15 K: the `PR-C1-ref-v1` datum (spec §6).
    formation_enthalpy: float
    #: b_0..b_4 of c_p^ig/R = sum_k b_k (T / 1000 K)^k (NASA TM-4513 low range, spec §3.1).
    cp_coefficients: tuple[float, float, float, float, float]
    #: K, the c_p fit's validity range as recorded.
    cp_temperature_range: tuple[float, float]
    elemental_composition: Mapping[str, int]


@dataclass(frozen=True)
class C1Records:
    """The five records in `COMPONENTS` order, and the SHA-256 of the bytes they were read from."""

    components: tuple[C1Component, ...]
    sha256: str


def _value(quantity: Mapping[str, Any], unit: str, where: str) -> float:
    if quantity.get("unit") != unit:
        raise ValueError(f"{where}: unit {quantity.get('unit')!r}, the record must state {unit!r}")
    value = quantity["value"]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{where}: value {value!r} is not a number")
    return float(value)


def _component(record: Mapping[str, Any]) -> C1Component:
    cid = record["id"]
    parameters = record["parameters"]
    if set(parameters) != set(_UNITS):
        raise ValueError(f"{cid}: parameters {sorted(parameters)} are not {sorted(_UNITS)}")
    value = {name: _value(parameters[name], unit, f"{cid}.{name}") for name, unit in _UNITS.items()}
    b0, b1, b2, b3, b4 = (value[f"ideal_gas_cp_b{k}"] for k in range(5))
    return C1Component(
        id=cid,
        name=record["name"],
        molar_mass=_value(record["molecular_weight"], "kg/mol", f"{cid}.molecular_weight"),
        critical_temperature=value["critical_temperature"],
        critical_pressure=value["critical_pressure"],
        acentric_factor=value["acentric_factor"],
        formation_enthalpy=value["standard_formation_enthalpy"],
        cp_coefficients=(b0, b1, b2, b3, b4),
        cp_temperature_range=(
            value["ideal_gas_cp_lower_temperature"],
            value["ideal_gas_cp_upper_temperature"],
        ),
        elemental_composition=dict(record["elemental_composition"]),
    )


def parse_records(data: bytes) -> C1Records:
    """The records in `data` (the bytes of a `components.yaml`), checked and typed."""
    document = yaml.safe_load(data.decode("utf-8"))
    if document.get("reference_convention") != REFERENCE_CONVENTION:
        raise ValueError(
            f"reference_convention {document.get('reference_convention')!r} is not "
            f"{REFERENCE_CONVENTION!r}"
        )
    components = tuple(_component(record) for record in document["components"])
    if tuple(component.id for component in components) != COMPONENTS:
        raise ValueError(
            f"component order {[c.id for c in components]} is not the registered {list(COMPONENTS)}"
        )
    return C1Records(components=components, sha256=hashlib.sha256(data).hexdigest())


@cache
def load_records() -> C1Records:
    """The packaged C1 records (read once per process; the file is package data, not state)."""
    return parse_records(packaged(RECORDS_PATH).read_bytes())
