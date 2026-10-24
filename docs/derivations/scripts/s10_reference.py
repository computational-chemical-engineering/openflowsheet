"""Closed-form reference generator for S10: the gamma-phi method `wilson-ig-v1` (ADR 0047).

Normative text: ``docs/derivations/S10-spec.md``. Input:
``benchmarks/s10/verification-records.yaml`` (three SYNTHETIC components; spec section 6).
Output: ``benchmarks/s10/reference_values.yaml``.

It imports nothing from ``openflowsheet`` or ``benchmarks``: the numbers it emits are the
expectations the S10 tests judge the implementation against, so they must not come from it. Four
classes of value, labelled as such in the YAML (the convention of ``m01_reference.py``):

* ``closed_form`` -- expectations, mpmath at 50 significant digits, written to 20. Two-phase
  flash answers are solved here by Newton's method on the equilibrium equations, not by the
  successive substitution the implementation is told to use (spec section 5), so the expectation
  does not share the implementation's algorithm.
* ``tolerances`` -- every tolerance the spec states, with the terms it is built from.
* ``measured`` -- the closed forms rerun in 53-bit arithmetic (a transcription in this file, never
  the implementation), used only to argue tolerances. Never an expectation.
* ``generator_claims`` -- every statement the specification makes about its own numbers,
  re-derived on every run. The script refuses to emit when one fails.

Run from the repository root::

    python docs/derivations/scripts/s10_reference.py --check
    python docs/derivations/scripts/s10_reference.py --emit

``--emit`` writes the YAML byte-reproducibly; ``--check`` regenerates it in memory and fails
unless it equals the committed file. Dependencies: Python 3.11+, mpmath, PyYAML.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from mpmath import mp, mpf

mp.dps = 50

ROOT = Path(__file__).resolve().parents[3]
RECORDS_YAML = ROOT / "benchmarks" / "s10" / "verification-records.yaml"
OUT_YAML = ROOT / "benchmarks" / "s10" / "reference_values.yaml"

R = mpf("8.31446261815324")  # J/(mol K), exact in the 2019 SI
T0 = mpf("298.15")
THETA_UNIT = mpf(1000)
P_ATM = 101325.0
EPS64 = 2.0**-52  # binary64 machine epsilon

# The method's registered numerical constants (spec section 5.6; ADR 0047 D6). The implementation
# uses exactly these values; the generator re-derives that each sits above its floor.
EPS_TPD = mpf("1e-10")  # stability resolution: a single phase is kept when tm >= -EPS_TPD
DELTA_K = mpf("1e-13")  # two-phase SS stop: max_i |ln K_i' - ln K_i| <= DELTA_K
DELTA_SS = mpf("1e-13")  # liquid-trial SS stop: max_i |ln W_i' - ln W_i| <= DELTA_SS
SS_MAX = 1000  # iteration cap of each SS loop; reaching it is `not_converged` / UNKNOWN
TOL_VALUE = 1e-12  # evaluate_phase values and derivatives, relative to max(|x|, s_q)
TOL_TM = 1e-12  # tangent-plane distances, absolute

ZERO = mpf(0)
NEWTON_TOL = mpf("1e-44")

CLAIMS: list[dict[str, Any]] = []


def claim(cid: str, ok: bool, text: str) -> None:
    CLAIMS.append({"id": cid, "holds": bool(ok), "statement": text})
    if not ok:
        raise SystemExit(f"generator claim {cid} FAILED: {text}")


def nstr(x: Any, digits: int = 20) -> float:
    """A value written to `digits` significant digits (YAML reads it as a float)."""
    x = mpf(x)
    return float(mp.nstr(x, digits, min_fixed=-30, max_fixed=30)) if x != 0 else 0.0


def g3(x: float) -> float:
    """A measured or derived number written to 3 significant digits."""
    return float(f"{x:.3g}") if x != 0 else 0.0


# ============================================================================================
# 1. Records
# ============================================================================================


@dataclass(frozen=True)
class Records:
    ids: tuple[str, ...]
    b: tuple[tuple[float, ...], ...]  # c_p^ig/R = sum_k b_k theta^k
    dhf: tuple[float, ...]  # J/mol, ideal gas at 298.15 K
    psat: tuple[tuple[float, float, float, float], ...]  # a, b, c, d
    lam: tuple[tuple[float, ...], ...]  # Lambda_ij, Lambda_ii = 1
    t_lo: float
    t_hi: float
    p_lo: float
    p_hi: float
    convention: str
    data_set: str
    sha256: str


def load_records(path: Path) -> Records:
    raw = path.read_bytes()
    doc = yaml.safe_load(raw)
    comps = doc["components"]
    ids = tuple(c["id"] for c in comps)
    b, dhf, psat = [], [], []
    for c in comps:
        p = c["parameters"]
        b.append(tuple(float(p[f"ideal_gas_cp_b{k}"]["value"]) for k in range(5)))
        dhf.append(float(p["standard_formation_enthalpy"]["value"]))
        psat.append(tuple(float(p[f"vapour_pressure_{s}"]["value"]) for s in "abcd"))
    n = len(ids)
    lam = [[1.0 if i == j else math.nan for j in range(n)] for i in range(n)]
    for e in doc["wilson_lambda"]:
        lam[ids.index(e["i"])][ids.index(e["j"])] = float(e["value"])
    claim(
        "REC-01",
        all(not math.isnan(v) and v > 0 for row in lam for v in row),
        "every Wilson Lambda_ij of the records is present and strictly positive (the convexity "
        "theorem of spec section 4.1 needs Lambda > 0)",
    )
    dom = doc["domain"]
    return Records(
        ids=ids,
        b=tuple(b),
        dhf=tuple(dhf),
        psat=tuple(psat),  # type: ignore[arg-type]
        lam=tuple(tuple(r) for r in lam),
        t_lo=float(dom["T"][0]),
        t_hi=float(dom["T"][1]),
        p_lo=float(dom["P"][0]),
        p_hi=float(dom["P"][1]),
        convention=doc["reference_convention"],
        data_set=doc["data_set"],
        sha256=hashlib.sha256(raw).hexdigest(),
    )


# ============================================================================================
# 2. The closed forms (spec section 3), in mpmath; `Mut` switches plausible implementation errors
# ============================================================================================


@dataclass(frozen=True)
class Mut:
    """A plausible implementation error, used only by the mutation claims (spec section 7.4)."""

    lam_transposed: bool = False  # Lambda_ji used for Lambda_ij everywhere
    s_transposed: bool = False  # S_i built as sum_j x_j Lambda_ji
    drop_third_term: bool = False  # ln gamma without -sum_k x_k Lambda_ki / S_k (kept the +1)
    drop_psat_d: bool = False
    drop_psat_c: bool = False
    psat_log_t: bool = False  # c ln(T/K) instead of c ln(T/1000 K)
    dhvap_drop_c: bool = False  # latent term with dlnPsat/dT missing c/theta
    latent_dropped: bool = False  # h^L = sum x h^ig
    unprojected: bool = False  # d/dn_j = G_ij / n_tot
    no_ntot: bool = False  # d/dn_j = (G_ij - sum_k x_k G_ik), no 1/n_tot
    dp_sign: bool = False  # d lnphi^L / dP = +1/P
    cp_shift: bool = False  # b_k multiplies theta^(k+1)
    drop_formation: bool = False
    r_rounded: bool = False  # R = 8.314


NOMUT = Mut()


class Model:
    def __init__(self, rec: Records, mut: Mut = NOMUT) -> None:
        self.rec = rec
        self.n = len(rec.ids)
        self.mut = mut
        self.R = mpf("8.314") if mut.r_rounded else R
        lam = [[mpf(v) for v in row] for row in rec.lam]
        if mut.lam_transposed:
            lam = [[lam[j][i] for j in range(self.n)] for i in range(self.n)]
        self.lam = lam
        self.b = [[mpf(v) for v in row] for row in rec.b]
        self.dhf = [mpf(v) for v in rec.dhf]
        self.ps = [[mpf(v) for v in row] for row in rec.psat]

    # ---- pure components ----
    def lnpsat(self, i: int, t: mpf) -> mpf:
        a, b, c, d = self.ps[i]
        th = t / THETA_UNIT
        lt = mp.log(t) if self.mut.psat_log_t else mp.log(th)
        cc = 0 if self.mut.drop_psat_c else c
        dd = 0 if self.mut.drop_psat_d else d
        return a + b / th + cc * lt + dd * th**2

    def dlnpsat(self, i: int, t: mpf) -> mpf:
        a, b, c, d = self.ps[i]
        th = t / THETA_UNIT
        cc = 0 if self.mut.drop_psat_c else c
        dd = 0 if self.mut.drop_psat_d else d
        return (-b / th**2 + cc / th + 2 * dd * th) / THETA_UNIT

    def d2lnpsat(self, i: int, t: mpf) -> mpf:
        a, b, c, d = self.ps[i]
        th = t / THETA_UNIT
        cc = 0 if self.mut.drop_psat_c else c
        dd = 0 if self.mut.drop_psat_d else d
        return (2 * b / th**3 - cc / th**2 + 2 * dd) / THETA_UNIT**2

    def cp_ig(self, i: int, t: mpf) -> mpf:
        th = t / THETA_UNIT
        sh = 1 if self.mut.cp_shift else 0
        return self.R * sum(self.b[i][k] * th ** (k + sh) for k in range(5))

    def h_ig(self, i: int, t: mpf) -> mpf:
        th, th0 = t / THETA_UNIT, T0 / THETA_UNIT
        sh = 1 if self.mut.cp_shift else 0
        integral = sum(
            self.b[i][k] * (th ** (k + 1 + sh) - th0 ** (k + 1 + sh)) / (k + 1 + sh)
            for k in range(5)
        )
        f = 0 if self.mut.drop_formation else self.dhf[i]
        return f + self.R * THETA_UNIT * integral

    def dhvap(self, i: int, t: mpf) -> mpf:
        """Delta h_i(T) = R T^2 dlnPsat/dT: the implied enthalpy of vaporization (spec eq. 3.5)."""
        if self.mut.dhvap_drop_c:
            a, b, c, d = self.ps[i]
            th = t / THETA_UNIT
            return self.R * t * t * (-b / th**2 + 2 * d * th) / THETA_UNIT
        return self.R * t * t * self.dlnpsat(i, t)

    def h0l(self, i: int, t: mpf) -> mpf:
        if self.mut.latent_dropped:
            return self.h_ig(i, t)
        return self.h_ig(i, t) - self.dhvap(i, t)

    def cp0l(self, i: int, t: mpf) -> mpf:
        if self.mut.latent_dropped:
            return self.cp_ig(i, t)
        return self.cp_ig(i, t) - self.R * (
            2 * t * self.dlnpsat(i, t) + t * t * self.d2lnpsat(i, t)
        )

    # ---- Wilson ----
    def s(self, x: Sequence[mpf]) -> list[mpf]:
        n, lam = self.n, self.lam
        if self.mut.s_transposed:
            return [sum(x[j] * lam[j][i] for j in range(n)) for i in range(n)]
        return [sum(x[j] * lam[i][j] for j in range(n)) for i in range(n)]

    def lngamma(self, x: Sequence[mpf]) -> list[mpf]:
        n, lam = self.n, self.lam
        s = self.s(x)
        out = []
        for i in range(n):
            third = (
                0 if self.mut.drop_third_term else sum(x[k] * lam[k][i] / s[k] for k in range(n))
            )
            extra = 1 if self.mut.drop_third_term else 0
            out.append(1 - mp.log(s[i]) - third - extra)
        return out

    def gmat(self, x: Sequence[mpf]) -> list[list[mpf]]:
        """G_ij = d ln gamma_i / d x_j with x free (spec eq. 3.9)."""
        n, lam = self.n, self.lam
        s = self.s(x)
        return [
            [
                -lam[i][j] / s[i]
                - lam[j][i] / s[j]
                + sum(x[k] * lam[k][i] * lam[k][j] / s[k] ** 2 for k in range(n))
                for j in range(n)
            ]
            for i in range(n)
        ]

    def lnk(self, t: mpf, p: mpf, x: Sequence[mpf]) -> list[mpf]:
        lg = self.lngamma(x)
        return [lg[i] + self.lnpsat(i, t) - mp.log(p) for i in range(self.n)]

    # ---- evaluate_phase (spec section 3.5) ----
    def evaluate(self, n: Sequence[float], t: float, p: float, phase: str) -> dict[str, Any]:
        ids = self.rec.ids
        nn = [mpf(v) for v in n]
        tt, pp = mpf(t), mpf(p)
        nt = sum(nn)
        x = [v / nt for v in nn]
        values: dict[str, mpf] = {}
        der: dict[str, dict[str, mpf]] = {}
        if phase == "LIQUID":
            lg = self.lngamma(x)
            g = self.gmat(x)
            for i, c in enumerate(ids):
                values[f"lnphi_{c}"] = lg[i] + self.lnpsat(i, tt) - mp.log(pp)
                row = {"T": self.dlnpsat(i, tt), "P": (1 if self.mut.dp_sign else -1) / pp}
                mean = sum(x[k] * g[i][k] for k in range(self.n))
                for j, cj in enumerate(ids):
                    if self.mut.unprojected:
                        row[f"n_{cj}"] = g[i][j] / nt
                    elif self.mut.no_ntot:
                        row[f"n_{cj}"] = g[i][j] - mean
                    else:
                        row[f"n_{cj}"] = (g[i][j] - mean) / nt
                der[f"lnphi_{c}"] = row
            hi = [self.h0l(i, tt) for i in range(self.n)]
            cpi = [self.cp0l(i, tt) for i in range(self.n)]
        else:
            for c in ids:
                values[f"lnphi_{c}"] = mpf(0)
                der[f"lnphi_{c}"] = {"T": mpf(0), "P": mpf(0), **{f"n_{cj}": mpf(0) for cj in ids}}
            hi = [self.h_ig(i, tt) for i in range(self.n)]
            cpi = [self.cp_ig(i, tt) for i in range(self.n)]
        h = sum(x[i] * hi[i] for i in range(self.n))
        values["h"] = h
        hrow: dict[str, mpf] = {"T": sum(x[i] * cpi[i] for i in range(self.n)), "P": mpf(0)}
        for j, cj in enumerate(ids):
            hrow[f"n_{cj}"] = (hi[j] - h) if self.mut.no_ntot else (hi[j] - h) / nt
        der["h"] = hrow
        return {"values": values, "derivatives": der}


# ============================================================================================
# 3. The binary64 transcription (measured floors only; never an expectation)
# ============================================================================================


class Float64Model:
    def __init__(self, rec: Records) -> None:
        self.rec = rec
        self.n = len(rec.ids)
        self.R = 8.31446261815324

    def lnpsat(self, i: int, t: float) -> float:
        a, b, c, d = self.rec.psat[i]
        th = t / 1000.0
        return a + b / th + c * math.log(th) + d * th * th

    def dlnpsat(self, i: int, t: float) -> float:
        a, b, c, d = self.rec.psat[i]
        th = t / 1000.0
        return (-b / (th * th) + c / th + 2.0 * d * th) / 1000.0

    def d2lnpsat(self, i: int, t: float) -> float:
        a, b, c, d = self.rec.psat[i]
        th = t / 1000.0
        return (2.0 * b / th**3 - c / (th * th) + 2.0 * d) / 1.0e6

    def cp_ig(self, i: int, t: float) -> float:
        th = t / 1000.0
        bb = self.rec.b[i]
        return self.R * (bb[0] + th * (bb[1] + th * (bb[2] + th * (bb[3] + th * bb[4]))))

    def h_ig(self, i: int, t: float) -> float:
        th, th0 = t / 1000.0, 0.29815
        bb = self.rec.b[i]
        integral = sum(bb[k] * (th ** (k + 1) - th0 ** (k + 1)) / (k + 1) for k in range(5))
        return self.rec.dhf[i] + self.R * 1000.0 * integral

    def h0l(self, i: int, t: float) -> float:
        return self.h_ig(i, t) - self.R * t * t * self.dlnpsat(i, t)

    def cp0l(self, i: int, t: float) -> float:
        return self.cp_ig(i, t) - self.R * (
            2.0 * t * self.dlnpsat(i, t) + t * t * self.d2lnpsat(i, t)
        )

    def s(self, x: Sequence[float]) -> list[float]:
        lam = self.rec.lam
        return [sum(x[j] * lam[i][j] for j in range(self.n)) for i in range(self.n)]

    def lngamma(self, x: Sequence[float]) -> list[float]:
        lam = self.rec.lam
        s = self.s(x)
        return [
            1.0 - math.log(s[i]) - sum(x[k] * lam[k][i] / s[k] for k in range(self.n))
            for i in range(self.n)
        ]

    def gmat(self, x: Sequence[float]) -> list[list[float]]:
        lam = self.rec.lam
        s = self.s(x)
        n = self.n
        return [
            [
                -lam[i][j] / s[i]
                - lam[j][i] / s[j]
                + sum(x[k] * lam[k][i] * lam[k][j] / s[k] ** 2 for k in range(n))
                for j in range(n)
            ]
            for i in range(n)
        ]

    def lnk(self, t: float, p: float, x: Sequence[float]) -> list[float]:
        lg = self.lngamma(x)
        return [lg[i] + self.lnpsat(i, t) - math.log(p) for i in range(self.n)]

    def evaluate(self, n: Sequence[float], t: float, p: float, phase: str) -> dict[str, Any]:
        ids = self.rec.ids
        nt = sum(n)
        x = [v / nt for v in n]
        values: dict[str, float] = {}
        der: dict[str, dict[str, float]] = {}
        if phase == "LIQUID":
            lg = self.lngamma(x)
            g = self.gmat(x)
            for i, c in enumerate(ids):
                values[f"lnphi_{c}"] = lg[i] + self.lnpsat(i, t) - math.log(p)
                mean = sum(x[k] * g[i][k] for k in range(self.n))
                row = {"T": self.dlnpsat(i, t), "P": -1.0 / p}
                for j, cj in enumerate(ids):
                    row[f"n_{cj}"] = (g[i][j] - mean) / nt
                der[f"lnphi_{c}"] = row
            hi = [self.h0l(i, t) for i in range(self.n)]
            cpi = [self.cp0l(i, t) for i in range(self.n)]
        else:
            for c in ids:
                values[f"lnphi_{c}"] = 0.0
                der[f"lnphi_{c}"] = {"T": 0.0, "P": 0.0, **{f"n_{cj}": 0.0 for cj in ids}}
            hi = [self.h_ig(i, t) for i in range(self.n)]
            cpi = [self.cp_ig(i, t) for i in range(self.n)]
        h = sum(x[i] * hi[i] for i in range(self.n))
        values["h"] = h
        hrow = {"T": sum(x[i] * cpi[i] for i in range(self.n)), "P": 0.0}
        for j, cj in enumerate(ids):
            hrow[f"n_{cj}"] = (hi[j] - h) / nt
        der["h"] = hrow
        return {"values": values, "derivatives": der}


# ============================================================================================
# 4. Scales of the evaluate_phase assertions (spec section 7.2)
# ============================================================================================


def scale(prop: str, wrt: str | None, n_tot: float, p: float) -> float:
    """s_q: the floor of the denominator max(|x|, s_q) of the relative tolerance."""
    if prop == "h":
        if wrt is None:
            return 1.0e3  # J/mol
        if wrt == "T":
            return 10.0  # J/(mol K)
        if wrt.startswith("n_"):
            return 1.0e3 / n_tot  # J/mol per mol/s
        return 0.0  # dh/dP: asserted exactly zero
    if wrt is None:
        return 1.0
    if wrt == "T":
        return 1.0e-2  # 1/K
    if wrt == "P":
        return 1.0 / p
    return 1.0 / n_tot


# ============================================================================================
# 5. Flash and stability at 50 digits (spec section 5)
# ============================================================================================


def rachford_rice(z: Sequence[mpf], k: Sequence[mpf], act: Sequence[int]) -> mpf:
    kmax = max(k[i] for i in act)
    kmin = min(k[i] for i in act)
    if not (kmax > 1 > kmin):
        raise ValueError("RR without a sign change")
    lo, hi = 1 / (1 - kmax), 1 / (1 - kmin)

    def f(beta: mpf) -> mpf:
        return sum(z[i] * (k[i] - 1) / (1 + beta * (k[i] - 1)) for i in act)

    for _ in range(260):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def solve_newton(
    fun: Callable[[list[mpf]], list[mpf]], v0: list[mpf], tol: mpf = NEWTON_TOL, it: int = 80
) -> list[mpf]:
    v = list(v0)
    h = mpf("1e-22")
    for _ in range(it):
        f = fun(v)
        if max(abs(e) for e in f) < tol:
            return v
        m = len(v)
        jac = mp.matrix(m, m)
        for j in range(m):
            vp, vm = list(v), list(v)
            vp[j] += h
            vm[j] -= h
            fp, fm = fun(vp), fun(vm)
            for i in range(m):
                jac[i, j] = (fp[i] - fm[i]) / (2 * h)
        step = mp.lu_solve(jac, mp.matrix([-e for e in f]))
        v = [v[i] + step[i] for i in range(m)]
    f = fun(v)
    if max(abs(e) for e in f) >= tol:
        raise SystemExit(f"Newton did not converge: residual {max(abs(e) for e in f)}")
    return v


class Flash:
    def __init__(self, model: Model) -> None:
        self.m = model
        self.n = model.n

    def full(self, act: Sequence[int], vals: Sequence[mpf]) -> list[mpf]:
        out = [mpf(0)] * self.n
        for i, v in zip(act, vals, strict=True):
            out[i] = v
        return out

    def tm_vapour_trial(self, t: mpf, p: mpf, z: Sequence[mpf]) -> mpf:
        lk = self.m.lnk(t, p, z)
        return 1 - sum(z[i] * mp.exp(lk[i]) for i in range(self.n) if z[i] > 0)

    def liquid_trial(
        self, t: mpf, p: mpf, z: Sequence[mpf], start: Sequence[mpf] | None = None
    ) -> dict[str, Any]:
        """Minimise tm over liquid trial phases. Returns W*, tm*, and the SS count to DELTA_SS."""
        act = [i for i in range(self.n) if z[i] > 0]
        if start is None:
            lk = self.m.lnk(t, p, z)
            w_un = {i: z[i] / mp.exp(lk[i]) for i in act}
        else:
            w_un = {i: start[i] for i in act}
        ss_count = None
        for m in range(1, 4 * SS_MAX):
            tot = sum(w_un.values())
            w = self.full(act, [w_un[i] / tot for i in act])
            lk = self.m.lnk(t, p, w)
            new = {i: z[i] / mp.exp(lk[i]) for i in act}
            step = max(abs(mp.log(new[i]) - mp.log(w_un[i])) for i in act)
            w_un = new
            if ss_count is None and step <= DELTA_SS:
                ss_count = m
            if step < mpf("1e-24"):
                break

        def fun(u: list[mpf]) -> list[mpf]:
            ww = [mp.exp(v) for v in u]
            tot = sum(ww)
            w = self.full(act, [v / tot for v in ww])
            lk = self.m.lnk(t, p, w)
            return [u[a] + lk[i] - mp.log(z[i]) for a, i in enumerate(act)]

        u = solve_newton(fun, [mp.log(w_un[i]) for i in act])
        ww = [mp.exp(v) for v in u]
        tot = sum(ww)
        w = self.full(act, [v / tot for v in ww])
        lk = self.m.lnk(t, p, w)
        tm = 1 + sum(ww[a] * (u[a] + lk[i] - mp.log(z[i]) - 1) for a, i in enumerate(act))
        return {"W": self.full(act, ww), "w": w, "tm": tm, "ss_count": ss_count}

    def two_phase(self, t: mpf, p: mpf, z: Sequence[mpf], w_star: Sequence[mpf]) -> dict[str, Any]:
        act = [i for i in range(self.n) if z[i] > 0]
        k = [mp.exp(v) for v in self.m.lnk(t, p, w_star)]
        ss_count = None
        for m in range(1, 4 * SS_MAX):
            beta = rachford_rice(z, k, act)
            x = self.full(act, [z[i] / (1 + beta * (k[i] - 1)) for i in act])
            kn = [mp.exp(v) for v in self.m.lnk(t, p, x)]
            step = max(abs(mp.log(kn[i]) - mp.log(k[i])) for i in act)
            k = kn
            if ss_count is None and step <= DELTA_K:
                ss_count = m
            if step < mpf("1e-24"):
                break
        beta = rachford_rice(z, k, act)
        x0 = [z[i] / (1 + beta * (k[i] - 1)) for i in act]

        def fun(v: list[mpf]) -> list[mpf]:
            xa, b = v[:-1], v[-1]
            x = self.full(act, xa)
            kk = [mp.exp(e) for e in self.m.lnk(t, p, x)]
            res = [x[i] + b * x[i] * (kk[i] - 1) - z[i] for i in act]
            res.append(sum(x[i] * (kk[i] - 1) for i in act))
            return res

        v = solve_newton(fun, [*x0, beta])
        x = self.full(act, v[:-1])
        beta = v[-1]
        kk = [mp.exp(e) for e in self.m.lnk(t, p, x)]
        y = [kk[i] * x[i] for i in range(self.n)]
        return {"beta": beta, "x": x, "y": y, "k": kk, "ss_count": ss_count, "act": act}

    def flash(self, n: Sequence[float], t: float, p: float) -> dict[str, Any]:
        nn = [mpf(v) for v in n]
        tt, pp = mpf(t), mpf(p)
        nt = sum(nn)
        if nt == 0:
            return {"phase": "ZERO_FLOW"}
        z = [v / nt for v in nn]
        tmv = self.tm_vapour_trial(tt, pp, z)
        if tmv >= -EPS_TPD:
            return {"phase": "LIQUID", "beta": mpf(0), "tm_v": tmv, "tm_l": None, "z": z}
        lt = self.liquid_trial(tt, pp, z)
        if lt["tm"] >= -EPS_TPD:
            return {
                "phase": "VAPOR",
                "beta": mpf(1),
                "tm_v": tmv,
                "tm_l": lt["tm"],
                "z": z,
                "lt": lt,
            }
        tp = self.two_phase(tt, pp, z, lt["w"])
        return {"phase": "TWO_PHASE", "tm_v": tmv, "tm_l": lt["tm"], "z": z, "lt": lt, **tp}

    # ---- sensitivities for the flash tolerances (spec section 7.3) ----
    def rr_outputs(
        self, z: Sequence[mpf], lnk_act: Sequence[mpf], act: Sequence[int], nt: mpf
    ) -> list[mpf]:
        k = self.full(act, [mp.exp(v) for v in lnk_act])
        beta = rachford_rice(z, k, act)
        x = [z[i] / (1 + beta * (k[i] - 1)) for i in act]
        y = [k[i] * x[a] for a, i in enumerate(act)]
        nv = [beta * nt * y[a] for a in range(len(act))]
        nl = [(1 - beta) * nt * x[a] for a in range(len(act))]
        return [beta, *x, *y, *nv, *nl]

    def sensitivities(
        self, t: mpf, p: mpf, z: Sequence[mpf], nt: mpf, sol: dict[str, Any]
    ) -> dict[str, Any]:
        act = sol["act"]
        lnk0 = [mp.log(sol["k"][i]) for i in act]
        h = mpf("1e-20")
        na = len(act)
        cols = []
        for j in range(na):
            lp, lm = list(lnk0), list(lnk0)
            lp[j] += h
            lm[j] -= h
            op, om = self.rr_outputs(z, lp, act, nt), self.rr_outputs(z, lm, act, nt)
            cols.append([(op[q] - om[q]) / (2 * h) for q in range(len(op))])
        nq = len(cols[0])
        s_rows = [sum(abs(cols[j][q]) for j in range(na)) for q in range(nq)]
        # SS map Phi(lnK) = ln K(T, P, x(RR(K))); its infinity norm bounds the contraction.
        phi_cols = []
        for j in range(na):
            lp, lm = list(lnk0), list(lnk0)
            lp[j] += h
            lm[j] -= h
            outs = []
            for ll in (lp, lm):
                kk = self.full(act, [mp.exp(v) for v in ll])
                beta = rachford_rice(z, kk, act)
                x = self.full(act, [z[i] / (1 + beta * (kk[i] - 1)) for i in act])
                lk = self.m.lnk(t, p, x)
                outs.append([lk[i] for i in act])
            phi_cols.append([(outs[0][q] - outs[1][q]) / (2 * h) for q in range(na)])
        # absent components: ln K_k = ln gamma_k(x(K)) + ln Psat_k - ln P depends on K only through
        # x
        absent = [i for i in range(self.n) if i not in act]
        kz_rows = {}
        for k_ in absent:
            row = mpf(0)
            for j in range(na):
                lp, lm = list(lnk0), list(lnk0)
                lp[j] += h
                lm[j] -= h
                vals = []
                for ll in (lp, lm):
                    kk = self.full(act, [mp.exp(v) for v in ll])
                    beta = rachford_rice(z, kk, act)
                    x = self.full(act, [z[i] / (1 + beta * (kk[i] - 1)) for i in act])
                    vals.append(self.m.lnk(t, p, x)[k_])
                row += abs((vals[0] - vals[1]) / (2 * h))
            kz_rows[k_] = row
        jphi = mp.matrix(na, na)
        for q in range(na):
            for j in range(na):
                jphi[q, j] = phi_cols[j][q]
        rho = max(abs(ev) for ev in mp.eig(jphi)[0])
        amp = mp.inverse(mp.eye(na) - jphi)
        a_inf = max(sum(abs(amp[q, j]) for j in range(na)) for q in range(na))
        return {"S": s_rows, "rho": rho, "A": a_inf, "S_kzero": kz_rows}


# ============================================================================================
# 6. Helpers: saturation, bubble and dew temperatures, azeotrope
# ============================================================================================


def bisect(f: Callable[[mpf], mpf], lo: mpf, hi: mpf, it: int = 200) -> mpf:
    flo = f(lo)
    for _ in range(it):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def t_sat(model: Model, i: int, p: mpf) -> mpf:
    return bisect(lambda t: model.lnpsat(i, t) - mp.log(p), mpf(250), mpf(500))


def bubble_t(fl: Flash, z: Sequence[mpf], p: mpf, target: mpf = ZERO) -> mpf:
    return bisect(lambda t: fl.tm_vapour_trial(t, p, z) - target, mpf(280), mpf(450), 180)


def dew_t(fl: Flash, z: Sequence[mpf], p: mpf, target: mpf = ZERO) -> mpf:
    return bisect(lambda t: fl.liquid_trial(t, p, z)["tm"] - target, mpf(280), mpf(450), 120)


def azeotrope(model: Model, i: int, j: int, p: mpf, x0: mpf, t0: mpf) -> tuple[mpf, mpf]:
    def fun(v: list[mpf]) -> list[mpf]:
        xi, t = v
        x = [mpf(0)] * model.n
        x[i], x[j] = xi, 1 - xi
        lk = model.lnk(t, p, x)
        return [lk[i], lk[j]]

    xi, t = solve_newton(fun, [x0, t0])
    return xi, t


def relative_volatility_bubble(fl: Flash, i: int, j: int, p: mpf, xi: mpf) -> mpf:
    x = [mpf(0)] * fl.n
    x[i], x[j] = xi, 1 - xi
    t = bubble_t(fl, x, p)
    lk = fl.m.lnk(t, p, x)
    return mp.exp(lk[i] - lk[j])


# ============================================================================================
# 7. Registered states (spec section 7.1)
# ============================================================================================

E_STATES: dict[str, dict[str, Any]] = {
    "E1": {
        "n": [0.6, 1.0, 0.4],
        "T": 350.0,
        "P": 120000.0,
        "why": "ternary interior with n_tot = 2 (the 1/n_tot of the n-derivatives is visible); "
        "every "
        "Wilson term active; three distinct ln phi values",
    },
    "E2": {
        "n": [0.0, 0.7, 0.8],
        "T": 365.0,
        "P": 100000.0,
        "why": "VA absent: ln gamma_VA at infinite dilution and its n_VA-derivative at n_VA = 0 "
        "(no log(0) on the path); the azeotropic pair VB-VC",
    },
    "E3": {
        "n": [0.0, 0.0, 1.5],
        "T": 330.0,
        "P": 80000.0,
        "why": "pure VC: ln gamma_VC vanishes exactly (registered because it vanishes), so "
        "lnphi_VC = ln(P_sat,VC/P); VA and VB at infinite dilution in VC",
    },
    "E4": {
        "n": [1.0e-9, 1.0, 1.0e-7],
        "T": 355.0,
        "P": 150000.0,
        "why": "near-pure VB with traces of VA and VC: cancellation in S_k and in the projected "
        "n-derivatives",
    },
    "E5": {
        "n": [0.5, 0.25, 0.25],
        "T": 300.0,
        "P": 300000.0,
        "why": "domain corner (T_lo, P_hi), inclusive: the provider must answer on the boundary",
    },
    "E6": {
        "n": [0.2, 0.3, 0.5],
        "T": 420.0,
        "P": 50000.0,
        "why": "domain corner (T_hi, P_lo), inclusive; the largest d ln P_sat/dT curvature terms",
    },
}

Z3 = [0.6, 0.8, 0.6]  # the ternary feed of F1-F3, F7, F8, F10, F11 (n_tot = 2)


def round_to(x: mpf, decimals: int) -> float:
    return round(float(x), decimals)


# ============================================================================================
# 8. Build
# ============================================================================================


def sig(entry: dict[str, Any]) -> dict[str, Any]:
    return {k: nstr(v) for k, v in entry.items()}


def build() -> dict[str, Any]:
    CLAIMS.clear()
    rec = load_records(RECORDS_YAML)
    model = Model(rec)
    f64 = Float64Model(rec)
    fl = Flash(model)
    ids = rec.ids
    n = model.n
    patm = mpf(P_ATM)

    claim(
        "REC-02",
        len({rec.lam[i][j] for i in range(n) for j in range(n) if i != j}) == n * (n - 1)
        and min(abs(rec.lam[i][j] - rec.lam[j][i]) for i in range(n) for j in range(n) if i != j)
        >= 0.3,
        "the six off-diagonal Lambda_ij are pairwise distinct and |Lambda_ij - Lambda_ji| >= 0.3, "
        "so a "
        "transposed or permuted index changes every Wilson term",
    )
    claim(
        "REC-03",
        all(v != 0 for row in rec.b for v in row) and all(v != 0 for row in rec.psat for v in row),
        "every ideal-gas c_p coefficient and every vapour-pressure coefficient of the verification "
        "records is nonzero, so a dropped term changes a value",
    )

    # ---- 8.1 pure-component sanity values ----
    pure: dict[str, Any] = {}
    tsat_atm = []
    for i, c in enumerate(ids):
        ts = t_sat(model, i, patm)
        tsat_atm.append(ts)
        t350 = mpf(350)
        pure[c] = {
            "lnpsat_350K": nstr(model.lnpsat(i, t350)),
            "dlnpsat_dT_350K": nstr(model.dlnpsat(i, t350)),
            "d2lnpsat_dT2_350K": nstr(model.d2lnpsat(i, t350)),
            "T_sat_101325Pa": nstr(ts),
            "dhvap_at_T_sat_101325Pa": nstr(model.dhvap(i, ts)),
            "cp_ig_350K": nstr(model.cp_ig(i, t350)),
            "h_ig_298_15K": nstr(model.h_ig(i, T0)),
            "h_ig_350K": nstr(model.h_ig(i, t350)),
            "h0L_350K": nstr(model.h0l(i, t350)),
            "cp0L_350K": nstr(model.cp0l(i, t350)),
        }
        claim(
            f"PURE-{c}-1",
            model.h_ig(i, T0) == mpf(rec.dhf[i]),
            f"h^ig_{c}(298.15 K) equals the record's formation enthalpy exactly (the datum of "
            f"{rec.convention})",
        )
        dmin = min(model.dhvap(i, mpf(t)) for t in range(int(rec.t_lo), int(rec.t_hi) + 1))
        claim(
            f"PURE-{c}-2",
            dmin > 10000,
            f"the implied enthalpy of vaporization of {c} exceeds 10 kJ/mol on the whole domain "
            "(P_sat strictly increasing in T), min "
            f"{float(dmin):.6g} J/mol",
        )
        claim(
            f"PURE-{c}-3",
            rec.t_lo < float(ts) < rec.t_hi,
            f"{c} boils at 101 325 Pa inside the domain ({float(ts):.6f} K)",
        )

    # Gibbs-Helmholtz consistency of the pure liquid (spec eq. 3.6), by a 50-digit central
    # difference.
    for i, c in enumerate(ids):
        worst = mpf(0)
        for t in (rec.t_lo, 350.0, rec.t_hi):
            tt = mpf(t)
            h = mpf("1e-18")
            dd = (model.lnpsat(i, tt + h) - model.lnpsat(i, tt - h)) / (2 * h)
            gh = -tt * tt * R * dd
            worst = max(worst, abs((model.h0l(i, tt) - model.h_ig(i, tt)) - gh) / abs(gh))
        claim(
            f"CONS-{c}",
            worst < mpf("1e-30"),
            f"h0L_{c} - h^ig_{c} = -T^2 d[R ln P_sat]/dT (Gibbs-Helmholtz on mu0L - mu^ig(P0) = "
            f"RT ln(P_sat/P0)) at T_lo, 350 K, T_hi: worst relative {float(worst):.2e}",
        )

    # ---- 8.2 evaluate_phase states ----
    ev: dict[str, Any] = {}
    floors: dict[str, float] = {}
    worst_floor = 0.0
    zero_count = 0
    zero_bad: list[str] = []
    for sid, st in E_STATES.items():
        nst, t, p = st["n"], st["T"], st["P"]
        claim(
            f"DOM-{sid}",
            rec.t_lo <= t <= rec.t_hi and rec.p_lo <= p <= rec.p_hi,
            f"{sid} is inside the closed domain",
        )
        ev[sid] = {"state": {"n": nst, "T": t, "P": p}, "why": st["why"]}
        nt = float(sum(mpf(v) for v in nst))
        for phase in ("LIQUID", "VAPOR"):
            r = model.evaluate(nst, t, p, phase)
            rf = f64.evaluate(nst, t, p, phase)
            ev[sid][phase] = {
                "values": {k: nstr(v) for k, v in r["values"].items()},
                "derivatives": {
                    k: {w: nstr(v) for w, v in row.items()} for k, row in r["derivatives"].items()
                },
            }
            fl_max = 0.0
            for prop, v in r["values"].items():
                s = scale(prop.split("_")[0], None, nt, p)
                if v == 0:
                    continue
                fl_max = max(
                    fl_max, float(abs(mpf(rf["values"][prop]) - v)) / max(float(abs(v)), s)
                )
            for prop, row in r["derivatives"].items():
                for wrt, v in row.items():
                    s = scale(prop.split("_")[0], wrt, nt, p)
                    identity_zero = (phase == "VAPOR" and prop.startswith("lnphi")) or (
                        prop == "h" and wrt == "P"
                    )
                    if identity_zero:
                        claim_ok = v == 0
                        if not claim_ok:
                            zero_bad.append(f"model {sid}.{phase}.d{prop}/d{wrt}")
                        zero_count += 1
                        if rf["derivatives"][prop][wrt] != 0.0:
                            zero_bad.append(f"{sid}.{phase}.d{prop}/d{wrt}")
                        continue
                    fl_max = max(
                        fl_max,
                        float(abs(mpf(rf["derivatives"][prop][wrt]) - v)) / max(float(abs(v)), s),
                    )
            floors[f"{sid}.{phase}"] = g3(fl_max)
            worst_floor = max(worst_floor, fl_max)
    claim(
        "ZERO-ALL",
        not zero_bad and zero_count == 6 * (3 * 5 + 2),
        f"the {zero_count} derivatives that vanish in the model (every VAPOR lnphi derivative and "
        "dh/dP in "
        "both phases, at the six E-states) are exactly zero in the 50-digit closed forms and in a "
        "plain binary64 "
        "transcription; the implementation must return them as 0.0 exactly",
    )
    claim(
        "FLOOR-E",
        worst_floor <= TOL_VALUE / 10,
        "the binary64 transcription's worst scaled error over every E-state value and derivative "
        "is "
        f"{worst_floor:.3g} <= TOL_VALUE/10 = {TOL_VALUE / 10:.0e} (spec section 7.2)",
    )

    # structural zeros at the pure state E3 (registered because they vanish there), nonzero at E1
    d3 = model.evaluate(E_STATES["E3"]["n"], E_STATES["E3"]["T"], E_STATES["E3"]["P"], "LIQUID")[
        "derivatives"
    ]
    d1m = model.evaluate(E_STATES["E1"]["n"], E_STATES["E1"]["T"], E_STATES["E1"]["P"], "LIQUID")[
        "derivatives"
    ]
    struct = (
        [("lnphi_VC", f"n_{c}") for c in ids]
        + [(f"lnphi_{c}", "n_VC") for c in ids]
        + [("h", "n_VC")]
    )
    claim(
        "VAN-02",
        all(d3[a][b] == 0 for a, b in struct)
        and min(abs(d1m[a][b]) * 2 for a, b in struct if a != "h") > mpf("1e-3")
        and abs(d1m["h"]["n_VC"]) > 1,
        "at pure VC (E3) d lnphi_VC/dn_j = 0 (Gibbs-Duhem with x_VC = 1), d lnphi_i/dn_VC = 0 and "
        "dh/dn_VC = 0 "
        "(homogeneity with one flowing component) exactly at 50 digits; at E1 the same entries are "
        "nonzero "
        "(n_tot |d lnphi/dn| > 1e-3, |dh/dn_VC| > 1 J/mol per mol/s)",
    )

    # vanishing and non-vanishing (rule 3): ln gamma_VC = 0 at E3, nonzero at E1
    lg_e3 = model.lngamma([mpf(0), mpf(0), mpf(1)])
    lg_e1 = model.lngamma([mpf(v) / 2 for v in E_STATES["E1"]["n"]])
    claim(
        "VAN-01",
        lg_e3[2] == 0 and min(abs(v) for v in lg_e1) > mpf("1e-3"),
        "ln gamma_VC = 0 exactly for pure VC (E3), and every ln gamma_i at E1 has magnitude > "
        "1e-3, "
        f"min {float(min(abs(v) for v in lg_e1)):.4f}",
    )
    l1 = ev["E1"]["LIQUID"]["values"]
    vals = [l1[f"lnphi_{c}"] for c in ids]
    claim(
        "DIST-01",
        min(abs(vals[a] - vals[b]) for a in range(n) for b in range(a + 1, n)) > 0.05,
        "at E1 the three liquid ln phi values differ pairwise by more than 0.05 (a permuted "
        "component "
        "index is caught)",
    )
    d1 = ev["E1"]["LIQUID"]["derivatives"]
    rows = [tuple(d1[f"lnphi_{c}"][f"n_{cj}"] for cj in ids) for c in ids]
    claim(
        "DIST-02",
        min(
            max(abs(rows[a][k] - rows[b][k]) for k in range(n))
            for a in range(n)
            for b in range(a + 1, n)
        )
        > 0.05,
        "at E1 the three liquid n-derivative rows of ln phi are pairwise distinct by more than "
        "0.05",
    )

    # identities at 50 digits (spec section 3.6)
    worst_gd = worst_sym = worst_hom = worst_row = worst_gsym = worst_ge = mpf(0)
    for _sid, st in E_STATES.items():
        nn = [mpf(v) for v in st["n"]]
        nt = sum(nn)
        x = [v / nt for v in nn]
        g = model.gmat(x)
        r = model.evaluate(st["n"], st["T"], st["P"], "LIQUID")["derivatives"]
        for j, cj in enumerate(ids):
            worst_gd = max(
                worst_gd, abs(sum(x[i] * r[f"lnphi_{ids[i]}"][f"n_{cj}"] for i in range(n))) * nt
            )
            for i, ci in enumerate(ids):
                worst_sym = max(
                    worst_sym, abs(r[f"lnphi_{ci}"][f"n_{cj}"] - r[f"lnphi_{cj}"][f"n_{ci}"]) * nt
                )
                worst_gsym = max(worst_gsym, abs(g[i][j] - g[j][i]))
        for prop in [*(f"lnphi_{c}" for c in ids), "h"]:
            worst_hom = max(
                worst_hom, abs(sum(nn[j] * r[prop][f"n_{cj}"] for j, cj in enumerate(ids)))
            )
        for i in range(n):
            worst_row = max(worst_row, abs(sum(x[k] * g[i][k] for k in range(n)) + 1))
        lg = model.lngamma(x)
        ge = -sum(x[i] * mp.log(model.s(x)[i]) for i in range(n))
        worst_ge = max(worst_ge, abs(sum(x[i] * lg[i] for i in range(n)) - ge))
    tiny = mpf("1e-40")
    claim(
        "ID-GD",
        worst_gd < tiny,
        f"Gibbs-Duhem sum_i x_i d lnphi_i/dn_j = 0 at every E-state ({float(worst_gd):.1e})",
    )
    claim(
        "ID-SYM",
        worst_sym < tiny,
        f"d lnphi_i/dn_j = d lnphi_j/dn_i at every E-state ({float(worst_sym):.1e})",
    )
    claim(
        "ID-HOM",
        worst_hom < mpf("1e-35"),
        f"sum_j n_j dX/dn_j = 0 for every X at every E-state ({float(worst_hom):.1e})",
    )
    claim(
        "ID-ROW",
        worst_row < tiny,
        f"sum_k x_k G_ik = -1 for every i at every E-state ({float(worst_row):.1e})",
    )
    claim("ID-GSYM", worst_gsym < tiny, f"G_ij = G_ji at every E-state ({float(worst_gsym):.1e})")
    claim(
        "ID-GE",
        worst_ge < tiny,
        "sum_i x_i ln gamma_i = -sum_i x_i ln S_i (= g^E/RT) at every E-state "
        f"({float(worst_ge):.1e})",
    )

    # analytic derivatives against 50-digit central differences
    worst_fd = mpf(0)
    for _sid, st in E_STATES.items():
        for phase in ("LIQUID", "VAPOR"):
            base = model.evaluate(st["n"], st["T"], st["P"], phase)
            for wrt in ["T", "P", *(f"n_{c}" for c in ids)]:
                if wrt == "T":
                    hh = mpf("1e-15") * mpf(st["T"])
                elif wrt == "P":
                    hh = mpf("1e-15") * mpf(st["P"])
                else:
                    hh = mpf("1e-15") * sum(mpf(v) for v in st["n"])

                def at(
                    sign: int,
                    wrt: str = wrt,
                    hh: mpf = hh,
                    st: dict[str, Any] = st,
                    phase: str = phase,
                ) -> dict[str, Any]:
                    nn = [mpf(v) for v in st["n"]]
                    t, p = mpf(st["T"]), mpf(st["P"])
                    if wrt == "T":
                        t += sign * hh
                    elif wrt == "P":
                        p += sign * hh
                    else:
                        nn[ids.index(wrt[2:])] += sign * hh
                    return model.evaluate(nn, t, p, phase)  # type: ignore[arg-type]

                plus, minus = at(1), at(-1)
                nt_s = float(sum(mpf(v) for v in st["n"]))
                for prop in base["values"]:
                    fd = (plus["values"][prop] - minus["values"][prop]) / (2 * hh)
                    an = base["derivatives"][prop][wrt]
                    den = max(abs(an), mpf(scale(prop.split("_")[0], wrt, nt_s, st["P"])))
                    if den == 0:
                        worst_fd = max(worst_fd, abs(fd) * 10**30)
                    else:
                        worst_fd = max(worst_fd, abs(fd - an) / den)
    claim(
        "FD-01",
        worst_fd < mpf("1e-24"),
        "every analytic derivative at every E-state and phase equals a 50-digit central difference "
        f"(step 1e-15 relative), |FD - analytic| / max(|analytic|, s_q) = {float(worst_fd):.1e}",
    )

    # mixture Gibbs-Helmholtz (spec eq. 3.11): h^L - sum x h^ig = -T^2 d/dT [R sum x ln(x gamma
    # Psat / P0)]
    worst_mix = mpf(0)
    for _sid, st in E_STATES.items():
        nn = [mpf(v) for v in st["n"]]
        nt = sum(nn)
        x = [v / nt for v in nn]
        tt = mpf(st["T"])
        hh = mpf("1e-18")

        def gl(t: mpf, x: list[mpf] = x) -> mpf:
            lg = model.lngamma(x)
            return R * sum(x[i] * (lg[i] + model.lnpsat(i, t)) for i in range(n) if x[i] > 0)

        lhs = model.evaluate(st["n"], st["T"], st["P"], "LIQUID")["values"]["h"] - sum(
            x[i] * model.h_ig(i, tt) for i in range(n)
        )
        rhs = -tt * tt * (gl(tt + hh) - gl(tt - hh)) / (2 * hh)
        worst_mix = max(worst_mix, abs(lhs - rhs) / abs(rhs))
    claim(
        "CONS-MIX",
        worst_mix < mpf("1e-30"),
        "h^L - sum_i x_i h^ig_i = -T^2 d/dT[(G^L - sum_i x_i mu^ig_i(P0))/T] at every E-state "
        f"(caloric and equilibrium parts from one potential; h^E = 0): {float(worst_mix):.1e}",
    )

    # IDAES 2.13 activity_coeff_prop_pack Wilson, transcribed (spec section 8.2): G_ij = (v_i/v_j)
    # exp(-tau_ij),
    # ln gamma_i = 1 - ln(sum_j x_j G_ji) - sum_j x_j G_ij / sum_k x_k G_kj, mapped with v = 1,
    # tau_ji = -ln Lambda_ij.
    def idaes_lngamma(x: Sequence[mpf], transposed: bool) -> list[mpf]:
        lam = model.lam
        tau = [
            [
                (-mp.log(lam[i][j]) if transposed else -mp.log(lam[j][i])) if i != j else mpf(0)
                for j in range(n)
            ]
            for i in range(n)
        ]
        gg = [[mp.exp(-tau[i][j]) if i != j else mpf(1) for j in range(n)] for i in range(n)]
        out = []
        for i in range(n):
            a = mp.log(sum(x[j] * gg[j][i] for j in range(n)))
            bsum = sum(x[j] * gg[i][j] / sum(x[k] * gg[k][j] for k in range(n)) for j in range(n))
            out.append(1 - a - bsum)
        return out

    worst_map = mpf(0)
    for st in E_STATES.values():
        nn = [mpf(v) for v in st["n"]]
        x = [v / sum(nn) for v in nn]
        ours = model.lngamma(x)
        worst_map = max(
            worst_map, max(abs(a - b) for a, b in zip(ours, idaes_lngamma(x, False), strict=True))
        )
    x1 = [mpf(v) / 2 for v in E_STATES["E1"]["n"]]
    wrong = max(abs(a - b) for a, b in zip(model.lngamma(x1), idaes_lngamma(x1, True), strict=True))
    claim(
        "IDAES-MAP",
        worst_map < tiny and wrong > mpf("1e-2"),
        "IDAES 2.13's Wilson with vol_mol_comp = 1 and tau[j,i] = -ln Lambda_ij reproduces ln "
        "gamma at every "
        f"E-state ({float(worst_map):.1e}); the transposed mapping tau[i,j] = -ln Lambda_ij is off "
        "by "
        f"{float(wrong):.3f} at E1",
    )

    # convexity of the liquid (spec section 4.1): projected Hessian of n g_mix/RT positive definite
    min_eig = mpf(10)
    steps = 20
    for a in range(1, steps):
        for b in range(1, steps - a):
            x = [mpf(a) / steps, mpf(b) / steps, 1 - mpf(a) / steps - mpf(b) / steps]
            g = model.gmat(x)
            m = [[(1 / x[i] if i == j else 0) + g[i][j] for j in range(n)] for i in range(n)]
            # basis of sum d = 0: (1,0,-1), (0,1,-1)
            bvec = [[1, 0, -1], [0, 1, -1]]
            h2 = [
                [
                    sum(bvec[p][i] * m[i][j] * bvec[q][j] for i in range(n) for j in range(n))
                    for q in range(2)
                ]
                for p in range(2)
            ]
            tr = h2[0][0] + h2[1][1]
            det = h2[0][0] * h2[1][1] - h2[0][1] * h2[1][0]
            lam_min = tr / 2 - mp.sqrt(tr * tr / 4 - det)
            min_eig = min(min_eig, lam_min)
    claim(
        "CVX-01",
        min_eig > 0,
        "the projected Hessian of n g_mix/RT of the verification liquid is positive definite on "
        "the "
        f"interior grid of step 0.05 (min eigenvalue {float(min_eig):.4f}); spec section 4.1 "
        "proves it for "
        "every Lambda > 0, this is the executable illustration",
    )

    # ---- 8.3 saturation and azeotrope sanity values ----
    xaz, taz = azeotrope(model, 1, 2, patm, mpf("0.7"), mpf(350))
    claim(
        "AZ-01",
        mpf("0.05") < xaz < mpf("0.95") and taz < tsat_atm[1] and taz < tsat_atm[2],
        f"VB-VC has a minimum-boiling azeotrope at 101 325 Pa: x_VB = {float(xaz):.6f}, T = "
        f"{float(taz):.6f} K, "
        "below both pure boiling points",
    )
    no_az = True
    for i, j in ((0, 1), (0, 2)):
        for k in range(0, 21):
            xi = mpf(k) / 20
            if relative_volatility_bubble(fl, i, j, patm, xi) <= 1:
                no_az = False
    claim(
        "AZ-02",
        no_az,
        "VA-VB and VA-VC have no azeotrope at 101 325 Pa: alpha_VA > 1 along the bubble curve at x "
        "= 0, "
        "0.05, ..., 1",
    )
    sat = {
        "azeotrope_VB_VC_101325Pa": {"x_VB": nstr(xaz), "T": nstr(taz)},
        "T_sat_101325Pa": {c: nstr(tsat_atm[i]) for i, c in enumerate(ids)},
    }

    # ---- 8.4 flash states ----
    z3 = [mpf(v) / 2 for v in Z3]
    tb3, td3 = bubble_t(fl, z3, patm), dew_t(fl, z3, patm)
    nf4 = [0.0, 0.9, 1.1]
    z4 = [mpf(v) / 2 for v in nf4]
    tb4, td4 = bubble_t(fl, z4, patm), dew_t(fl, z4, patm)
    xb5 = round(float(xaz) + 0.04, 6)
    nf5 = [0.0, round(2 * xb5, 6), round(2 * (1 - xb5), 6)]
    z5 = [mpf(v) / sum(mpf(u) for u in nf5) for v in nf5]
    tb5, td5 = bubble_t(fl, z5, patm), dew_t(fl, z5, patm)
    claim(
        "F5-BAND",
        td5 - tb5 > mpf("1e-3"),
        f"the near-azeotrope feed of F5 has a two-phase band {float(td5 - tb5):.6f} K wide at 101 "
        "325 Pa "
        "(> 1e-3 K, so a registered temperature lies inside it)",
    )
    tsb = tsat_atm[1]
    p12 = mpf(120000)
    t7 = float(bubble_t(fl, z3, p12, mpf("-3e-11")))
    t8 = float(bubble_t(fl, z3, p12, mpf("-1e-8")))
    t10 = float(dew_t(fl, z3, p12, mpf("-1e-8")))
    t11 = float(dew_t(fl, z3, p12, mpf("-3e-11")))
    nf12 = [0.0, float(2 * xaz), float(2 * (1 - xaz))]
    f_states: dict[str, dict[str, Any]] = {
        "F1": {
            "n": Z3,
            "T": 320.0,
            "P": 200000.0,
            "why": "subcooled ternary liquid: decided by the closed-form vapour trial alone",
        },
        "F2": {
            "n": Z3,
            "T": 415.0,
            "P": 60000.0,
            "why": "superheated ternary vapour: decided by the liquid-trial search",
        },
        "F3": {
            "n": Z3,
            "T": round_to((tb3 + td3) / 2, 2),
            "P": P_ATM,
            "why": "ternary two-phase interior (T midway between bubble and dew, to 0.01 K)",
        },
        "F4": {
            "n": nf4,
            "T": round_to((tb4 + td4) / 2, 2),
            "P": P_ATM,
            "why": "VB-VC two-phase with VA absent: outlets carry exactly zero VA; K_VA reported "
            "at infinite dilution",
        },
        "F5": {
            "n": nf5,
            "T": round_to((tb5 + td5) / 2, 6),
            "P": P_ATM,
            "why": "VB-VC 0.04 above the azeotrope, inside its narrow band: K_i close to 1, "
            "Rachford-Rice ill-conditioned",
        },
        "F6a": {
            "n": [0.0, 1.0, 0.0],
            "T": round_to(tsb - mpf("0.5"), 2),
            "P": P_ATM,
            "why": "pure VB 0.5 K below saturation: liquid, no special pure-component branch",
        },
        "F6b": {
            "n": [0.0, 1.0, 0.0],
            "T": round_to(tsb + mpf("0.5"), 2),
            "P": P_ATM,
            "why": "pure VB 0.5 K above saturation: vapour, no special pure-component branch",
        },
        "F7": {
            "n": Z3,
            "T": t7,
            "P": 120000.0,
            "why": "bubble side, tm_V = -3e-11 inside the band [-EPS_TPD, 0): kept single-phase "
            "liquid",
        },
        "F8": {
            "n": Z3,
            "T": t8,
            "P": 120000.0,
            "why": "bubble side, tm_V = -1e-8 outside the band: two-phase with a vapour fraction "
            "near 1e-8",
        },
        "F9": {
            "n": [0.0, 0.0, 0.0],
            "T": 350.0,
            "P": 100000.0,
            "why": "dormant feed: ZERO_FLOW, two dormant outlets (ADR 0001 D3.4)",
        },
        "F10": {
            "n": Z3,
            "T": t10,
            "P": 120000.0,
            "why": "dew side, tm_L = -1e-8 outside the band: two-phase with a liquid fraction near "
            "1e-8",
        },
        "F11": {
            "n": Z3,
            "T": t11,
            "P": 120000.0,
            "why": "dew side, tm_L = -3e-11 inside the band: kept single-phase vapour",
        },
        "F12": {
            "n": nf12,
            "T": float(taz),
            "P": P_ATM,
            "why": "the VB-VC azeotrope at its boiling point: both trial distances within roundoff "
            "of 0; the step order makes it LIQUID",
        },
    }
    expected_phase = {
        "F1": "LIQUID",
        "F2": "VAPOR",
        "F3": "TWO_PHASE",
        "F4": "TWO_PHASE",
        "F5": "TWO_PHASE",
        "F6a": "LIQUID",
        "F6b": "VAPOR",
        "F7": "LIQUID",
        "F8": "TWO_PHASE",
        "F9": "ZERO_FLOW",
        "F10": "TWO_PHASE",
        "F11": "VAPOR",
        "F12": "LIQUID",
    }
    flash_out: dict[str, Any] = {}
    measured_flash: dict[str, Any] = {}
    tol_flash: dict[str, Any] = {}
    worst_tm_floor = 0.0
    worst_lnk_floor = 0.0
    ss_trial_max = 0
    ss_two_max = 0
    for sid, st in f_states.items():
        nst, t, p = st["n"], st["T"], st["P"]
        if sid != "F9":
            claim(
                f"DOM-{sid}",
                rec.t_lo <= t <= rec.t_hi and rec.p_lo <= p <= rec.p_hi,
                f"{sid} is inside the closed domain",
            )
        res = fl.flash(nst, t, p)
        claim(
            f"PHASE-{sid}",
            res["phase"] == expected_phase[sid],
            f"{sid} is {expected_phase[sid]} (got {res['phase']})",
        )
        entry: dict[str, Any] = {
            "state": {"n": nst, "T": t, "P": p},
            "why": st["why"],
            "phase_signature": res["phase"],
        }
        if res["phase"] == "ZERO_FLOW":
            entry["vapor_fraction"] = None
            flash_out[sid] = entry
            continue
        nt = sum(mpf(v) for v in nst)
        z = res["z"]
        entry["stability"] = {
            "label": "STABLE_WITHIN_TESTED_SCOPE",
            "tm_vapour_trial": nstr(res["tm_v"]),
            "tm_liquid_trial": None if res["tm_l"] is None else nstr(res["tm_l"]),
        }
        # binary64 floor of tm_V at the state, and of tm_L at the rounded stationary point
        zf = [float(v) for v in z]
        lkf = f64.lnk(t, p, zf)
        tmv_f = 1.0 - sum(zf[i] * math.exp(lkf[i]) for i in range(n) if zf[i] > 0)
        fl_tm = abs(tmv_f - float(res["tm_v"]))
        if res["tm_l"] is not None:
            wf = [float(v) for v in res["lt"]["W"]]
            tot = sum(wf)
            wn = [v / tot for v in wf]
            lkw = f64.lnk(t, p, wn)
            tml_f = 1.0 + sum(
                wf[i] * (math.log(wf[i]) + lkw[i] - math.log(zf[i]) - 1.0)
                for i in range(n)
                if zf[i] > 0
            )
            fl_tm = max(fl_tm, abs(tml_f - float(res["tm_l"])))
            ss_trial_max = max(ss_trial_max, res["lt"]["ss_count"] or 0)
        worst_tm_floor = max(worst_tm_floor, fl_tm)
        measured_flash[sid] = {"tm_floor": g3(fl_tm)}
        if res["phase"] in ("LIQUID", "VAPOR"):
            entry["vapor_fraction"] = 0.0 if res["phase"] == "LIQUID" else 1.0
            entry["outlets"] = (
                "the feed state bitwise in the named phase; the other outlet dormant (zeros, same "
                "T and P)"
            )
            decide = res["tm_v"] if res["phase"] == "LIQUID" else res["tm_l"]
            entry["deciding_tm"] = nstr(decide)
        else:
            act = res["act"]
            sens = fl.sensitivities(mpf(t), mpf(p), z, nt, res)
            rho, a_inf = sens["rho"], sens["A"]
            claim(
                f"SS-{sid}",
                rho < mpf("0.9"),
                f"{sid}: the two-phase SS map converges, spectral radius of dPhi/dlnK = "
                f"{float(rho):.4f} < 0.9 "
                f"(error amplification ||(I - dPhi/dlnK)^-1||_inf = {float(a_inf):.4f})",
            )
            ss_two_max = max(ss_two_max, res["ss_count"] or 0)
            # binary64 floor of ln K at the rounded solution
            xf = [float(v) for v in res["x"]]
            lkx = f64.lnk(t, p, xf)
            fl_lnk = max(abs(lkx[i] - float(mp.log(res["k"][i]))) for i in range(n))
            worst_lnk_floor = max(worst_lnk_floor, fl_lnk)
            labels = [
                "beta",
                *(f"x_{ids[i]}" for i in act),
                *(f"y_{ids[i]}" for i in act),
                *(f"nV_{ids[i]}" for i in act),
                *(f"nL_{ids[i]}" for i in act),
            ]
            base = float(a_inf) * (float(DELTA_K) + fl_lnk)
            vals_q = fl.rr_outputs(z, [mp.log(res["k"][i]) for i in act], act, nt)
            tq = {}
            for q, lab in enumerate(labels):
                s_scale = float(nt) if lab.startswith("n") else 1.0
                tq[lab] = g3(
                    10
                    * (
                        float(sens["S"][q]) * base
                        + 64 * EPS64 * max(abs(float(vals_q[q])), s_scale)
                    )
                )
            tq["k_relative"] = g3(10 * (base + 64 * EPS64))
            for k_, srow in sens["S_kzero"].items():
                tq[f"k_relative_{ids[k_]}"] = g3(10 * (float(srow) * base + 64 * EPS64))
            tol_flash[sid] = {
                "rho": g3(float(rho)),
                "A": g3(float(a_inf)),
                "lnK_floor": g3(fl_lnk),
                "per_output": tq,
            }
            beta = res["beta"]
            entry["vapor_fraction"] = nstr(beta)
            entry["x"] = {c: nstr(res["x"][i]) for i, c in enumerate(ids)}
            entry["y"] = {c: nstr(res["y"][i]) for i, c in enumerate(ids)}
            entry["vapor_n"] = {c: nstr(beta * nt * res["y"][i]) for i, c in enumerate(ids)}
            entry["liquid_n"] = {c: nstr((1 - beta) * nt * res["x"][i]) for i, c in enumerate(ids)}
            entry["k_values"] = {c: nstr(res["k"][i]) for i, c in enumerate(ids)}
            claim(
                f"BETA-{sid}",
                0 < beta < 1,
                f"{sid}: 0 < beta < 1 (beta = {float(beta):.6e})",
            )
            claim(
                f"BAL-{sid}",
                max(
                    abs(beta * nt * res["y"][i] + (1 - beta) * nt * res["x"][i] - mpf(nst[i]))
                    for i in range(n)
                )
                < mpf("1e-40"),
                f"{sid}: the 50-digit outlets close the component balance",
            )
        flash_out[sid] = entry

    claim(
        "FLOOR-TM",
        worst_tm_floor <= TOL_TM / 10,
        f"the binary64 floor of the trial distances over every F-state is {worst_tm_floor:.3g} <= "
        "TOL_TM/10",
    )
    claim(
        "FLOOR-LNK",
        float(DELTA_K) >= 10 * worst_lnk_floor,
        f"DELTA_K = {float(DELTA_K):.0e} is at least 10 x the binary64 floor of ln K at the "
        "two-phase "
        f"solutions ({worst_lnk_floor:.3g})",
    )
    claim(
        "SS-CAP",
        ss_trial_max <= SS_MAX // 10 and ss_two_max <= SS_MAX // 10,
        f"SS needs at most {ss_trial_max} (liquid trial) and {ss_two_max} (two-phase) iterations "
        "at the "
        f"registered states to reach its stop test, <= SS_MAX/10 = {SS_MAX // 10}",
    )
    # band margins: classification never within 10 x TOL_TM of a threshold
    margins = {}
    for sid, e in flash_out.items():
        if "stability" not in e:
            continue
        tv = mpf(e["stability"]["tm_vapour_trial"])
        tl = e["stability"]["tm_liquid_trial"]
        dists = [abs(tv), abs(tv + EPS_TPD)]
        if tl is not None:
            dists += [abs(mpf(tl)), abs(mpf(tl) + EPS_TPD)]
        margins[sid] = g3(float(min(dists)))
    for sid in ("F7", "F11"):
        dec = (
            mpf(flash_out[sid]["deciding_tm"])
            if sid == "F7"
            else mpf(flash_out[sid]["stability"]["tm_liquid_trial"])
        )
        claim(
            f"BAND-{sid}",
            -EPS_TPD + 10 * TOL_TM < dec < -10 * TOL_TM,
            f"{sid}'s deciding distance {float(dec):.4e} lies inside [-EPS_TPD, 0) with 10 x "
            "TOL_TM to spare on both sides",
        )
    for sid in ("F8", "F10"):
        e = flash_out[sid]["stability"]
        dec = mpf(e["tm_vapour_trial"]) if sid == "F8" else mpf(e["tm_liquid_trial"])
        claim(
            f"BAND-{sid}",
            dec < -EPS_TPD - 10 * TOL_TM,
            f"{sid}'s deciding distance {float(dec):.4e} lies below -EPS_TPD by more than 10 x "
            "TOL_TM",
        )
    for sid in ("F1", "F2", "F3", "F4", "F6a", "F6b"):
        claim(
            f"MARGIN-{sid}",
            margins[sid] > 1e-4,
            f"{sid}'s trial distances are at least 1e-4 from 0 and from -EPS_TPD "
            f"({margins[sid]:.3g})",
        )
    e12 = flash_out["F12"]["stability"]
    claim(
        "AZ-F12",
        abs(e12["tm_vapour_trial"]) < 1e-12,
        "at the azeotrope (F12) the vapour-trial distance is within 1e-12 of zero "
        f"({e12['tm_vapour_trial']:.3e}); "
        "step 2 keeps the liquid",
    )
    claim(
        "PURE-01",
        flash_out["F6a"]["phase_signature"] == "LIQUID"
        and flash_out["F6b"]["phase_signature"] == "VAPOR",
        "one flowing component never reaches step 4: F6a is LIQUID, F6b VAPOR",
    )
    # zero component in F4
    claim(
        "ZC-F4",
        flash_out["F4"]["vapor_n"]["VA"] == 0.0
        and flash_out["F4"]["liquid_n"]["VA"] == 0.0
        and flash_out["F4"]["k_values"]["VA"] > 0,
        "F4: both outlets carry exactly zero VA, and K_VA (infinite dilution in the liquid) is "
        "reported and positive",
    )
    # uniqueness of the liquid-trial stationary point (spec section 4.2), multi-start at F2 and F10
    worst_ms = mpf(0)
    for sid in ("F2", "F10"):
        st = f_states[sid]
        nn = [mpf(v) for v in st["n"]]
        z = [v / sum(nn) for v in nn]
        ref = fl.liquid_trial(mpf(st["T"]), mpf(st["P"]), z)
        starts = [
            [mpf(1) / 3] * 3,
            [mpf("0.98"), mpf("0.01"), mpf("0.01")],
            [mpf("0.01"), mpf("0.98"), mpf("0.01")],
            [mpf("0.01"), mpf("0.01"), mpf("0.98")],
        ]
        for s0 in starts:
            other = fl.liquid_trial(mpf(st["T"]), mpf(st["P"]), z, s0)
            worst_ms = max(
                worst_ms, max(abs(a - b) for a, b in zip(other["W"], ref["W"], strict=True))
            )
    claim(
        "CVX-02",
        worst_ms < mpf("1e-35"),
        "the liquid-trial search at F2 and F10 reaches the same stationary point from the Wilson "
        "start, the "
        f"uniform start and three near-pure starts ({float(worst_ms):.1e}): one stationary point, "
        "as strict convexity requires",
    )

    # stability() queries (spec section 5.5)
    queries: dict[str, Any] = {}
    for sid in ("F1", "F2", "F3", "F7", "F11"):
        st = f_states[sid]
        nn = [mpf(v) for v in st["n"]]
        z = [v / sum(nn) for v in nn]
        tv = fl.tm_vapour_trial(mpf(st["T"]), mpf(st["P"]), z)
        tl = fl.liquid_trial(mpf(st["T"]), mpf(st["P"]), z)["tm"]
        queries[sid] = {
            "LIQUID": {
                "label": "STABLE_WITHIN_TESTED_SCOPE" if tv >= -EPS_TPD else "UNSTABLE",
                "tm": nstr(tv),
            },
            "VAPOR": {
                "label": "STABLE_WITHIN_TESTED_SCOPE" if tl >= -EPS_TPD else "UNSTABLE",
                "tm": nstr(tl),
            },
        }
    labels_seen = {q[ph]["label"] for q in queries.values() for ph in ("LIQUID", "VAPOR")}
    claim(
        "STAB-01",
        labels_seen == {"STABLE_WITHIN_TESTED_SCOPE", "UNSTABLE"},
        "the registered stability() queries return both STABLE_WITHIN_TESTED_SCOPE and UNSTABLE "
        "(no "
        "assertion is satisfiable by a constant label)",
    )

    # ---- 8.5 mutation claims (spec section 7.4) ----
    mutations = {
        "M01_lambda_transposed": Mut(lam_transposed=True),
        "M02_S_transposed": Mut(s_transposed=True),
        "M03_third_term_dropped": Mut(drop_third_term=True),
        "M04_psat_d_dropped": Mut(drop_psat_d=True),
        "M05_psat_c_dropped": Mut(drop_psat_c=True),
        "M06_psat_ln_T_not_theta": Mut(psat_log_t=True),
        "M07_latent_without_c": Mut(dhvap_drop_c=True),
        "M08_latent_dropped": Mut(latent_dropped=True),
        "M09_n_derivative_unprojected": Mut(unprojected=True),
        "M10_n_derivative_without_1_over_ntot": Mut(no_ntot=True),
        "M11_dP_sign": Mut(dp_sign=True),
        "M12_cp_index_shift": Mut(cp_shift=True),
        "M13_formation_dropped": Mut(drop_formation=True),
        "M14_R_rounded_8_314": Mut(r_rounded=True),
    }
    mut_out = {}
    for name, mu in mutations.items():
        mm = Model(rec, mu)
        worst = 0.0
        where = ""
        for sid, st in E_STATES.items():
            nt = float(sum(mpf(v) for v in st["n"]))
            for phase in ("LIQUID", "VAPOR"):
                good = model.evaluate(st["n"], st["T"], st["P"], phase)
                bad = mm.evaluate(st["n"], st["T"], st["P"], phase)
                for prop, v in good["values"].items():
                    s = scale(prop.split("_")[0], None, nt, st["P"])
                    rr = float(abs(bad["values"][prop] - v)) / (TOL_VALUE * max(float(abs(v)), s))
                    if rr > worst:
                        worst, where = rr, f"{sid}.{phase}.{prop}"
                for prop, row in good["derivatives"].items():
                    for wrt, v in row.items():
                        s = scale(prop.split("_")[0], wrt, nt, st["P"])
                        den = TOL_VALUE * max(float(abs(v)), s) if (v != 0 or s > 0) else 0.0
                        dv = float(abs(bad["derivatives"][prop][wrt] - v))
                        rr = math.inf if den == 0 and dv > 0 else (dv / den if den else 0.0)
                        if rr > worst:
                            worst, where = rr, f"{sid}.{phase}.d{prop}/d{wrt}"
        mut_out[name] = {"max_ratio_to_tolerance": g3(min(worst, 1e300)), "where": where}
        claim(
            f"MUT-{name[:3]}",
            worst >= 1e3,
            f"mutation {name} moves at least one registered evaluate_phase assertion by >= 1e3 x "
            "its "
            f"tolerance (max {worst:.3g} x, at {where})",
        )
    # flash-level mutation: K evaluated at the vapour composition
    st = f_states["F3"]
    nn = [mpf(v) for v in st["n"]]
    z = [v / sum(nn) for v in nn]
    good = fl.flash(st["n"], st["T"], st["P"])

    # solve x_i(1 + beta(K_i(y) - 1)) = z_i with y = K(y) x: fixed point in (x, beta)
    act = [0, 1, 2]

    def fun_bad(v: list[mpf]) -> list[mpf]:
        xa, b = v[:3], v[3]
        ya = v[4:7]
        kk = [mp.exp(e) for e in model.lnk(mpf(st["T"]), mpf(st["P"]), ya)]
        res = [xa[i] + b * xa[i] * (kk[i] - 1) - z[i] for i in act]
        res += [ya[i] - kk[i] * xa[i] for i in act]
        res.append(sum(ya) - sum(xa))
        return res

    vb = solve_newton(fun_bad, [*good["x"], good["beta"], *good["y"]])
    diff_beta = abs(vb[3] - good["beta"])
    tbeta = tol_flash["F3"]["per_output"]["beta"]
    claim(
        "MUT-F01",
        float(diff_beta) >= 1e3 * tbeta,
        "a flash that evaluates K at the vapour composition moves F3's beta by "
        f"{float(diff_beta):.3e}, >= 1e3 x "
        f"its tolerance {tbeta:.3g}",
    )

    doc: dict[str, Any] = {
        "generator": "docs/derivations/scripts/s10_reference.py",
        "spec": "docs/derivations/S10-spec.md",
        "adr": "docs/adr/0047-s10-liquid-mixture-property-method.md",
        "records": "benchmarks/s10/verification-records.yaml",
        "records_sha256": rec.sha256,
        "data_set": rec.data_set,
        "reference_convention": rec.convention,
        "components": list(ids),
        "domain": {"T": [rec.t_lo, rec.t_hi], "P": [rec.p_lo, rec.p_hi]},
        "method_constants": {
            "R": "8.31446261815324",
            "T0": "298.15",
            "EPS_TPD": float(EPS_TPD),
            "DELTA_K": float(DELTA_K),
            "DELTA_SS": float(DELTA_SS),
            "SS_MAX": SS_MAX,
        },
        "closed_form": {
            "pure": pure,
            "saturation": sat,
            "evaluate_phase": ev,
            "flash": flash_out,
            "stability_queries": queries,
        },
        "tolerances": {
            "evaluate_phase": {
                "rule": "|impl - expected| <= TOL_VALUE * max(|expected|, s_q); exact equality "
                "where expected is 0",
                "TOL_VALUE": TOL_VALUE,
                "s_q": {
                    "h": 1.0e3,
                    "dh/dT": 10.0,
                    "dh/dn_j": "1e3 / n_tot",
                    "dh/dP": "exactly 0",
                    "lnphi": 1.0,
                    "dlnphi/dT": 1.0e-2,
                    "dlnphi/dP": "1 / P",
                    "dlnphi/dn_j": "1 / n_tot",
                },
            },
            "tm": {"rule": "|impl - expected| <= TOL_TM", "TOL_TM": TOL_TM},
            "flash": {
                "rule": "|impl - expected| <= 10 (S_q A (DELTA_K + f_lnK) + 64 eps max(|q|, s_q)); "
                "k_values relative: 10 (A (DELTA_K + f_lnK) + 64 eps); an absent component k: "
                "10 (S_k A (DELTA_K + f_lnK) + 64 eps); A = ||(I - dPhi/dlnK)^-1||_inf",
                "per_state": tol_flash,
            },
        },
        "measured": {
            "binary64_floor_evaluate_phase": floors,
            "binary64_floor_flash": measured_flash,
            "classification_margins": margins,
            "ss_iterations_max": {"liquid_trial": ss_trial_max, "two_phase": ss_two_max},
        },
        "mutations": mut_out,
        "generator_claims": CLAIMS,
    }
    return doc


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
        OUT_YAML.write_text(text, encoding="utf-8")
        print(f"wrote {OUT_YAML.relative_to(ROOT)}; {len(CLAIMS)} claims hold")
        return 0
    ok = OUT_YAML.exists() and OUT_YAML.read_text(encoding="utf-8") == text
    print(f"{len(CLAIMS)} claims hold; reference_values.yaml {'matches' if ok else 'DIFFERS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
