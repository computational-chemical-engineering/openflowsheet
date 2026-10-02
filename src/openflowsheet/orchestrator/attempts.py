"""The bounded attempt controller and the frozen phase set. K03 §9, register R-012.

Blueprint [A01]: "the active phase set belongs to the **local nonlinear attempt**, not to
individual residual calls. Freeze it for all accepted iterates, trial points, residual/Jacobian
calls, and derivative perturbations within that attempt." This is the object that makes that
structural rather than conventional — the Newton core receives an `AttemptContext` and gets its
signature and its evaluation contexts from nowhere else.

**The signature covers the flash and nothing more.** The rule is that it covers the phase
selections the *residual depends on*, and for the SYN-001 tear that is exactly the flash. The
heater outlet's regime affects `U-HEAT.Q` and the lifted split, which are dead ends of the inner
system: `S3.n = S2.n` by the mole balance, so `G(t)` does not depend on it. Freezing it anyway
has a measured cost — the nominal case's one-step landing on `t*` is then rejected as a phase
change, because `S3` flips from `TWO_PHASE` at `0.5 t*` to `LIQUID` at `t*`, and the solver
crawls to a wall it never needed to cross. M3 observed exactly that crawl on a synthetic problem
before this controller existed.

**A phase change is treated as an overshoot first.** A Newton step across a boundary with the
root on this side is the common case, so the step halves once rather than restarting; a restart
on the first crossing would cycle. The attempt ends only when the wall is *persistent*.

**The restart point is a rejected trial, not the last accepted iterate.** This is the part that
is easy to get wrong. "Restore a valid checkpoint and select a new phase set" cannot mean the
last accepted iterate here, because the traversal at that point reports the *old* signature —
restarting there would re-open the same attempt. The restart point is a phase-rejected trial of
the last line search that had one — a point already known to be inside the new regime — and,
under ADR 0005 (T03 §4.5, register R-028), the largest-`α` one whose regime is **adjacent** to the
frozen one on `LIQUID — TWO_PHASE — VAPOR`, else the largest-`α` one. The decision itself is
`phase_contract.decide`, shared with the region solve.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.canonical import state_sha256
from openflowsheet.compiled import EvaluationContext, PhaseSignature
from openflowsheet.numerics.anderson import RecycleResult, solve_recycle
from openflowsheet.numerics.newton import NewtonResult, Problem, solve_newton
from openflowsheet.orchestrator.phase_contract import (
    Candidate,
    Conversion,
    Decision,
    OpeningRefusal,
    OpeningRequirement,
    OpeningSource,
    OpeningState,
    WallObserver,
    check_opening,
    decide,
)
from openflowsheet.orchestrator.roots import root_fingerprint
from openflowsheet.orchestrator.trace import (
    AttemptSignature,
    Checkpoint,
    Counters,
    SolveOutcome,
    SolvePlan,
    SolvePolicy,
    Trace,
)

#: §9.1's fixed map from the flash's two outlet signatures to the attempt's regime. Three
#: entries, and `regime ∈ {TWO_PHASE, LIQUID, VAPOR}` — exactly what §9.1 registers.
#:
#: A fourth entry `(ZERO_FLOW, ZERO_FLOW) -> ZERO_FLOW` was here and is removed. It admitted a
#: regime the specification does not name, on a state no registered case reaches (a flash with
#: no flow at all, which needs the fresh feed to vanish), and §9.1 is explicit that dormancy is
#: not a phase selection. An unregistered regime that never fires is worse than one that does:
#: it reads as coverage. The combination is now refused, which is what an unsupported state is
#: supposed to produce.
FLASH_REGIME: Final[Mapping[tuple[str, str], PhaseSignature]] = {
    ("VAPOR", "LIQUID"): "TWO_PHASE",
    ("ZERO_FLOW", "LIQUID"): "LIQUID",
    ("VAPOR", "ZERO_FLOW"): "VAPOR",
}

SIGNATURE_UNITS: Final[tuple[str, ...]] = ("U-FLASH",)

#: ADR 0010 D7.3: the cores an attempt can run (T04 adds `ptc` and `homotopy`).
AttemptCore = Literal["newton", "anderson", "ptc", "homotopy"]


def flash_signature(vapor: str | None, liquid: str | None) -> AttemptSignature:
    """§9.1: the attempt signature of a traversal, from its two flash outlet signatures."""
    regime = FLASH_REGIME.get((vapor or "ZERO_FLOW", liquid or "ZERO_FLOW"))
    if regime is None:
        raise ValueError(
            f"the flash reported outlets ({vapor}, {liquid}), which is not one of the registered "
            f"combinations {sorted(FLASH_REGIME)}"
        )
    return (("U-FLASH", regime),)


@dataclass(frozen=True)
class AttemptContext:
    """§12.4. [A01] made structural: the one object an attempt's calls take their context from."""

    attempt_index: int
    signature: AttemptSignature
    evaluation_context: EvaluationContext
    flowsheet_context: EvaluationContext
    column_scales: Mapping[str, float]
    row_scales: Mapping[str, float]
    counters_at_open: Counters
    opened_reason: str = "initial"
    opened_from: Checkpoint | None = None
    scale_segment: int = 0
    #: ADR 0009 D4: a region attempt's active phase set (T02 §6.3.1), per lifted unit — which
    #: lifted variables were solved and which pinned at zero. `None` on a tear attempt, whose
    #: signature is the flash's reported regime and pins nothing.
    active_phases: AttemptSignature | None = None
    #: ADR 0005 D5 (T03 §5.2): `{rows, columns, nnz, sha256}` of the structural pattern of the
    #: attempt's EO block — the evidence that a phase change rebuilt it. `None` only for an attempt
    #: with no compiled problem (the bare controller's constructed seeds).
    jacobian_pattern: Mapping[str, Any] | None = None
    #: ADR 0010 D7.3 (T04): the core the attempt ran. Every construction site names it.
    core: AttemptCore = "newton"
    #: ADR 0010 D7.3: `{type, parameter_ids}` of a homotopy attempt's continuation; `None` for
    #: every other core. The attempt's `evaluation_context` is then the target's (λ = 1), and each
    #: λ-level uses a level context equal to it but for `constants_sha256` (ADR 0010 D6).
    continuation: Mapping[str, Any] | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "attempt_index": self.attempt_index,
            "signature": [[unit, regime] for unit, regime in self.signature],
            "evaluation_context": _context_document(self.evaluation_context),
            "flowsheet_context": _context_document(self.flowsheet_context),
            "column_scales": dict(self.column_scales),
            "row_scales": dict(self.row_scales),
            "scale_segment": self.scale_segment,
            "opened_reason": self.opened_reason,
            "opened_from": (
                self.opened_from.as_document() if self.opened_from is not None else None
            ),
            "counters_at_open": {
                "property_calls": self.counters_at_open.property_calls,
                "requested_evaluations": self.counters_at_open.requested_evaluations,
                "cache_hits": self.counters_at_open.cache_hits,
                "residual_calls": self.counters_at_open.residual_calls,
                "jacobian_calls": self.counters_at_open.jacobian_calls,
                "factorizations": self.counters_at_open.factorizations,
            },
            "active_phases": (
                [[unit, regime] for unit, regime in self.active_phases]
                if self.active_phases is not None
                else None
            ),
            "jacobian_pattern": (
                dict(self.jacobian_pattern) if self.jacobian_pattern is not None else None
            ),
            "core": self.core,
            "continuation": (
                _continuation_document(self.continuation) if self.continuation is not None else None
            ),
        }


def _continuation_document(continuation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in continuation.items()
    }


def _context_document(context: EvaluationContext) -> dict[str, Any]:
    """The serializable part of an `EvaluationContext`. `workspace` is inert (ADR 0008 D1.4).

    Omitting it is not a convenience: nothing the evaluated function depends on may live there,
    so a workspace in a replayed document would be a claim that it does.
    """
    return {
        "model_version": context.model_version,
        "constants_sha256": context.constants_sha256,
        "phase_signature": context.phase_signature,
        "accuracy_policy": context.accuracy_policy,
    }


@dataclass(frozen=True)
class SolveResult:
    """What a whole solve returns: the outcome, the best state, and the attempts it took."""

    outcome: SolveOutcome
    x: npt.NDArray[np.float64]
    residual_inf: float
    attempts: int
    iterations: int
    counters: Counters
    checkpoint: Checkpoint | None
    signatures: tuple[AttemptSignature, ...]
    converged: bool = False
    message: str = ""
    #: The plan this solve ran under. `None` only for the bare controller, which constructed
    #: tests drive directly and which has no flowsheet and so no plan to build.
    plan: SolvePlan | None = None
    #: K04 §3.1 and A01: the full reconstructed state the certificate is about, by variable id,
    #: and only on a converged solve. `x` is the tear vector the solver iterated on — three
    #: numbers — and a verifier needs the forty-seven. It is emitted here rather than rebuilt by
    #: the verifier because a verifier that reconstructs the state it then judges has chosen
    #: that state; the Fable review of K03 recorded its absence as finding S2.
    final_state: Mapping[str, float] | None = None
    #: T02 §4.4: the closing attempt's best iterate, when its core tracked one — the merge
    #: edge's start. `None` under `newton_tear`, which has no merge edge.
    best_x: npt.NDArray[np.float64] | None = None
    #: §12.4's context per attempt, in the order they opened. It is the authority each attempt's
    #: calls took their scales, signature and evaluation context from, so discarding it would
    #: leave a replay (K05) unable to reconstruct the attempt it is replaying.
    contexts: tuple[AttemptContext, ...] = ()
    #: ADR 0005 D7 (T03 §8.1): one item per attempt, in order — the attempt history, and the
    #: starting point in item 0.
    branch_provenance: tuple[Mapping[str, Any], ...] = ()
    #: ADR 0005 D7 (T03 §8.2): issued on a `CONVERGED` solve, `None` otherwise.
    root_fingerprint: Mapping[str, Any] | None = None


def solve_with_attempts(
    *,
    problem_for: Callable[[AttemptContext], Problem],
    x0: Sequence[float],
    signature_of: Callable[[npt.NDArray[np.float64]], AttemptSignature | None],
    policy: SolvePolicy,
    trace: Trace,
    evaluation_context: EvaluationContext,
    flowsheet_context: EvaluationContext,
    column_scales: Mapping[str, float],
    row_scales: Mapping[str, float],
    variable_ids: Sequence[str],
    method: Literal["newton_tear", "anderson"] = "newton_tear",
    jacobian_pattern: Mapping[str, Any] | None = None,
    initializer_source: str = "user_guess",
    step_index: int | None = None,
) -> SolveResult:
    """Run bounded attempts with a frozen signature each, under ADR 0005's contract.

    `method` picks the core that runs inside each attempt (T02 §4.3): K03's damped Newton on the
    tear, or T02's safeguarded Anderson recycle. Every attempt closes through
    `phase_contract.decide` — the same function the region solve calls — so the precedence, the
    restart selection (the largest-α *adjacent* phase-rejected trial, T03 §4.5), the attempt
    budget, the cycle rule and the opening checks exist once for both paths.

    `signature_of` reports the signature a point's traversal produces, or `None` if the point
    cannot be evaluated; it is how the controller learns which regime a rejected trial was in
    without the Newton core knowing anything about phases.
    """
    x = np.array([float(value) for value in x0], dtype=np.float64)
    opening = signature_of(x)
    if opening is None:
        raise ValueError("the initializer's own traversal did not complete; the chain is §10's")

    counters = Counters()
    used: list[AttemptSignature] = []
    contexts: list[AttemptContext] = []
    provenance: list[dict[str, Any]] = []
    checkpoint: Checkpoint | None = None
    last: NewtonResult | None = None
    total_iterations = 0
    message = "initial"
    source: OpeningSource = "initializer"
    trial: Candidate | None = None

    for attempt_index in range(policy.max_attempts):
        used.append(opening)
        # T03 §4.2 / `interfaces-frozen.md` §1: every attempt constructs **new** context objects
        # (field-equal on this path), so an attempt's calls are told apart from another's.
        context = AttemptContext(
            attempt_index=attempt_index,
            signature=opening,
            evaluation_context=replace(evaluation_context),
            flowsheet_context=replace(flowsheet_context),
            column_scales=column_scales,
            row_scales=row_scales,
            counters_at_open=counters,
            opened_reason="initial" if attempt_index == 0 else "phase_update",
            opened_from=checkpoint,
            jacobian_pattern=jacobian_pattern,
            core="anderson" if method == "anderson" else "newton",
        )
        contexts.append(context)
        opening_hash = state_sha256(x, variable_ids)
        trace.record(
            kind="attempt_opened",
            attempt=attempt_index,
            iteration=0,
            signature=opening,
            state_sha256=opening_hash,
            residual_inf_unscaled=float("nan"),
            merit=float("nan"),
            counters=counters,
            alpha=trial.alpha if trial is not None else None,
            message=message,
        )

        wall = WallObserver(policy)
        problem = problem_for(context)
        if method == "anderson":
            last = _anderson_as_newton_result(
                solve_recycle(
                    problem,
                    x,
                    policy=policy.recycle,
                    signature=opening,
                    observer=wall,
                    trace=trace,
                    attempt=attempt_index,
                    counters=counters,
                ),
                problem,
            )
        else:
            last = solve_newton(
                problem,
                x,
                policy,
                trace=trace,
                signature=opening,
                attempt=attempt_index,
                counters=counters,
                observer=wall,
            )
        counters = last.counters
        total_iterations += last.iterations
        # `accepted_any or converged`. A solve that converges at iteration 0 accepted no step
        # and still has a root: the point it started at *is* one. Two of the five registered
        # SYN-001 variants are like that — once-through has r = 0, so G(0) is already the
        # answer — and with `accepted_any` alone they produced no checkpoint, so K04's
        # hand-over (A01) had nowhere to put `full_state_sha256` and the verifier would have
        # had to call them `final_state_absent`. Found by building the verifier.
        if last.accepted_any or last.converged:
            checkpoint = Checkpoint(
                checkpoint_id=f"attempt-{attempt_index}",
                attempt_index=attempt_index,
                iteration=last.iterations,
                variable_ids=tuple(variable_ids),
                state_sha256=state_sha256(last.x, variable_ids),
                signature=opening,
                residual_inf_unscaled=last.residual_inf,
                merit=last.merit,
                label="candidate_root" if last.converged else "partial",
                step_index=step_index,
            )

        ops = _TearOps(
            variable_ids=tuple(variable_ids),
            model_version=evaluation_context.model_version,
            constants_sha256=evaluation_context.constants_sha256,
            step_index=step_index,
            lower_bounds=dict(problem.lower_bounds),
        )
        decision = decide(
            last,
            attempt_index=attempt_index,
            frozen=opening,
            wall=wall,
            ops=ops,
            policy=policy,
            used=used,
        )
        provenance.append(
            provenance_item(
                attempt=attempt_index,
                signature=opening,
                core="anderson" if method == "anderson" else "newton",
                source=source,
                initializer_source=initializer_source if attempt_index == 0 else None,
                trial=trial,
                opening_state_sha256=opening_hash,
                result=last,
                decision=decision,
            )
        )
        if decision.kind != "restart":
            fingerprint = (
                root_fingerprint(
                    model_version=evaluation_context.model_version,
                    constants_sha256=evaluation_context.constants_sha256,
                    variable_ids=variable_ids,
                    branch_found=opening,
                    full_state_sha256=state_sha256(last.x, variable_ids),
                )
                if decision.kind == "converged"
                else None
            )
            return _closed(
                trace,
                decision.outcome,
                # A terminal outcome reports the last accepted iterate, never a candidate:
                # a rejected trial chosen as a restart point was never accepted, and pairing
                # it with `last`'s residual described a state whose residual was 7926 as
                # having a residual of 69.67 (K03's fix, kept).
                last.x,
                last,
                attempt_index + 1,
                total_iterations,
                counters,
                checkpoint,
                tuple(used),
                decision.message,
                tuple(contexts),
                tuple(provenance),
                fingerprint,
            )
        conversion = decision.conversion
        assert conversion is not None
        x = np.array(conversion.opening, dtype=np.float64)
        opening = conversion.signature
        message = decision.message
        source = conversion.source
        trial = conversion.trial

    raise AssertionError("unreachable: the restart gate ends the solve at max_attempts")


class _TearOps:
    """The tear path's side of the contract (T03 §4.3, §4.7): the traversal reports a trial's
    regime, neither lifted-only conversion can fire, and an opening is a candidate's tear vector."""

    lifted = False

    def __init__(
        self,
        *,
        variable_ids: tuple[str, ...],
        model_version: str,
        constants_sha256: str,
        step_index: int | None,
        lower_bounds: Mapping[str, float],
    ) -> None:
        self._variable_ids = variable_ids
        self._identity = (model_version, constants_sha256)
        self._step_index = step_index
        self._lower_bounds = lower_bounds

    def converged(self, result: NewtonResult) -> Conversion | None:
        return None

    def blocked(self, result: NewtonResult) -> Conversion | None:
        return None

    def kernel_disagrees(self, result: NewtonResult) -> Conversion | None:
        return None

    def at_candidate(self, candidate: Candidate, cause: str) -> Conversion:
        return Conversion(
            signature=candidate.signature,
            opening=candidate.x,
            source="phase_rejected_trial",
            cause=cause,
            trial=candidate,
        )

    def opening_check(self, conversion: Conversion) -> OpeningRefusal | None:
        model_version, constants = self._identity
        values = dict(zip(self._variable_ids, (float(v) for v in conversion.opening), strict=True))
        state = OpeningState(
            values=values,
            model_version=model_version,
            constants_sha256=constants,
            step_index=self._step_index,
            reported=conversion.trial.signature if conversion.trial is not None else None,
        )
        requirement = OpeningRequirement(
            signature=conversion.signature,
            model_version=model_version,
            constants_sha256=constants,
            free=self._variable_ids,
            lower_bounds=self._lower_bounds,
            step_index=self._step_index,
        )
        return check_opening(state, requirement)


def provenance_item(
    *,
    attempt: int,
    signature: AttemptSignature,
    core: AttemptCore,
    source: OpeningSource,
    initializer_source: str | None,
    trial: Candidate | None,
    opening_state_sha256: str,
    result: NewtonResult,
    decision: Decision,
    continuation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One `branch_provenance` item (T03 §8.1, ADR 0005 D7).

    `decision` records what the attempt's *closure* proposed: an attempt that closed into a restart
    reads `restart` with that restart's cause even when the restart gate then refused it (budget,
    cycling, opening checks) — the refusal is the solve's, recorded on `solve_closed` (T03 §4.10).
    `terminal` is an attempt whose core outcome ended the solve with no restart proposed. This is
    how `benchmarks/t03/reference_values.yaml` records PHS-05's last attempt.
    """
    kind = decision.kind
    if kind == "terminal" and decision.conversion is not None:
        kind = "restart"
    cause = {"converged": "", "restart": decision.cause, "terminal": decision.message}[kind]
    return {
        "attempt": attempt,
        "signature": [[unit, regime] for unit, regime in signature],
        "core": core,
        "opening_source": source,
        "initializer_source": initializer_source,
        "opening_trial": (
            {"iteration": trial.iteration, "halving": trial.halving} if trial is not None else None
        ),
        "opening_state_sha256": opening_state_sha256,
        "core_outcome": result.outcome,
        "iterations": result.iterations,
        "decision": kind,
        "cause": cause,
        # ADR 0010 D7.5 (T04 §4.7): `{type, parameter_ids, lambda_levels, lambda_reached,
        # rejected_trials}` on a homotopy attempt's item, `None` on every other.
        "continuation": (
            _continuation_document(continuation) if continuation is not None else None
        ),
    }


def _anderson_as_newton_result(result: RecycleResult, problem: Problem) -> NewtonResult:
    """The recycle core's result in the shape the attempt contract reads.

    `merit` is the problem's own `½‖F̂‖²` (K03 §5.6) at the final iterate, so a checkpoint means
    the same thing whichever core wrote it. `accepted_any` is true iff an iteration was accepted;
    the recycle core has no rejected-but-counted iterations.
    """
    residual = result.residual
    return NewtonResult(
        outcome=result.outcome,
        x=result.x,
        residual=residual or (),
        residual_inf=max((abs(value) for value in residual), default=0.0)
        if residual is not None
        else float("nan"),
        merit=problem.scaling.merit(residual, problem.row_ids)
        if residual is not None
        else float("nan"),
        iterations=result.iterations,
        counters=result.counters,
        converged=result.converged,
        message=result.message,
        accepted_any=result.iterations > 0,
        best_x=result.best_x,
    )


def _closed(
    trace: Trace,
    outcome: SolveOutcome,
    x: npt.NDArray[np.float64],
    last: NewtonResult | None,
    attempts: int,
    iterations: int,
    counters: Counters,
    checkpoint: Checkpoint | None,
    signatures: tuple[AttemptSignature, ...],
    message: str,
    contexts: tuple[AttemptContext, ...] = (),
    provenance: tuple[Mapping[str, Any], ...] = (),
    fingerprint: Mapping[str, Any] | None = None,
) -> SolveResult:
    trace.record(
        kind="solve_closed",
        attempt=attempts,
        iteration=iterations,
        signature=signatures[-1] if signatures else (),
        state_sha256=checkpoint.state_sha256 if checkpoint else "",
        residual_inf_unscaled=last.residual_inf if last else float("nan"),
        merit=last.merit if last else float("nan"),
        counters=counters,
        outcome=outcome,
        message=message,
    )
    return SolveResult(
        outcome=outcome,
        x=x,
        residual_inf=last.residual_inf if last else float("nan"),
        attempts=attempts,
        iterations=iterations,
        counters=counters,
        checkpoint=checkpoint,
        signatures=signatures,
        converged=outcome == "CONVERGED",
        best_x=last.best_x if last is not None else None,
        message=message,
        contexts=contexts,
        branch_provenance=provenance,
        root_fingerprint=fingerprint,
    )
