"""Revision-built runs through the contract: route, solve, verify, bundle, rerun (T07 §12).

T07 design note §12.1–§12.3 as amended by ruling round 1 (R2), ADR 0020 D4. A stored revision
solves on one of two **routes**, `revision_eo` | `legacy_eo`, chosen by `select_route` as a pure
function of the document (R2.2's table):

- *binder:* `bind_revision_flowsheet` | `bind_revision`;
- *plan:* `plan_revision(binding, policy)` | `legacy_plan(binding, policy)` (T02 §7.5);
- *solve:* `execute_plan(plan=…, flowsheet=binding.flowsheet, spec=binding.spec, policy=…)`,
  from the registered initializer, on both;
- *certify when:* `CONVERGED` and `run.state is not None` | `CONVERGED` and the `solve_eo`
  step's detail is a `RegionResult`;
- *verifier:* `verify_revision(…, solve_plan=plan.steps[-1].solve_plan)` |
  `verify_bound(…, detail, solve_plan=<the planned solve_eo step>.solve_plan)`;
- *failure bundle:* `region_bundle(step.detail, run.trace, step_index=…)` on both, or, for an
  EO initializer's registered refusal, `initializer_bundle(step, run.trace)` (ruling round 3, Q1).

The tear path (`run_session`, `Syn001Flowsheet`) stays the CLI's registered-case path and is not
reachable through `solve`; its registered-case construction lives here (§12.3), and the CLI
delegates to it.

`run_revision_session` writes a bundle `run_session`-shaped plus `execution-plan.json`,
`revision.json`, `solve-policy.json`, `check-policy.json` and `solve-path.json`, and, beside a
certificate only, `solution-state.json` (ruling round 2), under the frozen `RunManifest`
unchanged. `reproduce_bundle` reruns a bundle along **its recorded route** — it never
re-routes — after the archived policy documents recompute to the manifest's hashes, and compares
through `run.replay`. These are plain functions: the job runner (W4) calls them, maps their typed
refusals to `ApiError`s and registers their outputs as artifacts.

**What ends typed without a bundle** (§12.3): a `VerifierError` (the verifier refused to judge;
the job ends `failed(verifier_refused)`), a solve whose record has no registered mapping to a
certificate or a failure bundle — `RunUnsupportedError`, never a bundle invented for it — and a
judged state whose digest is not the certificate's (`SolutionStateMismatchError`, a defect).
"""

from __future__ import annotations

import copy
import json
import re
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from openflowsheet.application.binding import (
    Binding,
    Unbound,
    bind_revision_or_reason,
    legacy_admission,
    refusal_code,
)
from openflowsheet.application.coupled_run import (
    COUPLING_NAME,
    CouplingUnsupportedError,
    Experiments,
    RecordedExperiments,
    ReplayDivergenceError,
    compact_differences,
    compact_record,
    coupling_evidence,
    coupling_record_problem,
    external_units,
    final_constants,
    iterate_differences,
    record_differences,
    reproducibility_class,
    solve_coupled,
)
from openflowsheet.application.policies import SolvePath
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.structure_index import structure_index
from openflowsheet.canonical import canonical_json
from openflowsheet.compile.reference import state_vector
from openflowsheet.graph.analysis import analyse, analyse_declaration
from openflowsheet.graph.process import ProcessGraph
from openflowsheet.graph.report import StructuralReport
from openflowsheet.graph.trace import Declaration, StructureUnavailableError, trace_declaration
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    PlanRefusal,
    UnsupportedRankStructureError,
    build_execution_plan,
    declaration_identity,
    specification_regions,
)
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePlan, SolvePolicy, Trace
from openflowsheet.orchestrator.warm_start import WarmStartCandidate
from openflowsheet.resources import packaged
from openflowsheet.run import solution_state
from openflowsheet.run.bundle import read_artifact, read_manifest, verify_bundle, write_bundle
from openflowsheet.run.compare import KNOWN_POLICY_IDS
from openflowsheet.run.identity import r0_projection, r0_sha256
from openflowsheet.run.manifest import RunManifest, environment, policy_sha256, started_now
from openflowsheet.run.replay import ReplayReport, Rerun, decide_mode, replay
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.verify.certificate import (
    CheckPolicy,
    SolutionCertificate,
    verify_bound,
    verify_revision,
)
from openflowsheet.verify.failure import (
    FailureBundle,
    coupling_bundle,
    initializer_bundle,
    initializer_source,
    refusal_bundle,
    region_bundle,
)

__all__ = [
    "SOLVE_PATHS",
    "NoRoute",
    "Reproduction",
    "Route",
    "RouteRun",
    "RunUnsupportedError",
    "SolutionStateMismatchError",
    "bind_route",
    "check_policy_document",
    "declared_kinds",
    "legacy_plan",
    "registered_case",
    "registered_flowsheet",
    "reproduce_bundle",
    "rerun_registered",
    "route_analysis",
    "route_declaration",
    "route_structure",
    "run_revision_session",
    "select_route",
    "solve_route",
    "traced_analysis",
]

#: R2.4: the routes a `solve-path.json` may record; `revision_coupled` is M02's (ADR 0034 D2).
SOLVE_PATHS: Final[tuple[SolvePath, ...]] = ("revision_eo", "legacy_eo", "revision_coupled")

#: A stage callback (§6.4): called with a stage's name at its start, and never for a stage that
#: is skipped. The job runner emits progress and checks for interruption there (§8.1); `None`,
#: every other caller, changes nothing.
Stage = Callable[[str], None]


def _no_stage(_: str) -> None:
    return None


class SolutionStateMismatchError(RuntimeError):
    """The judged state's digest is not the certificate's `target_state_sha256` (ruling round 2
    F1.1): a producer defect. The job ends `failed(operation_error)`, no bundle is written, and
    it goes to the design lane; no other state is picked."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RunUnsupportedError(RuntimeError):
    """A run whose record has no registered mapping to a certificate or a failure bundle (§12.3).

    `code` is the typed reason the job runner reports as `unsupported(<code>)`. No bundle is
    written: a certificate or a failure bundle made up for the occasion would be the placeholder
    the repository's rules forbid."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# -- routing (R2.1) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Route:
    """The route a revision solves on, its binding, and why it is not `revision_eo` (R2.4)."""

    solve_path: SolvePath
    #: A `RevisionBinding` on `revision_eo`, a `Binding` on `legacy_eo`.
    binding: Any
    #: The revision binder's refusal, `<kind>(<detail>)`, when the route is `legacy_eo`.
    reason: str | None = None


@dataclass(frozen=True)
class NoRoute:
    """No route (R2.1 as amended by ruling rounds 6 and 7): neither binder binds, or the legacy
    one binds and `legacy_admission` refuses; admission's `revision_unsupported` (§5.3 step 3,
    R2.6)."""

    #: The refusal `validate()` reports when the legacy binder binds: `legacy_admission`'s, which
    #: outside the free class is the revision binder's own. When the legacy binder refuses, the
    #: revision binder's refusal.
    revision: Unbound
    legacy: Unbound

    @property
    def reason(self) -> str:
        """`<revision reason>; <legacy reason>`, the order R2.6 names them in."""
        return f"{_refusal(self.revision)}; {_refusal(self.legacy)}"

    @property
    def hint(self) -> str | None:
        """What the revision binder would accept (ruling round 6, B2): its refusal's hint, which
        admission's and the job's `revision_unsupported` carry as `detail.hint` (R2.6 as amended
        by B1)."""
        return self.revision.hint


def _refusal(unbound: Unbound) -> str:
    return f"{unbound.kind}({unbound.detail})"


def select_route(document: Mapping[str, Any]) -> Route | NoRoute:
    """R2.1 as amended by ruling rounds 6 and 7: `revision_eo` whenever the revision binder binds
    — `revision_coupled` when the binding has an external (variant-backed) unit (M02 design note
    §4.4, ADR 0034 D2); else `legacy_eo` when the legacy binder binds and `legacy_admission`
    admits the revision; else no route. A legacy binding not admitted is reported as
    `unsupported(legacy_route_not_admitted(<code>))`, beside the refusal `legacy_admission`
    reports. The route's reason stays the revision binder's refusal. A pure function of the
    document; each binder reads its own copy."""
    revision = bind_revision_flowsheet(copy.deepcopy(dict(document)))
    if isinstance(revision, RevisionBinding):
        return Route(_revision_path(revision), revision)
    legacy = bind_revision_or_reason(copy.deepcopy(dict(document)))
    if isinstance(legacy, Binding):
        why = legacy_admission(document, revision, legacy)
        if why is None:
            return Route("legacy_eo", legacy, _refusal(revision))
        return NoRoute(
            why,
            Unbound("unsupported", f"legacy_route_not_admitted({refusal_code(why.detail)})"),
        )
    return NoRoute(revision, legacy)


def _revision_path(binding: RevisionBinding) -> SolvePath:
    """`revision_coupled` iff the binding has an external unit (§4.4), else `revision_eo`."""
    return "revision_coupled" if external_units(binding) else "revision_eo"


def bind_route(solve_path: SolvePath, document: Mapping[str, Any]) -> Route | Unbound:
    """The named route's binder only (R2.5: a rerun follows the recorded route and never
    re-routes). On `legacy_eo` the route's reason is the revision binder's refusal, as
    `select_route` records it, or `None` when that binder binds (a route taken by request). On
    `revision_coupled` the binding must have an external unit."""
    revision = bind_revision_flowsheet(copy.deepcopy(dict(document)))
    if solve_path == "revision_eo":
        return Route("revision_eo", revision) if isinstance(revision, RevisionBinding) else revision
    if solve_path == "revision_coupled":
        if not isinstance(revision, RevisionBinding):
            return revision
        if not external_units(revision):
            return Unbound("unsupported", "no_external_unit")
        return Route("revision_coupled", revision)
    legacy = bind_revision_or_reason(copy.deepcopy(dict(document)))
    if not isinstance(legacy, Binding):
        return legacy
    reason = None if isinstance(revision, RevisionBinding) else _refusal(revision)
    return Route("legacy_eo", legacy, reason)


def traced_analysis(
    spec: Any,
    graph: Any,
    *,
    model_version: str,
    constants_sha256: str,
    specification_ids: Mapping[str, str],
    row_units: Mapping[str, str],
) -> tuple[StructuralReport, Declaration | None]:
    """`analyse(...)` as its two documented halves, `trace_declaration` then
    `analyse_declaration`, with the same arguments; and the declaration the report was analysed
    from, so that `inspect_structure`'s index is built from it (M06 design note §4.1). A
    declaration that cannot be traced has none: the report is `analyse`'s `UNSUPPORTED` one."""
    try:
        declaration = trace_declaration(
            spec,
            model_version=model_version,
            constants_sha256=constants_sha256,
            specification_ids=specification_ids,
            row_units=row_units,
        )
    except StructureUnavailableError:
        report = analyse(
            spec,
            graph,
            model_version=model_version,
            constants_sha256=constants_sha256,
            specification_ids=specification_ids,
            row_units=row_units,
        )
        return report, None
    report = analyse_declaration(declaration, graph, specification_ids=specification_ids)
    return report, declaration


def route_declaration(route: Route) -> tuple[StructuralReport, Declaration | None]:
    """`route_analysis`'s report and the declaration it was analysed from (`traced_analysis`)."""
    binding = route.binding
    model_version, constants = declaration_identity(binding.spec)
    return traced_analysis(
        binding.spec,
        binding.graph,
        model_version=model_version,
        constants_sha256=constants,
        specification_ids=binding.specification_ids if route.solve_path == "legacy_eo" else {},
        row_units=binding.row_units,
    )


def route_analysis(route: Route) -> StructuralReport:
    """T01's analysis of the formulation `solve` runs on `route`: its binder's declaration with its
    plan builder's inputs (`plan_revision`'s on `revision_eo`, `legacy_plan`'s on `legacy_eo`).
    Builds no plan and evaluates nothing (T01 A03)."""
    return route_declaration(route)[0]


def _index(
    declaration: Declaration | None,
    graph: ProcessGraph | None,
    binding: Binding | RevisionBinding,
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """The `rows` and `columns` members (M06 design note §4.1); both `None` when no declaration
    was traced."""
    if declaration is None or graph is None:
        return {"rows": None, "columns": None}
    return structure_index(declaration, graph, binding, document)


def route_structure(document: Mapping[str, Any]) -> dict[str, Any]:
    """`inspect_structure`'s document (§4.2 as amended by ruling round 1 R1.5 and ruling round 6,
    B1): the structural report of the formulation `solve` will use, naming its `solve_path` and
    its `route_reason` (the revision binder's refusal on `legacy_eo`, `None` on `revision_eo`) —
    or, when no route binds the revision, `validate()`'s reason that the structural analysis did
    not run and the `hint` of the refusal it reports. New in T07 and in no identity key; W5
    projects it.

    ADR 0019 Amendment 3 (A3.1) adds, beside the report and never inside it, the row and column
    index of the declaration that produced it (`rows`, `columns`); and, when no route binds, the
    structural report `validate()` analysed for the document (`validation_structural_report`)
    with the index of its declaration — each `None` when no structural stage ran."""
    from openflowsheet.application.validation import structural_analysis, validate

    route = select_route(document)
    if not isinstance(route, Route):
        report = validate(document, "simulation")
        # The hint of the refusal `validate()` reports, when its structural stage ran (ruling
        # round 6, B1 item 4); a document refused before that stage reports none.
        ran = any(check.stage == "structural_analysis" for check in report.checks)
        analysis = structural_analysis(document) if ran else None
        reported = None if analysis is None else analysis.refusal
        structure: dict[str, Any] = {
            "not_run_reason": report.structural_counts_absent_reason or route.reason,
            "hint": None if reported is None else reported.hint,
            "validation_structural_report": None,
            "rows": None,
            "columns": None,
        }
        if analysis is not None and analysis.report is not None:
            structure["validation_structural_report"] = analysis.report.as_document()
            structure.update(
                _index(analysis.declaration, analysis.graph, analysis.binding, document)
            )
        return structure
    analysis_report, declaration = route_declaration(route)
    return {
        "solve_path": route.solve_path,
        "route_reason": route.reason,
        "structural_report": analysis_report.as_document(),
        **_index(declaration, route.binding.graph, route.binding, document),
    }


# -- the legacy route's plan (R2.2) -----------------------------------------------------------


def legacy_plan(binding: Binding, policy: SolvePolicy) -> tuple[ExecutionPlan, StructuralReport]:
    """The registered SYN-001 binding's plan (T02 §7.5): the declaration, T01's analysis, the
    specification regions of the freed and promoted coordinates, the plan."""
    model_version, constants = declaration_identity(binding.spec)
    identity: dict[str, Any] = {
        "row_units": binding.row_units,
        "specification_ids": binding.specification_ids,
        "model_version": model_version,
        "constants_sha256": constants,
    }
    declaration = trace_declaration(binding.spec, **identity)
    report = analyse(binding.spec, binding.graph, **identity)
    regions = (
        specification_regions(
            declaration,
            binding.graph,
            report,
            freed=binding.freed,
            promoted=binding.promoted or {},
            missing_guesses=binding.missing_guesses,
        )
        if binding.freed
        else ()
    )
    plan = build_execution_plan(
        spec=binding.spec,
        declaration=declaration,
        graph=binding.graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in binding.flowsheet.units()},
        policy=policy,
        specifications=regions,
    )
    return plan, report


# -- one run ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteRun:
    """What a route's solve produced, before anything is written: the plan (or T02's refusal),
    T01's report, the plan run, and exactly one of the certificate and the failure bundle."""

    route: Route
    plan: ExecutionPlan | PlanRefusal
    report: StructuralReport
    #: `None` when the plan was refused.
    run: PlanResult | None
    #: The region's `SolvePlan`: the certified solve's, or the one whose run failed.
    solve_plan: SolvePlan | None
    certificate: SolutionCertificate | None
    failure: FailureBundle | None
    #: The certified state, `None` without a certificate.
    state: Mapping[str, float] | None
    #: `revision_coupled` only (ADR 0034 D6): `external-coupling.json`. The other fields are the
    #: last inner solve's, and `route.binding` is its binding (at the final w).
    coupling: Mapping[str, Any] | None = None
    #: `revision_coupled` only: the coupling's outcome when it is not the inner solve's
    #: (`COUPLING_NOT_CONVERGED`, `EVALUATION_ERROR`; ADR 0034 D3).
    coupled_outcome: str | None = None
    #: `revision_coupled` only: the run's reproducibility class (§7.2), else the flowsheet's.
    reproducibility_class: str | None = None

    @property
    def outcome(self) -> str:
        if self.coupled_outcome is not None:
            return self.coupled_outcome
        if self.run is not None:
            return str(self.run.outcome)
        assert isinstance(self.plan, PlanRefusal)
        return str(self.plan.outcome)


def check_policy_document(check_policy: CheckPolicy) -> dict[str, Any]:
    """`check-policy.json` (§12.3): exactly `CheckPolicy.sha256`'s preimage."""
    return {"policy_id": check_policy.policy_id, "tolerances": dict(check_policy.tolerances)}


def _run_identity(certificate: SolutionCertificate, plan: ExecutionPlan) -> SolutionCertificate:
    """The certificate with the ids of the plan and policy the run used (T08 D2, T08.A11).

    Neither object handed to a revision-route verifier (`run`, or the `solve_eo` step's
    `RegionResult`) carries a plan, so the verifier leaves `policy_id` and `plan_id` empty; they
    are the `ExecutionPlan`'s, as the run manifest's are. Only these two fields are set: the
    verdict, its checks and `certificate_id` are the verifier's, unchanged."""
    if certificate.policy_id or certificate.plan_id:
        raise ValueError(
            f"defect: the verifier set policy_id={certificate.policy_id!r}, "
            f"plan_id={certificate.plan_id!r} on a revision route"
        )
    return replace(certificate, policy_id=plan.policy_id, plan_id=plan.plan_id)


def _judged(source: Any, run: PlanResult) -> dict[str, float]:
    """The state the verifier judged (ruling round 2 F1.1): the first of `source.final_state`,
    `source.state` and `run.state` that is not `None`, `source` being the object handed to the
    verifier (`run` on `revision_eo`, the `solve_eo` step's `RegionResult` on `legacy_eo`)."""
    for state in (getattr(source, "final_state", None), getattr(source, "state", None), run.state):
        if state is not None:
            return dict(state)
    raise ValueError("defect: a certified run with no state")


def solve_route(
    route: Route,
    document: Mapping[str, Any],
    *,
    policy: SolvePolicy,
    check_policy: CheckPolicy,
    trace: Trace | None = None,
    stage: Stage | None = None,
    warm_start: WarmStartCandidate | None = None,
    experiments: Experiments | None = None,
    on_iteration: Callable[[int, int], None] | None = None,
) -> RouteRun:
    """§12.1's steps on `route` (R2.2's table), from the registered initializer (`user_start`
    unset). A `VerifierError` propagates: the verifier refused to judge, so nothing is certified
    and nothing is diagnosed. `RunUnsupportedError` when the record has no registered bundle
    mapping, and when T02 refuses the plan's rank structure (`plan_refused(...)`).

    `trace` is the one the solve records into (a fresh one when `None`, as before): the job
    runner passes its own, so that the events recorded before an interruption survive it
    (§8.1). `stage` is called at the start of `plan`, `solve` and `verify` (§6.4).

    `warm_start` is the source-2 candidate the caller found (ADR 0024 D2) or recorded (D5); it is
    read only on `revision_eo` and `revision_coupled` (its k = 0 inner solve), under a policy
    whose chain names the source (`execute_plan`).

    On `revision_coupled` (M02 design note §4.4) `experiments` runs the experiments — the job's
    runner, or a replay's recorded backend — and `on_iteration(k, max_outer)` is called at each
    outer iteration's start; a coupled run without `experiments` is
    `unsupported(external_runner_unavailable)`.
    """
    at = stage if stage is not None else _no_stage
    binding = route.binding
    if route.solve_path == "revision_coupled":
        return _solve_coupled(
            route,
            document,
            policy=policy,
            check_policy=check_policy,
            trace=trace,
            at=at,
            warm_start=warm_start,
            experiments=experiments,
            on_iteration=on_iteration,
        )
    at("plan")
    try:
        if route.solve_path == "revision_eo":
            plan, report = plan_revision(binding, policy, trace=trace)
        else:
            plan, report = legacy_plan(binding, policy)
    except UnsupportedRankStructureError as error:
        # T02 §7.1 refuses the plan before any evaluation, with no `PlanRefusal` and so no
        # registered bundle: §12.3's `plan_refused(<code>)`. Admission keeps it off every route
        # `select_route` gives (C5, review-2 S3); a recorded route re-bound by `bind_route`, which
        # never re-admits (R2.5), can still reach it.
        raise RunUnsupportedError("plan_refused(UNSUPPORTED_RANK_STRUCTURE)") from error

    if isinstance(plan, PlanRefusal):
        return _refused_plan(route, plan, report)

    at("solve")
    run = execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=policy,
        trace=trace,
        warm_start=warm_start if route.solve_path == "revision_eo" else None,
    )
    planned = [step for step in plan.steps if step.kind == "solve_eo"]
    region_plan = (
        plan.steps[-1].solve_plan
        if route.solve_path == "revision_eo"
        else (planned[0].solve_plan if len(planned) == 1 else None)
    )

    if run.outcome == "CONVERGED":
        if route.solve_path == "revision_eo" and run.state is not None:
            at("verify")
            certificate = _run_identity(
                verify_revision(
                    binding, document, run, policy=check_policy, solve_plan=region_plan
                ),
                plan,
            )
            return RouteRun(
                route, plan, report, run, region_plan, certificate, None, _judged(run, run)
            )
        solved = [step for step in run.steps if step.kind == "solve_eo"]
        if (
            route.solve_path == "legacy_eo"
            and len(solved) == 1
            and isinstance(solved[0].detail, RegionResult)
        ):
            detail = solved[0].detail
            at("verify")
            certificate = _run_identity(
                verify_bound(
                    binding, document, detail, policy=check_policy, solve_plan=region_plan
                ),
                plan,
            )
            return RouteRun(
                route, plan, report, run, region_plan, certificate, None, _judged(detail, run)
            )
        # R2.2 certifies a `legacy_eo` run through its `solve_eo` step's region result; a legacy
        # plan without one (no freed or promoted coordinate: a loop plan) has no registered
        # verifier on this route.
        kinds = ",".join(step.kind for step in plan.steps)
        raise RunUnsupportedError(f"certificate_unmapped({route.solve_path},{kinds})")
    return _failed_run(route, plan, report, run, region_plan)


def _refused_plan(route: Route, plan: PlanRefusal, report: StructuralReport) -> RouteRun:
    """§12.3: T02's registered mapping of a refused plan; `plan_refused` where it has none
    (§14.6 S11, logged for the design lane)."""
    try:
        failure = refusal_bundle(plan)
    except KeyError as error:
        raise RunUnsupportedError(f"plan_refused({plan.outcome})") from error
    return RouteRun(route, plan, report, None, None, None, failure, None)


def _failed_run(
    route: Route,
    plan: ExecutionPlan,
    report: StructuralReport,
    run: PlanResult,
    region_plan: SolvePlan | None,
) -> RouteRun:
    """§12.3's failure bundle of a plan run that did not converge, or `RunUnsupportedError`."""
    last = run.steps[-1] if run.steps else None
    if last is not None and isinstance(last.detail, RegionResult):
        failure = region_bundle(last.detail, run.trace, step_index=last.index, plan=plan)
        return RouteRun(route, plan, report, run, region_plan, None, failure, None)
    if (
        last is not None
        and last.kind == "solve_eo"
        and last.outcome == "INITIALIZATION_FAILED"
        and last.detail is None
        and initializer_source(last.message) is not None
    ):
        # Ruling round 3, Q1: the registered initializer refused before any attempt opened.
        failure = initializer_bundle(last, run.trace, plan=plan)
        return RouteRun(route, plan, report, run, region_plan, None, failure, None)
    # §12.3 maps a failed step to a bundle through its `RegionResult`, or an EO initializer's
    # registered refusal (ruling round 3, Q1). Any other step that failed with none (an
    # unregistered message, a refused `evaluate`, a loop's own K03 result) has no registered
    # mapping on this path.
    held = type(last.detail).__name__ if last is not None else "no_step"
    step_kind = last.kind if last is not None else "none"
    raise RunUnsupportedError(f"failure_bundle_unmapped({run.outcome},{step_kind},{held})")


def _inner_failure(
    route: Route,
    plan: ExecutionPlan,
    report: StructuralReport,
    run: PlanResult,
    region_plan: SolvePlan | None,
) -> dict[str, Any]:
    """M02 review F5: the diagnosis of a coupled run's last failed inner solve — the outcome,
    taxonomy and attempt tree of the failure bundle §12.3 gives that inner run on its own, or,
    for an inner failure §12.3 maps to no bundle, its outcome with an empty tree and the reason."""
    try:
        failed = _failed_run(route, plan, report, run, region_plan).failure
    except RunUnsupportedError as error:
        return {"outcome": str(run.outcome), "attempt_tree": [], "unmapped": error.code}
    assert failed is not None
    return {
        "outcome": failed.outcome,
        "taxonomy": failed.taxonomy,
        "attempt_tree": [dict(entry) for entry in failed.attempt_tree],
    }


def _solve_coupled(
    route: Route,
    document: Mapping[str, Any],
    *,
    policy: SolvePolicy,
    check_policy: CheckPolicy,
    trace: Trace | None,
    at: Stage,
    warm_start: WarmStartCandidate | None,
    experiments: Experiments | None,
    on_iteration: Callable[[int, int], None] | None,
) -> RouteRun:
    """`revision_coupled` (M02 design note §4.3–§4.4): the outer coupling, then the final inner
    solve certified with the coupling's evidence, or a bundle. Each inner solve is planned and run
    as `revision_eo`'s; `plan` and `solve` are called once, before the first inner solve."""
    from openflowsheet.run.session import _reproducibility_class

    if experiments is None:
        raise RunUnsupportedError("external_runner_unavailable")
    at("plan")
    at("solve")
    try:
        solved = solve_coupled(
            route.binding,
            policy=policy,
            experiments=experiments,
            trace=trace,
            warm_start=warm_start,
            on_iteration=on_iteration,
        )
    except CouplingUnsupportedError as error:
        raise RunUnsupportedError(error.code) from error
    except UnsupportedRankStructureError as error:
        raise RunUnsupportedError("plan_refused(UNSUPPORTED_RANK_STRUCTURE)") from error
    inner, coupling = solved.inner, solved.coupling
    final = Route("revision_coupled", inner.binding)
    extra: dict[str, Any] = {
        "coupling": solved.record,
        "reproducibility_class": reproducibility_class(
            solved.units, _reproducibility_class(inner.binding.flowsheet)
        ),
    }
    if isinstance(inner.plan, PlanRefusal):  # at k = 0: the plan's own outcome, passed through
        return replace(_refused_plan(final, inner.plan, inner.report), **extra)
    run = inner.run
    assert run is not None
    plan = inner.plan
    region_plan = plan.steps[-1].solve_plan
    if coupling.outcome == "CONVERGED":
        assert run.state is not None
        at("verify")
        certificate = _run_identity(
            verify_revision(
                inner.binding,
                document,
                run,
                policy=check_policy,
                solve_plan=region_plan,
                external=coupling_evidence(solved, run.state),
            ),
            plan,
        )
        return RouteRun(
            final,
            plan,
            inner.report,
            run,
            region_plan,
            certificate,
            None,
            _judged(run, run),
            **extra,
        )
    if coupling.outcome in ("COUPLING_NOT_CONVERGED", "EVALUATION_ERROR"):
        failure = coupling_bundle(
            coupling.outcome,
            coupling.reason,
            coupling=compact_record(solved.record),
            implicated=[unit.unit_id for unit in solved.units],
            plan=plan,
            counters=run.counters,
            inner_failure=(
                _inner_failure(final, plan, inner.report, run, region_plan)
                if coupling.reason == "inner_failed"
                else None
            ),
        )
        return RouteRun(
            final,
            plan,
            inner.report,
            run,
            region_plan,
            None,
            failure,
            None,
            coupled_outcome=coupling.outcome,
            **extra,
        )
    # §4.4: an inner failure at k = 0 passes its own outcome through, with its own bundle.
    return replace(_failed_run(final, plan, inner.report, run, region_plan), **extra)


def run_revision_session(
    route: Route,
    document: Mapping[str, Any],
    directory: Path,
    *,
    run_id: str,
    policy: SolvePolicy,
    check_policy: CheckPolicy,
    policy_requested: str,
    trace: Trace | None = None,
    stage: Stage | None = None,
    warm_start: WarmStartCandidate | None = None,
    experiments: Experiments | None = None,
    on_iteration: Callable[[int, int], None] | None = None,
) -> RunManifest:
    """Solve, verify and write the bundle (§12.3 as amended by R2.4). Mirrors `run_session`.

    `document` is the stored revision's canonical document; `policy` is the resolved policy and
    `policy_requested` the id as submitted (`"default"` or a registered id). Nothing is written
    when the run ends in a `VerifierError` or `RunUnsupportedError`. `trace`, `stage`,
    `warm_start`, `experiments` and `on_iteration` are `solve_route`'s; `stage` is also called at
    the start of `bundle`. A `revision_coupled` bundle is the final inner solve's, plus
    `external-coupling.json` (ADR 0034 D6).
    `solve-path.json` gains `warm_start` (ADR 0024 D4) iff the solve consulted the source.
    """
    from openflowsheet.run.session import _numerical_policy_id, _reproducibility_class

    started = started_now()
    clock = time.monotonic()
    result = solve_route(
        route,
        document,
        policy=policy,
        check_policy=check_policy,
        trace=trace,
        stage=stage,
        warm_start=warm_start,
        experiments=experiments,
        on_iteration=on_iteration,
    )
    (stage if stage is not None else _no_stage)("bundle")
    # The route the result was solved on: on `revision_coupled`, its binding is the final inner
    # solve's (at the final w); on every other route it is `route` itself.
    route = result.route

    if result.run is not None:
        trace = result.run.trace
    else:
        assert isinstance(result.plan, PlanRefusal)
        trace = result.plan.trace
    solve_path: dict[str, Any] = {
        "solve_path": route.solve_path,
        "route_reason": route.reason,
        "policy_requested": policy_requested,
    }
    warm = result.run.warm_start if result.run is not None else None
    if warm is not None:
        solve_path["warm_start"] = warm.as_document()
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in trace.events],
        "structural-report.json": result.report.as_document(),
        "revision.json": dict(document),
        "solve-policy.json": policy.as_document(),
        "check-policy.json": check_policy_document(check_policy),
        "solve-path.json": solve_path,
    }
    if isinstance(result.plan, ExecutionPlan):
        artifacts["execution-plan.json"] = result.plan.as_document()
    if result.solve_plan is not None:
        artifacts["solve-plan.json"] = result.solve_plan.as_document()
    if result.certificate is not None:
        artifacts["solution-certificate.json"] = result.certificate.as_document()
        # Ruling round 2 F1.1: the judged state, iff there is a certificate; its digest must be
        # the certificate's, or nothing is written (a producer defect, never a substitute state).
        assert result.state is not None
        spec = route.binding.spec
        state = solution_state.document(spec.variable_ids, state_vector(spec, result.state))
        if state["state_sha256"] != result.certificate.target_state_sha256:
            raise SolutionStateMismatchError("solution_state_mismatch")
        artifacts[solution_state.NAME] = state
    else:
        assert result.failure is not None
        artifacts["failure-bundle.json"] = result.failure.as_document()
    if result.coupling is not None:
        artifacts[COUPLING_NAME] = dict(result.coupling)

    # R0 of the documents **as written**: ADR 0002 spells an integral float as an integer, and
    # `execution_plan_r0` keeps a float as its `repr` but an integer as itself, so the projection
    # of the in-memory plan (`3.0` → `"3.0"`) is not the projection of its bytes (`3`). Hashing
    # the written form keeps the digest recomputable from the bundle alone. For every other
    # branch the two are the same projection (they carry no float).
    written = json.loads(canonical_json(artifacts))
    model_version, constants = declaration_identity(route.binding.spec)
    manifest = RunManifest(
        run_id=run_id,
        model_version=model_version,
        constants_sha256=constants,
        policy_id=policy.policy_id,
        plan_id=result.plan.plan_id if isinstance(result.plan, ExecutionPlan) else "",
        check_policy_sha256=check_policy.sha256,
        policy_sha256=policy_sha256(policy),
        artifact_r0_sha256=r0_sha256(r0_projection(written)),
        numerical_policy_id=_numerical_policy_id(),
        environment=environment(),
        artifacts={},
        outcome=result.outcome,
        verification_status=(
            result.certificate.verification_status if result.certificate is not None else None
        ),
        reproducibility_class=(
            result.reproducibility_class
            if result.reproducibility_class is not None
            else _reproducibility_class(route.binding.flowsheet)
        ),
        started_at=started,
        elapsed_seconds=time.monotonic() - clock,
    )
    return write_bundle(Path(directory), manifest, artifacts)


# -- the tear path's registered cases (moved from the CLI, §12.3) -----------------------------


def registered_case(case_id: str) -> dict[str, Any] | None:
    """A registered SYN-001 variant (`benchmarks/syn001/reference_values.yaml`), or `None`."""
    import yaml

    registry = packaged("benchmarks/syn001/reference_values.yaml")
    if registry.is_file():
        loaded = yaml.safe_load(registry.read_text(encoding="utf-8"))
        for entry in loaded["variants"]:
            if entry["case_id"] == case_id:
                return dict(entry)
    return None


def registered_flowsheet(case: Mapping[str, Any]) -> Any:
    """The tear path's `Syn001Flowsheet` of a registered variant, as the K06 CLI builds it."""
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.thermo.syn001 import Syn001Provider

    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(model_version="K06-cli@" + "0" * 64, constants_sha256="0" * 64),
        split_fraction=float(case["r"]),
        flash_temperature=float(case["T_flash_K"]),
        heater_temperature=float(case["T_heater_K"]),
        pressure=float(case["P_Pa"]),
    )


def rerun_registered(case: Mapping[str, Any], directory: Path, *, run_id: str) -> Rerun:
    """`run_session` of a registered variant into `directory`, read back as a `Rerun`."""
    from openflowsheet.run.session import run_session

    fresh = run_session(registered_flowsheet(case), directory, run_id=run_id)
    return Rerun({name: read_artifact(directory, name) for name in fresh.artifacts})


def declared_kinds(*specs: Any) -> dict[str, str]:
    """ADR 0025 D5 (W4): each variable's declared quantity kind, unioned over the compiled
    problems a rerun solved (`ProblemSpec.variable_kinds`), for comparing its solution state.

    A route's plan steps all solve `route.binding.spec` (`solve_route` hands it to
    `execute_plan`), which is also the spec `solution-state.json` is written over, so a rerun
    passes that one spec. A variable given two kinds is a defect, never a choice: it raises."""
    kinds: dict[str, str] = {}
    for spec in specs:
        for name, kind in spec.variable_kinds.items():
            if kinds.setdefault(name, kind) != kind:
                raise ValueError(
                    f"variable {name!r} is declared both {kinds[name]!r} and {kind!r} "
                    "(ADR 0025 D5: a solution state is compared under one declared kind)"
                )
    return kinds


# -- reproduce (§12.3 "Rerun", R2.5) -----------------------------------------------------------


@dataclass(frozen=True)
class Reproduction:
    """`reproduce`'s result: the replay report, and the rerun's bundle when one was written."""

    report: ReplayReport
    rerun_manifest: RunManifest | None = None


def _inspected(directory: Path, reason: str | None = None) -> ReplayReport:
    """The archive inspected and not re-run: `inspected_archived_results` / `NOT_RUN`, with the
    environment's reasons and, when given, why no rerun happened (§12.3; Q26 (ii))."""
    report = replay(directory, None)
    reasons = report.reasons
    if reason is not None:
        reasons = (*(entry for entry in reasons if entry != "no rerun was supplied"), reason)
    return replace(report, mode="inspected_archived_results", verdict="NOT_RUN", reasons=reasons)


def _recorded_warm_start(recorded: Any) -> WarmStartCandidate | None:
    """ADR 0024 D5: the candidate a bundle's `solve-path.json` recorded, or `None` (absent, or no
    member: the policy did not name the source)."""
    member = recorded.get("warm_start") if isinstance(recorded, Mapping) else None
    return WarmStartCandidate.from_record(member) if isinstance(member, Mapping) else None


def reproduce_bundle(
    directory: Path,
    *,
    rerun: bool,
    rerun_directory: Path,
    run_id: str,
    stage: Stage | None = None,
) -> Reproduction:
    """§12.3's rerun rule, as amended by R2.5.

    Nothing is re-run when `rerun` is false, when the archive fails its integrity check, or when
    the environment already decides `inspected_archived_results` (ADR 0007 D4: the mode is
    decided before anything runs). A bundle with `revision.json` reruns its **recorded** route
    after its policy documents recompute to the manifest's hashes; one without is K05's SYN-001
    shape and reruns only when `run_id` is a registered case. There is no fallback to
    SYN-001-nominal (§12.3, D-Q6): comparing an unknown run with nominal's rerun would be a
    misleading `MISMATCH`. The CLI's `replay --rerun` is this function (T08 review 2, Ruling 11).

    `stage` (§6.4) is called with `integrity` on entry, `rerun` before a rerun, and `compare`
    before the report is built; a rerun's bundle is complete in `rerun_directory` by `compare`.
    """
    at = stage if stage is not None else _no_stage
    directory = Path(directory)
    at("integrity")
    if not rerun:
        at("compare")
        return Reproduction(_inspected(directory))
    if not verify_bundle(directory).ok:
        at("compare")
        return Reproduction(replay(directory, None))
    manifest, _ = read_manifest(directory)
    if decide_mode(manifest.environment, environment())[0] == "inspected_archived_results":
        at("compare")
        return Reproduction(_inspected(directory))
    if manifest.numerical_policy_id not in KNOWN_POLICY_IDS:
        # ADR 0025 (Q4): a record under a policy this build does not know is not re-run;
        # `replay` names the policy as the reason.
        at("compare")
        return Reproduction(replay(directory, None))

    if "revision.json" not in manifest.artifacts:
        case = registered_case(manifest.run_id)
        if case is None:
            at("compare")
            return Reproduction(_inspected(directory, "rerun_unsupported(no_revision_document)"))
        at("rerun")
        fresh = rerun_registered(case, Path(rerun_directory), run_id=run_id)
        at("compare")
        return Reproduction(replay(directory, fresh), read_manifest(Path(rerun_directory))[0])

    if "solve-path.json" not in manifest.artifacts:
        at("compare")
        return Reproduction(_inspected(directory, "rerun_unsupported(no_solve_path)"))
    recorded = read_artifact(directory, "solve-path.json")
    try:
        policy = SolvePolicy.from_document(read_artifact(directory, "solve-policy.json"))
        check = read_artifact(directory, "check-policy.json")
        check_policy = CheckPolicy(policy_id=check["policy_id"], tolerances=check["tolerances"])
        matches = (
            policy_sha256(policy) == manifest.policy_sha256
            and check_policy.sha256 == manifest.check_policy_sha256
        )
    except (ValueError, TypeError, KeyError):
        matches = False
    if not matches:
        at("compare")
        return Reproduction(_inspected(directory, "policy_document_mismatch"))

    solve_path = recorded.get("solve_path") if isinstance(recorded, Mapping) else None
    document = read_artifact(directory, "revision.json")
    route = bind_route(solve_path, document) if solve_path in SOLVE_PATHS else None
    if not isinstance(route, Route):
        at("compare")
        return Reproduction(
            _inspected(directory, f"rerun_unsupported(route_unbound({solve_path}))")
        )
    coupling: Mapping[str, Any] | None = None
    coupling_found: list[str] = []
    classified_bitwise = True
    if route.solve_path == "revision_coupled":
        # M02 design note §7.2 step 1: the record against its schema, and each embedded request's
        # key against its content.
        if COUPLING_NAME not in manifest.artifacts:
            at("compare")
            return Reproduction(_inspected(directory, "rerun_unsupported(no_external_coupling)"))
        record: Mapping[str, Any] = read_artifact(directory, COUPLING_NAME)
        coupling = record
        problem = coupling_record_problem(record)
        if problem is not None:
            at("compare")
            return Reproduction(
                _inspected(directory, f"rerun_unsupported(external_coupling_invalid({problem}))")
            )
        # §14.5 D8 (R-308) item 2: the constants digest's R0 guard, by recomputation.
        constants = final_constants(route.binding, record)
        if constants is not None and constants[0] != constants[1]:
            final = record["iterations"][-1]
            coupling_found.append(
                f"coupling_constants: {constants[1]} rebuilt at the record's final w "
                f"{final['w']!r} (k = {final['k']}), against the recorded {constants[0]}"
            )
    at("rerun")
    with tempfile.TemporaryDirectory(prefix="ofs-replay-") as scratch:
        experiments = (
            None
            if coupling is None
            else RecordedExperiments(
                coupling,
                provider=PrC1Provider(),
                scratch=Path(scratch),
                policy_id=manifest.numerical_policy_id,
            )
        )
        try:
            rerun_manifest = run_revision_session(
                route,
                document,
                Path(rerun_directory),
                run_id=run_id,
                policy=policy,
                check_policy=check_policy,
                policy_requested=str(recorded.get("policy_requested")),
                # ADR 0024 D5: the recorded candidate, never a store lookup.
                warm_start=_recorded_warm_start(recorded),
                experiments=experiments,
            )
        except ReplayDivergenceError as error:
            at("compare")
            report = _diverged(directory, error.difference)
            return Reproduction(_with_differences(report, coupling_found))
    artifacts = {
        name: read_artifact(Path(rerun_directory), name) for name in rerun_manifest.artifacts
    }
    if coupling is not None:
        # §14.5 D8 (R-308) items 1 and 3: the inner solves' constants digests for shape, in the
        # record and in every artifact that carries the final one (build log D94; item 2 guards
        # it; the manifest is not compared), and the iterates under the archive's policy.
        artifacts = {
            name: _constants_for_shape(document, read_artifact(directory, name))
            if name in manifest.artifacts
            else document
            for name, document in artifacts.items()
        }
        if COUPLING_NAME in artifacts:
            fresh_record = artifacts[COUPLING_NAME]
            coupling_found += iterate_differences(
                fresh_record, coupling, manifest.numerical_policy_id
            )
            # R-317 (b): the record's floats at their registered floors; `replay` compares the
            # rest. A float taken from the record is not a bitwise match.
            shaped, floored = record_differences(
                fresh_record, coupling, manifest.numerical_policy_id
            )
            coupling_found += floored
            artifacts[COUPLING_NAME] = shaped
            classified_bitwise = shaped == fresh_record
        # Build log D130 (D124): a failure bundle's compact copy of the record by the same rules,
        # its `record_sha256` for shape.
        failure = artifacts.get(FAILURE_NAME)
        if FAILURE_NAME in manifest.artifacts and isinstance(failure, dict):
            archived = read_artifact(directory, FAILURE_NAME)
            fresh_copy = failure.get("observations", {}).get("external_coupling")
            archived_copy = archived.get("observations", {}).get("external_coupling")
            if isinstance(fresh_copy, dict) and isinstance(archived_copy, dict):
                shaped_copy, floored = compact_differences(
                    fresh_copy,
                    archived_copy,
                    coupling["coupling_block"],
                    manifest.numerical_policy_id,
                )
                coupling_found += floored
                classified_bitwise = classified_bitwise and shaped_copy == fresh_copy
                observations = {**failure["observations"], "external_coupling": shaped_copy}
                artifacts[FAILURE_NAME] = {**failure, "observations": observations}
    at("compare")
    # On `revision_coupled` the state is written over the final inner spec, whose columns and
    # kinds are the route's binding's (w moves constants only).
    rerun_result = Rerun(artifacts, variable_kinds=declared_kinds(route.binding.spec))
    report = replay(directory, rerun_result)
    if not classified_bitwise and report.bitwise_floats:
        report = replace(report, bitwise_floats=False)
    if experiments is not None and coupling is not None:
        report = _replayed_from_record(report, experiments, coupling)
    return Reproduction(_with_differences(report, coupling_found), rerun_manifest)


_HEX64: Final = re.compile(r"[0-9a-f]{64}")
FAILURE_NAME: Final = "failure-bundle.json"


def _constants_for_shape(fresh: Any, archived: Any) -> Any:
    """§14.5 D8 (R-308) item 1. On `revision_coupled` every `constants_sha256` digests an inner
    solve's X̂ and ΔT̂, which Broyden computes in floating point: by ADR 0007's criterion a digest
    of an R1/R2 quantity, compared for shape, never for value. `fresh` with each well-formed
    `constants_sha256` that the archive also has, well-formed, at the same place replaced by the
    archive's; anything else is left for `replay` to compare, so a malformed digest is a
    difference. The final digest's R0 guard is `final_constants`'s recomputation."""
    if isinstance(fresh, dict) and isinstance(archived, dict):
        shaped: dict[str, Any] = {}
        for key, value in fresh.items():
            theirs = archived.get(key)
            if (
                key == "constants_sha256"
                and isinstance(value, str)
                and isinstance(theirs, str)
                and _HEX64.fullmatch(value)
                and _HEX64.fullmatch(theirs)
            ):
                shaped[key] = theirs
            else:
                shaped[key] = _constants_for_shape(value, theirs) if key in archived else value
        return shaped
    if isinstance(fresh, list) and isinstance(archived, list):
        return [
            _constants_for_shape(value, archived[index]) if index < len(archived) else value
            for index, value in enumerate(fresh)
        ]
    return fresh


def _with_differences(report: ReplayReport, found: list[str]) -> ReplayReport:
    """`report` with the coupled route's own differences (§14.5 D8) added: any one is a
    `MISMATCH`."""
    if not found:
        return report
    return replace(report, differences=(*report.differences, *found), verdict="MISMATCH")


def _diverged(directory: Path, difference: str) -> ReplayReport:
    """§7.2: a recomputed external request that is not the record's — `MISMATCH`, naming it."""
    report = replay(directory, None)
    reasons = tuple(entry for entry in report.reasons if entry != "no rerun was supplied")
    return replace(report, verdict="MISMATCH", reasons=reasons, differences=(difference,))


def _replayed_from_record(
    report: ReplayReport, experiments: RecordedExperiments, coupling: Mapping[str, Any]
) -> ReplayReport:
    """§7.2 step 4: `reasons` gains how the external results were obtained, `recorded_environment`
    the frozen fingerprints, and an in-process re-evaluation that differs from the record is a
    difference (`external_result(<k>, <unit>)…`)."""
    reasons = (
        *report.reasons,
        f"external_results_replayed_from_record({experiments.replayed})",
        *(
            (f"external_results_reevaluated({experiments.reevaluated})",)
            if experiments.reevaluated
            else ()
        ),
    )
    environment = {**report.recorded_environment, "external_fingerprints": coupling["frozen"]}
    found = (*report.differences, *experiments.differences)
    verdict = report.verdict if not experiments.differences else "MISMATCH"
    return replace(
        report,
        reasons=reasons,
        recorded_environment=environment,
        differences=found,
        verdict=verdict,
    )
