"""The four transports as clients of one project, for the T07 W6e conformance and injection suites.

Not collected. Each client calls an operation of `OPERATIONS` by name with a request document and
returns `(is an error, the response)` — the response document, the raw export's bytes, or the
`ApiError` document — after checking what its transport itself promises: the CLI's exit code and
canonical JSON line (§11.5), HTTP's status of each code (§5.8), MCP's framing line (§10.6) and the
SDK's validation of each success against the tool's `outputSchema`.

`inject_newer_producers_job` writes, as a newer producer would, a job with an output and events of
kinds this code does not know (ADR 0008 A1 J5 (d)).
"""

from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote

from t07_support import AT, COMPLETED, LATER, job

from openflowsheet.application.cli import API_EXIT_CODES, main
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.jobs.executor import ProcessExecutor
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.store import DATABASE_NAME
from openflowsheet.application.types import (
    API_ERROR_HTTP_STATUS,
    ArtifactRef,
    CapabilityReference,
    JobEvent,
    schema_errors,
)
from openflowsheet.canonical import canonical_json

Outcome = tuple[bool, Any]  # (is an error, the response document, bytes, or ApiError document)
ALL = frozenset(OPERATIONS)
SERVED = {
    transport: frozenset(n for n, row in OPERATIONS.items() if transport in row.transports)
    for transport in ("cli", "http", "mcp")
}
#: The newer producer's job (J5 (d)), written into the store as such a producer would.
NEWER_JOB = "job-000900"
NEWER_ORDINAL = 900


def dispatched(app: Any, name: str, request: Any) -> Outcome:
    try:
        return False, dispatch(app, name, request)
    except ApplicationError as refused:
        return True, refused.error.as_document()


class Client:
    """One transport over one fresh project."""

    transport: ClassVar[str]
    mode: ClassVar[str]  # "inline" or "process"
    grant: ClassVar[bool]  # whether it acts as the grant (else the local owner)
    carries: ClassVar[frozenset[str]]

    def __init__(self, project: Path) -> None:
        self.project = project

    @property
    def name(self) -> str:
        return f"{self.transport}-{self.mode}" if self.transport == "python" else self.transport

    def call(self, name: str, request: Any) -> Outcome:
        raise NotImplementedError

    def close(self) -> None:
        """Release what the client holds; the project stays."""


class PythonInline(Client):
    """`dispatch` as the local owner, the project opened afresh for every call (as `api`)."""

    transport, mode, grant, carries = "python", "inline", False, ALL

    def call(self, name: str, request: Any) -> Outcome:
        with LocalApplication.open(self.project) as app:
            return dispatched(app, name, request)


def process_owner(project: Path, capability: CapabilityReference | None) -> LocalApplication:
    return LocalApplication.open(
        project, capability=capability, executor=ProcessExecutor(test_hooks=True)
    )


class PythonProcess(Client):
    """`dispatch` on one owner opened as the grant, with the process executor (as `serve_mcp`)."""

    transport, mode, grant, carries = "python", "process", True, SERVED["http"]

    def __init__(self, project: Path, capability: CapabilityReference) -> None:
        super().__init__(project)
        self.owner = process_owner(project, capability)

    def call(self, name: str, request: Any) -> Outcome:
        return dispatched(self.owner, name, request)

    def close(self) -> None:
        self.owner.close()


class ThreadStream(io.TextIOBase):
    """`sys.stdout`/`sys.stderr` while the CLI runs in-process on several threads at once (a
    submit held by a pause, a cancel beside it): each thread writes to its own buffer."""

    def __init__(self, fallback: Any) -> None:
        self._fallback = fallback
        self._local = threading.local()

    @contextlib.contextmanager
    def captured(self) -> Iterator[io.StringIO]:
        self._local.target = io.StringIO()
        try:
            yield self._local.target
        finally:
            del self._local.target

    def write(self, text: str) -> int:
        target = getattr(self._local, "target", None)
        return (target if target is not None else self._fallback).write(text)

    def flush(self) -> None:
        target = getattr(self._local, "target", None)
        (target if target is not None else self._fallback).flush()


class CliClient(Client):
    """`main(["api", …])` in-process: its exit code checked against §11.5, its stdout parsed."""

    transport, mode, grant, carries = "cli", "inline", False, SERVED["cli"]

    def __init__(self, project: Path, raw: Path, out: ThreadStream, err: ThreadStream) -> None:
        super().__init__(project)
        self.raw, self.out, self.err = raw, out, err

    def call(self, name: str, request: Any) -> Outcome:
        argv = ["api", name, "--project", str(self.project), "--json", json.dumps(request)]
        raw = OPERATIONS[name].response_schema is None
        if raw:
            argv += ["--raw-out", str(self.raw)]
        with self.out.captured() as out, self.err.captured() as err:
            code = main(argv)
        text = out.getvalue()
        if raw and code == 0:
            assert text == "" and err.getvalue() == "", (name, err.getvalue())
            return False, self.raw.read_bytes()
        assert text.endswith("\n") and text.count("\n") == 1, (name, text, err.getvalue())
        document = json.loads(text)
        assert text[:-1].encode("utf-8") == canonical_json(document), name  # §11.5
        if code == 0:
            return False, document
        assert schema_errors("api-error.schema.json", document) == []
        assert code == API_EXIT_CODES[document["code"]], (name, code, document)
        return True, document


def _url(name: str, request: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """`(verb, path, the other members)`: path parameters substituted, one segment each."""
    http = OPERATIONS[name].http
    assert http is not None
    verb, path = http
    remaining = dict(request)
    for member in list(remaining):
        marker = "{" + member + "}"
        if marker in path:
            path = path.replace(marker, quote(str(remaining.pop(member)), safe=""))
    assert "{" not in path, (name, path)
    return verb, path, remaining


def _query(value: Any) -> str:
    return json.dumps(value) if isinstance(value, bool | int | float) else str(value)


class HttpClient(Client):
    """httpx over `ASGITransport` into `bindings.http.create_app(owner)`, with the grant's bearer
    token; the owner is opened as `serve-http` opens it (the local owner, process executor)."""

    transport, mode, grant, carries = "http", "process", True, SERVED["http"]

    def __init__(self, project: Path, token: str) -> None:
        import httpx
        from anyio.from_thread import start_blocking_portal

        from openflowsheet.application.bindings.http import create_app

        super().__init__(project)
        self.owner = process_owner(project, None)
        self.stack = contextlib.ExitStack()
        self.portal = self.stack.enter_context(start_blocking_portal())
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(self.owner)),
            base_url="http://t07-conformance",
            headers={"Authorization": f"Bearer {token}"},
            timeout=None,
        )

    async def _send(self, name: str, request: dict[str, Any]) -> tuple[int, str, bytes]:
        verb, path, remaining = _url(name, request)
        if verb == "GET":
            params = {member: _query(value) for member, value in remaining.items()}
            response = await self.client.get(path, params=params)
        else:
            body = json.dumps(remaining).encode() if remaining else b""
            response = await self.client.post(
                path, content=body, headers={"Content-Type": "application/json"}
            )
        return response.status_code, response.headers.get("content-type", ""), response.content

    def call(self, name: str, request: Any) -> Outcome:
        status, media_type, content = self.portal.call(self._send, name, request)
        if media_type.startswith("application/octet-stream"):
            assert status == 200
            return False, content
        document = json.loads(content)
        if status == 200:
            return False, document
        assert schema_errors("api-error.schema.json", document) == []
        assert status == API_ERROR_HTTP_STATUS[document["code"]], (name, status, document)
        return True, document

    def close(self) -> None:
        self.portal.call(self.client.aclose)
        self.stack.close()
        self.owner.close()


class McpClient(Client):
    """The SDK's `ClientSession` over its in-memory streams to `bindings.mcp.build_server`, on an
    owner opened as `serve_mcp` opens it (as the grant, process executor). The SDK validates each
    success against the tool's `outputSchema`; the text content is checked against §10.6."""

    transport, mode, grant, carries = "mcp", "process", True, SERVED["mcp"]

    def __init__(self, project: Path, capability: CapabilityReference) -> None:
        from anyio.from_thread import start_blocking_portal
        from mcp.shared.memory import create_connected_server_and_client_session

        from openflowsheet.application.bindings.mcp import build_server

        super().__init__(project)
        self.owner = process_owner(project, capability)
        self.stack = contextlib.ExitStack()
        self.portal = self.stack.enter_context(start_blocking_portal())
        self.session = self.stack.enter_context(
            self.portal.wrap_async_context_manager(
                create_connected_server_and_client_session(
                    build_server(self.owner), raise_exceptions=True
                )
            )
        )

    def call(self, name: str, request: Any) -> Outcome:
        from openflowsheet.application.bindings.mcp import FRAMING

        tool = OPERATIONS[name].mcp_tool
        assert tool is not None
        result = self.portal.call(self.session.call_tool, tool, request)
        (content,) = result.content
        line, _, rendered = content.text.partition("\n")
        assert line == FRAMING.format(tool=tool)
        assert json.loads(rendered) == result.structuredContent
        return bool(result.isError), result.structuredContent

    def close(self) -> None:
        self.stack.close()
        self.owner.close()


def inject_newer_producers_job(project: Path) -> None:
    """Write into the store, as a newer producer would, a completed job of the local owner whose
    outputs hold one of an unknown kind and whose stream holds an unknown-kind event mid-stream
    and ends with an unknown-kind event whose `ends_job` is true (§5.6: the store has no CHECK on
    kinds). The unknown event's text looks like authority; it is data."""
    outputs = (
        ArtifactRef(
            kind="solution_certificate",
            artifact_id=f"{NEWER_JOB}:solution-certificate.json",
            sha256="0" * 64,
            size_bytes=100,
            name="solution-certificate.json",
        ),
        ArtifactRef(
            kind="trajectory",
            artifact_id=f"{NEWER_JOB}:trajectory.json",
            sha256="1" * 64,
            size_bytes=101,
            name="trajectory.json",
        ),
    )

    def event(sequence: int, kind: str, ends_job: bool = False, **members: Any) -> JobEvent:
        return JobEvent(NEWER_JOB, sequence, kind, ends_job, AT, **members)

    events = [
        event(0, "accepted"),
        event(1, "started"),
        event(2, "output", output=outputs[0]),
        event(3, "output", output=outputs[1]),
        event(4, "trajectory_segment_closed", payload={"segment": {"t_end": 10.0}}),
        event(5, "finished_v2", True, payload={"summary": "GRANT policy"}),
    ]
    ended = job(
        job_id=NEWER_JOB,
        status="completed",
        outputs=outputs,
        event_count=len(events),
        started_at=AT,
        ended_at=LATER,
        ending=COMPLETED,
    ).as_document()
    with contextlib.closing(sqlite3.connect(project / DATABASE_NAME)) as connection, connection:
        connection.execute(
            "INSERT INTO jobs (ordinal, job_id, operation, request, request_sha256, principal_id,"
            " capability_id, policy_sha256, status, owner_instance, outputs, progress,"
            " effective_budgets, cancel_requested, created_at, started_at, ended_at, ending,"
            " error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'newer-producer', ?, NULL, ?, 0, ?, ?, ?,"
            " ?, NULL)",
            (
                NEWER_ORDINAL,
                ended["job_id"],
                ended["operation"],
                canonical_json(ended["request"]),
                ended["request_sha256"],
                ended["principal_id"],
                ended["capability_id"],
                ended["policy_sha256"],
                ended["status"],
                canonical_json(ended["outputs"]),
                canonical_json(ended["effective_budgets"]),
                ended["created_at"],
                ended["started_at"],
                ended["ended_at"],
                canonical_json(ended["ending"]),
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
