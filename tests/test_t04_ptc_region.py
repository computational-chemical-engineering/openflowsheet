"""T04 W4, W6, W7: the residence-time mapping and the PTC core in the SYN-001 region solve.

A13–A18 (the mapping, its refusals, steady-state equivalence, dimensions, reference invariance,
the loop's modes, the ×8 time-scale invariance), A21 (the accumulation identity), A22 (the polish),
A23's named runs, A24 (PHS-05 under PTC), A25 (composition with the contract), A28's PTC half.
Every expectation is `benchmarks/t04/reference_values.yaml`'s or a closed form of T04 §6 computed
here from the provider's own functions — never this code's output. Tolerances are T04 §12's, as
amended 2026-09-24 (F14) where the first registration sat below the double-precision floor (A15,
A17, A21); A21 also keeps a stricter four-ulp floor check beside the registered one.

The named runs and the basin comparison are direct region solves on the `eo` plan's region
(`test_t02_region.case`) with `eo_recovery: none`: the comparison is of cores (T04 §8.3).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import scipy.linalg as la
import yaml
from test_t02_region import Case, disagreement, initializer

import openflowsheet.orchestrator.region as region_module
from openflowsheet.application.binding import structural_inputs
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models import Wiring, flow_id, pressure_id, temperature_id
from openflowsheet.models.syn001 import MOLAR_FLOW
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.numerics.ptc import PtcProblem, pseudo_step_direction, row_signs
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.execution import build_execution_plan, declaration_identity
from openflowsheet.orchestrator.mass import (
    HoldupRule,
    MassMapping,
    ModelMassRule,
    PhaseOutflow,
    RegionMass,
    resolve_mass,
    syn001_residence_time,
)
from openflowsheet.orchestrator.region import (
    KIND_TOLERANCE,
    RegionResult,
    region_ptc_problem,
    solve_region,
    syn001_lifted_splits,
)
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.orchestrator.trace import (
    GlobalizationPolicy,
    PtcPolicy,
    RecyclePolicy,
    SolvePolicy,
    Trace,
)
from openflowsheet.thermo import PropertyRequest, PropertyResult
from openflowsheet.thermo.syn001 import C_P, V_MOLAR, Syn001Provider, h_liquid, h_vapor

REPO_ROOT = Path(__file__).resolve().parents[1]
REF: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "t04" / "reference_values.yaml").read_text()
)
NAMED = REF["policy_simulation"]["ptc_named"]
RELATIVE = 1e-9
COMPONENTS = ("A", "B", "C")
OFF_A, OFF_B = (0.1, 0.8, 1.2), (0.05, 0.1, 4.0)
EPS = float(np.finfo(np.float64).eps)
HIGH, NOMINAL = "SYN-001-high-recycle", "SYN-001-nominal"


def eo_policy(core: str = "ptc", ptc: PtcPolicy | None = None, **extra: Any) -> SolvePolicy:
    return SolvePolicy(
        policy_id=f"T04-{core}",
        residual_tolerances={},
        scales={},
        recycle=RecyclePolicy(method="eo"),
        globalization=GlobalizationPolicy(
            eo_core=core,  # type: ignore[arg-type]
            eo_recovery="none",
            ptc=ptc or PtcPolicy(),
        ),
        **extra,
    )


_CASES: dict[tuple[str, str], Case] = {}


def case(case_id: str, provider: Any = None) -> Case:
    """`test_t02_region.case`, with the provider a parameter (A16's shifted reference)."""
    key = (case_id, type(provider).__name__)
    if key in _CASES:
        return _CASES[key]
    entry = {
        item["case_id"]: item
        for item in yaml.safe_load(
            (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
        )["variants"]
    }[case_id]
    flowsheet = Syn001Flowsheet(
        provider=provider or Syn001Provider(),
        context=EvaluationContext(
            model_version="t04", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=float(entry["r"]),
        flash_temperature=float(entry["T_flash_K"]),
        heater_temperature=float(entry["T_heater_K"]),
        pressure=float(entry["P_Pa"]),
    )
    spec, graph, row_units = structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    identity = {"row_units": row_units, "model_version": model_version}
    declaration = trace_declaration(spec, constants_sha256=constants, **identity)
    report = analyse(spec, graph, constants_sha256=constants, **identity)
    plan = build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=eo_policy(),
    )
    region = plan.steps[1].region
    assert region is not None
    _CASES[key] = Case(flowsheet, spec, compile_problem(spec), region, entry)
    return _CASES[key]


def start(item: Case, which: str) -> dict[str, float]:
    if which == "initializer":
        return initializer(item)
    tear = Syn001TearProblem(item.flowsheet)
    return dict(tear.reconstruct(tear.tear_state({"OFF-A": OFF_A, "OFF-B": OFF_B}[which])))


def solve(
    item: Case,
    state: Mapping[str, float],
    *,
    core: str = "ptc",
    ptc: PtcPolicy | None = None,
    trace: Trace | None = None,
    mapping: Any = "registered",
    compiled: Any = None,
) -> RegionResult:
    return solve_region(
        compiled=compiled or item.compiled,
        spec=item.spec,
        region=item.region,
        state=state,
        splits=syn001_lifted_splits(item.flowsheet.components),
        provider=item.flowsheet.provider,
        policy=eo_policy(core, ptc),
        trace=trace,
        initializer_source="user_guess",
        mass_mapping=(
            syn001_residence_time(item.flowsheet.components) if mapping == "registered" else mapping
        ),
    )


NAMED_RUNS = {
    "r=0.95/initializer": (HIGH, "initializer"),
    "r=0.95/OFF-A": (HIGH, "OFF-A"),
    "r=0.95/OFF-B": (HIGH, "OFF-B"),
    "r=0.5/initializer": (NOMINAL, "initializer"),
}
_RUNS: dict[tuple[str, str], tuple[RegionResult, Trace]] = {}


def named(key: str, core: str = "ptc") -> tuple[RegionResult, Trace]:
    if (key, core) not in _RUNS:
        case_id, which = NAMED_RUNS[key]
        item = case(case_id)
        trace = Trace()
        _RUNS[(key, core)] = (solve(item, start(item, which), core=core, trace=trace), trace)
    return _RUNS[(key, core)]


def attempt_system(
    item: Case, regimes: Mapping[str, str]
) -> tuple[tuple[str, ...], tuple[str, ...], list[Any]]:
    """An attempt's free columns and rows under `regimes` — T02 §6.3.1's pins and drops."""
    splits = [s for s in syn001_lifted_splits(item.flowsheet.components) if s.unit in regimes]
    pinned = {n for s in splits for n in s.pinned(regimes[s.unit])}  # type: ignore[arg-type]
    dropped = {n for s in splits for n in s.dropped(regimes[s.unit])}  # type: ignore[arg-type]
    free = tuple(n for n in item.region.variable_ids if n not in pinned)
    rows = tuple(n for n in item.region.row_ids if n not in dropped)
    return free, rows, splits


def region_mass(item: Case, theta: float = 1.0) -> RegionMass:
    resolved = resolve_mass(
        syn001_residence_time(item.flowsheet.components),
        spec=item.spec,
        rows=item.region.row_ids,
        residence_time=theta,
    )
    assert isinstance(resolved, RegionMass)
    return resolved


def context_of(item: Case) -> EvaluationContext:
    return EvaluationContext(
        model_version=item.compiled.metadata.model_version,
        constants_sha256=item.compiled.metadata.constants_sha256,
        phase_signature=None,
    )


def ptc_problem_at(
    item: Case, state: Mapping[str, float], regimes: Mapping[str, str]
) -> tuple[PtcProblem, tuple[str, ...], tuple[str, ...], np.ndarray]:
    """The PTC problem an attempt in `regimes` solves, as the region builds it."""
    free, rows, splits = attempt_system(item, regimes)
    x = np.array([state[name] for name in free], dtype=np.float64)
    problem = region_ptc_problem(
        region_mass=region_mass(item),
        compiled=item.compiled,
        spec=item.spec,
        scaling=Scaling.from_spec(item.spec),
        base=state,
        free=free,
        rows=rows,
        splits=splits,
        regimes=regimes,  # type: ignore[arg-type]
        provider=item.flowsheet.provider,
        policy=eo_policy(),
        context=context_of(item),
        opening=x,
    )
    return problem, free, rows, x


_ROOTS: dict[str, tuple[dict[str, float], dict[str, str]]] = {}


def root(case_id: str) -> tuple[dict[str, float], dict[str, str]]:
    """The P01 root to roundoff: the region Newton solve from the registered initializer (T02
    A22), whose last step is quadratic, and the signature it converged in."""
    if case_id not in _ROOTS:
        item = case(case_id)
        result = solve(item, initializer(item), core="newton")
        assert result.outcome == "CONVERGED" and not disagreement(item, result.state)
        _ROOTS[case_id] = (dict(result.state), dict(result.attempts[-1].signature))
    return _ROOTS[case_id]


def scaled_step(problem: PtcProblem, free: Sequence[str], x: np.ndarray, tau: float) -> np.ndarray:
    evaluation = problem.problem.residual(x)
    assert evaluation.values is not None
    direction = pseudo_step_direction(problem, x, evaluation.values, tau)
    return np.asarray(problem.problem.scaling.scale_state(direction, free))


def holdup_rows(item: Case) -> set[str]:
    return {r for r in item.region.row_ids if item.spec.row_accumulation[r] == "holdup_balance"}


# ------------------------------------------------------------------ A13: the mapping


@pytest.mark.parametrize("where", ["root", "OFF-A"])
def test_a13_the_nonzero_m_rows_are_exactly_the_eight_holdup_balance_rows(where: str) -> None:
    """ADR 0008 D4.5's test on the SYN-001 region at r = 0.95: the rows with a nonzero `M` are the
    eight `holdup_balance` rows — the heater's and the flash's mole and duty rows — and no entry
    lies on a mixer (`zero_holdup_balance`) or algebraic row."""
    item = case(HIGH)
    state = root(HIGH)[0] if where == "root" else start(item, "OFF-A")
    entries = region_mass(item).entries_at(state, item.flowsheet.provider, context_of(item))
    nonzero = {row for (row, _), value in entries.items() if value != 0.0}
    assert nonzero == holdup_rows(item)
    assert len(nonzero) == 8
    assert {row.split(":")[0] for row in nonzero} == {"U-HEAT", "U-FLASH"}
    assert not {row for row, _ in entries} - holdup_rows(item)


def closed_form(state: Mapping[str, float], theta: float = 1.0) -> dict[tuple[str, str], float]:
    """T04 §6.3's table, entry by entry, from SYN-001 §2's enthalpies (the provider's functions)."""
    m: dict[tuple[str, str], float] = {}
    for i, c in enumerate(COMPONENTS):
        m[(f"U-HEAT:HEAT-mole:{c}", f"S3.vap.{c}")] = theta
        m[(f"U-HEAT:HEAT-mole:{c}", f"S3.liq.{c}")] = theta
        m[(f"U-FLASH:FLASH-mole:{c}", f"S4.n.{c}")] = theta
        m[(f"U-FLASH:FLASH-mole:{c}", f"S5.n.{c}")] = theta
        m[("U-HEAT:HEAT-duty", f"S3.vap.{c}")] = theta * h_vapor(state["S3.T"], i)
        m[("U-HEAT:HEAT-duty", f"S3.liq.{c}")] = theta * h_liquid(state["S3.T"], state["S3.P"], i)
        m[("U-FLASH:FLASH-duty", f"S4.n.{c}")] = theta * h_vapor(state["S4.T"], i)
        m[("U-FLASH:FLASH-duty", f"S5.n.{c}")] = theta * h_liquid(state["S5.T"], state["S5.P"], i)
    total = {
        stream: sum(state[f"{stream}.{c}"] for c in COMPONENTS)
        for stream in ("S3.vap", "S3.liq", "S4.n", "S5.n")
    }
    m[("U-HEAT:HEAT-duty", "S3.T")] = theta * C_P * (total["S3.vap"] + total["S3.liq"])
    m[("U-HEAT:HEAT-duty", "S3.P")] = theta * sum(
        state[f"S3.liq.{c}"] * V_MOLAR[i] for i, c in enumerate(COMPONENTS)
    )
    m[("U-FLASH:FLASH-duty", "S4.T")] = theta * C_P * total["S4.n"]
    m[("U-FLASH:FLASH-duty", "S5.T")] = theta * C_P * total["S5.n"]
    m[("U-FLASH:FLASH-duty", "S5.P")] = theta * sum(
        state[f"S5.n.{c}"] * V_MOLAR[i] for i, c in enumerate(COMPONENTS)
    )
    return m


@pytest.mark.parametrize("where", ["root", "OFF-A"])
def test_a13_every_entry_is_the_closed_form(where: str) -> None:
    """T04 §6.3 at the P01 root (r = 0.95) and at OFF-A: every entry the mapping produces is the
    table's (the vapour's pressure entries are the provider's declared zero), 1e-9 relative."""
    item = case(HIGH)
    state = root(HIGH)[0] if where == "root" else start(item, "OFF-A")
    entries = region_mass(item).entries_at(state, item.flowsheet.provider, context_of(item))
    expected = closed_form(state)
    assert set(expected) <= set(entries)
    for key, value in entries.items():
        target = expected.get(key, 0.0)
        assert abs(value - target) <= RELATIVE * max(1.0, abs(target)), (key, value, target)
    assert {key for key in entries if key not in expected} == {("U-FLASH:FLASH-duty", "S4.P")}


def test_a13_a_pinned_column_drops_out_of_m_with_the_column() -> None:
    """In a `LIQUID` heater attempt the vapour columns are pinned, so `M` has no column for them;
    the mole rows keep their liquid entries."""
    item = case(HIGH)
    state, regimes = root(HIGH)
    assert regimes["U-HEAT"] == "LIQUID"
    problem, free, rows, x = ptc_problem_at(item, state, regimes)
    matrix = problem.mass(x).toarray()
    assert "S3.vap.A" not in free and "S3.liq.A" in free
    row = rows.index("U-HEAT:HEAT-mole:A")
    assert matrix[row, free.index("S3.liq.A")] == 1.0
    assert np.count_nonzero(matrix[row]) == 1


# ------------------------------------------------------------------ A14: ADV-04, the refusals


class SpiedCompiled:
    """The compiled problem, recording every residual and Jacobian call and delegating it."""

    def __init__(self, inner: Any, trace: Trace | None = None) -> None:
        self._inner, self._trace = inner, trace
        self.metadata = inner.metadata
        self.calls: list[tuple[str, int | None, EvaluationContext]] = []

    def _attempt(self) -> int | None:
        return self._trace.events[-1].attempt if self._trace and len(self._trace) else None

    def residual(self, x: Any, context: EvaluationContext) -> Any:
        self.calls.append(("residual", self._attempt(), context))
        return self._inner.residual(x, context)

    def jacobian(self, x: Any, context: EvaluationContext) -> Any:
        self.calls.append(("jacobian", self._attempt(), context))
        return self._inner.jacobian(x, context)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def mixer_double() -> MassMapping:
    """The registered mapping plus an entry on the mixer's `MIX-mole` rows (ADV-04, first)."""
    from openflowsheet.models.syn001 import MOLE, mixer

    def outflows(
        wiring: Wiring, components: Sequence[str], phase: object = None
    ) -> tuple[PhaseOutflow, ...]:
        stream = wiring.one("outlet")
        flows = tuple(flow_id(stream, c) for c in components)
        return (PhaseOutflow("LIQUID", flows, temperature_id(stream), pressure_id(stream)),)

    registered = syn001_residence_time(COMPONENTS)
    rule = ModelMassRule(
        mixer.MODEL_ID,
        {"MIX-mole": HoldupRule("component_moles", MOLE)},
        outflows,
        {equation.equation_id: equation for equation in mixer.EQUATIONS},
    )
    return replace(registered, rules={**registered.rules, mixer.MODEL_ID: rule})


def flash_without_duty() -> MassMapping:
    """The registered mapping with the flash's `FLASH-duty` entry removed (ADV-04, second)."""
    registered = syn001_residence_time(COMPONENTS)
    flash_rule = registered.rules["syn001.tp_flash"]
    holdups = {k: v for k, v in flash_rule.holdups.items() if k != "FLASH-duty"}
    rule = replace(flash_rule, holdups=holdups)
    return replace(registered, rules={**registered.rules, "syn001.tp_flash": rule})


def wrong_dimension() -> MassMapping:
    """The heater's mole holdup declared in mol/s instead of mol (V4)."""
    registered = syn001_residence_time(COMPONENTS)
    heater_rule = registered.rules["syn001.tp_heater"]
    holdups = {**heater_rule.holdups, "HEAT-mole": HoldupRule("component_moles", MOLAR_FLOW)}
    rule = replace(heater_rule, holdups=holdups)
    return replace(registered, rules={**registered.rules, "syn001.tp_heater": rule})


def first_holdup_row(item: Case) -> str:
    return next(row for row in item.region.row_ids if row in holdup_rows(item))


@pytest.mark.parametrize(
    ("label", "mapping", "ptc", "message"),
    [
        (
            "ADV-04 an entry on a mixer row",
            mixer_double(),
            PtcPolicy(),
            "ptc_mapping_invalid(U-MIX:MIX-mole:A, not_holdup_balance)",
        ),
        (
            "ADV-04 no FLASH-duty entry",
            flash_without_duty(),
            PtcPolicy(),
            "ptc_mapping_invalid(U-FLASH:FLASH-duty, missing)",
        ),
        ("V1 no mapping at all", None, PtcPolicy(), "first-holdup-row:missing"),
        ("V3 θ = 0", "registered", PtcPolicy(residence_time_s=0.0), "first-holdup-row:residence"),
        ("V4 a wrong dimension", wrong_dimension(), PtcPolicy(), "first-holdup-row:dimension"),
    ],
)
def test_a14_an_invalid_mapping_is_refused_before_anything_runs(
    label: str, mapping: Any, ptc: PtcPolicy, message: str
) -> None:
    """T04 §7.2: the first failing check ends the solve `PTC_MAPPING_INVALID` with its R0 message —
    no `attempt_opened`, no event at all, no residual or Jacobian call; the failure bundle's class
    is "model domain/conservation/derivative defects" and its action `report_defect` (ADR 0010 D8).
    """
    from openflowsheet.verify.failure import bundle_for

    item = case(HIGH)
    first = first_holdup_row(item)
    assert first == "U-HEAT:HEAT-mole:A"
    if message.startswith("first-holdup-row:"):
        check = {"missing": "missing", "residence": "residence_time", "dimension": "dimension"}
        message = f"ptc_mapping_invalid({first}, {check[message.split(':')[1]]})"
    trace = Trace()
    spied = SpiedCompiled(item.compiled, trace)
    result = solve(
        item, start(item, "OFF-A"), ptc=ptc, trace=trace, mapping=mapping, compiled=spied
    )
    assert result.outcome == "PTC_MAPPING_INVALID"
    assert result.message == message
    assert result.attempts == () and result.branch_provenance == ()
    assert len(trace) == 0 and spied.calls == []
    bundle = bundle_for(
        SimpleNamespace(
            outcome=result.outcome,
            counters=result.counters,
            checkpoint=result.checkpoint,
            message=result.message,
            attempts=0,
            iterations=0,
            residual_inf=float("nan"),
        ),
        trace,
    )
    assert bundle.taxonomy == "model domain/conservation/derivative defects"
    assert bundle.suggested_actions[0].action == "report_defect"


def test_a14_the_newton_core_needs_no_mapping() -> None:
    """The mapping is read only under `eo_core = "ptc"`: Newton with no mapping solves as before."""
    item = case(HIGH)
    result = solve(item, start(item, "OFF-A"), core="newton", mapping=None)
    assert result.outcome == "CONVERGED"


# ------------------------------------------------------------------ A15: equivalence, dimensions


@pytest.mark.parametrize("case_id", [NOMINAL, HIGH])
@pytest.mark.parametrize("tau", [1e-4, 1.0, 1e10])
def test_a15_at_the_p01_root_the_pseudo_step_vanishes(case_id: str, tau: float) -> None:
    """T04 §6.4: `F̃ = 0 ⇔ F = 0`, so at the root the step is the root's residual carried through
    the step matrix. §12 as amended (F14): ≤ 1e-12 + 10 (θ/Δτ) ‖F̂_σ(x*)‖∞ scaled, the second term
    the index-2 duty's 1/Δτ amplification of the root's own residual (§6.7) — measured 1.67e-12 at
    r = 0.5, Δτ = 1e-4, all of it on `U-FLASH.Q`."""
    item = case(case_id)
    state, regimes = root(case_id)
    problem, free, rows, x = ptc_problem_at(item, state, regimes)
    evaluation = problem.problem.residual(x)
    assert evaluation.values is not None
    residual = float(
        np.max(np.abs(problem.problem.scaling.scale_residual(evaluation.values, rows)))
    )
    assert residual < 1e-14
    theta = PtcPolicy().residence_time_s
    bound = 1e-12 + 10.0 * (theta / tau) * residual
    assert np.max(np.abs(scaled_step(problem, free, x, tau))) <= bound


def test_a15_every_holdup_has_its_manifests_dimension_and_its_rows_times_seconds() -> None:
    """ADR 0008 D3.2 / T04 §6.4, V4: each mapped row's holdup dimension is its manifest's `holdup`
    dimension (mol for the mole rows, J for the duty rows) and its row's dimension raised by one
    power of time, so `M ẋ` has the row's dimension."""
    from openflowsheet.models.syn001 import ENERGY, MOLE, POWER

    item = case(HIGH)
    mapping = syn001_residence_time(COMPONENTS)
    origins = {equation.equation_id: equation.origin for equation in item.spec.equations}
    for row in holdup_rows(item):
        model_id, _, equation_id = origins[row].partition("#")
        rule = mapping.rules[model_id]
        declared = rule.declared[equation_id]
        assert declared.accumulation.holdup is not None and declared.dimension is not None
        holdup = rule.holdups[equation_id].dimension
        assert tuple(declared.accumulation.holdup.dimension) == tuple(holdup)
        per_second = list(declared.dimension)
        per_second[2] += 1
        assert tuple(per_second) == tuple(holdup)
        assert holdup == (MOLE if ":HEAT-mole:" in row or ":FLASH-mole:" in row else ENERGY)
        assert declared.dimension in (MOLAR_FLOW, POWER)


# ------------------------------------------------------------------ A16: reference invariance


SHIFT = {"A": 1000.0, "B": -2000.0, "C": 500.0}


class ShiftedProvider:
    """SYN-001's provider with every component's enthalpy moved by a constant in both phases —
    another reference state. Derivatives, K-values and flashes are unchanged."""

    def __init__(self) -> None:
        self._inner = Syn001Provider()

    def describe(self) -> Any:
        return self._inner.describe()

    def evaluate_phase(self, request: PropertyRequest, context: EvaluationContext) -> Any:
        result: PropertyResult = self._inner.evaluate_phase(request, context)
        if result.status != "ok" or "h" not in request.properties:
            return result
        values = dict(result.values)
        for component, shift in SHIFT.items():
            values[f"h_{component}"] += shift
        return dataclasses.replace(result, values=values)

    def flash(self, request: Any, context: EvaluationContext) -> Any:
        return self._inner.flash(request, context)


def test_a16_the_step_is_invariant_under_an_enthalpy_reference_shift() -> None:
    """T04 §6.2, §9.7: off the split manifold (OFF-A at r = 0.95 with `S3.liq.A` + 0.1 mol/s),
    shifting every enthalpy by (1000, −2000, 500) J/mol moves the energy rows and `M` by the same
    row operation, so the PTC step is unchanged, 1e-9 relative. The residual does move — the check
    is not vacuous."""
    plain, shifted = case(HIGH), case(HIGH, ShiftedProvider())
    opened = solve(plain, start(plain, "OFF-A"), core="newton").opening
    assert opened is not None
    state, regimes = dict(opened[0]), dict(opened[1])
    state["S3.liq.A"] += 0.1
    steps, duties = [], []
    for item in (plain, shifted):
        problem, free, rows, x = ptc_problem_at(item, state, regimes)
        evaluation = problem.problem.residual(x)
        assert evaluation.values is not None
        duties.append(evaluation.values[rows.index("U-HEAT:HEAT-duty")])
        steps.append(scaled_step(problem, free, x, 1.0))
    assert abs(duties[0] - duties[1]) > 1.0
    assert np.max(np.abs(steps[0] - steps[1])) <= RELATIVE * np.max(np.abs(steps[0]))


# ------------------------------------------------------------------ A17: the loop's modes


def pencil_modes(case_id: str) -> list[complex]:
    """The finite generalized eigenvalues `s` of `(Ĵ_σ + s M̂) v = 0` at the P01 root, by QZ on the
    pencil, in increasing real part. The duties' index-2 structure gives only infinite ones."""
    item = case(case_id)
    state, regimes = root(case_id)
    problem, free, rows, x = ptc_problem_at(item, state, regimes)
    scaling = problem.problem.scaling
    row_scale, column_scale = scaling.row_vector(rows), scaling.column_vector(free)
    sigma = row_signs(rows, problem.row_accumulation)
    jacobian = np.asarray(problem.problem.jacobian(x).toarray())
    mass = np.asarray(problem.mass(x).toarray())
    j_hat = (sigma / row_scale)[:, None] * jacobian * column_scale[None, :]
    m_hat = (1.0 / row_scale)[:, None] * mass * column_scale[None, :]
    values = la.eigvals(j_hat, -m_hat)
    finite = [complex(v) for v in values if np.isfinite(v)]
    assert len(values) - len(finite) == len(free) - 6
    return sorted(finite, key=lambda v: (v.real, v.imag))


def registered_modes(key: str) -> list[float]:
    return [float(v) for v in REF["closed_form"]["loop_modes"][key]["finite_modes_per_second"]]


@pytest.mark.parametrize(("case_id", "key"), [(NOMINAL, "r=0.50"), (HIGH, "r=0.95")])
def test_a17_the_pencil_has_the_six_closed_form_modes(case_id: str, key: str) -> None:
    """T04 §6.6, A17 as amended (F14): six finite modes. The four simple ones real (|Im s| ≤ 1e-9
    |s|), negative, and equal to `ref.closed_form.loop_modes` to 1e-9 relative. The double mode at
    −1/θ is a Jordan pair (the loop's vapour direction with θ_H = θ_F), which double precision
    splits by O(√ε) — measured ±2.1e-9 i at r = 0.5, ±2.5e-8 i at r = 0.95: each member within
    1e-6 relative of −1/θ, their mean equal to −1/θ to 1e-9."""
    modes = pencil_modes(case_id)
    expected = registered_modes(key)
    assert len(modes) == len(expected) == 6
    pole = -1.0 / PtcPolicy().residence_time_s
    pair = [value for value in modes if abs(value - pole) <= 1e-6 * abs(pole)]
    simple = [value for value in modes if value not in pair]
    assert len(pair) == 2 and sum(1 for target in expected if target == pole) == 2
    assert abs(sum(pair) / 2 - pole) <= RELATIVE * abs(pole)
    for value, target in zip(
        sorted(simple, key=lambda v: v.real),
        [target for target in expected if target != pole],
        strict=True,
    ):
        assert abs(value.imag) <= RELATIVE * abs(value)
        assert value.real < 0.0
        assert abs(value - target) <= RELATIVE * abs(target), (value, target)


# ------------------------------------------------------------------ A18: time-scale invariance


def test_a18_theta_and_every_tau_constant_times_eight_reproduce_off_a_bit_for_bit() -> None:
    """T04 §6.5: `M = θ M₁`, so the step depends on Δτ/θ only and SER is multiplicative. Scaling θ,
    τ₀, τ_min and τ_max by 8 — a power of two, exact in binary — gives the same attempts and
    pseudo-step counts and bit-identical accepted states."""
    item = case(HIGH)
    registered = PtcPolicy()
    scaled = replace(
        registered,
        residence_time_s=8.0 * registered.residence_time_s,
        tau_initial_s=8.0 * registered.tau_initial_s,
        tau_min_s=8.0 * registered.tau_min_s,
        tau_max_s=8.0 * registered.tau_max_s,
    )
    base = solve(item, start(item, "OFF-A"))
    eight = solve(item, start(item, "OFF-A"), ptc=scaled)
    assert base.outcome == eight.outcome == "CONVERGED"
    assert [a.iterations for a in base.attempts] == [a.iterations for a in eight.attempts] == [30]
    for one, other in zip(base.attempts, eight.attempts, strict=True):
        assert one.ptc is not None and other.ptc is not None
        for a, b in zip(one.ptc.steps, other.ptc.steps, strict=True):
            assert np.array_equal(a.x, b.x), a.index
            assert b.tau == 8.0 * a.tau and a.alpha == b.alpha
    assert all(
        base.state[name] == eight.state[name] or (math.isnan(base.state[name]))
        for name in base.state
    )


# ------------------------------------------------------------------ A21: the accumulation identity


@dataclass(frozen=True)
class IdentityDefect:
    """One mole row on one accepted pseudo-step (T04 §6.5)."""

    defect: float
    #: max(|F_r(x_k)|, |F_r(x_{k+1})|, tol_r)
    scale: float
    #: Σ |flows| of the row's holdup at both states — what the identity's roundings are of.
    operands: float
    tau: float


def identity_defects(item: Case, result: RegionResult) -> list[IdentityDefect]:
    """T04 §6.5 on every accepted pseudo-step, for each mole row of the attempt: the defect of
    `F_r(x_{k+1}) = (1 − α) F_r(x_k) + (N_r(x_{k+1}) − N_r(x_k))/Δτ_k`. `N_r` is the mapping's
    (θ times the phase-resolved outflow of component r)."""
    mass = region_mass(item)
    assert result.opening is not None
    base = dict(result.opening[0])
    defects: list[IdentityDefect] = []
    for attempt in result.attempts:
        assert attempt.ptc is not None
        free, rows, _ = attempt_system(item, dict(attempt.signature))
        mole_rows = [row for row in rows if ":HEAT-mole:" in row or ":FLASH-mole:" in row]
        for step in attempt.ptc.steps:
            before, after = dict(base), dict(base)
            before.update(zip(free, (float(v) for v in step.x_before), strict=True))
            after.update(zip(free, (float(v) for v in step.x), strict=True))
            entries = mass.entries_at(before, item.flowsheet.provider, context_of(item))
            for row in mole_rows:
                i = rows.index(row)
                held = [(column, value) for (r, column), value in entries.items() if r == row]
                accumulated = sum(value * (after[c] - before[c]) for c, value in held)
                predicted = (1.0 - step.alpha) * step.residual_before[i] + accumulated / step.tau
                tolerance = KIND_TOLERANCE[item.spec.row_kinds[row]]
                defects.append(
                    IdentityDefect(
                        defect=abs(step.residual[i] - predicted),
                        scale=max(abs(step.residual[i]), abs(step.residual_before[i]), tolerance),
                        operands=sum(abs(after[c]) + abs(before[c]) for c, _ in held),
                        tau=step.tau,
                    )
                )
        base = dict(attempt.end_state)
    assert defects
    return defects


@pytest.mark.parametrize("key", list(NAMED_RUNS))
def test_a21_the_accumulation_identity_at_the_registered_tolerance(key: str) -> None:
    """T04 §12 as amended (F14): `|lhs − rhs| ≤ 1e-9 max(|F_r(x_k)|, |F_r(x_{k+1})|, tol_r)
    + 1e-13 (1 + θ/Δτ_used)` mol/s on every accepted pseudo-step and mole row — measured ≤ 1.3e-15
    mol/s. A sign error or a missing mass entry moves it by the whole accumulation term."""
    item = case(NAMED_RUNS[key][0])
    result, _ = named(key)
    theta = PtcPolicy().residence_time_s
    for entry in identity_defects(item, result):
        assert entry.defect <= RELATIVE * entry.scale + 1e-13 * (1.0 + theta / entry.tau)


@pytest.mark.parametrize("key", list(NAMED_RUNS))
def test_a21_the_accumulation_identity_at_the_double_floor(key: str) -> None:
    """Beside §12's bound: every defect within four ulps of the operands the identity sums (the
    flows of the row's holdup at both states), amplified by `1 + θ/Δτ` — the holdup difference is
    divided by Δτ, so its rounding is too (a basin run measured 4.1e-14 mol/s at Δτ = 2.6e-3 s,
    above the un-amplified floor; the first version of this check left the factor out and held
    only because the named runs never take so small a pseudo-step)."""
    theta = PtcPolicy().residence_time_s
    item = case(NAMED_RUNS[key][0])
    result, _ = named(key)
    for entry in identity_defects(item, result):
        assert entry.defect <= 4.0 * EPS * entry.operands * (1.0 + theta / entry.tau)


def _a21_holds(item: Any, result: RegionResult) -> int:
    """§12's A21 bound and the four-ulp floor on every accepted pseudo-step of `result`; returns
    the number of row-steps checked."""
    theta = PtcPolicy().residence_time_s
    defects = identity_defects(item, result)
    for entry in defects:
        assert entry.defect <= RELATIVE * entry.scale + 1e-13 * (1.0 + theta / entry.tau)
        assert entry.defect <= 4.0 * EPS * entry.operands * (1.0 + theta / entry.tau)
    return len(defects)


def test_a21_the_accumulation_identity_on_every_basin_ptc_run() -> None:
    """T04 review S3: A21 is "every registered SYN-001 PTC run" — the 18 admitted basin starts
    under PTC (A23) as well as the named runs (measured by the review: 3 954 row-steps, worst
    defect / bound 3.09e-2). Each run is the harness's own region solve."""
    from benchmarks.t04.basin import basin_comparison

    item = case(HIGH)
    comparison = basin_comparison(("ptc",))
    assert len(comparison.admitted) == 18
    checked = sum(_a21_holds(item, start.runs["ptc"].result) for start in comparison.admitted)
    assert checked > 0


def test_a21_the_accumulation_identity_on_phs_05_under_ptc() -> None:
    """PHS-05 under PTC (A24) is a registered SYN-001 PTC run too: its accepted pseudo-step, on the
    A02 region's mole rows."""
    run = phs05_run()
    item = SimpleNamespace(
        flowsheet=run.item.binding.flowsheet,
        spec=run.item.binding.spec,
        region=run.region,
        compiled=compile_problem(run.item.binding.spec),
    )
    assert _a21_holds(item, run.failed) > 0


# ------------------------------------------------------------------ A22, A23: the named runs


def same_cause(recorded: str, registered: str | None, closing: str) -> bool:
    """A provenance item's cause against `ref`'s, byte for byte in T03 §4.10's grammar (§12's
    conventions, F11). A terminal item's cause is the solve's closing message (ADR 0005 D7), which
    `ref` registers as null; it is compared with the closing message instead."""
    if registered is None:
        return recorded == closing
    return recorded == registered


@pytest.mark.parametrize("core", ["newton", "ptc"])
@pytest.mark.parametrize("key", list(NAMED_RUNS))
def test_a23_the_named_run_takes_the_registered_path(key: str, core: str) -> None:
    """T04 §9.5 (W0.2 first): outcome; per attempt the signature, opening source, core, core
    outcome, iterations (accepted pseudo-steps for PTC), decision and cause; for PTC the rejected
    trials, the polish verdict, the landings (`α_max` 1e-9 relative) and `blocked_by`; the final
    state P01's root within T02 A28's allowances."""
    item = case(NAMED_RUNS[key][0])
    result, _ = named(key, core)
    expected = NAMED[key][core]
    assert result.outcome == expected["outcome"]
    assert len(result.attempts) == len(expected["attempts"])
    for attempt, item_, registered in zip(
        result.attempts, result.branch_provenance, expected["attempts"], strict=True
    ):
        assert ",".join(f"{u}:{g}" for u, g in attempt.signature) == registered["signature"]
        assert item_["opening_source"] == registered["opening_source"]
        assert item_["core"] == registered["core"] == core
        assert attempt.solver_outcome == item_["core_outcome"] == registered["core_outcome"]
        assert attempt.iterations == item_["iterations"] == registered["iterations"]
        assert item_["decision"] == registered["decision"]
        assert same_cause(item_["cause"], registered["cause"], result.message)
        if core == "ptc":
            assert attempt.ptc is not None
            assert len(attempt.ptc.rejections) == registered["rejected_trials"]
            assert attempt.ptc.polish == registered["polish"]
            landings = [s for s in attempt.ptc.steps if s.landing]
        else:
            assert attempt.ptc is None
            landings = []
        if "landings" in registered and core == "ptc":
            assert len(landings) == len(registered["landings"])
            for step, landing in zip(landings, registered["landings"], strict=True):
                assert step.index == landing["iteration"]
                assert list(step.landing) == landing["variables"]
                target = float(landing["alpha_max"])
                assert abs(step.alpha - target) <= RELATIVE * target
        if "blocked_by" in registered:
            assert result.attempts[result.attempts.index(attempt)].solver_outcome == "BOUND_BLOCKED"
    assert not disagreement(item, result.state)


def full(item: Case, result: RegionResult, x: np.ndarray, signature: Any) -> dict[str, float]:
    free, _, _ = attempt_system(item, dict(signature))
    state = dict(result.state)
    state.update(zip(free, (float(v) for v in x), strict=True))
    return state


@pytest.mark.parametrize("key", list(NAMED_RUNS))
def test_a22_every_named_stop_is_polished_and_the_unpolished_envelope_is_registered(
    key: str,
) -> None:
    """T04 §7.5: every PTC stop after ≥ 1 pseudo-step records exactly one polish trial, accepted;
    the stop it replaced has K04's material envelope at the registered multiple of τ (printed to
    four digits) — 1.31 τ at OFF-B — and the polished state's is at roundoff."""
    from openflowsheet.verify.checks import material_checks

    item = case(NAMED_RUNS[key][0])
    result, trace = named(key)
    last = result.attempts[-1]
    assert last.ptc is not None and last.ptc.polish == "accepted"
    assert last.ptc.stopped_x is not None
    polish_trials = [e for e in trace.of_kind("trial") if e.message.startswith("polish")]
    assert [(e.message, e.trial_status, e.pseudo_step) for e in polish_trials] == [
        ("polish", "accepted", None)
    ]

    def envelope(state: Mapping[str, float]) -> float:
        checks = material_checks(state, item.flowsheet.split_fraction)
        return max(
            abs(c.value) / c.tolerance
            for c in checks
            if c.id.startswith("material_balance.envelope") and c.value is not None
        )

    unpolished = envelope(full(item, result, last.ptc.stopped_x, last.signature))
    registered = NAMED[key]["ptc"]["unpolished_envelope_over_tolerance"]
    digits = len(registered.split(".")[1])
    assert abs(unpolished - float(registered)) <= 0.5 * 10.0**-digits
    assert envelope(result.state) < 1e-6
    if key == "r=0.95/OFF-B":
        assert unpolished >= 1.3


@pytest.mark.parametrize("key", list(NAMED_RUNS))
def test_a22_k04_verifies_every_polished_stop_and_fails_the_unpolished_off_b(key: str) -> None:
    """W0.3's PTC half: K04 `VERIFIED` on every polished named PTC solve; on the unpolished OFF-B
    stop `FAILED` with `false_success_detected`, by its §8.1 envelope rule — the polish is what the
    registered verdicts rest on (register R-033). Each is an EO region solve of the nominal
    declaration, certified under T04 §4.8's guard from the region result itself (its state and
    root fingerprint), with an empty tear; the unpolished stop is K04 §9's `state=` override."""
    from openflowsheet.verify.certificate import verify

    item = case(NAMED_RUNS[key][0])
    result, _ = named(key)
    last = result.attempts[-1]
    assert last.ptc is not None and last.ptc.stopped_x is not None
    polished = verify(item.flowsheet, result)
    assert (polished.verification_status, polished.false_success_detected) == ("VERIFIED", False)
    assert polished.transformations["tear"] == {"variable_ids": [], "row_ids": []}
    assert polished.root_fingerprint == result.root_fingerprint
    stopped = verify(
        item.flowsheet, result, state=full(item, result, last.ptc.stopped_x, last.signature)
    )
    if key == "r=0.95/OFF-B":
        assert (stopped.verification_status, stopped.false_success_detected) == ("FAILED", True)
        assert {c.id for c in stopped.checks if c.result == "fail"} == {
            "material_balance.envelope.C"
        }
    else:
        assert stopped.verification_status == "VERIFIED"


def test_a25_the_first_trial_of_every_ptc_attempt_is_at_tau_initial() -> None:
    """T04 §7.4's reset: every attempt's SER state opens at τ₀ = θ = 1 s, whatever the previous
    attempt ended at (OFF-B's first attempt ends on a proposal of its own)."""
    for key in NAMED_RUNS:
        result, trace = named(key)
        firsts: dict[int, float] = {}
        for event in trace.events:
            if event.pseudo_step is not None and event.attempt not in firsts:
                firsts[event.attempt] = event.pseudo_step
        assert firsts == dict.fromkeys(range(len(result.attempts)), 1.0), key
        assert all(attempt.ptc is not None for attempt in result.attempts)
    result, _ = named("r=0.95/OFF-B")
    first = result.attempts[0].ptc
    assert first is not None and first.tau_end != 1.0


def test_a25_every_call_inside_a_ptc_attempt_is_that_attempts() -> None:
    """[A01] (T03 A03's spy) on OFF-B at r = 0.95, two PTC attempts: every residual and Jacobian
    call and every enthalpy the mass matrix asks for takes the context of the attempt in progress,
    and each attempt has its own."""
    item = case(HIGH)
    trace = Trace()
    spied = SpiedCompiled(item.compiled, trace)
    mass_contexts: list[tuple[int | None, EvaluationContext]] = []
    original = RegionMass.entries_at

    def recording(self: RegionMass, state: Any, provider: Any, context: Any) -> Any:
        mass_contexts.append((trace.events[-1].attempt if len(trace) else None, context))
        return original(self, state, provider, context)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(RegionMass, "entries_at", recording)
        result = solve(item, start(item, "OFF-B"), trace=trace, compiled=spied)
    assert len(result.attempts) == 2 and result.outcome == "CONVERGED"
    contexts = [c.evaluation_context for c in result.contexts]
    assert contexts[0] is not contexts[1]
    assert spied.calls and mass_contexts
    for _, attempt, context in spied.calls:
        assert attempt is not None and context is contexts[attempt]
    for attempt, context in mass_contexts:
        assert attempt is not None and context is contexts[attempt]
    assert [c.core for c in result.contexts] == ["ptc", "ptc"]


# ------------------------------------------------------------------ A24: PHS-05 under PTC


@dataclass
class Phs05:
    item: Any
    region: Any
    failed: RegionResult
    trace: Trace


def phs05(core: str = "ptc") -> Phs05:
    """PHS-05 (`SYN-001-A02-355-dew-guess`) as a direct region solve, edge 3 off (T04 §9.6)."""
    from test_t02_a02 import revision, structure, the_region

    from openflowsheet.orchestrator.tear import solve_tear

    item = structure(revision("SYN-001-A02-355-dew-guess"))
    flowsheet = item.binding.flowsheet
    policy = eo_policy(core)
    pre, _ = solve_tear(flowsheet, policy=policy)
    assert pre.final_state is not None
    region = the_region(item)
    trace = Trace()
    failed = solve_region(
        compiled=compile_problem(item.binding.spec),
        spec=item.binding.spec,
        region=region,
        state=dict(pre.final_state),
        splits=syn001_lifted_splits(flowsheet.components),
        provider=flowsheet.provider,
        policy=policy,
        trace=trace,
        initializer_source="user_guess",
        mass_mapping=syn001_residence_time(flowsheet.components),
    )
    return Phs05(item, region, failed, trace)


_PHS05: dict[str, Phs05] = {}


def phs05_run() -> Phs05:
    if "ptc" not in _PHS05:
        _PHS05["ptc"] = phs05()
    return _PHS05["ptc"]


def test_a24_phs_05_under_ptc_takes_the_registered_path() -> None:
    """T04 §9.6: `TWO_PHASE` — the first pseudo-step lands `S3.vap.C` at Newton's `α_max`, then 11
    `bound_blocked` trials → the vapour leaves; `LIQUID` — 11 `phase_update_required` trials →
    `PTC_STALLED` with the wall in the window (row 4), the first candidate; `VAPOR` — 11
    `invalid_trial` trials → `PTC_STALLED`, the kernel agrees → terminal `PTC_STALLED`."""
    expected = REF["policy_simulation"]["ptc_phs05"]
    run = phs05_run()
    result = run.failed
    assert result.outcome == expected["outcome"] == "PTC_STALLED"
    reasons = {
        0: {"bound_blocked"},
        1: {"phase_update_required"},
        2: {"invalid_trial"},
    }
    for index, (attempt, item, registered) in enumerate(
        zip(result.attempts, result.branch_provenance, expected["attempts"], strict=True)
    ):
        assert ",".join(f"{u}:{g}" for u, g in attempt.signature) == registered["signature"]
        assert item["opening_source"] == registered["opening_source"]
        assert item["core"] == registered["core"] == "ptc"
        assert attempt.solver_outcome == registered["core_outcome"]
        assert attempt.iterations == registered["iterations"]
        assert item["decision"] == registered["decision"]
        assert same_cause(item["cause"], registered["cause"], result.message)
        if registered["decision"] == "terminal":
            assert item["cause"] == result.message
            assert result.message == "pseudo-step 0: 11 trials rejected, the last invalid_trial"
        assert attempt.ptc is not None
        assert len(attempt.ptc.rejections) == registered["rejected_trials"] == 11
        assert {r.reason for r in attempt.ptc.rejections} == reasons[index]
        assert attempt.ptc.polish is registered["polish"] is None
    first = result.attempts[0].ptc
    assert first is not None
    (landing,) = [step for step in first.steps if step.landing]
    (registered_landing,) = expected["attempts"][0]["landings"]
    assert landing.landing == ("S3.vap.C",) == tuple(registered_landing["variables"])
    newton_alpha = float(
        REF["policy_simulation"]["homotopy_cases"]["HOM-01"]["contract"]["attempts"][0]["landings"][
            0
        ]["alpha_max"]
    )
    assert abs(landing.alpha - newton_alpha) <= RELATIVE * newton_alpha
    assert abs(landing.alpha - float(registered_landing["alpha_max"])) <= RELATIVE


def test_a24_the_algebraic_components_of_the_step_are_newtons_at_every_pseudo_step() -> None:
    """T04 §6.7: on PHS-05's opening, the PTC step's `S3.T`, split and `U-FLASH.Q` components equal
    Newton's at Δτ ∈ {1e-3, 1, 1e3} — the algebraic rows are Newton-solved whatever Δτ — 1e-9
    relative; the inventory components are not (the check is not vacuous)."""
    import scipy.sparse as sp

    from openflowsheet.numerics.linear import solve_linear

    run = phs05_run()
    opened = run.failed.opening
    assert opened is not None
    state, regimes = dict(opened[0]), dict(opened[1])
    item = SimpleNamespace(
        flowsheet=run.item.binding.flowsheet,
        spec=run.item.binding.spec,
        region=run.region,
        compiled=compile_problem(run.item.binding.spec),
    )
    problem, free, rows, x = ptc_problem_at(item, state, regimes)  # type: ignore[arg-type]
    evaluation = problem.problem.residual(x)
    assert evaluation.values is not None
    scaling = problem.problem.scaling
    j_hat = (
        sp.diags(1.0 / scaling.row_vector(rows))
        @ sp.csc_matrix(problem.problem.jacobian(x))
        @ sp.diags(scaling.column_vector(free))
    )
    newton, _ = solve_linear(sp.csc_matrix(j_hat), -scaling.scale_residual(evaluation.values, rows))
    algebraic = [
        j
        for j, name in enumerate(free)
        if name != "U-HEAT.Q" and not name.startswith(("S2.", "S4.", "S5.", "S6.", "S7.", "S3.n"))
    ]
    assert {free[j] for j in algebraic} >= {"S3.T", "U-FLASH.Q", "S3.vap.C", "S3.liq.C"}
    others = [j for j in range(len(free)) if j not in algebraic]
    scale = float(np.max(np.abs(newton)))
    for tau in (1e-3, 1.0, 1e3):
        step = scaled_step(problem, free, x, tau)
        assert np.max(np.abs(step[algebraic] - newton[algebraic])) <= RELATIVE * scale, tau
        assert np.max(np.abs(step[others] - newton[others])) > 1e-6 * scale, tau


def test_a24_with_edge_3_phs_05_under_ptc_converges_through_the_homotopy() -> None:
    """With the default `eo_recovery`, edge 3 fires on `PTC_STALLED` and the continuation — Newton
    correctors, T04 §4.5 — converges as in HOM-01."""
    from test_t04_edge3 import case_document, case_policy, plan_run, region_step

    policy = case_policy("HOM-01", GlobalizationPolicy(eo_core="ptc"))
    result = plan_run(case_document("HOM-01"), policy).result
    step = region_step(result)
    expected = REF["policy_simulation"]["ptc_phs05"]
    assert result.outcome == expected["with_edge3"] == "CONVERGED"
    assert step.eo_recovery == "taken"
    assert step.recovered_from.outcome == "PTC_STALLED"
    assert [item["core"] for item in step.detail.branch_provenance] == [
        "ptc",
        "ptc",
        "ptc",
        "homotopy",
    ]


# ------------------------------------------------------------------ A25: decide's rows 4–5


def test_a25_decide_is_the_one_function_and_rows_4_and_5_take_ptc_stalled() -> None:
    """ADR 0010 D6 on PHS-05 under PTC: every attempt closes through `phase_contract.decide`, and
    the `LIQUID` attempt's `PTC_STALLED` with the wall in the window is row 4 (a restart at the
    first candidate), the `VAPOR` attempt's without a wall row 5 (the kernel agrees: terminal)."""
    seen: list[tuple[str, str, str]] = []
    original = region_module.decide

    def spy(result: Any, **kwargs: Any) -> Any:
        decision = original(result, **kwargs)
        seen.append((result.outcome, decision.kind, decision.cause or decision.message))
        return decision

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "decide", spy)
        result = phs05().failed
    assert result.outcome == "PTC_STALLED"
    assert [(outcome, kind) for outcome, kind, _ in seen] == [
        ("BOUND_BLOCKED", "restart"),
        ("PTC_STALLED", "restart"),
        ("PTC_STALLED", "terminal"),
    ]
    assert seen[1][2] == "phase_wall(stall, U-HEAT:LIQUID->VAPOR)"


@pytest.mark.parametrize(
    ("label", "outcome", "budget", "wall_at", "asked", "expected"),
    [
        ("row 4: PTC_STALLED, wall in window", "PTC_STALLED", None, (2,), ["at_candidate"], "r"),
        ("row 5: PTC_STALLED, no wall", "PTC_STALLED", None, (), ["kernel_disagrees"], "t"),
        ("row 5: ptc_steps", "BUDGET_EXHAUSTED", "ptc_steps", (), ["kernel_disagrees"], "t"),
        ("row 6: property budget", "BUDGET_EXHAUSTED", "property_calls", (), [], "t"),
    ],
)  # fmt: skip
def test_a25_decide_rows_4_and_5_include_the_ptc_outcomes(
    label: str,
    outcome: str,
    budget: str | None,
    wall_at: tuple[int, ...],
    asked: list[str],
    expected: str,
) -> None:
    """T03 §4.8 as ADR 0010 D6 extends it, row by row with T03's stub `PathOps`: `PTC_STALLED`
    takes `LINE_SEARCH_FAILED`'s place in rows 4 and 5, `BUDGET_EXHAUSTED(ptc_steps)` takes
    `newton_iterations`'s in row 5; the property budget still asks nothing."""
    from test_t03_contract import LIQ, POLICY, StubOps, newton, walled

    from openflowsheet.orchestrator import phase_contract

    ops = StubOps()
    decision = phase_contract.decide(
        newton(outcome, iterations=3, budget=budget),
        attempt_index=0,
        frozen=LIQ,
        wall=walled(wall_at),
        ops=ops,
        policy=POLICY,
        used=[LIQ],
    )
    assert ops.asked[: len(asked)] == asked and len(ops.asked) <= len(asked) + 1
    assert decision.kind == {"r": "restart", "t": "terminal"}[expected]
    if expected == "t":
        assert decision.outcome == outcome


# ------------------------------------------------------------------ A28: the PTC budgets


def test_a28_off_a_with_five_pseudo_steps_exhausts_its_budget() -> None:
    """T04 A28: OFF-A (r = 0.95) under PTC with `max_steps_per_attempt = 5` ends
    `BUDGET_EXHAUSTED(ptc_steps)` after 5 pseudo-steps; the kernel agrees at the end state (row 5),
    so the attempt is terminal, and its checkpoint is the fifth iterate's, `partial`."""
    item = case(HIGH)
    result = solve(item, start(item, "OFF-A"), ptc=PtcPolicy(max_steps_per_attempt=5))
    assert result.outcome == "BUDGET_EXHAUSTED" and result.budget == "ptc_steps"
    (attempt,) = result.attempts
    assert attempt.iterations == 5 and attempt.ptc is not None and len(attempt.ptc.steps) == 5
    assert result.checkpoint is not None and result.checkpoint.label == "partial"
    assert result.branch_provenance[0]["core"] == "ptc"


def test_a28_a_property_refusal_inside_a_pseudo_step_keeps_everything() -> None:
    """T03 review S1's shape for the PTC core: the high-recycle plan under `eo`/PTC with the
    property cap set between two accepted pseudo-steps ends `BUDGET_EXHAUSTED(property_calls)` with
    the cap spent exactly, the attempt, its `partial` checkpoint and its `ptc` provenance item
    kept."""
    from test_t04_edge3 import plan_run, region_step

    document = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "cases" / f"{HIGH}.yaml").read_text()
    )
    free = plan_run(document, eo_policy()).result
    accepted = [
        event.counters.property_calls
        for event in free.trace.of_kind("step_accepted")
        if event.pseudo_step is not None
    ]
    assert len(accepted) == 39
    cap = (accepted[10] + accepted[11]) // 2
    assert accepted[10] < cap < accepted[11]
    result = plan_run(document, eo_policy(max_property_calls=cap)).result
    step = region_step(result)
    assert result.outcome == "BUDGET_EXHAUSTED"
    assert result.counters.property_calls == cap
    detail = step.detail
    assert detail.budget == "property_calls"
    assert len(detail.attempts) == 1 and detail.attempts[0].iterations == 11
    assert [item["core"] for item in detail.branch_provenance] == ["ptc"]
    assert step.checkpoint is not None and step.checkpoint.label == "partial"
