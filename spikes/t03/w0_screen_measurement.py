"""T03 W0 (spec §17, Q1): K03 §8.2 at every trial of every single-phase attempt of T02 A21/A22.

Observes only: the region's per-attempt residual is wrapped to evaluate the admissibility value of
each single-phase lifted unit at each point Newton evaluates; nothing the solver computes changes.
The first value of an attempt is its opening state, which spec §4.3 exempts from the screen.

Usage: PYTHONPATH=src .venv/bin/python spikes/t03/w0_screen_measurement.py > out.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from typing import Any

sys.path.insert(0, "tests")

from test_t02_region import case, initializer, solve  # noqa: E402

import openflowsheet.orchestrator.region as region  # noqa: E402

CASES = ("SYN-001-nominal", "SYN-001-high-recycle", "SYN-001-all-liquid-310K")
EPSILON = 1e-12


def measure(case_id: str) -> dict[str, Any]:
    item = case(case_id)
    provider = item.flowsheet.provider
    attempts: list[dict[str, Any]] = []
    original = region._region_problem

    def wrapped(compiled, context, spec, scaling, base, free, rows):  # type: ignore[no-untyped-def]
        problem = original(compiled, context, spec, scaling, base, free, rows)
        free_set = set(free)
        single = [
            (split, "LIQUID" if split.vapor_total not in free_set else "VAPOR")
            for split in region.syn001_lifted_splits(item.flowsheet.components)
            if split.vapor_total not in free_set or split.liquid_total not in free_set
        ]
        record: dict[str, Any] = {"single": [f"{s.unit}:{r}" for s, r in single], "values": []}
        attempts.append(record)
        residual = problem.residual

        def screened(x):  # type: ignore[no-untyped-def]
            state = dict(base)
            state.update(zip(free, (float(v) for v in x), strict=True))
            out = residual(x)
            row: dict[str, Any] = {"status": out.status}
            for split, regime in single:
                _, value = region._admissible(provider, context, split, regime, state, EPSILON)
                row[f"{split.unit}:{regime}"] = value
            record["values"].append(row)
            return out

        return replace(problem, residual=screened)

    region._region_problem = wrapped
    try:
        result = solve(item, initializer(item))
    finally:
        region._region_problem = original
    screen = []
    for index, record in enumerate(attempts):
        for key in record["single"]:
            series = [row[key] for row in record["values"] if row["status"] == "ok"]
            opening, trials = series[0], series[1:]
            screen.append(
                {
                    "attempt": index,
                    "unit": key,
                    "opening": opening,
                    "n_trials": len(trials),
                    "worst_trial": max(trials) if trials else None,
                    "exceeds": [value for value in trials if value > 1 + EPSILON],
                }
            )
    return {
        "outcome": result.outcome,
        "attempts": [
            (dict(attempt.signature), attempt.outcome, attempt.iterations)
            for attempt in result.attempts
        ],
        "screen": screen,
    }


if __name__ == "__main__":
    print(json.dumps({case_id: measure(case_id) for case_id in CASES}, indent=1))
