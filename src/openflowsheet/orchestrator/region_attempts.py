"""The region's PTC and homotopy attempts: `region_ptc_problem`, `_ptc_attempt`, `_homotopy`,
`_boundary_unit`.

Moved verbatim from `orchestrator.region` (S19 RS split-region-2); `region` re-exports them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from fractions import Fraction

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models.lifted import DormancyForm, LiftedSplit, Regime
from openflowsheet.numerics.newton import NewtonResult, solve_newton
from openflowsheet.numerics.ptc import PtcProblem, PtcRecord, solve_ptc
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.homotopy import (
    CorrectorOutcome,
    HomotopyRecord,
    continue_specification,
    level_values,
    rebind,
)
from openflowsheet.orchestrator.mass import RegionMass
from openflowsheet.orchestrator.phase_contract import WallObserver
from openflowsheet.orchestrator.region_phase import ClosureMemo
from openflowsheet.orchestrator.region_problem import (
    _region_problem,
    _watched_variables,
    _with_labels,
)
from openflowsheet.orchestrator.region_result import RecoveryStart
from openflowsheet.orchestrator.region_screen import _attempt_screen
from openflowsheet.orchestrator.trace import AttemptSignature, Counters, SolvePolicy, Trace
from openflowsheet.thermo import PropertyProvider


def region_ptc_problem(
    *,
    region_mass: RegionMass,
    compiled: CompiledProblem,
    spec: ProblemSpec,
    scaling: Scaling,
    base: Mapping[str, float],
    free: Sequence[str],
    rows: Sequence[str],
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    policy: SolvePolicy,
    context: EvaluationContext,
    opening: npt.NDArray[np.float64] | None = None,
    ph_units: frozenset[str] = frozenset(),
    v2: bool = False,
    labels: Sequence[tuple[str, str, str]] = (),
    dormancy: Sequence[DormancyForm] = (),
    temperatures: Mapping[str, tuple[str, ...]] | None = None,
    memo: ClosureMemo | None = None,
) -> PtcProblem:
    """One PTC attempt's problem (T04 §7.2–§7.3): the Newton attempt's — the same rows, columns,
    scales, tolerances, bounds and T03 screen, `opening` not screened — with `M` added: the
    region's validated mapping evaluated at each accepted iterate, restricted by id to the
    attempt's rows and free columns, under the attempt's one context (K03 §12.4). A label row
    (T05b spec §7.8 (v)) is algebraic: no holdup, a zero row of `M`."""
    screen = _attempt_screen(
        splits=splits,
        regimes=regimes,
        provider=provider,
        context=context,
        epsilon=policy.admissibility_epsilon,
        ph_units=ph_units,
        v2=v2,
        dormancy=dormancy,
        temperatures=temperatures,
        memo=memo,
    )
    problem = _region_problem(
        compiled, context, spec, scaling, base, free, rows, screen, opening, **_with_labels(labels)
    )
    held = dict(base)

    def mass(x: npt.NDArray[np.float64]) -> sp.csc_matrix:
        state = dict(held)
        state.update(zip(free, (float(value) for value in x), strict=True))
        return region_mass.matrix(state, problem.row_ids, free, provider, context)

    accumulation: Mapping[str, str] = spec.row_accumulation
    if labels:
        accumulation = {**accumulation, **{label: "algebraic" for label, _, _ in labels}}
    return PtcProblem(problem, mass, accumulation)


def _ptc_attempt(
    *,
    region_mass: RegionMass,
    compiled: CompiledProblem,
    spec: ProblemSpec,
    scaling: Scaling,
    base: Mapping[str, float],
    free: Sequence[str],
    rows: Sequence[str],
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    policy: SolvePolicy,
    attempt_context: EvaluationContext,
    trace: Trace,
    attempt_index: int,
    signature: AttemptSignature,
    counters: Counters,
    wall: WallObserver,
    x0: npt.NDArray[np.float64],
    ph_units: frozenset[str],
    v2: bool = False,
    labels: Sequence[tuple[str, str, str]] = (),
    dormancy: Sequence[DormancyForm] = (),
    temperatures: Mapping[str, tuple[str, ...]] | None = None,
    memo: ClosureMemo | None = None,
) -> tuple[NewtonResult, PtcRecord]:
    """T04 §7 as one attempt's core, in the attempt's frozen signature. The SER state opens at
    `tau_initial_s`: T04 §7.4's reset, per attempt."""
    problem = region_ptc_problem(
        region_mass=region_mass,
        compiled=compiled,
        spec=spec,
        scaling=scaling,
        base=base,
        free=free,
        rows=rows,
        splits=splits,
        regimes=regimes,
        provider=provider,
        policy=policy,
        context=attempt_context,
        opening=x0,
        ph_units=ph_units,
        v2=v2,
        labels=labels,
        dormancy=dormancy,
        temperatures=temperatures,
        memo=memo,
    )
    return solve_ptc(
        problem,
        x0,
        policy.globalization.ptc,
        trace=trace,
        signature=signature,
        attempt=attempt_index,
        counters=counters,
        observer=wall,
        # T05b spec §7.8 (iii): an empty signature is screened too where there are forms (v2).
        compare_empty=bool(dormancy),
    )


def _homotopy(
    *,
    recovery: RecoveryStart,
    compiled: CompiledProblem,
    compile_level: Callable[[ProblemSpec], CompiledProblem],
    spec: ProblemSpec,
    scaling: Scaling,
    opening_state: Mapping[str, float],
    free: Sequence[str],
    rows: Sequence[str],
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    policy: SolvePolicy,
    attempt_context: EvaluationContext,
    trace: Trace,
    attempt_index: int,
    signature: AttemptSignature,
    counters: Counters,
    x0: npt.NDArray[np.float64],
    ph_units: frozenset[str],
    v2: bool = False,
    labels: Sequence[tuple[str, str, str]] = (),
    dormancy: Sequence[DormancyForm] = (),
) -> tuple[NewtonResult, HomotopyRecord]:
    """T04 §4 as one attempt's core, in the attempt's frozen signature.

    Each λ < 1 level is compiled from the declaration with the continued pinned inputs re-bound
    (`homotopy.rebind`, by id) and evaluated under a **level context** — the attempt's own context
    but for `constants_sha256` (ADR 0010 D6). The λ = 1 level is the target instance under the
    attempt's context. Every corrector is K03's Newton core, unchanged, with the T03 screen and a
    wall observer of its own, capped at `corrector_max_iterations`.
    """
    settings = policy.globalization.homotopy
    corrector_policy = replace(policy, max_iterations_per_attempt=settings.corrector_max_iterations)
    levels: dict[Fraction, tuple[CompiledProblem, EvaluationContext]] = {}

    def level(lam: Fraction) -> tuple[CompiledProblem, EvaluationContext]:
        if lam == 1:
            return compiled, attempt_context
        if lam not in levels:
            values = level_values(recovery.continuation, spec.parameters, opening_state, lam)
            instance = compile_level(rebind(spec, values))
            if instance.metadata.model_version != compiled.metadata.model_version:
                raise RuntimeError(
                    "defect: a λ-level re-binds pinned inputs only, and compiled to another "
                    f"model_version ({instance.metadata.model_version})"
                )
            levels[lam] = (
                instance,
                replace(attempt_context, constants_sha256=instance.metadata.constants_sha256),
            )
        return levels[lam]

    def correct(
        lam: Fraction, start: npt.NDArray[np.float64], running: Counters
    ) -> CorrectorOutcome:
        instance, context = level(lam)
        screen = _attempt_screen(
            splits=splits,
            regimes=regimes,
            provider=provider,
            context=context,
            epsilon=policy.admissibility_epsilon,
            ph_units=ph_units,
            v2=v2,
            dormancy=dormancy,
        )
        problem = _region_problem(
            instance,
            context,
            spec,
            scaling,
            opening_state,
            free,
            rows,
            screen,
            start,
            **_with_labels(labels),
        )
        wall = WallObserver(policy)
        result = solve_newton(
            problem,
            start,
            corrector_policy,
            trace=trace,
            signature=signature,
            attempt=attempt_index,
            counters=running,
            observer=wall,
            compare_empty=bool(dormancy),
            # K03 §5.3's release reads the attempt's opening, not this λ-level's start (note of
            # 2026-09-25, T05b Q-S13): a phase that vanished at an earlier level is no
            # structural zero.
            opening=x0,
        )
        return CorrectorOutcome(
            result=result,
            level_constants_sha256=instance.metadata.constants_sha256,
            boundary_unit=_boundary_unit(
                result, wall, splits, regimes, signature, opening_state, free
            ),
        )

    return continue_specification(
        correct=correct,
        x0=x0,
        continuation=recovery.continuation,
        policy=settings,
        trace=trace,
        attempt=attempt_index,
        signature=signature,
        variable_ids=free,
        counters=counters,
    )


def _boundary_unit(
    result: NewtonResult,
    wall: WallObserver,
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    signature: AttemptSignature,
    base: Mapping[str, float],
    free: Sequence[str],
) -> str | None:
    """T04 §4.6: the unit a rejected corrector's phase boundary belongs to, or `None`.

    `BOUND_BLOCKED` with a watched variable (T03 §4.6) of a `TWO_PHASE` unit in `blocked_by`: that
    unit. `PHASE_UPDATE_REQUIRED`: the unit whose reported regime differed from the frozen one.
    Either way the first in signature order."""
    order = [unit for unit, _ in signature]
    # T05b spec §7.8 (i): a candidate can carry an item the frozen signature lacks; it follows
    # the frozen entries, in the candidates' order.
    order += list(
        dict.fromkeys(
            unit
            for candidate in wall.candidates
            for unit, _ in candidate.signature
            if unit not in order
        )
    )
    found: set[str] = set()
    if result.outcome == "BOUND_BLOCKED":
        end = dict(base)
        end.update(zip(free, (float(value) for value in result.x), strict=True))
        watched = _watched_variables(splits, regimes, end)
        found = {watched[name][0] for name in result.blocked_by if name in watched}
    elif result.outcome == "PHASE_UPDATE_REQUIRED":
        frozen = dict(signature)
        found = {
            unit
            for candidate in wall.candidates
            for unit, regime in candidate.signature
            if frozen.get(unit) != regime
        }
    if not found:
        return None
    return min(found, key=order.index)
