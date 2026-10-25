"""S08 prototype: block easy endpoint (V-block / 2P core / L-block) + unchanged target solve."""
import sys, math
from dataclasses import replace
import numpy as np
sys.path.insert(0, "tests")
from test_s02_column_wo1 import SPECS, PROVIDER, FEED, _pressures
from openflowsheet.models.syn001.column import ColumnSpec, EndSpecification, _initial_state
from openflowsheet.models.syn001.cascade import InletState, SideFeed, _k_values
from openflowsheet.models.syn001 import column_solve as cs
from openflowsheet.models.syn001.column_solve import (solve_column, compile_column, solve_target, stage_ratios,
    acceptance_failures, regimes_of)
from openflowsheet.models.syn001.column import profile_initial
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.thermo.syn001 import h_liquid, h_vapor, C_P, ln_k

CTX = DECLARATION_CONTEXT

def feeds_at(spec, j):
    return [f for f in spec.inlets() if f.stage == j]

def stage_duty(spec, j):
    q = spec.duties[j - 1]
    if q is None:
        es = spec.reboiler_spec if j == spec.stage_count else spec.condenser_spec
        assert es is not None and es.kind == "duty", (j, es)
        q = es.value
    return q

def h_stream(n, T, P, phase):
    return sum(x * (h_liquid(T, P, i) if phase == "LIQUID" else h_vapor(T, i)) for i, x in enumerate(n))

def solve_T(n, H, P, phase, T0):
    T = T0
    for _ in range(4):
        T -= (h_stream(n, T, P, phase) - H) / (C_P * sum(n))
    return T

def block_endpoint(spec, cand, initial, max_sweeps=500):
    """cand: dict stage -> 'V' | '2P' | 'L' | 'Z' (conforming)."""
    comps = spec.components; nc = len(comps)
    stages = list(spec.equilibrium_stages())
    P = {j: spec.pressures[j - 1] for j in stages}
    rho, phi = stage_ratios(spec, initial)
    core = [j for j in stages if cand[j] == "2P"]
    lb = [j for j in stages if cand[j] == "L"]
    vb = [j for j in stages if cand[j] == "V"]
    # liquid-carrying stages: core + L-block (contiguous from core top down)
    carry = core + lb
    T = {j: initial.profile[j - 1] for j in stages}
    liquid = {j: [0.0] * nc for j in stages}; vapor = {j: [0.0] * nc for j in stages}
    def flows(T):
        liq = {j: [0.0] * nc for j in stages}; vap = {j: [0.0] * nc for j in stages}
        if not carry:
            return liq, vap
        idx = {j: k for k, j in enumerate(carry)}
        for i in range(nc):
            n = len(carry); A = np.zeros((n, n)); b = np.zeros(n)
            S = {j: (math.exp(ln_k(T[j], P[j], i)) * rho[j] if cand[j] == "2P" else 0.0) for j in carry}
            for j in carry:
                k = idx[j]
                A[k, k] = -(1.0 + S[j])
                if j - 1 in idx: A[k, idx[j - 1]] = 1.0
                if j + 1 in idx: A[k, idx[j + 1]] = S[j + 1]
                b[k] = -sum(f.state.n[i] for f in feeds_at(spec, j))
            x = np.linalg.solve(A, b)
            for j in carry:
                liq[j][i] = float(x[idx[j]]); vap[j][i] = S[j] * float(x[idx[j]])
        return liq, vap
    for sweep in range(1, max_sweeps + 1):
        liquid, vapor = flows(T)
        delta = 0.0
        for j in core:
            bt = band_temperature(PROVIDER, liquid[j], P[j], 0.0, CTX)
            if bt.position != "inside": return f"bubble_outside(stage {j})"
            delta = max(delta, abs(bt.temperature - T[j])); T[j] = bt.temperature
        if delta <= 1e-9: break
    liquid, vapor = flows(T)
    # L-block: top-down energy with target duty
    for j in lb:
        H = stage_duty(spec, j) + sum(h_stream(f.state.n, f.state.temperature, f.state.pressure, f.state.phase) for f in feeds_at(spec, j))
        if j - 1 in core or j - 1 in lb: H += h_stream(liquid[j - 1], T[j - 1], P[j - 1], "LIQUID")
        T[j] = solve_T(liquid[j], H, P[j], "LIQUID", T[j])
    # V-block: bottom-up, all inflow to vapour
    for j in reversed(vb):
        n = [sum(f.state.n[i] for f in feeds_at(spec, j)) for i in range(nc)]
        H = stage_duty(spec, j) + sum(h_stream(f.state.n, f.state.temperature, f.state.pressure, f.state.phase) for f in feeds_at(spec, j))
        if j + 1 in stages and (cand[j + 1] in ("2P", "V")):
            n = [n[i] + vapor[j + 1][i] for i in range(nc)]
            H += h_stream(vapor[j + 1], T[j + 1], P[j + 1], "VAPOR")
        vapor[j] = n
        T[j] = solve_T(n, H, P[j], "VAPOR", T[j])
    prof = tuple(T.get(j, 0.0) for j in range(1, spec.stage_count + 1))
    st = _initial_state(spec, PROVIDER, CTX, liquid, vapor, prof, phi=0.5 if phi is None else phi)
    return st

def run(spec, cand):
    initial = profile_initial(spec, PROVIDER, CTX)
    x = block_endpoint(spec, cand, initial)
    if isinstance(x, str): return ("ENDPOINT", x)
    target = compile_column(spec, PROVIDER)
    order = target.spec.variable_ids
    x0 = {n: float(x[n]) for n in order}
    result, rec, regimes = solve_target(spec, PROVIDER, target, x0, initial.profile, policy=cs.S02_TARGET_POLICY)
    att = [(a.outcome, a.solver_outcome, "".join(r[0] for _, r in a.signature), a.iterations) for a in (rec.attempts if rec else ())] + \
          [(a.outcome, a.solver_outcome, "".join(r[0] for _, r in a.signature), a.iterations) for a in result.attempts]
    return result.outcome, result.message[:80], tuple(regimes.values()), att, result.state

if __name__ == "__main__":
    import json
    which = sys.argv[1]
    P5 = _pressures(5)
    cases = {}
    cases["P1"] = SPECS["P1"]
    # F1: flooded bottom: M4 with the vapour moved to a side feed at stage 3; small liquid bottom inlet
    cases["F1"] = replace(SPECS["M4"], sides=(SideFeed("feed", 3, InletState(FEED, 385.0, 1.02e5, "VAPOR")),),
                          bottom=InletState((0.03, 0.04, 0.03), 330.0, 1.04e5, "LIQUID"))
    # D1: dry top: M3 with the liquid moved to a side feed at stage 3; small vapour top inlet
    cases["D1"] = replace(SPECS["M3"], sides=(SideFeed("feed", 3, InletState(FEED, 340.0, 1.02e5, "LIQUID")),),
                          top=InletState((0.03, 0.04, 0.03), 400.0, 1.0e5, "VAPOR"))
    cases["P3"] = replace(SPECS["M4"], bottom=None, reboiler="partial", reboiler_spec=EndSpecification("duty", 1000.0),
                          duties=(None, 0.0, 0.0, 0.0, None),
                          sides=(SideFeed("feed", 3, InletState(FEED, 385.0, 1.02e5, "VAPOR")),
                                 SideFeed("cold", 4, InletState((0.15, 0.2, 0.15), 300.0, 1.03e5, "LIQUID"))))
    cases["P2"] = replace(SPECS["M4"], condenser_spec=EndSpecification("duty", -3000.0),
                          bottom=InletState(FEED, 420.0, 1.04e5, "VAPOR"))
    spec = cases[which]
    cand = dict(enumerate(sys.argv[2].split(","), start=1)) if len(sys.argv) > 2 else None
    if cand is None:
        ans = solve_column(spec, PROVIDER)
        print(which, "TODAY", getattr(ans, "outcome", ans), getattr(ans, "cause", "")[:100], getattr(ans, "signature", None))
        for res in (getattr(ans, "recovered_from", None), getattr(ans, "result", None)):
            for a in (res.attempts if res else ()):
                print("   ", a.outcome, a.solver_outcome, "".join(r[0] for _, r in a.signature), a.iterations, a.reason[:70])
    else:
        out = run(spec, cand)
        print(which, "BLOCK", sys.argv[2], out[:3]); [print("   ", a) for a in out[3]] if len(out) > 3 else None
        if len(out) > 4 and out[0] == "CONVERGED":
            st = out[4]; u = spec.unit_id
            print("    T:", [round(st[f"{u}.stage.{j}.T"], 4) for j in spec.equilibrium_stages()])
            print("    V:", [st[f"{u}.stage.{j}.V"] for j in spec.equilibrium_stages()])
            print("    L:", [st[f"{u}.stage.{j}.L"] for j in spec.equilibrium_stages()])
