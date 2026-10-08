"""Closed-form reference generator for M01: Peng-Robinson with the light gases vapour-only (ADR 0026), the
C1 component records' derived constants, and the reactor boundary's closed forms and overlay rows (ADR 0027).

Normative text: ``docs/derivations/M01-spec.md``. Inputs: ``benchmarks/m01/components.yaml`` (the records),
``benchmarks/t08/v19/c1-idaes.json`` (the T08 IDAES record, used only to check this script's transcription
of Peng-Robinson against an independent implementation), and, if present,
``benchmarks/m01/reactor-probe.json`` (a *measured* record of the group's reactor; only the section
``derived_from_measured`` reads it, and nothing in it is an expectation for this repository's code).

It imports nothing from ``openflowsheet`` or ``benchmarks``: the numbers it emits are the expectations the
M01 tests judge the implementation against, so they must not come from it. Three classes of value, labelled
as such in the YAML (the convention of ``t05b_reference.py``):

* ``closed_form`` -- expectations, mpmath at 50 significant digits, written to 20.
* ``generator_claims`` -- every statement the specification makes about its own numbers, re-derived on
  every run. The script refuses to emit when one fails.
* ``measured`` -- the same closed forms rerun in 53-bit arithmetic (a transcription, never the
  implementation), used only to argue tolerances. Never an expectation.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/m01_reference.py --check
    python docs/derivations/scripts/m01_reference.py --emit

``--emit`` writes ``benchmarks/m01/reference_values.yaml`` and ``benchmarks/m01/reactor-overlay.json``
byte-reproducibly; ``--check`` regenerates both in memory and fails unless they equal the committed files.
"""

from __future__ import annotations

import argparse
import cmath
import hashlib
import json
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml
from mpmath import mp, mpf

mp.dps = 50

ROOT = Path(__file__).resolve().parents[3]
COMPONENTS_YAML = ROOT / "benchmarks" / "m01" / "components.yaml"
OUT_YAML = ROOT / "benchmarks" / "m01" / "reference_values.yaml"
OVERLAY_JSON = ROOT / "benchmarks" / "m01" / "reactor-overlay.json"
IDAES_RECORD = ROOT / "benchmarks" / "t08" / "v19" / "c1-idaes.json"
PROBE_RECORD = ROOT / "benchmarks" / "m01" / "reactor-probe.json"

ORDER = ("H2", "N2", "NH3", "Ar", "CH4")
LIGHT = (0, 1, 3, 4)
I_NH3 = 2
NU = (-3, -1, 2, 0, 0)  # N2 + 3 H2 -> 2 NH3, in ORDER
REACTIVE = (0, 1, 2)
R = mpf("8.31446261815324")  # J/(mol K), exact in the 2019 SI
OMEGA_A = mpf("0.45724")  # Peng and Robinson (1976), as rounded there and in IDAES 2.13
OMEGA_B = mpf("0.07780")
SQ2 = mp.sqrt(2)
T0 = mpf("298.15")
DOMAIN_T = (mpf(200), mpf(1000))
DOMAIN_P = (mpf("1e4"), mpf("3e7"))
REACTOR_PIN = "6089593464fc9bc2c0a0cb58e30ad5433ece6332"

CLAIMS: list[dict[str, Any]] = []


class Unsupported(Exception):
    """A registered refusal: the code is the reason string the provider must report."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def claim(cid: str, ok: bool, text: str) -> None:
    CLAIMS.append({"id": cid, "holds": bool(ok), "statement": text})
    if not ok:
        raise SystemExit(f"generator claim {cid} FAILED: {text}")


def nstr(x: Any, digits: int = 20) -> float:
    """A value written to `digits` significant digits (YAML reads it as a float)."""
    return float(mp.nstr(mpf(x), digits, min_fixed=-30, max_fixed=30)) if x != 0 else 0.0


def dstr(x: Any, digits: int = 20) -> str:
    return mp.nstr(mpf(x), digits)


# ============================================================================================
# 1. Records
# ============================================================================================


class Comp:
    def __init__(self, rec: dict[str, Any]) -> None:
        p = rec["parameters"]

        def g(name: str) -> mpf:
            return mpf(repr(float(p[name]["value"])))

        self.id = rec["id"]
        self.tc, self.pc, self.om = g("critical_temperature"), g("critical_pressure"), g("acentric_factor")
        self.hf = g("standard_formation_enthalpy")
        self.bk = [g(f"ideal_gas_cp_b{k}") for k in range(5)]
        self.mw = mpf(repr(float(rec["molecular_weight"]["value"])))
        self.elements = dict(rec["elemental_composition"])
        self.kappa = mpf("0.37464") + mpf("1.54226") * self.om - mpf("0.26992") * self.om**2
        self.ac = OMEGA_A * R**2 * self.tc**2 / self.pc
        self.b = OMEGA_B * R * self.tc / self.pc


def load_components() -> list[Comp]:
    doc = yaml.safe_load(COMPONENTS_YAML.read_text(encoding="utf-8"))
    comps = [Comp(r) for r in doc["components"]]
    claim("REC-01", tuple(c.id for c in comps) == ORDER, f"components.yaml lists {ORDER} in that order")
    return comps


def custom_comp(cid: str, tc: float, pc: float, om: float) -> Comp:
    rec = {
        "id": cid,
        "molecular_weight": {"value": 1.0},
        "elemental_composition": {},
        "parameters": {
            "critical_temperature": {"value": tc},
            "critical_pressure": {"value": pc},
            "acentric_factor": {"value": om},
            "standard_formation_enthalpy": {"value": 0.0},
            **{f"ideal_gas_cp_b{k}": {"value": 0.0} for k in range(5)},
        },
    }
    return Comp(rec)


# ============================================================================================
# 2. Peng-Robinson closed forms (spec section 4)
# ============================================================================================


def sqrt_alpha(c: Comp, T: mpf) -> mpf:
    return 1 + c.kappa * (1 - mp.sqrt(T / c.tc))


def a_of(c: Comp, T: mpf) -> mpf:
    return c.ac * sqrt_alpha(c, T) ** 2


def da_of(c: Comp, T: mpf) -> mpf:
    return -c.ac * c.kappa * sqrt_alpha(c, T) / mp.sqrt(T * c.tc)


def cp_ig(c: Comp, T: mpf) -> mpf:
    tau = T / 1000
    return R * sum(c.bk[k] * tau**k for k in range(5))


def h_ig(c: Comp, T: mpf) -> mpf:
    tau, tau0 = T / 1000, T0 / 1000
    return c.hf + R * 1000 * sum(c.bk[k] * (tau ** (k + 1) - tau0 ** (k + 1)) / (k + 1) for k in range(5))


def mixture(comps: Sequence[Comp], T: mpf, P: mpf, y: Sequence[mpf], kij: dict[tuple[int, int], mpf]) -> dict:
    nc = len(comps)
    a = [a_of(c, T) for c in comps]
    da = [da_of(c, T) for c in comps]
    k = [[kij.get((min(i, j), max(i, j)), mpf(0)) if i != j else mpf(0) for j in range(nc)] for i in range(nc)]
    aij = [[mp.sqrt(a[i] * a[j]) * (1 - k[i][j]) for j in range(nc)] for i in range(nc)]
    S = [sum(y[j] * aij[i][j] for j in range(nc)) for i in range(nc)]
    am = sum(y[i] * S[i] for i in range(nc))
    dam = sum(
        y[i] * y[j] * (1 - k[i][j]) * (da[i] * a[j] + a[i] * da[j]) / (2 * mp.sqrt(a[i] * a[j]))
        for i in range(nc)
        for j in range(nc)
    )
    bm = sum(y[i] * comps[i].b for i in range(nc))
    A = am * P / (R * T) ** 2
    B = bm * P / (R * T)
    return {"a": a, "S": S, "am": am, "dam": dam, "bm": bm, "A": A, "B": B, "T": T, "P": P, "y": list(y)}


def cubic_coeffs(A: mpf, B: mpf) -> list[mpf]:
    return [mpf(1), -(1 - B), A - 3 * B**2 - 2 * B, -(A * B - B**2 - B**3)]


def discriminant(A: mpf, B: mpf) -> mpf:
    _, b, c, d = cubic_coeffs(A, B)
    return 18 * b * c * d - 4 * b**3 * d + b**2 * c**2 - 4 * c**3 - 27 * d**2


def real_roots(A: mpf, B: mpf) -> list[mpf]:
    """Real roots Z > B, ascending. Three distinct roots iff the discriminant is positive."""
    disc = discriminant(A, B)
    rs = mp.polyroots(cubic_coeffs(A, B), maxsteps=400, extraprec=400)
    re = sorted(mp.re(r) for r in rs)
    if disc > 0:
        cand = re
    else:  # one real root: the one with the smallest imaginary part
        cand = [mp.re(min(rs, key=lambda r: abs(mp.im(r))))]
    return [z for z in cand if z > B]


def log_term(Z: mpf, B: mpf) -> mpf:
    return mp.log((Z + (1 + SQ2) * B) / (Z + (1 - SQ2) * B))


def ln_phi(comps: Sequence[Comp], m: dict, Z: mpf) -> list[mpf]:
    A, B, am, bm = m["A"], m["B"], m["am"], m["bm"]
    L = log_term(Z, B)
    return [
        comps[i].b / bm * (Z - 1)
        - mp.log(Z - B)
        - A / (2 * SQ2 * B) * (2 * m["S"][i] / am - comps[i].b / bm) * L
        for i in range(len(comps))
    ]


def h_dep(m: dict, Z: mpf) -> mpf:
    T = m["T"]
    return R * T * (Z - 1) + (T * m["dam"] - m["am"]) / (2 * SQ2 * m["bm"]) * log_term(Z, m["B"])


def g_dep(comps: Sequence[Comp], m: dict, Z: mpf) -> mpf:
    """G^dep/RT of the phase at fixed composition, sum y_i ln phi_i."""
    return sum(yi * lp for yi, lp in zip(m["y"], ln_phi(comps, m, Z)))


# ---- the exact PR critical constants and NH3's EOS critical point (spec section 4.3) -----------


def pr_critical_constants() -> tuple[mpf, mpf, mpf]:
    """B_c, Z_c, A_c from the triple-root conditions of the PR cubic."""

    def f(B: mpf) -> mpf:
        Zc = (1 - B) / 3
        A = 3 * Zc**2 + 3 * B**2 + 2 * B
        return Zc**3 - (A * B - B**2 - B**3)

    Bc = mp.findroot(f, mpf("0.0778"))
    Zc = (1 - Bc) / 3
    Ac = 3 * Zc**2 + 3 * Bc**2 + 2 * Bc
    return Bc, Zc, Ac


BC, ZC, AC = pr_critical_constants()
THETA_C = AC / BC


def eos_critical(c: Comp) -> dict[str, mpf]:
    r = mp.sqrt(THETA_C * OMEGA_B / OMEGA_A)
    s = (1 + c.kappa) / (r + c.kappa)
    tce = c.tc * s**2
    pce = BC * R * tce / c.b
    vce = ZC / BC * c.b
    return {"T": tce, "P": pce, "v": vce, "r": r}


# ============================================================================================
# 3. Phase evaluation and the vapour-only flash (spec sections 5 and 6)
# ============================================================================================


class PR:
    def __init__(self, comps: Sequence[Comp], kij: dict[tuple[int, int], mpf] | None = None) -> None:
        self.c = list(comps)
        self.kij = kij or {}
        self.crit = eos_critical(self.c[I_NH3])

    # -- pure NH3 ------------------------------------------------------------------------------
    def pure(self, T: mpf, P: mpf) -> dict[str, Any]:
        y = [mpf(0)] * len(self.c)
        y[I_NH3] = mpf(1)
        m = mixture(self.c, T, P, y, self.kij)
        rs = real_roots(m["A"], m["B"])
        out: dict[str, Any] = {"m": m, "roots": rs, "liquid": None, "vapour": None}
        if T >= self.crit["T"]:
            if len(rs) != 1:
                raise RuntimeError("supercritical NH3 with more than one root")
            out["vapour"] = rs[0]
            return out
        if len(rs) == 3:
            out["liquid"], out["vapour"] = rs[0], rs[2]
        elif len(rs) == 1:
            v = rs[0] * R * T / P
            if v < self.crit["v"]:
                out["liquid"] = rs[0]
            else:
                out["vapour"] = rs[0]
        else:
            raise RuntimeError(f"unexpected root count {len(rs)}")
        return out

    def pure_stable(self, T: mpf, P: mpf) -> str:
        p = self.pure(T, P)
        if p["liquid"] is None:
            return "VAPOR"
        if p["vapour"] is None:
            return "LIQUID"
        lpl = ln_phi(self.c, p["m"], p["liquid"])[I_NH3]
        lpv = ln_phi(self.c, p["m"], p["vapour"])[I_NH3]
        return "LIQUID" if lpl <= lpv else "VAPOR"

    # -- evaluate_phase -----------------------------------------------------------------------
    def evaluate(self, phase: str, T: mpf, P: mpf, n: Sequence[mpf], guard: bool = True) -> dict[str, Any]:
        if not (DOMAIN_T[0] <= T <= DOMAIN_T[1] and DOMAIN_P[0] <= P <= DOMAIN_P[1]):
            raise Unsupported("out_of_domain")
        ntot = sum(n)
        y = [ni / ntot for ni in n]
        light = sum(n[i] for i in LIGHT)
        if phase == "LIQUID":
            if light > 0:
                raise Unsupported("light_gas_in_liquid")
            p = self.pure(T, P)
            if p["liquid"] is None:
                raise Unsupported("no_liquid_root")
            m, Z = p["m"], p["liquid"]
            lp = ln_phi(self.c, m, Z)
            return self._pack(m, Z, {I_NH3: lp[I_NH3]}, y)
        if light == 0:
            p = self.pure(T, P)
            if p["vapour"] is None:
                raise Unsupported("no_vapour_root")
            m, Z = p["m"], p["vapour"]
        else:
            m = mixture(self.c, T, P, y, self.kij)
            rs = real_roots(m["A"], m["B"])
            Z = rs[-1]
            if guard and len(rs) == 3 and g_dep(self.c, m, rs[0]) < g_dep(self.c, m, rs[-1]):
                raise Unsupported("vapour_root_metastable")
        lp = ln_phi(self.c, m, Z)
        return self._pack(m, Z, dict(enumerate(lp)), y)

    def _pack(self, m: dict, Z: mpf, lp: dict[int, mpf], y: Sequence[mpf]) -> dict[str, Any]:
        T, P = m["T"], m["P"]
        hig = sum(y[i] * h_ig(self.c[i], T) for i in range(len(self.c)))
        out = {"Z": Z, "v": Z * R * T / P, "h": hig + h_dep(m, Z), "h_dep": h_dep(m, Z)}
        for i, val in lp.items():
            out[f"lnphi_{ORDER[i]}"] = val
        return out

    # -- the flash ----------------------------------------------------------------------------
    def h_eq(self, T: mpf, P: mpf, w: Sequence[mpf], lnphi_l: mpf, yv: mpf, guard: bool = False) -> mpf:
        n = [mpf(0)] * len(self.c)
        for i, wi in zip(LIGHT, w):
            n[i] = (1 - yv) * wi
        n[I_NH3] = yv
        ev = self.evaluate("VAPOR", T, P, n, guard=guard)
        return mp.log(yv) + ev["lnphi_NH3"] - lnphi_l

    @staticmethod
    def samples() -> list[mpf]:
        s = [mpf(k) / 64 for k in range(1, 64)]
        s += [1 - mpf(2) ** (-j) for j in range(7, 41)]
        return s

    def y_star(self, T: mpf, P: mpf, w: Sequence[mpf]) -> dict[str, Any] | None:
        """Equilibrium vapour NH3 fraction for light-gas proportions w; None if no liquid can form."""
        if T >= self.crit["T"]:
            return None
        if self.pure_stable(T, P) != "LIQUID":
            return None
        lnphi_l = self.evaluate("LIQUID", T, P, [mpf(0), mpf(0), mpf(1), mpf(0), mpf(0)])["lnphi_NH3"]
        lo = mpf(0)
        hi = None
        neg_samples = 0
        for s in self.samples():
            if self.h_eq(T, P, w, lnphi_l, s) >= 0:
                hi = s
                break
            lo = s
            neg_samples += 1
        if hi is None:
            return None
        for _ in range(400):
            mid = (lo + hi) / 2
            if self.h_eq(T, P, w, lnphi_l, mid) >= 0:
                hi = mid
            else:
                lo = mid
            if hi - lo < mpf(10) ** (-45):
                break
        ys = (lo + hi) / 2
        resid = self.h_eq(T, P, w, lnphi_l, ys, guard=True)
        return {"y": ys, "residual": resid, "lnphi_l": lnphi_l, "bracket_index": neg_samples}

    def flash(self, T: mpf, P: mpf, n: Sequence[mpf]) -> dict[str, Any]:
        if not (DOMAIN_T[0] <= T <= DOMAIN_T[1] and DOMAIN_P[0] <= P <= DOMAIN_P[1]):
            raise Unsupported("out_of_domain")
        ntot = sum(n)
        if ntot == 0:
            return {"signature": "ZERO_FLOW", "beta": None}
        light = sum(n[i] for i in LIGHT)
        if light == 0:
            ph = "VAPOR" if T >= self.crit["T"] else self.pure_stable(T, P)
            return {"signature": ph, "beta": mpf(1) if ph == "VAPOR" else mpf(0), "route": "pure_nh3"}
        if n[I_NH3] == 0:
            return {"signature": "VAPOR", "beta": mpf(1), "route": "no_nh3"}
        w = [n[i] / light for i in LIGHT]
        ys = self.y_star(T, P, w)
        if ys is None:
            route = "supercritical" if T >= self.crit["T"] else "no_liquid"
            return {"signature": "VAPOR", "beta": mpf(1), "route": route}
        v_nh3 = light * ys["y"] / (1 - ys["y"])
        if n[I_NH3] <= v_nh3:
            return {"signature": "VAPOR", "beta": mpf(1), "route": "undersaturated", "y_star": ys["y"]}
        liq = n[I_NH3] - v_nh3
        return {
            "signature": "TWO_PHASE",
            "beta": (light + v_nh3) / ntot,
            "route": "two_phase",
            "y_star": ys["y"],
            "v_nh3": v_nh3,
            "l_nh3": liq,
            "residual": ys["residual"],
            "bracket_index": ys["bracket_index"],
            "lnphi_l": ys["lnphi_l"],
        }


def psat(pr: PR, T: mpf) -> dict[str, mpf]:
    c = pr.c[I_NH3]
    P0 = c.pc * mpf(10) ** (mpf(7) / 3 * (1 + c.om) * (1 - c.tc / T))

    def f(lnP: mpf) -> mpf:
        P = mp.exp(lnP)
        p = pr.pure(T, P)
        if p["liquid"] is None or p["vapour"] is None:
            raise RuntimeError("saturation iterate outside the three-root region")
        return ln_phi(pr.c, p["m"], p["liquid"])[I_NH3] - ln_phi(pr.c, p["m"], p["vapour"])[I_NH3]

    lnP = mp.findroot(f, (mp.log(P0), mp.log(P0 * mpf("1.01"))), solver="secant", tol=mpf(10) ** (-45))
    P = mp.exp(lnP)
    p = pr.pure(T, P)
    hl = pr._pack(p["m"], p["liquid"], {}, [0, 0, 1, 0, 0])
    hv = pr._pack(p["m"], p["vapour"], {}, [0, 0, 1, 0, 0])
    return {"P": P, "v_L": hl["v"], "v_V": hv["v"], "h_vap": hv["h"] - hl["h"], "residual": f(lnP)}


def spinodal_volumes(pr: PR, T: mpf) -> list[mpf]:
    """Real roots v > b of dP/dv = 0 for pure NH3: RT (v^2+2bv-b^2)^2 - 2a (v+b)(v-b)^2 = 0."""
    c = pr.c[I_NH3]
    a, b = a_of(c, T), c.b

    def pmul(p: list[mpf], q: list[mpf]) -> list[mpf]:
        out = [mpf(0)] * (len(p) + len(q) - 1)
        for i, pi in enumerate(p):
            for j, qj in enumerate(q):
                out[i + j] += pi * qj
        return out

    q = [mpf(1), 2 * b, -(b**2)]
    left = [R * T * x for x in pmul(q, q)]
    right = [2 * a * x for x in pmul([mpf(1), b], pmul([mpf(1), -b], [mpf(1), -b]))]
    right = [mpf(0)] * (len(left) - len(right)) + right
    poly = [lc - rc for lc, rc in zip(left, right)]
    rs = mp.polyroots(poly, maxsteps=400, extraprec=400)
    return sorted(mp.re(r) for r in rs if abs(mp.im(r)) < mpf(10) ** (-30) and mp.re(r) > b)


# ============================================================================================
# 4. Derivatives by 50-digit numerical differentiation (independent of any analytic formula)
# ============================================================================================

PROPS_V = ["Z", "v", "h"] + [f"lnphi_{c}" for c in ORDER]
PROPS_L = ["Z", "v", "h", "lnphi_NH3"]


def derivatives(pr: PR, phase: str, T: mpf, P: mpf, n: list[mpf]) -> dict[str, dict[str, mpf]]:
    props = PROPS_V if phase == "VAPOR" else PROPS_L
    out: dict[str, dict[str, mpf]] = {p: {} for p in props}

    def ev(TT: mpf, PP: mpf, nn: list[mpf]) -> dict[str, Any]:
        return pr.evaluate(phase, TT, PP, nn)

    for p in props:
        out[p]["T"] = mp.diff(lambda x: ev(x, P, n)[p], T)
        out[p]["P"] = mp.diff(lambda x: ev(T, x, n)[p], P)
        for j, cid in enumerate(ORDER):
            if phase == "LIQUID":
                out[p][f"n_{cid}"] = mpf(0)  # pure NH3: an intensive property of a fixed composition
                continue

            def fj(x: mpf, j: int = j) -> mpf:
                nn = list(n)
                nn[j] = x
                return ev(T, P, nn)[p]

            out[p][f"n_{cid}"] = mp.diff(fj, n[j])
    return out


# ============================================================================================
# 5. 53-bit transcription (measured: tolerance argument only)
# ============================================================================================


def f53_vapour_or_liquid(comps: Sequence[Comp], phase: str, T: float, P: float, n: Sequence[float]) -> dict:
    """Peng-Robinson in IEEE double: trigonometric/Cardano roots, two Newton polishes. Never an expectation."""
    nc = len(comps)
    ntot = sum(n)
    y = [x / ntot for x in n]
    Rf = float(R)
    a, da, b = [], [], []
    for c in comps:
        sa = 1.0 + float(c.kappa) * (1.0 - math.sqrt(T / float(c.tc)))
        a.append(float(c.ac) * sa * sa)
        da.append(-float(c.ac) * float(c.kappa) * sa / math.sqrt(T * float(c.tc)))
        b.append(float(c.b))
    S = [sum(y[j] * math.sqrt(a[i] * a[j]) for j in range(nc)) for i in range(nc)]
    am = sum(y[i] * S[i] for i in range(nc))
    dam = sum(y[i] * y[j] * (da[i] * a[j] + a[i] * da[j]) / (2 * math.sqrt(a[i] * a[j])) for i in range(nc) for j in range(nc))
    bm = sum(y[i] * b[i] for i in range(nc))
    A = am * P / (Rf * T) ** 2
    B = bm * P / (Rf * T)
    c2, c1, c0 = -(1 - B), A - 3 * B * B - 2 * B, -(A * B - B * B - B**3)
    # depressed cubic t^3 + p t + q, Z = t - c2/3
    p = c1 - c2 * c2 / 3
    q = 2 * c2**3 / 27 - c2 * c1 / 3 + c0
    disc = (q / 2) ** 2 + (p / 3) ** 3
    if disc > 0:
        sd = math.sqrt(disc)
        u = -q / 2 + sd
        v = -q / 2 - sd
        t = math.copysign(abs(u) ** (1 / 3), u) + math.copysign(abs(v) ** (1 / 3), v)
        roots = [t - c2 / 3]
    else:
        r = math.sqrt(-p / 3)
        phi = math.acos(max(-1.0, min(1.0, -q / (2 * r**3))))
        roots = sorted(2 * r * math.cos((phi + 2 * math.pi * k) / 3) - c2 / 3 for k in range(3))
    roots = [z for z in roots if z > B]
    Z = roots[0] if phase == "LIQUID" else roots[-1]
    for _ in range(2):
        f = ((Z + c2) * Z + c1) * Z + c0
        fp = (3 * Z + 2 * c2) * Z + c1
        Z -= f / fp
    L = math.log((Z + (1 + math.sqrt(2)) * B) / (Z + (1 - math.sqrt(2)) * B))
    lnphi = [b[i] / bm * (Z - 1) - math.log(Z - B) - A / (2 * math.sqrt(2) * B) * (2 * S[i] / am - b[i] / bm) * L for i in range(nc)]
    hd = Rf * T * (Z - 1) + (T * dam - am) / (2 * math.sqrt(2) * bm) * L
    hig = 0.0
    for i, c in enumerate(comps):
        tau, tau0 = T / 1000.0, float(T0) / 1000.0
        hig += y[i] * (float(c.hf) + Rf * 1000.0 * sum(float(c.bk[k]) * (tau ** (k + 1) - tau0 ** (k + 1)) / (k + 1) for k in range(5)))
    return {"Z": Z, "h": hig + hd, **{f"lnphi_{ORDER[i]}": lnphi[i] for i in range(nc)}}


# ============================================================================================
# 6. Reactor boundary closed forms (ADR 0027; spec section 8)
# ============================================================================================


def element_matrix(comps: Sequence[Comp]) -> tuple[list[str], list[list[int]]]:
    elems = sorted({e for c in comps for e in c.elements})
    return elems, [[int(c.elements.get(e, 0)) for c in comps] for e in elems]


def project_outlet(n_in: Sequence[mpf], n_raw: Sequence[mpf]) -> dict[str, Any]:
    """Least-squares extent over the reactive species; inert outlets equal their inlets."""
    num = sum(NU[i] * (n_raw[i] - n_in[i]) for i in REACTIVE)
    den = sum(NU[i] ** 2 for i in REACTIVE)
    xi = num / den
    n_out = [n_in[i] + NU[i] * xi for i in range(5)]
    defect = [n_raw[i] - n_out[i] for i in range(5)]
    scale = sum(n_in)
    return {"xi": xi, "n_out": n_out, "defect": defect, "defect_rel": max(abs(d) for d in defect) / scale}


def fit_dippr107(c: Comp, c3: mpf, c5: mpf) -> dict[str, Any]:
    """Relative least squares of C1 + C2 [(C3/T)/sinh(C3/T)]^2 + C4 [(C5/T)/cosh(C5/T)]^2 to NASA c_p, 250-1000 K."""
    Ts = [mpf(250 + 5 * k) for k in range(151)]
    rows, rhs = [], []
    for T in Ts:
        target = cp_ig(c, T) * 1000  # J/(kmol K), the reactor's unit
        x, z = c3 / T, c5 / T
        rows.append([1 / target, (x / mp.sinh(x)) ** 2 / target, (z / mp.cosh(z)) ** 2 / target])
        rhs.append(mpf(1))
    M = mp.matrix(3, 3)
    v = mp.matrix(3, 1)
    for r, t in zip(rows, rhs):
        for i in range(3):
            v[i] += r[i] * t
            for j in range(3):
                M[i, j] += r[i] * r[j]
    sol = mp.lu_solve(M, v)
    C1, C2, C4 = (mpf(mp.nstr(sol[i], 6)) for i in range(3))
    dev = max(
        abs((C1 + C2 * ((c3 / T) / mp.sinh(c3 / T)) ** 2 + C4 * ((c5 / T) / mp.cosh(c5 / T)) ** 2) / (cp_ig(c, T) * 1000) - 1)
        for T in Ts
    )
    return {"C1": C1, "C2": C2, "C3": c3, "C4": C4, "C5": c5, "max_rel_dev": dev}


# ============================================================================================
# 7. Registered states (spec section 7.1: why each is in the list)
# ============================================================================================


def m(x: str | float) -> mpf:
    return mpf(str(x))


FEED_REACTOR_INLET = [m("0.70"), m("0.235"), m("0.03"), m("0.015"), m("0.02")]
FEED_SEPARATOR = [m("0.60"), m("0.20"), m("0.165"), m("0.015"), m("0.02")]

PHASE_STATES: list[dict[str, Any]] = [
    {"id": "V1", "T": m("673.15"), "P": m("1e7"), "n": FEED_REACTOR_INLET, "phase": "VAPOR", "expect": "ok",
     "why": "reactor inlet: above NH3's EOS critical temperature, five distinct fugacity coefficients near one, a nonzero departure enthalpy"},
    {"id": "V2", "T": m("268.15"), "P": m("1e7"), "n": [m("0.6743819512868283"), m("0.22479398376227613"), m("0.061485117792505664"), m("0.01685954878217071"), m("0.022479398376227616")],
     "phase": "VAPOR", "expect": "ok",
     "why": "a cold, NH3-bearing vapour near the separator's equilibrium vapour (the IDAES composition): strongly nonideal NH3"},
    {"id": "L1", "T": m("268.15"), "P": m("1e7"), "n": [m(0), m(0), m(1), m(0), m(0)], "phase": "LIQUID", "expect": "ok",
     "why": "pure NH3 compressed liquid: a single real root, liquid by the critical-volume test"},
    {"id": "L2", "T": m("350"), "P": m("1e6"), "n": [m(0), m(0), m(1), m(0), m(0)], "phase": "LIQUID", "expect": "ok",
     "why": "pure NH3 below its saturation pressure: three real roots; the liquid root is metastable and still evaluable"},
    {"id": "V3", "T": m("350"), "P": m("1e6"), "n": [m(0), m(0), m(1), m(0), m(0)], "phase": "VAPOR", "expect": "ok",
     "why": "the same three-root state, vapour root: the largest root, distinct from L2's"},
    {"id": "V4", "T": m("420"), "P": m("5e6"), "n": [m(0), m(0), m(1), m(0), m(0)], "phase": "VAPOR", "expect": "ok",
     "why": "pure NH3 above its EOS critical temperature: one root, labelled vapour"},
    {"id": "V5", "T": m("268.15"), "P": m("1e7"), "n": [m("0.75"), m("0.25"), m(0), m(0), m(0)], "phase": "VAPOR", "expect": "ok",
     "why": "light gases only: lnphi_NH3 is NH3 at infinite dilution, defined although NH3 is absent"},
    {"id": "U1", "T": m("268.15"), "P": m("1e7"), "n": [m("1e-6"), m(0), m("0.999999"), m(0), m(0)], "phase": "LIQUID", "expect": "light_gas_in_liquid",
     "why": "a liquid carrying any light gas is outside the convention"},
    {"id": "U2", "T": m("420"), "P": m("5e6"), "n": [m(0), m(0), m(1), m(0), m(0)], "phase": "LIQUID", "expect": "no_liquid_root",
     "why": "no liquid above NH3's EOS critical temperature"},
    {"id": "U3", "T": m("268.15"), "P": m("1e7"), "n": [m(0), m(0), m(1), m(0), m(0)], "phase": "VAPOR", "expect": "no_vapour_root",
     "why": "pure compressed liquid NH3 has no vapour-like root"},
    {"id": "U4", "T": m("268.15"), "P": m("5e5"), "n": [m("0.02"), m(0), m("0.98"), m(0), m(0)], "phase": "VAPOR", "expect": "vapour_root_metastable",
     "why": "an NH3-rich mixture with three roots whose smallest root is the stable one: the convention's vapour would be metastable"},
    {"id": "U5", "T": m("150"), "P": m("1e7"), "n": FEED_REACTOR_INLET, "phase": "VAPOR", "expect": "out_of_domain",
     "why": "below the provider's temperature domain (200 K)"},
    {"id": "U6", "T": m("673.15"), "P": m("5e7"), "n": FEED_REACTOR_INLET, "phase": "VAPOR", "expect": "out_of_domain",
     "why": "above the provider's pressure domain (3e7 Pa)"},
]

FLASH_STATES: list[dict[str, Any]] = [
    {"id": "F1", "T": m("268.15"), "P": m("1e7"), "n": FEED_SEPARATOR, "expect": "TWO_PHASE",
     "why": "the C1 separator: vapour plus pure liquid NH3 (the IDAES composition, M01's parameter set)"},
    {"id": "F2", "T": m("300"), "P": m("1e7"), "n": FEED_REACTOR_INLET, "expect": "VAPOR", "route": "undersaturated",
     "why": "subcritical, above NH3's saturation pressure, but the feed holds less NH3 than the equilibrium vapour can"},
    {"id": "F3", "T": m("268.15"), "P": m("2e5"), "n": [m("0.25"), m("0.25"), m("0.5"), m(0), m(0)], "expect": "VAPOR", "route": "no_liquid",
     "why": "below NH3's saturation pressure: no liquid can form whatever the feed"},
    {"id": "F4", "T": m("268.15"), "P": m("1e7"), "n": None, "expect": "VAPOR_OR_TRACE", "route": "dew_point",
     "why": "F1's light gases with exactly the equilibrium vapour's NH3: the dew point, where a liquid of O(ulp) may appear"},
    {"id": "F5", "T": m("268.15"), "P": m("1e7"), "n": [m("1e-6"), m(0), m("0.999999"), m(0), m(0)], "expect": "TWO_PHASE",
     "why": "the trivial-solution trap: an NH3 feed with a trace of H2, whose own single root is liquid-like; the convention's answer is a small H2-rich vapour"},
    {"id": "F6", "T": m("268.15"), "P": m("1e7"), "n": [m("0.75"), m("0.25"), m(0), m(0), m(0)], "expect": "VAPOR", "route": "no_nh3",
     "why": "no NH3: no liquid can exist"},
    {"id": "F7", "T": m("268.15"), "P": m("1e7"), "n": [m(0), m(0), m(1), m(0), m(0)], "expect": "LIQUID", "route": "pure_nh3",
     "why": "pure NH3 above its saturation pressure"},
    {"id": "F8", "T": m("350"), "P": m("1e6"), "n": [m(0), m(0), m(1), m(0), m(0)], "expect": "VAPOR", "route": "pure_nh3",
     "why": "pure NH3 below its saturation pressure: the vapour root has the lower Gibbs energy"},
    {"id": "F9", "T": m("420"), "P": m("5e6"), "n": [m(0), m(0), m(1), m(0), m(0)], "expect": "VAPOR", "route": "pure_nh3",
     "why": "pure NH3 above its EOS critical temperature"},
    {"id": "F10", "T": m("673.15"), "P": m("1e7"), "n": FEED_REACTOR_INLET, "expect": "VAPOR", "route": "supercritical",
     "why": "the reactor inlet: above NH3's EOS critical temperature, decided without the equilibrium search"},
    {"id": "F11", "T": m("250"), "P": m("2.5e7"), "n": FEED_SEPARATOR, "expect": "TWO_PHASE",
     "why": "a colder, higher-pressure separator: a different equilibrium vapour, the same rules"},
    {"id": "F12", "T": m("400"), "P": m("2e7"), "n": [m("0.5"), m("0.17"), m("0.3"), m("0.01"), m("0.02")], "expect": "ANY",
     "why": "5.6 K below NH3's EOS critical temperature: the adversarial near-critical case, registered for what the rules give"},
    {"id": "F13", "T": m("268.15"), "P": m("5e5"), "n": [m("0.02"), m(0), m("0.98"), m(0), m(0)], "expect": "TWO_PHASE",
     "why": "U4's feed: evaluate_phase refuses its vapour root, the flash still finds the convention's split"},
    {"id": "F14", "T": m("300"), "P": m("1e7"), "n": [m(0), m(0), m(0), m(0), m(0)], "expect": "ZERO_FLOW",
     "why": "a dormant feed (ADR 0001 D3.4)"},
]

DERIVATIVE_STATES = ("V1", "V2", "L1")


# ============================================================================================
# 8. Build
# ============================================================================================


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    CLAIMS.clear()
    comps = load_components()
    pr = PR(comps)
    out: dict[str, Any] = {
        "record": "m01-reference-values",
        "version": 1,
        "specification": "docs/derivations/M01-spec.md",
        "generator": "docs/derivations/scripts/m01_reference.py",
        "components_yaml_sha256": hashlib.sha256(COMPONENTS_YAML.read_bytes()).hexdigest(),
        "constants": {
            "R_J_per_mol_K": dstr(R, 15),
            "Omega_a": "0.45724",
            "Omega_b": "0.07780",
            "kappa_rule": "0.37464 + 1.54226 w - 0.26992 w^2 (Peng-Robinson 1976) for every component",
            "k_ij": "0 for every pair (ADR 0026 D3)",
            "T_ref_K": "298.15",
            "domain": {"T_K": [200.0, 1000.0], "P_Pa": [1.0e4, 3.0e7]},
        },
    }
    cf: dict[str, Any] = {}

    # --- PR constants ------------------------------------------------------------------------------
    res = (1 - BC) / 3 - ZC
    claim("PR-01", abs(res) < mpf(10) ** -45 and abs(ZC**3 - (AC * BC - BC**2 - BC**3)) < mpf(10) ** -45,
          "B_c, Z_c, A_c satisfy the PR cubic's triple-root conditions")
    claim("PR-02", abs(BC - mpf("0.0777960739")) < mpf("1e-10") and abs(AC - mpf("0.4572355289")) < mpf("1e-10"),
          "the exact PR constants round to the textbook 0.0777960739 and 0.4572355289")
    cf["pr_constants"] = {"B_c": dstr(BC), "Z_c": dstr(ZC), "A_c": dstr(AC), "theta_c": dstr(THETA_C),
                          "v_c_over_b": dstr(ZC / BC)}
    comp_out = {}
    for c in comps:
        crit = eos_critical(c)
        comp_out[c.id] = {"kappa": nstr(c.kappa), "a_c_Pa_m6_per_mol2": nstr(c.ac), "b_m3_per_mol": nstr(c.b),
                          "T_c_EOS_K": nstr(crit["T"]), "sqrt_alpha_at_1000K": nstr(sqrt_alpha(c, mpf(1000))),
                          "cp_ig_298_15": nstr(cp_ig(c, T0)), "cp_ig_700": nstr(cp_ig(c, mpf(700))),
                          "h_ig_700": nstr(h_ig(c, mpf(700))), "h_ig_268_15": nstr(h_ig(c, mpf("268.15")))}
        claim(f"PR-03-{c.id}", sqrt_alpha(c, DOMAIN_T[1]) > 0 and sqrt_alpha(c, DOMAIN_T[0]) > 0,
              f"sqrt(alpha) of {c.id} stays positive on 200-1000 K (it is monotone in T)")
    cf["components"] = comp_out
    crit = pr.crit
    cf["nh3_eos_critical"] = {"T_K": nstr(crit["T"]), "P_Pa": nstr(crit["P"]), "v_m3_per_mol": nstr(crit["v"]),
                              "T_c_record_K": nstr(comps[I_NH3].tc)}
    # At the EOS critical point the pure cubic has a triple root at Z_c.
    mc = mixture(comps, crit["T"], crit["P"], [0, 0, 1, 0, 0], {})
    claim("PR-04", abs(mc["A"] - AC) < mpf(10) ** -40 and abs(mc["B"] - BC) < mpf(10) ** -40,
          "at (T_c,EOS, P_c,EOS) pure NH3's A and B equal the critical A_c, B_c: the closed form is NH3's EOS critical point")
    claim("PR-05", 0 < comps[I_NH3].tc - crit["T"] < mpf("0.02"),
          "with the rounded Omega_a, Omega_b NH3's EOS critical temperature lies below the record's T_c by less than 0.02 K")
    spin = {}
    for Tk in ("200", "240", "268.15", "300", "350", "400", "405"):
        T = mpf(Tk)
        vs = spinodal_volumes(pr, T)
        ok = len(vs) == 2 and vs[0] < crit["v"] < vs[1]
        claim(f"PR-06-{Tk}", ok, f"at {Tk} K NH3's two spinodal volumes straddle v_c,EOS (the single-root label rule is exact)")
        spin[Tk] = [nstr(v) for v in vs]
    cf["nh3_spinodal_volumes_m3_per_mol"] = spin

    # --- the T08 IDAES transcription check -------------------------------------------------------
    idaes = json.loads(IDAES_RECORD.read_text(encoding="utf-8"))
    src = idaes["property_route"]["sources"]
    t08 = []
    for cid in ORDER:
        v = src[cid]["values"]
        if "Tc" in v:
            t08.append(custom_comp(cid, v["Tc"], v["Pc"], v["omega"]))
        else:
            t08.append(custom_comp(cid, v["temperature_crit"], v["pressure_crit"], v["omega"]))
    pr08 = PR(t08)
    sep = idaes["pr_flash"]["light_gases_vapour_only"]["separator"]
    fl08 = pr08.flash(mpf("268.15"), mpf("1e7"), FEED_SEPARATOR)
    beta_dev = abs(fl08["beta"] - mpf(repr(sep["phase_fraction"]["Vap"])))
    y_dev = abs(fl08["y_star"] - mpf(repr(sep["y_vapour"]["NH3"])))
    nv = [mpf(repr(sep["y_vapour"][c])) for c in ORDER]
    ev08 = pr08.evaluate("VAPOR", mpf("268.15"), mpf("1e7"), nv)
    phi_dev = max(abs(mp.exp(ev08[f"lnphi_{c}"]) / mpf(repr(sep["fug_coeff_vapour"][c])) - 1) for c in ORDER)
    lq08 = pr08.evaluate("LIQUID", mpf("268.15"), mpf("1e7"), [0, 0, 1, 0, 0])
    phil_dev = abs(mp.exp(lq08["lnphi_NH3"]) / mpf(repr(sep["fug_coeff_liquid"]["NH3"])) - 1)
    claim("IDAES-01", beta_dev < mpf("1e-9") and y_dev < mpf("1e-9") and phi_dev < mpf("1e-9") and phil_dev < mpf("1e-9"),
          "with T08's parameter set this script reproduces IDAES 2.13's vapour-only separator (beta, y_NH3, five vapour and the liquid fugacity coefficients) to 1e-9")
    out["transcription_check_vs_idaes"] = {
        "record": "benchmarks/t08/v19/c1-idaes.json pr_flash.light_gases_vapour_only.separator",
        "parameter_set": "T08's (the group database for H2, N2, NH3; IDAES examples for Ar, CH4): used for this check only",
        "abs_dev_beta": nstr(beta_dev, 3), "abs_dev_y_NH3": nstr(y_dev, 3),
        "max_rel_dev_vapour_phi": nstr(phi_dev, 3), "rel_dev_liquid_phi": nstr(phil_dev, 3),
    }

    # --- phase states ----------------------------------------------------------------------------
    ps_out = {}
    evals: dict[str, dict[str, Any]] = {}
    for s in PHASE_STATES:
        rec: dict[str, Any] = {"T_K": nstr(s["T"]), "P_Pa": nstr(s["P"]), "n_mol_s": [nstr(x) for x in s["n"]],
                               "phase": s["phase"], "why": s["why"]}
        try:
            ev = pr.evaluate(s["phase"], s["T"], s["P"], s["n"])
            status = "ok"
            evals[s["id"]] = ev
            rec["values"] = {k: nstr(v) for k, v in ev.items() if k != "h_dep"}
            rec["h_departure_J_mol"] = nstr(ev["h_dep"])
            if s["phase"] == "VAPOR" and sum(s["n"][i] for i in LIGHT) > 0:
                mm = mixture(comps, s["T"], s["P"], [x / sum(s["n"]) for x in s["n"]], {})
                rec["real_root_count"] = len(real_roots(mm["A"], mm["B"]))
            else:
                rec["real_root_count"] = len(pr.pure(s["T"], s["P"])["roots"])
        except Unsupported as exc:
            status = exc.code
        rec["status_or_reason"] = status
        claim(f"PH-{s['id']}", status == s["expect"], f"state {s['id']} evaluates to {s['expect']}")
        ps_out[s["id"]] = rec
    claim("PH-ROOTS", ps_out["L2"]["real_root_count"] == 3 and ps_out["V3"]["real_root_count"] == 3
          and ps_out["L1"]["real_root_count"] == 1 and ps_out["V1"]["real_root_count"] == 1
          and ps_out["V2"]["real_root_count"] == 1,
          "L2/V3 have three real roots; L1, V1 and V2 one")
    claim("PH-DISTINCT", len({ps_out[k]["values"]["Z"] for k in ("L2", "V3")}) == 2
          and len({v for k, v in ps_out["V1"]["values"].items() if k.startswith("lnphi")}) == 5
          and len({v for k, v in ps_out["V2"]["values"].items() if k.startswith("lnphi")}) == 5,
          "the three-root state's two roots differ; V1's and V2's five lnphi are pairwise distinct")
    claim("PH-NONZERO", all(abs(ev["h_dep"]) > 1 for ev in evals.values()),
          "every evaluated state has a departure enthalpy above 1 J/mol in magnitude: a dropped departure term changes every h")
    cf["phase_states"] = ps_out

    # --- derivatives -----------------------------------------------------------------------------
    der_out = {}
    for sid in DERIVATIVE_STATES:
        s = next(x for x in PHASE_STATES if x["id"] == sid)
        d = derivatives(pr, s["phase"], s["T"], s["P"], list(s["n"]))
        der_out[sid] = {p: {k: nstr(v) for k, v in dd.items()} for p, dd in d.items()}
        if s["phase"] == "VAPOR":
            # Homogeneity of degree zero: sum_j n_j d(intensive)/dn_j = 0.
            hom = max(abs(sum(s["n"][j] * d[p][f"n_{ORDER[j]}"] for j in range(5))) for p in d)
            claim(f"DER-HOM-{sid}", hom < mpf(10) ** -25,
                  f"at {sid} every intensive property is homogeneous of degree zero in n (sum_j n_j dX/dn_j < 1e-25)")
            # Gibbs-Duhem at fixed T, P: sum_i n_i d lnphi_i / d n_j = 0 for every j.
            gd = max(abs(sum(s["n"][i] * d[f"lnphi_{ORDER[i]}"][f"n_{ORDER[j]}"] for i in range(5))) for j in range(5))
            claim(f"DER-GD-{sid}", gd < mpf(10) ** -25, f"at {sid} the lnphi derivatives satisfy Gibbs-Duhem to 1e-25")
            # Symmetry: d lnphi_i/dn_j = d lnphi_j/dn_i (n_tot times a Hessian of G^R).
            sym = max(abs(d[f"lnphi_{ORDER[i]}"][f"n_{ORDER[j]}"] - d[f"lnphi_{ORDER[j]}"][f"n_{ORDER[i]}"])
                      for i in range(5) for j in range(5))
            claim(f"DER-SYM-{sid}", sym < mpf(10) ** -25, f"at {sid} d lnphi_i/d n_j is symmetric to 1e-25")
            nz = min(abs(v) for p in d for v in d[p].values())
            claim(f"DER-NZ-{sid}", nz > mpf(10) ** -12,
                  f"at {sid} no registered derivative vanishes (smallest magnitude above 1e-12): no assertion is met by an accidental zero")
    cf["derivatives"] = der_out

    # --- flash states ----------------------------------------------------------------------------
    fl_out = {}
    f1 = None
    for s in FLASH_STATES:
        n = s["n"]
        if s["id"] == "F4":
            light = sum(f1n for i, f1n in enumerate(FEED_SEPARATOR) if i in LIGHT)
            n = list(FEED_SEPARATOR)
            n[I_NH3] = mpf(repr(float(light * f1["y_star"] / (1 - f1["y_star"]))))
        r = pr.flash(s["T"], s["P"], n)
        rec = {"T_K": nstr(s["T"]), "P_Pa": nstr(s["P"]), "n_mol_s": [nstr(x) for x in n], "why": s["why"],
               "phase_signature": r["signature"], "route": r.get("route", "zero_flow")}
        if r.get("beta") is not None:
            rec["vapor_fraction"] = nstr(r["beta"])
        for key in ("y_star", "v_nh3", "l_nh3"):
            if key in r:
                rec[key] = nstr(r[key])
        if r["signature"] == "TWO_PHASE":
            claim(f"FL-EQ-{s['id']}", abs(r["residual"]) < mpf(10) ** -40,
                  f"at {s['id']} the equilibrium row ln y* + lnphi_NH3^V - lnphi_NH3^L vanishes to 1e-40")
            vap = list(n)
            vap[I_NH3] = r["v_nh3"]
            ev = pr.evaluate("VAPOR", s["T"], s["P"], vap)
            lq = pr.evaluate("LIQUID", s["T"], s["P"], [0, 0, r["l_nh3"], 0, 0])
            rec["vapour"] = {"n_mol_s": [nstr(x) for x in vap], "h_J_mol": nstr(ev["h"]), "Z": nstr(ev["Z"]),
                             **{k: nstr(v) for k, v in ev.items() if k.startswith("lnphi")}}
            rec["liquid"] = {"n_NH3_mol_s": nstr(r["l_nh3"]), "h_J_mol": nstr(lq["h"]), "Z": nstr(lq["Z"]),
                             "lnphi_NH3": nstr(lq["lnphi_NH3"])}
            rec["k_value_NH3"] = nstr(r["y_star"])
            rec["bracket_sample_index"] = r["bracket_index"]
            mm = mixture(comps, s["T"], s["P"], [x / sum(vap) for x in vap], {})
            rec["vapour_real_root_count"] = len(real_roots(mm["A"], mm["B"]))
            if s["id"] in ("F1", "F5", "F11"):
                claim(f"FL-ROOT-{s['id']}", rec["vapour_real_root_count"] == 1,
                      f"at {s['id']} (100-250 bar) the equilibrium vapour's cubic has a single real root")
        if s["expect"] == "VAPOR_OR_TRACE":
            ok = r["signature"] == "VAPOR" or (r["signature"] == "TWO_PHASE" and r["l_nh3"] < mpf("1e-15"))
        elif s["expect"] == "ANY":
            ok = True
        else:
            ok = r["signature"] == s["expect"] and ("route" not in s or r.get("route") == s["route"])
        claim(f"FL-{s['id']}", ok, f"flash {s['id']} gives {s['expect']}{' by route ' + s['route'] if 'route' in s else ''}")
        if s["id"] == "F1":
            f1 = r
        fl_out[s["id"]] = rec
    # y* depends on (T, P, light-gas proportions) only: F1 with twice its NH3 has the same y*.
    nn = list(FEED_SEPARATOR)
    nn[I_NH3] *= 2
    r2 = pr.flash(mpf("268.15"), mpf("1e7"), nn)
    claim("FL-INDEP", r2["y_star"] == f1["y_star"], "the equilibrium vapour composition does not depend on the feed's NH3 (F1 with doubled NH3)")
    # Monotone below y*: every sample below the bracket has h < 0 (checked by construction); report F1's.
    claim("FL-F5-ROOT", fl_out["F5"]["y_star"] < 0.2, "F5's vapour holds NH3 at y* < 0.2: the H2-rich vapour, not the trivial liquid-like root")
    cf["flash_states"] = fl_out

    # --- W22: pure-NH3 saturation by this PR (compared externally with the reference EOS) ---------
    sat = {}
    for Tk in ("240", "260", "268.15", "280", "300", "320", "350", "380", "400"):
        ps = psat(pr, mpf(Tk))
        claim(f"SAT-{Tk}", abs(ps["residual"]) < mpf(10) ** -35, f"PR saturation at {Tk} K solved to 1e-35 in lnphi")
        sat[Tk] = {"P_sat_Pa": nstr(ps["P"]), "v_L_m3_mol": nstr(ps["v_L"]), "v_V_m3_mol": nstr(ps["v_V"]),
                   "h_vap_J_mol": nstr(ps["h_vap"])}
    cf["nh3_saturation_pr"] = sat

    # --- W22: pure-component fugacity coefficients at loop states (compared externally) -----------
    pure_states = {}
    for i, cid in enumerate(ORDER):
        for (Tk, Pk, phase) in (("268.15", "1e7", "VAPOR"), ("673.15", "1e7", "VAPOR"), ("268.15", "1e7", "LIQUID"),
                                ("250", "2.5e7", "LIQUID")):
            if (phase == "LIQUID") != (i == I_NH3) and not (i == I_NH3 and Tk == "673.15"):
                continue
            if i == I_NH3 and phase == "VAPOR" and Tk == "268.15":
                continue
            n = [mpf(0)] * 5
            n[i] = mpf(1)
            ev = pr.evaluate(phase, mpf(Tk), mpf(Pk), n)
            pure_states[f"{cid}-{phase}-{Tk}-{Pk}"] = {"T_K": nstr(mpf(Tk)), "P_Pa": nstr(mpf(Pk)), "phase": phase,
                                                       "lnphi": nstr(ev[f"lnphi_{cid}"]), "Z": nstr(ev["Z"]),
                                                       "h_departure_J_mol": nstr(ev["h_dep"])}
    cf["pure_component_states"] = pure_states
    claim("SAT-F3", mpf("2e5") < mpf(str(sat["268.15"]["P_sat_Pa"])) and mpf(str(sat["268.15"]["P_sat_Pa"])) < mpf("1e7"),
          "268.15 K: F3's 2e5 Pa lies below and F1's 1e7 Pa above PR's NH3 saturation pressure")

    # --- reaction datum and elements --------------------------------------------------------------
    elems, E = element_matrix(comps)
    claim("RX-01", all(sum(E[e][i] * NU[i] for i in range(5)) == 0 for e in range(len(elems))),
          "E nu = 0 for every element: the reaction conserves H, N, C and Ar")
    dh298 = sum(NU[i] * h_ig(comps[i], T0) for i in range(5))
    claim("RX-02", dh298 == 2 * comps[I_NH3].hf, "sum nu_i h_i^ig(298.15 K) = 2 dfH(NH3) exactly: PR-C1-ref-v1 is a formation datum")
    dh673 = sum(NU[i] * h_ig(comps[i], mpf("673.15")) for i in range(5))
    cf["reaction"] = {"elements": elems, "element_matrix": E, "nu": list(NU),
                      "dh_r_ig_298_15_J_mol": nstr(dh298), "dh_r_ig_673_15_J_mol": nstr(dh673)}

    # --- k_ij sensitivity at F1 (stated effect of k_ij = 0) -----------------------------------------
    sens = {}
    for (i, j) in ((0, 2), (1, 2), (2, 3), (2, 4), (0, 1)):
        vals = {}
        for k in ("-0.1", "0.1", "0.2"):
            prk = PR(comps, {(i, j): mpf(k)})
            rk = prk.flash(mpf("268.15"), mpf("1e7"), FEED_SEPARATOR)
            vals[k] = {"y_star": nstr(rk["y_star"], 8), "rel_change_y_star": nstr(rk["y_star"] / f1["y_star"] - 1, 4)}
        sens[f"{ORDER[i]}-{ORDER[j]}"] = vals
    cf["kij_sensitivity_F1"] = sens

    # --- reactor boundary: projection and the synthetic stand-in ------------------------------------
    n_in = FEED_REACTOR_INLET
    xs = mpf("0.25") * n_in[1]
    n_exact = [n_in[i] + NU[i] * xs for i in range(5)]
    d = [mpf("2e-6"), mpf("-1e-6"), mpf("3e-6"), mpf("1e-7"), mpf(0)]
    n_raw = [n_exact[i] + d[i] for i in range(5)]
    pj = project_outlet(n_in, n_raw)
    claim("BD-01", abs(pj["xi"] - (xs + mpf("1e-6") / 14)) < mpf(10) ** -40,
          "the least-squares extent of the perturbed outlet is xi_s + (nu . d)/14 = xi_s + 1e-6/14")
    elem_out = [sum(E[e][i] * pj["n_out"][i] for i in range(5)) - sum(E[e][i] * n_in[i] for i in range(5)) for e in range(len(elems))]
    claim("BD-02", max(abs(x) for x in elem_out) < mpf(10) ** -40, "the projected outlet conserves every element exactly")
    ev_in = pr.evaluate("VAPOR", mpf("673.15"), mpf("1e7"), n_in)
    ev_out = pr.evaluate("VAPOR", mpf("673.15"), mpf("1e7"), n_exact)
    Q = sum(n_exact) * ev_out["h"] - sum(n_in) * ev_in["h"]
    claim("BD-03", Q < 0, "the isothermal stand-in at 673.15 K removes heat (Q < 0): the reaction is exothermic on the datum")
    cf["boundary"] = {
        "standin": {"conversion_N2": "0.25", "inlet_n_mol_s": [nstr(x) for x in n_in], "T_in_K": 673.15, "P_in_Pa": 1.0e7,
                    "xi_mol_s": nstr(xs), "outlet_n_mol_s": [nstr(x) for x in n_exact], "T_out_K": 673.15, "P_out_Pa": 1.0e7,
                    "Q_W": nstr(Q), "H_in_W": nstr(sum(n_in) * ev_in["h"]), "H_out_W": nstr(sum(n_exact) * ev_out["h"]),
                    "Q_over_xi_J_mol": nstr(Q / xs)},
        "projection": {"perturbation_mol_s": [nstr(x) for x in d], "raw_outlet_mol_s": [nstr(x) for x in n_raw],
                       "xi_mol_s": nstr(pj["xi"]), "projected_outlet_mol_s": [nstr(x) for x in pj["n_out"]],
                       "defect_mol_s": [nstr(x) for x in pj["defect"]], "defect_rel": nstr(pj["defect_rel"])},
        "pressure_convention": {"eps_P": "1e-3", "accepted_dP_Pa": 5000.0, "refused_dP_Pa": 20000.0, "P_in_Pa": 1.0e7},
    }

    # --- reactor overlay rows (ADR 0027 D5) --------------------------------------------------------
    fit = fit_dippr107(comps[4], mpf(2000), mpf(1000))
    claim("OV-01", fit["max_rel_dev"] < mpf("0.005"), "the CH4 DIPPR-107 fit stays within 0.5 % of NASA c_p on 250-1000 K")
    ar_c1 = R * mpf("2.5") * 1000
    claim("OV-02", all(b == 0 for b in comps[3].bk[1:]) and comps[3].bk[0] == mpf("2.5"),
          "Ar's NASA c_p is exactly 5/2 R, so its DIPPR-107 row is C1 = 2500 R, C2 = C4 = 0")
    overlay = {
        "record": "m01-reactor-overlay",
        "version": 1,
        "reactor_commit": REACTOR_PIN,
        "specification": "docs/derivations/M01-spec.md section 8.6; ADR 0027 D5",
        "generator": "docs/derivations/scripts/m01_reference.py",
        "meaning": "Rows the pinned reactor's property database lacks (it holds H2, N2, NH3 only). The adapter merges them into a copy of the pinned src/reactor/data/properties_database.json read from the pinned checkout at run time; the group's file is never copied into this repository. 'copy_from' names a row of that pinned file whose columns are copied (the transport surrogate).",
        "species_properties": {
            "Ar": {"Mw": float(comps[3].mw), "Tc": float(comps[3].tc), "Pc": float(comps[3].pc), "omega": float(comps[3].om),
                   "c_p_C1": float(mp.nstr(ar_c1, 15)), "c_p_C2": 0.0, "c_p_C3": 1.0, "c_p_C4": 0.0, "c_p_C5": 1.0,
                   "dH_f": float(comps[3].hf),
                   "copy_from": {"row": "N2", "columns": ["wilke_C1", "wilke_C2", "wilke_C3", "wilke_C4",
                                                          "therm_cond_C1", "therm_cond_C2", "therm_cond_C3", "therm_cond_C4"]}},
            "CH4": {"Mw": float(comps[4].mw), "Tc": float(comps[4].tc), "Pc": float(comps[4].pc), "omega": float(comps[4].om),
                    "c_p_C1": float(fit["C1"]), "c_p_C2": float(fit["C2"]), "c_p_C3": float(fit["C3"]),
                    "c_p_C4": float(fit["C4"]), "c_p_C5": float(fit["C5"]), "dH_f": float(comps[4].hf),
                    "copy_from": {"row": "N2", "columns": ["wilke_C1", "wilke_C2", "wilke_C3", "wilke_C4",
                                                           "therm_cond_C1", "therm_cond_C2", "therm_cond_C3", "therm_cond_C4"]}},
        },
        "binary_properties": {
            "H2/Ar": {"copy_from": "H2/N2"}, "N2/Ar": {"copy_from": "N2/NH3"}, "NH3/Ar": {"copy_from": "N2/NH3"},
            "H2/CH4": {"copy_from": "H2/N2"}, "N2/CH4": {"copy_from": "N2/NH3"}, "NH3/CH4": {"copy_from": "N2/NH3"},
            "Ar/CH4": {"copy_from": "N2/NH3"},
        },
        "provenance": {
            "Mw, Tc, Pc, omega, dH_f": "benchmarks/m01/components.yaml (the M01 records)",
            "Ar c_p": "5/2 R exactly (monatomic ideal gas; NASA TM-4513's Ar low range is the same constant)",
            "CH4 c_p": f"relative least-squares fit of the DIPPR-107 form with C3 = 2000 K and C5 = 1000 K fixed (M01's choice) to NASA TM-4513's c_p on 250-1000 K step 5 K; C1, C2, C4 rounded to 6 significant digits; max relative deviation {mp.nstr(fit['max_rel_dev'], 3)}",
            "transport columns and binary rows": "surrogates copied from the pinned database's N2 row and N2 pairs (M01's choice; its effect is measured by the reactor probe's inert-transport variant)",
        },
    }
    cf["overlay_fit"] = {"max_rel_dev": nstr(fit["max_rel_dev"], 4)}

    # --- measured: 53-bit transcription floor -------------------------------------------------------
    meas = {}
    for sid in ("V1", "V2", "L1"):
        s = next(x for x in PHASE_STATES if x["id"] == sid)
        f = f53_vapour_or_liquid(comps, s["phase"], float(s["T"]), float(s["P"]), [float(x) for x in s["n"]])
        ref = evals[sid]
        keys = ["Z", "h"] + ([f"lnphi_{c}" for c in ORDER] if s["phase"] == "VAPOR" else ["lnphi_NH3"])
        meas[sid] = {k: nstr(abs(mpf(f[k]) - ref[k]) / max(abs(ref[k]), mpf(1)), 3) for k in keys}
    out["measured"] = {"meaning": "|53-bit transcription - 50-digit closed form| / max(|value|, 1): the double-precision floor the tolerances of spec section 9 sit above",
                       "transcription_floor": meas}

    # --- derived from the measured reactor record (regression only) --------------------------------
    if PROBE_RECORD.exists():
        probe = json.loads(PROBE_RECORD.read_text(encoding="utf-8"))
        if probe.get("record") == "m01-reactor-probe" and probe.get("version", 0) >= 2:
            out["derived_from_measured"] = derived_from_probe(pr, probe)

    out["closed_form"] = cf
    out["generator_claims"] = CLAIMS[:]
    return out, overlay


def derived_from_probe(pr: PR, probe: dict[str, Any]) -> dict[str, Any]:
    nom = probe["pinned"]
    n_in = [mpf(repr(x)) for x in nom["inlet_n_mol_s"]]
    n_raw = [mpf(repr(x)) for x in nom["outlet_n_mol_s"]]
    pj = project_outlet(n_in, n_raw)
    T_in, P = mpf(repr(nom["T_in_K"])), mpf(repr(nom["P_in_Pa"]))
    T_out = mpf(repr(nom["T_out_K"]))
    h_in = pr.evaluate("VAPOR", T_in, P, n_in)["h"] * sum(n_in)
    h_out = pr.evaluate("VAPOR", T_out, P, pj["n_out"])["h"] * sum(pj["n_out"])
    return {
        "meaning": "process-side quantities at the pinned grid's nominal solve, computed from the measured record: regression values, not validation",
        "probe_sha256": hashlib.sha256(PROBE_RECORD.read_bytes()).hexdigest(),
        "xi_mol_s": nstr(pj["xi"], 12), "projected_outlet_mol_s": [nstr(x, 12) for x in pj["n_out"]],
        "defect_rel": nstr(pj["defect_rel"], 3),
        "Q_process_W": nstr(h_out - h_in, 10),
        "Q_reactor_coolant_W": nom.get("coolant_heat_uptake_W"),
    }


def dump_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False, width=120, allow_unicode=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--emit", action="store_true")
    args = ap.parse_args()
    doc, overlay = build()
    text = dump_yaml(doc)
    otext = json.dumps(overlay, indent=1, sort_keys=False) + "\n"
    if args.emit:
        OUT_YAML.write_text(text, encoding="utf-8")
        OVERLAY_JSON.write_text(otext, encoding="utf-8")
        print(f"wrote {OUT_YAML.relative_to(ROOT)} and {OVERLAY_JSON.relative_to(ROOT)}; {len(CLAIMS)} claims hold")
        return 0
    ok = OUT_YAML.exists() and OUT_YAML.read_text(encoding="utf-8") == text
    ok2 = OVERLAY_JSON.exists() and OVERLAY_JSON.read_text(encoding="utf-8") == otext
    print(f"{len(CLAIMS)} claims hold; reference_values.yaml {'matches' if ok else 'DIFFERS'}; reactor-overlay.json {'matches' if ok2 else 'DIFFERS'}")
    return 0 if ok and ok2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
