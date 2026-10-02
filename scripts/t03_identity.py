"""T03's part of the cross-platform identity (A23), included by `k05_structural_identity.py`.

The R0 fields ADR 0005 adds, for the cases A23 names — OFF-B (the tear path), PHS-01, PHS-04,
PHS-05 (the lifted path: an appearance, a disappearance, the expected failure) and MR-A (a
multiple-root solve): the policy literal, each attempt's structural `jacobian_pattern`, the
`attempt_opened` and `solve_closed` messages, the R0 fields of `branch_provenance` and of
`root_fingerprint`. Floats-free, as K05's identity document must be: the one float the fingerprint
carries, `delta_scaled_inf`, is a registered constant and is written as its exact decimal; the
two digests (`opening_state_sha256`, `full_state_sha256`) are identities of float states and are
left out, never compared (ADR 0007).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

_DIGESTS = ("opening_state_sha256", "full_state_sha256")


def _provenance(items: Any) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key not in _DIGESTS} for item in items]


def _fingerprint(fingerprint: Any) -> dict[str, Any] | None:
    if fingerprint is None:
        return None
    projected = {key: value for key, value in fingerprint.items() if key not in _DIGESTS}
    projected["delta_scaled_inf"] = repr(projected["delta_scaled_inf"])
    return projected


def _messages(trace: Any) -> list[list[Any]]:
    return [
        [event.kind, event.attempt, event.message]
        for event in trace.events
        if event.kind in ("attempt_opened", "solve_closed")
    ]


def _region_case(case_id: str) -> dict[str, Any]:
    from test_t02_a02 import POLICY, revision, structure, the_region

    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.orchestrator.region import solve_region, syn001_lifted_splits
    from openflowsheet.orchestrator.tear import solve_tear
    from openflowsheet.orchestrator.trace import Trace

    item = structure(revision(case_id))
    flowsheet = item.binding.flowsheet
    pre, _ = solve_tear(flowsheet)
    trace = Trace()
    result = solve_region(
        compiled=compile_problem(item.binding.spec),
        spec=item.binding.spec,
        region=the_region(item),
        state=dict(pre.final_state or {}),
        splits=syn001_lifted_splits(flowsheet.components),
        provider=flowsheet.provider,
        policy=POLICY,
        trace=trace,
        initializer_source="user_guess",
    )
    return {
        "outcome": result.outcome,
        "phase_contract": POLICY.phase_contract,
        "jacobian_patterns": [dict(c.jacobian_pattern or {}) for c in result.contexts],
        "messages": _messages(trace),
        # The region records no `solve_closed` of its own (a plan's executor does); its terminal
        # decision is the result's message, in T03 §4.10's grammar.
        "terminal_message": result.message,
        "branch_provenance": _provenance(result.branch_provenance),
        "root_fingerprint": _fingerprint(result.root_fingerprint),
    }


def _off_b() -> dict[str, Any]:
    from test_k03_attempts import OFF_B, flowsheet_for, variants

    from openflowsheet.orchestrator.tear import solve_tear
    from openflowsheet.orchestrator.trace import SolvePolicy

    reference = yaml.safe_load(
        (ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    policy = SolvePolicy(policy_id="SYN-001-K03", residual_tolerances={}, scales={})
    result, trace = solve_tear(
        flowsheet_for(variants(reference)["SYN-001-nominal"]),
        initial_recycle=OFF_B,
        policy=policy,
    )
    return {
        "outcome": result.outcome,
        "phase_contract": policy.phase_contract,
        "jacobian_patterns": [dict(c.jacobian_pattern or {}) for c in result.contexts],
        "messages": _messages(trace),
        "branch_provenance": _provenance(result.branch_provenance),
        "root_fingerprint": _fingerprint(result.root_fingerprint),
    }


def _mr_a() -> dict[str, Any]:
    from test_t03_roots import rec_05_run

    t02 = yaml.safe_load((ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text())
    result = rec_05_run(t02, "1.1 t*")
    return {
        "outcome": result.outcome,
        "branch_provenance": _provenance(result.branch_provenance),
        "root_fingerprint": _fingerprint(result.root_fingerprint),
    }


def identity() -> dict[str, Any]:
    return {
        "OFF-B": _off_b(),
        "PHS-01": _region_case("SYN-001-A02-355-liquid-guess"),
        "PHS-04": _region_case("SYN-001-A02-340-two-phase-guess"),
        "PHS-05": _region_case("SYN-001-A02-355-dew-guess"),
        "MR-A": _mr_a(),
    }
