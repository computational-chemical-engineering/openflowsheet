"""`syn001.cascade` compiled and solved: S01 spec §4.1–§4.5, §7 and §8 (WO-2).

`cascade.py` holds the unit layer (WO-1): the specification, its §5 refusals, the §2 rows, the
§6 initializer and the §4.6 closed form. This module compiles those rows and runs spec §7's path
on them, calling `orchestrator.region.solve_region` unchanged (DECISION 1):

1. validate (§5); an all-dormant cascade is §4.6's closed form;
2. initialize (`s01-kremser-cmo-v1`), giving `x_K`;
3. the isothermal pre-solve `s01-isothermal-presolve-v1`: the target's columns with every
   `Q_j − Q_j*` row replaced by `T_j − T̄`, one attempt from `x_K`, which must converge with every
   stage `TWO_PHASE`; its root is `x⁰`;
4. the target from `x⁰` under `s01-default-v1`;
5. recovery edge 3 (ADR 0010 D3) when step 4 ends in one of its triggers, continuing the `Q_j*`
   from `Q⁰ = Q(x⁰)` (DECISION 2);

and holds a `CONVERGED` answer to §8 before returning it.

**Each stage is one lifted split** (spec §4.1), keyed by the stage's id `<U>.stage.<j>`: its feed
is the lifted `m_j`, its outlets `v_j`, `l_j`. In the target the stage is PH-type (its energy row
fixes `T_j`, ADR 0012 D3); in the pre-solve `T_j` is fixed by a specification row, so the stage
is TP-type there (build decision, `docs/S01_DECISIONS.md`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

from openflowsheet.canonical import state_sha256
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import EquationSpec, ProblemSpec, QuantityKind
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    SpecificationError,
    flow_id,
    origin,
    temperature_id,
)
from openflowsheet.models.rows import specification_row
from openflowsheet.models.syn001 import TEMPERATURE
from openflowsheet.models.syn001.cascade import (
    MODEL_ID as CASCADE_MODEL_ID,
)
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    CascadeSpec,
    DormantAnswer,
    KremserInitial,
    _enthalpy_flow,
    _parameter,
    _phase,
    declared_problem,
    declared_rows,
    dormant_answer,
    inlet_stream,
    is_dormant,
    kremser_initial,
    liquid_id,
    liquid_total_id,
    mixed_id,
    regime_form,
    stage_duty_id,
    stage_prefix,
    stage_pressure_id,
    stage_row_id,
    stage_temperature_id,
    validate,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.tp_state import single_phase_admissible
from openflowsheet.orchestrator.execution import Region
from openflowsheet.orchestrator.homotopy import Continuation
from openflowsheet.orchestrator.recovery import (
    eo_recovery_due,
    recovered_provenance,
    solver_outcomes,
)
from openflowsheet.orchestrator.region import (
    KIND_TOLERANCE,
    LABEL_KIND,
    ClosureType,
    LiftedSplit,
    RecoveryStart,
    Regime,
    RegionResult,
    ZeroFlowForm,
    solve_region,
)
from openflowsheet.orchestrator.trace import GlobalizationPolicy, SolvePolicy, Trace
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

#: Spec §7.3's registered pre-solve.
PRESOLVE_ID: Final = "s01-isothermal-presolve-v1"

#: Spec §7.6: the registered EO default (`T05b-v2`: the defaults with phase contract v2) with
#: `eo_core = "newton_refined"` (ADR 0018) and `eo_recovery = "homotopy"` (already its default).
S01_DEFAULT_V1: Final[SolvePolicy] = SolvePolicy(
    policy_id="s01-default-v1",
    residual_tolerances={},
    scales={},
    phase_contract="T05b-phase-contract-v2",
    globalization=GlobalizationPolicy(eo_core="newton_refined", eo_recovery="homotopy"),
)

#: Spec §7.3: one attempt (`max_attempts = 1`, so no restart is honoured) and no recovery edge;
#: otherwise `s01-default-v1` (spec §15.1's default).
PRESOLVE_POLICY: Final[SolvePolicy] = replace(
    S01_DEFAULT_V1,
    policy_id=PRESOLVE_ID,
    max_attempts=1,
    globalization=replace(S01_DEFAULT_V1.globalization, eo_recovery="none"),
)

#: The pre-solve's replacement rows `T_j − T̄` (spec §7.3). Not part of `cascade.EQUATIONS`:
#: they author rows of the pre-solve's problem only, never of the target's declaration.
PRESOLVE_EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="CAS-presolve-T",
        statement="T_j - Tbar = 0 for every stage j (the isothermal pre-solve, S01 spec §7.3)",
        dependencies=("stage.T", "parameters.Tbar"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source="docs/derivations/S01-spec.md §7.3",
    ),
)

#: The context the declaration's property blocks are built with. SYN-001 does not read it; the
#: compiled problem's own context is the one every evaluation is checked against.
DECLARATION_CONTEXT: Final = EvaluationContext(
    model_version="S01-cascade-declaration@" + "0" * 64,
    constants_sha256="0" * 64,
    phase_signature=None,
)

#: Spec §10 A10's column scales `D_x`, by quantity kind.
FD_COLUMN_SCALE: Final[Mapping[QuantityKind, float]] = {
    "molar_flow": 1.0,
    "temperature": 100.0,
    "pressure": 1.0e5,
    "heat_rate": 1.0e4,
}

Problem = Literal["target", "presolve"]


# -- spec §4.1–§4.2: the per-stage region descriptors ------------------------------------------


def stage_unit(unit: str, stage: int) -> str:
    """The split's key — its `unit` in every region map and in the attempt signature."""
    return stage_prefix(unit, stage)


def lifted_splits(spec: CascadeSpec) -> tuple[LiftedSplit, ...]:
    """Spec §4.1: stage j's `LiftedSplit`, `feed = m_j`, in stage order (the signature order)."""
    unit, components = spec.unit_id, spec.components
    return tuple(
        LiftedSplit(
            unit=stage_unit(unit, stage),
            stream=stage_unit(unit, stage),
            feed=tuple(mixed_id(unit, stage, c) for c in components),
            temperature=stage_temperature_id(unit, stage),
            pressure=stage_pressure_id(unit, stage),
            vapor=tuple(vapor_id(unit, stage, c) for c in components),
            liquid=tuple(liquid_id(unit, stage, c) for c in components),
            vapor_total=vapor_total_id(unit, stage),
            liquid_total=liquid_total_id(unit, stage),
            equilibrium_rows=tuple(stage_row_id(unit, stage, "eq", c) for c in components),
            vapor_definition=stage_row_id(unit, stage, "Vdef"),
            liquid_definition=stage_row_id(unit, stage, "Ldef"),
        )
        for stage in range(1, spec.stage_count + 1)
    )


def zero_flow_forms(spec: CascadeSpec) -> dict[str, ZeroFlowForm]:
    """Spec §4.2: each stage's `ZERO_FLOW` form from WO-1's `regime_form`; the swapped energy
    row is the form's last dropped row (`ZeroFlowForm.rows`), and the label is §4.3's."""
    forms: dict[str, ZeroFlowForm] = {}
    for stage in range(1, spec.stage_count + 1):
        form = regime_form(spec, stage, "ZERO_FLOW")
        forms[stage_unit(spec.unit_id, stage)] = ZeroFlowForm(
            unit=stage_unit(spec.unit_id, stage),
            columns=form.pinned,
            rows=(*form.dropped, form.swapped),
            swapped=form.swapped,
            label=form.label,
        )
    return forms


def closure_types(spec: CascadeSpec, problem: Problem) -> dict[str, ClosureType]:
    """PH for every stage of the target (its energy row fixes `T_j`, spec §4.1); TP in the
    pre-solve, where `T_j − T̄` fixes it."""
    kind: ClosureType = "PH" if problem == "target" else "TP"
    return {stage_unit(spec.unit_id, j): kind for j in range(1, spec.stage_count + 1)}


def split_temperatures(spec: CascadeSpec) -> dict[str, tuple[str, ...]]:
    """Each stage's temperature columns: `T_j` only (both outlets carry the stage's state)."""
    return {
        stage_unit(spec.unit_id, j): (stage_temperature_id(spec.unit_id, j),)
        for j in range(1, spec.stage_count + 1)
    }


# -- compile -------------------------------------------------------------------------------------


def presolve_row_id(unit: str, stage: int) -> str:
    """`<U>:stage:<j>:T`, the pre-solve's row in place of `<U>:stage:<j>:Q`."""
    return stage_row_id(unit, stage, "T")


def presolve_rows(rows: Contribution, spec: CascadeSpec, tbar: float) -> Contribution:
    """Spec §7.3: the declared rows with each `Q_j − Q_j*` replaced, in place, by `T_j − T̄`.

    Same columns; the `Q_j*` pinned inputs are replaced by `T_j*` (all `T̄`), so `Q_j` is free and
    `energy_j` determines it."""
    unit = spec.unit_id
    swap: dict[str, tuple[int, str]] = {}
    renamed: dict[str, str] = {}
    for stage in range(1, spec.stage_count + 1):
        parameter = _parameter(stage_temperature_id(unit, stage))
        swap[stage_row_id(unit, stage, "Q")] = (stage, parameter)
        renamed[_parameter(stage_duty_id(unit, stage))] = parameter
    equations: list[EquationSpec] = []
    row_kinds: dict[str, QuantityKind] = {}
    for equation in rows.equations:
        found = swap.get(equation.equation_id)
        if found is None:
            equations.append(equation)
            row_kinds[equation.equation_id] = rows.row_kinds[equation.equation_id]
            continue
        stage, parameter = found
        row = presolve_row_id(unit, stage)
        equations.append(
            EquationSpec(
                equation_id=row,
                build=specification_row(stage_temperature_id(unit, stage), parameter),
                accumulation="algebraic",
                origin=origin(CASCADE_MODEL_ID, "CAS-presolve-T"),
            )
        )
        row_kinds[row] = "temperature"
    parameter_ids = tuple(renamed.get(p, p) for p in rows.parameter_ids)
    parameters = {renamed.get(p, p): v for p, v in rows.parameters.items()}
    for new in renamed.values():
        parameters[new] = float(tbar)
    return replace(
        rows,
        equations=tuple(equations),
        row_kinds=row_kinds,
        parameter_ids=parameter_ids,
        parameters=parameters,
    )


def model_label(provider: PropertyProvider, problem: Problem) -> str:
    """ADR 0002 D2.7: the label names the equation set and the property package (the
    `Syn001Flowsheet.label` pattern), never a pinned input. The pre-solve's rows differ from the
    target's, so its label does too."""
    capabilities = provider.describe()
    tag = "S01-cascade" if problem == "target" else "S01-cascade-iso"
    label = (
        f"{tag}-{capabilities.provider_id}"
        f"-{capabilities.implementation_sha256[:12]}-{capabilities.data_sha256[:12]}"
    )
    if len(label) > 64:
        raise SpecificationError(f"the label {label!r} exceeds ADR 0002's 64 characters")
    return label


@dataclass(frozen=True)
class CompiledCascade:
    """One of the cascade's two problems, compiled, with everything `solve_region` is given."""

    problem: Problem
    spec: ProblemSpec
    compiled: CompiledProblem
    region: Region
    splits: tuple[LiftedSplit, ...]
    forms: Mapping[str, ZeroFlowForm]
    types: Mapping[str, ClosureType]
    temperatures: Mapping[str, tuple[str, ...]]

    def context(self) -> EvaluationContext:
        return EvaluationContext(
            model_version=self.compiled.metadata.model_version,
            constants_sha256=self.compiled.metadata.constants_sha256,
            phase_signature=None,
        )


def compile_cascade(
    spec: CascadeSpec,
    provider: PropertyProvider,
    problem: Problem = "target",
    *,
    tbar: float | None = None,
) -> CompiledCascade:
    """The target's (or, with `tbar`, the pre-solve's) `ProblemSpec`, compiled, and its region:
    every declared row over every declared column (the cascade owns all of them)."""
    rows = declared_rows(spec, provider, DECLARATION_CONTEXT)
    if problem == "presolve":
        if tbar is None:
            raise ValueError("the pre-solve's rows need T̄")
        rows = presolve_rows(rows, spec, tbar)
    declared = declared_problem(rows, model_label(provider, problem))
    splits = lifted_splits(spec)
    units = tuple(split.unit for split in splits)
    region = Region(
        units=units,
        row_ids=declared.equation_ids,
        variable_ids=declared.variable_ids,
        eliminated_rows=(),
        signature_units=units,
        fixed_upstream=(),
    )
    return CompiledCascade(
        problem=problem,
        spec=declared,
        compiled=compile_problem(declared),
        region=region,
        splits=splits,
        forms=zero_flow_forms(spec),
        types=closure_types(spec, problem),
        temperatures=split_temperatures(spec),
    )


def run_region(
    target: CompiledCascade,
    provider: PropertyProvider,
    state: Mapping[str, float],
    policy: SolvePolicy,
    *,
    initializer_source: str,
    trace: Trace | None = None,
    recovery: RecoveryStart | None = None,
) -> RegionResult:
    """`solve_region`, unchanged, on one compiled problem of the cascade."""
    return solve_region(
        compiled=target.compiled,
        spec=target.spec,
        region=target.region,
        state={name: float(state[name]) for name in target.spec.variable_ids},
        splits=target.splits,
        provider=provider,
        policy=policy,
        trace=trace,
        initializer_source=initializer_source,
        recovery=recovery,
        compile_level=compile_problem if recovery is not None else None,
        closure_types=target.types,
        zero_flow_forms=target.forms,
        split_temperatures=target.temperatures,
    )


# -- spec §8: acceptance -------------------------------------------------------------------------


class AcceptanceDefectError(RuntimeError):
    """Spec §8: a `CONVERGED` answer that fails acceptance is a defect, never a success."""

    def __init__(self, failures: Sequence[str]) -> None:
        super().__init__("S01 §8 refuses a CONVERGED answer: " + "; ".join(failures))
        self.failures = tuple(failures)


def regimes_of(spec: CascadeSpec, signature: Sequence[tuple[str, str]]) -> tuple[Regime, ...]:
    """A region signature's stage regimes, in stage order."""
    found = dict(signature)
    return tuple(
        _REGIMES[found[stage_unit(spec.unit_id, j)]] for j in range(1, spec.stage_count + 1)
    )


#: An attempt signature's value as a stage regime; any other value is a defect (`KeyError`).
_REGIMES: Final[Mapping[str, Regime]] = {
    "TWO_PHASE": "TWO_PHASE",
    "LIQUID": "LIQUID",
    "VAPOR": "VAPOR",
    "ZERO_FLOW": "ZERO_FLOW",
}


def system_residuals(
    spec: CascadeSpec,
    declared: ProblemSpec,
    state: Mapping[str, float],
    regimes: Sequence[Regime],
) -> tuple[dict[str, float], tuple[str, ...]]:
    """The declared rows of the signature `regimes` (pins, drops and labels applied), evaluated
    by the float reference evaluator at `state`, with their kinds; and the pinned columns."""
    values = row_values(declared, state)
    dropped: set[str] = set()
    pinned: list[str] = []
    labels: list[tuple[str, str, str]] = []
    for stage, regime in enumerate(regimes, start=1):
        form = regime_form(spec, stage, regime)
        dropped.update(form.dropped)
        pinned.extend(form.pinned)
        if form.swapped:
            dropped.add(form.swapped)
        if form.label is not None:
            labels.append(form.label)
    residuals = {name: value for name, value in values.items() if name not in dropped}
    for row, outlet, source in labels:
        residuals[row] = float(state[outlet]) - float(state[source])
    return residuals, tuple(pinned)


def row_kind(declared: ProblemSpec, row: str) -> str:
    return declared.row_kinds.get(row, LABEL_KIND)


def admissibility(
    spec: CascadeSpec,
    provider: PropertyProvider,
    state: Mapping[str, float],
    stage: int,
    regime: Phase,
) -> tuple[bool, str]:
    """Spec §8's admissibility of a single-phase stage, R-007 (spec §17.3, R-512):
    `tp_state.single_phase_admissible` on the stage's outlet in its phase, `l_j` (LIQUID) or
    `v_j` (VAPOR), at `(T_j, P_j)` -- the stream whose enthalpy the energy row writes
    single-phase, as the region's K03 §8.2 screen judges it. `(admissible, detail)`."""
    unit, components = spec.unit_id, spec.components
    outlet = liquid_id if regime == "LIQUID" else vapor_id
    stream = StreamState(
        n=tuple(float(state[outlet(unit, stage, c)]) for c in components),
        temperature=float(state[stage_temperature_id(unit, stage)]),
        pressure=float(state[stage_pressure_id(unit, stage)]),
    )
    admissible, _, error, status, message = single_phase_admissible(
        provider, stream, regime, components, DECLARATION_CONTEXT
    )
    return admissible, (f"equivalent temperature error {error!r} K" if status == "ok" else message)


def acceptance_failures(
    spec: CascadeSpec,
    provider: PropertyProvider,
    declared: ProblemSpec,
    state: Mapping[str, float],
    regimes: Sequence[Regime],
) -> tuple[str, ...]:
    """Spec §8: every declared row of the final signature within `KIND_TOLERANCE`, every pinned
    column `+0.0`, `V_j, L_j > 0` on a `TWO_PHASE` stage, admissibility on a single-phase one.
    Empty when the answer is accepted."""
    failures: list[str] = []
    residuals, pinned = system_residuals(spec, declared, state, regimes)
    for row, value in residuals.items():
        tolerance = KIND_TOLERANCE[row_kind(declared, row)]
        if not abs(value) <= tolerance:
            failures.append(f"row {row} = {value!r} exceeds {tolerance!r}")
    for column in pinned:
        if state[column] != 0.0:
            failures.append(f"pinned column {column} = {state[column]!r} is not zero")
    unit = spec.unit_id
    for stage, regime in enumerate(regimes, start=1):
        if regime == "TWO_PHASE":
            for total in (vapor_total_id(unit, stage), liquid_total_id(unit, stage)):
                if not state[total] > 0.0:
                    failures.append(f"TWO_PHASE stage {stage}: {total} = {state[total]!r}")
        elif regime in ("LIQUID", "VAPOR"):
            phase: Phase = "LIQUID" if regime == "LIQUID" else "VAPOR"
            admissible, detail = admissibility(spec, provider, state, stage, phase)
            if not admissible:
                failures.append(f"{regime} stage {stage} inadmissible: {detail}")
    return tuple(failures)


# -- spec §2: overall closure (A08) ---------------------------------------------------------------


@dataclass(frozen=True)
class Closure:
    """Spec §2's overall closures at a state: `Σ_k n_ik − v_i1 − l_iN` per component (mol/s) and
    `Σ_j Q_j + Σ_k Ḣ_k − Ḣ(top_vapour) − Ḣ(bottom_liquid)` (W)."""

    components: tuple[float, ...]
    energy: float


def overall_closure(
    spec: CascadeSpec, provider: PropertyProvider, state: Mapping[str, float]
) -> Closure:
    unit, components, count = spec.unit_id, spec.components, spec.stage_count
    inlets = spec.inlets()
    per_component = tuple(
        sum(float(state[flow_id(inlet_stream(unit, inlet.port), c)]) for inlet in inlets)
        - float(state[vapor_id(unit, 1, c)])
        - float(state[liquid_id(unit, count, c)])
        for c in components
    )
    h_in = sum(
        _enthalpy_flow(
            provider,
            DECLARATION_CONTEXT,
            components,
            [float(state[flow_id(inlet_stream(unit, inlet.port), c)]) for c in components],
            float(state[temperature_id(inlet_stream(unit, inlet.port))]),
            inlet.state.pressure,
            _phase(inlet.state),
        )
        for inlet in inlets
    )

    def product(stage: int, flows: str, phase: Literal["VAPOR", "LIQUID"]) -> float:
        ids = vapor_id if flows == "v" else liquid_id
        return _enthalpy_flow(
            provider,
            DECLARATION_CONTEXT,
            components,
            [float(state[ids(unit, stage, c)]) for c in components],
            float(state[stage_temperature_id(unit, stage)]),
            float(state[stage_pressure_id(unit, stage)]),
            phase,
        )

    duties = sum(float(state[stage_duty_id(unit, j)]) for j in range(1, count + 1))
    energy = duties + h_in - product(1, "v", "VAPOR") - product(count, "l", "LIQUID")
    return Closure(per_component, energy)


# -- spec §7: the solve path ---------------------------------------------------------------------


@dataclass(frozen=True)
class PresolveSummary:
    """Spec §7.7: the pre-solve's attempt as recorded — outcome, Newton's own outcome and its
    iterations — and the root's `state_sha256`."""

    outcome: str
    solver_outcome: str | None
    iterations: int
    signature: tuple[Regime, ...]
    state_sha256: str


@dataclass(frozen=True)
class CascadeSolution:
    """Spec §7's answer: the outcome and cause, the final signature in stage order, the state,
    and spec §7.7's records."""

    outcome: str
    cause: str
    signature: tuple[Regime, ...]
    state: Mapping[str, float]
    initial: KremserInitial
    #: `x_K` and `x⁰` hashes (ADR 0008 D2, over the target's column order).
    initial_sha256: str
    #: The hash of the state the pre-solve actually opened from: `opening` when one is given,
    #: else `x_K` (equal to `initial_sha256`), over the same column order (spec §7.7, review N2).
    opening_sha256: str
    presolve_sha256: str | None
    presolve: RegionResult
    presolve_summary: PresolveSummary
    #: The target solve's result — the recovery's, with the failed solve's provenance first, when
    #: edge 3 fired; `None` when the pre-solve failed.
    result: RegionResult | None
    recovered_from: RegionResult | None = None
    final_sha256: str | None = None

    @property
    def branch_provenance(self) -> tuple[Mapping[str, object], ...]:
        return () if self.result is None else tuple(self.result.branch_provenance)


def continuation(spec: CascadeSpec) -> Continuation:
    """Spec §7.5: the continued parameters are the `Q_j*` of the rows `Q_j − Q_j*`.

    Built directly: `homotopy.continuation_parameter` reads a promoted row's id as its parameter
    id (the binding's convention), and the cascade's pinned inputs are `<column>*`."""
    unit = spec.unit_id
    stages = range(1, spec.stage_count + 1)
    return Continuation(
        type="specification_continuation",
        parameter_ids=tuple(_parameter(stage_duty_id(unit, j)) for j in stages),
        variable_ids=tuple(stage_duty_id(unit, j) for j in stages),
    )


def recover(
    spec: CascadeSpec,
    target: CompiledCascade,
    provider: PropertyProvider,
    failed: RegionResult,
    policy: SolvePolicy,
    trace: Trace | None = None,
) -> RegionResult:
    """Spec §7.5 (ADR 0010 D3, as `executor._eo_recovery` runs it): one recovery solve from the
    failed solve's item-0 opening, its provenance continuing the failed solve's."""
    if failed.opening is None or not failed.branch_provenance:
        raise ValueError(f"defect: {spec.unit_id}'s target ended {failed.outcome} unopened")
    opening_state, opening_regimes = failed.opening
    recovered = run_region(
        target,
        provider,
        opening_state,
        policy,
        initializer_source=PRESOLVE_ID,
        trace=trace,
        recovery=RecoveryStart(
            state=opening_state,
            regimes=opening_regimes,
            continuation=continuation(spec),
            initializer_source=failed.branch_provenance[0]["initializer_source"],
        ),
    )
    return replace(
        recovered,
        branch_provenance=recovered_provenance(
            failed.branch_provenance, recovered.branch_provenance
        ),
        checkpoint=recovered.checkpoint if recovered.checkpoint is not None else failed.checkpoint,
    )


def solve_cascade(
    spec: CascadeSpec,
    provider: PropertyProvider,
    *,
    policy: SolvePolicy = S01_DEFAULT_V1,
    opening: Mapping[str, float] | None = None,
    tbar: float | None = None,
    trace: Trace | None = None,
) -> CascadeSolution | CascadeFailure | DormantAnswer:
    """Spec §7, steps 1–5, and §8 on a `CONVERGED` answer.

    `opening` replaces `x_K` as the pre-solve's start, and `tbar` replaces the initializer's `T̄`
    as the pre-solve's isothermal level (spec §10 A18's perturbed openings; spec §17.8, R-517).
    Both default to the initializer's. A `CONVERGED` answer that fails §8 raises
    `AcceptanceDefectError`.
    """
    refused = validate(spec, provider, DECLARATION_CONTEXT)
    if refused is not None:
        return refused
    if is_dormant(spec):
        return dormant_answer(spec, provider, DECLARATION_CONTEXT)
    initial = kremser_initial(spec, provider, DECLARATION_CONTEXT)
    if isinstance(initial, CascadeFailure):
        return initial

    target = compile_cascade(spec, provider)
    order = target.spec.variable_ids
    start = dict(initial.state) if opening is None else {n: float(opening[n]) for n in order}
    initial_sha = state_sha256(dict(initial.state), order)
    opening_sha = state_sha256(start, order)

    level = initial.tbar if tbar is None else float(tbar)
    pre = compile_cascade(spec, provider, "presolve", tbar=level)
    presolve = run_region(
        pre, provider, start, PRESOLVE_POLICY, initializer_source=initial.initializer
    )
    final_attempt = presolve.attempts[-1] if presolve.attempts else None
    pre_regimes = regimes_of(spec, final_attempt.signature) if final_attempt else ()
    summary = PresolveSummary(
        outcome=presolve.outcome,
        solver_outcome=None if final_attempt is None else final_attempt.solver_outcome,
        iterations=presolve.iterations,
        signature=pre_regimes,
        state_sha256=state_sha256(dict(presolve.state), order),
    )
    two_phase = bool(pre_regimes) and all(r == "TWO_PHASE" for r in pre_regimes)
    if presolve.outcome != "CONVERGED" or not two_phase:
        outcome = presolve.outcome if presolve.outcome != "CONVERGED" else "not_two_phase"
        return CascadeSolution(
            outcome="INITIALIZATION_FAILED",
            cause=f"initialization_failed({PRESOLVE_ID}, {outcome})",
            signature=(),
            state=dict(presolve.state),
            initial=initial,
            initial_sha256=initial_sha,
            opening_sha256=opening_sha,
            presolve_sha256=None,
            presolve=presolve,
            presolve_summary=summary,
            result=None,
        )
    x0 = {name: float(presolve.state[name]) for name in order}

    result = run_region(target, provider, x0, policy, initializer_source=PRESOLVE_ID, trace=trace)
    recovered_from: RegionResult | None = None
    if policy.globalization.eo_recovery == "homotopy" and eo_recovery_due(
        result.outcome, result.budget, attempts=solver_outcomes(result.attempts)
    ):
        recovered_from = result
        result = recover(spec, target, provider, result, policy, trace)

    regimes = regimes_of(spec, result.attempts[-1].signature) if result.attempts else ()
    if result.outcome == "CONVERGED":
        failures = acceptance_failures(spec, provider, target.spec, result.state, regimes)
        if failures:
            raise AcceptanceDefectError(failures)
    return CascadeSolution(
        outcome=result.outcome,
        cause=result.message if result.outcome != "CONVERGED" else "",
        signature=regimes,
        state=dict(result.state),
        initial=initial,
        initial_sha256=initial_sha,
        opening_sha256=opening_sha,
        presolve_sha256=summary.state_sha256,
        presolve=presolve,
        presolve_summary=summary,
        result=result,
        recovered_from=recovered_from,
        final_sha256=state_sha256(dict(result.state), order),
    )


def products(spec: CascadeSpec, state: Mapping[str, float]) -> dict[str, tuple[float, ...]]:
    """Spec §1's outlets: `top_vapour` (stage 1's vapour) and `bottom_liquid` (stage N's)."""
    unit, count = spec.unit_id, spec.stage_count
    return {
        "top_vapour": tuple(float(state[vapor_id(unit, 1, c)]) for c in spec.components),
        "bottom_liquid": tuple(float(state[liquid_id(unit, count, c)]) for c in spec.components),
    }


__all__ = [
    "DECLARATION_CONTEXT",
    "FD_COLUMN_SCALE",
    "PRESOLVE_EQUATIONS",
    "PRESOLVE_ID",
    "PRESOLVE_POLICY",
    "S01_DEFAULT_V1",
    "AcceptanceDefectError",
    "CascadeSolution",
    "Closure",
    "CompiledCascade",
    "PresolveSummary",
    "acceptance_failures",
    "closure_types",
    "compile_cascade",
    "continuation",
    "lifted_splits",
    "overall_closure",
    "presolve_row_id",
    "presolve_rows",
    "products",
    "recover",
    "regimes_of",
    "run_region",
    "solve_cascade",
    "split_temperatures",
    "system_residuals",
    "zero_flow_forms",
]
