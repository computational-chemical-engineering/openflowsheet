import json
import warnings

warnings.filterwarnings("ignore")
import run_columns as rc  # noqa: E402  (after warnings.filterwarnings, as run)

out = []
for alg in (None, "inside out", "phenomena", "simultaneous correction", "sequential modular"):
    col, r = rc.run("RC3", {4: ("Duty", 30000.0 * rc.W_TO_KJH)}, alg)
    p = r.get("profile", {})
    print(
        alg,
        "|",
        r["error"] and r["error"][:110],
        "| iter",
        r["iterations"],
        "| T1",
        p.get("T[1]"),
        "T5",
        p.get("T[5]"),
        "B",
        p.get("L[5]"),
        r.get("balances"),
    )
    out.append(r)
json.dump(out, open("rc3_algos.json", "w"), indent=1, default=str)
