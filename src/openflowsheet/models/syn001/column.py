"""`syn001.column` — a MESH column on SYN-001: S01's cascade with a condenser and a reboiler.

Authority `docs/derivations/S02-spec.md`. Stages `j = 1..N` top to bottom; `N` counts the
condenser (stage 1) and the reboiler (stage N) when present (§1). A partial condenser and a
partial reboiler are S01 equilibrium stages with an absent inlet; a total condenser is not an
equilibrium stage but the saturated-liquid block of §2.2. Every equilibrium stage carries S01's
rows (spec §2 of S01) under S01's ids; the condenser's and the reboiler's slot row is the column
specification of §2.1 in place of `Q_j − Q_j*`.

**The unit layer only** (S02 spec §12 WO-1), in four modules (S19 B2): `column_spec` holds the
specification object, the declarations and the column's ids, `column_validation` its §5
refusals and `column_rows` the §2 declared rows; this module holds the per-stage regime forms
with §2.3's label and the §6 analytic initializer `s02-profile-cmo-v1`, and re-exports the
other three's names. The pre-solve, the target and acceptance are WO-2's.

Column ids beyond S01's (build decision, `docs/S02_DECISIONS.md`): the total condenser's are
`<U>.stage.1.{r,d}.<c>`, `<U>.stage.1.{phi,D}` and S01's `<U>.stage.1.{T,P,Q}` for `T_c`, `P_c`,
`Q_c`. Row ids are S01's, plus `<U>:stage:<j>:spec:<kind>` (§2.1) and, at a total condenser,
`<U>:stage:1:{bal,split}:<c>` and `<U>:stage:1:{Ddef,bubble,energy,P}`.

**S06** (`docs/derivations/S06-spec.md`, WO-1) adds the inverse end specifications `purity`,
`recovery` and `temperature` (§1): their refusals I1–I6 after S10 (§5), their slot rows of the
form `variable − parameter` and, per `purity` end, the column `u = F x_c`
(`<U>.stage.<j>.purity_flow`) with its definition row `<U>:stage:<j>:spec:purity_definition`
(§2). Build decisions: `docs/C11_DECISIONS.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from openflowsheet.canonical import normalize_zero
from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.lifted import Regime
from openflowsheet.models.syn001.cascade import (
    CMO_FLOOR,
    CascadeFailure,
    _k_values,
    declared_problem,
    energy_row_id,
    inlet_stream,
    label_row_id,
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_duty_id,
    stage_pressure_id,
    stage_row_id,
    stage_temperature_id,
    thomas,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.column_rows import _inflow as _inflow
from openflowsheet.models.syn001.column_rows import declared_rows as declared_rows
from openflowsheet.models.syn001.column_spec import COLUMN_EQUATIONS as COLUMN_EQUATIONS
from openflowsheet.models.syn001.column_spec import COMPONENT_KINDS as COMPONENT_KINDS
from openflowsheet.models.syn001.column_spec import CONDENSER as CONDENSER
from openflowsheet.models.syn001.column_spec import CONDENSER_KINDS as CONDENSER_KINDS
from openflowsheet.models.syn001.column_spec import END_KINDS as END_KINDS
from openflowsheet.models.syn001.column_spec import EQUATIONS as EQUATIONS
from openflowsheet.models.syn001.column_spec import F_REF as F_REF
from openflowsheet.models.syn001.column_spec import FLOWSHEET_EQUATIONS as FLOWSHEET_EQUATIONS
from openflowsheet.models.syn001.column_spec import GAMMA_PHI_KINDS as GAMMA_PHI_KINDS
from openflowsheet.models.syn001.column_spec import INVERSE_EQUATIONS as INVERSE_EQUATIONS
from openflowsheet.models.syn001.column_spec import INVERSE_KINDS as INVERSE_KINDS
from openflowsheet.models.syn001.column_spec import MODEL_ID as MODEL_ID
from openflowsheet.models.syn001.column_spec import NOT_OFFERED as NOT_OFFERED
from openflowsheet.models.syn001.column_spec import RATIO_KINDS as RATIO_KINDS
from openflowsheet.models.syn001.column_spec import REBOILER as REBOILER
from openflowsheet.models.syn001.column_spec import REBOILER_KINDS as REBOILER_KINDS
from openflowsheet.models.syn001.column_spec import S06_SPECIFICATION as S06_SPECIFICATION
from openflowsheet.models.syn001.column_spec import S11_SPECIFICATION as S11_SPECIFICATION
from openflowsheet.models.syn001.column_spec import SPECIFICATION as SPECIFICATION
from openflowsheet.models.syn001.column_spec import ColumnSpec as ColumnSpec
from openflowsheet.models.syn001.column_spec import EndSpecification as EndSpecification
from openflowsheet.models.syn001.column_spec import FlowsheetLinks as FlowsheetLinks
from openflowsheet.models.syn001.column_spec import distillate_id as distillate_id
from openflowsheet.models.syn001.column_spec import distillate_total_id as distillate_total_id
from openflowsheet.models.syn001.column_spec import label_source as label_source
from openflowsheet.models.syn001.column_spec import product_flow_id as product_flow_id
from openflowsheet.models.syn001.column_spec import product_link_row_id as product_link_row_id
from openflowsheet.models.syn001.column_spec import product_total_id as product_total_id
from openflowsheet.models.syn001.column_spec import purity_flow_id as purity_flow_id
from openflowsheet.models.syn001.column_spec import (
    purity_reference_parameter as purity_reference_parameter,
)
from openflowsheet.models.syn001.column_spec import ratio_parameter as ratio_parameter
from openflowsheet.models.syn001.column_spec import recovery_flow_id as recovery_flow_id
from openflowsheet.models.syn001.column_spec import (
    recovery_reference_parameter as recovery_reference_parameter,
)
from openflowsheet.models.syn001.column_spec import reflux_fraction_id as reflux_fraction_id
from openflowsheet.models.syn001.column_spec import reflux_id as reflux_id
from openflowsheet.models.syn001.column_spec import slot_column as slot_column
from openflowsheet.models.syn001.column_spec import slot_row_id as slot_row_id
from openflowsheet.models.syn001.column_validation import (
    MULTIPLE_STEADY_STATES_WARNING as MULTIPLE_STEADY_STATES_WARNING,
)
from openflowsheet.models.syn001.column_validation import column_warnings as column_warnings
from openflowsheet.models.syn001.column_validation import component_feeds as component_feeds
from openflowsheet.models.syn001.column_validation import energy_precheck as energy_precheck
from openflowsheet.models.syn001.column_validation import inverse_parameter as inverse_parameter
from openflowsheet.models.syn001.column_validation import purity_reference as purity_reference
from openflowsheet.models.syn001.column_validation import (
    saturation_temperature as saturation_temperature,
)
from openflowsheet.models.syn001.column_validation import specified_quantity as specified_quantity
from openflowsheet.models.syn001.column_validation import stage_band as stage_band
from openflowsheet.models.syn001.column_validation import validate as validate
from openflowsheet.models.syn001.gamma_phi_blocks import GammaPhiLnKBlock as GammaPhiLnKBlock
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.models.syn001.tp_state import single_phase_admissible as single_phase_admissible
from openflowsheet.thermo import PropertyProvider

#: Spec §6's registered initializer.
INITIALIZER_ID: Final = "s02-profile-cmo-v1"

#: Spec §6 step 2: the band fractions of the profile's ends, `T_a = T(β_a)` at `P_1*` and
#: `T_b = T(β_b)` at `P_N*`.
PROFILE_BETAS: Final = (0.1, 0.9)

#: Spec §6 step 4: the total condenser's initial reflux fraction `φ⁰`.
PHI_INITIAL: Final = 0.5


# -- regime forms (S01 §4.2 with §2.3's label) ---------------------------------------------------


@dataclass(frozen=True)
class ColumnRegimeForm:
    """S01's `RegimeForm` for an equilibrium stage of a column: what the stage pins and drops in
    one regime. In `ZERO_FLOW` the energy row is `swapped` for the label row `(row id, T_j,
    source)`, `source` the column id `label_source` names."""

    regime: Regime
    pinned: tuple[str, ...]
    dropped: tuple[str, ...]
    swapped: str = ""
    label: tuple[str, str, str] | None = None


def regime_form(spec: ColumnSpec, stage: int, regime: Regime) -> ColumnRegimeForm:
    """S01 §4.2 for equilibrium stage j of the column (the total condenser has no regime, §4.1)."""
    if stage not in spec.equilibrium_stages():
        raise ValueError(f"{spec.unit_id}: stage {stage} is not an equilibrium stage")
    unit, components = spec.unit_id, spec.components
    vapor = (*(vapor_id(unit, stage, c) for c in components), vapor_total_id(unit, stage))
    liquid = (*(liquid_id(unit, stage, c) for c in components), liquid_total_id(unit, stage))
    equilibrium = tuple(stage_row_id(unit, stage, "eq", c) for c in components)
    if regime == "TWO_PHASE":
        return ColumnRegimeForm(regime, (), ())
    if regime == "LIQUID":
        return ColumnRegimeForm(regime, vapor, (*equilibrium, stage_row_id(unit, stage, "Vdef")))
    if regime == "VAPOR":
        return ColumnRegimeForm(regime, liquid, (*equilibrium, stage_row_id(unit, stage, "Ldef")))
    return ColumnRegimeForm(
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
            label_source(spec, stage),
        ),
    )


# -- spec §6: the initializer --------------------------------------------------------------------


@dataclass(frozen=True)
class ProfileInitial:
    """`x_K` of §6 and the intermediate quantities A04 checks."""

    z: tuple[float, ...]
    t_a: float
    t_b: float
    #: `T_j⁰`, one per stage including the condenser.
    profile: tuple[float, ...]
    #: `L_j`, `V_j` of step 3 (CMO, floored), one per stage including the condenser.
    liquid_cmo: tuple[float, ...]
    vapor_cmo: tuple[float, ...]
    #: `l_ij`, `v_ij` by equilibrium stage j, in component order.
    liquid: Mapping[int, tuple[float, ...]]
    vapor: Mapping[int, tuple[float, ...]]
    #: Every declared column, in `declared_rows` order.
    state: Mapping[str, float]
    initializer: str = INITIALIZER_ID


def profile_initial(
    spec: ColumnSpec, provider: PropertyProvider, context: EvaluationContext
) -> ProfileInitial | CascadeFailure:
    """§6 `s02-profile-cmo-v1` on a validated specification with `F > 0` (an all-dormant
    column without ends is S01 §4.6's, and asking here is misuse)."""
    unit, components = spec.unit_id, spec.components
    count = spec.stage_count
    inlets = spec.inlets()
    width = len(components)
    totals = [sum(inlet.state.n[i] for inlet in inlets) for i in range(width)]
    big_f = sum(totals)
    if big_f == 0.0:
        raise ValueError(f"{unit}: every inlet is dormant; §6 needs F > 0")
    z = tuple(a / big_f for a in totals)

    ends: list[float] = []
    for beta, pressure in (
        (PROFILE_BETAS[0], spec.pressures[0]),
        (PROFILE_BETAS[1], spec.pressures[-1]),
    ):
        band = band_temperature(provider, totals, pressure, beta, context)
        if band.position != "inside" or band.temperature is None:
            return CascadeFailure(
                "INITIALIZATION_FAILED",
                f"initialization_failed({INITIALIZER_ID}, profile_outside_domain)",
                f"{unit}: T(beta = {beta!r}) at P = {pressure!r} Pa is {band.position} the domain",
            )
        ends.append(band.temperature)
    t_a, t_b = ends
    # N = 1 (a column with no ends) has the one-point profile T_a (build decision).
    profile = tuple(
        t_a + (t_b - t_a) * (j - 1) / (count - 1) if count > 1 else t_a for j in range(1, count + 1)
    )

    floor = CMO_FLOOR * big_f
    l_base = big_f if spec.condenser != "none" else 0.0
    v_base = big_f if spec.reboiler != "none" else 0.0
    liquid_cmo = tuple(
        max(
            l_base
            + sum(sum(i.state.n) for i in inlets if i.state.phase == "LIQUID" and i.stage <= j),
            floor,
        )
        for j in range(1, count + 1)
    )
    vapor_cmo = tuple(
        max(
            v_base
            + sum(sum(i.state.n) for i in inlets if i.state.phase == "VAPOR" and i.stage >= j),
            floor,
        )
        for j in range(1, count + 1)
    )

    stages = spec.equilibrium_stages()
    # K at the total feed composition on every stage (S10-C §4.9; SYN-001 ignores `liquid`).
    k_stage = {
        j: _k_values(provider, context, components, profile[j - 1], spec.pressures[j - 1], liquid=z)
        for j in stages
    }
    liquid = {j: [0.0] * width for j in stages}
    vapor = {j: [0.0] * width for j in stages}
    for i in range(width):
        strip = {j: k_stage[j][i] * vapor_cmo[j - 1] / liquid_cmo[j - 1] for j in stages}
        diag = [-(1.0 + strip[j]) for j in stages]
        if spec.total_condenser:
            # Stage 2 receives `r = φ⁰ v_2 = φ⁰ S_2 l_2` from above (§6 step 4).
            diag[0] += PHI_INITIAL * strip[stages[0]]
        solved = thomas(
            [1.0] * len(stages),
            diag,
            [strip[j + 1] if j < count else 0.0 for j in stages],
            [-sum(f.state.n[i] for f in inlets if f.stage == j) for j in stages],
        )
        for k, j in enumerate(stages):
            liquid[j][i] = solved[k]
            vapor[j][i] = strip[j] * solved[k]

    state = _initial_state(spec, provider, context, liquid, vapor, profile)
    return ProfileInitial(
        z=z,
        t_a=t_a,
        t_b=t_b,
        profile=profile,
        liquid_cmo=liquid_cmo,
        vapor_cmo=vapor_cmo,
        liquid={j: tuple(values) for j, values in liquid.items()},
        vapor={j: tuple(values) for j, values in vapor.items()},
        state=state,
    )


def _inlet_columns(spec: ColumnSpec) -> dict[str, float]:
    values: dict[str, float] = {}
    for inlet in spec.inlets():
        stream = inlet_stream(spec.unit_id, inlet.port)
        for c, a in zip(spec.components, inlet.state.n, strict=True):
            values[flow_id(stream, c)] = normalize_zero(float(a))
        values[temperature_id(stream)] = float(inlet.state.temperature)
        values[pressure_id(stream)] = float(inlet.state.pressure)
    return values


def _initial_state(
    spec: ColumnSpec,
    provider: PropertyProvider,
    context: EvaluationContext,
    liquid: Mapping[int, list[float]],
    vapor: Mapping[int, list[float]],
    profile: tuple[float, ...],
    *,
    phi: float = PHI_INITIAL,
) -> dict[str, float]:
    """§6 steps 5–6: `T_j = T_j⁰`, `P_j = P_j*`; at a total condenser `φ = φ⁰`, `T_c = T_1⁰`,
    `r = φ⁰ v_2`, `d = v_2 − r`, `D = Σ d`; totals as sums; per `purity` end (S06 §6)
    `u = F·n_c / P`; `m` from `mix`; every `Q` from its energy row. S02 §18.2 step 5 passes its
    own `T` as `profile` and its `φ`."""
    unit, components = spec.unit_id, spec.components
    values = _inlet_columns(spec)
    stages = spec.equilibrium_stages()
    for stage in stages:
        for i, c in enumerate(components):
            values[liquid_id(unit, stage, c)] = liquid[stage][i]
            values[vapor_id(unit, stage, c)] = vapor[stage][i]
        values[liquid_total_id(unit, stage)] = sum(liquid[stage])
        values[vapor_total_id(unit, stage)] = sum(vapor[stage])
        values[stage_temperature_id(unit, stage)] = profile[stage - 1]
        values[stage_pressure_id(unit, stage)] = float(spec.pressures[stage - 1])
        values[stage_duty_id(unit, stage)] = 0.0
    if spec.total_condenser:
        distillate: list[float] = []
        for i, c in enumerate(components):
            reflux = phi * vapor[2][i]
            values[reflux_id(unit, c)] = reflux
            values[distillate_id(unit, c)] = vapor[2][i] - reflux
            distillate.append(vapor[2][i] - reflux)
        values[reflux_fraction_id(unit)] = phi
        values[distillate_total_id(unit)] = sum(distillate)
        values[stage_temperature_id(unit, 1)] = profile[0]
        values[stage_pressure_id(unit, 1)] = float(spec.pressures[0])
        values[stage_duty_id(unit, 1)] = 0.0
    for end in spec.ends():
        given = spec.end_specification(end)
        if given is not None and given.kind == "purity":
            # S06 §6: `u⁰ = fl(F·n_c⁰ / P⁰)`, so the definition row holds to one rounding.
            assert given.component is not None, "validate first"
            flow = values[product_flow_id(spec, end, given.component)]
            values[purity_flow_id(unit, spec.end_stage(end))] = (
                purity_reference(spec) * flow / values[product_total_id(spec, end)]
            )
    for stage in stages:
        for c in components:
            total = 0.0
            for k, name in enumerate(_inflow(spec, stage, c)):
                total = values[name] if k == 0 else total + values[name]
            values[mixed_id(unit, stage, c)] = total
    problem = declared_problem(declared_rows(spec, provider, context))
    residual = row_values(problem, values)
    for stage in (1, *stages) if spec.total_condenser else stages:
        # energy_j at Q_j = 0 is `0 + Hdot_in - Hdot_out`; Q_j closes it.
        values[stage_duty_id(unit, stage)] = normalize_zero(-residual[energy_row_id(unit, stage)])
    return {name: values[name] for name in problem.variable_ids}


__all__ = [
    "COLUMN_EQUATIONS",
    "COMPONENT_KINDS",
    "CONDENSER",
    "CONDENSER_KINDS",
    "END_KINDS",
    "EQUATIONS",
    "GAMMA_PHI_KINDS",
    "INITIALIZER_ID",
    "INVERSE_EQUATIONS",
    "INVERSE_KINDS",
    "MODEL_ID",
    "MULTIPLE_STEADY_STATES_WARNING",
    "NOT_OFFERED",
    "PHI_INITIAL",
    "PROFILE_BETAS",
    "RATIO_KINDS",
    "REBOILER",
    "REBOILER_KINDS",
    "S06_SPECIFICATION",
    "ColumnRegimeForm",
    "ColumnSpec",
    "EndSpecification",
    "ProfileInitial",
    "column_warnings",
    "component_feeds",
    "declared_rows",
    "distillate_id",
    "distillate_total_id",
    "energy_precheck",
    "inverse_parameter",
    "label_source",
    "product_flow_id",
    "product_total_id",
    "profile_initial",
    "purity_flow_id",
    "purity_reference",
    "purity_reference_parameter",
    "ratio_parameter",
    "reflux_fraction_id",
    "reflux_id",
    "regime_form",
    "saturation_temperature",
    "slot_column",
    "slot_row_id",
    "specified_quantity",
    "stage_band",
    "validate",
]
