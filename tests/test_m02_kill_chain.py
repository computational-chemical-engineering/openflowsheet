"""M02 WO-3, gate G3 (design note §2.3, ADR 0033 D2): the launcher and the three-layer kill chain,
on Linux, with the synthetic child (`tests/support/synthetic_child.py`).

Every time bound is measured here on the monotonic clock, which is system-wide on Linux, so a
child's own exit marker (`exit-<code>.json`) and this process's clock compare directly:

- (a) a cooperative cancel (the real `interruptible` check, through `INTERRUPT_CHECK`) while the
  child sleeps 60 s: the child is reaped ≤ 3.0 s after the cancel is set, also when it ignores
  SIGTERM; the interrupt propagates after the reap and the progress says `interrupt`;
- (b) `timeout_s = 1` on a 60 s child: `timed_out` ≤ 3.5 s after spawn (SIGTERM);
- (c) a child ignoring SIGTERM is reaped ≤ 2.5 s after the TERM (SIGKILL);
- (d) the executor's forced kill (`grace_s = 0.5`, a worker that ignores the cooperative check by
  the `OPENFLOWSHEET_TEST_CHILD` hook): the worker and its child are gone ≤ 1.0 s after the kill;
- (e) the worker SIGKILLed alone by pid: the child exits 70 ≤ 2.0 s later (its lifeline);
- (f) the self-deadline, `deadline_s = 1` with a 1 s margin, lifeline held: exit 71 ≤ 3 s after
  spawn;
- (g) `abort` → `crashed` with the signal recorded (the retry is the runner's, WO-4);
- (h) after the module, no synthetic child of this checkout is alive.

Besides: the exit mapping of every other path (`bad_json`, `wrong_hash`, an exit code, an
environment mismatch, a spawn the OS refuses, an absent environment, Windows), the scrubbed
environment, the request line's refusal of a non-finite number, and the protocol's literals in the
child equal to `adapters/external/protocol.py`.
"""

from __future__ import annotations

import ast
import json
import os
import signal
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t07_jobs_support import commit
from t07_process_support import gone, set_executor, solve_request, wait_ended, wait_until

from openflowsheet.adapters.external import launcher, protocol
from openflowsheet.adapters.external.launcher import (
    ChildProgram,
    LaunchProgress,
    Limits,
    launch,
)
from openflowsheet.application.jobs.executor import ProcessExecutor
from openflowsheet.application.jobs.interrupt import JobInterrupted, interruptible
from openflowsheet.application.jobs.worker import (
    CHILD_ATTEMPT_DIR,
    CHILD_PID_FILE,
    CHILD_VARIABLE,
)
from openflowsheet.application.local import LocalApplication
from openflowsheet.canonical import file_sha256
from openflowsheet.models.c1 import NU

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="G3 is registered on Linux")

SYNTHETIC = REPO_ROOT / "tests" / "support" / "synthetic_child.py"
RUNNER = file_sha256(SYNTHETIC)
TUBE = {
    "flow": 0.007146961299302104,
    "composition": [0.6975, 0.2325, 0.03, 0.017142857142857144, 0.022857142857142857],
    "temperature": 673.15,
    "outlet_pressure": 1.0e7,
    "coolant_flow": 0.007146961299302104,
    "coolant_composition": [0.0, 1.0, 0.0, 0.0, 0.0],
    "coolant_temperature": 673.15,
    "coolant_outlet_pressure": 1.0e5,
}
#: Measured bounds (§10.1 G3), seconds.
BOUND_A, BOUND_B, BOUND_C, BOUND_D, BOUND_E, BOUND_F = 3.0, 3.5, 2.5, 1.0, 2.0, 3.0
GRACE_S = 0.5
MEASURED: dict[str, float] = {}


@pytest.fixture(scope="module", autouse=True)
def no_child_survives() -> Iterator[None]:
    """(h): after the module, no process runs this checkout's synthetic child."""
    yield
    deadline = time.monotonic() + 5.0
    while True:
        alive = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                command = (entry / "cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            if str(SYNTHETIC).encode() in command and not gone(int(entry.name)):
                alive.append(int(entry.name))
        if not alive or time.monotonic() > deadline:
            break
        time.sleep(0.1)
    assert alive == [], f"synthetic children survived the module: {alive}"
    print(f"\nG3 measured (s): {json.dumps(MEASURED, sort_keys=True)}")


def _program(tmp_path: Path) -> ChildProgram:
    root = tmp_path / "env"
    root.mkdir(exist_ok=True)
    return ChildProgram(Path(sys.executable), SYNTHETIC, root)


def _request(*hooks: str, deadline_s: float = 60.0, **configuration: Any) -> dict[str, Any]:
    return {
        "deadline_s": deadline_s,
        "expected": {"runner_sha256": RUNNER},
        "configuration": {"hooks": list(hooks), **configuration},
        "tube_inlet": TUBE,
    }


def _exit_marker(directory: Path, code: int, patience_s: float = 10.0) -> dict[str, Any]:
    path = directory / f"exit-{code}.json"
    wait_until(path.is_file, f"the child's exit-{code} marker", patience_s)
    time.sleep(0.05)  # written before os._exit; a reader may race the write
    marker: dict[str, Any] = json.loads(path.read_text())
    return marker


# -- the protocol and the happy path --------------------------------------------------------------


def _literals(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AnnAssign):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and node.value is not None:
                try:
                    found[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    continue
    return found


def test_the_childs_protocol_literals_are_the_protocols() -> None:
    names = (
        "PROTOCOL_VERSION",
        "EXIT_LIFELINE_LOST",
        "EXIT_SELF_DEADLINE",
        "EXIT_ENVIRONMENT_MISMATCH",
        "RESULT_FILE",
        "RESULT_TEMPORARY",
        "HANDSHAKE_ARGUMENT",
        "OUTCOME_OUTLET",
        "OUTCOME_NOT_ACCEPTED",
        "OUTCOME_HANDSHAKE",
        "SELF_DEADLINE_MARGIN_S",
        "DEADLINE_MARGIN_VARIABLE",
    )
    child = _literals(SYNTHETIC)
    for name in names:
        assert child[name] == getattr(protocol, name), name


def test_an_attempt_completes_with_the_standin_closed_form(tmp_path: Path) -> None:
    attempt = tmp_path / "attempt"
    result = launch(_program(tmp_path), _request("ok"), attempt, Limits(timeout_s=30.0))
    assert result.status == "completed" and result.exit_code == 0 and result.signal is None
    assert result.document is not None and result.document["outcome"] == "outlet"
    feed = [TUBE["flow"] * y for y in TUBE["composition"]]  # type: ignore[attr-defined]
    xi = 0.25 * feed[1]
    assert result.document["tube_outlet"]["flows"] == [feed[i] + NU[i] * xi for i in range(5)]
    assert result.document["tube_outlet"]["temperature"] == TUBE["temperature"]
    assert result.logs is not None
    assert result.logs["stdout_sha256"] == file_sha256(attempt / protocol.STDOUT_FILE)
    assert result.logs["relpaths"] == {"stdout": "child.stdout", "stderr": "child.stderr"}
    assert set(result.timing) == {"startup_s", "solve_s"}
    assert result.pid is not None and gone(result.pid)
    assert not (attempt / protocol.RESULT_TEMPORARY).exists()


def test_the_handshake_reports_the_scrubbed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NUMBA_DISABLE_JIT", "1")
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT / "src"))
    monkeypatch.setenv("OMP_NUM_THREADS", "8")
    program = _program(tmp_path)
    result = launch(program, _request(), tmp_path / "a", Limits(timeout_s=30.0), handshake=True)
    assert result.status == "completed" and result.document is not None
    fingerprint = result.document["fingerprint"]
    allowlist = fingerprint["env_allowlist"]
    assert allowlist == {
        "HOME": "${ATTEMPT_DIR}",
        "LANG": "C.UTF-8",
        "MKL_NUM_THREADS": "1",
        "NUMBA_CACHE_DIR": str(program.environment_root / "numba-cache"),
        "NUMBA_NUM_THREADS": "1",
        "OFS_PROTOCOL": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "PATH": "/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "TMPDIR": "${ATTEMPT_DIR}",
    }
    assert set(fingerprint["thread_env"].values()) == {"1"}
    assert fingerprint["runner_sha256"] == RUNNER


def test_every_other_exit_maps_as_registered(tmp_path: Path) -> None:
    program = _program(tmp_path)
    limits = Limits(timeout_s=30.0)
    cases = {
        "bad_json": ("protocol_error", "not JSON"),
        "wrong_hash": ("protocol_error", "answers another request"),
        "exit(3)": ("crashed", "exit code 3"),
        "exit(70)": ("protocol_error", "lifeline_lost"),
        "exit(71)": ("protocol_error", "self_deadline"),
        "exit(0)": ("protocol_error", "exit 0 without result.json"),
    }
    for hook, (status, fragment) in cases.items():
        result = launch(program, _request(hook), tmp_path / hook, limits)
        assert result.status == status and fragment in result.message, (hook, result)
        assert result.document is None
    mismatched = {**_request(), "expected": {"runner_sha256": "0" * 64}}
    result = launch(program, mismatched, tmp_path / "mismatch", limits)
    assert (result.status, result.exit_code) == ("environment_mismatch", 72)
    assert result.message.startswith("environment_mismatch: runner_sha256 ")


def test_refusals_before_any_spawn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    program = _program(tmp_path)
    limits = Limits(timeout_s=30.0)
    missing = ChildProgram(tmp_path / "no-python", SYNTHETIC, program.environment_root)
    result = launch(missing, _request(), tmp_path / "spawn", limits)
    assert result.status == "spawn_failed" and result.pid is None
    absent = ChildProgram(program.python, SYNTHETIC, tmp_path / "no-environment")
    result = launch(absent, _request(), tmp_path / "absent", limits)
    assert result.status == "environment_unavailable" and "no environment" in result.message
    with pytest.raises(ValueError, match="canonical"):
        launch(program, {**_request(), "deadline_s": float("nan")}, tmp_path / "nan", limits)
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    result = launch(program, _request(), tmp_path / "windows", limits)
    assert result.status == "environment_unavailable"
    assert result.message.startswith(launcher.UNSUPPORTED_PLATFORM)


# -- (a)-(c), (f), (g): layer L1 and the self-deadline ---------------------------------------------


@pytest.mark.parametrize("hooks", [("sleep(60)",), ("ignore_sigterm", "sleep(60)")])
def test_g3a_a_cooperative_cancel_reaps_the_child_and_propagates(
    tmp_path: Path, hooks: tuple[str, ...]
) -> None:
    cancel = threading.Event()
    set_at: list[float] = []
    progress = LaunchProgress()

    def cancel_soon(pid: int) -> None:
        def fire() -> None:
            set_at.append(time.monotonic())
            cancel.set()

        threading.Timer(1.1, fire).start()  # mid-poll: the worst phase

    with interruptible(cancel, None), pytest.raises(JobInterrupted) as raised:
        launch(
            _program(tmp_path),
            _request(*hooks),
            tmp_path / "a",
            Limits(timeout_s=60.0),
            progress=progress,
            on_spawn=cancel_soon,
        )
    elapsed = time.monotonic() - set_at[0]
    assert raised.value.reason == "cancel_requested"
    assert progress.pid is not None and gone(progress.pid)
    assert progress.terminated == "interrupt"
    expected = signal.SIGKILL if "ignore_sigterm" in hooks else signal.SIGTERM
    assert progress.signal == expected and progress.exit_code is None
    assert elapsed <= BOUND_A, elapsed
    MEASURED[f"a_{'kill' if 'ignore_sigterm' in hooks else 'term'}"] = round(elapsed, 3)


def test_g3b_a_timeout_ends_the_attempt_timed_out(tmp_path: Path) -> None:
    result = launch(_program(tmp_path), _request("sleep(60)"), tmp_path / "b", Limits(1.0))
    assert result.status == "timed_out" and result.signal == signal.SIGTERM
    assert result.wall_s is not None and 1.0 <= result.wall_s <= BOUND_B, result.wall_s
    MEASURED["b_timed_out_after_spawn"] = round(result.wall_s, 3)


def test_g3c_a_child_ignoring_sigterm_is_killed_after_the_grace(tmp_path: Path) -> None:
    result = launch(
        _program(tmp_path), _request("ignore_sigterm", "sleep(60)"), tmp_path / "c", Limits(1.0)
    )
    assert result.status == "timed_out" and result.signal == signal.SIGKILL
    assert result.wall_s is not None
    # The TERM is sent at the first poll past the 1 s deadline, so wall - 1 s bounds TERM → reap.
    after_term = result.wall_s - 1.0
    assert protocol.KILL_GRACE_S <= after_term <= BOUND_C, after_term
    MEASURED["c_after_term_upper"] = round(after_term, 3)


def test_g3f_the_self_deadline_exits_71(tmp_path: Path) -> None:
    attempt = tmp_path / "f"
    result = launch(
        _program(tmp_path),
        _request("sleep(60)", deadline_s=1.0),
        attempt,
        Limits(timeout_s=30.0),
        test_environment={protocol.DEADLINE_MARGIN_VARIABLE: "1"},
    )
    assert (result.status, result.exit_code) == ("protocol_error", 71)
    assert "self_deadline" in result.message
    assert result.wall_s is not None and 2.0 <= result.wall_s <= BOUND_F, result.wall_s
    assert _exit_marker(attempt, 71)["code"] == 71
    MEASURED["f_exit71_after_spawn"] = round(result.wall_s, 3)


def test_g3g_an_abort_is_a_crash_with_its_signal(tmp_path: Path) -> None:
    result = launch(_program(tmp_path), _request("abort"), tmp_path / "g", Limits(30.0))
    assert (result.status, result.signal, result.exit_code) == ("crashed", signal.SIGABRT, None)
    assert result.message == f"crashed: killed by signal {int(signal.SIGABRT)}"


# -- (d), (e): layers L2 and L3 through the process executor ---------------------------------------


@pytest.fixture
def child_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LocalApplication]:
    monkeypatch.setenv(CHILD_VARIABLE, str(SYNTHETIC))
    directory = tmp_path / "project"
    LocalApplication.create(directory).close()
    set_executor(directory, grace_s=GRACE_S)
    application = LocalApplication.open(directory, executor=ProcessExecutor(test_hooks=True))
    try:
        yield application
    finally:
        application.close()


def _running_with_child(app: LocalApplication, key: str) -> tuple[str, int, int, Path]:
    revision_id = commit(app, CORPUS["SYN-001-nominal"]())
    job = app.submit_job(solve_request(key, revision_id)).job
    assert app.store.directory is not None
    job_directory = app.store.directory / "jobs" / job.job_id
    pid_file = job_directory / CHILD_PID_FILE
    wait_until(pid_file.is_file, "the worker's child to spawn")
    time.sleep(0.05)
    worker_pid = app.executor.pid(job.job_id)  # type: ignore[union-attr]
    assert worker_pid is not None
    child_pid = int(pid_file.read_text())
    assert os.getpgid(worker_pid) == worker_pid  # L2: the worker leads its own group
    assert os.getpgid(child_pid) == worker_pid  # the child stays in it
    return job.job_id, worker_pid, child_pid, job_directory / CHILD_ATTEMPT_DIR


def _wait_gone(pid: int, patience_s: float = 10.0) -> float:
    deadline = time.monotonic() + patience_s
    while not gone(pid):
        assert time.monotonic() < deadline, f"process {pid} is still alive"
        time.sleep(0.005)
    return time.monotonic()


def test_g3d_the_executors_forced_kill_takes_the_worker_and_its_child(
    child_app: LocalApplication,
) -> None:
    job_id, worker_pid, child_pid, _ = _running_with_child(child_app, "forced")
    child_app.cancel_job(job_id)
    cancelled = time.monotonic()
    worker_gone = _wait_gone(worker_pid)
    child_gone = _wait_gone(child_pid)
    job = wait_ended(child_app, job_id)
    assert job.status == "cancelled" and job.ending is not None
    assert (job.ending.reason, job.ending.interruption) == ("cancel_requested", "forced")
    # The kill is due `grace_s` after the cancel (timed from inside `cancel_job`, at the next
    # 0.1 s supervisor poll): never before it, and both processes gone within the bound after it.
    elapsed = max(worker_gone, child_gone) - cancelled
    assert GRACE_S - 0.05 <= elapsed <= GRACE_S + BOUND_D, elapsed
    MEASURED["d_both_gone_after_cancel"] = round(elapsed, 3)


def test_g3e_a_worker_killed_alone_leaves_its_child_to_its_lifeline(
    child_app: LocalApplication,
) -> None:
    job_id, worker_pid, child_pid, attempt = _running_with_child(child_app, "orphaned")
    os.kill(worker_pid, signal.SIGKILL)
    killed = time.monotonic()
    marker = _exit_marker(attempt, protocol.EXIT_LIFELINE_LOST)
    _wait_gone(child_pid)
    assert marker["code"] == 70
    after_kill = marker["monotonic"] - killed
    assert 0.0 <= after_kill <= BOUND_E, after_kill
    job = wait_ended(child_app, job_id)
    assert job.ending is not None and job.ending.reason == "worker_lost"
    MEASURED["e_exit70_after_worker_kill"] = round(after_kill, 3)
