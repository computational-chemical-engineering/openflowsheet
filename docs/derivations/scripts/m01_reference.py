"""Closed-form reference generator for M01: Peng-Robinson with the light gases vapour-only
(ADR 0026), the C1 component records' derived constants, and the reactor boundary's closed forms
and overlay rows (ADR 0027).

Normative text: ``docs/derivations/M01-spec.md``. Inputs: ``benchmarks/m01/components.yaml``
(the records), ``benchmarks/t08/v19/c1-idaes.json`` (the T08 IDAES record, used only to check this
script's transcription of Peng-Robinson against an independent implementation), and, if present,
``benchmarks/m01/reactor-probe.json`` (a *measured* record of the group's reactor; only the section
``derived_from_measured`` reads it, and nothing in it is an expectation for this repository's code).

It imports nothing from ``openflowsheet`` or ``benchmarks``: the numbers it emits are the
expectations the M01 tests judge the implementation against, so they must not come from it. Three
classes of value, labelled as such in the YAML (the convention of ``t05b_reference.py``):

* ``closed_form`` -- expectations, mpmath at 50 significant digits, written to 20.
* ``generator_claims`` -- every statement the specification makes about its own numbers,
  re-derived on every run. The script refuses to emit when one fails.
* ``measured`` -- the same closed forms rerun in 53-bit arithmetic (a transcription, never the
  implementation), used only to argue tolerances. Never an expectation.
* ``assertion_margins`` (spec Amendment 1) -- how far an assertion's expectation sits from its
  53-bit floor and from the nearest plausible wrong answer, each backed by a claim. Never an
  expectation.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/m01_reference.py --check
    python docs/derivations/scripts/m01_reference.py --emit

``--emit`` writes ``benchmarks/m01/reference_values.yaml`` and
``benchmarks/m01/reactor-overlay.json`` byte-reproducibly; ``--check`` regenerates both in memory
and fails unless they equal the committed files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Sequence
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


class UnsupportedError(Exception):
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
        self.tc, self.pc, self.om = (
            g("critical_temperature"),
            g("critical_pressure"),
            g("acentric_factor"),
        )
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
    claim(
        "REC-01",
        tuple(c.id for c in comps) == ORDER,
        f"components.yaml lists {ORDER} in that order",
    )
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


def sqrt_alpha(c: Comp, temp: mpf) -> mpf:
    return 1 + c.kappa * (1 - mp.sqrt(temp / c.tc))


def a_of(c: Comp, temp: mpf) -> mpf:
    return c.ac * sqrt_alpha(c, temp) ** 2


def da_of(c: Comp, temp: mpf) -> mpf:
    return -c.ac * c.kappa * sqrt_alpha(c, temp) / mp.sqrt(temp * c.tc)


def cp_ig(c: Comp, temp: mpf) -> mpf:
    tau = temp / 1000
    return R * sum(c.bk[k] * tau**k for k in range(5))


def h_ig(c: Comp, temp: mpf) -> mpf:
    tau, tau0 = temp / 1000, T0 / 1000
    return c.hf + R * 1000 * sum(
        c.bk[k] * (tau ** (k + 1) - tau0 ** (k + 1)) / (k + 1) for k in range(5)
    )


def mixture(
    comps: Sequence[Comp], temp: mpf, pres: mpf, y: Sequence[mpf], kij: dict[tuple[int, int], mpf]
) -> dict:
    nc = len(comps)
    a = [a_of(c, temp) for c in comps]
    da = [da_of(c, temp) for c in comps]
    k = [
        [kij.get((min(i, j), max(i, j)), mpf(0)) if i != j else mpf(0) for j in range(nc)]
        for i in range(nc)
    ]
    aij = [[mp.sqrt(a[i] * a[j]) * (1 - k[i][j]) for j in range(nc)] for i in range(nc)]
    sums = [sum(y[j] * aij[i][j] for j in range(nc)) for i in range(nc)]
    am = sum(y[i] * sums[i] for i in range(nc))
    dam = sum(
        y[i] * y[j] * (1 - k[i][j]) * (da[i] * a[j] + a[i] * da[j]) / (2 * mp.sqrt(a[i] * a[j]))
        for i in range(nc)
        for j in range(nc)
    )
    bm = sum(y[i] * comps[i].b for i in range(nc))
    aa = am * pres / (R * temp) ** 2
    bb = bm * pres / (R * temp)
    return {
        "a": a,
        "S": sums,
        "am": am,
        "dam": dam,
        "bm": bm,
        "A": aa,
        "B": bb,
        "T": temp,
        "P": pres,
        "y": list(y),
    }


def cubic_coeffs(aa: mpf, bb: mpf) -> list[mpf]:
    return [mpf(1), -(1 - bb), aa - 3 * bb**2 - 2 * bb, -(aa * bb - bb**2 - bb**3)]


def discriminant(aa: mpf, bb: mpf) -> mpf:
    _, b, c, d = cubic_coeffs(aa, bb)
    return 18 * b * c * d - 4 * b**3 * d + b**2 * c**2 - 4 * c**3 - 27 * d**2


def real_roots(aa: mpf, bb: mpf) -> list[mpf]:
    """Real roots Z > B, ascending. Three distinct roots iff the discriminant is positive."""
    disc = discriminant(aa, bb)
    rs = mp.polyroots(cubic_coeffs(aa, bb), maxsteps=400, extraprec=400)
    re = sorted(mp.re(r) for r in rs)
    if disc > 0:
        cand = re
    else:  # one real root: the one with the smallest imaginary part
        cand = [mp.re(min(rs, key=lambda r: abs(mp.im(r))))]
    return [z for z in cand if z > bb]


def log_term(zr: mpf, bb: mpf) -> mpf:
    return mp.log((zr + (1 + SQ2) * bb) / (zr + (1 - SQ2) * bb))


def ln_phi(comps: Sequence[Comp], m: dict, zr: mpf) -> list[mpf]:
    aa, bb, am, bm = m["A"], m["B"], m["am"], m["bm"]
    lt = log_term(zr, bb)
    return [
        comps[i].b / bm * (zr - 1)
        - mp.log(zr - bb)
        - aa / (2 * SQ2 * bb) * (2 * m["S"][i] / am - comps[i].b / bm) * lt
        for i in range(len(comps))
    ]


def h_dep(m: dict, zr: mpf) -> mpf:
    temp = m["T"]
    return R * temp * (zr - 1) + (temp * m["dam"] - m["am"]) / (2 * SQ2 * m["bm"]) * log_term(
        zr, m["B"]
    )


def g_dep(comps: Sequence[Comp], m: dict, zr: mpf) -> mpf:
    """G^dep/RT of the phase at fixed composition, sum y_i ln phi_i."""
    return sum(yi * lp for yi, lp in zip(m["y"], ln_phi(comps, m, zr), strict=False))


# ---- the exact PR critical constants and NH3's EOS critical point (spec section 4.3) -----------


def pr_critical_constants() -> tuple[mpf, mpf, mpf]:
    """B_c, Z_c, A_c from the triple-root conditions of the PR cubic."""

    def f(bb: mpf) -> mpf:
        zcr = (1 - bb) / 3
        aa = 3 * zcr**2 + 3 * bb**2 + 2 * bb
        return zcr**3 - (aa * bb - bb**2 - bb**3)

    bcr = mp.findroot(f, mpf("0.0778"))
    zcr = (1 - bcr) / 3
    acr = 3 * zcr**2 + 3 * bcr**2 + 2 * bcr
    return bcr, zcr, acr


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
    def __init__(
        self, comps: Sequence[Comp], kij: dict[tuple[int, int], mpf] | None = None
    ) -> None:
        self.c = list(comps)
        self.kij = kij or {}
        self.crit = eos_critical(self.c[I_NH3])

    # -- pure NH3 ------------------------------------------------------------------------------
    def pure(self, temp: mpf, pres: mpf) -> dict[str, Any]:
        y = [mpf(0)] * len(self.c)
        y[I_NH3] = mpf(1)
        m = mixture(self.c, temp, pres, y, self.kij)
        rs = real_roots(m["A"], m["B"])
        out: dict[str, Any] = {"m": m, "roots": rs, "liquid": None, "vapour": None}
        if temp >= self.crit["T"]:
            if len(rs) != 1:
                raise RuntimeError("supercritical NH3 with more than one root")
            out["vapour"] = rs[0]
            return out
        if len(rs) == 3:
            out["liquid"], out["vapour"] = rs[0], rs[2]
        elif len(rs) == 1:
            v = rs[0] * R * temp / pres
            if v < self.crit["v"]:
                out["liquid"] = rs[0]
            else:
                out["vapour"] = rs[0]
        else:
            raise RuntimeError(f"unexpected root count {len(rs)}")
        return out

    def pure_stable(self, temp: mpf, pres: mpf) -> str:
        p = self.pure(temp, pres)
        if p["liquid"] is None:
            return "VAPOR"
        if p["vapour"] is None:
            return "LIQUID"
        lpl = ln_phi(self.c, p["m"], p["liquid"])[I_NH3]
        lpv = ln_phi(self.c, p["m"], p["vapour"])[I_NH3]
        return "LIQUID" if lpl <= lpv else "VAPOR"

    # -- evaluate_phase -----------------------------------------------------------------------
    def evaluate(
        self, phase: str, temp: mpf, pres: mpf, n: Sequence[mpf], guard: bool = True
    ) -> dict[str, Any]:
        if not (DOMAIN_T[0] <= temp <= DOMAIN_T[1] and DOMAIN_P[0] <= pres <= DOMAIN_P[1]):
            raise UnsupportedError("out_of_domain")
        ntot = sum(n)
        y = [ni / ntot for ni in n]
        light = sum(n[i] for i in LIGHT)
        if phase == "LIQUID":
            if light > 0:
                raise UnsupportedError("light_gas_in_liquid")
            p = self.pure(temp, pres)
            if p["liquid"] is None:
                raise UnsupportedError("no_liquid_root")
            m, zr = p["m"], p["liquid"]
            lp = ln_phi(self.c, m, zr)
            return self._pack(m, zr, {I_NH3: lp[I_NH3]}, y)
        if light == 0:
            p = self.pure(temp, pres)
            if p["vapour"] is None:
                raise UnsupportedError("no_vapour_root")
            m, zr = p["m"], p["vapour"]
        else:
            m = mixture(self.c, temp, pres, y, self.kij)
            rs = real_roots(m["A"], m["B"])
            zr = rs[-1]
            if guard and len(rs) == 3 and g_dep(self.c, m, rs[0]) < g_dep(self.c, m, rs[-1]):
                raise UnsupportedError("vapour_root_metastable")
        lp = ln_phi(self.c, m, zr)
        return self._pack(m, zr, dict(enumerate(lp)), y)

    def _pack(self, m: dict, zr: mpf, lp: dict[int, mpf], y: Sequence[mpf]) -> dict[str, Any]:
        temp, pres = m["T"], m["P"]
        hig = sum(y[i] * h_ig(self.c[i], temp) for i in range(len(self.c)))
        out = {"Z": zr, "v": zr * R * temp / pres, "h": hig + h_dep(m, zr), "h_dep": h_dep(m, zr)}
        for i, val in lp.items():
            out[f"lnphi_{ORDER[i]}"] = val
        return out

    # -- the flash ----------------------------------------------------------------------------
    def h_eq(
        self, temp: mpf, pres: mpf, w: Sequence[mpf], lnphi_l: mpf, yv: mpf, guard: bool = False
    ) -> mpf:
        n = [mpf(0)] * len(self.c)
        for i, wi in zip(LIGHT, w, strict=False):
            n[i] = (1 - yv) * wi
        n[I_NH3] = yv
        ev = self.evaluate("VAPOR", temp, pres, n, guard=guard)
        return mp.log(yv) + ev["lnphi_NH3"] - lnphi_l

    @staticmethod
    def samples() -> list[mpf]:
        s = [mpf(k) / 64 for k in range(1, 64)]
        s += [1 - mpf(2) ** (-j) for j in range(7, 41)]
        return s

    def y_star(self, temp: mpf, pres: mpf, w: Sequence[mpf]) -> dict[str, Any] | None:
        """Equilibrium vapour NH3 fraction for light-gas proportions w; None if no liquid can
        form.
        """
        if temp >= self.crit["T"]:
            return None
        if self.pure_stable(temp, pres) != "LIQUID":
            return None
        lnphi_l = self.evaluate("LIQUID", temp, pres, [mpf(0), mpf(0), mpf(1), mpf(0), mpf(0)])[
            "lnphi_NH3"
        ]
        lo = mpf(0)
        hi = None
        neg_samples = 0
        for s in self.samples():
            if self.h_eq(temp, pres, w, lnphi_l, s) >= 0:
                hi = s
                break
            lo = s
            neg_samples += 1
        if hi is None:
            return None
        for _ in range(400):
            mid = (lo + hi) / 2
            if self.h_eq(temp, pres, w, lnphi_l, mid) >= 0:
                hi = mid
            else:
                lo = mid
            if hi - lo < mpf(10) ** (-45):
                break
        ys = (lo + hi) / 2
        resid = self.h_eq(temp, pres, w, lnphi_l, ys, guard=True)
        return {"y": ys, "residual": resid, "lnphi_l": lnphi_l, "bracket_index": neg_samples}

    def flash(self, temp: mpf, pres: mpf, n: Sequence[mpf]) -> dict[str, Any]:
        if not (DOMAIN_T[0] <= temp <= DOMAIN_T[1] and DOMAIN_P[0] <= pres <= DOMAIN_P[1]):
            raise UnsupportedError("out_of_domain")
        ntot = sum(n)
        if ntot == 0:
            return {"signature": "ZERO_FLOW", "beta": None}
        light = sum(n[i] for i in LIGHT)
        if light == 0:
            ph = "VAPOR" if temp >= self.crit["T"] else self.pure_stable(temp, pres)
            return {
                "signature": ph,
                "beta": mpf(1) if ph == "VAPOR" else mpf(0),
                "route": "pure_nh3",
            }
        if n[I_NH3] == 0:
            return {"signature": "VAPOR", "beta": mpf(1), "route": "no_nh3"}
        w = [n[i] / light for i in LIGHT]
        ys = self.y_star(temp, pres, w)
        if ys is None:
            route = "supercritical" if temp >= self.crit["T"] else "no_liquid"
            return {"signature": "VAPOR", "beta": mpf(1), "route": route}
        v_nh3 = light * ys["y"] / (1 - ys["y"])
        if n[I_NH3] <= v_nh3:
            return {
                "signature": "VAPOR",
                "beta": mpf(1),
                "route": "undersaturated",
                "y_star": ys["y"],
            }
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


def psat(pr: PR, temp: mpf) -> dict[str, mpf]:
    c = pr.c[I_NH3]
    p0 = c.pc * mpf(10) ** (mpf(7) / 3 * (1 + c.om) * (1 - c.tc / temp))

    def f(lnp: mpf) -> mpf:
        pres = mp.exp(lnp)
        p = pr.pure(temp, pres)
        if p["liquid"] is None or p["vapour"] is None:
            raise RuntimeError("saturation iterate outside the three-root region")
        return ln_phi(pr.c, p["m"], p["liquid"])[I_NH3] - ln_phi(pr.c, p["m"], p["vapour"])[I_NH3]

    lnp = mp.findroot(
        f, (mp.log(p0), mp.log(p0 * mpf("1.01"))), solver="secant", tol=mpf(10) ** (-45)
    )
    pres = mp.exp(lnp)
    p = pr.pure(temp, pres)
    hl = pr._pack(p["m"], p["liquid"], {}, [0, 0, 1, 0, 0])
    hv = pr._pack(p["m"], p["vapour"], {}, [0, 0, 1, 0, 0])
    return {
        "P": pres,
        "v_L": hl["v"],
        "v_V": hv["v"],
        "h_vap": hv["h"] - hl["h"],
        "residual": f(lnp),
    }


def spinodal_volumes(pr: PR, temp: mpf) -> list[mpf]:
    """Real roots v > b of dP/dv = 0 for pure NH3: RT (v^2+2bv-b^2)^2 - 2a (v+b)(v-b)^2 = 0."""
    c = pr.c[I_NH3]
    a, b = a_of(c, temp), c.b

    def pmul(p: list[mpf], q: list[mpf]) -> list[mpf]:
        out = [mpf(0)] * (len(p) + len(q) - 1)
        for i, pi in enumerate(p):
            for j, qj in enumerate(q):
                out[i + j] += pi * qj
        return out

    q = [mpf(1), 2 * b, -(b**2)]
    left = [R * temp * x for x in pmul(q, q)]
    right = [2 * a * x for x in pmul([mpf(1), b], pmul([mpf(1), -b], [mpf(1), -b]))]
    right = [mpf(0)] * (len(left) - len(right)) + right
    poly = [lc - rc for lc, rc in zip(left, right, strict=False)]
    rs = mp.polyroots(poly, maxsteps=400, extraprec=400)
    return sorted(mp.re(r) for r in rs if abs(mp.im(r)) < mpf(10) ** (-30) and mp.re(r) > b)


# ============================================================================================
# 4. Derivatives by 50-digit numerical differentiation (independent of any analytic formula)
# ============================================================================================

PROPS_V = ["Z", "v", "h"] + [f"lnphi_{c}" for c in ORDER]
PROPS_L = ["Z", "v", "h", "lnphi_NH3"]


def derivatives(
    pr: PR, phase: str, temp: mpf, pres: mpf, n: list[mpf]
) -> dict[str, dict[str, mpf]]:
    props = PROPS_V if phase == "VAPOR" else PROPS_L
    out: dict[str, dict[str, mpf]] = {p: {} for p in props}

    def ev(temp2: mpf, pres2: mpf, nn: list[mpf]) -> dict[str, Any]:
        return pr.evaluate(phase, temp2, pres2, nn)

    for p in props:
        out[p]["T"] = mp.diff(lambda x, p=p: ev(x, pres, n)[p], temp)
        out[p]["P"] = mp.diff(lambda x, p=p: ev(temp, x, n)[p], pres)
        for j, cid in enumerate(ORDER):
            if phase == "LIQUID":
                out[p][f"n_{cid}"] = mpf(
                    0
                )  # pure NH3: an intensive property of a fixed composition
                continue

            def fj(x: mpf, j: int = j, p: str = p) -> mpf:
                nn = list(n)
                nn[j] = x
                return ev(temp, pres, nn)[p]

            out[p][f"n_{cid}"] = mp.diff(fj, n[j])
    return out


# ============================================================================================
# 5. 53-bit transcription (measured: tolerance argument only)
# ============================================================================================


def f53_vapour_or_liquid(
    comps: Sequence[Comp], phase: str, temp: float, pres: float, n: Sequence[float]
) -> dict:
    """Peng-Robinson in IEEE double: trigonometric/Cardano roots, two Newton polishes.

    Never an expectation.
    """
    nc = len(comps)
    ntot = sum(n)
    y = [x / ntot for x in n]
    rf = float(R)
    a, da, b = [], [], []
    for c in comps:
        sa = 1.0 + float(c.kappa) * (1.0 - math.sqrt(temp / float(c.tc)))
        a.append(float(c.ac) * sa * sa)
        da.append(-float(c.ac) * float(c.kappa) * sa / math.sqrt(temp * float(c.tc)))
        b.append(float(c.b))
    sums = [sum(y[j] * math.sqrt(a[i] * a[j]) for j in range(nc)) for i in range(nc)]
    am = sum(y[i] * sums[i] for i in range(nc))
    dam = sum(
        y[i] * y[j] * (da[i] * a[j] + a[i] * da[j]) / (2 * math.sqrt(a[i] * a[j]))
        for i in range(nc)
        for j in range(nc)
    )
    bm = sum(y[i] * b[i] for i in range(nc))
    aa = am * pres / (rf * temp) ** 2
    bb = bm * pres / (rf * temp)
    c2, c1, c0 = -(1 - bb), aa - 3 * bb * bb - 2 * bb, -(aa * bb - bb * bb - bb**3)
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
    roots = [z for z in roots if z > bb]
    zr = roots[0] if phase == "LIQUID" else roots[-1]
    for _ in range(2):
        f = ((zr + c2) * zr + c1) * zr + c0
        fp = (3 * zr + 2 * c2) * zr + c1
        zr -= f / fp
    lt = math.log((zr + (1 + math.sqrt(2)) * bb) / (zr + (1 - math.sqrt(2)) * bb))
    lnphi = [
        b[i] / bm * (zr - 1)
        - math.log(zr - bb)
        - aa / (2 * math.sqrt(2) * bb) * (2 * sums[i] / am - b[i] / bm) * lt
        for i in range(nc)
    ]
    hd = rf * temp * (zr - 1) + (temp * dam - am) / (2 * math.sqrt(2) * bm) * lt
    hig = 0.0
    for i, c in enumerate(comps):
        tau, tau0 = temp / 1000.0, float(T0) / 1000.0
        hig += y[i] * (
            float(c.hf)
            + rf
            * 1000.0
            * sum(float(c.bk[k]) * (tau ** (k + 1) - tau0 ** (k + 1)) / (k + 1) for k in range(5))
        )
    return {"Z": zr, "h": hig + hd, **{f"lnphi_{ORDER[i]}": lnphi[i] for i in range(nc)}}


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
    return {
        "xi": xi,
        "n_out": n_out,
        "defect": defect,
        "defect_rel": max(abs(d) for d in defect) / scale,
    }


def fit_dippr107(c: Comp, c3: mpf, c5: mpf) -> dict[str, Any]:
    """Relative least squares of C1 + C2 [(C3/T)/sinh(C3/T)]^2 + C4 [(C5/T)/cosh(C5/T)]^2 to
    NASA c_p, 250-1000 K.
    """
    temps = [mpf(250 + 5 * k) for k in range(151)]
    rows, rhs = [], []
    for temp in temps:
        target = cp_ig(c, temp) * 1000  # J/(kmol K), the reactor's unit
        x, z = c3 / temp, c5 / temp
        rows.append([1 / target, (x / mp.sinh(x)) ** 2 / target, (z / mp.cosh(z)) ** 2 / target])
        rhs.append(mpf(1))
    mat = mp.matrix(3, 3)
    v = mp.matrix(3, 1)
    for r, t in zip(rows, rhs, strict=False):
        for i in range(3):
            v[i] += r[i] * t
            for j in range(3):
                mat[i, j] += r[i] * r[j]
    sol = mp.lu_solve(mat, v)
    c1f, c2f, c4f = (mpf(mp.nstr(sol[i], 6)) for i in range(3))
    dev = max(
        abs(
            (
                c1f
                + c2f * ((c3 / temp) / mp.sinh(c3 / temp)) ** 2
                + c4f * ((c5 / temp) / mp.cosh(c5 / temp)) ** 2
            )
            / (cp_ig(c, temp) * 1000)
            - 1
        )
        for temp in temps
    )
    return {"C1": c1f, "C2": c2f, "C3": c3, "C4": c4f, "C5": c5, "max_rel_dev": dev}


# ============================================================================================
# 7. Registered states (spec section 7.1: why each is in the list)
# ============================================================================================


def m(x: str | float) -> mpf:
    return mpf(str(x))


FEED_REACTOR_INLET = [m("0.70"), m("0.235"), m("0.03"), m("0.015"), m("0.02")]
FEED_SEPARATOR = [m("0.60"), m("0.20"), m("0.165"), m("0.015"), m("0.02")]

PHASE_STATES: list[dict[str, Any]] = [
    {
        "id": "V1",
        "T": m("673.15"),
        "P": m("1e7"),
        "n": FEED_REACTOR_INLET,
        "phase": "VAPOR",
        "expect": "ok",
        "why": (
            "reactor inlet: above NH3's EOS critical temperature, five distinct fugacity "
            "coefficients near one, a nonzero departure enthalpy"
        ),
    },
    {
        "id": "V2",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": [
            m("0.6743819512868283"),
            m("0.22479398376227613"),
            m("0.061485117792505664"),
            m("0.01685954878217071"),
            m("0.022479398376227616"),
        ],
        "phase": "VAPOR",
        "expect": "ok",
        "why": (
            "a cold, NH3-bearing vapour near the separator's equilibrium vapour (the IDAES "
            "composition): strongly nonideal NH3"
        ),
    },
    {
        "id": "L1",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "phase": "LIQUID",
        "expect": "ok",
        "why": "pure NH3 compressed liquid: a single real root, liquid by the critical-volume test",
    },
    {
        "id": "L2",
        "T": m("350"),
        "P": m("1e6"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "phase": "LIQUID",
        "expect": "ok",
        "why": (
            "pure NH3 below its saturation pressure: three real roots; the liquid root is "
            "metastable and still evaluable"
        ),
    },
    {
        "id": "V3",
        "T": m("350"),
        "P": m("1e6"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "phase": "VAPOR",
        "expect": "ok",
        "why": "the same three-root state, vapour root: the largest root, distinct from L2's",
    },
    {
        "id": "V4",
        "T": m("420"),
        "P": m("5e6"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "phase": "VAPOR",
        "expect": "ok",
        "why": "pure NH3 above its EOS critical temperature: one root, labelled vapour",
    },
    {
        "id": "V5",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": [m("0.75"), m("0.25"), m(0), m(0), m(0)],
        "phase": "VAPOR",
        "expect": "ok",
        "why": (
            "light gases only: lnphi_NH3 is NH3 at infinite dilution, defined although NH3 is "
            "absent"
        ),
    },
    {
        "id": "U1",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": [m("1e-6"), m(0), m("0.999999"), m(0), m(0)],
        "phase": "LIQUID",
        "expect": "light_gas_in_liquid",
        "why": "a liquid carrying any light gas is outside the convention",
    },
    {
        "id": "U2",
        "T": m("420"),
        "P": m("5e6"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "phase": "LIQUID",
        "expect": "no_liquid_root",
        "why": "no liquid above NH3's EOS critical temperature",
    },
    {
        "id": "U3",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "phase": "VAPOR",
        "expect": "no_vapour_root",
        "why": "pure compressed liquid NH3 has no vapour-like root",
    },
    {
        "id": "U4",
        "T": m("268.15"),
        "P": m("5e5"),
        "n": [m("0.02"), m(0), m("0.98"), m(0), m(0)],
        "phase": "VAPOR",
        "expect": "vapour_root_metastable",
        "why": (
            "an NH3-rich mixture with three roots whose smallest root is the stable one: the "
            "convention's vapour would be metastable"
        ),
    },
    {
        "id": "U5",
        "T": m("150"),
        "P": m("1e7"),
        "n": FEED_REACTOR_INLET,
        "phase": "VAPOR",
        "expect": "out_of_domain",
        "why": "below the provider's temperature domain (200 K)",
    },
    {
        "id": "U6",
        "T": m("673.15"),
        "P": m("5e7"),
        "n": FEED_REACTOR_INLET,
        "phase": "VAPOR",
        "expect": "out_of_domain",
        "why": "above the provider's pressure domain (3e7 Pa)",
    },
]

FLASH_STATES: list[dict[str, Any]] = [
    {
        "id": "F1",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": FEED_SEPARATOR,
        "expect": "TWO_PHASE",
        "why": (
            "the C1 separator: vapour plus pure liquid NH3 (the IDAES composition, M01's parameter "
            "set)"
        ),
    },
    {
        "id": "F2",
        "T": m("300"),
        "P": m("1e7"),
        "n": FEED_REACTOR_INLET,
        "expect": "VAPOR",
        "route": "undersaturated",
        "why": (
            "subcritical, above NH3's saturation pressure, but the feed holds less NH3 than the "
            "equilibrium vapour can"
        ),
    },
    {
        "id": "F3",
        "T": m("268.15"),
        "P": m("2e5"),
        "n": [m("0.25"), m("0.25"), m("0.5"), m(0), m(0)],
        "expect": "VAPOR",
        "route": "no_liquid",
        "why": "below NH3's saturation pressure: no liquid can form whatever the feed",
    },
    {
        "id": "F4",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": None,
        "expect": "VAPOR_OR_TRACE",
        "route": "dew_point",
        "why": (
            "F1's light gases with exactly the equilibrium vapour's NH3: the dew point, where a "
            "liquid of O(ulp) may appear"
        ),
    },
    {
        "id": "F5",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": [m("1e-6"), m(0), m("0.999999"), m(0), m(0)],
        "expect": "TWO_PHASE",
        "why": (
            "the trivial-solution trap: an NH3 feed with a trace of H2, whose own single root is "
            "liquid-like; the convention's answer is a small H2-rich vapour"
        ),
    },
    {
        "id": "F6",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": [m("0.75"), m("0.25"), m(0), m(0), m(0)],
        "expect": "VAPOR",
        "route": "no_nh3",
        "why": "no NH3: no liquid can exist",
    },
    {
        "id": "F7",
        "T": m("268.15"),
        "P": m("1e7"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "expect": "LIQUID",
        "route": "pure_nh3",
        "why": "pure NH3 above its saturation pressure",
    },
    {
        "id": "F8",
        "T": m("350"),
        "P": m("1e6"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "expect": "VAPOR",
        "route": "pure_nh3",
        "why": "pure NH3 below its saturation pressure: the vapour root has the lower Gibbs energy",
    },
    {
        "id": "F9",
        "T": m("420"),
        "P": m("5e6"),
        "n": [m(0), m(0), m(1), m(0), m(0)],
        "expect": "VAPOR",
        "route": "pure_nh3",
        "why": "pure NH3 above its EOS critical temperature",
    },
    {
        "id": "F10",
        "T": m("673.15"),
        "P": m("1e7"),
        "n": FEED_REACTOR_INLET,
        "expect": "VAPOR",
        "route": "supercritical",
        "why": (
            "the reactor inlet: above NH3's EOS critical temperature, decided without the "
            "equilibrium search"
        ),
    },
    {
        "id": "F11",
        "T": m("250"),
        "P": m("2.5e7"),
        "n": FEED_SEPARATOR,
        "expect": "TWO_PHASE",
        "why": (
            "a colder, higher-pressure separator: a different equilibrium vapour, the same rules"
        ),
    },
    {
        "id": "F12",
        "T": m("400"),
        "P": m("2e7"),
        "n": [m("0.5"), m("0.17"), m("0.3"), m("0.01"), m("0.02")],
        "expect": "ANY",
        "why": (
            "5.6 K below NH3's EOS critical temperature: the adversarial near-critical case, "
            "registered for what the rules give"
        ),
    },
    {
        "id": "F13",
        "T": m("268.15"),
        "P": m("5e5"),
        "n": [m("0.02"), m(0), m("0.98"), m(0), m(0)],
        "expect": "TWO_PHASE",
        "why": (
            "U4's feed: evaluate_phase refuses its vapour root, the flash still finds the "
            "convention's split"
        ),
    },
    {
        "id": "F14",
        "T": m("300"),
        "P": m("1e7"),
        "n": [m(0), m(0), m(0), m(0), m(0)],
        "expect": "ZERO_FLOW",
        "why": "a dormant feed (ADR 0001 D3.4)",
    },
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
            "kappa_rule": (
                "0.37464 + 1.54226 w - 0.26992 w^2 (Peng-Robinson 1976) for every component"
            ),
            "k_ij": "0 for every pair (ADR 0026 D3)",
            "T_ref_K": "298.15",
            "domain": {"T_K": [200.0, 1000.0], "P_Pa": [1.0e4, 3.0e7]},
        },
    }
    cf: dict[str, Any] = {}
    # Amendment 1: each margin an assertion's tolerance argument cites, re-derived on every run.
    margins: dict[str, Any] = {}

    # --- PR constants -----------------------------------------------------------------------------
    res = (1 - BC) / 3 - ZC
    claim(
        "PR-01",
        abs(res) < mpf(10) ** -45 and abs(ZC**3 - (AC * BC - BC**2 - BC**3)) < mpf(10) ** -45,
        "B_c, Z_c, A_c satisfy the PR cubic's triple-root conditions",
    )
    claim(
        "PR-02",
        abs(BC - mpf("0.0777960739")) < mpf("1e-10")
        and abs(AC - mpf("0.4572355289")) < mpf("1e-10"),
        "the exact PR constants round to the textbook 0.0777960739 and 0.4572355289",
    )
    cf["pr_constants"] = {
        "B_c": dstr(BC),
        "Z_c": dstr(ZC),
        "A_c": dstr(AC),
        "theta_c": dstr(THETA_C),
        "v_c_over_b": dstr(ZC / BC),
    }
    comp_out = {}
    for c in comps:
        crit = eos_critical(c)
        comp_out[c.id] = {
            "kappa": nstr(c.kappa),
            "a_c_Pa_m6_per_mol2": nstr(c.ac),
            "b_m3_per_mol": nstr(c.b),
            "T_c_EOS_K": nstr(crit["T"]),
            "sqrt_alpha_at_1000K": nstr(sqrt_alpha(c, mpf(1000))),
            "cp_ig_298_15": nstr(cp_ig(c, T0)),
            "cp_ig_700": nstr(cp_ig(c, mpf(700))),
            "h_ig_700": nstr(h_ig(c, mpf(700))),
            "h_ig_268_15": nstr(h_ig(c, mpf("268.15"))),
        }
        claim(
            f"PR-03-{c.id}",
            sqrt_alpha(c, DOMAIN_T[1]) > 0 and sqrt_alpha(c, DOMAIN_T[0]) > 0,
            f"sqrt(alpha) of {c.id} stays positive on 200-1000 K (it is monotone in T)",
        )
    cf["components"] = comp_out
    crit = pr.crit
    cf["nh3_eos_critical"] = {
        "T_K": nstr(crit["T"]),
        "P_Pa": nstr(crit["P"]),
        "v_m3_per_mol": nstr(crit["v"]),
        "T_c_record_K": nstr(comps[I_NH3].tc),
    }
    # At the EOS critical point the pure cubic has a triple root at Z_c.
    mc = mixture(comps, crit["T"], crit["P"], [0, 0, 1, 0, 0], {})
    claim(
        "PR-04",
        abs(mc["A"] - AC) < mpf(10) ** -40 and abs(mc["B"] - BC) < mpf(10) ** -40,
        (
            "at (T_c,EOS, P_c,EOS) pure NH3's A and B equal the critical A_c, B_c: the closed form "
            "is NH3's EOS critical point"
        ),
    )
    claim(
        "PR-05",
        0 < comps[I_NH3].tc - crit["T"] < mpf("0.02"),
        (
            "with the rounded Omega_a, Omega_b NH3's EOS critical temperature lies below the "
            "record's T_c by less than 0.02 K"
        ),
    )
    spin = {}
    for tk in ("200", "240", "268.15", "300", "350", "400", "405"):
        temp = mpf(tk)
        vs = spinodal_volumes(pr, temp)
        ok = len(vs) == 2 and vs[0] < crit["v"] < vs[1]
        claim(
            f"PR-06-{tk}",
            ok,
            (
                f"at {tk} K NH3's two spinodal volumes straddle v_c,EOS (the single-root label "
                "rule is exact)"
            ),
        )
        spin[tk] = [nstr(v) for v in vs]
    cf["nh3_spinodal_volumes_m3_per_mol"] = spin
    # Amendment 1 (spec section 5.2): the PR cubic at Z = B equals -2 B^2 < 0 and tends to +inf,
    # so its roots above B, counted with multiplicity, are odd in number; two distinct admissible
    # roots occur only at a double root, which the root rules treat like three.
    f_at_b = []
    for s in PHASE_STATES:
        mm = mixture(comps, s["T"], s["P"], [x / sum(s["n"]) for x in s["n"]], {})
        c3, c2, c1, c0 = cubic_coeffs(mm["A"], mm["B"])
        bb = mm["B"]
        f_at_b.append(abs(((c3 * bb + c2) * bb + c1) * bb + c0 + 2 * bb**2) / bb**2)
    claim(
        "PR-07",
        max(f_at_b) < mpf(10) ** -40,
        (
            "at every registered phase state the PR cubic at Z = B equals -2 B^2: the admissible "
            "roots counted with multiplicity are odd in number, so two distinct ones form a double "
            "root"
        ),
    )

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
    phi_dev = max(
        abs(mp.exp(ev08[f"lnphi_{c}"]) / mpf(repr(sep["fug_coeff_vapour"][c])) - 1) for c in ORDER
    )
    lq08 = pr08.evaluate("LIQUID", mpf("268.15"), mpf("1e7"), [0, 0, 1, 0, 0])
    phil_dev = abs(mp.exp(lq08["lnphi_NH3"]) / mpf(repr(sep["fug_coeff_liquid"]["NH3"])) - 1)
    claim(
        "IDAES-01",
        beta_dev < mpf("1e-9")
        and y_dev < mpf("1e-9")
        and phi_dev < mpf("1e-9")
        and phil_dev < mpf("1e-9"),
        (
            "with T08's parameter set this script reproduces IDAES 2.13's vapour-only separator "
            "(beta, y_NH3, five vapour and the liquid fugacity coefficients) to 1e-9"
        ),
    )
    out["transcription_check_vs_idaes"] = {
        "record": "benchmarks/t08/v19/c1-idaes.json pr_flash.light_gases_vapour_only.separator",
        "parameter_set": (
            "T08's (the group database for H2, N2, NH3; IDAES examples for Ar, CH4): used for this "
            "check only"
        ),
        "abs_dev_beta": nstr(beta_dev, 3),
        "abs_dev_y_NH3": nstr(y_dev, 3),
        "max_rel_dev_vapour_phi": nstr(phi_dev, 3),
        "rel_dev_liquid_phi": nstr(phil_dev, 3),
    }

    # --- phase states ----------------------------------------------------------------------------
    ps_out = {}
    evals: dict[str, dict[str, Any]] = {}
    for s in PHASE_STATES:
        rec: dict[str, Any] = {
            "T_K": nstr(s["T"]),
            "P_Pa": nstr(s["P"]),
            "n_mol_s": [nstr(x) for x in s["n"]],
            "phase": s["phase"],
            "why": s["why"],
        }
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
        except UnsupportedError as exc:
            status = exc.code
        rec["status_or_reason"] = status
        claim(f"PH-{s['id']}", status == s["expect"], f"state {s['id']} evaluates to {s['expect']}")
        ps_out[s["id"]] = rec
    claim(
        "PH-ROOTS",
        ps_out["L2"]["real_root_count"] == 3
        and ps_out["V3"]["real_root_count"] == 3
        and ps_out["L1"]["real_root_count"] == 1
        and ps_out["V1"]["real_root_count"] == 1
        and ps_out["V2"]["real_root_count"] == 1,
        "L2/V3 have three real roots; L1, V1 and V2 one",
    )
    claim(
        "PH-DISTINCT",
        len({ps_out[k]["values"]["Z"] for k in ("L2", "V3")}) == 2
        and len({v for k, v in ps_out["V1"]["values"].items() if k.startswith("lnphi")}) == 5
        and len({v for k, v in ps_out["V2"]["values"].items() if k.startswith("lnphi")}) == 5,
        "the three-root state's two roots differ; V1's and V2's five lnphi are pairwise distinct",
    )
    claim(
        "PH-NONZERO",
        all(abs(ev["h_dep"]) > 1 for ev in evals.values()),
        (
            "every evaluated state has a departure enthalpy above 1 J/mol in magnitude: a dropped "
            "departure term changes every h"
        ),
    )
    # Amendment 1 (A09): the smallest pairwise lnphi gap, against A07's tolerance 1e-12.
    gaps: dict[str, dict[str, Any]] = {}
    smallest = []
    for sid in ("V1", "V2"):
        lp = [evals[sid][f"lnphi_{c}"] for c in ORDER]
        gap, i, j = min((abs(lp[i] - lp[j]), i, j) for i in range(5) for j in range(i + 1, 5))
        gaps[sid] = {"pair": f"{ORDER[i]}/{ORDER[j]}", "gap": nstr(gap, 4)}
        smallest.append(gap)
    claim(
        "PH-GAP",
        min(smallest) >= mpf(10) ** 6 * mpf("1e-12"),
        (
            "V1's and V2's five lnphi differ pairwise by at least 1e6 times A07's tolerance 1e-12: "
            "a permuted component index fails A07"
        ),
    )
    margins["A09_min_pairwise_lnphi_gap"] = gaps
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
            claim(
                f"DER-HOM-{sid}",
                hom < mpf(10) ** -25,
                (
                    f"at {sid} every intensive property is homogeneous of degree zero in n (sum_j "
                    "n_j dX/dn_j < 1e-25)"
                ),
            )
            # Gibbs-Duhem at fixed T, P: sum_i n_i d lnphi_i / d n_j = 0 for every j.
            gd = max(
                abs(sum(s["n"][i] * d[f"lnphi_{ORDER[i]}"][f"n_{ORDER[j]}"] for i in range(5)))
                for j in range(5)
            )
            claim(
                f"DER-GD-{sid}",
                gd < mpf(10) ** -25,
                f"at {sid} the lnphi derivatives satisfy Gibbs-Duhem to 1e-25",
            )
            # Symmetry: d lnphi_i/dn_j = d lnphi_j/dn_i (n_tot times a Hessian of G^R).
            sym = max(
                abs(
                    d[f"lnphi_{ORDER[i]}"][f"n_{ORDER[j]}"]
                    - d[f"lnphi_{ORDER[j]}"][f"n_{ORDER[i]}"]
                )
                for i in range(5)
                for j in range(5)
            )
            claim(
                f"DER-SYM-{sid}",
                sym < mpf(10) ** -25,
                f"at {sid} d lnphi_i/d n_j is symmetric to 1e-25",
            )
            nz = min(abs(v) for p in d for v in d[p].values())
            claim(
                f"DER-NZ-{sid}",
                nz > mpf(10) ** -12,
                (
                    f"at {sid} no registered derivative vanishes (smallest magnitude above 1e-12): "
                    "no assertion is met by an accidental zero"
                ),
            )
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
        rec = {
            "T_K": nstr(s["T"]),
            "P_Pa": nstr(s["P"]),
            "n_mol_s": [nstr(x) for x in n],
            "why": s["why"],
            "phase_signature": r["signature"],
            "route": r.get("route", "zero_flow"),
        }
        if r.get("beta") is not None:
            rec["vapor_fraction"] = nstr(r["beta"])
        for key in ("y_star", "v_nh3", "l_nh3"):
            if key in r:
                rec[key] = nstr(r[key])
        if r["signature"] == "TWO_PHASE":
            claim(
                f"FL-EQ-{s['id']}",
                abs(r["residual"]) < mpf(10) ** -40,
                (
                    f"at {s['id']} the equilibrium row ln y* + lnphi_NH3^V - lnphi_NH3^L vanishes "
                    "to 1e-40"
                ),
            )
            vap = list(n)
            vap[I_NH3] = r["v_nh3"]
            ev = pr.evaluate("VAPOR", s["T"], s["P"], vap)
            lq = pr.evaluate("LIQUID", s["T"], s["P"], [0, 0, r["l_nh3"], 0, 0])
            rec["vapour"] = {
                "n_mol_s": [nstr(x) for x in vap],
                "h_J_mol": nstr(ev["h"]),
                "Z": nstr(ev["Z"]),
                **{k: nstr(v) for k, v in ev.items() if k.startswith("lnphi")},
            }
            rec["liquid"] = {
                "n_NH3_mol_s": nstr(r["l_nh3"]),
                "h_J_mol": nstr(lq["h"]),
                "Z": nstr(lq["Z"]),
                "lnphi_NH3": nstr(lq["lnphi_NH3"]),
            }
            rec["k_value_NH3"] = nstr(r["y_star"])
            rec["bracket_sample_index"] = r["bracket_index"]
            mm = mixture(comps, s["T"], s["P"], [x / sum(vap) for x in vap], {})
            rec["vapour_real_root_count"] = len(real_roots(mm["A"], mm["B"]))
            if s["id"] in ("F1", "F5", "F11"):
                claim(
                    f"FL-ROOT-{s['id']}",
                    rec["vapour_real_root_count"] == 1,
                    (
                        f"at {s['id']} (100-250 bar) the equilibrium vapour's cubic has a single "
                        "real root"
                    ),
                )
        if s["expect"] == "VAPOR_OR_TRACE":
            ok = r["signature"] == "VAPOR" or (
                r["signature"] == "TWO_PHASE" and r["l_nh3"] < mpf("1e-15")
            )
        elif s["expect"] == "ANY":
            ok = True
        else:
            ok = r["signature"] == s["expect"] and (
                "route" not in s or r.get("route") == s["route"]
            )
        claim(
            f"FL-{s['id']}",
            ok,
            (
                f"flash {s['id']} gives "
                f"{s['expect']}{' by route ' + s['route'] if 'route' in s else ''}"
            ),
        )
        if s["id"] == "F1":
            f1 = r
        fl_out[s["id"]] = rec
    # y* depends on (T, P, light-gas proportions) only: F1 with twice its NH3 has the same y*.
    nn = list(FEED_SEPARATOR)
    nn[I_NH3] *= 2
    r2 = pr.flash(mpf("268.15"), mpf("1e7"), nn)
    claim(
        "FL-INDEP",
        r2["y_star"] == f1["y_star"],
        (
            "the equilibrium vapour composition does not depend on the feed's NH3 (F1 with doubled "
            "NH3)"
        ),
    )
    # Monotone below y*: every sample below the bracket has h < 0 (checked by construction);
    # report F1's.
    claim(
        "FL-F5-ROOT",
        fl_out["F5"]["y_star"] < 0.2,
        "F5's vapour holds NH3 at y* < 0.2: the H2-rich vapour, not the trivial liquid-like root",
    )
    cf["flash_states"] = fl_out

    # --- W22: pure-NH3 saturation by this PR (compared externally with the reference EOS) ---------
    sat = {}
    for tk in ("240", "260", "268.15", "280", "300", "320", "350", "380", "400"):
        ps = psat(pr, mpf(tk))
        claim(
            f"SAT-{tk}",
            abs(ps["residual"]) < mpf(10) ** -35,
            f"PR saturation at {tk} K solved to 1e-35 in lnphi",
        )
        sat[tk] = {
            "P_sat_Pa": nstr(ps["P"]),
            "v_L_m3_mol": nstr(ps["v_L"]),
            "v_V_m3_mol": nstr(ps["v_V"]),
            "h_vap_J_mol": nstr(ps["h_vap"]),
        }
    cf["nh3_saturation_pr"] = sat

    # --- W22: pure-component fugacity coefficients at loop states (compared externally) -----------
    pure_states = {}
    for i, cid in enumerate(ORDER):
        for tk, pk, phase in (
            ("268.15", "1e7", "VAPOR"),
            ("673.15", "1e7", "VAPOR"),
            ("268.15", "1e7", "LIQUID"),
            ("250", "2.5e7", "LIQUID"),
        ):
            if (phase == "LIQUID") != (i == I_NH3) and not (i == I_NH3 and tk == "673.15"):
                continue
            if i == I_NH3 and phase == "VAPOR" and tk == "268.15":
                continue
            n = [mpf(0)] * 5
            n[i] = mpf(1)
            ev = pr.evaluate(phase, mpf(tk), mpf(pk), n)
            pure_states[f"{cid}-{phase}-{tk}-{pk}"] = {
                "T_K": nstr(mpf(tk)),
                "P_Pa": nstr(mpf(pk)),
                "phase": phase,
                "lnphi": nstr(ev[f"lnphi_{cid}"]),
                "Z": nstr(ev["Z"]),
                "h_departure_J_mol": nstr(ev["h_dep"]),
            }
    cf["pure_component_states"] = pure_states
    claim(
        "SAT-F3",
        mpf("2e5") < mpf(str(sat["268.15"]["P_sat_Pa"]))
        and mpf(str(sat["268.15"]["P_sat_Pa"])) < mpf("1e7"),
        "268.15 K: F3's 2e5 Pa lies below and F1's 1e7 Pa above PR's NH3 saturation pressure",
    )

    # --- reaction datum and elements --------------------------------------------------------------
    elems, emat = element_matrix(comps)
    claim(
        "RX-01",
        all(sum(emat[e][i] * NU[i] for i in range(5)) == 0 for e in range(len(elems))),
        "E nu = 0 for every element: the reaction conserves H, N, C and Ar",
    )
    dh298 = sum(NU[i] * h_ig(comps[i], T0) for i in range(5))
    claim(
        "RX-02",
        dh298 == 2 * comps[I_NH3].hf,
        "sum nu_i h_i^ig(298.15 K) = 2 dfH(NH3) exactly: PR-C1-ref-v1 is a formation datum",
    )
    dh673 = sum(NU[i] * h_ig(comps[i], mpf("673.15")) for i in range(5))
    cf["reaction"] = {
        "elements": elems,
        "element_matrix": emat,
        "nu": list(NU),
        "dh_r_ig_298_15_J_mol": nstr(dh298),
        "dh_r_ig_673_15_J_mol": nstr(dh673),
    }

    # --- k_ij sensitivity at F1 (stated effect of k_ij = 0) ---------------------------------------
    sens = {}
    for i, j in ((0, 2), (1, 2), (2, 3), (2, 4), (0, 1)):
        vals = {}
        for k in ("-0.1", "0.1", "0.2"):
            prk = PR(comps, {(i, j): mpf(k)})
            rk = prk.flash(mpf("268.15"), mpf("1e7"), FEED_SEPARATOR)
            vals[k] = {
                "y_star": nstr(rk["y_star"], 8),
                "rel_change_y_star": nstr(rk["y_star"] / f1["y_star"] - 1, 4),
            }
        sens[f"{ORDER[i]}-{ORDER[j]}"] = vals
    cf["kij_sensitivity_F1"] = sens

    # --- reactor boundary: projection and the synthetic stand-in ----------------------------------
    n_in = FEED_REACTOR_INLET
    xs = mpf("0.25") * n_in[1]
    n_exact = [n_in[i] + NU[i] * xs for i in range(5)]
    d = [mpf("2e-6"), mpf("-1e-6"), mpf("3e-6"), mpf("1e-7"), mpf(0)]
    n_raw = [n_exact[i] + d[i] for i in range(5)]
    pj = project_outlet(n_in, n_raw)
    claim(
        "BD-01",
        abs(pj["xi"] - (xs + mpf("1e-6") / 14)) < mpf(10) ** -40,
        "the least-squares extent of the perturbed outlet is xi_s + (nu . d)/14 = xi_s + 1e-6/14",
    )
    elem_out = [
        sum(emat[e][i] * pj["n_out"][i] for i in range(5))
        - sum(emat[e][i] * n_in[i] for i in range(5))
        for e in range(len(elems))
    ]
    claim(
        "BD-02",
        max(abs(x) for x in elem_out) < mpf(10) ** -40,
        "the projected outlet conserves every element exactly",
    )
    ev_in = pr.evaluate("VAPOR", mpf("673.15"), mpf("1e7"), n_in)
    ev_out = pr.evaluate("VAPOR", mpf("673.15"), mpf("1e7"), n_exact)
    q_w = sum(n_exact) * ev_out["h"] - sum(n_in) * ev_in["h"]
    claim(
        "BD-03",
        q_w < 0,
        (
            "the isothermal stand-in at 673.15 K removes heat (Q < 0): the reaction is exothermic "
            "on the datum"
        ),
    )
    # Amendment 1 (A26): spec section 8.9 in 53-bit arithmetic on the registered inputs as a double
    # implementation reads them, and the plausible wrong projections, against A26's flow-scale
    # tolerance 1e-13 x n_tot,in (defect vector, defect_rel and the element balances).
    a26_tol = mpf("1e-13")
    n_tot_in = sum(n_in)
    fin = [nstr(x) for x in n_in]
    fraw = [nstr(x) for x in n_raw]
    xi53 = sum(NU[i] * (fraw[i] - fin[i]) for i in REACTIVE) / 14.0
    out53 = [fin[i] + NU[i] * xi53 for i in range(5)]
    d53 = [fraw[i] - out53[i] for i in range(5)]
    floor_defect = max(abs(mpf(d53[i]) - pj["defect"][i]) for i in range(5)) / n_tot_in
    floor_defect_rel = max(
        abs(mpf(d53[i]) / pj["defect"][i] - 1) for i in range(5) if pj["defect"][i] != 0
    )
    elem_float = (
        max(
            abs(
                mpf(sum(emat[e][i] * out53[i] for i in range(5)))
                - mpf(sum(emat[e][i] * fin[i] for i in range(5)))
            )
            for e in range(len(elems))
        )
        / n_tot_in
    )
    elem_exact = (
        max(
            abs(sum(emat[e][i] * (mpf(out53[i]) - mpf(fin[i])) for i in range(5)))
            for e in range(len(elems))
        )
        / n_tot_in
    )
    claim(
        "BD-04",
        1000 * max(floor_defect, elem_float, elem_exact) <= a26_tol,
        (
            "the 53-bit projection of the registered raw outlet meets the 50-digit defect vector "
            "and conserves every element to 1e-3 of A26's tolerance 1e-13 x n_tot,in"
        ),
    )
    num = sum(NU[i] * (n_raw[i] - n_in[i]) for i in REACTIVE)
    wrong_xi = {
        "extent_from_H2_alone": -(n_raw[0] - n_in[0]) / 3,
        "extent_from_N2_alone": -(n_raw[1] - n_in[1]),
        "extent_from_NH3_alone": (n_raw[2] - n_in[2]) / 2,
        "extent_divided_by_13": num / 13,
        "extent_sign_reversed": -num / 14,
    }
    changes = {}
    for name, xw in wrong_xi.items():
        dw = [n_raw[i] - (n_in[i] + NU[i] * xw) for i in range(5)]
        changes[name] = max(abs(dw[i] - pj["defect"][i]) for i in range(5)) / n_tot_in
    nu_swapped = (-1, -3, 2, 0, 0)
    xs_swap = sum(nu_swapped[i] * (n_raw[i] - n_in[i]) for i in REACTIVE) / 14
    dw = [n_raw[i] - (n_in[i] + nu_swapped[i] * xs_swap) for i in range(5)]
    changes["nu_H2_N2_permuted"] = max(abs(dw[i] - pj["defect"][i]) for i in range(5)) / n_tot_in
    changes["inert_defect_dropped"] = abs(pj["defect"][3]) / n_tot_in
    claim(
        "BD-05",
        min(changes.values()) >= 1000 * a26_tol,
        (
            "every listed wrong projection (one-species extent, divisor 13, reversed sign, H2/N2 "
            "stoichiometry permuted, inert defect dropped) moves the defect vector by at least 1e3 "
            "times A26's tolerance"
        ),
    )
    claim(
        "BD-06",
        mpf("573.15") > pr.crit["T"],
        (
            "the adapter's hard domain starts above NH3's EOS critical temperature, so no inlet "
            "inside it flashes to a liquid: liquid_at_reactor_inlet is reachable only outside it, "
            "and the boundary checks the inlet phase first"
        ),
    )
    margins["A26_projection"] = {
        "tolerance_over_n_tot_in": "1e-13",
        "floor_defect_over_n_tot_in": nstr(floor_defect, 3),
        "floor_defect_relative_to_itself": nstr(floor_defect_rel, 3),
        "floor_element_balance_float_over_n_tot_in": nstr(elem_float, 3),
        "floor_element_balance_exact_over_n_tot_in": nstr(elem_exact, 3),
        "wrong_projection_change_over_n_tot_in": {k: nstr(v, 3) for k, v in changes.items()},
    }
    cf["boundary"] = {
        "standin": {
            "conversion_N2": "0.25",
            "inlet_n_mol_s": [nstr(x) for x in n_in],
            "T_in_K": 673.15,
            "P_in_Pa": 1.0e7,
            "xi_mol_s": nstr(xs),
            "outlet_n_mol_s": [nstr(x) for x in n_exact],
            "T_out_K": 673.15,
            "P_out_Pa": 1.0e7,
            "Q_W": nstr(q_w),
            "H_in_W": nstr(sum(n_in) * ev_in["h"]),
            "H_out_W": nstr(sum(n_exact) * ev_out["h"]),
            "Q_over_xi_J_mol": nstr(q_w / xs),
        },
        "projection": {
            "perturbation_mol_s": [nstr(x) for x in d],
            "raw_outlet_mol_s": [nstr(x) for x in n_raw],
            "xi_mol_s": nstr(pj["xi"]),
            "projected_outlet_mol_s": [nstr(x) for x in pj["n_out"]],
            "defect_mol_s": [nstr(x) for x in pj["defect"]],
            "defect_rel": nstr(pj["defect_rel"]),
        },
        "pressure_convention": {
            "eps_P": "1e-3",
            "accepted_dP_Pa": 5000.0,
            "refused_dP_Pa": 20000.0,
            "P_in_Pa": 1.0e7,
        },
    }

    # --- reactor overlay rows (ADR 0027 D5) -------------------------------------------------------
    fit = fit_dippr107(comps[4], mpf(2000), mpf(1000))
    claim(
        "OV-01",
        fit["max_rel_dev"] < mpf("0.005"),
        "the CH4 DIPPR-107 fit stays within 0.5 % of NASA c_p on 250-1000 K",
    )
    ar_c1 = R * mpf("2.5") * 1000
    claim(
        "OV-02",
        all(b == 0 for b in comps[3].bk[1:]) and comps[3].bk[0] == mpf("2.5"),
        "Ar's NASA c_p is exactly 5/2 R, so its DIPPR-107 row is C1 = 2500 R, C2 = C4 = 0",
    )
    overlay = {
        "record": "m01-reactor-overlay",
        "version": 1,
        "reactor_commit": REACTOR_PIN,
        "specification": "docs/derivations/M01-spec.md section 8.6; ADR 0027 D5",
        "generator": "docs/derivations/scripts/m01_reference.py",
        "meaning": (
            "Rows the pinned reactor's property database lacks (it holds H2, N2, NH3 only). The "
            "adapter merges them into a copy of the pinned "
            "src/reactor/data/properties_database.json read from the pinned checkout at run time; "
            "the group's file is never copied into this repository. 'copy_from' names a row of "
            "that pinned file whose columns are copied (the transport surrogate)."
        ),
        "species_properties": {
            "Ar": {
                "Mw": float(comps[3].mw),
                "Tc": float(comps[3].tc),
                "Pc": float(comps[3].pc),
                "omega": float(comps[3].om),
                "c_p_C1": float(mp.nstr(ar_c1, 15)),
                "c_p_C2": 0.0,
                "c_p_C3": 1.0,
                "c_p_C4": 0.0,
                "c_p_C5": 1.0,
                "dH_f": float(comps[3].hf),
                "copy_from": {
                    "row": "N2",
                    "columns": [
                        "wilke_C1",
                        "wilke_C2",
                        "wilke_C3",
                        "wilke_C4",
                        "therm_cond_C1",
                        "therm_cond_C2",
                        "therm_cond_C3",
                        "therm_cond_C4",
                    ],
                },
            },
            "CH4": {
                "Mw": float(comps[4].mw),
                "Tc": float(comps[4].tc),
                "Pc": float(comps[4].pc),
                "omega": float(comps[4].om),
                "c_p_C1": float(fit["C1"]),
                "c_p_C2": float(fit["C2"]),
                "c_p_C3": float(fit["C3"]),
                "c_p_C4": float(fit["C4"]),
                "c_p_C5": float(fit["C5"]),
                "dH_f": float(comps[4].hf),
                "copy_from": {
                    "row": "N2",
                    "columns": [
                        "wilke_C1",
                        "wilke_C2",
                        "wilke_C3",
                        "wilke_C4",
                        "therm_cond_C1",
                        "therm_cond_C2",
                        "therm_cond_C3",
                        "therm_cond_C4",
                    ],
                },
            },
        },
        "binary_properties": {
            "H2/Ar": {"copy_from": "H2/N2"},
            "N2/Ar": {"copy_from": "N2/NH3"},
            "NH3/Ar": {"copy_from": "N2/NH3"},
            "H2/CH4": {"copy_from": "H2/N2"},
            "N2/CH4": {"copy_from": "N2/NH3"},
            "NH3/CH4": {"copy_from": "N2/NH3"},
            "Ar/CH4": {"copy_from": "N2/NH3"},
        },
        "provenance": {
            "Mw, Tc, Pc, omega, dH_f": "benchmarks/m01/components.yaml (the M01 records)",
            "Ar c_p": (
                "5/2 R exactly (monatomic ideal gas; NASA TM-4513's Ar low range is the same "
                "constant)"
            ),
            "CH4 c_p": (
                "relative least-squares fit of the DIPPR-107 form with C3 = 2000 K and C5 = 1000 K "
                "fixed (M01's choice) to NASA TM-4513's c_p on 250-1000 K step 5 K; C1, C2, C4 "
                "rounded to 6 significant digits; max relative deviation "
                f"{mp.nstr(fit['max_rel_dev'], 3)}"
            ),
            "transport columns and binary rows": (
                "surrogates copied from the pinned database's N2 row and N2 pairs (M01's choice; "
                "its effect is measured by the reactor probe's inert-transport variant)"
            ),
        },
    }
    cf["overlay_fit"] = {"max_rel_dev": nstr(fit["max_rel_dev"], 4)}

    # --- measured: 53-bit transcription floor -----------------------------------------------------
    meas = {}
    for sid in ("V1", "V2", "L1"):
        s = next(x for x in PHASE_STATES if x["id"] == sid)
        f = f53_vapour_or_liquid(
            comps, s["phase"], float(s["T"]), float(s["P"]), [float(x) for x in s["n"]]
        )
        ref = evals[sid]
        keys = ["Z", "h"] + (
            [f"lnphi_{c}" for c in ORDER] if s["phase"] == "VAPOR" else ["lnphi_NH3"]
        )
        meas[sid] = {k: nstr(abs(mpf(f[k]) - ref[k]) / max(abs(ref[k]), mpf(1)), 3) for k in keys}
    out["measured"] = {
        "meaning": (
            "|53-bit transcription - 50-digit closed form| / max(|value|, 1): the double-precision "
            "floor the tolerances of spec section 9 sit above"
        ),
        "transcription_floor": meas,
    }

    # --- derived from the measured reactor record (regression only) -------------------------------
    if PROBE_RECORD.exists():
        probe = json.loads(PROBE_RECORD.read_text(encoding="utf-8"))
        if probe.get("record") == "m01-reactor-probe" and probe.get("version", 0) >= 2:
            out["derived_from_measured"] = derived_from_probe(pr, probe)

    out["assertion_margins"] = {
        "meaning": (
            "spec section 9 Amendment 1: the distance of each registered expectation from the "
            "nearest plausible wrong answer and from the 53-bit floor, re-derived on every run; "
            "arguments for tolerances, never expectations"
        ),
        **margins,
    }
    out["closed_form"] = cf
    out["generator_claims"] = CLAIMS[:]
    return out, overlay


def derived_from_probe(pr: PR, probe: dict[str, Any]) -> dict[str, Any]:
    nom = probe["pinned"]
    n_in = [mpf(repr(x)) for x in nom["inlet_n_mol_s"]]
    n_raw = [mpf(repr(x)) for x in nom["outlet_n_mol_s"]]
    pj = project_outlet(n_in, n_raw)
    t_in, pres = mpf(repr(nom["T_in_K"])), mpf(repr(nom["P_in_Pa"]))
    t_out = mpf(repr(nom["T_out_K"]))
    h_in = pr.evaluate("VAPOR", t_in, pres, n_in)["h"] * sum(n_in)
    h_out = pr.evaluate("VAPOR", t_out, pres, pj["n_out"])["h"] * sum(pj["n_out"])
    return {
        "meaning": (
            "process-side quantities at the pinned grid's nominal solve, computed from the "
            "measured record: regression values, not validation"
        ),
        "probe_sha256": hashlib.sha256(PROBE_RECORD.read_bytes()).hexdigest(),
        "xi_mol_s": nstr(pj["xi"], 12),
        "projected_outlet_mol_s": [nstr(x, 12) for x in pj["n_out"]],
        "defect_rel": nstr(pj["defect_rel"], 3),
        "Q_process_W": nstr(h_out - h_in, 10),
        "Q_reactor_coolant_W": nom.get("coolant_heat_uptake_W"),
        "discretization_estimate": discretization_estimate(probe),
    }


def discretization_estimate(probe: dict[str, Any]) -> dict[str, Any]:
    """Spec section 10.1's registered estimate at the design grid, from the record (Amendment 1).

    Orders p from the successive outlet-NH3 differences 200/400/800 and 400/800/1600 (1600: the
    record's last fine-polish state, not accepted); for each p, the 800 error from the 400->800
    difference (times 2^-p/(1-2^-p)) and from the 800->1600 difference (times 1/(1-2^-p)); the
    estimate is the range of the four, relative to the extrapolated value. T_out uses the same p.
    """
    grid = {g["num_z"]: g for g in probe["grid"]}
    polished = grid[1600]["fine_polish"][-1]
    nh3 = {k: mpf(repr(grid[k]["outlet_n_mol_s"][I_NH3])) for k in (200, 400, 800)}
    nh3[1600] = mpf(repr(polished["NH3_out_mol_s"]))
    t_out = {k: mpf(repr(grid[k]["T_out_K"])) for k in (200, 400, 800)}
    t_out[1600] = mpf(repr(polished["T_out_K"]))
    produced = nh3[800] - mpf(repr(probe["pinned"]["inlet_n_mol_s"][I_NH3]))
    d0, d1, d2 = nh3[400] - nh3[200], nh3[800] - nh3[400], nh3[1600] - nh3[800]
    orders = sorted([mp.log(d0 / d1, 2), mp.log(d1 / d2, 2)])

    def errors(e1: mpf, e2: mpf) -> list[mpf]:
        out = []
        for p in orders:
            q = mpf(2) ** -p
            out += [-e2 / (1 - q), -e1 * q / (1 - q)]
        return out

    e_n = errors(d1, d2)
    e_t = errors(t_out[800] - t_out[400], t_out[1600] - t_out[800])
    nh3_high = [e / (nh3[800] - e) for e in e_n]
    xi_high = [e / (produced - e) for e in e_n]
    t_low = [-e for e in e_t]
    printed = {  # spec section 10.1 as printed (Amendment 1 corrects T_out's lower end)
        "p": (0.62, 0.78, orders, 2),
        "NH3 %": (1.0, 1.4, [100 * x for x in nh3_high], 1),
        "xi %": (1.4, 1.9, [100 * x for x in xi_high], 1),
        "T_out K": (1.2, 1.7, t_low, 1),
    }
    claim(
        "DX-01",
        all(
            round(float(min(v)), d) == lo and round(float(max(v)), d) == hi
            for lo, hi, v, d in printed.values()
        ),
        (
            "the registered discretization estimate at num_z = 800, recomputed from the probe "
            "record, rounds to spec section 10.1's printed ranges (p 0.62-0.78; NH3 high "
            "1.0-1.4 %; xi high 1.4-1.9 %; T_out low 1.2-1.7 K)"
        ),
    )
    return {
        "meaning": (
            "spec section 10.1's discretization estimate at the design grid (Richardson, two "
            "orders, two differences); an estimate, not a bound; what every reactor result "
            "reports (section 8.12, M01.A48)"
        ),
        "num_z": 800,
        "order_p": [nstr(p, 4) for p in orders],
        "NH3_out_high_rel": [nstr(min(nh3_high), 4), nstr(max(nh3_high), 4)],
        "xi_high_rel": [nstr(min(xi_high), 4), nstr(max(xi_high), 4)],
        "T_out_low_K": [nstr(min(t_low), 4), nstr(max(t_low), 4)],
        "inputs": (
            "grid 200, 400, 800 (accepted); 1600 fine_polish[-1] (not accepted: element defect "
            "2.2e-6, still moving)"
        ),
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
        print(
            f"wrote {OUT_YAML.relative_to(ROOT)} and {OVERLAY_JSON.relative_to(ROOT)}; "
            f"{len(CLAIMS)} claims hold"
        )
        return 0
    ok = OUT_YAML.exists() and OUT_YAML.read_text(encoding="utf-8") == text
    ok2 = OVERLAY_JSON.exists() and OVERLAY_JSON.read_text(encoding="utf-8") == otext
    print(
        f"{len(CLAIMS)} claims hold; reference_values.yaml {'matches' if ok else 'DIFFERS'}; "
        f"reactor-overlay.json {'matches' if ok2 else 'DIFFERS'}"
    )
    return 0 if ok and ok2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
