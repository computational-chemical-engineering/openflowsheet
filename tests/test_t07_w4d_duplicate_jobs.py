"""T07 W4d: duplicate jobs under the process executor (design note §7, §15 W4d; gate G4).

Two servers — two processes, each a `LocalApplication` opened with `executor="process"` — each
with 25 threads submit a solve under one idempotency key, released together:

- **identical bodies:** exactly one job, 49 `replayed`, one audited acceptance, one bundle; the
  job runs once, in one worker, and ends `completed`;
- **different bodies** (each server its own revision): still exactly one job; the winner's peers
  replay it and every submission of the other body is refused `idempotency_key_reused` (HTTP 409)
  naming the winner's request hash;
- **after a restart** the key returns the same `job_id`, and a different body under it is still
  refused. (The restart after a `kill -9` of the owner, whose job ends `failed(owner_lost)` and
  is still what the key returns, is `test_t07_w4c_process_executor`'s.)
"""

from __future__ import annotations

import multiprocessing
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import PATIENCE_S, commit, lifecycle_violations
from t07_process_support import contend_process_submit, solve_request

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import API_ERROR_HTTP_STATUS

SPAWN = multiprocessing.get_context("spawn")
THREADS = 25
KEY = "one-key"


def _contend(directory: Path, revisions: tuple[str, str]) -> list[tuple[str, str, Any]]:
    """Two servers, `THREADS` threads each, the i-th server submitting `revisions[i]`."""
    ready = SPAWN.Queue()
    results = SPAWN.Queue()
    start = SPAWN.Event()
    servers = [
        SPAWN.Process(
            target=contend_process_submit,
            args=(str(directory), revision_id, KEY, THREADS, ready, start, results),
        )
        for revision_id in revisions
    ]
    for server in servers:
        server.start()
    for _ in servers:
        ready.get(timeout=PATIENCE_S)
    start.set()
    outcomes = [outcome for _ in servers for outcome in results.get(timeout=4 * PATIENCE_S)]
    for server in servers:
        server.join(PATIENCE_S)
        assert server.exitcode == 0
    return outcomes


@pytest.fixture
def project(tmp_path: Path) -> tuple[Path, str, str]:
    """A project with two solvable revisions; `(directory, first, second)`."""
    directory = tmp_path / "p"
    with LocalApplication.create(directory) as application:
        first = commit(application, CORPUS["SYN-001-nominal"]())
        second = commit(application, CORPUS["SYN-001-T06-STA02"]())
    return directory, first, second


def _accepted(application: LocalApplication) -> list[dict[str, Any]]:
    return [
        row
        for row in application.store.audit_rows()
        if row["operation"] == "submit_job" and row["outcome"] == "allowed"
    ]


def test_g4_one_key_identical_bodies_make_exactly_one_job(project: tuple[Path, str, str]) -> None:
    directory, revision_id, _ = project
    outcomes = _contend(directory, (revision_id, revision_id))

    assert len(outcomes) == 2 * THREADS
    assert {kind for kind, _, _ in outcomes} == {"job"}
    (job_id,) = {job_id for _, job_id, _ in outcomes}
    assert Counter(replayed for _, _, replayed in outcomes) == {False: 1, True: 49}

    with LocalApplication.open(directory, executor="process") as restarted:
        assert restarted.store.job_ids() == (job_id,)
        assert len(_accepted(restarted)) == 1, "one effect, audited once"
        job = restarted.get_job(job_id)
        assert job.status == "completed"
        assert sorted(path.name for path in (directory / "jobs").iterdir()) == [job_id]
        # After the restart the key still names the job; a different body is still refused.
        again = restarted.submit_job(solve_request(KEY, revision_id))
        assert (again.replayed, again.job.job_id, again.job.status) == (True, job_id, "completed")
        with pytest.raises(ApplicationError) as refused:
            restarted.submit_job(solve_request(KEY, revision_id, policy_id="T06-revision-v2"))
        assert refused.value.code == "idempotency_key_reused"
        assert API_ERROR_HTTP_STATUS[refused.value.code] == 409
        assert refused.value.error.detail["original_request_sha256"] == job.request_sha256
        assert restarted.store.job_ids() == (job_id,)
        assert lifecycle_violations(restarted) == {}


def test_g4_one_key_different_bodies_make_one_job_and_refuse_the_other(
    project: tuple[Path, str, str],
) -> None:
    directory, first, second = project
    outcomes = _contend(directory, (first, second))

    assert len(outcomes) == 2 * THREADS
    jobs = [outcome for outcome in outcomes if outcome[0] == "job"]
    refused = [outcome for outcome in outcomes if outcome[0] == "refused"]
    (job_id,) = {job_id for _, job_id, _ in jobs}
    # One server's body won: its 25 submissions are the job (one new, 24 replays); the other
    # server's 25 are refused, naming the winner's request.
    assert (len(jobs), len(refused)) == (THREADS, THREADS)
    assert Counter(replayed for _, _, replayed in jobs) == {False: 1, True: THREADS - 1}
    with LocalApplication.open(directory) as reopened:
        job = reopened.get_job(job_id)
        assert {(code, original) for _, code, original in refused} == {
            ("idempotency_key_reused", job.request_sha256)
        }
        assert reopened.store.job_ids() == (job_id,)
        assert len(_accepted(reopened)) == 1
        assert job.status == "completed"
        assert lifecycle_violations(reopened) == {}
