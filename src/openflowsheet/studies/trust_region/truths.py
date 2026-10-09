"""Truth adapters and the finite-difference policy `M05-fd-v2` (M05 design note §6.4, §6.5,
§16.4, §17.2; ADR 0038 D3, D5; R-262, R-265, R-297).

A truth is the expensive model behind an external link: the seven process-inlet coordinates
w = (n_H₂, n_N₂, n_NH₃, n_Ar, n_CH₄, T, P) in, the coupling coordinates (X, ΔT) out (ADR 0034
D1-D2). `holders.TruthBox` puts one behind an `EFHolder`, which memoizes, budgets and ledgers every
request; nothing here keeps a ledger of its own.

**The `meta` contract (§16.4).** Every `evaluate` returns, beside (X, ΔT), a mapping with at least
`{status, cache_hit, experiment_key, executions, extrapolated}`:

- `ParentExperimentTruth` maps M02's `ExperimentOutcome` exactly: `status` is the envelope's
  `status` (`ok`, `out_of_domain`, `not_converged`, `unsupported`, `error`), `cache_hit` the
  outcome's, `experiment_key` its key, `executions` the attempts this call wrote (M02 §3.3: 0 on a
  store hit), `extrapolated` whether the envelope's `domain_status` is `extrapolated`. It adds
  `code`, the envelope's reason, which a refusal carries as its reason.
- A truth that is not a parent experiment (a surrogate, an in-process test function) returns
  `in_process_meta()`: `ok`, no cache hit, no key, no execution, not extrapolated. It is never an
  experiment, so it never counts against a parent budget (`holders.TruthBox.parent`).

**(X, ΔT) from an experiment.** M02's boundary projects the raw outlet onto the reaction
(`models.c1.boundary.project`, the least-squares extent): X = ξ_E / n_N₂,in and
ΔT = T_E − T_in, ADR 0034 D1's coupling coordinates, read from the envelope as it stands. Nothing
here re-projects.

**`M05-fd-v2` (§6.5, §17.2)**, for a truth without a gradient: forward differences in w, step
h_j = η·max(|w_j|, f_j) with f_n = 10⁻³·Σn, f_T = 1 K, f_P = 10⁵ Pa and η = 2⁻¹⁴; the perturbed
coordinate is w_j′ = fl(w_j + h_j) and the quotient uses h_eff = w_j′ − w_j, exact in binary64;
the +h side unless w′ leaves the truth's hard domain (judged before any request), then −h, and if
both leave it `TruthRefused("fd_no_admissible_side", <coordinate>)`. The seven points are requested
through the holder (so each is memoized, budgeted and ledgered) on a thread pool of
min(7, physical cores − 1) workers, after the base point, so M02's handshake precedes the batch.
`gradient_check` is the policy's once-per-study quality check (§17.2, R-297, replacing v1's η
against η/4): three steps η/4, η, 4η on one side per column, a truncation estimate and a noise
estimate from their differences, and escalation of η for noise only. Truncation is bounded in
advance by the step (the FD model's optimum moves by about ½h_j); noise is what it measures.

FD values are optimizer internals, never sensitivities (§6.9).

This module imports neither Pyomo nor the reactor's environment: it runs in the default gate.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from openflowsheet.adapters.experiments.runner import ExperimentOutcome, ExperimentRunner
from openflowsheet.adapters.variants import Variant, hard_domain
from openflowsheet.models.c1.boundary import hard_domain_violations, state_space_violation
from openflowsheet.studies.trust_region.holders import (
    FDCHECK_POINT,
    PARENT_EXPERIMENT,
    EFHolder,
    TruthRefused,
)
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS

__all__ = [
    "ETA",
    "FD_POLICY_ID",
    "PARENT_EXPERIMENT",
    "ForwardDifference",
    "GradientCheck",
    "ParentExperimentTruth",
    "fd_workers",
    "gradient_check",
    "in_process_meta",
    "physical_cores",
]

FD_POLICY_ID: Final = "M05-fd-v2"
#: §6.5: η = 2⁻¹⁴ (≈ 6.1e-5).
ETA: Final = 2.0**-14
#: §17.2: the check's steps η/4, η, 4η and its escalation η ← 4η, at most twice (2⁻¹⁴, 2⁻¹², 2⁻¹⁰).
ETA_GROWTH: Final = 4.0
ETA_ESCALATIONS: Final = 2
#: §17.2: the registered allowance on ν̂ (and, for `clean`, on τ̂): 10⁻³ · max(1, ‖G(η)‖_∞).
CHECK_TOLERANCE: Final = 1e-3
#: §17.2: τ̂ = (4/3)·‖G(η) − G(η/4)‖_∞ and ν̂ = ‖G(4η) − 5·G(η) + 4·G(η/4)‖_∞ / 14.
TRUNCATION_FACTOR: Final = 4.0 / 3.0
NOISE_DIVISOR: Final = 14.0
#: §17.2: escalation continues only while ν̂ falls by at least a factor 2 per step.
NOISE_DECREASE: Final = 2.0
#: §17.2: the check's classes.
CLEAN: Final = "clean"
TRUNCATION_DOMINATED: Final = "truncation_dominated"
NOISE_DOMINATED: Final = "noise_dominated"
#: §6.5's floors f_j: f_n = 10⁻³ Σn (relative to the inlet's total flow), f_T = 1 K, f_P = 10⁵ Pa.
FLOW_FLOOR_REL: Final = 1e-3
TEMPERATURE_FLOOR_K: Final = 1.0
PRESSURE_FLOOR_PA: Final = 1e5
#: §6.5: at most seven FD workers (one per coordinate).
MAX_FD_WORKERS: Final = 7
#: The inlet's length and order: (n_H₂, n_N₂, n_NH₃, n_Ar, n_CH₄, T, P) (§6.1, ADR 0038 D3).
INLET_SIZE: Final = len(COMPONENTS) + 2
COORDINATES: Final = (*(f"n_{name}" for name in COMPONENTS), "T", "P")
_N2: Final = COMPONENTS.index("N2")
Matrix = tuple[tuple[float, ...], ...]


def in_process_meta() -> dict[str, Any]:
    """§16.4's `meta` of a truth that is not a parent experiment: a usable value, never cached,
    no experiment, no execution, not extrapolated."""
    return {
        "status": "ok",
        "cache_hit": False,
        "experiment_key": None,
        "executions": 0,
        "extrapolated": False,
    }


def physical_cores() -> int:
    """The host's physical cores (R-250's concurrency cap): distinct core sibling sets on Linux,
    else the logical count."""
    topology = Path("/sys/devices/system/cpu")
    siblings = {
        path.read_text(encoding="utf-8").strip()
        for path in topology.glob("cpu[0-9]*/topology/core_cpus_list")
    }
    return len(siblings) or (os.cpu_count() or 1)


def fd_workers() -> int:
    """§6.5: min(7, physical cores − 1), and at least one."""
    return max(1, min(MAX_FD_WORKERS, physical_cores() - 1))


# -- the finite-difference policy ------------------------------------------------------------------


@dataclass
class ForwardDifference:
    """`M05-fd-v2` for one truth: the step rule, the side rule against the truth's hard domain,
    and the worker count. `eta` is the policy's η; `gradient_check` may escalate it, and pins the
    sides it chose at w₀ (`pinned_sides`), so the basis gradient there is its G(η)."""

    #: The truth's hard-domain predicate on a whole inlet w, judged before any request.
    admissible: Callable[[tuple[float, ...]], bool]
    eta: float = ETA
    workers: int = field(default_factory=fd_workers)
    #: §17.2: the per-column sides `gradient_check` chose at an inlet (keyed by its exact w).
    pinned_sides: dict[tuple[float, ...], tuple[int, ...]] = field(default_factory=dict)

    def floors(self, w: Sequence[float]) -> tuple[float, ...]:
        """f_j: 10⁻³ Σn for each flow, 1 K, 10⁵ Pa."""
        flow = FLOW_FLOOR_REL * math.fsum(w[: len(COMPONENTS)])
        return (*(flow,) * len(COMPONENTS), TEMPERATURE_FLOOR_K, PRESSURE_FLOOR_PA)

    def sides(self, w: Sequence[float], eta: float) -> tuple[int, ...]:
        """Each coordinate's side at step η: +1 unless w_j + h_j leaves the hard domain, then −1.
        Raises `TruthRefused("fd_no_admissible_side", <coordinate>)` when neither side is
        admissible."""
        base = self._base(w)
        found = []
        for j, floor in enumerate(self.floors(base)):
            h = eta * max(abs(base[j]), floor)
            for side, moved in ((1, base[j] + h), (-1, base[j] - h)):
                if self.admissible((*base[:j], moved, *base[j + 1 :])):
                    found.append(side)
                    break
            else:
                raise TruthRefused(
                    "fd_no_admissible_side", COORDINATES[j], f"w = {base!r}, h = {h!r}"
                )
        return tuple(found)

    def points(
        self,
        w: Sequence[float],
        eta: float | None = None,
        sides: Sequence[int] | None = None,
    ) -> tuple[tuple[float, ...], ...]:
        """The seven perturbed inlets, coordinate j moved by ±h_j: on `sides` if given, else on
        the sides `gradient_check` pinned at this exact w, else by the side rule at this step (the
        +h side unless it leaves the hard domain). Raises `TruthRefused("fd_no_admissible_side",
        <coordinate>)` when the side is not admissible (neither side, for the side rule)."""
        step = self.eta if eta is None else eta
        base = self._base(w)
        chosen = tuple(sides) if sides is not None else self.pinned_sides.get(base)
        if chosen is None:
            chosen = self.sides(base, step)
        found = []
        for j, floor in enumerate(self.floors(base)):
            h = step * max(abs(base[j]), floor)
            moved = base[j] + h if chosen[j] > 0 else base[j] - h
            point = (*base[:j], moved, *base[j + 1 :])
            if not self.admissible(point):
                raise TruthRefused(
                    "fd_no_admissible_side", COORDINATES[j], f"w = {base!r}, h = {h!r}"
                )
            found.append(point)
        return tuple(found)

    @staticmethod
    def _base(w: Sequence[float]) -> tuple[float, ...]:
        base = tuple(float(value) for value in w)
        if len(base) != INLET_SIZE:
            raise ValueError(f"an inlet has {INLET_SIZE} coordinates, got {len(base)}")
        return base

    @staticmethod
    def quotients(
        w: Sequence[float],
        base: Sequence[float],
        points: Sequence[Sequence[float]],
        values: Sequence[Sequence[float]],
    ) -> tuple[tuple[float, ...], ...]:
        """The forward-difference Jacobian (n_out × 7): (f_k(w′) − f_k(w)) / h_eff, with
        h_eff = w_j′ − w_j exact in binary64."""
        columns = []
        for j, (point, value) in enumerate(zip(points, values, strict=True)):
            h_eff = point[j] - w[j]
            columns.append([(value[k] - base[k]) / h_eff for k in range(len(base))])
        return tuple(tuple(columns[j][k] for j in range(len(columns))) for k in range(len(base)))


# -- the parent experiment ------------------------------------------------------------------------


class ParentExperimentTruth:
    """The parent reactor through M02's `ExperimentRunner` (§6.4): one `run` on the exact inlet,
    (X, ΔT) from the envelope's projected extent and outlet temperature, the `meta` of
    `ExperimentOutcome` (module docstring), and a gradient only by `M05-fd-v2` through the
    holder (`finite_difference`).

    One runner per study: M02's frozen identity (ADR 0034 D5) then covers every request, and a
    changed fingerprint is a refusal (`error`, `external_environment_changed`)."""

    def __init__(
        self,
        runner: ExperimentRunner,
        variant: Variant,
        n_tubes: float,
        components: Sequence[str] = COMPONENTS,
        *,
        eta: float = ETA,
        workers: int | None = None,
    ) -> None:
        if tuple(components) != COMPONENTS:
            raise ValueError(f"a C1 truth takes {list(COMPONENTS)}, got {list(components)}")
        self.runner = runner
        self.variant = variant
        self.n_tubes = float(n_tubes)
        self.components = tuple(components)
        self._domain = hard_domain(variant)
        self.finite_difference: ForwardDifference | None = ForwardDifference(
            self.admissible, eta, fd_workers() if workers is None else workers
        )

    def describe(self) -> Mapping[str, Any]:
        return {
            "kind": PARENT_EXPERIMENT,
            "id": self.variant.variant_id,
            "sha256": self.variant.sha256,
            "synthetic": self.variant.synthetic,
            "gradient": "finite_difference" if self.finite_difference else "analytic",
        }

    def stream(self, inlet: Sequence[float]) -> StreamState:
        n = len(self.components)
        return StreamState(
            n=tuple(float(value) for value in inlet[:n]),
            temperature=float(inlet[n]),
            pressure=float(inlet[n + 1]),
        )

    def admissible(self, inlet: Sequence[float]) -> bool:
        """The variant's hard domain (ADR 0034 D10), as the boundary judges it: inside the state
        space and violating no hard-domain bound."""
        state = self.stream(inlet)
        if state_space_violation(state) is not None:
            return False
        return not hard_domain_violations(state, self._domain, self.n_tubes)

    def run(self, inlet: Sequence[float]) -> ExperimentOutcome:
        return self.runner.run(self.variant, self.stream(inlet), self.components, self.n_tubes)

    def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]:
        state = self.stream(inlet)
        outcome = self.run(inlet)
        return coupling_coordinates(state, outcome)

    def gradient(self, inlet: Sequence[float]) -> Sequence[Sequence[float]]:
        raise TypeError(
            f"{self.variant.variant_id}: a parent experiment has no gradient of its own; the "
            f"holder forms it by {FD_POLICY_ID}"
        )


def outcome_meta(outcome: ExperimentOutcome) -> dict[str, Any]:
    """§16.4's `meta` of one M02 outcome (module docstring)."""
    envelope = outcome.envelope
    return {
        "status": str(envelope["status"]),
        "cache_hit": bool(outcome.cache_hit),
        "experiment_key": outcome.key,
        "executions": len(outcome.attempts),
        "extrapolated": envelope.get("domain_status") == "extrapolated",
        "code": str(envelope.get("code", "")),
    }


def coupling_coordinates(
    inlet: StreamState, outcome: ExperimentOutcome
) -> tuple[float, float, dict[str, Any]]:
    """(X, ΔT, meta) of one outcome: X = ξ_E / n_N₂,in and ΔT = T_E − T_in from an `ok`
    envelope (ADR 0034 D1-D2), NaN for both otherwise — a non-`ok` status is a refusal the holder
    raises, and never returns a value to TRF."""
    meta = outcome_meta(outcome)
    envelope = outcome.envelope
    if meta["status"] != "ok":
        return math.nan, math.nan, meta
    outlet = envelope["outlet"]
    conversion = float(envelope["xi"]) / inlet.n[_N2]
    rise = float(outlet["T"]) - inlet.temperature
    return conversion, rise, meta


# -- the gradient-quality check (§6.5, §17.2: `M05-fd-v2`) ----------------------------------------


@dataclass(frozen=True)
class GradientCheck:
    """One study's gradient-quality check at w₀ (`M05-fd-v2`, §17.2): each candidate η with its
    statistics and class, the η the study proceeds with and its class, `pass` or `fd_unstable`
    (A3), why escalation stopped, the per-column sides, the raw FD Jacobian at the selected η (the
    basis gradient at w₀) and the scaled G at every step evaluated."""

    w0: tuple[float, ...]
    candidates: tuple[Mapping[str, Any], ...]
    eta: float
    status: str
    gradient: Matrix
    sides: tuple[int, ...]
    selected_class: str
    #: Why the escalation ended: `passed`, `noise_not_falling`, `side_limit` or `exhausted`.
    stopped: str
    #: ½h_j at the selected η, by coordinate: the displacement truncation can cause (§17.2).
    half_steps: Mapping[str, float]
    #: G at every step the check evaluated, by step (η/4, η, 4η of each candidate).
    scaled: Mapping[float, Matrix] = field(default_factory=dict)

    def as_document(self) -> dict[str, Any]:
        """§17.2's `fd_check` record (G11)."""
        return {
            "policy": FD_POLICY_ID,
            "w0": list(self.w0),
            "sides": list(self.sides),
            "candidates": [dict(item) for item in self.candidates],
            "selected_eta": self.eta,
            "class": self.selected_class,
            "result": self.status,
            "stopped": self.stopped,
            "half_steps": dict(self.half_steps),
        }


def _inf_norm(matrix: Sequence[Sequence[float]]) -> float:
    return max(abs(value) for row in matrix for value in row)


def candidate_statistics(fine: Matrix, mid: Matrix, coarse: Matrix, eta: float) -> dict[str, Any]:
    """§17.2's statistics for the candidate η from G(η/4), G(η), G(4η): D₀ = G(η) − G(η/4),
    ρ = G(4η) − 5·G(η) + 4·G(η/4) (entrywise), τ̂ = (4/3)·‖D₀‖_∞, ν̂ = ‖ρ‖_∞ / 14, and the class
    against the allowance 10⁻³·max(1, ‖G(η)‖_∞): `clean` (ν̂ and τ̂ within it),
    `truncation_dominated` (ν̂ within, τ̂ not) or `noise_dominated` (ν̂ beyond it, a failure)."""
    difference = _inf_norm(
        [[m - f for m, f in zip(rm, rf, strict=True)] for rm, rf in zip(mid, fine, strict=True)]
    )
    residual = _inf_norm(
        [
            [c - 5.0 * m + 4.0 * f for c, m, f in zip(rc, rm, rf, strict=True)]
            for rc, rm, rf in zip(coarse, mid, fine, strict=True)
        ]
    )
    size = _inf_norm(mid)
    truncation = TRUNCATION_FACTOR * difference
    noise = residual / NOISE_DIVISOR
    allowance = CHECK_TOLERANCE * max(1.0, size)
    if noise > allowance:
        verdict = NOISE_DOMINATED
    elif truncation > allowance:
        verdict = TRUNCATION_DOMINATED
    else:
        verdict = CLEAN
    return {
        "eta": eta,
        "g_inf": size,
        "truncation": truncation,
        "noise": noise,
        "allowance": allowance,
        "class": verdict,
    }


def gradient_check(holder: EFHolder, w0: Sequence[float]) -> GradientCheck:
    """`M05-fd-v2` (§17.2), once per study at the start inlet w₀, through `holder` (whose box
    carries the FD policy). Every point is requested with purpose `fdcheck_point`.

    d(w₀), then forward gradients at η/4, η and 4η (η the policy's, 2⁻¹⁴), scaled
    G_kj = g_kj·m_j/s_k with m_j = max(|w_j|, f_j); each column's side is chosen once, at its
    largest step 4η·m_j, so all of a column's steps lie on one side. The candidate passes iff its
    noise estimate ν̂ is within the allowance (`candidate_statistics`). On a failure η ← 4η (at
    most twice, η ≤ 2⁻¹⁰), reusing two gradients and adding G(4η); the escalation stops when ν̂
    did not fall by at least `NOISE_DECREASE` on the last step (`noise_not_falling`: a residual
    that grows with η is curvature), or when the new largest step leaves the hard domain on a
    column's chosen side (`side_limit`). With no candidate passing, the study proceeds with the
    smallest ν̂ (the smaller η on a tie) and A3 is `fd_unstable`.

    The policy's η becomes the selected one and its sides are pinned at w₀, so the basis gradient
    at w₀ (§6.6) is the check's G at that η and its n_in requests are memo hits."""
    policy = getattr(holder.box, "finite_difference", None)
    if policy is None:
        raise ValueError(f"holder {holder.name!r}: its truth has no finite-difference policy")
    w = tuple(float(value) for value in w0)
    base = holder.request_values(w, purpose=FDCHECK_POINT)
    scale = [max(abs(value), floor) for value, floor in zip(w, policy.floors(w), strict=True)]
    first = policy.eta
    sides = policy.sides(w, ETA_GROWTH * first)
    raw: dict[float, Matrix] = {}
    scaled: dict[float, Matrix] = {}

    def evaluate(eta: float) -> None:
        points = policy.points(w, eta, sides)
        values = holder.request_batch(points, purpose=FDCHECK_POINT, workers=policy.workers)
        raw[eta] = policy.quotients(w, base, points, values)
        scaled[eta] = tuple(
            tuple(raw[eta][k][j] * scale[j] / holder.scales[k] for j in range(len(w)))
            for k in range(len(raw[eta]))
        )

    for eta in (first / ETA_GROWTH, first, first * ETA_GROWTH):
        evaluate(eta)
    candidates: list[dict[str, Any]] = []
    eta = first
    stopped = "exhausted"
    for escalation in range(ETA_ESCALATIONS + 1):
        candidates.append(
            candidate_statistics(
                scaled[eta / ETA_GROWTH], scaled[eta], scaled[eta * ETA_GROWTH], eta
            )
        )
        if candidates[-1]["class"] != NOISE_DOMINATED:
            stopped = "passed"
            break
        if escalation == ETA_ESCALATIONS:
            break
        if len(candidates) > 1 and not (
            candidates[-1]["noise"] * NOISE_DECREASE <= candidates[-2]["noise"]
        ):
            stopped = "noise_not_falling"
            break
        largest = eta * ETA_GROWTH * ETA_GROWTH
        try:
            policy.points(w, largest, sides)
        except TruthRefused:
            stopped = "side_limit"
            break
        eta *= ETA_GROWTH
        evaluate(eta * ETA_GROWTH)
    if stopped == "passed":
        selected = candidates[-1]
    else:
        selected = min(candidates, key=lambda item: (item["noise"], item["eta"]))
    chosen = float(selected["eta"])
    policy.eta = chosen
    policy.pinned_sides[w] = sides
    return GradientCheck(
        w0=w,
        candidates=tuple(candidates),
        eta=chosen,
        status="pass" if stopped == "passed" else "fd_unstable",
        gradient=raw[chosen],
        sides=sides,
        selected_class=str(selected["class"]),
        stopped=stopped,
        half_steps={name: 0.5 * chosen * scale[j] for j, name in enumerate(COORDINATES)},
        scaled=dict(scaled),
    )
