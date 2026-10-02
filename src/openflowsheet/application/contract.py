"""The application contract's error and its frozen protocol (T07 design note §4, ADR 0019 D1, D5).

`Application` is `docs/interfaces-frozen.md` §1 verbatim: names, parameter names, order, arity and
result-type names, now annotated (the `CompiledProblem` precedent). `JobControl` (§4.1, ADR 0019)
is W4a's; `Inspection` and `Projection` are W5a's.

**Errors are one shape.** A non-domain outcome — a refusal, a missing object, a defect — is raised
as `ApplicationError` carrying an `ApiError` (§5.8). A domain outcome is *returned*: a conflicted
or rejected transaction, an `INVALID` report, a non-converged solve, a cancelled job.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from openflowsheet.application.types import ApiError, ApiErrorCode

if TYPE_CHECKING:
    from openflowsheet.application.jobs.model import JobStatus
    from openflowsheet.application.types import (
        Change,
        Job,
        JobEvent,
        JobRequest,
        JobResult,
        JobWait,
        ModelRegistryView,
        ProjectSummary,
        ReplayPolicy,
        RevisionSummary,
        RunResult,
        SemanticDiff,
        SubmitResult,
        TransactionResult,
    )
    from openflowsheet.application.validation import Task, ValidationReport
    from openflowsheet.run.replay import ReplayReport


class ApplicationError(Exception):
    """§4.2: a non-domain outcome of a contract call. `error` is the typed `ApiError`."""

    def __init__(self, error: ApiError) -> None:
        super().__init__(f"{error.code}: {error.message}")
        self.error = error

    @property
    def code(self) -> ApiErrorCode:
        return self.error.code


def api_error(
    code: ApiErrorCode, message: str, *, retryable: bool = False, **detail: Any
) -> ApplicationError:
    """An `ApplicationError` of `code`, ready to raise."""
    return ApplicationError(
        ApiError(code=code, message=message, retryable=retryable, detail=detail)
    )


class Application(Protocol):
    """Frozen, `docs/interfaces-frozen.md` §1 — verbatim (ADR 0019 D1)."""

    def validate(self, revision_id: str, task: Task) -> ValidationReport: ...

    def commit_change(
        self, change: Change, expected_revision: str | None, idempotency_key: str
    ) -> TransactionResult: ...

    def solve(self, revision_id: str, policy_id: str) -> RunResult: ...

    def reproduce(
        self, bundle_path: str | os.PathLike[str], policy: ReplayPolicy
    ) -> ReplayReport: ...


@dataclass(frozen=True)
class Page[T]:
    """One page of a list (§4.1, §11.4): the items, and the cursor of the next page, or `None`
    when this is the last. A cursor is opaque to the caller."""

    items: tuple[T, ...]
    next_cursor: str | None

    def as_document(self, item: Callable[[T], Any]) -> dict[str, Any]:
        """`{items, next_cursor}`, each item written by `item` (normally its `as_document`)."""
        return {"items": [item(entry) for entry in self.items], "next_cursor": self.next_cursor}


@dataclass(frozen=True)
class Projection:
    """§11.4: a bounded view of one document at an RFC 6901 `pointer`.

    `subject_id` names the document (a revision or an artifact id). `sha256` is that of the
    *whole* document as stored — a revision's canonical bytes, an artifact's file bytes, a
    bundle's directory hash — so two views of one document are told from views of two. `value`
    is the target, with objects deeper than the depth elided and long nested arrays cut; an array
    target is paged, and `next_cursor` fetches its next page. `truncated`: the size cap forced a
    smaller depth than the one asked for. The Python method returns the raw text;
    `operations.project_response` bounds it for every transport (§10.4).
    """

    subject_id: str
    pointer: str
    sha256: str
    value: Any
    truncated: bool
    next_cursor: str | None

    def as_document(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "pointer": self.pointer,
            "sha256": self.sha256,
            "value": self.value,
            "truncated": self.truncated,
            "next_cursor": self.next_cursor,
        }


class JobControl(Protocol):
    """§4.1, new under ADR 0019: jobs — submit, read, list, wait, cancel, result."""

    def submit_job(self, request: JobRequest) -> SubmitResult: ...

    def get_job(self, job_id: str) -> Job: ...

    def list_jobs(
        self, *, status: JobStatus | None = None, cursor: str | None = None, limit: int = 50
    ) -> Page[Job]: ...

    def list_job_events(
        self, job_id: str, *, after_sequence: int = -1, limit: int = 100
    ) -> Page[JobEvent]: ...

    def wait_job(
        self, job_id: str, *, after_sequence: int = -1, timeout_s: float = 20.0
    ) -> JobWait: ...

    def cancel_job(self, job_id: str) -> Job: ...

    def get_job_result(self, job_id: str) -> JobResult: ...


class Inspection(Protocol):
    """§4.1, new under ADR 0019: the project, its models, revisions, structure and artifacts.
    Every method is read-only (`read`); every document comes back as a bounded `Projection`."""

    def get_project(self) -> ProjectSummary: ...

    def list_models(self) -> ModelRegistryView: ...

    def list_revisions(
        self, *, cursor: str | None = None, limit: int = 50
    ) -> Page[RevisionSummary]: ...

    def get_revision(
        self,
        revision_id: str,
        *,
        pointer: str = "",
        depth: int = 4,
        cursor: str | None = None,
        limit: int = 50,
    ) -> Projection: ...

    def diff_revisions(self, from_revision: str, to_revision: str) -> SemanticDiff: ...

    def inspect_structure(
        self,
        revision_id: str,
        *,
        pointer: str = "",
        depth: int = 4,
        cursor: str | None = None,
        limit: int = 50,
    ) -> Projection: ...

    def preview_change(
        self, change: Change, expected_revision: str | None
    ) -> TransactionResult: ...

    def get_artifact(
        self,
        artifact_id: str,
        *,
        pointer: str = "",
        depth: int = 4,
        cursor: str | None = None,
        limit: int = 50,
    ) -> Projection: ...
