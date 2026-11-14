"""The check table's flowsheet rows: the material and energy envelopes over the flowsheet's feeds
and products, and the model-id sets that name their terms (T05 design note §4.3, register R-046).
`verify.table` re-exports the model-id sets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from openflowsheet.models import duty_id, flow_id
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionView
from openflowsheet.models.syn001.conversion_reactor import extent_id
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.verify import CheckResult, evaluated, pr_c1
from openflowsheet.verify import column as column_rows
from openflowsheet.verify.checks import KIND_REFERENCE
from openflowsheet.verify.split_checks import Degeneracy
from openflowsheet.verify.table_kit import _unlifted_read, blocked_check, stream_notes
from openflowsheet.verify.unit_checks import _cstr_rate

# §4.3's flowsheet rows name their terms by model id, so the envelope is the same function
# whether or not a model's own entry is in the table yet.
#: Feeds are the outlet streams of these instances.
FEED_MODELS: Final = frozenset({"syn001.feed_source", "c1.feed_source"})


#: Products are the inlet streams of these instances.
PRODUCT_MODELS: Final = frozenset({"syn001.product_sink", "c1.product_sink"})


#: `Q_ext`: the external duty `<U>.Q` — never the exchanger's internal `Q`.
EXTERNAL_DUTY_MODELS: Final = (
    "syn001.tp_heater",
    "syn001.tp_flash",
    "syn001.ph_flash",
    "syn001.conversion_reactor",
    "syn001.component_separator",
    "syn001.kinetic_cstr",
    "c1.tp_heater",
    "c1.tp_flash",
    # M02 WO-9: the C1 reactor's duty `<U>.Q`, positive into the unit (design note §4.1).
    "c1.reactor",
    "c1.reactor_standin",
    # M04 WO-7: the surrogate's duty `<U>.Q`, M02's row (spec §3.2).
    "c1.reactor_surrogate",
    # S11 units design §4.4 (I1b): the thermal heater's and flash's duty `<U>.Q`.
    "thermal.heater",
    "thermal.flash",
)


#: S11 design §4.8: a staged unit's duties are its own (`verify.column.duty`: each end's `Q_j` at
#: the state, then the fixed `Q_j*`), not one `<U>.Q`.
STAGED_DUTY_MODELS: Final = frozenset({"syn001.column"})


#: `W`: the shaft work `<U>.W`.
WORK_MODELS: Final = frozenset(
    # S11 units design §4.4 (I1b): the three thermal machines' `<U>.W`.
    {"syn001.liquid_pump", "thermal.pump", "thermal.compressor", "thermal.turbine"}
)


#: `ν_c ξ` on the material envelope; ADR 0011 D2's note on the energy balances. A conversion
#: reactor's `ξ` is its extent column; a kinetic CSTR's is its rate `r`, which it does not own and
#: the table recomputes from the state and the revision (`_cstr_rate`, T08 build-first §A1.6).
#: The C1 reactors' `ξ` is their extent column too, and their `ν` the verifier's own copy of the
#: C1 reaction (`pr_c1.REACTION_NU`; M02 WO-9), which no revision states.
REACTING_MODELS: Final = frozenset(
    {"syn001.conversion_reactor", "syn001.kinetic_cstr", *pr_c1.REACTOR_MODELS}
)


KINETIC_CSTR: Final = "syn001.kinetic_cstr"


# -- the flowsheet rows ------------------------------------------------------------------------


def _feeds(view: RevisionView) -> list[str]:
    return [
        stream
        for instance in view.instances
        if instance.model_id in FEED_MODELS
        for port, direction in instance.directions.items()
        if direction == "outlet"
        for stream in instance.ports[port]
    ]


def _products(view: RevisionView) -> list[str]:
    return [
        stream
        for instance in view.instances
        if instance.model_id in PRODUCT_MODELS
        for port, direction in instance.directions.items()
        if direction == "inlet"
        for stream in instance.ports[port]
    ]


def _extent(reactor: InstanceView, state: Mapping[str, float]) -> float:
    """A reacting instance's `ξ`: the conversion reactor's extent column, the CSTR's rate."""
    if reactor.model_id == KINETIC_CSTR:
        return _cstr_rate(reactor, state)
    return state[extent_id(reactor.unit_id)]


def _nu(reactor: InstanceView, component: str) -> float:
    """A reacting instance's `ν_c`: the revision's `nu.<c>`, or for a C1 reactor the verifier's
    own copy of the C1 reaction (M02 WO-9)."""
    if reactor.model_id in pr_c1.REACTOR_MODELS:
        return pr_c1.REACTION_NU[component]
    return reactor.parameters[f"nu.{component}"]


def _envelope_material(
    view: RevisionView, state: Mapping[str, float], tolerances: Mapping[str, float]
) -> list[CheckResult]:
    """`Σ_feeds n + Σ_reactors ν_c ξ − Σ_products n`, accumulated in that order into one sum."""
    feeds, products = _feeds(view), _products(view)
    reactors = [i for i in view.instances if i.model_id in REACTING_MODELS]
    checks: list[CheckResult] = []
    for c in view.components:
        value = 0.0
        for stream in feeds:
            value += state[flow_id(stream, c)]
        for reactor in reactors:
            value += _nu(reactor, c) * _extent(reactor, state)
        for stream in products:
            value -= state[flow_id(stream, c)]
        checks.append(
            evaluated(
                id=f"material_balance.envelope.{c}",
                category="material_balance",
                subject="flowsheet",
                value=value,
                tolerance=tolerances["molar_flow"],
                reference=KIND_REFERENCE["molar_flow"],
            )
        )
    return checks


def _envelope_energy(
    view: RevisionView,
    state: Mapping[str, float],
    enthalpy: Mapping[str, float],
    tolerances: Mapping[str, float],
    note: str,
    degenerate: Degeneracy,
) -> CheckResult:
    """`(Σ Q_ext + Σ W) − (Σ Ḣ(products) − Σ Ḣ(feeds))`, each sum in declaration order."""
    reads = (*_products(view), *_feeds(view))
    blocked = _unlifted_read(reads, degenerate.unlifted)
    if blocked is not None:
        return blocked_check("energy_balance.envelope", "energy_balance", "flowsheet", blocked)
    duty = 0.0
    for instance in view.instances:
        if instance.model_id in EXTERNAL_DUTY_MODELS:
            duty += state[duty_id(instance.unit_id)]
        elif instance.model_id in STAGED_DUTY_MODELS:
            duty += column_rows.duty(instance, state, view.components)
    work = 0.0
    for instance in view.instances:
        if instance.model_id in WORK_MODELS:
            work += state[work_id(instance.unit_id)]
    products = 0.0
    for stream in _products(view):
        products += enthalpy[stream]
    feeds = 0.0
    for stream in _feeds(view):
        feeds += enthalpy[stream]
    return evaluated(
        id="energy_balance.envelope",
        category="energy_balance",
        subject="flowsheet",
        value=(duty + work) - (products - feeds),
        tolerance=tolerances["heat_rate"],
        reference=KIND_REFERENCE["heat_rate"],
        independence_qualification=note + stream_notes(reads, degenerate.notes),
    )
