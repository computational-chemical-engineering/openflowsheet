"""Truth adapters and the finite-difference policy `M05-fd-v1` (M05 design note §6.4, §6.5,
§16.4; ADR 0038 D3, D5; R-262, R-265).

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

**`M05-fd-v1` (§6.5)**, for a truth without a gradient: forward differences in w, step
h_j = η·max(|w_j|, f_j) with f_n = 10⁻³·Σn, f_T = 1 K, f_P = 10⁵ Pa and η = 2⁻¹⁴; the perturbed
coordinate is w_j′ = fl(w_j + h_j) and the quotient uses h_eff = w_j′ − w_j, exact in binary64;
the +h side unless w′ leaves the truth's hard domain (judged before any request), then −h, and if
both leave it `TruthRefused("fd_no_admissible_side", <coordinate>)`. The seven points are requested
through the holder (so each is memoized, budgeted and ledgered) on a thread pool of
min(7, physical cores − 1) workers, after the base point, so M02's handshake precedes the batch.
`gradient_check` is the policy's once-per-study quality check of η against η/4.

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

FD_POLICY_ID: Final = "M05-fd-v1"
#: §6.5: η = 2⁻¹⁴ (≈ 6.1e-5).
ETA: Final = 2.0**-14
#: §6.5: the gradient-quality check's escalation, η ← 4η at most twice (η ≤ 2⁻¹⁰).
ETA_GROWTH: Final = 4.0
ETA_ESCALATIONS: Final = 2
#: §6.5: ‖G(η) − G(η/4)‖_∞ ≤ 10⁻³ · max(1, ‖G(η)‖_∞).
CHECK_TOLERANCE: Final = 1e-3
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
    """`M05-fd-v1` for one truth: the step rule, the side rule against the truth's hard domain,
    and the worker count. `eta` is the policy's η; `gradient_check` may escalate it."""

    #: The truth's hard-domain predicate on a whole inlet w, judged before any request.
    admissible: Callable[[tuple[float, ...]], bool]
    eta: float = ETA
    workers: int = field(default_factory=fd_workers)

    def floors(self, w: Sequence[float]) -> tuple[float, ...]:
        """f_j: 10⁻³ Σn for each flow, 1 K, 10⁵ Pa."""
        flow = FLOW_FLOOR_REL * math.fsum(w[: len(COMPONENTS)])
        return (*(flow,) * len(COMPONENTS), TEMPERATURE_FLOOR_K, PRESSURE_FLOOR_PA)

    def points(self, w: Sequence[float], eta: float | None = None) -> tuple[tuple[float, ...], ...]:
        """The seven perturbed inlets, coordinate j moved by ±h_j (the +h side unless it leaves
        the hard domain). Raises `TruthRefused("fd_no_admissible_side", <coordinate>)` when
        neither side is admissible."""
        step = self.eta if eta is None else eta
        base = tuple(float(value) for value in w)
        if len(base) != INLET_SIZE:
            raise ValueError(f"an inlet has {INLET_SIZE} coordinates, got {len(base)}")
        found = []
        for j, floor in enumerate(self.floors(base)):
            h = step * max(abs(base[j]), floor)
            for moved in (base[j] + h, base[j] - h):
                point = (*base[:j], moved, *base[j + 1 :])
                if self.admissible(point):
                    found.append(point)
                    break
            else:
                raise TruthRefused(
                    "fd_no_admissible_side", COORDINATES[j], f"w = {base!r}, h = {h!r}"
                )
        return tuple(found)

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
    `ExperimentOutcome` (module docstring), and a gradient only by `M05-fd-v1` through the
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


# -- the gradient-quality check (§6.5) ------------------------------------------------------------


@dataclass(frozen=True)
class GradientCheck:
    """One study's gradient-quality check at w₀: each comparison (η against η/4, the scaled ∞-norms
    and the verdict), the η the study proceeds with, and `pass` or `fd_unstable` (A3)."""

    w0: tuple[float, ...]
    comparisons: tuple[Mapping[str, Any], ...]
    eta: float
    status: str
    gradient: tuple[tuple[float, ...], ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "policy": FD_POLICY_ID,
            "w0": list(self.w0),
            "comparisons": [dict(item) for item in self.comparisons],
            "eta": self.eta,
            "status": self.status,
        }


def gradient_check(holder: EFHolder, w0: Sequence[float]) -> GradientCheck:
    """§6.5, once per study at the start inlet w₀, through `holder` (whose box carries the FD
    policy): G(η) against G(η/4), scaled G_kj = g_kj·max(|w_j|, f_j)/s_k; it passes iff
    ‖G(η) − G(η/4)‖_∞ ≤ 10⁻³·max(1, ‖G(η)‖_∞). On failure η ← 4η, at most twice; if it still
    fails the study proceeds with the last η and A3 is `fd_unstable`. The policy's η is set to
    the η it proceeds with, so the basis and the first run reuse G(η)'s points (memo or store
    hits). Every point is requested with purpose `fdcheck_point`."""
    policy = getattr(holder.box, "finite_difference", None)
    if policy is None:
        raise ValueError(f"holder {holder.name!r}: its truth has no finite-difference policy")
    w = tuple(float(value) for value in w0)
    base = holder.request_values(w, purpose=FDCHECK_POINT)
    scale = [max(abs(value), floor) for value, floor in zip(w, policy.floors(w), strict=True)]

    def gradients(eta: float) -> tuple[Matrix, Matrix]:
        """The raw FD Jacobian at step η, and its scaled form G."""
        points = policy.points(w, eta)
        values = holder.request_batch(points, purpose=FDCHECK_POINT, workers=policy.workers)
        raw = policy.quotients(w, base, points, values)
        return raw, tuple(
            tuple(raw[k][j] * scale[j] / holder.scales[k] for j in range(len(w)))
            for k in range(len(raw))
        )

    def norm(matrix: Sequence[Sequence[float]]) -> float:
        return max(abs(value) for row in matrix for value in row)

    eta = policy.eta
    raw, coarse = gradients(eta)
    fine = gradients(eta / 4.0)[1]
    comparisons: list[dict[str, Any]] = []
    for escalation in range(ETA_ESCALATIONS + 1):
        difference = norm(
            [
                [a - b for a, b in zip(row, other, strict=True)]
                for row, other in zip(coarse, fine, strict=True)
            ]
        )
        size = norm(coarse)
        passed = difference <= CHECK_TOLERANCE * max(1.0, size)
        comparisons.append(
            {
                "eta": eta,
                "eta_fine": eta / 4.0,
                "difference_inf": difference,
                "g_inf": size,
                "passed": passed,
            }
        )
        if passed or escalation == ETA_ESCALATIONS:
            break
        eta, fine = eta * ETA_GROWTH, coarse
        raw, coarse = gradients(eta)
    policy.eta = eta
    return GradientCheck(
        w0=w,
        comparisons=tuple(comparisons),
        eta=eta,
        status="pass" if comparisons[-1]["passed"] else "fd_unstable",
        gradient=raw,
    )
