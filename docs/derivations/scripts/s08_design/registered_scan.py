"""S08 measurement: every registered column case -> topological candidate, outcome, 2P consistency."""
import sys, math
sys.path.insert(0, "tests"); sys.path.insert(0, "scripts")
from test_s02_column_wo1 import SPECS as S02, REFERENCE as R02, _variant, PROVIDER
from test_s06_column_wo1 import J_CASES, V_SETS, U_SETS
import s03_references_ours as s03
from openflowsheet.models.syn001.column_solve import solve_column
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT as CTX

def topological(spec):
    N = spec.stage_count; stages = list(spec.equilibrium_stages())
    liq, vap = set(), set()
    if spec.condenser == "partial": liq.add(1)
    if spec.condenser == "total": liq.add(2)
    if spec.reboiler == "partial": vap.add(N)
    for f in spec.inlets():
        if sum(f.state.n) <= 0: continue
        (liq if f.state.phase == "LIQUID" else vap).add(f.stage)
    for j, q in enumerate(spec.duties, start=1):
        if q is not None and q < 0: liq.add(j)
        if q is not None and q > 0: vap.add(j)
    t = min(liq) if liq else None; s = max(vap) if vap else None
    out = []
    for j in stages:
        if t is not None and s is not None and t <= s:
            out.append("V" if j < t else "L" if j > s else "T")
        else:
            out.append("V" if (s is not None and j <= s) else "L" if (t is not None and j >= t) else "Z")
    return "".join(out)

cases = {}
for c in ("M1", "M2", "M3", "M4", "P1"): cases["S02." + c] = S02[c]
for c, vs in R02["variants"].items():
    for v in vs: 
        try: cases[f"S02.V-{c}.{v}"] = _variant(c, v)
        except Exception as e: pass
for k, v in J_CASES.items(): cases["S06." + k] = v
for k, v in V_SETS.items(): cases["S06.V." + k] = v
for k, v in U_SETS.items(): cases["S06.U." + k] = v
allc = s03.load_cases()
comps = tuple(allc.get("components", ("A", "B", "C"))) if isinstance(allc, dict) else ("A","B","C")
for cid, case in (allc["cases"].items() if "cases" in allc else allc.items()):
    try: cases["S03." + cid] = s03.column_spec(case, comps)
    except Exception as e: print("S03 spec fail", cid, type(e).__name__, str(e)[:80])

worst = 0.0; bad_topo = []
for name, spec in cases.items():
    topo = topological(spec)
    try:
        ans = solve_column(spec, PROVIDER)
    except Exception as e:
        print(f"{name:28s} topo={topo} EXC {type(e).__name__} {str(e)[:60]}"); continue
    out = getattr(ans, "outcome", "?")
    sig = "".join(r[0] for r in getattr(ans, "signature", ()) or ())
    m = 0.0; minLV = math.inf
    if out == "CONVERGED":
        st = ans.state; u = spec.unit_id
        for j, r in zip(spec.equilibrium_stages(), ans.signature):
            if r != "TWO_PHASE": continue
            T = st[f"{u}.stage.{j}.T"]; P = st[f"{u}.stage.{j}.P"]
            l = [st[f"{u}.stage.{j}.l.{c}"] for c in spec.components]; v = [st[f"{u}.stage.{j}.v.{c}"] for c in spec.components]
            minLV = min(minLV, sum(l), sum(v))
            for flows, beta in ((l, 0.0), (v, 1.0)):
                bt = band_temperature(PROVIDER, flows, P, beta, CTX)
                if bt.temperature is not None: m = max(m, abs(T - bt.temperature))
                else: m = math.inf
        worst = max(worst, m)
    if "L" in topo or "V" in topo or "Z" in topo: bad_topo.append(name)
    print(f"{name:28s} topo={topo} out={out:20s} sig={sig:8s} 2Pmargin={m:.2e} minLV={minLV:.3g}")
print("SUMMARY cases", len(cases), "worst_2P_equiv_T_error", worst, "non-all-2P topological:", bad_topo)
