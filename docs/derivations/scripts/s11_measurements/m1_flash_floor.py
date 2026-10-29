"""S11 measurement 1 (R-845): CoolProp 8.0.0's single-phase PH/PS flash floor at the states of
`benchmarks/s11/thermal_reference.yaml`, on the machine that runs it.

For every flash the generator makes whose answer is LIQUID or VAPOR (40 of them), with T0 its
answer at the generator's own input x0 (h or s) and pressure P0:
- an ulp scan: T at x0·(1 + k·eps), 0 < |k| <= K_ULP;
- random draws: T at (x0·(1 + a), P0·(1 + b)), a and b uniform in [-1e-12, 1e-12], N_RANDOM draws
  (seed 845);
- each answer's deviation from the smooth prediction T0 + (x - x0)·dT/dx + (P - P0)·dT/dP (dT/dx
  = 1/c_p for PH, T/c_p for PS, c_p CoolProp's at (T0, P0); dT/dP by a central difference of
  step 1e-3·P0), divided by T0.
It also prints TH-C1's pump-outlet entry (CI 40861460178 printed 2.403e+00 there on aarch64) and
the mapping of the energy class's aarch64 worst (1.536e-9 J/mol) to temperature through 1/c_p.

A measurement, not an expectation: no test reads its output. The executable form of its claim is
the generator's own grid assertion (R-845). Run from the repository root with the pinned CoolProp:
    PYTHONPATH=<coolprop-site> python docs/derivations/scripts/s11_measurements/m1_flash_floor.py
The last line is the summary.
"""

import importlib.util
import random
import sys
from pathlib import Path

GENERATOR = Path(__file__).resolve().parents[1] / "s11_thermal_reference.py"
K_ULP = 2048
N_RANDOM = 5000
EPS = sys.float_info.epsilon


def _generator():
    spec = importlib.util.spec_from_file_location("s11_thermal_reference", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    gen = _generator()
    calls = []
    ph, ps = gen._Fluid.ph, gen._Fluid.ps

    def record_ph(self, pressure, enthalpy):
        answer = ph(self, pressure, enthalpy)
        calls.append((self, "Hmolar", pressure, enthalpy, answer))
        return answer

    def record_ps(self, pressure, entropy):
        answer = ps(self, pressure, entropy)
        calls.append((self, "Smolar", pressure, entropy, answer))
        return answer

    gen._Fluid.ph, gen._Fluid.ps = record_ph, record_ps
    gen.build()
    cp = gen._coolprop()
    rng = random.Random(845)
    seen, overall, rows = set(), (0.0, "-"), 0
    for fluid, inp, p0, x0, answer in calls:
        if answer["regime"] == "SATURATED" or (fluid.name, inp, p0, x0) in seen:
            continue
        seen.add((fluid.name, inp, p0, x0))
        rows += 1
        name = fluid.name
        t0 = cp.PropsSI("T", "P", p0, inp, x0, name)
        cpm = cp.PropsSI("Cpmolar", "T", t0, "P", p0, name)
        dtdx = 1.0 / cpm if inp == "Hmolar" else t0 / cpm
        dp = 1e-3 * p0
        dtdp = (
            cp.PropsSI("T", "P", p0 + dp, inp, x0, name)
            - cp.PropsSI("T", "P", p0 - dp, inp, x0, name)
        ) / (2.0 * dp)
        worst = 0.0
        draws = [(k * EPS, 0.0) for k in range(-K_ULP, K_ULP + 1) if k]
        draws += [(rng.uniform(-1e-12, 1e-12), rng.uniform(-1e-12, 1e-12)) for _ in range(N_RANDOM)]
        for a, b in draws:
            x, p = x0 * (1.0 + a), p0 * (1.0 + b)
            t = cp.PropsSI("T", "P", p, inp, x, name)
            worst = max(worst, abs(t - (t0 + (x - x0) * dtdx + (p - p0) * dtdp)) / t0)
        label = f"{name} {inp[0]} P={p0:.6g} T0={t0:.6f} ({answer['regime']})"
        print(f"  {label:52s} worst |dT|/T = {worst:.3e}")
        if worst > overall[0]:
            overall = (worst, label)
    # TH-C1's pump outlet, as the generator computes it.
    water = gen._Fluid(cp, "H2O")
    h1 = water("Hmolar", "T", 318.15, "P", 1.0e4)
    s1 = water("Smolar", "T", 318.15, "P", 1.0e4)
    h2 = h1 + (water("Hmolar", "P", 3.0e6, "Smolar", s1) - h1) / 0.75
    t2 = water("T", "P", 3.0e6, "Hmolar", h2)
    cp2 = water("Cpmolar", "T", t2, "P", 3.0e6)
    scan = max(
        abs(water("T", "P", 3.0e6, "Hmolar", h2 * (1.0 + k * EPS)) - t2)
        for k in range(-64, 65)
        if k
    )
    bound = 1e-10 * t2
    input_noise = 1.536e-9 / cp2
    print(
        f"TH-C1 pump outlet: T = {t2:.10f} K, c_p = {cp2:.4f} J/(mol K); ulp scan |k| <= 64: "
        f"max |dT| = {scan:.4e} K = {scan / bound:.4f} x 1e-10·T; the energy class's aarch64 "
        f"worst 1.536e-9 J/mol / c_p = {input_noise:.2e} K = {input_noise / bound:.1e} x 1e-10·T"
    )
    print(
        f"m1: {rows} single-phase flashes, {2 * K_ULP} ulp + {N_RANDOM} random draws each; "
        f"worst |dT|/T = {overall[0]:.3e} at {overall[1]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
