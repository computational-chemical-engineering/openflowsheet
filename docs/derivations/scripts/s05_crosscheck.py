"""Design-lane cross-check for S05 (IAPWS-95): transcribes the coefficients and evaluates the
registered states with two independent implementations.

It runs ONLY in a scratch venv holding CoolProp 8.0.0 (MIT) and iapws 1.5.5 (GPL-3, executed as a
comparison, nothing copied) plus mpmath 1.3.0; never in the project venv (C10_DECISIONS, generator
layout). It writes two committed files:

* ``s05_iapws95_coefficients.json`` -- the coefficients, transcribed from CoolProp's ``Water`` fluid
  string, after asserting that every one equals iapws 1.5.5's value exactly (spec §2.1);
* ``s05_crosscheck.json`` -- both implementations' values at the states registered in
  ``s05_reference.py`` (imported for its state lists only), the seeds of its root solves, the
  admission bounds of spec §6.2, and CoolProp's central differences for the floor of spec §6.3.

    <scratch venv>/bin/python -I docs/derivations/scripts/s05_crosscheck.py --check
    <scratch venv>/bin/python -I docs/derivations/scripts/s05_crosscheck.py --emit
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import CoolProp
import CoolProp.CoolProp as CP  # noqa: N817
from iapws import IAPWS95

HERE = Path(__file__).resolve().parent
COEFF_PATH = HERE / "s05_iapws95_coefficients.json"
CROSS_PATH = HERE / "s05_crosscheck.json"
FLUID_SHA256 = "a10a0da6c55e623cccc1f56a70cb348c772d8fc1710a6a142b459abb0dec4586"
M = 0.018015268
#: Spec §6.2: a value is admitted iff both implementations lie within these bounds of it. Relative,
#: except phi (absolute in units of max(|value|, 1)), h (units of R T), s (units of R) and lnphi
#: (absolute). Each is set above the measured worst agreement (recorded in s05_reference.json's
#: "agreement") and below what a one-digit change in any coefficient produces (spec §6.2). The
#: states in (647.0 K, 648.0 K) take the bounds times near_critical_factor: CoolProp 8.0.0's
#: solve there disagrees by up to 4.3e-8 in cp and the derivatives (measured 2026-10-22).
ADMISSION_BOUNDS = {
    "phi": "1e-12",
    "sat_Psat": "2e-9",
    "sat_rho": "1e-9",
    "sat_h": "1e-9",
    "sat_s": "1e-9",
    "sat_Tsat": "2e-7",
    "tp_rho": "1e-9",
    "tp_h": "1e-8",
    "tp_s": "1e-8",
    "tp_cp": "1e-8",
    "tp_v": "1e-9",
    "tp_Z": "5e-9",
    "tp_lnphi": "5e-9",
    "tp_deriv": "1e-8",
    "near_critical_factor": "100",
}
#: Spec §6.3: relative central-difference step for the floor measurement.
FD_STEP = 1e-6


def fail(text: str) -> None:
    raise SystemExit(f"cross-check failed: {text}")


def transcribe() -> dict[str, Any]:
    raw = CP.get_fluid_param_string("Water", "JSON")
    if hashlib.sha256(raw.encode()).hexdigest() != FLUID_SHA256:
        fail("CoolProp's Water fluid string moved")
    fluid = json.loads(raw)
    eos = (fluid[0] if isinstance(fluid, list) else fluid)["EOS"][0]
    lead, logtau, pe = eos["alpha0"]
    power, gauss, nonan = eos["alphar"]
    if [lead["type"], logtau["type"], pe["type"]] != [
        "IdealGasHelmholtzLead",
        "IdealGasHelmholtzLogTau",
        "IdealGasHelmholtzPlanckEinstein",
    ] or [power["type"], gauss["type"], nonan["type"]] != [
        "ResidualHelmholtzPower",
        "ResidualHelmholtzGaussian",
        "ResidualHelmholtzNonAnalytic",
    ]:
        fail("unexpected term families")
    red = eos["STATES"]["reducing"]
    coeff = {
        "source": {
            "transcribed_from": "CoolProp 8.0.0 get_fluid_param_string('Water', 'JSON')",
            "fluid_string_sha256": FLUID_SHA256,
            "formulation": "IAPWS R6-95(2018), Wagner and Pruss, J. Phys. Chem. Ref. Data 31 (2002) 387",  # noqa: E501
            "checked_equal_to": "iapws 1.5.5 IAPWS95._constants and IAPWS95.Fi0",
        },
        "R_specific": 461.51805,
        "M": eos["molar_mass"],
        "T_c": red["T"],
        "rho_c": 322.0,
        "p_c": 22064000.0,
        "T_t": eos["STATES"]["sat_min_liquid"]["T"],
        "ideal": {"n": [lead["a1"], lead["a2"], logtau["a"], *pe["n"]], "gamma": pe["t"]},
        "power": {k: power[k2] for k, k2 in (("n", "n"), ("d", "d"), ("t", "t"), ("c", "l"))},
        "gaussian": {
            k: gauss[k2]
            for k, k2 in (
                ("n", "n"),
                ("d", "d"),
                ("t", "t"),
                ("alpha", "eta"),
                ("beta", "beta"),
                ("gamma", "gamma"),
                ("epsilon", "epsilon"),
            )
        },
        "nonanalytic": {k: nonan[k] for k in ("n", "a", "b", "B", "C", "D", "A", "beta")},
    }
    # R_s = 0.46151805 kJ/(kg K) is the formulation's; CoolProp stores the molar 8.314371357587.
    if abs(coeff["R_specific"] * M - eos["gas_constant"]) > 1e-12 or eos["molar_mass"] != M:
        fail("R_s * M does not reproduce CoolProp's molar gas constant")
    if abs(red["rhomolar"] * M / 322.0 - 1) > 1e-15 or red["T"] != 647.096:
        fail("CoolProp's reducing state is not (647.096 K, 322 kg/m3)")
    return coeff


def iapws_equal(coeff: dict[str, Any]) -> bool:
    c, f0 = IAPWS95._constants, IAPWS95.Fi0
    p, g, a = coeff["power"], coeff["gaussian"], coeff["nonanalytic"]
    pairs = [
        (coeff["ideal"]["n"], [*f0["ao_pow"], f0["ao_log"][1], *f0["ao_exp"]]),
        (coeff["ideal"]["gamma"], f0["titao"]),
        (p["n"], c["nr1"] + c["nr2"]),
        (p["d"], c["d1"] + c["d2"]),
        (p["t"], c["t1"] + c["t2"]),
        (p["c"][7:], c["c2"]),
        (g["n"], c["nr3"]),
        (g["d"], c["d3"]),
        (g["t"], c["t3"]),
        (g["alpha"], c["alfa3"]),
        (g["beta"], c["beta3"]),
        (g["gamma"], c["gamma3"]),
        (g["epsilon"], c["epsilon3"]),
        (a["n"], c["nr4"]),
        (a["a"], c["a4"]),
        (a["b"], c["b4"]),
        (a["B"], c["B"]),
        (a["C"], c["C"]),
        (a["D"], c["D"]),
        (a["A"], c["A"]),
        (a["beta"], c["beta4"]),
    ]
    same = all(
        len(x) == len(y) and all(float(u) == float(v) for u, v in zip(x, y, strict=True))
        for x, y in pairs
    )
    return same and p["c"][:7] == [0] * 7 and c["R"] == 8.314371357587 and f0["pow"] == [0, 1]


def encode(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def load_reference() -> Any:
    spec = importlib.util.spec_from_file_location("s05_reference", HERE / "s05_reference.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AS = CoolProp.AbstractState("HEOS", "Water")
PHI_KEYS = {
    "": ("alpha", ""),
    "_d": ("dalpha", "_dDelta"),
    "_dd": ("d2alpha", "_dDelta2"),
    "_t": ("dalpha", "_dTau"),
    "_tt": ("d2alpha", "_dTau2"),
    "_dt": ("d2alpha", "_dDelta_dTau"),
    "_ddd": ("d3alpha", "_dDelta3"),
    "_ddt": ("d3alpha", "_dDelta2_dTau"),
    "_dtt": ("d3alpha", "_dDelta_dTau2"),
    "_ttt": ("d3alpha", "_dTau3"),
}
IAPWS_PHI = {"": "", "_d": "d", "_dd": "dd", "_t": "t", "_tt": "tt", "_dt": "dt"}


def cp_tp(t: float, p: float, phase: str | None) -> dict[str, float]:
    AS.unspecify_phase()
    if phase is not None:
        AS.specify_phase(CoolProp.iphase_liquid if phase == "LIQUID" else CoolProp.iphase_gas)
    AS.update(CoolProp.PT_INPUTS, p, t)
    out = {
        "rho": AS.rhomass(),
        "h": AS.hmolar(),
        "s": AS.smolar(),
        "cp": AS.cpmolar(),
        "v": 1 / AS.rhomolar(),
        "Z": AS.compressibility_factor(),
        "lnphi_H2O": float(math.log(AS.fugacity_coefficient(0))),
    }
    # CoolProp's analytic first partials: a double implementation's derivative floor (spec §6.3).
    for k, ik in (("h", CoolProp.iHmolar), ("s", CoolProp.iSmolar), ("rhom", CoolProp.iDmolar)):
        out[f"d{k}_dT"] = AS.first_partial_deriv(ik, CoolProp.iT, CoolProp.iP)
        out[f"d{k}_dP"] = AS.first_partial_deriv(ik, CoolProp.iP, CoolProp.iT)
    for var in ("T", "P"):
        out[f"dv_d{var}"] = -out.pop(f"drhom_d{var}") / AS.rhomolar() ** 2
    AS.unspecify_phase()
    return out


def cp_sat(t: float) -> dict[str, float]:
    out = {}
    for q, k in ((0, "l"), (1, "v")):
        AS.update(CoolProp.QT_INPUTS, q, t)
        out.update({f"rho_{k}": AS.rhomass(), f"h_{k}": AS.hmolar(), f"s_{k}": AS.smolar()})
    out["Psat"] = AS.p()
    return out


def ia_sat(t: float) -> dict[str, float]:
    w = IAPWS95(T=t, x=0.5)
    return {
        "Psat": w.P * 1e6,
        "rho_l": w.Liquid.rho,
        "rho_v": w.Gas.rho,
        "h_l": w.Liquid.h * M * 1e3,
        "h_v": w.Gas.h * M * 1e3,
        "s_l": w.Liquid.s * M * 1e3,
        "s_v": w.Gas.s * M * 1e3,
    }


def build() -> dict[str, Any]:
    ref = load_reference()
    cool: dict[str, float] = {}
    iap: dict[str, float] = {}
    seeds: dict[str, Any] = {}
    fd: dict[str, float] = {}
    tc, rhoc = 647.096, 322.0
    for name, t_, rho_, _ in ref.PHI_STATES:
        t, rho = float(t_), float(rho_)
        AS.update(CoolProp.DmassT_INPUTS, rho, t)
        w = IAPWS95()
        i0, ir = w._phi0(tc / t, rho / rhoc), w._phir(tc / t, rho / rhoc)
        for suf, (pre, post) in PHI_KEYS.items():
            for lab, part in (("phi0", "0"), ("phir", "r")):
                if lab == "phi0" and suf in ("_ddd", "_ddt", "_dtt", "_ttt"):
                    continue
                cool[f"phi/{name}/{lab}{suf}"] = getattr(AS, f"{pre}{part}{post}")()
                if suf in IAPWS_PHI:
                    src = i0 if lab == "phi0" else ir
                    key = ("fio" if lab == "phi0" else "fir") + IAPWS_PHI[suf]
                    iap[f"phi/{name}/{lab}{suf}"] = src[key]
    for t_ in ref.SAT_T:
        c, i = cp_sat(float(t_)), ia_sat(float(t_))
        cool.update({f"sat/{t_}/{k}": v for k, v in c.items()})
        iap.update({f"sat/{t_}/{k}": v for k, v in i.items()})
        seeds[f"sat/{t_}"] = [repr(c["rho_l"]), repr(c["rho_v"])]
    for p_ in ref.SAT_P:
        AS.update(CoolProp.PQ_INPUTS, float(p_), 0)
        t = AS.T()
        cool[f"tsat/{p_}/Tsat"] = t
        iap[f"tsat/{p_}/Tsat"] = IAPWS95(P=float(p_) / 1e6, x=0.5).T
        c = cp_sat(t)
        seeds[f"tsat/{p_}"] = [repr(t), repr(c["rho_l"]), repr(c["rho_v"])]
    for name, t_, p_, phase, _ in ref.TP_STATES:
        t, p = float(t_), float(p_)
        c = cp_tp(t, p, phase if t < tc else None)
        w = IAPWS95(T=t, P=p / 1e6)
        i = {
            "rho": w.rho,
            "h": w.h * M * 1e3,
            "s": w.s * M * 1e3,
            "cp": w.cp * M * 1e3,
            "v": M / w.rho,
            "Z": w.Z,
            "lnphi_H2O": float(math.log(w.fi)),
        }
        cool.update({f"tp/{name}/{k}": v for k, v in c.items() if not k.startswith("d")})
        cool.update({f"dtp/{name}/{k}": v for k, v in c.items() if k.startswith("d")})
        iap.update({f"tp/{name}/{k}": v for k, v in i.items()})
        seeds[f"tp/{name}"] = repr(c["rho"])
        if t <= 647.0:
            s_ = cp_sat(t)
            seeds[f"tp_sat/{name}"] = [repr(s_["rho_l"]), repr(s_["rho_v"])]
        for var, x in (("T", t), ("P", p)):
            h = x * FD_STEP
            hi = (
                cp_tp(t + h, p, phase if t < tc else None)
                if var == "T"
                else cp_tp(t, p + h, phase if t < tc else None)
            )
            lo = (
                cp_tp(t - h, p, phase if t < tc else None)
                if var == "T"
                else cp_tp(t, p - h, phase if t < tc else None)
            )
            for k in ref.PROPS:
                fd[f"fd/{name}/d{k}_d{var}"] = (hi[k] - lo[k]) / (2 * h)
    for t_ in ref.GRID_SUB:
        c = cp_sat(float(t_))
        seeds[f"grid/{t_}"] = [repr(c["rho_l"]), repr(c["rho_v"])]
    return {
        "generator": "s05_crosscheck.py",
        "versions": {"CoolProp": CoolProp.__version__, "iapws": md.version("iapws")},
        "licences": {
            "CoolProp": "MIT",
            "iapws": "GPL-3 (executed as a comparison; nothing copied)",
        },
        "coefficients_sha256": hashlib.sha256(COEFF_PATH.read_bytes()).hexdigest(),
        "iapws_coefficients_equal": iapws_equal(json.loads(COEFF_PATH.read_bytes())),
        "admission_bounds": ADMISSION_BOUNDS,
        "fd_step": repr(FD_STEP),
        "CoolProp": {k: repr(v) for k, v in cool.items()},
        "iapws": {k: repr(float(v)) for k, v in iap.items()},
        "CoolProp_fd": {k: repr(v) for k, v in fd.items()},
        "seeds": seeds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="regenerate and compare both files")
    parser.add_argument("--emit", action="store_true", help="write both files")
    args = parser.parse_args()
    if not (args.check or args.emit):
        parser.error("choose --check or --emit")
    coeff = encode(transcribe())
    if not iapws_equal(json.loads(coeff)):
        fail("a coefficient differs between CoolProp 8.0.0 and iapws 1.5.5")
    if args.emit:
        COEFF_PATH.write_bytes(coeff)
    elif COEFF_PATH.read_bytes() != coeff:
        print(f"{COEFF_PATH} differs from the transcription", file=sys.stderr)
        return 1
    cross = encode(build())
    if args.emit:
        CROSS_PATH.write_bytes(cross)
        print("wrote", COEFF_PATH.name, CROSS_PATH.name)
    elif CROSS_PATH.read_bytes() != cross:
        print(f"{CROSS_PATH} differs from the cross-check's output", file=sys.stderr)
        return 1
    else:
        print("both files are byte-identical to the cross-check's output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
