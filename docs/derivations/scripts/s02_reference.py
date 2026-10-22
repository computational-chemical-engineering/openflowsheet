"""Design-lane reference generator for the S02 specification (MESH column on SYN-001).

Everything here follows from the SYN-001 definitions (``docs/derivations/SYN-001.md`` §2-§3) and
``docs/derivations/S02-spec.md`` alone, evaluated with mpmath at 50 significant digits. It imports
nothing from ``openflowsheet`` or ``benchmarks``: the numbers it emits are the *expectations* the
S02 tests judge the implementation against.

**Independence.** The implementation writes S01's 14 division-free rows per stage plus S02's
division-free specification rows and total-condenser block (spec §2-§3). This generator solves a
*different* formulation of the same equations -- 8 unknowns per equilibrium stage
``(l_i, v_i, T, Q)``, equilibrium and ratio specifications in quotient form, the total condenser
reduced to ``(phi, T_c, Q_c)`` -- by its own damped Newton with complex-step derivatives, follows
spec §7's straight specification path in equal steps, and then evaluates the implementation's
division-free rows at its root as a claim. Amendment 2 (spec §18, WO-G) adds §18.2's bubble-point
easy endpoint by its own sweeps (stopped at 1e-30 K) and V-M2 (duty, duty)'s second root R2; those
keys and claims are appended after the earlier ones, which stay byte-identical.

    python docs/derivations/scripts/s02_reference.py --check
    python docs/derivations/scripts/s02_reference.py --emit <path of the committed JSON>

``--check`` re-derives every claim, refuses to continue when one fails, and compares the result
with the committed file byte for byte. ``--emit`` runs the same claims and writes the file only
when all of them hold.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from mpmath import mp, mpc, mpf

mp.dps = 50
DEFAULT_OUT = Path(__file__).with_name("s02_reference.json")
DIGITS = 25

# -- SYN-001 constants (docs/derivations/SYN-001.md; plan §3.1) ------------------------------------
R = mpf("8.31446261815324")
T_REF, P_REF, C_P = mpf(300), mpf(100000), mpf(100)
T_BOIL = (mpf(320), mpf(360), mpf(400))
L_VAP = (mpf(25000), mpf(30000), mpf(35000))
V_MOL = (mpf("1e-4"),) * 3
T_MIN, T_MAX, P_MIN, P_MAX = mpf(280), mpf(440), mpf(50000), mpf(200000)
NC = 3
NEWTON_TOL = mpf("1e-40")
# spec §6: profile band fractions, CMO floor, total-condenser opening split
BETA_A, BETA_B, FLOOR, PHI0 = mpf("0.1"), mpf("0.9"), mpf("0.1"), mpf("0.5")
PATH_STEPS = 16  # spec §11: the generator's straight specification path
SIGMA_REGULAR = mpf("1e-4")  # spec §9: registered spec sets are regular above this
SIGMA_SINGULAR = mpf("1e-30")  # spec §5 S3: the (distillate, bottoms) pair is singular below this
FLOW_MIN, MARGIN_MIN = mpf("1e-3"), mpf("0.02")
SCALE_T, SCALE_Q = mpf(100), mpf(10000)

CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise SystemExit(f"claim failed: {text}")
    CLAIMS.append(text)


def ln_k(t: Any, p: Any, i: int) -> Any:
    return (
        mp.log(P_REF / p)
        + (L_VAP[i] / R) * (1 / T_BOIL[i] - 1 / t)
        + V_MOL[i] * (p - P_REF) / (R * t)
    )


def k_val(t: Any, p: Any, i: int) -> Any:
    return mp.exp(ln_k(t, p, i))


def h_liq(t: Any, p: Any, i: int) -> Any:
    return C_P * (t - T_REF) + V_MOL[i] * (p - P_REF)


def h_vap(t: Any, i: int) -> Any:
    return C_P * (t - T_REF) + L_VAP[i]


def h_stream(n: Sequence[Any], t: Any, p: Any, phase: str) -> Any:
    if phase == "LIQUID":
        return sum(n[i] * h_liq(t, p, i) for i in range(NC))
    return sum(n[i] * h_vap(t, i) for i in range(NC))


def s(x: Any) -> str:
    return mp.nstr(mpf(x), DIGITS, min_fixed=-mp.inf, max_fixed=mp.inf) if x != 0 else "0"


def sv(xs: Sequence[Any]) -> list[str]:
    return [s(x) for x in xs]


# -- registered cases (spec §9) --------------------------------------------------------------------
def inlet(port: str, n: Sequence[str], t: str, p: str, phase: str, stage: int) -> dict[str, Any]:
    return {
        "port": port,
        "n": [mpf(v) for v in n],
        "T": mpf(t),
        "P": mpf(p),
        "phase": phase,
        "stage": stage,
    }


def profile(n_st: int, p0: str, dp: str) -> list[Any]:
    return [mpf(p0) + j * mpf(dp) for j in range(n_st)]


FEED = ("0.3", "0.4", "0.3")
CASES: dict[str, dict[str, Any]] = {
    "M1": {
        "N": 7,
        "condenser": "partial",
        "reboiler": "partial",
        "P": profile(7, "100000", "1000"),
        "Q": {},
        "inlets": [inlet("feed", FEED, "340", "104000", "LIQUID", 4)],
        "spec": {"condenser": ("reflux_ratio", "2"), "reboiler": ("boilup_ratio", "1.5")},
        "signature": ["TWO_PHASE"] * 7,
    },
    "M2": {
        "N": 7,
        "condenser": "total",
        "reboiler": "partial",
        "P": profile(7, "100000", "1000"),
        "Q": {},
        "inlets": [inlet("feed", FEED, "340", "104000", "LIQUID", 4)],
        "spec": {"condenser": ("reflux_ratio", "1.5"), "reboiler": ("bottoms_rate", "0.55")},
        "signature": ["SATURATED_LIQUID"] + ["TWO_PHASE"] * 6,
    },
    "M3": {
        "N": 5,
        "condenser": "none",
        "reboiler": "partial",
        "P": profile(5, "100000", "1000"),
        "Q": {},
        "inlets": [inlet("top", FEED, "300", "100000", "LIQUID", 1)],
        "spec": {"reboiler": ("duty", "30000")},
        "signature": ["TWO_PHASE"] * 5,
    },
    "M4": {
        "N": 5,
        "condenser": "partial",
        "reboiler": "none",
        "P": profile(5, "100000", "1000"),
        "Q": {},
        "inlets": [inlet("bottom", FEED, "385", "104000", "VAPOR", 5)],
        "spec": {"condenser": ("distillate_rate", "0.5")},
        "signature": ["TWO_PHASE"] * 5,
    },
}
SLOT_OF = {
    "reflux_ratio": "RR",
    "boilup_ratio": "BR",
    "distillate_rate": "D",
    "bottoms_rate": "B",
    "duty": "Q",
}


def eq_stages(case: dict[str, Any]) -> list[int]:
    return list(range(2 if case["condenser"] == "total" else 1, case["N"] + 1))


def is_total(case: dict[str, Any]) -> bool:
    return case["condenser"] == "total"


def unpack(case: dict[str, Any], x: Sequence[Any]) -> dict[str, Any]:
    st: dict[str, Any] = {"l": {}, "v": {}, "T": {}, "Q": {}}
    k = 0
    for j in eq_stages(case):
        st["l"][j], st["v"][j] = list(x[k : k + NC]), list(x[k + NC : k + 2 * NC])
        st["T"][j], st["Q"][j] = x[k + 2 * NC], x[k + 2 * NC + 1]
        k += 2 * NC + 2
    if is_total(case):
        st["phi"], st["Tc"], st["Q"][1] = x[k], x[k + 1], x[k + 2]
    return st


def pack(case: dict[str, Any], st: dict[str, Any]) -> list[Any]:
    out: list[Any] = []
    for j in eq_stages(case):
        out += list(st["l"][j]) + list(st["v"][j]) + [st["T"][j], st["Q"][j]]
    if is_total(case):
        out += [st["phi"], st["Tc"], st["Q"][1]]
    return out


def col_scales(case: dict[str, Any]) -> list[Any]:
    out: list[Any] = []
    for _ in eq_stages(case):
        out += [mpf(1)] * (2 * NC) + [SCALE_T, SCALE_Q]
    if is_total(case):
        out += [mpf(1), SCALE_T, SCALE_Q]
    return out


def inflows(case: dict[str, Any], st: dict[str, Any], j: int) -> list[tuple[Any, ...]]:
    """Streams entering equilibrium stage j as (n, T, P, phase): spec §1-§2."""
    p, out = case["P"], []
    if j - 1 >= 1:
        if is_total(case) and j - 1 == 1:
            reflux = [st["phi"] * st["v"][2][i] for i in range(NC)]
            out.append((reflux, st["Tc"], p[0], "LIQUID"))
        else:
            out.append((st["l"][j - 1], st["T"][j - 1], p[j - 2], "LIQUID"))
    if j + 1 <= case["N"]:
        out.append((st["v"][j + 1], st["T"][j + 1], p[j], "VAPOR"))
    for f in case["inlets"]:
        if f["stage"] == j:
            out.append((f["n"], f["T"], f["P"], f["phase"]))
    return out


def slot_value(case: dict[str, Any], st: dict[str, Any], j: int, kind: str) -> Any:
    """The specified quantity of slot kind at stage j (quotient form for the ratios)."""
    if kind == "Q":
        return st["Q"][j]
    if kind == "T":
        return st["T"][j]
    if j == 1 and is_total(case):
        v2 = sum(st["v"][2])
        return {"RR": st["phi"] / (1 - st["phi"]), "D": (1 - st["phi"]) * v2}[kind]
    big_l, big_v = sum(st["l"][j]), sum(st["v"][j])
    return {"RR": big_l / big_v, "D": big_v, "BR": big_v / big_l, "B": big_l}[kind]


def residual(
    case: dict[str, Any], x: Sequence[Any], slots: dict[int, tuple[str, Any]], sig: Sequence[str]
) -> list[Any]:
    """The generator's formulation (scaled rows): spec §11."""
    st, p, rows = unpack(case, x), case["P"], []
    for j in eq_stages(case):
        ins, liq, vap, t = inflows(case, st, j), st["l"][j], st["v"][j], st["T"][j]
        rows += [sum(f[0][i] for f in ins) - liq[i] - vap[i] for i in range(NC)]
        if sig[j - 1] == "TWO_PHASE":
            big_l, big_v = sum(liq), sum(vap)
            rows += [vap[i] / big_v - k_val(t, p[j - 1], i) * liq[i] / big_l for i in range(NC)]
        elif sig[j - 1] == "LIQUID":
            rows += list(vap)
        else:
            rows += list(liq)
        h_in = sum(h_stream(*f) for f in ins)
        h_out = h_stream(vap, t, p[j - 1], "VAPOR") + h_stream(liq, t, p[j - 1], "LIQUID")
        rows.append((st["Q"][j] + h_in - h_out) / SCALE_Q)
        kind, value = slots[j]
        scale = {"Q": SCALE_Q, "T": SCALE_T}.get(kind, mpf(1))
        rows.append((slot_value(case, st, j, kind) - value) / scale)
    if is_total(case):
        v2, tc = st["v"][2], st["Tc"]
        rows.append(sum(k_val(tc, p[0], i) * v2[i] for i in range(NC)) / sum(v2) - 1)
        h_c = h_stream(v2, st["T"][2], p[1], "VAPOR") - h_stream(v2, tc, p[0], "LIQUID")
        rows.append((st["Q"][1] + h_c) / SCALE_Q)
        kind, value = slots[1]
        scale = SCALE_Q if kind == "Q" else mpf(1)
        rows.append((slot_value(case, st, 1, kind) - value) / scale)
    return rows


def jacobian(fun: Callable[[list[Any]], list[Any]], x: Sequence[Any]) -> Any:
    n, h = len(x), mpf("1e-60")
    jac = mp.matrix(n, n)
    for k in range(n):
        xp = [mpc(xi) for xi in x]
        xp[k] += mpc(0, h)
        col = fun(xp)
        for r in range(n):
            jac[r, k] = mp.im(col[r]) / h
    return jac


def newton(fun: Callable[[list[Any]], list[Any]], x0: Sequence[Any]) -> list[Any]:
    x, n = list(x0), len(x0)
    for _ in range(100):
        f = fun(x)
        norm = max(abs(r) for r in f)
        if norm < NEWTON_TOL:
            return x
        dx = mp.lu_solve(jacobian(fun, x), mp.matrix([-r for r in f]))
        alpha = mpf(1)
        while alpha > mpf("1e-8"):
            trial = [x[k] + alpha * dx[k] for k in range(n)]
            try:
                ft = fun(trial)
                if max(abs(r) for r in ft) < (1 - alpha / 4) * norm:
                    x = trial
                    break
            except (ZeroDivisionError, ValueError):
                pass
            alpha /= 2
        else:
            raise SystemExit("generator Newton failed: line search")
    raise SystemExit("generator Newton failed: budget")


def sigma_min(case: dict[str, Any], x: Sequence[Any], slots: dict, sig: Sequence[str]) -> Any:
    jac = jacobian(lambda y: residual(case, y, slots, sig), x)
    scales = col_scales(case)
    for r in range(jac.rows):
        for k in range(jac.cols):
            jac[r, k] *= scales[k]
    with mp.workdps(40):
        return min(mp.svd_r(jac, compute_uv=False))


# -- spec §6: band temperature, profile, CMO, Thomas -----------------------------------------------
def rr_temperature(z: Sequence[Any], beta: Any, p: Any) -> Any:
    """T(beta) of ADR 0012 D1: root of sum z_i (K_i - 1)/(1 + beta (K_i - 1))."""

    def g(t: Any) -> Any:
        return sum(
            z[i] * (k_val(t, p, i) - 1) / (1 + beta * (k_val(t, p, i) - 1))
            for i in range(NC)
            if z[i] > 0
        )

    return mp.findroot(g, (mpf(250), mpf(500)), solver="anderson")


def thomas(sub: list[Any], diag: list[Any], sup: list[Any], rhs: list[Any]) -> list[Any]:
    n = len(diag)
    c, d = [mpf(0)] * n, [mpf(0)] * n
    c[0], d[0] = sup[0] / diag[0], rhs[0] / diag[0]
    for j in range(1, n):
        m = diag[j] - sub[j] * c[j - 1]
        c[j] = sup[j] / m if j < n - 1 else mpf(0)
        d[j] = (rhs[j] - sub[j] * d[j - 1]) / m
    out = [mpf(0)] * n
    out[-1] = d[-1]
    for j in range(n - 2, -1, -1):
        out[j] = d[j] - c[j] * out[j + 1]
    return out


def feed_total(case: dict[str, Any]) -> tuple[list[Any], Any]:
    tot = [sum(f["n"][i] for f in case["inlets"]) for i in range(NC)]
    return tot, sum(tot)


def initializer(case: dict[str, Any]) -> dict[str, Any]:
    """Spec §6, steps 1-7."""
    n_st, p, inl = case["N"], case["P"], case["inlets"]
    tot, big_f = feed_total(case)
    z = [tot[i] / big_f for i in range(NC)]
    t_a, t_b = rr_temperature(z, BETA_A, p[0]), rr_temperature(z, BETA_B, p[-1])
    prof = [t_a + (t_b - t_a) * mpf(j) / (n_st - 1) for j in range(n_st)]
    l_base = big_f if case["condenser"] != "none" else mpf(0)
    v_base = big_f if case["reboiler"] != "none" else mpf(0)
    big_l = [
        max(
            l_base + sum(sum(f["n"]) for f in inl if f["phase"] == "LIQUID" and f["stage"] <= j),
            FLOOR * big_f,
        )
        for j in range(1, n_st + 1)
    ]
    big_v = [
        max(
            v_base + sum(sum(f["n"]) for f in inl if f["phase"] == "VAPOR" and f["stage"] >= j),
            FLOOR * big_f,
        )
        for j in range(1, n_st + 1)
    ]
    eqs = eq_stages(case)
    st: dict[str, Any] = {"l": {}, "v": {}, "T": {}, "Q": {}}
    for j in eqs:
        st["l"][j], st["v"][j] = [mpf(0)] * NC, [mpf(0)] * NC
    for i in range(NC):
        sr = {j: k_val(prof[j - 1], p[j - 1], i) * big_v[j - 1] / big_l[j - 1] for j in eqs}
        diag = [-(1 + sr[j]) for j in eqs]
        if is_total(case):
            diag[0] += PHI0 * sr[2]
        col = thomas(
            [mpf(1)] * len(eqs),
            diag,
            [sr[j + 1] if j + 1 <= n_st else mpf(0) for j in eqs],
            [-sum(f["n"][i] for f in inl if f["stage"] == j) for j in eqs],
        )
        for k, j in enumerate(eqs):
            st["l"][j][i], st["v"][j][i] = col[k], sr[j] * col[k]
    for j in eqs:
        st["T"][j], st["Q"][j] = prof[j - 1], mpf(0)
    if is_total(case):
        st["phi"], st["Tc"], st["Q"][1] = PHI0, prof[0], mpf(0)
    # Q from the energy rows (spec §6 step 7): the energy row is linear in Q with slope 1.
    x = pack(case, st)
    sig = ["TWO_PHASE"] * n_st
    f0 = residual(case, x, {j: ("Q", mpf(0)) for j in range(1, n_st + 1)}, sig)
    k = 0
    for j in eqs:
        st["Q"][j] = -f0[k + 2 * NC] * SCALE_Q
        k += 2 * NC + 2
    if is_total(case):
        st["Q"][1] = -f0[k + 1] * SCALE_Q
    claim(
        all(st["l"][j][i] > 0 and st["v"][j][i] > 0 for j in eqs for i in range(NC)),
        f"{case['name']}: initializer flows positive",
    )
    return {
        "z": z,
        "T_a": t_a,
        "T_b": t_b,
        "profile": prof,
        "L_cmo": big_l,
        "V_cmo": big_v,
        "state": st,
    }


# -- slots (spec §3, §7) ---------------------------------------------------------------------------
def target_slots(case: dict[str, Any]) -> dict[int, tuple[str, Any]]:
    n_st = case["N"]
    slots = {j: ("Q", mpf(case["Q"].get(j, "0"))) for j in range(1, n_st + 1)}
    if case["condenser"] != "none":
        kind, value = case["spec"]["condenser"]
        slots[1] = (SLOT_OF[kind], mpf(value))
    if case["reboiler"] != "none":
        kind, value = case["spec"]["reboiler"]
        slots[n_st] = (SLOT_OF[kind], mpf(value))
    return slots


def presolve_slots(case: dict[str, Any], prof: Sequence[Any]) -> dict[int, tuple[str, Any]]:
    out = {}
    for j, (kind, value) in target_slots(case).items():
        if kind in ("Q", "D", "B"):
            total_cond = j == 1 and is_total(case)
            out[j] = ("RR", mpf(1)) if total_cond else ("T", prof[j - 1])
        else:
            out[j] = (kind, value)
    return out


# -- checks ----------------------------------------------------------------------------------------
def bubble_margin(liq: Sequence[Any], t: Any, p: Any) -> Any:
    return 1 - sum(k_val(t, p, i) * liq[i] for i in range(NC)) / sum(liq)


def dew_margin(vap: Sequence[Any], t: Any, p: Any) -> Any:
    return 1 - sum(vap[i] / k_val(t, p, i) for i in range(NC)) / sum(vap)


def check_state(name: str, case: dict[str, Any], st: dict[str, Any], sig: Sequence[str]) -> None:
    p = case["P"]
    for j in eq_stages(case):
        t = st["T"][j]
        claim(T_MIN <= t <= T_MAX, f"{name}: stage {j} temperature in the SYN-001 domain")
        if sig[j - 1] == "TWO_PHASE":
            claim(
                min(sum(st["l"][j]), sum(st["v"][j])) > FLOW_MIN
                and min(st["l"][j] + st["v"][j]) > 0,
                f"{name}: stage {j} 2P, L and V > 1e-3",
            )
        elif sig[j - 1] == "LIQUID":
            claim(
                sum(st["l"][j]) > FLOW_MIN and bubble_margin(st["l"][j], t, p[j - 1]) >= MARGIN_MIN,
                f"{name}: stage {j} LIQUID admissible with margin >= 0.02",
            )
        else:
            claim(
                sum(st["v"][j]) > FLOW_MIN and dew_margin(st["v"][j], t, p[j - 1]) >= MARGIN_MIN,
                f"{name}: stage {j} VAPOR admissible with margin >= 0.02",
            )
    if is_total(case):
        claim(
            T_MIN <= st["Tc"] <= T_MAX and 0 < st["phi"] < 1,
            f"{name}: total condenser T in domain, 0 < phi < 1",
        )


def implementation_rows_max(
    case: dict[str, Any], st: dict[str, Any], slots: dict, sig: Sequence[str]
) -> Any:
    """Spec §2-§3's division-free rows at the generator's root (unscaled, SI)."""
    p, worst = case["P"], mpf(0)
    for j in eq_stages(case):
        liq, vap, t = st["l"][j], st["v"][j], st["T"][j]
        big_l, big_v = sum(liq), sum(vap)
        rows = []
        if sig[j - 1] == "TWO_PHASE":
            rows += [vap[i] * big_l - k_val(t, p[j - 1], i) * liq[i] * big_v for i in range(NC)]
        kind, value = slots[j]
        if kind == "RR":
            rows.append(big_l - value * big_v)
        elif kind == "BR":
            rows.append(big_v - value * big_l)
        worst = max([worst] + [abs(r) for r in rows])
    if is_total(case):
        v2, phi = st["v"][2], st["phi"]
        big_v2 = sum(v2)
        rows = [sum(k_val(st["Tc"], p[0], i) * v2[i] for i in range(NC)) - big_v2]
        kind, value = slots[1]
        if kind == "RR":
            rows.append(phi * big_v2 - value * (1 - phi) * big_v2)
        worst = max([worst] + [abs(r) for r in rows])
    return worst


def products(case: dict[str, Any], st: dict[str, Any]) -> dict[str, Any]:
    n_st, p = case["N"], case["P"]
    if is_total(case):
        top = ([(1 - st["phi"]) * st["v"][2][i] for i in range(NC)], st["Tc"], p[0], "LIQUID")
    else:
        top = (st["v"][1], st["T"][1], p[0], "VAPOR")
    bottom = (st["l"][n_st], st["T"][n_st], p[-1], "LIQUID")
    return {"top": top, "bottom": bottom}


def closures(name: str, case: dict[str, Any], st: dict[str, Any]) -> None:
    prod = products(case, st)
    comp = max(
        abs(sum(f["n"][i] for f in case["inlets"]) - prod["top"][0][i] - prod["bottom"][0][i])
        for i in range(NC)
    )
    energy = (
        sum(h_stream(f["n"], f["T"], f["P"], f["phase"]) for f in case["inlets"])
        + sum(st["Q"].values())
        - h_stream(*prod["top"])
        - h_stream(*prod["bottom"])
    )
    claim(
        comp < mpf("1e-38") and abs(energy) < mpf("1e-33"),
        f"{name}: overall component and energy closure",
    )


def record(case: dict[str, Any], st: dict[str, Any]) -> dict[str, Any]:
    stages = []
    for j in range(1, case["N"] + 1):
        if j == 1 and is_total(case):
            v2 = st["v"][2]
            stages.append(
                {
                    "stage": 1,
                    "kind": "total_condenser",
                    "T": s(st["Tc"]),
                    "Q": s(st["Q"][1]),
                    "phi": s(st["phi"]),
                    "reflux": sv([st["phi"] * v2[i] for i in range(NC)]),
                    "distillate": sv([(1 - st["phi"]) * v2[i] for i in range(NC)]),
                }
            )
            continue
        stages.append(
            {
                "stage": j,
                "T": s(st["T"][j]),
                "Q": s(st["Q"][j]),
                "l": sv(st["l"][j]),
                "v": sv(st["v"][j]),
                "L": s(sum(st["l"][j])),
                "V": s(sum(st["v"][j])),
            }
        )
    prod = products(case, st)
    return {
        "stages": stages,
        "top_product": sv(prod["top"][0]),
        "bottom_product": sv(prod["bottom"][0]),
    }


def spec_values(case: dict[str, Any], st: dict[str, Any]) -> dict[str, str]:
    n_st = case["N"]
    out = {"condenser_duty": s(st["Q"][1]), "reboiler_duty": s(st["Q"][n_st])}
    if case["condenser"] != "none":
        out["reflux_ratio"] = s(slot_value(case, st, 1, "RR"))
        out["distillate_rate"] = s(slot_value(case, st, 1, "D"))
    if case["reboiler"] != "none":
        out["boilup_ratio"] = s(slot_value(case, st, n_st, "BR"))
        out["bottoms_rate"] = s(slot_value(case, st, n_st, "B"))
    return out


# -- solve (spec §7 as the generator follows it) ---------------------------------------------------
def solve_case(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    case = CASES[name]
    case["name"] = name
    two = ["TWO_PHASE"] * case["N"]
    init = initializer(case)
    pre_slots = presolve_slots(case, init["profile"])
    fun0 = lambda y: residual(case, y, pre_slots, two)  # noqa: E731
    x0 = newton(fun0, pack(case, init["state"]))
    st0 = unpack(case, x0)
    check_state(f"{name} presolve", case, st0, two)
    claim(sigma_min(case, x0, pre_slots, two) > SIGMA_REGULAR, f"{name}: presolve regular")
    tgt = target_slots(case)
    cont = {j: tgt[j] for j in tgt if pre_slots[j] != tgt[j]}
    p0 = {j: slot_value(case, st0, j, kind) for j, (kind, _) in cont.items()}
    out: dict[str, Any] = {
        "initializer": {
            "z": sv(init["z"]),
            "T_a": s(init["T_a"]),
            "T_b": s(init["T_b"]),
            "profile": sv(init["profile"]),
            "L_cmo": sv(init["L_cmo"]),
            "V_cmo": sv(init["V_cmo"]),
            "l": {str(j): sv(v) for j, v in init["state"]["l"].items()},
            "v": {str(j): sv(v) for j, v in init["state"]["v"].items()},
        },
        "presolve_slots": {str(j): [k, s(v)] for j, (k, v) in sorted(pre_slots.items())},
        "presolve": record(case, st0),
        "continued": {
            str(j): {"kind": cont[j][0], "p0": s(p0[j]), "target": s(cont[j][1])}
            for j in sorted(cont)
        },
    }
    sig = case["signature"]
    stage_sig = [("TWO_PHASE" if g == "SATURATED_LIQUID" else g) for g in sig]
    x = x0
    if all(g == "TWO_PHASE" for g in stage_sig):
        for k in range(1, PATH_STEPS + 1):
            lam = mpf(k) / PATH_STEPS
            slots = dict(tgt)
            for j, (kind, value) in cont.items():
                slots[j] = (kind, value + (1 - lam) * (p0[j] - value))
            x = newton(lambda y, sl=slots: residual(case, y, sl, two), x)
            check_state(f"{name} path step {k}/{PATH_STEPS}", case, unpack(case, x), two)
        claim(True, f"{name}: the straight path stays two-phase at {PATH_STEPS} equal steps")
    else:
        raise SystemExit(f"{name}: a registered flowing case must be two-phase")
    st = unpack(case, x)
    check_state(f"{name} target", case, st, stage_sig)
    closures(name, case, st)
    claim(
        implementation_rows_max(case, st, tgt, stage_sig) < mpf("1e-38"),
        f"{name}: the implementation's division-free rows vanish below 1e-38",
    )
    smin = sigma_min(case, x, tgt, stage_sig)
    claim(smin > SIGMA_REGULAR, f"{name}: target regular, sigma_min > 1e-4")
    out.update(
        {
            "target": record(case, st),
            "signature": sig,
            "spec_values": spec_values(case, st),
            "sigma_min": mp.nstr(smin, 6),
        }
    )
    return out, {"x": x, "st": st, "slots": tgt, "sig": stage_sig, "init": init}


def phase_case() -> dict[str, Any]:
    """Spec §9 P1: M3's stripper at Q_N* = 3 kW. Closed form: every stage LIQUID, l_j = top."""
    case = dict(CASES["M3"], name="P1", spec={"reboiler": ("duty", "3000")})
    n_st, top, p = case["N"], case["inlets"][0], case["P"]
    big_f = sum(top["n"])
    temps, t_prev, p_prev = [], top["T"], top["P"]
    for j in range(1, n_st + 1):
        q = mpf(3000) if j == n_st else mpf(0)
        t_j = t_prev - V_MOL[0] * (p[j - 1] - p_prev) / C_P + q / (big_f * C_P)
        temps.append(t_j)
        t_prev, p_prev = t_j, p[j - 1]
    st: dict[str, Any] = {"l": {}, "v": {}, "T": {}, "Q": {}}
    for j in range(1, n_st + 1):
        st["l"][j], st["v"][j] = list(top["n"]), [mpf(0)] * NC
        st["T"][j], st["Q"][j] = temps[j - 1], mpf(3000) if j == n_st else mpf(0)
    sig = ["LIQUID"] * n_st
    x = pack(case, st)
    tgt = target_slots(case)
    claim(
        max(abs(r) for r in residual(case, x, tgt, sig)) < mpf("1e-45"),
        "P1: the closed form is a root of the generator's rows in signature LIQUID x5",
    )
    check_state("P1", case, st, sig)
    closures("P1", case, st)
    claim(sigma_min(case, x, tgt, sig) > SIGMA_REGULAR, "P1: closed-form root regular")
    claim(
        abs(temps[1] - temps[0] + mpf("0.001")) < mpf("1e-45"),
        "P1: an adiabatic liquid pass-through 1 kPa down cools by exactly 1e-3 K",
    )
    margins = [bubble_margin(st["l"][j], st["T"][j], p[j - 1]) for j in range(1, n_st + 1)]
    return {
        "N": n_st,
        "Q_reboiler": "3000",
        "signature": sig,
        "T": sv(temps),
        "l": sv(top["n"]),
        "bubble_margin_min": mp.nstr(min(margins), 6),
        "top_product": ["+0.0"] * NC,
    }


def null_residual(
    case: dict[str, Any], x: Sequence[Any], slots: dict, sig: Sequence[str], delta: Sequence[Any]
) -> Any:
    jac = jacobian(lambda y: residual(case, y, slots, sig), x)
    prod = jac * mp.matrix(list(delta))
    return max(abs(prod[r]) for r in range(jac.rows)) / max(abs(d) for d in delta)


def circulation(case: dict[str, Any], x: Sequence[Any], j: int, upper_liquid: bool) -> list[Any]:
    """Spec §4.3: the null vector of a (LIQUID over vapour-emitting) or (liquid-emitting over
    VAPOR) pair (j, j+1): a closed internal circulation that every row of both stages admits."""
    st, p = unpack(case, x), case["P"]
    eqs, layout = eq_stages(case), {}
    for k, s_j in enumerate(eqs):
        layout[s_j] = k * (2 * NC + 2)
    if upper_liquid:
        comp = [vi / sum(st["v"][j + 1]) for vi in st["v"][j + 1]]
    else:
        comp = [li / sum(st["l"][j]) for li in st["l"][j]]
    h_v = sum(comp[i] * h_vap(st["T"][j + 1], i) for i in range(NC))
    h_l = sum(comp[i] * h_liq(st["T"][j], p[j - 1], i) for i in range(NC))
    delta = [mpf(0)] * len(x)
    for i in range(NC):
        delta[layout[j] + i] = comp[i]
        delta[layout[j + 1] + NC + i] = comp[i]
    if upper_liquid:
        delta[layout[j] + 2 * NC] = (h_v - h_l) / (C_P * sum(st["l"][j]))
    else:
        delta[layout[j + 1] + 2 * NC] = (h_l - h_v) / (C_P * sum(st["v"][j + 1]))
    return delta


def singular_pairs(m1: dict[str, Any], m3: dict[str, Any]) -> dict[str, Any]:
    out = {}
    probes = [
        ("M1_stage3_LIQUID", "M1", m1, 3, True, ["TWO_PHASE"] * 2 + ["LIQUID"] + ["TWO_PHASE"] * 4),
        ("M3_stage1_LIQUID", "M3", m3, 1, True, ["LIQUID"] + ["TWO_PHASE"] * 4),
        ("M1_stage4_VAPOR", "M1", m1, 3, False, ["TWO_PHASE"] * 3 + ["VAPOR"] + ["TWO_PHASE"] * 3),
    ]
    for label, name, sol, j, upper, sig in probes:
        case = CASES[name]
        st = unpack(case, sol["x"])
        if upper:
            st["v"][j] = [mpf(0)] * NC  # the regime's pins: a LIQUID stage has no vapour
        else:
            st["l"][j + 1] = [mpf(0)] * NC  # a VAPOR stage has no liquid
        x = pack(case, st)
        delta = circulation(case, x, j, upper)
        worst = null_residual(case, x, sol["slots"], sig, delta)
        claim(worst < mpf("1e-40"), f"{label}: the circulation vector is a null vector (pair {j})")
        smin = sigma_min(case, x, sol["slots"], sig)
        claim(smin < SIGMA_SINGULAR, f"{label}: sigma_min < 1e-30")
        out[label] = {
            "pair": [j, j + 1],
            "signature": sig,
            "J_delta_max": mp.nstr(worst, 3),
            "sigma_min": mp.nstr(smin, 3),
        }
    return out


def variant_slots(
    name: str, sol: dict[str, Any], cond_kind: str, reb_kind: str
) -> tuple[dict[int, tuple[str, Any]], dict[str, list[str]]]:
    """Spec §9's variant set: both end slots take their value at the base case's root."""
    case, st = CASES[name], sol["st"]
    n_st = case["N"]
    value_of = {
        "reflux_ratio": (1, "RR"),
        "distillate_rate": (1, "D"),
        "boilup_ratio": (n_st, "BR"),
        "bottoms_rate": (n_st, "B"),
    }
    slots = dict(sol["slots"])
    spec = {}
    for end, kind in (("condenser", cond_kind), ("reboiler", reb_kind)):
        j, slot = value_of.get(kind, (1 if end == "condenser" else n_st, "Q"))
        value = slot_value(case, st, j, slot)
        slots[j] = (slot, value)
        spec[end] = [kind, s(value)]
    return slots, spec


def variants(name: str, sol: dict[str, Any], sets: Sequence[tuple[str, str]]) -> dict[str, Any]:
    case, out = CASES[name], {}
    for cond_kind, reb_kind in sets:
        slots, spec = variant_slots(name, sol, cond_kind, reb_kind)
        smin = sigma_min(case, sol["x"], slots, sol["sig"])
        key = f"{cond_kind}+{reb_kind}"
        if (cond_kind, reb_kind) == ("distillate_rate", "bottoms_rate"):
            claim(smin < SIGMA_SINGULAR, f"{name} {key}: singular (spec §5 S3), sigma_min < 1e-30")
        else:
            claim(smin > SIGMA_REGULAR, f"{name} {key}: regular at {name}'s root, sigma_min > 1e-4")
        out[key] = {"spec": spec, "sigma_min": mp.nstr(smin, 6)}
    return out


def dof(name: str) -> dict[str, int]:
    case = CASES[name]
    n_eq, n_in, total = len(eq_stages(case)), len(case["inlets"]), int(is_total(case))
    cols = 14 * n_eq + (NC + 2) * n_in + (2 * NC + 5) * total
    n_spec = int(case["condenser"] != "none") + int(case["reboiler"] != "none")
    return {
        "columns": cols,
        "rows": cols,
        "equilibrium_stages": n_eq,
        "inlets": n_in,
        "total_condenser_block": total,
        "column_specifications": n_spec,
    }


def refusal_section() -> dict[str, Any]:
    p = profile(7, "100000", "1000")
    z = [mpf(v) for v in FEED]
    hot = bubble_margin(z, mpf(360), p[3])
    claim(
        hot < 0, "S-R5: a LIQUID feed (0.3, 0.4, 0.3) at 360 K, 1.03 bar is above its bubble point"
    )
    claim(
        bubble_margin(z, mpf(340), mpf(104000)) >= MARGIN_MIN,
        "M1/M2 feed (340 K, 1.04 bar) is admissible LIQUID with margin >= 0.02",
    )
    claim(
        dew_margin(z, mpf(385), mpf(104000)) >= MARGIN_MIN,
        "M4 bottom inlet (385 K, 1.04 bar) is admissible VAPOR with margin >= 0.02",
    )
    claim(
        bubble_margin(z, mpf(300), mpf(100000)) >= MARGIN_MIN,
        "M3 top inlet (300 K, 1 bar) is admissible LIQUID with margin >= 0.02",
    )
    return {"feed_360K_bubble_margin": mp.nstr(hot, 6)}


# -- spec §18.2 (Amendment 2): the easy endpoint s02-bubble-point-v1, constructed (WO-G) ----------
VARIANT_SETS: dict[str, list[tuple[str, str]]] = {
    "M1": [
        ("duty", "duty"),
        ("reflux_ratio", "bottoms_rate"),
        ("distillate_rate", "boilup_ratio"),
        ("reflux_ratio", "duty"),
        ("distillate_rate", "bottoms_rate"),
    ],
    "M2": [
        ("duty", "duty"),
        ("distillate_rate", "boilup_ratio"),
        ("distillate_rate", "bottoms_rate"),
    ],
}
SINGULAR_SET = ("distillate_rate", "bottoms_rate")  # spec §5 S3: not admissible, no endpoint
SWEEP_MAX = 500  # spec §18.2 step 3: the sweep budget; the generator refuses beyond it
SWEEP_STOP = mpf("1e-30")  # spec §18.7 WO-G: the generator stops at max |dT| <= 1e-30 K
SWEEP_STOP_IMPL = mpf("1e-9")  # spec §18.2 step 3d: the implementation's stop (count recorded)
START_SHIFT = mpf(5)  # spec §18.6 A14: sweep start T0 +- 5 K
# Two runs that each stop at |dT| <= 1e-30 K with last-sweep contraction q <= 0.55 (measured, M4)
# sit within q/(1-q) * 1e-30 <= 1.3e-30 K of the fixed point, so within 2.5e-30 K of each other;
# a different fixed point would differ by far more than the emitted 25 digits resolve (1e-22 K).
SAME_FIXED_POINT = mpf("1e-29")
# spec §18.1 item 3: V-M2 (duty, duty)'s second root R2, to the six digits the spec quotes
R2_SEED = {"D": "0.274431", "phi": "0.775456", "T_c": "321.583"}


def sweep_flows(
    case: dict[str, Any], temps: dict[int, Any], rho: dict[int, Any], phi: Any
) -> tuple[dict[int, list[Any]], dict[int, list[Any]]]:
    """Spec §18.2 step 3b: per component, §6 step 4's tridiagonal with S_ij = K_ij rho_j."""
    p, inl, eqs, n_st = case["P"], case["inlets"], eq_stages(case), case["N"]
    liq = {j: [mpf(0)] * NC for j in eqs}
    vap = {j: [mpf(0)] * NC for j in eqs}
    for i in range(NC):
        sr = {j: k_val(temps[j], p[j - 1], i) * rho[j] for j in eqs}
        diag = [-(1 + sr[j]) for j in eqs]
        if is_total(case):
            diag[0] += phi * sr[2]
        col = thomas(
            [mpf(1)] * len(eqs),
            diag,
            [sr[j + 1] if j + 1 <= n_st else mpf(0) for j in eqs],
            [-sum(f["n"][i] for f in inl if f["stage"] == j) for j in eqs],
        )
        for k, j in enumerate(eqs):
            liq[j][i], vap[j][i] = col[k], sr[j] * col[k]
    return liq, vap


def bubble_temperature(n: Sequence[Any], p: Any) -> Any:
    """Spec §18.2 step 3c: ADR 0012 D1's band temperature at beta = 0, inside SYN-001's domain."""
    t = rr_temperature(n, 0, p)
    if not T_MIN < t < T_MAX:
        raise SystemExit(f"bubble_point_outside_domain: {mp.nstr(t, 8)} K at {p} Pa")
    return t


def end_ratios(
    case: dict[str, Any], init: dict[str, Any], slots: dict[int, tuple[str, Any]]
) -> tuple[dict[int, Any], Any]:
    """Spec §18.2 step 1: CMO stage ratios (floors included), the end overrides, and phi."""
    eqs, n_st = eq_stages(case), case["N"]
    rho = {j: init["V_cmo"][j - 1] / init["L_cmo"][j - 1] for j in eqs}
    if case["condenser"] == "partial" and slots[1][0] == "RR":
        rho[1] = 1 / slots[1][1]
    if case["reboiler"] == "partial" and slots[n_st][0] == "BR":
        rho[n_st] = slots[n_st][1]
    phi = None
    if is_total(case):
        phi = slots[1][1] / (1 + slots[1][1]) if slots[1][0] == "RR" else PHI0
    return rho, phi


def bubble_point(
    case: dict[str, Any],
    init: dict[str, Any],
    slots: dict[int, tuple[str, Any]],
    shift: Any = 0,
) -> dict[str, Any]:
    """Spec §18.2 steps 2-5, with the generator's stop SWEEP_STOP in place of 1e-9 K."""
    eqs, n_st, p = eq_stages(case), case["N"], case["P"]
    rho, phi = end_ratios(case, init, slots)
    temps = {j: init["profile"][j - 1] + shift for j in eqs}
    sweeps_impl = None
    for sweep in range(1, SWEEP_MAX + 1):
        liq, _ = sweep_flows(case, temps, rho, phi)
        new = {j: bubble_temperature(liq[j], p[j - 1]) for j in eqs}
        delta = max(abs(new[j] - temps[j]) for j in eqs)
        temps = new
        if sweeps_impl is None and delta <= SWEEP_STOP_IMPL:
            sweeps_impl = sweep
        if delta <= SWEEP_STOP:
            break
    else:
        raise SystemExit(f"{case['name']}: sweeps_exhausted")
    liq, vap = sweep_flows(case, temps, rho, phi)  # step 4: final flows at the stopped T
    st: dict[str, Any] = {"l": liq, "v": vap, "T": temps, "Q": {}}
    st["Q"] = {j: mpf(0) for j in range(1, n_st + 1)}
    if is_total(case):
        st["phi"], st["Tc"] = phi, bubble_temperature(vap[2], p[0])
    # step 5: every Q from its energy row, which is linear in Q with slope 1 (as in §6 step 7)
    two = ["TWO_PHASE"] * n_st
    f0 = residual(case, pack(case, st), {j: ("Q", mpf(0)) for j in range(1, n_st + 1)}, two)
    row = 0
    for j in eqs:
        st["Q"][j] = -f0[row + 2 * NC] * SCALE_Q
        row += 2 * NC + 2
    if is_total(case):
        st["Q"][1] = -f0[row + 1] * SCALE_Q
    return {"st": st, "rho": rho, "sweeps": sweep, "sweeps_impl": sweeps_impl}


def bubble_point_entry(
    label: str, case: dict[str, Any], init: dict[str, Any], slots: dict[int, tuple[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The registered x0 of one specification set, with its two-phase and start-shift claims."""
    bp = bubble_point(case, init, slots)
    st = bp["st"]
    check_state(f"{label} bubble_point", case, st, ["TWO_PHASE"] * case["N"])
    worst = mpf(0)
    for shift in (START_SHIFT, -START_SHIFT):
        other = bubble_point(case, init, slots, shift)["st"]
        worst = max([worst] + [abs(other["T"][j] - st["T"][j]) for j in st["T"]])
    claim(
        worst < SAME_FIXED_POINT,
        f"{label} bubble_point: sweeps from T0 + 5 K and T0 - 5 K reach the same fixed point"
        " within 1e-29 K",
    )
    out = record(case, st)
    out["rho"] = {str(j): s(r) for j, r in sorted(bp["rho"].items())}
    if is_total(case):
        out["phi"], out["T_c"] = s(st["phi"]), s(st["Tc"])
    out["sweeps"] = bp["sweeps"]
    out["sweeps_to_1e-9_K"] = bp["sweeps_impl"]
    return out, st


def continued_slots(
    case: dict[str, Any], st: dict[str, Any], tgt: dict[int, tuple[str, Any]]
) -> dict[str, dict[str, str]]:
    """Spec §18.2 / §7.5: ratio slots hold at x0; every other slot is continued from p0 = its
    variable at x0 toward its target value."""
    return {
        str(j): {"kind": kind, "p0": s(slot_value(case, st, j, kind)), "target": s(value)}
        for j, (kind, value) in sorted(tgt.items())
        if kind not in ("RR", "BR")
    }


def second_root(
    m2: dict[str, Any], x0_state: dict[str, Any], slots: dict[int, tuple[str, Any]]
) -> dict[str, Any]:
    """Spec §18.1 item 3: V-M2 (duty, duty)'s second regular root R2. Seed: the generator's Newton
    from V-M2 (duty, duty)'s bubble-point x0 with the condenser slot set to R2's six-digit
    distillate rate (D = 0.274431, reboiler duty unchanged); then Newton at both duties."""
    case, label = CASES["M2"], "V-M2 duty+duty second root R2"
    two = ["TWO_PHASE"] * case["N"]
    seed_slots = dict(slots)
    seed_slots[1] = ("D", mpf(R2_SEED["D"]))
    seed = newton(lambda y: residual(case, y, seed_slots, two), pack(case, x0_state))
    x = newton(lambda y: residual(case, y, slots, two), seed)
    st = unpack(case, x)
    claim(
        max(abs(r) for r in residual(case, x, slots, two)) < NEWTON_TOL,
        f"{label}: a root of the generator's rows below 1e-40",
    )
    claim(
        implementation_rows_max(case, st, slots, two) < mpf("1e-38"),
        f"{label}: the implementation's division-free rows vanish below 1e-38",
    )
    check_state(label, case, st, two)
    closures(label, case, st)
    smin = sigma_min(case, x, slots, two)
    claim(smin > SIGMA_REGULAR, f"{label}: regular, sigma_min > 1e-4")
    dist, phi, tc = slot_value(case, st, 1, "D"), st["phi"], st["Tc"]
    claim(
        abs(dist - mpf(R2_SEED["D"])) <= mpf("5e-7")
        and abs(phi - mpf(R2_SEED["phi"])) <= mpf("5e-7")
        and abs(tc - mpf(R2_SEED["T_c"])) <= mpf("5e-4"),
        f"{label}: rounds to spec §18.1's six digits (D 0.274431, phi 0.775456, T_c 321.583 K)",
    )
    m2_st = m2["st"]
    claim(
        abs(tc - m2_st["Tc"]) > 5 and abs(dist - slot_value(case, m2_st, 1, "D")) > mpf("0.1"),
        f"{label}: differs from M2's root by more than 5 K in T_c and 0.1 mol/s in D",
    )
    out = record(case, st)
    out.update(
        {
            "spec_values": spec_values(case, st),
            "sigma_min": mp.nstr(smin, 6),
            "seed": dict(R2_SEED),
        }
    )
    return out


def amendment_2(doc: dict[str, Any], sols: dict[str, dict[str, Any]]) -> None:
    """Spec §18.7 WO-G: additive keys; every claim here is appended after all earlier ones."""
    for name in ("M1", "M2", "M3", "M4"):
        case, tgt = CASES[name], sols[name]["slots"]
        entry, st = bubble_point_entry(name, case, sols[name]["init"], tgt)
        doc["cases"][name]["bubble_point"] = entry
        doc["cases"][name]["bubble_point_continued"] = continued_slots(case, st, tgt)
    for name, sets in VARIANT_SETS.items():
        case = CASES[name]
        for cond_kind, reb_kind in sets:
            if (cond_kind, reb_kind) == SINGULAR_SET:
                continue
            key = f"{cond_kind}+{reb_kind}"
            slots, _ = variant_slots(name, sols[name], cond_kind, reb_kind)
            entry, st = bubble_point_entry(f"V-{name} {key}", case, sols[name]["init"], slots)
            doc["variants"][name][key]["bubble_point"] = entry
            if (name, key) == ("M2", "duty+duty"):
                doc["variants"][name][key]["second_root"] = second_root(sols["M2"], st, slots)


def build() -> dict[str, Any]:
    doc: dict[str, Any] = {
        "generator": "docs/derivations/scripts/s02_reference.py",
        "spec": "docs/derivations/S02-spec.md",
        "precision_digits": mp.dps,
        "cases": {},
        "dof": {},
    }
    sols = {}
    for name in ("M1", "M2", "M3", "M4"):
        doc["cases"][name], sols[name] = solve_case(name)
        doc["dof"][name] = dof(name)
        claim(doc["dof"][name]["columns"] == doc["dof"][name]["rows"], f"{name}: square")
    doc["phase_case"] = {"P1": phase_case()}
    doc["variants"] = {
        name: variants(name, sols[name], sets) for name, sets in VARIANT_SETS.items()
    }
    doc["singular_pairs"] = singular_pairs(sols["M1"], sols["M3"])
    doc["refusals"] = refusal_section()
    amendment_2(doc, sols)  # spec §18 (WO-G): additive keys, claims appended after all others
    doc["claims"] = list(CLAIMS)
    doc["claim_count"] = len(CLAIMS)
    return doc


def encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="re-derive every claim and compare with the committed file",
    )
    parser.add_argument("--emit", metavar="PATH", help="write the reference JSON")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit PATH")
    payload = encode(build())
    if args.check:
        print(f"{len(CLAIMS)} claims passed")
        committed = DEFAULT_OUT.read_bytes() if DEFAULT_OUT.exists() else b""
        if committed != payload:
            print(f"{DEFAULT_OUT} differs from the generator's output", file=sys.stderr)
            return 1
        print(f"{DEFAULT_OUT} is byte-identical to the generator's output")
    if args.emit:
        Path(args.emit).parent.mkdir(parents=True, exist_ok=True)
        Path(args.emit).write_bytes(payload)
        print("wrote", args.emit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
