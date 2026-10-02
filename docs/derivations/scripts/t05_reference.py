"""Closed-form reference generator for T05, the v0.1 unit-model families.

Everything here follows from definitions: the SYN-001 thermodynamics of
``docs/derivations/SYN-001.md`` (restated below in a backend-generic form and cross-checked against
the sibling closed-form script ``syn001_reference.py``), and the equations, causal evaluators and
coupled flowsheets of ``docs/derivations/T05-unit-models-spec.md``. It imports nothing from
``process_runtime`` or ``benchmarks``: the numbers it emits are the expectations the T05 tests
judge the implementation against, so they must not come from it.

Three classes of value are emitted and labelled as such in the YAML:

* ``closed_form`` -- expectations: the unit-level cases, the coupled cases, the residual rows and
  their Jacobians at registered trial states, the injected false successes. Computed with mpmath
  at 40 significant digits and written to 20.
* ``generator_claims`` -- every statement the specification makes about its own numbers,
  re-derived by ``--check``. The script refuses to emit when one fails.
* ``measured`` -- the same rows and kernels rerun in 53-bit arithmetic, used only to argue the
  tolerances (their floors). Never an expectation.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/t05_reference.py --check
    python docs/derivations/scripts/t05_reference.py --emit benchmarks/t05/reference_values.yaml

``--emit`` is byte-reproducible.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import math
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from mpmath import lu_solve, matrix, mp, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import syn001_reference as p01  # noqa: E402  (closed-form SYN-001 thermodynamics, mpmath)

mp.dps = 40

# ============================================================================================
# 1. Registered constants
# ============================================================================================

COMPONENTS = ("A", "B", "C")
NC = 3
T_MIN, T_MAX = mpf(280), mpf(440)
P_MIN, P_MAX = mpf(50000), mpf(200000)
P_R = mpf(100000)
MOLAR_MASS = (mpf("0.100"),) * 3

#: ADR 0001 D6 (K04 §5.2 for the lifted equilibrium row), `a + r s`, by quantity kind.
TOL: dict[str, Any] = {
    "molar_flow": mpf("1e-9") + mpf("1e-8") * 3,
    "molar_flow_squared": mpf("1e-9") * 3 + mpf("1e-8") * 9,
    "heat_rate": mpf("1e-5") + mpf("1e-8") * mpf(10) ** 5,
    "temperature": mpf("1e-6"),
    "pressure": mpf("1e-2"),
}
#: K03 §4.2's registered nominals, by kind (scales, never iterates).
SCALE: dict[str, Any] = {
    "molar_flow": mpf(3),
    "molar_flow_squared": mpf(9),
    "heat_rate": mpf(10) ** 5,
    "temperature": mpf(100),
    "pressure": mpf(10) ** 5,
}
#: T05 §9.2: row values at trial states, relative to the row's term scale; Jacobian entries.
ROW_REL = mpf("1e-12")
JAC_REL = mpf("1e-11")
#: A mutation is "detected" when it moves some row by this many row tolerances (T05 §9.3).
DETECTION_FACTOR = mpf(1000)
#: R-007: an enthalpy gap converted to the temperature error it would cause.
ADMISSIBILITY_K = mpf("1e-6")
#: K04 §4.8's central-difference step, as a fraction of the column scale.
FD_STEP = mpf("1e-5")
#: Registered margin of a classified state from its phase boundary (T05 §8.1), dimensionless.
PHASE_MARGIN = mpf("1e-3")
#: Reaction-consistent reference conventions (ADR 0011 D2).
REACTION_CONSISTENT = ("SYN-001-ref-v1",)

Vec = tuple[Any, ...]


# ============================================================================================
# 2. Numeric backends and a forward-mode dual number (exact Jacobians in either backend)
# ============================================================================================


class Backend:
    """The SYN-001 constants in one arithmetic: mpmath at 40 digits, or IEEE doubles."""

    def __init__(self, name: str, num: Callable[[str], Any], exp: Any, log: Any) -> None:
        self.name = name
        self.num = num
        self.exp = exp
        self.log = log
        self.R = num("8.31446261815324")
        self.T_REF = num("300")
        self.P_REF = num("100000")
        self.CP = num("100")
        self.T_BOIL = (num("320"), num("360"), num("400"))
        self.L_VAP = (num("25000"), num("30000"), num("35000"))
        self.V_LIQ = (num("0.0001"), num("0.0001"), num("0.0001"))


MP = Backend("mp40", mpf, mp.exp, mp.log)
FL = Backend("float53", float, math.exp, math.log)


class Dual:
    """A value and its partials by variable id. Enough algebra for every T05 row."""

    __slots__ = ("v", "d")

    def __init__(self, v: Any, d: dict[str, Any] | None = None) -> None:
        self.v = v
        self.d = {} if d is None else d

    def __add__(self, o: Any) -> Dual:
        if isinstance(o, Dual):
            d = dict(self.d)
            for k, x in o.d.items():
                d[k] = d[k] + x if k in d else x
            return Dual(self.v + o.v, d)
        return Dual(self.v + o, dict(self.d))

    __radd__ = __add__

    def __neg__(self) -> Dual:
        return Dual(-self.v, {k: -x for k, x in self.d.items()})

    def __sub__(self, o: Any) -> Dual:
        return self + (-o)

    def __rsub__(self, o: Any) -> Dual:
        return (-self) + o

    def __mul__(self, o: Any) -> Dual:
        if isinstance(o, Dual):
            d = {k: x * o.v for k, x in self.d.items()}
            for k, x in o.d.items():
                d[k] = d[k] + self.v * x if k in d else self.v * x
            return Dual(self.v * o.v, d)
        return Dual(self.v * o, {k: x * o for k, x in self.d.items()})

    __rmul__ = __mul__

    def inverse(self) -> Dual:
        iv = 1 / self.v
        return Dual(iv, {k: -x * iv * iv for k, x in self.d.items()})

    def __truediv__(self, o: Any) -> Dual:
        if isinstance(o, Dual):
            return self * o.inverse()
        return Dual(self.v / o, {k: x / o for k, x in self.d.items()})

    def __rtruediv__(self, o: Any) -> Dual:
        return self.inverse() * o


def b_exp(b: Backend, x: Any) -> Any:
    if isinstance(x, Dual):
        e = b.exp(x.v)
        return Dual(e, {k: e * g for k, g in x.d.items()})
    return b.exp(x)


def b_log(b: Backend, x: Any) -> Any:
    if isinstance(x, Dual):
        return Dual(b.log(x.v), {k: g / x.v for k, g in x.d.items()})
    return b.log(x)


def val(x: Any) -> Any:
    return x.v if isinstance(x, Dual) else x


IDENTITY = (0, 1, 2)


class Thermo:
    """SYN-001's `h` and `ln K` (derivation §2-§3). The maps exist only for mutation analysis:
    `h_vap_map[i] = j` evaluates component i's vapour enthalpy with component j's data."""

    def __init__(
        self,
        b: Backend,
        *,
        h_liq_map: Sequence[int] = IDENTITY,
        h_vap_map: Sequence[int] = IDENTITY,
        lnk_map: Sequence[int] = IDENTITY,
    ) -> None:
        self.b = b
        self.h_liq_map = tuple(h_liq_map)
        self.h_vap_map = tuple(h_vap_map)
        self.lnk_map = tuple(lnk_map)

    def h(self, phase: str, i: int, t: Any, p: Any) -> Any:
        b = self.b
        if phase == "L":
            j = self.h_liq_map[i]
            return b.CP * (t - b.T_REF) + b.V_LIQ[j] * (p - b.P_REF)
        j = self.h_vap_map[i]
        return b.CP * (t - b.T_REF) + b.L_VAP[j]

    def lnk(self, i: int, t: Any, p: Any) -> Any:
        b = self.b
        j = self.lnk_map[i]
        return (
            b_log(b, b.P_REF / p)
            + (b.L_VAP[j] / b.R) * (1 / b.T_BOIL[j] - 1 / t)
            + b.V_LIQ[j] * (p - b.P_REF) / (b.R * t)
        )

    def k(self, i: int, t: Any, p: Any) -> Any:
        return b_exp(self.b, self.lnk(i, t, p))


TH = Thermo(MP)
THF = Thermo(FL)


# ============================================================================================
# 3. Identifiers (T05 spec §3.2; the same helpers the K02 models use)
# ============================================================================================


def fid(s: str, c: str) -> str:
    return f"{s}.n.{c}"


def tid(s: str) -> str:
    return f"{s}.T"


def pid(s: str) -> str:
    return f"{s}.P"


def vid(s: str, c: str) -> str:
    return f"{s}.vap.{c}"


def lid(s: str, c: str) -> str:
    return f"{s}.liq.{c}"


def vtot(s: str) -> str:
    return f"{s}.V"


def ltot(s: str) -> str:
    return f"{s}.L"


def ntot(s: str) -> str:
    return f"{s}.N"


def qid(u: str) -> str:
    return f"{u}.Q"


def wid(u: str) -> str:
    return f"{u}.W"


def xid(u: str) -> str:
    return f"{u}.xi"


def rid(u: str, eq: str, *suffix: str) -> str:
    return ":".join((u, eq, *suffix))


def stream_ids(s: str, *, lifted: bool = False) -> tuple[str, ...]:
    ids = (*(fid(s, c) for c in COMPONENTS), tid(s), pid(s))
    if lifted:
        ids = (
            *ids,
            *(vid(s, c) for c in COMPONENTS),
            *(lid(s, c) for c in COMPONENTS),
            vtot(s),
            ltot(s),
        )
    return ids


# ============================================================================================
# 4. The residual rows of the six models (T05 spec §4-§9), as lists of additive terms
# ============================================================================================

Rows = dict[str, tuple[str, list[Any]]]


def enthalpy_terms(
    th: Thermo, x: Mapping[str, Any], s: str, phase: str, sign: int, flows: Sequence[str]
) -> list[Any]:
    t, p = x[tid(s)], x[pid(s)]
    return [sign * (x[flows[i]] * th.h(phase, i, t, p)) for i in range(NC)]


def stream_enthalpy_terms(
    th: Thermo, x: Mapping[str, Any], s: str, regime: str, sign: int
) -> list[Any]:
    """`regime` is the declared phase `L`/`V`, or `lifted` (the producer's split of `s`)."""
    if regime == "lifted":
        return [
            *enthalpy_terms(th, x, s, "V", sign, [vid(s, c) for c in COMPONENTS]),
            *enthalpy_terms(th, x, s, "L", sign, [lid(s, c) for c in COMPONENTS]),
        ]
    return enthalpy_terms(th, x, s, regime, sign, [fid(s, c) for c in COMPONENTS])


def lifted_rows(th: Thermo, x: Mapping[str, Any], u: str, eq_id: str, s: str) -> Rows:
    """K02's `lift_two_phase_stream`: equilibrium, split, Vdef, Ldef (R-008)."""
    rows: Rows = {}
    t, p = x[tid(s)], x[pid(s)]
    for i, c in enumerate(COMPONENTS):
        rows[rid(u, eq_id, c)] = (
            "molar_flow_squared",
            [x[vid(s, c)] * x[ltot(s)], -(th.k(i, t, p) * x[lid(s, c)] * x[vtot(s)])],
        )
        rows[rid(u, "split", c)] = ("molar_flow", [x[vid(s, c)], x[lid(s, c)], -x[fid(s, c)]])
    rows[rid(u, "Vdef")] = ("molar_flow", [x[vtot(s)], *(-x[vid(s, c)] for c in COMPONENTS)])
    rows[rid(u, "Ldef")] = ("molar_flow", [x[ltot(s)], *(-x[lid(s, c)] for c in COMPONENTS)])
    return rows


def rows_ph_flash(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
    u, si, sv, sl = cfg["unit"], cfg["inlet"], cfg["vapor"], cfg["liquid"]
    rows: Rows = {}
    for c in COMPONENTS:
        rows[rid(u, "PHF-mole", c)] = (
            "molar_flow",
            [x[fid(si, c)], -x[fid(sv, c)], -x[fid(sl, c)]],
        )
    tv, pv = x[tid(sv)], x[pid(sv)]
    for i, c in enumerate(COMPONENTS):
        rows[rid(u, "PHF-equilibrium", c)] = (
            "molar_flow_squared",
            [
                x[fid(sv, c)] * x[ntot(sl)],
                -(th.k(i, tv, pv) * x[fid(sl, c)] * x[ntot(sv)]),
            ],
        )
    rows[rid(u, "PHF-T")] = ("temperature", [x[tid(sv)], -x[tid(sl)]])
    for port, s in (("vapor", sv), ("liquid", sl)):
        rows[rid(u, "PHF-pressure", port)] = (
            "pressure",
            [x[pid(s)], -x[pid(si)], p["pressure_drop"]],
        )
    rows[rid(u, "PHF-duty")] = (
        "heat_rate",
        [
            x[qid(u)],
            *stream_enthalpy_terms(th, x, si, cfg["inlet_regime"], 1),
            *stream_enthalpy_terms(th, x, sv, "V", -1),
            *stream_enthalpy_terms(th, x, sl, "L", -1),
        ],
    )
    rows[rid(u, "PHF-Q")] = ("heat_rate", [x[qid(u)], -p["duty"]])
    rows[rid(u, "Ndef", "vapor")] = (
        "molar_flow",
        [x[ntot(sv)], *(-x[fid(sv, c)] for c in COMPONENTS)],
    )
    rows[rid(u, "Ndef", "liquid")] = (
        "molar_flow",
        [x[ntot(sl)], *(-x[fid(sl, c)] for c in COMPONENTS)],
    )
    return rows


def rows_valve(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
    u, si, so = cfg["unit"], cfg["inlet"], cfg["outlet"]
    rows: Rows = {}
    for c in COMPONENTS:
        rows[rid(u, "VLV-mole", c)] = ("molar_flow", [x[fid(si, c)], -x[fid(so, c)]])
    rows[rid(u, "VLV-P")] = ("pressure", [x[pid(so)], -p["outlet_pressure"]])
    rows[rid(u, "VLV-energy")] = (
        "heat_rate",
        [
            *stream_enthalpy_terms(th, x, si, cfg["inlet_regime"], 1),
            *stream_enthalpy_terms(th, x, so, "lifted", -1),
        ],
    )
    rows.update(lifted_rows(th, x, u, "VLV-equilibrium", so))
    return rows


def rows_pump(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
    u, si, so = cfg["unit"], cfg["inlet"], cfg["outlet"]
    rows: Rows = {}
    for c in COMPONENTS:
        rows[rid(u, "PUMP-mole", c)] = ("molar_flow", [x[fid(si, c)], -x[fid(so, c)]])
    rows[rid(u, "PUMP-P")] = ("pressure", [x[pid(so)], -p["outlet_pressure"]])
    t_in, p_in, p_out = x[tid(si)], x[pid(si)], x[pid(so)]
    isothermal = [-(x[fid(si, c)] * th.h("L", i, t_in, p_out)) for i, c in enumerate(COMPONENTS)]
    base = [x[fid(si, c)] * th.h("L", i, t_in, p_in) for i, c in enumerate(COMPONENTS)]
    rows[rid(u, "PUMP-work")] = (
        "heat_rate",
        [p["efficiency"] * x[wid(u)], *isothermal, *base],
    )
    rows[rid(u, "PUMP-energy")] = (
        "heat_rate",
        [
            x[wid(u)],
            *stream_enthalpy_terms(th, x, si, "L", 1),
            *stream_enthalpy_terms(th, x, so, "L", -1),
        ],
    )
    return rows


def rows_reactor(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
    u, si, so = cfg["unit"], cfg["inlet"], cfg["outlet"]
    nu, key, conv = p["nu"], cfg["key"], p["conversion"]
    rows: Rows = {}
    for i, c in enumerate(COMPONENTS):
        rows[rid(u, "RX-mole", c)] = (
            "molar_flow",
            [x[fid(si, c)], nu[i] * x[xid(u)], -x[fid(so, c)]],
        )
    rows[rid(u, "RX-conversion")] = (
        "molar_flow",
        [x[xid(u)], -(conv * x[fid(si, COMPONENTS[key])] / (-nu[key]))],
    )
    rows[rid(u, "RX-pressure")] = ("pressure", [x[pid(so)], -x[pid(si)], p["pressure_drop"]])
    rows.update(lifted_rows(th, x, u, "RX-equilibrium", so))
    rows[rid(u, "RX-duty")] = (
        "heat_rate",
        [
            x[qid(u)],
            *stream_enthalpy_terms(th, x, si, cfg["inlet_regime"], 1),
            *stream_enthalpy_terms(th, x, so, "lifted", -1),
        ],
    )
    if cfg["mode"] == "outlet_temperature":
        rows[rid(u, "RX-spec")] = ("temperature", [x[tid(so)], -p["outlet_temperature"]])
    else:
        rows[rid(u, "RX-spec")] = ("heat_rate", [x[qid(u)], -p["duty"]])
    return rows


def rows_separator(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
    u, si, st, sb = cfg["unit"], cfg["inlet"], cfg["top"], cfg["bottom"]
    rows: Rows = {}
    for c in COMPONENTS:
        rows[rid(u, "SEP-mole", c)] = (
            "molar_flow",
            [x[fid(si, c)], -x[fid(st, c)], -x[fid(sb, c)]],
        )
    for i, c in enumerate(COMPONENTS):
        rows[rid(u, "SEP-split", c)] = (
            "molar_flow",
            [x[fid(st, c)], -(p["split"][i] * x[fid(si, c)])],
        )
    for port, s in (("top", st), ("bottom", sb)):
        rows[rid(u, "SEP-T", port)] = ("temperature", [x[tid(s)], -x[tid(si)]])
    for port, s in (("top", st), ("bottom", sb)):
        rows[rid(u, "SEP-P", port)] = ("pressure", [x[pid(s)], -x[pid(si)]])
    rows[rid(u, "SEP-duty")] = (
        "heat_rate",
        [
            x[qid(u)],
            *stream_enthalpy_terms(th, x, si, cfg["inlet_regime"], 1),
            *stream_enthalpy_terms(th, x, st, cfg["top_phase"], -1),
            *stream_enthalpy_terms(th, x, sb, cfg["bottom_phase"], -1),
        ],
    )
    return rows


def rows_exchanger(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
    u = cfg["unit"]
    hi, ho, ci, co = cfg["hot_inlet"], cfg["hot_outlet"], cfg["cold_inlet"], cfg["cold_outlet"]
    rows: Rows = {}
    for c in COMPONENTS:
        rows[rid(u, "HX-mole-hot", c)] = ("molar_flow", [x[fid(hi, c)], -x[fid(ho, c)]])
    for c in COMPONENTS:
        rows[rid(u, "HX-mole-cold", c)] = ("molar_flow", [x[fid(ci, c)], -x[fid(co, c)]])
    rows[rid(u, "HX-pressure", "hot")] = ("pressure", [x[pid(ho)], -x[pid(hi)]])
    rows[rid(u, "HX-pressure", "cold")] = ("pressure", [x[pid(co)], -x[pid(ci)]])
    rows[rid(u, "HX-energy-hot")] = (
        "heat_rate",
        [
            -x[qid(u)],
            *stream_enthalpy_terms(th, x, hi, cfg["hot_phase"], 1),
            *stream_enthalpy_terms(th, x, ho, cfg["hot_phase"], -1),
        ],
    )
    rows[rid(u, "HX-energy-cold")] = (
        "heat_rate",
        [
            x[qid(u)],
            *stream_enthalpy_terms(th, x, ci, cfg["cold_phase"], 1),
            *stream_enthalpy_terms(th, x, co, cfg["cold_phase"], -1),
        ],
    )
    mode = cfg["specification"]
    if mode == "cold_outlet_temperature":
        rows[rid(u, "HX-spec")] = ("temperature", [x[tid(co)], -p["value"]])
    elif mode == "hot_outlet_temperature":
        rows[rid(u, "HX-spec")] = ("temperature", [x[tid(ho)], -p["value"]])
    else:
        rows[rid(u, "HX-spec")] = ("heat_rate", [x[qid(u)], -p["value"]])
    return rows


BUILDERS: dict[str, Callable[..., Rows]] = {
    "syn001.ph_flash": rows_ph_flash,
    "syn001.valve": rows_valve,
    "syn001.liquid_pump": rows_pump,
    "syn001.conversion_reactor": rows_reactor,
    "syn001.component_separator": rows_separator,
    "syn001.heat_exchanger": rows_exchanger,
}


def evaluate_rows(
    model: str,
    b: Backend,
    x_values: Mapping[str, Any],
    cfg: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    jacobian: bool = False,
    thermo: Thermo | None = None,
    builder: Callable[..., Rows] | None = None,
) -> dict[str, dict[str, Any]]:
    th = thermo or Thermo(b)
    if jacobian:
        x: dict[str, Any] = {k: Dual(v, {k: b.num("1")}) for k, v in x_values.items()}
    else:
        x = dict(x_values)
    rows = (builder or BUILDERS[model])(th, x, cfg, params)
    out: dict[str, dict[str, Any]] = {}
    for row, (kind, terms) in rows.items():
        total: Any = b.num("0")
        for term in terms:
            total = total + term
        entry: dict[str, Any] = {
            "kind": kind,
            "value": val(total),
            "terms": [val(t) for t in terms],
            "scale": sum((abs(val(t)) for t in terms), b.num("0")),
        }
        if jacobian:
            entry["jac"] = dict(total.d) if isinstance(total, Dual) else {}
            # sum over terms of |d term / d column|: the scale of a partial that cancels to 0
            partial_scale: dict[str, Any] = {}
            for term in terms:
                if isinstance(term, Dual):
                    for col, g in term.d.items():
                        partial_scale[col] = partial_scale.get(col, b.num("0")) + abs(g)
            entry["partial_scale"] = partial_scale
        out[row] = entry
    return out


# ============================================================================================
# 5. The 40-digit kernels: TP split, enthalpy flows, R-007 admissibility, the PH solve
# ============================================================================================


def zeros() -> Vec:
    return (mpf(0),) * NC


def is_dormant(n: Sequence[Any]) -> bool:
    return all(v == 0 for v in n)


def h_flow(n: Sequence[Any], t: Any, p: Any, phase: str, th: Thermo = TH) -> Any:
    return sum((n[i] * th.h(phase, i, t, p) for i in range(NC)), mpf(0))


def in_domain(t: Any, p: Any) -> bool:
    return bool(T_MIN <= t <= T_MAX and P_MIN <= p <= P_MAX)


def bisect(fn: Callable[[Any], Any], lo: Any, hi: Any, iterations: int = 150) -> Any:
    """Root of an increasing function on [lo, hi] with fn(lo) <= 0 <= fn(hi)."""
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if fn(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def tp_split(n: Sequence[Any], t: Any, p: Any) -> dict[str, Any]:
    """The provider's TP flash (derivation §5.1 order), at 40 digits."""
    total = sum(n, mpf(0))
    if total == 0:
        return {"regime": "ZERO_FLOW", "beta": None, "v": zeros(), "l": zeros()}
    k = [TH.k(i, t, p) for i in range(NC)]
    z = [n[i] / total for i in range(NC)]
    szk = sum((z[i] * k[i] for i in range(NC)), mpf(0))
    szik = sum((z[i] / k[i] for i in range(NC)), mpf(0))
    base = {"szk": szk, "szik": szik, "K": tuple(k)}
    if szk <= 1:
        return {"regime": "LIQUID", "beta": mpf(0), "v": zeros(), "l": tuple(n), **base}
    if szik <= 1:
        return {"regime": "VAPOR", "beta": mpf(1), "v": tuple(n), "l": zeros(), **base}
    present = [i for i in range(NC) if z[i] > 0]
    kmax, kmin = max(k[i] for i in present), min(k[i] for i in present)
    lo = max(mpf(0), 1 / (1 - kmax))
    hi = min(mpf(1), 1 / (1 - kmin))

    def rr(beta: Any) -> Any:
        return sum((z[i] * (k[i] - 1) / (1 + beta * (k[i] - 1)) for i in present), mpf(0))

    beta = bisect(lambda b_: -rr(b_), lo, hi, 170)
    x = [z[i] / (1 + beta * (k[i] - 1)) for i in range(NC)]
    v = tuple(beta * total * k[i] * x[i] for i in range(NC))
    return {
        "regime": "TWO_PHASE",
        "beta": beta,
        "v": v,
        "l": tuple(n[i] - v[i] for i in range(NC)),
        **base,
    }


def h_split(split: Mapping[str, Any], t: Any, p: Any) -> Any:
    return h_flow(split["v"], t, p, "V") + h_flow(split["l"], t, p, "L")


def h_tp(n: Sequence[Any], t: Any, p: Any) -> Any:
    return h_split(tp_split(n, t, p), t, p)


def admissibility(n: Sequence[Any], t: Any, p: Any, phase: str) -> dict[str, Any]:
    """R-007: |H_true - H_single| / (dH_single/dT), against 1e-6 K."""
    if is_dormant(n):
        return {"admissible": True, "equivalent_K": mpf(0)}
    gap = abs(h_tp(n, t, p) - h_flow(n, t, p, phase))
    slope = sum(n, mpf(0)) * TH.b.CP
    equivalent = gap / slope
    return {"admissible": bool(equivalent <= ADMISSIBILITY_K), "equivalent_K": equivalent}


def ph_solve(n: Sequence[Any], p: Any, target: Any) -> dict[str, Any]:
    """T05 §4.4's kernel at 40 digits: the root of H_TP(n, T, P) = target on the domain."""
    flowing = [i for i in range(NC) if n[i] > 0]
    lo, hi = T_MIN, T_MAX
    if len(flowing) == 1:
        k = flowing[0]
        f_lo, f_hi = TH.lnk(k, lo, p), TH.lnk(k, hi, p)
        if f_lo < 0 < f_hi:
            tsat = bisect(lambda t: TH.lnk(k, t, p), lo, hi)
            hl, hv = h_flow(n, tsat, p, "L"), h_flow(n, tsat, p, "V")
            if hl <= target <= hv:
                beta = (target - hl) / (hv - hl)
                v = tuple(beta * n[i] if i == k else mpf(0) for i in range(NC))
                regime = "TWO_PHASE"
                if beta == 0:
                    regime = "LIQUID"
                elif beta == 1:
                    regime = "VAPOR"
                split = {
                    "regime": regime,
                    "beta": beta,
                    "v": v,
                    "l": tuple(n[i] - v[i] for i in range(NC)),
                }
                return {"status": "ok", "T": tsat, "split": split, "route": "saturation"}
            if target < hl:
                hi = tsat
            else:
                lo = tsat

    def f(t: Any) -> Any:
        return h_tp(n, t, p) - target

    if f(T_MIN) > 0:
        return {"status": "out_of_domain", "code": "ph_outside_domain(below)"}
    if f(T_MAX) < 0:
        return {"status": "out_of_domain", "code": "ph_outside_domain(above)"}
    t = bisect(f, lo, hi)
    return {"status": "ok", "T": t, "split": tp_split(n, t, p), "route": "bracket"}


def bubble_dew(n: Sequence[Any], p: Any) -> tuple[Any, Any]:
    """Bubble and dew temperatures of a flowing feed at P (bisection on the domain)."""
    total = sum(n, mpf(0))
    z = [v / total for v in n]

    def bub(t: Any) -> Any:
        return sum((z[i] * TH.k(i, t, p) for i in range(NC)), mpf(0)) - 1

    def dew(t: Any) -> Any:
        return 1 - sum((z[i] / TH.k(i, t, p) for i in range(NC) if z[i] > 0), mpf(0))

    return bisect(bub, mpf(200), mpf(700)), bisect(dew, mpf(200), mpf(700))


# ============================================================================================
# 6. The causal evaluators of the six models (T05 spec §4-§9), plus the K02 units C1-C3 use
# ============================================================================================


def stream(n: Sequence[Any], t: Any, p: Any) -> dict[str, Any]:
    return {"n": tuple(mpf(v) for v in n), "T": mpf(t), "P": mpf(p)}


def fail(status: str, code: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "code": code, **extra}


def inlet_enthalpy(inlet: Mapping[str, Any], regime: str | None, port: str = "inlet") -> dict:
    """A declared phase is admitted by R-007 and written single-phase; `None` means the
    producer lifted the stream, so its enthalpy is the TP state's."""
    n, t, p = inlet["n"], inlet["T"], inlet["P"]
    if is_dormant(n):
        return {"status": "ok", "H": mpf(0)}
    if not in_domain(t, p):
        return fail("out_of_domain", f"state_outside_domain({port})")
    if regime is None:
        return {"status": "ok", "H": h_tp(n, t, p)}
    adm = admissibility(n, t, p, regime)
    if not adm["admissible"]:
        name = "LIQUID" if regime == "L" else "VAPOR"
        return fail("unsupported", f"inadmissible_phase({port}, {name})", admissibility=adm)
    return {"status": "ok", "H": h_flow(n, t, p, regime), "admissibility": adm}


def outlet_from_split(n: Sequence[Any], t: Any, p: Any, split: Mapping[str, Any]) -> dict:
    return {
        "n": tuple(n),
        "T": t,
        "P": p,
        "regime": split["regime"],
        "v": tuple(split["v"]),
        "l": tuple(split["l"]),
        "beta": split["beta"],
    }


def eval_ph_flash(
    inlet: Mapping[str, Any], regime: str | None, duty: Any, pressure_drop: Any
) -> dict[str, Any]:
    n, t_in, p_in = inlet["n"], inlet["T"], inlet["P"]
    p_out = p_in - pressure_drop
    if is_dormant(n):
        if duty != 0:
            return fail("error", "duty_into_dormant_stream")
        dormant = {"n": zeros(), "T": t_in, "P": p_out}
        return {
            "status": "ok",
            "code": "",
            "signature": "ZERO_FLOW",
            "vapor": dormant,
            "liquid": dormant,
            "duty": mpf(0),
        }
    if not (P_MIN <= p_out <= P_MAX):
        return fail("out_of_domain", "pressure_outside_domain(outlet)")
    h_in = inlet_enthalpy(inlet, regime)
    if h_in["status"] != "ok":
        return h_in
    ph = ph_solve(n, p_out, h_in["H"] + duty)
    if ph["status"] != "ok":
        return fail(ph["status"], ph["code"])
    split, t = ph["split"], ph["T"]
    return {
        "status": "ok",
        "code": "",
        "signature": split["regime"],
        "T": t,
        "P": p_out,
        "beta": split["beta"],
        "vapor": {"n": split["v"], "T": t, "P": p_out},
        "liquid": {"n": split["l"], "T": t, "P": p_out},
        "duty": duty,
        "H_in": h_in["H"],
        "route": ph["route"],
    }


def eval_valve(inlet: Mapping[str, Any], regime: str | None, p_out: Any) -> dict[str, Any]:
    n, t_in, p_in = inlet["n"], inlet["T"], inlet["P"]
    if is_dormant(n):
        return {
            "status": "ok",
            "code": "",
            "signature": "ZERO_FLOW",
            "outlet": {"n": zeros(), "T": t_in, "P": p_out, "v": zeros(), "l": zeros()},
        }
    if p_out > p_in:
        return fail("out_of_domain", "pressure_rise(valve)")
    h_in = inlet_enthalpy(inlet, regime)
    if h_in["status"] != "ok":
        return h_in
    ph = ph_solve(n, p_out, h_in["H"])
    if ph["status"] != "ok":
        return fail(ph["status"], ph["code"])
    return {
        "status": "ok",
        "code": "",
        "signature": ph["split"]["regime"],
        "outlet": outlet_from_split(n, ph["T"], p_out, ph["split"]),
        "H_in": h_in["H"],
    }


def eval_pump(inlet: Mapping[str, Any], p_out: Any, efficiency: Any) -> dict[str, Any]:
    n, t_in, p_in = inlet["n"], inlet["T"], inlet["P"]
    if is_dormant(n):
        return {
            "status": "ok",
            "code": "",
            "signature": "ZERO_FLOW",
            "outlet": {"n": zeros(), "T": t_in, "P": p_out},
            "work": mpf(0),
        }
    if p_out < p_in:
        return fail("out_of_domain", "pressure_fall(pump)")
    h_in = inlet_enthalpy(inlet, "L")
    if h_in["status"] != "ok":
        return h_in
    w_ideal = h_flow(n, t_in, p_out, "L") - h_flow(n, t_in, p_in, "L")
    work = w_ideal / efficiency
    target = h_in["H"] + work
    total = sum(n, mpf(0))
    t_out = TH.b.T_REF + (
        target - sum((n[i] * TH.b.V_LIQ[i] for i in range(NC)), mpf(0)) * (p_out - P_R)
    ) / (total * TH.b.CP)
    adm = admissibility(n, t_out, p_out, "L")
    if not adm["admissible"]:
        return fail("unsupported", "inadmissible_phase(outlet, LIQUID)")
    return {
        "status": "ok",
        "code": "",
        "signature": "LIQUID",
        "outlet": {"n": tuple(n), "T": t_out, "P": p_out},
        "work": work,
        "work_ideal": w_ideal,
        "inlet_admissibility": h_in["admissibility"]["equivalent_K"],
    }


def eval_reactor(
    inlet: Mapping[str, Any],
    regime: str | None,
    nu: Sequence[Any],
    key: int,
    conversion: Any,
    mode: str,
    value: Any,
    pressure_drop: Any = None,
) -> dict[str, Any]:
    n, t_in, p_in = inlet["n"], inlet["T"], inlet["P"]
    p_out = p_in - (mpf(0) if pressure_drop is None else pressure_drop)
    if is_dormant(n):
        if mode == "duty" and value != 0:
            return fail("error", "duty_into_dormant_stream")
        t_label = value if mode == "outlet_temperature" else t_in
        return {
            "status": "ok",
            "code": "",
            "signature": "ZERO_FLOW",
            "extent": mpf(0),
            "duty": mpf(0),
            "outlet": {"n": zeros(), "T": t_label, "P": p_out, "v": zeros(), "l": zeros()},
        }
    extent = conversion * n[key] / (-nu[key])
    n_out = tuple(n[i] + nu[i] * extent for i in range(NC))
    for i in range(NC):
        if n_out[i] < 0:
            return fail("out_of_domain", f"reactant_exhausted({COMPONENTS[i]})", extent=extent)
    if not (P_MIN <= p_out <= P_MAX):
        return fail("out_of_domain", "pressure_outside_domain(outlet)")
    h_in = inlet_enthalpy(inlet, regime)
    if h_in["status"] != "ok":
        return h_in
    if mode == "outlet_temperature":
        split = tp_split(n_out, value, p_out)
        t_out = value
        duty = h_split(split, t_out, p_out) - h_in["H"]
    else:
        ph = ph_solve(n_out, p_out, h_in["H"] + value)
        if ph["status"] != "ok":
            return fail(ph["status"], ph["code"])
        split, t_out, duty = ph["split"], ph["T"], value
    return {
        "status": "ok",
        "code": "",
        "signature": split["regime"],
        "extent": extent,
        "duty": duty,
        "outlet": outlet_from_split(n_out, t_out, p_out, split),
        "H_in": h_in["H"],
    }


def eval_separator(
    inlet: Mapping[str, Any],
    regime: str | None,
    split: Sequence[Any],
    top_phase: str,
    bottom_phase: str,
) -> dict[str, Any]:
    n, t, p = inlet["n"], inlet["T"], inlet["P"]
    if is_dormant(n):
        dormant = {"n": zeros(), "T": t, "P": p}
        return {
            "status": "ok",
            "code": "",
            "signature": "ZERO_FLOW",
            "top": dormant,
            "bottom": dormant,
            "duty": mpf(0),
        }
    h_in = inlet_enthalpy(inlet, regime)
    if h_in["status"] != "ok":
        return h_in
    top = tuple(split[i] * n[i] for i in range(NC))
    bottom = tuple(n[i] - top[i] for i in range(NC))
    failures = []
    for port, flows, phase in (("top", top, top_phase), ("bottom", bottom, bottom_phase)):
        adm = admissibility(flows, t, p, phase)
        if not adm["admissible"]:
            name = "LIQUID" if phase == "L" else "VAPOR"
            failures.append(f"inadmissible_phase({port}, {name})")
    if failures:
        return fail("unsupported", failures[0], failures=failures)
    duty = h_flow(top, t, p, top_phase) + h_flow(bottom, t, p, bottom_phase) - h_in["H"]
    return {
        "status": "ok",
        "code": "",
        "signature": None,
        "top": {"n": top, "T": t, "P": p},
        "bottom": {"n": bottom, "T": t, "P": p},
        "duty": duty,
    }


def invert_single_phase(n: Sequence[Any], p: Any, target: Any, phase: str) -> Any:
    """T with sum_i n_i h_i^phase(T, P) = target; affine in T for SYN-001."""
    total = sum(n, mpf(0))
    offset = sum(
        (n[i] * (TH.b.V_LIQ[i] * (p - P_R) if phase == "L" else TH.b.L_VAP[i]) for i in range(NC)),
        mpf(0),
    )
    return TH.b.T_REF + (target - offset) / (total * TH.b.CP)


def eval_exchanger(
    hot: Mapping[str, Any],
    cold: Mapping[str, Any],
    hot_phase: str,
    cold_phase: str,
    mode: str,
    value: Any,
) -> dict[str, Any]:
    names = {"L": "LIQUID", "V": "VAPOR"}
    hot_dormant, cold_dormant = is_dormant(hot["n"]), is_dormant(cold["n"])
    if hot_dormant or cold_dormant:
        satisfiable = (
            (mode == "duty" and value == 0)
            or (mode == "cold_outlet_temperature" and (cold_dormant or value == cold["T"]))
            or (mode == "hot_outlet_temperature" and (hot_dormant or value == hot["T"]))
        )
        if not satisfiable:
            return fail("error", "specification_unsatisfiable_with_dormant_side")
        t_ho = value if (mode == "hot_outlet_temperature") else hot["T"]
        t_co = value if (mode == "cold_outlet_temperature") else cold["T"]
        return {
            "status": "ok",
            "code": "",
            "signature": "ZERO_FLOW" if (hot_dormant and cold_dormant) else None,
            "duty": mpf(0),
            "hot_outlet": {"n": hot["n"], "T": t_ho, "P": hot["P"]},
            "cold_outlet": {"n": cold["n"], "T": t_co, "P": cold["P"]},
        }
    diagnostics: list[tuple[str, bool]] = []
    h_hi = inlet_enthalpy(hot, hot_phase, "hot_inlet")
    h_ci = inlet_enthalpy(cold, cold_phase, "cold_inlet")
    for h in (h_hi, h_ci):
        if h["status"] != "ok":
            return h
    if mode == "duty":
        duty = value
    elif mode == "cold_outlet_temperature":
        duty = h_flow(cold["n"], value, cold["P"], cold_phase) - h_ci["H"]
    else:
        duty = h_hi["H"] - h_flow(hot["n"], value, hot["P"], hot_phase)
    t_ho = invert_single_phase(hot["n"], hot["P"], h_hi["H"] - duty, hot_phase)
    t_co = invert_single_phase(cold["n"], cold["P"], h_ci["H"] + duty, cold_phase)
    if mode == "hot_outlet_temperature":
        t_ho = value
    if mode == "cold_outlet_temperature":
        t_co = value
    domain_ok = bool(T_MIN <= t_ho <= T_MAX and T_MIN <= t_co <= T_MAX)
    diagnostics.append(("outlet_outside_domain", domain_ok))
    adm_hot = admissibility(hot["n"], t_ho, hot["P"], hot_phase) if domain_ok else None
    adm_cold = admissibility(cold["n"], t_co, cold["P"], cold_phase) if domain_ok else None
    diagnostics.append(
        (
            f"inadmissible_phase(hot_outlet, {names[hot_phase]})",
            bool(adm_hot and adm_hot["admissible"]),
        )
    )
    diagnostics.append(
        (
            f"inadmissible_phase(cold_outlet, {names[cold_phase]})",
            bool(adm_cold and adm_cold["admissible"]),
        )
    )
    diagnostics.append(("heat_flow_reversed", bool(duty >= 0)))
    diagnostics.append(("temperature_cross(hot_end)", bool(hot["T"] - t_co > 0)))
    diagnostics.append(("temperature_cross(cold_end)", bool(t_ho - cold["T"] > 0)))
    failures = [code for code, passed in diagnostics if not passed]
    result = {
        "duty": duty,
        "hot_outlet": {"n": hot["n"], "T": t_ho, "P": hot["P"]},
        "cold_outlet": {"n": cold["n"], "T": t_co, "P": cold["P"]},
        "hot_end_K": hot["T"] - t_co,
        "cold_end_K": t_ho - cold["T"],
        "failures": failures,
    }
    if failures:
        status = "unsupported" if failures[0].startswith("inadmissible") else "out_of_domain"
        return {**result, "status": status, "code": failures[0]}
    return {**result, "status": "ok", "code": "", "signature": None}


def eval_heater(inlet: Mapping[str, Any], t_out: Any) -> dict[str, Any]:
    """K02 `syn001.tp_heater` (SYN-001 §4), used inside C1 and in the RX-7 identity."""
    h_in = inlet_enthalpy(inlet, "L")
    split = tp_split(inlet["n"], t_out, inlet["P"])
    return {
        "duty": h_split(split, t_out, inlet["P"]) - h_in["H"],
        "outlet": outlet_from_split(inlet["n"], t_out, inlet["P"], split),
    }


def eval_mixer(inlets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """K02 `syn001.adiabatic_mixer`: liquid closure, equal pressures (SYN-001 §4.1)."""
    p = inlets[0]["P"]
    n = tuple(sum((s["n"][i] for s in inlets), mpf(0)) for i in range(NC))
    target = sum((h_flow(s["n"], s["T"], s["P"], "L") for s in inlets), mpf(0))
    return {"outlet": {"n": n, "T": invert_single_phase(n, p, target, "L"), "P": p}}


# ============================================================================================
# 7. Unit-level registered cases (T05 spec §4-§9: "the case tables")
# ============================================================================================

NU = (mpf(-2), mpf(-1), mpf(3))
Z_EQ = (1, 1, 1)
Z_RX = (mpf("1.2"), mpf("0.9"), mpf("0.3"))
Z_ZC = (1, 0, 2)
Z_PURE_B = (0, 2, 0)
Z_DORMANT = (0, 0, 0)
HOT_BIG = (mpf("0.8"), mpf("1.6"), mpf("2.6"))
HOT_SMALL = (mpf("0.4"), mpf("0.8"), mpf("1.3"))


def as_double(value: Any) -> Any:
    """The exact binary value of the double an implementation would hold for `value`."""
    return mpf(float(value))


def saturated_liquid_360() -> tuple[Any, ...]:
    """SYN-001's single-flash liquid of the equimolar feed at 360 K, P_r (as doubles)."""
    split = tp_split((mpf(1), mpf(1), mpf(1)), mpf(360), P_R)
    return tuple(as_double(v) for v in split["l"])


def q_tp_360() -> Any:
    """PHF-2's duty: H_TP(F, 360 K) - H^L(F, 300 K), to 17 significant digits (a double)."""
    exact = h_tp((mpf(1), mpf(1), mpf(1)), mpf(360), P_R)
    return mpf(mp.nstr(exact, 17))


def unit_cases() -> dict[str, dict[str, Any]]:
    """Every unit-level case: inputs, the model call, the registered outcome."""
    c: dict[str, dict[str, Any]] = {}
    f300 = stream(Z_EQ, 300, P_R)

    def add(case_id: str, model: str, purpose: str, inputs: dict, result: dict) -> None:
        c[case_id] = {"model": model, "purpose": purpose, "inputs": inputs, "result": result}

    # -- PH flash ------------------------------------------------------------------------------
    for cid, q, purpose in (
        ("PHF-1", mpf(50000), "two-phase nominal"),
        ("PHF-3", mpf(10000), "single-phase liquid result: vapour outlet dormant"),
        ("PHF-4", mpf(120000), "single-phase vapour result: liquid outlet dormant"),
        ("PHF-F1", mpf(-10000), "target below the domain: typed out_of_domain"),
        ("PHF-F2", mpf(200000), "target above the domain: typed out_of_domain"),
    ):
        add(
            cid,
            "syn001.ph_flash",
            purpose,
            {"inlet": f300, "inlet_phase": "L", "duty": q, "pressure_drop": mpf(0)},
            eval_ph_flash(f300, "L", q, mpf(0)),
        )
    q2 = q_tp_360()
    add(
        "PHF-2",
        "syn001.ph_flash",
        "the inverse of SYN-001's TP flash at 360 K (metamorphic PH o TP = identity)",
        {"inlet": f300, "inlet_phase": "L", "duty": q2, "pressure_drop": mpf(0)},
        eval_ph_flash(f300, "L", q2, mpf(0)),
    )
    zc = stream(Z_ZC, 300, P_R)
    add(
        "PHF-5",
        "syn001.ph_flash",
        "a zero component (B) in a two-phase PH flash",
        {"inlet": zc, "inlet_phase": "L", "duty": mpf(60000), "pressure_drop": mpf(0)},
        eval_ph_flash(zc, "L", mpf(60000), mpf(0)),
    )
    pure = stream(Z_PURE_B, 300, P_R)
    add(
        "PHF-6",
        "syn001.ph_flash",
        "single component: T pinned at the boiling point, the split by the lever rule",
        {"inlet": pure, "inlet_phase": "L", "duty": mpf(42000), "pressure_drop": mpf(0)},
        eval_ph_flash(pure, "L", mpf(42000), mpf(0)),
    )
    hp = stream(Z_EQ, 360, 180000)
    add(
        "PHF-7",
        "syn001.ph_flash",
        "adiabatic flash across a declared pressure drop (equals VLV-2)",
        {"inlet": hp, "inlet_phase": "L", "duty": mpf(0), "pressure_drop": mpf(80000)},
        eval_ph_flash(hp, "L", mpf(0), mpf(80000)),
    )
    dormant = stream(Z_DORMANT, 330, P_R)
    add(
        "PHF-Z0",
        "syn001.ph_flash",
        "dormant inlet, zero duty: ZERO_FLOW, a valid result",
        {"inlet": dormant, "inlet_phase": "L", "duty": mpf(0), "pressure_drop": mpf(0)},
        eval_ph_flash(dormant, "L", mpf(0), mpf(0)),
    )
    add(
        "PHF-Z1",
        "syn001.ph_flash",
        "dormant inlet with a nonzero duty: typed error",
        {"inlet": dormant, "inlet_phase": "L", "duty": mpf(1000), "pressure_drop": mpf(0)},
        eval_ph_flash(dormant, "L", mpf(1000), mpf(0)),
    )
    hot = stream(Z_EQ, 360, P_R)
    add(
        "PHF-F3",
        "syn001.ph_flash",
        "inlet declared LIQUID but two-phase: typed unsupported",
        {"inlet": hot, "inlet_phase": "L", "duty": mpf(0), "pressure_drop": mpf(0)},
        eval_ph_flash(hot, "L", mpf(0), mpf(0)),
    )
    add(
        "PHF-F4",
        "syn001.ph_flash",
        "outlet pressure below the domain: typed out_of_domain",
        {"inlet": f300, "inlet_phase": "L", "duty": mpf(0), "pressure_drop": mpf(60000)},
        eval_ph_flash(f300, "L", mpf(0), mpf(60000)),
    )

    # -- valve ---------------------------------------------------------------------------------
    rx_hp = stream(Z_RX, 300, 180000)
    add(
        "VLV-1",
        "syn001.valve",
        "liquid to liquid: throttling heats a SYN-001 liquid by v dP / c_p",
        {"inlet": rx_hp, "inlet_phase": "L", "outlet_pressure": P_R},
        eval_valve(rx_hp, "L", P_R),
    )
    add(
        "VLV-2",
        "syn001.valve",
        "liquid to two-phase: flashing across the valve cools",
        {"inlet": hp, "inlet_phase": "L", "outlet_pressure": P_R},
        eval_valve(hp, "L", P_R),
    )
    vap = stream(Z_EQ, 420, 150000)
    add(
        "VLV-3",
        "syn001.valve",
        "vapour to vapour: SYN-001 vapour enthalpy is P-independent, so T is unchanged",
        {"inlet": vap, "inlet_phase": "V", "outlet_pressure": mpf(60000)},
        eval_valve(vap, "V", mpf(60000)),
    )
    add(
        "VLV-4",
        "syn001.valve",
        "zero pressure drop: the outlet is the inlet",
        {"inlet": rx_hp, "inlet_phase": "L", "outlet_pressure": mpf(180000)},
        eval_valve(rx_hp, "L", mpf(180000)),
    )
    v2 = c["VLV-2"]["result"]["outlet"]
    lifted_in = stream(v2["n"], as_double(v2["T"]), P_R)
    add(
        "VLV-5",
        "syn001.valve",
        "a two-phase (lifted) inlet flashes further",
        {"inlet": lifted_in, "inlet_phase": None, "outlet_pressure": mpf(60000)},
        eval_valve(lifted_in, None, mpf(60000)),
    )
    add(
        "VLV-Z",
        "syn001.valve",
        "dormant inlet: dormant outlet, the temperature a retained label",
        {"inlet": dormant, "inlet_phase": "L", "outlet_pressure": mpf(90000)},
        eval_valve(dormant, "L", mpf(90000)),
    )
    rx_lp = stream(Z_RX, 300, P_R)
    add(
        "VLV-F1",
        "syn001.valve",
        "outlet pressure above the inlet's: typed out_of_domain",
        {"inlet": rx_lp, "inlet_phase": "L", "outlet_pressure": mpf(120000)},
        eval_valve(rx_lp, "L", mpf(120000)),
    )

    # -- pump ----------------------------------------------------------------------------------
    eta = mpf("0.75")
    add(
        "PUMP-1",
        "syn001.liquid_pump",
        "nominal: eta = 0.75 heats the liquid by (1/eta - 1) v dP / c_p",
        {"inlet": rx_lp, "outlet_pressure": mpf(180000), "efficiency": eta},
        eval_pump(rx_lp, mpf(180000), eta),
    )
    add(
        "PUMP-2",
        "syn001.liquid_pump",
        "eta = 1: isentropic is isothermal for SYN-001's liquid, so no heating",
        {"inlet": rx_lp, "outlet_pressure": mpf(180000), "efficiency": mpf(1)},
        eval_pump(rx_lp, mpf(180000), mpf(1)),
    )
    add(
        "PUMP-3",
        "syn001.liquid_pump",
        "zero pressure rise: zero work",
        {"inlet": rx_lp, "outlet_pressure": P_R, "efficiency": eta},
        eval_pump(rx_lp, P_R, eta),
    )
    sat = stream(saturated_liquid_360(), 360, P_R)
    add(
        "PUMP-4",
        "syn001.liquid_pump",
        "a saturated liquid inlet (SYN-001's flash liquid) is admitted by R-007",
        {"inlet": sat, "outlet_pressure": mpf(180000), "efficiency": eta},
        eval_pump(sat, mpf(180000), eta),
    )
    vap_lp = stream(Z_EQ, 420, P_R)
    add(
        "PUMP-F1",
        "syn001.liquid_pump",
        "vapour inlet: typed unsupported",
        {"inlet": vap_lp, "outlet_pressure": mpf(180000), "efficiency": eta},
        eval_pump(vap_lp, mpf(180000), eta),
    )
    add(
        "PUMP-F2",
        "syn001.liquid_pump",
        "two-phase inlet: typed unsupported",
        {"inlet": hot, "outlet_pressure": mpf(180000), "efficiency": eta},
        eval_pump(hot, mpf(180000), eta),
    )
    add(
        "PUMP-F3",
        "syn001.liquid_pump",
        "outlet pressure below the inlet's: typed out_of_domain",
        {"inlet": rx_lp, "outlet_pressure": mpf(80000), "efficiency": eta},
        eval_pump(rx_lp, mpf(80000), eta),
    )
    add(
        "PUMP-Z",
        "syn001.liquid_pump",
        "dormant inlet: zero work",
        {"inlet": dormant, "outlet_pressure": mpf(180000), "efficiency": eta},
        eval_pump(dormant, mpf(180000), eta),
    )

    # -- conversion reactor --------------------------------------------------------------------
    half = mpf("0.5")
    rx_vap = stream(Z_RX, 420, P_R)
    specs = (
        (
            "RX-1",
            rx_lp,
            "L",
            0,
            half,
            "outlet_temperature",
            mpf(300),
            "liquid, isothermal: the reaction is exactly thermoneutral (ADR 0011 D2)",
        ),
        (
            "RX-2",
            rx_vap,
            "V",
            0,
            half,
            "outlet_temperature",
            mpf(420),
            "vapour, isothermal: Q = xi sum(nu L)",
        ),
        (
            "RX-3",
            rx_vap,
            "V",
            0,
            half,
            "duty",
            mpf(0),
            "vapour, adiabatic: the endothermic reaction cools the stream",
        ),
        (
            "RX-4",
            rx_lp,
            "L",
            0,
            half,
            "outlet_temperature",
            mpf(360),
            "two-phase TP-state outlet: the reaction moves the split",
        ),
        ("RX-5", rx_lp, "L", 0, half, "duty", mpf(40000), "duty-specified, two-phase PH outlet"),
        (
            "RX-6",
            stream((1, 1, half), 420, P_R),
            "V",
            1,
            half,
            "outlet_temperature",
            mpf(420),
            "key B: the non-key reactant A exhausted exactly",
        ),
        (
            "RX-7",
            rx_lp,
            "L",
            0,
            mpf(0),
            "outlet_temperature",
            mpf(330),
            "conversion 0: the reactor is the TP heater",
        ),
        (
            "RX-8",
            rx_vap,
            "V",
            0,
            mpf(1),
            "outlet_temperature",
            mpf(420),
            "conversion 1: the key component exhausted exactly",
        ),
        ("RX-Z", dormant, "L", 0, half, "outlet_temperature", mpf(330), "dormant inlet"),
        (
            "RX-F1",
            stream((1, 1, half), 420, P_R),
            "V",
            1,
            mpf("0.6"),
            "outlet_temperature",
            mpf(420),
            "the non-key reactant would go negative: typed out_of_domain",
        ),
        (
            "RX-F5",
            rx_lp,
            "L",
            0,
            half,
            "duty",
            mpf(-20000),
            "adiabatic target below the domain: typed out_of_domain",
        ),
    )
    for cid, inlet, phase, key, conv, mode, value, purpose in specs:
        add(
            cid,
            "syn001.conversion_reactor",
            purpose,
            {
                "inlet": inlet,
                "inlet_phase": phase,
                "nu": NU,
                "key": COMPONENTS[key],
                "conversion": conv,
                "energy_specification": mode,
                "value": value,
                "pressure_drop": mpf(0),
            },
            eval_reactor(inlet, phase, NU, key, conv, mode, value),
        )

    # -- component separator -------------------------------------------------------------------
    f345 = stream(Z_EQ, 345, P_R)
    seps = (
        ("SEP-1", rx_lp, (mpf("0.9"), half, mpf("0.1")), "L", "L", "all liquid: the duty vanishes"),
        (
            "SEP-2",
            f345,
            (mpf("0.95"), mpf("0.1"), mpf(0)),
            "V",
            "L",
            "vapour top, liquid bottom: Q = sum_i top_i (h_i^V - h_i^L); C absent from the top",
        ),
        ("SEP-3", rx_lp, (mpf(1), mpf(1), mpf(1)), "L", "L", "split fraction 1: dormant bottom"),
        ("SEP-4", rx_lp, (mpf(0), mpf(0), mpf(0)), "L", "L", "split fraction 0: dormant top"),
        ("SEP-Z", dormant, (mpf("0.9"), half, mpf("0.1")), "L", "L", "dormant inlet"),
        (
            "SEP-F2",
            f345,
            (half, half, half),
            "V",
            "L",
            "top declared VAPOR but liquid: typed unsupported",
        ),
    )
    for cid, inlet, fractions, tp, bp, purpose in seps:
        add(
            cid,
            "syn001.component_separator",
            purpose,
            {
                "inlet": inlet,
                "inlet_phase": "L",
                "split": fractions,
                "top_phase": tp,
                "bottom_phase": bp,
            },
            eval_separator(inlet, "L", fractions, tp, bp),
        )

    # -- heat exchanger ------------------------------------------------------------------------
    hot_l = stream(HOT_BIG, 340, P_R)
    cold_l = stream(Z_EQ, 300, P_R)
    hxs = (
        (
            "HX-1",
            hot_l,
            cold_l,
            "L",
            "L",
            "cold_outlet_temperature",
            mpf(320),
            "liquid/liquid, cold-outlet specification",
        ),
        (
            "HX-2",
            hot_l,
            cold_l,
            "L",
            "L",
            "hot_outlet_temperature",
            mpf(328),
            "the same state by its hot-outlet specification",
        ),
        ("HX-3", hot_l, cold_l, "L", "L", "duty", mpf(6000), "the same state by its duty"),
        (
            "HX-4",
            stream(HOT_SMALL, 430, P_R),
            cold_l,
            "V",
            "L",
            "hot_outlet_temperature",
            mpf(400),
            "vapour hot side",
        ),
        ("HX-5", hot_l, cold_l, "L", "L", "duty", mpf(0), "zero duty: outlets are inlets"),
        (
            "HX-Z0",
            stream(Z_DORMANT, 340, P_R),
            cold_l,
            "L",
            "L",
            "duty",
            mpf(0),
            "dormant hot side, zero duty: valid",
        ),
        (
            "HX-Z1",
            stream(Z_DORMANT, 340, P_R),
            cold_l,
            "L",
            "L",
            "cold_outlet_temperature",
            mpf(320),
            "dormant hot side cannot heat the cold side: typed error",
        ),
        (
            "HX-F1",
            hot_l,
            cold_l,
            "L",
            "L",
            "cold_outlet_temperature",
            mpf(345),
            "temperature cross at the hot end only",
        ),
        (
            "HX-F2",
            stream(HOT_SMALL, 340, P_R),
            cold_l,
            "L",
            "L",
            "hot_outlet_temperature",
            mpf(295),
            "temperature cross at the cold end only",
        ),
        (
            "HX-F3",
            hot_l,
            cold_l,
            "L",
            "L",
            "cold_outlet_temperature",
            mpf(290),
            "heat would flow from cold to hot",
        ),
        (
            "HX-F4",
            stream(HOT_SMALL, 430, P_R),
            stream(Z_EQ, 340, P_R),
            "V",
            "L",
            "cold_outlet_temperature",
            mpf(350),
            "the cold side would boil: typed unsupported",
        ),
    )
    for cid, h_in, c_in, hph, cph, mode, value, purpose in hxs:
        add(
            cid,
            "syn001.heat_exchanger",
            purpose,
            {
                "hot_inlet": h_in,
                "cold_inlet": c_in,
                "hot_phase": hph,
                "cold_phase": cph,
                "specification": mode,
                "value": value,
            },
            eval_exchanger(h_in, c_in, hph, cph, mode, value),
        )
    return c


#: Construction-time refusals (SpecificationError), each with its registered code (T05 §10.2).
SPECIFICATION_ERRORS: tuple[tuple[str, str, str, dict[str, Any]], ...] = (
    ("PHF-S1", "syn001.ph_flash", "negative_pressure_drop", {"pressure_drop": -1000.0}),
    (
        "VLV-S1",
        "syn001.valve",
        "pressure_outside_domain(outlet_pressure)",
        {"outlet_pressure": 40000.0},
    ),
    ("PUMP-S1", "syn001.liquid_pump", "efficiency_outside_interval", {"efficiency": 0.0}),
    ("PUMP-S2", "syn001.liquid_pump", "efficiency_outside_interval", {"efficiency": 1.2}),
    ("RX-S1", "syn001.conversion_reactor", "conversion_outside_unit_interval", {"conversion": 1.5}),
    ("RX-S2", "syn001.conversion_reactor", "key_not_reactant", {"key": "C"}),
    (
        "RX-S3",
        "syn001.conversion_reactor",
        "stoichiometry_not_mass_conserving",
        {"nu": [-1.0, 2.0, 0.0]},
    ),
    (
        "RX-S4",
        "syn001.conversion_reactor",
        "reference_convention_not_reaction_consistent(SYN-001-ref-v0)",
        {"provider_reference_convention": "SYN-001-ref-v0"},
    ),
    (
        "RX-S5",
        "syn001.conversion_reactor",
        "outlet_temperature_outside_domain",
        {"energy_specification": "outlet_temperature", "value": 450.0},
    ),
    (
        "SEP-S1",
        "syn001.component_separator",
        "split_fraction_outside_unit_interval(A)",
        {"split": [1.1, 0.5, 0.5]},
    ),
    (
        "HX-S1",
        "syn001.heat_exchanger",
        "unknown_specification(approach_temperature)",
        {"specification": "approach_temperature"},
    ),
)


def mass_conservation_residual(nu: Sequence[Any]) -> tuple[Any, Any]:
    """|sum nu_i M_i| and the ADR 0011 threshold 1e-9 sum |nu_i| M_i."""
    return (
        abs(sum((nu[i] * MOLAR_MASS[i] for i in range(NC)), mpf(0))),
        mpf("1e-9") * sum((abs(nu[i]) * MOLAR_MASS[i] for i in range(NC)), mpf(0)),
    )


# ============================================================================================
# 8. Trial states: rows and Jacobians at registered off-solution states (T05 spec §9.2)
# ============================================================================================


def d(value: str) -> Any:
    return as_double(value)


def _stream_values(s: str, n: Sequence[str], t: str, p: str) -> dict[str, Any]:
    out = {fid(s, c): d(n[i]) for i, c in enumerate(COMPONENTS)}
    out[tid(s)] = d(t)
    out[pid(s)] = d(p)
    return out


def _lifted_values(s: str, v: Sequence[str], liq: Sequence[str], vt: str, lt: str) -> dict:
    out = {vid(s, c): d(v[i]) for i, c in enumerate(COMPONENTS)}
    out.update({lid(s, c): d(liq[i]) for i, c in enumerate(COMPONENTS)})
    out[vtot(s)] = d(vt)
    out[ltot(s)] = d(lt)
    return out


def trial_states() -> dict[str, dict[str, dict[str, Any]]]:
    """Two registered states per model, chosen so no term vanishes and every component differs.
    None of them is a solution; they test the function, not the solver."""
    t: dict[str, dict[str, dict[str, Any]]] = {}
    phf_cfg = {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3"}
    t["syn001.ph_flash"] = {
        "J1": {
            "cfg": {**phf_cfg, "inlet_regime": "L"},
            "params": {"duty": d("24000"), "pressure_drop": d("20000")},
            "x": {
                **_stream_values("S1", ("1.2", "0.9", "0.3"), "330", "150000"),
                **_stream_values("S2", ("0.45", "0.25", "0.05"), "352.5", "130000"),
                **_stream_values("S3", ("0.7", "0.6", "0.3"), "351", "128000"),
                ntot("S2"): d("0.8"),
                ntot("S3"): d("1.55"),
                qid("U-PHF"): d("25000"),
            },
        },
        "J2": {
            "cfg": {**phf_cfg, "inlet_regime": "V"},
            "params": {"duty": d("-28000"), "pressure_drop": d("5000")},
            "x": {
                **_stream_values("S1", ("0.5", "1.1", "1.4"), "410", "90000"),
                **_stream_values("S2", ("0.35", "0.5", "0.3"), "371", "85000"),
                **_stream_values("S3", ("0.1", "0.55", "1.2"), "372", "86000"),
                ntot("S2"): d("1.1"),
                ntot("S3"): d("1.9"),
                qid("U-PHF"): d("-30000"),
            },
        },
    }
    vlv_cfg = {"unit": "U-VLV", "inlet": "S1", "outlet": "S2"}
    t["syn001.valve"] = {
        "J1": {
            "cfg": {**vlv_cfg, "inlet_regime": "L"},
            "params": {"outlet_pressure": d("105000")},
            "x": {
                **_stream_values("S1", ("1.2", "0.9", "0.3"), "355", "160000"),
                **_stream_values("S2", ("1.15", "0.95", "0.28"), "349", "100000"),
                **_lifted_values(
                    "S2", ("0.3", "0.12", "0.02"), ("0.8", "0.85", "0.27"), "0.45", "1.9"
                ),
            },
        },
        "J2": {
            "cfg": {**vlv_cfg, "inlet_regime": "lifted"},
            "params": {"outlet_pressure": d("70000")},
            "x": {
                **_stream_values("S1", ("1.1", "0.8", "0.43"), "352", "100000"),
                **_lifted_values(
                    "S1", ("0.2", "0.1", "0.03"), ("0.9", "0.7", "0.4"), "0.35", "2.05"
                ),
                **_stream_values("S2", ("1.05", "0.85", "0.4"), "343", "72000"),
                **_lifted_values(
                    "S2", ("0.4", "0.2", "0.05"), ("0.7", "0.6", "0.33"), "0.6", "1.7"
                ),
            },
        },
    }
    pump_cfg = {"unit": "U-PUMP", "inlet": "S1", "outlet": "S2"}
    t["syn001.liquid_pump"] = {
        "J1": {
            "cfg": pump_cfg,
            "params": {"outlet_pressure": d("175000"), "efficiency": d("0.75")},
            "x": {
                **_stream_values("S1", ("1.2", "0.9", "0.3"), "310", "95000"),
                **_stream_values("S2", ("1.1", "0.95", "0.35"), "311", "170000"),
                wid("U-PUMP"): d("30"),
            },
        },
        "J2": {
            "cfg": pump_cfg,
            "params": {"outlet_pressure": d("190000"), "efficiency": d("0.6")},
            "x": {
                **_stream_values("S1", ("0.3", "0.55", "0.8"), "355", "60000"),
                **_stream_values("S2", ("0.35", "0.5", "0.85"), "356", "185000"),
                wid("U-PUMP"): d("55"),
            },
        },
    }
    rx_cfg = {"unit": "U-RX", "inlet": "S1", "outlet": "S2"}
    t["syn001.conversion_reactor"] = {
        "J1": {
            "cfg": {**rx_cfg, "inlet_regime": "L", "key": 0, "mode": "outlet_temperature"},
            "params": {
                "nu": (d("-2"), d("-1"), d("3")),
                "conversion": d("0.5"),
                "pressure_drop": d("3000"),
                "outlet_temperature": d("365"),
            },
            "x": {
                **_stream_values("S1", ("1.2", "0.9", "0.3"), "320", "110000"),
                **_stream_values("S2", ("0.65", "0.55", "1.25"), "362", "104000"),
                **_lifted_values(
                    "S2", ("0.25", "0.15", "0.2"), ("0.35", "0.45", "1.1"), "0.55", "1.95"
                ),
                qid("U-RX"): d("41000"),
                xid("U-RX"): d("0.28"),
            },
        },
        "J2": {
            "cfg": {**rx_cfg, "inlet_regime": "V", "key": 1, "mode": "duty"},
            "params": {
                "nu": (d("-2"), d("-1"), d("3")),
                "conversion": d("0.4"),
                "pressure_drop": d("0"),
                "duty": d("-5000"),
            },
            "x": {
                **_stream_values("S1", ("1.3", "1.1", "0.6"), "425", "95000"),
                **_stream_values("S2", ("0.5", "0.7", "1.8"), "405", "95500"),
                **_lifted_values(
                    "S2", ("0.45", "0.6", "1.3"), ("0.03", "0.08", "0.45"), "2.4", "0.6"
                ),
                qid("U-RX"): d("-4000"),
                xid("U-RX"): d("0.43"),
            },
        },
    }
    sep_cfg = {"unit": "U-SEP", "inlet": "S1", "top": "S2", "bottom": "S3"}
    t["syn001.component_separator"] = {
        "J1": {
            "cfg": {**sep_cfg, "inlet_regime": "L", "top_phase": "V", "bottom_phase": "L"},
            "params": {"split": (d("0.95"), d("0.3"), d("0.05"))},
            "x": {
                **_stream_values("S1", ("1.0", "1.1", "0.9"), "344", "100000"),
                **_stream_values("S2", ("0.9", "0.35", "0.06"), "345", "101000"),
                **_stream_values("S3", ("0.12", "0.8", "0.83"), "343", "99000"),
                qid("U-SEP"): d("30000"),
            },
        },
        "J2": {
            "cfg": {**sep_cfg, "inlet_regime": "lifted", "top_phase": "L", "bottom_phase": "L"},
            "params": {"split": (d("0.6"), d("0.45"), d("0.2"))},
            "x": {
                **_stream_values("S1", ("1.2", "0.9", "0.5"), "352", "120000"),
                **_lifted_values(
                    "S1", ("0.25", "0.15", "0.05"), ("0.9", "0.8", "0.45"), "0.45", "2.1"
                ),
                **_stream_values("S2", ("0.7", "0.4", "0.12"), "350", "118000"),
                **_stream_values("S3", ("0.45", "0.55", "0.4"), "351", "119000"),
                qid("U-SEP"): d("-9000"),
            },
        },
    }
    hx_cfg = {
        "unit": "U-HX",
        "hot_inlet": "S1",
        "hot_outlet": "S2",
        "cold_inlet": "S3",
        "cold_outlet": "S4",
    }
    t["syn001.heat_exchanger"] = {
        "J1": {
            "cfg": {
                **hx_cfg,
                "hot_phase": "L",
                "cold_phase": "L",
                "specification": "cold_outlet_temperature",
            },
            "params": {"value": d("322")},
            "x": {
                **_stream_values("S1", ("0.8", "1.6", "2.6"), "341", "105000"),
                **_stream_values("S2", ("0.75", "1.65", "2.55"), "327", "104000"),
                **_stream_values("S3", ("1.0", "1.1", "0.9"), "301", "98000"),
                **_stream_values("S4", ("1.05", "1.0", "0.95"), "319", "97000"),
                qid("U-HX"): d("6500"),
            },
        },
        "J2": {
            "cfg": {**hx_cfg, "hot_phase": "V", "cold_phase": "L", "specification": "duty"},
            "params": {"value": d("7200")},
            "x": {
                **_stream_values("S1", ("0.4", "0.8", "1.3"), "431", "101000"),
                **_stream_values("S2", ("0.43", "0.75", "1.36"), "399", "100500"),
                **_stream_values("S3", ("0.9", "1.2", "1.0"), "302", "150000"),
                **_stream_values("S4", ("0.95", "1.1", "1.05"), "326", "149000"),
                qid("U-HX"): d("7600"),
            },
        },
    }
    return t


#: The properties each model's rows read (T05 §3.3). A mutation of a property a model never
#: reads is not a test of that model, so it is not in its catalogue.
READS: dict[str, frozenset[str]] = {
    "syn001.ph_flash": frozenset({"h_liq", "h_vap", "lnk"}),
    "syn001.valve": frozenset({"h_liq", "h_vap", "lnk"}),
    "syn001.conversion_reactor": frozenset({"h_liq", "h_vap", "lnk"}),
    "syn001.component_separator": frozenset({"h_liq", "h_vap"}),
    "syn001.liquid_pump": frozenset({"h_liq"}),
    "syn001.heat_exchanger": frozenset({"h_liq", "h_vap"}),
}

#: Mutations the SYN-001 data cannot see at any state (T05 §9.3, §15): a permutation of a lifted
#: inlet's *liquid* flows is read only through sum_i l_i h_i^L, and h_i^L is the same function for
#: every component. Registered so that a new invisibility fails the generator instead of passing.
EXPECTED_INVISIBLE: dict[str, frozenset[str]] = {
    "syn001.valve": frozenset(
        {"swap(S1.liq, A<->B)", "swap(S1.liq, B<->C)", "swap(S1.liq, A<->C)"}
    ),
    "syn001.component_separator": frozenset(
        {"swap(S1.liq, A<->B)", "swap(S1.liq, B<->C)", "swap(S1.liq, A<->C)"}
    ),
}


def mutation_catalogue(model: str, state: Mapping[str, Any]) -> list[tuple[str, Any]]:
    """Every registered mutation of a model: (name, (thermo, x, params, builder))."""
    cfg, params, x = state["cfg"], state["params"], state["x"]
    builder = BUILDERS[model]
    out: list[tuple[str, Any]] = []
    transpositions = ((0, 1), (1, 2), (0, 2))
    # 1. a component read with the wrong index, one stream vector at a time
    vectors: dict[str, list[str]] = {}
    for key in x:
        parts = key.split(".")
        if len(parts) == 3 and parts[2] in COMPONENTS:
            vectors.setdefault(f"{parts[0]}.{parts[1]}", []).append(key)
    for vector in sorted(vectors):
        for a, b in transpositions:
            ka, kb = f"{vector}.{COMPONENTS[a]}", f"{vector}.{COMPONENTS[b]}"
            swapped = dict(x)
            swapped[ka], swapped[kb] = x[kb], x[ka]
            out.append(
                (
                    f"swap({vector}, {COMPONENTS[a]}<->{COMPONENTS[b]})",
                    (TH, swapped, params, builder),
                )
            )
    # 2. property data read with the wrong component index (only properties the model reads)
    for a, b in transpositions:
        perm = [0, 1, 2]
        perm[a], perm[b] = b, a
        if "h_vap" in READS[model]:
            out.append(
                (
                    f"h_vap_data({COMPONENTS[a]}<->{COMPONENTS[b]})",
                    (Thermo(MP, h_vap_map=perm), x, params, builder),
                )
            )
        if "lnk" in READS[model]:
            out.append(
                (
                    f"lnk_data({COMPONENTS[a]}<->{COMPONENTS[b]})",
                    (Thermo(MP, lnk_map=perm), x, params, builder),
                )
            )
    # 3. a declared phase written as the other phase
    for field in ("inlet_regime", "top_phase", "bottom_phase", "hot_phase", "cold_phase"):
        if field in cfg and cfg[field] in ("L", "V"):
            other = "V" if cfg[field] == "L" else "L"
            out.append(
                (
                    f"phase({field}: {cfg[field]}->{other})",
                    (TH, x, params, _with_cfg(builder, {field: other})),
                )
            )
    # 4. model-specific slips
    if model == "syn001.conversion_reactor":
        nu = params["nu"]
        for a, b in transpositions:
            perm = list(nu)
            perm[a], perm[b] = nu[b], nu[a]
            out.append(
                (
                    f"nu({COMPONENTS[a]}<->{COMPONENTS[b]})",
                    (TH, x, {**params, "nu": tuple(perm)}, builder),
                )
            )
        for other in range(NC):
            if other != cfg["key"] and nu[other] < 0:
                out.append(
                    (
                        f"key({COMPONENTS[cfg['key']]}->{COMPONENTS[other]})",
                        (TH, x, params, _with_cfg(builder, {"key": other})),
                    )
                )
        out.append(
            (
                "conversion(X -> 1 - X)",
                (TH, x, {**params, "conversion": 1 - params["conversion"]}, builder),
            )
        )
        out.append(("extent without 1/|nu_key|", (TH, x, params, _key_only(builder))))
    if model == "syn001.liquid_pump":
        out.append(("work relation eta on the ideal work", (TH, x, params, _pump_eta_swapped)))
    if model == "syn001.component_separator":
        out.append(("split applied to the bottom", (TH, x, params, _separator_bottom_split)))
    if model == "syn001.ph_flash":
        out.append(("K at the liquid outlet's (T, P)", (TH, x, params, _phf_k_at_liquid)))
    return out


def _with_cfg(builder: Callable[..., Rows], override: Mapping[str, Any]) -> Callable[..., Rows]:
    def mutated(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
        return builder(th, x, {**cfg, **override}, p)

    return mutated


def _key_only(builder: Callable[..., Rows]) -> Callable[..., Rows]:
    """The conversion row with the key's coefficient dropped: xi - X n_key."""

    def mutated(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
        rows = builder(th, x, cfg, p)
        u, si = cfg["unit"], cfg["inlet"]
        rows[rid(u, "RX-conversion")] = (
            "molar_flow",
            [x[xid(u)], -(p["conversion"] * x[fid(si, COMPONENTS[cfg["key"]])])],
        )
        return rows

    return mutated


def _pump_eta_swapped(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
    rows = rows_pump(th, x, cfg, p)
    kind, terms = rows[rid(cfg["unit"], "PUMP-work")]
    eta = p["efficiency"]
    rows[rid(cfg["unit"], "PUMP-work")] = (
        kind,
        [x[wid(cfg["unit"])], *(eta * t for t in terms[1:])],
    )
    return rows


def _separator_bottom_split(
    th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping
) -> Rows:
    rows = rows_separator(th, x, cfg, p)
    for i, c in enumerate(COMPONENTS):
        rows[rid(cfg["unit"], "SEP-split", c)] = (
            "molar_flow",
            [x[fid(cfg["bottom"], c)], -(p["split"][i] * x[fid(cfg["inlet"], c)])],
        )
    return rows


def _phf_k_at_liquid(th: Thermo, x: Mapping[str, Any], cfg: Mapping[str, Any], p: Mapping) -> Rows:
    rows = rows_ph_flash(th, x, cfg, p)
    u, sv, sl = cfg["unit"], cfg["vapor"], cfg["liquid"]
    for i, c in enumerate(COMPONENTS):
        rows[rid(u, "PHF-equilibrium", c)] = (
            "molar_flow_squared",
            [
                x[fid(sv, c)] * x[ntot(sl)],
                -(th.k(i, x[tid(sl)], x[pid(sl)]) * x[fid(sl, c)] * x[ntot(sv)]),
            ],
        )
    return rows


def row_tolerance(entry: Mapping[str, Any]) -> Any:
    return ROW_REL * entry["scale"]


def analyse_trial_states() -> dict[str, Any]:
    """Rows, Jacobians, term visibility and mutation detection at every trial state."""
    report: dict[str, Any] = {}
    for model, states in trial_states().items():
        model_report: dict[str, Any] = {"states": {}, "mutations": {}, "invisible": {}}
        base: dict[str, dict[str, dict[str, Any]]] = {}
        term_visible: dict[tuple[str, int], Any] = {}
        for name, state in states.items():
            # Values from plain arithmetic, partials from the dual path: every comparison below
            # is then between two evaluations that did the same arithmetic.
            rows = evaluate_rows(model, MP, state["x"], state["cfg"], state["params"])
            duals = evaluate_rows(
                model, MP, state["x"], state["cfg"], state["params"], jacobian=True
            )
            for row, entry in rows.items():
                entry["jac"] = duals[row]["jac"]
                entry["partial_scale"] = duals[row]["partial_scale"]
                entry["dual_value"] = duals[row]["value"]
            base[name] = rows
            for row, entry in rows.items():
                for j, term in enumerate(entry["terms"]):
                    ratio = abs(term) / entry["scale"]
                    term_visible[(row, j)] = max(term_visible.get((row, j), mpf(0)), ratio)
            model_report["states"][name] = {
                "cfg": state["cfg"],
                "params": state["params"],
                "x": state["x"],
                "rows": rows,
            }
        model_report["min_term_visibility"] = min(term_visible.values())
        # pairwise distinct Jacobian rows (a permuted row id cannot hide)
        for name, rows in base.items():
            signatures = [
                tuple(sorted((k, mp.nstr(v, 12)) for k, v in entry["jac"].items()))
                for entry in rows.values()
            ]
            model_report["states"][name]["rows_pairwise_distinct"] = len(set(signatures)) == len(
                signatures
            )
        # mutations: each must move some row by >= DETECTION_FACTOR row tolerances somewhere
        for name, state in states.items():
            for label, (th, xm, pm, builder) in mutation_catalogue(model, state):
                rows_m = evaluate_rows(model, MP, xm, state["cfg"], pm, thermo=th, builder=builder)
                ratio = max(
                    abs(rows_m[r]["value"] - base[name][r]["value"]) / row_tolerance(base[name][r])
                    for r in base[name]
                )
                previous = model_report["mutations"].get(label, mpf(0))
                model_report["mutations"][label] = max(previous, ratio)
        # the degeneracy of the fixture, stated as a checkable fact: h_i^L is the same for all i
        for a, b in ((0, 1), (1, 2), (0, 2)):
            perm = [0, 1, 2]
            perm[a], perm[b] = b, a
            worst = mpf(0)
            for name, state in states.items():
                rows_m = evaluate_rows(
                    model,
                    MP,
                    state["x"],
                    state["cfg"],
                    state["params"],
                    thermo=Thermo(MP, h_liq_map=perm),
                )
                worst = max(
                    worst,
                    max(abs(rows_m[r]["value"] - base[name][r]["value"]) for r in base[name]),
                )
            model_report["invisible"][f"h_liq_data({COMPONENTS[a]}<->{COMPONENTS[b]})"] = worst
        report[model] = model_report
    return report


def dormant_temperature_columns() -> dict[str, dict[str, Any]]:
    """At exactly zero flow, which rows still read each energy-determined outlet temperature?
    (T05 §4.7.) The Jacobian column of such a temperature is zero in every row but a copy row,
    so the EO system is singular there; the causal path returns the temperature as a label."""
    zero = ("0", "0", "0")
    cases: dict[str, tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], list[str]]] = {
        "syn001.valve": (
            "syn001.valve",
            {"unit": "U-VLV", "inlet": "S1", "outlet": "S2", "inlet_regime": "L"},
            {
                **_stream_values("S1", zero, "330", "150000"),
                **_stream_values("S2", zero, "330", "100000"),
                **_lifted_values("S2", zero, zero, "0", "0"),
            },
            {"outlet_pressure": d("100000")},
            [tid("S2")],
        ),
        "syn001.ph_flash": (
            "syn001.ph_flash",
            {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3", "inlet_regime": "L"},
            {
                **_stream_values("S1", zero, "330", "100000"),
                **_stream_values("S2", zero, "330", "100000"),
                **_stream_values("S3", zero, "330", "100000"),
                ntot("S2"): d("0"),
                ntot("S3"): d("0"),
                qid("U-PHF"): d("0"),
            },
            {"duty": d("0"), "pressure_drop": d("0")},
            [tid("S2"), tid("S3")],
        ),
        "syn001.conversion_reactor(duty)": (
            "syn001.conversion_reactor",
            {
                "unit": "U-RX",
                "inlet": "S1",
                "outlet": "S2",
                "inlet_regime": "L",
                "key": 0,
                "mode": "duty",
            },
            {
                **_stream_values("S1", zero, "330", "100000"),
                **_stream_values("S2", zero, "330", "100000"),
                **_lifted_values("S2", zero, zero, "0", "0"),
                qid("U-RX"): d("0"),
                xid("U-RX"): d("0"),
            },
            {"nu": NU, "conversion": d("0.5"), "pressure_drop": d("0"), "duty": d("0")},
            [tid("S2")],
        ),
        "syn001.conversion_reactor(outlet_temperature)": (
            "syn001.conversion_reactor",
            {
                "unit": "U-RX",
                "inlet": "S1",
                "outlet": "S2",
                "inlet_regime": "L",
                "key": 0,
                "mode": "outlet_temperature",
            },
            {
                **_stream_values("S1", zero, "330", "100000"),
                **_stream_values("S2", zero, "330", "100000"),
                **_lifted_values("S2", zero, zero, "0", "0"),
                qid("U-RX"): d("0"),
                xid("U-RX"): d("0"),
            },
            {
                "nu": NU,
                "conversion": d("0.5"),
                "pressure_drop": d("0"),
                "outlet_temperature": d("330"),
            },
            [tid("S2")],
        ),
        "syn001.liquid_pump": (
            "syn001.liquid_pump",
            {"unit": "U-PUMP", "inlet": "S1", "outlet": "S2"},
            {
                **_stream_values("S1", zero, "330", "100000"),
                **_stream_values("S2", zero, "330", "180000"),
                wid("U-PUMP"): d("0"),
            },
            {"outlet_pressure": d("180000"), "efficiency": d("0.75")},
            [tid("S2")],
        ),
        "syn001.component_separator": (
            "syn001.component_separator",
            {
                "unit": "U-SEP",
                "inlet": "S1",
                "top": "S2",
                "bottom": "S3",
                "inlet_regime": "L",
                "top_phase": "L",
                "bottom_phase": "L",
            },
            {
                **_stream_values("S1", zero, "330", "100000"),
                **_stream_values("S2", zero, "330", "100000"),
                **_stream_values("S3", zero, "330", "100000"),
                qid("U-SEP"): d("0"),
            },
            {"split": (d("0.9"), d("0.5"), d("0.1"))},
            [tid("S2"), tid("S3")],
        ),
        "syn001.heat_exchanger(hot side dormant)": (
            "syn001.heat_exchanger",
            {
                "unit": "U-HX",
                "hot_inlet": "S1",
                "hot_outlet": "S2",
                "cold_inlet": "S3",
                "cold_outlet": "S4",
                "hot_phase": "L",
                "cold_phase": "L",
                "specification": "duty",
            },
            {
                **_stream_values("S1", zero, "340", "100000"),
                **_stream_values("S2", zero, "340", "100000"),
                **_stream_values("S3", ("1", "1", "1"), "300", "100000"),
                **_stream_values("S4", ("1", "1", "1"), "300", "100000"),
                qid("U-HX"): d("0"),
            },
            {"value": d("0")},
            [tid("S2"), tid("S4")],
        ),
    }
    out: dict[str, dict[str, Any]] = {}
    for label, (model, cfg, x, params, columns) in cases.items():
        rows = evaluate_rows(model, MP, x, cfg, params, jacobian=True)
        out[label] = {
            column: sorted(row for row, e in rows.items() if e["jac"].get(column, 0) != 0)
            for column in columns
        }
    return out


#: T05 §4.7: the registered structure. A column reading no row is singular; two columns reading
#: only one shared copy row are singular together.
DORMANT_EXPECTED: dict[str, dict[str, list[str]]] = {
    "syn001.valve": {"S2.T": []},
    "syn001.ph_flash": {"S2.T": ["U-PHF:PHF-T"], "S3.T": ["U-PHF:PHF-T"]},
    "syn001.conversion_reactor(duty)": {"S2.T": []},
    "syn001.conversion_reactor(outlet_temperature)": {"S2.T": ["U-RX:RX-spec"]},
    "syn001.liquid_pump": {"S2.T": []},
    "syn001.component_separator": {"S2.T": ["U-SEP:SEP-T:top"], "S3.T": ["U-SEP:SEP-T:bottom"]},
    "syn001.heat_exchanger(hot side dormant)": {"S2.T": [], "S4.T": ["U-HX:HX-energy-cold"]},
}


# ============================================================================================
# 9. Coupled cases (T05 spec §11): expected values by closed forms and 1-D solves
# ============================================================================================


def coupled_c1() -> dict[str, Any]:
    """SYN-001-UL-C1: feed -> pump -> TP heater -> valve -> PH flash (acyclic)."""
    s1 = stream(Z_EQ, 300, P_R)
    pump = eval_pump(s1, mpf(180000), mpf("0.75"))
    s2 = pump["outlet"]
    heater = eval_heater(s2, mpf(360))
    s3 = heater["outlet"]
    valve = eval_valve(s3, None, P_R)
    s4 = valve["outlet"]
    flash = eval_ph_flash(s4, None, mpf(10000), mpf(0))
    h_products = h_flow(flash["vapor"]["n"], flash["T"], P_R, "V") + h_flow(
        flash["liquid"]["n"], flash["T"], P_R, "L"
    )
    h_feed = h_flow(s1["n"], s1["T"], s1["P"], "L")
    return {
        "streams": {
            "S1": s1,
            "S2": s2,
            "S3": s3,
            "S4": s4,
            "S5": flash["vapor"],
            "S6": flash["liquid"],
        },
        "work": {"U-PUMP": pump["work"]},
        "duty": {"U-HEAT": heater["duty"], "U-PHF": mpf(10000)},
        "signatures": {"U-HEAT": s3["regime"], "U-VLV": s4["regime"], "U-PHF": flash["signature"]},
        "envelope_W": pump["work"] + heater["duty"] + mpf(10000) - (h_products - h_feed),
        "valve": valve,
        "flash": flash,
        "pump": pump,
    }


C2_FEED = (mpf(2), mpf(1), mpf(0))
C2_SPLIT = (mpf("0.9"), mpf("0.8"), mpf("0.05"))
C2_T = mpf(315)
C2_X = mpf("0.5")


def coupled_c2() -> dict[str, Any]:
    """SYN-001-UL-C2: feed + recycle -> mixer -> reactor (T spec) -> separator; top recycled."""
    a = matrix(NC, NC)
    rhs = matrix(NC, 1)
    for i in range(NC):
        a[i, i] = 1 - C2_SPLIT[i]
        a[i, 0] -= C2_SPLIT[i] * NU[i] * C2_X / (-NU[0])
        rhs[i] = C2_SPLIT[i] * (C2_FEED[i] + NU[i] * C2_X * C2_FEED[0] / (-NU[0]))
    r = lu_solve(a, rhs)
    recycle_n = tuple(r[i] for i in range(NC))
    s1 = stream(C2_FEED, 300, P_R)
    s4 = {"n": recycle_n, "T": C2_T, "P": P_R}
    mixer = eval_mixer((s1, s4))
    s2 = mixer["outlet"]
    reactor = eval_reactor(s2, "L", NU, 0, C2_X, "outlet_temperature", C2_T)
    s3 = reactor["outlet"]
    sep = eval_separator(s3, None, C2_SPLIT, "L", "L")
    closure = max(abs(sep["top"]["n"][i] - recycle_n[i]) for i in range(NC))
    h_prod = h_flow(sep["bottom"]["n"], C2_T, P_R, "L")
    return {
        "streams": {"S1": s1, "S2": s2, "S3": s3, "S4": sep["top"], "S5": sep["bottom"]},
        "duty": {"U-RX": reactor["duty"], "U-SEP": sep["duty"]},
        "extent": {"U-RX": reactor["extent"]},
        "signatures": {"U-RX": reactor["signature"]},
        "recycle_closure": closure,
        "envelope_W": reactor["duty"] + sep["duty"] - (h_prod - h_flow(C2_FEED, 300, P_R, "L")),
        "reactor": reactor,
        "separator": sep,
    }


C3_Q_FLASH = mpf(48000)
C3_R = mpf("0.6")
C3_T_PURGE_OUT = mpf(310)


def c3_residual(tf: Any, t_purge_out: Any = None) -> Any:
    """C3's reduction (T05 spec §11.4): H_TP(F, T_f) - H(F, 300) - Q_flash - Q_hx(T_f)."""
    t_out = C3_T_PURGE_OUT if t_purge_out is None else t_purge_out
    f = (mpf(1), mpf(1), mpf(1))
    single = tp_split(f, tf, P_R)
    purge = sum(single["l"], mpf(0))
    q_hx = purge * TH.b.CP * (tf - t_out)
    return h_split(single, tf, P_R) - h_flow(f, 300, P_R, "L") - C3_Q_FLASH - q_hx


def coupled_c3(t_purge_out: Any = None) -> dict[str, Any]:
    """SYN-001-UL-C3: feed -> HX cold -> mixer -> PH flash -> splitter; purge -> HX hot.
    With `t_purge_out` = 290 K it is C3X, whose exchanger crosses at the cold end."""
    t_out = C3_T_PURGE_OUT if t_purge_out is None else t_purge_out
    tf = bisect(lambda t: c3_residual(t, t_out), mpf(350), mpf(370))
    f = (mpf(1), mpf(1), mpf(1))
    single = tp_split(f, tf, P_R)
    l_single = sum(single["l"], mpf(0))
    x_liq = tuple(v / l_single for v in single["l"])
    liquid_loop = l_single / (1 - C3_R)
    s5_n = tuple(liquid_loop * xi for xi in x_liq)
    s6_n = tuple(C3_R * v for v in s5_n)
    s7_n = tuple((1 - C3_R) * v for v in s5_n)
    q_hx = sum(s7_n, mpf(0)) * TH.b.CP * (tf - t_out)
    s1 = stream(f, 300, P_R)
    t_co = invert_single_phase(f, P_R, h_flow(f, 300, P_R, "L") + q_hx, "L")
    s2 = {"n": s1["n"], "T": t_co, "P": P_R}
    s6 = {"n": s6_n, "T": tf, "P": P_R}
    mixer = eval_mixer((s2, s6))
    s3 = mixer["outlet"]
    flash = eval_ph_flash(s3, "L", C3_Q_FLASH, mpf(0))
    s7 = {"n": s7_n, "T": tf, "P": P_R}
    hx = eval_exchanger(s7, s1, "L", "L", "hot_outlet_temperature", t_out)
    h_out = (
        h_flow(flash["vapor"]["n"], tf, P_R, "V")
        + h_flow(hx["hot_outlet"]["n"], t_out, P_R, "L")
        - h_flow(f, 300, P_R, "L")
    )
    return {
        "streams": {
            "S1": s1,
            "S2": hx["cold_outlet"],
            "S3": s3,
            "S4": flash["vapor"],
            "S5": flash["liquid"],
            "S6": s6,
            "S7": s7,
            "S8": hx["hot_outlet"],
        },
        "duty": {"U-PHF": C3_Q_FLASH, "U-HX": hx["duty"]},
        "signatures": {"U-PHF": flash["signature"]},
        "T_flash": tf,
        "mixer_closure_K": abs(s3["T"] - mixer["outlet"]["T"]),
        "flash_consistency_K": abs(flash["T"] - tf),
        "flash_liquid_consistency": max(abs(flash["liquid"]["n"][i] - s5_n[i]) for i in range(NC)),
        "hx": hx,
        "flash": flash,
        "envelope_W": C3_Q_FLASH - h_out,
        "reduction_residual_W": c3_residual(tf, t_out),
        "T_purge_out_K": t_out,
    }


def c3_one_pass(m_n: Sequence[Any], t_m: Any) -> tuple[Any, ...]:
    """One traversal of C3 from the mixer outlet (n, T) back to it (the tear map, T05 §11.4)."""
    s3 = {"n": tuple(m_n), "T": t_m, "P": P_R}
    flash = eval_ph_flash(s3, "L", C3_Q_FLASH, mpf(0))
    tf, liquid = flash["T"], flash["liquid"]["n"]
    recycle = tuple(C3_R * v for v in liquid)
    purge = tuple((1 - C3_R) * v for v in liquid)
    f = (mpf(1), mpf(1), mpf(1))
    q_hx = sum(purge, mpf(0)) * TH.b.CP * (tf - C3_T_PURGE_OUT)
    t_co = invert_single_phase(f, P_R, h_flow(f, 300, P_R, "L") + q_hx, "L")
    mixed = eval_mixer(({"n": f, "T": t_co, "P": P_R}, {"n": recycle, "T": tf, "P": P_R}))
    return (*mixed["outlet"]["n"], mixed["outlet"]["T"])


def c3_tear_jacobian(solution: Mapping[str, Any]) -> list[list[Any]]:
    """d(one pass)/d(mixer outlet) at the fixed point, by 40-digit central differences."""
    s3 = solution["streams"]["S3"]
    point = [*s3["n"], s3["T"]]
    h = mpf("1e-12")
    columns = []
    for j in range(NC + 1):
        up = list(point)
        dn = list(point)
        up[j] += h
        dn[j] -= h
        f_up = c3_one_pass(up[:NC], up[NC])
        f_dn = c3_one_pass(dn[:NC], dn[NC])
        columns.append([(f_up[i] - f_dn[i]) / (2 * h) for i in range(NC + 1)])
    return [[columns[j][i] for j in range(NC + 1)] for i in range(NC + 1)]


# ============================================================================================
# 10. Injected false successes for K04's T05 check table (T05 spec §12.4)
# ============================================================================================


def injections(cases: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    # INJ-T1: the valve's trivial root at VLV-2: the outlet forced all-liquid
    v2 = cases["VLV-2"]
    inlet = v2["inputs"]["inlet"]
    n = inlet["n"]
    h_in = h_flow(n, inlet["T"], inlet["P"], "L")
    t_triv = invert_single_phase(n, P_R, h_in, "L")
    cfg = {"unit": "U-VLV", "inlet": "S1", "outlet": "S2", "inlet_regime": "L"}
    x = {
        **{fid("S1", c): n[i] for i, c in enumerate(COMPONENTS)},
        tid("S1"): inlet["T"],
        pid("S1"): inlet["P"],
        **{fid("S2", c): n[i] for i, c in enumerate(COMPONENTS)},
        tid("S2"): t_triv,
        pid("S2"): P_R,
        **{vid("S2", c): mpf(0) for c in COMPONENTS},
        **{lid("S2", c): n[i] for i, c in enumerate(COMPONENTS)},
        vtot("S2"): mpf(0),
        ltot("S2"): sum(n, mpf(0)),
    }
    rows = evaluate_rows("syn001.valve", MP, x, cfg, {"outlet_pressure": P_R})
    total = sum(n, mpf(0))
    k = [TH.k(i, t_triv, P_R) for i in range(NC)]
    fresh = tp_split(n, t_triv, P_R)
    out["INJ-T1"] = {
        "state": "VLV-2 with the outlet split forced to LIQUID (V = 0): the classical trivial root",
        "T_trivial_K": t_triv,
        "max_abs_row_valve": max(abs(e["value"]) for e in rows.values()),
        "admissibility_sum_xK_minus_1": sum((n[i] / total * k[i] for i in range(NC)), mpf(0)) - 1,
        "fresh_flash_energy_gap_W": h_split(fresh, t_triv, P_R) - h_in,
        "independent_split_V_gap_mol_s": sum(fresh["v"], mpf(0)),
        "true_T_K": v2["result"]["outlet"]["T"],
    }
    # INJ-T2: HX-F1's converged EO state (the rows hold; the second law does not)
    f1 = cases["HX-F1"]["result"]
    out["INJ-T2"] = {
        "state": "HX-F1 solved by its rows: T_co = 345 K above T_hi = 340 K",
        "hot_end_K": f1["hot_end_K"],
        "cold_end_K": f1["cold_end_K"],
        "duty_W": f1["duty"],
    }
    # INJ-T3: RX-2 with the outlet computed from a permuted nu at the right extent
    r2 = cases["RX-2"]
    xi = r2["result"]["extent"]
    nu_wrong = (mpf(-1), mpf(-2), mpf(3))
    n_in = r2["inputs"]["inlet"]["n"]
    n_bad = tuple(n_in[i] + nu_wrong[i] * xi for i in range(NC))
    out["INJ-T3"] = {
        "state": "RX-2 with outlet flows from nu' = (-1, -2, 3): moles and mass conserved",
        "component_balance_mol_s": tuple(n_in[i] + NU[i] * xi - n_bad[i] for i in range(NC)),
        "mass_balance_kg_s": sum((MOLAR_MASS[i] * (n_in[i] - n_bad[i]) for i in range(NC)), mpf(0)),
        "total_moles_mol_s": sum(n_in, mpf(0)) - sum(n_bad, mpf(0)),
    }
    # INJ-T4: PUMP-1 with the efficiency ignored (W = W_ideal), energy balance consistent
    p1 = cases["PUMP-1"]["result"]
    w_bad = p1["work_ideal"]
    eta = cases["PUMP-1"]["inputs"]["efficiency"]
    out["INJ-T4"] = {
        "state": "PUMP-1 with W = W_ideal and the outlet temperature that balances it",
        "work_relation_W": eta * w_bad - p1["work_ideal"],
        "energy_balance_W": mpf(0),
    }
    return out


# ============================================================================================
# 11. Measured: the same things in 53-bit arithmetic (floors; never expectations)
# ============================================================================================


def float_tp_split(n: Sequence[float], t: float, p: float) -> dict[str, Any]:
    """The provider's TP flash algorithm (classification, bracketed RR to 1e-14) in doubles."""
    total = sum(n)
    k = [THF.k(i, t, p) for i in range(NC)]
    z = [v / total for v in n]
    if sum(z[i] * k[i] for i in range(NC)) <= 1.0:
        return {"v": (0.0,) * 3, "l": tuple(n)}
    if sum(z[i] / k[i] for i in range(NC)) <= 1.0:
        return {"v": tuple(n), "l": (0.0,) * 3}

    def rr(beta: float) -> float:
        return sum(z[i] * (k[i] - 1.0) / (1.0 + beta * (k[i] - 1.0)) for i in range(NC))

    lo, hi = 0.0, 1.0
    f_lo = rr(lo)
    beta = 0.5
    for _ in range(200):
        value = rr(beta)
        if abs(value) <= 1e-14:
            break
        if value * f_lo > 0.0:
            lo, f_lo = beta, value
        else:
            hi = beta
        slope = -sum(z[i] * (k[i] - 1.0) ** 2 / (1.0 + beta * (k[i] - 1.0)) ** 2 for i in range(NC))
        candidate = beta - value / slope if slope != 0.0 else beta
        beta = candidate if lo < candidate < hi else 0.5 * (lo + hi)
    x = [z[i] / (1.0 + beta * (k[i] - 1.0)) for i in range(NC)]
    v = tuple(beta * total * k[i] * x[i] for i in range(NC))
    return {"v": v, "l": tuple(n[i] - v[i] for i in range(NC))}


def float_h(n: Sequence[float], t: float, p: float, phase: str) -> float:
    return sum(n[i] * THF.h(phase, i, t, p) for i in range(NC))


def float_ph(n: Sequence[float], p: float, target: float) -> float:
    """T05 §4.4's bracket in doubles: bisection to adjacent doubles, then the better end."""

    def f(t: float) -> float:
        s = float_tp_split(n, t, p)
        return float_h(s["v"], t, p, "V") + float_h(s["l"], t, p, "L") - target

    lo, hi = 280.0, 440.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid <= lo or mid >= hi:
            break
        value = f(mid)
        if value == 0.0:
            return mid
        if value < 0.0:
            lo = mid
        else:
            hi = mid
    return lo if abs(f(lo)) <= abs(f(hi)) else hi


def measured_floors(cases: Mapping[str, Any], trials: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"rows": {}, "jacobian": {}, "fd_witness": {}, "ph_kernel_T_K": {}}
    for model, states in trial_states().items():
        worst_row = mpf(0)
        worst_jac = mpf(0)
        worst_fd: dict[str, Any] = {"1e-4": mpf(0), "1e-5": mpf(0), "1e-6": mpf(0)}
        for name, state in states.items():
            ref = trials[model]["states"][name]["rows"]
            x_float = {k: float(v) for k, v in state["x"].items()}
            p_float = {
                k: (tuple(float(e) for e in v) if isinstance(v, tuple) else float(v))
                for k, v in state["params"].items()
            }
            rows_f = evaluate_rows(model, FL, x_float, state["cfg"], p_float, jacobian=True)
            for row, entry in rows_f.items():
                worst_row = max(
                    worst_row, abs(mpf(entry["value"]) - ref[row]["value"]) / ref[row]["scale"]
                )
                for col, value in ref[row]["jac"].items():
                    if value != 0:
                        got = mpf(entry["jac"].get(col, 0.0))
                        worst_jac = max(worst_jac, abs(got - value) / abs(value))
            kinds = {row: ref[row]["kind"] for row in ref}
            for label, step in (("1e-4", 1e-4), ("1e-5", 1e-5), ("1e-6", 1e-6)):
                for col in x_float:
                    s_x = float(_column_scale(col))
                    h = step * s_x
                    up = dict(x_float)
                    dn = dict(x_float)
                    up[col] += h
                    dn[col] -= h
                    r_up = evaluate_rows(model, FL, up, state["cfg"], p_float)
                    r_dn = evaluate_rows(model, FL, dn, state["cfg"], p_float)
                    for row in ref:
                        fd = (r_up[row]["value"] - r_dn[row]["value"]) / (2 * h)
                        exact = float(ref[row]["jac"].get(col, 0))
                        s_f = float(SCALE[kinds[row]])
                        worst_fd[label] = max(worst_fd[label], mpf(abs(fd - exact) * s_x / s_f))
        out["rows"][model] = worst_row
        out["jacobian"][model] = worst_jac
        out["fd_witness"][model] = worst_fd
    for cid in ("PHF-1", "PHF-2", "PHF-5", "PHF-7", "VLV-2", "VLV-5", "RX-5", "RX-3"):
        case = cases[cid]
        result = case["result"]
        if case["model"] == "syn001.ph_flash":
            inlet = case["inputs"]["inlet"]
            n = tuple(float(v) for v in inlet["n"])
            p_out = float(inlet["P"] - case["inputs"]["pressure_drop"])
            target = float(result["H_in"] + case["inputs"]["duty"])
            t_ref = result["T"]
        elif case["model"] == "syn001.valve":
            n = tuple(float(v) for v in case["inputs"]["inlet"]["n"])
            p_out = float(case["inputs"]["outlet_pressure"])
            target = float(result["H_in"])
            t_ref = result["outlet"]["T"]
        else:
            n = tuple(float(v) for v in result["outlet"]["n"])
            p_out = float(result["outlet"]["P"])
            target = float(result["H_in"] + case["inputs"]["value"])
            t_ref = result["outlet"]["T"]
        out["ph_kernel_T_K"][cid] = abs(mpf(float_ph(n, p_out, target)) - t_ref)
    return out


def _column_scale(column: str) -> Any:
    if column.endswith(".T"):
        return SCALE["temperature"]
    if column.endswith(".P"):
        return SCALE["pressure"]
    if column.endswith(".Q") or column.endswith(".W"):
        return SCALE["heat_rate"]
    return SCALE["molar_flow"]


# ============================================================================================
# 12. Generator claims (T05 spec §14.2): every statement about the document's own numbers
# ============================================================================================


class Claims:
    def __init__(self) -> None:
        self.passed: list[str] = []

    def __call__(self, name: str, condition: bool, detail: str = "") -> None:
        if not condition:
            raise AssertionError(f"generator claim failed: {name} {detail}")
        self.passed.append(name)


CLOSE_DEFAULT = mpf("1e-30")


def close(a: Any, b: Any, tol: Any = CLOSE_DEFAULT) -> bool:
    return bool(abs(mpf(a) - mpf(b)) <= tol)


def run_claims(
    cases: Mapping[str, Any],
    trials: Mapping[str, Any],
    coupled: Mapping[str, Any],
    inj: Mapping[str, Any],
    measured: Mapping[str, Any],
    tear: Sequence[Sequence[Any]],
) -> list[str]:
    claim = Claims()
    r = {cid: case["result"] for cid, case in cases.items()}

    # -- the thermodynamics restated here is SYN-001's (sibling closed-form script) ------------
    for t in (mpf(280), mpf(347), mpf(360), mpf(440)):
        for p in (mpf(50000), P_R, mpf(200000)):
            for i in range(NC):
                claim(
                    f"thermo_agrees_with_syn001_reference(T={t},P={p},{COMPONENTS[i]})",
                    close(TH.h("L", i, t, p), p01.h_liquid(i, t, p), mpf("1e-30"))
                    and close(TH.h("V", i, t, p), p01.h_vapor(i, t, p), mpf("1e-30"))
                    and abs(TH.k(i, t, p) / p01.k_value(i, t, p) - 1) < mpf("1e-35"),
                )
    split = tp_split((mpf(1), mpf(1), mpf(1)), mpf(360), P_R)
    ref = p01.tp_flash((mpf(1), mpf(1), mpf(1)), mpf(360), P_R)
    claim("tp_split_agrees_with_syn001_reference", abs(split["beta"] - ref["beta"]) < mpf("1e-35"))
    claim(
        "adr0001_duty_identity_56338_069W",
        abs(q_tp_360() - mpf("56338.069")) < mpf("0.001"),
        mp.nstr(q_tp_360(), 20),
    )

    # -- monotone PH map (the bracket's premise, T05 §4.4) ------------------------------------
    for n in (Z_EQ, Z_ZC, Z_RX, (mpf("0.25"), mpf("0.25"), mpf("0.5"))):
        nn = tuple(mpf(v) for v in n)
        grid = [T_MIN + (T_MAX - T_MIN) * j / 160 for j in range(161)]
        values = [h_tp(nn, t, P_R) for t in grid]
        slopes = [(values[j + 1] - values[j]) / (grid[j + 1] - grid[j]) for j in range(160)]
        claim(
            f"H_TP_strictly_increasing_with_slope_at_least_n_cp({n})",
            min(slopes) >= sum(nn) * TH.b.CP * (1 - mpf("1e-30")),
        )
    for p in (P_MIN, P_R, P_MAX):
        for i in range(NC):
            claim(
                f"latent_heat_positive_on_domain({COMPONENTS[i]},P={p})",
                TH.b.L_VAP[i] - TH.b.V_LIQ[i] * (p - P_R) > 0,
            )

    # -- unit cases: statuses, codes and closed forms ----------------------------------------
    expect = {
        "PHF-1": ("ok", ""),
        "PHF-2": ("ok", ""),
        "PHF-3": ("ok", ""),
        "PHF-4": ("ok", ""),
        "PHF-5": ("ok", ""),
        "PHF-6": ("ok", ""),
        "PHF-7": ("ok", ""),
        "PHF-Z0": ("ok", ""),
        "PHF-Z1": ("error", "duty_into_dormant_stream"),
        "PHF-F1": ("out_of_domain", "ph_outside_domain(below)"),
        "PHF-F2": ("out_of_domain", "ph_outside_domain(above)"),
        "PHF-F3": ("unsupported", "inadmissible_phase(inlet, LIQUID)"),
        "PHF-F4": ("out_of_domain", "pressure_outside_domain(outlet)"),
        "VLV-1": ("ok", ""),
        "VLV-2": ("ok", ""),
        "VLV-3": ("ok", ""),
        "VLV-4": ("ok", ""),
        "VLV-5": ("ok", ""),
        "VLV-Z": ("ok", ""),
        "VLV-F1": ("out_of_domain", "pressure_rise(valve)"),
        "PUMP-1": ("ok", ""),
        "PUMP-2": ("ok", ""),
        "PUMP-3": ("ok", ""),
        "PUMP-4": ("ok", ""),
        "PUMP-Z": ("ok", ""),
        "PUMP-F1": ("unsupported", "inadmissible_phase(inlet, LIQUID)"),
        "PUMP-F2": ("unsupported", "inadmissible_phase(inlet, LIQUID)"),
        "PUMP-F3": ("out_of_domain", "pressure_fall(pump)"),
        "RX-1": ("ok", ""),
        "RX-2": ("ok", ""),
        "RX-3": ("ok", ""),
        "RX-4": ("ok", ""),
        "RX-5": ("ok", ""),
        "RX-6": ("ok", ""),
        "RX-7": ("ok", ""),
        "RX-8": ("ok", ""),
        "RX-Z": ("ok", ""),
        "RX-F1": ("out_of_domain", "reactant_exhausted(A)"),
        "RX-F5": ("out_of_domain", "ph_outside_domain(below)"),
        "SEP-1": ("ok", ""),
        "SEP-2": ("ok", ""),
        "SEP-3": ("ok", ""),
        "SEP-4": ("ok", ""),
        "SEP-Z": ("ok", ""),
        "SEP-F2": ("unsupported", "inadmissible_phase(top, VAPOR)"),
        "HX-1": ("ok", ""),
        "HX-2": ("ok", ""),
        "HX-3": ("ok", ""),
        "HX-4": ("ok", ""),
        "HX-5": ("ok", ""),
        "HX-Z0": ("ok", ""),
        "HX-Z1": ("error", "specification_unsatisfiable_with_dormant_side"),
        "HX-F1": ("out_of_domain", "temperature_cross(hot_end)"),
        "HX-F2": ("out_of_domain", "temperature_cross(cold_end)"),
        "HX-F3": ("out_of_domain", "heat_flow_reversed"),
        "HX-F4": ("unsupported", "inadmissible_phase(cold_outlet, LIQUID)"),
    }
    claim(
        "every_case_has_a_registered_outcome",
        set(expect) == set(cases),
        str(set(cases) ^ set(expect)),
    )
    for cid, (status, code) in expect.items():
        claim(
            f"outcome({cid})={status}{'/' + code if code else ''}",
            r[cid]["status"] == status and r[cid].get("code", "") == code,
            f"got {r[cid]['status']} {r[cid].get('code')}",
        )
    for cid in ("HX-F1", "HX-F2", "HX-F3", "HX-F4", "SEP-F2"):
        claim(
            f"fails_for_exactly_one_reason({cid})",
            len(r[cid]["failures"]) == 1,
            str(r[cid]["failures"]),
        )
    for cid in ("HX-1", "HX-2", "HX-3", "HX-4", "HX-5"):
        claim(f"all_checks_pass({cid})", r[cid]["failures"] == [])

    claim("PHF-3_closed_form_T=300+Q/(n cp)", close(r["PHF-3"]["T"], 300 + mpf(10000) / 300))
    claim(
        "PHF-3_liquid_vapour_dormant",
        r["PHF-3"]["signature"] == "LIQUID" and is_dormant(r["PHF-3"]["vapor"]["n"]),
    )
    claim("PHF-4_closed_form_T=400K", close(r["PHF-4"]["T"], 400))
    claim(
        "PHF-4_vapour_liquid_dormant",
        r["PHF-4"]["signature"] == "VAPOR" and is_dormant(r["PHF-4"]["liquid"]["n"]),
    )
    claim(
        "PHF-2_inverts_the_TP_flash_at_360K",
        abs(r["PHF-2"]["T"] - 360) < mpf("1e-12"),
        mp.nstr(r["PHF-2"]["T"] - 360, 5),
    )
    claim(
        "PHF-2_split_is_syn001_single_flash", abs(r["PHF-2"]["beta"] - ref["beta"]) < mpf("1e-12")
    )
    claim(
        "PHF-5_B_exactly_absent_in_both_outlets",
        r["PHF-5"]["vapor"]["n"][1] == 0
        and r["PHF-5"]["liquid"]["n"][1] == 0
        and r["PHF-5"]["signature"] == "TWO_PHASE",
    )
    claim(
        "PHF-6_saturation_route_T=360K_beta=1/2",
        r["PHF-6"]["route"] == "saturation"
        and close(r["PHF-6"]["T"], 360, mpf("1e-35"))
        and close(r["PHF-6"]["beta"], mpf("0.5"), mpf("1e-35")),
    )
    claim(
        "PHF-7_equals_VLV-2",
        close(r["PHF-7"]["T"], r["VLV-2"]["outlet"]["T"], mpf("1e-35"))
        and all(
            close(r["PHF-7"]["vapor"]["n"][i], r["VLV-2"]["outlet"]["v"][i], mpf("1e-35"))
            for i in range(NC)
        ),
    )
    claim(
        "VLV-1_closed_form_T=T_in+v dP/cp",
        close(r["VLV-1"]["outlet"]["T"], mpf(300) + mpf("0.0001") * 80000 / 100)
        and r["VLV-1"]["signature"] == "LIQUID",
    )
    claim(
        "VLV-2_two_phase_and_colder",
        r["VLV-2"]["signature"] == "TWO_PHASE" and r["VLV-2"]["outlet"]["T"] < 360,
    )
    claim(
        "VLV-3_vapour_T_unchanged",
        close(r["VLV-3"]["outlet"]["T"], 420) and r["VLV-3"]["signature"] == "VAPOR",
    )
    claim(
        "VLV-4_zero_drop_identity",
        close(r["VLV-4"]["outlet"]["T"], 300) and r["VLV-4"]["signature"] == "LIQUID",
    )
    claim(
        "VLV-5_further_flashing",
        r["VLV-5"]["signature"] == "TWO_PHASE"
        and r["VLV-5"]["outlet"]["T"] < r["VLV-2"]["outlet"]["T"]
        and r["VLV-5"]["outlet"]["beta"] > r["VLV-2"]["outlet"]["beta"],
    )
    claim(
        "PUMP-1_closed_forms",
        close(r["PUMP-1"]["work_ideal"], mpf("19.2"), mpf("1e-35"))
        and close(r["PUMP-1"]["work"], mpf("25.6"), mpf("1e-35"))
        and close(r["PUMP-1"]["outlet"]["T"], 300 + mpf("6.4") / 240, mpf("1e-35")),
    )
    claim(
        "PUMP-2_eta_1_no_heating",
        close(r["PUMP-2"]["outlet"]["T"], 300, mpf("1e-35"))
        and close(r["PUMP-2"]["work"], mpf("19.2"), mpf("1e-35")),
    )
    claim(
        "PUMP-3_zero_rise_zero_work",
        r["PUMP-3"]["work"] == 0 and close(r["PUMP-3"]["outlet"]["T"], 300, mpf("1e-35")),
    )
    claim(
        "PUMP-4_saturated_inlet_admitted_by_R-007",
        r["PUMP-4"]["inlet_admissibility"] <= ADMISSIBILITY_K,
    )
    claim("RX-1_liquid_reaction_exactly_thermoneutral", abs(r["RX-1"]["duty"]) < mpf("1e-30"))
    claim(
        "RX-1_extent_and_outlet",
        close(r["RX-1"]["extent"], mpf("0.3"), mpf("1e-35"))
        and all(
            close(r["RX-1"]["outlet"]["n"][i], v, mpf("1e-35"))
            for i, v in enumerate((mpf("0.6"), mpf("0.6"), mpf("1.2")))
        ),
    )
    dh_rx = sum((NU[i] * TH.b.L_VAP[i] for i in range(NC)), mpf(0))
    claim("vapour_reaction_enthalpy_sum_nu_L=+25000", dh_rx == 25000)
    claim(
        "RX-2_Q=xi*sum(nu L)=7500W",
        close(r["RX-2"]["duty"], 7500, mpf("1e-30")) and r["RX-2"]["signature"] == "VAPOR",
    )
    claim(
        "RX-3_adiabatic_T=388.75K",
        close(r["RX-3"]["outlet"]["T"], mpf("388.75")) and r["RX-3"]["signature"] == "VAPOR",
    )
    claim("RX-4_two_phase", r["RX-4"]["signature"] == "TWO_PHASE")
    claim("RX-5_two_phase_duty_specified", r["RX-5"]["signature"] == "TWO_PHASE")
    claim(
        "RX-6_A_exactly_exhausted_Q=12500W",
        r["RX-6"]["outlet"]["n"][0] == 0 and close(r["RX-6"]["duty"], 12500, mpf("1e-30")),
    )
    heater = eval_heater(stream(Z_RX, 300, P_R), mpf(330))
    claim(
        "RX-7_equals_TP_heater",
        close(r["RX-7"]["duty"], heater["duty"], mpf("1e-30"))
        and close(r["RX-7"]["duty"], 7200, mpf("1e-30")),
    )
    claim(
        "RX-8_key_exactly_exhausted_Q=15000W",
        r["RX-8"]["outlet"]["n"][0] == 0 and close(r["RX-8"]["duty"], 15000, mpf("1e-30")),
    )
    claim("RX-8_double_arithmetic_exhausts_exactly", 1.2 + (-2.0) * (1.0 * 1.2 / 2.0) == 0.0)
    claim("RX-6_double_arithmetic_exhausts_exactly", 1.0 + (-2.0) * (0.5 * 1.0 / 1.0) == 0.0)
    claim("SEP-1_all_liquid_duty_vanishes", abs(r["SEP-1"]["duty"]) < mpf("1e-30"))
    claim(
        "SEP-2_closed_form_Q=26750W",
        close(r["SEP-2"]["duty"], 26750, mpf("1e-30")) and r["SEP-2"]["top"]["n"][2] == 0,
    )
    claim("SEP-3_bottom_dormant", is_dormant(r["SEP-3"]["bottom"]["n"]))
    claim("SEP-4_top_dormant", is_dormant(r["SEP-4"]["top"]["n"]))
    for cid in ("HX-1", "HX-2", "HX-3"):
        claim(
            f"{cid}_state_T_ho=328_T_co=320_Q=6000",
            close(r[cid]["hot_outlet"]["T"], 328)
            and close(r[cid]["cold_outlet"]["T"], 320)
            and close(r[cid]["duty"], 6000),
        )
    claim(
        "HX-4_closed_form",
        close(r["HX-4"]["duty"], 7500) and close(r["HX-4"]["cold_outlet"]["T"], 325),
    )
    claim(
        "HX-5_zero_duty_identity",
        close(r["HX-5"]["hot_outlet"]["T"], 340) and close(r["HX-5"]["cold_outlet"]["T"], 300),
    )
    for cid, name, value in (("HX-F1", "hot_end_K", -5), ("HX-F2", "cold_end_K", -5)):
        claim(f"{cid}_{name}={value}", close(r[cid][name], value))
    claim("HX-F3_duty=-3000W", close(r["HX-F3"]["duty"], -3000))
    for spec_id, _model, code, _change in SPECIFICATION_ERRORS:
        claim(f"specification_error_registered({spec_id})", bool(code))
    residual, threshold = mass_conservation_residual(NU)
    claim("registered_nu_conserves_mass", residual <= threshold)
    residual_bad, threshold_bad = mass_conservation_residual((mpf(-1), mpf(2), mpf(0)))
    claim("RX-S3_nu_violates_mass", residual_bad > 1000 * threshold_bad)
    doubles = sum(nu_i * 0.1 for nu_i in (-2.0, -1.0, 3.0))
    claim(
        "mass_check_threshold_1000x_above_double_rounding",
        abs(doubles) < 1e-9 * 0.6 / 1000,
        repr(doubles),
    )

    # -- phase margins of every registered single-phase state (T05 §8.1) ----------------------
    margins: list[tuple[str, Any]] = []

    def phase_margin(label: str, n: Sequence[Any], t: Any, p: Any, expected: str) -> None:
        if is_dormant(n):
            return
        s = tp_split(n, t, p)
        claim(f"regime({label})={expected}", s["regime"] == expected, s["regime"])
        if expected == "LIQUID":
            margins.append((label, 1 - s["szk"]))
        elif expected == "VAPOR":
            margins.append((label, 1 - s["szik"]))
        else:
            margins.append((label, min(s["szk"] - 1, s["szik"] - 1)))

    phase_margin("PHF-1.inlet", Z_EQ, 300, P_R, "LIQUID")
    phase_margin("VLV-1.outlet", Z_RX, r["VLV-1"]["outlet"]["T"], P_R, "LIQUID")
    phase_margin("VLV-2.inlet", Z_EQ, 360, 180000, "LIQUID")
    phase_margin("VLV-3.inlet", Z_EQ, 420, 150000, "VAPOR")
    phase_margin("VLV-3.outlet", Z_EQ, 420, 60000, "VAPOR")
    phase_margin("RX-2.inlet", Z_RX, 420, P_R, "VAPOR")
    phase_margin("RX-2.outlet", r["RX-2"]["outlet"]["n"], 420, P_R, "VAPOR")
    phase_margin("RX-3.outlet", r["RX-3"]["outlet"]["n"], r["RX-3"]["outlet"]["T"], P_R, "VAPOR")
    phase_margin("RX-6.outlet", r["RX-6"]["outlet"]["n"], 420, P_R, "VAPOR")
    phase_margin("RX-8.outlet", r["RX-8"]["outlet"]["n"], 420, P_R, "VAPOR")
    phase_margin("SEP-2.inlet", Z_EQ, 345, P_R, "LIQUID")
    phase_margin("SEP-2.top", r["SEP-2"]["top"]["n"], 345, P_R, "VAPOR")
    phase_margin("SEP-2.bottom", r["SEP-2"]["bottom"]["n"], 345, P_R, "LIQUID")
    phase_margin("HX-1.hot_inlet", HOT_BIG, 340, P_R, "LIQUID")
    phase_margin("HX-1.hot_outlet", HOT_BIG, 328, P_R, "LIQUID")
    phase_margin("HX-1.cold_outlet", Z_EQ, 320, P_R, "LIQUID")
    phase_margin("HX-4.hot_inlet", HOT_SMALL, 430, P_R, "VAPOR")
    phase_margin("HX-4.hot_outlet", HOT_SMALL, 400, P_R, "VAPOR")
    phase_margin("HX-4.cold_outlet", Z_EQ, 325, P_R, "LIQUID")
    phase_margin("HX-F1.cold_outlet", Z_EQ, 345, P_R, "LIQUID")
    phase_margin("HX-F1.hot_outlet", HOT_BIG, r["HX-F1"]["hot_outlet"]["T"], P_R, "LIQUID")
    phase_margin("HX-F2.cold_outlet", Z_EQ, r["HX-F2"]["cold_outlet"]["T"], P_R, "LIQUID")
    phase_margin("HX-F2.hot_outlet", HOT_SMALL, 295, P_R, "LIQUID")
    phase_margin("HX-F3.hot_outlet", HOT_BIG, r["HX-F3"]["hot_outlet"]["T"], P_R, "LIQUID")
    phase_margin("HX-F4.cold_inlet", Z_EQ, 340, P_R, "LIQUID")
    phase_margin("HX-F4.hot_outlet", HOT_SMALL, r["HX-F4"]["hot_outlet"]["T"], P_R, "VAPOR")
    for cid in ("PHF-1", "PHF-2", "PHF-5", "PHF-7", "VLV-2", "VLV-5", "RX-4", "RX-5"):
        res = r[cid]
        if "outlet" in res:
            o = res["outlet"]
            phase_margin(f"{cid}.outlet", o["n"], o["T"], o["P"], "TWO_PHASE")
        else:
            n_tot = tuple(res["vapor"]["n"][i] + res["liquid"]["n"][i] for i in range(NC))
            phase_margin(f"{cid}.outlet", n_tot, res["T"], res["P"], "TWO_PHASE")
    c1s = coupled["SYN-001-UL-C1"]["streams"]
    phase_margin("C1.S3", c1s["S3"]["n"], c1s["S3"]["T"], c1s["S3"]["P"], "LIQUID")
    phase_margin("C1.S4", c1s["S4"]["n"], c1s["S4"]["T"], c1s["S4"]["P"], "TWO_PHASE")
    c1_flash = tuple(c1s["S5"]["n"][i] + c1s["S6"]["n"][i] for i in range(NC))
    phase_margin("C1.U-PHF", c1_flash, c1s["S5"]["T"], P_R, "TWO_PHASE")
    for cid in ("SYN-001-UL-C3", "SYN-001-UL-C3X"):
        cs = coupled[cid]["streams"]
        flash_n = tuple(cs["S4"]["n"][i] + cs["S5"]["n"][i] for i in range(NC))
        phase_margin(f"{cid}.U-PHF", flash_n, cs["S4"]["T"], P_R, "TWO_PHASE")
        phase_margin(f"{cid}.S8", cs["S8"]["n"], cs["S8"]["T"], P_R, "LIQUID")
    worst_margin = min(m for _, m in margins)
    claim(
        "every_registered_regime_is_at_least_1e-3_from_its_boundary",
        worst_margin >= PHASE_MARGIN,
        mp.nstr(worst_margin, 5),
    )

    # -- stencils inside the domain (K04 §4.8 at every registered solution state) -------------
    temps: list[Any] = []
    press: list[Any] = []
    for res in r.values():
        if res["status"] != "ok":
            continue
        for key in ("outlet", "vapor", "liquid", "top", "bottom", "hot_outlet", "cold_outlet"):
            if key in res and not is_dormant(res[key]["n"]):
                temps.append(res[key]["T"])
                press.append(res[key]["P"])
    for case in coupled.values():
        for s in case["streams"].values():
            temps.append(s["T"])
            press.append(s["P"])
    t_margin = min(min(t - T_MIN, T_MAX - t) for t in temps)
    p_margin = min(min(p - P_MIN, P_MAX - p) for p in press)
    claim(
        "fd_stencils_inside_T_domain_by_10_steps",
        t_margin >= 10 * FD_STEP * SCALE["temperature"],
        mp.nstr(t_margin, 5),
    )
    claim(
        "fd_stencils_inside_P_domain_by_10_steps",
        p_margin >= 10 * FD_STEP * SCALE["pressure"],
        mp.nstr(p_margin, 5),
    )

    # -- rows at the twin's own causal solutions are zero (rows and evaluators agree) ---------
    for cid, (model, cfg, x, params) in solution_states(cases).items():
        rows = evaluate_rows(model, MP, x, cfg, params)
        worst = max(abs(e["value"]) / TOL[e["kind"]] for e in rows.values())
        claim(f"rows_vanish_at_causal_solution({cid})", worst < mpf("1e-20"), mp.nstr(worst, 5))

    # -- trial states: every term visible, rows distinct, every mutation detected --------------
    for model, rep in trials.items():
        claim(
            f"every_term_visible({model})",
            rep["min_term_visibility"] >= mpf("1e-6"),
            mp.nstr(rep["min_term_visibility"], 5),
        )
        for name, state in rep["states"].items():
            claim(
                f"jacobian_rows_pairwise_distinct({model},{name})", state["rows_pairwise_distinct"]
            )
        invisible = EXPECTED_INVISIBLE.get(model, frozenset())
        for label, ratio in rep["mutations"].items():
            if label in invisible:
                claim(f"mutation_invisible_by_fixture_degeneracy({model},{label})", ratio == 0)
            else:
                claim(
                    f"mutation_detected({model},{label})",
                    ratio >= DETECTION_FACTOR,
                    mp.nstr(ratio, 5),
                )
        claim(f"registered_invisible_mutations_exist({model})", invisible <= set(rep["mutations"]))
        for label, worst in rep["invisible"].items():
            claim(f"fixture_degeneracy_invisible({model},{label})", worst == 0)

    cancelling = sorted(
        (model, row, col)
        for model, rep in trials.items()
        for state in rep["states"].values()
        for row, e in state["rows"].items()
        for col, value in e["jac"].items()
        if value == 0
    )
    claim(
        "the_only_cancelling_partial_is_the_pump_work_relation_in_T_in",
        sorted(set(cancelling)) == [("syn001.liquid_pump", "U-PUMP:PUMP-work", "S1.T")],
        str(sorted(set(cancelling))),
    )

    dormant = dormant_temperature_columns()
    claim(
        "dormant_temperature_columns_are_the_registered_structure",
        dormant == DORMANT_EXPECTED,
        str(dormant),
    )

    # -- coupled cases ------------------------------------------------------------------------
    c1, c2, c3 = coupled["SYN-001-UL-C1"], coupled["SYN-001-UL-C2"], coupled["SYN-001-UL-C3"]
    claim("C1_envelope_closes", abs(c1["envelope_W"]) < mpf("1e-25"))
    claim(
        "C1_heater_liquid_valve_and_flash_two_phase",
        c1["signatures"] == {"U-HEAT": "LIQUID", "U-VLV": "TWO_PHASE", "U-PHF": "TWO_PHASE"},
    )
    claim(
        "C1_pump_heats_by_8/300_K",
        close(c1["streams"]["S2"]["T"], 300 + mpf(8) / 300, mpf("1e-35")),
    )
    claim("C2_recycle_closes", c2["recycle_closure"] < mpf("1e-35"))
    claim("C2_envelope_closes", abs(c2["envelope_W"]) < mpf("1e-25"))
    claim("C2_reactor_duty=4500W_exactly", close(c2["duty"]["U-RX"], 4500, mpf("1e-30")))
    claim("C2_separator_duty_vanishes", abs(c2["duty"]["U-SEP"]) < mpf("1e-30"))
    claim("C2_all_liquid_every_K_below_1_at_315K", all(TH.k(i, C2_T, P_R) < 1 for i in range(NC)))
    claim("C3_reduction_root", abs(c3["reduction_residual_W"]) < mpf("1e-25"))
    claim(
        "C3_flash_reproduces_T_f",
        c3["flash_consistency_K"] < mpf("1e-30"),
        mp.nstr(c3["flash_consistency_K"], 5),
    )
    claim("C3_flash_liquid_reproduces_loop", c3["flash_liquid_consistency"] < mpf("1e-30"))
    claim("C3_envelope_closes", abs(c3["envelope_W"]) < mpf("1e-25"))
    claim("C3_hx_passes_every_check", c3["hx"]["failures"] == [])
    c3x = coupled["SYN-001-UL-C3X"]
    claim("C3X_reduction_root", abs(c3x["reduction_residual_W"]) < mpf("1e-25"))
    claim("C3X_envelope_closes", abs(c3x["envelope_W"]) < mpf("1e-25"))
    claim("C3X_flash_reproduces_T_f", c3x["flash_consistency_K"] < mpf("1e-30"))
    claim(
        "C3X_exchanger_fails_only_at_the_cold_end",
        c3x["hx"]["failures"] == ["temperature_cross(cold_end)"],
        str(c3x["hx"]["failures"]),
    )
    claim("C3X_cold_end=-10K", close(c3x["hx"]["cold_end_K"], -10))
    s = tp_split(c3x["streams"]["S3"]["n"], c3x["streams"]["S3"]["T"], P_R)
    claim(
        "C3X_mixer_outlet_subcooled_by_1e-3",
        s["regime"] == "LIQUID" and 1 - s["szk"] >= PHASE_MARGIN,
    )
    s = tp_split(c3x["streams"]["S2"]["n"], c3x["streams"]["S2"]["T"], P_R)
    claim(
        "C3X_cold_outlet_subcooled_by_1e-3",
        s["regime"] == "LIQUID" and 1 - s["szk"] >= PHASE_MARGIN,
    )
    claim("C3_recycle_and_purge_differ", C3_R != mpf("0.5"))
    grid = [mpf(350) + j * mpf("0.25") for j in range(81)]
    values = [c3_residual(t) for t in grid]
    claim("C3_reduction_increasing_on_bracket", all(values[j + 1] > values[j] for j in range(80)))
    mixer_z = c3["streams"]["S3"]["n"]
    s = tp_split(mixer_z, c3["streams"]["S3"]["T"], P_R)
    claim(
        "C3_mixer_outlet_subcooled_by_1e-3",
        s["regime"] == "LIQUID" and 1 - s["szk"] >= PHASE_MARGIN,
        mp.nstr(1 - s["szk"], 5),
    )
    s = tp_split(c3["streams"]["S2"]["n"], c3["streams"]["S2"]["T"], P_R)
    claim(
        "C3_cold_outlet_subcooled_by_1e-3", s["regime"] == "LIQUID" and 1 - s["szk"] >= PHASE_MARGIN
    )
    cross = max(abs(tear[NC][j]) for j in range(NC))
    back = max(abs(tear[i][NC]) for i in range(NC))
    claim("C3_tear_map_couples_temperature_to_composition", cross >= mpf("1e-3"), mp.nstr(cross, 5))
    claim("C3_tear_map_couples_composition_to_temperature", back >= mpf("1e-3"), mp.nstr(back, 5))
    claim("C3_tear_map_contracting", _spectral_radius(tear) < 1)

    for cid, (model, cfg, x, params) in coupled_solution_states(coupled).items():
        rows = evaluate_rows(model, MP, x, cfg, params)
        worst = max(abs(e["value"]) / TOL[e["kind"]] for e in rows.values())
        claim(f"rows_vanish_at_coupled_solution({cid})", worst < mpf("1e-20"), mp.nstr(worst, 5))

    # -- injections ---------------------------------------------------------------------------
    t1 = inj["INJ-T1"]
    claim("INJ-T1_every_valve_row_satisfied", t1["max_abs_row_valve"] < mpf("1e-25"))
    claim(
        "INJ-T1_caught_by_admissibility", t1["admissibility_sum_xK_minus_1"] > 1000 * mpf("1e-12")
    )
    claim(
        "INJ-T1_caught_by_fresh_flash_energy",
        abs(t1["fresh_flash_energy_gap_W"]) > 1000 * TOL["heat_rate"],
    )
    claim(
        "INJ-T1_caught_by_independent_split",
        t1["independent_split_V_gap_mol_s"] > 1000 * TOL["molar_flow"],
    )
    t3 = inj["INJ-T3"]
    claim(
        "INJ-T3_mass_and_moles_blind",
        abs(t3["mass_balance_kg_s"]) < mpf("1e-30") and abs(t3["total_moles_mol_s"]) < mpf("1e-30"),
    )
    claim(
        "INJ-T3_component_balance_catches",
        max(abs(v) for v in t3["component_balance_mol_s"]) > 1000 * TOL["molar_flow"],
    )
    claim(
        "INJ-T4_work_relation_catches",
        abs(inj["INJ-T4"]["work_relation_W"]) > 1000 * TOL["heat_rate"],
    )

    # -- measured floors against the registered tolerances -------------------------------------
    worst_row = max(measured["rows"].values())
    worst_jac = max(measured["jacobian"].values())
    worst_fd = max(v["1e-5"] for v in measured["fd_witness"].values())
    worst_ph = max(measured["ph_kernel_T_K"].values())
    claim(
        "row_tolerance_1e-12_at_least_100x_above_53bit_floor",
        ROW_REL >= 100 * worst_row,
        mp.nstr(worst_row, 5),
    )
    claim(
        "jacobian_tolerance_1e-11_at_least_100x_above_53bit_floor",
        JAC_REL >= 100 * worst_jac,
        mp.nstr(worst_jac, 5),
    )
    claim(
        "fd_witness_1e-7_at_least_100x_above_floor_at_1e-5",
        mpf("1e-7") >= 100 * worst_fd,
        mp.nstr(worst_fd, 5),
    )
    claim(
        "ph_kernel_T_1e-6_at_least_100x_above_53bit_floor",
        TOL["temperature"] >= 100 * worst_ph,
        mp.nstr(worst_ph, 5),
    )

    # -- independence ------------------------------------------------------------------------
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    claim(
        "imports_nothing_from_process_runtime_or_benchmarks",
        not ({"openflowsheet", "benchmarks"} & imported),
        str(imported),
    )
    return claim.passed


def coupled_solution_states(
    coupled: Mapping[str, Any],
) -> dict[str, tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """Each T05 unit of C1-C3 with its coupled streams, in the case's own ids (T05 §11)."""

    def sv_(s: str, st: Mapping[str, Any]) -> dict[str, Any]:
        v = {fid(s, c): st["n"][i] for i, c in enumerate(COMPONENTS)}
        v[tid(s)] = st["T"]
        v[pid(s)] = st["P"]
        if "v" in st:
            v.update({vid(s, c): st["v"][i] for i, c in enumerate(COMPONENTS)})
            v.update({lid(s, c): st["l"][i] for i, c in enumerate(COMPONENTS)})
            v[vtot(s)] = sum(st["v"], mpf(0))
            v[ltot(s)] = sum(st["l"], mpf(0))
        return v

    out: dict[str, tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]] = {}
    c1 = coupled["SYN-001-UL-C1"]
    st = c1["streams"]
    out["C1.U-PUMP"] = (
        "syn001.liquid_pump",
        {"unit": "U-PUMP", "inlet": "S1", "outlet": "S2"},
        {**sv_("S1", st["S1"]), **sv_("S2", st["S2"]), wid("U-PUMP"): c1["work"]["U-PUMP"]},
        {"outlet_pressure": mpf(180000), "efficiency": mpf("0.75")},
    )
    out["C1.U-VLV"] = (
        "syn001.valve",
        {"unit": "U-VLV", "inlet": "S3", "outlet": "S4", "inlet_regime": "lifted"},
        {**sv_("S3", st["S3"]), **sv_("S4", st["S4"])},
        {"outlet_pressure": P_R},
    )
    out["C1.U-PHF"] = (
        "syn001.ph_flash",
        {"unit": "U-PHF", "inlet": "S4", "vapor": "S5", "liquid": "S6", "inlet_regime": "lifted"},
        {
            **sv_("S4", st["S4"]),
            **sv_("S5", st["S5"]),
            **sv_("S6", st["S6"]),
            ntot("S5"): sum(st["S5"]["n"], mpf(0)),
            ntot("S6"): sum(st["S6"]["n"], mpf(0)),
            qid("U-PHF"): c1["duty"]["U-PHF"],
        },
        {"duty": mpf(10000), "pressure_drop": mpf(0)},
    )
    c2 = coupled["SYN-001-UL-C2"]
    st = c2["streams"]
    out["C2.U-RX"] = (
        "syn001.conversion_reactor",
        {
            "unit": "U-RX",
            "inlet": "S2",
            "outlet": "S3",
            "inlet_regime": "L",
            "key": 0,
            "mode": "outlet_temperature",
        },
        {
            **sv_("S2", st["S2"]),
            **sv_("S3", st["S3"]),
            qid("U-RX"): c2["duty"]["U-RX"],
            xid("U-RX"): c2["extent"]["U-RX"],
        },
        {"nu": NU, "conversion": C2_X, "pressure_drop": mpf(0), "outlet_temperature": C2_T},
    )
    out["C2.U-SEP"] = (
        "syn001.component_separator",
        {
            "unit": "U-SEP",
            "inlet": "S3",
            "top": "S4",
            "bottom": "S5",
            "inlet_regime": "lifted",
            "top_phase": "L",
            "bottom_phase": "L",
        },
        {
            **sv_("S3", st["S3"]),
            **sv_("S4", st["S4"]),
            **sv_("S5", st["S5"]),
            qid("U-SEP"): c2["duty"]["U-SEP"],
        },
        {"split": C2_SPLIT},
    )
    c3 = coupled["SYN-001-UL-C3"]
    st = c3["streams"]
    out["C3.U-PHF"] = (
        "syn001.ph_flash",
        {"unit": "U-PHF", "inlet": "S3", "vapor": "S4", "liquid": "S5", "inlet_regime": "L"},
        {
            **sv_("S3", st["S3"]),
            **sv_("S4", st["S4"]),
            **sv_("S5", st["S5"]),
            ntot("S4"): sum(st["S4"]["n"], mpf(0)),
            ntot("S5"): sum(st["S5"]["n"], mpf(0)),
            qid("U-PHF"): C3_Q_FLASH,
        },
        {"duty": C3_Q_FLASH, "pressure_drop": mpf(0)},
    )
    out["C3.U-HX"] = (
        "syn001.heat_exchanger",
        {
            "unit": "U-HX",
            "hot_inlet": "S7",
            "hot_outlet": "S8",
            "cold_inlet": "S1",
            "cold_outlet": "S2",
            "hot_phase": "L",
            "cold_phase": "L",
            "specification": "hot_outlet_temperature",
        },
        {
            **sv_("S7", st["S7"]),
            **sv_("S8", st["S8"]),
            **sv_("S1", st["S1"]),
            **sv_("S2", st["S2"]),
            qid("U-HX"): c3["duty"]["U-HX"],
        },
        {"value": C3_T_PURGE_OUT},
    )
    return out


def _spectral_radius(a: Sequence[Sequence[Any]]) -> Any:
    m = matrix([[mpf(v) for v in row] for row in a])
    eigenvalues = mp.eig(m, left=False, right=False)
    return max(abs(e) for e in eigenvalues)


def solution_states(
    cases: Mapping[str, Any],
) -> dict[str, tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """The full EO state of each model at one registered causal solution, for the rows."""
    out: dict[str, tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]] = {}

    def s_vals(s: str, st: Mapping[str, Any]) -> dict[str, Any]:
        v = {fid(s, c): st["n"][i] for i, c in enumerate(COMPONENTS)}
        v[tid(s)] = st["T"]
        v[pid(s)] = st["P"]
        return v

    def lifted(s: str, st: Mapping[str, Any]) -> dict[str, Any]:
        v = {vid(s, c): st["v"][i] for i, c in enumerate(COMPONENTS)}
        v.update({lid(s, c): st["l"][i] for i, c in enumerate(COMPONENTS)})
        v[vtot(s)] = sum(st["v"], mpf(0))
        v[ltot(s)] = sum(st["l"], mpf(0))
        return v

    for cid in ("PHF-1", "PHF-5", "PHF-6"):
        res, inp = cases[cid]["result"], cases[cid]["inputs"]
        x = {
            **s_vals("S1", inp["inlet"]),
            **s_vals("S2", res["vapor"]),
            **s_vals("S3", res["liquid"]),
        }
        x[ntot("S2")] = sum(res["vapor"]["n"], mpf(0))
        x[ntot("S3")] = sum(res["liquid"]["n"], mpf(0))
        x[qid("U-PHF")] = res["duty"]
        cfg = {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3", "inlet_regime": "L"}
        out[cid] = (
            "syn001.ph_flash",
            cfg,
            x,
            {"duty": inp["duty"], "pressure_drop": inp["pressure_drop"]},
        )
    for cid in ("VLV-2", "VLV-5"):
        res, inp = cases[cid]["result"], cases[cid]["inputs"]
        regime = "L" if inp["inlet_phase"] == "L" else "lifted"
        x = {
            **s_vals("S1", inp["inlet"]),
            **s_vals("S2", res["outlet"]),
            **lifted("S2", res["outlet"]),
        }
        if regime == "lifted":
            split = tp_split(inp["inlet"]["n"], inp["inlet"]["T"], inp["inlet"]["P"])
            x.update(lifted("S1", split))
        cfg = {"unit": "U-VLV", "inlet": "S1", "outlet": "S2", "inlet_regime": regime}
        out[cid] = ("syn001.valve", cfg, x, {"outlet_pressure": inp["outlet_pressure"]})
    res, inp = cases["PUMP-1"]["result"], cases["PUMP-1"]["inputs"]
    x = {**s_vals("S1", inp["inlet"]), **s_vals("S2", res["outlet"]), wid("U-PUMP"): res["work"]}
    out["PUMP-1"] = (
        "syn001.liquid_pump",
        {"unit": "U-PUMP", "inlet": "S1", "outlet": "S2"},
        x,
        {"outlet_pressure": inp["outlet_pressure"], "efficiency": inp["efficiency"]},
    )
    for cid in ("RX-3", "RX-4", "RX-5"):
        res, inp = cases[cid]["result"], cases[cid]["inputs"]
        x = {
            **s_vals("S1", inp["inlet"]),
            **s_vals("S2", res["outlet"]),
            **lifted("S2", res["outlet"]),
        }
        x[qid("U-RX")] = res["duty"]
        x[xid("U-RX")] = res["extent"]
        mode = inp["energy_specification"]
        params: dict[str, Any] = {
            "nu": inp["nu"],
            "conversion": inp["conversion"],
            "pressure_drop": inp["pressure_drop"],
        }
        params["outlet_temperature" if mode == "outlet_temperature" else "duty"] = inp["value"]
        cfg = {
            "unit": "U-RX",
            "inlet": "S1",
            "outlet": "S2",
            "inlet_regime": inp["inlet_phase"],
            "key": COMPONENTS.index(inp["key"]),
            "mode": mode,
        }
        out[cid] = ("syn001.conversion_reactor", cfg, x, params)
    res, inp = cases["SEP-2"]["result"], cases["SEP-2"]["inputs"]
    x = {
        **s_vals("S1", inp["inlet"]),
        **s_vals("S2", res["top"]),
        **s_vals("S3", res["bottom"]),
        qid("U-SEP"): res["duty"],
    }
    out["SEP-2"] = (
        "syn001.component_separator",
        {
            "unit": "U-SEP",
            "inlet": "S1",
            "top": "S2",
            "bottom": "S3",
            "inlet_regime": "L",
            "top_phase": "V",
            "bottom_phase": "L",
        },
        x,
        {"split": inp["split"]},
    )
    for cid in ("HX-1", "HX-4"):
        res, inp = cases[cid]["result"], cases[cid]["inputs"]
        x = {
            **s_vals("S1", inp["hot_inlet"]),
            **s_vals("S2", res["hot_outlet"]),
            **s_vals("S3", inp["cold_inlet"]),
            **s_vals("S4", res["cold_outlet"]),
            qid("U-HX"): res["duty"],
        }
        cfg = {
            "unit": "U-HX",
            "hot_inlet": "S1",
            "hot_outlet": "S2",
            "cold_inlet": "S3",
            "cold_outlet": "S4",
            "hot_phase": inp["hot_phase"],
            "cold_phase": inp["cold_phase"],
            "specification": inp["specification"],
        }
        out[cid] = ("syn001.heat_exchanger", cfg, x, {"value": inp["value"]})
    return out


# ============================================================================================
# 13. The document
# ============================================================================================


def s(value: Any, digits: int = 20) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    return p01.s(mpf(value), digits)


def sv(values: Sequence[Any]) -> list[Any]:
    return [s(v) for v in values]


def doc_stream(st: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"n_mol_per_s": sv(st["n"]), "T_K": s(st["T"]), "P_Pa": s(st["P"])}
    if "regime" in st:
        out["regime"] = st["regime"]
    if "v" in st:
        out["vapor_n_mol_per_s"] = sv(st["v"])
        out["liquid_n_mol_per_s"] = sv(st["l"])
    return out


def doc_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in inputs.items():
        if isinstance(value, dict):
            out[key] = doc_stream(value)
        elif isinstance(value, tuple):
            out[key] = sv(value)
        elif value is None or isinstance(value, str):
            out[key] = {"L": "LIQUID", "V": "VAPOR"}.get(value, value) if value else None
        else:
            out[key] = s(value)
    return out


def doc_result(result: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"status": result["status"], "code": result.get("code", "")}
    for key in ("signature", "route"):
        if key in result:
            out[key] = result[key]
    for key in (
        "T",
        "P",
        "beta",
        "duty",
        "work",
        "work_ideal",
        "extent",
        "hot_end_K",
        "cold_end_K",
        "inlet_admissibility",
    ):
        if key in result and result[key] is not None:
            out[
                {
                    "T": "T_K",
                    "P": "P_Pa",
                    "duty": "duty_W",
                    "work": "work_W",
                    "work_ideal": "work_ideal_W",
                    "extent": "extent_mol_per_s",
                    "inlet_admissibility": "inlet_admissibility_K",
                }.get(key, key)
            ] = s(result[key])
    for key in ("vapor", "liquid", "outlet", "top", "bottom", "hot_outlet", "cold_outlet"):
        if key in result:
            out[key] = doc_stream(result[key])
    if result.get("failures"):
        out["failures"] = list(result["failures"])
    return out


def build() -> dict[str, Any]:
    cases = unit_cases()
    trials = analyse_trial_states()
    coupled = {
        "SYN-001-UL-C1": coupled_c1(),
        "SYN-001-UL-C2": coupled_c2(),
        "SYN-001-UL-C3": coupled_c3(),
        "SYN-001-UL-C3X": coupled_c3(mpf(290)),
    }
    tear = c3_tear_jacobian(coupled["SYN-001-UL-C3"])
    inj = injections(cases)
    measured = measured_floors(cases, trials)
    passed = run_claims(cases, trials, coupled, inj, measured, tear)

    trial_doc: dict[str, Any] = {}
    for model, rep in trials.items():
        states_doc = {}
        for name, state in rep["states"].items():
            states_doc[name] = {
                "configuration": {
                    k: ({"L": "LIQUID", "V": "VAPOR"}.get(v, v) if isinstance(v, str) else v)
                    for k, v in state["cfg"].items()
                },
                "parameters": {
                    k: (sv(v) if isinstance(v, tuple) else s(v)) for k, v in state["params"].items()
                },
                "x": {k: s(v) for k, v in state["x"].items()},
                "rows": {
                    row: {"kind": e["kind"], "value": s(e["value"]), "term_scale": s(e["scale"])}
                    for row, e in state["rows"].items()
                },
                "jacobian": [
                    [row, col, s(value)]
                    for row, e in state["rows"].items()
                    for col, value in sorted(e["jac"].items())
                    if value != 0
                ],
                "cancelling_partials": [
                    [row, col, s(e["partial_scale"][col], 6)]
                    for row, e in state["rows"].items()
                    for col, value in sorted(e["jac"].items())
                    if value == 0
                ],
            }
        trial_doc[model] = {
            "states": states_doc,
            "min_term_visibility": s(rep["min_term_visibility"], 6),
            "mutation_detection_ratio_min": s(
                min(
                    ratio
                    for label, ratio in rep["mutations"].items()
                    if label not in EXPECTED_INVISIBLE.get(model, frozenset())
                ),
                6,
            ),
            "mutations_invisible_by_fixture_degeneracy": sorted(
                EXPECTED_INVISIBLE.get(model, frozenset())
            ),
            "mutations": {label: s(ratio, 6) for label, ratio in rep["mutations"].items()},
            "h_liq_data_swaps_invisible_at_every_state": sorted(rep["invisible"]),
        }

    coupled_doc: dict[str, Any] = {}
    for cid, case in coupled.items():
        entry: dict[str, Any] = {"streams": {k: doc_stream(v) for k, v in case["streams"].items()}}
        for key in ("duty", "work", "extent"):
            if key in case:
                entry[{"duty": "duty_W", "work": "work_W", "extent": "extent_mol_per_s"}[key]] = {
                    k: s(v) for k, v in case[key].items()
                }
        entry["signatures"] = case["signatures"]
        entry["envelope_residual_W"] = s(case["envelope_W"], 6)
        coupled_doc[cid] = entry
    for cid in ("SYN-001-UL-C3", "SYN-001-UL-C3X"):
        coupled_doc[cid]["T_flash_K"] = s(coupled[cid]["T_flash"])
        coupled_doc[cid]["exchanger_hot_end_K"] = s(coupled[cid]["hx"]["hot_end_K"])
        coupled_doc[cid]["exchanger_cold_end_K"] = s(coupled[cid]["hx"]["cold_end_K"])
        coupled_doc[cid]["exchanger_failures"] = list(coupled[cid]["hx"]["failures"])
    coupled_doc["SYN-001-UL-C3"]["tear_map_jacobian"] = {
        "coordinates": [*(fid("S3", c) for c in COMPONENTS), tid("S3")],
        "matrix": [[s(v, 12) for v in row] for row in tear],
        "spectral_radius": s(_spectral_radius(tear), 12),
    }

    inj_doc = {
        k: {
            kk: (sv(vv) if isinstance(vv, tuple) else (vv if isinstance(vv, str) else s(vv)))
            for kk, vv in v.items()
        }
        for k, v in inj.items()
    }
    measured_doc = {
        "floors_53_bit": {
            "rows_relative_to_term_scale": {k: s(v, 3) for k, v in measured["rows"].items()},
            "jacobian_relative": {k: s(v, 3) for k, v in measured["jacobian"].items()},
            "ph_kernel_T_K": {k: s(v, 3) for k, v in measured["ph_kernel_T_K"].items()},
        },
        "fd_witness_scaled": {
            model: {step: s(v, 3) for step, v in steps.items()}
            for model, steps in measured["fd_witness"].items()
        },
    }
    return {
        "generated_by": (
            "docs/derivations/scripts/t05_reference.py (design lane, T05): SYN-001 closed forms "
            "(cross-checked against syn001_reference.py), the six T05 models' rows and causal "
            "evaluators, the three coupled cases and the K04 injections, at 40 digits"
        ),
        "specification": "docs/derivations/T05-unit-models-spec.md",
        "independence": (
            "no solver, oracle, graph-layer, benchmarks or process_runtime code was used. "
            "`unit_cases`, `specification_errors`, `trial_states`, `coupled_cases` and "
            "`injections` are expectations; `measured` is labelled and never an expectation."
        ),
        "constants": {
            "components": list(COMPONENTS),
            "domain": {"T_K": [s(T_MIN), s(T_MAX)], "P_Pa": [s(P_MIN), s(P_MAX)]},
            "tolerances": {k: s(v, 6) for k, v in TOL.items()},
            "scales": {k: s(v, 6) for k, v in SCALE.items()},
            "row_relative_tolerance": s(ROW_REL, 3),
            "jacobian_relative_tolerance": s(JAC_REL, 3),
            "detection_factor": s(DETECTION_FACTOR, 3),
            "admissibility_K": s(ADMISSIBILITY_K, 3),
            "phase_margin": s(PHASE_MARGIN, 3),
            "fd_step_fraction_of_scale": s(FD_STEP, 3),
            "stoichiometry_nu": sv(NU),
            "reaction_enthalpy_vapour_J_per_mol": s(
                sum((NU[i] * TH.b.L_VAP[i] for i in range(NC)), mpf(0))
            ),
            "reaction_enthalpy_liquid_J_per_mol": s(
                sum((NU[i] * TH.h("L", i, mpf(345), mpf(123456)) for i in range(NC)), mpf(0))
            ),
            "reaction_consistent_conventions": list(REACTION_CONSISTENT),
        },
        "unit_cases": {
            cid: {
                "model": case["model"],
                "purpose": case["purpose"],
                "inputs": doc_inputs(case["inputs"]),
                "expected": doc_result(case["result"]),
            }
            for cid, case in cases.items()
        },
        "specification_errors": {
            sid: {"model": model, "code": code, "change_from_nominal": change}
            for sid, model, code, change in SPECIFICATION_ERRORS
        },
        "trial_states": trial_doc,
        "coupled_cases": coupled_doc,
        "injections": inj_doc,
        "dormant_temperature_columns": {
            "note": (
                "At exactly zero flow, the rows that still read each outlet temperature fixed "
                "by an energy balance (T05 §4.7). An empty list is a zero Jacobian column."
            ),
            "structure": dormant_temperature_columns(),
        },
        "measured": measured_doc,
        "generator_claims": {"count": len(passed), "names": passed},
    }


def emit(path: Path, document: Mapping[str, Any]) -> str:
    text = yaml.safe_dump(dict(document), sort_keys=False, width=200, allow_unicode=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="re-derive every claim")
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not args.check and not args.emit:
        parser.error("choose --check and/or --emit PATH")
    document = build()
    if args.check:
        for name in document["generator_claims"]["names"]:
            print(f"ok  {name}")
        print(f"{document['generator_claims']['count']} claims passed")
    if args.emit:
        digest = emit(Path(args.emit), document)
        print(f"wrote {args.emit}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
