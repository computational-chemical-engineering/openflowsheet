"""The verifier's checks of a `syn001.column` instance (S11 design note §4.8; WO-B4).

One function per category of §4.3's table, each taking the table's `Unit` and the component order,
as `verify.table.ModelChecks` expects; I1 registers them as `MODEL_CHECKS["syn001.column"]`
(`column_checks` in the tests until then). The rules are typed against `_Unit`, a local `Protocol`
of what they read, so this module imports no `verify.table` at run time.

| Check id | Value (tolerance kind) |
| --- | --- |
| `material_balance.<U>.<c>` | `Σ_inlets n_c − n_c(D) − n_c(B)` (molar_flow) |
| `energy_balance.<U>` | `Σ_inlets Ḣ + Q₁ + Q_N + Σ_j Q_j* − Ḣ(D) − Ḣ(B)` (heat_rate) |
| `specification.<U>.<end>` | the end's quantity against its target (below) |
| `phase_admissibility.<U>.<port>[.<S>]` | the declared ports (the table's rule) |
| `phase_admissibility.<U>.stage.<j>` | the number of stage j's failing acceptance items (0) |
| `phase_stability.<U>.stage.<j>` | γ–φ only: the stage liquid's vapour-trial `tm` (stable) |

Reading. The column's structure — its stage count, its ends and their specifications, its inlets
and the stage each enters — is the revision's, read by `column_unit.column_structure` (the
revision's one reader of a column instance, as `parse_revision` is of every instance). Stream
flows, temperatures and enthalpies are the table's; `Q₁` and `Q_N` are `stage_duty_id` at the
judged state when they are ends; `Q_j*` is `stage_duty.<j>` (0 when absent).

Specifications (S11 B4 decision: the table's linear form, as the splitter's ratio row is judged,
since the policy has no dimensionless tolerance kind): reflux `r − R·d`, boil-up `v_N − B·l_N`,
rates `Σ n − rate*` (molar_flow); duty `Q_s − Q*` (heat_rate); purity `n_c − π*·P` and recovery
`n_c − ν*·F_c` (molar_flow), the recovery failing outright when `F_c ≤ 0` at the state;
temperature `T_s − T*` (temperature). `d`, `P` and `n_c` are the product stream's; `r` is the
reflux (a total condenser's `r_c`, a partial one's `l_1`); `v_N` the bottom stage's vapour; `F_c`
the inlet streams'.

The stage items are `column_solve.acceptance_failures` at the judged state (the standalone solve's
acceptance: rows, pins, two-phase totals, single-phase admissibility, S02 §8 items 2–6, S06 §8
item 4), with each stage's regime read from the state's own totals, and attributed to the stage
each item names. That is the solver's implementation, and the check says so (A09).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Final, Protocol

from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import InstanceView
from openflowsheet.models.syn001.cascade import (
    InletState,
    declared_problem,
    inlet_stream,
    liquid_id,
    liquid_total_id,
    stage_duty_id,
    stage_pressure_id,
    stage_temperature_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.column import (
    CONDENSER,
    REBOILER,
    ColumnSpec,
    EndSpecification,
    declared_rows,
    reflux_id,
)
from openflowsheet.models.syn001.column_solve import acceptance_failures
from openflowsheet.models.syn001.column_unit import (
    BOTTOMS,
    DISTILLATE,
    ColumnStructure,
    column_structure,
)
from openflowsheet.models.syn001.equilibrium_form import composition_dependent
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.wilson_ig import EPS_TPD
from openflowsheet.verify import CheckResult, dormant, evaluated, unsupported
from openflowsheet.verify.checks import VerifierError

if TYPE_CHECKING:
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.orchestrator.region import Regime
    from openflowsheet.thermo import PropertyProvider
    from openflowsheet.verify import CheckCategory

__all__ = [
    "DECLARED_PORTS",
    "admissibility",
    "duty",
    "energy",
    "material",
    "specification",
]

#: §4.8: the declared ports, all five, each `(port, several streams)` (`ModelChecks`).
DECLARED_PORTS: Final[tuple[tuple[str, bool], ...]] = (
    ("feed", True),
    ("top", False),
    ("bottom", False),
    (DISTILLATE, False),
    (BOTTOMS, False),
)
#: A09: the stage items are the standalone solve's acceptance, not an independent check.
_SHARED_ACCEPTANCE: Final = (
    "; the stage items are models.syn001.column_solve.acceptance_failures, the standalone "
    "solve's own acceptance (not an independent check)"
)
#: A09: the stability test is the provider's own (Q-F4).
_SHARED_STABILITY: Final = (
    "; the stability test is the provider's own tangent-plane test (not an independent check)"
)
_STABLE: Final = "STABLE_WITHIN_TESTED_SCOPE"


class _Unit(Protocol):
    """What the rules read of `verify.table.Unit`."""

    @property
    def view(self) -> InstanceView: ...

    @property
    def state(self) -> Mapping[str, float]: ...

    @property
    def enthalpy(self) -> Mapping[str, float]: ...

    @property
    def energy_note(self) -> str: ...

    @property
    def provider(self) -> PropertyProvider | None: ...

    @property
    def context(self) -> EvaluationContext | None: ...

    @property
    def id(self) -> str: ...

    def stream(self, port: str) -> str: ...

    def inlets(self) -> tuple[str, ...]: ...

    def n(self, stream: str, component: str) -> float: ...

    def check(
        self,
        category: CheckCategory,
        item: str,
        value: float,
        kind: str,
        *,
        reads: Sequence[str] | None = None,
    ) -> CheckResult: ...


def _structure(unit: _Unit, components: Sequence[str]) -> ColumnStructure:
    return column_structure(unit.view, components)


def _end_stages(structure: ColumnStructure) -> dict[str, int]:
    """Each present end and its stage: the condenser's is 1, the reboiler's N."""
    stages: dict[str, int] = {}
    if structure.condenser != "none":
        stages[CONDENSER] = 1
    if structure.reboiler != "none":
        stages[REBOILER] = structure.stage_count
    return stages


def duty(view: InstanceView, state: Mapping[str, float], components: Sequence[str]) -> float:
    """`Q₁ + Q_N + Σ_j Q_j*`: each end's duty at `state`, condenser first, then the fixed duties
    `stage_duty.<j>` of the other stages in stage order (§4.8; also the envelope's `Q_ext`)."""
    structure = column_structure(view, components)
    ends = _end_stages(structure)
    total = 0.0
    for stage in ends.values():
        total += state[stage_duty_id(structure.unit_id, stage)]
    for stage in range(1, structure.stage_count + 1):
        if stage not in ends.values():
            total += view.parameters.get(f"stage_duty.{stage}", 0.0)
    return total


def material(unit: _Unit, components: Sequence[str]) -> list[CheckResult]:
    """`material_balance.<U>.<c>`: `Σ_inlets n_c − n_c(distillate) − n_c(bottoms)`."""
    distillate, bottoms = unit.stream(DISTILLATE), unit.stream(BOTTOMS)
    checks: list[CheckResult] = []
    for c in components:
        value = 0.0
        for stream in unit.inlets():
            value += unit.n(stream, c)
        value -= unit.n(distillate, c)
        value -= unit.n(bottoms, c)
        checks.append(unit.check("material_balance", c, value, "molar_flow"))
    return checks


def energy(unit: _Unit, components: Sequence[str]) -> list[CheckResult]:
    """`energy_balance.<U>`: `Σ_inlets Ḣ + Q₁ + Q_N + Σ_j Q_j* − Ḣ(distillate) − Ḣ(bottoms)`."""
    distillate, bottoms = unit.stream(DISTILLATE), unit.stream(BOTTOMS)
    inlets = unit.inlets()
    value = 0.0
    for stream in inlets:
        value += unit.enthalpy[stream]
    value += duty(unit.view, unit.state, components)
    value -= unit.enthalpy[distillate]
    value -= unit.enthalpy[bottoms]
    return [
        unit.check("energy_balance", "", value, "heat_rate", reads=(*inlets, distillate, bottoms))
    ]


def _total(unit: _Unit, stream: str, components: Sequence[str]) -> float:
    total = 0.0
    for c in components:
        total += unit.n(stream, c)
    return total


def specification(unit: _Unit, components: Sequence[str]) -> list[CheckResult]:
    """`specification.<U>.<end>`, condenser first: each end's quantity against its target."""
    structure = _structure(unit, components)
    given = {CONDENSER: structure.condenser_spec, REBOILER: structure.reboiler_spec}
    checks: list[CheckResult] = []
    for end, stage in _end_stages(structure).items():
        found = given[end]
        if found is None:
            continue
        checks.append(_end_check(unit, structure, end, stage, found, components))
    return checks


def _end_check(
    unit: _Unit,
    structure: ColumnStructure,
    end: str,
    stage: int,
    given: EndSpecification,
    components: Sequence[str],
) -> CheckResult:
    state, name = unit.state, structure.unit_id
    product = unit.stream(DISTILLATE if end == CONDENSER else BOTTOMS)
    kind, target = given.kind, given.value
    if kind == "duty":
        value = state[stage_duty_id(name, stage)] - target
        return unit.check("specification", end, value, "heat_rate")
    if kind == "temperature":
        assert given.stage is not None, "the parser requires the stage"
        value = state[stage_temperature_id(name, given.stage)] - target
        return unit.check("specification", end, value, "temperature")
    if kind in ("distillate_rate", "bottoms_rate"):
        return unit.check(
            "specification", end, _total(unit, product, components) - target, "molar_flow"
        )
    if kind == "reflux_ratio":
        if structure.condenser == "total":
            reflux = sum(state[reflux_id(name, c)] for c in components)
        else:
            reflux = state[liquid_total_id(name, 1)]
        value = reflux - target * _total(unit, product, components)
        return unit.check("specification", end, value, "molar_flow")
    if kind == "boilup_ratio":
        boilup = state[vapor_total_id(name, stage)]
        value = boilup - target * _total(unit, product, components)
        return unit.check("specification", end, value, "molar_flow")
    component = given.component
    assert component is not None, "the parser requires the component"
    flow = unit.n(product, component)
    if kind == "purity":
        value = flow - target * _total(unit, product, components)
        return unit.check("specification", end, value, "molar_flow")
    if kind == "recovery":
        feed = 0.0
        for stream in unit.inlets():
            feed += unit.n(stream, component)
        check = unit.check("specification", end, flow - target * feed, "molar_flow")
        if feed > 0.0:
            return check
        # §4.8: a recovery is undefined without its component in the feed; never a pass.
        return replace(check, result="fail", reason=f"recovery_feed_not_positive({component})")
    raise VerifierError(f"specification_kind_unknown({name}.{end}.{kind})")


# -- the stage items ----------------------------------------------------------------------------


def _regime(state: Mapping[str, float], unit: str, stage: int) -> Regime:
    """A stage's regime as the state's own totals say (the verifier never reads the solve's)."""
    vapor, liquid = state[vapor_total_id(unit, stage)], state[liquid_total_id(unit, stage)]
    if vapor > 0.0 and liquid > 0.0:
        return "TWO_PHASE"
    if vapor > 0.0:
        return "VAPOR"
    if liquid > 0.0:
        return "LIQUID"
    return "ZERO_FLOW"


_STAGE = re.compile(r"(?::stage:|\.stage\.)(\d+)(?:[:.]|$)|\bstage (\d+)\b")
_PAIR = re.compile(r"^§8\.4: stages \((\d+), (\d+)\)")
_INLET = re.compile(r":inlet:([^:]+):")
_END = re.compile(r"^S06 §8\.4: (condenser|reboiler) ")
_PRODUCT = re.compile(r":product:(distillate|bottoms):|^§8\.5: product (distillate|bottoms) ")


def _stages_of(item: str, structure: ColumnStructure) -> tuple[int, ...]:
    """The stage(s) an acceptance item names: a pair for S02 §8 item 4; a row or column id's stage;
    an inlet link row's inlet stage; a product row's or S02 §8 item 5's end stage; S02 §8 item 3's
    total condenser (stage 1); S06 §8 item 4's end stage; else the `stage <j>` it states."""
    count = structure.stage_count
    if found := _PAIR.match(item):
        return (int(found[1]), int(found[2]))
    if found := _END.match(item):
        return (1 if found[1] == CONDENSER else count,)
    if item.startswith("§8.3:"):
        return (1,)
    if found := _PRODUCT.search(item):
        port = found[1] or found[2]
        return (1 if port == DISTILLATE else count,)
    if found := _INLET.search(item):
        stages = [inlet.stage for inlet in structure.inlets if inlet.name == found[1]]
        if len(stages) == 1:
            return (stages[0],)
    if found := _STAGE.search(item):
        return (int(found[1] or found[2]),)
    raise VerifierError(f"acceptance_item_unattributed({structure.unit_id}): {item}")


def _judged_spec(unit: _Unit, structure: ColumnStructure, components: Sequence[str]) -> ColumnSpec:
    """The `ColumnSpec` with each inlet's state read from the judged state's inlet stream."""
    state = unit.state
    return structure.spec(
        {
            inlet.name: InletState(
                n=tuple(state[flow_id(inlet.stream, c)] for c in components),
                temperature=state[temperature_id(inlet.stream)],
                pressure=state[pressure_id(inlet.stream)],
                phase=inlet.phase,
            )
            for inlet in structure.inlets
        }
    )


def admissibility(unit: _Unit, components: Sequence[str]) -> list[CheckResult]:
    """`phase_admissibility.<U>.stage.<j>` for every stage (value: the number of stage j's
    failing acceptance items, tolerance 0), then, on a composition-dependent basis,
    `phase_stability.<U>.stage.<j>` for every equilibrium stage."""
    provider, context = unit.provider, unit.context
    if provider is None or context is None:
        raise VerifierError(f"provider_missing({unit.id})")
    structure = _structure(unit, components)
    spec = _judged_spec(unit, structure, components)
    name = structure.unit_id
    # The standalone declaration (no flowsheet links) at the judged state, its pinned inlet
    # columns `<U>.inlet.<name>.*` read from the inlet streams: the standalone acceptance.
    state = dict(unit.state)
    for inlet in structure.inlets:
        column = inlet_stream(name, inlet.name)
        for c in components:
            state[flow_id(column, c)] = unit.state[flow_id(inlet.stream, c)]
        state[temperature_id(column)] = unit.state[temperature_id(inlet.stream)]
        state[pressure_id(column)] = unit.state[pressure_id(inlet.stream)]
    declared = declared_problem(declared_rows(spec, provider, context))
    equilibrium = spec.equilibrium_stages()
    regimes = {stage: _regime(state, name, stage) for stage in equilibrium}
    note = unit.energy_note
    try:
        failures = acceptance_failures(spec, provider, declared, state, regimes)
    except ZeroDivisionError as error:
        # S06 §8 item 4 divides by `F_c` (recovery) or `P` (purity): undefined at this state,
        # which the specification row already fails (`recovery_feed_not_positive`).
        return [
            unsupported(
                id=f"phase_admissibility.{name}.stage.{stage}",
                category="phase_admissibility",
                subject=name,
                reason=f"acceptance_undefined({error})",
            )
            for stage in range(1, structure.stage_count + 1)
        ]
    by_stage: dict[int, list[str]] = {}
    for item in failures:
        for stage in _stages_of(item, structure):
            by_stage.setdefault(stage, []).append(item)
    checks: list[CheckResult] = []
    for stage in range(1, structure.stage_count + 1):
        items = by_stage.get(stage, [])
        checks.append(
            replace(
                evaluated(
                    id=f"phase_admissibility.{name}.stage.{stage}",
                    category="phase_admissibility",
                    subject=name,
                    value=float(len(items)),
                    tolerance=0.0,
                    independence_qualification=note + _SHARED_ACCEPTANCE,
                ),
                reason="; ".join(items),
            )
        )
    if composition_dependent(provider):
        for stage in equilibrium:
            checks.append(_stability(unit, provider, context, name, stage, components, note))
    return checks


def _stability(
    unit: _Unit,
    provider: PropertyProvider,
    context: EvaluationContext,
    name: str,
    stage: int,
    components: Sequence[str],
    note: str,
) -> CheckResult:
    """`phase_stability.<U>.stage.<j>`: the stage liquid at `(T_j, P_j)` judged as LIQUID
    reports no split (Q-F4); its value is the vapour trial's tangent-plane distance `tm`."""
    state = unit.state
    identifier = f"phase_stability.{name}.stage.{stage}"
    liquid = StreamState(
        n=tuple(state[liquid_id(name, stage, c)] for c in components),
        temperature=state[stage_temperature_id(name, stage)],
        pressure=state[stage_pressure_id(name, stage)],
    )
    if liquid.is_dormant:
        return dormant(id=identifier, category="phase_admissibility", subject=name)
    judge = getattr(provider, "stability", None)
    if judge is None:
        return unsupported(
            id=identifier,
            category="phase_admissibility",
            subject=name,
            reason="stability_unavailable",
        )
    report = judge(liquid, "LIQUID", context)
    distance = report.tm.get("VAPOR")
    if report.label not in (_STABLE, "UNSTABLE") or distance is None:
        return unsupported(
            id=identifier,
            category="phase_admissibility",
            subject=name,
            reason=f"stability_{report.label.lower()}: {report.reason}",
        )
    # The provider's verdict (`tm ≥ −EPS_TPD`), with `tm` and its resolution reported.
    return replace(
        evaluated(
            id=identifier,
            category="phase_admissibility",
            subject=name,
            value=distance,
            tolerance=EPS_TPD,
            independence_qualification=note + _SHARED_STABILITY,
        ),
        result="pass" if report.label == _STABLE else "fail",
    )
