"""X07a (roadmap 0.5, ADR 0056 row 5): the platform layer `openflowsheet._platform`, on each leg.

- (a) the lock contract: a second descriptor on a held lock file raises `BlockingIOError` with an
  `errno` in `LOCK_HELD_ERRNOS`, and takes the lock once the first releases it (by
  `release_lock`, `close_locked` or `release_lock_file`, which also removes the file);
- (b) the store's owner lock (`application.store` §9.3) on top of it: a second hold is refused,
  and a released owner's lock file is gone;
- (c) the forced kill takes the tree: a worker that called `isolate_process_tree` and spawned a
  child holding a lock is ended by the executor's `_kill_tree`, and the child's lock comes free
  (POSIX: `killpg`; Windows: the worker's kill-on-close Job Object);
- (d) `replace_file` and `fsync_directory` give `atomic_write_bytes` its contract; on Windows a
  `PermissionError` is retried `REPLACE_ATTEMPTS` times in all, `REPLACE_RETRY_S` apart, then
  raised, and elsewhere it is raised at once;
- (e) POSIX only, by construction: the layer makes the calls its callers made before X07a, with
  the same arguments and in the same order (Linux behaviour unchanged).
"""

from __future__ import annotations

import multiprocessing
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from openflowsheet import _platform
from openflowsheet._files import atomic_write_bytes
from openflowsheet._platform import (
    LOCK_HELD_ERRNOS,
    close_locked,
    isolate_process_tree,
    lock_exclusive,
    release_lock,
    release_lock_file,
)
from openflowsheet.application.jobs.executor import _kill_tree
from openflowsheet.application.store import ProjectStore, StoreError

#: The child of (c): holds the lock on argv[1], then marks argv[2], then sleeps.
_HOLDER = """
import os, sys, time
from pathlib import Path
from openflowsheet._platform import lock_exclusive
handle = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)
lock_exclusive(handle)
Path(sys.argv[2]).write_text("held", encoding="utf-8")
time.sleep(120)
"""


def _open(path: Path) -> int:
    return os.open(path, os.O_RDWR | os.O_CREAT, 0o644)


def _held(path: Path) -> bool:
    """Whether another descriptor holds the lock on `path` (probed and released at once)."""
    handle = _open(path)
    try:
        lock_exclusive(handle)
    except BlockingIOError as error:
        assert error.errno in LOCK_HELD_ERRNOS
        return True
    finally:
        close_locked(handle)
    return False


def test_a_a_held_lock_refuses_a_second_descriptor(tmp_path: Path) -> None:
    path = tmp_path / "a.lock"
    first = _open(path)
    lock_exclusive(first)
    assert _held(path)
    release_lock(first)
    assert not _held(path)
    lock_exclusive(first)
    assert _held(path)
    close_locked(first)
    assert not _held(path)
    second = _open(path)
    lock_exclusive(second)
    release_lock_file(second, path)
    assert not path.exists()


def test_b_the_store_owner_lock(tmp_path: Path) -> None:
    store = ProjectStore.create(tmp_path / "project", project_id="x07a")
    other = ProjectStore.open(tmp_path / "project")
    try:
        store.acquire_owner("owner-1")
        lock = store._lock_path("owner-1")
        assert lock.exists() and _held(lock)
        with pytest.raises(StoreError, match="already held"):
            other.acquire_owner("owner-1")
        store.release_owner("owner-1")
        assert not lock.exists()
        other.acquire_owner("owner-1")
        other.release_owner("owner-1")
    finally:
        store.close()
        other.close()


def _tree_root(lock: str, ready: str) -> None:
    """(c)'s worker: the root of a process tree, with one child holding `lock`."""
    isolate_process_tree()
    subprocess.Popen([sys.executable, "-c", _HOLDER, lock, ready])
    time.sleep(120)


def test_c_the_forced_kill_takes_the_workers_child(tmp_path: Path) -> None:
    lock, ready = tmp_path / "child.lock", tmp_path / "ready"
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=_tree_root, args=(str(lock), str(ready)))
    process.start()
    try:
        _wait_for(ready.exists, 60.0, "the child to take its lock")
        assert _held(lock)
        _kill_tree(process)
        process.join(10.0)
        assert not process.is_alive()
        _wait_for(lambda: not _held(lock), 10.0, "the child's lock to come free")
    finally:
        if process.is_alive():
            process.kill()
            process.join(10.0)


def _wait_for(condition: Any, timeout_s: float, what: str) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out after {timeout_s} s waiting for {what}")
        time.sleep(0.05)


def test_d_atomic_write_replaces_in_place(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    atomic_write_bytes(path, b"one")
    atomic_write_bytes(path, b"two")
    assert path.read_bytes() == b"two"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["record.json"]
    _platform.fsync_directory(tmp_path)


def _replace_failing(monkeypatch: pytest.MonkeyPatch, platform: str, failures: int) -> list[str]:
    """`os.replace` raising `PermissionError` on its first `failures` calls; the log of calls."""
    calls: list[str] = []

    def fake_replace(source: Path, target: Path) -> None:
        calls.append("replace")
        if calls.count("replace") <= failures:
            raise PermissionError(13, "in use")

    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(_platform.os, "replace", fake_replace)
    monkeypatch.setattr(_platform.time, "sleep", lambda s: calls.append(f"sleep {s}"))
    return calls


def test_d_replace_retries_on_windows_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source, target = tmp_path / "a", tmp_path / "b"
    pause = f"sleep {_platform.REPLACE_RETRY_S}"
    calls = _replace_failing(monkeypatch, "win32", 2)
    _platform.replace_file(source, target)
    assert calls == ["replace", pause, "replace", pause, "replace"]

    calls = _replace_failing(monkeypatch, "win32", _platform.REPLACE_ATTEMPTS)
    with pytest.raises(PermissionError):
        _platform.replace_file(source, target)
    assert calls.count("replace") == _platform.REPLACE_ATTEMPTS
    assert calls.count(pause) == _platform.REPLACE_ATTEMPTS - 1
    assert calls[-1] == "replace"

    calls = _replace_failing(monkeypatch, "linux", 1)
    with pytest.raises(PermissionError):
        _platform.replace_file(source, target)
    assert calls == ["replace"]


@pytest.mark.skipif(sys.platform == "win32", reason="the POSIX calls are checked on POSIX")
def test_e_posix_calls_are_the_callers_former_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fcntl  # noqa: PLC0415
    import signal  # noqa: PLC0415

    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(_platform.fcntl, "flock", lambda *a: calls.append(("flock", *a)))
    monkeypatch.setattr(_platform.os, "killpg", lambda *a: calls.append(("killpg", *a)))
    monkeypatch.setattr(_platform.os, "setpgid", lambda *a: calls.append(("setpgid", *a)))
    path = tmp_path / "e.lock"
    path.write_bytes(b"")
    handle = _open(path)
    lock_exclusive(handle)
    release_lock(handle)
    release_lock_file(handle, path)
    assert not path.exists()
    assert _platform.kill_process_tree(4321) is True
    isolate_process_tree()
    assert calls == [
        ("flock", handle, fcntl.LOCK_EX | fcntl.LOCK_NB),
        ("flock", handle, fcntl.LOCK_UN),
        ("flock", handle, fcntl.LOCK_UN),
        ("killpg", 4321, signal.SIGKILL),
        ("setpgid", 0, 0),
    ]
    assert os.RTLD_NOLOAD | os.RTLD_LAZY == _platform.LOADED_LIBRARY_MODE
