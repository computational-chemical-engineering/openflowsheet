"""`SolvePolicy`, `SolveEvent` and `Checkpoint` — the recorded metadata of a solve.

K03 specification §12. These are the serializable types: what a run was told to do, what it did,
and where it got to. They live in the orchestrator because that is the layer that owns plans,
checkpoints and budgets (blueprint §3); the numerics layer computes and emits, and holds none of
this.

**Every field is required.** A default that can be mistaken for a declaration is the failure
`Capabilities` and `PropertyCapabilities` already avoid on their own boundaries: a policy that
did not say what merit it used should not read as though it used the usual one.

**The trace is append-only and its `sequence` strictly increases.** A trace is the evidence that
a solve did what it says, so an event that could be rewritten or reordered is not evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any, Final, Literal

from openflowsheet.compiled import PhaseSignature

#: §11.1. `PHYSICALLY_INFEASIBLE` is deliberately absent: blueprint §7.7 forbids calling a
#: failure to converge an infeasibility without independent evidence, and K03 has none.
SolveOutcome = Literal[
    "CONVERGED",
    "INITIALIZATION_FAILED",
    "SCALE_UNAVAILABLE",
    "SPECIFICATION_CONFLICT",
    "UNSUPPORTED_RANK_STRUCTURE",
    "PHASE_UPDATE_REQUIRED",
    "ACTIVE_SET_CYCLING",
    "ATTEMPTS_EXHAUSTED",
    "BUDGET_EXHAUSTED",
    "STAGNATION",
    "LINE_SEARCH_FAILED",
    "BOUND_BLOCKED",
    "LINEAR_SOLVE_FAILED",
    "INNER_SOLVE_INCONSISTENT",
    "EVALUATION_ERROR",
    # ADR 0009 D3 (T02): the recycle iteration's give-up (T02 §5.6), attempt level; and the plan
    # refused because a unit of an EO region lacks the derivatives it needs (T02 §7.4).
    "RECYCLE_STAGNATION",
    "CAPABILITY_UNAVAILABLE",
    # ADR 0005 D6 (T03): an attempt's opening state failed a compatibility check (T03 §5.1).
    "CHECKPOINT_INCOMPATIBLE",
    # ADR 0010 D7.2 (T04): the homotopy's failure to advance (T04 §4.6), the PTC core's (§7.3),
    # and the PTC mass mapping refused before any attempt (§7.2).
    "HOMOTOPY_STALLED",
    "PTC_STALLED",
    "PTC_MAPPING_INVALID",
    # ADR 0034 D3 (M02 design note §4.4): the `revision_coupled` route's outer coupling ended
    # without convergence, with a reason (`orchestrator.coupling`). A run outcome; no event of a
    # K03 core records it.
    "COUPLING_NOT_CONVERGED",
]

EventKind = Literal[
    "plan_built",
    "initializer_candidate",
    "initializer_rejected",
    "initializer_accepted",
    "attempt_opened",
    "jacobian",
    "linear_solve",
    "trial",
    "step_accepted",
    "attempt_closed",
    "solve_closed",
    # ADR 0009 D3 (T02): plan-step boundaries and recycle decisions.
    "unit_evaluated",
    "region_opened",
    "region_closed",
    "acceleration",
    "restart",
    # ADR 0010 D7.2 (T04 §4.7): one per λ-trial, the easy endpoint included.
    "homotopy_step",
]

#: `bound_blocked` and `linear_solve_failed` are the PTC core's (ADR 0010 D7.2, T04 §7.3): a
#: rejected pseudo-step is retried at a smaller one, where Newton's would end the attempt.
RejectionReason = Literal[
    "invalid_trial", "phase_update_required", "armijo", "bound_blocked", "linear_solve_failed"
]

#: Why recovery edge 3 could not run (ADR 0010 D3), on a region step's `region_closed`. The last
#: three are ADR 0015 D4's, recorded only under `eo_recovery = "homotopy_or_sequential_restart"`.
EoRecoveryUnsupported = Literal[
    "no_continuation_parameter",
    "no_restart_initializer",
    "restart_start_unchanged",
    "restart_initializer_failed",
]

#: §9.1. The phase selections an attempt freezes, in a fixed order, as `(unit_id, signature)`.
AttemptSignature = tuple[tuple[str, PhaseSignature], ...]


@dataclass(frozen=True)
class Counters:
    """§11.2. Cumulative, and carried on every event so a trace shows where a budget went.

    `property_calls` is the budgeted quantity: actual provider calls, which is exact-cache
    misses. `requested_evaluations` and `cache_hits` are recorded separately because blueprint
    §6.4 requires cost to be reported rather than folded into one number, and because a cache
    that changed the budget would make the budget depend on the cache.
    """

    property_calls: int = 0
    requested_evaluations: int = 0
    cache_hits: int = 0
    residual_calls: int = 0
    jacobian_calls: int = 0
    factorizations: int = 0

    def plus(self, **increments: int) -> Counters:
        return replace(self, **{name: getattr(self, name) + by for name, by in increments.items()})


@dataclass(frozen=True)
class LinearRecord:
    """ADR 0004 D3.1, as it appears on a `SolveEvent`."""

    residual_normalized: float
    u_diag_min_abs: float
    u_diag_max_abs: float
    nnz_l: int
    nnz_u: int


@dataclass(frozen=True)
class SolveEvent:
    """One observable decision. §12.3."""

    sequence: int
    kind: EventKind
    attempt: int
    iteration: int
    signature: AttemptSignature
    state_sha256: str
    residual_inf_unscaled: float
    merit: float
    counters: Counters
    alpha: float | None = None
    step_inf_scaled: float | None = None
    trial_status: Literal["accepted", "rejected"] | None = None
    rejection_reason: RejectionReason | None = None
    linear: LinearRecord | None = None
    inner_consistency: Mapping[str, Any] | None = None
    outcome: SolveOutcome | None = None
    message: str = ""
    # ADR 0009 D3 (T02 §5.8, §3.4, §4.4): null except on the events that define them.
    step_index: int | None = None
    #: On the one `plan_built` of an `ExecutionPlan` (ADR 0009 D3).
    step_count: int | None = None
    depth_used: int | None = None
    columns_dropped_condition: int | None = None
    columns_dropped_coefficient: int | None = None
    kappa_2: float | None = None
    gamma_inf: float | None = None
    beta_substitution: float | None = None
    oscillation_flag: bool | None = None
    restart_reason: Literal["stagnation"] | None = None
    restart_count: int | None = None
    merge_into_eo: Literal["taken", "unsupported"] | None = None
    merge_unsupported: tuple[str, str] | None = None
    # ADR 0010 D7.2 (T04 §4.7, §5.2): null except on the events that define them. λ and Δλ are
    # exact fractions written `p/q` (R0); `level_constants_sha256` is a digest, shape only.
    lambda_value: str | None = None
    delta_lambda: str | None = None
    corrector_outcome: SolveOutcome | None = None
    corrector_iterations: int | None = None
    level_constants_sha256: str | None = None
    #: On every event a homotopy corrector records: that λ-trial's index (0 for the easy
    #: endpoint). Stamped by the trace, as `step_index` is.
    homotopy_level: int | None = None
    #: On a region step's `region_closed`: whether recovery edge 3 ran (§5.2–§5.3).
    eo_recovery: Literal["taken", "unsupported"] | None = None
    eo_recovery_unsupported: EoRecoveryUnsupported | None = None
    #: ADR 0010 D7.2 (T04 §7.8): on a PTC `trial` the Δτ it was taken at, on a PTC `step_accepted`
    #: the Δτ used, the SER proposal (`None` when the stop test holds) and the clipped ratio. R1/R2
    #: under ADR 0007 D2; null on the polish trial and on every other core's events.
    pseudo_step: float | None = None
    pseudo_step_next: float | None = None
    ser_ratio: float | None = None

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "sequence": self.sequence,
            "kind": self.kind,
            "attempt": self.attempt,
            "iteration": self.iteration,
            "signature": [[unit, regime] for unit, regime in self.signature],
            "state_sha256": self.state_sha256,
            "residual_inf_unscaled": _finite_or_none(self.residual_inf_unscaled),
            "merit": _finite_or_none(self.merit),
            "counters": {
                "property_calls": self.counters.property_calls,
                "requested_evaluations": self.counters.requested_evaluations,
                "cache_hits": self.counters.cache_hits,
                "residual_calls": self.counters.residual_calls,
                "jacobian_calls": self.counters.jacobian_calls,
                "factorizations": self.counters.factorizations,
            },
            "message": self.message,
        }
        if self.alpha is not None:
            document["alpha"] = self.alpha
        if self.step_inf_scaled is not None:
            document["step_inf_scaled"] = self.step_inf_scaled
        if self.trial_status is not None:
            document["trial_status"] = self.trial_status
        if self.rejection_reason is not None:
            document["rejection_reason"] = self.rejection_reason
        if self.linear is not None:
            document["linear"] = {
                "residual_normalized": self.linear.residual_normalized,
                "u_diag_min_abs": self.linear.u_diag_min_abs,
                "u_diag_max_abs": self.linear.u_diag_max_abs,
                "nnz_L": self.linear.nnz_l,
                "nnz_U": self.linear.nnz_u,
            }
        if self.inner_consistency is not None:
            document["inner_consistency"] = dict(self.inner_consistency)
        if self.outcome is not None:
            document["outcome"] = self.outcome
        for name in (
            "step_index",
            "step_count",
            "depth_used",
            "columns_dropped_condition",
            "columns_dropped_coefficient",
            "beta_substitution",
            "oscillation_flag",
            "restart_reason",
            "restart_count",
            "merge_into_eo",
            "lambda_value",
            "delta_lambda",
            "corrector_outcome",
            "corrector_iterations",
            "level_constants_sha256",
            "homotopy_level",
            "eo_recovery",
            "eo_recovery_unsupported",
            "pseudo_step",
            "pseudo_step_next",
            "ser_ratio",
        ):
            value = getattr(self, name)
            if value is not None:
                document[name] = value
        if self.kind == "acceleration":
            # Present on every acceleration event and null on a plain step: "non-null iff
            # `depth_used ≥ 1`" (A33) is only checkable if the key is there to be null.
            document["kappa_2"] = None if self.kappa_2 is None else _finite_or_none(self.kappa_2)
            document["gamma_inf"] = (
                None if self.gamma_inf is None else _finite_or_none(self.gamma_inf)
            )
        if self.merge_unsupported is not None:
            unit, method = self.merge_unsupported
            document["merge_unsupported"] = {"unit": unit, "method": method}
        return document


def _finite_or_none(value: float) -> float | None:
    """JSON has no NaN. A quantity that does not exist at an event is `null`, never `0.0`.

    ADR 0002 D3's canonical JSON refuses a non-finite number outright, and a zero standing in
    for "there was no residual here" is the placeholder-success pattern in a trace.
    """
    return None if value != value or value in (float("inf"), float("-inf")) else value


@dataclass(frozen=True)
class EliminatedRowRecord:
    """One structurally eliminated row and the certificate that permits it (§7.2)."""

    row_id: str
    equals: tuple[tuple[str, int], ...]
    constant_mismatch: float
    tolerance: float


@dataclass(frozen=True)
class SolvePlan:
    """§12.2. Structural, built before any numerics, and reproducible from the model alone.

    Everything here is decided before a single residual is evaluated: the partition, the
    eliminations and their certificates, the scales and where they came from, the bounds and
    the initializer order. That ordering is requirement **D06** — "scales precede initialization
    acceptance" — and it is what makes the plan replayable: nothing in it depends on an iterate.
    """

    plan_id: str
    model_version: str
    constants_sha256: str
    policy_id: str
    tear_variable_ids: tuple[str, ...]
    tear_row_ids: tuple[str, ...]
    inner_variable_ids: tuple[str, ...]
    inner_row_ids: tuple[str, ...]
    eliminated_rows: tuple[EliminatedRowRecord, ...]
    column_scales: Mapping[str, float]
    row_scales: Mapping[str, float]
    scale_provenance: str
    bounds: Mapping[str, tuple[float | None, float | None]]
    signature_units: tuple[str, ...]
    initializer_chain: tuple[str, ...]
    estimates: Mapping[str, int]

    def __post_init__(self) -> None:
        if len(self.inner_row_ids) != len(self.inner_variable_ids):
            raise ValueError(
                f"the inner block is {len(self.inner_row_ids)}x{len(self.inner_variable_ids)} "
                "and not square: UNSUPPORTED_RANK_STRUCTURE"
            )
        if len(self.tear_row_ids) != len(self.tear_variable_ids):
            raise ValueError(
                f"{len(self.tear_row_ids)} tear rows for {len(self.tear_variable_ids)} tear "
                "variables"
            )

    def as_document(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "model_version": self.model_version,
            "constants_sha256": self.constants_sha256,
            "policy_id": self.policy_id,
            "tear_variable_ids": list(self.tear_variable_ids),
            "tear_row_ids": list(self.tear_row_ids),
            "inner_variable_ids": list(self.inner_variable_ids),
            "inner_row_ids": list(self.inner_row_ids),
            "eliminated_rows": [
                {
                    "row_id": row.row_id,
                    "equals": [[name, sign] for name, sign in row.equals],
                    "constant_mismatch": row.constant_mismatch,
                    "tolerance": row.tolerance,
                }
                for row in self.eliminated_rows
            ],
            "column_scales": dict(self.column_scales),
            "row_scales": dict(self.row_scales),
            "scale_provenance": self.scale_provenance,
            "bounds": {name: [lower, upper] for name, (lower, upper) in self.bounds.items()},
            "signature_units": list(self.signature_units),
            "initializer_chain": list(self.initializer_chain),
            "estimates": dict(self.estimates),
        }


@dataclass(frozen=True)
class Checkpoint:
    """§12.5. A state a solve reached, and exactly what is claimed about it.

    **K03 never writes anything but `"unverified"`**: verifying a state is K04's, and a solver
    that certified its own answer would be the injected-false-success failure blueprint §8.2
    warns about. The literal is nevertheless wider than that, because the *verifier* writes the
    other two (K04 §8.3, the one K03 field-set change that specification declares):
    `checked_partial` when a failed solve's best iterate has been run through the check set and
    carries a `CheckReport` with **no verdict word**, and `certified` only on a `candidate_root`
    and only together with a certificate id. A budget-exhausted iterate that happens to satisfy
    every check still reads as the failure it is.

    `full_state_sha256` is the hash of the **full reconstructed state**, not of the tear vector:
    `state_sha256` covers exactly the variables the solver iterated on (three, here), and K04's
    verifier needs the 47 the certificate is about. It had no writer until K04 — the Fable
    review of K03 recorded that as finding S2 — and a verifier that rebuilt the state it then
    judges would have chosen that state, so K03 emits it rather than K04 reconstructing it.
    """

    checkpoint_id: str
    attempt_index: int
    iteration: int
    variable_ids: tuple[str, ...]
    state_sha256: str
    signature: AttemptSignature
    residual_inf_unscaled: float
    merit: float
    label: Literal["partial", "candidate_root"]
    verification_scope: Literal["unverified", "checked_partial", "certified"] = "unverified"
    full_state_sha256: str | None = None
    scale_segment: int = 0
    jacobian_identity: Mapping[str, Any] | None = None
    #: ADR 0009 D4: the `ExecutionPlan` step the checkpoint was taken in; `None` for a solve run
    #: outside a plan (K03's `solve_tear` on its own).
    step_index: int | None = None
    #: ADR 0010 D7.4 (T04 §4.4): the λ of a homotopy checkpoint, `"p/q"`; `None` otherwise. A
    #: state accepted at λ < 1 is a root of a *modified* problem, so it can only be `partial` and
    #: `unverified` — enforced here and by the schema.
    continuation_lambda: str | None = None

    def __post_init__(self) -> None:
        if self.continuation_lambda not in (None, "1") and (
            self.label != "partial" or self.verification_scope != "unverified"
        ):
            raise ValueError(
                f"a checkpoint at continuation level {self.continuation_lambda} is a state of a "
                f"modified problem: it is partial and unverified, never {self.label!r}/"
                f"{self.verification_scope!r} (T04 §4.4)"
            )

    def as_document(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "attempt_index": self.attempt_index,
            "iteration": self.iteration,
            "variable_ids": list(self.variable_ids),
            "state_sha256": self.state_sha256,
            "full_state_sha256": self.full_state_sha256,
            "signature": [[unit, regime] for unit, regime in self.signature],
            "residual_inf_unscaled": self.residual_inf_unscaled,
            "merit": self.merit,
            "label": self.label,
            "verification_scope": self.verification_scope,
            "scale_segment": self.scale_segment,
            "jacobian_identity": (
                dict(self.jacobian_identity) if self.jacobian_identity is not None else None
            ),
            "step_index": self.step_index,
            "continuation_lambda": self.continuation_lambda,
        }


#: §5.9, the registered defaults. Named so a test can assert the policy was not silently widened.
REGISTERED_ARMIJO_C: Final = 1e-4
REGISTERED_STEP_HALVINGS_MAX: Final = 20
REGISTERED_STAGNATION_WINDOW: Final = 5
REGISTERED_STAGNATION_RATIO: Final = 0.99
REGISTERED_MAX_ITERATIONS: Final = 50
REGISTERED_MAX_ATTEMPTS: Final = 5
REGISTERED_MAX_PROPERTY_CALLS: Final = 10_000
REGISTERED_PHASE_WALL_PATIENCE: Final = 2
REGISTERED_ETA_INNER: Final = 1e-10
REGISTERED_ADMISSIBILITY_EPSILON: Final = 1e-12


RecycleMethod = Literal["auto", "newton_tear", "anderson", "eo"]

#: ADR 0005 D1's rule-set literals: T03's contract, and ADR 0012 D4's (T05b) second value.
PhaseContract = Literal["T03-phase-contract-v1", "T05b-phase-contract-v2"]


@dataclass(frozen=True)
class RecyclePolicy:
    """`SolvePolicy.recycle` (ADR 0009 D2): T02 §5.10's registered constants and the method.

    `method` is resolved per loop at plan time (T02 §4): `auto` is `newton_tear` when every unit
    of the loop declares exact residual derivatives and `anderson` otherwise; `eo` promotes every
    loop to an equation-oriented region. `tear_streams` optionally names a tear set that leaves
    the loop acyclic (T02 §3.3's alternate tearing). Every value is R0.
    """

    policy_id: str = "T02-recycle-policy-v1"
    method: RecycleMethod = "auto"
    depth_max: int = 5
    beta: float = 1.0
    beta_substitution: float = 1.0
    beta_substitution_oscillating: float = 0.5
    condition_max: float = 1e8
    coefficient_max: float = 1e4
    stagnation_window: int = 5
    stagnation_ratio: float = 0.99
    oscillation_window: int = 3
    max_restarts: int = 2
    max_iterations_per_attempt: int = 200
    step_halvings_max: int = 20
    tear_streams: tuple[str, ...] | None = None

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "policy_id": self.policy_id,
            "method": self.method,
            "depth_max": self.depth_max,
            "beta": self.beta,
            "beta_substitution": self.beta_substitution,
            "beta_substitution_oscillating": self.beta_substitution_oscillating,
            "condition_max": self.condition_max,
            "coefficient_max": self.coefficient_max,
            "stagnation_window": self.stagnation_window,
            "stagnation_ratio": self.stagnation_ratio,
            "oscillation_window": self.oscillation_window,
            "max_restarts": self.max_restarts,
            "max_iterations_per_attempt": self.max_iterations_per_attempt,
            "step_halvings_max": self.step_halvings_max,
        }
        if self.tear_streams is not None:
            document["tear_streams"] = list(self.tear_streams)
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> RecyclePolicy:
        """The inverse of `as_document` (T07 design note §12.3)."""
        members = _members(document, "recycle", _names(cls), optional=("tear_streams",))
        tear_streams = members.pop("tear_streams", None)
        return cls(**members, tear_streams=None if tear_streams is None else tuple(tear_streams))


def _names(cls: type) -> tuple[str, ...]:
    from dataclasses import fields

    return tuple(entry.name for entry in fields(cls))


def _members(
    document: Mapping[str, Any],
    where: str,
    names: tuple[str, ...],
    *,
    optional: tuple[str, ...] = (),
) -> dict[str, Any]:
    """`document`'s members, which must be exactly `names` (less any absent `optional` one).

    T07 design note §12.3: a rerun rebuilds its policy from the archived document, so the reader
    refuses a member it does not know or one it lacks rather than filling it from a default — a
    document that does not round-trip is not the policy it claims to be."""
    if not isinstance(document, Mapping):
        raise ValueError(f"{where}: not an object")
    unknown = sorted(set(document) - set(names))
    missing = sorted(set(names) - set(optional) - set(document))
    if unknown or missing:
        raise ValueError(f"{where}: unknown members {unknown}, missing members {missing}")
    return dict(document)


def fraction_string(value: Fraction) -> str:
    """ADR 0010 D7: an exact fraction as `"p/q"`, or `"p"` when it is an integer (`"0"`, `"1"`).

    λ and Δλ are R0 decisions, so they are written as exact strings: no float formatting enters
    a record whose bytes the K05 identity compares across architectures."""
    return str(Fraction(value))


@dataclass(frozen=True)
class HomotopyPolicy:
    """`SolvePolicy.globalization.homotopy` (ADR 0010 D1–D2; T04 §4.3's registered constants).

    Every λ the controller forms is dyadic — Δλ₀ = 1/4, growth 2, shrink 1/2 — so the fractions
    are held exactly and λ is never a float anywhere in the controller (T04 §4.2)."""

    type: Literal["specification_continuation"] = "specification_continuation"
    delta_lambda_initial: Fraction = Fraction(1, 4)
    delta_lambda_min: Fraction = Fraction(1, 1024)
    growth: int = 2
    shrink: Fraction = Fraction(1, 2)
    corrector_max_iterations: int = 10
    max_lambda_trials: int = 64

    def as_document(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "delta_lambda_initial": fraction_string(self.delta_lambda_initial),
            "delta_lambda_min": fraction_string(self.delta_lambda_min),
            "growth": self.growth,
            "shrink": fraction_string(self.shrink),
            "corrector_max_iterations": self.corrector_max_iterations,
            "max_lambda_trials": self.max_lambda_trials,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> HomotopyPolicy:
        """The inverse of `as_document`; the three fractions are read back exactly."""
        members = _members(document, "globalization.homotopy", _names(cls))
        for name in ("delta_lambda_initial", "delta_lambda_min", "shrink"):
            members[name] = Fraction(members[name])
        return cls(**members)


@dataclass(frozen=True)
class PtcPolicy:
    """`SolvePolicy.globalization.ptc` (ADR 0010 D1, D4–D5; T04 §7.7's registered constants).

    `status` is single-valued: the residence-time family is experimental in v0.1 (T04 §8), and a
    later qualification is a new value, never a silent change."""

    status: Literal["experimental"] = "experimental"
    mass_policy: Literal["T04-residence-time-v1"] = "T04-residence-time-v1"
    residence_time_s: float = 1.0
    tau_initial_s: float = 1.0
    tau_min_s: float = 1e-4
    tau_max_s: float = 1e10
    gamma_min: float = 0.2
    gamma_max: float = 2.0
    phi_floor: float = 1e-12
    retry_shrink: float = 0.5
    retries_max: int = 10
    max_steps_per_attempt: int = 200
    polish: Literal["one_newton_step"] = "one_newton_step"

    def as_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mass_policy": self.mass_policy,
            "residence_time_s": self.residence_time_s,
            "tau_initial_s": self.tau_initial_s,
            "tau_min_s": self.tau_min_s,
            "tau_max_s": self.tau_max_s,
            "gamma_min": self.gamma_min,
            "gamma_max": self.gamma_max,
            "phi_floor": self.phi_floor,
            "retry_shrink": self.retry_shrink,
            "retries_max": self.retries_max,
            "max_steps_per_attempt": self.max_steps_per_attempt,
            "polish": self.polish,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> PtcPolicy:
        """The inverse of `as_document`."""
        return cls(**_members(document, "globalization.ptc", _names(cls)))


@dataclass(frozen=True)
class GlobalizationPolicy:
    """`SolvePolicy.globalization` (ADR 0010 D1): the EO core, recovery edge 3, and the constants
    of both globalizations. Every value is R0.

    `eo_recovery = "homotopy"` is the registered default (T04 Q4/F2): a recovery edge is automatic
    by blueprint §7.7's definition. A test whose subject is the contract or a core pins `"none"`
    (T04 §11.2), so that the edge is the only thing that changed where it fires.
    `"homotopy_or_sequential_restart"` (ADR 0015 D1) adds edge 3's second action, the sequential
    restart of a revision-built region; it is never the default, so no registered policy
    document moves (design note `docs/design/T06-F4-recovery.md` §5.8). `eo_core =
    "newton_refined"` (ADR 0018 D1) is the Newton core with one terminal refinement at a
    `CONVERGED` exit whose chord correction exceeds the kind tolerance; it is never the default
    either, and every registered policy keeps `"newton"`."""

    policy_id: Literal["T04-globalization-v1"] = "T04-globalization-v1"
    eo_core: Literal["newton", "ptc", "newton_refined"] = "newton"
    eo_recovery: Literal["homotopy", "none", "homotopy_or_sequential_restart"] = "homotopy"
    eo_recovery_max_count: Literal[1] = 1
    homotopy: HomotopyPolicy = field(default_factory=HomotopyPolicy)
    ptc: PtcPolicy = field(default_factory=PtcPolicy)

    def as_document(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "eo_core": self.eo_core,
            "eo_recovery": self.eo_recovery,
            "eo_recovery_max_count": self.eo_recovery_max_count,
            "homotopy": self.homotopy.as_document(),
            "ptc": self.ptc.as_document(),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> GlobalizationPolicy:
        """The inverse of `as_document`."""
        members = _members(document, "globalization", _names(cls))
        members["homotopy"] = HomotopyPolicy.from_document(members["homotopy"])
        members["ptc"] = PtcPolicy.from_document(members["ptc"])
        return cls(**members)


@dataclass(frozen=True)
class SolvePolicy:
    """§12.1. What a solve was told to do, recorded so a run can be replayed and judged.

    The defaults are the registered constants of §5.9 and nothing else; a caller that wants
    another value passes it and it appears in the trace. `merit`, `redundant_row_policy`,
    `derivative_path` and `cycle_rule` are single-valued literals today so that a later second
    policy is a *new value* a reader can see, never a silent change of meaning.
    """

    policy_id: str
    residual_tolerances: Mapping[str, Mapping[str, float]]
    scales: Mapping[str, float]
    initializer_chain: tuple[str, ...] = ()
    merit: Literal["scaled_residual_half_norm2"] = "scaled_residual_half_norm2"
    armijo_c: float = REGISTERED_ARMIJO_C
    step_halvings_max: int = REGISTERED_STEP_HALVINGS_MAX
    stagnation_window: int = REGISTERED_STAGNATION_WINDOW
    stagnation_ratio: float = REGISTERED_STAGNATION_RATIO
    phase_wall_patience: int = REGISTERED_PHASE_WALL_PATIENCE
    max_iterations_per_attempt: int = REGISTERED_MAX_ITERATIONS
    max_attempts: int = REGISTERED_MAX_ATTEMPTS
    max_property_calls: int = REGISTERED_MAX_PROPERTY_CALLS
    linear_solver: Mapping[str, Any] = field(default_factory=dict)
    linear_residual_threshold: float = 1e-12
    eta_inner: float = REGISTERED_ETA_INNER
    admissibility_epsilon: float = REGISTERED_ADMISSIBILITY_EPSILON
    redundant_row_policy: Literal["structural_alias_elimination"] = "structural_alias_elimination"
    derivative_path: Literal["assembled_schur", "finite_difference_oracle"] = "assembled_schur"
    cycle_rule: Literal["no_repeated_signature"] = "no_repeated_signature"
    #: ADR 0005 D1 (T03): the phase-attempt rule set this solve ran under, named so that a replay
    #: under a policy that does not declare it is refused rather than run under other rules.
    #: ADR 0012 D4 (T05b) adds `T05b-phase-contract-v2` (a frozen-schema widening, approved by
    #: Frank 2026-09-25); v1 stays the default and every registered policy's.
    phase_contract: PhaseContract = "T03-phase-contract-v1"
    #: ADR 0009 D2: the recycle constants and the method, required in the document so that the
    #: policy hash covers the constants that were in force (K03 §12: no field is left to a default
    #: a reader could mistake for a declaration). The Python default is the registered policy,
    #: as every other field's is.
    recycle: RecyclePolicy = field(default_factory=RecyclePolicy)
    #: ADR 0010 D1 (T04): the EO core, recovery edge 3 and the globalization constants, required
    #: in the document for the same reason `recycle` is; a replay under a policy without it is
    #: refused (the schema requires it).
    globalization: GlobalizationPolicy = field(default_factory=GlobalizationPolicy)

    def as_document(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "residual_tolerances": {
                kind: dict(entry) for kind, entry in self.residual_tolerances.items()
            },
            "scales": dict(self.scales),
            "merit": self.merit,
            "armijo_c": self.armijo_c,
            "step_halvings_max": self.step_halvings_max,
            "stagnation_window": self.stagnation_window,
            "stagnation_ratio": self.stagnation_ratio,
            "phase_wall_patience": self.phase_wall_patience,
            "max_iterations_per_attempt": self.max_iterations_per_attempt,
            "max_attempts": self.max_attempts,
            "max_property_calls": self.max_property_calls,
            "linear_solver": dict(self.linear_solver),
            "linear_residual_threshold": self.linear_residual_threshold,
            "eta_inner": self.eta_inner,
            "admissibility_epsilon": self.admissibility_epsilon,
            "redundant_row_policy": self.redundant_row_policy,
            "derivative_path": self.derivative_path,
            "initializer_chain": list(self.initializer_chain),
            "cycle_rule": self.cycle_rule,
            "phase_contract": self.phase_contract,
            "recycle": self.recycle.as_document(),
            "globalization": self.globalization.as_document(),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> SolvePolicy:
        """The inverse of `as_document`: `from_document(d).as_document() == d` for every document
        `as_document` writes (T07 design note §12.3: a revision bundle's rerun rebuilds its policy
        from `solve-policy.json` and refuses it unless it recomputes to the manifest's hash).
        Every member is required, as the schema requires it; none is filled from a default."""
        import copy

        members = _members(document, "solve-policy", _names(cls))
        members["residual_tolerances"] = {
            kind: dict(entry) for kind, entry in members["residual_tolerances"].items()
        }
        members["scales"] = dict(members["scales"])
        members["initializer_chain"] = tuple(members["initializer_chain"])
        members["linear_solver"] = copy.deepcopy(dict(members["linear_solver"]))
        members["recycle"] = RecyclePolicy.from_document(members["recycle"])
        members["globalization"] = GlobalizationPolicy.from_document(members["globalization"])
        return cls(**members)

    def __post_init__(self) -> None:
        if not self.linear_solver:
            from openflowsheet.numerics.linear import SUPERLU_OPTIONS

            object.__setattr__(
                self,
                "linear_solver",
                {"name": "scipy.sparse.linalg.splu", **SUPERLU_OPTIONS},
            )


#: T07 design note §8.1: the running job's cooperative interruption check, called by every
#: `Trace.record` before it builds the event, so an interrupted trace ends at its last completed
#: event. It raises (`application.jobs.interrupt.JobInterrupted`, a `BaseException`) or returns.
#: Outside a job it is `None` and `record` does exactly what it did without it.
INTERRUPT_CHECK: ContextVar[Callable[[], None] | None] = ContextVar("INTERRUPT_CHECK", default=None)


class Trace:
    """An append-only list of events with a strictly increasing sequence.

    A list would do; this exists so the sequence cannot be assigned by a caller and so that
    "append-only" is a property of the type rather than a convention in a docstring.
    """

    def __init__(self, property_sampler: Callable[[], Mapping[str, int]] | None = None) -> None:
        self._events: list[SolveEvent] = []
        #: §11.2: "every `SolveEvent` carries the cumulative counters, so a trace shows where a
        #: budget went". The property counts are kept by the cache and the budget guard, not by
        #: the Newton core, so the trace samples them here rather than having every one of the
        #: thirteen `record` call sites thread them through. A trace built without a sampler
        #: leaves the three fields at whatever the caller passed, which is zero.
        self._property_sampler = property_sampler
        #: ADR 0009 D3: the plan step whose events are being recorded. The Newton and Anderson
        #: cores know nothing of plans, so the step index is stamped here, on every event between
        #: a step's opening and its closing, rather than threaded through their call sites.
        self._step: int | None = None
        #: ADR 0010 D7.2: the λ-trial whose corrector is recording, stamped like the step.
        self._level: int | None = None

    def open_level(self, index: int) -> None:
        if self._level is not None:
            raise ValueError(f"homotopy level {self._level} is still open; levels do not nest")
        self._level = index

    def close_level(self) -> None:
        self._level = None

    def open_step(self, index: int) -> None:
        if self._step is not None:
            raise ValueError(f"step {self._step} is still open; steps do not nest (T02 §3)")
        self._step = index

    def close_step(self) -> None:
        self._step = None

    def record(self, **fields: Any) -> SolveEvent:
        check = INTERRUPT_CHECK.get()
        if check is not None:
            check()
        counters = fields.get("counters")
        if self._property_sampler is not None and isinstance(counters, Counters):
            fields = {**fields, "counters": replace(counters, **dict(self._property_sampler()))}
        if self._step is not None and fields.get("step_index") is None:
            fields = {**fields, "step_index": self._step}
        if self._level is not None and fields.get("homotopy_level") is None:
            fields = {**fields, "homotopy_level": self._level}
        event = SolveEvent(sequence=len(self._events), **fields)
        self._events.append(event)
        return event

    def extend(self, events: Sequence[SolveEvent]) -> None:
        """Append events another trace recorded, re-sequenced after this one's, each otherwise
        unchanged (M02 design note §4.4: a coupled job's trace holds every inner solve's events,
        so that an interruption's partial trace keeps them). No interruption check and no
        stamping: the events were checked and stamped when they were recorded."""
        for event in events:
            self._events.append(replace(event, sequence=len(self._events)))

    @property
    def events(self) -> tuple[SolveEvent, ...]:
        return tuple(self._events)

    def of_kind(self, kind: EventKind) -> tuple[SolveEvent, ...]:
        return tuple(event for event in self._events if event.kind == kind)

    def __len__(self) -> int:
        return len(self._events)
