"""RC3 settings sweep: which BioSTEAM algorithm/settings converge the stripper (exploratory)."""

import json
import time
import warnings

warnings.filterwarnings("ignore")
import run_columns as rc  # noqa: E402  (after warnings.filterwarnings, as run)

SPEC = {4: ("Duty", 30000.0 * rc.W_TO_KJH)}
trials = [
    ("phenomena", "fixed-point", False),
    ("phenomena", "wegstein", False),
    ("sequential modular", "fixed-point", False),
    ("sequential modular", "wegstein", False),
    ("inside out", "fixed-point", False),
    ("inside out", "wegstein", False),
    (("phenomena", "simultaneous correction"), None, False),
    (("sequential modular", "simultaneous correction"), None, False),
]
out = []
for alg, meth, et in trials:
    algs = alg if isinstance(alg, tuple) else (alg,)
    col = rc.build("RC3", SPEC)
    col.algorithms = algs
    col.methods = (
        tuple(meth if a != "simultaneous correction" else "hybr" for a in algs)
        if meth
        else tuple(col.default_methods[a] for a in algs)
    )
    col.early_termination = et
    col.maxiter = 500
    col.tolerance = 1e-10
    col.relative_tolerance = 1e-10
    t0 = time.perf_counter()
    err = None
    try:
        col.simulate()
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:90]}"
    r = {
        "alg": algs,
        "method": col.methods,
        "err": err,
        "iter": col.iter,
        "wall": time.perf_counter() - t0,
        "best_r": getattr(col, "_best_result", None) and col._best_result.r,
    }
    if err is None:
        r["profile"] = rc.profile(col)
        r["bal"] = rc.balances(col)
    p = r.get("profile", {})
    print(
        algs,
        col.methods,
        "|",
        err,
        "| iter",
        col.iter,
        f"| {r['wall']:.1f}s | best_r",
        r["best_r"],
        "| T1",
        p.get("T[1]"),
        "T5",
        p.get("T[5]"),
        "B",
        p.get("L[5]"),
        r.get("bal"),
    )
    out.append(r)
json.dump(out, open("rc3_sweep.json", "w"), indent=1, default=str)
