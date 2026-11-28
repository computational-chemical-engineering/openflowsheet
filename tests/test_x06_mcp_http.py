"""X06-WO1: MCP over streamable HTTP at `/mcp` of `serve-http` (ADR 0078 D1).

Exit tests E-X06-2 to E-X06-5 (E-X06-1 is the conformance suite's sixth client,
`tests/test_t07_conformance.py`):

- **E-X06-2** `tools/list` over HTTP equals stdio's in canonical bytes, and its digest is the
  registered served digest;
- **E-X06-3** the guard table: each refusal's status, body code and headers, with **no call into
  the session manager** (a spy on `McpGuard.manager.handle_request`); the allowed and the absent
  `Origin` pass;
- **E-X06-4** caller isolation: 50 concurrent `tools/call` requests alternating two tokens with
  different rights on one server;
- **E-X06-5** a token revoked through the CLI while a real `serve-http` runs is refused 401 on its
  next request, and the token appears in no line of the server's log nor of the in-process
  loggers.

Also: Q9's measurements of the SDK's stateless answers (a batch, a wrong Accept or Content-Type,
an unsupported protocol version, a notification, a call without `initialize`), each executing
nothing; the served origins; the composition (`serving.http_application`, the no-TLS warning
naming `/mcp`); a missing caller is `internal_error`; the guard's bearer grammar is the REST
binding's.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import logging
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.authz import grant, new_token, revoke
from openflowsheet.application.cli import main
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.store import POLICY_NAME
from openflowsheet.canonical import canonical_json
from openflowsheet.schema_check import schema_errors

SERVER_EXTRA = all(
    importlib.util.find_spec(name) is not None for name in ("mcp", "starlette", "httpx", "uvicorn")
)
if SERVER_EXTRA:
    import anyio
    import httpx
    from starlette.applications import Starlette

    from openflowsheet.application.bindings import http, mcp_http
    from openflowsheet.application.serving import (
        HTTP_NO_TLS_WARNING,
        http_application,
        serve_http,
    )

pytestmark = [
    pytest.mark.skipif(not SERVER_EXTRA, reason="needs the server extra (mcp, starlette, httpx)"),
    pytest.mark.filterwarnings("ignore:Using `httpx` with `starlette.testclient` is deprecated"),
]

PROJECT_ID = "x06-mcp-http"
HOST, PORT = "127.0.0.1", 8765
BASE = f"http://{HOST}:{PORT}"
JSON_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
PROTOCOL = "2025-06-18"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": PROTOCOL,
        "capabilities": {},
        "clientInfo": {"name": "x06-test", "version": "0"},
    },
}
TOOLS_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
READER, DRAFTER = "agent-reader", "agent-drafter"


def tools_call(tool: str, arguments: dict[str, Any], request_id: int = 3) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }


# ==================================================================================== fixtures


class Project:
    """A project with a reader (`read`), a drafter (`draft` only), an expired grant and a revoked
    one; `tokens` by role, and `unknown`/`malformed` tokens no grant has."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        LocalApplication.create(directory, project_id=PROJECT_ID).close()
        self.reader, reader = grant(
            directory, principal_id=READER, rights=("read",), capability_id="cap-reader"
        )
        self.drafter, drafter = grant(
            directory, principal_id=DRAFTER, rights=("draft",), capability_id="cap-drafter"
        )
        _, expired = grant(
            directory,
            principal_id="agent-expired",
            rights=("read",),
            expires_at="2020-01-01T00:00:00.000000Z",
            capability_id="cap-expired",
        )
        _, revoked = grant(
            directory, principal_id="agent-revoked", rights=("read",), capability_id="cap-revoked"
        )
        revoke(directory, "cap-revoked")
        self.tokens = {
            "reader": reader,
            "drafter": drafter,
            "expired": expired,
            "revoked": revoked,
            "unknown": new_token(),
            "malformed": "prt_short",
        }

    def bearer(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def refusals(self) -> list[dict[str, Any]]:
        """The audit's refusal rows (the operator's grants and revocation are rows too)."""
        with LocalApplication.open(self.directory) as owner:
            return [row for row in owner.store.audit_rows() if row["outcome"] == "refused"]


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path / "project")


class Served:
    """`serving.http_application` over the project's owner, its lifespan running, an httpx
    client into it, and a count of the requests the guard handed to the session manager."""

    def __init__(self, application: Starlette, client: httpx.AsyncClient) -> None:
        self.application = application
        self.client = client
        self.handed = 0

    async def post(self, message: Any, headers: dict[str, str] | None = None) -> httpx.Response:
        return await self.client.post(
            "/mcp", content=json.dumps(message), headers={**JSON_HEADERS, **(headers or {})}
        )


def guard_of(application: Starlette) -> mcp_http.McpGuard:
    (route,) = [r for r in application.router.routes if getattr(r, "path", None) == "/mcp"]
    guard = route.app  # type: ignore[attr-defined]
    assert isinstance(guard, mcp_http.McpGuard)
    return guard


def serve[T](
    project: Project,
    body: Callable[[Served], Awaitable[T]],
    monkeypatch: pytest.MonkeyPatch,
) -> T:
    owner = LocalApplication.open(project.directory)

    async def run() -> T:
        application = http_application(owner, host=HOST, port=PORT)
        manager = guard_of(application).manager
        handle = manager.handle_request

        async def spy(scope: Any, receive: Any, send: Any) -> None:
            served.handed += 1
            await handle(scope, receive, send)

        monkeypatch.setattr(manager, "handle_request", spy)
        async with (
            application.router.lifespan_context(application),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application), base_url=BASE, timeout=60
            ) as client,
        ):
            served = Served(application, client)
            with anyio.fail_after(120):
                return await body(served)

    try:
        return anyio.run(run)
    finally:
        owner.close()


def error_document(response: httpx.Response) -> dict[str, Any]:
    assert response.headers["content-type"] == "application/json"
    document = response.json()
    assert schema_errors("api-error.schema.json", document) == []
    return document  # type: ignore[no-any-return]


# ======================================================================== E-X06-3: the guard

#: (label, method, extra headers by role or literal, expected status, code, detail.code)
REFUSALS: list[tuple[str, str, str | None, dict[str, str], int, str, str | None]] = [
    ("initialize without a token", "POST", None, {}, 401, "unauthenticated", None),
    ("wrong scheme", "POST", None, {"Authorization": "Basic YTpi"}, 401, "unauthenticated", None),
    ("malformed token", "POST", "malformed", {}, 401, "unauthenticated", None),
    ("unknown token", "POST", "unknown", {}, 401, "unauthenticated", None),
    ("expired token", "POST", "expired", {}, 401, "unauthenticated", None),
    ("revoked token", "POST", "revoked", {}, 401, "unauthenticated", None),
    (
        "foreign Origin",
        "POST",
        "reader",
        {"Origin": "http://elsewhere.example"},
        403,
        "forbidden",
        "origin_refused",
    ),
    ("opaque Origin", "POST", "reader", {"Origin": "null"}, 403, "forbidden", "origin_refused"),
    (
        "same host, other port",
        "POST",
        "reader",
        {"Origin": f"http://{HOST}:{PORT + 1}"},
        403,
        "forbidden",
        "origin_refused",
    ),
    ("GET", "GET", "reader", {}, 405, "invalid_request", None),
    ("DELETE", "DELETE", "reader", {}, 405, "invalid_request", None),
    ("PUT", "PUT", "reader", {}, 405, "invalid_request", None),
]


@pytest.mark.parametrize(
    ("label", "method", "role", "headers", "status", "code", "detail_code"),
    REFUSALS,
    ids=[case[0] for case in REFUSALS],
)
def test_e_x06_3_the_guard_refuses_before_the_sdk(
    project: Project,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    method: str,
    role: str | None,
    headers: dict[str, str],
    status: int,
    code: str,
    detail_code: str | None,
) -> None:
    sent = {**JSON_HEADERS, **(project.bearer(role) if role else {}), **headers}

    async def body(served: Served) -> tuple[httpx.Response, int]:
        content = json.dumps(INITIALIZE) if method in ("POST", "PUT") else None
        response = await served.client.request(method, "/mcp", content=content, headers=sent)
        return response, served.handed

    response, handed = serve(project, body, monkeypatch)
    assert (response.status_code, handed) == (status, 0), (label, response.text)
    document = error_document(response)
    assert (document["code"], document["detail"].get("code")) == (code, detail_code)
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    if status == 405:
        assert response.headers["allow"] == "POST"
        assert document["detail"]["allowed"] == "POST"
    if detail_code == "origin_refused":
        assert document["detail"]["origin"] == headers["Origin"]
        assert document["detail"]["explanation"]["chain"] == ["forbidden", "origin_refused"]


@pytest.mark.parametrize("streamed", [False, True], ids=["declared", "streamed"])
def test_e_x06_3_a_body_over_the_limit_is_413_before_the_sdk(
    project: Project, monkeypatch: pytest.MonkeyPatch, streamed: bool
) -> None:
    limit = http.MAX_BODY_BYTES
    oversized = b" " * (limit + 1)

    async def chunks() -> Any:
        for start in range(0, len(oversized), 1 << 16):
            yield oversized[start : start + (1 << 16)]

    async def body(served: Served) -> tuple[httpx.Response, int]:
        content: Any = chunks() if streamed else oversized
        response = await served.client.post(
            "/mcp", content=content, headers={**JSON_HEADERS, **project.bearer("reader")}
        )
        return response, served.handed

    response, handed = serve(project, body, monkeypatch)
    assert (response.status_code, handed) == (413, 0), response.text
    document = error_document(response)
    assert document["code"] == "invalid_request"
    assert document["detail"]["limit_bytes"] == limit


def test_e_x06_3_a_body_at_the_limit_and_the_allowed_origins_pass(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The limit is inclusive; the bound origin, the loopback names on its port and an absent
    `Origin` each reach the session manager once, as the reader."""
    padded = dict(TOOLS_LIST)
    padded["params"] = {"_meta": {"pad": ""}}
    pad = http.MAX_BODY_BYTES - len(json.dumps(padded).encode())
    padded["params"] = {"_meta": {"pad": " " * pad}}
    at_limit = json.dumps(padded).encode()
    assert len(at_limit) == http.MAX_BODY_BYTES
    origins = [None, f"http://{HOST}:{PORT}", f"http://localhost:{PORT}", f"http://[::1]:{PORT}"]

    async def body(served: Served) -> list[tuple[int, int]]:
        seen = []
        for origin in origins:
            headers = {**project.bearer("reader"), **({"Origin": origin} if origin else {})}
            before = served.handed
            response = await served.post(TOOLS_LIST, headers)
            seen.append((response.status_code, served.handed - before))
        before = served.handed
        response = await served.client.post(
            "/mcp", content=at_limit, headers={**JSON_HEADERS, **project.bearer("reader")}
        )
        seen.append((response.status_code, served.handed - before))
        return seen

    assert serve(project, body, monkeypatch) == [(200, 1)] * 5


def test_the_served_origins() -> None:
    assert mcp_http.served_origins("127.0.0.1", 8765, loopback=True) == {
        "http://127.0.0.1:8765",
        "http://localhost:8765",
        "http://[::1]:8765",
    }
    assert mcp_http.served_origins("::1", 9000, loopback=True) == {
        "http://[::1]:9000",
        "http://localhost:9000",
        "http://127.0.0.1:9000",
    }
    assert mcp_http.served_origins("192.0.2.7", 80, loopback=False) == {"http://192.0.2.7:80"}


# ============================================================================== Q9 (measured)


def test_q9_the_sdks_stateless_answers_execute_nothing(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0078 Q9, pinned as `mcp==1.30.0` answers past the guard (each request authenticated,
    as the drafter, whose `get_project` would be refused and audited if it ran): a batch 400, a
    wrong Accept 406, a wrong Content-Type 400, an unsupported `MCP-Protocol-Version` 400, a
    body that is not JSON 400, a notification 202 (empty). None runs a tool: no refusal is
    audited. A `tools/call` without `initialize` runs (stateless: no session requires it)."""
    call = tools_call("get_project", {})
    drafter = project.bearer("drafter")

    async def body(served: Served) -> dict[str, tuple[int, Any]]:
        def outcome(response: httpx.Response) -> tuple[int, Any]:
            try:
                parsed = response.json()
            except ValueError:
                return response.status_code, response.text
            error = parsed.get("error") if isinstance(parsed, dict) else None
            return response.status_code, error["code"] if error else None

        answers = {
            "batch": outcome(await served.post([INITIALIZE, call], drafter)),
            "accept text/plain": outcome(
                await served.post(call, {**drafter, "Accept": "text/plain"})
            ),
            "accept event-stream only": outcome(
                await served.post(call, {**drafter, "Accept": "text/event-stream"})
            ),
            "content-type text/plain": outcome(
                await served.post(call, {**drafter, "Content-Type": "text/plain"})
            ),
            "protocol version 1999-01-01": outcome(
                await served.post(call, {**drafter, "MCP-Protocol-Version": "1999-01-01"})
            ),
            "notification": outcome(
                await served.post(
                    {"jsonrpc": "2.0", "method": "notifications/initialized"}, drafter
                )
            ),
        }
        not_json = await served.client.post(
            "/mcp", content=b"{", headers={**JSON_HEADERS, **drafter}
        )
        answers["not JSON"] = outcome(not_json)
        assert project.refusals() == []
        answers["call without initialize"] = outcome(await served.post(call, drafter))
        return answers

    answers = serve(project, body, monkeypatch)
    assert answers == {
        "batch": (400, -32602),
        "accept text/plain": (406, -32600),
        "accept event-stream only": (406, -32600),
        "content-type text/plain": (400, "Invalid Content-Type header"),
        "protocol version 1999-01-01": (400, -32600),
        "notification": (202, ""),  # an empty body
        "not JSON": (400, -32700),
        "call without initialize": (200, None),
    }
    rows = project.refusals()
    assert [(r["principal_id"], r["operation"], r["code"]) for r in rows] == [
        (DRAFTER, "get_project", "forbidden")
    ]


# ============================================================ E-X06-2: the one served tool list


def test_e_x06_2_tools_list_over_http_is_stdios_and_the_registered_digest(
    project: Project, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import copy

    import test_t08_w2_surface_digest as surface
    from f8_schema_support import without_f8
    from t07_mcp_support import in_session

    from benchmarks.t07.v17 import harness

    async def body(served: Served) -> Any:
        initialized = await served.post(INITIALIZE, project.bearer("reader"))
        assert initialized.status_code == 200, initialized.text
        listed = await served.post(TOOLS_LIST, project.bearer("reader"))
        assert listed.status_code == 200, listed.text
        assert "mcp-session-id" not in listed.headers  # D1.3: stateless, no session
        return listed.json()["result"]["tools"]

    over_http = serve(project, body, monkeypatch)
    token_file = tmp_path / "reader.token"
    token_file.write_text(project.tokens["reader"] + "\n", encoding="utf-8")

    async def listed(session: Any) -> Any:
        return (await session.list_tools()).tools

    over_stdio = in_session(project.directory, token_file, tmp_path / "stdio.log", listed)
    stdio = [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in over_stdio]
    assert canonical_json(over_http) == canonical_json(stdio)
    digest = hashlib.sha256(canonical_json(over_http)).hexdigest()
    # The registered served digest (D6; X06-WO2's `X06_SERVED_SHA256`), with F8's additions taken
    # out first: F8 merges after X06 (R-1076, c_13 onto c_12; F8-FR1).
    assert digest == harness.tool_descriptions_sha256() == surface.F8_SERVED_SHA256
    before_f8 = without_f8(copy.deepcopy(over_http))
    assert hashlib.sha256(canonical_json(before_f8)).hexdigest() == surface.X06_SERVED_SHA256


# ========================================================= E-X06-4: callers isolated per request


def test_e_x06_4_fifty_concurrent_calls_each_act_as_their_own_token(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Alternating the reader (`read`: `get_project` answers, naming the reader's capability) and
    the drafter (no `read`: refused `forbidden` and audited as the drafter)."""
    roles = ["reader" if index % 2 == 0 else "drafter" for index in range(50)]

    async def body(served: Served) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = [{} for _ in roles]

        async def one(index: int, role: str) -> None:
            response = await served.post(
                tools_call("get_project", {}, request_id=index), project.bearer(role)
            )
            assert response.status_code == 200, response.text
            results[index] = response.json()

        async with anyio.create_task_group() as group:
            for index, role in enumerate(roles):
                group.start_soon(one, index, role)
        return results

    results = serve(project, body, monkeypatch)
    for index, (role, answer) in enumerate(zip(roles, results, strict=True)):
        assert answer["id"] == index
        result = answer["result"]
        if role == "reader":
            assert result["isError"] is False, result
            assert result["structuredContent"]["capability_id"] == "cap-reader"
        else:
            assert result["isError"] is True, result
            assert result["structuredContent"]["code"] == "forbidden"
            assert result["structuredContent"]["detail"]["required"] == ["read"]
    rows = project.refusals()
    assert len(rows) == 25
    assert {(r["principal_id"], r["capability_id"], r["operation"], r["code"]) for r in rows} == {
        (DRAFTER, "cap-drafter", "get_project", "forbidden")
    }


# ================================================ E-X06-5: revocation and the token in no log


_LISTENING = r"Uvicorn running on http://127\.0\.0\.1:(\d+)"


def test_e_x06_5_a_token_revoked_through_the_cli_is_refused_on_its_next_request(
    project: Project, tmp_path: Path
) -> None:
    import re

    from t07_mcp_support import environment
    from t07_process_support import wait_until

    log = tmp_path / "server.log"
    with log.open("w") as handle:
        server = subprocess.Popen(
            [sys.executable, "-m", "openflowsheet.application.cli", "serve-http"]
            + ["--project", str(project.directory), "--port", "0"],
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=environment(None),
            cwd=str(REPO_ROOT),
        )
    token = project.tokens["reader"]
    try:
        wait_until(
            lambda: re.search(_LISTENING, log.read_text()) is not None or server.poll() is not None,
            "the server to listen",
        )
        found = re.search(_LISTENING, log.read_text())
        assert found is not None, log.read_text()
        headers = {**JSON_HEADERS, **project.bearer("reader")}
        call = json.dumps(tools_call("get_project", {}))
        with httpx.Client(base_url=f"http://127.0.0.1:{found.group(1)}", timeout=60) as client:
            before = client.post("/mcp", content=call, headers=headers)
            assert before.status_code == 200, before.text
            assert before.json()["result"]["isError"] is False
            policy = (project.directory / POLICY_NAME).read_bytes()
            assert (
                main(
                    ["project", "revoke", "--project", str(project.directory)]
                    + ["--capability", "cap-reader"]
                )
                == 0
            )
            assert (project.directory / POLICY_NAME).read_bytes() != policy
            after = client.post("/mcp", content=call, headers=headers)
        assert after.status_code == 401
        assert after.headers["www-authenticate"] == "Bearer"
        assert error_document(after)["code"] == "unauthenticated"
    finally:
        server.terminate()
        server.wait(timeout=60)
    text = log.read_text()
    assert '"POST /mcp HTTP/1.1" 200' in text and '"POST /mcp HTTP/1.1" 401' in text, text
    assert token not in text
    assert token.removeprefix("prt_") not in text


def test_e_x06_5_the_token_is_in_no_in_process_log_line(
    project: Project, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Every logger at DEBUG, through an `initialize`, a call, a refused call and a refused
    credential: no record carries a token."""
    caplog.set_level(logging.DEBUG)

    async def body(served: Served) -> None:
        for role in ("reader", "drafter", "revoked"):
            await served.post(INITIALIZE, project.bearer(role))
            await served.post(tools_call("get_project", {}), project.bearer(role))

    serve(project, body, monkeypatch)
    assert caplog.records  # the SDK logged at DEBUG
    for token in project.tokens.values():
        assert token not in caplog.text


# ============================================================================ the composition


def test_a_missing_caller_is_internal_error_never_a_fallback(
    project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    """D1.4: the session manager reached without the guard (so no caller in the scope) answers a
    `tools/call` as the fixed `internal_error`; the traceback goes to the log only."""
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.routing import Route

    from openflowsheet.application.bindings.mcp import INTERNAL_ERROR_MESSAGE, build_server

    manager = StreamableHTTPSessionManager(
        app=build_server(mcp_http.scoped_caller), stateless=True, json_response=True
    )

    class Unguarded:
        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            await manager.handle_request(scope, receive, send)

    application = Starlette(routes=[Route("/mcp", Unguarded())])

    async def run() -> dict[str, Any]:
        async with (
            manager.run(),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application), base_url=BASE
            ) as client,
        ):
            response = await client.post(
                "/mcp", content=json.dumps(tools_call("get_project", {})), headers=JSON_HEADERS
            )
            assert response.status_code == 200
            return response.json()["result"]  # type: ignore[no-any-return]

    with caplog.at_level(logging.ERROR, logger="openflowsheet.application.bindings.mcp"):
        result = anyio.run(run)
    assert result["isError"] is True
    assert result["structuredContent"]["code"] == "internal_error"
    assert result["structuredContent"]["message"] == INTERNAL_ERROR_MESSAGE
    assert "openflowsheet.caller" not in json.dumps(result)
    assert "no caller to act as" in caplog.text and "openflowsheet.caller" in caplog.text


def test_serve_http_warns_beyond_loopback_naming_mcp(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import uvicorn

    served: list[Starlette] = []
    monkeypatch.setattr(uvicorn, "run", lambda application, **_: served.append(application))
    with LocalApplication.open(project.directory) as owner:
        with pytest.raises(ValueError, match="allow_remote"):
            serve_http(owner, host="192.0.2.7", port=8765)
        assert served == []
        serve_http(owner, host="192.0.2.7", port=8765, allow_remote=True)
    (application,) = served
    assert guard_of(application).origins == {"http://192.0.2.7:8765"}
    warning = HTTP_NO_TLS_WARNING.format(host="192.0.2.7", port=8765)
    assert "/mcp" in warning
    assert capsys.readouterr().err == warning + "\n"


def test_the_composition_adds_mcp_and_leaves_the_rest_routes_as_they_were(
    project: Project,
) -> None:
    with LocalApplication.open(project.directory) as owner:
        composed = http_application(owner, host=HOST, port=PORT)
        bare = http.create_app(owner)
    paths = [getattr(route, "path", None) for route in composed.router.routes]
    assert paths == [getattr(route, "path", None) for route in bare.router.routes] + ["/mcp"]
    guard = guard_of(composed)
    assert guard.max_body_bytes == http.MAX_BODY_BYTES
    assert guard.origins == mcp_http.served_origins(HOST, PORT, loopback=True)
    assert (guard.manager.stateless, guard.manager.json_response) == (True, True)
    assert guard.manager.security_settings is None


def test_the_guard_reads_the_bearer_as_the_rest_binding_does_and_http_imports_no_mcp() -> None:
    assert mcp_http._BEARER.pattern == http._BEARER.pattern
    source = REPO_ROOT / "src" / "openflowsheet" / "application" / "bindings" / "http.py"
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    assert "openflowsheet.application.operations" in imported
    assert not {name for name in imported if name.split(".")[0] == "mcp" or "mcp" in name}
