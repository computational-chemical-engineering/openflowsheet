"""M05 WO-7 (design note §9.1, §8.3, gate G12): the `trust-region-study-v1` schema and the record's
arithmetic, on records produced by `run_study` over the WO-6 fakes.

Default gate: no Pyomo, no solve. The identities are written as functions of a record so that WO-8's
committed records (`COMMITTED_RECORDS`) pass through the very same checks as the fakes'.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from jsonschema import Draft202012Validator
from test_m05_study_loop import (
    DECISIONS,
    FakeParent,
    FakeStage,
    T,
    budget,
    study,
)

from openflowsheet.studies.trust_region.checks import ParentSolve
from openflowsheet.studies.trust_region.holders import PARENT_EXPERIMENT, SUMMARY_PURPOSES
from openflowsheet.studies.trust_region.study import run_study
from openflowsheet.studies.trust_region.trf_state import (
    TRF_CONFIG_V1,
    TRF_CONVERGED,
    TRF_STALLED_INCONSISTENT,
    FrameworkReadiness,
    ReadinessReason,
)
from openflowsheet.studies.trust_region.truths import (
    COORDINATES,
    GradientCheck,
    candidate_statistics,
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_numerical_policy  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "schemas" / "trust-region-study.schema.json"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

#: WO-8's committed study records join here (G12: "the committed records validate and pass §8.3's
#: arithmetic"); every record found is run through `test_a_record_validates_and_adds_up`. They
#: live under `benchmarks/m05/records/` (§9.5), beside their `.ledger.json` and `.coupling/`.
COMMITTED_RECORDS = sorted(
    path
    for path in [
        *(REPO_ROOT / "evidence" / "M05").glob("*/records/trust-region-study-*.json"),
        *(REPO_ROOT / "benchmarks" / "m05" / "records").glob("trust-region-study-*.json"),
    ]
    if path.suffixes == [".json"]
)

SPEC = {
    "case": "fake",
    "revision_sha256": "0" * 64,
    "decisions": [{"id": T, "lower": 653.15, "upper": 693.15}],
    "objective": {"id": "J", "sense": "maximize"},
    "inequalities": [],
    "decision_tolerances": {T: 0.5},
    "budgets": {"budget_id": "test"},
    "configs": {
        "trf": "M05-trf-config-v1",
        "trsp": "M05-trsp-ipopt-v1",
        "fd": "M05-fd-v2",
        "basis": "M05-basis-v1",
        "checks": "M05-checks-v1",
    },
    "truth": {"kind": "synthetic", "id": "fake", "sha256": None, "synthetic": True},
    "surrogate": None,
}


ENVIRONMENT = {
    "pyomo_version": "6.10.1",
    "trf_module_sha256": {"TRF.py": "3" * 64},
    "ipopt_version": "3.14.19",
    "mumps_version": "5.8.2",
    "trsp_executable_sha256": "2" * 64,
    "platform": "linux-x86_64",
}


#: S12: `artifacts.ledger`, the study ledger file's sha256 (the caller's, as the ledger file is).
LEDGER_SHA256 = "5" * 64

#: §8.3: n_in, the reactor EF's inlet coordinates (an FD gradient costs n_in points).
N_IN = 7

#: `FullStage`'s truth: a parent experiment whose gradient the holder takes by `M05-fd-v2`.
FD_TRUTH = {
    "kind": PARENT_EXPERIMENT,
    "id": "fake-fd",
    "sha256": "4" * 64,
    "synthetic": True,
    "gradient": "finite_difference",
}


def fd_summary(iterations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """An `EFHolder.summary` that satisfies §8.3's identity for `iterations` (S16): the start a
    store hit, one PMP value, K trial values, n_in basis FD points, and n_in FD points per TRF
    gradient (the PMP point's, and each accepted iterate's but the last)."""
    logged = sum(1 for it in iterations if it["k"] >= 1)
    accepted = sum(1 for it in iterations if it["type"] in ("f", "theta"))
    gradients = 1 + accepted - int(iterations[-1]["type"] in ("f", "theta"))
    by_purpose = dict.fromkeys(SUMMARY_PURPOSES, 0)
    by_purpose.update(
        trf_start_value=1,
        trf_pmp_value=1,
        trf_trial_value=logged,
        trf_fd_point=N_IN * gradients,
        basis_fd_point=N_IN,
    )
    value_cold = 1 + logged + N_IN * (1 + gradients)
    return {
        "value_cold": value_cold,
        "value_store_hit": 1,
        "value_memo_hit": 0,
        "jacobian_cold": gradients,
        "jacobian_store_hit": 0,
        "jacobian_memo_hit": 0,
        "requests": value_cold + 1 + gradients,
        "refused": 0,
        "by_purpose": by_purpose,
        "pmp_point_equals_start": False,
    }


class FullStage(FakeStage):
    """`FakeStage` with a complete §9.1 `runs[]` entry: every key `TrfStage` writes, on dummy
    numbers (iteration 0 is the PMP, with no step type), with an FD truth whose holder summary
    satisfies §8.3's identity."""

    def __call__(self, start: Any, *, run_id: str, radius_factor: float, budget: Any) -> Any:
        staged = super().__call__(start, run_id=run_id, radius_factor=radius_factor, budget=budget)
        decisions = staged.decisions
        config: dict[str, Any] = {
            **TRF_CONFIG_V1,
            "trust_radius": TRF_CONFIG_V1["trust_radius"] * radius_factor,
        }
        iterations = [
            {
                "k": k,
                "theta": 0.0,
                "objective": 0.1 * k,
                "radius": 0.5,
                "radius_logged": "updated",
                "step_norm": 0.1,
                "type": None if k == 0 else "f",
            }
            for k in range(3)
        ]
        document = {
            "truth": [dict(FD_TRUTH)],
            "basis": {"reactor": "affine_taylor"},
            "projection": {
                "source_map_sha256": "1" * 64,
                "n_vars": 9,
                "n_rows": 8,
                "n_block_efs": 1,
                "n_link_efs": 1,
                "n_ineq": 0,
            },
            "config": config,
            "iterations": iterations,
            "filter": [{"f": 0.0, "theta": 0.0}],
            "exit_lines": [],
            "final": None
            if decisions is None
            else {"decisions": dict(decisions), "objective": 0.3, "theta": 0.0},
            "theta_recheck": None if decisions is None else 0.0,
            "exit_claim": None,
            "theta_logged": None if decisions is None else 0.0,
            "final_state_is_last_truth_point": None if decisions is None else True,
            # R-401 (WO-8a): the final step's s_K/Δ_K and the returned decision at a box bound.
            "final_step_ratio": 0.25,
            "final_step_at_box_bound": None if decisions is None else False,
            "error": None,
            "ledger": {"summary": {"reactor": fd_summary(iterations)}, "cold_parent": 0},
            "assumptions": [{"id": f"A{i}", "status": "assumed"} for i in range(1, 8)],
        }
        return type(staged)(
            run_id=staged.run_id,
            outcome=staged.outcome,
            decisions=staged.decisions,
            point=staged.point,
            cold=staged.cold,
            document=document,
        )


def _document(found: Any, fd_check: Mapping[str, Any] | None = None) -> dict[str, Any]:
    document: dict[str, Any] = found.as_document(
        spec=SPEC,
        environment=ENVIRONMENT,
        trf_theory="assumptions_hold",
        limitations=("synthetic",),
        artifacts={"ledger": LEDGER_SHA256},
        fd_check=fd_check,
    )
    return document


def _stable() -> dict[str, Any]:
    stage = FullStage(
        [(TRF_STALLED_INCONSISTENT, None), (TRF_CONVERGED, 670.0), (TRF_CONVERGED, 673.0)]
    )
    return _document(study(FakeParent(), stage))


def _failed_candidate() -> dict[str, Any]:
    parent = FakeParent(regime=lambda t: "liquid" if t > 670.0 else "two_phase")
    return _document(study(parent, FullStage([(TRF_CONVERGED, 673.0)])))


def _start_not_certified() -> dict[str, Any]:
    return _document(study(FakeParent(uncertified=lambda t: t == 668.0), FullStage([])))


def _budget_exhausted() -> dict[str, Any]:
    return _document(
        study(FakeParent(), FullStage([(TRF_CONVERGED, 673.0)]), budget=budget(cold=4))
    )


def _unsupported() -> dict[str, Any]:
    def unpinned() -> FrameworkReadiness:
        return FrameworkReadiness(
            "UNSUPPORTED", (ReadinessReason("TRUST_REGION_FRAMEWORK_UNPINNED", "6.9"),)
        )

    return _document(
        run_study(
            FakeParent(),
            decisions=DECISIONS,
            start={T: 668.0},
            stage_c=FullStage([]),
            budget=budget(),
            framework=unpinned,
        )
    )


def _escalated_fd_check() -> dict[str, Any]:
    """An `fd_check` that escalates once (§19.2, R-386: one generated record carries an `fd_check`
    with at least two candidates, so that every float rule of the addendum sees a float).

    Hand-built from `candidate_statistics`, as §19.2 allows: the in-process synthetic FD truth
    passes at the first η (`test_fd_v2_iii_the_check_passes_at_eta_truncation_dominated`, one
    candidate). G(η) is the same matrix at every step except a 0.1 spike at η/4 = 2⁻¹⁶: the first
    candidate (2⁻¹⁴) is `noise_dominated` (ν̂ = 0.4/14), the second (2⁻¹²) `clean`."""
    g = tuple(tuple(0.25 * (k + 1) * (j + 1) for j in range(N_IN)) for k in range(2))
    spiked = ((g[0][0] + 0.1, *g[0][1:]), g[1])
    eta = 2.0**-14
    candidates = (
        candidate_statistics(spiked, g, g, eta),
        candidate_statistics(g, g, g, 4.0 * eta),
    )
    assert [item["class"] for item in candidates] == ["noise_dominated", "clean"]
    selected = 4.0 * eta
    w0 = (2.0, 0.7, 0.05, 0.02, 0.03, 673.15, 2.0e7)
    floors = (1e-3 * sum(w0[:5]),) * 5 + (1.0, 1e5)
    return GradientCheck(
        w0=w0,
        candidates=candidates,
        eta=selected,
        status="pass",
        gradient=g,
        sides=(1, 1, 1, -1, 1, -1, 1),
        selected_class="clean",
        stopped="passed",
        half_steps={
            name: 0.5 * selected * max(abs(value), floor)
            for name, value, floor in zip(COORDINATES, w0, floors, strict=True)
        },
    ).as_document()


def _charge_first_stage_c(
    record: dict[str, Any], cold: int, store_hits: int, **purposes: int
) -> dict[str, Any]:
    """`record` with `cold` more cold and `store_hits` more store-hit value requests of the given
    purposes in its first stage-C run, charged to that run, its candidate and the study."""
    first = next(run for run in record["runs"] if run["stage"] == "C")
    summary = first["ledger"]["summary"]["reactor"]
    summary["by_purpose"].update(purposes)
    summary["value_cold"] += cold
    summary["value_store_hit"] += store_hits
    summary["requests"] += cold + store_hits
    first["cold"] += cold
    accounting = record["accounting"]
    for table, key in (("by_stage", "C"), ("by_iteration", str(first["study_iteration"]))):
        accounting[table][key]["trf_cold"] += cold
    accounting["totals"]["trf_cold"] += cold
    accounting["budgets"]["cold_used"] += cold
    for candidate in record["candidates"]:
        if candidate["run_id"] == first["run_id"]:
            accounting["by_candidate"][candidate["candidate_id"]]["produce_trf_cold"] += cold
    return record


def _stable_with_an_fd_check() -> dict[str, Any]:
    """R-406: the study's check is inside the first stage-C run, 1 + 4·7 points (the escalated
    check evaluated η/4, η, 4η and 16η), its base a store hit, charged to the run and the study."""
    stage = FullStage([(TRF_CONVERGED, 673.0)])
    record = _document(study(FakeParent(), stage), fd_check=_escalated_fd_check())
    return _charge_first_stage_c(record, 28, 1, fdcheck_point=29)


def _iteration_limit() -> dict[str, Any]:
    script: list[tuple[str, float | None]] = [(TRF_CONVERGED, 660.0)] * 12
    return _document(study(FakeParent(), FullStage(script)))


def _stable_with_basis_v2() -> dict[str, Any]:
    """`decision_stable_with_an_fd_check` under `M05-basis-v2` (R-400): the first stage-C run also
    carries the curvature block and its two path points (charged to its cold count and the
    study's budget)."""
    record = copy.deepcopy(_stable_with_an_fd_check())  # the spec is a shared constant
    record["spec"]["configs"]["basis"] = "M05-basis-v2"
    _charge_first_stage_c(record, 2, 0, basis_curvature_point=2)
    first = next(run for run in record["runs"] if run["stage"] == "C")
    first["basis"] = {
        "policy": "M05-basis-v2",
        "kinds": first["basis"],
        "links": {
            "link:reactor": {
                "stencil": "central",
                "t": 0.025,
                "d_points": [0.025, -0.025],
                "solves": ["CONVERGED", "CONVERGED"],
                "w_points": [[0.5, 673.65], [0.5, 672.65]],
                "v": [0.0, 20.0],
                "c": [-0.3835, 0.8914],
                "status": "ok",
                "reason": None,
                "noise_ratio": [0.065, 0.028],
            }
        },
    }
    return record


def _stable_with_provenance() -> dict[str, Any]:
    """Build log S65 (FD-3): the evidence script's `provenance` block, added after
    `as_document` (the run commit, a clean tree, the study's spent wall time)."""
    record = _stable()
    record["provenance"] = {
        "run_commit": "0123456789abcdef" * 2 + "01234567",
        "tree_clean": True,
        "wall_s": 12.5,
    }
    return record


GENERATED: dict[str, Callable[[], dict[str, Any]]] = {
    "decision_stable_with_a_retry": _stable,
    "candidate_failure": _failed_candidate,
    "start_not_certified": _start_not_certified,
    "budget_exhausted": _budget_exhausted,
    "unsupported": _unsupported,
    "iteration_limit": _iteration_limit,
    "decision_stable_with_an_fd_check": _stable_with_an_fd_check,
    "decision_stable_with_basis_v2": _stable_with_basis_v2,
    "decision_stable_with_provenance": _stable_with_provenance,
}


# -- §8.3's arithmetic, as functions of a record ---------------------------------------------------


def accounting_violations(record: Mapping[str, Any]) -> list[str]:
    """Every way the record's `accounting` fails to add up to its `runs`, `start` and `candidates`
    (§8.3: totals by stage, iteration and candidate against the overall; §8.2's summaries against
    the coupled-run list)."""
    found: list[str] = []
    accounting = record["accounting"]
    totals = accounting["totals"]
    runs = record["runs"]
    solves = ([record["start"]] if record.get("start") else []) + [
        solve for candidate in record["candidates"] for solve in candidate["solves"]
    ]
    expected = {
        "trf_cold": sum(run["cold"] for run in runs),
        "parent_executions": sum(s["experiments"]["executions"] for s in solves),
        "store_hits": sum(s["experiments"]["store_hits"] for s in solves),
        "parent_solves": len(solves),
        "trf_runs": len(runs),
    }
    for name, value in expected.items():
        if totals[name] != value:
            found.append(f"totals.{name} = {totals[name]}, the records give {value}")
    for table in ("by_stage", "by_iteration"):
        for name in ("trf_cold", "parent_executions", "store_hits"):
            added = sum(row[name] for row in accounting[table].values())
            if added != totals[name]:
                found.append(f"{table}.{name} adds to {added}, totals.{name} = {totals[name]}")
    for stage in {run["stage"] for run in runs}:
        cold = sum(run["cold"] for run in runs if run["stage"] == stage)
        if accounting["by_stage"].get(stage, {}).get("trf_cold") != cold:
            found.append(f"by_stage.{stage}.trf_cold is not the stage's runs' {cold}")
    cold_by_run = {run["run_id"]: run["cold"] for run in runs}
    for candidate in record["candidates"]:
        row = accounting["by_candidate"][candidate["candidate_id"]]
        checked = sum(s["experiments"]["executions"] for s in candidate["solves"])
        if row["check_parent_executions"] != checked:
            found.append(f"by_candidate.{candidate['candidate_id']} check executions != {checked}")
        # A candidate's run is its last attempt; the earlier attempts' cold requests are the
        # same study iteration's (`produced_by` lists them in order).
        if row["produce_trf_cold"] < cold_by_run.get(candidate["run_id"], 0):
            found.append(f"by_candidate.{candidate['candidate_id']} produce < its run's cold")
    if set(accounting["by_candidate"]) != {c["candidate_id"] for c in record["candidates"]}:
        found.append("by_candidate is not keyed by the candidates")
    if accounting["budgets"]["cold_used"] != totals["trf_cold"] + totals["parent_executions"]:
        found.append("budgets.cold_used is not trf_cold + parent_executions")
    if accounting["exhausted"] != (record["status"] == "BUDGET_EXHAUSTED"):
        found.append("exhausted disagrees with the status")
    # S18: only the solves that have a coupling record are listed.
    recorded = [s for s in solves if s["coupling_record_sha256"] is not None]
    coupled = [item["check_id"] for item in record["artifacts"]["coupled_runs"]]
    if coupled != [s["check_id"] for s in recorded]:
        found.append("artifacts.coupled_runs is not the recorded solves in order")
    for solve, item in zip(recorded, record["artifacts"]["coupled_runs"], strict=False):
        if item["sha256"] != solve["coupling_record_sha256"]:
            found.append(f"coupled run {item['check_id']} hash differs from its summary")
    return found


def status_violations(record: Mapping[str, Any]) -> list[str]:
    """The status against the record's own evidence (§7.3 precedence: readiness, then S0, then
    the runs and candidates in order)."""
    found: list[str] = []
    status = record["status"]
    candidates = record["candidates"]
    readiness = record.get("readiness")
    if status.startswith("UNSUPPORTED("):
        codes = [r["code"] for r in (readiness or {"reasons": []})["reasons"]]
        if not codes or status != f"UNSUPPORTED({','.join(dict.fromkeys(codes))})":
            found.append("UNSUPPORTED codes are not the readiness reasons")
    elif readiness is not None and readiness["status"] != "READY":
        found.append("a readiness refusal with a status that is not UNSUPPORTED")
    if status == "DECISION_STABLE":
        last = candidates[-1] if candidates else None
        if last is None or last["status"] != "PARENT_LOCAL_EVIDENCE":
            found.append("DECISION_STABLE without a final PARENT_LOCAL_EVIDENCE candidate")
        if not all(c["status"] == "NOT_STATIONARY_AT_DELTA" for c in candidates[:-1]):
            found.append("a candidate before the stable one is not NOT_STATIONARY_AT_DELTA")
        if record["claims"]["stationarity"] != "poll_at_delta" or not (record["best"] or {}).get(
            "stable"
        ):
            found.append("DECISION_STABLE without the poll-at-delta claim")
    elif record["claims"]["stationarity"] != "not_claimed":
        found.append("a stationarity claim without DECISION_STABLE")
    for candidate in candidates:
        # `pass: null` is a check that does not apply (P2 without a TRF point), not a failure.
        failed = [name for name, check in candidate["checks"].items() if check["pass"] is False]
        if candidate["status"] == "PARENT_CHECK_FAILED" and "P1" not in failed:
            found.append(f"{candidate['candidate_id']}: PARENT_CHECK_FAILED with P1 passing")
        if candidate["status"] == "PARENT_LOCAL_EVIDENCE" and failed:
            found.append(f"{candidate['candidate_id']}: local evidence with {failed} failed")
        # S15: the half-width is null iff P5 did not run, else keyed by exactly the decision ids.
        halfwidth = candidate["indifference_halfwidth"]
        if (halfwidth is None) != ("P5" not in candidate["checks"]):
            found.append(f"{candidate['candidate_id']}: indifference_halfwidth null iff no P5")
        elif halfwidth is not None and set(halfwidth) != set(candidate["decisions"]):
            found.append(f"{candidate['candidate_id']}: indifference_halfwidth's keys differ")
    if status.startswith("FAILED(") and candidates:
        stopped = candidates[-1]["status"]
        if status not in (f"FAILED({stopped})",) and not status.startswith("FAILED(trf_aborted"):
            found.append("FAILED status is not the last candidate's")
    if record["claims"]["global_optimality"] is not False:
        found.append("global optimality claimed")
    return found


#: R-400's basis policy, whose runs carry a curvature block.
BASIS_V2 = "M05-basis-v2"


def request_identity_violations(record: Mapping[str, Any]) -> list[str]:
    """§8.3's TRF request identity (S16, G12) as integer equalities, for every run with an FD
    truth (a `truth` entry with `gradient: finite_difference`), on its holder's `by_purpose`:
    `trf_start_value` = 1; `trf_pmp_value` = 1, or 0 when `pmp_point_equals_start`;
    `trf_trial_value` = K, the logged iterations k ≥ 1; `basis_fd_point` = n_in (no surrogate
    basis, §6.6); `trf_fd_point` = n_in·(1 + A − [the final logged iteration was accepted]), with
    A the accepted steps (`trf_state.accepted_steps`). The run's truths and holder summaries are
    lists by holder in the same order but keyed differently, so an FD truth is attributed only
    when it is the run's one truth (build log S41).

    R-400: a run with an `M05-basis-v2` block has `basis_curvature_point` = 2 per link.
    R-406 (§20.4): the study's FD check is inside the first stage-C run, whose `fdcheck_point` =
    1 + n_in·|η evaluated| (each candidate η used G(η/4), G(η), G(4η)), and every other run's is
    0 (build log S54: since WO-8e no record predates R-406, so no record is exempt)."""
    found: list[str] = []
    accepting = ("f", "theta")
    check_run = None
    check_points = 0
    stage_c = [run["run_id"] for run in record["runs"] if run["stage"] == "C"]
    check = record.get("fd_check")
    if check is not None and stage_c:
        check_run = stage_c[0]
        etas = {
            eta * factor
            for candidate in check["candidates"]
            for eta in (candidate["eta"],)
            for factor in (0.25, 1.0, 4.0)
        }
        check_points = 1 + N_IN * len(etas)
    for run in record["runs"]:
        name = run["run_id"]
        if not any(truth["gradient"] == "finite_difference" for truth in run["truth"]):
            continue
        summaries = run["ledger"]["summary"]
        if len(run["truth"]) != 1 or len(summaries) != 1:
            found.append(
                f"{name}: an FD truth among {len(run['truth'])} truths and {len(summaries)} "
                "holder summaries is not attributable to one summary"
            )
            continue
        (summary,) = summaries.values()
        counts = summary["by_purpose"]
        iterations = run["iterations"]
        accepted = sum(1 for it in iterations if it["type"] in accepting)
        final_accepted = bool(iterations) and iterations[-1]["type"] in accepting
        expected = {
            "trf_start_value": 1,
            "trf_pmp_value": 0 if summary["pmp_point_equals_start"] else 1,
            "trf_trial_value": sum(1 for it in iterations if it["k"] >= 1),
            "trf_fd_point": N_IN * (1 + accepted - int(final_accepted)),
        }
        basis = run["basis"]
        kinds = basis["kinds"] if "policy" in basis else basis
        if "surrogate" not in kinds.values():
            expected["basis_fd_point"] = N_IN
        if basis.get("policy") == BASIS_V2:
            # R-400: two path points per link (§8.3 as amended by §20.7).
            expected["basis_curvature_point"] = 2 * len(basis["links"])
        expected["fdcheck_point"] = check_points if name == check_run else 0
        for purpose, value in expected.items():
            if counts[purpose] != value:
                found.append(f"{name}: {purpose} = {counts[purpose]}, §8.3 gives {value}")
    return found


def _records() -> list[Any]:
    generated = [pytest.param(make, id=name) for name, make in GENERATED.items()]
    committed = [
        pytest.param(lambda path=path: json.loads(path.read_text(encoding="utf-8")), id=path.name)
        for path in COMMITTED_RECORDS
    ]
    return generated + committed


@pytest.mark.parametrize("make", _records())
def test_a_record_validates_and_adds_up(make: Callable[[], dict[str, Any]]) -> None:
    """The WO-8 hook: every generated record and every committed one."""
    record = make()
    assert sorted(VALIDATOR.iter_errors(record), key=str) == []
    assert accounting_violations(record) == []
    assert status_violations(record) == []
    assert request_identity_violations(record) == []


def test_the_schema_is_registered_and_is_itself_a_valid_schema() -> None:
    Draft202012Validator.check_schema(VALIDATOR.schema)
    registry = json.loads((REPO_ROOT / "schemas" / "registry.json").read_text(encoding="utf-8"))
    assert "trust-region-study.schema.json" in registry
    schema: Any = VALIDATOR.schema
    assert schema["properties"]["schema_version"] == {"const": "trust-region-study-v1"}


def test_the_generated_records_cover_the_statuses() -> None:
    statuses = {name: make()["status"] for name, make in GENERATED.items()}
    assert statuses == {
        "decision_stable_with_a_retry": "DECISION_STABLE",
        "candidate_failure": "FAILED(REGIME_CHANGED)",
        "start_not_certified": "FAILED(start_not_certified)",
        "budget_exhausted": "BUDGET_EXHAUSTED",
        "unsupported": "UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNPINNED)",
        "iteration_limit": "ITERATION_LIMIT",
        "decision_stable_with_an_fd_check": "DECISION_STABLE",
        "decision_stable_with_basis_v2": "DECISION_STABLE",
        "decision_stable_with_provenance": "DECISION_STABLE",
    }


def test_the_stable_record_has_the_retry_and_both_candidates() -> None:
    record = _stable()
    assert [(r["run_id"], r["retry"]) for r in record["runs"]] == [
        ("C1", 0),
        ("C1-retry", 1),
        ("C2", 0),
    ]
    assert len(record["candidates"]) == 2


# -- the schema rejects what §9.1 forbids ----------------------------------------------------------


def _set(record: Any, path: Sequence[Any], value: Any) -> None:
    node: Any = record
    for key in path[:-1]:
        node = node[key]
    if value is _DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = value


def _mutated(path: Sequence[Any], value: Any, base: Callable[[], dict[str, Any]] = _stable) -> Any:
    record = copy.deepcopy(base())
    _set(record, path, value)
    return record


def _fd_check_document() -> dict[str, Any]:
    """§17.2's `fd_check` as `GradientCheck.as_document` writes it, on dummy numbers."""
    g = ((1.0,) * N_IN, (0.5,) * N_IN)
    eta = 2.0**-14
    return GradientCheck(
        w0=(1.0,) * N_IN,
        candidates=(candidate_statistics(g, g, g, eta),),
        eta=eta,
        status="pass",
        gradient=g,
        sides=(1,) * N_IN,
        selected_class="clean",
        stopped="passed",
        half_steps={"T": 1e-5},
    ).as_document()


_DELETE = object()


@pytest.mark.parametrize(
    "path, value",
    [
        (("schema_version",), "trust-region-study-v2"),
        (("claims", "global_optimality"), True),
        (("claims", "stationarity"), "stationary"),
        (("claims", "trf_theory"), "proved"),
        (("status",), "DONE"),
        (("accounting", "totals", "trf_cold"), -1),
        (("accounting", "totals", "surprise"), 1),
        (("runs", 0, "stage"), "B"),
        (("runs", 0, "retry"), 2),
        (("runs", 0, "iterations", 1, "type"), "accepted"),
        (("runs", 0, "iterations", 1, "type"), None),
        (("runs", 0, "iterations", 0, "type"), "f"),
        (("runs", 0, "assumptions", 0, "status"), "fine"),
        (("runs", 0, "assumptions", 0, "status"), "checked()"),
        (("runs", 0, "projection", "source_map_sha256"), "1" * 63),
        (("spec", "revision_sha256"), "rev-668.0"),
        (("environment", "trf_module_sha256", "TRF.py"), "3" * 65),
        (("artifacts", "coupled_runs", 0, "sha256"), "X" * 64),
        (("claims", "trf_theory"), "qualified"),
        (("accounting", "budgets", "exhausted"), "time"),
        (("candidates", 0, "curvature", "T"), "flat"),
        (("runs", 0, "assumptions", 0, "id"), "A8"),
        (("runs", 0, "projection", "n_vars"), 1.5),
        (("candidates", 0, "label"), "certified"),
        (("candidates", 0, "checks", "P6"), {"pass": True, "values": {}}),
        (("candidates", 0, "checks", "P1", "pass"), "yes"),
        (("spec", "configs", "trf"), 3),
        (("unknown_field",), 1),
        (("candidates", 1, "indifference_halfwidth", T), -1e-12),
        # S12: no per-run ledger digest; the study ledger's is `artifacts.ledger`.
        (("runs", 0, "ledger", "sha256"), "5" * 64),
        (("artifacts", "ledger"), "5" * 63),
        (("artifacts", "ledger"), None),
        # S18: a listed coupled run has a coupling record.
        (("artifacts", "coupled_runs", 0, "sha256"), None),
        # S13: object or null.
        (("start",), []),
        (("stage_a",), "skipped"),
        # S14, S16: the holder summary and the truth identity are typed.
        (("runs", 0, "ledger", "summary", "reactor", "by_purpose", "trf_start_value"), -1),
        (("runs", 0, "ledger", "summary", "reactor", "pmp_point_equals_start"), None),
        (("runs", 0, "truth", 0, "gradient"), "numeric"),
        (("runs", 0, "basis", "reactor"), "taylor"),
        (("runs", 0, "exit_claim"), "converged"),
        # R-401: a ratio is a non-negative number, the bound flag a boolean.
        (("runs", 0, "final_step_ratio"), -0.5),
        (("runs", 0, "final_step_ratio"), "0.99"),
        (("runs", 0, "final_step_at_box_bound"), "yes"),
    ],
)
def test_the_schema_rejects(path: Sequence[Any], value: Any) -> None:
    assert list(VALIDATOR.iter_errors(_mutated(path, value)))


@pytest.mark.parametrize(
    "path, value",
    [
        (("candidates", 0, "checks", "P2", "pass"), None),
        (("runs", 0, "assumptions", 2, "status"), "qualified(FD gradient, check 3.1e-07)"),
        (("runs", 0, "assumptions", 1, "status"), "checked(1.2e-06)"),
        (("claims", "trf_theory"), "qualified(A2,A3)"),
        (("candidates", 0, "indifference_halfwidth"), None),
        (("candidates", 1, "indifference_halfwidth", T), 0.0),
        (("start",), None),
        (("stage_a",), None),
        (("best",), None),
        (("fd_check",), _fd_check_document()),
        (("runs", 0, "ledger", "summary", "reactor", "by_purpose", "trf_pmp_value"), 0),
        # R-401: nulls without a logged TRSP; the outcome is a free string; v1 records lack both.
        (("runs", 0, "final_step_ratio"), None),
        (("runs", 0, "final_step_at_box_bound"), True),
        (("runs", 0, "outcome"), "TRF_EXIT_UNVERIFIED(radius_limited)"),
        (("runs", 0, "final_step_ratio"), _DELETE),
        (("runs", 0, "final_step_at_box_bound"), _DELETE),
    ],
)
def test_the_schema_accepts(path: Sequence[Any], value: Any) -> None:
    """What the producer writes beyond the fakes: P2 not applicable (`checks.py`), §9.1's
    parametrised assumption statuses, the qualified claim (§6.9), a zero half-width (a parent
    with no noise, build log S36), S13's nulls and §17.2's `fd_check` document."""
    assert sorted(VALIDATOR.iter_errors(_mutated(path, value)), key=str) == []


@pytest.mark.parametrize(
    "path",
    [
        ("spec",),
        ("environment",),
        ("accounting",),
        ("claims",),
        ("artifacts",),
        ("status",),
        ("spec", "truth"),
        ("spec", "budgets"),
        ("runs", 0, "projection"),
        ("runs", 0, "ledger"),
        ("runs", 0, "final"),
        ("runs", 0, "assumptions"),
        ("candidates", 0, "checks"),
        ("candidates", 0, "noise_floor"),
        ("candidates", 0, "indifference_halfwidth"),
        ("candidates", 0, "limitations"),
        ("accounting", "by_candidate"),
        # S12, S13, S14
        ("artifacts", "ledger"),
        ("readiness",),
        ("start",),
        ("stage_a",),
        ("best",),
        ("fd_check",),
        ("runs", 0, "ledger", "summary"),
        ("runs", 0, "ledger", "cold_parent"),
        ("runs", 0, "exit_claim"),
        ("runs", 0, "theta_logged"),
        ("runs", 0, "theta_recheck"),
        ("runs", 0, "final_state_is_last_truth_point"),
        ("runs", 0, "ledger", "summary", "reactor", "by_purpose", "basis_fd_point"),
        ("runs", 0, "ledger", "summary", "reactor", "pmp_point_equals_start"),
        ("candidates", 0, "checks", "P2", "judged"),
    ],
)
def test_the_schema_requires(path: Sequence[Any]) -> None:
    assert list(VALIDATOR.iter_errors(_mutated(path, _DELETE)))


_P4_CHANGED = ("candidates", 0, "checks", "P4", "values", "changed", "flash")
_BASES: dict[str, Callable[[], dict[str, Any]]] = {"stable": _stable, "unsupported": _unsupported}


#: S14: every closed object, as (base record, what to set first, the object's path). The base
#: record with the set-up must validate; one undeclared field in the object must then fail.
CLOSED_OBJECTS: list[tuple[str, tuple[tuple[tuple[Any, ...], Any], ...], tuple[Any, ...]]] = [
    ("stable", (), ()),
    ("stable", (), ("spec",)),
    ("stable", (), ("spec", "configs")),
    ("stable", (), ("spec", "truth")),
    (
        "stable",
        ((("spec", "surrogate"), {"manifest_sha256": "6" * 64, "verdict": "x"}),),
        ("spec", "surrogate"),
    ),
    ("stable", (), ("environment",)),
    ("unsupported", (), ("readiness",)),
    ("unsupported", (), ("readiness", "reasons", 0)),
    ("stable", (), ("start",)),
    ("stable", (), ("start", "experiments")),
    ("stable", (), ("stage_a",)),
    ("stable", (), ("runs", 0)),
    ("stable", (), ("runs", 0, "truth", 0)),
    ("stable", (), ("runs", 0, "projection")),
    ("stable", (), ("runs", 0, "iterations", 0)),
    ("stable", (), ("runs", 0, "filter", 0)),
    ("stable", (), ("runs", 2, "final")),
    ("stable", (), ("runs", 0, "ledger")),
    ("stable", (), ("runs", 0, "ledger", "summary", "reactor")),
    ("stable", (), ("runs", 0, "ledger", "summary", "reactor", "by_purpose")),
    ("stable", (), ("runs", 0, "assumptions", 0)),
    ("stable", (), ("candidates", 0)),
    ("stable", (), ("candidates", 0, "checks")),
    ("stable", (), ("candidates", 0, "checks", "P1")),
    ("stable", (), ("candidates", 0, "checks", "P1", "values")),
    ("stable", (), ("candidates", 0, "checks", "P2")),
    ("stable", (), ("candidates", 0, "checks", "P2", "values")),
    (
        "stable",
        (
            (
                ("candidates", 0, "checks", "P2"),
                {
                    "pass": None,
                    "judged": False,
                    "reason": "no_trf_point",
                    "values": {"applicable": False},
                },
            ),
        ),
        ("candidates", 0, "checks", "P2", "values"),
    ),
    ("stable", (), ("candidates", 0, "checks", "P3")),
    ("stable", (), ("candidates", 0, "checks", "P3", "values")),
    ("stable", (), ("candidates", 0, "checks", "P4")),
    ("stable", (), ("candidates", 0, "checks", "P4", "values")),
    ("stable", ((_P4_CHANGED, {"reference": "two_phase", "found": "liquid"}),), _P4_CHANGED),
    ("stable", (), ("candidates", 0, "checks", "P5")),
    ("stable", (), ("candidates", 0, "checks", "P5", "values")),
    ("stable", (), ("candidates", 0, "checks", "P5", "values", "points", 0)),
    ("stable", (), ("candidates", 0, "poll", 0)),
    ("stable", (), ("candidates", 0, "noise_floor")),
    ("stable", (), ("candidates", 0, "noise_floor", "inner", 0)),
    ("stable", (), ("candidates", 0, "solves", 0)),
    ("stable", (), ("candidates", 0, "solves", 0, "experiments")),
    ("stable", (), ("best",)),
    ("stable", (), ("accounting",)),
    ("stable", (), ("accounting", "totals")),
    ("stable", (), ("accounting", "by_stage", "C")),
    ("stable", (), ("accounting", "by_iteration", "1")),
    ("stable", (), ("accounting", "by_candidate", "cand-C1")),
    ("stable", (), ("accounting", "budgets")),
    ("stable", (), ("claims",)),
    ("stable", ((("fd_check",), _fd_check_document()),), ("fd_check",)),
    ("stable", ((("fd_check",), _fd_check_document()),), ("fd_check", "candidates", 0)),
    ("stable", (), ("artifacts",)),
    ("stable", (), ("artifacts", "coupled_runs", 0)),
]


@pytest.mark.parametrize(
    "base, setup, path",
    CLOSED_OBJECTS,
    ids=[".".join(map(str, path)) or "<top>" for _, _, path in CLOSED_OBJECTS],
)
def test_the_schema_rejects_an_undeclared_field(
    base: str, setup: tuple[tuple[tuple[Any, ...], Any], ...], path: tuple[Any, ...]
) -> None:
    """S14: an undeclared field at any level fails, one case per closed object."""
    record = copy.deepcopy(_BASES[base]())
    for where, value in setup:
        _set(record, where, value)
    assert sorted(VALIDATOR.iter_errors(record), key=str) == []
    _set(record, (*path, "surprise"), 1)
    assert list(VALIDATOR.iter_errors(record))


# -- the identities catch a tampered record --------------------------------------------------------


@pytest.mark.parametrize(
    "path, value",
    [
        (("accounting", "totals", "trf_cold"), 10),
        (("accounting", "totals", "parent_executions"), 8),
        (("accounting", "by_stage", "C", "trf_cold"), 0),
        (("accounting", "by_iteration", "1", "parent_executions"), 9),
        (("accounting", "by_candidate", "cand-C2", "check_parent_executions"), 1),
        (("accounting", "budgets", "cold_used"), 1),
        (("accounting", "exhausted"), True),
        (("artifacts", "coupled_runs", 0, "sha256"), "x"),
        (("runs", 0, "cold"), 9),
    ],
)
def test_accounting_violations_catch_a_tampered_record(path: Sequence[Any], value: Any) -> None:
    assert accounting_violations(_stable()) == []
    assert accounting_violations(_mutated(path, value))


@pytest.mark.parametrize(
    "path, value",
    [
        (("status",), "FAILED(P1)"),
        (("candidates", 1, "status"), "NOT_STATIONARY_AT_DELTA"),
        (("claims", "stationarity"), "not_claimed"),
        (("candidates", 0, "status"), "PARENT_LOCAL_EVIDENCE"),
        # S15: null iff P5 did not run, else keyed by exactly the decision ids.
        (("candidates", 0, "indifference_halfwidth"), {}),
        (("candidates", 0, "indifference_halfwidth"), None),
        (("candidates", 0, "indifference_halfwidth"), {T: 0.02, "other": 0.1}),
        (("candidates", 0, "checks", "P5"), _DELETE),
    ],
)
def test_status_violations_catch_a_tampered_record(path: Sequence[Any], value: Any) -> None:
    assert status_violations(_stable()) == []
    assert status_violations(_mutated(path, value))


# -- §8.3's TRF request identity (S16, G12) --------------------------------------------------------

_C2_PURPOSES = ("runs", 2, "ledger", "summary", "reactor", "by_purpose")


@pytest.mark.parametrize(
    "purpose, value, expected",
    [
        ("trf_start_value", 2, 1),
        ("trf_pmp_value", 0, 1),
        ("trf_trial_value", 3, 2),
        ("basis_fd_point", 0, N_IN),
        ("trf_fd_point", 3 * N_IN, 2 * N_IN),
    ],
)
def test_the_request_identity_catches_each_broken_equality(
    purpose: str, value: int, expected: int
) -> None:
    """One synthetic record holds the identity on every run; breaking one equality on one run
    is caught, and nothing else is."""
    assert request_identity_violations(_stable()) == []
    record = _mutated((*_C2_PURPOSES, purpose), value)
    assert request_identity_violations(record) == [
        f"C2: {purpose} = {value}, §8.3 gives {expected}"
    ]


def test_the_request_identity_reads_pmp_point_equals_start() -> None:
    """`trf_pmp_value` = 0 holds with the flag, and 1 then breaks it (the PMP point adds no key)."""
    record = _mutated((*_C2_PURPOSES, "trf_pmp_value"), 0)
    _set(record, ("runs", 2, "ledger", "summary", "reactor", "pmp_point_equals_start"), True)
    assert request_identity_violations(record) == []
    _set(record, (*_C2_PURPOSES, "trf_pmp_value"), 1)
    assert request_identity_violations(record) == ["C2: trf_pmp_value = 1, §8.3 gives 0"]


def test_the_request_identity_follows_the_logged_iterations() -> None:
    """K and A come from the run's iterations: a first step rejected moves `trf_fd_point`'s
    expectation to n_in·(1 + 1 − 1); one more accepted iteration moves K and the FD points."""
    record = _mutated(("runs", 2, "iterations", 1, "type"), "rejected")
    assert request_identity_violations(record) == [
        f"C2: trf_fd_point = {2 * N_IN}, §8.3 gives {N_IN}"
    ]
    record = _stable()
    record["runs"][2]["iterations"].append({**record["runs"][2]["iterations"][-1], "k": 3})
    assert request_identity_violations(record) == [
        "C2: trf_trial_value = 2, §8.3 gives 3",
        f"C2: trf_fd_point = {2 * N_IN}, §8.3 gives {3 * N_IN}",
    ]


def test_r406_the_check_s_points_belong_to_the_first_stage_c_run() -> None:
    """R-406: the first stage-C run carries 1 + n_in·|η| check points (the escalated check
    evaluated η/4, η, 4η and 16η: 1 + 4·7 = 29), every other run none, whatever the basis policy
    (build log S54, dropped in WO-8e)."""
    record = copy.deepcopy(_stable_with_an_fd_check())  # the spec is a shared constant
    first_c = next(i for i, run in enumerate(record["runs"]) if run["stage"] == "C")
    name = record["runs"][first_c]["run_id"]
    purposes = ("runs", first_c, "ledger", "summary", "reactor", "by_purpose", "fdcheck_point")
    assert record["spec"]["configs"]["basis"] == "M05-basis-v1"
    assert request_identity_violations(record) == []
    _set(record, purposes, 0)
    assert request_identity_violations(record) == [f"{name}: fdcheck_point = 0, §8.3 gives 29"]
    _set(record, purposes, 29)
    _set(record, ("fd_check",), None)
    assert request_identity_violations(record) == [f"{name}: fdcheck_point = 29, §8.3 gives 0"]


def test_r400_a_v2_basis_block_has_two_curvature_points_per_link() -> None:
    record = _stable()
    run = record["runs"][2]
    link = {
        "stencil": "central",
        "t": 0.025,
        "d_points": [0.025, -0.025],
        "solves": ["CONVERGED", "CONVERGED"],
        "w_points": [[1.0], [1.0]],
        "v": [20.0],
        "c": [-0.38, 0.89],
        "status": "ok",
        "reason": None,
        "noise_ratio": None,
    }
    run["basis"] = {"policy": "M05-basis-v2", "kinds": run["basis"], "links": {"link:R": link}}
    assert sorted(VALIDATOR.iter_errors(record), key=str) == []
    name = run["run_id"]
    assert request_identity_violations(record) == [
        f"{name}: basis_curvature_point = 0, §8.3 gives 2"
    ]
    run["ledger"]["summary"]["reactor"]["by_purpose"]["basis_curvature_point"] = 2
    assert request_identity_violations(record) == []


def test_the_request_identity_applies_to_fd_truths_only() -> None:
    """An analytic truth is outside §8.3's identity; a surrogate basis is outside its basis term
    (§6.6); an FD truth that is one of several truths cannot be attributed and is reported."""
    record = _mutated(("runs", 2, "truth", 0, "gradient"), "analytic")
    _set(record, (*_C2_PURPOSES, "trf_start_value"), 5)
    assert request_identity_violations(record) == []
    record = _mutated(("runs", 2, "basis", "reactor"), "surrogate")
    _set(record, (*_C2_PURPOSES, "basis_fd_point"), 0)
    assert request_identity_violations(record) == []
    record = _mutated(("runs", 2, "truth"), [dict(FD_TRUTH), {**FD_TRUTH, "id": "second"}])
    assert VALIDATOR.is_valid(record)
    assert request_identity_violations(record) == [
        "C2: an FD truth among 2 truths and 1 holder summaries is not attributable to one summary"
    ]


# -- S18: only solves with a coupling record are listed -------------------------------------------


@dataclasses.dataclass
class UncoupledParent(FakeParent):
    """`FakeParent` without an external unit: no coupling, no residuals, no coupling record."""

    def solve(self, decisions: Mapping[str, float], *, solve_id: str, purpose: str) -> ParentSolve:
        solved = super().solve(decisions, solve_id=solve_id, purpose=purpose)
        return dataclasses.replace(
            solved, coupling=None, coupling_residuals=None, coupling_record_sha256=None
        )


def test_a_parent_without_an_external_unit_lists_no_coupled_run() -> None:
    """S18; and, with no noise floor (e* = e_j = 0), S36's exact zero half-width validates."""
    record = _document(study(UncoupledParent(), FullStage([(TRF_CONVERGED, 673.0)])))
    assert record["start"]["coupling_record_sha256"] is None
    assert record["candidates"][0]["indifference_halfwidth"] == {T: 0.0}
    assert record["candidates"] and record["candidates"][0]["solves"]
    assert record["artifacts"]["coupled_runs"] == []
    assert sorted(VALIDATOR.iter_errors(record), key=str) == []
    assert accounting_violations(record) == []
    assert status_violations(record) == []
    assert request_identity_violations(record) == []


def test_an_unsupported_record_states_its_reasons_and_runs_nothing() -> None:
    record = _unsupported()
    assert record["readiness"]["reasons"] == [
        {"code": "TRUST_REGION_FRAMEWORK_UNPINNED", "detail": "6.9"}
    ]
    assert record["runs"] == [] and record["candidates"] == [] and record["start"] is None
    assert record["accounting"]["totals"]["parent_solves"] == 0
    assert status_violations(
        _mutated(("status",), "UNSUPPORTED(START_NOT_CERTIFIED)", _unsupported)
    )


def test_the_default_install_study_is_unsupported_without_running_the_parent() -> None:
    """G12: without the `nlp` environment the answer is
    UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE) (the production `framework_readiness`
    reads the environment, no fake)."""
    try:
        import pyomo  # noqa: F401
    except ImportError:
        parent = FakeParent()
        found = run_study(
            parent, decisions=DECISIONS, start={T: 668.0}, stage_c=FullStage([]), budget=budget()
        )
        record = _document(found)
        assert record["status"] == "UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE)"
        assert parent.calls == []
        assert sorted(VALIDATOR.iter_errors(record), key=str) == []
    else:
        pytest.skip("Pyomo is installed")


# -- the classification of the record's digests (ADR 0025 D2.3; build decision S11) ---------------

POLICY_V2: dict[str, Any] = load_yaml(
    REPO_ROOT / "benchmarks" / "t08" / "numerical_policy_v2.yaml"
)["numerical_policy"]
EXTERNAL_M02: dict[str, Any] = t08_numerical_policy.external_policy()
EXTERNAL_M05: dict[str, Any] = t08_numerical_policy.external_policy(
    REPO_ROOT / "benchmarks" / "m05" / "numerical_policy_external.yaml"
)


def test_the_m05_addendum_is_audited_after_m02s_and_its_partition_holds() -> None:
    # Amended on purpose (ADR 0052, E01 escalation ESC-A1): E01's addendum is audited after M05's.
    assert [path.parent.name for path in t08_numerical_policy.ADDENDA] == ["m02", "m05", "e01"]
    assert EXTERNAL_M05["id"] == "M05-numerical-policy-external-v1"
    assert EXTERNAL_M05["schemas"] == ["trust-region-study.schema.json"]
    assert t08_numerical_policy.external_audit(POLICY_V2, EXTERNAL_M05, [EXTERNAL_M02]) == []
    declared = t08_numerical_policy.schema_sha256_names(external=True, addendum=EXTERNAL_M05)
    assert set(EXTERNAL_M05["exact_sha256"]) <= declared
    # v2's partition is computed without either addendum's files, so v2's content does not move.
    assert not declared & t08_numerical_policy.schema_sha256_names() - {"sha256", "manifest_sha256"}


def test_the_m05_partition_refuses_an_unclassified_and_a_reclassified_name() -> None:
    kept = [name for name in EXTERNAL_M05["exact_sha256"] if name != "revision_sha256"]
    missing = {**EXTERNAL_M05, "exact_sha256": kept}
    (problem,) = t08_numerical_policy.external_audit(POLICY_V2, missing, [EXTERNAL_M02])
    assert problem == "(m05) unclassified sha256 names: ['revision_sha256']"
    doubled = {**EXTERNAL_M05, "exact_sha256": [*EXTERNAL_M05["exact_sha256"], "variant_sha256"]}
    problems = t08_numerical_policy.external_audit(POLICY_V2, doubled, [EXTERNAL_M02])
    assert "(m05) already classified by an earlier addendum: ['variant_sha256']" in problems
    claimed = {**EXTERNAL_M05, "schemas": [*EXTERNAL_M05["schemas"], "experiment.schema.json"]}
    problems = t08_numerical_policy.external_audit(POLICY_V2, claimed, [EXTERNAL_M02])
    assert "(m05) schemas of an earlier addendum: ['experiment.schema.json']" in problems


# -- the classification of the record's floats (ADR 0007 D2.3; A32's rule, as M02's) --------------

FLOAT_RULES = [
    (re.compile(rule["path"]), rule["class"])
    for rule in EXTERNAL_M05["rules"]["trust_region_study"]
]


def _floats(node: Any, path: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _floats(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _floats(value, f"{path}[{index}]")
    elif isinstance(node, float):
        yield path


def test_the_m05_addendum_uses_m02s_four_classes() -> None:
    """Design note D14: the replay classes follow M02."""
    assert set(EXTERNAL_M05["classes"]) == set(EXTERNAL_M02["classes"])
    assert set(EXTERNAL_M05["rules"]) == {"trust_region_study"}
    assert all(cls in EXTERNAL_M05["classes"] for _, cls in FLOAT_RULES)


@pytest.mark.parametrize("make", _records())
def test_every_float_of_every_record_is_classified(make: Callable[[], dict[str, Any]]) -> None:
    """ADR 0007 D2.3 for M05's floats: each one matches a rule of the addendum."""
    found = list(_floats(make()))
    assert found  # every record carries the specification's decision box
    unclassified = [where for where in found if not any(p.fullmatch(where) for p, _ in FLOAT_RULES)]
    assert unclassified == []


def test_every_float_rule_classifies_a_float_of_the_generated_records() -> None:
    """No dead rule: a mistyped path would otherwise pass unnoticed."""
    paths = [where for make in GENERATED.values() for where in _floats(make())]
    dead = [p.pattern for p, _ in FLOAT_RULES if not any(p.fullmatch(where) for where in paths)]
    assert dead == []
