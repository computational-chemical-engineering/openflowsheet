"""Spawned-process bodies for the T07 store tests (design note §9.2–§9.3, W2a).

`multiprocessing`'s spawn start method imports these by module name in a fresh interpreter, so
they live in an importable module rather than inside a test. Each opens its own
`LocalApplication`, exactly as a second CLI invocation or server would.
"""

from __future__ import annotations

import os
import threading
import time
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from typing import Any

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revisions import Revision
from openflowsheet.application.store import IdempotencyKeyReusedError
from openflowsheet.application.types import (
    LOCAL_OWNER_PRINCIPAL,
    Change,
    Edit,
    EffectiveBudgets,
    JobRequest,
    SolveBody,
)

POLICY_SHA256 = "0" * 64


def solve_request(key: str, revision_id: str = "rev-1") -> JobRequest:
    return JobRequest(
        operation="solve", idempotency_key=key, body=SolveBody(revision_id=revision_id)
    )


def accept(application: LocalApplication, request: JobRequest) -> tuple[str, bool]:
    job, replayed = application.store.accept_job(
        request,
        principal_id=application.principal_id,
        capability_id=LOCAL_OWNER_PRINCIPAL,
        policy_sha256=POLICY_SHA256,
        owner_instance=application.owner_instance,
        effective_budgets=EffectiveBudgets(),
    )
    return job.job_id, replayed


def contend_submit(
    directory: str, key: str, threads: int, ready: Queue[Any], start: Event, results: Queue[Any]
) -> None:
    """`threads` threads submit one request under one key, released together with the peer."""
    application = LocalApplication.open(directory)
    barrier = threading.Barrier(threads + 1)
    outcomes: list[tuple[str, bool] | str] = []
    lock = threading.Lock()

    def one() -> None:
        barrier.wait()
        start.wait()
        try:
            outcome: tuple[str, bool] | str = accept(application, solve_request(key))
        except IdempotencyKeyReusedError:
            outcome = "reused"
        with lock:
            outcomes.append(outcome)

    workers = [threading.Thread(target=one) for _ in range(threads)]
    for worker in workers:
        worker.start()
    barrier.wait()
    ready.put(os.getpid())
    for worker in workers:
        worker.join()
    application.close()
    results.put(outcomes)


def crash_mid_commit(directory: str, document: dict[str, Any]) -> None:
    """Die (no cleanup, no rollback) between the revision insert and the head move."""
    application = LocalApplication.open(directory)
    store = application.store
    store.test_hook_after_revision_insert = lambda: os._exit(3)
    with store.writing() as connection:
        store.commit_revision(
            connection,
            Revision(revision_id="rev-crash", document=document, parent_revision=None),
            principal_id=application.principal_id,
            capability_id=LOCAL_OWNER_PRINCIPAL,
            policy_sha256=POLICY_SHA256,
        )


def own_jobs_then_hang(directory: str, ready: Queue[Any]) -> None:
    """Accept two jobs, start one, report their ids, and wait to be killed."""
    application = LocalApplication.open(directory)
    queued, _ = accept(application, solve_request("queued-key"))
    running, _ = accept(application, solve_request("running-key"))
    assert application.store.start_job(running, owner_instance=application.owner_instance)
    ready.put((queued, running))
    time.sleep(600)


def contend_commit(
    directory: str,
    key: str,
    expected_revision: str,
    threads: int,
    ready: Queue[Any],
    start: Event,
    results: Queue[Any],
) -> None:
    """`threads` threads commit one change under one key, released together with the peer."""
    application = LocalApplication.open(directory)
    change = Change(edits=(Edit("set", ("units",), [{"id": "U2"}]),))
    barrier = threading.Barrier(threads + 1)
    outcomes: list[tuple[str, str | None]] = []
    lock = threading.Lock()

    def one() -> None:
        barrier.wait()
        start.wait()
        result = application.commit_change(change, expected_revision, key)
        with lock:
            outcomes.append((result.status, result.revision_id))

    workers = [threading.Thread(target=one) for _ in range(threads)]
    for worker in workers:
        worker.start()
    barrier.wait()
    ready.put(os.getpid())
    for worker in workers:
        worker.join()
    application.close()
    results.put(outcomes)
