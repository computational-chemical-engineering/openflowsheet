"""Q3: S03 cases on BioSTEAM's MultiStageEquilibrium with the SYN-001 mapping (syn001_thermo).

Case inputs are read from the repository's s03_cases.json (blind: no result of ours is read
here; compare_ours.py does the informal comparison afterwards). Units: BioSTEAM flows kmol/hr,
duties kJ/hr. Stage map: our stage j -> BioSTEAM stage j-1 (0 = top).
"""

import json
import sys
import time

import biosteam as bst
import numpy as np
import syn001_thermo as s

CASES = "/home/frankp/Codes/OpenFlowsheet/docs/derivations/scripts/s03_cases.json"
MOLS_TO_KMOLH = 3.6
W_TO_KJH = 3.6

thermo = s.make_thermo()
bst.settings.set_thermo(thermo)
cases = json.load(open(CASES))["cases"]


def inlet_stream(inlet, stream_id):
    n = [float(v) * MOLS_TO_KMOLH for v in inlet["n_mol_per_s"]]
    phase = {"LIQUID": "l", "VAPOR": "g"}[inlet["phase"]]
    return bst.Stream(
        stream_id,
        A=n[0],
        B=n[1],
        C=n[2],
        T=float(inlet["T_K"]),
        P=float(inlet["P_Pa"]),
        phase=phase,
        units="kmol/hr",
    )


def build(name, specs, algorithm=None):
    case = cases[name]
    n_stages = case["stage_count"]
    pressures = [float(p) for p in case["stage_pressures_Pa"]]
    feeds = [inlet_stream(i, f"{name}_in{k}") for k, i in enumerate(case["inlets"])]
    stages = [int(i["stage"]) - 1 for i in case["inlets"]]
    col = bst.MultiStageEquilibrium(
        f"{name}_col",
        ins=feeds,
        outs=["vapor", "liquid"],
        N_stages=n_stages,
        feed_stages=stages,
        P=pressures,
        phases=("g", "l"),
        stage_specifications=specs,
        maxiter=500,
    )
    # Spike settings (from rc3_sweep.py): the default algorithm chain fails RC3; 'phenomena' with
    # fixed-point, no early termination and tight tolerances converges RC1 and RC3.
    algorithm = algorithm or "phenomena"
    col.algorithms = (algorithm,)
    col.methods = (col.default_methods[algorithm],)
    col.early_termination = False
    col.tolerance = 1e-10
    col.relative_tolerance = 1e-10
    return col


def structural(col):
    return {
        "N_stages": len(col.stages),
        "stage_P": [st.partition.P if st.partition.P is not None else st.P for st in col.stages],
        "specs": [
            (i, st.specified_variable, getattr(st.partition, st.specified_variable, None))
            for i, st in enumerate(col.stages)
        ],
    }


def profile(col):
    temps, liqs, vaps, duties = [], [], [], []
    for st in col.stages:
        p = st.partition
        temps.append(p.T)
        vaps.append(p.outs[0].F_mol / MOLS_TO_KMOLH)
        liqs.append(p.outs[1].F_mol / MOLS_TO_KMOLH)
        # Stage duty from the stage's own streams (StageEquilibrium.Q returns only a specified
        # value).
        duties.append(
            (sum(o.H for o in st.outs if o is not None) - sum(i.H for i in st.ins)) / W_TO_KJH
        )
    top, bottom = col.outs[0], col.outs[1]
    out = {f"T[{j + 1}]": temps[j] for j in range(len(temps))}
    out.update({f"L[{j + 1}]": liqs[j] for j in range(len(liqs))})
    out.update({f"V[{j + 1}]": vaps[j] for j in range(len(vaps))})
    for c in "ABC":
        out[f"top[{c}]"] = top.imol[c] / MOLS_TO_KMOLH
        out[f"bottom[{c}]"] = bottom.imol[c] / MOLS_TO_KMOLH
    out["Q_stage_W"] = duties
    return out


def balances(col):
    fin = sum(f.mol for f in col.ins)
    fout = sum(o.mol for o in col.outs)
    h_in = sum(f.H for f in col.ins)
    h_out = sum(o.H for o in col.outs)
    q_sum = sum(
        sum(o.H for o in st.outs if o is not None) - sum(i.H for i in st.ins) for st in col.stages
    )
    return {
        "component_abs_kmolh": float(np.abs(fin - fout).max()),
        "energy_abs_W": float(abs(h_out - h_in - q_sum) / W_TO_KJH),
        "adiabatic_stage_max_abs_W": max(
            abs(q)
            for q, st in zip(profile(col)["Q_stage_W"], col.stages, strict=False)
            if st.specified_variable == "Q" and st.Q == 0
        )
        if any(st.specified_variable == "Q" and st.Q == 0 for st in col.stages)
        else None,
    }


def run(name, specs, algorithm=None):
    col = build(name, specs, algorithm)
    t0 = time.perf_counter()
    err = None
    try:
        col.simulate()
    except Exception as e:  # recorded, not hidden
        err = f"{type(e).__name__}: {e}"
    dt = time.perf_counter() - t0
    rec = {
        "case": name,
        "specs": {str(k): v for k, v in specs.items()},
        "algorithm": algorithm or "default",
        "error": err,
        "wall_s": dt,
        "iterations": getattr(col, "iter", None),
        "attempt": getattr(col, "attempt", None),
        "structure": structural(col),
    }
    if err is None:
        rec["profile"] = profile(col)
        rec["balances"] = balances(col)
    return col, rec


def rc4_outer_loop(d_target=0.5, algorithm=None):
    """EXPLORATORY, not an S03 level: secant on the stage-0 reflux ratio until V[1] = D*."""

    def g(rr):
        col, rec = run("RC4", {0: ("Reflux", rr)}, algorithm)
        return (
            col,
            rec,
            (rec["profile"]["V[1]"] - d_target if rec["error"] is None else float("nan")),
        )

    hist = []
    x0, x1 = 1.0, 1.5
    _, r0, f0 = g(x0)
    hist.append((x0, f0))
    col, r1, f1 = g(x1)
    hist.append((x1, f1))
    for _ in range(30):
        if abs(f1) < 1e-12:
            break
        x0, x1, f0 = x1, x1 - f1 * (x1 - x0) / (f1 - f0), f1
        col, r1, f1 = g(x1)
        hist.append((x1, f1))
    r1["outer_loop"] = {"reflux_ratio": x1, "residual_D": f1, "history": hist}
    return col, r1


if __name__ == "__main__":
    which = sys.argv[1:] or ["RC1", "RC3", "RC4", "RC7"]
    records = []
    for name in which:
        if name == "RC1":
            records.append(run("RC1", {0: ("Reflux", 2.0), -1: ("Boilup", 1.5)})[1])
        elif name == "RC3":
            records.append(run("RC3", {4: ("Duty", 30000.0 * W_TO_KJH)})[1])
        elif name == "RC4":
            records.append(rc4_outer_loop()[1])
        elif name == "RC7":
            # The closest native realization: T on stage 6 (index 5) replaces stage 6's energy
            # balance and
            # leaves stage 7 adiabatic, which is NOT RC7 (RC7: stage 6 adiabatic, reboiler duty
            # free).
            records.append(run("RC7", {0: ("Reflux", 2.0), 5: ("Temperature", 368.0)})[1])
    json.dump(records, open("columns.json", "w"), indent=1, default=str)
    for r in records:
        p = r.get("profile", {})
        print(
            r["case"],
            "err",
            r["error"],
            "iter",
            r["iterations"],
            f"wall {r['wall_s']:.2f}s",
            "T1",
            p.get("T[1]"),
            "TN",
            p.get(f"T[{r['structure']['N_stages']}]"),
            "bal",
            r.get("balances"),
        )
