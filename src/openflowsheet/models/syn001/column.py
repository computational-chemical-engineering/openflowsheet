"""`syn001.column` — a MESH column on SYN-001: S01's cascade with a condenser and a reboiler.

Authority `docs/derivations/S02-spec.md`. Stages `j = 1..N` top to bottom; `N` counts the
condenser (stage 1) and the reboiler (stage N) when present (§1). A partial condenser and a
partial reboiler are S01 equilibrium stages with an absent inlet; a total condenser is not an
equilibrium stage but the saturated-liquid block of §2.2. Every equilibrium stage carries S01's
rows (spec §2 of S01) under S01's ids; the condenser's and the reboiler's slot row is the column
specification of §2.1 in place of `Q_j − Q_j*`.

**This module is the unit layer only** (S02 spec §12 WO-1): the specification object and its §5
refusals, the §2 declared rows, the per-stage regime forms with §2.3's label, and the §6
analytic initializer `s02-profile-cmo-v1`. The pre-solve, the target and acceptance are WO-2's.

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

import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

from openflowsheet.canonical import normalize_zero
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import EquationSpec, QuantityKind, RowBuilder
from openflowsheet.compiled import EvaluationContext, RowAccumulation
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    Holdup,
    flow_id,
    origin,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.rows import (
    balance_row,
    bubble_row,
    definition_row,
    energy_row,
    equilibrium_row,
    fraction_row,
    ratio_row,
    scaled_definition_row,
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
from openflowsheet.models.syn001.cascade import (
    BOTTOM,
    CMO_FLOOR,
    INLET_PHASES,
    TOP,
    CascadeFailure,
    EnergyPrecheck,
    InletState,
    PlacedInlet,
    SideFeed,
    _enthalpy_flow,
    _in_domain,
    _invalid,
    _is_dormant,
    _k_values,
    _parameter,
    _phase,
    _token,
    declared_problem,
    energy_row_id,
    inlet_row_id,
    inlet_stream,
    label_row_id,
    liquid_id,
    liquid_total_id,
    mixed_id,
    property_method_refusal,
    stage_duty_id,
    stage_prefix,
    stage_pressure_id,
    stage_row_id,
    stage_temperature_id,
    thomas,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade import EQUATIONS as CASCADE_EQUATIONS
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.models.syn001.tp_state import (
    enthalpy_block_id,
    lnk_block_id,
    single_phase_admissible,
)
from openflowsheet.orchestrator.region import Regime
from openflowsheet.thermo import Phase, PropertyProvider, StreamState
from openflowsheet.thermo import syn001 as syn001_thermo

MODEL_ID: Final = "syn001.column"

#: Where the equations are stated.
SPECIFICATION: Final = "docs/derivations/S02-spec.md §2"

#: Spec §6's registered initializer.
INITIALIZER_ID: Final = "s02-profile-cmo-v1"

#: Spec §6 step 2: the band fractions of the profile's ends, `T_a = T(β_a)` at `P_1*` and
#: `T_b = T(β_b)` at `P_N*`.
PROFILE_BETAS: Final = (0.1, 0.9)

#: Spec §6 step 4: the total condenser's initial reflux fraction `φ⁰`.
PHI_INITIAL: Final = 0.5

CONDENSER_KINDS: Final[tuple[str, ...]] = ("none", "partial", "total")
REBOILER_KINDS: Final[tuple[str, ...]] = ("none", "partial")

CONDENSER: Final = "condenser"
REBOILER: Final = "reboiler"

#: S06 §1: the inverse kinds, each with one attribute: `component` for `purity` and `recovery`,
#: `stage` for `temperature`. Either end takes any of them.
INVERSE_KINDS: Final[tuple[str, ...]] = ("purity", "recovery", "temperature")

#: The kinds whose attribute is a component (S06 §1).
COMPONENT_KINDS: Final[tuple[str, ...]] = ("purity", "recovery")

#: Spec §2.1 with S06 §1: the specification kinds each end takes. Any other kind at that end is
#: `invalid_spec(specification:<end>)` (§5 S2).
END_KINDS: Final[Mapping[str, tuple[str, ...]]] = {
    CONDENSER: ("reflux_ratio", "distillate_rate", "duty", *INVERSE_KINDS),
    REBOILER: ("boilup_ratio", "bottoms_rate", "duty", *INVERSE_KINDS),
}

#: S06 §1 (S02 §3's list narrowed): `unsupported(specification:<kind>)` (§5 S2). `mole_fraction`
#: is not an alias of `purity` (one id per row). The names are a build decision
#: (`docs/S02_DECISIONS.md`).
NOT_OFFERED: Final[tuple[str, ...]] = (
    "mole_fraction",
    "reflux_rate",
    "boilup_rate",
    "distillate_to_feed_ratio",
)

#: Where S06's rows are stated.
S06_SPECIFICATION: Final = "docs/derivations/S06-spec.md §2"

#: The ratio specifications (§2.1, "ratio" form); every other kind is `variable − parameter`.
RATIO_KINDS: Final[tuple[str, ...]] = ("reflux_ratio", "boilup_ratio")


# -- declarations --------------------------------------------------------------------------------

#: S01's families, which every equilibrium stage carries unchanged, then S02's (§2).
COLUMN_EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="COL-reflux-ratio",
        statement=(
            "L_1 - RR* V_1 = 0 at a partial condenser; sum_i r_i - RR* D = 0 at a total condenser"
        ),
        dependencies=("stage.L", "stage.V", "condenser.r", "condenser.D", "parameters.RR"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-distillate-rate",
        statement="V_1 - D* = 0 at a partial condenser; D - D* = 0 at a total condenser",
        dependencies=("stage.V", "condenser.D", "parameters.D_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-boilup-ratio",
        statement="V_N - BR* L_N = 0 at a partial reboiler",
        dependencies=("stage.V", "stage.L", "parameters.BR"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-bottoms-rate",
        statement="L_N - B* = 0 at a partial reboiler",
        dependencies=("stage.L", "parameters.B_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-duty",
        statement="Q_j - Q_j* = 0 at the condenser (j = 1) or the reboiler (j = N)",
        dependencies=("stage.Q", "parameters.Q_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-tc-bal",
        statement="v_i,2 - r_i - d_i = 0 for every component i (total condenser)",
        dependencies=("stage.v", "condenser.r", "condenser.d"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i", quantity="component moles held in the condenser", dimension=MOLE
            ),
        ),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-tc-split",
        statement="r_i - phi v_i,2 = 0 for every component i (total condenser)",
        dependencies=("condenser.r", "condenser.phi", "stage.v"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-tc-Ddef",
        statement="D - sum_i d_i = 0 (total condenser)",
        dependencies=("condenser.D", "condenser.d"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-tc-bubble",
        statement="sum_i K_i(T_c, P_c) v_i,2 - V_2 = 0 (total condenser, saturated liquid)",
        dependencies=("stage.v", "stage.V", "condenser.T", "condenser.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-tc-energy",
        statement=(
            "Q_c + Hdot^V(v_2, T_2) - Hdot^L(r, T_c, P_c) - Hdot^L(d, T_c, P_c) = 0, Q_c positive "
            "into the condenser"
        ),
        dependencies=("condenser.Q", "stage.v", "condenser.r", "condenser.d", "condenser.T"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="U", quantity="internal energy of the condenser contents", dimension=ENERGY
            ),
        ),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-tc-P",
        statement="P_c - P_1* = 0 (total condenser)",
        dependencies=("condenser.P", "parameters.P_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
)

#: S06 §2: the inverse slot rows and the purity definition.
INVERSE_EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="COL-purity",
        statement="u - pi* = 0, pi* = x* F (the end's product purity of component c)",
        dependencies=("column.u", "parameters.pi"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=S06_SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-purity-definition",
        statement="F n_c - u P = 0, n_c and P the end's product flow of c and its total",
        dependencies=("product.n", "product.P", "column.u", "parameters.F"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        source=S06_SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-recovery",
        statement="n_c - nu* = 0, nu* = r* F_c (the end's product recovery of component c)",
        dependencies=("product.n", "parameters.nu"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=S06_SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-temperature",
        statement="T_s - T* = 0 (the temperature of stage s; T_c at a total condenser's s = 1)",
        dependencies=("stage.T", "parameters.T_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=S06_SPECIFICATION,
    ),
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    *CASCADE_EQUATIONS,
    *COLUMN_EQUATIONS,
    *INVERSE_EQUATIONS,
)

#: The declared family of each slot kind (§2.1).
_SLOT_FAMILY: Final[Mapping[str, str]] = {
    "reflux_ratio": "COL-reflux-ratio",
    "distillate_rate": "COL-distillate-rate",
    "boilup_ratio": "COL-boilup-ratio",
    "bottoms_rate": "COL-bottoms-rate",
    "duty": "COL-duty",
    "purity": "COL-purity",
    "recovery": "COL-recovery",
    "temperature": "COL-temperature",
}

#: S06 §2: each inverse slot row's kind.
_INVERSE_ROW_KIND: Final[Mapping[str, QuantityKind]] = {
    "purity": "molar_flow",
    "recovery": "molar_flow",
    "temperature": "temperature",
}


# -- the specification ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EndSpecification:
    """One column specification (§2.1, S06 §1): a kind of `END_KINDS` and its value (SI; ratios,
    purities and recoveries are dimensionless). `kind` is a plain string so an unsupported kind
    reaches `validate` and is refused there (§5 S2).

    The inverse kinds carry one attribute (S06 §1): `component` (a name of `spec.components`) for
    `purity` and `recovery`, `stage` (1..N) for `temperature`. A direct kind carries neither; a
    missing, wrong or extra attribute is refused by `validate` (S06 §5 I1)."""

    kind: str
    value: float
    component: str | None = None
    stage: int | None = None


@dataclass(frozen=True)
class ColumnSpec:
    """The S02 specification set (§1, §3): N, `P_j*`, the intermediate `Q_j*`, the end kinds and
    their specifications, and the present inlets.

    `duties` has one entry per stage, top to bottom; the entry is `None` exactly at a stage whose
    slot is a column specification (stage 1 with a condenser, stage N with a reboiler) and a duty
    in W, positive into the stage, everywhere else. `top` and `bottom` are `None` when absent
    (§2.3). Nothing is checked on construction; `validate` applies §5 and answers with a typed
    refusal.
    """

    unit_id: str
    stage_count: int
    #: `P_j*`, Pa, one per stage including the condenser, top to bottom.
    pressures: tuple[float, ...]
    duties: tuple[float | None, ...]
    condenser: str = "none"
    reboiler: str = "none"
    condenser_spec: EndSpecification | None = None
    reboiler_spec: EndSpecification | None = None
    top: InletState | None = None
    bottom: InletState | None = None
    sides: tuple[SideFeed, ...] = ()
    components: tuple[str, ...] = COMPONENTS

    def inlets(self) -> tuple[PlacedInlet, ...]:
        """The present inlets: `top`, `bottom`, then the side feeds in declaration order (S01's
        order, with absent ends left out)."""
        placed: list[PlacedInlet] = []
        if self.top is not None:
            placed.append(PlacedInlet(TOP, 1, self.top))
        if self.bottom is not None:
            placed.append(PlacedInlet(BOTTOM, self.stage_count, self.bottom))
        placed.extend(PlacedInlet(side.port, side.stage, side.state) for side in self.sides)
        return tuple(placed)

    @property
    def total_condenser(self) -> bool:
        return self.condenser == "total"

    def equilibrium_stages(self) -> tuple[int, ...]:
        """The S01 equilibrium stages: all N, or 2..N with a total condenser (§1)."""
        return tuple(range(2 if self.total_condenser else 1, self.stage_count + 1))

    def end_stage(self, end: str) -> int:
        return 1 if end == CONDENSER else self.stage_count

    def end_specification(self, end: str) -> EndSpecification | None:
        return self.condenser_spec if end == CONDENSER else self.reboiler_spec

    def end_kind(self, end: str) -> str:
        return self.condenser if end == CONDENSER else self.reboiler

    def ends(self) -> tuple[str, ...]:
        """The non-`none` ends, condenser first."""
        return tuple(end for end in (CONDENSER, REBOILER) if self.end_kind(end) != "none")

    def slot_stages(self) -> dict[int, str]:
        """Stage → end, for the stages whose slot row is a column specification."""
        return {self.end_stage(end): end for end in self.ends()}


# -- names ---------------------------------------------------------------------------------------


def reflux_id(unit: str, component: str) -> str:
    return f"{stage_prefix(unit, 1)}.r.{component}"


def distillate_id(unit: str, component: str) -> str:
    return f"{stage_prefix(unit, 1)}.d.{component}"


def reflux_fraction_id(unit: str) -> str:
    return f"{stage_prefix(unit, 1)}.phi"


def distillate_total_id(unit: str) -> str:
    return f"{stage_prefix(unit, 1)}.D"


def slot_row_id(unit: str, stage: int, kind: str) -> str:
    """`<U>:stage:<j>:spec:<kind>` (§2.1)."""
    return stage_row_id(unit, stage, "spec", kind)


def ratio_parameter(unit: str, stage: int, kind: str) -> str:
    """A ratio's pinned input, `<U>.stage.<j>.<kind>*`: it pins no column, so it is named after
    its stage and kind (build decision)."""
    return f"{stage_prefix(unit, stage)}.{kind}*"


def purity_flow_id(unit: str, stage: int) -> str:
    """S06 §2: the purity column `u = F x_c` of the end at `stage`, `<U>.stage.<j>.purity_flow`."""
    return f"{stage_prefix(unit, stage)}.purity_flow"


def purity_reference_parameter(unit: str, stage: int) -> str:
    """S06 §2: the pinned feed total `F` of the purity definition at `stage`,
    `<U>.stage.<j>.purity_reference*`."""
    return f"{stage_prefix(unit, stage)}.purity_reference*"


def product_flow_id(spec: ColumnSpec, end: str, component: str) -> str:
    """S06 §1: the end's product flow `n_c` of `component`: `v_1,c` (partial or `none`
    condenser), `d_c` (total condenser) or `l_N,c` (reboiler)."""
    unit = spec.unit_id
    if end == REBOILER:
        return liquid_id(unit, spec.stage_count, component)
    return distillate_id(unit, component) if spec.total_condenser else vapor_id(unit, 1, component)


def product_total_id(spec: ColumnSpec, end: str) -> str:
    """S06 §1: the end's product total `P`: `V_1`, `D` or `L_N`."""
    unit = spec.unit_id
    if end == REBOILER:
        return liquid_total_id(unit, spec.stage_count)
    return distillate_total_id(unit) if spec.total_condenser else vapor_total_id(unit, 1)


def slot_column(spec: ColumnSpec, end: str, kind: str) -> str:
    """The column a `variable − parameter` slot pins (§2.1, S06 §2): `Q_j`, `V_1` (partial) or
    `D` (total) for `distillate_rate`, `L_N` for `bottoms_rate`; `T_s` (`T_c` at a total
    condenser's s = 1) for `temperature`, the product flow `n_c` for `recovery`, the purity
    column `u` for `purity` (the attribute is the end specification's). Not defined for a
    ratio."""
    unit, stage = spec.unit_id, spec.end_stage(end)
    if kind in INVERSE_KINDS:
        given = _specification(spec, end)
        if given.kind != kind:
            raise ValueError(f"{unit}: the {end} specification is {given.kind!r}, not {kind!r}")
        if kind == "temperature":
            assert given.stage is not None, "validate first"
            return stage_temperature_id(unit, given.stage)
        if kind == "recovery":
            assert given.component is not None, "validate first"
            return product_flow_id(spec, end, given.component)
        return purity_flow_id(unit, stage)
    if kind == "duty":
        return stage_duty_id(unit, stage)
    if kind == "distillate_rate":
        return distillate_total_id(unit) if spec.total_condenser else vapor_total_id(unit, 1)
    if kind == "bottoms_rate":
        return liquid_total_id(unit, stage)
    raise ValueError(f"{kind!r} is not a variable - parameter slot")


def label_source(spec: ColumnSpec, stage: int) -> str:
    """S01 §4.3 with §2.3 as amended (§17 item 2, R-537): `T_{j−1}` for j > 1 (with a total
    condenser stage 2's is `T_c`); for j = 1 the temperature column of the first present inlet in
    `ColumnSpec.inlets()` order, which is `T_top` when there is a `top` inlet. Always a column id.
    A column with no present inlet has none; §5 refuses it (S6, S10) before any form is built, so
    asking here is misuse."""
    if stage > 1:
        return stage_temperature_id(spec.unit_id, stage - 1)
    inlets = spec.inlets()
    if not inlets:
        raise ValueError(f"{spec.unit_id}: stage 1 has no label without a present inlet (§5 S10)")
    return temperature_id(inlet_stream(spec.unit_id, inlets[0].port))


# -- spec §5: validation -------------------------------------------------------------------------


def _feed_total(spec: ColumnSpec) -> float:
    return sum(sum(inlet.state.n) for inlet in spec.inlets())


def component_feeds(spec: ColumnSpec) -> tuple[float, ...]:
    """S06 §1: `F_c = Σ_k n_{k,c}` over the present inlets in `inlets()` order, binary64, one per
    component of `spec.components`."""
    inlets = spec.inlets()
    return tuple(sum(inlet.state.n[i] for inlet in inlets) for i in range(len(spec.components)))


def purity_reference(spec: ColumnSpec) -> float:
    """S06 §1: `F = Σ_c F_c`, binary64, summed in component order."""
    return sum(component_feeds(spec))


def inverse_parameter(spec: ColumnSpec, end: str) -> float:
    """S06 §2: the pinned slot parameter of an inverse end: `T*`, `ν* = fl(r*·F_c)` or
    `π* = fl(x*·F)`."""
    given = _specification(spec, end)
    if given.kind == "temperature":
        return given.value
    if given.kind == "recovery":
        assert given.component is not None, "validate first"
        return given.value * component_feeds(spec)[spec.components.index(given.component)]
    if given.kind == "purity":
        return given.value * purity_reference(spec)
    raise ValueError(f"{given.kind!r} is not an inverse specification")


def specified_quantity(spec: ColumnSpec, end: str, state: Mapping[str, float]) -> float:
    """S06 §7.3: an inverse end's quantity at `state`, binary64: `n_c / P` (purity), `n_c / F_c`
    (recovery) or `T_s` (temperature)."""
    given = _specification(spec, end)
    if given.kind == "temperature":
        assert given.stage is not None, "validate first"
        return float(state[stage_temperature_id(spec.unit_id, given.stage)])
    if given.kind not in COMPONENT_KINDS:
        raise ValueError(f"{given.kind!r} is not an inverse specification")
    assert given.component is not None, "validate first"
    flow = float(state[product_flow_id(spec, end, given.component)])
    if given.kind == "recovery":
        return flow / component_feeds(spec)[spec.components.index(given.component)]
    return flow / float(state[product_total_id(spec, end)])


def saturation_temperature(component: str, pressure: float) -> float:
    """S06 §4: SYN-001's `T_sat,i(P) = (L_i − V_i (P − P_ref)) / (L_i / T_b,i + R ln(P_ref / P))`,
    the root of `ln K_i(T, P) = 0`, in binary64 (K)."""
    i = syn001_thermo.COMPONENTS.index(component)
    latent = syn001_thermo.L_VAP[i]
    numerator = latent - syn001_thermo.V_MOLAR[i] * (pressure - syn001_thermo.P_REF)
    return numerator / (
        latent / syn001_thermo.T_BOIL[i]
        + syn001_thermo.R * math.log(syn001_thermo.P_REF / pressure)
    )


def stage_band(spec: ColumnSpec, stage: int) -> tuple[float, float]:
    """S06 §4: the open band `(T_sat,lightest(P_s*), T_sat,heaviest(P_s*))` over the components
    with `F_c > 0`, as the least and the greatest of their saturation temperatures (§4 shows they
    are ordered A < B < C at every P). Needs a present component; `validate` refuses a feedless
    column first (S10)."""
    pressure = spec.pressures[stage - 1]
    present = [
        saturation_temperature(c, pressure)
        for c, feed in zip(spec.components, component_feeds(spec), strict=True)
        if feed > 0.0
    ]
    if not present:
        raise ValueError(f"{spec.unit_id}: no present component; validate first (S10)")
    return min(present), max(present)


def validate(
    spec: ColumnSpec, provider: PropertyProvider, context: EvaluationContext
) -> CascadeFailure | None:
    """§5, before any row is evaluated: the first refusal that applies, or `None`.

    Order: S01's R1, R2, R3, R4, R6, R5 as written for the present inlets (S01's order), then
    S1–S10, then R7 when every slot is a duty. A malformed object (a pressure or duty list that is
    not one per stage, a non-finite duty, a `None` duty anywhere but a column-specification stage,
    a flow vector of the wrong length, a duplicated port) is misuse and raises `ValueError`.

    S03 §9 S11 precedes R1: a provider other than SYN-001 is refused by identity
    (`property_method_refusal`) before anything else is read or evaluated.
    """
    unit, components = spec.unit_id, spec.components
    # S11 (S03 §9)
    refused = property_method_refusal(unit, provider)
    if refused is not None:
        return refused
    count = spec.stage_count
    # R1
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        return _invalid("stage_count", f"{unit}: N = {count!r} is not an integer >= 1")
    if len(spec.pressures) != count or len(spec.duties) != count:
        raise ValueError(
            f"{unit}: {len(spec.pressures)} pressures and {len(spec.duties)} duties for "
            f"{count} stages"
        )
    for stage, duty in enumerate(spec.duties, start=1):
        if duty is not None and not math.isfinite(duty):
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
                f"{unit}: inlet {inlet.port} declared {inlet.state.phase!r}; a column takes a "
                "declared LIQUID or VAPOR inlet only",
            )
    # R5
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

    refusal = _column_refusal(spec)
    if refusal is not None:
        return refusal

    # R7, only when every slot is a duty (§5).
    if all(_specification(spec, end).kind == "duty" for end in spec.ends()):
        if all(_is_dormant(inlet.state) for inlet in inlets):
            # No end (S10 refused the others): S01 §4.6's all-dormant cascade.
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


#: C8 (Frank, Q-S02-4): the notice on every duty-only column specification. Spec §18.1 item 3 and
#: §14: a `(duty, duty)` column may have several regular roots, and no root-selection claim is made.
MULTIPLE_STEADY_STATES_WARNING: Final = "multiple_steady_states_possible(duty_only)"


def column_warnings(spec: ColumnSpec) -> tuple[str, ...]:
    """C8: the warnings a column answer carries, decided from the specification alone. A column
    is duty-only when it has at least one end and every end's specification is of kind `duty`
    (the §5 R7 condition, which a column without ends satisfies vacuously and gets no warning)."""
    ends = spec.ends()
    given = tuple(spec.end_specification(end) for end in ends)
    if ends and all(found is not None and found.kind == "duty" for found in given):
        return (MULTIPLE_STEADY_STATES_WARNING,)
    return ()


def _specification(spec: ColumnSpec, end: str) -> EndSpecification:
    found = spec.end_specification(end)
    if found is None:
        raise ValueError(f"{spec.unit_id}: no {end} specification; validate first")
    return found


def _column_refusal(spec: ColumnSpec) -> CascadeFailure | None:
    """§5 S1–S10, in that order, on a specification that passed R1–R6."""
    unit, count = spec.unit_id, spec.stage_count
    # S1
    if spec.condenser not in CONDENSER_KINDS:
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE",
            f"unsupported(condenser:{spec.condenser})",
            f"{unit}: condenser kind {spec.condenser!r} is not one of {CONDENSER_KINDS}",
        )
    if spec.reboiler not in REBOILER_KINDS:
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE",
            f"unsupported(reboiler:{spec.reboiler})",
            f"{unit}: reboiler kind {spec.reboiler!r} is not one of {REBOILER_KINDS}",
        )
    # S2
    for end in (CONDENSER, REBOILER):
        given = spec.end_specification(end)
        present = spec.end_kind(end) != "none"
        if given is None and present:
            return _invalid(f"specification:{end}", f"{unit}: no {end} specification")
        if given is None:
            continue
        if not present:
            return _invalid(
                f"specification:{end}", f"{unit}: a {end} specification at a `none` {end}"
            )
        if given.kind in NOT_OFFERED:
            return CascadeFailure(
                "CAPABILITY_UNAVAILABLE",
                f"unsupported(specification:{given.kind})",
                f"{unit}: {given.kind!r} is a specification S02 and S06 do not offer",
            )
        if given.kind not in END_KINDS[end]:
            return _invalid(
                f"specification:{end}",
                f"{unit}: {given.kind!r} is not a {end} specification ({END_KINDS[end]})",
            )
    kinds = {end: _specification(spec, end).kind for end in spec.ends()}
    # S3
    if kinds.get(CONDENSER) == "distillate_rate" and kinds.get(REBOILER) == "bottoms_rate":
        return _invalid(
            "redundant_specification",
            f"{unit}: distillate and bottoms rates are linearly dependent through the overall "
            "balance (§3)",
        )
    # S4, direct kinds only (S06 §5; I1, I2 take the inverse kinds)
    for end in spec.ends():
        given = _specification(spec, end)
        if given.kind in INVERSE_KINDS:
            continue
        value = given.value
        if given.kind == "duty":
            wrong = value >= 0.0 if end == CONDENSER else value <= 0.0
        else:
            wrong = value <= 0.0
        if not math.isfinite(value) or wrong:
            return _invalid(f"{given.kind}:{end}", f"{unit}: {end} {given.kind} = {value!r}")
    # S5
    feed = _feed_total(spec)
    for end in spec.ends():
        given = _specification(spec, end)
        if given.kind in ("distillate_rate", "bottoms_rate") and given.value >= feed:
            return CascadeFailure(
                "INVALID_SPECIFICATION",
                f"infeasible_spec({given.kind}_exceeds_feed)",
                f"{unit}: {given.kind} {given.value!r} mol/s >= F = {feed!r} mol/s",
            )
    # S6
    with_condenser, with_reboiler = spec.condenser != "none", spec.reboiler != "none"
    if (spec.top is not None) == with_condenser:
        return _invalid(
            "top_inlet",
            f"{unit}: a column {'with' if with_condenser else 'without'} a condenser "
            f"{'has no' if with_condenser else 'needs a'} top inlet",
        )
    if (spec.bottom is not None) == with_reboiler:
        return _invalid(
            "bottom_inlet",
            f"{unit}: a column {'with' if with_reboiler else 'without'} a reboiler "
            f"{'has no' if with_reboiler else 'needs a'} bottom inlet",
        )
    # S7
    ends = spec.slot_stages()
    for side in spec.sides:
        if side.stage in ends:
            return _invalid(
                f"side_feed_stage:{side.port}",
                f"{unit}: side feed {side.port} at the {ends[side.stage]} stage {side.stage}",
            )
    # S8
    if count < 1 + int(with_condenser) + int(with_reboiler):
        return _invalid(
            "stage_count", f"{unit}: N = {count} cannot hold a condenser and a reboiler apart"
        )
    misplaced = [
        stage
        for stage, duty in enumerate(spec.duties, start=1)
        if (duty is None) != (stage in ends)
    ]
    if misplaced:
        raise ValueError(
            f"{unit}: Q_j* must be None exactly at the column-specification stages "
            f"{sorted(ends)}; stages {misplaced} disagree"
        )
    # S9
    for stage in range(1, count):
        if spec.pressures[stage] < spec.pressures[stage - 1]:
            return _invalid(
                "pressure_profile",
                f"{unit}: P_{stage + 1}* = {spec.pressures[stage]!r} Pa < "
                f"P_{stage}* = {spec.pressures[stage - 1]!r} Pa",
            )
    # S10
    if spec.ends() and feed == 0.0:
        return _invalid("no_feed", f"{unit}: a column with a condenser or reboiler and no feed")
    return _inverse_refusal(spec)


def _inverse_refusal(spec: ColumnSpec) -> CascadeFailure | None:
    """S06 §5 I1–I6, in that order, on a specification that passed S1–S10. Each rule is applied
    to the condenser end, then the reboiler end, before the next rule."""
    unit, count, components = spec.unit_id, spec.stage_count, spec.components
    given = {end: _specification(spec, end) for end in spec.ends()}
    # I1: the attribute
    for end, found in given.items():
        if found.kind == "temperature":
            stage = found.stage
            wrong = (
                found.component is not None
                or isinstance(stage, bool)
                or not isinstance(stage, int)
                or not 1 <= stage <= count
            )
        elif found.kind in COMPONENT_KINDS:
            wrong = found.stage is not None or found.component not in components
        else:
            wrong = found.component is not None or found.stage is not None
        if wrong:
            return _invalid(
                f"{found.kind}:{end}",
                f"{unit}: {end} {found.kind} with component {found.component!r} and stage "
                f"{found.stage!r} (N = {count}, components {components})",
            )
    # I2: the value
    for end, found in given.items():
        if found.kind not in INVERSE_KINDS:
            continue
        value = found.value
        if not math.isfinite(value) or (found.kind in COMPONENT_KINDS and not 0.0 < value < 1.0):
            return _invalid(f"{found.kind}:{end}", f"{unit}: {end} {found.kind} = {value!r}")
    feeds = component_feeds(spec)
    # I3: an absent component
    for end, found in given.items():
        if found.kind in COMPONENT_KINDS:
            assert found.component is not None
            if feeds[components.index(found.component)] == 0.0:
                return CascadeFailure(
                    "INVALID_SPECIFICATION",
                    f"infeasible_spec(absent_component:{end})",
                    f"{unit}: {end} {found.kind} of {found.component}, which no inlet carries",
                )
    # I4: the stage band (§4)
    for found in given.values():
        if found.kind == "temperature":
            assert found.stage is not None
            low, high = stage_band(spec, found.stage)
            if not low < found.value < high:
                return CascadeFailure(
                    "INVALID_SPECIFICATION",
                    f"infeasible_spec(temperature_outside_band:{found.stage})",
                    f"{unit}: T_{found.stage}* = {found.value!r} K outside the open band "
                    f"({low!r}, {high!r}) K at P_{found.stage}*",
                )
    # I5: redundant specifications
    stages = [found.stage for found in given.values() if found.kind == "temperature"]
    totals = [Fraction(feed) for feed in feeds]
    rows, rhs = _split_rows(spec, totals)
    if len(stages) != len(set(stages)) or (rows and _rank(rows) < len(rows)):
        return _invalid(
            "redundant_specification",
            f"{unit}: two temperatures name one stage, or the specifications linear in the "
            "product split are linearly dependent (S06 §5 I5)",
        )
    # I6: no product split
    if rows and not _split_feasible(totals, rows, rhs):
        return CascadeFailure(
            "INVALID_SPECIFICATION",
            "infeasible_spec(mass_balance)",
            f"{unit}: no top product with 0 < t_c < F_c for every present c meets the "
            "specifications linear in it (S06 §5 I6)",
        )
    return None


def _split_rows(
    spec: ColumnSpec, totals: list[Fraction]
) -> tuple[list[list[Fraction]], list[Fraction]]:
    """S06 §5's table: the end specifications linear in the top product `t`, as rows `a·t = b`,
    exact on the binary64 inputs. Ratios, duties and temperatures give none."""
    feed = sum(totals, Fraction(0))
    rows: list[list[Fraction]] = []
    rhs: list[Fraction] = []
    for end in spec.ends():
        found = _specification(spec, end)
        value = Fraction(found.value)
        if found.kind == "distillate_rate":
            rows.append([Fraction(1)] * len(totals))
            rhs.append(value)
        elif found.kind == "bottoms_rate":
            rows.append([Fraction(1)] * len(totals))
            rhs.append(feed - value)
        elif found.kind in COMPONENT_KINDS:
            assert found.component is not None
            k = spec.components.index(found.component)
            unit_vector = [Fraction(int(i == k)) for i in range(len(totals))]
            if found.kind == "recovery":
                rows.append(unit_vector)
                rhs.append((value if end == CONDENSER else 1 - value) * totals[k])
            elif end == CONDENSER:
                rows.append([e - value for e in unit_vector])
                rhs.append(Fraction(0))
            else:
                rows.append([value - e for e in unit_vector])
                rhs.append(value * feed - totals[k])
    return rows, rhs


def _reduce(
    rows: list[list[Fraction]], rhs: list[Fraction], n: int
) -> tuple[list[Fraction] | None, list[list[Fraction]]]:
    """Gauss–Jordan in exact arithmetic: a particular solution `t⁰` of `rows·t = rhs` (`None`
    when inconsistent) and a basis of the null space, so every solution is `t⁰ + N s`."""
    matrix = [[*row, b] for row, b in zip(rows, rhs, strict=True)]
    pivots: list[int] = []
    r = 0
    for col in range(n):
        found = next((i for i in range(r, len(matrix)) if matrix[i][col] != 0), None)
        if found is None:
            continue
        matrix[r], matrix[found] = matrix[found], matrix[r]
        pivot = matrix[r][col]
        matrix[r] = [entry / pivot for entry in matrix[r]]
        for i in range(len(matrix)):
            if i != r and matrix[i][col] != 0:
                factor = matrix[i][col]
                matrix[i] = [a - factor * b for a, b in zip(matrix[i], matrix[r], strict=True)]
        pivots.append(col)
        r += 1
    if any(row[n] != 0 for row in matrix[r:]):
        return None, []
    particular = [Fraction(0)] * n
    for i, col in enumerate(pivots):
        particular[col] = matrix[i][n]
    basis: list[list[Fraction]] = []
    for free in (col for col in range(n) if col not in pivots):
        vector = [Fraction(0)] * n
        vector[free] = Fraction(1)
        for i, col in enumerate(pivots):
            vector[col] = -matrix[i][free]
        basis.append(vector)
    return particular, basis


def _rank(rows: list[list[Fraction]]) -> int:
    """The rank of `rows` over every component (S06 §5 I5)."""
    n = len(rows[0])
    _, basis = _reduce(rows, [Fraction(0)] * len(rows), n)
    return n - len(basis)


def _split_feasible(
    totals: list[Fraction], rows: list[list[Fraction]], rhs: list[Fraction]
) -> bool:
    """S06 §5 I6: is there a `t` with `0 < t_c < F_c` for every present c (`t_c = 0` for an
    absent one) meeting `rows·t = rhs`? Decided exactly: with no free direction test the point;
    with one intersect the open intervals per coordinate; with one row test
    `Σ min(0, a_c F_c) < b < Σ max(0, a_c F_c)`."""
    present = [c for c, total in enumerate(totals) if total > 0]
    box = [totals[c] for c in present]
    reduced = [[row[c] for c in present] for row in rows]
    particular, basis = _reduce(reduced, rhs, len(present))
    if particular is None:
        return False
    if not basis:
        return all(0 < t < high for t, high in zip(particular, box, strict=True))
    if len(basis) == 1:
        (direction,) = basis
        low: Fraction | None = None
        high: Fraction | None = None
        for t, d, upper in zip(particular, direction, box, strict=True):
            if d == 0:
                if not 0 < t < upper:
                    return False
                continue
            a, b = sorted(((0 - t) / d, (upper - t) / d))
            low = a if low is None else max(low, a)
            high = b if high is None else min(high, b)
        return low is None or high is None or low < high
    if len(reduced) == 1:
        (row,) = reduced
        lower = sum((min(Fraction(0), a * f) for a, f in zip(row, box, strict=True)), Fraction(0))
        upper = sum((max(Fraction(0), a * f) for a, f in zip(row, box, strict=True)), Fraction(0))
        return lower < rhs[0] < upper
    # Two independent rows and two or more free directions: four or more present components,
    # which SYN-001 (three) cannot declare. Not decided here rather than guessed.
    raise ValueError(
        f"S06 §5 I6 is decided for at most three present components; {len(present)} given"
    )


def energy_precheck(
    spec: ColumnSpec, provider: PropertyProvider, context: EvaluationContext
) -> EnergyPrecheck:
    """S01 §5 R7 on a column whose every slot is a duty, W, with
    `H* = H_in + Σ_j Q_j*` over every stage's duty, the ends' included, and the bounds
    `Σ_i F_i h_i^L(T_min, P_N*)`, `Σ_i F_i h_i^V(T_max)`."""
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
    duties = [duty for duty in spec.duties if duty is not None]
    duties.extend(_specification(spec, end).value for end in spec.ends())
    p_bottom = spec.pressures[-1]
    return EnergyPrecheck(
        inflow=h_in,
        target=h_in + sum(duties),
        lower=_enthalpy_flow(provider, context, components, totals, T_MIN, p_bottom, "LIQUID"),
        upper=_enthalpy_flow(provider, context, components, totals, T_MAX, p_bottom, "VAPOR"),
    )


# -- spec §2: declared rows ----------------------------------------------------------------------


def declared_rows(
    spec: ColumnSpec, provider: PropertyProvider, context: EvaluationContext
) -> Contribution:
    """The §2 columns, rows, blocks and pinned inputs: `14 n_eq + (C + 2) n_in + (2C + 5)[total]`
    of each (§3), plus one column `u` and one definition row per `purity` end (S06 §3).

    Stage order, the total condenser's block first when there is one, then each present inlet.
    An equilibrium stage's columns and rows are S01's, in S01's order, with its slot row in the
    place of `Q_j − Q_j*`. Call after `validate`.
    """
    unit, components = _token(spec.unit_id), spec.components
    count = spec.stage_count
    inlets = spec.inlets()
    for inlet in inlets:
        _token(inlet.port)
    total = spec.total_condenser
    stages = spec.equilibrium_stages()
    slots = spec.slot_stages()

    variables: list[str] = []
    variable_kinds: dict[str, QuantityKind] = {}
    equations: list[EquationSpec] = []
    row_kinds: dict[str, QuantityKind] = {}
    blocks: list[LnKBlock | EnthalpyFlowBlock] = []
    block_inputs: dict[str, tuple[str, ...]] = {}
    parameter_ids: list[str] = []
    parameters: dict[str, float] = {}

    def column(name: str, kind: QuantityKind | None) -> None:
        variables.append(name)
        if kind is not None:
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
        parameter_ids.append(name)
        parameters[name] = normalize_zero(float(value))
        return name

    def enthalpy_block(
        token: str, phase: Phase, flows: tuple[str, ...], t: str, p: str
    ) -> tuple[str, ...]:
        block = EnthalpyFlowBlock(
            provider, components, phase, context, block_id=enthalpy_block_id(token, phase)
        )
        blocks.append(block)
        block_inputs[block.block_id] = (*flows, t, p)
        return tuple(f"{block.block_id}.{out}" for out in block.output_ids)

    def lnk_block(token: str, t: str, p: str) -> str:
        lnk = LnKBlock(provider, components, context, block_id=lnk_block_id(token))
        blocks.append(lnk)
        block_inputs[lnk.block_id] = (t, p)
        return lnk.block_id

    # Blocks, as S01: one lnK and one enthalpy block per (stage, phase) outlet, one per inlet; at
    # a total condenser one lnK (the bubble row) and one liquid block each for `r` and `d`.
    vapor_keys: dict[int, tuple[str, ...]] = {}
    liquid_keys: dict[int, tuple[str, ...]] = {}
    lnk_keys: dict[int, str] = {}
    reflux_keys: tuple[str, ...] = ()
    distillate_keys: tuple[str, ...] = ()
    if total:
        t_c, p_c = stage_temperature_id(unit, 1), stage_pressure_id(unit, 1)
        lnk_keys[1] = lnk_block(f"{unit}_s1", t_c, p_c)
        reflux_keys = enthalpy_block(
            f"{unit}_s1_r", "LIQUID", tuple(reflux_id(unit, c) for c in components), t_c, p_c
        )
        distillate_keys = enthalpy_block(
            f"{unit}_s1_d", "LIQUID", tuple(distillate_id(unit, c) for c in components), t_c, p_c
        )
    for stage in stages:
        token = f"{unit}_s{stage}"
        t, p = stage_temperature_id(unit, stage), stage_pressure_id(unit, stage)
        lnk_keys[stage] = lnk_block(token, t, p)
        vapor_keys[stage] = enthalpy_block(
            token, "VAPOR", tuple(vapor_id(unit, stage, c) for c in components), t, p
        )
        liquid_keys[stage] = enthalpy_block(
            token, "LIQUID", tuple(liquid_id(unit, stage, c) for c in components), t, p
        )
    inlet_keys: dict[str, tuple[str, ...]] = {}
    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        inlet_keys[inlet.port] = enthalpy_block(
            f"{unit}_in_{inlet.port}",
            _phase(inlet.state),
            tuple(flow_id(stream, c) for c in components),
            temperature_id(stream),
            pressure_id(stream),
        )

    def slot(stage: int) -> None:
        """Stage j's slot row: `Q_j − Q_j*` (S01's id) or the column specification (§2.1)."""
        end = slots.get(stage)
        if end is None:
            duty = spec.duties[stage - 1]
            assert duty is not None
            row(
                stage_row_id(unit, stage, "Q"),
                specification_row(
                    stage_duty_id(unit, stage), pin(_parameter(stage_duty_id(unit, stage)), duty)
                ),
                "algebraic",
                "CAS-Q",
                "heat_rate",
            )
            return
        given = _specification(spec, end)
        build: RowBuilder
        if given.kind in RATIO_KINDS:
            ratio = pin(ratio_parameter(unit, stage, given.kind), given.value)
            if given.kind == "boilup_ratio":
                build = ratio_row(
                    (vapor_total_id(unit, stage),), ratio, liquid_total_id(unit, stage)
                )
            elif total:
                build = ratio_row(
                    tuple(reflux_id(unit, c) for c in components), ratio, distillate_total_id(unit)
                )
            else:
                build = ratio_row((liquid_total_id(unit, 1),), ratio, vapor_total_id(unit, 1))
        elif given.kind in INVERSE_KINDS:
            # S06 §2: `T_s − T*`, `n_c − ν*` or `u − π*`, each `variable − parameter`.
            pinned = slot_column(spec, end, given.kind)
            build = specification_row(pinned, pin(_parameter(pinned), inverse_parameter(spec, end)))
        else:
            pinned = slot_column(spec, end, given.kind)
            build = specification_row(pinned, pin(_parameter(pinned), given.value))
        row(
            slot_row_id(unit, stage, given.kind),
            build,
            "algebraic",
            _SLOT_FAMILY[given.kind],
            _INVERSE_ROW_KIND.get(
                given.kind, "heat_rate" if given.kind == "duty" else "molar_flow"
            ),
        )
        if given.kind == "purity":
            # S06 §2: the column `u` and its definition `F n_c − u P`, after the slot row.
            assert given.component is not None
            scaled = purity_flow_id(unit, stage)
            column(scaled, "molar_flow")
            row(
                stage_row_id(unit, stage, "spec", "purity_definition"),
                scaled_definition_row(
                    product_flow_id(spec, end, given.component),
                    pin(purity_reference_parameter(unit, stage), purity_reference(spec)),
                    scaled,
                    product_total_id(spec, end),
                ),
                "algebraic",
                "COL-purity-definition",
                "molar_flow_squared",
            )

    if total:
        # §2.2: columns r_i, d_i, phi, D, T_c, P_c, Q_c; rows bal_i, split_i, Ddef, bubble,
        # energy, P, slot.
        for c in components:
            column(reflux_id(unit, c), "molar_flow")
        for c in components:
            column(distillate_id(unit, c), "molar_flow")
        # `phi` is a pure number: the column-only kind `dimensionless`, nominal 1 (§17 item 1).
        column(reflux_fraction_id(unit), "dimensionless")
        column(distillate_total_id(unit), "molar_flow")
        column(stage_temperature_id(unit, 1), "temperature")
        column(stage_pressure_id(unit, 1), "pressure")
        column(stage_duty_id(unit, 1), "heat_rate")
        for c in components:
            row(
                stage_row_id(unit, 1, "bal", c),
                balance_row((vapor_id(unit, 2, c),), (reflux_id(unit, c), distillate_id(unit, c))),
                "holdup_balance",
                "COL-tc-bal",
                "molar_flow",
            )
        for c in components:
            row(
                stage_row_id(unit, 1, "split", c),
                fraction_row(reflux_id(unit, c), reflux_fraction_id(unit), vapor_id(unit, 2, c)),
                "algebraic",
                "COL-tc-split",
                "molar_flow",
            )
        row(
            stage_row_id(unit, 1, "Ddef"),
            definition_row(
                distillate_total_id(unit), tuple(distillate_id(unit, c) for c in components)
            ),
            "algebraic",
            "COL-tc-Ddef",
            "molar_flow",
        )
        row(
            stage_row_id(unit, 1, "bubble"),
            bubble_row(
                tuple(vapor_id(unit, 2, c) for c in components),
                tuple(f"{lnk_keys[1]}.lnK_{c}" for c in components),
                vapor_total_id(unit, 2),
            ),
            "algebraic",
            "COL-tc-bubble",
            "molar_flow",
        )
        row(
            energy_row_id(unit, 1),
            energy_row(
                vapor_keys[2], (*reflux_keys, *distillate_keys), source=stage_duty_id(unit, 1)
            ),
            "holdup_balance",
            "COL-tc-energy",
            "heat_rate",
        )
        row(
            stage_row_id(unit, 1, "P"),
            specification_row(
                stage_pressure_id(unit, 1),
                pin(_parameter(stage_pressure_id(unit, 1)), spec.pressures[0]),
            ),
            "algebraic",
            "COL-tc-P",
            "pressure",
        )
        slot(1)

    sides_at: dict[int, list[PlacedInlet]] = {}
    for inlet in inlets:
        if inlet.port not in (TOP, BOTTOM):
            sides_at.setdefault(inlet.stage, []).append(inlet)

    for stage in stages:
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
            row(
                stage_row_id(unit, stage, "mix", c),
                balance_row(_inflow(spec, stage, c), (mixed_id(unit, stage, c),)),
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
        above: tuple[str, ...]
        if stage == 1:
            above = inlet_keys[TOP] if spec.top is not None else ()
        elif stage == 2 and total:
            above = reflux_keys
        else:
            above = liquid_keys[stage - 1]
        below: tuple[str, ...]
        if stage == count:
            below = inlet_keys[BOTTOM] if spec.bottom is not None else ()
        else:
            below = vapor_keys[stage + 1]
        row(
            energy_row_id(unit, stage),
            energy_row(
                (*above, *below, *(key for s in sides for key in inlet_keys[s.port])),
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
                pin(_parameter(stage_pressure_id(unit, stage)), spec.pressures[stage - 1]),
            ),
            "algebraic",
            "CAS-P",
            "pressure",
        )
        slot(stage)

    for inlet in inlets:
        stream = inlet_stream(unit, inlet.port)
        for c in components:
            column(flow_id(stream, c), "molar_flow")
        column(temperature_id(stream), "temperature")
        column(pressure_id(stream), "pressure")
        for c, value in zip(components, inlet.state.n, strict=True):
            row(
                inlet_row_id(unit, inlet.port, "n", c),
                specification_row(flow_id(stream, c), pin(_parameter(flow_id(stream, c)), value)),
                "algebraic",
                "CAS-inlet-n",
                "molar_flow",
            )
        row(
            inlet_row_id(unit, inlet.port, "T"),
            specification_row(
                temperature_id(stream),
                pin(_parameter(temperature_id(stream)), inlet.state.temperature),
            ),
            "algebraic",
            "CAS-inlet-T",
            "temperature",
        )
        row(
            inlet_row_id(unit, inlet.port, "P"),
            specification_row(
                pressure_id(stream), pin(_parameter(pressure_id(stream)), inlet.state.pressure)
            ),
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


def _inflow(spec: ColumnSpec, stage: int, c: str) -> tuple[str, ...]:
    """Equilibrium stage j's `mix` inflow of component c, in S01's order: from above (`top`,
    the reflux `r` below a total condenser, or `l_{j−1}`; nothing without a `top` inlet), from
    below (`bottom` or `v_{j+1}`; nothing without a `bottom` inlet), then its side feeds."""
    unit = spec.unit_id
    names: list[str] = []
    if stage == 1:
        if spec.top is not None:
            names.append(flow_id(inlet_stream(unit, TOP), c))
    elif stage == 2 and spec.total_condenser:
        names.append(reflux_id(unit, c))
    else:
        names.append(liquid_id(unit, stage - 1, c))
    if stage == spec.stage_count:
        if spec.bottom is not None:
            names.append(flow_id(inlet_stream(unit, BOTTOM), c))
    else:
        names.append(vapor_id(unit, stage + 1, c))
    names.extend(
        flow_id(inlet_stream(unit, side.port), c) for side in spec.sides if side.stage == stage
    )
    return tuple(names)


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
    k_stage = {
        j: _k_values(provider, context, components, profile[j - 1], spec.pressures[j - 1])
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
