"""`syn001.column`'s declarations: the specification kinds and equation families (S02 spec §2,
S06 §1 and §2), the specification object and the column's ids and names.

Moved verbatim from `column` (S19 B2), which re-exports every public name here and keeps the regime
forms and the §6 initializer. This module imports nothing from the other column modules.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from openflowsheet.compile.spec import QuantityKind
from openflowsheet.models import Accumulation, DeclaredEquation, Holdup, row_id, temperature_id
from openflowsheet.models.syn001 import (
    COMPONENTS,
    ENERGY,
    MOLAR_FLOW,
    MOLE,
    POWER,
    PRESSURE,
    TEMPERATURE,
)
from openflowsheet.models.syn001.cascade import (
    BOTTOM,
    TOP,
    InletState,
    PlacedInlet,
    SideFeed,
    inlet_stream,
    liquid_id,
    liquid_total_id,
    stage_duty_id,
    stage_prefix,
    stage_row_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade import EQUATIONS as CASCADE_EQUATIONS

MODEL_ID: Final = "syn001.column"


#: Where the equations are stated.
SPECIFICATION: Final = "docs/derivations/S02-spec.md §2"


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


S11_SPECIFICATION: Final = "docs/derivations/S11-design.md §4.7.3"


#: The ratio specifications (§2.1, "ratio" form); every other kind is `variable − parameter`.
RATIO_KINDS: Final[tuple[str, ...]] = ("reflux_ratio", "boilup_ratio")


#: S10-C §4.8 (ADR 0049 D7): the end specification kinds a column admits for a
#: composition-dependent equilibrium form; `purity`, `recovery` and `temperature` are refused,
#: typed, after S1–S10 and before I1 (their bands and inverse rows are SYN-001's closed forms).
GAMMA_PHI_KINDS: Final[tuple[str, ...]] = (
    "reflux_ratio",
    "boilup_ratio",
    "distillate_rate",
    "bottoms_rate",
    "duty",
)


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


#: S11 §4.7.3 and §4.7.4: what the column authors only in a flowsheet (`declared_rows(...,
#: links=...)`): the inlet and product link rows and the recovery definition. Its recovery slot
#: is `w - nu*` there, under `COL-recovery`'s family, with `nu* = r* F_ref`.
FLOWSHEET_EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="COL-inlet-link",
        statement="v_stream - v_inlet = 0 for each flow, T and P of a connected inlet stream "
        "(the pin rows' ids and kinds)",
        dependencies=("stream.n", "stream.T", "stream.P", "inlet.n", "inlet.T", "inlet.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        source=S11_SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-product-link",
        statement="v_stream - v_product = 0 for each flow, T and P of the distillate (v_1 or d, "
        "T_1, P_1) and the bottoms (l_N, T_N, P_N)",
        dependencies=("stream.n", "stream.T", "stream.P", "product.n", "stage.T", "stage.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        source=S11_SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="COL-recovery-definition",
        statement="F_ref n_c - w sum_k n_k,c = 0, n_c the end's product flow of c and n_k,c the "
        "column's inlet flows of c (S06 §15 Q7 ruling)",
        dependencies=("product.n", "inlet.n", "column.w", "parameters.F_ref"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        source=S11_SPECIFICATION,
    ),
)


#: S11 §4.7.4: the fixed reference flow, mol/s, that replaces `F` (purity) and `F_c` (recovery)
#: in a flowsheet, where the feed is solved; `pi* = x* F_ref` and `nu* = r* F_ref`.
F_REF: Final = 1.0


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


def recovery_flow_id(unit: str, stage: int) -> str:
    """S11 §4.7.4: the recovery column `w = F_ref n_c / F_c` of the end at `stage` in a
    flowsheet, `<U>.stage.<j>.recovery_flow`."""
    return f"{stage_prefix(unit, stage)}.recovery_flow"


def recovery_reference_parameter(unit: str, stage: int) -> str:
    """S11 §4.7.4: the pinned `F_ref` of the recovery definition at `stage`,
    `<U>.stage.<j>.recovery_reference*`."""
    return f"{stage_prefix(unit, stage)}.recovery_reference*"


def product_link_row_id(unit: str, product: str, kind: str, *component: str) -> str:
    """S11 §4.7.3: `<U>:product:<distillate|bottoms>:<n:<c>|T|P>`."""
    return row_id(unit, "product", product, kind, *component)


@dataclass(frozen=True)
class FlowsheetLinks:
    """S11 §4.7.3: the flowsheet streams a column instance is wired to. `inlets` maps each port
    of `ColumnSpec.inlets()` (`top`, `bottom`, the side feeds' ports) to its connected stream;
    `distillate` and `bottoms` name the two product streams. The stream columns are the
    flowsheet's (`flow_id`, `temperature_id`, `pressure_id`); the column owns none of them."""

    inlets: Mapping[str, str]
    distillate: str
    bottoms: str


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


def _specification(spec: ColumnSpec, end: str) -> EndSpecification:
    found = spec.end_specification(end)
    if found is None:
        raise ValueError(f"{spec.unit_id}: no {end} specification; validate first")
    return found
