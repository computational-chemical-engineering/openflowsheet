"""T07 W4e: the job-error mapping (design note §5.8 as amended by ruling round 4; gate R4-G6).

- **`reproduce` without its report (W4a-Q3).** In-process `reproduce` whose job ends `cancelled`
  or `timed_out` with neither a report nor an error raises `not_ready` with
  `detail = {job_id, status, reason}`, `reason` the ending's; `retryable` is true iff
  `reason == "server_shutdown"`.
- **`retryable` on a job's error (W4c-Q2)** means that a *new* job for the same request may
  succeed unchanged. The table below pins it at every site that records an error on a job:
  `operation_error` (every code) false, `verifier_refused` false, `worker_lost` with an integer
  `exitcode` false, `worker_lost` whose worker never started (`exitcode: null`) true,
  `store_error` true. Each row is produced end to end, by a real job.
"""

from __future__ import annotations

import multiprocessing.context
import os
import shutil
import signal
import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, get_args

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit, lifecycle_violations, response_schema_violations
from t07_process_support import paused_pid, set_executor, solve_request, wait_ended

import openflowsheet.application.revision_run as revision_run
from openflowsheet.application.authz import grant
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.jobs import runner
from openflowsheet.application.jobs.executor import ProcessExecutor, _defect
from openflowsheet.application.jobs.worker import PAUSE_AT_STAGE_VARIABLE
from openflowsheet.application.local import LocalApplication, _unproduced
from openflowsheet.application.types import (
    ApiError,
    ApiErrorCode,
    Job,
    JobEnding,
    Limits,
    ReplayPolicy,
    schema_errors,
)
from openflowsheet.verify.checks import VerifierError

NOMINAL = "SYN-001-nominal"
#: W3-Q1: admitted, and ending at the registered initializer's refusal (ruling round 3, Q1).
INITIALIZER_REFUSED = "SYN-001-UL-C3X"
GRACE_S = 0.5


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project", project_id="w4e")
    yield application
    try:
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []  # R4-G3
    finally:
        application.close()


def _valid_error(error: ApiError) -> ApiError:
    assert schema_errors("api-error.schema.json", error.as_document()) == []
    return error


# -- reproduce without its report (W4a-Q3, R4-G6) ----------------------------------------------


def _outside_bundle(app: LocalApplication, tmp_path: Path) -> Path:
    """A solved bundle copied outside the project, as `reproduce` takes it."""
    result = app.solve(commit(app, CORPUS[NOMINAL]()), "default")
    (bundle,) = [output for output in result.outputs if output.kind == "replay_bundle"]
    row = app.store.artifact(bundle.artifact_id)
    assert row is not None
    outside = tmp_path / "outside"
    shutil.copytree(app.files_root / row.relpath, outside)
    return outside


def test_a_timed_out_reproduce_raises_not_ready_not_retryable(
    app: LocalApplication, tmp_path: Path
) -> None:
    outside = _outside_bundle(app, tmp_path)
    directory = app.store.directory
    assert directory is not None
    # A capability whose default wall time has passed before the job's first check.
    capability, _ = grant(
        directory,
        principal_id="agent",
        rights=("execute", "read"),
        limits=Limits(default_wall_time_s=1e-9),
    )
    with LocalApplication.open(directory, capability=capability) as agent:
        with pytest.raises(ApplicationError) as raised:
            agent.reproduce(outside, ReplayPolicy())
        (job,) = [job for job in agent.list_jobs().items if job.operation == "reproduce"]
        assert lifecycle_violations(agent) == {}
    error = _valid_error(raised.value.error)
    assert (error.code, error.retryable) == ("not_ready", False)
    assert error.detail == {
        "job_id": job.job_id,
        "status": "timed_out",
        "reason": "wall_time_exhausted",
    }
    assert job.ending is not None and job.ending.reason == "wall_time_exhausted"
    assert job.effective_budgets.wall_time_s == 1e-9


def test_a_cancelled_reproduce_raises_not_ready_not_retryable(
    app: LocalApplication, tmp_path: Path
) -> None:
    outside = _outside_bundle(app, tmp_path)

    def cancel_at_first_check(job_id: str, check: int) -> None:
        if check == 1:
            app.cancel_job(job_id)

    app.executor.test_hook_on_check = cancel_at_first_check
    try:
        with pytest.raises(ApplicationError) as raised:
            app.reproduce(outside, ReplayPolicy())
    finally:
        app.executor.test_hook_on_check = None
    error = _valid_error(raised.value.error)
    assert (error.code, error.retryable) == ("not_ready", False)
    assert (error.detail["status"], error.detail["reason"]) == ("cancelled", "cancel_requested")
    assert app.get_job(error.detail["job_id"]).operation == "reproduce"


@pytest.mark.parametrize(
    ("status", "reason", "retryable"),
    [
        ("timed_out", "wall_time_exhausted", False),
        ("cancelled", "cancel_requested", False),
        ("cancelled", "keyboard_interrupt", False),
        ("cancelled", "server_shutdown", True),
    ],
)
def test_the_not_ready_mapping_is_retryable_only_after_a_server_shutdown(
    status: str, reason: str, retryable: bool
) -> None:
    """R4-G6's unit of the mapping: an end-to-end `server_shutdown` of an in-process
    `reproduce` is impractical, since its caller is the one waiting."""
    ended = replace(
        _a_job(),
        status=status,  # type: ignore[arg-type]
        ending=JobEnding(status=status, reason=reason),  # type: ignore[arg-type]
    )
    error = _valid_error(_unproduced(ended))
    assert (error.code, error.retryable) == ("not_ready", retryable)
    assert error.detail == {"job_id": ended.job_id, "status": status, "reason": reason}


def _a_job() -> Job:
    """A real ended job, whose status and ending the mapping's unit test replaces."""
    with LocalApplication.in_memory() as application:
        result = application.solve(commit(application, CORPUS[NOMINAL]()), "default")
        return application.get_job(result.job_id)


# -- `retryable` on a job's error: the table (W4c-Q2, R4-G6) -----------------------------------


def _raise(error: Exception) -> Callable[..., Any]:
    def raising(*_: Any, **__: Any) -> Any:
        raise error

    return raising


#: (row, the patch, the revision) → (ending reason, error code, retryable).
INLINE_TABLE: list[tuple[str, tuple[str, Exception | None], str, tuple[str, str, bool]]] = [
    (
        "operation_error: unsupported, unmapped record",
        ("initializer_source", None),
        INITIALIZER_REFUSED,
        ("operation_error", "unsupported", False),
    ),
    (
        "operation_error: internal_error, untyped exception",
        ("execute_plan", ValueError("defect")),
        NOMINAL,
        ("operation_error", "internal_error", False),
    ),
    (
        "verifier_refused",
        ("verify_revision", VerifierError("the verifier's own flash failed")),
        NOMINAL,
        ("verifier_refused", "unsupported", False),
    ),
    (
        "store_error",
        ("execute_plan", sqlite3.OperationalError("database is locked")),
        NOMINAL,
        ("store_error", "internal_error", True),
    ),
]


@pytest.mark.parametrize(
    ("row", "patch", "name", "expected"), INLINE_TABLE, ids=[row[0] for row in INLINE_TABLE]
)
def test_retryable_table_inline(
    app: LocalApplication,
    monkeypatch: pytest.MonkeyPatch,
    row: str,
    patch: tuple[str, Exception | None],
    name: str,
    expected: tuple[str, str, bool],
) -> None:
    attribute, error = patch
    monkeypatch.setattr(
        revision_run, attribute, (lambda _: None) if error is None else _raise(error)
    )
    result = app.solve(commit(app, CORPUS[name]()), "default")
    job = app.get_job(result.job_id)
    assert job.ending is not None and job.error is not None, row
    assert result.error == job.error
    _valid_error(job.error)
    assert (job.ending.reason, job.error.code, job.error.retryable) == expected, row


def test_retryable_table_operation_error_is_false_for_every_code() -> None:
    """The runner's one constructor of a body's error, and the executor's for a body's escaped
    exception: every `operation_error` code is false; only a store error is true."""
    for code in get_args(ApiErrorCode):
        assert runner._error(code, "m").retryable is False, code
    assert _defect(ValueError("x")).as_document()["error"]["retryable"] is False
    assert _defect(ValueError("x")).reason == "operation_error"
    stored = _defect(sqlite3.OperationalError("database is locked"))
    assert (stored.reason, stored.as_document()["error"]["retryable"]) == ("store_error", True)


def _process_app(directory: Path) -> LocalApplication:
    LocalApplication.create(directory).close()
    set_executor(directory, max_workers=1, grace_s=GRACE_S)
    return LocalApplication.open(directory, executor=ProcessExecutor(test_hooks=True))


def test_retryable_table_a_worker_that_never_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _process_app(tmp_path / "p")
    try:
        revision_id = commit(app, CORPUS[NOMINAL]())
        monkeypatch.setattr(
            multiprocessing.context.SpawnProcess, "start", _raise(OSError("no fork"))
        )
        job = wait_ended(app, app.submit_job(solve_request("unstarted", revision_id)).job.job_id)
        monkeypatch.undo()
        assert job.ending is not None and job.error is not None
        assert (job.status, job.ending.reason) == ("failed", "worker_lost")
        assert job.error.detail == {"exitcode": None}
        assert (_valid_error(job.error).code, job.error.retryable) == ("internal_error", True)
        assert lifecycle_violations(app) == {}
    finally:
        app.close()


def test_retryable_table_a_worker_that_exited_with_a_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, "plan")
    app = _process_app(tmp_path / "p")
    try:
        revision_id = commit(app, CORPUS[NOMINAL]())
        job = app.submit_job(solve_request("killed", revision_id)).job
        os.kill(paused_pid(app, job.job_id), signal.SIGKILL)
        job = wait_ended(app, job.job_id)
        assert job.ending is not None and job.error is not None
        assert (job.status, job.ending.reason) == ("failed", "worker_lost")
        assert job.error.detail["exitcode"] == -signal.SIGKILL
        assert (_valid_error(job.error).code, job.error.retryable) == ("internal_error", False)
        assert lifecycle_violations(app) == {}
    finally:
        app.close()
