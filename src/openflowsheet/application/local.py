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
import os
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

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
from openflowsheet.application.errors import ApiErrorCode, api_error
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
    RunResult,
)
from openflowsheet.application.job_requests import (
    JobRequest,
)
from openflowsheet.application.job_service import JobService
from openflowsheet.application.jobs.executor import InlineExecutor, ProcessExecutor
from openflowsheet.application.jobs.model import JobStatus
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
from openflowsheet.application.revision_service import RevisionService
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.store import (
    ProjectStore,
)
from openflowsheet.application.store_records import (
    StoreError,
    coded_store_error,
)
from openflowsheet.application.transaction_types import Change, SemanticDiff, TransactionResult
from openflowsheet.application.validation_report import Task, ValidationReport
from openflowsheet.application.validation_service import ValidationService
from openflowsheet.registry import default_registry
from openflowsheet.run.replay import ReplayReport

Executor = Literal["inline", "process"]


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
        self._jobs = JobService(
            core, self._inspection, self._revisions, self._artifacts, self._validation
        )

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
        return self._jobs.solve(revision_id, policy_id)

    def reproduce(self, bundle_path: str | os.PathLike[str], policy: ReplayPolicy) -> ReplayReport:
        """§4.2: import the bundle at `bundle_path` (its regular files, no symlink followed) as
        `import-<ordinal>:bundle`, submit `reproduce` with a fresh `auto:` key, wait, and return
        the report. Needs `execute`. A job that ends without a report raises its error, or, when
        it has none (`cancelled`, `timed_out`), `not_ready` (§5.8 as amended by ruling round 4)."""
        return self._jobs.reproduce(bundle_path, policy)

    # ---------------------------------------------------------------------- JobControl (§4.1)

    def submit_job(self, request: JobRequest) -> SubmitResult:
        """§4.2: authorize `execute`; canonical form (Q29), then the schema; the ledger (§7);
        semantic admission (§5.3); accept (job, `accepted`, ledger row and audit row in one
        transaction); hand it to the executor. Returns the job as the executor leaves it —
        ended inline, queued or running under the process executor — or, same key, same request,
        the existing one with `replayed = true`."""
        return self._jobs.submit_job(request)

    def get_job(self, job_id: str) -> Job:
        """§4.2: any job of the project (`read` covers every principal's jobs)."""
        return self._jobs.get_job(job_id)

    def list_jobs(
        self, *, status: JobStatus | None = None, cursor: str | None = None, limit: int = 50
    ) -> Page[Job]:
        """§4.2, §11.4: the project's jobs in acceptance order, by ordinal cursor."""
        return self._jobs.list_jobs(status=status, cursor=cursor, limit=limit)

    def list_job_events(
        self, job_id: str, *, after_sequence: int = -1, limit: int = 100
    ) -> Page[JobEvent]:
        """§4.2, §11.4: a job's events after `after_sequence`; the next cursor is the last
        sequence returned, to pass back as `after_sequence`."""
        return self._jobs.list_job_events(job_id, after_sequence=after_sequence, limit=limit)

    def wait_job(
        self, job_id: str, *, after_sequence: int = -1, timeout_s: float = 20.0
    ) -> JobWait:
        """§4.2: return once the job has events after `after_sequence` (a cancellation request
        among them), once it has ended, or at `timeout_s` (in-process, `math.inf` waits for
        either); polls every 0.1 s. At most 100 events."""
        return self._jobs.wait_job(job_id, after_sequence=after_sequence, timeout_s=timeout_s)

    def cancel_job(self, job_id: str) -> Job:
        """§4.2: needs `execute`, and `policy` as well for another principal's job. A queued job
        ends `cancelled` at once; a running one is flagged and signalled, and stops at its next
        checkpoint; an ended one is returned as it is. Idempotent."""
        return self._jobs.cancel_job(job_id)

    def get_job_result(self, job_id: str, *, display_units: str | None = None) -> JobResult:
        """§4.2 as amended by R4: `{operation, run_result, replay_report, error}` of an ended
        job; `not_ready` before it ends. `display_units` (ADR 0075 D7.4, ADR 0019 Amendment 17)
        is a display preference, resolved against the project's declared ambient pressure: the
        result echoes it and every explanation it holds is rendered under it; its SI content is
        the result without it."""
        return self._jobs.get_job_result(job_id, display_units=display_units)

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


if TYPE_CHECKING:
    from openflowsheet.application.contract import Application

    def _conforms(app: LocalApplication) -> Application:
        """ADR 0076 I-11: mypy checks that `LocalApplication` implements §2.1's `Application`."""
        return app
