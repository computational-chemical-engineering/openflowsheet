"""Fable's reference generator for the P02 composition test.

Specification: docs/derivations/P02-composition-spec.md.

Everything here follows from the plan §3.1 SYN-001 definitions and the closed forms of
``docs/derivations/SYN-001.md`` §3, evaluated with mpmath at 40 significant digits. It imports
nothing from ``process_runtime`` or ``benchmarks`` and it never calls a backend: the expected
residuals and Jacobian entries it emits are the independent reference the CasADi and
Pyomo/PyNumero harnesses are judged against (CLAUDE.md "self-generated outputs are regression
fixtures, not validation").

It also *measures* the finite-difference floors that the specification's FD tolerances are
required to sit above (brief §7: no FD tolerance without step, stencil order and floor estimate),
and the condition numbers that justify the linear-solve tolerances.

Run from the repository root inside the project environment (mpmath is in the ``dev`` extra)::

    python docs/derivations/scripts/p02_reference.py --check
    python docs/derivations/scripts/p02_reference.py --emit benchmarks/p02/reference_values.yaml
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import yaml
from mpmath import exp, log, mp, mpf

mp.dps = 40

# --------------------------------------------------------------------------------------------
# SYN-001 constants (plan §3.1) — the only physical inputs
# --------------------------------------------------------------------------------------------
R_GAS = mpf("8.31446261815324")
T_REF = mpf(300)
P_REF = mpf(100000)
CP = mpf(100)
T_BOIL = (mpf(320), mpf(360), mpf(400))
L_VAP = (mpf(25000), mpf(30000), mpf(35000))
V_LIQ = (mpf("0.0001"),) * 3
COMP = ("A", "B", "C")

# Registered scales (derivation §9 / ADR 0001 D6): flows 3 mol/s, T 100 K, P 1e5 Pa, duty 1e5 W.
S_FLOW, S_T, S_P, S_DUTY = mpf(3), mpf(100), mpf(100000), mpf(100000)

# --------------------------------------------------------------------------------------------
# Closed forms (SYN-001 derivation §2-§3 and their derivatives)
# --------------------------------------------------------------------------------------------


def lnk(i: int, t: Any, p: Any) -> Any:
    clausius = (L_VAP[i] / R_GAS) * (1 / T_BOIL[i] - 1 / t)
    poynting = V_LIQ[i] * (p - P_REF) / (R_GAS * t)
    return log(P_REF / p) + clausius + poynting


def dlnk_dt(i: int, t: Any, p: Any) -> Any:
    return (L_VAP[i] - V_LIQ[i] * (p - P_REF)) / (R_GAS * t * t)


def dlnk_dp(i: int, t: Any, p: Any) -> Any:
    return -1 / p + V_LIQ[i] / (R_GAS * t)


def d2lnk_dt2(i: int, t: Any, p: Any) -> Any:
    return -2 * (L_VAP[i] - V_LIQ[i] * (p - P_REF)) / (R_GAS * t**3)


def d2lnk_dtdp(i: int, t: Any, p: Any) -> Any:
    return -V_LIQ[i] / (R_GAS * t * t)


def d2lnk_dp2(i: int, t: Any, p: Any) -> Any:
    return 1 / (p * p)


def h_liq(i: int, t: Any, p: Any) -> Any:
    return CP * (t - T_REF) + V_LIQ[i] * (p - P_REF)


def h_vap(i: int, t: Any) -> Any:
    return CP * (t - T_REF) + L_VAP[i]


# --------------------------------------------------------------------------------------------
# The compiled subsystem: lifted form (L-form, matched) and inlined form (I-form, CasADi-only)
# --------------------------------------------------------------------------------------------
VARS_L = [
    "v_A",
    "v_B",
    "v_C",
    "l_A",
    "l_B",
    "l_C",
    "V",
    "L",
    "lnK_A",
    "lnK_B",
    "lnK_C",
    "hL_A",
    "hL_B",
    "hL_C",
    "T",
    "P",
    "Q",
]
EQS_L = [
    "bal_A",
    "bal_B",
    "bal_C",
    "Vdef",
    "Ldef",
    "eq_A",
    "eq_B",
    "eq_C",
    "kdef_A",
    "kdef_B",
    "kdef_C",
    "hdef_A",
    "hdef_B",
    "hdef_C",
    "energy",
    "tspec",
    "pspec",
]
VARS_I = ["v_A", "v_B", "v_C", "l_A", "l_B", "l_C", "V", "L", "T", "P", "Q"]
EQS_I = [
    "bal_A",
    "bal_B",
    "bal_C",
    "Vdef",
    "Ldef",
    "eq_A",
    "eq_B",
    "eq_C",
    "energy",
    "tspec",
    "pspec",
]

COL_SCALE: dict[str, Any] = {
    **{f"v_{c}": S_FLOW for c in COMP},
    **{f"l_{c}": S_FLOW for c in COMP},
    "V": S_FLOW,
    "L": S_FLOW,
    **{f"lnK_{c}": mpf(1) for c in COMP},
    **{f"hL_{c}": S_DUTY for c in COMP},
    "T": S_T,
    "P": S_P,
    "Q": S_DUTY,
}
ROW_SCALE: dict[str, Any] = {
    **{f"bal_{c}": S_FLOW for c in COMP},
    "Vdef": S_FLOW,
    "Ldef": S_FLOW,
    **{f"eq_{c}": S_FLOW * S_FLOW for c in COMP},
    **{f"kdef_{c}": mpf(1) for c in COMP},
    **{f"hdef_{c}": S_DUTY for c in COMP},
    "energy": S_DUTY,
    "tspec": S_T,
    "pspec": S_P,
}


def residual_l(x: dict[str, Any], prm: dict[str, Any]) -> dict[str, Any]:
    t, p = x["T"], x["P"]
    r: dict[str, Any] = {}
    for i, c in enumerate(COMP):
        r[f"bal_{c}"] = x[f"v_{c}"] + x[f"l_{c}"] - prm["f"][i]
    r["Vdef"] = x["V"] - sum(x[f"v_{c}"] for c in COMP)
    r["Ldef"] = x["L"] - sum(x[f"l_{c}"] for c in COMP)
    for i, c in enumerate(COMP):
        r[f"eq_{c}"] = x[f"v_{c}"] * x["L"] - exp(x[f"lnK_{c}"]) * x[f"l_{c}"] * x["V"]
        r[f"kdef_{c}"] = x[f"lnK_{c}"] - lnk(i, t, p)
        r[f"hdef_{c}"] = x[f"hL_{c}"] - x[f"l_{c}"] * h_liq(i, t, p)
    r["energy"] = (
        sum(x[f"v_{c}"] * h_vap(i, t) for i, c in enumerate(COMP))
        + sum(x[f"hL_{c}"] for c in COMP)
        - prm["H_feed"]
        - x["Q"]
    )
    r["tspec"] = t - prm["T_spec"]
    r["pspec"] = p - prm["P_spec"]
    return r


def jacobian_l(x: dict[str, Any], prm: dict[str, Any]) -> dict[tuple[str, str], Any]:
    t, p = x["T"], x["P"]
    j: dict[tuple[str, str], Any] = {}
    for c in COMP:
        j[(f"bal_{c}", f"v_{c}")] = mpf(1)
        j[(f"bal_{c}", f"l_{c}")] = mpf(1)
        j[("Vdef", f"v_{c}")] = mpf(-1)
        j[("Ldef", f"l_{c}")] = mpf(-1)
    j[("Vdef", "V")] = mpf(1)
    j[("Ldef", "L")] = mpf(1)
    for i, c in enumerate(COMP):
        k = exp(x[f"lnK_{c}"])
        j[(f"eq_{c}", f"v_{c}")] = x["L"]
        j[(f"eq_{c}", f"l_{c}")] = -k * x["V"]
        j[(f"eq_{c}", "V")] = -k * x[f"l_{c}"]
        j[(f"eq_{c}", "L")] = x[f"v_{c}"]
        j[(f"eq_{c}", f"lnK_{c}")] = -k * x[f"l_{c}"] * x["V"]
        j[(f"kdef_{c}", f"lnK_{c}")] = mpf(1)
        j[(f"kdef_{c}", "T")] = -dlnk_dt(i, t, p)
        j[(f"kdef_{c}", "P")] = -dlnk_dp(i, t, p)
        j[(f"hdef_{c}", f"hL_{c}")] = mpf(1)
        j[(f"hdef_{c}", f"l_{c}")] = -h_liq(i, t, p)
        j[(f"hdef_{c}", "T")] = -x[f"l_{c}"] * CP
        j[(f"hdef_{c}", "P")] = -x[f"l_{c}"] * V_LIQ[i]
        j[("energy", f"v_{c}")] = h_vap(i, t)
        j[("energy", f"hL_{c}")] = mpf(1)
    j[("energy", "T")] = CP * sum(x[f"v_{c}"] for c in COMP)
    j[("energy", "Q")] = mpf(-1)
    j[("tspec", "T")] = mpf(1)
    j[("pspec", "P")] = mpf(1)
    return j


def residual_i(x: dict[str, Any], prm: dict[str, Any]) -> dict[str, Any]:
    t, p = x["T"], x["P"]
    r: dict[str, Any] = {}
    for i, c in enumerate(COMP):
        r[f"bal_{c}"] = x[f"v_{c}"] + x[f"l_{c}"] - prm["f"][i]
    r["Vdef"] = x["V"] - sum(x[f"v_{c}"] for c in COMP)
    r["Ldef"] = x["L"] - sum(x[f"l_{c}"] for c in COMP)
    for i, c in enumerate(COMP):
        r[f"eq_{c}"] = x[f"v_{c}"] * x["L"] - exp(lnk(i, t, p)) * x[f"l_{c}"] * x["V"]
    r["energy"] = (
        sum(x[f"v_{c}"] * h_vap(i, t) for i, c in enumerate(COMP))
        + sum(x[f"l_{c}"] * h_liq(i, t, p) for i, c in enumerate(COMP))
        - prm["H_feed"]
        - x["Q"]
    )
    r["tspec"] = t - prm["T_spec"]
    r["pspec"] = p - prm["P_spec"]
    return r


def jacobian_i(x: dict[str, Any], prm: dict[str, Any]) -> dict[tuple[str, str], Any]:
    t, p = x["T"], x["P"]
    j: dict[tuple[str, str], Any] = {}
    for c in COMP:
        j[(f"bal_{c}", f"v_{c}")] = mpf(1)
        j[(f"bal_{c}", f"l_{c}")] = mpf(1)
        j[("Vdef", f"v_{c}")] = mpf(-1)
        j[("Ldef", f"l_{c}")] = mpf(-1)
    j[("Vdef", "V")] = mpf(1)
    j[("Ldef", "L")] = mpf(1)
    for i, c in enumerate(COMP):
        k = exp(lnk(i, t, p))
        j[(f"eq_{c}", f"v_{c}")] = x["L"]
        j[(f"eq_{c}", f"l_{c}")] = -k * x["V"]
        j[(f"eq_{c}", "V")] = -k * x[f"l_{c}"]
        j[(f"eq_{c}", "L")] = x[f"v_{c}"]
        j[(f"eq_{c}", "T")] = -k * x[f"l_{c}"] * x["V"] * dlnk_dt(i, t, p)
        j[(f"eq_{c}", "P")] = -k * x[f"l_{c}"] * x["V"] * dlnk_dp(i, t, p)
        j[("energy", f"v_{c}")] = h_vap(i, t)
        j[("energy", f"l_{c}")] = h_liq(i, t, p)
    j[("energy", "T")] = CP * sum(x[f"v_{c}"] + x[f"l_{c}"] for c in COMP)
    j[("energy", "P")] = sum(x[f"l_{c}"] * V_LIQ[i] for i, c in enumerate(COMP))
    j[("energy", "Q")] = mpf(-1)
    j[("tspec", "T")] = mpf(1)
    j[("pspec", "P")] = mpf(1)
    return j


# --------------------------------------------------------------------------------------------
# On-solution states: single TP flash of the feed at (T, P), mpmath bisection on Rachford-Rice
# --------------------------------------------------------------------------------------------


def flash(f: Sequence[Any], t: Any, p: Any) -> tuple[str, list[Any], list[Any]]:
    k = [exp(lnk(i, t, p)) for i in range(3)]
    ftot = sum(f)
    z = [fi / ftot for fi in f]
    if sum(zi * ki for zi, ki in zip(z, k, strict=True)) <= 1:
        return "LIQUID", [mpf(0)] * 3, list(f)
    if sum(zi / ki for zi, ki in zip(z, k, strict=True)) <= 1:
        return "VAPOR", list(f), [mpf(0)] * 3

    def rr(b: Any) -> Any:
        return sum(zi * (ki - 1) / (1 + b * (ki - 1)) for zi, ki in zip(z, k, strict=True))

    lo, hi = mpf(0), mpf(1)
    for _ in range(200):
        mid = (lo + hi) / 2
        if rr(mid) > 0:
            lo = mid
        else:
            hi = mid
    beta = (lo + hi) / 2
    x = [zi / (1 + beta * (ki - 1)) for zi, ki in zip(z, k, strict=True)]
    liq = [(1 - beta) * ftot * xi for xi in x]
    vap = [fi - li for fi, li in zip(f, liq, strict=True)]
    return "TWO_PHASE", vap, liq


def dbl(v: Any) -> float:
    return float(v)


def s20(v: Any, digits: int = 20) -> str:
    return mp.nstr(mpf(v), digits, strip_zeros=False)


def make_state(
    sid: str,
    f: Sequence[float],
    t: float,
    p: float,
    *,
    h_feed: float,
    t_spec: float,
    p_spec: float,
    purpose: str,
    x_override: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build a registered state. Every entry of x is a double (the harness uses it verbatim)."""
    fm = [mpf(repr(v)) for v in f]
    tm, pm = mpf(repr(t)), mpf(repr(p))
    phase, vap, liq = flash(fm, tm, pm)
    x: dict[str, float] = {}
    if x_override is None:
        for i, c in enumerate(COMP):
            x[f"v_{c}"] = dbl(vap[i])
            x[f"l_{c}"] = dbl(liq[i])
        x["V"] = dbl(sum(vap))
        x["L"] = dbl(sum(liq))
        for i, c in enumerate(COMP):
            x[f"lnK_{c}"] = dbl(lnk(i, tm, pm))
            x[f"hL_{c}"] = dbl(mpf(repr(x[f"l_{c}"])) * h_liq(i, tm, pm))
        x["T"], x["P"] = t, p
        q = sum(mpf(repr(x[f"v_{c}"])) * h_vap(i, tm) for i, c in enumerate(COMP))
        q += sum(mpf(repr(x[f"hL_{c}"])) for c in COMP) - mpf(repr(h_feed))
        x["Q"] = dbl(q)
        on_solution = True
    else:
        x = dict(x_override)
        x["T"], x["P"] = t, p
        on_solution = False
    xm = {k: mpf(repr(v)) for k, v in x.items()}
    prm = {
        "f": fm,
        "H_feed": mpf(repr(h_feed)),
        "T_spec": mpf(repr(t_spec)),
        "P_spec": mpf(repr(p_spec)),
    }
    r_l = residual_l(xm, prm)
    j_l = jacobian_l(xm, prm)
    xi = {k: v for k, v in xm.items() if k in VARS_I}
    r_i = residual_i(xi, prm)
    j_i = jacobian_i(xi, prm)
    num_zero_l = sorted(f"{a}|{b}" for (a, b), v in j_l.items() if v == 0)
    num_zero_i = sorted(f"{a}|{b}" for (a, b), v in j_i.items() if v == 0)
    return {
        "state_id": sid,
        "purpose": purpose,
        "on_solution": on_solution,
        "oracle_phase_state": phase,
        "parameters": {
            "f_mol_per_s": [repr(v) for v in f],
            "H_feed_W": repr(h_feed),
            "T_spec_K": repr(t_spec),
            "P_spec_Pa": repr(p_spec),
        },
        "x_L": {k: repr(x[k]) for k in VARS_L},
        "x_I": {k: repr(x[k]) for k in VARS_I},
        "K": [s20(exp(lnk(i, tm, pm))) for i in range(3)],
        "lnK": [s20(lnk(i, tm, pm)) for i in range(3)],
        "dlnK_dT_per_K": [s20(dlnk_dt(i, tm, pm)) for i in range(3)],
        "dlnK_dP_per_Pa": [s20(dlnk_dp(i, tm, pm)) for i in range(3)],
        "d2lnK_dT2_per_K2": [s20(d2lnk_dt2(i, tm, pm)) for i in range(3)],
        "d2lnK_dTdP": [s20(d2lnk_dtdp(i, tm, pm)) for i in range(3)],
        "d2lnK_dP2_per_Pa2": [s20(d2lnk_dp2(i, tm, pm)) for i in range(3)],
        "hL_J_per_mol": [s20(h_liq(i, tm, pm)) for i in range(3)],
        "hV_J_per_mol": [s20(h_vap(i, tm)) for i in range(3)],
        "residual_L": {k: s20(r_l[k]) for k in EQS_L},
        "jacobian_L": {f"{a}|{b}": s20(v) for (a, b), v in j_l.items()},
        "numerically_zero_entries_L": num_zero_l,
        "residual_I": {k: s20(r_i[k]) for k in EQS_I},
        "jacobian_I": {f"{a}|{b}": s20(v) for (a, b), v in j_i.items()},
        "numerically_zero_entries_I": num_zero_i,
        "_mp": {"x": xm, "prm": prm, "j_l": j_l, "j_i": j_i, "r_l": r_l},
    }


def registered_states() -> list[dict[str, Any]]:
    equi = (1.0, 1.0, 1.0)
    skew = (0.5, 1.0, 1.5)
    st = [
        make_state(
            "S1",
            equi,
            360.0,
            100000.0,
            h_feed=0.0,
            t_spec=360.0,
            p_spec=100000.0,
            purpose="nominal two-phase flash on the oracle solution; 20-digit lnK-derivative "
            "reference exists here (reference_values.yaml lnK_derivatives_at_360K_P_r). "
            "Traps: K_B = 1 exactly and "
            "H_feed = 0 exactly, so neither is evidence on its own.",
        ),
        make_state(
            "S2",
            equi,
            347.0,
            60000.0,
            h_feed=0.0,
            t_spec=347.0,
            p_spec=60000.0,
            purpose="two-phase flash on the oracle solution at P != P_r: Poynting term nonzero "
            "in dlnK/dT, "
            "no K_i equal to 1, dlnK/dP differs from -1/P by v/(RT).",
        ),
        make_state(
            "S3",
            equi,
            310.0,
            100000.0,
            h_feed=0.0,
            t_spec=310.0,
            p_spec=100000.0,
            purpose="single-phase LIQUID solution (V = 0 exactly): structural nonzeros that are "
            "numerically "
            "zero here must stay in the pattern; the same entries are nonzero at S1/S2/S5/S6.",
        ),
        make_state(
            "S4",
            equi,
            420.0,
            100000.0,
            h_feed=0.0,
            t_spec=420.0,
            p_spec=100000.0,
            purpose="single-phase VAPOR solution (L = 0 exactly): the complementary "
            "numerically-zero set, "
            "including the restricted block's T and P entries.",
        ),
        make_state(
            "S5",
            skew,
            372.0,
            130000.0,
            h_feed=9000.0,
            t_spec=370.0,
            p_spec=125000.0,
            purpose="off-solution, non-equimolar feed, interior (T, P) off the reference grid, "
            "H_feed != 0, T != T_spec, P != P_spec: every residual row and every Jacobian "
            "entry is nonzero and generic.",
            x_override={
                "v_A": 0.3,
                "v_B": 0.5,
                "v_C": 0.4,
                "l_A": 0.25,
                "l_B": 0.65,
                "l_C": 1.2,
                "V": 1.38,
                "L": 1.7,
                "lnK_A": 1.1,
                "lnK_B": 0.2,
                "lnK_C": -0.9,
                "hL_A": 1500.0,
                "hL_B": 2500.0,
                "hL_C": 3500.0,
                "Q": 4000.0,
            },
        ),
        make_state(
            "S6",
            skew,
            440.0,
            200000.0,
            h_feed=9000.0,
            t_spec=437.0,
            p_spec=197000.0,
            purpose="off-solution at the closed domain corner (T_max, P_max): the callback must "
            "accept the "
            "boundary inclusively. No FD check here (a central stencil would leave the domain).",
            x_override={
                "v_A": 1.2,
                "v_B": 0.9,
                "v_C": 0.6,
                "l_A": 0.1,
                "l_B": 0.3,
                "l_C": 0.4,
                "V": 2.6,
                "L": 0.95,
                "lnK_A": 1.9,
                "lnK_B": 1.1,
                "lnK_C": 0.3,
                "hL_A": 1400.0,
                "hL_B": 4300.0,
                "hL_C": 5700.0,
                "Q": -2000.0,
            },
        ),
    ]
    return st


# Registered directions (scaled coordinates, no zero entries, no repeated magnitudes).
U_DIR_L = [
    0.31,
    -0.47,
    0.83,
    -0.29,
    0.61,
    -0.73,
    0.19,
    -0.37,
    0.53,
    -0.67,
    0.41,
    -0.23,
    0.79,
    -0.11,
    0.59,
    -0.43,
    0.97,
]
V_DIR_L = [
    -0.13,
    0.71,
    -0.37,
    0.89,
    -0.23,
    0.47,
    -0.61,
    0.17,
    -0.79,
    0.29,
    -0.93,
    0.43,
    -0.07,
    0.67,
    -0.51,
    0.83,
    -0.31,
]
U_DIR_I = U_DIR_L[:8] + U_DIR_L[14:]
V_DIR_I = V_DIR_L[:8] + V_DIR_L[14:]

# Perturbation applied to S1 for the SuperLU Newton-step evidence.
PERTURB = {
    "v_A": ("mul", 1.05),
    "v_B": ("mul", 1.05),
    "v_C": ("mul", 1.05),
    "l_A": ("mul", 1.05),
    "l_B": ("mul", 1.05),
    "l_C": ("mul", 1.05),
    "V": ("mul", 0.97),
    "L": ("mul", 1.02),
    "lnK_A": ("add", 0.1),
    "lnK_B": ("add", 0.1),
    "lnK_C": ("add", 0.1),
    "hL_A": ("mul", 0.9),
    "hL_B": ("mul", 0.9),
    "hL_C": ("mul", 0.9),
    "T": ("add", 5.0),
    "P": ("add", 5000.0),
    "Q": ("add", 1000.0),
}

FD_H_T, FD_H_P, FD_H_L, FD_H_P_HL, FD_EPS = 0.1, 100.0, 0.01, 5000.0, 1e-3
T_MIN, T_MAX, P_MIN, P_MAX = 280.0, 440.0, 50000.0, 200000.0
STENCIL = ((-2, 1.0), (-1, -8.0), (1, 8.0), (2, -1.0))  # fourth-order central, divide by 12 h


def fd4(fn: Callable[[float], float], h: float) -> float:
    return sum(w * fn(k * h) for k, w in STENCIL) / (12.0 * h)


def dense_matrix(
    j: dict[tuple[str, str], Any], rows: list[str], cols: list[str], scaled: bool
) -> np.ndarray:
    m = np.zeros((len(rows), len(cols)))
    for (a, b), v in j.items():
        val = v / ROW_SCALE[a] * COL_SCALE[b] if scaled else v
        m[rows.index(a), cols.index(b)] = float(val)
    return m


# --------------------------------------------------------------------------------------------
# Double-precision evaluators (what a backend computes) for the floor measurements
# --------------------------------------------------------------------------------------------
RD = 8.31446261815324
TB = (320.0, 360.0, 400.0)
LV = (25000.0, 30000.0, 35000.0)


def lnk_d(i: int, t: float, p: float) -> float:
    return math.log(1e5 / p) + (LV[i] / RD) * (1 / TB[i] - 1 / t) + 1e-4 * (p - 1e5) / (RD * t)


def hl_d(i: int, t: float, p: float) -> float:
    return 100.0 * (t - 300.0) + 1e-4 * (p - 1e5)


def hv_d(i: int, t: float) -> float:
    return 100.0 * (t - 300.0) + LV[i]


def residual_l_dbl(x: dict[str, float], prm: dict[str, Any]) -> dict[str, float]:
    t, p = x["T"], x["P"]
    r: dict[str, float] = {}
    for i, c in enumerate(COMP):
        r[f"bal_{c}"] = x[f"v_{c}"] + x[f"l_{c}"] - prm["f"][i]
    r["Vdef"] = x["V"] - (x["v_A"] + x["v_B"] + x["v_C"])
    r["Ldef"] = x["L"] - (x["l_A"] + x["l_B"] + x["l_C"])
    for i, c in enumerate(COMP):
        r[f"eq_{c}"] = x[f"v_{c}"] * x["L"] - math.exp(x[f"lnK_{c}"]) * x[f"l_{c}"] * x["V"]
        r[f"kdef_{c}"] = x[f"lnK_{c}"] - lnk_d(i, t, p)
        r[f"hdef_{c}"] = x[f"hL_{c}"] - x[f"l_{c}"] * hl_d(i, t, p)
    r["energy"] = (
        sum(x[f"v_{c}"] * hv_d(i, t) for i, c in enumerate(COMP))
        + x["hL_A"]
        + x["hL_B"]
        + x["hL_C"]
        - prm["H_feed"]
        - x["Q"]
    )
    r["tspec"] = t - prm["T_spec"]
    r["pspec"] = p - prm["P_spec"]
    return r


def measure_floors(states: list[dict[str, Any]]) -> dict[str, Any]:
    """Worst double-precision FD error against the 40-digit closed forms (the achievable floor)."""
    out: dict[str, Any] = {}
    worst_kt = worst_kp = worst_hl = worst_ht = worst_hp = 0.0
    for st in states:
        if st["state_id"] == "S6":
            continue
        t, p = float(st["x_L"]["T"]), float(st["x_L"]["P"])
        for i in range(3):
            ex_t = float(dlnk_dt(i, mpf(repr(t)), mpf(repr(p))))
            ex_p = float(dlnk_dp(i, mpf(repr(t)), mpf(repr(p))))
            fd_t = fd4(lambda d, i=i, t=t, p=p: lnk_d(i, t + d, p), FD_H_T)
            fd_p = fd4(lambda d, i=i, t=t, p=p: lnk_d(i, t, p + d), FD_H_P)
            worst_kt = max(worst_kt, abs(fd_t - ex_t) / abs(ex_t))
            worst_kp = max(worst_kp, abs(fd_p - ex_p) / abs(ex_p))
            lval = 0.7  # a generic liquid flow for the H^L block probe
            fd_l = fd4(lambda d, i=i, t=t, p=p, lv=lval: (lv + d) * hl_d(i, t, p), FD_H_L)
            fd_ht = fd4(lambda d, i=i, t=t, p=p, lv=lval: lv * hl_d(i, t + d, p), FD_H_T)
            fd_hp = fd4(lambda d, i=i, t=t, p=p, lv=lval: lv * hl_d(i, t, p + d), FD_H_P_HL)
            worst_hl = max(worst_hl, abs(fd_l - hl_d(i, t, p)) / abs(hl_d(i, t, p)))
            worst_ht = max(worst_ht, abs(fd_ht - lval * 100.0) / (lval * 100.0))
            worst_hp = max(worst_hp, abs(fd_hp - lval * 1e-4) / (lval * 1e-4))
    out["callback_lnK_dT"] = {
        "h_K": FD_H_T,
        "stencil": "4th-order central (5-point)",
        "worst_relative_error": worst_kt,
    }
    out["callback_lnK_dP"] = {
        "h_Pa": FD_H_P,
        "stencil": "4th-order central (5-point)",
        "worst_relative_error": worst_kp,
    }
    out["callback_HL_dl"] = {"h_mol_per_s": FD_H_L, "worst_relative_error": worst_hl}
    out["callback_HL_dT"] = {"h_K": FD_H_T, "worst_relative_error": worst_ht}
    out["callback_HL_dP"] = {"h_Pa": FD_H_P_HL, "worst_relative_error": worst_hp}

    # Directional derivative of the assembled L-form residual along D_c u, step eps, 4th order.
    worst_dir: dict[str, float] = {}
    for st in states:
        if st["state_id"] == "S6":
            continue
        xm, prm = st["_mp"]["x"], st["_mp"]["prm"]
        jl = st["_mp"]["j_l"]
        prm_d = {
            "f": [float(v) for v in prm["f"]],
            "H_feed": float(prm["H_feed"]),
            "T_spec": float(prm["T_spec"]),
            "P_spec": float(prm["P_spec"]),
        }
        x0 = {k: float(v) for k, v in xm.items()}
        du = {k: float(COL_SCALE[k]) * U_DIR_L[n] for n, k in enumerate(VARS_L)}
        exact = {
            row: sum(v * mpf(repr(du[col])) for (r_, col), v in jl.items() if r_ == row)
            for row in EQS_L
        }
        for row in EQS_L:

            def along(
                e: float,
                row: str = row,
                x0: dict[str, float] = x0,
                du: dict[str, float] = du,
                prm_d: dict[str, Any] = prm_d,
            ) -> float:
                xe = {k: x0[k] + e * du[k] for k in VARS_L}
                return residual_l_dbl(xe, prm_d)[row]

            fd = fd4(along, FD_EPS)
            err = abs(fd - float(exact[row])) / float(ROW_SCALE[row])
            worst_dir[row] = float(max(worst_dir.get(row, 0.0), err))
    out["directional_L_form"] = {
        "eps": FD_EPS,
        "stencil": "4th-order central (5-point) along D_c u",
        "worst_error_over_row_scale_by_row": worst_dir,
        "worst_error_over_row_scale": float(max(worst_dir.values())),
    }
    return out


def linear_solve_evidence(states: list[dict[str, Any]]) -> dict[str, Any]:
    """Condition numbers of the scaled L-form Jacobian and the S1 Newton-step demonstration."""
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla

    out: dict[str, Any] = {
        "condition_numbers_scaled_L_form": {},
        "condition_numbers_unscaled_L_form": {},
    }
    for st in states:
        js = dense_matrix(st["_mp"]["j_l"], EQS_L, VARS_L, scaled=True)
        ju = dense_matrix(st["_mp"]["j_l"], EQS_L, VARS_L, scaled=False)
        out["condition_numbers_scaled_L_form"][st["state_id"]] = float(np.linalg.cond(js, 2))
        out["condition_numbers_unscaled_L_form"][st["state_id"]] = float(np.linalg.cond(ju, 2))
    s1 = states[0]
    x0 = {k: float(v) for k, v in s1["_mp"]["x"].items()}
    xp = {}
    for k, (op, val) in PERTURB.items():
        xp[k] = x0[k] * val if op == "mul" else x0[k] + val
    prm = s1["_mp"]["prm"]
    xpm = {k: mpf(repr(v)) for k, v in xp.items()}
    jp = jacobian_l(xpm, prm)
    rp = residual_l(xpm, prm)
    js = sp.csc_matrix(dense_matrix(jp, EQS_L, VARS_L, scaled=True))
    bs = -np.array([float(rp[row] / ROW_SCALE[row]) for row in EQS_L])
    lu = spla.splu(
        js,
        permc_spec="COLAMD",
        diag_pivot_thresh=1.0,
        options={"Equil": False, "SymmetricMode": False},
    )
    ds = lu.solve(bs)
    lin_res = np.max(np.abs(js @ ds - bs)) / (
        np.max(np.abs(js.toarray())) * np.max(np.abs(ds)) + np.max(np.abs(bs))
    )
    x1 = {k: xp[k] + float(COL_SCALE[k]) * ds[n] for n, k in enumerate(VARS_L)}
    prm_d = {
        "f": [float(v) for v in prm["f"]],
        "H_feed": float(prm["H_feed"]),
        "T_spec": float(prm["T_spec"]),
        "P_spec": float(prm["P_spec"]),
    }
    r1 = residual_l_dbl(x1, prm_d)
    affine = ["bal_A", "bal_B", "bal_C", "Vdef", "Ldef", "tspec", "pspec"]
    u = np.array(U_DIR_L)
    rec = lu.solve(js @ u)
    out["S1_perturbed_newton_step"] = {
        "x_pert": {k: repr(xp[k]) for k in VARS_L},
        "superlu": (
            "scipy.sparse.linalg.splu(permc_spec='COLAMD', diag_pivot_thresh=1.0, "
            "Equil=False, SymmetricMode=False) on D_r^-1 J D_c"
        ),
        "kappa2_scaled_at_x_pert": float(np.linalg.cond(js.toarray(), 2)),
        "scaled_linear_residual_inf": float(lin_res),
        "affine_rows_after_step_max_abs_over_scale": float(
            max(abs(r1[row]) / float(ROW_SCALE[row]) for row in affine)
        ),
        "recover_u_max_abs_error": float(np.max(np.abs(rec - u))),
        "step_scaled_inf_norm": float(np.max(np.abs(ds))),
    }
    return out


def second_order_probe_values(states: list[dict[str, Any]]) -> dict[str, Any]:
    s1 = states[0]
    xm, t, p = s1["_mp"]["x"], s1["_mp"]["x"]["T"], s1["_mp"]["x"]["P"]
    ka = exp(xm["lnK_A"])
    return {
        "state": "S1",
        "algebraic_only": {
            "d2 eq_A / d v_A d L": s20(mpf(1)),
            "d2 eq_A / d lnK_A^2": s20(-ka * xm["l_A"] * xm["V"]),
        },
        "callback_boundary": {
            "d2 kdef_A / dT^2": s20(-d2lnk_dt2(0, t, p)),
            "d2 kdef_A / dT dP": s20(-d2lnk_dtdp(0, t, p)),
            "d2 kdef_A / dP^2": s20(-d2lnk_dp2(0, t, p)),
            "d2 hdef_A / d l_A dT": s20(-CP),
            "d2 hdef_A / d l_A dP": s20(-V_LIQ[0]),
        },
        "I_form_mixed_via_first_derivative_only": {
            "d2 eq_A / dT d l_A": s20(-ka * xm["V"] * dlnk_dt(0, t, p)),
        },
        "I_form_pure_callback_second_order": {
            "d2 eq_A / dT^2": s20(
                -ka * xm["l_A"] * xm["V"] * (dlnk_dt(0, t, p) ** 2 + d2lnk_dt2(0, t, p))
            ),
        },
    }


def pattern_tables() -> dict[str, Any]:
    dummy = {k: mpf("0.37") for k in VARS_L}
    dummy["T"], dummy["P"] = mpf(350), mpf(120000)
    prm = {"f": [mpf(1)] * 3, "H_feed": mpf(0), "T_spec": mpf(350), "P_spec": mpf(120000)}
    jl = jacobian_l(dummy, prm)
    ji = jacobian_i({k: dummy[k] for k in VARS_I}, prm)

    def origin(row: str, col: str, form: str) -> str:
        if row.startswith("kdef") and col in ("T", "P"):
            return "callback:lnK"
        if row.startswith("hdef") and col in ("l_A", "l_B", "l_C", "T", "P"):
            return "callback:HL"
        if form == "I" and row.startswith("eq") and col in ("T", "P"):
            return "chain:lnK"
        if form == "I" and row == "energy" and col in ("l_A", "l_B", "l_C", "P"):
            return "chain:HL"
        if form == "I" and row == "energy" and col == "T":
            return "algebraic+chain:HL"
        return "algebraic"

    return {
        "L_form": {
            "variables": VARS_L,
            "equations": EQS_L,
            "nnz": len(jl),
            "entries": [{"row": a, "col": b, "origin": origin(a, b, "L")} for (a, b) in jl],
        },
        "I_form": {
            "variables": VARS_I,
            "equations": EQS_I,
            "nnz": len(ji),
            "entries": [{"row": a, "col": b, "origin": origin(a, b, "I")} for (a, b) in ji],
        },
    }


def stencil_domain_checks(states: list[dict[str, Any]]) -> list[str]:
    """Every point a registered FD stencil evaluates (A04, A07, A15 at S1-S5) must lie inside
    the closed SYN-001 domain, because both callback blocks raise a typed domain error outside
    it (specification §2.2, §3). Asserted so that a step can never again be chosen that would
    force a harness to drop the guard."""
    passed: list[str] = []
    for st in states:
        if st["state_id"] not in ("S1", "S2", "S3", "S4", "S5"):
            continue
        t, p = float(st["x_L"]["T"]), float(st["x_L"]["P"])
        du_t = float(COL_SCALE["T"]) * U_DIR_L[VARS_L.index("T")]
        du_p = float(COL_SCALE["P"]) * U_DIR_L[VARS_L.index("P")]
        points = [("A04 T", t + k * FD_H_T, p) for k in (-2, -1, 1, 2)] + [
            ("A04 P", t, p + k * FD_H_P) for k in (-2, -1, 1, 2)
        ]
        points += [("A07 T", t + k * FD_H_T, p) for k in (-2, -1, 1, 2)]
        points += [("A07 P", t, p + k * FD_H_P_HL) for k in (-2, -1, 1, 2)]
        points += [("A15", t + k * FD_EPS * du_t, p + k * FD_EPS * du_p) for k in (-2, -1, 1, 2)]
        for label, tt, pp in points:
            assert T_MIN <= tt <= T_MAX and P_MIN <= pp <= P_MAX, (
                f"{st['state_id']} {label}: stencil point (T={tt}, P={pp}) leaves the closed domain"
            )
        passed.append(f"{st['state_id']}: all A04/A07/A15 stencil points inside the closed domain")
    return passed


def distinctness_checks(states: list[dict[str, Any]]) -> list[str]:
    """Assert the accidental-zero and coincidence-free claims of the specification (§4.2, §5).

    Returns the list of checks passed; raises AssertionError naming the first failure, so the
    claims cannot regress silently when a state is edited.
    """
    by_id = {st["state_id"]: st for st in states}
    passed: list[str] = []
    for sid in ("S5", "S6"):
        for form in ("L", "I"):
            rows = {k: float(v) for k, v in by_id[sid][f"residual_{form}"].items()}
            zero = [k for k, v in rows.items() if v == 0.0]
            assert not zero, f"{sid} {form}-form residual rows exactly zero: {zero}"
            mags = sorted((abs(v), k) for k, v in rows.items())
            for (a, ka), (b, kb) in zip(mags, mags[1:], strict=False):
                assert a != b, f"{sid} {form}-form residual rows {ka} and {kb} coincide at |{a}|"
            passed.append(f"{sid} {form}-form: all residual rows nonzero, magnitudes distinct")
    for sid in ("S1", "S2", "S5", "S6"):
        for form in ("L", "I"):
            zero = [k for k, v in by_id[sid][f"jacobian_{form}"].items() if float(v) == 0.0]
            assert not zero, f"{sid} {form}-form Jacobian entries exactly zero: {zero}"
            passed.append(f"{sid} {form}-form: all Jacobian entries nonzero")
    expected_counts = {("S3", "L"): 10, ("S4", "L"): 15, ("S3", "I"): 12, ("S4", "I"): 13}
    for (sid, form), n in expected_counts.items():
        got = len(by_id[sid][f"numerically_zero_entries_{form}"])
        assert got == n, f"{sid} {form}-form numerically-zero count {got} != {n}"
        passed.append(f"{sid} {form}-form: {n} numerically-zero structural nonzeros")
    nz_union = set(by_id["S3"]["numerically_zero_entries_L"]) | set(
        by_id["S4"]["numerically_zero_entries_L"]
    )
    floor = min(
        abs(float(by_id[sid]["jacobian_L"][e])) for sid in ("S1", "S2", "S5") for e in nz_union
    )
    assert floor >= 1e-5, f"A11 nonzero floor violated: {floor}"
    passed.append(f"A11 floor: min |entry| over S1,S2,S5 of the S3/S4 zero sets = {floor:.3e}")
    nz_union_i = set(by_id["S3"]["numerically_zero_entries_I"]) | set(
        by_id["S4"]["numerically_zero_entries_I"]
    )
    floor_i = min(
        abs(float(by_id[sid]["jacobian_I"][e]))
        for sid in ("S1", "S2", "S5", "S6")
        for e in nz_union_i
    )
    assert floor_i >= 1e-6, f"A13 nonzero floor violated: {floor_i}"
    passed.append(
        f"A13 floor: min |entry| over S1,S2,S5,S6 of the I-form zero sets = {floor_i:.3e}"
    )
    for form, nnz in (("L", 60), ("I", 43)):
        for st in states:
            assert len(st[f"jacobian_{form}"]) == nnz, f"{st['state_id']} {form}-form nnz != {nnz}"
    passed.append("every state carries 60 L-form and 43 I-form entries")
    return passed


def schur_identity_check(states: list[dict[str, Any]]) -> dict[str, Any]:
    """A14: the Schur complement of the L-form over the lifted variables equals the I-form
    Jacobian exactly where the lifted variables satisfy their defining rows (S1-S4). At S5/S6
    the registered lifted values are deliberately inconsistent, so the identity does not hold;
    the discrepancy is recorded as the expected non-identity, not asserted."""
    lifted = [f"lnK_{c}" for c in COMP] + [f"hL_{c}" for c in COMP]
    defining = [f"kdef_{c}" for c in COMP] + [f"hdef_{c}" for c in COMP]
    out: dict[str, Any] = {}
    for st in states:
        jl, ji = st["_mp"]["j_l"], st["_mp"]["j_i"]
        worst = mpf(0)
        for row in EQS_I:
            for col in VARS_I:
                direct = jl.get((row, col), mpf(0))
                correction = sum(
                    jl.get((row, y), mpf(0)) * jl.get((yd, col), mpf(0))
                    for y, yd in zip(lifted, defining, strict=True)
                )
                schur = direct - correction
                expect = ji.get((row, col), mpf(0))
                rel = abs(schur - expect) / (
                    abs(expect) + mpf("1e-14") * ROW_SCALE[row] / COL_SCALE[col]
                )
                worst = max(worst, rel)
        consistent = st["state_id"] in ("S1", "S2", "S3", "S4")
        if consistent:
            assert worst <= mpf("1e-13"), f"A14 identity fails at {st['state_id']}: {worst}"
        out[st["state_id"]] = {
            "lifted_consistent": consistent,
            "max_relative_discrepancy": s20(worst, 6),
            "verdict": "identity holds (asserted <= 1e-13)"
            if consistent
            else "non-identity expected",
        }
    return out


def build() -> dict[str, Any]:
    states = registered_states()
    checks_passed = distinctness_checks(states)
    checks_passed += stencil_domain_checks(states)
    schur = schur_identity_check(states)
    floors = measure_floors(states)
    lin = linear_solve_evidence(states)
    so = second_order_probe_values(states)
    pats = pattern_tables()
    public_states = [{k: v for k, v in st.items() if k != "_mp"} for st in states]
    return {
        "schema_version": 1,
        "generated_by": (
            "Fable 5.1, docs/derivations/scripts/p02_reference.py, mpmath 1.3.0 at 40 digits, "
            "from plan §3.1 definitions and SYN-001 derivation §3 closed forms only; "
            "no backend, no oracle import"
        ),
        "specification": "docs/derivations/P02-composition-spec.md",
        "precision_note": (
            "Values are 20-significant-digit decimal strings. State vectors x_L/x_I are exact "
            "Python double reprs and must be used verbatim; expected values are the closed "
            "forms evaluated at those exact doubles."
        ),
        "scales": {
            "column": {k: s20(v, 6) for k, v in COL_SCALE.items()},
            "row": {k: s20(v, 6) for k, v in ROW_SCALE.items()},
        },
        "patterns": pats,
        "states": public_states,
        "directions": {"u_L": U_DIR_L, "v_L": V_DIR_L, "u_I": U_DIR_I, "v_I": V_DIR_I},
        "distinctness_checks_passed": checks_passed,
        "schur_identity_check": schur,
        "fd_floors_measured": floors,
        "linear_solve": lin,
        "second_order_probe_expected": so,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="print the key numbers and floors")
    parser.add_argument("--emit", metavar="PATH", help="write reference_values.yaml to PATH")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit PATH")
    ref = build()
    if args.check:
        for st in ref["states"]:
            print(
                st["state_id"],
                st["oracle_phase_state"],
                "on_solution" if st["on_solution"] else "off_solution",
            )
            print("  K", st["K"])
            print("  dlnK/dT", st["dlnK_dT_per_K"])
            print("  dlnK/dP", st["dlnK_dP_per_Pa"])
            print("  x_L", st["x_L"])
            print("  max |r_L| (unscaled)", max(abs(float(v)) for v in st["residual_L"].values()))
            print("  numerically zero L entries", st["numerically_zero_entries_L"])
        print(
            "patterns nnz L/I", ref["patterns"]["L_form"]["nnz"], ref["patterns"]["I_form"]["nnz"]
        )
        for line in ref["distinctness_checks_passed"]:
            print("distinctness check passed:", line)
        print(
            yaml.safe_dump({"schur_identity_check": ref["schur_identity_check"]}, sort_keys=False)
        )
        print(yaml.safe_dump(ref["fd_floors_measured"], sort_keys=False))
        print(yaml.safe_dump(ref["linear_solve"], sort_keys=False))
        print(yaml.safe_dump(ref["second_order_probe_expected"], sort_keys=False))
    if args.emit:
        with open(args.emit, "w", encoding="utf-8") as fh:
            fh.write(
                "# Generated by docs/derivations/scripts/p02_reference.py — do not edit by hand.\n"
            )
            yaml.safe_dump(ref, fh, sort_keys=False, width=200, allow_unicode=True)
        print(f"wrote {args.emit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
