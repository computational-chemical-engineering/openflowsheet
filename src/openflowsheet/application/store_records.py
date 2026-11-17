"""The project store's records and errors: what `ProjectStore` raises, writes and returns.

`StoreError` and its coded form (MSG §3.8), the two refusals of job acceptance, the audit,
artifact and ledger rows of the store's tables (T07 design note §7, §9.2, §10.7), the
operator-readable policy file and the `artifacts` table as an experiment store's sink. They sit
directly below `store` (ADR 0076 I-12b); `ProjectStore` and its schema stay there.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from openflowsheet.application.types import ArtifactRef, ProjectPolicy

if TYPE_CHECKING:
    from openflowsheet.application.store import ProjectStore


class StoreError(RuntimeError):
    """A project directory or database that cannot be created or opened as asked.

    MSG §3.8: a *coded* one (`code` set: `project_exists`, `directory_not_empty`,
    `not_a_directory`, `project_id_mismatch`, `not_a_project`) carries the machine message
    `"<code>: <directory>"` as `args[0]`, and its `str()` is the layered text (surface `python`)
    ending in that message. An uncoded one behaves exactly as before MSG.
    """

    def __init__(
        self, *args: object, code: str | None = None, params: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(*args)
        self.code = code
        self.params: Mapping[str, Any] = dict(params or {})
        if code is not None:
            from openflowsheet.messages import audit

            if audit.auditor is not None:  # MSG-G3: the code has an entry
                import sys

                audit.auditor.code(code, sys._getframe(1).f_globals.get("__name__", ""))

    def explanation(self, surface: Literal["python", "cli"] | None = "python") -> dict[str, Any]:
        """The coded error's explanation on `surface` (MSG §4.4)."""
        from openflowsheet.messages.render import RenderContext, render_code

        assert self.code is not None, "only a coded StoreError has an explanation"
        return render_code(self.code, self.params, context=RenderContext(surface=surface))

    def text(self, surface: Literal["python", "cli"] = "python") -> str:
        """The layered text on `surface`; an uncoded error's plain message."""
        if self.code is None:
            return super().__str__()
        from openflowsheet.messages.text import format_text

        return format_text(self.explanation(surface), str(self.args[0]))

    def __str__(self) -> str:
        return self.text("python")


def coded_store_error(code: str, directory: Path, **params: Any) -> StoreError:
    """MSG §3.8: the coded `StoreError` of `code` about `directory`."""
    return StoreError(
        f"{code}: {directory}", code=code, params={"directory": str(directory), **params}
    )


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


class ArtifactTableSink:
    """The `artifacts` table as an experiment store's `ArtifactSink` (M02 design note §14 B4,
    R-237): each `record` is one row, inserted in its own write transaction. The id is the owning
    job (or `nojob`), the kind, the name and the file's stem, with `-<n>` added when a row of that
    id exists (a cache hit or a determinism finding names the result file again)."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

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
        base = f"{job_id if job_id is not None else 'nojob'}:{kind}:{name}:{Path(relpath).stem}"
        with self.store.writing() as connection:
            artifact_id, number = base, 1
            while connection.execute(
                "SELECT 1 FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone():
                number += 1
                artifact_id = f"{base}-{number}"
            row = ArtifactRow(
                artifact_id=artifact_id,
                job_id=job_id,
                kind=kind,
                name=name,
                sha256=sha256,
                size_bytes=size_bytes,
                relpath=relpath,
                parent_artifact_id=parent_artifact_id,
            )
            self.store.register_artifacts(connection, [row])
        return artifact_id


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
