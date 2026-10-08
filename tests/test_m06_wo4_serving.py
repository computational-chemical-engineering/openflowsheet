"""M06 WO-4: `serve-http --ui` serves the diagnostic web shell beside the unchanged API.

Design note §5.2 and §7 (ADR 0030 D3), gates G8 (headers) and G10 (packaging, the in-tree
half). Over a `TestClient`: the exact Content-Security-Policy and the other shell headers on every
response at or below `/ui` — the files, and the binding's own `not_found`/`invalid_request`
documents for a missing file or a wrong method — the content types the browser needs to run a
module script, `/` → `307 /ui/`, and the API's responses byte for byte equal with and without the
shell. Through the CLI: `--ui` refuses to start without the packaged files, and without `--ui`
nothing of the shell is imported. Through a real `openflowsheet serve-http --ui` subprocess
(`scripts/m06_web_serve_check.py`, which CI's clean-install job runs against the installed
wheel): the same files over uvicorn.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.authz import grant
from openflowsheet.application.cli import main
from openflowsheet.application.local import LocalApplication

#: Every test here serves the shell, so it needs the server extra. The skip is a mark, not a
#: module-level `importorskip`, so the tests are collected (and skipped) without the extra: T08.A22
#: resolves its evidence references by collection (M06 review F2c).
SERVER_EXTRA = all(
    importlib.util.find_spec(name) is not None for name in ("starlette", "httpx", "uvicorn")
)
if SERVER_EXTRA:
    from starlette.testclient import TestClient

    from openflowsheet.application.bindings import http, web

pytestmark = [
    pytest.mark.skipif(
        not SERVER_EXTRA, reason="needs the server extra (starlette, httpx, uvicorn)"
    ),
    pytest.mark.filterwarnings("ignore:Using `httpx` with `starlette.testclient` is deprecated"),
]

#: §5.2, verbatim: the string every `/ui` response carries.
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
SHELL_HEADERS = {
    "content-security-policy": CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cache-control": "no-cache",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
}
SHELL = REPO_ROOT / "apps" / "web"


class Pair:
    """One project served twice: by `http.create_app` and by `web.create_web_app`."""

    def __init__(self, directory: Path) -> None:
        self.owner = LocalApplication.create(directory, project_id="m06-wo4")
        _, token = grant(directory, principal_id="agent-ui", rights=("read",))
        self.headers = {"Authorization": f"Bearer {token}"}
        self.api = TestClient(http.create_app(self.owner), raise_server_exceptions=False)
        self.ui = TestClient(web.create_web_app(self.owner), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def pair(tmp_path_factory: pytest.TempPathFactory) -> Any:
    served = Pair(tmp_path_factory.mktemp("wo4") / "project")
    yield served
    served.owner.close()


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    """`main(argv)` in-process: its exit code, stdout and stderr (as `test_t07_w5b_cli`)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exited:
            code = exited.code if isinstance(exited.code, int) else 1
    return code, out.getvalue(), err.getvalue()


def _assert_shell_headers(response: Any) -> None:
    for name, value in SHELL_HEADERS.items():
        assert response.headers.get_list(name) == [value], (name, response.request.url)


@pytest.mark.parametrize(
    ("path", "media_type"),
    [
        ("/ui/", "text/html; charset=utf-8"),
        ("/ui/index.html", "text/html; charset=utf-8"),
        ("/ui/favicon.svg", "image/svg+xml"),
    ],
)
def test_a_shell_file_is_served_with_its_type_and_the_shell_headers(
    pair: Pair, path: str, media_type: str
) -> None:
    response = pair.ui.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"] == media_type
    name = "index.html" if path.endswith("/") else path.rsplit("/", 1)[1]
    assert response.content == (SHELL / name).read_bytes()
    _assert_shell_headers(response)


def test_every_shell_file_is_served_byte_for_byte_with_a_runnable_type(pair: Pair) -> None:
    """Every file under `apps/web/` (the package data, G10): a `.js` file as `text/javascript`
    (a module script under any other type does not run) and a `.css` file as `text/css`."""
    types = {
        ".html": "text/html; charset=utf-8",
        ".svg": "image/svg+xml",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
    }
    files = sorted(path for path in SHELL.rglob("*") if path.is_file())
    assert files
    for path in files:
        response = pair.ui.get(f"/ui/{path.relative_to(SHELL).as_posix()}")
        assert response.status_code == 200, path
        assert response.headers["content-type"] == types[path.suffix], path
        assert response.content == path.read_bytes(), path
        _assert_shell_headers(response)


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("GET", "/ui/no-such-file.js", 404, "not_found"),
        ("GET", "/ui/..%2F..%2Fpyproject.toml", 404, "not_found"),
        ("GET", "/ui", 404, "not_found"),
        ("POST", "/ui/", 422, "invalid_request"),
    ],
)
def test_a_refusal_below_the_mount_is_the_binding_s_error_and_carries_the_headers(
    pair: Pair, method: str, path: str, status: int, code: str
) -> None:
    """The reason the headers are a middleware, not a wrapper of the mount: these responses are
    written by the binding's exception handlers, outside the static app."""
    response = pair.ui.request(method, path)
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    assert response.json()["code"] == code
    _assert_shell_headers(response)


def test_the_root_redirects_to_the_shell(pair: Pair) -> None:
    response = pair.ui.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"
    assert pair.api.get("/", follow_redirects=False).status_code == 404


def test_the_api_answers_byte_for_byte_alike_with_and_without_the_shell(pair: Pair) -> None:
    """Status, every header and the body: authorised reads, a 401, an unknown route, a method a
    route does not carry, a refused request shape, and a browser's preflight (no CORS)."""
    requests: list[tuple[str, str, dict[str, str]]] = [
        ("GET", "/v1/project", pair.headers),
        ("GET", "/v1/revisions?limit=5", pair.headers),
        ("GET", "/v1/models", pair.headers),
        ("GET", "/v1/project", {}),
        ("GET", "/v1/project", {"Authorization": "Bearer prt_unknown"}),
        ("GET", "/v1/no-such-route", pair.headers),
        ("DELETE", "/v1/project", pair.headers),
        ("GET", "/v1/revisions?limit=zero", pair.headers),
        ("OPTIONS", "/v1/jobs", {"Origin": "http://evil.example"}),
    ]
    for method, path, headers in requests:
        before = pair.api.request(method, path, headers=headers)
        after = pair.ui.request(method, path, headers=headers)
        assert after.status_code == before.status_code, path
        assert after.headers.multi_items() == before.headers.multi_items(), path
        assert after.content == before.content, path
        assert "content-security-policy" not in after.headers


def test_no_operation_route_is_at_or_below_the_mount() -> None:
    assert web.MOUNT == "/ui"
    paths = [operation.http[1] for operation in http.HTTP_OPERATIONS if operation.http]
    assert paths and not [path for path in paths if path == "/ui" or path.startswith("/ui/")]


def test_the_headers_are_the_note_s_and_the_static_directory_is_the_repository_copy() -> None:
    assert {name.lower(): value for name, value in web.SHELL_HEADERS.items()} == SHELL_HEADERS
    assert web.static_directory() == SHELL.resolve()


# ============================================================================== the CLI


def test_ui_refuses_to_start_without_the_packaged_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    LocalApplication.create(project, project_id="m06-wo4").close()
    empty = tmp_path / "web"
    empty.mkdir()
    monkeypatch.setattr(web, "packaged", lambda relative: empty)
    with pytest.raises(web.WebShellMissingError, match="index.html"):
        web.static_directory()
    called: list[Any] = []
    monkeypatch.setattr(web, "serve", lambda *a, **k: called.append(a))
    code, out, err = run_cli(["serve-http", "--project", str(project), "--port", "0", "--ui"])
    assert (code, out, called) == (1, "", [])
    assert "serve-http: refused to start: the diagnostic web shell's files are missing" in err


def test_ui_serves_through_the_web_binding_and_without_it_the_http_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    LocalApplication.create(project, project_id="m06-wo4").close()
    called: list[str] = []
    monkeypatch.setattr(http, "serve", lambda owner, **options: called.append("http"))
    monkeypatch.setattr(web, "serve", lambda owner, **options: called.append("web"))
    assert run_cli(["serve-http", "--project", str(project), "--port", "0"])[0] == 0
    assert run_cli(["serve-http", "--project", str(project), "--port", "0", "--ui"])[0] == 0
    assert called == ["http", "web"]


def test_without_ui_the_web_binding_is_not_imported(tmp_path: Path) -> None:
    """`serve-http` without `--ui` is today's command: `bindings.web` never loads."""
    project = tmp_path / "project"
    LocalApplication.create(project, project_id="m06-wo4").close()
    probe = (
        "import sys\n"
        "from openflowsheet.application.bindings import http\n"
        "from openflowsheet.application import cli\n"
        "http.serve = lambda owner, **options: None\n"
        f"assert cli.main(['serve-http', '--project', {str(project)!r}, '--port', '0']) == 0\n"
        "print('openflowsheet.application.bindings.web' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, timeout=120
    )
    assert result.stdout.strip() == "False"


def test_a_real_server_serves_the_shell(tmp_path: Path) -> None:
    """G10's in-tree half: `openflowsheet serve-http --ui` over uvicorn, from this interpreter,
    answered by `scripts/m06_web_serve_check.py` (CI runs it against the installed wheel)."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "m06_web_serve_check.py"), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "m06_web_serve_check: PASSED" in result.stdout
