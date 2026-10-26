"""S09 Amendment 1 design probe (NOT evidence): the L2(c) accuracy rerun on NON-registered columns.

Written by the design lane (`specifier`) for docs/derivations/S09-spec.md §18.4. It runs no S03
case and reads nothing of this project but SYN-001's constants (through floor_probe.py, which
re-types them from docs/derivations/SYN-001.md §1). Its two columns are floor_probe.py's outer-loop
probes A1 (a rate specification, V1 = 0.6 mol/s) and D1T (a temperature specification, D1's own T5
+ 1 K), both deliberately unlike RC1-RC7.

Per rung it runs the registered loop (S09 §5.4) at tolerance 1e-10 with ytol = rule 2d's threshold
/ 10 (rate 1e-9, temperature 1e-10), and then both forms of the accuracy rerun:
- "amended" (S09 §18.4): one fresh evaluation, the full §5.2 path, at the loop's final x with
  tolerance 1e-9 and no outer loop;
- "original" (S09 §5.5 before Amendment 1): the whole loop again at tolerance 1e-9 and ytol x 10.
It prints, per rung, each rerun's largest movement of a probe quantity in S03 §6 tolerances
(a_k + 1e-6 |v|, v the registered run's own value) and each run's final |g| relative to rule 2d's
threshold. Nothing here is a threshold; the numbers are facts about two non-registered columns.

Run with the BioSTEAM environment's interpreter, from this directory:
<venv>/bin/python -I rerun_probe.py > rerun_probe.log
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import floor_probe as fp  # noqa: E402

ALLOW = {"T": 1e-5, "flow": 3.1e-7, "duty": 1e-2}  # S03 §6's a_k (K, mol/s, W)
THRESHOLD = {"A1": 1e-8, "D1T": 1e-9}  # rule 2d: rate 1e-8 relative, temperature 1e-9 relative


def tolerance(name, value):
    kind = "T" if name.startswith("T[") else ("duty" if name.startswith("Q") else "flow")
    return ALLOW[kind] + 1e-6 * abs(value)


def movement(base, other):
    ratios = {k: abs(other[k] - base[k]) / tolerance(k, base[k]) for k in base}
    worst = max(ratios, key=lambda k: ratios[k])
    return ratios[worst], worst


def main():
    d1, _ = fp.solve(fp.PROBES["D1"], fp.RUNGS[1], 1e-10, fp.PROBES["D1"]["specs"])
    fp.PROBES["D1T"]["outer"]["target"] = ("T5", d1.stages[4].partition.T + 1.0)
    for name in ("A1", "D1T"):
        p = fp.PROBES[name]
        o = p["outer"]
        theta = THRESHOLD[name]
        for rung in fp.RUNGS:
            col, err, hist = fp.outer(p, rung, 1e-10, theta / 10)
            if err is not None:
                print(name, rung[0], "registered loop failed:", err[:90])
                continue
            x_star, g_star, _ = hist[-1]
            base = fp.quantities(col)
            # Amended rerun: one fresh evaluation at x_star, tolerance 1e-9, no outer loop.
            specs = {k: v for k, v in p["specs"].items() if v[1] is not None}
            specs[o["stage"]] = (o["name"], x_star)
            col_a, err_a = fp.solve(p, rung, 1e-9, specs)
            line = [
                name,
                rung[0],
                f"x*={x_star!r}",
                f"n_eval={len(hist)}",
                f"|g|/theta={abs(g_star) / theta:.3e}",
            ]
            if err_a is None:
                r = fp.residuals(col_a)
                inner_ok = (
                    r["stage_component_mol_s"] <= 3.1e-8
                    and r["equilibrium"] <= 1e-8
                    and r["adiabatic_W"] <= 1e-3
                )
                target = fp.target_value(col_a, o["target"])
                g_a = (target - o["target"][1]) / abs(o["target"][1])
                m_a, k_a = movement(base, fp.quantities(col_a))
                line += [
                    f"amended: rule2 {'pass' if inner_ok else 'FAIL'}",
                    f"move {m_a:.3e} tol ({k_a})",
                    f"|g|/theta {abs(g_a) / theta:.3e}",
                ]
            else:
                line += [f"amended: error {err_a[:60]}"]
            # Original rerun: the whole loop at tolerance 1e-9 and ytol = theta.
            col_o, err_o, hist_o = fp.outer(p, rung, 1e-9, theta)
            if err_o is None:
                m_o, k_o = movement(base, fp.quantities(col_o))
                line += [
                    f"original: move {m_o:.3e} tol ({k_o})",
                    f"|g|/theta {abs(hist_o[-1][1]) / theta:.3e}",
                    f"n_eval={len(hist_o)}",
                ]
            else:
                line += [f"original: error {err_o[:60]}"]
            print(" | ".join(line))
    print("finite:", all(math.isfinite(v) for v in fp.quantities(d1).values()))


if __name__ == "__main__":
    main()
