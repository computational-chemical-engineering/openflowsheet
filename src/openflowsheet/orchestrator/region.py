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
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.canonical import state_sha256
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext, PhaseSignature
from openflowsheet.models import temperature_id
from openflowsheet.models.c1.phase import classify
from openflowsheet.models.syn001 import ENERGY_TOLERANCE, FLOW_TOLERANCE, TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.ph_kernel import ph_state
from openflowsheet.models.syn001.saturation_band import BandError, band_temperature
from openflowsheet.models.syn001.tp_state import enthalpy_flow, tp_state
from openflowsheet.numerics.newton import (
    Evaluation,
    JacobianUnavailableError,
    NewtonResult,
    Problem,
    solve_newton,
)
from openflowsheet.numerics.ptc import PtcProblem, PtcRecord, solve_ptc
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS, Scaling
from openflowsheet.orchestrator.attempts import AttemptContext, AttemptCore, provenance_item
from openflowsheet.orchestrator.budget import BudgetExhaustedError
from openflowsheet.orchestrator.execution import Region
from openflowsheet.orchestrator.homotopy import (
    Continuation,
    CorrectorOutcome,
    HomotopyRecord,
    continue_specification,
    level_values,
    rebind,
)
from openflowsheet.orchestrator.mass import MappingRefusal, MassMapping, RegionMass, resolve_mass
from openflowsheet.orchestrator.phase_contract import (
    CONTRACT_V2,
    Candidate,
    Conversion,
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
from openflowsheet.orchestrator.rank import PRESSURE_TOLERANCE
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
from openflowsheet.thermo import FlashRequest, Phase, PropertyProvider, StreamState
from openflowsheet.thermo.pr_c1 import LIGHT
from openflowsheet.thermo.pr_c1 import PROVIDER_ID as PR_C1_PROVIDER_ID

__all__ = [
    "ClosureType",
    "DormancyForm",
    "LiftedSplit",
    "RecoveryStart",
    "RegionResult",
    "Regime",
    "VapourOnlyForm",
    "ZeroFlowForm",
    "region_ptc_problem",
    "solve_region",
    "syn001_lifted_splits",
]

#: An attempt's regime of one lifted split. `ZERO_FLOW` (T05b spec §7; ADR 0012 D4 (c)) is selected
#: only under `T05b-phase-contract-v2`, exactly when the split's feed is dormant.
Regime = Literal["TWO_PHASE", "LIQUID", "VAPOR", "ZERO_FLOW"]
#: T05b spec §6.1 (ADR 0012 D3): whether a lifted split's unit fixes its temperature by an energy
#: row (`PH`: the valve, the PH flash, the duty-mode reactor) or by a specification (`TP`).
ClosureType = Literal["PH", "TP"]
#: A split's branch found at a state (`roots.branch_found`): a regime, or `ZERO_FLOW` when it
#: carries nothing in either phase (ADR 0012 D6). Not an attempt regime under v1.
Branch = Literal["TWO_PHASE", "LIQUID", "VAPOR", "ZERO_FLOW"]

#: T03 §4.10's `inadmissible(<stream>, <branch>)` vocabulary, with T05b spec §6.5's `zero_flow`
#: (a `ZERO_FLOW` branch whose feed flows at closure). A `TWO_PHASE` branch is always admissible.
INADMISSIBLE_BRANCH: Final[Mapping[str, str]] = {
    "LIQUID": "all_liquid",
    "VAPOR": "all_vapor",
    "ZERO_FLOW": "zero_flow",
}

#: K04 §5.2's registered tolerance for the division-free equilibrium row, `a + r s` with
#: `a = 1e-9 · 3`, `r = 1e-8`, `s = 9 (mol/s)²`. Restated here because the verifier imports the
#: orchestrator; `tests/test_t02_region.py` pins the two equal so they cannot drift.
EQUILIBRIUM_TOLERANCE: Final = 1e-9 * 3.0 + 1e-8 * 9.0

#: The row acceptance rule by declared kind (ADR 0001 D6; K04 §5.2), K03 §5.2's per-row test.
KIND_TOLERANCE: Final[Mapping[str, float]] = {
    "molar_flow": FLOW_TOLERANCE,
    "molar_flow_squared": EQUILIBRIUM_TOLERANCE,
    "heat_rate": ENERGY_TOLERANCE,
    "temperature": TEMPERATURE_TOLERANCE,
    "pressure": PRESSURE_TOLERANCE,
}


@dataclass(frozen=True)
class LiftedSplit:
    """One lifted phase split: the variables that carry it and the rows that define it."""

    unit: str
    #: The stream being split, for messages and for the admissibility check's subject.
    stream: str
    feed: tuple[str, ...]
    temperature: str
    pressure: str
    vapor: tuple[str, ...]
    liquid: tuple[str, ...]
    vapor_total: str
    liquid_total: str
    equilibrium_rows: tuple[str, ...]
    vapor_definition: str
    liquid_definition: str

    def pinned(self, regime: Regime) -> tuple[str, ...]:
        """§6.3.1: LIQUID pins the vapour side, VAPOR the liquid side, TWO_PHASE nothing.
        `ZERO_FLOW`'s pins are its `ZeroFlowForm`'s (T05b spec §7.2), never read here."""
        if regime == "ZERO_FLOW":
            raise ValueError(f"defect: {self.unit}'s ZERO_FLOW pins are its ZeroFlowForm's")
        if regime == "LIQUID":
            return (*self.vapor, self.vapor_total)
        if regime == "VAPOR":
            return (*self.liquid, self.liquid_total)
        return ()

    def dropped(self, regime: Regime) -> tuple[str, ...]:
        """The rows a pinned phase satisfies identically; dropping them keeps the system square.
        `ZERO_FLOW`'s are its `ZeroFlowForm`'s (T05b spec §7.2), never read here."""
        if regime == "ZERO_FLOW":
            raise ValueError(f"defect: {self.unit}'s ZERO_FLOW rows are its ZeroFlowForm's")
        if regime == "LIQUID":
            return (*self.equilibrium_rows, self.vapor_definition)
        if regime == "VAPOR":
            return (*self.equilibrium_rows, self.liquid_definition)
        return ()


@dataclass(frozen=True)
class ZeroFlowForm:
    """One lifted split's `ZERO_FLOW` form (T05b spec §7.2; ADR 0012 D4 (c)): what an attempt
    in that regime pins and drops, and — for a PH-type split — the label row it adds in place of
    its unit's energy row. Built from the split registry's ids (spec §6.1,
    `splits.zero_flow_forms`), beside the split's descriptor rather than inside it, so
    `LiftedSplit` (and its registered `repr` digest, T05 W1.a) does not move.

    The label row is a row of the attempt's system only — never of the compiled declaration — so
    no `model_version`, structure hash or T01 report moves (spec §7.2)."""

    unit: str
    #: The split's lifted flows and totals, pinned at `+0.0`.
    columns: tuple[str, ...]
    #: The rows the form drops: equilibrium, split (or the products' mole) rows, the two total
    #: definitions, and for a PH-type split its energy row, last.
    rows: tuple[str, ...]
    #: A PH-type split's energy row, swapped out for the label (`""` for a TP-type split).
    swapped: str = ""
    #: `(row id, T_out, T_label)` of a PH-type split's label row `T_out − T_label`; `None` for a
    #: TP-type split, whose temperature keeps its specification row.
    label: tuple[str, str, str] | None = None


@dataclass(frozen=True)
class VapourOnlyForm:
    """One lifted split's vapour-only liquid flows (M02 design note §14.2 B12–B13; ADR 0012
    Amendment A2): the components whose liquid flow is a structural zero (the C1 flash's light
    gases), fixed by zero rows `l_i = 0` in the equilibrium family. A `TWO_PHASE` attempt pins
    `columns` at `+0.0` and drops `rows`; VAPOR and ZERO_FLOW pin them already, and LIQUID leaves
    them to the mole rows. Built by `splits.vapour_only_forms`, beside the descriptor as
    `ZeroFlowForm` is, so `LiftedSplit` and its registered `repr` digest do not move."""

    unit: str
    #: The split's liquid flows of the vapour-only components, in component order.
    columns: tuple[str, ...]
    #: Their zero rows, in the same order.
    rows: tuple[str, ...]


@dataclass(frozen=True)
class DormancyForm:
    """The zero-flow form of one dormancy-form outlet of a unit without a lifted split (T05b spec
    §7.6–§7.7; ADR 0012 D12): at exact dormancy of every stream of its trigger port it swaps one
    row — the unit's energy row, whose `T_out` coefficient `−Σ n c_p` is then zero — for the label
    row `T_out − T_label`, and pins nothing. Built from the dormancy-form registry
    (`splits.dormancy_forms`) and checked by `splits.check_agreement` (g).

    An attempt that runs the form carries the signature item `(item, "ZERO_FLOW")` after its
    lifted regimes (spec §7.8 (i)); the label row is a row of the attempt's system only, never of
    the compiled declaration."""

    #: `<U>.<port>`: the signature item's key.
    item: str
    unit: str
    #: The ports the rule names: the outlet, and the port whose every stream is the trigger.
    outlet_port: str
    trigger_port: str
    #: The outlet stream, and the trigger port's streams in connection order (R1).
    outlet: str
    triggers: tuple[str, ...]
    #: Every flow column of every trigger stream: the form is selected when all are `+0.0`.
    trigger_flows: tuple[str, ...]
    #: Spec §7.8 (ii)'s outlet reset: per component, the outlet's flow column and the trigger
    #: streams' flow columns it is the sum of, in connection order.
    balance: tuple[tuple[str, tuple[str, ...]], ...]
    #: The row swapped out, and the label row `(row id, T_out, T_label)` swapped in.
    swapped: str
    label: tuple[str, str, str]
    #: The outlet's declared phase, which names the item's absence in a cause string (§7.8 (i)).
    declared: PhaseSignature


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


@dataclass(frozen=True)
class RegionAttempt:
    signature: AttemptSignature
    outcome: SolveOutcome
    iterations: int
    #: Why the attempt closed into the next one, in §9's registered grammar, or "".
    reason: str = ""
    #: What Newton itself ended on, before §6.3 converted it (A31: `STAGNATION` read as a
    #: disagreement with the kernel), and the iterate it ended at, before any pin or projection.
    solver_outcome: SolveOutcome | None = None
    end_state: Mapping[str, float] = field(default_factory=dict)
    #: The numbers behind `reason` or the terminal message — an admissibility value, the offending
    #: value of a refused opening — kept here because the strings are R0 (review S4).
    observations: Mapping[str, float] = field(default_factory=dict)
    #: T04 §7.8: a PTC attempt's pseudo-steps, rejections, SER state and polish. In memory only.
    ptc: PtcRecord | None = None


@dataclass(frozen=True)
class RegionResult:
    outcome: SolveOutcome
    state: Mapping[str, float]
    attempts: tuple[RegionAttempt, ...]
    #: Streams whose supplied split disagreed with the kernel and was overwritten (§6.2).
    projections: tuple[str, ...] = ()
    counters: Counters = field(default_factory=Counters)
    message: str = ""
    #: K03 §12.5's checkpoint of the last attempt that accepted a step or converged:
    #: `candidate_root` only when the solve converged, `partial` otherwise (A30).
    checkpoint: Checkpoint | None = None
    #: One context per attempt, with the active phase set it solved under (ADR 0009 D4).
    contexts: tuple[AttemptContext, ...] = ()
    #: ADR 0005 D7 (T03 §8.1): one item per attempt — the attempt history and its start.
    branch_provenance: tuple[Mapping[str, Any], ...] = ()
    #: ADR 0005 D7 (T03 §8.2): issued on a `CONVERGED`, admissible solve, `None` otherwise.
    root_fingerprint: Mapping[str, Any] | None = None
    #: Attempt 0's opening: the full state (after §6.2's projection and the attempt's pins) and
    #: the regimes it opened under — what recovery edge 3 starts from (T04 §5.3). In memory only.
    opening: tuple[Mapping[str, float], Mapping[str, Regime]] | None = None
    #: On `BUDGET_EXHAUSTED`: which budget — the core's (`newton_iterations`, `homotopy_steps`) or
    #: `property_calls` — because edge 3's trigger set tells them apart (T04 §5.1).
    budget: str | None = None
    #: T04 §4.7: the homotopy's record, when attempt 0 ran the homotopy core.
    homotopy: HomotopyRecord | None = None

    @property
    def iterations(self) -> int:
        return sum(attempt.iterations for attempt in self.attempts)

    @property
    def signatures(self) -> tuple[AttemptSignature, ...]:
        return tuple(attempt.signature for attempt in self.attempts)


@dataclass(frozen=True)
class RecoveryStart:
    """Recovery edge 3's start (T04 §5.3): the failed solve's item-0 opening state and signature,
    the region's continuation parameter, and item 0's initializer source. The recovery region
    solve's attempt 0 runs the homotopy core from here, with a fresh contract state."""

    state: Mapping[str, float]
    regimes: Mapping[str, Regime]
    continuation: Continuation
    initializer_source: str | None


class _KernelRefusedError(ValueError):
    """The provider would not split a lifted stream (review S5). Never escapes `solve_region`:
    it becomes the `EVALUATION_ERROR` the outcome vocabulary has for it."""

    def __init__(self, stream: str, status: str, message: str) -> None:
        super().__init__(
            f"the kernel could not split {stream}: the provider returned {status}"
            + (f" ({message})" if message else "")
        )


def _kernel(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: Mapping[str, float],
    *,
    temperature: str | None = None,
) -> tuple[Regime, dict[str, float]]:
    """The provider's regime and split at the stream's `(n, T, P)` (K03 §8.3): the feed's flows,
    the split's pressure and the split's temperature — or the `temperature` column named."""
    stream = StreamState(
        n=tuple(state[name] for name in split.feed),
        temperature=state[split.temperature if temperature is None else temperature],
        pressure=state[split.pressure],
    )
    if _pr_c1(provider):
        # M02 design note §14.2 B14: M01 §7 rule 3 with τ_dew. A VAPOR answer — the provider's,
        # or a TWO_PHASE one inside the dew band — opens as `_pin(VAPOR)` sets it.
        band, _, result = classify(provider, context, stream.n, stream.temperature, stream.pressure)
        if band == "VAPOR" and result.status == "ok":
            return "VAPOR", _vapour_pinned(split, stream.n)
    else:
        result = provider.flash(FlashRequest(state=stream), context)
    if result.status != "ok" or result.vapor is None or result.liquid is None:
        raise _KernelRefusedError(split.stream, str(result.status), result.message)
    regime: Regime = "TWO_PHASE"
    if result.phase_signature == "LIQUID":
        regime = "LIQUID"
    elif result.phase_signature == "VAPOR":
        regime = "VAPOR"
    values = {
        **dict(zip(split.vapor, result.vapor.n, strict=True)),
        **dict(zip(split.liquid, result.liquid.n, strict=True)),
        split.vapor_total: float(sum(result.vapor.n)),
        split.liquid_total: float(sum(result.liquid.n)),
    }
    return regime, values


def _pr_c1(provider: PropertyProvider) -> bool:
    """Whether `provider` is `pr-c1-v1` (B14's dispatch; `describe` is uncounted)."""
    return provider.describe().provider_id == PR_C1_PROVIDER_ID


def _vapour_pinned(split: LiftedSplit, feed: Sequence[float]) -> dict[str, float]:
    """A VAPOR split's values as `_pin(VAPOR)` writes them: the vapour the feed bitwise, the
    liquid `+0.0`, `V = float(sum(feed))`, `L = 0.0`."""
    values = dict(zip(split.vapor, feed, strict=True))
    values.update(dict.fromkeys(split.liquid, 0.0))
    values[split.vapor_total] = float(sum(feed))
    values[split.liquid_total] = 0.0
    return values


@dataclass(frozen=True)
class _KernelAnswer:
    """The contract's kernel at one split and state: its regime, the split's values it opens with
    (and, from a PH closure, the split's temperature), and F2's record (T05b spec §6.5): `""`
    for a primary answer, `ph-band` or `tp` for a fallback's."""

    regime: Regime
    values: dict[str, float]
    fallback: str = ""


def _zero_flow_answer(split: LiftedSplit) -> _KernelAnswer:
    """T05b spec §6.2 step 1 and §7.1: a dormant feed's regime is `ZERO_FLOW`, and every lifted
    flow of its split is `+0.0` (§7.4: entering pins them and leaves every other value)."""
    names = (*split.vapor, *split.liquid, split.vapor_total, split.liquid_total)
    return _KernelAnswer("ZERO_FLOW", dict.fromkeys(names, 0.0))


def _dormant_feed(split: LiftedSplit, state: Mapping[str, float]) -> bool:
    """ADR 0001 D3.1: every flow of the split's feed exactly zero (`-0.0 == 0.0`)."""
    return all(state[name] == 0.0 for name in split.feed)


def _split_enthalpy(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: Mapping[str, float],
) -> float | None:
    """T05b spec §6.2 step 2's `H_split = Σ v_i h_i^V(T, P) + Σ l_i h_i^L(T, P)`, with `T`, `P`
    the split's temperature and pressure columns; `None` when the provider refuses an enthalpy."""
    temperature, pressure = state[split.temperature], state[split.pressure]
    components = provider.describe().components
    target = 0.0
    phases: tuple[tuple[Phase, tuple[str, ...]], ...] = (
        ("VAPOR", split.vapor),
        ("LIQUID", split.liquid),
    )
    for phase, names in phases:
        stream = StreamState(
            n=tuple(state[name] for name in names), temperature=temperature, pressure=pressure
        )
        status, contribution, _ = enthalpy_flow(provider, stream, phase, components, context)
        if status != "ok":
            return None
        target += contribution
    return target


#: `_band_regime`'s (s1) answer: `ph_state` would refuse the target as outside the domain, so the
#: screen reports the TP flash's regime at the trial, as step 4 does.
TP_REGIME: Final = "tp"


def _band_regime(
    provider: PropertyProvider,
    context: EvaluationContext,
    feed: tuple[float, ...],
    pressure: float,
    target: float,
) -> Regime | Literal["tp"] | None:
    """T05b spec §6.2 (s1)–(s2) as amended (ruling Q-S10, R-053; review S1): the regime of a flagged
    PH-type trial of the flowing `feed` at `(P, H_split = target)`, from the band's end
    enthalpies instead of the full closure.

    (s1) `target` below `Ḣ_TP(feed, T_min, P)` or above `Ḣ_TP(feed, T_max, P)` — `ph_state`'s own
    step-3 test on the same function — gives `TP_REGIME`. (s2) Else, with `T_b = T(0)`,
    `T_d = T(1)` (`band_temperature`, its sign oracle: a band end below the domain is `−∞`, above
    it `+∞`), `H_0 = Σ n_i h_i^L(T_b, P)` and `H_1 = Σ n_i h_i^V(T_d, P)`: `LIQUID` below
    `H_0 − τ_E`, `TWO_PHASE` strictly between `H_0 + τ_E` and `H_1 − τ_E`, `VAPOR` above
    `H_1 + τ_E`. (s3) `None` — ask the full closure — within `τ_E` of an end, or when any
    evaluation here is not `ok`.

    Exact wherever `ph_state` answers `ok` (§6.2: an `ok` answer carries the target to `τ_E`, and
    the phase regions are ordered by enthalpy, §4.2); floating-point error in `H_0`, `H_1` is far
    below the `τ_E` margin. Costs two `T(β)` bisections, two TP flashes and two enthalpy sums."""
    t_min, t_max = provider.describe().domain["T"]
    for end in (t_min, t_max):
        at_end = tp_state(
            provider, StreamState(n=feed, temperature=end, pressure=pressure), context
        )
        if at_end.status != "ok" or at_end.enthalpy_flow is None:
            return None
        if (end == t_min and target < at_end.enthalpy_flow) or (
            end == t_max and target > at_end.enthalpy_flow
        ):
            return TP_REGIME
    components = provider.describe().components
    ends: list[float] = []
    band_ends: tuple[tuple[float, Phase], ...] = ((0.0, "LIQUID"), (1.0, "VAPOR"))
    for beta, phase in band_ends:
        try:
            at = band_temperature(provider, feed, pressure, beta, context)
        except BandError:
            return None
        if at.temperature is None:
            ends.append(-math.inf if at.position == "below" else math.inf)
            continue
        stream = StreamState(n=feed, temperature=at.temperature, pressure=pressure)
        status, value, _ = enthalpy_flow(provider, stream, phase, components, context)
        if status != "ok":
            return None
        ends.append(value)
    h_0, h_1 = ends
    if target < h_0 - ENERGY_TOLERANCE:
        return "LIQUID"
    if h_0 + ENERGY_TOLERANCE < target < h_1 - ENERGY_TOLERANCE:
        return "TWO_PHASE"
    if target > h_1 + ENERGY_TOLERANCE:
        return "VAPOR"
    return None


#: T05b spec §6.2 as amended, "carrying": a PH closure (steps 2–3) the screen asked at a trial,
#: by unit and the exact inputs (`_closure_key`), which an opening at the same state reuses.
type ClosureMemo = dict[tuple[str, tuple[str, ...]], "_KernelAnswer | None"]


def _closure_key(split: LiftedSplit, state: Mapping[str, float]) -> tuple[str, tuple[str, ...]]:
    """`_ph_closure`'s inputs, exactly (`float.hex`: `-0.0` is not `+0.0`)."""
    names = (*split.feed, *split.vapor, *split.liquid, split.temperature, split.pressure)
    return split.unit, tuple(float(state[name]).hex() for name in names)


def _ph_closure(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: Mapping[str, float],
    temperatures: Sequence[str] | None = None,
) -> _KernelAnswer | None:
    """T05b spec §6.2 steps 2–3 (F2's primary): the PH closure of the split's feed at the split's
    own enthalpy, `H_split = Σ v_i h_i^V(T, P) + Σ l_i h_i^L(T, P)` with `T`, `P` the split's
    temperature and pressure columns. `None` when it gives no answer — a provider refusal of the
    enthalpy, or any non-`ok` closure — and the caller falls back to the TP flash (step 4).

    `temperatures` are every temperature column of the split's streams
    (`splits.split_temperatures`); the answer sets each to the closure's `T` (step 3 as amended,
    Q-S11 (a)). `None` names the split's own column only."""
    feed = tuple(state[name] for name in split.feed)
    if all(value == 0.0 for value in feed):
        # Spec §6.2 step 1: the regime is `ZERO_FLOW`.
        return _zero_flow_answer(split)
    target = _split_enthalpy(provider, context, split, state)
    if target is None:
        return None
    closure = ph_state(provider, feed, state[split.pressure], target, context)
    if closure.status != "ok":
        return None
    answer = closure.split
    assert answer is not None and answer.vapor is not None and answer.liquid is not None
    assert closure.temperature is not None
    regime: Regime = "TWO_PHASE"
    if answer.phase_signature == "LIQUID":
        regime = "LIQUID"
    elif answer.phase_signature == "VAPOR":
        regime = "VAPOR"
    values = {
        **dict(zip(split.vapor, answer.vapor.n, strict=True)),
        **dict(zip(split.liquid, answer.liquid.n, strict=True)),
        split.vapor_total: float(sum(answer.vapor.n)),
        split.liquid_total: float(sum(answer.liquid.n)),
        # §6.2 step 3 as amended (Q-S11 (a)): the opening sets every temperature column of the
        # split's streams to the closure's — a products-style split's liquid product too.
        **dict.fromkeys(
            (split.temperature,) if temperatures is None else temperatures, closure.temperature
        ),
    }
    return _KernelAnswer(regime, values, "ph-band" if closure.route == "band" else "")


def _contract_kernel(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: Mapping[str, float],
    ph_units: frozenset[str],
    *,
    v2: bool = False,
    regime: Regime | None = None,
    temperatures: Sequence[str] | None = None,
    memo: ClosureMemo | None = None,
) -> _KernelAnswer:
    """ADR 0005's "kernel" of one split under the policy's rule set: the TP flash (`_kernel`) —
    every split under v1, a TP-type split under v2 — or, for a PH-type split under v2 (`ph_units`
    is empty under v1), F2: the PH closure, then the TP flash recorded `tp` (T05b spec §6.2).

    Under v2 (`v2`), for either closure type (spec §7.1, §7.4): a dormant feed is `ZERO_FLOW`;
    a split whose attempt `regime` is `ZERO_FLOW` and whose feed flows is leaving it, and its
    pinned split carries no enthalpy, so the TP flash answers — recorded `tp` when PH-type. As
    amended (Q-S14) a PH-type split's leaving flash is taken at its feed's `n` and `T` and its
    own (outlet) `P`, and that `T` is written to every column of `temperatures`: the split's own
    `T` is the zero-flow label of an earlier feed, i.e. attempt history. A TP-type split flashes
    at its own specified `T`.

    `temperatures` are the split's temperature columns (`splits.split_temperatures`), which a PH
    closure's answer and a PH-type leaving answer set. `memo` holds the closures the attempt's
    screen asked (§6.2 as amended, "carrying"): one at the same inputs is reused, not asked
    again."""
    if v2 and _dormant_feed(split, state):
        return _zero_flow_answer(split)
    if v2 and regime == "ZERO_FLOW":
        if split.unit not in ph_units:
            leaving, values = _kernel(provider, context, split, state)
            return _KernelAnswer(leaving, values)
        # The stream `split.feed` names: a products-style split's inlet; an outlet-style split's
        # own outlet, whose `T` is `split.temperature` — there the flash is unchanged and there is
        # nothing to write.
        feed = temperature_id(split.stream)
        leaving, values = _kernel(provider, context, split, state, temperature=feed)
        written = (split.temperature,) if temperatures is None else tuple(temperatures)
        values.update({column: state[feed] for column in written if column != feed})
        return _KernelAnswer(leaving, values, "tp")
    if split.unit in ph_units:
        key = _closure_key(split, state)
        if memo is not None and key in memo:
            answer = memo[key]
        else:
            answer = _ph_closure(provider, context, split, state, temperatures)
        if answer is not None:
            return answer
        regime, values = _kernel(provider, context, split, state)
        return _KernelAnswer(regime, values, "tp")
    regime, values = _kernel(provider, context, split, state)
    return _KernelAnswer(regime, values)


def _admissible(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    regime: Branch,
    state: Mapping[str, float],
    epsilon: float,
) -> tuple[bool, float]:
    """K03 §8.2 on a single-phase branch: a liquid that would boil, a vapour that would condense.

    A `ZERO_FLOW` branch (`V = L = 0`, ADR 0012 D6) is admissible iff its feed is exactly dormant
    (T05b spec §7.3's closure rule, which §8 applies under every literal): a split with nothing
    in either phase is right only when nothing flows into it. The value is the feed's total."""
    if regime == "TWO_PHASE":
        return True, 0.0
    if regime == "ZERO_FLOW":
        feed = sum(state[name] for name in split.feed)
        return all(state[name] == 0.0 for name in split.feed), feed
    if _pr_c1(provider):
        return _pr_admissible(provider, context, split, regime, state)
    from openflowsheet.verify.checks import k_values

    constants = k_values(provider, state[split.temperature], state[split.pressure], context)
    side = split.liquid if regime == "LIQUID" else split.vapor
    amounts = [state[name] for name in side]
    total = sum(amounts)
    if total == 0.0:
        return True, 0.0
    fractions = [amount / total for amount in amounts]
    if regime == "LIQUID":
        value = sum(x * k for x, k in zip(fractions, constants, strict=True))
    else:
        value = sum(y / k for y, k in zip(fractions, constants, strict=True))
    return value <= 1.0 + epsilon, value


def _pr_admissible(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    regime: Branch,
    state: Mapping[str, float],
) -> tuple[bool, float]:
    """B14 on a single-phase branch of a `pr-c1-v1` split, `admissibility_epsilon` unread:
    VAPOR iff `classify` of the feed at the split's `(T, P)` is VAPOR, with its value; LIQUID iff
    no light gas flows in the feed and `classify` is LIQUID, with value `n_light / n_tot`. A
    provider refusal is a `VerifierError`, which the screen converts to `invalid_trial_state`.
    A dormant feed is admissible with value `0.0`, as the K03 rule's empty side is."""
    from openflowsheet.verify.checks import VerifierError

    feed = tuple(state[name] for name in split.feed)
    total = sum(feed)
    if total == 0.0:
        return True, 0.0
    answer, value, result = classify(
        provider, context, feed, state[split.temperature], state[split.pressure]
    )
    if answer is None:
        raise VerifierError(
            f"the kernel refused {split.unit}'s regime ({split.stream}): {result.status}: "
            f"{result.message}"
        )
    if regime == "VAPOR":
        return answer == "VAPOR", value
    light = sum(feed[k] for k in LIGHT)
    return all(feed[k] == 0.0 for k in LIGHT) and answer == "LIQUID", light / total


def _branch(split: LiftedSplit, state: Mapping[str, float], v2: bool = False) -> str:
    """Which branch a supplied split is on, for the projection record; under v2 an empty split
    (`V = L = 0`) is `zero_flow` (T05b spec §6.5's branch word), under v1 `two_phase` as before."""
    vapor, liquid = state[split.vapor_total], state[split.liquid_total]
    if v2 and vapor == 0.0 and liquid == 0.0:
        return "zero_flow"
    if vapor == 0.0 and liquid > 0.0:
        return "all_liquid"
    if liquid == 0.0 and vapor > 0.0:
        return "all_vapor"
    return "two_phase"


def _pin(state: dict[str, float], split: LiftedSplit, regime: Regime) -> None:
    """§6.3.3's restart point: the phase that left is exactly zero, the other takes the feed."""
    feed = [state[name] for name in split.feed]
    if regime == "LIQUID":
        state.update(dict.fromkeys(split.vapor, 0.0))
        state[split.vapor_total] = 0.0
        state.update(dict(zip(split.liquid, feed, strict=True)))
        state[split.liquid_total] = float(sum(feed))
    elif regime == "VAPOR":
        state.update(dict.fromkeys(split.liquid, 0.0))
        state[split.liquid_total] = 0.0
        state.update(dict(zip(split.vapor, feed, strict=True)))
        state[split.vapor_total] = float(sum(feed))


def _form(split: LiftedSplit, forms: Mapping[str, ZeroFlowForm]) -> ZeroFlowForm:
    form = forms.get(split.unit)
    if form is None:
        raise ValueError(f"defect: {split.unit} is in ZERO_FLOW and the region has no form for it")
    return form


def _pinned(
    split: LiftedSplit,
    regime: Regime,
    forms: Mapping[str, ZeroFlowForm],
    vapour_only: Mapping[str, VapourOnlyForm] | None = None,
) -> tuple[str, ...]:
    """The columns an attempt holds at `+0.0` for one split: its `ZeroFlowForm`'s in `ZERO_FLOW`
    (T05b spec §7.2), `LiftedSplit.pinned`'s otherwise — and, in `TWO_PHASE`, its
    `VapourOnlyForm`'s (M02 design note §14.2 B13)."""
    if regime == "ZERO_FLOW":
        return _form(split, forms).columns
    if regime == "TWO_PHASE" and vapour_only and split.unit in vapour_only:
        return (*split.pinned(regime), *vapour_only[split.unit].columns)
    return split.pinned(regime)


def _dropped(
    split: LiftedSplit,
    regime: Regime,
    forms: Mapping[str, ZeroFlowForm],
    vapour_only: Mapping[str, VapourOnlyForm] | None = None,
) -> tuple[str, ...]:
    """The rows an attempt drops for one split, as `_pinned`."""
    if regime == "ZERO_FLOW":
        return _form(split, forms).rows
    if regime == "TWO_PHASE" and vapour_only and split.unit in vapour_only:
        return (*split.dropped(regime), *vapour_only[split.unit].rows)
    return split.dropped(regime)


def _labels(
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    forms: Mapping[str, ZeroFlowForm],
) -> tuple[tuple[str, str, str], ...]:
    """The label rows `(row id, T_out, T_label)` of the attempt's PH-type `ZERO_FLOW` splits, in
    signature order (T05b spec §7.2)."""
    labels: list[tuple[str, str, str]] = []
    for split in splits:
        if regimes[split.unit] == "ZERO_FLOW":
            label = _form(split, forms).label
            if label is not None:
                labels.append(label)
    return tuple(labels)


#: T05b spec §7.2: a label row's kind, and so its tolerance and its row scale (K03 §4.2's
#: temperature nominal); a PTC core reads it as algebraic (spec §7.8 (v), ADR 0008 D3).
LABEL_KIND: Final = "temperature"


def _region_problem(
    compiled: CompiledProblem,
    context: EvaluationContext,
    spec: ProblemSpec,
    scaling: Scaling,
    base: Mapping[str, float],
    free: Sequence[str],
    rows: Sequence[str],
    screen: Callable[[dict[str, float]], AttemptSignature | Evaluation] | None = None,
    opening: npt.NDArray[np.float64] | None = None,
    labels: Sequence[tuple[str, str, str]] = (),
) -> Problem:
    """One attempt's square system: its rows over its free columns, everything else held at `base`.

    The residual and the Jacobian are the compiled problem's, selected **by id**, never by
    position (§6.1), so the region solves exactly the function K04 verifies.

    `labels` (T05b spec §7.2) are the attempt's label rows `(row id, T_out, T_label)`, appended
    after `rows`: residual `T_out − T_label`, derivative exactly `+1` at `T_out` and `−1` at
    `T_label` where those are free columns, kind temperature. They are not compiled rows. With
    none, the problem is the one it always was.

    `screen` (T03 §4.3) reports each trial's signature: the frozen one, or the kernel's regime for a
    single-phase unit whose admissibility check flagged the trial — or, when the kernel refuses,
    the typed evaluation to return instead. It reads a trial; it never changes the residual. The
    `opening` point is not screened (an attempt may open where its own screen would object).
    """
    order = {name: index for index, name in enumerate(spec.variable_ids)}
    rows_at = {name: index for index, name in enumerate(spec.equation_ids)}
    selected_rows = [rows_at[name] for name in rows]
    selected_columns = [order[name] for name in free]
    held = np.array([base[name] for name in spec.variable_ids], dtype=np.float64)
    label_ids = tuple(label for label, _, _ in labels)
    label_columns = [(order[outlet], order[source]) for _, outlet, source in labels]
    label_matrix = _label_matrix(labels, free)

    def full(x: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        vector = held.copy()
        vector[selected_columns] = x
        return vector

    def residual(x: npt.NDArray[np.float64]) -> Evaluation:
        vector = full(x)
        result = compiled.residual(vector, context)
        if result.status != "ok" or result.values is None:
            return Evaluation(status=result.status, message=result.message)
        values = tuple(result.values[i] for i in selected_rows)
        if labels:
            values += tuple(float(vector[o]) - float(vector[s]) for o, s in label_columns)
        if screen is None or (opening is not None and np.array_equal(x, opening)):
            return Evaluation(status="ok", values=values)
        reported = screen(dict(zip(spec.variable_ids, (float(v) for v in vector), strict=True)))
        if isinstance(reported, Evaluation):
            return reported
        return Evaluation(status="ok", values=values, signature=reported)

    def jacobian(x: npt.NDArray[np.float64]) -> sp.csc_matrix:
        result = compiled.jacobian(full(x), context)
        if result.status != "ok":
            # T04 review M1: a failed evaluation carries empty data; read as a matrix it would be
            # a structurally valid zero, which a core then factors.
            raise JacobianUnavailableError(str(result.status), result.message)
        matrix = sp.csc_matrix(
            (result.data, result.indices, result.indptr),
            shape=(len(result.row_ids), len(result.col_ids)),
        )
        selected = matrix[selected_rows, :][:, selected_columns]
        if labels:
            return sp.csc_matrix(sp.vstack([selected, label_matrix]))
        return sp.csc_matrix(selected)

    return Problem(
        variable_ids=tuple(free),
        row_ids=(*rows, *label_ids),
        residual=residual,
        jacobian=jacobian,
        scaling=Scaling(
            column={name: scaling.column[name] for name in free},
            row={
                **{name: scaling.row[name] for name in rows},
                **dict.fromkeys(label_ids, REGISTERED_NOMINALS[LABEL_KIND]),
            },
        ),
        row_tolerance={
            **{name: KIND_TOLERANCE[spec.row_kinds[name]] for name in rows},
            **dict.fromkeys(label_ids, KIND_TOLERANCE[LABEL_KIND]),
        },
        lower_bounds={name: 0.0 for name in free if spec.variable_kinds.get(name) == "molar_flow"},
    )


def _refinement(
    policy: SolvePolicy, spec: ProblemSpec, free: Sequence[str]
) -> dict[str, float] | None:
    """ADR 0018 D1–D2: under `eo_core = "newton_refined"`, the terminal refinement's `τ_kind` for
    every free column whose declared quantity kind has a registered acceptance rule — the rule
    the rows are judged by (`KIND_TOLERANCE`); `None`, which is K03's Newton unchanged, under any
    other value. Label rows are rows, not columns, so they add nothing here."""
    if policy.globalization.eo_core != "newton_refined":
        return None
    return {
        name: KIND_TOLERANCE[kind]
        for name in free
        if (kind := spec.variable_kinds.get(name)) is not None and kind in KIND_TOLERANCE
    }


def _with_labels(labels: Sequence[tuple[str, str, str]]) -> dict[str, Any]:
    """`_region_problem`'s `labels` argument, passed only when there are any: an attempt without
    a label row calls it exactly as before T05b W7."""
    return {"labels": tuple(labels)} if labels else {}


def _label_matrix(labels: Sequence[tuple[str, str, str]], free: Sequence[str]) -> sp.csc_matrix:
    """The label rows' exact Jacobian over the free columns: `+1` at `T_out`, `−1` at `T_label`
    (T05b spec §7.2); a held column has no entry."""
    at = {name: index for index, name in enumerate(free)}
    data: list[float] = []
    row_index: list[int] = []
    column_index: list[int] = []
    for k, (_, outlet, source) in enumerate(labels):
        for name, value in ((outlet, 1.0), (source, -1.0)):
            if name in at:
                data.append(value)
                row_index.append(k)
                column_index.append(at[name])
    return sp.csc_matrix(
        sp.coo_matrix(
            (np.asarray(data, dtype=np.float64), (row_index, column_index)),
            shape=(len(labels), len(free)),
        )
    )


def _label_entries(labels: Sequence[tuple[str, str, str]]) -> tuple[tuple[str, str], ...]:
    """The label rows' structural entries, for the attempt's `jacobian_pattern` (spec §7.2)."""
    return tuple((label, name) for label, outlet, source in labels for name in (outlet, source))


def _trigger_dormant(form: DormancyForm, state: Mapping[str, float]) -> bool:
    """ADR 0001 D3.1: every flow of every trigger stream exactly zero (`-0.0 == 0.0`)."""
    return all(state[name] == 0.0 for name in form.trigger_flows)


def _items(forms: Sequence[DormancyForm], state: Mapping[str, float]) -> AttemptSignature:
    """T05b spec §7.8 (i)–(ii): the item `(<U>.<port>, ZERO_FLOW)` of every form whose trigger
    streams are exactly dormant at `state`, in declaration order (the exchanger's hot side first).
    """
    return tuple((form.item, "ZERO_FLOW") for form in forms if _trigger_dormant(form, state))


#: One entry of an opening's fixed point: a lifted split or a dormancy-form outlet.
type OpeningEntry = LiftedSplit | DormancyForm


def _opening_order(
    splits: Sequence[LiftedSplit], dormancy: Sequence[DormancyForm], units: Sequence[str]
) -> tuple[OpeningEntry, ...]:
    """T05b spec §7.8 (ii) 1's pass order: units in declaration order (`units`, the region's);
    within a unit its lifted split, then its dormancy-form outlets as `dormancy` lists them (an
    exchanger's hot before cold)."""
    at = {unit: index for index, unit in enumerate(units)}
    keyed: list[tuple[tuple[int, int, int], OpeningEntry]] = [
        ((at[split.unit], 0, k), split) for k, split in enumerate(splits)
    ]
    keyed += [((at[form.unit], 1, k), form) for k, form in enumerate(dormancy)]
    return tuple(entry for _, entry in sorted(keyed, key=lambda pair: pair[0]))


def _same(a: float, b: float) -> bool:
    """Bitwise equality of two finite doubles as ADR 0001 D3.1 reads them: `+0.0` is not `-0.0`."""
    return a == b and math.copysign(1.0, a) == math.copysign(1.0, b)


def _reset_outlet(state: dict[str, float], form: DormancyForm) -> bool:
    """T05b spec §7.8 (ii)'s outlet reset: the outlet's flows set to its mole balance at `state` —
    pump and exchanger side `n_out,i := n_in,i`, mixer `n_out,i := Σ_k n_in(k),i` summed in
    connection order — wherever they differ from it; exactly `+0.0` on entering (a dormant sum is
    `+0.0`, never `-0.0`). Its temperature keeps its value (the label row closes it on entering,
    the energy row on leaving). On leaving, without it the declared energy row's `T_out`
    coefficient `−Σ n_out c_p` is still zero and the first Jacobian singular (F7). Whether it
    wrote anything."""
    written = False
    for outlet, inlets in form.balance:
        value = state[inlets[0]]
        for name in inlets[1:]:
            value += state[name]
        value += 0.0
        if not _same(state[outlet], value):
            state[outlet] = value
            written = True
    return written


@dataclass(frozen=True)
class _SplitChange:
    """One lifted split's regime change in an opening's fixed point: the split, its branch before
    the change (for attempt 0's `projected(<S>, <branch>, <regime>)` record) and its new regime."""

    split: LiftedSplit
    branch: str
    regime: Regime


def _settle(
    state: Mapping[str, float],
    regimes: Mapping[str, Regime],
    *,
    order: Sequence[OpeningEntry],
    reference: frozenset[str],
    leave: Callable[[LiftedSplit, Mapping[str, float]], _KernelAnswer],
) -> tuple[dict[str, float], dict[str, Regime], dict[str, str], list[_SplitChange]]:
    """T05b spec §7.8 (ii) as amended (Q-S9, R-065; review M1, N1): an opening made consistent
    with exact dormancy, under v2.

    Passes over `order` (`_opening_order`) until one changes nothing. Each pass, per entry:
    **(a)** a lifted split whose feed is exactly dormant and whose regime is not `ZERO_FLOW`
    enters it (§7.4: its lifted flows set to `+0.0`, every other value kept); a split in
    `ZERO_FLOW` whose feed flows leaves it (§7.4: regime and split from `leave`, the provider's TP
    flash at the current state); **(b)** a dormancy-form outlet whose item — read off the current
    state — differs from its `reference` (the previous attempt's items, or at attempt 0 the
    supplied start's) has its flows reset to its mole balance wherever they differ from it, so a
    reset made stale by a later write is redone.

    With `m = len(order)`, an acyclic propagation settles within `m` passes whatever the
    declaration order; a pass `m + 1` that still changes something raises
    `OpeningNotSettledError` naming the first entry (unit id or item key) it changed.

    Returns the settled state and regimes, F2's record (`unit → kernel`, spec §6.5) of each split
    that left `ZERO_FLOW` and did not re-enter it, and every split change in order."""
    opened, settled = dict(state), dict(regimes)
    records: dict[str, str] = {}
    changes: list[_SplitChange] = []
    for index in range(len(order) + 1):
        changed = [
            identifier
            for entry in order
            if (identifier := _rederive(entry, opened, settled, reference, leave, records, changes))
        ]
        if not changed:
            return opened, settled, records, changes
        if index == len(order):
            raise OpeningNotSettledError(changed[0])
    raise AssertionError("unreachable: the last pass returns or raises")


def _rederive(
    entry: OpeningEntry,
    state: dict[str, float],
    regimes: dict[str, Regime],
    reference: frozenset[str],
    leave: Callable[[LiftedSplit, Mapping[str, float]], _KernelAnswer],
    records: dict[str, str],
    changes: list[_SplitChange],
) -> str:
    """One entry of one pass of `_settle`, in place: the entry's id (unit id or item key) if it
    changed the opening, else `""`."""
    if isinstance(entry, DormancyForm):
        if _trigger_dormant(entry, state) == (entry.item in reference):
            return ""
        return entry.item if _reset_outlet(state, entry) else ""
    split = entry
    dormant = _dormant_feed(split, state)
    if dormant == (regimes[split.unit] == "ZERO_FLOW"):
        return ""
    branch = _branch(split, state, v2=True)
    answer = _zero_flow_answer(split) if dormant else leave(split, state)
    state.update(answer.values)
    regimes[split.unit] = answer.regime
    records.pop(split.unit, None)
    if answer.fallback:
        records[split.unit] = answer.fallback
    changes.append(_SplitChange(split, branch, answer.regime))
    return split.unit


def _watched_variables(
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    state: Mapping[str, float],
) -> dict[str, tuple[str, str, str]]:
    """T03 §4.6: the lifted variables whose persistent block means a phase leaves.

    Only a `TWO_PHASE` unit's: each phase's total while the stream flows, and each phase component
    while the stream's own component is positive (T02 §6.3.3's premise, unchanged: with finite,
    positive K-values a flowing phase cannot hold a zero component at a two-phase root). A
    single-phase unit watches nothing: its one phase cannot leave while the stream flows, and a
    component vanishing there is the stream's own (ADR 0001 D3.3), not a phase event.
    """
    watched: dict[str, tuple[str, str, str]] = {}
    for split in splits:
        if regimes[split.unit] != "TWO_PHASE":
            continue
        if sum(state[name] for name in split.feed) <= 0.0:
            continue
        for phase, total, components in (
            ("vapor", split.vapor_total, split.vapor),
            ("liquid", split.liquid_total, split.liquid),
        ):
            watched[total] = (split.unit, phase, total)
            for component, feed in zip(components, split.feed, strict=True):
                if state[feed] > 0.0:
                    watched[component] = (split.unit, phase, component)
    return watched


def _branch_found(split: LiftedSplit, state: Mapping[str, float]) -> Branch:
    """K03 §8.2's branch found for one split (`roots.branch_found`, the one definition)."""
    ((_, branch),) = branch_found([split], state)
    return branch  # type: ignore[return-value]


class _LiftedOps:
    """The lifted EO path's side of the contract (T03 §4.3, §4.6, §4.7), for one attempt.

    An opening here is `(state, regimes)`: a full state over the declaration's variables with
    every lifted split set for the regimes it opens under.
    """

    lifted = True

    def __init__(
        self,
        *,
        splits: Sequence[LiftedSplit],
        regimes: Mapping[str, Regime],
        end_state: Mapping[str, float],
        free: Sequence[str],
        provider: PropertyProvider,
        context: EvaluationContext,
        policy: SolvePolicy,
        region: Region,
        spec: ProblemSpec,
        identity: tuple[str, str],
        ph_units: frozenset[str] = frozenset(),
        v2: bool = False,
        forms: Mapping[str, ZeroFlowForm] | None = None,
        dormancy: Sequence[DormancyForm] = (),
        items: frozenset[str] = frozenset(),
        order: Sequence[OpeningEntry] = (),
        temperatures: Mapping[str, tuple[str, ...]] | None = None,
        memo: ClosureMemo | None = None,
        vapour_only: Mapping[str, VapourOnlyForm] | None = None,
    ) -> None:
        self._splits = splits
        self._regimes = dict(regimes)
        self._end = dict(end_state)
        self._free = tuple(free)
        self._provider = provider
        self._context = context
        self._policy = policy
        self._region = region
        self._spec = spec
        self._identity = identity
        #: The PH-type units under v2 (T05b spec §6.2); empty under v1.
        self._ph_units = ph_units
        #: T05b spec §7: whether `ZERO_FLOW` is a regime (v2), and each split's form.
        self._v2 = v2
        self._forms = forms or {}
        #: M02 design note §14.2 B13: each split's vapour-only form (empty for SYN-001).
        self._vapour_only = vapour_only or {}
        #: T05b spec §7.8: the region's dormancy forms (empty under v1) and the items the closing
        #: attempt ran.
        self._dormancy = tuple(dormancy)
        self._items = items
        #: T05b spec §7.8 (ii) as amended: the opening fixed point's pass order (v2).
        self._order = tuple(order)
        #: T05b spec §6.2 step 3 as amended: each split's temperature columns (v2).
        self._temperatures = temperatures or {}
        #: T05b spec §6.2 as amended: the PH closures the attempt's screen asked, by exact input.
        self._memo = memo
        self.declared_phases: Mapping[str, str] = {
            form.item: form.declared for form in self._dormancy
        }

    def _signature(
        self, regimes: Mapping[str, Regime], state: Mapping[str, float]
    ) -> AttemptSignature:
        """The lifted regimes, then the items of the opening `state` (T05b spec §7.8 (i))."""
        lifted = tuple((split.unit, regimes[split.unit]) for split in self._splits)
        return (*lifted, *_items(self._dormancy, state))

    def _settled(
        self,
        state: Mapping[str, float],
        regimes: Mapping[str, Regime],
        fallbacks: Sequence[tuple[str, str]] = (),
    ) -> tuple[dict[str, float], dict[str, Regime], tuple[tuple[str, str], ...]]:
        """T05b spec §7.8 (ii) as amended (Q-S9, R-065): a restart opening made consistent with
        exact dormancy — every lifted split's `ZERO_FLOW` membership and every item, to a fixed
        point (`_settle`), the closing attempt's items the reference. Returns the opening and F2's
        records (§6.5) of the kernel answers the caller set (`fallbacks`) and of each split the
        fixed point took out of `ZERO_FLOW` (`fallback(<U>, tp)` for a PH-type one), in signature
        order; a split the fixed point changed keeps only its own record. Under v1 the opening is
        returned as given (no `ZERO_FLOW`, no forms)."""
        if not self._v2:
            return dict(state), dict(regimes), tuple(fallbacks)
        opened, settled, records, changes = _settle(
            state, regimes, order=self._order, reference=self._items, leave=self._leave
        )
        merged = dict(fallbacks)
        for change in changes:
            merged.pop(change.split.unit, None)
        merged.update(records)
        ordered = tuple(
            (split.unit, merged[split.unit]) for split in self._splits if split.unit in merged
        )
        return opened, settled, ordered

    def _leave(self, split: LiftedSplit, state: Mapping[str, float]) -> _KernelAnswer:
        """§7.4's leaving: regime and split from the TP flash at `state`, `tp` for PH-type (at
        the feed's `T`, written to the split's temperature columns, as amended by Q-S14)."""
        return _contract_kernel(
            self._provider,
            self._context,
            split,
            state,
            self._ph_units,
            v2=True,
            regime="ZERO_FLOW",
            temperatures=self._temperatures.get(split.unit),
        )

    def _answer(self, split: LiftedSplit, state: Mapping[str, float]) -> _KernelAnswer:
        return _contract_kernel(
            self._provider,
            self._context,
            split,
            state,
            self._ph_units,
            v2=self._v2,
            regime=self._regimes[split.unit],
            temperatures=self._temperatures.get(split.unit),
            memo=self._memo,
        )

    def _projected(
        self, state: Mapping[str, float], unit: str, known: _KernelAnswer | None = None
    ) -> tuple[dict[str, float], dict[str, Regime], tuple[tuple[str, str], ...]]:
        """The state with `unit`'s split from the kernel (`known`, when the caller already asked
        it at this state), the regimes it opens under, and F2's record for it (§6.5)."""
        split = next(entry for entry in self._splits if entry.unit == unit)
        answer = known if known is not None else self._answer(split, state)
        opened, regimes = dict(state), dict(self._regimes)
        opened.update(answer.values)
        regimes[unit] = answer.regime
        return self._settled(opened, regimes, ((unit, answer.fallback),) if answer.fallback else ())

    def converged(self, result: NewtonResult) -> Conversion | None:
        """§4.7(a), by the branch found; the first inadmissible unit restarts in the kernel's."""
        for split in self._splits:
            branch = _branch_found(split, self._end)
            ok, value = _admissible(
                self._provider,
                self._context,
                split,
                branch,
                self._end,
                self._policy.admissibility_epsilon,
            )
            if not ok:
                opened, regimes, fallbacks = self._projected(self._end, split.unit)
                label = INADMISSIBLE_BRANCH[branch]
                return Conversion(
                    signature=self._signature(regimes, opened),
                    opening=(opened, regimes),
                    source="closure_projection",
                    cause=f"inadmissible({split.stream}, {label})",
                    observations={f"admissibility:{split.stream}": value},
                    fallbacks=fallbacks,
                )
        return self._items_disagree()

    def _items_disagree(self) -> Conversion | None:
        """T05b spec §7.8 (iv) 1: an item whose trigger streams flow, or an outlet without one
        whose trigger streams are exactly dormant, restarts with the item toggled. Unreachable
        after the openings and the screen, which compares an empty signature too (§7.8 (iii),
        `newton.another_signature`); specified so that no silent path exists."""
        for form in self._dormancy:
            dormant = _trigger_dormant(form, self._end)
            if dormant == (form.item in self._items):
                continue
            opened, regimes, fallbacks = self._settled(self._end, self._regimes)
            return Conversion(
                signature=self._signature(regimes, opened),
                opening=(opened, regimes),
                source="closure_projection",
                cause=f"inadmissible({form.outlet}, {'dormant' if dormant else 'zero_flow'})",
                fallbacks=fallbacks,
            )
        return None

    def blocked(self, result: NewtonResult) -> Conversion | None:
        """§4.6: `BOUND_BLOCKED` on a watched variable of a `TWO_PHASE` unit — the phase left."""
        watched = _watched_variables(self._splits, self._regimes, self._end)
        found = next((watched[name] for name in result.blocked_by if name in watched), None)
        if found is None:
            return None
        unit, phase, variable = found
        split = next(entry for entry in self._splits if entry.unit == unit)
        remaining: Regime = "LIQUID" if phase == "vapor" else "VAPOR"
        opened, regimes = dict(self._end), dict(self._regimes)
        _pin(opened, split, remaining)
        regimes[unit] = remaining
        opened, regimes, fallbacks = self._settled(opened, regimes)
        return Conversion(
            signature=self._signature(regimes, opened),
            opening=(opened, regimes),
            source="pinned_iterate",
            cause=f"phase_disappeared({unit}, {phase}, {variable})",
            fallbacks=fallbacks,
        )

    def kernel_disagrees(self, result: NewtonResult) -> Conversion | None:
        """§4.7(b): the kernel's regime at the end state (the last accepted iterate)."""
        for split in self._splits:
            answer = self._answer(split, self._end)
            if answer.regime != self._regimes[split.unit]:
                # The TP flash is asked again for the opening, as v1 always has; a PH closure (up
                # to ~3 000 provider calls on its band route, W0.6) is not asked twice.
                known = answer if split.unit in self._ph_units else None
                opened, regimes, fallbacks = self._projected(self._end, split.unit, known)
                return Conversion(
                    signature=self._signature(regimes, opened),
                    opening=(opened, regimes),
                    source="closure_projection",
                    cause=f"kernel_disagrees({split.unit}, {answer.regime})",
                    fallbacks=fallbacks,
                )
        return None

    def at_candidate(self, candidate: Candidate, cause: str) -> Conversion:
        """§4.5: the candidate's full state, each changed unit's split from the kernel there."""
        opened = dict(self._end)
        opened.update(zip(self._free, (float(value) for value in candidate.x), strict=True))
        # T05b spec §7.8 (iii): the screen read the candidate's items off this same state; checked,
        # as the split regimes below are. The opening's own items are recomputed after the lifted
        # part is set (§7.8 (ii)), and may differ from these (an upstream split the kernel sets).
        reported = tuple(entry for entry in candidate.signature if entry[0] not in self._regimes)
        if _items(self._dormancy, opened) != reported:
            raise RuntimeError(
                f"defect: the items at the candidate are {_items(self._dormancy, opened)}, the "
                f"screen reported {reported} (iteration {candidate.iteration}, halving "
                f"{candidate.halving})"
            )
        # T05b spec §7.8 (ii) 5 (ruling Q-S12, both literals): every changed unit's kernel is
        # asked at the candidate itself, and only then are the answers written. Writing each
        # answer before asking the next unit would ask a split whose feed an earlier answer had
        # rewritten (a products-style split's products are the next flash's feed) at a state the
        # screen never saw (re-review M2). Each answer writes only its own split's columns, so the
        # writes are disjoint and their order is immaterial; the lag this leaves between a
        # downstream split's products and its rewritten feed sits on linear mole rows.
        answers: list[tuple[str, _KernelAnswer]] = []
        for unit, regime in candidate.signature:
            if unit not in self._regimes:
                continue
            if regime != self._regimes[unit]:
                split = next(entry for entry in self._splits if entry.unit == unit)
                # The kernel's regime equals the candidate's by construction: the screen took
                # the candidate's reported regime from this same kernel at this same state — or,
                # for a PH-type split, from the band's end enthalpies, which name the regime of
                # every `ok` closure (T05b spec §6.2 as amended). Checked, not assumed (review N4):
                # otherwise the cause and the new signature would disagree. The one sanctioned
                # difference: a flowing PH-type split's closure refused inside the domain range,
                # and the TP fallback (recorded `tp`) governs the opened signature. It does not
                # cover a leaving answer (Q-S15 (3)): the screen reports that from the same TP
                # flash at the same inputs, so a difference there is a defect.
                answer = self._answer(split, opened)
                sanctioned = (
                    split.unit in self._ph_units
                    and answer.fallback == "tp"
                    and self._regimes[unit] != "ZERO_FLOW"
                )
                if answer.regime != regime and not sanctioned:
                    raise RuntimeError(
                        f"defect: the kernel reports {unit} {answer.regime} at the candidate the "
                        f"screen reported {regime} at (iteration {candidate.iteration}, halving "
                        f"{candidate.halving})"
                    )
                answers.append((unit, answer))
        regimes = dict(self._regimes)
        fallbacks: list[tuple[str, str]] = []
        for unit, answer in answers:
            opened.update(answer.values)
            regimes[unit] = answer.regime
            if answer.fallback:
                fallbacks.append((unit, answer.fallback))
        opened, regimes, settled = self._settled(opened, regimes, fallbacks)
        return Conversion(
            signature=self._signature(regimes, opened),
            opening=(opened, regimes),
            source="phase_rejected_trial",
            cause=cause,
            trial=candidate,
            fallbacks=settled,
        )

    def opening_check(self, conversion: Conversion) -> OpeningRefusal | None:
        """§5.1 on the lifted path: pinned variables exactly `+0.0`, every variable finite."""
        state, regimes = conversion.opening
        pinned = tuple(
            name
            for split in self._splits
            for name in _pinned(split, regimes[split.unit], self._forms, self._vapour_only)
        )
        held = set(pinned)
        free = tuple(name for name in self._region.variable_ids if name not in held)
        model_version, constants = self._identity
        requirement = OpeningRequirement(
            signature=conversion.signature,
            model_version=model_version,
            constants_sha256=constants,
            free=free,
            pinned=pinned,
            lower_bounds={
                name: 0.0 for name in free if self._spec.variable_kinds.get(name) == "molar_flow"
            },
        )
        return check_opening(
            OpeningState(values=state, model_version=model_version, constants_sha256=constants),
            requirement,
        )


def _attempt_screen(
    *,
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    context: EvaluationContext,
    epsilon: float,
    ph_units: frozenset[str],
    v2: bool = False,
    dormancy: Sequence[DormancyForm] = (),
    temperatures: Mapping[str, tuple[str, ...]] | None = None,
    memo: ClosureMemo | None = None,
) -> Callable[[dict[str, float]], AttemptSignature | Evaluation]:
    """The attempt's screen: T03's (`_screen`) under v1 — every v1 attempt, called exactly as
    before — else the same screen with F2's kernel on the PH-type units (T05b spec §6.2), the
    dormancy agreement of every split (§7.3), and each dormancy form's item read off the trial
    (§7.8 (iii)). `temperatures` and `memo` are the openings' (§6.2 as amended): a full PH
    closure the screen asks is kept in `memo` for an opening at the same state."""
    if not v2:
        return _screen(
            splits=splits, regimes=regimes, provider=provider, context=context, epsilon=epsilon
        )
    return _build_screen(
        splits,
        regimes,
        provider,
        context,
        epsilon,
        ph_units,
        v2=True,
        dormancy=dormancy,
        temperatures=temperatures,
        memo=memo,
    )


def _screen(
    *,
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    context: EvaluationContext,
    epsilon: float,
) -> Callable[[dict[str, float]], AttemptSignature | Evaluation]:
    """T03 §4.3: K03 §8.2 on each single-phase unit at a trial; the kernel on a flagged one."""
    return _build_screen(splits, regimes, provider, context, epsilon, frozenset())


def _build_screen(
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    context: EvaluationContext,
    epsilon: float,
    ph_units: frozenset[str],
    v2: bool = False,
    dormancy: Sequence[DormancyForm] = (),
    temperatures: Mapping[str, tuple[str, ...]] | None = None,
    memo: ClosureMemo | None = None,
) -> Callable[[dict[str, float]], AttemptSignature | Evaluation]:
    """`_screen`'s body. The flag is v1's under both literals; under v2 a flagged PH-type unit
    (`ph_units`) reports its PH closure's regime, and the TP flash's only when the closure gives
    none (T05b spec §6.2). As amended (Q-S10, R-053) the regime is read off the band's end
    enthalpies (`_band_regime`, (s1)–(s2)); only inside a `τ_E` zone of an end, or when an
    evaluation there is not `ok`, is the full closure asked (s3), and its answer is kept in
    `memo` (with `temperatures`' columns, as an opening would ask it) for the opening.

    Under v2 (`v2`) every split is first checked for T05b spec §7.3's agreement — one comparison:
    a dormant feed reports `ZERO_FLOW`; a `ZERO_FLOW` split whose feed flows reports the TP
    flash's regime (it is leaving, and its pinned split carries no enthalpy, §7.4) at the
    leaving answer's inputs — for a PH-type split its feed's `T` (Q-S15 (3)). After the
    splits, each dormancy form's item is reported from the trial's trigger dormancy (§7.8 (iii),
    one comparison per outlet): an item the attempt does not run, or runs against a flowing
    trigger, makes the reported signature differ, and the trial is phase-rejected."""

    from openflowsheet.verify.checks import VerifierError

    def screen(state: dict[str, float]) -> AttemptSignature | Evaluation:
        # The screen calls the provider outside the compiled residual, so it converts a refusal
        # exactly as the residual does (review S1): a spent budget is an `error` evaluation (the
        # executor reports `BUDGET_EXHAUSTED` from its meter), a provider that will not give the
        # K-values is `invalid_trial_state`. Neither may escape the attempt loop.
        try:
            return reported_signature(state)
        except BudgetExhaustedError as exhausted:
            return Evaluation(status="error", message=str(exhausted))
        except VerifierError as refused:
            return Evaluation(status="invalid_trial_state", message=str(refused))

    def reported_signature(state: dict[str, float]) -> AttemptSignature | Evaluation:
        reported: list[tuple[str, PhaseSignature]] = []
        for split in splits:
            regime = regimes[split.unit]
            if v2 and _dormant_feed(split, state):
                reported.append((split.unit, "ZERO_FLOW"))
                continue
            if v2 and regime == "ZERO_FLOW":
                # §7.4 as amended (Q-S15 (3)): a PH-type split reports the TP flash at the
                # leaving answer's inputs — its feed's `T` (`_contract_kernel`), not its own
                # `T` column, the zero-flow label of an earlier feed.
                leaving = tp_regime(split, state, leaving=split.unit in ph_units)
                if isinstance(leaving, Evaluation):
                    return leaving
                reported.append((split.unit, leaving))
                continue
            if regime == "TWO_PHASE":
                reported.append((split.unit, regime))
                continue
            ok, _ = _admissible(provider, context, split, regime, state, epsilon)
            if ok:
                reported.append((split.unit, regime))
                continue
            if split.unit in ph_units:
                screened = screened_regime(split, state)
                if screened is not None and screened != TP_REGIME:
                    reported.append((split.unit, screened))
                    continue
                if screened is None:
                    answer = asked(split, state)
                    if answer is not None:
                        reported.append((split.unit, answer.regime))
                        continue
            kernel = tp_regime(split, state)
            if isinstance(kernel, Evaluation):
                return kernel
            reported.append((split.unit, kernel))
        return (*reported, *_items(dormancy, state))

    def screened_regime(
        split: LiftedSplit, state: dict[str, float]
    ) -> Regime | Literal["tp"] | None:
        """§6.2 (s1)–(s2): the band ends' regime, `TP_REGIME`, or `None` for (s3)."""
        target = _split_enthalpy(provider, context, split, state)
        if target is None:
            return None
        feed = tuple(state[name] for name in split.feed)
        return _band_regime(provider, context, feed, state[split.pressure], target)

    def asked(split: LiftedSplit, state: dict[str, float]) -> _KernelAnswer | None:
        """§6.2 (s3): the full closure, kept for an opening at the same state."""
        key = _closure_key(split, state)
        if memo is not None and key in memo:
            return memo[key]
        answer = _ph_closure(provider, context, split, state, (temperatures or {}).get(split.unit))
        if memo is not None:
            memo[key] = answer
        return answer

    def tp_regime(
        split: LiftedSplit, state: dict[str, float], *, leaving: bool = False
    ) -> PhaseSignature | Evaluation:
        """The provider's TP flash of the split's feed at the trial, or its refusal: at the
        split's own `T`, or — for a PH-type split `leaving` `ZERO_FLOW` — at its feed's `T`,
        as the opening's leaving answer asks it (`_contract_kernel`)."""
        temperature = temperature_id(split.stream) if leaving else split.temperature
        stream = StreamState(
            n=tuple(state[name] for name in split.feed),
            temperature=state[temperature],
            pressure=state[split.pressure],
        )
        band: PhaseSignature | None = None
        if _pr_c1(provider):
            # M02 design note §14.2 B14: the kernel's regime, so the dew band reads VAPOR here as
            # in `_kernel` (build log D38).
            band, _, flashed = classify(
                provider, context, stream.n, stream.temperature, stream.pressure
            )
        else:
            flashed = provider.flash(FlashRequest(state=stream), context)
        if flashed.status != "ok" or flashed.phase_signature is None:
            # The provider's own status (review N3; K03 §5.5: the unit, the status and the
            # message). Newton halves on any of them but `error`, which ends the attempt.
            return Evaluation(
                status="invalid_trial_state" if flashed.status == "ok" else flashed.status,
                message=(
                    f"the kernel refused {split.unit}'s regime ({split.stream}) at the "
                    f"trial: {flashed.status}: {flashed.message}"
                ),
            )
        if band == "VAPOR":
            return band
        if flashed.phase_signature in ("LIQUID", "VAPOR"):
            return flashed.phase_signature
        return "TWO_PHASE"

    return screen


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
    attempt; SYN-001's splits have none.

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
    contract opens after it runs the Newton core on the target (T04 §4.5).

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
    active_splits = [split for split in splits if split.unit in set(region.units)]
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
    order = _opening_order(active_splits, dormancy, region.units) if v2 else ()
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

    def closed(outcome: SolveOutcome, text: str = "") -> RegionResult:
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
        if warm_start and attempt_index == 0 and recovery is None:
            # ADR 0024 D3: an external start is checked, not silently pinned — T03 §5.1 on the
            # opening this attempt would take, in place of `CHECKPOINT_INCOMPATIBLE`.
            held = tuple(
                name
                for split in active_splits
                for name in _pinned(split, regimes[split.unit], forms, vapour)
            )
            refused = check_opening(
                OpeningState(
                    values=current, model_version=identity[0], constants_sha256=identity[1]
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
            return closed("CONVERGED")
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
