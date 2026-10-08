"""The diagnostic web shell's server: the HTTP binding, unchanged, plus its static files at `/ui/`.

M06 design note §5.2 and §7, ADR 0030 D3. `create_web_app(owner)` is `http.create_app(owner)`
with two routes added after every `OPERATIONS` route — a static mount of the packaged shell
(`openflowsheet.resources.packaged("web")`, the `_data/web` → `apps/web/` link in a checkout, the
files themselves in a wheel) at `/ui`, and a `307` from `/` to `/ui/` — and one middleware that
sets the shell's security headers on every response whose path is `/ui` or below it. The headers
are a middleware rather than a wrapper of the mount so that the responses the mount does not
write itself — the binding's `not_found` and `invalid_request` documents for a missing file or a
method a file does not carry — carry the Content-Security-Policy too. Every other response, the
API's included, passes through untouched: `serve-http` without `--ui` and the API under `--ui`
answer byte for byte alike.

The static files hold no project data; every data request the shell makes is an `OPERATIONS`
route and needs the bearer token (§7). There is no CORS here either.

**Imports** (T07 design note §11.6 (2), extended by M06 §5.2): the binding's own list plus
`bindings.http` and `openflowsheet.resources` (standard library only); never `local` or `authz`.
"""

from __future__ import annotations

import mimetypes
import sys
from pathlib import Path
from types import MappingProxyType
from typing import Final

from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from openflowsheet.application.bindings.http import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    Owner,
    create_app,
    is_loopback,
    run,
)
from openflowsheet.resources import packaged

__all__ = [
    "MOUNT",
    "SHELL_HEADERS",
    "WebShellMissingError",
    "create_web_app",
    "serve",
    "static_directory",
]

#: Where the shell is served; no `OPERATIONS` path starts with it (a static scan holds this).
MOUNT: Final[str] = "/ui"
#: §5.2: set on every response at or below `MOUNT`, replacing a value the response had.
CONTENT_SECURITY_POLICY: Final[str] = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
SHELL_HEADERS: Final = MappingProxyType(
    {
        "Content-Security-Policy": CONTENT_SECURITY_POLICY,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-cache",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
    }
)
#: The file whose absence means the shell is not installed (`serve-http --ui` refuses to start).
INDEX: Final[str] = "index.html"

# §5.2: the system's MIME tables differ, and a module script served as `text/plain` does not run.
for _suffix, _type in (
    (".js", "text/javascript"),
    (".css", "text/css"),
    (".svg", "image/svg+xml"),
    (".html", "text/html"),
):
    mimetypes.add_type(_type, _suffix)


class WebShellMissingError(RuntimeError):
    """The shell's files are not where the package says they are: `serve-http --ui` refuses."""


def static_directory() -> Path:
    """The directory the shell is served from: the packaged `web` directory, resolved (so the
    checkout's `_data/web` link is followed once, and nothing inside it is). Raises
    `WebShellMissingError` when it is not a directory on the file system holding `index.html`."""
    shell = packaged("web")
    if not isinstance(shell, Path):
        raise WebShellMissingError(
            "the diagnostic web shell's files are not on the file system (the package is "
            "imported from an archive); install the wheel to a directory"
        )
    directory = shell.resolve()
    if not (directory / INDEX).is_file():
        raise WebShellMissingError(
            f"the diagnostic web shell's files are missing: no {INDEX} in {directory} (the "
            "package data `openflowsheet/_data/web`)"
        )
    return directory


def _is_shell_path(path: str) -> bool:
    return path == MOUNT or path.startswith(f"{MOUNT}/")


class _ShellHeaders:
    """ASGI middleware: `SHELL_HEADERS` on the response start of every request at or below
    `MOUNT`, whichever layer wrote it; every other request passes through untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _is_shell_path(scope["path"]):
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SHELL_HEADERS.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _to_shell(_: Request) -> Response:
    return RedirectResponse(f"{MOUNT}/", status_code=307)


def create_web_app(owner: Owner, directory: Path | None = None) -> Starlette:
    """`http.create_app(owner)` with the shell: the static mount at `MOUNT` (files from
    `directory`, by default `static_directory()`), `GET /` → `307 /ui/`, and the headers."""
    application = create_app(owner)
    static = StaticFiles(directory=directory or static_directory(), html=True)
    application.router.routes += [
        Mount(MOUNT, app=static),
        Route("/", _to_shell, methods=["GET"]),
    ]
    application.add_middleware(_ShellHeaders)
    return application


def serve(
    owner: Owner,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    allow_remote: bool = False,
    log_level: str = "info",
) -> None:
    """`serve-http --ui`'s body: `http.serve`'s rules (loopback unless `allow_remote`, the
    no-TLS warning) over `create_web_app(owner)`, until interrupted."""
    application = create_web_app(owner)
    if is_loopback(host) or allow_remote:
        print(f"openflowsheet: web shell at http://{host}:{port}{MOUNT}/", file=sys.stderr)
    run(application, host=host, port=port, allow_remote=allow_remote, log_level=log_level)
