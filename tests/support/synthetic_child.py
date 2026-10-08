"""A synthetic external child for the default gate (M02 design note §2.3, WO-3; ADR 0033).

Run as `python -I synthetic_child.py [--handshake]` by `adapters.external.launcher`, with the
project's own interpreter, in place of the pinned reactor's child. It speaks the same protocol —
one JSON request line on stdin, stdin held as the lifeline, a self-deadline, one atomically written
`result.json`, the registered exit codes — and imports the standard library only, so `-I` keeps
this repository out of it exactly as it keeps it out of the real child. The protocol's constants
are literals here, mirrored from `adapters/external/protocol.py`; a test asserts they are equal.

Its "reactor" is the stand-in's closed form per tube (ξ = 0.25 F y_N2, T_out = T_in, M01 spec
§8.13), so an out-of-process attempt through this child answers what the in-process stand-in
answers. `configuration.hooks` (a list, applied in order) reaches every failure path:

- `ok` — nothing; `sleep(s)` — sleep s seconds; `ignore_sigterm` — ignore SIGTERM;
- `abort` — `os.abort()` (SIGABRT, a crash); `abort_first` — the same, on the first run under
  an environment root only; `exit(code)` — `os._exit(code)`;
- `bad_json` — write a `result.json` that is not JSON and exit 0;
- `wrong_hash` — answer with another request's `request_sha256`;
- `fingerprint(alt)` — an evaluation reports another interpreter in its fingerprint;
- `nondeterministic` — each run's outlet temperature differs by one more ulp (a counter beside
  the environment root);
- `not_accepted(stage)` — answer `not_accepted` at `stage`.

A hook acts on evaluations only; `handshake:<hook>` acts on the handshake only (`--handshake`).

`configuration.pressure_drop` (Pa, default 0.0) is the tube's reported drop. Before exiting 70 or
71 the child writes `exit-<code>.json` (`{code, monotonic}`) in its working directory, so a test
can see a lifeline exit it is not the parent of, and when.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

PROTOCOL_VERSION = 1
EXIT_LIFELINE_LOST = 70
EXIT_SELF_DEADLINE = 71
EXIT_ENVIRONMENT_MISMATCH = 72
RESULT_FILE = "result.json"
RESULT_TEMPORARY = "result.json.tmp"
HANDSHAKE_ARGUMENT = "--handshake"
OUTCOME_OUTLET = "outlet"
OUTCOME_NOT_ACCEPTED = "not_accepted"
OUTCOME_HANDSHAKE = "handshake"
SELF_DEADLINE_MARGIN_S = 30.0
DEADLINE_MARGIN_VARIABLE = "OFS_TEST_DEADLINE_MARGIN_S"

NU = (-3, -1, 2, 0, 0)
CONVERSION = 0.25
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMBA_NUM_THREADS",
)
CHEAP = ("python", "packages", "cpu_model", "thread_env", "runner_sha256", "export_tree_sha256")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exit(code: int) -> None:
    """Leave now with `code`, after leaving a marker a non-parent can read."""
    try:
        marker = Path.cwd() / f"exit-{code}.json"
        marker.write_text(json.dumps({"code": code, "monotonic": time.monotonic()}))
    finally:
        os._exit(code)


def _lifeline() -> None:
    sys.stdin.buffer.read()  # blocks until the worker closes stdin, or dies
    _exit(EXIT_LIFELINE_LOST)


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _fingerprint(expected: dict[str, object], runner: str) -> dict[str, object]:
    attempt = os.getcwd()
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": _cpu_model(),
        "cpu_flags_sha256": hashlib.sha256(b"synthetic").hexdigest(),
        "packages": {},
        "thread_env": {name: os.environ.get(name) for name in THREAD_VARIABLES},
        "env_allowlist": {
            name: value.replace(attempt, "${ATTEMPT_DIR}")
            for name, value in sorted(os.environ.items())
        },
        "export_tree_sha256": expected.get("export_tree_sha256"),
        "merged_database_sha256": expected.get("merged_database_sha256"),
        "lock_sha256": expected.get("lock_sha256"),
        "runner_sha256": runner,
    }


def _write(document: dict[str, object] | str) -> None:
    temporary = Path(RESULT_TEMPORARY)
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(document if isinstance(document, str) else json.dumps(document))
        handle.flush()
        os.fsync(handle.fileno())
    os.rename(temporary, RESULT_FILE)


def _counter() -> int:
    path = Path(os.environ["NUMBA_CACHE_DIR"]).parent / "synthetic-counter"
    count = int(path.read_text()) + 1 if path.is_file() else 1
    path.write_text(str(count))
    return count


def main() -> None:
    started = time.monotonic()
    request = json.loads(sys.stdin.buffer.readline())
    threading.Thread(target=_lifeline, daemon=True).start()
    margin = float(os.environ.get(DEADLINE_MARGIN_VARIABLE, SELF_DEADLINE_MARGIN_S))
    deadline = threading.Timer(
        float(request["deadline_s"]) + margin, _exit, args=(EXIT_SELF_DEADLINE,)
    )
    deadline.daemon = True
    deadline.start()

    runner = _sha256(Path(__file__))
    expected = request.get("expected", {})
    if expected.get("runner_sha256") != runner:
        sys.stderr.write(
            f"runner_sha256 {runner} is not the expected {expected.get('runner_sha256')}\n"
        )
        sys.stderr.flush()
        os._exit(EXIT_ENVIRONMENT_MISMATCH)

    configuration = request.get("configuration", {})
    hooks = list(configuration.get("hooks", []))
    full = _fingerprint(expected, runner)
    cheap = {name: full[name] for name in CHEAP}
    digest = request["request_sha256"]
    stage = None
    handshake = HANDSHAKE_ARGUMENT in sys.argv
    for hook in hooks:
        # A hook acts on evaluations; `handshake:<hook>` on the handshake only.
        if hook.startswith("handshake:") != handshake:
            continue
        parsed = re.fullmatch(r"([a-z_]+)(?:\((.*)\))?", hook.removeprefix("handshake:"))
        assert parsed is not None, hook
        name, argument = parsed.groups("")
        if name == "sleep":
            time.sleep(float(argument))
        elif name == "ignore_sigterm":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        elif name == "abort":
            os.abort()
        elif name == "abort_first":
            marker = Path(os.environ["NUMBA_CACHE_DIR"]).parent / "aborted-once"
            if not marker.exists():
                marker.write_text("1")
                os.abort()
        elif name == "exit":
            os._exit(int(argument))
        elif name == "bad_json":
            _write("{this is not json")
            os._exit(0)
        elif name == "wrong_hash":
            digest = "0" * 64
        elif name == "fingerprint":
            cheap = {**cheap, "python": f"{argument}-{cheap['python']}"}
        elif name == "not_accepted":
            stage = argument
    solve_started = time.monotonic()
    timing = {"startup_s": solve_started - started}
    if HANDSHAKE_ARGUMENT in sys.argv:
        document: dict[str, object] = {"outcome": OUTCOME_HANDSHAKE, "fingerprint": full}
    elif stage is not None:
        document = {"outcome": OUTCOME_NOT_ACCEPTED, "stage": stage, "fingerprint": cheap}
    else:
        tube = request["tube_inlet"]
        feed = [tube["flow"] * y for y in tube["composition"]]
        xi = CONVERSION * feed[1]
        flows = [feed[i] + NU[i] * xi for i in range(len(NU))]
        temperature = tube["temperature"]
        if "nondeterministic" in hooks:
            for _ in range(_counter()):
                temperature = math.nextafter(temperature, math.inf)
        document = {
            "outcome": OUTCOME_OUTLET,
            "tube_outlet": {
                "flows": flows,
                "temperature": temperature,
                "pressure_drop": float(configuration.get("pressure_drop", 0.0)),
                "coolant_heat": None,
                "inlet_face_heat_loss": None,
            },
            "diagnostics": {"synthetic": True},
            "fingerprint": cheap,
        }
    timing["solve_s"] = time.monotonic() - solve_started
    _write({"protocol": PROTOCOL_VERSION, "request_sha256": digest, **document, "timing": timing})
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Every exit is `os._exit`: a normal interpreter exit with the lifeline thread blocked in
        # stdin's buffered read is a fatal error (SIGABRT), which would read as a crash of the
        # model rather than of the child's own code.
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
