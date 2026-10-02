"""Fable's closed-form reference generator for the T02 recycle, EO and cross-unit specification.

Everything here follows from definitions: the manufactured recycle maps of
``docs/briefs/T02-oscillatory-recycle-cases.md`` (fixed point and Jacobian exact by construction),
the SYN-001 thermodynamics of ``docs/derivations/SYN-001.md`` (through the sibling generators
``syn001_reference.py`` and ``k03_reference.py``, both closed-form mpmath scripts), the process
topology of plan §3.2, and the recycle policy of ``docs/derivations/T02-recycle-spec.md`` §5,
which is *simulated here at 40 significant digits from its own statement* so that the trajectory
a correct implementation must reproduce is derived a second time, independently of the solver.
It imports nothing from ``process_runtime`` or ``benchmarks``: the numbers it emits are the
*expectations* the T02 tests judge the implementation against, so they must not come from it.

Three classes of value are emitted and labelled as such in the YAML:

* ``closed_form`` — fixed points, spectra, best damping factors, transient-growth ratios,
  Krylov grades, duties along the A02 sweep, the phase-flip position on the SYN-001 ray. These
  are the expectations proper.
* ``policy_simulation`` — the trajectory of the registered policy (Anderson depth 5, the
  safeguards of §5) evaluated in 40-digit arithmetic. An implementation of the same policy must
  agree with it to the registered tolerance; a different policy will not. This is a
  definition-level reference, as T01's canonical matching was, not a closed form.
* ``measured`` — prototype observations from 2026-09-24 (double-precision floors, iteration
  counts on the real SYN-001 traversal and on a plain EO Newton), labelled, used only to argue
  tolerances and bounds, never an expectation.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/t02_reference.py --check
    python docs/derivations/scripts/t02_reference.py --emit benchmarks/t02/reference_values.yaml

``--check`` re-derives every identity the specification claims about its own numbers and refuses
to emit when one stops holding (T02-recycle-spec §16.2). ``--emit`` is byte-reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from mpmath import cos, matrix, mp, mpf, nstr, pi, qr_solve, sin, sqrt, svd_r

sys.path.insert(0, str(Path(__file__).resolve().parent))
import k03_reference as k03  # noqa: E402  (closed-form SYN-001 tear, mpmath)
import syn001_reference as p01  # noqa: E402  (closed-form SYN-001 thermodynamics, mpmath)

mp.dps = 40

Vec = tuple[Any, ...]

# --------------------------------------------------------------------------------------------
# 1. The registered recycle policy (T02-recycle-spec §5), as constants
# --------------------------------------------------------------------------------------------

POLICY: dict[str, Any] = {
    "policy_id": "T02-recycle-policy-v1",
    "method_default": "auto",
    "depth_max": 5,
    "beta": "1",
    "beta_substitution": "1",
    "beta_substitution_oscillating": "0.5",
    "condition_max": "1e8",
    "coefficient_max": "1e4",
    "stagnation_window": 5,
    "stagnation_ratio": "0.99",
    "oscillation_window": 3,
    "max_restarts": 2,
    "max_iterations_per_attempt": 200,
    "step_halvings_max": 20,
    "tear_tolerance_mol_per_s": "3.1e-8",
    "tear_scale_mol_per_s": "3",
}

DEPTH_MAX = 5
BETA = mpf(1)
BETA_SUB = mpf(1)
BETA_SUB_OSC = mpf("0.5")
KAPPA_MAX = mpf("1e8")
GAMMA_MAX = mpf("1e4")
STAG_WINDOW = 5
STAG_RATIO = mpf("0.99")
OSC_WINDOW = 3
MAX_RESTARTS = 2
MAX_ITER = 200
STEP_HALVINGS = 20
TEAR_TOL = mpf("1e-9") + mpf("1e-8") * mpf(3)  # ADR 0001 D6 component-balance rule at S = 3
S3 = mpf(3)

# --------------------------------------------------------------------------------------------
# 2. The manufactured maps (brief T02-oscillatory-recycle-cases.md)
# --------------------------------------------------------------------------------------------

T_STAR: Vec = (mpf(1), mpf(2), mpf(3))


def rotation_120() -> matrix:
    th = 2 * pi / 3
    return matrix([[cos(th), -sin(th), 0], [sin(th), cos(th), 0], [0, 0, 1]])


def diag(*values: str) -> matrix:
    m = matrix(3, 3)
    for i, v in enumerate(values):
        m[i, i] = mpf(v)
    return m


A_REC04 = mpf("0.95") * rotation_120()
A_REC04[2, 2] = mpf("0.3")

REC_MAPS: dict[str, dict[str, Any]] = {
    "REC-01": {
        "A": diag("-0.9", "0.5", "0.2"),
        "start_factor": "0.5",
        "title": "oscillating: real spectrum, dominant negative eigenvalue",
    },
    "REC-02": {
        "A": diag("-1.5", "0.5", "0.2"),
        "start_factor": "0.5",
        "title": "divergent oscillation: rho = 1.5, second substitution iterate negative",
    },
    "REC-03": {
        "A": diag("0.95", "-0.95", "0.3"),
        "start_factor": "0.5",
        "title": "mixed sign: +-0.95, no damping factor helps",
    },
    "REC-04": {
        "A": A_REC04,
        "start_factor": "0.5",
        "title": "spiral: complex pair 0.95 e^{+-2 pi i/3}, sign alternation does not see it",
    },
    "REC-05": {
        "A": matrix([[mpf("0.5"), mpf("2.5"), 0], [0, mpf("0.5"), mpf("2.5")], [0, 0, mpf("0.5")]]),
        "start_factor": "1.1",
        "title": "non-normal: all eigenvalues 0.5, ||A||_2 = 2.80, transient growth 8.70",
    },
}


def q_tail(d: Sequence[Any]) -> Vec:
    return (d[1] * d[2], d[2] * d[0], d[0] * d[1])


def manufactured_map(amat: matrix, gamma: Any, t_star: Vec = T_STAR) -> Callable[[Vec], Vec]:
    """G(t) = t* + A (t - t*) + gamma q(t - t*) / S."""

    def g_map(t: Vec) -> Vec:
        d = [t[i] - t_star[i] for i in range(3)]
        lin = amat * matrix(d)
        tail = q_tail(d)
        return tuple(t_star[i] + lin[i] + gamma * tail[i] / S3 for i in range(3))

    return g_map


def manufactured_jacobian(amat: matrix, gamma: Any, t: Vec, t_star: Vec = T_STAR) -> matrix:
    d = [t[i] - t_star[i] for i in range(3)]
    jac = matrix(amat)
    # d q / d d = [[0, d3, d2], [d3, 0, d1], [d2, d1, 0]]
    dq = matrix([[0, d[2], d[1]], [d[2], 0, d[0]], [d[1], d[0], 0]])
    return jac + gamma * dq / S3


def eigen_real_diag(amat: matrix) -> list[Any] | None:
    """Eigenvalues when A is diagonal (the REC-01..03 cases); None otherwise."""
    for i in range(3):
        for j in range(3):
            if i != j and amat[i, j] != 0:
                return None
    return [amat[i, i] for i in range(3)]


def best_damping(lambda_min: Any, lambda_max: Any) -> tuple[Any, Any]:
    """omega* = 2 / (2 - l_min - l_max), rate = (l_max - l_min) / (2 - l_min - l_max)."""
    den = 2 - lambda_min - lambda_max
    return 2 / den, (lambda_max - lambda_min) / den


def norm2(v: Sequence[Any]) -> Any:
    return sqrt(sum(x * x for x in v))


def norm_inf(v: Sequence[Any]) -> Any:
    return max(abs(x) for x in v)


def matpow_apply(amat: matrix, v: Sequence[Any], k: int) -> Vec:
    out = matrix(list(v))
    for _ in range(k):
        out = amat * out
    return tuple(out[i] for i in range(len(v)))


def krylov_grade(amat: matrix, r0: Sequence[Any], tol: Any = None) -> int:
    tol = mpf("1e-30") if tol is None else tol
    """Dimension of span{r0, A r0, A^2 r0, ...}: the GMRES termination index for (I - A)."""
    vecs: list[matrix] = []
    v = matrix(list(r0))
    for k in range(len(r0) + 1):
        # Gram-Schmidt against the basis so far
        w = matrix(v)
        for b in vecs:
            w = w - (b.T * w)[0] * b
        nw = sqrt((w.T * w)[0])
        if nw <= tol:
            return k
        vecs.append(w / nw)
        v = amat * v
    return len(r0)


# --------------------------------------------------------------------------------------------
# 3. The registered policy, simulated from its statement (T02-recycle-spec §5)
# --------------------------------------------------------------------------------------------


@dataclass
class Run:
    outcome: str
    iterations: int
    x: Vec
    residual_inf_scaled: list[Any] = field(default_factory=list)
    events: dict[str, Any] = field(default_factory=dict)
    trajectory_x: list[Vec] = field(default_factory=list)


def least_squares(cols: list[Vec], rhs: Vec) -> tuple[Vec, Any]:
    """gamma = argmin ||rhs - [cols] gamma||_2 and kappa_2 of the column matrix (SVD)."""
    n = len(rhs)
    m = len(cols)
    mmat = matrix(n, m)
    for j, c in enumerate(cols):
        for i in range(n):
            mmat[i, j] = c[i]
    sv = svd_r(mmat, compute_uv=False)
    smin = min(sv)
    smax = max(sv)
    kappa = mpf("inf") if smin == 0 else smax / smin
    if smin == 0:
        return tuple(), kappa
    g, _ = qr_solve(mmat, matrix(list(rhs)))
    return tuple(g[j] for j in range(m)), kappa


def accelerate(
    g_map: Callable[[Vec], Vec | None],
    t0: Vec,
    *,
    scale: Sequence[Any],
    tolerance: Sequence[Any],
    depth: int = DEPTH_MAX,
    lower_bounds: Sequence[Any] | None = None,
    max_iterations: int = MAX_ITER,
) -> Run:
    """The T02 recycle policy on a map G (returns None for an invalid state), 40 digits.

    Coordinates are scaled by `scale` (x_hat = t / S, f_hat = R / S with R = G(t) - t); bounds are
    handled by K03 §5.3's bound-aware alpha with exact landing; every safeguard of §5 is applied
    exactly as registered and every event is counted.
    """
    n = len(t0)
    svec = [mpf(s) for s in scale]
    lo = [mpf("-inf")] * n if lower_bounds is None else [mpf(b) for b in lower_bounds]
    tol_hat = [mpf(tolerance[i]) / svec[i] for i in range(n)]
    x = tuple(mpf(v) for v in t0)
    xs: list[Vec] = []
    fs: list[Vec] = []
    ev: dict[str, Any] = {
        "column_dropped_condition": 0,
        "column_dropped_coefficient": 0,
        "restarts": 0,
        "stagnation_closures": [],
        "oscillation_detected_at": None,
        "bound_landings": 0,
        "invalid_trials": 0,
        "plain_steps": 0,
        "anderson_steps": 0,
        "max_kappa": mpf(0),
        "max_gamma_inf": mpf(0),
        "residual_increases": 0,
    }
    res_hist: list[Any] = []
    traj: list[Vec] = []
    beta_sub = BETA_SUB
    stag_count = 0
    flip_count = 0
    prev_f: Vec | None = None
    f0_norm: Any = None
    k = 0
    while True:
        g = g_map(x)
        if g is None:
            return Run("EVALUATION_ERROR", k, x, res_hist, ev, traj)
        f_hat = tuple((g[i] - x[i]) / svec[i] for i in range(n))
        fnorm = norm_inf(f_hat)
        res_hist.append(fnorm)
        traj.append(x)
        if f0_norm is None:
            f0_norm = fnorm
        # §5.2 convergence, tested before anything else
        if all(abs(f_hat[i]) <= tol_hat[i] for i in range(n)):
            return Run("CONVERGED", k, x, res_hist, ev, traj)
        # §5.6 stagnation on accepted iterates
        if k > 0:
            if res_hist[-1] > res_hist[-2]:
                ev["residual_increases"] += 1
            if res_hist[-1] / res_hist[-2] > STAG_RATIO:
                stag_count += 1
            else:
                stag_count = 0
            if stag_count >= STAG_WINDOW:
                ev["stagnation_closures"].append(k)
                if ev["restarts"] < MAX_RESTARTS:
                    ev["restarts"] += 1
                    xs.clear()
                    fs.clear()
                    stag_count = 0
                else:
                    return Run("RECYCLE_STAGNATION", k, x, res_hist, ev, traj)
        # §5.5 oscillation detector: dominant component flips sign OSC_WINDOW times running
        i_dom = max(range(n), key=lambda i: abs(f_hat[i]))
        if (
            prev_f is not None
            and abs(prev_f[i_dom]) > tol_hat[i_dom]
            and prev_f[i_dom] * f_hat[i_dom] < 0
        ):
            flip_count += 1
        else:
            flip_count = 0
        if flip_count >= OSC_WINDOW and ev["oscillation_detected_at"] is None:
            ev["oscillation_detected_at"] = k
            beta_sub = BETA_SUB_OSC
        prev_f = f_hat
        if k >= max_iterations:
            return Run("BUDGET_EXHAUSTED", k, x, res_hist, ev, traj)
        # §5.3 history and the filtered least squares
        xs.append(tuple(x[i] / svec[i] for i in range(n)))
        fs.append(f_hat)
        # §5.3: the effective depth never exceeds the tear dimension. Beyond n columns the
        # difference matrix is rank-deficient in exact arithmetic and the least-squares
        # coefficient is not unique, so two correct implementations could differ; n columns is
        # the Krylov dimension and everything a linear map can use.
        m_k = min(depth, len(fs) - 1, n)
        x_new_hat: Vec | None = None
        while m_k >= 1:
            d_f = [tuple(fs[-j][i] - fs[-j - 1][i] for i in range(n)) for j in range(1, m_k + 1)]
            d_x = [tuple(xs[-j][i] - xs[-j - 1][i] for i in range(n)) for j in range(1, m_k + 1)]
            gamma, kappa = least_squares(d_f, f_hat)
            if kappa > KAPPA_MAX:
                ev["column_dropped_condition"] += 1
                m_k -= 1
                continue
            if norm_inf(gamma) > GAMMA_MAX:
                ev["column_dropped_coefficient"] += 1
                m_k -= 1
                continue
            ev["max_kappa"] = max(ev["max_kappa"], kappa)
            ev["max_gamma_inf"] = max(ev["max_gamma_inf"], norm_inf(gamma))
            x_new_hat = tuple(
                xs[-1][i]
                + BETA * f_hat[i]
                - sum((d_x[j][i] + BETA * d_f[j][i]) * gamma[j] for j in range(m_k))
                for i in range(n)
            )
            ev["anderson_steps"] += 1
            break
        if x_new_hat is None:
            x_new_hat = tuple(xs[-1][i] + beta_sub * f_hat[i] for i in range(n))
            ev["plain_steps"] += 1
        d = tuple((x_new_hat[i] - xs[-1][i]) * svec[i] for i in range(n))
        # K03 §5.3 bound-aware alpha with exact landing
        alpha_max = mpf(1)
        for i in range(n):
            if d[i] < 0 and x[i] + d[i] < lo[i]:
                alpha_max = min(alpha_max, (lo[i] - x[i]) / d[i])
        if alpha_max == 0:
            return Run("BOUND_BLOCKED", k, x, res_hist, ev, traj)
        if alpha_max < 1:
            ev["bound_landings"] += 1
        alpha = alpha_max
        accepted: Vec | None = None
        for _ in range(STEP_HALVINGS + 1):
            trial = list(x[i] + alpha * d[i] for i in range(n))
            if alpha == alpha_max:
                for i in range(n):
                    if d[i] < 0 and x[i] + alpha_max * d[i] <= lo[i]:
                        trial[i] = lo[i]
            if g_map(tuple(trial)) is not None:
                accepted = tuple(trial)
                break
            ev["invalid_trials"] += 1
            alpha = alpha / 2
        if accepted is None:
            return Run("LINE_SEARCH_FAILED", k, x, res_hist, ev, traj)
        x = accepted
        k += 1


def bounded_map(g_map: Callable[[Vec], Vec], lower: Any = 0) -> Callable[[Vec], Vec | None]:
    """A manufactured map that refuses a negative component flow (ADR 0001 D3.5)."""

    def h_fn(t: Vec) -> Vec | None:
        if any(v < lower for v in t):
            return None
        return g_map(t)

    return h_fn


def substitution_unbounded(amat: matrix, t0: Vec, k: int, t_star: Vec = T_STAR) -> Vec:
    """t_k - t* = A^k (t0 - t*) for the linear part, no bounds: the brief's closed form."""
    d0 = [t0[i] - t_star[i] for i in range(3)]
    dk = matpow_apply(amat, d0, k)
    return tuple(t_star[i] + dk[i] for i in range(3))


# --------------------------------------------------------------------------------------------
# 4. NEST-1: a linear flowsheet whose loop no single edge breaks (T01 -> T02)
# --------------------------------------------------------------------------------------------

NEST_CONNECTIONS: tuple[tuple[str, str, str], ...] = (
    ("s0", "FEED", "A"),
    ("s1", "A", "B"),
    ("s2", "B", "C"),
    ("s3", "C", "PRODUCT"),
    ("s4", "B", "A"),
    ("s5", "C", "B"),
)
NEST_BOUNDARY = ("FEED",)
NEST_ROW_UNITS = ("A", "B", "C")  # sinks own no rows
NEST_FEED = mpf(1)
NEST_B_SPLIT = mpf("0.5")  # B sends half of its total back to A, half on to C
NEST_C_RECYCLE = mpf("0.8")  # C sends 0.8 of s2 back to B, 0.2 to the product


def nest_evaluate(s4: Any, s5: Any) -> dict[str, Any]:
    s1 = NEST_FEED + s4
    total = s1 + s5
    s4_new = NEST_B_SPLIT * total
    s2 = (1 - NEST_B_SPLIT) * total
    s5_new = NEST_C_RECYCLE * s2
    s3 = (1 - NEST_C_RECYCLE) * s2
    return {"s1": s1, "s2": s2, "s3": s3, "s4": s4_new, "s5": s5_new}


def nest_map(t: Vec) -> Vec:
    out = nest_evaluate(t[0], t[1])
    return (out["s4"], out["s5"])


def nest_alternate_map(t: Vec) -> Vec:
    """Tear set {s1, s5} instead of the rule's {s4, s5}: the alternate tearing of §13.2."""
    s1, s5 = t
    total = s1 + s5
    s4 = NEST_B_SPLIT * total
    s2 = (1 - NEST_B_SPLIT) * total
    return (NEST_FEED + s4, NEST_C_RECYCLE * s2)


def strongly_connected(
    nodes: Sequence[str], edges: Sequence[tuple[str, str, str]]
) -> list[list[str]]:
    """Tarjan, written from its definition; components in discovery order."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    out: list[list[str]] = []
    counter = [0]
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for _, a, b in edges:
        adj[a].append(b)

    def visit(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in adj[v]:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            out.append(sorted(comp, key=nodes.index))

    for v in nodes:
        if v not in index:
            visit(v)
    return out


def boundary_distances(
    nodes: Sequence[str], edges: Sequence[tuple[str, str, str]], boundary: Sequence[str]
) -> dict[str, int]:
    dist = {b: 0 for b in boundary}
    frontier = list(boundary)
    while frontier:
        nxt: list[str] = []
        for u in frontier:
            for _, a, b in edges:
                if a == u and b not in dist:
                    dist[b] = dist[u] + 1
                    nxt.append(b)
        frontier = nxt
    return dist


def nest_tear_set() -> dict[str, Any]:
    """T02 §4.3's iterated single-edge rule on the loop {A, B, C}: least dimension, then least
    consumer boundary distance, then declaration order; remove, recompute, repeat."""
    nodes = ["FEED", "A", "B", "C", "PRODUCT"]
    edges = list(NEST_CONNECTIONS)
    dist = boundary_distances(nodes, edges, NEST_BOUNDARY)
    torn: list[dict[str, Any]] = []
    remaining = list(edges)
    rounds: list[dict[str, Any]] = []
    while True:
        loops = [c for c in strongly_connected(nodes, remaining) if len(c) > 1]
        if not loops:
            break
        loop = loops[0]
        cycle_edges = [e for e in remaining if e[1] in loop and e[2] in loop]
        candidates = []
        for sid, _a, b in cycle_edges:
            trial = [e for e in remaining if e[0] != sid]
            breaks = all(
                len(c) == 1
                for c in strongly_connected(
                    loop, [e for e in trial if e[1] in loop and e[2] in loop]
                )
            )
            candidates.append(
                {
                    "stream": sid,
                    "dimension": 1,
                    "consumer_boundary_distance": dist[b],
                    "declaration_index": [e[0] for e in edges].index(sid),
                    "breaks_loop": breaks,
                }
            )
        chosen = min(
            candidates,
            key=lambda c: (c["dimension"], c["consumer_boundary_distance"], c["declaration_index"]),
        )
        rounds.append(
            {
                "loop_units": loop,
                "cycle_edges": [e[0] for e in cycle_edges],
                "candidates": candidates,
                "chosen": chosen["stream"],
            }
        )
        torn.append(chosen)
        remaining = [e for e in remaining if e[0] != chosen["stream"]]
    single_edge_breaks = any(
        all(
            len(c) == 1
            for c in strongly_connected(
                ["A", "B", "C"],
                [e for e in edges if e[0] != sid and e[1] in "ABC" and e[2] in "ABC"],
            )
        )
        for sid, a, b in edges
        if a in "ABC" and b in "ABC"
    )
    return {
        "rounds": rounds,
        "tear_streams": [t["stream"] for t in torn],
        "tear_dimension": len(torn),
        "single_edge_feedback_set_exists": single_edge_breaks,
        "boundary_distances": dist,
    }


# --------------------------------------------------------------------------------------------
# 5. SYN-001 closed forms for the EO and A02 cases
# --------------------------------------------------------------------------------------------

P_R = mpf(100000)
T_FLASH = mpf(360)
T_HEATER_NOMINAL = mpf(350)
R_NOMINAL = mpf("0.5")


def stream_enthalpy_split(n: Vec, t: Any, p: Any) -> tuple[str, Any, Any, Vec, Vec]:
    """(regime, H, beta, vapor n, liquid n) of the TP flash of n at (t, p)."""
    fl = p01.tp_flash(list(n), t, p)
    tot = sum(n)
    if fl["state"] == "LIQUID":
        return "LIQUID", p01.enthalpy_flow(list(n), t, p, "L"), mpf(0), (mpf(0),) * 3, tuple(n)
    if fl["state"] == "VAPOR":
        return "VAPOR", p01.enthalpy_flow(list(n), t, p, "V"), mpf(1), tuple(n), (mpf(0),) * 3
    beta = fl["beta"]
    vtot = beta * tot
    ltot = tot - vtot
    vap = tuple(vtot * fl["y"][i] for i in range(3))
    liq = tuple(ltot * fl["x"][i] for i in range(3))
    h_fn = p01.enthalpy_flow(list(vap), t, p, "V") + p01.enthalpy_flow(list(liq), t, p, "L")
    return "TWO_PHASE", h_fn, beta, vap, liq


def a02_closed_forms() -> dict[str, Any]:
    """The nominal loop at t* with the heater outlet temperature free: duties along a sweep."""
    t = k03.reference_recycle(R_NOMINAL, T_FLASH, P_R)
    n3 = tuple(p01.FRESH[i] + t[i] for i in range(3))
    tot = sum(n3)
    _, h_out, beta_out, vap_out, liq_out = stream_enthalpy_split(n3, T_FLASH, P_R)
    h_s2 = p01.enthalpy_flow(list(p01.FRESH), mpf(300), P_R, "L") + p01.enthalpy_flow(
        list(t), T_FLASH, P_R, "L"
    )
    q_total = h_out - h_s2
    sweep: dict[str, Any] = {}
    for t3 in (340, 350, 355, 358, 360, 365):
        regime, h3, beta, vap, liq = stream_enthalpy_split(n3, mpf(t3), P_R)
        sweep[f"T_heater={t3}K"] = {
            "regime": regime,
            "Q_heater_W": h3 - h_s2,
            "Q_flash_W": h_out - h3,
            "beta": beta,
            "S3_vapor_mol_per_s": vap,
            "S3_liquid_mol_per_s": liq,
        }

    # phase flip of S3 (350 K) along the ray n = F + s t*, and the bubble point of S3.n at t*
    def szk_ray(s: Any, temp_k: Any = T_HEATER_NOMINAL) -> Any:
        n = [p01.FRESH[i] + s * t[i] for i in range(3)]
        tt = sum(n)
        return sum(n[i] / tt * p01.k_value(i, temp_k, P_R) for i in range(3)) - 1

    s_flip = p01.bisect(szk_ray, mpf(0), mpf(1))
    t_bubble = p01.bisect(
        lambda temp_k: sum(n3[i] / tot * p01.k_value(i, temp_k, P_R) for i in range(3)) - 1,
        mpf(340),
        mpf(360),
    )
    t_dew = p01.bisect(
        lambda temp_k: sum(n3[i] / tot / p01.k_value(i, temp_k, P_R) for i in range(3)) - 1,
        mpf(360),
        mpf(400),
    )

    # liquid-branch and vapor-branch roots of FLASH-duty for a given Q_flash specification:
    # H_liq(n3, T) = cp N (T - 300) [+ v (P - P_r) = 0 at P_r]; H_vap = cp N (T - 300) + sum n_i L_i
    def liquid_branch_root(q_spec: Any) -> Any:
        return 300 + (h_out - q_spec) / (p01.CP * tot)

    def vapor_branch_root(q_spec: Any) -> Any:
        return 300 + (h_out - q_spec - sum(n3[i] * p01.L_VAP[i] for i in range(3))) / (p01.CP * tot)

    branch = {}
    for label, q_spec in (
        ("Q_flash=0", mpf(0)),
        ("Q_flash=Q(355K)", sweep["T_heater=355K"]["Q_flash_W"]),
    ):
        t_liq = liquid_branch_root(q_spec)
        t_vap = vapor_branch_root(q_spec)
        branch[label] = {
            "liquid_branch_T_K": t_liq,
            "liquid_branch_sum_zK": sum(n3[i] / tot * p01.k_value(i, t_liq, P_R) for i in range(3)),
            "vapor_branch_T_K": t_vap,
            "provider_domain_K": [280, 440],
            "sum_z_over_K_at_440K": sum(
                n3[i] / tot / p01.k_value(i, mpf(440), P_R) for i in range(3)
            ),
            "sum_zK_at_280K": sum(n3[i] / tot * p01.k_value(i, mpf(280), P_R) for i in range(3)),
        }
    high = k03.reference_recycle(mpf("0.95"), T_FLASH, P_R)

    def szk_ray_high(s: Any) -> Any:
        n = [p01.FRESH[i] + s * high[i] for i in range(3)]
        tt = sum(n)
        return sum(n[i] / tt * p01.k_value(i, T_HEATER_NOMINAL, P_R) for i in range(3)) - 1

    s_flip_high = p01.bisect(szk_ray_high, mpf(0), mpf("0.05"))
    return {
        "t_star_nominal": t,
        "S3_n_mol_per_s": n3,
        "H_S2_W": h_s2,
        "H_flash_products_W": h_out,
        "Q_total_W": q_total,
        "flash_split_at_360K": {"beta": beta_out, "vapor": vap_out, "liquid": liq_out},
        "sweep": sweep,
        "s_flip_nominal_ray": s_flip,
        "s_flip_high_recycle_ray": s_flip_high,
        "S3_bubble_point_K": t_bubble,
        "S3_dew_point_K": t_dew,
        "branch_roots": branch,
    }


# --------------------------------------------------------------------------------------------
# 6. The registered plan shapes (structural; ids from T01's declaration)
# --------------------------------------------------------------------------------------------

SYN001_UNITS_WITH_ROWS = ("U-FEED", "U-MIX", "U-HEAT", "U-FLASH", "U-SPLIT")
SYN001_LOOP = ("U-MIX", "U-HEAT", "U-FLASH", "U-SPLIT")
SYN001_CERTIFIED_ROWS = ("U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle")

PLAN_NOMINAL = [
    {"kind": "evaluate", "unit": "U-FEED"},
    {
        "kind": "converge",
        "loop": list(SYN001_LOOP),
        "tear_stream": "S6",
        "tear_variable_ids": ["S6.n.A", "S6.n.B", "S6.n.C"],
        "tear_row_ids": [
            "U-SPLIT:SPLIT-recycle:A",
            "U-SPLIT:SPLIT-recycle:B",
            "U-SPLIT:SPLIT-recycle:C",
        ],
        "method": "newton_tear",
        "signature_units": ["U-FLASH"],
    },
]
PLAN_NOMINAL_EO = [
    {"kind": "evaluate", "unit": "U-FEED"},
    {
        "kind": "solve_eo",
        "region_units": list(SYN001_LOOP),
        "specification_rows": [],
        "square": 42,
        "signature_units": ["U-HEAT", "U-FLASH"],
    },
]
PLAN_A02 = [
    {"kind": "evaluate", "unit": "U-FEED"},
    {
        "kind": "solve_eo",
        "region_units": list(SYN001_LOOP),
        "specification_rows": ["SPEC:SPEC-flash-duty"],
        "adjusted_variable": "S3.T",
        "target_variable": "U-FLASH.Q",
        "removed_specification_row": "U-HEAT:HEAT-T",
        "square": 42,
        "signature_units": ["U-HEAT", "U-FLASH"],
    },
]
PLAN_ONCE_THROUGH = [
    {"kind": "evaluate", "unit": "U-FEED"},
    {
        "kind": "converge",
        "loop": list(SYN001_LOOP),
        "tear_stream": "S6",
        "tear_variable_ids": ["S6.n.A", "S6.n.B", "S6.n.C"],
        "tear_row_ids": [
            "U-SPLIT:SPLIT-recycle:A",
            "U-SPLIT:SPLIT-recycle:B",
            "U-SPLIT:SPLIT-recycle:C",
        ],
        "method": "newton_tear",
        "signature_units": ["U-FLASH"],
        "note": "the loop is structurally present at r = 0 (T01 A02: the declared pattern does "
        "not fold); numerically the tear converges at iteration 0",
    },
]

# --------------------------------------------------------------------------------------------
# 7. Measured (prototype, 2026-09-24) — never an expectation
# --------------------------------------------------------------------------------------------

MEASURED: dict[str, Any] = {
    "note": "Prototype observations on main@fe0a4de, 2026-09-24: a double-precision Anderson of "
    "the "
    "registered policy on the manufactured maps and on the real SYN-001 traversal, and a plain "
    "bounded K03 Newton on the compiled 47-row EO system and the 42-row A02 region. Floors and "
    "counts used to argue tolerances and bounds; not expectations.",
    "linear_variants_trajectory_floor_scaled_inf": "4.4e-16 (worst |double - 40-digit| before "
    "termination, REC-01..05 gamma=0, m=5)",
    "linear_variants_terminal_residual_scaled_inf": {
        "REC-01": "3.0e-16",
        "REC-02": "0.0",
        "REC-03": "1.3e-15",
        "REC-04": "7.4e-17",
        "REC-05": "6.2e-13",
    },
    "linear_variants_iterations_double": {
        "REC-01": 4,
        "REC-02": 4,
        "REC-03": 4,
        "REC-04": 4,
        "REC-05": 4,
    },
    "tail_variants_iterations_double_gamma_0.1": {
        "REC-01": 7,
        "REC-02": 7,
        "REC-03": 9,
        "REC-04": 7,
        "REC-05": "12, to the fixed point S1",
    },
    "REC-05_basin_double": "gamma=0.1: starts 1.08..1.15 t* -> S1, 1.05 and 1.20 t* -> t*; "
    "gamma=0.05: 1.05..1.11 t* -> t*, 1.12..1.3 t* -> S2; plain substitution diverges from "
    "1.10 t* at gamma=0.1 and from 1.20 t* at gamma=0.05",
    "plain_substitution_iterations_double": {
        "REC-01": 164,
        "REC-02": "never (2-cycle on the bound without the oscillation response); 54 with it",
        "REC-03": 351,
        "REC-04": 348,
        "REC-05 gamma=0": 37,
        "REC-05 gamma=0.1": "diverges",
    },
    "syn001_anderson_iterations_double": {
        "nominal t0": 2,
        "high-recycle t0": 2,
        "310K t0": 2,
        "once-through t0": 0,
        "420K t0": 0,
        "nominal OFF-A": 9,
        "high-recycle OFF-A": 9,
        "once-through OFF-A": 1,
        "nominal OFF-B (no signature contract, 12 invalid trials)": 10,
        "high-recycle OFF-B (no signature contract, 83 invalid trials)": 13,
    },
    "syn001_eo_newton_double": {
        "nominal from x(t0), two-phase active set": "BOUND_BLOCKED at iteration 1, iterate at s = "
        "0.5467 on the ray (S3.V 4.4e-5)",
        "nominal liquid active-set restart from that iterate": "CONVERGED in 2 iterations to t*",
        "nominal liquid active set from x(t0)": "CONVERGED in 2",
        "high-recycle from x(t0)": "CONVERGED in 5 (S3 liquid at both ends)",
        "310K from x(t0)": "CONVERGED in 2",
        "once-through and 420K": "CONVERGED at iteration 0",
        "once-through forced all-liquid S3 without projection": "CONVERGED in 1 to the "
        "inadmissible trivial root (|R| 2e-16)",
    },
    "a02_eo_newton_double": {
        "Q_flash=0 from S3.T=358K": "CONVERGED in 3, S3.T = 360.0000000005",
        "Q_flash=0 from 355K": "CONVERGED in 4",
        "Q_flash=Q(365K) from 358K": "CONVERGED in 4, S3.T = 365.0000000000047",
        "Q_flash=0 from 350K, liquid active set": "STAGNATION at iteration 13 at S3.T = "
        "439.9999997 K (domain edge)",
        "then vapor active set from that state": "STAGNATION at iteration 9 at S3.T = 280.00002 K "
        "(domain edge)",
        "Q_flash=Q(355K) from 350K, liquid active set": "CONVERGED in 1 to the liquid-branch root "
        "389.438 K (inadmissible)",
    },
    "eo_region_condition": "kappa_2 of the scaled 44x44 inner block 28-1440 over the registered "
    "states (K03 §4.3)",
}


# --------------------------------------------------------------------------------------------
# 8. Build, check, emit
# --------------------------------------------------------------------------------------------


def s(x: Any, digits: int = 20) -> str:
    return p01.s(x, digits)


def vec(v: Sequence[Any]) -> list[str]:
    return [s(x) for x in v]


def mat(m: matrix) -> list[list[str]]:
    return [[s(m[i, j]) for j in range(m.cols)] for i in range(m.rows)]


def run_block(run: Run, keep: int) -> dict[str, Any]:
    ev = dict(run.events)
    ev["max_kappa"] = s(ev["max_kappa"])
    ev["max_gamma_inf"] = s(ev["max_gamma_inf"])
    return {
        "outcome": run.outcome,
        "iterations": run.iterations,
        "final_t": vec(run.x),
        "residual_inf_scaled": vec(run.residual_inf_scaled[:keep]),
        "residual_inf_scaled_recorded_through": min(keep, len(run.residual_inf_scaled)) - 1,
        "events": ev,
    }


def build() -> dict[str, Any]:
    checks: list[str] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        if not cond:
            raise AssertionError(f"self-check failed: {name} {detail}")
        checks.append(name)

    cases: dict[str, Any] = {}
    tol3 = (TEAR_TOL,) * 3
    scale3 = (S3,) * 3

    # ---- REC-01..05 ------------------------------------------------------------------------
    for cid, spec in REC_MAPS.items():
        amat = spec["A"]
        t0 = tuple(mpf(spec["start_factor"]) * v for v in T_STAR)
        eig = eigen_real_diag(amat)
        entry: dict[str, Any] = {
            "title": spec["title"],
            "A": mat(amat),
            "t_star": vec(T_STAR),
            "start": vec(t0),
            "scale_mol_per_s": "3",
            "lower_bounds": ["0", "0", "0"],
            "variants": {},
        }
        if eig is not None:
            lmin, lmax = min(eig), max(eig)
            omega, rate = best_damping(lmin, lmax)
            entry["spectrum"] = vec(eig)
            entry["spectral_radius"] = s(max(abs(v) for v in eig))
            entry["best_damping"] = {"omega_star": s(omega), "rate": s(rate)}
        elif cid == "REC-04":
            entry["spectrum"] = "0.95 e^{+-2 pi i / 3}, 0.3"
            entry["spectral_radius"] = "0.95"
        else:
            entry["spectrum"] = "0.5 (triple, one Jordan block of size 3)"
            entry["spectral_radius"] = "0.5"
            sv = svd_r(amat, compute_uv=False)
            entry["norm_2"] = s(max(sv))
            d0 = [mpf("0.1") * v for v in T_STAR]
            growth = [norm2(matpow_apply(amat, d0, k)) / norm2(d0) for k in range(9)]
            entry["transient_growth_2norm_d0=0.1t*"] = vec(growth)
            ok(
                "REC-05 transient growth peaks at k=3 with 8.70",
                abs(growth[3] - mpf("8.70")) < mpf("0.005") and growth[3] == max(growth),
            )
        for gamma_str in ("0", "0.1"):
            gamma = mpf(gamma_str)
            g_map = manufactured_map(amat, gamma)
            # closed-form identities
            fixed = g_map(T_STAR)
            ok(
                f"{cid} gamma={gamma_str}: t* is a fixed point",
                norm_inf([fixed[i] - T_STAR[i] for i in range(3)]) == 0,
            )
            jac = manufactured_jacobian(amat, gamma, T_STAR)
            ok(
                f"{cid} gamma={gamma_str}: dG/dt(t*) = A",
                all(jac[i, j] == amat[i, j] for i in range(3) for j in range(3)),
            )
            r0 = [g_map(t0)[i] - t0[i] for i in range(3)]
            v: dict[str, Any] = {"gamma": gamma_str, "residual_at_start_mol_per_s": vec(r0)}
            if gamma == 0:
                grade = krylov_grade(amat, r0)
                v["krylov_grade"] = grade
                v["anderson_termination_iteration_exact_arithmetic"] = grade + 1
                ok(f"{cid} linear: Krylov grade 3", grade == 3)
            run = accelerate(
                bounded_map(g_map), t0, scale=scale3, tolerance=tol3, lower_bounds=(0, 0, 0)
            )
            v["policy_simulation_anderson"] = run_block(run, keep=6)
            ok(f"{cid} gamma={gamma_str}: policy converges", run.outcome == "CONVERGED")
            if gamma == 0:
                ok(
                    f"{cid} linear: policy terminates at exactly grade+1 = 4",
                    run.iterations == 4,
                    str(run.iterations),
                )
                ok(
                    f"{cid} linear: no restart, no column drop, no landing",
                    run.events["restarts"] == 0
                    and run.events["column_dropped_condition"] == 0
                    and run.events["column_dropped_coefficient"] == 0
                    and run.events["bound_landings"] == 0,
                )
                ok(
                    f"{cid} linear: kappa and gamma a decade inside their limits",
                    run.events["max_kappa"] < KAPPA_MAX / 10
                    and run.events["max_gamma_inf"] < GAMMA_MAX / 10,
                    f"kappa {nstr(run.events['max_kappa'], 5)} gamma "
                    f"{nstr(run.events['max_gamma_inf'], 5)}",
                )
                ok(
                    f"{cid} linear: converged to t*",
                    norm_inf([run.x[i] - T_STAR[i] for i in range(3)]) < mpf("1e-25"),
                )
            elif cid == "REC-05" and gamma_str == "0.1":
                dist = norm_inf([run.x[i] - T_STAR[i] for i in range(3)])
                ok("REC-05 gamma=0.1: the policy lands on a fixed point other than t*", dist > 1)
                v["converges_to"] = "S1"
            else:
                ok(
                    f"{cid} gamma={gamma_str}: converged to t*",
                    norm_inf([run.x[i] - T_STAR[i] for i in range(3)]) < mpf("1e-6"),
                )
                v["converges_to"] = "t*"
            # plain substitution under the policy (depth 0 override)
            sub = accelerate(
                bounded_map(g_map),
                t0,
                scale=scale3,
                tolerance=tol3,
                depth=0,
                max_iterations=600,
                lower_bounds=(0, 0, 0),
            )
            v["policy_simulation_substitution_depth0"] = run_block(sub, keep=8)
            entry["variants"][f"gamma={gamma_str}"] = v
        cases[cid] = entry

    # REC-01 specifics: oscillation detector fires at iteration 3 under substitution; not under
    # Anderson
    r01 = cases["REC-01"]["variants"]
    ok(
        "REC-01 substitution: oscillation detected at iteration 3",
        r01["gamma=0"]["policy_simulation_substitution_depth0"]["events"]["oscillation_detected_at"]
        == 3,
    )
    ok(
        "REC-01 substitution converges (with the damping response)",
        r01["gamma=0"]["policy_simulation_substitution_depth0"]["outcome"] == "CONVERGED",
    )
    # REC-02 specifics
    t0_02 = tuple(mpf("0.5") * v for v in T_STAR)
    t2_unbounded = substitution_unbounded(REC_MAPS["REC-02"]["A"], t0_02, 2)
    ok("REC-02: unbounded linear substitution has t_2,A = -0.125", t2_unbounded[0] == mpf("-0.125"))
    cases["REC-02"]["unbounded_linear_substitution_iterate_2"] = vec(t2_unbounded)
    sub02 = cases["REC-02"]["variants"]["gamma=0"]["policy_simulation_substitution_depth0"]
    ok(
        "REC-02 substitution: first bound landing at the second step, iterate 2 has t_A = 0 "
        "exactly",
        sub02["events"]["bound_landings"] >= 1
        and cases["REC-02"]["variants"]["gamma=0"]["policy_simulation_substitution_depth0"][
            "final_t"
        ]
        is not None,
    )
    run02 = accelerate(
        bounded_map(manufactured_map(REC_MAPS["REC-02"]["A"], mpf(0))),
        t0_02,
        scale=scale3,
        tolerance=tol3,
        depth=0,
        max_iterations=600,
        lower_bounds=(0, 0, 0),
    )
    ok("REC-02 substitution: iterate 2 lands on the bound exactly", run02.trajectory_x[2][0] == 0)
    ok(
        "REC-02 substitution: oscillation detected at iteration 3, then converges",
        run02.events["oscillation_detected_at"] == 3 and run02.outcome == "CONVERGED",
    )
    cases["REC-02"]["substitution_iterate_2_landed"] = vec(run02.trajectory_x[2])
    ok(
        "REC-02 Anderson: no invalid trial and no landing (bounds never reached)",
        cases["REC-02"]["variants"]["gamma=0"]["policy_simulation_anderson"]["events"][
            "invalid_trials"
        ]
        == 0
        and cases["REC-02"]["variants"]["gamma=0.1"]["policy_simulation_anderson"]["events"][
            "invalid_trials"
        ]
        == 0,
    )
    # REC-03: damping cannot help
    ok(
        "REC-03: omega* = 1 and rate 0.95",
        cases["REC-03"]["best_damping"] == {"omega_star": s(mpf(1)), "rate": s(mpf("0.95"))},
    )
    # REC-04: the sign-alternation detector does not fire under substitution
    sub04 = cases["REC-04"]["variants"]["gamma=0"]["policy_simulation_substitution_depth0"]
    ok(
        "REC-04 substitution: oscillation detector never fires (rotation)",
        sub04["events"]["oscillation_detected_at"] is None,
    )
    # REC-05: transient growth without a restart; the residual increases and nothing fires
    a05 = cases["REC-05"]["variants"]["gamma=0"]["policy_simulation_anderson"]
    ok(
        "REC-05 linear Anderson: residual increases at least once and no safeguard fires",
        a05["events"]["residual_increases"] >= 1
        and a05["events"]["restarts"] == 0
        and a05["events"]["stagnation_closures"] == [],
    )
    sub05 = cases["REC-05"]["variants"]["gamma=0"]["policy_simulation_substitution_depth0"]
    ok(
        "REC-05 linear substitution converges despite the transient (rho = 0.5)",
        sub05["outcome"] == "CONVERGED",
    )
    sub05t = cases["REC-05"]["variants"]["gamma=0.1"]["policy_simulation_substitution_depth0"]
    ok(
        "REC-05 gamma=0.1 substitution under the policy: a slow divergence reads as stagnation "
        "and closes "
        "RECYCLE_STAGNATION at 20 with the residual grown",
        sub05t["outcome"] == "RECYCLE_STAGNATION"
        and sub05t["iterations"] == 20
        and sub05t["events"]["residual_increases"] >= 15
        and sub05t["events"]["stagnation_closures"] == [10, 15, 20],
    )
    g05raw = manufactured_map(REC_MAPS["REC-05"]["A"], mpf("0.1"))
    xr = tuple(mpf("1.1") * v for v in T_STAR)
    f0 = norm_inf([g05raw(xr)[i] - xr[i] for i in range(3)])
    k_raw = None
    for k in range(1, 61):
        xr = g05raw(xr)
        if norm_inf([g05raw(xr)[i] - xr[i] for i in range(3)]) > mpf("1e4") * f0:
            k_raw = k
            break
    ok(
        "REC-05 gamma=0.1 raw substitution (no safeguard, no bound) exceeds 1e4 x the initial "
        "residual within 60 steps",
        k_raw is not None,
    )
    cases["REC-05"]["raw_substitution_gamma=0.1_exceeds_divergence_factor_at"] = k_raw
    # REC-05 gamma=0.1: the three fixed points, pinned by Newton from the definition
    g05 = manufactured_map(REC_MAPS["REC-05"]["A"], mpf("0.1"))
    roots: dict[str, Vec] = {"t*": T_STAR}
    from mpmath import findroot

    def resid(a: Any, b: Any, c: Any) -> list[Any]:
        g = g05((a, b, c))
        return [g[0] - a, g[1] - b, g[2] - c]

    s1 = findroot(resid, (mpf("3.8887"), mpf("2.5769"), mpf("3.1111")))
    roots["S1"] = (s1[0], s1[1], s1[2])
    ok("REC-05 gamma=0.1: S1 is a fixed point", norm_inf(resid(*roots["S1"])) < mpf("1e-30"))
    ok(
        "REC-05 gamma=0.1: S1 is not t* (distance > 1 mol/s)",
        norm_inf([roots["S1"][i] - T_STAR[i] for i in range(3)]) > 1,
    )
    landed = [
        mpf(v)
        for v in cases["REC-05"]["variants"]["gamma=0.1"]["policy_simulation_anderson"]["final_t"]
    ]
    ok(
        "REC-05 gamma=0.1: the policy lands on S1 from 1.1 t* (within 1e-4: the solution-error "
        "bound is ~40 x 3.1e-8)",
        norm_inf([landed[i] - roots["S1"][i] for i in range(3)]) < mpf("1e-4"),
    )
    basin: dict[str, Any] = {}
    for s0 in ("1.05", "1.15"):
        r = accelerate(
            bounded_map(g05),
            tuple(mpf(s0) * v for v in T_STAR),
            scale=scale3,
            tolerance=tol3,
            lower_bounds=(0, 0, 0),
        )
        basin[f"start={s0}t*"] = {
            "outcome": r.outcome,
            "iterations": r.iterations,
            "lands_on": "S1"
            if norm_inf([r.x[i] - roots["S1"][i] for i in range(3)]) < mpf("1e-4")
            else "other",
        }
        ok(
            f"REC-05 gamma=0.1: start {s0} t* also lands on S1 (basin margin)",
            basin[f"start={s0}t*"]["lands_on"] == "S1",
        )
    cases["REC-05"]["fixed_points_gamma=0.1"] = {
        "t*": vec(T_STAR),
        "S1": vec(roots["S1"]),
        "note": "S1 is the fixed point the registered policy reaches from the registered start "
        "1.1 t*; "
        "the basin margin is executable (1.05 t* and 1.15 t* land there too). Other fixed points "
        "of the quadratic map exist and are not registered (T03: multiple-root provenance).",
        "basin_margin": basin,
    }

    # ---- auxiliary cases ------------------------------------------------------------------
    aux: dict[str, Any] = {}
    # RCY-DIV: rho = 1.5 positive real, no bounds, depth 0 -> the stagnation rule closes a monotone
    # divergence at 15 (ratios 1.5 > 0.99 for three windows of 5, two restarts); Anderson terminates
    # at 4
    a_div = diag("1.5", "0.5", "0.2")
    gdiv = manufactured_map(a_div, mpf(0))
    div_run = accelerate(
        lambda t: gdiv(t),
        tuple(mpf("0.5") * v for v in T_STAR),
        scale=scale3,
        tolerance=tol3,
        depth=0,
    )
    # closed form: f_k = (A - I) A^k d0 with d0 = -0.5 t*; component 1 is -0.25 * 1.5^k and
    # dominates
    # the infinity norm from k = 1 on (at k = 0 component 3, 1.2, dominates), so ||f_hat_k|| = 0.25
    # * 1.5^k / 3
    # for k >= 1; the first ratio (k = 1) is 0.9375 < 0.99, every later one is 1.5, so the windows
    # close
    # at 6, 11 and 16.
    ok(
        "RCY-DIV substitution: RECYCLE_STAGNATION at 16 with closures [6, 11, 16]",
        div_run.outcome == "RECYCLE_STAGNATION"
        and div_run.iterations == 16
        and div_run.events["stagnation_closures"] == [6, 11, 16],
    )
    ok(
        "RCY-DIV substitution: ||f_hat_k|| = 0.25 * 1.5^k / 3 for k = 1..16 and 0.4 at k = 0",
        div_run.residual_inf_scaled[0] == mpf("0.4")
        and all(
            abs(div_run.residual_inf_scaled[k] - mpf("0.25") * mpf("1.5") ** k / 3) < mpf("1e-30")
            for k in range(1, 17)
        ),
    )
    div_and = accelerate(
        lambda t: gdiv(t), tuple(mpf("0.5") * v for v in T_STAR), scale=scale3, tolerance=tol3
    )
    ok(
        "RCY-DIV: Anderson terminates at 4",
        div_and.outcome == "CONVERGED" and div_and.iterations == 4,
    )
    aux["RCY-DIV"] = {
        "title": "monotone divergence (rho = 1.5, real positive), no bounds: the stagnation "
        "rule's divergence case and the EO-merge edge with a real root",
        "A": mat(a_div),
        "gamma": "0",
        "start": vec(tuple(mpf("0.5") * v for v in T_STAR)),
        "lower_bounds": None,
        "substitution_depth0": run_block(div_run, keep=17),
        "anderson": run_block(div_and, keep=6),
        "closed_form": "||f_hat_k||_inf = 0.25 * 1.5^k / 3 for k >= 1 (component 1 dominates from "
        "k = 1; at k = 0 component 3 gives 0.4); 1.5^16 = 656.84",
        "eo_merge_expected": "CONVERGED in one Newton step to t* (affine)",
    }
    # RCY-STALL: G(t) = t + c, no root
    c = (mpf(1), mpf(1), mpf(1))
    gstall = lambda t: tuple(t[i] + c[i] for i in range(3))  # noqa: E731
    stall = accelerate(gstall, (mpf(0),) * 3, scale=scale3, tolerance=tol3)
    ok(
        "RCY-STALL: stagnation closures at 5, 10, 15 and RECYCLE_STAGNATION after two restarts",
        stall.outcome == "RECYCLE_STAGNATION"
        and stall.events["stagnation_closures"] == [5, 10, 15]
        and stall.events["restarts"] == 2,
    )
    ok(
        "RCY-STALL: every history column was dropped for condition (sigma_min = 0)",
        stall.events["column_dropped_condition"] > 0 and stall.events["anderson_steps"] == 0,
    )
    aux["RCY-STALL"] = {
        "title": "constant residual, no root: stagnation -> restart x2 -> give up -> EO merge "
        "fails singular",
        "map": "G(t) = t + (1, 1, 1)",
        "start": ["0", "0", "0"],
        "lower_bounds": None,
        "anderson": run_block(stall, keep=3),
        "eo_merge_expected": "LINEAR_SOLVE_FAILED(exactly_singular): dR/dt = 0",
    }
    # RCY-COEF: 1-D f(t) = 1 + 1e-6 t
    eps = mpf("1e-6")
    gcoef = lambda t: (t[0] + 1 + eps * t[0],)  # noqa: E731
    coef = accelerate(gcoef, (mpf(0),), scale=(mpf(1),), tolerance=(mpf("3.1e-8"),))
    gamma1 = (1 + eps) / eps  # the secant coefficient at k = 1: f_1 / (f_1 - f_0) = (1 + eps)/eps
    ok("RCY-COEF: the coefficient at k = 1 is (1 + 1e-6)/1e-6 > 1e4", gamma1 > GAMMA_MAX)
    ok(
        "RCY-COEF: every Anderson column is dropped for its coefficient and the run stagnates out "
        "after two restarts",
        coef.outcome == "RECYCLE_STAGNATION"
        and coef.events["anderson_steps"] == 0
        and coef.events["column_dropped_coefficient"] >= 1
        and coef.events["stagnation_closures"] == [5, 10, 15],
    )
    aux["RCY-COEF"] = {
        "title": "nearly constant residual with a far root: the coefficient bound's case, then "
        "the EO merge that solves it",
        "map": "G(t) = t + 1 + 1e-6 t (one variable, scale 1, no bounds)",
        "start": ["0"],
        "root": s(-1 / eps),
        "secant_coefficient_at_k1": s(gamma1),
        "anderson": run_block(coef, keep=3),
        "eo_merge_expected": "CONVERGED in one Newton step to t = -1e6 (affine)",
    }
    # NEST-1
    nest = nest_tear_set()
    ok("NEST-1: no single edge breaks the loop", not nest["single_edge_feedback_set_exists"])
    ok("NEST-1: the rule tears {s4, s5}", nest["tear_streams"] == ["s4", "s5"])
    nest_fixed = (mpf(5), mpf(4))
    ok(
        "NEST-1: (5, 4) is the fixed point",
        norm_inf([nest_map(nest_fixed)[i] - nest_fixed[i] for i in range(2)]) < mpf("1e-35"),
    )
    prod = nest_evaluate(*nest_fixed)["s3"]
    ok("NEST-1: product equals feed", abs(prod - NEST_FEED) < mpf("1e-35"))
    a_nest = matrix(
        [
            [NEST_B_SPLIT, NEST_B_SPLIT],
            [NEST_C_RECYCLE * (1 - NEST_B_SPLIT), NEST_C_RECYCLE * (1 - NEST_B_SPLIT)],
        ]
    )
    nest_run = accelerate(
        bounded_map(nest_map),
        (mpf(0), mpf(0)),
        scale=(mpf(1), mpf(1)),
        tolerance=(mpf("3.1e-8"),) * 2,
        lower_bounds=(0, 0),
    )
    ok(
        "NEST-1: Anderson terminates at 2 (grade 1 + 1)",
        nest_run.outcome == "CONVERGED" and nest_run.iterations == 2,
    )
    alt_run = accelerate(
        bounded_map(nest_alternate_map),
        (mpf(0), mpf(0)),
        scale=(mpf(1), mpf(1)),
        tolerance=(mpf("3.1e-8"),) * 2,
        lower_bounds=(0, 0),
    )
    ok(
        "NEST-1 alternate tear {s1, s5}: same product",
        alt_run.outcome == "CONVERGED"
        and abs(
            nest_evaluate(NEST_B_SPLIT * (alt_run.x[0] + alt_run.x[1]), alt_run.x[1])["s3"]
            - NEST_FEED
        )
        < mpf("1e-7"),
    )
    aux["NEST-1"] = {
        "title": "two edge-disjoint loops sharing unit B: a multi-edge feedback set",
        "connections": [list(c) for c in NEST_CONNECTIONS],
        "boundary_units": list(NEST_BOUNDARY),
        "units": {
            "A": "s1 = s0 + s4",
            "B": "s4 = 0.5 (s1 + s5); s2 = 0.5 (s1 + s5)",
            "C": "s5 = 0.8 s2; s3 = 0.2 s2",
        },
        "tear": nest,
        "map_A": mat(a_nest),
        "spectrum": ["0.9", "0"],
        "fixed_point_s4_s5": vec(nest_fixed),
        "streams_at_fixed_point": {k: s(v) for k, v in nest_evaluate(*nest_fixed).items()},
        "anderson": run_block(nest_run, keep=4),
        "alternate_tear_s1_s5": {
            "fixed_point": vec((mpf(6), mpf(4))),
            "anderson": run_block(alt_run, keep=4),
        },
    }
    ok(
        "NEST-1 alternate tear fixed point (6, 4)",
        norm_inf([nest_alternate_map((mpf(6), mpf(4)))[i] - (mpf(6), mpf(4))[i] for i in range(2)])
        < mpf("1e-35"),
    )
    # SCL-1: REC-03 linear with non-uniform scales
    g03 = manufactured_map(REC_MAPS["REC-03"]["A"], mpf(0))
    t0_03 = tuple(mpf("0.5") * v for v in T_STAR)
    scl = accelerate(
        bounded_map(g03),
        t0_03,
        scale=(mpf(1), mpf(3), mpf(9)),
        tolerance=(mpf("3.1e-8") / 3, mpf("3.1e-8"), mpf("3.1e-8") * 3),
        lower_bounds=(0, 0, 0),
    )
    uni = cases["REC-03"]["variants"]["gamma=0"]["policy_simulation_anderson"]
    ok(
        "SCL-1: non-uniform scales change iterate 2 by more than 1e-2 and still terminate at 4",
        scl.outcome == "CONVERGED"
        and scl.iterations == 4
        and abs(scl.residual_inf_scaled[2] - mpf(uni["residual_inf_scaled"][2])) > mpf("1e-2"),
    )
    aux["SCL-1"] = {
        "title": "REC-03 linear under scales (1, 3, 9): the least squares is taken in scaled "
        "coordinates",
        "scale": ["1", "3", "9"],
        "tolerance_mol_per_s": [s(mpf("3.1e-8") / 3), "3.1e-8", s(mpf("3.1e-8") * 3)],
        "anderson": run_block(scl, keep=6),
    }
    # RCY-TRUNC: REC-01 linear with depth 2
    g01 = manufactured_map(REC_MAPS["REC-01"]["A"], mpf(0))
    t0_01 = tuple(mpf("0.5") * v for v in T_STAR)
    trunc = accelerate(
        bounded_map(g01), t0_01, scale=scale3, tolerance=tol3, depth=2, lower_bounds=(0, 0, 0)
    )
    ok(
        "RCY-TRUNC: depth 2 converges later than 4 and within 30",
        trunc.outcome == "CONVERGED" and 4 < trunc.iterations <= 30,
    )
    aux["RCY-TRUNC"] = {
        "title": "REC-01 linear with depth_max = 2: the sliding window truncates and finite "
        "termination is lost",
        "depth_max": 2,
        "anderson": run_block(trunc, keep=6),
    }

    # ---- SYN-001 closed forms ---------------------------------------------------------------
    syn = a02_closed_forms()
    sweep = syn["sweep"]
    for key, row in sweep.items():
        ok(
            f"A02 sweep {key}: Q_heater + Q_flash = Q_total",
            abs(row["Q_heater_W"] + row["Q_flash_W"] - syn["Q_total_W"]) < mpf("1e-25"),
        )
    ok("A02: Q_flash = 0 exactly at T_heater = 360 K", sweep["T_heater=360K"]["Q_flash_W"] == 0)
    ok(
        "A02: Q_total equals P01's 56338.069446743527231 W",
        abs(syn["Q_total_W"] - mpf("56338.069446743527231")) < mpf("1e-14"),
    )
    ok(
        "A02: the 360 K heater split equals the flash split",
        all(
            abs(
                sweep["T_heater=360K"]["S3_vapor_mol_per_s"][i]
                - syn["flash_split_at_360K"]["vapor"][i]
            )
            < mpf("1e-30")
            for i in range(3)
        ),
    )
    ok(
        "A02: regimes along the sweep",
        [
            sweep[k]["regime"]
            for k in (
                "T_heater=340K",
                "T_heater=350K",
                "T_heater=355K",
                "T_heater=358K",
                "T_heater=360K",
                "T_heater=365K",
            )
        ]
        == ["LIQUID", "LIQUID", "TWO_PHASE", "TWO_PHASE", "TWO_PHASE", "TWO_PHASE"],
    )
    ok(
        "A02: bubble point of S3.n between 350 and 355 K",
        mpf(350) < syn["S3_bubble_point_K"] < mpf(355),
    )
    ok("A02: dew point of S3.n between 365 and 400 K", mpf(365) < syn["S3_dew_point_K"] < mpf(400))
    ok(
        "A02: the duty curve is steep in the band (factor > 2 between 350 and 355 K)",
        sweep["T_heater=355K"]["Q_heater_W"] / sweep["T_heater=350K"]["Q_heater_W"] > 2,
    )
    br = syn["branch_roots"]
    ok(
        "A02 liquid-branch root for Q_flash = 0 lies outside the provider domain",
        br["Q_flash=0"]["liquid_branch_T_K"] > 440,
    )
    ok(
        "A02 liquid-branch root for Q_flash = Q(355 K) is inside the domain and inadmissible",
        280 < br["Q_flash=Q(355K)"]["liquid_branch_T_K"] < 440
        and br["Q_flash=Q(355K)"]["liquid_branch_sum_zK"] > 1,
    )
    ok(
        "A02 vapor-branch root for Q_flash = 0 lies outside the domain (below 280 K)",
        br["Q_flash=0"]["vapor_branch_T_K"] < 280,
    )
    ok(
        "A02: at 440 K the S3 kernel is all vapor; at 280 K all liquid",
        br["Q_flash=0"]["sum_z_over_K_at_440K"] < 1 and br["Q_flash=0"]["sum_zK_at_280K"] < 1,
    )
    ok(
        "EO nominal: the S3 flip on the ray is between 0.5 and 1",
        mpf("0.5") < syn["s_flip_nominal_ray"] < 1,
    )
    ok(
        "EO high-recycle: the S3 flip on the ray is below the initializer 0.05",
        syn["s_flip_high_recycle_ray"] < mpf("0.05"),
    )

    document = {
        "policy": POLICY,
        "cases_rec": cases,
        "cases_auxiliary": aux,
        "syn001": {
            "t_star_nominal_mol_per_s": vec(syn["t_star_nominal"]),
            "S3_n_at_t_star_mol_per_s": vec(syn["S3_n_mol_per_s"]),
            "H_S2_W": s(syn["H_S2_W"]),
            "H_flash_products_W": s(syn["H_flash_products_W"]),
            "Q_total_W": s(syn["Q_total_W"]),
            "flash_split_at_360K": {
                "beta": s(syn["flash_split_at_360K"]["beta"]),
                "vapor": vec(syn["flash_split_at_360K"]["vapor"]),
                "liquid": vec(syn["flash_split_at_360K"]["liquid"]),
            },
            "a02_sweep": {
                k: {
                    "regime": r["regime"],
                    "Q_heater_W": s(r["Q_heater_W"]),
                    "Q_flash_W": s(r["Q_flash_W"]),
                    "beta": s(r["beta"]),
                    "S3_vapor_mol_per_s": vec(r["S3_vapor_mol_per_s"]),
                    "S3_liquid_mol_per_s": vec(r["S3_liquid_mol_per_s"]),
                }
                for k, r in sweep.items()
            },
            "S3_bubble_point_K": s(syn["S3_bubble_point_K"]),
            "S3_dew_point_K": s(syn["S3_dew_point_K"]),
            "s_flip_nominal_ray": s(syn["s_flip_nominal_ray"]),
            "s_flip_high_recycle_ray": s(syn["s_flip_high_recycle_ray"]),
            "branch_roots": {
                k: {kk: (s(vv) if not isinstance(vv, list) else vv) for kk, vv in r.items()}
                for k, r in br.items()
            },
            "plans": {
                "SYN-001-nominal (tear)": PLAN_NOMINAL,
                "SYN-001-nominal (eo override)": PLAN_NOMINAL_EO,
                "SYN-001-A02-*": PLAN_A02,
                "SYN-001-once-through": PLAN_ONCE_THROUGH,
            },
            "certified_rows": list(SYN001_CERTIFIED_ROWS),
            "a02_region": {
                "units": list(SYN001_LOOP),
                "rows": "all rows of the four units (44 after the heater's HEAT-T is removed and "
                "SPEC:SPEC-flash-duty added) minus the 2 certified = 42",
                "columns": "the 47 free variables minus S1's 5 = 42",
                "fixed_upstream": ["S1.n.A", "S1.n.B", "S1.n.C", "S1.T", "S1.P"],
            },
        },
        "measured": MEASURED,
        "checks_passed": checks,
    }
    return document


def emit(path: Path, document: dict[str, Any]) -> str:
    header = {
        "generated_by": "Fable 5.1, docs/derivations/scripts/t02_reference.py: closed forms of "
        "the manufactured maps and of "
        "SYN-001 (through syn001_reference.py and k03_reference.py), and the registered recycle "
        "policy "
        "simulated at 40 digits from its statement in T02-recycle-spec.md §5",
        "specification": "docs/derivations/T02-recycle-spec.md",
        "independence": "no solver, graph-layer, oracle or process_runtime code was used. "
        "`closed_form` values are "
        "expectations; `policy_simulation` values are definition-level references (the same "
        "policy, "
        "derived a second time); the `measured` block is prototype observation, labelled, never an "
        "expectation.",
    }
    text = yaml.safe_dump({**header, **document}, sort_keys=False, allow_unicode=True, width=110)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="re-derive every identity and print the checks"
    )
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not args.check and not args.emit:
        parser.error("choose --check and/or --emit PATH")
    document = build()
    if args.check:
        for name in document["checks_passed"]:
            print(f"ok  {name}")
        print(f"{len(document['checks_passed'])} checks passed")
    if args.emit:
        digest = emit(Path(args.emit), document)
        print(f"wrote {args.emit}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
