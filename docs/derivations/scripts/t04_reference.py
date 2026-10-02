"""Closed-form reference generator for T04: typed homotopy, the residence-time PTC family, edge 3.

Everything here follows from definitions: the SYN-001 thermodynamics of ``docs/derivations/
SYN-001.md`` (through the sibling closed-form script ``syn001_reference.py``), the equation-oriented
rows of the SYN-001 region exactly as the declared manifests write them (T02 §6.1, §7.3; ADR 0008
D3.3's orientation), K03's Newton core as specified (K03 §5), T03's phase-attempt contract as
specified (T03 §4), and the T04 homotopy, PTC core, mass mapping and recovery edge as specified in
``docs/derivations/T04-globalization-spec.md`` -- *simulated here at 40 significant digits from
their own statements*. It imports nothing from ``process_runtime`` or ``benchmarks``: the numbers it
emits are the expectations the T04 tests judge the implementation against.

**Two twins of the A02 region, and why both.** T03's generator simulates the eleven-row heater
block of the A02 region (T03 §6.1's exact reduction). This generator adds the full 42 x 42 SYN-001
region (both the nominal EO region of T02 §6.1 and the A02 region of T02 §7.3), because the PTC
mass matrix couples loop rows to heater columns and the basin comparison runs the whole loop. The
two are checked against each other on every A02 case both can run (identical outcomes, attempts,
counts and end temperatures), which is the evidence that each is the other's system.

Three classes of value are emitted and labelled as such in the YAML:

* ``closed_form`` -- phase boundaries, lambda at a phase boundary on a continuation path, the
  inventory modes of the SYN-001 loop, the flash's liquid-split Jacobian, exact seed trajectories.
* ``policy_simulation`` -- trajectories of the registered policies on the registered cases in
  40-digit arithmetic. An implementation of the same policies must reproduce them; the ablations
  show which rule each assertion depends on.
* ``measured`` -- the same twins rerun in 53-bit arithmetic, used only to argue tolerances.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/t04_reference.py --check
    python docs/derivations/scripts/t04_reference.py --emit benchmarks/t04/reference_values.yaml

``--check`` re-derives every claim the specification makes about its own numbers and refuses to
emit when one stops holding (T04 spec §13). ``--emit`` is byte-reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml
from mpmath import det, eig, exp, eye, inverse, log, lu_solve, matrix, mp, mpf, sqrt, svd_r

sys.path.insert(0, str(Path(__file__).resolve().parent))
import syn001_reference as p01  # noqa: E402  (closed-form SYN-001 thermodynamics, mpmath)
import t03_reference as t03  # noqa: E402  (the heater-block twin of the A02 region, T03 §6.1)

mp.dps = 40

# --------------------------------------------------------------------------------------------
# 1. Registered constants: K03 §5.9, T03 §4.9 (unchanged) and T04 §4.3, §7.7 (new)
# --------------------------------------------------------------------------------------------

ARMIJO_C = mpf("1e-4")
STEP_HALVINGS_MAX = 20
STAGNATION_WINDOW = 5
STAGNATION_RATIO = mpf("0.99")
MAX_ITERATIONS = 50
MAX_ATTEMPTS = 5
PHASE_WALL_PATIENCE = 2
ADMISSIBILITY_EPSILON = mpf("1e-12")


@dataclass(frozen=True)
class HomotopyPolicy:
    """T04 §4.3: `SolvePolicy.globalization.homotopy`."""

    delta_lambda_initial: Any = Fraction(1, 4)
    delta_lambda_min: Any = Fraction(1, 1024)
    growth: int = 2
    corrector_max_iterations: int = 10
    max_lambda_trials: int = 64
    #: ablations only (T04 §9.9); the registered policy has every flag at its default
    rollback: bool = True
    shrink: bool = True
    grow: bool = True


@dataclass(frozen=True)
class PTCPolicy:
    """T04 §7.7: `SolvePolicy.globalization.ptc`. Pseudo-time in seconds, theta = 1 s."""

    residence_time: Any = mpf(1)
    tau_initial: Any = mpf(1)
    tau_min: Any = mpf("1e-4")
    tau_max: Any = mpf("1e10")
    gamma_min: Any = mpf("0.2")
    gamma_max: Any = mpf(2)
    phi_floor: Any = mpf("1e-12")
    retry_shrink: Any = mpf("0.5")
    retries_max: int = 10
    max_steps: int = 200
    #: ADR 0008 D3.4's row-sign map on `holdup_balance` rows; +1 is the ablation
    holdup_row_sign: int = -1
    #: ablations only (T04 §9.9)
    clip: bool = True
    use_floor: bool = True
    stop: str = "k03"  # "k03" | "norm_floor"
    ratio_tau: str = "used"  # "used" | "proposed"
    rejected_phi: bool = False
    reset: bool = True
    polish: bool = True
    energy_holdup: str = "enthalpy"  # "enthalpy" | "internal"
    mole_holdup: str = "phase_resolved"  # "phase_resolved" | "stream_total"


HOMOTOPY = HomotopyPolicy()
PTC = PTCPolicy()

#: Every pseudo-step tried and every SER proposal made while `TAU_LOG` is armed (T04 §7.7's claim
#: that neither τ limit is reached on a registered path is read from here).
TAU_LOG: dict[str, Any] = {
    "armed": False,
    "tried_min": None,
    "proposed_max": None,
    "tau_min_stops": 0,
    "tau_min_clips": 0,
}


def _log_tau(tried: Any = None, proposed: Any = None) -> None:
    if not TAU_LOG["armed"]:
        return
    if tried is not None:
        cur = TAU_LOG["tried_min"]
        TAU_LOG["tried_min"] = tried if cur is None else min(cur, tried)
    if proposed is not None:
        cur = TAU_LOG["proposed_max"]
        TAU_LOG["proposed_max"] = proposed if cur is None else max(cur, proposed)


# --------------------------------------------------------------------------------------------
# 2. Forward-mode dual numbers: exact Jacobians of the rows as written, no hand differentiation
# --------------------------------------------------------------------------------------------


class Dual:
    __slots__ = ("v", "g")

    def __init__(self, v: Any, g: dict[str, Any] | None = None) -> None:
        self.v = v
        self.g = g or {}

    @staticmethod
    def lift(a: Any) -> Dual:
        return a if isinstance(a, Dual) else Dual(a)

    def __add__(self, o: Any) -> Dual:
        o = Dual.lift(o)
        g = dict(self.g)
        for k, x in o.g.items():
            g[k] = g.get(k, 0) + x
        return Dual(self.v + o.v, g)

    __radd__ = __add__

    def __neg__(self) -> Dual:
        return Dual(-self.v, {k: -x for k, x in self.g.items()})

    def __sub__(self, o: Any) -> Dual:
        return self + (-Dual.lift(o))

    def __rsub__(self, o: Any) -> Dual:
        return Dual.lift(o) + (-self)

    def __mul__(self, o: Any) -> Dual:
        o = Dual.lift(o)
        g = {k: x * o.v for k, x in self.g.items()}
        for k, x in o.g.items():
            g[k] = g.get(k, 0) + self.v * x
        return Dual(self.v * o.v, g)

    __rmul__ = __mul__

    def __truediv__(self, o: Any) -> Dual:
        o = Dual.lift(o)
        inv = 1 / o.v
        g = {k: x * inv for k, x in self.g.items()}
        for k, x in o.g.items():
            g[k] = g.get(k, 0) - self.v * x * inv * inv
        return Dual(self.v * inv, g)

    def __rtruediv__(self, o: Any) -> Dual:
        return Dual.lift(o) / self


def d_exp(a: Any) -> Any:
    if isinstance(a, Dual):
        e = exp(a.v)
        return Dual(e, {k: x * e for k, x in a.g.items()})
    return exp(a)


def d_log(a: Any) -> Any:
    if isinstance(a, Dual):
        return Dual(log(a.v), {k: x / a.v for k, x in a.g.items()})
    return log(a)


def value(a: Any) -> Any:
    return a.v if isinstance(a, Dual) else a


# --------------------------------------------------------------------------------------------
# 3. The SYN-001 EO region (T02 §6.1) and its A02 revision (T02 §7.3), rows as written
# --------------------------------------------------------------------------------------------

C = ("A", "B", "C")
CP = p01.CP
T_REF = p01.T_REF
P_REF = p01.P_REF
R_GAS = p01.R_GAS
T_BOIL = p01.T_BOIL
L_VAP = p01.L_VAP
V_LIQ = p01.V_LIQ
FRESH = (mpf(1), mpf(1), mpf(1))
T_FEED = mpf(300)
T_DOMAIN = (mpf(280), mpf(440))
P_DOMAIN = (mpf(50000), mpf(200000))
SPEC_ROW = "SPEC:SPEC-flash-duty"


def _stream(s: str) -> list[str]:
    return [f"{s}.n.{c}" for c in C] + [f"{s}.T", f"{s}.P"]


COLUMNS: tuple[str, ...] = tuple(
    _stream("S2")
    + _stream("S3")
    + _stream("S4")
    + _stream("S5")
    + _stream("S6")
    + _stream("S7")
    + ["U-HEAT.Q"]
    + [f"S3.vap.{c}" for c in C]
    + [f"S3.liq.{c}" for c in C]
    + ["S3.V", "S3.L", "U-FLASH.Q", "S4.N", "S5.N"]
)
NOMINAL_ROWS: tuple[str, ...] = (
    *[f"U-MIX:MIX-mole:{c}" for c in C],
    "U-MIX:MIX-energy",
    "U-MIX:MIX-pressure:0",
    "U-MIX:MIX-pressure:1",
    *[f"U-HEAT:HEAT-mole:{c}" for c in C],
    "U-HEAT:HEAT-T",
    "U-HEAT:HEAT-pressure",
    "U-HEAT:HEAT-duty",
    *[r for c in C for r in (f"U-HEAT:HEAT-equilibrium:{c}", f"U-HEAT:split:{c}")],
    "U-HEAT:Vdef",
    "U-HEAT:Ldef",
    *[r for c in C for r in (f"U-FLASH:FLASH-mole:{c}", f"U-FLASH:FLASH-equilibrium:{c}")],
    "U-FLASH:FLASH-T:vapor",
    "U-FLASH:FLASH-T:liquid",
    "U-FLASH:FLASH-P:vapor",
    "U-FLASH:FLASH-P:liquid",
    "U-FLASH:FLASH-duty",
    "U-FLASH:Ndef:vapor",
    "U-FLASH:Ndef:liquid",
    *[r for c in C for r in (f"U-SPLIT:SPLIT-recycle:{c}", f"U-SPLIT:SPLIT-purge:{c}")],
    "U-SPLIT:SPLIT-T:recycle",
    "U-SPLIT:SPLIT-T:purge",
    "U-SPLIT:SPLIT-P:purge",
)
#: ADR 0008 D3.5 restricted to the region: the rows that may, and must, carry a mass-matrix row.
HOLDUP_ROWS = frozenset(
    [f"U-HEAT:HEAT-mole:{c}" for c in C]
    + ["U-HEAT:HEAT-duty"]
    + [f"U-FLASH:FLASH-mole:{c}" for c in C]
    + ["U-FLASH:FLASH-duty"]
)
ZERO_HOLDUP_ROWS = frozenset([f"U-MIX:MIX-mole:{c}" for c in C] + ["U-MIX:MIX-energy"])
MOLE_HOLDUP_ROWS = frozenset(r for r in HOLDUP_ROWS if "-mole:" in r)


def column_kind(v: str) -> str:
    if v.endswith(".T"):
        return "temperature"
    if v.endswith(".P"):
        return "pressure"
    if v.endswith(".Q"):
        return "heat_rate"
    return "molar_flow"


def row_kind(r: str) -> str:
    if "equilibrium" in r:
        return "molar_flow_squared"
    if "energy" in r or "duty" in r:
        return "heat_rate"
    if r.endswith(":HEAT-T") or "FLASH-T:" in r or "SPLIT-T:" in r:
        return "temperature"
    if "pressure" in r or "FLASH-P:" in r or "SPLIT-P:" in r:
        return "pressure"
    return "molar_flow"


SCALE = {
    "molar_flow": mpf(3),
    "molar_flow_squared": mpf(9),
    "temperature": mpf(100),
    "pressure": mpf(10) ** 5,
    "heat_rate": mpf(10) ** 5,
}
TOLERANCE = {
    "molar_flow": mpf("1e-9") + mpf("1e-8") * 3,
    "molar_flow_squared": mpf("1e-9") * 3 + mpf("1e-8") * 9,
    "heat_rate": mpf("1e-5") + mpf("1e-8") * mpf(10) ** 5,
    "temperature": mpf("1e-6"),
    "pressure": mpf("1e-2"),
}
COL_SCALE = {v: SCALE[column_kind(v)] for v in COLUMNS}
ROW_SCALE = {r: SCALE[row_kind(r)] for r in NOMINAL_ROWS} | {SPEC_ROW: SCALE["heat_rate"]}
ROW_TOL = {r: TOLERANCE[row_kind(r)] for r in NOMINAL_ROWS} | {SPEC_ROW: TOLERANCE["heat_rate"]}
FLOW_COLUMNS = frozenset(v for v in COLUMNS if column_kind(v) == "molar_flow")
BLOCK_T = ("S2.T", "S3.T", "S4.T", "S5.T", "S6.T")
BLOCK_P = ("S2.P", "S3.P", "S4.P", "S5.P", "S6.P")


@dataclass(frozen=True)
class Flowsheet:
    """One compiled-problem instance: its pinned inputs (ADR 0008 D1.3)."""

    r: Any
    t_heater: Any = mpf(350)
    t_flash: Any = mpf(360)
    p: Any = P_REF
    #: None: the nominal region. A value: the A02 revision's `SPEC:SPEC-flash-duty` pinned input.
    q_spec: Any = None
    #: A per-component shift of the enthalpy reference (0 = SYN-001-ref-v1): §6.4's invariance.
    h_shift: tuple[Any, ...] = (mpf(0), mpf(0), mpf(0))

    @property
    def rows(self) -> tuple[str, ...]:
        if self.q_spec is None:
            return NOMINAL_ROWS
        return tuple(r for r in NOMINAL_ROWS if r != "U-HEAT:HEAT-T") + (SPEC_ROW,)


ZERO3 = (mpf(0), mpf(0), mpf(0))


def h_liq(i: int, t: Any, p: Any, sh: tuple[Any, ...]) -> Any:
    return CP * (t - T_REF) + V_LIQ[i] * (p - P_REF) + sh[i]


def h_vap(i: int, t: Any, sh: tuple[Any, ...]) -> Any:
    return CP * (t - T_REF) + L_VAP[i] + sh[i]


def ln_k(i: int, t: Any, p: Any) -> Any:
    return (
        d_log(P_REF / p)
        + (L_VAP[i] / R_GAS) * (1 / T_BOIL[i] - 1 / t)
        + V_LIQ[i] * (p - P_REF) / (R_GAS * t)
    )


def residual(x: dict[str, Any], fs: Flowsheet) -> dict[str, Any]:
    """The region's rows in the written form of `models/rows.py` (inflow − outflow + sources)."""
    sh = fs.h_shift
    out: dict[str, Any] = {}

    def n(s: str, c: str) -> Any:
        return x[f"{s}.n.{c}"]

    # S1 is fixed upstream of the region (T02 §6.1); T04 §4.8's 47 x 47 target makes it a column.
    s1 = [x.get(f"S1.n.{c}", FRESH[i]) for i, c in enumerate(C)]
    t1, p1 = x.get("S1.T", T_FEED), x.get("S1.P", P_REF)
    for i, c in enumerate(C):
        out[f"U-MIX:MIX-mole:{c}"] = (s1[i] + n("S6", c)) - n("S2", c)
    h1 = [s1[i] * h_liq(i, t1, p1, sh) for i in range(3)]
    h6 = [n("S6", c) * h_liq(i, x["S6.T"], x["S6.P"], sh) for i, c in enumerate(C)]
    h2 = [n("S2", c) * h_liq(i, x["S2.T"], x["S2.P"], sh) for i, c in enumerate(C)]
    out["U-MIX:MIX-energy"] = sum(h1) + sum(h6) - sum(h2)
    out["U-MIX:MIX-pressure:0"] = p1 - x["S2.P"]
    out["U-MIX:MIX-pressure:1"] = x["S6.P"] - x["S2.P"]
    for c in C:
        out[f"U-HEAT:HEAT-mole:{c}"] = n("S2", c) - n("S3", c)
    if fs.q_spec is None:
        out["U-HEAT:HEAT-T"] = x["S3.T"] - fs.t_heater
    else:
        out[SPEC_ROW] = x["U-FLASH.Q"] - fs.q_spec
    out["U-HEAT:HEAT-pressure"] = x["S3.P"] - x["S2.P"]
    h3v = [x[f"S3.vap.{c}"] * h_vap(i, x["S3.T"], sh) for i, c in enumerate(C)]
    h3l = [x[f"S3.liq.{c}"] * h_liq(i, x["S3.T"], x["S3.P"], sh) for i, c in enumerate(C)]
    out["U-HEAT:HEAT-duty"] = x["U-HEAT.Q"] + sum(h2) - sum(h3v) - sum(h3l)
    for i, c in enumerate(C):
        k = d_exp(ln_k(i, x["S3.T"], x["S3.P"]))
        out[f"U-HEAT:HEAT-equilibrium:{c}"] = (
            x[f"S3.vap.{c}"] * x["S3.L"] - k * x[f"S3.liq.{c}"] * x["S3.V"]
        )
        out[f"U-HEAT:split:{c}"] = (x[f"S3.vap.{c}"] + x[f"S3.liq.{c}"]) - n("S3", c)
    out["U-HEAT:Vdef"] = x["S3.V"] - x["S3.vap.A"] - x["S3.vap.B"] - x["S3.vap.C"]
    out["U-HEAT:Ldef"] = x["S3.L"] - x["S3.liq.A"] - x["S3.liq.B"] - x["S3.liq.C"]
    for i, c in enumerate(C):
        out[f"U-FLASH:FLASH-mole:{c}"] = (n("S3", c) - n("S4", c)) - n("S5", c)
        k = d_exp(ln_k(i, x["S4.T"], x["S4.P"]))
        out[f"U-FLASH:FLASH-equilibrium:{c}"] = n("S4", c) * x["S5.N"] - k * n("S5", c) * x["S4.N"]
    out["U-FLASH:FLASH-T:vapor"] = x["S4.T"] - fs.t_flash
    out["U-FLASH:FLASH-T:liquid"] = x["S5.T"] - fs.t_flash
    out["U-FLASH:FLASH-P:vapor"] = x["S4.P"] - fs.p
    out["U-FLASH:FLASH-P:liquid"] = x["S5.P"] - fs.p
    h4 = [n("S4", c) * h_vap(i, x["S4.T"], sh) for i, c in enumerate(C)]
    h5 = [n("S5", c) * h_liq(i, x["S5.T"], x["S5.P"], sh) for i, c in enumerate(C)]
    out["U-FLASH:FLASH-duty"] = x["U-FLASH.Q"] + sum(h3v) + sum(h3l) - sum(h4) - sum(h5)
    out["U-FLASH:Ndef:vapor"] = x["S4.N"] - n("S4", "A") - n("S4", "B") - n("S4", "C")
    out["U-FLASH:Ndef:liquid"] = x["S5.N"] - n("S5", "A") - n("S5", "B") - n("S5", "C")
    for c in C:
        out[f"U-SPLIT:SPLIT-recycle:{c}"] = n("S6", c) - fs.r * n("S5", c)
        out[f"U-SPLIT:SPLIT-purge:{c}"] = n("S7", c) - (1 - fs.r) * n("S5", c)
    out["U-SPLIT:SPLIT-T:recycle"] = x["S6.T"] - x["S5.T"]
    out["U-SPLIT:SPLIT-T:purge"] = x["S7.T"] - x["S5.T"]
    out["U-SPLIT:SPLIT-P:purge"] = x["S7.P"] - x["S5.P"]
    return out


def evaluate(x: dict[str, Any], fs: Flowsheet) -> dict[str, Any]:
    return {r: value(v) for r, v in residual(x, fs).items()}


def jacobian(
    x: dict[str, Any], free: Sequence[str], rows: Sequence[str], fs: Flowsheet
) -> tuple[dict[str, Any], matrix]:
    xd = {v: (Dual(x[v], {v: mpf(1)}) if v in free else x[v]) for v in x}
    out = residual(xd, fs)
    jac = matrix(len(rows), len(free))
    at = {v: j for j, v in enumerate(free)}
    for i, r in enumerate(rows):
        e = out[r]
        if isinstance(e, Dual):
            for k, g in e.g.items():
                if k in at:
                    jac[i, at[k]] = g
    return {r: value(v) for r, v in out.items()}, jac


def in_domain(x: dict[str, Any]) -> bool:
    return all(T_DOMAIN[0] <= x[t] <= T_DOMAIN[1] for t in BLOCK_T) and all(
        P_DOMAIN[0] <= x[p] <= P_DOMAIN[1] for p in BLOCK_P
    )


def domain_margin(x: dict[str, Any]) -> Any:
    return min(min(x[t] - T_DOMAIN[0], T_DOMAIN[1] - x[t]) for t in BLOCK_T)


# --------------------------------------------------------------------------------------------
# 4. The residence-time mass mapping (T04 §6.3): holdup = theta x phase-resolved outflow content
# --------------------------------------------------------------------------------------------


def mass_entries(x: dict[str, Any], fs: Flowsheet, pol: PTCPolicy) -> dict[tuple[str, str], Any]:
    """`M_row = d(holdup_row)/dx`, unscaled, in the rows' written orientation (ADR 0008 D3.3)."""
    th, sh = pol.residence_time, fs.h_shift
    m: dict[tuple[str, str], Any] = {}
    internal = pol.energy_holdup == "internal"
    for i, c in enumerate(C):
        if pol.mole_holdup == "phase_resolved":
            m[(f"U-HEAT:HEAT-mole:{c}", f"S3.vap.{c}")] = th
            m[(f"U-HEAT:HEAT-mole:{c}", f"S3.liq.{c}")] = th
        else:  # ablation: the heater's mole holdup on its stream total S3.n
            m[(f"U-HEAT:HEAT-mole:{c}", f"S3.n.{c}")] = th
        m[(f"U-FLASH:FLASH-mole:{c}", f"S4.n.{c}")] = th
        m[(f"U-FLASH:FLASH-mole:{c}", f"S5.n.{c}")] = th
        hv3, hl3 = h_vap(i, x["S3.T"], sh), h_liq(i, x["S3.T"], x["S3.P"], sh)
        hv4, hl5 = h_vap(i, x["S4.T"], sh), h_liq(i, x["S5.T"], x["S5.P"], sh)
        if internal:  # ablation: U = H − PV instead of the enthalpy content
            hv3, hv4 = hv3 - R_GAS * x["S3.T"], hv4 - R_GAS * x["S4.T"]
            hl3, hl5 = hl3 - x["S3.P"] * V_LIQ[i], hl5 - x["S5.P"] * V_LIQ[i]
        m[("U-HEAT:HEAT-duty", f"S3.vap.{c}")] = th * hv3
        m[("U-HEAT:HEAT-duty", f"S3.liq.{c}")] = th * hl3
        m[("U-FLASH:FLASH-duty", f"S4.n.{c}")] = th * hv4
        m[("U-FLASH:FLASH-duty", f"S5.n.{c}")] = th * hl5
    cpv = CP - R_GAS if internal else CP
    v3 = sum(x[f"S3.vap.{c}"] for c in C)
    l3 = sum(x[f"S3.liq.{c}"] for c in C)
    m[("U-HEAT:HEAT-duty", "S3.T")] = th * (cpv * v3 + CP * l3)
    m[("U-FLASH:FLASH-duty", "S4.T")] = th * cpv * sum(x[f"S4.n.{c}"] for c in C)
    m[("U-FLASH:FLASH-duty", "S5.T")] = th * CP * sum(x[f"S5.n.{c}"] for c in C)
    if not internal:
        m[("U-HEAT:HEAT-duty", "S3.P")] = th * sum(
            x[f"S3.liq.{c}"] * V_LIQ[i] for i, c in enumerate(C)
        )
        m[("U-FLASH:FLASH-duty", "S5.P")] = th * sum(
            x[f"S5.n.{c}"] * V_LIQ[i] for i, c in enumerate(C)
        )
    return m


def mass_matrix(
    x: dict[str, Any],
    free: Sequence[str],
    rows: Sequence[str],
    fs: Flowsheet,
    pol: PTCPolicy,
    extra: dict[tuple[str, str], Any] | None = None,
) -> matrix:
    """Scaled `M̂ = S_F⁻¹ M S_x`, restricted to the attempt's rows and free columns."""
    at_row = {r: i for i, r in enumerate(rows)}
    at_col = {v: j for j, v in enumerate(free)}
    out = matrix(len(rows), len(free))
    for (r, v), val in {**mass_entries(x, fs, pol), **(extra or {})}.items():
        if r in at_row and v in at_col:
            out[at_row[r], at_col[v]] = val * COL_SCALE[v] / ROW_SCALE[r]
    return out


def validate_mapping(
    entries: dict[tuple[str, str], Any], rows: Sequence[str], pol: PTCPolicy
) -> str | None:
    """T04 §7.2 / ADR 0008 D5: the rows with a nonzero M equal the holdup_balance rows."""
    mapped = {r for (r, _), val in entries.items() if val != 0}
    # §7.2 as amended 2026-09-24: V1 over every row, then V2 over every row, in declaration order
    for r in rows:
        if r in HOLDUP_ROWS and r not in mapped:
            return f"ptc_mapping_invalid({r}, missing)"
    for r in rows:
        if r in mapped and r not in HOLDUP_ROWS:
            return f"ptc_mapping_invalid({r}, not_holdup_balance)"
    if not pol.residence_time > 0:
        return "ptc_mapping_invalid(residence_time, non_positive)"
    return None


# --------------------------------------------------------------------------------------------
# 5. Lifted units, the kernel, the admissibility screen (K03 §8.2, T03 §4.3)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Lifted:
    unit: str
    temperature: str
    pressure: str
    vapor: tuple[str, ...]
    liquid: tuple[str, ...]
    vtot: str
    ltot: str
    eq_rows: tuple[str, ...]
    vdef: str
    ldef: str
    feed: tuple[str, ...] = tuple(f"S3.n.{c}" for c in C)

    def pinned(self, regime: str) -> tuple[str, ...]:
        if regime == "LIQUID":
            return (*self.vapor, self.vtot)
        if regime == "VAPOR":
            return (*self.liquid, self.ltot)
        return ()

    def dropped(self, regime: str) -> tuple[str, ...]:
        if regime == "LIQUID":
            return (*self.eq_rows, self.vdef)
        if regime == "VAPOR":
            return (*self.eq_rows, self.ldef)
        return ()


HEATER = Lifted(
    "U-HEAT",
    "S3.T",
    "S3.P",
    tuple(f"S3.vap.{c}" for c in C),
    tuple(f"S3.liq.{c}" for c in C),
    "S3.V",
    "S3.L",
    tuple(f"U-HEAT:HEAT-equilibrium:{c}" for c in C),
    "U-HEAT:Vdef",
    "U-HEAT:Ldef",
)
FLASH = Lifted(
    "U-FLASH",
    "S4.T",
    "S4.P",
    tuple(f"S4.n.{c}" for c in C),
    tuple(f"S5.n.{c}" for c in C),
    "S4.N",
    "S5.N",
    tuple(f"U-FLASH:FLASH-equilibrium:{c}" for c in C),
    "U-FLASH:Ndef:vapor",
    "U-FLASH:Ndef:liquid",
)
UNITS = (HEATER, FLASH)
ADJACENT = {
    ("LIQUID", "TWO_PHASE"),
    ("TWO_PHASE", "LIQUID"),
    ("TWO_PHASE", "VAPOR"),
    ("VAPOR", "TWO_PHASE"),
}


def kernel(u: Lifted, x: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    n = [x[f] for f in u.feed]
    fl = p01.tp_flash(n, x[u.temperature], x[u.pressure])
    total, zero, split = sum(n), mpf(0), {}
    if fl["state"] in ("LIQUID", "VAPOR"):
        liquid = fl["state"] == "LIQUID"
        for a, b, ni in zip(u.vapor, u.liquid, n, strict=True):
            split[a], split[b] = (zero, ni) if liquid else (ni, zero)
        split[u.vtot], split[u.ltot] = (zero, total) if liquid else (total, zero)
        return fl["state"], split
    vap = fl["beta"] * total
    liq = total - vap
    for i, (a, b) in enumerate(zip(u.vapor, u.liquid, strict=True)):
        split[a], split[b] = vap * fl["y"][i], liq * fl["x"][i]
    split[u.vtot], split[u.ltot] = vap, liq
    return "TWO_PHASE", split


def admissibility(u: Lifted, x: dict[str, Any], branch: str) -> Any:
    if branch == "TWO_PHASE":
        return mpf(0)
    k = [p01.k_value(i, x[u.temperature], x[u.pressure]) for i in range(3)]
    side = u.liquid if branch == "LIQUID" else u.vapor
    amounts = [x[v] for v in side]
    total = sum(amounts)
    if total == 0:
        return mpf(0)
    fr = [a / total for a in amounts]
    if branch == "LIQUID":
        return sum(f * kk for f, kk in zip(fr, k, strict=True))
    return sum(f / kk for f, kk in zip(fr, k, strict=True))


def branch_found(u: Lifted, x: dict[str, Any]) -> str:
    if x[u.vtot] == 0 and x[u.ltot] > 0:
        return "LIQUID"
    if x[u.ltot] == 0 and x[u.vtot] > 0:
        return "VAPOR"
    return "TWO_PHASE"


def signature(regimes: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple((u.unit, regimes[u.unit]) for u in UNITS)


def system(regimes: dict[str, str], fs: Flowsheet) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pinned = {v for u in UNITS for v in u.pinned(regimes[u.unit])}
    dropped = {r for u in UNITS for r in u.dropped(regimes[u.unit])}
    free = tuple(v for v in COLUMNS if v not in pinned)
    return free, tuple(r for r in fs.rows if r not in dropped)


def watched(regimes: dict[str, str], x: dict[str, Any]) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for u in UNITS:
        if regimes[u.unit] != "TWO_PHASE" or sum(x[f] for f in u.feed) <= 0:
            continue
        for phase, tot, comps in (("vapor", u.vtot, u.vapor), ("liquid", u.ltot, u.liquid)):
            out[tot] = (u.unit, phase)
            for cv, f in zip(comps, u.feed, strict=True):
                if x[f] > 0:
                    out[cv] = (u.unit, phase)
    return out


def pin(x: dict[str, Any], u: Lifted, remaining: str) -> dict[str, Any]:
    y, n = dict(x), [x[f] for f in u.feed]
    liquid = remaining == "LIQUID"
    for a, b, ni in zip(u.vapor, u.liquid, n, strict=True):
        y[a], y[b] = (mpf(0), ni) if liquid else (ni, mpf(0))
    y[u.vtot], y[u.ltot] = (mpf(0), sum(n)) if liquid else (sum(n), mpf(0))
    return y


# --------------------------------------------------------------------------------------------
# 6. Starts: K03 §3.3's reconstruction x(t0), and the A02 pre-solve (T02 §7.5)
# --------------------------------------------------------------------------------------------


def mixer_margin(t0: Sequence[Any], fs: Flowsheet) -> Any:
    """K03 §10.1's registered margin `1 − Σ z_i K_i(T_f, P)` of the recycle candidate `t0` itself
    (intensive: its composition, not its magnitude). > 0: subcooled."""
    total = sum(t0)
    z = [v / total for v in t0]
    return 1 - sum(z[i] * p01.k_value(i, fs.t_flash, fs.p) for i in range(3))


def mixer_gap_k(t0: Sequence[Any], fs: Flowsheet) -> Any:
    """The rule the v0.0 mixer enforces on each inlet (K02 `single_phase_admissible`): the gap
    between the candidate's true TP-state enthalpy and its all-liquid enthalpy at `(T_f, P)`, as
    the outlet temperature error it would cause, `|H_true − H_liq| / Σ n c_p`. Admitted iff
    ≤ 1e-6 K. (Amended 2026-09-24, T04 §17 F14: the first version judged the *mixed* feed at
    `T_mix`.)"""
    n = [mpf(v) for v in t0]
    fl = p01.tp_flash(n, fs.t_flash, fs.p)
    if fl["state"] != "TWO_PHASE":
        return mpf(0) if fl["state"] == "LIQUID" else mpf("inf")
    vap = [fl["beta"] * sum(n) * fl["y"][i] for i in range(3)]
    gap = sum(
        vap[i] * (h_vap(i, fs.t_flash, ZERO3) - h_liq(i, fs.t_flash, fs.p, ZERO3)) for i in range(3)
    )
    return abs(gap) / (sum(n) * CP)


MIXER_GAP_LIMIT_K = mpf("1e-6")  # ADR 0001 D6's temperature tolerance, as the mixer applies it


def reconstruct(t0: Sequence[Any], fs: Flowsheet) -> dict[str, Any] | None:
    """One traversal at tear `t0` (S6 = t0 at T_f, P): every row holds except SPLIT-recycle."""
    t0 = [mpf(v) for v in t0]
    if mixer_gap_k(t0, fs) > MIXER_GAP_LIMIT_K:
        return None
    x: dict[str, Any] = {}
    s2 = [FRESH[i] + t0[i] for i in range(3)]
    t2 = (sum(FRESH) * T_FEED + sum(t0) * fs.t_flash) / (sum(FRESH) + sum(t0))
    for i, c in enumerate(C):
        x[f"S2.n.{c}"], x[f"S3.n.{c}"], x[f"S6.n.{c}"] = s2[i], s2[i], t0[i]
    x["S2.T"], x["S2.P"] = t2, fs.p
    x["S3.T"], x["S3.P"] = fs.t_heater, fs.p
    x["S6.T"], x["S6.P"] = fs.t_flash, fs.p
    x.update(kernel(HEATER, x)[1])
    x["S4.T"], x["S4.P"], x["S5.T"], x["S5.P"] = fs.t_flash, fs.p, fs.t_flash, fs.p
    x.update(kernel(FLASH, x)[1])
    for c in C:
        x[f"S7.n.{c}"] = (1 - fs.r) * x[f"S5.n.{c}"]
    x["S7.T"], x["S7.P"] = fs.t_flash, fs.p
    sh = fs.h_shift
    h2 = sum(x[f"S2.n.{c}"] * h_liq(i, t2, fs.p, sh) for i, c in enumerate(C))
    h3 = sum(
        x[f"S3.vap.{c}"] * h_vap(i, fs.t_heater, sh)
        + x[f"S3.liq.{c}"] * h_liq(i, fs.t_heater, fs.p, sh)
        for i, c in enumerate(C)
    )
    h4 = sum(x[f"S4.n.{c}"] * h_vap(i, fs.t_flash, sh) for i, c in enumerate(C))
    h5 = sum(x[f"S5.n.{c}"] * h_liq(i, fs.t_flash, fs.p, sh) for i, c in enumerate(C))
    x["U-HEAT.Q"], x["U-FLASH.Q"] = h3 - h2, h4 + h5 - h3
    return x


def tear_root(r: Any) -> tuple[Any, ...]:
    return tuple(mpf(v) for v in p01.recycle_reference(r, mpf(360), "t04")["recycle_mol_per_s"])


def a02_open(guess: Any, q_spec: Any) -> tuple[dict[str, Any], Flowsheet]:
    """T02 §7.5: the pre-solve at S3.T = guess; the loop is at t* whatever S3.T is (T03 §6.1)."""
    r = mpf("0.5")
    x = reconstruct(tear_root(r), Flowsheet(r=r, t_heater=mpf(guess)))
    assert x is not None
    return x, Flowsheet(r=r, q_spec=q_spec)


def project(x0: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """T02 §6.2: every lifted split of the start is the kernel's; the regimes are the kernel's."""
    x, regimes = dict(x0), {}
    for u in UNITS:
        g, sp = kernel(u, x)
        x.update(sp)
        regimes[u.unit] = g
    return x, regimes


# --------------------------------------------------------------------------------------------
# 7. The cores: K03 §5 Newton, the T04 PTC core with SER and polish, the T04 homotopy
# --------------------------------------------------------------------------------------------


@dataclass
class Trial:
    iteration: int
    retry: int
    alpha: Any
    verdict: str
    reported: tuple[tuple[str, str], ...] | None = None
    state: dict[str, Any] | None = None
    tau: Any = None


@dataclass
class Margins:
    """The smallest distance of any decision on a path from its threshold (T04 §9.10)."""

    convergence_factor: Any = (
        None  # min over closing tests of min(tol/|F| at the stop, |F|/tol before)
    )
    armijo_relative: Any = None
    screen_relative: Any = None
    landing_gap: Any = None  # (1 − α_max) and the gap between the two smallest bound ratios
    domain_k: Any = None
    tau_min_relative: Any = None  # |0.5 Δτ_try / τ_min − 1| at every retry decision

    def take(self, name: str, v: Any) -> None:
        cur = getattr(self, name)
        setattr(self, name, v if cur is None else min(cur, v))

    def merge(self, other: Margins) -> None:
        for name in (
            "convergence_factor",
            "armijo_relative",
            "screen_relative",
            "landing_gap",
            "tau_min_relative",
        ):
            v = getattr(other, name)
            if v is not None:
                self.take(name, v)
        if other.domain_k is not None:
            self.take("domain_k", other.domain_k)


@dataclass
class CoreRun:
    outcome: str
    iterations: int
    x: dict[str, Any]
    core: str = "newton"
    trials: list[Trial] = field(default_factory=list)
    wall_iterations: list[int] = field(default_factory=list)
    candidates: list[Trial] = field(default_factory=list)
    blocked: tuple[str, ...] = ()
    landings: list[tuple[int, Any, tuple[str, ...]]] = field(default_factory=list)
    budget: str = ""
    closed_by: str = ""
    #: PTC only: (k, tau_used, phi_new, alpha, tau_next) per accepted pseudo-step
    history: list[tuple[Any, ...]] = field(default_factory=list)
    tau_end: Any = None
    polish: str = ""
    min_phi_at_ratio: Any = None
    margins: Margins = field(default_factory=Margins)
    accumulation_identity: Any = mpf(0)  # PTC: max relative defect of §6.5's identity
    #: PTC: max |lhs − rhs| / (1 + θ/Δτ) in mol/s — A21's absolute floor term (F14)
    accumulation_floor: Any = mpf(0)


def scaled_rows(values: dict[str, Any], rows: Sequence[str]) -> list[Any]:
    return [values[r] / ROW_SCALE[r] for r in rows]


def merit(values: dict[str, Any], rows: Sequence[str]) -> Any:
    return sum(v * v for v in scaled_rows(values, rows)) / 2


def phi_norm(values: dict[str, Any], rows: Sequence[str]) -> Any:
    return sqrt(sum(v * v for v in scaled_rows(values, rows)))


def worst(values: dict[str, Any], rows: Sequence[str]) -> Any:
    return max(abs(values[r]) / ROW_TOL[r] for r in rows)


def converged(values: dict[str, Any], rows: Sequence[str]) -> bool:
    return all(abs(values[r]) <= ROW_TOL[r] for r in rows)


def screen(x: dict[str, Any], regimes: dict[str, str], mg: Margins) -> tuple[tuple[str, str], ...]:
    reported = []
    for u in UNITS:
        g = regimes[u.unit]
        if g == "TWO_PHASE":
            reported.append((u.unit, g))
            continue
        val = admissibility(u, x, g)
        mg.take("screen_relative", abs(val - 1 - ADMISSIBILITY_EPSILON))
        if val > 1 + ADMISSIBILITY_EPSILON:
            reported.append((u.unit, kernel(u, x)[0]))
        else:
            reported.append((u.unit, g))
    return tuple(reported)


def bound_ratio(
    x: dict[str, Any], d: dict[str, Any], free: Sequence[str], mg: Margins
) -> tuple[Any, tuple[str, ...]]:
    ratios = {v: -x[v] / d[v] for v in free if v in FLOW_COLUMNS and d[v] < 0 and x[v] + d[v] < 0}
    amax = min([mpf(1), *ratios.values()])
    if amax <= 0:
        return mpf(0), tuple(v for v in free if v in ratios and x[v] <= 0)
    landing = tuple(v for v, q in ratios.items() if q == amax)
    if ratios:
        ordered = sorted(ratios.values())
        mg.take("landing_gap", 1 - ordered[0])
        if len(ordered) > 1:
            mg.take("landing_gap", (ordered[1] - ordered[0]) / ordered[0])
    return amax, landing


def _scaled_jacobian(jac: matrix, free: Sequence[str], rows: Sequence[str]) -> matrix:
    out = matrix(len(rows), len(free))
    for i, r in enumerate(rows):
        for j, v in enumerate(free):
            out[i, j] = jac[i, j] * COL_SCALE[v] / ROW_SCALE[r]
    return out


def _wall(run: CoreRun, trial: Trial, it: int) -> None:
    if not run.candidates or run.candidates[0].iteration != it:
        run.candidates = []
    run.candidates.append(trial)
    if not run.wall_iterations or run.wall_iterations[-1] != it:
        run.wall_iterations.append(it)


def _patience(run: CoreRun, it: int) -> bool:
    recent = run.wall_iterations[-PHASE_WALL_PATIENCE:]
    return (
        len(recent) == PHASE_WALL_PATIENCE
        and recent == list(range(recent[0], recent[0] + PHASE_WALL_PATIENCE))
        and recent[-1] == it
    )


def _pinned(x0: dict[str, Any], regimes: dict[str, str]) -> dict[str, Any]:
    x = dict(x0)
    for u in UNITS:
        for v in u.pinned(regimes[u.unit]):
            x[v] = mpf(0)
    return x


def _close_convergence(run: CoreRun, prev: Any, now: Any) -> None:
    """The factor by which the stopping decision clears its threshold on both sides."""
    f = 1 / now if now > 0 else mpf(10) ** 30
    if prev is not None:
        f = min(f, prev)
    run.margins.take("convergence_factor", f)


def newton(
    x0: dict[str, Any], regimes: dict[str, str], fs: Flowsheet, max_it: int = MAX_ITERATIONS
) -> CoreRun:
    """K03 §5, verbatim, on the region under a frozen signature (T03 §4)."""
    free, rows = system(regimes, fs)
    sig = signature(regimes)
    x = _pinned(x0, regimes)
    values = evaluate(x, fs)
    run = CoreRun("", 0, x)
    ratios: list[Any] = []
    prev = None
    for it in range(max_it + 1):
        m = merit(values, rows)
        if converged(values, rows):
            _close_convergence(run, prev, worst(values, rows))
            run.outcome, run.iterations, run.x = "CONVERGED", it, x
            return run
        prev = worst(values, rows)
        if it == max_it:
            run.outcome, run.iterations, run.x, run.budget = (
                "BUDGET_EXHAUSTED",
                it,
                x,
                "newton_iterations",
            )
            return run
        if len(ratios) >= STAGNATION_WINDOW and all(
            q > STAGNATION_RATIO for q in ratios[-STAGNATION_WINDOW:]
        ):
            run.outcome, run.iterations, run.x = "STAGNATION", it, x
            return run
        _, jac = jacobian(x, free, rows, fs)
        step = lu_solve(
            _scaled_jacobian(jac, free, rows),
            matrix([-values[r] / ROW_SCALE[r] for r in rows]),
        )
        d = {v: step[j] * COL_SCALE[v] for j, v in enumerate(free)}
        amax, landing = bound_ratio(x, d, free, run.margins)
        if amax == 0:
            run.outcome, run.iterations, run.x, run.blocked = "BOUND_BLOCKED", it, x, landing
            return run
        accepted = False
        for h in range(STEP_HALVINGS_MAX + 1):
            alpha = amax / mpf(2) ** h
            y = dict(x)
            for v in free:
                y[v] = x[v] + alpha * d[v]
            if h == 0:
                for v in landing:
                    y[v] = mpf(0)
            tr = Trial(it, h, alpha, "", state=y)
            if not in_domain(y):
                tr.verdict = "invalid_trial"
                run.trials.append(tr)
                continue
            run.margins.take("domain_k", domain_margin(y))
            reported = screen(y, regimes, run.margins)
            if reported != sig:
                tr.verdict, tr.reported = "phase_update_required", reported
                run.trials.append(tr)
                _wall(run, tr, it)
                continue
            tv = evaluate(y, fs)
            tm = merit(tv, rows)
            bound = (1 - 2 * ARMIJO_C * alpha) * m
            if bound > 0:
                run.margins.take("armijo_relative", abs(tm / bound - 1))
            if tm > bound:
                tr.verdict = "armijo"
                run.trials.append(tr)
                continue
            tr.verdict = "accepted"
            run.trials.append(tr)
            ratios.append(tm / m if m > 0 else mpf(0))
            x, values, accepted = y, tv, True
            if h == 0 and landing:
                run.landings.append((it, amax, landing))
            break
        if _patience(run, it):
            run.outcome, run.iterations, run.x, run.closed_by = (
                "PHASE_UPDATE_REQUIRED",
                it + int(accepted),
                x,
                "wall",
            )
            return run
        if not accepted:
            run.outcome, run.iterations, run.x = "LINE_SEARCH_FAILED", it, x
            return run
    raise AssertionError("unreachable: the iteration budget is checked inside the loop")


def _ptc_matrix(
    x: dict[str, Any],
    free: Sequence[str],
    rows: Sequence[str],
    fs: Flowsheet,
    pol: PTCPolicy,
    extra: dict[tuple[str, str], Any] | None = None,
) -> tuple[dict[str, Any], matrix, matrix, matrix]:
    """F, the row-signed scaled Jacobian Ĵ_σ, the scaled mass M̂, and the row-signed F̂_σ."""
    values, jac = jacobian(x, free, rows, fs)
    js = _scaled_jacobian(jac, free, rows)
    ms = mass_matrix(x, free, rows, fs, pol, extra)
    fsig = matrix(len(rows), 1)
    for i, r in enumerate(rows):
        sg = pol.holdup_row_sign if r in HOLDUP_ROWS else 1
        fsig[i] = sg * values[r] / ROW_SCALE[r]
        for j in range(len(free)):
            js[i, j] = sg * js[i, j]
    return values, js, ms, fsig


def polish(
    x: dict[str, Any],
    values: dict[str, Any],
    regimes: dict[str, str],
    fs: Flowsheet,
    free: Sequence[str],
    rows: Sequence[str],
    mg: Margins,
) -> tuple[dict[str, Any], str]:
    """T04 §7.5: one Newton step from a PTC stop; kept iff valid, frozen, converged and no worse."""
    _, jac = jacobian(x, free, rows, fs)
    try:
        step = lu_solve(
            _scaled_jacobian(jac, free, rows), matrix([-values[r] / ROW_SCALE[r] for r in rows])
        )
    except ZeroDivisionError:
        return x, "rejected(linear_solve_failed)"
    d = {v: step[j] * COL_SCALE[v] for j, v in enumerate(free)}
    amax, landing = bound_ratio(x, d, free, mg)
    if amax == 0:
        return x, "rejected(bound_blocked)"
    y = dict(x)
    for v in free:
        y[v] = x[v] + amax * d[v]
    for v in landing:
        y[v] = mpf(0)
    if not in_domain(y):
        return x, "rejected(invalid_trial)"
    if screen(y, regimes, mg) != signature(regimes):
        return x, "rejected(phase_update_required)"
    yv = evaluate(y, fs)
    if not converged(yv, rows) or worst(yv, rows) > worst(values, rows):
        return x, "rejected(not_better)"
    return y, "accepted"


def ptc(
    x0: dict[str, Any],
    regimes: dict[str, str],
    fs: Flowsheet,
    pol: PTCPolicy = PTC,
    tau_start: Any = None,
    extra_mass: dict[tuple[str, str], Any] | None = None,
) -> CoreRun:
    """T04 §7: the linearly implicit pseudo-transient step with safeguarded SER."""
    free, rows = system(regimes, fs)
    sig = signature(regimes)
    x = _pinned(x0, regimes)
    values = evaluate(x, fs)
    phi = phi_norm(values, rows)
    tau = pol.tau_initial if tau_start is None else tau_start
    run = CoreRun("", 0, x, core="ptc")
    prev = None
    for k in range(pol.max_steps + 1):
        stop = converged(values, rows) if pol.stop == "k03" else phi <= pol.phi_floor
        if stop:
            _close_convergence(run, prev, worst(values, rows))
            run.outcome, run.iterations, run.x, run.tau_end = "CONVERGED", k, x, tau
            if k > 0 and pol.polish:
                run.x, run.polish = polish(x, values, regimes, fs, free, rows, run.margins)
            return run
        prev = worst(values, rows)
        if k == pol.max_steps:
            run.outcome, run.iterations, run.x, run.budget, run.tau_end = (
                "BUDGET_EXHAUSTED",
                k,
                x,
                "ptc_steps",
                tau,
            )
            return run
        values_k, js, ms, fsig = _ptc_matrix(x, free, rows, fs, pol, extra_mass)
        tau_try, retry, rejected_phi = tau, 0, None
        blocked: tuple[str, ...] = ()
        while True:
            reason = ""
            _log_tau(tried=tau_try)
            a = js + ms / tau_try
            try:
                step = lu_solve(a, -fsig)
            except ZeroDivisionError:
                reason = "linear_solve_failed"
            if not reason:
                d = {v: step[j] * COL_SCALE[v] for j, v in enumerate(free)}
                amax, landing = bound_ratio(x, d, free, run.margins)
                if amax == 0:
                    reason, blocked = "bound_blocked", landing
                else:
                    y = dict(x)
                    for v in free:
                        y[v] = x[v] + amax * d[v]
                    for v in landing:
                        y[v] = mpf(0)
                    tr = Trial(k, retry, amax, "", state=y, tau=tau_try)
                    if not in_domain(y):
                        reason = "invalid_trial"
                    else:
                        run.margins.take("domain_k", domain_margin(y))
                        reported = screen(y, regimes, run.margins)
                        if reported != sig:
                            reason, tr.reported = "phase_update_required", reported
                            _wall(run, tr, k)
                            rejected_phi = phi_norm(evaluate(y, fs), rows)
            if not reason:
                break
            run.trials.append(Trial(k, retry, None, reason, tau=tau_try))
            retry += 1
            if retry <= pol.retries_max:
                run.margins.take(
                    "tau_min_relative", abs(tau_try * pol.retry_shrink / pol.tau_min - 1)
                )
                if tau_try * pol.retry_shrink < pol.tau_min and TAU_LOG["armed"]:
                    TAU_LOG["tau_min_stops"] += 1
            if retry > pol.retries_max or tau_try * pol.retry_shrink < pol.tau_min:
                out = "BOUND_BLOCKED" if reason == "bound_blocked" else "PTC_STALLED"
                run.outcome, run.iterations, run.x, run.tau_end = out, k, x, tau_try
                run.blocked = blocked if reason == "bound_blocked" else ()
                return run
            tau_try = tau_try * pol.retry_shrink
        new_values = evaluate(y, fs)
        run.trials.append(Trial(k, retry, amax, "accepted", tau=tau_try))
        # §6.5: the accumulation identity on the linear mole rows, exact for linear holdups
        for r in MOLE_HOLDUP_ROWS & set(rows):
            ent = {v: val for (rr, v), val in mass_entries(x, fs, pol).items() if rr == r}
            dn = sum(val * (y[v] - x[v]) for v, val in ent.items())
            lhs = new_values[r]
            rhs = (1 - amax) * values_k[r] + dn / tau_try
            den = max(abs(lhs), abs(values_k[r]), ROW_TOL[r])
            run.accumulation_identity = max(run.accumulation_identity, abs(lhs - rhs) / den)
            run.accumulation_floor = max(
                run.accumulation_floor, abs(lhs - rhs) / (1 + pol.residence_time / tau_try)
            )
        if amax < 1:
            run.landings.append((k, amax, landing))
        phi_new = phi_norm(new_values, rows)
        x, values = y, new_values
        tau_next = None
        if pol.stop != "k03" or not converged(values, rows):
            base = tau_try if pol.ratio_tau == "used" else tau
            den = max(phi_new, pol.phi_floor) if pol.use_floor else phi_new
            if pol.rejected_phi and rejected_phi is not None:
                den = rejected_phi
            run.min_phi_at_ratio = (
                phi_new if run.min_phi_at_ratio is None else min(run.min_phi_at_ratio, phi_new)
            )
            ratio = phi / den
            if pol.clip:
                ratio = min(max(ratio, pol.gamma_min), pol.gamma_max)
            _log_tau(proposed=base * ratio)
            if base * ratio < pol.tau_min and TAU_LOG["armed"]:
                TAU_LOG["tau_min_clips"] += 1
            tau_next = min(max(base * ratio, pol.tau_min), pol.tau_max)
            tau = tau_next
        run.history.append((k, tau_try, phi_new, amax, tau_next))
        phi = phi_new
        if _patience(run, k):
            run.outcome, run.iterations, run.x, run.closed_by, run.tau_end = (
                "PHASE_UPDATE_REQUIRED",
                k + 1,
                x,
                "wall",
                tau,
            )
            return run
    raise AssertionError("unreachable: the step budget is checked inside the loop")


@dataclass
class HomotopyRun:
    outcome: str
    x: dict[str, Any]
    lam: Fraction
    #: (lambda trial, delta lambda, corrector outcome, corrector iterations, accepted, S3.T,
    #:  landings, blocked, margins) per corrector, the lambda = 0 corrector first
    steps: list[tuple[Any, ...]] = field(default_factory=list)
    budget: str = ""
    margins: Margins = field(default_factory=Margins)


def continued(fs: Flowsheet, q0: Any, lam: Fraction) -> Flowsheet:
    """T04 §4.2: p(λ) = p* + (1 − λ)(p⁰ − p*); p(1) is the target's pinned input, bit for bit."""
    if lam == 1:
        return fs
    one_minus = mpf(1 - lam.numerator * mpf(1) / lam.denominator)
    return replace(fs, q_spec=fs.q_spec + one_minus * (q0 - fs.q_spec))


def homotopy(
    x_open: dict[str, Any], regimes: dict[str, str], fs: Flowsheet, hp: HomotopyPolicy = HOMOTOPY
) -> HomotopyRun:
    """T04 §4.3: specification continuation from the opening state in the opening signature."""
    q0 = x_open["U-FLASH.Q"]
    out = HomotopyRun("", x_open, Fraction(0))
    r0 = newton(x_open, regimes, continued(fs, q0, Fraction(0)), hp.corrector_max_iterations)
    out.margins.merge(r0.margins)
    out.steps.append(
        (
            Fraction(0),
            Fraction(0),
            r0.outcome,
            r0.iterations,
            r0.outcome == "CONVERGED",
            r0.x["S3.T"],
            r0.landings,
            r0.blocked,
        )
    )
    if r0.outcome != "CONVERGED":
        out.outcome = "HOMOTOPY_STALLED"
        return out
    lam, x, dl, trials = Fraction(0), r0.x, Fraction(hp.delta_lambda_initial), 0
    while lam < 1:
        if trials == hp.max_lambda_trials:
            out.outcome, out.x, out.lam, out.budget = "BUDGET_EXHAUSTED", x, lam, "homotopy_steps"
            return out
        trial = min(lam + dl, Fraction(1))
        run = newton(x, regimes, continued(fs, q0, trial), hp.corrector_max_iterations)
        out.margins.merge(run.margins)
        trials += 1
        ok = run.outcome == "CONVERGED"
        out.steps.append(
            (trial, dl, run.outcome, run.iterations, ok, run.x["S3.T"], run.landings, run.blocked)
        )
        if ok:
            lam, x = trial, run.x
            if lam < 1 and hp.grow:
                dl = min(hp.growth * dl, 1 - lam)
            elif lam < 1:
                dl = min(dl, 1 - lam)
        else:
            if not hp.rollback:
                x = run.x
            dl = dl / 2
            if dl < hp.delta_lambda_min or not hp.shrink:
                out.outcome, out.x, out.lam = "HOMOTOPY_STALLED", x, lam
                return out
    out.outcome, out.x, out.lam = "CONVERGED", x, lam
    return out


# --------------------------------------------------------------------------------------------
# 8. The contract (T03 §4) on the two lifted units, with the T04 extensions, and edge 3 (§5)
# --------------------------------------------------------------------------------------------

STALL_OUTCOMES = {"LINE_SEARCH_FAILED", "STAGNATION", "PTC_STALLED"}  # T03 §4.8 row 4 + T04
KERNEL_OUTCOMES = {"STAGNATION", "LINE_SEARCH_FAILED", "BOUND_BLOCKED", "PTC_STALLED"}  # row 5
EDGE3_TRIGGERS = {
    "LINE_SEARCH_FAILED",
    "STAGNATION",
    "BOUND_BLOCKED",
    "BUDGET_EXHAUSTED",
    "PTC_STALLED",
    "ACTIVE_SET_CYCLING",
    "ATTEMPTS_EXHAUSTED",
}


@dataclass
class Attempt:
    regimes: dict[str, str]
    source: str
    run: CoreRun
    decision: str = ""
    cause: str = ""


@dataclass
class Solve:
    outcome: str
    attempts: list[Attempt]
    x: dict[str, Any]
    message: str = ""
    homotopy: HomotopyRun | None = None
    recovery: str = ""
    contract_outcome: str = ""


def adjacent(a: tuple[Any, ...], b: tuple[Any, ...]) -> bool:
    diff = [(ra, rb) for (_, ra), (_, rb) in zip(a, b, strict=True) if ra != rb]
    return bool(diff) and all(p in ADJACENT for p in diff)


def sigtext(sig: tuple[tuple[str, str], ...]) -> str:
    return ",".join(f"{u}:{g}" for u, g in sig)


def contract(
    x0: dict[str, Any],
    fs: Flowsheet,
    core: str = "newton",
    pol: PTCPolicy = PTC,
    max_attempts: int = MAX_ATTEMPTS,
    newton_max_it: int = MAX_ITERATIONS,
    extra_mass: dict[tuple[str, str], Any] | None = None,
) -> Solve:
    """T03 §4 on the region (both lifted units), with `eo_core` (T04 §7.1) and T04's rows 4–5."""
    x, regimes = project(x0)
    used: list[tuple[Any, ...]] = []
    attempts: list[Attempt] = []
    source, carried = "initializer", None
    for k in range(max_attempts):
        sig = signature(regimes)
        used.append(sig)
        if core == "newton":
            run = newton(x, regimes, fs, newton_max_it)
        else:
            start = None if pol.reset else carried
            run = ptc(x, regimes, fs, pol, tau_start=start, extra_mass=extra_mass)
            carried = run.tau_end
        at = Attempt(dict(regimes), source, run)
        attempts.append(at)
        end = run.x
        new: dict[str, str] | None = None
        opening: dict[str, Any] = {}
        cause = ""
        if run.outcome == "CONVERGED":
            bad = next(
                (
                    u
                    for u in UNITS
                    if branch_found(u, end) != "TWO_PHASE"
                    and admissibility(u, end, branch_found(u, end)) > 1 + ADMISSIBILITY_EPSILON
                ),
                None,
            )
            if bad is None:
                at.decision = "converged"
                return Solve("CONVERGED", attempts, end)
            g, sp = kernel(bad, end)
            opening, new = {**end, **sp}, {**regimes, bad.unit: g}
            label = "all_liquid" if branch_found(bad, end) == "LIQUID" else "all_vapor"
            # T03 §4.10's R0 form (review S4): the stream split, and the branch found.
            cause, source = f"inadmissible(S3, {label})", "closure_projection"
        wall = run.outcome == "PHASE_UPDATE_REQUIRED" or (
            run.outcome in STALL_OUTCOMES
            and run.wall_iterations
            and run.iterations - run.wall_iterations[-1] < STAGNATION_WINDOW
        )
        if new is None and wall and run.candidates:
            pick = next(
                (t for t in run.candidates if t.reported and adjacent(sig, t.reported)),
                run.candidates[0],
            )
            assert pick.state is not None and pick.reported is not None
            opening, new = dict(pick.state), dict(regimes)
            changes = []
            for unit, g in pick.reported:
                if g != regimes[unit]:
                    u = next(uu for uu in UNITS if uu.unit == unit)
                    kg, sp = kernel(u, opening)
                    assert kg == g
                    opening.update(sp)
                    new[unit] = g
                    changes.append(f"{unit}:{regimes[unit]}->{g}")
            trig = "patience" if run.outcome == "PHASE_UPDATE_REQUIRED" else "stall"
            # T03 §4.10's grammar in full: `phase_wall(<trigger>, <unit>:<from>-><to>[, …])`.
            cause = f"phase_wall({trig}, {', '.join(changes)})"
            source = "phase_rejected_trial"
        if new is None and run.outcome == "BOUND_BLOCKED":
            w = watched(regimes, end)
            hit = next((v for v in run.blocked if v in w), None)
            if hit is not None:
                unit, phase = w[hit]
                u = next(uu for uu in UNITS if uu.unit == unit)
                remaining = "LIQUID" if phase == "vapor" else "VAPOR"
                opening, new = pin(end, u, remaining), {**regimes, unit: remaining}
                cause, source = f"phase_disappeared({unit}, {phase}, {hit})", "pinned_iterate"
        if new is None and (run.outcome in KERNEL_OUTCOMES or run.outcome == "BUDGET_EXHAUSTED"):
            for u in UNITS:
                g, sp = kernel(u, end)
                if g != regimes[u.unit]:
                    opening, new = {**end, **sp}, {**regimes, u.unit: g}
                    cause, source = f"kernel_disagrees({u.unit}, {g})", "closure_projection"
                    break
        if new is None:
            at.decision = "terminal"
            return Solve(run.outcome, attempts, end)
        at.decision, at.cause = "restart", cause
        if k + 1 == max_attempts:
            return Solve("ATTEMPTS_EXHAUSTED", attempts, end)
        ns = signature(new)
        if ns in used:
            return Solve("ACTIVE_SET_CYCLING", attempts, end, f"{sigtext(ns)}; {cause}")
        regimes, x = new, opening
    raise AssertionError("unreachable: the restart gate ends the solve at max_attempts")


def solve_with_edge3(
    x0: dict[str, Any],
    fs: Flowsheet,
    core: str = "newton",
    recovery: bool = True,
    max_attempts: int = MAX_ATTEMPTS,
    newton_max_it: int = MAX_ITERATIONS,
    hp: HomotopyPolicy = HOMOTOPY,
    start: str = "opening",
) -> Solve:
    """T04 §5: a region solve; on a trigger outcome, one specification continuation."""
    failed = contract(x0, fs, core, max_attempts=max_attempts, newton_max_it=newton_max_it)
    failed.contract_outcome = failed.outcome
    if failed.outcome == "CONVERGED" or not recovery:
        return failed
    if failed.outcome not in EDGE3_TRIGGERS:
        return failed
    if fs.q_spec is None:
        failed.recovery = "unsupported(no_continuation_parameter)"
        return failed
    if start == "opening":
        x_open, regimes = project(x0)
    else:  # ablation: the failed solve's end state and last signature
        x_open, regimes = dict(failed.x), dict(failed.attempts[-1].regimes)
    h = homotopy(x_open, regimes, fs, hp)
    failed.homotopy, failed.recovery = h, "taken"
    if h.outcome != "CONVERGED":
        failed.outcome, failed.x = h.outcome, h.x
        return failed
    bad = next(
        (
            u
            for u in UNITS
            if branch_found(u, h.x) != "TWO_PHASE"
            and admissibility(u, h.x, branch_found(u, h.x)) > 1 + ADMISSIBILITY_EPSILON
        ),
        None,
    )
    assert bad is None, "no registered continuation converges onto an inadmissible branch"
    failed.outcome, failed.x = "CONVERGED", h.x
    return failed


# --------------------------------------------------------------------------------------------
# 9. Synthetic seeds on the generic PTC core (T04 §9.4), and the bare controller (T03 §6.6)
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Seed:
    ids: tuple[str, ...]
    rows: tuple[str, ...]
    holdup: frozenset[str]
    f: Callable[[dict[str, Any]], dict[str, Any] | None]
    j: Callable[[dict[str, Any]], list[list[Any]]]
    m: Callable[[dict[str, Any]], list[list[Any]]]
    tol: dict[str, Any]
    lower: dict[str, Any]
    regime: Callable[[dict[str, Any]], str] | None = None


@dataclass
class SeedRun:
    outcome: str
    k: int
    x: dict[str, Any]
    events: list[tuple[Any, ...]] = field(default_factory=list)
    wall: list[int] = field(default_factory=list)
    candidates: list[tuple[Any, ...]] = field(default_factory=list)
    blocked: tuple[str, ...] = ()
    tau_end: Any = None
    min_phi_at_ratio: Any = None
    margin: Any = None


def seed_ptc(
    s: Seed,
    x0: dict[str, Any],
    pol: PTCPolicy = PTC,
    regime: str | None = None,
    tau_start: Any = None,
) -> SeedRun:
    x = dict(x0)
    fv = s.f(x)
    assert fv is not None
    phi = sqrt(sum(fv[r] ** 2 for r in s.rows))
    tau = pol.tau_initial if tau_start is None else tau_start
    run = SeedRun("", 0, x)
    prev = None
    for k in range(pol.max_steps + 1):
        worst_now = max(abs(fv[r]) / s.tol[r] for r in s.rows)
        stop = worst_now <= 1 if pol.stop == "k03" else phi <= pol.phi_floor
        if stop:
            run.margin = min(1 / worst_now, prev) if prev is not None else 1 / worst_now
            run.outcome, run.k, run.x, run.tau_end = "CONVERGED", k, x, tau
            return run
        prev = worst_now
        if k == pol.max_steps:
            run.outcome, run.k, run.x, run.tau_end = "BUDGET_EXHAUSTED", k, x, tau
            return run
        jm, mm, n = s.j(x), s.m(x), len(s.ids)
        tau_try, retry, rejected_phi = tau, 0, None
        blocked: tuple[str, ...] = ()
        while True:
            reason = ""
            _log_tau(tried=tau_try)
            a = matrix(n, n)
            for i, r in enumerate(s.rows):
                sg = pol.holdup_row_sign if r in s.holdup else 1
                for jj in range(n):
                    a[i, jj] = (mm[i][jj] / tau_try if r in s.holdup else 0) + sg * jm[i][jj]
            rhs = matrix([-(pol.holdup_row_sign if r in s.holdup else 1) * fv[r] for r in s.rows])
            try:
                d = lu_solve(a, rhs)
            except ZeroDivisionError:
                reason = "linear_solve_failed"
            if not reason:
                dd = {v: d[jj] for jj, v in enumerate(s.ids)}
                ratios = {
                    v: (s.lower[v] - x[v]) / dd[v]
                    for v in s.ids
                    if v in s.lower and dd[v] < 0 and x[v] + dd[v] < s.lower[v]
                }
                amax = min([mpf(1), *ratios.values()])
                if amax <= 0:
                    reason = "bound_blocked"
                    blocked = tuple(v for v in ratios if x[v] <= s.lower[v])
                else:
                    y = {v: x[v] + amax * dd[v] for v in s.ids}
                    for v, q in ratios.items():
                        if q == amax:
                            y[v] = s.lower[v]
                    fy = s.f(y)
                    if fy is None:
                        reason = "invalid_trial"
                    elif regime is not None and s.regime is not None and s.regime(y) != regime:
                        reason = "phase_update_required"
                        rejected_phi = sqrt(sum(fy[r] ** 2 for r in s.rows))
                        if not run.candidates or run.candidates[0][0] != k:
                            run.candidates = []
                        run.candidates.append((k, retry, y, s.regime(y)))
                        if not run.wall or run.wall[-1] != k:
                            run.wall.append(k)
            if not reason:
                break
            run.events.append(("reject", k, tau_try, reason))
            retry += 1
            if retry > pol.retries_max or tau_try * pol.retry_shrink < pol.tau_min:
                out = "BOUND_BLOCKED" if reason == "bound_blocked" else "PTC_STALLED"
                run.outcome, run.k, run.x, run.tau_end, run.blocked = out, k, x, tau_try, blocked
                return run
            tau_try = tau_try * pol.retry_shrink
        assert fy is not None
        phi_new = sqrt(sum(fy[r] ** 2 for r in s.rows))
        x, fv = y, fy
        tau_next = None
        if pol.stop != "k03" or not max(abs(fv[r]) / s.tol[r] for r in s.rows) <= 1:
            base = tau_try if pol.ratio_tau == "used" else tau
            den = max(phi_new, pol.phi_floor) if pol.use_floor else phi_new
            if pol.rejected_phi and rejected_phi is not None:
                den = rejected_phi
            run.min_phi_at_ratio = (
                phi_new if run.min_phi_at_ratio is None else min(run.min_phi_at_ratio, phi_new)
            )
            ratio = phi / den
            if pol.clip:
                ratio = min(max(ratio, pol.gamma_min), pol.gamma_max)
            _log_tau(proposed=base * ratio)
            tau_next = min(max(base * ratio, pol.tau_min), pol.tau_max)
            tau = tau_next
        run.events.append(("accept", k, tau_try, phi_new, amax, dict(y), tau_next))
        phi = phi_new
        recent = run.wall[-2:]
        if len(recent) == 2 and recent[1] == recent[0] + 1 and recent[1] == k:
            run.outcome, run.k, run.x, run.tau_end = "PHASE_UPDATE_REQUIRED", k + 1, x, tau
            return run
    raise AssertionError("unreachable")


ONE, ZERO = mpf(1), mpf(0)


def _band(b1: Any, b2: Any) -> Callable[[dict[str, Any]], str]:
    return lambda x: "LIQUID" if x["x"] < b1 else ("TWO_PHASE" if x["x"] < b2 else "VAPOR")


SEEDS: dict[str, tuple[Seed, dict[str, Any], str | None]] = {
    # S1: the analytic limit -- one well-mixed vessel filling from empty, F = 1 − x, holdup θx
    "PTC-S1": (
        Seed(
            ("x",),
            ("hold",),
            frozenset({"hold"}),
            lambda x: {"hold": 1 - x["x"]},
            lambda x: [[-ONE]],
            lambda x: [[ONE]],
            {"hold": mpf("1e-8")},
            {"x": ZERO},
        ),
        {"x": ZERO},
        None,
    ),
    # S2: rejection and retry with a residual -- F = 1 − x³, a regime wall at x > 1.05
    "PTC-S2": (
        Seed(
            ("x",),
            ("hold",),
            frozenset({"hold"}),
            lambda x: {"hold": 1 - x["x"] ** 3},
            lambda x: [[-3 * x["x"] ** 2]],
            lambda x: [[ONE]],
            {"hold": mpf("1e-8")},
            {"x": ZERO},
            lambda x: "LIQUID" if x["x"] <= mpf("1.05") else "VAPOR",
        ),
        {"x": mpf("0.1")},
        "LIQUID",
    ),
    # S3: the algebraic stall -- an algebraic row whose Newton target y = 10 lies outside y ≤ 5
    "PTC-S3": (
        Seed(
            ("x", "y"),
            ("hold", "alg"),
            frozenset({"hold"}),
            lambda x: None if x["y"] > 5 else {"hold": 1 - x["x"], "alg": x["y"] - 10},
            lambda x: [[-ONE, ZERO], [ZERO, ONE]],
            lambda x: [[ONE, ZERO], [ZERO, ZERO]],
            {"hold": mpf("1e-8"), "alg": mpf("1e-8")},
            {"x": ZERO},
        ),
        {"x": ZERO, "y": ZERO},
        None,
    ),
    # S4: the bound -- a holdup whose steady state (−0.5) lies below its bound 0
    "PTC-S4": (
        Seed(
            ("x",),
            ("hold",),
            frozenset({"hold"}),
            lambda x: {"hold": mpf("-0.5") - x["x"]},
            lambda x: [[-ONE]],
            lambda x: [[ONE]],
            {"hold": mpf("1e-8")},
            {"x": ZERO},
        ),
        {"x": ONE},
        None,
    ),
    # S5: restart and reset -- T03's PHS-SYN-1 bands (1, 2) with F = 3 − x, holdup θx
    "PTC-S5": (
        Seed(
            ("x",),
            ("hold",),
            frozenset({"hold"}),
            lambda x: {"hold": 3 - x["x"]},
            lambda x: [[-ONE]],
            lambda x: [[ONE]],
            {"hold": mpf("1e-12")},
            {},
            _band(mpf(1), mpf(2)),
        ),
        {"x": ZERO},
        "bare",
    ),
}


def bare(
    s: Seed, x0: dict[str, Any], pol: PTCPolicy = PTC
) -> tuple[str, list[tuple[str, SeedRun]]]:
    """T03 §6.6's bare controller with the PTC core; the SER state resets per attempt unless the
    `reset` ablation carries it."""
    assert s.regime is not None
    x, regime = dict(x0), s.regime(x0)
    used: list[str] = []
    out: list[tuple[str, SeedRun]] = []
    carried = None
    for a in range(MAX_ATTEMPTS):
        used.append(regime)
        run = seed_ptc(s, x, pol, regime, tau_start=None if pol.reset else carried)
        carried = run.tau_end
        out.append((regime, run))
        if run.outcome == "CONVERGED":
            return "CONVERGED", out
        stall = run.outcome == "PTC_STALLED" and run.wall and run.k - run.wall[-1] < 5
        if not (run.outcome == "PHASE_UPDATE_REQUIRED" or stall):
            return run.outcome, out
        pick = next((c for c in run.candidates if (regime, c[3]) in ADJACENT), run.candidates[0])
        new, x = pick[3], dict(pick[2])
        if a + 1 == MAX_ATTEMPTS:
            return "ATTEMPTS_EXHAUSTED", out
        if new in used:
            return "ACTIVE_SET_CYCLING", out
        regime = new
    raise AssertionError("unreachable")


def run_seed(name: str, pol: PTCPolicy = PTC) -> tuple[str, list[tuple[str | None, SeedRun]]]:
    s, x0, mode = SEEDS[name]
    if mode == "bare":
        res, atts = bare(s, x0, pol)
        return res, [(g, r) for g, r in atts]
    r = seed_ptc(s, x0, pol, regime=mode)
    return r.outcome, [(mode, r)]


# --------------------------------------------------------------------------------------------
# 10. Output helpers
# --------------------------------------------------------------------------------------------


def s(v: Any, digits: int = 20) -> str:
    return p01.s(v, digits)


def frac(q: Fraction) -> str:
    return f"{q.numerator}/{q.denominator}" if q.denominator != 1 else str(q.numerator)


def attempts_record(sol: Solve) -> list[dict[str, Any]]:
    out = []
    for a in sol.attempts:
        r = a.run
        item: dict[str, Any] = {
            "signature": sigtext(signature(a.regimes)),
            "opening_source": a.source,
            "core": r.core,
            "core_outcome": r.outcome,
            "iterations": r.iterations,
            "decision": a.decision,
            # ADR 0005 D7 / T03 §8.1: `""` for `converged`; a terminal item's cause is the core's
            # closing message, which no specification gives a grammar for, so it is not registered
            # here (null) and is compared with the solve's own closing message instead (T04 A04).
            "cause": None if a.decision == "terminal" else a.cause,
        }
        if r.core == "ptc":
            item["rejected_trials"] = sum(1 for t in r.trials if t.verdict != "accepted")
            item["polish"] = r.polish or None
        if r.landings:
            item["landings"] = [
                {"iteration": i, "alpha_max": s(am, 15), "variables": list(v)}
                for i, am, v in r.landings
            ]
        if r.blocked:
            item["blocked_by"] = list(r.blocked)
        out.append(item)
    return out


def homotopy_record(h: HomotopyRun) -> dict[str, Any]:
    return {
        "outcome": h.outcome,
        "lambda_reached": frac(h.lam),
        "lambda_trials": len(h.steps) - 1,
        # §4.7 as amended: the provenance item's `iterations` = every corrector's, rejected too
        "provenance_item_iterations": sum(st[3] for st in h.steps),
        "steps": [
            {
                "lambda": frac(st[0]),
                "delta_lambda": frac(st[1]),
                "corrector_outcome": st[2],
                "corrector_iterations": st[3],
                "accepted": st[4],
                "S3_T_K": s(st[5], 15),
                **(
                    {
                        "landings": [
                            {"iteration": i, "alpha_max": s(am, 12), "variables": list(v)}
                            for i, am, v in st[6]
                        ]
                    }
                    if st[6]
                    else {}
                ),
                **({"blocked_by": list(st[7])} if st[7] else {}),
            }
            for st in h.steps
        ],
        "end_S3_T_K": s(h.x["S3.T"]),
        "end_S3_V_mol_per_s": s(h.x["S3.V"]),
    }


def state_error(x: dict[str, Any], ref: dict[str, Any]) -> dict[str, str]:
    """The largest distance of `x` from `ref`, per quantity kind (T02 §6.4's comparison)."""
    kinds: dict[str, Any] = {}
    for v in COLUMNS:
        k = column_kind(v)
        kinds[k] = max(kinds.get(k, mpf(0)), abs(x[v] - ref[v]))
    return {k: s(val, 3) for k, val in sorted(kinds.items())}


# --------------------------------------------------------------------------------------------
# 11. Closed forms: the loop's inventory modes (§6.6), the flash split Jacobian, λ at a boundary
# --------------------------------------------------------------------------------------------


def flash_split_jacobian(w: Sequence[Any], t: Any, p: Any) -> matrix:
    """D = ∂ℓ/∂w of a two-phase TP flash, by implicit differentiation of Rachford–Rice."""
    k = [p01.k_value(i, t, p) for i in range(3)]
    b = p01.tp_flash(list(w), t, p)["beta"]
    g = [(1 - b) / (1 + b * (kk - 1)) for kk in k]
    dg = [(-(1 + b * (kk - 1)) - (1 - b) * (kk - 1)) / (1 + b * (kk - 1)) ** 2 for kk in k]
    f_beta = -sum(w[i] * (k[i] - 1) ** 2 / (1 + b * (k[i] - 1)) ** 2 for i in range(3))
    db = [-((k[j] - 1) / (1 + b * (k[j] - 1))) / f_beta for j in range(3)]
    d = matrix(3, 3)
    for i in range(3):
        for j in range(3):
            d[i, j] = (g[i] if i == j else 0) + w[i] * dg[i] * db[j]
    return d


def modes_closed_form(r: Any, theta: Any) -> dict[str, Any]:
    fs = Flowsheet(r=r)
    x = reconstruct(tear_root(r), fs)
    assert x is not None
    w = [x[f"S3.n.{c}"] for c in C]
    d = flash_split_jacobian(w, fs.t_flash, fs.p)
    d2 = sum(d[i, i] for i in range(3)) - 1
    mus = [r * mpf(1), r * d2, mpf(0)]
    s_values = sorted(
        [(-1 + sqrt(mu)) / theta for mu in mus] + [(-1 - sqrt(mu)) / theta for mu in mus]
    )
    return {"x": x, "D": d, "d2": d2, "mu": mus, "s": s_values}


def pencil_reduced(x0: dict[str, Any], r: Any, pol: PTCPolicy = PTC) -> matrix:
    """Ĵ_σ⁻¹ M̂ at the state: its nonzero eigenvalues ν give the finite modes s = −1/ν."""
    fs = Flowsheet(r=r)
    x, regimes = project(x0)
    free, rows = system(regimes, fs)
    _, js, ms, _ = _ptc_matrix(x, free, rows, fs, pol)
    return inverse(js) * ms


def modes_from_pencil(r: Any, pol: PTCPolicy = PTC) -> list[Any]:
    """The finite generalized eigenvalues of (Ĵ_σ, M̂) at the root: s with (Ĵ_σ + s M̂) v = 0."""
    x = reconstruct(tear_root(r), Flowsheet(r=r))
    assert x is not None
    nu = eig(pencil_reduced(x, r, pol), left=False, right=False)
    return sorted((-1 / e).real for e in nu if abs(e) > mpf("1e-20"))


def singular_values(a: matrix) -> list[Any]:
    sv = svd_r(a, compute_uv=False)
    return sorted(abs(sv[i]) for i in range(len(sv)))


def lambda_at_temperature(q_target: Any, q0: Any, q_at_boundary: Any) -> Any:
    """λ with p(λ) = Q_flash(T_boundary) on the linear parameter path."""
    return (q_at_boundary - q0) / (q_target - q0)


def q_flash_vapor_branch(t: Any) -> Any:
    """Q_flash with the heater outlet all vapour at T (the VAPOR-signature path, HOM-03)."""
    h3 = sum(t03.N3[i] * (CP * (t - T_REF) + L_VAP[i]) for i in range(3))
    return t03.H_OUT - h3


def cstr_preregistered() -> dict[str, Any]:
    """T04 §8.4, PTC-R1 (not run): the dimensionless cooled CSTR's steady states and their modes.

    ẋ₁ = −x₁ + Da (1 − x₁) e^{x₂},  Le ẋ₂ = −x₂ + B Da (1 − x₁) e^{x₂} − β x₂;  at a steady state
    x₁ = Da e^{x₂} / (1 + Da e^{x₂}) and (1 + β) x₂ = B x₁.
    """
    da, b, beta = mpf("0.072"), mpf(8), mpf("0.3")

    def g(x2: Any) -> Any:
        return (1 + beta) * x2 - b * da * exp(x2) / (1 + da * exp(x2))

    grid = [mpf(i) / 100 for i in range(801)]
    roots = []
    for lo, hi in zip(grid, grid[1:], strict=False):
        if g(lo) * g(hi) < 0:
            a, c = lo, hi
            for _ in range(200):
                m = (a + c) / 2
                a, c = (m, c) if g(a) * g(m) > 0 else (a, m)
            roots.append((a + c) / 2)
    states = []
    for x2 in roots:
        e = da * exp(x2)
        x1 = e / (1 + e)
        jac = matrix([[-1 - e, (1 - x1) * e], [-b * e, -1 - beta + b * (1 - x1) * e]])
        ev = sorted(complex(z).real for z in eig(jac, left=False, right=False))
        states.append({"x1": x1, "x2": x2, "eigenvalues": ev})
    return {"Da": da, "B": b, "beta": beta, "states": states}


# --------------------------------------------------------------------------------------------
# 11b. K04 on the bound declaration (T04 §4.8): the 47 x 47 target, its norms, the determinant
#      identity, and the fresh-flash comparisons K04 §4.4/§4.7 make at a lifted two-phase stream
# --------------------------------------------------------------------------------------------

FEED_ROWS = (*[f"U-FEED:FEED-n:{c}" for c in C], "U-FEED:FEED-T", "U-FEED:FEED-P")
S1_COLUMNS = (*[f"S1.n.{c}" for c in C], "S1.T", "S1.P")
TARGET_COLUMNS = S1_COLUMNS + COLUMNS
TARGET_COL_SCALE = COL_SCALE | {v: SCALE[column_kind(v)] for v in S1_COLUMNS}
FEED_ROW_SCALE = {r: SCALE[column_kind(v)] for r, v in zip(FEED_ROWS, S1_COLUMNS, strict=True)}
#: K04 §7.4: the absolute-conditioning limit tau_min / (n eps), n = 47, eps = 2^-52.
ABSOLUTE_LIMIT_47 = mpf("1e-8") / (47 * mpf(2) ** -52)
TAU_ILL = mpf("1e-8")
FLOW_TOL = TOLERANCE["molar_flow"]
ENERGY_TOL = TOLERANCE["heat_rate"]


def with_feed(x: dict[str, Any]) -> dict[str, Any]:
    feed = {f"S1.n.{c}": FRESH[i] for i, c in enumerate(C)} | {"S1.T": T_FEED, "S1.P": P_REF}
    return {**x, **feed}


def residual47(x: dict[str, Any], fs: Flowsheet) -> dict[str, Any]:
    """The declaration's rows minus its two certified aliases: U-FEED's written `v - p` rows and
    the region's (T02 §7.3: 49 - 2 = 47 over 47 columns)."""
    out = residual(x, fs)
    for i, c in enumerate(C):
        out[f"U-FEED:FEED-n:{c}"] = x[f"S1.n.{c}"] - FRESH[i]
    out["U-FEED:FEED-T"] = x["S1.T"] - T_FEED
    out["U-FEED:FEED-P"] = x["S1.P"] - P_REF
    return out


def target47(
    x: dict[str, Any], fs: Flowsheet, rows: Sequence[str] | None = None, scaled: bool = True
) -> matrix:
    """K04 §7.1 for the declaration `fs` binds: rows `FEED_ROWS + fs.rows`, every column."""
    rows = tuple(rows) if rows is not None else FEED_ROWS + fs.rows
    x47 = with_feed(x)
    xd = {v: Dual(x47[v], {v: mpf(1)}) for v in TARGET_COLUMNS}
    out = residual47(xd, fs)
    at = {v: j for j, v in enumerate(TARGET_COLUMNS)}
    jac = matrix(len(rows), len(TARGET_COLUMNS))
    row_scale = ROW_SCALE | FEED_ROW_SCALE
    for i, r in enumerate(rows):
        e = out[r]
        if isinstance(e, Dual):
            for k, g in e.g.items():
                j = at[k]
                jac[i, j] = g * TARGET_COL_SCALE[k] / row_scale[r] if scaled else g
    return jac


def one_norm(a: matrix) -> Any:
    return max(sum(abs(a[i, j]) for i in range(a.rows)) for j in range(a.cols))


def regularity47(x: dict[str, Any], fs: Flowsheet) -> dict[str, Any]:
    jac = target47(x, fs)
    norm, inv_norm = one_norm(jac), one_norm(inverse(jac))
    entries = [abs(jac[i, j]) for i in range(jac.rows) for j in range(jac.cols)]
    return {
        "one_norm": norm,
        "inverse_one_norm": inv_norm,
        "rcond_1": 1 / (norm * inv_norm),
        "smallest_nonzero_entry": min(e for e in entries if e > mpf("1e-30")),
    }


def h_s3_fresh(x: dict[str, Any], t: Any) -> Any:
    """Ḣ(S3) from a fresh flash of S3's `(n, t, P)` — never from the lifted split (K04 §4.4)."""
    _, sp = kernel(HEATER, {**x, "S3.T": t})
    return sum(
        sp[f"S3.vap.{c}"] * h_vap(i, t, ZERO3) + sp[f"S3.liq.{c}"] * h_liq(i, t, x["S3.P"], ZERO3)
        for i, c in enumerate(C)
    )


def fresh_flash_checks(x: dict[str, Any], fs: Flowsheet) -> dict[str, Any]:
    """K04 §4.7's independent split and §4.4's heater balance at S3, the heater's lifted split,
    and (K04 §4.7's second clause, not implemented at `1f632ed`) the flash outlets' split."""
    _, sp = kernel(HEATER, x)
    h2 = sum(x[f"S2.n.{c}"] * h_liq(i, x["S2.T"], x["S2.P"], ZERO3) for i, c in enumerate(C))
    _, fo = kernel(FLASH, x)
    values = evaluate(x, fs)
    return {
        "worst_row_over_tolerance": max(abs(values[r]) / ROW_TOL[r] for r in fs.rows),
        "worst_row": max(fs.rows, key=lambda r: abs(values[r]) / ROW_TOL[r]),
        "independent_split_S3_total": x["S3.V"] - sp["S3.V"],
        "independent_split_S3": [x[f"S3.vap.{c}"] - sp[f"S3.vap.{c}"] for c in C],
        "energy_heater_W": h2 + x["U-HEAT.Q"] - h_s3_fresh(x, x["S3.T"]),
        "independent_split_flash_total": x["S4.N"] - fo["S4.N"],
    }


def band_ratio(fc: dict[str, Any]) -> Any:
    """The largest thresholded value over its threshold among §4.4/§4.7's S3 checks."""
    return max(
        abs(fc["independent_split_S3_total"]) / FLOW_TOL,
        *(abs(v) / FLOW_TOL for v in fc["independent_split_S3"]),
        abs(fc["energy_heater_W"]) / ENERGY_TOL,
    )


def lifted_block_amplification(x: dict[str, Any], fs: Flowsheet) -> dict[str, Any]:
    """Worst case over |e_j| <= tau_eq of the heater's lifted split error against the flash, to
    first order: w - w* = B^-1 r with B the 8 x 8 block (eq, split, Vdef, Ldef) x (v, l, V, L)
    at fixed (n, T, P); the linear rows are exact at any Newton iterate, so r = (e, 0)."""
    cols = (*HEATER.vapor, *HEATER.liquid, HEATER.vtot, HEATER.ltot)
    rows = (
        *HEATER.eq_rows,
        *[f"U-HEAT:split:{c}" for c in C],
        HEATER.vdef,
        HEATER.ldef,
    )
    _, jac = jacobian(x, cols, rows, fs)
    inv = inverse(jac)
    tau_eq = TOLERANCE["molar_flow_squared"]
    dv = [sum(abs(inv[i, j]) for j in range(3)) * tau_eq for i in range(8)]
    latent = [h_vap(i, x["S3.T"], ZERO3) - h_liq(i, x["S3.T"], x["S3.P"], ZERO3) for i in range(3)]
    energy = sum(abs(sum(latent[i] * inv[i, j] for i in range(3))) for j in range(3)) * tau_eq
    return {
        "worst_split_total_over_tau_flow": dv[6] / FLOW_TOL,
        "worst_split_component_over_tau_flow": max(dv[:3]) / FLOW_TOL,
        "worst_energy_over_tau_energy": energy / ENERGY_TOL,
    }


def determinant_identity(x: dict[str, Any], fs: Flowsheet) -> dict[str, Any]:
    """det J_A02 / det J_nom at one state = dQ_f/dT along {common rows = 0} = -dH_S3/dT.

    The two unscaled 47 x 47 targets share every row but one (HEAT-T = S3.T - T_h against
    SPEC = Q_f - Q_spec), placed last in both; the cofactor vector of the 46 common rows spans
    their kernel, so the ratio of the two determinants is the kernel's Q_f/S3.T ratio."""
    nominal = Flowsheet(r=fs.r, t_heater=x["S3.T"])
    common = tuple(r for r in FEED_ROWS + NOMINAL_ROWS if r != "U-HEAT:HEAT-T")
    d_a02 = det(target47(x, fs, (*common, SPEC_ROW), scaled=False))
    d_nom = det(target47(x, nominal, (*common, "U-HEAT:HEAT-T"), scaled=False))
    h = mpf("1e-12")
    dh = (h_s3_fresh(x, x["S3.T"] + h) - h_s3_fresh(x, x["S3.T"] - h)) / (2 * h)
    return {"ratio": d_a02 / d_nom, "dH_S3_dT": dh, "det_nominal": d_nom}


# --------------------------------------------------------------------------------------------
# 12. build(): every registered number, every claim checked
# --------------------------------------------------------------------------------------------

HOM_CASES = {
    # id: (registry id, target K, guess K, max_attempts, newton max iterations, why)
    "HOM-01": ("SYN-001-A02-355-dew-guess", 355, 375, MAX_ATTEMPTS, MAX_ITERATIONS),
    "HOM-02": ("SYN-001-A02-355-dew-guess-377", 355, 377, MAX_ATTEMPTS, MAX_ITERATIONS),
    "HOM-03": ("SYN-001-A02-352-vapor-guess-410", 352, 410, MAX_ATTEMPTS, MAX_ITERATIONS),
    "HOM-04": ("SYN-001-A02-340-two-phase-guess-capped", 340, 360, 1, MAX_ITERATIONS),
    "HOM-05": ("SYN-001-A02-360-iteration-capped", 360, 358, MAX_ATTEMPTS, 1),
}
LATTICE = [(i, j, 4 - i - j) for i in range(5) for j in range(5 - i)]
MAGNITUDES = (mpf("0.3"), mpf(3), mpf(30))
FAMILY_TARGETS = (340, 345, 350, 352, 355, 358, 360, 365, 370, 375)
FAMILY_GUESSES: tuple[Any, ...] = (*range(300, 440, 10), 375, 376, 377, mpf("377.4"))
OFF_A = (mpf("0.1"), mpf("0.8"), mpf("1.2"))
OFF_B = (mpf("0.05"), mpf("0.1"), mpf("4.0"))


def build(low_precision: bool = True) -> dict[str, Any]:  # noqa: C901 (one flat list of claims)
    checks: list[str] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        if not cond:
            raise AssertionError(f"self-check failed: {name} {detail}")
        checks.append(name)

    # ---- the twin is the implementation's system: two independent reductions agree ----------
    q = {t: t03.q_flash_at(mpf(t)) for t in (340, 352, 355, 358, 360)}
    x05, fs05 = a02_open(375, q[355])
    ok(
        "the full-region A02 opening at 375 K has the block's S3.n to 1e-18 mol/s and its flash "
        "duty to 1e-12 W (two 40-digit derivations of the loop, P01's and T02's)",
        abs(x05["U-FLASH.Q"] - t03.initial_state(mpf(375))[1]["Qf"]) < mpf("1e-12")
        and max(abs(x05[f"S3.n.{c}"] - t03.N3[i]) for i, c in enumerate(C)) < mpf("1e-18"),
    )
    probe = {**x05, "S3.T": mpf(366), "U-HEAT.Q": mpf(70000), "S2.T": mpf(330)}
    values, jac = jacobian(probe, COLUMNS, fs05.rows, fs05)
    worst_fd = mpf(0)
    for j, v in enumerate(COLUMNS):
        h = mpf("1e-15") * max(1, abs(probe[v]))
        up = evaluate({**probe, v: probe[v] + h}, fs05)
        dn = evaluate({**probe, v: probe[v] - h}, fs05)
        for i, r in enumerate(fs05.rows):
            fd = (up[r] - dn[r]) / (2 * h)
            worst_fd = max(worst_fd, abs(fd - jac[i, j]) / max(1, abs(jac[i, j])))
    ok(
        "the dual-number Jacobian equals central differences at 40 digits to 1e-20",
        worst_fd < mpf("1e-20"),
    )
    ok(
        "the region is square under the nominal and the A02 row sets",
        len(NOMINAL_ROWS) == 42 and len(fs05.rows) == 42,
    )

    # PHS-05 on the full region reproduces T03's registered block trajectory (T03 §6.4)
    t03_phs05 = t03.solve(mpf(375), q[355])
    full_phs05 = contract(x05, fs05)
    ok(
        "PHS-05 on the full region reproduces T03's attempts, counts and landing",
        full_phs05.outcome == t03_phs05.outcome == "ACTIVE_SET_CYCLING"
        and [(a.regimes["U-HEAT"], a.run.outcome, a.run.iterations) for a in full_phs05.attempts]
        == [(a.regime, a.run.outcome, a.run.iterations) for a in t03_phs05.attempts]
        and abs(
            full_phs05.attempts[0].run.landings[0][1]
            - t03_phs05.attempts[0].run.alpha_max_history[0]
        )
        < mpf("1e-15"),
    )

    # ---- §4: the homotopy cases (and the contract's failure that triggers edge 3) ------------
    hom_cases: dict[str, Any] = {}
    hom_solves: dict[str, Solve] = {}
    for cid, (reg, target, guess, max_att, max_it) in HOM_CASES.items():
        x0, fs = a02_open(guess, q[target] if target in q else t03.q_flash_at(mpf(target)))
        sol = solve_with_edge3(x0, fs, max_attempts=max_att, newton_max_it=max_it)
        hom_solves[cid] = sol
        assert sol.homotopy is not None
        hom_cases[cid] = {
            "registry_id": reg,
            "T_target_K": target,
            "guess_S3_T_K": s(mpf(guess), 6),
            "policy_overrides": (
                {"max_attempts": max_att}
                if max_att != MAX_ATTEMPTS
                else {"max_iterations_per_attempt": max_it}
                if max_it != MAX_ITERATIONS
                else {}
            ),
            "Q_flash_spec_W": s(fs.q_spec),
            "contract": {"outcome": sol.contract_outcome, "attempts": attempts_record(sol)},
            "edge3": sol.recovery,
            "homotopy": homotopy_record(sol.homotopy),
            "outcome": sol.outcome,
        }
    h1, h2, h3, h4, h5 = (hom_solves[c] for c in ("HOM-01", "HOM-02", "HOM-03", "HOM-04", "HOM-05"))
    ok(
        "HOM-01 (PHS-05): the contract ends ACTIVE_SET_CYCLING (T03 A12 unchanged)",
        hom_cases["HOM-01"]["contract"]["outcome"] == "ACTIVE_SET_CYCLING",
    )
    ok(
        "HOM-01: edge 3 converges in 3 λ-trials 1/4, 3/4, 1 with correctors 4, 4, 4 and no "
        "rejection",
        h1.outcome == "CONVERGED"
        and [(st[0], st[3], st[4]) for st in h1.homotopy.steps[1:]]
        == [(Fraction(1, 4), 4, True), (Fraction(3, 4), 4, True), (Fraction(1), 4, True)]
        and h1.homotopy.steps[0][3] == 0,
    )
    ok("HOM-01: the λ = 1 root is the 355 K root to 1e-6 K", abs(h1.x["S3.T"] - 355) < mpf("1e-6"))
    ok(
        "HOM-02 (377 K): converges in 3 λ-trials with one landing of S3.vap.C at λ = 3/4 that "
        "does not close the corrector",
        h2.outcome == "CONVERGED"
        and len(h2.homotopy.steps) == 4
        and h2.homotopy.steps[2][6]
        and h2.homotopy.steps[2][4],
    )
    ok(
        "HOM-03 (352 K from 410 K): the contract cycles, edge 3 stalls",
        hom_cases["HOM-03"]["contract"]["outcome"] == "ACTIVE_SET_CYCLING"
        and h3.outcome == "HOMOTOPY_STALLED",
    )
    ok(
        "HOM-04 (PHS-04, max_attempts = 1): ATTEMPTS_EXHAUSTED, then edge 3 stalls",
        hom_cases["HOM-04"]["contract"]["outcome"] == "ATTEMPTS_EXHAUSTED"
        and h4.outcome == "HOMOTOPY_STALLED",
    )
    ok(
        "HOM-05 (A02-360, max_iterations = 1): BUDGET_EXHAUSTED, then edge 3 converges to 360 K",
        hom_cases["HOM-05"]["contract"]["outcome"] == "BUDGET_EXHAUSTED"
        and h5.outcome == "CONVERGED"
        and abs(h5.x["S3.T"] - 360) < mpf("1e-6"),
    )

    def accepted_lams(h: HomotopyRun) -> list[Fraction]:
        return [st[0] for st in h.steps[1:] if st[4]]

    ok(
        "HOM-03: 17 λ-trials, accepted at 1/16, 5/64, 11/128, 23/256, every rejection "
        "PHASE_UPDATE_REQUIRED; the last root 0.317 K above the dew point",
        len(h3.homotopy.steps) - 1 == 17
        and accepted_lams(h3.homotopy)
        == [Fraction(1, 16), Fraction(5, 64), Fraction(11, 128), Fraction(23, 256)]
        and all(st[2] == "PHASE_UPDATE_REQUIRED" for st in h3.homotopy.steps[1:] if not st[4])
        and abs(h3.x["S3.T"] - t03.T_DEW - mpf("0.317")) < mpf("1e-3"),
    )
    ok(
        "§4.7 as amended (review Q1): the provenance item's iterations — every corrector's, "
        "rejected λ-trials included — are 12, 12, 30, 28, 9 on HOM-01…05 (HOM-03's accepted "
        "correctors ran 4 of its 30)",
        [hom_cases[c]["homotopy"]["provenance_item_iterations"] for c in HOM_CASES]
        == [12, 12, 30, 28, 9]
        and sum(st[3] for st in h3.homotopy.steps if st[4]) == 4,
    )
    ok(
        "HOM-04: 18 λ-trials, accepted at 1/4, 3/4, 7/8, 113/128, 227/256, 909/1024, every "
        "rejection BOUND_BLOCKED on S3.vap.C",
        len(h4.homotopy.steps) - 1 == 18
        and accepted_lams(h4.homotopy)
        == [
            Fraction(1, 4),
            Fraction(3, 4),
            Fraction(7, 8),
            Fraction(113, 128),
            Fraction(227, 256),
            Fraction(909, 1024),
        ]
        and all(
            st[2] == "BOUND_BLOCKED" and "S3.vap.C" in st[7]
            for st in h4.homotopy.steps[1:]
            if not st[4]
        ),
    )
    ok(
        "HOM-05: λ-trials 1/4, 3/4, 1 with correctors 3, 3, 3",
        [(st[0], st[3]) for st in h5.homotopy.steps[1:]]
        == [(Fraction(1, 4), 3), (Fraction(3, 4), 3), (Fraction(1), 3)],
    )
    # the stalls bracket the phase boundary on the path
    q0_04 = a02_open(360, q[340])[0]["U-FLASH.Q"]
    lam_b = lambda_at_temperature(q[340], q0_04, t03.q_flash_at(t03.T_BUBBLE))
    q0_03 = a02_open(410, t03.q_flash_at(mpf(352)))[0]["U-FLASH.Q"]
    lam_d = lambda_at_temperature(t03.q_flash_at(mpf(352)), q0_03, q_flash_vapor_branch(t03.T_DEW))
    for name, run, lb in (("HOM-04", h4, lam_b), ("HOM-03", h3, lam_d)):
        hr = run.homotopy
        lam_last = mpf(hr.lam.numerator) / hr.lam.denominator
        rejected_above = [
            mpf(st[0].numerator) / st[0].denominator for st in hr.steps[1:] if not st[4]
        ]
        accepted = [mpf(st[0].numerator) / st[0].denominator for st in hr.steps[1:] if st[4]]
        ok(
            f"{name}: every accepted λ lies below the boundary λ_b and every rejected one above it",
            all(a < lb for a in accepted) and all(r > lb for r in rejected_above),
        )
        ok(
            f"{name}: λ_last < λ_b < λ_last + 2 Δλ_min (the stall brackets the boundary)",
            lam_last < lb < lam_last + 2 * mpf(1) / 1024,
        )
        ok(
            f"{name}: every λ decision is at least 2e-5 from λ_b",
            min(abs(mpf(st[0].numerator) / st[0].denominator - lb) for st in hr.steps[1:])
            > mpf("2e-5"),
        )
    ok(
        "HOM-04: the reported stall state is the last accepted root, V = 1.28e-3 mol/s",
        abs(h4.x["S3.V"] - mpf("0.001281")) < mpf("1e-6"),
    )
    hom_closed = {
        "HOM-04_lambda_bubble": s(lam_b),
        "HOM-03_lambda_dew_vapor_branch": s(lam_d),
        "S3_bubble_point_K": s(t03.T_BUBBLE),
        "S3_dew_point_K": s(t03.T_DEW),
    }
    # endpoint equivalence: the continuation's root is Newton's root (same revision, other guess)
    x355, fs355 = a02_open(358, q[355])
    newton355 = contract(x355, fs355)
    dist = max(abs(h1.x[v] - newton355.x[v]) / COL_SCALE[v] for v in COLUMNS)
    ok(
        "HOM-01's root and A02-355's Newton root (358 K) are the same root: scaled distance < 1e-8",
        newton355.outcome == "CONVERGED" and dist < mpf("1e-8"),
    )
    ok(
        "the λ = 1 instance is the target instance: p(1) = p* exactly",
        continued(fs05, mpf(12345), Fraction(1)).q_spec == fs05.q_spec,
    )

    # ---- §6: the mapping -- pattern, sign, dimension, reference invariance, modes --------------
    fs95 = Flowsheet(r=mpf("0.95"))
    x_root95 = reconstruct(tear_root(mpf("0.95")), fs95)
    assert x_root95 is not None
    x_root95, reg95 = project(x_root95)
    free95, rows95 = system(reg95, fs95)
    ents = mass_entries(x_root95, fs95, PTC)
    ok(
        "ADR 0008 D5: the rows with a nonzero M are exactly the eight holdup_balance rows",
        {r for (r, _), v in ents.items() if v != 0} == set(HOLDUP_ROWS),
    )
    ok(
        "no M entry on a zero_holdup_balance (mixer) or algebraic row",
        not ({r for (r, _) in ents} & (set(NOMINAL_ROWS) - HOLDUP_ROWS)),
    )
    ok(
        "the mapping validator refuses M on MIX-mole:A (the ablation)",
        validate_mapping({**ents, ("U-MIX:MIX-mole:A", "S2.n.A"): mpf(1)}, rows95, PTC)
        == "ptc_mapping_invalid(U-MIX:MIX-mole:A, not_holdup_balance)",
    )
    ok(
        "the mapping validator refuses a missing FLASH-duty mapping",
        validate_mapping(
            {k: v for k, v in ents.items() if k[0] != "U-FLASH:FLASH-duty"}, rows95, PTC
        )
        == "ptc_mapping_invalid(U-FLASH:FLASH-duty, missing)",
    )
    # steady-state equivalence: at the root the step is zero for every pseudo-step
    _, js, ms, fsig = _ptc_matrix(x_root95, free95, rows95, fs95, PTC)
    root_residual = max(abs(fsig[i]) for i in range(len(rows95)))
    ok(
        "the reconstructed P01 root at r = 0.95 is a root to 1e-18 scaled",
        root_residual < mpf("1e-18"),
    )
    for tau in (mpf("1e-6"), mpf(1), mpf("1e10")):
        stp = lu_solve(js + ms / tau, -fsig)
        ok(
            f"steady-state equivalence: at that root the PTC step at Δτ = {s(tau, 2)} is at most "
            "10 times the root's own residual",
            max(abs(stp[i]) for i in range(len(free95))) < 10 * root_residual,
        )
    # reference invariance of the step (§6.4): a shifted enthalpy reference moves nothing
    xa = reconstruct(OFF_A, fs95)
    assert xa is not None
    xa, rega = project(xa)
    fa, ra = system(rega, fs95)
    shift = (mpf(1000), mpf(-2000), mpf(500))
    fs95s = replace(fs95, h_shift=shift)

    # a probe off the split manifold (F_split,A = 0.1 mol/s) where the two mappings can differ
    probe_off = {**xa, "S3.liq.A": xa["S3.liq.A"] + mpf("0.1")}
    steps = {}
    for label, xx in (("on_manifold", xa), ("off_manifold", probe_off)):
        for mapping in ("phase_resolved", "stream_total"):
            pol = replace(PTC, mole_holdup=mapping)
            _, j1, m1, f1 = _ptc_matrix(xx, fa, ra, fs95, pol)
            # the same state x under the shifted reference: a duty is a heat flow and does not move
            _, j2, m2, f2 = _ptc_matrix(xx, fa, ra, fs95s, pol)
            d1 = lu_solve(j1 + m1 / mpf(1), -f1)
            d2 = lu_solve(j2 + m2 / mpf(1), -f2)
            steps[(label, mapping)] = (max(abs(d1[i] - d2[i]) for i in range(len(fa))), d1)
    ok(
        "§6.4: on the split manifold the phase-resolved and stream-total heater mole holdups "
        "give the same step to 1e-25 (no registered path can tell them apart)",
        max(
            abs(
                steps[("on_manifold", "phase_resolved")][1][i]
                - steps[("on_manifold", "stream_total")][1][i]
            )
            for i in range(len(fa))
        )
        < mpf("1e-25"),
    )
    ok(
        "§6.4: off the split manifold the phase-resolved step (every component) is invariant "
        "under an enthalpy-reference shift to 1e-25",
        steps[("off_manifold", "phase_resolved")][0] < mpf("1e-25"),
    )
    ok(
        "§6.4: off the split manifold the stream-total holdup's step moves by more than 1e-6 "
        "scaled under the same shift",
        steps[("off_manifold", "stream_total")][0] > mpf("1e-6"),
    )
    # modes (§6.6): the pencil at the root equals the closed form
    modes: dict[str, Any] = {}
    for r in (mpf("0.5"), mpf("0.95")):
        cf = modes_closed_form(r, PTC.residence_time)
        pen = modes_from_pencil(r)
        dev = eig(cf["D"], left=False, right=False)
        ok(
            f"r = {s(r, 2)}: the flash split Jacobian D has eigenvalues 1, d₂ = tr D − 1, 0",
            all(min(abs(e - t) for e in dev) < mpf("1e-30") for t in (mpf(1), cf["d2"], mpf(0))),
        )
        ok(
            f"r = {s(r, 2)}: the pencil has exactly six finite modes, equal to the closed form to "
            "1e-18",
            len(pen) == 6
            and max(abs(a - b) for a, b in zip(pen, cf["s"], strict=True)) < mpf("1e-18"),
        )
        ok(f"r = {s(r, 2)}: every finite mode is real and negative", all(v < 0 for v in cf["s"]))
        # F14 / A17: the μ = 0 mode is a heater→flash cascade without feedback — defective
        xr = reconstruct(tear_root(r), Flowsheet(r=r))
        assert xr is not None
        red = pencil_reduced(xr, r)
        a = red - eye(red.rows) * PTC.residence_time
        once, twice = singular_values(a), singular_values(a * a)
        ok(
            f"r = {s(r, 2)}: the double mode at −1/θ is one 2 × 2 Jordan block (nullity of "
            "Ĵ_σ⁻¹M̂ − θI is 1, of its square 2; the next singular value ≥ 1e-2)",
            once[0] < mpf("1e-30")
            and once[1] > mpf("1e-2")
            and twice[1] < mpf("1e-30")
            and twice[2] > mpf("1e-3"),
        )
        modes[f"r={s(r, 2)}"] = {
            "D_eigenvalues": ["1", s(cf["d2"]), "0"],
            "mu_eq_r_times_D_eigenvalues": [s(m) for m in cf["mu"]],
            "finite_modes_per_second": [s(v) for v in cf["s"]],
            "slowest_time_constant_s": s(-1 / cf["s"][-1]),
        }
    # the time-scale invariance (§6.5): θ and every τ constant scaled by 8 changes nothing
    pol8 = replace(
        PTC, residence_time=mpf(8), tau_initial=mpf(8), tau_min=mpf("8e-4"), tau_max=mpf("8e10")
    )
    base_run = ptc(xa, rega, fs95, PTC)
    run8 = ptc(xa, rega, fs95, pol8)
    ok(
        "§6.5: scaling θ and the τ constants by 8 reproduces the OFF-A pseudo-step count and "
        "every state",
        base_run.iterations == run8.iterations
        and max(abs(base_run.x[v] - run8.x[v]) / COL_SCALE[v] for v in COLUMNS) < mpf("1e-25"),
    )

    # ---- §7/§9.4: the synthetic seeds ------------------------------------------------------
    TAU_LOG.update(armed=True, tried_min=None, proposed_max=None)
    seeds: dict[str, Any] = {}
    seed_runs: dict[str, tuple[str, list[tuple[str | None, SeedRun]]]] = {}
    for name in SEEDS:
        res, atts = run_seed(name)
        seed_runs[name] = (res, atts)
        seeds[name] = {
            "outcome": res,
            "attempts": [
                {
                    "regime": g,
                    "outcome": r.outcome,
                    "pseudo_steps": r.k,
                    "events": [
                        {"step": e[1], "tau": s(e[2], 15), "result": e[3]}
                        if e[0] == "reject"
                        else {
                            "step": e[1],
                            "tau": s(e[2], 15),
                            "result": "accepted",
                            "phi": s(e[3], 15),
                            "alpha": s(e[4], 15),
                            "x": {k: s(v, 20) for k, v in e[5].items()},
                            "tau_next": s(e[6], 15) if e[6] is not None else None,
                        }
                        for e in r.events
                    ],
                    "blocked_by": list(r.blocked),
                }
                for g, r in atts
            ],
        }
    s1 = seed_runs["PTC-S1"][1][0][1]
    ok(
        "PTC-S1: CONVERGED at pseudo-step 8 with Δτ_k = 2^k exactly",
        s1.outcome == "CONVERGED"
        and s1.k == 8
        and [e[2] for e in s1.events] == [mpf(2) ** k for k in range(8)],
    )
    prod = mpf(1)
    exact = []
    for k in range(8):
        prod *= 1 + mpf(2) ** k
        exact.append(1 / prod)
    ok(
        "PTC-S1: φ_{k+1} = 1/∏_{j≤k}(1 + 2^j) exactly (the implicit-Euler contraction θ/(θ+Δτ))",
        max(abs(e[3] - ex) for e, ex in zip(s1.events, exact, strict=True)) < mpf("1e-35"),
    )
    ok(
        "PTC-S1: the stop is decided with margin ≥ 9.8 on both sides (φ₇ = 1.0157e-7, φ₈ = "
        "7.87e-10, tol 1e-8)",
        s1.margin > mpf("9.8"),
    )
    s2 = seed_runs["PTC-S2"][1][0][1]
    ok(
        "PTC-S2: one phase rejection at Δτ = 1, accepted at 1/2, CONVERGED at 8",
        s2.outcome == "CONVERGED"
        and s2.k == 8
        and s2.events[0][:4] == ("reject", 0, 1, "phase_update_required")
        and s2.events[1][2] == mpf("0.5"),
    )
    s3 = seed_runs["PTC-S3"][1][0][1]
    ok(
        "PTC-S3: PTC_STALLED at pseudo-step 0 after 11 invalid trials, Δτ from 1 to 2⁻¹⁰",
        s3.outcome == "PTC_STALLED"
        and s3.k == 0
        and len(s3.events) == 11
        and s3.events[-1][2] == mpf(2) ** -10,
    )
    s4 = seed_runs["PTC-S4"][1][0][1]
    ok(
        "PTC-S4: lands x on +0.0 at α_max = 1/2 at step 1, then BOUND_BLOCKED at step 2 after 11 "
        "trials",
        s4.outcome == "BOUND_BLOCKED"
        and s4.k == 2
        and s4.blocked == ("x",)
        and s4.events[1][4] == mpf("0.5")
        and s4.events[1][5]["x"] == 0
        and sum(1 for e in s4.events if e[0] == "reject") == 11,
    )
    res5, atts5 = seed_runs["PTC-S5"]
    ok(
        "PTC-S5: LIQUID → TWO_PHASE → VAPOR by patience, CONVERGED at x = 3 in the third attempt",
        res5 == "CONVERGED"
        and [g for g, _ in atts5] == ["LIQUID", "TWO_PHASE", "VAPOR"]
        and [r.outcome for _, r in atts5]
        == ["PHASE_UPDATE_REQUIRED", "PHASE_UPDATE_REQUIRED", "CONVERGED"]
        and [r.k for _, r in atts5] == [2, 2, 10],
    )

    # ---- §9.9: the ablations -- each registered rule changes a registered value -------------
    TAU_LOG["armed"] = False
    ablations: dict[str, Any] = {}

    def seed_ablate(name: str, pol: PTCPolicy) -> tuple[str, list[int]]:
        res, atts = run_seed(name, pol)
        return res, [r.k for _, r in atts]

    table = {
        "no_gamma_clip (PTC-S1)": ("PTC-S1", replace(PTC, clip=False)),
        "row_sign_plus_one (PTC-S1)": ("PTC-S1", replace(PTC, holdup_row_sign=1)),
        "stop_on_phi_floor (PTC-S1)": ("PTC-S1", replace(PTC, stop="norm_floor")),
        "tau_max_16 (PTC-S1, a policy override, not an ablation)": (
            "PTC-S1",
            replace(PTC, tau_max=mpf(16)),
        ),
        "proposed_tau_in_update (PTC-S2)": ("PTC-S2", replace(PTC, ratio_tau="proposed")),
        "rejected_residual_in_ratio (PTC-S2)": ("PTC-S2", replace(PTC, rejected_phi=True)),
        "no_reset_on_restart (PTC-S5)": ("PTC-S5", replace(PTC, reset=False)),
        "no_phi_floor (every seed)": ("PTC-S1", replace(PTC, use_floor=False)),
    }
    for label, (name, pol) in table.items():
        res, ks = seed_ablate(name, pol)
        ablations[label] = {"outcome": res, "pseudo_steps": ks}
    ok(
        "ablation: without the γ clip PTC-S1 converges at 6, not 8",
        ablations["no_gamma_clip (PTC-S1)"] == {"outcome": "CONVERGED", "pseudo_steps": [6]},
    )
    ok(
        "ablation: the wrong row sign makes PTC-S1 BOUND_BLOCKED at step 0 (first trial exactly "
        "singular at Δτ = θ)",
        ablations["row_sign_plus_one (PTC-S1)"]["outcome"] == "BOUND_BLOCKED"
        and run_seed("PTC-S1", replace(PTC, holdup_row_sign=1))[1][0][1].events[0][3]
        == "linear_solve_failed",
    )
    ok(
        "ablation: stopping on ‖F̂‖ ≤ φ_floor instead of K03's test takes 10 steps, not 8",
        ablations["stop_on_phi_floor (PTC-S1)"]["pseudo_steps"] == [10],
    )
    ok(
        "τ_max = 16 caps the growth: PTC-S1 converges at 9",
        ablations["tau_max_16 (PTC-S1, a policy override, not an ablation)"]["pseudo_steps"] == [9],
    )
    ok(
        "ablation: the proposed (rejected) Δτ in the update makes PTC-S2 converge at 7, not 8",
        ablations["proposed_tau_in_update (PTC-S2)"]["pseudo_steps"] == [7],
    )
    ok(
        "ablation: the rejected trial's residual in the ratio makes PTC-S2 converge at 7, not 8",
        ablations["rejected_residual_in_ratio (PTC-S2)"]["pseudo_steps"] == [7],
    )
    ok(
        "A20's rows without a seam are discharged by A19 (F16): the counts A19 registers — "
        "PTC-S1 8, PTC-S2 8 — differ from the ablated rules' 10, 7 and 7, so an implementation of "
        "any of the three rules fails A19",
        [a["pseudo_steps"] for a in seeds["PTC-S1"]["attempts"]] == [8]
        and [a["pseudo_steps"] for a in seeds["PTC-S2"]["attempts"]] == [8]
        and ablations["stop_on_phi_floor (PTC-S1)"]["pseudo_steps"] == [10]
        and ablations["proposed_tau_in_update (PTC-S2)"]["pseudo_steps"] == [7]
        and ablations["rejected_residual_in_ratio (PTC-S2)"]["pseudo_steps"] == [7],
    )
    ok(
        "ablation: without the reset PTC-S5 ends BUDGET_EXHAUSTED in its third attempt",
        ablations["no_reset_on_restart (PTC-S5)"]["outcome"] == "BUDGET_EXHAUSTED",
    )
    ok(
        "the φ_floor is inert: removing it changes nothing on PTC-S1",
        ablations["no_phi_floor (every seed)"] == {"outcome": "CONVERGED", "pseudo_steps": [8]},
    )

    # homotopy and edge-3 ablations
    xo1, rg1 = project(x05)
    xo4, rg4 = project(a02_open(360, q[340])[0])
    fs04 = a02_open(360, q[340])[1]
    hom_ablations = {
        "no_growth (HOM-01)": homotopy(xo1, rg1, fs05, replace(HOMOTOPY, grow=False)),
        "no_shrink (HOM-04)": homotopy(xo4, rg4, fs04, replace(HOMOTOPY, shrink=False)),
        "no_rollback (HOM-04)": homotopy(xo4, rg4, fs04, replace(HOMOTOPY, rollback=False)),
        "corrector_cap_50 (HOM-01)": homotopy(
            xo1, rg1, fs05, replace(HOMOTOPY, corrector_max_iterations=50)
        ),
        "corrector_cap_50 (HOM-04)": homotopy(
            xo4, rg4, fs04, replace(HOMOTOPY, corrector_max_iterations=50)
        ),
    }
    for label, hr in hom_ablations.items():
        ablations[label] = {
            "outcome": hr.outcome,
            "lambda_reached": frac(hr.lam),
            "lambda_trials": len(hr.steps) - 1,
            "end_S3_T_K": s(hr.x["S3.T"], 12),
        }
    ok(
        "ablation: without growth HOM-01 needs 4 λ-trials, not 3",
        ablations["no_growth (HOM-01)"]["lambda_trials"] == 4,
    )
    ok(
        "ablation: without shrinking HOM-04 stalls at λ = 3/4, not at the bubble point",
        ablations["no_shrink (HOM-04)"]["lambda_reached"] == "3/4",
    )
    ok(
        "ablation: without rollback HOM-04 reports a boundary state (S3.T within 1e-3 K of the "
        "bubble point), not the last root",
        abs(hom_ablations["no_rollback (HOM-04)"].x["S3.T"] - t03.T_BUBBLE) < mpf("1e-3")
        and abs(h4.x["S3.T"] - t03.T_BUBBLE) > mpf("5e-3"),
    )
    ok(
        "ablation: rollback is inert on HOM-04's λ path (18 trials, 909/1024 either way) — only "
        "the reported state depends on it, which A07 asserts",
        ablations["no_rollback (HOM-04)"]["lambda_trials"] == len(h4.homotopy.steps) - 1 == 18
        and ablations["no_rollback (HOM-04)"]["lambda_reached"] == frac(h4.homotopy.lam),
    )
    ok(
        "the corrector cap is inert on the registered paths (50 changes nothing)",
        ablations["corrector_cap_50 (HOM-01)"]["lambda_trials"] == 3
        and ablations["corrector_cap_50 (HOM-04)"]["lambda_reached"] == frac(h4.homotopy.lam),
    )
    budget_h = homotopy(xo4, rg4, fs04, replace(HOMOTOPY, max_lambda_trials=4))
    ok(
        "budget: HOM-04 with max_lambda_trials = 4 ends BUDGET_EXHAUSTED(homotopy_steps) "
        "at λ = 7/8",
        budget_h.outcome == "BUDGET_EXHAUSTED"
        and budget_h.budget == "homotopy_steps"
        and budget_h.lam == Fraction(7, 8),
    )
    xa_b = reconstruct(OFF_A, fs95)
    assert xa_b is not None
    budget_p = contract(xa_b, fs95, core="ptc", pol=replace(PTC, max_steps=5))
    ok(
        "budget: OFF-A (r = 0.95) under PTC with max_steps_per_attempt = 5 ends "
        "BUDGET_EXHAUSTED(ptc_steps) after 5 pseudo-steps",
        budget_p.outcome == "BUDGET_EXHAUSTED"
        and budget_p.attempts[-1].run.budget == "ptc_steps"
        and budget_p.attempts[-1].run.iterations == 5,
    )
    e_end = solve_with_edge3(x05, fs05, start="end")
    ablations["edge3_from_failed_end_state (HOM-01)"] = {
        "outcome": e_end.outcome,
        "lambda_reached": frac(e_end.homotopy.lam) if e_end.homotopy else None,
    }
    ok(
        "ablation: edge 3 started from the failed end state cannot leave λ = 0 (PHS-05 unrescued)",
        e_end.outcome == "HOMOTOPY_STALLED"
        and e_end.homotopy is not None
        and e_end.homotopy.lam == 0,
    )
    for dl0 in (Fraction(1), Fraction(1, 2), Fraction(1, 8)):
        hr = homotopy(xo1, rg1, fs05, replace(HOMOTOPY, delta_lambda_initial=dl0))
        ablations[f"delta_lambda_initial_{frac(dl0)} (HOM-01, sensitivity)"] = {
            "outcome": hr.outcome,
            "lambda_trials": len(hr.steps) - 1,
        }
        ok(
            f"sensitivity: HOM-01 also converges from Δλ₀ = {frac(dl0)} (the constant is not "
            "fitted)",
            hr.outcome == "CONVERGED",
        )

    ok(
        "the λ = 0 corrector converges at iteration 0 on every registered continuation case",
        all(
            sol.homotopy is not None and sol.homotopy.steps[0][3] == 0
            for sol in hom_solves.values()
        ),
    )
    cstr = cstr_preregistered()
    signs = [sum(1 for v in st["eigenvalues"] if v > 0) for st in cstr["states"]]
    ok(
        "§8.4 PTC-R1 (preregistered, not run): three steady states in 0 < x₂ < 8, the middle one "
        "a saddle (one positive eigenvalue), the outer two stable",
        len(cstr["states"]) == 3 and signs == [0, 1, 0],
    )

    # ---- §6.7: PHS-05 under PTC -- the algebraic subsystem is not restrained ----------------
    TAU_LOG["armed"] = True
    ptc05 = contract(x05, fs05, core="ptc")
    ok(
        "PHS-05 under PTC: the first pseudo-step lands S3.vap.C at Newton's α_max to 1e-15 (the "
        "opening's loop residual, 1e-21, is the only difference)",
        abs(ptc05.attempts[0].run.landings[0][1] - full_phs05.attempts[0].run.landings[0][1])
        < mpf("1e-15"),
    )
    # the structural theorem: the PTC direction's (T, split) part is Newton's at every Δτ
    fr5, rw5 = system(rg1, fs05)
    vals5, jac5 = jacobian(xo1, fr5, rw5, fs05)
    newton_dir = lu_solve(
        _scaled_jacobian(jac5, fr5, rw5), matrix([-vals5[r] / ROW_SCALE[r] for r in rw5])
    )
    _, js5, ms5, f5 = _ptc_matrix(xo1, fr5, rw5, fs05, PTC)
    algebraic_cols = [
        j
        for j, v in enumerate(fr5)
        if v not in ("U-HEAT.Q",) and not v.startswith(("S2.", "S4.", "S5.", "S6.", "S7.", "S3.n"))
    ]
    dev_struct = mpf(0)
    for tau in (mpf("1e-3"), mpf(1), mpf(1000)):
        pd = lu_solve(js5 + ms5 / tau, -f5)
        dev_struct = max(dev_struct, max(abs(pd[j] - newton_dir[j]) for j in algebraic_cols))
    ok(
        "§6.7: on PHS-05's opening state the PTC step's S3.T, split and U-FLASH.Q components "
        "equal Newton's at Δτ = 1e-3, 1, 1e3 (to 1e-15)",
        dev_struct < mpf("1e-15"),
    )
    ok(
        "PHS-05 under PTC ends PTC_STALLED after TWO_PHASE → LIQUID → VAPOR",
        ptc05.outcome == "PTC_STALLED"
        and [a.regimes["U-HEAT"] for a in ptc05.attempts] == ["TWO_PHASE", "LIQUID", "VAPOR"],
    )
    ok(
        "PHS-05 under PTC: 11 rejected trials in each of its three attempts",
        [sum(1 for t in a.run.trials if t.verdict != "accepted") for a in ptc05.attempts]
        == [11, 11, 11],
    )
    ptc05_edge = solve_with_edge3(x05, fs05, core="ptc")
    ok(
        "PHS-05 under PTC with edge 3: the continuation converges (Newton correctors)",
        ptc05_edge.outcome == "CONVERGED" and ptc05_edge.recovery == "taken",
    )

    # the A02 family scan under the default policy (contract + edge 3), both twins
    scan: list[dict[str, Any]] = []
    agree = 0
    band = {k: {"clear": 0, "near": 0, "fail": 0} for k in ("S3", "flash")}
    band_failures: list[tuple[Any, ...]] = []
    #: T04 A11 as amended (review S4): every run's contract attempts, and the family's margins
    family_runs: list[dict[str, Any]] = []
    family_margins = Margins()
    for tt in FAMILY_TARGETS:
        qt = t03.q_flash_at(mpf(tt))
        for g in FAMILY_GUESSES:
            block = t03.solve(mpf(g), qt)
            x0, fs = a02_open(g, qt)
            full = solve_with_edge3(x0, fs)
            same = block.outcome == full.contract_outcome and [
                (a.regime, a.run.outcome, a.run.iterations) for a in block.attempts
            ] == [(a.regimes["U-HEAT"], a.run.outcome, a.run.iterations) for a in full.attempts]
            agree += int(same)
            for a in full.attempts:
                family_margins.merge(a.run.margins)
            family_runs.append(
                {
                    "T_target_K": tt,
                    "guess_K": s(mpf(g), 6),
                    "contract": full.contract_outcome,
                    # [signature, core outcome, iterations, decision] per contract attempt
                    "attempts": [
                        [sigtext(signature(a.regimes)), a.run.outcome, a.run.iterations, a.decision]
                        for a in full.attempts
                    ],
                }
            )
            if full.outcome == "CONVERGED":
                fc = fresh_flash_checks(full.x, fs)
                ratio = band_ratio(fc)
                band["S3"]["fail" if ratio > 1 else "near" if ratio >= mpf("0.1") else "clear"] += 1
                fl = abs(fc["independent_split_flash_total"]) / FLOW_TOL
                band["flash"]["fail" if fl > 1 else "near" if fl >= mpf("0.1") else "clear"] += 1
                if ratio > 1:
                    band_failures.append((tt, s(mpf(g), 6), s(ratio, 4)))
            if full.contract_outcome != "CONVERGED":
                scan.append(
                    {
                        "T_target_K": tt,
                        "guess_K": s(mpf(g), 6),
                        "contract": full.contract_outcome,
                        "edge3": full.recovery,
                        "outcome": full.outcome,
                        "lambda_trials": (len(full.homotopy.steps) - 1) if full.homotopy else 0,
                    }
                )
    runs = len(FAMILY_TARGETS) * len(FAMILY_GUESSES)
    ok(
        f"family scan: the block twin (T03) and the full region agree on all {runs} runs",
        agree == runs,
    )
    ok(f"family scan: {runs} runs; the contract fails exactly 10", len(scan) == 10)
    ok(
        "family scan (A11, review S4): every contract decision on the 180 runs is far from its "
        "threshold — stop factor ≥ 1.06, Armijo ≥ 9e-4 relative, screen ≥ 6e-5, landing ≥ 2e-3, "
        "≥ 3.6 K inside the domain — decades above the 1e-9 relative duty difference a test's "
        "oracle duty may carry and the 53-bit floor",
        family_margins.convergence_factor > mpf("1.06")
        and family_margins.armijo_relative > mpf("9e-4")
        and family_margins.screen_relative > mpf("6e-5")
        and family_margins.landing_gap > mpf("2e-3")
        and family_margins.domain_k > mpf("3.6"),
        str({k: getattr(family_margins, k) for k in ("convergence_factor", "screen_relative")}),
    )
    ok(
        "family scan: edge 3 rescues 9; 352 K from 410 K ends HOMOTOPY_STALLED",
        sum(1 for e in scan if e["outcome"] == "CONVERGED") == 9
        and [(e["T_target_K"], e["guess_K"]) for e in scan if e["outcome"] != "CONVERGED"]
        == [(352, "410.000")],
    )

    # ---- §4.8: K04 on the bound declaration -----------------------------------------------
    # The registered certificate states: T04's converged recoveries and T02's A02 successes
    # (Newton from 358 K, T02 §7.6), each at its own final iterate.
    cert_states: dict[str, tuple[dict[str, Any], Flowsheet]] = {}
    for cid, sol in (("HOM-01", h1), ("HOM-02", h2), ("HOM-05", h5)):
        target = HOM_CASES[cid][1]
        cert_states[cid] = (sol.x, Flowsheet(r=mpf("0.5"), q_spec=t03.q_flash_at(mpf(target))))
    t02_runs: dict[str, Solve] = {}
    for tt in (360, 365, 355):
        x0, fs = a02_open(358, t03.q_flash_at(mpf(tt)))
        t02_runs[f"SYN-001-A02-{tt}"] = contract(x0, fs)
        cert_states[f"SYN-001-A02-{tt}"] = (t02_runs[f"SYN-001-A02-{tt}"].x, fs)
    ok(
        "T02's A02 successes from 358 K: CONVERGED in one TWO_PHASE attempt, 3 / 4 / 3 "
        "iterations (360 / 365 / 355 K)",
        [(r.outcome, len(r.attempts), r.attempts[0].run.iterations) for r in t02_runs.values()]
        == [("CONVERGED", 1, 3), ("CONVERGED", 1, 4), ("CONVERGED", 1, 3)],
    )
    fresh = {k: fresh_flash_checks(xs, fs) for k, (xs, fs) in cert_states.items()}
    registered_cert = ("HOM-01", "HOM-02", "HOM-05", "SYN-001-A02-360", "SYN-001-A02-365")
    for k in registered_cert:
        ok(
            f"{k}: every K04 §4.4/§4.7 S3 value and every row is outside ADR 0007 D2.4's band "
            "(< tau / 10), so its verdict is promised",
            band_ratio(fresh[k]) < mpf("0.1") and fresh[k]["worst_row_over_tolerance"] < mpf("0.1"),
            f"{s(band_ratio(fresh[k]), 4)}",
        )
        ok(
            f"{k}: the flash outlets' split (K04 §4.7's second clause, F10) is below "
            "tau_flow / 10 too",
            abs(fresh[k]["independent_split_flash_total"]) < FLOW_TOL / 10,
        )
    f355 = fresh["SYN-001-A02-355"]
    ok(
        "finding F9: T02's A02-355 from 358 K satisfies every row at <= 0.082 tau, yet its lifted "
        "S3 split differs from the fresh flash by more than tau_flow (1.09 tau_flow) and its "
        "fresh-flash heater balance is inside D2.4's band (0.937 tau)",
        f355["worst_row_over_tolerance"] < mpf("0.082")
        and f355["worst_row"] == "U-HEAT:HEAT-equilibrium:A"
        and mpf("1.09") < abs(f355["independent_split_S3_total"]) / FLOW_TOL < mpf("1.10")
        and mpf("0.93") < abs(f355["energy_heater_W"]) / ENERGY_TOL < mpf("0.94"),
    )
    amplification = lifted_block_amplification(cert_states["HOM-01"][0], cert_states["HOM-01"][1])
    ok(
        "finding F9: at the 355 K root the equilibrium rows' tolerance admits a lifted split "
        "error above tau_flow (first order, worst case)",
        amplification["worst_split_total_over_tau_flow"] > 1,
    )
    ok(
        "finding F9: the family scan has converged states whose S3 fresh-flash checks fail and "
        "states inside D2.4's band",
        band["S3"]["fail"] > 0 and band["S3"]["near"] > 0,
        str(band),
    )

    regularity: dict[str, Any] = {}
    for k in ("HOM-01", "HOM-05", "SYN-001-A02-365"):
        xs, fs = cert_states[k]
        reg = regularity47(xs, fs)
        nom = regularity47(xs, Flowsheet(r=fs.r, t_heater=xs["S3.T"]))
        ident = determinant_identity(xs, fs)
        regularity[k] = {
            "S3_T_K": s(xs["S3.T"], 15),
            "one_norm": s(reg["one_norm"], 15),
            "inverse_one_norm": s(reg["inverse_one_norm"], 15),
            "rcond_1": s(reg["rcond_1"], 15),
            "smallest_nonzero_scaled_entry": s(reg["smallest_nonzero_entry"], 12),
            "nominal_declaration_rcond_1_same_state": s(nom["rcond_1"], 12),
            "dH_S3_dT_W_per_K": s(ident["dH_S3_dT"], 15),
            "det_ratio_A02_over_nominal": s(ident["ratio"], 15),
            "identity_relative_error": s(abs(ident["ratio"] / ident["dH_S3_dT"] + 1), 3),
        }
        ok(
            f"{k}: the 47 x 47 bound target is regular with margin — rcond_1 >= 1e4 tau_ill and "
            "||J^-1||_1 <= the absolute limit / 1e3",
            reg["rcond_1"] > 10**4 * TAU_ILL and reg["inverse_one_norm"] < ABSOLUTE_LIMIT_47 / 1000,
        )
        ok(
            f"{k}: det J_A02 / det J_nominal = -dH_S3/dT to 1e-10 relative (§4.8's identity, "
            "exact on the solution curve and first order in the residual off it), and dH_S3/dT > 0",
            abs(ident["ratio"] + ident["dH_S3_dT"]) < mpf("1e-10") * abs(ident["dH_S3_dT"])
            and ident["dH_S3_dT"] > 0,
        )
        ok(
            f"{k}: the nominal declaration's target at the same state differs in rcond_1 by more "
            "than 1e-3 relative (A30's 1e-6 separates the two declarations)",
            abs(nom["rcond_1"] / reg["rcond_1"] - 1) > mpf("1e-3"),
        )
        ok(
            f"{k}: the smallest nonzero scaled entry is >= 1e3 x K04 §4.8's witness tolerance",
            reg["smallest_nonzero_entry"] > 1000 * mpf("1e-7"),
        )
    bound_doc = {
        "certificate_states": {
            k: {
                "worst_row": fresh[k]["worst_row"],
                "worst_row_over_tolerance": s(fresh[k]["worst_row_over_tolerance"], 4),
                "independent_split_S3_total_mol_per_s": s(
                    fresh[k]["independent_split_S3_total"], 5
                ),
                "energy_heater_W": s(fresh[k]["energy_heater_W"], 5),
                "independent_split_flash_total_mol_per_s": s(
                    fresh[k]["independent_split_flash_total"], 5
                ),
                "largest_value_over_threshold": s(band_ratio(fresh[k]), 4),
                "verdict_promised": k in registered_cert,
            }
            for k in cert_states
        },
        "target_regularity": regularity,
        "absolute_limit_inverse_one_norm": s(ABSOLUTE_LIMIT_47, 6),
        "finding_F9": {
            "state": "SYN-001-A02-355 from 358 K (T02 §7.6), Newton, 1 attempt, 3 iterations",
            "worst_row": f355["worst_row"],
            "worst_row_over_tolerance": s(f355["worst_row_over_tolerance"], 5),
            "independent_split_S3_total_mol_per_s": s(f355["independent_split_S3_total"], 6),
            "independent_split_S3_total_over_tau_flow": s(
                abs(f355["independent_split_S3_total"]) / FLOW_TOL, 5
            ),
            "energy_heater_W": s(f355["energy_heater_W"], 6),
            "energy_heater_over_tau_energy": s(abs(f355["energy_heater_W"]) / ENERGY_TOL, 5),
            "amplification_at_355K_root": {k: s(v, 4) for k, v in amplification.items()},
            "family_scan_converged_states": {
                "S3_as_implemented": band["S3"],
                "flash_outlets_as_specified_by_K04_4_7": band["flash"],
                "S3_failures": [
                    {"T_target_K": t, "guess_K": gk, "largest_over_threshold": rr}
                    for t, gk, rr in band_failures
                ],
            },
        },
    }

    # ---- §8: the basin comparison at r = 0.95, and the named PTC runs ----------------------
    basin: list[dict[str, Any]] = []
    root95 = x_root95
    margins_all = Margins()
    min_phi_ratio = None
    max_accum = mpf(0)
    for m in MAGNITUDES:
        for lat in LATTICE:
            t0 = tuple(m * mpf(v) / 4 for v in lat)
            margin = mixer_margin(t0, fs95)
            x0 = reconstruct(t0, fs95)
            entry: dict[str, Any] = {
                "magnitude_mol_per_s": s(m, 3),
                "direction_quarters": list(lat),
                "mixer_margin": s(margin, 6),
                "mixer_gap_K": s(mixer_gap_k(t0, fs95), 4),
            }
            if x0 is None:
                entry["start"] = "refused_by_the_mixer"
                basin.append(entry)
                continue
            for core in ("newton", "ptc"):
                sol = contract(x0, fs95, core=core)
                for a in sol.attempts:
                    margins_all.merge(a.run.margins)
                    if a.run.core == "ptc":
                        max_accum = max(max_accum, a.run.accumulation_identity)
                        if a.run.min_phi_at_ratio is not None:
                            min_phi_ratio = (
                                a.run.min_phi_at_ratio
                                if min_phi_ratio is None
                                else min(min_phi_ratio, a.run.min_phi_at_ratio)
                            )
                entry[core] = {
                    "outcome": sol.outcome,
                    "attempts": [
                        [sigtext(signature(a.regimes)), a.run.outcome, a.run.iterations]
                        for a in sol.attempts
                    ],
                    "same_root": sol.outcome == "CONVERGED"
                    and max(abs(sol.x[v] - root95[v]) / COL_SCALE[v] for v in COLUMNS)
                    < mpf("1e-6"),
                }
                if core == "ptc":
                    entry[core]["polish"] = sol.attempts[-1].run.polish
            basin.append(entry)
    admitted = [e for e in basin if "newton" in e]
    refused_dirs = sorted(
        {"".join(map(str, e["direction_quarters"])) for e in basin if "newton" not in e}
    )
    ok(
        "basin set (F14, K03 §10.1's rule as the mixer enforces it): 45 lattice starts, 18 "
        "admitted, "
        "the 27 refused are the directions 112, 121, 130, 202, 211, 220, 301, 310, 400 at every "
        "magnitude (the rule is intensive), each with K03 margin ≤ −0.115 and a gap ≥ 1e3 × the "
        "mixer's 1e-6 K; every admitted gap is 0 (subcooled or exactly saturated)",
        len(basin) == 45
        and len(admitted) == 18
        and refused_dirs == ["112", "121", "130", "202", "211", "220", "301", "310", "400"]
        and all(mpf(e["mixer_margin"]) <= mpf("-0.115") for e in basin if "newton" not in e)
        and all(mpf(e["mixer_gap_K"]) >= mpf("1e-3") for e in basin if "newton" not in e)
        and all(mpf(e["mixer_gap_K"]) == 0 for e in admitted),
    )
    ok(
        "basin comparison: damped Newton converges to the P01 root from all 18",
        all(e["newton"]["outcome"] == "CONVERGED" and e["newton"]["same_root"] for e in admitted),
    )
    ok(
        "basin comparison: PTC converges to the P01 root from all 18 (it improves no basin)",
        all(e["ptc"]["outcome"] == "CONVERGED" and e["ptc"]["same_root"] for e in admitted),
    )
    ok(
        "basin comparison: every PTC run's polish is accepted",
        all(e["ptc"]["polish"] == "accepted" for e in admitted),
    )
    n_steps = [sum(a[2] for a in e["newton"]["attempts"]) for e in admitted]
    p_steps = [sum(a[2] for a in e["ptc"]["attempts"]) for e in admitted]
    ok(
        "basin comparison: PTC costs between 1.87 and 8.81 times Newton's iterations on every "
        "start (Newton 5–10, PTC 15–55 per start)",
        all(
            mpf(p) / n > mpf("1.87") and mpf(p) / n < mpf("8.81")
            for p, n in zip(p_steps, n_steps, strict=True)
        )
        and (min(n_steps), max(n_steps), min(p_steps), max(p_steps)) == (5, 10, 15, 55),
    )
    ok(
        "§6.5: the accumulation identity holds on every accepted PTC step of the basin set to "
        "1e-30",
        max_accum < mpf("1e-30"),
    )
    ok(
        "§7.4: the φ floor never binds: the smallest φ at which a ratio was formed exceeds 1e-12 "
        "by 1e3",
        min_phi_ratio is not None and min_phi_ratio > mpf("1e-9"),
    )

    named: dict[str, Any] = {}
    for label, r, t0 in (
        (
            "r=0.95/initializer",
            mpf("0.95"),
            tuple((1 - mpf("0.95")) * v for v in tear_root(mpf("0.95"))),
        ),
        ("r=0.95/OFF-A", mpf("0.95"), OFF_A),
        ("r=0.95/OFF-B", mpf("0.95"), OFF_B),
        (
            "r=0.5/initializer",
            mpf("0.5"),
            tuple((1 - mpf("0.5")) * v for v in tear_root(mpf("0.5"))),
        ),
    ):
        fsn = Flowsheet(r=r)
        x0 = reconstruct(t0, fsn)
        assert x0 is not None
        rootn = reconstruct(tear_root(r), fsn)
        assert rootn is not None
        named[label] = {}
        for core in ("newton", "ptc"):
            sol = contract(x0, fsn, core=core)
            for a in sol.attempts:
                margins_all.merge(a.run.margins)
            named[label][core] = {
                "outcome": sol.outcome,
                "attempts": attempts_record(sol),
                "final_error_vs_P01_by_kind": state_error(sol.x, rootn),
            }
            if core == "ptc":
                nopol = contract(x0, fsn, core="ptc", pol=replace(PTC, polish=False))
                env = abs(FRESH[0] - nopol.x["S4.n.A"] - nopol.x["S7.n.A"])
                env = max(
                    env,
                    *(
                        abs(FRESH[i] - nopol.x[f"S4.n.{c}"] - nopol.x[f"S7.n.{c}"])
                        for i, c in enumerate(C)
                    ),
                )
                named[label]["ptc"]["unpolished_envelope_over_tolerance"] = s(
                    env / TOLERANCE["molar_flow"], 4
                )
    ok(
        "named: r = 0.95 initializer -- Newton 5, PTC 39 (one attempt each, heater LIQUID)",
        [a["iterations"] for a in named["r=0.95/initializer"]["newton"]["attempts"]] == [5]
        and [a["iterations"] for a in named["r=0.95/initializer"]["ptc"]["attempts"]] == [39],
    )
    ok(
        "named: OFF-B at r = 0.95 -- Newton [2, 1, 3], PTC [4, 26]",
        [a["iterations"] for a in named["r=0.95/OFF-B"]["newton"]["attempts"]] == [2, 1, 3]
        and [a["iterations"] for a in named["r=0.95/OFF-B"]["ptc"]["attempts"]] == [4, 26],
    )
    ok(
        "§7.5: without the polish OFF-B's PTC stop has a material envelope 1.31 × τ (K04 would "
        "say FAILED)",
        mpf(named["r=0.95/OFF-B"]["ptc"]["unpolished_envelope_over_tolerance"]) > mpf("1.3"),
    )
    ok(
        "§7.5: with the polish every named PTC final state is within 1e-12 scaled of P01's root",
        all(
            mpf(v) < mpf("1e-10")
            for lab in named
            for k, v in named[lab]["ptc"]["final_error_vs_P01_by_kind"].items()
            if k != "heat_rate"
        )
        and all(
            mpf(named[lab]["ptc"]["final_error_vs_P01_by_kind"]["heat_rate"]) < mpf("1e-4")
            for lab in named
        ),
    )

    TAU_LOG["armed"] = False
    for a in ptc05.attempts:
        margins_all.merge(a.run.margins)
    ok(
        "§7.7: τ_max is never reached on a registered path (largest SER proposal below 1e4 s)",
        TAU_LOG["proposed_max"] is not None and TAU_LOG["proposed_max"] < mpf(10) ** 4,
    )
    ok(
        "§7.7: τ_min is reached on registered paths only by ending a retry sequence or clipping "
        "a proposal, never inside a decision margin (every retry decision ≥ 1e-3 from it)",
        margins_all.tau_min_relative is not None and margins_all.tau_min_relative > mpf("1e-3"),
    )
    tau_limits = {
        "smallest_pseudo_step_tried_s": s(TAU_LOG["tried_min"], 4),
        "largest_ser_proposal_s": s(TAU_LOG["proposed_max"], 4),
        "retry_sequences_ended_by_tau_min": TAU_LOG["tau_min_stops"],
        "ser_proposals_clipped_at_tau_min": TAU_LOG["tau_min_clips"],
    }

    # ---- §9.10: margins of every decision on every registered path --------------------------
    for sol in hom_solves.values():
        assert sol.homotopy is not None
        margins_all.merge(sol.homotopy.margins)
        for a in sol.attempts:
            margins_all.merge(a.run.margins)
    margins_doc = {
        "convergence_factor_min": s(margins_all.convergence_factor, 4),
        "armijo_relative_min": s(margins_all.armijo_relative, 4),
        "screen_relative_min": s(margins_all.screen_relative, 4),
        "landing_gap_min": s(margins_all.landing_gap, 4),
        "domain_K_min": s(margins_all.domain_k, 4),
        "tau_min_retry_decision_relative_min": s(margins_all.tau_min_relative, 4),
        "phi_min_at_a_formed_ratio": s(min_phi_ratio, 4),
        "accumulation_identity_max": s(max_accum, 3),
    }
    mdetail = str(margins_doc)
    ok(
        "margins: every stop decided by a factor ≥ 1 + 1e-8 on both sides",
        margins_all.convergence_factor > 1 + mpf("1e-8"),
        mdetail,
    )
    ok(
        "margins: every Armijo decision ≥ 1e-8 relative from its bound",
        margins_all.armijo_relative > mpf("1e-8"),
        mdetail,
    )
    ok(
        "margins: every screen value ≥ 1e-8 from 1 + ε",
        margins_all.screen_relative > mpf("1e-8"),
        mdetail,
    )
    ok(
        "margins: every landing decided by ≥ 1e-8 (ratio gap, or the distance of α_max from 1)",
        margins_all.landing_gap > mpf("1e-8"),
        mdetail,
    )
    ok(
        "margins: every evaluated trial ≥ 1e-6 K inside the provider's temperature domain",
        margins_all.domain_k > mpf("1e-6"),
        mdetail,
    )

    # ---- measured: the same algorithms in 53-bit arithmetic ---------------------------------
    measured: dict[str, Any] = {}
    if low_precision:
        # the same inputs, formed at 40 digits (P01's reference asserts 40-digit closure); every
        # operation of the rerun then rounds to 53 bits
        openings = {
            cid: a02_open(guess, t03.q_flash_at(mpf(target)))
            for cid, (_, target, guess, _, _) in HOM_CASES.items()
        }
        starts95 = {
            label: reconstruct(t0, Flowsheet(r=mpf("0.95")))
            for label, t0 in (("r=0.95/OFF-A", OFF_A), ("r=0.95/OFF-B", OFF_B))
        }
        roots40 = {r: reconstruct(tear_root(r), Flowsheet(r=r)) for r in (mpf("0.5"), mpf("0.95"))}
        closed_modes = {r: modes_closed_form(r, PTC.residence_time)["s"] for r in roots40}
        saved = mp.prec
        try:
            mp.prec = 53
            low = {}
            floors53: dict[str, Any] = {}
            a15_rows: list[tuple[Any, ...]] = []
            a17_rows: list[tuple[Any, ...]] = []
            for cid, (_, _, _, max_att, max_it) in HOM_CASES.items():
                x0l, fsl = openings[cid]
                sl = solve_with_edge3(x0l, fsl, max_attempts=max_att, newton_max_it=max_it)
                ref = hom_solves[cid]
                assert sl.homotopy is not None and ref.homotopy is not None
                low[cid] = {
                    "same_lambda_path_and_counts": [
                        (st[0], st[2], st[3]) for st in sl.homotopy.steps
                    ]
                    == [(st[0], st[2], st[3]) for st in ref.homotopy.steps],
                    "end_T_difference_K": s(abs(sl.x["S3.T"] - ref.x["S3.T"]), 3),
                }
            for label in ("r=0.95/OFF-A", "r=0.95/OFF-B"):
                fsl = Flowsheet(r=mpf("0.95"))
                x0l = starts95[label]
                assert x0l is not None
                for core in ("newton", "ptc"):
                    sl = contract(x0l, fsl, core=core)
                    low[f"{label}/{core}"] = {
                        "attempt_iterations": [a.run.iterations for a in sl.attempts]
                    }
                    if core == "ptc":
                        floors53[f"A21 {label}"] = {
                            "relative_old_rule": s(
                                max(a.run.accumulation_identity for a in sl.attempts), 3
                            ),
                            "absolute_over_1_plus_theta_over_dtau_mol_per_s": s(
                                max(a.run.accumulation_floor for a in sl.attempts), 3
                            ),
                        }
            # A15: the PTC step at the root rounded to 53 bits; A17: the modes in 53 bits
            for r, x40 in roots40.items():
                assert x40 is not None
                fsr = Flowsheet(r=r)
                xr, regr = project({k: mpf(v) for k, v in x40.items()})
                freer, rowsr = system(regr, fsr)
                _, jsr, msr, fsr_sig = _ptc_matrix(xr, freer, rowsr, fsr, PTC)
                res53 = max(abs(fsr_sig[i]) for i in range(len(rowsr)))
                steps53 = {}
                for tau in (mpf("1e-4"), mpf("1e-3"), mpf(1), mpf("1e10")):
                    stp = lu_solve(jsr + msr / tau, -fsr_sig)
                    j = max(range(len(freer)), key=lambda j: abs(stp[j]))
                    steps53[s(tau, 2)] = (abs(stp[j]), freer[j], tau)
                nu = eig(inverse(jsr) * msr, left=False, right=False)
                finite = sorted(
                    (-1 / e for e in sorted(nu, key=lambda e: -abs(e))[:6]),
                    key=lambda z: (z.real, z.imag),
                )
                floors53[f"A15/A17 r={s(r, 2)}"] = {
                    "root_residual_scaled": s(res53, 3),
                    "steps": {k: [s(v[0], 3), v[1]] for k, v in steps53.items()},
                    "modes": [[s(z.real, 16), s(z.imag, 3)] for z in finite],
                }
                a15_rows.append((r, res53, steps53))
                a17_rows.append((r, finite))
            phi_floor: dict[str, dict[str, str]] = {}
            for name in SEEDS:
                res, atts = run_seed(name)
                low[name] = {"outcome": res, "pseudo_steps": [r.k for _, r in atts]}
                # A19's φ floor (F13): each accepted φ's 53-bit departure from the 40-digit φ
                hi_phi = [e[3] for _, r in seed_runs[name][1] for e in r.events if e[0] == "accept"]
                lo_phi = [e[3] for _, r in atts for e in r.events if e[0] == "accept"]
                assert len(hi_phi) == len(lo_phi)
                gaps = [abs(a - b) for a, b in zip(hi_phi, lo_phi, strict=True)]
                phi_floor[name] = {
                    "max_abs": s(max(gaps, default=mpf(0)), 3),
                    "max_rel": s(
                        max(
                            (gp / abs(a) for gp, a in zip(gaps, hi_phi, strict=True) if a),
                            default=0,
                        ),
                        3,
                    ),
                    "smallest_phi": s(min((abs(a) for a in hi_phi if a), default=mpf(0)), 3),
                }
            measured["low_precision_53_bit"] = low
            measured["seed_phi_53_bit"] = phi_floor
            measured["floors_53_bit"] = floors53
        finally:
            mp.prec = saved
        for cid in HOM_CASES:
            ok(
                f"{cid}: 53-bit arithmetic reproduces the λ path and every corrector count",
                bool(measured["low_precision_53_bit"][cid]["same_lambda_path_and_counts"]),
            )
            ok(
                f"{cid}: 53-bit end temperature within 1e-9 K",
                mpf(measured["low_precision_53_bit"][cid]["end_T_difference_K"]) < mpf("1e-9"),
            )
        for label in ("r=0.95/OFF-A", "r=0.95/OFF-B"):
            for core in ("newton", "ptc"):
                ok(
                    f"{label}/{core}: 53-bit arithmetic reproduces the attempt iteration counts",
                    measured["low_precision_53_bit"][f"{label}/{core}"]["attempt_iterations"]
                    == [a["iterations"] for a in named[label][core]["attempts"]],
                )
        theta = PTC.residence_time
        for r, res53, steps53 in a15_rows:
            ok(
                f"A15's floor (F14), r = {s(r, 2)}: at the root rounded to 53 bits every PTC step "
                "is ≤ half of 1e-12 + 10 (θ/Δτ) ‖F̂_σ‖∞, and the Δτ = 1e-4 step's largest "
                "component is U-FLASH.Q (the index-2 duty)",
                all(
                    v[0] <= (mpf("1e-12") + 10 * (theta / v[2]) * res53) / 2
                    for v in steps53.values()
                )
                and steps53["0.00010"][1] == "U-FLASH.Q",
                str({k: (s(v[0], 3), v[1]) for k, v in steps53.items()}),
            )
        ok(
            "A15's floor (F14): the Δτ = 1e-4 step exceeds A15's first tolerance 1e-12 at some r "
            "(why the θ/Δτ term is needed)",
            any(steps53["0.00010"][0] > mpf("1e-12") for _, _, steps53 in a15_rows),
        )
        for r, finite in a17_rows:
            cf = closed_modes[r]
            pair = [z for z in finite if abs(z.real + 1 / theta) < mpf("1e-4")]
            simple = [z for z in finite if abs(z.real + 1 / theta) >= mpf("1e-4")]
            ok(
                f"A17's rule (F14), r = {s(r, 2)}: in 53 bits the four simple modes are real and "
                "equal the closed form to 1e-10 relative; the Jordan pair at −1/θ splits by less "
                "than 1e-6/5 relative and its mean equals −1/θ to 1e-10 relative",
                len(pair) == 2
                and len(simple) == 4
                and all(
                    abs(z.imag) < mpf("1e-10") * abs(z)
                    and min(abs(z.real - c) / abs(c) for c in cf) < mpf("1e-10")
                    for z in simple
                )
                and all(abs(z + 1 / theta) < mpf("2e-7") / theta for z in pair)
                and abs((pair[0] + pair[1]) / 2 + 1 / theta) < mpf("1e-10") / theta,
                str([(s(z.real, 16), s(z.imag, 3)) for z in finite]),
            )
        a21 = [v for k, v in measured["floors_53_bit"].items() if k.startswith("A21")]
        ok(
            "A21's floor (F14): on the 53-bit named PTC runs the identity's defect is ≤ 1e-13/10 "
            "(1 + θ/Δτ) mol/s, while the old relative rule (1e-9 × max(|F|, tol)) is exceeded",
            all(
                mpf(v["absolute_over_1_plus_theta_over_dtau_mol_per_s"]) <= mpf("1e-14")
                for v in a21
            )
            and any(mpf(v["relative_old_rule"]) > mpf("1e-9") for v in a21),
            str(a21),
        )
        ok(
            "A19's φ floor (F13): every seed's 53-bit φ departs from the 40-digit φ by at most "
            "1e-15 / 5 absolute, and by more than 1e-12 relative on some seed (why A19 needs "
            "the floor)",
            all(mpf(v["max_abs"]) <= mpf("2e-16") for v in measured["seed_phi_53_bit"].values())
            and any(mpf(v["max_rel"]) > mpf("1e-12") for v in measured["seed_phi_53_bit"].values()),
            str(measured["seed_phi_53_bit"]),
        )
        for name in SEEDS:
            ok(
                f"{name}: 53-bit arithmetic reproduces the outcome and the pseudo-step counts",
                measured["low_precision_53_bit"][name]
                == {
                    "outcome": seeds[name]["outcome"],
                    "pseudo_steps": [a["pseudo_steps"] for a in seeds[name]["attempts"]],
                },
            )

    return {
        "constants": {
            "homotopy": {
                "type": "specification_continuation",
                "delta_lambda_initial": frac(Fraction(HOMOTOPY.delta_lambda_initial)),
                "delta_lambda_min": frac(Fraction(HOMOTOPY.delta_lambda_min)),
                "growth": HOMOTOPY.growth,
                "shrink": "1/2",
                "corrector_max_iterations": HOMOTOPY.corrector_max_iterations,
                "max_lambda_trials": HOMOTOPY.max_lambda_trials,
            },
            "ptc": {
                "mass_policy": "T04-residence-time-v1",
                "residence_time_s": s(PTC.residence_time, 3),
                "tau_initial_s": s(PTC.tau_initial, 3),
                "tau_min_s": s(PTC.tau_min, 3),
                "tau_max_s": s(PTC.tau_max, 3),
                "gamma_min": s(PTC.gamma_min, 3),
                "gamma_max": s(PTC.gamma_max, 3),
                "phi_floor": s(PTC.phi_floor, 3),
                "retry_shrink": s(PTC.retry_shrink, 3),
                "retries_max": PTC.retries_max,
                "max_steps_per_attempt": PTC.max_steps,
                "holdup_row_sign": PTC.holdup_row_sign,
            },
            "edge3_triggers": sorted(EDGE3_TRIGGERS),
        },
        "closed_form": {
            "a02": hom_closed,
            "ptc_r1_cstr_preregistered": {
                "Da": s(cstr["Da"], 3),
                "B": s(cstr["B"], 3),
                "beta": s(cstr["beta"], 3),
                "Le": "1",
                "steady_states": [
                    {
                        "x1": s(st["x1"], 12),
                        "x2": s(st["x2"], 12),
                        "eigenvalues": [s(v, 8) for v in st["eigenvalues"]],
                    }
                    for st in cstr["states"]
                ],
            },
            "loop_modes": modes,
        },
        "bound_declaration_certificate": bound_doc,
        "policy_simulation": {
            "homotopy_cases": hom_cases,
            "a02_family_scan": {
                "targets_K": list(FAMILY_TARGETS),
                "guesses_K": [s(mpf(g), 6) for g in FAMILY_GUESSES],
                "runs": runs,
                "contract_failures": scan,
                "contract_attempts": family_runs,
                "margins": {
                    "convergence_factor_min": s(family_margins.convergence_factor, 4),
                    "armijo_relative_min": s(family_margins.armijo_relative, 4),
                    "screen_relative_min": s(family_margins.screen_relative, 4),
                    "landing_gap_min": s(family_margins.landing_gap, 4),
                    "domain_K_min": s(family_margins.domain_k, 4),
                },
            },
            "ptc_seeds": seeds,
            "ptc_phs05": {
                "outcome": ptc05.outcome,
                "attempts": attempts_record(ptc05),
                "with_edge3": ptc05_edge.outcome,
            },
            "ptc_named": named,
            "basin_comparison_r095": basin,
            "ablations": ablations,
            "margins": margins_doc,
            "pseudo_step_limits": tau_limits,
        },
        "measured": measured,
        "checks_passed": checks,
    }


def emit(path: Path, document: dict[str, Any]) -> str:
    header = {
        "generated_by": "docs/derivations/scripts/t04_reference.py (design lane, T04): closed "
        "forms of SYN-001 through syn001_reference.py and t03_reference.py; the SYN-001 EO region, "
        "K03's Newton core, T03's contract and the T04 homotopy, PTC core, mass mapping and edge 3 "
        "simulated at 40 digits from their statements in T04-globalization-spec.md",
        "specification": "docs/derivations/T04-globalization-spec.md",
        "independence": "no solver, graph-layer, oracle or process_runtime code was used. "
        "`closed_form` values are expectations; `policy_simulation` values are definition-level "
        "references (the same policies, derived a second time); `measured` is labelled and never "
        "an expectation.",
    }
    text = yaml.safe_dump({**header, **document}, sort_keys=False, allow_unicode=True, width=110)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="re-derive every identity and print the checks"
    )
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not args.check and not args.emit:
        parser.error("choose --check and/or --emit PATH")
    document = build()
    if args.check:
        for name in document["checks_passed"]:
            print(f"ok  {name}")
        print(f"{len(document['checks_passed'])} checks passed")
    if args.emit:
        digest = emit(Path(args.emit), document)
        print(f"wrote {args.emit}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
