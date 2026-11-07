"""Optimisation of a stored revision: the start phase, the solve, the report and the record.

OPT design §4.5 (start phase), §4.6, §4.8, §4.12 (WO-4); ADR 0071. `optimize_revision` is the
library entry the job body calls (as `solve` calls `run_revision_session`):

1. **Static readiness** (`request.static_readiness`): every failing reason, or the formulation
   through the decision map. A static failure is `UNSUPPORTED` with every reason (M03 §8.7).
2. **Start phase**, per start in order: certify cold on the production route (the start's bundle
   written), then Q3 (M03's `_start`). A start that fails is **not run**: it is classified
   `SOLVER_FAILED` by the pure `classify_starts`, its detail `START_NOT_CERTIFIED(<k>, <code>)`.
   The formulation is ready iff one start passes; if none does, `UNSUPPORTED` with
   `SIMULATION_NOT_READY` and every start's reason. With an assessment (E01) its binding is
   planned at the first start that passes (D-18, D-32): its program-wide checks
   (`ASSESSMENT_OUTPUT_UNKNOWN`/`_UNAVAILABLE`, `ASSESSMENT_PARAMETER_*`) refuse the request,
   its per-start checks (`ASSESSMENT_REGIME_INADMISSIBLE`, `ASSESSMENT_OBJECTIVE_UNSCALED`) the
   start.
3. **Solve and verify** each passing start with M03's gray box (`greybox.solve_start`, imported
   only now, so the default install never loads Pyomo or cyipopt): Ipopt over the held system,
   then V1–V6 on the cold re-solve at the returned decisions (V1's bundle written).
4. **Report**: M03's `OptimizationReport` with the additive `revision` member and the start and
   candidate members of §4.13; the candidate carries a change-set (`change-set.schema.json`)
   that writes its decisions into the base revision — committing it is the user's act.
5. **Record** (§4.8, with a `directory`): manifest, request, revision, report and per start the
   start bundle, `optimizer.json`, the candidate document, V1's bundle and `verification.json`.

Identity: `optimization_sha256` over the request, the revision, the route and both policies;
run ids `opt-<optimization_sha256[:16]>-s<k>` (start) and `-r<k>` (V1 re-solve).
"""

from __future__ import annotations

import dataclasses
import importlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openflowsheet.application.policies import DEFAULT_POLICY_ID
from openflowsheet.assessment.program import AssessmentProgram, Refusal
from openflowsheet.assessment.spec import load_assessment
from openflowsheet.assessment.views import view_of
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.compile.casadi_backend import TwinEvaluationError
from openflowsheet.models.revision_flowsheet import si_unit
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.studies.nlp.boundary import PHASE_BOUNDARY_FORM
from openflowsheet.studies.nlp.closure import (
    ADAPTER_MODULE,
    OptimizationReport,
    Readiness,
    ReadinessReason,
    SolverAvailability,
    SolverProbe,
    StartEvidence,
    StartReadiness,
    _assessment_objective_scale,
    _assessment_outputs,
    _assessment_regime,
    _assessment_theta,
    _start,
    assessment_record,
    audited_solver,
    classify_starts,
    formulation_record,
    report_limits,
    solver_record,
    start_closure,
)
from openflowsheet.studies.nlp.formulation import (
    HESSIAN_POLICY,
    AssessmentBinding,
    AssessmentClosure,
    NlpFormulation,
)
from openflowsheet.studies.nlp.host import CertifiedPoint
from openflowsheet.studies.nlp.request import (
    OptimizationRequest,
    StaticReadiness,
    request_formulation,
    request_starts,
    static_readiness,
)
from openflowsheet.studies.nlp.revision_host import ROUTE, DecisionMap, RevisionNlpHost
from openflowsheet.studies.nlp.verification import CandidateVerification
from openflowsheet.verify.certificate import CheckPolicy

OPTIMIZATION_FORMAT: Final = "openflowsheet-optimization-v1"
#: §4.8's record members, by path relative to the record directory.
MANIFEST: Final = "optimization-manifest.json"
REQUEST: Final = "optimization-request.json"
REVISION: Final = "revision-document.json"
REPORT: Final = "optimization-report.json"
#: §4.5: a start that fails the start phase; its arguments are the start and the code.
START_NOT_CERTIFIED: Final = "START_NOT_CERTIFIED"
#: §4.7: a held regime with no phase row and no bound that holds it (a start-phase refusal).
REGIME_MARGIN_UNDEFINED: Final = "REGIME_MARGIN_UNDEFINED"
#: §4.6 (E01 N5): the candidate's words when a phase or regime row is active.
PHASE_REGIME_NOTE: Final = (
    "KKT point of the held-regime problem; the physical derivative across the boundary is one-sided"
)

#: §9 A-1: added to `regime_note` when the candidate's V1 passed on the phase-boundary form.
BOUNDARY_NOTE: Final = (
    "the simulation certificate of this design is UNVERIFIED (rank limitation at the phase "
    "boundary of {units}); its regularity is judged with those splits held"
)

Progress = Callable[[str, Mapping[str, Any]], None]


def optimization_sha256(
    request_sha256: str,
    revision_sha256: str,
    route: str,
    solve_policy_sha256: str,
    check_policy_sha256: str,
) -> str:
    """§4.8's identity of an optimisation: canonical SHA-256 of its five inputs."""
    return document_sha256(
        {
            "format": OPTIMIZATION_FORMAT,
            "request_sha256": request_sha256,
            "revision_sha256": revision_sha256,
            "route": route,
            "solve_policy_sha256": solve_policy_sha256,
            "check_policy_sha256": check_policy_sha256,
        }
    )


@dataclass(frozen=True)
class StartPoints:
    """One start's certified points in memory (§4.15 X24): the start's and V1's re-solve, each
    `None` where none was taken. Never serialised."""

    start: CertifiedPoint | None
    candidate: CertifiedPoint | None


@dataclass(frozen=True)
class OptimizationOutcome:
    """`optimize_revision`'s result: the report, the record directory (`None` without one) and
    every start's points."""

    report: OptimizationReport
    record_dir: Path | None
    points: tuple[StartPoints, ...]


class _Sink:
    """The host's bundle sink: the next certify's directory and run id, set before each one."""

    def __init__(self) -> None:
        self.target: tuple[Path, str] | None = None

    def __call__(self, document: Mapping[str, Any]) -> tuple[Path, str]:
        if self.target is None:
            raise RuntimeError("a certify without a bundle target")
        target, self.target = self.target, None
        target[0].parent.mkdir(parents=True, exist_ok=True)
        return target


def optimize_revision(
    document: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    directory: Path | None,
    solve_policy: SolvePolicy,
    check_policy: CheckPolicy,
    policy_requested: str = DEFAULT_POLICY_ID,
    check: Callable[[], None] | None = None,
    progress: Progress | None = None,
    solver_probe: SolverProbe = audited_solver,
    surrogates: Any = None,
) -> OptimizationOutcome:
    """Optimise `document` (a stored revision) by `request` (§4.12). See the module docstring.

    Raises `ValueError` for a request with problems (`request_problems`): an invalid input, not
    a report. `check` is called between stages and may raise to cancel; `progress(stage, info)`
    is told each stage."""
    check = check or (lambda: None)
    progress = progress or (lambda stage, info: None)
    parsed = OptimizationRequest.of(request)
    static = static_readiness(request, document, surrogates=surrogates, solver_probe=solver_probe)
    revision_sha256 = document_sha256(document)
    identity = {
        "request_sha256": parsed.sha256,
        "revision_sha256": revision_sha256,
        "route": ROUTE,
        "solve_policy_sha256": policy_sha256(solve_policy),
        "check_policy_sha256": check_policy.sha256,
    }
    sha = optimization_sha256(**identity)
    revision = {
        "revision_id": document.get("revision_id"),
        **identity,
        "optimization_sha256": sha,
        "objective_sense": parsed.sense,
        "decision_parameters": (
            dict(static.decisions.parameters) if static.decisions is not None else None
        ),
    }
    record = _Record(directory, sha, identity, request, document) if directory else None
    progress("resolve", {"ready": static.ready, "codes": list(static.codes)})
    if not static.ready or static.formulation is None or static.decisions is None:
        reasons = static.reasons or _not_run(static)
        report = _unsupported(parsed, static, revision, reasons, document=document)
        return _finish(record, report, ())
    formulation = static.formulation
    sink = _Sink() if record is not None else None
    host = RevisionNlpHost(
        document,
        static.decisions,
        solve_policy=solve_policy,
        check_policy=check_policy,
        policy_requested=policy_requested,
        sink=sink,
        surrogates=surrogates,
    )
    spec = host.base_spec()
    starts: list[StartReadiness] = []
    failures: dict[int, str] = {}
    for index, start in enumerate(formulation.starts):
        check()
        progress("start", {"start": index})
        if sink is not None:
            sink.target = (record.path(f"starts/{index}/start"), f"opt-{sha[:16]}-s{index}")  # type: ignore[union-attr]
        readiness, found = _start(formulation, host, index, start, True, spec)
        starts.append(readiness)
        if found or readiness.state is None:
            code = readiness.outcome if readiness.state is None else found[0].code
            failures[index] = f"{START_NOT_CERTIFIED}({index}, {code})"
            detail = "; ".join(reason.detail for reason in found) or readiness.message
            failures[index] += f": {detail}"
        elif readiness.point is not None:
            # §4.7: a held regime no phase row (and no bound) can hold refuses the start.
            undefined = host.phase_rows(readiness.point).undefined
            if undefined:
                failures[index] = f"{START_NOT_CERTIFIED}({index}, {REGIME_MARGIN_UNDEFINED}): " + (
                    "; ".join(f"{REGIME_MARGIN_UNDEFINED}({unit})" for unit in undefined)
                )
    bound = _Bound(formulation, (), None)
    if parsed.assessment is not None:
        bound = _bind_assessment(parsed.assessment, formulation, host, starts, failures)
        formulation = bound.formulation
    if bound.reasons:
        refused = Readiness("unsupported", bound.reasons, static.solver, tuple(starts))
        report = _unsupported(
            parsed,
            static,
            revision,
            bound.reasons,
            formulation,
            refused,
            host.model_record(),
            assessment=assessment_record(formulation, bound.closure(host, starts, static.solver)),
        )
        points = tuple(StartPoints(start.point, None) for start in starts)
        return _finish(record, report, points)
    if len(failures) == len(starts):
        reasons = tuple(
            ReadinessReason("SIMULATION_NOT_READY", failures[index], f"start {index}")
            for index in range(len(starts))
        )
        refused = Readiness("unsupported", reasons, static.solver, tuple(starts))
        report = _unsupported(
            parsed, static, revision, reasons, formulation, refused, host.model_record()
        )
        points = tuple(StartPoints(start.point, None) for start in starts)
        return _finish(record, report, points)

    check()
    adapter = importlib.import_module(ADAPTER_MODULE)
    solver = dataclasses.replace(
        static.solver, versions={**static.solver.versions, "ipopt": adapter.ipopt_version()}
    )
    options = {"max_iter": parsed.max_iter, "max_wall_time": parsed.max_wall_time_s}
    runs: list[Any] = []
    evidence: list[StartEvidence] = []
    for index, readiness in enumerate(starts):
        if index in failures:
            runs.append(None)
            evidence.append(StartEvidence(None, {}, failures[index]))
            continue
        check()
        progress("optimize", {"start": index})

        def place(index: int = index) -> None:
            check()
            if sink is not None:
                sink.target = (record.path(f"starts/{index}/resolve"), f"opt-{sha[:16]}-r{index}")  # type: ignore[union-attr]

        run = adapter.solve_start(
            host, formulation, readiness, index, options=options, before_verification=place
        )
        runs.append(run)
        evidence.append(run.evidence())
    verdict = classify_starts(evidence)
    records = []
    for index, (readiness, run) in enumerate(zip(starts, runs, strict=True)):
        records.append(_start_record(formulation, readiness, run, index, host))
    verified = [runs[index] for index in verdict.verified_starts]
    candidate = adapter._candidate(verified)
    assessment = assessment_record(formulation, bound.closure(host, starts, solver), candidate)
    candidate_document = None
    if candidate is not None:
        best = next(run for run in verified if run.verification is candidate)
        candidate_document = {
            **candidate.as_document(),
            **_candidate_members(host, document, formulation, best, sha),
            **_phase_members(host, starts[best.index], candidate, assessment),
        }
    report = OptimizationReport(
        formulation=formulation_record(formulation, _declared(starts), assessment),
        model=host.model_record(),
        solver=solver_record(solver, adapter.solver_environment()),
        hessian_policy=dict(HESSIAN_POLICY),
        starts=verdict.start_records(records),
        candidate=candidate_document,
        distinct_local_solutions=adapter._distinct(formulation, verified),
        status=verdict.status,
        reasons=verdict.reasons,
        claims={
            "global_optimality": False,
            "local_stationarity": verdict.local_stationarity,
            "second_order": (
                candidate.kkt.second_order
                if candidate is not None and candidate.kkt is not None
                else "not_assessed"
            ),
            # §9 A-1: numerical verification is reported apart from optimality evidence (§2.5).
            **(
                {"numerical_verification": candidate.basis}
                if candidate is not None and candidate.basis is not None
                else {}
            ),
        },
        limits={
            **report_limits(),
            "max_iter": parsed.max_iter,
            "max_wall_time": parsed.max_wall_time_s,
        },
        revision=revision,
    )
    if record is not None:
        for index, run in enumerate(runs):
            if run is not None:
                record.start_members(index, host, formulation, run)
    points = tuple(
        StartPoints(
            readiness.point,
            run.verification.point if run is not None and run.verification is not None else None,
        )
        for readiness, run in zip(starts, runs, strict=True)
    )
    return _finish(record, report, points)


@dataclass(frozen=True)
class _Bound:
    """The formulation with its assessment binding (or as it was), the program-wide reasons that
    refuse it, and the start the binding was planned at (`None` where none was)."""

    formulation: NlpFormulation
    reasons: tuple[ReadinessReason, ...]
    at: int | None

    def closure(
        self, host: RevisionNlpHost, starts: Sequence[StartReadiness], solver: SolverAvailability
    ) -> AssessmentClosure | None:
        """The binding's gray-box closure at the start it was planned at (E01 §4.10.2)."""
        if self.at is None or self.formulation.assessment is None:
            return None
        planned = Readiness("unsupported", (), solver, (starts[self.at],))
        return start_closure(self.formulation, host, planned)


def _bind_assessment(
    document: Mapping[str, Any],
    formulation: NlpFormulation,
    host: RevisionNlpHost,
    starts: Sequence[StartReadiness],
    failures: dict[int, str],
) -> _Bound:
    """E01's binding at the first start that passes the start phase (§4.5, D-18, D-32).

    The program is planned at that start's certified state on its bound problem
    (`AssessmentProgram.build`, the regime chosen by the rule there), and each named output's
    scale is taken there (`AssessmentBinding.at`). A start where the program cannot be planned
    (a `Refusal`) or a named output cannot be evaluated does not pass: its failure is
    `START_NOT_CERTIFIED(<k>, <code>)` and the next passing start is tried. The program-wide
    checks (`ASSESSMENT_OUTPUT_UNKNOWN`, `_UNAVAILABLE`, `ASSESSMENT_PARAMETER_STRUCTURAL`,
    `_DECISION`) are returned as reasons that refuse the request; the per-start ones
    (`ASSESSMENT_REGIME_INADMISSIBLE`, `ASSESSMENT_OBJECTIVE_UNSCALED`) fail each start they
    find, the planning start included. A request naming no `assessment:<id>` is not bound."""
    named = tuple(dict.fromkeys(formulation.assessment_outputs))
    if not named:
        return _Bound(formulation, (), None)
    spec = load_assessment(document)
    for index, start in enumerate(starts):
        if index in failures:
            continue
        point, state = start.point, start.state
        assert point is not None and point.spec is not None and state is not None
        program = AssessmentProgram.build(
            view_of(host.bound_flowsheet(point)), point.spec, spec, state
        )
        if isinstance(program, Refusal):
            failures[index] = (
                f"{START_NOT_CERTIFIED}({index}, {program.code}): the assessment program "
                f"cannot be planned at this start: {program.target} {program.detail}".rstrip()
            )
            continue
        published = set(program.output_ids) - set(program.admissibility_ids)
        bindable = [n for n in named if n in published and n not in program.unavailable]
        if not bindable:
            return _Bound(formulation, _unbound_outputs(named, program), None)
        try:
            binding = AssessmentBinding.at(program, bindable, state)
        except TwinEvaluationError as error:
            failures[index] = (
                f"{START_NOT_CERTIFIED}({index}, ASSESSMENT_OUTPUT_UNAVAILABLE): the bound "
                f"outputs cannot be evaluated at this start: {error}"
            )
            continue
        bound = dataclasses.replace(formulation, assessment=binding)
        reasons = [
            theta
            for decision_id in bound.decision_ids
            if (theta := _assessment_theta(bound, decision_id)) is not None
        ]
        reasons.extend(_assessment_outputs(bound))
        for later in range(index, len(starts)):
            if later in failures:
                continue
            found = [
                *_assessment_regime(bound, later, starts[later]),
                *_assessment_objective_scale(bound, later, starts[later]),
            ]
            if found:
                failures[later] = f"{START_NOT_CERTIFIED}({later}, {found[0].code}): " + "; ".join(
                    reason.detail for reason in found
                )
        return _Bound(bound, tuple(reasons), index)
    return _Bound(formulation, (), None)


def _unbound_outputs(
    named: Sequence[str], program: AssessmentProgram
) -> tuple[ReadinessReason, ...]:
    """Every named output when none can be bound: null in the program (`_UNAVAILABLE`, with
    why) or not one of its published outputs (`_UNKNOWN`), as `closure._assessment_outputs`."""
    reasons = []
    for name in named:
        if name in program.unavailable:
            reasons.append(
                ReadinessReason(
                    "ASSESSMENT_OUTPUT_UNAVAILABLE",
                    f"assessment:{name} is null: {program.unavailable[name]}",
                    name,
                )
            )
        else:
            reasons.append(
                ReadinessReason(
                    "ASSESSMENT_OUTPUT_UNKNOWN",
                    f"assessment:{name} is not a bound output of the program",
                    name,
                )
            )
    return tuple(reasons)


def _declared(starts: Sequence[StartReadiness]) -> Mapping[str, str] | None:
    return next((start.regimes for start in starts if start.regimes is not None), None)


def _not_run(static: StaticReadiness) -> tuple[ReadinessReason, ...]:
    """A static phase with checks not run and no failing reason cannot be `READY`; its report
    names what was not judged (unreachable for a well-formed request on a bound revision)."""
    return tuple(
        ReadinessReason("SIMULATION_NOT_READY", f"{code} not judged: {why}")
        for code, why in static.not_run.items()
    )


def _unsupported(
    parsed: OptimizationRequest,
    static: StaticReadiness,
    revision: Mapping[str, Any],
    reasons: Sequence[ReadinessReason],
    formulation: NlpFormulation | None = None,
    readiness: Readiness | None = None,
    model: Mapping[str, Any] | None = None,
    document: Mapping[str, Any] | None = None,
    assessment: Mapping[str, Any] | None = None,
) -> OptimizationReport:
    """`UNSUPPORTED` with every reason: refused before any Ipopt call."""
    record = (
        formulation_record(
            formulation, _declared(readiness.starts) if readiness else None, assessment
        )
        if formulation is not None
        else _request_formulation_record(parsed, static, document or {})
    )
    return OptimizationReport(
        formulation=record,
        model=dict(model)
        if model is not None
        else {"model_version": None, "constants_sha256": None},
        solver=solver_record(static.solver),
        hessian_policy=dict(HESSIAN_POLICY),
        starts=(),
        candidate=None,
        distinct_local_solutions=0,
        status="UNSUPPORTED",
        reasons=tuple(reasons),
        claims={
            "global_optimality": False,
            "local_stationarity": False,
            "second_order": "not_assessed",
        },
        limits={
            **report_limits(),
            "max_iter": parsed.max_iter,
            "max_wall_time": parsed.max_wall_time_s,
        },
        revision=revision,
    )


def _request_formulation_record(
    parsed: OptimizationRequest, static: StaticReadiness, document: Mapping[str, Any]
) -> dict[str, Any]:
    """D-24: the report's formulation of a request refused statically — the decision map where
    it was found, else the specification ids themselves; start 0 the specifications' values as
    the revision writes them (when every decision's specification has one), then the explicit
    and Halton starts. With no start at all the record carries one empty start (the schema needs
    one; nothing was run)."""
    mapping = static.decisions or DecisionMap({name: name for name in parsed.specification_ids})
    written = {entry.get("id"): entry.get("value") for entry in document.get("specifications", ())}
    values = [written.get(name) for name in parsed.specification_ids]
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    revision_values = tuple(numbers) if len(numbers) == len(values) else None
    known = parsed
    if parsed.include_revision and revision_values is None:
        known = dataclasses.replace(parsed, include_revision=False)
    try:
        starts = request_starts(known, revision_values)
    except ValueError:
        starts = ()
    placeholder = tuple(0.0 for _ in parsed.decisions)
    record = formulation_record(
        request_formulation(parsed, mapping, starts or (placeholder,)), None
    )
    if not starts:
        record["starts"] = [[]]
    return record


def _start_record(
    formulation: NlpFormulation,
    readiness: StartReadiness,
    run: Any,
    index: int,
    host: RevisionNlpHost,
) -> dict[str, Any]:
    """The report's start record (§8.6) with §4.13's additive members, the start's zero
    subsystem (§9 A-2) and its unguarded splits (§9 A-3) where non-empty."""
    point = readiness.point
    held = point.signature if point is not None else None
    if run is None:
        record: dict[str, Any] = {
            "start": formulation.decision_values(readiness.start),
            "ipopt_status": None,
            "ipopt_message": None,
            "iterations": None,
            "evaluations": {
                "residual_calls": 0,
                "jacobian_calls": 0,
                "property_calls": 0,
                "evaluation_errors": 0,
            },
            "wall_time_s": None,
            "final_decisions": None,
            "ipopt_final": None,
            "checks": [],
        }
    else:
        record = run.record(formulation)
    record["start_record"] = f"starts/{index}/start" if point and point.bundle_ref else None
    candidate = run.verification.point if run is not None and run.verification else None
    record["resolve_record"] = (
        f"starts/{index}/resolve" if candidate is not None and candidate.bundle_ref else None
    )
    record["held_signature"] = _signature(held)
    if point is not None and point.verified:
        zero = host.held_system(point).zero
        if zero is not None:
            record["zero_subsystem"] = zero.as_document()
        unguarded = host.phase_rows(point).unguarded
        if unguarded:
            record["regimes_unguarded"] = list(unguarded)
    return record


def _signature(signature: Any) -> list[list[str]] | None:
    if signature is None:
        return None
    return [[str(part) for part in item] for item in signature]


def _candidate_members(
    host: RevisionNlpHost,
    document: Mapping[str, Any],
    formulation: NlpFormulation,
    run: Any,
    sha: str,
) -> dict[str, Any]:
    """§4.8 and §4.13: the candidate's change-set (§4.2.2's edits as `commit_change` edits on
    the base revision), its document's SHA-256 and V1's record."""
    values = {
        host.decisions.specifications[parameter]: value
        for parameter, value in formulation.decision_values(run.final_decisions).items()
    }
    edits: list[dict[str, Any]] = []
    for position, entry in enumerate(document.get("specifications", ())):
        name = entry.get("id")
        if name not in values:
            continue
        path: list[str | int] = ["specifications", position]
        edits.append({"operation": "set", "path": [*path, "value"], "value": float(values[name])})
        unit = si_unit(entry["kind"])
        if entry.get("unit") != unit:
            edits.append({"operation": "set", "path": [*path, "unit"], "value": unit})
    point = run.verification.point
    return {
        "certificate_basis": run.verification.basis,
        "change_set": {
            "edits": edits,
            "expected_revision": document.get("revision_id"),
            "idempotency_key": f"opt-{sha[:32]}",
        },
        "resolve_record": f"starts/{run.index}/resolve" if point.bundle_ref else None,
    }


def _phase_members(
    host: RevisionNlpHost,
    readiness: StartReadiness,
    candidate: CandidateVerification,
    assessment: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """§4.7/§4.6: `phase_bounds_active` — the candidate's start's phase rows in V3's active set,
    each with its unit (a split's, or a declared port's stream), its scaled slack and V5's
    multiplier — and `regime_note` when it or the assessment's `regime_bounds_active` is
    non-empty; `regimes_unguarded` (§9 A-3) where the start has unguarded splits."""
    assert readiness.point is not None
    rows = host.phase_rows(readiness.point)
    multipliers = candidate.kkt.multipliers if candidate.kkt is not None else {}
    active = [
        {
            "unit": rows.row(item.target).unit,
            "row": item.target,
            "slack_scaled": item.slack,
            "multiplier": multipliers.get(item.name),
        }
        for item in candidate.active_set
        if item.kind == "constraint" and item.target in set(rows.ids)
    ]
    members: dict[str, Any] = {"phase_bounds_active": active}
    if active or (assessment is not None and assessment.get("regime_bounds_active")):
        members["regime_note"] = PHASE_REGIME_NOTE
    v1 = next(check for check in candidate.checks if check.check == "V1")
    if candidate.basis == PHASE_BOUNDARY_FORM:
        units = ", ".join(v1.detail["boundary_form"]["splits"])
        members["regime_note"] = f"{PHASE_REGIME_NOTE}; {BOUNDARY_NOTE.format(units=units)}"
    if rows.unguarded:
        members["regimes_unguarded"] = list(rows.unguarded)
    return members


class _Record:
    """§4.8's record directory: members written as canonical JSON, their SHA-256s in the
    manifest, which is written last."""

    def __init__(
        self,
        directory: Path,
        sha: str,
        identity: Mapping[str, str],
        request: Mapping[str, Any],
        document: Mapping[str, Any],
    ) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.sha = sha
        self.identity = dict(identity)
        self.members: dict[str, str] = {}
        self.write(REQUEST, request)
        self.write(REVISION, document)

    def path(self, relative: str) -> Path:
        return self.directory / relative

    def write(self, relative: str, document: Any) -> None:
        payload = canonical_json(document)
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        self.members[relative] = document_sha256(document)

    def start_members(
        self, index: int, host: RevisionNlpHost, formulation: NlpFormulation, run: Any
    ) -> None:
        """`optimizer.json`, the candidate document and `verification.json` of one start."""
        primal = None
        if run.final_primal is not None:
            names = run.primal_ids
            primal = {
                name: _finite(float(value))
                for name, value in zip(names, run.final_primal, strict=True)
            }
        self.write(
            f"starts/{index}/optimizer.json",
            {
                "options": dict(run.options),
                "ipopt_status": run.ipopt_status,
                "ipopt_message": run.ipopt_message,
                "iterations": run.iterations,
                "final_primal": primal,
                "objective": _finite(run.iteration_rows[-1][1]) if run.iteration_rows else None,
                "ipopt_final": run.ipopt_final,
                "evaluations": dict(run.evaluations),
                "iteration_rows": [
                    {
                        "iter": row[0],
                        "obj": _finite(row[1]),
                        "inf_pr": _finite(row[2]),
                        "inf_du": _finite(row[3]),
                        "mu": _finite(row[4]),
                        "alpha_pr": _finite(row[5]),
                    }
                    for row in run.iteration_rows
                ],
                "detail": run.detail,
            },
        )
        verification = run.verification
        if verification is not None and verification.point is not None:
            self.write(
                f"starts/{index}/candidate-revision.json", verification.point.handle.document
            )
        if verification is not None:
            self.write(f"starts/{index}/verification.json", verification.as_document())

    def finish(self, report: OptimizationReport) -> None:
        self.write(REPORT, report.as_document())
        for bundle in sorted(self.directory.glob("starts/*/*/")):
            for file in sorted(path for path in bundle.rglob("*") if path.is_file()):
                relative = file.relative_to(self.directory).as_posix()
                self.members[relative] = _file_sha256(file)
        manifest = {
            "format": OPTIMIZATION_FORMAT,
            "optimization_sha256": self.sha,
            **self.identity,
            "members": dict(sorted(self.members.items())),
            "environment": {"solver": report.solver.get("environment")},
        }
        self.path(MANIFEST).write_bytes(canonical_json(manifest))


def _finite(value: float) -> float | str:
    """A float, or its name where it is not finite (canonical JSON has no NaN or infinity)."""
    return value if math.isfinite(value) else repr(value)


def _file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finish(
    record: _Record | None, report: OptimizationReport, points: tuple[StartPoints, ...]
) -> OptimizationOutcome:
    if record is not None:
        record.finish(report)
    return OptimizationOutcome(report, record.directory if record else None, points)
