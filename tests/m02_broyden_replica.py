"""An independent replica of the coupling iteration (M02 design note §4.3 as amended by §14.5 D5,
register R-305), for G8 (f)'s expectations. It does not import the driver
(`openflowsheet.orchestrator.coupling`): it is written from the clause, for one unit whose inner
solve always converges and whose experiment always answers, so it has no backtracks.

    u = D w, D = diag(1/s_X, 1/s_dT); B₀ = −I; r̂ = D r, r = F(w) − w;
    ρ = max(|r_X| n_N2,in / (τ_ξ n_tot,in), |r_T| / τ_T); converged iff ρ ≤ 1;
    on ρ_k > ρ_best: at k ≥ 2n (n = 2), B = −I and a substitution step from the best (a second
    reset in a row ends `no_decrease`); at k < 2n, B is updated and the best does not move;
    otherwise Broyden's good update from the base and best = k; the step clipped to the bounds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

Pair = tuple[float, float]


@dataclass
class Iterate:
    k: int
    w: Pair
    rho: float
    #: The step taken from this iterate: "broyden", "reset", or "none" at the end.
    kind: str = "none"
    #: Whether that step was clipped to the bounds.
    clipped: bool = False


@dataclass
class Replica:
    iterates: list[Iterate] = field(default_factory=list)
    end: str = ""


def _solve(b: list[list[float]], rhs: Pair) -> Pair:
    """b x = rhs for a 2 x 2 b, by Cramer's rule."""
    det = b[0][0] * b[1][1] - b[0][1] * b[1][0]
    return (
        (rhs[0] * b[1][1] - b[0][1] * rhs[1]) / det,
        (b[0][0] * rhs[1] - rhs[0] * b[1][0]) / det,
    )


def replicate(
    f: Callable[[Pair], Pair],
    w0: Pair,
    *,
    scale: Pair = (0.1, 10.0),
    lower: Pair = (0.0, -50.0),
    upper: Pair = (0.95, 250.0),
    tau_xi: float = 1e-5,
    tau_t: float = 1e-2,
    n_n2: float = 1.0,
    n_tot: float = 4.35,
    max_outer: int = 15,
) -> Replica:
    window = 2 * 2  # 2n, n = 2 for one unit
    out = Replica()
    u = (w0[0] / scale[0], w0[1] / scale[1])
    b = [[-1.0, 0.0], [0.0, -1.0]]
    best: tuple[Pair, Pair, float] | None = None  # (u, r̂, ρ)
    base: tuple[Pair, Pair] | None = None  # (u, r̂) the step was taken from
    reset_last = False
    for k in range(max_outer):
        w = (u[0] * scale[0], u[1] * scale[1])
        fx, ft = f(w)
        r = (fx - w[0], ft - w[1])
        r_hat = (r[0] / scale[0], r[1] / scale[1])
        rho = max(abs(r[0]) * n_n2 / (tau_xi * n_tot), abs(r[1]) / tau_t)
        here = Iterate(k, w, rho)
        out.iterates.append(here)
        if rho <= 1.0:
            out.end = "converged"
            return out
        if k == max_outer - 1:
            out.end = "max_outer"
            return out
        rose = best is not None and rho > best[2]
        if rose and k >= window:
            if reset_last:
                out.end = "no_decrease"
                return out
            assert best is not None
            b = [[-1.0, 0.0], [0.0, -1.0]]
            origin, origin_r = best[0], best[1]
            here.kind, reset_last = "reset", True
        else:
            if base is not None:
                du = (u[0] - base[0][0], u[1] - base[0][1])
                dr = (r_hat[0] - base[1][0], r_hat[1] - base[1][1])
                bdu = (b[0][0] * du[0] + b[0][1] * du[1], b[1][0] * du[0] + b[1][1] * du[1])
                den = du[0] * du[0] + du[1] * du[1]
                b = [[b[i][j] + (dr[i] - bdu[i]) * du[j] / den for j in range(2)] for i in range(2)]
            if not rose:
                best = (u, r_hat, rho)
            origin, origin_r = u, r_hat
            here.kind, reset_last = "broyden", False
        step = _solve(b, (-origin_r[0], -origin_r[1]))
        trial = (origin[0] + step[0], origin[1] + step[1])
        lo = (lower[0] / scale[0], lower[1] / scale[1])
        hi = (upper[0] / scale[0], upper[1] / scale[1])
        u = (min(max(trial[0], lo[0]), hi[0]), min(max(trial[1], lo[1]), hi[1]))
        here.clipped = u != trial
        base = (origin, origin_r)
    raise AssertionError("unreachable: max_outer ends the loop")
