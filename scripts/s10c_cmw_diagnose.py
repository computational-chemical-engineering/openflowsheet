"""S10-C diagnostic: one `solve_column` on a registered Wilson column, its full attempt record.

Prints one compact JSON line for one solve of `C-MW` (or the case named on the command line):
the platform, the bubble-point sweeps (count, the last `max |ΔT|` and `max |Δx|`, the last few of
each), Stage A's region result and edge 3's recovery (every attempt's signature, outcome, solver
outcome, iterations, reason, observations), the homotopy record (λ reached, where it stalled, the
inferred cause, trials and rejections), every Newton call the region made (outcome, iterations,
residual ∞-norm, the variables `BOUND_BLOCKED` names with their values and lower bounds, and per
iteration the bound step: `α_max`, the landing variables, the released count and the absent
component's flows and direction), the accepted steps' residuals and `α`, Stage B's candidates,
and the answer with its worst deviation from the 50-digit root in tolerances (as
`tests/test_s10c_columns.py` measures it).

Observation only: the wrappers record arguments and results and change nothing the solve computes
(the answer's `final_sha256` is printed so a run with and without them can be compared). Written
for the aarch64 / x86-64 C-MW divergence (CI run 40275276182; `docs/S10C_DECISIONS.md`, "S10-C
diag"). Informative, not a gate.

Usage (repository root):
    PYTHONPATH=src:tests .venv/bin/python scripts/s10c_cmw_diagnose.py [C-MW|C-EW] [--dump F]

`--dump F` also writes the sweeps' start profile, `x_K`, `x⁰` and the answer's state to `F` as JSON
(floats `repr`-exact), for an ulp-level comparison of two machines' records.
"""

from __future__ import annotations

import json
import math
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import numpy as np  # noqa: E402
import scipy  # noqa: E402
from test_s10c_blocks import REAL, column_spec  # noqa: E402
from test_s10c_columns import deviations, worst  # noqa: E402

import openflowsheet.models.syn001.column_solve as column_solve  # noqa: E402
import openflowsheet.numerics.newton as newton_module  # noqa: E402
import openflowsheet.orchestrator.region as region  # noqa: E402
from openflowsheet.orchestrator.trace import Trace  # noqa: E402

#: How many of the last sweeps to print.
SWEEP_TAIL = 6


def _f(value: float | None) -> float | str | None:
    """A float as JSON can carry it (`repr`-exact through `json`), non-finite as a string."""
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else repr(value)


def _signature(signature: Sequence[tuple[str, Any]]) -> str:
    """An attempt signature as one letter per item in order (T = TWO_PHASE, L = LIQUID,
    V = VAPOR, ...), items being the column's equilibrium stages top to bottom."""
    return "".join(str(phases)[0] for _, phases in signature)


def _attempts(result: Any) -> list[dict[str, Any]] | None:
    if result is None:
        return None
    return [
        {
            "signature": _signature(a.signature),
            "outcome": a.outcome,
            "solver_outcome": a.solver_outcome,
            "iterations": a.iterations,
            "reason": a.reason,
            "observations": {k: _f(v) for k, v in a.observations.items()},
        }
        for a in result.attempts
    ]


def _homotopy(result: Any) -> dict[str, Any] | None:
    record = None if result is None else result.homotopy
    if record is None:
        return None
    return {
        "lambda_reached": str(record.lambda_reached),
        "stalled_at": record.stalled_at,
        "inferred_cause": record.inferred_cause,
        "trials": len(record.trials),
        "rejected": record.rejected_trials,
        "levels": [str(level) for level in record.lambda_levels],
    }


def _region(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "outcome": result.outcome,
        "message": result.message,
        "budget": result.budget,
        "iterations": result.iterations,
        "attempts": _attempts(result),
        "homotopy": _homotopy(result),
    }


class Recorder:
    """Wraps `sweep_flows`, `relaxed_compositions`, the region's `solve_newton` and Newton's
    `_bound_aware_step`; records. `absent` is the component whose feed flow is exactly zero (its
    column ids end `.<absent>`), whose flows each bound step summarises."""

    def __init__(self, absent: str | None) -> None:
        self.absent = absent
        self.temperatures: list[dict[int, float]] = []
        self.changes: list[float] = []
        self.newton: list[dict[str, Any]] = []
        self._ids: tuple[str, ...] = ()
        self._steps: list[dict[str, Any]] = []

    def _bound_step(self, x: Any, direction: Any, found: Any) -> dict[str, Any]:
        """One `_bound_aware_step`: `α_max`, the landing (or blocking) ids, the released count,
        and over the absent component's columns: how many are `> 0`, `== 0`, the largest value,
        the largest `|d|`, and how many have `d < 0` while `x + d < 0` (would cross zero)."""
        _, alpha, landing, released = found
        ids = self._ids
        cols = [k for k, name in enumerate(ids) if self.absent and name.endswith("." + self.absent)]
        xa, da = np.asarray(x)[cols], np.asarray(direction)[cols]
        return {
            "alpha_max": _f(alpha),
            "landing": [ids[k] for k in landing][:4],
            "landing_count": len(landing),
            "released": len(released),
            "absent_pos": int(np.sum(xa > 0.0)),
            "absent_zero": int(np.sum(xa == 0.0)),
            "absent_max_x": _f(float(np.max(xa))) if cols else None,
            "absent_max_d": _f(float(np.max(np.abs(da)))) if cols else None,
            "absent_crossing": int(np.sum((da < 0.0) & (xa + da < 0.0))),
        }

    def install(self) -> Callable[[], None]:
        sweep_flows = column_solve.sweep_flows
        relaxed = column_solve.relaxed_compositions
        newton = region.solve_newton
        bound_step = newton_module._bound_aware_step

        def bound_spy(x: Any, direction: Any, *a: Any, **kw: Any) -> Any:
            found = bound_step(x, direction, *a, **kw)
            self._steps.append(self._bound_step(x, direction, found))
            return found

        def sweep_spy(spec: Any, provider: Any, temperatures: Mapping[int, float], *a: Any) -> Any:
            self.temperatures.append(dict(temperatures))
            return sweep_flows(spec, provider, temperatures, *a)

        def relaxed_spy(*a: Any) -> Any:
            found = relaxed(*a)
            self.changes.append(found[1])
            return found

        def newton_spy(problem: Any, x0: Any, policy: Any, **kw: Any) -> Any:
            self._ids, self._steps = tuple(problem.variable_ids), []
            found = newton(problem, x0, policy, **kw)
            ids = problem.variable_ids
            index = {name: k for k, name in enumerate(ids)}
            self.newton.append(
                {
                    "attempt": kw.get("attempt"),
                    "signature": _signature(kw.get("signature") or ()),
                    "outcome": found.outcome,
                    "iterations": found.iterations,
                    "residual_inf": _f(found.residual_inf),
                    "blocked_by": [
                        {
                            "id": name,
                            "value": _f(found.x[index[name]]),
                            "lower": _f(problem.lower_bounds.get(name)),
                        }
                        for name in found.blocked_by
                    ],
                    "free": len(ids),
                    "steps": self._steps,
                }
            )
            return found

        spies = [
            (column_solve, "sweep_flows", sweep_flows, sweep_spy),
            (column_solve, "relaxed_compositions", relaxed, relaxed_spy),
            (region, "solve_newton", newton, newton_spy),
            (newton_module, "_bound_aware_step", bound_step, bound_spy),
        ]
        for module, name, _, spy in spies:
            setattr(module, name, spy)

        def restore() -> None:
            for module, name, original, _ in spies:
                setattr(module, name, original)

        return restore

    def sweep_deltas(self) -> list[float]:
        """`max_j |ΔT_j|` of each sweep: consecutive `sweep_flows` temperature arguments."""
        out = []
        for a, b in zip(self.temperatures, self.temperatures[1:], strict=False):
            out.append(max(abs(b[j] - a[j]) for j in a))
        return out


def _residuals(trace: Trace) -> dict[str, list[list[float | str | None]]]:
    """The accepted steps' `[residual ∞-norm, α]`, by attempt (Stage A, recovery, Stage B in
    trace order, keyed `"<n>:<attempt>"` with `n` counting the attempt-0 openings)."""
    out: dict[str, list[list[float | str | None]]] = {}
    run, previous = 0, None
    for event in trace.events:
        if event.kind == "attempt_opened":
            if previous is not None and event.attempt == 0:
                run += 1
            previous = event.attempt
        if event.kind == "step_accepted":
            out.setdefault(f"{run}:{event.attempt}", []).append(
                [_f(event.residual_inf_unscaled), _f(event.alpha)]
            )
    return out


def diagnose(case: str = "C-MW", dump: Path | None = None) -> dict[str, Any]:
    spec = column_spec(case)
    (feed,) = spec.sides
    gone = [c for c, a in zip(spec.components, feed.state.n, strict=True) if float(a) == 0.0]
    recorder = Recorder(gone[0] if gone else None)
    restore = recorder.install()
    trace = Trace()
    try:
        found = column_solve.solve_column(spec, REAL, trace=trace)
    finally:
        restore()
    record: dict[str, Any] = {
        "case": case,
        "machine": platform.machine(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "answer": type(found).__name__,
        "outcome": getattr(found, "outcome", None),
        "cause": getattr(found, "cause", None),
    }
    deltas = recorder.sweep_deltas()
    record["sweeps"] = {
        "count": len(recorder.changes),
        "flows_calls": len(recorder.temperatures),
        "dT_tail": [_f(d) for d in deltas[-SWEEP_TAIL:]],
        "dx_tail": [_f(c) for c in recorder.changes[-SWEEP_TAIL:]],
    }
    if isinstance(found, column_solve.ColumnSolution):
        endpoint = found.endpoint
        record["endpoint"] = {
            "type": type(endpoint).__name__,
            "sweeps": getattr(endpoint, "sweeps", None),
            "last_delta": _f(getattr(endpoint, "last_delta", None)),
            "sha256": found.endpoint_sha256,
            "initial_sha256": found.initial_sha256,
        }
        record["final_sha256"] = found.final_sha256
        record["signature"] = "".join(r[0] for r in found.signature)
        ratio, name = worst(deviations(case, found.state))
        record["worst"] = [_f(ratio), name]
        reentry = found.reentry
        stage_a_result = found.result if reentry is None else reentry.stage_a.result
        stage_a_from = found.recovered_from if reentry is None else reentry.stage_a.recovered_from
        record["stage_a"] = {
            "outcome": found.outcome if reentry is None else reentry.stage_a.outcome,
            "cause": found.cause if reentry is None else reentry.stage_a.cause,
            "first": _region(stage_a_from if stage_a_from is not None else stage_a_result),
            "recovery": _region(stage_a_result) if stage_a_from is not None else None,
        }
        record["stage_b"] = (
            None
            if reentry is None
            else {
                "trigger": reentry.trigger,
                "accepted": reentry.accepted,
                "candidates": [
                    {
                        "a": c.a,
                        "c": c.c,
                        "endpoint": c.endpoint,
                        "outcome": c.outcome,
                        "cause": c.cause,
                        "region": _region(c.recovered_from or c.result),
                        "recovery": _region(c.result) if c.recovered_from else None,
                    }
                    for c in reentry.candidates
                ],
            }
        )
    else:
        record["detail"] = getattr(found, "detail", None)
    record["newton"] = recorder.newton
    record["residuals"] = _residuals(trace)
    if dump is not None and isinstance(found, column_solve.ColumnSolution):
        # The states themselves, `repr`-exact, for an ulp-level comparison across machines.
        states = {
            "profile_initial": list(found.initial.profile),
            "initial": dict(found.initial.state),
            "endpoint": dict(found.endpoint.state),
            "final": dict(found.state),
        }
        dump.write_text(json.dumps(states, sort_keys=True), encoding="utf-8")
    return record


def main(argv: Sequence[str]) -> int:
    args = list(argv[1:])
    dump = None
    if "--dump" in args:
        at = args.index("--dump")
        dump = Path(args[at + 1])
        del args[at : at + 2]
    case = args[0] if args else "C-MW"
    print(json.dumps(diagnose(case, dump), separators=(",", ":"), sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
