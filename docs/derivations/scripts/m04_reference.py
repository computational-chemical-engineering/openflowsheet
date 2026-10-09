"""Design-lane reference generator for the M04 specification (surrogate, Default split-conformal).

Everything here follows from ``docs/derivations/M04-spec.md`` alone. It imports nothing from
``openflowsheet`` or ``benchmarks``: the numbers it emits are the *expectations* M04's tests judge
the implementation against, so they must not come from the implementation.

What it produces (spec §12):

* ``benchmarks/m04/plan-it1.json`` -- the registered sample plan of iteration 1 (spec §5): every
  draw of the training, calibration and test splits and every gradient-check stencil, as the exact
  binary64 sampler output and the exact binary64 experiment-request inputs. The implementation reads
  this file and must reproduce it bitwise from the seeds (M04.A02); the parent model is run on it.
* ``benchmarks/m04/reference_values.json`` -- the finite-sample rule and the plan's power (spec §6),
  the Clopper-Pearson bounds, the verdict-logic vectors (spec §7), the quadratic basis and its
  derivatives, the unit Jacobian at the registered states (spec §3), and the complete expected
  outcome of the pipeline on the two synthetic test-only parents and on the stand-in (spec §9).

Run from the repository root inside the project environment::

    python docs/derivations/scripts/m04_reference.py --check
    python docs/derivations/scripts/m04_reference.py --emit

``--check`` re-derives every claim the specification makes about its own numbers, refuses to
continue when one fails, and compares both files with the committed ones byte for byte. ``--emit``
runs the same claims and writes the files only when all of them hold.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from mpmath import mp, mpf

mp.dps = 50

SPEC = "docs/derivations/M04-spec.md"
GENERATOR = "docs/derivations/scripts/m04_reference.py"
OUT_VALUES = Path("benchmarks/m04/reference_values.json")
OUT_PLAN = Path("benchmarks/m04/plan-it1.json")

# -- registered constants (spec §2-§7) ----------------------------------------------------------

COMPONENTS = ("H2", "N2", "NH3", "Ar", "CH4")
NU = (-3, -1, 2, 0, 0)
#: Element matrix rows (Ar, C, H, N) over COMPONENTS (M01 spec §8.9).
ELEMENTS = ((0, 0, 0, 1, 0), (0, 0, 0, 0, 1), (2, 0, 3, 0, 4), (0, 2, 1, 0, 0))

#: The reference box (spec §4.1): (coordinate, unit, lo, hi) as decimal literals parsed to binary64.
BOX: tuple[tuple[str, str, str, str], ...] = (
    ("T", "K", "653.15", "693.15"),
    ("P", "Pa", "9.0e6", "1.0e7"),
    ("r_H2_N2", "1", "2.5", "3.0"),
    ("y_NH3", "1", "0.02", "0.04"),
    ("y_Ar", "1", "0.01", "0.03"),
    ("y_CH4", "1", "0.01", "0.04"),
    ("F_tube", "mol/s", "0.0057", "0.0086"),
)
D = len(BOX)
LO = tuple(float(b[2]) for b in BOX)
HI = tuple(float(b[3]) for b in BOX)
#: Centre and half-width, binary64, in this operation order (spec §3.1).
CENTRE = tuple((lo + hi) * 0.5 for lo, hi in zip(LO, HI, strict=True))
HALF = tuple((hi - lo) * 0.5 for lo, hi in zip(LO, HI, strict=True))

#: The parent's hard domain and data domain (M01 spec §8.12, ADR 0027; ADR 0034 D10 for the flow).
F0 = 0.007146961299302104
HARD = {
    "T": (573.15, 773.15),
    "P": (5.0e6, 15.0e6),
    "r": (1.0, 4.0),
    "inert_max": 0.2,
    "F_real": (0.5 * F0, 2.0 * F0),
}
DATA = {"T": (643.15, 733.15), "P": (5.0e6, 1.0e7), "r": (1.5, 3.0)}

N_TUBES_PLAN = 1.0
#: M01's registered nominal extent per tube (M01 spec §10.4, regression value of the parent).
XI_NOM = mpf("2.65383399725e-4")
SEED_BASE = 20261008
SPLITS = ("training", "calibration", "test", "gradient")
#: Registered counts of iteration 1 (spec §5.2).
COUNTS = {"training": 144, "calibration": 118, "test": 300, "gradient": 5}
#: The registered prefix sub-plan used by the cheap end-to-end cases (spec §9.3).
PREFIX = {"training": 72, "calibration": 39, "test": 60, "gradient": 2}
GRAD_INNER = 0.95
GRAD_STEP = 0.05

ALPHA = (1, 20)  # alpha = 1/20 as an exact rational: nominal 1 - alpha = 0.95
DELTA = mpf(1) / 20  # one-sided confidence 0.95
C_MIN = mpf(9) / 10
W = {"X": 0.0025, "dT": 1.5}  # width limits = score scales (spec §6.1)
RHO_G = 0.25
TAU_ID = 1.0e-8
ADMISSIBLE = {"X": (0.0, 0.95), "dT": (-50.0, 250.0)}

#: Synthetic test-only parents (spec §9.1).
SYN_A = (
    mpf("-0.06"),
    mpf("0.04"),
    mpf("0.03"),
    mpf("-0.05"),
    mpf("-0.01"),
    mpf("-0.015"),
    mpf("-0.08"),
)
SYN_B = (
    mpf("-0.10"),
    mpf("0.03"),
    mpf("0.02"),
    mpf("-0.04"),
    mpf("-0.01"),
    mpf("-0.01"),
    mpf("-0.04"),
)
SYN_X0 = mpf("0.16")
SYN_DT0 = mpf(80)
SYN_FAIL = mpf("1.6")  # NotAccepted iff z_T + z_F > 1.6
SYNTHETIC = {"m04-synthetic-smooth-v1": mpf(1), "m04-synthetic-rough-v1": mpf(4)}

MASK = (1 << 64) - 1
ZERO = mpf(10) ** -40


class ClaimFailedError(RuntimeError):
    """A claim the specification makes about its own numbers no longer holds."""


CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise ClaimFailedError(text)
    CLAIMS.append(text)


def s(x: Any, digits: int = 20) -> str:
    if abs(x) < ZERO:
        return "0.0"
    return str(mp.nstr(x, digits))


# -- sampler (spec §5.1) --------------------------------------------------------------------------


def seed_of(iteration: int, split: str) -> int:
    return SEED_BASE * 1000 + 10 * iteration + (SPLITS.index(split) + 1)


def splitmix64(seed: int, count: int) -> list[int]:
    state = seed & MASK
    out = []
    for _ in range(count):
        state = (state + 0x9E3779B97F4A7C15) & MASK
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        out.append(z ^ (z >> 31))
    return out


def unit_uniform(word: int) -> float:
    """U = (w >> 11) * 2^-53 in [0, 1): both factors and the product are exact in binary64."""
    return float(word >> 11) * 2.0**-53


def inner_box() -> tuple[tuple[float, ...], tuple[float, ...]]:
    lo = tuple(c - GRAD_INNER * h for c, h in zip(CENTRE, HALF, strict=True))
    hi = tuple(c + GRAD_INNER * h for c, h in zip(CENTRE, HALF, strict=True))
    return lo, hi


def draws(iteration: int, split: str, count: int) -> list[tuple[float, ...]]:
    lo, hi = (LO, HI) if split != "gradient" else inner_box()
    words = splitmix64(seed_of(iteration, split), D * count)
    out = []
    for j in range(count):
        u = tuple(lo[k] + (hi[k] - lo[k]) * unit_uniform(words[D * j + k]) for k in range(D))
        out.append(u)
    return out


def request_of(u: Sequence[float]) -> dict[str, Any]:
    """Spec §5.1: binary64 operations in exactly this order; N_tubes = 1."""
    t, p, r, y_nh3, y_ar, y_ch4, f = u
    y_n2 = (1.0 - y_nh3 - y_ar - y_ch4) / (1.0 + r)
    y_h2 = r * y_n2
    n = [f * y_h2, f * y_n2, f * y_nh3, f * y_ar, f * y_ch4]
    return {"n": n, "T": t, "P": p}


def stencil(u: Sequence[float], k: int, sign: int) -> tuple[float, ...]:
    step = GRAD_STEP * HALF[k]
    v = list(u)
    v[k] = u[k] + step if sign > 0 else u[k] - step
    return tuple(v)


# -- input map, basis, derivatives (spec §3) ------------------------------------------------------


def u_of_request(n: Sequence[Any], t: Any, p: Any, n_tubes: Any = 1) -> list[Any]:
    n = [mpf(x) for x in n]
    n_tot = n[0] + n[1] + n[2] + n[3] + n[4]
    return [
        mpf(t),
        mpf(p),
        n[0] / n[1],
        n[2] / n_tot,
        n[3] / n_tot,
        n[4] / n_tot,
        n_tot / mpf(n_tubes),
    ]


def z_of_u(u: Sequence[Any]) -> list[Any]:
    return [(mpf(u[k]) - mpf(CENTRE[k])) / mpf(HALF[k]) for k in range(D)]


def z_of_request(req: Mapping[str, Any], n_tubes: Any = 1) -> list[Any]:
    return z_of_u(u_of_request(req["n"], req["T"], req["P"], n_tubes))


PAIRS = [(i, j) for i in range(D) for j in range(i, D)]
P_TERMS = 1 + D + len(PAIRS)


def basis(z: Sequence[Any]) -> list[Any]:
    return [mpf(1)] + [mpf(x) for x in z] + [z[i] * z[j] for i, j in PAIRS]


def basis_dz(z: Sequence[Any]) -> list[list[Any]]:
    """d phi_m / d z_k as a P_TERMS x D matrix."""
    rows = [[mpf(0)] * D]
    for k in range(D):
        row = [mpf(0)] * D
        row[k] = mpf(1)
        rows.append(row)
    for i, j in PAIRS:
        row = [mpf(0)] * D
        row[i] += z[j]
        row[j] += z[i]
        rows.append(row)
    return rows


def predict(beta: Sequence[Any], z: Sequence[Any]) -> Any:
    return mp.fsum(b * f for b, f in zip(beta, basis(z), strict=True))


def grad_z(beta: Sequence[Any], z: Sequence[Any]) -> list[Any]:
    dphi = basis_dz(z)
    return [mp.fsum(beta[m] * dphi[m][k] for m in range(P_TERMS)) for k in range(D)]


def du_ds(n: Sequence[Any], n_tubes: Any) -> list[list[Any]]:
    """d u / d (n_1..n_5, T, P): a D x 7 matrix (spec §3.3)."""
    n = [mpf(x) for x in n]
    n_tot = mp.fsum(n)
    rows = []
    rows.append([0, 0, 0, 0, 0, 1, 0])
    rows.append([0, 0, 0, 0, 0, 0, 1])
    rows.append([1 / n[1], -n[0] / n[1] ** 2, 0, 0, 0, 0, 0])
    for j in (2, 3, 4):
        y_j = n[j] / n_tot
        rows.append([((1 if i == j else 0) - y_j) / n_tot for i in range(5)] + [0, 0])
    rows.append([1 / mpf(n_tubes)] * 5 + [0, 0])
    return [[mpf(x) for x in row] for row in rows]


def unit_rows(
    beta_x: Sequence[Any], beta_t: Sequence[Any], v: Sequence[Any], n_tubes: Any
) -> list[Any]:
    """The two surrogate rows (spec §3.2) at v = (n_1..n_5, T_in, P_in, xi, T_out)."""
    n, t_in, p_in, xi, t_out = v[0:5], v[5], v[6], v[7], v[8]
    z = z_of_u(u_of_request(n, t_in, p_in, n_tubes))
    return [xi - predict(beta_x, z) * n[1], t_out - t_in - predict(beta_t, z)]


def unit_jacobian(
    beta_x: Sequence[Any], beta_t: Sequence[Any], v: Sequence[Any], n_tubes: Any
) -> list[list[Any]]:
    """Closed-form chain rule (spec §3.3).

    Rows (R_xi, R_T); columns (n_1..n_5, T_in, P_in, xi, T_out).
    """
    n, t_in, p_in = v[0:5], v[5], v[6]
    z = z_of_u(u_of_request(n, t_in, p_in, n_tubes))
    jus = du_ds(n, n_tubes)
    gx = grad_z(beta_x, z)
    gt = grad_z(beta_t, z)
    x_pred = predict(beta_x, z)
    dx_ds = [mp.fsum(gx[k] / mpf(HALF[k]) * jus[k][c] for k in range(D)) for c in range(7)]
    dt_ds = [mp.fsum(gt[k] / mpf(HALF[k]) * jus[k][c] for k in range(D)) for c in range(7)]
    row_xi = [-dx_ds[c] * mpf(n[1]) for c in range(7)]
    row_xi[1] -= x_pred
    row_xi += [mpf(1), mpf(0)]
    row_t = [-dt_ds[c] for c in range(7)]
    row_t[5] -= 1
    row_t += [mpf(0), mpf(1)]
    return [row_xi, row_t]


def cancellation_ratio(
    beta_x: Sequence[Any], beta_t: Sequence[Any], v: Sequence[Any], n_tubes: Any
) -> Any:
    """max over the 14 inlet entries of (sum of |terms|) / |entry| (spec §11, A14's floor)."""
    n, t_in, p_in = v[0:5], v[5], v[6]
    z = z_of_u(u_of_request(n, t_in, p_in, n_tubes))
    jus = du_ds(n, n_tubes)
    dphi = basis_dz(z)
    jac = unit_jacobian(beta_x, beta_t, v, n_tubes)
    worst = mpf(0)
    for r, beta in ((0, beta_x), (1, beta_t)):
        for c in range(7):
            terms = mp.fsum(
                abs(beta[m] * dphi[m][k] / mpf(HALF[k]) * jus[k][c])
                for k in range(D)
                for m in range(P_TERMS)
            )
            if r == 0:
                terms = terms * abs(mpf(n[1])) + (abs(predict(beta_x, z)) if c == 1 else 0)
            else:
                terms = terms + (1 if c == 5 else 0)
            worst = max(worst, terms / abs(jac[r][c]))
    return worst


def numeric_jacobian(
    beta_x: Sequence[Any], beta_t: Sequence[Any], v: Sequence[Any], n_tubes: Any
) -> list[list[Any]]:
    out = [[mpf(0)] * 9 for _ in range(2)]
    for c in range(9):
        for r in range(2):

            def along(x: Any, c: int = c, r: int = r) -> Any:
                w = [mpf(e) for e in v]
                w[c] = x
                return unit_rows(beta_x, beta_t, w, n_tubes)[r]

            out[r][c] = mp.diff(along, mpf(v[c]))
    return out


# -- synthetic parents (spec §9.1) ----------------------------------------------------------------


def synthetic_truth(z: Sequence[Any], amplitude: Any) -> dict[str, Any] | None:
    if z[0] + z[6] > SYN_FAIL:
        return None
    eta_x = mp.fsum(a * x for a, x in zip(SYN_A, z, strict=True))
    eta_t = mp.fsum(b * x for b, x in zip(SYN_B, z, strict=True))
    return {"X": SYN_X0 * mp.exp(amplitude * eta_x), "dT": SYN_DT0 * mp.exp(amplitude * eta_t)}


def synthetic_grad(z: Sequence[Any], amplitude: Any) -> dict[str, list[Any]]:
    t = synthetic_truth(z, amplitude)
    assert t is not None
    return {
        "X": [amplitude * a * t["X"] for a in SYN_A],
        "dT": [amplitude * b * t["dT"] for b in SYN_B],
    }


# -- least squares (spec §3.4) --------------------------------------------------------------------


def lstsq(rows: Sequence[Sequence[Any]], rhs: Sequence[Any]) -> list[Any]:
    a = mp.matrix([list(r) for r in rows])
    ata = a.T * a
    atb = a.T * mp.matrix(list(rhs))
    sol = mp.lu_solve(ata, atb)
    return [sol[i] for i in range(sol.rows)]


def singular_ratio(rows: Sequence[Sequence[Any]]) -> Any:
    a = mp.matrix([list(r) for r in rows])
    ev = mp.eigsy(a.T * a, eigvals_only=True)
    vals = sorted(ev[i] for i in range(ev.rows))
    return mp.sqrt(vals[0] / vals[-1])


# -- finite-sample rule, Clopper-Pearson, power (spec §6) -----------------------------------------


def k_index(n: int) -> int:
    num, den = ALPHA
    return -((-(n + 1) * (den - num)) // den)


def quantile(scores: Sequence[Any | None]) -> tuple[int, Any | None, str | None]:
    """(k, q_hat, refusal): None scores are +inf (a draw without an ok result)."""
    n = len(scores)
    k = k_index(n)
    if k > n:
        return k, None, "calibration_too_small"
    finite = sorted(x for x in scores if x is not None)
    if k > len(finite):
        return k, None, "band_not_finite"
    return k, finite[k - 1], None


def cp_lower(h: int, m: int) -> Any:
    if h == 0:
        return mpf(0)
    f = lambda x: mp.betainc(h, m - h + 1, 0, x, regularized=True) - DELTA  # noqa: E731
    lo, hi = mpf(0), mpf(1)
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def binom_tail(m: int, h: int, p: Any) -> Any:
    """P(Bin(m, p) >= h)."""
    return mp.fsum(mp.binomial(m, j) * p**j * (1 - p) ** (m - j) for j in range(h, m + 1))


def h_min(m: int) -> int | None:
    for h in range(m + 1):
        if binom_tail(m, h, C_MIN) <= DELTA:
            return h
    return None


def m_min() -> int:
    m = 1
    while cp_lower(m, m) < C_MIN:
        m += 1
    return m


def n_min() -> int:
    n = 1
    while k_index(n) > n:
        n += 1
    return n


def power(n: int, m: int) -> dict[str, Any]:
    k = k_index(n)
    a, b = k, n + 1 - k
    hm = h_min(m)
    assert hm is not None
    pw = mp.fsum(
        mp.binomial(m, h) * mp.beta(h + a, m - h + b) / mp.beta(a, b) for h in range(hm, m + 1)
    )
    return {
        "n": n,
        "m": m,
        "k": k,
        "k_over_n_plus_1": s(mpf(k) / (n + 1)),
        "p_conditional_coverage_below_minimum": s(mp.betainc(a, b, 0, C_MIN, regularized=True)),
        "h_min": hm,
        "power_no_failures": s(pw),
        "false_pass_at_minimum": s(binom_tail(m, hm, C_MIN)),
        "false_pass_one_below_h_min": s(binom_tail(m, hm - 1, C_MIN)),
    }


def power_with_failures(n: int, m: int, f: Any) -> dict[str, Any]:
    """Spec §5.3: an atom of mass f at +inf. The band is finite iff U_(k) < 1 - f, and then its
    coverage of P_ref is C = U_(k) ~ Beta(k, n + 1 - k); H | C ~ Bin(m, C)."""
    k = k_index(n)
    a, b = k, n + 1 - k
    hm = h_min(m)
    assert hm is not None
    dens = lambda c: c ** (a - 1) * (1 - c) ** (b - 1) / mp.beta(a, b)  # noqa: E731
    tail = lambda c: mp.betainc(hm, m - hm + 1, 0, c, regularized=True)  # noqa: E731
    pw = mp.quad(lambda c: dens(c) * tail(c), [0, mpf("0.8"), mpf("0.9"), 1 - f])
    return {
        "failure_fraction": s(f, 6),
        "p_band_finite": s(mp.betainc(a, b, 0, 1 - f, regularized=True), 6),
        "power": s(pw, 6),
    }


# -- verdict logic (spec §7) ----------------------------------------------------------------------


def verdict(case: Mapping[str, Any]) -> dict[str, Any]:
    """The registered verdict function: precedence IE > NP > PROMOTABLE; all reasons listed."""
    ie: list[str] = []
    np_: list[str] = []
    if not case.get("budget_ok", True):
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "insufficient": ["budget_below_plan"],
            "not_promotable": [],
            "k": None,
            "q_hat": None,
            "hits": None,
            "lower_bound": None,
        }
    if not case.get("plan_complete", True):
        ie.append("plan_incomplete")
    if case["training_ok"] < P_TERMS or case["singular_ratio"] < TAU_ID:
        ie.append("training_unidentifiable")
    k, q_hat, refusal = quantile(case["calibration_scores"])
    if refusal == "calibration_too_small":
        ie.append("calibration_too_small")
    elif refusal == "band_not_finite":
        np_.append("band_not_finite")
    m = len(case["test_scores"])
    hits = lower = None
    if cp_lower(m, m) < C_MIN:
        ie.append("test_too_small")
    if q_hat is not None:
        hits = sum(1 for x in case["test_scores"] if x is not None and x <= q_hat)
        lower = cp_lower(hits, m)
        if q_hat > 1:
            np_.append("width_limit_exceeded")
        hm = h_min(m)
        if "test_too_small" not in ie and (hm is None or hits < hm):
            np_.append("coverage_bound_below_minimum")
    if case["gradient_errors"] is None:
        ie.append("gradient_check_incomplete")
    elif max(case["gradient_errors"]) > RHO_G:
        np_.append("gradient_limit_exceeded")
    if case.get("inadmissible", 0) > 0:
        np_.append("inadmissible_prediction")
    if case.get("extrapolated", 0) > 0:
        np_.append("parent_extrapolated")
    v = "INSUFFICIENT_EVIDENCE" if ie else ("NOT_PROMOTABLE" if np_ else "PROMOTABLE")
    return {
        "verdict": v,
        "insufficient": ie,
        "not_promotable": np_,
        "k": k,
        "q_hat": None if q_hat is None else s(q_hat),
        "hits": hits,
        "lower_bound": None if lower is None else s(lower),
    }


def verdict_vectors() -> list[dict[str, Any]]:
    base = {
        "training_ok": 144,
        "singular_ratio": mpf("0.1"),
        "gradient_errors": [mpf("0.01")],
        "inadmissible": 0,
        "extrapolated": 0,
    }
    cal19 = [mpf(i) / 100 for i in range(19, 0, -1)]  # 0.19 ... 0.01, unsorted on purpose
    test29 = [mpf("0.05")] * 29
    cases: list[tuple[str, dict[str, Any], str]] = [
        (
            "V01",
            {**base, "calibration_scores": cal19, "test_scores": test29},
            "n = 19 gives k = 19 = n: q_hat is the largest score, 0.19; m = 29 is the smallest "
            "test set "
            "whose all-hit bound 0.05^(1/29) = 0.90185 clears 0.90: PROMOTABLE.",
        ),
        (
            "V02",
            {**base, "calibration_scores": cal19[:18], "test_scores": test29},
            "n = 18 gives k = 19 > n: calibration_too_small (the uncorrected index ceil(0.95 n) "
            "= 18 "
            "would return the maximum).",
        ),
        (
            "V03",
            {**base, "calibration_scores": cal19, "test_scores": test29[:28]},
            "m = 28: even 28 hits give a bound 0.89866 below 0.90, so a pass is impossible: "
            "test_too_small.",
        ),
        (
            "V04",
            {**base, "calibration_scores": [None] + cal19[1:], "test_scores": test29},
            "One failed calibration draw (+inf) when k = n = 19: no finite band, "
            "band_not_finite; the "
            "test set is not scored against an infinite band.",
        ),
        (
            "V05",
            {**base, "calibration_scores": [x * 10 for x in cal19], "test_scores": test29},
            "Scores x10: q_hat = 1.9 > 1: width_limit_exceeded; coverage still passes (all hits).",
        ),
        (
            "V06",
            {**base, "calibration_scores": cal19, "test_scores": [mpf("0.5")] + test29[1:]},
            "One test miss (0.5 > 0.19) of 29: 28/29 hits, bound below 0.90: "
            "coverage_bound_below_minimum.",
        ),
        (
            "V07",
            {**base, "calibration_scores": cal19, "test_scores": [None] + test29[1:]},
            "One failed test draw counts as a miss, exactly as V06.",
        ),
        (
            "V08",
            {
                **base,
                "gradient_errors": [mpf("0.01"), mpf("0.30")],
                "calibration_scores": cal19,
                "test_scores": test29,
            },
            "A gradient error 0.30 > 0.25: gradient_limit_exceeded.",
        ),
        (
            "V09",
            {**base, "gradient_errors": None, "calibration_scores": cal19, "test_scores": test29},
            "A gradient point with a failed stencil experiment: gradient_check_incomplete.",
        ),
        (
            "V10",
            {**base, "inadmissible": 1, "calibration_scores": cal19, "test_scores": test29},
            "One inadmissible prediction inside the reference box: inadmissible_prediction.",
        ),
        (
            "V11",
            {**base, "training_ok": 35, "calibration_scores": cal19, "test_scores": test29},
            "35 ok training results < 36 coefficients: training_unidentifiable.",
        ),
        (
            "V12",
            {
                **base,
                "singular_ratio": mpf("1e-9"),
                "calibration_scores": cal19,
                "test_scores": test29,
            },
            "Singular-value ratio 1e-9 < tau_id 1e-8: training_unidentifiable.",
        ),
        (
            "V13",
            {
                **base,
                "training_ok": 35,
                "calibration_scores": [x * 10 for x in cal19],
                "test_scores": test29,
            },
            "IE and NP together: the verdict is INSUFFICIENT_EVIDENCE and both lists are recorded.",
        ),
        (
            "V14",
            {**base, "plan_complete": False, "calibration_scores": cal19, "test_scores": test29},
            "A registered draw without a deterministic result: plan_incomplete.",
        ),
        (
            "V15",
            {**base, "budget_ok": False, "calibration_scores": cal19, "test_scores": test29},
            "Approved budget below the plan's cold-experiment count: refused before any "
            "experiment.",
        ),
        (
            "V16",
            {**base, "extrapolated": 1, "calibration_scores": cal19, "test_scores": test29},
            "A registered draw the parent flags extrapolated (contradicts box within data domain).",
        ),
    ]
    out = []
    for label, case, why in cases:
        res = verdict(case)
        out.append(
            {
                "id": label,
                "why": why,
                "input": {
                    "training_ok": case["training_ok"],
                    "singular_ratio": s(case["singular_ratio"]),
                    "calibration_scores": [
                        None if x is None else s(x) for x in case["calibration_scores"]
                    ],
                    "test_scores": [None if x is None else s(x) for x in case["test_scores"]],
                    "gradient_errors": None
                    if case["gradient_errors"] is None
                    else [s(x) for x in case["gradient_errors"]],
                    "inadmissible": case.get("inadmissible", 0),
                    "extrapolated": case.get("extrapolated", 0),
                    "plan_complete": case.get("plan_complete", True),
                    "budget_ok": case.get("budget_ok", True),
                },
                "expected": res,
            }
        )
    by = {o["id"]: o["expected"] for o in out}
    claim(by["V01"]["verdict"] == "PROMOTABLE", "V01 is PROMOTABLE")
    claim(by["V02"]["insufficient"] == ["calibration_too_small"], "V02 refuses n = 18")
    claim(by["V03"]["insufficient"] == ["test_too_small"], "V03 refuses m = 28")
    claim(by["V04"]["not_promotable"] == ["band_not_finite"], "V04 has no finite band")
    claim(by["V05"]["not_promotable"] == ["width_limit_exceeded"], "V05 fails width only")
    claim(
        by["V06"]["not_promotable"] == ["coverage_bound_below_minimum"], "V06 fails coverage only"
    )
    claim(by["V06"]["hits"] == 28 and by["V07"]["hits"] == 28, "V06 and V07 both count 28 hits")
    claim(by["V08"]["not_promotable"] == ["gradient_limit_exceeded"], "V08 fails gradient only")
    claim(by["V09"]["insufficient"] == ["gradient_check_incomplete"], "V09 incomplete gradient")
    claim(by["V10"]["not_promotable"] == ["inadmissible_prediction"], "V10 inadmissible")
    claim(by["V11"]["insufficient"] == ["training_unidentifiable"], "V11 too few training results")
    claim(by["V12"]["insufficient"] == ["training_unidentifiable"], "V12 rank test")
    claim(
        by["V13"]["verdict"] == "INSUFFICIENT_EVIDENCE"
        and by["V13"]["not_promotable"] == ["width_limit_exceeded"],
        "V13 records IE and NP together",
    )
    claim(by["V14"]["insufficient"] == ["plan_incomplete"], "V14 plan incomplete")
    claim(by["V15"]["insufficient"] == ["budget_below_plan"], "V15 budget refusal")
    claim(by["V16"]["not_promotable"] == ["parent_extrapolated"], "V16 extrapolated")
    claim(len({o["expected"]["verdict"] for o in out}) == 3, "the vectors reach all three verdicts")
    return out


# -- the plan (spec §5) ---------------------------------------------------------------------------


def in_hard(u: Sequence[Any], real: bool) -> bool:
    t, p, r, _, y_ar, y_ch4, f = u
    ok = HARD["T"][0] <= t <= HARD["T"][1] and HARD["P"][0] <= p <= HARD["P"][1]
    ok = ok and HARD["r"][0] <= r <= HARD["r"][1] and y_ar + y_ch4 <= HARD["inert_max"]
    if real:
        ok = ok and HARD["F_real"][0] <= f <= HARD["F_real"][1]
    return ok


def in_data(u: Sequence[Any]) -> bool:
    t, p, r = u[0], u[1], u[2]
    return (
        DATA["T"][0] <= t <= DATA["T"][1]
        and DATA["P"][0] <= p <= DATA["P"][1]
        and DATA["r"][0] <= r <= DATA["r"][1]
    )


def build_plan() -> dict[str, Any]:
    plan: dict[str, Any] = {}
    for split in ("training", "calibration", "test"):
        rows = []
        for j, u in enumerate(draws(1, split, COUNTS[split])):
            rows.append({"index": j, "u": list(u), "request": request_of(u)})
        plan[split] = rows
    centres = []
    for j, u in enumerate(draws(1, "gradient", COUNTS["gradient"])):
        sten = []
        for k in range(D):
            for sign in (+1, -1):
                v = stencil(u, k, sign)
                sten.append(
                    {"coordinate": BOX[k][0], "sign": sign, "u": list(v), "request": request_of(v)}
                )
        centres.append({"index": j, "u": list(u), "request": request_of(u), "stencil": sten})
    plan["gradient"] = centres
    return plan


def plan_claims(plan: Mapping[str, Any]) -> dict[str, Any]:
    # bitwise sampler vs mpmath: each u within one rounding of the exact affine map
    for split in ("training", "calibration", "test"):
        words = splitmix64(seed_of(1, split), D * COUNTS[split])
        for row in plan[split]:
            j = row["index"]
            for k in range(D):
                exact = (
                    mpf(LO[k])
                    + (mpf(HI[k]) - mpf(LO[k])) * mpf(words[D * j + k] >> 11) / mpf(2) ** 53
                )
                claim(
                    abs(mpf(row["u"][k]) - exact) <= abs(exact) * mpf(2) ** -51,
                    f"{split}[{j}].u[{k}] is the affine sample to within 2 ulp",
                )
    all_u: list[tuple[str, int, list[Any]]] = []
    for split in ("training", "calibration", "test"):
        for row in plan[split]:
            u_req = u_of_request(row["request"]["n"], row["request"]["T"], row["request"]["P"])
            z = z_of_u(u_req)
            claim(
                all(-1 <= x <= 1 for x in z), f"{split}[{row['index']}] lies in the reference box"
            )
            claim(
                in_hard(u_req, real=True) and in_data(u_req),
                f"{split}[{row['index']}] in hard and data domain",
            )
            all_u.append((split, row["index"], z))
    for c in plan["gradient"]:
        for st in c["stencil"]:
            u_req = u_of_request(st["request"]["n"], st["request"]["T"], st["request"]["P"])
            z = z_of_u(u_req)
            claim(all(-1 <= x <= 1 for x in z), f"gradient[{c['index']}] stencil inside the box")
            claim(in_hard(u_req, real=True) and in_data(u_req), "stencil in hard and data domain")
    # no near-duplicate between training and calibration/test (leakage, blueprint 9.1)
    train = [z for sp, _, z in all_u if sp == "training"]
    held = [z for sp, _, z in all_u if sp != "training"]
    dmin = min(max(abs(a - b) for a, b in zip(zt, zh, strict=True)) for zt in train for zh in held)
    claim(
        dmin >= mpf("0.05"),
        "every held-out draw is >= 0.05 (inf-norm, scaled) from every training draw",
    )
    keys = set()
    for split in ("training", "calibration", "test"):
        for row in plan[split]:
            keys.add(json.dumps(row["request"]))
    for c in plan["gradient"]:
        for st in c["stencil"]:
            keys.add(json.dumps(st["request"]))
    n_exp = sum(COUNTS[x] for x in ("training", "calibration", "test")) + COUNTS["gradient"] * 2 * D
    claim(len(keys) == n_exp, "all registered experiment requests are distinct")
    # box within hard and data domain at its corners (the box is a product, so corners suffice)
    claim(
        in_hard(LO, True) and in_hard(HI, True) and in_data(LO) and in_data(HI),
        "box corners in both domains",
    )
    claim(HI[4] + HI[5] <= HARD["inert_max"], "max inerts within hard domain")
    # The convex hull of the training draws covers little of the support of P_ref (spec §3.6):
    # count the test draws inside it by LP feasibility (HiGHS). Only the bound is asserted, so a
    # borderline point flipping with the LP solver's version cannot change the emitted bytes.
    import numpy as np
    from scipy.optimize import linprog

    def zf(row: Mapping[str, Any]) -> list[float]:
        return [float(x) for x in z_of_u(row["u"])]

    tz = np.array([zf(r) for r in plan["training"]])
    a_eq = np.vstack([tz.T, np.ones(len(tz))])
    inside = 0
    for row in plan["test"]:
        b_eq = np.concatenate([np.array(zf(row)), [1.0]])
        res = linprog(np.zeros(len(tz)), A_eq=a_eq, b_eq=b_eq, bounds=(0, None), method="highs")
        inside += int(res.status == 0)
    claim(inside < 30, "fewer than 30 of the 300 test draws lie in the training draws' convex hull")
    return {"min_inf_distance_training_to_heldout": s(dmin, 6), "experiments": n_exp}


# -- later iterations (spec §5.5, Amendment 1 §A1.2) ---------------------------------------------

ITERATIONS: Final = (2, 3)


def fresh_splits(iteration: int) -> tuple[str, ...]:
    """The P_ref splits an iteration draws itself: iteration 1 all three, later ones no training."""
    return ("training", "calibration", "test") if iteration == 1 else ("calibration", "test")


def build_plan_iteration(iteration: int) -> dict[str, Any]:
    """Iteration i >= 2: training is every P_ref draw of iterations < i, listed by origin, in
    iteration order and then split and index order; calibration, test and gradient are fresh."""
    assert iteration >= 2
    training = []
    for j in range(1, iteration):
        for split in fresh_splits(j):
            for index in range(COUNTS[split]):
                origin = {"iteration": j, "split": split, "index": index}
                training.append({"index": len(training), "origin": origin})
    plan: dict[str, Any] = {"training": training}
    for split in ("calibration", "test"):
        plan[split] = [
            {"index": j, "u": list(u), "request": request_of(u)}
            for j, u in enumerate(draws(iteration, split, COUNTS[split]))
        ]
    centres = []
    for j, u in enumerate(draws(iteration, "gradient", COUNTS["gradient"])):
        sten = []
        for k in range(D):
            for sign in (+1, -1):
                v = stencil(u, k, sign)
                sten.append(
                    {"coordinate": BOX[k][0], "sign": sign, "u": list(v), "request": request_of(v)}
                )
        centres.append({"index": j, "u": list(u), "request": request_of(u), "stencil": sten})
    plan["gradient"] = centres
    return plan


def plan_requests(plans: Mapping[int, Mapping[str, Any]], iteration: int) -> list[str]:
    """Every request an iteration's own plan file carries (training origins excluded)."""
    plan = plans[iteration]
    out = [
        json.dumps(row["request"])
        for split in ("training", "calibration", "test")
        for row in plan[split]
        if "request" in row
    ]
    out += [json.dumps(st["request"]) for c in plan["gradient"] for st in c["stencil"]]
    return out


def iteration_claims(plans: Mapping[int, Mapping[str, Any]], iteration: int) -> dict[str, Any]:
    plan = plans[iteration]
    expected = sum(COUNTS[sp] for j in range(1, iteration) for sp in fresh_splits(j))
    claim(len(plan["training"]) == expected, f"it{iteration}: training lists {expected} origins")
    for row in plan["training"]:
        o = row["origin"]
        claim(o["iteration"] < iteration, f"it{iteration}: training origins are earlier draws")
    for split in ("calibration", "test"):
        for row in plan[split]:
            z = z_of_request(row["request"])
            claim(all(-1 <= x <= 1 for x in z), f"it{iteration} {split}[i] lies in the box")
            u_req = u_of_request(row["request"]["n"], row["request"]["T"], row["request"]["P"])
            claim(in_hard(u_req, real=True) and in_data(u_req), f"it{iteration} {split}[i] domains")
    for c in plan["gradient"]:
        for st in c["stencil"]:
            z = z_of_request(st["request"])
            claim(all(-1 <= x <= 1 for x in z), f"it{iteration}: stencil inside the box")
    earlier: set[str] = set()
    for j in range(1, iteration):
        earlier |= set(plan_requests(plans, j))
    own = plan_requests(plans, iteration)
    claim(len(set(own)) == len(own), f"it{iteration}: its own requests are distinct")
    claim(not (set(own) & earlier), f"it{iteration}: no request repeats an earlier iteration's")

    def z_rows(rows: Sequence[Mapping[str, Any]]) -> list[list[Any]]:
        return [z_of_request(r["request"]) for r in rows]

    inherited = []
    for row in plan["training"]:
        o = row["origin"]
        inherited.append(z_of_request(plans[o["iteration"]][o["split"]][o["index"]]["request"]))
    held = z_rows(plan["calibration"]) + z_rows(plan["test"])
    dmin = min(
        max(abs(a - b) for a, b in zip(zt, zh, strict=True)) for zt in inherited for zh in held
    )
    claim(
        dmin >= mpf("0.05"), f"it{iteration}: every held-out draw >= 0.05 from every training draw"
    )
    return {
        "iteration": iteration,
        "training_origins": expected,
        "fresh_experiments": sum(COUNTS[sp] for sp in ("calibration", "test"))
        + COUNTS["gradient"] * 2 * D,
        "min_inf_distance_training_to_heldout": s(dmin, 6),
    }


def a11_fixture() -> dict[str, Any]:
    """M04.A11 (Amendment 1): the prefix training draws with F set to the box centre."""
    rows = []
    for u in draws(1, "training", PREFIX["training"]):
        v = list(u)
        v[6] = CENTRE[6]
        rows.append(basis(z_of_request(request_of(v))))
    z7 = max(abs(r[7]) for r in rows)
    # The z_F^2 column is ~1e-30, so the Gram matrix's smallest eigenvalue is ~1e-60 of its largest:
    # evaluated at 150 digits.
    with mp.workdps(150):
        ratio = singular_ratio(rows)
    claim(z7 < mpf("1e-12") and z7 > 0, "A11: z_F is roundoff-small but not exactly zero")
    claim(ratio < mpf("1e-10"), "A11: the singular-value ratio is far below tau_id = 1e-8")
    return {
        "max_abs_z_F": s(z7, 3),
        "singular_value_ratio": s(ratio, 3),
        "vanishing_columns": ["z7"] + [f"z{i + 1}*z7" for i in range(D)],
    }


# -- pipeline expectations on a synthetic parent (spec §9) ----------------------------------------


def run_case(
    plan: Mapping[str, Any], amplitude: Any | None, counts: Mapping[str, int], label: str
) -> dict[str, Any]:
    """amplitude None = the stand-in (X = 0.25, dT = 0)."""

    def truth(req: Mapping[str, Any]) -> dict[str, Any] | None:
        if amplitude is None:
            return {"X": mpf("0.25"), "dT": mpf(0)}
        return synthetic_truth(z_of_request(req), amplitude)

    rec: dict[str, Any] = {}
    train_rows, train_y = [], {"X": [], "dT": []}
    failed = {}
    for split in ("training", "calibration", "test"):
        failed[split] = []
        for row in plan[split][: counts[split]]:
            t = truth(row["request"])
            if t is None:
                failed[split].append(row["index"])
            elif split == "training":
                train_rows.append(basis(z_of_request(row["request"])))
                train_y["X"].append(t["X"])
                train_y["dT"].append(t["dT"])
    ratio = singular_ratio(train_rows)
    beta = {o: lstsq(train_rows, train_y[o]) for o in ("X", "dT")}
    resid = {
        o: [predict(beta[o], r[1 : 1 + D]) - y for r, y in zip(train_rows, train_y[o], strict=True)]
        for o in ("X", "dT")
    }

    def score(req: Mapping[str, Any]) -> tuple[Any | None, Any | None]:
        t = truth(req)
        z = z_of_request(req)
        pred = {o: predict(beta[o], z) for o in ("X", "dT")}
        inad = not (
            ADMISSIBLE["X"][0]
            <= pred["X"]
            <= min(ADMISSIBLE["X"][1], u_of_request(req["n"], req["T"], req["P"])[2] / 3)
            and ADMISSIBLE["dT"][0] <= pred["dT"] <= ADMISSIBLE["dT"][1]
        )
        if t is None:
            return None, inad
        return max(
            abs(t["X"] - pred["X"]) / mpf(W["X"]), abs(t["dT"] - pred["dT"]) / mpf(W["dT"])
        ), inad

    cal, test, inad = [], [], 0
    for split, sink in (("calibration", cal), ("test", test)):
        for row in plan[split][: counts[split]]:
            sc, bad = score(row["request"])
            sink.append(sc)
            inad += int(bad)
    k, q_hat, refusal = quantile(cal)
    # gradients
    grad_err = []
    grad_rec = []
    fd_trunc = mpf(0)
    complete = True
    for c in plan["gradient"][: counts["gradient"]]:
        zc = z_of_request(c["request"])
        fd = {"X": [mpf(0)] * D, "dT": [mpf(0)] * D}
        ok = True
        for k_ in range(D):
            plus = c["stencil"][2 * k_]["request"]
            minus = c["stencil"][2 * k_ + 1]["request"]
            tp, tm = truth(plus), truth(minus)
            if tp is None or tm is None:
                ok = False
                break
            dz = z_of_request(plus)[k_] - z_of_request(minus)[k_]
            for o in ("X", "dT"):
                fd[o][k_] = (tp[o] - tm[o]) / dz
        if not ok:
            complete = False
            grad_rec.append({"index": c["index"], "status": "parent_failed"})
            continue
        entry = {"index": c["index"], "status": "ok"}
        for o in ("X", "dT"):
            g = grad_z(beta[o], zc)
            num = mp.sqrt(mp.fsum((a - b) ** 2 for a, b in zip(g, fd[o], strict=True)))
            den = max(mp.sqrt(mp.fsum(b**2 for b in fd[o])), mpf(W[o]))
            e = num / den
            grad_err.append(e)
            entry[o] = {
                "fd": [s(x) for x in fd[o]],
                "surrogate": [s(x) for x in g],
                "relative_error": s(e),
            }
            if amplitude is not None:
                exact = synthetic_grad(zc, amplitude)[o]
                tr = mp.sqrt(
                    mp.fsum((a - b) ** 2 for a, b in zip(fd[o], exact, strict=True))
                ) / mp.sqrt(mp.fsum(b**2 for b in exact))
                fd_trunc = max(fd_trunc, tr)
        grad_rec.append(entry)
    res = verdict(
        {
            "training_ok": len(train_rows),
            "singular_ratio": ratio,
            "calibration_scores": cal,
            "test_scores": test,
            "gradient_errors": grad_err if complete else None,
            "inadmissible": inad,
        }
    )
    rec = {
        "case": label,
        "parent": "stand-in" if amplitude is None else f"synthetic amplitude {s(amplitude)}",
        "counts": dict(counts),
        "failed_indices": failed,
        "training_ok": len(train_rows),
        "singular_value_ratio": s(ratio, 12),
        "coefficients": {o: [s(b) for b in beta[o]] for o in ("X", "dT")},
        "training_rms": {
            o: s(mp.sqrt(mp.fsum(r**2 for r in resid[o]) / len(resid[o])), 12) for o in ("X", "dT")
        },
        "calibration_scores": [None if x is None else s(x) for x in cal],
        "test_scores": [None if x is None else s(x) for x in test],
        "inadmissible": inad,
        "gradient": grad_rec,
        "result": res,
    }
    if amplitude is not None:
        rec["fd_truncation_relative_max"] = s(fd_trunc, 6)
    # margins that make the implementation's integer outcomes exact (spec §10.3)
    if q_hat is not None:
        fin = sorted(x for x in cal if x is not None)
        gaps = [abs(fin[k - 1] - fin[i]) for i in (k - 2, k) if 0 <= i < len(fin)]
        tgap = min((abs(x - q_hat) for x in test if x is not None), default=mpf(1))
        rec["margins"] = {
            "order_statistic_gap": s(min(gaps), 6),
            "test_to_q_hat": s(tgap, 6),
            "q_hat_to_width_limit": s(abs(q_hat - 1), 6),
        }
    return rec


def failure_margin(plan: Mapping[str, Any]) -> Any:
    reqs = [row["request"] for sp in ("training", "calibration", "test") for row in plan[sp]]
    reqs += [st["request"] for c in plan["gradient"] for st in c["stencil"]]
    return min(abs(z[0] + z[6] - SYN_FAIL) for z in (z_of_request(r) for r in reqs))


def synthetic_claims(
    smooth: Mapping[str, Any], rough: Mapping[str, Any], standin: Mapping[str, Any]
) -> None:
    for rec in (smooth, rough):
        m = rec["margins"]
        claim(
            mpf(m["order_statistic_gap"]) > mpf("1e-8") and mpf(m["test_to_q_hat"]) > mpf("1e-8"),
            f"{rec['case']}: no score within 1e-8 of q_hat (integer outcomes are exact)",
        )
        claim(
            mpf(m["q_hat_to_width_limit"]) > mpf("1e-6"),
            f"{rec['case']}: q_hat not within 1e-6 of 1",
        )
        claim(
            mpf(rec["fd_truncation_relative_max"]) < mpf("1e-3"),
            f"{rec['case']}: FD truncation < 1e-3",
        )
    claim(
        all(len(smooth["failed_indices"][sp]) >= 1 for sp in ("training", "calibration", "test")),
        "smooth: the failure region removes at least one draw from every split",
    )
    claim(
        smooth["result"]["verdict"] == "PROMOTABLE",
        "smooth (full plan): PROMOTABLE, the end-to-end promotion case",
    )
    claim("width_limit_exceeded" not in smooth["result"]["not_promotable"], "smooth: width passes")
    claim(mpf(smooth["result"]["q_hat"]) > mpf("1e-3"), "smooth: q_hat does not vanish (rule 3)")
    claim("width_limit_exceeded" in rough["result"]["not_promotable"], "rough: width fails")
    for o in ("X", "dT"):
        beta = [mpf(x) for x in smooth["coefficients"][o]]
        top = max(abs(b) for b in beta)
        gap = min(abs(a - b) for i, a in enumerate(beta) for b in beta[i + 1 :])
        claim(
            gap / top > mpf("1e-8"),
            f"smooth {o}: coefficients pairwise distinct beyond 1e-8 of max",
        )
        claim(
            min(abs(b) for b in beta) / top > mpf("1e-8"),
            f"smooth {o}: no coefficient below 1e-8 of max",
        )
    claim(
        all(mpf(x) == 0 or abs(mpf(x)) < mpf("1e-30") for x in standin["coefficients"]["X"][1:])
        and mpf(standin["coefficients"]["X"][0]) == mpf("0.25"),
        "stand-in: beta_X = 0.25 e_0",
    )
    claim(
        all(mpf(x) == 0 or abs(mpf(x)) < mpf("1e-30") for x in standin["coefficients"]["dT"]),
        "stand-in: beta_T = 0",
    )
    claim(standin["result"]["q_hat"] == "0.0", "stand-in: the exact band vanishes")


# -- Jacobian states (spec §3.5) ------------------------------------------------------------------


def jacobian_states(beta: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    # Inlets are binary64 values (the implementation's inputs); the generator reads them exactly.
    nominal_y = (0.70, 0.235, 0.03, 0.015, 0.02)
    states = []
    j1_n = [F0 * y for y in nominal_y]
    j2_req = request_of((661.7, 9.37e6, 2.61, 0.0273, 0.0188, 0.0321, 0.00653))
    j2_n = [1000.0 * x for x in j2_req["n"]]
    j3_req = request_of((703.15, 9.5e6, 2.75, 0.03, 0.02, 0.025, 0.00715))
    defs = [
        (
            "J1",
            j1_n,
            673.15,
            1.0e7,
            1.0,
            "The nominal inlet per tube (M01 spec §8.4). z_T vanishes there to roundoff (the box "
            "is centred "
            "on 673.15 K), so every term carrying z_T is invisible at J1; J2 exists for that "
            "reason.",
        ),
        (
            "J2",
            j2_n,
            661.7,
            9.37e6,
            1000.0,
            "An off-nominal inlet at N_tubes = 1000 with every z_k non-zero and pairwise "
            "distinct, so a "
            "permuted coordinate, a dropped cross term or a missing 1/N_tubes changes the "
            "Jacobian.",
        ),
        (
            "J3",
            j3_req["n"],
            703.15,
            9.5e6,
            1.0,
            "Outside the reference box in T only (z_T = 1.5, every other |z_k| < 1): the "
            "surrogate still "
            "evaluates (the residual is a polynomial), the domain status is "
            "outside_reference_domain with "
            "scaled excess 0.5, and the hard domain admits it (T 703.15 K < 773.15 K).",
        ),
    ]
    for label, n, t, p, nt, why in defs:
        z = z_of_u(u_of_request(n, t, p, nt))
        xi = predict(beta["X"], z) * n[1]
        t_out = t + predict(beta["dT"], z)
        v = list(n) + [t, p, xi, t_out]
        jac = unit_jacobian(beta["X"], beta["dT"], v, nt)
        num = numeric_jacobian(beta["X"], beta["dT"], v, nt)
        err = max(
            abs(jac[r][c] - num[r][c]) / max(abs(num[r][c]), mpf(1))
            for r in range(2)
            for c in range(9)
        )
        claim(
            err < mpf("1e-30"),
            f"{label}: chain-rule Jacobian equals mpmath differentiation (err {mp.nstr(err, 3)})",
        )
        ratio = cancellation_ratio(beta["X"], beta["dT"], v, nt)
        claim(ratio < 1000, f"{label}: no inlet Jacobian entry cancels by more than 1e3")
        res = unit_rows(beta["X"], beta["dT"], v, nt)
        claim(max(abs(x) for x in res) < mpf("1e-40"), f"{label}: rows vanish at the causal outlet")
        dn = [n[i] + NU[i] * xi - n[i] for i in range(5)]
        claim(
            all(
                abs(mp.fsum(e * d for e, d in zip(row, dn, strict=True))) < mpf("1e-45")
                for row in ELEMENTS
            ),
            f"{label}: elements conserved",
        )
        if label == "J1":
            claim(abs(z[0]) < mpf("1e-14"), "J1: z_T vanishes to roundoff")
        if label == "J3":
            claim(
                abs(z[0] - mpf("1.5")) < mpf("1e-12") and all(abs(x) < 1 for x in z[1:]),
                "J3: z_T = 1.5 and every other coordinate inside the box",
            )
            claim(
                in_hard(u_of_request(n, t, p, nt), real=True), "J3: inside the parent's hard domain"
            )
        if label == "J2":
            claim(
                all(abs(x) > mpf("0.05") for x in z) and len({mp.nstr(x, 6) for x in z}) == D,
                "J2: every z_k non-zero and pairwise distinct",
            )
            claim(
                all(abs(jac[r][c]) > mpf("1e-30") for r in range(2) for c in range(7)),
                "J2: all 14 inlet-column entries of the two rows are non-zero",
            )
        states.append(
            {
                "id": label,
                "why": why,
                "n_tubes": nt,
                "inlet": {"n": list(n), "T": t, "P": p},
                "domain": {
                    "status": "within_reference_domain"
                    if max(abs(x) for x in z) <= 1
                    else "outside_reference_domain",
                    "scaled_excess": s(max(mpf(0), max(abs(x) for x in z) - 1), 12),
                },
                "z": [s(x) for x in z],
                "outlet": {
                    "xi": s(xi),
                    "T_out": s(t_out),
                    "X": s(predict(beta["X"], z)),
                    "dT": s(predict(beta["dT"], z)),
                },
                "columns": [f"inlet.n.{c}" for c in COMPONENTS]
                + ["inlet.T", "inlet.P", "xi", "outlet.T"],
                "rows": ["C1RX-extent", "C1RX-temperature"],
                "cancellation_ratio_max": s(ratio, 6),
                "jacobian": [[s(x) for x in row] for row in jac],
            }
        )
    return states


# -- assembly -------------------------------------------------------------------------------------


def build() -> tuple[dict[str, Any], dict[int, Any]]:
    plan = build_plan()
    plan_summary = plan_claims(plan)
    claim(P_TERMS == 36 and len(PAIRS) == 28, "the full quadratic in 7 inputs has 36 terms")
    x_nom = XI_NOM / (mpf("0.235") * mpf(F0))
    claim(
        mpf("0.0144") <= mpf(W["X"]) / x_nom <= mpf("0.0194"),
        "w_X / X_nom lies inside DX-01's xi range 1.44-1.94 %",
    )
    claim(
        mpf("1.24") <= mpf(W["dT"]) <= mpf("1.67"),
        "w_T lies inside DX-01's T_out range 1.24-1.67 K",
    )
    claim(n_min() == 19 and k_index(18) == 19 and k_index(19) == 19, "n_min = 19 at alpha = 1/20")
    claim(
        k_index(118) == 114 and math.ceil(0.95 * 118) == 113,
        "n = 118: corrected k = 114, uncorrected 113",
    )
    claim(m_min() == 29, "m_min = 29: the smallest all-hit test set whose bound clears 0.90")
    pw = power(COUNTS["calibration"], COUNTS["test"])
    claim(pw["h_min"] == 279, "h_min(300) = 279")
    claim(mpf(pw["power_no_failures"]) > mpf("0.90"), "the registered plan's power exceeds 0.90")
    claim(
        mpf(pw["false_pass_at_minimum"]) <= DELTA < mpf(pw["false_pass_one_below_h_min"]),
        "h_min is the exact Clopper-Pearson decision boundary at m = 300",
    )
    claim(
        abs(mpf(pw["false_pass_at_minimum"]) - DELTA) > mpf("1e-6"),
        "the decision boundary is not knife-edge",
    )
    alternatives = [
        power(n, m) for n, m in ((99, 300), (118, 200), (149, 400), (199, 400), (299, 400))
    ]
    cp_table = []
    for h, m in (
        (29, 29),
        (28, 28),
        (28, 29),
        (279, 300),
        (278, 300),
        (288, 300),
        (300, 300),
        (57, 60),
        (60, 60),
    ):
        cp_table.append({"h": h, "m": m, "lower_bound": s(cp_lower(h, m))})
    claim(
        cp_lower(279, 300) >= C_MIN > cp_lower(278, 300), "CP bound brackets 0.90 at h = 279 / 278"
    )
    failure_power = [
        power_with_failures(COUNTS["calibration"], COUNTS["test"], mpf(f))
        for f in ("0.01", "0.02", "0.05")
    ]
    claim(
        abs(
            mpf(power_with_failures(COUNTS["calibration"], COUNTS["test"], mpf("1e-30"))["power"])
            - mpf(pw["power_no_failures"])
        )
        < mpf("1e-5"),
        "the failure-aware power reduces to the beta-binomial power at f = 0",
    )
    nearest = min(abs(mpf(r["lower_bound"]) - C_MIN) for r in cp_table)
    claim(nearest > mpf("7e-4"), "no registered CP bound lies within 7e-4 of 0.90")
    vectors = verdict_vectors()
    smooth = run_case(
        plan, SYNTHETIC["m04-synthetic-smooth-v1"], COUNTS, "m04-synthetic-smooth-v1/full"
    )
    rough = run_case(
        plan, SYNTHETIC["m04-synthetic-rough-v1"], PREFIX, "m04-synthetic-rough-v1/prefix"
    )
    smooth_prefix = run_case(
        plan, SYNTHETIC["m04-synthetic-smooth-v1"], PREFIX, "m04-synthetic-smooth-v1/prefix"
    )
    standin = run_case(plan, None, PREFIX, "standin-x025-v1/prefix")
    synthetic_claims(smooth, rough, standin)
    gaps = smooth_prefix["margins"]
    claim(
        min(mpf(gaps[g]) for g in ("order_statistic_gap", "test_to_q_hat", "q_hat_to_width_limit"))
        > mpf("1e-8"),
        "smooth prefix: every decision gap exceeds 1e-8 (Amendment 1 A1.3)",
    )
    fmargin = failure_margin(plan)
    claim(
        fmargin > mpf("1e-6"),
        "no registered request lies within 1e-6 of the synthetic failure boundary",
    )
    smooth_prefix["band"] = {
        o: s(mpf(smooth_prefix["result"]["q_hat"]) * mpf(W[o]), 12) for o in ("X", "dT")
    }
    standin = {
        key: standin[key]
        for key in ("case", "parent", "counts", "failed_indices", "training_ok", "coefficients")
    } | {"q_hat": standin["result"]["q_hat"]}
    # The fixture surrogate of the Jacobian states: the smooth case's coefficients rounded once to
    # binary64, so the implementation's fixture and the expectation use the same numbers.
    fixture = {o: [float(mpf(x)) for x in smooth["coefficients"][o]] for o in ("X", "dT")}
    jac = jacobian_states({o: [mpf(x) for x in fixture[o]] for o in ("X", "dT")})
    zstar = [
        mpf("0.11"),
        mpf("-0.23"),
        mpf("0.37"),
        mpf("-0.41"),
        mpf("0.53"),
        mpf("-0.67"),
        mpf("0.79"),
    ]
    values = {
        "schema_version": "m04-reference-v1",
        "generated_by": GENERATOR,
        "specification": SPEC,
        "kind": (
            "design-lane closed-form and seeded expectations; "
            "numerical verification, not validation"
        ),
        "constants": {
            "box": [
                {
                    "coordinate": b[0],
                    "unit": b[1],
                    "lo": LO[i],
                    "hi": HI[i],
                    "centre": CENTRE[i],
                    "half_width": HALF[i],
                }
                for i, b in enumerate(BOX)
            ],
            "nominal_tube_flow_mol_s": F0,
            "X_nominal_from_M01": s(XI_NOM / (mpf("0.235") * mpf(F0)), 12),
            "alpha": "1/20",
            "delta": "1/20",
            "c_min": "9/10",
            "width_limits": W,
            "rho_g": RHO_G,
            "tau_id": TAU_ID,
            "gradient_step_z": GRAD_STEP,
            "gradient_inner_box": GRAD_INNER,
            "admissible": ADMISSIBLE,
            "seeds": {sp: seed_of(1, sp) for sp in SPLITS},
            "counts": COUNTS,
            "prefix_counts": PREFIX,
            "terms": P_TERMS,
            "basis_order": ["1"]
            + [f"z{k + 1}" for k in range(D)]
            + [f"z{i + 1}*z{j + 1}" for i, j in PAIRS],
            "synthetic": {
                "a": [s(x) for x in SYN_A],
                "b": [s(x) for x in SYN_B],
                "X0": s(SYN_X0),
                "dT0": s(SYN_DT0),
                "fail_if_zT_plus_zF_above": s(SYN_FAIL),
                "amplitudes": {k: s(v) for k, v in SYNTHETIC.items()},
            },
        },
        "splitmix64_first_words": {
            sp: [str(w) for w in splitmix64(seed_of(1, sp), 3)] for sp in SPLITS
        },
        "plan_summary": plan_summary,
        "finite_sample": {
            "k": {str(n): k_index(n) for n in (18, 19, 39, 99, 118, 119, 149, 199)},
            "h_min": {str(m): h_min(m) for m in (29, 60, 300)},
            "registered_plan_with_failures": failure_power,
            "n_min": n_min(),
            "m_min": m_min(),
            "registered_plan": pw,
            "alternatives": alternatives,
            "clopper_pearson": cp_table,
        },
        "verdict_vectors": vectors,
        "basis_at_zstar": {"z": [s(x) for x in zstar], "phi": [s(x) for x in basis(zstar)]},
        "fixture_coefficients": fixture,
        "jacobian_states": jac,
        "a11_fixture": a11_fixture(),
        "synthetic_failure_margin": s(fmargin, 6),
        "pipeline": {
            "smooth_full": smooth,
            "smooth_prefix": smooth_prefix,
            "rough_prefix": rough,
            "standin_prefix": standin,
        },
        "claims": {
            "count": len(CLAIMS),
            "distinct_statements": sorted({re.sub(r"\[\d+\]", "[i]", c) for c in CLAIMS}),
        },
    }
    plans: dict[int, Any] = {1: plan}
    for i in ITERATIONS:
        plans[i] = build_plan_iteration(i)
    later = [iteration_claims(plans, i) for i in ITERATIONS]
    values["later_iterations"] = later
    values["claims"] = {
        "count": len(CLAIMS),
        "distinct_statements": sorted({re.sub(r"\[\d+\]", "[i]", c) for c in CLAIMS}),
    }
    docs = {}
    for i, body in plans.items():
        counts = dict(COUNTS) if i == 1 else {**COUNTS, "training": len(body["training"])}
        docs[i] = {
            "schema_version": "m04-plan-v1",
            "generated_by": GENERATOR,
            "iteration": i,
            "n_tubes": N_TUBES_PLAN,
            "components": list(COMPONENTS),
            "seeds": {sp: seed_of(i, sp) for sp in SPLITS},
            "counts": counts,
            **body,
        }
    return values, docs


def encode(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="re-derive every claim and compare with the committed files",
    )
    parser.add_argument("--emit", action="store_true", help="write every file")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit")
    values, plans = build()
    payloads = {OUT_VALUES: encode(values)}
    for i, doc in plans.items():
        payloads[OUT_PLAN.with_name(f"plan-it{i}.json")] = encode(doc)
    status = 0
    if args.check:
        print(f"{len(CLAIMS)} claims passed")
        for path, payload in payloads.items():
            committed = path.read_bytes() if path.exists() else b""
            if committed != payload:
                print(f"{path} differs from the generator's output", file=sys.stderr)
                status = 1
            else:
                print(f"{path} is byte-identical to the generator's output")
    if args.emit and status == 0:
        for path, payload in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            print("wrote", path)
    return status


if __name__ == "__main__":
    sys.exit(main())
