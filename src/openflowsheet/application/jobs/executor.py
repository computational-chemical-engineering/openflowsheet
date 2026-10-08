"""Job executors (T07 design note §9.1): the inline executor behind the process-wide compute lock,
and the process executor that runs each job in a freshly spawned worker.

**`InlineExecutor`** runs a job in the calling thread while holding `COMPUTE_LOCK`, a module-level
`threading.Lock`, so at most one job computes per interpreter through the contract, whichever
`LocalApplication` accepted it (R-088 Q27: no two verifications run concurrently in one
interpreter, so no thread can observe the seeded global generator of `inverse_one_norm_estimate`).
The lock is not the Q27 fix — the process boundary is (§9.4): a *caller's own* thread drawing from
`np.random` while a contract verification runs is not excluded here, and `executor="process"`
(W4c) is its remedy.

The executor is the job's **owner** (§6.2): it moves the job `queued → running`, runs the
operation body (`runner.execute`) inside `interrupt.interruptible(...)`, and writes the one `ended`
event with the body's `WorkerResult`. It has no forced stop (§8.2): a cancellation is cooperative,
at the next `Trace.record` or stage boundary. A `KeyboardInterrupt` in the calling thread ends the
job `cancelled(keyboard_interrupt)` and is re-raised.

**`ProcessExecutor`** (§9.1–§9.3, §8.2) is what a server uses: a supervisor thread holds a FIFO
of the jobs its owner accepted and runs each in a **fresh** `multiprocessing` `spawn` process
(`jobs.worker.main`), at most `executor.max_workers` at once. The worker writes `started`, the
job's `progress` and `output` events and its `worker_result`, all fenced on the owner (§9.3); the
supervisor, the owner, writes the one `ended` event after it has joined the worker, appending the
worker's non-empty `worker.log` as the last output first (§5.4, §6.2). It polls its workers every
0.1 s and acts once cancellation has been requested (by this instance, or recorded in the store by
another), the wall-time deadline has passed, or a shutdown has begun (§8.2): it signals the cancel
event, waits `executor.grace_s`, then kills the worker, and the job ends `cancelled` or
`timed_out` with `interruption = "forced"` — unless the worker wrote its own result first. The kill
reaches the worker's **process group** (`_kill_tree`; ADR 0033 D2 widens ADR 0020 D3's "kill"): the
worker makes itself a group leader as its first statement, so a child it runs (an external model's
attempt, M02) dies with it rather than outliving it. A
worker that exits with no `worker_result` ends the job `failed(worker_lost)` with
`detail.exitcode`. The Q27 hazard is excluded here by construction, not locked around (§9.4): two
verifications never share an interpreter.

**`retryable` on a job's error (§5.8 as amended by ruling round 4, W4c-Q2)** means that a *new*
job for the same request may succeed unchanged. It is true only for the transient ends: a worker
that never started (`worker_lost`, `exitcode: null`) and `store_error`. A worker that exited with
a code (`worker_lost`, integer `exitcode`: an OOM kill, a segfault, a `kill -9`) is not known to be
transient and is false, as is an untyped exception of the body (`operation_error`).
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import sqlite3
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.process import BaseProcess
from multiprocessing.sharedctypes import Synchronized
from multiprocessing.synchronize import Event
from typing import Final, Literal

from openflowsheet.application.jobs import worker
from openflowsheet.application.jobs.interrupt import (
    CancelReason,
    CancelSignal,
    InterruptReason,
    JobInterrupted,
    interruptible,
)
from openflowsheet.application.jobs.model import TERMINAL_STATUSES
from openflowsheet.application.jobs.runner import RunContext, WorkerResult, execute
from openflowsheet.application.store import JOBS_DIR, ArtifactRow
from openflowsheet.application.types import ApiError, ExecutorSettings, Job, JobEnding
from openflowsheet.canonical import file_sha256

__all__ = [
    "COMPUTE_LOCK",
    "CancelSignal",
    "CancelToken",
    "InlineExecutor",
    "InterruptReason",
    "JobInterrupted",
    "ProcessExecutor",
    "interruptible",
]

_LOG = logging.getLogger(__name__)

#: §9.1: at most one job computes per process through the contract (R-088 Q27).
COMPUTE_LOCK: Final[threading.Lock] = threading.Lock()
#: §8.2: the supervisor looks at its workers this often.
SUPERVISOR_POLL_S: Final[float] = 0.1
#: §9.3 with a failing store (rf1-Q1): after `shutdown`, a failing store is tried this many
#: times, backing off from `SUPERVISOR_POLL_S` by doubling (3.1 s of waits in all), and then
#: given up. The jobs it could not end stay as recorded, and the next open ends them
#: `failed(owner_lost)`. Before `shutdown` a store error is retried without bound (T07 review S1).
SHUTDOWN_STORE_ATTEMPTS: Final[int] = 6


def _kill_tree(process: BaseProcess) -> None:
    """ADR 0033 D2 (amending ADR 0020 D3): SIGKILL the worker's process group — the worker and
    every child it spawned — falling back to `Process.kill()` where there are no process groups,
    or no group led by the worker (it died before `setpgid`, or is gone). The worker's pid cannot
    be reused while it is unreaped, so the group id names the worker's group only."""
    pid = process.pid
    if pid is not None and hasattr(os, "killpg") and process.is_alive():
        try:
            os.killpg(pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError):
            pass
    process.kill()


def _shutdown_backoff_s(failures: int) -> float:
    """The wait after the `failures`-th consecutive failure at shutdown (1-based)."""
    return SUPERVISOR_POLL_S * 2.0 ** (failures - 1)


class CancelToken:
    """§8.1's inline cancel token: a `threading.Event` with the reason it was set for.

    `is_set` is what the installed check asks at every `Trace.record` and stage boundary; the
    executor's `test_hook_on_check` (Python only, never reachable from a request) sees each ask
    with its ordinal, so a test can cancel at a chosen record.
    """

    def __init__(self, job_id: str, hook: Callable[[str, int], None] | None = None) -> None:
        self.job_id = job_id
        self.event = threading.Event()
        self.reason: CancelReason = "cancel_requested"
        self.checks = 0
        self._hook = hook

    def set(self, reason: CancelReason = "cancel_requested") -> None:
        if not self.event.is_set():
            self.reason = reason
        self.event.set()

    def is_set(self) -> bool:
        self.checks += 1
        if self._hook is not None:
            self._hook(self.job_id, self.checks)
        return self.event.is_set()


class InlineExecutor:
    """§9.1: runs each job in the calling thread under `COMPUTE_LOCK`.

    `test_hook_on_check` and `clock` are Python-only test hooks, as the store's
    `test_hook_after_revision_insert` is: the first sees every interruption check of a running
    job, the second replaces `time.monotonic` for the wall-time deadline (§8.3).
    """

    def __init__(self) -> None:
        self.test_hook_on_check: Callable[[str, int], None] | None = None
        self.clock: Callable[[], float] = time.monotonic
        self._tokens: dict[str, CancelToken] = {}
        self._tokens_lock = threading.Lock()

    def run(self, context: RunContext, job_id: str) -> None:
        """Run the queued job `job_id` to its end, as its owner. A job no longer queued when the
        lock is taken — cancelled meanwhile — is left as it is."""
        try:
            with COMPUTE_LOCK:
                self._run(context, job_id)
        except KeyboardInterrupt:
            context.store.finish_job(
                job_id,
                owner_instance=context.owner_instance,
                ending=JobEnding(status="cancelled", reason="keyboard_interrupt"),
                error=None,
                worker_result=None,
            )
            raise

    def shutdown(self) -> None:
        """Nothing to stop: an inline job runs in its caller's thread and has ended by now."""

    def signal_cancel(self, job_id: str, reason: CancelReason = "cancel_requested") -> bool:
        """Set the running job's token; whether this executor is running `job_id`."""
        with self._tokens_lock:
            token = self._tokens.get(job_id)
        if token is None:
            return False
        token.set(reason)
        return True

    def _run(self, context: RunContext, job_id: str) -> None:
        store = context.store
        if not store.start_job(job_id, owner_instance=context.owner_instance):
            return
        job = store.get_job(job_id)
        assert job is not None
        token = CancelToken(job_id, self.test_hook_on_check)
        with self._tokens_lock:
            self._tokens[job_id] = token
        budget = job.effective_budgets.wall_time_s
        # §8.3: the clock starts at `started`.
        deadline = self.clock() + budget if budget is not None else None
        try:
            with interruptible(
                token, deadline, cancel_reason=lambda: token.reason, clock=self.clock
            ) as check:
                result = execute(context, job, check=check, cancel=token.set)
        except Exception as error:  # a defect of the runner or the store, never of a solve
            _LOG.exception("job %s: the runner raised", job_id)
            result = _defect(error)
        finally:
            with self._tokens_lock:
                self._tokens.pop(job_id, None)
        store.finish_job(
            job_id,
            owner_instance=context.owner_instance,
            ending=result.ending,
            error=result.error,
            worker_result=result.as_document(),
        )


def _defect(error: Exception) -> WorkerResult:
    """An exception that escaped the operation body: `failed`, with no text of it in the error
    (D9 (4): the traceback goes to the log)."""
    store = isinstance(error, sqlite3.Error)
    return WorkerResult(
        status="failed",
        reason="store_error" if store else "operation_error",
        interruption=None,
        error=ApiError(
            code="internal_error",
            message=f"the job runner raised {type(error).__name__}; see the log",
            retryable=store,
            detail={"exception": type(error).__name__},
        ),
    )


#: Why the supervisor is stopping a worker (§8.2).
StopReason = Literal["cancel_requested", "server_shutdown", "wall_time_exhausted"]


@dataclass
class _Slot:
    """One job's worker, as the supervisor sees it."""

    job_id: str
    process: BaseProcess
    cancel_event: Event
    cancel_reason: Synchronized[int]
    started: Event
    budget: float | None
    launched: bool = False
    #: The supervisor's deadline, from the moment it first sees the worker started (§8.3).
    deadline: float | None = None
    #: Why and since when the supervisor is stopping the worker; `None` while it is not.
    stopping: StopReason | None = None
    stopping_since: float = 0.0
    killed: bool = False


class ProcessExecutor:
    """§9.1: each job in a freshly spawned worker process, under a supervisor thread.

    Construct it unbound and pass it — or `executor="process"`, which constructs one — to
    `LocalApplication.open`, which binds it to the owner with `start` once recovery has run.
    `test_hooks=True` lets the workers honour §15 W4c's environment variables
    (`jobs.worker.PAUSE_AT_STAGE_VARIABLE`, `jobs.worker.BLOCK_VARIABLE`); it is a constructor
    argument only, which no API, CLI flag or policy exposes. The settings (`max_workers`,
    `grace_s`) are the project policy's at `open`.
    """

    def __init__(self, *, test_hooks: bool = False) -> None:
        self.test_hooks = test_hooks
        self.settings = ExecutorSettings()
        self._context: RunContext | None = None
        self._spawn = multiprocessing.get_context("spawn")
        self._queue: deque[str] = deque()
        self._slots: dict[str, _Slot] = {}
        self._condition = threading.Condition()
        self._closing = False
        self._thread: threading.Thread | None = None

    # -- the owner's side ---------------------------------------------------------------------

    def start(self, context: RunContext, settings: ExecutorSettings) -> None:
        """Bind to the owner and start the supervisor thread."""
        if self._context is not None:
            raise RuntimeError("this process executor is already bound to an owner")
        if context.store.directory is None:
            raise ValueError("the process executor needs a project directory")
        self._context = context
        self.settings = settings
        self._thread = threading.Thread(
            target=self._supervise,
            name=f"process-executor-{context.owner_instance[:8]}",
            daemon=True,
        )
        self._thread.start()

    def run(self, context: RunContext, job_id: str) -> None:
        """Queue the accepted job `job_id` for a worker and return at once (the inline
        executor's `run` returns once the job has ended, this one once it is queued)."""
        assert self._context is not None and context.owner_instance == self._context.owner_instance
        with self._condition:
            if not self._closing:
                self._queue.append(job_id)
                self._condition.notify_all()
                return
        self._end_unstarted(job_id)

    def signal_cancel(self, job_id: str, reason: CancelReason = "cancel_requested") -> bool:
        """Start stopping `job_id`'s worker (§8.2); whether this executor has one for it."""
        with self._condition:
            slot = self._slots.get(job_id)
            if slot is None:
                return False
            self._stop(slot, reason)
            self._condition.notify_all()
        return True

    def pid(self, job_id: str) -> int | None:
        """The process id of `job_id`'s worker while it has one (for operators and tests)."""
        with self._condition:
            slot = self._slots.get(job_id)
            return slot.process.pid if slot is not None and slot.launched else None

    def shutdown(self) -> None:
        """§9.3's clean shutdown: end the queued jobs `cancelled(server_shutdown)`, stop the
        running ones cooperatively and then forced with the same reason, and return once every
        worker has been joined and its job ended. Idempotent.

        A store that keeps failing is tried `SHUTDOWN_STORE_ATTEMPTS` times, here and in the
        supervisor, and then given up: shutdown returns, and a job it could not end stays
        `queued` or `running` until the next open ends it `failed(owner_lost)` (rf1-Q1)."""
        with self._condition:
            closing, self._closing = self._closing, True
            thread = self._thread
            if thread is None or closing:
                return
            queued = list(self._queue)
            self._queue.clear()
            for slot in self._slots.values():
                self._stop(slot, "server_shutdown")
            self._condition.notify_all()
        failures = 0
        while queued and failures < SHUTDOWN_STORE_ATTEMPTS:
            try:
                self._end_unstarted(queued[0])
            except Exception:
                failures += 1
                _LOG.exception("process executor: job %s: ending at shutdown failed", queued[0])
                if failures < SHUTDOWN_STORE_ATTEMPTS:
                    time.sleep(_shutdown_backoff_s(failures))
                continue
            queued.pop(0)
        if queued:
            _LOG.error(
                "process executor: shutdown gave up on a failing store; jobs %s stay queued"
                " until the next open ends them failed(owner_lost)",
                queued,
            )
        thread.join()

    # -- the supervisor thread ----------------------------------------------------------------

    def _supervise(self) -> None:
        failures = 0  # consecutive failing polls since `shutdown` (rf1-Q1)
        while True:
            with self._condition:
                if self._closing and not self._slots and not self._queue:
                    return
                if self._closing and failures >= SHUTDOWN_STORE_ATTEMPTS:
                    abandoned = list(self._slots.values())
                    _LOG.error(
                        "process executor: shutdown gave up on a failing store; jobs %s stay as"
                        " recorded until the next open ends them failed(owner_lost)",
                        sorted({*self._slots, *self._queue}),
                    )
                    self._slots.clear()
                    self._queue.clear()
                    for slot in abandoned:  # no worker outlives the shutdown
                        if slot.launched and slot.process.is_alive():
                            _kill_tree(slot.process)
                    return
                admitted: list[str] = []
                while self._queue and len(self._slots) + len(admitted) < self.settings.max_workers:
                    admitted.append(self._queue.popleft())
            # The supervisor outlives a store error, and the next poll retries what it interrupted:
            # an admitted id goes back to the head of the queue, and a slot leaves only once its
            # job's end is recorded, so a job is never left `queued` or `running` behind a
            # transient error (T07 review S1).
            retry: list[str] = []
            finished: list[_Slot] = []
            for index, job_id in enumerate(admitted):
                try:
                    self._launch(job_id)
                except Exception:
                    _LOG.exception("process executor: job %s: launching failed", job_id)
                    retry = admitted[index:]
                    break
            failed = bool(retry)
            try:
                ended = self._watch()
            except Exception:
                _LOG.exception("process executor: a supervisor poll failed")
                ended, failed = [], True
            for slot in ended:
                try:
                    self._finish(slot)
                except Exception:
                    _LOG.exception("process executor: job %s: ending failed", slot.job_id)
                    failed = True
                    continue
                finished.append(slot)
            with self._condition:
                self._queue.extendleft(reversed(retry))
                for slot in finished:
                    self._slots.pop(slot.job_id, None)
                if self._closing and failed:  # bounded, with backoff (rf1-Q1)
                    failures += 1
                    if failures < SHUTDOWN_STORE_ATTEMPTS:
                        self._condition.wait(_shutdown_backoff_s(failures))
                    continue
                failures = 0
                if not finished and len(retry) == len(admitted):
                    # Idle or failing, it sleeps until `run` or `shutdown` notifies, or a poll.
                    busy = self._slots or self._queue
                    self._condition.wait(SUPERVISOR_POLL_S if busy else None)

    def _launch(self, job_id: str) -> None:
        """Start a worker for a job still queued; a job cancelled meanwhile needs none."""
        assert self._context is not None
        job = self._context.store.get_job(job_id)
        if job is None or job.status != "queued":
            return
        cancel_event = self._spawn.Event()
        cancel_reason: Synchronized[int] = self._spawn.Value("i", 0)
        started = self._spawn.Event()
        process = self._spawn.Process(
            target=worker.main,
            args=(
                str(self._context.root),
                job_id,
                self._context.owner_instance,
                cancel_event,
                cancel_reason,
                started,
                self.test_hooks,
            ),
            name=f"job-worker-{job_id}",
            daemon=True,
        )
        slot = _Slot(
            job_id=job_id,
            process=process,
            cancel_event=cancel_event,
            cancel_reason=cancel_reason,
            started=started,
            budget=job.effective_budgets.wall_time_s,
        )
        with self._condition:
            closing = self._closing
            if not closing:
                self._slots[job_id] = slot
        if closing:  # `shutdown` came between the queue and here
            self._end_unstarted(job_id)
            return
        try:
            process.start()
        except Exception:
            _LOG.exception("process executor: job %s: the worker could not be started", job_id)
            with self._condition:
                self._slots.pop(job_id, None)
            self._context.store.finish_job(
                job_id,
                owner_instance=self._context.owner_instance,
                ending=JobEnding(status="failed", reason="worker_lost"),
                error=ApiError(
                    code="internal_error",
                    message="the job's worker process could not be started",
                    retryable=True,
                    detail={"exitcode": None},
                ),
                worker_result=None,
            )
            return
        with self._condition:
            slot.launched = True

    def _stop(self, slot: _Slot, reason: StopReason) -> None:
        """§8.2 step 1, under the condition's lock: signal the worker once, and start the grace
        period. A passed deadline signals nothing: the worker's own deadline started before the
        supervisor's (`jobs.worker`), so it has already stopped the job if a check could."""
        if slot.stopping is not None:
            return
        slot.stopping = reason
        slot.stopping_since = time.monotonic()
        if reason != "wall_time_exhausted":
            with slot.cancel_reason.get_lock():
                slot.cancel_reason.value = (
                    worker.SERVER_SHUTDOWN
                    if reason == "server_shutdown"
                    else worker.CANCEL_REQUESTED
                )
            slot.cancel_event.set()

    def _watch(self) -> list[_Slot]:
        """One poll (§8.2): the slots whose worker has exited; the others are stopped and killed
        as they become due."""
        assert self._context is not None
        store = self._context.store
        with self._condition:
            slots = [slot for slot in self._slots.values() if slot.launched]
        ended: list[_Slot] = []
        for slot in slots:
            if not slot.process.is_alive():
                ended.append(slot)
                continue
            now = time.monotonic()
            if slot.deadline is None and slot.budget is not None and slot.started.is_set():
                slot.deadline = now + slot.budget
            if slot.stopping is None and slot.started.is_set():
                # Another instance's `cancel_job` reaches this owner through the store.
                if store.cancel_requested(slot.job_id):
                    with self._condition:
                        self._stop(slot, "cancel_requested")
                elif slot.deadline is not None and now >= slot.deadline:
                    with self._condition:
                        self._stop(slot, "wall_time_exhausted")
            if (
                slot.stopping is not None
                and not slot.killed
                and now >= slot.stopping_since + self.settings.grace_s
            ):
                _kill_tree(slot.process)
                slot.killed = True
        return ended

    def _finish(self, slot: _Slot) -> None:
        """The owner's end of a job whose worker has exited (§6.2, §8.2)."""
        assert self._context is not None
        store = self._context.store
        slot.process.join()
        job = store.get_job(slot.job_id)
        if job is None or job.status in TERMINAL_STATUSES:
            return  # cancelled while queued: the worker found nothing to start
        document = store.worker_result(slot.job_id)
        log = self._worker_log(job) if job.status == "running" else None
        if document is not None:
            result = WorkerResult.from_document(document)
        elif slot.killed and slot.stopping is not None:
            result = WorkerResult(
                status="timed_out" if slot.stopping == "wall_time_exhausted" else "cancelled",
                reason=slot.stopping,
                interruption="forced",
                error=None,
            )
        else:
            detail: dict[str, object] = {"exitcode": slot.process.exitcode}
            if log is not None:
                detail["log_artifact_id"] = log
            result = WorkerResult(
                status="failed",
                reason="worker_lost",
                interruption=None,
                error=ApiError(
                    code="internal_error",
                    message="the job's worker process exited without a result",
                    retryable=False,
                    detail=detail,
                ),
            )
        store.finish_job(
            slot.job_id,
            owner_instance=self._context.owner_instance,
            ending=result.ending,
            error=result.error,
            worker_result=document,
        )

    def _worker_log(self, job: Job) -> str | None:
        """§5.4: a non-empty `worker.log` is the running job's last output; its artifact id.

        Idempotent, for a `_finish` retried after a store error: a registered row is not
        registered again, and a referenced one is not appended again."""
        assert self._context is not None
        context = self._context
        job_id = job.job_id
        artifact_id = f"{job_id}:{worker.WORKER_LOG}"
        if any(output.artifact_id == artifact_id for output in job.outputs):
            return artifact_id
        path = context.root / JOBS_DIR / job_id / worker.WORKER_LOG
        if not path.is_file() or path.stat().st_size == 0:
            return None
        row = ArtifactRow(
            artifact_id=artifact_id,
            job_id=job_id,
            kind="worker_log",
            name=worker.WORKER_LOG,
            sha256=file_sha256(path),
            size_bytes=path.stat().st_size,
            relpath=path.relative_to(context.root).as_posix(),
        )
        if context.store.artifact(artifact_id) is None:
            with context.store.writing() as connection:
                context.store.register_artifacts(connection, [row])
        if not context.store.append_job_event(
            job_id, owner_instance=context.owner_instance, output=row.as_ref()
        ):
            return None
        return row.artifact_id

    def _end_unstarted(self, job_id: str) -> None:
        """§9.3: a job this owner accepted and will not start ends `cancelled(server_shutdown)`."""
        assert self._context is not None
        self._context.store.finish_job(
            job_id,
            owner_instance=self._context.owner_instance,
            ending=JobEnding(status="cancelled", reason="server_shutdown"),
            error=None,
            worker_result=None,
        )
