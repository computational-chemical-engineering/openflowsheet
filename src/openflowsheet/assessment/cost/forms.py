"""Cost forms: the arithmetic of a correlation, with every number taken from its set file.

E01 design §4.5.1 as amended by §9.2.4 (register R-864). Two kinds:

- **Generic forms** (`log-polynomial-v1`, `power-law-v1`, `constant-v1`), the constant and
  piecewise log-polynomial factors and the two bare-module forms, for sets users register and for
  quotes (§4.5.4).
- **SSLW forms**, one per IDAES-PSE 2.13.0 `SSLWCostingData` method a day-one family uses
  (`sslw-exchanger-v1` … `sslw-turbine-v1`). Each mirrors the IDAES function it transcribes, line
  for line, products left to right in the order IDAES writes them; the seven deliberate departures
  are §9.2.2's (ranges, the exact tray-count `max`, the vessel wrappers, the vertical-platform
  piece, the number of units, the electric-motor-only compressor drive, the exchanger design
  pressure). Every number is `ResolvedEntry.numbers[...]`, read from `sslw-idaes-v1.json` with its
  `source_line`; nothing numeric is written here except the exact unit factors of §2.1.

Every expression is written with `Algebra`'s `exp`/`log` and `**`, so one builder serves the float
reference path and the CasADi twin (§4.2.2). A regime choice — the number of parallel units, the
size floor, a factor's piece — arrives as data in a `Selection`, made on floats by `select`
(§4.3.2) and then held; a floored quantity is a Python `float`, so its derivative is structurally
zero. The admissibility rows of a selection are `rows`; the cost contributor (WO-A4) turns them
into `regimes.AdmissibilityRow`s.

Input quantities are SI and positive: `area` m², `design_pressure` Pa (absolute), `diameter` and
`length` m, `thickness` m, `vol_flow` m³/s, `head` m, `power` W (the shaft power of a pump or
compressor, `−W` of a turbine, §4.4.5), and `n_act` (an `int`, structural).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final, Literal

from openflowsheet.assessment.regimes import select_piece, select_size, size_units
from openflowsheet.compile.reference import FloatAlgebra
from openflowsheet.compile.spec import Algebra, Expr

__all__ = [
    "ATM_PA",
    "FOOT_M",
    "FORMS",
    "GENERIC_FORMS",
    "INCH_M",
    "KAPPA_A",
    "KAPPA_Q",
    "KAPPA_W",
    "LN10",
    "PSI_PA",
    "Form",
    "OutOfRange",
    "Range",
    "RangeRow",
    "ResolvedEntry",
    "Selection",
    "constant",
    "log_polynomial",
    "motor_efficiency",
    "power_law",
    "rows",
    "select",
]

# -- exact unit factors (§2.1, §9.2.4), each a binary64 constant computed once -------------------

#: ft² per m²: 1/0.3048² = 10.763910416709722.
KAPPA_A: Final = 1.0 / 0.3048**2
#: US gpm per m³/s: 60/3.785411784e-3 = 15850.323141488905.
KAPPA_Q: Final = 60.0 / 3.785411784e-3
#: hp per W: 1/745.6998715822702 = 0.0013410220895950279.
KAPPA_W: Final = 1.0 / 745.6998715822702
INCH_M: Final = 0.0254
FOOT_M: Final = 0.3048
#: Pa per psi; gauge psig = (P − ATM_PA)/PSI_PA.
PSI_PA: Final = 6894.757293168361
ATM_PA: Final = 101325.0
#: ln 10 as a binary64 constant (§4.5.1); never `math.log(10)` at run time.
LN10: Final = 2.302585092994046

_FLOAT = FloatAlgebra()


# -- the generic forms (§4.5.1) ------------------------------------------------------------------


def log_polynomial(
    size: Expr, a: Sequence[float], base: Literal["e", "10"], kappa: float, alg: Algebra
) -> Expr:
    """`log-polynomial-v1`: `B^{Σ a_i (log_B S')^i}`, `S' = S·κ`, written
    `exp(ln B · Σ a_i (ln S'/ln B)^i)` with `ln 10 = LN10`; the sum is a left fold from i = 0.
    For B = e, `ln B = 1` and the form is `exp(Σ a_i (ln S')^i)` exactly."""
    log_s = alg.log(size * kappa)
    if base == "10":
        log_s = log_s / LN10
    elif base != "e":
        raise ValueError(f"log-polynomial base {base!r} is neither 'e' nor '10'")
    total: Expr = a[0]
    for power, coefficient in enumerate(a[1:], start=1):
        total = total + coefficient * log_s**power
    return alg.exp(LN10 * total) if base == "10" else alg.exp(total)


def power_law(size: Expr, c_ref: float, s_ref: float, n: float, alg: Algebra) -> Expr:
    """`power-law-v1`: `C_ref·(S/S_ref)^n`, written `C_ref·exp(n·ln(S/S_ref))`."""
    return c_ref * alg.exp(n * alg.log(size / s_ref))


def constant(c: float) -> float:
    """`constant-v1`: `C` (a quote without scaling)."""
    return float(c)


# -- data the forms read -------------------------------------------------------------------------


@dataclass(frozen=True)
class Range:
    """A validity range of one quantity, in the source's native unit (§9.2.3).

    `role` `size`: the §4.3 size regime over `[min, max]`. `role` `input`: a `piece` entry, with
    `below` `floor` or `refuse` and `above` `refuse`; `pieces` lists contiguous `(lo, hi)` intervals
    when the factor is piecewise, and `max_by_piece` gives a maximum per piece of the range named
    `pieces_of` (the vertical platforms' diameter). `source` is the range's provenance."""

    name: str
    role: Literal["size", "input"]
    min: float
    max: float
    source: Mapping[str, Any]
    below: Literal["floor", "refuse"] = "refuse"
    above: Literal["refuse"] = "refuse"
    pieces: tuple[tuple[float, float], ...] = ()
    max_by_piece: tuple[float, ...] = ()
    pieces_of: str | None = None


@dataclass(frozen=True)
class ResolvedEntry:
    """One set entry with an item's options applied (`sets.resolve`).

    `numbers` merges the entry's coefficients and the selected choices' values (floats, or tuples
    for listed coefficients); `ranges` merges the entry's and the selected choices' ranges;
    `options` is every option's chosen key and `defaulted` those taken from the IDAES default.
    `ratio` is the set's index value over the entry's (§9.2.6; 1.0 when they agree). `amended`
    maps the set path of each amended number in `numbers` to its record (§10.4.8), and `drive` is
    the set's resolved `machine.drive` entry for a form sized on consumed power (§10.4.4)."""

    set_id: str
    entry_id: str
    form: str
    options: Mapping[str, str]
    defaulted: tuple[str, ...]
    numbers: Mapping[str, Any]
    ranges: Mapping[str, Range]
    sources: Mapping[str, str]
    continuous: Mapping[str, float] = field(default_factory=dict)
    ratio: float = 1.0
    includes_drive: bool = False
    amended: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    drive: ResolvedEntry | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))
        object.__setattr__(self, "amended", MappingProxyType(dict(self.amended)))
        object.__setattr__(self, "numbers", MappingProxyType(dict(self.numbers)))
        object.__setattr__(self, "ranges", MappingProxyType(dict(self.ranges)))

    def n(self, name: str) -> float:
        value = self.numbers[name]
        if not isinstance(value, float):
            raise TypeError(f"{self.entry_id}: coefficient {name!r} is not a scalar")
        return value

    def ns(self, name: str) -> tuple[float, ...]:
        value = self.numbers[name]
        if not isinstance(value, tuple):
            raise TypeError(f"{self.entry_id}: coefficient {name!r} is not a list")
        return value


@dataclass(frozen=True)
class Selection:
    """The held choices of one item under its form (§4.3.2), made on floats.

    `size` is `units:N`, `floor` or `None` (no size regime); `n` the multiplier of `C_P1` (N, 1
    for a floor, the machine's N for a drive); `pieces` maps an input range to its piece (0 the
    floor, 1… the pieces); `extrapolated` maps a range to `(value, lo, hi)` when the item declared
    `allow_extrapolation` and the value lies outside (limitation `CORRELATION_EXTRAPOLATED`)."""

    size: str | None
    n: int
    pieces: Mapping[str, int] = field(default_factory=dict)
    extrapolated: Mapping[str, tuple[float, float, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class OutOfRange:
    """A value outside a range without `allow_extrapolation`: refusal
    `CORRELATION_OUT_OF_RANGE(<item>.<target>)` (§4.3.2), or a non-finite or non-positive input."""

    range_name: str
    target: str
    value: float
    low: float
    high: float
    detail: str = ""


@dataclass(frozen=True)
class RangeRow:
    """One admissibility row `sense·(q − bound) ≥ 0` on a native quantity `q` (§4.3.1)."""

    row_id: str
    quantity: str
    sense: Literal[1, -1]
    bound: float

    @property
    def nominal(self) -> float:
        return abs(self.bound) if self.bound != 0.0 else 1.0


Inputs = Mapping[str, Any]


class Form:
    """One SSLW form. Subclasses give `quantities`, `cost` and, for floored inputs,
    `input_response`; `select` and `rows` are generic over the ranges."""

    form_id: str = ""
    parallel: bool = False
    #: the size range's name, or `None` when the source states none (turbine, §9.2.4 VII).
    size_range: str | None = None
    #: the drive inherits the machine's N; its size rows are per unit (§9.2.4 V).
    inherits_units: bool = False
    #: refusal target and piece-entry stem of each range.
    targets: Mapping[str, str] = MappingProxyType({})
    inputs: tuple[str, ...] = ()

    def size_name(self, e: ResolvedEntry) -> str | None:
        return self.size_range

    def active_ranges(self, e: ResolvedEntry) -> tuple[Range, ...]:
        return tuple(e.ranges.values())

    def quantities(self, e: ResolvedEntry, x: Inputs, alg: Algebra, n: int = 1) -> dict[str, Expr]:
        raise NotImplementedError

    def cost(self, e: ResolvedEntry, x: Inputs, sel: Selection, alg: Algebra) -> Expr:
        """`C_P` of the item at the set's index basis: `N·C_P1` for a parallel form."""
        raise NotImplementedError

    def input_response(self, e: ResolvedEntry, name: str, z: float) -> float:
        """The factor that floored input `name` enters, as a float function of it alone (the
        loader's no-undercut check, §9.2.3)."""
        raise NotImplementedError(f"{self.form_id}: no floor on {name!r}")

    def target(self, name: str) -> str:
        return self.targets.get(name, name)

    def domain(self, e: ResolvedEntry, x: Inputs, units: int) -> OutOfRange | None:
        """A guard on a derived quantity outside its physical domain, on floats; `None` if none."""
        return None


def _input_value(sel: Selection, r: Range, value: Expr) -> Expr:
    """`value`, or the range's minimum (a float) when the input is floored (piece 0)."""
    return r.min if sel.pieces.get(r.name) == 0 else value


def _piece(sel: Selection, name: str) -> int:
    """The formula piece in use: a floor (0) uses the first piece's formula at the bound."""
    return max(1, sel.pieces.get(name, 1))


# -- I. sslw-exchanger-v1 (SSLW.py:327-507) -------------------------------------------------------


class _Exchanger(Form):
    form_id = "sslw-exchanger-v1"
    parallel = True
    size_range = "area_ft2"
    targets = MappingProxyType({"area_ft2": "area", "pressure_psig": "pressure"})
    inputs = ("area", "design_pressure")

    def quantities(self, e: ResolvedEntry, x: Inputs, alg: Algebra, n: int = 1) -> dict[str, Expr]:
        return {
            "area_ft2": x["area"] * KAPPA_A,
            "pressure_psig": (x["design_pressure"] - ATM_PA) / PSI_PA,
        }

    def pressure_factor(self, e: ResolvedEntry, p: Expr) -> Expr:
        a0, a1, a2 = e.ns("pressure_a")
        u = p / e.n("pressure_ref_psig")
        return a0 + a1 * u + a2 * u**2

    def input_response(self, e: ResolvedEntry, name: str, z: float) -> float:
        if name != "pressure_psig":
            return super().input_response(e, name, z)
        return float(self.pressure_factor(e, z))

    def cost(self, e: ResolvedEntry, x: Inputs, sel: Selection, alg: Algebra) -> Expr:
        area_range = e.ranges["area_ft2"]
        # A per unit in ft² (without the oversize); the floor puts A = S_min into C_B and F_M.
        area: Expr = area_range.min if sel.size == "floor" else (x["area"] / sel.n) * KAPPA_A
        z = e.n("oversize") * area
        log_z = alg.log(z)
        c_b = alg.exp(e.n("alpha1") - e.n("alpha2") * log_z + e.n("alpha3") * log_z**2)
        if "unity" in e.numbers:  # CarbonSteelCarbonSteel: F_M = 1 exactly (SSLW.py:455-456)
            f_m: Expr = e.n("unity")
        else:
            f_m = e.n("A") + (area / e.n("material_area_ref_ft2")) ** e.n("B")
        p_range = e.ranges["pressure_psig"]
        p = _input_value(sel, p_range, self.quantities(e, x, alg)["pressure_psig"])
        f_p = self.pressure_factor(e, p)
        c_p1 = f_p * f_m * e.n("F_L") * c_b
        return sel.n * c_p1


# -- II. sslw-vessel-v1 (SSLW.py:509-776) --------------------------------------------------------


class _Vessel(Form):
    form_id = "sslw-vessel-v1"
    parallel = False
    size_range = "weight_lb"
    targets = MappingProxyType(
        {
            "weight_lb": "weight",
            "platform_length_ft": "platforms.L",
            "platform_diameter_ft": "platforms.D",
        }
    )
    inputs = ("diameter", "length", "thickness")

    def _platforms(self, e: ResolvedEntry) -> bool:
        return e.options.get("platforms_ladders", "true") == "true"

    def active_ranges(self, e: ResolvedEntry) -> tuple[Range, ...]:
        platform = ("platform_length_ft", "platform_diameter_ft")
        return tuple(r for r in e.ranges.values() if r.name not in platform or self._platforms(e))

    def weight(self, e: ResolvedEntry, x: Inputs) -> Expr:
        d_in = x["diameter"] / INCH_M
        l_in = x["length"] / INCH_M
        t_in = x["thickness"] / INCH_M
        return (
            math.pi
            * (d_in + t_in)
            * (l_in + e.n("diameter_allowance") * d_in)
            * t_in
            * e.n("density_lb_in3")
        )

    def quantities(self, e: ResolvedEntry, x: Inputs, alg: Algebra, n: int = 1) -> dict[str, Expr]:
        q = {"weight_lb": self.weight(e, x)}
        if "platforms" in e.numbers or "platform_length_ft" in e.ranges:
            q["platform_length_ft"] = x["length"] / FOOT_M
            q["platform_diameter_ft"] = x["diameter"] / FOOT_M
        return q

    def _vertical_platforms(self, e: ResolvedEntry, piece: int, d_ft: Expr, l_ft: Expr) -> Expr:
        coefficients = e.numbers["platforms"][piece - 1]
        return coefficients["a"] * d_ft ** coefficients["b_D"] * l_ft ** coefficients["b_L"]

    def input_response(self, e: ResolvedEntry, name: str, z: float) -> float:
        lengths = e.ranges["platform_length_ft"]
        diameters = e.ranges["platform_diameter_ft"]
        if name == "platform_length_ft":
            return float(self._vertical_platforms(e, 1, diameters.min, z))
        if name == "platform_diameter_ft":
            return float(self._vertical_platforms(e, 1, z, lengths.min))
        return super().input_response(e, name, z)

    def cost(self, e: ResolvedEntry, x: Inputs, sel: Selection, alg: Algebra) -> Expr:
        weight: Expr = e.ranges["weight_lb"].min if sel.size == "floor" else self.weight(e, x)
        log_w = alg.log(weight)
        c_v = alg.exp(e.n("alpha1") + e.n("alpha2") * log_w + e.n("alpha3") * log_w**2)
        c_p1 = e.n("F_M") * c_v
        if self._platforms(e):
            d_ft = x["diameter"] / FOOT_M
            if "platforms_horizontal" in e.numbers:
                h = e.numbers["platforms_horizontal"]
                c_p1 = c_p1 + h["a"] * d_ft ** h["b_D"]
            else:
                lengths = e.ranges["platform_length_ft"]
                diameters = e.ranges["platform_diameter_ft"]
                l_ft = _input_value(sel, lengths, x["length"] / FOOT_M)
                d_ft = _input_value(sel, diameters, d_ft)
                piece = _piece(sel, lengths.name)
                c_p1 = c_p1 + self._vertical_platforms(e, piece, d_ft, l_ft)
        return c_p1


# -- III. sslw-trays-v1 (SSLW.py:777-868) --------------------------------------------------------


class _Trays(Form):
    form_id = "sslw-trays-v1"
    parallel = False
    size_range = "diameter_ft"
    targets = MappingProxyType({"diameter_ft": "diameter"})
    inputs = ("diameter", "n_act")

    def quantities(self, e: ResolvedEntry, x: Inputs, alg: Algebra, n: int = 1) -> dict[str, Expr]:
        return {"diameter_ft": x["diameter"] / FOOT_M}

    def count_factor(self, e: ResolvedEntry, n_act: int) -> float:
        """`F_NT = max(1, 2.25/1.0414**N)` exactly, in binary64 at build (departure 2: IDAES's
        `smooth_max` with eps = 1e-4 is replaced by the exact `max`; N_act is structural)."""
        if isinstance(n_act, bool) or not isinstance(n_act, int) or n_act < 1:
            raise ValueError(f"N_act {n_act!r} must be an integer ≥ 1")
        return max(e.n("count_floor"), e.n("count_a") / e.n("count_b") ** n_act)

    def cost(self, e: ResolvedEntry, x: Inputs, sel: Selection, alg: Algebra) -> Expr:
        d_ft: Expr = e.ranges["diameter_ft"].min if sel.size == "floor" else x["diameter"] / FOOT_M
        n_act = x["n_act"]
        f_tm = e.n("alpha1") + e.n("alpha2") * d_ft
        c_t = e.n("tray_cost_a") * alg.exp(e.n("tray_cost_b") * d_ft)
        f_nt = self.count_factor(e, n_act)
        return float(n_act) * f_nt * e.n("F_TT") * f_tm * c_t


# -- IV. sslw-pump-v1 (SSLW.py:1387-1623) --------------------------------------------------------


class _Pump(Form):
    form_id = "sslw-pump-v1"
    parallel = True
    targets = MappingProxyType({"size_factor": "size", "flow_gpm": "vol_flow", "power_hp": "power"})
    inputs = ("vol_flow", "head", "power")
    _SIZE: Final = MappingProxyType(
        {"Centrifugal": "size_factor", "ExternalGear": "flow_gpm", "Reciprocating": "power_hp"}
    )

    def size_name(self, e: ResolvedEntry) -> str | None:
        return self._SIZE[e.options["pump_type"]]

    def quantities(self, e: ResolvedEntry, x: Inputs, alg: Algebra, n: int = 1) -> dict[str, Expr]:
        kind = e.options["pump_type"]
        if kind == "Centrifugal":
            head_ft = x["head"] / FOOT_M
            return {"size_factor": (x["vol_flow"] * KAPPA_Q) * head_ft ** e.n("head_exponent")}
        if kind == "ExternalGear":
            return {"flow_gpm": x["vol_flow"] * KAPPA_Q}
        return {"power_hp": x["power"] * KAPPA_W}

    def cost(self, e: ResolvedEntry, x: Inputs, sel: Selection, alg: Algebra) -> Expr:
        kind = e.options["pump_type"]
        floor = sel.size == "floor"
        size_range = e.ranges[self._SIZE[kind]]
        if kind == "Centrifugal":
            q = (x["vol_flow"] / sel.n) * KAPPA_Q
            head_ft = x["head"] / FOOT_M
            s: Expr = size_range.min if floor else q * head_ft ** e.n("head_exponent")
            log_s = alg.log(s)
            c_b = alg.exp(e.n("a0") - e.n("a1") * log_s + e.n("a2") * log_s**2)
        else:
            if kind == "ExternalGear":
                z: Expr = size_range.min if floor else (x["vol_flow"] / sel.n) * KAPPA_Q
            else:
                z = size_range.min if floor else (x["power"] / sel.n) * KAPPA_W
            log_z = alg.log(z)
            c_b = alg.exp(e.n("a0") + e.n("a1") * log_z + e.n("a2") * log_z**2)
        f_t = e.n("F_T") if kind == "Centrifugal" else e.n("type_factor_other")
        c_p1 = f_t * e.n("F_M") * c_b * e.ratio
        return sel.n * c_p1


# -- V. sslw-motor-v1 (SSLW.py:1624-1677) --------------------------------------------------------


def motor_efficiency(e: ResolvedEntry, power_hp: Expr, alg: Algebra) -> Expr:
    """`η_m = 0.80 + 0.0319·ln W − 0.00182·ln² W`, W the per-unit shaft power in hp
    (SSLW.py:1636-1641; §9.2.7)."""
    e0, e1, e2 = e.ns("eta")
    log_w = alg.log(power_hp)
    return e0 + e1 * log_w - e2 * log_w**2


class _Motor(Form):
    form_id = "sslw-motor-v1"
    parallel = False
    inherits_units = True
    size_range = "motor_power_hp"
    targets = MappingProxyType({"motor_power_hp": "power"})
    inputs = ("power",)

    def quantities(self, e: ResolvedEntry, x: Inputs, alg: Algebra, n: int = 1) -> dict[str, Expr]:
        """`W_m` per unit: the per-unit shaft power over the motor efficiency at it."""
        w_hp = (x["power"] / n) * KAPPA_W
        return {"motor_power_hp": w_hp / motor_efficiency(e, w_hp, alg)}

    def domain(self, e: ResolvedEntry, x: Inputs, units: int) -> OutOfRange | None:
        """§9.2.4 V: `0 < η_m ≤ 1`, else `CORRELATION_OUT_OF_RANGE(<U>.drive.eta)`."""
        w_hp = (float(x["power"]) / units) * KAPPA_W
        if not (w_hp > 0.0 and math.isfinite(w_hp)):
            return OutOfRange("eta", "eta", w_hp, 0.0, math.inf, f"per-unit power {w_hp!r} hp")
        eta = float(motor_efficiency(e, w_hp, _FLOAT))
        if not 0.0 < eta <= 1.0:
            return OutOfRange("eta", "eta", eta, 0.0, 1.0, f"η_m = {eta!r} at {w_hp!r} hp")
        return None

    def cost(self, e: ResolvedEntry, x: Inputs, sel: Selection, alg: Algebra) -> Expr:
        w_m: Expr = (
            e.ranges["motor_power_hp"].min
            if sel.size == "floor"
            else self.quantities(e, x, alg, sel.n)["motor_power_hp"]
        )
        b0, b1, b2, b3, b4 = e.ns("base")
        lam = alg.log(w_m)
        c_b = alg.exp(b0 + b1 * lam + b2 * lam**2 + b3 * lam**3 - b4 * lam**4)
        c_p1 = e.n("F_MT") * c_b * e.ratio
        return sel.n * c_p1


# -- VI. sslw-compressor-v1 (SSLW.py:1080-1178) --------------------------------------------------


class _Compressor(Form):
    form_id = "sslw-compressor-v1"
    parallel = True
    size_range = "power_hp"
    targets = MappingProxyType({"power_hp": "power"})
    inputs = ("power",)

    def quantities(self, e: ResolvedEntry, x: Inputs, alg: Algebra, n: int = 1) -> dict[str, Expr]:
        return {"power_hp": x["power"] * KAPPA_W}

    def cost(self, e: ResolvedEntry, x: Inputs, sel: Selection, alg: Algebra) -> Expr:
        w_hp: Expr = (
            e.ranges["power_hp"].min if sel.size == "floor" else (x["power"] / sel.n) * KAPPA_W
        )
        c_b = alg.exp(e.n("alpha1") + e.n("alpha2") * alg.log(w_hp))
        c_p1 = e.n("F_D") * e.n("F_M") * c_b
        return sel.n * c_p1


# -- VII. sslw-turbine-v1 (SSLW.py:1338-1386) ----------------------------------------------------


class _Turbine(Form):
    form_id = "sslw-turbine-v1"
    parallel = False
    size_range = None
    inputs = ("power",)

    def quantities(self, e: ResolvedEntry, x: Inputs, alg: Algebra, n: int = 1) -> dict[str, Expr]:
        return {"power_hp": x["power"] * KAPPA_W}

    def cost(self, e: ResolvedEntry, x: Inputs, sel: Selection, alg: Algebra) -> Expr:
        w_hp = (x["power"] / sel.n) * KAPPA_W
        return e.n("a") * w_hp ** e.n("b")


#: The SSLW forms by id (§9.2.4).
FORMS: Final[Mapping[str, Form]] = MappingProxyType(
    {
        form.form_id: form
        for form in (
            _Exchanger(),
            _Vessel(),
            _Trays(),
            _Pump(),
            _Motor(),
            _Compressor(),
            _Turbine(),
        )
    }
)

#: The generic forms a `generic-v1` entry's `base` may name (§4.5.1).
GENERIC_FORMS: Final = ("log-polynomial-v1", "power-law-v1", "constant-v1")


# -- selection and admissibility (§4.3.2, §9.2.5) ------------------------------------------------


def _finite_positive(value: Any) -> bool:
    return isinstance(value, float) and math.isfinite(value) and value > 0.0


def select(
    form: Form,
    e: ResolvedEntry,
    x: Inputs,
    *,
    allow_extrapolation: bool = False,
    units: int = 1,
) -> Selection | OutOfRange:
    """The regime of one item at a float state `x` (§4.3.2 rules 4 and 5, §9.2.5).

    Size: below `S_min` the floor; above `S_max` a parallel form splits into `units:N`, any other
    form is refused (or extrapolated at `units:1`). A drive inherits `units` (the machine's N).
    Inputs: below `min` the floor where declared, else refused; above `max` refused; refused
    values are extrapolated on the nearest piece when `allow_extrapolation`. A non-finite or
    non-positive quantity is refused."""
    guard = form.domain(e, x, units)
    if guard is not None:
        return guard
    q = {
        k: float(v) if isinstance(v, int) else v
        for k, v in form.quantities(e, x, _FLOAT, units).items()
    }
    extrapolated: dict[str, tuple[float, float, float]] = {}
    size_name = form.size_name(e)
    size: str | None = None
    n = 1
    if size_name is not None:
        r = e.ranges[size_name]
        s = q[size_name]
        if not _finite_positive(s):
            return OutOfRange(
                size_name,
                form.target(size_name),
                float("nan"),
                r.min,
                r.max,
                f"{size_name} is not a finite positive value: {s!r}",
            )
        if form.inherits_units:
            n = units
            if s < r.min:
                size = "floor"
            elif s <= r.max:
                size = f"units:{units}"
            elif allow_extrapolation:
                size = f"units:{units}"
                extrapolated[size_name] = (s, r.min, r.max)
            else:
                return OutOfRange(size_name, form.target(size_name), s, r.min, r.max)
        elif form.parallel:
            size = select_size(s, r.min, r.max)
            n = size_units(size) or 1
        elif s < r.min:
            size = "floor"
        elif s <= r.max:
            size = "units:1"
        elif allow_extrapolation:
            size = "units:1"
            extrapolated[size_name] = (s, r.min, r.max)
        else:
            return OutOfRange(size_name, form.target(size_name), s, r.min, r.max)
    else:
        for name, value in q.items():
            if not _finite_positive(value):
                return OutOfRange(
                    name,
                    form.target(name),
                    float("nan"),
                    0.0,
                    math.inf,
                    f"{name} is not a finite positive value: {value!r}",
                )
    pieces: dict[str, int] = {}
    inputs = [r for r in form.active_ranges(e) if r.role == "input"]
    inputs.sort(key=lambda r: r.pieces_of is not None)  # a range's pieces before their dependants
    for r in inputs:
        z = q[r.name]
        if not (isinstance(z, float) and math.isfinite(z)):
            return OutOfRange(
                r.name,
                form.target(r.name),
                float("nan"),
                r.min,
                r.max,
                f"{r.name} is not finite: {z!r}",
            )
        intervals = r.pieces or ((r.min, _upper(r, pieces)),)
        low, high = intervals[0][0], intervals[-1][1]
        if z < low and r.below == "floor":
            pieces[r.name] = 0
            continue
        if low <= z <= high:
            pieces[r.name] = select_piece(z, intervals) + 1
            continue
        if not allow_extrapolation:
            return OutOfRange(r.name, form.target(r.name), z, low, high)
        pieces[r.name] = 1 if z < low else len(intervals)
        extrapolated[r.name] = (z, low, high)
    return Selection(size, n, MappingProxyType(pieces), MappingProxyType(extrapolated))


def _upper(r: Range, pieces: Mapping[str, int]) -> float:
    if not r.max_by_piece:
        return r.max
    if r.pieces_of is None:
        raise ValueError(f"range {r.name!r}: a maximum per piece needs `pieces_of`")
    return r.max_by_piece[max(1, pieces[r.pieces_of]) - 1]


def rows(form: Form, e: ResolvedEntry, sel: Selection) -> tuple[RangeRow, ...]:
    """The admissibility rows of `sel` (§4.3.1): size `units:N` `q − N·S_min`, `N·S_max − q`
    (per unit for a drive), `floor` `S_min − q`; a piece `z − lo`, `hi − z`; an input floor
    `min − z`. An extrapolated side has no row."""
    out: list[RangeRow] = []
    size_name = form.size_name(e)
    if size_name is not None and sel.size is not None:
        r = e.ranges[size_name]
        if sel.size == "floor":
            out.append(RangeRow(f"{size_name}.floor", size_name, -1, r.min))
        else:
            scale = 1.0 if form.inherits_units else float(sel.n)
            out.append(RangeRow(f"{size_name}.lo", size_name, 1, scale * r.min))
            if size_name not in sel.extrapolated:
                out.append(RangeRow(f"{size_name}.hi", size_name, -1, scale * r.max))
    for r in form.active_ranges(e):
        if r.role != "input" or r.name not in sel.pieces:
            continue
        piece = sel.pieces[r.name]
        intervals = r.pieces or ((r.min, _upper(r, sel.pieces)),)
        if piece == 0:
            out.append(RangeRow(f"{r.name}.floor", r.name, -1, intervals[0][0]))
            continue
        low, high = intervals[piece - 1]
        value = sel.extrapolated.get(r.name)
        if value is None or value[0] >= low:
            out.append(RangeRow(f"{r.name}.lo", r.name, 1, low))
        if value is None or value[0] <= high:
            out.append(RangeRow(f"{r.name}.hi", r.name, -1, high))
    return tuple(out)
