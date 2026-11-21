"""The content-addressed record store (ADR 0061 D8).

A project's store is `<project>/records/`: write-once object files
`objects/<sha[0:2]>/<sha[2:4]>/<sha>.json` holding a record's canonical identity-projection bytes,
so `sha256(file bytes) == name` (integrity is a file hash, as in git), and `records.sqlite3`
(WAL, `busy_timeout` 30 s, schema id `f3-records-v1`, independent of T07's `project.sqlite3`)
with the tables `objects` and `keys` (both rebuildable from the object files), `registrations`
(the volatile blocks) and `rights` (D11's project register, `append_rights`, `rights_rows`).

**Write protocol (N12).** An object is written to a temporary file beside its target, flushed,
`fsync`ed and moved over the target with `os.replace`; a target that exists and verifies is kept.
A target whose bytes do not hash to its name is replaced by the write (F3 decision WO2-1 as ruled
in F3 ruling round 1): the writer holds bytes that hash to the name, so the repair is exact, and
`register` reports it with the notice `store_object_repaired(<sha>)`. On Windows a reader holding
the target open makes the replace fail with `PermissionError`: a target that then exists and
verifies is success, a corrupt one stays `store_object_corrupt`. Concurrent writers of one object
are safe: both write the same bytes. The object is written before its rows (W1 P1 review N7), so
a row never names a missing object; the rows are one `BEGIN IMMEDIATE` transaction. A file whose
bytes do not hash to its name is `store_object_corrupt(<sha>)` wherever it is read.

**Opened lazily.** Constructing a store touches nothing; its first operation checks the path
length (Windows without long paths: `store_path_too_long(<root>)`), creates the directory and the
database. So a project whose path is too deep for the store keeps opening (review item 21).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal, NamedTuple

from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.records.model import RecordOutcome
from openflowsheet.records.resolve import lookup_keys
from openflowsheet.records.rights import ROW_FIELDS, check_row
from openflowsheet.registry.tokens import Coded

#: D8: the store's directory below the project root, its database and its schema id.
RECORDS_DIR: Final = "records"
DATABASE_NAME: Final = "records.sqlite3"
SCHEMA_ID: Final = "f3-records-v1"
OBJECTS_DIR: Final = "objects"
BUSY_TIMEOUT_S: Final = 30.0
#: D8: `len("/records/objects/aa/bb/") + 64 + len(".json")`, the longest path below the root.
PATH_BUDGET: Final = 92
#: D8: the longest path Windows opens without long paths (MAX_PATH less the terminating NUL).
MAX_PATH: Final = 259
#: D8: the registry value that enables long paths on Windows.
LONG_PATHS_KEY: Final = r"SYSTEM\CurrentControlSet\Control\FileSystem"
#: D8: the prefix of a temporary object file; a rebuild skips such files (W1 P1 review N7).
TMP_PREFIX: Final = ".tmp-"

#: What D8's write protocol did with one object: wrote a new one, kept a valid one, or replaced
#: one whose bytes did not hash to its name.
Written = Literal["created", "kept", "repaired"]

_TABLES: Final = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS objects (
    sha TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    amount_basis TEXT
);
CREATE TABLE IF NOT EXISTS keys (
    sha TEXT NOT NULL,
    scheme TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (scheme, value, sha)
);
CREATE TABLE IF NOT EXISTS registrations (
    sequence INTEGER PRIMARY KEY,
    sha TEXT NOT NULL,
    volatile_sha TEXT NOT NULL,
    volatile TEXT NOT NULL,
    findings TEXT NOT NULL,
    at TEXT NOT NULL,
    principal TEXT NOT NULL,
    UNIQUE (sha, volatile_sha)
);
CREATE TABLE IF NOT EXISTS rights (
    sequence INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    record_sha256 TEXT,
    assessment TEXT NOT NULL CHECK (assessment IN ('permitted', 'unknown', 'refused')),
    conditions TEXT,
    basis TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    date TEXT NOT NULL
);
"""


class RecordStoreError(RuntimeError):
    """A store refusal carrying its catalogued code (`store_object_corrupt`,
    `store_path_too_long`, `data_unavailable`, `record_*` on a refused registration), or `None`
    for a database that is not an `f3-records-v1` store."""

    def __init__(self, coded: Coded | None, message: str = "") -> None:
        super().__init__(message or (coded.code if coded is not None else "record store error"))
        self.coded = coded


class Registration(NamedTuple):
    """One registration's result: the record's SHA, whether this call created its object (false
    when the object existed, valid or repaired, D8), and the findings (notices) of this
    submission, `store_object_repaired` included."""

    record_sha256: str
    created: bool
    findings: tuple[Coded, ...]


class ObjectRow(NamedTuple):
    """D8's `objects` row: what a listing shows of a stored record without reading its file."""

    sha: str
    record_type: str
    id: str
    name: str
    amount_basis: str | None


def corrupt(sha: str) -> Coded:
    """D8's `store_object_corrupt(<sha>)`: a stored file's bytes do not hash to its name."""
    return Coded("store_object_corrupt", {"sha": sha})


def repaired(sha: str) -> Coded:
    """D8's notice `store_object_repaired(<sha>)`: a registration replaced a stored file whose
    bytes did not hash to its name."""
    return Coded("store_object_repaired", {"sha": sha})


def path_too_long(root: Path, *, windows: bool, long_paths: bool) -> Coded | None:
    """D8's path-length check of the absolute resolved project `root`: `store_path_too_long
    (<root>)` when the platform is Windows (`windows`), long paths are off (`long_paths`) and
    `len(str(root)) + 92 > 259`; `None` otherwise. The platform and the flag are parameters so a
    test on any platform decides the Windows case."""
    text = str(root)
    if windows and not long_paths and len(text) + PATH_BUDGET > MAX_PATH:
        return Coded("store_path_too_long", {"root": text})
    return None


def long_paths_enabled() -> bool:
    """Whether Windows long paths are on (`HKLM\\...\\FileSystem\\LongPathsEnabled` = 1); any
    read error, and every other platform, counts as off."""
    try:
        # Imported by name: the module exists, and is typed, on Windows only.
        winreg: Any = importlib.import_module("winreg")
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, LONG_PATHS_KEY) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
    except (ImportError, OSError):  # D8: any read error counts as disabled
        return False
    return bool(value == 1)


def object_bytes(record: Mapping[str, Any]) -> tuple[str, bytes]:
    """The SHA and the bytes of a normalised identity projection, computed together (F3-WO1
    review N2: what is hashed is what is written)."""
    data = canonical_json(record)
    return hashlib.sha256(data).hexdigest(), data


class RecordStore:
    """One record store: a project's `<root>/records/` (`at`), or in memory (`in_memory`, for
    `LocalApplication.in_memory()` and the virtual legacy store). Thread-safe; a file store is
    also safe across processes."""

    def __init__(
        self,
        root: Path | None,
        *,
        windows: bool | None = None,
        long_paths: bool | None = None,
    ) -> None:
        self.root = root
        self._windows = sys.platform == "win32" if windows is None else windows
        self._long_paths = long_paths
        self._lock = threading.Lock()
        self._ready = False
        self._memory: sqlite3.Connection | None = None
        self._memory_objects: dict[str, bytes] = {}

    @classmethod
    def at(
        cls, project_root: Path, *, windows: bool | None = None, long_paths: bool | None = None
    ) -> RecordStore:
        """The store of the project at `project_root`, opened at its first operation. `windows`
        and `long_paths` override the platform and the registry flag (for tests)."""
        return cls(Path(project_root), windows=windows, long_paths=long_paths)

    @classmethod
    def in_memory(cls) -> RecordStore:
        """A store whose objects and database live in this process only."""
        return cls(None)

    @property
    def directory(self) -> Path | None:
        """`<root>/records`, or `None` in memory."""
        return None if self.root is None else self.root / RECORDS_DIR

    # ------------------------------------------------------------------------------- opening

    def _open(self) -> None:
        """The first operation's setup (D8, review item 21): the path-length check, then the
        directory and the database. Raises `store_path_too_long` and, for a database of another
        schema, an uncoded `RecordStoreError`."""
        with self._lock:
            if self._ready:
                return
            if self.root is None:
                self._memory = sqlite3.connect(
                    ":memory:", isolation_level=None, check_same_thread=False
                )
                self._create(self._memory)
            else:
                self._open_directory(self.root)
            self._ready = True

    def _open_directory(self, root: Path) -> None:
        """The file store's setup: D8's path-length check on the absolute resolved root, the
        object directory, and the database created or checked."""
        resolved = root.resolve()
        long_paths = long_paths_enabled() if self._long_paths is None else self._long_paths
        refusal = path_too_long(resolved, windows=self._windows, long_paths=long_paths)
        if refusal is not None:
            raise RecordStoreError(refusal)
        (root / RECORDS_DIR / OBJECTS_DIR).mkdir(parents=True, exist_ok=True)
        with self._file_connection() as connection:
            mode = _journal_mode_wal(connection)
            if str(mode).lower() != "wal":
                raise RecordStoreError(None, f"{root} cannot hold a WAL database ({mode})")
            self._create(connection)

    def _create(self, connection: sqlite3.Connection) -> None:
        """The tables and the schema id, in one transaction; an existing database of another
        schema id is refused."""
        connection.execute("BEGIN IMMEDIATE")
        for statement in filter(str.strip, _TABLES.split(";")):
            connection.execute(statement)
        connection.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', ?)", (SCHEMA_ID,)
        )
        schema = connection.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()[0]
        connection.execute("COMMIT")
        if schema != SCHEMA_ID:
            raise RecordStoreError(None, f"record store schema {schema!r}, not {SCHEMA_ID!r}")

    @contextmanager
    def _file_connection(self) -> Iterator[sqlite3.Connection]:
        """A connection to the file store's database (one per unit of work, as T07's)."""
        assert self.directory is not None
        connection = sqlite3.connect(
            self.directory / DATABASE_NAME, timeout=BUSY_TIMEOUT_S, isolation_level=None
        )
        try:
            connection.execute(f"PRAGMA busy_timeout = {int(BUSY_TIMEOUT_S * 1000)}")
            connection.execute("PRAGMA synchronous = FULL")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """A connection for one unit of work, after the first operation's setup."""
        self._open()
        if self._memory is not None:
            with self._lock:
                yield self._memory
            return
        with self._file_connection() as connection:
            yield connection

    @contextmanager
    def _writing(self) -> Iterator[sqlite3.Connection]:
        """One `BEGIN IMMEDIATE` transaction: all of it or, on any exception, none of it. The
        rollback is a `finally`, so it runs on an interrupt too (the in-memory store shares one
        connection) and the exception propagates unchanged (T07 §8.1). A transaction SQLite has
        already ended (SQLITE_FULL, IOERR, NOMEM) is not rolled back again, which would replace
        the exception (F3 ruling round 2, C3)."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            completed = False
            try:
                yield connection
                completed = True
            finally:
                if not completed and connection.in_transaction:
                    connection.execute("ROLLBACK")
            connection.execute("COMMIT")

    # ------------------------------------------------------------------------------- writing

    def register(
        self, outcome: RecordOutcome, *, principal: str, at: str | None = None
    ) -> Registration:
        """Register one identified record (`records.identify`'s outcome) for `principal`: its
        object (written once), its `objects` and `keys` rows, and a `registrations` row holding
        its volatile block and this submission's findings (F3-WO1 review N1). The first
        registration of one (record, volatile block) pair is kept; a later one adds no row.
        An object whose bytes do not hash to its name is replaced (D8): `created` is false and
        the returned findings carry `store_object_repaired(<sha>)`, which the `registrations`
        row never holds. Raises `RecordStoreError` with the outcome's first error when it is
        refused, and `store_object_corrupt` when a corrupt object cannot be replaced (D8,
        Windows)."""
        if outcome.refused or outcome.record_sha256 is None:
            raise RecordStoreError(outcome.errors[0] if outcome.errors else None)
        sha, written = self._add(outcome.record, expected=outcome.record_sha256)
        volatile = dict(outcome.volatile or {})
        findings = sorted(outcome.findings, key=Coded.sort_key)
        row = (
            sha,
            document_sha256(volatile),
            canonical_json(volatile).decode("utf-8"),
            canonical_json([f.as_document() for f in findings]).decode("utf-8"),
            at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            principal,
        )
        with self._writing() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO registrations"
                " (sha, volatile_sha, volatile, findings, at, principal)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                row,
            )
        notices = [repaired(sha)] if written == "repaired" else []
        returned = tuple(sorted([*findings, *notices], key=Coded.sort_key))
        return Registration(sha, written == "created", returned)

    def add(self, record: Mapping[str, Any], *, expected: str | None = None) -> tuple[str, bool]:
        """Store a normalised identity projection without a registration (a copy from another
        store, D8): its object, then its `objects` and `keys` rows. Returns its SHA and whether
        this call wrote the object. A copy for a data lock reads the project store first
        (`StoreStack.adopt`), so a corrupt object there is refused before this is reached. An
        `expected` SHA that is not the record's is a bug (`AssertionError`)."""
        sha, written = self._add(record, expected=expected)
        return sha, written == "created"

    def _add(self, record: Mapping[str, Any], *, expected: str | None) -> tuple[str, Written]:
        """`add`, returning what the write protocol did with the object."""
        sha, data = object_bytes(record)
        if expected is not None and sha != expected:
            raise AssertionError(f"record SHA {expected} does not match its bytes ({sha})")
        written = self._write_object(sha, data)
        self._index(sha, record)
        return sha, written

    def _write_object(self, sha: str, data: bytes) -> Written:
        """D8's write protocol for one object (`data` hashes to `sha`): a valid object is kept, a
        missing one created, one whose bytes do not hash to `sha` replaced (`repaired`)."""
        self._open()
        if self.directory is None:
            with self._lock:
                stored = self._memory_objects.get(sha)
                self._memory_objects[sha] = data
            return _written(sha, stored)
        target = self._object_path(sha)
        found = _written(sha, target.read_bytes() if target.exists() else None)
        if found == "kept":
            return found
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{TMP_PREFIX}{secrets.token_hex(8)}.json")
        _write_synced(temporary, data)
        try:
            os.replace(temporary, target)
        except (PermissionError, FileExistsError):
            # D8, Windows: a reader holds the target open. Another writer's valid target is
            # success; anything else is raised.
            if not target.exists():
                raise
            _verified(sha, target.read_bytes())
            _unlink_quietly(temporary)
            return "kept"
        if os.name != "nt":
            _fsync_directory(target.parent)
        return found

    def _index(self, sha: str, record: Mapping[str, Any]) -> None:
        """The record's `objects` row and its D9 lookup keys, written once."""
        row = (
            sha,
            str(record["record_type"]),
            str(record["id"]),
            str(record["name"]),
            record.get("amount_basis"),
        )
        with self._writing() as connection:
            connection.execute("INSERT OR IGNORE INTO objects VALUES (?, ?, ?, ?, ?)", row)
            connection.executemany(
                "INSERT OR IGNORE INTO keys (sha, scheme, value) VALUES (?, ?, ?)",
                [(sha, scheme, value) for scheme, value in sorted(lookup_keys(sha, record))],
            )

    def _object_path(self, sha: str) -> Path:
        assert self.directory is not None
        return self.directory / OBJECTS_DIR / sha[0:2] / sha[2:4] / f"{sha}.json"

    # ------------------------------------------------------------------------------- reading

    def object_bytes(self, sha: str) -> bytes | None:
        """The verified bytes of object `sha`, or `None` when this store does not hold it.
        Raises `store_object_corrupt` when its bytes do not hash to `sha`."""
        self._open()
        if self.directory is None:
            with self._lock:
                data = self._memory_objects.get(sha)
        else:
            path = self._object_path(sha)
            data = path.read_bytes() if path.is_file() else None
        return None if data is None else _verified(sha, data)

    def record(self, sha: str) -> Mapping[str, Any] | None:
        """The identity projection stored under `sha` (parsed from its verified bytes), or `None`
        when this store does not hold it."""
        data = self.object_bytes(sha)
        return None if data is None else dict(json.loads(data))

    def shas_for(
        self, scheme: str, value: str, *, record_type: str | None = None
    ) -> frozenset[str]:
        """The SHAs of the records (of `record_type`, when given) holding D9 key `scheme:value`."""
        query = "SELECT k.sha FROM keys k JOIN objects o ON o.sha = k.sha"
        query += " WHERE k.scheme = ? AND k.value = ?"
        arguments: tuple[str, ...] = (scheme, value)
        if record_type is not None:
            query += " AND o.record_type = ?"
            arguments += (record_type,)
        with self._connect() as connection:
            return frozenset(row[0] for row in connection.execute(query, arguments))

    def objects(self) -> list[ObjectRow]:
        """Every `objects` row, by SHA."""
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM objects ORDER BY sha").fetchall()
        return [ObjectRow(*row) for row in rows]

    def registrations(self, sha: str) -> list[dict[str, Any]]:
        """The `registrations` rows of `sha` in insertion order, each with its volatile block and
        findings parsed. The first row is the record's first submission; a record's notices are
        read from a row, never from the object (F3-WO1 review N1)."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT sequence, volatile_sha, volatile, findings, at, principal"
                " FROM registrations WHERE sha = ? ORDER BY sequence",
                (sha,),
            ).fetchall()
        return [
            {
                "sequence": sequence,
                "volatile_sha": volatile_sha,
                "volatile": json.loads(volatile),
                "findings": json.loads(findings),
                "at": at,
                "principal": principal,
            }
            for sequence, volatile_sha, volatile, findings, at, principal in rows
        ]

    # -------------------------------------------------------------------------------- rights

    def append_rights(self, row: Mapping[str, Any]) -> int:
        """Append one D11 row to the project register (the `rights` table, append-only), checked
        as a repository row is (`rights.check_row`, `RightsRegisterError`), and return its
        insertion sequence: D11's "latest" is the highest."""
        checked = check_row(row, "rights row")
        with self._writing() as connection:
            cursor = connection.execute(
                f"INSERT INTO rights ({', '.join(ROW_FIELDS)})"
                f" VALUES ({', '.join('?' for _ in ROW_FIELDS)})",
                tuple(checked[name] for name in ROW_FIELDS),
            )
        return int(cursor.lastrowid or 0)

    def rights_rows(self) -> list[dict[str, Any]]:
        """The project register's rows in insertion order, each D11's fields and its
        `sequence`."""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT sequence, {', '.join(ROW_FIELDS)} FROM rights ORDER BY sequence"
            ).fetchall()
        return [dict(zip(("sequence", *ROW_FIELDS), row, strict=True)) for row in rows]

    # ------------------------------------------------------------------------------ rebuilding

    def rebuild(self) -> tuple[Coded, ...]:
        """Rebuild `objects` and `keys` from the object files (D8), skipping temporary files
        (N7). An object whose bytes do not hash to its name is left out of the index and
        returned as `store_object_corrupt(<sha>)`, sorted by SHA; `registrations` and `rights`
        are kept."""
        self._open()
        found: list[Coded] = []
        stored: list[tuple[str, Mapping[str, Any]]] = []
        for sha, data in self._object_files():
            if hashlib.sha256(data).hexdigest() != sha:
                found.append(corrupt(sha))
                continue
            stored.append((sha, json.loads(data)))
        with self._writing() as connection:
            connection.execute("DELETE FROM keys")
            connection.execute("DELETE FROM objects")
        for sha, record in stored:
            self._index(sha, record)
        return tuple(found)

    def _object_files(self) -> Iterator[tuple[str, bytes]]:
        """Every stored object's name and bytes, by SHA, temporary files skipped."""
        if self.directory is None:
            with self._lock:
                items = sorted(self._memory_objects.items())
            yield from items
            return
        for path in sorted((self.directory / OBJECTS_DIR).glob("*/*/*.json")):
            if not path.name.startswith(TMP_PREFIX):
                yield path.stem, path.read_bytes()


def _written(sha: str, stored: bytes | None) -> Written:
    """What writing object `sha` does over the `stored` bytes (`None`: no object): `created`,
    `kept` when they hash to `sha`, else `repaired`."""
    if stored is None:
        return "created"
    return "kept" if hashlib.sha256(stored).hexdigest() == sha else "repaired"


def _verified(sha: str, data: bytes) -> bytes:
    """`data` when it hashes to `sha`; raises `store_object_corrupt(<sha>)` otherwise."""
    if hashlib.sha256(data).hexdigest() != sha:
        raise RecordStoreError(corrupt(sha))
    return data


def _write_synced(path: Path, data: bytes) -> None:
    """Write `data` to a new file `path`, flushed and `fsync`ed."""
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _unlink_quietly(path: Path) -> None:
    """Remove a temporary file whose target is verified; a failure is ignored (N7): the file
    is skipped by a rebuild and by every read."""
    try:
        path.unlink()
    except OSError:
        pass


def _fsync_directory(directory: Path) -> None:
    """`fsync` a directory, so a rename in it is durable (POSIX)."""
    handle = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def _journal_mode_wal(connection: sqlite3.Connection) -> str:
    """`PRAGMA journal_mode = WAL`, retried while busy until `BUSY_TIMEOUT_S`. On a database in
    rollback mode the switch upgrades the read lock it holds to a write lock, and SQLite returns
    `SQLITE_BUSY` on that upgrade rather than call the busy handler, to avoid deadlock; so of two
    processes opening a new store at once, one sees `database is locked` from it (E-F3-8 on CI).
    A database already in WAL answers from its read, at once (F3 ruling round 2, C1)."""
    deadline = time.monotonic() + BUSY_TIMEOUT_S
    while True:
        try:
            return str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0])
        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode != sqlite3.SQLITE_BUSY or time.monotonic() > deadline:
                raise
        time.sleep(0.005)
