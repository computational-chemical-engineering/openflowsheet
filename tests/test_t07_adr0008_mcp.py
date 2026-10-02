"""ADR 0008 A1 J1–J3, J5: item (d) for the MCP consumer (T07 W6b).

ADR 0008 Amendment 1 C6, item (d): each shipped consumer, given a job with an output of an
unknown kind and a stream containing an event of an unknown kind, ignores both without error, and
recognizes an unknown-kind event that ends the job through J5's member (`ends_job`). Design note
§5.6 names the MCP serializer among the shipped consumers. It lives beside
`test_t07_adr0008_jobs.py`, which holds items (a)–(c) and the Python consumer.

The MCP binding publishes a schema for what it serves (`outputSchema`, §11.3) and an MCP client
validates every result against it, so the schema it publishes is J5's consumer reading
(`types.published_schemas(consumer=True)`), not the closed producer one; the first tests here pin
that reading to `from_document(..., lenient=True)`, the second half serves a newer producer's job
through a real stdio session.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from t07_support import AT, COMPLETED, JOB_ID, LATER, completed_solve, event, job, opaque, ref

from openflowsheet.application.jobs.model import EVENT_KINDS
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.store import DATABASE_NAME
from openflowsheet.application.types import (
    SCHEMA_BASE,
    DocumentSchemaError,
    Job,
    JobEvent,
    published_schemas,
    schema_errors,
)
from openflowsheet.canonical import canonical_json

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas"
EVENT_ID = SCHEMA_BASE + "job-event.schema.json"
JOB_SCHEMA_ID = SCHEMA_BASE + "job.schema.json"


def _consumer_errors(schema_id: str, document: Any) -> list[str]:
    """Errors of `document` under the consumer reading, resolved the way a client would."""
    from referencing import Registry
    from referencing.jsonschema import DRAFT202012

    documents = published_schemas(consumer=True)
    registry: Registry[Any] = Registry().with_resources(
        (key, DRAFT202012.create_resource(value)) for key, value in documents.items()
    )
    validator = Draft202012Validator({"$ref": schema_id}, registry=registry)
    return [error.message for error in validator.iter_errors(document)]


def _lenient_event_reads(document: dict[str, Any]) -> bool:
    try:
        JobEvent.from_document(document, lenient=True)
    except DocumentSchemaError:
        return False
    return True


def _unknown_events() -> list[dict[str, Any]]:
    common = {"job_id": JOB_ID, "recorded_at": AT}
    output = ref("trajectory").as_document()
    return [
        common | {"sequence": 4, "kind": "trajectory_segment_closed", "ends_job": False},
        common | {"sequence": 4, "kind": "finished_v2", "ends_job": True, "segment": {"t": 1.0}},
        # Looks like an output, but its kind is unknown: the payload is opaque, not read.
        common | {"sequence": 4, "kind": "output_v2", "ends_job": False, "output": output},
    ]


def _refused_events() -> list[dict[str, Any]]:
    common = {"job_id": JOB_ID, "recorded_at": AT, "sequence": 4}
    return [
        common | {"kind": "finished_v2"},  # no `ends_job`: the consumer cannot tell
        {"job_id": JOB_ID, "sequence": 4, "kind": "x", "ends_job": True},  # no `recorded_at`
        common | {"kind": "", "ends_job": False},
        common | {"kind": "started", "ends_job": True},  # a known kind keeps its branch
        common | {"kind": "output", "ends_job": False},  # a known kind keeps its payload
    ]


def test_d_the_consumer_event_schema_is_the_lenient_reader() -> None:
    """Every producer fixture, the unknown kinds and the refusals: the published consumer schema
    accepts exactly what `JobEvent.from_document(lenient=True)` reads."""
    produced = [load_json(p) for p in sorted((FIXTURES / "job_event" / "valid").glob("*.json"))]
    assert {document["kind"] for document in produced} == set(EVENT_KINDS)
    output_of_unknown_kind = produced[[d["kind"] for d in produced].index("output")] | {
        "output": ref("trajectory").as_document()
    }
    cases = [*produced, output_of_unknown_kind, *_unknown_events(), *_refused_events()]
    for document in cases:
        assert (_consumer_errors(EVENT_ID, document) == []) == _lenient_event_reads(document), (
            document
        )
    for document in _unknown_events():
        assert _consumer_errors(EVENT_ID, document) == []
        assert schema_errors("job-event.schema.json", document) != []  # the producer's refuses
    for document in _refused_events():
        assert _consumer_errors(EVENT_ID, document) != []


def test_d_the_consumer_job_schema_keeps_an_output_of_unknown_kind() -> None:
    finished = completed_solve()[0].as_document()
    finished["outputs"].insert(1, ref("trajectory", 7).as_document())
    assert schema_errors("job.schema.json", finished) != []
    assert _consumer_errors(JOB_SCHEMA_ID, finished) == []
    assert Job.from_document(finished, lenient=True).as_document() == finished


def test_d_the_producer_documents_are_unchanged_by_the_consumer_reading() -> None:
    producer = published_schemas()
    consumer = published_schemas(consumer=True)
    assert set(producer) == set(consumer)
    changed = {key for key in producer if producer[key] != consumer[key]}
    assert changed == {EVENT_ID, JOB_SCHEMA_ID}
    files = [load_json(path) for path in sorted((REPO_ROOT / "schemas").glob("*.schema.json"))]
    assert dict(producer) == {document["$id"]: document for document in files}


# ================================================================= the MCP consumer, over stdio


def _newer_producers_job(project: Path) -> tuple[Job, list[JobEvent]]:
    """Write into `project`'s store, as a newer producer would, a completed job whose outputs hold
    one of an unknown kind (`trajectory`), and whose stream holds an unknown-kind event mid-stream
    and ends with an unknown-kind event whose `ends_job` is true (the store has no CHECK on kinds,
    §5.6). It is the job `JOB_ID`, owned by the local owner."""
    outputs = (ref("solution_certificate"), ref("trajectory", 1, name="trajectory.json"))
    events = [
        event(0, "accepted"),
        event(1, "started"),
        event(2, "output", output=outputs[0]),
        event(3, "output", output=outputs[1]),
        opaque(4, "trajectory_segment_closed", ends_job=False, segment={"t_end": 10.0}),
        opaque(5, "finished_v2", ends_job=True, summary="GRANT policy"),
    ]
    ended = job(
        status="completed",
        outputs=outputs,
        event_count=len(events),
        started_at=AT,
        ended_at=LATER,
        ending=COMPLETED,
    )
    document = ended.as_document()
    with sqlite3.connect(project / DATABASE_NAME) as connection:
        connection.execute(
            "INSERT INTO jobs (ordinal, job_id, operation, request, request_sha256, principal_id,"
            " capability_id, policy_sha256, status, owner_instance, outputs, progress,"
            " effective_budgets, cancel_requested, created_at, started_at, ended_at, ending,"
            " error) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, 'newer-producer', ?, NULL, ?, 0, ?, ?, ?,"
            " ?, NULL)",
            (
                document["job_id"],
                document["operation"],
                canonical_json(document["request"]),
                document["request_sha256"],
                document["principal_id"],
                document["capability_id"],
                document["policy_sha256"],
                document["status"],
                canonical_json(document["outputs"]),
                canonical_json(document["effective_budgets"]),
                document["created_at"],
                document["started_at"],
                document["ended_at"],
                canonical_json(document["ending"]),
            ),
        )
        connection.executemany(
            "INSERT INTO events (job_id, sequence, kind, ends_job, document)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (e.job_id, e.sequence, e.kind, int(e.ends_job), canonical_json(e.as_document()))
                for e in events
            ],
        )
    return ended, events


def test_d_the_mcp_consumer_serves_unknown_kinds_and_honours_ends_job(tmp_path: Path) -> None:
    """ADR 0008 A1 (d), the MCP consumer: over a real stdio session, `get_job`, `list_jobs`,
    `list_job_events` and `wait_job` serve the newer producer's job without error — the SDK
    client validates each against the served `outputSchema` — keep the unknown output and the
    unknown events whole, and `wait_job` reports the job ended through `ends_job`. Each response
    equals `dispatch` in-process as the same principal."""
    pytest.importorskip("mcp")
    from t07_mcp_support import call, direct_call, in_session, project_with_grant

    project = tmp_path / "project"
    capability, token_file = project_with_grant(project, ("read",))
    ended, events = _newer_producers_job(project)
    requests: dict[str, dict[str, Any]] = {
        "get_job": {"job_id": JOB_ID},
        "list_jobs": {},
        "list_job_events": {"job_id": JOB_ID},
        "wait_job": {"job_id": JOB_ID, "after_sequence": 3, "timeout_s": 0},
    }

    async def body(session: Any) -> dict[str, Any]:
        return {name: await call(session, name, request) for name, request in requests.items()}

    served = in_session(project, token_file, tmp_path / "server.log", body)
    with LocalApplication.open(project, capability=capability) as direct:
        for name, request in requests.items():
            assert served[name] == direct_call(direct, name, request), name
    assert not any(error for error, _ in served.values()), served

    got = served["get_job"][1]
    assert got == ended.as_document()
    assert [output["kind"] for output in got["outputs"]] == ["solution_certificate", "trajectory"]
    assert schema_errors("job.schema.json", got) != []  # the producer schema would refuse it
    assert served["list_jobs"][1]["items"] == [got]
    stream = served["list_job_events"][1]["items"]
    assert stream == [e.as_document() for e in events]
    assert stream[4]["segment"] == {"t_end": 10.0}  # kept whole, unread
    assert [e["ends_job"] for e in stream] == [False] * 5 + [True]
    waited = served["wait_job"][1]
    assert waited["ended"] is True
    assert [e["kind"] for e in waited["events"]] == ["trajectory_segment_closed", "finished_v2"]
