"""T07 W6e: the conformance suite — no transport adds anything to `dispatch` (§11.6 (3), G14).

Design note `docs/design/T07-jobs-and-bindings.md` §11.6 (3), §16 G14. **One scenario**
(`Scenario.run`) runs against five clients, each on a fresh project (same project id, same policy
file, so ids, ordinals and every `policy_sha256` agree):

| client | transport | executor | caller | compared with |
| --- | --- | --- | --- | --- |
| `PythonClient` (inline) | `dispatch`, an owner per call | inline | local owner | (reference) |
| `CliClient` | `main(["api", …])` in-process | inline | local owner | Python (inline) |
| `PythonClient` (process) | `dispatch` on one owner | process | the grant | (reference) |
| `HttpClient` | httpx `ASGITransport` | process | the grant (bearer) | Python (process) |
| `McpClient` | the SDK's in-memory client session | process | the grant | Python (process) |

**Why two references.** The CLI runs jobs inline only (W5b-Q1: a one-shot command closes its
project, and closing a process executor ends its jobs), and each `api` call opens the project as
a fresh owner. So the CLI is held to `dispatch` under the same executor and the same
owner-per-call; the servers are held to `dispatch` under the process executor as the same
principal. A step names an operation; a client that does not carry it (HTTP and MCP: `solve`,
`reproduce`; MCP: `artifact_bytes`) skips it, and so does its reference — the three the servers
skip either create jobs (so the process reference skips them too) or are reads.

**What is compared.** Every step's outcome — error or not, and the document — after removing the
members that are clock readings or host facts (`stable`): §11.6's list (`recorded_at`,
`created_at`, `started_at`, `ended_at`, `elapsed_seconds`, `hostname`, `environment`, the
`worker_log` references' digest and size), extended by W5b's finding — the `sha256` and
`size_bytes` of `run_manifest` and `replay_bundle` references, whose bytes hold `started_at` and
`elapsed_seconds` — by the validation report's `provenance.timestamp`, and by the random part of
the `auto:<uuid4>` key an in-process `solve` or `reproduce` draws for its job (with that job's
`request_sha256`, which hashes it). Each extension is a clock or a random draw of the method,
which `dispatch` makes the same way; none is something a transport adds. Two relations loosen
the comparison, each for a stated reason, never for a transport's convenience:

- `live`: a response that reads a job while a process worker may be moving it (a first submit:
  `queued` or `running`; a cancel of a running job: `running` or already `cancelled`). The
  members a running job changes (`status`, `progress`, `event_count`, `outputs`, `ending`,
  `error`) are compared in the job's final read instead, which is `equal`.
- `code`: HTTP's refusal of a revoked credential. §10.2 has HTTP present its token on every
  request, so a revoked token is refused by the transport before any method runs (401,
  `unauthenticated`, its own message, not audited); in-process and over MCP the capability was
  authenticated at open, and the method refuses it. The code and `retryable` must agree.

**Scenarios**: every operation's success path; every `ApiError` code each transport can reach
(`REACHABLE`); duplicate submit and commit, and key reuse; cancel of a queued job, of a running
one (cooperative, held by §15 W4c's pause hook) and of an ended one; pagination across a page
boundary (revisions, a revision's array, jobs, events, an artifact's array); a newer producer's
job — an output of unknown kind, an unknown event mid-stream, an unknown kind that ends the job
(J5 (d)). Not the V17 reference solutions: W7c adds those, with their own budget.

**Smoke tests**, one per transport beyond the in-process ones: the CLI as a subprocess, the HTTP
server started by `openflowsheet serve-http` on a loopback port, and the MCP server started by
`openflowsheet serve-mcp` over stdio.

Budget: the whole module ≤ 120 s wall on the reference host (§11.6); `--durations` reports it.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t07_jobs_support import PATIENCE_S, Pause, lifecycle_violations
from t07_mcp_support import environment
from t07_process_support import wait_until
from t07_transport_support import (
    ALL,
    NEWER_JOB,
    SERVED,
    CliClient,
    Client,
    HttpClient,
    McpClient,
    Outcome,
    PythonInline,
    PythonProcess,
    ThreadStream,
    dispatched,
    inject_newer_producers_job,
)

from openflowsheet.application.authz import grant, revoke
from openflowsheet.application.jobs.executor import COMPUTE_LOCK
from openflowsheet.application.jobs.worker import PAUSE_AT_STAGE_VARIABLE, PAUSED_FILE
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.store import DATABASE_NAME, POLICY_NAME
from openflowsheet.application.types import Limits

NOMINAL = "SYN-001-nominal"
PROJECT_ID = "t07-conformance"
PRINCIPAL = "agent-conformance"
CAPABILITY = "cap-conformance"
#: Two active jobs: a running one and a queued one fit, a third is `limit_exceeded`.
LIMITS = Limits(default_wall_time_s=600.0, max_wall_time_s=1800.0, max_active_jobs=2)
#: The process worker's pause (§15 W4c) and the inline one (the first interruption check).
PAUSE_STAGE = "solve"
PAUSE_CHECK = 1
#: §11.6 (3)'s strip list, and its extensions (module docstring).
VOLATILE = frozenset(
    {
        "recorded_at",
        "created_at",
        "started_at",
        "ended_at",
        "elapsed_seconds",
        "hostname",
        "environment",
        "timestamp",
    }
)
CLOCKED_REFS = frozenset({"run_manifest", "replay_bundle", "worker_log"})
#: §5.1: the key prefix in-process `solve` and `reproduce` draw a random key under.
AUTO = "auto:"
#: What a running job changes; a `live` step leaves them to the job's final read.
LIVE = frozenset({"status", "progress", "event_count", "outputs", "ending", "error"})
#: §5.8's codes each transport reaches in the scenario. Not reachable anywhere:
#: `revision_unsupported` (G9: a READY corpus revision always has a route; W3c reaches it only by
#: replacing `select_route`) and `internal_error` (a defect). Not reachable as the local owner
#: (§10.2: all rights, no limits): `forbidden`, `unauthenticated`, `limit_exceeded`. MCP has no
#: raw export, the one `unsupported` a request can reach.
_COMMON = {
    "invalid_request",
    "document_not_canonical",
    "not_found",
    "idempotency_key_reused",
    "not_ready",
    "revision_not_ready",
    "verification_weakening_refused",
    "budget_exceeds_ceiling",
}
_GRANT = {"forbidden", "unauthenticated", "limit_exceeded"}
REACHABLE = {
    "python-inline": _COMMON | {"unsupported"},
    "cli": _COMMON | {"unsupported"},
    "python-process": _COMMON | _GRANT | {"unsupported"},
    "http": _COMMON | _GRANT | {"unsupported"},
    "mcp": _COMMON | _GRANT,
}
pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)


# ============================================================================ comparison


def stable(document: Any) -> Any:
    """`document` without its clock readings and host facts (§11.6's list, extended), and
    without the random part of an in-process `solve`'s or `reproduce`'s `auto:` key."""
    if isinstance(document, dict):
        drop = VOLATILE
        if document.get("kind") in CLOCKED_REFS and "artifact_id" in document:
            drop = drop | {"sha256", "size_bytes"}
        request = document.get("request")
        if isinstance(request, dict) and str(request.get("idempotency_key")).startswith(AUTO):
            # §4.2: the method draws the key (`auto:<uuid4>`); the job's request hash covers it.
            document = {**document, "request": {**request, "idempotency_key": AUTO}}
            drop = drop | {"request_sha256"}
        return {k: stable(v) for k, v in document.items() if k not in drop}
    if isinstance(document, list):
        return [stable(item) for item in document]
    return document


def settled(document: Any) -> Any:
    """A `live` read: a job (or a submit result's job) without what a running job changes."""
    if isinstance(document, dict) and isinstance(document.get("job"), dict):
        return {**document, "job": settled(document["job"])}
    if isinstance(document, dict) and "job_id" in document and "status" in document:
        return {k: v for k, v in document.items() if k not in LIVE}
    return document


def differences(a: Any, b: Any, pointer: str = "") -> list[str]:
    """Where two documents differ, as RFC 6901 pointers with both values (a failure's message)."""
    if isinstance(a, dict) and isinstance(b, dict):
        found = []
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                found.append(f"{pointer}/{key}: only in {'b' if key not in a else 'a'}")
            else:
                found += differences(a[key], b[key], f"{pointer}/{key}")
        return found
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [
            d
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for d in differences(x, y, f"{pointer}/{i}")
        ]
    return [] if a == b else [f"{pointer}: {a!r:.200} != {b!r:.200}"]


@dataclass
class Step:
    label: str
    operation: str
    request: Any
    outcome: Outcome
    relation: str = "equal"  # "equal", "live", "code" (module docstring)


# ============================================================================== the pauses


class InlineArm:
    """The inline pause (§15 W4c's `test_hook_on_check`) on the owner a call opens next: the CLI
    and the inline reference open a fresh owner per call, so the hook goes on as it opens."""

    def __init__(self) -> None:
        self.pending: Pause | None = None
        self.lock = threading.Lock()

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original = LocalApplication.open
        arm = self

        def open_(cls: type[LocalApplication], *args: Any, **kwargs: Any) -> LocalApplication:
            app = original(*args, **kwargs)
            with arm.lock:
                pause, arm.pending = arm.pending, None
            if pause is not None:
                app.executor.test_hook_on_check = pause
            return app

        monkeypatch.setattr(LocalApplication, "open", classmethod(open_))

    def arm(self, at: int) -> Pause:
        with self.lock:
            assert self.pending is None
            self.pending = Pause(at)
            return self.pending


class Background:
    """`body()` in a thread; `join` returns its result or raises its error."""

    def __init__(self, body: Callable[[], Any]) -> None:
        self.result: Any = None
        self.error: BaseException | None = None

        def run() -> None:
            try:
                self.result = body()
            except BaseException as error:  # re-raised in the test's thread
                self.error = error

        self.thread = threading.Thread(target=run)
        self.thread.start()

    def join(self) -> Any:
        self.thread.join(PATIENCE_S)
        assert not self.thread.is_alive(), "the background call never returned"
        if self.error is not None:
            raise self.error
        return self.result


def _queued_job(project: Path) -> str | None:
    with contextlib.closing(sqlite3.connect(project / DATABASE_NAME)) as connection:
        row = connection.execute("SELECT job_id FROM jobs WHERE status = 'queued'").fetchone()
    return None if row is None else str(row[0])


# ============================================================================ the scenario


def _edits(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"operation": "set", "path": [key], "value": value} for key, value in document.items()]


@dataclass
class Scenario:
    """§11.6 (3)'s scenario list, run on one client. `shared` is a directory every client's run
    uses for the in-process `reproduce`'s bundle path, so the requests are equal."""

    client: Client
    shared: Path
    arm: InlineArm
    steps: list[Step] = field(default_factory=list)

    # -- steps --------------------------------------------------------------------------------

    def step(self, label: str, name: str, request: Any, relation: str = "equal") -> Any:
        """Call `name` if the client carries it; the response document (`None` if skipped)."""
        if name not in self.client.carries:
            return None
        outcome = self.client.call(name, request)
        self.steps.append(Step(label, name, request, outcome, relation))
        return outcome[1]

    def ok(self, label: str, name: str, request: Any, relation: str = "equal") -> Any:
        response = self.step(label, name, request, relation)
        assert response is not None and not self.steps[-1].outcome[0], (label, response)
        return response

    def stream(self, label: str, job_id: str) -> dict[str, Any]:
        """Follow a job with `wait_job` to its end; one step holding every event and the ended job
        (how many waits it takes is the clock's, so the waits themselves are not steps)."""
        events: list[Any] = []
        after = -1
        while True:
            error, waited = self.client.call(
                "wait_job", {"job_id": job_id, "after_sequence": after, "timeout_s": 30}
            )
            assert not error, waited
            events.extend(waited["events"])
            if waited["events"]:
                after = waited["events"][-1]["sequence"]
            if waited["ended"]:
                break
        document = {"events": events, "job": waited["job"]}
        self.steps.append(Step(label, "wait_job", {"job_id": job_id}, (False, document)))
        return document

    def run_job(self, label: str, request: dict[str, Any]) -> str:
        relation = "live" if self.client.mode == "process" else "equal"
        job_id = str(self.ok(f"{label} submit", "submit_job", request, relation)["job"]["job_id"])
        self.stream(f"{label} stream", job_id)
        return job_id

    # -- the scenario -------------------------------------------------------------------------

    def run(self) -> list[Step]:
        c = self.client
        self.ok("project", "get_project", {})
        self.ok("models", "list_models", {})

        # Revisions: commit, replay, key reuse, preview, validation, pagination, views.
        first = {"edits": _edits(CORPUS[NOMINAL]()), "expected_revision": None}
        first["idempotency_key"] = "c1"
        rev1 = self.ok("commit", "commit_change", first)["revision_id"]
        self.ok("commit replayed", "commit_change", first)
        self.step("commit key reused", "commit_change", {**first, "expected_revision": rev1})
        title = [{"operation": "set", "path": ["title"], "value": "conformance"}]
        self.ok("preview", "preview_change", {"edits": title, "expected_revision": rev1})
        second = {"edits": title, "expected_revision": rev1, "idempotency_key": "c2"}
        rev2 = self.ok("commit title", "commit_change", second)["revision_id"]
        broken = CORPUS[NOMINAL]()
        broken["connections"][0]["to"]["instance"] = "nowhere"
        third = {"edits": _edits(broken), "expected_revision": rev2, "idempotency_key": "c3"}
        rev3 = self.ok("commit broken", "commit_change", third)["revision_id"]
        self.ok("validate", "validate", {"revision_id": rev2, "task": "simulation"})
        self.ok("validate broken", "validate", {"revision_id": rev3, "task": "simulation"})
        page = self.ok("revisions 1", "list_revisions", {"limit": 2})
        assert page["next_cursor"] is not None
        self.ok("revisions 2", "list_revisions", {"limit": 2, "cursor": page["next_cursor"]})
        view = {"revision_id": rev1, "pointer": "/connections", "limit": 2}
        part = self.ok("revision array 1", "get_revision", view)
        assert part["next_cursor"] is not None
        self.ok("revision array 2", "get_revision", {**view, "cursor": part["next_cursor"]})
        self.ok("diff", "diff_revisions", {"from_revision": rev1, "to_revision": rev3})
        self.ok("structure", "inspect_structure", {"revision_id": rev2, "depth": 2})

        # Refusals that create nothing.
        self.step("no job", "get_job", {"job_id": "job-999999"})
        self.step("no revision", "validate", {"revision_id": "absent", "task": "simulation"})
        self.step("no result", "get_job_result", {"job_id": "job-999999"})
        self.step("schema", "list_jobs", {"limit": 0})
        self.step("bad cursor", "list_revisions", {"cursor": "not-a-cursor"})
        huge = [{"operation": "set", "path": ["title"], "value": 2**53 + 1}]
        self.step(
            "non-canonical",
            "commit_change",
            {"edits": huge, "expected_revision": rev3, "idempotency_key": "c4"},
        )

        def solve(key: str, revision: str = rev2, **body: Any) -> dict[str, Any]:
            return {
                "operation": "solve",
                "idempotency_key": key,
                "body": {"revision_id": revision, **body},
            }

        self.step("reserved key", "submit_job", solve("auto:mine"))
        self.step("not ready", "submit_job", solve("s-broken", rev3))
        self.step("weakening", "submit_job", solve("s-loose", check_tolerances={"molar_flow": 1.0}))
        self.step("call budget", "submit_job", solve("s-calls", max_property_calls=10**9))
        self.step("no policy", "submit_job", solve("s-policy", policy_id="no-such-policy"))
        if c.grant:
            wall = {**solve("s-wall"), "budgets": {"wall_time_s": 10.0**6}}
            self.step("wall budget", "submit_job", wall)

        # Cancellation: a queued job, a running one (paused), and later an ended one.
        if c.mode == "process":
            self._cancel_under_the_process_executor(solve)
        else:
            self._cancel_under_the_inline_executor(solve)

        # A solve to its end, then everything that reads it.
        d = self.run_job("D", solve("s-d"))
        self.ok("D replayed", "submit_job", solve("s-d"))
        self.step("D key reused", "submit_job", solve("s-d", policy_id="T06-revision-v2"))
        ended = self.ok("D job", "get_job", {"job_id": d})
        result = self.ok("D result", "get_job_result", {"job_id": d})
        run = result["run_result"]
        assert (run["outcome"], run["verification_status"]) == ("CONVERGED", "VERIFIED")
        self.ok("D wait ended", "wait_job", {"job_id": d, "timeout_s": 0})
        self.ok("D cancel ended", "cancel_job", {"job_id": d})
        events = self.ok("D events 1", "list_job_events", {"job_id": d, "limit": 3})
        after = int(events["next_cursor"])
        self.ok("D events 2", "list_job_events", {"job_id": d, "after_sequence": after, "limit": 3})
        jobs = self.ok("jobs 1", "list_jobs", {"limit": 2})
        self.ok("jobs 2", "list_jobs", {"limit": 2, "cursor": jobs["next_cursor"]})
        (certificate,) = [o for o in ended["outputs"] if o["kind"] == "solution_certificate"]
        self.ok("certificate", "get_artifact", {"artifact_id": certificate["artifact_id"]})
        state = f"{d}:bundle/solution-state.json"
        ids = {"artifact_id": state, "pointer": "/variable_ids", "limit": 5}
        part = self.ok("state ids 1", "get_artifact", ids)
        self.ok("state ids 2", "get_artifact", {**ids, "cursor": part["next_cursor"]})
        self.step("no pointer", "get_artifact", {"artifact_id": state, "pointer": "/nowhere"})
        self.step("state bytes", "artifact_bytes", {"artifact_id": state})
        self.step("bundle bytes", "artifact_bytes", {"artifact_id": f"{d}:bundle"})

        # A reproduce job of D's bundle (inspection only), and its report.
        reproduce = {
            "operation": "reproduce",
            "idempotency_key": "s-r",
            "body": {"bundle_artifact_id": f"{d}:bundle", "rerun": False},
        }
        r = self.run_job("R", reproduce)
        report = self.ok("R result", "get_job_result", {"job_id": r})["replay_report"]
        assert (report["mode"], report["verdict"]) == ("inspected_archived_results", "NOT_RUN")

        # The in-process operations (Python and the CLI): solve and reproduce by path.
        if "solve" in c.carries:
            self.ok("solve", "solve", {"revision_id": rev2, "policy_id": "default"})
            bundle = self.shared / "bundle"
            shutil.rmtree(bundle, ignore_errors=True)
            shutil.copytree(c.project / "jobs" / d / "bundle", bundle)
            path = {"bundle_path": str(bundle), "policy": {"rerun": False}}
            self.ok("reproduce", "reproduce", path)
            self.step("reproduce nowhere", "reproduce", {**path, "bundle_path": str(bundle / "x")})

        # J5 (d): a newer producer's job, served whole; its `ends_job` ends it.
        inject_newer_producers_job(c.project)
        self.ok("newer job", "get_job", {"job_id": NEWER_JOB})
        self.ok("newer events", "list_job_events", {"job_id": NEWER_JOB})
        waited = self.ok(
            "newer wait", "wait_job", {"job_id": NEWER_JOB, "after_sequence": 3, "timeout_s": 0}
        )
        assert waited["ended"] is True
        self.ok("completed jobs", "list_jobs", {"status": "completed", "limit": 200})
        # The local owner's job: another principal needs `policy` to cancel it (§10.1).
        self.step("newer cancel", "cancel_job", {"job_id": NEWER_JOB})

        # A revoked grant is refused on its next call (§10.2).
        if c.grant:
            revoke(c.project, CAPABILITY)
            relation = "code" if c.transport == "http" else "equal"
            self.step("revoked", "get_project", {}, relation)
        return self.steps

    def _cancel_under_the_process_executor(self, solve: Callable[..., dict[str, Any]]) -> None:
        """A paused worker (A), a queued job behind it (B, one worker slot), a third over the
        grant's two active jobs (C); B cancelled while queued, A while running."""
        project = self.client.project
        os.environ[PAUSE_AT_STAGE_VARIABLE] = PAUSE_STAGE
        try:
            a = self.ok("A submit", "submit_job", solve("s-a"), "live")["job"]["job_id"]
            paused = project / "jobs" / a / PAUSED_FILE
            wait_until(lambda: paused.is_file() and paused.read_text("utf-8") != "", "A's pause")
        finally:
            del os.environ[PAUSE_AT_STAGE_VARIABLE]
        self.step("A not ready", "get_job_result", {"job_id": a})
        submitted = self.ok("B submit", "submit_job", solve("s-b"))
        assert submitted["job"]["status"] == "queued"
        b = submitted["job"]["job_id"]
        self.step("C over the limit", "submit_job", solve("s-c"))
        cancelled = self.ok("B cancel queued", "cancel_job", {"job_id": b})
        assert cancelled["status"] == "cancelled" and cancelled["outputs"] == []
        running = self.ok("A cancel running", "cancel_job", {"job_id": a}, "live")
        assert running["cancel_requested"] is True
        assert running["status"] in ("running", "cancelled")
        self._ended_by_cancel(a, b)

    def _cancel_under_the_inline_executor(self, solve: Callable[..., dict[str, Any]]) -> None:
        """B submitted while the compute lock is held: queued, then cancelled from another call.
        A held at its first interruption check, cancelled from another call (another owner, so
        through the store), then released."""
        project = self.client.project
        with COMPUTE_LOCK:
            submit_b = Background(lambda: self.ok("B submit", "submit_job", solve("s-b")))
            wait_until(lambda: _queued_job(project) is not None, "B queued")
            b = _queued_job(project)
            assert b is not None
            cancelled = self.ok("B cancel queued", "cancel_job", {"job_id": b})
            assert cancelled["status"] == "cancelled" and cancelled["outputs"] == []
        submit_b.join()
        pause = self.arm.arm(PAUSE_CHECK)
        submit_a = Background(lambda: self.ok("A submit", "submit_job", solve("s-a")))
        try:
            assert pause.reached.wait(PATIENCE_S), "A never reached its pause"
            a = pause.job_id
            assert a is not None
            self.step("A not ready", "get_job_result", {"job_id": a})
            running = self.ok("A cancel running", "cancel_job", {"job_id": a})
            assert (running["status"], running["cancel_requested"]) == ("running", True)
        finally:
            pause.release.set()
        submit_a.join()
        self._ended_by_cancel(a, b)

    def _ended_by_cancel(self, a: str, b: str) -> None:
        streamed = self.stream("A stream", a)
        assert streamed["job"]["status"] == "cancelled"
        self.ok("A job", "get_job", {"job_id": a})
        result = self.ok("A result", "get_job_result", {"job_id": a})
        assert result["error"] is None or result["error"]["code"] != "internal_error"
        self.ok("B job", "get_job", {"job_id": b})


# ================================================================================ the runs


@dataclass
class Run:
    client: str
    steps: list[Step]
    wall_s: float
    violations: dict[str, Any]


def _project(root: Path, name: str, policy: bytes) -> Path:
    project = root / name
    LocalApplication.create(project, project_id=PROJECT_ID).close()
    (project / POLICY_NAME).write_bytes(policy)
    return project


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Run]:
    """The scenario on each of the five clients (module docstring), each on a fresh project."""
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    root = tmp_path_factory.mktemp("conformance")
    template = root / "template"
    LocalApplication.create(template, project_id=PROJECT_ID).close()
    capability, token = grant(
        template,
        principal_id=PRINCIPAL,
        rights=("draft", "execute", "read"),
        limits=LIMITS,
        capability_id=CAPABILITY,
    )
    policy = (template / POLICY_NAME).read_bytes()
    shared = root / "shared"
    shared.mkdir()
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    factories: dict[str, Callable[[Path], Client]] = {
        "python-inline": PythonInline,
        "cli": lambda p: CliClient(p, root / "raw.bin", out, err),
        "python-process": lambda p: PythonProcess(p, capability),
        "http": lambda p: HttpClient(p, token),
        "mcp": lambda p: McpClient(p, capability),
    }
    arm = InlineArm()
    done: dict[str, Run] = {}
    with pytest.MonkeyPatch.context() as monkeypatch:
        arm.install(monkeypatch)
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)
        started = time.monotonic()
        for name, factory in factories.items():
            began = time.monotonic()
            client = factory(_project(root, name, policy))
            try:
                steps = Scenario(client, shared, arm).run()
            finally:
                client.close()
            with LocalApplication.open(client.project) as app:
                violations = {k: v for k, v in lifecycle_violations(app).items() if k != NEWER_JOB}
            done[name] = Run(name, steps, time.monotonic() - began, violations)
        total = time.monotonic() - started
    timings = ", ".join(
        f"{run.client} {len(run.steps)} steps {run.wall_s:.1f} s" for run in done.values()
    )
    print(f"\nT07 conformance: 5 scenario runs in {total:.1f} s wall ({timings})")
    return done


# =================================================================================== tests


@pytest.mark.parametrize(
    ("transport", "reference"),
    [("cli", "python-inline"), ("http", "python-process"), ("mcp", "python-process")],
)
def test_g14_every_transport_equals_dispatch(
    runs: dict[str, Run], transport: str, reference: str
) -> None:
    """Every step, in order, equal to the reference's same step (module docstring)."""
    got, expected = runs[transport].steps, runs[reference].steps
    carried = SERVED[transport]
    assert [s.label for s in got] == [s.label for s in expected if s.operation in carried]
    assert len({s.label for s in got}) == len(got)
    by_label = {s.label: s for s in expected}
    for step in got:
        want = by_label[step.label]
        (error, document), (want_error, want_document) = step.outcome, want.outcome
        assert error == want_error, (step.label, document, want_document)
        if isinstance(document, bytes):
            assert document == want_document, step.label
        elif step.relation == "equal":
            assert stable(document) == stable(want_document), (
                step.label,
                differences(stable(document), stable(want_document)),
            )
        elif step.relation == "live":
            assert stable(settled(document)) == stable(settled(want_document)), (
                step.label,
                differences(stable(settled(document)), stable(settled(want_document))),
            )
        else:
            assert step.relation == "code" and error
            assert (document["code"], document["retryable"]) == (
                want_document["code"],
                want_document["retryable"],
            ), step.label


@pytest.mark.parametrize("client", sorted(REACHABLE))
def test_every_reachable_api_error_code_is_reached(runs: dict[str, Run], client: str) -> None:
    codes = {s.outcome[1]["code"] for s in runs[client].steps if s.outcome[0]}
    assert codes == REACHABLE[client]


@pytest.mark.parametrize("client", sorted(REACHABLE))
def test_every_carried_operation_succeeds_at_least_once(runs: dict[str, Run], client: str) -> None:
    carried = {"python-inline": ALL, "python-process": SERVED["http"]}.get(client, None)
    carried = carried if carried is not None else SERVED[client]
    succeeded = {s.operation for s in runs[client].steps if not s.outcome[0]}
    assert succeeded == carried


@pytest.mark.parametrize("client", sorted(REACHABLE))
def test_g3_every_job_the_scenario_made_keeps_the_lifecycle(
    runs: dict[str, Run], client: str
) -> None:
    assert runs[client].violations == {}


def _outcome(run: Run, label: str) -> Any:
    (step,) = [s for s in run.steps if s.label == label]
    return step.outcome


@pytest.mark.parametrize("client", sorted(REACHABLE))
def test_the_cancellations_and_the_duplicates_behave(runs: dict[str, Run], client: str) -> None:
    """What the equalities above hold equal is also right: a queued job cancelled has no output
    and never started; a running one ends `cancelled(cancel_requested)` with no certificate,
    failure bundle or solver outcome (G5); a duplicate submit or commit is replayed, a key reused
    with another body is refused."""
    run = runs[client]
    b = _outcome(run, "B job")[1]
    assert (b["status"], b["ending"]["reason"], b.get("started_at")) == (
        "cancelled",
        "cancel_requested",
        None,
    )
    assert b["outputs"] == []
    a = _outcome(run, "A job")[1]
    assert (a["status"], a["ending"]["reason"]) == ("cancelled", "cancel_requested")
    kinds = {output["kind"] for output in a["outputs"]}
    assert kinds.isdisjoint({"solution_certificate", "failure_bundle", "replay_bundle"}), kinds
    assert _outcome(run, "A not ready")[1]["code"] == "not_ready"
    assert _outcome(run, "D replayed")[1]["replayed"] is True
    assert _outcome(run, "commit replayed")[1]["status"] == "replayed"
    for label in ("D key reused", "commit key reused"):
        assert _outcome(run, label)[1]["code"] == "idempotency_key_reused", label
    cancelled_ended = _outcome(run, "D cancel ended")[1]
    assert (cancelled_ended["status"], cancelled_ended["cancel_requested"]) == ("completed", False)


@pytest.mark.parametrize("client", ["cli", "http", "mcp"])
def test_j5_d_every_transport_serves_the_newer_producers_job_whole(
    runs: dict[str, Run], client: str
) -> None:
    run = runs[client]
    served = _outcome(run, "newer job")[1]
    assert [o["kind"] for o in served["outputs"]] == ["solution_certificate", "trajectory"]
    stream = _outcome(run, "newer events")[1]["items"]
    assert [e["kind"] for e in stream][-2:] == ["trajectory_segment_closed", "finished_v2"]
    assert stream[4]["segment"] == {"t_end": 10.0}
    assert [e["ends_job"] for e in stream] == [False] * 5 + [True]
    waited = _outcome(run, "newer wait")[1]
    assert waited["ended"] is True
    assert NEWER_JOB in {j["job_id"] for j in _outcome(run, "completed jobs")[1]["items"]}
    error, cancel = _outcome(run, "newer cancel")
    if client == "cli":  # the local owner's own job, ended: returned as it is
        assert error is False and cancel == served
    else:
        assert error is True and cancel["code"] == "forbidden"


def test_the_budget_of_the_scenario_runs(runs: dict[str, Run]) -> None:
    """§11.6: ≤ 120 s for the module on the reference host. The five scenario runs are the bulk;
    they are held to it here, the smoke tests' share is in `--durations`."""
    total = sum(run.wall_s for run in runs.values())
    assert total <= 120.0, {run.client: round(run.wall_s, 1) for run in runs.values()}


# ============================================================================ smoke tests


def _subprocess_cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "openflowsheet.application.cli", *argv],
        capture_output=True,
        text=True,
        check=False,
        env=environment(None),
        cwd=str(REPO_ROOT),
        timeout=300,
    )


def test_smoke_the_cli_as_a_subprocess(tmp_path: Path) -> None:
    """`openflowsheet api` as its own process: a commit and a solve job, run inline to its end
    in that process, each printed response equal to `dispatch`'s read of the same state."""
    project = tmp_path / "project"
    LocalApplication.create(project, project_id=PROJECT_ID).close()
    commit = {"edits": _edits(CORPUS[NOMINAL]()), "expected_revision": None}
    commit["idempotency_key"] = "c1"
    done = _subprocess_cli(
        "api", "commit_change", "--project", str(project), "--json", json.dumps(commit)
    )
    assert done.returncode == 0, done.stderr
    revision = json.loads(done.stdout)["revision_id"]
    solve = {"operation": "solve", "idempotency_key": "s", "body": {"revision_id": revision}}
    done = _subprocess_cli(
        "api", "submit_job", "--project", str(project), "--json", json.dumps(solve)
    )
    assert done.returncode == 0, done.stderr
    printed = json.loads(done.stdout)
    assert printed["job"]["status"] == "completed"
    with LocalApplication.open(project) as app:
        assert printed["job"] == dispatch(app, "get_job", {"job_id": printed["job"]["job_id"]})
        replayed = dispatched(app, "submit_job", solve)
    assert replayed == (False, {**printed, "replayed": True})


_LISTENING = re.compile(r"Uvicorn running on http://127\.0\.0\.1:(\d+)")


def test_smoke_serve_http_on_a_loopback_port(tmp_path: Path) -> None:
    """`openflowsheet serve-http` as an operator starts it (port 0: the kernel's choice, read
    from uvicorn's log): a real socket, the grant's token, a solve in a process worker to
    VERIFIED; each read equal to `dispatch` as the same principal; SIGINT stops it cleanly."""
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("uvicorn")
    project = tmp_path / "project"
    LocalApplication.create(project, project_id=PROJECT_ID).close()
    capability, token = grant(
        project, principal_id=PRINCIPAL, rights=("draft", "execute", "read"), limits=LIMITS
    )
    log = tmp_path / "server.log"
    with log.open("w") as handle:
        server = subprocess.Popen(
            [sys.executable, "-m", "openflowsheet.application.cli", "serve-http"]
            + ["--project", str(project), "--port", "0"],
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=environment(None),
            cwd=str(REPO_ROOT),
        )
    try:
        wait_until(
            lambda: _LISTENING.search(log.read_text()) is not None or server.poll() is not None,
            "the server to listen",
        )
        found = _LISTENING.search(log.read_text())
        assert found is not None, log.read_text()
        base = f"http://127.0.0.1:{found.group(1)}"
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=base, headers=headers, timeout=60) as client:
            commit = {"edits": _edits(CORPUS[NOMINAL]()), "expected_revision": None}
            commit["idempotency_key"] = "c1"
            revision = client.post("/v1/changes", json=commit).json()["revision_id"]
            body = {"operation": "solve", "idempotency_key": "s", "body": {"revision_id": revision}}
            job_id = client.post("/v1/jobs", json=body).json()["job"]["job_id"]
            wait = f"/v1/jobs/{job_id}/wait"
            while not client.get(wait, params={"timeout_s": 30}).json()["ended"]:
                pass
            result = client.get(f"/v1/jobs/{job_id}/result").json()
            served_job = client.get(f"/v1/jobs/{job_id}").json()
            project_view = client.get("/v1/project").json()
            refused = client.get("/v1/project", headers={"Authorization": "Bearer x"})
            assert refused.status_code == 401
        with LocalApplication.open(project, capability=capability) as direct:
            assert project_view == dispatch(direct, "get_project", {})
            assert served_job == dispatch(direct, "get_job", {"job_id": job_id})
        run = result["run_result"]
        assert (run["outcome"], run["verification_status"]) == ("CONVERGED", "VERIFIED")
        assert (project / "jobs" / job_id / "worker.log").is_file()  # a process worker ran it
    finally:
        server.send_signal(signal.SIGINT)
        try:
            code = server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            server.kill()
            raise
    assert code == 0, log.read_text()


def test_smoke_serve_mcp_over_stdio(tmp_path: Path) -> None:
    """`openflowsheet serve-mcp --token-file F` as a client starts it: the tools listed, and
    reads equal to `dispatch` as the same principal."""
    pytest.importorskip("mcp")
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    project = tmp_path / "project"
    LocalApplication.create(project, project_id=PROJECT_ID).close()
    capability, token = grant(project, principal_id=PRINCIPAL, rights=("read",))
    token_file = tmp_path / "token"
    token_file.write_text(token + "\n", encoding="utf-8")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "openflowsheet.application.cli", "serve-mcp"]
        + ["--project", str(project), "--token-file", str(token_file)],
        env=environment(None),
        cwd=str(REPO_ROOT),
    )

    async def session_body() -> tuple[list[str], Any, Any]:
        with anyio.fail_after(300), (tmp_path / "server.log").open("w") as errlog:
            async with (
                stdio_client(parameters, errlog=errlog) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = [tool.name for tool in (await session.list_tools()).tools]
                project_view = await session.call_tool("get_project", {})
                models = await session.call_tool("list_models", {})
                return tools, project_view.structuredContent, models.structuredContent

    tools, project_view, models = anyio.run(session_body)
    assert tools == [row.mcp_tool for row in OPERATIONS.values() if "mcp" in row.transports]
    with LocalApplication.open(project, capability=capability) as direct:
        assert project_view == dispatch(direct, "get_project", {})
        assert models == dispatch(direct, "list_models", {})
