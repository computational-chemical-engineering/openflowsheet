"""The R0 projection of a run's artifacts, and its digest. K05, S1(b) of the Fable review.

Blueprint §8.3 R0 promises "identical structural artifacts on supported platforms". This is
that projection: the plan's structure, the event sequence with its kinds and outcomes, the
certificate's check ids and results, the solver counters — and **no floats**, because §8.3
excludes adaptive floating-point decisions from any cross-platform bitwise promise and two
x86-64 runners were measured disagreeing on a converged state's last bits.

It lives in production rather than in a script because two things need it and they must not
drift: `RunManifest.structural_sha256`, so that a run's identity actually covers what the run
did rather than only what it was called, and the G05 comparison, which gets a one-hash check
with this document as its diagnosable preimage.

**A conditional promise, stated.** Per-check `result` words, `verification_status` and
`outcome` are R0 only under ADR 0007 D2.4: when a quantity they depend on sits within the
near-threshold margin of its threshold, two registered platforms may legitimately disagree.
The projection therefore carries each check's `near_threshold` flag — a boolean, no float — so
that a cross-platform difference is diagnosable as D2.4 rather than mistaken for a defect.
SYN-001 nominal has no flags at all (K04 A33), so this is invisible today and will matter the
day a registered case lands in the band.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from openflowsheet.canonical import canonical_json

#: ADR 0007 D5.3: the counters that are invariant under a one-ulp perturbation and across
#: architectures. The three property counters move 13% under the same perturbation and are
#: deliberately absent.
SOLVER_COUNTERS = ("residual_calls", "jacobian_calls", "factorizations")


def execution_plan_r0(document: Mapping[str, Any]) -> dict[str, Any]:
    """T02 A02: an `ExecutionPlan` document's R0 content, floats-free as K05's identity document
    must be. ADR 0009 D1 makes the plan R0 entire — ids, integers, orderings, *declared scales
    and bounds* (review S3) — and every float in it is such a declared constant, so each is kept
    and compared exactly as its shortest decimal string. The one computed float, a certificate's
    `constant_mismatch`, goes with the eliminated rows, which are compared by id."""

    def keep(value: Any, key: str = "") -> Any:
        if isinstance(value, float):
            return repr(value)
        if isinstance(value, Mapping):
            return {name: keep(item, name) for name, item in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            if key == "eliminated_rows":
                return [row["row_id"] if isinstance(row, Mapping) else row for row in value]
            return [keep(item) for item in value]
        return value

    result: dict[str, Any] = keep(document)
    return result


def r0_projection(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    """The R0 content of a run's artifacts, by artifact name. No floats, at any depth."""
    projection: dict[str, Any] = {}

    plan = artifacts.get("solve-plan.json")
    if isinstance(plan, dict):
        projection["plan"] = {
            "tear_variable_ids": plan["tear_variable_ids"],
            "tear_row_ids": plan["tear_row_ids"],
            "inner_variable_ids": plan["inner_variable_ids"],
            "inner_row_ids": plan["inner_row_ids"],
            "eliminated_rows": [row["row_id"] for row in plan["eliminated_rows"]],
            "signature_units": plan["signature_units"],
            "initializer_chain": plan["initializer_chain"],
            "estimates": plan["estimates"],
        }

    events = artifacts.get("solve-events.json")
    if isinstance(events, Sequence) and not isinstance(events, str | bytes):
        projection["events"] = [
            {
                "sequence": event["sequence"],
                "kind": event["kind"],
                "attempt": event["attempt"],
                "iteration": event["iteration"],
                "signature": event["signature"],
                "outcome": event.get("outcome"),
            }
            for event in events
        ]
        if events:
            projection["solver_counters"] = {
                key: events[-1]["counters"][key] for key in SOLVER_COUNTERS
            }

    certificate = artifacts.get("solution-certificate.json")
    if isinstance(certificate, dict):
        projection["certificate"] = {
            "verification_status": certificate["verification_status"],
            "false_success_detected": certificate["false_success_detected"],
            "check_ids": [check["id"] for check in certificate["checks"]],
            "check_results": [check["result"] for check in certificate["checks"]],
            # D2.4's condition, carried so a difference is diagnosable rather than mysterious.
            "check_near_threshold": [
                bool(check["near_threshold"]) for check in certificate["checks"]
            ],
            "regularity_status": certificate["regularity"]["status"],
            "regularity_dimension": certificate["regularity"]["dimension"],
            "limitation_kinds": sorted(
                {limitation["kind"] for limitation in certificate["limitations"]}
            ),
        }

    structural = artifacts.get("structural-report.json")
    if isinstance(structural, dict):
        # T01 A22. The whole report is structural by construction, so the projection is the
        # report's own (`graph.report.r0_of`) rather than a subset chosen here — a second,
        # hand-picked subset is exactly the drift M4 of the K05 review found between the
        # comparator and the policy, and S3 of the T01 review found it again.
        from openflowsheet.graph.report import r0_of

        projection["structural"] = r0_of(structural)

    # T07 §12.3 (ADR 0020): a revision bundle's execution plan, R0 entire (T02 A02), and its
    # recorded route (ruling round 1 R2.4; `route_reason` stays outside R0). No bundle written
    # before T07 has either file, so every earlier projection — and every K05 hash — is unchanged.
    execution_plan = artifacts.get("execution-plan.json")
    if isinstance(execution_plan, dict):
        projection["execution_plan"] = execution_plan_r0(execution_plan)
    solve_path = artifacts.get("solve-path.json")
    if isinstance(solve_path, dict):
        projection["solve_path"] = solve_path["solve_path"]
        # ADR 0024 D4 (T08 build-first spec §B2): a warm start's R0 — what happened and on which
        # ids, never a value, a digest or the provenance ids. No bundle before T08 W4 has the
        # member, so every earlier projection, and every registered key, is unchanged.
        warm_start = solve_path.get("warm_start")
        if isinstance(warm_start, dict):
            candidate = warm_start.get("candidate")
            ids = candidate.get("variable_ids") if isinstance(candidate, dict) else None
            projection["warm_start"] = {
                "status": warm_start["status"],
                "reason": warm_start["reason"],
                "selection": warm_start["selection"],
                "candidate_variable_ids": (
                    sorted(ids)
                    if isinstance(ids, list) and all(isinstance(name, str) for name in ids)
                    else None
                ),
                "projected_ids": [entry[0] for entry in warm_start["projections"]],
            }
    # T07 ruling round 2 F1.3: the solution state's ids only. Its values and its digest are
    # float-derived and never R0 (ADR 0007; ADR 0008 D2.1). Inert for every earlier bundle.
    solution_state = artifacts.get("solution-state.json")
    if isinstance(solution_state, dict):
        projection["solution_state"] = {"variable_ids": list(solution_state["variable_ids"])}

    bundle = artifacts.get("failure-bundle.json")
    if isinstance(bundle, dict):
        projection["failure"] = {
            "outcome": bundle["outcome"],
            "taxonomy": bundle["taxonomy"],
            "implicated_sources": bundle["implicated_sources"],
            "suggested_actions": [entry["action"] for entry in bundle["suggested_actions"]],
            "solver_counters": {
                key: bundle["observations"]["counters"][key] for key in SOLVER_COUNTERS
            },
        }
    return projection


def r0_sha256(projection: Mapping[str, Any]) -> str:
    """ADR 0002's canonical JSON of the projection."""
    return hashlib.sha256(canonical_json(dict(projection))).hexdigest()


def floats_in(node: Any, path: str = "") -> list[str]:
    """Every float in a document, by path. The projection must contain none."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found += floats_in(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found += floats_in(value, f"{path}[{index}]")
    elif isinstance(node, float):
        found.append(path)
    return found
