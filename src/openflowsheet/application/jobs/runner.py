"""The operation bodies of a job: `solve`, `reproduce`, `experiment` and `surrogate_study` (T07
design note §5.4, §6.2–§6.4, §8; M02 design note §3.5; M04 spec §10.3).

`execute(context, job, check=…, cancel=…)` runs one job's operation and returns its
`WorkerResult` — the termination the owner turns into the one `ended` event (§6.2: a body never
writes `ended`). Along the way it writes the job's `progress` and `output` events, fenced on its
owner (§9.3), and the files its outputs name. It is the same code under every executor: inline
here (W4a) and in a spawned worker (W4c).

**Stages (§6.4).** Progress is emitted at the *start* of each stage with `completed` = the stage's
index in the operation's fixed list, so the counts are deterministic and a skipped stage emits
nothing. `solve`: `resolve` (the request against the stored revision: the route, the effective
solve and check policies), `bind` (the route's binder, afresh for this run), `plan`, `solve`,
`verify`, `bundle` — the last four called back from `revision_run.run_revision_session`, the same
function a direct caller uses, so a job's bundle *is* that function's bundle (gate G6).
`reproduce`: `integrity`, `rerun` (only when `rerun`), `compare`. `experiment`: `resolve` (the
variant and the inlet), `evaluate` (`adapters.experiments`' runner: key, lock, cache, attempts,
records), `record` (the outputs). `surrogate_study`: `resolve` (the variant), `study`
(`studies.surrogate.study.run_study`: the plan, the budget, the experiments one by one, the
evidence), `record` (the manifest and the evidence).

**Experiments (ADR 0033 D9, M02 design note §3.5).** An `experiment` job evaluates one request and
ends `completed` whatever the experiment's outcome — a refusal or a transient failure is a result,
recorded; `failed` is kept for a defect. Its outputs are the records it wrote, as the store's sink
registered them — the request, the attempts, the result, or a cache hit's row whose parent is the
producing result — and, for a deterministic outcome it did not write (a bypassed repeat), the
producing result's row. The body is read here and by the runner only: nothing in it reaches a
solve (R-235). Its property calls are its own and unmetered (R-233).

**Surrogate studies (ADR 0037 D6, M04 spec §10.3).** A `surrogate_study` ends `completed`
whatever its verdict, with its answer (`job_result.surrogate_study`) in `worker_result.study`. Its
outputs are the manifest and then the evidence that names it (none for a budget refusal; spec §18
A1.4); its experiment records are artifacts of the job, not outputs. A cancellation recorded by
another caller is honoured between experiments. A cancelled study keeps its records; a new job
re-reads them through the cache.

**Interruption (§8.1).** `check` raises `JobInterrupted` once cancellation is requested or the
wall-time deadline has passed; it runs at every `Trace.record` (installed by the executor) and at
every stage boundary here. An interrupted solve writes `partial-solve-events.json` — the events its
trace holds, if any — and **nothing else**: no certificate, no failure bundle, no solver outcome,
even when the interruption came at `verify` or `bundle`. A cancellation another caller recorded in
the store reaches the body at its next stage boundary.

**Outputs (§5.4).** A written solve bundle gives exactly three outputs, in order: the certificate
xor the failure bundle, the run manifest, the bundle. Every file of a bundle is registered as the
artifact `<bundle id>/<file>` with its kind, and only those three are outputs. A job's bundle id is
`<job_id>:bundle` (a solve) or `<job_id>:rerun` (a reproduce's rerun, §12.3), as an import's is
`import-<ordinal>:bundle`; a job's other files are `<job_id>:<file>`.

**Typed ends without a bundle (§12.3).** A record with no registered bundle mapping
(`RunUnsupportedError`) ends `failed(operation_error)` with `unsupported(<code>)`; a
`VerifierError` ends `failed(verifier_refused)`; a judged state that is not the certificate's ends
`failed(operation_error)` with `internal_error(solution_state_mismatch)`. None writes a bundle.

**`retryable` (§5.8 as amended by ruling round 4, W4c-Q2).** On an error recorded on a job it
means that a *new* job for the same request may succeed with nothing changed; re-submitting the
same key returns this job whatever the flag says. Every error a body returns here —
`operation_error` with any code, and `verifier_refused` — is `retryable: false`. The executor's
own ends (`jobs.executor`) carry the transient cases.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Self

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ArtifactSink, ExperimentStore
from openflowsheet.application.admission import resolve_policies, stored_surrogate_manifests
from openflowsheet.application.jobs.interrupt import CancelReason, JobInterrupted
from openflowsheet.application.jobs.model import (
    ARTIFACT_FILE_NAMES,
    EndingReason,
    Interruption,
    TerminalStatus,
)
from openflowsheet.application.revision_run import (
    Route,
    RunUnsupportedError,
    SolutionStateMismatchError,
    bind_route,
    reproduce_bundle,
    run_revision_session,
    select_route,
)
from openflowsheet.application.store import JOBS_DIR, ArtifactRow, ArtifactTableSink, ProjectStore
from openflowsheet.application.types import (
    ApiError,
    ApiErrorCode,
    ArtifactRef,
    ExperimentBody,
    Job,
    JobEnding,
    Progress,
    ReproduceBody,
    SolveBody,
    SurrogateStudyBody,
)
from openflowsheet.canonical import canonical_json, directory_hash, file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator.trace import Trace
from openflowsheet.orchestrator.warm_start import WARM_START_SOURCE, WarmStartCandidate
from openflowsheet.run.bundle import ARTIFACT_DIR, MANIFEST_NAME, BundleError, read_artifact
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.studies.surrogate.iterations import predecessors as iteration_predecessors
from openflowsheet.studies.surrogate.plan import REGISTERED_PLANS, PlanRefusedError
from openflowsheet.studies.surrogate.study import run_study
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.verify.checks import VerifierError

__all__ = [
    "EXPERIMENT_STAGES",
    "REPRODUCE_STAGES",
    "SOLVE_STAGES",
    "SURROGATE_STUDY_STAGES",
    "RunContext",
    "WorkerResult",
    "bundle_rows",
    "execute",
]

_LOG = logging.getLogger(__name__)

#: §6.4.
SOLVE_STAGES: Final[tuple[str, ...]] = ("resolve", "bind", "plan", "solve", "verify", "bundle")
REPRODUCE_STAGES: Final[tuple[str, ...]] = ("integrity", "rerun", "compare")
EXPERIMENT_STAGES: Final[tuple[str, ...]] = ("resolve", "evaluate", "record")
SURROGATE_STUDY_STAGES: Final[tuple[str, ...]] = ("resolve", "study", "record")
#: §5.4: the producer kind of each fixed file name.
KIND_OF_FILE: Final[Mapping[str, str]] = {
    name: kind for kind, name in ARTIFACT_FILE_NAMES.items() if name is not None
}
PARTIAL_TRACE: Final[str] = ARTIFACT_FILE_NAMES["partial_solve_trace"] or ""
REPLAY_REPORT: Final[str] = ARTIFACT_FILE_NAMES["replay_report"] or ""
CERTIFICATE: Final[str] = ARTIFACT_FILE_NAMES["solution_certificate"] or ""
FAILURE: Final[str] = ARTIFACT_FILE_NAMES["failure_bundle"] or ""
MANIFEST_FILE: Final[str] = ARTIFACT_FILE_NAMES["surrogate_manifest"] or ""
EVIDENCE_FILE: Final[str] = ARTIFACT_FILE_NAMES["model_evidence"] or ""


@dataclass(frozen=True)
class RunContext:
    """Where a job runs: the project's store, the root its files live under, and its owner."""

    store: ProjectStore
    root: Path
    owner_instance: str

    def job_directory(self, job_id: str) -> Path:
        return self.root / JOBS_DIR / job_id


@dataclass(frozen=True)
class WorkerResult:
    """§6.2's `worker_result`: how the body intends the job to end, and — for a solve — the
    resolution and run facts `RunResult` is read from (`run`, `None` before `resolve` ended)."""

    status: TerminalStatus
    reason: EndingReason
    interruption: Interruption | None
    error: ApiError | None
    run: Mapping[str, Any] | None = None
    #: A `surrogate_study` job's answer (M04 spec §10.3), written only when the study ended; the
    #: member is absent from the document otherwise, so the other operations' are unchanged.
    study: Mapping[str, Any] | None = None

    @property
    def ending(self) -> JobEnding:
        return JobEnding(status=self.status, reason=self.reason, interruption=self.interruption)

    def as_document(self) -> dict[str, Any]:
        document = {
            "status": self.status,
            "reason": self.reason,
            "interruption": self.interruption,
            "error": self.error.as_document() if self.error is not None else None,
            "run": dict(self.run) if self.run is not None else None,
        }
        if self.study is not None:
            document["study"] = dict(self.study)
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        error = document["error"]
        return cls(
            status=document["status"],
            reason=document["reason"],
            interruption=document["interruption"],
            error=ApiError._build(error) if error is not None else None,
            run=document["run"],
            study=document.get("study"),
        )


def warm_start_candidate(
    context: RunContext, job_id: str, revision_id: str
) -> WarmStartCandidate | None:
    """ADR 0024 D2 (T08 build-first spec §B1): the source-2 candidate of `job_id`, a solve of
    `revision_id`, by `store-latest-verified-lineage-v1`, as the store is when the job starts;
    `None` when there is none. A file that does not parse is a candidate with no document, which
    the orchestrator's `integrity` check rejects. Any principal's job counts: `read` on the
    project covers all its jobs (T07 §10.1; `authz.OPERATION_RIGHTS`)."""
    store = context.store
    with store.reading() as connection:
        found = store.latest_verified_solution(
            connection, store.lineage(connection, revision_id), excluding=job_id
        )
    if found is None:
        return None
    source_job_id, source_revision_id, relpath = found
    try:
        document = json.loads((context.root / relpath).read_bytes())
    except (OSError, ValueError):
        document = None
    return WarmStartCandidate(document, source_job_id, source_revision_id)


class _RecordingSink:
    """An `ArtifactSink` that forwards to the project's and keeps a reference to each record it
    made, in order: an experiment job's outputs (R-237)."""

    def __init__(self, inner: ArtifactSink) -> None:
        self.inner = inner
        self.refs: list[ArtifactRef] = []

    def record(
        self,
        *,
        job_id: str | None,
        kind: str,
        name: str,
        relpath: str,
        sha256: str,
        size_bytes: int,
        parent_artifact_id: str | None,
    ) -> str:
        artifact_id = self.inner.record(
            job_id=job_id,
            kind=kind,
            name=name,
            relpath=relpath,
            sha256=sha256,
            size_bytes=size_bytes,
            parent_artifact_id=parent_artifact_id,
        )
        self.refs.append(ArtifactRef(kind, artifact_id, sha256, size_bytes, name))
        return artifact_id


class _FenceLost(Exception):  # noqa: N818 - a signal inside this module, not an error type
    """The job is no longer running under this owner (§9.3): stop writing at once."""


def _error(code: ApiErrorCode, message: str, **detail: Any) -> ApiError:
    return ApiError(code=code, message=message, retryable=False, detail=detail)


def _failed(
    error: ApiError, run: Mapping[str, Any] | None, reason: EndingReason = "operation_error"
) -> WorkerResult:
    return WorkerResult(status="failed", reason=reason, interruption=None, error=error, run=run)


def _interrupted(interrupted: JobInterrupted, run: Mapping[str, Any] | None) -> WorkerResult:
    """§8.1: a cooperative stop is `timed_out` for the deadline, `cancelled` otherwise."""
    status: TerminalStatus = (
        "timed_out" if interrupted.reason == "wall_time_exhausted" else "cancelled"
    )
    return WorkerResult(
        status=status, reason=interrupted.reason, interruption="cooperative", error=None, run=run
    )


def _typed_end(
    error: Exception, run: Mapping[str, Any] | None, route: Route | None = None
) -> WorkerResult:
    """§12.3's typed ends without a bundle, shared by both operations. A solve's end names the
    route it ran on, `detail.solve_path` and `detail.route_reason` (ruling round 6, B1 item 4):
    no bundle carries them on these ends."""
    where: dict[str, Any] = (
        {} if route is None else {"solve_path": route.solve_path, "route_reason": route.reason}
    )
    if isinstance(error, RunUnsupportedError):
        # W3-Q1: a record with no registered mapping is `unsupported(<code>)`, never a bundle.
        return _failed(_error("unsupported", error.code, reason=error.code, **where), run)
    if isinstance(error, VerifierError):
        # The verifier refused to judge; its text may carry revision ids, so it goes to the log
        # only (D9 (4)).
        _LOG.warning("verifier refused: %s", error)
        return _failed(
            _error("unsupported", "verifier_refused", exception=type(error).__name__, **where),
            run,
            "verifier_refused",
        )
    assert isinstance(error, SolutionStateMismatchError)
    # Ruling round 2 F1.1: a producer defect, escalated to the design lane; no bundle.
    return _failed(_error("internal_error", error.code, reason=error.code, **where), run)


def bundle_rows(
    root: Path, directory: Path, bundle_id: str, job_id: str | None, *, producer: bool
) -> tuple[ArtifactRow, list[ArtifactRow]]:
    """The bundle's own row and its members' (`<bundle id>/<file>`), for `artifacts` (§5.4).

    `producer` is this code's own bundle, where a file name outside §5.4's table is a defect
    (`ValueError`); an imported bundle's unknown files are simply not registered.
    """
    members: list[ArtifactRow] = []
    files = [directory / MANIFEST_NAME]
    artifacts = directory / ARTIFACT_DIR
    if artifacts.is_dir():
        files.extend(sorted(path for path in artifacts.iterdir() if path.is_file()))
    for path in files:
        kind = KIND_OF_FILE.get(path.name)
        if kind is None:
            if producer:
                raise ValueError(f"producer defect: {path.name!r} has no artifact kind (§5.4)")
            continue
        members.append(
            ArtifactRow(
                artifact_id=f"{bundle_id}/{path.name}",
                job_id=job_id,
                kind=kind,
                name=path.name,
                sha256=file_sha256(path),
                size_bytes=path.stat().st_size,
                relpath=path.relative_to(root).as_posix(),
                parent_artifact_id=bundle_id,
            )
        )
    size = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
    bundle = ArtifactRow(
        artifact_id=bundle_id,
        job_id=job_id,
        kind="replay_bundle",
        name=directory.name,
        sha256=directory_hash(directory),
        size_bytes=size,
        relpath=directory.relative_to(root).as_posix(),
    )
    return bundle, members


class _Body:
    """One job's operation body: its stage boundaries, its fenced events and its files."""

    def __init__(
        self,
        context: RunContext,
        job: Job,
        check: Callable[[], None],
        cancel: Callable[[CancelReason], None],
        on_stage: Callable[[str], None] | None = None,
    ) -> None:
        self.context = context
        self.job = job
        self.check = check
        self.cancel = cancel
        self.on_stage = on_stage
        self.directory = context.job_directory(job.job_id)
        self.stages: tuple[str, ...] = ()

    # -- events -------------------------------------------------------------------------------

    def at(self, stage: str) -> None:
        """A stage boundary (§6.4, §8.1): the executor's `on_stage` (a worker's test hook, §15
        W4c), then honour a cancellation recorded in the store, check, and emit the stage's
        progress."""
        if self.on_stage is not None:
            self.on_stage(stage)
        self._honour_interruption()
        self._emit(
            progress=Progress(
                completed=self.stages.index(stage), total=len(self.stages), stage=stage
            )
        )

    def _honour_interruption(self) -> None:
        """Raise `JobInterrupted` for a cancellation recorded in the store, a signalled one, or
        a passed deadline."""
        if self.context.store.cancel_requested(self.job.job_id):
            self.cancel("cancel_requested")
        self.check()

    def _emit(self, *, progress: Progress | None = None, output: ArtifactRef | None = None) -> None:
        written = self.context.store.append_job_event(
            self.job.job_id,
            owner_instance=self.context.owner_instance,
            progress=progress,
            output=output,
        )
        if not written:
            raise _FenceLost(self.job.job_id)

    def _register(self, rows: list[ArtifactRow]) -> None:
        store = self.context.store
        with store.writing() as connection:
            store.register_artifacts(connection, rows)

    def _file_output(self, name: str, document: Any) -> ArtifactRow:
        """Write one of the job's own files, register it as `<job_id>:<name>` and emit it."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / name
        path.write_bytes(canonical_json(document))
        row = ArtifactRow(
            artifact_id=f"{self.job.job_id}:{name}",
            job_id=self.job.job_id,
            kind=KIND_OF_FILE[name],
            name=name,
            sha256=file_sha256(path),
            size_bytes=path.stat().st_size,
            relpath=path.relative_to(self.context.root).as_posix(),
        )
        self._register([row])
        self._emit(output=row.as_ref())
        return row

    def _bundle(self, directory: Path, bundle_id: str) -> tuple[ArtifactRow, list[ArtifactRow]]:
        bundle, members = bundle_rows(
            self.context.root, directory, bundle_id, self.job.job_id, producer=True
        )
        self._register([bundle, *members])
        return bundle, members

    def partial_trace(self, trace: Trace) -> None:
        """§8.1: the events recorded so far, as `partial-solve-events.json`, if there are any."""
        if len(trace.events) > 0:
            self._file_output(PARTIAL_TRACE, [event.as_document() for event in trace.events])

    # -- solve --------------------------------------------------------------------------------

    def solve(self) -> WorkerResult:
        body = self.job.request.body
        assert isinstance(body, SolveBody)
        self.stages = SOLVE_STAGES
        store = self.context.store
        trace = Trace()
        run: dict[str, Any] | None = None
        #: The route the solve runs on, once selected (and re-bound): named by a typed end.
        selected: Route | None = None
        try:
            self.at("resolve")
            with store.reading() as connection:
                revision = store.get_revision(connection, body.revision_id)
            if revision is None:
                return _failed(_error("not_found", "no such revision"), run)
            document = revision.as_document()
            route = select_route(document)
            if not isinstance(route, Route):
                return _failed(
                    _error(
                        "revision_unsupported",
                        f"no solve route binds revision {body.revision_id!r}",
                        unbound=route.reason,
                        hint=route.hint,
                    ),
                    run,
                )
            selected = route
            resolved = resolve_policies(route, body)
            if isinstance(resolved, ApiError):
                return _failed(resolved, run)
            policy, check_policy = resolved
            run = {
                "solve_path": route.solve_path,
                "policy_id": policy.policy_id,
                "policy_sha256": policy_sha256(policy),
                "check_policy_sha256": check_policy.sha256,
                "run_id": None,
                "outcome": None,
                "verification_status": None,
                "structural_sha256": None,
            }
            # Ruling round 1 R5: the worker's own assertion that nothing loosens verification.
            if check_policy.relaxations():
                kinds = sorted(item.detail["check"] for item in check_policy.relaxations())
                return _failed(
                    _error(
                        "verification_weakening_refused",
                        f"verification_weakening_refused({','.join(kinds)})",
                        kind=kinds[0],
                    ),
                    run,
                )

            self.at("bind")
            bound = bind_route(route.solve_path, document)
            if not isinstance(bound, Route):
                return _failed(
                    _error(
                        "revision_unsupported",
                        f"route {route.solve_path} no longer binds revision {body.revision_id!r}",
                        unbound=f"{bound.kind}({bound.detail})",
                    ),
                    run,
                )
            selected = bound
            # ADR 0024 D2: the lookup is here, where the store is, and only when the policy opts
            # in on the route that reads it; the orchestrator never reads the store.
            warm_start = None
            if bound.solve_path == "revision_eo" and WARM_START_SOURCE in policy.initializer_chain:
                warm_start = warm_start_candidate(self.context, self.job.job_id, body.revision_id)
            directory = self.directory / "bundle"
            manifest = run_revision_session(
                bound,
                document,
                directory,
                run_id=f"run-{self.job.job_id}",
                policy=policy,
                check_policy=check_policy,
                policy_requested=body.policy_id,
                trace=trace,
                stage=self.at,
                warm_start=warm_start,
            )
        except JobInterrupted as interrupted:
            self.partial_trace(trace)
            return _interrupted(interrupted, run)
        except KeyboardInterrupt:
            self.partial_trace(trace)
            raise
        except (RunUnsupportedError, VerifierError, SolutionStateMismatchError) as error:
            return _typed_end(error, run, selected)
        except _FenceLost:
            return _failed(_error("internal_error", "fence_lost"), run, "owner_lost")

        bundle, members = self._bundle(directory, f"{self.job.job_id}:bundle")
        by_name = {member.name: member for member in members}
        judged = by_name.get(CERTIFICATE) or by_name[FAILURE]
        try:
            for row in (judged, by_name[MANIFEST_NAME], bundle):
                self._emit(output=row.as_ref())
        except _FenceLost:
            return _failed(_error("internal_error", "fence_lost"), run, "owner_lost")
        assert run is not None
        verdict = None
        if CERTIFICATE in by_name:
            verdict = read_artifact(directory, CERTIFICATE)["verification_status"]
        run.update(
            run_id=manifest.run_id,
            outcome=manifest.outcome,
            verification_status=verdict,
            structural_sha256=manifest.structural_sha256,
            policy_sha256=manifest.policy_sha256,
            check_policy_sha256=manifest.check_policy_sha256,
        )
        return WorkerResult(
            status="completed",
            reason="operation_completed",
            interruption=None,
            error=None,
            run=run,
        )

    # -- reproduce ----------------------------------------------------------------------------

    def reproduce(self) -> WorkerResult:
        body = self.job.request.body
        assert isinstance(body, ReproduceBody)
        self.stages = REPRODUCE_STAGES if body.rerun else ("integrity", "compare")
        store = self.context.store
        archive = store.artifact(body.bundle_artifact_id)
        if archive is None or archive.kind != "replay_bundle":
            return _failed(
                _error(
                    "not_found",
                    f"no replay bundle {body.bundle_artifact_id!r}",
                    artifact_id=body.bundle_artifact_id,
                ),
                None,
            )
        rerun_directory = self.directory / "rerun"
        rerun_id = f"{self.job.job_id}:rerun"

        def at(stage: str) -> None:
            # The rerun's bundle is complete by `compare`; it is the rerun stage's output (J2).
            if stage == "compare" and (rerun_directory / MANIFEST_NAME).is_file():
                # §8.1: an interruption that came during the rerun's verify or bundle, where no
                # trace record checks it, must not register or emit a certificate (T07 review S2).
                self._honour_interruption()
                bundle, _ = self._bundle(rerun_directory, rerun_id)
                self._emit(output=bundle.as_ref())
            self.at(stage)

        try:
            reproduction = reproduce_bundle(
                self.context.root / archive.relpath,
                rerun=body.rerun,
                rerun_directory=rerun_directory,
                run_id=f"run-{self.job.job_id}",
                stage=at,
            )
            self._file_output(REPLAY_REPORT, reproduction.report.as_document())
        except JobInterrupted as interrupted:
            return _interrupted(interrupted, None)
        except (RunUnsupportedError, VerifierError, SolutionStateMismatchError) as error:
            return _typed_end(error, None)
        except BundleError as error:
            _LOG.warning("job %s: unreadable bundle: %s", self.job.job_id, error)
            return _failed(
                _error(
                    "invalid_request",
                    "the bundle cannot be read (bundle_unreadable)",
                    pointer="/body/bundle_artifact_id",
                ),
                None,
            )
        except _FenceLost:
            return _failed(_error("internal_error", "fence_lost"), None, "owner_lost")
        return WorkerResult(
            status="completed", reason="operation_completed", interruption=None, error=None
        )

    # -- experiment ---------------------------------------------------------------------------

    def experiment(self) -> WorkerResult:
        body = self.job.request.body
        assert isinstance(body, ExperimentBody)
        self.stages = EXPERIMENT_STAGES
        sink = _RecordingSink(ArtifactTableSink(self.context.store))
        records = ExperimentStore(self.context.root, sink)
        emitted = 0

        def emit_records() -> None:
            nonlocal emitted
            for ref in sink.refs[emitted:]:
                self._emit(output=ref)
            emitted = len(sink.refs)

        try:
            self.at("resolve")
            model = body.model
            variant = variants.resolve(model.id, model.version, model.artifact_ref)
            if variant is None:  # admitted, and registered variants are package data: a defect
                return _failed(_error("internal_error", "variant_unresolved"), None)
            runner = ExperimentRunner(
                records,
                PrC1Provider(),
                EvaluationContext(
                    model_version=variant.variant_id, constants_sha256=variant.sha256
                ),
                job_id=self.job.job_id,
                check=self.check,
            )
            inlet = StreamState(
                n=body.inlet.n,
                temperature=body.inlet.temperature,
                pressure=body.inlet.pressure,
            )
            self.at("evaluate")
            outcome = runner.run(
                variant, inlet, body.inlet.components, body.n_tubes, cache=body.cache
            )
            self.at("record")
            emit_records()
            if outcome.result is not None and not any(
                ref.kind == "experiment_result" for ref in sink.refs
            ):
                producing = records.producing_artifact_id(outcome.key)
                row = self.context.store.artifact(producing) if producing is not None else None
                if row is not None:
                    self._emit(output=row.as_ref())
        except JobInterrupted as interrupted:
            try:
                emit_records()  # the attempts written before the interruption (§3.3)
            except _FenceLost:
                return _failed(_error("internal_error", "fence_lost"), None, "owner_lost")
            return _interrupted(interrupted, None)
        except _FenceLost:
            return _failed(_error("internal_error", "fence_lost"), None, "owner_lost")
        return WorkerResult(
            status="completed", reason="operation_completed", interruption=None, error=None
        )

    # -- surrogate study ----------------------------------------------------------------------

    def surrogate_study(self) -> WorkerResult:
        """M04 spec §10.3: the registered plan through the experiment runner, cache first, then
        the evidence; the manifest and then the evidence that names it by SHA-256 are the job's
        two outputs (spec §18 A1.4). The experiment records are registered as artifacts of the
        job (R-237's sink) but are not outputs: a study writes hundreds. A budget refusal writes
        nothing. The job ends `completed` whatever the verdict; the answer is `study`."""
        body = self.job.request.body
        assert isinstance(body, SurrogateStudyBody)
        self.stages = SURROGATE_STUDY_STAGES
        records = ExperimentStore(self.context.root, ArtifactTableSink(self.context.store))
        try:
            self.at("resolve")
            parent = body.parent
            variant = variants.resolve(parent.model_id, parent.variant_id, parent.variant_sha256)
            if variant is None:  # admitted, and registered variants are package data: a defect
                return _failed(_error("internal_error", "variant_unresolved"), None)
            runner = ExperimentRunner(
                records,
                PrC1Provider(),
                EvaluationContext(
                    model_version=variant.variant_id, constants_sha256=variant.sha256
                ),
                job_id=self.job.job_id,
                check=self.check,
            )
            # Spec §18 A1.2: admission judged the earlier iterations; their manifests are the
            # predecessors (an `it<i>` refused here was permitted at admission: a defect).
            predecessors = iteration_predecessors(
                variant,
                body.plan_id,
                stored_surrogate_manifests(self.context.store, self.context.root)
                if REGISTERED_PLANS[body.plan_id][0] > 1
                else (),
            )
            self.at("study")
            outcome = run_study(
                runner,
                variant,
                body.plan_id,
                body.max_cold_experiments,
                predecessors=predecessors,
                between=self._honour_interruption,
            )
            self.at("record")
            manifest_sha256 = evidence_sha256 = None
            if outcome.manifest is not None and outcome.evidence is not None:
                manifest_sha256 = self._file_output(MANIFEST_FILE, outcome.manifest).sha256
                evidence_sha256 = self._file_output(EVIDENCE_FILE, outcome.evidence).sha256
        except PlanRefusedError as refused:  # admission checked the plan: a defect if reached
            return _failed(_error("internal_error", f"plan_refused({refused.code})"), None)
        except JobInterrupted as interrupted:
            return _interrupted(interrupted, None)
        except _FenceLost:
            return _failed(_error("internal_error", "fence_lost"), None, "owner_lost")
        answer = {
            "verdict": outcome.verdict,
            "insufficient": list(outcome.insufficient),
            "not_promotable": list(outcome.not_promotable),
            "surrogate_id": outcome.surrogate_id,
            "manifest_sha256": manifest_sha256,
            "evidence_sha256": evidence_sha256,
            "cold_experiments": outcome.cold_experiments,
            "cache_hits": outcome.cache_hits,
            "cache_misses": outcome.cache_misses,
        }
        return WorkerResult(
            status="completed",
            reason="operation_completed",
            interruption=None,
            error=None,
            study=answer,
        )


def execute(
    context: RunContext,
    job: Job,
    *,
    check: Callable[[], None],
    cancel: Callable[[CancelReason], None],
    on_stage: Callable[[str], None] | None = None,
) -> WorkerResult:
    """Run `job`'s operation body (the job is `running` under `context.owner_instance`).

    `check` is the installed interruption check (§8.1), called again at every stage boundary;
    `cancel` sets the job's cancel token, so that a cancellation recorded in the store by another
    caller stops the body at its next boundary. `on_stage`, when given, is called with the stage's
    name at the start of every stage boundary, before the check (a worker's pause hook, §15 W4c).
    `JobInterrupted` never escapes; a `KeyboardInterrupt` does, after the partial trace is
    written.
    """
    body = _Body(context, job, check, cancel, on_stage)
    if job.operation == "solve":
        return body.solve()
    if job.operation == "experiment":
        return body.experiment()
    if job.operation == "surrogate_study":
        return body.surrogate_study()
    return body.reproduce()
