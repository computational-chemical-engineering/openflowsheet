"""The project store: one directory, one SQLite database (T07 design note §9.2–§9.3, D3).

A project is a directory holding `project.sqlite3` (WAL, `synchronous=FULL`, `busy_timeout` 30 s,
`foreign_keys` on), `project-policy.json`, `owners/`, `jobs/<job_id>/…` and `imports/<n>/…`. The
database holds revisions, the head, the idempotency ledger, jobs, their events, artifacts and the
audit log; bundles and other artifacts are files. Idempotency and job records therefore survive a
restart, and every CLI invocation shares one ledger.

**Writing rules.** Every write is one `BEGIN IMMEDIATE` transaction (`writing()`), so writers from
any mix of threads and processes are serialized by SQLite itself and a read-then-insert inside one
transaction cannot race. The next event sequence is `MAX(sequence) + 1` inside that transaction,
and the primary key makes a duplicate impossible. A file store opens a connection per unit of work,
so each connection belongs to one thread; an in-memory store has one connection behind a lock.
Documents are stored as their canonical JSON (ADR 0002), so what is stored is what is hashed.

**Ownership (§9.3).** Every `LocalApplication` instance holds an exclusive `flock` on
`owners/<owner_instance>.lock` for its lifetime; the kernel releases it when the process dies.
`recover` ends every non-terminal job whose owner's lock can be taken — its owner is dead —
`failed(owner_lost)`. A queued job never started, so no work is lost by ending it.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import sqlite3
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openflowsheet.application.revisions import Revision, content_hash
from openflowsheet.application.types import (
    LOCAL_OWNER_PRINCIPAL,
    ApiError,
    ArtifactRef,
    AuditRecord,
    EffectiveBudgets,
    ExecutorSettings,
    Job,
    JobEnding,
    JobEvent,
    JobRequest,
    Progress,
    ProjectPolicy,
    RevisionSummary,
)

# §5.1's timestamp has one definition, `validation.utc_timestamp`; the store stamps with it.
from openflowsheet.application.validation import utc_timestamp
from openflowsheet.canonical import canonical_json

STORE_SCHEMA: Final[str] = "t07-store-v1"
DATABASE_NAME: Final[str] = "project.sqlite3"
POLICY_NAME: Final[str] = "project-policy.json"
OWNERS_DIR: Final[str] = "owners"
JOBS_DIR: Final[str] = "jobs"
IMPORTS_DIR: Final[str] = "imports"
#: §9.2: how long a writer waits for another's transaction before SQLite reports busy.
BUSY_TIMEOUT_S: Final[float] = 30.0
#: The one ref in v1 (§1: no branches).
HEAD: Final[str] = "head"
ACTIVE_STATUSES: Final[tuple[str, ...]] = ("queued", "running")

_TABLES: Final[tuple[str, ...]] = (
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE revisions (ordinal INTEGER PRIMARY KEY, revision_id TEXT NOT NULL UNIQUE,"
    " document BLOB NOT NULL, content_sha256 TEXT NOT NULL, parent_revision TEXT,"
    " principal_id TEXT NOT NULL, capability_id TEXT NOT NULL, policy_sha256 TEXT NOT NULL,"
    " created_at TEXT NOT NULL)",
    "CREATE TABLE refs (name TEXT PRIMARY KEY,"
    " revision_id TEXT NOT NULL REFERENCES revisions(revision_id))",
    "CREATE TABLE ledger (principal_id TEXT NOT NULL, operation TEXT NOT NULL,"
    " idempotency_key TEXT NOT NULL, request_sha256 TEXT NOT NULL, result BLOB NOT NULL,"
    " created_at TEXT NOT NULL, PRIMARY KEY (principal_id, operation, idempotency_key))",
    # No CHECK on `status` or any `kind` column: rows from a newer producer stay readable (J5).
    "CREATE TABLE jobs (ordinal INTEGER PRIMARY KEY, job_id TEXT NOT NULL UNIQUE,"
    " operation TEXT NOT NULL, request BLOB NOT NULL, request_sha256 TEXT NOT NULL,"
    " principal_id TEXT NOT NULL, capability_id TEXT NOT NULL, policy_sha256 TEXT NOT NULL,"
    " status TEXT NOT NULL, owner_instance TEXT NOT NULL, outputs BLOB NOT NULL, progress BLOB,"
    " effective_budgets BLOB NOT NULL, cancel_requested INTEGER NOT NULL,"
    " created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT, ending BLOB, error BLOB,"
    " worker_result BLOB)",
    "CREATE TABLE events (job_id TEXT NOT NULL REFERENCES jobs(job_id),"
    " sequence INTEGER NOT NULL, kind TEXT NOT NULL, ends_job INTEGER NOT NULL,"
    " document BLOB NOT NULL, PRIMARY KEY (job_id, sequence))",
    "CREATE TABLE artifacts (artifact_id TEXT PRIMARY KEY, job_id TEXT, kind TEXT NOT NULL,"
    " name TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,"
    " relpath TEXT NOT NULL, parent_artifact_id TEXT)",
    "CREATE TABLE audit (seq INTEGER PRIMARY KEY, at TEXT NOT NULL, principal_id TEXT NOT NULL,"
    " capability_id TEXT NOT NULL, operation TEXT NOT NULL,"
    " outcome TEXT NOT NULL CHECK (outcome IN ('allowed', 'refused')), code TEXT,"
    " request_sha256 TEXT, effect TEXT)",
)


class StoreError(RuntimeError):
    """A project directory or database that cannot be created or opened as asked."""


class IdempotencyKeyReusedError(StoreError):
    """§7: the key's triple is in the ledger under a different request hash."""

    def __init__(self, original_request_sha256: str) -> None:
        super().__init__(
            "this idempotency key was used with a different request "
            f"(original request_sha256 {original_request_sha256})"
        )
        self.original_request_sha256 = original_request_sha256


class ActiveJobLimitError(StoreError):
    """§5.3 step 8, checked inside the accepting transaction: the principal already has
    `active_jobs` queued or running, not fewer than the limit it was accepted under."""

    def __init__(self, active_jobs: int) -> None:
        super().__init__(f"the principal has {active_jobs} active jobs")
        self.active_jobs = active_jobs


def _blob(document: object) -> bytes:
    return canonical_json(document)


def _load(blob: bytes | str | None) -> Any:
    return None if blob is None else json.loads(blob)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write a temporary file beside `path`, `fsync` it, rename it over `path`, `fsync` the dir."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def policy_file_bytes(policy: ProjectPolicy) -> bytes:
    """The operator-readable spelling of a policy; its identity is `policy_sha256`, not these."""
    return (json.dumps(policy.as_document(), indent=1, sort_keys=True) + "\n").encode("utf-8")


@dataclass(frozen=True)
class AuditEntry:
    """§10.7: one effect or one refusal. `at` is stamped by the store."""

    principal_id: str
    capability_id: str
    operation: str
    outcome: str
    code: str | None = None
    request_sha256: str | None = None
    effect: str | None = None


@dataclass(frozen=True)
class ArtifactRow:
    """§9.2 `artifacts`: one registered file or bundle directory. `relpath` is relative to the
    project's files root and is never read from a request; `job_id` is `None` for an import."""

    artifact_id: str
    job_id: str | None
    kind: str
    name: str
    sha256: str
    size_bytes: int
    relpath: str
    parent_artifact_id: str | None = None

    def as_ref(self) -> ArtifactRef:
        """The J1 reference of this artifact (§5.4)."""
        return ArtifactRef(
            kind=self.kind,
            artifact_id=self.artifact_id,
            sha256=self.sha256,
            size_bytes=self.size_bytes,
            name=self.name,
        )


@dataclass(frozen=True)
class LedgerRow:
    """§7: `(principal_id, operation, idempotency_key)` → `(request_sha256, result)`."""

    request_sha256: str
    result: Any


class ProjectStore:
    """The SQLite store of one project, or of an in-memory one (`in_memory`).

    Methods taking a `connection` run inside a transaction the caller opened with `reading()` or
    `writing()`; the others open their own.
    """

    def __init__(self, directory: Path | None, connection: sqlite3.Connection | None) -> None:
        self.directory = directory
        self._memory = connection
        self._memory_lock = threading.RLock()
        self._owner_handles: dict[str, int] = {}
        #: A test hook, callable only from Python: it runs between a revision's insert and the
        #: head's move (`commit_revision`), so a test can crash a commit at its middle.
        self.test_hook_after_revision_insert: Callable[[], None] | None = None

    # ------------------------------------------------------------------------- construction

    @classmethod
    def create(cls, directory: Path, *, project_id: str) -> ProjectStore:
        """A new project in `directory`, which must be absent or empty."""
        directory = Path(directory)
        if directory.exists() and any(directory.iterdir()):
            raise StoreError(f"{directory} is not empty; a project is created in a new directory")
        directory.mkdir(parents=True, exist_ok=True)
        for name in (OWNERS_DIR, JOBS_DIR, IMPORTS_DIR):
            (directory / name).mkdir()
        connection = sqlite3.connect(directory / DATABASE_NAME, isolation_level=None)
        try:
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                # §17 R2: SQLite on a filesystem without shared memory (a network mount) is
                # unsupported, and refusing here is better than corrupting a ledger later.
                raise StoreError(f"{directory} cannot hold a WAL database (journal_mode={mode})")
            policy = ProjectPolicy(
                project_id=project_id, capabilities=(), executor=ExecutorSettings()
            )
            connection.execute("BEGIN IMMEDIATE")
            _create_tables(connection, project_id)
            # §10.3: every policy change is audited by the owner, the first one included.
            cls.audit(
                connection,
                AuditEntry(
                    principal_id=LOCAL_OWNER_PRINCIPAL,
                    capability_id=LOCAL_OWNER_PRINCIPAL,
                    operation="project_init",
                    outcome="allowed",
                    request_sha256=policy.policy_sha256,
                    effect=f"project:{project_id}",
                ),
            )
            atomic_write_bytes(directory / POLICY_NAME, policy_file_bytes(policy))
            connection.execute("COMMIT")
        finally:
            connection.close()
        return cls.open(directory)

    @classmethod
    def open(cls, directory: Path) -> ProjectStore:
        directory = Path(directory)
        path = directory / DATABASE_NAME
        if not path.is_file():
            raise StoreError(f"{directory} is not a project (no {DATABASE_NAME})")
        store = cls(directory, None)
        with store.reading() as connection:
            mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            schema = store._meta(connection, "store_schema")
        if str(mode).lower() != "wal":
            raise StoreError(f"{path} is not in WAL mode (journal_mode={mode})")
        if schema != STORE_SCHEMA:
            raise StoreError(f"{path} has store schema {schema!r}, not {STORE_SCHEMA!r}")
        return store

    @classmethod
    def in_memory(cls, *, project_id: str) -> ProjectStore:
        """SQLite `:memory:`: one connection, shared by the process's threads behind a lock."""
        connection = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        _create_tables(connection, project_id)
        connection.execute("COMMIT")
        return cls(None, connection)

    def close(self) -> None:
        for owner_instance in list(self._owner_handles):
            self.release_owner(owner_instance)
        if self._memory is not None:
            with self._memory_lock:
                self._memory.close()

    # -------------------------------------------------------------------------- transactions

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self._memory is not None:
            with self._memory_lock:
                yield self._memory
            return
        assert self.directory is not None
        connection = sqlite3.connect(
            self.directory / DATABASE_NAME, timeout=BUSY_TIMEOUT_S, isolation_level=None
        )
        try:
            connection.execute(f"PRAGMA busy_timeout = {int(BUSY_TIMEOUT_S * 1000)}")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def reading(self) -> Iterator[sqlite3.Connection]:
        """One consistent snapshot for several reads."""
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                yield connection
            finally:
                connection.execute("COMMIT")

    @contextmanager
    def writing(self) -> Iterator[sqlite3.Connection]:
        """One `BEGIN IMMEDIATE` transaction: all of it, or — on any exception — none of it."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")

    # ---------------------------------------------------------------------------------- meta

    @staticmethod
    def _meta(connection: sqlite3.Connection, key: str) -> str | None:
        row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    @property
    def project_id(self) -> str:
        with self.reading() as connection:
            value = self._meta(connection, "project_id")
        assert value is not None
        return value

    @property
    def policy_path(self) -> Path | None:
        return None if self.directory is None else self.directory / POLICY_NAME

    # ----------------------------------------------------------------------------- revisions

    @staticmethod
    def head(connection: sqlite3.Connection) -> str | None:
        row = connection.execute("SELECT revision_id FROM refs WHERE name = ?", (HEAD,)).fetchone()
        return None if row is None else str(row[0])

    @staticmethod
    def get_revision(connection: sqlite3.Connection, revision_id: str) -> Revision | None:
        row = connection.execute(
            "SELECT document, parent_revision FROM revisions WHERE revision_id = ?",
            (revision_id,),
        ).fetchone()
        if row is None:
            return None
        return Revision(revision_id=revision_id, document=_load(row[0]), parent_revision=row[1])

    @staticmethod
    def revision_ids(connection: sqlite3.Connection) -> tuple[str, ...]:
        rows = connection.execute("SELECT revision_id FROM revisions ORDER BY ordinal").fetchall()
        return tuple(str(row[0]) for row in rows)

    @staticmethod
    def next_revision_ordinal(connection: sqlite3.Connection) -> int:
        row = connection.execute("SELECT COALESCE(MAX(ordinal), 0) + 1 FROM revisions").fetchone()
        return int(row[0])

    @staticmethod
    def revision_count(connection: sqlite3.Connection) -> int:
        return int(connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0])

    def list_revisions(
        self, *, after_ordinal: int, limit: int
    ) -> tuple[list[tuple[int, RevisionSummary]], bool]:
        """At most `limit` revision summaries after `after_ordinal`, in commit order, with their
        ordinals, and whether more follow (§11.4 `list_revisions`)."""
        with self.reading() as connection:
            head = self.head(connection)
            rows = connection.execute(
                "SELECT ordinal, revision_id, parent_revision, content_sha256, principal_id,"
                " created_at, document FROM revisions WHERE ordinal > ? ORDER BY ordinal LIMIT ?",
                (after_ordinal, limit + 1),
            ).fetchall()
        summaries: list[tuple[int, RevisionSummary]] = []
        for ordinal, revision_id, parent, content_sha256, principal_id, created_at, blob in rows:
            title = _load(blob).get("title")
            summaries.append(
                (
                    int(ordinal),
                    RevisionSummary(
                        revision_id=revision_id,
                        parent_revision=parent,
                        content_sha256=content_sha256,
                        title=title if isinstance(title, str) else None,
                        principal_id=principal_id,
                        created_at=created_at,
                        head=revision_id == head,
                    ),
                )
            )
        return summaries[:limit], len(summaries) > limit

    def commit_revision(
        self,
        connection: sqlite3.Connection,
        revision: Revision,
        *,
        principal_id: str,
        capability_id: str,
        policy_sha256: str,
    ) -> None:
        """Insert `revision` and move the head to it, inside the caller's write transaction.

        `policy_sha256` is the project policy in force (§10.3: every transaction records it).
        """
        connection.execute(
            "INSERT INTO revisions (ordinal, revision_id, document, content_sha256,"
            " parent_revision, principal_id, capability_id, policy_sha256, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.next_revision_ordinal(connection),
                revision.revision_id,
                _blob(revision.document),
                content_hash(revision.document),
                revision.parent_revision,
                principal_id,
                capability_id,
                policy_sha256,
                utc_timestamp(),
            ),
        )
        if self.test_hook_after_revision_insert is not None:
            self.test_hook_after_revision_insert()
        connection.execute(
            "INSERT INTO refs (name, revision_id) VALUES (?, ?)"
            " ON CONFLICT (name) DO UPDATE SET revision_id = excluded.revision_id",
            (HEAD, revision.revision_id),
        )

    # -------------------------------------------------------------------------------- ledger

    @staticmethod
    def ledger_lookup(
        connection: sqlite3.Connection, principal_id: str, operation: str, key: str
    ) -> LedgerRow | None:
        row = connection.execute(
            "SELECT request_sha256, result FROM ledger"
            " WHERE principal_id = ? AND operation = ? AND idempotency_key = ?",
            (principal_id, operation, key),
        ).fetchone()
        return None if row is None else LedgerRow(str(row[0]), _load(row[1]))

    @staticmethod
    def ledger_insert(
        connection: sqlite3.Connection,
        principal_id: str,
        operation: str,
        key: str,
        request_sha256: str,
        result: object,
    ) -> None:
        connection.execute(
            "INSERT INTO ledger (principal_id, operation, idempotency_key, request_sha256,"
            " result, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (principal_id, operation, key, request_sha256, _blob(result), utc_timestamp()),
        )

    # --------------------------------------------------------------------------------- audit

    @staticmethod
    def audit(connection: sqlite3.Connection, entry: AuditEntry) -> None:
        connection.execute(
            "INSERT INTO audit (at, principal_id, capability_id, operation, outcome, code,"
            " request_sha256, effect) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                utc_timestamp(),
                entry.principal_id,
                entry.capability_id,
                entry.operation,
                entry.outcome,
                entry.code,
                entry.request_sha256,
                entry.effect,
            ),
        )

    def record_audit(self, entry: AuditEntry) -> None:
        """A refusal, in a transaction of its own (an effect is audited inside its own)."""
        with self.writing() as connection:
            self.audit(connection, entry)

    def list_audit(
        self,
        *,
        principal_id: str | None,
        operation: str | None,
        descending: bool,
        after_seq: int | None,
        limit: int,
    ) -> tuple[list[AuditRecord], bool]:
        """At most `limit` audit rows in `seq` order (descending when asked), after `after_seq`
        in that order, with the ledger's idempotency key of each `allowed` row; and whether more
        follow (ADR 0019 Amendment 3, A3.3; M06 design note §4.3).

        One read-only query, a LEFT JOIN of `audit` with `ledger` on `(principal_id, operation,
        request_sha256)`, which the ledger's primary-key prefix `(principal_id, operation)`
        bounds. A keyed request's hash covers its key (R2, tested), so at most one ledger row
        matches; a second would repeat a `seq`, which is refused as a defect, never shown."""
        clauses: list[str] = []
        parameters: list[str | int] = []
        if principal_id is not None:
            clauses.append("a.principal_id = ?")
            parameters.append(principal_id)
        if operation is not None:
            clauses.append("a.operation = ?")
            parameters.append(operation)
        if after_seq is not None:
            clauses.append("a.seq < ?" if descending else "a.seq > ?")
            parameters.append(after_seq)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        direction = "DESC" if descending else "ASC"
        with self.reading() as connection:
            rows = connection.execute(
                "SELECT a.seq, a.at, a.principal_id, a.capability_id, a.operation, a.outcome,"
                " a.code, a.request_sha256, a.effect, l.idempotency_key FROM audit a"
                " LEFT JOIN ledger l ON a.outcome = 'allowed'"
                " AND l.principal_id = a.principal_id AND l.operation = a.operation"
                f" AND l.request_sha256 = a.request_sha256{where}"
                f" ORDER BY a.seq {direction} LIMIT ?",
                (*parameters, limit + 1),
            ).fetchall()
        sequence = [int(row[0]) for row in rows]
        if len(set(sequence)) != len(sequence):
            raise StoreError("an audit row joins more than one ledger row")
        records = [
            AuditRecord(
                seq=int(row[0]),
                at=str(row[1]),
                principal_id=str(row[2]),
                capability_id=str(row[3]),
                operation=str(row[4]),
                outcome=row[5],
                code=row[6],
                request_sha256=row[7],
                effect=row[8],
                idempotency_key=row[9],
            )
            for row in rows
        ]
        return records[:limit], len(records) > limit

    def audit_rows(self) -> list[dict[str, Any]]:
        with self.reading() as connection:
            cursor = connection.execute(
                "SELECT seq, at, principal_id, capability_id, operation, outcome, code,"
                " request_sha256, effect FROM audit ORDER BY seq"
            )
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    # ---------------------------------------------------------------------------------- jobs

    def accept_job(
        self,
        request: JobRequest,
        *,
        principal_id: str,
        capability_id: str,
        policy_sha256: str,
        owner_instance: str,
        effective_budgets: EffectiveBudgets,
        max_active_jobs: int | None = None,
    ) -> tuple[Job, bool]:
        """§4.2 step 8 with §7's ledger: `(job, replayed)`, in one transaction.

        The ledger lookup and the insert share one `BEGIN IMMEDIATE` transaction, so of any
        number of concurrent submissions with one key exactly one inserts; every other one reads
        the winner's row and gets the winner's job, or `IdempotencyKeyReusedError` if its request
        hash differs. There is never a second job.

        §5.3 step 8 is checked in the same transaction, after the ledger: a new job is inserted
        only while the principal has fewer than `max_active_jobs` active ones, else
        `ActiveJobLimitError`. A replay is not a new job and is not limited.
        """
        request_sha256 = request.request_sha256
        with self.writing() as connection:
            prior = self.ledger_lookup(
                connection, principal_id, "submit_job", request.idempotency_key
            )
            if prior is not None:
                if prior.request_sha256 != request_sha256:
                    raise IdempotencyKeyReusedError(prior.request_sha256)
                return self._job(connection, str(prior.result)), True
            if max_active_jobs is not None:
                active = self._active_jobs(connection, principal_id)
                if active >= max_active_jobs:
                    raise ActiveJobLimitError(active)
            ordinal = int(
                connection.execute("SELECT COALESCE(MAX(ordinal), 0) + 1 FROM jobs").fetchone()[0]
            )
            job_id = f"job-{ordinal:06d}"
            now = utc_timestamp()
            connection.execute(
                "INSERT INTO jobs (ordinal, job_id, operation, request, request_sha256,"
                " principal_id, capability_id, policy_sha256, status, owner_instance, outputs,"
                " progress, effective_budgets, cancel_requested, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, NULL, ?, 0, ?)",
                (
                    ordinal,
                    job_id,
                    request.operation,
                    _blob(request.as_document()),
                    request_sha256,
                    principal_id,
                    capability_id,
                    policy_sha256,
                    owner_instance,
                    _blob([]),
                    _blob(effective_budgets.as_document()),
                    now,
                ),
            )
            self._append_event(
                connection,
                JobEvent(
                    job_id=job_id, sequence=0, kind="accepted", ends_job=False, recorded_at=now
                ),
            )
            self.ledger_insert(
                connection,
                principal_id,
                "submit_job",
                request.idempotency_key,
                request_sha256,
                job_id,
            )
            self.audit(
                connection,
                AuditEntry(
                    principal_id=principal_id,
                    capability_id=capability_id,
                    operation="submit_job",
                    outcome="allowed",
                    request_sha256=request_sha256,
                    effect=f"job:{job_id}",
                ),
            )
            return self._job(connection, job_id), False

    @staticmethod
    def _append_event(connection: sqlite3.Connection, event: JobEvent) -> None:
        connection.execute(
            "INSERT INTO events (job_id, sequence, kind, ends_job, document)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                event.job_id,
                event.sequence,
                event.kind,
                int(event.ends_job),
                _blob(event.as_document()),
            ),
        )

    @staticmethod
    def _next_sequence(connection: sqlite3.Connection, job_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence), -1) + 1 FROM events WHERE job_id = ?", (job_id,)
        ).fetchone()
        return int(row[0])

    def start_job(self, job_id: str, *, owner_instance: str) -> bool:
        """`queued` → `running` with its `started` event; fenced on the owner (§9.3).

        Returns whether the fence held. Zero matching rows means the job is not this owner's or
        is no longer queued, and nothing is written.
        """
        with self.writing() as connection:
            now = utc_timestamp()
            moved = connection.execute(
                "UPDATE jobs SET status = 'running', started_at = ?"
                " WHERE job_id = ? AND owner_instance = ? AND status = 'queued'",
                (now, job_id, owner_instance),
            ).rowcount
            if moved != 1:
                return False
            self._append_event(
                connection,
                JobEvent(
                    job_id=job_id,
                    sequence=self._next_sequence(connection, job_id),
                    kind="started",
                    ends_job=False,
                    recorded_at=now,
                ),
            )
            return True

    def end_job(
        self,
        connection: sqlite3.Connection,
        job_id: str,
        ending: JobEnding,
        error: ApiError | None = None,
    ) -> bool:
        """Append the one `ended` event and set the terminal status, if the job has not ended.

        §6.2: only the job's owner — or recovery, standing in for a dead owner — calls this. The
        update is conditional on a non-terminal status, so two recoverers cannot both end a job.
        """
        now = utc_timestamp()
        placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
        moved = connection.execute(
            f"UPDATE jobs SET status = ?, ended_at = ?, ending = ?, error = ?"
            f" WHERE job_id = ? AND status IN ({placeholders})",
            (
                ending.status,
                now,
                _blob(ending.as_document()),
                None if error is None else _blob(error.as_document()),
                job_id,
                *ACTIVE_STATUSES,
            ),
        ).rowcount
        if moved != 1:
            return False
        self._append_event(
            connection,
            JobEvent(
                job_id=job_id,
                sequence=self._next_sequence(connection, job_id),
                kind="ended",
                ends_job=True,
                recorded_at=now,
                ending=ending,
                error=error,
            ),
        )
        return True

    # ------------------------------------------------------------ running a job (§6.2, §9.3)

    def append_job_event(
        self,
        job_id: str,
        *,
        owner_instance: str,
        progress: Progress | None = None,
        output: ArtifactRef | None = None,
    ) -> bool:
        """A `progress` or an `output` event, with the `jobs` row it changes, in one transaction.

        Exactly one of `progress` and `output`. Fenced (§9.3): written only while the job is
        running under `owner_instance`; returns whether the fence held. `Job.outputs` is thereby
        always the ordered list of the output events' references (§6.2, J1, J2).
        """
        if (progress is None) == (output is None):
            raise ValueError("an execution event carries exactly one of progress and output")
        with self.writing() as connection:
            row = connection.execute(
                "SELECT outputs FROM jobs WHERE job_id = ? AND owner_instance = ?"
                " AND status = 'running'",
                (job_id, owner_instance),
            ).fetchone()
            if row is None:
                return False
            if progress is not None:
                connection.execute(
                    "UPDATE jobs SET progress = ? WHERE job_id = ?",
                    (_blob(progress.as_document()), job_id),
                )
                kind = "progress"
            else:
                assert output is not None
                outputs = [*_load(row[0]), output.as_document()]
                connection.execute(
                    "UPDATE jobs SET outputs = ? WHERE job_id = ?", (_blob(outputs), job_id)
                )
                kind = "output"
            self._append_event(
                connection,
                JobEvent(
                    job_id=job_id,
                    sequence=self._next_sequence(connection, job_id),
                    kind=kind,
                    ends_job=False,
                    recorded_at=utc_timestamp(),
                    progress=progress,
                    output=output,
                ),
            )
            return True

    def record_worker_result(
        self, job_id: str, *, owner_instance: str, worker_result: Mapping[str, Any]
    ) -> bool:
        """A worker's intended termination (§6.2): `jobs.worker_result`, fenced like every other
        worker write (§9.3). The owner turns it into `ended`; returns whether the fence held."""
        with self.writing() as connection:
            moved = connection.execute(
                "UPDATE jobs SET worker_result = ?"
                " WHERE job_id = ? AND owner_instance = ? AND status = 'running'",
                (_blob(dict(worker_result)), job_id, owner_instance),
            ).rowcount
        return moved == 1

    def finish_job(
        self,
        job_id: str,
        *,
        owner_instance: str,
        ending: JobEnding,
        error: ApiError | None,
        worker_result: Mapping[str, Any] | None,
    ) -> bool:
        """The owner's end of a job it ran or was running (§6.2): `worker_result` and the one
        `ended` event, in one transaction. Returns whether this call ended the job."""
        with self.writing() as connection:
            owned = connection.execute(
                "SELECT 1 FROM jobs WHERE job_id = ? AND owner_instance = ?",
                (job_id, owner_instance),
            ).fetchone()
            if owned is None:
                return False
            if not self.end_job(connection, job_id, ending, error):
                return False
            if worker_result is not None:
                connection.execute(
                    "UPDATE jobs SET worker_result = ? WHERE job_id = ?",
                    (_blob(dict(worker_result)), job_id),
                )
            return True

    def request_cancel(
        self, job_id: str, audit: AuditEntry | None = None
    ) -> tuple[str, bool] | None:
        """§4.2 `cancel_job`'s store half, in one transaction: `(status before, recorded)`, or
        `None` for no such job.

        A queued job is ended `cancelled(cancel_requested)` at once, after its
        `cancel_requested` event; a running job gets the flag and the event, once; an ended job
        is left as it is. `recorded` says whether this call changed the job. `audit` (the
        allowed cancel, an effect under §10.7) is written in the same transaction whenever the
        job exists, a cancel that changes nothing included: it records the authorization
        decision, whatever the job's state (ruling round 5, S10).
        """
        with self.writing() as connection:
            row = connection.execute(
                "SELECT status, cancel_requested FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                return None
            status, requested = str(row[0]), bool(row[1])
            if status not in ACTIVE_STATUSES or requested:
                if audit is not None:
                    self.audit(connection, audit)
                return status, False
            connection.execute("UPDATE jobs SET cancel_requested = 1 WHERE job_id = ?", (job_id,))
            self._append_event(
                connection,
                JobEvent(
                    job_id=job_id,
                    sequence=self._next_sequence(connection, job_id),
                    kind="cancel_requested",
                    ends_job=False,
                    recorded_at=utc_timestamp(),
                ),
            )
            if status == "queued":
                self.end_job(
                    connection, job_id, JobEnding(status="cancelled", reason="cancel_requested")
                )
            if audit is not None:
                self.audit(connection, audit)
            return status, True

    def cancel_requested(self, job_id: str) -> bool:
        with self.reading() as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return row is not None and bool(row[0])

    def worker_result(self, job_id: str) -> Any:
        """The job's `worker_result` document, or `None` when no owner or worker wrote one."""
        with self.reading() as connection:
            row = connection.execute(
                "SELECT worker_result FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return None if row is None else _load(row[0])

    def active_job_count(self, principal_id: str) -> int:
        """§5.3 step 8: the principal's queued and running jobs."""
        with self.reading() as connection:
            return self._active_jobs(connection, principal_id)

    @staticmethod
    def _active_jobs(connection: sqlite3.Connection, principal_id: str) -> int:
        placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
        row = connection.execute(
            f"SELECT COUNT(*) FROM jobs WHERE principal_id = ? AND status IN ({placeholders})",
            (principal_id, *ACTIVE_STATUSES),
        ).fetchone()
        return int(row[0])

    @staticmethod
    def job_counts(connection: sqlite3.Connection) -> dict[str, int]:
        """`{status: number of jobs}` for the statuses the project's jobs are in."""
        rows = connection.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall()
        return {str(status): int(count) for status, count in rows}

    def job_snapshot(self, job_id: str) -> tuple[Job, list[JobEvent]] | None:
        """The job and its whole event stream from one read transaction (§6.3 rule 12)."""
        with self.reading() as connection:
            if connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone():
                return self._job(connection, job_id), self._events(connection, job_id, -1, None)
        return None

    def job_events_after(
        self, job_id: str, after_sequence: int, limit: int
    ) -> tuple[Job, list[JobEvent]] | None:
        """The job and at most `limit` of its events after `after_sequence`, in one snapshot."""
        with self.reading() as connection:
            if connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone():
                job = self._job(connection, job_id)
                return job, self._events(connection, job_id, after_sequence, limit)
        return None

    @staticmethod
    def _events(
        connection: sqlite3.Connection, job_id: str, after_sequence: int, limit: int | None
    ) -> list[JobEvent]:
        rows = connection.execute(
            "SELECT document FROM events WHERE job_id = ? AND sequence > ? ORDER BY sequence"
            " LIMIT ?",
            (job_id, after_sequence, -1 if limit is None else limit),
        ).fetchall()
        return [JobEvent.from_document(_load(row[0]), lenient=True) for row in rows]

    def list_jobs(
        self, *, status: str | None, after_ordinal: int, limit: int
    ) -> tuple[list[tuple[int, Job]], bool]:
        """At most `limit` jobs after `after_ordinal`, in acceptance order, with their ordinals,
        and whether more follow."""
        clause, parameters = ("", ()) if status is None else (" AND status = ?", (status,))
        with self.reading() as connection:
            rows = connection.execute(
                f"SELECT ordinal, job_id FROM jobs WHERE ordinal > ?{clause}"
                " ORDER BY ordinal LIMIT ?",
                (after_ordinal, *parameters, limit + 1),
            ).fetchall()
            jobs = [(int(ordinal), self._job(connection, str(job_id))) for ordinal, job_id in rows]
        return jobs[:limit], len(jobs) > limit

    # ----------------------------------------------------------------------------- artifacts

    @staticmethod
    def register_artifacts(connection: sqlite3.Connection, rows: Sequence[ArtifactRow]) -> None:
        """Insert artifact rows inside the caller's write transaction (§9.2 `artifacts`)."""
        connection.executemany(
            "INSERT INTO artifacts (artifact_id, job_id, kind, name, sha256, size_bytes, relpath,"
            " parent_artifact_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row.artifact_id,
                    row.job_id,
                    row.kind,
                    row.name,
                    row.sha256,
                    row.size_bytes,
                    row.relpath,
                    row.parent_artifact_id,
                )
                for row in rows
            ],
        )

    def artifact(self, artifact_id: str) -> ArtifactRow | None:
        with self.reading() as connection:
            row = connection.execute(
                "SELECT artifact_id, job_id, kind, name, sha256, size_bytes, relpath,"
                " parent_artifact_id FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        return None if row is None else ArtifactRow(*row)

    def artifact_children(self, parent_artifact_id: str) -> list[ArtifactRow]:
        """The registered members of a bundle, in id order."""
        with self.reading() as connection:
            rows = connection.execute(
                "SELECT artifact_id, job_id, kind, name, sha256, size_bytes, relpath,"
                " parent_artifact_id FROM artifacts WHERE parent_artifact_id = ?"
                " ORDER BY artifact_id",
                (parent_artifact_id,),
            ).fetchall()
        return [ArtifactRow(*row) for row in rows]

    def get_job(self, job_id: str) -> Job | None:
        with self.reading() as connection:
            row = connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return None if row is None else self._job(connection, job_id)

    def job_events(self, job_id: str) -> list[JobEvent]:
        with self.reading() as connection:
            rows = connection.execute(
                "SELECT document FROM events WHERE job_id = ? ORDER BY sequence", (job_id,)
            ).fetchall()
        return [JobEvent.from_document(_load(row[0]), lenient=True) for row in rows]

    def job_ids(self) -> tuple[str, ...]:
        with self.reading() as connection:
            rows = connection.execute("SELECT job_id FROM jobs ORDER BY ordinal").fetchall()
        return tuple(str(row[0]) for row in rows)

    @staticmethod
    def lineage(connection: sqlite3.Connection, revision_id: str) -> tuple[str, ...]:
        """`revision_id` and its ancestors through `parent_revision`, nearest first."""
        found: list[str] = []
        current: str | None = revision_id
        while current is not None and current not in found:
            row = connection.execute(
                "SELECT parent_revision FROM revisions WHERE revision_id = ?", (current,)
            ).fetchone()
            if row is None:
                break
            found.append(current)
            current = row[0]
        return tuple(found)

    @staticmethod
    def latest_verified_solution(
        connection: sqlite3.Connection, revision_ids: Sequence[str], *, excluding: str
    ) -> tuple[str, str, str] | None:
        """ADR 0024 D2's `store-latest-verified-lineage-v1`: `(job_id, revision_id, relpath)` of
        the `solution_state` artifact of the ended solve job with the highest ordinal, other than
        `excluding`, whose request names one of `revision_ids`, which holds that artifact, and
        whose certificate verdict (`worker_result.run`, copied from the certificate) is
        `VERIFIED`; `None` when there is none. At most one is returned: the caller checks it and
        does not look further (T08 build-first spec §B1)."""
        lineage = set(revision_ids)
        placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
        rows = connection.execute(
            "SELECT job_id, request, worker_result FROM jobs WHERE operation = 'solve'"
            f" AND status NOT IN ({placeholders}) ORDER BY ordinal DESC",
            ACTIVE_STATUSES,
        ).fetchall()
        for job_id, request, worker in rows:
            if job_id == excluding:
                continue
            revision_id = _load(request).get("body", {}).get("revision_id")
            if revision_id not in lineage:
                continue
            ended = _load(worker)
            run = ended.get("run") if isinstance(ended, Mapping) else None
            if not isinstance(run, Mapping) or run.get("verification_status") != "VERIFIED":
                continue
            artifact = connection.execute(
                "SELECT relpath FROM artifacts WHERE job_id = ? AND kind = 'solution_state'"
                " ORDER BY artifact_id LIMIT 1",
                (job_id,),
            ).fetchone()
            if artifact is None:
                continue
            return str(job_id), str(revision_id), str(artifact[0])
        return None

    @staticmethod
    def solve_jobs_for_revision(connection: sqlite3.Connection, revision_id: str) -> list[str]:
        """The ids of every solve job whose request names `revision_id`, in acceptance order."""
        rows = connection.execute(
            "SELECT job_id, request FROM jobs WHERE operation = 'solve' ORDER BY ordinal"
        ).fetchall()
        return [
            str(job_id)
            for job_id, request in rows
            if _load(request).get("body", {}).get("revision_id") == revision_id
        ]

    @staticmethod
    def _job(connection: sqlite3.Connection, job_id: str) -> Job:
        row = connection.execute(
            "SELECT job_id, operation, request, request_sha256, principal_id, capability_id,"
            " policy_sha256, status, outputs, progress, effective_budgets, cancel_requested,"
            " created_at, started_at, ended_at, ending, error FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        count = connection.execute(
            "SELECT COUNT(*) FROM events WHERE job_id = ?", (job_id,)
        ).fetchone()[0]
        document: Mapping[str, Any] = {
            "job_id": row[0],
            "operation": row[1],
            "request": _load(row[2]),
            "request_sha256": row[3],
            "principal_id": row[4],
            "capability_id": row[5],
            "policy_sha256": row[6],
            "status": row[7],
            "outputs": _load(row[8]),
            "progress": _load(row[9]),
            "effective_budgets": _load(row[10]),
            "cancel_requested": bool(row[11]),
            "event_count": int(count),
            "created_at": row[12],
            "started_at": row[13],
            "ended_at": row[14],
            "ending": _load(row[15]),
            "error": _load(row[16]),
        }
        return Job.from_document(document, lenient=True)

    # ------------------------------------------------------------------ ownership (§9.3)

    def _lock_path(self, owner_instance: str) -> Path:
        assert self.directory is not None
        return self.directory / OWNERS_DIR / f"{owner_instance}.lock"

    def acquire_owner(self, owner_instance: str) -> None:
        """Hold `owners/<owner_instance>.lock` exclusively until `release_owner` or exit."""
        if self.directory is None:
            return
        handle = os.open(self._lock_path(owner_instance), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(handle)
            raise StoreError(f"owner instance {owner_instance} is already held") from None
        self._owner_handles[owner_instance] = handle

    def release_owner(self, owner_instance: str) -> None:
        handle = self._owner_handles.pop(owner_instance, None)
        if handle is None:
            return
        self._lock_path(owner_instance).unlink(missing_ok=True)
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)

    def _probe_dead(self, owner_instance: str) -> int | None:
        """A handle holding a dead owner's lock, `-1` if its lock file is gone, `None` if alive.

        An owner creates its lock file before it accepts any job, so a job whose owner has no
        lock file has a dead owner.
        """
        try:
            handle = os.open(self._lock_path(owner_instance), os.O_RDWR)
        except FileNotFoundError:
            return -1
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(handle)
            if error.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                return None
            raise
        return handle

    def recover(self, *, own_instance: str) -> list[str]:
        """§9.3: end every non-terminal job of a dead owner `failed(owner_lost)`; their ids."""
        if self.directory is None:
            return []
        placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
        with self.reading() as connection:
            rows = connection.execute(
                f"SELECT job_id, owner_instance FROM jobs WHERE status IN ({placeholders})"
                " ORDER BY ordinal",
                ACTIVE_STATUSES,
            ).fetchall()
        by_owner: dict[str, list[str]] = {}
        for job_id, owner in rows:
            if owner != own_instance and owner not in self._owner_handles:
                by_owner.setdefault(str(owner), []).append(str(job_id))
        recovered: list[str] = []
        ending = JobEnding(status="failed", reason="owner_lost")
        for owner, job_ids in by_owner.items():
            handle = self._probe_dead(owner)
            if handle is None:
                continue
            try:
                with self.writing() as connection:
                    recovered.extend(
                        job_id for job_id in job_ids if self.end_job(connection, job_id, ending)
                    )
                self._lock_path(owner).unlink(missing_ok=True)
            finally:
                if handle >= 0:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                    os.close(handle)
        return recovered


def _create_tables(connection: sqlite3.Connection, project_id: str) -> None:
    for statement in _TABLES:
        connection.execute(statement)
    connection.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?)",
        (("store_schema", STORE_SCHEMA), ("project_id", project_id)),
    )
