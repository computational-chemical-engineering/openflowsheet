"""S09 design probe (NOT evidence): BioSTEAM's residual floors on NON-registered columns.

Written by the design lane (`specifier`) while authoring docs/derivations/S09-spec.md. It runs
no S03 case and reads nothing of this project but SYN-001's constants (re-typed below from
docs/derivations/SYN-001.md §1; the registered harness imports them from
spikes/references/t06_fixtures.py instead). Its states (feeds, stage counts, specifications) are
deliberately unlike RC1-RC7, so no number here can be compared with a twin or with our solver.

It measures, per S09 §6 rung and per probe column, the quantities S09's BioSTEAM rule 2 checks
read from the tool's own record: per-stage component balance, per-stage equilibrium residual |y
- (Psat/P) x|, adiabatic-stage duty, overall energy closure, the tool's iteration counter, and
the movement under the accuracy rerun (tolerance x 10). For the two outer-loop probes it records
the secant history (S09 §5.3's registered loop: starts 1 and 2).

Run with the BioSTEAM environment's interpreter: <venv>/bin/python -I floor_probe.py >
floor_probe.log
"""

import json
import math
import warnings

warnings.filterwarnings("ignore")

import biosteam as bst  # noqa: E402
import thermosteam as tmo  # noqa: E402

R = 8.31446261815324
P_R = 1.0e5
CP = 100.0
V_L = 1.0e-4
COMP = {"A": (320.0, 25000.0), "B": (360.0, 30000.0), "C": (400.0, 35000.0)}
IDS = tuple(COMP)
K = 3.6  # mol/s -> kmol/h and W -> kJ/h

RUNGS = (
    ("inside out", "fixed-point"),
    ("phenomena", "fixed-point"),
    ("simultaneous correction", "hybr"),
    ("sequential modular", "fixed-point"),
)


def chem(cid):
    t_b, lat = COMP[cid]
    c = tmo.Chemical.blank(cid, phase_ref="l", MW=100.0, Tb=t_b)
    c.Psat.add_method(
        f=lambda t, t_b=t_b, lat=lat: P_R * math.exp((lat / R) * (1.0 / t_b - 1.0 / t)),
        Tmin=200.0,
        Tmax=600.0,
    )
    c.Hvap.add_method(f=lambda t, lat=lat: lat, Tmin=200.0, Tmax=600.0)
    c.Cn.l.add_method(CP)
    c.Cn.g.add_method(CP)
    c.V.l.add_method(V_L)
    c.reset_free_energies()
    return c


CHEMS = tmo.Chemicals([chem(i) for i in IDS])
CHEMS.compile(skip_checks=True)
THERMO = tmo.IdealThermo(CHEMS, mixture=tmo.IdealMixture.from_chemicals(CHEMS), skip_checks=True)
bst.settings.set_thermo(THERMO)

# Non-registered probe columns (our stage numbering j = 1..N; BioSTEAM index j - 1).
PROBES = {
    "D1": {
        "N": 6,
        "feeds": [((0.25, 0.45, 0.30), 350.0, "l", 3)],
        "specs": {0: ("Reflux", 2.5), -1: ("Boilup", 1.8)},
    },
    "T1": {
        "N": 6,
        "feeds": [((0.25, 0.45, 0.30), 350.0, "l", 3)],
        "specs": {0: ("Reflux", math.inf), -1: ("Flow", 0.5)},
        "bottom_side_draws": {0: 1.0 / (1.0 + 2.0)},
    },
    "S1": {
        "N": 4,
        "feeds": [((0.25, 0.45, 0.30), 310.0, "l", 1)],
        "specs": {-1: ("Duty", 25000.0 * K)},
    },
    "A1": {
        "N": 4,
        "feeds": [((0.25, 0.45, 0.30), 390.0, "g", 4)],
        "specs": {0: ("Reflux", None)},
        "outer": {"stage": 0, "name": "Reflux", "target": ("V1", 0.6)},
    },
    "D1T": {
        "N": 6,
        "feeds": [((0.25, 0.45, 0.30), 350.0, "l", 3)],
        "specs": {0: ("Reflux", 2.5), -1: ("Boilup", None)},
        "outer": {"stage": -1, "name": "Boilup", "target": ("T5", None)},
    },
}


def build(p, rung, tol, spec_values):
    feeds = []
    for n, temp, ph, _ in p["feeds"]:
        feeds.append(
            bst.Stream(
                None,
                **{c: v * K for c, v in zip(IDS, n, strict=False)},
                T=temp,
                P=P_R,
                phase=ph,
                units="kmol/hr",
            )
        )
    kw = {}
    if "bottom_side_draws" in p:
        kw["bottom_side_draws"] = p["bottom_side_draws"]
    outs = ["", ""] + ([""] if kw else [])
    col = bst.MultiStageEquilibrium(
        None,
        ins=feeds,
        outs=outs,
        N_stages=p["N"],
        feed_stages=[s - 1 for (*_, s) in p["feeds"]],
        P=[P_R] * p["N"],
        phases=("g", "l"),
        stage_specifications=dict(spec_values),
        maxiter=500,
        max_attempts=1,
        use_cache=True,
        **kw,
    )
    col.algorithms = (rung[0],)
    col.methods = (rung[1],)
    col.early_termination = False
    col.tolerance = tol
    col.relative_tolerance = tol
    return col


STORED = {
    "Reflux": ("B", lambda v: math.inf if v == 0 else 1.0 / v),
    "Boilup": ("B", lambda v: v),
    "Duty": ("Q", lambda v: v),
    "Flow": ("F", lambda v: v),
    "Temperature": ("T", lambda v: v),
}


def respecify(col, spec_values):
    """Re-store each registered specification value as specify_variables stored it
    (stage.py:922-946), through the stage's own attribute setter. specify_variables itself is not
    called again: it clears partition.T (so the tool's cached point is discarded and its
    initializer runs again) and, without P=..., resets P to 101325 Pa."""
    n = len(col.stages)
    for idx, (name, value) in spec_values.items():
        attr, conv = STORED[name]
        setattr(col.stages[idx % n], attr, conv(value))


def residuals(col):
    worst_bal, worst_eq, worst_adiab, duties = 0.0, 0.0, 0.0, []
    for st in col.stages:
        bal = sum(i.mol for i in st.ins) - sum(o.mol for o in st.outs if o is not None)
        worst_bal = max(worst_bal, float(abs(bal).max()) / K)
        duty = (sum(o.H for o in st.outs if o is not None) - sum(i.H for i in st.ins)) / K
        duties.append(duty)
        if st.specified_variable == "Q" and st.Q == 0:
            worst_adiab = max(worst_adiab, abs(duty))
        v, liq = st.partition.outs
        temp, pres = st.partition.T, st.partition.P if st.partition.P is not None else st.P
        kc = [CHEMS[c].Psat(temp) / pres for c in IDS]
        x = liq.imol[IDS] / liq.F_mol if liq.F_mol > 0 else None
        if v.F_mol > 0 and x is not None:
            y = v.imol[IDS] / v.F_mol
            worst_eq = max(worst_eq, max(abs(y[i] - kc[i] * x[i]) for i in range(3)))
        elif x is not None:  # total condenser: bubble condition
            worst_eq = max(worst_eq, abs(sum(kc[i] * x[i] for i in range(3)) - 1.0))
    h_in = sum(f.H for f in col.ins)
    h_out = sum(o.H for o in col.outs)
    energy = abs(h_out - h_in - sum(duties) * K) / K
    return {
        "stage_component_mol_s": worst_bal,
        "equilibrium": worst_eq,
        "adiabatic_W": worst_adiab,
        "energy_W": energy,
    }


def quantities(col):
    q = {}
    for j, st in enumerate(col.stages, 1):
        v, liq = st.partition.outs
        q[f"T[{j}]"] = st.partition.T
        q[f"V[{j}]"] = v.F_mol / K
        q[f"L[{j}]"] = liq.F_mol / K
    q["Q_top"] = (
        sum(o.H for o in col.stages[0].outs if o is not None) - sum(i.H for i in col.stages[0].ins)
    ) / K
    q["Q_bottom"] = (
        sum(o.H for o in col.stages[-1].outs if o is not None)
        - sum(i.H for i in col.stages[-1].ins)
    ) / K
    return q


def solve(p, rung, tol, spec_values):
    """S09 §5.2's path: build, simulate, re-specify, simulate again."""
    col = build(p, rung, tol, spec_values)
    err = None
    try:
        col.simulate()
        respecify(col, spec_values)
        col.simulate()
    except Exception as e:  # recorded
        err = f"{type(e).__name__}: {str(e)[:100]}"
    return col, err


def target_value(col, target):
    kind, _ = target
    if kind == "V1":
        return col.stages[0].partition.outs[0].F_mol / K
    return col.stages[4].partition.T  # T5 (our stage 5 = index 4)


def outer(p, rung, tol, ytol):
    """S09 §5.4's registered loop: evaluate x = 1, 2; expand by factors of 2 (up if
    |g(2)| <= |g(1)|, else down, four steps at most) until the sign changes; then
    flexsolve.IQ_interpolation on the bracket; then one final fresh evaluation at the returned x,
    which is the record. Every evaluation is a fresh build and the full §5.2 path."""
    import flexsolve as flx

    o = p["outer"]
    fixed = {k: v for k, v in p["specs"].items() if v[1] is not None}
    target = o["target"]
    hist = []

    def run_at(x):
        sv = dict(fixed)
        sv[o["stage"]] = (o["name"], x)
        col, err = solve(p, rung, tol, sv)
        if err is None:
            r = residuals(col)
            if (
                r["stage_component_mol_s"] > 3.1e-8
                or r["equilibrium"] > 1e-8
                or r["adiabatic_W"] > 1e-3
            ):
                err = f"inner rule 2 failed at x={x!r}: {r}"
        g = math.nan if err else (target_value(col, target) - target[1]) / abs(target[1])
        hist.append((x, g, err))
        return col, err, g

    def g_only(x):
        col, err, g = run_at(x)
        if err:
            raise RuntimeError(err)
        return g

    try:
        _, e1, g1 = run_at(1.0)
        _, e2, g2 = run_at(2.0)
        if e1 or e2:
            raise RuntimeError(e1 or e2)
        a, ga, b, gb = 1.0, g1, 2.0, g2
        if ga * gb > 0:
            up = abs(g2) <= abs(g1)
            prev_x, prev_g = (2.0, g2) if up else (1.0, g1)
            for _ in range(4):
                x = prev_x * 2.0 if up else prev_x / 2.0
                gx = g_only(x)
                if gx * prev_g < 0:
                    a, ga, b, gb = prev_x, prev_g, x, gx
                    break
                prev_x, prev_g = x, gx
            else:
                raise RuntimeError("no bracket in [1/16, 32]")
        xs = flx.IQ_interpolation(g_only, a, b, ga, gb, None, 0.0, ytol, (), 50, False, True, True)
        col, err, gfin = run_at(xs)
        if err is None and not abs(gfin) <= ytol:
            err = f"final evaluation residual {gfin!r} above {ytol!r}"
    except Exception as e:  # recorded
        return None, f"{type(e).__name__}: {str(e)[:120]}", hist
    return col, err, hist


def main():
    out = {}
    # D1T's temperature target: D1's own T5 + 1 K (a tool value of a NON-registered column, so the
    # probe is self-contained).
    d1, _ = solve(PROBES["D1"], RUNGS[1], 1e-10, PROBES["D1"]["specs"])
    PROBES["D1T"]["outer"]["target"] = ("T5", d1.stages[4].partition.T + 1.0)
    for name, p in PROBES.items():
        rows = {}
        for rung in RUNGS:
            for tol in (1e-10, 1e-9):
                if "outer" in p:
                    ytol = 1e-11 if tol == 1e-10 else 1e-10
                    col, err, hist = outer(p, rung, tol, ytol)
                else:
                    col, err = solve(p, rung, tol, p["specs"])
                    hist = None
                rec = {
                    "error": err,
                    "iter": getattr(col, "iter", None),
                    "maxiter": getattr(col, "maxiter", None),
                }
                if err is None:
                    rec["residuals"] = residuals(col)
                    rec["quantities"] = quantities(col)
                if hist is not None:
                    rec["outer_history"] = hist
                rows[f"{rung[0]}|{tol:g}"] = rec
        out[name] = rows
        for key, rec in rows.items():
            r = rec.get("residuals", {})
            print(
                name,
                key,
                "err",
                rec["error"],
                "iter",
                rec["iter"],
                "res",
                {k: f"{v:.2e}" for k, v in r.items()},
                "outer_n",
                len(rec["outer_history"]) if rec.get("outer_history") else "-",
                "outer_last",
                f"{rec['outer_history'][-1][1]:.2e}" if rec.get("outer_history") else "-",
            )
        # Rerun movement (tol 1e-10 vs 1e-9) per rung, and spread across rungs at 1e-10.
        for rung in RUNGS:
            a, b = rows[f"{rung[0]}|1e-10"], rows[f"{rung[0]}|1e-09"]
            if "quantities" in a and "quantities" in b:
                d_t = max(
                    abs(a["quantities"][k] - b["quantities"][k])
                    for k in a["quantities"]
                    if k.startswith("T[")
                )
                d_f = max(
                    abs(a["quantities"][k] - b["quantities"][k])
                    for k in a["quantities"]
                    if k[0] in "LV"
                )
                d_q = max(
                    abs(a["quantities"][k] - b["quantities"][k]) for k in ("Q_top", "Q_bottom")
                )
                print(
                    name,
                    rung[0],
                    f"rerun move: T {d_t:.2e} K, flow {d_f:.2e} mol/s, duty {d_q:.2e} W",
                )
    json.dump(out, open("floor_probe.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
