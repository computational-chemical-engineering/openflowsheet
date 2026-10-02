"""Programmatic T07 jobs and event streams for the W1 unit tests (design note §5–§6).

These are *constructed* documents for testing the types and the lifecycle checker. They are not
schema fixtures: `tests/fixtures/schemas/` fixtures for `job` and `job-event` are emitted by real
jobs in W4a (design note §5 preamble; R-015), and nothing here is written there.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from openflowsheet.application.types import (
    ArtifactRef,
    EffectiveBudgets,
    Job,
    JobEnding,
    JobEvent,
    JobRequest,
    Progress,
    SolveBody,
)

JOB_ID = "job-000001"
AT = "2026-09-27T12:00:00.000000Z"
LATER = "2026-09-27T12:00:05.000000Z"
DIGEST = "0" * 64


def ref(kind: str, index: int = 0, name: str | None = None) -> ArtifactRef:
    """A reference of `kind`; `index` distinguishes two of the same kind."""
    return ArtifactRef(
        kind=kind,
        artifact_id=f"{JOB_ID}/{kind}-{index}",
        sha256=f"{index:064x}",
        size_bytes=100 + index,
        name=name if name is not None else f"{kind}.json",
    )


def solve_request(key: str = "key-1") -> JobRequest:
    return JobRequest(operation="solve", idempotency_key=key, body=SolveBody(revision_id="rev-1"))


def event(sequence: int, kind: str, **payload: Any) -> JobEvent:
    """A producer event; `ends_job` follows the kind unless given."""
    ends_job = payload.pop("ends_job", kind == "ended")
    return JobEvent(
        job_id=JOB_ID,
        sequence=sequence,
        kind=kind,
        ends_job=ends_job,
        recorded_at=AT,
        **payload,
    )


def opaque(sequence: int, kind: str, *, ends_job: bool, **payload: Any) -> JobEvent:
    """An event of a kind this producer does not know, as a J5 consumer holds it."""
    return JobEvent(
        job_id=JOB_ID,
        sequence=sequence,
        kind=kind,
        ends_job=ends_job,
        recorded_at=AT,
        payload=payload,
    )


def progress(completed: int, stage: str, total: int | None = 6) -> Progress:
    return Progress(completed=completed, total=total, stage=stage)


COMPLETED = JobEnding(status="completed", reason="operation_completed", interruption=None)


def job(**overrides: Any) -> Job:
    """A queued solve job, with `overrides` applied."""
    request = solve_request()
    base = Job(
        job_id=JOB_ID,
        operation="solve",
        request=request,
        request_sha256=request.request_sha256,
        principal_id="local-owner",
        capability_id="local-owner",
        policy_sha256=DIGEST,
        status="queued",
        outputs=(),
        progress=None,
        effective_budgets=EffectiveBudgets(wall_time_s=None, max_property_calls=None),
        cancel_requested=False,
        event_count=1,
        created_at=AT,
    )
    return dataclasses.replace(base, **overrides)


def completed_solve() -> tuple[Job, list[JobEvent]]:
    """A solve that ran all six stages and wrote its bundle: §5.4's three outputs, §6.4's stages."""
    outputs = (ref("solution_certificate"), ref("run_manifest"), ref("replay_bundle", name="b"))
    stages = ("resolve", "bind", "plan", "solve", "verify", "bundle")
    events = [event(0, "accepted"), event(1, "started")]
    for completed, stage in enumerate(stages):
        events.append(event(len(events), "progress", progress=progress(completed, stage)))
    for output in outputs:
        events.append(event(len(events), "output", output=output))
    events.append(event(len(events), "ended", ending=COMPLETED, error=None))
    finished = job(
        status="completed",
        outputs=outputs,
        progress=progress(5, "bundle"),
        event_count=len(events),
        started_at=AT,
        ended_at=LATER,
        ending=COMPLETED,
    )
    return finished, events
