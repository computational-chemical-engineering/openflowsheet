"""Starting a transport server on a project (T07 W6b; design note §10.2, §11.3, §11.6).

The bindings under `bindings/` import only the contract (§11.6 (2)). What a server needs besides
— the credential, the project policy it is checked against, and the project opened with the
capability it presents — is composed here, and the CLI's `serve-mcp` calls `serve_mcp`.

**MCP over stdio** (§10.2). The token is read from `--token-file`, or else from the file the
environment variable `OPENFLOWSHEET_TOKEN_FILE` names. It is authenticated once, at start,
against the project policy in force; a missing, unreadable, unknown, malformed, revoked or
expired token refuses the start with a non-zero exit, and nothing is served — there is no
anonymous server. Refusing the start is safer than serving refusals: a client that starts a
server with a bad credential learns so at once, and no tool is ever listed to it. After the start
the application re-authorizes every call against the current policy, so a revocation takes
effect on the next call. The token itself is never printed or logged.

**HTTP** (§11.2, ADR 0078 D1). `serve_http` composes what `serve-http` serves on one host and
port: the REST routes (`bindings.http.create_app`), with `--ui` the diagnostic web shell
(`bindings.web.create_web_app`), and MCP over streamable HTTP at `/mcp` (`bindings.mcp_http`,
behind its guard, with the REST body limit and the origins of the bound host). Every request
presents its bearer token; there is no start-up credential. A server bound beyond loopback marks
its owner `serving_remote`, which refuses the in-band policy writes (ADR 0078 D5.3).

Jobs run under the process executor (§9.1): each in its own freshly spawned worker, whose
stdout and stderr go to its `worker.log`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, TextIO

from openflowsheet.application.authz import authenticate, read_policy
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policy_types import CapabilityReference
from openflowsheet.application.store import POLICY_NAME

if TYPE_CHECKING:
    from starlette.applications import Starlette

    from openflowsheet.application.bindings.http import Owner

#: §10.2: the environment variable naming the token file when no path is given.
TOKEN_FILE_VARIABLE: Final[str] = "OPENFLOWSHEET_TOKEN_FILE"
#: The exit status of a server that refused to start.
SERVE_REFUSED: Final[int] = 1
#: ADR 0078 D1.6: `serve-http`'s no-TLS warning names both of what it serves.
HTTP_NO_TLS_WARNING: Final[str] = (
    "openflowsheet: serving on {host}:{port} without TLS (v0.1 has none); bearer tokens cross the "
    "network in clear text, on the REST routes and on /mcp"
)


class ServeRefusedError(Exception):
    """The server refuses to start; the message is safe to show (it never holds the token)."""


def token_capability(
    project: str | os.PathLike[str], token_file: str | os.PathLike[str]
) -> CapabilityReference:
    """The capability the token in `token_file` presents under `project`'s current policy.

    The file holds the token as `project grant` printed it; surrounding whitespace is ignored.
    """
    try:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise ServeRefusedError(
            f"the token file {os.fspath(token_file)!r} cannot be read ({type(error).__name__})"
        ) from None
    try:
        policy = read_policy(Path(project) / POLICY_NAME)
    except (OSError, ValueError) as error:
        raise ServeRefusedError(
            f"{os.fspath(project)!r} has no valid project policy ({type(error).__name__})"
        ) from None
    capability = authenticate(policy, token)
    if capability is None:
        raise ServeRefusedError(
            "the token matches no current grant of the project policy (unknown, malformed, "
            "revoked or expired)"
        )
    return capability


def serve_mcp(
    project: str | os.PathLike[str],
    token_file: str | os.PathLike[str] | None = None,
    *,
    stderr: TextIO | None = None,
) -> int:
    """`openflowsheet serve-mcp --project DIR [--token-file FILE]`: serve the project's MCP
    tools over stdin and stdout as the token's capability, until the client closes the session.

    Returns the exit status: 0 after the session, `SERVE_REFUSED` when the server refused to
    start (the reason on `stderr`).
    """
    errors = stderr if stderr is not None else sys.stderr
    path = token_file if token_file is not None else os.environ.get(TOKEN_FILE_VARIABLE)
    try:
        if not path:
            raise ServeRefusedError(
                f"no credential: pass --token-file or set {TOKEN_FILE_VARIABLE}; there is no "
                "anonymous server"
            )
        try:
            from openflowsheet.application.bindings import mcp as binding
        except ImportError:
            raise ServeRefusedError(
                "the MCP server needs the `server` extra: pip install 'openflowsheet[server]'"
            ) from None
        capability = token_capability(project, path)
        try:
            application = LocalApplication.open(project, capability=capability, executor="process")
        except (OSError, ValueError, RuntimeError) as error:
            raise ServeRefusedError(f"the project cannot be opened: {error}") from None
    except ServeRefusedError as refused:
        print(f"serve-mcp: refused to start: {refused}", file=errors, flush=True)
        return SERVE_REFUSED
    with application:
        binding.serve_stdio(application)
    return 0


def http_application(owner: Owner, *, host: str, port: int, ui: bool = False) -> Starlette:
    """What `serve-http` serves on `host:port`: the REST routes, the web shell when `ui`, and
    MCP at `/mcp` behind its guard, with the REST body limit and the served origins of `host`
    and `port` (ADR 0078 D1.5). `bindings.web` loads only when `ui`."""
    from openflowsheet.application.bindings import http, mcp_http

    if ui:
        from openflowsheet.application.bindings import web

        application = web.create_web_app(owner)
    else:
        application = http.create_app(owner)
    mcp_http.mount(
        application,
        owner.authenticated,
        origins=mcp_http.served_origins(host, port, loopback=http.is_loopback(host)),
        max_body_bytes=http.MAX_BODY_BYTES,
    )
    return application


def serve_http(
    owner: LocalApplication,
    *,
    host: str,
    port: int,
    allow_remote: bool = False,
    ui: bool = False,
    log_level: str = "info",
) -> None:
    """`serve-http`'s body: `http_application` served under `bindings.http.run`'s rules
    (loopback unless `allow_remote`, the no-TLS warning, here naming `/mcp` too) until
    interrupted.

    The caller opens the owner (`LocalApplication.open(project, executor="process")`) and closes
    it once this returns. Before anything is served the owner is marked `serving_remote` when
    `host` is not loopback, so its in-band policy writes are refused (ADR 0078 D5.3).
    """
    from openflowsheet.application.bindings import http

    owner.serving_remote = not http.is_loopback(host)

    application = http_application(owner, host=host, port=port, ui=ui)
    if ui and (http.is_loopback(host) or allow_remote):
        from openflowsheet.application.bindings.web import MOUNT

        print(f"openflowsheet: web shell at http://{host}:{port}{MOUNT}/", file=sys.stderr)
    http.run(
        application,
        host=host,
        port=port,
        allow_remote=allow_remote,
        log_level=log_level,
        warning=HTTP_NO_TLS_WARNING,
    )
