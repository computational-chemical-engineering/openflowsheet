"""T07 W4c: the process executor (design note §9.1–§9.5, §8.2, §15 W4c; gates G5, G6, G7).

Each job runs in a freshly spawned worker under the supervisor thread of the `LocalApplication`
that accepted it. What is held here:

- **Execution:** a job completes in a worker whose `openflowsheet` is the parent's, and every
  job this module produces passes §6.3 (G3).
- **Cancellation (G5):** a running job cancelled at the pause hook ends `cancelled`, cooperative,
  within 2 s of `cancel_job`; a worker blocked without checkpoints ends `cancelled`, forced, within
  `grace_s + 1` s (`grace_s = 0.5`); a blocked worker past its wall time ends `timed_out`,
  forced. Never a certificate, a failure bundle or a solver outcome from an interruption.
- **Lost processes (§8.2, §9.3):** a `kill -9`ed worker ends its job `failed(worker_lost)` with
  `detail.exitcode`; a `kill -9`ed server's running job ends `failed(owner_lost)` at the next
  open, and its orphaned worker exits on its own.
- **Clean shutdown (§9.3):** `close` ends the queued job and stops the running one, both
  `cancelled(server_shutdown)`.
- **Equivalence (G6, G7, §9.5 (2)):** for 5 corpus revisions a process job's bundle is the inline
  job's, byte for byte, apart from the volatile manifest members, with R0 equal; 8 revisions run
  four at a time give the bytes they give one at a time; job B alone in a fresh worker gives the
  bytes of job B run inline right after job A, for 3 pairs.

The timing bounds are G5's, registered in §16; nothing here is tighter.
"""

from __future__ import annotations

import multiprocessing
import os
import signal
import sqlite3
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import PATIENCE_S, commit, lifecycle_violations, response_schema_violations
from t07_process_support import (
    bundle_bytes,
    gone,
    paused_pid,
    serve_paused_job_then_hang,
    set_executor,
    solve_request,
    wait_ended,
    wait_until,
)

import openflowsheet
from openflowsheet.application.jobs.executor import (
    SHUTDOWN_STORE_ATTEMPTS,
    SUPERVISOR_POLL_S,
    ProcessExecutor,
)
from openflowsheet.application.jobs.worker import (
    BLOCK_VARIABLE,
    PAUSE_AT_STAGE_VARIABLE,
    RESUME_FILE,
)
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.store import ProjectStore
from openflowsheet.application.types import Budgets, Job

SPAWN = multiprocessing.get_context("spawn")
NOMINAL = "SYN-001-nominal"
#: G6: revision_eo with a certificate, legacy_eo with a certificate, legacy_eo with a failure
#: bundle (HOMOTOPY_STALLED), revision_eo on a T06 network, and a T05b builder.
G6_REVISIONS = (
    NOMINAL,
    "SYN-001-A02-360",
    "SYN-001-A02-352-vapor-guess-410",
    "SYN-001-T06-NET03",
    "T05b:SC-3",
)
#: G7: G6's five and three more.
G7_REVISIONS = (*G6_REVISIONS, "SYN-001-T06-NET10", "SYN-001-T06-STA02", "SYN-001-UL-C1")
#: §9.5 (2): (A, B) — B alone in a fresh worker vs B inline right after A.
A_THEN_B = (
    (NOMINAL, "SYN-001-T06-NET03"),
    ("SYN-001-A02-352-vapor-guess-410", NOMINAL),
    ("SYN-001-T06-NET10", "SYN-001-A02-360"),
)
#: G5.
COOPERATIVE_BOUND_S = 2.0
GRACE_S = 0.5
FORCED_BOUND_S = GRACE_S + 1.0
INTERRUPTION_KINDS = ([], ["partial_solve_trace"])


def _open(
    directory: Path, *, max_workers: int = 1, grace_s: float = 10, test_hooks: bool = True
) -> LocalApplication:
    """A new project with the given executor settings, opened under the process executor."""
    LocalApplication.create(directory).close()
    set_executor(directory, max_workers=max_workers, grace_s=grace_s)
    return LocalApplication.open(directory, executor=ProcessExecutor(test_hooks=test_hooks))


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = _open(tmp_path / "project", grace_s=GRACE_S)
    yield application
    try:
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []  # R4-G3
    finally:
        application.close()


def _submit(app: LocalApplication, name: str, key: str, **body: object) -> Job:
    revision_id = commit(app, CORPUS[name]())
    return app.submit_job(solve_request(key, revision_id, **body)).job


def _kinds(job: Job) -> list[str]:
    return [output.kind for output in job.outputs]


# -- execution ------------------------------------------------------------------------------------


def test_workers_import_the_parents_openflowsheet(tmp_path: Path) -> None:
    """A spawned worker runs the code under test, not another installed copy (G6's premise)."""
    queue = SPAWN.Queue()
    child = SPAWN.Process(target=_report_package, args=(queue,))
    child.start()
    assert queue.get(timeout=PATIENCE_S) == openflowsheet.__file__
    child.join(PATIENCE_S)


def _report_package(queue: multiprocessing.Queue[str]) -> None:
    import openflowsheet as package

    queue.put(package.__file__)


def test_a_job_runs_in_a_worker_and_the_owner_ends_it(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    submitted = app.submit_job(solve_request("one", revision_id))
    assert submitted.job.status in ("queued", "running")  # submit_job does not wait
    job = wait_ended(app, submitted.job.job_id)
    assert (job.status, _kinds(job)) == (
        "completed",
        ["solution_certificate", "run_manifest", "replay_bundle"],
    )
    result = app.get_job_result(job.job_id).run_result
    assert result is not None
    assert (result.outcome, result.verification_status) == ("CONVERGED", "VERIFIED")
    # The frozen `solve` is the same composition over the process executor.
    assert app.solve(revision_id, "default").verification_status == "VERIFIED"
    assert app.executor.pid(job.job_id) is None  # type: ignore[union-attr]


def test_a_process_executor_binds_to_one_owner(tmp_path: Path) -> None:
    LocalApplication.create(tmp_path / "p").close()
    executor = ProcessExecutor()
    with LocalApplication.open(tmp_path / "p", executor=executor) as first:
        assert first.executor is executor
        with pytest.raises(RuntimeError, match="already bound"):
            LocalApplication.open(tmp_path / "p", executor=executor)


# -- cancellation (G5) --------------------------------------------------------------------------


def test_cancel_at_the_pause_hook_is_cooperative(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, "solve")
    job = _submit(app, NOMINAL, "paused")
    paused_pid(app, job.job_id)
    assert app.get_job(job.job_id).status == "running"
    app.cancel_job(job.job_id)
    cancelled = time.monotonic()
    job = wait_ended(app, job.job_id)
    elapsed = time.monotonic() - cancelled
    assert elapsed <= COOPERATIVE_BOUND_S, elapsed
    assert job.status == "cancelled" and job.error is None
    assert job.ending is not None
    assert (job.ending.reason, job.ending.interruption) == ("cancel_requested", "cooperative")
    # The hook wrote to the worker's stderr at the descriptor level: the log is the last output.
    kinds = _kinds(job)
    assert kinds[-1] == "worker_log" and kinds[:-1] in INTERRUPTION_KINDS, kinds
    log = app.files_root / "jobs" / job.job_id / "worker.log"
    assert b"test hook: paused at stage solve" in log.read_bytes()
    assert not (app.files_root / "jobs" / job.job_id / "bundle").exists()
    result = app.get_job_result(job.job_id).run_result
    assert result is not None
    assert (result.outcome, result.verification_status) == (None, None)


def test_the_pause_hook_resumes(app: LocalApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, "verify")
    job = _submit(app, NOMINAL, "resumed")
    paused_pid(app, job.job_id)
    (app.files_root / "jobs" / job.job_id / RESUME_FILE).touch()
    job = wait_ended(app, job.job_id)
    assert job.status == "completed"
    assert _kinds(job) == ["solution_certificate", "run_manifest", "replay_bundle", "worker_log"]


def test_a_blocked_worker_is_killed_after_the_grace_period(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(BLOCK_VARIABLE, "1")
    job = _submit(app, NOMINAL, "blocked")
    wait_until(lambda: app.get_job(job.job_id).status == "running", "the worker to start")
    pid = app.executor.pid(job.job_id)  # type: ignore[union-attr]
    assert pid is not None
    app.cancel_job(job.job_id)
    cancelled = time.monotonic()
    job = wait_ended(app, job.job_id)
    elapsed = time.monotonic() - cancelled
    # Not before the grace period (the kill is timed from inside `cancel_job`, hence the slack).
    assert GRACE_S - 0.05 <= elapsed <= FORCED_BOUND_S, elapsed
    assert job.status == "cancelled" and job.error is None
    assert job.ending is not None
    assert (job.ending.reason, job.ending.interruption) == ("cancel_requested", "forced")
    assert _kinds(job) == []
    assert gone(pid)
    assert app.store.worker_result(job.job_id) is None


def test_a_blocked_worker_past_its_wall_time_is_timed_out_forced(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(BLOCK_VARIABLE, "1")
    job = _submit(app, NOMINAL, "late", budgets=Budgets(wall_time_s=1.0))
    job = wait_ended(app, job.job_id)
    assert job.status == "timed_out" and job.error is None
    assert job.ending is not None
    assert (job.ending.reason, job.ending.interruption) == ("wall_time_exhausted", "forced")
    assert _kinds(job) == []


# -- lost processes (§8.2, §9.3) ----------------------------------------------------------------


def test_a_killed_worker_ends_its_job_worker_lost(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, "plan")
    job = _submit(app, NOMINAL, "killed")
    os.kill(paused_pid(app, job.job_id), signal.SIGKILL)
    job = wait_ended(app, job.job_id)
    assert job.status == "failed"
    assert job.ending is not None
    assert (job.ending.reason, job.ending.interruption) == ("worker_lost", None)
    assert job.error is not None and job.error.code == "internal_error"
    assert job.error.detail["exitcode"] == -signal.SIGKILL
    assert job.error.detail["log_artifact_id"] == f"{job.job_id}:worker.log"
    assert _kinds(job) == ["worker_log"]
    assert app.get_job_result(job.job_id).error == job.error


# -- a store error in the supervisor (T07 review S1) --------------------------------------------


def _fails_once(monkeypatch: pytest.MonkeyPatch, target: object, name: str) -> list[int]:
    """Make `target.name` raise a store error on its first call from the supervisor thread."""
    real = getattr(target, name)
    calls: list[int] = []

    def flaky(*args: object, **kwargs: object) -> object:
        if threading.current_thread().name.startswith("process-executor") and not calls:
            calls.append(1)
            raise sqlite3.OperationalError("database is locked")
        return real(*args, **kwargs)

    monkeypatch.setattr(target, name, flaky)
    return calls


def test_a_store_error_ending_a_job_is_retried_not_dropped(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One failed `finish_job` used to pop the slot anyway: the VERIFIED job stayed `running`,
    and a restart read it `failed(owner_lost)`."""
    calls = _fails_once(monkeypatch, app.store, "finish_job")
    job = wait_ended(app, _submit(app, NOMINAL, "finish-once").job_id)
    assert calls == [1]
    assert job.status == "completed"
    assert _kinds(job) == ["solution_certificate", "run_manifest", "replay_bundle"]
    result = app.get_job_result(job.job_id).run_result
    assert result is not None and result.verification_status == "VERIFIED"


def test_a_retried_ending_appends_the_worker_log_once(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retry repeats `_worker_log`, whose registration and output event are idempotent."""
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, "plan")
    calls = _fails_once(monkeypatch, app.store, "finish_job")
    job = _submit(app, NOMINAL, "killed-finish-once")
    os.kill(paused_pid(app, job.job_id), signal.SIGKILL)
    job = wait_ended(app, job.job_id)
    assert calls == [1]
    assert job.status == "failed" and job.ending is not None
    assert job.ending.reason == "worker_lost"
    assert _kinds(job) == ["worker_log"]
    assert job.error is not None
    assert job.error.detail["log_artifact_id"] == f"{job.job_id}:worker.log"


def test_a_store_error_launching_a_job_requeues_it(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One failed read in `_launch` used to drop the admitted id: the job stayed `queued`."""
    calls = _fails_once(monkeypatch, app.store, "get_job")
    job = wait_ended(app, _submit(app, NOMINAL, "launch-once").job_id)
    assert calls == [1]
    assert job.status == "completed"


def test_a_killed_server_leaves_owner_lost_and_its_worker_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "p"
    with LocalApplication.create(directory) as setup:
        revision_id = commit(setup, CORPUS[NOMINAL]())
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, "solve")
    ready = SPAWN.Queue()
    server = SPAWN.Process(
        target=serve_paused_job_then_hang, args=(str(directory), revision_id, ready)
    )
    server.start()
    job_id, worker_pid = ready.get(timeout=PATIENCE_S)
    assert server.pid is not None
    os.kill(server.pid, signal.SIGKILL)
    server.join(PATIENCE_S)
    # §9.3: the orphaned worker sees its parent change at its next checkpoint and exits.
    wait_until(lambda: gone(worker_pid), "the orphaned worker to exit")

    with LocalApplication.open(directory, executor="process") as reopened:
        assert reopened.recovered == (job_id,)
        job = reopened.get_job(job_id)
        assert job.status == "failed"
        assert job.ending is not None and job.ending.reason == "owner_lost"
        assert [event.kind for event in reopened.store.job_events(job_id)][-1] == "ended"
        # §7 Restarts: the key still names that job, ended as it is (a re-run takes a new key).
        again = reopened.submit_job(solve_request("server-key", revision_id))
        assert (again.replayed, again.job.job_id, again.job.status) == (True, job_id, "failed")
        assert lifecycle_violations(reopened) == {}


def test_close_ends_queued_and_running_jobs_server_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, "solve")
    app = _open(tmp_path / "p", grace_s=GRACE_S)
    running = _submit(app, NOMINAL, "first")
    queued = _submit(app, NOMINAL, "second")
    paused_pid(app, running.job_id)
    assert app.get_job(queued.job_id).status == "queued"  # max_workers = 1
    app.close()
    with LocalApplication.open(tmp_path / "p") as reopened:
        assert reopened.recovered == ()
        first, second = reopened.get_job(running.job_id), reopened.get_job(queued.job_id)
        assert first.ending is not None and second.ending is not None
        assert (first.status, first.ending.reason, first.ending.interruption) == (
            "cancelled",
            "server_shutdown",
            "cooperative",
        )
        assert (second.status, second.ending.reason, second.started_at, second.outputs) == (
            "cancelled",
            "server_shutdown",
            None,
            (),
        )
        assert lifecycle_violations(reopened) == {}


def test_shutdown_gives_up_on_a_failing_store_and_the_next_open_ends_owner_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rf1-Q1: after S1, a store that kept failing made `close` retry forever. It tries
    `SHUTDOWN_STORE_ATTEMPTS` times with backoff, in `shutdown` and in the supervisor, and
    returns; the jobs stay as recorded, and the next open ends them `failed(owner_lost)`."""
    monkeypatch.setenv(PAUSE_AT_STAGE_VARIABLE, "solve")
    directory = tmp_path / "p"
    app = _open(directory, grace_s=GRACE_S)
    running = _submit(app, NOMINAL, "first")
    queued = _submit(app, NOMINAL, "second")
    paused_pid(app, running.job_id)
    assert app.get_job(queued.job_id).status == "queued"  # max_workers = 1
    calls: list[str] = []

    def broken(job_id: str, **_: object) -> None:
        calls.append(job_id)
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(app.store, "finish_job", broken)
    raised: list[BaseException] = []

    def close() -> None:
        try:
            app.close()
        except BaseException as error:  # noqa: BLE001 — reported by the assertion below
            raised.append(error)

    closing = threading.Thread(target=close, daemon=True)
    started = time.monotonic()
    closing.start()
    waits = SUPERVISOR_POLL_S * (2 ** (SHUTDOWN_STORE_ATTEMPTS - 1) - 1)  # doubling backoff
    closing.join(2 * waits + GRACE_S + PATIENCE_S)
    assert not closing.is_alive(), "close never returned"
    assert raised == [], "close raised the store's error"
    assert time.monotonic() - started >= waits  # it did retry, with backoff
    assert sorted(calls) == sorted(
        [queued.job_id] * SHUTDOWN_STORE_ATTEMPTS + [running.job_id] * SHUTDOWN_STORE_ATTEMPTS
    )
    store = ProjectStore.open(directory)
    try:
        left = [store.get_job(job.job_id) for job in (running, queued)]
        assert [job.status if job is not None else None for job in left] == ["running", "queued"]
    finally:
        store.close()
    with LocalApplication.open(directory) as reopened:
        assert set(reopened.recovered) == {running.job_id, queued.job_id}
        for job_id in (running.job_id, queued.job_id):
            job = reopened.get_job(job_id)
            assert job.ending is not None
            assert (job.status, job.ending.reason) == ("failed", "owner_lost")
        assert lifecycle_violations(reopened) == {}


# -- equivalence (G6, G7, §9.5 (2)) -------------------------------------------------------------


def _bundles(app: LocalApplication, names: tuple[str, ...], prefix: str) -> list[Job]:
    """Submit one solve per revision (committed in order), then wait for them all."""
    revisions = [commit(app, CORPUS[name]()) for name in names]
    jobs = [
        app.submit_job(solve_request(f"{prefix}-{index}", revision_id)).job
        for index, revision_id in enumerate(revisions)
    ]
    return [wait_ended(app, job.job_id) for job in jobs]


def _assert_same_bundles(
    ours: list[Job], ours_app: LocalApplication, theirs: list[Job], theirs_app: LocalApplication
) -> None:
    for mine, other in zip(ours, theirs, strict=True):
        assert mine.status == other.status == "completed"
        assert _kinds(mine)[:3] == _kinds(other)[:3]
        files, manifest, r0 = bundle_bytes(ours_app, mine)
        other_files, other_manifest, other_r0 = bundle_bytes(theirs_app, other)
        assert files.keys() == other_files.keys() and files
        for name in files:
            assert files[name] == other_files[name], (mine.job_id, name)
        assert manifest == other_manifest, mine.job_id
        assert r0 == other_r0 == manifest["artifact_r0_sha256"]


def test_g6_process_bundles_are_the_inline_bundles(tmp_path: Path) -> None:
    with LocalApplication.create(tmp_path / "inline") as inline:
        inline_jobs = _bundles(inline, G6_REVISIONS, "g6")
        with _open(tmp_path / "process") as process:
            process_jobs = _bundles(process, G6_REVISIONS, "g6")
            _assert_same_bundles(process_jobs, process, inline_jobs, inline)
            assert lifecycle_violations(process) == {}


def test_g7_four_workers_give_the_serial_bytes(tmp_path: Path) -> None:
    with _open(tmp_path / "serial", max_workers=1) as serial:
        serial_jobs = _bundles(serial, G7_REVISIONS, "g7")
        with _open(tmp_path / "parallel", max_workers=4) as parallel:
            parallel_jobs = _bundles(parallel, G7_REVISIONS, "g7")
            _assert_same_bundles(parallel_jobs, parallel, serial_jobs, serial)
            assert lifecycle_violations(parallel) == {}
            # Four at once, not one after another: some jobs' runs overlapped.
            spans = sorted((job.started_at, job.ended_at) for job in parallel_jobs)
            assert any(
                later[0] < earlier[1] for earlier, later in zip(spans, spans[1:], strict=False)
            )


@pytest.mark.parametrize(("first", "second"), A_THEN_B)
def test_job_b_alone_in_a_worker_is_job_b_after_job_a_inline(
    tmp_path: Path, first: str, second: str
) -> None:
    with LocalApplication.create(tmp_path / "inline") as inline:
        _, after_a = _bundles(inline, (first, second), "ab")
        with _open(tmp_path / "process") as process:
            # The revision ordinals of the inline project, so `revision.json` agrees (the run id,
            # `run-<job_id>`, differs and is volatile).
            commit(process, CORPUS[first]())
            (alone,) = _bundles(process, (second,), "ab-b")
            _assert_same_bundles([alone], process, [after_a], inline)
