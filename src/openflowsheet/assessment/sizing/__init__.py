"""Sizing models per unit family (E01 design §4.4; ADR 0052 D3).

A *family* turns one host unit into its costable *items* (§4.4.0): the `size.<item>.<q>` outputs
(each a functional of the solved state), the θ its inputs become (`asm:item.<item>.<input>`), the
volumetric-flow blocks it needs (§4.4.3), its regime entries (service, utility, approach, argmax,
dormant; §4.3.1), and its refusals and limitations. The `size` regime of an item belongs to the
cost entry that prices it (WO-A3/A4), which reads `SizedItem`.

`FAMILIES` maps a host model id to its family; `register_family` is the extension point for later
unit packages. The model ids, ports and variable ids the families read are those of the model
registry (verified by WO-A2, recorded in `docs/E01A_DECISIONS.md`).

Every choice is made on floats at the planning state (`SizingContext.value`) or taken from the
held regime, and handed to the builders as data: a builder never branches on a symbol (§4.2.2).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol

from openflowsheet.assessment.blocks import (
    VOLUME_OUTPUT,
    SaturatedVolumetricFlowBlock,
    VolumetricFlowBlock,
    saturated_volume_available,
    volume_available,
    volumetric_block_id,
)
from openflowsheet.assessment.defaults import default
from openflowsheet.assessment.program import (
    BuildContext,
    ContributionPlan,
    FunctionalBuilder,
    Limitation,
    OutputDef,
    Refusal,
    Symbols,
    Theta,
)
from openflowsheet.assessment.quantities import SIZE_QUANTITIES
from openflowsheet.assessment.regimes import AdmissibilityRow, RegimeEntry, select_dormancy
from openflowsheet.assessment.views import UnitRef
from openflowsheet.compile.spec import Algebra, Expr, PropertyBlock
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.thermal.state import liquid_id, vapor_id
from openflowsheet.thermo import Phase

__all__ = [
    "FAMILIES",
    "GRAVITY",
    "Family",
    "ItemFamily",
    "SizedItem",
    "SizingContext",
    "SizingInput",
    "SizingPlan",
    "StreamFlow",
    "argmax_rows",
    "family_of",
    "nominal",
    "plan_sizing",
    "register_family",
    "size_output",
    "sub_item",
]

#: Standard gravity, m s⁻² (exact by definition, CGPM 1901), for a pump's head (§4.4.5).
GRAVITY: Final = 9.80665

ItemFamily = Literal[
    "exchanger.utility",
    "exchanger.process",
    "drum",
    "machine.pump",
    "machine.compressor",
    "machine.turbine",
    "drive",
    "column.shell",
    "column.trays",
    "reactor.vessel",
]


@dataclass(frozen=True)
class SizingInput:
    """One recorded input of an item (§4.5.5): its name, value, unit, whether it was defaulted,
    and the θ that carries it (`None` for a host quantity or a structural constant)."""

    name: str
    value: float | str
    unit: str
    defaulted: bool
    theta_id: str | None = None


@dataclass(frozen=True)
class SizedItem:
    """One costable item (§4.4.0) as the cost entry that prices it reads it.

    `size` maps a quantity (`area`, `volume`, `diameter`, `height`, `power`, `vol_flow`, `head`)
    to its output id. `design_pressure` is the host variable id or the constant (Pa) the
    correlation's pressure factor reads. `options` are the item's structural choices (material,
    orientation, subtype, tray type, `N_act`). `utility` and `duty` give the exchanger's utility
    and a builder of its absolute duty `|Q|` (W), for the operating cost (WO-A4); `electricity`
    is `consumption` or `generation`, with `power` the builder of that electric power (W).
    """

    item_id: str
    unit_id: str
    family: ItemFamily
    size: Mapping[str, str]
    inputs: tuple[SizingInput, ...] = ()
    design_pressure: str | float | None = None
    options: Mapping[str, Any] = field(default_factory=dict)
    utility: str | None = None
    duty: FunctionalBuilder | None = None
    electricity: Literal["consumption", "generation"] | None = None
    power: FunctionalBuilder | None = None


@dataclass(frozen=True)
class SizingPlan:
    """A family's contribution: items plus the plan fragment the cost contributor merges."""

    items: tuple[SizedItem, ...] = ()
    outputs: tuple[OutputDef, ...] = ()
    theta: tuple[Theta, ...] = ()
    blocks: tuple[tuple[PropertyBlock, tuple[str, ...]], ...] = ()
    regime_entries: tuple[RegimeEntry, ...] = ()
    refusals: tuple[Refusal, ...] = ()
    limitations: tuple[Limitation, ...] = ()
    #: Units listed as having no equipment (`NO_EQUIPMENT`, §4.4.0).
    no_equipment: tuple[str, ...] = ()

    def merged(self, other: SizingPlan) -> SizingPlan:
        return SizingPlan(
            *(
                getattr(self, name) + getattr(other, name)
                for name in (
                    "items",
                    "outputs",
                    "theta",
                    "blocks",
                    "regime_entries",
                    "refusals",
                    "limitations",
                    "no_equipment",
                )
            )
        )

    def contribution(self) -> ContributionPlan:
        return ContributionPlan(
            outputs=self.outputs,
            theta=self.theta,
            blocks=self.blocks,
            regime_entries=self.regime_entries,
            refusals=self.refusals,
            limitations=self.limitations,
        )


@dataclass(frozen=True)
class StreamFlow:
    """A stream's volumetric flow as a builder reads it (§4.4.3).

    `block_id` is `None` for a dormant stream (V̇ ≡ 0.0) or a declared liquid molar volume
    (`declared_v`, m³/mol θ: `V̇ = N·v_decl`). `mass` builds `ṁ = Σ M_c n_c` (kg/s), `moles` builds
    `N` (mol/s).
    """

    stream: str
    dormant: bool
    block_id: str | None
    mass: FunctionalBuilder
    moles: FunctionalBuilder
    declared_v: str | None = None

    def vdot(self, s: Symbols, a: Algebra) -> Expr:
        if self.dormant:
            return 0.0
        if self.declared_v is not None:
            return self.moles(s, a) * s.theta(self.declared_v)
        assert self.block_id is not None
        return s.block(self.block_id, VOLUME_OUTPUT)

    def density(self, s: Symbols, a: Algebra) -> Expr:
        """`ρ = M̄/v = ṁ/V̇` (kg/m³); undefined (the caller refuses) for a dormant stream."""
        return self.mass(s, a) / self.vdot(s, a)


class SizingContext:
    """What a family plans from: the build context, the state, the document's items, utilities and
    defaults, and the shared block and θ registries of one planning pass (§4.2.4 order)."""

    def __init__(self, ctx: BuildContext, state: Mapping[str, float]) -> None:
        self.ctx = ctx
        self.state = state
        document = ctx.spec.document
        self.items: Mapping[str, Mapping[str, Any]] = document.get("items", {})
        self.utilities: tuple[Mapping[str, Any], ...] = tuple(document.get("utilities", ()))
        self.defaults: Mapping[str, Any] = document.get("defaults", {})
        self.variables = frozenset(ctx.host_spec.variable_ids)
        self.parameters: Mapping[str, float] = ctx.host_spec.parameters
        self._blocks: list[tuple[PropertyBlock, tuple[str, ...]]] = []
        self._flows: dict[tuple[str, str], StreamFlow | Refusal] = {}

    # -- document inputs -------------------------------------------------------------------------

    def item(self, item_id: str) -> Mapping[str, Any]:
        return self.items.get(item_id, {})

    def utility(self, utility_id: str) -> Mapping[str, Any] | None:
        return next((u for u in self.utilities if u["utility_id"] == utility_id), None)

    def input(
        self,
        item_id: str,
        name: str,
        unit: str,
        *,
        item_key: str | None = None,
        default_key: str | None = None,
        structural: bool = False,
    ) -> tuple[Theta, SizingInput]:
        """The item's input `name` as θ `asm:item.<item>.<name>`: from the item (`item_key`),
        else the document's `defaults.<default_key>`, else the built-in default (reported)."""
        key = item_key or name
        doc = self.item(item_id)
        defaulted = False
        if key in doc:
            value, provenance = float(doc[key]), f"items.{item_id}.{key}"
        elif default_key is not None and default_key in self.defaults:
            value, provenance = float(self.defaults[default_key]), f"defaults.{default_key}"
        elif default_key is not None:
            entry = default(default_key)
            value, provenance = float(entry.value), f"default {entry.key}: {entry.text}"
            defaulted = True
        else:
            raise KeyError(f"{item_id}.{name} has neither a document value nor a default")
        theta_id = f"asm:item.{item_id}.{name}"
        theta = Theta(theta_id, value, unit, provenance, structural=structural)
        return theta, SizingInput(name, value, unit, defaulted, theta_id)

    def x(self, variable_id: str) -> float:
        return float(self.state[variable_id])

    # -- volumetric flows (§4.4.3) ---------------------------------------------------------------

    def total(self, stream: str) -> float:
        """N of a stream at the state, a left fold over the host's components."""
        if vapor_id(stream) in self.variables:
            return self.x(vapor_id(stream)) + self.x(liquid_id(stream))
        return sum(self.x(flow_id(stream, c)) for c in self.ctx.view.components)

    def moles_builder(self, stream: str) -> FunctionalBuilder:
        if vapor_id(stream) in self.variables:
            return lambda s, a: s.x(vapor_id(stream)) + s.x(liquid_id(stream))
        ids = tuple(flow_id(stream, c) for c in self.ctx.view.components)

        def moles(s: Symbols, a: Algebra) -> Expr:
            total: Expr = s.x(ids[0])
            for name in ids[1:]:
                total = total + s.x(name)
            return total

        return moles

    def mass_builder(self, stream: str) -> FunctionalBuilder:
        """`ṁ = Σ M_c n_c`, kg/s, a left fold in component order (molar masses are constants)."""
        masses = self.ctx.view.molar_masses()
        components = self.ctx.view.components
        if vapor_id(stream) in self.variables:
            (component,) = components
            mass = masses[component]
            return lambda s, a: mass * (s.x(vapor_id(stream)) + s.x(liquid_id(stream)))
        terms = tuple((masses[c], flow_id(stream, c)) for c in components)

        def build(s: Symbols, a: Algebra) -> Expr:
            total: Expr = terms[0][0] * s.x(terms[0][1])
            for mass, name in terms[1:]:
                total = total + mass * s.x(name)
            return total

        return build

    def dormant_entry(
        self, item_id: str, stream: str, flows: Sequence[str] | None = None
    ) -> RegimeEntry:
        """`<item>.<stream>.dormant` (§4.3.1): the held choice, else rule 3 on the state (the
        stream's total, or the sum of `flows` for a column stage)."""
        entry_id = f"{item_id}.{stream}.dormant"
        held = self.ctx.regime.choice(entry_id)
        total = self.total(stream) if flows is None else sum(self.x(name) for name in flows)
        choice = held if held is not None else select_dormancy(total)
        return RegimeEntry(entry_id, "dormant", choice, "§4.3.2 rule 3")

    def flow(
        self,
        item_id: str,
        stream: str,
        phase: Phase,
        *,
        target: str = "v",
        declared_v: str | None = None,
        state_ids: tuple[Sequence[str], str, str] | None = None,
    ) -> tuple[StreamFlow | Refusal, RegimeEntry]:
        """The stream's `StreamFlow` for one item, and its dormant entry. A saturated stream (S11
        thermal, `<S>.sat.V` a host column) uses the saturated block whatever `phase` says.
        `state_ids` overrides the stream's `(flows, T, P)` ids (a column stage, §4.4.6)."""
        entry = self.dormant_entry(item_id, stream, None if state_ids is None else state_ids[0])
        moles = self.moles_builder(stream) if state_ids is None else _sum_builder(state_ids[0])
        mass = self.mass_builder(stream) if state_ids is None else self._mass_of(state_ids[0])
        if entry.choice == "dormant":
            return StreamFlow(stream, True, None, mass, moles), entry
        if declared_v is not None:
            return StreamFlow(stream, False, None, mass, moles, declared_v), entry
        key = (stream, phase)
        if key not in self._flows:
            self._flows[key] = self._new_flow(
                item_id, stream, phase, target, mass, moles, state_ids
            )
        return self._flows[key], entry

    def _mass_of(self, ids: Sequence[str]) -> FunctionalBuilder:
        masses = self.ctx.view.molar_masses()
        terms = tuple(zip((masses[c] for c in self.ctx.view.components), ids, strict=True))

        def build(s: Symbols, a: Algebra) -> Expr:
            total: Expr = terms[0][0] * s.x(terms[0][1])
            for mass, name in terms[1:]:
                total = total + mass * s.x(name)
            return total

        return build

    def _new_flow(
        self,
        item_id: str,
        stream: str,
        phase: Phase,
        target: str,
        mass: FunctionalBuilder,
        moles: FunctionalBuilder,
        state_ids: tuple[Sequence[str], str, str] | None,
    ) -> StreamFlow | Refusal:
        view = self.ctx.view
        block_id = volumetric_block_id(len(self._blocks) + 1)
        if state_ids is None and vapor_id(stream) in self.variables:
            reason = saturated_volume_available(
                view.provider, view.context, self.x(pressure_id(stream))
            )
            if reason is not None:
                return Refusal("SIZING_INPUT_UNAVAILABLE", f"{item_id}.v_sat", reason)
            sat_block = SaturatedVolumetricFlowBlock(view.provider, view.context, block_id=block_id)
            inputs = (vapor_id(stream), liquid_id(stream), pressure_id(stream))
            self._blocks.append((sat_block, inputs))
            return StreamFlow(stream, False, block_id, mass, moles)
        if state_ids is None:
            flows = tuple(flow_id(stream, c) for c in view.components)
            t_id, p_id = temperature_id(stream), pressure_id(stream)
        else:
            flows, t_id, p_id = tuple(state_ids[0]), state_ids[1], state_ids[2]
        reason = volume_available(
            view.provider,
            view.context,
            phase,
            [self.x(name) for name in flows],
            self.x(t_id),
            self.x(p_id),
        )
        if reason is not None:
            return Refusal("SIZING_INPUT_UNAVAILABLE", f"{item_id}.{target}", reason)
        block = VolumetricFlowBlock(view.provider, view.context, phase, block_id=block_id)
        self._blocks.append((block, (*flows, t_id, p_id)))
        return StreamFlow(stream, False, block_id, mass, moles)

    @property
    def blocks(self) -> tuple[tuple[PropertyBlock, tuple[str, ...]], ...]:
        return tuple(self._blocks)

    # -- float evaluation for the selection pass -------------------------------------------------

    def values(self, outputs: Sequence[OutputDef], theta: Sequence[Theta] = ()) -> dict[str, float]:
        """`ctx.evaluate` with every block registered so far (§4.3.2's float pass)."""
        return self.ctx.evaluate(self.state, outputs, theta, self.blocks)


def _sum_builder(ids: Sequence[str]) -> FunctionalBuilder:
    names = tuple(ids)

    def build(s: Symbols, a: Algebra) -> Expr:
        total: Expr = s.x(names[0])
        for name in names[1:]:
            total = total + s.x(name)
        return total

    return build


def nominal(value: float) -> float:
    """§4.3.1: the absolute value of a row's leading quantity at the selection state; a zero one
    is replaced by 1 (none of the sizing rows leads with a host variable that has a K03
    nominal)."""
    magnitude = abs(float(value))
    return magnitude if magnitude > 0.0 and math.isfinite(magnitude) else 1.0


def size_output(item_id: str, quantity: str) -> str:
    if quantity not in SIZE_QUANTITIES:
        raise ValueError(f"{quantity!r} is not a sizing quantity of §4.1")
    return f"size.{item_id}.{quantity}"


def argmax_rows(
    members: Sequence[tuple[str, FunctionalBuilder]], chosen: str, values: Mapping[str, float]
) -> tuple[AdmissibilityRow, ...]:
    """`f_{j*} − f_j ≥ 0` for every member j ≠ j* (§4.3.1, the squared forms of §4.4)."""
    lead = dict(members)[chosen]
    scale = nominal(values[chosen])

    def row(other: FunctionalBuilder) -> FunctionalBuilder:
        return lambda s, a: lead(s, a) - other(s, a)

    return tuple(
        AdmissibilityRow(f"over_{name}", row(build), scale)
        for name, build in members
        if name != chosen
    )


class Family(Protocol):
    """One unit family: the items of a unit (§4.4.0)."""

    name: str

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan: ...


FAMILIES: dict[str, Family] = {}


def register_family(model_id: str, family: Family) -> None:
    """Register `family` as the sizing of host model `model_id` (the extension point, §4.4.0)."""
    FAMILIES[model_id] = family


def family_of(model_id: str) -> Family | None:
    _load_builtin()
    return FAMILIES.get(model_id)


_LOADED: list[bool] = []


def _load_builtin() -> None:
    if not _LOADED:
        from openflowsheet.assessment.sizing import families  # noqa: F401, PLC0415

        _LOADED.append(True)


def plan_sizing(
    ctx: BuildContext,
    state: Mapping[str, float],
    *,
    families: Mapping[str, Family] | None = None,
) -> tuple[SizingPlan, SizingContext]:
    """Every unit's items, in the host's unit declaration order (§4.2.4 step 1).

    A unit whose model id no family covers is refused `NO_SIZING_MODEL(<U>)` unless its item
    carries a `quote` or `exclude` (the cost contributor reads those, §4.4.0)."""
    _load_builtin()
    table = FAMILIES if families is None else families
    sctx = SizingContext(ctx, state)
    plan = SizingPlan()
    for unit in ctx.view.units():
        family = table.get(unit.model_id)
        if family is None:
            doc = sctx.item(unit.unit_id)
            if "quote" in doc or "exclude" in doc:
                continue
            plan = plan.merged(
                SizingPlan(
                    refusals=(Refusal("NO_SIZING_MODEL", unit.unit_id, unit.model_id),),
                )
            )
            continue
        plan = plan.merged(family.plan(sctx, unit))
    return SizingPlan(
        items=plan.items,
        outputs=plan.outputs,
        theta=plan.theta,
        blocks=sctx.blocks,
        regime_entries=plan.regime_entries,
        refusals=plan.refusals,
        limitations=plan.limitations,
        no_equipment=plan.no_equipment,
    ), sctx


#: Reused by the families: an item's id for a unit's sub-item (`<U>.drum`, `<U>.drive`, …).
def sub_item(unit_id: str, suffix: str | None) -> str:
    return unit_id if suffix is None else f"{unit_id}.{suffix}"


#: `(symbols, algebra) -> constant` builder.
def constant(value: float) -> FunctionalBuilder:
    return lambda s, a: value
