"""Driving the MCP server over a real stdio session, for the T07 W6b tests.

The server is spawned the way a client starts it — `serving.serve_mcp(project)`, the token from
`OPENFLOWSHEET_TOKEN_FILE` — and driven by the SDK's own `ClientSession` over `stdio_client`.
The SDK is imported inside the functions, so a module importing this one collects without the
`server` extra; its tests `pytest.importorskip("mcp")` before calling in.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from conftest import REPO_ROOT

from openflowsheet.application.authz import grant
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.types import CapabilityReference

PROJECT_ID = "w6b-mcp"
PRINCIPAL = "agent-w6b"
CAPABILITY = "cap-agent-w6b"
#: A generous bound on one whole stdio session, solve included: CI's 2-core aarch64 runner spawns
#: the server and a solve worker, each importing numpy and scipy. A normal session takes seconds.
SESSION_TIMEOUT_S = 600.0
#: How a client starts the server: `serve-mcp --project DIR`, the token from the environment.
SERVER = (
    "import sys\n"
    "from openflowsheet.application.serving import serve_mcp\n"
    "sys.exit(serve_mcp(sys.argv[1]))\n"
)

Session = Any  # mcp.ClientSession; the SDK is imported only once the extra is known present
Outcome = tuple[bool, Any]  # (is an error, the response or the ApiError document)


def environment(token_file: Path | None) -> dict[str, str]:
    """The test's environment, this checkout's `src` first on the path, and the token file."""
    variables = {k: v for k, v in os.environ.items() if k != "OPENFLOWSHEET_TOKEN_FILE"}
    paths = [str(REPO_ROOT / "src"), str(REPO_ROOT), os.environ.get("PYTHONPATH", "")]
    variables["PYTHONPATH"] = os.pathsep.join(path for path in paths if path)
    if token_file is not None:
        variables["OPENFLOWSHEET_TOKEN_FILE"] = str(token_file)
    return variables


def project_with_grant(
    directory: Path, rights: tuple[str, ...]
) -> tuple[CapabilityReference, Path]:
    """A fresh project with one grant to `PRINCIPAL`; the grant and its token file."""
    LocalApplication.create(directory, project_id=PROJECT_ID).close()
    capability, token = grant(
        directory, principal_id=PRINCIPAL, rights=rights, capability_id=CAPABILITY
    )
    token_file = directory.parent / f"{directory.name}.token"
    token_file.write_text(token + "\n", encoding="utf-8")
    return capability, token_file


def in_session[T](
    project: Path, token_file: Path, errlog: Path, body: Callable[[Session], Awaitable[T]]
) -> T:
    """Spawn the server over `project` as a client would, open a session, run `body`; the
    server's stderr goes to `errlog`."""
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-c", SERVER, str(project)],
        env=environment(token_file),
        cwd=str(REPO_ROOT),
    )

    async def main() -> T:
        with anyio.fail_after(SESSION_TIMEOUT_S), errlog.open("w") as log:
            async with (
                stdio_client(parameters, errlog=log) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                return await body(session)

    return anyio.run(main)


def in_memory[T](app: Any, body: Callable[[Session], Awaitable[T]]) -> T:
    """Serve `app` (an owner, or a view acting as a grant) with `bindings.mcp.build_server` over
    the SDK's in-memory streams, open a client session, run `body` — the server in this process,
    so its executor's test hooks and the store are the test's to reach."""
    import anyio
    from mcp.shared.memory import create_connected_server_and_client_session

    from openflowsheet.application.bindings.mcp import build_server

    async def main() -> T:
        with anyio.fail_after(SESSION_TIMEOUT_S):
            async with create_connected_server_and_client_session(
                build_server(app), raise_exceptions=True
            ) as session:
                return await body(session)

    return anyio.run(main)


async def call(session: Session, tool: str, arguments: dict[str, Any]) -> Outcome:
    """One tool call; checks §10.6's framing of the text content against `structuredContent`.
    (The SDK client has already validated a success against the tool's `outputSchema`.)"""
    from openflowsheet.application.bindings.mcp import FRAMING

    result = await session.call_tool(tool, arguments)
    (content,) = result.content
    line, _, rendered = content.text.partition("\n")
    assert line == FRAMING.format(tool=tool)
    assert json.loads(rendered) == result.structuredContent
    return bool(result.isError), result.structuredContent


def direct_call(app: LocalApplication, name: str, request: dict[str, Any]) -> Outcome:
    """`dispatch` in-process, with a refusal as its error document."""
    try:
        return False, dispatch(app, name, request)
    except ApplicationError as refused:
        return True, refused.error.as_document()
