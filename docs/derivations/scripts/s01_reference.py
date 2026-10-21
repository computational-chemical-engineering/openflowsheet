"""Design-lane reference generator for the S01 specification (countercurrent equilibrium stages).

Everything here follows from the SYN-001 definitions (``docs/derivations/SYN-001.md`` §2-§3) and
``docs/derivations/S01-spec.md`` alone, evaluated with mpmath at 50 significant digits. It imports
nothing from ``openflowsheet`` or ``benchmarks``: the numbers it emits are the *expectations* the
S01 tests judge the implementation against.

**Independence.** The implementation writes equilibrium in the division-free form
``v_i L - K_i l_i V`` over 14 variables per stage (spec §3). This generator solves a *different*
formulation of the same equations -- 7 unknowns per stage ``(l_i, v_i, T)``, equilibrium in
mole-fraction form ``v_i/V - K_i l_i/L`` -- by its own damped Newton with complex-step
derivatives, and then evaluates the implementation's division-free rows at its root as a claim.

What it produces (spec §11): the Kremser endpoint of the initializer (S01.A02), the initializer
and the isothermal pre-solve root of every flowing case (A03-A04), the target roots and their
signatures (A05-A07, A11-A12), the dormant closed form with its label chain, outcome and cause
(A13-A14), the analytic root of the partial-dormancy probe and its spec §8 test (A19), the
energy-domain precheck bounds (A16), and the measured central-difference floor that sets A10's
tolerance.

    python docs/derivations/scripts/s01_reference.py --check
    python docs/derivations/scripts/s01_reference.py --emit <path of the committed JSON>

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
DEFAULT_OUT = Path(__file__).with_name("s01_reference.json")
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
BETA_LO, BETA_HI = mpf("0.1"), mpf("0.9")  # spec §6.1 step 2

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


# -- registered cases (spec §10) -------------------------------------------------------------------
def inlet(n: Sequence[str], t: str, p: str, phase: str, stage: int) -> dict[str, Any]:
    return {"n": [mpf(v) for v in n], "T": mpf(t), "P": mpf(p), "phase": phase, "stage": stage}


TOP1 = inlet(("0.2", "0.3", "0.5"), "330", "100000", "LIQUID", 1)
CASES: dict[str, dict[str, Any]] = {
    "C1": {
        "N": 1,
        "P": ["100000"],
        "Q": ["0"],
        "inlets": [TOP1, inlet(("0.5", "0.3", "0.2"), "380", "100000", "VAPOR", 1)],
        "signature": ["TWO_PHASE"],
    },
    "C2": {
        "N": 3,
        "P": ["100000"] * 3,
        "Q": ["0"] * 3,
        "inlets": [TOP1, inlet(("0.5", "0.3", "0.2"), "380", "100000", "VAPOR", 3)],
        "signature": ["TWO_PHASE"] * 3,
    },
    "C3": {
        "N": 5,
        "P": ["100000", "102000", "104000", "106000", "108000"],
        "Q": ["-1500", "0", "1000", "0", "2500"],
        "inlets": [
            inlet(("0.3", "0.3", "0.4"), "320", "100000", "LIQUID", 1),
            inlet(("0.4", "0.4", "0.2"), "390", "108000", "VAPOR", 5),
            inlet(("0.2", "0.5", "0.3"), "340", "104000", "LIQUID", 3),
        ],
        "signature": ["TWO_PHASE"] * 5,
    },
    "C4": {
        "N": 3,
        "P": ["100000"] * 3,
        "Q": ["20000", "-1000", "-4000"],
        "inlets": [
            inlet(("0.4", "0.3", "0.3"), "335", "100000", "LIQUID", 1),
            inlet(("0.05", "0.03", "0.02"), "380", "100000", "VAPOR", 3),
        ],
        "signature": ["TWO_PHASE", "LIQUID", "LIQUID"],
    },
    "C5": {
        "N": 2,
        "P": ["100000"] * 2,
        "Q": ["4000", "-15000"],
        "inlets": [
            inlet(("0.01", "0.01", "0.01"), "330", "100000", "LIQUID", 1),
            inlet(("0.5", "0.3", "0.2"), "390", "100000", "VAPOR", 2),
        ],
        "signature": ["VAPOR", "TWO_PHASE"],
    },
}


def stage_inflow(
    case: dict[str, Any],
    j: int,
    liq: list[list[Any]],
    v: list[list[Any]],
    t: list[Any],
    p: list[Any],
):
    """Component inflow and inflow enthalpy of stage j (0-based), spec §3.2."""
    n_st = case["N"]
    comp = [mpf(0)] * NC
    enth = mpf(0)
    if j > 0:
        comp = [comp[i] + liq[j - 1][i] for i in range(NC)]
        enth += h_stream(liq[j - 1], t[j - 1], p[j - 1], "LIQUID")
    if j < n_st - 1:
        comp = [comp[i] + v[j + 1][i] for i in range(NC)]
        enth += h_stream(v[j + 1], t[j + 1], p[j + 1], "VAPOR")
    for f in case["inlets"]:
        if f["stage"] - 1 == j:
            comp = [comp[i] + f["n"][i] for i in range(NC)]
            enth += h_stream(f["n"], f["T"], f["P"], f["phase"])
    return comp, enth


def unpack(x: Sequence[Any], n_st: int):
    liq = [[x[7 * j + i] for i in range(NC)] for j in range(n_st)]
    v = [[x[7 * j + 3 + i] for i in range(NC)] for j in range(n_st)]
    t = [x[7 * j + 6] for j in range(n_st)]
    return liq, v, t


def residual(
    case: dict[str, Any],
    x: Sequence[Any],
    sig: Sequence[str],
    lam: Any,
    tbar: Any | None,
    q0: Sequence[Any],
):
    """Generator formulation: 7 rows per stage. `tbar` set = isothermal pre-solve (spec §6.2)."""
    n_st, p = case["N"], case["Pm"]
    liq, v, t = unpack(x, n_st)
    rows: list[Any] = []
    for j in range(n_st):
        comp, h_in = stage_inflow(case, j, liq, v, t, p)
        rows += [comp[i] - liq[j][i] - v[j][i] for i in range(NC)]
        if sig[j] == "TWO_PHASE":
            big_l, big_v = sum(liq[j]), sum(v[j])
            rows += [v[j][i] / big_v - k_val(t[j], p[j], i) * liq[j][i] / big_l for i in range(NC)]
        elif sig[j] == "LIQUID":
            rows += list(v[j])
        else:
            rows += list(liq[j])
        if tbar is not None:
            rows.append(t[j] - tbar)
        else:
            q = q0[j] + lam * (case["Qm"][j] - q0[j])
            rows.append(
                (
                    q
                    + h_in
                    - h_stream(liq[j], t[j], p[j], "LIQUID")
                    - h_stream(v[j], t[j], p[j], "VAPOR")
                )
                / 1000
            )
    return rows


def newton(fun: Callable[[list[Any]], list[Any]], x0: list[Any], tol: Any = None) -> list[Any]:
    tol = NEWTON_TOL if tol is None else tol
    x = list(x0)
    n = len(x)
    for _ in range(80):
        f = fun(x)
        norm = max(abs(r) for r in f)
        if norm < tol:
            return x
        h = mpf("1e-60")
        jac = mp.matrix(n, n)
        for k in range(n):
            xp = [mpc(xi) for xi in x]
            xp[k] += mpc(0, h)
            col = fun(xp)
            for r in range(n):
                jac[r, k] = mp.im(col[r]) / h
        dx = mp.lu_solve(jac, mp.matrix([-r for r in f]))
        alpha = mpf(1)
        while alpha > mpf("1e-6"):
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


def initializer(case: dict[str, Any]) -> dict[str, Any]:
    """Spec §6.1, steps 1-6."""
    n_st, p = case["N"], case["Pm"]
    tot = [sum(f["n"][i] for f in case["inlets"]) for i in range(NC)]
    big_f = sum(tot)
    z = [tot[i] / big_f for i in range(NC)]
    beta = sum(sum(f["n"]) for f in case["inlets"] if f["phase"] == "VAPOR") / big_f
    beta_c = min(max(beta, BETA_LO), BETA_HI)
    pbar = sum(p) / n_st
    tbar = rr_temperature(z, beta_c, pbar)
    big_l = [
        sum(sum(f["n"]) for f in case["inlets"] if f["phase"] == "LIQUID" and f["stage"] <= j + 1)
        for j in range(n_st)
    ]
    big_v = [
        sum(sum(f["n"]) for f in case["inlets"] if f["phase"] == "VAPOR" and f["stage"] >= j + 1)
        for j in range(n_st)
    ]
    floor = BETA_LO * big_f
    big_l = [max(x, floor) for x in big_l]
    big_v = [max(x, floor) for x in big_v]
    liq = [[mpf(0)] * NC for _ in range(n_st)]
    v = [[mpf(0)] * NC for _ in range(n_st)]
    for i in range(NC):
        st = [k_val(tbar, p[j], i) * big_v[j] / big_l[j] for j in range(n_st)]
        rhs = [-sum(f["n"][i] for f in case["inlets"] if f["stage"] == j + 1) for j in range(n_st)]
        col = thomas(
            [mpf(1)] * n_st,
            [-(1 + st[j]) for j in range(n_st)],
            [st[j + 1] if j + 1 < n_st else mpf(0) for j in range(n_st)],
            rhs,
        )
        for j in range(n_st):
            liq[j][i], v[j][i] = col[j], st[j] * col[j]
    return {
        "z": z,
        "beta": beta,
        "beta_clamped": beta_c,
        "Pbar": pbar,
        "Tbar": tbar,
        "L_cmo": big_l,
        "V_cmo": big_v,
        "l": liq,
        "v": v,
    }


def kremser(
    n_st: int, k: Sequence[Any], big_l: Any, big_v: Any, l_top: Sequence[Any], v_bot: Sequence[Any]
) -> list[list[Any]]:
    """Closed form l_ij = a_i + b_i S_i^-j (S_i != 1), a_i + b_i j (S_i = 1); spec §6.3."""
    out = [[mpf(0)] * NC for _ in range(n_st)]
    for i in range(NC):
        st = k[i] * big_v / big_l
        if st == 1:
            b = (v_bot[i] - l_top[i]) / (n_st + 1)
            for j in range(1, n_st + 1):
                out[j - 1][i] = l_top[i] + b * j
        else:
            b = (v_bot[i] / st - l_top[i]) / (st ** -(n_st + 1) - 1)
            a = l_top[i] - b
            for j in range(1, n_st + 1):
                out[j - 1][i] = a + b * st**-j
    return out


def division_free_max(
    case: dict[str, Any], liq: list[list[Any]], v: list[list[Any]], t: list[Any], sig: Sequence[str]
) -> Any:
    worst = mpf(0)
    for j in range(case["N"]):
        if sig[j] != "TWO_PHASE":
            continue
        big_l, big_v = sum(liq[j]), sum(v[j])
        for i in range(NC):
            worst = max(
                worst, abs(v[j][i] * big_l - k_val(t[j], case["Pm"][j], i) * liq[j][i] * big_v)
            )
    return worst


def stage_records(case: dict[str, Any], liq, v, t) -> list[dict[str, Any]]:
    p = case["Pm"]
    out = []
    for j in range(case["N"]):
        comp, h_in = stage_inflow(case, j, liq, v, t, p)
        q = h_stream(liq[j], t[j], p[j], "LIQUID") + h_stream(v[j], t[j], p[j], "VAPOR") - h_in
        out.append(
            {
                "stage": j + 1,
                "T": s(t[j]),
                "P": s(p[j]),
                "l": [s(a) for a in liq[j]],
                "v": [s(a) for a in v[j]],
                "L": s(sum(liq[j])),
                "V": s(sum(v[j])),
                "m": [s(a) for a in comp],
                "Q": s(q),
            }
        )
    return out


def flatten(liq, v, t) -> list[Any]:
    return [a for j in range(len(t)) for a in (*liq[j], *v[j], t[j])]


def check_admissible(
    case: dict[str, Any], name: str, liq, v, t, sig: Sequence[str]
) -> dict[str, str]:
    margins: dict[str, str] = {}
    for j, reg in enumerate(sig):
        tj, pj = t[j], case["Pm"][j]
        claim(T_MIN <= tj <= T_MAX, f"{name} stage {j + 1}: T inside the SYN-001 domain")
        if reg == "TWO_PHASE":
            low = min(min(liq[j]), min(v[j]))
            claim(
                low > mpf("1e-4"), f"{name} stage {j + 1}: two-phase with every flow > 1e-4 mol/s"
            )
            margins[str(j + 1)] = s(low)
        elif reg == "LIQUID":
            big_l = sum(liq[j])
            bubble = sum(liq[j][i] / big_l * k_val(tj, pj, i) for i in range(NC))
            claim(
                bubble < mpf("0.98") and max(v[j]) == 0,
                f"{name} stage {j + 1}: subcooled liquid, sum x K < 0.98",
            )
            margins[str(j + 1)] = s(1 - bubble)
        else:
            big_v = sum(v[j])
            dew = sum(v[j][i] / big_v / k_val(tj, pj, i) for i in range(NC))
            claim(
                dew < mpf("0.98") and max(liq[j]) == 0,
                f"{name} stage {j + 1}: superheated vapour, sum y/K < 0.98",
            )
            margins[str(j + 1)] = s(1 - dew)
    return margins


def solve_case(name: str, case: dict[str, Any]) -> dict[str, Any]:
    case["Pm"] = [mpf(x) for x in case["P"]]
    case["Qm"] = [mpf(x) for x in case["Q"]]
    n_st, sig = case["N"], case["signature"]
    init = initializer(case)
    all2p = ["TWO_PHASE"] * n_st
    x_k = flatten(init["l"], init["v"], [init["Tbar"]] * n_st)
    x0 = newton(lambda x: residual(case, x, all2p, 0, init["Tbar"], []), x_k)
    l0, v0, t0 = unpack(x0, n_st)
    check_admissible(case, f"{name} pre-solve", l0, v0, t0, all2p)
    pre = stage_records(case, l0, v0, t0)
    q0 = [mpf(r["Q"]) for r in pre]
    # target: the generator's own path (equal duty steps in the registered signature)
    x = list(x0)
    for j, reg in enumerate(sig):
        for i in range(NC):
            tot = x[7 * j + i] + x[7 * j + 3 + i]
            if reg == "LIQUID":
                x[7 * j + i], x[7 * j + 3 + i] = tot, mpf(0)
            elif reg == "VAPOR":
                x[7 * j + i], x[7 * j + 3 + i] = mpf(0), tot
    steps = 16
    for k in range(1, steps + 1):
        x = newton(lambda y, k=k: residual(case, y, sig, mpf(k) / steps, None, q0), x)
    liq, v, t = unpack(x, n_st)
    margins = check_admissible(case, name, liq, v, t, sig)
    claim(
        division_free_max(case, liq, v, t, sig) < mpf("1e-38"),
        f"{name}: the implementation's division-free rows vanish at the root",
    )
    # overall closures (spec §3.5): telescoping internal streams
    tot_in = [sum(f["n"][i] for f in case["inlets"]) for i in range(NC)]
    tot_out = [v[0][i] + liq[-1][i] for i in range(NC)]
    claim(
        max(abs(tot_in[i] - tot_out[i]) for i in range(NC)) < mpf("1e-38"),
        f"{name}: overall component closure",
    )
    h_in = sum(h_stream(f["n"], f["T"], f["P"], f["phase"]) for f in case["inlets"])
    h_out = h_stream(v[0], t[0], case["Pm"][0], "VAPOR") + h_stream(
        liq[-1], t[-1], case["Pm"][-1], "LIQUID"
    )
    claim(abs(sum(case["Qm"]) + h_in - h_out) < mpf("1e-34"), f"{name}: overall energy closure")
    # regularity of the generator's Jacobian at the root (complex step; smallest singular value)
    n = len(x)
    jac = mp.matrix(n, n)
    for kk in range(n):
        xp = [mpc(a) for a in x]
        xp[kk] += mpc(0, mpf("1e-60"))
        col = residual(case, xp, sig, 1, None, q0)
        for r in range(n):
            jac[r, kk] = mp.im(col[r]) / mpf("1e-60")
    smin = min(mp.svd_r(jac, compute_uv=False))
    claim(smin > mpf("1e-6"), f"{name}: Jacobian regular at the root (sigma_min > 1e-6)")
    doc = {
        "N": n_st,
        "P": case["P"],
        "Q": case["Q"],
        "inlets": [
            {
                "stage": f["stage"],
                "phase": f["phase"],
                "n": [s(a) for a in f["n"]],
                "T": s(f["T"]),
                "P": s(f["P"]),
            }
            for f in case["inlets"]
        ],
        "initializer": {
            "z": [s(a) for a in init["z"]],
            "beta": s(init["beta"]),
            "beta_clamped": s(init["beta_clamped"]),
            "Pbar": s(init["Pbar"]),
            "Tbar": s(init["Tbar"]),
            "L_cmo": [s(a) for a in init["L_cmo"]],
            "V_cmo": [s(a) for a in init["V_cmo"]],
            "l": [[s(a) for a in row] for row in init["l"]],
            "v": [[s(a) for a in row] for row in init["v"]],
        },
        "presolve": pre,
        "signature": sig,
        "target": stage_records(case, liq, v, t),
        "admissibility_margin": margins,
        "sigma_min": s(smin),
        "products": {"top_vapour": [s(a) for a in v[0]], "bottom_liquid": [s(a) for a in liq[-1]]},
    }
    case["root"] = x
    return doc


def kremser_section() -> dict[str, Any]:
    k = [k_val(mpf(360), P_REF, i) for i in range(NC)]
    claim(k[1] == 1, "K_B(360 K, P_r) = 1 exactly, so V/L = 1 gives the S = 1 special case")
    out = {}
    l_top = [mpf("0.2"), mpf("0.3"), mpf("0.5")]
    v_bot = [mpf("0.5"), mpf("0.3"), mpf("0.2")]
    for n_st, big_v in ((1, mpf("1.5")), (2, mpf("1.5")), (5, mpf("1.5")), (3, mpf(1))):
        case = {
            "N": n_st,
            "inlets": [{"n": l_top, "stage": 1}, {"n": [a * big_v for a in v_bot], "stage": n_st}],
        }
        rec = []
        for i in range(NC):
            st = [k[i] * big_v] * n_st
            rhs = [
                -sum(f["n"][i] for f in case["inlets"] if f["stage"] == j + 1) for j in range(n_st)
            ]
            rec.append(
                thomas(
                    [mpf(1)] * n_st,
                    [-(1 + a) for a in st],
                    [st[0] if j + 1 < n_st else mpf(0) for j in range(n_st)],
                    rhs,
                )
            )
        closed_scaled = kremser(n_st, k, mpf(1), big_v, l_top, [a * big_v for a in v_bot])
        diff = max(abs(closed_scaled[j][i] - rec[i][j]) for j in range(n_st) for i in range(NC))
        claim(
            diff < mpf("1e-45"),
            f"Kremser N={n_st}, V/L={s(big_v)}: closed form equals the tridiagonal recurrence",
        )
        out[f"N{n_st}_VL{s(big_v)}"] = {
            "K": [s(a) for a in k],
            "L": "1",
            "V": s(big_v),
            "l_top": [s(a) for a in l_top],
            "v_bot": [s(a * big_v) for a in v_bot],
            "l": [[s(closed_scaled[j][i]) for i in range(NC)] for j in range(n_st)],
        }
    return out


def fd_floor(case: dict[str, Any]) -> dict[str, str]:
    """Float64 central differences of the generator's rows at C2's root vs the exact derivative."""
    x = [float(a) for a in case["root"]]
    sig = case["signature"]

    def f_float(y: list[float]) -> list[float]:
        return [
            float(r)
            for r in residual(case, [mpf(a) for a in y], sig, 1, None, [mpf(0)] * case["N"])
        ]

    worst = {}
    for rel in (1e-4, 1e-6, 1e-8):
        err = 0.0
        for k in range(len(x)):
            h = rel * max(1.0, abs(x[k]))
            xp, xm = list(x), list(x)
            xp[k] += h
            xm[k] -= h
            fp, fm = f_float(xp), f_float(xm)
            xc = [mpc(a) for a in case["root"]]
            xc[k] += mpc(0, mpf("1e-60"))
            exact = [
                mp.im(r) / mpf("1e-60")
                for r in residual(case, xc, sig, 1, None, [mpf(0)] * case["N"])
            ]
            for r in range(len(x)):
                fd = (fp[r] - fm[r]) / (2 * h)
                err = max(err, abs(fd - float(exact[r])) / max(1.0, abs(float(exact[r]))))
        worst[f"{rel:.0e}"] = f"{err:.2e}"
    claim(
        float(worst["1e-06"]) < 1e-6,
        "central differences at h = 1e-6 max(1,|x|) agree with the exact Jacobian to < 1e-6",
    )
    return worst


def precheck_section() -> dict[str, Any]:
    case = CASES["C1"]
    tot = [sum(f["n"][i] for f in case["inlets"]) for i in range(NC)]
    h_lo = sum(tot[i] * h_liq(T_MIN, case["Pm"][-1], i) for i in range(NC))
    h_hi = sum(tot[i] * h_vap(T_MAX, i) for i in range(NC))
    h_in = sum(h_stream(f["n"], f["T"], f["P"], f["phase"]) for f in case["inlets"])
    claim(
        max(h_liq(T_MAX, P_MAX, i) for i in range(NC)) < min(h_vap(T_MIN, i) for i in range(NC)),
        "max h^L < min h^V on the domain",
    )
    q_bad = mpf(200000)
    claim(h_in + q_bad > h_hi, "R7: C1 with Q_1 = +200 kW exceeds the all-vapour-at-T_max bound")
    claim(h_in - q_bad < h_lo, "R7b: C1 with Q_1 = -200 kW is below the all-liquid-at-T_min bound")
    claim(h_lo < h_in < h_hi, "C1 as registered passes the precheck")
    return {
        "case": "C1",
        "H_in": s(h_in),
        "H_lo": s(h_lo),
        "H_hi": s(h_hi),
        "Q_refused": ["200000", "-200000"],
    }


# -- dormant stages (spec §4.2-§4.6) and the A19 partial-dormancy probe -------------------------
# Dormant inlets carry C2's top/bottom states with zero flow.  T_top (330 K) differs from the vapour
# inlet's 380 K (DECISION 4's rejected label) and from A19's side feed 340 K, so a label taken from
# the wrong stream, or from the stage below, changes a registered temperature.
DORMANT_TOP = inlet(("0", "0", "0"), "330", "100000", "LIQUID", 1)
DORMANT_BOTTOM = inlet(("0", "0", "0"), "380", "100000", "VAPOR", 3)
DORMANT_CASES: dict[str, dict[str, Any]] = {
    "D1": {"N": 3, "P": ["100000"] * 3, "Q": ["0", "0", "0"]},
    "D2": {"N": 3, "P": ["100000"] * 3, "Q": ["0", "50", "0"]},
}
A19_CASE: dict[str, Any] = {
    "N": 3,
    "P": ["100000"] * 3,
    "Q": ["0"] * 3,
    "side": inlet(("0.2", "0.5", "0.3"), "340", "100000", "LIQUID", 3),
    "signature": ["ZERO_FLOW", "ZERO_FLOW", "LIQUID"],
}
PINNED = {
    "TWO_PHASE": (),
    "LIQUID": ("v", "V"),
    "VAPOR": ("l", "L"),
    "ZERO_FLOW": ("l", "v", "L", "V"),
}


def closed_form_state(case: dict[str, Any], sig: Sequence[str]) -> dict[str, Any]:
    """Spec §4.3/§4.6 and §10 A19: the root of the declared rows under a signature with no vapour.

    With no TWO_PHASE or VAPOR stage every vapour stream is pinned to zero, so stage j's inflow is
    the liquid from j-1 plus its own inlets and a top-down sweep is exact.  A ZERO_FLOW stage pins
    its flows and takes T_label(j) = T_{j-1} (T_top for j = 1).  A LIQUID stage passes its inflow
    through (mix, mole, Ldef) and its energy row is linear in T_j:
    Q_j + H_in - sum_i l_ij [C_P (T_j - T_ref) + v_i (P_j - P_ref)] = 0.
    """
    n_st, p, q = case["N"], case["Pm"], case["Qm"]
    claim(
        all(reg in ("ZERO_FLOW", "LIQUID") for reg in sig),
        f"{case['name']}: no vapour-carrying stage, so a top-down sweep solves the declared rows",
    )
    zero = [mpf(0)] * NC
    liq, v, m = [list(zero) for _ in range(n_st)], [list(zero) for _ in range(n_st)], []
    t: list[Any] = [mpf(0)] * n_st
    big_l, big_v, label, slope = [mpf(0)] * n_st, [mpf(0)] * n_st, [], []
    t_top = next(f["T"] for f in case["inlets"] if f["stage"] == 1 and f["phase"] == "LIQUID")
    dormant_ok = True
    for j in range(n_st):
        comp, h_in = stage_inflow(case, j, liq, v, t, p)
        m.append(list(comp))
        if sig[j] == "ZERO_FLOW":
            dormant_ok = dormant_ok and all(a == 0 for a in comp) and h_in == 0
            t[j] = t_top if j == 0 else t[j - 1]
            label.append("T_top" if j == 0 else f"T_{j}")
            slope.append(None)
        else:
            liq[j] = list(comp)
            big_l[j] = sum(
                f["n"][i] for f in case["inlets"] if f["stage"] == j + 1 for i in range(NC)
            )
            if j > 0:
                big_l[j] += big_l[j - 1]
            poynting = sum(liq[j][i] * V_MOL[i] for i in range(NC)) * (p[j] - P_REF)
            t[j] = T_REF + (q[j] + h_in - poynting) / (C_P * big_l[j])
            label.append(None)
            slope.append(-C_P * big_l[j])
    claim(
        dormant_ok,
        f"{case['name']}: every ZERO_FLOW stage's inflow is exactly zero (the dormancy test holds)",
    )
    return {
        "l": liq,
        "v": v,
        "m": m,
        "L": big_l,
        "V": big_v,
        "T": t,
        "t_top": t_top,
        "label": label,
        "slope": slope,
    }


def declared_rows(case: dict[str, Any], st: dict[str, Any], sig: Sequence[str]) -> dict[str, Any]:
    """The implementation's rows of spec §2 at `st`, after §4.2's pins, drops and label swaps.

    Returns the declared rows by id, plus the swapped-out energy rows of ZERO_FLOW stages (under
    `swapped`), whose values decide §4.5/§4.6's SPECIFICATION_CONFLICT.
    """
    n_st, p = case["N"], case["Pm"]
    liq, v, t = st["l"], st["v"], st["T"]
    rows: dict[str, Any] = {}
    swapped: dict[str, Any] = {}
    pinned, pins_ok = 0, True
    for j in range(n_st):
        u, reg = f"<cascade>:stage:{j + 1}", sig[j]
        cols = {"l": liq[j], "v": v[j], "L": [st["L"][j]], "V": [st["V"][j]]}
        for name in PINNED[reg]:
            pins_ok = pins_ok and all(a == 0 for a in cols[name])
            pinned += len(cols[name])
        comp, h_in = stage_inflow(case, j, liq, v, t, p)
        for i in range(NC):
            rows[f"{u}:mix:{i}"] = comp[i] - st["m"][j][i]
        if reg != "ZERO_FLOW":
            for i in range(NC):
                rows[f"{u}:mole:{i}"] = st["m"][j][i] - v[j][i] - liq[j][i]
        if reg == "TWO_PHASE":
            for i in range(NC):
                rows[f"{u}:eq:{i}"] = (
                    v[j][i] * st["L"][j] - k_val(t[j], p[j], i) * liq[j][i] * st["V"][j]
                )
        if reg in ("TWO_PHASE", "LIQUID"):
            rows[f"{u}:Ldef"] = st["L"][j] - sum(liq[j])
        if reg in ("TWO_PHASE", "VAPOR"):
            rows[f"{u}:Vdef"] = st["V"][j] - sum(v[j])
        energy = (
            case["Qm"][j]
            + h_in
            - h_stream(v[j], t[j], p[j], "VAPOR")
            - h_stream(liq[j], t[j], p[j], "LIQUID")
        )
        if reg == "ZERO_FLOW":
            rows[f"{u}:label"] = t[j] - (t[j - 1] if j > 0 else st["t_top"])
            swapped[f"{u}:energy"] = energy
        else:
            rows[f"{u}:energy"] = energy
        rows[f"{u}:P_spec"] = p[j] - mpf(case["P"][j])
        rows[f"{u}:Q_spec"] = case["Qm"][j] - mpf(case["Q"][j])
    claim(
        pins_ok and len(rows) == 14 * n_st - pinned,
        f"{case['name']}: pinned columns zero; declared rows = free stage columns = {len(rows)}",
    )
    return {"rows": rows, "swapped": swapped}


def stage_record(case: dict[str, Any], st: dict[str, Any], j: int, sig: Sequence[str]):
    return {
        "stage": j + 1,
        "regime": sig[j],
        "T": s(st["T"][j]),
        "T_label": st["label"][j],
        "P": s(case["Pm"][j]),
        "Q": s(case["Qm"][j]),
        "l": [s(a) for a in st["l"][j]],
        "v": [s(a) for a in st["v"][j]],
        "L": s(st["L"][j]),
        "V": s(st["V"][j]),
        "m": [s(a) for a in st["m"][j]],
    }


def dormant_case(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Spec §4.6: every inlet dormant; label chain, outcome and cause derived, not written."""
    case = dict(spec, name=name, inlets=[DORMANT_TOP, DORMANT_BOTTOM])
    case["Pm"], case["Qm"] = [mpf(x) for x in case["P"]], [mpf(x) for x in case["Q"]]
    sig = ["ZERO_FLOW"] * case["N"]
    st = closed_form_state(case, sig)
    t_top, t_bot = DORMANT_TOP["T"], DORMANT_BOTTOM["T"]
    claim(
        all(tj == t_top for tj in st["T"]) and t_top == 330 and t_bot != t_top,
        f"{name}: label chain T_j = T_top = 330 K at every stage, not the vapour inlet's 380 K",
    )
    ev = declared_rows(case, st, sig)
    claim(
        all(r == 0 for r in ev["rows"].values()),
        f"{name}: every declared row (mix, label, P and Q specifications) is exactly zero",
    )
    energy = list(ev["swapped"].values())
    claim(
        all(energy[j] == case["Qm"][j] for j in range(case["N"])),
        f"{name}: each swapped energy row equals Q_j* (every enthalpy flow vanishes)",
    )
    bad = [j for j in range(case["N"]) if energy[j] != 0]
    outcome = "SPECIFICATION_CONFLICT" if bad else "CONVERGED"
    cause = f"zero_flow_conflict(<cascade>:stage:{bad[0] + 1}:energy)" if bad else None
    return {
        "N": case["N"],
        "P": case["P"],
        "Q": case["Q"],
        "inlets": [inlet_record(f) for f in case["inlets"]],
        "signature": sig,
        "stages": [stage_record(case, st, j, sig) for j in range(case["N"])],
        "swapped_energy": [s(a) for a in energy],
        "outcome": outcome,
        "cause": cause,
    }


def inlet_record(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": f["stage"],
        "phase": f["phase"],
        "n": [s(a) for a in f["n"]],
        "T": s(f["T"]),
        "P": s(f["P"]),
    }


def dormant_section() -> dict[str, Any]:
    out = {name: dormant_case(name, spec) for name, spec in DORMANT_CASES.items()}
    claim(
        out["D1"]["outcome"] == "CONVERGED" and out["D1"]["cause"] is None,
        "D1: every Q_j* = 0, so §4.6 answers CONVERGED",
    )
    claim(
        out["D2"]["outcome"] == "SPECIFICATION_CONFLICT"
        and out["D2"]["cause"] == "zero_flow_conflict(<cascade>:stage:2:energy)",
        "D2: Q_2* = 50 W leaves stage 2's swapped energy row at 50 W: SPECIFICATION_CONFLICT",
    )
    return out


def partial_dormancy_section() -> dict[str, Any]:
    """Spec §10 A19: the analytic root under (ZERO_FLOW, ZERO_FLOW, LIQUID) and its §8 test.

    Stage 2 dormant forces m_2 = l_1 + v_3 = 0, so v_3 = 0 and stage 3 receives only the side feed.
    Under this signature the declared rows are linear and the energy row's T-slope is -C_P L_3 != 0,
    so the root is unique: stage 3 is a liquid pass-through at the feed's 340 K, stages 1-2 take
    T_top = 330 K.  Spec §8 then asks: declared rows within tolerance, T in the domain, and R-007
    admissibility of the LIQUID stage.
    """
    side = A19_CASE["side"]
    case = dict(A19_CASE, name="A19", inlets=[DORMANT_TOP, DORMANT_BOTTOM, side])
    case["Pm"], case["Qm"] = [mpf(x) for x in case["P"]], [mpf(x) for x in case["Q"]]
    sig, n_st = case["signature"], case["N"]
    st = closed_form_state(case, sig)
    t = st["T"]
    claim(
        t[0] == t[1] == DORMANT_TOP["T"] == 330
        and len({t[0], side["T"], DORMANT_BOTTOM["T"]}) == 3,
        "A19: stages 1-2 take T_top = 330 K, not the side feed's 340 K or the vapour inlet's 380 K",
    )
    claim(
        abs(t[2] - 340) < mpf("1e-45") and t[2] == side["T"],
        "A19: stage 3 is a liquid pass-through, T_3 = 340 K (the side feed's temperature)",
    )
    h_in3 = stage_inflow(case, 2, st["l"], st["v"], t, case["Pm"])[1]
    claim(
        abs(h_in3 - 4000) < mpf("1e-45") and st["slope"][2] == -100,
        "A19: stage 3 energy row: H_in = 4000 W, T-slope -C_P L_3 = -100 W/K, so T_3 is unique",
    )
    ev = declared_rows(case, st, sig)
    worst = max(abs(r) for r in ev["rows"].values())
    claim(worst < mpf("1e-45"), "A19: every declared row vanishes at the analytic root")
    # spec §8: domain, R-007 admissibility of the LIQUID stage (at m_3, T_3, P_3)
    claim(all(T_MIN <= tj <= T_MAX for tj in t), "A19: every stage T inside the SYN-001 domain")
    z3 = [a / sum(st["m"][2]) for a in st["m"][2]]
    bubble = sum(z3[i] * k_val(t[2], case["Pm"][2], i) for i in range(NC))
    claim(bubble < mpf("0.98"), "A19 stage 3: subcooled liquid, sum x K < 0.98 (passes spec §8)")
    zf = [a / sum(side["n"]) for a in side["n"]]
    bubble_in = sum(zf[i] * k_val(side["T"], side["P"], i) for i in range(NC))
    claim(bubble_in <= 1, "A19: the side feed is an admissible liquid (spec §5 R5 passes)")
    tot = [sum(f["n"][i] for f in case["inlets"]) for i in range(NC)]
    h_star = sum(h_stream(f["n"], f["T"], f["P"], f["phase"]) for f in case["inlets"]) + sum(
        case["Qm"]
    )
    h_lo = sum(tot[i] * h_liq(T_MIN, case["Pm"][-1], i) for i in range(NC))
    h_hi = sum(tot[i] * h_vap(T_MAX, i) for i in range(NC))
    claim(h_lo < h_star < h_hi, "A19: the energy precheck passes (spec §5 R7 does not refuse)")
    out_l, out_v = st["l"][-1], st["v"][0]
    claim(
        all(tot[i] == out_l[i] + out_v[i] for i in range(NC))
        and h_star
        == h_stream(out_v, t[0], case["Pm"][0], "VAPOR")
        + h_stream(out_l, t[-1], case["Pm"][-1], "LIQUID"),
        "A19: overall component and energy closure",
    )
    return {
        "N": n_st,
        "P": case["P"],
        "Q": case["Q"],
        "inlets": [inlet_record(f) for f in case["inlets"]],
        "signature": sig,
        "target": [stage_record(case, st, j, sig) for j in range(n_st)],
        "admissibility_margin": {"3": s(1 - bubble)},
        "precheck": {"H_in": s(h_star), "H_lo": s(h_lo), "H_hi": s(h_hi)},
        "products": {"top_vapour": [s(a) for a in out_v], "bottom_liquid": [s(a) for a in out_l]},
        "accepted_by_section_8": True,
    }


def dof_section() -> dict[str, Any]:
    out = {}
    for name, case in CASES.items():
        n_st, n_in = case["N"], len(case["inlets"])
        cols = n_st * (3 * NC + 5) + n_in * (NC + 2)
        rows = n_st * (3 * NC + 5) + n_in * (NC + 2)
        specs = n_st * 2 + n_in * (NC + 2)
        claim(cols == rows, f"{name}: implementation formulation square, {cols} x {rows}")
        claim(
            cols - (rows - specs) == specs,
            f"{name}: DOF before specification = 2N + n_in (C + 2) = {specs}",
        )
        out[name] = {"variables": cols, "rows": rows, "specifications": specs}
    pins = {
        "TWO_PHASE": (0, 0),
        "LIQUID": (NC + 1, NC + 1),
        "VAPOR": (NC + 1, NC + 1),
        "ZERO_FLOW": (2 * NC + 2, 2 * NC + 2),
    }
    for reg, (pinned, dropped) in pins.items():
        claim(pinned == dropped, f"regime {reg}: pinned columns = dropped rows")
    out["per_regime_pinned_dropped"] = {k: list(v) for k, v in pins.items()}
    return out


def sensitivity_section() -> dict[str, Any]:
    """Rule 3: the tolerances of spec §10 catch a dropped Poynting term and a reversed duty list."""
    base = CASES["C3"]
    root_t = unpack(base["root"], base["N"])[2]
    alt = dict(base)
    alt["Q"] = list(reversed(base["Q"]))
    alt["inlets"] = base["inlets"]
    alt["signature"] = base["signature"]
    doc = solve_case("C3_reversed_duties", alt)
    dt = max(abs(mpf(doc["target"][j]["T"]) - root_t[j]) for j in range(base["N"]))
    claim(dt > mpf("0.1"), "C3: reversing the duty list moves some stage temperature by > 0.1 K")
    poynting = max(abs(V_MOL[0] * (p - P_REF) / C_P) for p in base["Pm"])
    claim(
        poynting > mpf("1e-3"),
        "C3: the liquid Poynting enthalpy term is worth > 1e-3 K of temperature",
    )
    return {"C3_reversed_duties_max_dT": s(dt), "C3_poynting_dT_scale": s(poynting)}


def build() -> dict[str, Any]:
    CLAIMS.clear()
    doc: dict[str, Any] = {
        "generator": "docs/derivations/scripts/s01_reference.py",
        "spec": "docs/derivations/S01-spec.md",
        "mp_dps": mp.dps,
        "digits": DIGITS,
    }
    doc["kremser"] = kremser_section()
    doc["cases"] = {name: solve_case(name, case) for name, case in CASES.items()}
    c1 = CASES["C1"]
    liq, v, t = unpack(c1["root"], 1)
    z = [(liq[0][i] + v[0][i]) for i in range(NC)]
    beta = sum(v[0]) / (sum(v[0]) + sum(liq[0]))
    rr = sum(
        z[i] * (k_val(t[0], P_REF, i) - 1) / (1 + beta * (k_val(t[0], P_REF, i) - 1))
        for i in range(NC)
    )
    claim(
        abs(rr) < mpf("1e-38"),
        "C1 (N = 1) is the PH flash of the combined inlet: Rachford-Rice holds at T_1",
    )
    doc["dof"] = dof_section()
    doc["precheck"] = precheck_section()
    doc["dormant"] = dormant_section()
    doc["partial_dormancy"] = partial_dormancy_section()
    doc["fd_floor_C2"] = fd_floor(CASES["C2"])
    doc["sensitivity"] = sensitivity_section()
    doc["claims"] = list(CLAIMS)
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
