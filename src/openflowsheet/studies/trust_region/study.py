"""The C1 study's formulation `c1-trf-study-v1` (M05 design note §7.1; ADR 0039 D1, D2; R-267).

WO-5 built the formulation and its projection; WO-6 the loop (§7.2-§7.5; module part two), its
readiness (§6.8) and its record (§9.1). The formulation is **generated** from the bound revision,
the bound variant's boundary block and the admissibility definitions, never authored per case:

- **Case.** A revision binding of the C1 loop `C1-LOOP-M02-v1` (M02 design note §8.1), at the
  coupled route's inner problem: the embedded reactor pinned at w₀ (`with_coupling`, M02's
  accessor), its coupling parameters promoted to the link variables (X̂, ΔT̂) (ADR 0038 D3).
- **Decision.** The outlet-temperature specification of the `c1.tp_heater` that feeds the
  reactor (its `T_spec`, a pinned input, ADR 0031 D1), in a registered box: [653.15, 693.15] K for
  the REAL study (R-313: v3's T_in span, superseding ADR 0039 D1's [643.15, 733.15] K) and for
  TR-E2 and the loops.
  The purge fraction stays the revision's (0.02).
- **Objective `c1-obj-nh3-liquid-v1`.** Maximize the NH₃ molar flow of the `c1.tp_flash`'s liquid
  outlet, mol/s, scale 1.
- **Constraints**, from the variant's `boundary.hard_domain` and M04 spec §3.2's A(s):
  T_in and P_in as bounds on the reactor-inlet variables; 1 ≤ H₂/N₂ ≤ 4 as lo·n_N₂ − n_H₂ ≤ 0 and
  n_H₂ − hi·n_N₂ ≤ 0; inerts as n_Ar + n_CH₄ − inert_max·Σn ≤ 0; for a variant with a per-tube
  flow bound, lo ≤ Σn/N_tubes ≤ hi; X̂ ≤ r/3 as 3 X̂ n_N₂ − n_H₂ ≤ 0. X̂ ∈ [0, 0.95] and
  ΔT̂ ∈ [−50, 250] K are the link variables' bounds, the provider's domain bounds every stream T
  and P, and molar flows are non-negative (the projection's own bounds, §6.1). Expression
  constraints carry the margin 1e-6 relative (`InequalitySpec.tightened`: none on a zero bound).
- **Stated limits, never constraints:** `extrapolated`, `synthetic`, `fd_gradient`,
  `surrogate_outside_reference_domain` (recorded by WO-6).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

from openflowsheet.adapters.variants import Variant, hard_domain
from openflowsheet.application.revision_binding import RevisionBinding, with_coupling
from openflowsheet.compile.reference import FloatAlgebra
from openflowsheet.compile.spec import Expr
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.c1.flash import TPFlash
from openflowsheet.models.c1.heater import TPHeater
from openflowsheet.models.c1.reactor import C1Reactor
from openflowsheet.studies.trust_region.checks import (
    NOT_CHECKED,
    NOT_STATIONARY_AT_DELTA,
    PARENT_LOCAL_EVIDENCE,
    CandidateCheck,
    ConstraintValue,
    Decision,
    P2Reference,
    Parent,
    ParentSolve,
    TrfPoint,
    check_candidate,
    targeted_check,
)
from openflowsheet.studies.trust_region.holders import (
    LINK_BOUNDS,
    ColdBudget,
    TruthBox,
    TruthModel,
)
from openflowsheet.studies.trust_region.trf_state import (
    RETURNS_MODEL,
    FrameworkReadiness,
    framework_readiness,
    truth_refused,
)
from openflowsheet.thermo.pr_c1 import COMPONENTS

if TYPE_CHECKING:
    from openflowsheet.studies.trust_region.projection import (
        DecisionSpec,
        ExternalLinkSpec,
        InequalitySpec,
        ObjectiveSpec,
        Projection,
    )
    from openflowsheet.studies.trust_region.trf_state import EFBasis

__all__ = [
    "BUDGET_ID",
    "IN_PROCESS_BUDGET",
    "K_MAX",
    "MARGIN_REL",
    "OBJECTIVE_ID",
    "REAL_BOX",
    "REAL_BUDGET",
    "STUDY_ID",
    "TR_E2_BOX",
    "Budgets",
    "C1Formulation",
    "StageRun",
    "StageRunner",
    "StudyBudget",
    "StudyReadiness",
    "StudyResult",
    "TrfStage",
    "c1_constraint_values",
    "c1_formulation",
    "pinned_at",
    "project_c1",
    "run_study",
    "trust_region_readiness",
]

STUDY_ID: Final = "c1-trf-study-v1"
OBJECTIVE_ID: Final = "c1-obj-nh3-liquid-v1"
#: The REAL decision box, K: R-313 (M02 seventh round) makes it v3's T_in span unconditionally,
#: superseding ADR 0039 D1's [643.15, 733.15] K (the kinetics' inlet data span, R-169).
REAL_BOX: Final = (653.15, 693.15)
#: ADR 0039 D2: TR-E2's and the loops' decision box, K.
TR_E2_BOX: Final = (653.15, 693.15)
#: §7.1: the relative margin on expression constraints.
MARGIN_REL: Final = 1e-6
#: §7.1: the objective's scale, mol/s.
OBJECTIVE_SCALE: Final = 1.0
_PROVIDER_KINDS: Final = {"T": "temperature", "P": "pressure"}


@dataclass(frozen=True)
class C1Formulation:
    """The projection's inputs for one C1 study, and where each came from."""

    reactor: str
    heater: str
    inlet_stream: str
    liquid_stream: str
    decisions: tuple[DecisionSpec, ...]
    external_links: tuple[ExternalLinkSpec, ...]
    inequalities: tuple[InequalitySpec, ...]
    objective: ObjectiveSpec
    #: The provider's declared domain by variable kind (§6.1 step 1).
    domain: Mapping[str, tuple[float, float]]
    #: The truth's hard domain on the reactor inlet's T and P (§7.1).
    variable_bounds: Mapping[str, tuple[float, float]]


def _only(found: Sequence[Any], what: str) -> Any:
    if len(found) != 1:
        raise ValueError(f"a C1 study needs exactly one {what}; the revision has {len(found)}")
    return found[0]


def _linear(terms: Sequence[tuple[float, str]]) -> Any:
    """A `RowBuilder` Σ c·v over variable ids."""

    def build(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
        total: Any = 0.0
        for coefficient, name in terms:
            total = total + coefficient * v[name]
        return total

    return build


def c1_formulation(
    binding: RevisionBinding,
    variant: Variant,
    truth: TruthModel,
    box: tuple[float, float],
) -> C1Formulation:
    """`c1-trf-study-v1`'s formulation on `binding` (the C1 loop at the coupled route's inner
    problem) for the reactor bound to `variant` and evaluated by `truth`, with the decision box
    `box` (module docstring). Raises `ValueError` for a revision that is not C1-shaped.

    The projection's specs are imported here, not at module level: this module imports in the
    default install, without Pyomo (M03's G6; WO-6's readiness answers there)."""
    from openflowsheet.studies.trust_region.projection import (
        DecisionSpec,
        ExternalLinkSpec,
        InequalitySpec,
        ObjectiveSpec,
    )

    flowsheet = binding.flowsheet
    reactor: C1Reactor = _only(
        [unit for unit in flowsheet.instances if isinstance(unit, C1Reactor)], "C1 reactor"
    )
    inlet = _only(flowsheet.wiring[reactor.unit_id].streams["inlet"], "reactor inlet")
    producer = binding.graph.producer_of(inlet)
    heater = _only(
        [
            unit
            for unit in flowsheet.instances
            if unit.unit_id == producer and isinstance(unit, TPHeater)
        ],
        "c1.tp_heater feeding the reactor",
    )
    flash: TPFlash = _only(
        [unit for unit in flowsheet.instances if isinstance(unit, TPFlash)], "c1.tp_flash"
    )
    liquid = _only(flowsheet.wiring[flash.unit_id].streams["liquid"], "flash liquid outlet")

    flows = [flow_id(inlet, name) for name in COMPONENTS]
    h2, n2, _, ar, ch4 = flows
    inlet_ids = (*flows, temperature_id(inlet), pressure_id(inlet))
    domain_block = hard_domain(variant)
    ratio_low, ratio_high = domain_block.h2_n2

    def inequality(
        name: str, build: Any, bound: float, source: str, sense: str = "<="
    ) -> InequalitySpec:
        return InequalitySpec(name, build, bound, source, MARGIN_REL, sense)  # type: ignore[arg-type]

    inequalities = [
        inequality(
            "hard_domain.h2_n2.lower",
            _linear([(ratio_low, n2), (-1.0, h2)]),
            0.0,
            "variant.boundary.hard_domain.H2_N2",
        ),
        inequality(
            "hard_domain.h2_n2.upper",
            _linear([(1.0, h2), (-ratio_high, n2)]),
            0.0,
            "variant.boundary.hard_domain.H2_N2",
        ),
        inequality(
            "hard_domain.inert_max",
            _linear(
                [(1.0, ar), (1.0, ch4)] + [(-domain_block.inert_fraction, name) for name in flows]
            ),
            0.0,
            "variant.boundary.hard_domain.inert_max",
        ),
    ]
    if domain_block.tube_flow is not None:
        per_tube = _linear([(1.0 / reactor.n_tubes, name) for name in flows])
        low, high = domain_block.tube_flow
        source = "variant.boundary.hard_domain.tube_flow_mol_s"
        inequalities.append(inequality("hard_domain.tube_flow.lower", per_tube, low, source, ">="))
        inequalities.append(inequality("hard_domain.tube_flow.upper", per_tube, high, source))
    conversion = reactor.conversion_parameter

    def h2_limit(
        v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
    ) -> Expr:
        return 3.0 * p[conversion] * v[n2] - v[h2]

    inequalities.append(inequality("admissibility.h2_limit", h2_limit, 0.0, "M04 spec §3.2 A(s)"))

    def objective(
        v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
    ) -> Expr:
        return v[flow_id(liquid, "NH3")]

    provider = flowsheet.provider.describe().domain
    return C1Formulation(
        reactor=reactor.unit_id,
        heater=heater.unit_id,
        inlet_stream=inlet,
        liquid_stream=liquid,
        decisions=(DecisionSpec(heater.temperature_parameter, box[0], box[1]),),
        external_links=(
            ExternalLinkSpec(reactor.unit_id, conversion, reactor.rise_parameter, inlet_ids, truth),
        ),
        inequalities=tuple(inequalities),
        objective=ObjectiveSpec(OBJECTIVE_ID, "maximize", objective, OBJECTIVE_SCALE),
        domain={
            _PROVIDER_KINDS[key]: (float(value[0]), float(value[1]))
            for key, value in provider.items()
        },
        variable_bounds={
            temperature_id(inlet): domain_block.temperature_k,
            pressure_id(inlet): domain_block.pressure_pa,
        },
    )


def project_c1(
    binding: RevisionBinding, x0: Mapping[str, float], formulation: C1Formulation
) -> Projection:
    """The C1 formulation projected at the state `x0` of `binding`'s inner problem (§6.1): the
    omitted rows are the certified alias elimination's (R-274), and the shape check is required
    (R-278: C1 is forward by construction)."""
    from openflowsheet.studies.trust_region.projection import project

    return project(
        binding.spec,
        x0,
        decisions=formulation.decisions,
        objective=formulation.objective,
        domain=formulation.domain,
        external_links=formulation.external_links,
        inequalities=formulation.inequalities,
        variable_bounds=formulation.variable_bounds,
    )


def pinned_at(
    binding: RevisionBinding, unit_id: str, coupling: tuple[float, float]
) -> RevisionBinding:
    """`binding`'s inner problem with the embedded reactor `unit_id` pinned at w = (X̂, ΔT̂).

    The one call site of M02's coupling accessor in M05's library. WO-5c (R-309) replaces
    `revision_binding.with_coupling` here with `coupled_run.at_coupling(binding, {unit_id: w})`
    when `wp/M02` reaches this branch."""
    return with_coupling(binding, unit_id, coupling[0], coupling[1])


def c1_constraint_values(
    formulation: C1Formulation,
    state: Mapping[str, float],
    decisions: Mapping[str, float],
    coupling: tuple[float, float],
    kinds: Mapping[str, str],
    n_tubes: int,
) -> tuple[ConstraintValue, ...]:
    """P3's constraints (§7.1, §7.4) at a solved C1 state, without margins.

    - Every formulation inequality, evaluated on floats (`state`, X̂ for the conversion
      parameter); scale max(|bound|, F) with F the reactor-inlet total flow Σn, per tube
      (Σn / N_tubes) for the per-tube flow rows.
    - The decision box, the truth's hard-domain bounds on the inlet T and P, the link bounds on
      (X̂, ΔT̂) (M04 spec §3.2), the provider's domain on every stream temperature and pressure,
      and non-negative molar flows; scale max(|bound|, 1) in the variable's unit."""
    flows = [flow_id(formulation.inlet_stream, name) for name in COMPONENTS]
    total = math.fsum(state[name] for name in flows)
    (link,) = formulation.external_links
    parameters = {link.x_param_id: coupling[0], link.dt_param_id: coupling[1]}
    values: list[ConstraintValue] = []

    def bound(name: str, value: float, low: float | None, high: float | None) -> None:
        for limit, sense, side in ((low, ">=", "lower"), (high, "<=", "upper")):
            if limit is not None:
                values.append(
                    ConstraintValue(f"{name}.{side}", value, limit, sense, max(abs(limit), 1.0))  # type: ignore[arg-type]
                )

    for item in formulation.inequalities:
        value = float(item.build(state, {}, parameters, FloatAlgebra()))
        reference = total / n_tubes if item.source.endswith("tube_flow_mol_s") else total
        values.append(
            ConstraintValue(
                item.inequality_id, value, item.bound, item.sense, max(abs(item.bound), reference)
            )
        )
    for decision in formulation.decisions:
        bound(
            f"decision.{decision.parameter_id}",
            decisions[decision.parameter_id],
            decision.lower,
            decision.upper,
        )
    for name, (low, high) in sorted(formulation.variable_bounds.items()):
        bound(f"hard_domain.{name}", state[name], low, high)
    for coordinate, value in zip(("X", "dT"), coupling, strict=True):
        low, high = LINK_BOUNDS[coordinate]
        bound(f"admissibility.{coordinate}", value, low, high)
    for name in sorted(state):
        kind = kinds.get(name, "")
        if kind in formulation.domain:
            low, high = formulation.domain[kind]
            bound(f"provider_domain.{name}", state[name], low, high)
        elif kind == "molar_flow":
            bound(f"non_negative.{name}", state[name], 0.0, None)
    return tuple(values)


# == the loop (§7.2-§7.5) ==========================================================================

BUDGET_ID: Final = "M05-budget-v1"
#: §7.3: study iterations of stage C.
K_MAX: Final = 3
#: §7.3: a retried run starts with this fraction of the configured trust radius.
RETRY_RADIUS_FACTOR: Final = 0.25

DECISION_STABLE: Final = "DECISION_STABLE"
ITERATION_LIMIT: Final = "ITERATION_LIMIT"
BUDGET_EXHAUSTED: Final = "BUDGET_EXHAUSTED"
#: The holders' refusal when a cold cap is reached (§6.3).
BUDGET_REFUSAL: Final = truth_refused("budget:budget_exhausted")


def failed(reason: str) -> str:
    return f"FAILED({reason})"


def unsupported(codes: Sequence[str]) -> str:
    return f"UNSUPPORTED({','.join(codes)})"


@dataclass(frozen=True)
class Budgets:
    """`M05-budget-v1` (§7.5): the study's cold cap and wall clock, and a TRF run's cold cap and
    iteration limit (`None`: none beyond the study's; the iterations are TRF's own
    `maximum_iterations`). `unit` names what the cold cap counts."""

    configuration: str
    study_cold: int
    study_wall_s: float
    run_cold: int | None
    run_iterations: int | None
    unit: Literal["cold_parent_experiments", "evaluations"]

    def as_document(self) -> dict[str, Any]:
        return {
            "budget_id": BUDGET_ID,
            "configuration": self.configuration,
            "study_cold": self.study_cold,
            "study_wall_s": self.study_wall_s,
            "run_cold": self.run_cold,
            "run_iterations": self.run_iterations,
            "unit": self.unit,
            "k_max": K_MAX,
        }


REAL_BUDGET: Final = Budgets("REAL", 400, 4 * 3600.0, 250, 30, "cold_parent_experiments")
IN_PROCESS_BUDGET: Final = Budgets("in_process", 2000, 3600.0, None, None, "evaluations")


class StudyBudget:
    """The study's budget while it runs (`checks.BudgetGate`). Its `cold` cap is the
    `ColdBudget` the parent holders are given (charged live, per cold request); a stage runner
    charges an in-process truth's cold evaluations after its run, and a parent solve its
    executions after the solve. Exhaustion is judged before every run and check (§7.3)."""

    def __init__(self, budgets: Budgets, clock: Callable[[], float] = time.monotonic) -> None:
        self.budgets = budgets
        self.cold = ColdBudget("study", budgets.study_cold)
        self._clock = clock
        self._start = clock()

    @property
    def wall_s(self) -> float:
        return self._clock() - self._start

    def exhausted(self) -> str | None:
        if self.cold.exhausted:
            return "cold"
        if self.wall_s >= self.budgets.study_wall_s:
            return "wall"
        return None

    def charge(self, count: int) -> None:
        self.cold.used += count

    def charge_solve(self, solve: ParentSolve) -> None:
        self.charge(solve.executions)

    def run_cap(self, run_id: str) -> ColdBudget | None:
        cap = self.budgets.run_cold
        return None if cap is None else ColdBudget(run_id, cap)

    def as_document(self) -> dict[str, Any]:
        return {
            **self.budgets.as_document(),
            "cold_used": self.cold.used,
            "exhausted": self.exhausted(),
        }


@dataclass(frozen=True)
class StageRun:
    """One TRF run as the loop reads it (Pyomo-free; `TrfStage` builds it from a `TrfRun`).
    `point` is P2's view of the returned state, `None` when the outcome has no candidate; `cold`
    the run's cold truth requests; `document` its §9.1 `runs[]` entry without the loop's keys."""

    run_id: str
    outcome: str
    decisions: Mapping[str, float] | None
    point: TrfPoint | None
    cold: int
    document: Mapping[str, Any]


class StageRunner(Protocol):
    """Stage A or C (§7.2): one TRF run from the parent-checked `start`, with the configured
    trust radius times `radius_factor`, charging `budget`."""

    def __call__(
        self, start: ParentSolve, *, run_id: str, radius_factor: float, budget: StudyBudget
    ) -> StageRun: ...


Disposition = Literal["candidate", "abort", "defect", "budget"]


def disposition(outcome: str, budget: StudyBudget) -> Disposition:
    """What the loop does with a run's outcome (§6.7, §7.3, §16.5, §17.4):

    - the outcomes that keep TRF's clone give a candidate (`TRF_MAX_ITERATIONS` included,
      whatever its θ_recheck: build log W2);
    - `TRF_ERROR(...)` is a defect, never retried;
    - a budget refusal with the study's cap reached is the study's budget; with only the run's
      cap reached it is an abort;
    - every other outcome (`TRF_STALLED_INCONSISTENT`, `TRF_SUBPROBLEM_FAILED`, any other
      `TRF_TRUTH_REFUSED`) is an abort, retried once."""
    if outcome in RETURNS_MODEL:
        return "candidate"
    if outcome.startswith("TRF_ERROR("):
        return "defect"
    if outcome == BUDGET_REFUSAL and budget.exhausted() is not None:
        return "budget"
    return "abort"


@dataclass
class StudyResult:
    """A finished study: its status, the runs, candidates and solves in the order they happened,
    and the best parent-checked point. `as_document` is §9.1's record."""

    status: str
    budget: StudyBudget
    sense: str
    s0: ParentSolve | None = None
    readiness: StudyReadiness | None = None
    runs: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[CandidateCheck] = field(default_factory=list)
    stage_a: dict[str, Any] = field(default_factory=dict)
    best: ParentSolve | None = None
    #: The cold requests of each run, by candidate it produced (`by_candidate`, §8.3).
    produced_by: dict[str, list[str]] = field(default_factory=dict)

    def accounting(self) -> dict[str, Any]:
        """§8.3's totals: TRF cold requests by run, and parent executions by solve, summed by
        stage, by study iteration and by candidate."""
        solves = ([self.s0] if self.s0 is not None else []) + [
            solve for candidate in self.candidates for solve in candidate.solves
        ]
        by_stage: dict[str, dict[str, int]] = {}
        by_iteration: dict[str, dict[str, int]] = {}

        def add(table: dict[str, dict[str, int]], key: str, name: str, count: int) -> None:
            row = table.setdefault(key, {"trf_cold": 0, "parent_executions": 0, "store_hits": 0})
            row[name] += count

        for run in self.runs:
            add(by_stage, run["stage"], "trf_cold", run["cold"])
            add(by_iteration, str(run["study_iteration"]), "trf_cold", run["cold"])
        if self.s0 is not None:
            for table, key in ((by_stage, "S0"), (by_iteration, "0")):
                add(table, key, "parent_executions", self.s0.executions)
                add(table, key, "store_hits", self.s0.store_hits)
        for candidate in self.candidates:
            iteration = str(self._iteration_of(candidate))
            for solve in candidate.solves:
                for table, key in ((by_stage, "B"), (by_iteration, iteration)):
                    add(table, key, "parent_executions", solve.executions)
                    add(table, key, "store_hits", solve.store_hits)
        cold_by_run = {run["run_id"]: run["cold"] for run in self.runs}
        by_candidate = {
            candidate.candidate_id: {
                "produce_trf_cold": sum(
                    cold_by_run[r] for r in self.produced_by.get(candidate.candidate_id, [])
                ),
                "check_parent_executions": sum(s.executions for s in candidate.solves),
            }
            for candidate in self.candidates
        }
        totals = {
            "trf_cold": sum(run["cold"] for run in self.runs),
            "parent_executions": sum(solve.executions for solve in solves),
            "store_hits": sum(solve.store_hits for solve in solves),
            "parent_solves": len(solves),
            "trf_runs": len(self.runs),
        }
        return {
            "totals": totals,
            "by_stage": dict(sorted(by_stage.items())),
            "by_iteration": dict(sorted(by_iteration.items())),
            "by_candidate": by_candidate,
            "budgets": self.budget.as_document(),
            "exhausted": self.status == BUDGET_EXHAUSTED,
        }

    def _iteration_of(self, candidate: CandidateCheck) -> int:
        for run in self.runs:
            if run["run_id"] == candidate.run_id:
                return int(run["study_iteration"])
        return 0

    def as_document(
        self,
        *,
        spec: Mapping[str, Any],
        environment: Mapping[str, Any],
        trf_theory: str,
        limitations: Sequence[str] = (),
        artifacts: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """§9.1's `trust-region-study-v1` record. `spec`, `environment`, the TRF-theory claim and
        the artifacts are the caller's; everything else is the loop's, in the order it happened
        (never completion order, R-300 E6)."""
        stated = set(limitations) | {
            item for candidate in self.candidates for item in candidate.limitations
        }
        coupled = ([self.s0] if self.s0 is not None else []) + [
            solve for candidate in self.candidates for solve in candidate.solves
        ]
        return {
            "schema_version": "trust-region-study-v1",
            "study_id": STUDY_ID,
            "spec": dict(spec),
            "environment": dict(environment),
            "readiness": None if self.readiness is None else self.readiness.as_document(),
            "start": None if self.s0 is None else self.s0.as_document(),
            "stage_a": dict(self.stage_a),
            "runs": [dict(run) for run in self.runs],
            "candidates": [candidate.as_document() for candidate in self.candidates],
            "best": None
            if self.best is None
            else {
                "check_id": self.best.solve_id,
                "decisions": dict(self.best.decisions),
                "objective": self.best.objective,
                "stable": self.status == DECISION_STABLE,
            },
            "accounting": self.accounting(),
            "status": self.status,
            "claims": {
                "global_optimality": False,
                "trf_theory": trf_theory,
                "stationarity": "poll_at_delta"
                if self.status == DECISION_STABLE
                else "not_claimed",
            },
            "limitations": sorted(stated),
            "artifacts": {
                **dict(artifacts or {}),
                "coupled_runs": [
                    {"check_id": solve.solve_id, "sha256": solve.coupling_record_sha256}
                    for solve in coupled
                ],
            },
        }


def _better(sense: str, a: ParentSolve, b: ParentSolve) -> bool:
    """Whether `a` improves on `b` (strictly, so ties keep the earlier point)."""
    assert a.objective is not None and b.objective is not None
    return a.objective > b.objective if sense == "maximize" else a.objective < b.objective


def run_study(
    parent: Parent,
    *,
    decisions: Sequence[Decision],
    start: Mapping[str, float],
    stage_c: StageRunner,
    budget: StudyBudget,
    stage_a: StageRunner | None = None,
    stage_a_reference: Callable[[ParentSolve], P2Reference] | None = None,
    framework: Callable[[], FrameworkReadiness] = framework_readiness,
    projection_check: Callable[[ParentSolve], None] | None = None,
    limitations: Sequence[str] = (),
) -> StudyResult:
    """The deterministic loop of §7.3.

    The framework half of readiness first (`UNSUPPORTED`, nothing runs); then S0, the parent at
    `start` (P1, else `FAILED(start_not_certified)`); then `projection_check` at S0, whose
    `ProjectionRefusedError` is `UNSUPPORTED(<code>)`; then stage A if `stage_a` is given (a
    promoted surrogate; else recorded skipped, `surrogate_not_promoted`), checked with
    `stage_a_reference` as P2's reference; then up to `K_MAX` stage-C iterations, each from the
    best parent-checked point, retried once with radius × ¼ after an abort. The budget is judged
    before every run and check: `BUDGET_EXHAUSTED`, never stable."""
    sense = parent.sense
    result = StudyResult(status="", budget=budget, sense=sense)
    readiness = framework()
    if readiness.status != "READY":
        result.readiness = StudyReadiness.of(readiness.reasons)
        result.status = unsupported(result.readiness.codes)
        return result

    def stop(status: str) -> StudyResult:
        result.status = status
        return result

    if budget.exhausted() is not None:
        return stop(BUDGET_EXHAUSTED)
    s0 = parent.solve(start, solve_id="S0", purpose="start")
    budget.charge_solve(s0)
    result.s0 = s0
    if not targeted_check(s0).passed:
        return stop(failed("start_not_certified"))
    result.best = s0
    if projection_check is not None:
        refused = _projection_refusal(projection_check, s0)
        if refused is not None:
            result.readiness = StudyReadiness.of([refused])
            return stop(unsupported(result.readiness.codes))
    reference_regimes = dict(s0.regimes)

    def run(
        runner: StageRunner, stage: str, iteration: int, begin: ParentSolve
    ) -> tuple[StageRun | None, str | None, list[str]]:
        """A run and its one retry: (the run with a candidate, the stopping status, run ids)."""
        ids: list[str] = []
        for retry, factor in enumerate((1.0, RETRY_RADIUS_FACTOR)):
            if budget.exhausted() is not None:
                return None, BUDGET_EXHAUSTED, ids
            run_id = f"{stage}{iteration}" + ("-retry" if retry else "")
            staged = runner(begin, run_id=run_id, radius_factor=factor, budget=budget)
            ids.append(run_id)
            result.runs.append(
                {
                    **dict(staged.document),
                    "run_id": run_id,
                    "stage": stage,
                    "study_iteration": iteration,
                    "retry": retry,
                    "start_check_id": begin.solve_id,
                    "radius_factor": factor,
                    "outcome": staged.outcome,
                    "cold": staged.cold,
                }
            )
            kind = disposition(staged.outcome, budget)
            if kind == "candidate":
                return staged, None, ids
            if kind == "budget":
                return None, BUDGET_EXHAUSTED, ids
            if kind == "defect":
                return None, failed(f"trf_aborted:{staged.outcome}"), ids
        return None, failed(f"trf_aborted:{staged.outcome}"), ids

    def check(staged: StageRun, stage: str, reference: Any = None) -> CandidateCheck:
        assert staged.decisions is not None
        candidate_id = f"cand-{staged.run_id.removesuffix('-retry')}"
        checked = check_candidate(
            parent,
            candidate_id=candidate_id,
            stage=stage,
            decisions=decisions,
            at=staged.decisions,
            reference_regimes=reference_regimes,
            budget=budget,
            run_id=staged.run_id,
            trf_point=staged.point,
            p2_reference=reference,
            limitations=limitations,
        )
        result.candidates.append(checked)
        return checked

    # Stage A (§7.3): only with a promoted surrogate of the bound parent.
    if stage_a is None:
        result.stage_a = {"executed": False, "reason": "surrogate_not_promoted"}
    else:
        staged, stopped, ids = run(stage_a, "A", 0, s0)
        result.stage_a = {"executed": True, "runs": ids}
        if staged is None and disposition(result.runs[-1]["outcome"], budget) != "abort":
            assert stopped is not None
            return stop(stopped)
        if staged is None:
            # A second stage-A abort leaves stage C to start from S0 (build log S6).
            result.stage_a["outcome"] = stopped
        else:
            candidate = check(staged, "A", stage_a_reference)
            result.produced_by[candidate.candidate_id] = ids
            if candidate.status == NOT_CHECKED:
                return stop(BUDGET_EXHAUSTED)
            if candidate.status == PARENT_LOCAL_EVIDENCE:
                result.best = candidate.targeted
                return stop(DECISION_STABLE)
            eligible = [s0]
            if candidate.checks["P1"].passed and all(
                candidate.checks[name].passed for name in ("P3", "P4")
            ):
                assert candidate.targeted is not None
                eligible.append(candidate.targeted)
            eligible += [p.solve for p in candidate.poll if p.feasible and p.regimes_match]
            for point in eligible[1:]:
                if _better(sense, point, result.best):
                    result.best = point

    # Stage C (§7.3).
    for k in range(1, K_MAX + 1):
        staged, stopped, ids = run(stage_c, "C", k, result.best)
        if staged is None:
            assert stopped is not None
            return stop(stopped)
        candidate = check(staged, "C")
        result.produced_by[candidate.candidate_id] = ids
        if candidate.status == NOT_CHECKED:
            return stop(BUDGET_EXHAUSTED)
        if candidate.status == PARENT_LOCAL_EVIDENCE:
            result.best = candidate.targeted
            return stop(DECISION_STABLE)
        if candidate.status != NOT_STATIONARY_AT_DELTA:
            return stop(failed(candidate.status))
        feasible = [point.solve for point in candidate.poll if point.feasible]
        best = feasible[0]
        for point in feasible[1:]:
            if _better(sense, point, best):
                best = point
        result.best = best
    return stop(ITERATION_LIMIT)


class TrfStage:
    """The production `StageRunner`: `project_at(start)` (the projection at the start's
    certified state, so TRF's first evaluation at w₀ is a store hit), `basis_for(projection)`
    (`M05-basis-v1`), `config` (`M05-trf-config-v1` with the study's σ), and `run_trf`.

    Budgets: the parent holders get the study's cold cap and the run's (`Budgets.run_cold`) and
    are charged live; an in-process truth's cold value requests are charged after the run (§7.5:
    its cap counts evaluations, and its holder takes no parent budget, R-300 E4). `assumptions`
    is the run's A1-A7 block (§5.2), recorded as given."""

    def __init__(
        self,
        project_at: Callable[[ParentSolve], Projection],
        basis_for: Callable[[Projection], Mapping[str, EFBasis]],
        config: Mapping[str, Any],
        assumptions: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.project_at = project_at
        self.basis_for = basis_for
        self.config = dict(config)
        self.assumptions = tuple(dict(item) for item in assumptions)

    def __call__(
        self, start: ParentSolve, *, run_id: str, radius_factor: float, budget: StudyBudget
    ) -> StageRun:
        from openflowsheet.studies.trust_region.trf import run_trf

        projection = self.project_at(start)
        config = {**self.config, "trust_radius": self.config["trust_radius"] * radius_factor}
        run_cap = budget.run_cap(run_id)
        caps = [budget.cold] + ([run_cap] if run_cap is not None else [])
        parents = [h for h in projection.holders if getattr(h.box, "parent", False)]
        trf_run = run_trf(
            projection,
            config,
            basis=self.basis_for(projection),
            budgets={holder.name: caps for holder in parents},
            run_id=run_id,
        )
        cold_parent = 0
        cold_in_process = 0
        ledgers: dict[str, Any] = {}
        for holder in projection.holders:
            if not isinstance(holder.box, TruthBox):
                continue
            summary = holder.summary(run_id)
            ledgers[holder.name] = summary
            if holder.box.parent:
                cold_parent += summary["value_cold"]
            else:
                cold_in_process += summary["value_cold"]
        budget.charge(cold_in_process)
        point = None
        if trf_run.outcome in RETURNS_MODEL and trf_run.final is not None:
            assert trf_run.final_state is not None
            checks = {
                name: found.status == "pass"
                for name, found in (
                    ("omitted_rows", trf_run.omitted_rows_final),
                    ("zero_pins", trf_run.zero_pins_final),
                )
                if found is not None
            }
            point = TrfPoint(
                trf_run.final.objective,
                trf_run.final_state,
                projection.scaling.column,
                checks,
            )
        source_map = projection.source_map
        document = {
            "truth": [
                dict(holder.truth_identity)
                for holder in projection.holders
                if isinstance(holder.box, TruthBox)
            ],
            "basis": dict(trf_run.basis),
            "projection": {
                "source_map_sha256": trf_run.source_map_sha256(projection),
                "n_vars": len(projection.variable_indices),
                "n_rows": len(projection.row_ids),
                "n_block_efs": sum(1 for h in projection.holders if h.kind == "property_block"),
                "n_link_efs": sum(1 for h in projection.holders if h.kind == "truth"),
                "n_ineq": len(source_map["inequalities"]),
            },
            "config": dict(trf_run.config),
            "iterations": [record.as_document() for record in trf_run.iterations],
            "filter": [{"f": f, "theta": theta} for f, theta in trf_run.filter],
            "exit_lines": list(trf_run.exit_lines),
            "final": None if trf_run.final is None else trf_run.final.as_document(),
            "theta_recheck": trf_run.theta_recheck,
            "exit_claim": trf_run.exit_claim,
            "theta_logged": trf_run.theta_logged,
            "final_state_is_last_truth_point": trf_run.final_state_is_last_truth_point,
            "error": trf_run.error,
            "ledger": {"summary": ledgers, "cold_parent": cold_parent},
            "assumptions": [dict(item) for item in self.assumptions],
        }
        return StageRun(
            run_id=run_id,
            outcome=trf_run.outcome,
            decisions=None if point is None or trf_run.final is None else trf_run.final.decisions,
            point=point,
            cold=cold_parent + cold_in_process,
            document=document,
        )


# == readiness (§6.8, §16.4) =======================================================================

#: §6.8's reasons, then the projection refusals the rulings added (R-274, R-275, R-278, R-296).
READINESS_CODES: Final = (
    "TRUST_REGION_FRAMEWORK_UNAVAILABLE",
    "TRUST_REGION_FRAMEWORK_UNPINNED",
    "TRSP_SOLVER_UNAUDITED",
    "PARAMETER_NOT_DIFFERENTIABLE",
    "PROJECTION_NONSMOOTH",
    "PROJECTION_STRUCTURE",
    "PROJECTION_DOF",
    "PROJECTION_SCALES_UNAVAILABLE",
    "PROJECTION_IMPLICIT_EF_INPUT",
    "PROJECTION_OMITTED_ROW_UNCERTIFIED",
    "PROJECTION_ZERO_FLOW",
    "START_NOT_CERTIFIED",
)


@dataclass(frozen=True)
class StudyReadiness:
    """`trust_region_readiness` (§6.8): `READY`, or `UNSUPPORTED` with every failing reason as
    (code, detail) in the order found."""

    status: Literal["READY", "UNSUPPORTED"]
    reasons: tuple[tuple[str, str], ...]

    @classmethod
    def of(cls, reasons: Sequence[Any]) -> StudyReadiness:
        pairs = tuple(
            (reason.code, reason.detail) if hasattr(reason, "detail") else tuple(reason)
            for reason in reasons
        )
        return cls("UNSUPPORTED" if pairs else "READY", pairs)

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(code for code, _ in self.reasons))

    def as_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reasons": [{"code": code, "detail": detail} for code, detail in self.reasons],
        }


def _projection_refusal(
    project: Callable[[ParentSolve], Any], start: ParentSolve
) -> tuple[str, str] | None:
    """The projection half: `project(start)`'s refusal as (code, `reason: detail`), or `None`.
    The projection module (Pyomo) is imported only here, after the framework half passed."""
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    try:
        project(start)
    except ProjectionRefusedError as refused:
        return refused.code, f"{refused.reason}: {refused.detail}"
    return None


def trust_region_readiness(
    *,
    start: Callable[[], ParentSolve] | None = None,
    project: Callable[[ParentSolve], Any] | None = None,
    framework: Callable[[], FrameworkReadiness] = framework_readiness,
) -> StudyReadiness:
    """§6.8: the framework half (`trf_state.framework_readiness`: environment, pin, TRSP
    executable), then the start half (`start()`, the parent at the start decisions: P1, else
    `START_NOT_CERTIFIED`) and the projection half (`project(start)` compiles without refusal).

    Without the `nlp` environment the answer is `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE)`
    alone and nothing else is attempted (the default install, N1). Otherwise every failing
    reason is listed; the projection is attempted on any start that has a state, certified or
    not."""
    found = framework()
    reasons: list[tuple[str, str]] = [(r.code, r.detail) for r in found.reasons]
    if "TRUST_REGION_FRAMEWORK_UNAVAILABLE" in found.codes:
        return StudyReadiness.of(reasons)
    solved = start() if start is not None else None
    if solved is not None and not targeted_check(solved).passed:
        reasons.append(
            (
                "START_NOT_CERTIFIED",
                f"{solved.solve_id}: outcome {solved.outcome}, certificate {solved.certificate}",
            )
        )
    if project is not None and solved is not None and solved.state is not None:
        refused = _projection_refusal(project, solved)
        if refused is not None:
            reasons.append(refused)
    return StudyReadiness.of(reasons)
