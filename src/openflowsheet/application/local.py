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

import base64
import binascii
import copy
import json
import math
import os
import shutil
import sqlite3
import tempfile
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final, Literal, NoReturn, Self, get_args

from openflowsheet.application import validation
from openflowsheet.application.admission import (
    active_jobs_refusal,
    admit_experiment,
    admit_reproduce,
    admit_solve,
    admit_surrogate_study,
    resolve_policies,
)
from openflowsheet.application.authz import (
    LOCAL_OWNER,
    PolicyFile,
    StaticPolicy,
    authenticate,
    authorize,
)
from openflowsheet.application.contract import ApplicationError, Page, Projection, api_error
from openflowsheet.application.jobs.executor import InlineExecutor, ProcessExecutor
from openflowsheet.application.jobs.model import JOB_STATUSES, TERMINAL_STATUSES, JobStatus
from openflowsheet.application.jobs.runner import RunContext, bundle_rows
from openflowsheet.application.policies import APPLICATION_POLICIES, DEFAULT_POLICY_ID
from openflowsheet.application.projection import (
    DEFAULT_DEPTH,
    DEFAULT_PAGE,
    MAX_PAGE,
    check_view_arguments,
    project,
)
from openflowsheet.application.revision_binding import (
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    ModelSignature,
    PinColumn,
    pin_encodings,
)
from openflowsheet.application.revision_run import Route, route_structure, select_route
from openflowsheet.application.revisions import Revision
from openflowsheet.application.store import (
    IMPORTS_DIR,
    STORE_SCHEMA,
    ActiveJobLimitError,
    ArtifactRow,
    AuditEntry,
    IdempotencyKeyReusedError,
    LedgerRow,
    ProjectStore,
)
from openflowsheet.application.transactions import (
    EditPathError,
    apply_edits,
    revision_diff,
    semantic_diff,
)
from openflowsheet.application.types import (
    ApiError,
    ApiErrorCode,
    AuditOrder,
    AuditRecord,
    CapabilityReference,
    Change,
    DocumentSchemaError,
    EffectiveBudgets,
    ExecutorSettings,
    ExperimentBody,
    Job,
    JobEvent,
    JobRequest,
    JobResult,
    JobWait,
    ModelRegistryView,
    ProjectPolicy,
    ProjectSummary,
    ReplayPolicy,
    ReproduceBody,
    RevisionSummary,
    RunResult,
    SemanticDiff,
    ServerInfo,
    SolveBody,
    SubmitResult,
    SurrogateStudyBody,
    TransactionResult,
    _replay_report_build,
    validate_document,
)
from openflowsheet.application.validation import Task, ValidationReport
from openflowsheet.canonical import canonical_json, document_sha256, first_noncanonical
from openflowsheet.run.bundle import MANIFEST_NAME
from openflowsheet.run.replay import ReplayReport

Executor = Literal["inline", "process"]
TASKS: tuple[str, ...] = get_args(Task)
#: §4.2: `wait_job` polls the store this often.
WAIT_POLL_S: Final[float] = 0.1
#: §11.4: page sizes — job lists as arrays (default 50, at most 200), events (100, at most 500).
MAX_JOB_PAGE: Final[int] = 200
#: ADR 0019 Amendment 3 (A3.3): `list_audit`'s orders, and its `operation` filter's length bound.
AUDIT_ORDERS: Final[tuple[str, ...]] = ("ascending", "descending")
_AUDIT_OPERATION_LIMIT: Final[int] = 128
MAX_EVENT_PAGE: Final[int] = 500


class LocalApplication:
    """One project, opened by one owner. Construct through `create`, `open` or `in_memory`."""

    def __init__(
        self,
        store: ProjectStore,
        *,
        owner_instance: str,
        policy: PolicyFile | StaticPolicy,
        capability: CapabilityReference | None,
    ) -> None:
        self._store = store
        self._policy = policy
        self._capability = capability
        self.owner_instance = owner_instance
        self.recovered: tuple[str, ...] = ()
        self._executor: InlineExecutor | ProcessExecutor = InlineExecutor()
        #: An in-memory project's files (bundles, imports) live in a directory of its own,
        #: removed on `close`.
        self._scratch: tempfile.TemporaryDirectory[str] | None = None

    # ------------------------------------------------------------------------- construction

    @classmethod
    def create(
        cls, directory: str | os.PathLike[str], *, project_id: str | None = None
    ) -> LocalApplication:
        """A new project in `directory` (absent or empty), opened by the local owner."""
        ProjectStore.create(
            Path(directory),
            project_id=project_id if project_id is not None else f"project-{uuid.uuid4().hex[:12]}",
        ).close()
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
        """
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
                process.start(application._context(), policy.current().executor)
            except BaseException:
                application.close()
                raise
            application._executor = process
        return application

    @classmethod
    def in_memory(cls) -> LocalApplication:
        """SQLite `:memory:`, inline execution only, the local owner only; nothing survives."""
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
        against the current policy on every call, like any other (`_caller`), so a revocation
        takes effect on the next call. The result is never closed; its owner is.
        """
        capability = authenticate(self._policy.current(), token)
        if capability is None:
            return None
        view = copy.copy(self)
        view._capability = capability
        return view

    def close(self) -> None:
        """Shut the executor down (§9.3), then release the store and the owner lock."""
        self._executor.shutdown()
        self._store.close()
        if self._scratch is not None:
            self._scratch.cleanup()
            self._scratch = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------------------ accessors

    @property
    def store(self) -> ProjectStore:
        return self._store

    @property
    def project_id(self) -> str:
        return self._store.project_id

    @property
    def principal_id(self) -> str:
        return (self._capability or LOCAL_OWNER).principal_id

    @property
    def capability_id(self) -> str:
        return (self._capability or LOCAL_OWNER).capability_id

    @property
    def policy(self) -> ProjectPolicy:
        """The project policy in force now (hot-reloaded)."""
        return self._policy.current()

    @property
    def executor(self) -> InlineExecutor | ProcessExecutor:
        """The executor this owner runs its jobs on (its test hooks are Python-only)."""
        return self._executor

    @property
    def files_root(self) -> Path:
        """The directory `jobs/` and `imports/` live under: the project's, or an in-memory
        project's scratch directory."""
        if self._store.directory is not None:
            return self._store.directory
        if self._scratch is None:
            self._scratch = tempfile.TemporaryDirectory(prefix="openflowsheet-")
        return Path(self._scratch.name)

    def _context(self) -> RunContext:
        return RunContext(
            store=self._store, root=self.files_root, owner_instance=self.owner_instance
        )

    # ---------------------------------------------------------------------- authorization

    def _caller(self, operation: str) -> CapabilityReference:
        """The caller's capability as the current policy states it; 401 if it is gone."""
        if self._capability is None:
            return LOCAL_OWNER
        for capability in self._policy.current().capabilities:
            if (
                capability.capability_id == self._capability.capability_id
                and capability.token_sha256 == self._capability.token_sha256
                and capability.token_sha256 is not None
            ):
                return capability
        return self._refuse(
            "unauthenticated",
            "this capability is not in the project policy (revoked or never granted)",
            operation=operation,
        )

    def _authorize(
        self,
        operation: str,
        *,
        target_principal: str | None = None,
        request_sha256: str | None = None,
    ) -> CapabilityReference:
        """§10.1 for this call; a refusal is audited and raised."""
        caller = self._caller(operation)
        decision = authorize(caller, operation, target_principal)
        if not decision.allowed:
            assert decision.code is not None
            self._refuse(
                decision.code,
                decision.message,
                operation=operation,
                request_sha256=request_sha256,
                required=list(decision.required),
            )
        return caller

    def _refuse(
        self,
        code: ApiErrorCode,
        message: str,
        *,
        operation: str,
        request_sha256: str | None = None,
        **detail: Any,
    ) -> NoReturn:
        """§10.7: audit a refusal of `operation`, then raise it."""
        self._audit_refusal(operation, code, request_sha256)
        raise api_error(code, message, **detail)

    def _audit_refusal(self, operation: str, code: str, request_sha256: str | None) -> None:
        self._store.record_audit(
            AuditEntry(
                principal_id=self.principal_id,
                capability_id=self.capability_id,
                operation=operation,
                outcome="refused",
                code=code,
                request_sha256=request_sha256,
            )
        )

    # -------------------------------------------------------------------- Application (frozen)

    def validate(self, revision_id: str, task: Task) -> ValidationReport:
        """§4.2: the stored revision's validation report for `task`; no side effects. `read`."""
        self._authorize("validate")
        if task not in TASKS:
            self._refuse(
                "invalid_request",
                f"task is one of {list(TASKS)}",
                operation="validate",
                pointer="/task",
            )
        if task == "optimization":
            # U05 (T08 review 2, Ruling 1): no optimization formulation is checked in v0.1, so no
            # `READY_FOR_OPTIMIZATION`; refused before the revision is read.
            self._refuse(
                "unsupported",
                "task_unsupported(optimization)",
                operation="validate",
                pointer="/task",
            )
        with self._store.reading() as connection:
            revision = self._store.get_revision(connection, revision_id)
        if revision is None:
            self._refuse(
                "not_found", "no such revision", operation="validate", revision_id=revision_id
            )
        return validation.validate(revision.as_document(), task)

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
        """
        operation = "commit_change"
        caller = self._authorize(operation)
        request = change.as_change_set(expected_revision, idempotency_key)
        rejected = self._check_request(request, operation, idempotency_key)
        if rejected is not None:
            return rejected
        request_sha256 = document_sha256(request)
        principal_id = caller.principal_id
        store = self._store

        with store.reading() as connection:
            prior = store.ledger_lookup(connection, principal_id, operation, idempotency_key)
            head = store.head(connection)
        if prior is not None:
            return self._replayed(prior, request_sha256, idempotency_key)
        if expected_revision != head:
            return _conflict(expected_revision, head, idempotency_key)

        prepared = self._prepare(change, expected_revision, idempotency_key, operation)
        if isinstance(prepared, TransactionResult):
            return prepared

        revision = prepared.revision
        result: TransactionResult | None = None
        with store.writing() as connection:
            prior = store.ledger_lookup(connection, principal_id, operation, idempotency_key)
            actual = store.head(connection)
            taken = store.get_revision(connection, revision.revision_id) is not None
            if prior is None and actual == expected_revision and not taken:
                store.commit_revision(
                    connection,
                    revision,
                    principal_id=principal_id,
                    capability_id=caller.capability_id,
                    policy_sha256=self._policy.current().policy_sha256,
                )
                invalidations = (
                    tuple(
                        f"run-{job_id}"
                        for job_id in store.solve_jobs_for_revision(connection, expected_revision)
                    )
                    if expected_revision is not None
                    else ()
                )
                result = TransactionResult(
                    status="committed",
                    revision_id=revision.revision_id,
                    validation=prepared.report,
                    diff=prepared.diff,
                    invalidations=invalidations,
                    idempotency_key=idempotency_key,
                )
                store.ledger_insert(
                    connection,
                    principal_id,
                    operation,
                    idempotency_key,
                    request_sha256,
                    result.as_document(),
                )
                store.audit(
                    connection,
                    AuditEntry(
                        principal_id=principal_id,
                        capability_id=caller.capability_id,
                        operation=operation,
                        outcome="allowed",
                        request_sha256=request_sha256,
                        effect=f"revision:{revision.revision_id}",
                    ),
                )
        if result is not None:
            return result
        # Another writer got in between the snapshot and the lock; say which way it moved.
        if prior is not None:
            return self._replayed(prior, request_sha256, idempotency_key)
        if actual != expected_revision:
            return _conflict(expected_revision, actual, idempotency_key)
        return self._rejected(
            operation,
            idempotency_key,
            "invalid_request",
            f"revision id {revision.revision_id!r} is taken; a revision is never replaced",
            pointer="/new_revision_id",
            reason="revision_id_taken",
        )

    def solve(self, revision_id: str, policy_id: str) -> RunResult:
        """§4.2: `submit_job` with a fresh `auto:` key, `wait_job` until it ends (no time-out),
        then `get_job_result(...).run_result`. Needs `execute`; a refusal at submission is raised.
        `policy_id` may be `"default"`, the route's registered policy (R2.3)."""
        caller = self._authorize("solve")
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
        caller = self._authorize(operation)
        if not isinstance(policy, ReplayPolicy):
            self._refuse("invalid_request", "policy is a ReplayPolicy", operation=operation)
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
        caller = self._authorize("submit_job")
        return self._submit(request, caller, "submit_job")

    def get_job(self, job_id: str) -> Job:
        """§4.2: any job of the project (`read` covers every principal's jobs)."""
        self._authorize("get_job")
        return self._job(job_id, "get_job")

    def list_jobs(
        self, *, status: JobStatus | None = None, cursor: str | None = None, limit: int = 50
    ) -> Page[Job]:
        """§4.2, §11.4: the project's jobs in acceptance order, by ordinal cursor."""
        operation = "list_jobs"
        self._authorize(operation)
        if status is not None and status not in JOB_STATUSES:
            self._refuse(
                "invalid_request",
                f"status is one of {list(JOB_STATUSES)}",
                operation=operation,
                pointer="/status",
            )
        self._check_limit(limit, MAX_JOB_PAGE, operation)
        after = self._decode_cursor(cursor, operation)
        rows, more = self._store.list_jobs(status=status, after_ordinal=after, limit=limit)
        next_cursor = _encode_cursor(rows[-1][0]) if more else None
        return Page(items=tuple(job for _, job in rows), next_cursor=next_cursor)

    def list_job_events(
        self, job_id: str, *, after_sequence: int = -1, limit: int = 100
    ) -> Page[JobEvent]:
        """§4.2, §11.4: a job's events after `after_sequence`; the next cursor is the last
        sequence returned, to pass back as `after_sequence`."""
        operation = "list_job_events"
        self._authorize(operation)
        self._check_limit(limit, MAX_EVENT_PAGE, operation)
        self._check_sequence(after_sequence, operation)
        found = self._store.job_events_after(job_id, after_sequence, limit + 1)
        if found is None:
            self._refuse("not_found", "no such job", operation=operation, job_id=job_id)
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
        self._authorize(operation)
        self._check_sequence(after_sequence, operation)
        if (
            isinstance(timeout_s, bool)
            or not isinstance(timeout_s, int | float)
            or math.isnan(timeout_s)
            or timeout_s < 0
        ):
            self._refuse(
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
        caller = self._authorize(operation, target_principal=self.principal_id)
        job = self._job(job_id, operation)
        caller = self._authorize(operation, target_principal=job.principal_id)
        outcome = self._store.request_cancel(
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
            self._executor.signal_cancel(job_id)
        return self._job(job_id, operation)

    def get_job_result(self, job_id: str) -> JobResult:
        """§4.2 as amended by R4: `{operation, run_result, replay_report, error}` of an ended
        job; `not_ready` before it ends."""
        self._authorize("get_job_result")
        return self._result(job_id, "get_job_result")

    # ------------------------------------------------------------------------- the job steps

    def _submit(
        self, request: JobRequest, caller: CapabilityReference, operation: str
    ) -> SubmitResult:
        document = request.as_document()
        # As `dispatch` orders them (§4.3): a non-canonical value is named as such, not as a
        # schema error.
        pointer = first_noncanonical(document)
        if pointer is not None:
            self._refuse(
                "document_not_canonical",
                "a value has no canonical JSON form (NaN, an infinity, an integer beyond 2^53 that "
                "is not a binary64's canonical spelling, or not JSON at all)",
                operation=operation,
                pointer=pointer,
            )
        try:
            validate_document("job.schema.json#/$defs/job_request", document)
        except DocumentSchemaError as error:
            self._refuse(
                "invalid_request", error.message, operation=operation, pointer=error.pointer
            )
        request_sha256 = request.request_sha256
        store = self._store
        with store.reading() as connection:
            prior = store.ledger_lookup(
                connection, caller.principal_id, "submit_job", request.idempotency_key
            )
        if prior is not None:
            return self._replayed_job(prior, request_sha256, operation)
        budgets = self._admit(request, caller, operation, request_sha256)
        try:
            job, replayed = store.accept_job(
                request,
                principal_id=caller.principal_id,
                capability_id=caller.capability_id,
                # §5.5: the project-policy document hash at acceptance.
                policy_sha256=self._policy.current().policy_sha256,
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
            self._refuse_error(refused, operation, request_sha256)
        if not replayed:
            self._executor.run(self._context(), job.job_id)
            job = self._job(job.job_id, operation)
        return SubmitResult(job=job, replayed=replayed)

    def _replayed_job(self, prior: LedgerRow, request_sha256: str, operation: str) -> SubmitResult:
        """§7: the existing job, as it is now; a different request under the key is refused."""
        if prior.request_sha256 != request_sha256:
            self._refuse_key_reused(prior.request_sha256, request_sha256, operation)
        return SubmitResult(job=self._job(str(prior.result), operation), replayed=True)

    def _refuse_key_reused(self, original: str, request_sha256: str, operation: str) -> NoReturn:
        self._refuse(
            "idempotency_key_reused",
            "this idempotency key was used with a different job request; use a new key for a "
            "new job",
            operation=operation,
            request_sha256=request_sha256,
            original_request_sha256=original,
        )

    def _admit(
        self,
        request: JobRequest,
        caller: CapabilityReference,
        operation: str,
        request_sha256: str,
    ) -> EffectiveBudgets:
        """§5.3's semantic admission; a refusal creates no job and no ledger row, and is
        audited. The effective budgets the job will run under."""
        store = self._store
        active = store.active_job_count(caller.principal_id)
        body = request.body
        if isinstance(body, SolveBody):
            with store.reading() as connection:
                revision = store.get_revision(connection, body.revision_id)
            admission = admit_solve(
                body.revision_id,
                revision.as_document() if revision is not None else None,
                body,
                budgets=request.budgets,
                limits=caller.limits,
                active_jobs=active,
            )
            if isinstance(admission, ApiError):
                self._refuse_error(admission, operation, request_sha256)
            return EffectiveBudgets(
                wall_time_s=admission.wall_time_s,
                max_property_calls=admission.policy.max_property_calls,
            )
        if isinstance(body, ExperimentBody):
            admitted = admit_experiment(
                body, budgets=request.budgets, limits=caller.limits, active_jobs=active
            )
            if isinstance(admitted, ApiError):
                self._refuse_error(admitted, operation, request_sha256)
            # R-233: an experiment's property calls are its own, never a solve's budget.
            return EffectiveBudgets(wall_time_s=admitted[1], max_property_calls=None)
        if isinstance(body, SurrogateStudyBody):
            study = admit_surrogate_study(
                body, budgets=request.budgets, limits=caller.limits, active_jobs=active
            )
            if isinstance(study, ApiError):
                self._refuse_error(study, operation, request_sha256)
            # R-233 again: a study's experiments are experiments; their calls are their own.
            return EffectiveBudgets(wall_time_s=study, max_property_calls=None)
        archive = store.artifact(body.bundle_artifact_id)
        wall_time_s = admit_reproduce(
            archive.kind if archive is not None else None,
            body,
            budgets=request.budgets,
            limits=caller.limits,
            active_jobs=active,
        )
        if isinstance(wall_time_s, ApiError):
            self._refuse_error(wall_time_s, operation, request_sha256)
        return EffectiveBudgets(wall_time_s=wall_time_s, max_property_calls=None)

    def _job(self, job_id: str, operation: str) -> Job:
        job = self._store.get_job(job_id)
        if job is None:
            self._refuse("not_found", "no such job", operation=operation, job_id=job_id)
        return job

    def _wait(self, job_id: str, after_sequence: int, timeout_s: float, operation: str) -> JobWait:
        deadline = time.monotonic() + timeout_s
        while True:
            found = self._store.job_events_after(job_id, after_sequence, 100)
            if found is None:
                self._refuse("not_found", "no such job", operation=operation, job_id=job_id)
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

    def _result(self, job_id: str, operation: str) -> JobResult:
        job = self._job(job_id, operation)
        if job.status not in TERMINAL_STATUSES:
            self._refuse(
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
                run_result=self._run_result(job),
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
            worker = self._store.worker_result(job.job_id)
            study = worker.get("study") if isinstance(worker, Mapping) else None
            return JobResult(
                operation="surrogate_study",
                run_result=None,
                replay_report=None,
                error=job.error,
                surrogate_study=study,
            )
        report = None
        for output in job.outputs:
            if output.kind == "replay_report":
                report = _replay_report_build(json.loads(self._artifact_path(output).read_bytes()))
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
        answer: dict[str, Any] = json.loads(self._artifact_path(chosen).read_bytes())
        return answer

    def _run_result(self, job: Job) -> RunResult:
        """§5.7, read from what the job produced: the resolution and run facts its runner
        recorded (`worker_result.run`) and its outputs; a job that never resolved its request
        (cancelled while queued) has its resolution re-derived — a pure function of the stored
        revision and the registries — and no run facts."""
        body = job.request.body
        assert isinstance(body, SolveBody)
        with self._store.reading() as connection:
            revision = self._store.get_revision(connection, body.revision_id)
        assert revision is not None
        worker = self._store.worker_result(job.job_id)
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
        )

    def _resolution(self, revision: Revision, body: SolveBody) -> dict[str, Any]:
        from openflowsheet.run.manifest import policy_sha256

        route = select_route(revision.as_document())
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

    def _artifact_path(self, output: Any) -> Path:
        row = self._store.artifact(output.artifact_id)
        assert row is not None, output.artifact_id
        return self.files_root / row.relpath

    def _import_bundle(self, source: Path, operation: str) -> str:
        """§4.2 `reproduce`'s import: copy the regular files of `source` (no symlink followed)
        into `imports/<ordinal>/` and register the copy and its known members."""
        if not source.is_dir():
            self._refuse(
                "not_found",
                "no bundle directory at this path",
                operation=operation,
                pointer="/bundle_path",
            )
        manifest = source / MANIFEST_NAME
        if manifest.is_symlink() or not manifest.is_file():
            self._refuse(
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
        bundle, members = bundle_rows(
            self.files_root, target, f"import-{ordinal:06d}:bundle", None, producer=False
        )
        with self._store.writing() as connection:
            self._store.register_artifacts(connection, [bundle, *members])
        return bundle.artifact_id

    def _check_limit(self, limit: int, maximum: int, operation: str) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
            self._refuse(
                "invalid_request",
                f"limit is an integer from 1 to {maximum}",
                operation=operation,
                pointer="/limit",
            )

    def _check_sequence(self, after_sequence: int, operation: str) -> None:
        if (
            isinstance(after_sequence, bool)
            or not isinstance(after_sequence, int)
            or after_sequence < -1
        ):
            self._refuse(
                "invalid_request",
                "after_sequence is an integer >= -1",
                operation=operation,
                pointer="/after_sequence",
            )

    def _decode_cursor(self, cursor: str | None, operation: str) -> int:
        if cursor is None:
            return 0
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        except (ValueError, TypeError, binascii.Error):
            decoded = None
        ordinal = decoded.get("ordinal") if isinstance(decoded, dict) else None
        if (
            not isinstance(decoded, dict)
            or set(decoded) != {"ordinal"}
            or isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or ordinal < 0
        ):
            self._refuse(
                "invalid_request",
                "cursor is not one this list issued",
                operation=operation,
                pointer="/cursor",
            )
        return int(ordinal)

    def _refuse_error(
        self, error: ApiError, operation: str, request_sha256: str | None
    ) -> NoReturn:
        """§10.7: audit a typed refusal, then raise it as it is."""
        self._audit_refusal(operation, error.code, request_sha256)
        raise ApplicationError(error)

    # ----------------------------------------------------------------- Inspection (W2b part)

    def preview_change(self, change: Change, expected_revision: str | None) -> TransactionResult:
        """§4.2: `commit_change`'s steps 2 and 4–6 — no head check, no write, no ledger. `read`.

        The validation report names the id the commit would assign, so a preview and the commit
        that follows it with nothing in between report the same thing.
        """
        operation = "preview_change"
        self._authorize(operation)
        # The key is `commit_change`'s, not the preview's; a placeholder satisfies the schema.
        rejected = self._check_request(
            change.as_change_set(expected_revision, "preview"), operation, ""
        )
        if rejected is not None:
            return rejected
        prepared = self._prepare(change, expected_revision, "", operation)
        if isinstance(prepared, TransactionResult):
            return prepared
        return TransactionResult(
            status="previewed",
            revision_id=None,
            validation=prepared.report,
            diff=prepared.diff,
        )

    # ------------------------------------------------------------ Inspection (W5a, §4.2, §11.4)

    def get_project(self) -> ProjectSummary:
        """§4.2: the project, its head and counts, its solve policies, and the caller as its
        credential makes it. `read`."""
        from openflowsheet import __version__
        from openflowsheet.run.manifest import policy_sha256

        caller = self._authorize("get_project")
        store = self._store
        with store.reading() as connection:
            head = store.head(connection)
            revision_count = store.revision_count(connection)
            # Every status is named; a status a newer producer wrote is kept, not dropped (J5).
            job_counts = {status: 0 for status in JOB_STATUSES} | store.job_counts(connection)
        return ProjectSummary(
            project_id=self.project_id,
            head=head,
            revision_count=revision_count,
            job_counts=job_counts,
            solve_policies=tuple(
                (policy_id, policy_sha256(policy))
                for policy_id, policy in sorted(APPLICATION_POLICIES.items())
            ),
            default_policy_id=DEFAULT_POLICY_ID,
            principal_id=caller.principal_id,
            capability_id=caller.capability_id,
            rights=caller.rights,
            limits=caller.limits,
            # No commit is read at run time: the server runs no subprocess for it.
            server=ServerInfo(
                package_version=__version__, git_commit=None, store_schema=STORE_SCHEMA
            ),
        )

    def list_models(self) -> ModelRegistryView:
        """§4.2: each model id in `MODEL_BUILDERS` with its declarative `ModelSignature`; nothing
        is constructed ("inspect manifests without executing them"). `read`."""
        self._authorize("list_models")
        return ModelRegistryView(
            models=tuple(
                _model_view(MODEL_SIGNATURES[model_id]) for model_id in sorted(MODEL_BUILDERS)
            )
        )

    def list_revisions(
        self, *, cursor: str | None = None, limit: int = 50
    ) -> Page[RevisionSummary]:
        """§4.2, §11.4: the project's revisions in commit order, by ordinal cursor. `read`."""
        operation = "list_revisions"
        self._authorize(operation)
        self._check_limit(limit, MAX_PAGE, operation)
        after = self._decode_cursor(cursor, operation)
        rows, more = self._store.list_revisions(after_ordinal=after, limit=limit)
        next_cursor = _encode_cursor(rows[-1][0]) if more else None
        return Page(items=tuple(summary for _, summary in rows), next_cursor=next_cursor)

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
        operation = "get_revision"
        self._authorize(operation)
        self._check_view(operation, pointer, depth, cursor, limit)
        document = self._revision(revision_id, operation).as_document()
        return self._project(
            operation,
            document,
            revision_id,
            document_sha256(document),
            pointer,
            depth,
            cursor,
            limit,
        )

    def diff_revisions(self, from_revision: str, to_revision: str) -> SemanticDiff:
        """§4.2: the semantic diff (content paths added, removed, changed; the title and other
        descriptive members excluded) from one stored revision to another, with its
        `elements` (ADR 0019 Amendment 3, A3.2: the items of `instances`, `connections` and
        `specifications` that differ, paired by id). `read`."""
        operation = "diff_revisions"
        self._authorize(operation)
        before = self._revision(from_revision, operation)
        after = self._revision(to_revision, operation)
        return revision_diff(before.document, after.document)

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
        `revision_run.route_structure`, projected. `read`."""
        operation = "inspect_structure"
        self._authorize(operation)
        self._check_view(operation, pointer, depth, cursor, limit)
        revision = self._revision(revision_id, operation)
        document = route_structure(revision.as_document())
        return self._project(
            operation,
            document,
            revision_id,
            document_sha256(document),
            pointer,
            depth,
            cursor,
            limit,
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
        """
        operation = "get_artifact"
        self._authorize(operation)
        self._check_view(operation, pointer, depth, cursor, limit)
        row = self._artifact_row(artifact_id, operation)
        if row.kind == "replay_bundle":
            members = self._store.artifact_children(row.artifact_id)
            manifest = [member for member in members if member.name == MANIFEST_NAME]
            manifest_path = (
                self.files_root / manifest[0].relpath
                if manifest
                else self.files_root / row.relpath / MANIFEST_NAME
            )
            document: Any = {
                "manifest": _file_document(manifest_path),
                "files": [
                    {
                        "name": member.name,
                        "kind": member.kind,
                        "artifact_id": member.artifact_id,
                        "sha256": member.sha256,
                        "size_bytes": member.size_bytes,
                    }
                    for member in members
                ],
            }
        else:
            document = _file_document(self.files_root / row.relpath)
        return self._project(
            operation, document, artifact_id, row.sha256, pointer, depth, cursor, limit
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
        name = "list_audit"
        self._authorize(name, target_principal=principal_id)
        if principal_id is not None and not isinstance(principal_id, str):
            self._refuse(
                "invalid_request", "principal_id is an id", operation=name, pointer="/principal_id"
            )
        if operation is not None and (
            not isinstance(operation, str) or not 1 <= len(operation) <= _AUDIT_OPERATION_LIMIT
        ):
            self._refuse(
                "invalid_request",
                f"operation is a string of 1 to {_AUDIT_OPERATION_LIMIT} characters",
                operation=name,
                pointer="/operation",
            )
        if order not in AUDIT_ORDERS:
            self._refuse(
                "invalid_request",
                f"order is one of {list(AUDIT_ORDERS)}",
                operation=name,
                pointer="/order",
            )
        self._check_limit(limit, MAX_PAGE, name)
        after = self._decode_audit_cursor(cursor, order, name)
        rows, more = self._store.list_audit(
            principal_id=principal_id,
            operation=operation,
            descending=order == "descending",
            after_seq=after,
            limit=limit,
        )
        next_cursor = _encode_audit_cursor(order, rows[-1].seq) if more else None
        return Page(items=tuple(rows), next_cursor=next_cursor)

    def _decode_audit_cursor(self, cursor: str | None, order: str, operation: str) -> int | None:
        """`list_audit`'s cursor, `{order, seq}`, as the `seq` to continue after; `None` for the
        first page. A cursor of the other order, or one this list did not issue, is refused."""
        if cursor is None:
            return None
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        except (ValueError, TypeError, binascii.Error):
            decoded = None
        seq = decoded.get("seq") if isinstance(decoded, dict) else None
        if (
            not isinstance(decoded, dict)
            or set(decoded) != {"order", "seq"}
            or decoded["order"] not in AUDIT_ORDERS
            or isinstance(seq, bool)
            or not isinstance(seq, int)
            or seq < 0
        ):
            self._refuse(
                "invalid_request",
                "cursor is not one this list issued",
                operation=operation,
                pointer="/cursor",
            )
        if decoded["order"] != order:
            self._refuse(
                "invalid_request",
                f"cursor was issued for order {decoded['order']!r}, not {order!r}",
                operation=operation,
                pointer="/cursor",
            )
        return int(seq)

    def artifact_bytes(self, artifact_id: str) -> bytes:
        """§4.3, §10.4: an artifact file's bytes exactly as stored — the raw export (Python, CLI,
        HTTP; never MCP). A bundle is a directory, exported member by member. `read`."""
        operation = "artifact_bytes"
        self._authorize(operation)
        row = self._artifact_row(artifact_id, operation)
        if row.kind == "replay_bundle":
            self._refuse(
                "unsupported",
                "a replay bundle is a directory; export its members, `<bundle id>/<file>`, one by "
                "one",
                operation=operation,
                artifact_id=artifact_id,
            )
        return (self.files_root / row.relpath).read_bytes()

    def audit_refusal(self, operation: str, code: ApiErrorCode) -> None:
        """§10.7 for a request refused before it reached a method — by `operations.dispatch`,
        for its canonical form, its schema or a reserved key."""
        self._audit_refusal(operation, code, None)

    def _revision(self, revision_id: str, operation: str) -> Revision:
        with self._store.reading() as connection:
            revision = self._store.get_revision(connection, revision_id)
        if revision is None:
            self._refuse(
                "not_found", "no such revision", operation=operation, revision_id=revision_id
            )
        return revision

    def _artifact_row(self, artifact_id: str, operation: str) -> ArtifactRow:
        row = self._store.artifact(artifact_id) if isinstance(artifact_id, str) else None
        if row is None:
            self._refuse(
                "not_found", "no such artifact", operation=operation, artifact_id=artifact_id
            )
        return row

    def _check_view(
        self, operation: str, pointer: object, depth: object, cursor: object, limit: object
    ) -> None:
        """§11.4's argument rules, before any document is read or built."""
        try:
            check_view_arguments(pointer, depth, cursor, limit)
        except ApplicationError as refused:
            self._refuse_error(refused.error, operation, None)

    def _project(
        self,
        operation: str,
        document: Any,
        subject_id: str,
        sha256: str,
        pointer: str,
        depth: int,
        cursor: str | None,
        limit: int,
    ) -> Projection:
        try:
            return project(
                document,
                subject_id=subject_id,
                sha256=sha256,
                pointer=pointer,
                depth=depth,
                cursor=cursor,
                limit=limit,
            )
        except ApplicationError as refused:
            self._refuse_error(refused.error, operation, None)

    # --------------------------------------------------------------- the transaction steps

    def _check_request(
        self, request: dict[str, Any], operation: str, idempotency_key: str
    ) -> TransactionResult | None:
        """Q29 first (a non-canonical value is `rejected`), then the ChangeSet schema (raised)."""
        pointer = first_noncanonical(request)
        if pointer is not None:
            return self._rejected(
                operation,
                idempotency_key,
                "document_not_canonical",
                "a value has no canonical JSON form (NaN, an infinity, an integer beyond 2^53 that "
                "is not a binary64's canonical spelling, or not JSON at all)",
                pointer=pointer,
            )
        try:
            validate_document("change-set.schema.json", request)
        except DocumentSchemaError as error:
            self._refuse(
                "invalid_request", error.message, operation=operation, pointer=error.pointer
            )
        return None

    def _prepare(
        self,
        change: Change,
        expected_revision: str | None,
        idempotency_key: str,
        operation: str,
    ) -> _Prepared | TransactionResult:
        """Steps 4–6 from one snapshot: the new document, its validation and its diff."""
        if change.task == "optimization":
            # U05 (T08 review 2, Ruling 1), as `validate` refuses it: no optimization formulation
            # is checked in v0.1. Audited, before the snapshot is read or anything is built.
            self._refuse(
                "unsupported",
                "task_unsupported(optimization)",
                operation=operation,
                pointer="/task",
            )
        store = self._store
        # A refusal is audited, and the audit writes; it is issued after the snapshot closes. An
        # in-memory store is one connection, where a write inside the open read would nest a
        # transaction (T07 review M2).
        refusal: tuple[ApiErrorCode, str, dict[str, Any]] | None = None
        revision_id = ""
        with store.reading() as connection:
            expected: Mapping[str, Any] = {}
            if expected_revision is not None:
                found = store.get_revision(connection, expected_revision)
                if found is None:
                    refusal = (
                        "not_found",
                        "the expected revision does not exist",
                        {"pointer": "/expected_revision"},
                    )
                else:
                    expected = found.document
            start = expected
            if refusal is None and change.restore_from is not None:
                restored = store.get_revision(connection, change.restore_from)
                if restored is None:
                    refusal = (
                        "not_found",
                        "the revision to restore from does not exist",
                        {"pointer": "/restore_from"},
                    )
                else:
                    start = restored.document
            if refusal is None and change.new_revision_id is not None:
                if store.get_revision(connection, change.new_revision_id) is not None:
                    refusal = (
                        "invalid_request",
                        f"revision id {change.new_revision_id!r} is taken; a revision is never "
                        "replaced",
                        {"pointer": "/new_revision_id", "reason": "revision_id_taken"},
                    )
                else:
                    revision_id = change.new_revision_id
            elif refusal is None:
                revision_id = _assigned_revision_id(store, connection)
        if refusal is not None:
            code, message, detail = refusal
            return self._rejected(operation, idempotency_key, code, message, **detail)
        try:
            built = apply_edits(start, change.edits)
        except EditPathError as error:
            return self._rejected(
                operation,
                idempotency_key,
                "invalid_request",
                str(error),
                pointer=f"/edits/{error.edit_index}/path",
                reason="edit_path_invalid",
                edit_index=error.edit_index,
                document_pointer=error.pointer,
            )
        # What is validated is exactly what is stored: the canonical document, read back.
        document = json.loads(canonical_json(built))
        revision = Revision(
            revision_id=revision_id, document=document, parent_revision=expected_revision
        )
        return _Prepared(
            revision=revision,
            report=validation.validate(revision.as_document(), change.task),
            diff=semantic_diff(expected, document),
        )

    def _replayed(
        self, prior: LedgerRow, request_sha256: str, idempotency_key: str
    ) -> TransactionResult:
        """§7: the original result, `replayed`; a different request under the key is refused."""
        if prior.request_sha256 != request_sha256:
            self._refuse(
                "idempotency_key_reused",
                "this idempotency key was used with a different change set; use a new key for a "
                "new change",
                operation="commit_change",
                request_sha256=request_sha256,
                original_request_sha256=prior.request_sha256,
            )
        return replace(TransactionResult._build(prior.result), status="replayed")

    def _rejected(
        self,
        operation: str,
        idempotency_key: str,
        code: ApiErrorCode,
        message: str,
        **detail: Any,
    ) -> TransactionResult:
        """A `rejected` domain result, audited as a refusal (§10.7)."""
        self._audit_refusal(operation, code, None)
        return TransactionResult(
            status="rejected",
            revision_id=None,
            validation=None,
            diff=None,
            idempotency_key=idempotency_key,
            error=ApiError(code=code, message=message, retryable=False, detail=detail),
        )


@dataclass(frozen=True)
class _Prepared:
    revision: Revision
    report: ValidationReport
    diff: SemanticDiff


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


def _conflict(expected: str | None, actual: str | None, idempotency_key: str) -> TransactionResult:
    return TransactionResult(
        status="conflict",
        revision_id=None,
        validation=None,
        diff=None,
        conflict={"expected": expected, "actual": actual},
        idempotency_key=idempotency_key,
    )


def _assigned_revision_id(store: ProjectStore, connection: sqlite3.Connection) -> str:
    """§5.2: `rev-<ordinal:06d>`, stepping past an id a caller already took by name."""
    ordinal = store.next_revision_ordinal(connection)
    while store.get_revision(connection, f"rev-{ordinal:06d}") is not None:
        ordinal += 1
    return f"rev-{ordinal:06d}"


def _model_view(signature: ModelSignature) -> dict[str, Any]:
    """§4.2 `list_models`: one signature as a document — ports (name, direction, multiplicity,
    kind), required and zero-only parameters, the pinned columns always read, and the one-of
    choices of pinned columns; each pin and option with the `specifications` that pin it, its
    `pin_encodings` (ruling round 6, B2 item 4; ADR 0019 Amendment 2)."""

    def pin(column: PinColumn) -> dict[str, Any]:
        return {
            "name": column.name,
            "quantity": column.quantity,
            "port": column.port,
            "specifications": [
                encoding.as_document() for encoding in pin_encodings(signature, column)
            ],
        }

    return {
        "model_id": signature.model_id,
        "ports": [
            {
                "name": port.name,
                "direction": port.direction,
                "multiplicity": port.multiplicity,
                "kind": port.kind,
            }
            for port in signature.ports
        ],
        "required": list(signature.required),
        "zero": list(signature.zero),
        "pins": [pin(column) for column in signature.pins],
        "choices": [
            {"name": choice.name, "options": [pin(option) for option in choice.options]}
            for choice in signature.choices
        ],
    }


def _unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    names = [name for name, _ in pairs]
    if len(set(names)) != len(names):
        raise ValueError("duplicate key")
    return dict(pairs)


def _file_document(path: Path) -> Any:
    """An artifact file as a document for `get_artifact`: its JSON when it holds a canonical JSON
    document — a `.json` name, a strict parse with no repeated key, every number canonical —
    else its text as a list of lines (a log, or an imported file that is not what its name says),
    decoded as UTF-8 with U+FFFD for what is not."""
    raw = path.read_bytes()
    if path.suffix == ".json":
        try:
            document = json.loads(raw, object_pairs_hook=_unique_members)
        except (ValueError, RecursionError):
            pass
        else:
            if first_noncanonical(document) is None:
                return document
    return raw.decode("utf-8", errors="replace").splitlines()


def _encode_audit_cursor(order: str, seq: int) -> str:
    """ADR 0019 Amendment 3 (A3.3): `list_audit`'s cursor, `base64url(canonical_json({"order":
    o, "seq": s}))` unpadded, `s` the `seq` of the last row returned."""
    encoded = base64.urlsafe_b64encode(canonical_json({"order": order, "seq": seq}))
    return encoded.decode("ascii").rstrip("=")


def _encode_cursor(ordinal: int) -> str:
    """§11.4: a list's cursor, `base64url(canonical_json({"ordinal": k}))` unpadded, `k` the
    ordinal of the last item returned."""
    encoded = base64.urlsafe_b64encode(canonical_json({"ordinal": ordinal}))
    return encoded.decode("ascii").rstrip("=")
