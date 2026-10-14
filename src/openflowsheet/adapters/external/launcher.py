"""The launcher: one external attempt as one child process, and the kill chain's adapter-owned
layer (M02 design note §2.3, ADR 0033 D1, D2).

`launch` runs one child — an interpreter in isolated mode (`-I`) on one script — in a private
working directory (the attempt directory), with a scrubbed environment (an allowlist, never
inheritance), its stdout and stderr in files (never pipes, so no pipe-buffer deadlock), and the
request as one JSON line on stdin. **Stdin stays open for the whole attempt: it is the child's
lifeline** (layer L3); the child exits on its end of file and at its own deadline.

**Layer L1 (this module).** The launcher polls the child every `POLL_S` (0.2 s); between polls it
calls the job's cooperative check (the `INTERRUPT_CHECK` installed by `application.jobs.interrupt`,
ADR 0020 D3) and then its own per-attempt deadline. On a timeout or an interrupt it sends SIGTERM,
waits `kill_grace_s` (2.0 s), sends SIGKILL, and reaps. A timeout is returned as `timed_out`; an
interrupt propagates after the child is reaped (the caller records the attempt `cancelled` on its
way out). Layer L2 — the executor's forced kill of the worker's whole process group — needs the
child to stay in the worker's group, so the child is never given a session of its own.

**Exit mapping (§2.3 step 9).** Exit 0 with a valid `result.json` whose `request_sha256` is the
request's → `completed` with the document; exit 0 otherwise → `protocol_error`; 70 and 71 (the
child's lifeline and self-deadline, seen only if this launcher survived them) → `protocol_error`;
72 → `environment_mismatch` with the child's one line of reason; a signal or any other code →
`crashed`. A spawn the operating system refuses → `spawn_failed`; an absent environment root or a
Windows host → `environment_unavailable`, without a spawn.

**Isolation profile `external-subprocess-v1`.** It provides a separate interpreter and address
space, an environment allowlist, a private working directory, one thread, a wall-clock limit with
TERM→KILL escalation, termination on cooperative cancel, on a forced kill of the worker and on the
worker's death, output read from one validated file. It provides **no** filesystem confinement,
network isolation, memory or CPU quota, or syscall filtering: **it is not a sandbox**, and trust
rests on the provenance of the pinned code. Linux is registered; macOS is best effort (the same
mechanisms); Windows is refused before spawn.
"""

from __future__ import annotations

import json
import math
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from openflowsheet.adapters.external.protocol import (
    EXIT_ENVIRONMENT_MISMATCH,
    EXIT_LIFELINE_LOST,
    EXIT_OK,
    EXIT_SELF_DEADLINE,
    HANDSHAKE_ARGUMENT,
    KILL_GRACE_S,
    OUTCOME_HANDSHAKE,
    OUTCOME_NOT_ACCEPTED,
    OUTCOME_OUTLET,
    POLL_S,
    PROTOCOL_VERSION,
    RESULT_FILE,
    STDERR_FILE,
    STDOUT_FILE,
)
from openflowsheet.canonical import document_sha256, file_sha256, first_noncanonical
from openflowsheet.orchestrator.trace import INTERRUPT_CHECK

__all__ = [
    "ChildProgram",
    "LaunchProgress",
    "LaunchResult",
    "LaunchStatus",
    "Limits",
    "UNSUPPORTED_PLATFORM",
    "launch",
    "scrubbed_environment",
]

LaunchStatus = Literal[
    "completed",
    "timed_out",
    "crashed",
    "protocol_error",
    "spawn_failed",
    "environment_unavailable",
    "environment_mismatch",
]
#: §2.3: the message of a refusal on a platform the profile does not register.
UNSUPPORTED_PLATFORM: Final = "external_execution_unsupported_platform"
#: The child's own message on stderr is carried at most this long into the attempt record.
_MESSAGE_LIMIT: Final = 1024


@dataclass(frozen=True)
class ChildProgram:
    """What an attempt runs: an interpreter, a script, and the environment root its caches live
    under (`NUMBA_CACHE_DIR = <root>/numba-cache`). An absent root is `environment_unavailable`."""

    python: Path
    script: Path
    environment_root: Path


@dataclass(frozen=True)
class Limits:
    """One attempt's wall-clock limit and the TERM→KILL grace (the variant's `execution`)."""

    timeout_s: float
    kill_grace_s: float = KILL_GRACE_S

    def __post_init__(self) -> None:
        for name in ("timeout_s", "kill_grace_s"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0.0):
                raise ValueError(f"{name} = {value!r} must be a positive finite number")


@dataclass
class LaunchProgress:
    """What is known about an attempt so far, filled in as it runs. A caller reads it after an
    interrupt propagated out of `launch`, to record the attempt it ended."""

    pid: int | None = None
    exit_code: int | None = None
    signal: int | None = None
    wall_s: float | None = None
    #: Why the launcher terminated the child, if it did: `timeout` or `interrupt`.
    terminated: str | None = None
    logs: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class LaunchResult:
    """An attempt's end: its status, the child's exit, the validated `result.json` (`completed`
    only), the logs' hashes and relative paths, and the wall time from spawn to reap."""

    status: LaunchStatus
    exit_code: int | None
    signal: int | None
    message: str
    document: Mapping[str, Any] | None = None
    logs: Mapping[str, Any] | None = None
    wall_s: float | None = None
    pid: int | None = None
    timing: Mapping[str, Any] = field(default_factory=dict)


def scrubbed_environment(
    attempt_dir: Path, environment_root: Path, extra: Mapping[str, str] | None = None
) -> dict[str, str]:
    """§2.3 step 2: the child's whole environment, an allowlist. A user's `NUMBA_*`, `OMP_*` or
    `PYTHON*` never reaches the child; `extra` is the launcher's test-only addition."""
    environment = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "HOME": str(attempt_dir),
        "TMPDIR": str(attempt_dir),
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMBA_NUM_THREADS": "1",
        "NUMBA_CACHE_DIR": str(environment_root / "numba-cache"),
        "OFS_PROTOCOL": str(PROTOCOL_VERSION),
    }
    if extra:
        environment.update(extra)
    return environment


def request_line(request: Mapping[str, Any]) -> tuple[bytes, str]:
    """The stdin line for `request` and its `request_sha256` (the `document_sha256` of the line's
    document without that member). Floats are written by `repr`, an exact round trip; a
    non-finite number is refused here, before any spawn."""
    payload = {"protocol": PROTOCOL_VERSION, **request}
    pointer = first_noncanonical(payload)
    if pointer is not None:
        raise ValueError(f"a child request must be canonical JSON; not at {pointer!r}")
    digest = document_sha256(payload)
    line = json.dumps({**payload, "request_sha256": digest}, allow_nan=False) + "\n"
    return line.encode("utf-8"), digest


def _unavailable(message: str) -> LaunchResult:
    return LaunchResult("environment_unavailable", None, None, message)


def launch(
    program: ChildProgram,
    request: Mapping[str, Any],
    attempt_dir: Path,
    limits: Limits,
    *,
    handshake: bool = False,
    progress: LaunchProgress | None = None,
    on_spawn: Callable[[int], None] | None = None,
    check: Callable[[], None] | None = None,
    use_installed_check: bool = True,
    test_environment: Mapping[str, str] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> LaunchResult:
    """Run one attempt of `program` on `request` in `attempt_dir` (created; must be private to
    the attempt) under `limits`, and return how it ended.

    `check` is the cooperative check called between polls; by default the one installed in
    `INTERRUPT_CHECK` (none outside a job). `use_installed_check=False` with no `check` disables
    it (a worker test hook that ignores cancellation, gate G3 (d)). `on_spawn` sees the child's
    pid once it runs. `test_environment` is added to the scrubbed environment; no API reaches it.
    """
    if sys.platform == "win32":
        return _unavailable(f"{UNSUPPORTED_PLATFORM}: external-subprocess-v1 refuses Windows")
    if not program.environment_root.is_dir():
        return _unavailable(
            f"environment_unavailable: no environment at {program.environment_root}"
        )
    line, digest = request_line(request)
    if check is None and use_installed_check:
        check = INTERRUPT_CHECK.get()
    progress = progress if progress is not None else LaunchProgress()
    attempt_dir.mkdir(parents=True, exist_ok=True)
    command = [str(program.python), "-I", str(program.script)]
    if handshake:
        command.append(HANDSHAKE_ARGUMENT)
    environment = scrubbed_environment(attempt_dir, program.environment_root, test_environment)
    stdout_path = attempt_dir / STDOUT_FILE
    stderr_path = attempt_dir / STDERR_FILE
    with open(stdout_path, "wb") as stdout, open(stderr_path, "wb") as stderr:
        started = clock()
        try:
            # No `start_new_session`: the child stays in the worker's process group (L2).
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
                cwd=attempt_dir,
                env=environment,
                close_fds=True,
            )
        except OSError as error:  # FileNotFoundError, PermissionError, ENOEXEC, ...
            return LaunchResult("spawn_failed", None, None, f"spawn_failed: {error}")
        progress.pid = process.pid
        assert process.stdin is not None
        timed_out = False
        try:
            if on_spawn is not None:
                on_spawn(process.pid)
            try:
                process.stdin.write(line)
                process.stdin.flush()
            except BrokenPipeError:
                pass  # the child is already gone; its exit status says why
            deadline = started + limits.timeout_s
            while True:
                try:
                    process.wait(timeout=POLL_S)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if check is not None:
                    check()  # an interrupt propagates; `finally` terminates and reaps the child
                if clock() >= deadline:
                    timed_out = True
                    progress.terminated = "timeout"
                    _terminate(process, limits.kill_grace_s)
                    break
        finally:
            if process.returncode is None:
                progress.terminated = progress.terminated or "interrupt"
                _terminate(process, limits.kill_grace_s)
            # The lifeline is closed only once the child is reaped, so the exit status recorded
            # is the child's own answer or the launcher's signal, never the lifeline's.
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
            progress.wall_s = clock() - started
            progress.exit_code, progress.signal = _exit(process.returncode)
    logs = {
        "stdout_sha256": file_sha256(stdout_path),
        "stderr_sha256": file_sha256(stderr_path),
        "relpaths": {"stdout": STDOUT_FILE, "stderr": STDERR_FILE},
    }
    progress.logs = logs
    exit_code, signal_number = progress.exit_code, progress.signal

    def ended(status: LaunchStatus, message: str, **extra: Any) -> LaunchResult:
        return LaunchResult(
            status,
            exit_code,
            signal_number,
            message,
            logs=logs,
            wall_s=progress.wall_s,
            pid=process.pid,
            **extra,
        )

    if timed_out:
        return ended("timed_out", f"timed_out: no answer within {limits.timeout_s!r} s")
    if process.returncode == EXIT_OK:
        document, problem = _read_result(attempt_dir / RESULT_FILE, digest, handshake)
        if document is None:
            return ended("protocol_error", f"protocol_error: {problem}")
        timing = document.get("timing")
        return ended(
            "completed",
            "",
            document=document,
            timing=dict(timing) if isinstance(timing, Mapping) else {},
        )
    if process.returncode == EXIT_LIFELINE_LOST:
        return ended("protocol_error", "protocol_error: lifeline_lost (the child saw stdin close)")
    if process.returncode == EXIT_SELF_DEADLINE:
        return ended("protocol_error", "protocol_error: self_deadline (the child's own deadline)")
    if process.returncode == EXIT_ENVIRONMENT_MISMATCH:
        return ended("environment_mismatch", f"environment_mismatch: {_last_line(stderr_path)}")
    if signal_number is not None:
        return ended("crashed", f"crashed: killed by signal {signal_number}")
    return ended("crashed", f"crashed: exit code {exit_code}")


def _terminate(process: subprocess.Popen[bytes], grace_s: float) -> None:
    """SIGTERM, up to `grace_s` for the child to go, then SIGKILL; always reaps."""
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _exit(returncode: int | None) -> tuple[int | None, int | None]:
    """`(exit_code, signal)`: a negative return code is a signal (POSIX `Popen`)."""
    if returncode is None:
        return None, None
    if returncode < 0:
        return None, -returncode
    return returncode, None


def _read_result(path: Path, digest: str, handshake: bool) -> tuple[dict[str, Any] | None, str]:
    """The child's `result.json`, validated as the protocol's envelope, or the reason it is not.
    The payload's own shape (an outlet, a stage, a fingerprint) is the caller's to check."""
    if not path.is_file():
        return None, f"exit 0 without {RESULT_FILE}"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, f"{RESULT_FILE} is not JSON: {error}"
    if not isinstance(document, dict):
        return None, f"{RESULT_FILE} is not an object"
    if document.get("protocol") != PROTOCOL_VERSION:
        return None, f"{RESULT_FILE} protocol {document.get('protocol')!r}, not {PROTOCOL_VERSION}"
    if document.get("request_sha256") != digest:
        return None, f"{RESULT_FILE} answers another request ({document.get('request_sha256')!r})"
    expected = {OUTCOME_HANDSHAKE} if handshake else {OUTCOME_OUTLET, OUTCOME_NOT_ACCEPTED}
    if document.get("outcome") not in expected:
        return None, f"{RESULT_FILE} outcome {document.get('outcome')!r} not in {sorted(expected)}"
    if not isinstance(document.get("fingerprint"), dict):
        return None, f"{RESULT_FILE} carries no fingerprint object"
    return document, ""


def _last_line(path: Path) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    return lines[-1][:_MESSAGE_LIMIT] if lines else "(no reason on stderr)"
