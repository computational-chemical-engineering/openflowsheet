"""Revision-built runs through the contract: route, solve, verify, bundle (T07 §12).

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
reachable through `solve`; its registered-case construction lives in `revision_replay` (§12.3),
and the CLI delegates to it.

`run_revision_session` writes a bundle `run_session`-shaped plus `execution-plan.json`,
`revision.json`, `solve-policy.json`, `check-policy.json` and `solve-path.json`, and, beside a
certificate only, `solution-state.json` (ruling round 2), under the frozen `RunManifest`
unchanged. `revision_replay.reproduce_bundle` reruns a bundle along **its recorded route** — it
never re-routes — after the archived policy documents recompute to the manifest's hashes, and
compares through `run.replay`. These are plain functions: the job runner (W4) calls them, maps
their typed refusals to `ApiError`s and registers their outputs as artifacts.

**What ends typed without a bundle** (§12.3): a `VerifierError` (the verifier refused to judge;
the job ends `failed(verifier_refused)`), a solve whose record has no registered mapping to a
certificate or a failure bundle — `RunUnsupportedError`, never a bundle invented for it — and a
judged state whose digest is not the certificate's (`SolutionStateMismatchError`, a defect).
"""

from __future__ import annotations

import copy
import json
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from openflowsheet.application.binding import Binding, bind_revision_or_reason, legacy_admission
from openflowsheet.application.binding_common import Unbound, refusal_code
from openflowsheet.application.coupled_run import (
    COUPLING_NAME,
    CoupledStart,
    CouplingUnsupportedError,
    Experiments,
    compact_record,
    coupling_evidence,
    external_units,
    reproducibility_class,
    solve_coupled,
    unused_coupling_start,
)
from openflowsheet.application.model_builders import SurrogateResolver
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.revision_continuation import (
    ContinuationSource,
    continues_revisions,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.compile.reference import state_vector
from openflowsheet.graph.analysis import analyse, analyse_declaration
from openflowsheet.graph.report import StructuralReport
from openflowsheet.graph.trace import Declaration, StructureUnavailableError, trace_declaration
from openflowsheet.messages import audit
from openflowsheet.models.revision_flowsheet import RevisionError, lowered_document
from openflowsheet.numerics.solve_record import SolvePlan, SolvePolicy, Trace
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    PlanRefusal,
    UnsupportedRankStructureError,
    build_execution_plan,
    declaration_identity,
    specification_regions,
)
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.policies import SolvePath
from openflowsheet.orchestrator.region_result import RegionResult
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.revision_continuation import RevisionContinuationRefusal
from openflowsheet.orchestrator.warm_start import (
    EXPLICIT,
    WarmStartCandidate,
    WarmStartRecord,
)
from openflowsheet.run import solution_state
from openflowsheet.run.bundle import write_bundle
from openflowsheet.run.identity import r0_projection, r0_sha256
from openflowsheet.run.manifest import RunManifest, environment, policy_sha256, started_now
from openflowsheet.verify.certificate import verify_bound, verify_revision
from openflowsheet.verify.failure import (
    FailureBundle,
    coupling_bundle,
    initializer_bundle,
    initializer_source,
    refusal_bundle,
    region_bundle,
)
from openflowsheet.verify.verdict import CheckPolicy, SolutionCertificate

__all__ = [
    "SOLVE_PATHS",
    "NoRoute",
    "Route",
    "RouteRun",
    "RunUnsupportedError",
    "SolutionStateMismatchError",
    "bind_route",
    "check_policy_document",
    "legacy_plan",
    "route_analysis",
    "route_declaration",
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


def no_stage(_: str) -> None:
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
        if audit.auditor is not None:  # MSG-G3: the reported `unsupported(<code>)` has entries
            audit.auditor.observe(code, sys._getframe(1).f_globals.get("__name__", ""))


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


def select_route(
    document: Mapping[str, Any], *, surrogates: SurrogateResolver | None = None
) -> Route | NoRoute:
    """R2.1 as amended by ruling rounds 6 and 7: `revision_eo` whenever the revision binder binds
    — `revision_coupled` when the binding has an external (variant-backed) unit (M02 design note
    §4.4, ADR 0034 D2); else `legacy_eo` when the legacy binder binds and `legacy_admission`
    admits the revision; else no route. A legacy binding not admitted is reported as
    `unsupported(legacy_route_not_admitted(<code>))`, beside the refusal `legacy_admission`
    reports. The route's reason stays the revision binder's refusal. A pure function of the
    document and of `surrogates`, the project's SurrogateManifest resolver (M04 spec §8.2); each
    binder reads its own copy.

    ADR 0062 D12 (ADR 0019 Amendment 9): a `schema_version` 2 document is routed as its lowering;
    one that does not lower has no route, both binders refusing with the lowering's refusal.
    """
    try:
        document = lowered_document(document)
    except RevisionError as error:
        refused = Unbound(error.kind, error.code, hint=error.hint)
        return NoRoute(refused, refused)
    revision = bind_revision_flowsheet(copy.deepcopy(dict(document)), surrogates=surrogates)
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


def bind_route(
    solve_path: SolvePath,
    document: Mapping[str, Any],
    *,
    surrogates: SurrogateResolver | None = None,
) -> Route | Unbound:
    """The named route's binder only (R2.5: a rerun follows the recorded route and never
    re-routes). On `legacy_eo` the route's reason is the revision binder's refusal, as
    `select_route` records it, or `None` when that binder binds (a route taken by request). On
    `revision_coupled` the binding must have an external unit. A `schema_version` 2 document is
    bound as its lowering (ADR 0062 D12).
    """
    try:
        document = lowered_document(document)
    except RevisionError as error:
        return Unbound(error.kind, error.code, hint=error.hint)
    revision = bind_revision_flowsheet(copy.deepcopy(dict(document)), surrogates=surrogates)
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
    #: `revision_coupled` only (X02 Part C): the warm-start record of the coupling's k = 0 inner
    #: run, which `solve-path.json` carries in place of the last inner run's.
    initial_warm: WarmStartRecord | None = None
    #: `revision_coupled` only (ADR 0070 D3): the `coupling` sub-record of a declared outer
    #: start, `None` when none was declared.
    coupling_start: Mapping[str, Any] | None = None

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
    coupled_start: CoupledStart | None = None,
    revision_continuation: ContinuationSource | None = None,
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
    whose chain names the source or when it is the request's explicit source (ADR 0070,
    `execute_plan`).

    `revision_continuation` is the source the caller found and assembled (ADR 0072; RRC design
    note §5.3) or rebuilt from the bundle (§5.9); its candidate or refusal is read only on
    `revision_eo`, under a policy whose `eo_recovery` names the revision continuation
    (`execute_plan`).

    On `revision_coupled` (M02 design note §4.4) `experiments` runs the experiments — the job's
    runner, or a replay's recorded backend — and `on_iteration(k, max_outer)` is called at each
    outer iteration's start; a coupled run without `experiments` is
    `unsupported(external_runner_unavailable)`. `coupled_start` is a declared outer start
    (ADR 0070 D3), read on `revision_coupled` only.
    """
    at = stage if stage is not None else no_stage
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
            coupled_start=coupled_start,
        )
    at("plan")
    plan, report = _route_plan(route, policy, trace)

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
        revision_continuation=(
            revision_continuation.found
            if route.solve_path == "revision_eo" and revision_continuation is not None
            else None
        ),
    )
    region_plan = _region_plan(route, plan)

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
        detail = _legacy_region_result(route, run)
        if detail is not None:
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


def _route_plan(
    route: Route, policy: SolvePolicy, trace: Trace | None
) -> tuple[ExecutionPlan | PlanRefusal, StructuralReport]:
    """`solve_route`'s plan of `route` (a route without an outer iteration) and its structural
    report."""
    binding = route.binding
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
    return plan, report


def _region_plan(route: Route, plan: ExecutionPlan) -> SolvePlan | None:
    """`solve_route`'s solve plan of `plan`'s region: the final step's on `revision_eo`; on
    `legacy_eo` its one `solve_eo` step's, or `None` without exactly one."""
    planned = [step for step in plan.steps if step.kind == "solve_eo"]
    region_plan = (
        plan.steps[-1].solve_plan
        if route.solve_path == "revision_eo"
        else (planned[0].solve_plan if len(planned) == 1 else None)
    )
    return region_plan


def _legacy_region_result(route: Route, run: PlanResult) -> RegionResult | None:
    """`solve_route`'s region result of a converged `legacy_eo` run: its one `solve_eo` step's,
    or `None` without exactly one (R2.2's certified case)."""
    solved = [step for step in run.steps if step.kind == "solve_eo"]
    if (
        route.solve_path == "legacy_eo"
        and len(solved) == 1
        and isinstance(solved[0].detail, RegionResult)
    ):
        return solved[0].detail
    return None


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
    coupled_start: CoupledStart | None = None,
) -> RouteRun:
    """`revision_coupled` (M02 design note §4.3–§4.4): the outer coupling, then the final inner
    solve certified with the coupling's evidence, or a bundle. Each inner solve is planned and run
    as `revision_eo`'s; `plan` and `solve` are called once, before the first inner solve."""
    from openflowsheet.application.run_session import _reproducibility_class

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
            coupled_start=coupled_start,
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
        "initial_warm": solved.initial_warm,
        "coupling_start": solved.coupling_start,
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
    coupled_start: CoupledStart | None = None,
    on_diagnosis: Callable[[dict[str, Any]], None] | None = None,
    revision_continuation: ContinuationSource | None = None,
) -> RunManifest:
    """Solve, verify and write the bundle (§12.3 as amended by R2.4). Mirrors `run_session`.

    `document` is the stored revision's canonical document; `policy` is the resolved policy and
    `policy_requested` the id as submitted (`"default"` or a registered id). Nothing is written
    when the run ends in a `VerifierError` or `RunUnsupportedError`. `trace`, `stage`,
    `warm_start`, `experiments` and `on_iteration` are `solve_route`'s; `stage` is also called at
    the start of `bundle`. A `revision_coupled` bundle is the final inner solve's, plus
    `external-coupling.json` (ADR 0034 D6).
    `solve-path.json` gains `warm_start` (ADR 0024 D4) iff the solve consulted the source (on
    `revision_coupled`, the coupling's k = 0 inner solve, X02 Part C) or a start was declared
    (ADR 0070); a declared outer start (`coupled_start`) adds its `coupling` sub-record (X02
    design note §5.7).
    `on_diagnosis` receives the outcome-defining step's MSG sidecar (design note §4.6) as a
    document, once the bundle is written, iff it is a failure bundle and the step carries one;
    the sidecar is in no artifact.
    `revision_continuation` (ADR 0072; RRC design note §5.8) is `solve_route`'s; `solve-path.json`
    gains the member `revision_continuation` iff the policy names the revision continuation on
    `revision_eo`, whether or not edge 3 fired, and without a source it records
    `absent(not_supplied)`.

    ADR 0062 D8, D12 (ADR 0019 Amendment 9): a `schema_version` 2 `document` is solved and
    written as its lowering (`lowered_document`), so every artifact, `revision.json` included, is
    the v1 run's of the lowered document; the v2 revision is referenced by the run's record
    (`RunResult.revision_id`, `revision_content_sha256`), not by the bundle.
    """
    document = lowered_document(document)
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
        coupled_start=coupled_start,
        revision_continuation=revision_continuation,
    )
    (stage if stage is not None else no_stage)("bundle")
    return write_revision_bundle(
        result,
        document,
        directory,
        run_id=run_id,
        policy=policy,
        check_policy=check_policy,
        policy_requested=policy_requested,
        started=started,
        clock=clock,
        warm_start=warm_start,
        coupled_start=coupled_start,
        on_diagnosis=on_diagnosis,
        revision_continuation=revision_continuation,
    )


def write_revision_bundle(
    result: RouteRun,
    document: Mapping[str, Any],
    directory: Path,
    *,
    run_id: str,
    policy: SolvePolicy,
    check_policy: CheckPolicy,
    policy_requested: str,
    started: str,
    clock: float,
    warm_start: WarmStartCandidate | None = None,
    coupled_start: CoupledStart | None = None,
    on_diagnosis: Callable[[dict[str, Any]], None] | None = None,
    revision_continuation: ContinuationSource | None = None,
) -> RunManifest:
    """`run_revision_session`'s bundle of a route's solve `result`, as it writes it: `started`
    is the run's start stamp and `clock` its `time.monotonic()` at the start; `warm_start`,
    `coupled_start`, `on_diagnosis` and `revision_continuation` are `run_revision_session`'s, as
    the solve was given them.
    OPT's revision NLP host solves with `solve_route` and writes the same bundle through this,
    without them (OPT design §4.8)."""
    from openflowsheet.application.run_session import _numerical_policy_id, _reproducibility_class

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
    _record_warm_start(solve_path, result, warm_start, coupled_start)
    if route.solve_path == "revision_eo" and continues_revisions(policy):
        _record_revision_continuation(solve_path, result, revision_continuation)
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in trace.events],
        "structural-report.json": result.report.as_document(),
        "revision.json": dict(document),
        "solve-policy.json": policy.as_document(),
        "check-policy.json": check_policy_document(check_policy),
        "solve-path.json": solve_path,
    }
    _add_outcome_artifacts(artifacts, result)

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
    complete: RunManifest = write_bundle(Path(directory), manifest, artifacts)
    diagnosis = _diagnosis(result)
    if on_diagnosis is not None and diagnosis is not None:
        on_diagnosis(diagnosis)
    return complete


def _add_outcome_artifacts(artifacts: dict[str, Any], result: RouteRun) -> None:
    """`write_revision_bundle`'s artifacts of `result`'s plan and outcome, added to `artifacts`
    after the documents every bundle carries."""
    route = result.route
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


def _record_revision_continuation(
    solve_path: dict[str, Any],
    result: RouteRun,
    revision_continuation: ContinuationSource | None,
) -> None:
    """`write_revision_bundle`'s `revision_continuation` member of `solve-path.json` for `result`
    on `revision_eo`, set in `solve_path`; an unsupplied source is recorded `absent`."""
    source = (
        revision_continuation
        if revision_continuation is not None
        else ContinuationSource(RevisionContinuationRefusal("absent", "not_supplied"))
    )
    recorded = result.run.revision_continuation if result.run is not None else None
    solve_path["revision_continuation"] = source.member(recorded)


def _record_warm_start(
    solve_path: dict[str, Any],
    result: RouteRun,
    warm_start: WarmStartCandidate | None,
    coupled_start: CoupledStart | None,
) -> None:
    """`write_revision_bundle`'s `warm_start` member of `solve-path.json` for `result`, set in
    `solve_path` when the run records a start."""
    route = result.route
    warm = _inner_start_record(result, warm_start, coupled_start)
    coupling_member: Mapping[str, Any] | None = None
    if coupled_start is not None:
        coupling_member = _outer_start_record(result, coupled_start)
        if warm is None:
            # §5.7: a start declared without an x₀ source (an iterate only, under a policy whose
            # chain is empty) records the inner members `absent`, `not_declared`.
            warm = WarmStartRecord(
                "absent", "not_declared" if warm_start is None else None, selection=EXPLICIT
            )
    if warm is not None:
        solve_path["warm_start"] = warm.as_document()
        if coupling_member is not None:
            solve_path["warm_start"]["coupling"] = dict(coupling_member)
        external = coupled_start.external if coupled_start is not None else None
        if external is not None and route.solve_path == "revision_coupled":
            # ADR 0070 D9 (§5.7): the k = 0 child starts of a job source.
            solve_path["warm_start"]["external"] = external


def _inner_start_record(
    result: RouteRun,
    warm_start: WarmStartCandidate | None,
    coupled_start: CoupledStart | None,
) -> WarmStartRecord | None:
    """`_record_warm_start`'s record of the inner solve's start, before an outer start's
    default."""
    route = result.route
    # X02 Part C: on `revision_coupled` the candidate is read by the k = 0 inner solve only, so
    # the record is that solve's, whatever the coupling's number of outer iterations.
    if route.solve_path == "revision_coupled":
        warm = result.initial_warm
    else:
        warm = result.run.warm_start if result.run is not None else None
    explicit = warm_start is not None and warm_start.selection == EXPLICIT
    if warm is None and route.solve_path == "legacy_eo" and (explicit or coupled_start is not None):
        # ADR 0070 (X02 design note §5.2): the legacy route reads no start; a declared one is
        # recorded rejected, and the solve ran as without it.
        warm = WarmStartRecord("rejected", "route", warm_start, selection=EXPLICIT)
    return warm


def _outer_start_record(result: RouteRun, coupled_start: CoupledStart) -> Mapping[str, Any] | None:
    """`_record_warm_start`'s record of a declared outer start."""
    route = result.route
    # ADR 0070 D3 (§5.2, §5.7): the outer start's record — the coupling's own on
    # `revision_coupled`; on the routes without an outer iteration, rejected.
    if route.solve_path == "revision_coupled":
        return result.coupling_start
    return unused_coupling_start(
        coupled_start,
        "coupling_compatibility" if route.solve_path == "revision_eo" else "route",
    )


def _diagnosis(result: RouteRun) -> dict[str, Any] | None:
    """MSG §4.6: the sidecar of the step that defined a failure bundle's outcome, as a document;
    `None` without a failure bundle, or when that step carries none."""
    if result.failure is None or result.run is None or not result.run.steps:
        return None
    last = result.run.steps[-1]
    if last.diagnostic is None or last.outcome != result.failure.outcome:
        return None
    return last.diagnostic.as_document()
