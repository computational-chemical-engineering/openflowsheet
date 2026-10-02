"""Helpers for the T07 process-executor tests (design note §9.1–§9.3, §8.2, §15 W4c–W4d).

Not collected. The spawned-process bodies live here, in an importable module, because the `spawn`
start method imports them by module name in a fresh interpreter (as `t07_store_support`'s do).
`set_executor` writes the project policy's `executor` settings the way an operator edits the file;
`bundle_bytes` reads a job's bundle as §9.5 (2) compares it; `wait_ended` watches the store at a
finer grain than `wait_job`'s 0.1 s poll, so a measured stop time is the executor's, not the
waiter's.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import replace
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import Any

from t07_jobs_support import PATIENCE_S

from openflowsheet.application.authz import read_policy
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.jobs.executor import ProcessExecutor
from openflowsheet.application.jobs.model import TERMINAL_STATUSES
from openflowsheet.application.jobs.worker import PAUSED_FILE
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.store import POLICY_NAME, atomic_write_bytes, policy_file_bytes
from openflowsheet.application.types import ExecutorSettings, Job, JobRequest, SolveBody
from openflowsheet.run.identity import r0_projection, r0_sha256

#: §9.5 (2): the manifest members that differ between two runs of one solve, and the hash over
#: them.
VOLATILE_MANIFEST = (
    "started_at",
    "elapsed_seconds",
    "hostname",
    "environment",
    "run_id",
    "manifest_sha256",
)


def set_executor(directory: Path, *, max_workers: int = 1, grace_s: float = 10) -> None:
    """The project policy's `executor` settings (§5.9), as an operator's edit of the file."""
    path = Path(directory) / POLICY_NAME
    policy = read_policy(path)
    settings = ExecutorSettings(max_workers=max_workers, grace_s=grace_s)
    atomic_write_bytes(path, policy_file_bytes(replace(policy, executor=settings)))


def solve_request(key: str, revision_id: str, **body: Any) -> JobRequest:
    budgets = body.pop("budgets", None)
    request = JobRequest("solve", key, SolveBody(revision_id=revision_id, **body))
    return request if budgets is None else replace(request, budgets=budgets)


def wait_until(condition: Any, what: str, patience_s: float = PATIENCE_S) -> float:
    """Poll `condition` every 5 ms; the monotonic time it first held."""
    deadline = time.monotonic() + patience_s
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.005)
    return time.monotonic()


def wait_ended(app: LocalApplication, job_id: str, patience_s: float = PATIENCE_S) -> Job:
    wait_until(
        lambda: app.store.get_job(job_id).status in TERMINAL_STATUSES,  # type: ignore[union-attr]
        f"job {job_id} to end",
        patience_s,
    )
    job = app.store.get_job(job_id)
    assert job is not None
    return job


def paused_pid(app: LocalApplication, job_id: str) -> int:
    """Wait for the pause hook to engage; the paused worker's pid (it writes it)."""
    path = app.files_root / "jobs" / job_id / PAUSED_FILE
    wait_until(lambda: path.is_file() and path.read_text("utf-8") != "", "the pause hook")
    return int(path.read_text("utf-8"))


def gone(pid: int) -> bool:
    """Whether process `pid` has exited (reaped, or a zombie its new parent has yet to reap)."""
    try:
        status = Path(f"/proc/{pid}/status").read_text("utf-8")
    except (FileNotFoundError, ProcessLookupError):  # the process can exit mid-read
        return True
    return any(
        line.split()[1:2] == ["Z"] for line in status.splitlines() if line.startswith("State:")
    )


def bundle_bytes(app: LocalApplication, job: Job) -> tuple[dict[str, bytes], dict[str, Any], str]:
    """A job's bundle as §9.5 (2) compares it: every file under `artifacts/` by relative path,
    the manifest without its volatile members, and R0 recomputed from the files."""
    (bundle,) = [output for output in job.outputs if output.kind == "replay_bundle"]
    row = app.store.artifact(bundle.artifact_id)
    assert row is not None
    directory = app.files_root / row.relpath
    files = {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted((directory / "artifacts").rglob("*"))
        if path.is_file()
    }
    manifest = json.loads((directory / "run-manifest.json").read_bytes())
    stable = {key: value for key, value in manifest.items() if key not in VOLATILE_MANIFEST}
    artifacts = {
        name.removeprefix("artifacts/"): json.loads(data)
        for name, data in files.items()
        if name.endswith(".json")
    }
    return files, stable, r0_sha256(r0_projection(artifacts))


# -- spawned bodies ------------------------------------------------------------------------------


def serve_paused_job_then_hang(directory: str, revision_id: str, ready: Queue[Any]) -> None:
    """A server: open with the process executor (test hooks on; the pause variable is inherited),
    submit one solve, report its job id and its paused worker's pid, and wait to be killed."""
    application = LocalApplication.open(directory, executor=ProcessExecutor(test_hooks=True))
    job = application.submit_job(solve_request("server-key", revision_id)).job
    ready.put((job.job_id, paused_pid(application, job.job_id)))
    time.sleep(600)


def contend_process_submit(
    directory: str,
    revision_id: str,
    key: str,
    threads: int,
    ready: Queue[Any],
    start: Event,
    results: Queue[Any],
) -> None:
    """A server under the process executor: `threads` threads submit one request (a solve of
    `revision_id`) under one key, released together with the peer. Each outcome is
    `("job", job_id, replayed)` or `("refused", code, detail.original_request_sha256)`. The server
    waits for the job to end before it closes, so an owner never shuts its own job down."""
    application = LocalApplication.open(directory, executor="process")
    barrier = threading.Barrier(threads + 1)
    outcomes: list[tuple[str, str, Any]] = []
    lock = threading.Lock()

    def one() -> None:
        barrier.wait()
        start.wait()
        try:
            submitted = application.submit_job(solve_request(key, revision_id))
            outcome = ("job", submitted.job.job_id, submitted.replayed)
        except ApplicationError as error:
            outcome = ("refused", error.code, error.error.detail.get("original_request_sha256"))
        with lock:
            outcomes.append(outcome)

    workers = [threading.Thread(target=one) for _ in range(threads)]
    for worker in workers:
        worker.start()
    barrier.wait()
    ready.put(os.getpid())
    for worker in workers:
        worker.join()
    for job_id in {outcome[1] for outcome in outcomes if outcome[0] == "job"}:
        wait_ended(application, job_id)
    application.close()
    results.put(outcomes)
