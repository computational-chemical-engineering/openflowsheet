"""Staged import and memory probe for the CasADi route (specification §7, M01 and M06).

Run as its own process. The harness imports CasADi at module scope, so the backend's import cost
and its resident-memory delta cannot be measured from inside it: by the time any harness function
runs, the import has already happened. This probe imports in stages and reports each point.
"""

from __future__ import annotations

import json
import resource
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def rss_mib() -> float:
    """Current resident set size in MiB.

    `getrusage(...).ru_maxrss` is a high-water mark that this process can inherit from the parent
    it was spawned from: measured, a probe spawned by the harness reported the parent's 52.4 MiB
    at every stage, while the same probe run directly reported 24.8, 34.4 and 47.4. The current
    figure from /proc is not affected, so the staged points use it and the peak is reported
    separately.
    """
    try:
        with Path("/proc/self/status").open(encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / 1024.0
    except OSError:
        pass
    return peak_rss_mib()


def peak_rss_mib() -> float:
    """Peak resident set size in MiB, as the kernel accounts it for this process."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> int:
    start = time.perf_counter_ns()
    import numpy  # noqa: F401, PLC0415

    numpy_import_ms = (time.perf_counter_ns() - start) / 1e6
    rss_after_numpy = rss_mib()

    start = time.perf_counter_ns()
    import casadi  # noqa: PLC0415

    backend_import_ms = (time.perf_counter_ns() - start) / 1e6
    rss_after_backend = rss_mib()

    from spikes.p02.casadi.harness import compile_form  # noqa: PLC0415
    from spikes.p02.common import CounterSet, load_states  # noqa: PLC0415

    state = load_states()["S1"]
    tracemalloc.start()
    start = time.perf_counter_ns()
    compile_form("L", state, CounterSet())
    compile_ms = (time.perf_counter_ns() - start) / 1e6
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(
        json.dumps(
            {
                "backend": "casadi",
                "backend_version": casadi.__version__,
                "numpy_import_ms": numpy_import_ms,
                "backend_import_ms": backend_import_ms,
                "compile_L_ms": compile_ms,
                "rss_after_numpy_mib": rss_after_numpy,
                "rss_after_backend_import_mib": rss_after_backend,
                "rss_after_compile_mib": rss_mib(),
                "peak_rss_mib": peak_rss_mib(),
                "tracemalloc_peak_compile_mib": peak / (1024 * 1024),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
