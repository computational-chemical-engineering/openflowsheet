"""Experiment records on disk, their artifact rows, and the per-key lock (M02 design note §3.3,
§3.4; ADR 0033 D5, D6).

Files live under `<root>/experiments/<key[0:2]>/<key>/`: `request.json`, `result.json` (iff the
outcome was deterministic), `attempts/<n>.json`, and each attempt's directory `attempts/<n>/` (the
child's working directory: its logs and raw `result.json`). Every write is atomic. **Nothing is
deleted, and a result is written once**: the one permitted update is appending a determinism
finding (§5.3), recorded as a new artifact row.

Each file a job writes is recorded through an injected **`ArtifactSink`** (R-237, design note
§14 B4): the application passes one that writes a row of its `artifacts` table (`kind` ∈
{`experiment_request`, `experiment_result`, `experiment_attempt`}, `name` = the key, `relpath`
relative to the project); tests and the in-memory path pass `ListArtifactSink`. A cache hit is
recorded for the consuming job with `parent_artifact_id` = the producing result's artifact id,
which the store keeps beside the result (`result.artifact_id`, written once) because the sink
assigns it; so call accounting is a query and the store schema does not change. Without a sink the
files are written and nothing is recorded. `adapters` never imports `application`, which sits
above it.

**Concurrency.** `experiments/locks/<key>.lock` is taken with `flock(LOCK_EX | LOCK_NB)`, retried
every 0.2 s with the cooperative check between tries; the kernel drops it when its holder dies, so
there is no stale claim. Two holders of one key are impossible within one project directory on a
local filesystem (network filesystems with unreliable `flock` are a stated limitation, §11).
"""

from __future__ import annotations

import dataclasses
import fcntl
import json
import os
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final, Protocol

from openflowsheet._files import atomic_write_bytes
from openflowsheet.canonical import canonical_json, file_sha256

__all__ = ["EXPERIMENTS_DIR", "LOCK_POLL_S", "ArtifactSink", "ExperimentStore", "ListArtifactSink"]

EXPERIMENTS_DIR: Final = "experiments"
LOCKS_DIR: Final = "locks"
#: §3.4: a held key's lock is tried again this often.
LOCK_POLL_S: Final = 0.2
REQUEST_KIND: Final = "experiment_request"
RESULT_KIND: Final = "experiment_result"
ATTEMPT_KIND: Final = "experiment_attempt"
#: Beside `result.json`: the artifact id its producing record received from the sink.
RESULT_ARTIFACT_FILE: Final = "result.artifact_id"


class ArtifactSink(Protocol):
    """Where an experiment store records the files a job writes (R-237): one call per file,
    returning the artifact id the record received."""

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
    ) -> str: ...


@dataclasses.dataclass
class ListArtifactSink:
    """An `ArtifactSink` that keeps its records in a list (tests and the in-memory path); the id
    of record `i` is `artifact-<i + 1>`."""

    records: list[dict[str, Any]] = dataclasses.field(default_factory=list)

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
        artifact_id = f"artifact-{len(self.records) + 1}"
        self.records.append(
            {
                "artifact_id": artifact_id,
                "job_id": job_id,
                "kind": kind,
                "name": name,
                "relpath": relpath,
                "sha256": sha256,
                "size_bytes": size_bytes,
                "parent_artifact_id": parent_artifact_id,
            }
        )
        return artifact_id


def _atomic_write(path: Path, data: bytes) -> None:
    """Write beside `path`, fsync, rename over it, fsync the directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(path, data)


def encode(document: Any) -> bytes:
    """A record's bytes: its canonical JSON (ADR 0002), so equal records are equal files."""
    return canonical_json(document)


class ExperimentStore:
    """The experiment records of one project directory, and their records in its sink."""

    def __init__(self, root: Path, sink: ArtifactSink | None = None) -> None:
        self.root = root
        self.sink = sink
        self.base = root / EXPERIMENTS_DIR

    # -- paths ---------------------------------------------------------------------------------

    def directory(self, key: str) -> Path:
        return self.base / key[:2] / key

    def request_path(self, key: str) -> Path:
        return self.directory(key) / "request.json"

    def result_path(self, key: str) -> Path:
        return self.directory(key) / "result.json"

    def attempt_path(self, key: str, number: int) -> Path:
        return self.directory(key) / "attempts" / f"{number}.json"

    def attempt_directory(self, key: str, number: int) -> Path:
        return self.directory(key) / "attempts" / str(number)

    def relpath(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    # -- the lock ------------------------------------------------------------------------------

    @contextmanager
    def locked(self, key: str, check: Callable[[], None] | None = None) -> Iterator[None]:
        """Hold `key`'s lock for the body; between tries, the cooperative check may raise."""
        path = self.base / LOCKS_DIR / f"{key}.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if check is not None:
                        check()
                    time.sleep(LOCK_POLL_S)
            yield
        finally:
            os.close(handle)  # closing the descriptor releases the lock

    # -- reads ---------------------------------------------------------------------------------

    def read(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        document: dict[str, Any] = json.loads(path.read_bytes())
        return document

    def result(self, key: str) -> dict[str, Any] | None:
        return self.read(self.result_path(key))

    def attempts(self, key: str) -> list[dict[str, Any]]:
        """Every attempt of `key`, in attempt order."""
        folder = self.directory(key) / "attempts"
        numbers = (
            sorted(int(path.stem) for path in folder.glob("*.json")) if folder.is_dir() else []
        )
        found = [self.read(self.attempt_path(key, number)) for number in numbers]
        return [document for document in found if document is not None]

    def next_attempt(self, key: str) -> int:
        folder = self.directory(key) / "attempts"
        if not folder.is_dir():
            return 1
        return 1 + max((int(path.stem) for path in folder.glob("*.json")), default=0)

    # -- writes --------------------------------------------------------------------------------

    def write_request(self, request: Mapping[str, Any], job_id: str | None) -> None:
        """Write once; a request already on disk must be byte-equal (the key is its hash)."""
        key = request["experiment_key"]
        path = self.request_path(key)
        data = encode(request)
        if path.is_file():
            if path.read_bytes() != data:
                raise RuntimeError(f"experiment {key}: request.json differs from its key's request")
            return
        _atomic_write(path, data)
        self._register(REQUEST_KIND, key, path, job_id)

    def write_attempt(self, attempt: Mapping[str, Any], job_id: str | None) -> None:
        key, number = attempt["experiment_key"], attempt["attempt"]
        path = self.attempt_path(key, number)
        if path.exists():
            raise RuntimeError(f"experiment {key}: attempt {number} exists; attempts are kept")
        _atomic_write(path, encode(attempt))
        self._register(ATTEMPT_KIND, key, path, job_id)

    def write_result(self, result: Mapping[str, Any], job_id: str | None) -> None:
        """Write the deterministic result, once (§3.3: never overwritten)."""
        key = result["experiment_key"]
        path = self.result_path(key)
        if path.exists():
            raise RuntimeError(f"experiment {key}: result.json exists; a result is written once")
        _atomic_write(path, encode(result))
        artifact_id = self._register(RESULT_KIND, key, path, job_id)
        if artifact_id is not None:
            _atomic_write(self.directory(key) / RESULT_ARTIFACT_FILE, artifact_id.encode("utf-8"))

    def append_finding(self, key: str, finding: Mapping[str, Any], job_id: str | None) -> None:
        """§5.3: the one permitted update of a result — a determinism finding appended."""
        path = self.result_path(key)
        document = self.read(path)
        assert document is not None
        document["determinism_findings"] = [*document["determinism_findings"], dict(finding)]
        _atomic_write(path, encode(document))
        self._register(RESULT_KIND, key, path, job_id)

    def record_hit(self, key: str, job_id: str | None) -> None:
        """A cache hit: a record for the consuming job whose parent is the producing result's
        (none when the result was written without a sink)."""
        if self.sink is None:
            return
        marker = self.directory(key) / RESULT_ARTIFACT_FILE
        producing = marker.read_text("utf-8") if marker.is_file() else None
        self._register(RESULT_KIND, key, self.result_path(key), job_id, parent=producing)

    # -- records -------------------------------------------------------------------------------

    def _register(
        self, kind: str, key: str, path: Path, job_id: str | None, *, parent: str | None = None
    ) -> str | None:
        if self.sink is None:
            return None
        return self.sink.record(
            job_id=job_id,
            kind=kind,
            name=key,
            relpath=self.relpath(path),
            sha256=file_sha256(path),
            size_bytes=path.stat().st_size,
            parent_artifact_id=parent,
        )
