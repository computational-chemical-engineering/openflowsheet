"""The verifier's zero-flow form of a dormant lifted split (T05b spec §7.2, §9.3; ADR 0012 D7).

At a state where a lifted split carries nothing in either phase (`V = L = 0`, the branch found
`ZERO_FLOW`, ADR 0012 D6) the declaration's own Jacobian is singular: the split's equilibrium rows
are bilinear in lifted flows that are all zero, so they vanish identically (T05 A28's rank 15 of
18). That is a property of the lifted formulation at zero flow, not of the problem. The verifier's
regularity screen (K04 §7) therefore judges such a root on the **zero-flow form** of spec §7.2,
square by construction:

| style | columns removed (pinned at `+0.0`) | rows dropped |
| --- | --- | --- |
| heater | `S.vap.<c>`, `S.liq.<c>`, `S.V`, `S.L` | equilibrium, `split:<c>`, `Vdef`, `Ldef` |
| products | `S_V.n.<c>`, `S_L.n.<c>`, `S_V.N`, `S_L.N` | equilibrium, `<EQ>-mole:<c>`, `Ndef:*` |
| PH-type, also | — | its energy row, replaced by the **label row** `T_out − T_label` |

The label row, `<U>:zero-flow-label`, is never a row of the compiled declaration (spec §7.2): it
exists here and in the attempt's system (W7), each built by its own code. It has kind
`temperature`; its derivative is exact (`+1` at `T_out`, the split's temperature column; `−1` at
`T_label`, the unit's inlet stream temperature).

**R-016.** Everything here is read from the declarations — the split descriptor (`LiftedSplit`, as
the table reads it), the revision's view (model ids, ports, pins) and the id helpers — and none of
it from the solver: no row builder, kernel, causal evaluator or the solver's own zero-flow regime.
`tests/test_t05_table_independence.py` pins this module's imports with the table's rule.

The choice of matrix is made from the state alone (spec §9.3), so it applies whichever phase
contract solved the root: a v1 solve of a dormant PH-type outlet converges in its `TWO_PHASE`
form and is judged here. A split is reduced only when its feed is exactly dormant too (§9.3 as
ruled, finding F9): a flowing feed with `V = L = 0` is judged as a flowing split.

**Dormant non-lifted outlets** (spec §7.6–§7.7, §9.3; ADR 0012 D12). The pump's outlet, the K02
mixer's, and an exchanger side whose outlet temperature is not the specification are, at exact
dormancy of every stream of their trigger port, read by no declared row but their unit's energy
row, whose `T_out` coefficient is then zero. Such an outlet is reduced in the same matrix: its
energy row out, its label row `T_out − T_label` in (`T_label` the first trigger stream's
temperature, in connection order), no column removed. `DORMANT_OUTLETS` is this module's own
transcription of spec §7.6's table; the exchanger's specification is read from which column the
revision pins, as the table's `_exchanger_specification` reads it. Nothing is imported from the
solver's registry (`orchestrator.splits.DORMANCY_RULES`); `tests/test_t05_table_independence.py`
compares the two as data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from openflowsheet.models import duty_id, flow_id, row_id, temperature_id
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionView

if TYPE_CHECKING:
    from openflowsheet.orchestrator.region import LiftedSplit

__all__ = [
    "DORMANT_OUTLETS",
    "LABEL_FAMILY",
    "PH_TYPE_ENERGY_ROWS",
    "DormantOutlet",
    "ZeroFlowSplit",
    "dormant_outlets",
    "zero_flow_splits",
]

#: The label row's family: `<U>:zero-flow-label` (spec §7.2).
LABEL_FAMILY: Final = "zero-flow-label"

#: Spec §6.1: the models whose energy row fixes their split's temperature, and that row's family.
#: The conversion reactor is PH-type only with its duty specified (its duty pinned in the
#: revision); with its outlet temperature specified it is TP-type.
PH_TYPE_ENERGY_ROWS: Final[Mapping[str, str]] = {
    "syn001.valve": "VLV-energy",
    "syn001.ph_flash": "PHF-duty",
    "syn001.conversion_reactor": "RX-duty",
}

#: Spec §7.2: the family of a products-style split's per-component mole rows, by model.
PRODUCT_MOLE_ROWS: Final[Mapping[str, str]] = {
    "syn001.tp_flash": "FLASH-mole",
    "syn001.ph_flash": "PHF-mole",
    "c1.tp_flash": "C1FL-mole",
}


@dataclass(frozen=True)
class ZeroFlowSplit:
    """One `ZERO_FLOW` split's reduction: what leaves the matrix, and its label if PH-type; also a
    dormant non-lifted outlet's (no column, its energy row, its label)."""

    unit: str
    #: The split's lifted flows and totals, removed as columns.
    columns: tuple[str, ...]
    #: The rows the zero-flow form drops (for a PH-type split, its energy row too).
    rows: tuple[str, ...]
    #: `(row id, T_out, T_label)` for a PH-type split; `None` for a TP-type one.
    label: tuple[str, str, str] | None


def _products(instance: InstanceView) -> bool:
    """A products-style split writes into two product ports; a heater-style one lifts its outlet."""
    return "vapor" in instance.ports and "liquid" in instance.ports


def _ph_type(instance: InstanceView) -> bool:
    if instance.model_id not in PH_TYPE_ENERGY_ROWS:
        return False
    if instance.model_id == "syn001.conversion_reactor":
        return duty_id(instance.unit_id) in instance.pins
    return True


def _reduction(
    split: LiftedSplit, instance: InstanceView, components: Sequence[str]
) -> ZeroFlowSplit:
    unit = split.unit
    if _products(instance):
        family = PRODUCT_MOLE_ROWS.get(instance.model_id)
        if family is None:
            raise ValueError(f"zero_flow_form_unknown({instance.model_id})")
        split_rows = tuple(row_id(unit, family, c) for c in components)
    else:
        split_rows = tuple(row_id(unit, "split", c) for c in components)
    rows: tuple[str, ...] = (
        *split.equilibrium_rows,
        *split_rows,
        split.vapor_definition,
        split.liquid_definition,
    )
    label: tuple[str, str, str] | None = None
    if _ph_type(instance):
        rows = (*rows, row_id(unit, PH_TYPE_ENERGY_ROWS[instance.model_id]))
        (inlet,) = instance.ports["inlet"]
        label = (row_id(unit, LABEL_FAMILY), split.temperature, temperature_id(inlet))
    return ZeroFlowSplit(
        unit=unit,
        columns=(*split.vapor, *split.liquid, split.vapor_total, split.liquid_total),
        rows=rows,
        label=label,
    )


def zero_flow_splits(
    view: RevisionView, splits: Sequence[LiftedSplit], state: Mapping[str, float]
) -> tuple[ZeroFlowSplit, ...]:
    """The reduction of every split whose branch at `state` is `ZERO_FLOW` (`V = L = 0`, read
    from the state's own totals) and whose feed is exactly dormant, in the splits' order."""
    instances = {instance.unit_id: instance for instance in view.instances}
    return tuple(
        _reduction(split, instances[split.unit], view.components)
        for split in splits
        if state[split.vapor_total] == 0.0
        and state[split.liquid_total] == 0.0
        and all(state[name] == 0.0 for name in split.feed)
    )


@dataclass(frozen=True)
class DormantOutlet:
    """One row of spec §7.6's table, as the verifier reads it."""

    #: The outlet whose temperature the label row fixes.
    outlet: str
    #: The port whose every stream must be exactly dormant; its first stream is the label source.
    trigger: str
    #: The family of the energy row the form swaps out, `<U>:<swapped>`.
    swapped: str
    #: `None`: `<U>:zero-flow-label`; else `<U>:zero-flow-label:<side>`.
    side: str | None
    #: The exchanger specification under which this side has no form (its outlet temperature is
    #: the specification's); `None` for a model with one configuration.
    unless: str | None = None


#: Spec §7.6, transcribed: by model id, the dormancy-form outlets in signature order.
DORMANT_OUTLETS: Final[Mapping[str, tuple[DormantOutlet, ...]]] = {
    "syn001.liquid_pump": (DormantOutlet("outlet", "inlet", "PUMP-energy", None),),
    "syn001.adiabatic_mixer": (DormantOutlet("outlet", "inlet", "MIX-energy", None),),
    # M02 design note §14.2 B13: the C1 mixer's vapour outlet.
    "c1.adiabatic_mixer": (DormantOutlet("outlet", "inlet", "C1MIX-energy", None),),
    "syn001.heat_exchanger": (
        DormantOutlet("hot_outlet", "hot_inlet", "HX-energy-hot", "hot", "hot_outlet_temperature"),
        DormantOutlet(
            "cold_outlet", "cold_inlet", "HX-energy-cold", "cold", "cold_outlet_temperature"
        ),
    ),
}


def exchanger_specification(instance: InstanceView) -> str:
    """The exchanger's specification, by the column its revision pins (as the table's
    `_exchanger_specification`): `hot_outlet_temperature`, `cold_outlet_temperature` or `duty`.
    Raises `ValueError` when it pins none or more than one."""
    (hot,) = instance.ports["hot_outlet"]
    (cold,) = instance.ports["cold_outlet"]
    modes = {
        temperature_id(hot): "hot_outlet_temperature",
        temperature_id(cold): "cold_outlet_temperature",
        duty_id(instance.unit_id): "duty",
    }
    pinned = [mode for column, mode in modes.items() if column in instance.pins]
    if len(pinned) != 1:
        raise ValueError(f"exchanger_specification({instance.unit_id}): pins {pinned}")
    return pinned[0]


def dormant_outlets(view: RevisionView, state: Mapping[str, float]) -> tuple[ZeroFlowSplit, ...]:
    """The reduction of every dormancy-form outlet whose trigger streams are all exactly dormant
    at `state`, in declaration order (the exchanger's hot side before its cold side): its energy
    row out, its label row in, no column removed."""
    found: list[ZeroFlowSplit] = []
    for instance in view.instances:
        outlets = DORMANT_OUTLETS.get(instance.model_id, ())
        specification = (
            exchanger_specification(instance)
            if instance.model_id == "syn001.heat_exchanger"
            else None
        )
        for entry in outlets:
            if entry.unless is not None and entry.unless == specification:
                continue
            triggers = tuple(instance.ports.get(entry.trigger, ()))
            if not triggers or not all(
                state[flow_id(stream, component)] == 0.0
                for stream in triggers
                for component in view.components
            ):
                continue
            (outlet,) = instance.ports[entry.outlet]
            unit = instance.unit_id
            label_row = (
                row_id(unit, LABEL_FAMILY)
                if entry.side is None
                else row_id(unit, LABEL_FAMILY, entry.side)
            )
            found.append(
                ZeroFlowSplit(
                    unit=unit,
                    columns=(),
                    rows=(row_id(unit, entry.swapped),),
                    label=(label_row, temperature_id(outlet), temperature_id(triggers[0])),
                )
            )
    return tuple(found)
