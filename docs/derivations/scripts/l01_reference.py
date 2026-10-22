"""Closed-form reference generator for L01: the vapour-only Peng-Robinson library route `pr-lib-v1`.

Normative text: ``docs/derivations/L01-spec.md`` sections 4.2 and 5 (L01.A15-A21), ADR 0043, and
the method of ADR 0026 (M01 spec section 4). Input: ``benchmarks/l01/components.yaml`` (the nine
records). Output: ``benchmarks/l01/reference_values.yaml``.

It imports nothing from ``openflowsheet`` or ``benchmarks``: the numbers it emits are the
expectations the L01 provider tests judge the implementation against, so they must not come from it.
This is its own transcription of the equations, written as ``m01_reference.py`` is (mixing on
sqrt(a_i a_j), roots by ``mpmath.polyroots``, derivatives by ``mpmath.diff``), never a copy of the
provider. Two classes of value, labelled as such in the YAML:

* ``closed_form`` -- expectations, mpmath at 50 significant digits, written to 20.
* ``generator_claims`` -- every statement the specification makes about its own numbers,
  re-derived on every run. The script refuses to emit when one fails; in particular unless V1L,
  V2L and P1 are admitted (spec section 5).

Run from the repository root inside the project environment::

    python docs/derivations/scripts/l01_reference.py --check
    python docs/derivations/scripts/l01_reference.py --emit

``--emit`` writes ``benchmarks/l01/reference_values.yaml`` byte-reproducibly; ``--check``
regenerates it in memory and fails unless it equals the committed file.
"""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Callable, Sequence
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml
from mpmath import mp, mpf

mp.dps = 50

ROOT = Path(__file__).resolve().parents[3]
COMPONENTS_YAML = ROOT / "benchmarks" / "l01" / "components.yaml"
OUT_YAML = ROOT / "benchmarks" / "l01" / "reference_values.yaml"

ORDER = ("H2", "N2", "Ar", "CH4", "H2O", "CO2", "O2", "C2H6", "C3H8")
NC = len(ORDER)
R = mpf("8.31446261815324")  # J/(mol K), exact in the 2019 SI
OMEGA_A = mpf("0.45724")  # Peng and Robinson (1976), as rounded there (ADR 0026 D1)
OMEGA_B = mpf("0.07780")
T0 = mpf("298.15")
SQ2 = mp.sqrt(2)
DOMAIN_T = (mpf(200), mpf(1000))
DOMAIN_P = (mpf("1e4"), mpf("3e7"))

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


def m(x: str | float) -> mpf:
    return mpf(str(x))


# ============================================================================================
# 1. Records
# ============================================================================================


class Comp:
    def __init__(self, rec: dict[str, Any]) -> None:
        p = rec["parameters"]

        def g(name: str) -> mpf:
            return mpf(repr(float(p[name]["value"])))

        self.id = rec["id"]
        self.tc = g("critical_temperature")
        self.pc = g("critical_pressure")
        self.om = g("acentric_factor")
        self.hf = g("standard_formation_enthalpy")
        self.bk = [g(f"ideal_gas_cp_b{k}") for k in range(5)]
        self.kappa = mpf("0.37464") + mpf("1.54226") * self.om - mpf("0.26992") * self.om**2
        self.ac = OMEGA_A * R**2 * self.tc**2 / self.pc
        self.b = OMEGA_B * R * self.tc / self.pc


def load_components() -> list[Comp]:
    doc = yaml.safe_load(COMPONENTS_YAML.read_text(encoding="utf-8"))
    comps = [Comp(r) for r in doc["components"]]
    claim("REC-01", tuple(c.id for c in comps) == ORDER, f"components.yaml lists {ORDER} in order")
    claim(
        "REC-02",
        doc["reference_convention"] == "PR-C1-ref-v1",
        "the records' reference convention is PR-C1-ref-v1 (ADR 0043 D4)",
    )
    return comps


# ============================================================================================
# 2. Peng-Robinson closed forms (M01 spec section 4; ADR 0026 D1, D3, D4)
# ============================================================================================


def pr_critical_constants() -> tuple[mpf, mpf]:
    """B_c and Z_c from the triple-root conditions of the PR cubic."""

    def f(bb: mpf) -> mpf:
        zcr = (1 - bb) / 3
        aa = 3 * zcr**2 + 3 * bb**2 + 2 * bb
        return zcr**3 - (aa * bb - bb**2 - bb**3)

    bcr = mp.findroot(f, mpf("0.0778"))
    return bcr, (1 - bcr) / 3


BC, ZC = pr_critical_constants()
VC_OVER_B = ZC / BC


def a_of(c: Comp, temp: mpf) -> mpf:
    return c.ac * (1 + c.kappa * (1 - mp.sqrt(temp / c.tc))) ** 2


def da_of(c: Comp, temp: mpf) -> mpf:
    return -c.ac * c.kappa * (1 + c.kappa * (1 - mp.sqrt(temp / c.tc))) / mp.sqrt(temp * c.tc)


def h_ig(c: Comp, temp: mpf) -> mpf:
    tau, tau0 = temp / 1000, T0 / 1000
    return c.hf + R * 1000 * sum(
        c.bk[k] * (tau ** (k + 1) - tau0 ** (k + 1)) / (k + 1) for k in range(5)
    )


class Mix:
    """The van der Waals one-fluid mixture (k_ij = 0) at (T, P, y)."""

    def __init__(self, comps: Sequence[Comp], temp: mpf, pres: mpf, y: Sequence[mpf]) -> None:
        a = [a_of(c, temp) for c in comps]
        da = [da_of(c, temp) for c in comps]
        aij = [[mp.sqrt(a[i] * a[j]) for j in range(NC)] for i in range(NC)]
        self.comps, self.temp, self.pres, self.y = comps, temp, pres, list(y)
        self.sums = [sum(y[j] * aij[i][j] for j in range(NC)) for i in range(NC)]
        self.am = sum(y[i] * self.sums[i] for i in range(NC))
        self.dam = sum(
            y[i] * y[j] * (da[i] * a[j] + a[i] * da[j]) / (2 * aij[i][j])
            for i in range(NC)
            for j in range(NC)
        )
        self.bm = sum(y[i] * comps[i].b for i in range(NC))
        self.aa = self.am * pres / (R * temp) ** 2
        self.bb = self.bm * pres / (R * temp)

    def roots(self) -> list[mpf]:
        """Real roots Z > B, ascending. Three distinct roots iff the discriminant is positive."""
        aa, bb = self.aa, self.bb
        b, c, d = -(1 - bb), aa - 3 * bb**2 - 2 * bb, -(aa * bb - bb**2 - bb**3)
        disc = 18 * b * c * d - 4 * b**3 * d + b**2 * c**2 - 4 * c**3 - 27 * d**2
        rs = mp.polyroots([1, b, c, d], maxsteps=400, extraprec=400)
        if disc > 0:
            cand = sorted(mp.re(r) for r in rs)
        else:
            cand = [mp.re(min(rs, key=lambda r: abs(mp.im(r))))]
        return [z for z in cand if z > bb]

    def log_term(self, zr: mpf) -> mpf:
        return mp.log((zr + (1 + SQ2) * self.bb) / (zr + (1 - SQ2) * self.bb))

    def ln_phi(self, zr: mpf) -> list[mpf]:
        lt = self.log_term(zr)
        return [
            self.comps[i].b / self.bm * (zr - 1)
            - mp.log(zr - self.bb)
            - self.aa
            / (2 * SQ2 * self.bb)
            * (2 * self.sums[i] / self.am - self.comps[i].b / self.bm)
            * lt
            for i in range(NC)
        ]

    def g_dep(self, zr: mpf) -> mpf:
        return sum(yi * lp for yi, lp in zip(self.y, self.ln_phi(zr), strict=True))

    def h_dep(self, zr: mpf) -> mpf:
        t = self.temp
        return R * t * (zr - 1) + (t * self.dam - self.am) / (2 * SQ2 * self.bm) * self.log_term(zr)


# ============================================================================================
# 3. The vapour phase rule (L01 spec section 4.2, ADR 0043 D5)
# ============================================================================================


def vapour(comps: Sequence[Comp], temp: mpf, pres: mpf, n: Sequence[mpf]) -> dict[str, Any]:
    """The provider's VAPOR answer at (T, P, n), or `UnsupportedError` with its code."""
    if not (DOMAIN_T[0] <= temp <= DOMAIN_T[1] and DOMAIN_P[0] <= pres <= DOMAIN_P[1]):
        raise UnsupportedError("out_of_domain")
    total = sum(n)
    y = [ni / total for ni in n]
    mx = Mix(comps, temp, pres, y)
    rs = mx.roots()
    zr = rs[-1]
    if len(rs) == 3 and mx.g_dep(rs[0]) < mx.g_dep(zr):
        raise UnsupportedError("vapour_root_metastable")
    v = zr * R * temp / pres
    if v < VC_OVER_B * mx.bm:
        raise UnsupportedError("vapour_root_liquid_like")
    out: dict[str, Any] = {
        "Z": zr,
        "v": v,
        "h": sum(y[i] * h_ig(comps[i], temp) for i in range(NC)) + mx.h_dep(zr),
    }
    for i, lp in enumerate(mx.ln_phi(zr)):
        out[f"lnphi_{ORDER[i]}"] = lp
    out["_h_dep"] = mx.h_dep(zr)
    out["_roots"] = rs
    out["_v_over_b"] = v / mx.bm
    return out


def roots_and_vb(comps: Sequence[Comp], temp: mpf, pres: mpf, n: Sequence[mpf]) -> tuple[int, mpf]:
    """The admissible root count and v/b_mix of the largest root, with no guard applied."""
    total = sum(n)
    mx = Mix(comps, temp, pres, [ni / total for ni in n])
    rs = mx.roots()
    return len(rs), rs[-1] * R * temp / (pres * mx.bm)


def saturation(f: Callable[[mpf], Mix], x0: mpf) -> mpf:
    """The coordinate at which the pure fluid's smallest and largest roots have equal G^dep/RT."""

    def gap(x: mpf) -> mpf:
        mx = f(x)
        rs = mx.roots()
        if len(rs) != 3:
            raise RuntimeError(f"saturation search left the three-root region at {x}")
        return mx.g_dep(rs[0]) - mx.g_dep(rs[-1])

    return mp.findroot(gap, x0)


PROPS = ["Z", "v", "h"] + [f"lnphi_{c}" for c in ORDER]


def derivatives(
    comps: Sequence[Comp], temp: mpf, pres: mpf, n: list[mpf]
) -> dict[str, dict[str, mpf]]:
    """d/dT, d/dP and d/dn_j of every property by mpmath.diff at 50 digits (no stencil choice
    survives at that precision); the closed forms are analytic in n, so a zero flow is
    differentiated through zero."""
    out: dict[str, dict[str, mpf]] = {p: {} for p in PROPS}
    for p in PROPS:
        out[p]["T"] = mp.diff(lambda x, p=p: vapour(comps, x, pres, n)[p], temp)
        out[p]["P"] = mp.diff(lambda x, p=p: vapour(comps, temp, x, n)[p], pres)
        for j, cid in enumerate(ORDER):

            def fj(x: mpf, j: int = j, p: str = p) -> mpf:
                nn = list(n)
                nn[j] = x
                return vapour(comps, temp, pres, nn)[p]

            out[p][f"n_{cid}"] = mp.diff(fj, n[j])
    return out


# ============================================================================================
# 4. The registered states (L01 spec section 5)
# ============================================================================================


def flows(**named: str) -> list[mpf]:
    return [m(named.get(c, "0")) for c in ORDER]


STATES: dict[str, dict[str, Any]] = {
    "V1L": {
        "T": m(700),
        "P": m("5e6"),
        "n": flows(
            H2="0.30",
            N2="0.04",
            Ar="0.01",
            CH4="0.18",
            H2O="0.30",
            CO2="0.10",
            O2="0.02",
            C2H6="0.03",
            C3H8="0.02",
        ),
        "why": "every flow non-zero, so a permuted index shows (L01.A15, A16, A21)",
    },
    "V2L": {
        "T": m(500),
        "P": m("1e6"),
        "n": flows(H2O="0.90", CO2="0.05", N2="0.05"),
        "why": "steam-rich, three roots and a stable vapour; zero flows test infinite dilution",
    },
    "P1": {
        "T": m(500),
        "P": m("1e5"),
        "n": flows(H2O="1"),
        "why": "pure water vapour at 0.1 MPa, 500 K (L01.A18's admitted counterpart)",
    },
}

#: The refusal and boundary states of L01.A17-A20: (id, T, P, n, expected status or reason, why).
GUARD_STATES: list[tuple[str, mpf, mpf, list[mpf], str, str]] = [
    ("A17_365K", m(365), m(101325), flows(H2O="1"), "vapour_root_metastable", "below PR's T_b"),
    ("A17_385K", m(385), m(101325), flows(H2O="1"), "ok", "above PR's T_b"),
    (
        "A18_H2O_300K",
        m(300),
        m("5e6"),
        flows(H2O="1"),
        "vapour_root_liquid_like",
        "compressed liquid water, a single root",
    ),
    (
        "A18_CO2_250K",
        m(250),
        m("5e6"),
        flows(CO2="1"),
        "vapour_root_liquid_like",
        "compressed liquid CO2, a single root",
    ),
    (
        "A19_330K",
        m(330),
        m("1e5"),
        flows(H2O="0.95", N2="0.05"),
        "vapour_root_metastable",
        "water partial pressure above its PR vapour pressure",
    ),
    ("A19_400K", m(400), m("1e5"), flows(H2O="0.95", N2="0.05"), "ok", "the same mixture, dry"),
    (
        "A19_C3H8",
        m(300),
        m("1.5e6"),
        flows(C3H8="1"),
        "vapour_root_metastable",
        "propane above its PR vapour pressure",
    ),
    ("A20_T_low", m("199.5"), m("5e6"), STATES["V1L"]["n"], "out_of_domain", "T below 200 K"),
    ("A20_T_high", m("1000.5"), m("5e6"), STATES["V1L"]["n"], "out_of_domain", "T above 1000 K"),
    ("A20_P_high", m(700), m("3.1e7"), STATES["V1L"]["n"], "out_of_domain", "P above 30 MPa"),
]


def status_of(comps: Sequence[Comp], temp: mpf, pres: mpf, n: Sequence[mpf]) -> str:
    try:
        vapour(comps, temp, pres, n)
    except UnsupportedError as refusal:
        return refusal.code
    return "ok"


def build() -> dict[str, Any]:
    CLAIMS.clear()
    comps = load_components()
    i_h2o, i_c3 = ORDER.index("H2O"), ORDER.index("C3H8")

    claim(
        "PR-01",
        abs(VC_OVER_B - mpf("3.951373035591441433")) < mpf("1e-18"),
        f"Z_c/B_c of the PR cubic's triple root is {mp.nstr(VC_OVER_B, 20)} (≈ 3.951, spec §4.2)",
    )

    # -- the three value states ------------------------------------------------------------
    phase_states: dict[str, Any] = {}
    evaluated: dict[str, dict[str, Any]] = {}
    for sid, st in STATES.items():
        code = status_of(comps, st["T"], st["P"], st["n"])
        claim(f"ADMIT-{sid}", code == "ok", f"{sid} is admitted (got {code})")
        ev = vapour(comps, st["T"], st["P"], st["n"])
        evaluated[sid] = ev
        phase_states[sid] = {
            "T_K": nstr(st["T"]),
            "P_Pa": nstr(st["P"]),
            "n_mol_s": [nstr(x) for x in st["n"]],
            "phase": "VAPOR",
            "why": st["why"],
            "values": {p: nstr(ev[p]) for p in PROPS},
            "h_departure_J_mol": nstr(ev["_h_dep"]),
            "real_root_count": len(ev["_roots"]),
            "v_over_b_mix": nstr(ev["_v_over_b"]),
            "status_or_reason": "ok",
        }
        claim(f"HDEP-{sid}", abs(ev["_h_dep"]) > 1, f"|h^dep| at {sid} exceeds 1 J/mol")
    claim(
        "V2L-ROOTS",
        len(evaluated["V2L"]["_roots"]) == 3,
        "V2L has three admissible roots and its vapour (the largest) is the stable one",
    )
    gaps: dict[str, float] = {}
    for sid in ("V1L", "V2L"):
        lp = [evaluated[sid][f"lnphi_{c}"] for c in ORDER]
        gap = min(abs(a - b) for a, b in combinations(lp, 2))
        gaps[sid] = nstr(gap, 3)
        claim(
            f"PH-GAP-{sid}",
            gap >= mpf("1e-6") and min(abs(x) for x in lp) > 0,
            f"{sid}: nine non-zero ln phi, pairwise gaps >= 1e-6 (min {mp.nstr(gap, 3)}),"
            " so a permuted index fails A15's 1e-12 by >= 1e6",
        )
    p1z = evaluated["P1"]["Z"]
    claim(
        "P1-Z",
        abs(p1z - mpf("0.9958")) <= mpf("0.002") and mp.nstr(p1z, 5) == "0.9962",
        f"P1's Z = {mp.nstr(p1z, 8)} is within 0.002 of IAPWS-IF97's 0.9958 (PR gives 0.99620)",
    )
    claim(
        "P1-FALLBACKS",
        abs(1 - mpf("0.9958")) > mpf("0.002") and abs(mpf("1.0006") - mpf("0.9958")) > mpf("0.002"),
        "the ideal-gas fallback (Z = 1) and a dropped a-term (Z ≈ 1.0006) fall outside A18's band",
    )

    # -- derivatives at V1L and V2L ----------------------------------------------------------
    ders: dict[str, Any] = {}
    for sid in ("V1L", "V2L"):
        st = STATES[sid]
        dd = derivatives(comps, st["T"], st["P"], st["n"])
        ders[sid] = {p: {k: nstr(v) for k, v in by.items()} for p, by in dd.items()}
        if sid == "V1L":
            smallest = min(
                abs(v) for by in dd.values() for k, v in by.items() if k.startswith("n_")
            )
            claim(
                "DER-NZ",
                smallest > mpf("1e-12"),
                f"every n-derivative at V1L exceeds 1e-12 in size (min {mp.nstr(smallest, 3)})",
            )

    # -- the guard and domain states (L01.A17-A20) -------------------------------------------
    guard_states: dict[str, Any] = {}
    for gid, temp, pres, n, expected, why in GUARD_STATES:
        code = status_of(comps, temp, pres, n)
        claim(f"GUARD-{gid}", code == expected, f"{gid} ({why}) gives {expected} (got {code})")
        entry: dict[str, Any] = {
            "T_K": nstr(temp),
            "P_Pa": nstr(pres),
            "n_mol_s": [nstr(x) for x in n],
            "why": why,
            "status_or_reason": expected,
        }
        if expected != "out_of_domain":
            count, vb = roots_and_vb(comps, temp, pres, n)
            entry["real_root_count"] = count
            entry["largest_root_v_over_b_mix"] = nstr(vb, 6)
        guard_states[gid] = entry

    # A17: PR's normal boiling point of water and the bracket's margins.
    def pure(index: int) -> list[mpf]:
        return [mpf(1) if i == index else mpf(0) for i in range(NC)]

    t_b = saturation(lambda x: Mix(comps, x, m(101325), pure(i_h2o)), m("374.5"))
    claim(
        "A17-TB",
        abs(t_b - mpf("374.53")) < mpf("0.005"),
        f"PR places water's saturation at 101325 Pa at {mp.nstr(t_b, 7)} K (spec: 374.53 K)",
    )
    claim(
        "A17-MARGIN",
        t_b - 365 >= mpf("9.5") and 385 - t_b >= mpf("9.5"),
        "365 K and 385 K are each >= 9.5 K from PR's saturation temperature",
    )
    # A18: v/b of the two liquid-like single roots.
    for gid, quoted in (("A18_H2O_300K", "1.12"), ("A18_CO2_250K", "1.52")):
        count, vb = roots_and_vb(comps, *[s for s in GUARD_STATES if s[0] == gid][0][1:4])
        claim(
            f"A18-VB-{gid}",
            count == 1 and vb < VC_OVER_B,
            f"{gid} has a single root with v/b = {mp.nstr(vb, 6)} < Z_c/B_c (spec quotes {quoted})",
        )
    # A19: the water partial pressure over PR's vapour pressure at 330 K; propane's at 300 K.
    p_w = saturation(lambda x: Mix(comps, m(330), x, pure(i_h2o)), m("2e4"))
    ratio = m("0.95e5") / p_w
    claim(
        "A19-RATIO",
        ratio > 1,
        f"at 330 K the water partial pressure 0.95e5 Pa is {mp.nstr(ratio, 4)} x PR's vapour "
        f"pressure {mp.nstr(p_w, 6)} Pa (spec: 5.5x, against water's measured vapour pressure)",
    )
    p_c3 = saturation(lambda x: Mix(comps, m(300), x, pure(i_c3)), m("1e6"))
    claim(
        "A19-C3H8",
        abs(p_c3 - mpf("1e6")) < mpf("0.05e6") and p_c3 < mpf("1.5e6"),
        f"propane's PR vapour pressure at 300 K is {mp.nstr(p_c3, 6)} Pa (spec: about 1.0 MPa)",
    )

    return {
        "record": "l01-reference-values",
        "version": 1,
        "specification": "docs/derivations/L01-spec.md",
        "generator": "docs/derivations/scripts/l01_reference.py",
        "components_yaml_sha256": hashlib.sha256(COMPONENTS_YAML.read_bytes()).hexdigest(),
        "constants": {
            "R_J_per_mol_K": "8.31446261815324",
            "Omega_a": "0.45724",
            "Omega_b": "0.07780",
            "kappa_rule": "0.37464 + 1.54226 w - 0.26992 w^2 (Peng-Robinson 1976), every component",
            "k_ij": "0 for every pair (ADR 0026 D3)",
            "T_ref_K": "298.15",
            "Zc_over_Bc": mp.nstr(VC_OVER_B, 20),
            "order": list(ORDER),
            "domain": {"T_K": [200.0, 1000.0], "P_Pa": [1.0e4, 3.0e7]},
        },
        "closed_form": {
            "phase_states": phase_states,
            "derivatives": ders,
            "guard_states": guard_states,
            "saturation": {
                "water_T_b_at_101325_Pa_K": nstr(t_b),
                "water_P_sat_at_330_K_Pa": nstr(p_w),
                "propane_P_sat_at_300_K_Pa": nstr(p_c3),
            },
        },
        "assertion_margins": {"min_pairwise_lnphi_gap": gaps},
        "generator_claims": list(CLAIMS),
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
        OUT_YAML.write_text(text, encoding="utf-8")
        print(f"wrote {OUT_YAML.relative_to(ROOT)}; {len(CLAIMS)} claims hold")
        return 0
    ok = OUT_YAML.exists() and OUT_YAML.read_text(encoding="utf-8") == text
    print(f"{len(CLAIMS)} claims hold; reference_values.yaml {'matches' if ok else 'DIFFERS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
