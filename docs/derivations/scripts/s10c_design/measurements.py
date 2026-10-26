"""S10-C design evidence (`docs/derivations/S10C-design.md` §2.4): the measurements it rests on.

Not production code and not a reference generator. It reads `wilson-ig-v1`'s closed forms from the
provider module's private helpers (`_pure`, `_ln_gamma`) so that every number is the provider's
own arithmetic, and prints `measured.txt` (run from the repository root with `PYTHONPATH=src:.`):

1. positivity on each record set's T domain: Δh_i, c_p,i^0L, c_p,i^ig, d ln P_i^sat/dT;
2. the constant-β point (§4.3) by composition successive substitution with an exact T solve per
   step: iterations, the last-step contraction rate and the last step, at binary, ternary,
   near-pure and near-azeotrope feeds, β ∈ {0, 0.1, 0.5, 0.9, 1};
3. the same at the 13 E-2 states of `tests/test_s10_flash.py::NEAR_AZEOTROPE` (verification
   records), β ∈ {0, 0.25, 0.5, 0.75, 1}, with the band width and whether the state's T lies in it;
4. S02 §18.2's bubble-point sweeps with K at the previous sweep's composition, relaxed by ω, on the
   registered C-MW and C-EW definitions (S10 spec §10), ω ∈ {1, 0.7, 0.5, 0.3};
5. the C-MW and C-EW MESH roots (scipy `hybr`, total condenser, 19 equilibrium stages, reflux ratio
   and distillate rate held): the profile, min |K_i − 1| per stage, and the model azeotrope.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence

import numpy as np
from scipy.optimize import root

from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider, WilsonRecords, _ln_gamma, _pure

P_ATM = 101325.0


class Model:
    """K_i(T, P, x) = γ_i(x) P_i^sat(T)/P and the pure enthalpies, from one record set."""

    def __init__(self, records: WilsonRecords, pressure: float = P_ATM) -> None:
        self.records = records
        self.lam = records.wilson_lambda
        self.pressure = pressure
        self.t_lo, self.t_hi = records.temperature_domain

    def ln_k(self, t: float, x: Sequence[float]) -> list[float]:
        total = sum(x)
        comp = [v / total for v in x]
        pure = _pure(self.records, t)
        ln_gamma, _ = _ln_gamma(self.lam, comp)
        ln_p = math.log(self.pressure)
        return [g + s - ln_p for g, s in zip(ln_gamma, pure.ln_psat, strict=True)]

    def rr(self, t: float, z: Sequence[float], beta: float, x: Sequence[float]) -> float:
        k = self.ln_k(t, x)
        return sum(
            zi * (math.exp(ki) - 1.0) / (1.0 + beta * (math.exp(ki) - 1.0))
            for zi, ki in zip(z, k, strict=True)
            if zi > 0.0
        )

    def t_solve(self, z: Sequence[float], beta: float, x: Sequence[float]) -> float:
        """Bisection to adjacent doubles of the frozen-x Rachford–Rice form (increasing in T)."""
        lo, hi = self.t_lo, self.t_hi
        if self.rr(lo, z, beta, x) > 0.0 or self.rr(hi, z, beta, x) < 0.0:
            raise ValueError("T(beta) outside the domain")
        while True:
            mid = 0.5 * (lo + hi)
            if mid in (lo, hi):
                return lo
            if self.rr(mid, z, beta, x) > 0.0:
                hi = mid
            else:
                lo = mid

    def point(
        self, z: Sequence[float], beta: float, cap: int = 1000, delta: float = 1e-13
    ) -> tuple[float, list[float], int, list[float]]:
        """§4.3: x⁰ = z; T from the frozen-x RR; x = z/(1 + β(K − 1)) normalised; stop on the
        largest change of ln K at the new x (S10 §5.4 step 4(c)'s form) ≤ delta."""
        x = list(z)
        steps: list[float] = []
        t = self.t_lo
        for m in range(1, cap + 1):
            t = self.t_solve(z, beta, x)
            k = self.ln_k(t, x)
            raw = [
                zi / (1.0 + beta * (math.exp(ki) - 1.0)) if zi > 0.0 else 0.0
                for zi, ki in zip(z, k, strict=True)
            ]
            x = [v / sum(raw) for v in raw]
            k_new = self.ln_k(t, x)
            steps.append(max(abs(a - b) for a, b, zi in zip(k_new, k, z, strict=True) if zi > 0.0))
            if steps[-1] <= delta:
                return t, x, m, steps
        return t, x, -1, steps

    def bubble(self, flows: Sequence[float]) -> float:
        return self.t_solve(flows, 0.0, flows)


def rate(steps: Sequence[float]) -> float:
    ratios = [steps[i + 1] / steps[i] for i in range(len(steps) - 1) if steps[i] > 1e-11]
    return max(ratios[-3:]) if ratios else 0.0


def positivity(provider: WilsonIdealGasProvider) -> str:
    rec = provider.records
    lo, hi = rec.temperature_domain
    mins = [math.inf] * 4
    for k in range(1001):
        pure = _pure(rec, lo + (hi - lo) * k / 1000)
        latent = [a - b for a, b in zip(pure.h_ig, pure.h_liquid, strict=True)]
        values = (min(latent), min(pure.cp_liquid), min(pure.cp_ig), min(pure.dln_psat_dt))
        mins = [min(a, b) for a, b in zip(mins, values, strict=True)]
    return (
        f"{rec.reference_convention} T in [{lo}, {hi}] K (1001-point grid): min dh_vap "
        f"{mins[0]:.1f} J/mol, min cp_L {mins[1]:.2f}, min cp_ig {mins[2]:.2f} J/(mol K), "
        f"min dlnPsat/dT {mins[3]:.4f} 1/K"
    )


def thomas(sub: list[float], diag: list[float], sup: list[float], rhs: list[float]) -> list[float]:
    size = len(diag)
    cp, dp = [0.0] * size, [0.0] * size
    cp[0], dp[0] = sup[0] / diag[0], rhs[0] / diag[0]
    for i in range(1, size):
        m = diag[i] - sub[i] * cp[i - 1]
        cp[i] = sup[i] / m if i < size - 1 else 0.0
        dp[i] = (rhs[i] - sub[i] * dp[i - 1]) / m
    out = [0.0] * size
    out[-1] = dp[-1]
    for i in range(size - 2, -1, -1):
        out[i] = dp[i] - cp[i] * out[i + 1]
    return out


def sweeps(
    model: Model, z: list[float], reflux: float, omega: float, count: int = 20, feed: int = 10
) -> tuple[int, float, float]:
    """S02 §18.2 with CMO stage ratios (V/L = 1 above the feed, 1/2 below; φ = RR/(1 + RR)),
    K_ij at (T_j, x̄_j), x̄ ← ω x + (1 − ω) x̄; stop on max|ΔT| ≤ 1e-9 K and max|x − x̄| ≤ 1e-12."""
    stages = list(range(2, count + 1))
    t_a = model.point(z, 0.1)[0]
    t_b = model.point(z, 0.9)[0]
    temps = {j: t_a + (t_b - t_a) * (j - 1) / (count - 1) for j in stages}
    rho = {j: (1.0 if j < feed else 0.5) for j in stages}
    phi = reflux / (1.0 + reflux)

    def flows(xs: dict[int, list[float]]) -> dict[int, list[float]]:
        liq = {j: [0.0] * 3 for j in stages}
        for i in range(3):
            if z[i] == 0.0:
                continue
            s = {j: math.exp(model.ln_k(temps[j], xs[j])[i]) * rho[j] for j in stages}
            diag = [-(1.0 + s[j]) for j in stages]
            diag[0] += phi * s[stages[0]]
            sol = thomas(
                [1.0] * len(stages),
                diag,
                [s[j + 1] if j < count else 0.0 for j in stages],
                [-(z[i] if j == feed else 0.0) for j in stages],
            )
            for k, j in enumerate(stages):
                liq[j][i] = sol[k]
        return liq

    def normed(liq: dict[int, list[float]]) -> dict[int, list[float]]:
        return {j: [v / sum(liq[j]) for v in liq[j]] for j in stages}

    xbar = normed(flows({j: list(z) for j in stages}))
    d_t = d_x = math.inf
    for sweep in range(1, 2001):
        liq = flows(xbar)
        new_t = {j: model.bubble(liq[j]) for j in stages}
        xs = normed(liq)
        d_x = max(abs(xs[j][i] - xbar[j][i]) for j in stages for i in range(3))
        xbar = {
            j: [omega * xs[j][i] + (1.0 - omega) * xbar[j][i] for i in range(3)] for j in stages
        }
        d_t = max(abs(new_t[j] - temps[j]) for j in stages)
        temps = new_t
        if d_t <= 1e-9 and d_x <= 1e-12:
            return sweep, d_t, d_x
    return -1, d_t, d_x


def mesh(model: Model, light: int, z_light: float, distillate: float, reflux: float) -> list[str]:
    """MESH of a total condenser over stages 2..20 (feed saturated liquid on 10, F = 1 mol/s)."""
    count, feed_stage, ns = 20, 10, 19
    z = [z_light, 1.0 - z_light]

    def tern(xb: Sequence[float]) -> list[float]:
        x = [0.0, 0.0, 0.0]
        x[light], x[2] = xb[0], xb[1]
        return x

    def kb(t: float, xb: Sequence[float]) -> np.ndarray:
        k = model.ln_k(t, tern(xb))
        return np.exp([k[light], k[2]])

    def hb(t: float, liquid: bool) -> np.ndarray:
        pure = _pure(model.records, t)
        h = pure.h_liquid if liquid else pure.h_ig
        return np.array([h[light], h[2]])

    t_feed = model.bubble(tern(z))
    h_feed = float(np.dot(z, hb(t_feed, True)))
    v_top = (reflux + 1.0) * distillate

    def residual(u: np.ndarray) -> np.ndarray:
        liq, vap = u[: 2 * ns].reshape(ns, 2), u[2 * ns : 4 * ns].reshape(ns, 2)
        temps, t_c = u[4 * ns : 5 * ns], u[5 * ns]
        xc = vap[0] / vap[0].sum()
        out = [float(np.dot(xc, kb(t_c, xc))) - 1.0]
        refl = reflux / (reflux + 1.0) * vap[0]
        for s in range(ns):
            j = s + 2
            above = refl if s == 0 else liq[s - 1]
            below = vap[s + 1] if s < ns - 1 else np.zeros(2)
            fin = np.array(z) if j == feed_stage else np.zeros(2)
            out += list(above + below + fin - liq[s] - vap[s])
            big_l, big_v = liq[s].sum(), vap[s].sum()
            out += list(vap[s] * big_l - kb(temps[s], liq[s] / big_l) * liq[s] * big_v)
            t_above = t_c if s == 0 else temps[s - 1]
            energy = (
                float(np.dot(above, hb(t_above, True)))
                + (float(np.dot(below, hb(temps[s + 1], False))) if s < ns - 1 else 0.0)
                + (h_feed if j == feed_stage else 0.0)
                - float(np.dot(liq[s], hb(temps[s], True)))
                - float(np.dot(vap[s], hb(temps[s], False)))
            )
            out.append(vap[0].sum() - v_top if s == ns - 1 else energy / 1e4)
        return np.array(out)

    temps0 = np.linspace(model.bubble(tern([0.95, 0.05])), model.bubble(tern([0.01, 0.99])), ns)
    xs0 = np.linspace(0.9, 0.01, ns)
    liq0, vap0 = [], []
    for s in range(ns):
        j = s + 2
        big_l = reflux * distillate if j < feed_stage else reflux * distillate + 1.0
        big_l = 1.0 - distillate if j == count else big_l
        x = np.array([xs0[s], 1.0 - xs0[s]])
        y = x * kb(temps0[s], x)
        liq0.append(big_l * x)
        vap0.append(v_top * y / y.sum())
    u0 = np.concatenate([np.ravel(liq0), np.ravel(vap0), temps0, [temps0[0] - 1.0]])
    sol = root(residual, u0, method="hybr", options={"xtol": 1e-13, "maxfev": 200000})
    liq, vap = sol.x[: 2 * ns].reshape(ns, 2), sol.x[2 * ns : 4 * ns].reshape(ns, 2)
    temps = sol.x[4 * ns : 5 * ns]
    lines = [
        f"  converged {sol.success}, max|residual| {np.max(np.abs(sol.fun)):.2e}, "
        f"T_condenser {sol.x[5 * ns]:.4f} K, x_D {vap[0][0] / vap[0].sum():.6f}"
    ]
    for s in range(ns):
        x, y = liq[s] / liq[s].sum(), vap[s] / vap[s].sum()
        k = kb(temps[s], x)
        lines.append(
            f"  stage {s + 2:2d} T {temps[s]:.4f} x {x[0]:.6f} y {y[0]:.6f} "
            f"min|K-1| {min(abs(k - 1.0)):.3g}"
        )
    return lines


def azeotrope(model: Model, light: int) -> tuple[float, float]:
    """The bubble composition where K_light = K_water, by bisection on x_light in (0.5, 1)."""

    def gap(xa: float) -> tuple[float, float]:
        x = [0.0, 0.0, 0.0]
        x[light], x[2] = xa, 1.0 - xa
        t = model.bubble(x)
        k = model.ln_k(t, x)
        return k[light] - k[2], t

    lo, hi = 0.5, 0.9999
    g_lo = gap(lo)[0]
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        g_mid = gap(mid)[0]
        if (g_mid > 0.0) == (g_lo > 0.0):
            lo, g_lo = mid, g_mid
        else:
            hi = mid
    return 0.5 * (lo + hi), gap(0.5 * (lo + hi))[1]


def main() -> int:
    sys.path.insert(0, "tests")
    from test_s10_flash import NEAR_AZEOTROPE

    real = WilsonIdealGasProvider()
    verification = WilsonIdealGasProvider("benchmarks/s10/verification-records.yaml")
    print("1. positivity")
    for provider in (real, verification):
        print("  " + positivity(provider))

    print("2. constant-beta point, real records, P = 101325 Pa")
    model = Model(real.records)
    az_e = azeotrope(model, 1)
    feeds = [[0.0, ze, 1.0 - ze] for ze in (0.2, 0.5, 0.8, az_e[0] - 1e-4, az_e[0] + 1e-4)]
    feeds += [[zm, 0.0, 1.0 - zm] for zm in (0.4, 0.994, 0.0039, 1.0 - 1e-10, 1e-10)]
    feeds += [[0.3, 0.2, 0.5]]
    worst = (0, 0.0)
    for z in feeds:
        for beta in (0.0, 0.1, 0.5, 0.9, 1.0):
            t, _, m, steps = model.point(z, beta)
            worst = (max(worst[0], m), max(worst[1], rate(steps)))
            print(
                f"  z {[f'{v:.6g}' for v in z]} beta {beta:.1f} T {t:.9f} iterations {m} "
                f"rate {rate(steps):.3f} last {steps[-1]:.2e}"
            )
    print(f"  worst: iterations {worst[0]}, rate {worst[1]:.3f}")

    print("3. constant-beta point at the 13 E-2 states (verification records)")
    vmodel = Model(verification.records)
    worst = (0, 0.0)
    for (nb, nc), t_state in NEAR_AZEOTROPE:
        z = [0.0, nb / (nb + nc), nc / (nb + nc)]
        ends = []
        for beta in (0.0, 0.25, 0.5, 0.75, 1.0):
            t, _, m, steps = vmodel.point(z, beta)
            ends.append(t)
            worst = (max(worst[0], m), max(worst[1], rate(steps)))
        print(
            f"  T_b {ends[0]:.12f} T_d {ends[-1]:.12f} width {ends[-1] - ends[0]:.2e} "
            f"state inside {ends[0] <= t_state <= ends[-1]}"
        )
    print(f"  worst: iterations {worst[0]}, rate {worst[1]:.3f}")

    print("4. bubble-point sweeps with K(T, x_bar), x_bar relaxed by omega")
    for z, reflux in (([0.4, 0.0, 0.6], 1.5), ([0.0, 0.2, 0.8], 3.0)):
        for omega in (1.0, 0.7, 0.5, 0.3):
            count, d_t, d_x = sweeps(model, z, reflux, omega)
            print(f"  z {z} omega {omega} sweeps {count} last dT {d_t:.2e} last dx {d_x:.2e}")

    print("5. MESH roots of the registered definitions")
    print("  C-MW (methanol-water, z 0.4, D 0.4, RR 1.5)")
    print("\n".join(mesh(model, 0, 0.4, 0.4, 1.5)))
    print("  C-EW (ethanol-water, z 0.2, D 0.18, RR 3)")
    print("\n".join(mesh(model, 1, 0.2, 0.18, 3.0)))
    print(f"  ethanol-water azeotrope at 101325 Pa: x_E {az_e[0]:.6f}, T {az_e[1]:.4f} K")
    return 0


if __name__ == "__main__":
    sys.exit(main())
