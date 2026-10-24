"""WO-S07-2b record (Q-A1-5): where the provider's saturation solve (S05's Newton in (δ', δ''),
seeded by CoolProp's ancillaries, B-19) fails near T_c, for all 123 fluids, at
θ = 1 − T/T_c ∈ THETAS (T ≥ T_lo).

The provider needs the saturation at every T < T_c it answers: `Psat` on [T_lo, T_σ,max]
(θ ≥ 2e-4), and the density bracket in the strip (T_σ,max, T_c) outside the near-critical box.

Also measured, as a diagnostic and NOT in the provider: the same Newton with its step halved until
ρ' > ρ_c > ρ'' holds ("damped"), and the seed error as a fraction of ρ' − ρ'' (CoolProp's QT
densities). Run from the repository root with CoolProp 8.0.0 and `PYTHONPATH=src`; writes argv[1].
"""

import json
import math
import sys
from typing import Any

from CoolProp.CoolProp import QT_INPUTS, AbstractState

from openflowsheet.thermo import _coolprop_heos_fluids as table
from openflowsheet.thermo import coolprop_heos as cph

THETAS = [3e-2, 1e-2, 5e-3, 2e-3, 1e-3, 5e-4, 2e-4, 1e-4, 5e-5, 2e-5, 1e-5, 3e-6, 1e-6]


def damped(provider: Any, t: float) -> tuple[tuple[float, float, int, int] | None, str]:
    fluid, seeds = provider._fluid, provider._seeds
    dc = fluid.rho_c / fluid.rho_red
    dl = seeds.rho_l(t, fluid.t_c) / fluid.rho_red
    dv = seeds.rho_v(t, fluid.t_c) / fluid.rho_red
    if not dl > dc > dv > 0:
        return None, "seed outside"
    previous, halvings = math.inf, 0
    for iteration in range(1, 200):
        (_, rl), (_, rv) = (
            provider._jet(t, dl * fluid.rho_red),
            provider._jet(t, dv * fluid.rho_red),
        )
        kl = 1 + 2 * dl * rl.d + dl * dl * rl.dd
        kv = 1 + 2 * dv * rv.d + dv * dv * rv.dd
        f1 = dl * (1 + dl * rl.d) - dv * (1 + dv * rv.d)
        f2 = (rl.phi + dl * rl.d + math.log(dl)) - (rv.phi + dv * rv.d + math.log(dv))
        spread = 1 / dl - 1 / dv
        step_l, step_v = -(f2 - f1 / dv) / (kl * spread), -(f2 - f1 / dl) / (kv * spread)
        lam = 1.0
        while not dl + lam * step_l > dc > dv + lam * step_v > 0:
            lam *= 0.5
            halvings += 1
            if lam < 1e-12:
                return None, "stuck"
        dl, dv = dl + lam * step_l, dv + lam * step_v
        step = max(abs(lam * step_l) / dl, abs(lam * step_v) / dv)
        if lam == 1.0 and cph._converged(step, previous):
            return (dl * fluid.rho_red, dv * fluid.rho_red, iteration, halvings), "ok"
        previous = step if lam == 1.0 else math.inf
    return None, "maxit"


def main() -> None:
    out = {}
    for row in table.FLUIDS:
        cid = row["id"]
        provider = cph.CoolPropHeosProvider(cid)
        assert provider._guard() is None
        fluid = provider._fluid
        state = AbstractState("HEOS", fluid.name)
        fails, damped_fails, seed_error, damped_iterations = [], [], 0.0, 0
        for theta in THETAS:
            t = fluid.t_c * (1 - theta)
            if t < fluid.t_lo:
                continue
            solved = provider._solve_saturation(t)
            if solved is None:
                fails.append(theta)
            result, why = damped(provider, t)
            if result is None:
                damped_fails.append([theta, why])
            else:
                damped_iterations = max(damped_iterations, result[2])
                if solved is not None:  # damping never acts where the provider converges
                    assert result[3] == 0, (cid, theta)
                    assert (solved.rho_l, solved.rho_v) == result[:2], (cid, theta)
            try:
                state.update(QT_INPUTS, 0, t)
                rho_l = state.rhomolar()
                state.update(QT_INPUTS, 1, t)
                rho_v = state.rhomolar()
            except ValueError:
                continue
            width = rho_l - rho_v
            seeds = provider._seeds
            assert seeds is not None
            seed_l, seed_v = seeds.rho_l(t, fluid.t_c), seeds.rho_v(t, fluid.t_c)
            seed_error = max(seed_error, abs(seed_l - rho_l) / width, abs(seed_v - rho_v) / width)
        out[cid] = {
            "tier": row["tier"],
            "fails": fails,
            "damped_fails": damped_fails,
            "seed_error_over_width": seed_error,
            "damped_iterations": damped_iterations,
        }
    with open(sys.argv[1], "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1)
    failing = {c: r for c, r in out.items() if r["fails"]}
    print("fluids failing at some theta:", len(failing), "of", len(out))
    for cid, r in sorted(failing.items(), key=lambda item: -max(item[1]["fails"])):
        print(
            f"  {cid} ({r['tier']}): highest failing theta {max(r['fails']):g}; damped fails at "
            f"{[f[0] for f in r['damped_fails']]}; "
            f"seed error/width {r['seed_error_over_width']:.2f}"
        )


if __name__ == "__main__":
    main()
