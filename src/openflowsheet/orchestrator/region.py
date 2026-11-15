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

**Where the code is** (S19 B1). This module holds the region's records, the attempt loop
(`solve_region`, `_solve_region`), the trial screen, PTC and the homotopy. The phase-policy kernel
(the kernel, the PH closure, the admissibility screens and their refusals) is in
`orchestrator.region_phase`, the Newton problem over lifted splits (labels, the opening fixed
point, dormancy outlets, `_LiftedOps`) in `orchestrator.region_problem`; `region` re-exports what
its callers and tests read there.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

import numpy as np

from openflowsheet.canonical import state_sha256
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models.lifted import INADMISSIBLE_BRANCH as INADMISSIBLE_BRANCH
from openflowsheet.models.lifted import LABEL_KIND as LABEL_KIND
from openflowsheet.models.lifted import Branch as Branch
from openflowsheet.models.lifted import ClosureType as ClosureType
from openflowsheet.models.lifted import DormancyForm as DormancyForm
from openflowsheet.models.lifted import LiftedSplit as LiftedSplit
from openflowsheet.models.lifted import Regime as Regime
from openflowsheet.models.lifted import StagedSplits as StagedSplits
from openflowsheet.models.lifted import VapourOnlyForm as VapourOnlyForm
from openflowsheet.models.lifted import ZeroFlowForm as ZeroFlowForm
from openflowsheet.models.lifted_tolerance import (
    EQUILIBRIUM_TOLERANCE as EQUILIBRIUM_TOLERANCE,
)
from openflowsheet.models.lifted_tolerance import KIND_TOLERANCE as KIND_TOLERANCE
from openflowsheet.models.syn001.ph_kernel import ph_state as ph_state
from openflowsheet.numerics.newton import solve_newton
from openflowsheet.numerics.ptc import PtcRecord
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS, Scaling
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
from openflowsheet.orchestrator.region_attempts import _homotopy as _homotopy
from openflowsheet.orchestrator.region_attempts import _ptc_attempt
from openflowsheet.orchestrator.region_attempts import region_ptc_problem as region_ptc_problem
from openflowsheet.orchestrator.region_phase import TP_REGIME as TP_REGIME
from openflowsheet.orchestrator.region_phase import ClosureMemo as ClosureMemo
from openflowsheet.orchestrator.region_phase import _admissible as _admissible
from openflowsheet.orchestrator.region_phase import _band_regime as _band_regime
from openflowsheet.orchestrator.region_phase import (
    _branch,
    _dormant_feed,
    _form,
    _zero_flow_answer,
)
from openflowsheet.orchestrator.region_phase import _contract_kernel as _contract_kernel
from openflowsheet.orchestrator.region_phase import _dropped as _dropped
from openflowsheet.orchestrator.region_phase import _kernel as _kernel
from openflowsheet.orchestrator.region_phase import _KernelAnswer as _KernelAnswer
from openflowsheet.orchestrator.region_phase import _KernelRefusedError as _KernelRefusedError
from openflowsheet.orchestrator.region_phase import _ph_closure as _ph_closure
from openflowsheet.orchestrator.region_phase import _pin as _pin
from openflowsheet.orchestrator.region_phase import _pinned as _pinned
from openflowsheet.orchestrator.region_phase import _pr_c1 as _pr_c1
from openflowsheet.orchestrator.region_phase import _reference_k_values as _reference_k_values
from openflowsheet.orchestrator.region_phase import _split_enthalpy as _split_enthalpy
from openflowsheet.orchestrator.region_phase import admissibility_value as admissibility_value
from openflowsheet.orchestrator.region_problem import (
    _branch_found,
    _label_entries,
    _labels,
    _refinement,
    _with_labels,
)
from openflowsheet.orchestrator.region_problem import _items as _items
from openflowsheet.orchestrator.region_problem import _LiftedOps as _LiftedOps
from openflowsheet.orchestrator.region_problem import _opening_order as _opening_order
from openflowsheet.orchestrator.region_problem import _rederive as _rederive
from openflowsheet.orchestrator.region_problem import _region_problem as _region_problem
from openflowsheet.orchestrator.region_problem import _reset_outlet as _reset_outlet
from openflowsheet.orchestrator.region_problem import _settle as _settle
from openflowsheet.orchestrator.region_problem import _trigger_dormant as _trigger_dormant
from openflowsheet.orchestrator.region_problem import (
    _units_and_items_disjoint as _units_and_items_disjoint,
)
from openflowsheet.orchestrator.region_result import AttemptSystem as AttemptSystem
from openflowsheet.orchestrator.region_result import RecoveryStart as RecoveryStart
from openflowsheet.orchestrator.region_result import RegionAttempt as RegionAttempt
from openflowsheet.orchestrator.region_result import RegionResult as RegionResult
from openflowsheet.orchestrator.region_screen import _attempt_screen as _attempt_screen
from openflowsheet.orchestrator.region_screen import _build_screen as _build_screen
from openflowsheet.orchestrator.region_screen import _screen as _screen
from openflowsheet.orchestrator.revision_continuation import REVISION_CONTINUATION_REJECTED
from openflowsheet.orchestrator.roots import branch_found, root_fingerprint
from openflowsheet.orchestrator.trace import (
    AttemptSignature,
    Checkpoint,
    Counters,
    SolveOutcome,
    SolvePolicy,
    Trace,
    fraction_string,
)
from openflowsheet.orchestrator.warm_start import WARM_START_REJECTED, WARM_START_SOURCE
from openflowsheet.thermo import PropertyProvider

__all__ = [
    "ClosureType",
    "DormancyForm",
    "LiftedSplit",
    "RecoveryStart",
    "RegionResult",
    "Regime",
    "StagedSplits",
    "VapourOnlyForm",
    "ZeroFlowForm",
    "region_ptc_problem",
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

    def new_context() -> EvaluationContext:
        # T03 §4.2: every attempt constructs its own context objects (field-equal on this path).
        return EvaluationContext(
            model_version=identity[0], constants_sha256=identity[1], phase_signature=None
        )

    context = new_context()
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
    projections: list[str] = []
    regimes: dict[str, Regime] = {}
    if recovery is not None:
        # T04 §5.3: the failed solve's item-0 opening, projected and pinned already.
        current = {name: float(recovery.state[name]) for name in spec.variable_ids}
        regimes = {split.unit: recovery.regimes[split.unit] for split in active_splits}
    # §6.2: every lifted split of x⁰ is the kernel's; a supplied split that disagrees is
    # overwritten and the overwrite recorded, which is what keeps EO-TRIV off its trivial root.
    for split in active_splits if recovery is None else ():
        regime: Regime
        if v2 and _dormant_feed(split, current):
            # T05b spec §7.1: selected by exact dormancy, for either closure type; §7.4: its
            # lifted flows are pinned at `+0.0` (an overwritten supplied split is recorded).
            regime, kernel = "ZERO_FLOW", _zero_flow_answer(split).values
        elif split.unit in ph_units and _branch_found(split, current) != "ZERO_FLOW":
            # §6.4 (ADR 0012 D4 (b)): a PH-type split is not re-projected; it opens with the
            # traversal closure's split (D5), in the regime of its branch. An empty split of a
            # flowing feed carries no enthalpy, so it leaves `ZERO_FLOW` by the TP flash below
            # (§7.4), projected as a TP-type split is.
            regimes[split.unit] = _branch_found(split, current)
            continue
        else:
            regime, kernel = _kernel(provider, context, split, current)
        if any(
            abs(current[name] - value) > 1e-12 * max(1.0, abs(value))
            for name, value in kernel.items()
        ):
            projections.append(split.stream)
            # ADR 0009 D3's grammar, on existing kinds (K03 A08's precedent for a projected
            # guess): the candidate names what was supplied and what the kernel says.
            run.record(
                kind="initializer_candidate",
                attempt=0,
                iteration=0,
                signature=(),
                state_sha256="",
                residual_inf_unscaled=float("nan"),
                merit=float("nan"),
                counters=Counters(),
                message=f"projected({split.stream}, {_branch(split, current, v2)}, {regime})",
            )
        current.update(kernel)
        regimes[split.unit] = regime
    if order and recovery is None:
        # T05b spec §7.8 (ii) as amended (Q-S9, R-065; review M1): after the start rules, one fixed
        # point over the lifted splits' `ZERO_FLOW` membership and the items, so that a projection
        # of an earlier split that changes a later one's feed (or a trigger) is carried through,
        # in any declaration order. Each split change is recorded as a projection (§6.4); an item
        # change by the signature alone. (A recovery start is a settled attempt-0 opening.)
        try:
            current, regimes, _, changes = _settle(
                current,
                regimes,
                order=order,
                reference=supplied_items,
                leave=lambda split, at: _contract_kernel(
                    provider,
                    context,
                    split,
                    at,
                    ph_units,
                    v2=True,
                    regime="ZERO_FLOW",
                    temperatures=temperatures.get(split.unit),
                ),
            )
        except OpeningNotSettledError as unsettled:
            # §7.8 (ii) 2: the contract's cycling refusal, before any attempt opened.
            refusal = opening_not_settled(unsettled)
            return RegionResult(
                outcome=refusal.outcome,
                state=dict(current),
                attempts=(),
                projections=tuple(projections),
                message=refusal.message,
            )
        for change in changes:
            if change.split.stream not in projections:
                projections.append(change.split.stream)
            run.record(
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
    if projections:
        run.record(
            kind="initializer_accepted",
            attempt=0,
            iteration=0,
            signature=(),
            state_sha256="",
            residual_inf_unscaled=float("nan"),
            merit=float("nan"),
            counters=Counters(),
            message=f"the start with {len(projections)} split(s) projected onto the kernel's",
        )
    if v2 and recovery is None and band_routes:
        # §6.5 (ADR 0012 D10 F1): the traversal's band routes, after §6.2's projection records,
        # in declaration order, on T02 §6.2's existing pair of kinds.
        for unit in band_routes:
            run.record(
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
        run.record(
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

    counters = Counters()
    used: list[AttemptSignature] = []
    attempts: list[RegionAttempt] = []
    provenance: list[dict[str, Any]] = []
    checkpoint: Checkpoint | None = None
    contexts: list[AttemptContext] = []
    message = "initial"
    source: OpeningSource = item0_opening_source if recovery is None else "eo_recovery_start"
    trial: Candidate | None = None
    opened_at: tuple[Mapping[str, float], Mapping[str, Regime]] | None = None
    budget: str | None = None
    homotopy: HomotopyRecord | None = None

    def closed(
        outcome: SolveOutcome, text: str = "", system: AttemptSystem | None = None
    ) -> RegionResult:
        fingerprint = None
        if outcome == "CONVERGED":
            fingerprint = root_fingerprint(
                model_version=identity[0],
                constants_sha256=identity[1],
                variable_ids=spec.variable_ids,
                # Every lifted split of the declaration, from the state (review M1): a root's
                # branch is where it is, not which units this region happened to hold.
                branch_found=branch_found(splits, current),
                full_state_sha256=state_sha256(current, spec.variable_ids),
            )
        return RegionResult(
            outcome=outcome,
            state=dict(current),
            attempts=tuple(attempts),
            projections=tuple(projections),
            counters=counters,
            message=text,
            checkpoint=checkpoint,
            contexts=tuple(contexts),
            branch_provenance=tuple(provenance),
            root_fingerprint=fingerprint,
            opening=opened_at,
            budget=budget if outcome == "BUDGET_EXHAUSTED" else None,
            homotopy=homotopy,
            final_system=system,
        )

    for attempt_index in range(policy.max_attempts):
        if v2:
            # T05b spec §7.1: `ZERO_FLOW` exactly when the feed is dormant. Every opening — attempt
            # 0's start and every restart — ends in §7.8 (ii)'s fixed point (`_settle`), which makes
            # it so; this guard stays behind it (Q-S9) and a disagreement here is a defect.
            for split in active_splits:
                if _dormant_feed(split, current) != (regimes[split.unit] == "ZERO_FLOW"):
                    raise RuntimeError(
                        f"defect: {split.unit} opens attempt {attempt_index} in "
                        f"{regimes[split.unit]} with its feed "
                        f"{'dormant' if _dormant_feed(split, current) else 'flowing'}"
                    )
        # T05b spec §7.8 (i)–(ii): the lifted regimes, then the items of the opening state.
        items = _items(dormancy, current)
        running = [form for form in dormancy if (form.item, "ZERO_FLOW") in items]
        opening = (*((split.unit, regimes[split.unit]) for split in active_splits), *items)
        used.append(opening)
        pinned = {
            name
            for split in active_splits
            for name in _pinned(split, regimes[split.unit], forms, vapour)
        }
        dropped = {
            name
            for split in active_splits
            for name in _dropped(split, regimes[split.unit], forms, vapour)
        } | {form.swapped for form in running}
        labels = (*_labels(active_splits, regimes, forms), *(form.label for form in running))
        free = tuple(name for name in region.variable_ids if name not in pinned)
        rows = tuple(name for name in region.row_ids if name not in dropped)
        # T05b spec §7.2: the attempt's system is its compiled rows, then its label rows.
        attempt_rows = (*rows, *(label for label, _, _ in labels))
        if len(free) != len(attempt_rows):
            return closed(
                "UNSUPPORTED_RANK_STRUCTURE",
                f"the region with signature {opening} is {len(attempt_rows)} x {len(free)}, "
                "not square",
            )
        if recovery is not None and recovery.reported_signature is not None and attempt_index == 0:
            # RRC design note §5.7: a revision continuation opens at an external root — the
            # ancestor certificate's — so it is checked as a warm start is, against the signature
            # the certificate reported, before its pinned columns are set. The identity pair is
            # the requirement's: R5 and R8 established it (`revision_continuation`).
            refused = _external_opening(
                current,
                opening,
                identity,
                free,
                active_splits,
                regimes,
                forms,
                vapour,
                spec,
                reported=recovery.reported_signature,
            )
            if refused is not None:
                return closed(
                    "INITIALIZATION_FAILED",
                    f"{REVISION_CONTINUATION_REJECTED}(opening:{refused.check}:{refused.subject})",
                )
        if warm_start and attempt_index == 0 and recovery is None:
            # ADR 0024 D3: an external start is checked, not silently pinned — T03 §5.1 on the
            # opening this attempt would take, in place of `CHECKPOINT_INCOMPATIBLE`.
            refused = _external_opening(
                current, opening, identity, free, active_splits, regimes, forms, vapour, spec
            )
            if refused is not None:
                return closed(
                    "INITIALIZATION_FAILED", f"{WARM_START_REJECTED}(opening:{refused.check})"
                )
            run.record(
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
        for name in pinned:
            current[name] = 0.0
        if attempt_index == 0:
            opened_at = (dict(current), dict(regimes))
        # T04 §4.5: a recovery's attempt 0 is the homotopy; every later attempt is Newton's.
        # T04 §7.1: otherwise the policy's EO core, PTC for every attempt when it says so.
        continuing = recovery is not None and attempt_index == 0
        core: AttemptCore = (
            "homotopy" if continuing else "ptc" if region_mass is not None else "newton"
        )
        attempt_context = new_context()
        # T05b spec §6.2 as amended ("carrying"): the PH closures this attempt's screen asks,
        # reused by its openings at the same state.
        memo: ClosureMemo = {}
        x0 = np.array([current[name] for name in free], dtype=np.float64)
        contexts.append(
            AttemptContext(
                attempt_index=attempt_index,
                signature=opening,
                evaluation_context=attempt_context,
                flowsheet_context=attempt_context,
                column_scales={name: scaling.column[name] for name in free},
                row_scales={
                    **{name: scaling.row[name] for name in rows},
                    **{label: REGISTERED_NOMINALS[LABEL_KIND] for label, _, _ in labels},
                },
                counters_at_open=counters,
                opened_reason="initial" if attempt_index == 0 else "phase_update",
                opened_from=checkpoint,
                active_phases=opening,
                jacobian_pattern=(
                    jacobian_pattern((*structure, *_label_entries(labels)), attempt_rows, free)
                    if structure is not None
                    else None
                ),
                core=core,
                continuation=(
                    recovery.continuation.as_context()
                    if continuing and recovery is not None
                    else None
                ),
            )
        )
        opening_hash = state_sha256(x0, free)
        run.record(
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
        record: HomotopyRecord | None = None
        ptc_record: PtcRecord | None = None
        if continuing:
            assert recovery is not None and compile_level is not None
            last, record = _homotopy(
                recovery=recovery,
                compiled=compiled,
                compile_level=compile_level,
                spec=spec,
                scaling=scaling,
                opening_state=dict(current),
                free=free,
                rows=rows,
                splits=active_splits,
                regimes=regimes,
                provider=provider,
                policy=policy,
                attempt_context=attempt_context,
                trace=run,
                attempt_index=attempt_index,
                signature=opening,
                counters=counters,
                x0=x0,
                ph_units=ph_units,
                v2=v2,
                labels=labels,
                dormancy=dormancy,
            )
            homotopy = record
        elif region_mass is not None:
            last, ptc_record = _ptc_attempt(
                temperatures=temperatures,
                memo=memo,
                region_mass=region_mass,
                compiled=compiled,
                spec=spec,
                scaling=scaling,
                base=current,
                free=free,
                rows=rows,
                splits=active_splits,
                regimes=regimes,
                provider=provider,
                policy=policy,
                attempt_context=attempt_context,
                trace=run,
                attempt_index=attempt_index,
                signature=opening,
                counters=counters,
                wall=wall,
                x0=x0,
                ph_units=ph_units,
                v2=v2,
                labels=labels,
                dormancy=dormancy,
            )
        else:
            screen = _attempt_screen(
                splits=active_splits,
                regimes=regimes,
                provider=provider,
                context=attempt_context,
                epsilon=policy.admissibility_epsilon,
                ph_units=ph_units,
                v2=v2,
                dormancy=dormancy,
                temperatures=temperatures,
                memo=memo,
            )
            problem = _region_problem(
                compiled,
                attempt_context,
                spec,
                scaling,
                current,
                free,
                rows,
                screen,
                x0,
                **_with_labels(labels),
            )
            last = solve_newton(
                problem,
                x0,
                policy,
                trace=run,
                signature=opening,
                attempt=attempt_index,
                counters=counters,
                observer=wall,
                # T05b spec §7.8 (iii) (Q-S4 (6)): every trial of a v2 attempt in a region with a
                # dormancy-form outlet is screened, an empty signature included; `dormancy` is
                # empty under v1.
                compare_empty=bool(dormancy),
                # ADR 0018 D1: the target's Newton attempts only — never the homotopy corrector
                # (`_homotopy`) or the PTC core.
                refinement=_refinement(policy, spec, free),
            )
        counters = last.counters
        for position, name in enumerate(free):
            current[name] = float(last.x[position])
        for name in pinned:
            current[name] = 0.0
        ended = dict(current)

        ops = _LiftedOps(
            splits=active_splits,
            regimes=regimes,
            end_state=ended,
            free=free,
            provider=provider,
            context=attempt_context,
            policy=policy,
            region=region,
            spec=spec,
            identity=identity,
            ph_units=ph_units,
            v2=v2,
            forms=forms,
            dormancy=dormancy,
            items=frozenset(item for item, _ in items),
            order=order,
            temperatures=temperatures,
            memo=memo,
            vapour_only=vapour,
        )
        try:
            decision = decide(
                last,
                attempt_index=attempt_index,
                frozen=opening,
                wall=wall,
                ops=ops,
                policy=policy,
                used=used,
            )
        except BudgetExhaustedError as exhausted:
            # The closure's kernel calls (an end-state verdict, a restart point) are provider calls
            # outside the compiled residual (review S1). A refusal there closes this attempt: its
            # end state, checkpoint and provenance are kept, never discarded with the loop.
            decision = Decision("terminal", "BUDGET_EXHAUSTED", str(exhausted))
            budget = "property_calls"
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
                    if regimes[split.unit] == "ZERO_FLOW" and _form(split, forms).swapped
                ),
                *(form.swapped for form in running),
            )
            if swapped:
                decision = (
                    _swapped_row_test(compiled, attempt_context, spec, ended, swapped) or decision
                )
        outcome: SolveOutcome = decision.outcome
        if outcome == "BUDGET_EXHAUSTED" and budget is None:
            budget = last.budget
        attempts.append(
            RegionAttempt(
                opening,
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
            checkpoint = Checkpoint(
                checkpoint_id=f"region-attempt-{attempt_index}",
                attempt_index=attempt_index,
                iteration=last.iterations,
                variable_ids=free,
                state_sha256=state_sha256(last.x, free),
                signature=opening,
                residual_inf_unscaled=last.residual_inf,
                merit=last.merit,
                label="candidate_root" if decision.kind == "converged" else "partial",
                # T04 §4.4: a homotopy checkpoint names its level; below λ = 1 it is a state of a
                # modified problem, and the dataclass refuses to call it anything but partial.
                continuation_lambda=(
                    fraction_string(record.lambda_reached) if record is not None else None
                ),
            )
        provenance.append(
            provenance_item(
                attempt=attempt_index,
                signature=opening,
                core=core,
                source=source,
                initializer_source=(
                    (recovery.initializer_source if recovery is not None else initializer_source)
                    if attempt_index == 0
                    else None
                ),
                trial=trial,
                opening_state_sha256=opening_hash,
                result=last,
                decision=decision,
                continuation=record.provenance() if record is not None else None,
            )
        )
        if decision.kind == "converged":
            # OPT design §4.2.1: the system this attempt solved — its rows, free columns and label
            # rows, and every other column at the value it held (the end state's: the attempt
            # wrote only its free columns, and re-pinned its pinned ones at +0.0).
            kept = set(free)
            return closed(
                "CONVERGED",
                system=AttemptSystem(
                    rows=tuple(rows),
                    free=tuple(free),
                    held={name: current[name] for name in spec.variable_ids if name not in kept},
                    labels=tuple(labels),
                    signature=opening,
                ),
            )
        if decision.kind == "terminal":
            return closed(decision.outcome, decision.message)
        conversion = decision.conversion
        assert conversion is not None
        opened, new_regimes = conversion.opening
        current = dict(opened)
        regimes = dict(new_regimes)
        message = decision.message
        source = conversion.source
        trial = conversion.trial

    raise AssertionError("unreachable: the restart gate ends the solve at max_attempts")


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
