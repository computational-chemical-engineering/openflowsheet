"""S08 probe: log contract decisions on a column case; optionally apply a block closure."""
import os, sys, json
sys.path.insert(0, "tests")
from openflowsheet.orchestrator import phase_contract as pc, region as rg
from openflowsheet.models.syn001.column_solve import solve_column

MODE = os.environ.get("S08_MODE", "log")   # log | close
FORBID = json.loads(os.environ.get("S08_FORBID", "{}"))  # unit -> list of forbidden regimes
LOG = []

def conforms(sig):
    regs = [r for _, r in sig if r != "ZERO_FLOW"]
    # V^a 2P^b L^c
    rank = {"VAPOR": 0, "TWO_PHASE": 1, "LIQUID": 2}
    seq = [rank[r] for r in regs]
    return all(a <= b for a, b in zip(seq, seq[1:]))

def closure(frozen, prop):
    """Nearest V^a 2P^b L^c keeping every changed unit's new regime; None if impossible."""
    units = [u for u, _ in prop]
    pf, pp = dict(frozen), dict(prop)
    changed = {u for u in units if pf.get(u) != pp[u]}
    live = [u for u in units if pp[u] != "ZERO_FLOW"]
    n = len(live); best = None
    for a in range(n + 1):
        for c in range(n + 1 - a):
            cand = {u: ("VAPOR" if i < a else "LIQUID" if i >= n - c else "TWO_PHASE") for i, u in enumerate(live)}
            if any(cand[u] != pp[u] for u in changed if u in cand):
                continue
            if any(cand[u] in FORBID.get(u, []) for u in live):
                continue
            cost = sum(cand[u] != pp[u] for u in live)
            if best is None or cost < best[0]:
                best = (cost, cand)
    if best is None:
        return None
    return tuple((u, best[1].get(u, pp[u])) for u in units)

SPEC = None
def block_sweep(state, regimes, frozen, ops):
    """Experimental: single-phase units that changed get a consistent opening (S02 columns)."""
    from openflowsheet.models.syn001.column import _inflow
    from openflowsheet.models.syn001.cascade import (stage_temperature_id as Tid, stage_pressure_id as Pid,
        stage_duty_id as Qid, liquid_id, vapor_id, liquid_total_id, vapor_total_id, mixed_id)
    from openflowsheet.thermo.syn001 import h_liquid, h_vapor, C_P
    spec = SPEC; unit = spec.unit_id; comps = spec.components
    fz = dict(frozen)
    stages = list(spec.equilibrium_stages())
    uid = lambda j: f"{unit}.stage.{j}"
    changed = [j for j in stages if regimes[uid(j)] in ("LIQUID", "VAPOR") and fz.get(uid(j)) != regimes[uid(j)]]
    def tp_of(name):
        # stream variable -> (T, P, phase)
        parts = name.split(".")
        if ".stage." in name:
            j = int(parts[2]); ph = parts[3]
            return state[Tid(unit, j)], state[Pid(unit, j)], ("L" if ph == "l" else "V")
        stream = name.rsplit(".n.", 1)[0]
        port = stream.rsplit(".", 1)[1]
        inl = {"top": spec.top, "bottom": spec.bottom}.get(port)
        if inl is None:
            inl = next(s.state for s in spec.sides if s.port == port)
        return inl.temperature, inl.pressure, ("L" if inl.phase == "LIQUID" else "V")
    order = [j for j in stages if j in changed and regimes[uid(j)] == "LIQUID"] + \
            [j for j in reversed(stages) if j in changed and regimes[uid(j)] == "VAPOR"]
    for j in order:
        reg = regimes[uid(j)]
        H_in = 0.0; m = []
        for ci, c in enumerate(comps):
            tot = 0.0
            for name in _inflow(spec, j, c):
                x = state[name]; tot += x
                if x != 0.0:
                    T, P, ph = tp_of(name)
                    H_in += x * (h_liquid(T, P, ci) if ph == "L" else h_vapor(T, ci))
            m.append(tot)
            state[mixed_id(unit, j, c)] = tot
        q = spec.duties[j - 1]
        if q is None:
            es = spec.reboiler_spec if j == spec.stage_count else spec.condenser_spec
            q = es.value if (es is not None and es.kind == "duty") else state[Qid(unit, j)]
        state[Qid(unit, j)] = q
        H = H_in + q
        P = state[Pid(unit, j)]
        T = state[Tid(unit, j)]
        for _ in range(3):
            if reg == "LIQUID":
                f = sum(m[ci] * h_liquid(T, P, ci) for ci in range(len(comps))) - H
            else:
                f = sum(m[ci] * h_vapor(T, ci) for ci in range(len(comps))) - H
            T -= f / (C_P * sum(m))
        state[Tid(unit, j)] = T
        side = liquid_id if reg == "LIQUID" else vapor_id
        for ci, c in enumerate(comps):
            state[side(unit, j, c)] = m[ci]
        (state.__setitem__(liquid_total_id(unit, j) if reg == "LIQUID" else vapor_total_id(unit, j), sum(m)))
        LOG.append({"sweep": j, "reg": reg, "T": T})

orig_proposal = pc._proposal
orig_converged = rg._LiftedOps.converged

def apply(conv, frozen, ops):
    chain = {s.unit for s in ops._splits}
    if conv is None or MODE != "close" or conforms(tuple(e for e in conv.signature if e[0] in chain)):
        return conv
    chain = {s.unit for s in ops._splits}
    units_only = tuple(e for e in conv.signature if e[0] in chain)
    new = closure(frozen, units_only)
    LOG.append({"closure_of": [r[:2] for _, r in units_only], "to": None if new is None else [r[:2] for _, r in new]})
    if new is None:
        return conv
    state, regimes = conv.opening
    state, regimes = dict(state), dict(regimes)
    for u, r in new:
        if regimes.get(u) != r:
            split = next(s for s in ops._splits if s.unit == u)
            rg._pin(state, split, r)
            regimes[u] = r
    if os.environ.get("S08_SWEEP") == "1":
        block_sweep(state, regimes, frozen, ops)
    sig = ops._signature(regimes, state)
    return pc.Conversion(signature=sig, opening=(state, regimes), source=conv.source,
                         cause=conv.cause + "; block_closure", trial=conv.trial,
                         observations=conv.observations, fallbacks=conv.fallbacks)

def proposal(result, frozen, wall, ops):
    conv = orig_proposal(result, frozen, wall, ops)
    conv2 = apply(conv, frozen, ops)
    LOG.append({"frozen": [r[:2] for _, r in frozen], "core": result.outcome, "blocked_by": list(getattr(result, "blocked_by", ()))[:3],
                "proposal": None if conv is None else [r[:2] for _, r in conv.signature], "cause": None if conv is None else conv.cause,
                "final": None if conv2 is None else [r[:2] for _, r in conv2.signature]})
    return conv2

def converged(self, result):
    conv = orig_converged(self, result)
    LOG.append({"converged_check": None if conv is None else [r[:2] for _, r in conv.signature]})
    return apply(conv, tuple((s.unit, self._regimes[s.unit]) for s in self._splits), self)

pc._proposal = proposal
rg._LiftedOps.converged = converged

if __name__ == "__main__":
    case = sys.argv[1]
    from test_s02_column_wo1 import SPECS, PROVIDER
    globals()['SPEC'] = SPECS[case]
    ans = solve_column(SPECS[case], PROVIDER)
    print("OUTCOME", getattr(ans, "outcome", None), getattr(ans, "cause", None), getattr(ans, "signature", None))
    for res_name in ("recovered_from", "result"):
        res = getattr(ans, res_name, None)
        if res is None: continue
        for a in res.attempts:
            print(res_name, a.outcome, a.solver_outcome, [r[:2] for _, r in a.signature], a.iterations, a.reason)
    for e in LOG: print("LOG", e)
    if getattr(ans, "outcome", None) == "CONVERGED" and case == "P1":
        st = ans.state
        print({k: st[k] for k in st if k.endswith(".T") or "temperature" in k.lower()} )
