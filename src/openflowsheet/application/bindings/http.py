"""The HTTP binding: Starlette over `operations.dispatch`, and nothing else (§4.3, §10.2, §11.2).

**What it adds is transport, never meaning.** Each row of `OPERATIONS` whose transports include
`http` is one route, at the row's verb and path, and every route's handler does the same four
things:

1. **The credential** (§10.2). `Authorization: Bearer prt_…` is resolved by the owner to a view
   acting as the grant it presents (`LocalApplication.authenticated`); no header, or a token the
   current policy does not know (unknown, malformed, expired, revoked), is 401 `unauthenticated`.
   Nothing in the request other than the token is ever read for authority, and the rights
   themselves are checked by the method, not here (§10.1).
2. **The request document.** The route's path parameters (matched on the raw path, one segment
   each, then percent-decoded: an artifact id's `/` travels as `%2F`), the query parameters (a
   value is a JSON number where the operation's request schema says `integer` or `number` and
   the text is a JSON number, and a string otherwise), and — for `POST` — the JSON body, at most
   1 MiB, parsed with `canonical.load_document`'s refusal of duplicate keys. A member given twice
   (in two of these places, or as a repeated query parameter) is refused rather than resolved.
   A refusal here is audited like `dispatch`'s own (§10.7) and never reaches the method.
3. **`dispatch`**, in a worker thread: the canonical form (a non-canonical body is 422
   `document_not_canonical` before any method runs, §12.5), the schema, the reserved `auto:`
   key, the method, the bounding (§10.4).
4. **The response.** A domain result is 200 with its document as JSON, whatever its status. A
   raised `ApiError` is its §5.8 status (`types.API_ERROR_HTTP_STATUS`) with the error document.
   The raw export (`GET /v1/artifacts/{artifact_id}/raw`) streams the bytes with
   `X-Content-SHA256`. Anything else raised is a defect: 500 `internal_error` with a fixed
   message; the traceback goes to the log only (§10.4).

Every error this module answers — an unknown route, a method a route does not carry, a refusal
of the request's shape — is an `ApiError` bounded by `operations.project_error`, with the status
its code has in §5.8; there is no second error shape.

**Safe defaults** (decisions the note leaves open, logged in `docs/T07_DECISIONS.md`): no CORS
(a browser's preflight is refused like any other unknown method), no TLS, and `serve` binds the
loopback interface unless `allow_remote` is given, when it says on stderr that there is no TLS.

**Imports** (§11.6 (2)): `contract`, `types`, `operations` and `projection` of the application,
the standard library, `starlette` and `uvicorn`. The owner is passed in, so this module never
imports `local` or `authz`: a test holds the import graph to that list.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any, Final, Protocol
from urllib.parse import unquote

import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Match, Route
from starlette.types import Scope

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.operations import (
    OPERATIONS,
    Dispatchable,
    Operation,
    dispatch,
    project_error,
)
from openflowsheet.application.types import ApiError, ApiErrorCode

_LOG = logging.getLogger(__name__)

#: §11.2: the serving defaults — the loopback interface only.
DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8765
#: §11.2: the largest request body accepted.
MAX_BODY_BYTES: Final[int] = 1 << 20
#: §4.3: the raw export's digest header — the SHA-256 of exactly the bytes sent.
CONTENT_SHA256_HEADER: Final[str] = "X-Content-SHA256"
#: The raw export is sent in pieces of this size.
STREAM_CHUNK_BYTES: Final[int] = 1 << 16
#: §4.3: the operations HTTP carries, in the table's order.
HTTP_OPERATIONS: Final[tuple[Operation, ...]] = tuple(
    operation for operation in OPERATIONS.values() if "http" in operation.transports
)

_JSON_MEDIA_TYPE: Final[str] = "application/json"
_BEARER: Final[re.Pattern[str]] = re.compile(r"^[Bb][Ee][Aa][Rr][Ee][Rr] +(\S+) *$")
#: RFC 8259 §6: the JSON number grammar. A query value of this form under a numeric member is
#: that number; anything else stays a string, for the schema to judge.
_JSON_NUMBER: Final[re.Pattern[str]] = re.compile(
    r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$"
)
_NUMERIC_TYPES: Final[frozenset[str]] = frozenset({"integer", "number"})


class Owner(Protocol):
    """What the binding serves: the project's one owner (`LocalApplication`, opened with the
    process executor), which resolves a bearer token to a view acting as its grant."""

    def authenticated(self, token: str) -> Dispatchable | None: ...


class _RefusedError(Exception):
    """A refusal made by this module, before `dispatch`; audited once the caller is known."""

    def __init__(self, code: ApiErrorCode, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.error = ApiError(code=code, message=message, retryable=False, detail=detail)


# ================================================================================= responses


def _json_bytes(document: Any) -> bytes:
    """A response body. ASCII-escaped, so that no string — an error echoing request text
    included — can fail to encode; a client parses it to the same document."""
    return json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _error_response(error: ApiError, headers: Mapping[str, str] | None = None) -> Response:
    """§5.8: a raised `ApiError` at its code's status, bounded (§10.4)."""
    bounded = project_error(error)
    return Response(
        _json_bytes(bounded.as_document()),
        status_code=bounded.http_status,
        media_type=_JSON_MEDIA_TYPE,
        headers=dict(headers or {}),
    )


def _internal_error(operation: str) -> Response:
    _LOG.exception("HTTP %s: an untyped exception reached the transport", operation)
    return _error_response(
        ApiError(
            code="internal_error",
            message="the server failed to complete this request; the defect is logged",
            retryable=False,
            detail={"operation": operation},
        )
    )


def _raw_response(data: bytes, digest: str) -> Response:
    """§4.3, §11.2: the raw export, streamed, with `digest`, the SHA-256 of exactly these bytes."""

    async def pieces() -> AsyncIterator[bytes]:
        view = memoryview(data)
        for start in range(0, len(data), STREAM_CHUNK_BYTES):
            yield bytes(view[start : start + STREAM_CHUNK_BYTES])

    return StreamingResponse(
        pieces(),
        media_type="application/octet-stream",
        headers={
            CONTENT_SHA256_HEADER: digest,
            "Content-Length": str(len(data)),
        },
    )


# ============================================================================ the credential


def _token(request: Request) -> str:
    header = request.headers.get("authorization")
    found = _BEARER.fullmatch(header) if header is not None else None
    if found is None:
        raise _RefusedError(
            "unauthenticated", "a bearer credential is required: Authorization: Bearer prt_…"
        )
    return found.group(1)


async def _caller(owner: Owner, request: Request) -> Dispatchable:
    """§10.2: the view acting as the grant the request's token presents; 401 otherwise."""
    caller = await run_in_threadpool(owner.authenticated, _token(request))
    if caller is None:
        raise _RefusedError(
            "unauthenticated",
            "the credential is not in the project policy (unknown, malformed, expired or revoked)",
        )
    return caller


# ====================================================================== the request document


class _Duplicated(dict[str, Any]):
    """An object whose text repeated a key; `repeated` is the first such key."""

    repeated: str


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            marked = _Duplicated(pairs)
            marked.repeated = key
            return marked
        document[key] = value
    return document


def _escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _first_duplicate(document: Any, pointer: str = "") -> str | None:
    """The RFC 6901 pointer of the first repeated member, in document order, or `None`."""
    if isinstance(document, _Duplicated):
        return f"{pointer}/{_escape(document.repeated)}"
    if isinstance(document, dict):
        for key, value in document.items():
            found = _first_duplicate(value, f"{pointer}/{_escape(key)}")
            if found is not None:
                return found
    elif isinstance(document, list):
        for index, item in enumerate(document):
            found = _first_duplicate(item, f"{pointer}/{index}")
            if found is not None:
                return found
    return None


async def _body(request: Request) -> dict[str, Any]:
    """A `POST`'s JSON object: at most `MAX_BODY_BYTES`, UTF-8, no repeated key (ADR 0002 D3.6,
    as `canonical.load_document`). An empty body is the empty object."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise _RefusedError(
            "invalid_request",
            f"the request body exceeds {MAX_BODY_BYTES} bytes",
            pointer="",
            limit_bytes=MAX_BODY_BYTES,
        )
    received = bytearray()
    async for piece in request.stream():
        received += piece
        if len(received) > MAX_BODY_BYTES:
            raise _RefusedError(
                "invalid_request",
                f"the request body exceeds {MAX_BODY_BYTES} bytes",
                pointer="",
                limit_bytes=MAX_BODY_BYTES,
            )
    if not received:
        return {}
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != _JSON_MEDIA_TYPE:
        raise _RefusedError(
            "invalid_request",
            f"a request body must be {_JSON_MEDIA_TYPE}",
            pointer="",
            content_type=media_type,
        )
    try:
        document = json.loads(received.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except UnicodeDecodeError:
        raise _RefusedError(
            "invalid_request", "the request body is not UTF-8", pointer=""
        ) from None
    except json.JSONDecodeError as error:
        raise _RefusedError(
            "invalid_request",
            f"the request body is not JSON: {error.msg}",
            pointer="",
            position=error.pos,
        ) from None
    except ValueError:
        # Not a `JSONDecodeError`: CPython's parser refuses an integer text of more than 4300
        # digits with a plain `ValueError` (ADR 0002 Amendment 1, A1.1). Refused typed, never
        # `internal_error`.
        raise _RefusedError(
            "invalid_request", "the request body is not JSON this server parses", pointer=""
        ) from None
    repeated = _first_duplicate(document)
    if repeated is not None:
        raise _RefusedError(
            "document_not_canonical",
            "a key is repeated in one object; a document carrying two values for one member has "
            "no canonical form",
            pointer=repeated,
        )
    if not isinstance(document, dict):
        raise _RefusedError("invalid_request", "the request body must be a JSON object", pointer="")
    return document


def _numeric(operation: Operation, name: str) -> bool:
    """Whether the request schema declares member `name` an integer or a number."""
    properties = operation.request_schema.get("properties")
    member = properties.get(name) if isinstance(properties, Mapping) else None
    if not isinstance(member, Mapping):
        return False
    declared = member.get("type")
    types = {declared} if isinstance(declared, str) else set(declared or ())
    return bool(types & _NUMERIC_TYPES)


def _query_value(operation: Operation, name: str, text: str) -> Any:
    if _numeric(operation, name) and _JSON_NUMBER.fullmatch(text):
        return json.loads(text)
    return text


def _add(document: dict[str, Any], name: str, value: Any) -> None:
    if name in document:
        raise _RefusedError(
            "invalid_request",
            f"the member {name!r} is given more than once (path, query or body)",
            pointer=f"/{_escape(name)}",
        )
    document[name] = value


async def _request_document(request: Request, operation: Operation) -> dict[str, Any]:
    """§11.3's flattening: body members, then path parameters, then query parameters."""
    document = await _body(request) if request.method == "POST" else {}
    for name, value in request.path_params.items():
        _add(document, name, value)
    for name, text in request.query_params.multi_items():
        _add(document, name, _query_value(operation, name, text))
    return document


# ================================================================================= the routes


class OperationRoute(Route):
    """One row of `OPERATIONS` at its verb and path, matched on the **raw** path.

    Each path parameter is one percent-encoded segment, decoded after the match (§4.3), so an
    artifact id's `/` travels as `%2F` and `/v1/artifacts/{artifact_id}` never swallows the
    `/raw` of the export. The route carries exactly its verb: no implicit `HEAD`.
    """

    def __init__(self, operation: Operation, endpoint: Callable[[Request], Awaitable[Response]]):
        assert operation.http is not None
        verb, path = operation.http
        super().__init__(path, endpoint, methods=[verb], name=operation.name)
        self.methods = {verb}
        self.operation = operation

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        raw = scope.get("raw_path") if scope["type"] == "http" else None
        if raw is None:
            return super().matches(scope)
        match, child = super().matches({**scope, "path": raw.decode("latin-1"), "root_path": ""})
        if match is not Match.NONE:
            child["path_params"] = {
                name: unquote(value) if isinstance(value, str) else value
                for name, value in child["path_params"].items()
            }
        return match, child


def _endpoint(owner: Owner, operation: Operation) -> Callable[[Request], Awaitable[Response]]:
    async def endpoint(request: Request) -> Response:
        caller: Dispatchable | None = None
        try:
            caller = await _caller(owner, request)
            document = await _request_document(request, operation)
            result = await run_in_threadpool(dispatch, caller, operation.name, document)
        except _RefusedError as refused:
            if caller is not None:
                await run_in_threadpool(caller.audit_refusal, operation.name, refused.error.code)
            headers = (
                {"WWW-Authenticate": "Bearer"} if refused.error.code == "unauthenticated" else None
            )
            return _error_response(refused.error, headers)
        except ApplicationError as raised:
            headers = {"WWW-Authenticate": "Bearer"} if raised.code == "unauthenticated" else None
            return _error_response(raised.error, headers)
        except Exception:
            return _internal_error(operation.name)
        if operation.response_schema is None:
            assert isinstance(result, bytes)
            digest = await run_in_threadpool(lambda: hashlib.sha256(result).hexdigest())
            return _raw_response(result, digest)
        return Response(_json_bytes(result), media_type=_JSON_MEDIA_TYPE)

    return endpoint


async def _no_route(request: Request, _: Exception) -> Response:
    path = request.scope.get("raw_path", request.url.path.encode()).decode("latin-1")
    return _error_response(
        ApiError(
            code="not_found",
            message="no operation is served at this path; a '/' inside a path parameter (an "
            "artifact id) is sent percent-encoded, as %2F",
            retryable=False,
            detail={"path": path},
        )
    )


async def _wrong_method(request: Request, _: Exception) -> Response:
    allowed = ", ".join(
        sorted(
            verb
            for route in request.app.router.routes
            if isinstance(route, OperationRoute)
            and route.matches(request.scope)[0] is not Match.NONE
            for verb in route.methods or ()
        )
    )
    return _error_response(
        ApiError(
            code="invalid_request",
            message=f"this path is not served for {request.method}",
            retryable=False,
            detail={"method": request.method, "allowed": allowed},
        ),
        {"Allow": allowed},
    )


def create_app(owner: Owner) -> Starlette:
    """The ASGI application serving `owner`: one `OperationRoute` per HTTP row of `OPERATIONS`,
    in the table's order, and nothing else — no CORS, no middleware of its own."""
    application = Starlette(
        routes=[
            OperationRoute(operation, _endpoint(owner, operation)) for operation in HTTP_OPERATIONS
        ],
        exception_handlers={404: _no_route, 405: _wrong_method},
    )
    application.router.redirect_slashes = False
    return application


# ================================================================================== serving


def is_loopback(host: str) -> bool:
    """Whether `host` names the loopback interface only (`localhost`, 127.0.0.0/8, `::1`)."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def serve(
    owner: Owner,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    allow_remote: bool = False,
    log_level: str = "info",
) -> None:
    """§11.2: serve `owner` over HTTP with uvicorn until interrupted. `serve-http`'s body.

    The caller opens the owner (`LocalApplication.open(project, executor="process")`) and closes
    it once this returns. A host other than the loopback interface is refused unless
    `allow_remote`, and then served with a warning on stderr that v0.1 has no TLS.
    """
    run(create_app(owner), host=host, port=port, allow_remote=allow_remote, log_level=log_level)


def run(
    application: Starlette,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    allow_remote: bool = False,
    log_level: str = "info",
) -> None:
    """`serve`'s rules — loopback unless `allow_remote`, the no-TLS warning, uvicorn's options —
    applied to an application built over `create_app` (`bindings.web` adds the shell to it)."""
    if not is_loopback(host):
        if not allow_remote:
            raise ValueError(
                f"{host!r} is not a loopback address; serving beyond this host needs "
                "allow_remote (--allow-remote), and v0.1 has no TLS"
            )
        print(
            f"openflowsheet: serving on {host}:{port} without TLS (v0.1 has none); bearer "
            "tokens cross the network in clear text",
            file=sys.stderr,
        )
    uvicorn.run(
        application,
        host=host,
        port=port,
        log_level=log_level,
        proxy_headers=False,
        server_header=False,
    )
