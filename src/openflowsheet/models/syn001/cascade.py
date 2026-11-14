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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.canonical import normalize_zero
from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import pressure_id, temperature_id
from openflowsheet.models.lifted import Regime
from openflowsheet.models.lifted_tolerance import KIND_TOLERANCE
from openflowsheet.models.rows import balance_row
from openflowsheet.models.syn001 import (
    P_MAX,
    P_MIN,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    T_MAX,
    T_MIN,
)
from openflowsheet.models.syn001.cascade_failure import (
    CascadeFailure as CascadeFailure,
)
from openflowsheet.models.syn001.cascade_failure import (
    FailureOutcome as FailureOutcome,
)
from openflowsheet.models.syn001.cascade_init import BETA_BOUNDS as BETA_BOUNDS
from openflowsheet.models.syn001.cascade_init import CMO_FLOOR as CMO_FLOOR
from openflowsheet.models.syn001.cascade_init import INITIALIZER_ID as INITIALIZER_ID
from openflowsheet.models.syn001.cascade_init import KremserInitial as KremserInitial
from openflowsheet.models.syn001.cascade_init import KValues as KValues
from openflowsheet.models.syn001.cascade_init import _inflow_sum, _inlet_columns
from openflowsheet.models.syn001.cascade_init import _k_values as _k_values
from openflowsheet.models.syn001.cascade_init import kremser_initial as kremser_initial
from openflowsheet.models.syn001.cascade_init import thomas as thomas
from openflowsheet.models.syn001.cascade_rows import _token as _token
from openflowsheet.models.syn001.cascade_rows import declared_problem as declared_problem
from openflowsheet.models.syn001.cascade_rows import declared_rows as declared_rows
from openflowsheet.models.syn001.cascade_spec import _TOKEN as _TOKEN
from openflowsheet.models.syn001.cascade_spec import BOTTOM as BOTTOM
from openflowsheet.models.syn001.cascade_spec import EQUATIONS as EQUATIONS
from openflowsheet.models.syn001.cascade_spec import MODEL_ID as MODEL_ID
from openflowsheet.models.syn001.cascade_spec import SPECIFICATION as SPECIFICATION
from openflowsheet.models.syn001.cascade_spec import TOP as TOP
from openflowsheet.models.syn001.cascade_spec import CascadeSpec as CascadeSpec
from openflowsheet.models.syn001.cascade_spec import InletState as InletState
from openflowsheet.models.syn001.cascade_spec import PlacedInlet as PlacedInlet
from openflowsheet.models.syn001.cascade_spec import SideFeed as SideFeed
from openflowsheet.models.syn001.cascade_spec import _parameter as _parameter
from openflowsheet.models.syn001.cascade_spec import _phase as _phase
from openflowsheet.models.syn001.cascade_spec import energy_row_id as energy_row_id
from openflowsheet.models.syn001.cascade_spec import inlet_row_id as inlet_row_id
from openflowsheet.models.syn001.cascade_spec import inlet_stream as inlet_stream
from openflowsheet.models.syn001.cascade_spec import label_column as label_column
from openflowsheet.models.syn001.cascade_spec import label_row_id as label_row_id
from openflowsheet.models.syn001.cascade_spec import liquid_id as liquid_id
from openflowsheet.models.syn001.cascade_spec import liquid_total_id as liquid_total_id
from openflowsheet.models.syn001.cascade_spec import mixed_id as mixed_id
from openflowsheet.models.syn001.cascade_spec import stage_duty_id as stage_duty_id
from openflowsheet.models.syn001.cascade_spec import stage_prefix as stage_prefix
from openflowsheet.models.syn001.cascade_spec import stage_pressure_id as stage_pressure_id
from openflowsheet.models.syn001.cascade_spec import stage_row_id as stage_row_id
from openflowsheet.models.syn001.cascade_spec import stage_temperature_id as stage_temperature_id
from openflowsheet.models.syn001.cascade_spec import vapor_id as vapor_id
from openflowsheet.models.syn001.cascade_spec import vapor_total_id as vapor_total_id
from openflowsheet.models.syn001.saturation_band import band_temperature as band_temperature
from openflowsheet.models.syn001.tp_state import enthalpy_flow, single_phase_admissible
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

#: The declared inlet phases S01 accepts; any other is `unsupported(two_phase_inlet:<port>)`.
INLET_PHASES: Final[tuple[Phase, ...]] = ("LIQUID", "VAPOR")


# -- spec §5: validation -------------------------------------------------------------------------


def _invalid(code: str, message: str) -> CascadeFailure:
    return CascadeFailure("INVALID_SPECIFICATION", f"invalid_spec({code})", message)


def property_method_refusal(unit: str, provider: PropertyProvider) -> CascadeFailure | None:
    """S03 §9 S11, before R1 and before any provider evaluation: `None` exactly when `provider`
    declares SYN-001's identity, else `unsupported(column_property_method:<provider_id>)`.

    It reads `describe()` (metadata, not an evaluation). The check is identity, not capability:
    the cascade evaluates K as a function of (T, P) alone (`LnKBlock`), so a provider with
    composition-dependent K would declare what SYN-001 declares and be answered silently wrong.
    A wrapper that delegates `describe()` to a SYN-001 provider (the property cache) passes.
    """
    described = provider.describe()
    if (
        described.provider_id == PROVIDER_ID
        and described.reference_convention == REFERENCE_CONVENTION
    ):
        return None
    return CascadeFailure(
        "CAPABILITY_UNAVAILABLE",
        f"unsupported(column_property_method:{described.provider_id})",
        f"{unit}: provider {described.provider_id!r} (reference convention "
        f"{described.reference_convention!r}) is outside the supported scope; a cascade or "
        f"column supports SYN-001 only (provider_id {PROVIDER_ID!r}, reference_convention "
        f"{REFERENCE_CONVENTION!r}), whose K is composition-independent; the supported nonideal "
        "scope is empty (S03 §9)",
    )


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

    S03 §9 S11 precedes R1: a provider other than SYN-001 is refused by identity before anything
    else is read or evaluated.
    """
    unit, components = spec.unit_id, spec.components
    refused = property_method_refusal(unit, provider)
    if refused is not None:
        return refused
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
    # R5: R-007 admissibility (spec §17.3, R-512), the inlet at its own `(n, T, P)` in its
    # declared phase.
    for inlet in inlets:
        state = inlet.state
        if _is_dormant(state):
            continue
        phase: Phase = "LIQUID" if state.phase == "LIQUID" else "VAPOR"
        admissible, _, error, status, message = single_phase_admissible(
            provider,
            StreamState(n=state.n, temperature=state.temperature, pressure=state.pressure),
            phase,
            components,
            context,
        )
        if not admissible:
            detail = f"equivalent temperature error {error!r} K" if status == "ok" else message
            return CascadeFailure(
                "INVALID_SPECIFICATION",
                f"inadmissible_inlet({inlet.port}, {state.phase})",
                f"{unit}: inlet {inlet.port} is not an admissible {state.phase} ({detail})",
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
    not from the duties: `CONVERGED` when each is within `KIND_TOLERANCE["heat_rate"]` (R-518),
    else `SPECIFICATION_CONFLICT`, `zero_flow_conflict(<energy row>)` at the first stage where
    one is not.
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
    # A swapped energy row holds within its kind tolerance, the rule `solve_region` applies to the
    # same row (spec §17.9, R-518; T05b §7.8 (iv) 2).
    tolerance = KIND_TOLERANCE["heat_rate"]
    conflict = next((j for j, value in enumerate(swapped) if not abs(value) <= tolerance), None)
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
