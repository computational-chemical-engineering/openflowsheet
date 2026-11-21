"""The v2 record model (ADR 0061 D1 to D5, D14): the schema, the tables the ADR states, the result.

The record's shape is `schemas/record-v2.schema.json`'s (closed objects); this module holds what
the schema cannot state as data: D4's core property ids per record type, D4's two built-in
correlation forms, D1's three record types and D12's two data sources (the payloads of the
built-in descriptors `registry/builtin/records.json` is generated from), D2's set-valued arrays
and D6's phase-class order. Rules that read these tables are `normalize`'s and `validate`'s.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from types import MappingProxyType
from typing import Any, Final, NamedTuple

from openflowsheet.registry.tokens import Coded
from openflowsheet.resources import packaged

RECORD_FORMAT: Final = "openflowsheet-record-v2"
SCHEMA_NAME: Final = "record-v2.schema.json"
#: D2 step 2: the top-level member detached before hashing.
VOLATILE: Final = "volatile"
#: D2 step 5, D3: the member D6 derives when it is absent.
ANCHOR: Final = "anchor_phase"

#: D7: the amount bases admitted now. `segment_mol` and `kg` wait for ADR-F2's quantity kinds
#: (`amount_basis_unsupported`); admitting one is a one-line change of this table.
ADMITTED_BASES: Final = frozenset({"mol"})
#: D3, Q7.R2: the kind of `molar_mass` per amount basis; `kg` has no molar mass.
MOLAR_MASS_KINDS: Final[Mapping[str, str]] = MappingProxyType(
    {"mol": "molar_mass", "segment_mol": "segment_molar_mass"}
)
#: D3: the kind of a formation or transition enthalpy and entropy on the `mol` basis. Entropy has
#: no registered kind yet (risk 6): an `s` Constant is `record_unit_invalid` until ADR-F2 adds it.
FORMATION_KINDS: Final[Mapping[str, str]] = MappingProxyType(
    {"h": "molar_enthalpy", "s": "molar_entropy"}
)
#: D4: the variables a constant entry's validity may name.
CONSTANT_VARIABLES: Final = ("T", "P")
#: D6: the phase classes in anchor order. Among `s:<form>` forms, formation keeps record order
#: (step 2) and phase-tagged entries take the smallest token (step 3).
PHASE_CLASSES: Final = ("ig", "aq", "l", "s:")


def phase_class(phase: object) -> int:
    """D2 step 4, D6: the rank of `phase`'s class (`ig` 0, `aq` 1, `l` 2, `s:<form>` 3); a value
    that is no phase token ranks after every class (step 6 refuses it)."""
    if isinstance(phase, str) and phase.startswith("s:"):
        return PHASE_CLASSES.index("s:")
    return PHASE_CLASSES.index(phase) if phase in PHASE_CLASSES[:-1] else len(PHASE_CLASSES)


def is_phase(value: object) -> bool:
    """Whether `value` is of a phase class (the schema checks the `s:<form>` spelling)."""
    return phase_class(value) < len(PHASE_CLASSES)


def pointer(parent: str, key: str | int) -> str:
    """The RFC 6901 pointer of member or element `key` below `parent`."""
    return f"{parent}/{str(key).replace('~', '~0').replace('/', '~1')}"


class CoreProperty(NamedTuple):
    """D4: a core property id's form, the kind of its value or result, and its phase."""

    form: str
    kind: str
    phase: str | None


#: D4: the core property ids of each record type (1.0.0); adding one amends ADR 0061.
CORE_PROPERTIES: Final[Mapping[str, Mapping[str, CoreProperty]]] = MappingProxyType(
    {
        "component": MappingProxyType(
            {
                "critical_temperature": CoreProperty("constant", "temperature", None),
                "critical_pressure": CoreProperty("constant", "pressure", None),
                "acentric_factor": CoreProperty("constant", "dimensionless", None),
                "ideal_gas_cp": CoreProperty("cp_ig_poly4_theta", "molar_heat_capacity", "ig"),
                "vapour_pressure": CoreProperty("ln_psat_abcd_theta", "pressure", "l"),
            }
        ),
        "parameter_set": MappingProxyType(
            {"wilson_lambda": CoreProperty("constant", "dimensionless", None)}
        ),
    }
)


def _quantity(name: str, kind: str, unit: str) -> dict[str, str]:
    return {"name": name, "kind": kind, "unit": unit}


def _dimensionless(*names: str) -> list[dict[str, str]]:
    return [_quantity(name, "dimensionless", "1") for name in names]


class CorrelationForm(NamedTuple):
    """D4: a built-in correlation form's descriptor title and payload."""

    title: str
    payload: Mapping[str, Any]


#: D4: the built-in correlation forms (F1 `correlation_form` descriptors, 1.0.0), by id. The
#: payload's `evaluator` is `null`, preview until ADR-F4 (D14): F3 validates and stores, F4
#: evaluates.
CORRELATION_FORMS: Final[Mapping[str, CorrelationForm]] = MappingProxyType(
    {
        "cp_ig_poly4_theta": CorrelationForm(
            "Ideal-gas heat capacity, quartic in T over 1000 K",
            {
                "variables": [_quantity("T", "temperature", "K")],
                "coefficients": _dimensionless("b0", "b1", "b2", "b3", "b4"),
                "result": {"kind": "molar_heat_capacity", "per_amount": True},
                "expression": (
                    "c_p^ig = R Σ_{k=0}^{4} b_k θ^k (per mol); θ = T / (1000 K); "
                    "R = 8.31446261815324 J/(mol K) exactly"
                ),
                "evaluator": None,
            },
        ),
        "ln_psat_abcd_theta": CorrelationForm(
            "Vapour pressure, ln P_sat in T over 1000 K",
            {
                "variables": [_quantity("T", "temperature", "K")],
                "coefficients": _dimensionless("a", "b", "c", "d"),
                "result": {"kind": "pressure", "per_amount": False},
                "expression": "ln(P_sat / Pa) = a + b/θ + c ln θ + d θ²; θ = T / (1000 K)",
                "evaluator": None,
            },
        ),
    }
)


class RecordType(NamedTuple):
    """D1: a built-in record type, its version, title and payload schema pointer (`None`: the
    payload is preview and owned elsewhere)."""

    version: str
    title: str
    pointer: str | None


#: D1: the built-in record types. `assay` 0.1.0 is preview (X21 owns its payload).
RECORD_TYPES: Final[Mapping[str, RecordType]] = MappingProxyType(
    {
        "component": RecordType("1.0.0", "Component record", "/$defs/component"),
        "parameter_set": RecordType("1.0.0", "Parameter set record", "/$defs/parameter_set"),
        "assay": RecordType("0.1.0", "Assay record", None),
    }
)

#: D12: the built-in data sources, by id: their titles, the record types they write and the
#: formats they read (D12's user-file formats; the legacy files are v1 component-record YAML).
DATA_SOURCES: Final[Mapping[str, Mapping[str, Any]]] = MappingProxyType(
    {
        "legacy-yaml": {
            "title": "Legacy benchmark record files",
            "record_types": ["component", "parameter_set"],
            "formats": ["component-record-v1-yaml"],
        },
        "user-file": {
            "title": "User record files",
            "record_types": ["component", "parameter_set"],
            "formats": ["component-record-v1-yaml", "record-v2-json", "record-v2-yaml"],
        },
    }
)


@cache
def record_schema() -> Mapping[str, Any]:
    """`schemas/record-v2.schema.json`, as the package carries it."""
    document: Mapping[str, Any] = json.loads(
        packaged(f"schemas/{SCHEMA_NAME}").read_text(encoding="utf-8")
    )
    return document


def element_symbols() -> frozenset[str]:
    """D3: the 118 element symbols, the schema's `$defs/elements/propertyNames/enum`."""
    return frozenset(record_schema()["$defs"]["elements"]["propertyNames"]["enum"])


@dataclass(frozen=True)
class RecordOutcome:
    """D2's result for one record: the normalised identity projection (`record`, without
    `volatile`), the detached `volatile` block (`None` when absent), D7's `errors` (refusals) and
    `findings` (notices; never identity), and `record_sha256`, `None` when an error refuses it."""

    record: Mapping[str, Any]
    volatile: Mapping[str, Any] | None
    record_sha256: str | None
    errors: tuple[Coded, ...] = field(default=())
    findings: tuple[Coded, ...] = field(default=())

    @property
    def refused(self) -> bool:
        return bool(self.errors)
