"""T07 W2a: the project store, owner locks and recovery (design note §9.2–§9.3, §7).

The store is what makes idempotency and job records survive a restart and what lets two CLI
invocations share one ledger (D3). These tests hold its four promises: what was written is there
after a reopen; of many concurrent submissions under one key exactly one takes effect; a commit
that dies part way leaves nothing visible; and a job whose owner died is ended
`failed(owner_lost)` rather than left `running` for ever.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import signal
import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest
import t07_store_support as support

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.jobs.model import check_lifecycle
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revisions import Revision
from openflowsheet.application.store import (
    DATABASE_NAME,
    POLICY_NAME,
    STORE_SCHEMA,
    IdempotencyKeyReusedError,
    ProjectStore,
    StoreError,
)
from openflowsheet.application.types import LOCAL_OWNER_PRINCIPAL, ProjectPolicy

SPAWN = multiprocessing.get_context("spawn")
DOCUMENT = {"schema_version": "0.1", "title": "a store test", "units": [{"id": "U1"}]}


def commit(application: LocalApplication, revision_id: str, document: dict[str, Any]) -> None:
    store = application.store
    with store.writing() as connection:
        store.commit_revision(
            connection,
            Revision(revision_id=revision_id, document=document, parent_revision=None),
            principal_id=application.principal_id,
            capability_id=LOCAL_OWNER_PRINCIPAL,
            policy_sha256=support.POLICY_SHA256,
        )


def head_and_history(store: ProjectStore) -> tuple[str | None, tuple[str, ...]]:
    with store.reading() as connection:
        return store.head(connection), store.revision_ids(connection)


def assert_lifecycle(store: ProjectStore, job_id: str) -> None:
    job = store.get_job(job_id)
    assert job is not None
    assert check_lifecycle(job, store.job_events(job_id)) == []


# ------------------------------------------------------------------------------ the directory


def test_create_lays_out_the_project_directory(tmp_path: Path) -> None:
    directory = tmp_path / "project"
    with LocalApplication.create(directory, project_id="p-1") as application:
        assert application.project_id == "p-1"
        assert application.principal_id == LOCAL_OWNER_PRINCIPAL
        assert (directory / "owners" / f"{application.owner_instance}.lock").is_file()
    assert {path.name for path in directory.iterdir()} == {
        DATABASE_NAME,
        POLICY_NAME,
        "owners",
        "jobs",
        "imports",
    }
    assert not any((directory / "owners").iterdir()), "a clean close releases the owner lock"

    policy = ProjectPolicy.from_document(
        json.loads((directory / POLICY_NAME).read_text(encoding="utf-8"))
    )
    assert policy.project_id == "p-1" and policy.capabilities == ()

    connection = sqlite3.connect(directory / DATABASE_NAME)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        schema = connection.execute("SELECT value FROM meta WHERE key = 'store_schema'").fetchone()
        assert schema[0] == STORE_SCHEMA
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    finally:
        connection.close()
    assert {"meta", "revisions", "refs", "ledger", "jobs", "events", "artifacts", "audit"} <= tables


def test_create_refuses_a_non_empty_directory_and_open_refuses_a_non_project(
    tmp_path: Path,
) -> None:
    (tmp_path / "busy").mkdir()
    (tmp_path / "busy" / "file.txt").write_text("x", encoding="utf-8")
    with pytest.raises(StoreError, match="not empty"):
        LocalApplication.create(tmp_path / "busy")
    with pytest.raises(StoreError, match="not a project"):
        LocalApplication.open(tmp_path / "busy")


#: MSG §3.8's matrix: the directory's state → (outcome without `exist_ok`, outcome with it). An
#: outcome is "create", "open" or the coded refusal.
FB01_MATRIX = {
    "absent": ("create", "create"),
    "empty": ("create", "create"),
    "project": ("project_exists", "open"),
    "other project": ("project_exists", "project_id_mismatch"),
    "not a project": ("directory_not_empty", "directory_not_empty"),
    "file": ("not_a_directory", "not_a_directory"),
}


def _fb01_directory(root: Path, state: str) -> Path:
    directory = root / "plant"
    if state == "empty":
        directory.mkdir()
    elif state in ("project", "other project"):
        LocalApplication.create(directory, project_id="p-existing").close()
    elif state == "not a project":
        directory.mkdir()
        (directory / "notes.txt").write_text("x", encoding="utf-8")
    elif state == "file":
        directory.write_text("x", encoding="utf-8")
    return directory


@pytest.mark.parametrize("exist_ok", [False, True])
@pytest.mark.parametrize("state", sorted(FB01_MATRIX))
def test_msg_fb01_create_gives_the_stated_outcome_for_each_directory_state(
    tmp_path: Path, state: str, exist_ok: bool
) -> None:
    directory = _fb01_directory(tmp_path, state)
    project_id = "p-other" if state == "other project" else "p-existing"
    expected = FB01_MATRIX[state][exist_ok]
    before = sorted(path.name for path in directory.iterdir()) if directory.is_dir() else None
    if expected in ("create", "open"):
        with LocalApplication.create(directory, project_id=project_id, exist_ok=exist_ok) as app:
            assert app.project_id == project_id
            jobs = app.list_jobs().items
        assert len(jobs) == 0
        if expected == "open":
            assert sorted(path.name for path in directory.iterdir()) == before
        return
    with pytest.raises(StoreError) as refused:
        LocalApplication.create(directory, project_id=project_id, exist_ok=exist_ok)
    assert refused.value.code == expected
    assert refused.value.args == (f"{expected}: {directory}",)
    assert str(refused.value).split("\n")[-1] == f"  Details: {expected}: {directory}"
    assert refused.value.explanation()["kind"] == "input"
    assert refused.value.explanation()["family"] == "refusal"
    if expected in ("project_exists", "directory_not_empty"):
        assert "is not empty" in str(refused.value).split("\n")[0]
    if directory.is_dir():
        assert sorted(path.name for path in directory.iterdir()) == before  # nothing written
    else:
        assert directory.read_text(encoding="utf-8") == "x"


def test_msg_fb01_the_python_text_of_project_exists_is_the_worked_entry(tmp_path: Path) -> None:
    """§4.13.4's Python rendering, on the second run of the old quickstart."""
    directory = tmp_path / "plant"
    LocalApplication.create(directory).close()
    with pytest.raises(StoreError) as refused:
        LocalApplication.create(directory)
    lines = str(refused.value).split("\n")
    assert lines[0] == (
        f"Directory '{directory}' is not empty: it already holds a project, and create() needs "
        "a new or empty directory."
    )
    assert lines[2] == (
        f'  Do:      To use the existing project, call LocalApplication.open("{directory}"), or '
        f'call LocalApplication.create("{directory}", exist_ok=True), which opens it.'
    )


def test_msg_fb01_open_on_a_non_project_is_the_coded_not_a_project(tmp_path: Path) -> None:
    with pytest.raises(StoreError) as refused:
        ProjectStore.open(tmp_path)
    assert refused.value.code == "not_a_project"
    assert refused.value.args == (f"not_a_project: {tmp_path}",)
    assert "is not a project" in str(refused.value)


def test_msg_fb01_an_uncoded_store_error_is_unchanged() -> None:
    error = StoreError("an audit row joins more than one ledger row")
    assert error.code is None
    assert str(error) == "an audit row joins more than one ledger row"
    reused = IdempotencyKeyReusedError("ab" * 32)
    assert reused.code is None and str(reused) == reused.args[0]


def test_an_executor_this_build_lacks_is_an_explicit_unsupported(tmp_path: Path) -> None:
    """W2 held `executor="process"` to this until W4c built it
    (`tests/test_t07_w4c_process_executor.py`); any other name still gets it."""
    LocalApplication.create(tmp_path / "p").close()
    with pytest.raises(ApplicationError) as refused:
        LocalApplication.open(tmp_path / "p", executor="threads")  # type: ignore[arg-type]
    assert refused.value.code == "unsupported"


# ------------------------------------------------------------------------------- persistence


def test_everything_written_survives_a_reopen(tmp_path: Path) -> None:
    """D3: the ledger and the job records outlive the process that wrote them (§7 Restarts)."""
    directory = tmp_path / "p"
    with LocalApplication.create(directory) as first:
        commit(first, "rev-1", DOCUMENT)
        job_id, replayed = support.accept(first, support.solve_request("key-1"))
        assert not replayed

    with LocalApplication.open(directory) as second:
        store = second.store
        assert head_and_history(store) == ("rev-1", ("rev-1",))
        with store.reading() as connection:
            revision = store.get_revision(connection, "rev-1")
        assert revision is not None and dict(revision.document) == DOCUMENT
        assert second.recovered == (job_id,), "the first owner closed with its job queued"

        # A key submitted before the restart returns the same job afterwards; it may have been
        # ended `owner_lost` meanwhile, and a deliberate re-run takes a new key (J6).
        again, replayed = support.accept(second, support.solve_request("key-1"))
        assert (again, replayed) == (job_id, True)
        with pytest.raises(IdempotencyKeyReusedError) as reused:
            support.accept(second, support.solve_request("key-1", revision_id="rev-2"))
        assert reused.value.original_request_sha256 == support.solve_request("key-1").request_sha256
        assert store.job_ids() == (job_id,)
        assert_lifecycle(store, job_id)


def test_a_rolled_back_transaction_leaves_nothing(tmp_path: Path) -> None:
    with LocalApplication.create(tmp_path / "p") as application:
        store = application.store

        def refuse() -> None:
            raise RuntimeError("a crash between the revision insert and the head move")

        store.test_hook_after_revision_insert = refuse
        with pytest.raises(RuntimeError, match="between the revision insert"):
            commit(application, "rev-1", DOCUMENT)
        assert head_and_history(store) == (None, ())

        store.test_hook_after_revision_insert = None
        commit(application, "rev-1", DOCUMENT)
        assert head_and_history(store) == ("rev-1", ("rev-1",))


def test_a_process_dying_mid_commit_leaves_nothing_visible(tmp_path: Path) -> None:
    """W2a: the hook kills the process between the revision insert and the head move."""
    directory = tmp_path / "p"
    with LocalApplication.create(directory) as application:
        commit(application, "rev-1", DOCUMENT)

    child = SPAWN.Process(
        target=support.crash_mid_commit, args=(str(directory), {**DOCUMENT, "title": "lost"})
    )
    child.start()
    child.join(60)
    assert child.exitcode == 3, "the child died inside the hook, not after a commit"

    with LocalApplication.open(directory) as reopened:
        store = reopened.store
        assert head_and_history(store) == ("rev-1", ("rev-1",))
        with store.reading() as connection:
            assert store.get_revision(connection, "rev-crash") is None
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


# ---------------------------------------------------------------------- one key, one effect


def test_two_processes_times_25_threads_with_one_key_make_exactly_one_job(tmp_path: Path) -> None:
    """§7 Races: of 50 concurrent submissions under one key, one inserts and 49 replay it."""
    directory = tmp_path / "p"
    LocalApplication.create(directory).close()
    ready = SPAWN.Queue()
    results = SPAWN.Queue()
    start = SPAWN.Event()
    children = [
        SPAWN.Process(
            target=support.contend_submit,
            args=(str(directory), "one-key", 25, ready, start, results),
        )
        for _ in range(2)
    ]
    for child in children:
        child.start()
    for _ in children:
        ready.get(timeout=120)
    start.set()
    outcomes = [outcome for _ in children for outcome in results.get(timeout=120)]
    for child in children:
        child.join(60)
        assert child.exitcode == 0

    assert len(outcomes) == 50
    assert "reused" not in outcomes
    job_ids = {job_id for job_id, _ in outcomes}
    assert len(job_ids) == 1
    assert sorted(replayed for _, replayed in outcomes) == [False] + [True] * 49

    store = ProjectStore.open(directory)
    try:
        assert store.job_ids() == tuple(job_ids)
        accepted = [row for row in store.audit_rows() if row["operation"] == "submit_job"]
        assert len(accepted) == 1, "one effect, audited once"
    finally:
        store.close()


def test_the_in_memory_store_serves_threads(tmp_path: Path) -> None:
    application = LocalApplication.in_memory()
    outcomes: list[tuple[str, bool]] = []
    lock = threading.Lock()

    def one() -> None:
        outcome = support.accept(application, support.solve_request("k"))
        with lock:
            outcomes.append(outcome)

    workers = [threading.Thread(target=one) for _ in range(16)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert len({job_id for job_id, _ in outcomes}) == 1
    assert sum(not replayed for _, replayed in outcomes) == 1
    application.close()


# ---------------------------------------------------------------------------------- recovery


def test_recovery_ends_the_jobs_of_a_killed_owner_as_owner_lost(tmp_path: Path) -> None:
    """§9.3: a SIGKILLed owner's lock is released by the kernel; the next open ends its jobs."""
    directory = tmp_path / "p"
    LocalApplication.create(directory).close()
    ready = SPAWN.Queue()
    child = SPAWN.Process(target=support.own_jobs_then_hang, args=(str(directory), ready))
    child.start()
    queued, running = ready.get(timeout=120)

    # While the owner lives, its jobs are its own: a second instance does not touch them.
    with LocalApplication.open(directory) as bystander:
        assert bystander.recovered == ()
        job = bystander.store.get_job(running)
        assert job is not None and job.status == "running"

    assert child.pid is not None
    os.kill(child.pid, signal.SIGKILL)
    child.join(60)

    with LocalApplication.open(directory) as recovering:
        assert recovering.recovered == (queued, running)
        store = recovering.store
        for job_id, kinds in (
            (queued, ["accepted", "ended"]),
            (running, ["accepted", "started", "ended"]),
        ):
            job = store.get_job(job_id)
            assert job is not None and job.status == "failed"
            assert job.ending is not None and job.ending.reason == "owner_lost"
            assert job.ended_at is not None
            assert [event.kind for event in store.job_events(job_id)] == kinds
            assert_lifecycle(store, job_id)
        owners = {path.stem for path in (directory / "owners").iterdir()}
        assert owners == {recovering.owner_instance}, "the dead owner's lock file is removed"

    with LocalApplication.open(directory) as later:
        assert later.recovered == (), "an ended job is never ended twice"
        assert [event.kind for event in later.store.job_events(running)][-1] == "ended"
