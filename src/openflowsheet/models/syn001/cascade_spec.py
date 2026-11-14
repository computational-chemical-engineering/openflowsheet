"""`syn001.cascade`'s declarations: the equation families (S01 spec §2), the specification object
and the cascade's column and row ids.

Moved verbatim from `cascade` (S19 B4), which re-exports every name here and keeps the §5
refusals, the §4.2 regime forms and the §4.6 dormant answer. This module imports nothing from the
other cascade modules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

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
from openflowsheet.thermo import Phase

MODEL_ID: Final = "syn001.cascade"


#: Where the equations are stated.
SPECIFICATION: Final = "docs/derivations/S01-spec.md §2"


#: The two fixed ports. Side feeds carry their own port names.
TOP: Final = "top"


BOTTOM: Final = "bottom"


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


def _phase(state: InletState) -> Phase:
    if state.phase == "LIQUID":
        return "LIQUID"
    if state.phase == "VAPOR":
        return "VAPOR"
    raise ValueError(f"inlet phase {state.phase!r} is not LIQUID or VAPOR; validate first")
