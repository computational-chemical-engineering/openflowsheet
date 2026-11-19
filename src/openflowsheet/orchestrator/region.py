"""The equation-oriented region solve, and the phase policy the lifted form needs. T02 §6.

A region is a square system of rows and free variables with every upstream stream fixed (§6.1).
It is solved by K03's Newton core, unchanged — scales, bounds, SuperLU, line search, outcomes. What
is new is §6.3, and it exists because of two measurements. On the lifted form the phase split is
a *variable*, and both trivial branches — all liquid, all vapour — are exact roots of every row
(register R-010's warning). A plain bounded Newton started on the once-through case's all-liquid
branch converges in one iteration to that inadmissible root with `|R| = 2e-16`; started at the
nominal initializer it ends `BOUND_BLOCKED` at iteration 1 with the heater outlet's vapour total at
`4.4e-5 mol/s`, because the solution has that stream liquid and the iterate is crossing into it.

So each attempt freezes an **active phase set** per lifted unit, under ADR 0005's contract (T03
§4; register R-028 — T03 reversed two of T02's rules, and this note once stated both). A phase
leaves only when an attempt ends **`BOUND_BLOCKED` on one of its variables**; a lifted total that
merely *lands* on its bound is an overshoot, not a disappearance. Every trial of a single-phase unit
is screened by K03 §8.2's admissibility check, and a flagged trial asks the kernel: a trial in
another regime is rejected `phase_update_required` and halved, exactly as on the tear path, and a
persistent wall restarts from the phase-rejected trial the adjacency rule selects (T03 §4.5). At
closure, T02's two conversions are kept: an inadmissible converged state (judged by the branch
found) and a failed attempt the kernel disagrees with. The opening state is never screened.

**"The kernel" under `T05b-phase-contract-v2`** (T05b spec §6.2–§6.5; ADR 0012 D4, D10 F2). A
TP-type split is answered by the provider's TP flash, as under v1. A PH-type split — its unit's
energy row fixes its temperature (`splits.closure_types`) — is answered by its PH closure at the
split's own enthalpy, `ph_state(n_feed, P, H_split)`, which on SYN-001 never reports the far
regime (spec §6.3); when that closure refuses, by the TP flash, and the opening records
`fallback(<unit>, tp)` (`fallback(<unit>, ph-band)` when the closure answered by its band route).
A PH-type split is not re-projected at the start: it opens with the traversal closure's split, in
the regime of its branch (§6.4).

**`ZERO_FLOW` under v2** (T05b spec §7.1–§7.5; ADR 0012 D4 (c)). A lifted split whose feed is
exactly dormant (`+0.0`, no threshold) is in `ZERO_FLOW`: its `ZeroFlowForm` pins its lifted flows
at `+0.0` and drops its equilibrium, split and total-definition rows, and a PH-type split's form
swaps its unit's energy row for the label row `T_out − T_label`, a row of the attempt's system
only (never of the compiled declaration). The screen checks, at every trial, that exact dormancy
of each feed agrees with the regime; a split leaving `ZERO_FLOW` takes the TP flash's regime and
split (the zero-flow state carries no enthalpy), recorded `fallback(<unit>, tp)` for a PH-type
split. At closure, after the branch's admissibility, every swapped energy row must hold at the
final state (spec §7.8 (iv) 2), or the region closes `SPECIFICATION_CONFLICT`,
`zero_flow_conflict(<row id>)`.

**Dormant non-lifted outlets under v2** (T05b spec §7.6–§7.8; ADR 0012 D12). A dormancy-form
outlet (`splits.dormancy_forms`: the pump's, the K02 mixer's, an exchanger side whose outlet
temperature is not the specification) whose trigger streams are all exactly dormant runs its
`DormancyForm`: its energy row out, its label row in, nothing pinned. The regime machinery carries
it without making its unit a signature unit: the attempt signature is the lifted regimes followed
by one item `(<U>.<port>, ZERO_FLOW)` per active form. The items are recomputed from every opening
state — after the lifted part is set — and an outlet whose item changes there has its outlet flows
set to its mole balance (§7.8 (ii)); the screen checks each trial's trigger dormancy against the
items; at closure an item that disagrees with its triggers restarts with it toggled, and every
swapped row, lifted and non-lifted, must hold (§7.8 (iv)).

**`pr-c1-v1` splits** (M02 design note §14.2 B12–B14; ADR 0012 Amendment A1–A2; register R-254,
R-256). Where the provider is `pr-c1-v1` (`_pr_c1`, which reads the uncounted `describe`), the
kernel's regime is M01 §7 rule 3 with τ_dew (`models.c1.phase.classify`): a TWO_PHASE flash whose
liquid NH3 is at most τ_dew of the feed is VAPOR, opened as a VAPOR restart pins it — never with
the flash's ulp-sized liquid, at which the TWO_PHASE Jacobian is singular. The single-phase
admissibility reads the same classification and not `admissibility_epsilon`, and the screen's
regime of a flagged split is the same kernel's. A split whose rule declares vapour-only components
has a `VapourOnlyForm`: in a TWO_PHASE attempt their liquid flows are pinned at `+0.0` and their
zero rows dropped. Every other provider runs the code above, unchanged.

**Where the code is** (S19 B1, RS). This module holds SYN-001's lifted splits and the attempt
loop (`solve_region`, `_solve_region`, with `_swapped_row_test` and `_external_opening`). The
region's records (`RegionResult`, `RegionAttempt`, `AttemptSystem`, `RecoveryStart`) are in
`orchestrator.region_result`; the trial screen (`_attempt_screen`) in `orchestrator.region_screen`;
the PTC and homotopy attempts (`region_ptc_problem`, `_ptc_attempt`, `_homotopy`) in
`orchestrator.region_attempts`; the phase-policy kernel (the kernel, the PH closure, the
admissibility screens and their refusals) in `orchestrator.region_phase`; the Newton problem over
lifted splits (labels, the opening fixed point, dormancy outlets, `_LiftedOps`) in
`orchestrator.region_problem`. Callers and tests import those names from their modules.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, NamedTuple

import numpy as np
import numpy.typing as npt

from openflowsheet.canonical import state_sha256
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models.lifted import (
    LABEL_KIND,
    ClosureType,
    DormancyForm,
    LiftedSplit,
    Regime,
    VapourOnlyForm,
    ZeroFlowForm,
)
from openflowsheet.models.lifted import StagedSplits as StagedSplits
from openflowsheet.models.lifted_tolerance import KIND_TOLERANCE
from openflowsheet.numerics.newton import solve_newton
from openflowsheet.numerics.ptc import PtcRecord
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS, Scaling
from openflowsheet.numerics.solve_record import (
    AttemptSignature,
    Checkpoint,
    Counters,
    SolveOutcome,
    SolvePolicy,
    Trace,
    fraction_string,
)
from openflowsheet.orchestrator.attempts import AttemptContext, AttemptCore, provenance_item
from openflowsheet.orchestrator.budget import BudgetExhaustedError
from openflowsheet.orchestrator.execution import Region
from openflowsheet.orchestrator.homotopy import (
    HomotopyRecord,
)
from openflowsheet.orchestrator.mass import MappingRefusal, MassMapping, RegionMass, resolve_mass
from openflowsheet.orchestrator.phase_contract import (
    CONTRACT_V2,
    Candidate,
    Decision,
    OpeningNotSettledError,
    OpeningRefusal,
    OpeningRequirement,
    OpeningSource,
    OpeningState,
    WallObserver,
    check_opening,
    decide,
    jacobian_pattern,
    opening_not_settled,
)
from openflowsheet.orchestrator.region_attempts import _homotopy, _ptc_attempt
from openflowsheet.orchestrator.region_phase import (
    ClosureMemo,
    _branch,
    _contract_kernel,
    _dormant_feed,
    _dropped,
    _form,
    _kernel,
    _KernelRefusedError,
    _pinned,
    _zero_flow_answer,
)
from openflowsheet.orchestrator.region_problem import (
    OpeningEntry,
    _branch_found,
    _items,
    _label_entries,
    _labels,
    _LiftedOps,
    _opening_order,
    _refinement,
    _region_problem,
    _settle,
    _with_labels,
)
from openflowsheet.orchestrator.region_result import (
    AttemptSystem,
    RecoveryStart,
    RegionAttempt,
    RegionResult,
)
from openflowsheet.orchestrator.region_screen import _attempt_screen
from openflowsheet.orchestrator.revision_continuation import REVISION_CONTINUATION_REJECTED
from openflowsheet.orchestrator.roots import branch_found, root_fingerprint
from openflowsheet.orchestrator.warm_start import WARM_START_REJECTED, WARM_START_SOURCE
from openflowsheet.thermo import PropertyProvider

__all__ = [
    "StagedSplits",
    "solve_region",
    "syn001_lifted_splits",
]


def syn001_lifted_splits(components: Sequence[str]) -> tuple[LiftedSplit, ...]:
    """The heater's split of S3 and the flash's split of its feed into S4 and S5, in order."""
    from openflowsheet.models import flow_id, pressure_id, row_id, temperature_id
    from openflowsheet.models.syn001.flash import total_flow_id
    from openflowsheet.models.syn001.flowsheet import FLASH_UNIT, HEATER_UNIT
    from openflowsheet.models.syn001.tp_state import (
        liquid_flow_id,
        liquid_total_id,
        vapor_flow_id,
        vapor_total_id,
    )

    heater = LiftedSplit(
        unit=HEATER_UNIT,
        stream="S3",
        feed=tuple(flow_id("S3", c) for c in components),
        temperature=temperature_id("S3"),
        pressure=pressure_id("S3"),
        vapor=tuple(vapor_flow_id("S3", c) for c in components),
        liquid=tuple(liquid_flow_id("S3", c) for c in components),
        vapor_total=vapor_total_id("S3"),
        liquid_total=liquid_total_id("S3"),
        equilibrium_rows=tuple(row_id(HEATER_UNIT, "HEAT-equilibrium", c) for c in components),
        vapor_definition=row_id(HEATER_UNIT, "Vdef"),
        liquid_definition=row_id(HEATER_UNIT, "Ldef"),
    )
    flash = LiftedSplit(
        unit=FLASH_UNIT,
        stream="S3",
        feed=tuple(flow_id("S3", c) for c in components),
        temperature=temperature_id("S4"),
        pressure=pressure_id("S4"),
        vapor=tuple(flow_id("S4", c) for c in components),
        liquid=tuple(flow_id("S5", c) for c in components),
        vapor_total=total_flow_id("S4"),
        liquid_total=total_flow_id("S5"),
        equilibrium_rows=tuple(row_id(FLASH_UNIT, "FLASH-equilibrium", c) for c in components),
        vapor_definition=row_id(FLASH_UNIT, "Ndef", "vapor"),
        liquid_definition=row_id(FLASH_UNIT, "Ndef", "liquid"),
    )
    return heater, flash


def solve_region(
    *,
    compiled: CompiledProblem,
    spec: ProblemSpec,
    region: Region,
    state: Mapping[str, float],
    splits: Sequence[LiftedSplit],
    provider: PropertyProvider,
    policy: SolvePolicy,
    trace: Trace | None = None,
    initializer_source: str | None,
    recovery: RecoveryStart | None = None,
    compile_level: Callable[[ProblemSpec], CompiledProblem] | None = None,
    mass_mapping: MassMapping | None = None,
    closure_types: Mapping[str, ClosureType] | None = None,
    band_routes: Sequence[str] = (),
    zero_flow_forms: Mapping[str, ZeroFlowForm] | None = None,
    dormancy_forms: Sequence[DormancyForm] = (),
    split_temperatures: Mapping[str, tuple[str, ...]] | None = None,
    item0_opening_source: Literal["initializer", "eo_recovery_start"] = "initializer",
    warm_start: bool = False,
    vapour_only_forms: Mapping[str, VapourOnlyForm] | None = None,
    split_owners: Mapping[str, str] | None = None,
) -> RegionResult:
    """§6's region solve from `state`, a full state over `spec.variable_ids` (the initializer),
    under ADR 0005's contract (T03 §4) as the policy's `phase_contract` states it.

    `closure_types` (T05b spec §6.1) names each lifted unit's closure type; a unit it omits is
    TP-type, as every split of SYN-001's own flowsheet is. `band_routes` are the units whose
    traversal closure answered by the band route (ADR 0012 D10 F1), recorded under v2 before
    attempt 0 (§6.5). `zero_flow_forms` (spec §6.1, §7.2; `splits.zero_flow_forms`) is each
    split's `ZERO_FLOW` form; a split that enters `ZERO_FLOW` without one is a defect
    (`ValueError`). `dormancy_forms` (spec §7.6–§7.8; `splits.dormancy_forms`) are the flowsheet's
    dormancy-form outlets in declaration order; those of the region's units carry the attempt's
    signature items. `split_temperatures` (spec §6.2 step 3 as amended;
    `splits.split_temperatures`) are each split's temperature columns, which an opening from a PH
    closure sets to its `T`; a PH-type split without them under v2 is a defect (`ValueError`).
    Under v1 none of the five is read. `vapour_only_forms` (M02 design note §14.2 B13;
    `splits.vapour_only_forms`) are the splits' vapour-only forms, read in every `TWO_PHASE`
    attempt; SYN-001's splits have none. `split_owners` (S11 §10.2, `splits.split_owners`) maps a
    staged unit's split keys to the instance that owns them: a split is active iff its owner is
    one of `region.units`, and opens at its owner's position; a key it omits is its own owner.

    Under `policy.globalization.eo_core = "ptc"` (T04 §7.1) every attempt runs the PTC core on
    `mass_mapping`'s holdups, validated before anything is evaluated: a mapping that fails T04
    §7.2 — `None` included, which maps nothing — ends the solve `PTC_MAPPING_INVALID` with no
    attempt opened. A recovery solve is the exception: its attempt 0 is the homotopy, and every
    later attempt Newton's (T04 §4.5).

    `item0_opening_source` is item 0's `opening_source` when there is no `recovery`: the
    registered `initializer`, or `eo_recovery_start` for edge 3's sequential restart (ADR 0015
    D3), a fresh initializer output that §6.2 projects as any other start.

    `warm_start` (ADR 0024 D3; T08 build-first spec §B2) says `state` is a compatible warm start:
    attempt 0's opening, after §6.2 and before its pinned columns are set, is held to T03 §5.1's
    six checks (`check_opening`) in place of the silent pin a `user_start` gets. A refusal ends the
    solve `INITIALIZATION_FAILED`, `warm_start_rejected(opening:<check>)`, with no attempt opened,
    and the caller takes the next source; a pass records `initializer_accepted`
    (`compatible_warm_start`) before the attempt opens. Not read with `recovery`.

    With `recovery` (T04 §5.3) it is edge 3's recovery solve: attempt 0 opens at the failed solve's
    item-0 opening (already projected, so §6.2 does not run again) and runs the homotopy core,
    whose λ < 1 levels `compile_level` compiles from the re-bound declaration; every attempt the
    contract opens after it runs the Newton core on the target (T04 §4.5). A recovery with a
    `reported_signature` (RRC design note §5.7, a revision continuation) opens attempt 0 the same
    way, at the ancestor's root, and holds that opening to the six checks first, with the reported
    signature as the source's: a refusal ends the solve `INITIALIZATION_FAILED`,
    `revision_continuation_rejected(opening:<check>:<subject>)`, with no attempt opened and no
    event, and the caller records it and takes the restart.

    A provider that will not split a lifted stream — at the start, at an admissibility check or at
    a kernel verdict — ends the solve `EVALUATION_ERROR` naming the stream and the provider's
    status (review S5). The attempts before it are on the trace; the result carries the supplied
    state, because no attempt's end state was kept as a point to report.
    """
    try:
        return _solve_region(
            compiled=compiled,
            spec=spec,
            region=region,
            state=state,
            splits=splits,
            provider=provider,
            policy=policy,
            trace=trace,
            initializer_source=initializer_source,
            recovery=recovery,
            compile_level=compile_level,
            mass_mapping=mass_mapping,
            closure_types=closure_types,
            band_routes=band_routes,
            zero_flow_forms=zero_flow_forms,
            dormancy_forms=dormancy_forms,
            split_temperatures=split_temperatures,
            item0_opening_source=item0_opening_source,
            warm_start=warm_start,
            vapour_only_forms=vapour_only_forms,
            split_owners=split_owners,
        )
    except _KernelRefusedError as refused:
        return RegionResult(
            outcome="EVALUATION_ERROR",
            state={name: float(state[name]) for name in spec.variable_ids},
            attempts=(),
            message=str(refused),
        )


def _solve_region(
    *,
    compiled: CompiledProblem,
    spec: ProblemSpec,
    region: Region,
    state: Mapping[str, float],
    splits: Sequence[LiftedSplit],
    provider: PropertyProvider,
    policy: SolvePolicy,
    trace: Trace | None,
    initializer_source: str | None,
    recovery: RecoveryStart | None = None,
    compile_level: Callable[[ProblemSpec], CompiledProblem] | None = None,
    mass_mapping: MassMapping | None = None,
    closure_types: Mapping[str, ClosureType] | None = None,
    band_routes: Sequence[str] = (),
    zero_flow_forms: Mapping[str, ZeroFlowForm] | None = None,
    dormancy_forms: Sequence[DormancyForm] = (),
    split_temperatures: Mapping[str, tuple[str, ...]] | None = None,
    item0_opening_source: Literal["initializer", "eo_recovery_start"] = "initializer",
    warm_start: bool = False,
    vapour_only_forms: Mapping[str, VapourOnlyForm] | None = None,
    split_owners: Mapping[str, str] | None = None,
) -> RegionResult:
    if recovery is not None and compile_level is None:
        raise ValueError("a recovery solve compiles its λ-levels, and was given no compiler")
    run = trace if trace is not None else Trace()
    identity = (compiled.metadata.model_version, compiled.metadata.constants_sha256)

    # T04 §7.1–§7.2: the PTC core's mass mapping, refused before any call when it is invalid.
    region_mass: RegionMass | None = None
    if policy.globalization.eo_core == "ptc" and recovery is None:
        resolved = resolve_mass(
            mass_mapping,
            spec=spec,
            rows=region.row_ids,
            residence_time=policy.globalization.ptc.residence_time_s,
        )
        if isinstance(resolved, MappingRefusal):
            return RegionResult(
                outcome="PTC_MAPPING_INVALID",
                state={name: float(state[name]) for name in spec.variable_ids},
                attempts=(),
                message=resolved.message,
            )
        region_mass = resolved

    context = _new_context(identity)
    scaling = Scaling.from_spec(spec)
    # S11 §10.2 (R-822): a split is active iff its owner is a unit of the region.
    owners: Mapping[str, str] = split_owners or {}
    inside = set(region.units)
    active_splits = [split for split in splits if owners.get(split.unit, split.unit) in inside]
    structure = compiled.structural_pattern() if hasattr(compiled, "structural_pattern") else None

    # T05b spec §6.6: v2's rules (§6.2–§6.5) are gated on the literal; under v1 no split is PH-type.
    v2 = policy.phase_contract == CONTRACT_V2
    ph_units = frozenset(
        unit for unit, kind in (closure_types or {}).items() if kind == "PH" and v2
    )
    forms: Mapping[str, ZeroFlowForm] = zero_flow_forms or {}
    vapour: Mapping[str, VapourOnlyForm] = vapour_only_forms or {}
    temperatures: Mapping[str, tuple[str, ...]] = split_temperatures or {}
    for split in active_splits:
        if split.unit in ph_units and split.unit not in temperatures:
            raise ValueError(
                f"defect: {split.unit} is PH-type and the region has no temperature columns for it"
            )
    # T05b spec §7.8, §7.10: the dormancy forms of the region's units, read only under v2.
    units = set(region.units)
    dormancy = tuple(form for form in dormancy_forms if form.unit in units) if v2 else ()

    current = {name: float(state[name]) for name in spec.variable_ids}
    # T05b spec §7.8 (ii) as amended: the opening fixed point's pass order, and attempt 0's item
    # reference — the items of the start as supplied, before any projection.
    order = _opening_order(active_splits, dormancy, region.units, owners) if v2 else ()
    supplied_items = frozenset(item for item, _ in _items(dormancy, current))
    solve = _RegionSolve(
        spec=spec,
        region=region,
        splits=splits,
        provider=provider,
        policy=policy,
        run=run,
        identity=identity,
        scaling=scaling,
        structure=structure,
        region_mass=region_mass,
        active_splits=active_splits,
        v2=v2,
        ph_units=ph_units,
        forms=forms,
        vapour=vapour,
        temperatures=temperatures,
        dormancy=dormancy,
        order=order,
        recovery=recovery,
        warm_start=warm_start,
        current=current,
        source=item0_opening_source if recovery is None else "eo_recovery_start",
    )
    start_refusal = solve._open_start(context, supplied_items, band_routes)
    if start_refusal is not None:
        return start_refusal

    for attempt_index in range(policy.max_attempts):
        if v2:
            solve._check_dormancy(attempt_index)
        layout = solve._layout()
        solve.used.append(layout.opening)
        if len(layout.free) != len(layout.attempt_rows):
            return solve.closed(
                "UNSUPPORTED_RANK_STRUCTURE",
                f"the region with signature {layout.opening} is {len(layout.attempt_rows)} x "
                f"{len(layout.free)}, not square",
            )
        external_refusal = solve._external_refusal(attempt_index, layout)
        if external_refusal is not None:
            return external_refusal
        attempt_open = solve._open(attempt_index, layout)
        record: HomotopyRecord | None = None
        ptc_record: PtcRecord | None = None
        if attempt_open.continuing:
            assert recovery is not None and compile_level is not None
            last, record = _homotopy(
                recovery=recovery,
                compiled=compiled,
                compile_level=compile_level,
                spec=spec,
                scaling=scaling,
                opening_state=dict(solve.current),
                free=layout.free,
                rows=layout.rows,
                splits=active_splits,
                regimes=solve.regimes,
                provider=provider,
                policy=policy,
                attempt_context=attempt_open.attempt_context,
                trace=run,
                attempt_index=attempt_index,
                signature=layout.opening,
                counters=solve.counters,
                x0=attempt_open.x0,
                ph_units=ph_units,
                v2=v2,
                labels=layout.labels,
                dormancy=dormancy,
            )
            solve.homotopy = record
        elif region_mass is not None:
            last, ptc_record = _ptc_attempt(
                temperatures=temperatures,
                memo=attempt_open.memo,
                region_mass=region_mass,
                compiled=compiled,
                spec=spec,
                scaling=scaling,
                base=solve.current,
                free=layout.free,
                rows=layout.rows,
                splits=active_splits,
                regimes=solve.regimes,
                provider=provider,
                policy=policy,
                attempt_context=attempt_open.attempt_context,
                trace=run,
                attempt_index=attempt_index,
                signature=layout.opening,
                counters=solve.counters,
                wall=attempt_open.wall,
                x0=attempt_open.x0,
                ph_units=ph_units,
                v2=v2,
                labels=layout.labels,
                dormancy=dormancy,
            )
        else:
            screen = _attempt_screen(
                splits=active_splits,
                regimes=solve.regimes,
                provider=provider,
                context=attempt_open.attempt_context,
                epsilon=policy.admissibility_epsilon,
                ph_units=ph_units,
                v2=v2,
                dormancy=dormancy,
                temperatures=temperatures,
                memo=attempt_open.memo,
            )
            problem = _region_problem(
                compiled,
                attempt_open.attempt_context,
                spec,
                scaling,
                solve.current,
                layout.free,
                layout.rows,
                screen,
                attempt_open.x0,
                **_with_labels(layout.labels),
            )
            last = solve_newton(
                problem,
                attempt_open.x0,
                policy,
                trace=run,
                signature=layout.opening,
                attempt=attempt_index,
                counters=solve.counters,
                observer=attempt_open.wall,
                # T05b spec §7.8 (iii) (Q-S4 (6)): every trial of a v2 attempt in a region with a
                # dormancy-form outlet is screened, an empty signature included; `dormancy` is
                # empty under v1.
                compare_empty=bool(dormancy),
                # ADR 0018 D1: the target's Newton attempts only — never the homotopy corrector
                # (`_homotopy`) or the PTC core.
                refinement=_refinement(policy, spec, layout.free),
            )
        solve.counters = last.counters
        for position, name in enumerate(layout.free):
            solve.current[name] = float(last.x[position])
        for name in layout.pinned:
            solve.current[name] = 0.0
        ended = dict(solve.current)

        ops = _LiftedOps(
            splits=active_splits,
            regimes=solve.regimes,
            end_state=ended,
            free=layout.free,
            provider=provider,
            context=attempt_open.attempt_context,
            policy=policy,
            region=region,
            spec=spec,
            identity=identity,
            ph_units=ph_units,
            v2=v2,
            forms=forms,
            dormancy=dormancy,
            items=frozenset(item for item, _ in layout.items),
            order=order,
            temperatures=temperatures,
            memo=attempt_open.memo,
            vapour_only=vapour,
        )
        try:
            decision = decide(
                last,
                attempt_index=attempt_index,
                frozen=layout.opening,
                wall=attempt_open.wall,
                ops=ops,
                policy=policy,
                used=solve.used,
            )
        except BudgetExhaustedError as exhausted:
            # The closure's kernel calls (an end-state verdict, a restart point) are provider calls
            # outside the compiled residual (review S1). A refusal there closes this attempt: its
            # end state, checkpoint and provenance are kept, never discarded with the loop.
            decision = Decision("terminal", "BUDGET_EXHAUSTED", str(exhausted))
            solve.budget = "property_calls"
        except _KernelRefusedError as refused:
            decision = Decision("terminal", "EVALUATION_ERROR", str(refused))
        except OpeningNotSettledError as unsettled:
            # T05b spec §7.8 (ii) 2: a restart opening whose fixed point does not settle.
            decision = opening_not_settled(unsettled)
        if decision.kind == "converged" and v2:
            # T05b spec §7.8 (iv) 2 (finding F6): after the contract's closure found the root
            # admissible and its items in agreement, every row a zero-flow form swapped out —
            # lifted, then non-lifted, in signature order — must hold there.
            swapped = (
                *(
                    _form(split, forms).swapped
                    for split in active_splits
                    if solve.regimes[split.unit] == "ZERO_FLOW" and _form(split, forms).swapped
                ),
                *(form.swapped for form in layout.running),
            )
            if swapped:
                decision = (
                    _swapped_row_test(compiled, attempt_open.attempt_context, spec, ended, swapped)
                    or decision
                )
        outcome: SolveOutcome = decision.outcome
        if outcome == "BUDGET_EXHAUSTED" and solve.budget is None:
            solve.budget = last.budget
        solve.attempts.append(
            RegionAttempt(
                layout.opening,
                outcome,
                last.iterations,
                decision.cause if decision.kind == "restart" else "",
                solver_outcome=last.outcome,
                end_state=ended,
                observations=dict(decision.observations),
                ptc=ptc_record,
            )
        )
        # K03 §9: a checkpoint for an attempt that accepted a step or converged. Only an attempt
        # the region *kept* is a candidate root; one converged on an inadmissible branch is not.
        if last.accepted_any or last.converged:
            solve.checkpoint = Checkpoint(
                checkpoint_id=f"region-attempt-{attempt_index}",
                attempt_index=attempt_index,
                iteration=last.iterations,
                variable_ids=layout.free,
                state_sha256=state_sha256(last.x, layout.free),
                signature=layout.opening,
                residual_inf_unscaled=last.residual_inf,
                merit=last.merit,
                label="candidate_root" if decision.kind == "converged" else "partial",
                # T04 §4.4: a homotopy checkpoint names its level; below λ = 1 it is a state of a
                # modified problem, and the dataclass refuses to call it anything but partial.
                continuation_lambda=(
                    fraction_string(record.lambda_reached) if record is not None else None
                ),
            )
        solve.provenance.append(
            provenance_item(
                attempt=attempt_index,
                signature=layout.opening,
                core=attempt_open.core,
                source=solve.source,
                initializer_source=(
                    (recovery.initializer_source if recovery is not None else initializer_source)
                    if attempt_index == 0
                    else None
                ),
                trial=solve.trial,
                opening_state_sha256=attempt_open.opening_hash,
                result=last,
                decision=decision,
                continuation=record.provenance() if record is not None else None,
            )
        )
        if decision.kind == "converged":
            # OPT design §4.2.1: the system this attempt solved — its rows, free columns and label
            # rows, and every other column at the value it held (the end state's: the attempt
            # wrote only its free columns, and re-pinned its pinned ones at +0.0).
            kept = set(layout.free)
            return solve.closed(
                "CONVERGED",
                system=AttemptSystem(
                    rows=tuple(layout.rows),
                    free=tuple(layout.free),
                    held={
                        name: solve.current[name] for name in spec.variable_ids if name not in kept
                    },
                    labels=tuple(layout.labels),
                    signature=layout.opening,
                ),
            )
        if decision.kind == "terminal":
            return solve.closed(decision.outcome, decision.message)
        conversion = decision.conversion
        assert conversion is not None
        opened, new_regimes = conversion.opening
        solve.current = dict(opened)
        solve.regimes = dict(new_regimes)
        solve.message = decision.message
        solve.source = conversion.source
        solve.trial = conversion.trial

    raise AssertionError("unreachable: the restart gate ends the solve at max_attempts")


@dataclass
class _RegionSolve:
    """One `_solve_region` call: what its start, openings and closing read, and its ledger.

    Frame: `spec`, the `region`, `splits` (every lifted split of the declaration, for the root's
    branch), the `provider`, `policy`, the trace `run`, `identity`, the `scaling`, the compiled
    `structure` and the PTC core's `region_mass`, phase B's contract setting (`active_splits`,
    `v2`, `ph_units`, the zero-flow `forms`, the `vapour` forms, `temperatures`, the `dormancy`
    forms, the opening `order`), the `recovery` start and `warm_start`. State: the opening state
    `current` and `regimes`, the start's `projections`, and the ledger (counters, used signatures,
    attempts, provenance, checkpoint, contexts, the next attempt's opening message, source and
    trial, attempt 0's opening, the budget kind and the homotopy record).
    """

    spec: ProblemSpec
    region: Region
    splits: Sequence[LiftedSplit]
    provider: PropertyProvider
    policy: SolvePolicy
    run: Trace
    identity: tuple[str, str]
    scaling: Scaling
    structure: Sequence[tuple[str, str]] | None
    region_mass: RegionMass | None
    active_splits: list[LiftedSplit]
    v2: bool
    ph_units: frozenset[str]
    forms: Mapping[str, ZeroFlowForm]
    vapour: Mapping[str, VapourOnlyForm]
    temperatures: Mapping[str, tuple[str, ...]]
    dormancy: tuple[DormancyForm, ...]
    order: tuple[OpeningEntry, ...]
    recovery: RecoveryStart | None
    warm_start: bool
    current: dict[str, float]
    source: OpeningSource
    projections: list[str] = field(default_factory=list)
    regimes: dict[str, Regime] = field(default_factory=dict)
    counters: Counters = field(default_factory=Counters)
    used: list[AttemptSignature] = field(default_factory=list)
    attempts: list[RegionAttempt] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: Checkpoint | None = None
    contexts: list[AttemptContext] = field(default_factory=list)
    message: str = "initial"
    trial: Candidate | None = None
    opened_at: tuple[Mapping[str, float], Mapping[str, Regime]] | None = None
    budget: str | None = None
    homotopy: HomotopyRecord | None = None

    def _open_start(
        self, context: EvaluationContext, reference: frozenset[str], band_routes: Sequence[str]
    ) -> RegionResult | None:
        """Attempt 0's start: a recovery's opening, or the supplied state projected onto the
        kernel's (`_project_start`) and settled by §7.8 (ii)'s fixed point (`_settle_start`); then
        the start's records (`_record_start`).

        Writes `current`, `regimes` and `projections`, and records into `run` through
        `_project_start`, `_settle_start` and `_record_start`. `reference` is attempt 0's item
        reference, the items of the start as supplied; `band_routes` are §6.5's. Returns
        `_settle_start`'s refusal when the fixed point cycles, else None: attempt 0 may open.
        """
        if self.recovery is not None:
            # T04 §5.3: the failed solve's item-0 opening, projected and pinned already.
            self.current = {
                name: float(self.recovery.state[name]) for name in self.spec.variable_ids
            }
            self.regimes = {
                split.unit: self.recovery.regimes[split.unit] for split in self.active_splits
            }
        self._project_start(context)
        if self.order and self.recovery is None:
            start_refusal = self._settle_start(context, reference)
            if start_refusal is not None:
                return start_refusal
        self._record_start(band_routes)
        return None

    def _project_start(self, context: EvaluationContext) -> None:
        """T05b spec §6.2 on the supplied start (none for a recovery start): each lifted split's
        answer (`_start_answer`): its regime written into `regimes` and the kernel's values, when
        there are any (not for a PH-type split, §6.4), into `current`; a split the kernel's values
        overwrite is appended to `projections` and recorded into `run` after its own kernel call,
        before the next split's.
        """
        # §6.2: every lifted split of x⁰ is the kernel's; a supplied split that disagrees is
        # overwritten and the overwrite recorded, which is what keeps EO-TRIV off its trivial root.
        for split in self.active_splits if self.recovery is None else ():
            regime, kernel = self._start_answer(context, split)
            if kernel is not None:
                if any(
                    abs(self.current[name] - value) > 1e-12 * max(1.0, abs(value))
                    for name, value in kernel.items()
                ):
                    self.projections.append(split.stream)
                    # ADR 0009 D3's grammar, on existing kinds (K03 A08's precedent for a projected
                    # guess): the candidate names what was supplied and what the kernel says.
                    branch = _branch(split, self.current, self.v2)
                    self.run.record(
                        kind="initializer_candidate",
                        attempt=0,
                        iteration=0,
                        signature=(),
                        state_sha256="",
                        residual_inf_unscaled=float("nan"),
                        merit=float("nan"),
                        counters=Counters(),
                        message=f"projected({split.stream}, {branch}, {regime})",
                    )
                self.current.update(kernel)
            self.regimes[split.unit] = regime

    def _start_answer(
        self, context: EvaluationContext, split: LiftedSplit
    ) -> tuple[Regime, Mapping[str, float] | None]:
        """§6.2's answer for one lifted split of the start at `current`: its regime and the
        kernel's values for it, or None for the values when the split is PH-type and not
        re-projected (§6.4). Pure: it writes nothing of the run (the kernel is a provider call).
        """
        if self.v2 and _dormant_feed(split, self.current):
            # T05b spec §7.1: selected by exact dormancy, for either closure type; §7.4: its
            # lifted flows are pinned at `+0.0` (an overwritten supplied split is recorded).
            return "ZERO_FLOW", _zero_flow_answer(split).values
        if split.unit in self.ph_units and _branch_found(split, self.current) != "ZERO_FLOW":
            # §6.4 (ADR 0012 D4 (b)): a PH-type split is not re-projected; it opens with the
            # traversal closure's split (D5), in the regime of its branch. An empty split of a
            # flowing feed carries no enthalpy, so it leaves `ZERO_FLOW` by the TP flash below
            # (§7.4), projected as a TP-type split is.
            return _branch_found(split, self.current), None
        return _kernel(self.provider, context, split, self.current)

    def _settle_start(
        self, context: EvaluationContext, reference: frozenset[str]
    ) -> RegionResult | None:
        """T05b spec §7.8 (ii) as amended (Q-S9, R-065; review M1): after the start rules, one
        fixed point over the lifted splits' `ZERO_FLOW` membership and the items, so that a
        projection of an earlier split that changes a later one's feed (or a trigger) is carried
        through, in any declaration order. Each split change is recorded as a projection (§6.4);
        an item change by the signature alone. (A recovery start is a settled attempt-0 opening.)

        Writes `current`, `regimes`, `projections` and the projection records into `run`;
        `reference` is attempt 0's item reference. Returns §7.8 (ii) 2's cycling refusal (with the
        state before the fixed point and the projections so far) when the opening does not
        settle, else None.
        """
        try:
            self.current, self.regimes, _, changes = _settle(
                self.current,
                self.regimes,
                order=self.order,
                reference=reference,
                leave=lambda split, at: _contract_kernel(
                    self.provider,
                    context,
                    split,
                    at,
                    self.ph_units,
                    v2=True,
                    regime="ZERO_FLOW",
                    temperatures=self.temperatures.get(split.unit),
                ),
            )
        except OpeningNotSettledError as unsettled:
            # §7.8 (ii) 2: the contract's cycling refusal, before any attempt opened.
            refusal = opening_not_settled(unsettled)
            return RegionResult(
                outcome=refusal.outcome,
                state=dict(self.current),
                attempts=(),
                projections=tuple(self.projections),
                message=refusal.message,
            )
        for change in changes:
            if change.split.stream not in self.projections:
                self.projections.append(change.split.stream)
            self.run.record(
                kind="initializer_candidate",
                attempt=0,
                iteration=0,
                signature=(),
                state_sha256="",
                residual_inf_unscaled=float("nan"),
                merit=float("nan"),
                counters=Counters(),
                message=f"projected({change.split.stream}, {change.branch}, {change.regime})",
            )
        return None

    def _record_start(self, band_routes: Sequence[str]) -> None:
        """The start's records into `run`: the accepted start when a split was projected, then
        under v2 (not for a recovery start) §6.5's band routes (`band_routes`) and their accepted
        start.
        """
        if self.projections:
            projected = len(self.projections)
            self.run.record(
                kind="initializer_accepted",
                attempt=0,
                iteration=0,
                signature=(),
                state_sha256="",
                residual_inf_unscaled=float("nan"),
                merit=float("nan"),
                counters=Counters(),
                message=f"the start with {projected} split(s) projected onto the kernel's",
            )
        if self.v2 and self.recovery is None and band_routes:
            # §6.5 (ADR 0012 D10 F1): the traversal's band routes, after §6.2's projection records,
            # in declaration order, on T02 §6.2's existing pair of kinds.
            for unit in band_routes:
                self.run.record(
                    kind="initializer_candidate",
                    attempt=0,
                    iteration=0,
                    signature=(),
                    state_sha256="",
                    residual_inf_unscaled=float("nan"),
                    merit=float("nan"),
                    counters=Counters(),
                    message=f"closure_route({unit}, band)",
                )
            self.run.record(
                kind="initializer_accepted",
                attempt=0,
                iteration=0,
                signature=(),
                state_sha256="",
                residual_inf_unscaled=float("nan"),
                merit=float("nan"),
                counters=Counters(),
                message=f"the start with {len(band_routes)} closure(s) from the band route",
            )

    def _check_dormancy(self, attempt_index: int) -> None:
        """T05b spec §7.1 under v2 (the caller's test): `ZERO_FLOW` exactly when the feed is
        dormant, for every active split at the opening of attempt `attempt_index` (`current`,
        `regimes`). Every opening, attempt 0's start and every restart, ends in §7.8 (ii)'s fixed
        point (`_settle`), which makes it so; this guard stays behind it (Q-S9), and a
        disagreement raises a `RuntimeError` naming the defect.
        """
        for split in self.active_splits:
            if _dormant_feed(split, self.current) != (self.regimes[split.unit] == "ZERO_FLOW"):
                raise RuntimeError(
                    f"defect: {split.unit} opens attempt {attempt_index} in "
                    f"{self.regimes[split.unit]} with its feed "
                    f"{'dormant' if _dormant_feed(split, self.current) else 'flowing'}"
                )

    def _layout(self) -> _Layout:
        """The attempt's layout at its opening (`current`, `regimes`): T05b spec §7.8 (i)–(ii)'s
        signature, the columns it pins and the rows it drops, its label rows, and §7.2's system.
        Pure.
        """
        # T05b spec §7.8 (i)–(ii): the lifted regimes, then the items of the opening state.
        items = _items(self.dormancy, self.current)
        running = [form for form in self.dormancy if (form.item, "ZERO_FLOW") in items]
        opening = (
            *((split.unit, self.regimes[split.unit]) for split in self.active_splits),
            *items,
        )
        pinned = {
            name
            for split in self.active_splits
            for name in _pinned(split, self.regimes[split.unit], self.forms, self.vapour)
        }
        dropped = {
            name
            for split in self.active_splits
            for name in _dropped(split, self.regimes[split.unit], self.forms, self.vapour)
        } | {form.swapped for form in running}
        labels = (
            *_labels(self.active_splits, self.regimes, self.forms),
            *(form.label for form in running),
        )
        free = tuple(name for name in self.region.variable_ids if name not in pinned)
        rows = tuple(name for name in self.region.row_ids if name not in dropped)
        # T05b spec §7.2: the attempt's system is its compiled rows, then its label rows.
        attempt_rows = (*rows, *(label for label, _, _ in labels))
        return _Layout(
            opening=opening,
            items=items,
            running=running,
            pinned=pinned,
            dropped=dropped,
            labels=labels,
            free=free,
            rows=rows,
            attempt_rows=attempt_rows,
        )

    def _external_refusal(self, attempt_index: int, layout: _Layout) -> RegionResult | None:
        """Attempt 0's checks of an external start at `current` against `layout`'s opening: a
        revision continuation's (RRC design note §5.7), then a warm start's (ADR 0024 D3), whose
        acceptance it records into `run`. Returns the `INITIALIZATION_FAILED` result of a refused
        check (`closed`), else None: the attempt may open.
        """
        if (
            self.recovery is not None
            and self.recovery.reported_signature is not None
            and attempt_index == 0
        ):
            # RRC design note §5.7: a revision continuation opens at an external root — the
            # ancestor certificate's — so it is checked as a warm start is, against the signature
            # the certificate reported, before its pinned columns are set. The identity pair is
            # the requirement's: R5 and R8 established it (`revision_continuation`).
            refused = _external_opening(
                self.current,
                layout.opening,
                self.identity,
                layout.free,
                self.active_splits,
                self.regimes,
                self.forms,
                self.vapour,
                self.spec,
                reported=self.recovery.reported_signature,
            )
            if refused is not None:
                return self.closed(
                    "INITIALIZATION_FAILED",
                    f"{REVISION_CONTINUATION_REJECTED}(opening:{refused.check}:{refused.subject})",
                )
        if self.warm_start and attempt_index == 0 and self.recovery is None:
            # ADR 0024 D3: an external start is checked, not silently pinned — T03 §5.1 on the
            # opening this attempt would take, in place of `CHECKPOINT_INCOMPATIBLE`.
            refused = _external_opening(
                self.current,
                layout.opening,
                self.identity,
                layout.free,
                self.active_splits,
                self.regimes,
                self.forms,
                self.vapour,
                self.spec,
            )
            if refused is not None:
                return self.closed(
                    "INITIALIZATION_FAILED", f"{WARM_START_REJECTED}(opening:{refused.check})"
                )
            self.run.record(
                kind="initializer_accepted",
                attempt=0,
                iteration=0,
                signature=(),
                state_sha256="",
                residual_inf_unscaled=float("nan"),
                merit=float("nan"),
                counters=Counters(),
                message=WARM_START_SOURCE,
            )
        return None

    def _open(self, attempt_index: int, layout: _Layout) -> _Opened:
        """Opens attempt `attempt_index` at `layout`: its pinned columns set to `+0.0` in
        `current` (attempt 0's opening kept in `opened_at`, as copies), its core, evaluation
        context and closure memo, its `AttemptContext` appended to `contexts`, its
        `attempt_opened` record into `run`, and its wall observer.
        """
        for name in layout.pinned:
            self.current[name] = 0.0
        if attempt_index == 0:
            self.opened_at = (dict(self.current), dict(self.regimes))
        # T04 §4.5: a recovery's attempt 0 is the homotopy; every later attempt is Newton's.
        # T04 §7.1: otherwise the policy's EO core, PTC for every attempt when it says so.
        continuing = self.recovery is not None and attempt_index == 0
        core: AttemptCore = (
            "homotopy" if continuing else "ptc" if self.region_mass is not None else "newton"
        )
        attempt_context = _new_context(self.identity)
        # T05b spec §6.2 as amended ("carrying"): the PH closures this attempt's screen asks,
        # reused by its openings at the same state.
        memo: ClosureMemo = {}
        x0 = np.array([self.current[name] for name in layout.free], dtype=np.float64)
        self.contexts.append(
            AttemptContext(
                attempt_index=attempt_index,
                signature=layout.opening,
                evaluation_context=attempt_context,
                flowsheet_context=attempt_context,
                column_scales={name: self.scaling.column[name] for name in layout.free},
                row_scales={
                    **{name: self.scaling.row[name] for name in layout.rows},
                    **{label: REGISTERED_NOMINALS[LABEL_KIND] for label, _, _ in layout.labels},
                },
                counters_at_open=self.counters,
                opened_reason="initial" if attempt_index == 0 else "phase_update",
                opened_from=self.checkpoint,
                active_phases=layout.opening,
                jacobian_pattern=(
                    jacobian_pattern(
                        (*self.structure, *_label_entries(layout.labels)),
                        layout.attempt_rows,
                        layout.free,
                    )
                    if self.structure is not None
                    else None
                ),
                core=core,
                continuation=(
                    self.recovery.continuation.as_context()
                    if continuing and self.recovery is not None
                    else None
                ),
            )
        )
        opening_hash = state_sha256(x0, layout.free)
        self.run.record(
            kind="attempt_opened",
            attempt=attempt_index,
            iteration=0,
            signature=layout.opening,
            state_sha256=opening_hash,
            residual_inf_unscaled=float("nan"),
            merit=float("nan"),
            counters=self.counters,
            alpha=self.trial.alpha if self.trial is not None else None,
            message=self.message,
        )
        wall = WallObserver(self.policy)
        return _Opened(
            continuing=continuing,
            core=core,
            attempt_context=attempt_context,
            memo=memo,
            x0=x0,
            opening_hash=opening_hash,
            wall=wall,
        )

    def closed(
        self, outcome: SolveOutcome, text: str = "", system: AttemptSystem | None = None
    ) -> RegionResult:
        fingerprint = None
        if outcome == "CONVERGED":
            fingerprint = root_fingerprint(
                model_version=self.identity[0],
                constants_sha256=self.identity[1],
                variable_ids=self.spec.variable_ids,
                # Every lifted split of the declaration, from the state (review M1): a root's
                # branch is where it is, not which units this region happened to hold.
                branch_found=branch_found(self.splits, self.current),
                full_state_sha256=state_sha256(self.current, self.spec.variable_ids),
            )
        return RegionResult(
            outcome=outcome,
            state=dict(self.current),
            attempts=tuple(self.attempts),
            projections=tuple(self.projections),
            counters=self.counters,
            message=text,
            checkpoint=self.checkpoint,
            contexts=tuple(self.contexts),
            branch_provenance=tuple(self.provenance),
            root_fingerprint=fingerprint,
            opening=self.opened_at,
            budget=self.budget if outcome == "BUDGET_EXHAUSTED" else None,
            homotopy=self.homotopy,
            final_system=system,
        )


class _Layout(NamedTuple):
    """An attempt's layout (`_RegionSolve._layout`): its signature `opening` (the lifted regimes,
    then the `items`), the dormancy forms `running` in it, the `pinned` columns and `dropped` rows,
    the `labels` rows, the `free` columns and compiled `rows`, and the system's `attempt_rows`.
    """

    opening: AttemptSignature
    items: AttemptSignature
    running: list[DormancyForm]
    pinned: set[str]
    dropped: set[str]
    labels: tuple[tuple[str, str, str], ...]
    free: tuple[str, ...]
    rows: tuple[str, ...]
    attempt_rows: tuple[str, ...]


class _Opened(NamedTuple):
    """An opened attempt (`_RegionSolve._open`): `continuing` (a recovery's attempt 0, the
    homotopy), its `core`, its `attempt_context` and closure `memo`, its start `x0` over the free
    columns with its `opening_hash`, and its `wall` observer.
    """

    continuing: bool
    core: AttemptCore
    attempt_context: EvaluationContext
    memo: ClosureMemo
    x0: npt.NDArray[np.float64]
    opening_hash: str
    wall: WallObserver


def _new_context(identity: tuple[str, str]) -> EvaluationContext:
    # T03 §4.2: every attempt constructs its own context objects (field-equal on this path).
    return EvaluationContext(
        model_version=identity[0], constants_sha256=identity[1], phase_signature=None
    )


def _swapped_row_test(
    compiled: CompiledProblem,
    context: EvaluationContext,
    spec: ProblemSpec,
    state: Mapping[str, float],
    swapped: Sequence[str],
) -> Decision | None:
    """T05b spec §7.8 (iv) 2: each swapped row, in signature order, at the final state against its
    kind's tolerance (K03 §5.2's per-row test). The first that fails closes the region
    `SPECIFICATION_CONFLICT`, `zero_flow_conflict(<row id>)`, its value in the non-R0
    observations; no restart is proposed (the retained rows fix the row's value). `None` when
    every one holds."""
    vector = np.array([state[name] for name in spec.variable_ids], dtype=np.float64)
    result = compiled.residual(vector, context)
    if result.status != "ok" or result.values is None:
        return Decision(
            "terminal",
            "EVALUATION_ERROR",
            f"the swapped rows could not be evaluated at the final state: {result.status}: "
            f"{result.message}",
        )
    at = {name: index for index, name in enumerate(spec.equation_ids)}
    for row in swapped:
        value = float(result.values[at[row]])
        if not abs(value) <= KIND_TOLERANCE[spec.row_kinds[row]]:
            return Decision(
                "terminal",
                "SPECIFICATION_CONFLICT",
                f"zero_flow_conflict({row})",
                observations={f"swapped_row:{row}": value},
            )
    return None


def _external_opening(
    current: Mapping[str, float],
    opening: AttemptSignature,
    identity: tuple[str, str],
    free: Sequence[str],
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    forms: Mapping[str, ZeroFlowForm],
    vapour: Mapping[str, VapourOnlyForm],
    spec: ProblemSpec,
    *,
    reported: AttemptSignature | None = None,
) -> OpeningRefusal | None:
    """T03 §5.1's six checks on attempt 0's opening from an external start (a compatible warm
    start, ADR 0024 D3; a revision continuation's ancestor root, RRC §5.7), before its pinned
    columns are set: the opening's own identity, its signature's pinned columns in signature
    order, and a zero lower bound on every free molar flow. `reported` is the signature the
    source reported for the state, `None` for a source that reports none."""
    held = tuple(
        name for split in splits for name in _pinned(split, regimes[split.unit], forms, vapour)
    )
    return check_opening(
        OpeningState(
            values=current,
            model_version=identity[0],
            constants_sha256=identity[1],
            reported=reported,
        ),
        OpeningRequirement(
            signature=opening,
            model_version=identity[0],
            constants_sha256=identity[1],
            free=free,
            pinned=held,
            lower_bounds={
                name: 0.0 for name in free if spec.variable_kinds.get(name) == "molar_flow"
            },
        ),
    )
