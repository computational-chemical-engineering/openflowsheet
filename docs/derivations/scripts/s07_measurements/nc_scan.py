"""S07 near-critical saturation scan (design note `docs/design/S07-near-critical-saturation.md`,
gates G1, G2, G3 and G8) over the 123 admitted fluids.

Grid per fluid: T_lo, T_σ,max, and T_c(1 − θ) for θ log-spaced 40 per decade from
min(0.5, 1 − T_lo/T_c) down to `THETA_FALLBACK_MIN`, the endpoint included. A grid T whose
computed 1 − T/T_c falls below θ_min by rounding (T_c(1 − 5e-5) does for every fluid) is moved
down to the nearest double at which it does not, so every point lies in the fallback's domain.
At each T:

- G1: `_solve_saturation(T)` is not `None`; counts the points where the fallback ran, its polish
  iterations and the `_jet` calls made inside it (G8: a regression tripwire of ≤ 500 per T, spec
  §19.3; the hard bound set by the loop limits is 6906, plus up to 100 for the failed plain Newton);
  the whole solve's calls, the failed Newton included, are reported beside it.
- G2: where the Newton from the ancillary seeds converges, the result is bitwise (repr) that
  Newton's and the fallback is not entered.
- G3: where that Newton converges and θ ≥ θ_min, the fallback forced from the same T; relative
  differences of ρ', ρ'' and p_σ against the plain root, split at θ = 1e-2 (spec §19.2, A47:
  densities 1e-11 above and 3e-8 below; p_σ 1e-12 above and 1e-10 below).

Writes argv[1] (JSON: per-fluid worsts, every failing point and every T at which the fallback ran;
the highest θ of the last per fluid is spec §19.5's reference set, registered once in
`s07_reference.py`'s `NC_FALLBACK_T`) and prints one summary line.
Scratch CoolProp venv; `PYTHONPATH=src`.
"""

import json
import math
import sys
from multiprocessing import Pool

from openflowsheet.thermo import coolprop_heos as ch

PER_DECADE = 40
#: Spec §19.2 (A47) and §19.3 (G8), R-626.
G3_FAR_RHO, G3_NEAR_RHO, G3_FAR_P, G3_NEAR_P = 1e-11, 3e-8, 1e-12, 1e-10
G8_TRIPWIRE = 500


def grid(fluid):
    top = min(0.5, 1.0 - fluid.t_lo / fluid.t_c)
    thetas, k = [], 0
    while True:
        theta = top * 10.0 ** (-k / PER_DECADE)
        if theta < ch.THETA_FALLBACK_MIN:
            break
        thetas.append(theta)
        k += 1
    thetas.append(ch.THETA_FALLBACK_MIN)
    temperatures = [fluid.t_lo, fluid.t_sigma_max]
    for theta in thetas:
        t = fluid.t_c * (1.0 - theta)
        while 1.0 - t / fluid.t_c < ch.THETA_FALLBACK_MIN:
            t = math.nextafter(t, 0.0)
        temperatures.append(t)
    return temperatures


def scan(component):
    provider = ch.CoolPropHeosProvider(component)
    assert provider._guard() is None, component
    fluid, seeds = provider._fluid, provider._seeds
    jets = [0]
    original_jet = provider._jet

    def jet(t, rho):
        jets[0] += 1
        return original_jet(t, rho)

    provider._jet = jet
    entered, inside = [0], [0]
    original_fallback = provider._maxwell_fallback

    def fallback(t, seed_v):
        entered[0] += 1
        before = jets[0]
        result = original_fallback(t, seed_v)
        inside[0] = jets[0] - before
        return result

    provider._maxwell_fallback = fallback
    out = {
        "points": 0,
        "solved": 0,
        "fallback": 0,
        "max_polish": 0,
        "max_jets": 0,
        "max_solve_jets": 0,
        "g1_fail": [],
        "g2_fail": [],
        "g3_rows": [],
        "forced_none": [],
        "fallback_t": [],
    }
    for t in grid(fluid):
        theta = 1.0 - t / fluid.t_c
        out["points"] += 1
        rho_l, rho_v = seeds.rho_l(t, fluid.t_c), seeds.rho_v(t, fluid.t_c)
        plain = None
        if ch._usable(rho_l) and ch._usable(rho_v):
            plain = provider._maxwell_newton(t, rho_l / fluid.rho_red, rho_v / fluid.rho_red)
        entered[0], jets[0] = 0, 0
        result = provider._solve_saturation(t)
        if result is None:
            out["g1_fail"].append(theta)
        else:
            out["solved"] += 1
        if entered[0]:
            out["fallback"] += 1
            out["fallback_t"].append(t)
            out["max_jets"] = max(out["max_jets"], inside[0])
            out["max_solve_jets"] = max(out["max_solve_jets"], jets[0])
            if result is not None:
                out["max_polish"] = max(out["max_polish"], result.iterations)
        if plain is not None:
            if entered[0] or repr(result) != repr(plain):
                out["g2_fail"].append(theta)
            if theta >= ch.THETA_FALLBACK_MIN:
                forced = original_fallback(t, rho_v)
                if forced is None:
                    out["forced_none"].append(theta)
                else:
                    out["g3_rows"].append(
                        (
                            theta,
                            abs(forced.rho_l - plain.rho_l) / plain.rho_l,
                            abs(forced.rho_v - plain.rho_v) / plain.rho_v,
                            abs(forced.pressure - plain.pressure) / plain.pressure,
                        )
                    )
    return component, out


def main():
    components = [row["id"] for row in ch.CoolPropHeosProvider.admitted()]
    with Pool() as pool:
        results = dict(pool.map(scan, components))
    total = {key: sum(r[key] for r in results.values()) for key in ("points", "solved", "fallback")}
    g1 = sum(len(r["g1_fail"]) for r in results.values())
    g2 = sum(len(r["g2_fail"]) for r in results.values())
    rows = [row for r in results.values() for row in r["g3_rows"]]
    far = [row for row in rows if row[0] >= 1e-2]
    near = [row for row in rows if row[0] < 1e-2]

    def worst(sel, i):
        return max((row[i] for row in sel), default=0.0)

    forced_none = sorted(theta for r in results.values() for theta in r["forced_none"])
    summary = {
        "fluids": len(results),
        **total,
        "g1_failures": g1,
        "g2_failures": g2,
        "max_polish": max(r["max_polish"] for r in results.values()),
        "max_fallback_jets": max(r["max_jets"] for r in results.values()),
        "max_solve_jets": max(r["max_solve_jets"] for r in results.values()),
        "g3_pairs": len(rows),
        "g3_far_rho": max(worst(far, 1), worst(far, 2)),
        "g3_near_rho": max(worst(near, 1), worst(near, 2)),
        "g3_far_p": worst(far, 3),
        "g3_near_p": worst(near, 3),
        "forced_none": len(forced_none),
        "forced_none_min_theta": forced_none[0] if forced_none else None,
    }
    with open(sys.argv[1], "w") as handle:
        json.dump({"summary": summary, "fluids": results}, handle, indent=1)
    ok = (
        g1 == 0
        and g2 == 0
        and summary["max_fallback_jets"] <= G8_TRIPWIRE
        and summary["g3_far_rho"] <= G3_FAR_RHO
        and summary["g3_near_rho"] <= G3_NEAR_RHO
        and summary["g3_far_p"] <= G3_FAR_P
        and summary["g3_near_p"] <= G3_NEAR_P
    )
    print(
        ("PASS " if ok else "FAIL ")
        + " ".join(
            f"{k}={v:.2e}" if isinstance(v, float) and not math.isnan(v) else f"{k}={v}"
            for k, v in summary.items()
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
