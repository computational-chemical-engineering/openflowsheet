"""Timing, memory and environment records (specification §7)."""

from __future__ import annotations

import platform
import resource
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


@contextmanager
def timed(sink: dict[str, float], key: str) -> Iterator[None]:
    """Record the wall-clock duration of the block under `key`, in milliseconds."""
    start = time.perf_counter_ns()
    try:
        yield
    finally:
        sink[key] = (time.perf_counter_ns() - start) / 1e6


def repeat_microseconds(call: Callable[[], Any], repetitions: int, warmup: int) -> dict[str, float]:
    """Call `call` and report the median and minimum duration in microseconds."""
    for _ in range(warmup):
        call()
    samples: list[float] = []
    for _ in range(repetitions):
        start = time.perf_counter_ns()
        call()
        samples.append((time.perf_counter_ns() - start) / 1e3)
    samples.sort()
    return {
        "median_us": samples[len(samples) // 2],
        "min_us": samples[0],
        "repetitions": float(repetitions),
    }


def measure_memory() -> float:
    """Maximum resident set size of this process, in MiB."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(__file__).resolve().parents[3],
        )
        return result.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def environment_record(backend: str, backend_version: str, extra: dict[str, Any]) -> dict[str, Any]:
    """The environment block written next to every result set (specification §7)."""
    import numpy

    return {
        "backend": backend,
        "backend_version": backend_version,
        "numpy_version": numpy.__version__,
        "python_version": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "cpu_model": _cpu_model(),
        "git_commit": _git_commit(),
        "recorded_at_unix": time.time(),
        **extra,
    }
