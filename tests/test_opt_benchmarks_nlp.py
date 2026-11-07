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
from openflowsheet.canonical import canonical_json, document_sha256
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


def test_c0_an_assessment_objective_reaches_the_hand_cost_optimum(records: Path) -> None:
    """OPT-C0 (D-32): OPT-A1 with E01's heating-utility cost as the objective, the binding planned
    at the revision's start. Expected by hand (`benchmarks/opt/analytic.py`): opex = α·Q with
    α = 8 USD/GJ · 1e-9 GJ/J · 8000 h · 3600 s/h, so Q* and λ* are A1's and opex* = α·Q*."""
    report = _check("OPT-C0", _run("OPT-C0", records))
    assert report["status"] == "KKT_POINT_VERIFIED", report["reasons"]
    candidate = report["candidate"]
    q = candidate["decisions"]["U-PHF.Q_spec"]
    q_star = _expected("OPT-C0", "Q")
    assert abs(q - q_star) <= 1e-7 * q_star, (q, q_star)
    (multiplier,) = candidate["kkt"]["multipliers"].values()
    lam = _expected("OPT-C0", "multiplier")
    assert abs(multiplier - lam) <= 1e-4 * lam, (multiplier, lam)
    checks = {check["check"]: check for check in candidate["checks"]}
    assert checks["V7"]["outcome"] == "pass", checks["V7"]
    # The certified candidate's cost (float reference path, V6) is the hand formula at its Q.
    alpha = 8.0e-9 * 8000.0 * 3600.0
    opex = checks["V6"]["assessment_values"]["opex.total"]
    assert abs(opex - alpha * q) <= 1e-9 * alpha * q, (opex, alpha * q)
    opex_star = _expected("OPT-C0", "opex")
    assert abs(opex - opex_star) <= 1e-7 * opex_star, (opex, opex_star)
    # The binding's scale is max(|opex(x0)|, 1) at start 0 (Q = 10500 W).
    assessment = report["formulation"]["assessment"]
    (output,) = assessment["outputs"]
    assert output["id"] == "opex.total"
    assert abs(output["scale"] - alpha * 10500.0) <= 1e-12 * alpha * 10500.0, output


def test_the_record_holds_every_starts_files_by_hash(records: Path) -> None:
    """§4.8 on OPT-A2 (3 starts, all verified): per start the start bundle, `optimizer.json`,
    the candidate document, V1's bundle and `verification.json`, each a manifest member with its
    SHA-256; the manifest lists every file of the record and nothing else."""
    outcome = _run("OPT-A2", records)
    report = _check("OPT-A2", outcome)
    directory = outcome.record_dir
    assert directory is not None
    members = json.loads((directory / MANIFEST).read_bytes())["members"]
    files = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != MANIFEST
    }
    assert set(members) == files
    sha = report["revision"]["optimization_sha256"]
    for k, start in enumerate(report["starts"]):
        prefix = f"starts/{k}"
        for name in ("optimizer.json", "candidate-revision.json", "verification.json"):
            payload = (directory / prefix / name).read_bytes()
            document = json.loads(payload)
            assert canonical_json(document) == payload, name
            assert members[f"{prefix}/{name}"] == document_sha256(document), name
        optimizer = json.loads((directory / prefix / "optimizer.json").read_bytes())
        assert optimizer["iterations"] == start["iterations"]
        assert optimizer["options"]["max_iter"] == report["limits"]["max_iter"]
        assert 1 <= len(optimizer["iteration_rows"]) <= optimizer["iterations"] + 1
        decisions = start["final_decisions"]
        assert {n: optimizer["final_primal"][n] for n in decisions} == decisions
        # The candidate document is the base revision with the returned decisions written.
        written = {
            spec["id"]: spec.get("value")
            for spec in json.loads((directory / prefix / "candidate-revision.json").read_bytes())[
                "specifications"
            ]
        }
        assert written["SPEC-r"] == decisions["U-SPLIT.split_fraction"]
        assert written["SPEC-Q"] == decisions["U-PHF.Q_spec"]
        for bundle, run in (("start", f"-s{k}"), ("resolve", f"-r{k}")):
            assert start[f"{bundle}_record"] == f"{prefix}/{bundle}"
            inside = [m for m in members if m.startswith(f"{prefix}/{bundle}/")]
            assert inside, bundle
            text = "".join((directory / m).read_text(encoding="utf-8") for m in inside)
            assert f"opt-{sha[:16]}{run}" in text, (bundle, run)
