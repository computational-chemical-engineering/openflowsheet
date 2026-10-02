"""Closed-form reference generator for T05b: near-pure PH, one flowing component on the EO path,
and dormant outlets -- the PH-type lifted ones and, since the amendment of 2026-09-25 (spec
§7.6-§7.10), the non-lifted ones (ADR 0012; ``docs/derivations/T05b-limitations-spec.md``).

A sibling of ``t05_reference.py``, whose SYN-001 thermodynamics, row builders and 40-digit PH
solve it imports (as that script imports ``syn001_reference.py``). It imports nothing from
``process_runtime`` or ``benchmarks``: the numbers it emits are the expectations the T05b tests
judge the implementation against, so they must not come from it. It does not modify T05's
registered file; one claim re-hashes that file and requires it unchanged.

Three classes of value are emitted and labelled as such in the YAML:

* ``closed_form`` -- expectations, computed with mpmath at 40 significant digits and written to 20.
* ``generator_claims`` -- every statement the specification makes about its own numbers,
  re-derived by ``--check``. The script refuses to emit when one fails.
* ``measured`` -- the same kernels rerun in 53-bit arithmetic (a transcription of the published
  algorithms, never the implementation), used only to argue tolerances, route predictions and
  the residual limitation's boundary. Never an expectation.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/t05b_reference.py --check
    python docs/derivations/scripts/t05b_reference.py --emit benchmarks/t05b/reference_values.yaml

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
from mpmath import mp, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t05_reference as t05  # noqa: E402  (SYN-001 thermodynamics, T05 rows, 40-digit PH solve)

mp.dps = 40

ROOT = Path(__file__).resolve().parents[3]
T05_YAML = ROOT / "benchmarks" / "t05" / "reference_values.yaml"
#: T05 spec header: the registered SHA-256 of T05's reference file, which T05b must not move.
T05_YAML_SHA256 = "af4a543f8dab3d95c32764117be00afbc9e8d49478998e8538a1daf359385a6a"

TH, THF, NC, COMPONENTS = t05.TH, t05.THF, t05.NC, t05.COMPONENTS
T_MIN, T_MAX, P_R = t05.T_MIN, t05.T_MAX, t05.P_R

# ============================================================================================
# 1. Registered constants (ADR 0001 D6, K04 §5.1-§5.2; nothing new is registered here)
# ============================================================================================

TAU_FLOW = t05.TOL["molar_flow"]  # 3.1e-8 mol/s
TAU_EQ = t05.TOL["molar_flow_squared"]  # 9.3e-8 (mol/s)^2
TAU_E = t05.TOL["heat_rate"]  # 1.01e-3 W
TAU_T = t05.TOL["temperature"]  # 1e-6 K
TAU_P = t05.TOL["pressure"]  # 1e-2 Pa
EPS_ADM = mpf("1e-12")  # K03 §8.2
#: T02 §6.4's per-kind allowances for converged coupled states (ten times each residual rule).
ALLOW = {"flow": mpf("3.1e-7"), "T": mpf("1e-5"), "P": mpf("0.1"), "duty": mpf("1e-2")}
#: The spec's B01 tolerances for the kernel grid (spec §13): temperature, total vapour flow,
#: and each flowing component's vapour fraction q_i = v_i / n_i.
GRID_TOL = {"T": mpf("1e-6"), "V": mpf("1e-7"), "q": mpf("1e-6")}
#: Spec §13: an accepted answer meets the energy row to tau_E, which fixes the total vapour
#: flow to tau_E / min_i dh_i (dh_i >= 24 990 J/mol on the domain, T05 §4.2); the traces' split
#: follows the vapour fraction through K (equilibrium row), so their share of the error is second
#: order (the 1.001 factor). This is the bound B01's V tolerance covers.
GRID_ACCEPTANCE_BOUND_V = TAU_E / mpf(24990) * mpf("1.001")
#: Spec §5: the band route stops bisecting beta at this bracket width (2^-60).
BETA_WIDTH_FLOOR = mpf(2) ** -60
MAX_EVALUATIONS = 200
MAX_BAND_EVALUATIONS = 64
SCALE = t05.SCALE

# Case parameters (spec §12).
EPSILONS = (mpf("1e-12"), mpf("1e-9"), mpf("1e-7"), mpf("1e-6"))
PHIS = (mpf("0.1"), mpf("0.3"), mpf("0.5"), mpf("0.7"), mpf("0.9"))
H_L_PURE_B = mpf(12000)  # 2 mol/s of B as liquid at T_sat = 360 K, P_r: 2 c_p 60 K
LATENT_2B = mpf(60000)  # 2 L_B
JUMP_T = mpf(360)
JUMP_J = mpf(1000)  # J/mol added to every vapour enthalpy above JUMP_T (the JUMP double)
BIAS_BETA = mpf("1e-5")  # added to the vapour fraction of every two-phase flash (BIASED double)

Vec = tuple[Any, ...]


def s(value: Any, digits: int = 20) -> Any:
    return t05.s(value, digits)


def sv(values: Sequence[Any]) -> list[Any]:
    return [s(v) for v in values]


# ============================================================================================
# 2. The saturation band at 40 digits (spec §4)
# ============================================================================================


def flowing(n: Sequence[Any]) -> list[int]:
    return [i for i in range(NC) if n[i] > 0]


def g_band(n: Sequence[Any], p: Any, beta: Any, t: Any, th: t05.Thermo = TH) -> Any:
    """Rachford-Rice in temperature form: sum over flowing i of z_i (K_i - 1)/(1 + b(K_i - 1))."""
    total = sum(n, mpf(0))
    out = mpf(0)
    for i in flowing(n):
        k = th.k(i, t, p)
        out += (n[i] / total) * (k - 1) / (1 + beta * (k - 1))
    return out


def bisect_increasing(fn: Callable[[Any], Any], lo: Any, hi: Any, iterations: int) -> Any:
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if fn(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def band_t(n: Sequence[Any], p: Any, beta: Any, th: t05.Thermo = TH) -> Any:
    """T(beta) on the domain, or 'below'/'above' when the root lies outside it (spec §4.1)."""
    if g_band(n, p, beta, T_MIN, th) > 0:
        return "below"
    if g_band(n, p, beta, T_MAX, th) < 0:
        return "above"
    return bisect_increasing(lambda t: g_band(n, p, beta, t, th), T_MIN, T_MAX, 140)


def band_split(n: Sequence[Any], p: Any, beta: Any, t: Any) -> tuple[Vec, Vec]:
    v, liq = [], []
    for i in range(NC):
        if n[i] == 0:
            v.append(mpf(0))
            liq.append(mpf(0))
            continue
        k = TH.k(i, t, p)
        d = 1 + beta * (k - 1)
        v.append(n[i] * beta * k / d)
        liq.append(n[i] * (1 - beta) / d)
    return tuple(v), tuple(liq)


def band_h(n: Sequence[Any], p: Any, beta: Any) -> Any:
    t = band_t(n, p, beta)
    if isinstance(t, str):
        return t
    v, liq = band_split(n, p, beta, t)
    return t05.h_flow(v, t, p, "V") + t05.h_flow(liq, t, p, "L")


def band_ends(n: Sequence[Any], p: Any) -> tuple[Any, Any]:
    return band_t(n, p, mpf(0)), band_t(n, p, mpf(1))


def band_solve(n: Sequence[Any], p: Any, target: Any) -> dict[str, Any]:
    """The PH closure inside the band, parametrised by the vapour fraction (spec §4.3)."""

    def f(beta: Any) -> Any:
        h = band_h(n, p, beta)
        if h == "below":
            return mpf(-1)
        if h == "above":
            return mpf(1)
        return h - target

    beta = bisect_increasing(f, mpf(0), mpf(1), 140)
    t = band_t(n, p, beta)
    v, liq = band_split(n, p, beta, t)
    total = sum(n, mpf(0))
    return {
        "beta": sum(v, mpf(0)) / total,
        "beta_parameter": beta,
        "T": t,
        "v": v,
        "l": liq,
        "V": sum(v, mpf(0)),
    }


def degeneracy_distance(n: Sequence[Any], t: Any, p: Any) -> Any:
    """max(|T - T_b|, |T - T_d|); infinite when either band end is outside the domain (§4.4)."""
    tb, td = band_ends(n, p)
    if isinstance(tb, str) or isinstance(td, str):
        return mp.inf
    return max(abs(t - tb), abs(t - td))


def rows_at(n: Sequence[Any], t: Any, p: Any, v: Sequence[Any], liq: Sequence[Any], target: Any):
    """The PH closure's rows at a split (spec §5.3): material, equilibrium, energy."""
    vt, lt = sum(v, mpf(0)), sum(liq, mpf(0))
    material = [v[i] + liq[i] - n[i] for i in range(NC)]
    equilibrium = [v[i] * lt - TH.k(i, t, p) * liq[i] * vt for i in range(NC)]
    energy = t05.h_flow(v, t, p, "V") + t05.h_flow(liq, t, p, "L") - target
    return material, equilibrium, energy


# ============================================================================================
# 3. 53-bit transcriptions (measured class only): the kernel's routes, the provider's flash
# ============================================================================================


def f_bracketed_root(fn: Callable[[float], float], lo: float, hi: float, budget: int):
    """The kernel's bisection rule (T05 spec §4.4 step 4): adjacent doubles or an exact zero;
    the end with the smaller |f|, the lower one on a tie. Returns (point, value, lo, hi, n)."""
    f_lo, f_hi = fn(lo), fn(hi)
    count = 2
    if f_lo == 0.0:
        return lo, f_lo, lo, hi, count
    if f_hi == 0.0:
        return hi, f_hi, lo, hi, count
    while True:
        mid = 0.5 * (lo + hi)
        if not lo < mid < hi or count >= budget:
            break
        f_mid = fn(mid)
        count += 1
        if f_mid == 0.0:
            return mid, f_mid, lo, hi, count
        if f_mid < 0.0:
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid
    if abs(f_hi) < abs(f_lo):
        return hi, f_hi, lo, hi, count
    return lo, f_lo, lo, hi, count


def f_rows(n, t, p, v, liq, target, thermo=THF):
    vt, lt = sum(v), sum(liq)
    material = max(abs(v[i] + liq[i] - n[i]) for i in range(NC))
    equilibrium = max(abs(v[i] * lt - thermo.k(i, t, p) * liq[i] * vt) for i in range(NC))
    energy = abs(t05.float_h(v, t, p, "V") + t05.float_h(liq, t, p, "L") - target)
    return material, equilibrium, energy


def f_accepts(rows) -> bool:
    material, equilibrium, energy = rows
    return material <= float(TAU_FLOW) and equilibrium <= float(TAU_EQ) and energy <= float(TAU_E)


def f_temperature_route(n, p, target, split_fn=t05.float_tp_split):
    """The bracket route in doubles on a TP flash `split_fn` (the provider's by default)."""

    def f(t: float) -> float:
        sp = split_fn(n, t, p)
        return t05.float_h(sp["v"], t, p, "V") + t05.float_h(sp["l"], t, p, "L") - target

    t, value, _, _, _ = f_bracketed_root(f, 280.0, 440.0, MAX_EVALUATIONS)
    sp = split_fn(n, t, p)
    rows = f_rows(n, t, p, sp["v"], sp["l"], target)
    return {"T": t, "v": sp["v"], "l": sp["l"], "f": value, "rows": rows, "ok": f_accepts(rows)}


def f_g(n, p, beta, t):
    total = sum(n)
    out = 0.0
    for i in range(NC):
        if n[i] > 0.0:
            k = THF.k(i, t, p)
            out += (n[i] / total) * (k - 1.0) / (1.0 + beta * (k - 1.0))
    return out


def f_band_state(n, p, beta):
    if f_g(n, p, beta, 280.0) > 0.0:
        return "below"
    if f_g(n, p, beta, 440.0) < 0.0:
        return "above"
    t, _, _, _, _ = f_bracketed_root(lambda x: f_g(n, p, beta, x), 280.0, 440.0, MAX_EVALUATIONS)
    v, liq = [], []
    for i in range(NC):
        if n[i] == 0.0:
            v.append(0.0)
            liq.append(0.0)
            continue
        k = THF.k(i, t, p)
        d = 1.0 + beta * (k - 1.0)
        v.append(n[i] * beta * k / d)
        liq.append(n[i] * (1.0 - beta) / d)
    return t, v, liq


def f_band_route(n, p, target):
    """The band route in doubles (spec §5.2): bisection on beta with the sign oracle."""

    def big_f(beta):
        st = f_band_state(n, p, beta)
        if st == "below":
            return -math.inf, None
        if st == "above":
            return math.inf, None
        t, v, liq = st
        return t05.float_h(v, t, p, "V") + t05.float_h(liq, t, p, "L") - target, (t, v, liq)

    lo, hi = 0.0, 1.0
    f_lo, s_lo = big_f(lo)
    f_hi, s_hi = big_f(hi)
    if f_lo > 0.0 or f_hi < 0.0:
        return None
    floor = float(BETA_WIDTH_FLOOR)
    count = 2
    while True:
        mid = 0.5 * (lo + hi)
        if not lo < mid < hi or hi - lo <= floor or count >= MAX_BAND_EVALUATIONS:
            break
        f_mid, s_mid = big_f(mid)
        count += 1
        if f_mid == 0.0:
            lo, f_lo, s_lo = mid, f_mid, s_mid
            hi, f_hi, s_hi = mid, f_mid, s_mid
            break
        if f_mid < 0.0:
            lo, f_lo, s_lo = mid, f_mid, s_mid
        else:
            hi, f_hi, s_hi = mid, f_mid, s_mid
    beta, value, state = (hi, f_hi, s_hi) if abs(f_hi) < abs(f_lo) else (lo, f_lo, s_lo)
    t, v, liq = state
    rows = f_rows(n, t, p, v, liq, target)
    return {
        "beta": beta,
        "T": t,
        "v": v,
        "l": liq,
        "f": value,
        "rows": rows,
        "ok": f_accepts(rows),
        "evaluations": count,
    }


def f_fresh_enthalpy(n, t, p) -> tuple[float, float]:
    sp = t05.float_tp_split(n, t, p)
    return t05.float_h(sp["v"], t, p, "V") + t05.float_h(sp["l"], t, p, "L"), sum(sp["v"])


# ============================================================================================
# 4. The kernel grid (replaces T05 A29) and the two provider test doubles
# ============================================================================================


def grid_flows(which: str, eps: Any) -> Vec:
    return (eps, mpf(2), mpf(0)) if which == "A" else (mpf(0), mpf(2), eps)


def kernel_grid() -> dict[str, dict[str, Any]]:
    grid: dict[str, dict[str, Any]] = {}
    for which in ("A", "C"):
        for eps in EPSILONS:
            n = grid_flows(which, eps)
            tb, td = band_ends(n, P_R)
            for phi in PHIS:
                target = H_L_PURE_B + phi * LATENT_2B
                ref = band_solve(n, P_R, target)
                q = [ref["v"][i] / n[i] if n[i] > 0 else None for i in range(NC)]
                nf = tuple(float(x) for x in n)
                tr = f_temperature_route(nf, 1e5, float(target))
                br = f_band_route(nf, 1e5, float(target))
                route = "bracket" if tr["ok"] else "band"
                chosen = tr if tr["ok"] else br
                case_id = f"NPK-{which}-{mp.nstr(eps, 1)}-{mp.nstr(phi, 1)}"
                grid[case_id] = {
                    "n": n,
                    "P": P_R,
                    "target": target,
                    "phi": phi,
                    "eps": eps,
                    "T_bubble": tb,
                    "T_dew": td,
                    "ref": ref,
                    "q": q,
                    "t_route": tr,
                    "band_route": br,
                    "route_53": route,
                    "chosen": chosen,
                }
    return grid


def jump_case() -> dict[str, Any]:
    """The JUMP double (spec §12.2): every vapour enthalpy + J above T_J. The target is the
    middle of the resulting jump of H_TP at T_J for (1, 1, 1) at P_r."""
    n = (mpf(1), mpf(1), mpf(1))
    split = t05.tp_split(n, JUMP_T, P_R)
    below = t05.h_split(split, JUMP_T, P_R)
    jump = JUMP_J * sum(split["v"], mpf(0))
    return {
        "n": n,
        "P": P_R,
        "T_J": JUMP_T,
        "J": JUMP_J,
        "V_at_T_J": sum(split["v"], mpf(0)),
        "H_below": below,
        "jump_W": jump,
        "target": below + jump / 2,
        "margin_W": jump / 2,
    }


def biased_split(n, t, p):
    """The BIASED double's flash (spec §12.2): the provider's split with beta + 1e-6 when the
    provider says two-phase; single-phase answers are the provider's (bias BIAS_BETA)."""
    sp = t05.float_tp_split(n, t, p)
    total = sum(n)
    vt = sum(sp["v"])
    if vt == 0.0 or vt == total:
        return sp
    beta = vt / total + float(BIAS_BETA)
    k = [THF.k(i, t, p) for i in range(NC)]
    z = [x / total for x in n]
    x = [z[i] / (1.0 + beta * (k[i] - 1.0)) for i in range(NC)]
    v = tuple(beta * total * k[i] * x[i] for i in range(NC))
    return {"v": v, "l": tuple(n[i] - v[i] for i in range(NC))}


def biased_case() -> dict[str, Any]:
    """PHF-1's inputs (T05 §5.3) through the BIASED double's temperature route in doubles."""
    n = (1.0, 1.0, 1.0)
    target = float(0 + 50000)  # (1,1,1) liquid at 300 K, P_r carries zero enthalpy; Q = 50 000 W
    tr = f_temperature_route(n, 1e5, target, split_fn=biased_split)
    br = f_band_route(n, 1e5, target)
    ref = t05.ph_solve((mpf(1), mpf(1), mpf(1)), P_R, mpf(50000))
    return {"t_route": tr, "band_route": br, "ref_T": ref["T"], "ref_split": ref["split"]}


# ============================================================================================
# 5. The phase-contract facts: the PH regime of a trial state (spec §6)
# ============================================================================================


def rho_tp(n: Sequence[Any], t: Any, p: Any) -> str:
    return t05.tp_split(n, t, p)["regime"]


def rho_ph(n: Sequence[Any], p: Any, h: Any) -> dict[str, Any]:
    """The regime of the PH closure's answer at the split's own enthalpy (spec §6.2)."""
    result = t05.ph_solve(n, p, h)
    return {"regime": result["split"]["regime"], "T": result["T"], "beta": result["split"]["beta"]}


# ============================================================================================
# 6. The EO cases: single component (SC), near-pure (NP), dormant (DZ)
# ============================================================================================


def pure_b(v: Any) -> Vec:
    return (mpf(0), mpf(v), mpf(0))


def lever_root(n: Vec, p: Any, target: Any) -> dict[str, Any]:
    r = t05.ph_solve(n, p, target)
    assert r["route"] == "saturation", r
    return r


def sc_cases() -> dict[str, Any]:
    out: dict[str, Any] = {}
    # SC-1: T05 A30's P3 -- pure B through a valve, flashing to the jump.
    feed = t05.stream(pure_b(2), 370, 180000)
    h_in = t05.h_flow(feed["n"], feed["T"], feed["P"], "L")
    r1 = lever_root(feed["n"], P_R, h_in)
    out["SC-1"] = {"feed": feed, "H_in": h_in, "valve": r1}
    # SC-2: T05 A30's P4 -- PHF-6's inputs as a flowsheet.
    feed2 = t05.stream(pure_b(2), 300, P_R)
    r2 = lever_root(feed2["n"], P_R, t05.h_flow(feed2["n"], 300, P_R, "L") + 42000)
    out["SC-2"] = {"feed": feed2, "Q": mpf(42000), "phf": r2}
    # SC-3: the valve's outlet feeds a PH flash (lifted inlet) with Q = -1000 W.
    q3 = mpf(-1000)
    r3 = lever_root(feed["n"], P_R, h_in + q3)
    # The traversal's start of U-PHF reads the lifted inlet by (n, T, P) (T05 §5.2 (3)): at
    # T_sat the provider's flash says LIQUID, so it sees the liquid enthalpy.
    h_start = t05.h_tp(feed["n"], r1["T"], P_R)
    start = t05.ph_solve(feed["n"], P_R, h_start + q3)
    # The LIQUID attempt's first full step lands on the liquid-form root of the energy row.
    t_liq = t05.bisect(
        lambda t: t05.h_flow(feed["n"], t, P_R, "L") - (h_in + q3), T_MIN, T_MAX, 200
    )
    h_trial = t05.h_flow(feed["n"], t_liq, P_R, "L")
    out["SC-3"] = {
        "feed": feed,
        "H_in": h_in,
        "Q": q3,
        "valve": r1,
        "phf": r3,
        "start_H_in_read": h_start,
        "start_phf": start,
        "trial_T": t_liq,
        "trial_rho_TP": rho_tp(feed["n"], t_liq, P_R),
        "trial_rho_PH": rho_ph(feed["n"], P_R, h_trial),
    }
    # SC-4: products of a pure-B PH flash to declared-phase consumers.
    q1, q2, p_pump, eta = mpf(42000), mpf(-15000), mpf(150000), mpf("0.75")
    ra = lever_root(pure_b(2), P_R, q1)
    vap = t05.stream(ra["split"]["v"], ra["T"], P_R)
    liq = t05.stream(ra["split"]["l"], ra["T"], P_R)
    h_vap = t05.h_flow(vap["n"], vap["T"], P_R, "V")
    rb = lever_root(vap["n"], P_R, h_vap + q2)
    pump = t05.eval_pump(liq, p_pump, eta)
    out["SC-4"] = {
        "feed": feed2,
        "Q1": q1,
        "Q2": q2,
        "P_pump": p_pump,
        "eta": eta,
        "phf1": ra,
        "phf2": rb,
        "pump": pump,
        "phf2_inlet_tp_gap_K": t05.admissibility(vap["n"], vap["T"], P_R, "V")["equivalent_K"],
        "phf2_inlet_tp_regime": rho_tp(vap["n"], vap["T"], P_R),
        "phf2_inlet_degeneracy_K": degeneracy_distance(vap["n"], vap["T"], P_R),
        "pump_inlet_tp_gap_K": t05.admissibility(liq["n"], liq["T"], P_R, "L")["equivalent_K"],
        "pump_outlet_degeneracy_K": degeneracy_distance(
            pump["outlet"]["n"], pump["outlet"]["T"], p_pump
        ),
    }
    return out


NP_SPECS = {
    # id: (flows, Q_W, why)
    "NP-1": ((mpf("1e-12"), mpf(2), mpf(0)), mpf(30000), "light trace, degenerate by 5 decades"),
    "NP-2": ((mpf(0), mpf(2), mpf("1e-8")), mpf(54000), "heavy trace, degenerate by a factor 3.6"),
    "NP-3": ((mpf("1e-5"), mpf(2), mpf(0)), mpf(30000), "resolved: judged by the fresh flash"),
    "NP-G": ((mpf(0), mpf(2), mpf("1.5e-7")), mpf(30000), "the residual limitation (F9's band)"),
}


def np_cases() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cid, (n, q, why) in NP_SPECS.items():
        ref = band_solve(n, P_R, q)  # feed at 300 K, P_r, liquid carries zero enthalpy
        cross = t05.ph_solve(n, P_R, q)
        tb, td = band_ends(n, P_R)
        dist = degeneracy_distance(n, ref["T"], P_R)
        nf = tuple(float(x) for x in n)
        tf = float(ref["T"])
        vf = tuple(float(x) for x in ref["v"])
        lf = tuple(float(x) for x in ref["l"])
        h_v, _ = f_fresh_enthalpy(vf, tf, 1e5)
        h_l, _ = f_fresh_enthalpy(lf, tf, 1e5)
        _, v_feed = f_fresh_enthalpy(nf, tf, 1e5)
        tr = f_temperature_route(nf, 1e5, float(q))
        out[cid] = {
            "t_route_53": tr,
            "why": why,
            "n": n,
            "Q": q,
            "ref": ref,
            "cross_T": cross["T"],
            "cross_v": cross["split"]["v"],
            "T_bubble": tb,
            "T_dew": td,
            "width": td - tb,
            "degeneracy_K": dist,
            "degenerate": bool(dist <= TAU_T),
            "fresh_products_energy_error_W": h_v + h_l - float(q),
            "fresh_feed_V_error": v_feed - sum(vf),
        }
    return out


# -- the dormant (ZERO_FLOW) systems ------------------------------------------------------------


def feed_rows(x, u, s_, n, t, p) -> t05.Rows:
    rows: t05.Rows = {}
    for i, c in enumerate(COMPONENTS):
        rows[t05.rid(u, "FEED-n", c)] = ("molar_flow", [x[t05.fid(s_, c)], -n[i]])
    rows[t05.rid(u, "FEED-T")] = ("temperature", [x[t05.tid(s_)], -t])
    rows[t05.rid(u, "FEED-P")] = ("pressure", [x[t05.pid(s_)], -p])
    return rows


def heater_rows(th, x, u, si, so, t_spec, dp=None) -> t05.Rows:
    """K02's `syn001.tp_heater` rows (structure as `heater.py`), declared-liquid inlet."""
    dp = mpf(0) if dp is None else dp
    rows: t05.Rows = {}
    for c in COMPONENTS:
        rows[t05.rid(u, "HEAT-mole", c)] = ("molar_flow", [x[t05.fid(si, c)], -x[t05.fid(so, c)]])
    rows[t05.rid(u, "HEAT-T")] = ("temperature", [x[t05.tid(so)], -t_spec])
    rows[t05.rid(u, "HEAT-pressure")] = (
        "pressure",
        [x[t05.pid(so)], -x[t05.pid(si)], dp],
    )
    rows[t05.rid(u, "HEAT-duty")] = (
        "heat_rate",
        [
            x[t05.qid(u)],
            *t05.stream_enthalpy_terms(th, x, si, "L", 1),
            *t05.stream_enthalpy_terms(th, x, so, "lifted", -1),
        ],
    )
    rows.update(t05.lifted_rows(th, x, u, "HEAT-equilibrium", so))
    return rows


def splitter_rows(x, u, si, rec, pur, r) -> t05.Rows:
    rows: t05.Rows = {}
    for c in COMPONENTS:
        rows[t05.rid(u, "SPLIT-recycle", c)] = (
            "molar_flow",
            [x[t05.fid(rec, c)], -(r * x[t05.fid(si, c)])],
        )
        rows[t05.rid(u, "SPLIT-purge", c)] = (
            "molar_flow",
            [x[t05.fid(pur, c)], -((1 - r) * x[t05.fid(si, c)])],
        )
    for port, st in (("recycle", rec), ("purge", pur)):
        rows[t05.rid(u, "SPLIT-T", port)] = ("temperature", [x[t05.tid(st)], -x[t05.tid(si)]])
        rows[t05.rid(u, "SPLIT-P", port)] = ("pressure", [x[t05.pid(st)], -x[t05.pid(si)]])
    return rows


def label_row(x, u, t_out, t_label) -> t05.Rows:
    return {f"{u}:zero-flow-label": ("temperature", [x[t_out], -x[t_label]])}


def column_kind(column: str) -> str:
    if column.endswith(".T"):
        return "temperature"
    if column.endswith(".P"):
        return "pressure"
    if column.endswith(".Q") or column.endswith(".W"):
        return "heat_rate"
    return "molar_flow"


class System:
    """A mini-flowsheet's rows as one function of its columns, for Jacobians at 40 digits."""

    def __init__(self, builder: Callable[[Mapping[str, Any]], t05.Rows], columns: Sequence[str]):
        self.builder = builder
        self.columns = tuple(columns)

    def evaluate(self, state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        x = {k: t05.Dual(mpf(state[k]), {k: mpf(1)}) for k in self.columns}
        out = {}
        for row, (kind, terms) in self.builder(x).items():
            total: Any = mpf(0)
            for term in terms:
                total = total + term
            value = total.v if isinstance(total, t05.Dual) else total
            jac = dict(total.d) if isinstance(total, t05.Dual) else {}
            out[row] = {"kind": kind, "value": value, "jac": jac}
        return out


def scaled_matrix(evaluated, rows, cols) -> Any:
    m = mp.matrix(len(rows), len(cols))
    for a, row in enumerate(rows):
        e = evaluated[row]
        rs = SCALE[e["kind"]]
        for b, col in enumerate(cols):
            m[a, b] = e["jac"].get(col, mpf(0)) * SCALE[column_kind(col)] / rs
    return m


def rank_and_rcond(m) -> tuple[int, Any]:
    sigma = mp.svd_r(m, compute_uv=False)
    rank = sum(1 for sv_ in sigma if sv_ > mpf("1e-25"))
    if rank < min(m.rows, m.cols):
        return rank, mpf(0)
    inv = m**-1
    return rank, 1 / (mp.mnorm(m, 1) * mp.mnorm(inv, 1))


def dormant_state(streams: Mapping[str, Mapping[str, Any]], owned: Mapping[str, Any]) -> dict:
    x: dict[str, Any] = {}
    for sname, st in streams.items():
        for i, c in enumerate(COMPONENTS):
            x[t05.fid(sname, c)] = st["n"][i]
        x[t05.tid(sname)] = st["T"]
        x[t05.pid(sname)] = st["P"]
        if st.get("lifted"):
            for i, c in enumerate(COMPONENTS):
                x[t05.vid(sname, c)] = st["v"][i]
                x[t05.lid(sname, c)] = st["l"][i]
            x[t05.vtot(sname)] = sum(st["v"], mpf(0))
            x[t05.ltot(sname)] = sum(st["l"], mpf(0))
    x.update(owned)
    return x


def zero_flow_form(split: Mapping[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Spec §7.2: (pinned columns, dropped rows, added rows) of one split in ZERO_FLOW."""
    u, style = split["unit"], split["style"]
    if style == "outlet":
        so = split["stream"]
        pinned = [
            *(t05.vid(so, c) for c in COMPONENTS),
            *(t05.lid(so, c) for c in COMPONENTS),
            t05.vtot(so),
            t05.ltot(so),
        ]
        dropped = [
            *(t05.rid(u, split["equilibrium"], c) for c in COMPONENTS),
            *(t05.rid(u, "split", c) for c in COMPONENTS),
            t05.rid(u, "Vdef"),
            t05.rid(u, "Ldef"),
        ]
    else:
        sv_, sl = split["vapor"], split["liquid"]
        pinned = [
            *(t05.fid(sv_, c) for c in COMPONENTS),
            *(t05.fid(sl, c) for c in COMPONENTS),
            t05.ntot(sv_),
            t05.ntot(sl),
        ]
        dropped = [
            *(t05.rid(u, split["equilibrium"], c) for c in COMPONENTS),
            *(t05.rid(u, split["mole"], c) for c in COMPONENTS),
            t05.rid(u, "Ndef", "vapor"),
            t05.rid(u, "Ndef", "liquid"),
        ]
    added: list[str] = []
    if split["closure"] == "PH":
        dropped.append(split["energy_row"])
        added.append(f"{u}:zero-flow-label")
    return pinned, dropped, added


def dz_cases() -> dict[str, Any]:
    th = TH
    zero = t05.zeros()
    t330 = mpf(330)
    out: dict[str, Any] = {}

    def run(cid, builder, columns, state, split, label, extra=None):
        system = System(builder, columns)
        ev = system.evaluate(state)
        # The declaration's rows: every compiled row, and never the regime's label row.
        rows = [r for r in ev if not r.endswith(":zero-flow-label")]
        full = scaled_matrix(ev, rows, list(columns))
        full_rank, _ = rank_and_rcond(full)
        zero_rows = [r for r in rows if all(v == 0 for v in ev[r]["jac"].values())]
        pinned, dropped, added = zero_flow_form(split)
        zrows = [r for r in rows if r not in dropped] + added
        zcols = [c for c in columns if c not in pinned]
        zmat = scaled_matrix(ev, zrows, zcols)
        z_rank, z_rcond = rank_and_rcond(zmat)
        t_out = label["T_out"] if label is not None else None
        t_out_rows = (
            sorted(r for r in rows if ev[r]["jac"].get(t_out, 0) != 0)
            if t_out is not None
            else None
        )
        out[cid] = {
            "full_form_T_out_rows": t_out_rows,
            "columns": list(columns),
            "rows": rows,
            "full_dimension": len(columns),
            "full_rank": full_rank,
            "identically_zero_rows": zero_rows,
            "zero_flow_rows": zrows,
            "zero_flow_columns": zcols,
            "zero_flow_rank": z_rank,
            "zero_flow_rcond1": z_rcond,
            "residual_max": max(abs(ev[r]["value"]) for r in rows if r in ev),
            "label": label,
            "state": state,
            "split_unit": split["unit"],
            **(extra or {}),
        }

    # DZ-1: W0.8's valve.
    streams = {
        "S1": {"n": zero, "T": t330, "P": P_R},
        "S2": {"n": zero, "T": t330, "P": mpf(90000), "lifted": True, "v": zero, "l": zero},
    }
    cols = [*t05.stream_ids("S1"), *t05.stream_ids("S2", lifted=True)]
    st = dormant_state(streams, {})
    cfg = {"unit": "U-VLV", "inlet": "S1", "outlet": "S2", "inlet_regime": "L"}

    def b1(x):
        return {
            **feed_rows(x, "U-FEED", "S1", zero, t330, P_R),
            **t05.rows_valve(th, x, cfg, {"outlet_pressure": mpf(90000)}),
            **label_row(x, "U-VLV", "S2.T", "S1.T"),
        }

    run(
        "DZ-1",
        b1,
        cols,
        st,
        {
            "unit": "U-VLV",
            "style": "outlet",
            "stream": "S2",
            "equilibrium": "VLV-equilibrium",
            "closure": "PH",
            "energy_row": "U-VLV:VLV-energy",
        },
        {"row": "U-VLV:zero-flow-label", "T_out": "S2.T", "T_label": "S1.T"},
    )

    # DZ-2: W0.8's PH flash.
    streams = {
        "S1": {"n": zero, "T": t330, "P": P_R},
        "S2": {"n": zero, "T": t330, "P": P_R},
        "S3": {"n": zero, "T": t330, "P": P_R},
    }
    cols = [
        *t05.stream_ids("S1"),
        *t05.stream_ids("S2"),
        *t05.stream_ids("S3"),
        "U-PHF.Q",
        "S2.N",
        "S3.N",
    ]
    st = dormant_state(streams, {"U-PHF.Q": mpf(0), "S2.N": mpf(0), "S3.N": mpf(0)})
    cfg2 = {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3", "inlet_regime": "L"}

    def b2(x):
        return {
            **feed_rows(x, "U-FEED", "S1", zero, t330, P_R),
            **t05.rows_ph_flash(th, x, cfg2, {"pressure_drop": mpf(0), "duty": mpf(0)}),
            **label_row(x, "U-PHF", "S2.T", "S1.T"),
        }

    run(
        "DZ-2",
        b2,
        cols,
        st,
        {
            "unit": "U-PHF",
            "style": "products",
            "vapor": "S2",
            "liquid": "S3",
            "equilibrium": "PHF-equilibrium",
            "mole": "PHF-mole",
            "closure": "PH",
            "energy_row": "U-PHF:PHF-duty",
        },
        {"row": "U-PHF:zero-flow-label", "T_out": "S2.T", "T_label": "S1.T"},
    )

    # DZ-3: a dormant valve branch (splitter r = 0) below a flowing PH flash (PHF-1).
    phf1 = t05.ph_solve((mpf(1), mpf(1), mpf(1)), P_R, mpf(50000))
    tf = phf1["T"]
    vap, liq = phf1["split"]["v"], phf1["split"]["l"]
    streams = {
        "S1": {"n": (mpf(1), mpf(1), mpf(1)), "T": mpf(300), "P": P_R},
        "S2": {"n": vap, "T": tf, "P": P_R},
        "S3": {"n": liq, "T": tf, "P": P_R},
        "S4": {"n": zero, "T": tf, "P": P_R},
        "S6": {"n": liq, "T": tf, "P": P_R},
        "S5": {"n": zero, "T": tf, "P": mpf(90000), "lifted": True, "v": zero, "l": zero},
    }
    cols = [
        *t05.stream_ids("S1"),
        *t05.stream_ids("S2"),
        *t05.stream_ids("S3"),
        "U-PHF.Q",
        "S2.N",
        "S3.N",
        *t05.stream_ids("S4"),
        *t05.stream_ids("S6"),
        *t05.stream_ids("S5", lifted=True),
    ]
    owned = {"U-PHF.Q": mpf(50000), "S2.N": sum(vap, mpf(0)), "S3.N": sum(liq, mpf(0))}
    st = dormant_state(streams, owned)
    cfg3 = {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3", "inlet_regime": "L"}
    cfgv = {"unit": "U-VLV", "inlet": "S4", "outlet": "S5", "inlet_regime": "L"}

    def b3(x):
        return {
            **feed_rows(x, "U-FEED", "S1", (mpf(1), mpf(1), mpf(1)), mpf(300), P_R),
            **t05.rows_ph_flash(th, x, cfg3, {"pressure_drop": mpf(0), "duty": mpf(50000)}),
            **splitter_rows(x, "U-SPLIT", "S3", "S4", "S6", mpf(0)),
            **t05.rows_valve(th, x, cfgv, {"outlet_pressure": mpf(90000)}),
            **label_row(x, "U-VLV", "S5.T", "S4.T"),
        }

    perturbed = {
        k: (v + 1 if k in ("S2.T", "S3.T", "S4.T", "S5.T", "S6.T") else v) for k, v in st.items()
    }
    run(
        "DZ-3",
        b3,
        cols,
        st,
        {
            "unit": "U-VLV",
            "style": "outlet",
            "stream": "S5",
            "equilibrium": "VLV-equilibrium",
            "closure": "PH",
            "energy_row": "U-VLV:VLV-energy",
        },
        {"row": "U-VLV:zero-flow-label", "T_out": "S5.T", "T_label": "S4.T"},
        {"phf1": phf1, "start": perturbed},
    )

    # DZ-4: a dormant duty-mode reactor.
    nu = t05.NU
    streams = {
        "S1": {"n": zero, "T": t330, "P": P_R},
        "S2": {"n": zero, "T": t330, "P": P_R, "lifted": True, "v": zero, "l": zero},
    }
    cols = [*t05.stream_ids("S1"), *t05.stream_ids("S2", lifted=True), "U-RX.Q", "U-RX.xi"]
    st = dormant_state(streams, {"U-RX.Q": mpf(0), "U-RX.xi": mpf(0)})
    cfg4 = {
        "unit": "U-RX",
        "inlet": "S1",
        "outlet": "S2",
        "inlet_regime": "L",
        "key": 0,
        "mode": "duty",
    }

    def b4(x):
        return {
            **feed_rows(x, "U-FEED", "S1", zero, t330, P_R),
            **t05.rows_reactor(
                th,
                x,
                cfg4,
                {"nu": nu, "conversion": mpf("0.5"), "pressure_drop": mpf(0), "duty": mpf(0)},
            ),
            **label_row(x, "U-RX", "S2.T", "S1.T"),
        }

    run(
        "DZ-4",
        b4,
        cols,
        st,
        {
            "unit": "U-RX",
            "style": "outlet",
            "stream": "S2",
            "equilibrium": "RX-equilibrium",
            "closure": "PH",
            "energy_row": "U-RX:RX-duty",
        },
        {"row": "U-RX:zero-flow-label", "T_out": "S2.T", "T_label": "S1.T"},
    )

    # DZ-5: a dormant K02 heater (TP-type: no label row; HEAT-T fixes the temperature).
    streams = {
        "S1": {"n": zero, "T": t330, "P": P_R},
        "S2": {"n": zero, "T": mpf(350), "P": P_R, "lifted": True, "v": zero, "l": zero},
    }
    cols = [*t05.stream_ids("S1"), *t05.stream_ids("S2", lifted=True), "U-HEAT.Q"]
    st = dormant_state(streams, {"U-HEAT.Q": mpf(0)})

    def b5(x):
        return {
            **feed_rows(x, "U-FEED", "S1", zero, t330, P_R),
            **heater_rows(th, x, "U-HEAT", "S1", "S2", mpf(350)),
        }

    run(
        "DZ-5",
        b5,
        cols,
        st,
        {
            "unit": "U-HEAT",
            "style": "outlet",
            "stream": "S2",
            "equilibrium": "HEAT-equilibrium",
            "closure": "TP",
        },
        None,
    )
    return out


def sc_regularity() -> dict[str, Any]:
    """The lifted system at the SC-1 and SC-2 roots is regular (T05 §4.7 (b), measured here)."""
    out: dict[str, Any] = {}
    th = TH
    sc = sc_cases()
    # SC-1
    r1 = sc["SC-1"]["valve"]
    v, liq = r1["split"]["v"], r1["split"]["l"]
    streams = {
        "S1": {"n": pure_b(2), "T": mpf(370), "P": mpf(180000)},
        "S2": {"n": pure_b(2), "T": r1["T"], "P": P_R, "lifted": True, "v": v, "l": liq},
    }
    cols = [*t05.stream_ids("S1"), *t05.stream_ids("S2", lifted=True)]
    st = dormant_state(streams, {})
    cfg = {"unit": "U-VLV", "inlet": "S1", "outlet": "S2", "inlet_regime": "L"}
    system = System(
        lambda x: {
            **feed_rows(x, "U-FEED", "S1", pure_b(2), mpf(370), mpf(180000)),
            **t05.rows_valve(th, x, cfg, {"outlet_pressure": P_R}),
        },
        cols,
    )
    ev = system.evaluate(st)
    rank, rcond = rank_and_rcond(scaled_matrix(ev, list(ev), cols))
    out["SC-1"] = {
        "dimension": len(cols),
        "rank": rank,
        "rcond1": rcond,
        "residual_max": max(abs(e["value"]) for e in ev.values()),
    }
    # SC-2
    r2 = sc["SC-2"]["phf"]
    streams = {
        "S1": {"n": pure_b(2), "T": mpf(300), "P": P_R},
        "S2": {"n": r2["split"]["v"], "T": r2["T"], "P": P_R},
        "S3": {"n": r2["split"]["l"], "T": r2["T"], "P": P_R},
    }
    cols = [
        *t05.stream_ids("S1"),
        *t05.stream_ids("S2"),
        *t05.stream_ids("S3"),
        "U-PHF.Q",
        "S2.N",
        "S3.N",
    ]
    st = dormant_state(streams, {"U-PHF.Q": mpf(42000), "S2.N": mpf(1), "S3.N": mpf(1)})
    cfg2 = {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3", "inlet_regime": "L"}
    system = System(
        lambda x: {
            **feed_rows(x, "U-FEED", "S1", pure_b(2), mpf(300), P_R),
            **t05.rows_ph_flash(th, x, cfg2, {"pressure_drop": mpf(0), "duty": mpf(42000)}),
        },
        cols,
    )
    ev = system.evaluate(st)
    rank, rcond = rank_and_rcond(scaled_matrix(ev, list(ev), cols))
    out["SC-2"] = {
        "dimension": len(cols),
        "rank": rank,
        "rcond1": rcond,
        "residual_max": max(abs(e["value"]) for e in ev.values()),
    }
    return out


# ============================================================================================
# 7. Degeneracy at registered states (inertness of the verifier and R-007 changes)
# ============================================================================================


def registered_degeneracy() -> dict[str, Any]:
    out: dict[str, Any] = {}
    coupled = {"C1": t05.coupled_c1(), "C2": t05.coupled_c2(), "C3": t05.coupled_c3()}
    # PH-flash splits: (feed stream, vapour product, liquid product) by case (T05 §11).
    products = {"C1": ("S4", "S5", "S6"), "C3": ("S3", "S4", "S5")}
    for cid, case in coupled.items():
        entries: dict[str, Any] = {}
        for name, st in case["streams"].items():
            if all(v == 0 for v in st["n"]):
                continue
            entries[name] = degeneracy_distance(st["n"], st["T"], st["P"])
        if cid in products:
            feed, vap, liq = products[cid]
            fs, vs, ls = case["streams"][feed], case["streams"][vap], case["streams"][liq]
            balance = max(abs(fs["n"][i] - vs["n"][i] - ls["n"][i]) for i in range(NC))
            entries[f"split:{feed}@{vap}"] = degeneracy_distance(fs["n"], vs["T"], vs["P"])
            entries[f"_balance:{feed}"] = balance
        out[cid] = entries
    # SYN-001's nominal root (r = 0.5, flash 360 K, heater 350 K): K04 §6, W1.d's root.
    p01 = t05.p01
    fresh = p01.FRESH
    fl = p01.tp_flash(fresh, mpf(360), P_R)
    beta = fl["beta"]
    total = sum(fresh)
    vapor = tuple(beta * total * y for y in fl["y"])
    liq_total = total * (1 - beta) / (1 - mpf("0.5"))
    liquid = tuple(liq_total * x for x in fl["x"])
    rec = tuple(mpf("0.5") * v for v in liquid)
    mixed = tuple(fresh[i] + rec[i] for i in range(NC))
    t_mix = (total * 300 + sum(rec) * 360) / sum(mixed)
    syn = {
        "S1": (fresh, mpf(300)),
        "S2": (mixed, t_mix),
        "S3": (mixed, mpf(350)),
        "S4": (vapor, mpf(360)),
        "S5": (liquid, mpf(360)),
        "S6": (rec, mpf(360)),
        "S7": (rec, mpf(360)),
        "split:S3@S4": (mixed, mpf(360)),
    }
    out["SYN-001-nominal"] = {name: degeneracy_distance(n, t, P_R) for name, (n, t) in syn.items()}
    return out


def kernel_states() -> dict[str, Any]:
    """Spec §6.5: the contract's kernel of a PH-type split (a valve outlet) at three registered
    states -- the primary answer, the PH closure's band route, and the TP fallback."""
    out: dict[str, Any] = {}
    # KS-1: SC-3's first trial, pure B in liquid form at 365.08 K: the PH closure answers.
    n1 = pure_b(2)
    t1 = mpf("365.08")
    h1 = t05.h_flow(n1, t1, P_R, "L")
    r1 = t05.ph_solve(n1, P_R, h1)
    out["KS-1"] = {
        "n": n1,
        "T": t1,
        "P": P_R,
        "v": t05.zeros(),
        "l": n1,
        "H_split": h1,
        "rho_TP": rho_tp(n1, t1, P_R),
        "ph_status": "ok",
        "ph_route": r1["route"],
        "rho": r1["split"]["regime"],
        "rho_T": r1["T"],
        "rho_beta": r1["split"]["beta"],
        "record": "",
    }
    # KS-2: a near-pure liquid-form trial at 430 K: the PH closure answers through its band route.
    n2 = (mpf("1e-12"), mpf(2), mpf(0))
    t2 = mpf(430)
    h2 = t05.h_flow(n2, t2, P_R, "L")
    r2 = band_solve(n2, P_R, h2)
    tr2 = f_temperature_route(tuple(float(x) for x in n2), 1e5, float(h2))
    out["KS-2"] = {
        "n": n2,
        "T": t2,
        "P": P_R,
        "v": t05.zeros(),
        "l": n2,
        "H_split": h2,
        "rho_TP": rho_tp(n2, t2, P_R),
        "ph_status": "ok",
        "ph_route": "band",
        "rho": "TWO_PHASE",
        "rho_T": r2["T"],
        "rho_beta": r2["beta"],
        "t_route_f_53": tr2["f"],
        "record": "fallback(U-VLV, ph-band)",
    }
    # KS-3: a trial whose split rows are far from satisfied (l = 2 n at 280 K): its enthalpy is
    # below the domain's, the PH closure refuses, and the TP flash answers.
    n3 = (mpf(1), mpf(1), mpf(1))
    l3 = (mpf(2), mpf(2), mpf(2))
    h3 = t05.h_flow(l3, T_MIN, P_R, "L")
    r3 = t05.ph_solve(n3, P_R, h3)
    out["KS-3"] = {
        "n": n3,
        "T": T_MIN,
        "P": P_R,
        "v": t05.zeros(),
        "l": l3,
        "H_split": h3,
        "rho_TP": rho_tp(n3, T_MIN, P_R),
        "ph_status": r3["status"],
        "ph_code": r3.get("code"),
        "rho": rho_tp(n3, T_MIN, P_R),
        "record": "fallback(U-VLV, tp)",
    }
    return out


def injections() -> dict[str, Any]:
    """Spec §12.6: injected states at SC-1's and DZ-1's roots that the verifier must judge."""
    n = pure_b(2)
    h_in = t05.h_flow(n, 370, 180000, "L")  # 14 016 W
    beta = mpf(2016) / 60000
    v, liq = pure_b(2 * beta), pure_b(2 - 2 * beta)
    out: dict[str, Any] = {}
    # INJ-B1: SC-1's root with the split all liquid (the TP kernel's answer at T_sat).
    t = mpf(360)
    out["INJ-B1"] = {
        "state": "SC-1's root with S2.vap = 0, S2.liq = S2.n (V = 0, L = 2) at T = 360 K",
        "degeneracy_K": degeneracy_distance(n, t, P_R),
        "energy_balance_U-VLV_W": h_in - t05.h_flow(n, t, P_R, "L"),
        # The compiled row reads the same stored split (VLV-energy = H_in - sum v h^V - sum l h^L),
        # and the envelope (feed in - product out) the same enthalpies: both miss by 2 016 W.
        "compiled_energy_row_W": h_in
        - (t05.h_flow(t05.zeros(), t, P_R, "V") + t05.h_flow(n, t, P_R, "L")),
        "energy_balance_envelope_in_minus_out_W": h_in - t05.h_flow(n, t, P_R, "L"),
        # v_i L - K_i l_i V with v = 0, V = 0, l = n, L = 2: every equilibrium row vanishes.
        "compiled_equilibrium_rows_max": max(
            abs(mpf(0) * sum(n, mpf(0)) - TH.k(i, t, P_R) * n[i] * mpf(0)) for i in range(NC)
        ),
    }
    # INJ-B2: SC-1's root 2e-6 K above T_sat: outside the window, judged by the fresh flash.
    t2 = mpf(360) + mpf("2e-6")
    fresh = t05.tp_split(n, t2, P_R)
    out["INJ-B2"] = {
        "state": "SC-1's root with S2.T = 360.000002 K (the lever-rule split kept)",
        "degeneracy_K": degeneracy_distance(n, t2, P_R),
        "fresh_regime": fresh["regime"],
        "independent_split_total_mol_per_s": sum(v, mpf(0)) - sum(fresh["v"], mpf(0)),
        "energy_balance_U-VLV_W": h_in - t05.h_split(fresh, t2, P_R),
        "compiled_energy_row_W": h_in
        - (t05.h_flow(v, t2, P_R, "V") + t05.h_flow(liq, t2, P_R, "L")),
        "compiled_equilibrium_row_B": v[1] * liq[1] - TH.k(1, t2, P_R) * liq[1] * v[1],
    }
    # INJ-B2p: 5e-7 K above T_sat: inside the window, judged by the stored split.
    t3 = mpf(360) + mpf("5e-7")
    out["INJ-B2p"] = {
        "state": "SC-1's root with S2.T = 360.0000005 K (the lever-rule split kept)",
        "degeneracy_K": degeneracy_distance(n, t3, P_R),
        "energy_balance_U-VLV_W": h_in
        - (t05.h_flow(v, t3, P_R, "V") + t05.h_flow(liq, t3, P_R, "L")),
    }
    # INJ-B3: DZ-1's root with the dormant outlet's label moved by 1 K.
    out["INJ-B3"] = {"state": "DZ-1's root with S2.T = 331 K", "label_residual_K": mpf(1)}
    return out


def registered_refusals() -> dict[str, Any]:
    """Every T05 unit case refused by R-007 (`inadmissible_phase(<port>, <PHASE>)`), with the
    refused stream's degeneracy distance: none may become admitted by D8 (spec §11)."""
    out: dict[str, Any] = {}
    for cid, case in t05.unit_cases().items():
        code = str(case["result"].get("code", ""))
        if not code.startswith("inadmissible_phase("):
            continue
        port = code[len("inadmissible_phase(") :].split(",")[0]
        stream = case["inputs"].get(port) or case["result"].get(port)
        if stream is None and port == "top":
            inlet = case["inputs"]["inlet"]
            split = case["inputs"]["split"]
            stream = {
                "n": tuple(inlet["n"][i] * split[i] for i in range(NC)),
                "T": inlet["T"],
                "P": inlet["P"],
            }
        out[cid] = {
            "code": code,
            "stream": stream,
            "degeneracy_K": degeneracy_distance(stream["n"], stream["T"], stream["P"])
            if stream is not None
            else None,
        }
    return out


def r007_states() -> dict[str, Any]:
    """Spec §11: R-007 extended by degeneracy, at the registered discriminating states."""
    states = {
        "R7-1": (pure_b(1), mpf(360), P_R, "V", "admitted: saturated vapour, T = T_sat exactly"),
        "R7-2": (
            pure_b(1),
            mpf(360) + mpf("2e-6"),
            P_R,
            "L",
            "refused: 2e-6 K above T_sat is outside the tolerance",
        ),
        "R7-3": (
            pure_b(1),
            mpf(360) + mpf("5e-7"),
            P_R,
            "L",
            "admitted: 5e-7 K above T_sat is inside the tolerance",
        ),
        "R7-4": (
            (mpf(1), mpf(1), mpf(1)),
            mpf("347.45"),
            P_R,
            "L",
            "refused: R-007's registered discriminating state, unchanged",
        ),
    }
    out = {}
    for cid, (n, t, p, phase, why) in states.items():
        adm = t05.admissibility(n, t, p, phase)
        dist = degeneracy_distance(n, t, p)
        admitted = bool(adm["admissible"] or dist <= TAU_T)
        out[cid] = {
            "n": n,
            "T": t,
            "P": p,
            "phase": phase,
            "why": why,
            "tp_gap_K": adm["equivalent_K"],
            "degeneracy_K": dist,
            "admitted": admitted,
            "reported_gap_K": adm["equivalent_K"]
            if adm["admissible"]
            else (dist if dist <= TAU_T else adm["equivalent_K"]),
        }
    return out


# ============================================================================================
# 7b. Dormant non-lifted outlets: the zero-flow form (spec §7.6-§7.10; Frank, 2026-09-25)
# ============================================================================================

#: Spec §7.6, transcribed: each registered dormancy-form outlet of a non-lifted model, by model
#: and, for the exchanger, by its `specification`. `trigger`: the inlet port whose streams must
#: all be exactly dormant; `swapped`: the equation family of the row the form drops; `label`: the
#: inlet port whose (first) stream's temperature the label row copies; `suffix`: the label row's
#: suffix (`<U>:zero-flow-label[:<suffix>]`). The item key is `<U>.<outlet>`.
HX_HOT = {
    "outlet": "hot_outlet",
    "trigger": "hot_inlet",
    "swapped": "HX-energy-hot",
    "label": "hot_inlet",
    "suffix": "hot",
    "declared_phase": "hot_phase",
}
HX_COLD = {
    "outlet": "cold_outlet",
    "trigger": "cold_inlet",
    "swapped": "HX-energy-cold",
    "label": "cold_inlet",
    "suffix": "cold",
    "declared_phase": "cold_phase",
}
NONLIFTED_FORMS: dict[str, list[dict[str, Any]]] = {
    "syn001.liquid_pump": [
        {
            "outlet": "outlet",
            "trigger": "inlet",
            "swapped": "PUMP-energy",
            "label": "inlet",
            "suffix": None,
            "declared_phase": "LIQUID",
        },
    ],
    "syn001.adiabatic_mixer": [
        {
            "outlet": "outlet",
            "trigger": "inlet",
            "swapped": "MIX-energy",
            "label": "inlet",
            "suffix": None,
            "declared_phase": "LIQUID",
        },
    ],
    "syn001.heat_exchanger(specification=duty)": [HX_HOT, HX_COLD],
    "syn001.heat_exchanger(specification=hot_outlet_temperature)": [HX_COLD],
    "syn001.heat_exchanger(specification=cold_outlet_temperature)": [HX_HOT],
}
HX_SPECS = ("duty", "hot_outlet_temperature", "cold_outlet_temperature")


def hx_forms(spec: str) -> list[dict[str, Any]]:
    return NONLIFTED_FORMS[f"syn001.heat_exchanger(specification={spec})"]


def mixer_rows(th, x, u: str, inlets: Sequence[str], so: str) -> t05.Rows:
    """K02's `syn001.adiabatic_mixer` rows (structure as `mixer.py`): liquid enthalpies, no duty,
    one pressure copy per inlet (`MIX-pressure:<k>`, k in wiring order)."""
    rows: t05.Rows = {}
    for c in COMPONENTS:
        rows[t05.rid(u, "MIX-mole", c)] = (
            "molar_flow",
            [*(x[t05.fid(si, c)] for si in inlets), -x[t05.fid(so, c)]],
        )
    rows[t05.rid(u, "MIX-energy")] = (
        "heat_rate",
        [
            *(term for si in inlets for term in t05.stream_enthalpy_terms(th, x, si, "L", 1)),
            *t05.stream_enthalpy_terms(th, x, so, "L", -1),
        ],
    )
    for k, si in enumerate(inlets):
        rows[t05.rid(u, "MIX-pressure", str(k))] = ("pressure", [x[t05.pid(si)], -x[t05.pid(so)]])
    return rows


def nl_label_row(x, row: str, t_out: str, t_label: str) -> t05.Rows:
    return {row: ("temperature", [x[t_out], -x[t_label]])}


def nl_form(unit: str, entry: Mapping[str, Any], wiring: Mapping[str, Any]) -> dict[str, Any]:
    """One active zero-flow form: its signature item, label row, swapped row and columns."""
    trigger = wiring[entry["trigger"]]
    trigger = list(trigger) if isinstance(trigger, list | tuple) else [trigger]
    label_stream = trigger[0]
    suffix = (entry["suffix"],) if entry["suffix"] else ()
    return {
        "item": f"{unit}.{entry['outlet']}",
        "label_row": t05.rid(unit, "zero-flow-label", *suffix),
        "swapped_row": t05.rid(unit, entry["swapped"]),
        "T_out": t05.tid(wiring[entry["outlet"]]),
        "T_label": t05.tid(label_stream),
        "trigger_flows": [t05.fid(s_, c) for s_ in trigger for c in COMPONENTS],
        "outlet_flows": [t05.fid(wiring[entry["outlet"]], c) for c in COMPONENTS],
    }


def certified_copies(ev: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """T01 §8.2's affine-copy certificate, transcribed for these mini-flowsheets: rows of kind
    pressure or temperature with every coefficient +-1 over at most two columns (cancelling when
    two), visited in declaration order; a row whose nodes are already connected is certified."""
    parent: dict[str, str] = {}

    def find(a: str) -> str:
        while parent.setdefault(a, a) != a:
            a = parent[a]
        return a

    certified = []
    for row, e in ev.items():
        if e["kind"] not in ("pressure", "temperature") or ":zero-flow-label" in row:
            continue
        entries = {k: v for k, v in e["jac"].items() if v != 0}
        if not entries or len(entries) > 2 or any(abs(v) != 1 for v in entries.values()):
            continue
        if len(entries) == 2 and sum(entries.values()) != 0:
            continue
        nodes = list(entries) if len(entries) == 2 else [next(iter(entries)), "CONST"]
        a, b = find(nodes[0]), find(nodes[1])
        if a == b:
            certified.append(row)
        else:
            parent[a] = b
    return certified


def form_of(ev, columns, rows, pinned=(), dropped=(), added=()) -> dict[str, Any]:
    """An attempt's system: rows minus dropped plus added, over columns minus pinned."""
    zrows = [r for r in rows if r not in dropped] + list(added)
    zcols = [c for c in columns if c not in pinned]
    rank, rcond = rank_and_rcond(scaled_matrix(ev, zrows, zcols))
    return {"rows": zrows, "columns": zcols, "rank": rank, "rcond1": rcond}


def nl_run(
    builder: Callable[[Mapping[str, Any]], t05.Rows],
    columns: Sequence[str],
    state: Mapping[str, Any],
    forms: Sequence[Mapping[str, Any]],
    lifted: Sequence[tuple[str, str]] = (),
    pinned: Sequence[str] = (),
    dropped: Sequence[str] = (),
) -> dict[str, Any]:
    """The declared (region) form and the attempt's zero-flow form of one registered state.
    `forms` are the active non-lifted zero-flow forms; `lifted`, the lifted signature items;
    `pinned`/`dropped`, the lifted regimes' pins and dropped rows (T02 §6.3.1)."""
    ev = System(builder, columns).evaluate(state)
    labels = {f["label_row"] for f in forms}
    declared = [r for r in ev if ":zero-flow-label" not in r]
    eliminated = certified_copies({r: ev[r] for r in declared})
    region = [r for r in declared if r not in eliminated]
    full = form_of(ev, columns, region, pinned, dropped)
    swapped = [f["swapped_row"] for f in forms]
    zf = form_of(ev, columns, region, pinned, [*dropped, *swapped], [f["label_row"] for f in forms])
    return {
        "columns": list(columns),
        "declared_rows": declared,
        "eliminated_rows": eliminated,
        "region_rows": region,
        "full_form": full,
        "zero_flow_form": zf,
        "T_out_rows": {
            f["T_out"]: sorted(r for r in region if ev[r]["jac"].get(f["T_out"], 0) != 0)
            for f in forms
        },
        "signature": [*[list(item) for item in lifted], *[[f["item"], "ZERO_FLOW"] for f in forms]],
        "forms": [dict(f) for f in forms],
        "residual_max": max(abs(ev[r]["value"]) for r in region),
        "swapped_values": {f["swapped_row"]: ev[f["swapped_row"]]["value"] for f in forms},
        "label_values": {r: ev[r]["value"] for r in labels},
        "trigger_dormant": {
            f["item"]: all(state[k] == 0 for k in f["trigger_flows"]) for f in forms
        },
        "outlet_dormant": {f["item"]: all(state[k] == 0 for k in f["outlet_flows"]) for f in forms},
        "state": dict(state),
        "_ev": ev,
    }


def hx_cfg(spec: str, hot_phase: str = "L", cold_phase: str = "L") -> dict[str, Any]:
    return {
        "unit": "U-HX",
        "hot_inlet": "S1",
        "hot_outlet": "S2",
        "cold_inlet": "S3",
        "cold_outlet": "S4",
        "hot_phase": hot_phase,
        "cold_phase": cold_phase,
        "specification": spec,
    }


HX_WIRING = {"hot_inlet": "S1", "hot_outlet": "S2", "cold_inlet": "S3", "cold_outlet": "S4"}
HX_COLUMNS = [*(c for s_ in ("S1", "S2", "S3", "S4") for c in t05.stream_ids(s_)), "U-HX.Q"]


def hx_system(spec: str, value: Any, hot, cold, t_ho, t_co, q, forms):
    """Two feeds into U-HX, as DZ-7/DZ-8/DZ-11 and the structure scan."""
    streams = {
        "S1": {"n": hot[0], "T": hot[1], "P": P_R},
        "S2": {"n": hot[0], "T": t_ho, "P": P_R},
        "S3": {"n": cold[0], "T": cold[1], "P": P_R},
        "S4": {"n": cold[0], "T": t_co, "P": P_R},
    }
    state = dormant_state(streams, {"U-HX.Q": q})
    cfg = hx_cfg(spec)

    def builder(x):
        rows = {
            **feed_rows(x, "U-FEED", "S1", hot[0], hot[1], P_R),
            **feed_rows(x, "U-FEED2", "S3", cold[0], cold[1], P_R),
            **t05.rows_exchanger(TH, x, cfg, {"value": value}),
        }
        for f in forms:
            rows.update(nl_label_row(x, f["label_row"], f["T_out"], f["T_label"]))
        return rows

    return builder, state


def nl_cases() -> dict[str, Any]:
    """Spec §12.8-§12.9: the dormant non-lifted outlets (DZ-6...DZ-12), the conflicts (DZ-11,
    DZ-2C) and INJ-B5."""
    th = TH
    zero = t05.zeros()
    ones = (mpf(1), mpf(1), mpf(1))
    t330, p_pump, eta = mpf(330), mpf(150000), mpf("0.75")
    out: dict[str, Any] = {}

    # DZ-6: a dormant pump.
    pump = NONLIFTED_FORMS["syn001.liquid_pump"][0]
    f6 = nl_form("U-PUMP", pump, {"inlet": "S1", "outlet": "S2"})
    streams = {"S1": {"n": zero, "T": t330, "P": P_R}, "S2": {"n": zero, "T": t330, "P": p_pump}}
    cols = [*t05.stream_ids("S1"), *t05.stream_ids("S2"), "U-PUMP.W"]
    cfgp = {"unit": "U-PUMP", "inlet": "S1", "outlet": "S2"}

    def b6(x):
        return {
            **feed_rows(x, "U-FEED", "S1", zero, t330, P_R),
            **t05.rows_pump(th, x, cfgp, {"outlet_pressure": p_pump, "efficiency": eta}),
            **nl_label_row(x, f6["label_row"], f6["T_out"], f6["T_label"]),
        }

    out["DZ-6"] = nl_run(b6, cols, dormant_state(streams, {"U-PUMP.W": mpf(0)}), [f6])

    # DZ-7: the exchanger's hot side dormant at 290 K -- below the cold inlet, so each terminal
    # difference would be a 10 K cross if a dormant side were judged (spec §9.3) -- duty
    # specified at 0 (the hot side swaps).
    t_hot7 = mpf(290)
    f7 = nl_form("U-HX", HX_HOT, HX_WIRING)
    b7, s7 = hx_system(
        "duty", mpf(0), (zero, t_hot7), (ones, mpf(300)), t_hot7, mpf(300), mpf(0), [f7]
    )
    out["DZ-7"] = nl_run(b7, HX_COLUMNS, s7, [f7])
    out["DZ-7"]["terminal_differences_K"] = {
        "hot_end": s7["S1.T"] - s7["S4.T"],
        "cold_end": s7["S2.T"] - s7["S3.T"],
    }

    # DZ-8: both sides dormant, the hot outlet temperature specified at 345 K: the cold side
    # swaps, the hot side is read by HX-spec and has no form.
    f8 = nl_form("U-HX", HX_COLD, HX_WIRING)
    b8, s8 = hx_system(
        "hot_outlet_temperature",
        mpf(345),
        (zero, mpf(350)),
        (zero, mpf(300)),
        mpf(345),
        mpf(300),
        mpf(0),
        [f8],
    )
    out["DZ-8"] = nl_run(b8, HX_COLUMNS, s8, [f8])

    # DZ-9: a mixer with both inlets dormant at different temperatures (the label is inlet 0's).
    mixer = NONLIFTED_FORMS["syn001.adiabatic_mixer"][0]
    f9 = nl_form("U-MIX", mixer, {"inlet": ["S1", "S2"], "outlet": "S3"})
    streams = {
        "S1": {"n": zero, "T": t330, "P": P_R},
        "S2": {"n": zero, "T": mpf(310), "P": P_R},
        "S3": {"n": zero, "T": t330, "P": P_R},
    }
    cols = [*t05.stream_ids("S1"), *t05.stream_ids("S2"), *t05.stream_ids("S3")]

    def b9(x):
        return {
            **feed_rows(x, "U-FEED", "S1", zero, t330, P_R),
            **feed_rows(x, "U-FEED2", "S2", zero, mpf(310), P_R),
            **mixer_rows(th, x, "U-MIX", ("S1", "S2"), "S3"),
            **nl_label_row(x, f9["label_row"], f9["T_out"], f9["T_label"]),
        }

    out["DZ-9"] = nl_run(b9, cols, dormant_state(streams, {}), [f9])

    # DZ-10: DZ-3 with the valve replaced by a pump -- a moving label on a non-lifted outlet.
    phf1 = t05.ph_solve(ones, P_R, mpf(50000))
    tf = phf1["T"]
    vap, liq = phf1["split"]["v"], phf1["split"]["l"]
    f10 = nl_form("U-PUMP", pump, {"inlet": "S4", "outlet": "S5"})
    streams = {
        "S1": {"n": ones, "T": mpf(300), "P": P_R},
        "S2": {"n": vap, "T": tf, "P": P_R},
        "S3": {"n": liq, "T": tf, "P": P_R},
        "S4": {"n": zero, "T": tf, "P": P_R},
        "S6": {"n": liq, "T": tf, "P": P_R},
        "S5": {"n": zero, "T": tf, "P": p_pump},
    }
    cols = [
        *t05.stream_ids("S1"),
        *t05.stream_ids("S2"),
        *t05.stream_ids("S3"),
        "U-PHF.Q",
        "S2.N",
        "S3.N",
        *t05.stream_ids("S4"),
        *t05.stream_ids("S6"),
        *t05.stream_ids("S5"),
        "U-PUMP.W",
    ]
    owned = {
        "U-PHF.Q": mpf(50000),
        "S2.N": sum(vap, mpf(0)),
        "S3.N": sum(liq, mpf(0)),
        "U-PUMP.W": mpf(0),
    }
    st10 = dormant_state(streams, owned)
    cfg10 = {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3", "inlet_regime": "L"}
    cfgp10 = {"unit": "U-PUMP", "inlet": "S4", "outlet": "S5"}

    def b10(x):
        return {
            **feed_rows(x, "U-FEED", "S1", ones, mpf(300), P_R),
            **t05.rows_ph_flash(th, x, cfg10, {"pressure_drop": mpf(0), "duty": mpf(50000)}),
            **splitter_rows(x, "U-SPLIT", "S3", "S4", "S6", mpf(0)),
            **t05.rows_pump(th, x, cfgp10, {"outlet_pressure": p_pump, "efficiency": eta}),
            **nl_label_row(x, f10["label_row"], f10["T_out"], f10["T_label"]),
        }

    out["DZ-10"] = nl_run(b10, cols, st10, [f10], lifted=[("U-PHF", "TWO_PHASE")])
    out["DZ-10"]["phf1"] = phf1
    out["DZ-10"]["start"] = {
        k: (v + 1 if k in ("S2.T", "S3.T", "S4.T", "S5.T", "S6.T") else v) for k, v in st10.items()
    }
    ev_start = System(b10, cols).evaluate(out["DZ-10"]["start"])
    out["DZ-10"]["start_label_residual_K"] = ev_start[f10["label_row"]]["value"]

    # DZ-11: DZ-7 with Q_spec = 1000 W -- the zero-flow form converges, the swapped row does not
    # vanish. Start: DZ-7's root. End: the zero-flow form's root (closed form).
    q11 = mpf(1000)
    t_co11 = mpf(300) + q11 / (3 * TH.b.CP)
    b11, s11 = hx_system("duty", q11, (zero, t_hot7), (ones, mpf(300)), t_hot7, t_co11, q11, [f7])
    out["DZ-11"] = nl_run(b11, HX_COLUMNS, s11, [f7])
    out["DZ-11"]["start"] = dict(s7)
    out["DZ-11"]["Q_spec_W"] = q11
    ev11 = out["DZ-11"]["_ev"]
    zf11 = out["DZ-11"]["zero_flow_form"]["rows"]
    out["DZ-11"]["zero_flow_rows_max"] = max(abs(ev11[r]["value"]) for r in zf11)
    ev11s = System(b11, HX_COLUMNS).evaluate(s7)
    out["DZ-11"]["start_zero_flow_rows_nonzero"] = sorted(r for r in zf11 if ev11s[r]["value"] != 0)
    # INJ-B4's energy balances at DZ-11's end: the unit (in - out, no external duty) and the
    # flowsheet envelope (feeds in - products out, no external duty anywhere).
    h = t05.h_flow
    unit_balance = (
        h(zero, t_hot7, P_R, "L")
        + h(ones, mpf(300), P_R, "L")
        - h(zero, t_hot7, P_R, "L")
        - h(ones, t_co11, P_R, "L")
    )
    out["DZ-11"]["energy_balance_U-HX_W"] = unit_balance
    out["DZ-11"]["energy_balance_envelope_W"] = unit_balance

    # DZ-2C: DZ-2 (a dormant PH flash, lifted) with Q_spec = 1000 W: the same conflict on a
    # lifted PH-type split, whose swapped row is PHF-duty.
    streams = {
        "S1": {"n": zero, "T": t330, "P": P_R},
        "S2": {"n": zero, "T": t330, "P": P_R},
        "S3": {"n": zero, "T": t330, "P": P_R},
    }
    cols2 = [
        *t05.stream_ids("S1"),
        *t05.stream_ids("S2"),
        *t05.stream_ids("S3"),
        "U-PHF.Q",
        "S2.N",
        "S3.N",
    ]
    cfg2 = {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3", "inlet_regime": "L"}
    lifted_zf = {
        "item": "U-PHF",
        "label_row": "U-PHF:zero-flow-label",
        "swapped_row": "U-PHF:PHF-duty",
        "T_out": "S2.T",
        "T_label": "S1.T",
        "trigger_flows": [t05.fid("S1", c) for c in COMPONENTS],
        "outlet_flows": [t05.fid(s_, c) for s_ in ("S2", "S3") for c in COMPONENTS],
    }
    pins, drops, _ = zero_flow_form(
        {
            "unit": "U-PHF",
            "style": "products",
            "vapor": "S2",
            "liquid": "S3",
            "equilibrium": "PHF-equilibrium",
            "mole": "PHF-mole",
            "closure": "TP",
        }
    )

    def b2c(x):
        return {
            **feed_rows(x, "U-FEED", "S1", zero, t330, P_R),
            **t05.rows_ph_flash(th, x, cfg2, {"pressure_drop": mpf(0), "duty": q11}),
            **label_row(x, "U-PHF", "S2.T", "S1.T"),
        }

    s2c = dormant_state(streams, {"U-PHF.Q": q11, "S2.N": mpf(0), "S3.N": mpf(0)})
    out["DZ-2C"] = nl_run(b2c, cols2, s2c, [lifted_zf], pinned=pins, dropped=drops)
    # The lifted item replaces the unit's regime entry: the signature is [[U-PHF, ZERO_FLOW]].
    out["DZ-2C"]["signature"] = [["U-PHF", "ZERO_FLOW"]]
    out["DZ-2C"]["start"] = {**s2c, "U-PHF.Q": mpf(0)}
    out["DZ-2C"]["Q_spec_W"] = q11
    ev2c = out["DZ-2C"]["_ev"]
    out["DZ-2C"]["zero_flow_rows_max"] = max(
        abs(ev2c[r]["value"]) for r in out["DZ-2C"]["zero_flow_form"]["rows"]
    )

    # DZ-12: leaving the form at a restart. U-PHF (lifted, PH-type) opens LIQUID from a supplied
    # start (its liquid-form root at 400 K), so its vapour product S2 is pinned dormant and
    # U-HX's hot side runs its zero-flow form; the LIQUID branch is inadmissible at closure, the
    # PH closure answers TWO_PHASE, S2 flows at the new opening, and the item leaves.
    q12 = mpf(30000)
    t_start = mpf(300) + q12 / (3 * TH.b.CP)  # 400 K: the liquid form's energy root
    root = t05.ph_solve(ones, P_R, q12)
    t_r, v12, l12 = root["T"], root["split"]["v"], root["split"]["l"]
    f12 = nl_form(
        "U-HX",
        HX_HOT,
        {"hot_inlet": "S2", "hot_outlet": "S4", "cold_inlet": "S5", "cold_outlet": "S6"},
    )
    cols12 = [
        *t05.stream_ids("S1"),
        *t05.stream_ids("S2"),
        *t05.stream_ids("S3"),
        "U-PHF.Q",
        "S2.N",
        "S3.N",
        *t05.stream_ids("S4"),
        *t05.stream_ids("S5"),
        *t05.stream_ids("S6"),
        "U-HX.Q",
    ]
    cfg12 = {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3", "inlet_regime": "L"}
    cfghx12 = {
        "unit": "U-HX",
        "hot_inlet": "S2",
        "hot_outlet": "S4",
        "cold_inlet": "S5",
        "cold_outlet": "S6",
        "hot_phase": "V",
        "cold_phase": "L",
        "specification": "duty",
    }

    def b12(x):
        return {
            **feed_rows(x, "U-FEED", "S1", ones, mpf(300), P_R),
            **t05.rows_ph_flash(th, x, cfg12, {"pressure_drop": mpf(0), "duty": q12}),
            **feed_rows(x, "U-FEED2", "S5", ones, mpf(300), P_R),
            **t05.rows_exchanger(th, x, cfghx12, {"value": mpf(0)}),
            **nl_label_row(x, f12["label_row"], f12["T_out"], f12["T_label"]),
        }

    def st12(s2n, t_phf, s3n, s4n, t4):
        streams = {
            "S1": {"n": ones, "T": mpf(300), "P": P_R},
            "S2": {"n": s2n, "T": t_phf, "P": P_R},
            "S3": {"n": s3n, "T": t_phf, "P": P_R},
            "S4": {"n": s4n, "T": t4, "P": P_R},
            "S5": {"n": ones, "T": mpf(300), "P": P_R},
            "S6": {"n": ones, "T": mpf(300), "P": P_R},
        }
        owned = {
            "U-PHF.Q": q12,
            "S2.N": sum(s2n, mpf(0)),
            "S3.N": sum(s3n, mpf(0)),
            "U-HX.Q": mpf(0),
        }
        return dormant_state(streams, owned)

    liquid_pins, liquid_drops = (
        [*(t05.fid("S2", c) for c in COMPONENTS), "S2.N"],
        [*(t05.rid("U-PHF", "PHF-equilibrium", c) for c in COMPONENTS), "U-PHF:Ndef:vapor"],
    )
    start12 = st12(zero, t_start, ones, zero, t_start)
    a0 = nl_run(
        b12,
        cols12,
        start12,
        [f12],
        lifted=[("U-PHF", "LIQUID")],
        pinned=liquid_pins,
        dropped=liquid_drops,
    )
    ev_a0 = a0["_ev"]
    a0_rows = a0["zero_flow_form"]["rows"]
    # The kernel of U-PHF at attempt 0's end (= the start): the PH closure at the split's own
    # enthalpy, which is the liquid form's 30 000 W.
    h_split0 = t05.h_flow(ones, t_start, P_R, "L")
    kernel0 = t05.ph_solve(ones, P_R, h_split0)
    # Attempt 1's opening: the kernel's split and temperature; S4's flows reset to S2's (spec
    # §7.8) or left at zero (the defect the reset prevents); S4.T keeps its label value.
    open_reset = st12(v12, t_r, l12, v12, t_start)
    open_noreset = st12(v12, t_r, l12, zero, t_start)
    decl = System(b12, cols12)
    ev_or, ev_on = decl.evaluate(open_reset), decl.evaluate(open_noreset)
    region12 = a0["region_rows"]
    a1_reset = form_of(ev_or, cols12, region12)
    a1_noreset = form_of(ev_on, cols12, region12)
    root12 = st12(v12, t_r, l12, v12, t_r)
    fin = nl_run(b12, cols12, root12, [], lifted=[("U-PHF", "TWO_PHASE")])
    y = [v12[i] / sum(v12, mpf(0)) for i in range(NC)]
    out["DZ-12"] = {
        **fin,
        "attempt0": {
            "signature": a0["signature"],
            "form": a0["zero_flow_form"],
            "rows_max_at_start": max(abs(ev_a0[r]["value"]) for r in a0_rows),
            "declared_rows_max_at_start": a0["residual_max"],
            "liquid_branch_bubble_value": sum(
                (TH.k(i, t_start, P_R) / 3 for i in range(NC)), mpf(0)
            ),
            "kernel": kernel0,
            "H_split_W": h_split0,
            "form_without_hx_form": a0["full_form"],
        },
        "attempt1_opening": {
            "with_reset": a1_reset,
            "without_reset": a1_noreset,
            "S4.T_column_zero_without_reset": all(
                ev_on[r]["jac"].get("S4.T", 0) == 0 for r in region12
            ),
        },
        "start": start12,
        "root_T": t_r,
        "hot_outlet_dew_value": sum((y[i] / TH.k(i, t_r, P_R) for i in range(NC)), mpf(0)) - 1,
        "hot_outlet_degeneracy_K": degeneracy_distance(v12, t_r, P_R),
        "hot_end_K": t_r - 300,
        "cold_end_K": t_r - 300,
    }

    # INJ-B5: DZ-9's root with the mixer outlet labelled by inlet 1 (310 K) instead of inlet 0.
    inj5 = {**out["DZ-9"]["state"], "S3.T": mpf(310)}
    ev5 = System(
        b9, [*t05.stream_ids("S1"), *t05.stream_ids("S2"), *t05.stream_ids("S3")]
    ).evaluate(inj5)
    out["INJ-B5"] = {
        "label_residual_K": ev5[f9["label_row"]]["value"],
        "compiled_rows_max": max(abs(ev5[r]["value"]) for r in out["DZ-9"]["region_rows"]),
    }
    return out


def dormant_structure() -> dict[str, Any]:
    """Spec §7.6's coverage claim: at exact dormancy, every outlet temperature of a SYN-001 model
    is read by a specification or copy row in the declared form, or has a zero-flow form (the
    lifted PH-type label of §7.2, or a registered non-lifted form)."""
    zero = t05.zeros()
    structure = {k: dict(v) for k, v in t05.dormant_temperature_columns().items()}
    # K02 units with the twin's own builders.
    x_state = dormant_state(
        {
            "S1": {"n": zero, "T": mpf(330), "P": P_R},
            "S2": {"n": zero, "T": mpf(350), "P": P_R, "lifted": True, "v": zero, "l": zero},
        },
        {"U-HEAT.Q": mpf(0)},
    )
    cols = [*t05.stream_ids("S1"), *t05.stream_ids("S2", lifted=True), "U-HEAT.Q"]
    ev = System(lambda x: heater_rows(TH, x, "U-HEAT", "S1", "S2", mpf(350)), cols).evaluate(
        x_state
    )
    structure["syn001.tp_heater"] = {"S2.T": sorted(r for r in ev if ev[r]["jac"].get("S2.T", 0))}
    x_state = dormant_state(
        {
            "S1": {"n": zero, "T": mpf(330), "P": P_R},
            "S2": {"n": zero, "T": mpf(330), "P": P_R},
            "S3": {"n": zero, "T": mpf(330), "P": P_R},
        },
        {},
    )
    cols = [*t05.stream_ids("S1"), *t05.stream_ids("S2"), *t05.stream_ids("S3")]
    ev = System(lambda x: splitter_rows(x, "U-SPLIT", "S1", "S2", "S3", mpf("0.5")), cols).evaluate(
        x_state
    )
    structure["syn001.splitter"] = {
        t: sorted(r for r in ev if ev[r]["jac"].get(t, 0)) for t in ("S2.T", "S3.T")
    }
    ev = System(lambda x: mixer_rows(TH, x, "U-MIX", ("S1", "S2"), "S3"), cols).evaluate(x_state)
    structure["syn001.adiabatic_mixer"] = {
        "S3.T": sorted(r for r in ev if ev[r]["jac"].get("S3.T", 0))
    }
    # The exchanger: every specification x every dormancy pattern.
    ones = (mpf(1), mpf(1), mpf(1))
    hx: dict[str, Any] = {}
    for spec in HX_SPECS:
        for pattern in ("hot", "cold", "both"):
            hot_n = zero if pattern in ("hot", "both") else ones
            cold_n = zero if pattern in ("cold", "both") else ones
            value = {"duty": mpf(0), "hot_outlet_temperature": mpf(345)}.get(spec, mpf(300))
            t_ho = mpf(345) if spec == "hot_outlet_temperature" else mpf(350)
            if spec == "hot_outlet_temperature" and pattern == "cold":
                value, t_ho = mpf(350), mpf(350)  # a flowing hot side at its inlet temperature
            t_co = mpf(300)
            dormant_sides = {"hot": pattern in ("hot", "both"), "cold": pattern in ("cold", "both")}
            forms = [
                nl_form("U-HX", e, HX_WIRING) for e in hx_forms(spec) if dormant_sides[e["suffix"]]
            ]
            builder, state = hx_system(
                spec, value, (hot_n, mpf(350)), (cold_n, mpf(300)), t_ho, t_co, mpf(0), forms
            )
            run = nl_run(builder, HX_COLUMNS, state, forms)
            ev = run["_ev"]
            hx[f"{spec}/{pattern}"] = {
                "dormant_T_rows": {
                    t05.tid(HX_WIRING[f"{side}_outlet"]): sorted(
                        r
                        for r in run["region_rows"]
                        if ev[r]["jac"].get(t05.tid(HX_WIRING[f"{side}_outlet"]), 0) != 0
                    )
                    for side in ("hot", "cold")
                    if dormant_sides[side]
                },
                "forms": [f["item"] for f in forms],
                "full_rank": run["full_form"]["rank"],
                "dimension": len(run["columns"]),
                "zero_flow_rank": run["zero_flow_form"]["rank"],
                "zero_flow_square": len(run["zero_flow_form"]["rows"])
                == len(run["zero_flow_form"]["columns"]),
                "residual_max": run["residual_max"],
            }
    return {"models": structure, "exchanger": hx}


#: Spec §7.6: how each dormant outlet temperature of a SYN-001 model is determined -- by a row of
#: the declared form (`row`), by the lifted PH-type label of §7.2 (`lifted`), or by a registered
#: non-lifted zero-flow form (`form`).
DORMANT_COVERAGE: dict[str, dict[str, str]] = {
    "syn001.valve": {"S2.T": "lifted"},
    "syn001.ph_flash": {"S2.T": "lifted", "S3.T": "lifted"},
    "syn001.conversion_reactor(duty)": {"S2.T": "lifted"},
    "syn001.conversion_reactor(outlet_temperature)": {"S2.T": "row"},
    "syn001.liquid_pump": {"S2.T": "form"},
    "syn001.component_separator": {"S2.T": "row", "S3.T": "row"},
    "syn001.heat_exchanger(hot side dormant)": {"S2.T": "form", "S4.T": "row"},
    "syn001.tp_heater": {"S2.T": "row"},
    "syn001.splitter": {"S2.T": "row", "S3.T": "row"},
    "syn001.adiabatic_mixer": {"S3.T": "form"},
}


def registered_dormancy_triggers() -> dict[str, Any]:
    """Spec §7.10's inertness: at every registered coupled root (T05 C1-C3, C3X) and at SC-4, the
    trigger inlets of every registered dormancy-form outlet flow, so no signature gains an item."""
    c1, c2, c3 = t05.coupled_c1(), t05.coupled_c2(), t05.coupled_c3()
    c3x = t05.coupled_c3(mpf(290))
    sc4_pump_inlet = sc_cases()["SC-4"]["phf1"]["split"]["l"]

    def flows(n):
        return sum(n, mpf(0))

    return {
        "C1:U-PUMP.outlet (inlet S1)": flows(c1["streams"]["S1"]["n"]),
        "C2:U-MIX.outlet (inlets S1, S4)": flows(c2["streams"]["S1"]["n"])
        + flows(c2["streams"]["S4"]["n"]),
        "C3:U-MIX.outlet (inlets S2, S6)": flows(c3["streams"]["S2"]["n"])
        + flows(c3["streams"]["S6"]["n"]),
        "C3:U-HX.cold_outlet (inlet S1; hot side temperature-specified)": flows(
            c3["streams"]["S1"]["n"]
        ),
        "C3X:U-MIX.outlet (inlets S2, S6)": flows(c3x["streams"]["S2"]["n"])
        + flows(c3x["streams"]["S6"]["n"]),
        "C3X:U-HX.cold_outlet (inlet S1)": flows(c3x["streams"]["S1"]["n"]),
        "SC-4:U-PUMP.outlet (inlet S3)": flows(sc4_pump_inlet),
    }


#: Spec B31 (i) (Q-S9 addendum, 2026-09-25): every downstream flash's pressure drop in the
#: companion cases, which takes its feed off the dew point without a duty on a dormant start.
B31_DP = mpf(10000)
#: `(unit, inlet, vapour product, liquid product, inlet phase)` of each `Q = 0` flash downstream
#: of `U-PHF` (spec B31; BUB is the bubble point's mirror, registered here only).
B31_CHAINS: dict[str, list[tuple[str, str, str, str, str]]] = {
    "CH-UP": [("U-PHF2", "S2", "S4", "S5", "V")],
    "CH-3": [("U-PHF2", "S2", "S4", "S5", "V"), ("U-PHF3", "S4", "S6", "S7", "V")],
    "BUB": [("U-PHF4", "S3", "S4", "S5", "L")],
}


def downstream_flash_cases() -> dict[str, Any]:
    """Spec B31 (b), (i) (Q-S9 addendum): `Q = 0` PH flashes fed a product of `U-PHF`.

    `U-PHF` is DZ-12's flash (feed (1,1,1), 300 K, `P_r`, 30 000 W); its vapour product `S2` feeds
    `Q = 0` flashes in series with pressure drop `dp` each (BUB: its liquid product `S3` feeds
    one). The closed-form root passes the feed through: the product of the feed's phase equals the
    feed at the feed's `T` (neither `h^V` nor, at `dp = 0`, `h^L` moves) and `P_in - dp`, the other
    product is zero. The declared lifted rows of a flash whose absent product is zero have entries
    only in that product's flow columns and total; with its total substituted their block is
    `v 1^T - N_V diag(K)` (absent liquid) or `N_L I - (K o l) 1^T` (absent vapour), of determinant
    `(-N_V)^n prod(K) (1 - sum y/K)` or `N_L^n (1 - sum K x)`: zero exactly on the dew or bubble
    point, which is where every `dp = 0` flash here sits."""
    th = TH
    ones, zero = (mpf(1), mpf(1), mpf(1)), t05.zeros()
    q = mpf(30000)
    root = t05.ph_solve(ones, P_R, q)
    t_r, v, liq = root["T"], root["split"]["v"], root["split"]["l"]
    out: dict[str, Any] = {}
    for label, chain in B31_CHAINS.items():
        for dp in (mpf(0),) if label == "BUB" else (mpf(0), B31_DP):
            streams: dict[str, dict[str, Any]] = {
                "S1": {"n": ones, "T": mpf(300), "P": P_R},
                "S2": {"n": v, "T": t_r, "P": P_R},
                "S3": {"n": liq, "T": t_r, "P": P_R},
            }
            owned: dict[str, Any] = {
                "U-PHF.Q": q,
                "S2.N": sum(v, mpf(0)),
                "S3.N": sum(liq, mpf(0)),
            }
            for u, si, so_v, so_l, phase in chain:
                n_in, p_out = streams[si]["n"], streams[si]["P"] - dp
                n_v, n_l = (n_in, zero) if phase == "V" else (zero, n_in)
                streams[so_v] = {"n": n_v, "T": t_r, "P": p_out}
                streams[so_l] = {"n": n_l, "T": t_r, "P": p_out}
                owned.update(
                    {
                        t05.qid(u): mpf(0),
                        t05.ntot(so_v): sum(n_v, mpf(0)),
                        t05.ntot(so_l): sum(n_l, mpf(0)),
                    }
                )

            def build(x, chain=chain, dp=dp):
                rows = {
                    **feed_rows(x, "U-FEED", "S1", ones, mpf(300), P_R),
                    **t05.rows_ph_flash(
                        th,
                        x,
                        {"unit": "U-PHF", "inlet": "S1", "vapor": "S2", "liquid": "S3"}
                        | {"inlet_regime": "L"},
                        {"pressure_drop": mpf(0), "duty": q},
                    ),
                }
                for u, si, so_v, so_l, phase in chain:
                    rows.update(
                        t05.rows_ph_flash(
                            th,
                            x,
                            {"unit": u, "inlet": si, "vapor": so_v, "liquid": so_l}
                            | {"inlet_regime": phase},
                            {"pressure_drop": dp, "duty": mpf(0)},
                        )
                    )
                return rows

            cols = [*(c for s_ in streams for c in t05.stream_ids(s_)), *owned]
            state = dormant_state(streams, owned)
            run = nl_run(build, cols, state, [])
            ev, rows = run["_ev"], run["region_rows"]
            u_mat, sigma, v_mat = mp.svd_r(scaled_matrix(ev, rows, cols))
            n = len(cols)
            deficit = n - run["full_form"]["rank"]
            null_right = sorted(
                {
                    cols[j]
                    for k in range(n - deficit, n)
                    for j in range(n)
                    if abs(v_mat[k, j]) > 1e-20
                }
            )
            null_left = sorted(
                {
                    rows[i]
                    for k in range(n - deficit, n)
                    for i in range(n)
                    if abs(u_mat[i, k]) > 1e-20
                }
            )
            flashes: dict[str, Any] = {}
            product_columns: list[str] = []
            for u, _si, so_v, so_l, phase in chain:
                s = streams[so_v] if phase == "V" else streams[so_l]
                t_, p_ = s["T"], s["P"]
                n_in = s["n"]
                total = sum(n_in, mpf(0))
                k_ = [th.k(i, t_, p_) for i in range(NC)]
                absent = so_l if phase == "V" else so_v
                if phase == "V":
                    boundary = sum((n_in[i] / total / k_[i] for i in range(NC)), mpf(0)) - 1
                    formula = (-total) ** NC * mp.fprod(k_) * (-boundary)
                else:
                    boundary = sum((k_[i] * n_in[i] / total for i in range(NC)), mpf(0)) - 1
                    formula = total**NC * (-boundary)
                eq_rows = [t05.rid(u, "PHF-equilibrium", c) for c in COMPONENTS]
                block_cols = [*(t05.fid(absent, c) for c in COMPONENTS), t05.ntot(absent)]
                block = mp.matrix(NC, NC)
                for a, ra in enumerate(eq_rows):
                    jac = ev[ra]["jac"]
                    for b, cb in enumerate(COMPONENTS):
                        block[a, b] = jac.get(t05.fid(absent, cb), 0) + jac.get(t05.ntot(absent), 0)
                support = sorted({c for r in eq_rows for c, d in ev[r]["jac"].items() if d != 0})
                flashes[u] = {
                    "phase_fed": phase,
                    "boundary_function": boundary,
                    # mpmath's det returns the int 0 for an exactly singular LU; keep it an mpf.
                    "block_det": mpf(mp.det(block)),
                    "block_det_formula": formula,
                    "equilibrium_support": support,
                    "equilibrium_block_columns": sorted(block_cols),
                    "absent_ndef_row": t05.rid(u, "Ndef", "liquid" if phase == "V" else "vapor"),
                    "product_P": p_,
                    "feed_P": streams[_si]["P"],
                }
                product_columns += [
                    c for s_ in (so_v, so_l) for c in (*t05.stream_ids(s_), t05.ntot(s_))
                ]
            out[f"{label}/dp={int(dp)}"] = {
                "dimension": n,
                "rank": run["full_form"]["rank"],
                "rcond1": run["full_form"]["rcond1"],
                "sigma_min_scaled": sigma[n - 1],
                "residual_max": run["residual_max"],
                "null_right_support": null_right,
                "null_left_support": null_left,
                "product_columns": product_columns,
                "flashes": flashes,
            }
    return out


# ============================================================================================
# 8. Claims (--check)
# ============================================================================================


class Claims:
    def __init__(self) -> None:
        self.passed: list[str] = []

    def __call__(self, name: str, condition: bool, detail: str = "") -> None:
        if not condition:
            raise AssertionError(f"generator claim failed: {name} {detail}")
        self.passed.append(name)


def imports_are_independent() -> bool:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            if name.split(".")[0] in ("openflowsheet", "benchmarks"):
                return False
    return True


def run_claims(grid, jump, biased, sc, npc, dz, screg, deg, r7, refusals, inj, ks) -> list[str]:
    claim = Claims()
    claim("imports_nothing_from_process_runtime_or_benchmarks", imports_are_independent())
    t05_bytes = T05_YAML.read_bytes()
    claim("t05_reference_file_unchanged", hashlib.sha256(t05_bytes).hexdigest() == T05_YAML_SHA256)

    # -- §4: the band ----------------------------------------------------------------------
    for which in ("A", "C"):
        for eps in EPSILONS:
            n = grid_flows(which, eps)
            betas = [mpf(k) / 20 for k in range(21)]
            ts = [band_t(n, P_R, b) for b in betas]
            claim(
                f"band_temperature_increasing_in_beta({which},{mp.nstr(eps, 1)})",
                all(ts[k] <= ts[k + 1] for k in range(20)),
            )
            hs = [band_h(n, P_R, b) for b in betas]
            claim(
                f"band_enthalpy_strictly_increasing_in_beta({which},{mp.nstr(eps, 1)})",
                all(hs[k] < hs[k + 1] for k in range(20)),
            )
            tb, td = ts[0], ts[-1]
            claim(
                f"band_end_enthalpies({which},{mp.nstr(eps, 1)})",
                t05.close(hs[0], t05.h_flow(n, tb, P_R, "L"), mpf("1e-28"))
                and t05.close(hs[-1], t05.h_flow(n, td, P_R, "V"), mpf("1e-28")),
            )
            for b in (mpf(0), mpf("0.5"), mpf(1)):
                g_lo = g_band(n, P_R, b, tb - 1)
                g_hi = g_band(n, P_R, b, td + 1)
                claim(f"g_increasing_in_T({which},{mp.nstr(eps, 1)},{b})", g_lo < 0 < g_hi)
            # First-order width: the band's width is proportional to the trace (spec §4.2).
            if eps <= mpf("1e-7"):
                small = grid_flows(which, eps / 10)
                tb2, td2 = band_ends(small, P_R)
                ratio = (td - tb) / (td2 - tb2)
                claim(
                    f"band_width_linear_in_trace({which},{mp.nstr(eps, 1)})",
                    abs(ratio - 10) <= mpf("1e-4"),
                )

    # -- §5: the kernel grid -----------------------------------------------------------------
    for cid, e in grid.items():
        ref = e["ref"]
        cross = t05.ph_solve(e["n"], P_R, e["target"])
        claim(
            f"band_solve_equals_temperature_bisection({cid})",
            abs(cross["T"] - ref["T"]) <= mpf("1e-25")
            and max(abs(cross["split"]["v"][i] - ref["v"][i]) for i in range(NC)) <= mpf("1e-25"),
        )
        mat, eq, en = rows_at(e["n"], ref["T"], P_R, ref["v"], ref["l"], e["target"])
        claim(
            f"reference_satisfies_closure_rows({cid})",
            max(abs(x) for x in mat) <= mpf("1e-30")
            and max(abs(x) for x in eq) <= mpf("1e-30")
            and abs(en) <= mpf("1e-25"),
        )
        claim(f"reference_inside_band({cid})", e["T_bubble"] <= ref["T"] <= e["T_dew"])
        br = e["band_route"]
        claim(f"band_route_53_accepts({cid})", br is not None and br["ok"])
        chosen = e["chosen"]
        err_t = abs(mpf(chosen["T"]) - ref["T"])
        err_v = abs(mpf(sum(chosen["v"])) - ref["V"])
        err_q = max(abs(mpf(chosen["v"][i]) / e["n"][i] - e["q"][i]) for i in flowing(e["n"]))
        claim(
            f"kernel_53_T_and_q_within_grid_tolerances_by_10x({cid})",
            err_t * 10 <= GRID_TOL["T"] and err_q * 10 <= GRID_TOL["q"],
            f"T {err_t} q {err_q}",
        )
        claim(
            f"kernel_53_V_error_within_the_acceptance_bound({cid})",
            err_v <= GRID_ACCEPTANCE_BOUND_V,
            f"V {err_v}",
        )
        b_err_t = abs(mpf(br["T"]) - ref["T"])
        b_err_v = abs(mpf(sum(br["v"])) - ref["V"])
        b_err_q = max(abs(mpf(br["v"][i]) / e["n"][i] - e["q"][i]) for i in flowing(e["n"]))
        claim(
            f"band_route_53_floor_100x_under_tolerance({cid})",
            b_err_t * 100 <= GRID_TOL["T"]
            and b_err_v * 100 <= GRID_TOL["V"]
            and b_err_q * 100 <= GRID_TOL["q"],
        )
        if e["eps"] <= mpf("1e-9") and e["phi"] != mpf("0.5"):
            claim(
                f"temperature_route_fails_energy_by_10x({cid})",
                abs(e["t_route"]["f"]) >= 10 * float(TAU_E),
                f"|f| = {e['t_route']['f']}",
            )
        # The pure limit (spec §4.2 sanity values).
        if e["eps"] == mpf("1e-12"):
            claim(
                f"pure_limit({cid})",
                abs(ref["T"] - 360) <= mpf("4e-11")
                and abs(ref["V"] - 2 * e["phi"]) <= mpf("1e-11"),
            )
    claim(
        "grid_V_tolerance_is_2x_the_acceptance_bound",
        2 * GRID_ACCEPTANCE_BOUND_V <= GRID_TOL["V"],
        f"bound {GRID_ACCEPTANCE_BOUND_V}",
    )
    # The trace's vapour fraction is not a vanishing quantity: q_trace >= 0.02 everywhere.
    claim(
        "trace_vapour_fractions_are_order_one",
        min(e["q"][0 if e["n"][0] > 0 else 2] for e in grid.values()) >= mpf("0.02"),
    )

    # -- §12.2: the doubles ------------------------------------------------------------------
    claim("jump_margin_is_1e5_tau_E", jump["margin_W"] >= 100000 * TAU_E)
    tr = biased["t_route"]
    claim("biased_temperature_route_meets_energy", abs(tr["f"]) <= float(TAU_E))
    claim(
        "biased_temperature_route_fails_equilibrium_by_10x",
        tr["rows"][1] >= 10 * float(TAU_EQ),
        f"{tr['rows'][1]}",
    )
    claim(
        "biased_temperature_route_is_wrong_by_10_tau_T",
        abs(mpf(tr["T"]) - biased["ref_T"]) >= 10 * TAU_T,
        f"{tr['T']}",
    )
    br = biased["band_route"]
    claim(
        "biased_band_route_equals_phf1_within_100x",
        abs(mpf(br["T"]) - biased["ref_T"]) * 100 <= TAU_T
        and max(abs(mpf(br["v"][i]) - biased["ref_split"]["v"][i]) for i in range(NC)) * 100
        <= TAU_FLOW,
    )

    # -- §6, §12.3: single component ---------------------------------------------------------
    r1 = sc["SC-1"]["valve"]
    claim(
        "sc1_lever_rule_closed_form",
        r1["T"] == 360 and t05.close(r1["split"]["beta"], mpf(2016) / 60000),
    )
    claim(
        "sc2_is_phf6",
        sc["SC-2"]["phf"]["T"] == 360 and t05.close(sc["SC-2"]["phf"]["split"]["beta"], mpf("0.5")),
    )
    sc3 = sc["SC-3"]
    claim("sc3_root_closed_form", t05.close(sc3["phf"]["split"]["beta"], mpf(1016) / 60000))
    claim(
        "sc3_start_reads_liquid_and_opens_liquid_at_355K",
        t05.close(sc3["start_H_in_read"], 12000)
        and sc3["start_phf"]["split"]["regime"] == "LIQUID"
        and t05.close(sc3["start_phf"]["T"], 355),
    )
    claim("sc3_trial_at_liquid_form_root", t05.close(sc3["trial_T"], mpf("365.08"), mpf("1e-25")))
    claim("sc3_trial_tp_regime_is_far", sc3["trial_rho_TP"] == "VAPOR")
    claim(
        "sc3_trial_ph_regime_is_adjacent_and_is_the_root",
        sc3["trial_rho_PH"]["regime"] == "TWO_PHASE"
        and t05.close(sc3["trial_rho_PH"]["beta"], mpf(1016) / 60000, mpf("1e-25")),
    )
    sc4 = sc["SC-4"]
    claim(
        "sc4_phf2_inlet_refused_by_tp_R007",
        sc4["phf2_inlet_tp_gap_K"] > TAU_T and sc4["phf2_inlet_tp_regime"] == "LIQUID",
    )
    claim("sc4_phf2_inlet_degenerate_exactly", sc4["phf2_inlet_degeneracy_K"] == 0)
    claim("sc4_pump_inlet_admitted_by_tp_R007", sc4["pump_inlet_tp_gap_K"] <= TAU_T)
    claim("sc4_phf2_lever_rule", t05.close(sc4["phf2"]["split"]["beta"], mpf("0.5")))
    claim("sc4_pump_outlet_not_degenerate", sc4["pump_outlet_degeneracy_K"] >= 1)
    claim(
        "sc4_pump_ok",
        sc4["pump"]["status"] == "ok"
        and t05.close(sc4["pump"]["work"], mpf(5) / mpf("0.75"), mpf("1e-25")),
    )
    for cid, reg in screg.items():
        claim(
            f"{cid}_root_regular",
            reg["rank"] == reg["dimension"] and reg["rcond1"] >= mpf("1e-4"),
            f"rcond {reg['rcond1']}",
        )
        claim(f"{cid}_rows_vanish_at_root", reg["residual_max"] <= mpf("1e-25"))

    # -- §12.4: near-pure EO -------------------------------------------------------------------
    for cid, e in npc.items():
        claim(
            f"{cid}_band_solve_equals_temperature_bisection",
            abs(e["cross_T"] - e["ref"]["T"]) <= mpf("1e-25"),
        )
    claim(
        "np1_traversal_takes_the_band_route_by_10x",
        abs(npc["NP-1"]["t_route_53"]["f"]) >= 10 * float(TAU_E),
    )
    np3_rows = npc["NP-3"]["t_route_53"]["rows"]
    claim(
        "np3_traversal_takes_the_temperature_route_with_10x",
        np3_rows[0] * 10 <= float(TAU_FLOW)
        and np3_rows[1] * 10 <= float(TAU_EQ)
        and np3_rows[2] * 10 <= float(TAU_E),
        f"{np3_rows}",
    )
    claim("np1_np2_degenerate", npc["NP-1"]["degenerate"] and npc["NP-2"]["degenerate"])
    claim(
        "np1_np2_degeneracy_margin_absolute_7e-7K",
        all(TAU_T - npc[c]["degeneracy_K"] >= mpf("7e-7") for c in ("NP-1", "NP-2")),
    )
    claim("np3_npg_not_degenerate", not npc["NP-3"]["degenerate"] and not npc["NP-G"]["degenerate"])
    claim("npg_width_exceeds_twice_tau_T", npc["NP-G"]["width"] >= 2 * TAU_T * mpf("1.5"))
    claim("np3_width_exceeds_10_tau_T", npc["NP-3"]["width"] >= 20 * TAU_T)
    claim(
        "np3_fresh_flash_resolves_it_by_10x",
        abs(npc["NP-3"]["fresh_products_energy_error_W"]) * 10 <= float(TAU_E)
        and abs(npc["NP-3"]["fresh_feed_V_error"]) * 10 <= float(TAU_FLOW),
        f"{npc['NP-3']['fresh_products_energy_error_W']} {npc['NP-3']['fresh_feed_V_error']}",
    )
    claim(
        "npg_fresh_flash_fails_by_2x",
        abs(npc["NP-G"]["fresh_products_energy_error_W"]) >= 2 * float(TAU_E)
        or abs(npc["NP-G"]["fresh_feed_V_error"]) >= 2 * float(TAU_FLOW),
        f"{npc['NP-G']['fresh_products_energy_error_W']} {npc['NP-G']['fresh_feed_V_error']}",
    )

    # -- §7, §12.5: ZERO_FLOW ------------------------------------------------------------------
    for cid, e in dz.items():
        n_eq = 3
        claim(f"{cid}_rows_vanish_at_dormant_root", e["residual_max"] <= mpf("1e-25"))
        equilibrium = [
            r for r in e["rows"] if r.startswith(e["split_unit"] + ":") and "equilibrium" in r
        ]
        claim(
            f"{cid}_full_form_zero_rows_are_exactly_the_equilibrium_rows",
            sorted(e["identically_zero_rows"]) == sorted(equilibrium) and len(equilibrium) == n_eq,
        )
        claim(
            f"{cid}_full_form_rank_deficit",
            e["full_rank"] <= e["full_dimension"] - n_eq,
            f"rank {e['full_rank']} of {e['full_dimension']}",
        )
        claim(
            f"{cid}_zero_flow_form_square", len(e["zero_flow_rows"]) == len(e["zero_flow_columns"])
        )
        claim(
            f"{cid}_zero_flow_form_regular",
            e["zero_flow_rank"] == len(e["zero_flow_columns"])
            and e["zero_flow_rcond1"] >= mpf("1e-6"),
            f"rcond {e['zero_flow_rcond1']}",
        )
        if e["label"] is not None:
            claim(
                f"{cid}_label_satisfied",
                e["state"][e["label"]["T_out"]] == e["state"][e["label"]["T_label"]],
            )
    # DZ-3: the label must move from the perturbed start (T_label moves by -1 K).
    claim(
        "dz3_start_moves_the_label", dz["DZ-3"]["start"]["S4.T"] - dz["DZ-3"]["state"]["S4.T"] == 1
    )
    # The dormant temperature column in the full form is T05 A15's registered structure: no row
    # for the valve and the duty-mode reactor, only the copy row PHF-T for the PH flash.
    claim(
        "dormant_T_columns_match_T05_A15",
        dz["DZ-1"]["full_form_T_out_rows"] == []
        and dz["DZ-3"]["full_form_T_out_rows"] == []
        and dz["DZ-4"]["full_form_T_out_rows"] == []
        and dz["DZ-2"]["full_form_T_out_rows"] == ["U-PHF:PHF-T"],
        f"{[dz[c]['full_form_T_out_rows'] for c in ('DZ-1', 'DZ-2', 'DZ-3', 'DZ-4')]}",
    )

    # -- §10, §11: degeneracy at registered states and R-007 --------------------------------------
    minimum = min(v for case in deg.values() for k, v in case.items() if not k.startswith("_"))
    claim("registered_states_are_not_degenerate_by_1e7", minimum >= 10**7 * TAU_T, f"min {minimum}")
    for cid, case in deg.items():
        for k, v in case.items():
            if k.startswith("_balance"):
                claim(f"{cid}_{k}_holds", v <= mpf("1e-25"))
    claim("r7_1_admitted", r7["R7-1"]["admitted"] and r7["R7-1"]["tp_gap_K"] > 100)
    claim("r7_2_refused", not r7["R7-2"]["admitted"])
    claim("r7_3_admitted", r7["R7-3"]["admitted"] and r7["R7-3"]["tp_gap_K"] > 100)
    claim("r7_4_refused_unchanged", not r7["R7-4"]["admitted"] and r7["R7-4"]["degeneracy_K"] >= 1)
    # -- §6.5: the contract's kernel of a PH-type split ------------------------------------------
    claim(
        "ks1_primary_ph_answer_is_the_adjacent_regime",
        ks["KS-1"]["rho_TP"] == "VAPOR"
        and ks["KS-1"]["rho"] == "TWO_PHASE"
        and ks["KS-1"]["ph_route"] == "saturation",
    )
    claim(
        "ks2_ph_closure_takes_the_band_route_by_10x",
        abs(ks["KS-2"]["t_route_f_53"]) >= 10 * float(TAU_E),
        f"{ks['KS-2']['t_route_f_53']}",
    )
    claim(
        "ks2_ph_regime_two_phase_tp_vapour",
        ks["KS-2"]["rho_TP"] == "VAPOR" and 0 < ks["KS-2"]["rho_beta"] < 1,
    )
    claim(
        "ks3_ph_closure_refuses_below_and_tp_answers_liquid",
        ks["KS-3"]["ph_status"] == "out_of_domain"
        and ks["KS-3"]["ph_code"] == "ph_outside_domain(below)"
        and ks["KS-3"]["rho_TP"] == "LIQUID",
    )

    # -- §12.6: injections -------------------------------------------------------------------
    claim(
        "inj_b1_is_degenerate_and_misses_the_latent_share_exactly",
        inj["INJ-B1"]["degeneracy_K"] == 0 and inj["INJ-B1"]["energy_balance_U-VLV_W"] == 2016,
    )
    claim(
        "inj_b1_compiled_energy_row_and_envelope_miss_by_2016W_equilibrium_rows_pass",
        inj["INJ-B1"]["compiled_energy_row_W"] == 2016
        and inj["INJ-B1"]["energy_balance_envelope_in_minus_out_W"] == 2016
        and inj["INJ-B1"]["compiled_equilibrium_rows_max"] == 0,
    )
    b2 = inj["INJ-B2"]
    claim("inj_b2_outside_window_by_1.9x", b2["degeneracy_K"] >= mpf("1.9") * TAU_T)
    claim(
        "inj_b2_fresh_flash_vapour_and_fails_by_1e3",
        b2["fresh_regime"] == "VAPOR"
        and abs(b2["independent_split_total_mol_per_s"]) >= 1000 * TAU_FLOW
        and abs(b2["energy_balance_U-VLV_W"]) >= 1000 * TAU_E,
    )
    claim(
        "inj_b2_compiled_rows_pass",
        abs(b2["compiled_energy_row_W"]) <= TAU_E
        and abs(b2["compiled_equilibrium_row_B"]) <= TAU_EQ,
    )
    b2p = inj["INJ-B2p"]
    claim(
        "inj_b2p_inside_window_by_2x_and_balances",
        b2p["degeneracy_K"] * 2 <= TAU_T and abs(b2p["energy_balance_U-VLV_W"]) * 10 <= TAU_E,
    )
    claim("inj_b3_label_residual_1e6_tau_T", inj["INJ-B3"]["label_residual_K"] >= 10**6 * TAU_T)
    # A PH-type split on SYN-001 is never reported in the far regime (spec §6.3): the liquid
    # enthalpy at the top of the domain is below the vapour enthalpy at its bottom, per mole.
    claim(
        "ph_regime_never_far_on_the_domain",
        max(TH.h("L", i, T_MAX, t05.P_MAX) for i in range(NC))
        < min(TH.h("V", j, T_MIN, t05.P_MIN) for j in range(NC)),
    )
    claim(
        "t05_registered_refusals_are_the_five_known",
        sorted(refusals) == ["HX-F4", "PHF-F3", "PUMP-F1", "PUMP-F2", "SEP-F2"],
        f"{sorted(refusals)}",
    )
    for cid, e in refusals.items():
        claim(
            f"t05_refusal_{cid}_stays_refused_by_1e6_tau_T",
            e["degeneracy_K"] is not None and e["degeneracy_K"] >= 10**6 * TAU_T,
            f"{e['degeneracy_K']}",
        )
    return claim.passed


def run_nl_claims(claim: Claims, nl, structure, triggers) -> None:
    """Spec §7.6-§7.10 and §12.8: the zero-flow form of dormant non-lifted outlets (amendment of
    2026-09-25, Frank's answer to §18 Q2)."""
    tiny = mpf("1e-25")

    def square_regular(form: Mapping[str, Any]) -> bool:
        n = len(form["columns"])
        return len(form["rows"]) == n and form["rank"] == n and form["rcond1"] >= mpf("1e-6")

    for cid in ("DZ-6", "DZ-7", "DZ-8", "DZ-9", "DZ-10"):
        e = nl[cid]
        n = len(e["columns"])
        claim(f"{cid}_rows_vanish_at_dormant_root", e["residual_max"] <= tiny)
        claim(
            f"{cid}_label_and_swapped_rows_vanish_at_root",
            all(
                abs(v) <= tiny for v in (*e["label_values"].values(), *e["swapped_values"].values())
            ),
        )
        claim(
            f"{cid}_trigger_inlets_and_outlet_exactly_dormant",
            all(e["trigger_dormant"].values()) and all(e["outlet_dormant"].values()),
        )
        claim(
            f"{cid}_dormant_outlet_temperature_has_no_row_in_the_declared_form",
            all(rows == [] for rows in e["T_out_rows"].values()),
            f"{e['T_out_rows']}",
        )
        claim(f"{cid}_declared_form_square", len(e["full_form"]["rows"]) == n)
        claim(
            f"{cid}_declared_form_rank_deficit_is_one_per_form",
            e["full_form"]["rank"] == n - len(e["forms"]),
            f"rank {e['full_form']['rank']} of {n}",
        )
        claim(
            f"{cid}_zero_flow_form_square_and_regular",
            square_regular(e["zero_flow_form"]),
            f"rcond {e['zero_flow_form']['rcond1']}",
        )
    claim(
        "dz9_t01_certifies_exactly_the_second_mixer_pressure_row",
        nl["DZ-9"]["eliminated_rows"] == ["U-MIX:MIX-pressure:1"]
        and all(nl[c]["eliminated_rows"] == [] for c in ("DZ-6", "DZ-7", "DZ-8", "DZ-10", "DZ-12")),
    )
    claim(
        "dz9_label_is_inlet_0s_and_inlet_1_differs_by_20K",
        nl["DZ-9"]["forms"][0]["T_label"] == "S1.T"
        and nl["DZ-9"]["state"]["S1.T"] - nl["DZ-9"]["state"]["S2.T"] == 20,
    )
    claim(
        "dz8_hot_side_dormant_but_specified_has_no_form",
        [f["item"] for f in nl["DZ-8"]["forms"]] == ["U-HX.cold_outlet"]
        and nl["DZ-8"]["state"]["S2.T"] == 345,
    )
    claim(
        "dz7_terminal_differences_would_cross_by_10K_if_judged",
        nl["DZ-7"]["terminal_differences_K"] == {"hot_end": -10, "cold_end": -10},
        f"{nl['DZ-7']['terminal_differences_K']}",
    )
    claim(
        "dz10_start_moves_the_label_by_1K",
        nl["DZ-10"]["start"]["S4.T"] - nl["DZ-10"]["state"]["S4.T"] == 1
        and nl["DZ-10"]["start"]["S5.T"] - nl["DZ-10"]["state"]["S5.T"] == 1,
    )
    # The conflicts: the zero-flow form converges; the row it swapped out does not vanish.
    for cid, row, value in (
        ("DZ-11", "U-HX:HX-energy-hot", mpf(-1000)),
        ("DZ-2C", "U-PHF:PHF-duty", mpf(1000)),
    ):
        e = nl[cid]
        claim(f"{cid}_zero_flow_rows_vanish_at_the_end_state", e["zero_flow_rows_max"] <= tiny)
        claim(f"{cid}_zero_flow_form_square_and_regular", square_regular(e["zero_flow_form"]))
        claim(
            f"{cid}_swapped_row_is_{mp.nstr(value, 5)}W_at_the_end_by_9e5_tau_E",
            e["swapped_values"][row] == value and abs(value) >= mpf("9e5") * TAU_E,
        )
    claim(
        "dz11_start_is_not_the_end_state",
        nl["DZ-11"]["start_zero_flow_rows_nonzero"] == ["U-HX:HX-spec"],
    )
    claim(
        "dz11_energy_balances_fail_by_minus_1000W",
        abs(nl["DZ-11"]["energy_balance_U-HX_W"] + 1000) <= tiny
        and abs(nl["DZ-11"]["energy_balance_envelope_W"] + 1000) <= tiny,
    )
    d12 = nl["DZ-12"]
    a0 = d12["attempt0"]
    claim(
        "dz12_start_satisfies_attempt0_and_the_declaration",
        a0["rows_max_at_start"] <= tiny and a0["declared_rows_max_at_start"] <= tiny,
    )
    claim("dz12_attempt0_form_square_and_regular", square_regular(a0["form"]))
    claim(
        "dz12_attempt0_without_the_hx_form_is_singular_by_one",
        a0["form_without_hx_form"]["rank"] == len(a0["form_without_hx_form"]["columns"]) - 1,
    )
    claim(
        "dz12_liquid_branch_inadmissible_at_closure",
        a0["liquid_branch_bubble_value"] > 1 + EPS_ADM,
        f"{a0['liquid_branch_bubble_value']}",
    )
    claim(
        "dz12_kernel_is_the_ph_closure_primary_route_two_phase",
        a0["kernel"]["status"] == "ok"
        and a0["kernel"]["route"] == "bracket"
        and a0["kernel"]["split"]["regime"] == "TWO_PHASE"
        and a0["kernel"]["T"] == d12["root_T"],
    )
    claim(
        "dz12_attempt1_opening_regular_with_the_outlet_reset",
        square_regular(d12["attempt1_opening"]["with_reset"]),
    )
    claim(
        "dz12_attempt1_opening_singular_without_the_outlet_reset",
        d12["attempt1_opening"]["without_reset"]["rank"]
        == len(d12["attempt1_opening"]["without_reset"]["columns"]) - 1
        and d12["attempt1_opening"]["S4.T_column_zero_without_reset"],
    )
    claim("dz12_root_rows_vanish", d12["residual_max"] <= tiny)
    claim("dz12_root_declared_form_regular", square_regular(d12["full_form"]))
    claim(
        "dz12_hot_inlet_flows_at_the_root_so_no_item",
        sum((d12["state"][t05.fid("S2", c)] for c in COMPONENTS), mpf(0)) > 0
        and d12["signature"] == [["U-PHF", "TWO_PHASE"]],
    )
    claim("dz12_hot_outlet_at_its_dew_point", abs(d12["hot_outlet_dew_value"]) <= tiny)
    claim("dz12_hot_outlet_not_degenerate_by_1K", d12["hot_outlet_degeneracy_K"] >= 1)
    claim("dz12_terminal_differences_positive", d12["hot_end_K"] > 0 and d12["cold_end_K"] > 0)
    inj5 = nl["INJ-B5"]
    claim(
        "inj_b5_label_residual_minus_20K_compiled_rows_zero",
        inj5["label_residual_K"] == -20 and inj5["compiled_rows_max"] <= tiny,
    )
    # §7.6's coverage: every dormant outlet temperature of a SYN-001 model has a row or a form.
    models = structure["models"]
    claim(
        "dormant_structure_covers_every_model_scanned",
        sorted(models) == sorted(DORMANT_COVERAGE),
        f"{sorted(models)}",
    )
    for model, columns in models.items():
        for column, rows in columns.items():
            how = DORMANT_COVERAGE[model][column]
            shared_copy = model == "syn001.ph_flash" and rows == ["U-PHF:PHF-T"]
            ok = (how == "row" and rows != [] and not shared_copy) or (
                how in ("lifted", "form") and (rows == [] or shared_copy)
            )
            claim(f"dormant_coverage({model},{column})={how}", ok, f"{rows}")
    claim(
        "dormant_coverage_forms_are_the_registered_non_lifted_models",
        {m.split("(")[0] for m, cs in DORMANT_COVERAGE.items() if "form" in cs.values()}
        == {m.split("(")[0] for m in NONLIFTED_FORMS},
    )
    for key, e in structure["exchanger"].items():
        spec, pattern = key.split("/")
        claim(f"hx_{key}_state_is_a_root", e["residual_max"] <= tiny)
        expected_rows = {
            t05.tid(HX_WIRING[f"{side}_outlet"]): (
                ["U-HX:HX-spec"] if spec == f"{side}_outlet_temperature" else []
            )
            for side in ("hot", "cold")
            if pattern in (side, "both")
        }
        claim(f"hx_{key}_dormant_outlet_rows", e["dormant_T_rows"] == expected_rows)
        expected_forms = [
            f"U-HX.{side}_outlet"
            for side in ("hot", "cold")
            if pattern in (side, "both") and spec != f"{side}_outlet_temperature"
        ]
        claim(f"hx_{key}_forms_are_the_registry", e["forms"] == expected_forms, f"{e['forms']}")
        claim(
            f"hx_{key}_declared_rank_deficit_is_one_per_form",
            e["full_rank"] == e["dimension"] - len(e["forms"]),
        )
        claim(
            f"hx_{key}_zero_flow_form_square_and_regular",
            e["zero_flow_square"] and e["zero_flow_rank"] == e["dimension"],
        )
    for key, flow in triggers.items():
        claim(f"registered_dormancy_trigger_flows({key})", flow > 0, f"{flow}")


def run_b31_claims(claim: Claims, b31: Mapping[str, Any], nl: Mapping[str, Any]) -> None:
    """Spec B31 (b), (i) (Q-S9 addendum, 2026-09-25): why a `Q = 0` flash fed a saturated product
    is rank deficient in the declared form, and why the companions are not."""
    tiny = mpf("1e-25")
    claim(
        "b31_upstream_root_is_dz12s",
        t05.ph_solve((mpf(1),) * NC, P_R, mpf(30000))["T"] == nl["DZ-12"]["root_T"],
    )
    for key, e in b31.items():
        label, dp_text = key.split("/dp=")
        dp = mpf(dp_text)
        chain = B31_CHAINS[label]
        claim(f"b31_{key}_closed_form_rows_vanish", e["residual_max"] <= tiny)
        if dp == 0:
            claim(
                f"b31_{key}_declared_rank_deficit_one_per_downstream_flash",
                e["rank"] == e["dimension"] - len(chain),
                f"{e['rank']} of {e['dimension']}",
            )
            expected_left = sorted(
                r
                for u in e["flashes"]
                for r in (
                    *(t05.rid(u, "PHF-equilibrium", c) for c in COMPONENTS),
                    e["flashes"][u]["absent_ndef_row"],
                )
            )
            claim(
                f"b31_{key}_left_null_space_on_equilibrium_rows",
                e["null_left_support"] == expected_left,
            )
            temperatures = {t05.tid(s_) for _u, _si, so_v, so_l, _p in chain for s_ in (so_v, so_l)}
            claim(
                f"b31_{key}_right_null_space_in_the_products_with_their_T_no_P",
                set(e["null_right_support"]) <= set(e["product_columns"])
                and temperatures <= set(e["null_right_support"])
                and not any(c.endswith(".P") for c in e["null_right_support"]),
                f"{e['null_right_support']}",
            )
        else:
            claim(
                f"b31_{key}_declared_form_square_and_regular",
                e["rank"] == e["dimension"] and e["rcond1"] >= mpf("1e-6"),
                f"{e['rank']} {e['rcond1']}",
            )
        for u, f in e["flashes"].items():
            claim(
                f"b31_{key}_{u}_equilibrium_rows_read_only_the_absent_product",
                f["equilibrium_support"] == f["equilibrium_block_columns"],
                f"{f['equilibrium_support']}",
            )
            claim(
                f"b31_{key}_{u}_block_determinant_is_the_closed_form",
                abs(f["block_det"] - f["block_det_formula"])
                <= mpf("1e-30") * max(mpf(1), abs(f["block_det_formula"])),
            )
            claim(f"b31_{key}_{u}_product_P_is_feed_P_minus_dp", f["product_P"] == f["feed_P"] - dp)
            if dp == 0:
                claim(f"b31_{key}_{u}_on_its_boundary", abs(f["boundary_function"]) <= tiny)
            else:
                # Strictly superheated by 5 % of the dew function or more: the root's regime is
                # VAPOR by admissibility, not by roundoff, and the block determinant is not small.
                claim(
                    f"b31_{key}_{u}_superheated_by_at_least_0.05",
                    f["phase_fed"] == "V" and f["boundary_function"] <= mpf("-0.05"),
                    f"{f['boundary_function']}",
                )


# ============================================================================================
# 9. The document
# ============================================================================================


def doc_split(v, liq) -> dict[str, Any]:
    return {"vapor_mol_per_s": sv(v), "liquid_mol_per_s": sv(liq)}


def build() -> dict[str, Any]:
    grid = kernel_grid()
    jump = jump_case()
    biased = biased_case()
    sc = sc_cases()
    npc = np_cases()
    dz = dz_cases()
    screg = sc_regularity()
    deg = registered_degeneracy()
    r7 = r007_states()
    refusals = registered_refusals()
    inj = injections()
    ks = kernel_states()
    passed = run_claims(grid, jump, biased, sc, npc, dz, screg, deg, r7, refusals, inj, ks)
    nl = nl_cases()
    structure = dormant_structure()
    triggers = registered_dormancy_triggers()
    nl_claim = Claims()
    run_nl_claims(nl_claim, nl, structure, triggers)
    b31 = downstream_flash_cases()
    run_b31_claims(nl_claim, b31, nl)
    passed = [*passed, *nl_claim.passed]

    grid_doc = {}
    for cid, e in grid.items():
        ref = e["ref"]
        grid_doc[cid] = {
            "inputs": {"n_mol_per_s": sv(e["n"]), "P_Pa": s(e["P"]), "H_target_W": s(e["target"])},
            "expected": {
                "status": "ok",
                "T_K": s(ref["T"]),
                "V_mol_per_s": s(ref["V"]),
                "beta": s(ref["beta"]),
                **doc_split(ref["v"], ref["l"]),
                "vapour_fraction_by_component": [s(q) if q is not None else None for q in e["q"]],
            },
            "band": {
                "T_bubble_K": s(e["T_bubble"]),
                "T_dew_K": s(e["T_dew"]),
                "width_K": s(e["T_dew"] - e["T_bubble"]),
            },
            "measured_53_bit": {
                "temperature_route_energy_residual_W": float(e["t_route"]["f"]),
                "temperature_route_rows_ok": bool(e["t_route"]["ok"]),
                "route": e["route_53"],
            },
        }

    def stream_doc(n, t, p):
        return {"n_mol_per_s": sv(n), "T_K": s(mpf(t)), "P_Pa": s(mpf(p))}

    sc_doc = {
        "SC-1": {
            "flowsheet": "U-FEED (0,2,0) 370 K 1.8e5 Pa liquid -> S1 -> U-VLV (P_spec = 1e5 Pa, "
            "inlet LIQUID) -> S2 (vapor_liquid, lifted) -> sink",
            "root": {
                "S2": {
                    **stream_doc(pure_b(2), sc["SC-1"]["valve"]["T"], P_R),
                    **doc_split(
                        sc["SC-1"]["valve"]["split"]["v"], sc["SC-1"]["valve"]["split"]["l"]
                    ),
                    "beta": s(sc["SC-1"]["valve"]["split"]["beta"]),
                }
            },
            "signature": [["U-VLV", "TWO_PHASE"]],
        },
        "SC-2": {
            "flowsheet": "U-FEED (0,2,0) 300 K 1e5 Pa liquid -> S1 -> U-PHF (Q_spec = 42000 W, "
            "dP = 0, inlet LIQUID) -> S2 (vapor), S3 (liquid) -> sinks",
            "root": {
                "S2": stream_doc(sc["SC-2"]["phf"]["split"]["v"], mpf(360), P_R),
                "S3": stream_doc(sc["SC-2"]["phf"]["split"]["l"], mpf(360), P_R),
                "U-PHF.Q": s(mpf(42000)),
            },
            "signature": [["U-PHF", "TWO_PHASE"]],
        },
        "SC-3": {
            "flowsheet": "SC-1's feed and valve; S2 (lifted) -> U-PHF (Q_spec = -1000 W, dP = 0, "
            "inlet lifted) -> S3 (vapor), S4 (liquid) -> sinks",
            "root": {
                "S2": {
                    **stream_doc(pure_b(2), mpf(360), P_R),
                    **doc_split(
                        sc["SC-3"]["valve"]["split"]["v"], sc["SC-3"]["valve"]["split"]["l"]
                    ),
                },
                "S3": stream_doc(sc["SC-3"]["phf"]["split"]["v"], mpf(360), P_R),
                "S4": stream_doc(sc["SC-3"]["phf"]["split"]["l"], mpf(360), P_R),
                "U-PHF.Q": s(mpf(-1000)),
                "U-PHF_beta": s(sc["SC-3"]["phf"]["split"]["beta"]),
            },
            "start": {
                "U-PHF_H_in_read_W": s(sc["SC-3"]["start_H_in_read"]),
                "U-PHF_regime": sc["SC-3"]["start_phf"]["split"]["regime"],
                "U-PHF_T_K": s(sc["SC-3"]["start_phf"]["T"]),
            },
            "first_trial": {
                "T_K": s(sc["SC-3"]["trial_T"]),
                "rho_TP": sc["SC-3"]["trial_rho_TP"],
                "rho_PH": sc["SC-3"]["trial_rho_PH"]["regime"],
                "rho_PH_beta": s(sc["SC-3"]["trial_rho_PH"]["beta"]),
                "rho_PH_T_K": s(sc["SC-3"]["trial_rho_PH"]["T"]),
            },
            "signatures": {
                "opening": [["U-VLV", "TWO_PHASE"], ["U-PHF", "LIQUID"]],
                "final": [["U-VLV", "TWO_PHASE"], ["U-PHF", "TWO_PHASE"]],
            },
        },
        "SC-4": {
            "flowsheet": "U-FEED (0,2,0) 300 K 1e5 Pa liquid -> S1 -> U-PHF1 (Q = 42000 W) -> "
            "S2 (vapor) -> U-PHF2 (Q = -15000 W, inlet VAPOR) -> S4 (vapor), S5 "
            "(liquid) -> sinks; U-PHF1 S3 (liquid) -> U-PUMP (P_out = 1.5e5 Pa, "
            "efficiency 0.75) -> S6 -> sink",
            "root": {
                "S2": stream_doc(sc["SC-4"]["phf1"]["split"]["v"], mpf(360), P_R),
                "S3": stream_doc(sc["SC-4"]["phf1"]["split"]["l"], mpf(360), P_R),
                "S4": stream_doc(sc["SC-4"]["phf2"]["split"]["v"], mpf(360), P_R),
                "S5": stream_doc(sc["SC-4"]["phf2"]["split"]["l"], mpf(360), P_R),
                "S6": stream_doc(
                    sc["SC-4"]["pump"]["outlet"]["n"],
                    sc["SC-4"]["pump"]["outlet"]["T"],
                    sc["SC-4"]["pump"]["outlet"]["P"],
                ),
                "U-PHF1.Q": s(mpf(42000)),
                "U-PHF2.Q": s(mpf(-15000)),
                "U-PUMP.W": s(sc["SC-4"]["pump"]["work"]),
            },
            "r007": {
                "U-PHF2.inlet_tp_gap_K": s(sc["SC-4"]["phf2_inlet_tp_gap_K"]),
                "U-PHF2.inlet_degeneracy_K": s(sc["SC-4"]["phf2_inlet_degeneracy_K"]),
                "U-PUMP.inlet_tp_gap_K": s(sc["SC-4"]["pump_inlet_tp_gap_K"]),
            },
            "signature": [["U-PHF1", "TWO_PHASE"], ["U-PHF2", "TWO_PHASE"]],
        },
    }
    np_doc = {}
    for cid, e in npc.items():
        np_doc[cid] = {
            "why": e["why"],
            "flowsheet": f"U-FEED {[s(x) for x in e['n']]} 300 K 1e5 Pa liquid -> S1 -> U-PHF "
            f"(Q_spec = {s(e['Q'])} W, dP = 0, inlet LIQUID) -> S2, S3 -> sinks",
            "root": {
                "T_K": s(e["ref"]["T"]),
                "V_mol_per_s": s(e["ref"]["V"]),
                **doc_split(e["ref"]["v"], e["ref"]["l"]),
            },
            "band": {
                "T_bubble_K": s(e["T_bubble"]),
                "T_dew_K": s(e["T_dew"]),
                "width_K": s(e["width"]),
            },
            "degeneracy_K": s(e["degeneracy_K"]),
            "degenerate": e["degenerate"],
            "measured_53_bit_traversal_route": "bracket" if e["t_route_53"]["ok"] else "band",
            "measured_53_bit_fresh_flash_at_nearest_double": {
                "products_energy_error_W": float(e["fresh_products_energy_error_W"]),
                "feed_vapour_flow_error_mol_per_s": float(e["fresh_feed_V_error"]),
            },
        }
    dz_doc = {}
    for cid, e in dz.items():
        dz_doc[cid] = {
            "full_form": {
                "dimension": e["full_dimension"],
                "rank": e["full_rank"],
                "identically_zero_rows": e["identically_zero_rows"],
            },
            "zero_flow_form": {
                "rows": e["zero_flow_rows"],
                "columns": e["zero_flow_columns"],
                "dimension": len(e["zero_flow_columns"]),
                "rcond1_scaled": s(e["zero_flow_rcond1"], 6),
            },
            "label": e["label"],
            "root": {k: s(v) for k, v in e["state"].items()},
        }
        if cid == "DZ-3":
            dz_doc[cid]["start"] = {k: s(v) for k, v in e["start"].items()}
    deg_doc = {
        cid: {k: s(v, 8) for k, v in case.items() if not k.startswith("_")}
        for cid, case in deg.items()
    }
    r7_doc = {
        cid: {
            "n_mol_per_s": sv(e["n"]),
            "T_K": s(e["T"]),
            "P_Pa": s(e["P"]),
            "declared_phase": {"L": "LIQUID", "V": "VAPOR"}[e["phase"]],
            "tp_gap_K": s(e["tp_gap_K"], 12),
            "degeneracy_K": s(e["degeneracy_K"], 12),
            "admitted": e["admitted"],
            "why": e["why"],
        }
        for cid, e in r7.items()
    }
    floors: dict[str, Any] = {}
    for label in ("band_route", "chosen"):
        et, ev_, eq = mpf(0), mpf(0), mpf(0)
        for e in grid.values():
            r = e[label]
            et = max(et, abs(mpf(r["T"]) - e["ref"]["T"]))
            ev_ = max(ev_, abs(mpf(sum(r["v"])) - e["ref"]["V"]))
            eq = max(eq, max(abs(mpf(r["v"][i]) / e["n"][i] - e["q"][i]) for i in flowing(e["n"])))
        floors[label] = {"T_K": s(et, 3), "V_mol_per_s": s(ev_, 3), "q": s(eq, 3)}
    tr, br = biased["t_route"], biased["band_route"]
    return {
        "meta": {
            "package": "T05b",
            "generator": "docs/derivations/scripts/t05b_reference.py",
            "specification": "docs/derivations/T05b-limitations-spec.md",
            "adr": "docs/adr/0012-saturation-band-ph-contract-zero-flow.md",
            "precision": "mpmath 40 significant digits; values written to 20",
            "reads": {"benchmarks/t05/reference_values.yaml": T05_YAML_SHA256},
            "classes": {
                "closed_form": "expectations",
                "measured_53_bit": "a transcription of the published algorithms in doubles; "
                "never an expectation",
                "generator_claims": "re-derived by --check",
            },
        },
        "tolerances": {
            "molar_flow": s(TAU_FLOW),
            "molar_flow_squared": s(TAU_EQ),
            "heat_rate": s(TAU_E),
            "temperature": s(TAU_T),
            "admissibility_epsilon": s(EPS_ADM),
            "grid": {k: s(v) for k, v in GRID_TOL.items()},
            "coupled_allowances": {k: s(v) for k, v in ALLOW.items()},
            "band_route": {
                "beta_width_floor": "2^-60",
                "max_beta_evaluations": MAX_BAND_EVALUATIONS,
                "max_temperature_evaluations": MAX_EVALUATIONS,
            },
        },
        "kernel_grid": grid_doc,
        "kernel_grid_measured_53_bit_floors": {
            "note": "max over the 40 grid states of |kernel - reference|: the band route alone, "
            "and the route the kernel takes (the temperature route when its rows pass)",
            **floors,
        },
        "kernel_doubles": {
            "JUMP": {
                "definition": "SYN-001 with every vapour enthalpy + 1000 J/mol above 360 K "
                "(evaluate_phase only; flash, lnK and liquid enthalpies unchanged)",
                "inputs": {
                    "n_mol_per_s": sv(jump["n"]),
                    "P_Pa": s(jump["P"]),
                    "H_target_W": s(jump["target"]),
                },
                "jump_W": s(jump["jump_W"]),
                "expected": {"status": "not_converged", "code": "ph_ill_conditioned"},
            },
            "BIASED": {
                "definition": "SYN-001 whose TP flash returns beta + 1e-5 (x, y recomputed from "
                "it) whenever the provider's answer is two-phase",
                "inputs": "PHF-1's (T05 §5.3): (1,1,1) mol/s, 300 K, 1e5 Pa, LIQUID; Q = 50000 W",
                "expected": {
                    "status": "ok",
                    "route": "band",
                    "T_K": s(biased["ref_T"]),
                    **doc_split(biased["ref_split"]["v"], biased["ref_split"]["l"]),
                },
                "measured_53_bit": {
                    "temperature_route_T_K": tr["T"],
                    "temperature_route_energy_residual_W": tr["f"],
                    "temperature_route_max_equilibrium_row": tr["rows"][1],
                    "band_route_T_K": br["T"],
                },
            },
        },
        "single_component_cases": sc_doc,
        "single_component_regularity": {
            cid: {
                "dimension": e["dimension"],
                "rank": e["rank"],
                "rcond1_scaled": s(e["rcond1"], 6),
            }
            for cid, e in screg.items()
        },
        "near_pure_cases": np_doc,
        "dormant_cases": dz_doc,
        "degeneracy_at_registered_states_K": deg_doc,
        "r007_states": r7_doc,
        "injections": {
            cid: {k: (s(v) if not isinstance(v, str) else v) for k, v in e.items()}
            for cid, e in inj.items()
        },
        "contract_kernel_states": {
            cid: {
                "split": "U-VLV's outlet (PH-type, heater style), frozen LIQUID at the trial",
                "feed_mol_per_s": sv(e["n"]),
                "T_K": s(e["T"]),
                "P_Pa": s(e["P"]),
                "vapor_mol_per_s": sv(e["v"]),
                "liquid_mol_per_s": sv(e["l"]),
                "H_split_W": s(e["H_split"]),
                "tp_regime": e["rho_TP"],
                "ph_closure": e["ph_status"]
                if e["ph_status"] != "ok"
                else f"ok via {e['ph_route']}",
                "expected_regime": e["rho"],
                **(
                    {"expected_T_K": s(e["rho_T"]), "expected_beta": s(e["rho_beta"])}
                    if "rho_T" in e
                    else {}
                ),
                "expected_record": e["record"],
            }
            for cid, e in ks.items()
        },
        "t05_registered_refusals_degeneracy_K": {
            cid: s(e["degeneracy_K"], 8) for cid, e in refusals.items()
        },
        **nl_documents(nl, structure, triggers),
        "downstream_flash_cases": {
            "_about": "Spec B31 (b), (i) (Q-S9 addendum, 2026-09-25): U-PHF at DZ-12's root "
            "(30 000 W) feeding Q = 0 flashes (CH-UP: U-PHF2 on S2; CH-3: U-PHF2, U-PHF3 in "
            "series; BUB: U-PHF4 on the liquid product S3), each with pressure drop dp, in the "
            "declared lifted form at the closed-form root (the feed passed through at its own T, "
            "P_in - dp; the other product zero). boundary_function: sum y/K - 1 (fed a vapour) "
            "or sum K x - 1 (fed a liquid) at the product's T and P; block_det: the equilibrium "
            "rows over the absent product's flows, its total substituted",
            "downstream_pressure_drop_Pa": s(B31_DP),
            **{
                key: {
                    "dimension": e["dimension"],
                    "declared_rank": e["rank"],
                    "rcond1_scaled": s(e["rcond1"], 6),
                    "null_right_support": e["null_right_support"],
                    "null_left_support": e["null_left_support"],
                    "flashes": {
                        u: {
                            "fed": {"V": "vapor", "L": "liquid"}[f["phase_fed"]],
                            "boundary_function": s(f["boundary_function"]),
                            "block_det": s(f["block_det"], 12),
                            "product_P_Pa": s(f["product_P"]),
                        }
                        for u, f in e["flashes"].items()
                    },
                }
                for key, e in b31.items()
            },
        },
        "generator_claims": {"count": len(passed), "names": passed},
    }


def form_doc(form: Mapping[str, Any], with_ids: bool = True) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "dimension": len(form["columns"]),
        "rows_count": len(form["rows"]),
        "rank": form["rank"],
        "rcond1_scaled": s(form["rcond1"], 6),
    }
    if with_ids:
        doc = {"rows": list(form["rows"]), "columns": list(form["columns"]), **doc}
    return doc


NL_FLOWSHEETS = {
    "DZ-6": "U-FEED (0,0,0) 330 K 1e5 Pa liquid -> S1 -> U-PUMP (P_out = 1.5e5 Pa, efficiency "
    "0.75) -> S2 -> sink",
    "DZ-7": "U-FEED (0,0,0) 290 K 1e5 Pa -> S1 -> U-HX hot side (LIQUID) -> S2 -> sink; U-FEED2 "
    "(1,1,1) 300 K 1e5 Pa -> S3 -> U-HX cold side (LIQUID) -> S4 -> sink; specification duty, "
    "Q_spec = 0 W",
    "DZ-8": "U-FEED (0,0,0) 350 K 1e5 Pa -> S1 -> U-HX hot side (LIQUID) -> S2 -> sink; U-FEED2 "
    "(0,0,0) 300 K 1e5 Pa -> S3 -> U-HX cold side (LIQUID) -> S4 -> sink; specification "
    "hot_outlet_temperature, T_spec = 345 K",
    "DZ-9": "U-FEED (0,0,0) 330 K 1e5 Pa -> S1, U-FEED2 (0,0,0) 310 K 1e5 Pa -> S2; U-MIX (inlets "
    "S1, S2 in that wiring order) -> S3 -> sink",
    "DZ-10": "DZ-3 with U-VLV replaced by U-PUMP: U-FEED (1,1,1) 300 K 1e5 Pa liquid -> S1 -> "
    "U-PHF (Q_spec = 50000 W, dP = 0, inlet LIQUID) -> S2 (vapor) -> sink; S3 (liquid) -> "
    "U-SPLIT (r = 0) -> S4 (recycle, dormant) -> U-PUMP (P_out = 1.5e5 Pa, efficiency 0.75) -> "
    "S5 -> sink; S6 (purge) -> sink",
    "DZ-11": "DZ-7 with Q_spec = 1000 W, solved from DZ-7's root (the traversal refuses: "
    "specification_unsatisfiable_with_dormant_side)",
    "DZ-2C": "DZ-2 with Q_spec = 1000 W, solved from DZ-2's root (the traversal refuses: "
    "duty_into_dormant_stream)",
    "DZ-12": "U-FEED (1,1,1) 300 K 1e5 Pa liquid -> S1 -> U-PHF (Q_spec = 30000 W, dP = 0, inlet "
    "LIQUID) -> S2 (vapor), S3 (liquid); S2 -> U-HX hot side (VAPOR) -> S4 -> sink; U-FEED2 "
    "(1,1,1) 300 K 1e5 Pa -> S5 -> U-HX cold side (LIQUID) -> S6 -> sink; U-HX specification "
    "duty, Q_spec = 0 W; S3 -> sink. Solved from the registered start",
}


def nl_documents(nl, structure, triggers) -> dict[str, Any]:
    """The YAML sections of the amendment (spec §7.6-§7.10, §12.8)."""
    registry: dict[str, Any] = {}
    for model, entries in NONLIFTED_FORMS.items():
        registry[model] = [
            {
                "item": f"<U>.{e['outlet']}",
                "trigger": f"every stream of port {e['trigger']} exactly dormant",
                "swapped_row": f"<U>:{e['swapped']}",
                "label_row": "<U>:zero-flow-label" + (f":{e['suffix']}" if e["suffix"] else ""),
                "label": f"T({e['outlet']}) - T(first stream of {e['label']})",
                "declared_phase": e["declared_phase"],
            }
            for e in entries
        ]
    cases: dict[str, Any] = {}
    for cid in ("DZ-6", "DZ-7", "DZ-8", "DZ-9", "DZ-10", "DZ-12"):
        e = nl[cid]
        cases[cid] = {
            "flowsheet": NL_FLOWSHEETS[cid],
            "signature": e["signature"],
            "items": [f["item"] for f in e["forms"]],
            "label_rows": {
                f["label_row"]: {"T_out": f["T_out"], "T_label": f["T_label"]} for f in e["forms"]
            },
            "swapped_rows": [f["swapped_row"] for f in e["forms"]],
            "eliminated_rows": e["eliminated_rows"],
            "declared_form": {
                **form_doc(e["full_form"], with_ids=False),
                "dormant_T_out_rows": e["T_out_rows"],
            },
            "zero_flow_form": form_doc(e["zero_flow_form"]),
            "root": {k: s(v) for k, v in e["state"].items()},
        }
    cases["DZ-7"]["terminal_differences_if_judged_K"] = {
        k: s(v) for k, v in nl["DZ-7"]["terminal_differences_K"].items()
    }
    cases["DZ-10"]["start"] = {k: s(v) for k, v in nl["DZ-10"]["start"].items()}
    cases["DZ-10"]["phf1_T_K"] = s(nl["DZ-10"]["phf1"]["T"])
    d12, a0 = nl["DZ-12"], nl["DZ-12"]["attempt0"]
    cases["DZ-12"].update(
        {
            "start": {k: s(v) for k, v in d12["start"].items()},
            "attempt0": {
                "signature": a0["signature"],
                "core_outcome": "CONVERGED at iteration 0 (every row of the attempt vanishes "
                "at the start)",
                "form": form_doc(a0["form"]),
                "form_without_the_hx_zero_flow_form": form_doc(
                    a0["form_without_hx_form"], with_ids=False
                ),
                "closure": "U-PHF's LIQUID branch inadmissible: sum x K at 400 K = "
                + s(a0["liquid_branch_bubble_value"], 12),
                "kernel_H_split_W": s(a0["H_split_W"]),
                "kernel": {
                    "status": a0["kernel"]["status"],
                    "route": a0["kernel"]["route"],
                    "regime": a0["kernel"]["split"]["regime"],
                    "T_K": s(a0["kernel"]["T"]),
                },
            },
            "attempt1": {
                "signature": [["U-PHF", "TWO_PHASE"]],
                "opening_message": "phase_update(inadmissible(S1, all_liquid))",
                "opening_with_outlet_reset": form_doc(
                    d12["attempt1_opening"]["with_reset"], with_ids=False
                ),
                "opening_without_outlet_reset": form_doc(
                    d12["attempt1_opening"]["without_reset"], with_ids=False
                ),
            },
            "root_checks": {
                "hot_outlet_dew_function": s(d12["hot_outlet_dew_value"], 6),
                "hot_outlet_degeneracy_K": s(d12["hot_outlet_degeneracy_K"], 8),
                "hot_end_K": s(d12["hot_end_K"], 12),
                "cold_end_K": s(d12["cold_end_K"], 12),
            },
        }
    )
    conflicts: dict[str, Any] = {}
    for cid, message in (
        ("DZ-11", "zero_flow_conflict(U-HX:HX-energy-hot)"),
        ("DZ-2C", "zero_flow_conflict(U-PHF:PHF-duty)"),
    ):
        e = nl[cid]
        conflicts[cid] = {
            "flowsheet": NL_FLOWSHEETS[cid],
            "Q_spec_W": s(e["Q_spec_W"]),
            "signature": e["signature"],
            "zero_flow_form": form_doc(e["zero_flow_form"]),
            "start": {k: s(v) for k, v in e["start"].items()},
            "end_state": {k: s(v) for k, v in e["state"].items()},
            "swapped_row_at_end_W": {k: s(v) for k, v in e["swapped_values"].items()},
            "expected": {"outcome": "SPECIFICATION_CONFLICT", "message": message},
        }
    conflicts["DZ-11"]["start_rows_not_satisfied"] = nl["DZ-11"]["start_zero_flow_rows_nonzero"]
    injections = {
        "INJ-B4": {
            "state": "DZ-11's end state, given to the verifier",
            "residual_U-HX:HX-energy-hot_W": s(nl["DZ-11"]["swapped_values"]["U-HX:HX-energy-hot"]),
            "residual_U-HX:zero-flow-label:hot_K": s(
                nl["DZ-11"]["label_values"]["U-HX:zero-flow-label:hot"]
            ),
            "energy_balance_U-HX_in_minus_out_W": s(nl["DZ-11"]["energy_balance_U-HX_W"]),
            "energy_balance_envelope_in_minus_out_W": s(nl["DZ-11"]["energy_balance_envelope_W"]),
        },
        "INJ-B5": {
            "state": "DZ-9's root with S3.T = 310 K (inlet 1's temperature, not inlet 0's)",
            "residual_U-MIX:zero-flow-label_K": s(nl["INJ-B5"]["label_residual_K"]),
            "compiled_rows_max": s(nl["INJ-B5"]["compiled_rows_max"]),
        },
    }
    structure_doc = {
        "models": {
            model: {
                column: {"rows": rows, "determined_by": DORMANT_COVERAGE[model][column]}
                for column, rows in columns.items()
            }
            for model, columns in structure["models"].items()
        },
        "exchanger_patterns": {
            key: {
                "dormant_T_out_rows": e["dormant_T_rows"],
                "items": e["forms"],
                "declared_rank": e["full_rank"],
                "dimension": e["dimension"],
                "zero_flow_rank": e["zero_flow_rank"],
            }
            for key, e in structure["exchanger"].items()
        },
    }
    return {
        "dormancy_forms": registry,
        "dormant_non_lifted_cases": cases,
        "zero_flow_conflicts": conflicts,
        "dormant_non_lifted_injections": injections,
        "dormant_outlet_structure": structure_doc,
        "registered_dormancy_trigger_flows_mol_per_s": {k: s(v) for k, v in triggers.items()},
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
