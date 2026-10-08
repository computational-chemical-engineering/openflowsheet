"""M06 WO-11: the web shell in a real browser — gates G1 (dynamic half), G8 (DOM half) and G11.

Design note `docs/design/M06-web-shell.md` §8 A6. The W26 fixture project
(`scripts/m06_web_fixtures.py`, `build_fixture_project`) is built in a temporary directory and
served by `create_web_app` with uvicorn on a free loopback port in a thread, wrapped — in this
test only — by an ASGI recorder of every request (method, raw path, query, whether it carried a
credential, status, start and end). A headless Chromium (`m06_browser_support`) opens each route
of §6 cold, in a fresh browser context, at `http://127.0.0.1:<port>/ui/#<route>?token=<token>`
(the fragment never reaches the server), waits for `<html data-ofs-ready="1">`, and reads the
serialized DOM. Asserted per route:

- **G11**: ready marker 1, no `#ofs-fatal`, no `data-ofs-error`, the route's screen and its marker
  texts (the design note's G7 numbers where a route shows them), no console error, uncaught
  exception or JavaScript dialog (a CSP violation is a console error), and the boot token gone
  from the address;
- **G1 (dynamic)**: every request is a static file under `/ui/` or an `OPERATIONS` route with
  its verb; `prt_` occurs in no path or query; the credential travels on contract calls only;
  the operations reached are among §6's 17 — and over the whole module, exactly the 17;
- **G8 (DOM)**: rev-000005's title (markup, then U+202E) renders as text with U+FFFD in place of
  U+202E: no `<img`, no element carrying an `on…` attribute, one script element (the module) —
  on the project list and the revision overview, and, once the hostile revision has been solved,
  in the JSON tree of its "revision as solved", where the hostile description is shown too. The
  two kinds of path differ: a projected document (`list_revisions`, `get_revision`) arrives with
  U+202E already replaced by the server's projection (`projection.FORBIDDEN_RANGES`), so only
  the raw export reaches the browser with U+202E in it and exercises the shell's own `sanitize`
  (measured: with `sanitize` disabled, only the raw-export case fails). Markup is text on both.

What the Node tests stub is exercised here against the real server: **Solve** (the dialog's
submit, through `submit_job`) and the **live job** path (`wait_job` long-polls, one outstanding
call at a time, while a real worker is held at its `solve` stage by the process executor's test
hook; the screen reloads itself when the job ends); **Cancel** of a running job (through
`cancel_job`, the job ending `cancelled`); and the two **download** buttons (the saved file's
bytes are the raw export's).

The binary is `OPENFLOWSHEET_BROWSER`, else the first of `chromium, chromium-browser,
google-chrome` on `PATH`. Without one the module is skipped with that reason — and **fails**
when `OPENFLOWSHEET_REQUIRE_BROWSER=1` (CI's x86-64 leg).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import socket
import sys
import threading
import time
from collections.abc import Awaitable, Callable, Iterator, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import REPO_ROOT
from m06_browser_support import (
    BROWSER_VARIABLE,
    CANDIDATES,
    REQUIRE_VARIABLE,
    Browser,
    Page,
    find_browser,
)
from test_m06_static_scan import UI_OPERATIONS

from openflowsheet.application.jobs.executor import ProcessExecutor
from openflowsheet.application.jobs.worker import (
    PAUSE_AT_STAGE_VARIABLE,
    PAUSED_FILE,
    RESUME_FILE,
)
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch

pytestmark = [
    pytest.mark.browser,
    pytest.mark.filterwarnings("ignore:Using `httpx` with `starlette.testclient` is deprecated"),
]

BINARY: Final[str | None] = find_browser()
if BINARY is None:
    _REASON = f"no browser: set {BROWSER_VARIABLE} or put one of {', '.join(CANDIDATES)} on PATH"
    if os.environ.get(REQUIRE_VARIABLE) == "1":
        pytest.fail(f"{REQUIRE_VARIABLE}=1 and {_REASON}", pytrace=False)
    pytest.skip(_REASON, allow_module_level=True)

uvicorn = pytest.importorskip("uvicorn")
pytest.importorskip("starlette")

from openflowsheet.application.bindings.web import create_web_app  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "m06_web_fixtures", REPO_ROOT / "scripts" / "m06_web_fixtures.py"
)
assert _spec is not None and _spec.loader is not None
fixtures = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("m06_web_fixtures", fixtures)
_spec.loader.exec_module(fixtures)

#: rev-000005's title and description as the DOM serializes text: markup escaped, U+202E → U+FFFD.
HOSTILE_TITLE_TEXT: Final[str] = "&lt;img src=x onerror=alert(1)&gt;�evil"
HOSTILE_DESCRIPTION_TEXT: Final[str] = "&lt;script&gt;alert(2)&lt;/script&gt;�evil description"
#: §6.1: the key the Solve dialog draws.
SOLVE_KEY: Final[re.Pattern[str]] = re.compile(r"ui-solve-[0-9a-f]{32}")
#: The run stage at which the held worker waits (`jobs.worker`'s test hook).
HOLD_STAGE: Final[str] = "solve"


# ==================================================================================== recorder


@dataclass
class Request:
    method: str
    path: str
    query: str
    authorized: bool
    started: float
    status: int | None = None
    ended: float | None = None


Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
ASGIApp = Callable[
    [Scope, Callable[[], Awaitable[Message]], Callable[[Message], Awaitable[None]]],
    Awaitable[None],
]


class Recorder:
    """§8 A6's ASGI recorder (test only): every HTTP request the server sees, in order."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.requests: list[Request] = []
        self._lock = threading.Lock()

    async def __call__(
        self,
        scope: Scope,
        receive: Callable[[], Awaitable[Message]],
        send: Callable[[Message], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        entry = Request(
            method=scope["method"],
            path=scope["raw_path"].decode("latin-1"),
            query=scope["query_string"].decode("latin-1"),
            authorized=any(name == b"authorization" for name, _ in scope["headers"]),
            started=time.monotonic(),
        )
        with self._lock:
            self.requests.append(entry)

        async def recording_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                entry.status = message["status"]
            elif message["type"] == "http.response.body" and not message.get("more_body"):
                entry.ended = time.monotonic()
            await send(message)

        await self.app(scope, receive, recording_send)

    def mark(self) -> int:
        with self._lock:
            return len(self.requests)

    def since(self, mark: int) -> list[Request]:
        with self._lock:
            return list(self.requests[mark:])


def _operation_patterns() -> list[tuple[str, str, re.Pattern[str]]]:
    patterns = []
    for name, operation in OPERATIONS.items():
        if operation.http is None:
            continue
        verb, path = operation.http
        regex = re.sub(r"\\\{[a-z_]+\\\}", "[^/]+", re.escape(path))
        patterns.append((name, verb, re.compile(f"^{regex}$")))
    return patterns


PATTERNS: Final = _operation_patterns()


def operation_of(request: Request) -> str | None:
    """The `OPERATIONS` row `request` is (verb and path), or `None`."""
    found = [
        name
        for name, verb, regex in PATTERNS
        if verb == request.method and regex.match(request.path)
    ]
    assert len(found) <= 1, (request, found)
    return found[0] if found else None


def contract_only(requests: list[Request]) -> set[str]:
    """G1 (dynamic) over `requests`: each a static file under `/ui/` or an `OPERATIONS` route;
    no `prt_` in any path or query; the credential on contract calls and on nothing else. The
    operations reached."""
    reached: set[str] = set()
    assert requests, "the browser made no request"
    for request in requests:
        assert "prt_" not in request.path and "prt_" not in request.query, request
        if request.path == "/ui/" or request.path.startswith("/ui/"):
            assert request.method == "GET" and not request.authorized, request
            continue
        name = operation_of(request)
        assert name is not None, f"not static and not an OPERATIONS route: {request}"
        assert request.authorized, request
        reached.add(name)
    assert reached <= UI_OPERATIONS, reached - UI_OPERATIONS
    return reached


#: Every operation the module's tests reached, for the whole-module G1 check.
REACHED: set[str] = set()
#: The tests of this module that ran to the end (the whole-module check needs all of them).
FINISHED: set[str] = set()
#: The job that solved a revision, by revision (the raw G8 case reads its bundle).
SOLVED: dict[str, str] = {}


# ======================================================================================= server


@dataclass
class Shell:
    project: Any  # m06_web_fixtures.FixtureProject
    owner: LocalApplication
    recorder: Recorder
    browser: Browser
    port: int
    downloads: Path
    pages: list[Page] = field(default_factory=list)

    def url(self, route: str, principal: str | None) -> str:
        fragment = route
        if principal is not None:
            joiner = "&" if "?" in route else "?"
            fragment = f"{route}{joiner}token={self.project.tokens[principal]}"
        return f"http://127.0.0.1:{self.port}/ui/#{fragment}"

    def job_directory(self, job_id: str) -> Path:
        return Path(self.project.path) / "jobs" / job_id


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


@pytest.fixture(scope="module")
def shell(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Shell]:
    assert BINARY is not None
    base = tmp_path_factory.mktemp("m06-browser")
    project = fixtures.build_fixture_project(base / "project")
    # The process executor a server uses (`http.serve`), with the workers' test hooks, so a test
    # can hold a real job at a stage boundary.
    owner = LocalApplication.open(project.path, executor=ProcessExecutor(test_hooks=True))
    recorder = Recorder(create_web_app(owner))
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(recorder, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, name="m06-uvicorn", daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        assert thread.is_alive() and time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.02)
    downloads = base / "downloads"
    downloads.mkdir()
    browser = Browser(BINARY, base / "profile", downloads)
    try:
        yield Shell(project, owner, recorder, browser, port, downloads)
    finally:
        browser.close()
        server.should_exit = True
        thread.join(timeout=30)
        owner.close()


def open_route(shell: Shell, route: str, principal: str | None) -> tuple[Page, str]:
    """A cold page at `route` with `principal`'s boot token, once ready; its DOM."""
    page = shell.browser.page()
    page.navigate(shell.url(route, principal))
    page.wait_ready()
    return page, page.dom()


def assert_rendered(page: Page, dom: str, screen: str) -> None:
    """G11's per-page half: ready, no fatal marker or error flag, the screen, no problem."""
    found = re.search(r"<html\b[^>]*>", dom)
    assert found is not None, dom[:200]
    opening = found.group(0)
    assert 'data-ofs-ready="1"' in opening, opening
    assert "data-ofs-error" not in opening, opening
    assert 'id="ofs-fatal"' not in dom
    assert f'data-ofs-screen="{screen}"' in dom
    assert page.problems() == []
    assert "token=" not in page.evaluate("location.href")


# ================================================================================ G11 and G1


@dataclass(frozen=True)
class Route:
    route: str
    screen: str
    markers: tuple[str, ...]
    principal: str | None = "supervisor-c"
    absent: tuple[str, ...] = ()
    #: Non-200 statuses this route's contract calls answer (by design: a refusal shown).
    refusals: tuple[int, ...] = ()
    #: `(job, variable, short)`: the route shows `repr` of the variable's value in the solution
    #: state that job recorded here, a value `short` (the G7 short form, also a marker) begins.
    #: The fixture re-solves on the host, and x86-64 hosts disagree on a converged float's
    #: trailing digits (`ci.yml`, above the `check` matrix), so the full-precision text is read
    #: from the run, not written here (M06 review F2a). The Node tests hold `fmt` to the
    #: committed fixture's digits exactly.
    solved: tuple[tuple[str, str, str], ...] = ()


def solved_text(shell: Shell, job_id: str, variable: str) -> str:
    """`repr` of `variable`'s value in the solution state `job_id` recorded on this host — read
    as the shell reads it: the job's result, its replay bundle, the bundle's
    `solution-state.json` member's bytes."""
    result = shell.owner.get_job_result(job_id)
    assert result.run_result is not None, job_id
    (bundle,) = [o for o in result.run_result.outputs if o.kind == "replay_bundle"]
    stored = shell.owner.artifact_bytes(f"{bundle.artifact_id}/solution-state.json")
    value = json.loads(stored)["variables"][variable]
    assert isinstance(value, float), (job_id, variable, value)
    return repr(value)


#: §6's routes. Markers are what the route must show: the design note's G7 numbers where the
#: route shows them, the fixture project's ids and outcomes (§8) elsewhere.
ROUTES: Final[tuple[Route, ...]] = (
    Route("/", "project", ("m06-web-fixtures", "rev-000005", "job-000003", HOSTILE_TITLE_TEXT)),
    Route(
        "/rev/rev-000001",
        "revision",
        ("READY_FOR_SIMULATION", "U-HEAT", "<svg", "S6", "job-000001", "needs the execute right"),
    ),
    Route(
        "/rev/rev-000001",
        "revision",
        ('data-ofs-action="solve"',),
        principal="agent-a",
        absent=("needs the execute right",),
    ),
    Route("/rev/rev-000001/validation", "validation", ("READY_FOR_SIMULATION", "SCHEMA-01")),
    Route("/rev/rev-000003/validation", "validation", ("INVALID",)),
    Route("/rev/rev-000001/row/U-HEAT%3AHEAT-duty", "equation", ("U-HEAT:HEAT-duty", "heat_rate")),
    Route(
        "/job/job-000001",
        "job",
        ("CONVERGED", "VERIFIED", "BOUND_BLOCKED", ">338<", "<td>match</td>"),
        absent=("mismatch", "unchecked", "data-ofs-digest"),
    ),
    Route("/job/job-000003", "job", ("HOMOTOPY_STALLED", "T04-W12"), absent=("mismatch",)),
    Route(
        "/job/job-000001/certificate",
        "certificate",
        ("VERIFIED", ">144<", "near_threshold", "residual.U-HEAT:HEAT-duty"),
    ),
    Route(
        "/job/job-000003/failure",
        "failure",
        ("HOMOTOPY_STALLED", "T04-W12", ">2104<", "hypothesis", "phase_boundary_on_path"),
    ),
    Route(
        "/job/job-000001/streams",
        "streams",
        (">31487.6",),
        solved=(("job-000001", "U-HEAT.Q", "31487.6"),),
    ),
    Route("/job/job-000003/streams", "streams", ("no solution state recorded for this run",)),
    Route(
        "/job/job-000001/row/U-HEAT%3AHEAT-duty",
        "equation",
        (">31487.6",),
        solved=(("job-000001", "U-HEAT.Q", "31487.6"),),
    ),
    Route(
        "/job/job-000001/file/solve-path.json",
        "file",
        ("solve_path", ">match<"),
        absent=("mismatch", "data-ofs-digest"),
    ),
    Route("/compare/rev/rev-000001/rev-000002", "compare-revisions", ("U-SPLIT", "split_fraction")),
    Route("/compare/run/job-000001/job-000002", "compare-runs", ("not judged", "job-000002")),
    Route("/history", "history", ("supervisor-c",)),
    Route("/history?principal=all", "history", ("viewer-b", "forbidden", "commit_change")),
    Route(
        "/history?principal=all",
        "history",
        ('data-ofs-refused="forbidden"',),
        principal="viewer-b",
        refusals=(403,),
    ),
    Route("/rev/rev-000005", "revision", (HOSTILE_TITLE_TEXT, "READY_FOR_SIMULATION")),
    Route("/nowhere", "not-found", ("No such screen",)),
    Route("/login", "login", ("Sign in to OpenFlowsheet",), principal=None),
)


@pytest.mark.parametrize("case", ROUTES, ids=[f"{case.principal}:{case.route}" for case in ROUTES])
def test_g11_every_screen_renders_and_reaches_only_the_contract(shell: Shell, case: Route) -> None:
    mark = shell.recorder.mark()
    page, dom = open_route(shell, case.route, case.principal)
    try:
        assert_rendered(page, dom, case.screen)
        for marker in case.markers:
            assert marker in dom, marker
        for job_id, variable, short in case.solved:
            full = solved_text(shell, job_id, variable)
            assert full.startswith(short) and full != short, (variable, full)
            assert full in dom, full
        for marker in case.absent:
            assert marker not in dom, marker
        requests = shell.recorder.since(mark)
        REACHED.update(contract_only(requests))
        statuses = {r.status for r in requests if operation_of(r) is not None} - {200}
        assert statuses == set(case.refusals), statuses
    finally:
        page.close()
    FINISHED.add(f"g11 {case.principal}:{case.route}")


def test_a_bad_token_lands_on_login_with_the_server_s_message(shell: Shell) -> None:
    mark = shell.recorder.mark()
    page = shell.browser.page()
    try:
        page.navigate(f"http://127.0.0.1:{shell.port}/ui/#/rev/rev-000001?token=prt_not-a-grant")
        page.wait_ready()
        page.wait_for("location.hash.startsWith('#/login')", "the login screen")
        page.wait_ready()
        dom = page.dom()
        assert_rendered(page, dom, "login")
        assert "a bearer credential" in dom or "unauthenticated" in dom or "token" in dom
        # The screen asked for comes back after sign-in; the token is not kept anywhere.
        assert page.evaluate("location.hash").startswith("#/login?next=")
        assert page.evaluate("sessionStorage.length + localStorage.length") == 0
        requests = shell.recorder.since(mark)
        REACHED.update(contract_only(requests))
        assert [r.status for r in requests if operation_of(r) is not None] == [401]
    finally:
        page.close()
    FINISHED.add("bad token")


# ========================================================================================= G8


def assert_inert(page: Page, dom: str) -> None:
    """G8 (DOM): hostile text is text — no `<img`, no element with an `on…` attribute, the one
    module script, U+202E nowhere, no dialog."""
    assert "<img" not in dom
    assert "‮" not in dom
    assert page.evaluate("document.images.length") == 0
    assert page.evaluate("document.scripts.length") == 1
    assert (
        page.evaluate(
            "[...document.querySelectorAll('*')].filter(e => [...e.attributes].some("
            "a => a.name.startsWith('on'))).length"
        )
        == 0
    )
    assert page.problems() == []


@pytest.mark.parametrize("route", ["/", "/rev/rev-000005"])
def test_g8_the_hostile_title_renders_as_text(shell: Shell, route: str) -> None:
    page, dom = open_route(shell, route, "supervisor-c")
    try:
        assert HOSTILE_TITLE_TEXT in dom
        assert_inert(page, dom)
    finally:
        page.close()
    FINISHED.add(f"g8 {route}")


# =========================================================== Solve, the live job, Cancel, download


def _wait_file(path: Path, what: str, patience_s: float = 60) -> None:
    deadline = time.monotonic() + patience_s
    while not path.exists():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.02)


def _release(shell: Shell, job_id: str) -> None:
    """Let a held worker go on (a no-op once the job has ended)."""
    directory = shell.job_directory(job_id)
    if directory.is_dir():
        (directory / RESUME_FILE).write_text("", encoding="utf-8")


def _not_overlapping(requests: list[Request]) -> None:
    """§5.4: one outstanding `wait_job` per view — each starts after the previous one ended."""
    previous_end = 0.0
    for request in requests:
        assert request.ended is not None, request
        assert request.started >= previous_end, "two wait_job calls outstanding at once"
        previous_end = request.ended


def test_solve_follows_the_live_job_until_it_ends(
    shell: Shell, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Solve rev-000005 from its overview; the run screen is live while the worker is held at
    the solve stage (`wait_job` long-polls), and loads itself again when the job has ended; the
    revision as solved then shows the hostile description as text."""
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, HOLD_STAGE)
    mark = shell.recorder.mark()
    job_id: str | None = None
    page, dom = open_route(shell, "/rev/rev-000005", "agent-a")
    try:
        assert_rendered(page, dom, "revision")
        page.click("[data-ofs-action=solve] summary")
        page.wait_for("document.querySelector('[data-ofs-action=solve]').open", "the dialog")
        page.click("[data-ofs-action=solve] button[type=submit]")
        page.wait_for("location.hash.startsWith('#/job/')", "the run screen")
        address: str = page.evaluate("location.hash")
        job_id = address.removeprefix("#/job/")
        assert re.fullmatch(r"job-\d{6}", job_id), job_id
        # The job is real and held: the screen is live and following it.
        _wait_file(shell.job_directory(job_id) / PAUSED_FILE, "the worker to pause")
        page.wait_ready()
        page.wait_for(
            "document.querySelector('[data-ofs-screen=job][data-ofs-live=\"1\"]') !== null", "live"
        )
        page.wait_for(
            "[...document.querySelectorAll('[data-ofs-screen=job] dt')].some("
            "dt => dt.textContent === 'status' && dt.nextSibling.textContent.includes('running'))",
            "the running status",
        )
        assert "Job events (live)" in page.dom()
        job = shell.owner.store.get_job(job_id)
        assert job is not None and job.status == "running"
        assert SOLVE_KEY.fullmatch(job.request.idempotency_key), job.request.idempotency_key
        assert job.principal_id == "agent-a"
        # The worker continues; the outstanding wait_job answers, and the screen reloads ended.
        _release(shell, job_id)
        page.wait_for(
            "document.querySelector('[data-ofs-screen=job][data-ofs-live=\"0\"]') !== null"
            " && document.documentElement.getAttribute('data-ofs-ready') === '1'",
            "the ended run screen",
            patience_s=120,
        )
        dom = page.dom()
        assert_rendered(page, dom, "job")
        for marker in ("completed", "CONVERGED", "VERIFIED", "rev-000005", "<td>match</td>"):
            assert marker in dom, marker
        assert "Job events (live)" not in dom
        requests = shell.recorder.since(mark)
        reached = contract_only(requests)
        assert {"submit_job", "wait_job", "get_job_result", "artifact_bytes"} <= reached
        submits = [r for r in requests if operation_of(r) == "submit_job"]
        assert [r.status for r in submits] == [200]
        waits = [r for r in requests if operation_of(r) == "wait_job"]
        assert waits and all(f"/v1/jobs/{job_id}/" in r.path for r in waits)
        assert all(r.status == 200 for r in waits)
        _not_overlapping(waits)
        REACHED.update(reached)
    finally:
        page.close()
        if job_id is not None:  # never leave the one worker held
            _release(shell, job_id)
    assert job_id is not None
    SOLVED["rev-000005"] = job_id
    FINISHED.add("solve")


def test_g8_the_raw_revision_as_solved_renders_as_text(shell: Shell) -> None:
    """The hostile revision as solved, read through the raw export (bytes, not a projection: it
    holds U+202E), as a bundle member's JSON tree: title and description are text."""
    if "rev-000005" not in SOLVED:
        pytest.fail("needs test_solve_follows_the_live_job_until_it_ends to have solved rev-000005")
    raw = _stored(shell, f"{SOLVED['rev-000005']}:bundle/revision.json")
    assert "\u202e".encode() in raw  # the record holds the character the DOM must not
    page, dom = open_route(shell, f"/job/{SOLVED['rev-000005']}/file/revision.json", "supervisor-c")
    try:
        assert_rendered(page, dom, "file")
        assert HOSTILE_TITLE_TEXT in dom and HOSTILE_DESCRIPTION_TEXT in dom
        assert_inert(page, dom)
    finally:
        page.close()
    FINISHED.add("g8 raw")


def test_cancel_stops_a_running_job(shell: Shell, monkeypatch: pytest.MonkeyPatch) -> None:
    """A job held at its solve stage; Cancel on its run screen; it ends `cancelled`, and the
    screen shows it ended."""
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, HOLD_STAGE)
    agent = shell.owner.authenticated(shell.project.tokens["agent-a"])
    assert agent is not None
    submitted = dispatch(
        agent,
        "submit_job",
        {
            "operation": "solve",
            "idempotency_key": "browser-cancel",
            "body": {"revision_id": "rev-000001", "policy_id": "default"},
        },
    )
    job_id = submitted["job"]["job_id"]
    _wait_file(shell.job_directory(job_id) / PAUSED_FILE, "the worker to pause")
    mark = shell.recorder.mark()
    page, dom = open_route(shell, f"/job/{job_id}", "agent-a")
    try:
        assert_rendered(page, dom, "job")
        assert 'data-ofs-live="1"' in dom
        page.click("[data-ofs-action=cancel]")
        page.wait_for(
            "document.querySelector('[data-ofs-screen=job][data-ofs-live=\"0\"]') !== null"
            " && document.documentElement.getAttribute('data-ofs-ready') === '1'",
            "the ended run screen",
            patience_s=120,
        )
        dom = page.dom()
        assert_rendered(page, dom, "job")
        assert "cancelled" in dom
        assert 'data-ofs-action="cancel"' not in dom
        job = shell.owner.store.get_job(job_id)
        assert job is not None and job.status == "cancelled"
        requests = shell.recorder.since(mark)
        reached = contract_only(requests)
        cancels = [r for r in requests if operation_of(r) == "cancel_job"]
        assert [r.status for r in cancels] == [200]
        assert all(f"/v1/jobs/{job_id}/" in r.path for r in cancels)
        # Cancel navigates (the screen is loaded again): the first view's long-poll is aborted
        # by the browser, but the server answers it only when it returns. One outstanding call
        # per view, then: the waits before the cancel, and those after it, each one at a time.
        waits = [r for r in requests if operation_of(r) == "wait_job"]
        assert waits and all(f"/v1/jobs/{job_id}/" in r.path for r in waits)
        _not_overlapping([r for r in waits if r.started < cancels[0].started])
        _not_overlapping([r for r in waits if r.started > cancels[0].started])
        REACHED.update(reached)
    finally:
        page.close()
        _release(shell, job_id)
    FINISHED.add("cancel")


def _download(shell: Shell, page: Page, element: str, what: str) -> tuple[dict[str, Any], bytes]:
    """Click `element` (a JS expression) and wait for the download it starts to complete."""
    seen = len(shell.browser.events())
    page.click_element(element, what)

    def began(event: dict[str, Any]) -> bool:
        return (
            event["method"] == "Browser.downloadWillBegin"
            and event in shell.browser.events()[seen:]
        )

    begun = shell.browser.wait_event(began, f"a download from {what}")["params"]
    guid = begun["guid"]
    done = shell.browser.wait_event(
        lambda event: event["method"] == "Browser.downloadProgress"
        and event["params"]["guid"] == guid
        and event["params"]["state"] in {"completed", "canceled"},
        f"the download from {what} to end",
    )["params"]
    assert done["state"] == "completed", done
    return begun, (shell.downloads / guid).read_bytes()


def _stored(shell: Shell, artifact_id: str) -> bytes:
    row = shell.owner.store.artifact(artifact_id)
    assert row is not None
    return (shell.owner.files_root / row.relpath).read_bytes()


def test_the_download_buttons_save_the_recorded_bytes(shell: Shell) -> None:
    mark = shell.recorder.mark()
    page, dom = open_route(shell, "/job/job-000001/file/solve-path.json", "supervisor-c")
    try:
        assert_rendered(page, dom, "file")
        begun, saved = _download(
            shell, page, "document.querySelector('[data-ofs-action=download]')", "the file screen"
        )
        assert begun["suggestedFilename"] == "solve-path.json"
        assert begun["url"].startswith(f"blob:http://127.0.0.1:{shell.port}/")
        assert saved == _stored(shell, "job-000001:bundle/solve-path.json")
        assert page.problems() == []
    finally:
        page.close()
    page, dom = open_route(shell, "/job/job-000001", "supervisor-c")
    try:
        assert_rendered(page, dom, "job")
        row = (
            "[...document.querySelectorAll('tr')].find(tr => tr.cells[0]"
            " && tr.cells[0].textContent === 'run-manifest.json').querySelector('button')"
        )
        begun, saved = _download(shell, page, row, "the run screen's bundle files")
        assert begun["suggestedFilename"] == "run-manifest.json"
        stored = _stored(shell, "job-000001:bundle/run-manifest.json")
        assert saved == stored
        supervisor = shell.owner.authenticated(shell.project.tokens["supervisor-c"])
        assert supervisor is not None
        listing = dispatch(
            supervisor,
            "get_artifact",
            {"artifact_id": "job-000001:bundle", "depth": 12, "limit": 200, "pointer": ""},
        )
        (member,) = (f for f in listing["value"]["files"] if f["name"] == "run-manifest.json")
        assert member["sha256"] == hashlib.sha256(saved).hexdigest()
        assert page.problems() == []
    finally:
        page.close()
    REACHED.update(contract_only(shell.recorder.since(mark)))
    FINISHED.add("download")


# ================================================================================== G1, whole


def test_g1_over_the_module_the_browser_reached_exactly_the_seventeen(shell: Shell) -> None:
    """Every request of the module's browser sessions (including any between pages) is static or
    an `OPERATIONS` route, and the operations reached are §6's 17 — no more, no fewer."""
    expected = {f"g11 {case.principal}:{case.route}" for case in ROUTES} | {
        "bad token",
        "g8 /",
        "g8 /rev/rev-000005",
        "solve",
        "g8 raw",
        "cancel",
        "download",
    }
    missing = expected - FINISHED
    if missing:
        # Under -k or a reordering plugin this check cannot run. Where the browser gate is
        # required, that is a failure, not a silent skip (M06 review F9).
        reason = f"needs the module's other tests to have run first: {sorted(missing)}"
        if os.environ.get(REQUIRE_VARIABLE) == "1":
            pytest.fail(f"{REQUIRE_VARIABLE}=1 and {reason}", pytrace=False)
        pytest.skip(reason)
    reached = contract_only(shell.recorder.since(0))
    assert reached == REACHED == UI_OPERATIONS, sorted(UI_OPERATIONS - reached)


def test_the_recorder_matches_every_http_row_and_nothing_else() -> None:
    """The recorder's route matcher, checked on its own: each HTTP row's path with values in its
    parameters matches that row only; a static path, the API under another verb, and an unknown
    path match none."""
    for name, operation in OPERATIONS.items():
        if operation.http is None:
            continue
        verb, path = operation.http
        filled = re.sub(r"\{[a-z_]+\}", "x%2Fy", path)
        assert operation_of(Request(verb, filled, "", True, 0.0)) == name
    assert operation_of(Request("GET", "/ui/js/api.js", "", False, 0.0)) is None
    assert operation_of(Request("DELETE", "/v1/project", "", True, 0.0)) is None
    assert operation_of(Request("GET", "/v1/nothing", "", True, 0.0)) is None
    with pytest.raises(AssertionError):
        contract_only([Request("GET", "/v1/nothing", "", True, 0.0)])
    with pytest.raises(AssertionError):
        contract_only([Request("GET", "/v1/project", "token=prt_x", True, 0.0)])
    with pytest.raises(AssertionError):
        contract_only([Request("GET", "/ui/", "", True, 0.0)])
