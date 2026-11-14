"""`syn001.column` compiled and solved: S02 spec §7 and §8 (WO-2), §7.3 as §18.2 (WO-2b).

`column.py` holds the unit layer (WO-1) with `column_spec`, `column_validation` and `column_rows`
(S19 B2): the specification, its §5 refusals, the §2 rows, the regime forms and the §6
initializer. `column_compile` compiles those rows, `column_endpoint` builds the easy endpoint and
the inverse records, and `column_acceptance` holds §8 and the products (S19 B3). This module runs
spec §7's path on them, calling `orchestrator.region.solve_region` unchanged, through S01's
`run_region`:

1. validate (§5); an all-dormant column (possible only without ends, §5 S10) is S01 §4.6's;
2. initialize (`s02-profile-cmo-v1`), giving `x_K`;
3. the easy endpoint `s02-bubble-point-v1` (§18.2, constructed, not solved): bubble-point sweeps
   at fixed CMO stage ratios give an all-two-phase `x⁰` on which every target row except the
   continued `variable − parameter` slot rows holds;
4. the target from `x⁰` under S01's registered `s01-default-v1` (no new policy, spec §0);
5. recovery edge 3 (ADR 0010 D3, ADR 0044's trigger) on its triggers, continuing every
   `variable − parameter` slot from `p⁰` = its column at the opening;

and holds a `CONVERGED` answer to §8 before returning it. That is Stage A. S08 adds step 7, Stage B
(S08 design note §5.1, ADR 0048): when Stage A ends in a typed outcome of `REENTRY_OUTCOMES`, or
converges to a state that fails §8 on item 6 alone (a near-trivial split, S08 §3 F4), the
column's initializer builds block openings `V^a 2P^b L^c` from its sources (`column_blocks`) and
solves from each in turn; the first accepted answer is returned, and `ColumnSolution.reentry`
records Stage A and every candidate (§5.6–§5.7).

Each equilibrium stage is one lifted split keyed `<U>.stage.<j>`, as S01's (spec §4.1), PH-type.
The total condenser is not a split (§4.1). The withdrawn Newton profile pre-solve's rows
(`presolve_rows`, §7.3) stay in `column_compile` only as the definition of the registered second
easy endpoint `ref.cases.*.presolve` (A06b); they are not on the solve path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

from openflowsheet.canonical import state_sha256
from openflowsheet.compile.spec import QuantityKind
from openflowsheet.models import Accumulation, DeclaredEquation
from openflowsheet.models.syn001 import TEMPERATURE
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    CascadeSpec,
    DormantAnswer,
    dormant_answer,
)
from openflowsheet.models.syn001.cascade_solve import (
    DECLARATION_CONTEXT,
    S01_DEFAULT_V1,
    TWO_PHASE_SATURATION_TOLERANCE,
    AcceptanceDefectError,
    CompiledCascade,
    run_region,
)
from openflowsheet.models.syn001.cascade_solve import FD_COLUMN_SCALE as CASCADE_FD_SCALE
from openflowsheet.models.syn001.cascade_solve import saturation_pairs as saturation_pairs
from openflowsheet.models.syn001.column import (
    ColumnSpec,
    ProfileInitial,
    column_warnings,
    profile_initial,
    validate,
)
from openflowsheet.models.syn001.column_acceptance import ITEM_6_PREFIX as ITEM_6_PREFIX
from openflowsheet.models.syn001.column_acceptance import QUOTIENT_SLACK as QUOTIENT_SLACK
from openflowsheet.models.syn001.column_acceptance import Closure as Closure
from openflowsheet.models.syn001.column_acceptance import (
    UnsupportedAnswerError as UnsupportedAnswerError,
)
from openflowsheet.models.syn001.column_acceptance import _admissibility as _admissibility
from openflowsheet.models.syn001.column_acceptance import _saturation_pairs as _saturation_pairs
from openflowsheet.models.syn001.column_acceptance import acceptance_failures as acceptance_failures
from openflowsheet.models.syn001.column_acceptance import overall_closure as overall_closure
from openflowsheet.models.syn001.column_acceptance import product_columns as product_columns
from openflowsheet.models.syn001.column_acceptance import products as products
from openflowsheet.models.syn001.column_acceptance import regimes_of as regimes_of
from openflowsheet.models.syn001.column_acceptance import saturation_errors as saturation_errors
from openflowsheet.models.syn001.column_acceptance import (
    single_phase_specified_stage as single_phase_specified_stage,
)
from openflowsheet.models.syn001.column_acceptance import singular_pairs as singular_pairs
from openflowsheet.models.syn001.column_acceptance import spec_values as spec_values
from openflowsheet.models.syn001.column_acceptance import system_residuals as system_residuals
from openflowsheet.models.syn001.column_acceptance import target_bound as target_bound
from openflowsheet.models.syn001.column_compile import CONTINUED_KIND as CONTINUED_KIND
from openflowsheet.models.syn001.column_compile import RATIO_LETTER as RATIO_LETTER
from openflowsheet.models.syn001.column_compile import Slot as Slot
from openflowsheet.models.syn001.column_compile import closure_types as closure_types
from openflowsheet.models.syn001.column_compile import compile_column as compile_column
from openflowsheet.models.syn001.column_compile import lifted_splits as lifted_splits
from openflowsheet.models.syn001.column_compile import model_label as model_label
from openflowsheet.models.syn001.column_compile import presolve_row_id as presolve_row_id
from openflowsheet.models.syn001.column_compile import presolve_rows as presolve_rows
from openflowsheet.models.syn001.column_compile import slots as slots
from openflowsheet.models.syn001.column_compile import split_temperatures as split_temperatures
from openflowsheet.models.syn001.column_compile import stage_unit as stage_unit
from openflowsheet.models.syn001.column_compile import zero_flow_forms as zero_flow_forms
from openflowsheet.models.syn001.column_endpoint import MAX_SWEEPS as MAX_SWEEPS
from openflowsheet.models.syn001.column_endpoint import PRESOLVE_ID as PRESOLVE_ID
from openflowsheet.models.syn001.column_endpoint import (
    SWEEP_COMPOSITION_TOLERANCE as SWEEP_COMPOSITION_TOLERANCE,
)
from openflowsheet.models.syn001.column_endpoint import SWEEP_RELAXATION as SWEEP_RELAXATION
from openflowsheet.models.syn001.column_endpoint import SWEEP_TOLERANCE as SWEEP_TOLERANCE
from openflowsheet.models.syn001.column_endpoint import BubblePointEndpoint as BubblePointEndpoint
from openflowsheet.models.syn001.column_endpoint import InverseRecord as InverseRecord
from openflowsheet.models.syn001.column_endpoint import (
    UnreachedSpecification as UnreachedSpecification,
)
from openflowsheet.models.syn001.column_endpoint import (
    bubble_point_endpoint as bubble_point_endpoint,
)
from openflowsheet.models.syn001.column_endpoint import inverse_ends as inverse_ends
from openflowsheet.models.syn001.column_endpoint import inverse_records as inverse_records
from openflowsheet.models.syn001.column_endpoint import lambda_state as lambda_state
from openflowsheet.models.syn001.column_endpoint import liquid_compositions as liquid_compositions
from openflowsheet.models.syn001.column_endpoint import relaxed_compositions as relaxed_compositions
from openflowsheet.models.syn001.column_endpoint import stage_ratios as stage_ratios
from openflowsheet.models.syn001.column_endpoint import sweep_flows as sweep_flows
from openflowsheet.models.syn001.column_endpoint import (
    unreached_specifications as unreached_specifications,
)
from openflowsheet.models.syn001.saturation_band import band_temperature as band_temperature
from openflowsheet.orchestrator.homotopy import Continuation
from openflowsheet.orchestrator.recovery import (
    eo_recovery_due,
    recovered_provenance,
    solver_outcomes,
)
from openflowsheet.orchestrator.region import RecoveryStart, Regime, RegionResult
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.thermo import PropertyProvider

if TYPE_CHECKING:
    # `column_blocks` imports this module; Stage B imports it at call time (`_stage_b`).
    from openflowsheet.models.syn001.column_blocks import BlockEndpoint


#: Spec §7.4: the target's policy is S01's registered `s01-default-v1`, reused (spec §0).
S02_TARGET_POLICY: Final[SolvePolicy] = S01_DEFAULT_V1

#: The withdrawn pre-solve's replacement rows `T_j − T_j⁰` (spec §7.3), kept as the definition of
#: the registered profile endpoint (§18.2, A06b); not on the solve path. A total condenser's
#: replacement `Σ r − 1·D` is the `COL-reflux-ratio` row at `RR = 1`.
PRESOLVE_EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="COL-presolve-T",
        statement=(
            "T_j - T_j0 = 0 in place of each variable - parameter slot row of an equilibrium "
            "stage (the profile pre-solve, S02 spec §7.3)"
        ),
        dependencies=("stage.T", "parameters.T0"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source="docs/derivations/S02-spec.md §7.3",
    ),
)

#: Spec §10 A10's column scales `D_x`: S01's, plus `D_x(phi) = 1` (§2.2).
FD_COLUMN_SCALE: Final[Mapping[QuantityKind, float]] = {**CASCADE_FD_SCALE, "dimensionless": 1.0}


#: S08 §5.1 trigger (i): the typed region outcomes of Stage A that start Stage B, `T_B`.
REENTRY_OUTCOMES: Final = frozenset(
    {
        "HOMOTOPY_STALLED",
        "ACTIVE_SET_CYCLING",
        "ATTEMPTS_EXHAUSTED",
        "LINE_SEARCH_FAILED",
        "LINEAR_SOLVE_FAILED",
        "BOUND_BLOCKED",
        "STAGNATION",
        "PTC_STALLED",
        "EVALUATION_ERROR",
    }
)
#: S08 §5.1 trigger (i): `BUDGET_EXHAUSTED` starts Stage B only on these budgets (never on
#: `property_calls`).
REENTRY_BUDGETS: Final = frozenset({"newton_iterations", "ptc_steps"})
#: S08 §5.1 trigger (ii) and §5.4: the code of a `CONVERGED` state that fails §8 on item 6 alone.
NEAR_TRIVIAL_SPLIT: Final = "near_trivial_split"


# -- spec §7: the solve path ---------------------------------------------------------------------


@dataclass(frozen=True)
class StageARecord:
    """S08 §5.6: Stage A's answer when it started Stage B — its outcome and cause (on trigger
    (ii) `CONVERGED` with cause `near_trivial_split(<stages>)`), its region results, the
    `state_sha256` of its endpoint `x⁰` and of its final state, and its item-6 failure strings
    (`()` on a typed outcome)."""

    outcome: str
    cause: str
    result: RegionResult
    recovered_from: RegionResult | None
    endpoint_sha256: str
    final_sha256: str | None
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateRecord:
    """S08 §5.6: one Stage-B candidate `(a, c)` — its signature `σ(a, c)` over the equilibrium
    stages, `endpoint` `"built"` or the refusal's cause (then nothing was solved: every later
    field is `None` and `cause` is the refusal's), the endpoint's `state_sha256`, and the solve's
    outcome, cause (`""` when accepted; the region's message, `near_trivial_split(<stages>)` or
    `unsupported(…)` otherwise) and region results."""

    a: int
    c: int
    signature: tuple[Regime, ...]
    endpoint: str
    endpoint_sha256: str | None
    outcome: str | None
    cause: str
    result: RegionResult | None
    recovered_from: RegionResult | None


@dataclass(frozen=True)
class BlockReentry:
    """S08 §5.6: Stage B's record — its trigger (Stage A's outcome, or `near_trivial_split`),
    Stage A, every candidate tried in §5.2's order, and the index of the accepted one (`None`
    when none was accepted)."""

    trigger: str
    stage_a: StageARecord
    candidates: tuple[CandidateRecord, ...]
    accepted: int | None


@dataclass(frozen=True)
class ColumnSolution:
    """Spec §7's answer and §18.2's records: the outcome, the final signature by equilibrium
    stage (top to bottom), the state, the sweeps' start `T⁰` (shifted when asked; A14), the easy
    endpoint with `ρ`, `φ`, sweeps and last `max |ΔT|`, the continued slots with `p⁰`, and the
    `state_sha256` of `x_K`, `x⁰` and the answer.

    S08 §5.6: the top-level fields always describe the returned solve. When a Stage-B candidate is
    accepted they are that candidate's (`endpoint` is then its `BlockEndpoint`); otherwise they
    are Stage A's. `reentry` is `None` whenever Stage B did not run."""

    outcome: str
    cause: str
    signature: tuple[Regime, ...]
    state: Mapping[str, float]
    initial: ProfileInitial
    profile: tuple[float, ...]
    endpoint: BubblePointEndpoint | BlockEndpoint
    #: Continued parameter id → `p⁰` (the slot's column at `x⁰`), in stage order.
    continued: Mapping[str, float]
    initial_sha256: str
    endpoint_sha256: str
    result: RegionResult
    recovered_from: RegionResult | None = None
    final_sha256: str | None = None
    #: C8: stable `code(detail)` notices (`column_warnings`); not part of any `state_sha256`.
    warnings: tuple[str, ...] = ()
    #: S06 §7.5: one record per inverse end, condenser first.
    inverse: tuple[InverseRecord, ...] = ()
    #: S06 §7.3: per inverse end on a non-`CONVERGED` answer; empty on a `CONVERGED` one.
    unreached: tuple[UnreachedSpecification, ...] = ()
    #: S08 §5.6: Stage B's record; not part of any `state_sha256`.
    reentry: BlockReentry | None = None


def continuation(spec: ColumnSpec, profile: Sequence[float]) -> Continuation:
    """Spec §7.5: the continued parameters are exactly the slots §7.3 replaced, each the pinned
    input of a `variable − parameter` row (ADR 0010 D2), in stage order; ratio rows are not."""
    replaced = [slot for slot in slots(spec, profile) if slot.parameter]
    return Continuation(
        type="specification_continuation",
        parameter_ids=tuple(slot.parameter for slot in replaced),
        variable_ids=tuple(slot.variable for slot in replaced),
    )


def recover(
    spec: ColumnSpec,
    profile: Sequence[float],
    target: CompiledCascade,
    provider: PropertyProvider,
    failed: RegionResult,
    policy: SolvePolicy,
    trace: Trace | None = None,
) -> RegionResult:
    """Spec §7.5 (ADR 0010 D3, as S01's `recover`): one recovery solve from the failed solve's
    item-0 opening, its provenance continuing the failed solve's."""
    if failed.opening is None or not failed.branch_provenance:
        raise ValueError(f"defect: {spec.unit_id}'s target ended {failed.outcome} unopened")
    opening_state, opening_regimes = failed.opening
    recovered = run_region(
        target,
        provider,
        opening_state,
        policy,
        initializer_source=PRESOLVE_ID,
        trace=trace,
        recovery=RecoveryStart(
            state=opening_state,
            regimes=opening_regimes,
            continuation=continuation(spec, profile),
            initializer_source=failed.branch_provenance[0]["initializer_source"],
        ),
    )
    return replace(
        recovered,
        branch_provenance=recovered_provenance(
            failed.branch_provenance, recovered.branch_provenance
        ),
        checkpoint=recovered.checkpoint if recovered.checkpoint is not None else failed.checkpoint,
    )


def _as_cascade(spec: ColumnSpec) -> CascadeSpec:
    """A column without ends is S01's cascade under S01's ids (§5 S6 gives it both inlets)."""
    assert spec.top is not None and spec.bottom is not None
    duties = tuple(float(duty) for duty in spec.duties if duty is not None)
    return CascadeSpec(
        unit_id=spec.unit_id,
        stage_count=spec.stage_count,
        pressures=spec.pressures,
        duties=duties,
        top=spec.top,
        bottom=spec.bottom,
        sides=spec.sides,
        components=spec.components,
    )


def target_attempt(
    spec: ColumnSpec,
    provider: PropertyProvider,
    target: CompiledCascade,
    x0: Mapping[str, float],
    profile: Sequence[float],
    *,
    policy: SolvePolicy = S02_TARGET_POLICY,
    trace: Trace | None = None,
    initializer_source: str = PRESOLVE_ID,
) -> tuple[RegionResult, RegionResult | None, dict[int, Regime], tuple[str, ...], int | None]:
    """Spec §7 steps 4–5 and §8 from an easy endpoint `x⁰` whose id is `initializer_source`
    (S08 §5.1): the target under `policy`, edge 3 on its triggers (continuing the slots §7.3
    replaced at `profile`), and §8 evaluated on a `CONVERGED` answer, without raising. Returns
    the final result, the failed solve edge 3 recovered from (or `None`), the final regimes by
    stage, §8's failures and S06 §8 item 3's single-phase `temperature`-specified stage (or
    `None`); the last two are empty and `None` unless the answer is `CONVERGED`."""
    state = {name: float(x0[name]) for name in target.spec.variable_ids}
    result = run_region(
        target, provider, state, policy, initializer_source=initializer_source, trace=trace
    )
    recovered_from: RegionResult | None = None
    if policy.globalization.eo_recovery == "homotopy" and eo_recovery_due(
        result.outcome, result.budget, attempts=solver_outcomes(result.attempts)
    ):
        recovered_from = result
        result = recover(spec, profile, target, provider, result, policy, trace)
    regimes = regimes_of(spec, result.attempts[-1].signature) if result.attempts else {}
    failures: tuple[str, ...] = ()
    unsupported: int | None = None
    if result.outcome == "CONVERGED":
        failures = acceptance_failures(spec, provider, target.spec, result.state, regimes)
        unsupported = single_phase_specified_stage(spec, regimes)
    return result, recovered_from, regimes, failures, unsupported


def _unsupported(
    spec: ColumnSpec, regimes: Mapping[int, Regime], stage: int
) -> UnsupportedAnswerError:
    """S06 §8 item 3's answer for a single-phase `temperature`-specified `stage`."""
    return UnsupportedAnswerError(
        f"unsupported(temperature_specification_on_single_phase_stage:{stage})",
        f"{spec.unit_id} stage {stage} is {regimes[stage]} at the CONVERGED state",
    )


def solve_target(
    spec: ColumnSpec,
    provider: PropertyProvider,
    target: CompiledCascade,
    x0: Mapping[str, float],
    profile: Sequence[float],
    *,
    policy: SolvePolicy = S02_TARGET_POLICY,
    trace: Trace | None = None,
    initializer_source: str = PRESOLVE_ID,
) -> tuple[RegionResult, RegionResult | None, dict[int, Regime]]:
    """Spec §7 steps 4–5 and §8 from an easy endpoint `x⁰`: `target_attempt`, and acceptance of
    a `CONVERGED` answer (`AcceptanceDefectError` on a failure). S06 §8 item 3 is decided after
    the defect clauses (S06 §17.3, R-610): a defect-free `CONVERGED` answer whose
    `temperature`-specified stage is single-phase raises `UnsupportedAnswerError` (never a
    success, and not a defect); a defective one is a defect whatever the regime. Returns the
    final result, the failed solve edge 3 recovered from (or `None`), and the final regimes by
    stage."""
    result, recovered_from, regimes, failures, unsupported = target_attempt(
        spec,
        provider,
        target,
        x0,
        profile,
        policy=policy,
        trace=trace,
        initializer_source=initializer_source,
    )
    if failures:
        raise AcceptanceDefectError(failures)
    if unsupported is not None:
        raise _unsupported(spec, regimes, unsupported)
    return result, recovered_from, regimes


def _item_6_stages(
    spec: ColumnSpec,
    provider: PropertyProvider,
    state: Mapping[str, float],
    regimes: Mapping[int, Regime],
    failures: Sequence[str],
) -> tuple[int, ...]:
    """The `TWO_PHASE` stages that fail item 6, top to bottom, when §8's `failures` are all item
    6's; `()` when there is none or another item failed as well."""
    if not failures or not all(failure.startswith(ITEM_6_PREFIX) for failure in failures):
        return ()
    errors = saturation_errors(spec, provider, state, regimes)
    return tuple(
        stage for stage, error in errors.items() if not error <= TWO_PHASE_SATURATION_TOLERANCE
    )


def _near_trivial_cause(stages: Sequence[int]) -> str:
    return f"{NEAR_TRIVIAL_SPLIT}({','.join(str(stage) for stage in stages)})"


def reentry_trigger(result: RegionResult, near_trivial: Sequence[int]) -> str | None:
    """S08 §5.1: Stage B's trigger on Stage A's final `result` — its outcome when that is in
    `REENTRY_OUTCOMES`, or `BUDGET_EXHAUSTED` on a budget of `REENTRY_BUDGETS` (trigger (i));
    `near_trivial_split` when it is `CONVERGED` and fails §8 on item 6 alone, at the stages
    `near_trivial` (trigger (ii)); `None` otherwise."""
    if result.outcome == "CONVERGED":
        return NEAR_TRIVIAL_SPLIT if near_trivial else None
    if result.outcome in REENTRY_OUTCOMES:
        return result.outcome
    if result.outcome == "BUDGET_EXHAUSTED" and result.budget in REENTRY_BUDGETS:
        return result.outcome
    return None


def solve_column(
    spec: ColumnSpec,
    provider: PropertyProvider,
    *,
    policy: SolvePolicy = S02_TARGET_POLICY,
    profile_shift: float = 0.0,
    ratio_scale: float = 1.0,
    max_sweeps: int = MAX_SWEEPS,
    trace: Trace | None = None,
) -> ColumnSolution | CascadeFailure | DormantAnswer:
    """Spec §7, steps 1–5 (step 3 as §18.2), and §8 on a `CONVERGED` answer (Stage A); then S08's
    step 7 (Stage B, §5.1) on its trigger.

    `profile_shift` (K) moves the sweeps' start and `ratio_scale` the stage ratios no
    specification holds (spec §18.6 A14); `max_sweeps` is §18.2's cap (A22). A failed endpoint
    returns its typed `CascadeFailure` before any region solve. A `CONVERGED` answer that fails §8
    raises `AcceptanceDefectError`, unless it fails item 6 alone (S08 §5.1 trigger (ii)); one S06
    §8 item 3 does not offer is the `CascadeFailure` `CAPABILITY_UNAVAILABLE` with its cause.
    S06: `inverse` holds §7.5's records and `unreached` §7.3's report. S08: Stage B's first
    accepted candidate is the answer; when none is accepted a typed Stage-A answer is returned
    with `reentry`, and an item-6 rejection raises `AcceptanceDefectError` (§5.7).

    C8: every `ColumnSolution` and `CascadeFailure` for a duty-only specification carries
    `column_warnings(spec)`; the dormant answer has no ends and none.
    """
    warnings = column_warnings(spec)
    refused = validate(spec, provider, DECLARATION_CONTEXT)
    if refused is not None:
        return replace(refused, warnings=warnings)
    if all(float(a) == 0.0 for inlet in spec.inlets() for a in inlet.state.n):
        # Only a column without ends reaches here (§5 S10): S01 §4.6's closed form.
        return dormant_answer(_as_cascade(spec), provider, DECLARATION_CONTEXT)
    initial = profile_initial(spec, provider, DECLARATION_CONTEXT)
    if isinstance(initial, CascadeFailure):
        return replace(initial, warnings=warnings)
    endpoint = bubble_point_endpoint(
        spec,
        provider,
        initial,
        profile_shift=profile_shift,
        ratio_scale=ratio_scale,
        max_sweeps=max_sweeps,
    )
    if isinstance(endpoint, CascadeFailure):
        return replace(endpoint, warnings=warnings)

    target = compile_column(spec, provider)
    order = target.spec.variable_ids
    x0 = {name: float(endpoint.state[name]) for name in order}
    profile = tuple(t + float(profile_shift) for t in initial.profile)
    result, recovered_from, regimes, failures, unsupported = target_attempt(
        spec, provider, target, x0, initial.profile, policy=policy, trace=trace
    )
    near_trivial = _item_6_stages(spec, provider, result.state, regimes, failures)
    trigger = reentry_trigger(result, near_trivial)
    if failures and trigger is None:
        raise AcceptanceDefectError(failures)
    if not failures and unsupported is not None:
        scope = _unsupported(spec, regimes, unsupported)
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE", scope.cause, scope.detail, warnings=warnings
        )
    answer = _column_answer(
        spec, initial, profile, endpoint, target, x0, result, recovered_from, regimes, warnings
    )
    if trigger is None:
        return answer
    stage_a = StageARecord(
        outcome=answer.outcome,
        cause=_near_trivial_cause(near_trivial) if failures else answer.cause,
        result=result,
        recovered_from=recovered_from,
        endpoint_sha256=answer.endpoint_sha256,
        final_sha256=answer.final_sha256,
        failures=failures,
    )
    return _stage_b(
        spec,
        provider,
        target,
        initial,
        answer,
        BlockReentry(trigger, stage_a, (), None),
        policy=policy,
        profile_shift=profile_shift,
        ratio_scale=ratio_scale,
        max_sweeps=max_sweeps,
        trace=trace,
    )


def _column_answer(
    spec: ColumnSpec,
    initial: ProfileInitial,
    profile: tuple[float, ...],
    endpoint: BubblePointEndpoint | BlockEndpoint,
    target: CompiledCascade,
    x0: Mapping[str, float],
    result: RegionResult,
    recovered_from: RegionResult | None,
    regimes: Mapping[int, Regime],
    warnings: tuple[str, ...],
) -> ColumnSolution:
    """The `ColumnSolution` of one solve from the endpoint `x⁰` (Stage A's, or a Stage-B
    candidate's: S08 §5.6's top-level fields)."""
    order = target.spec.variable_ids
    replaced = [slot for slot in slots(spec, initial.profile) if slot.parameter]
    return ColumnSolution(
        outcome=result.outcome,
        cause=result.message if result.outcome != "CONVERGED" else "",
        signature=tuple(regimes.values()),
        state=dict(result.state),
        initial=initial,
        profile=profile,
        endpoint=endpoint,
        continued={slot.parameter: x0[slot.variable] for slot in replaced},
        initial_sha256=state_sha256(dict(initial.state), order),
        endpoint_sha256=state_sha256(x0, order),
        result=result,
        recovered_from=recovered_from,
        final_sha256=state_sha256(dict(result.state), order),
        warnings=warnings,
        inverse=inverse_records(spec, x0),
        unreached=unreached_specifications(spec, result, recovered_from),
    )


def _stage_b(
    spec: ColumnSpec,
    provider: PropertyProvider,
    target: CompiledCascade,
    initial: ProfileInitial,
    answer: ColumnSolution,
    reentry: BlockReentry,
    *,
    policy: SolvePolicy,
    profile_shift: float,
    ratio_scale: float,
    max_sweeps: int,
    trace: Trace | None,
) -> ColumnSolution:
    """S08 §5.1 Stage B and §5.7 after Stage A's `answer` triggered it: for each candidate of
    §5.2, in order, its §5.3 endpoint (a refusal is recorded and the next candidate tried), then
    §5.4's solve from it under the same policy; the first accepted answer is returned with
    `reentry`. None accepted: Stage A's typed `answer` with `reentry`, or, when Stage A failed
    item 6, `AcceptanceDefectError` with Stage A's failures. A candidate's §8 failure other than
    item 6 is a defect and raises."""
    from openflowsheet.models.syn001 import column_blocks

    order = target.spec.variable_ids
    records: list[CandidateRecord] = []
    for index, candidate in enumerate(column_blocks.candidates(spec)):
        a, c = candidate
        signature = column_blocks.block_signature(spec, candidate)
        built = column_blocks.block_endpoint(
            spec,
            provider,
            initial,
            candidate,
            profile_shift=profile_shift,
            ratio_scale=ratio_scale,
            max_sweeps=max_sweeps,
        )
        if isinstance(built, CascadeFailure):
            records.append(
                CandidateRecord(a, c, signature, built.cause, None, None, built.cause, None, None)
            )
            continue
        x0 = {name: float(built.state[name]) for name in order}
        result, recovered_from, regimes, failures, unsupported = target_attempt(
            spec,
            provider,
            target,
            x0,
            initial.profile,
            policy=policy,
            trace=trace,
            initializer_source=column_blocks.BLOCK_ENDPOINT_ID,
        )
        cause = result.message if result.outcome != "CONVERGED" else ""
        if failures:
            near_trivial = _item_6_stages(spec, provider, result.state, regimes, failures)
            if not near_trivial:
                raise AcceptanceDefectError(failures)
            cause = _near_trivial_cause(near_trivial)
        elif result.outcome == "CONVERGED" and unsupported is not None:
            cause = _unsupported(spec, regimes, unsupported).cause
        records.append(
            CandidateRecord(
                a,
                c,
                signature,
                "built",
                state_sha256(x0, order),
                result.outcome,
                cause,
                result,
                recovered_from,
            )
        )
        if result.outcome == "CONVERGED" and not cause:
            accepted = _column_answer(
                spec,
                initial,
                answer.profile,
                built,
                target,
                x0,
                result,
                recovered_from,
                regimes,
                answer.warnings,
            )
            return replace(
                accepted, reentry=replace(reentry, candidates=tuple(records), accepted=index)
            )
    reentry = replace(reentry, candidates=tuple(records))
    if reentry.stage_a.failures:
        refused = AcceptanceDefectError(reentry.stage_a.failures)
        tried = "; ".join(f"({r.a}, {r.c}) {r.cause}" for r in records) or "none"
        refused.add_note(f"S08 §5.7: no Stage-B candidate was accepted; tried: {tried}")
        raise refused
    return replace(answer, reentry=reentry)


__all__ = [
    "CONTINUED_KIND",
    "FD_COLUMN_SCALE",
    "MAX_SWEEPS",
    "PRESOLVE_EQUATIONS",
    "PRESOLVE_ID",
    "QUOTIENT_SLACK",
    "ITEM_6_PREFIX",
    "NEAR_TRIVIAL_SPLIT",
    "RATIO_LETTER",
    "REENTRY_BUDGETS",
    "REENTRY_OUTCOMES",
    "S02_TARGET_POLICY",
    "SWEEP_COMPOSITION_TOLERANCE",
    "SWEEP_RELAXATION",
    "SWEEP_TOLERANCE",
    "BlockReentry",
    "BubblePointEndpoint",
    "CandidateRecord",
    "Closure",
    "ColumnSolution",
    "InverseRecord",
    "Slot",
    "StageARecord",
    "UnreachedSpecification",
    "UnsupportedAnswerError",
    "acceptance_failures",
    "bubble_point_endpoint",
    "closure_types",
    "compile_column",
    "continuation",
    "inverse_ends",
    "inverse_records",
    "lambda_state",
    "lifted_splits",
    "model_label",
    "overall_closure",
    "presolve_row_id",
    "presolve_rows",
    "product_columns",
    "products",
    "recover",
    "reentry_trigger",
    "regimes_of",
    "single_phase_specified_stage",
    "singular_pairs",
    "slots",
    "solve_column",
    "solve_target",
    "spec_values",
    "split_temperatures",
    "stage_ratios",
    "sweep_flows",
    "system_residuals",
    "target_attempt",
    "target_bound",
    "unreached_specifications",
    "zero_flow_forms",
]
