"""S10-C WO-R1 (R-782): which solves have an *acting* iteration — an observation-only pytest plugin.

`docs/derivations/S10C-absent-component.md` §4.4 calls iteration `k` of a Newton attempt **acting**
when `α_max(d_k) > 0` and the largest released set `Z*(x_k)` (K03 §5.3 as amended, R-064) meets
the direction's support. The inertness theorem says the solves R-782 moves are exactly the solves
with an acting iteration on the *pre-change* code, so this plugin is run on the pre-change tree to
name them (the set D of §4.6), and the identity gate then checks *moved ⊆ D*.

At configure time the plugin wraps `openflowsheet.numerics.newton._bound_aware_step`. The wrapper
returns the wrapped function's result unchanged. For each call with `α_max > 0` it evaluates the
acting predicate with the module's own `_bound_aware_alpha` and `_released` (captured at configure
time, so that a test that spies on `newton._released` does not see the detector's calls), in the
order §4.5 fixes: the mask `C` first, `_released` only when `C ≠ ∅`.

Each acting iteration is one JSON line (`test` from `PYTEST_CURRENT_TEST`, `n`, `released` =
`|Z*|`, `acting` = `|Z* ∩ supp(d)|`, `dmax` = the largest direction entry there) in
`$S10C_RELEASE_EVENTS/<pid>.jsonl`; at session finish the process writes its counters to
`<pid>.summary.json` and prints

    DETECTOR acting_tests=<N> acting_iterations=<M> released_calls=<K>

Usage (repository root; `scripts` on `sys.path`):

    S10C_RELEASE_EVENTS=DIR PYTHONPATH=src:.:scripts pytest -p s10c_release_detector [args]
    python scripts/s10c_release_detector.py summarize DIR   # one line over every process in DIR

`summarize` prints the same `DETECTOR` line over all processes, then one line per acting test.
Without `S10C_RELEASE_EVENTS` the plugin counts and prints but writes nothing.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ENVIRONMENT = "S10C_RELEASE_EVENTS"

_counts = {"released_calls": 0, "acting_iterations": 0}
_acting_tests: set[str] = set()


def _current_test() -> str:
    """The pytest node id without its ` (call)`/` (setup)` phase suffix."""
    return os.environ.get("PYTEST_CURRENT_TEST", "").rsplit(" (", 1)[0]


def _write(name: str, text: str) -> None:
    directory = os.environ.get(ENVIRONMENT)
    if not directory:
        return
    Path(directory).mkdir(parents=True, exist_ok=True)
    with open(Path(directory) / name, "a", encoding="utf-8") as sink:
        sink.write(text)


def install() -> None:
    """Wrap `newton._bound_aware_step` observation-only (idempotent)."""
    import numpy as np

    from openflowsheet.numerics import newton

    if getattr(newton._bound_aware_step, "_s10c_detector", False):
        return
    wrapped = newton._bound_aware_step
    alpha_of = newton._bound_aware_alpha
    released_of = newton._released

    def observed(x: Any, direction: Any, lower: Any, **keywords: Any) -> Any:
        alpha_max, _ = alpha_of(x, direction, lower)
        if alpha_max > 0.0:
            opening = keywords["opening"]
            on_bound = np.isfinite(lower) & (x == lower) & (opening == lower) & (direction != 0.0)
            if np.any(on_bound):
                released = released_of(
                    x, opening, lower, keywords["residual"], keywords["jacobian"]
                )
                _counts["released_calls"] += 1
                acting = [index for index in released if direction[index] != 0.0]
                if acting:
                    _counts["acting_iterations"] += 1
                    test = _current_test() or " ".join(sys.argv[:3])
                    _acting_tests.add(test)
                    record = {
                        "test": test,
                        "n": int(x.size),
                        "released": len(released),
                        "acting": len(acting),
                        "dmax": float(max(direction[index] for index in acting)),
                    }
                    _write(f"{os.getpid()}.jsonl", json.dumps(record) + "\n")
        return wrapped(x, direction, lower, **keywords)

    observed._s10c_detector = True  # type: ignore[attr-defined]
    newton._bound_aware_step = observed


def _line(tests: int, iterations: int, calls: int) -> str:
    return f"DETECTOR acting_tests={tests} acting_iterations={iterations} released_calls={calls}"


def pytest_configure(config: Any) -> None:
    install()


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    summary = {**_counts, "acting_tests": sorted(_acting_tests)}
    _write(f"{os.getpid()}.summary.json", json.dumps(summary) + "\n")
    print("\n" + _line(len(_acting_tests), _counts["acting_iterations"], _counts["released_calls"]))


def summarize(directory: Path) -> int:
    """The `DETECTOR` line over every process's summary in `directory`, then the acting tests."""
    calls = iterations = 0
    for path in sorted(directory.glob("*.summary.json")):
        for text in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(text)
            calls += entry["released_calls"]
            iterations += entry["acting_iterations"]
    per_test: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(directory.glob("*.jsonl")):
        for text in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(text)
            per_test[event["test"]].append(event)
    print(_line(len(per_test), iterations, calls))
    for test, events in sorted(per_test.items()):
        sizes = sorted({event["released"] for event in events})
        dmax = max(event["dmax"] for event in events)
        print(f"  {test} | iterations {len(events)} | |Z*| {sizes} | max d {dmax:.3e}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "summarize":
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(summarize(Path(sys.argv[2])))
