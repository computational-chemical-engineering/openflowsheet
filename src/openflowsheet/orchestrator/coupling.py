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
from typing import Any, Final, Literal, NamedTuple

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
    #: ADR 0070 D6: the result's exported start profile (a start-capable variant's `ok`), the
    #: next experiment's start for that unit; `None` otherwise.
    profile_sha256: str | None = None


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
    initial: Mapping[str, tuple[float, float]] | None = None,
) -> CouplingRun:
    """§4.3's iteration over `units` under one coupling `block` (every unit's variant carries the
    same one; the caller checks). `solve_inner(w, start)` solves the inner problem at w — `start`
    is `None` at k = 0 (the route's initializer chain) and otherwise the inner solution of the
    iterate the step was taken from; `evaluate(unit, inlet)` runs one experiment. `on_iteration(k,
    max_outer)` is called at the start of each outer iteration.

    `initial` (ADR 0070 D3, X02 design note §5.4) is a declared w₀, `(X, ΔT)` by unit, already
    checked and projected into the bounds by the caller; `None` starts from `block.initial`. The
    Broyden matrix starts at −I either way."""
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
    start = (
        [value for _ in units for value in block.initial]
        if initial is None
        else [value for unit in units for value in initial[unit]]
    )
    run = _Outer(
        units=units,
        block=block,
        solve_inner=solve_inner,
        evaluate=evaluate,
        scales=scales,
        lower=lower,
        upper=upper,
        m2=m2,
        u=np.array(start, dtype=np.float64) / scales,
        b_matrix=-np.eye(m2),
    )

    while True:
        if on_iteration is not None:
            on_iteration(run.k, block.max_outer)
        trial = run._trial()
        if isinstance(trial, CouplingRun):
            return trial
        inner, r_hat, rho, answers, item = trial
        run.accepted_count += 1
        point = _Point(k=run.k, u=run.u.copy(), inner=inner, r_hat=r_hat, rho=rho)
        if rho <= 1.0:
            item["step"] = {"kind": "converged", "du": None, "B": None}
            return run.end("CONVERGED", None, inner, run.u, answers)
        if run.k == block.max_outer - 1:
            return run.end("COUPLING_NOT_CONVERGED", "max_outer", inner, run.u)
        rose = run.best is not None and rho > run.best.rho
        if run.best is not None and rose and run.k >= 2 * m2:
            if run.reset_last:
                return run.end("COUPLING_NOT_CONVERGED", "no_decrease", inner, run.u)
            run.b_matrix = -np.eye(m2)
            step_from, kind, run.reset_last = run.best, "reset", True
        else:
            # §14.5 D5 (R-305): a rise inside the first 2n iterations (n = 2m, Gay's bound for
            # Broyden on an affine map) does not reset; B is updated as usual and the best
            # iterate does not move.
            if run.base is not None:
                du = point.u - run.base.u
                denominator = float(du @ du)
                if denominator == 0.0:
                    # A zero secant step (a step clipped back onto its base): the update is
                    # undefined.
                    return run.end("COUPLING_NOT_CONVERGED", "broyden_singular", inner, run.u)
                run.b_matrix = run.b_matrix + np.outer(
                    (point.r_hat - run.base.r_hat) - run.b_matrix @ du, du
                ) / (denominator)
            if not rose:
                run.best = point
            step_from, kind, run.reset_last = point, "broyden", False
        try:
            step = np.linalg.solve(run.b_matrix, -step_from.r_hat)
        except np.linalg.LinAlgError:
            return run.end("COUPLING_NOT_CONVERGED", "broyden_singular", inner, run.u)
        if not np.all(np.isfinite(step)):
            return run.end("COUPLING_NOT_CONVERGED", "broyden_singular", inner, run.u)
        u_next = np.clip(step_from.u + step, lower, upper)
        item["step"] = {
            "kind": kind,
            "du": [float(v) for v in u_next - step_from.u],
            "B": [[float(v) for v in row] for row in run.b_matrix],
        }
        run.base = step_from
        run.u = u_next
        run.k += 1


@dataclass
class _Outer:
    """One `couple` call's outer iteration: the frame its trials and updates read, and the state
    that crosses iterations (the iterate `u`, the Broyden matrix, the best and base points, the
    reset flag, `k`, the accepted count and the record)."""

    units: Sequence[str]
    block: CouplingBlock
    solve_inner: InnerSolver
    evaluate: Evaluate
    scales: Vector
    lower: Vector
    upper: Vector
    m2: int
    u: Vector
    b_matrix: Vector
    best: _Point | None = None
    base: _Point | None = None  # the iterate the current step was taken from
    reset_last: bool = False
    k: int = 0
    accepted_count: int = 0
    record: list[dict[str, Any]] = field(default_factory=list)

    def _trial(self) -> _Trial | CouplingRun:
        """§4.3's trial at `u` (`_trial_at_u`), halved back towards `base` on a failure, at most
        `BACKTRACKS` times; each halving writes `u` and the failed entry's backtrack step.
        Returns the accepted trial, or the run's end: `_trial_at_u`'s, or the failure after the
        last halving."""
        halvings = 0
        while True:  # the trial at u, halved back towards `base` on a failure
            tried = self._trial_at_u()
            if not isinstance(tried, _FailedTrial):
                return tried
            failure, inner, item = tried
            assert self.base is not None and failure is not None
            if halvings == BACKTRACKS:
                return self.end("COUPLING_NOT_CONVERGED", failure, inner, self.u)
            halvings += 1
            self.u = self.base.u + 0.5 * (self.u - self.base.u)
            item["step"] = {
                "kind": "backtrack",
                "du": [float(v) for v in self.u - self.base.u],
                "B": None,
            }

    def _trial_at_u(self) -> _Trial | CouplingRun | _FailedTrial:
        """One trial at `u`: the inner solve at w (`solve_inner`, from the base's inner solution)
        and, when it converged, the units' experiments (`_experiments`); writes the trial's entry
        into `record` (`entry`). Returns the accepted trial; the run's end on an inner failure
        at k = 0, a transient answer (`EVALUATION_ERROR`) or a refusal with no base to halve
        towards; else the failed trial, to be halved back."""
        w = _w_of(self.u, self.units, self.scales)
        inner = self.solve_inner(w, None if self.base is None else self.base.inner.state)
        failure: str | None = None
        if not inner.converged:
            item = self.entry(self.u, inner, {})
            if self.base is None:
                # §4.4: an inner failure at k = 0 passes its own outcome through.
                return self.end(inner.outcome, None, inner, self.u)
            failure = "inner_failed"
        else:
            answers, unit_entries, r_hat, rho, failure, transient = _experiments(
                self.units, inner, self.evaluate, w, self.block
            )
            if transient is not None:
                self.entry(self.u, inner, unit_entries)
                return self.end("EVALUATION_ERROR", transient, inner, self.u)
            item = self.entry(self.u, inner, unit_entries)
            if failure is None:
                item["rho"] = rho
                return _Trial(inner, r_hat, rho, answers, item)
            elif self.base is None:
                # No iterate to halve back towards: a refusal at the start ends the run.
                return self.end("COUPLING_NOT_CONVERGED", failure, inner, self.u)
        return _FailedTrial(failure, inner, item)

    def entry(
        self, u_at: Vector, inner: InnerSolve, unit_entries: Mapping[str, Any]
    ) -> dict[str, Any]:
        w_at = u_at * self.scales
        item: dict[str, Any] = {
            "k": self.k,
            "w": [float(value) for value in w_at],
            "u": [float(value) for value in u_at],
            "inner": inner.as_document(),
            "units": dict(unit_entries),
            "rho": None,
            "step": {"kind": "none", "du": None, "B": None},
        }
        self.record.append(item)
        return item

    def end(
        self,
        outcome: str,
        reason: str | None,
        final: InnerSolve | None,
        u_at: Vector,
        answers: Mapping[str, ExternalAnswer] | None = None,
    ) -> CouplingRun:
        return CouplingRun(
            outcome=outcome,
            reason=reason,
            iterations=tuple(self.record),
            final=final,
            w=_w_of(u_at, self.units, self.scales),
            answers=dict(answers or {}),
            outer_iterations=self.accepted_count,
        )


class _Trial(NamedTuple):
    """An accepted trial: its converged inner solve, r̂ and ρ over the units, their answers, and
    its record entry (its `step` still to be written)."""

    inner: InnerSolve
    r_hat: Vector
    rho: float
    answers: dict[str, ExternalAnswer]
    item: dict[str, Any]


class _FailedTrial(NamedTuple):
    """A trial that failed (the inner solve or a unit's refusal) with a base to halve back
    towards: the failure, its inner solve and its record entry."""

    failure: str
    inner: InnerSolve
    item: dict[str, Any]


class _Experiments(NamedTuple):
    """One trial's experiments, in unit order up to the first unit whose answer was refused or
    transient: the answers and record entries by unit, and r̂ and ρ over the units that
    answered."""

    answers: dict[str, ExternalAnswer]
    entries: dict[str, Any]
    r_hat: Vector
    rho: float
    #: The trial's failure, `external_refused(<code>)`, when a unit refused.
    refused: str | None
    #: `EVALUATION_ERROR`'s reason, `<code>(<unit>)`, when a unit's answer was transient.
    transient: str | None


def _experiments(
    units: Sequence[str],
    inner: InnerSolve,
    evaluate: Evaluate,
    w: Mapping[str, tuple[float, float]],
    block: CouplingBlock,
) -> _Experiments:
    """Runs `evaluate` on each unit at the converged inner solve `inner`, in unit order, up to the
    first refused or transient answer. Writes no record: `couple` writes the trial's entry and
    ends the run on a transient answer."""
    answers: dict[str, ExternalAnswer] = {}
    unit_entries: dict[str, Any] = {}
    r_hat = np.zeros(2 * len(units))
    rho = 0.0
    for j, unit in enumerate(units):
        inlet = inner.inlets[unit]
        answer = evaluate(unit, inlet)
        answers[unit] = answer
        if answer.status == "transient":
            unit_entries[unit] = _unit_entry(inlet, answer, None)
            return _Experiments(answers, unit_entries, r_hat, rho, None, f"{answer.code}({unit})")
        if answer.status == "refused":
            unit_entries[unit] = _unit_entry(inlet, answer, None)
            failure = f"external_refused({answer.code})"
            return _Experiments(answers, unit_entries, r_hat, rho, failure, None)
        terms = _unit_terms(inlet, answer, w[unit], block)
        unit_entries[unit] = _unit_entry(inlet, answer, terms)
        r_hat[2 * j] = terms["r_xi"] / block.scale_X
        r_hat[2 * j + 1] = terms["r_T"] / block.scale_dT
        rho = max(rho, float(terms["_rho"]))
    return _Experiments(answers, unit_entries, r_hat, rho, None, None)
