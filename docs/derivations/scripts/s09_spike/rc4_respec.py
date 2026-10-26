"""RC4 diagnostic: the single-specification initializer (biosteam stage.py ~3285-3298) overwrites
the stage-0 reflux spec. Workaround probe: solve once, re-impose the spec, re-solve from the
cached point (use_cache=True). DIAGNOSTIC: RR = 1.23419018 is our twin's value; this checks the
tool's capability, it is not a blind run.
"""

import warnings

warnings.filterwarnings("ignore")
import run_columns as rc  # noqa: E402  (after warnings.filterwarnings, as run)


def solve_rr(rr, alg="phenomena", passes=3):
    col = rc.build("RC4", {0: ("Reflux", rr)}, alg)
    col.use_cache = True
    log = []
    for k in range(passes):
        col.stages[0].B = 1.0 / rr  # re-impose the specification the initializer overwrote
        col.simulate()
        p = rc.profile(col)
        log.append(
            (k, col.stages[0].B, p["V[1]"], rc.balances(col)["adiabatic_stage_max_abs_W"], col.iter)
        )
    return col, log


if __name__ == "__main__":
    for alg in ("phenomena", "sequential modular"):
        col, log = solve_rr(1.23419018, alg)
        for row in log:
            print(alg, "pass {} B {:.12g} D {:.12g} adiabatic_res_W {:.3e} iter {}".format(*row))
        p = rc.profile(col)
        print(
            alg,
            "T",
            [round(p[f"T[{j}]"], 8) for j in range(1, 6)],
            "Qcond",
            p["Q_stage_W"][0],
            "L",
            [round(p[f"L[{j}]"], 8) for j in range(1, 6)],
        )
