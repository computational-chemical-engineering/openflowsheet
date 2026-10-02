"""Helpers for the T07 job tests and the job fixtures (design note §4.2, §6, §9.1). Not collected.

`commit` stores a corpus revision through the contract; `lifecycle_violations` runs the §6.3
checker over every job a project holds (gate G3); `response_schema_violations` holds the
JobControl responses about them to their published schemas (R4-G3); `cancel_while_queued`
produces a job that is cancelled before it starts, under the inline executor, by holding the
process-wide compute lock while another thread submits it — the job is accepted (queued) and
waits for the lock, and `cancel_job` ends it; `paused_at` holds a running job at a chosen
interruption check.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from openflowsheet.application.jobs.executor import COMPUTE_LOCK
from openflowsheet.application.jobs.model import (
    TERMINAL_STATUSES,
    LifecycleViolation,
    check_lifecycle,
)
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.types import (
    Change,
    DocumentSchemaError,
    Edit,
    Job,
    JobRequest,
    SubmitResult,
    validate_inline,
)

#: A generous bound on anything a test waits for; every wait here normally takes milliseconds.
PATIENCE_S = 60.0


def commit(
    application: LocalApplication, document: Mapping[str, Any], revision_id: str | None = None
) -> str:
    """Store `document` as a new head revision (one `set` per top-level key); its id."""
    edits = tuple(Edit("set", (key,), value) for key, value in document.items())
    with application.store.reading() as connection:
        head = application.store.head(connection)
    result = application.commit_change(
        Change(edits=edits, new_revision_id=revision_id),
        head,
        f"commit-{time.monotonic_ns()}",
    )
    assert result.status == "committed", result
    assert result.revision_id is not None
    return result.revision_id


def lifecycle_violations(application: LocalApplication) -> dict[str, list[LifecycleViolation]]:
    """§6.3 over every job in the project, each from one read snapshot: `{job_id: violations}`
    for the jobs that have any."""
    found: dict[str, list[LifecycleViolation]] = {}
    for job_id in application.store.job_ids():
        snapshot = application.store.job_snapshot(job_id)
        assert snapshot is not None
        violations = check_lifecycle(*snapshot)
        if violations:
            found[job_id] = violations
    return found


def response_schema_violations(application: LocalApplication) -> list[str]:
    """R4-G3 (ruling round 4): every JobControl response about the project's jobs, and its
    summary, through `dispatch` and held to the operation's published response schema —
    `get_project`, `list_jobs`, and per job `get_job`, `list_job_events`, `wait_job` and, once it
    has ended, `get_job_result`. The problems found, as text."""
    problems: list[str] = []

    def check(name: str, request: dict[str, Any]) -> Any:
        response = dispatch(application, name, request)
        schema = OPERATIONS[name].response_schema
        assert schema is not None
        try:
            validate_inline(name, schema, response)
        except DocumentSchemaError as error:
            problems.append(f"{name} {request}: {error}")
        return response

    check("get_project", {})
    for job_id in application.store.job_ids():
        request = {"job_id": job_id}
        job = check("get_job", request)
        check("list_job_events", {**request, "limit": 500})
        check("wait_job", {**request, "timeout_s": 0})
        if job["status"] in TERMINAL_STATUSES:
            check("get_job_result", request)
    check("list_jobs", {"limit": 200})
    return problems


def _wait_for(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + PATIENCE_S
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.005)


def cancel_while_queued(
    application: LocalApplication, request: JobRequest
) -> tuple[SubmitResult, Job]:
    """Submit `request` from another thread while this one holds `COMPUTE_LOCK`, cancel the
    queued job, release the lock: `(the submitter's result, cancel_job's answer)`."""
    submitted: list[SubmitResult] = []
    failures: list[BaseException] = []

    def submit() -> None:
        try:
            submitted.append(application.submit_job(request))
        except BaseException as error:  # reported to the test thread below
            failures.append(error)

    def queued() -> Job | None:
        for job in application.list_jobs(status="queued", limit=200).items:
            if job.request.idempotency_key == request.idempotency_key:
                return job
        return None

    with COMPUTE_LOCK:
        thread = threading.Thread(target=submit)
        thread.start()
        _wait_for(lambda: queued() is not None or bool(failures), "the job to be queued")
        job = queued()
        assert job is not None, failures
        cancelled = application.cancel_job(job.job_id)
    thread.join(PATIENCE_S)
    assert not failures, failures
    return submitted[0], cancelled


@dataclass
class Pause:
    """A running job held at its `at`-th interruption check until `release` is set."""

    at: int
    job_id: str | None = None
    reached: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)

    def __call__(self, job_id: str, check: int) -> None:
        if check == self.at:
            self.job_id = job_id
            self.reached.set()
            assert self.release.wait(PATIENCE_S), "the paused job was never released"


@contextmanager
def paused_at(
    application: LocalApplication, request: JobRequest, at: int
) -> Iterator[tuple[Pause, list[SubmitResult]]]:
    """Submit `request` in another thread and hold its job at interruption check `at`. On exit
    the job is released and the submitter joined; its result is the list's one item."""
    pause = Pause(at)
    application.executor.test_hook_on_check = pause
    submitted: list[SubmitResult] = []
    thread = threading.Thread(target=lambda: submitted.append(application.submit_job(request)))
    thread.start()
    try:
        assert pause.reached.wait(PATIENCE_S), "the job never reached its pause"
        yield pause, submitted
    finally:
        pause.release.set()
        thread.join(PATIENCE_S)
        application.executor.test_hook_on_check = None
