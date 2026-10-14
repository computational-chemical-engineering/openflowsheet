"""The outer coupling of the `revision_coupled` route: Broyden's good method on w = (X̂, ΔT̂) per
external unit (M02 design note §4.2–§4.4; ADR 0034 D2, D3; register R-225).

A unit embedded extent-fixed (`models.c1.reactor`) takes the N2 conversion X̂ and the temperature
rise ΔT̂ as pinned parameters, so its inner EO problem is analytic. This module iterates those two
numbers per unit against the external model:

- **The inner solve and the experiments are injected.** `orchestrator` sits below `adapters`, so
  the driver never builds an experiment or a binding: the application hands it `solve_inner`
  (re-bind at w, plan, solve; read each external unit's inlet exactly from the solution) and
  `evaluate` (one experiment of one unit at one inlet). Both are plain callables; the driver's
  arithmetic is all here, and is tested with both stubbed (G8 (f)).
- **The problem (§4.2).** F_j(w) = (ξ_E / n_N2,in, T_E − T_in) on a flowing inlet, (X̂_j, 0) on a
  `ZERO_FLOW` answer; r_j = F_j(w) − w_j; ρ = max_j max(|ξ_E − X̂_j n_N2,in| / (τ_ξ n_tot,in),
  |T_E − T_in − ΔT̂_j| / τ_T). Converged iff ρ ≤ 1 at an iterate whose inner solve converged, the
  experiments evaluated at that iterate's inlets.
- **The iteration (§4.3, `broyden_good_v1`).** Scaled coordinates u = D w, D = diag(1/s_X,
  1/s_dT) per unit; B₀ = −I, so the first step is successive substitution; Broyden's good update
  B += ((r̂_k − r̂_b) − B Δu) Δuᵀ / (Δuᵀ Δu) from the base b the step was taken from; on no
  decrease against the best iterate at k ≥ 2n (n = 2m; §14.5 D5), B = −I and a substitution step
  from the best (a second reset in a row ends `no_decrease`; before 2n, no reset); steps clipped
  to the bounds; at most `max_outer` accepted iterates. An inner failure or a deterministic
  external refusal halves the step back towards its base, at most three times per iteration (the
  inner solve repeated, the experiments run only at the accepted point); an inner failure at
  k = 0 passes its own outcome through.

**The record (§7.1).** Every trial point — accepted or backtracked — is one entry of
`iterations`: its outer index `k`, `w`, `u`, the inner solve's facts, each unit's experiment
documents with ξ_E, T_E, the residual components and the floor ratios, ρ, and the `step` taken
from it. A replay reads the experiments back in this order (§7.2).

Conventions: units in the order the caller gives them (instance-id order); w, u, r̂ and Δu are
flat lists over the units, (X̂, ΔT̂) per unit; ΔT̂ in K. No floating-point state is quantized.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt

__all__ = [
    "BACKTRACKS",
    "METHOD",
    "CouplingBlock",
    "CouplingRun",
    "ExternalAnswer",
    "InnerSolve",
    "UnitInlet",
    "couple",
]

#: §4.3: the one registered iteration.
METHOD: Final = "broyden_good_v1"
#: §4.3: step-halvings towards the base per outer iteration.
BACKTRACKS: Final = 3

Vector = npt.NDArray[np.float64]
AnswerStatus = Literal["ok", "zero_flow", "refused", "transient"]
CouplingOutcome = str


@dataclass(frozen=True)
class CouplingBlock:
    """A variant's `coupling` block (`model-variant.schema.json#/$defs/coupling`)."""

    tau_xi_rel: float
    tau_T_K: float  # noqa: N815 - the registered symbol
    max_outer: int
    method: str
    scale_X: float  # noqa: N815
    scale_dT: float  # noqa: N815
    initial: tuple[float, float]
    bounds_X: tuple[float, float]  # noqa: N815
    bounds_dT: tuple[float, float]  # noqa: N815

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> CouplingBlock:
        scales, initial, bounds = document["scales"], document["initial"], document["bounds"]
        block = cls(
            tau_xi_rel=float(document["tau_xi_rel"]),
            tau_T_K=float(document["tau_T_K"]),
            max_outer=int(document["max_outer"]),
            method=str(document["method"]),
            scale_X=float(scales["X"]),
            scale_dT=float(scales["dT_K"]),
            initial=(float(initial["X"]), float(initial["dT_K"])),
            bounds_X=(float(bounds["X"][0]), float(bounds["X"][1])),
            bounds_dT=(float(bounds["dT_K"][0]), float(bounds["dT_K"][1])),
        )
        if block.method != METHOD:
            raise ValueError(f"coupling method {block.method!r} is not {METHOD!r}")
        return block


@dataclass(frozen=True)
class UnitInlet:
    """An external unit's inlet, read exactly from an inner solution (§4.2)."""

    n: tuple[float, ...]
    T: float  # noqa: N815
    P: float  # noqa: N815
    #: n of the key reactant (N2): X̂ is its conversion.
    n_key: float

    @property
    def n_tot(self) -> float:
        return sum(self.n)

    def as_document(self) -> dict[str, Any]:
        return {"n": list(self.n), "T": self.T, "P": self.P}


@dataclass(frozen=True)
class InnerSolve:
    """What the injected inner solver returns for one w."""

    outcome: str
    #: The solution over the declaration's variables; `None` unless the inner solve converged.
    state: Mapping[str, float] | None
    #: Each external unit's inlet at `state` (empty unless converged).
    inlets: Mapping[str, UnitInlet]
    iterations: int | None
    #: How the inner solve started (the route's initializer chain, or a previous solution).
    start: str
    constants_sha256: str | None
    state_sha256: str | None
    #: The caller's own objects for this solve (binding, plan, run), passed back untouched.
    payload: Any = None

    @property
    def converged(self) -> bool:
        return self.outcome == "CONVERGED" and self.state is not None

    def as_document(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "iterations": self.iterations,
            "start": self.start,
            "constants_sha256": self.constants_sha256,
            "state_sha256": self.state_sha256,
        }


@dataclass(frozen=True)
class ExternalAnswer:
    """One experiment's answer as the coupling reads it.

    `ok`: ξ_E and T_E (the projected extent and the outlet temperature, M01 §8.9). `zero_flow`: the
    boundary's `ZERO_FLOW` answer. `refused`: a deterministic refusal (cached; the driver
    backtracks). `transient`: no deterministic outcome after the runner's retries (the run ends
    `EVALUATION_ERROR`). `code` is the boundary envelope's code; `documents` the unit's record
    members (`request`, `result`, `attempts`, `cache_hit`); `floor_xi` and `floor_T` the
    propagated precision floors δξ (mol/s) and δT (K), `None` where the floor is zero.
    `attributed_request` is not a record member (register R-317 (a)): the request the answer is
    attributed to, whose inputs EXT-COUPLING checks against the certified inlet bit for bit —
    live, the request sent (`documents["request"]`); in a replay, the request recomputed at the
    rerun's inlet, while `documents` keeps the recorded (served) one."""

    status: AnswerStatus
    code: str
    xi: float | None = None
    T_out: float | None = None  # noqa: N815
    floor_xi: float | None = None
    floor_T: float | None = None  # noqa: N815
    documents: Mapping[str, Any] = field(default_factory=dict)
    attributed_request: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class _Point:
    """An accepted iterate: its u, its inner solve, its scaled residual and ρ."""

    k: int
    u: Vector
    inner: InnerSolve
    r_hat: Vector
    rho: float


@dataclass(frozen=True)
class CouplingRun:
    """The coupling's end: the outcome, its reason, the record's iterates, and the last inner
    solve (the converged one on `CONVERGED`; the last one that ran otherwise)."""

    outcome: CouplingOutcome
    #: `COUPLING_NOT_CONVERGED`'s reason, or `EVALUATION_ERROR`'s `external_<status>(<unit>)`.
    reason: str | None
    iterations: tuple[Mapping[str, Any], ...]
    final: InnerSolve | None
    #: The accepted iterate's w per unit on `CONVERGED`; the last trial's otherwise.
    w: Mapping[str, tuple[float, float]]
    #: On `CONVERGED`: each unit's answer at the final iterate.
    answers: Mapping[str, ExternalAnswer] = field(default_factory=dict)
    #: Accepted iterates (each with one experiment per unit; backtracked trials not counted).
    outer_iterations: int = 0

    @property
    def converged(self) -> bool:
        return self.outcome == "CONVERGED"


InnerSolver = Callable[[Mapping[str, tuple[float, float]], Mapping[str, float] | None], InnerSolve]
Evaluate = Callable[[str, UnitInlet], ExternalAnswer]
OnIteration = Callable[[int, int], None]


def _scales(units: Sequence[str], block: CouplingBlock) -> Vector:
    return np.array([s for _ in units for s in (block.scale_X, block.scale_dT)], dtype=np.float64)


def _w_of(u: Vector, units: Sequence[str], scales: Vector) -> dict[str, tuple[float, float]]:
    w = u * scales
    return {unit: (float(w[2 * j]), float(w[2 * j + 1])) for j, unit in enumerate(units)}


def _unit_terms(
    inlet: UnitInlet, answer: ExternalAnswer, w: tuple[float, float], block: CouplingBlock
) -> dict[str, Any]:
    """§4.2 for one unit: ξ_E, T_E, the residual r = F(w) − w, ρ's two terms and the floor
    ratios."""
    x_hat, dt_hat = w
    n_tot = inlet.n_tot
    if answer.status == "zero_flow":
        # §4.2: F = (X̂, 0) on a ZERO_FLOW answer; no division, and no extent to compare.
        xi_e, t_e = x_hat * inlet.n_key, inlet.T
        r_xi, r_t = 0.0, -dt_hat
        term_xi = 0.0
    else:
        assert answer.xi is not None and answer.T_out is not None
        if not inlet.n_key > 0.0:
            raise ValueError("defect: an `ok` experiment on an inlet with no key reactant")
        xi_e, t_e = answer.xi, answer.T_out
        r_xi = xi_e / inlet.n_key - x_hat
        r_t = (t_e - inlet.T) - dt_hat
        term_xi = abs(xi_e - x_hat * inlet.n_key) / (block.tau_xi_rel * n_tot)
    term_t = abs(t_e - inlet.T - dt_hat) / block.tau_T_K
    ratio_xi = (
        None
        if answer.floor_xi is None or answer.floor_xi == 0.0
        else block.tau_xi_rel * n_tot / answer.floor_xi
    )
    ratio_t = (
        None if answer.floor_T is None or answer.floor_T == 0.0 else block.tau_T_K / answer.floor_T
    )
    return {
        "xi_E": xi_e,
        "T_E": t_e,
        "n_N2_in": inlet.n_key,
        "n_tot_in": n_tot,
        "r_xi": r_xi,
        "r_T": r_t,
        "floor_ratio_xi": ratio_xi,
        "floor_ratio_T": ratio_t,
        "_rho": max(term_xi, term_t),
    }


def _unit_entry(
    inlet: UnitInlet, answer: ExternalAnswer, terms: Mapping[str, Any] | None
) -> dict[str, Any]:
    documents = answer.documents
    entry: dict[str, Any] = {
        "inlet": inlet.as_document(),
        "request": documents.get("request"),
        "result": documents.get("result"),
        "attempts": list(documents.get("attempts", ())),
        "cache_hit": bool(documents.get("cache_hit", False)),
        "xi_E": None,
        "T_E": None,
        "n_N2_in": inlet.n_key,
        "n_tot_in": inlet.n_tot,
        "r_xi": None,
        "r_T": None,
        "floor_ratio_xi": None,
        "floor_ratio_T": None,
    }
    if terms is not None:
        entry.update({key: value for key, value in terms.items() if not key.startswith("_")})
    return entry


def couple(
    units: Sequence[str],
    block: CouplingBlock,
    solve_inner: InnerSolver,
    evaluate: Evaluate,
    *,
    on_iteration: OnIteration | None = None,
) -> CouplingRun:
    """§4.3's iteration over `units` under one coupling `block` (every unit's variant carries the
    same one; the caller checks). `solve_inner(w, start)` solves the inner problem at w — `start`
    is `None` at k = 0 (the route's initializer chain) and otherwise the inner solution of the
    iterate the step was taken from; `evaluate(unit, inlet)` runs one experiment. `on_iteration(k,
    max_outer)` is called at the start of each outer iteration."""
    if not units:
        raise ValueError("a coupled run needs at least one external unit")
    m2 = 2 * len(units)
    scales = _scales(units, block)
    lower = (
        np.array(
            [b for _ in units for b in (block.bounds_X[0], block.bounds_dT[0])], dtype=np.float64
        )
        / scales
    )
    upper = (
        np.array(
            [b for _ in units for b in (block.bounds_X[1], block.bounds_dT[1])], dtype=np.float64
        )
        / scales
    )
    record: list[dict[str, Any]] = []
    u = np.array([value for _ in units for value in block.initial], dtype=np.float64) / scales
    b_matrix = -np.eye(m2)
    best: _Point | None = None
    base: _Point | None = None  # the iterate the current step was taken from
    reset_last = False
    k = 0
    accepted_count = 0

    def entry(u_at: Vector, inner: InnerSolve, unit_entries: Mapping[str, Any]) -> dict[str, Any]:
        w_at = u_at * scales
        item: dict[str, Any] = {
            "k": k,
            "w": [float(value) for value in w_at],
            "u": [float(value) for value in u_at],
            "inner": inner.as_document(),
            "units": dict(unit_entries),
            "rho": None,
            "step": {"kind": "none", "du": None, "B": None},
        }
        record.append(item)
        return item

    def end(
        outcome: str,
        reason: str | None,
        final: InnerSolve | None,
        u_at: Vector,
        answers: Mapping[str, ExternalAnswer] | None = None,
    ) -> CouplingRun:
        return CouplingRun(
            outcome=outcome,
            reason=reason,
            iterations=tuple(record),
            final=final,
            w=_w_of(u_at, units, scales),
            answers=dict(answers or {}),
            outer_iterations=accepted_count,
        )

    while True:
        if on_iteration is not None:
            on_iteration(k, block.max_outer)
        halvings = 0
        while True:  # the trial at u, halved back towards `base` on a failure
            w = _w_of(u, units, scales)
            inner = solve_inner(w, None if base is None else base.inner.state)
            failure: str | None = None
            accepted: tuple[Vector, float, dict[str, ExternalAnswer], dict[str, Any]] | None
            accepted = None
            if not inner.converged:
                item = entry(u, inner, {})
                if base is None:
                    # §4.4: an inner failure at k = 0 passes its own outcome through.
                    return end(inner.outcome, None, inner, u)
                failure = "inner_failed"
            else:
                answers: dict[str, ExternalAnswer] = {}
                unit_entries: dict[str, Any] = {}
                r_hat = np.zeros(m2)
                rho = 0.0
                for j, unit in enumerate(units):
                    inlet = inner.inlets[unit]
                    answer = evaluate(unit, inlet)
                    answers[unit] = answer
                    if answer.status == "transient":
                        unit_entries[unit] = _unit_entry(inlet, answer, None)
                        entry(u, inner, unit_entries)
                        return end("EVALUATION_ERROR", f"{answer.code}({unit})", inner, u)
                    if answer.status == "refused":
                        unit_entries[unit] = _unit_entry(inlet, answer, None)
                        failure = f"external_refused({answer.code})"
                        break
                    terms = _unit_terms(inlet, answer, w[unit], block)
                    unit_entries[unit] = _unit_entry(inlet, answer, terms)
                    r_hat[2 * j] = terms["r_xi"] / block.scale_X
                    r_hat[2 * j + 1] = terms["r_T"] / block.scale_dT
                    rho = max(rho, float(terms["_rho"]))
                item = entry(u, inner, unit_entries)
                if failure is None:
                    item["rho"] = rho
                    accepted = (r_hat, rho, answers, item)
                elif base is None:
                    # No iterate to halve back towards: a refusal at the start ends the run.
                    return end("COUPLING_NOT_CONVERGED", failure, inner, u)
            if accepted is not None:
                break
            assert base is not None and failure is not None
            if halvings == BACKTRACKS:
                return end("COUPLING_NOT_CONVERGED", failure, inner, u)
            halvings += 1
            u = base.u + 0.5 * (u - base.u)
            item["step"] = {"kind": "backtrack", "du": [float(v) for v in u - base.u], "B": None}

        r_hat, rho, answers, item = accepted
        accepted_count += 1
        point = _Point(k=k, u=u.copy(), inner=inner, r_hat=r_hat, rho=rho)
        if rho <= 1.0:
            item["step"] = {"kind": "converged", "du": None, "B": None}
            return end("CONVERGED", None, inner, u, answers)
        if k == block.max_outer - 1:
            return end("COUPLING_NOT_CONVERGED", "max_outer", inner, u)
        rose = best is not None and rho > best.rho
        if best is not None and rose and k >= 2 * m2:
            if reset_last:
                return end("COUPLING_NOT_CONVERGED", "no_decrease", inner, u)
            b_matrix = -np.eye(m2)
            step_from, kind, reset_last = best, "reset", True
        else:
            # §14.5 D5 (R-305): a rise inside the first 2n iterations (n = 2m, Gay's bound for
            # Broyden on an affine map) does not reset; B is updated as usual and the best
            # iterate does not move.
            if base is not None:
                du = point.u - base.u
                denominator = float(du @ du)
                if denominator == 0.0:
                    # A zero secant step (a step clipped back onto its base): the update is
                    # undefined.
                    return end("COUPLING_NOT_CONVERGED", "broyden_singular", inner, u)
                b_matrix = b_matrix + np.outer((point.r_hat - base.r_hat) - b_matrix @ du, du) / (
                    denominator
                )
            if not rose:
                best = point
            step_from, kind, reset_last = point, "broyden", False
        try:
            step = np.linalg.solve(b_matrix, -step_from.r_hat)
        except np.linalg.LinAlgError:
            return end("COUPLING_NOT_CONVERGED", "broyden_singular", inner, u)
        if not np.all(np.isfinite(step)):
            return end("COUPLING_NOT_CONVERGED", "broyden_singular", inner, u)
        u_next = np.clip(step_from.u + step, lower, upper)
        item["step"] = {
            "kind": kind,
            "du": [float(v) for v in u_next - step_from.u],
            "B": [[float(v) for v in row] for row in b_matrix],
        }
        base = step_from
        u = u_next
        k += 1
