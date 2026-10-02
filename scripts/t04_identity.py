"""T04's part of the cross-platform identity (A26), included by `k05_structural_identity.py`.

The R0 fields ADR 0010 D7 adds, for the cases A26 names and the ones W11's order adds — HOM-01
(PHS-05 rescued by edge 3), HOM-03 and HOM-04 (two stalls, bracketed at `23/256` and `909/1024`),
HOM-U (edge 3 due and `unsupported`), the synthetic seeds PTC-S1 and PTC-S5 on the generic PTC
core, OFF-B at r = 0.95 under PTC (a named run: a restart, then a polished stop) and PHS-05 under
PTC (the expected `PTC_STALLED`): the policy's `globalization` document; every `homotopy_step`
with λ and Δλ written `p/q`, its verdict and its corrector's outcome and iteration count; the
`homotopy_level` stamped on every corrector event; `region_closed`'s `eo_recovery` fields; each
attempt context's `core` and `continuation`; the provenance items with their `continuation`; the
checkpoint's `continuation_lambda`; and the PTC core's R0 fields — per attempt the pseudo-step
count, every trial's verdict and rejection reason in order, the landings, `blocked_by` and the
polish verdict.

Floats-free, as K05's identity document must be, by ADR 0007's classes as ADR 0010 D7 assigns
them. The policy's constants are registered values (R0) and are written as their exact decimal
strings. The compared floats — `pseudo_step`, `pseudo_step_next`, `ser_ratio`, a PTC trial's
`alpha` below 1 (R1/R2 under D2) — and the digests — `level_constants_sha256` (its preimage holds
the solved `p⁰`), `opening_state_sha256`, `full_state_sha256`, `state_sha256` — are left out,
never rounded. Messages are kept where their grammar is R0 (T03 §4.10, T04 §10): `attempt_opened`,
`solve_closed`, `homotopy_step` and the polish `trial`; the others may quote a measured number.

Every case is built from the package's tests (`test_t04_edge3`, `test_t04_ptc_region`,
`test_t04_ptc`, `test_t04_registry`), so this document and the gate run the same fixtures, and
from their uncached entry points, so two calls in one process are two solves.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

from t03_identity import _fingerprint, _provenance  # noqa: E402

#: The event kinds whose `message` has an R0 grammar; every other kind's is left out.
_MESSAGES = ("attempt_opened", "solve_closed", "homotopy_step")
#: The integer and string fields of an event, R0 by ADR 0007 and ADR 0010 D7 — kept when set.
_EVENT_FIELDS = (
    "outcome",
    "trial_status",
    "rejection_reason",
    "step_index",
    "homotopy_level",
    "lambda_value",
    "delta_lambda",
    "corrector_outcome",
    "corrector_iterations",
    "eo_recovery",
    "eo_recovery_unsupported",
)


def _exact(value: Any) -> Any:
    """A registered constant's float as its shortest round-trip decimal (T02's `execution_plan_r0`
    rule); everything else as it is."""
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return {key: _exact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_exact(item) for item in value]
    return value


def _events(trace: Any) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for event in trace.events:
        entry: dict[str, Any] = {
            "kind": event.kind,
            "attempt": event.attempt,
            "iteration": event.iteration,
            "signature": [[unit, regime] for unit, regime in event.signature],
        }
        entry.update(
            {
                name: getattr(event, name)
                for name in _EVENT_FIELDS
                if getattr(event, name) is not None
            }
        )
        polish = event.kind == "trial" and event.message.startswith("polish")
        if event.kind in _MESSAGES or polish:
            entry["message"] = event.message
        projected.append(entry)
    return projected


def _contexts(contexts: Any) -> list[dict[str, Any]]:
    return [
        {
            "attempt_index": context.attempt_index,
            "signature": [[unit, regime] for unit, regime in context.signature],
            "core": context.core,
            "continuation": context.as_document()["continuation"],
            "jacobian_pattern": (
                dict(context.jacobian_pattern) if context.jacobian_pattern is not None else None
            ),
        }
        for context in contexts
    ]


def _checkpoint(checkpoint: Any) -> dict[str, Any] | None:
    if checkpoint is None:
        return None
    document = checkpoint.as_document()
    return {
        key: document[key]
        for key in (
            "attempt_index",
            "iteration",
            "signature",
            "label",
            "verification_scope",
            "step_index",
            "continuation_lambda",
        )
    }


def _ptc(record: Any) -> dict[str, Any] | None:
    """A PTC attempt's R0 record: counts, the trials' verdicts and reasons in order, landings."""
    if record is None:
        return None
    trials = [(r.index, r.retry, r.reason, list(r.blocked_by)) for r in record.rejections]
    trials += [(s.index, s.retries, "accepted", list(s.landing)) for s in record.steps]
    return {
        "pseudo_steps": len(record.steps),
        "trials": [list(trial) for trial in sorted(trials, key=lambda t: (t[0], t[1]))],
        "polish": record.polish,
    }


def _region(result: Any) -> dict[str, Any]:
    """A region solve: its outcome and budget, attempts, contexts, provenance and checkpoint."""
    homotopy = result.homotopy
    return {
        "outcome": result.outcome,
        "budget": result.budget,
        "attempts": [
            {
                "signature": [[unit, regime] for unit, regime in attempt.signature],
                "outcome": attempt.outcome,
                "solver_outcome": attempt.solver_outcome,
                "iterations": attempt.iterations,
                "ptc": _ptc(attempt.ptc),
            }
            for attempt in result.attempts
        ],
        "contexts": _contexts(result.contexts),
        "branch_provenance": _provenance(result.branch_provenance),
        "checkpoint": _checkpoint(result.checkpoint),
        "root_fingerprint": _fingerprint(result.root_fingerprint),
        "homotopy": (
            None
            if homotopy is None
            else {
                "lambda_reached": str(homotopy.lambda_reached),
                "stalled_at": homotopy.stalled_at,
                "inferred_cause": homotopy.inferred_cause,
                "provenance": homotopy.provenance(),
            }
        ),
    }


def _plan(result: Any) -> dict[str, Any]:
    """A plan run through the executor: the step that solved the region, edge 3's record, the
    failed solve it recovered from, and the plan's trace."""
    (step,) = [step for step in result.steps if step.kind in ("solve_eo", "converge")][-1:]
    return {
        "outcome": result.outcome,
        "step": {
            "kind": step.kind,
            "outcome": step.outcome,
            "eo_recovery": step.eo_recovery,
            "eo_recovery_unsupported": step.eo_recovery_unsupported,
            "checkpoint": _checkpoint(step.checkpoint),
        },
        "region": _region(step.detail),
        "recovered_from": (
            _region(step.recovered_from) if step.recovered_from is not None else None
        ),
        "events": _events(result.trace),
    }


def _homotopy_case(case_id: str) -> dict[str, Any]:
    from test_t04_edge3 import case_document, case_policy, plan_run

    return _plan(plan_run(case_document(case_id), case_policy(case_id)).result)


def _hom_u() -> dict[str, Any]:
    """HOM-U from the registry: SYN-001 nominal under `eo`, one Newton iteration per attempt."""
    from test_t04_registry import CASES, plan_run, policy_for, revision

    case = CASES["SYN-001-nominal-eo-iteration-capped"]
    return _plan(plan_run(revision(case), policy_for(case)).result)


def _seed(name: str) -> dict[str, Any]:
    from test_t04_ptc import run_seed

    from openflowsheet.orchestrator.trace import Trace

    trace = Trace()
    outcome, attempts = run_seed(name, trace=trace)
    return {
        "outcome": outcome,
        "attempts": [
            {
                "regime": attempt.regime,
                "outcome": attempt.result.outcome,
                "iterations": attempt.result.iterations,
                "blocked_by": list(attempt.result.blocked_by),
                "ptc": _ptc(attempt.record),
            }
            for attempt in attempts
        ],
        "events": _events(trace),
    }


def _off_b_ptc() -> dict[str, Any]:
    from test_t04_ptc_region import HIGH, case, solve, start

    from openflowsheet.orchestrator.trace import Trace

    item = case(HIGH)
    trace = Trace()
    result = solve(item, start(item, "OFF-B"), trace=trace)
    return {**_region(result), "message": result.message, "events": _events(trace)}


def _phs05_ptc() -> dict[str, Any]:
    from test_t04_ptc_region import phs05

    run = phs05()
    return {**_region(run.failed), "message": run.failed.message, "events": _events(run.trace)}


def identity() -> dict[str, Any]:
    from openflowsheet.orchestrator.trace import SolvePolicy

    policy = SolvePolicy(policy_id="T04", residual_tolerances={}, scales={})
    return {
        "globalization": _exact(policy.as_document()["globalization"]),
        "HOM-01": _homotopy_case("HOM-01"),
        "HOM-03": _homotopy_case("HOM-03"),
        "HOM-04": _homotopy_case("HOM-04"),
        "HOM-U": _hom_u(),
        "PTC-S1": _seed("PTC-S1"),
        "PTC-S5": _seed("PTC-S5"),
        "OFF-B/ptc": _off_b_ptc(),
        "PHS-05/ptc": _phs05_ptc(),
    }
