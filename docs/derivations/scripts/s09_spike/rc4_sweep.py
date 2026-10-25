"""RC4 inner-column diagnostic: which algorithm converges the refluxed absorber at a fixed reflux
ratio. DIAGNOSTIC ONLY: RR = 1.23419018 is our own twin's value (S03 table), so this is not a
blind run.
"""

import json
import warnings

warnings.filterwarnings("ignore")
import run_columns as rc  # noqa: E402  (after warnings.filterwarnings, as run)

out = []
for rr in (1.23419018, 1.0, 2.0):
    for alg in ("phenomena", "sequential modular", "inside out", "simultaneous correction"):
        try:
            col, r = rc.run("RC4", {0: ("Reflux", rr)}, alg)
        except Exception as e:
            print(rr, alg, "build/run exception", e)
            continue
        p = r.get("profile", {})
        print(
            rr,
            alg,
            "|",
            r["error"] and r["error"][:80],
            "| iter",
            r["iterations"],
            "| T1",
            p.get("T[1]"),
            "T5",
            p.get("T[5]"),
            "D",
            p.get("V[1]"),
            "spec",
            r["structure"]["specs"][0],
            r.get("balances"),
        )
        out.append(r)
json.dump(out, open("rc4_sweep.json", "w"), indent=1, default=str)
