"""The residence-time mass mapping `T04-residence-time-v1`. T04 §6, §7.2; ADR 0010 D4.

PTC needs a mass matrix `M = ∂(holdup)/∂x`, and a mass matrix is a claim about physics: which
rows accumulate, and what. ADR 0008 D3–D5 already say which: the rows a manifest declares
`holdup_balance`, and no others. This module says *what* they hold, for the two SYN-001 vessels,
as T04 §6.2 derives it — a well-mixed vessel whose every phase inventory drains at a rate
proportional to itself with a common residence time θ, at its outlet state:

    N_i = θ Σ_π n_i^π,          H = θ Σ_π Σ_i n_i^π h_i^π(T_π, P_π),

with `n_i^π` the phase-resolved outflow — the flash's vapour and liquid products, the heater's
lifted outlet split — and the energy holdup the *enthalpy* content (`U + PV` at the pinned
pressure; T04 §6.2, finding F2). Every enthalpy and enthalpy derivative is the provider's own, so a
provider with another reference state shifts `M` exactly as it shifts the energy rows (A16).

**The pattern comes only from the manifests.** A registry entry names a model's manifest equation
and the holdup it maps it to; a region's rows are matched to entries through the `origin` every
row carries (`model_id#equation_id`), and the result is validated before the region's first
attempt (T04 §7.2): every `holdup_balance` row mapped (V1), no entry on any other row (V2), θ > 0
(V3), and each entry's holdup dimension the manifest's (V4). The first failure refuses the solve
`PTC_MAPPING_INVALID`. A row nobody mapped is a refusal, never `M = 0`.

**A pseudo-holdup, not a physical one (ADR 0008 Amendment 1, U–H.5).** The vessel above is the
pseudo-transient's: its contents are proportional to its outflow and its volume moves with the
state at pinned pressure, which is why it accumulates `H = U + PV`. A physical vessel's energy
content is the manifests' `U`; the SYN-001 vessels are rigid, so `U` is also what their dynamic
energy rows accumulate (U–H.2). Nothing here is a physical mass matrix, and a physical-time
integrator never uses this module. `tests/test_adr_0008_transient_readiness.py` (U2) pins the
modules that import it directly: a tripwire, not a proof.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

import numpy as np
import scipy.sparse as sp

from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import DeclaredEquation, Dimension, Wiring, flow_id
from openflowsheet.models import pressure_id as _pressure_id
from openflowsheet.models import temperature_id as _temperature_id
from openflowsheet.models.syn001 import ENERGY, MOLE
from openflowsheet.numerics.ptc import MassUnavailableError
from openflowsheet.orchestrator.budget import BudgetExhaustedError
from openflowsheet.thermo import Phase, PropertyProvider, PropertyRequest, StreamState

__all__ = [
    "MASS_POLICY",
    "HoldupRule",
    "MappingRefusal",
    "MassMapping",
    "ModelMassRule",
    "PhaseOutflow",
    "RegionMass",
    "declared_phases",
    "residence_time",
    "resolve_mass",
    "syn001_residence_time",
]

#: `SolvePolicy.globalization.ptc.mass_policy` (ADR 0010 D1).
MASS_POLICY: Final = "T04-residence-time-v1"

MappingCheck = Literal["missing", "not_holdup_balance", "residence_time", "dimension"]
HoldupQuantity = Literal["component_moles", "enthalpy_content"]


@dataclass(frozen=True)
class PhaseOutflow:
    """One phase-resolved outflow of a vessel: its component amounts and the state they leave at."""

    phase: Phase
    flows: tuple[str, ...]
    temperature: str
    pressure: str


@dataclass(frozen=True)
class HoldupRule:
    """What one manifest equation accumulates under this mapping, and in which dimension."""

    quantity: HoldupQuantity
    dimension: Dimension


@dataclass(frozen=True)
class ModelMassRule:
    """The registered entries for one model id (T04 §6.3): the manifest equations it maps, and how
    a unit instance's phase-resolved outflows are read from its wiring."""

    model_id: str
    holdups: Mapping[str, HoldupRule]
    #: `(wiring, components, declared phase)`: the declared phase is the instance's
    #: (`MassMapping.phases`) for a vessel whose outlet is single-phase by declaration, `None` for
    #: one whose phases its lifted split or its products resolve.
    outflows: Callable[[Wiring, Sequence[str], Phase | None], tuple[PhaseOutflow, ...]]
    #: The model's declared equations, by id — the manifest V4 compares a rule's dimension with.
    declared: Mapping[str, DeclaredEquation]


@dataclass(frozen=True)
class MassMapping:
    """A mass policy's registered entries, by model id, with the flowsheet wiring they read."""

    policy_id: str
    rules: Mapping[str, ModelMassRule]
    wiring: Mapping[str, Wiring]
    components: tuple[str, ...]
    #: Unit id -> its outlet's declared phase, for the units whose rule reads one (the kinetic
    #: CSTR, T08 build-first §A3.1). Empty on SYN-001's flowsheet and every T05 one.
    phases: Mapping[str, Phase] = field(default_factory=dict)


@dataclass(frozen=True)
class MappingRefusal:
    """The first failing check of T04 §7.2, in its R0 grammar."""

    row: str
    check: MappingCheck

    @property
    def message(self) -> str:
        return f"ptc_mapping_invalid({self.row}, {self.check})"


@dataclass(frozen=True)
class _Entry:
    row: str
    unit: str
    quantity: HoldupQuantity
    #: The component of a mole row (its row id's suffix); `None` for the energy row.
    component: int | None
    outflows: tuple[PhaseOutflow, ...]


@dataclass(frozen=True)
class RegionMass:
    """A validated mapping for one region: the mapped rows and how to evaluate `M` on them."""

    entries: tuple[_Entry, ...]
    residence_time: float
    components: tuple[str, ...]

    def entries_at(
        self,
        state: Mapping[str, float],
        provider: PropertyProvider,
        context: EvaluationContext,
    ) -> dict[tuple[str, str], float]:
        """`M_row,col = ∂(holdup_row)/∂x_col` at a full state, unscaled, by id (T04 §6.3).

        Raises `MassUnavailableError` when the provider will not give an enthalpy or refuses the
        call for the property budget: the iterate `M` is wanted at was already accepted, so that is
        a defect or a spent budget, never a reason to take `M = 0`."""
        theta = self.residence_time
        enthalpies: dict[PhaseOutflow, tuple[list[float], list[float], list[float]]] = {}
        for entry in self.entries:
            if entry.quantity != "enthalpy_content":
                continue
            for outflow in entry.outflows:
                if outflow not in enthalpies:
                    enthalpies[outflow] = _enthalpies(
                        outflow, self.components, state, provider, context
                    )
        values: dict[tuple[str, str], float] = {}

        def add(row: str, column: str, value: float) -> None:
            values[(row, column)] = values.get((row, column), 0.0) + value

        for entry in self.entries:
            for outflow in entry.outflows:
                if entry.quantity == "component_moles":
                    assert entry.component is not None
                    add(entry.row, outflow.flows[entry.component], theta)
                    continue
                h, dh_dt, dh_dp = enthalpies[outflow]
                amounts = [state[name] for name in outflow.flows]
                for name, value in zip(outflow.flows, h, strict=True):
                    add(entry.row, name, theta * value)
                add(
                    entry.row,
                    outflow.temperature,
                    theta * sum(n * d for n, d in zip(amounts, dh_dt, strict=True)),
                )
                add(
                    entry.row,
                    outflow.pressure,
                    theta * sum(n * d for n, d in zip(amounts, dh_dp, strict=True)),
                )
        return values

    def matrix(
        self,
        state: Mapping[str, float],
        rows: Sequence[str],
        columns: Sequence[str],
        provider: PropertyProvider,
        context: EvaluationContext,
    ) -> sp.csc_matrix:
        """`M` restricted by id to an attempt's rows and free columns. A pinned column drops out
        with the column (T04 §6.3); a row outside the mapping is a zero row."""
        at_row = {name: index for index, name in enumerate(rows)}
        at_column = {name: index for index, name in enumerate(columns)}
        data: list[float] = []
        row_index: list[int] = []
        column_index: list[int] = []
        for (row, column), value in self.entries_at(state, provider, context).items():
            if row in at_row and column in at_column:
                data.append(value)
                row_index.append(at_row[row])
                column_index.append(at_column[column])
        return sp.csc_matrix(
            sp.coo_matrix(
                (np.asarray(data, dtype=np.float64), (row_index, column_index)),
                shape=(len(rows), len(columns)),
            )
        )


def _enthalpies(
    outflow: PhaseOutflow,
    components: Sequence[str],
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
) -> tuple[list[float], list[float], list[float]]:
    """The provider's `h_i^π` and its `T` and `P` derivatives at the outflow's state."""
    stream = StreamState(
        n=tuple(float(state[name]) for name in outflow.flows),
        temperature=float(state[outflow.temperature]),
        pressure=float(state[outflow.pressure]),
    )
    try:
        result = provider.evaluate_phase(
            PropertyRequest(
                state=stream, phase=outflow.phase, properties=("h",), derivatives=("T", "P")
            ),
            context,
        )
    except BudgetExhaustedError as exhausted:
        raise MassUnavailableError(str(exhausted)) from exhausted
    if result.status != "ok":
        raise MassUnavailableError(
            f"the provider gave no {outflow.phase} enthalpy at {outflow.temperature}: "
            f"{result.status}: {result.message}"
        )
    keys = [f"h_{component}" for component in components]
    missing = [key for key in keys if key not in result.values or key not in result.derivatives]
    if missing:
        raise MassUnavailableError(f"the provider returned no {missing} with T and P derivatives")
    h = [float(result.values[key]) for key in keys]
    dh_dt = [float(result.derivatives[key]["T"]) for key in keys]
    dh_dp = [float(result.derivatives[key]["P"]) for key in keys]
    return h, dh_dt, dh_dp


def resolve_mass(
    mapping: MassMapping | None,
    *,
    spec: ProblemSpec,
    rows: Sequence[str],
    residence_time: float,
) -> RegionMass | MappingRefusal:
    """T04 §7.2: the mapping for a region's rows, validated, or the first failing check.

    Each row is matched to a registry entry through its `origin` (`model_id#equation_id`) and its
    unit (the row id's prefix). The checks run in the specification's order — V1 every
    `holdup_balance` row (or row of unknown accumulation, ADR 0008 D3.6) is mapped; V2 no entry
    lies on another row; V3 θ > 0; V4 each entry's holdup dimension is its manifest's — over the
    rows in region order. `mapping = None` maps nothing, so the first holdup row is `missing`."""
    accumulation = spec.row_accumulation
    origins = {equation.equation_id: equation.origin for equation in spec.equations}
    components = mapping.components if mapping is not None else ()
    matched: list[tuple[str, ModelMassRule, str, HoldupRule]] = []
    unmatched: list[str] = []
    for row in rows:
        model_id, _, equation_id = origins.get(row, "").partition("#")
        rule = mapping.rules.get(model_id) if mapping is not None else None
        holdup = rule.holdups.get(equation_id) if rule is not None else None
        if rule is None or holdup is None:
            unmatched.append(row)
        else:
            matched.append((row, rule, equation_id, holdup))
    mapped = {row for row, *_ in matched}

    for row in rows:  # V1
        if accumulation[row] in ("holdup_balance", "absent") and row not in mapped:
            return MappingRefusal(row, "missing")
    for row, *_ in matched:  # V2
        if accumulation[row] != "holdup_balance":
            return MappingRefusal(row, "not_holdup_balance")
    if matched and not residence_time > 0.0:  # V3
        return MappingRefusal(matched[0][0], "residence_time")
    for row, rule, equation_id, holdup in matched:  # V4
        declared = rule.declared.get(equation_id)
        manifest = declared.accumulation.holdup if declared is not None else None
        if manifest is None or tuple(manifest.dimension) != tuple(holdup.dimension):
            return MappingRefusal(row, "dimension")

    assert mapping is not None or not matched
    entries: list[_Entry] = []
    for row, rule, _, holdup in matched:
        unit = row.split(":", 1)[0]
        wiring = mapping.wiring[unit] if mapping is not None else None
        if wiring is None:
            raise ValueError(f"the mapping has no wiring for unit {unit}")
        component = None
        if holdup.quantity == "component_moles":
            suffix = row.rsplit(":", 1)[-1]
            component = components.index(suffix)
        phase = mapping.phases.get(unit) if mapping is not None else None
        entries.append(
            _Entry(row, unit, holdup.quantity, component, rule.outflows(wiring, components, phase))
        )
    return RegionMass(tuple(entries), residence_time, components)


# ------------------------------------------------------------------ the registered entries (§6.3)


def _heater_outflows(
    wiring: Wiring, components: Sequence[str], phase: Phase | None = None
) -> tuple[PhaseOutflow, ...]:
    """The heater's outlet, phase-resolved by its lifted split (T04 §6.2: the heater's mole
    holdup on the phase amounts, not on the stream total — reference invariance, R-032). It has
    no declared phase; `phase` is not read."""
    from openflowsheet.models.syn001.tp_state import liquid_flow_id, vapor_flow_id

    stream = wiring.one("outlet")
    temperature, pressure = _temperature_id(stream), _pressure_id(stream)
    return (
        PhaseOutflow(
            "VAPOR", tuple(vapor_flow_id(stream, c) for c in components), temperature, pressure
        ),
        PhaseOutflow(
            "LIQUID", tuple(liquid_flow_id(stream, c) for c in components), temperature, pressure
        ),
    )


def _flash_outflows(
    wiring: Wiring, components: Sequence[str], phase: Phase | None = None
) -> tuple[PhaseOutflow, ...]:
    """The flash's two products, each at its own outlet state. `phase` is not read."""
    vapor, liquid = wiring.one("vapor"), wiring.one("liquid")
    return (
        PhaseOutflow(
            "VAPOR",
            tuple(flow_id(vapor, c) for c in components),
            _temperature_id(vapor),
            _pressure_id(vapor),
        ),
        PhaseOutflow(
            "LIQUID",
            tuple(flow_id(liquid, c) for c in components),
            _temperature_id(liquid),
            _pressure_id(liquid),
        ),
    )


def _declared_outflow(
    wiring: Wiring, components: Sequence[str], phase: Phase | None
) -> tuple[PhaseOutflow, ...]:
    """A single-phase vessel's one outflow, its outlet stream in the instance's declared phase
    (T08 build-first §A3.1: the kinetic CSTR). A missing phase is a defect: the mapping was built
    without the instance's configuration, and guessing a phase would guess `M`."""
    if phase is None:
        raise ValueError("a declared-phase outflow needs the instance's declared phase")
    stream = wiring.one("outlet")
    return (
        PhaseOutflow(
            phase,
            tuple(flow_id(stream, c) for c in components),
            _temperature_id(stream),
            _pressure_id(stream),
        ),
    )


def _declared(equations: Sequence[DeclaredEquation]) -> dict[str, DeclaredEquation]:
    return {equation.equation_id: equation for equation in equations}


def _registered_rules() -> dict[str, ModelMassRule]:
    from openflowsheet.models.syn001 import flash, heater, kinetic_cstr

    moles, content = (
        HoldupRule("component_moles", MOLE),
        HoldupRule("enthalpy_content", ENERGY),
    )
    return {
        heater.MODEL_ID: ModelMassRule(
            heater.MODEL_ID,
            {"HEAT-mole": moles, "HEAT-duty": content},
            _heater_outflows,
            _declared(heater.EQUATIONS),
        ),
        flash.MODEL_ID: ModelMassRule(
            flash.MODEL_ID,
            {"FLASH-mole": moles, "FLASH-duty": content},
            _flash_outflows,
            _declared(flash.EQUATIONS),
        ),
        # T08 build-first §A3.1 (ADR 0023): one outflow, the outlet in its declared phase.
        kinetic_cstr.MODEL_ID: ModelMassRule(
            kinetic_cstr.MODEL_ID,
            {"CSTR-mole": moles, "CSTR-duty": content},
            _declared_outflow,
            _declared(kinetic_cstr.EQUATIONS),
        ),
    }


def syn001_residence_time(components: Sequence[str]) -> MassMapping:
    """`T04-residence-time-v1` on the SYN-001 flowsheet: the heater's and the flash's entries."""
    from openflowsheet.models.syn001.flowsheet import WIRING

    return MassMapping(MASS_POLICY, _registered_rules(), WIRING, tuple(components))


def residence_time(
    wiring: Mapping[str, Wiring],
    components: Sequence[str],
    phases: Mapping[str, Phase] | None = None,
) -> MassMapping:
    """`T04-residence-time-v1` over a revision-built flowsheet's wiring (T05 design note §5).

    The registered rules are T04's, the K02 heater's and flash's, and T08's kinetic CSTR's
    (build-first §A3.1), whose outlet phase is its instance's: `phases`, by unit id
    (`declared_phases`). T05 registers no rule (spec §12.4), so a T05 model's `holdup_balance`
    row is refused by `resolve_mass`'s V1 before any attempt, `ptc_mapping_invalid(<row>,
    missing)`. Over SYN-001's own wiring this is `syn001_residence_time`, which stays the legacy
    path's.
    """
    return MassMapping(
        MASS_POLICY, _registered_rules(), wiring, tuple(components), dict(phases or {})
    )


def declared_phases(units: Sequence[object]) -> dict[str, Phase]:
    """Unit id -> declared outlet phase, for every unit whose registered rule reads one (the
    kinetic CSTR's `phase`, T08 build-first §A3.1)."""
    from openflowsheet.models.syn001.kinetic_cstr import KineticCSTR

    return {unit.unit_id: unit.phase for unit in units if isinstance(unit, KineticCSTR)}
