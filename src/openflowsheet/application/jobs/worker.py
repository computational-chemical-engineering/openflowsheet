"""The body of one job's worker process (T07 design note §9.1, §9.3, §8.1–§8.2, §15 W4c).

`ProcessExecutor` starts `main` in a **fresh** `multiprocessing` `spawn` process for exactly one
job; the process has one thread that touches numpy, runs that job and exits. Nothing is shared with
the supervisor's interpreter but the project directory and three synchronization objects: the
cancel event, the cancel reason and the started event.

In order, the worker:

1. redirects its stdout and stderr, at the file-descriptor level, to `jobs/<job_id>/worker.log`
   (§9.1) — before it imports anything heavier than the standard library, so what an import
   prints is in the log too — and ignores `SIGINT`, so that a terminal's Ctrl-C reaches the
   supervisor, which governs its workers (§9.3's clean shutdown);
2. moves the job `queued → running` with its `started` event (§6.2), fenced on the owner (§9.3);
   a job that is not queued any more (cancelled meanwhile) is left as it is, and the worker exits;
3. starts the wall-time clock (§8.3) and then sets the started event, so the supervisor's own
   deadline is never earlier than the worker's;
4. runs the operation body (`runner.execute`) inside `interruptible(...)`, whose check raises
   `JobInterrupted` once the cancel event is set (with the supervisor's reason) or the deadline
   has passed — and, at every check, **exits at once if its parent changed**: the owner died,
   and recovery will end the job `failed(owner_lost)` (§9.3);
5. writes its `worker_result` (§6.2), fenced; the supervisor turns it into `ended`. A fence that
   no longer holds (the job ended under another hand) makes every later write a no-op, and the
   worker exits.

**Test hooks (§15 W4c).** Honoured only when `ProcessExecutor` was constructed with
`test_hooks=True`, a Python argument that no API, CLI flag or policy exposes:

- `OPENFLOWSHEET_TEST_PAUSE_AT_STAGE=<stage>`: at that stage's start the worker writes a line
  to its descriptor 2 (the log) and `jobs/<id>/paused` (holding its pid), and polls the cancel
  event every 10 ms; it continues when `jobs/<id>/resume` appears, and a set cancel event ends the
  pause at once, so the stage boundary's check stops the job cooperatively;
- `OPENFLOWSHEET_TEST_BLOCK=1`: once running, the worker sleeps without checkpoints, so only
  the forced stop (§8.2) can end it.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from collections.abc import Callable
from multiprocessing.sharedctypes import Synchronized
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from openflowsheet.application.jobs.interrupt import CancelReason

#: §15 W4c's two environment variables; read only by a worker started with test hooks.
PAUSE_AT_STAGE_VARIABLE: Final[str] = "OPENFLOWSHEET_TEST_PAUSE_AT_STAGE"
BLOCK_VARIABLE: Final[str] = "OPENFLOWSHEET_TEST_BLOCK"
PAUSED_FILE: Final[str] = "paused"
RESUME_FILE: Final[str] = "resume"
#: §5.4's `worker_log` file (`jobs.model.ARTIFACT_FILE_NAMES`), where stdout and stderr go.
WORKER_LOG: Final[str] = "worker.log"
#: The pause hook's poll period.
PAUSE_POLL_S: Final[float] = 0.01
#: The exit status of a worker that found its owner gone (§9.3); nothing reads it but a person.
EXIT_OWNER_GONE: Final[int] = 3
_LOG = logging.getLogger(__name__)
#: The cancel reason codes the supervisor writes before it sets the cancel event.
CANCEL_REQUESTED: Final[int] = 1
SERVER_SHUTDOWN: Final[int] = 2


def main(
    project_dir: str,
    job_id: str,
    owner_instance: str,
    cancel_event: Event,
    cancel_reason: Synchronized[int],
    started_event: Event,
    test_hooks: bool,
) -> None:
    """Run the job `job_id` of the project at `project_dir` under `owner_instance`, then exit."""
    job_directory = Path(project_dir) / "jobs" / job_id  # `store.JOBS_DIR`, not imported here
    job_directory.mkdir(parents=True, exist_ok=True)
    _redirect_output(job_directory / WORKER_LOG)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal_ = _WorkerSignal(cancel_event, cancel_reason, os.getppid())
    hooks = _TestHooks.from_environment(job_directory, signal_) if test_hooks else None
    _run(Path(project_dir), job_id, owner_instance, signal_, started_event, hooks)


def _redirect_output(path: Path) -> None:
    """Point file descriptors 1 and 2 at `path` (appending), so that native code's output is
    captured with Python's (multiprocessing flushes `sys.stdout` and `sys.stderr` at exit)."""
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.dup2(handle, 1)
        os.dup2(handle, 2)
    finally:
        os.close(handle)


class _WorkerSignal:
    """The worker's cancel token: the supervisor's cancel event, read with its reason, and the
    owner-liveness check §9.3 asks for at every cooperative checkpoint."""

    def __init__(self, event: Event, reason: Synchronized[int], parent: int) -> None:
        self.event = event
        self.reason_code = reason
        self.parent = parent

    def is_set(self) -> bool:
        self.exit_if_orphaned()
        return self.event.is_set()

    def reason(self) -> CancelReason:
        return (
            "server_shutdown" if self.reason_code.value == SERVER_SHUTDOWN else "cancel_requested"
        )

    def set(self, reason: CancelReason = "cancel_requested") -> None:
        """The runner's `cancel`: a cancellation it found recorded in the store."""
        with self.reason_code.get_lock():
            if not self.event.is_set():
                self.reason_code.value = (
                    SERVER_SHUTDOWN if reason == "server_shutdown" else CANCEL_REQUESTED
                )
        self.event.set()

    def exit_if_orphaned(self) -> None:
        if os.getppid() != self.parent:
            # The owner is dead: stop at once. Its jobs are recovery's (§9.3), and every write this
            # worker could still make is fenced out once recovery has ended the job.
            os._exit(EXIT_OWNER_GONE)


class _TestHooks:
    """§15 W4c's hooks, read from the environment the worker inherited."""

    def __init__(
        self, job_directory: Path, signal_: _WorkerSignal, pause_at: str | None, block: bool
    ) -> None:
        self.job_directory = job_directory
        self.signal = signal_
        self.pause_at = pause_at
        self.block = block

    @classmethod
    def from_environment(cls, job_directory: Path, signal_: _WorkerSignal) -> _TestHooks:
        return cls(
            job_directory,
            signal_,
            os.environ.get(PAUSE_AT_STAGE_VARIABLE) or None,
            os.environ.get(BLOCK_VARIABLE) == "1",
        )

    def block_forever(self) -> None:
        """Sleep without a checkpoint: only `Process.kill()` ends this."""
        while True:
            time.sleep(3600)

    def pause(self, stage: str) -> None:
        if stage != self.pause_at:
            return
        # Straight to descriptor 2, which is the log: a test sees the redirection itself.
        os.write(2, f"test hook: paused at stage {stage}\n".encode())
        (self.job_directory / PAUSED_FILE).write_text(str(os.getpid()), encoding="utf-8")
        resume = self.job_directory / RESUME_FILE
        while not resume.exists() and not self.signal.is_set():
            time.sleep(PAUSE_POLL_S)


def _run(
    directory: Path,
    job_id: str,
    owner_instance: str,
    signal_: _WorkerSignal,
    started_event: Event,
    hooks: _TestHooks | None,
) -> None:
    # Imported here, after the redirection: what these imports print belongs in the log.
    from openflowsheet.application.jobs.executor import _defect
    from openflowsheet.application.jobs.interrupt import interruptible
    from openflowsheet.application.jobs.runner import RunContext, WorkerResult, execute
    from openflowsheet.application.store import ProjectStore

    store = ProjectStore.open(directory)
    try:
        if not store.start_job(job_id, owner_instance=owner_instance):
            return
        job = store.get_job(job_id)
        assert job is not None
        budget = job.effective_budgets.wall_time_s
        # §8.3: the clock starts at `started`; the supervisor's starts after this one.
        deadline = time.monotonic() + budget if budget is not None else None
        started_event.set()
        on_stage: Callable[[str], None] | None = None
        if hooks is not None:
            if hooks.block:
                hooks.block_forever()
            on_stage = hooks.pause
        context = RunContext(store=store, root=directory, owner_instance=owner_instance)
        result: WorkerResult
        with interruptible(signal_, deadline, cancel_reason=signal_.reason) as check:
            try:
                result = execute(context, job, check=check, cancel=signal_.set, on_stage=on_stage)
            except Exception as error:  # a defect of the runner or the store, never of a solve
                _LOG.exception("job %s: the runner raised", job_id)
                result = _defect(error)
        store.record_worker_result(
            job_id, owner_instance=owner_instance, worker_result=result.as_document()
        )
    finally:
        store.close()
