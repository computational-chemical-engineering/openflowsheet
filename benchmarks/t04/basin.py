"""T04 §8.3's basin comparison, as a harness: the registered lattice of off-ray starts on SYN-001 at
r = 0.95, each solved by both EO cores under one contract, one set of tolerances and one budget.

The start family is the specification's, not a selection: tear guesses `t⁰ = m·(i, j, k)/4` over
the fifteen points of the quarter-lattice on the simplex (`i + j + k = 4`) and the three
magnitudes `m ∈ {0.3, 3, 30}` mol/s — 45 guesses. Each is turned into a region start exactly as a
registered initializer is: one traversal (`Syn001TearProblem.reconstruct`, K03 §3.3), which the
mixer may refuse (K03 §10.1's own check; the refusal is recorded with the mixer's message and the
start is not solved), then the region solve's projection (T02 §6.2). Both cores run with
`eo_recovery: none` — the comparison is of cores, not of recoveries.

`BasinComparison` carries the verdict fields the evidence manifest records (T04 A23): the success
sets, the starts only PTC converges from, and what T04 §8.1's criterion says of them. The criterion
has two halves; route (a), the derivation, is the specification's (§8.2) and is taken as given
here; this harness decides only the basin half — "the set of starts from which PTC reaches the P01
root is not contained in damped Newton's".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import yaml

from openflowsheet.application.binding import Binding, bind_revision
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.orchestrator.execution import (
    Region,
    build_execution_plan,
    declaration_identity,
)
from openflowsheet.orchestrator.mass import syn001_residence_time
from openflowsheet.orchestrator.region import RegionResult, solve_region, syn001_lifted_splits
from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear
from openflowsheet.orchestrator.trace import GlobalizationPolicy, RecyclePolicy, SolvePolicy

__all__ = [
    "LATTICE",
    "MAGNITUDES",
    "BasinComparison",
    "BasinStart",
    "CoreRun",
    "basin_comparison",
    "criterion",
    "lattice_guesses",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
CASE_ID: Final = "SYN-001-high-recycle"

#: T04 §8.3: the fifteen quarter-lattice directions on the simplex, in the registered order, and
#: the three magnitudes bracketing `Σ t* = 31.1 mol/s`.
LATTICE: Final[tuple[tuple[int, int, int], ...]] = tuple(
    (i, j, 4 - i - j) for i in range(5) for j in range(5 - i)
)
MAGNITUDES: Final[tuple[float, ...]] = (0.3, 3.0, 30.0)

#: T02 A28's per-kind allowances: a converged state is "the P01 root" within these of K03's
#: tear solution (itself gated against P01's 20-digit values).
AGREEMENT: Final[Mapping[str, float]] = {
    "molar_flow": 3.1e-7,
    "temperature": 1e-5,
    "pressure": 0.1,
    "heat_rate": 1e-2,
}

Core = Literal["newton", "ptc"]


def lattice_guesses() -> tuple[tuple[float, tuple[int, int, int], tuple[float, ...]], ...]:
    """The 45 guesses `(m, (i, j, k), m·(i, j, k)/4)`, magnitude-major, in the registered order."""
    return tuple(
        (m, quarters, tuple(m * q / 4 for q in quarters))
        for m in MAGNITUDES
        for quarters in LATTICE
    )


@dataclass(frozen=True)
class CoreRun:
    """One core's solve from one start: its outcome, each attempt's `(signature, core outcome,
    iterations)`, whether the end state is the P01 root, and — PTC — the last attempt's polish."""

    outcome: str
    attempts: tuple[tuple[str, str, int], ...]
    same_root: bool
    polish: str | None
    result: RegionResult

    @property
    def iterations(self) -> int:
        return sum(count for _, _, count in self.attempts)

    @property
    def converged_to_the_root(self) -> bool:
        return self.outcome == "CONVERGED" and self.same_root


@dataclass(frozen=True)
class BasinStart:
    magnitude: float
    quarters: tuple[int, int, int]
    guess: tuple[float, ...]
    #: The traversal's refusal message when the start could not be reconstructed; `None` if it was.
    refused: str | None
    runs: Mapping[Core, CoreRun]


@dataclass(frozen=True)
class BasinComparison:
    starts: tuple[BasinStart, ...]

    @property
    def admitted(self) -> tuple[BasinStart, ...]:
        return tuple(start for start in self.starts if start.refused is None)

    def converged(self, core: Core) -> frozenset[int]:
        """Indices (into `starts`) of the admitted starts `core` took to the P01 root."""
        return frozenset(
            index
            for index, start in enumerate(self.starts)
            if start.refused is None and start.runs[core].converged_to_the_root
        )

    @property
    def ptc_only(self) -> frozenset[int]:
        return self.converged("ptc") - self.converged("newton")

    @property
    def cost_ratios(self) -> tuple[float, ...]:
        """PTC's total iterations over Newton's, on every start both took to the root."""
        both = self.converged("ptc") & self.converged("newton")
        return tuple(
            self.starts[index].runs["ptc"].iterations / self.starts[index].runs["newton"].iterations
            for index in sorted(both)
        )

    def verdict_fields(self) -> dict[str, Any]:
        """What the manifest records (T04 A23): the counts, the sets' relation and the criterion."""
        verdict = criterion(self.converged("newton"), self.converged("ptc"))
        return {
            "guesses": len(self.starts),
            "refused": len(self.starts) - len(self.admitted),
            "admitted": len(self.admitted),
            "newton_converged": len(self.converged("newton")),
            "ptc_converged": len(self.converged("ptc")),
            "ptc_only": len(self.ptc_only),
            **verdict,
        }


def criterion(newton: frozenset[int], ptc: frozenset[int]) -> dict[str, str | bool]:
    """T04 §8.1's basin half: the family qualifies iff PTC's success set is not contained in damped
    Newton's (route (a), the other half, holds by §8.2). Otherwise it stays experimental and V14's
    qualified-PTC clause is incomplete (plan §4.3)."""
    improves = not ptc <= newton
    return {
        "improves_a_tested_basin": improves,
        "verdict": "qualified" if improves else "experimental",
        "v14_qualified_ptc_clause": "complete" if improves else "incomplete",
    }


@dataclass(frozen=True)
class _Setup:
    binding: Binding
    region: Region
    compiled: Any
    root: Mapping[str, float]


def _setup() -> _Setup:
    document = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "cases" / f"{CASE_ID}.yaml").read_text()
    )
    binding = bind_revision(document)
    if binding is None:
        raise ValueError(f"{CASE_ID} does not bind")
    spec = binding.spec
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec,
        row_units=binding.row_units,
        model_version=model_version,
        constants_sha256=constants,
    )
    report = analyse(
        spec,
        binding.graph,
        row_units=binding.row_units,
        model_version=model_version,
        constants_sha256=constants,
    )
    plan = build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=binding.graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in binding.flowsheet.units()},
        policy=_policy("newton"),
    )
    region = plan.steps[1].region
    if region is None:
        raise ValueError(f"{CASE_ID}'s eo plan has no region at step 1")
    tear, _ = solve_tear(binding.flowsheet)
    if tear.final_state is None:
        raise ValueError(f"{CASE_ID}'s tear solve has no final state")
    return _Setup(binding, region, compile_problem(spec), dict(tear.final_state))


def _policy(core: Core) -> SolvePolicy:
    return SolvePolicy(
        policy_id=f"T04-basin-{core}",
        residual_tolerances={},
        scales={},
        recycle=RecyclePolicy(method="eo"),
        globalization=GlobalizationPolicy(eo_core=core, eo_recovery="none"),
    )


def _same_root(setup: _Setup, state: Mapping[str, float]) -> bool:
    kinds = setup.binding.spec.variable_kinds
    return all(
        abs(state[name] - setup.root[name]) <= AGREEMENT[kinds.get(name, "molar_flow")]
        for name in setup.binding.spec.variable_ids
    )


def _run(setup: _Setup, state: Mapping[str, float], core: Core) -> CoreRun:
    flowsheet = setup.binding.flowsheet
    result = solve_region(
        compiled=setup.compiled,
        spec=setup.binding.spec,
        region=setup.region,
        state=state,
        splits=syn001_lifted_splits(flowsheet.components),
        provider=flowsheet.provider,
        policy=_policy(core),
        initializer_source="user_guess",
        mass_mapping=syn001_residence_time(flowsheet.components),
    )
    last = result.attempts[-1] if result.attempts else None
    return CoreRun(
        outcome=result.outcome,
        attempts=tuple(
            (
                ",".join(f"{unit}:{regime}" for unit, regime in attempt.signature),
                str(attempt.solver_outcome),
                attempt.iterations,
            )
            for attempt in result.attempts
        ),
        same_root=result.outcome == "CONVERGED" and _same_root(setup, result.state),
        polish=last.ptc.polish if last is not None and last.ptc is not None else None,
        result=result,
    )


def basin_comparison(cores: Sequence[Core] = ("newton", "ptc")) -> BasinComparison:
    """Run the 45 guesses of T04 §8.3 through both cores (about 5 s)."""
    setup = _setup()
    tear = Syn001TearProblem(setup.binding.flowsheet)
    starts: list[BasinStart] = []
    for magnitude, quarters, guess in lattice_guesses():
        # The traversal is the initializer's own check (K03 §10.1): a unit that refuses the start
        # says so, with its status and message, and the start is recorded refused, not solved.
        traversal = setup.binding.flowsheet.traverse(tear.tear_state(guess))
        if traversal.status != "ok":
            refusal = f"{traversal.status}: {traversal.message}"
            starts.append(BasinStart(magnitude, quarters, guess, refusal, {}))
            continue
        state = dict(tear.reconstruct(tear.tear_state(guess)))
        runs = {core: _run(setup, state, core) for core in cores}
        starts.append(BasinStart(magnitude, quarters, guess, None, runs))
    return BasinComparison(tuple(starts))
