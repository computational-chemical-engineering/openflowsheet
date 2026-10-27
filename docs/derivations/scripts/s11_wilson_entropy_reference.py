"""50-digit reference for `wilson-ig-v2`'s molar entropy `s` (S11 units design §4.6, S11.A76).

Normative text: ``docs/derivations/S11-units-design.md`` §4.6 (ADR 0051). Inputs: the S10 record
files ``benchmarks/s10/verification-records.yaml`` and ``benchmarks/s10/records.yaml``. Output:
``benchmarks/s11/wilson_entropy_reference.yaml``.

It imports nothing from ``openflowsheet``, and it does not use the note's closed form for the
expectation: ``s`` is computed from the potential, ``s = (h − g)/T`` with

* ``g = Σ x_i [μ_i^ig(T, P₀) + RT ln(x_i φ_i P/P₀)]``, ``μ_i^ig = h_i^ig − T s_i^ig``,
* ``s_i^ig(T, P₀) = R ∫_{T₀}^{T} (c_p,i^ig/R) dT/T`` by quadrature (datum 0 at T₀ = 298.15 K, P₀),
* ``h_i^ig = h_f,i + R ∫_{T₀}^{T} (c_p,i^ig/R) dT`` by quadrature,
* ``ln φ_i^L = ln γ_i^Wilson + ln P_i^sat − ln P``, ``ln φ^V = 0``,
* ``h^L = Σ x_i (h_i^ig − Δh_i)`` with ``Δh_i = R T² d ln P_i^sat/dT`` by numerical differentiation,

and every derivative (``T``, ``P``, ``n_<c>``) by 50-digit numerical differentiation of that ``s``.
The note's closed form is transcribed separately and must agree (claim ENT-01): that checks the
derivation, not the implementation. Values are written to 20 significant digits.

Run from the repository root::

    python docs/derivations/scripts/s11_wilson_entropy_reference.py --check
    python docs/derivations/scripts/s11_wilson_entropy_reference.py --emit

``--emit`` writes the YAML byte-reproducibly; ``--check`` regenerates it in memory and fails unless
it equals the committed file. A record file that is absent is reported ``UNAVAILABLE`` (exit 2).
Dependencies: Python 3.11+, mpmath, PyYAML.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from mpmath import mp, mpf

mp.dps = 50

ROOT = Path(__file__).resolve().parents[3]
RECORD_FILES = {
    "verification": "benchmarks/s10/verification-records.yaml",
    "real": "benchmarks/s10/records.yaml",
}
OUT_YAML = ROOT / "benchmarks" / "s11" / "wilson_entropy_reference.yaml"

R = mpf("8.31446261815324")  # J/(mol K), exact in the 2019 SI
T0 = mpf("298.15")
THETA_UNIT = mpf(1000)
THETA0 = T0 / THETA_UNIT
P0 = mpf(101325)

#: S11.A76: s within 1e-13 relative. The derivatives (no registered A-tolerance) are judged by
#: S10's evaluate_phase rule, |got − want| <= TOL_DERIVATIVE * max(|want|, s_q), with the floors
#: s_q below in s's units (S11D decisions).
TOL_S = 1e-13
TOL_DERIVATIVE = 1e-12
#: |s/R| at every registered state is at least this, so A76's relative test is about s.
S_FLOOR = mpf("0.05")

#: The grid per record file: T (K), P (Pa), the n-vectors (one with a zero component), phases.
TEMPERATURES = (310, 350, 390)
PRESSURES = (60_000, 150_000)
COMPOSITIONS = (("a", (1.0, 0.6, 0.4)), ("b", (0.2, 0.2, 0.6)), ("z", (0.7, 0.0, 0.3)))
PHASES = ("LIQUID", "VAPOR")
#: S11.A77(iii)'s temperatures.
SATURATION_TEMPERATURES = (310, 350, 390)

CLAIMS: list[dict[str, Any]] = []


def claim(cid: str, ok: bool, text: str) -> None:
    CLAIMS.append({"id": cid, "holds": bool(ok), "statement": text})
    if not ok:
        raise SystemExit(f"generator claim {cid} FAILED: {text}")


def nstr(x: Any, digits: int = 20) -> float:
    """A value written to `digits` significant digits (YAML reads it as a float)."""
    x = mpf(x)
    return float(mp.nstr(x, digits, min_fixed=-30, max_fixed=30)) if x != 0 else 0.0


def g3(x: Any) -> float:
    return float(f"{float(x):.3g}") if x != 0 else 0.0


# ============================================================================================
# 1. Records
# ============================================================================================


@dataclass(frozen=True)
class Records:
    ids: tuple[str, ...]
    b: tuple[tuple[mpf, ...], ...]  # c_p^ig/R = sum_k b_k theta^k
    dhf: tuple[mpf, ...]  # J/mol, ideal gas at 298.15 K
    psat: tuple[tuple[mpf, mpf, mpf, mpf], ...]  # a, b, c, d
    lam: tuple[tuple[mpf, ...], ...]  # Lambda_ij, Lambda_ii = 1
    t_dom: tuple[float, float]
    p_dom: tuple[float, float]
    convention: str
    sha256: str


def load_records(path: Path) -> Records:
    raw = path.read_bytes()
    doc = yaml.safe_load(raw)
    comps = doc["components"]
    ids = tuple(c["id"] for c in comps)
    b, dhf, psat = [], [], []
    for c in comps:
        p = c["parameters"]
        b.append(tuple(mpf(float(p[f"ideal_gas_cp_b{k}"]["value"])) for k in range(5)))
        dhf.append(mpf(float(p["standard_formation_enthalpy"]["value"])))
        psat.append(tuple(mpf(float(p[f"vapour_pressure_{s}"]["value"])) for s in "abcd"))
    n = len(ids)
    lam = [[mpf(1) if i == j else None for j in range(n)] for i in range(n)]
    for e in doc["wilson_lambda"]:
        lam[ids.index(e["i"])][ids.index(e["j"])] = mpf(float(e["value"]))
    assert all(v is not None for row in lam for v in row)
    dom = doc["domain"]
    return Records(
        ids=ids,
        b=tuple(b),
        dhf=tuple(dhf),
        psat=tuple(psat),  # type: ignore[arg-type]
        lam=tuple(tuple(r) for r in lam),  # type: ignore[misc]
        t_dom=(float(dom["T"][0]), float(dom["T"][1])),
        p_dom=(float(dom["P"][0]), float(dom["P"][1])),
        convention=doc["reference_convention"],
        sha256=hashlib.sha256(raw).hexdigest(),
    )


# ============================================================================================
# 2. The potential at 50 digits
# ============================================================================================


class Model:
    def __init__(self, rec: Records) -> None:
        self.rec = rec
        self.size = len(rec.ids)
        self._s_ig: dict[tuple[int, mpf], mpf] = {}
        self._h_ig: dict[tuple[int, mpf], mpf] = {}

    def cp_over_r(self, i: int, t: mpf) -> mpf:
        theta = t / THETA_UNIT
        return sum(bk * theta**k for k, bk in enumerate(self.rec.b[i]))

    def s_ig(self, i: int, t: mpf) -> mpf:
        """s_i^ig(T, P0), J/(mol K), by quadrature; 0 at T0."""
        key = (i, t)
        if key not in self._s_ig:
            self._s_ig[key] = R * mp.quad(lambda u: self.cp_over_r(i, u) / u, [T0, t])
        return self._s_ig[key]

    def h_ig(self, i: int, t: mpf) -> mpf:
        key = (i, t)
        if key not in self._h_ig:
            self._h_ig[key] = self.rec.dhf[i] + R * mp.quad(lambda u: self.cp_over_r(i, u), [T0, t])
        return self._h_ig[key]

    def ln_psat(self, i: int, t: mpf) -> mpf:
        a, b, c, d = self.rec.psat[i]
        theta = t / THETA_UNIT
        return a + b / theta + c * mp.log(theta) + d * theta**2

    def dh_vap(self, i: int, t: mpf) -> mpf:
        return R * t**2 * mp.diff(lambda u: self.ln_psat(i, u), t)

    def ln_gamma(self, x: Sequence[mpf]) -> list[mpf]:
        lam, n = self.rec.lam, self.size
        s = [sum(x[j] * lam[i][j] for j in range(n)) for i in range(n)]
        return [1 - mp.log(s[i]) - sum(x[k] * lam[k][i] / s[k] for k in range(n)) for i in range(n)]

    def ln_phi(self, phase: str, t: mpf, p: mpf, x: Sequence[mpf]) -> list[mpf]:
        if phase == "VAPOR":
            return [mpf(0)] * self.size
        gam = self.ln_gamma(x)
        return [gam[i] + self.ln_psat(i, t) - mp.log(p) for i in range(self.size)]

    def h(self, phase: str, t: mpf, x: Sequence[mpf]) -> mpf:
        return sum(
            x[i] * (self.h_ig(i, t) - (self.dh_vap(i, t) if phase == "LIQUID" else 0))
            for i in range(self.size)
        )

    def g(self, phase: str, t: mpf, p: mpf, x: Sequence[mpf]) -> mpf:
        lnphi = self.ln_phi(phase, t, p, x)
        total = mpf(0)
        for i in range(self.size):
            if x[i] == 0:
                continue
            mu_ig = self.h_ig(i, t) - t * self.s_ig(i, t)
            total += x[i] * (mu_ig + R * t * (mp.log(x[i]) + lnphi[i] + mp.log(p / P0)))
        return total

    def s(self, phase: str, t: mpf, p: mpf, n: Sequence[mpf]) -> mpf:
        """s = (h − g)/T, J/(mol K)."""
        total = sum(n)
        x = [ni / total for ni in n]
        return (self.h(phase, t, x) - self.g(phase, t, p, x)) / t

    def s_closed(self, phase: str, t: mpf, p: mpf, n: Sequence[mpf]) -> mpf:
        """The note's closed form (§4.6), transcribed: used only for claim ENT-01."""
        total = sum(n)
        x = [ni / total for ni in n]
        theta = t / THETA_UNIT
        lnphi = self.ln_phi(phase, t, p, x)
        out = mpf(0)
        for i in range(self.size):
            b0, b1, b2, b3, b4 = self.rec.b[i]
            sigma = b0 * mp.log(theta / THETA0) + sum(
                bk * (theta**k - THETA0**k) / k for k, bk in ((1, b1), (2, b2), (3, b3), (4, b4))
            )
            _, b, c, d = self.rec.psat[i]
            lam = -b / theta + c + 2 * d * theta**2
            out += x[i] * (sigma - (lam if phase == "LIQUID" else 0) - lnphi[i])
            if x[i] != 0:
                out -= x[i] * mp.log(x[i])
        return R * (out - mp.log(p / P0))


# ============================================================================================
# 3. The registered states
# ============================================================================================


def derivative(f: Callable[[mpf], mpf], at: mpf) -> mpf:
    return mp.diff(f, at)


def state_entry(model: Model, sid: str, phase: str, t: float, p: float, n: Sequence[float]) -> dict:
    ids = model.rec.ids
    tm, pm, nm = mpf(t), mpf(p), [mpf(v) for v in n]
    s = model.s(phase, tm, pm, nm)
    closed = model.s_closed(phase, tm, pm, nm)
    claim(
        f"ENT-01-{sid}",
        abs(s - closed) <= mpf("1e-40") * abs(s),
        f"{sid}: the potential's (h - g)/T equals the note's closed form (|diff| = "
        f"{mp.nstr(abs(s - closed), 3)})",
    )
    claim(
        f"ENT-02-{sid}",
        abs(s / R) >= S_FLOOR,
        f"{sid}: |s/R| = {mp.nstr(abs(s / R), 4)} >= {S_FLOOR}",
    )
    ds_dt = derivative(lambda u: model.s(phase, u, pm, nm), tm)
    dh_dt = derivative(lambda u: model.h(phase, u, [v / sum(nm) for v in nm]), tm)
    claim(
        f"ENT-03-{sid}",
        abs(ds_dt - dh_dt / tm) <= mpf("1e-30") * abs(ds_dt),
        f"{sid}: ds/dT = (dh/dT)/T (c_p/T)",
    )
    ds_dp = derivative(lambda u: model.s(phase, tm, u, nm), pm)
    if phase == "LIQUID":
        claim(f"ENT-04-{sid}", abs(ds_dp) <= mpf("1e-35"), f"{sid}: ds^L/dP = 0 (no Poynting)")
    else:
        claim(
            f"ENT-04-{sid}",
            abs(ds_dp + R / pm) <= mpf("1e-35") * R / pm,
            f"{sid}: ds^V/dP = -R/P",
        )
    entry: dict[str, Any] = {
        "id": sid,
        "phase": phase,
        "state": {"n": [float(v) for v in n], "T": float(t), "P": float(p)},
        "s": nstr(s),
        "ds_dT": nstr(ds_dt),
        "ds_dP": 0.0 if phase == "LIQUID" else nstr(ds_dp),
    }
    if all(v > 0 for v in n):
        by_n: dict[str, float] = {}
        homogeneity = mpf(0)
        for j, c in enumerate(ids):

            def along(u: mpf, j: int = j) -> mpf:
                moved = list(nm)
                moved[j] = u
                return model.s(phase, tm, pm, moved)

            value = derivative(along, nm[j])
            homogeneity += nm[j] * value
            by_n[c] = nstr(value)
        claim(
            f"ENT-05-{sid}",
            abs(homogeneity) <= mpf("1e-30") * R,
            f"{sid}: sum_j n_j ds/dn_j = 0 (s is intensive)",
        )
        entry["ds_dn"] = by_n
    return entry


def build_file(name: str, rel: str) -> dict[str, Any]:
    rec = load_records(ROOT / rel)
    model = Model(rec)
    (t_lo, t_hi), (p_lo, p_hi) = rec.t_dom, rec.p_dom
    states = []
    for t, p, (label, n), phase in itertools.product(TEMPERATURES, PRESSURES, COMPOSITIONS, PHASES):
        assert t_lo <= t <= t_hi and p_lo <= p <= p_hi, (name, t, p)
        sid = f"{name[0].upper()}-{phase[0]}-{t}-{p}-{label}"
        states.append(state_entry(model, sid, phase, t, p, n))
    # S11.A77(iii): pure components at saturation, where P_sat(T) is inside the domain.
    saturation = []
    for i, c in enumerate(rec.ids):
        for t in SATURATION_TEMPERATURES:
            psat = mp.exp(model.ln_psat(i, mpf(t)))
            inside = p_lo <= psat <= p_hi and t_lo <= t <= t_hi
            pure = [mpf(1) if k == i else mpf(0) for k in range(model.size)]
            if inside:
                gap = model.s("VAPOR", mpf(t), psat, pure) - model.s("LIQUID", mpf(t), psat, pure)
                latent = model.dh_vap(i, mpf(t)) / t
                claim(
                    f"ENT-06-{name}-{c}-{t}",
                    abs(gap - latent) <= mpf("1e-35") * abs(latent),
                    f"{name} {c} at {t} K, P_sat: s^V - s^L = dh_vap/T",
                )
            saturation.append(
                {"component": c, "T": float(t), "P_sat": nstr(psat), "in_domain": bool(inside)}
            )
    claim(
        f"ENT-07-{name}",
        sum(1 for e in states if "ds_dn" not in e) >= 1,
        f"{name}: at least one registered state has a zero mole fraction",
    )
    return {
        "path": rel,
        "sha256": rec.sha256,
        "reference_convention": rec.convention,
        "components": list(rec.ids),
        "states": states,
        "saturation": saturation,
    }


def build() -> dict[str, Any]:
    CLAIMS.clear()
    files = {name: build_file(name, rel) for name, rel in RECORD_FILES.items()}
    count = sum(len(f["states"]) for f in files.values())
    claim("ENT-08", count >= 30, f"{count} registered states (S11.A76 asks >= 30)")
    return {
        "schema": "s11-wilson-entropy-reference-v1",
        "generator": "docs/derivations/scripts/s11_wilson_entropy_reference.py",
        "normative": "docs/derivations/S11-units-design.md section 4.6 (ADR 0051)",
        "precision": "mpmath at 50 significant digits, written to 20",
        "convention": {
            "P0_Pa": 101325.0,
            "datum": "s_i^ig(298.15 K, P0) = 0 for every component (Q22)",
            "units": (
                "s J/(mol K); ds_dT J/(mol K^2); ds_dP J/(mol K Pa); ds_dn J/(mol K) per mol/s"
            ),
            "ds_dn": "the derivative of the intensive s(n) at fixed other flows (v1's projection)",
        },
        "tolerances": {
            "s_relative": TOL_S,
            "derivative_relative": TOL_DERIVATIVE,
            "derivative_floor": {"ds_dT": "R/T", "ds_dP": "R/P", "ds_dn": "R/n_tot"},
        },
        "record_files": files,
        "generator_claims": CLAIMS[:],
    }


def dump_yaml(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False, width=120, allow_unicode=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--emit", action="store_true")
    args = ap.parse_args()
    missing = [rel for rel in RECORD_FILES.values() if not (ROOT / rel).exists()]
    if missing:
        print(f"UNAVAILABLE: {missing} absent (the real records are read from a source checkout)")
        return 2
    text = dump_yaml(build())
    if args.emit:
        OUT_YAML.write_text(text, encoding="utf-8")
        print(f"wrote {OUT_YAML.relative_to(ROOT)}; {len(CLAIMS)} claims hold")
        return 0
    ok = OUT_YAML.exists() and OUT_YAML.read_text(encoding="utf-8") == text
    print(f"{len(CLAIMS)} claims hold; {OUT_YAML.name} {'matches' if ok else 'DIFFERS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
