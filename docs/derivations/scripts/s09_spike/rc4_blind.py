"""RC4 blind (EXPLORATORY, not an S03 level): secant on the reflux ratio until V[1] = D* = 0.5,
each inner solve with the re-specification workaround of rc4_respec.py. Starting guesses 1.0 and
1.5 are arbitrary.
"""

import json
import warnings

warnings.filterwarnings("ignore")
import run_columns as rc  # noqa: E402  (after warnings.filterwarnings, as run)
from rc4_respec import solve_rr  # noqa: E402

D = float(rc.cases["RC4"]["specifications"]["condenser"]["value"])


def g(rr):
    col, log = solve_rr(rr, "phenomena", passes=3)
    return col, rc.profile(col)["V[1]"] - D


hist = []
x0, x1 = 1.0, 1.5
_, f0 = g(x0)
hist.append((x0, f0))
col, f1 = g(x1)
hist.append((x1, f1))
for _ in range(30):
    if abs(f1) < 1e-13:
        break
    x0, x1, f0 = x1, x1 - f1 * (x1 - x0) / (f1 - f0), f1
    col, f1 = g(x1)
    hist.append((x1, f1))
p = rc.profile(col)
rec = {
    "case": "RC4",
    "realization": "outer secant on Reflux + re-spec workaround",
    "reflux_ratio": x1,
    "history": hist,
    "profile": p,
    "balances": rc.balances(col),
}
json.dump(rec, open("rc4_blind.json", "w"), indent=1, default=str)
print(f"RR {x1:.12f} residual {f1:.3e} outer_iters {len(hist)}", "bal", rec["balances"])
