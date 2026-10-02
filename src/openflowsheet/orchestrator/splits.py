"""Lifted-split discovery by model id, for revision-built flowsheets. T05 design note §3.

A region solves a lifted phase split as variables, and the phase policy of T02 §6.3 has to know,
per lifted unit, which variables carry the split and which rows define it: a `LiftedSplit`
descriptor. SYN-001 names its two by hand (`region.syn001_lifted_splits`, which stays as it is and
stays SYN-001's). A flowsheet assembled from a revision cannot, so the descriptors are *derived*
here from each instance's model id and wiring through one registered rule per model (register
R-046; rejected: a `lifted_splits()` member on every unit, because the K02 units are not edited).

**Two styles.** A heater-style unit lifts the split of its own outlet (`outlet`): the split
variables are named after the outlet stream. A flash-style unit writes the split into its two
product streams (`products`): the split variables are the products' flows. One rule per model is
what makes R-039's "at most one lifted split per unit" structural rather than checked.

**Drift is closed by structure, not by a second naming site.** A rule names rows a unit authors;
if the unit and the rule disagree, `check_agreement` (§3.3) says so from the assembled
declaration: the units with `molar_flow_squared` rows must be exactly the units with a descriptor,
and every id a descriptor names must be a row or column the declaration actually has.

**Closure type** (T05b spec §6.1, ADR 0012 D3). A lifted split is *PH-type* when its unit's
energy row fixes its temperature — the valve, the PH flash, the reactor with `energy_specification
= duty` — and *TP-type* otherwise. The rule declares it per model, and for the reactor by its
configuration; `closure_types` reads it off a flowsheet's units. Only the phase contract
`T05b-phase-contract-v2` reads it (spec §6.2): under v1 every split is answered by the TP flash.

**The `ZERO_FLOW` form's ids** (T05b spec §6.1, §7.2; ADR 0012 D4 (c)). The rule also names the
family of a split's split rows (`<U>:split:<c>` heater style; `<U>:<EQ>-mole:<c>` products style)
and, for a model that can be PH-type, its energy row (`VLV-energy`, `PHF-duty`, `RX-duty`); the
label source is the unit's inlet stream temperature. `zero_flow_forms` builds each split's
`ZeroFlowForm` from them and a flowsheet's closure types, and `check_agreement` checks them
against the declaration like the rest: every id a row its unit authored, the energy row reading
the split's temperature, the label source a column. Only v2's region reads a form.

**Dormancy-form outlets** (T05b spec §7.6; ADR 0012 D12; register R-058). A unit with no lifted
split can still have an outlet whose temperature, at exact dormancy, no declared row reads: the
pump's outlet, the K02 mixer's with every inlet dormant, an exchanger side whose outlet
temperature is not the specification. `DORMANCY_RULES`, beside `SPLIT_RULES` and keyed by model id
and — for the exchanger — its `specification`, names each: the outlet port, the trigger port, the
swapped energy row's family and the label row's. `dormancy_forms` builds each instance's
`DormancyForm`; `check_agreement` (g) checks them against the declaration. Only v2's region reads
a form.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import PhaseSignature
from openflowsheet.graph.trace import Declaration
from openflowsheet.models import Wiring, flow_id, pressure_id, row_id, temperature_id
from openflowsheet.models.syn001.flash import total_flow_id
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.orchestrator.region import (
    ClosureType,
    DormancyForm,
    LiftedSplit,
    ZeroFlowForm,
)

if TYPE_CHECKING:
    from openflowsheet.models import UnitModel

__all__ = [
    "DORMANCY_RULES",
    "SPLIT_RULES",
    "DormancyRule",
    "SplitRule",
    "SplitStyle",
    "check_agreement",
    "closure_types",
    "dormancy_forms",
    "lifted_splits",
    "split_temperatures",
    "zero_flow_forms",
]

#: `outlet`: a heater-style lifted outlet; `products`: a flash-style pair of product streams.
SplitStyle = Literal["outlet", "products"]

#: The reactor's configuration that makes its split PH-type (T05b spec §6.1): its energy row is
#: `RX-duty`, which reads the outlet temperature; `outlet_temperature`'s `RX-spec` fixes it.
_PH_ENERGY_SPECIFICATION: Final = "duty"

#: T05b spec §7.2: the label row's family, `<U>:zero-flow-label`, and the port whose (one) stream's
#: temperature is the label — T05 §4.7 (a)'s, which the causal evaluators return.
LABEL_FAMILY: Final = "zero-flow-label"
_LABEL_PORT: Final = "inlet"


@dataclass(frozen=True)
class SplitRule:
    """How one model's lifted split is read from an instance's id and wiring."""

    style: SplitStyle
    #: The equation family of its equilibrium rows (`row_id(unit, family, component)`).
    equilibrium: str
    #: T05b spec §6.1: `PH` or `TP`; `None` when the instance's configuration decides (the
    #: reactor: PH-type iff `energy_specification` is `duty`).
    closure: ClosureType | None
    #: T05b spec §6.1, §7.2: the family of the split rows a `ZERO_FLOW` form drops —
    #: `split` (`<U>:split:<c>`, heater style) or the products' `<EQ>-mole` (products style).
    split_rows: str
    #: T05b spec §6.1: the energy row a PH-type split's form swaps for its label row; `None` for
    #: a model that is never PH-type.
    energy: str | None


#: One rule per model id (§3.1). The T05 models need only their ids here; no model class is read.
SPLIT_RULES: Final[Mapping[str, SplitRule]] = {
    "syn001.tp_heater": SplitRule("outlet", "HEAT-equilibrium", "TP", "split", None),
    "syn001.tp_flash": SplitRule("products", "FLASH-equilibrium", "TP", "FLASH-mole", None),
    "syn001.valve": SplitRule("outlet", "VLV-equilibrium", "PH", "split", "VLV-energy"),
    "syn001.conversion_reactor": SplitRule("outlet", "RX-equilibrium", None, "split", "RX-duty"),
    "syn001.ph_flash": SplitRule("products", "PHF-equilibrium", "PH", "PHF-mole", "PHF-duty"),
}


@dataclass(frozen=True)
class DormancyRule:
    """One dormancy-form outlet of a model (T05b spec §7.6's table, one row)."""

    #: The outlet whose temperature the label row fixes; the item key is `<U>.<outlet>`.
    outlet: str
    #: The port whose every stream must be exactly dormant; its first stream, in connection
    #: order, is the label source (the causal evaluator's label).
    trigger: str
    #: The family of the swapped row, `<U>:<swapped>`.
    swapped: str
    #: The label row's side suffix: `<U>:zero-flow-label` when `None`, else
    #: `<U>:zero-flow-label:<side>`.
    side: str | None
    #: The outlet's declared phase: `LIQUID`, or the configuration attribute that holds it
    #: (`hot_phase`, `cold_phase`).
    declared_phase: str


#: The exchanger's configuration attribute the registry is keyed by (spec §7.6).
_CONFIGURED_BY: Final[Mapping[str, str]] = {"syn001.heat_exchanger": "specification"}

_PUMP_OUTLET: Final = DormancyRule("outlet", "inlet", "PUMP-energy", None, "LIQUID")
_MIXER_OUTLET: Final = DormancyRule("outlet", "inlet", "MIX-energy", None, "LIQUID")
_HOT_SIDE: Final = DormancyRule("hot_outlet", "hot_inlet", "HX-energy-hot", "hot", "hot_phase")
_COLD_SIDE: Final = DormancyRule(
    "cold_outlet", "cold_inlet", "HX-energy-cold", "cold", "cold_phase"
)

#: Spec §7.6 (`ref.dormancy_forms`): `(model id, configuration)` → its dormancy-form outlets, in
#: signature order (the exchanger's hot side before its cold side). The configuration is `None`
#: for a model the registry does not key by one. A temperature-specified exchanger side has no
#: form: its outlet temperature is read by `HX-spec`.
DORMANCY_RULES: Final[Mapping[tuple[str, str | None], tuple[DormancyRule, ...]]] = {
    ("syn001.liquid_pump", None): (_PUMP_OUTLET,),
    ("syn001.adiabatic_mixer", None): (_MIXER_OUTLET,),
    ("syn001.heat_exchanger", "duty"): (_HOT_SIDE, _COLD_SIDE),
    ("syn001.heat_exchanger", "hot_outlet_temperature"): (_COLD_SIDE,),
    ("syn001.heat_exchanger", "cold_outlet_temperature"): (_HOT_SIDE,),
}
_DORMANCY_MODELS: Final = frozenset(model for model, _ in DORMANCY_RULES)


def _dormancy_rules(unit: UnitModel) -> tuple[DormancyRule, ...]:
    """The registry's rules for one unit, by its model id and configuration; `()` for a model
    outside the registry. Raises `ValueError` — a defect — for a registered model whose instance
    carries a configuration the registry does not know."""
    if unit.model_id not in _DORMANCY_MODELS:
        return ()
    attribute = _CONFIGURED_BY.get(unit.model_id)
    configuration = None if attribute is None else getattr(unit, attribute, None)
    rules = DORMANCY_RULES.get((unit.model_id, configuration))
    if rules is None:
        raise ValueError(
            f"dormancy_form_configuration_unknown({unit.unit_id}): {attribute} {configuration!r}"
        )
    return rules


def dormancy_forms(
    instances: Sequence[tuple[str, str, Wiring]],
    units: Sequence[UnitModel],
    components: Sequence[str],
) -> tuple[DormancyForm, ...]:
    """T05b spec §7.6–§7.7: every dormancy-form outlet's `DormancyForm`, in declaration order of
    `units` and, within a unit, in its rules' order.

    A port the rule names but the instance does not wire yields a form without its streams, which
    `check_agreement` (g) refuses; nothing here raises for it."""
    wirings = {unit: wiring for unit, _, wiring in instances}
    forms: list[DormancyForm] = []
    for unit in units:
        for rule in _dormancy_rules(unit):
            wiring = wirings[unit.unit_id]
            outlets = tuple(wiring.streams.get(rule.outlet, ()))
            triggers = tuple(wiring.streams.get(rule.trigger, ()))
            outlet = outlets[0] if len(outlets) == 1 else ""
            declared: PhaseSignature = (
                "LIQUID" if rule.declared_phase == "LIQUID" else getattr(unit, rule.declared_phase)
            )
            label_row = (
                row_id(unit.unit_id, LABEL_FAMILY)
                if rule.side is None
                else row_id(unit.unit_id, LABEL_FAMILY, rule.side)
            )
            forms.append(
                DormancyForm(
                    item=f"{unit.unit_id}.{rule.outlet}",
                    unit=unit.unit_id,
                    outlet_port=rule.outlet,
                    trigger_port=rule.trigger,
                    outlet=outlet,
                    triggers=triggers,
                    trigger_flows=tuple(
                        flow_id(stream, c) for stream in triggers for c in components
                    ),
                    balance=tuple(
                        (flow_id(outlet, c), tuple(flow_id(stream, c) for stream in triggers))
                        for c in components
                    ),
                    swapped=row_id(unit.unit_id, rule.swapped),
                    label=(
                        label_row,
                        temperature_id(outlet) if outlet else "",
                        temperature_id(triggers[0]) if triggers else "",
                    ),
                    declared=declared,
                )
            )
    return tuple(forms)


def closure_types(units: Sequence[UnitModel]) -> dict[str, ClosureType]:
    """T05b spec §6.1: the closure type of every unit with a lifted split, by unit id.

    Raises `ValueError` — a defect — when a configuration-typed model's instance carries no
    `energy_specification` this rule knows."""
    found: dict[str, ClosureType] = {}
    for unit in units:
        rule = SPLIT_RULES.get(unit.model_id)
        if rule is None:
            continue
        if rule.closure is not None:
            found[unit.unit_id] = rule.closure
            continue
        specification = getattr(unit, "energy_specification", None)
        if specification not in (_PH_ENERGY_SPECIFICATION, "outlet_temperature"):
            raise ValueError(
                f"closure_type_unknown({unit.unit_id}): energy_specification {specification!r}"
            )
        found[unit.unit_id] = "PH" if specification == _PH_ENERGY_SPECIFICATION else "TP"
    return found


def _descriptor(
    unit: str, rule: SplitRule, wiring: Wiring, components: Sequence[str]
) -> LiftedSplit:
    equilibrium_rows = tuple(row_id(unit, rule.equilibrium, c) for c in components)
    if rule.style == "outlet":
        stream = wiring.one("outlet")
        return LiftedSplit(
            unit=unit,
            stream=stream,
            feed=tuple(flow_id(stream, c) for c in components),
            temperature=temperature_id(stream),
            pressure=pressure_id(stream),
            vapor=tuple(vapor_flow_id(stream, c) for c in components),
            liquid=tuple(liquid_flow_id(stream, c) for c in components),
            vapor_total=vapor_total_id(stream),
            liquid_total=liquid_total_id(stream),
            equilibrium_rows=equilibrium_rows,
            vapor_definition=row_id(unit, "Vdef"),
            liquid_definition=row_id(unit, "Ldef"),
        )
    inlet, vapor, liquid = wiring.one("inlet"), wiring.one("vapor"), wiring.one("liquid")
    return LiftedSplit(
        unit=unit,
        stream=inlet,
        feed=tuple(flow_id(inlet, c) for c in components),
        temperature=temperature_id(vapor),
        pressure=pressure_id(vapor),
        vapor=tuple(flow_id(vapor, c) for c in components),
        liquid=tuple(flow_id(liquid, c) for c in components),
        vapor_total=total_flow_id(vapor),
        liquid_total=total_flow_id(liquid),
        equilibrium_rows=equilibrium_rows,
        vapor_definition=row_id(unit, "Ndef", "vapor"),
        liquid_definition=row_id(unit, "Ndef", "liquid"),
    )


def lifted_splits(
    instances: Sequence[tuple[str, str, Wiring]], components: Sequence[str]
) -> tuple[LiftedSplit, ...]:
    """One descriptor per `(unit id, model id, wiring)` whose model has a rule, in the order given.

    The order given is the flowsheet's declaration order, which is the order the region's phase
    policy visits the splits in. An instance whose model has no rule contributes nothing here;
    whether it *should* have had one is `check_agreement`'s question, answered from its rows.
    """
    return tuple(
        _descriptor(unit, SPLIT_RULES[model], wiring, components)
        for unit, model, wiring in instances
        if model in SPLIT_RULES
    )


def split_temperatures(
    instances: Sequence[tuple[str, str, Wiring]], splits: Sequence[LiftedSplit]
) -> dict[str, tuple[str, ...]]:
    """T05b spec §6.2 step 3 as amended (Q-S11 (a)): every temperature column of each split's
    streams, by unit id — heater style its outlet's; products style the vapour product's (the
    descriptor's `temperature`, which the label row reads), then the liquid product's (which the
    unit's copy row equates to it). An opening that takes a PH closure's answer sets each of them
    to the closure's `T`. Kept beside the descriptor, as `zero_flow_forms`, so `LiftedSplit`'s
    registered `repr` digest does not move."""
    models = {unit: (model, wiring) for unit, model, wiring in instances}
    found: dict[str, tuple[str, ...]] = {}
    for split in splits:
        model, wiring = models[split.unit]
        if SPLIT_RULES[model].style == "products":
            found[split.unit] = (split.temperature, temperature_id(wiring.one("liquid")))
        else:
            found[split.unit] = (split.temperature,)
    return found


def zero_flow_forms(
    instances: Sequence[tuple[str, str, Wiring]],
    splits: Sequence[LiftedSplit],
    types: Mapping[str, ClosureType],
    components: Sequence[str],
) -> dict[str, ZeroFlowForm]:
    """T05b spec §7.2: each split's `ZERO_FLOW` form, by unit id, from its rule's ids.

    `types` is `closure_types`' answer; a unit it omits is TP-type (the region's default). Raises
    `ValueError` — a defect — for a PH-type unit whose model's rule names no energy row."""
    models = {unit: (model, wiring) for unit, model, wiring in instances}
    forms: dict[str, ZeroFlowForm] = {}
    for split in splits:
        model, wiring = models[split.unit]
        rule = SPLIT_RULES[model]
        rows = (
            *split.equilibrium_rows,
            *(row_id(split.unit, rule.split_rows, c) for c in components),
            split.vapor_definition,
            split.liquid_definition,
        )
        columns = (*split.vapor, *split.liquid, split.vapor_total, split.liquid_total)
        if types.get(split.unit, "TP") == "TP":
            forms[split.unit] = ZeroFlowForm(split.unit, columns, rows)
            continue
        if rule.energy is None:
            raise ValueError(f"zero_flow_form_without_energy_row({split.unit}): {model}")
        energy = row_id(split.unit, rule.energy)
        label = (
            row_id(split.unit, LABEL_FAMILY),
            split.temperature,
            temperature_id(wiring.one(_LABEL_PORT)),
        )
        forms[split.unit] = ZeroFlowForm(split.unit, columns, (*rows, energy), energy, label)
    return forms


def check_agreement(
    instances: Sequence[tuple[str, str, Wiring]],
    splits: Sequence[LiftedSplit],
    spec: ProblemSpec,
    row_units: Mapping[str, str],
    declaration: Declaration,
    forms: Mapping[str, ZeroFlowForm] | None = None,
    dormancy: Sequence[DormancyForm] | None = None,
) -> None:
    """§3.3: the registry and the rows the units authored describe the same splits.

    Raises `ValueError` — a defect, never a typed refusal: a registered model whose rows disagree
    with its rule is a bug in the model or the registry, not a property of a revision. The checks,
    in order: (a) the units with `molar_flow_squared` rows are exactly the units with a
    descriptor; (b) a descriptor's equilibrium rows are its unit's `molar_flow_squared` rows, in
    `equation_ids` order; (c) every variable a descriptor names is a column of the spec; (d) each
    phase-total definition row reads exactly that phase's flows and its total; (e) each
    equilibrium row reads its component's vapour and liquid flows and both totals.

    With `forms` (T05b spec §6.1), also: (f) every row a form drops is a row its unit authored,
    the swapped energy row among them and reading the split's temperature, and the label row's
    two columns are columns of the spec (`zero_flow_form_disagrees(<unit>, …)`).

    With `dormancy` (T05b spec §7.6), also: (g) each dormancy form's outlet port carries exactly
    its outlet stream and its trigger port exactly its trigger streams (at least one), its label
    reads the outlet's temperature and the first trigger stream's, every column it names is a
    column of the spec, and its swapped row is a row its unit authored that reads the outlet's
    temperature (`dormancy_form_disagrees(<item>, …)`).
    """
    models = {unit: model for unit, model, _ in instances}
    squared: dict[str, list[str]] = {}
    for row in spec.equation_ids:
        if spec.row_kinds.get(row) == "molar_flow_squared":
            squared.setdefault(row_units[row], []).append(row)

    described = {split.unit for split in splits}
    for unit in squared:
        if unit not in described:
            raise ValueError(f"lifted_split_unregistered({models.get(unit, unit)})")
    for split in splits:
        if split.unit not in squared:
            raise ValueError(f"lifted_split_without_rows({split.unit})")

    columns = set(spec.variable_ids)
    for split in splits:
        if split.equilibrium_rows != tuple(squared[split.unit]):
            raise ValueError(
                f"lifted_split_rows_disagree({split.unit}): the rule names "
                f"{list(split.equilibrium_rows)}, the unit authors {squared[split.unit]}"
            )
        named = (
            *split.feed,
            split.temperature,
            split.pressure,
            *split.vapor,
            *split.liquid,
            split.vapor_total,
            split.liquid_total,
        )
        absent = [name for name in named if name not in columns]
        if absent:
            raise ValueError(f"lifted_split_variables_absent({split.unit}): {absent}")
        for definition, flows, total in (
            (split.vapor_definition, split.vapor, split.vapor_total),
            (split.liquid_definition, split.liquid, split.liquid_total),
        ):
            traced = declaration.rows.get(definition)
            if traced is None or set(traced.columns) != {*flows, total}:
                raise ValueError(
                    f"lifted_split_definition_disagrees({split.unit}, {definition}): reads "
                    f"{None if traced is None else list(traced.columns)}, the rule names "
                    f"{[*flows, total]}"
                )
        totals = {split.vapor_total, split.liquid_total}
        for equilibrium, vapor, liquid in zip(
            split.equilibrium_rows, split.vapor, split.liquid, strict=True
        ):
            read = set(declaration.rows[equilibrium].columns)
            if not {vapor, liquid, *totals} <= read:
                raise ValueError(
                    f"lifted_split_equilibrium_disagrees({split.unit}, {equilibrium}): does not "
                    f"read {sorted({vapor, liquid, *totals} - read)}"
                )
    for split in splits if forms is not None else ():
        assert forms is not None
        form = forms.get(split.unit)
        if form is None:
            raise ValueError(f"zero_flow_form_disagrees({split.unit}): no form")
        foreign = [row for row in form.rows if row_units.get(row) != split.unit]
        if foreign:
            raise ValueError(
                f"zero_flow_form_disagrees({split.unit}): not rows the unit authored: {foreign}"
            )
        if form.label is None:
            continue
        _, outlet, source = form.label
        if outlet != split.temperature or source not in columns:
            raise ValueError(
                f"zero_flow_form_disagrees({split.unit}): the label reads {outlet} and {source}"
            )
        swapped = declaration.rows.get(form.swapped)
        if swapped is None or split.temperature not in swapped.columns:
            raise ValueError(
                f"zero_flow_form_disagrees({split.unit}, {form.swapped}): does not read "
                f"{split.temperature}"
            )
    wirings = {unit: wiring for unit, _, wiring in instances}
    for dormant in dormancy or ():
        _check_dormancy_form(dormant, wirings, columns, row_units, declaration)


def _check_dormancy_form(
    form: DormancyForm,
    wirings: Mapping[str, Wiring],
    columns: set[str],
    row_units: Mapping[str, str],
    declaration: Declaration,
) -> None:
    """`check_agreement` (g) for one form."""
    wiring = wirings.get(form.unit)
    connected = {} if wiring is None else wiring.streams
    outlets = tuple(connected.get(form.outlet_port, ()))
    triggers = tuple(connected.get(form.trigger_port, ()))
    if outlets != (form.outlet,) or not triggers or triggers != form.triggers:
        raise ValueError(
            f"dormancy_form_disagrees({form.item}): {form.outlet_port} carries {list(outlets)}, "
            f"{form.trigger_port} carries {list(triggers)}; the form names {form.outlet!r} and "
            f"{list(form.triggers)}"
        )
    _, outlet_temperature, source = form.label
    if (outlet_temperature, source) != (
        temperature_id(form.outlet),
        temperature_id(form.triggers[0]),
    ):
        raise ValueError(
            f"dormancy_form_disagrees({form.item}): the label reads {outlet_temperature} and "
            f"{source}"
        )
    named = (
        outlet_temperature,
        source,
        *form.trigger_flows,
        *(name for outlet, inlets in form.balance for name in (outlet, *inlets)),
    )
    absent = [name for name in named if name not in columns]
    if absent:
        raise ValueError(f"dormancy_form_disagrees({form.item}): not columns: {absent}")
    swapped = declaration.rows.get(form.swapped)
    if (
        row_units.get(form.swapped) != form.unit
        or swapped is None
        or outlet_temperature not in swapped.columns
    ):
        raise ValueError(
            f"dormancy_form_disagrees({form.item}, {form.swapped}): not a row of {form.unit} "
            f"reading {outlet_temperature}"
        )
