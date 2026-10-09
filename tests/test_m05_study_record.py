"""M05 WO-7 (design note §9.1, §8.3, gate G12): the `trust-region-study-v1` schema and the record's
arithmetic, on records produced by `run_study` over the WO-6 fakes.

Default gate: no Pyomo, no solve. The identities are written as functions of a record so that WO-8's
committed records (`COMMITTED_RECORDS`) pass through the very same checks as the fakes'.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest
from conftest import REPO_ROOT
from jsonschema import Draft202012Validator
from test_m05_study_loop import (
    DECISIONS,
    FakeParent,
    FakeStage,
    T,
    budget,
    study,
)

from openflowsheet.studies.trust_region.study import run_study
from openflowsheet.studies.trust_region.trf_state import (
    TRF_CONFIG_V1,
    TRF_CONVERGED,
    TRF_STALLED_INCONSISTENT,
    FrameworkReadiness,
    ReadinessReason,
)

SCHEMA_PATH = REPO_ROOT / "schemas" / "trust-region-study.schema.json"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

#: WO-8's committed study records join here (G12: "the committed records validate and pass §8.3's
#: arithmetic"); every record found is run through `test_a_record_validates_and_adds_up`.
COMMITTED_RECORDS = sorted(
    (REPO_ROOT / "evidence" / "M05").glob("*/records/trust-region-study-*.json")
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


class FullStage(FakeStage):
    """`FakeStage` with a complete §9.1 `runs[]` entry: every key `TrfStage` writes, on dummy
    numbers (iteration 0 is the PMP, with no step type)."""

    def __call__(self, start: Any, *, run_id: str, radius_factor: float, budget: Any) -> Any:
        staged = super().__call__(start, run_id=run_id, radius_factor=radius_factor, budget=budget)
        decisions = staged.decisions
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
            "truth": [],
            "basis": {},
            "projection": {
                "source_map_sha256": "1" * 64,
                "n_vars": 9,
                "n_rows": 8,
                "n_block_efs": 1,
                "n_link_efs": 1,
                "n_ineq": 0,
            },
            "config": {
                **TRF_CONFIG_V1,
                "trust_radius": TRF_CONFIG_V1["trust_radius"] * radius_factor,
            },
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
            "error": None,
            "ledger": {"summary": {}, "cold_parent": 0},
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


def _document(found: Any) -> dict[str, Any]:
    document: dict[str, Any] = found.as_document(
        spec=SPEC,
        environment=ENVIRONMENT,
        trf_theory="assumptions_hold",
        limitations=("synthetic",),
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


def _iteration_limit() -> dict[str, Any]:
    script: list[tuple[str, float | None]] = [(TRF_CONVERGED, 660.0)] * 12
    return _document(study(FakeParent(), FullStage(script)))


GENERATED: dict[str, Callable[[], dict[str, Any]]] = {
    "decision_stable_with_a_retry": _stable,
    "candidate_failure": _failed_candidate,
    "start_not_certified": _start_not_certified,
    "budget_exhausted": _budget_exhausted,
    "unsupported": _unsupported,
    "iteration_limit": _iteration_limit,
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
    coupled = [item["check_id"] for item in record["artifacts"]["coupled_runs"]]
    if coupled != [s["check_id"] for s in solves]:
        found.append("artifacts.coupled_runs is not the solves in order")
    for solve, item in zip(solves, record["artifacts"]["coupled_runs"], strict=False):
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
    if status.startswith("FAILED(") and candidates:
        stopped = candidates[-1]["status"]
        if status not in (f"FAILED({stopped})",) and not status.startswith("FAILED(trf_aborted"):
            found.append("FAILED status is not the last candidate's")
    if record["claims"]["global_optimality"] is not False:
        found.append("global optimality claimed")
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


def _mutated(path: Sequence[Any], value: Any, base: Callable[[], dict[str, Any]] = _stable) -> Any:
    record = copy.deepcopy(base())
    node: Any = record
    for key in path[:-1]:
        node = node[key]
    if value is _DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return record


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
    ],
)
def test_the_schema_accepts(path: Sequence[Any], value: Any) -> None:
    """What the producer writes beyond the fakes: P2 not applicable (`checks.py`), §9.1's
    parametrised assumption statuses and the qualified claim (§6.9)."""
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
    ],
)
def test_the_schema_requires(path: Sequence[Any]) -> None:
    assert list(VALIDATOR.iter_errors(_mutated(path, _DELETE)))


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
    ],
)
def test_status_violations_catch_a_tampered_record(path: Sequence[Any], value: Any) -> None:
    assert status_violations(_stable()) == []
    assert status_violations(_mutated(path, value))


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
