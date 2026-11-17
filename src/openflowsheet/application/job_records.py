"""The job record documents of the application contract v1 (T07 design note §5.4-§5.7, ADR 0019
D2; ADR 0076 I-12a): `Job`, `JobEvent`, `RunResult`, `JobResult` and their parts.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Self

from openflowsheet.application.documents import (
    EVENT_COMMON_MEMBERS,
    checked,
    event_common_validator,
)
from openflowsheet.application.errors import ApiError, ApplicationError, SolveFailedError
from openflowsheet.application.job_requests import JobRequest
from openflowsheet.application.jobs.model import (
    ARTIFACT_KINDS,
    ENDS_JOB,
    EVENT_KINDS,
    EVENT_PAYLOAD,
    PAYLOAD_MEMBERS,
    EndingReason,
    Interruption,
    JobOperation,
    JobStatus,
    TerminalStatus,
)
from openflowsheet.application.transaction_types import error_build, error_document
from openflowsheet.schema_check import _raise_first, validate_document
from openflowsheet.units.display import DisplayUnits

if TYPE_CHECKING:
    from openflowsheet.run.replay import ReplayReport

#: The certificate's own verdicts (ruling round 1 R5): copied into `RunResult`, never mapped.
VerificationStatus = Literal["VERIFIED", "RELAXED", "UNVERIFIED", "FAILED"]
#: `policies.SolvePath` (ruling round 1 R2.4), restated so this module imports no solver code.
SolvePath = Literal["revision_eo", "legacy_eo", "revision_coupled"]


# ============================================================= ArtifactRef, Progress, Ending


@dataclass(frozen=True)
class ArtifactRef:
    """§5.4 (J1). `kind` is a `str`: a consumer keeps a kind it does not know (J5)."""

    kind: str
    artifact_id: str
    sha256: str
    size_bytes: int
    name: str

    @property
    def known(self) -> bool:
        return self.kind in ARTIFACT_KINDS

    def as_document(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "artifact_id": self.artifact_id,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "name": self.name,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        validate_document("job.schema.json#/$defs/artifact_ref", document, consumer=lenient)
        return cls._build(document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            kind=document["kind"],
            artifact_id=document["artifact_id"],
            sha256=document["sha256"],
            size_bytes=document["size_bytes"],
            name=document["name"],
        )


@dataclass(frozen=True)
class Progress:
    """§5.5 and §6.4 (J6): operation-neutral stage counts."""

    completed: int
    total: int | None
    stage: str | None

    def as_document(self) -> dict[str, Any]:
        return {"completed": self.completed, "total": self.total, "stage": self.stage}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            completed=document["completed"], total=document["total"], stage=document["stage"]
        )


@dataclass(frozen=True)
class JobEnding:
    """§5.5 `$defs/job_ending`: how a job ended. The schema ties each reason to its status."""

    status: TerminalStatus
    reason: EndingReason
    interruption: Interruption | None = None

    def as_document(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "interruption": self.interruption}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            status=document["status"],
            reason=document["reason"],
            interruption=document["interruption"],
        )


@dataclass(frozen=True)
class EffectiveBudgets:
    """§5.5: the budgets the job runs under, after the capability and policy resolved them."""

    wall_time_s: float | None = None
    max_property_calls: int | None = None

    def as_document(self) -> dict[str, Any]:
        return {"wall_time_s": self.wall_time_s, "max_property_calls": self.max_property_calls}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            wall_time_s=document["wall_time_s"],
            max_property_calls=document["max_property_calls"],
        )


# ================================================================================ Job §5.5


@dataclass(frozen=True)
class Job:
    """§5.5 (J1, J3). `completed` means the operation ran to its end, never that it verified.

    Cross-field rules — the operation is the request's, the status is the ending's, the outputs
    are the output events' — are the lifecycle checker's (§6.3), not this constructor's, so that
    the checker can be shown a job that breaks them.
    """

    job_id: str
    operation: JobOperation
    request: JobRequest
    request_sha256: str
    principal_id: str
    capability_id: str
    policy_sha256: str
    status: JobStatus
    outputs: tuple[ArtifactRef, ...]
    progress: Progress | None
    effective_budgets: EffectiveBudgets
    cancel_requested: bool
    event_count: int
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    ending: JobEnding | None = None
    error: ApiError | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "operation": self.operation,
            "request": self.request.as_document(),
            "request_sha256": self.request_sha256,
            "principal_id": self.principal_id,
            "capability_id": self.capability_id,
            "policy_sha256": self.policy_sha256,
            "status": self.status,
            "outputs": [output.as_document() for output in self.outputs],
            "progress": self.progress.as_document() if self.progress is not None else None,
            "effective_budgets": self.effective_budgets.as_document(),
            "cancel_requested": self.cancel_requested,
            "event_count": self.event_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "ending": self.ending.as_document() if self.ending is not None else None,
            "error": error_document(self.error),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        """Strict for a producer; `lenient` keeps outputs of kinds this code does not know."""
        reference = "job.schema.json"
        validate_document(reference, document, consumer=lenient)
        return checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            job_id=document["job_id"],
            operation=document["operation"],
            request=JobRequest._build(document["request"]),
            request_sha256=document["request_sha256"],
            principal_id=document["principal_id"],
            capability_id=document["capability_id"],
            policy_sha256=document["policy_sha256"],
            status=document["status"],
            outputs=tuple(ArtifactRef._build(output) for output in document["outputs"]),
            progress=(
                Progress._build(document["progress"]) if document["progress"] is not None else None
            ),
            effective_budgets=EffectiveBudgets._build(document["effective_budgets"]),
            cancel_requested=document["cancel_requested"],
            event_count=document["event_count"],
            created_at=document["created_at"],
            started_at=document["started_at"],
            ended_at=document["ended_at"],
            ending=(
                JobEnding._build(document["ending"]) if document["ending"] is not None else None
            ),
            error=error_build(document["error"]),
        )


# =========================================================================== JobEvent §5.6


@dataclass(frozen=True)
class JobEvent:
    """§5.6 (J2, J5, J6). Whether the event ends the job is `ends_job`, never `kind`.

    For a producer kind, the payload members are exactly its branch's (`EVENT_PAYLOAD`), and
    `ends_job` is the kind's (`ENDS_JOB`); the constructor refuses anything else. An event of a
    kind this code does not know exists only as a consumer read it (`from_document(lenient=True)`):
    its payload is kept whole in `payload`, unread.
    """

    job_id: str
    sequence: int
    kind: str
    ends_job: bool
    recorded_at: str
    progress: Progress | None = None
    output: ArtifactRef | None = None
    ending: JobEnding | None = None
    error: ApiError | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.known:
            if any(getattr(self, member) is not None for member in PAYLOAD_MEMBERS):
                raise ValueError(f"an event of unknown kind {self.kind!r} has no typed payload")
            return
        if self.payload:
            raise ValueError(f"a {self.kind!r} event keeps no opaque payload")
        if self.ends_job != ENDS_JOB[self.kind]:
            raise ValueError(f"a {self.kind!r} event has ends_job = {ENDS_JOB[self.kind]}")
        carried = EVENT_PAYLOAD[self.kind]
        for member in PAYLOAD_MEMBERS:
            value = getattr(self, member)
            if member not in carried and value is not None:
                raise ValueError(f"a {self.kind!r} event carries no {member!r}")
            if member in carried and member != "error" and value is None:
                raise ValueError(f"a {self.kind!r} event carries {member!r}")

    @property
    def known(self) -> bool:
        return self.kind in EVENT_KINDS

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "job_id": self.job_id,
            "sequence": self.sequence,
            "kind": self.kind,
            "ends_job": self.ends_job,
            "recorded_at": self.recorded_at,
        }
        if not self.known:
            document.update(self.payload)
            return document
        for member in EVENT_PAYLOAD[self.kind]:
            value = getattr(self, member)
            document[member] = value.as_document() if value is not None else None
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        """Strict: the producer schema. `lenient`: J5's consumer rule (module docstring)."""
        reference = "job-event.schema.json"
        if lenient and document.get("kind") not in EVENT_KINDS:
            _raise_first(reference, event_common_validator(), document)
            return cls(
                **{member: document[member] for member in EVENT_COMMON_MEMBERS},
                payload={
                    key: value for key, value in document.items() if key not in EVENT_COMMON_MEMBERS
                },
            )
        validate_document(reference, document, consumer=lenient)
        return checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        progress = document.get("progress")
        output = document.get("output")
        ending = document.get("ending")
        return cls(
            job_id=document["job_id"],
            sequence=document["sequence"],
            kind=document["kind"],
            ends_job=document["ends_job"],
            recorded_at=document["recorded_at"],
            progress=Progress._build(progress) if progress is not None else None,
            output=ArtifactRef._build(output) if output is not None else None,
            ending=JobEnding._build(ending) if ending is not None else None,
            error=error_build(document.get("error")),
        )


# ========================================================================== RunResult §5.7


@dataclass(frozen=True)
class RunFailure:
    """ADR 0058 D5 (MSG §3.4, §4.8): why a solve did not converge, read from its failure bundle.

    `outcome`, `taxonomy`, `message` (`observations.message`, verbatim), `implicated`
    (`implicated_sources`) and `suggested_actions` (each `action`) are the stored failure
    bundle's; `code` is the explained code and `chain` the codes outer → inner; `params` the
    merged params (a quantity as `{value, unit, kind}`); `failure_bundle` the artifact id of
    `failure-bundle.json`. Derived on read, never stored; `str()` is the layered text.
    """

    outcome: str
    taxonomy: str
    message: str | None
    code: str
    chain: tuple[str, ...]
    implicated: tuple[str, ...]
    suggested_actions: tuple[str, ...]
    failure_bundle: str
    params: Mapping[str, Any]
    explanation: Mapping[str, Any]

    def as_document(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "taxonomy": self.taxonomy,
            "message": self.message,
            "code": self.code,
            "chain": list(self.chain),
            "implicated": list(self.implicated),
            "suggested_actions": list(self.suggested_actions),
            "failure_bundle": self.failure_bundle,
            "params": copy.deepcopy(dict(self.params)),
            "explanation": copy.deepcopy(dict(self.explanation)),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        validate_document("run-result.schema.json#/$defs/run_failure", document)
        return cls._build(document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            outcome=document["outcome"],
            taxonomy=document["taxonomy"],
            message=document["message"],
            code=document["code"],
            chain=tuple(document["chain"]),
            implicated=tuple(document["implicated"]),
            suggested_actions=tuple(document["suggested_actions"]),
            failure_bundle=document["failure_bundle"],
            params=dict(document["params"]),
            explanation=dict(document["explanation"]),
        )

    def __str__(self) -> str:
        """MSG §4.5: the layered text; `Details:` is `<observations.message> — <failure bundle
        artifact id>` (the outcome when the bundle recorded no message)."""
        from openflowsheet.messages.text import format_text

        return format_text(
            self.explanation, f"{self.message or self.outcome} — {self.failure_bundle}"
        )


def _failure_document(failure: RunFailure | None) -> dict[str, Any] | None:
    return failure.as_document() if failure is not None else None


@dataclass(frozen=True)
class RunResult:
    """§5.7: what a solve job produced. `job_status` is not `verification_status`.

    `failure` (ADR 0058 D5) is non-null iff `outputs` holds a `failure_bundle`; it says why the
    solve did not converge. `error` stays the operational failure (R-095). Verification is
    separate: a `CONVERGED` run whose certificate is `FAILED` has no `failure`.
    """

    job_id: str
    run_id: str | None
    revision_id: str
    revision_content_sha256: str
    policy_id: str
    policy_sha256: str | None
    check_policy_sha256: str | None
    job_status: TerminalStatus
    outcome: str | None
    verification_status: VerificationStatus | None
    structural_sha256: str | None
    outputs: tuple[ArtifactRef, ...]
    error: ApiError | None = None
    solve_path: SolvePath = "revision_eo"
    failure: RunFailure | None = None

    def __post_init__(self) -> None:
        certified = any(output.kind == "solution_certificate" for output in self.outputs)
        if self.verification_status is not None and not certified:
            raise ValueError(
                "verification_status is copied from a solution certificate, and no "
                "solution_certificate output exists (§5.7)"
            )
        if self.failure is not None and not any(
            output.kind == "failure_bundle" for output in self.outputs
        ):
            raise ValueError(
                "failure is read from a failure bundle, and no failure_bundle output exists "
                "(ADR 0058 D5)"
            )

    def raise_for_outcome(self) -> Self:
        """Raise unless the solve ran to its end and wrote no failure bundle; return `self`, so
        calls chain (MSG §3.4). An operational `error` raises `ApplicationError`; a `failure`,
        or a job that did not complete, raises `SolveFailedError`. Verification is separate: a
        converged run whose certificate is not `VERIFIED` does not raise."""
        if self.error is not None:
            raise ApplicationError(self.error)
        if self.failure is not None or self.job_status != "completed":
            raise SolveFailedError(self)
        return self

    def as_document(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_id": self.run_id,
            "revision_id": self.revision_id,
            "revision_content_sha256": self.revision_content_sha256,
            "policy_id": self.policy_id,
            "policy_sha256": self.policy_sha256,
            "check_policy_sha256": self.check_policy_sha256,
            "solve_path": self.solve_path,
            "job_status": self.job_status,
            "outcome": self.outcome,
            "verification_status": self.verification_status,
            "structural_sha256": self.structural_sha256,
            "outputs": [output.as_document() for output in self.outputs],
            "error": error_document(self.error),
            "failure": _failure_document(self.failure),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        reference = "run-result.schema.json"
        validate_document(reference, document, consumer=lenient)
        return checked(
            reference,
            lambda d: cls(
                job_id=d["job_id"],
                run_id=d["run_id"],
                revision_id=d["revision_id"],
                revision_content_sha256=d["revision_content_sha256"],
                policy_id=d["policy_id"],
                policy_sha256=d["policy_sha256"],
                check_policy_sha256=d["check_policy_sha256"],
                job_status=d["job_status"],
                outcome=d["outcome"],
                verification_status=d["verification_status"],
                structural_sha256=d["structural_sha256"],
                outputs=tuple(ArtifactRef._build(output) for output in d["outputs"]),
                error=error_build(d["error"]),
                solve_path=d["solve_path"],
                failure=RunFailure._build(d["failure"]) if d["failure"] is not None else None,
            ),
            document,
        )


# ======================================================================= JobResult (R4)


def _replay_report_build(document: Mapping[str, Any]) -> ReplayReport:
    """The inverse of `ReplayReport.as_document` for a schema-valid document."""
    from openflowsheet.run.bundle import BundleIntegrity
    from openflowsheet.run.replay import ReplayReport

    integrity = document["integrity"]
    return ReplayReport(
        mode=document["mode"],
        verdict=document["verdict"],
        integrity=BundleIntegrity(
            ok=integrity["ok"],
            missing=tuple(integrity["missing"]),
            tampered=tuple(integrity["tampered"]),
            unexpected=tuple(integrity["unexpected"]),
        ),
        recorded_environment=dict(document["recorded_environment"]),
        current_environment=dict(document["current_environment"]),
        reasons=tuple(document["reasons"]),
        differences=tuple(document["differences"]),
        bitwise_floats=document["bitwise_floats"],
        verdict_changed_near_threshold=tuple(document["verdict_changed_near_threshold"]),
    )


@dataclass(frozen=True)
class JobResult:
    """§4.2 as amended by ruling round 1 R4 (`job.schema.json#/$defs/job_result`).

    `run_result` is present iff the operation is `solve` (a failed or cancelled solve has one
    too); `replay_report` only for a `reproduce` whose report was produced; `error` is the job's.
    `experiment` (ADR 0033 D9) is an `experiment` job's answer and only its: the deterministic
    `result`, or the last `attempt` of a transient outcome, or `None` for a job that ended before
    any attempt was recorded (cancelled while queued). `surrogate_study` (ADR 0037 D6) is a
    `surrogate_study` job's answer and only its, `None` when the job ended before its study did.
    `optimization` (ADR 0071, OPT design §4.10) is an `optimize` job's report and only its,
    `None` when the job ended without one. `display_units` (ADR 0075 D7.4–D7.5) is the request's
    resolved display preference, echoed iff the request carried one; the result's explanations
    were rendered under it.
    """

    operation: JobOperation
    run_result: RunResult | None
    replay_report: ReplayReport | None
    error: ApiError | None
    experiment: Mapping[str, Any] | None = None
    surrogate_study: Mapping[str, Any] | None = None
    optimization: Mapping[str, Any] | None = None
    display_units: DisplayUnits | None = None

    def __post_init__(self) -> None:
        if (self.run_result is not None) != (self.operation == "solve"):
            raise ValueError("a job result carries a run result iff its operation is 'solve'")
        if self.replay_report is not None and self.operation != "reproduce":
            raise ValueError("only a 'reproduce' job result carries a replay report")
        if self.experiment is not None and self.operation != "experiment":
            raise ValueError("only an 'experiment' job result carries an experiment record")
        if self.surrogate_study is not None and self.operation != "surrogate_study":
            raise ValueError("only a 'surrogate_study' job result carries a study answer")
        if self.optimization is not None and self.operation != "optimize":
            raise ValueError("only an 'optimize' job result carries an optimization report")

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "operation": self.operation,
            "run_result": self.run_result.as_document() if self.run_result is not None else None,
            "replay_report": (
                self.replay_report.as_document() if self.replay_report is not None else None
            ),
            "error": error_document(self.error),
        }
        if self.operation == "experiment":
            document["experiment"] = (
                copy.deepcopy(dict(self.experiment)) if self.experiment is not None else None
            )
        if self.operation == "surrogate_study":
            document["surrogate_study"] = (
                copy.deepcopy(dict(self.surrogate_study))
                if self.surrogate_study is not None
                else None
            )
        if self.operation == "optimize":
            document["optimization"] = (
                copy.deepcopy(dict(self.optimization)) if self.optimization is not None else None
            )
        if self.display_units is not None:
            document["display_units"] = self.display_units.as_document()
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        reference = "job.schema.json#/$defs/job_result"
        validate_document(reference, document, consumer=lenient)
        return checked(
            reference,
            lambda d: cls(
                operation=d["operation"],
                run_result=(
                    RunResult.from_document(d["run_result"], lenient=lenient)
                    if d["run_result"] is not None
                    else None
                ),
                replay_report=(
                    _replay_report_build(d["replay_report"])
                    if d["replay_report"] is not None
                    else None
                ),
                error=error_build(d["error"]),
                experiment=d.get("experiment"),
                surrogate_study=d.get("surrogate_study"),
                optimization=d.get("optimization"),
                display_units=_display_units_build(d.get("display_units")),
            ),
            document,
        )


def _display_units_build(document: Mapping[str, Any] | None) -> DisplayUnits | None:
    """A `display_units` echo → its `DisplayUnits`; the ambient is non-null iff a gauge unit is
    in the map, which the schema cannot state (ADR 0075 D5.4)."""
    if document is None:
        return None
    ambient = document["ambient_pressure"]
    units = DisplayUnits(document["units"], None if ambient is None else float(ambient["value"]))
    if units.as_document() != document:
        raise ValueError("display_units: ambient_pressure is set iff a gauge unit is in the map")
    return units
