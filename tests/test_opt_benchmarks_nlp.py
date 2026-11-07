"""OPT WO-4 gates G7, G8, G9 (design §6): `optimize_revision` on the analytic cases.

The expectations are `benchmarks/opt/expected.json`, computed by `benchmarks/opt/analytic.py` with
mpmath from the SYN-001 coefficient table, independently of the provider and of the code under
test. Audited NLP environment only (`scripts/m03_nlp_check.sh`, `OMP_NUM_THREADS=1`).
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.types import schema_errors
from openflowsheet.canonical import document_sha256
from openflowsheet.studies.nlp.revision import (
    MANIFEST,
    REPORT,
    OptimizationOutcome,
    optimize_revision,
)
from openflowsheet.verify.certificate import CheckPolicy

pytestmark = pytest.mark.nlp

OPT = Path(__file__).resolve().parents[1] / "benchmarks" / "opt"
EXPECTED = json.loads((OPT / "expected.json").read_bytes())
POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert POLICY is not None


def _load(case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    flowsheet = EXPECTED["flowsheets"][case]
    document = json.loads((OPT / "flowsheets" / f"{flowsheet}.json").read_bytes())
    request = json.loads((OPT / "requests" / f"{case}.json").read_bytes())
    return document, request


@cache
def _run(case: str, directory: Path) -> OptimizationOutcome:
    document, request = _load(case)
    return optimize_revision(
        document,
        request,
        directory=directory / case,
        solve_policy=POLICY,
        check_policy=CheckPolicy(),
    )


@pytest.fixture(scope="module")
def records(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("opt-records")


def _expected(case: str, name: str) -> float:
    return float(EXPECTED[case][name])


def _check(case: str, outcome: OptimizationOutcome) -> dict[str, Any]:
    report = outcome.report.as_document()
    assert schema_errors("optimization-report.schema.json", report) == []
    assert outcome.record_dir is not None
    manifest = json.loads((outcome.record_dir / MANIFEST).read_bytes())
    assert manifest["optimization_sha256"] == report["revision"]["optimization_sha256"]
    assert manifest["members"][REPORT] == document_sha256(report)
    return report


def test_g7_opt_a1_reaches_the_analytic_optimum_and_multiplier(records: Path) -> None:
    report = _check("OPT-A1", _run("OPT-A1", records))
    assert report["status"] == "KKT_POINT_VERIFIED", report["reasons"]
    candidate = report["candidate"]
    q = candidate["decisions"]["U-PHF.Q_spec"]
    q_star = _expected("OPT-A1", "Q")
    assert abs(q - q_star) <= 1e-7 * q_star, (q, q_star)
    (multiplier,) = candidate["kkt"]["multipliers"].values()
    lam = _expected("OPT-A1", "multiplier")
    assert abs(multiplier - lam) <= 1e-4 * lam, (multiplier, lam)


def test_g8_opt_a2_every_start_verifies_one_solution(records: Path) -> None:
    report = _check("OPT-A2", _run("OPT-A2", records))
    assert report["status"] == "KKT_POINT_VERIFIED", report["reasons"]
    assert [s["classification"] for s in report["starts"]] == ["KKT_POINT_VERIFIED"] * 3
    assert report["distinct_local_solutions"] == 1
    candidate = report["candidate"]
    r, q = candidate["decisions"]["U-SPLIT.split_fraction"], candidate["decisions"]["U-PHF.Q_spec"]
    assert abs(r - _expected("OPT-A2", "r")) <= 1e-6, r
    assert abs(q - _expected("OPT-A2", "Q")) <= 1e-6 * _expected("OPT-A2", "Q"), q
    f_star = _expected("OPT-A2", "objective")
    assert abs(candidate["objective"] - f_star) <= 1e-8 * max(1.0, abs(f_star))


def test_g8_opt_a2b_the_outlet_temperature_as_decision_gives_the_same_optimum(
    records: Path,
) -> None:
    outcome = _run("OPT-A2b", records)
    report = _check("OPT-A2b", outcome)
    assert report["status"] == "KKT_POINT_VERIFIED", report["reasons"]
    assert [s["classification"] for s in report["starts"]] == ["KKT_POINT_VERIFIED"] * 3
    assert report["distinct_local_solutions"] == 1
    candidate = report["candidate"]
    r = candidate["decisions"]["U-SPLIT.split_fraction"]
    assert abs(r - _expected("OPT-A2b", "r")) <= 1e-6, r
    (best,) = (
        points.candidate
        for points, start in zip(outcome.points, report["starts"], strict=True)
        if start["final_decisions"] == candidate["decisions"]
    )
    assert best is not None and best.state is not None
    q = best.state["U-HEAT.Q"]  # the duty at the certified candidate
    assert abs(q - _expected("OPT-A2b", "Q")) <= 1e-6 * _expected("OPT-A2b", "Q"), q
    f_star = _expected("OPT-A2b", "objective")
    assert abs(candidate["objective"] - f_star) <= 1e-8 * max(1.0, abs(f_star))


def test_g9_opt_n1_is_refuted_by_the_regime_change(records: Path) -> None:
    report = _check("OPT-N1", _run("OPT-N1", records))
    assert report["status"] == "NOT_VERIFIED", report["reasons"]
    (reason,) = report["reasons"]
    assert "V4" in reason["detail"]
    (start,) = report["starts"]
    (v4,) = (check for check in start["checks"] if check["check"] == "V4")
    assert v4["outcome"] == "fail"
    assert v4["phase_regime_changed"] == ["PHASE_REGIME_CHANGED(U-PHF)"]
