"""S07 measurement 2: AbstractState derivative API, imposed phase, in-dome evaluation, determinism."""

import json
import sys

import CoolProp.CoolProp as CP

AS = CP.AbstractState("HEOS", "Water")
names_r = [
    "alphar",
    "dalphar_dDelta",
    "dalphar_dTau",
    "d2alphar_dDelta2",
    "d2alphar_dDelta_dTau",
    "d2alphar_dTau2",
    "d3alphar_dDelta3",
    "d3alphar_dDelta2_dTau",
    "d3alphar_dDelta_dTau2",
    "d3alphar_dTau3",
]
names_0 = [
    "alpha0",
    "dalpha0_dDelta",
    "dalpha0_dTau",
    "d2alpha0_dDelta2",
    "d2alpha0_dDelta_dTau",
    "d2alpha0_dTau2",
    "d3alpha0_dDelta3",
    "d3alpha0_dDelta2_dTau",
    "d3alpha0_dDelta_dTau2",
    "d3alpha0_dTau3",
]
missing = [n for n in names_r + names_0 if not hasattr(AS, n)]
print("missing_methods", missing)
print(
    "has specify_phase", hasattr(AS, "specify_phase"), "unspecify", hasattr(AS, "unspecify_phase")
)


def jet(AS):
    return [getattr(AS, n)() for n in names_0 + names_r if hasattr(AS, n)]


# in-dome state for water at 400 K: rho between sat densities (mol/m3)
T = 400.0
AS.update(CP.QT_INPUTS, 0.0, T)
rl = AS.rhomolar()
AS.update(CP.QT_INPUTS, 1.0, T)
rv = AS.rhomolar()
rm = 0.5 * (rl + rv)
pts = {"dome": (rm, T), "vap": (rv * 0.5, T), "liq": (rl * 1.01, T), "super": (5000.0, 900.0)}
res = {}
for key, (rho, t) in pts.items():
    row = {}
    for mode in ("free", "gas", "liquid", "supercritical"):
        A = CP.AbstractState("HEOS", "Water")
        try:
            if mode == "gas":
                A.specify_phase(CP.iphase_gas)
            if mode == "liquid":
                A.specify_phase(CP.iphase_liquid)
            if mode == "supercritical":
                A.specify_phase(CP.iphase_supercritical)
            A.update(CP.DmolarT_INPUTS, rho, t)
            row[mode] = dict(p=A.p(), phase=A.phase(), jet=jet(A), tau=A.tau(), delta=A.delta())
        except Exception as e:
            row[mode] = dict(err=str(e)[:100])
    res[key] = dict(rho=rho, T=t, rows=row)
    base = row.get("gas", {})
    for mode, r in row.items():
        if "err" in r:
            print(key, mode, "ERR", r["err"])
        else:
            same = r["jet"] == base.get("jet")
            print(key, mode, "phase", r["phase"], "p", repr(r["p"]), "jet==gas", same)
# determinism: same call twice, and after other updates
A = CP.AbstractState("HEOS", "Water")
A.specify_phase(CP.iphase_gas)
A.update(CP.DmolarT_INPUTS, rm, T)
j1 = jet(A)
A.update(CP.DmolarT_INPUTS, 1000.0, 600.0)
A.update(CP.DmolarT_INPUTS, rm, T)
j2 = jet(A)
print("repeat_bit_identical", j1 == j2)
json.dump(res, open(sys.argv[1], "w"))
