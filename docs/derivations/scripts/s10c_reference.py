"""S10-C reference generator: composition-dependent K in the PH kernel and the column (WO-S).

Normative text: ``docs/derivations/S10C-spec.md`` (the registered states, tolerances and numbered
assertions) and ``docs/derivations/S10C-design.md`` (the algorithms). Inputs:
``benchmarks/s10/records.yaml`` (methanol, ethanol, water; ``WILSON-IG-ref-v1``) and
``benchmarks/s10/verification-records.yaml`` (three SYNTHETIC components; ``S10-VER-ref-v1``).
Output: ``benchmarks/s10c/reference_values.yaml``.

It imports nothing from ``openflowsheet`` or ``benchmarks``. The closed forms of ``wilson-ig-v1``
(S10 spec section 3) are read from the S10 generator (``s10_reference.py``, itself independent of
``src/``), as S08's generator reads S02's. Four classes of value, labelled as such in the YAML (the
convention of ``s10_reference.py``):

* ``closed_form`` -- expectations, mpmath at 50 significant digits, written to 20. Every
  expectation is solved here by Newton's method on the defining equations (the constant-beta point
  as a square system in ``(T, x)``; the PH answers with ``beta`` or ``T`` as an extra unknown; the
  column as a MESH system in quotient form), never by the successive substitution, bisection or
  sweeps the implementation is told to use.
* ``tolerances`` -- every tolerance the specification states, with the floor it sits above.
* ``measured`` -- the design's algorithms transcribed in 53-bit arithmetic in this file (never the
  implementation), used only to measure floors and iteration counts. Never an expectation.
* ``generator_claims`` -- every statement the specification makes about its own numbers,
  re-derived on every run. The script refuses to emit when one fails.

Run from the repository root::

    python docs/derivations/scripts/s10c_reference.py --check
    python docs/derivations/scripts/s10c_reference.py --emit

``--emit`` writes the YAML byte-reproducibly; ``--check`` regenerates it in memory and fails unless
it equals the committed file. Dependencies: Python 3.11+, mpmath, PyYAML, NumPy, SciPy (SciPy only
for the binary64 starting point of the column roots, which the 50-digit Newton then refines; the
registered digits do not depend on it).

**What this does not establish.** That the implementation takes the registered routes or converges
from its own openings (the tests judge that); anything about a real mixture beyond the model
(numerical verification, not validation); uniqueness of the column roots beyond local regularity
(``sigma_min``); convergence of the constant-beta point outside the measured scan.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from mpmath import mp, mpc, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s10_reference as s10  # noqa: E402  (wilson-ig-v1's closed forms; records loader)

mp.dps = 50

ROOT = Path(__file__).resolve().parents[3]
REAL_YAML = ROOT / "benchmarks" / "s10" / "records.yaml"
VER_YAML = ROOT / "benchmarks" / "s10" / "verification-records.yaml"
OUT_YAML = ROOT / "benchmarks" / "s10c" / "reference_values.yaml"

P_ATM = 101325.0
EPS64 = 2.0**-52
ZERO = mpf(0)

# -- the design's registered constants (S10C-design §4.3, §4.4, §4.5; T05b §5.2) ----------------
DELTA_BETA = 1e-13  # constant-beta point stop: max_i |ln K_i(T^m, x^m) - ln K^m_i| <= DELTA_BETA
BETA_SS_MAX = 1000  # its iteration cap
INCIPIENT_STOP, INCIPIENT_MAX = 1e-13, 1000  # the fixed-T incipient liquid (S10 step 3's values)
MAX_BAND_EVALUATIONS = 64  # the band route's beta bisection budget, ends included
BETA_WIDTH_FLOOR = 2.0**-60  # its width floor
EQUILIBRIUM_TOLERANCE = 1e-9 * 3.0 + 1e-8 * 9.0  # (mol/s)^2, K04 §5.1
FLOW_TOLERANCE = 1e-9 + 1e-8 * 3.0  # mol/s
ENERGY_TOLERANCE = 1e-5 + 1e-8 * 1e5  # W
TEMPERATURE_TOLERANCE = 1e-6  # K
EPS_TPD = 1e-10  # S10's stability resolution
TAU_ITEM6 = 1e-4  # K: S08 §5.5 item 6, |T_j - T_bub(l_j)| and |T_j - T_dew(v_j)|

# -- the specification's tolerances (S10C-spec §5) ------------------------------------------------
TOL_BP_T = 1e-9  # K, band-point temperature (G3)
TOL_BP_X = 1e-10  # band-point liquid composition (G3)
TOL_BP_K = 1e-9  # band-point K, relative (G3)
TOL_BP_ITER = 100  # band-point iterations at the registered states (G3)
TOL_TM_DEW = 1e-12  # |tm| of the provider's liquid trial at the band point beta = 1 (G3)
TOL_BP_RES = 1e-12  # the returned band point's fixed-point rows (G3, A06)
TOL_PH_T = 1e-9  # K (G4)
TOL_PH_BETA = 1e-10  # vapour fraction (G4)
TOL_PH_FLOW_REL = 1e-10  # flows, relative to n_tot (G4)
TOL_E2_T = 1e-10  # K (G5)
TOL_E2_BETA = 1e-9  # (G5)
TOL_E2_XY = 1e-9  # (G5)
TOL_FD = 1e-6  # central / one-sided differences on the blocks, relative to max(|J|, s) (G6)
TOL_VALUE = 1e-12  # block values and Jacobians against the closed forms (S10 §7.2's rule)
MARGIN = 10.0  # every tolerance sits at least this factor above its measured floor

CLAIMS: list[dict[str, Any]] = []
_CLAIM_INDEX: dict[str, dict[str, Any]] = {}


def claim(cid: str, ok: bool, text: str) -> None:
    """Refuse to continue unless `ok`. A claim re-derived at several states is listed once, with
    the number of states (`instances`) and the first statement."""
    if not ok:
        raise SystemExit(f"generator claim {cid} FAILED: {text}")
    if cid in _CLAIM_INDEX:
        _CLAIM_INDEX[cid]["instances"] += 1
        return
    entry = {"id": cid, "holds": True, "instances": 1, "statement": text}
    _CLAIM_INDEX[cid] = entry
    CLAIMS.append(entry)


def nstr(x: Any, digits: int = 20) -> float:
    """A 50-digit value written to `digits` significant digits (YAML reads it as a float)."""
    x = mpf(x)
    return float(mp.nstr(x, digits, min_fixed=-30, max_fixed=30)) if x != 0 else 0.0


def g3(x: float) -> float:
    """A measured or derived number written to 3 significant digits."""
    return float(f"{float(x):.3g}") if x != 0 else 0.0


def exact_double(x: Any) -> float:
    """The binary64 nearest a 50-digit value: a registered input, written with `repr`."""
    return float(mpf(x))


# ================================================================================================
# 1. Records: the two committed sets and two test-built variants
# ================================================================================================


def ideal_records(rec: s10.Records) -> s10.Records:
    """The verification records with every Lambda_ij = 1 (the ideal limit, Raoult's law)."""
    n = len(rec.ids)
    return dataclasses.replace(rec, lam=tuple(tuple(1.0 for _ in range(n)) for _ in range(n)))


NARROW_T = (342.0, 365.0)  # K: the narrowed temperature domain of the positions record set


def narrowed_records(rec: s10.Records) -> s10.Records:
    """The verification records with the temperature domain narrowed to NARROW_T (positions)."""
    return dataclasses.replace(rec, t_lo=NARROW_T[0], t_hi=NARROW_T[1])


class Thermo:
    """One record set at 50 digits (`m`, the S10 generator's closed forms) and in binary64 (`f`,
    the S10 generator's transcription), with the mixture quantities this package needs."""

    def __init__(self, name: str, rec: s10.Records) -> None:
        self.name = name
        self.rec = rec
        self.m = s10.Model(rec)
        self.f = s10.Float64Model(rec)
        self.n = len(rec.ids)
        self.t_lo, self.t_hi = rec.t_lo, rec.t_hi

    # 50 digits; x need not be normalised (it is normalised here, as the provider does)
    def lnk(self, t: Any, p: Any, x: Sequence[Any]) -> list[Any]:
        tot = sum(x)
        return self.m.lnk(t, mpf(p) if not isinstance(p, mpc) else p, [v / tot for v in x])

    def hl(self, n: Sequence[Any], t: Any) -> Any:
        return sum(n[i] * self.m.h0l(i, t) for i in range(self.n) if n[i] != 0)

    def hv(self, n: Sequence[Any], t: Any) -> Any:
        return sum(n[i] * self.m.h_ig(i, t) for i in range(self.n) if n[i] != 0)

    # binary64
    def lnk64(self, t: float, p: float, x: Sequence[float]) -> list[float]:
        tot = sum(x)
        return self.f.lnk(t, p, [v / tot for v in x])

    def hl64(self, n: Sequence[float], t: float) -> float:
        tot = sum(n)
        return tot * sum((n[i] / tot) * self.f.h0l(i, t) for i in range(self.n))

    def hv64(self, n: Sequence[float], t: float) -> float:
        tot = sum(n)
        return tot * sum((n[i] / tot) * self.f.h_ig(i, t) for i in range(self.n))


# ================================================================================================
# 2. Positivity on each record set's whole T domain (S10C-spec §2.3; the theorems' premises)
# ================================================================================================


def interval_min(poly_hi_first: Sequence[mpf], f: Callable[[mpf], mpf], lo: mpf, hi: mpf) -> mpf:
    """min of f on [lo, hi] (theta units), where poly is f's derivative times a positive factor:
    the minimum is at an end or at a real root of poly inside the interval."""
    cands = [lo, hi]
    coeffs = list(poly_hi_first)
    while coeffs and coeffs[0] == 0:
        coeffs = coeffs[1:]
    if len(coeffs) > 1:
        for r in mp.polyroots(coeffs, maxsteps=200, extraprec=100):
            if abs(mp.im(r)) < mpf("1e-30") and lo < mp.re(r) < hi:
                cands.append(mp.re(r))
    return min(f(c) for c in cands)


def positivity(th: Thermo) -> dict[str, Any]:
    """Exact minima over the domain of Delta h_i, c_p,i^0L, c_p,i^ig and d ln P_i^sat/dT."""
    m, rec = th.m, th.rec
    lo, hi = mpf(rec.t_lo) / 1000, mpf(rec.t_hi) / 1000
    gas_r = s10.R
    out: dict[str, Any] = {}
    for i, cid in enumerate(rec.ids):
        a, b, c, d = m.ps[i]
        bb = m.b[i]

        def dh(th_: mpf, b=b, c=c, d=d) -> mpf:  # R*1000*(-b + c th + 2 d th^3)
            return gas_r * 1000 * (-b + c * th_ + 2 * d * th_**3)

        def dlnp(th_: mpf, b=b, c=c, d=d) -> mpf:
            return (-b / th_**2 + c / th_ + 2 * d * th_) / 1000

        def cpig(th_: mpf, bb=bb) -> mpf:
            return gas_r * sum(bb[k] * th_**k for k in range(5))

        def cpl(th_: mpf, bb=bb, c=c, d=d) -> mpf:
            return gas_r * sum(bb[k] * th_**k for k in range(5)) - gas_r * (c + 6 * d * th_**2)

        mins = {
            # d(dh)/dth = R*1000*(c + 6 d th^2)
            "dh_vap": interval_min([6 * d, 0, c], dh, lo, hi),
            # d(dlnp)/dth * th^3 = 2b - c th + 2 d th^3
            "dlnpsat_dT": interval_min([2 * d, 0, -c, 2 * b], dlnp, lo, hi),
            # d(cpig)/dth = R (b1 + 2 b2 th + 3 b3 th^2 + 4 b4 th^3)
            "cp_ig": interval_min([4 * bb[4], 3 * bb[3], 2 * bb[2], bb[1]], cpig, lo, hi),
            "cp_liquid": interval_min(
                [4 * bb[4], 3 * bb[3], 2 * bb[2] - 12 * d, bb[1]], cpl, lo, hi
            ),
        }
        # Cross-check each exact minimum against a 2001-point grid (it may not exceed the grid's).
        grid = [lo + (hi - lo) * k / 2000 for k in range(2001)]
        for key, fn in (("dh_vap", dh), ("dlnpsat_dT", dlnp), ("cp_ig", cpig), ("cp_liquid", cpl)):
            gmin = min(fn(t) for t in grid)
            claim(
                f"POS-GRID-{rec.convention}-{cid}-{key}",
                mins[key] <= gmin + mpf("1e-30"),
                f"{rec.convention} {cid}: the exact minimum of {key} on the T domain does not "
                f"exceed "
                f"its 2001-point grid minimum",
            )
            claim(
                f"POS-{rec.convention}-{cid}-{key}",
                mins[key] > 0,
                f"{rec.convention} {cid}: {key} > 0 on the whole T domain "
                f"[{rec.t_lo}, {rec.t_hi}] K "
                f"(minimum {mp.nstr(mins[key], 6)}); a premise of T1-T3 (S10C-spec §2)",
            )
        out[cid] = {k: g3(float(v)) for k, v in mins.items()}
    return out


# ================================================================================================
# 3. The constant-beta point (S10C-design §4.3)
# ================================================================================================


def newton(
    fun: Callable[[list[Any]], list[Any]], v0: Sequence[Any], tol: Any = None, it: int = 60
) -> list[Any]:
    """Newton with a complex-step Jacobian (exact to h^2 = 1e-120) and a backtracking line search;
    `fun` must be analytic in its arguments (no abs, no max)."""
    tol = mpf("1e-44") if tol is None else tol
    v = [mpf(e) for e in v0]
    size = len(v)
    h = mpf("1e-60")
    for _ in range(it):
        f = fun(v)
        norm = max(abs(e) for e in f)
        if norm < tol:
            return v
        jac = mp.matrix(size, size)
        for j in range(size):
            vp = [mpc(e) for e in v]
            vp[j] += mpc(0, h)
            col = fun(vp)
            for i in range(size):
                jac[i, j] = mp.im(col[i]) / h
        step = mp.lu_solve(jac, mp.matrix([-e for e in f]))
        alpha = mpf(1)
        while True:
            trial = [v[k] + alpha * step[k] for k in range(size)]
            try:
                ft = fun(trial)
                if max(abs(e) for e in ft) < (1 - alpha / 4) * norm:
                    v = trial
                    break
            except (ValueError, ZeroDivisionError):
                pass
            alpha /= 2
            if alpha < mpf("1e-12"):
                raise SystemExit("generator Newton failed: line search")
    raise SystemExit(f"generator Newton failed: budget, residual {norm}")


def real_part(z: Any) -> Any:
    return mp.re(z) if isinstance(z, mpc) else z


@dataclasses.dataclass
class BandPoint:
    """A constant-beta point at 50 digits: T, the liquid x, K = K(T, P, x) for every component."""

    t: Any
    x: list[Any]
    k: list[Any]
    position: str  # inside | below | above (T against the record set's domain)


def band_point_mp(th: Thermo, n: Sequence[float], p: float, beta: Any, start: Any) -> BandPoint:
    """The constant-beta point as a square system in (T, x_F): x_i D_i - z_i = 0 (i in F) and
    g = sum z_i (K_i - 1)/D_i = 0, with K at the normalised x, solved by Newton from `start`
    = (T, x_F). Evaluated off the domain where T lies outside it (the closed forms extend), so the
    position is read from T."""
    nn = [mpf(v) for v in n]
    tot = sum(nn)
    z = [v / tot for v in nn]
    act = [i for i in range(th.n) if z[i] > 0]
    beta = mpf(beta)

    def full(xs: Sequence[Any]) -> list[Any]:
        out: list[Any] = [mpf(0)] * th.n
        for i, v in zip(act, xs, strict=True):
            out[i] = v
        return out

    def fun(v: list[Any]) -> list[Any]:
        t, xs = v[0], v[1:]
        lk = th.lnk(t, p, full(xs))
        k = [mp.exp(e) for e in lk]
        d = {i: 1 + beta * (k[i] - 1) for i in act}
        rows = [xs[a] * d[i] - z[i] for a, i in enumerate(act)]
        rows.append(sum(z[i] * (k[i] - 1) / d[i] for i in act))
        return rows

    sol = newton(fun, start)
    t = sol[0]
    x = full(sol[1:])
    k = [mp.exp(e) for e in th.lnk(t, p, x)]
    pos = "below" if t < th.t_lo else ("above" if t > th.t_hi else "inside")
    return BandPoint(t, x, k, pos)


# -- the binary64 transcription of §4.3 (measured floors and iteration counts; never expectations)


@dataclasses.dataclass
class BandPoint64:
    t: float
    x: list[float]
    lnk: list[float]  # ln K^m: the K that produced x^m
    position: str
    iterations: int
    steps: list[float]


def tsolve64(
    th: Thermo, z: Sequence[float], act: Sequence[int], p: float, beta: float, x: Sequence[float]
) -> tuple[float, str, list[float]]:
    """The frozen-x temperature solve of §4.3: positions from the domain ends' signs, then a
    Newton step safeguarded by the bracket, to g == 0 or adjacent doubles (the end with the
    smaller |g|, the lower on a tie)."""

    def ev(t: float) -> tuple[float, float, list[float]]:
        lk = th.lnk64(t, p, x)
        g = dg = 0.0
        for i in act:
            k = math.exp(lk[i])
            d = 1.0 + beta * (k - 1.0)
            g += z[i] * (k - 1.0) / d
            dg += z[i] * k * th.f.dlnpsat(i, t) / (d * d)
        return g, dg, lk

    lo, hi = th.t_lo, th.t_hi
    g_lo, _, lk_lo = ev(lo)
    if g_lo > 0.0:
        return lo, "below", lk_lo
    if g_lo == 0.0:
        return lo, "inside", lk_lo
    g_hi, _, lk_hi = ev(hi)
    if g_hi < 0.0:
        return hi, "above", lk_hi
    if g_hi == 0.0:
        return hi, "inside", lk_hi
    t = 0.5 * (lo + hi)
    widths = [hi - lo]
    for _ in range(400):
        g, dg, lk = ev(t)
        if g == 0.0:
            return t, "inside", lk
        if g < 0.0:
            lo, g_lo, lk_lo = t, g, lk
        else:
            hi, g_hi, lk_hi = t, g, lk
        widths.append(hi - lo)
        if math.nextafter(lo, math.inf) >= hi:
            if abs(g_hi) < abs(g_lo):
                return hi, "inside", lk_hi
            return lo, "inside", lk_lo
        nt = t - g / dg if dg > 0.0 else 0.5 * (lo + hi)
        halved = len(widths) < 3 or widths[-1] <= 0.5 * widths[-3]
        if not (lo < nt < hi) or not halved:
            nt = 0.5 * (lo + hi)
        if nt == t:
            nt = math.nextafter(t, math.inf if g < 0.0 else -math.inf)
            if not (lo < nt < hi):
                nt = 0.5 * (lo + hi)
        t = nt
    raise SystemExit("tsolve64: no stop")


def band_point64(
    th: Thermo,
    n: Sequence[float],
    p: float,
    beta: float,
    delta: float = DELTA_BETA,
    cap: int = BETA_SS_MAX,
) -> BandPoint64:
    """§4.3's algorithm in binary64 (`delta` and `cap` differ from the registered constants only in
    the mutation measurements MB1 and MB2)."""
    tot = sum(n)
    z = [v / tot for v in n]
    act = [i for i in range(th.n) if z[i] > 0.0]
    x = list(z)
    if beta == 0.0:
        t, pos, lk = tsolve64(th, z, act, p, beta, x)
        return BandPoint64(t, x, lk, pos, 1, [0.0])
    steps: list[float] = []
    for m in range(1, cap + 1):
        t, pos, lkm = tsolve64(th, z, act, p, beta, x)
        raw = [
            z[i] / (1.0 + beta * (math.exp(lkm[i]) - 1.0)) if i in act else 0.0 for i in range(th.n)
        ]
        tot_raw = sum(raw)
        x_new = [v / tot_raw for v in raw]
        lk_new = th.lnk64(t, p, x_new)
        s = max(abs(lk_new[i] - lkm[i]) for i in act)
        steps.append(s)
        x = x_new
        if s <= delta or m == cap < BETA_SS_MAX:
            return BandPoint64(t, x, lkm, pos, m, steps)
    raise SystemExit(f"band_point64: no stop in {BETA_SS_MAX} iterations at n={n}, beta={beta}")


def contraction(steps: Sequence[float]) -> float:
    """The largest of the last three step ratios with the earlier step above 1e-11 (the
    design's M-a measure)."""
    ratios = [steps[i + 1] / steps[i] for i in range(len(steps) - 1) if steps[i] > 1e-11]
    return max(ratios[-3:]) if ratios else 0.0


def band_point(
    th: Thermo, n: Sequence[float], p: float, beta: float
) -> tuple[BandPoint, BandPoint64]:
    """The 50-digit point started from the binary64 transcription's answer (unclamped: where the
    transcription clamped to a domain end, the 50-digit solve starts there and leaves the
    domain)."""
    b64 = band_point64(th, n, p, beta)
    act = [i for i in range(th.n) if n[i] > 0.0]
    bp = band_point_mp(th, n, p, beta, [mpf(b64.t)] + [mpf(b64.x[i]) for i in act])
    return bp, b64


# ================================================================================================
# 4. Two-phase splits and PH answers at 50 digits
# ================================================================================================


@dataclasses.dataclass
class Split:
    """A two-phase split at 50 digits: T, beta, liquid x, vapour y, liquid flows lq, vapour flows v,
    Hdot."""

    t: Any
    beta: Any
    x: list[Any]
    y: list[Any]
    lq: list[Any]
    v: list[Any]
    h: Any


def split_from(
    th: Thermo, n: Sequence[float], p: float, t: Any, beta: Any, x: Sequence[Any]
) -> Split:
    """The band split of design §4.3 (`band_split`): v_i = n_i beta K_i/D_i, l_i = n_i (1-beta)/D_i,
    with K = K(T, P, x); y_i = K_i x_i."""
    k = [mp.exp(e) for e in th.lnk(t, p, x)]
    nn = [mpf(v) for v in n]
    d = [1 + beta * (k[i] - 1) for i in range(th.n)]
    v = [nn[i] * beta * k[i] / d[i] if nn[i] > 0 else mpf(0) for i in range(th.n)]
    lq = [nn[i] * (1 - beta) / d[i] if nn[i] > 0 else mpf(0) for i in range(th.n)]
    y = [k[i] * x[i] for i in range(th.n)]
    return Split(t, mpf(beta), list(x), y, lq, v, th.hl(lq, t) + th.hv(v, t))


def tp_split_mp(th: Thermo, n: Sequence[float], p: float, t: Any, start: Sequence[Any]) -> Split:
    """The two-phase split at fixed (T, P, n): unknowns (beta, x_F); rows x_i D_i - z_i and g.
    Solved at 70 digits (near an azeotrope the system's condition is ~1e8, S10 §14 E-2)."""
    nn = [mpf(v) for v in n]
    tot = sum(nn)
    z = [v / tot for v in nn]
    act = [i for i in range(th.n) if z[i] > 0]

    def full(xs: Sequence[Any]) -> list[Any]:
        out: list[Any] = [mpf(0)] * th.n
        for i, v in zip(act, xs, strict=True):
            out[i] = v
        return out

    with mp.workdps(70):
        tt = mpf(t)

        def fun(v: list[Any]) -> list[Any]:
            beta, xs = v[0], v[1:]
            k = [mp.exp(e) for e in th.lnk(tt, p, full(xs))]
            d = {i: 1 + beta * (k[i] - 1) for i in act}
            rows = [xs[a] * d[i] - z[i] for a, i in enumerate(act)]
            rows.append(sum(z[i] * (k[i] - 1) / d[i] for i in act))
            return rows

        sol = newton(fun, start, tol=mpf("1e-62"))
    return split_from(th, n, p, mpf(t), sol[0], full(sol[1:]))


def ph_band_mp(
    th: Thermo, n: Sequence[float], p: float, target: Any, start: Sequence[Any]
) -> Split:
    """The two-phase PH answer: unknowns (beta, T, x_F); the constant-beta rows plus
    (Hdot - H*)/1e4 = 0. Solved at 70 digits."""
    nn = [mpf(v) for v in n]
    tot = sum(nn)
    z = [v / tot for v in nn]
    act = [i for i in range(th.n) if z[i] > 0]

    def full(xs: Sequence[Any]) -> list[Any]:
        out: list[Any] = [mpf(0)] * th.n
        for i, v in zip(act, xs, strict=True):
            out[i] = v
        return out

    with mp.workdps(70):
        hstar = mpf(target)

        def fun(v: list[Any]) -> list[Any]:
            beta, t, xs = v[0], v[1], v[2:]
            x = full(xs)
            k = [mp.exp(e) for e in th.lnk(t, p, x)]
            d = {i: 1 + beta * (k[i] - 1) for i in act}
            rows = [xs[a] * d[i] - z[i] for a, i in enumerate(act)]
            rows.append(sum(z[i] * (k[i] - 1) / d[i] for i in act))
            lv = [nn[i] * (1 - beta) / d[i] if i in act else mpf(0) for i in range(th.n)]
            vv = [nn[i] * beta * k[i] / d[i] if i in act else mpf(0) for i in range(th.n)]
            rows.append((th.hl(lv, t) + th.hv(vv, t) - hstar) / 10000)
            return rows

        sol = newton(fun, start, tol=mpf("1e-62"))
    return split_from(th, n, p, sol[1], sol[0], full(sol[2:]))


def ph_single_mp(th: Thermo, n: Sequence[float], target: Any, phase: str, t0: Any) -> Any:
    """T* of a single-phase PH answer: Hdot^phase(n, T) = H*."""
    nn = [mpf(v) for v in n]
    hfun = th.hl if phase == "LIQUID" else th.hv
    with mp.workdps(70):
        hstar = mpf(target)
        sol = newton(lambda v: [(hfun(nn, v[0]) - hstar) / 10000], [mpf(t0)], tol=mpf("1e-62"))
    return sol[0]


def t_sat_mp(th: Thermo, i: int, p: float, t0: float) -> Any:
    return newton(lambda v: [th.m.lnpsat(i, v[0]) - mp.log(mpf(p))], [mpf(t0)])[0]


def beta_at_t64(th: Thermo, n: Sequence[float], p: float, t: float) -> tuple[float, BandPoint64]:
    """The vapour fraction whose binary64 constant-beta point has temperature t, by 40 halvings
    of [0, 1] (T(beta) increases for a binary, T5): a starting point for `tp_split_mp`, whose
    fixed-T system has spurious roots outside (0, 1) near an azeotrope."""
    lo, hi = 0.0, 1.0
    best = band_point64(th, n, p, 0.5)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        best = band_point64(th, n, p, mid)
        if best.t < t:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), best


# -- the binary64 transcription of design §4.5 (measured floors only; never expectations) ----------


def bracketed_root64(
    f: Callable[[float], tuple[float, Any]],
    lower: tuple[float, float, Any],
    upper: tuple[float, float, Any],
    evaluations: int,
    budget: int,
    min_width: float = 0.0,
) -> tuple[float, float, Any, int]:
    """`models/syn001/bisection.bracketed_root`'s rule: bisect to f == 0, adjacent doubles or
    `min_width`; return the end with the smaller |f| (the lower on a tie)."""
    lo, f_lo, p_lo = lower
    hi, f_hi, p_hi = upper
    if f_lo == 0.0:
        return lo, f_lo, p_lo, evaluations
    if f_hi == 0.0:
        return hi, f_hi, p_hi, evaluations
    while True:
        mid = 0.5 * (lo + hi)
        if not lo < mid < hi or hi - lo <= min_width:
            break
        if evaluations >= budget:
            raise SystemExit("bracketed_root64: budget")
        f_mid, p_mid = f(mid)
        evaluations += 1
        if f_mid == 0.0:
            return mid, f_mid, p_mid, evaluations
        if f_mid < 0.0:
            lo, f_lo, p_lo = mid, f_mid, p_mid
        else:
            hi, f_hi, p_hi = mid, f_mid, p_mid
    if abs(f_hi) < abs(f_lo):
        return hi, f_hi, p_hi, evaluations
    return lo, f_lo, p_lo, evaluations


@dataclasses.dataclass
class PH64:
    route: str
    t: float
    beta: float
    lq: list[float]
    v: list[float]
    evaluations: int


def ph64(
    th: Thermo,
    n: Sequence[float],
    p: float,
    target: float,
    end_h: tuple[float, float] | None = None,
    width_floor: float = BETA_WIDTH_FLOOR,
) -> PH64 | str:
    """Design §4.5 in binary64. `end_h` supplies (H_lo, H_hi) where a domain end lies inside the
    band (the provider's TP flash there, which this file does not transcribe). Returns the answer,
    or the refusal code."""
    act = [i for i in range(th.n) if n[i] > 0.0]
    t_min, t_max = th.t_lo, th.t_hi
    zero = [0.0] * th.n

    def liquid_route(lo: float, hi: float) -> PH64 | str:
        def f(t: float) -> tuple[float, None]:
            return th.hl64(n, t) - target, None

        f_lo, f_hi = f(lo)[0], f(hi)[0]
        if f_lo > 0.0:
            return "ph_outside_domain(below)"
        if f_hi < 0.0:
            return "ph_outside_domain(above)"
        t, _, _, ev = bracketed_root64(f, (lo, f_lo, None), (hi, f_hi, None), 2, 200)
        return PH64("bracket", t, 0.0, list(n), zero, ev)

    def vapour_route(lo: float, hi: float) -> PH64 | str:
        def f(t: float) -> tuple[float, None]:
            return th.hv64(n, t) - target, None

        f_lo, f_hi = f(lo)[0], f(hi)[0]
        if f_lo > 0.0:
            return "ph_outside_domain(below)"
        if f_hi < 0.0:
            return "ph_outside_domain(above)"
        t, _, _, ev = bracketed_root64(f, (lo, f_lo, None), (hi, f_hi, None), 2, 200)
        return PH64("bracket", t, 1.0, zero, list(n), ev)

    if len(act) == 1:
        c = act[0]

        def g(t: float) -> tuple[float, None]:
            return th.lnk64(t, p, n)[c], None

        g_lo, g_hi = g(t_min)[0], g(t_max)[0]
        if g_hi < 0.0:
            return liquid_route(t_min, t_max)
        if g_lo > 0.0:
            return vapour_route(t_min, t_max)
        tsat, _, _, _ = bracketed_root64(g, (t_min, g_lo, None), (t_max, g_hi, None), 2, 200)
        h_l, h_v = th.hl64(n, tsat), th.hv64(n, tsat)
        if target < h_l:
            return liquid_route(t_min, tsat)
        if target > h_v:
            return vapour_route(tsat, t_max)
        beta = (target - h_l) / (h_v - h_l)
        vf = beta * n[c]
        v = [vf if i == c else 0.0 for i in range(th.n)]
        lq = [n[c] - vf if i == c else 0.0 for i in range(th.n)]
        return PH64("saturation", tsat, beta, lq, v, 0)

    b0 = band_point64(th, n, p, 0.0)
    b1 = band_point64(th, n, p, 1.0)
    if end_h is not None:
        h_lo, h_hi = end_h
    else:
        if b0.position in ("inside", "above"):
            h_lo = th.hl64(n, t_min)
        elif b1.position == "below":
            h_lo = th.hv64(n, t_min)
        else:
            raise SystemExit("ph64: T_min inside the band needs end_h")
        if b1.position in ("inside", "below"):
            h_hi = th.hv64(n, t_max)
        elif b0.position == "above":
            h_hi = th.hl64(n, t_max)
        else:
            raise SystemExit("ph64: T_max inside the band needs end_h")
    if target < h_lo:
        return "ph_outside_domain(below)"
    if target > h_hi:
        return "ph_outside_domain(above)"
    h_b = (
        th.hl64(n, b0.t)
        if b0.position == "inside"
        else (h_hi if b0.position == "above" else -math.inf)
    )
    h_d = (
        th.hv64(n, b1.t)
        if b1.position == "inside"
        else (h_lo if b1.position == "below" else math.inf)
    )
    if target <= h_b:
        return liquid_route(t_min, b0.t if b0.position == "inside" else t_max)
    if target >= h_d:
        return vapour_route(b1.t if b1.position == "inside" else t_min, t_max)

    def big_f(beta: float) -> tuple[float, Any]:
        bp = band_point64(th, n, p, beta)
        if bp.position != "inside":
            return (-math.inf if bp.position == "below" else math.inf), None
        k = [math.exp(e) for e in bp.lnk]
        d = [1.0 + beta * (k[i] - 1.0) for i in range(th.n)]
        v = [n[i] * beta * k[i] / d[i] if n[i] > 0.0 else 0.0 for i in range(th.n)]
        lq = [n[i] * (1.0 - beta) / d[i] if n[i] > 0.0 else 0.0 for i in range(th.n)]
        h = (th.hv64(v, bp.t) if sum(v) > 0.0 else 0.0) + (
            th.hl64(lq, bp.t) if sum(lq) > 0.0 else 0.0
        )
        return h - target, (bp.t, lq, v)

    f_lo, p_lo = big_f(0.0)
    f_hi, p_hi = big_f(1.0)
    beta, _, payload, ev = bracketed_root64(
        big_f, (0.0, f_lo, p_lo), (1.0, f_hi, p_hi), 2, MAX_BAND_EVALUATIONS, width_floor
    )
    t, lq, v = payload
    return PH64("band", t, sum(v) / sum(n), lq, v, ev)


# ================================================================================================
# 5. The columns C-MW and C-EW (S10C-spec §4): MESH roots at 50 digits
# ================================================================================================

N_STAGES = 20  # S02 §1 item 1: N counts the total condenser (stage 1) and the reboiler (stage N)
FEED_STAGE = 10
EQ = list(range(2, N_STAGES + 1))  # the 19 equilibrium stages
SCALE_Q = mpf(10000)  # the generator's energy-row scale (S02's)

COLUMN_CASES: dict[str, dict[str, Any]] = {
    "C-MW": {
        "feed": (0.4, 0.0, 0.6),
        "present": (0, 2),
        "reflux_ratio": "1.5",
        "bottoms_rate": "0.6",
        "why": "methanol-water: the nominal composition-dependent-K column; a binary on the "
        "ternary provider (ethanol exactly +0.0); feed pinch on stages 10-14",
    },
    "C-EW": {
        "feed": (0.0, 0.2, 0.8),
        "present": (1, 2),
        "reflux_ratio": "3",
        "bottoms_rate": "0.82",
        "why": "ethanol-water: azeotrope-limited (x_D below the model azeotrope); the larger "
        "non-ideality (Lambda_EW = 0.165); feed pinch on stages 10-17",
    },
}


class Column:
    """One registered column in the generator's own formulation (S02 §11's style): per
    equilibrium stage j the present components' l_j, v_j and T_j; the condenser's T_c; quotient
    equilibrium rows y_i - K_i(T_j, x_j) x_i; energy rows / 1e4; the reboiler's slot L_20 - B*
    in place of its energy row (Q_r follows from it); phi = RR/(1 + RR) from the condenser's slot
    (Q_c follows from the condenser's energy row)."""

    def __init__(self, th: Thermo, name: str) -> None:
        case = COLUMN_CASES[name]
        self.th, self.name = th, name
        self.feed = case["feed"]
        self.a, self.w = case["present"]
        self.idx = (self.a, self.w)
        self.rr = mpf(float(case["reflux_ratio"]))
        self.b_star = mpf(float(case["bottoms_rate"]))
        self.phi = self.rr / (1 + self.rr)
        self.p = P_ATM
        self.f_tot = sum(mpf(v) for v in self.feed)
        # The feed: saturated liquid at the 50-digit bubble temperature, rounded to the nearest
        # double (the registered input), at P_ATM, on stage FEED_STAGE.
        bp, _ = band_point(th, list(self.feed), self.p, 0.0)
        self.t_bubble_feed = bp.t
        self.t_feed = exact_double(bp.t)
        self.h_feed = th.hl([mpf(v) for v in self.feed], mpf(self.t_feed))
        self.size = 5 * len(EQ) + 1

    def full(self, pair: Sequence[Any]) -> list[Any]:
        out: list[Any] = [mpf(0)] * self.th.n
        out[self.a], out[self.w] = pair[0], pair[1]
        return out

    def unpack(self, u: Sequence[Any]) -> dict[str, Any]:
        st: dict[str, Any] = {"lq": {}, "v": {}, "T": {}}
        for s, j in enumerate(EQ):
            o = 5 * s
            st["lq"][j] = [u[o], u[o + 1]]
            st["v"][j] = [u[o + 2], u[o + 3]]
            st["T"][j] = u[o + 4]
        st["Tc"] = u[5 * len(EQ)]
        return st

    # the pair's closed forms, with the absent component at exactly zero
    def lnk_pair(self, t: Any, pair: Sequence[Any]) -> list[Any]:
        lk = self.th.lnk(t, self.p, self.full(pair))
        return [lk[self.a], lk[self.w]]

    def h_pair(self, pair: Sequence[Any], t: Any, phase: str) -> Any:
        fn = self.th.m.h0l if phase == "LIQUID" else self.th.m.h_ig
        return pair[0] * fn(self.a, t) + pair[1] * fn(self.w, t)

    def inflows(self, st: dict[str, Any], j: int) -> list[tuple[list[Any], Any, str]]:
        out: list[tuple[list[Any], Any, str]] = []
        if j == 2:
            out.append(([self.phi * v for v in st["v"][2]], st["Tc"], "LIQUID"))
        else:
            out.append((st["lq"][j - 1], st["T"][j - 1], "LIQUID"))
        if j < N_STAGES:
            out.append((st["v"][j + 1], st["T"][j + 1], "VAPOR"))
        return out

    def residual(self, u: Sequence[Any]) -> list[Any]:
        st = self.unpack(u)
        rows: list[Any] = []
        feed_pair = [mpf(self.feed[self.a]), mpf(self.feed[self.w])]
        for j in EQ:
            ins = self.inflows(st, j)
            lq, v, t = st["lq"][j], st["v"][j], st["T"][j]
            for c in range(2):
                inflow = sum(f[0][c] for f in ins) + (feed_pair[c] if j == FEED_STAGE else 0)
                rows.append(inflow - lq[c] - v[c])
            big_l, big_v = lq[0] + lq[1], v[0] + v[1]
            lk = self.lnk_pair(t, [lq[0] / big_l, lq[1] / big_l])
            for c in range(2):
                rows.append(v[c] / big_v - mp.exp(lk[c]) * lq[c] / big_l)
            if j < N_STAGES:
                h_in = sum(self.h_pair(f[0], f[1], f[2]) for f in ins)
                if j == FEED_STAGE:
                    h_in += self.h_feed
                h_out = self.h_pair(lq, t, "LIQUID") + self.h_pair(v, t, "VAPOR")
                rows.append((h_in - h_out) / SCALE_Q)
            else:
                rows.append(big_l - self.b_star)
        v2 = st["v"][2]
        big_v2 = v2[0] + v2[1]
        xc = [v2[0] / big_v2, v2[1] / big_v2]
        lk = self.lnk_pair(st["Tc"], xc)
        rows.append(xc[0] * mp.exp(lk[0]) + xc[1] * mp.exp(lk[1]) - 1)
        return rows

    def duties(self, st: dict[str, Any]) -> tuple[Any, Any]:
        """Q_c and Q_r from the condenser's and the reboiler's energy rows (S02 §2.2, §2.1)."""
        v2, tc = st["v"][2], st["Tc"]
        q_c = self.h_pair(v2, tc, "LIQUID") - self.h_pair(v2, st["T"][2], "VAPOR")
        j = N_STAGES
        ins = self.inflows(st, j)
        h_in = sum(self.h_pair(f[0], f[1], f[2]) for f in ins)
        h_out = self.h_pair(st["lq"][j], st["T"][j], "LIQUID") + self.h_pair(
            st["v"][j], st["T"][j], "VAPOR"
        )
        return q_c, h_out - h_in

    # -- the binary64 starting point (SciPy's hybr on the same rows; see the module docstring)
    def start(self) -> list[float]:
        from scipy.optimize import root

        th, a, w = self.th, self.a, self.w
        d_star = float(self.f_tot - self.b_star)
        rr, phi = float(self.rr), float(self.phi)

        def lnk64(t: float, pair: Sequence[float]) -> list[float]:
            x = [0.0] * th.n
            x[a], x[w] = pair[0], pair[1]
            lk = th.lnk64(t, self.p, x)
            return [lk[a], lk[w]]

        def h64(pair: Sequence[float], t: float, phase: str) -> float:
            fn = th.f.h0l if phase == "LIQUID" else th.f.h_ig
            return pair[0] * fn(a, t) + pair[1] * fn(w, t)

        feed_pair = [self.feed[a], self.feed[w]]
        h_feed = float(self.h_feed)

        def res(u: np.ndarray) -> np.ndarray:
            out: list[float] = []
            ls = {j: u[5 * s : 5 * s + 2] for s, j in enumerate(EQ)}
            vs = {j: u[5 * s + 2 : 5 * s + 4] for s, j in enumerate(EQ)}
            ts = {j: u[5 * s + 4] for s, j in enumerate(EQ)}
            tc = u[5 * len(EQ)]
            for j in EQ:
                if j == 2:
                    above, t_above = phi * vs[2], tc
                else:
                    above, t_above = ls[j - 1], ts[j - 1]
                below = vs[j + 1] if j < N_STAGES else np.zeros(2)
                fin = np.array(feed_pair) if j == FEED_STAGE else np.zeros(2)
                out += list(above + below + fin - ls[j] - vs[j])
                big_l, big_v = ls[j].sum(), vs[j].sum()
                k = np.exp(lnk64(ts[j], ls[j] / big_l))
                out += list(vs[j] / big_v - k * ls[j] / big_l)
                if j < N_STAGES:
                    e = (
                        h64(above, t_above, "LIQUID")
                        + h64(below, ts[j + 1], "VAPOR")
                        - h64(ls[j], ts[j], "LIQUID")
                        - h64(vs[j], ts[j], "VAPOR")
                    )
                    if j == FEED_STAGE:
                        e += h_feed
                    out.append(e / 1e4)
                else:
                    out.append(big_l - float(self.b_star))
            xc = vs[2] / vs[2].sum()
            out.append(float(np.dot(xc, np.exp(lnk64(tc, xc)))) - 1.0)
            return np.array(out)

        t_top = band_point64(th, self.full_f([0.95, 0.05]), self.p, 0.0).t
        t_bot = band_point64(th, self.full_f([0.01, 0.99]), self.p, 0.0).t
        temps = np.linspace(t_top, t_bot, len(EQ))
        xs = np.linspace(0.9, 0.01, len(EQ))
        v_top = (rr + 1.0) * d_star
        u0: list[float] = []
        for s, j in enumerate(EQ):
            big_l = rr * d_star if j < FEED_STAGE else rr * d_star + float(self.f_tot)
            if j == N_STAGES:
                big_l = float(self.b_star)
            x = np.array([xs[s], 1.0 - xs[s]])
            y = x * np.exp(lnk64(temps[s], x))
            u0 += list(big_l * x) + list(v_top * y / y.sum()) + [temps[s]]
        u0.append(temps[0] - 1.0)
        sol = root(res, np.array(u0), method="hybr", options={"xtol": 1e-13, "maxfev": 400000})
        claim(
            f"COL-{self.name}-START",
            bool(sol.success) and float(np.max(np.abs(sol.fun))) < 1e-9,
            f"{self.name}: the binary64 starting point converged (SciPy hybr, max|row| < 1e-9)",
        )
        return [float(v) for v in sol.x]

    def full_f(self, pair: Sequence[float]) -> list[float]:
        out = [0.0] * self.th.n
        out[self.a], out[self.w] = pair[0], pair[1]
        return out

    def solve(self) -> list[Any]:
        return newton(self.residual, [mpf(v) for v in self.start()], tol=mpf("1e-42"))

    # -- the implementation's row forms (S01/S02: division-free), for the acceptance image ----
    def impl_unknowns(self, u: Sequence[Any]) -> list[Any]:
        st = self.unpack(u)
        q_c, q_r = self.duties(st)
        return list(u) + [self.phi, q_c, q_r]

    def impl_residual(self, w: Sequence[Any]) -> list[Any]:
        """Rows in the implementation's forms over (stage lq, v, T; T_c; phi; Q_c; Q_r): material
        rows, `v_i L - K_i l_i V`, energy rows with Q_r on the reboiler, the reboiler's slot
        `L_N - B*`, the condenser's `bubble` `sum K_i v_i2 - V_2`, its energy row with r and d at
        (T_c, P_c), and its slot `sum r - RR D`."""
        u, phi, q_c, q_r = w[: self.size], w[self.size], w[self.size + 1], w[self.size + 2]
        st = self.unpack(u)
        rows: list[Any] = []
        feed_pair = [mpf(self.feed[self.a]), mpf(self.feed[self.w])]
        v2 = st["v"][2]
        for j in EQ:
            if j == 2:
                ins = [
                    ([phi * v for v in v2], st["Tc"], "LIQUID"),
                    (st["v"][3], st["T"][3], "VAPOR"),
                ]
            else:
                ins = self.inflows(st, j)
            lq, v, t = st["lq"][j], st["v"][j], st["T"][j]
            for c in range(2):
                inflow = sum(f[0][c] for f in ins) + (feed_pair[c] if j == FEED_STAGE else 0)
                rows.append(inflow - lq[c] - v[c])
            big_l, big_v = lq[0] + lq[1], v[0] + v[1]
            lk = self.lnk_pair(t, [lq[0] / big_l, lq[1] / big_l])
            for c in range(2):
                rows.append(v[c] * big_l - mp.exp(lk[c]) * lq[c] * big_v)
            h_in = sum(self.h_pair(f[0], f[1], f[2]) for f in ins)
            if j == FEED_STAGE:
                h_in += self.h_feed
            h_out = self.h_pair(lq, t, "LIQUID") + self.h_pair(v, t, "VAPOR")
            rows.append((q_r if j == N_STAGES else 0) + h_in - h_out)
        rows.append(st["lq"][N_STAGES][0] + st["lq"][N_STAGES][1] - self.b_star)
        big_v2 = v2[0] + v2[1]
        lk = self.lnk_pair(st["Tc"], [v2[0] / big_v2, v2[1] / big_v2])
        rows.append(mp.exp(lk[0]) * v2[0] + mp.exp(lk[1]) * v2[1] - big_v2)
        rows.append(
            q_c
            + self.h_pair(v2, st["T"][2], "VAPOR")
            - self.h_pair([phi * v for v in v2], st["Tc"], "LIQUID")
            - self.h_pair([(1 - phi) * v for v in v2], st["Tc"], "LIQUID")
        )
        rows.append(phi * big_v2 - self.rr * (1 - phi) * big_v2)
        return rows

    def impl_tolerances(self, w: Sequence[Any]) -> list[float]:
        """Each implementation row's acceptance allowance, conservatively including the linear rows
        the generator eliminates (mix and balance; L, V definitions; Q_j - 0 slots; the condenser's
        split, bal and Ddef rows), each at its kind tolerance."""
        st = self.unpack(w[: self.size])
        tf, te, tq = FLOW_TOLERANCE, ENERGY_TOLERANCE, EQUILIBRIUM_TOLERANCE
        tol: list[float] = []
        for j in EQ:
            lq, v, t = st["lq"][j], st["v"][j], st["T"][j]
            big_l = lq[0] + lq[1]
            lk = self.lnk_pair(t, [lq[0] / big_l, lq[1] / big_l])
            tol += [(4 if j == 2 else 2) * tf] * 2
            tol += [tq + tf * float(abs(v[c]) + mp.exp(lk[c]) * abs(lq[c])) for c in range(2)]
            tol.append((1 if j == N_STAGES else 2) * te)
        tol.append(2 * tf)  # L_N - B*, plus the L_N definition row
        tol.append(2 * tf)  # bubble, plus the V_2 definition row
        tol.append(te)
        tol.append((1 + 2 * 2 * (1 + float(self.rr))) * tf)  # slot, split, bal, Ddef
        return tol


# ================================================================================================
# 6. The blocks (S10C-spec §5.4, G6): closed-form values and Jacobians; the FD stencil's floor
# ================================================================================================

FD_REL = 1e-6  # the stencil's relative step


def block_scales(n: Sequence[float], p: float) -> dict[str, float]:
    """s of the relative error |FD - J| / max(|J|, s): S10 §7.2's scales, the H block's scaled
    by n_tot (H = n_tot h)."""
    tot = sum(n)
    return {"lnK_n": 1.0 / tot, "lnK_T": 1e-2, "lnK_P": 1.0 / p, "H_n": 1e3, "H_T": 10.0 * tot}


def k_block_mp(th: Thermo, n: Sequence[float], t: float, p: float) -> dict[str, Any]:
    """The K-block (design §4.7): lnK_i = lnphi_i^L at the liquid n; Jacobian columns
    (n_1..n_C, T, P), the provider's projected derivatives."""
    ev = th.m.evaluate(n, t, p, "LIQUID")
    ids = th.rec.ids
    vals = [ev["values"][f"lnphi_{c}"] for c in ids]
    jac = [
        [ev["derivatives"][f"lnphi_{c}"][f"n_{cj}"] for cj in ids]
        + [ev["derivatives"][f"lnphi_{c}"]["T"], ev["derivatives"][f"lnphi_{c}"]["P"]]
        for c in ids
    ]
    return {"values": vals, "jacobian": jac}


def h_block_mp(th: Thermo, n: Sequence[float], t: float, p: float, phase: str) -> dict[str, Any]:
    """The mixture enthalpy block: H = n_tot h; dH/dn_j = h + n_tot dh/dn_j (= h_j of the phase);
    dH/dT = n_tot dh/dT; dH/dP = n_tot dh/dP = 0 exactly."""
    ev = th.m.evaluate(n, t, p, phase)
    tot = sum(mpf(v) for v in n)
    h = ev["values"]["h"]
    d = ev["derivatives"]["h"]
    jac = [h + tot * d[f"n_{c}"] for c in th.rec.ids] + [tot * d["T"], tot * d["P"]]
    return {"value": tot * h, "jacobian": jac}


def k_block64(th: Thermo, n: Sequence[float], t: float, p: float) -> list[float]:
    ev = th.f.evaluate(n, t, p, "LIQUID")
    return [ev["values"][f"lnphi_{c}"] for c in th.rec.ids]


def h_block64(th: Thermo, n: Sequence[float], t: float, p: float, phase: str) -> float:
    ev = th.f.evaluate(n, t, p, phase)
    return sum(n) * ev["values"]["h"]


def stencil(u: float, kind: str) -> tuple[str, float]:
    """The registered stencil of one input: central with h = 1e-6 |u| for T and P; for a flow,
    central with h = min(1e-6 max(u, 1), u/2) when u > 0 and the one-sided second-order
    (-3 f(0) + 4 f(h) - f(2h)) / (2h) with h = 1e-6 when u = 0."""
    if kind in ("T", "P"):
        return "central", FD_REL * abs(u)
    if u > 0.0:
        return "central", min(FD_REL * max(u, 1.0), 0.5 * u)
    return "forward2", FD_REL


def fd_column(
    fun: Callable[[list[float]], Any],
    u: list[float],
    k: int,
    kind: str,
    domain: dict[str, tuple[float, float]],
) -> tuple[Any, list[list[float]]]:
    """One FD column of `fun` at u along input k; returns the derivative and the stencil points
    (for the domain claim)."""
    form, h = stencil(u[k], kind)
    if form == "central":
        up, um = list(u), list(u)
        up[k] += h
        um[k] -= h
        fp, fm = fun(up), fun(um)
        if isinstance(fp, list):
            return [(a - b) / (2 * h) for a, b in zip(fp, fm, strict=True)], [up, um]
        return (fp - fm) / (2 * h), [up, um]
    u1, u2 = list(u), list(u)
    u1[k] += h
    u2[k] += 2 * h
    f0, f1, f2 = fun(u), fun(u1), fun(u2)
    if isinstance(f0, list):
        return [(-3 * a + 4 * b - c) / (2 * h) for a, b, c in zip(f0, f1, f2, strict=True)], [
            u1,
            u2,
        ]
    return (-3 * f0 + 4 * f1 - f2) / (2 * h), [u1, u2]


def inside(th: Thermo, point: Sequence[float]) -> bool:
    nc = th.n
    flows, t, p = point[:nc], point[nc], point[nc + 1]
    return (
        all(v >= 0.0 for v in flows)
        and sum(flows) > 0.0
        and th.t_lo <= t <= th.t_hi
        and th.rec.p_lo <= p <= th.rec.p_hi
    )


def fd_errors(th: Thermo, n: Sequence[float], t: float, p: float) -> dict[str, float]:
    """The measured FD error (binary64 transcription, registered stencils) of both blocks against
    their 50-digit Jacobians, as the largest relative error |FD - J| / max(|J|, s) per block."""
    nc = th.n
    u = [float(v) for v in n] + [float(t), float(p)]
    kinds = ["n"] * nc + ["T", "P"]
    sc = block_scales(n, p)
    kb = k_block_mp(th, n, t, p)
    out = {"K": 0.0, "H_LIQUID": 0.0, "H_VAPOR": 0.0}
    for k in range(nc + 2):
        col, pts = fd_column(lambda v: k_block64(th, v[:nc], v[nc], v[nc + 1]), u, k, kinds[k], {})
        for pt in pts:
            claim(
                "FD-DOMAIN", inside(th, pt), "every FD stencil point lies in the provider's domain"
            )
        s = sc["lnK_n"] if k < nc else (sc["lnK_T"] if k == nc else sc["lnK_P"])
        for i in range(nc):
            ref = float(kb["jacobian"][i][k])
            out["K"] = max(out["K"], abs(col[i] - ref) / max(abs(ref), s))
    for phase in ("LIQUID", "VAPOR"):
        hb = h_block_mp(th, n, t, p, phase)
        for k in range(nc + 2):
            col, _ = fd_column(
                lambda v, ph=phase: h_block64(th, v[:nc], v[nc], v[nc + 1], ph), u, k, kinds[k], {}
            )
            ref = float(hb["jacobian"][k])
            if k == nc + 1:
                claim(
                    "FD-HP-ZERO",
                    col == 0.0 and ref == 0.0,
                    "dH/dP is exactly 0.0 and its central difference is exactly 0.0 (h has no P)",
                )
                continue
            s = sc["H_n"] if k < nc else sc["H_T"]
            out[f"H_{phase}"] = max(out[f"H_{phase}"], abs(col - ref) / max(abs(ref), s))
    return out


def block_value_floor(
    th: Thermo,
    n: Sequence[float],
    t: float,
    p: float,
    kb: dict[str, Any],
    hl_: dict[str, Any],
    hv_: dict[str, Any],
) -> float:
    """The binary64 transcription of both blocks against their closed forms, as the largest
    |f64 - ref| / max(|ref|, s) (S10 §7.2's rule and scales; the H block's scaled by n_tot)."""
    nc = th.n
    sc = block_scales(n, p)
    tot = sum(n)
    worst = 0.0
    ev = th.f.evaluate(n, t, p, "LIQUID")
    for i, c in enumerate(th.rec.ids):
        worst = max(
            worst,
            abs(ev["values"][f"lnphi_{c}"] - float(kb["values"][i]))
            / max(abs(float(kb["values"][i])), 1.0),
        )
        row = [ev["derivatives"][f"lnphi_{c}"][f"n_{cj}"] for cj in th.rec.ids] + [
            ev["derivatives"][f"lnphi_{c}"]["T"],
            ev["derivatives"][f"lnphi_{c}"]["P"],
        ]
        for k in range(nc + 2):
            s_ = sc["lnK_n"] if k < nc else (sc["lnK_T"] if k == nc else sc["lnK_P"])
            ref = float(kb["jacobian"][i][k])
            worst = max(worst, abs(row[k] - ref) / max(abs(ref), s_))
    for phase, hb in (("LIQUID", hl_), ("VAPOR", hv_)):
        ev = th.f.evaluate(n, t, p, phase)
        h, d = ev["values"]["h"], ev["derivatives"]["h"]
        worst = max(
            worst, abs(tot * h - float(hb["value"])) / max(abs(float(hb["value"])), 1e3 * tot)
        )
        row = [h + tot * d[f"n_{c}"] for c in th.rec.ids] + [tot * d["T"]]
        for k in range(nc + 1):
            s_ = sc["H_n"] if k < nc else sc["H_T"]
            ref = float(hb["jacobian"][k])
            worst = max(worst, abs(row[k] - ref) / max(abs(ref), s_))
    return worst


def m1_signal(th: Thermo, n: Sequence[float], t: float, p: float) -> float:
    """M1 (the K-block's n columns set to 0.0): the relative error it shows at this state,
    max_ij |J_ij| / max(|J_ij|, s)."""
    kb = k_block_mp(th, n, t, p)
    s = block_scales(n, p)["lnK_n"]
    return max(
        float(abs(kb["jacobian"][i][j]) / max(abs(kb["jacobian"][i][j]), s))
        for i in range(th.n)
        for j in range(th.n)
    )


# ================================================================================================
# 7. The theorems' executable checks (S10C-spec §2, T1-T5) at registered states
# ================================================================================================


def liquid_trial_mp(th: Thermo, z: Sequence[Any], p: float, t: Any, w0: Sequence[Any]) -> list[Any]:
    """The liquid-trial stationary point W_i = z_i / K_i(T, P, W/sum W) (i in F), by Newton."""
    act = [i for i in range(th.n) if z[i] > 0]

    def full(ws: Sequence[Any]) -> list[Any]:
        out: list[Any] = [mpf(0)] * th.n
        for i, v in zip(act, ws, strict=True):
            out[i] = v
        return out

    def fun(v: list[Any]) -> list[Any]:
        lk = th.lnk(t, p, full(v))
        return [v[a] * mp.exp(lk[i]) - z[i] for a, i in enumerate(act)]

    return full(newton(fun, [w0[i] for i in act]))


def gmat_full(th: Thermo, x: Sequence[Any]) -> list[list[Any]]:
    tot = sum(x)
    return th.m.gmat([v / tot for v in x])


def latent_slope(th: Thermo, sp: Split) -> tuple[Any, Any]:
    """T3: dHdot_TP/dT along the split = frozen part + dh^T A^-1 dh / (R T^2), with
    A = [diag(1/y) - 1 1^T]/V + [diag(1/x) + G]/L over the flowing components (S10C-spec §2.4)."""
    act = [i for i in range(th.n) if sp.lq[i] + sp.v[i] > 0]
    t = sp.t
    big_l, big_v = sum(sp.lq), sum(sp.v)
    g = gmat_full(th, sp.x)
    m = len(act)
    a = mp.matrix(m, m)
    for r, i in enumerate(act):
        for c, j in enumerate(act):
            a[r, c] = ((1 / sp.y[i] if i == j else 0) - 1) / big_v + (
                (1 / sp.x[i] if i == j else 0) + g[i][j]
            ) / big_l
    dh = mp.matrix([th.m.h_ig(i, t) - th.m.h0l(i, t) for i in act])
    latent = (dh.T * mp.lu_solve(a, dh))[0] / (s10.R * t * t)
    frozen = sum(sp.lq[i] * th.m.cp0l(i, t) + sp.v[i] * th.m.cp_ig(i, t) for i in act)
    return frozen, latent


def theorem_checks(
    th: Thermo, n: Sequence[float], p: float, sp: Split, label: str
) -> dict[str, Any]:
    """T3 (and T5 for a binary) at the split `sp`: the derived slopes against 50-digit central
    differences of the split in T (step 1e-15 K: truncation ~1e-30, roundoff ~1e-35)."""
    out: dict[str, Any] = {}
    delta = mpf("1e-15")
    act = [i for i in range(th.n) if n[i] > 0.0]

    def split_at(t: Any) -> Split:
        return tp_split_mp(th, n, p, t, [sp.beta] + [sp.x[i] for i in act])

    up, dn = split_at(sp.t + delta), split_at(sp.t - delta)
    fd = (up.h - dn.h) / (2 * delta)
    frozen, latent = latent_slope(th, sp)
    rel = abs(fd - frozen - latent) / abs(fd)
    claim(
        f"T3-{label}",
        rel < mpf("1e-12") and latent > 0 and frozen > 0,
        f"{label}: dHdot_TP/dT by 50-digit central differences equals frozen + "
        f"dh^T A^-1 dh/(R T^2) (relative {mp.nstr(rel, 3)}); latent > 0, frozen > 0 (T3)",
    )
    out["dH_dT"] = nstr(fd)
    out["frozen"] = nstr(frozen)
    out["latent"] = nstr(latent)
    out["fd_vs_formula_rel"] = g3(float(rel))
    if len(act) == 2:
        i1, i2 = act
        x1, x2, y1, y2 = sp.x[i1], sp.x[i2], sp.y[i1], sp.y[i2]
        g = gmat_full(th, sp.x)
        gamma_tf = -g[i1][i2]
        t = sp.t
        dh = {i: th.m.h_ig(i, t) - th.m.h0l(i, t) for i in act}
        rt2 = s10.R * t * t
        dx1 = -(y1 * dh[i1] + y2 * dh[i2]) * x1 * x2 / (rt2 * gamma_tf * (y1 - x1))
        dy1 = -(x1 * dh[i1] + x2 * dh[i2]) * y1 * y2 / (rt2 * (y1 - x1))
        dbeta = -((1 - sp.beta) * dx1 + sp.beta * dy1) / (y1 - x1)
        fd_x = (up.x[i1] - dn.x[i1]) / (2 * delta)
        fd_y = (up.y[i1] - dn.y[i1]) / (2 * delta)
        fd_b = (up.beta - dn.beta) / (2 * delta)
        gd = 1 + x1 * (g[i1][i1] - g[i1][i2])
        ok = (
            gamma_tf > 0
            and abs(gd - gamma_tf) < mpf("1e-40")
            and abs(fd_x - dx1) <= mpf("1e-12") * abs(dx1)
            and abs(fd_y - dy1) <= mpf("1e-12") * abs(dy1)
            and abs(fd_b - dbeta) <= mpf("1e-12") * abs(dbeta)
            and dbeta > 0
        )
        claim(
            f"T5-{label}",
            ok,
            f"{label}: Gamma = 1 + x1 dln(gamma1)/dx1 = -G_12 > 0; dx1/dT, dy1/dT and dbeta/dT "
            f"(Gibbs-Konovalov, S10C-spec §2.6) equal 50-digit central differences to 1e-12 "
            f"relative; dbeta/dT > 0 (T5)",
        )
        out["thermodynamic_factor"] = nstr(gamma_tf)
        out["dx1_dT"] = nstr(dx1)
        out["dy1_dT"] = nstr(dy1)
        out["dbeta_dT"] = nstr(dbeta)
    return out


def envelope_check(
    th: Thermo, n: Sequence[float], p: float, t: Any, w0: Sequence[Any], label: str
) -> dict[str, Any]:
    """T2: d tm*/dT = sum_i W_i* d ln P_i^sat/dT (the envelope theorem), against 50-digit central
    differences of tm*(T) = 1 - sum W*."""
    nn = [mpf(v) for v in n]
    tot = sum(nn)
    z = [v / tot for v in nn]
    delta = mpf("1e-15")
    w = liquid_trial_mp(th, z, p, mpf(t), w0)
    wp = liquid_trial_mp(th, z, p, mpf(t) + delta, w)
    wm = liquid_trial_mp(th, z, p, mpf(t) - delta, w)
    fd = (-(sum(wp)) + sum(wm)) / (2 * delta)
    env = sum(w[i] * th.m.dlnpsat(i, mpf(t)) for i in range(th.n) if z[i] > 0)
    rel = abs(fd - env) / env
    claim(
        f"T2-{label}",
        rel < mpf("1e-12") and env > 0,
        f"{label}: d tm*/dT by central differences equals sum W* dlnPsat/dT > 0 "
        f"(relative {mp.nstr(rel, 3)}; T2's envelope theorem)",
    )
    return {
        "records": th.name,
        "n": list(n),
        "P": p,
        "T": nstr(t),
        "tm_star": nstr(1 - sum(w)),
        "dtm_dT": nstr(env),
        "fd_rel": g3(float(rel)),
    }


# ================================================================================================
# 8. The convergence scan of the constant-beta point (Q5; measured, binary64)
# ================================================================================================

SCAN_BETAS = (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)
SCAN_BINARY = (0.001, 0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 0.999)


def scan(th: Thermo) -> dict[str, Any]:
    feeds: list[list[float]] = []
    for i, j in ((0, 1), (0, 2), (1, 2)):
        for a in SCAN_BINARY:
            f = [0.0] * th.n
            f[i], f[j] = a, 1.0 - a
            feeds.append(f)
    for a in range(1, 9):
        for b in range(1, 10 - a):
            feeds.append([a / 10, b / 10, (10 - a - b) / 10])
    pressures = (th.rec.p_lo, P_ATM, th.rec.p_hi)
    worst_it, worst_rate, count = 0, 0.0, 0
    positions = {"inside": 0, "below": 0, "above": 0}
    worst_at: list[Any] = []
    for f in feeds:
        for p in pressures:
            for beta in SCAN_BETAS:
                pt = band_point64(th, f, p, beta)  # raises SystemExit on no stop
                count += 1
                positions[pt.position] += 1
                if pt.iterations > worst_it:
                    worst_it, worst_at = pt.iterations, [f, p, beta]
                worst_rate = max(worst_rate, contraction(pt.steps))
    claim(
        f"SCAN-{th.rec.convention}",
        worst_it <= BETA_SS_MAX // 10,
        f"{th.rec.convention}: the binary64 constant-beta point stops at all {count} scan points "
        f"(3 binaries x 15 compositions + 36 ternary, 3 pressures, 7 betas) within "
        f"BETA_SS_MAX/10 = {BETA_SS_MAX // 10} iterations (worst {worst_it})",
    )
    return {
        "points": count,
        "worst_iterations": worst_it,
        "worst_at": {"z": worst_at[0], "P": worst_at[1], "beta": worst_at[2]},
        "worst_contraction": g3(worst_rate),
        "positions": positions,
    }


# ================================================================================================
# 9. The registered states (S10C-spec §5) and the document
# ================================================================================================

BETAS5 = (0.0, 0.1, 0.5, 0.9, 1.0)
BETAS_E2 = (0.0, 0.25, 0.5, 0.75, 1.0)
BETAS3 = (0.0, 0.5, 1.0)

# (id, record set, n, P, betas, why)
BAND_STATES: list[tuple[str, str, tuple[float, ...], float, tuple[float, ...], str]] = [
    (
        "BP-R01",
        "real",
        (0.0, 0.2, 0.8),
        P_ATM,
        BETAS5,
        "ethanol-water on the water side (C-EW's feed)",
    ),
    (
        "BP-R02",
        "real",
        (0.0, 0.5, 0.5),
        P_ATM,
        BETAS5,
        "ethanol-water at 0.5: the slowest contraction of the design's measurements (M-a)",
    ),
    (
        "BP-R03",
        "real",
        (0.0, 0.8, 0.2),
        P_ATM,
        BETAS5,
        "ethanol-water 0.08 below the model azeotrope: K near 1 towards the dew end",
    ),
    (
        "BP-R04",
        "real",
        (0.0, 0.88134, 0.11866),
        P_ATM,
        BETAS5,
        "1e-4 below the model azeotrope (x_az = 0.88144): a band 1e-8 K wide",
    ),
    (
        "BP-R05",
        "real",
        (0.0, 0.88154, 0.11846),
        P_ATM,
        BETAS5,
        "1e-4 above the model azeotrope: y - x has the other sign",
    ),
    ("BP-R06", "real", (0.4, 0.0, 0.6), P_ATM, BETAS5, "methanol-water (C-MW's feed)"),
    (
        "BP-R07",
        "real",
        (0.994, 0.0, 0.006),
        P_ATM,
        BETAS5,
        "methanol-rich (C-MW's distillate composition)",
    ),
    (
        "BP-R08",
        "real",
        (0.0039, 0.0, 0.9961),
        P_ATM,
        BETAS5,
        "water-rich (C-MW's bottoms composition)",
    ),
    (
        "BP-R09",
        "real",
        (1.0, 0.0, 1e-10),
        P_ATM,
        BETAS5,
        "near-pure methanol with a 1e-10 water trace: two flowing components, band ~2e-9 K",
    ),
    (
        "BP-R10",
        "real",
        (1e-10, 0.0, 1.0),
        P_ATM,
        BETAS5,
        "near-pure water with a 1e-10 methanol trace",
    ),
    (
        "BP-R11",
        "real",
        (0.6, 0.4, 1.0),
        P_ATM,
        BETAS5,
        "ternary interior with n_tot = 2: the band point normalises the flows",
    ),
    (
        "BP-R12",
        "real",
        (0.6, 0.4, 1.0),
        30000.0,
        BETAS5,
        "the ternary at the domain's P_min: a pressure-blind implementation fails here",
    ),
    ("BP-R13", "real", (0.6, 0.4, 1.0), 200000.0, BETAS5, "the ternary at the domain's P_max"),
    (
        "BP-R14",
        "real",
        (0.0, 0.0, 1.0),
        P_ATM,
        BETAS3,
        "pure water: x = e_c exactly and T = T_sat at every beta, in exactly one iteration",
    ),
    (
        "BP-V01",
        "verification",
        (0.0, 1.675349164407079, 0.324650835592921),
        P_ATM,
        BETAS_E2,
        "E-2 feed 1 (x_VB = x_az + 2e-5; band 2.5e-8 K)",
    ),
    (
        "BP-V02",
        "verification",
        (0.0, 1.675209164407079, 0.324790835592921),
        P_ATM,
        BETAS_E2,
        "E-2 feed 2 (x_VB = x_az - 5e-5; band 1.5e-7 K)",
    ),
    (
        "BP-V03",
        "verification",
        (0.0, 1.675509164407079, 0.324490835592921),
        P_ATM,
        BETAS_E2,
        "E-2 feed 3 (x_VB = x_az + 1e-4; band 6.2e-7 K)",
    ),
    (
        "BP-V04",
        "verification",
        (0.0, 1.675339164407079, 0.324660835592921),
        P_ATM,
        BETAS_E2,
        "E-2 feed 4, the S10 review's reproducer (band 1.4e-8 K)",
    ),
    (
        "BP-I01",
        "ideal",
        (0.6, 0.8, 0.6),
        P_ATM,
        BETAS3,
        "Lambda = 1 (Raoult): T_b and T_d have closed forms; exactly one iteration at every beta",
    ),
    (
        "BP-N01",
        "narrowed",
        (0.9, 0.1, 0.0),
        P_ATM,
        BETAS3,
        "T(beta) below T_min = 342 K at every beta: position below, no temperature",
    ),
    (
        "BP-N02",
        "narrowed",
        (0.7, 0.3, 0.0),
        P_ATM,
        BETAS3,
        "T_min inside the band: below at beta = 0 and 0.5, inside at beta = 1",
    ),
    (
        "BP-N03",
        "narrowed",
        (0.0, 0.1, 0.9),
        P_ATM,
        BETAS3,
        "inside at beta = 0, above T_max = 365 K at beta = 0.5 and 1",
    ),
    (
        "BP-N04",
        "narrowed",
        (0.0, 0.2, 0.8),
        P_ATM,
        BETAS3,
        "T_max inside the band: inside at beta = 0 and 0.5, above at beta = 1",
    ),
]

# PH targets: (id, record set, n, P, how, value, why). `how`: ("L", T) -> H* = Hdot^L(n, T);
# ("V", T) -> Hdot^V(n, T); ("B", beta) -> Hdot of the constant-beta split; ("S", beta) -> the
# lever rule at T_sat; ("TP", T) -> Hdot of the TP split at T; ("L-", T, dW) etc. -> offsets.
PH_TARGETS: list[tuple[str, str, tuple[float, ...], float, tuple[Any, ...], str]] = [
    (
        "PH-L",
        "real",
        (0.4, 0.0, 0.6),
        P_ATM,
        ("L", 330.0),
        "subcooled methanol-water: the liquid route on [T_min, T_b]",
    ),
    (
        "PH-V",
        "real",
        (0.4, 0.0, 0.6),
        P_ATM,
        ("V", 385.0),
        "superheated methanol-water: the vapour route on [T_d, T_max]",
    ),
    (
        "PH-2B",
        "real",
        (0.0, 1.0, 1.0),
        P_ATM,
        ("B", 0.4),
        "binary two-phase (ethanol-water, n_tot = 2): the band route; T5 makes H(beta) monotone",
    ),
    (
        "PH-2T",
        "real",
        (0.6, 0.4, 1.0),
        P_ATM,
        ("B", 0.5),
        "ternary two-phase: the band route without T5's proof (T4 + acceptance)",
    ),
    (
        "PH-2P",
        "real",
        (0.6, 0.4, 1.0),
        150000.0,
        ("B", 0.5),
        "the ternary two-phase target at 1.5e5 Pa: the band route away from 1 atm",
    ),
    (
        "PH-NP",
        "real",
        (1.0, 0.0, 1e-10),
        P_ATM,
        ("B", 0.5),
        "near-pure 1e-10 trace, two-phase: the band route inside a 2e-9 K band",
    ),
    (
        "PH-NPL",
        "real",
        (1.0, 0.0, 1e-10),
        P_ATM,
        ("L", 330.0),
        "near-pure 1e-10 trace, subcooled: the liquid route",
    ),
    (
        "PH-1L",
        "real",
        (0.0, 0.0, 1.0),
        P_ATM,
        ("L", 360.0),
        "one flowing component, subcooled: the liquid route on [T_min, T_sat]",
    ),
    (
        "PH-1S",
        "real",
        (0.0, 0.0, 1.0),
        P_ATM,
        ("S", 0.3),
        "one flowing component inside the jump: the saturation route (lever rule)",
    ),
    (
        "PH-1V",
        "real",
        (0.0, 0.0, 1.0),
        P_ATM,
        ("V", 390.0),
        "one flowing component, superheated: the vapour route on [T_sat, T_max]",
    ),
    (
        "PH-OB",
        "real",
        (0.4, 0.0, 0.6),
        P_ATM,
        ("L-", 300.0, 100.0),
        "100 W below Hdot^L(T_min): ph_outside_domain(below)",
    ),
    (
        "PH-OA",
        "real",
        (0.4, 0.0, 0.6),
        P_ATM,
        ("V+", 400.0, 100.0),
        "100 W above Hdot^V(T_max): ph_outside_domain(above)",
    ),
    (
        "PH-1OB",
        "real",
        (0.0, 0.0, 1.0),
        P_ATM,
        ("L-", 300.0, 100.0),
        "one component, 100 W below Hdot^L(T_min): ph_outside_domain(below)",
    ),
    (
        "PH-ID",
        "ideal",
        (0.6, 0.8, 0.6),
        P_ATM,
        ("B", 0.5),
        "Lambda = 1 (Raoult), two-phase: the band route with composition-free K",
    ),
    (
        "PH-N1",
        "narrowed",
        (0.7, 0.3, 0.0),
        P_ATM,
        ("TP", 342.2),
        "T_min = 342 K inside the band [341.10, 342.41] K: H_lo from the provider's TP flash at "
        "T_min (one flash call), the band route's sign oracle below T_min",
    ),
    (
        "PH-N2",
        "narrowed",
        (0.7, 0.3, 0.0),
        P_ATM,
        ("TP-", 342.0, 10.0),
        "10 W below Hdot_TP(T_min) with T_min inside the band: ph_outside_domain(below)",
    ),
    (
        "PH-N3",
        "narrowed",
        (0.7, 0.3, 0.0),
        P_ATM,
        ("V", 350.0),
        "superheated with T_min inside the band: the vapour route on [T_d, T_max] (one flash call)",
    ),
]

# The 13 E-2 states of `tests/test_s10_flash.py::NEAR_AZEOTROPE` ((n_VB, n_VC), T), n_VA = 0,
# 101 325 Pa, verification records. Transcribed; `e2_states_match_the_test` checks the transcription
# against the test file's literal (parsed, not imported).
NEAR_AZEOTROPE: tuple[tuple[tuple[float, float], float], ...] = (
    ((1.675349164407079, 0.324650835592921), 350.03974947074545),
    ((1.675349164407079, 0.324650835592921), 350.0397494746303),
    ((1.675349164407079, 0.324650835592921), 350.03974947851515),
    ((1.675349164407079, 0.324650835592921), 350.0397494824),
    ((1.675209164407079, 0.324790835592921), 350.0397495467531),
    ((1.675209164407079, 0.324790835592921), 350.0397495765184),
    ((1.675209164407079, 0.324790835592921), 350.0397496062837),
    ((1.675209164407079, 0.324790835592921), 350.03974963604895),
    ((1.675509164407079, 0.324490835592921), 350.039749818219),
    ((1.675509164407079, 0.324490835592921), 350.0397499402996),
    ((1.675509164407079, 0.324490835592921), 350.03975006238016),
    ((1.675509164407079, 0.324490835592921), 350.0397501844608),
    ((1.675339164407079, 0.324660835592921), 350.0397494670053),
)
E2_TEST_FILE = ROOT / "tests" / "test_s10_flash.py"


def e2_states_match_the_test() -> None:
    import ast

    tree = ast.parse(E2_TEST_FILE.read_text(encoding="utf-8"))
    found = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "NEAR_AZEOTROPE" for t in node.targets
        ):
            found = ast.literal_eval(node.value)
    claim(
        "E2-TRANSCRIPTION",
        found == NEAR_AZEOTROPE,
        "the 13 E-2 states equal tests/test_s10_flash.py::NEAR_AZEOTROPE bitwise",
    )


# Block states beyond the column stages: (id, n, T, P, why)
BLOCK_STATES: list[tuple[str, tuple[float, ...], float, float, str]] = [
    (
        "G6-D1",
        (1e-8, 0.0, 1.0),
        372.0,
        P_ATM,
        "dilute methanol (x = 1e-8) in water with ethanol absent: the dilute and absent stencils",
    ),
    (
        "G6-D2",
        (0.3, 1e-8, 0.7),
        350.0,
        P_ATM,
        "dilute ethanol (x = 1e-8) in a methanol-water liquid: three flowing components",
    ),
    (
        "G6-T",
        (0.6, 0.4, 1.0),
        355.0,
        150000.0,
        "ternary interior, n_tot = 2, P away from 1 atm: every Jacobian entry nonzero",
    ),
]


def vec(xs: Sequence[Any]) -> list[float]:
    return [nstr(v) for v in xs]


def build() -> dict[str, Any]:
    CLAIMS.clear()
    _CLAIM_INDEX.clear()
    real_rec = s10.load_records(REAL_YAML)
    ver_rec = s10.load_records(VER_YAML)
    s10.CLAIMS.clear()
    sets = {
        "real": Thermo("real", real_rec),
        "verification": Thermo("verification", ver_rec),
        "ideal": Thermo("ideal", ideal_records(ver_rec)),
        "narrowed": Thermo("narrowed", narrowed_records(ver_rec)),
    }
    real, ver = sets["real"], sets["verification"]
    e2_states_match_the_test()
    doc: dict[str, Any] = {
        "generator": "docs/derivations/scripts/s10c_reference.py",
        "specification": "docs/derivations/S10C-spec.md",
        "design": "docs/derivations/S10C-design.md",
        "value_classes": {
            "closed_form": "expectations: mpmath at 50 digits, written to 20 significant digits",
            "inputs": "registered binary64 inputs, written exactly (repr)",
            "tolerances": "every tolerance with its floor",
            "measured": "binary64 transcriptions in the generator (never the implementation); "
            "floors and iteration counts only, never expectations",
            "generator_claims": "statements re-derived on every run",
        },
        "records": {
            "real": {
                "path": "benchmarks/s10/records.yaml",
                "sha256": real_rec.sha256,
                "convention": real_rec.convention,
            },
            "verification": {
                "path": "benchmarks/s10/verification-records.yaml",
                "sha256": ver_rec.sha256,
                "convention": ver_rec.convention,
            },
            "ideal": "the verification records with every Lambda_ij = 1.0 (built by the test)",
            "narrowed": "the verification records with domain T = "
            f"[{NARROW_T[0]}, {NARROW_T[1]}] K "
            "(built by the test)",
        },
        "constants": {
            "DELTA_BETA": DELTA_BETA,
            "BETA_SS_MAX": BETA_SS_MAX,
            "INCIPIENT_STOP": INCIPIENT_STOP,
            "INCIPIENT_MAX": INCIPIENT_MAX,
            "MAX_BAND_EVALUATIONS": MAX_BAND_EVALUATIONS,
            "BETA_WIDTH_FLOOR": BETA_WIDTH_FLOOR,
        },
    }

    # -- positivity
    doc["positivity"] = {"real": positivity(real), "verification": positivity(ver)}

    # -- azeotropes (context for the registered feeds)
    xe, te = s10.azeotrope(real.m, 1, 2, mpf(P_ATM), mpf("0.88"), mpf("351.3"))
    xb, tb = s10.azeotrope(ver.m, 1, 2, mpf(P_ATM), mpf("0.8376"), mpf("350.04"))
    claim(
        "AZ-REAL",
        abs(xe - mpf("0.88144")) < mpf("5e-6"),
        f"the model's ethanol-water azeotrope at 101325 Pa: x_E = {mp.nstr(xe, 8)}, "
        f"T = {mp.nstr(te, 9)} K",
    )
    claim(
        "AZ-REAL-FEEDS",
        mpf("0.9e-4") < xe - mpf("0.88134") < mpf("1.1e-4")
        and mpf("0.9e-4") < mpf("0.88154") - xe < mpf("1.1e-4"),
        "BP-R04 and BP-R05 lie 1e-4 (within 10 %) below and above the model azeotrope",
    )
    claim(
        "AZ-VER",
        abs(xb - mpf("0.83765458220354")) < mpf("1e-13"),
        "the VB-VC azeotrope equals S10's AZ-01 (x_VB = 0.83765458220354)",
    )
    doc["azeotropes"] = {
        "real_ethanol_water": {"x_ethanol": nstr(xe), "T": nstr(te), "P": P_ATM},
        "verification_VB_VC": {"x_VB": nstr(xb), "T": nstr(tb), "P": P_ATM},
    }

    # -- G3: band points
    bands: dict[str, Any] = {}
    floor_t = floor_x = floor_k = floor_tm = floor_res = 0.0
    worst_it = 0
    for sid, set_name, n, p, betas, why in BAND_STATES:
        th = sets[set_name]
        entry: dict[str, Any] = {
            "records": set_name,
            "n": list(n),
            "P": p,
            "why": why,
            "points": [],
        }
        prev_t = None
        for beta in betas:
            bp, b64 = band_point(th, n, p, beta)
            claim(
                "BP-POSITION",
                b64.position == bp.position,
                "the binary64 transcription's position equals the 50-digit position at every "
                "registered band point",
            )
            margin = min(abs(bp.t - th.t_lo), abs(bp.t - th.t_hi))
            claim(
                "BP-POSITION-MARGIN",
                margin > mpf("0.1"),
                "every registered band point lies more than 0.1 K from a domain end (its position "
                "cannot turn on rounding)",
            )
            if prev_t is not None:
                claim(
                    "BP-MONOTONE",
                    bp.t >= prev_t - mpf("1e-40"),
                    "T(beta) is non-decreasing along each registered feed's betas (to the "
                    "generator's 1e-40; one flowing component gives T_sat at every beta)",
                )
            prev_t = bp.t
            point: dict[str, Any] = {"beta": beta, "position": bp.position}
            point["iterations_measured"] = b64.iterations
            if bp.position == "inside":
                ft = abs(b64.t - float(bp.t))
                fx = max(abs(b64.x[i] - float(bp.x[i])) for i in range(th.n))
                fk = max(abs(math.exp(b64.lnk[i]) / float(bp.k[i]) - 1.0) for i in range(th.n))
                floor_t, floor_x, floor_k = max(floor_t, ft), max(floor_x, fx), max(floor_k, fk)
                # A06: the returned point's own fixed-point rows with the returned K (K^m) and x
                tot_n = sum(n)
                z64 = [v / tot_n for v in n]
                k64 = [math.exp(e) for e in b64.lnk]
                d64 = [1.0 + beta * (k64[i] - 1.0) for i in range(th.n)]
                act64 = [i for i in range(th.n) if z64[i] > 0.0]
                r_x = max(abs(b64.x[i] * d64[i] - z64[i]) for i in act64)
                r_g = abs(sum(z64[i] * (k64[i] - 1.0) / d64[i] for i in act64))
                floor_res = max(floor_res, r_x, r_g)
                point.update(
                    {
                        "T": nstr(bp.t),
                        "x": vec(bp.x),
                        "K": vec(bp.k),
                        "y": vec([bp.k[i] * bp.x[i] for i in range(th.n)]),
                    }
                )
                if beta == 1.0:
                    # G3: the provider's liquid trial at (n, T_d) has |tm| ~ 0; its floor is the
                    # 50-digit tm* at the transcription's T_d plus S10's FLOOR-TM (1.78e-14)
                    nn_ = [mpf(v) for v in n]
                    z_ = [v / sum(nn_) for v in nn_]
                    w_ = liquid_trial_mp(th, z_, p, mpf(b64.t), bp.x)
                    floor_tm = max(floor_tm, float(abs(1 - sum(w_))) + 1.78e-14)
            worst_it = max(worst_it, b64.iterations)
            exact_one = beta == 0.0 or set_name == "ideal" or sum(1 for v in n if v > 0) == 1
            if exact_one:
                claim(
                    "BP-ONE-ITERATION",
                    b64.iterations == 1,
                    "beta = 0, the ideal limit and one flowing component take exactly one "
                    "iteration in the transcription (S10C-spec §5.1)",
                )
            point["iterations_expected"] = 1 if exact_one else f"<= {TOL_BP_ITER}"
            entry["points"].append(point)
        bands[sid] = entry
    # MB1 (the stop 1e5 x looser, 1e-8) and MB2 (no composition iteration: one step from x = z)
    mb1 = mb1x = mb2 = mb3 = 0.0
    for _sid, set_name, n, p, betas, _why in BAND_STATES:
        if set_name != "real":
            continue
        th = sets[set_name]
        for beta in betas:
            if beta == 0.0:
                continue
            bp, b64 = band_point(th, n, p, beta)
            loose = band_point64(th, n, p, beta, delta=1e-8)
            one = band_point64(th, n, p, beta, cap=1)
            mb1 = max(mb1, abs(loose.t - float(bp.t)))
            mb1x = max(mb1x, max(abs(loose.x[i] - float(bp.x[i])) for i in range(th.n)))
            mb2 = max(mb2, abs(one.t - float(bp.t)))
            # MB3: k_values from the feed composition instead of the liquid (A06's rows)
            tot_n = sum(n)
            z64 = [v / tot_n for v in n]
            kz = [math.exp(e) for e in th.lnk64(b64.t, p, z64)]
            mb3 = max(
                mb3,
                max(
                    abs(b64.x[i] * (1.0 + beta * (kz[i] - 1.0)) - z64[i])
                    for i in range(th.n)
                    if z64[i] > 0.0
                ),
            )
    claim(
        "MB1",
        mb1 >= MARGIN * TOL_BP_T,
        f"mutation MB1 (DELTA_BETA = 1e-8) moves a registered real-record band point's T by "
        f"{mb1:.3g} K >= {MARGIN}x TOL_BP_T: the tolerance resolves the registered stop",
    )
    claim(
        "MB1-X",
        mb1x >= MARGIN * TOL_BP_X,
        f"mutation MB1 moves a registered band point's x by {mb1x:.3g} >= {MARGIN}x TOL_BP_X",
    )
    claim(
        "MB3",
        mb3 >= 1e3 * TOL_BP_RES,
        f"mutation MB3 (k_values at the feed composition) leaves A06's rows at {mb3:.3g} >= 1e3 x "
        f"TOL_BP_RES at a registered point",
    )
    claim(
        "MB2",
        mb2 >= 1e6 * TOL_BP_T,
        f"mutation MB2 (K frozen at the feed composition: one step) moves a registered band "
        f"point's "
        f"T by {mb2:.3g} K >= 1e6 x TOL_BP_T",
    )
    doc["band_point_mutations"] = {
        "MB1_stop_1e-8_max_dT": g3(mb1),
        "MB1_stop_1e-8_max_dx": g3(mb1x),
        "MB2_one_step_max_dT": g3(mb2),
        "MB3_feed_K_rows": g3(mb3),
    }
    claim(
        "BP-ITER",
        worst_it <= TOL_BP_ITER,
        f"the transcription's iterations at every registered band point are <= {TOL_BP_ITER} "
        f"(worst {worst_it})",
    )
    claim(
        "BP-TOL-T",
        TOL_BP_T >= MARGIN * floor_t,
        f"TOL_BP_T = {TOL_BP_T} K is >= {MARGIN}x the measured floor {floor_t:.3g} K",
    )
    claim(
        "BP-TOL-X",
        TOL_BP_X >= MARGIN * floor_x,
        f"TOL_BP_X = {TOL_BP_X} is >= {MARGIN}x the measured floor {floor_x:.3g}",
    )
    claim(
        "BP-TOL-RES",
        TOL_BP_RES >= MARGIN * floor_res,
        f"TOL_BP_RES = {TOL_BP_RES} is >= {MARGIN}x the floor {floor_res:.3g} of the returned band "
        f"points' fixed-point rows |x_i D_i(K^m) - z_i| and |sum z_i (K^m_i - 1)/D_i|",
    )
    claim(
        "BP-TOL-TM",
        TOL_TM_DEW >= MARGIN * floor_tm,
        f"TOL_TM_DEW = {TOL_TM_DEW} is >= {MARGIN}x the floor {floor_tm:.3g} of |tm| at the "
        f"band point beta = 1 (50-digit tm* at the transcription's T_d + S10's FLOOR-TM)",
    )
    claim(
        "BP-TOL-K",
        TOL_BP_K >= MARGIN * floor_k,
        f"TOL_BP_K = {TOL_BP_K} (relative) is >= {MARGIN}x the measured floor {floor_k:.3g}",
    )
    # The ideal limit against the closed forms (Raoult): sum z P_sat = P, sum z / P_sat = 1/P.
    ideal = sets["ideal"]
    z_id = [mpf(v) / 2 for v in (0.6, 0.8, 0.6)]
    tb_id = newton(
        lambda v: [sum(z_id[i] * mp.exp(ideal.m.lnpsat(i, v[0])) for i in range(3)) / P_ATM - 1],
        [mpf(347)],
    )[0]
    td_id = newton(
        lambda v: [sum(z_id[i] / mp.exp(ideal.m.lnpsat(i, v[0])) for i in range(3)) * P_ATM - 1],
        [mpf(352)],
    )[0]
    bp_b = band_point_mp(ideal, (0.6, 0.8, 0.6), P_ATM, 0.0, [tb_id, *z_id])
    bp_d = band_point(ideal, (0.6, 0.8, 0.6), P_ATM, 1.0)[0]
    claim(
        "IDEAL-CLOSED-FORM",
        abs(bp_b.t - tb_id) < mpf("1e-40") and abs(bp_d.t - td_id) < mpf("1e-40"),
        "with Lambda = 1 the band points at beta = 0 and 1 equal Raoult's closed forms "
        "sum z_i P_i^sat(T) = P and sum z_i / P_i^sat(T) = 1/P",
    )
    bands["BP-I01"]["closed_forms"] = {"T_bubble": nstr(tb_id), "T_dew": nstr(td_id)}
    doc["band_points"] = bands

    # -- T2 envelope checks
    theorems: dict[str, Any] = {"T2": {}, "T3_T5": {}}
    b1r = band_point(real, (0.0, 0.5, 0.5), P_ATM, 1.0)[0]
    theorems["T2"]["real-(0,0.5,0.5)"] = envelope_check(
        real, (0.0, 0.5, 0.5), P_ATM, b1r.t + mpf("0.5"), b1r.x, "real"
    )
    b1v = band_point(ver, (0.6, 0.8, 0.6), P_ATM, 1.0)[0]
    theorems["T2"]["verification-(0.6,0.8,0.6)"] = envelope_check(
        ver, (0.6, 0.8, 0.6), P_ATM, b1v.t - mpf("0.5"), b1v.x, "verification"
    )

    # -- G4: PH targets
    phs: dict[str, Any] = {}
    floor_pt = floor_pb = floor_pf = mp1 = 0.0
    for pid, set_name, n, p, how, why in PH_TARGETS:
        th = sets[set_name]
        nn = [mpf(v) for v in n]
        tot = sum(nn)
        kind = how[0]
        entry = {"records": set_name, "n": list(n), "P": p, "why": why}
        end_h = None
        expected: dict[str, Any]
        if kind in ("L", "V", "L-", "V+"):
            t0 = mpf(how[1])
            hval = th.hl(nn, t0) if kind in ("L", "L-") else th.hv(nn, t0)
            if kind == "L-":
                hval -= mpf(how[2])
            if kind == "V+":
                hval += mpf(how[2])
            target = exact_double(hval)
            entry["H_target_built_from"] = (
                f"Hdot^{'L' if kind[0] == 'L' else 'V'}(n, {how[1]} K)"
                + (f" {'-' if kind == 'L-' else '+'} {how[2]} W" if len(how) > 2 else "")
            )
        elif kind == "B":
            bp, _ = band_point(th, n, p, how[1])
            sp0 = split_from(th, n, p, bp.t, mpf(how[1]), bp.x)
            target = exact_double(sp0.h)
            entry["H_target_built_from"] = f"Hdot of the constant-beta split at beta = {how[1]}"
        elif kind == "S":
            c = [i for i in range(th.n) if n[i] > 0][0]
            ts = t_sat_mp(th, c, p, 373.0)
            beta = mpf(how[1])
            target = exact_double((1 - beta) * th.hl(nn, ts) + beta * th.hv(nn, ts))
            entry["H_target_built_from"] = f"the lever rule at T_sat with beta = {how[1]}"
        else:  # TP, TP-: the full verification domain for the start (no clamping at T_min)
            t0 = mpf(how[1])
            beta0, b64 = beta_at_t64(ver, n, p, float(t0))
            act = [i for i in range(th.n) if n[i] > 0]
            sp0 = tp_split_mp(ver, n, p, t0, [mpf(beta0)] + [mpf(b64.x[i]) for i in act])
            hval = sp0.h - (mpf(how[2]) if kind == "TP-" else 0)
            target = exact_double(hval)
            entry["H_target_built_from"] = f"Hdot of the TP split at {how[1]} K" + (
                f" - {how[2]} W" if kind == "TP-" else ""
            )
        entry["H_target"] = target
        # end enthalpies where a domain end lies inside the band (the provider's TP flash there)
        if set_name == "narrowed":
            t_lo = mpf(th.t_lo)
            beta0, b64 = beta_at_t64(ver, n, p, th.t_lo)
            act = [i for i in range(th.n) if n[i] > 0]
            sp_lo = tp_split_mp(ver, n, p, t_lo, [mpf(beta0)] + [mpf(b64.x[i]) for i in act])
            end_h = (float(sp_lo.h), float(th.hv(nn, mpf(th.t_hi))))
            entry["H_lo_TP_flash_at_T_min"] = nstr(sp_lo.h)
        got = ph64(th, list(n), p, target, end_h)
        if kind in ("L-", "V+", "TP-"):
            code = (
                "ph_outside_domain(below)" if kind in ("L-", "TP-") else "ph_outside_domain(above)"
            )
            claim(
                "PH-REFUSAL",
                got == code,
                "the transcription refuses every registered out-of-domain target with its code",
            )
            expected = {"status": "out_of_domain", "code": code}
        else:
            assert isinstance(got, PH64)
            if kind in ("L", "V"):
                phase = "LIQUID" if kind == "L" else "VAPOR"
                t_ref = ph_single_mp(th, n, target, phase, how[1])
                expected = {
                    "status": "ok",
                    "route": "bracket",
                    "phase_signature": phase,
                    "T": nstr(t_ref),
                    "vapor_fraction": 0.0 if phase == "LIQUID" else 1.0,
                    "liquid_n": list(n) if phase == "LIQUID" else [0.0] * th.n,
                    "vapor_n": [0.0] * th.n if phase == "LIQUID" else list(n),
                    "single_phase_flows": "bitwise: the feed in the named phase, zeros in the "
                    "other",
                }
                claim(
                    "PH-T-SHIFT",
                    abs(t_ref - mpf(how[1])) <= mpf("3e-13"),
                    "a single-phase target's answer lies within 3e-13 K of its building "
                    "temperature (the rounding of H* to a double)",
                )
                floor_pt = max(floor_pt, abs(got.t - float(t_ref)))
            elif kind == "S":
                c = [i for i in range(th.n) if n[i] > 0][0]
                ts = t_sat_mp(th, c, p, 373.0)
                hl_, hv_ = th.hl(nn, ts), th.hv(nn, ts)
                beta = (mpf(target) - hl_) / (hv_ - hl_)
                v = [beta * nn[i] for i in range(th.n)]
                lq = [nn[i] - v[i] for i in range(th.n)]
                expected = {
                    "status": "ok",
                    "route": "saturation",
                    "phase_signature": "TWO_PHASE",
                    "T": nstr(ts),
                    "vapor_fraction": nstr(beta),
                    "liquid_n": vec(lq),
                    "vapor_n": vec(v),
                }
                floor_pt = max(floor_pt, abs(got.t - float(ts)))
                floor_pb = max(floor_pb, abs(got.beta - float(beta)))
                floor_pf = max(
                    floor_pf, max(abs(got.v[i] - float(v[i])) for i in range(th.n)) / float(tot)
                )
            else:
                act = [i for i in range(th.n) if n[i] > 0]
                start = [mpf(got.beta), mpf(got.t)] + [mpf(got.lq[i] / sum(got.lq)) for i in act]
                sp = ph_band_mp(th, n, p, target, start)
                expected = {
                    "status": "ok",
                    "route": "band",
                    "phase_signature": "TWO_PHASE",
                    "T": nstr(sp.t),
                    "vapor_fraction": nstr(sp.beta),
                    "liquid_n": vec(sp.lq),
                    "vapor_n": vec(sp.v),
                    "x": vec(sp.x),
                    "y": vec(sp.y),
                }
                floor_pt = max(floor_pt, abs(got.t - float(sp.t)))
                floor_pb = max(floor_pb, abs(got.beta - float(sp.beta)))
                floor_pf = max(
                    floor_pf,
                    max(abs(got.v[i] - float(sp.v[i])) for i in range(th.n)) / float(tot),
                    max(abs(got.lq[i] - float(sp.lq[i])) for i in range(th.n)) / float(tot),
                )
                coarse = ph64(th, list(n), p, target, end_h, width_floor=2.0**-30)
                assert isinstance(coarse, PH64)
                mp1 = max(mp1, abs(coarse.beta - float(sp.beta)))
                if pid in ("PH-2B", "PH-2T", "PH-ID"):
                    theorems["T3_T5"][pid] = theorem_checks(th, n, p, sp, pid)
            claim(
                "PH-ROUTE",
                got.route == expected["route"],
                "the transcription takes the registered route at every registered PH target",
            )
            entry["evaluations_measured"] = got.evaluations
        expected["provider_tp_flash_calls"] = 1 if set_name == "narrowed" else 0
        entry["expected"] = expected
        phs[pid] = entry
    claim(
        "MP1",
        mp1 >= TOL_PH_BETA,
        f"mutation MP1 (the band route's width floor 2^-30 instead of 2^-60) moves a registered "
        f"two-phase answer's beta by {mp1:.3g} >= TOL_PH_BETA",
    )
    doc["ph_mutations"] = {"MP1_width_2^-30_max_dbeta": g3(mp1)}
    claim(
        "PH-TOL-T",
        TOL_PH_T >= MARGIN * floor_pt,
        f"TOL_PH_T = {TOL_PH_T} K is >= {MARGIN}x the measured floor {floor_pt:.3g} K",
    )
    claim(
        "PH-TOL-BETA",
        TOL_PH_BETA >= MARGIN * floor_pb,
        f"TOL_PH_BETA = {TOL_PH_BETA} is >= {MARGIN}x the measured floor {floor_pb:.3g}",
    )
    claim(
        "PH-TOL-FLOW",
        TOL_PH_FLOW_REL >= MARGIN * floor_pf,
        f"TOL_PH_FLOW_REL = {TOL_PH_FLOW_REL} is >= {MARGIN}x the measured floor {floor_pf:.3g}",
    )
    doc["ph_targets"] = phs

    # -- G5: the 13 E-2 states
    e2: dict[str, Any] = {}
    fl_t = fl_b = fl_xy = 0.0
    for k, ((nb, nc), t_state) in enumerate(NEAR_AZEOTROPE, start=1):
        n = (0.0, nb, nc)
        b0, _ = band_point(ver, n, P_ATM, 0.0)
        b1, _ = band_point(ver, n, P_ATM, 1.0)
        claim(
            "E2-INSIDE",
            b0.t < mpf(t_state) < b1.t,
            "every E-2 state's temperature lies strictly inside its band (T_b, T_d)",
        )
        beta0, b64 = beta_at_t64(ver, n, P_ATM, t_state)
        sp_state = tp_split_mp(ver, n, P_ATM, t_state, [mpf(beta0), mpf(b64.x[1]), mpf(b64.x[2])])
        claim(
            "E2-SPLIT",
            0 < sp_state.beta < 1,
            "every E-2 state's 50-digit TP split has 0 < beta < 1",
        )
        target = exact_double(sp_state.h)
        sp = ph_band_mp(
            ver, n, P_ATM, target, [sp_state.beta, sp_state.t, sp_state.x[1], sp_state.x[2]]
        )
        claim(
            "E2-TREF",
            abs(sp.t - mpf(t_state)) < mpf("1e-18"),
            "the PH answer at each E-2 target lies within 1e-18 K of the state's temperature "
            "(H* is rounded to a double)",
        )
        got = ph64(ver, list(n), P_ATM, target)
        assert isinstance(got, PH64)
        claim(
            "E2-ROUTE",
            got.route == "band",
            "the transcription takes the band route at every E-2 state",
        )
        xl = [v / sum(got.lq) for v in got.lq]
        yv = [v / sum(got.v) for v in got.v]
        fl_t = max(fl_t, abs(got.t - float(sp.t)))
        fl_b = max(fl_b, abs(got.beta - float(sp.beta)))
        fl_xy = max(
            fl_xy,
            max(abs(xl[i] - float(sp.x[i])) for i in range(3)),
            max(abs(yv[i] - float(sp.y[i])) for i in range(3)),
        )
        k_near = min(abs(sp.y[i] / sp.x[i] - 1) for i in (1, 2))
        zz = [mpf(v) / sum(mpf(u) for u in n) for v in n]
        dxdb = max(
            abs(zz[i] * (sp.y[i] / sp.x[i] - 1) / (1 + sp.beta * (sp.y[i] / sp.x[i] - 1)) ** 2)
            for i in (1, 2)
        )
        claim(
            "E2-CATCH",
            dxdb * mpf("1e-2") >= MARGIN * TOL_E2_XY,
            "at every E-2 state a vapour fraction wrong by 1e-2 moves x by |dx/dbeta| 1e-2 >= "
            f"{MARGIN}x TOL_E2_XY (|dx_i/dbeta| = z_i |K_i - 1| / D_i^2)",
        )
        e2[f"E2-{k:02d}"] = {
            "n": list(n),
            "T_state": t_state,
            "P": P_ATM,
            "band": {"T_bubble": nstr(b0.t), "T_dew": nstr(b1.t), "width": g3(float(b1.t - b0.t))},
            "H_target": target,
            "expected": {
                "status": "ok",
                "route": "band",
                "phase_signature": "TWO_PHASE",
                "T": nstr(sp.t),
                "vapor_fraction": nstr(sp.beta),
                "x": vec(sp.x),
                "y": vec(sp.y),
                "liquid_n": vec(sp.lq),
                "vapor_n": vec(sp.v),
                "provider_tp_flash_calls": 0,
            },
            "min_abs_K_minus_1": g3(float(k_near)),
            "evaluations_measured": got.evaluations,
        }
        if k == 1:
            theorems["T3_T5"]["E2-01"] = theorem_checks(ver, n, P_ATM, sp, "E2-01")
    claim(
        "E2-TOL-T",
        TOL_E2_T >= MARGIN * fl_t,
        f"TOL_E2_T = {TOL_E2_T} K is >= {MARGIN}x the measured floor {fl_t:.3g} K",
    )
    claim(
        "E2-TOL-BETA",
        TOL_E2_BETA >= MARGIN * fl_b,
        f"TOL_E2_BETA = {TOL_E2_BETA} is >= {MARGIN}x the measured floor {fl_b:.3g}",
    )
    claim(
        "E2-TOL-XY",
        TOL_E2_XY >= MARGIN * fl_xy,
        f"TOL_E2_XY = {TOL_E2_XY} is >= {MARGIN}x the measured floor {fl_xy:.3g}",
    )
    doc["e2_states"] = e2
    doc["theorems"] = theorems
    doc["measured_floors"] = {
        "band_point": {
            "T": g3(floor_t),
            "x": g3(floor_x),
            "K_rel": g3(floor_k),
            "tm_at_dew": g3(floor_tm),
            "fixed_point_rows": g3(floor_res),
            "worst_iterations": worst_it,
        },
        "ph": {"T": g3(floor_pt), "beta": g3(floor_pb), "flow_rel": g3(floor_pf)},
        "e2": {"T": g3(fl_t), "beta": g3(fl_b), "xy": g3(fl_xy)},
    }
    columns = build_columns(doc, real)
    build_blocks(doc, real, columns)
    doc["scan"] = {"real": scan(real), "verification": scan(ver)}
    doc["tolerances"] = tolerance_table(doc)
    doc["generator_claims"] = {"count": len(CLAIMS), "claims": list(CLAIMS)}
    return doc


def jacobian_cs(fun: Callable[[list[Any]], list[Any]], w: Sequence[Any]) -> Any:
    size = len(w)
    h = mpf("1e-60")
    jac = mp.matrix(size, size)
    for k in range(size):
        wp = [mpc(e) for e in w]
        wp[k] += mpc(0, h)
        col = fun(wp)
        for i in range(size):
            jac[i, k] = mp.im(col[i]) / h
    return jac


def derived_image(jinv: Any, tol_rows: Sequence[float], grad: dict[int, Any]) -> float:
    """The first-order image of the kind tolerances on a derived quantity q(w), with
    dq/dw_k = grad[k]: sum_r |sum_k grad_k (J^-1)_kr| tau_r."""
    return float(
        sum(
            abs(sum(g_ * jinv[k, r] for k, g_ in grad.items())) * tol_rows[r]
            for r in range(len(tol_rows))
        )
    )


class ProbeColumn(Column):
    """Mutation M2: the K-block evaluates every stage at the probe n = (1, ..., 1)."""

    def lnk_pair(self, t: Any, pair: Sequence[Any]) -> list[Any]:
        lk = self.th.lnk(t, self.p, [mpf(1)] * self.th.n)
        return [lk[self.a], lk[self.w]]


def build_columns(doc: dict[str, Any], real: Thermo) -> dict[str, dict[str, Any]]:
    """G7: the C-MW and C-EW roots, their per-variable tolerances (10x the first-order image of the
    kind tolerances), the rows-at-root floor, regularity, item 6, the feed, and M2."""
    out: dict[str, Any] = {}
    states: dict[str, dict[str, Any]] = {}
    for name in COLUMN_CASES:
        case = COLUMN_CASES[name]
        col = Column(real, name)
        u = col.solve()
        st = col.unpack(u)
        q_c, q_r = col.duties(st)
        w = col.impl_unknowns(u)
        impl_rows = col.impl_residual(w)
        claim(
            f"COL-{name}-IMPL-ROWS",
            max(abs(e) for e in impl_rows) < mpf("1e-38"),
            f"{name}: the implementation's division-free rows vanish below 1e-38 at the root",
        )
        jac = jacobian_cs(col.impl_residual, w)
        with mp.workdps(30):
            jinv = mp.inverse(jac)
        tol_rows = col.impl_tolerances(w)
        size = len(w)
        image = [sum(abs(jinv[k, r]) * tol_rows[r] for r in range(size)) for k in range(size)]

        # rows at the root rounded to binary64: the floor of each row against its kind tolerance
        kinds: list[float] = []
        for _ in EQ:
            kinds += [FLOW_TOLERANCE] * 2 + [EQUILIBRIUM_TOLERANCE] * 2 + [ENERGY_TOLERANCE]
        kinds += [FLOW_TOLERANCE, FLOW_TOLERANCE, ENERGY_TOLERANCE, FLOW_TOLERANCE]
        floor_rows = max(
            float(8 * mpf(2) ** -53 * sum(abs(jac[r, k] * w[k]) for k in range(size)) / kinds[r])
            for r in range(size)
        )
        claim(
            f"COL-{name}-ROWS-FLOOR",
            ROWS_AT_ROOT * 1.0 >= MARGIN * floor_rows,
            f"{name}: the binary64 floor of every implementation row at the rounded root, "
            f"8 u sum_k |J_rk x_k| = {floor_rows:.3g} tau_kind, is <= ROWS_AT_ROOT/{MARGIN}",
        )
        # regularity (S02's scaling: T columns x 100)
        jq = jacobian_cs(col.residual, u)
        scales = [
            100.0 if (k % 5 == 4 and k < 5 * len(EQ)) or k == 5 * len(EQ) else 1.0
            for k in range(col.size)
        ]
        with mp.workdps(20):
            jm = mp.matrix(
                [[jq[i, k] * scales[k] for k in range(col.size)] for i in range(col.size)]
            )
            sigma = min(mp.svd_r(jm, compute_uv=False))
        claim(
            f"COL-{name}-REGULAR",
            sigma > mpf("1e-4"),
            f"{name}: the root is regular, sigma_min = {mp.nstr(sigma, 3)} > 1e-4 (S02 §9's "
            f"threshold, S02's scaling)",
        )
        # per-stage checks
        stages: dict[str, Any] = {}
        item6_b = item6_d = 0.0
        kmin = mpf(10)
        for s_, j in enumerate(EQ):
            lq, v, t = st["lq"][j], st["v"][j], st["T"][j]
            big_l, big_v = lq[0] + lq[1], v[0] + v[1]
            claim(
                "COL-FLOWS",
                big_l > mpf("0.1") and big_v > mpf("0.1"),
                "every equilibrium stage of C-MW and C-EW carries L, V > 0.1 mol/s (two-phase, "
                "far from S02 §9's 1e-3 floor)",
            )
            x = [lq[0] / big_l, lq[1] / big_l]
            y = [v[0] / big_v, v[1] / big_v]
            lk = col.lnk_pair(t, x)
            k_ = [mp.exp(e) for e in lk]
            dl = [real.m.dlnpsat(col.a, t), real.m.dlnpsat(col.w, t)]
            sb = sum(x[c] * k_[c] * dl[c] for c in range(2))
            sd = sum(y[c] / k_[c] * dl[c] for c in range(2))
            tol_eq = [
                EQUILIBRIUM_TOLERANCE + FLOW_TOLERANCE * float(abs(v[c]) + k_[c] * abs(lq[c]))
                for c in range(2)
            ]
            item6_b = max(item6_b, float(sum(tol_eq) / (big_l * big_v * sb)))
            item6_d = max(
                item6_d, float(sum(tol_eq[c] / k_[c] for c in range(2)) / (big_l * big_v * sd))
            )
            kmin = min(kmin, min(abs(e - 1) for e in k_))
            o = 5 * s_
            stages[str(j)] = {
                "T": nstr(t),
                "liquid_n": vec(col.full(lq)),
                "vapor_n": vec(col.full(v)),
                "x": vec(col.full(x)),
                "y": vec(col.full(y)),
                "tolerance": {
                    "T": g3(MARGIN * float(image[o + 4])),
                    "liquid_n": g3(MARGIN * float(max(image[o], image[o + 1]))),
                    "vapor_n": g3(MARGIN * float(max(image[o + 2], image[o + 3]))),
                },
            }
        claim(
            f"COL-{name}-ITEM6",
            item6_b <= TAU_ITEM6 / 5 and item6_d <= TAU_ITEM6 / 5,
            f"{name}: an iterate within the kind tolerances has |T_j - T_bub(l_j)| <= "
            f"{item6_b:.3g} K and |T_j - T_dew(v_j)| <= {item6_d:.3g} K (first order, S08 §13.4's "
            f"bound): item 6 (1e-4 K) is implied with margin >= 5",
        )
        claim(
            f"COL-{name}-NOT-E2",
            kmin > mpf("1e-3"),
            f"{name}: min over stages and components of |K_i - 1| = {mp.nstr(kmin, 3)} > 1e-3: "
            f"the root is outside the E-2 regime (|K - 1| <~ 1e-4)",
        )
        v2 = st["v"][2]
        big_v2 = v2[0] + v2[1]
        d_rate = (1 - col.phi) * big_v2
        r = [col.phi * e for e in v2]
        dd = [(1 - col.phi) * e for e in v2]
        l_n = st["lq"][N_STAGES]
        b_rate = l_n[0] + l_n[1]
        x_d = v2[0] / big_v2
        x_b = l_n[0] / b_rate
        # closure
        feed = [mpf(e) for e in col.feed]
        comp = max(abs(feed[c] - col.full(dd)[c] - col.full(l_n)[c]) for c in range(3))
        h_d = col.h_pair(dd, st["Tc"], "LIQUID")
        h_b = col.h_pair(l_n, st["T"][N_STAGES], "LIQUID")
        energy = abs(col.h_feed + q_c + q_r - h_d - h_b)
        claim(
            f"COL-{name}-CLOSURE",
            comp < mpf("1e-38") and energy < mpf("1e-33"),
            f"{name}: overall component closure < 1e-38 mol/s and energy closure < 1e-33 W",
        )
        if name == "C-EW":
            xe = mpf(doc["azeotropes"]["real_ethanol_water"]["x_ethanol"])
            claim(
                "COL-C-EW-AZEOTROPE",
                x_d < xe - mpf("0.05"),
                f"C-EW: x_D = {mp.nstr(x_d, 8)} lies below the model azeotrope x_E = "
                f"{mp.nstr(xe, 8)} by more than 0.05 (azeotrope-limited)",
            )
        # the feed: saturated liquid, admitted as LIQUID by the provider's flash (tm_V >= -eps)
        zf = [e / col.f_tot for e in feed]
        tmv = 1 - sum(
            zf[i] * mp.exp(e)
            for i, e in enumerate(real.lnk(mpf(col.t_feed), P_ATM, zf))
            if zf[i] > 0
        )
        claim(
            f"COL-{name}-FEED",
            abs(mpf(col.t_feed) - col.t_bubble_feed) <= mpf(2) ** -44 and abs(tmv) < mpf("1e-13"),
            f"{name}: the feed temperature is the 50-digit bubble temperature rounded to a double "
            f"(|tm_V| = {mp.nstr(abs(tmv), 3)} < 1e-13 << eps_tpd, so the provider's flash "
            f"returns LIQUID and R5 admits it)",
        )
        # derived quantities' images: D = (1 - phi) V_2, B = L_N, x_D = v_2a / V_2, x_B = l_Na / L_N
        o = 5 * len(EQ)
        i_phi = o + 1
        img_d = derived_image(jinv, tol_rows, {2: 1 - col.phi, 3: 1 - col.phi, i_phi: -big_v2})
        img_b = derived_image(jinv, tol_rows, {o - 5: mpf(1), o - 4: mpf(1)})
        img_xd = derived_image(jinv, tol_rows, {2: v2[1] / big_v2**2, 3: -v2[0] / big_v2**2})
        img_xb = derived_image(
            jinv, tol_rows, {o - 5: l_n[1] / b_rate**2, o - 4: -l_n[0] / b_rate**2}
        )
        if name == "C-EW":
            bp_r01 = doc["band_points"]["BP-R01"]["points"][0]["T"]
            claim(
                "COL-C-EW-FEED-BP",
                col.t_feed == bp_r01,
                "C-EW's feed temperature equals BP-R01's beta = 0 temperature bitwise",
            )
        # M2
        probe = ProbeColumn(real, name)
        um = newton(probe.residual, u, tol=mpf("1e-30"))
        sm = probe.unpack(um)
        v2m = sm["v"][2]
        x_dm = v2m[0] / (v2m[0] + v2m[1])
        tol_xd = MARGIN * img_xd
        m2_rows = max(abs(e) for e in probe.impl_residual(w))
        claim(
            f"COL-{name}-M2",
            abs(x_dm - x_d) > mpf("1e-2")
            and abs(x_dm - x_d) > 1000 * tol_xd
            and m2_rows > 1e6 * EQUILIBRIUM_TOLERANCE,
            f"{name}: mutation M2 (K at the probe) moves x_D by {mp.nstr(abs(x_dm - x_d), 3)} "
            f"(> 1e-2 and > 1000x its tolerance) and leaves rows of {mp.nstr(m2_rows, 3)} at the "
            f"registered root (> 1e6 tau_eq)",
        )
        out[name] = {
            "why": case["why"],
            "definition": {
                "provider_records": "real",
                "stage_count": N_STAGES,
                "condenser": "total",
                "reboiler": "partial",
                "equilibrium_stages": f"2..{N_STAGES}",
                "pressures": [P_ATM] * N_STAGES,
                "duties": [None] + [0.0] * (N_STAGES - 2) + [None],
                "condenser_spec": {"kind": "reflux_ratio", "value": float(case["reflux_ratio"])},
                "reboiler_spec": {"kind": "bottoms_rate", "value": float(case["bottoms_rate"])},
                "feed": {
                    "stage": FEED_STAGE,
                    "phase": "LIQUID",
                    "n": list(col.feed),
                    "T": col.t_feed,
                    "P": P_ATM,
                },
            },
            "root": {
                "stages": stages,
                "condenser": {
                    "T": nstr(st["Tc"]),
                    "phi": nstr(col.phi),
                    "reflux_n": vec(col.full(r)),
                    "distillate_n": vec(col.full(dd)),
                    "D": nstr(d_rate),
                    "Q": nstr(q_c),
                    "x_D": nstr(x_d),
                    "tolerance": {
                        "T": g3(MARGIN * float(image[o])),
                        "D": g3(MARGIN * img_d),
                        "x_D": g3(MARGIN * img_xd),
                        "Q": g3(MARGIN * float(image[o + 2])),
                        "reflux_n_and_distillate_n": g3(MARGIN * float(max(image[2], image[3]))),
                    },
                },
                "reboiler": {
                    "Q": nstr(q_r),
                    "B": nstr(b_rate),
                    "x_B": nstr(x_b),
                    "tolerance": {
                        "Q": g3(MARGIN * float(image[o + 3])),
                        "B": g3(MARGIN * img_b),
                        "x_B": g3(MARGIN * img_xb),
                    },
                },
                "feed_bubble_temperature": nstr(col.t_bubble_feed),
            },
            "conditioning": {
                "sigma_min_scaled": g3(float(sigma)),
                "kind_tolerance_image_max": {
                    "T": g3(max(float(image[5 * s_ + 4]) for s_ in range(len(EQ)))),
                    "flow": g3(max(float(image[k]) for k in range(5 * len(EQ)) if k % 5 != 4)),
                },
                "item6_bound": {"bubble": g3(item6_b), "dew": g3(item6_d)},
                "rows_at_root_floor_over_tau_kind": g3(floor_rows),
                "min_abs_K_minus_1": g3(float(kmin)),
            },
            "mutation_M2": {"x_D": nstr(x_dm), "rows_at_registered_root": g3(float(m2_rows))},
        }
        states[name] = {"col": col, "st": st, "r": r, "d": dd}
    doc["columns"] = out
    return states


ROWS_AT_ROOT = 1e-4  # G7: every implementation row at the reference root, as a fraction of tau_kind


def build_blocks(doc: dict[str, Any], real: Thermo, columns: dict[str, dict[str, Any]]) -> None:
    """G6: the FD floors at every registered block state; closed-form values and Jacobians at the
    special states; the dormant convention's numbers; M1's signal."""
    states: list[tuple[str, tuple[float, ...], float, float]] = []
    for name, c in columns.items():
        col, st = c["col"], c["st"]
        for j in EQ:
            states.append(
                (
                    f"{name}-stage-{j}",
                    tuple(float(e) for e in col.full(st["lq"][j])),
                    float(st["T"][j]),
                    P_ATM,
                )
            )
        states.append(
            (
                f"{name}-condenser",
                tuple(float(e) for e in col.full(st["v"][2])),
                float(st["Tc"]),
                P_ATM,
            )
        )
    xe = mpf(doc["azeotropes"]["real_ethanol_water"]["x_ethanol"])
    te = mpf(doc["azeotropes"]["real_ethanol_water"]["T"])
    az = (0.0, exact_double(mpf("1.5") * xe), exact_double(mpf("1.5") * (1 - xe)))
    special = [(sid, n, t, p, why) for sid, n, t, p, why in BLOCK_STATES]
    special.append(
        (
            "G6-AZ",
            az,
            exact_double(te),
            P_ATM,
            "the model azeotrope's liquid (ethanol-water, n_tot = 1.5) at its boiling point",
        )
    )
    fd_listed = [{"id": sid, "n": list(n), "T": t, "P": p} for sid, n, t, p in states]
    fd_listed += [
        {"id": s_[0], "n": list(s_[1]), "T": s_[2], "P": s_[3], "why": s_[4]} for s_ in special
    ]
    floors = {"K": 0.0, "H_LIQUID": 0.0, "H_VAPOR": 0.0}
    m1 = 1.0
    for sid, n, t, p in states + [(s_[0], s_[1], s_[2], s_[3]) for s_ in special]:
        e = fd_errors(real, n, t, p)
        for k in floors:
            floors[k] = max(floors[k], e[k])
        if sid.startswith("C-"):
            m1 = min(m1, m1_signal(real, n, t, p))
    claim(
        "FD-TOL",
        TOL_FD >= MARGIN * max(floors.values()),
        f"TOL_FD = {TOL_FD} is >= {MARGIN}x the measured FD floor {max(floors.values()):.3g} "
        f"over every registered block state",
    )
    claim(
        "M1-SIGNAL",
        m1 >= 1e-2,
        f"at every C-MW and C-EW stage the K-block has an n-entry with |J| / max(|J|, s) >= "
        f"{m1:.3g} >= 1e-2: M1 shows a relative error >= 1e-2 >> TOL_FD",
    )
    special_out: dict[str, Any] = {}
    picks = [(f"{name}-stage-{j}", "") for name in columns for j in (2, FEED_STAGE, N_STAGES)]
    pick_ids = {p_[0] for p_ in picks} | {f"{name}-condenser" for name in columns}
    for sid, n, t, p in states:
        if sid in pick_ids:
            special.append(
                (
                    sid,
                    n,
                    t,
                    p,
                    "a registered column stage (top, feed, bottom) or the "
                    "condenser's K-block input",
                )
            )
    value_floor = 0.0
    for sid, n, t, p, why in special:
        kb = k_block_mp(real, n, t, p)
        hl_ = h_block_mp(real, n, t, p, "LIQUID")
        hv_ = h_block_mp(real, n, t, p, "VAPOR")
        value_floor = max(value_floor, block_value_floor(real, n, t, p, kb, hl_, hv_))
        special_out[sid] = {
            "n": list(n),
            "T": t,
            "P": p,
            "why": why,
            "K_block": {"values": vec(kb["values"]), "jacobian": [vec(r) for r in kb["jacobian"]]},
            "H_block_LIQUID": {"value": nstr(hl_["value"]), "jacobian": vec(hl_["jacobian"])},
            "H_block_VAPOR": {"value": nstr(hv_["value"]), "jacobian": vec(hv_["jacobian"])},
        }
    claim(
        "BLOCK-VALUE-TOL",
        TOL_VALUE >= MARGIN * value_floor,
        f"TOL_VALUE = {TOL_VALUE} is >= {MARGIN}x the binary64 floor {value_floor:.3g} of the "
        f"block values and Jacobians at the closed-form states (S10 §7.2's scales; H's x n_tot)",
    )
    # the dormant convention at (350 K, 101325 Pa)
    probe = k_block_mp(real, (1.0, 1.0, 1.0), 350.0, P_ATM)
    dormant = {
        "T": 350.0,
        "P": P_ATM,
        "K_block_at_probe": {
            "values": vec(probe["values"]),
            "T_column": vec([r[3] for r in probe["jacobian"]]),
            "P_column": vec([r[4] for r in probe["jacobian"]]),
            "n_columns": "exactly 0.0 (stored)",
        },
        "H_block_dH_dn_LIQUID": vec([real.m.h0l(i, mpf(350)) for i in range(3)]),
        "H_block_dH_dn_VAPOR": vec([real.m.h_ig(i, mpf(350)) for i in range(3)]),
        "H_block_value_and_T_P_columns": "exactly 0.0",
    }
    doc["blocks"] = {
        "fd_states": fd_listed,
        "stencils": {
            "T, P": "central, h = 1e-6 |u|",
            "flow u > 0": "central, h = min(1e-6 max(u, 1), u/2)",
            "flow u = 0": "one-sided second order (-3 f(u) + 4 f(u + h) - f(u + 2h)) / (2h), "
            "h = 1e-6",
            "relative error": "|FD - J| / max(|J|, s); s = 1/n_tot (dlnK/dn), 1e-2 1/K (dlnK/dT), "
            "1/P (dlnK/dP), 1e3 J/mol (dH/dn), 10 n_tot W/K (dH/dT); dH/dP exactly 0.0",
        },
        "fd_floor_measured": {k: g3(v) for k, v in floors.items()},
        "closed_form_floor_measured": g3(value_floor),
        "closed_form_scales": "values: 1 (lnK), 1e3 n_tot J/s (H); Jacobians: 1/n_tot (dlnK/dn), "
        "1e-2 1/K (dlnK/dT), 1/P (dlnK/dP), 1e3 J/mol (dH/dn), 10 n_tot W/K (dH/dT); dH/dP "
        "exactly 0.0",
        "m1_signal_min": g3(m1),
        "closed_form_states": special_out,
        "dormant": dormant,
    }


def tolerance_table(doc: dict[str, Any]) -> dict[str, Any]:
    mf = doc["measured_floors"]
    return {
        "G3": {
            "T": TOL_BP_T,
            "x": TOL_BP_X,
            "K_rel": TOL_BP_K,
            "iterations": TOL_BP_ITER,
            "tm_at_dew": TOL_TM_DEW,
            "fixed_point_rows": TOL_BP_RES,
            "floors": mf["band_point"],
        },
        "G4": {
            "T": TOL_PH_T,
            "vapor_fraction": TOL_PH_BETA,
            "flow_rel_n_tot": TOL_PH_FLOW_REL,
            "floors": mf["ph"],
        },
        "G5": {"T": TOL_E2_T, "vapor_fraction": TOL_E2_BETA, "x_y": TOL_E2_XY, "floors": mf["e2"]},
        "G6": {
            "fd_rel": TOL_FD,
            "closed_form": f"S10 §7.2: |impl - ref| <= {TOL_VALUE} max(|ref|, s)",
            "floor": doc["blocks"]["fd_floor_measured"],
        },
        "G7": {
            "state": "per variable: 10x the first-order image of the kind tolerances "
            "(columns.<case>.root.*.tolerance)",
            "rows_at_root_fraction_of_tau_kind": ROWS_AT_ROOT,
            "item6": TAU_ITEM6,
        },
    }


def dump_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False, width=120, allow_unicode=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--emit", action="store_true")
    args = ap.parse_args()
    text = dump_yaml(build())
    if args.emit:
        OUT_YAML.parent.mkdir(parents=True, exist_ok=True)
        OUT_YAML.write_text(text, encoding="utf-8")
        print(f"wrote {OUT_YAML.relative_to(ROOT)}; {len(CLAIMS)} claims hold")
        return 0
    ok = OUT_YAML.exists() and OUT_YAML.read_text(encoding="utf-8") == text
    print(f"{len(CLAIMS)} claims hold; reference_values.yaml {'matches' if ok else 'DIFFERS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
