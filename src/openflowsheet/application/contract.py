"""The application contract's frozen protocol (T07 design note §4, ADR 0019 D1, D5).

`Application` is `docs/interfaces-frozen.md` §1 verbatim: names, parameter names, order, arity and
result-type names, now annotated (the `CompiledProblem` precedent). `JobControl` (§4.1, ADR 0019)
is W4a's; `Inspection` and `Projection` are W5a's.

**Errors are one shape.** A non-domain outcome — a refusal, a missing object, a defect — is raised
as `ApplicationError` carrying an `ApiError` (§5.8; both in `application.errors`, ADR 0076 I-9). A
domain outcome is *returned*: a conflicted or rejected transaction, an `INVALID` report, a
non-converged solve, a cancelled job.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
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
        SolvePolicyRegistration,
        SolvePolicyView,
        SubmitResult,
    )
    from openflowsheet.application.job_records import Job, JobEvent, JobResult, RunResult
    from openflowsheet.application.job_requests import JobRequest
    from openflowsheet.application.jobs.model import JobStatus
    from openflowsheet.application.policy_types import (
        AmbientPressureResult,
        GrantResult,
        ProjectPolicy,
        ReplayPolicy,
        RevokeResult,
    )
    from openflowsheet.application.record_types import (
        RecordPage,
        RecordRegistrationResult,
        RecordValidationReport,
        RecordView,
        RightsAssessmentResult,
    )
    from openflowsheet.application.transaction_types import (
        Branch,
        BranchResult,
        Change,
        SemanticDiff,
        TransactionResult,
    )
    from openflowsheet.application.validation_report import Task, ValidationReport
    from openflowsheet.run.replay import ReplayReport


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

    def get_job_result(self, job_id: str, *, display_units: str | None = None) -> JobResult: ...


class Inspection(Protocol):
    """§4.1, new under ADR 0019: the project, its models, revisions, structure and artifacts.
    Every method is read-only (`read`); every document comes back as a bounded `Projection`.
    `list_audit` is ADR 0019 Amendment 3's (A3.3): the audit, by `seq`; another principal's rows,
    or all principals', need `policy` as well. `explain` is ADR 0058 D7's: a message-catalogue
    entry, which reads no project state. `get_stream_table` is ADR 0068's (ADR 0019 Amendment
    13): an ended job's stream table and energy summary, computed on read from its bundle.
    `list_capabilities` and `check_admission` are ADR 0060 D11's (ADR 0019 Amendment 7): the
    extension registry's descriptors, and D5's admission verdict on a (unit, method, definition)
    pair; both read the registry, not the project."""

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

    def get_stream_table(
        self,
        job_id: str,
        *,
        pointer: str = "",
        depth: int = 12,
        cursor: str | None = None,
        limit: int = 50,
        display_units: str | None = None,
    ) -> Projection: ...

    def list_audit(
        self,
        *,
        principal_id: str | None = None,
        operation: str | None = None,
        order: AuditOrder = "ascending",
        cursor: str | None = None,
        limit: int = 50,
    ) -> Page[AuditRecord]: ...

    def explain(self, code: str) -> MessageEntry: ...

    def list_capabilities(
        self,
        *,
        kind: str | Sequence[str] | None = None,
        id_prefix: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CapabilityPage: ...

    def check_admission(
        self,
        *,
        pair: Mapping[str, Any] | None = None,
        revision: Mapping[str, Any] | None = None,
    ) -> AdmissionReport: ...


class Records(Protocol):
    """ADR 0061 D13 (ADR 0019 Amendment 8): the component-data record store of the project,
    read through `[project store, legacy store]` (D8), and its rights register (D11).

    `search_records` lists the records a D9 key matches (every record without a key) with D9's
    resolution over them; `get_record` reads one by SHA; `register_record` stores a record, or
    the records of a user file (D12), idempotently by content; `validate_record` runs D7, and
    the reaction checks, without storing; `assess_rights` appends a project register row
    (right `policy`). The writes are audited."""

    def search_records(
        self,
        *,
        key: str | None = None,
        scheme: str | None = None,
        record_type: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> RecordPage: ...

    def get_record(self, record_sha256: str) -> RecordView: ...

    def register_record(
        self,
        *,
        record: Mapping[str, Any] | None = None,
        file: Mapping[str, Any] | None = None,
        defaults: Mapping[str, Any] | None = None,
    ) -> RecordRegistrationResult: ...

    def validate_record(
        self,
        *,
        record: Mapping[str, Any] | None = None,
        records: Sequence[str | Mapping[str, Any]] | None = None,
        components: Mapping[str, str] | None = None,
        reactions: Sequence[Mapping[str, Any]] | None = None,
    ) -> RecordValidationReport: ...

    def assess_rights(
        self,
        *,
        source_id: str,
        record_sha256: str,
        scope: str,
        assessment: str,
        basis: str,
        conditions: str | None = None,
    ) -> RightsAssessmentResult: ...


class Branches(Protocol):
    """ADR 0078 D2 (ADR 0019 Amendment 18): named refs of the project store. A branch is a
    name and the revision it points at; `head` is the main line and reserved. `list_branches`
    lists `head` first, then the branches by name; `create_branch` and `delete_branch` are
    idempotent by key and answer a stale or occupied ref with the domain result `conflict`. A
    commit on a branch is `commit_change` with `Change.branch`; promoting it is `commit_change`
    on `head` with `restore_from` its tip. No stored document names a branch (C7)."""

    def list_branches(self, *, cursor: str | None = None, limit: int = 50) -> Page[Branch]: ...

    def create_branch(
        self, *, name: str, revision_id: str, idempotency_key: str
    ) -> BranchResult: ...

    def delete_branch(
        self, *, name: str, expected_revision: str, idempotency_key: str
    ) -> BranchResult: ...


class SolvePolicies(Protocol):
    """ADR 0078 D4 (ADR 0019 Amendment 18): project solve policies. A project registers a
    solve-policy document under a `user.` id once (`draft`); the id is never re-bound, and a job
    names it as it names an offered policy. Registration checks every member the schema leaves
    open against the solver's registries, so an unknown value is refused there, never at run
    time. A policy changes how the solver searches, never what the verifier accepts."""

    def register_solve_policy(
        self, *, policy: Mapping[str, Any], idempotency_key: str
    ) -> SolvePolicyRegistration: ...

    def get_solve_policy(self, *, policy_id: str) -> SolvePolicyView: ...


class Administration(Protocol):
    """ADR 0078 D5 (ADR 0019 Amendment 18): in-band policy administration, right `policy`.
    `get_policy` reads the policy in force. The three writes need the project operator's switch
    (`openflowsheet project administration on`), are refused on a server bound beyond loopback,
    and never grant more than the caller holds; each is audited and ledgered, and a grant's
    token is returned once, never stored."""

    def get_policy(self) -> ProjectPolicy: ...

    def grant_capability(
        self,
        *,
        principal_id: str,
        idempotency_key: str,
        rights: Sequence[str] | None = None,
        limits: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        note: str | None = None,
        capability_id: str | None = None,
    ) -> GrantResult: ...

    def revoke_capability(self, *, capability_id: str, idempotency_key: str) -> RevokeResult: ...

    def set_ambient_pressure(
        self, *, value: float | None, idempotency_key: str, unit: str | None = None
    ) -> AmbientPressureResult: ...
