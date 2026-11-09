"""Display conversion at the boundary: `display-conversion-v1` (ADR 0075).

X04 converts in two places only (ADR 0075 D1): a request's `display_units` text is parsed into a
resolved preference (`parse_display_units`, D5), and an SI number a response carries for a reader
gains a display value beside it (`display_item`, D3, D7). Nothing stored or hashed is ever
converted, and a display value is never an input to anything (D1.2, D1.3).

The output table (D2) shares its constants with ADR 0016's input table (`CONVERSION_ROWS`): on
ADR 0016's kinds the rows here are ADR 0016's non-mass rows plus the two gauge rows, and the
`mass_flow` rows have ADR 0016's mass-row factors. A gauge row's offset is the project's declared
ambient pressure (D6), never an assumed one.

The arithmetic (D3) is exact rational arithmetic and correctly rounded conversions — CPython's
`repr` for `D(x)`, `float(Fraction)` for `RN`, `format(x, ".pg")` for the digit rounding — so the
result is platform-independent and needs no tolerance. A binary64 chain (`x - 273.15`,
`x / 1e5`) is not this function. The reference values are
`docs/derivations/scripts/x04_reference.json` (`docs/derivations/X04-test-specification.md`).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from types import MappingProxyType
from typing import Any, Final, Literal

from openflowsheet.units import KIND_SI_UNITS, KINDS, Dimension

__all__ = [
    "DISPLAY_CONVERSION_ID",
    "DISPLAY_KINDS",
    "DISPLAY_ROWS",
    "GAUGE",
    "GAUGE_ROWS",
    "PRESETS",
    "DisplayKind",
    "DisplayRow",
    "DisplayUnits",
    "DisplayUnitsError",
    "csv_suffix",
    "display_item",
    "parse_display_units",
    "row_to_si",
]

DISPLAY_CONVERSION_ID: Final = "display-conversion-v1"

#: A gauge row's `b`: the project's declared ambient pressure (ADR 0075 D2, D6).
GAUGE: Final = "ambient"

#: ADR 0075 D2.1: the five kinds ADR 0062 D1 (Proposed) names that the stream table already
#: carries, with ADR 0062's SI units and dimensions. Display kinds only: they are not Quantity
#: kinds (F2 registers those), so F2 landing them changes nothing here.
_DISPLAY_ONLY_KINDS: Final[dict[str, tuple[str, Dimension]]] = {
    "specific_enthalpy": ("J/kg", (2, 0, -2, 0, 0, 0, 0)),
    "specific_entropy": ("J/(kg K)", (2, 0, -2, -1, 0, 0, 0)),
    "molar_entropy": ("J/(mol K)", (2, 1, -2, -1, -1, 0, 0)),
    "enthalpy_flow": ("W", (2, 1, -3, 0, 0, 0, 0)),
    "mass_fraction": ("1", (0, 0, 0, 0, 0, 0, 0)),
}


@dataclass(frozen=True)
class DisplayKind:
    """A display kind: its SI unit (the identity, never a row) and its dimension."""

    si_unit: str
    dimension: Dimension


#: ADR 0075 D2.1, sorted by kind: every kind of `schemas/units.json` and the five above.
DISPLAY_KINDS: Final[Mapping[str, DisplayKind]] = MappingProxyType(
    {
        kind: DisplayKind(*spec)
        for kind, spec in sorted(
            {
                **{kind: (KIND_SI_UNITS[kind], KINDS[kind]) for kind in KINDS},
                **_DISPLAY_ONLY_KINDS,
            }.items()
        )
    }
)

Direction = Literal["input and output", "output"]


def csv_suffix(unit: str) -> str:
    """ADR 0075 D7.6: a unit's CSV column suffix — `/` becomes `_`; `(`, `)` and spaces are
    dropped; `%` becomes `pct`. On ST's thirteen SI units it gives ST's suffixes (claim C12)."""
    for old, new in (("/", "_"), ("(", ""), (")", ""), (" ", ""), ("%", "pct")):
        unit = unit.replace(old, new)
    return unit


@dataclass(frozen=True)
class DisplayRow:
    """One row of ADR 0075 D2: `SI = a·u + b`, `a > 0`; `b` is `GAUGE` on a gauge row."""

    kind: str
    unit: str
    a: Fraction
    b: Fraction | Literal["ambient"]
    direction: Direction
    csv_suffix: str

    @property
    def gauge(self) -> bool:
        return self.b == GAUGE


#: The pound-force per square inch of the 1959 international definitions, Pa, exactly (ADR 0016
#: D3): 0.45359237 kg · 9.80665 m/s² / (0.0254 m)².
_PSI: Final = Fraction("0.45359237") * Fraction("9.80665") / Fraction("0.0254") ** 2
_IO: Final[Direction] = "input and output"
_OUT: Final[Direction] = "output"

_Offset = Fraction | Literal["ambient"]
_ROW_SPECS: Final[tuple[tuple[str, str, Fraction, _Offset, Direction], ...]] = (
    ("temperature", "degC", Fraction(1), Fraction(5463, 20), _IO),
    ("temperature", "degF", Fraction(5, 9), Fraction(45967, 180), _IO),
    ("temperature_difference", "degC", Fraction(1), Fraction(0), _IO),
    ("temperature_difference", "degF", Fraction(5, 9), Fraction(0), _IO),
    ("pressure", "kPa", Fraction(1000), Fraction(0), _IO),
    ("pressure", "MPa", Fraction(10**6), Fraction(0), _IO),
    ("pressure", "bar", Fraction(10**5), Fraction(0), _IO),
    ("pressure", "atm", Fraction(101325), Fraction(0), _IO),
    ("pressure", "psi", _PSI, Fraction(0), _IO),
    ("pressure", "barg", Fraction(10**5), GAUGE, _OUT),
    ("pressure", "psig", _PSI, GAUGE, _OUT),
    ("molar_flow", "kmol/s", Fraction(1000), Fraction(0), _IO),
    ("molar_flow", "mmol/s", Fraction(1, 1000), Fraction(0), _IO),
    ("molar_flow", "mol/h", Fraction(1, 3600), Fraction(0), _IO),
    ("molar_flow", "kmol/h", Fraction(5, 18), Fraction(0), _IO),
    ("mass_flow", "g/s", Fraction(1, 1000), Fraction(0), _OUT),
    ("mass_flow", "kg/h", Fraction(1, 3600), Fraction(0), _OUT),
    ("heat_rate", "kW", Fraction(1000), Fraction(0), _IO),
    ("heat_rate", "MW", Fraction(10**6), Fraction(0), _IO),
    ("power", "kW", Fraction(1000), Fraction(0), _IO),
    ("power", "MW", Fraction(10**6), Fraction(0), _IO),
    ("enthalpy_flow", "kW", Fraction(1000), Fraction(0), _OUT),
    ("enthalpy_flow", "MW", Fraction(10**6), Fraction(0), _OUT),
    ("molar_enthalpy", "kJ/mol", Fraction(1000), Fraction(0), _OUT),
    ("specific_enthalpy", "kJ/kg", Fraction(1000), Fraction(0), _OUT),
    ("molar_entropy", "kJ/(mol K)", Fraction(1000), Fraction(0), _OUT),
    ("specific_entropy", "kJ/(kg K)", Fraction(1000), Fraction(0), _OUT),
    ("dimensionless", "%", Fraction(1, 100), Fraction(0), _IO),
    ("mole_fraction", "%", Fraction(1, 100), Fraction(0), _IO),
    ("mass_fraction", "%", Fraction(1, 100), Fraction(0), _OUT),
)

#: ADR 0075 D2.2 (`display-conversion-v1`), keyed by (kind, unit) — exact, case-sensitive — in
#: table order. Each kind's SI unit is the identity and is not a row.
DISPLAY_ROWS: Final[Mapping[tuple[str, str], DisplayRow]] = MappingProxyType(
    {
        (kind, unit): DisplayRow(kind, unit, a, b, direction, csv_suffix(unit))
        for kind, unit, a, b, direction in _ROW_SPECS
    }
)

#: The gauge rows: output only, offset by the project's declared ambient pressure (D6.4).
GAUGE_ROWS: Final[frozenset[tuple[str, str]]] = frozenset(
    key for key, row in DISPLAY_ROWS.items() if row.gauge
)

#: ADR 0075 D5.3. No preset holds a gauge unit, so each works in every project (claim C11).
PRESETS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "si": MappingProxyType({}),
        "eng": MappingProxyType(
            {
                "temperature": "degC",
                "temperature_difference": "degC",
                "pressure": "bar",
                "molar_flow": "kmol/h",
                "mass_flow": "kg/h",
                "heat_rate": "kW",
                "power": "kW",
                "enthalpy_flow": "kW",
                "molar_enthalpy": "kJ/mol",
                "specific_enthalpy": "kJ/kg",
                "specific_entropy": "kJ/(kg K)",
            }
        ),
    }
)


# -- the arithmetic (ADR 0075 D3) ---------------------------------------------------------------


def _decimal(x: float) -> Fraction:
    """`D(x)`: the shortest decimal that rounds to `x` (CPython's `repr`), as an exact rational."""
    return Fraction(repr(x))


def _offset(row: DisplayRow, ambient_pressure: float | None) -> Fraction:
    if isinstance(row.b, Fraction):
        return row.b
    if ambient_pressure is None:
        raise ValueError(f"the gauge row ({row.kind}, {row.unit}) needs the declared ambient")
    return _decimal(ambient_pressure)


def row_to_si(value: float, kind: str, unit: str, ambient_pressure: float | None = None) -> float:
    """The row's arithmetic in the input direction, `RN(a·D(v) + b)` — ADR 0016 D2's, where the
    row is an input row; a gauge row's `b` is `D(ambient_pressure)`. A zero is `+0.0`. Raises
    `KeyError` for no row, `ValueError` for a nonfinite `value` or a gauge row without an
    ambient, `OverflowError` when the result is not finite."""
    row = DISPLAY_ROWS[(kind, unit)]
    if not isfinite(value):
        raise ValueError(f"{value!r} is not finite")
    return float(row.a * _decimal(value) + _offset(row, ambient_pressure)) + 0.0


def _display_value(x: float, row: DisplayRow, ambient_pressure: float | None) -> float | None:
    """ADR 0075 D3 steps 1-3 for a finite SI `x`: the display value, or `None` when `RN(q)` is
    not finite."""
    a, b = row.a, _offset(row, ambient_pressure)
    target = _decimal(x)
    # Step 1: q = (D(X) − b)/a exactly; v0 = RN(q).
    try:
        v0 = float((target - b) / a) + 0.0
    except OverflowError:
        return None
    # Step 2, p = 0: the value vanishes iff RN(b) = X.
    if float(b) == x:
        return 0.0
    # Step 2, p = 1…17: the first rounding of v0 to p significant digits that converts back. A
    # candidate whose conversion back is not finite (or that is itself not finite, which only
    # the largest doubles can give) does not convert back to the finite X.
    for p in range(1, 18):
        candidate = float(format(v0, f".{p}g")) + 0.0
        if not isfinite(candidate):
            continue
        try:
            back = float(a * _decimal(candidate) + b)
        except OverflowError:
            continue
        if back == x:
            return candidate
    # Step 3: the fallback, within half an ulp of q; it does not convert back.
    return v0


class DisplayUnits(Mapping[str, str]):
    """A resolved display preference (ADR 0075 D5.4): the map kind → non-SI unit of D2, and the
    project's ambient pressure, kept iff a gauge unit is in the map.

    It is MSG's `RenderContext.display_units` slot type (`Mapping[str, str]`). Immutable; two
    preferences are equal iff their maps and ambients are."""

    __slots__ = ("_ambient_pressure", "_units")

    def __init__(
        self, units: Mapping[str, str] | None = None, ambient_pressure: float | None = None
    ) -> None:
        resolved = dict(sorted((units or {}).items()))
        for kind, unit in resolved.items():
            if (kind, unit) not in DISPLAY_ROWS:
                raise ValueError(f"({kind}, {unit}) is not a row of {DISPLAY_CONVERSION_ID}")
        gauge = any((kind, unit) in GAUGE_ROWS for kind, unit in resolved.items())
        if gauge and (
            ambient_pressure is None or not isfinite(ambient_pressure) or ambient_pressure <= 0.0
        ):
            raise ValueError("a gauge unit needs the declared ambient pressure, finite and > 0")
        self._units: Mapping[str, str] = MappingProxyType(resolved)
        self._ambient_pressure: float | None = ambient_pressure if gauge else None

    @property
    def ambient_pressure(self) -> float | None:
        """The declared ambient pressure, Pa — `None` unless a gauge unit is in the map."""
        return self._ambient_pressure

    def __getitem__(self, kind: str) -> str:
        return self._units[kind]

    def __iter__(self) -> Iterator[str]:
        return iter(self._units)

    def __len__(self) -> int:
        return len(self._units)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DisplayUnits):
            return NotImplemented
        return (
            dict(self._units) == dict(other._units)
            and self._ambient_pressure == other._ambient_pressure
        )

    def __hash__(self) -> int:
        return hash((tuple(self._units.items()), self._ambient_pressure))

    def __repr__(self) -> str:
        return f"DisplayUnits({dict(self._units)!r}, ambient_pressure={self._ambient_pressure!r})"

    def as_document(self) -> dict[str, Any]:
        """The echo of D7.3: `{units: {kind: unit}, ambient_pressure: {value, unit} | null}`."""
        ambient = self._ambient_pressure
        return {
            "units": dict(self._units),
            "ambient_pressure": None if ambient is None else {"value": ambient, "unit": "Pa"},
        }

    def canonical(self) -> str:
        """D5.4: the `kind=unit` pairs sorted by kind, joined by `,`; the empty map gives `""`."""
        return ",".join(f"{kind}={unit}" for kind, unit in self._units.items())


def display_item(x: float, kind: str | None, units: Mapping[str, str]) -> dict[str, Any] | None:
    """ADR 0075 D3, D4 and D7.1: the display item of the SI number `x` of kind `kind`.

    `None` when the number has no kind, or its kind is not in the preference (D4.1, D4.3: kinds
    decide, never the SI unit symbol); `{value, unit}` otherwise, or `{value: None, unit, reason:
    {code: "display_out_of_range", params: {kind, unit}}}` when the display value is not finite.
    A zero display value is `+0.0`. `units` is a `DisplayUnits` (a plain mapping carries no
    ambient, so a gauge unit in it raises `ValueError`)."""
    if kind is None or kind not in units:
        return None
    unit = units[kind]
    row = DISPLAY_ROWS[(kind, unit)]
    if not isfinite(x):
        raise ValueError(f"{x!r} is not finite: SI values are finite (ADR 0001 D1.5)")
    ambient = units.ambient_pressure if isinstance(units, DisplayUnits) else None
    value = _display_value(x, row, ambient)
    if value is None:
        return {
            "value": None,
            "unit": unit,
            "reason": {"code": "display_out_of_range", "params": {"kind": kind, "unit": unit}},
        }
    return {"value": value, "unit": unit}


# -- the preference grammar (ADR 0075 D5) --------------------------------------------------------

DisplayRefusal = Literal[
    "display_units_invalid", "display_unit_unsupported", "ambient_pressure_undeclared"
]


class DisplayUnitsError(ValueError):
    """A `display_units` text refused (ADR 0075 D5.2, D9): the `ApiError` code it is raised as
    (`invalid_request` or `unsupported`), the reason code, and the message head
    `code(arg): "<text>"` — the user's text JSON-quoted, so MSG's legacy grammar reads exactly one
    code (claim C13). An `invalid_request` points at `/display_units`."""

    def __init__(
        self,
        api_error: Literal["invalid_request", "unsupported"],
        reason: DisplayRefusal,
        message: str,
    ) -> None:
        super().__init__(message)
        self.api_error = api_error
        self.reason: DisplayRefusal = reason
        self.message = message

    @property
    def pointer(self) -> str | None:
        return "/display_units" if self.api_error == "invalid_request" else None


def _refuse(
    api_error: Literal["invalid_request", "unsupported"],
    reason: DisplayRefusal,
    arg: str | int,
    text: str,
) -> DisplayUnitsError:
    return DisplayUnitsError(
        api_error, reason, f"{reason}({arg}): {json.dumps(text, ensure_ascii=False)}"
    )


def parse_display_units(text: str, ambient_pressure: float | None) -> DisplayUnits:
    """ADR 0075 D5.2: the resolved preference of a `display_units` text, given the project's
    declared ambient pressure (`None` when undeclared). Raises `DisplayUnitsError`.

    `display_units := item ("," item)*`, `item := preset | kind "=" unit`. Each item, and each
    side of its first `=`, is stripped of leading and trailing U+0020 and nothing else. A preset
    only first; a kind named at most once among the explicit items; the kind's SI unit removes the
    kind; a gauge unit needs a declared ambient. The text's length (1–1024) is the request
    schema's business."""
    resolved: dict[str, str] = {}
    explicit: set[str] = set()
    for index, raw in enumerate(text.split(",")):
        item = raw.strip(" ")
        if item in PRESETS:
            if index != 0:
                raise _refuse("invalid_request", "display_units_invalid", index, item)
            resolved.update(PRESETS[item])
            continue
        kind, separator, unit = item.partition("=")
        kind, unit = kind.strip(" "), unit.strip(" ")
        if not separator or not unit or kind not in DISPLAY_KINDS or kind in explicit:
            raise _refuse("invalid_request", "display_units_invalid", index, item)
        explicit.add(kind)
        if unit == DISPLAY_KINDS[kind].si_unit:
            resolved.pop(kind, None)
        elif (kind, unit) in DISPLAY_ROWS:
            resolved[kind] = unit
        else:
            raise _refuse("unsupported", "display_unit_unsupported", kind, unit)
    gauge = sorted(kind for kind, unit in resolved.items() if (kind, unit) in GAUGE_ROWS)
    if gauge and ambient_pressure is None:
        raise _refuse(
            "invalid_request", "ambient_pressure_undeclared", gauge[0], resolved[gauge[0]]
        )
    return DisplayUnits(resolved, ambient_pressure if gauge else None)
