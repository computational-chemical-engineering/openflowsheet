"""`JobService`: the job operations, from submission and the run requests to a job's result
(ADR 0076 I-12d, the top service, above `ValidationService`).

`LocalApplication` delegates `solve`, `reproduce`, `submit_job`, `get_job`, `list_jobs`,
`list_job_events`, `wait_job`, `cancel_job` and `get_job_result` here; their contract documentation
is the facade's.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import time
import uuid
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, NoReturn

from openflowsheet.application.admission import active_jobs_refusal, resolve_policies
from openflowsheet.application.artifact_service import ArtifactService
from openflowsheet.application.contract import Page
from openflowsheet.application.errors import ApiError, ApplicationError, api_error
from openflowsheet.application.inspection_service import InspectionService
from openflowsheet.application.inspection_types import JobWait, SubmitResult
from openflowsheet.application.job_records import (
    Job,
    JobEvent,
    JobResult,
    RunFailure,
    RunResult,
    _replay_report_build,
)
from openflowsheet.application.job_requests import JobRequest, ReproduceBody, SolveBody
from openflowsheet.application.jobs.artifact_rows import bundle_rows, record_rows
from openflowsheet.application.jobs.model import JOB_STATUSES, TERMINAL_STATUSES, JobStatus
from openflowsheet.application.policy_types import CapabilityReference, ReplayPolicy
from openflowsheet.application.revision_run import Route, select_route
from openflowsheet.application.revision_service import RevisionService, encode_cursor
from openflowsheet.application.revisions import Revision
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.solve_policy_service import SolvePolicyService
from openflowsheet.application.store import IMPORTS_DIR
from openflowsheet.application.store_records import (
    ActiveJobLimitError,
    AuditEntry,
    IdempotencyKeyReusedError,
    LedgerRow,
)
from openflowsheet.application.validation_service import ValidationService
from openflowsheet.canonical import first_noncanonical
from openflowsheet.run.bundle import MANIFEST_NAME
from openflowsheet.run.replay import ReplayReport
from openflowsheet.schema_check import DocumentSchemaError, validate_document
from openflowsheet.studies.nlp.replay import MANIFEST as OPTIMIZATION_MANIFEST
from openflowsheet.studies.nlp.replay import is_optimization_record
from openflowsheet.units.display import DisplayUnits

#: §4.2: `wait_job` polls the store this often.
WAIT_POLL_S: Final[float] = 0.1
#: §11.4: page sizes — job lists as arrays (default 50, at most 200), events (100, at most 500).
MAX_JOB_PAGE: Final[int] = 200
MAX_EVENT_PAGE: Final[int] = 500


class JobService:
    """The job operations over one caller's `ServiceCore`. Each public method is the
    `LocalApplication` method of the same name, documented there; it takes every argument
    explicitly (the defaults are the facade's)."""

    def __init__(
        self,
        core: ServiceCore,
        inspection: InspectionService,
        revisions: RevisionService,
        artifacts: ArtifactService,
        validation: ValidationService,
        policies: SolvePolicyService,
    ) -> None:
        self._core = core
        self._policies = policies
        self._inspection = inspection
        self._revisions = revisions
        self._artifacts = artifacts
        self._validation = validation

    def solve(self, revision_id: str, policy_id: str) -> RunResult:
        caller = self._core.authorize("solve")
        request = JobRequest(
            operation="solve",
            idempotency_key=f"auto:{uuid.uuid4().hex}",
            body=SolveBody(revision_id=revision_id, policy_id=policy_id),
        )
        job_id = self._submit(request, caller, "solve").job.job_id
        self._wait_until_ended(job_id, "solve")
        result = self._result(job_id, "solve")
        assert result.run_result is not None
        return result.run_result

    def reproduce(self, bundle_path: str | os.PathLike[str], policy: ReplayPolicy) -> ReplayReport:
        operation = "reproduce"
        caller = self._core.authorize(operation)
        if not isinstance(policy, ReplayPolicy):
            self._core.refuse("invalid_request", "policy is a ReplayPolicy", operation=operation)
        artifact_id = self._import_bundle(Path(bundle_path), operation)
        request = JobRequest(
            operation="reproduce",
            idempotency_key=f"auto:{uuid.uuid4().hex}",
            body=ReproduceBody(bundle_artifact_id=artifact_id, rerun=policy.rerun),
        )
        job_id = self._submit(request, caller, operation).job.job_id
        job = self._wait_until_ended(job_id, operation)
        result = self._result(job_id, operation)
        if result.replay_report is not None:
            return result.replay_report
        raise ApplicationError(result.error if result.error is not None else _unproduced(job))

    def submit_job(self, request: JobRequest) -> SubmitResult:
        caller = self._core.authorize("submit_job")
        return self._submit(request, caller, "submit_job")

    def get_job(self, job_id: str) -> Job:
        self._core.authorize("get_job")
        return self._artifacts.job(job_id, "get_job")

    def list_jobs(self, *, status: JobStatus | None, cursor: str | None, limit: int) -> Page[Job]:
        operation = "list_jobs"
        self._core.authorize(operation)
        if status is not None and status not in JOB_STATUSES:
            self._core.refuse(
                "invalid_request",
                f"status is one of {list(JOB_STATUSES)}",
                operation=operation,
                pointer="/status",
            )
        self._inspection.check_limit(limit, MAX_JOB_PAGE, operation)
        after = self._revisions.decode_cursor(cursor, operation)
        rows, more = self._core.store.list_jobs(status=status, after_ordinal=after, limit=limit)
        next_cursor = encode_cursor(rows[-1][0]) if more else None
        return Page(items=tuple(job for _, job in rows), next_cursor=next_cursor)

    def list_job_events(self, job_id: str, *, after_sequence: int, limit: int) -> Page[JobEvent]:
        operation = "list_job_events"
        self._core.authorize(operation)
        self._inspection.check_limit(limit, MAX_EVENT_PAGE, operation)
        self._check_sequence(after_sequence, operation)
        found = self._core.store.job_events_after(job_id, after_sequence, limit + 1)
        if found is None:
            self._core.refuse("not_found", "no such job", operation=operation, job_id=job_id)
        events = found[1]
        more = len(events) > limit
        events = events[:limit]
        return Page(items=tuple(events), next_cursor=str(events[-1].sequence) if more else None)

    def wait_job(self, job_id: str, *, after_sequence: int, timeout_s: float) -> JobWait:
        operation = "wait_job"
        self._core.authorize(operation)
        self._check_sequence(after_sequence, operation)
        if (
            isinstance(timeout_s, bool)
            or not isinstance(timeout_s, int | float)
            or math.isnan(timeout_s)
            or timeout_s < 0
        ):
            self._core.refuse(
                "invalid_request",
                "timeout_s is a number >= 0",
                operation=operation,
                pointer="/timeout_s",
            )
        return self._wait(job_id, after_sequence, float(timeout_s), operation)

    def cancel_job(self, job_id: str) -> Job:
        operation = "cancel_job"
        caller = self._core.authorize(operation, target_principal=self._core.principal_id)
        job = self._artifacts.job(job_id, operation)
        caller = self._core.authorize(operation, target_principal=job.principal_id)
        outcome = self._core.store.request_cancel(
            job_id,
            AuditEntry(
                principal_id=caller.principal_id,
                capability_id=caller.capability_id,
                operation=operation,
                outcome="allowed",
                request_sha256=job.request_sha256,
                effect=f"cancel:{job_id}",
            ),
        )
        assert outcome is not None
        status, recorded = outcome
        if recorded and status == "running":
            self._core.executor.signal_cancel(job_id)
        return self._artifacts.job(job_id, operation)

    def get_job_result(self, job_id: str, *, display_units: str | None) -> JobResult:
        self._core.authorize("get_job_result")
        units = (
            None
            if display_units is None
            else self._artifacts.display_units(display_units, "get_job_result")
        )
        result = self._result(job_id, "get_job_result", display_units=units)
        return result if units is None else _displayed(result, units)

    def _submit(
        self, request: JobRequest, caller: CapabilityReference, operation: str
    ) -> SubmitResult:
        document = request.as_document()
        # As `dispatch` orders them (§4.3): a non-canonical value is named as such, not as a
        # schema error.
        pointer = first_noncanonical(document)
        if pointer is not None:
            self._core.refuse(
                "document_not_canonical",
                "a value has no canonical JSON form (NaN, an infinity, an integer beyond 2^53 that "
                "is not a binary64's canonical spelling, or not JSON at all)",
                operation=operation,
                pointer=pointer,
            )
        try:
            validate_document("job.schema.json#/$defs/job_request", document)
        except DocumentSchemaError as error:
            self._core.refuse(
                "invalid_request", error.message, operation=operation, pointer=error.pointer
            )
        request_sha256 = request.request_sha256
        store = self._core.store
        with store.reading() as connection:
            prior = store.ledger_lookup(
                connection, caller.principal_id, "submit_job", request.idempotency_key
            )
        if prior is not None:
            return self._replayed_job(prior, request_sha256, operation)
        budgets = self._validation.admit(request, caller, operation, request_sha256)
        try:
            job, replayed = store.accept_job(
                request,
                principal_id=caller.principal_id,
                capability_id=caller.capability_id,
                # §5.5: the project-policy document hash at acceptance.
                policy_sha256=self._core.policy.current().policy_sha256,
                owner_instance=self._core.owner_instance,
                effective_budgets=budgets,
                max_active_jobs=caller.limits.max_active_jobs,
            )
        except IdempotencyKeyReusedError as error:
            self._refuse_key_reused(error.original_request_sha256, request_sha256, operation)
        except ActiveJobLimitError as error:
            # Admission's early count raced another submission (T07 review S4).
            refused = active_jobs_refusal(caller.limits, error.active_jobs)
            assert refused is not None
            self._core.refuse_error(refused, operation, request_sha256)
        if not replayed:
            self._core.executor.run(self._core.context(), job.job_id)
            job = self._artifacts.job(job.job_id, operation)
        return SubmitResult(job=job, replayed=replayed)

    def _replayed_job(self, prior: LedgerRow, request_sha256: str, operation: str) -> SubmitResult:
        """§7: the existing job, as it is now; a different request under the key is refused."""
        if prior.request_sha256 != request_sha256:
            self._refuse_key_reused(prior.request_sha256, request_sha256, operation)
        return SubmitResult(job=self._artifacts.job(str(prior.result), operation), replayed=True)

    def _refuse_key_reused(self, original: str, request_sha256: str, operation: str) -> NoReturn:
        self._core.refuse(
            "idempotency_key_reused",
            "this idempotency key was used with a different job request; use a new key for a "
            "new job",
            operation=operation,
            request_sha256=request_sha256,
            original_request_sha256=original,
        )

    def _wait(self, job_id: str, after_sequence: int, timeout_s: float, operation: str) -> JobWait:
        deadline = time.monotonic() + timeout_s
        while True:
            found = self._core.store.job_events_after(job_id, after_sequence, 100)
            if found is None:
                self._core.refuse("not_found", "no such job", operation=operation, job_id=job_id)
            job, events = found
            ended = job.status in TERMINAL_STATUSES
            remaining = deadline - time.monotonic()
            if events or ended or remaining <= 0:
                return JobWait(job=job, events=tuple(events), ended=ended)
            time.sleep(min(WAIT_POLL_S, remaining))

    def _wait_until_ended(self, job_id: str, operation: str) -> Job:
        after = -1
        while True:
            waited = self._wait(job_id, after, math.inf, operation)
            if waited.ended:
                return waited.job
            after = waited.events[-1].sequence

    def _result(
        self, job_id: str, operation: str, *, display_units: DisplayUnits | None = None
    ) -> JobResult:
        job = self._artifacts.job(job_id, operation)
        if job.status not in TERMINAL_STATUSES:
            self._core.refuse(
                "not_ready",
                f"job {job_id} is {job.status}; its result exists once it has ended",
                operation=operation,
                retryable=True,
                job_id=job_id,
                status=job.status,
            )
        if job.operation == "solve":
            return JobResult(
                operation="solve",
                run_result=self._run_result(job, display_units=display_units),
                replay_report=None,
                error=job.error,
            )
        if job.operation == "experiment":
            return JobResult(
                operation="experiment",
                run_result=None,
                replay_report=None,
                error=job.error,
                experiment=self._experiment_answer(job),
            )
        if job.operation == "surrogate_study":
            worker = self._core.store.worker_result(job.job_id)
            study = worker.get("study") if isinstance(worker, Mapping) else None
            return JobResult(
                operation="surrogate_study",
                run_result=None,
                replay_report=None,
                error=job.error,
                surrogate_study=study,
            )
        if job.operation == "optimize":
            # OPT §4.10: the answer is the report the job output, absent when it ended without.
            optimization = None
            for output in job.outputs:
                if output.kind == "optimization_report":
                    optimization = json.loads(self._artifacts.artifact_path(output).read_bytes())
            return JobResult(
                operation="optimize",
                run_result=None,
                replay_report=None,
                error=job.error,
                optimization=optimization,
            )
        report = None
        for output in job.outputs:
            if output.kind == "replay_report":
                report = _replay_report_build(
                    json.loads(self._artifacts.artifact_path(output).read_bytes())
                )
        return JobResult(
            operation="reproduce", run_result=None, replay_report=report, error=job.error
        )

    def _experiment_answer(self, job: Job) -> dict[str, Any] | None:
        """ADR 0033 D9: the experiment's `result` when the job output one (its own, a cache hit's
        row or the producing row), else its last `attempt`; `None` when it output neither."""
        results = [output for output in job.outputs if output.kind == "experiment_result"]
        attempts = [output for output in job.outputs if output.kind == "experiment_attempt"]
        chosen = results[-1] if results else (attempts[-1] if attempts else None)
        if chosen is None:
            return None
        answer: dict[str, Any] = json.loads(self._artifacts.artifact_path(chosen).read_bytes())
        return answer

    def _run_result(self, job: Job, *, display_units: DisplayUnits | None = None) -> RunResult:
        """§5.7, read from what the job produced: the resolution and run facts its runner
        recorded (`worker_result.run`) and its outputs; a job that never resolved its request
        (cancelled while queued) has its resolution re-derived — a pure function of the stored
        revision and the registries — and no run facts."""
        body = job.request.body
        assert isinstance(body, SolveBody)
        with self._core.store.reading() as connection:
            revision = self._core.store.get_revision(connection, body.revision_id)
        assert revision is not None
        worker = self._core.store.worker_result(job.job_id)
        run = worker.get("run") if isinstance(worker, Mapping) else None
        if run is None:
            run = self._resolution(revision, body)
        return RunResult(
            job_id=job.job_id,
            run_id=run["run_id"],
            revision_id=body.revision_id,
            revision_content_sha256=revision.content_hash,
            policy_id=run["policy_id"],
            policy_sha256=run["policy_sha256"],
            check_policy_sha256=run["check_policy_sha256"],
            job_status=job.status,  # type: ignore[arg-type]
            outcome=run["outcome"],
            verification_status=run["verification_status"],
            structural_sha256=run["structural_sha256"],
            outputs=job.outputs,
            error=job.error,
            solve_path=run["solve_path"],
            failure=self._run_failure(job, revision, run, display_units=display_units),
        )

    def _run_failure(
        self,
        job: Job,
        revision: Revision,
        run: Mapping[str, Any],
        *,
        display_units: DisplayUnits | None = None,
    ) -> RunFailure | None:
        """ADR 0058 D5 (MSG §3.4, §4.8): the failure, derived on read from the stored
        `failure-bundle.json`, the run's `diagnosis` when the runner recorded one, and the
        revision document — so a job a 0.3 store holds gets one too (without numbers). A bundle
        that cannot be read or parsed gives the failure of the outcome alone. Never raises.
        The explanation is rendered under `display_units` (ADR 0075 D7.4); `params` stay SI."""
        from openflowsheet.messages.render import RenderContext, explain_failure
        from openflowsheet.verify.failure import TAXONOMY

        output = next((o for o in job.outputs if o.kind == "failure_bundle"), None)
        if output is None:
            return None
        bundle: Mapping[str, Any] = {}
        try:
            loaded = json.loads(self._artifacts.artifact_path(output).read_bytes())
            if isinstance(loaded, Mapping):
                bundle = loaded
        except (OSError, ValueError, AssertionError):
            bundle = {}
        outcome = bundle.get("outcome")
        if not isinstance(outcome, str):
            bundle, outcome = {}, str(run.get("outcome") or "")
        observations = bundle.get("observations")
        message = observations.get("message") if isinstance(observations, Mapping) else None
        message = message if isinstance(message, str) else None
        taxonomy = bundle.get("taxonomy")
        # The sidecar explains the bundle's message; without the bundle it has nothing to match.
        diagnosis = run.get("diagnosis") if bundle else None
        explanation, params = explain_failure(
            outcome=outcome,
            message=message,
            diagnosis=diagnosis if isinstance(diagnosis, Mapping) else None,
            context=RenderContext(
                revision=revision.document,
                revision_id=revision.revision_id,
                job_id=job.job_id,
                bundle_id=output.artifact_id.rpartition("/")[0] or None,
                display_units=display_units,
            ),
        )
        return RunFailure(
            outcome=outcome,
            taxonomy=taxonomy if isinstance(taxonomy, str) else TAXONOMY.get(outcome, ""),
            message=message,
            code=str(explanation["code"]),
            chain=tuple(str(code) for code in explanation["chain"]),
            implicated=tuple(str(s) for s in bundle.get("implicated_sources") or ()),
            suggested_actions=tuple(
                str(entry["action"])
                for entry in bundle.get("suggested_actions") or ()
                if isinstance(entry, Mapping) and "action" in entry
            ),
            failure_bundle=output.artifact_id,
            params=params,
            explanation=explanation,
        )

    def _resolution(self, revision: Revision, body: SolveBody) -> dict[str, Any]:
        from openflowsheet.run.manifest import policy_sha256

        route = select_route(revision.as_document(), surrogates=self._core.surrogates())
        project = self._policies.project_policies("get_job_result", body.policy_id)
        resolved = resolve_policies(route, body, project) if isinstance(route, Route) else None
        if not isinstance(route, Route) or not isinstance(resolved, tuple):
            raise api_error(
                "internal_error",
                "an admitted solve's request no longer resolves",
                job_revision=body.revision_id,
            )
        policy, check_policy = resolved
        return {
            "solve_path": route.solve_path,
            "policy_id": policy.policy_id,
            "policy_sha256": policy_sha256(policy),
            "check_policy_sha256": check_policy.sha256,
            "run_id": None,
            "outcome": None,
            "verification_status": None,
            "structural_sha256": None,
        }

    def _import_bundle(self, source: Path, operation: str) -> str:
        """§4.2 `reproduce`'s import: copy the regular files of `source` (no symlink followed)
        into `imports/<ordinal>/` and register the copy and its known members. An optimisation
        record (OPT design §4.9: no `manifest.json`, an `optimization-manifest.json` naming its
        format) is imported the same way and registered by `record_rows`."""
        if not source.is_dir():
            self._core.refuse(
                "not_found",
                "no bundle directory at this path",
                operation=operation,
                pointer="/bundle_path",
            )
        manifest = source / MANIFEST_NAME
        record = (
            not manifest.exists()
            and not (source / OPTIMIZATION_MANIFEST).is_symlink()
            and is_optimization_record(source)
        )
        if not record and (manifest.is_symlink() or not manifest.is_file()):
            self._core.refuse(
                "invalid_request",
                f"not a replay bundle: no {MANIFEST_NAME}",
                operation=operation,
                pointer="/bundle_path",
            )
        imports = self._core.files_root / IMPORTS_DIR
        imports.mkdir(parents=True, exist_ok=True)
        ordinal = len(list(imports.iterdir())) + 1
        while True:
            target = imports / f"{ordinal:06d}"
            try:
                target.mkdir()
                break
            except FileExistsError:
                ordinal += 1
        for directory, _, names in os.walk(source, followlinks=False):
            for name in sorted(names):
                path = Path(directory) / name
                if path.is_symlink() or not path.is_file():
                    continue
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
        bundle_id = f"import-{ordinal:06d}:bundle"
        bundle, members = (
            record_rows(self._core.files_root, target, bundle_id, None)
            if record
            else bundle_rows(self._core.files_root, target, bundle_id, None, producer=False)
        )
        with self._core.store.writing() as connection:
            self._core.store.register_artifacts(connection, [bundle, *members])
        return bundle.artifact_id

    def _check_sequence(self, after_sequence: int, operation: str) -> None:
        if (
            isinstance(after_sequence, bool)
            or not isinstance(after_sequence, int)
            or after_sequence < -1
        ):
            self._core.refuse(
                "invalid_request",
                "after_sequence is an integer >= -1",
                operation=operation,
                pointer="/after_sequence",
            )


def _displayed(result: JobResult, units: DisplayUnits) -> JobResult:
    """ADR 0075 D7.4: `result` with its `error` documents (the root's and the run result's)
    explained under `units` and the preference echoed. `project_response` keeps an explanation
    an error already carries (`operations.explained_detail`), so this rendering is the one sent."""
    run_result = result.run_result
    if run_result is not None:
        run_result = replace(run_result, error=_explained(run_result.error, units))
    return replace(
        result, run_result=run_result, error=_explained(result.error, units), display_units=units
    )


def _explained(error: ApiError | None, units: DisplayUnits) -> ApiError | None:
    from openflowsheet.messages.render import RenderContext, render_error

    if error is None:
        return None
    explanation = render_error(error.as_document(), context=RenderContext(display_units=units))
    return replace(error, detail={**error.detail, "explanation": explanation})


def _unproduced(job: Job) -> ApiError:
    """§5.8 as amended by ruling round 4 (W4a-Q3): `not_ready` for a result an ended job never
    produced — a `cancelled` or `timed_out` job with neither a report nor an error. `detail.reason`
    is the ending's reason. A new job may succeed unchanged (`retryable`) only after a
    `server_shutdown`: a timed-out job would time out again, and a cancel was someone's decision."""
    assert job.ending is not None
    reason = job.ending.reason
    return ApiError(
        code="not_ready",
        message=f"job {job.job_id} ended {job.status} ({reason}) without a replay report",
        retryable=reason == "server_shutdown",
        detail={"job_id": job.job_id, "status": job.status, "reason": reason},
    )
