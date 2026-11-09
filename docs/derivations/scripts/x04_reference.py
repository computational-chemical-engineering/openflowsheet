"""Reference generator for X04, units at the boundary.

Authority: ADR 0075 and `docs/derivations/X04-test-specification.md`.

X04 converts SI values to display units on the way out (`display-conversion-v1`). This script is
the executable form of the specification's numbers: the output table, the presets, the
registered display states, the registered round trips, the sampled measurements and the
preference-grammar cases. It imports nothing from `openflowsheet`. Its inputs are exact
definitions written here, `schemas/units.json` (the frozen kind table) and the ADR 0016 table as
registered in `benchmarks/t06/reference_values.yaml` (`closed_form.unit_conversion_v2.rows`),
which it reads only to check that the rows X04 shares with the input direction are ADR 0016's.

The display rule (ADR 0075 D3), for an SI binary64 `X` of kind `k` shown in unit `u` with
`SI = a*u + b` (`a > 0`, `b` exact; a gauge row's `b` is `D(P_amb)`):

1. `q = (D(X) - b) / a` exactly, `D(X)` the shortest decimal that rounds to `X` (`repr`), and
   `v0 = RN(q)`; an `OverflowError` here means the value has no display (`display_out_of_range`).
2. If `RN(b) == X`, the display value is `+0.0`. Otherwise, for `p = 1, ..., 17`: `c_p` is `v0`
   rounded to `p` significant decimal digits (half-even, on the exact binary value of `v0`), read
   back as binary64; the first `c_p` with `RN(a*D(c_p) + b) == X` is the display value.
3. If no `p` qualifies, the display value is `v0`.

A zero display value is `+0.0`. `RN` is one round-to-nearest-even to binary64. Two independent
cross-checks back the emitted values: `rn` below rounds a rational by integer arithmetic and is
asserted equal to CPython's `float(Fraction)` on every rounding this script performs (claim C02),
and `shortest_in_preimage` finds the shortest displayable decimal of the interval of reals that
convert to `X` by enumerating that interval exactly, asserted equal to step 2's result on every
registered state whose result has at most 15 digits (claim C06) and empty for the registered
fallback (claim C16). Step 2 is not exhaustive: on SI doubles it can fall back where a longer
displayable preimage exists; the sample records how often (`fallbacks_with_a_displayable_preimage`).

Run from the repository root inside the project environment::

    python docs/derivations/scripts/x04_reference.py --check
    python docs/derivations/scripts/x04_reference.py \
        --emit docs/derivations/scripts/x04_reference.json

`--emit` is byte-reproducible. `--check` re-derives every claim and confirms that the committed
JSON is byte-identical to what `--emit` writes. The script refuses to emit if a claim fails.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import struct
import sys
from collections.abc import Callable, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JSON = Path(__file__).with_name("x04_reference.json")
UNITS_JSON = ROOT / "schemas" / "units.json"
T06_REFERENCE = ROOT / "benchmarks" / "t06" / "reference_values.yaml"

F = Fraction

#: The pound-force per square inch of the 1959 international definitions, Pa (ADR 0016 D3).
PSI = F("0.45359237") * F("9.80665") / F("0.0254") ** 2
#: 273.15 and 459.67 * 5/9: the offsets of the Celsius and Fahrenheit scales, K.
CELSIUS = F(5463, 20)
FAHRENHEIT = F(45967, 180)
GAUGE = "ambient"  # a gauge row's `b` is the project's declared ambient pressure

# ---------------------------------------------------------------- the kinds and the output table

#: The display kinds (ADR 0075 D2): every kind of `schemas/units.json`, and five kinds named by
#: ADR 0062 D1 (Proposed) that the stream table already carries. X04 does not register these
#: five as Quantity kinds; it uses ADR 0062's names, SI units and dimensions so that F2 landing
#: them changes nothing here (claim C10).
DISPLAY_ONLY_KINDS: dict[str, tuple[str, tuple[int, ...]]] = {
    "specific_enthalpy": ("J/kg", (2, 0, -2, 0, 0, 0, 0)),
    "specific_entropy": ("J/(kg K)", (2, 0, -2, -1, 0, 0, 0)),
    "molar_entropy": ("J/(mol K)", (2, 1, -2, -1, -1, 0, 0)),
    "enthalpy_flow": ("W", (2, 1, -3, 0, 0, 0, 0)),
    "mass_fraction": ("1", (0, 0, 0, 0, 0, 0, 0)),
}

#: ADR 0075 D2, in table order: (kind, unit, a, b). `SI = a * u + b`.
ROWS: tuple[tuple[str, str, Fraction, Fraction | str], ...] = (
    ("temperature", "degC", F(1), CELSIUS),
    ("temperature", "degF", F(5, 9), FAHRENHEIT),
    ("temperature_difference", "degC", F(1), F(0)),
    ("temperature_difference", "degF", F(5, 9), F(0)),
    ("pressure", "kPa", F(1000), F(0)),
    ("pressure", "MPa", F(10**6), F(0)),
    ("pressure", "bar", F(10**5), F(0)),
    ("pressure", "atm", F(101325), F(0)),
    ("pressure", "psi", PSI, F(0)),
    ("pressure", "barg", F(10**5), GAUGE),
    ("pressure", "psig", PSI, GAUGE),
    ("molar_flow", "kmol/s", F(1000), F(0)),
    ("molar_flow", "mmol/s", F(1, 1000), F(0)),
    ("molar_flow", "mol/h", F(1, 3600), F(0)),
    ("molar_flow", "kmol/h", F(5, 18), F(0)),
    ("mass_flow", "g/s", F(1, 1000), F(0)),
    ("mass_flow", "kg/h", F(1, 3600), F(0)),
    ("heat_rate", "kW", F(1000), F(0)),
    ("heat_rate", "MW", F(10**6), F(0)),
    ("power", "kW", F(1000), F(0)),
    ("power", "MW", F(10**6), F(0)),
    ("enthalpy_flow", "kW", F(1000), F(0)),
    ("enthalpy_flow", "MW", F(10**6), F(0)),
    ("molar_enthalpy", "kJ/mol", F(1000), F(0)),
    ("specific_enthalpy", "kJ/kg", F(1000), F(0)),
    ("molar_entropy", "kJ/(mol K)", F(1000), F(0)),
    ("specific_entropy", "kJ/(kg K)", F(1000), F(0)),
    ("dimensionless", "%", F(1, 100), F(0)),
    ("mole_fraction", "%", F(1, 100), F(0)),
    ("mass_fraction", "%", F(1, 100), F(0)),
)
ROW = {(kind, unit): (a, b) for kind, unit, a, b in ROWS}

#: ADR 0075 D5: the presets. `si` converts nothing; `eng` is the default of Frank question FQ2.
PRESETS: dict[str, dict[str, str]] = {
    "si": {},
    "eng": {
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
    },
}

#: The stream table's SI column suffixes (ST design note §6.3, the CSV header), which the suffix
#: rule of ADR 0075 D7 must reproduce (claim C12).
ST_SI_SUFFIXES = {
    "K": "K",
    "Pa": "Pa",
    "mol/s": "mol_s",
    "kg/s": "kg_s",
    "J/mol": "J_mol",
    "J/kg": "J_kg",
    "J/(mol K)": "J_molK",
    "J/(kg K)": "J_kgK",
    "m3/mol": "m3_mol",
    "kg/m3": "kg_m3",
    "W": "W",
    "W/K": "W_K",
    "m3/s": "m3_s",
}


def csv_suffix(unit: str) -> str:
    """ADR 0075 D7: `/` becomes `_`; `(`, `)` and spaces are dropped; `%` becomes `pct`."""
    return (unit.replace("/", "_").replace("(", "").replace(")", "").replace(" ", "")).replace(
        "%", "pct"
    )


# ------------------------------------------------------------------------------ the arithmetic


def decimal_of(x: float) -> Fraction:
    """D(x): the shortest decimal that rounds to `x` (CPython's `repr`), as an exact rational."""
    return F(repr(x))


def rn(q: Fraction) -> float:
    """One round-to-nearest-even of `q` to binary64, by integer arithmetic alone.

    Independent of `float(Fraction)`; claim C02 asserts the two agree on every rounding this
    script performs. Raises `OverflowError` when the result is not finite.
    """
    if q == 0:
        return 0.0
    sign = -1.0 if q < 0 else 1.0
    n, d = abs(q.numerator), q.denominator
    # The exponent e with 2^52 <= n / (d 2^e) < 2^53, then clamped to the subnormal floor.
    e = n.bit_length() - d.bit_length() - 53
    while True:
        num, den = (n, d << e) if e >= 0 else (n << -e, d)
        if num >= den << 53:
            e += 1
        elif num < den << 52:
            e -= 1
        else:
            break
    e = max(e, -1074)
    num, den = (n, d << e) if e >= 0 else (n << -e, d)
    m, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and m % 2 == 1):
        m += 1
    if m == 1 << 53:
        m, e = m >> 1, e + 1
    if e + 53 > 1024:
        raise OverflowError("not finite")
    return sign * math.ldexp(m, e)


ROUNDINGS: list[tuple[Fraction, float | None]] = []  # every rounding, for claim C02


def round_q(q: Fraction) -> float:
    try:
        value = rn(q)
    except OverflowError:
        ROUNDINGS.append((q, None))
        raise
    ROUNDINGS.append((q, value))
    return value + 0.0  # +0.0 for a zero


def offset(b: Fraction | str, ambient: float | None) -> Fraction:
    if b == GAUGE:
        assert ambient is not None, "a gauge row needs the declared ambient pressure"
        return decimal_of(ambient)
    assert isinstance(b, Fraction)
    return b


def to_si(value: float, kind: str, unit: str, ambient: float | None = None) -> float:
    """The row's arithmetic in the input direction, `RN(a*D(v) + b)` (ADR 0016 D2)."""
    a, b = ROW[(kind, unit)]
    return round_q(a * decimal_of(value) + offset(b, ambient))


def display(x: float, kind: str, unit: str, ambient: float | None = None) -> dict[str, Any]:
    """`display-conversion-v1` (ADR 0075 D3): the display value of `x`, how it was found, and
    the exact rational it approximates. `value` is `None` when the conversion overflows."""
    a, b = ROW[(kind, unit)]
    b = offset(b, ambient)
    q = (decimal_of(x) - b) / a
    try:
        v0 = round_q(q)
    except OverflowError:
        return {"value": None, "method": "out_of_range", "digits": None, "q": q}
    if round_q(b) == x:  # p = 0: zero, the shortest spelling of all
        return {"value": 0.0, "method": "preimage", "digits": 0, "q": q}
    for p in range(1, 18):
        candidate = float(format(v0, f".{p}g")) + 0.0
        if round_q(a * decimal_of(candidate) + b) == x:
            return {"value": candidate, "method": "preimage", "digits": p, "q": q}
    return {"value": v0, "method": "fallback", "digits": None, "q": q}


# ----------------------------------------------- the independent check: shortest preimage decimal


def _bits(x: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", x))[0]


def preimage(x: float, kind: str, unit: str, ambient: float | None) -> tuple[F, F, bool]:
    """The reals `u` with `RN(a*u + b) == x`: `[L, H]` (closed iff the significand of `x` is
    even, round-half-even's tie rule), from `x`'s rounding interval mapped through `(r - b)/a`."""
    a, b = ROW[(kind, unit)]
    b = offset(b, ambient)
    low = (F(math.nextafter(x, -math.inf)) + F(x)) / 2
    high = (F(x) + F(math.nextafter(x, math.inf))) / 2
    closed = _bits(x) % 2 == 0
    return (low - b) / a, (high - b) / a, closed


def _exponent10(u: Fraction) -> int:
    """floor(log10(u)) for a positive rational, exactly."""
    n, d = u.numerator, u.denominator
    e = len(str(n)) - len(str(d))
    while F(10) ** e > u:
        e -= 1
    while F(10) ** (e + 1) <= u:
        e += 1
    return e


def shortest_in_preimage(
    x: float, kind: str, unit: str, ambient: float | None, target: Fraction
) -> tuple[Fraction, int] | None:
    """The displayable decimal with the fewest significant digits (at most 17) in `preimage(x)`,
    nearest to `target` among those, and its digit count; `None` if there is none. A decimal is
    displayable when it is the shortest decimal of its own binary64, `D(RN(d)) == d`: only such a
    decimal can be a JSON number's spelling. Found by enumerating every p-digit decimal of the
    interval, not by rounding `v0` (an independent route to step 2's result)."""
    low, high, closed = preimage(x, kind, unit, ambient)

    def inside(u: Fraction) -> bool:
        return (low <= u <= high) if closed else (low < u < high)

    if inside(F(0)):
        return F(0), 1
    first = _exponent10(min(abs(low), abs(high))) - 1
    last = _exponent10(max(abs(low), abs(high))) + 1
    for p in range(1, 18):
        found: list[Fraction] = []
        for decade in range(first, last + 1):
            step = F(10) ** (decade - p + 1)
            k_low = math.ceil(low / step)
            k_high = math.floor(high / step)
            for k in range(k_low, k_high + 1):
                if (
                    10 ** (p - 1) <= abs(k) < 10**p
                    and inside(k * step)
                    and decimal_of(rn(k * step)) == k * step
                ):
                    found.append(k * step)
        if found:
            best = min(found, key=lambda u: (abs(u - target), u))
            return best, p
    return None


# --------------------------------------------------------------------------- registered states

AMBIENT_SEA = 101325.0
AMBIENT_SITE = 95000.0  # 0.95 bar: a site above sea level; a dropped ambient would show here


def _input(value: float, kind: str, unit: str, ambient: float | None = None) -> float:
    return to_si(value, kind, unit, ambient)


#: (id, X, kind, unit, ambient, expected display as written, why). `X` may be a callable that
#: computes the SI value from an input (registered so the state is what a user would enter).
DisplayState = tuple[str, float | Callable[[], float], str, str, float | None, str | None, str]

DISPLAY_STATES: tuple[DisplayState, ...] = (
    (
        "DS01",
        298.15,
        "temperature",
        "degC",
        None,
        "25.0",
        "offset row; reading X as its exact binary value, not D(X), gives 24.99999999999998",
    ),
    (
        "DS02",
        298.15,
        "temperature_difference",
        "degC",
        None,
        "298.15",
        "same X as DS01 under the difference kind: no offset (ADR 0001 D1.3)",
    ),
    (
        "DS03",
        273.15,
        "temperature",
        "degC",
        None,
        "0.0",
        "vanishes: the offset cancels exactly; +0.0",
    ),
    ("DS04", 233.15, "temperature", "degC", None, "-40.0", "negative Celsius"),
    (
        "DS05",
        233.15,
        "temperature",
        "degF",
        None,
        "-40.0",
        "the Celsius/Fahrenheit crossing: a swapped or mis-signed offset moves it",
    ),
    ("DS06", 300.0, "temperature", "degF", None, "80.33", "Fahrenheit offset and scale"),
    (
        "DS07",
        310.0,
        "temperature_difference",
        "degF",
        None,
        "558.0",
        "difference kind: scale 9/5 only",
    ),
    (
        "DS08",
        310.0,
        "temperature",
        "degF",
        None,
        "98.33",
        "same X as DS07 under the absolute kind: 558 - 459.67",
    ),
    ("DS09", 10.0, "temperature_difference", "degC", None, "10.0", "difference: identity scale"),
    (
        "DS10",
        lambda: _input(25.0, "temperature", "degF"),
        "temperature",
        "degF",
        None,
        "25.0",
        "a user's 25 degF reads back as 25; RN(q) alone gives 24.99999999999998",
    ),
    ("DS11", 101325.0, "pressure", "bar", None, "1.01325", "bar"),
    ("DS12", 101325.0, "pressure", "atm", None, "1.0", "atm"),
    ("DS13", 101325.0, "pressure", "kPa", None, "101.325", "kPa"),
    (
        "DS14",
        101325.0,
        "pressure",
        "psi",
        None,
        None,
        "psi: a non-terminating scale; the value is whatever step 2 or 3 gives (emitted)",
    ),
    ("DS15", 101325.0, "pressure", "barg", AMBIENT_SEA, "0.0", "gauge at the ambient: vanishes"),
    ("DS16", 101325.0, "pressure", "psig", AMBIENT_SEA, "0.0", "psig at the ambient: vanishes"),
    (
        "DS17",
        101325.0,
        "pressure",
        "barg",
        AMBIENT_SITE,
        "0.06325",
        "the same X at another declared ambient: the ambient is read, not assumed",
    ),
    ("DS18", 301325.0, "pressure", "barg", AMBIENT_SEA, "2.0", "gauge above ambient"),
    (
        "DS19",
        50000.0,
        "pressure",
        "barg",
        AMBIENT_SEA,
        "-0.51325",
        "gauge below ambient: negative (vacuum)",
    ),
    (
        "DS20",
        10000.0,
        "pressure",
        "bar",
        None,
        "0.1",
        "MSG's isentropic_state_two_phase pressure (tests/test_msg_engine.py)",
    ),
    ("DS21", 10000.0, "pressure", "barg", AMBIENT_SEA, "-0.91325", "the same, gauge"),
    ("DS22", 5000000.0, "pressure", "MPa", None, "5.0", "MSG's pressure_rise p_spec, MPa"),
    ("DS23", 3000000.0, "pressure", "bar", None, "30.0", "MSG's pressure_rise p_inlet, bar"),
    (
        "DS24",
        lambda: _input(30.0, "pressure", "psig", AMBIENT_SEA),
        "pressure",
        "psig",
        AMBIENT_SEA,
        "30.0",
        "a user's 30 psig reads back as 30; RN(q) alone gives 30.000000000000004",
    ),
    (
        "DS25",
        lambda: _input(1.0, "molar_flow", "kmol/h"),
        "molar_flow",
        "kmol/h",
        None,
        "1.0",
        "1 kmol/h = 5/18 mol/s, a non-terminating scale, reads back as 1",
    ),
    ("DS26", 1.0, "molar_flow", "kmol/h", None, "3.6", "kmol/h"),
    ("DS27", 1.0, "molar_flow", "mol/h", None, "3600.0", "mol/h"),
    ("DS28", 1.0, "molar_flow", "kmol/s", None, "0.001", "kmol/s"),
    ("DS29", 1.0, "molar_flow", "mmol/s", None, "1000.0", "mmol/s"),
    ("DS30", 1.0, "mass_flow", "kg/h", None, "3600.0", "kg/h"),
    ("DS31", 1.0, "mass_flow", "g/s", None, "1000.0", "g/s"),
    (
        "DS32",
        -16144.6,
        "heat_rate",
        "kW",
        None,
        "-16.1446",
        "a negative duty (ADR 0001 D4.2): the sign survives",
    ),
    ("DS33", -16144.6, "power", "MW", None, "-0.0161446", "power, MW"),
    ("DS34", 2627345.1, "enthalpy_flow", "kW", None, "2627.3451", "enthalpy flow, kW"),
    (
        "DS35",
        47330.0,
        "molar_enthalpy",
        "kJ/mol",
        None,
        "47.33",
        "MSG's phase_regime_mismatch value",
    ),
    (
        "DS36",
        749161.585,
        "specific_enthalpy",
        "kJ/kg",
        None,
        "749.161585",
        "ST's water h' (ST design note O7)",
    ),
    (
        "DS37",
        139.7797844964916,
        "molar_entropy",
        "kJ/(mol K)",
        None,
        "0.1397797844964916",
        "MSG's s_star: 16 significant digits survive the shift",
    ),
    ("DS38", 2108.65845, "specific_entropy", "kJ/(kg K)", None, "2.10865845", "ST's s'"),
    ("DS39", 0.25, "mole_fraction", "%", None, "25.0", "%"),
    ("DS40", 0.25, "mass_fraction", "%", None, "25.0", "% on the mass basis"),
    ("DS41", 0.912345, "dimensionless", "%", None, "91.2345", "a vapour fraction in %"),
    ("DS42", 0.0, "molar_flow", "kmol/h", None, "0.0", "a dormant flow: +0.0"),
    ("DS43", 0.0, "heat_rate", "kW", None, "0.0", "zero duty: +0.0"),
    (
        "DS44",
        5e-324,
        "pressure",
        "MPa",
        None,
        "0.0",
        "a nonzero SI value that rounds to zero in MPa (underflow); registered because it vanishes",
    ),
    (
        "DS45",
        1e305,
        "molar_flow",
        "mol/h",
        None,
        None,
        "3.6e308 overflows: no display value (display_out_of_range)",
    ),
    (
        "DS46",
        1e305,
        "molar_flow",
        "kmol/h",
        None,
        "3.6e+305",
        "the same X in a smaller multiple stays finite",
    ),
    (
        "DS47",
        1.7976931348623157e308,
        "mass_flow",
        "kg/h",
        None,
        None,
        "the largest double, kg/h: out of range",
    ),
    (
        "DS48",
        5000000.0,
        "pressure",
        "barg",
        AMBIENT_SEA,
        "48.98675",
        "MSG's pressure_rise p_spec, gauge (test specification A27)",
    ),
    (
        "DS49",
        3000000.0,
        "pressure",
        "barg",
        AMBIENT_SEA,
        "28.98675",
        "MSG's pressure_rise p_inlet, gauge (A27)",
    ),
    (
        "DS50",
        146.80317968321518,
        "molar_entropy",
        "kJ/(mol K)",
        None,
        "0.14680317968321518",
        "MSG's s_saturated (A25): 17 significant digits survive the shift",
    ),
)
#: DS14 and the fallback state: no hand-written decimal; the emitted value is registered.
FALLBACK_SEED = 20261109


def find_fallback() -> tuple[float, str, str]:
    """The first X of a seeded sequence of molar flows whose kmol/h display falls back (step 3)
    and for which no binary64 at all converts back (enumeration finds no displayable decimal in
    the preimage interval): registered so that the fallback path has a known answer."""
    generator = random.Random(FALLBACK_SEED)
    for _ in range(10_000):
        x = generator.uniform(0.01, 100.0)
        result = display(x, "molar_flow", "kmol/h")
        if result["method"] == "fallback" and (
            shortest_in_preimage(x, "molar_flow", "kmol/h", None, result["q"]) is None
        ):
            return x, "molar_flow", "kmol/h"
    raise AssertionError("no fallback in 10000 draws")


def display_table() -> list[dict[str, Any]]:
    rows = []
    states = list(DISPLAY_STATES)
    x, kind, unit = find_fallback()
    states.append(
        (
            "DS51",
            x,
            kind,
            unit,
            None,
            None,
            "seeded: no binary64 converts back to X (checked by enumeration); step 3's v0",
        )
    )
    for ident, value, kind, unit, ambient, expected, why in states:
        x = value() if callable(value) else value
        result = display(x, kind, unit, ambient)
        got = result["value"]
        if expected is not None:
            assert got is not None and repr(got) == expected, (ident, got, expected)
        assert got is None or got != 0.0 or math.copysign(1.0, got) == 1.0, ident
        back = None if got is None else to_si(got, kind, unit, ambient)
        rows.append(
            {
                "id": ident,
                "si_value": repr(x),
                "kind": kind,
                "unit": unit,
                "ambient_pressure": None if ambient is None else repr(ambient),
                "q": f"{result['q'].numerator}/{result['q'].denominator}",
                "display_value": None if got is None else repr(got),
                "method": result["method"],
                "digits": result["digits"],
                "converts_back_to_si": None if back is None else back == x,
                "why": why,
            }
        )
    return rows


#: The registered round trips: ADR 0016's shared rows (all but the mass basis) and the two gauge
#: rows, each with every value of `ROUND_TRIP_VALUES` whose SI value is admissible.
ROUND_TRIP_VALUES = (
    25.0,
    -40.0,
    0.01,
    12.34,
    1.5,
    100.0,
    0.001,
    0.1,
    75.1,
    26.85,
    1.01325,
    14.6959,
    3600.0,
    0.5,
    1.0,
    2.0,
    30.0,
    0.0,
)


def round_trips() -> list[dict[str, Any]]:
    out = []
    for kind, unit, _a, b in ROWS:
        if kind not in T06_KINDS and b != GAUGE:
            continue
        ambients = (AMBIENT_SEA, AMBIENT_SITE) if b == GAUGE else (None,)
        for ambient in ambients:
            for v in ROUND_TRIP_VALUES:
                x = to_si(v, kind, unit, ambient)
                if kind in ("temperature", "pressure") and x <= 0.0:
                    continue
                result = display(x, kind, unit, ambient)
                plain = round_q(result["q"])
                out.append(
                    {
                        "kind": kind,
                        "unit": unit,
                        "ambient_pressure": None if ambient is None else repr(ambient),
                        "input": repr(v),
                        "si_value": repr(x),
                        "display_value": repr(result["value"]),
                        "plain_rounding": repr(plain),
                    }
                )
    return out


# ------------------------------------------------------------------------- sampled measurements

SAMPLE_SEED = 20261109
SAMPLE_PER_DIGITS = 100
SAMPLE_DIGITS = range(1, 18)
GUARANTEED_DIGITS = 10  # the claim: no round-trip failure with this many digits or fewer


def _sample_value(generator: random.Random, digits: int) -> float:
    """A decimal with `digits` significant digits in [1e-4, 1e6), either sign."""
    mantissa = generator.randrange(10 ** (digits - 1), 10**digits)
    exponent = generator.randrange(-6, 4)
    sign = generator.choice((1, -1))
    return float(F(sign * mantissa) * F(10) ** (exponent - digits + 3))


def sampled() -> dict[str, Any]:
    """Round trips input -> SI -> display on a seeded sample, per row and digit count, with the
    plain rounding `RN(q)` beside step 2's search; and the fallback rate on SI doubles."""
    generator = random.Random(SAMPLE_SEED)
    per_row = []
    for kind, unit, _a, b in ROWS:
        ambient = AMBIENT_SEA if b == GAUGE else None
        search_fail: dict[str, int] = {}
        plain_fail: dict[str, int] = {}
        drawn = 0
        for digits in SAMPLE_DIGITS:
            failures = plains = 0
            for _ in range(SAMPLE_PER_DIGITS):
                v = _sample_value(generator, digits)
                x = to_si(v, kind, unit, ambient)
                if kind == "temperature" and x <= 0.0:
                    continue
                drawn += 1
                result = display(x, kind, unit, ambient)
                failures += result["value"] != v
                plains += round_q(result["q"]) != v
            if failures:
                search_fail[str(digits)] = failures
            if plains:
                plain_fail[str(digits)] = plains
        fallback = missed = violations = 0
        for _ in range(SAMPLE_PER_DIGITS * 4):
            if kind == "temperature":
                x = generator.uniform(200.0, 800.0)
            else:
                x = math.ldexp(generator.random() + 0.5, generator.randrange(-30, 40))
            result = display(x, kind, unit, ambient)
            a_row = ROW[(kind, unit)][0]
            shown = result["value"]
            if abs(F(shown) - result["q"]) > F(math.ulp(x)) / a_row + F(math.ulp(shown)) / 2:
                violations += 1
            if result["method"] == "fallback":
                fallback += 1
                if shortest_in_preimage(x, kind, unit, ambient, result["q"]) is not None:
                    missed += 1
        per_row.append(
            {
                "kind": kind,
                "unit": unit,
                "inputs_drawn": drawn,
                "search_round_trip_failures_by_digits": search_fail,
                "plain_rounding_failures_by_digits": plain_fail,
                "si_doubles_drawn": SAMPLE_PER_DIGITS * 4,
                "fallbacks": fallback,
                "fallbacks_with_a_displayable_preimage": missed,
                "bound_violations": violations,
            }
        )
    return {
        "seed": SAMPLE_SEED,
        "per_digit_count": SAMPLE_PER_DIGITS,
        "input_domain": "decimals of 1..17 significant digits, magnitude in [1e-4, 1e6), either "
        "sign; temperatures whose SI value is not positive are skipped",
        "si_domain": "temperature: uniform [200, 800] K; others: 2^[-30, 40) times [0.5, 1.5)",
        "gauge_ambient_pressure": repr(AMBIENT_SEA),
        "rows": per_row,
    }


# ---------------------------------------------------------------------- the preference grammar

ALL_KINDS: dict[str, tuple[str, tuple[int, ...]]] = {}  # filled from units.json in load()
T06_KINDS: set[str] = set()  # the kinds of ADR 0016's table, filled in load()


def parse(text: str, ambient: float | None) -> dict[str, Any]:
    """ADR 0075 D5: the resolved preference, or the refusal: its ApiError code, its reason code
    and the message head (D9: `code(arg): "<text>"`, the user's text JSON-quoted so that the MSG
    legacy grammar never reads it as a code)."""

    def refuse(api: str, reason: str, arg: str | int, quoted: str) -> dict[str, Any]:
        message = f"{reason}({arg}): {json.dumps(quoted, ensure_ascii=False)}"
        return {"refused": {"api_error": api, "reason": reason, "message": message}}

    if text == "" or len(text) > 1024:
        return {
            "refused": {
                "api_error": "invalid_request",
                "reason": "schema",
                "pointer": "/display_units",
            }
        }
    items = [item.strip(" ") for item in text.split(",")]
    resolved: dict[str, str] = {}
    explicit: dict[str, str] = {}
    for index, item in enumerate(items):
        if item in PRESETS:
            if index != 0:
                return refuse("invalid_request", "display_units_invalid", index, item)
            resolved.update(PRESETS[item])
            continue
        kind, separator, unit = item.partition("=")
        kind, unit = kind.strip(" "), unit.strip(" ")
        if not separator or not kind or not unit or kind not in ALL_KINDS or kind in explicit:
            return refuse("invalid_request", "display_units_invalid", index, item)
        explicit[kind] = unit
        if unit == ALL_KINDS[kind][0]:
            resolved.pop(kind, None)
        elif (kind, unit) in ROW:
            resolved[kind] = unit
        else:
            return refuse("unsupported", "display_unit_unsupported", kind, unit)
    gauge = sorted(k for k, u in resolved.items() if ROW[(k, u)][1] == GAUGE)
    if gauge and ambient is None:
        kind = gauge[0]
        return refuse("invalid_request", "ambient_pressure_undeclared", kind, resolved[kind])
    return {
        "units": dict(sorted(resolved.items())),
        "ambient_pressure": None if not gauge else repr(ambient),
    }


ENG = dict(sorted(PRESETS["eng"].items()))

#: ADR 0075 D6.2: the operator command's conversion of a declared ambient pressure, by ADR 0016's
#: arithmetic on an absolute pressure row; (id, value, unit, expected Pa as repr or the refusal
#: reason, why). Written by hand; claim C17 asserts `declare` agrees.
AMBIENT_ROWS = ("Pa", "kPa", "MPa", "bar", "atm", "psi")
AMBIENT_DECLARATIONS: tuple[tuple[str, float, str, str, str], ...] = (
    ("AD01", 1.0, "atm", "101325.0", "one standard atmosphere"),
    ("AD02", 0.95, "bar", "95000.0", "a site above sea level (the DS17 ambient)"),
    ("AD03", 14.6959, "psi", "101324.66370467292", "a non-terminating scale"),
    ("AD04", 101325.0, "Pa", "101325.0", "the SI unit: identity"),
    ("AD05", 101.325, "kPa", "101325.0", "kPa"),
    ("AD06", 0.0, "bar", "refused:value", "an absolute pressure is positive"),
    ("AD07", -1.0, "bar", "refused:value", "negative"),
    ("AD08", math.nan, "bar", "refused:value", "not finite"),
    ("AD09", math.inf, "bar", "refused:value", "not finite"),
    ("AD10", 1e304, "MPa", "refused:value", "1e310 Pa overflows"),
    ("AD11", 1.0, "barg", "refused:unit", "a gauge unit cannot declare the ambient"),
    ("AD12", 760.0, "mmHg", "refused:unit", "not a row (ADR 0016 D8)"),
    ("AD13", 1.0, "bara", "refused:unit", "one spelling per unit"),
)


def declare(value: float, unit: str) -> str:
    """D6.2: the ambient in Pa as repr, or `refused:<reason>`."""
    if unit not in AMBIENT_ROWS:
        return "refused:unit"
    if not math.isfinite(value):
        return "refused:value"
    try:
        pascal = value if unit == "Pa" else to_si(value, "pressure", unit)
    except OverflowError:
        return "refused:value"
    if not pascal > 0.0:
        return "refused:value"
    return repr(pascal)


#: (id, text, ambient, expected, why). `expected` is written by hand; claim C14 asserts `parse`
#: agrees with every one.
PREFERENCES: tuple[tuple[str, str, float | None, dict[str, Any], str], ...] = (
    ("PU01", "eng", None, {"units": ENG, "ambient_pressure": None}, "the preset"),
    ("PU02", "si", None, {"units": {}, "ambient_pressure": None}, "converts nothing"),
    (
        "PU03",
        "eng,temperature=degF",
        None,
        {"units": {**ENG, "temperature": "degF"}, "ambient_pressure": None},
        "an explicit item overrides the preset's entry",
    ),
    (
        "PU04",
        " eng , temperature = degF ",
        None,
        {"units": {**ENG, "temperature": "degF"}, "ambient_pressure": None},
        "spaces around items and around '=' are dropped",
    ),
    (
        "PU05",
        "eng,temperature=K",
        None,
        {"units": {k: v for k, v in ENG.items() if k != "temperature"}, "ambient_pressure": None},
        "the SI unit removes the kind: nothing to convert",
    ),
    (
        "PU06",
        "temperature=degC,pressure=barg",
        AMBIENT_SEA,
        {"units": {"pressure": "barg", "temperature": "degC"}, "ambient_pressure": "101325.0"},
        "gauge with a declared ambient: the ambient is echoed",
    ),
    (
        "PU07",
        "temperature=degC,pressure=barg",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "ambient_pressure_undeclared",
                "message": 'ambient_pressure_undeclared(pressure): "barg"',
            }
        },
        "gauge without a declared ambient is refused, never assumed",
    ),
    (
        "PU08",
        "eng",
        AMBIENT_SEA,
        {"units": ENG, "ambient_pressure": None},
        "a declared ambient a preference does not use is not echoed",
    ),
    (
        "PU09",
        "temperature=degC,temperature=degF",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "display_units_invalid",
                "message": 'display_units_invalid(1): "temperature=degF"',
            }
        },
        "a kind named twice",
    ),
    (
        "PU10",
        "temperature=celsius",
        None,
        {
            "refused": {
                "api_error": "unsupported",
                "reason": "display_unit_unsupported",
                "message": 'display_unit_unsupported(temperature): "celsius"',
            }
        },
        "a unit not in the table for a known kind",
    ),
    (
        "PU11",
        "temperature=°C",
        None,
        {
            "refused": {
                "api_error": "unsupported",
                "reason": "display_unit_unsupported",
                "message": 'display_unit_unsupported(temperature): "°C"',
            }
        },
        "aliases are not rows (ADR 0016 Q14 stands)",
    ),
    (
        "PU12",
        "temp=degC",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "display_units_invalid",
                "message": 'display_units_invalid(0): "temp=degC"',
            }
        },
        "an unknown kind",
    ),
    (
        "PU13",
        "temperature_difference=barg",
        AMBIENT_SEA,
        {
            "refused": {
                "api_error": "unsupported",
                "reason": "display_unit_unsupported",
                "message": 'display_unit_unsupported(temperature_difference): "barg"',
            }
        },
        "a unit of another kind",
    ),
    (
        "PU14",
        "temperature=degC,eng",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "display_units_invalid",
                "message": 'display_units_invalid(1): "eng"',
            }
        },
        "a preset only first",
    ),
    (
        "PU15",
        "eng,si",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "display_units_invalid",
                "message": 'display_units_invalid(1): "si"',
            }
        },
        "one preset",
    ),
    (
        "PU16",
        "",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "schema",
                "pointer": "/display_units",
            }
        },
        "the empty string fails the request schema (minLength 1)",
    ),
    (
        "PU17",
        "temperature",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "display_units_invalid",
                "message": 'display_units_invalid(0): "temperature"',
            }
        },
        "no '='",
    ),
    (
        "PU18",
        "temperature=",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "display_units_invalid",
                "message": 'display_units_invalid(0): "temperature="',
            }
        },
        "an empty unit",
    ),
    (
        "PU19",
        "molar_heat_capacity=kJ/(mol K)",
        None,
        {
            "refused": {
                "api_error": "unsupported",
                "reason": "display_unit_unsupported",
                "message": 'display_unit_unsupported(molar_heat_capacity): "kJ/(mol K)"',
            }
        },
        "a known kind with no display rows",
    ),
    (
        "PU20",
        "pressure=bara",
        None,
        {
            "refused": {
                "api_error": "unsupported",
                "reason": "display_unit_unsupported",
                "message": 'display_unit_unsupported(pressure): "bara"',
            }
        },
        "one spelling per unit (ADR 0016 D8)",
    ),
    (
        "PU21",
        "mole_fraction=%,mass_fraction=%,dimensionless=%",
        None,
        {
            "units": {"dimensionless": "%", "mass_fraction": "%", "mole_fraction": "%"},
            "ambient_pressure": None,
        },
        "percent on the three fraction kinds",
    ),
    (
        "PU22",
        "molar_entropy=kJ/(mol K),specific_entropy=kJ/(kg K)",
        None,
        {
            "units": {"molar_entropy": "kJ/(mol K)", "specific_entropy": "kJ/(kg K)"},
            "ambient_pressure": None,
        },
        "units with spaces and parentheses",
    ),
    (
        "PU23",
        "eng,pressure=psig",
        AMBIENT_SITE,
        {"units": {**ENG, "pressure": "psig"}, "ambient_pressure": "95000.0"},
        "a preset with a gauge override",
    ),
    (
        "PU24",
        "kmol/h",
        None,
        {
            "refused": {
                "api_error": "invalid_request",
                "reason": "display_units_invalid",
                "message": 'display_units_invalid(0): "kmol/h"',
            }
        },
        "a bare unit is neither a preset nor an item",
    ),
)


# ------------------------------------------------------------------------------------- loading


def load() -> list[dict[str, Any]]:
    units = json.loads(UNITS_JSON.read_text(encoding="utf-8"))
    for kind, entry in units["kinds"].items():
        ALL_KINDS[kind] = (entry["si_unit"], tuple(entry["dimension"]))
    for kind, (si_unit, dimension) in DISPLAY_ONLY_KINDS.items():
        if kind in ALL_KINDS:  # F2 landed it: it must be the same kind (claim C10)
            assert ALL_KINDS[kind] == (si_unit, dimension), f"C10 {kind}"
        else:
            ALL_KINDS[kind] = (si_unit, dimension)
    reference = yaml.safe_load(T06_REFERENCE.read_text(encoding="utf-8"))
    rows = reference["closed_form"]["unit_conversion_v2"]["rows"]
    for row in rows:
        T06_KINDS.add(row["required_kind"])
    return rows


# -------------------------------------------------------------------------------------- claims


def claims(
    t06_rows: list[dict[str, Any]],
    states: list[dict[str, Any]],
    trips: list[dict[str, Any]],
    sample: dict[str, Any],
) -> dict[str, str]:
    out: dict[str, str] = {}

    # C01 the table is well formed: a > 0, keyed uniquely, every kind a display kind, SI unit
    # never a row, gauge rows only on pressure.
    keys = [(kind, unit) for kind, unit, _a, _b in ROWS]
    assert len(keys) == len(set(keys)), "C01 unique"
    for kind, unit, a, b in ROWS:
        assert a > 0 and kind in ALL_KINDS and unit != ALL_KINDS[kind][0], f"C01 {kind} {unit}"
        assert b != GAUGE or kind == "pressure", f"C01 gauge {kind}"
    out["C01"] = (
        f"{len(ROWS)} rows, unique (kind, unit), a > 0, no SI identity row, gauge on pressure only"
    )

    # C02 the independent rounding equals CPython's on every rounding performed.
    for q, value in ROUNDINGS:
        try:
            cpython: float | None = float(q)
        except OverflowError:
            cpython = None
        if cpython is None or value is None:
            assert cpython is value, f"C02 {q}"
        else:
            assert _bits(cpython + 0.0) == _bits(value + 0.0), f"C02 {q}"
    out["C02"] = f"rn (integer arithmetic) equals float(Fraction) on all {len(ROUNDINGS)} roundings"

    # C03 the rows X04 shares with ADR 0016 are ADR 0016's, and on ADR 0016's kinds the output
    # table is ADR 0016's non-mass rows plus the two gauge rows.
    t06 = {}
    t06_mass = {}
    for row in t06_rows:
        key = (row["required_kind"], row["unit"])
        if row["rule"] == "mass_to_molar":
            t06_mass[row["unit"]] = F(row["a"])
        else:
            t06[key] = (F(row["a"]), F(row["b"]))
    ours = {key: ab for key, ab in ROW.items() if key[0] in T06_KINDS and ab[1] != GAUGE}
    assert ours == t06, "C03 shared rows"
    gauges = sorted(key for key, ab in ROW.items() if ab[1] == GAUGE)
    assert gauges == [("pressure", "barg"), ("pressure", "psig")], "C03 gauges"
    out["C03"] = (
        f"the {len(t06)} non-mass rows of ADR 0016 D3 (read from benchmarks/t06) are exactly the "
        "output rows on ADR 0016's kinds, gauge rows (barg, psig) aside; a and b equal"
    )

    # C04 the mass-flow display rows have ADR 0016's mass factors.
    for unit in ("g/s", "kg/h"):
        assert ROW[("mass_flow", unit)][0] == t06_mass[unit], f"C04 {unit}"
    assert t06_mass["kg/s"] == 1, "C04 kg/s"
    out["C04"] = "mass_flow g/s and kg/h scale by ADR 0016's mass-row factors (1/1000, 1/3600)"

    # C05 every registered state: the hand-written decimal (where given) is the result; a
    # preimage result converts back to X; a fallback is RN(q); zero is +0.0.
    for state in states:
        if state["method"] == "preimage":
            assert state["converts_back_to_si"] is True, f"C05 {state['id']}"
        if state["method"] == "fallback":
            assert float(F(state["q"])) == float(state["display_value"]), f"C05 {state['id']}"
        if state["display_value"] is not None and float(state["display_value"]) == 0.0:
            assert state["display_value"] == "0.0", f"C05 sign {state['id']}"
    methods = sorted({s["method"] for s in states})
    assert methods == ["fallback", "out_of_range", "preimage"], f"C05 {methods}"
    out["C05"] = (
        f"{len(states)} display states: hand-written values reproduced; every preimage result "
        "converts back to X bit for bit; the fallback is RN(q); zeros are +0.0; all three "
        "methods occur"
    )

    # C06 two routes agree where the decimal is short: on every registered state whose step 2
    # result has at most 15 digits, it is the shortest displayable decimal of the preimage
    # interval found by enumerating that interval (exact interval arithmetic, rn, no search).
    checked = 0
    for state in states:
        if state["method"] != "preimage" or state["digits"] > 15:
            continue
        x = float(state["si_value"])
        ambient = None if state["ambient_pressure"] is None else float(state["ambient_pressure"])
        found = shortest_in_preimage(x, state["kind"], state["unit"], ambient, F(state["q"]))
        assert found is not None, f"C06 {state['id']}"
        assert decimal_of(float(state["display_value"])) == found[0], f"C06 {state['id']}"
        checked += 1
    out["C06"] = (
        f"on all {checked} registered preimage states of at most 15 digits, step 2's value is the "
        "shortest displayable decimal of the interval of reals converting to X, found by "
        "enumerating the interval exactly"
    )

    # C16 the registered fallback is a true one: no displayable decimal in its interval.
    fallback = next(s for s in states if s["id"] == "DS51")
    assert fallback["method"] == "fallback", "C16"
    assert (
        shortest_in_preimage(
            float(fallback["si_value"]), "molar_flow", "kmol/h", None, F(fallback["q"])
        )
        is None
    ), "C16 enumeration"
    out["C16"] = (
        "DS51 falls back and enumeration of its preimage interval finds no displayable decimal: "
        "no binary64 converts back to its X"
    )

    # C17 the ambient declarations agree with the hand-written expectations.
    for ident, value, unit, expected, _why in AMBIENT_DECLARATIONS:
        assert declare(value, unit) == expected, f"C17 {ident}: {declare(value, unit)}"
    out["C17"] = (
        f"all {len(AMBIENT_DECLARATIONS)} ambient declarations (D6.2) give the hand-written Pa "
        "value or refusal reason"
    )

    # C07 every registered round trip returns its input; the plain rounding RN(q) does not
    # always (the reason for step 2).
    assert all(t["display_value"] == t["input"] for t in trips), "C07"
    plain_misses = sum(t["plain_rounding"] != t["input"] for t in trips)
    assert plain_misses > 0, "C07 plain"
    out["C07"] = (
        f"all {len(trips)} registered round trips input -> SI -> display return the input bit "
        f"for bit; RN(q) alone misses {plain_misses} of them"
    )

    # C08 sampled: no round-trip failure at GUARANTEED_DIGITS or fewer, on any row.
    for row in sample["rows"]:
        for digits in row["search_round_trip_failures_by_digits"]:
            assert int(digits) > GUARANTEED_DIGITS, f"C08 {row['kind']} {row['unit']} {digits}"
    out["C08"] = (
        f"on the seeded sample every input of at most {GUARANTEED_DIGITS} significant digits "
        "round-trips on every row (failures by digit count are emitted, all above "
        f"{GUARANTEED_DIGITS})"
    )

    # C09 the display error is bounded by X's own resolution plus half an ulp of the display
    # value: |display - q| <= ulp(X)/a + ulp(display)/2, on every registered state and sample.
    def within(x: float, kind: str, unit: str, shown: float, q: Fraction) -> bool:
        a = ROW[(kind, unit)][0]
        return abs(F(shown) - q) <= F(math.ulp(x)) / a + F(math.ulp(shown)) / 2

    for state in states:
        if state["display_value"] is not None:
            assert within(
                float(state["si_value"]),
                state["kind"],
                state["unit"],
                float(state["display_value"]),
                F(state["q"]),
            ), f"C09 {state['id']}"
    assert all(row["bound_violations"] == 0 for row in sample["rows"]), "C09 sample"
    out["C09"] = (
        "|display - q| <= ulp(X)/a + ulp(display)/2 on every registered state and every sampled "
        "SI double"
    )

    # C10 the five display-only kinds are ADR 0062 D1's (or units.json's once F2 lands).
    out["C10"] = (
        "specific_enthalpy, specific_entropy, molar_entropy, enthalpy_flow, mass_fraction: "
        "SI unit and dimension as ADR 0062 D1; equal to units.json wherever units.json has them"
    )

    # C11 presets name only display kinds and table units, and no gauge unit.
    for name, mapping in PRESETS.items():
        for kind, unit in mapping.items():
            assert (kind, unit) in ROW and ROW[(kind, unit)][1] != GAUGE, f"C11 {name} {kind}"
    out["C11"] = "every preset entry is a table row and none is a gauge unit"

    # C12 the CSV suffix rule reproduces ST's SI suffixes and is injective per kind.
    for unit, suffix in ST_SI_SUFFIXES.items():
        assert csv_suffix(unit) == suffix, f"C12 {unit}"
    for kind in ALL_KINDS:
        units = [ALL_KINDS[kind][0]] + [u for k, u in ROW if k == kind]
        suffixes = [csv_suffix(u) for u in units]
        assert len(suffixes) == len(set(suffixes)), f"C12 {kind}"
        assert all(s and s.replace("_", "").isalnum() for s in suffixes), f"C12 chars {kind}"
    out["C12"] = (
        "the suffix rule gives ST's 13 SI suffixes exactly; per kind the suffixes of the SI unit "
        "and every row are distinct and alphanumeric with underscores"
    )

    # C13 every grammar refusal's message head parses under MSG's legacy grammar as one code
    # segment whose args hold no parenthesis or comma, followed by a JSON-quoted detail.
    head = re.compile(r'^([a-z]+(?:_[a-z]+)+)\(([A-Za-z0-9_]+)\): "(.*)"$')
    for ident, _text, _ambient, expected, _why in PREFERENCES:
        refused = expected.get("refused")
        if refused and refused["reason"] != "schema":
            match = head.match(refused["message"])
            assert match is not None and match.group(1) == refused["reason"], f"C13 {ident}"
    out["C13"] = (
        'every grammar refusal\'s message is `code(arg): "<text>"` with an identifier or '
        "integer arg, so MSG's legacy grammar reads exactly one code"
    )

    # C14 the grammar agrees with every hand-written preference expectation.
    for ident, text, ambient, expected, _why in PREFERENCES:
        assert parse(text, ambient) == expected, f"C14 {ident}: {parse(text, ambient)}"
    out["C14"] = f"parse agrees with all {len(PREFERENCES)} hand-written preference cases"

    # C15 distinctness: the registered states that pair one X under two kinds or two ambients
    # give different values (a dropped offset, a swapped kind or an ignored ambient is caught).
    by_id = {s["id"]: s["display_value"] for s in states}
    for left, right in (
        ("DS01", "DS02"),
        ("DS07", "DS08"),
        ("DS15", "DS17"),
        ("DS04", "DS06"),
        ("DS11", "DS15"),
        ("DS45", "DS46"),
    ):
        assert by_id[left] != by_id[right], f"C15 {left} {right}"
    out["C15"] = (
        "paired states differ: DS01/DS02 (kind), DS07/DS08 (kind), DS15/DS17 (ambient), "
        "DS11/DS15 (gauge), DS45/DS46 (range), DS04/DS06"
    )
    return out


def document() -> dict[str, Any]:
    ROUNDINGS.clear()
    ALL_KINDS.clear()
    T06_KINDS.clear()
    t06_rows = load()
    states = display_table()
    trips = round_trips()
    sample = sampled()
    preferences = [
        {
            "id": ident,
            "text": text,
            "ambient_pressure": None if amb is None else repr(amb),
            "expected": expected,
            "why": why,
        }
        for ident, text, amb, expected, why in PREFERENCES
    ]
    return {
        "schema": "x04-reference-v1",
        "generator": "docs/derivations/scripts/x04_reference.py",
        "specification": "docs/adr/0075-X04-units-at-the-boundary.md; "
        "docs/derivations/X04-test-specification.md",
        "conversion_id": "display-conversion-v1",
        "note": (
            "Rationals are 'p/q' strings, binary64 values repr strings. SI = a*u + b; a gauge "
            "row's b is the declared ambient pressure. Nothing here comes from openflowsheet."
        ),
        "display_kinds": {
            kind: {
                "si_unit": ALL_KINDS[kind][0],
                "dimension": list(ALL_KINDS[kind][1]),
                "source": "ADR 0062 D1 (display only until F2)"
                if kind in DISPLAY_ONLY_KINDS
                else "schemas/units.json",
            }
            for kind in sorted(ALL_KINDS)
        },
        "rows": [
            {
                "kind": kind,
                "unit": unit,
                "a": f"{a.numerator}/{a.denominator}",
                "b": b if b == GAUGE else f"{b.numerator}/{b.denominator}",
                "direction": "output"
                if kind not in T06_KINDS or b == GAUGE
                else "input and output",
                "csv_suffix": csv_suffix(unit),
            }
            for kind, unit, a, b in ROWS
        ],
        "presets": PRESETS,
        "display_states": states,
        "round_trips": trips,
        "preferences": preferences,
        "ambient_declarations": [
            {"id": ident, "value": repr(value), "unit": unit, "expected": expected, "why": why}
            for ident, value, unit, expected, why in AMBIENT_DECLARATIONS
        ],
        "sample": sample,
        "generator_claims": claims(t06_rows, states, trips, sample),
    }


def emitted() -> bytes:
    return (json.dumps(document(), indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="re-derive every claim")
    parser.add_argument("--emit", metavar="PATH", help="write the reference JSON")
    arguments = parser.parse_args(argv)
    if not arguments.check and not arguments.emit:
        parser.error("choose --check and/or --emit PATH")
    data = emitted()  # raises, and emits nothing, if a claim fails
    if arguments.check:
        for name, summary in json.loads(data)["generator_claims"].items():
            print(f"PASS {name}: {summary}")
        if DEFAULT_JSON.is_file():
            if DEFAULT_JSON.read_bytes() != data:
                print(f"FAIL {DEFAULT_JSON.name} differs from what --emit writes")
                return 1
            print(f"{DEFAULT_JSON.name} is byte-identical to --emit")
    if arguments.emit:
        Path(arguments.emit).write_bytes(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
