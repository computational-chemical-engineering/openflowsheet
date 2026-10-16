"""The C1 parent adapter (M05 design note §7.4, §7.2, §6.4; build decisions S3, S44): the `Parent`
the parent checks and the study loop solve, and the parent truth stage C's projection links.

**The application's operations are injected** (S44): binding, routing and solving a revision,
the live experiments, the reactor inlet and variant, and pinning the reactor at w are
`application`'s, and `studies` never imports `application` (M04's rule). The adapter calls them
through its `services` (`ParentServices`; `application.trust_region_parent.C1_PARENT_SERVICES`
is the implementation) and holds the bindings they return as opaque values.

**A solve** (§7.4) edits the C1 revision document in memory: the specification that pins the
decision — the outlet temperature of the `c1.tp_heater` feeding the reactor (ADR 0031 D1), found
through the binding's `specification_pins` — takes the decision's binary64 value. The document is
canonicalized, its sha256 recorded, and solved through the route it selects
(`revision_run.select_route`, then `solve_route`), uncommitted and unwritten: `revision_coupled`,
M02's outer coupling on the study's one `ExperimentRunner` (`coupled_run.LiveExperiments`, §6.4:
M02's frozen identity then covers every coupled check and every TRF call of the study), the final
inner solve certified with `EXT-COUPLING`'s checks. A route that refuses (`RunUnsupportedError`)
or a verifier that refuses to judge (`VerifierError`) is returned as the outcome, never raised:
P1 judges it.

**What a solve reads** from the run:
- the outcome and the certificate's status (P1);
- J (`c1-obj-nh3-liquid-v1`, the flash's liquid NH₃) and the certified state;
- the converged w, the final inner binding's reactor coupling parameters (the floats the
  certified inner solve was pinned at);
- the achieved coupling residuals (ΔX, ΔT) from the certificate's `EXT-COUPLING:<unit>:xi` and
  `:T` checks. M02 normalizes the ξ check by n_tot,in; §7.4's ΔX is per n_N₂,in, so its value is
  rescaled by n_tot,in / n_N₂,in, both read through `coupled_run.inlet_of` at the certified state;
- every unit's phase regime (P4): each non-external unit's own causal `evaluate` on its inlets
  read from the certified state, labelled by its `phase_signature`;
- P3's constraint values (`study.c1_constraint_values`);
- §8.2's summary: the executions and store hits of every experiment in `external-coupling.json`
  and that record's sha256;
- §7.1's stated limits: `synthetic` (the variant), `extrapolated` (the final iterate's experiment
  outside the variant's data domain).

**The inner objective** (§7.4's noise floor): the solve's revision with the reactor pinned at w
(`services.pinned_at`), planned and solved as M02's inner solve from the solve's certified state
(`user_start`, as M02's inner solves after k = 0 start from the base iterate), no reactor call; NaN
when that solve fails, so the noise floor is NaN and P5 cannot pass (the safe failure is an extra
refinement, never a false stability).

**The parent truth** (§6.4): `ParentExperimentTruth` on the same runner, the external link of the
formulation `project_at` projects at a parent-checked start: the inner problem pinned at the
start's converged w, at its certified state, so TRF's first truth evaluation at w₀ is a store hit
(§7.2).

Pyomo-free at import (M03 G6): only `project_at` imports the projection.
"""

from __future__ import annotations

import copy
import math
import time
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Final, Protocol

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.variants import Variant
from openflowsheet.canonical import document_sha256
from openflowsheet.models import flow_id, temperature_id
from openflowsheet.models.c1.reactor import C1Reactor
from openflowsheet.orchestrator.coupling import UnitInlet
from openflowsheet.orchestrator.execution import PlanRefusal
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.studies.trust_region.checks import Decision, ParentSolve, Sense
from openflowsheet.studies.trust_region.study import (
    C1Formulation,
    CaseBinding,
    c1_constraint_values,
    c1_formulation,
    project_c1,
)
from openflowsheet.studies.trust_region.truths import ParentExperimentTruth
from openflowsheet.verify.certificate import CheckPolicy
from openflowsheet.verify.checks import VerifierError, stream_of

if TYPE_CHECKING:
    from openflowsheet.studies.trust_region.projection import Projection

__all__ = [
    "DECISION_TOLERANCE_K",
    "C1Parent",
    "ParentServices",
    "coupling_counts",
    "unit_regimes",
]

#: §7.1 (N-F2): the decision tolerance δ_T on the heater outlet temperature, K.
DECISION_TOLERANCE_K: Final = 0.5


class ParentServices(Protocol):
    """The application operations a `C1Parent` runs (S44; `application.trust_region_parent`).
    Bindings are `application`'s `RevisionBinding`s, opaque here (`Any`): the adapter reads them
    as `CaseBinding`s and hands them back to `services` and to the orchestrator."""

    @property
    def policy(self) -> SolvePolicy:
        """The default solve policy."""
        ...

    def bind(self, document: Mapping[str, Any]) -> Any:
        """The revision's binding; a refusal raises `ValueError`."""
        ...

    def coupled_route(self, document: Mapping[str, Any]) -> Any:
        """The route `document` selects when it is `revision_coupled`, else `None`."""
        ...

    def solve_coupled(
        self,
        route: Any,
        document: Mapping[str, Any],
        *,
        policy: SolvePolicy,
        check_policy: CheckPolicy,
        experiments: Any,
    ) -> Any:
        """`route`'s run of `document`, or the `unsupported(<code>)` code (a `str`) of a run that
        has no mapping. A `VerifierError` propagates."""
        ...

    def live_experiments(self, runner: ExperimentRunner) -> Any:
        """The study's experiments on its one runner (§6.4)."""
        ...

    def inlet_of(self, binding: Any, unit: C1Reactor, state: Mapping[str, float]) -> UnitInlet:
        """`unit`'s inlet, read exactly from `state`."""
        ...

    def unit_variant(self, unit: C1Reactor) -> Variant:
        """The variant the binder resolved for `unit`."""
        ...

    def pinned_at(self, binding: Any, unit_id: str, coupling: tuple[float, float]) -> Any:
        """`binding`'s inner problem with the reactor `unit_id` pinned at w = (X̂, ΔT̂)."""
        ...


def coupling_counts(record: Mapping[str, Any] | None) -> tuple[int, int]:
    """(executions, store hits) of every experiment `external-coupling.json` embeds (§8.2;
    ADR 0034 D6): an experiment's executions are its attempts, as `truths.outcome_meta` counts."""
    executions = hits = 0
    for iteration in (record or {}).get("iterations", ()):
        for entry in (iteration.get("units") or {}).values():
            executions += len(entry.get("attempts") or ())
            hits += bool(entry.get("cache_hit"))
    return executions, hits


def unit_regimes(binding: CaseBinding, state: Mapping[str, float]) -> dict[str, str]:
    """P4's labels: each non-external unit's `phase_signature` from its own causal `evaluate` on
    its inlets read from `state` (`"none"` for a unit that reports none, `"status:<s>"` for an
    evaluation that is not `ok`). The external reactor's regime is its experiment's, not the
    flowsheet provider's, and is not labelled."""
    flowsheet = binding.flowsheet
    labels: dict[str, str] = {}
    for unit in flowsheet.instances:
        if isinstance(unit, C1Reactor):
            continue
        streams = flowsheet.wiring[unit.unit_id].streams
        inlets = {
            port.name: tuple(
                stream_of(state, stream, flowsheet.components) for stream in streams[port.name]
            )
            for port in unit.ports()
            if port.direction == "inlet" and port.name in streams
        }
        evaluation = unit.evaluate(inlets, flowsheet.context)
        if evaluation.status != "ok":
            labels[unit.unit_id] = f"status:{evaluation.status}"
        else:
            labels[unit.unit_id] = str(evaluation.phase_signature or "none")
    return labels


class C1Parent:
    """The C1 loop as the study's parent (module docstring).

    `document` is the C1 revision (its reactor bound to a variant: the stand-in, a synthetic
    variant or the real reactor, v3 for REAL); `runner` is the study's one `ExperimentRunner`;
    `box` the decision box (`study.REAL_BOX`, `study.TR_E2_BOX`); `services` the application's
    operations (S44). `coupling_sink`, when given, receives `(solve_id, record)` once for every
    solve that has an M02 coupling record, where its digest is computed, so that the caller can
    keep the document the digest certifies (§19.1 item 3, R-385); `None` changes nothing."""

    def __init__(
        self,
        document: Mapping[str, Any],
        runner: ExperimentRunner,
        box: tuple[float, float],
        *,
        services: ParentServices,
        policy: SolvePolicy | None = None,
        check_policy: CheckPolicy | None = None,
        clock: Callable[[], float] = time.monotonic,
        coupling_sink: Callable[[str, Mapping[str, Any]], None] | None = None,
    ) -> None:
        self.services = services
        self.coupling_sink = coupling_sink
        self.document: dict[str, Any] = copy.deepcopy(dict(document))
        binding = services.bind(self.document)
        self.binding = binding
        self.runner = runner
        self.policy = services.policy if policy is None else policy
        self.check_policy = CheckPolicy() if check_policy is None else check_policy
        self.experiments = services.live_experiments(runner)
        self._clock = clock
        reactors = [unit for unit in binding.flowsheet.instances if isinstance(unit, C1Reactor)]
        if len(reactors) != 1:
            raise ValueError(f"a C1 parent needs exactly one C1 reactor; it has {len(reactors)}")
        self.reactor: C1Reactor = reactors[0]
        self.variant = services.unit_variant(self.reactor)
        self.truth = ParentExperimentTruth(runner, self.variant, self.reactor.n_tubes)
        self.formulation: C1Formulation = c1_formulation(binding, self.variant, self.truth, box)
        pins = binding.specification_pins[self.formulation.heater]
        (decision,) = self.formulation.decisions
        self._specification = {
            decision.parameter_id: pins[temperature_id(self.formulation.inlet_stream)]
        }
        box_low, box_high = box
        self.decisions: tuple[Decision, ...] = (
            Decision(decision.parameter_id, box_low, box_high, DECISION_TOLERANCE_K),
        )
        self._bindings: dict[tuple[tuple[str, float], ...], Any] = {}

    @property
    def sense(self) -> Sense:
        return "maximize"

    # -- the revision at a decision -------------------------------------------------------------

    def document_at(self, decisions: Mapping[str, float]) -> dict[str, Any]:
        """The revision with each decision's pinning specification at its binary64 value."""
        if set(decisions) != set(self._specification):
            raise ValueError(
                f"decisions {sorted(decisions)} are not the study's {sorted(self._specification)}"
            )
        edited = copy.deepcopy(self.document)
        by_id = {item["id"]: item for item in edited["specifications"]}
        for parameter, specification in self._specification.items():
            by_id[specification]["value"] = float(decisions[parameter])
        return edited

    def binding_at(self, decisions: Mapping[str, float]) -> Any:
        key = tuple(sorted((name, float(value)) for name, value in decisions.items()))
        if key not in self._bindings:
            self._bindings[key] = self.services.bind(self.document_at(decisions))
        return self._bindings[key]

    # -- the Parent protocol --------------------------------------------------------------------

    def solve(self, decisions: Mapping[str, float], *, solve_id: str, purpose: str) -> ParentSolve:
        values = {name: float(value) for name, value in decisions.items()}
        document = self.document_at(values)
        revision_sha256 = document_sha256(document)
        started = self._clock()

        def failed(outcome: str) -> ParentSolve:
            return ParentSolve(
                solve_id=solve_id,
                purpose=purpose,
                decisions=values,
                revision_sha256=revision_sha256,
                outcome=outcome,
                certificate=None,
                wall_s=self._clock() - started,
            )

        route = self.services.coupled_route(document)
        if route is None:
            return failed("unsupported(not_revision_coupled)")
        try:
            result = self.services.solve_coupled(
                route,
                document,
                policy=self.policy,
                check_policy=self.check_policy,
                experiments=self.experiments,
            )
        except VerifierError as error:
            return failed(f"verifier_refused({error})")
        if isinstance(result, str):
            return failed(f"unsupported({result})")
        record = result.coupling
        if record is not None and self.coupling_sink is not None:
            self.coupling_sink(solve_id, record)
        executions, hits = coupling_counts(record)
        certificate = result.certificate
        common: dict[str, Any] = {
            "solve_id": solve_id,
            "purpose": purpose,
            "decisions": values,
            "revision_sha256": revision_sha256,
            "outcome": result.outcome,
            "certificate": None if certificate is None else certificate.verification_status,
            "executions": executions,
            "store_hits": hits,
            "coupling_record_sha256": None if record is None else document_sha256(record),
            "limitations": self._limitations(record),
        }
        if result.state is None or certificate is None:
            return ParentSolve(**common, wall_s=self._clock() - started)
        state = dict(result.state)
        binding = result.route.binding
        (reactor,) = (u for u in binding.flowsheet.instances if u.unit_id == self.reactor.unit_id)
        assert isinstance(reactor, C1Reactor)
        coupling = (reactor.conversion, reactor.temperature_rise)
        checks = {check.id: check for check in certificate.checks}
        xi = checks[f"EXT-COUPLING:{reactor.unit_id}:xi"]
        rise = checks[f"EXT-COUPLING:{reactor.unit_id}:T"]
        inlet = self.services.inlet_of(binding, reactor, state)
        assert xi.value is not None and rise.value is not None
        residuals = (xi.value * inlet.n_tot / inlet.n_key, rise.value)
        return ParentSolve(
            **common,
            objective=state[flow_id(self.formulation.liquid_stream, "NH3")],
            state=state,
            coupling=coupling,
            coupling_residuals=residuals,
            regimes=unit_regimes(binding, state),
            constraints=c1_constraint_values(
                self.formulation,
                state,
                values,
                coupling,
                binding.spec.variable_kinds,
                reactor.n_tubes,  # type: ignore[arg-type]
            ),
            wall_s=self._clock() - started,
        )

    def _limitations(self, record: Mapping[str, Any] | None) -> tuple[str, ...]:
        """§7.1's stated limits a solve carries: `synthetic` for a synthetic variant, and
        `extrapolated` when the experiment of the record's final iterate (the one the certified
        state rests on) left the variant's data domain."""
        stated = {"synthetic"} if self.variant.synthetic else set()
        iterations = (record or {}).get("iterations") or []
        entry = (
            (iterations[-1].get("units") or {}).get(self.reactor.unit_id) if iterations else None
        )
        envelope = ((entry or {}).get("result") or {}).get("envelope") or {}
        if envelope.get("domain_status") == "extrapolated":
            stated.add("extrapolated")
        return tuple(sorted(stated))

    def inner_objective(self, solve: ParentSolve, coupling: tuple[float, float]) -> float:
        pinned = self.services.pinned_at(
            self.binding_at(solve.decisions), self.reactor.unit_id, coupling
        )
        plan, _ = plan_revision(pinned, self.policy)
        if isinstance(plan, PlanRefusal):
            return math.nan
        run = execute_plan(
            plan=plan,
            flowsheet=pinned.flowsheet,
            spec=pinned.spec,
            policy=self.policy,
            user_start=solve.state,
        )
        if run.outcome != "CONVERGED" or run.state is None:
            return math.nan
        return float(run.state[flow_id(self.formulation.liquid_stream, "NH3")])

    # -- stage C's projection -------------------------------------------------------------------

    def project_at(self, start: ParentSolve) -> Projection:
        """The formulation projected at a parent-checked start (`TrfStage`'s `project_at`): the
        inner problem of the start's revision pinned at its converged w, at its certified state.
        Needs the `nlp` environment."""
        if start.state is None or start.coupling is None:
            raise ValueError(f"{start.solve_id}: no certified coupled state to project at")
        pinned = self.services.pinned_at(
            self.binding_at(start.decisions), self.reactor.unit_id, start.coupling
        )
        return project_c1(pinned, start.state, self.formulation)
