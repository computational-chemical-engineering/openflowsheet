"""Units and quantities layer.

Owns physical quantities, the SI-internal state convention, dimensional checking, and unit
conversion at the IR boundary (blueprint §3 layer table row ``schemas/``, ``src/ir/``,
``src/units/``; §4.2 state representation). Canonical stored values are SI; display units are
a presentation concern recorded with the quantity. It must not own equations, solver scaling
policy, or any implicit unit coercion inside a residual evaluation.

The kind table and the three pure checks below are introduced by package P01 and implement
ADR 0001 D1: the fixed dimension order (D1.2), the ``kind`` vocabulary and the
temperature/temperature-difference arithmetic rules (D1.3), unprefixed SI storage (D1.1), and
rejection of nonfinite values with normalization of signed zero (D1.5). ``schemas/units.json``
carries the same table for schema-side validation; ``tests/test_units_p01.py`` asserts the two
agree exactly, so neither can drift.

The one conversion is `unit-conversion-v2` (ADR 0016, which widens ADR 0001 D1.1 and D1.4 for
input documents; T06 specification §8.5 as amended by A2): a specification value or an instance
parameter written in a unit of ADR 0016's table is converted to its kind's SI unit, exactly, at
validation and binding, and the conversion is recorded. Nothing stored is in a non-SI unit. No
expression evaluation and no state objects. Everything here is a pure function over plain data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from math import copysign, inf, isfinite
from types import MappingProxyType
from typing import Final, Literal, overload

# ADR 0002 D3.3's integer rule, implemented once (Amendment 1): which integers have a binary64
# reading.
from openflowsheet.canonical import integer_binary64

__all__ = [
    "CONVERSION_ROWS",
    "DIMENSION_ORDER",
    "FRACTION_PARAMETERS",
    "KIND_LOWER_BOUNDS_EXCLUSIVE",
    "KIND_SI_UNITS",
    "KINDS",
    "QUANTITY_ROLES",
    "UNIT_CONVERSION_ID",
    "ConversionRefusal",
    "ConversionRow",
    "ConversionRule",
    "ConversionSource",
    "Dimension",
    "TargetClass",
    "UnitConversion",
    "UnitConversionError",
    "UnknownKindError",
    "check_quantity",
    "combine_kinds",
    "convert_input_value",
    "dimension_of",
    "normalize_zero",
    "read_number",
]

Dimension = tuple[int, int, int, int, int, int, int]

DIMENSION_ORDER: Final[tuple[str, ...]] = (
    "length",
    "mass",
    "time",
    "temperature",
    "amount",
    "current",
    "luminous_intensity",
)
"""ADR 0001 D1.2. The order is part of the P01 interface freeze."""

_KIND_DIMENSIONS: Final[dict[str, Dimension]] = {
    "temperature": (0, 0, 0, 1, 0, 0, 0),
    "temperature_difference": (0, 0, 0, 1, 0, 0, 0),
    "pressure": (-1, 1, -2, 0, 0, 0, 0),
    "molar_flow": (0, 0, -1, 0, 1, 0, 0),
    "mass_flow": (0, 1, -1, 0, 0, 0, 0),
    "heat_rate": (2, 1, -3, 0, 0, 0, 0),
    "power": (2, 1, -3, 0, 0, 0, 0),
    "molar_enthalpy": (2, 1, -2, 0, -1, 0, 0),
    "mole_fraction": (0, 0, 0, 0, 0, 0, 0),
    "dimensionless": (0, 0, 0, 0, 0, 0, 0),
    "molar_mass": (0, 1, 0, 0, -1, 0, 0),
    # Added in P01 beyond the kinds ADR 0001 D1.3 enumerates, because the SYN-001
    # ComponentRecord parameters c_p and v_i cannot otherwise be expressed. Dimension-only, in
    # the sense D1.3 uses for its non-temperature kinds: no arithmetic rule beyond the
    # dimension check. Escalated to Fable in docs/progress.md ("Opus -> Fable, P01 handoff").
    "molar_heat_capacity": (2, 1, -2, -1, -1, 0, 0),
    "molar_volume": (3, 0, 0, 0, -1, 0, 0),
}

_KIND_SI_UNITS: Final[dict[str, str]] = {
    "temperature": "K",
    "temperature_difference": "K",
    "pressure": "Pa",
    "molar_flow": "mol/s",
    "mass_flow": "kg/s",
    "heat_rate": "W",
    "power": "W",
    "molar_enthalpy": "J/mol",
    "mole_fraction": "1",
    "dimensionless": "1",
    "molar_mass": "kg/mol",
    "molar_heat_capacity": "J/(mol K)",
    "molar_volume": "m3/mol",
}

_KIND_LOWER_BOUNDS_EXCLUSIVE: Final[dict[str, float | None]] = {
    "temperature": 0.0,
    "temperature_difference": None,
    "pressure": None,
    "molar_flow": None,
    "mass_flow": None,
    "heat_rate": None,
    "power": None,
    "molar_enthalpy": None,
    "mole_fraction": None,
    "dimensionless": None,
    "molar_mass": 0.0,
    "molar_heat_capacity": None,
    "molar_volume": 0.0,
}

KINDS: Final[Mapping[str, Dimension]] = MappingProxyType(_KIND_DIMENSIONS)
KIND_SI_UNITS: Final[Mapping[str, str]] = MappingProxyType(_KIND_SI_UNITS)
KIND_LOWER_BOUNDS_EXCLUSIVE: Final[Mapping[str, float | None]] = MappingProxyType(
    _KIND_LOWER_BOUNDS_EXCLUSIVE
)

QUANTITY_ROLES: Final[frozenset[str]] = frozenset({"fixed", "free", "decision", "derived"})

_REQUIRED_QUANTITY_FIELDS: Final[tuple[str, ...]] = (
    "value",
    "unit",
    "dimension",
    "kind",
    "meaning",
    "role",
)

# ADR 0001 D1.3, as a closed table. Anything absent from it is a validation error; in
# particular `temperature + temperature`, which has no physical meaning.
_KIND_ARITHMETIC: Final[dict[tuple[str, str, str], str]] = {
    ("temperature", "-", "temperature"): "temperature_difference",
    ("temperature", "+", "temperature_difference"): "temperature",
    ("temperature", "-", "temperature_difference"): "temperature",
    ("temperature_difference", "+", "temperature"): "temperature",
    ("temperature_difference", "+", "temperature_difference"): "temperature_difference",
    ("temperature_difference", "-", "temperature_difference"): "temperature_difference",
}


class UnknownKindError(ValueError):
    """A `kind` outside the ADR 0001 D1.3 vocabulary. Not silently coerced to `dimensionless`."""


def dimension_of(kind: str) -> Dimension:
    """The SI dimension exponent vector of `kind`, in `DIMENSION_ORDER` (ADR 0001 D1.2).

    Raises `UnknownKindError` for an unregistered kind: an unknown quantity kind is a schema
    error, never a default.
    """
    try:
        return _KIND_DIMENSIONS[kind]
    except KeyError:
        raise UnknownKindError(
            f"unknown quantity kind {kind!r}; registered kinds are "
            + ", ".join(sorted(_KIND_DIMENSIONS))
        ) from None


def normalize_zero(value: float) -> float:
    """ADR 0001 D1.5: -0.0 and +0.0 are the same state, and canonical form is +0.0."""
    return 0.0 if value == 0.0 else value


def combine_kinds(left: str, operator: str, right: str) -> str:
    """The kind of `left operator right` for `operator` in `{'+', '-'}` (ADR 0001 D1.3).

    `temperature - temperature` yields `temperature_difference`; `temperature` and a
    `temperature_difference` combine to a `temperature`; `temperature + temperature` raises,
    as does subtracting an absolute temperature from a temperature difference. Two quantities
    of the same kind combine to that kind. Two distinct kinds that merely share a dimension
    (`heat_rate` and `power`, `mole_fraction` and `dimensionless`) do not combine.
    """
    if operator not in ("+", "-"):
        raise ValueError(f"operator must be '+' or '-', got {operator!r}")
    left_dimension = dimension_of(left)
    right_dimension = dimension_of(right)

    if left_dimension != right_dimension:
        raise ValueError(
            f"cannot combine {left} {list(left_dimension)} with {right} {list(right_dimension)}: "
            "dimensions differ"
        )

    if left in ("temperature", "temperature_difference") or right in (
        "temperature",
        "temperature_difference",
    ):
        result = _KIND_ARITHMETIC.get((left, operator, right))
        if result is None:
            raise ValueError(
                f"{left} {operator} {right} is not a defined operation (ADR 0001 D1.3); "
                "absolute temperature and temperature difference are distinct quantities"
            )
        return result

    if left != right:
        raise ValueError(
            f"{left} and {right} share a dimension but are distinct kinds; "
            "combining them requires an explicit, declared conversion"
        )
    return left


def read_number(value: object) -> float | None:
    """The one reading of a number a reader takes from a specification's `value` or from a
    parameter Quantity's `value`, `bounds` or `nominal` (T06 spec §8.5 (A5)): `value` as a float
    if it is a real number, else `None` (`bool` is not a number).

    An integer is read as the binary64 it is the canonical spelling of (`integer_binary64`:
    every one with `|n| ≤ 2⁵³`, exactly, and one per binary64 beyond; ADR 0002 D3.3,
    Amendment 1). Any other integer has no binary64 reading (refused, never rounded) and reads as
    the infinity of its sign, so that V0's refusal of a nonfinite value (ADR 0016) fires exactly
    as it does for that infinity, with the same code (spec A100). A float is returned as is; the
    reader's own checks judge it.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        reading = integer_binary64(value)
        if reading is None:
            return inf if value > 0 else -inf  # not `copysign(inf, n)`: it converts `n` first
        return reading
    if isinstance(value, float):
        return value
    return None


def check_quantity(quantity: Mapping[str, object]) -> tuple[str, ...]:
    """Semantic checks on one Quantity document; returns a tuple of problems, empty if clean.

    A pure function: it reports, it never repairs. It covers what JSON Schema cannot express
    for a Quantity — that the value is finite (JSON Schema's `number` admits NaN and infinity
    once a YAML/JSON document has been decoded into Python floats), that `dimension` and `unit`
    are the ones ADR 0001 registers for the declared `kind`, that signed zero is in canonical
    form, and that declared bounds are consistent with each other and with the value.
    """
    problems: list[str] = []

    for field in _REQUIRED_QUANTITY_FIELDS:
        if field not in quantity:
            problems.append(f"missing required field {field!r}")

    kind = quantity.get("kind")
    dimension: Dimension | None = None
    if isinstance(kind, str):
        try:
            dimension = dimension_of(kind)
        except UnknownKindError as error:
            problems.append(str(error))
    elif "kind" in quantity:
        problems.append(f"kind must be a string, got {kind!r}")

    value = read_number(quantity.get("value")) if "value" in quantity else None
    if "value" in quantity and value is None:
        problems.append(f"value must be a number, got {quantity['value']!r}")
    elif value is not None:
        if not isfinite(value):
            problems.append(
                f"value must be finite, got {value!r}; nonfinite numbers are rejected in every "
                "semantic input (ADR 0001 D1.5)"
            )
        elif value == 0.0 and copysign(1.0, value) < 0.0:
            problems.append(
                "value is -0.0; canonical form normalizes signed zero to +0.0 (ADR 0001 D1.5)"
            )

    if dimension is not None and isinstance(kind, str):
        declared = quantity.get("dimension")
        if not (
            isinstance(declared, list)
            and len(declared) == len(DIMENSION_ORDER)
            and all(isinstance(item, int) and not isinstance(item, bool) for item in declared)
        ):
            problems.append(
                f"dimension must be {len(DIMENSION_ORDER)} integers in the order "
                f"{list(DIMENSION_ORDER)}, got {declared!r}"
            )
        elif tuple(declared) != dimension:
            problems.append(
                f"dimension {declared} does not match kind {kind!r}, which is "
                f"{list(dimension)} (ADR 0001 D1.2)"
            )

        expected_unit = _KIND_SI_UNITS[kind]
        unit = quantity.get("unit")
        if unit != expected_unit:
            problems.append(
                f"unit {unit!r} is not the internal SI unit for kind {kind!r}, which is "
                f"{expected_unit!r}; display units belong in display_unit (ADR 0001 D1.1)"
            )

        bound = _KIND_LOWER_BOUNDS_EXCLUSIVE[kind]
        if bound is not None and value is not None and isfinite(value) and value <= bound:
            problems.append(f"kind {kind!r} requires value > {bound}, got {value!r}")
        if kind == "mole_fraction" and value is not None and isfinite(value):
            if not (0.0 <= value <= 1.0):
                problems.append(f"mole_fraction must lie in [0, 1], got {value!r}")

    role = quantity.get("role")
    if "role" in quantity and role not in QUANTITY_ROLES:
        problems.append(f"role must be one of {sorted(QUANTITY_ROLES)}, got {role!r}")

    problems.extend(_check_bounds(quantity, value))

    nominal = quantity.get("nominal")
    if nominal is not None:
        nominal_value = read_number(nominal)
        if nominal_value is None or not isfinite(nominal_value):
            problems.append(f"nominal must be a finite number, got {nominal!r}")

    return tuple(problems)


def _check_bounds(quantity: Mapping[str, object], value: float | None) -> list[str]:
    problems: list[str] = []
    bounds = quantity.get("bounds")
    if bounds is None:
        return problems
    if not isinstance(bounds, Mapping):
        return [f"bounds must be an object with optional lower/upper, got {bounds!r}"]

    limits: dict[str, float] = {}
    for name in ("lower", "upper"):
        if name not in bounds or bounds[name] is None:
            continue
        limit = read_number(bounds[name])
        if limit is None or not isfinite(limit):
            problems.append(f"bounds.{name} must be a finite number, got {bounds[name]!r}")
        else:
            limits[name] = limit

    if "lower" in limits and "upper" in limits and limits["lower"] > limits["upper"]:
        problems.append(
            f"bounds.lower {limits['lower']!r} exceeds bounds.upper {limits['upper']!r}"
        )
    if value is not None and isfinite(value):
        if "lower" in limits and value < limits["lower"]:
            problems.append(f"value {value!r} is below bounds.lower {limits['lower']!r}")
        if "upper" in limits and value > limits["upper"]:
            problems.append(f"value {value!r} is above bounds.upper {limits['upper']!r}")
    return problems


# -- unit-conversion-v2 (ADR 0016; T06 specification §8.5 as amended by A2; register R-077) -----

UNIT_CONVERSION_ID: Final = "unit-conversion-v2"

ConversionRule = Literal["degC_to_K", "degF_to_K", "mass_to_molar", "scale"]
ConversionSource = Literal["specification", "parameter"]
#: What a row asks of its target (ADR 0016 D3, *Targets*): anything; a one-component flow; a
#: one-component flow of a component with a molecular weight (a mass basis); a fraction.
TargetClass = Literal["any", "component", "mass", "fraction"]


@dataclass(frozen=True)
class ConversionRow:
    """One row of ADR 0016 D3: `SI = RN(a·D(v) + b)` for a unit on a required kind.

    `a` and `b` are exact rationals fixed by the unit's definition; a mass row's `a` is further
    divided by `D(M_c)` at conversion time. `declared_kinds` is what the input's own `kind` may
    say.
    """

    rule: ConversionRule
    a: Fraction
    b: Fraction
    declared_kinds: frozenset[str]
    target_class: TargetClass


def _row(
    rule: ConversionRule,
    a: str,
    b: str = "0",
    *,
    declared: tuple[str, ...],
    target: TargetClass = "any",
) -> ConversionRow:
    return ConversionRow(rule, Fraction(a), Fraction(b), frozenset(declared), target)


#: The pound-force per square inch of the 1959 international definitions, Pa, exactly:
#: 0.45359237 kg · 9.80665 m/s² / (0.0254 m)² (ADR 0016 D3).
_PSI: Final = str(Fraction("0.45359237") * Fraction("9.80665") / Fraction("0.0254") ** 2)

#: ADR 0016 D3, keyed by (the kind the target requires, the unit as written — exact,
#: case-sensitive). Every kind's SI unit is the identity (step V3) and is not a row.
_ROWS: Final[dict[tuple[str, str], ConversionRow]] = {
    ("temperature", "degC"): _row("degC_to_K", "1", "5463/20", declared=("temperature",)),
    ("temperature", "degF"): _row("degF_to_K", "5/9", "45967/180", declared=("temperature",)),
    ("temperature_difference", "degC"): _row("scale", "1", declared=("temperature_difference",)),
    ("temperature_difference", "degF"): _row("scale", "5/9", declared=("temperature_difference",)),
    ("pressure", "kPa"): _row("scale", "1000", declared=("pressure",)),
    ("pressure", "MPa"): _row("scale", "1000000", declared=("pressure",)),
    ("pressure", "bar"): _row("scale", "100000", declared=("pressure",)),
    ("pressure", "atm"): _row("scale", "101325", declared=("pressure",)),
    ("pressure", "psi"): _row("scale", _PSI, declared=("pressure",)),
    ("heat_rate", "kW"): _row("scale", "1000", declared=("heat_rate",)),
    ("heat_rate", "MW"): _row("scale", "1000000", declared=("heat_rate",)),
    ("power", "kW"): _row("scale", "1000", declared=("power",)),
    ("power", "MW"): _row("scale", "1000000", declared=("power",)),
    ("molar_flow", "kmol/s"): _row("scale", "1000", declared=("molar_flow",), target="component"),
    ("molar_flow", "mmol/s"): _row("scale", "1/1000", declared=("molar_flow",), target="component"),
    ("molar_flow", "mol/h"): _row("scale", "1/3600", declared=("molar_flow",), target="component"),
    ("molar_flow", "kmol/h"): _row("scale", "5/18", declared=("molar_flow",), target="component"),
    ("molar_flow", "kg/s"): _row(
        "mass_to_molar", "1", declared=("molar_flow", "mass_flow"), target="mass"
    ),
    ("molar_flow", "g/s"): _row(
        "mass_to_molar", "1/1000", declared=("molar_flow", "mass_flow"), target="mass"
    ),
    ("molar_flow", "kg/h"): _row(
        "mass_to_molar", "1/3600", declared=("molar_flow", "mass_flow"), target="mass"
    ),
    ("dimensionless", "%"): _row("scale", "1/100", declared=("dimensionless",), target="fraction"),
    ("mole_fraction", "%"): _row("scale", "1/100", declared=("mole_fraction",)),
}
CONVERSION_ROWS: Final[Mapping[tuple[str, str], ConversionRow]] = MappingProxyType(_ROWS)

#: The parameters that are fractions, by name up to the first `.` (`split.C` is `split`): the only
#: `dimensionless` targets `%` converts (ADR 0016 D3). A stoichiometric coefficient in percent is
#: not a quantity.
FRACTION_PARAMETERS: Final[frozenset[str]] = frozenset(
    {"split_fraction", "efficiency", "conversion", "split"}
)


@dataclass(frozen=True)
class UnitConversion:
    """One conversion `unit-conversion-v2` applied (ADR 0016 D6).

    What a binding's `input_mapping` and `DIM-01`'s message carry; never the certificate, whose
    subject is the declaration, which is SI by construction (R-035).
    """

    source: ConversionSource
    #: A specification id, or `<instance>.<name>` for an instance parameter.
    input_id: str
    #: As written.
    value: float
    unit: str
    si_value: float
    si_unit: str
    rule: ConversionRule
    #: `mass_to_molar` only: the target component and its molecular weight `M_c`, kg/mol.
    component: str | None = None
    molar_mass: float | None = None


ConversionRefusal = Literal["kind", "unit", "value"]


class UnitConversionError(ValueError):
    """`unit-conversion-v2` refuses (ADR 0016 D4): a nonfinite value, or a result outside the
    finite binary64 range (`reason = "value"`, V0 and V4); a declared kind the target does not
    admit (V2, `"kind"`); a unit that is neither the kind's SI unit nor a row of the table for the
    target (V1/V5, `"unit"`). The caller names the input in its own vocabulary."""

    def __init__(self, reason: ConversionRefusal) -> None:
        super().__init__(f"{UNIT_CONVERSION_ID} refuses the {reason}")
        self.reason: ConversionRefusal = reason


def _admits(
    row: ConversionRow, target: str, component: str | None, molar_masses: Mapping[str, float]
) -> bool:
    if row.target_class == "component":
        return component is not None
    if row.target_class == "mass":
        return component is not None and component in molar_masses
    if row.target_class == "fraction":
        name = target.removeprefix("parameters.") if target.startswith("parameters.") else None
        return name is not None and name.split(".")[0] in FRACTION_PARAMETERS
    return True


@overload
def convert_input_value(
    input_id: str,
    value: float,
    unit: object,
    kind: object,
    required_kind: str | None,
    target: str,
    component: str | None,
    molar_masses: Mapping[str, float],
    source: ConversionSource = ...,
) -> tuple[float, UnitConversion | None]: ...


@overload
def convert_input_value(
    input_id: str,
    value: None,
    unit: object,
    kind: object,
    required_kind: str | None,
    target: str,
    component: str | None,
    molar_masses: Mapping[str, float],
    source: ConversionSource = ...,
) -> tuple[None, None]: ...


def convert_input_value(
    input_id: str,
    value: float | None,
    unit: object,
    kind: object,
    required_kind: str | None,
    target: str,
    component: str | None,
    molar_masses: Mapping[str, float],
    source: ConversionSource = "specification",
) -> tuple[float | None, UnitConversion | None]:
    """`unit-conversion-v2`: an input value in its target's SI unit, and the record of the
    conversion, `None` when there was none (ADR 0016 D4, steps V0–V5 in order).

    `kind` and `unit` are as declared; `required_kind` is the kind the target requires (`None`
    where no table names it); `target` is the target path (`state.T`, `parameters.split.C`, …),
    which decides whether a `%` row admits it; `component` is the target's component, if any;
    `molar_masses` is the id-keyed molecular-weight table, kg/mol. A `value` of `None` (a `role:
    free` specification that states no start) is checked and converts to `None`.

    The arithmetic is ADR 0016 D2: `SI = RN(a·D(v) + b)`, `D(v)` the shortest decimal that
    rounds to `v` (`repr`) read as an exact rational, `a` and `b` the row's exact constants (a
    mass row's `a` over `D(M_c)`), and **one** round-to-nearest-even to binary64 — CPython's
    `int / int` true division, which `Fraction.__float__` is. So two spellings of one quantity
    bind to one double, on every platform. A binary64 chain (`v * 1e-3`, `v + 273.15`) is not
    this function and `ref.closed_form.unit_conversion_v2.known_answers.rows` refuses it. A zero
    result is `+0.0`. The result is not bounds-checked: that is the downstream checks' business,
    as for an SI value. Raises `UnitConversionError`.
    """
    # V0: nonfinite.
    if value is not None and not isfinite(value):
        raise UnitConversionError("value")
    # V1: a path no table names — identity iff the unit is the declared kind's SI unit.
    if required_kind is None:
        if isinstance(kind, str) and unit == _KIND_SI_UNITS.get(kind):
            return value, None
        raise UnitConversionError("unit")
    # V2: the declared kind must be the one the target requires, or the mass basis of a
    # one-component flow.
    admitted = {required_kind}
    if required_kind == "molar_flow" and component is not None:
        admitted.add("mass_flow")
    if kind not in admitted:
        raise UnitConversionError("kind")
    si_unit = _KIND_SI_UNITS[required_kind]
    # V3: already SI.
    if kind == required_kind and unit == si_unit:
        return value, None
    # V4: a row of the table that admits the declared kind and the target.
    row = _ROWS.get((required_kind, unit)) if isinstance(unit, str) else None
    if (
        row is None
        or not isinstance(unit, str)
        or kind not in row.declared_kinds
        or not _admits(row, target, component, molar_masses)
    ):
        # V5.
        raise UnitConversionError("unit")
    if value is None:
        return None, None
    a = row.a
    molar_mass: float | None = None
    if row.rule == "mass_to_molar":
        assert component is not None
        molar_mass = molar_masses[component]
        a = a / Fraction(repr(molar_mass))
    try:
        si_value = float(a * Fraction(repr(value)) + row.b)
    except OverflowError:
        raise UnitConversionError("value") from None
    return si_value, UnitConversion(
        source=source,
        input_id=input_id,
        value=value,
        unit=unit,
        si_value=si_value,
        si_unit=si_unit,
        rule=row.rule,
        component=component if molar_mass is not None else None,
        molar_mass=molar_mass,
    )
