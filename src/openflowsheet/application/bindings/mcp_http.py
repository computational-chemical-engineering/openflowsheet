"""MCP over streamable HTTP: `/mcp` of `serve-http`, behind a guard (ADR 0078 D1).

The server is `bindings.mcp.build_server`, the tool list `bindings.mcp.tools()`: one object on
both carriers (D1.2). The SDK's `StreamableHTTPSessionManager` runs it in its stateless JSON mode
(D1.3): each `POST /mcp` carries one JSON-RPC message and gets one `application/json` response,
or 202 for a notification; there is no `Mcp-Session-Id`, no SSE stream and no event store. The
SDK's own checks of the request headers (Accept, Content-Type, `MCP-Protocol-Version`) stand.

**The guard** (`McpGuard`, D1.5) answers every request before the SDK sees it, in this order:

1. a method other than `POST`: 405, `Allow: POST`;
2. an `Origin` header that is not one of the served origins (`served_origins`): 403
   `forbidden`, `detail.code = origin_refused`. A request without `Origin` (a non-browser
   client) passes;
3. a body above the limit, declared (`Content-Length`) or streamed: 413 `invalid_request`,
   `detail.limit_bytes`. The body is read whole, up to the limit, before anything else sees it;
4. no bearer credential, or a token the owner does not resolve (unknown, malformed, expired,
   revoked): 401 `unauthenticated`, `WWW-Authenticate: Bearer`, exactly as the REST routes
   answer it (and, as there, not audited: no principal is known);
5. otherwise the resolved caller goes into the request's scope state (`CALLER_KEY`) and the
   request, its body replayed, to the session manager.

No request reaches the SDK unauthenticated, `initialize` and `tools/list` included. The token is
read from the `Authorization` header only, re-resolved on every request (a revocation takes
effect on the next one), and never logged. Each tool call acts as the caller its own request
resolved to (`scoped_caller`, read through the SDK's `request_context.request.state`).

**Imports** (D1.7): `bindings.mcp`, `mcp`, `starlette`, `anyio`, the contract modules and the
standard library. The owner, the body limit and the served origins are passed in by the
composition (`serving.serve_http`), so this module never imports `bindings.http`, `local` or
`authz`: a test holds the import graph to that list.
"""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from typing import Any, Final

import anyio.to_thread
from mcp.server.lowlevel.server import request_ctx
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.types import Message, Receive, Scope, Send

from openflowsheet.application.bindings.mcp import build_server
from openflowsheet.application.errors import ApiError
from openflowsheet.application.operations import Dispatchable, project_error

__all__ = [
    "CALLER_KEY",
    "MCP_PATH",
    "McpGuard",
    "mount",
    "scoped_caller",
    "served_origins",
]

#: D1.1: where MCP is served, exactly (no trailing slash).
MCP_PATH: Final[str] = "/mcp"
#: D1.4: the scope-state member the guard stores the request's caller under.
CALLER_KEY: Final[str] = "openflowsheet.caller"
#: The `detail.code` of a refused `Origin` (catalogue `refusals.yaml`).
ORIGIN_REFUSED: Final[str] = "origin_refused"
_ALLOWED_METHOD: Final[str] = "POST"
_JSON_MEDIA_TYPE: Final[str] = "application/json"
#: The bearer grammar of `bindings.http` (a test holds the two equal).
_BEARER: Final[re.Pattern[str]] = re.compile(r"^[Bb][Ee][Aa][Rr][Ee][Rr] +(\S+) *$")
#: D1.5 (b): the loopback names a browser may use for a server bound to the loopback interface.
_LOOPBACK_HOSTS: Final[tuple[str, ...]] = ("localhost", "127.0.0.1", "[::1]")

Authenticate = Callable[[str], Dispatchable | None]


class _TooLargeError(Exception):
    """The body exceeds the limit."""


class _DisconnectedError(Exception):
    """The client went away before its body was complete; there is no one to answer."""


# ================================================================================= origins


def _authority(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def served_origins(host: str, port: int, *, loopback: bool) -> frozenset[str]:
    """D1.5 (b): the origins a browser page served by this server has — `http://<host>:<port>`
    for the bound host and, on a loopback binding, the loopback names on the same port."""
    hosts: Iterable[str] = (_authority(host), *_LOOPBACK_HOSTS) if loopback else (_authority(host),)
    return frozenset(f"http://{name}:{port}" for name in hosts)


# =============================================================================== responses


def _refusal(status: int, error: ApiError, headers: Mapping[str, str] | None = None) -> Response:
    """A refusal of the guard: the projected `ApiError` document (§10.4) at `status`."""
    document = project_error(error).as_document()
    body = json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")
    return Response(
        body, status_code=status, media_type=_JSON_MEDIA_TYPE, headers=dict(headers or {})
    )


def _wrong_method(method: str) -> Response:
    return _refusal(
        405,
        ApiError(
            code="invalid_request",
            message=f"{MCP_PATH} is served for POST only, not for {method}",
            retryable=False,
            detail={"method": method, "allowed": _ALLOWED_METHOD},
        ),
        {"Allow": _ALLOWED_METHOD},
    )


def _foreign_origin(origin: str) -> Response:
    return _refusal(
        403,
        ApiError(
            code="forbidden",
            # The code leads the message: the explanation reads its chain from there (MSG §4.4).
            message=f"{ORIGIN_REFUSED}: the request's Origin is not an origin this server "
            "serves; a page of another origin cannot call it",
            retryable=False,
            detail={"code": ORIGIN_REFUSED, "origin": origin},
        ),
    )


def _too_large(limit: int) -> Response:
    return _refusal(
        413,
        ApiError(
            code="invalid_request",
            message=f"the request body exceeds {limit} bytes",
            retryable=False,
            detail={"pointer": "", "limit_bytes": limit},
        ),
    )


def _unauthenticated(message: str) -> Response:
    return _refusal(
        401,
        ApiError(code="unauthenticated", message=message, retryable=False, detail={}),
        {"WWW-Authenticate": "Bearer"},
    )


# =================================================================================== guard


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", ()):
        if key.lower() == name:
            return bytes(value).decode("latin-1")
    return None


async def _read_body(receive: Receive, limit: int) -> bytes:
    """The whole request body, refused once it exceeds `limit`."""
    received = bytearray()
    while True:
        message = await receive()
        if message["type"] != "http.request":
            raise _DisconnectedError
        received += message.get("body", b"")
        if len(received) > limit:
            raise _TooLargeError
        if not message.get("more_body", False):
            return bytes(received)


def _replay(body: bytes, receive: Receive) -> Receive:
    """A `receive` that yields `body` once, whole, then defers to `receive` (a disconnect)."""
    sent = False

    async def replayed() -> Message:
        nonlocal sent
        if sent:
            return await receive()
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return replayed


class McpGuard:
    """The ASGI application at `MCP_PATH`: the guard of the module docstring in front of
    `manager`. `authenticate` resolves a bearer token to the view acting as its grant (the
    owner's `authenticated`), or `None`."""

    def __init__(
        self,
        manager: StreamableHTTPSessionManager,
        authenticate: Authenticate,
        *,
        origins: frozenset[str],
        max_body_bytes: int,
    ) -> None:
        self.manager = manager
        self.authenticate = authenticate
        self.origins = origins
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"
        method = scope["method"]
        if method != _ALLOWED_METHOD:
            await _wrong_method(method)(scope, receive, send)
            return
        origin = _header(scope, b"origin")
        if origin is not None and origin not in self.origins:
            await _foreign_origin(origin)(scope, receive, send)
            return
        declared = _header(scope, b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_body_bytes:
            await _too_large(self.max_body_bytes)(scope, receive, send)
            return
        try:
            body = await _read_body(receive, self.max_body_bytes)
        except _TooLargeError:
            await _too_large(self.max_body_bytes)(scope, receive, send)
            return
        except _DisconnectedError:
            return
        header = _header(scope, b"authorization")
        found = _BEARER.fullmatch(header) if header is not None else None
        if found is None:
            refused = _unauthenticated(
                "a bearer credential is required: Authorization: Bearer prt_…"
            )
            await refused(scope, receive, send)
            return
        caller = await anyio.to_thread.run_sync(self.authenticate, found.group(1))
        if caller is None:
            refused = _unauthenticated(
                "the credential is not in the project policy (unknown, malformed, expired or "
                "revoked)"
            )
            await refused(scope, receive, send)
            return
        state = {**scope.get("state", {}), CALLER_KEY: caller}
        await self.manager.handle_request({**scope, "state": state}, _replay(body, receive), send)


def scoped_caller() -> Dispatchable:
    """D1.4: the caller the guard stored for the request being served; a missing one is a
    defect (`build_server` answers it `internal_error`), never a fallback."""
    caller: Any = getattr(request_ctx.get().request.state, CALLER_KEY, None)  # type: ignore[union-attr]
    if caller is None:
        raise RuntimeError(f"no {CALLER_KEY} in the request's scope state")
    return caller  # type: ignore[no-any-return]


# ================================================================================ mounting


def mount(
    application: Starlette,
    authenticate: Authenticate,
    *,
    origins: frozenset[str],
    max_body_bytes: int,
) -> McpGuard:
    """Serve MCP at `MCP_PATH` of `application`: the guard as a route there, and the session
    manager run in `application`'s lifespan, around whatever lifespan it had."""
    manager = StreamableHTTPSessionManager(
        app=build_server(scoped_caller),
        stateless=True,
        json_response=True,
        security_settings=None,
    )
    guard = McpGuard(manager, authenticate, origins=origins, max_body_bytes=max_body_bytes)
    application.router.routes.append(Route(MCP_PATH, guard))
    previous = application.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[Any]:
        async with manager.run(), previous(app) as state:
            yield state

    application.router.lifespan_context = lifespan
    return guard
