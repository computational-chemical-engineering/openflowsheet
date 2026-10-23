"""S07 measurement 3: FP environment after import, reference-state mutation, water jets, timing."""

import hashlib
import importlib
import json
import sys
import time

tiny = 2.2250738585072014e-308
before = (tiny / 3.0, 5e-324 * 1.0, tiny * 0.5)
CP = importlib.import_module("CoolProp.CoolProp")

A = CP.AbstractState("HEOS", "Water")
after = (tiny / 3.0, 5e-324 * 1.0, tiny * 0.5)
print("subnormals_preserved_after_import", before == after and all(x != 0.0 for x in after))

R = [
    "alphar",
    "dalphar_dDelta",
    "dalphar_dDelta",
    "d2alphar_dDelta2",
    "d2alphar_dDelta_dTau",
    "d2alphar_dTau2",
    "d3alphar_dDelta3",
    "d3alphar_dDelta2_dTau",
    "d3alphar_dDelta_dTau2",
    "d3alphar_dTau3",
]
R = [
    "alphar",
    "dalphar_dDelta",
    "d2alphar_dDelta2",
    "dalphar_dTau",
    "d2alphar_dTau2",
    "d2alphar_dDelta_dTau",
    "d3alphar_dDelta3",
    "d3alphar_dDelta2_dTau",
    "d3alphar_dDelta_dTau2",
    "d3alphar_dTau3",
]
Z = [n.replace("alphar", "alpha0") for n in R]


def jet(name, rho, temp, phase=CP.iphase_gas):
    a = CP.AbstractState("HEOS", name)
    a.specify_phase(phase)
    a.update(CP.DmolarT_INPUTS, rho, temp)
    return [getattr(a, n)() for n in Z], [getattr(a, n)() for n in R], a.tau(), a.delta()


# reference-state mutation hazard
s0 = hashlib.sha256(CP.get_fluid_param_string("Water", "JSON").encode()).hexdigest()
j0 = jet("Water", 1000.0, 500.0)[0][:3]
CP.set_reference_state("Water", "NBP")
s1 = hashlib.sha256(CP.get_fluid_param_string("Water", "JSON").encode()).hexdigest()
j1 = jet("Water", 1000.0, 500.0)[0][:3]
CP.set_reference_state("Water", "DEF")
j2 = jet("Water", 1000.0, 500.0)[0][:3]
print("refstate: json_changes", s0 != s1, "alpha0_changes", j0 != j1, "DEF_restores_bits", j0 == j2)

# water jets in (tau, delta) for comparison against iapws95.phi_jet (project venv)
rc, Tc = 17873.72799560906, 647.096
pts = [
    (0.5, 1e-3),
    (1.2, 2.9),
    (0.9, 0.05),
    (1.0 / 0.999, 1.3),
    (647.096 / 400.0, 2.85),
    (647.096 / 400.0, 0.8),
    (0.6, 0.6),
    (1.4, 3.1),
]
dump = []
for tau, delta in pts:
    j0_, jr, t, d = jet("Water", delta * rc, Tc / tau)
    dump.append(dict(tau_in=tau, delta_in=delta, tau=t, delta=d, ideal=j0_, resid=jr))
json.dump(dump, open(sys.argv[1], "w"))

# timing: one update + 20 jet calls, on a reused AbstractState
a = CP.AbstractState("HEOS", "Nitrogen")
a.specify_phase(CP.iphase_gas)
n = 20000
t0 = time.perf_counter()
for i in range(n):
    a.update(CP.DmolarT_INPUTS, 100.0 + i * 1e-3, 300.0)
    v = [getattr(a, m)() for m in Z + R]
dt = (time.perf_counter() - t0) / n
print("us_per_update_plus_20_partials", round(dt * 1e6, 2))
# third derivatives of alpha0 in delta: should be the ideal-gas -1/delta^k pattern
print("alpha0_delta_partials_sample", jet("Nitrogen", 5000.0, 200.0)[0][1:3])
