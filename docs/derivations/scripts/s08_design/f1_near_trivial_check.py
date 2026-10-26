import math
import sys
from dataclasses import replace

sys.argv = ["x", "F1"]
# The prototype's module body (everything before its __main__ block), executed into a namespace.
_NS: dict = {}
exec(
    open(__file__.replace("f1_near_trivial_check.py", "block_endpoint_prototype.py"))
    .read()
    .split('if __name__ == "__main__":')[0],
    _NS,
)
SPECS, SideFeed, InletState, FEED = _NS["SPECS"], _NS["SideFeed"], _NS["InletState"], _NS["FEED"]
solve_column, PROVIDER, run, CTX = _NS["solve_column"], _NS["PROVIDER"], _NS["run"], _NS["CTX"]
ln_k, band_temperature = _NS["ln_k"], _NS["band_temperature"]

spec = replace(
    SPECS["M4"],
    sides=(SideFeed("feed", 3, InletState(FEED, 385.0, 1.02e5, "VAPOR")),),
    bottom=InletState((0.03, 0.04, 0.03), 330.0, 1.04e5, "LIQUID"),
)
for label, ans_state in (
    ("today", solve_column(spec, PROVIDER).state),
    ("block", run(spec, {1: "2P", 2: "2P", 3: "2P", 4: "L", 5: "L"})[4]),
):
    u = spec.unit_id
    for j in (3, 4):
        T = ans_state[f"{u}.stage.{j}.T"]
        P = ans_state[f"{u}.stage.{j}.P"]
        lf = [ans_state[f"{u}.stage.{j}.l.{c}"] for c in spec.components]
        v = [ans_state[f"{u}.stage.{j}.v.{c}"] for c in spec.components]
        L = sum(lf)
        V = sum(v)
        sk = sum(math.exp(ln_k(T, P, i)) * lf[i] / L for i in range(3))
        bt = band_temperature(PROVIDER, lf, P, 0.0, CTX).temperature
        eq = [v[i] * L - math.exp(ln_k(T, P, i)) * lf[i] * V for i in range(3)]
        print(label, j, "T", T, "Tbub", bt, "sumKx", sk, "V", V, "eqrows", eq)
