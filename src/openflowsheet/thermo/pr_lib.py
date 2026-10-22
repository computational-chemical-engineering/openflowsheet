"""`pr-lib-v1`: the vapour-only Peng–Robinson library route — its records (L01 spec §4.1, ADR 0043).

**This module holds the route's record loader only** (WO-L01-1). The provider itself, PR 1976 with
ADR 0026's method and the vapour root rule of spec §4.2, is WO-L01-2's and is not here yet: nothing
in this module evaluates a property, and nothing outside tests constructs the route.

**The records are data, read at run time, never transcribed into code.**
`benchmarks/l01/components.yaml` holds nine ComponentRecords in the identity order of every
`pr-lib-v1` n-vector: H2, N2, Ar, CH4 (copied verbatim from C1's file, one datum per substance),
then H2O, CO2, O2, C2H6, C3H8, each value with its primary reference (spec §4.1, ADR 0043 D6). The
format, the units and the reference convention `PR-C1-ref-v1` are C1's (`benchmarks/m01/
components.yaml`, unchanged). The package carries the file's bytes as package data
(`openflowsheet.resources`), so a checkout and an installed wheel read the same records.
`load_records` refuses a file whose order, units or reference convention are off the registration,
with a `RecordError` naming the defect, and hands over the parsed floats unchanged (bitwise).
`data_sha256` will be the SHA-256 of the file's bytes, `implementation_sha256` that of this
module's source, which holds the loader as well as (from WO-L01-2) the closed forms.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

import yaml

from openflowsheet.resources import packaged

#: The records' repository path, one of `openflowsheet.resources.PACKAGED` (spec §4.1).
RECORDS_PATH: Final = "benchmarks/l01/components.yaml"

#: The identity order of every `pr-lib-v1` n-vector (spec §4.1, L01.A01).
COMPONENTS: Final[tuple[str, ...]] = (
    "H2",
    "N2",
    "Ar",
    "CH4",
    "H2O",
    "CO2",
    "O2",
    "C2H6",
    "C3H8",
)

#: The reference convention the records' formation enthalpies define, shared with `pr-c1-v1`
#: (ADR 0043 D4, ADR 0026 D4).
REFERENCE_CONVENTION: Final = "PR-C1-ref-v1"

#: Parameter name -> the unit the record must state. `ideal_gas_cp_b<k>` are dimensionless:
#: c_p^ig/R = sum_k b_k (T / 1000 K)^k (spec §4.1, C1's format).
_UNITS: Final[Mapping[str, str]] = {
    "critical_temperature": "K",
    "critical_pressure": "Pa",
    "acentric_factor": "1",
    "standard_formation_enthalpy": "J/mol",
    **{f"ideal_gas_cp_b{k}": "1" for k in range(5)},
    "ideal_gas_cp_lower_temperature": "K",
    "ideal_gas_cp_upper_temperature": "K",
}


class RecordError(ValueError):
    """A record file off the registration: the message names the defect and where it is."""


@dataclass(frozen=True)
class LibraryComponent:
    """One `pr-lib-v1` component record, as the route reads it. SI throughout."""

    id: str
    name: str
    #: kg/mol, the only route to a mass basis (ADR 0001 D1.4).
    molar_mass: float
    #: K, Pa and the Pitzer acentric factor of the component's reference equation of state.
    critical_temperature: float
    critical_pressure: float
    acentric_factor: float
    #: J/mol, ideal gas at 298.15 K: the `PR-C1-ref-v1` datum.
    formation_enthalpy: float
    #: b_0..b_4 of c_p^ig/R = sum_k b_k (T / 1000 K)^k (NASA TM-4513 low range).
    cp_coefficients: tuple[float, float, float, float, float]
    #: K, the c_p fit's validity range as recorded.
    cp_temperature_range: tuple[float, float]
    elemental_composition: Mapping[str, int]


@dataclass(frozen=True)
class LibraryRecords:
    """The nine records in `COMPONENTS` order, and the SHA-256 of the bytes they were read from."""

    components: tuple[LibraryComponent, ...]
    sha256: str


def _value(quantity: Mapping[str, Any], unit: str, where: str) -> float:
    if quantity.get("unit") != unit:
        raise RecordError(f"{where}: unit {quantity.get('unit')!r}, the record must state {unit!r}")
    value = quantity["value"]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RecordError(f"{where}: value {value!r} is not a number")
    return float(value)


def _component(record: Mapping[str, Any]) -> LibraryComponent:
    cid = record["id"]
    parameters = record["parameters"]
    if set(parameters) != set(_UNITS):
        raise RecordError(f"{cid}: parameters {sorted(parameters)} are not {sorted(_UNITS)}")
    value = {name: _value(parameters[name], unit, f"{cid}.{name}") for name, unit in _UNITS.items()}
    b0, b1, b2, b3, b4 = (value[f"ideal_gas_cp_b{k}"] for k in range(5))
    return LibraryComponent(
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


def parse_records(data: bytes) -> LibraryRecords:
    """The records in `data` (the bytes of the library's `components.yaml`), checked and typed."""
    document = yaml.safe_load(data.decode("utf-8"))
    if document.get("reference_convention") != REFERENCE_CONVENTION:
        raise RecordError(
            f"reference_convention {document.get('reference_convention')!r} is not "
            f"{REFERENCE_CONVENTION!r}"
        )
    ids = [record["id"] for record in document["components"]]
    if tuple(ids) != COMPONENTS:
        raise RecordError(f"component order {ids} is not the registered {list(COMPONENTS)}")
    components = tuple(_component(record) for record in document["components"])
    return LibraryRecords(components=components, sha256=hashlib.sha256(data).hexdigest())


def _checkout_records() -> Path | None:
    """The repository's single copy of the records when this module runs from a source checkout
    (`<root>/src/openflowsheet/thermo/pr_lib.py`), else `None`."""
    here = Path(__file__).resolve()
    root = here.parents[3]
    if here.parents[1] != root / "src" / "openflowsheet":
        return None
    copy = root / RECORDS_PATH
    return copy if copy.is_file() else None


@cache
def load_records() -> LibraryRecords:
    """The library records, read once per process (the file is data, not state).

    Package data (`PACKAGED`); where the package does not carry them, a source checkout reads its
    single repository copy instead, and an installed package without them says so on first use.
    """
    try:
        return parse_records(packaged(RECORDS_PATH).read_bytes())
    except KeyError:
        checkout = _checkout_records()
    if checkout is None:
        raise FileNotFoundError(f"{RECORDS_PATH} is neither package data nor in a source checkout")
    return parse_records(checkout.read_bytes())
