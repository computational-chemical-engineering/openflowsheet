"""`ArtifactService`: the artifact reads, a run's stream table and the job lookup they share
(ADR 0076 I-12d, above `RevisionService`).

`LocalApplication` delegates `get_artifact`, `artifact_bytes` and `get_stream_table` here; their
contract documentation is the facade's. The job lookup (`job`), a job's artifact path
(`artifact_path`) and the display-units parse (`display_units`) are shared with the job service
above.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openflowsheet.application import stream_table
from openflowsheet.application.contract import Projection
from openflowsheet.application.job_records import Job
from openflowsheet.application.jobs.model import TERMINAL_STATUSES
from openflowsheet.application.revision_service import RevisionService
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.store_records import ArtifactRow
from openflowsheet.canonical import document_sha256, first_noncanonical
from openflowsheet.run.bundle import MANIFEST_NAME
from openflowsheet.studies.nlp.replay import MANIFEST as OPTIMIZATION_MANIFEST
from openflowsheet.units.display import DisplayUnits, DisplayUnitsError, parse_display_units

#: MSG §3.4 (FB-03b): a `not_found` on a bundle member lists at most this many member names.
MAX_LISTED_MEMBERS: Final[int] = 64

#: ST note §6.1: `get_stream_table`'s default depth, `MAX_DEPTH`, so that a stream's phases
#: arrive whole (the other views keep `DEFAULT_DEPTH`).
STREAM_TABLE_DEPTH: Final[int] = 12


@dataclass(frozen=True)
class StreamTableQuery:
    """One `get_stream_table` request's projection bounds and display preference, built by the
    facade from its keyword arguments (their documentation and defaults are the facade's)."""

    pointer: str
    depth: int
    cursor: str | None
    limit: int
    display_units: str | None


class ArtifactService:
    """The artifact operations over one caller's `ServiceCore`. Each public method is the
    `LocalApplication` method of the same name, documented there; it takes every argument
    explicitly (the defaults are the facade's)."""

    def __init__(self, core: ServiceCore, revisions: RevisionService) -> None:
        self._core = core
        self._revisions = revisions

    def display_units(self, text: str, operation: str) -> DisplayUnits:
        """ADR 0075 D5, D9: `text` resolved against the declared ambient; a refusal is audited.
        An `invalid_request` points at `/display_units`; an `unsupported` carries its message
        head as `reason` (the code with its kind and unit, X04 decision D-5), which MSG reads."""
        try:
            return parse_display_units(text, self._core.policy.current().ambient_pressure)
        except DisplayUnitsError as error:
            pointer = error.pointer
            detail = {"pointer": pointer} if pointer is not None else {"reason": error.message}
            self._core.refuse(error.api_error, error.message, operation=operation, **detail)

    def job(self, job_id: str, operation: str) -> Job:
        job = self._core.store.get_job(job_id)
        if job is None:
            self._core.refuse("not_found", "no such job", operation=operation, job_id=job_id)
        return job

    def artifact_path(self, output: Any) -> Path:
        row = self._core.store.artifact(output.artifact_id)
        assert row is not None, output.artifact_id
        return self._core.files_root / row.relpath

    def get_artifact(
        self, artifact_id: str, *, pointer: str, depth: int, cursor: str | None, limit: int
    ) -> Projection:
        operation = "get_artifact"
        self._core.authorize(operation)
        self._revisions.check_view(operation, pointer, depth, cursor, limit)
        row = self._artifact_row(artifact_id, operation)
        if row.kind == "replay_bundle":
            members = self._core.store.artifact_children(row.artifact_id)
            # An optimisation record's manifest is its `optimization-manifest.json` (§4.9).
            manifest = [
                member
                for member in members
                if member.name in (MANIFEST_NAME, OPTIMIZATION_MANIFEST)
            ]
            manifest_path = (
                self._core.files_root / manifest[0].relpath
                if manifest
                else self._core.files_root / row.relpath / MANIFEST_NAME
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
            document = _file_document(self._core.files_root / row.relpath)
        return self._revisions.project(
            operation, document, artifact_id, row.sha256, pointer, depth, cursor, limit
        )

    def get_stream_table(self, job_id: str, query: StreamTableQuery) -> Projection:
        operation = "get_stream_table"
        self._core.authorize(operation)
        self._revisions.check_view(operation, query.pointer, query.depth, query.cursor, query.limit)
        units = (
            None
            if query.display_units is None
            else self.display_units(query.display_units, operation)
        )
        job = self.job(job_id, operation)
        if job.status not in TERMINAL_STATUSES:
            self._core.refuse(
                "not_ready",
                f"job {job_id} is {job.status}; its stream table exists once it has ended",
                operation=operation,
                retryable=True,
                job_id=job_id,
                status=job.status,
            )
        bundle = next((o for o in job.outputs if o.kind == "replay_bundle"), None)
        if bundle is None:
            self._core.refuse(
                "not_found",
                f"job {job_id} has no replay bundle",
                operation=operation,
                output="replay_bundle",
                **self._run_outcome(job_id),
            )
        row = self._artifact_row(bundle.artifact_id, operation)
        try:
            document = stream_table.from_bundle(
                self._core.files_root / row.relpath,
                source={"job_id": job_id, "bundle_id": row.artifact_id},
            )
        except stream_table.StreamTableError as error:
            if error.code == "not_found":
                member = error.detail.get("member")
                self._core.refuse(
                    "not_found",
                    f"bundle {row.artifact_id} has no {member}",
                    operation=operation,
                    **{
                        **self._run_outcome(job_id),
                        "bundle_id": row.artifact_id,
                        "member": member,
                        **self._missing_member(f"{row.artifact_id}/{member}"),
                    },
                )
            if error.code == "unsupported":
                self._core.refuse(
                    "unsupported", error.message, operation=operation, job_id=job_id, **error.detail
                )
            self._core.refuse(
                "internal_error",
                error.message,
                operation=operation,
                job_id=job_id,
                bundle_id=row.artifact_id,
                **error.detail,
            )
        if units is not None:
            document = stream_table.displayed(document, units)
        return self._revisions.project(
            operation,
            document,
            f"stream-table:{job_id}",
            document_sha256(document),
            query.pointer,
            query.depth,
            query.cursor,
            query.limit,
        )

    def artifact_bytes(self, artifact_id: str) -> bytes:
        operation = "artifact_bytes"
        self._core.authorize(operation)
        row = self._artifact_row(artifact_id, operation)
        if row.kind == "replay_bundle":
            self._core.refuse(
                "unsupported",
                "a replay bundle is a directory; export its members, `<bundle id>/<file>`, one by "
                "one",
                operation=operation,
                artifact_id=artifact_id,
            )
        return (self._core.files_root / row.relpath).read_bytes()

    def _artifact_row(self, artifact_id: str, operation: str) -> ArtifactRow:
        row = self._core.store.artifact(artifact_id) if isinstance(artifact_id, str) else None
        if row is None:
            self._core.refuse(
                "not_found",
                "no such artifact",
                operation=operation,
                artifact_id=artifact_id,
                **self._missing_member(artifact_id),
            )
        return row

    def _missing_member(self, artifact_id: object) -> dict[str, Any]:
        """MSG §3.4 (FB-03b): for a missing `<bundle id>/<member>` of a bundle with registered
        members, what the bundle does hold — `bundle_id`, `member`, `members` (sorted file
        names, at most `MAX_LISTED_MEMBERS`; `members_total` when cut) and, for a job's bundle
        (`<job_id>:bundle`, `<job_id>:rerun`), `job_id` and the run's `run_outcome` when the job
        recorded one.
        Added detail members only: the message and the existing members are unchanged (I1)."""
        if not isinstance(artifact_id, str):
            return {}
        bundle_id, slash, member = artifact_id.rpartition("/")
        if not slash or not bundle_id or not member:
            return {}
        members = sorted(row.name for row in self._core.store.artifact_children(bundle_id))
        if not members:
            return {}
        found: dict[str, Any] = {
            "bundle_id": bundle_id,
            "member": member,
            "members": members[:MAX_LISTED_MEMBERS],
        }
        if len(members) > MAX_LISTED_MEMBERS:
            # Review S5 (D3-4): a cut list says so, with the full count.
            found["members_total"] = len(members)
        job_id, colon, suffix = bundle_id.rpartition(":")
        if colon and suffix in ("bundle", "rerun") and self._core.store.get_job(job_id) is not None:
            found.update(self._run_outcome(job_id))
        return found

    def _run_outcome(self, job_id: str) -> dict[str, Any]:
        """`job_id` and, when the job recorded one, its run's `run_outcome` (the members
        `_missing_member` gives a job's bundle)."""
        found: dict[str, Any] = {"job_id": job_id}
        worker = self._core.store.worker_result(job_id)
        run = worker.get("run") if isinstance(worker, Mapping) else None
        outcome = run.get("outcome") if isinstance(run, Mapping) else None
        if isinstance(outcome, str):
            found["run_outcome"] = outcome
        return found


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
