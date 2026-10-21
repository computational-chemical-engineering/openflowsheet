"""`syn001.cascade` — an N-stage countercurrent equilibrium-stage cascade (S01 spec).

Stages `j = 1..N` are numbered top to bottom: liquid flows down, vapour flows up. The `top` inlet
enters stage 1, the `bottom` inlet stage N, and side feeds a declared stage, each in a declared
single phase. There is no condenser, reboiler or reflux (S01 spec §1; those are S02's).

**This module is the unit layer only** (S01 spec §12 WO-1): the specification object and its §5
refusals, the §2 declared rows built from `models.rows`, the per-stage regime forms of §4.2, the
§6 analytic initializer `s01-kremser-cmo-v1` and the §4.6 closed-form answer for an all-dormant
cascade. Compiling, the isothermal pre-solve and the `solve_region` call are WO-2's.

**Every stage is one lifted split, PH-type** (S01 spec §4.1): its mixed inflow `m_j` is lifted
(DECISION 3), so `feed = m_j`, and its energy row fixes `T_j`. Equilibrium is written
division-free (`rows.equilibrium_row`), so every row stays finite at a vanished phase; the trivial
splits it also admits are excluded by the phase contract, not by the rows.

Column ids (build decision, `docs/S01_DECISIONS.md`): stage `j`'s columns are
`<U>.stage.<j>.{l,v,m}.<c>`, `<U>.stage.<j>.{L,V,T,P,Q}`; an inlet's are `flow_id`,
`temperature_id` and `pressure_id` of the stream `<U>.inlet.<port>`. Row ids are
`<U>:stage:<j>:<kind>[:<c>]` (spec §12) and `<U>:inlet:<port>:<kind>[:<c>]`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.canonical import normalize_zero
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import (
    EquationSpec,
    ProblemSpec,
    QuantityKind,
    RowBuilder,
)
from openflowsheet.compiled import EvaluationContext, RowAccumulation
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    Holdup,
    SpecificationError,
    flow_id,
    origin,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.rows import (
    balance_row,
    definition_row,
    energy_row,
    equilibrium_row,
    specification_row,
)
from openflowsheet.models.syn001 import (
    COMPONENTS,
    ENERGY,
    MOLAR_FLOW,
    MOLE,
    P_MAX,
    P_MIN,
    POWER,
    PRESSURE,
    T_MAX,
    T_MIN,
    TEMPERATURE,
)
from openflowsheet.models.syn001.blocks import EnthalpyFlowBlock, LnKBlock
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.models.syn001.tp_state import (
    enthalpy_block_id,
    enthalpy_flow,
    lnk_block_id,
)
from openflowsheet.orchestrator.region import Regime
from openflowsheet.thermo import Phase, PropertyProvider, PropertyRequest, StreamState

MODEL_ID: Final = "syn001.cascade"

#: Where the equations are stated.
SPECIFICATION: Final = "docs/derivations/S01-spec.md §2"

#: Spec §6's registered initializer.
INITIALIZER_ID: Final = "s01-kremser-cmo-v1"

#: Spec §6.2 (DECISION 7): `β̄` is clamped to this interval, and each CMO total is floored at
#: `CMO_FLOOR · F`.
BETA_BOUNDS: Final = (0.1, 0.9)
CMO_FLOOR: Final = 0.1

#: The declared inlet phases S01 accepts; any other is `unsupported(two_phase_inlet:<port>)`.
INLET_PHASES: Final[tuple[Phase, ...]] = ("LIQUID", "VAPOR")

#: The two fixed ports. Side feeds carry their own port names.
TOP: Final = "top"
BOTTOM: Final = "bottom"

#: A refusal's category (spec §5). `INVALID_SPECIFICATION` is not a `SolveOutcome` value; see the
#: design-lane question in `docs/S01_DECISIONS.md`.
FailureOutcome = Literal[
    "CAPABILITY_UNAVAILABLE",
    "INVALID_SPECIFICATION",
    "INITIALIZATION_FAILED",
]

#: `K_i(T, P)` in component order. The initializer's injection point (spec §10 A02).
KValues = Callable[[float, float], Sequence[float]]

# Block ids are CasADi names (`tp_state._token`), so a unit id or port that cannot be one is
# refused when the rows are built rather than sanitized into a collision.
_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*$")


# -- declarations --------------------------------------------------------------------------------

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="CAS-mix",
        statement=(
            "(l_i,j-1 or top_i) + (v_i,j+1 or bottom_i) + sum side_i@j - m_ij = 0 for every "
            "stage j and component i"
        ),
        dependencies=("stage.l", "stage.v", "stage.m", "inlet.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-mole",
        statement="m_ij - v_ij - l_ij = 0 for every stage j and component i",
        dependencies=("stage.m", "stage.v", "stage.l"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i", quantity="component moles held on the stage", dimension=MOLE
            ),
        ),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-equilibrium",
        statement="v_ij L_j - K_i(T_j, P_j) l_ij V_j = 0 for every stage j and component i",
        dependencies=("stage.v", "stage.l", "stage.L", "stage.V", "stage.T", "stage.P"),
        conditional_class="phase_conditional",
        accumulation=Accumulation(kind="algebraic"),
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-Ldef",
        statement="L_j - sum_i l_ij = 0 for every stage j",
        dependencies=("stage.L", "stage.l"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-Vdef",
        statement="V_j - sum_i v_ij = 0 for every stage j",
        dependencies=("stage.V", "stage.v"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-energy",
        statement=(
            "Q_j + Hdot_in,j - Hdot^V(v_j, T_j) - Hdot^L(l_j, T_j, P_j) = 0 for every stage j, "
            "Q_j positive into the stage"
        ),
        dependencies=("stage.Q", "stage.l", "stage.v", "stage.T", "stage.P", "inlet"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="U", quantity="internal energy of the stage contents", dimension=ENERGY
            ),
        ),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-P",
        statement="P_j - P_j* = 0 for every stage j",
        dependencies=("stage.P", "parameters.P_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-Q",
        statement="Q_j - Q_j* = 0 for every stage j",
        dependencies=("stage.Q", "parameters.Q_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-inlet-n",
        statement="n_ik - n_ik* = 0 for every inlet k and component i",
        dependencies=("inlet.n", "parameters.n_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-inlet-T",
        statement="T_k - T_k* = 0 for every inlet k",
        dependencies=("inlet.T", "parameters.T_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CAS-inlet-P",
        statement="P_k - P_k* = 0 for every inlet k",
        dependencies=("inlet.P", "parameters.P_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
)


# -- the specification ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InletState:
    """One external inlet's fixed `nTP` state and declared phase (spec §3).

    `phase` is a plain string so a declaration S01 does not support reaches `validate` and is
    refused there (R6) rather than failing a type check somewhere else.
    """

    n: tuple[float, ...]
    temperature: float
    pressure: float
    phase: str


@dataclass(frozen=True)
class SideFeed:
    """An inlet at a declared stage. `port` names it in row ids and refusal codes."""

    port: str
    stage: int
    state: InletState


@dataclass(frozen=True)
class PlacedInlet:
    """An inlet with the stage it enters: `top` at 1, `bottom` at N, side feeds where declared."""

    port: str
    stage: int
    state: InletState


@dataclass(frozen=True)
class CascadeSpec:
    """The S01 specification set (spec §3): N, `P_j*`, `Q_j*` and every inlet.

    Nothing is checked on construction; `validate` applies spec §5 and answers with a typed
    refusal, so an invalid specification can be stated and refused rather than raising.
    """

    unit_id: str
    stage_count: int
    #: `P_j*`, Pa, one per stage, top to bottom.
    pressures: tuple[float, ...]
    #: `Q_j*`, W, positive into the stage (ADR 0001 D4.1); `0` is adiabatic.
    duties: tuple[float, ...]
    top: InletState
    bottom: InletState
    sides: tuple[SideFeed, ...] = ()
    components: tuple[str, ...] = COMPONENTS

    def inlets(self) -> tuple[PlacedInlet, ...]:
        """`top`, `bottom`, then the side feeds in declaration order — the order every sum over
        inlets is formed in (the generator's)."""
        return (
            PlacedInlet(TOP, 1, self.top),
            PlacedInlet(BOTTOM, self.stage_count, self.bottom),
            *(PlacedInlet(side.port, side.stage, side.state) for side in self.sides),
        )


@dataclass(frozen=True)
class CascadeFailure:
    """A typed refusal or failure: the outcome and its cause code (spec §4.5, §5)."""

    outcome: FailureOutcome
    cause: str
    message: str = ""


# -- names ---------------------------------------------------------------------------------------


def stage_prefix(unit: str, stage: int) -> str:
    return f"{unit}.stage.{stage}"


def liquid_id(unit: str, stage: int, component: str) -> str:
    return f"{stage_prefix(unit, stage)}.l.{component}"


def vapor_id(unit: str, stage: int, component: str) -> str:
    return f"{stage_prefix(unit, stage)}.v.{component}"


def mixed_id(unit: str, stage: int, component: str) -> str:
    return f"{stage_prefix(unit, stage)}.m.{component}"


def liquid_total_id(unit: str, stage: int) -> str:
    return f"{stage_prefix(unit, stage)}.L"


def vapor_total_id(unit: str, stage: int) -> str:
    return f"{stage_prefix(unit, stage)}.V"


def stage_temperature_id(unit: str, stage: int) -> str:
    return f"{stage_prefix(unit, stage)}.T"


def stage_pressure_id(unit: str, stage: int) -> str:
    return f"{stage_prefix(unit, stage)}.P"


def stage_duty_id(unit: str, stage: int) -> str:
    return f"{stage_prefix(unit, stage)}.Q"


def inlet_stream(unit: str, port: str) -> str:
    return f"{unit}.inlet.{port}"


def stage_row_id(unit: str, stage: int, kind: str, *component: str) -> str:
    """`<U>:stage:<j>:<kind>[:<c>]` (spec §12 WO-1)."""
    return row_id(unit, "stage", str(stage), kind, *component)


def inlet_row_id(unit: str, port: str, kind: str, *component: str) -> str:
    return row_id(unit, "inlet", port, kind, *component)


def energy_row_id(unit: str, stage: int) -> str:
    return stage_row_id(unit, stage, "energy")


def label_row_id(unit: str, stage: int) -> str:
    """The `ZERO_FLOW` label row `T_j − T_label` that replaces `energy_j` (spec §4.2). A row of an
    attempt's system, not of the declaration."""
    return stage_row_id(unit, stage, "label")


def label_column(spec: CascadeSpec, stage: int) -> str:
    """Spec §4.3 (DECISION 4): `T_{j−1}` for j > 1, the `top` inlet's temperature for j = 1."""
    if stage == 1:
        return temperature_id(inlet_stream(spec.unit_id, TOP))
    return stage_temperature_id(spec.unit_id, stage - 1)


def _parameter(column: str) -> str:
    return f"{column}*"


# -- spec §5: validation -------------------------------------------------------------------------


def _invalid(code: str, message: str) -> CascadeFailure:
    return CascadeFailure("INVALID_SPECIFICATION", f"invalid_spec({code})", message)


def _k_values(
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
    temperature: float,
    pressure: float,
) -> tuple[float, ...]:
    """`K_i(T, P)` from the provider's `lnK`, as the rows' `LnKBlock` asks for it."""
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(
                n=(1.0,) * len(components), temperature=temperature, pressure=pressure
            ),
            phase="LIQUID",
            properties=("lnK",),
        ),
        context,
    )
    if result.status != "ok":
        raise RuntimeError(
            f"lnK at T = {temperature!r} K, P = {pressure!r} Pa: {result.status}: {result.message}"
        )
    return tuple(math.exp(result.values[f"lnK_{name}"]) for name in components)


def _enthalpy_flow(
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
    n: Sequence[float],
    temperature: float,
    pressure: float,
    phase: Phase,
) -> float:
    status, value, message = enthalpy_flow(
        provider,
        StreamState(
            n=tuple(normalize_zero(float(a)) for a in n),
            temperature=temperature,
            pressure=pressure,
        ),
        phase,
        components,
        context,
    )
    if status != "ok":
        raise RuntimeError(f"Hdot^{phase} at T = {temperature!r} K: {status}: {message}")
    return value


def _in_domain(value: float, bounds: tuple[float, float]) -> bool:
    return math.isfinite(value) and bounds[0] <= value <= bounds[1]


def _is_dormant(state: InletState) -> bool:
    return all(float(a) == 0.0 for a in state.n)


def validate(
    spec: CascadeSpec, provider: PropertyProvider, context: EvaluationContext
) -> CascadeFailure | None:
    """Spec §5, before any row is evaluated: the first refusal that applies, or `None`.

    Checked in the order R1, R2, R3, R4, R6, R5, R7: R6 precedes R5 because admissibility is a
    question about a declared phase. A malformed object (a flow vector of the wrong length, a
    pressure or duty list that is not one per stage, a non-finite duty, a duplicated port) is
    misuse and raises `ValueError`; it is not one of §5's refusals.
    """
    unit, components = spec.unit_id, spec.components
    count = spec.stage_count
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        return _invalid("stage_count", f"{unit}: N = {count!r} is not an integer >= 1")
    if len(spec.pressures) != count or len(spec.duties) != count:
        raise ValueError(
            f"{unit}: {len(spec.pressures)} pressures and {len(spec.duties)} duties for "
            f"{count} stages"
        )
    for stage, duty in enumerate(spec.duties, start=1):
        if not math.isfinite(duty):
            raise ValueError(f"{unit}: Q_{stage}* = {duty!r} is not finite")
    inlets = spec.inlets()
    ports = [inlet.port for inlet in inlets]
    if len(set(ports)) != len(ports):
        raise ValueError(f"{unit}: inlet ports {ports} are not distinct")
    for inlet in inlets:
        if len(inlet.state.n) != len(components):
            raise ValueError(
                f"{unit}: inlet {inlet.port} carries {len(inlet.state.n)} flows for "
                f"{len(components)} components"
            )

    # R2
    for inlet in inlets:
        if not all(math.isfinite(a) and a >= 0.0 for a in inlet.state.n):
            return _invalid(
                f"inlet_flow:{inlet.port}",
                f"{unit}: inlet {inlet.port} flows {inlet.state.n} are not finite and >= 0",
            )
    # R3
    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        for column, value, bounds in (
            (temperature_id(stream), inlet.state.temperature, (T_MIN, T_MAX)),
            (pressure_id(stream), inlet.state.pressure, (P_MIN, P_MAX)),
        ):
            if not _in_domain(value, bounds):
                return _invalid(f"domain:{column}", f"{column} = {value!r} outside {bounds}")
    for stage, value in enumerate(spec.pressures, start=1):
        column = stage_pressure_id(unit, stage)
        if not _in_domain(value, (P_MIN, P_MAX)):
            return _invalid(f"domain:{column}", f"{column} = {value!r} outside {(P_MIN, P_MAX)}")
    # R4
    taken: set[int] = set()
    for side in spec.sides:
        stage = side.stage
        if (
            isinstance(stage, bool)
            or not isinstance(stage, int)
            or not 1 <= stage <= count
            or stage in taken
        ):
            return _invalid(
                f"side_feed_stage:{side.port}",
                f"{unit}: side feed {side.port} at stage {stage!r} (N = {count}; one side feed "
                "per stage)",
            )
        taken.add(stage)
    # R6
    for inlet in inlets:
        if inlet.state.phase not in INLET_PHASES:
            return CascadeFailure(
                "CAPABILITY_UNAVAILABLE",
                f"unsupported(two_phase_inlet:{inlet.port})",
                f"{unit}: inlet {inlet.port} declared {inlet.state.phase!r}; S01 takes a declared "
                "LIQUID or VAPOR inlet only",
            )
    # R5
    for inlet in inlets:
        state = inlet.state
        if _is_dormant(state):
            continue
        k = _k_values(provider, context, components, state.temperature, state.pressure)
        total = sum(state.n)
        if state.phase == "LIQUID":
            criterion = sum(a / total * ki for a, ki in zip(state.n, k, strict=True))
        else:
            criterion = sum(a / total / ki for a, ki in zip(state.n, k, strict=True))
        if not criterion <= 1.0:
            return CascadeFailure(
                "INVALID_SPECIFICATION",
                f"inadmissible_inlet({inlet.port}, {state.phase})",
                f"{unit}: inlet {inlet.port} is not an admissible {state.phase} "
                f"(criterion {criterion!r} > 1)",
            )
    # R7
    if is_dormant(spec):
        # Every inlet dormant: §4.6's closed form answers (see the design-lane question in
        # docs/S01_DECISIONS.md on R7's scope).
        return None
    precheck = energy_precheck(spec, provider, context)
    if not precheck.lower <= precheck.target <= precheck.upper:
        return CascadeFailure(
            "INVALID_SPECIFICATION",
            "infeasible_spec(energy_outside_domain)",
            f"{unit}: H* = {precheck.target!r} W outside "
            f"[{precheck.lower!r}, {precheck.upper!r}] W",
        )
    return None


@dataclass(frozen=True)
class EnergyPrecheck:
    """Spec §5 R7's quantities, W: `H_in = Σ_k Ḣ_k`, `H* = H_in + Σ_j Q_j*` and the bounds
    `Σ_i F_i h_i^L(T_min, P_N*)`, `Σ_i F_i h_i^V(T_max)`."""

    inflow: float
    target: float
    lower: float
    upper: float


def energy_precheck(
    spec: CascadeSpec, provider: PropertyProvider, context: EvaluationContext
) -> EnergyPrecheck:
    """R7's necessary condition (spec §5): since `max h^L < min h^V` on the domain, no in-domain
    state carries an `H*` outside `[lower, upper]`. Each inlet's enthalpy is at its own `(T, P)`
    in its declared phase (DECISION 8); a dormant inlet contributes exactly `0`."""
    components, inlets = spec.components, spec.inlets()
    totals = [sum(inlet.state.n[i] for inlet in inlets) for i in range(len(components))]
    h_in = sum(
        _enthalpy_flow(
            provider,
            context,
            components,
            inlet.state.n,
            inlet.state.temperature,
            inlet.state.pressure,
            _phase(inlet.state),
        )
        for inlet in inlets
    )
    p_bottom = spec.pressures[-1]
    return EnergyPrecheck(
        inflow=h_in,
        target=h_in + sum(spec.duties),
        lower=_enthalpy_flow(provider, context, components, totals, T_MIN, p_bottom, "LIQUID"),
        upper=_enthalpy_flow(provider, context, components, totals, T_MAX, p_bottom, "VAPOR"),
    )


def _phase(state: InletState) -> Phase:
    if state.phase == "LIQUID":
        return "LIQUID"
    if state.phase == "VAPOR":
        return "VAPOR"
    raise ValueError(f"inlet phase {state.phase!r} is not LIQUID or VAPOR; validate first")


# -- spec §2: declared rows ----------------------------------------------------------------------


def _token(text: str) -> str:
    if not _TOKEN.match(text):
        raise SpecificationError(
            f"{text!r} cannot name a property block: a letter followed by letters, digits and "
            "non-consecutive underscores"
        )
    return text


def declared_rows(
    spec: CascadeSpec, provider: PropertyProvider, context: EvaluationContext
) -> Contribution:
    """The §2 columns, rows, blocks and pinned inputs: `14N + (C + 2) n_in` of each.

    The cascade owns every column it declares (stage and inlet), so all of them are in
    `variable_ids`. Stage j's columns come first, in stage order, then each inlet's. Call after
    `validate`.
    """
    unit, components = _token(spec.unit_id), spec.components
    count = spec.stage_count
    inlets = spec.inlets()
    for inlet in inlets:
        _token(inlet.port)

    variables: list[str] = []
    variable_kinds: dict[str, QuantityKind] = {}
    equations: list[EquationSpec] = []
    row_kinds: dict[str, QuantityKind] = {}
    blocks: list[LnKBlock | EnthalpyFlowBlock] = []
    block_inputs: dict[str, tuple[str, ...]] = {}
    parameter_ids: list[str] = []
    parameters: dict[str, float] = {}

    def column(name: str, kind: QuantityKind) -> None:
        variables.append(name)
        variable_kinds[name] = kind

    def row(
        equation_id: str,
        build: RowBuilder,
        accumulation: RowAccumulation,
        family: str,
        kind: QuantityKind,
    ) -> None:
        equations.append(
            EquationSpec(
                equation_id=equation_id,
                build=build,
                accumulation=accumulation,
                origin=origin(MODEL_ID, family),
            )
        )
        row_kinds[equation_id] = kind

    def pin(name: str, value: float) -> str:
        parameter = _parameter(name)
        parameter_ids.append(parameter)
        parameters[parameter] = normalize_zero(float(value))
        return parameter

    # Enthalpy blocks: one per (stage, phase) outlet and one per inlet. Each internal stream has
    # one block, read with + by the stage it enters and with - by the stage it leaves, so the
    # overall energy closure of spec §2 cancels term by term.
    vapor_keys: dict[int, tuple[str, ...]] = {}
    liquid_keys: dict[int, tuple[str, ...]] = {}
    lnk_keys: dict[int, str] = {}
    for stage in range(1, count + 1):
        token = f"{unit}_s{stage}"
        lnk = LnKBlock(provider, components, context, block_id=lnk_block_id(token))
        blocks.append(lnk)
        block_inputs[lnk.block_id] = (
            stage_temperature_id(unit, stage),
            stage_pressure_id(unit, stage),
        )
        lnk_keys[stage] = lnk.block_id
        outlets: tuple[
            tuple[Phase, Callable[[str, int, str], str], dict[int, tuple[str, ...]]], ...
        ]
        outlets = (("VAPOR", vapor_id, vapor_keys), ("LIQUID", liquid_id, liquid_keys))
        for phase, flows, keys in outlets:
            block = EnthalpyFlowBlock(
                provider, components, phase, context, block_id=enthalpy_block_id(token, phase)
            )
            blocks.append(block)
            block_inputs[block.block_id] = (
                *(flows(unit, stage, c) for c in components),
                stage_temperature_id(unit, stage),
                stage_pressure_id(unit, stage),
            )
            keys[stage] = tuple(f"{block.block_id}.{out}" for out in block.output_ids)
    inlet_keys: dict[str, tuple[str, ...]] = {}
    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        phase = _phase(inlet.state)
        block = EnthalpyFlowBlock(
            provider,
            components,
            phase,
            context,
            block_id=enthalpy_block_id(f"{unit}_in_{inlet.port}", phase),
        )
        blocks.append(block)
        block_inputs[block.block_id] = (
            *(flow_id(stream, c) for c in components),
            temperature_id(stream),
            pressure_id(stream),
        )
        inlet_keys[inlet.port] = tuple(f"{block.block_id}.{out}" for out in block.output_ids)

    sides_at: dict[int, list[PlacedInlet]] = {}
    for inlet in inlets[2:]:
        sides_at.setdefault(inlet.stage, []).append(inlet)

    for stage in range(1, count + 1):
        for c in components:
            column(liquid_id(unit, stage, c), "molar_flow")
        for c in components:
            column(vapor_id(unit, stage, c), "molar_flow")
        for c in components:
            column(mixed_id(unit, stage, c), "molar_flow")
        column(liquid_total_id(unit, stage), "molar_flow")
        column(vapor_total_id(unit, stage), "molar_flow")
        column(stage_temperature_id(unit, stage), "temperature")
        column(stage_pressure_id(unit, stage), "pressure")
        column(stage_duty_id(unit, stage), "heat_rate")

        sides = sides_at.get(stage, [])
        for c in components:
            above = (
                flow_id(inlet_stream(unit, TOP), c) if stage == 1 else liquid_id(unit, stage - 1, c)
            )
            below = (
                flow_id(inlet_stream(unit, BOTTOM), c)
                if stage == count
                else vapor_id(unit, stage + 1, c)
            )
            inflow = (above, below, *(flow_id(inlet_stream(unit, s.port), c) for s in sides))
            row(
                stage_row_id(unit, stage, "mix", c),
                balance_row(inflow, (mixed_id(unit, stage, c),)),
                "algebraic",
                "CAS-mix",
                "molar_flow",
            )
        for c in components:
            row(
                stage_row_id(unit, stage, "mole", c),
                balance_row(
                    (mixed_id(unit, stage, c),),
                    (vapor_id(unit, stage, c), liquid_id(unit, stage, c)),
                ),
                "holdup_balance",
                "CAS-mole",
                "molar_flow",
            )
        for c in components:
            row(
                stage_row_id(unit, stage, "eq", c),
                equilibrium_row(
                    vapor_id(unit, stage, c),
                    liquid_id(unit, stage, c),
                    vapor_total_id(unit, stage),
                    liquid_total_id(unit, stage),
                    f"{lnk_keys[stage]}.lnK_{c}",
                ),
                "algebraic",
                "CAS-equilibrium",
                "molar_flow_squared",
            )
        row(
            stage_row_id(unit, stage, "Ldef"),
            definition_row(
                liquid_total_id(unit, stage), tuple(liquid_id(unit, stage, c) for c in components)
            ),
            "algebraic",
            "CAS-Ldef",
            "molar_flow",
        )
        row(
            stage_row_id(unit, stage, "Vdef"),
            definition_row(
                vapor_total_id(unit, stage), tuple(vapor_id(unit, stage, c) for c in components)
            ),
            "algebraic",
            "CAS-Vdef",
            "molar_flow",
        )
        enthalpy_in = (
            *(inlet_keys[TOP] if stage == 1 else liquid_keys[stage - 1]),
            *(inlet_keys[BOTTOM] if stage == count else vapor_keys[stage + 1]),
            *(key for s in sides for key in inlet_keys[s.port]),
        )
        row(
            energy_row_id(unit, stage),
            energy_row(
                enthalpy_in,
                (*vapor_keys[stage], *liquid_keys[stage]),
                source=stage_duty_id(unit, stage),
            ),
            "holdup_balance",
            "CAS-energy",
            "heat_rate",
        )
        row(
            stage_row_id(unit, stage, "P"),
            specification_row(
                stage_pressure_id(unit, stage),
                pin(stage_pressure_id(unit, stage), spec.pressures[stage - 1]),
            ),
            "algebraic",
            "CAS-P",
            "pressure",
        )
        row(
            stage_row_id(unit, stage, "Q"),
            specification_row(
                stage_duty_id(unit, stage),
                pin(stage_duty_id(unit, stage), spec.duties[stage - 1]),
            ),
            "algebraic",
            "CAS-Q",
            "heat_rate",
        )

    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        for c in components:
            column(flow_id(stream, c), "molar_flow")
        column(temperature_id(stream), "temperature")
        column(pressure_id(stream), "pressure")
        for c, value in zip(components, inlet.state.n, strict=True):
            row(
                inlet_row_id(unit, inlet.port, "n", c),
                specification_row(flow_id(stream, c), pin(flow_id(stream, c), value)),
                "algebraic",
                "CAS-inlet-n",
                "molar_flow",
            )
        row(
            inlet_row_id(unit, inlet.port, "T"),
            specification_row(
                temperature_id(stream), pin(temperature_id(stream), inlet.state.temperature)
            ),
            "algebraic",
            "CAS-inlet-T",
            "temperature",
        )
        row(
            inlet_row_id(unit, inlet.port, "P"),
            specification_row(pressure_id(stream), pin(pressure_id(stream), inlet.state.pressure)),
            "algebraic",
            "CAS-inlet-P",
            "pressure",
        )

    return Contribution(
        variable_ids=tuple(variables),
        equations=tuple(equations),
        blocks=tuple(blocks),
        block_inputs=block_inputs,
        parameter_ids=tuple(parameter_ids),
        parameters=parameters,
        variable_kinds=variable_kinds,
        row_kinds=row_kinds,
    )


def declared_problem(rows: Contribution, label: str = MODEL_ID) -> ProblemSpec:
    """The declared rows as a `ProblemSpec`, for the float evaluator (`compile.reference`).

    `label` is a placeholder for evaluation only: the compiled problem's label, which identity
    depends on, is WO-2's to fix.
    """
    problem = ProblemSpec(
        label=label,
        variable_ids=rows.variable_ids,
        equations=rows.equations,
        parameter_ids=rows.parameter_ids,
        parameters=rows.parameters,
        blocks=rows.blocks,
        block_inputs=rows.block_inputs,
        variable_kinds=rows.variable_kinds,
        row_kinds=rows.row_kinds,
    )
    problem.validate()
    return problem


# -- spec §4.2: regime forms ---------------------------------------------------------------------


@dataclass(frozen=True)
class RegimeForm:
    """What stage j pins and drops in one regime (spec §4.2), as ids.

    `pinned` columns are held at `+0.0`; `dropped` rows leave the system. In `ZERO_FLOW` the
    energy row is also `swapped` for the label row `label = (row id, T_j, T_label)`; the swap is
    one-for-one, so `len(pinned) == len(dropped)` in every regime.
    """

    regime: Regime
    pinned: tuple[str, ...]
    dropped: tuple[str, ...]
    swapped: str = ""
    label: tuple[str, str, str] | None = None


def regime_form(spec: CascadeSpec, stage: int, regime: Regime) -> RegimeForm:
    unit, components = spec.unit_id, spec.components
    vapor = (*(vapor_id(unit, stage, c) for c in components), vapor_total_id(unit, stage))
    liquid = (*(liquid_id(unit, stage, c) for c in components), liquid_total_id(unit, stage))
    equilibrium = tuple(stage_row_id(unit, stage, "eq", c) for c in components)
    if regime == "TWO_PHASE":
        return RegimeForm(regime, (), ())
    if regime == "LIQUID":
        return RegimeForm(regime, vapor, (*equilibrium, stage_row_id(unit, stage, "Vdef")))
    if regime == "VAPOR":
        return RegimeForm(regime, liquid, (*equilibrium, stage_row_id(unit, stage, "Ldef")))
    return RegimeForm(
        regime,
        (
            *(liquid_id(unit, stage, c) for c in components),
            *(vapor_id(unit, stage, c) for c in components),
            liquid_total_id(unit, stage),
            vapor_total_id(unit, stage),
        ),
        (
            *equilibrium,
            *(stage_row_id(unit, stage, "mole", c) for c in components),
            stage_row_id(unit, stage, "Ldef"),
            stage_row_id(unit, stage, "Vdef"),
        ),
        swapped=energy_row_id(unit, stage),
        label=(
            label_row_id(unit, stage),
            stage_temperature_id(unit, stage),
            label_column(spec, stage),
        ),
    )


# -- spec §6: the initializer --------------------------------------------------------------------


@dataclass(frozen=True)
class KremserInitial:
    """`x_K` of spec §6 and the intermediate quantities A03 checks."""

    z: tuple[float, ...]
    beta: float
    beta_clamped: float
    pbar: float
    tbar: float
    #: `L_j`, `V_j` of step 4 (CMO, floored), before step 5 replaces them by the sums.
    liquid_cmo: tuple[float, ...]
    vapor_cmo: tuple[float, ...]
    #: `l_ij`, `v_ij`, indexed `[j - 1][i]`.
    liquid: tuple[tuple[float, ...], ...]
    vapor: tuple[tuple[float, ...], ...]
    #: Every declared column, in `declared_rows` order.
    state: Mapping[str, float]
    initializer: str = INITIALIZER_ID


def thomas(
    sub: Sequence[float], diag: Sequence[float], sup: Sequence[float], rhs: Sequence[float]
) -> list[float]:
    """The Thomas algorithm without pivoting (spec §6.5): stable on the cascade's weakly
    column-diagonally-dominant, irreducible matrix. `sub[0]` and `sup[-1]` are not read."""
    n = len(diag)
    c = [0.0] * n
    d = [0.0] * n
    c[0], d[0] = sup[0] / diag[0], rhs[0] / diag[0]
    for j in range(1, n):
        m = diag[j] - sub[j] * c[j - 1]
        c[j] = sup[j] / m if j < n - 1 else 0.0
        d[j] = (rhs[j] - sub[j] * d[j - 1]) / m
    out = [0.0] * n
    out[-1] = d[-1]
    for j in range(n - 2, -1, -1):
        out[j] = d[j] - c[j] * out[j + 1]
    return out


def kremser_initial(
    spec: CascadeSpec,
    provider: PropertyProvider,
    context: EvaluationContext,
    *,
    k_values: KValues | None = None,
) -> KremserInitial | CascadeFailure:
    """Spec §6 `s01-kremser-cmo-v1`, on a validated, flowing specification.

    `k_values` replaces the provider's `K_i(T̄, P_j*)` in step 5 only (spec §10 A02 injects a
    constant `K` to reach the Kremser closed form); `T̄` is always the provider's band
    temperature. An all-dormant specification has no initializer: it is §4.6's
    (`dormant_answer`), and asking here is misuse.
    """
    unit, components = spec.unit_id, spec.components
    count = spec.stage_count
    inlets = spec.inlets()
    width = len(components)
    totals = [sum(inlet.state.n[i] for inlet in inlets) for i in range(width)]
    big_f = sum(totals)
    if big_f == 0.0:
        raise ValueError(f"{unit}: every inlet is dormant; spec §4.6 answers it, not §6")
    z = tuple(a / big_f for a in totals)
    beta = sum(sum(i.state.n) for i in inlets if i.state.phase == "VAPOR") / big_f
    beta_clamped = min(max(beta, BETA_BOUNDS[0]), BETA_BOUNDS[1])
    pbar = sum(spec.pressures) / count

    band = band_temperature(provider, totals, pbar, beta_clamped, context)
    if band.position != "inside" or band.temperature is None:
        return CascadeFailure(
            "INITIALIZATION_FAILED",
            f"initialization_failed({INITIALIZER_ID}, tbar_outside_domain)",
            f"{unit}: T(beta = {beta_clamped!r}) at P = {pbar!r} Pa is {band.position} the domain",
        )
    tbar = band.temperature

    floor = CMO_FLOOR * big_f
    liquid_cmo = tuple(
        max(
            sum(sum(i.state.n) for i in inlets if i.state.phase == "LIQUID" and i.stage <= j),
            floor,
        )
        for j in range(1, count + 1)
    )
    vapor_cmo = tuple(
        max(
            sum(sum(i.state.n) for i in inlets if i.state.phase == "VAPOR" and i.stage >= j),
            floor,
        )
        for j in range(1, count + 1)
    )

    def provider_k(temperature: float, pressure: float) -> Sequence[float]:
        return _k_values(provider, context, components, temperature, pressure)

    k_of = k_values if k_values is not None else provider_k
    k_stage = [tuple(k_of(tbar, spec.pressures[j])) for j in range(count)]
    liquid = [[0.0] * width for _ in range(count)]
    vapor = [[0.0] * width for _ in range(count)]
    for i in range(width):
        strip = [k_stage[j][i] * vapor_cmo[j] / liquid_cmo[j] for j in range(count)]
        rhs = [-sum(f.state.n[i] for f in inlets if f.stage == j + 1) for j in range(count)]
        column = thomas(
            [1.0] * count,
            [-(1.0 + strip[j]) for j in range(count)],
            [strip[j + 1] if j + 1 < count else 0.0 for j in range(count)],
            rhs,
        )
        for j in range(count):
            liquid[j][i] = column[j]
            vapor[j][i] = strip[j] * column[j]

    state = _initial_state(spec, provider, context, liquid, vapor, tbar)
    return KremserInitial(
        z=z,
        beta=beta,
        beta_clamped=beta_clamped,
        pbar=pbar,
        tbar=tbar,
        liquid_cmo=liquid_cmo,
        vapor_cmo=vapor_cmo,
        liquid=tuple(tuple(row) for row in liquid),
        vapor=tuple(tuple(row) for row in vapor),
        state=state,
    )


def _inflow_sum(spec: CascadeSpec, values: Mapping[str, float], stage: int, c: str) -> float:
    """The `mix` row's inflow, summed in the row's own order, so `mix` vanishes exactly."""
    unit, count = spec.unit_id, spec.stage_count
    above = flow_id(inlet_stream(unit, TOP), c) if stage == 1 else liquid_id(unit, stage - 1, c)
    below = (
        flow_id(inlet_stream(unit, BOTTOM), c) if stage == count else vapor_id(unit, stage + 1, c)
    )
    total = values[above] + values[below]
    for side in spec.sides:
        if side.stage == stage:
            total = total + values[flow_id(inlet_stream(unit, side.port), c)]
    return total


def _inlet_columns(spec: CascadeSpec) -> dict[str, float]:
    values: dict[str, float] = {}
    for inlet in spec.inlets():
        stream = inlet_stream(spec.unit_id, inlet.port)
        for c, a in zip(spec.components, inlet.state.n, strict=True):
            values[flow_id(stream, c)] = normalize_zero(float(a))
        values[temperature_id(stream)] = float(inlet.state.temperature)
        values[pressure_id(stream)] = float(inlet.state.pressure)
    return values


def _initial_state(
    spec: CascadeSpec,
    provider: PropertyProvider,
    context: EvaluationContext,
    liquid: Sequence[Sequence[float]],
    vapor: Sequence[Sequence[float]],
    tbar: float,
) -> dict[str, float]:
    """Spec §6.5's last step: totals as sums, `T_j = T̄`, `P_j = P_j*`, `m` from `mix`, `Q_j` from
    `energy_j`."""
    unit, components = spec.unit_id, spec.components
    values = _inlet_columns(spec)
    for j in range(spec.stage_count):
        stage = j + 1
        for i, c in enumerate(components):
            values[liquid_id(unit, stage, c)] = liquid[j][i]
            values[vapor_id(unit, stage, c)] = vapor[j][i]
        values[liquid_total_id(unit, stage)] = sum(liquid[j])
        values[vapor_total_id(unit, stage)] = sum(vapor[j])
        values[stage_temperature_id(unit, stage)] = tbar
        values[stage_pressure_id(unit, stage)] = float(spec.pressures[j])
        values[stage_duty_id(unit, stage)] = 0.0
    for stage in range(1, spec.stage_count + 1):
        for c in components:
            values[mixed_id(unit, stage, c)] = _inflow_sum(spec, values, stage, c)
    problem = declared_problem(declared_rows(spec, provider, context))
    residual = row_values(problem, values)
    for stage in range(1, spec.stage_count + 1):
        # energy_j at Q_j = 0 is `0 + Hdot_in - Hdot_out`; Q_j closes it.
        values[stage_duty_id(unit, stage)] = normalize_zero(-residual[energy_row_id(unit, stage)])
    return {name: values[name] for name in problem.variable_ids}


# -- spec §4.6: every inlet dormant --------------------------------------------------------------


@dataclass(frozen=True)
class DormantAnswer:
    """Spec §4.6's closed form: no Newton solve, so `newton_iterations` is `0` by construction.

    `residuals` are the rows of the all-`ZERO_FLOW` system at `state`: the declared rows less the
    dropped ones, with each stage's label row in place of its energy row. `swapped_energy` is the
    value of each swapped-out energy row there, which is what decides the outcome.
    """

    outcome: Literal["CONVERGED", "SPECIFICATION_CONFLICT"]
    cause: str | None
    signature: tuple[Regime, ...]
    state: Mapping[str, float]
    labels: tuple[str, ...]
    swapped_energy: tuple[float, ...]
    residuals: Mapping[str, float]
    newton_iterations: int = 0


def is_dormant(spec: CascadeSpec) -> bool:
    """ADR 0001 D3.1: every inlet flow exactly zero."""
    return all(_is_dormant(inlet.state) for inlet in spec.inlets())


def dormant_answer(
    spec: CascadeSpec, provider: PropertyProvider, context: EvaluationContext
) -> DormantAnswer:
    """Spec §4.6 on a validated specification whose every inlet is dormant.

    Every stage `ZERO_FLOW`, every flow `+0.0`, `T_j` by the label chain (`T_top` down the
    cascade), `P_j = P_j*`, `Q_j = Q_j*`. The outcome is derived from the swapped energy rows,
    not from the duties: `CONVERGED` when each is zero, else `SPECIFICATION_CONFLICT`,
    `zero_flow_conflict(<energy row>)` at the first stage where one is not.
    """
    unit, components = spec.unit_id, spec.components
    count = spec.stage_count
    if not is_dormant(spec):
        raise ValueError(f"{unit}: an inlet flows; spec §4.6 is for an all-dormant cascade")
    values = _inlet_columns(spec)
    labels = tuple(label_column(spec, stage) for stage in range(1, count + 1))
    for j in range(count):
        stage = j + 1
        for c in components:
            values[liquid_id(unit, stage, c)] = 0.0
            values[vapor_id(unit, stage, c)] = 0.0
        values[liquid_total_id(unit, stage)] = 0.0
        values[vapor_total_id(unit, stage)] = 0.0
        values[stage_temperature_id(unit, stage)] = values[labels[j]]
        values[stage_pressure_id(unit, stage)] = float(spec.pressures[j])
        values[stage_duty_id(unit, stage)] = normalize_zero(float(spec.duties[j]))
    for stage in range(1, count + 1):
        for c in components:
            values[mixed_id(unit, stage, c)] = _inflow_sum(spec, values, stage, c)

    problem = declared_problem(declared_rows(spec, provider, context))
    declared = row_values(problem, values)
    forms = [regime_form(spec, stage, "ZERO_FLOW") for stage in range(1, count + 1)]
    removed = {row for form in forms for row in (*form.dropped, form.swapped)}
    residuals = {name: value for name, value in declared.items() if name not in removed}
    for form in forms:
        assert form.label is not None
        row_name, temperature, label = form.label
        build = balance_row((temperature,), (label,))
        residuals[row_name] = float(build(values, {}, {}, _NO_ALGEBRA))
    swapped = tuple(declared[form.swapped] for form in forms)
    conflict = next((j for j, value in enumerate(swapped) if value != 0.0), None)
    state = {name: values[name] for name in problem.variable_ids}
    zero_flow: Regime = "ZERO_FLOW"
    signature = tuple(zero_flow for _ in range(count))
    if conflict is None:
        return DormantAnswer("CONVERGED", None, signature, state, labels, swapped, residuals)
    return DormantAnswer(
        "SPECIFICATION_CONFLICT",
        f"zero_flow_conflict({energy_row_id(unit, conflict + 1)})",
        signature,
        state,
        labels,
        swapped,
        residuals,
    )


class _NoAlgebra:
    """The label row is linear; an `Algebra` call from it would be a defect."""

    def exp(self, value: float) -> float:
        raise AssertionError("defect: a label row called exp")

    def log(self, value: float) -> float:
        raise AssertionError("defect: a label row called log")

    def sqrt(self, value: float) -> float:
        raise AssertionError("defect: a label row called sqrt")


_NO_ALGEBRA: Final = _NoAlgebra()

__all__ = [
    "BETA_BOUNDS",
    "BOTTOM",
    "CMO_FLOOR",
    "EQUATIONS",
    "INITIALIZER_ID",
    "INLET_PHASES",
    "MODEL_ID",
    "TOP",
    "CascadeFailure",
    "CascadeSpec",
    "DormantAnswer",
    "EnergyPrecheck",
    "InletState",
    "KremserInitial",
    "PlacedInlet",
    "RegimeForm",
    "SideFeed",
    "declared_problem",
    "declared_rows",
    "dormant_answer",
    "energy_precheck",
    "is_dormant",
    "kremser_initial",
    "regime_form",
    "thomas",
    "validate",
]
