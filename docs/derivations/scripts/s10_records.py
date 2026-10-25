"""The real S10 records: ideal gas from NASA, the vapour-pressure fit and the Wilson fit.

Normative text: ``docs/derivations/S10-spec.md`` sections 9.3-9.5. Committed inputs:

* ``benchmarks/s10/saturation-points.json`` -- CoolProp 8.0.0 saturation pressures on the
  290-410 K grid (``s10_saturation_points.py``; spec section 9.2);
* ``benchmarks/s10/nasa7-low.json`` -- the NASA-7 low-range coefficients a1..a6 of CH3OH, C2H5OH
  and H2O as printed in Cantera 3.2.0's ``nasa_gas.yaml`` (``--extract-nasa``; build decision
  B-20);
* ``benchmarks/s10/vle/kurihara1993_binaries.csv`` -- the three isobaric binaries of Kurihara,
  Nakamichi and Kojima, J. Chem. Eng. Data 38 (1993) 446-449, Table II, each value as printed,
  double-entered (spec section 9.4).

Outputs: ``benchmarks/s10/records.yaml`` (the records of ``wilson-ig-v1``, spec section 5.1) and
``benchmarks/s10/fit-report.json`` (the fit claims and the fit quality: residuals, bubble-T and y
deviations, the ethanol-water azeotrope; fit quality, not validation).

It imports nothing from ``openflowsheet``. Everything is computed in mpmath at 50 digits, except the
grid scan of the Lambda fit (section 15, A2-1, which replaced section 9.4's solver), which runs in
binary64 and re-evaluates its best point at 50 digits (build decision B-25).

Run from the repository root::

    python docs/derivations/scripts/s10_records.py --check
    python docs/derivations/scripts/s10_records.py --emit
    python docs/derivations/scripts/s10_records.py --extract-nasa [--nasa-yaml PATH]

``--check`` regenerates both outputs in memory and fails unless they equal the committed files
(S10.A31). ``--vle CSV --out-dir DIR`` runs the fit on another transcription and writes to DIR
(a provisional run; never the committed records). Dependencies: Python 3.11+, mpmath, PyYAML,
NumPy. ``--extract-nasa`` also needs Cantera 3.2.0's data file (it is read as text, not executed).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from mpmath import mp, mpf

mp.dps = 50

ROOT = Path(__file__).resolve().parents[3]
S10 = ROOT / "benchmarks" / "s10"
SAT_JSON = S10 / "saturation-points.json"
NASA_JSON = S10 / "nasa7-low.json"
VLE_CSV = S10 / "vle" / "kurihara1993_binaries.csv"
RECORDS_YAML = S10 / "records.yaml"
FIT_JSON = S10 / "fit-report.json"

R = mpf("8.31446261815324")  # J/(mol K), exact in the 2019 SI
T0 = mpf("298.15")
THETA_UNIT = mpf(1000)

#: Component order and ids (spec section 9.5), with the NASA species name and the elements.
COMPONENTS = (
    ("CH3OH", "methanol", "CH3OH", {"C": 1, "H": 4, "O": 1}),
    ("C2H5OH", "ethanol", "C2H5OH", {"C": 2, "H": 6, "O": 1}),
    ("H2O", "water", "H2O", {"H": 2, "O": 1}),
)
#: Cantera 3.2.0's nasa_gas.yaml, as recorded in rights row S10-RC-01.
NASA_SHA256 = "4de6199d65d2d3db782e30573720c723130953707336add59713b02d8667e4db"
#: CIAAW 2021 conventional atomic weights, g/mol (Q-N6 default; molar mass is unused by the
#: provider).
ATOMIC_WEIGHT = {"H": Decimal("1.008"), "C": Decimal("12.011"), "O": Decimal("15.999")}
DOMAIN_T = (300.0, 400.0)  # K (spec section 9.5)
DOMAIN_P = (30000.0, 200000.0)  # Pa

PSAT_CLAIM = mpf("2e-3")  # max |delta ln P| on the grid (S10.A32)
PSAT_NARROW = (295.0, 405.0)  # Q-N4's pre-registered narrowing of the fit range
PSAT_DIGITS = 12
LAMBDA_DIGITS = 10
X_WINDOW = (mpf("0.02"), mpf("0.98"))  # 0.02 <= x_i <= 0.98 enters the objective
GN_STEP_TOL = mpf("1e-30")
GN_MAX_IT = 200
#: theta in [-3, 6], step 0.005: m * 0.005 in binary64, m = -600..1200 (1801 values; spec section
#: 15, A2-1, which replaced section 9.4's step 0.05).
GRID = np.arange(-600, 1201) * 0.005
GRID_BOX = (mpf(-3), mpf(6))
GRID_MARGIN = 1e-12
#: |Phi_binary64 - Phi_50| at the grid's best point (A2-1 claim LAMBDA-GRID64): ~430x above the
#: measured worst (2.3e-17, ethanol+water), 100x below GRID_MARGIN, which it must not eat.
GRID_F64_TOL = 1e-14
#: Central-difference step of the Hessian of Phi at theta* (A2-1 claim LAMBDA-MIN): at 50 digits
#: the truncation error is ~h^2 = 1e-30 and the rounding error ~1e-50/h = 1e-35.
HESS_H = mpf("1e-15")
#: |grad Phi(theta*)|_inf bound (A2-1 claim LAMBDA-MIN): measured worst 6.3e-29; a theta error
#: that moves Lambda's 10th digit (1e-10) gives |grad Phi| >= 2e-13 (smallest eigenvalue 2.2e-3).
GRAD_TOL = mpf("1e-20")
#: Agreement of the theta = 0 start with the adopted theta* where both converge (A2-1 claim
#: LAMBDA-V1): measured worst 1.05e-27 (ethanol+water); Lambda's 10th digit is ~1e-10.
V1_TOL = mpf("1e-24")
#: The binaries on which section 9.4's original start (theta = 0) must converge (A2-1).
V1_REQUIRED = ("ethanol+water", "methanol+water")
#: The binary whose Phi has a second local minimum on the singular curve theta_12 + theta_21 = 0,
#: and the start of the secant search for it, theta = (-a, a) (A2-1 claim LAMBDA-CURVE).
CURVE_BINARY = "methanol+ethanol"
CURVE_START = mpf("0.16")

#: The binaries of Table II, as (CSV label, i, j) with i, j indices into COMPONENTS.
BINARIES = (("methanol+ethanol", 0, 1), ("ethanol+water", 1, 2), ("methanol+water", 0, 2))
#: The pressure of Table II as the paper prints it, "101.3 kPa" (build decision B-24; the spec's
#: section 9.4 recalled 101.325 kPa). The temperatures were corrected to it by the authors.
P_TABLE = mpf("101.3") * 1000
SOURCE_PAPER = (
    "K. Kurihara, M. Nakamichi, K. Kojima, J. Chem. Eng. Data 38 (1993) 446-449, Table II"
)

CLAIMS: list[dict[str, Any]] = []


def claim(cid: str, ok: bool, text: str) -> None:
    if not ok:
        raise SystemExit(f"generator claim {cid} FAILED: {text}")
    CLAIMS.append({"id": cid, "holds": True, "statement": text})


def sig_float(x: mpf, digits: int) -> float:
    """x rounded to `digits` significant digits, as the binary64 nearest that decimal."""
    return float(mp.nstr(x, digits, min_fixed=-mp.inf, max_fixed=mp.inf))


def g(x: Any, digits: int = 6) -> float:
    return float(mp.nstr(mpf(x), digits))


# ============================================================================================
# 1. NASA-7 extraction (build decision B-20) and the ideal-gas rows (spec sections 3.1, 9.5)
# ============================================================================================


def extract_nasa(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != NASA_SHA256:
        raise SystemExit(f"{path}: SHA-256 {sha} is not the vetted {NASA_SHA256}")
    species = {s["name"]: s for s in yaml.load(raw, Loader=yaml.BaseLoader)["species"]}
    out = []
    for cid, _, nasa_name, elements in COMPONENTS:
        s = species[nasa_name]
        thermo = s["thermo"]
        if thermo["model"] != "NASA7" or [float(t) for t in thermo["temperature-ranges"]] != [
            200.0,
            1000.0,
            6000.0,
        ]:
            raise SystemExit(f"{nasa_name}: not a NASA7 entry on [200, 1000, 6000] K")
        if {k: int(v) for k, v in s["composition"].items()} != elements:
            raise SystemExit(f"{nasa_name}: composition {s['composition']} is not {elements}")
        out.append(
            {
                "id": cid,
                "nasa_species": nasa_name,
                "note": s["thermo"].get("note", ""),
                "temperature_ranges_K": thermo["temperature-ranges"],
                "low_range_a1_a7": thermo["data"][0],
            }
        )
    return {
        "schema_version": 1,
        "what": "NASA-7 low-range coefficients (200-1000 K) as printed in Cantera 3.2.0's "
        "nasa_gas.yaml, which cites McBride, Gordon, Reno, NASA TM-4513 (1993). Strings are the "
        "file's own decimal literals (S10 spec sections 3.1 and 9.5; rights row S10-RC-01).",
        "generator": "docs/derivations/scripts/s10_records.py --extract-nasa",
        "source_file": "cantera/data/nasa_gas.yaml (Cantera 3.2.0)",
        "source_sha256": sha,
        "species": out,
    }


def ideal_gas(nasa: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in nasa["species"]:
        a = entry["low_range_a1_a7"]
        # b_k = a_{k+1} 1000^k, exactly in decimal (spec 3.1; ADR 0026 D5), then the nearest double.
        b = [float(Decimal(a[k]) * Decimal(1000) ** k) for k in range(5)]
        am = [mpf(s) for s in a]
        h0 = R * (
            am[0] * T0
            + am[1] * T0**2 / 2
            + am[2] * T0**3 / 3
            + am[3] * T0**4 / 4
            + am[4] * T0**5 / 5
            + am[5]
        )
        rows.append({"b": b, "dhf": float(h0), "dhf_mp": h0, "note": entry["note"]})
    return rows


# ============================================================================================
# 2. The vapour-pressure fit (spec section 9.3)
# ============================================================================================


def ln_psat(c: Sequence[Any], t: Any) -> mpf:
    th = mpf(t) / THETA_UNIT
    return mpf(c[0]) + mpf(c[1]) / th + mpf(c[2]) * mp.log(th) + mpf(c[3]) * th**2


def fit_psat(points: list[list[float]], t_range: tuple[float, float]) -> dict[str, Any]:
    pts = [(mpf(t), mp.log(mpf(p))) for t, p in points if t_range[0] <= t <= t_range[1]]
    rows = [[mpf(1), THETA_UNIT / t, mp.log(t / THETA_UNIT), (t / THETA_UNIT) ** 2] for t, _ in pts]
    coef, _ = mp.qr_solve(mp.matrix(rows), mp.matrix([y for _, y in pts]))
    stored = [sig_float(coef[k], PSAT_DIGITS) for k in range(4)]
    worst = max(abs(ln_psat(stored, t) - y) for t, y in pts)
    return {"stored": stored, "worst": worst, "n": len(pts), "range": t_range}


def vapour_pressure(sat: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for comp in sat["components"]:
        fit = fit_psat(comp["points_T_K_P_Pa"], (290.0, 410.0))
        if not fit["worst"] <= PSAT_CLAIM:
            # Q-N4: narrow the fit range once, leaving the domain unchanged. A second failure
            # needs a spec amendment (a fifth term), never a silent change of form.
            fit = fit_psat(comp["points_T_K_P_Pa"], PSAT_NARROW)
        claim(
            f"PSAT-{comp['id']}",
            fit["worst"] <= PSAT_CLAIM,
            f"{comp['id']}: max |delta ln P| = {mp.nstr(fit['worst'], 3)} <= 2e-3 over the "
            f"{fit['n']} grid points of {fit['range'][0]}-{fit['range'][1]} K, with the stored "
            f"(12-digit) coefficients (S10.A32; fit quality, not validation)",
        )
        out.append({**fit, "id": comp["id"], "bibtex": comp["eos_bibtex_key"]})
    return out


# ============================================================================================
# 3. The Wilson fit (spec section 9.4)
# ============================================================================================


def read_vle(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ln_gamma(x: Sequence[mpf], lam: Sequence[Sequence[mpf]]) -> list[mpf]:
    """Eq. 3.8: ln gamma_i = 1 - ln S_i - sum_k x_k Lambda_ki / S_k, S_k = sum_j x_j Lambda_kj"""
    n = len(x)
    s = [mp.fsum(x[j] * lam[k][j] for j in range(n)) for k in range(n)]
    return [1 - mp.log(s[i]) - mp.fsum(x[k] * lam[k][i] / s[k] for k in range(n)) for i in range(n)]


def ln_gamma_binary(x1: mpf, t12: mpf, t21: mpf) -> tuple[list[mpf], list[list[mpf]]]:
    """ln gamma of a binary at theta_12, theta_21 and d ln gamma_i / d theta_ab (a != b).

    With S_a = sum_j x_j Lambda_aj, d ln gamma_i / d Lambda_ab = -delta_ia x_b / S_a
    - x_a delta_ib / S_a + x_a x_b Lambda_ai / S_a^2, and d Lambda_ab / d theta_ab = -Lambda_ab.
    """
    x = [x1, 1 - x1]
    lam = [[mpf(1), mp.exp(-t12)], [mp.exp(-t21), mpf(1)]]
    lg = ln_gamma(x, lam)
    s = [x[0] * lam[a][0] + x[1] * lam[a][1] for a in range(2)]
    jac = []
    for i in range(2):
        row = []
        for a, b in ((0, 1), (1, 0)):
            d = -(x[b] / s[a] if i == a else 0) - (x[a] / s[a] if i == b else 0)
            d += x[a] * x[b] * lam[a][i] / s[a] ** 2
            row.append(-lam[a][b] * d)
        jac.append(row)
    return lg, jac


def binary_data(
    rows: list[dict[str, str]], label: str, i: int, j: int, psat: list[dict[str, Any]]
) -> dict[str, Any]:
    pts = [r for r in rows if r["system"] == label]
    ids = (COMPONENTS[i][0], COMPONENTS[j][0])
    if [int(r["row"]) for r in pts] != list(range(1, len(pts) + 1)):
        raise SystemExit(f"{label}: rows are not 1..n in printed order")
    data = []
    for r in pts:
        x1, y1, t, p = mpf(r["x1"]), mpf(r["y1"]), mpf(r["T_K"]), P_TABLE
        x, y = (x1, 1 - x1), (y1, 1 - y1)  # B-23: x2 = 1 - x1, y2 = 1 - y1, exact decimals
        lpsat = (ln_psat(psat[i]["stored"], t), ln_psat(psat[j]["stored"], t))
        lgexp = [mp.log(y[k] * p / x[k]) - lpsat[k] for k in range(2)]
        used = [X_WINDOW[0] <= x[k] <= X_WINDOW[1] for k in range(2)]
        data.append({"row": r, "x1": x1, "y1": y1, "T": t, "P": p, "lgexp": lgexp, "used": used})
    return {"label": label, "i": i, "j": j, "ids": ids, "data": data}


def objective(b: dict[str, Any], t12: mpf, t21: mpf) -> tuple[mpf, list[mpf], list[list[mpf]]]:
    res, jac = [], []
    for d in b["data"]:
        lg, dlg = ln_gamma_binary(d["x1"], t12, t21)
        for k in range(2):
            if d["used"][k]:
                res.append(d["lgexp"][k] - lg[k])
                jac.append([-dlg[k][0], -dlg[k][1]])
    return mp.fsum(r * r for r in res), res, jac


def singular_curve_claim() -> None:
    """Spec section 15, A2-1: on the curve Lambda_12 Lambda_21 = 1 (theta_12 + theta_21 = 0),
    d ln gamma_i / d theta_21 = Lambda_21 d ln gamma_i / d theta_12 for i = 1, 2 at every x, so
    the two columns of J are proportional for any data set; off the curve they are not."""
    xs = (mpf("0.2"), mpf("0.7"))

    def dev(t12: mpf, t21: mpf) -> mpf:
        out = mpf(0)
        for x1 in xs:
            _, jac = ln_gamma_binary(x1, t12, t21)
            out = max(out, *(abs(jac[i][1] - mp.exp(-t21) * jac[i][0]) for i in range(2)))
        return out

    on = max(dev(-a, a) for a in (mpf("0.3"), mpf("-0.7")))
    off = dev(mpf("0.5"), mpf("-0.3"))
    claim(
        "WILSON-SINGULAR-CURVE",
        on <= mpf("1e-45") and off >= mpf("1e-3"),
        "on theta_12 + theta_21 = 0, d ln gamma_i/d theta_21 = Lambda_21 d ln gamma_i/d theta_12 "
        f"(worst {mp.nstr(on, 3)} <= 1e-45 at theta_21 = 0.3, -0.7; x1 = 0.2, 0.7); off it, at "
        f"theta = (0.5, -0.3), the columns differ by {mp.nstr(off, 3)} >= 1e-3 (A2-1)",
    )


def gn_step(jac: list[list[mpf]], res: list[mpf]) -> list[mpf]:
    """The minimum-norm least-squares solution of J step = -r (build decision B-26).

    At theta = 0 (every Lambda = 1) the two columns of J are equal, d ln gamma_i / d theta_12 =
    d ln gamma_i / d theta_21 = x_j^2, so J^T J is singular at the start the spec prescribes. The
    step is taken on the eigenvectors of J^T J whose eigenvalue exceeds 1e-40 of the largest.
    """
    jm, rv = mp.matrix(jac), mp.matrix(res)
    e, v = mp.eigsy(jm.T * jm)
    rhs = -(jm.T * rv)
    top = max(abs(e[k]) for k in range(2))
    step = [mpf(0), mpf(0)]
    for k in range(2):
        if abs(e[k]) > top * mpf("1e-40"):
            c = (v[0, k] * rhs[0] + v[1, k] * rhs[1]) / e[k]
            step = [step[0] + c * v[0, k], step[1] + c * v[1, k]]
    return step


def gn_run(b: dict[str, Any], start: Sequence[Any] = (0, 0)) -> dict[str, Any]:
    """Gauss-Newton at 50 digits from `start` (spec section 15, A2-1; B-26, B-27).

    Each iteration takes the minimum-norm step, halves it while Phi increases (down to a factor
    2^-200), and accepts the trial if Phi does not increase. It stops when the step taken, after
    halving, is shorter than 1e-30 (B-27), and gives up after 200 iterations. Never raises.
    """
    th = [mpf(start[0]), mpf(start[1])]
    phi, res, jac = objective(b, *th)
    for it in range(1, GN_MAX_IT + 1):
        step = gn_step(jac, res)
        lam = mpf(1)
        while True:
            trial = [th[0] + lam * step[0], th[1] + lam * step[1]]
            phi_t, res_t, jac_t = objective(b, *trial)
            if phi_t <= phi or lam < mpf(2) ** -200:
                break
            lam /= 2
        taken = mp.sqrt((lam * step[0]) ** 2 + (lam * step[1]) ** 2)
        if phi_t <= phi:
            th, phi, res, jac = trial, phi_t, res_t, jac_t
        if taken < GN_STEP_TOL:
            return {
                "converged": True,
                "theta": th,
                "phi": phi,
                "res": res,
                "jac": jac,
                "iterations": it,
                "last_step": taken,
            }
    return {"converged": False, "theta": th, "phi": phi, "iterations": GN_MAX_IT}


def gauss_newton(b: dict[str, Any], start: Sequence[Any] = (0, 0)) -> dict[str, Any]:
    """gn_run, refusing a run that reaches the iteration cap."""
    out = gn_run(b, start)
    if not out["converged"]:
        raise SystemExit(f"{b['label']}: Gauss-Newton did not converge in {GN_MAX_IT} iterations")
    return out


def gradient(b: dict[str, Any], t12: mpf, t21: mpf) -> list[mpf]:
    """grad Phi = 2 J^T r, with J = d r / d theta as `objective` returns it."""
    _, res, jac = objective(b, t12, t21)
    return [2 * mp.fsum(res[k] * jac[k][c] for k in range(len(res))) for c in range(2)]


def hessian_eigenvalues(b: dict[str, Any], th: Sequence[mpf]) -> list[mpf]:
    """Eigenvalues of the Hessian of Phi at th: a central difference of the analytic gradient
    with step HESS_H at 50 digits, symmetrised (A2-1 claim LAMBDA-MIN)."""
    cols = []
    for c in range(2):
        e = [HESS_H if k == c else mpf(0) for k in range(2)]
        gp = gradient(b, th[0] + e[0], th[1] + e[1])
        gm = gradient(b, th[0] - e[0], th[1] - e[1])
        cols.append([(gp[k] - gm[k]) / (2 * HESS_H) for k in range(2)])
    h = mp.matrix(2, 2)
    for r in range(2):
        for c in range(2):
            h[r, c] = (cols[c][r] + cols[r][c]) / 2
    e, _ = mp.eigsy(h)
    return sorted([e[0], e[1]])


def grid_scan(b: dict[str, Any]) -> tuple[float, float, float]:
    """Phi on theta in [-3, 6]^2, step 0.005, in binary64 (B-25, A2-1): (min Phi, theta_12,
    theta_21). Ties go to the first point in (theta_12, theta_21) row-major order."""
    t12, t21 = np.meshgrid(GRID, GRID, indexing="ij")
    l12, l21 = np.exp(-t12), np.exp(-t21)
    phi = np.zeros_like(t12)
    for d in b["data"]:
        x1 = float(d["x1"])
        x2 = 1.0 - x1
        s1, s2 = x1 + x2 * l12, x1 * l21 + x2
        lg1 = -np.log(s1) + x2 * (l12 / s1 - l21 / s2)
        lg2 = -np.log(s2) - x1 * (l12 / s1 - l21 / s2)
        for k, lg in enumerate((lg1, lg2)):
            if d["used"][k]:
                phi += (float(d["lgexp"][k]) - lg) ** 2
    m = np.unravel_index(np.argmin(phi), phi.shape)
    return float(phi[m]), float(GRID[m[0]]), float(GRID[m[1]])


def bubble(
    x1: mpf, lam: list[list[mpf]], ci: Sequence[float], cj: Sequence[float], p: mpf
) -> tuple[mpf, mpf]:
    """Bubble T and y1 at x1 and P with constant Lambda: sum_k x_k gamma_k P_k^sat(T) = P."""
    x = [x1, 1 - x1]
    gam = [mp.exp(v) for v in ln_gamma(x, lam)]

    def f(t: mpf) -> mpf:
        return mp.log(
            x[0] * gam[0] * mp.exp(ln_psat(ci, t)) + x[1] * gam[1] * mp.exp(ln_psat(cj, t))
        ) - mp.log(p)

    lo, hi = mpf(250), mpf(450)
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    t = (lo + hi) / 2
    return t, x[0] * gam[0] * mp.exp(ln_psat(ci, t)) / p


def fit_binary(b: dict[str, Any], psat: list[dict[str, Any]]) -> dict[str, Any]:
    """The Lambda fit of one binary, spec section 15, A2-1 (which replaced section 9.4's
    solver): Gauss-Newton from the best point of the step-0.005 grid, and its claims."""
    lab = b["label"]
    gmin, g12, g21 = grid_scan(b)
    gmin_mp, _, _ = objective(b, mpf(g12), mpf(g21))
    f64_err = abs(mpf(gmin) - gmin_mp)
    claim(
        f"LAMBDA-GRID64-{lab}",
        f64_err <= GRID_F64_TOL,
        f"{lab}: the binary64 grid objective at its best point agrees with the 50-digit one to "
        f"{mp.nstr(f64_err, 3)} <= 1e-14 (B-25, A2-1)",
    )
    gn = gn_run(b, (g12, g21))
    claim(
        f"LAMBDA-CONV-{lab}",
        gn["converged"],
        f"{lab}: Gauss-Newton from the grid's best point ({g12:g}, {g21:g}) converged in "
        f"{gn['iterations']} iterations (last step {mp.nstr(gn.get('last_step', mpf(1)), 3)} "
        "< 1e-30; cap 200) (A2-1)",
    )
    t12, t21 = gn["theta"]
    claim(
        f"LAMBDA-BOX-{lab}",
        all(GRID_BOX[0] < v < GRID_BOX[1] for v in (t12, t21)),
        f"{lab}: theta* = ({mp.nstr(t12, 8)}, {mp.nstr(t21, 8)}) lies inside the open box "
        "(-3, 6)^2 the grid covers (A2-1)",
    )
    claim(
        f"LAMBDA-{lab}",
        float(gmin_mp) >= float(gn["phi"]) - GRID_MARGIN,
        f"{lab}: Phi* = {mp.nstr(gn['phi'], 12)}; the grid scan of [-3, 6]^2 (step 0.005) finds "
        f"no Phi below Phi* - 1e-12 (its minimum {mp.nstr(gmin_mp, 12)} at theta = "
        f"({g12:g}, {g21:g})) (S10.A33, A2-1)",
    )
    grad = gradient(b, t12, t21)
    eig = hessian_eigenvalues(b, (t12, t21))
    jtj = mp.matrix(gn["jac"]).T * mp.matrix(gn["jac"])
    jtj_eig = sorted(mp.eigsy(jtj)[0][k] for k in range(2))
    gnorm = max(abs(v) for v in grad)
    claim(
        f"LAMBDA-MIN-{lab}",
        gnorm <= GRAD_TOL and eig[0] > 0,
        f"{lab}: theta* is a strict local minimum: |grad Phi|_inf = {mp.nstr(gnorm, 3)} <= 1e-20 "
        f"and the Hessian's eigenvalues ({mp.nstr(eig[0], 6)}, {mp.nstr(eig[1], 6)}) are "
        "positive (central difference of the analytic gradient, h = 1e-15, 50 digits) (A2-1)",
    )
    curve = None
    if lab == CURVE_BINARY:
        a = mp.findroot(lambda s: (lambda gr: gr[1] - gr[0])(gradient(b, -s, s)), CURVE_START)
        c_phi = objective(b, -a, a)[0]
        c_grad = max(abs(v) for v in gradient(b, -a, a))
        c_eig = hessian_eigenvalues(b, (-a, a))
        claim(
            f"LAMBDA-CURVE-{lab}",
            c_grad <= GRAD_TOL and c_eig[0] > 0 and c_phi > gmin_mp + GRID_MARGIN,
            f"{lab}: Phi has a second local minimum on the singular curve, theta = (-a, a) with "
            f"a = {mp.nstr(a, 9)}: |grad Phi|_inf = {mp.nstr(c_grad, 3)} <= 1e-20, Hessian "
            f"eigenvalues ({mp.nstr(c_eig[0], 4)}, {mp.nstr(c_eig[1], 4)}) > 0, Phi = "
            f"{mp.nstr(c_phi, 10)}, above the grid's best point by {mp.nstr(c_phi - gmin_mp, 3)} "
            "> 1e-12, so the grid claim refuses it (A2-1)",
        )
        curve = {
            "what": "the second local minimum of Phi, on theta_12 + theta_21 = 0, where J has "
            "rank 1 (spec section 15, A2-1); the theta = 0 start is drawn to it",
            "theta": [g(-a, 10), g(a, 10)],
            "phi": g(c_phi, 10),
            "hessian_eigenvalues": [g(v, 6) for v in c_eig],
        }
    v1 = gn_run(b, (0, 0))
    v1_dev = max(abs(v1["theta"][k] - gn["theta"][k]) for k in range(2))
    lam_stored = [sig_float(mp.exp(-t12), LAMBDA_DIGITS), sig_float(mp.exp(-t21), LAMBDA_DIGITS)]
    if lab in V1_REQUIRED:
        lam_v1 = [sig_float(mp.exp(-v), LAMBDA_DIGITS) for v in v1["theta"]]
        claim(
            f"LAMBDA-V1-{lab}",
            v1["converged"] and v1_dev <= V1_TOL and lam_v1 == lam_stored,
            f"{lab}: section 9.4's original start theta = 0 also converges ({v1['iterations']} "
            f"iterations) to theta* within {mp.nstr(v1_dev, 3)} <= 1e-24, with the same stored "
            "Lambda: Amendment 2 leaves this binary's result unchanged (A2-1)",
        )
    lam = [[mpf(1), mpf(lam_stored[0])], [mpf(lam_stored[1]), mpf(1)]]
    ci, cj = psat[b["i"]]["stored"], psat[b["j"]]["stored"]
    dev_t, dev_y, points = [], [], []
    for d in b["data"]:
        tb, yb = bubble(d["x1"], lam, ci, cj, d["P"])
        dev_t.append(tb - d["T"])
        dev_y.append(yb - d["y1"])
        points.append(
            {
                "row": int(d["row"]["row"]),
                "x1": d["row"]["x1"],
                "residual_ln_gamma": [
                    g(d["lgexp"][k] - ln_gamma([d["x1"], 1 - d["x1"]], lam)[k])
                    if d["used"][k]
                    else None
                    for k in range(2)
                ],
                "bubble_T_minus_exp_K": g(tb - d["T"]),
                "bubble_y1_minus_exp": g(yb - d["y1"]),
            }
        )
    n = len(b["data"])
    return {
        "binary": b["label"],
        "components": list(b["ids"]),
        "points": n,
        "residuals_in_objective": len(gn["res"]),
        "theta_star": [mp.nstr(t12, 20), mp.nstr(t21, 20)],
        "phi_star": g(gn["phi"], 15),
        "gauss_newton_start": [g12, g21],
        "gauss_newton_iterations": gn["iterations"],
        "grid_step": 0.005,
        "grid_min_phi": g(gmin_mp, 15),
        "grid_min_theta": [g12, g21],
        "grid_margin_over_phi_star": g(gmin_mp - gn["phi"], 6),
        "grad_phi_inf_norm": g(gnorm, 3),
        "hessian_eigenvalues": [g(v, 6) for v in eig],
        "jtj_eigenvalues": [g(v, 6) for v in jtj_eig],
        "start_theta_zero": {
            "what": "section 9.4's original start, run under the same rules for comparison "
            "(spec section 15, A2-1); not the adopted result",
            "converged": v1["converged"],
            "iterations": v1["iterations"],
            "theta": [g(v, 8) for v in v1["theta"]],
            "phi": g(v1["phi"], 8),
            "max_abs_theta_minus_theta_star": g(v1_dev, 3),
        },
        "second_local_minimum": curve,
        "lambda_stored": {
            f"{b['ids'][0]}->{b['ids'][1]}": lam_stored[0],
            f"{b['ids'][1]}->{b['ids'][0]}": lam_stored[1],
        },
        "aad_bubble_T_K": g(mp.fsum(abs(v) for v in dev_t) / n),
        "max_bubble_T_K": g(max(abs(v) for v in dev_t)),
        "aad_bubble_y1": g(mp.fsum(abs(v) for v in dev_y) / n),
        "max_bubble_y1": g(max(abs(v) for v in dev_y)),
        "per_point": points,
        "_lam": lam,
    }


def azeotrope(fit: dict[str, Any], b: dict[str, Any], psat: list[dict[str, Any]]) -> dict[str, Any]:
    """The model's azeotrope (y1 = x1 at the bubble point) and the data's own sign change."""
    ci, cj = psat[b["i"]]["stored"], psat[b["j"]]["stored"]
    p = b["data"][0]["P"]
    data = [(d["x1"], d["y1"] - d["x1"], d["T"], d["row"]) for d in b["data"]]
    k = next(k for k in range(len(data) - 1) if data[k][1] > 0 >= data[k + 1][1])
    lo, hi = mpf("0.5"), mpf("0.99")

    def h(x1: mpf) -> mpf:
        return bubble(x1, fit["_lam"], ci, cj, p)[1] - x1

    if not h(lo) > 0 > h(hi):
        return {"model": "no azeotrope in x1 = 0.5-0.99"}
    for _ in range(80):
        mid = (lo + hi) / 2
        if h(mid) > 0:
            lo = mid
        else:
            hi = mid
    x_az = (lo + hi) / 2
    t_az, _ = bubble(x_az, fit["_lam"], ci, cj, p)
    (xa, da, ta, ra), (xb, db, tb, rb) = data[k], data[k + 1]
    x_lin = xa + da * (xb - xa) / (da - db)
    return {
        "model_x1": g(x_az),
        "model_T_K": g(t_az, 8),
        "data_bracket_rows": [int(ra["row"]), int(rb["row"])],
        "data_x1_linear_interpolation_of_y1_minus_x1": g(x_lin),
        "data_T_K_bracket": [float(ta), float(tb)],
        "what": "fit quality, not validation: the model's ethanol-water azeotrope at the data's "
        "pressure against the sign change of y1 - x1 in the fit data (spec section 9.4)",
    }


# ============================================================================================
# 4. The records (spec sections 5.1, 9.5) and the fit report
# ============================================================================================


def fmt(v: float) -> str:
    s = repr(float(v))
    mant, _, exp = s.partition("e")
    if exp and "." not in mant:
        s = f"{mant}.0e{exp}"
    if exp and exp[0] not in "+-":
        s = s.replace("e", "e+")
    return s


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


MW_PROV = "CIAAW 2021 conventional atomic weights (H 1.008, C 12.011, O 15.999); S10 Q-N6 default"
DHF_MEANING = (
    "H(298.15 K) of the NASA-7 polynomial, R (a1 T0 + ... + a5 T0^5/5 + a6); "
    "the WILSON-IG-ref-v1 datum"
)
REDISTRIBUTION = (
    "unresolved: see docs/s10-rights-check.md (S10-RC-01..08); repository only, not shipped "
    "(S10 spec 9.1, Q-F3)"
)
DIMLESS = 'unit: "1", dimension: [0, 0, 0, 0, 0, 0, 0], kind: dimensionless'
ENTHALPY = "unit: J/mol, dimension: [2, 1, -2, 0, -1, 0, 0], kind: molar_enthalpy"


def records_text(
    ig: list[dict[str, Any]],
    ps: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    vle_sha: str,
    nasa_sha: str,
    sat: dict[str, Any],
) -> str:
    cp = sat["coolprop"]
    lines = [
        "# S10 real records for `wilson-ig-v1`: methanol, ethanol, water (WILSON-IG-ref-v1).",
        "#",
        "# GENERATED by docs/derivations/scripts/s10_records.py from committed inputs.",
        "# Normative text: docs/derivations/S10-spec.md sections 3, 5.1 and 9.3-9.5; ADR 0047.",
        "# Rights: docs/s10-rights-check.md. Not package data and not shipped until every row is",
        "# permitted and Frank decides (spec section 9.1, Q-F3; R-706).",
        "#",
        "# Forms (theta = T / 1000 K, R = 8.31446261815324 J/(mol K)):",
        "#   c_p^ig / R = b0 + b1 theta + b2 theta^2 + b3 theta^3 + b4 theta^4 (NASA-7 low range)",
        "#   ln(P_sat / Pa) = a + b / theta + c ln(theta) + d theta^2 (project fit, spec 9.3)",
        "#   Wilson Lambda_ij > 0, constant (project fit, spec 9.4)",
        "#",
        f"# Inputs: nasa7-low.json (nasa_gas.yaml {nasa_sha[:8]}...), saturation-points.json "
        f"(CoolProp {cp['version']}),",
        f"#   vle/kurihara1993_binaries.csv (SHA-256 {vle_sha[:16]}...).",
        "",
        "schema_version: 1",
        "record_schema: schemas/component-record.schema.json",
        "data_set: S10-wilson-ig-real-v1",
        "reference_convention: WILSON-IG-ref-v1",
        "synthetic: false",
        f"uncertainty: {q('not yet validated (S10 spec §9.6)')}",
        "data_provenance: "
        + q(
            "Ideal gas: NASA TM-4513 (McBride, Gordon, Reno 1993) via Cantera 3.2.0 nasa_gas.yaml. "
            f"Vapour pressure: project fit to CoolProp {cp['version']} saturation pressures. "
            f"Wilson: project fit to {SOURCE_PAPER} (101.3 kPa). Generated by "
            "docs/derivations/scripts/s10_records.py (S10 spec sections 9.3-9.5)."
        ),
        "domain:",
        f"  T: [{fmt(DOMAIN_T[0])}, {fmt(DOMAIN_T[1])}]",
        f"  P: [{fmt(DOMAIN_P[0])}, {fmt(DOMAIN_P[1])}]",
        "components:",
    ]
    for k, (cid, name, _, elements) in enumerate(COMPONENTS):
        mw = float(sum(ATOMIC_WEIGHT[e] * n for e, n in elements.items()) / 1000)
        note = ig[k]["note"]
        nasa_prov = f"NASA TM-4513 via Cantera 3.2.0 nasa_gas.yaml, {cid} low range (note {note})"
        p = ps[k]
        fit_prov = (
            f"Project fit (S10 spec 9.3) to CoolProp {cp['version']} saturation pressures, "
            f"{p['range'][0]}-{p['range'][1]} K, {p['n']} points; EOS {p['bibtex']}"
        )
        rights_source = (
            f"NASA TM-4513 via Cantera 3.2.0 (ideal gas); project fits to CoolProp "
            f"{cp['version']} ({p['bibtex']}) and to {SOURCE_PAPER}; CIAAW 2021 (molar mass)"
        )
        elems = ", ".join(f"{e}: {n}" for e, n in elements.items())
        lines += [
            f"  - id: {cid}",
            f"    name: {name}",
            "    synthetic: false",
            f"    molecular_weight: {{value: {fmt(mw)}, unit: kg/mol, "
            f"dimension: [0, 1, 0, 0, -1, 0, 0], kind: molar_mass, "
            f"meaning: {q(f'Molar mass of {name}; unused by wilson-ig-v1')}, role: fixed, "
            f"provenance: {q(MW_PROV)}}}",
            f"    elemental_composition: {{{elems}}}",
            "    elemental_verification: VERIFIED",
            "    parameters:",
        ]
        for n in range(5):
            lines.append(
                f"      ideal_gas_cp_b{n}: {{value: {fmt(ig[k]['b'][n])}, {DIMLESS}, "
                f"meaning: {q(f'b_{n} of c_p^ig/R = a_{n + 1} 1000^{n}')}, role: fixed, "
                f"provenance: {q(nasa_prov)}}}"
            )
        lines.append(
            f"      standard_formation_enthalpy: {{value: {fmt(ig[k]['dhf'])}, {ENTHALPY}, "
            f"meaning: {q(DHF_MEANING)}, "
            f"role: fixed, provenance: {q(nasa_prov)}}}"
        )
        for n, s in enumerate("abcd"):
            lines.append(
                f"      vapour_pressure_{s}: {{value: {fmt(p['stored'][n])}, {DIMLESS}, "
                f"meaning: {q(f'{s} of ln(P_sat/Pa) = a + b/theta + c ln theta + d theta^2')}, "
                f"role: fixed, provenance: {q(fit_prov)}}}"
            )
        lines.append(
            f"    rights: {{source: {q(rights_source)}, redistribution: {q(REDISTRIBUTION)}}}"
        )
    lines.append("# Wilson Lambda_ij (dimensionless, constant, > 0), project fits (S10 spec 9.4).")
    lines.append("wilson_lambda:")
    for f in fits:
        a, b = f["components"]
        for (i, j), v in zip(((a, b), (b, a)), f["lambda_stored"].values(), strict=True):
            prov = f"Project fit (S10 spec 9.4) to {SOURCE_PAPER}, {a}-{b}, {f['points']} points"
            lines.append(f"  - {{i: {i}, j: {j}, value: {fmt(v)}, provenance: {q(prov)}}}")
    return "\n".join(lines) + "\n"


def build(vle_path: Path) -> tuple[str, str]:
    CLAIMS.clear()
    sat = json.loads(SAT_JSON.read_text(encoding="utf-8"))
    nasa = json.loads(NASA_JSON.read_text(encoding="utf-8"))
    claim(
        "SAT-XCHECK",
        sat["water_crosscheck"]["worst_relative"] <= 1e-8,
        "the committed water saturation points agree with iapws95-v1 to <= 1e-8 relative "
        f"(worst {sat['water_crosscheck']['worst_relative']:.3e}; spec 9.2)",
    )
    ig = ideal_gas(nasa)
    ps = vapour_pressure(sat)
    vle_raw = vle_path.read_bytes()
    rows = read_vle(vle_path)
    claim(
        "VLE-P",
        {r["table"] for r in rows} == {"II"}
        and {r["system"] for r in rows} == {b[0] for b in BINARIES},
        "the transcription holds Table II's three binaries and nothing else (spec 9.4)",
    )
    singular_curve_claim()
    fits, data = [], []
    for label, i, j in BINARIES:
        b = binary_data(rows, label, i, j, ps)
        fits.append(fit_binary(b, ps))
        data.append(b)
    az = azeotrope(fits[1], data[1], ps)
    text = records_text(
        ig, ps, fits, hashlib.sha256(vle_raw).hexdigest(), nasa["source_sha256"], sat
    )
    parsed = yaml.safe_load(text)
    back = [
        [c["parameters"][f"ideal_gas_cp_b{n}"]["value"] for n in range(5)]
        + [c["parameters"]["standard_formation_enthalpy"]["value"]]
        + [c["parameters"][f"vapour_pressure_{s}"]["value"] for s in "abcd"]
        for c in parsed["components"]
    ]
    want = [ig[k]["b"] + [ig[k]["dhf"]] + ps[k]["stored"] for k in range(3)]
    claim(
        "REC-ROUNDTRIP",
        back == want and all(isinstance(v, float) for r in back for v in r),
        "records.yaml parses back to exactly the computed binary64 values (every value a float)",
    )
    for f in fits:
        f.pop("_lam")
    report = {
        "schema_version": 1,
        "what": "S10 fit claims and fit quality (spec sections 9.3-9.4 and 15). Fit quality, not "
        "validation: the same data were used to fit.",
        "generator": "docs/derivations/scripts/s10_records.py",
        "inputs_sha256": {
            "saturation-points.json": hashlib.sha256(SAT_JSON.read_bytes()).hexdigest(),
            "nasa7-low.json": hashlib.sha256(NASA_JSON.read_bytes()).hexdigest(),
            "vle": hashlib.sha256(vle_raw).hexdigest(),
        },
        "records_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "ideal_gas": [
            {"id": COMPONENTS[k][0], "dhf_J_mol_50_digits": mp.nstr(ig[k]["dhf_mp"], 20)}
            for k in range(3)
        ],
        "vapour_pressure": [
            {
                "id": p["id"],
                "fit_range_K": list(p["range"]),
                "points": p["n"],
                "max_abs_delta_ln_P": g(p["worst"]),
                "claim": 2e-3,
            }
            for p in ps
        ],
        "wilson": fits,
        "ethanol_water_azeotrope": az,
        "claims": CLAIMS,
    }
    return text, json.dumps(report, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g_ = ap.add_mutually_exclusive_group(required=True)
    g_.add_argument("--check", action="store_true")
    g_.add_argument("--emit", action="store_true")
    g_.add_argument("--extract-nasa", action="store_true")
    ap.add_argument("--nasa-yaml", type=Path, default=None)
    ap.add_argument("--vle", type=Path, default=VLE_CSV)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()
    if args.extract_nasa:
        path = args.nasa_yaml
        if path is None:
            spec = importlib.util.find_spec("cantera")
            if spec is None or spec.origin is None:
                print("UNAVAILABLE: Cantera not importable; pass --nasa-yaml")
                return 2
            path = Path(spec.origin).parent / "data" / "nasa_gas.yaml"
        NASA_JSON.write_text(json.dumps(extract_nasa(path), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {NASA_JSON.relative_to(ROOT)}")
        return 0
    if not args.vle.exists():
        print(f"UNAVAILABLE: {args.vle} is absent (the double-entered transcription, spec 9.4)")
        return 2
    records, report = build(args.vle)
    out_records, out_report = RECORDS_YAML, FIT_JSON
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        out_records, out_report = args.out_dir / "records.yaml", args.out_dir / "fit-report.json"
    elif args.vle != VLE_CSV:
        print("refused: a run on another transcription needs --out-dir (never the records)")
        return 2
    if args.emit:
        out_records.write_text(records, encoding="utf-8")
        out_report.write_text(report, encoding="utf-8")
        print(f"wrote {out_records} and {out_report}; {len(CLAIMS)} claims hold")
        return 0
    ok = all(
        p.exists() and p.read_text(encoding="utf-8") == t
        for p, t in ((out_records, records), (out_report, report))
    )
    print(
        f"{len(CLAIMS)} claims hold; records.yaml and fit-report.json {'match' if ok else 'DIFFER'}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
