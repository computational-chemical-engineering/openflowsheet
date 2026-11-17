"""`LocalApplication`: the one concrete implementation of the contract (T07 design note §4, D1).

HTTP, MCP and the CLI dispatch to an instance of this class and add nothing. An instance is one
*owner* (§9.3): it holds `owners/<owner_instance>.lock` for its lifetime, it alone executes the
jobs it accepted, and opening a project first recovers the jobs of owners that died.

**Authority (§10).** `capability=None` is the built-in `LOCAL_OWNER` — all six rights, no limits,
no token — which no transport can produce: the in-process caller owns the files, and restricting
it would be theatre. Any other capability is resolved against the *current* project policy on
every call, by its id and token hash, so a revocation or a narrowed grant takes effect on the next
call; the rights of the object passed in are never read. Every refusal is audited.

**Jobs (§4.2, §9.1).** Every solve and reproduce is a job. `submit_job` checks the request
(canonical form first, as `dispatch` does, then its schema), consults the idempotency ledger,
admits it (§5.3), accepts it and hands it to the executor. The inline executor (the default) runs
it before `submit_job` returns, in the calling thread, behind the process-wide
`jobs.executor.COMPUTE_LOCK`; the process executor (`executor="process"`, what a server uses)
queues it for a freshly spawned worker and `submit_job` returns the job as it is then. The frozen
`solve` and `reproduce` are submit, then wait, then result, with a fresh `auto:` key. A caller's
*own* thread drawing from `np.random` while a contract verification runs in this process is not
excluded by the lock (§9.4); `executor="process"` is the remedy. `close` shuts the executor down
first (§9.3): queued jobs end `cancelled(server_shutdown)` and running ones are stopped.
"""

from __future__ import annotations

import copy
import json
import math
import os
import shutil
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, NoReturn, Self

from openflowsheet.application.admission import (
    active_jobs_refusal,
    resolve_policies,
)
from openflowsheet.application.artifact_service import (
    STREAM_TABLE_DEPTH,
    ArtifactService,
    StreamTableQuery,
)
from openflowsheet.application.authz import (
    PolicyFile,
    StaticPolicy,
    authenticate,
)
from openflowsheet.application.contract import Page, Projection
from openflowsheet.application.errors import ApiError, ApiErrorCode, ApplicationError, api_error
from openflowsheet.application.inspection_service import InspectionService
from openflowsheet.application.inspection_types import (
    AdmissionReport,
    AuditOrder,
    AuditRecord,
    CapabilityPage,
    JobWait,
    MessageEntry,
    ModelRegistryView,
    ProjectSummary,
    RevisionSummary,
    SubmitResult,
)
from openflowsheet.application.job_records import (
    Job,
    JobEvent,
    JobResult,
    RunFailure,
    RunResult,
    _replay_report_build,
)
from openflowsheet.application.job_requests import (
    JobRequest,
    ReproduceBody,
    SolveBody,
)
from openflowsheet.application.jobs.executor import InlineExecutor, ProcessExecutor
from openflowsheet.application.jobs.model import JOB_STATUSES, TERMINAL_STATUSES, JobStatus
from openflowsheet.application.jobs.runner import bundle_rows, record_rows
from openflowsheet.application.policy_types import (
    CapabilityReference,
    ExecutorSettings,
    ProjectPolicy,
    ReplayPolicy,
)
from openflowsheet.application.projection import (
    DEFAULT_DEPTH,
    DEFAULT_PAGE,
)
from openflowsheet.application.revision_run import Route, select_route
from openflowsheet.application.revision_service import RevisionService, encode_cursor
from openflowsheet.application.revisions import Revision
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.store import (
    IMPORTS_DIR,
    ProjectStore,
)
from openflowsheet.application.store_records import (
    ActiveJobLimitError,
    AuditEntry,
    IdempotencyKeyReusedError,
    LedgerRow,
    StoreError,
    coded_store_error,
)
from openflowsheet.application.transaction_types import Change, SemanticDiff, TransactionResult
from openflowsheet.application.validation_report import Task, ValidationReport
from openflowsheet.application.validation_service import ValidationService
from openflowsheet.canonical import first_noncanonical
from openflowsheet.registry import default_registry
from openflowsheet.run.bundle import MANIFEST_NAME
from openflowsheet.run.replay import ReplayReport
from openflowsheet.schema_check import DocumentSchemaError, validate_document
from openflowsheet.studies.nlp.replay import MANIFEST as OPTIMIZATION_MANIFEST
from openflowsheet.studies.nlp.replay import is_optimization_record
from openflowsheet.units.display import DisplayUnits

Executor = Literal["inline", "process"]
#: §4.2: `wait_job` polls the store this often.
WAIT_POLL_S: Final[float] = 0.1
#: §11.4: page sizes — job lists as arrays (default 50, at most 200), events (100, at most 500).
MAX_JOB_PAGE: Final[int] = 200
MAX_EVENT_PAGE: Final[int] = 500


class LocalApplication:
    """One project, opened by one owner. Construct through `create`, `open` or `in_memory`.

    The Python transport of the application contract: every operation of the operations table is
    a method of the same name, taking the request's members as parameters and returning the
    result type whose `as_document()` is the response the CLI, HTTP and MCP carry.

    Examples
    --------
    >>> from openflowsheet.application.local import LocalApplication
    >>> with LocalApplication.in_memory() as app:
    ...     models = app.list_models()
    """

    def __init__(
        self,
        store: ProjectStore,
        *,
        owner_instance: str,
        policy: PolicyFile | StaticPolicy,
        capability: CapabilityReference | None,
    ) -> None:
        self.owner_instance = owner_instance
        self.recovered: tuple[str, ...] = ()
        self._bind(
            ServiceCore(store, owner_instance=owner_instance, policy=policy, capability=capability)
        )

    def _bind(self, core: ServiceCore) -> None:
        """The services over `core` (`__init__`; `authenticated`, with a core of its own)."""
        self._core = core
        self._inspection = InspectionService(core)
        self._revisions = RevisionService(core, self._inspection)
        self._artifacts = ArtifactService(core, self._revisions)
        self._validation = ValidationService(core, self._revisions)

    # ------------------------------------------------------------------------- construction

    @classmethod
    def create(
        cls,
        directory: str | os.PathLike[str],
        *,
        project_id: str | None = None,
        exist_ok: bool = False,
    ) -> LocalApplication:
        """A new project in `directory` (absent or empty), opened by the local owner.

        With `exist_ok`, a directory that already holds a project is opened instead (MSG §3.8,
        FB-01), so a script that creates its project can run twice. It tries to create first
        and opens only on the typed refusal `project_exists`, so there is no check-then-act
        race.

        Parameters
        ----------
        directory
            Where the project is created; it must be absent or empty, or (with `exist_ok`)
            hold a project.
        project_id
            The project's id; a fresh `project-<hex>` id when omitted. With `exist_ok`, an
            existing project must have this id when it is given.
        exist_ok
            Open the project the directory already holds instead of refusing it.

        Returns
        -------
        LocalApplication
            The new (or, with `exist_ok`, the existing) project, opened with the inline
            executor.

        Raises
        ------
        StoreError
            Coded (`.code`): `project_exists` (without `exist_ok`), `project_id_mismatch`,
            `directory_not_empty` (files that are not a project) or `not_a_directory`.
        """
        try:
            ProjectStore.create(
                Path(directory),
                project_id=project_id
                if project_id is not None
                else f"project-{uuid.uuid4().hex[:12]}",
            ).close()
        except StoreError as refused:
            if not exist_ok or refused.code != "project_exists":
                raise
            store = ProjectStore.open(Path(directory))
            try:
                existing = store.project_id
            finally:
                store.close()
            if project_id is not None and existing != project_id:
                raise coded_store_error(
                    "project_id_mismatch",
                    Path(directory),
                    project_id=project_id,
                    existing=existing,
                ) from None
        return cls.open(directory)

    @classmethod
    def open(
        cls,
        directory: str | os.PathLike[str],
        *,
        capability: CapabilityReference | None = None,
        executor: Executor | ProcessExecutor = "inline",
    ) -> LocalApplication:
        """Open a project: load its policy, take an owner lock, recover dead owners' jobs, then
        start the executor (§9.1): `"inline"`, `"process"`, or an unbound `ProcessExecutor`
        (a Python caller's, e.g. one constructed with `test_hooks=True`). The process executor
        takes the policy's `executor` settings in force now.

        An invalid policy file with no valid one before it refuses the open
        (`PolicyRefusedError`): a policy is never defaulted (§10.3).

        Parameters
        ----------
        directory
            An existing project directory (`create`, or `openflowsheet project init`).
        capability
            The capability to act as; the local owner, holding every right, when omitted.
        executor
            `"inline"` (jobs run in the calling process), `"process"` (a worker process), or an
            unbound `ProcessExecutor`.

        Returns
        -------
        LocalApplication
            The opened project. Close it with `close`, or use it as a context manager.
        """
        default_registry()  # ADR 0060 D8: the process registry is built at start
        process: ProcessExecutor | None = None
        if isinstance(executor, ProcessExecutor):
            process = executor
        elif executor == "process":
            process = ProcessExecutor()
        elif executor != "inline":
            raise api_error(
                "unsupported",
                f"the {executor!r} executor is not available in this build",
                executor=executor,
            )
        store = ProjectStore.open(Path(directory))
        try:
            assert store.policy_path is not None
            policy = PolicyFile(store.policy_path)
            owner_instance = uuid.uuid4().hex
            store.acquire_owner(owner_instance)
        except BaseException:
            store.close()
            raise
        application = cls(
            store, owner_instance=owner_instance, policy=policy, capability=capability
        )
        application.recovered = tuple(store.recover(own_instance=owner_instance))
        if process is not None:
            try:
                process.start(application._core.context(), policy.current().executor)
            except BaseException:
                application.close()
                raise
            application._core.executor = process
        return application

    @classmethod
    def in_memory(cls) -> LocalApplication:
        """SQLite `:memory:`, inline execution only, the local owner only; nothing survives.

        Returns
        -------
        LocalApplication
            A throw-away project; its files live in a scratch directory removed on `close`.
        """
        default_registry()  # ADR 0060 D8: the process registry is built at start
        project_id = f"memory-{uuid.uuid4().hex[:12]}"
        store = ProjectStore.in_memory(project_id=project_id)
        policy = StaticPolicy(
            ProjectPolicy(project_id, capabilities=(), executor=ExecutorSettings())
        )
        return cls(store, owner_instance=uuid.uuid4().hex, policy=policy, capability=None)

    def authenticated(self, token: str) -> LocalApplication | None:
        """§10.2 for a server that serves many credentials from one owner (HTTP): this owner
        acting as the grant `token` presents, or `None` — an unknown, malformed or expired token
        (401).

        The result shares this owner's store, policy, executor and owner lock (§9.3): a job it
        accepts is this owner's to run. Only the caller's capability differs, and it is resolved
        against the current policy on every call, like any other (`ServiceCore.caller`), so a
        revocation takes effect on the next call. The result is never closed; its owner is.
        """
        capability = authenticate(self._core.policy.current(), token)
        if capability is None:
            return None
        view = copy.copy(self)
        view._bind(self._core.acting_as(capability))
        return view

    def close(self) -> None:
        """Shut the executor down (§9.3), then release the store and the owner lock."""
        self._core.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------------------ accessors

    @property
    def store(self) -> ProjectStore:
        return self._core.store

    @property
    def project_id(self) -> str:
        return self._core.project_id

    @property
    def principal_id(self) -> str:
        return self._core.principal_id

    @property
    def capability_id(self) -> str:
        return self._core.capability_id

    @property
    def policy(self) -> ProjectPolicy:
        """The project policy in force now (hot-reloaded)."""
        return self._core.policy.current()

    @property
    def executor(self) -> InlineExecutor | ProcessExecutor:
        """The executor this owner runs its jobs on (its test hooks are Python-only)."""
        return self._core.executor

    @property
    def files_root(self) -> Path:
        """The directory `jobs/` and `imports/` live under: the project's, or an in-memory
        project's scratch directory."""
        return self._core.files_root

    # -------------------------------------------------------------------- Application (frozen)

    def validate(
        self, revision_id: str, task: Task, optimization: Mapping[str, Any] | None = None
    ) -> ValidationReport:
        """§4.2: the stored revision's validation report for `task`; no side effects. `read`.

        Parameters
        ----------
        revision_id
            A revision of this project.
        task
            `"simulation"` or `"optimization"` (OPT design §4.11, ADR 0071 D8).
        optimization
            The optimization request (`optimization-request.schema.json`), ADR 0019 Amendment
            16's optional member; read only for the optimization task, and required there.
            The static readiness only: nothing is solved.

        Returns
        -------
        ValidationReport
            The status (`INVALID`, `DRAFT`, `READY_FOR_SIMULATION` or, for the optimization
            task, `READY_FOR_OPTIMIZATION`) and every check.

        Raises
        ------
        ApplicationError
            `invalid_request` (also the missing `optimization`), `unsupported`
            (`nlp_solver_unavailable`, before the revision is read) or `not_found`.
        """
        return self._validation.validate(revision_id, task, optimization)

    def commit_change(
        self, change: Change, expected_revision: str | None, idempotency_key: str
    ) -> TransactionResult:
        """§4.2: the K06 algorithm, persistent and typed. Needs `draft`.

        The order: authorize; canonical check (Q29); ledger lookup (§7); build, validate and
        diff *outside* the write lock from a snapshot; then, inside one `BEGIN IMMEDIATE`
        transaction, the ledger again, the head check, the insert, the head move, the ledger
        row and the audit row. Returned: `committed`, `replayed` (same key, same request),
        `conflict` (the head moved) or `rejected` (a bad edit path, a taken or unknown id, a
        non-canonical value). Raised: a refusal, and a key reused with a different request.

        Parameters
        ----------
        change
            The edits to apply to the head (`Change`), with its optional new revision id.
        expected_revision
            The head the change was written against; `None` for a project's first revision.
        idempotency_key
            A key of the caller's choosing: the same key with the same request returns the
            first result (`replayed`) and never commits twice.

        Returns
        -------
        TransactionResult
            `status` is `committed`, `replayed`, `conflict` or `rejected`; a commit carries the
            new `revision_id`, the semantic diff and the validation report.

        Raises
        ------
        ApplicationError
            A refusal, for example `forbidden`, `document_not_canonical` or
            `idempotency_key_reused` (the key with a different request).
        """
        return self._revisions.commit_change(change, expected_revision, idempotency_key)

    def solve(self, revision_id: str, policy_id: str) -> RunResult:
        """§4.2: `submit_job` with a fresh `auto:` key, `wait_job` until it ends (no time-out),
        then `get_job_result(...).run_result`. Needs `execute`; a refusal at submission is raised.
        `policy_id` may be `"default"`, the route's registered policy (R2.3).

        Parameters
        ----------
        revision_id
            A revision that validates `READY_FOR_SIMULATION`.
        policy_id
            An offered solve policy id, or `"default"`.

        Returns
        -------
        RunResult
            The job status, the solver's outcome, the verifier's verdict and the artifacts the run
            registered (solution certificate, run manifest, replay bundle). A failed solve is a
            result, not an exception.

        Raises
        ------
        ApplicationError
            A refusal at submission, for example `revision_not_ready`, `not_found` (an unknown
            policy) or `unsupported` (a registered policy that is not offered).
        """
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
        """§4.2: import the bundle at `bundle_path` (its regular files, no symlink followed) as
        `import-<ordinal>:bundle`, submit `reproduce` with a fresh `auto:` key, wait, and return
        the report. Needs `execute`. A job that ends without a report raises its error, or, when
        it has none (`cancelled`, `timed_out`), `not_ready` (§5.8 as amended by ruling round 4)."""
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

    # ---------------------------------------------------------------------- JobControl (§4.1)

    def submit_job(self, request: JobRequest) -> SubmitResult:
        """§4.2: authorize `execute`; canonical form (Q29), then the schema; the ledger (§7);
        semantic admission (§5.3); accept (job, `accepted`, ledger row and audit row in one
        transaction); hand it to the executor. Returns the job as the executor leaves it —
        ended inline, queued or running under the process executor — or, same key, same request,
        the existing one with `replayed = true`."""
        caller = self._core.authorize("submit_job")
        return self._submit(request, caller, "submit_job")

    def get_job(self, job_id: str) -> Job:
        """§4.2: any job of the project (`read` covers every principal's jobs)."""
        self._core.authorize("get_job")
        return self._artifacts.job(job_id, "get_job")

    def list_jobs(
        self, *, status: JobStatus | None = None, cursor: str | None = None, limit: int = 50
    ) -> Page[Job]:
        """§4.2, §11.4: the project's jobs in acceptance order, by ordinal cursor."""
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

    def list_job_events(
        self, job_id: str, *, after_sequence: int = -1, limit: int = 100
    ) -> Page[JobEvent]:
        """§4.2, §11.4: a job's events after `after_sequence`; the next cursor is the last
        sequence returned, to pass back as `after_sequence`."""
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

    def wait_job(
        self, job_id: str, *, after_sequence: int = -1, timeout_s: float = 20.0
    ) -> JobWait:
        """§4.2: return once the job has events after `after_sequence` (a cancellation request
        among them), once it has ended, or at `timeout_s` (in-process, `math.inf` waits for
        either); polls every 0.1 s. At most 100 events."""
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
        """§4.2: needs `execute`, and `policy` as well for another principal's job. A queued job
        ends `cancelled` at once; a running one is flagged and signalled, and stops at its next
        checkpoint; an ended one is returned as it is. Idempotent."""
        operation = "cancel_job"
        caller = self._core.authorize(operation, target_principal=self.principal_id)
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

    def get_job_result(self, job_id: str, *, display_units: str | None = None) -> JobResult:
        """§4.2 as amended by R4: `{operation, run_result, replay_report, error}` of an ended
        job; `not_ready` before it ends. `display_units` (ADR 0075 D7.4, ADR 0019 Amendment 17)
        is a display preference, resolved against the project's declared ambient pressure: the
        result echoes it and every explanation it holds is rendered under it; its SI content is
        the result without it."""
        self._core.authorize("get_job_result")
        units = (
            None
            if display_units is None
            else self._artifacts.display_units(display_units, "get_job_result")
        )
        result = self._result(job_id, "get_job_result", display_units=units)
        return result if units is None else _displayed(result, units)

    # ------------------------------------------------------------------------- the job steps

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
                owner_instance=self.owner_instance,
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
        resolved = resolve_policies(route, body) if isinstance(route, Route) else None
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
        imports = self.files_root / IMPORTS_DIR
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
            record_rows(self.files_root, target, bundle_id, None)
            if record
            else bundle_rows(self.files_root, target, bundle_id, None, producer=False)
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

    # ----------------------------------------------------------------- Inspection (W2b part)

    def preview_change(self, change: Change, expected_revision: str | None) -> TransactionResult:
        """§4.2: `commit_change`'s steps 2 and 4–6 — no head check, no write, no ledger. `read`.

        The validation report names the id the commit would assign, so a preview and the commit
        that follows it with nothing in between report the same thing.
        """
        return self._revisions.preview_change(change, expected_revision)

    # ------------------------------------------------------------ Inspection (W5a, §4.2, §11.4)

    def get_project(self) -> ProjectSummary:
        """§4.2: the project, its head and counts, its solve policies, and the caller as its
        credential makes it. `read`."""
        return self._inspection.get_project()

    def list_models(self) -> ModelRegistryView:
        """§4.2: each model id in `MODEL_BUILDERS` with its declarative `ModelSignature`; nothing
        is constructed ("inspect manifests without executing them"). `read`.

        Returns
        -------
        ModelRegistryView
            Every model with its ports, required parameters, pins and one-of specifications, and
            for each pin the specification targets that can fix it.
        """
        return self._inspection.list_models()

    def list_revisions(
        self, *, cursor: str | None = None, limit: int = 50
    ) -> Page[RevisionSummary]:
        """§4.2, §11.4: the project's revisions in commit order, by ordinal cursor. `read`."""
        return self._revisions.list_revisions(cursor=cursor, limit=limit)

    def get_revision(
        self,
        revision_id: str,
        *,
        pointer: str = "",
        depth: int = DEFAULT_DEPTH,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE,
    ) -> Projection:
        """§11.4: the stored revision's document — `Revision.as_document()`, as `validate` reads
        it and a bundle's `revision.json` holds it — projected. `read`."""
        return self._revisions.get_revision(
            revision_id, pointer=pointer, depth=depth, cursor=cursor, limit=limit
        )

    def diff_revisions(self, from_revision: str, to_revision: str) -> SemanticDiff:
        """§4.2: the semantic diff (content paths added, removed, changed; the title and other
        descriptive members excluded) from one stored revision to another, with its
        `elements` (ADR 0019 Amendment 3, A3.2: the items of `instances`, `connections` and
        `specifications` that differ, paired by id). `read`."""
        return self._revisions.diff_revisions(from_revision, to_revision)

    def inspect_structure(
        self,
        revision_id: str,
        *,
        pointer: str = "",
        depth: int = DEFAULT_DEPTH,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE,
    ) -> Projection:
        """§4.2 as amended by R1.5: the structural report of the formulation `solve` would use,
        naming its `solve_path`, or `{"not_run_reason": …}` when no route binds the revision —
        `structure_inspection.route_structure`, projected. `read`."""
        return self._validation.inspect_structure(
            revision_id, pointer=pointer, depth=depth, cursor=cursor, limit=limit
        )

    def get_artifact(
        self,
        artifact_id: str,
        *,
        pointer: str = "",
        depth: int = DEFAULT_DEPTH,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE,
    ) -> Projection:
        """§11.4: a registered artifact, projected; any principal's (`read` covers them all).

        A file is its JSON when it holds a canonical JSON document, else its text lines. A
        `replay_bundle` is `{manifest, files: [{name, kind, artifact_id, sha256, size_bytes}]}`,
        its members listed — `solution-state.json` among them when the bundle has one (ruling
        round 2) — and each read in turn as `<bundle id>/<file>`. `sha256` is the registered
        one: the file's bytes, or the bundle's directory hash.

        Parameters
        ----------
        artifact_id
            An artifact id from a run's `outputs`, or `<bundle id>/<file>` for a bundle member.
        pointer
            A JSON pointer into the document; the whole document when empty.
        depth, cursor, limit
            Bounds of the projection, and the cursor of its next page.

        Returns
        -------
        Projection
            The value at `pointer`, with the artifact's SHA-256 and whether it was truncated.
        """
        return self._artifacts.get_artifact(
            artifact_id, pointer=pointer, depth=depth, cursor=cursor, limit=limit
        )

    def get_stream_table(
        self,
        job_id: str,
        *,
        pointer: str = "",
        depth: int = STREAM_TABLE_DEPTH,
        cursor: str | None = None,
        limit: int = DEFAULT_PAGE,
        display_units: str | None = None,
    ) -> Projection:
        """ADR 0068 (ST note §6.1): an ended job's stream table and energy summary, the
        `stream-table-v1` document computed on read from its replay bundle's revision, solution
        state, certificate and run manifest; any principal's job (`read` covers them all).
        Nothing is stored: two calls give the same document, and its `sha256` is the
        document's canonical hash.

        Parameters
        ----------
        job_id
            An ended job with a `replay_bundle` output.
        pointer
            A JSON pointer into the document (`/streams` to page the streams); the whole
            document when empty.
        depth, cursor, limit
            Bounds of the projection, and the cursor of its next page.
        display_units
            A display preference (ADR 0075 D7.3, ADR 0019 Amendment 17), resolved against the
            project's declared ambient pressure: each converted number gains a `display` item
            beside it and the root echoes the preference; the SI members are unchanged, and the
            `sha256` is the displayed document's.

        Returns
        -------
        Projection
            The value at `pointer`, `subject_id` `stream-table:<job_id>`.

        Raises
        ------
        ApplicationError
            `not_found` for an unknown job, a job without a replay bundle, or a bundle missing a
            member the report reads (MSG's member detail, as `get_artifact`'s); `not_ready`
            before the job ends; `unsupported` when the revision's basis cannot be evaluated in
            this installation (`basis_unavailable(<id>)`, with its `hint`); `internal_error` when
            the bundle's members are inconsistent; `invalid_request` or `unsupported` for a
            `display_units` refused by ADR 0075 D9.
        """
        return self._artifacts.get_stream_table(
            job_id,
            StreamTableQuery(
                pointer=pointer,
                depth=depth,
                cursor=cursor,
                limit=limit,
                display_units=display_units,
            ),
        )

    def list_audit(
        self,
        *,
        principal_id: str | None = None,
        operation: str | None = None,
        order: AuditOrder = "ascending",
        cursor: str | None = None,
        limit: int = 50,
    ) -> Page[AuditRecord]:
        """ADR 0019 Amendment 3 (A3.3; M06 design note §4.3): the project's audit rows — every
        effect and every refusal — by `seq`, optionally of one principal and one operation, each
        `allowed` row with the ledger's idempotency key. `read`; another principal's rows, or all
        principals' (`principal_id` omitted), need `policy` as well (`cancel_job`'s rule). The
        cursor is `{order, seq}`; one issued for the other order is refused at `/cursor`."""
        return self._inspection.list_audit(
            principal_id=principal_id,
            operation=operation,
            order=order,
            cursor=cursor,
            limit=limit,
        )

    def explain(self, code: str) -> MessageEntry:
        """ADR 0058 D7 (MSG §3.5, §4.9): the message-catalogue entry `code` — its display
        templates, params, gap, see-also, rendered examples, docs URL and the catalogue's digest.
        `read`; it reads no project state. An unknown code is refused `not_found` with
        `detail {code, suggestions}`: up to five keys within edit distance 3, case-insensitively."""
        return self._inspection.explain(code)

    def list_capabilities(
        self,
        *,
        kind: str | Sequence[str] | None = None,
        id_prefix: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CapabilityPage:
        """ADR 0060 D11 (ADR 0019 Amendment 7): a page of the process registry's descriptors —
        each declared and computed field (D2), sorted by (kind, id, version key) — of `kind` (one
        or several) whose id starts with `id_prefix`. `read`; it reads the registry, not the
        project. A cursor this list did not issue is refused `invalid_request`, as is any argument
        the operation's request schema refuses (rule C1; F1 review SF-1)."""
        return self._inspection.list_capabilities(
            kind=kind, id_prefix=id_prefix, cursor=cursor, limit=limit
        )

    def check_admission(
        self,
        *,
        pair: Mapping[str, Any] | None = None,
        revision: Mapping[str, Any] | None = None,
    ) -> AdmissionReport:
        """ADR 0060 D11 (ADR 0019 Amendment 7): D5's verdict on a (unit, method, definition)
        pair of the process registry, versions defaulting to the highest registered and the
        definition to the unit's one `conn:` requirement. `read`; it reads the registry, not the
        project. An unknown id is `not_found` with `detail.suggestions`. The draft form
        (`revision`, a schema_version 1 document) takes one pair per unit instance on the
        property method its component set selects and `nTP-v1`."""
        return self._validation.check_admission(pair=pair, revision=revision)

    def artifact_bytes(self, artifact_id: str) -> bytes:
        """§4.3, §10.4: an artifact file's bytes exactly as stored — the raw export (Python, CLI,
        HTTP; never MCP). A bundle is a directory, exported member by member. `read`.

        Parameters
        ----------
        artifact_id
            A file artifact, for example `<bundle id>/solution-state.json`.

        Returns
        -------
        bytes
            The file's bytes as stored.
        """
        return self._artifacts.artifact_bytes(artifact_id)

    def audit_refusal(self, operation: str, code: ApiErrorCode) -> None:
        """§10.7 for a request refused before it reached a method — by `operations.dispatch`,
        for its canonical form, its schema or a reserved key."""
        self._inspection.audit_refusal(operation, code)

    # --------------------------------------------------------------- the transaction steps


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


if TYPE_CHECKING:
    from openflowsheet.application.contract import Application

    def _conforms(app: LocalApplication) -> Application:
        """ADR 0076 I-11: mypy checks that `LocalApplication` implements §2.1's `Application`."""
        return app
