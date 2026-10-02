"""ADR 0008 A1 (d) for the HTTP consumer: unknown kinds pass, and J5's member ends the job.

Item (d) of Amendment 1 C6 (`test_t07_adr0008_jobs.py` holds (a)–(c)): each shipped consumer
ignores an output and an event of unknown kind without error, and recognizes an unknown-kind event
that ends the job through J5's member, `ends_job` (design note §5.6). This module is the HTTP
binding's part (W6a); it sits beside that module because W6's other bindings add theirs at the
same time.

The job is written as a *newer producer* would write it: accepted and started through the store,
then an event of a kind this code does not know, an `output` whose reference is of an unknown
artifact kind, and an unknown-kind event with `ends_job: true` that ends it. Every job read over
HTTP (`get_job`, `list_job_events`, `wait_job`, `get_job_result`) must answer 200 with the
unknown members carried whole; the lifecycle checker, as a client over HTTP runs it, must accept
the stream and find its end through `ends_job`; and each answer must equal `dispatch`'s as the
same principal.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit
from test_t07_w6a_http import CAPABILITY, PRINCIPAL, Served, direct_call, http_call

from openflowsheet.application.jobs.model import check_lifecycle
from openflowsheet.application.types import (
    ArtifactRef,
    EffectiveBudgets,
    Job,
    JobEnding,
    JobEvent,
    JobRequest,
    SolveBody,
)
from openflowsheet.canonical import canonical_json

pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)

AT = "2026-09-27T12:00:00.000000Z"
UNKNOWN_OUTPUT = ArtifactRef(
    kind="hologram_v9",
    artifact_id="job-000001:bundle/hologram.bin",
    sha256="a" * 64,
    size_bytes=7,
    name="hologram.bin",
)


@pytest.fixture
def served(tmp_path: Path) -> Iterator[Served]:
    pytest.importorskip("starlette")
    pytest.importorskip("httpx")
    from openflowsheet.application.bindings import http

    project = Served(http, tmp_path / "project")
    yield project
    project.close()


def _newer_producers_job(served: Served) -> str:
    owner = served.owner
    revision = commit(owner, CORPUS["SYN-001-nominal"]())
    job, replayed = owner.store.accept_job(
        JobRequest("solve", "from-a-newer-producer", SolveBody(revision)),
        principal_id=PRINCIPAL,
        capability_id=CAPABILITY,
        policy_sha256=owner.policy.policy_sha256,
        owner_instance=owner.owner_instance,
        effective_budgets=EffectiveBudgets(),
    )
    assert not replayed
    assert owner.store.start_job(job.job_id, owner_instance=owner.owner_instance)
    assert job.job_id == "job-000001"
    stream = (
        JobEvent(job.job_id, 2, "note_v2", False, AT, payload={"text": "a newer note"}),
        JobEvent(job.job_id, 3, "output", False, AT, output=UNKNOWN_OUTPUT),
        JobEvent(job.job_id, 4, "ended_v2", True, AT, payload={"verdict": "done"}),
    )
    ending = JobEnding(status="completed", reason="operation_completed")
    with owner.store.writing() as connection:
        for event in stream:
            connection.execute(
                "INSERT INTO events (job_id, sequence, kind, ends_job, document)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    event.job_id,
                    event.sequence,
                    event.kind,
                    int(event.ends_job),
                    canonical_json(event.as_document()),
                ),
            )
        connection.execute(
            "UPDATE jobs SET status = 'completed', outputs = ?, ended_at = ?, ending = ?"
            " WHERE job_id = ?",
            (
                canonical_json([UNKNOWN_OUTPUT.as_document()]),
                AT,
                canonical_json(ending.as_document()),
                job.job_id,
            ),
        )
    return job.job_id


def test_d_the_http_consumer_ignores_unknown_kinds_and_honours_ends_job(served: Served) -> None:
    job_id = _newer_producers_job(served)
    view = served.view()
    reads: list[tuple[str, dict[str, Any]]] = [
        ("get_job", {"job_id": job_id}),
        ("list_job_events", {"job_id": job_id}),
        ("wait_job", {"job_id": job_id, "after_sequence": 3, "timeout_s": 0}),
        ("get_job_result", {"job_id": job_id}),
    ]
    answers = {}
    for name, request in reads:
        status, document = http_call(served, name, request)
        assert status == 200, (name, document)
        assert (status, document) == direct_call(view, name, request), name
        answers[name] = document

    job = answers["get_job"]
    assert job["status"] == "completed"
    assert job["outputs"] == [UNKNOWN_OUTPUT.as_document()], "an unknown output kind, kept whole"
    events = answers["list_job_events"]["items"]
    assert [event["kind"] for event in events] == [
        "accepted",
        "started",
        "note_v2",
        "output",
        "ended_v2",
    ]
    assert events[2]["text"] == "a newer note", "an unknown event's payload, kept whole"
    assert events[3]["output"]["kind"] == "hologram_v9"
    waited = answers["wait_job"]
    assert waited["ended"] is True
    assert [event["kind"] for event in waited["events"]] == ["ended_v2"]
    result = answers["get_job_result"]
    assert result["run_result"]["job_status"] == "completed"
    assert result["run_result"]["outputs"] == [UNKNOWN_OUTPUT.as_document()]

    # J5, as a client over HTTP applies it: the stream is a valid lifecycle, and the job's end is
    # the one event whose `ends_job` is true — a kind this code does not know.
    typed = [JobEvent.from_document(event, lenient=True) for event in events]
    assert check_lifecycle(Job.from_document(job, lenient=True), typed) == []
    (ender,) = (event for event in typed if event.ends_job)
    assert (ender.kind, ender.known, ender.sequence) == ("ended_v2", False, typed[-1].sequence)
    assert not typed[2].known and typed[3].output is not None and not typed[3].output.known
