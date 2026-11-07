"""OPT WO-4: `optimize_revision` without Ipopt (design §4.5, §4.8, §4.12; gates G9's route
refusals, G11's library path). The solved cases are `test_opt_benchmarks_nlp.py` (audited env).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from t07_corpus import A02_FILES, CORPUS

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.revision_run import select_route
from openflowsheet.application.types import schema_errors
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.studies.nlp.closure import SolverAvailability
from openflowsheet.studies.nlp.host import CertifiedPoint
from openflowsheet.studies.nlp.revision import (
    MANIFEST,
    REPORT,
    REQUEST,
    REVISION,
    optimization_sha256,
    optimize_revision,
)
from openflowsheet.studies.nlp.revision_host import RevisionNlpHost
from openflowsheet.verify.certificate import CheckPolicy

REPO = Path(__file__).resolve().parents[1]
OPT = REPO / "benchmarks" / "opt"
POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert POLICY is not None
AVAILABLE = SolverAvailability(True, "test double: an audited solver")
UNAVAILABLE = SolverAvailability(False, "test double: no audited solver")


def _case(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = json.loads((OPT / "expected.json").read_bytes())
    flowsheet = expected["flowsheets"][name]
    document = json.loads((OPT / "flowsheets" / f"{flowsheet}.json").read_bytes())
    return document, json.loads((OPT / "requests" / f"{name}.json").read_bytes())


def _optimize(document: Any, request: Any, directory: Path | None, probe: Any) -> Any:
    return optimize_revision(
        document,
        request,
        directory=directory,
        solve_policy=POLICY,
        check_policy=CheckPolicy(),
        solver_probe=lambda: probe,
    )


def test_the_analytic_expectations_and_requests_are_current() -> None:
    """`benchmarks/opt/analytic.py --check`: the requests and mpmath expectations committed are
    the ones the script computes from the SYN-001 coefficient table."""
    result = subprocess.run(
        [sys.executable, str(OPT / "analytic.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("case", ["OPT-A1", "OPT-A2", "OPT-A2b", "OPT-C0", "OPT-N1"])
def test_the_benchmark_flowsheets_bind_on_revision_eo(case: str) -> None:
    document, _ = _case(case)
    assert getattr(select_route(document), "solve_path", None) == "revision_eo"


def test_g11_without_an_audited_solver_the_library_reports_unsupported(tmp_path: Path) -> None:
    document, request = _case("OPT-A1")
    outcome = _optimize(document, request, tmp_path / "record", UNAVAILABLE)
    report = outcome.report.as_document()
    assert report["status"] == "UNSUPPORTED"
    assert [reason["code"] for reason in report["reasons"]] == ["NLP_SOLVER_UNAVAILABLE"]
    assert schema_errors("optimization-report.schema.json", report) == []
    revision = report["revision"]
    assert revision["revision_sha256"] == document_sha256(document)
    assert revision["decision_parameters"] == {"SPEC-Q": "U-PHF.Q_spec"}
    assert revision["optimization_sha256"] == optimization_sha256(
        revision["request_sha256"],
        revision["revision_sha256"],
        "revision_eo",
        revision["solve_policy_sha256"],
        revision["check_policy_sha256"],
    )
    # The record: request, revision, report and manifest, each member's SHA-256 recorded.
    record = outcome.record_dir
    manifest = json.loads((record / MANIFEST).read_bytes())
    assert manifest["format"] == "openflowsheet-optimization-v1"
    assert set(manifest["members"]) == {REQUEST, REVISION, REPORT}
    for name, sha in manifest["members"].items():
        assert document_sha256(json.loads((record / name).read_bytes())) == sha
    assert (record / REQUEST).read_bytes() == canonical_json(request)


def test_an_unaudited_nlp_stack_is_unsupported_before_any_solve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-44 (R-190, G-A10): an available solver whose loaded stack is not the audited one (here
    PyNumero's ASL from `~/.pyomo/lib`, as `greybox.environment_problems` reports it) refuses the
    optimisation as M03's `optimize` does — `UNSUPPORTED(NLP_SOLVER_UNAVAILABLE)` naming the
    audit, the starts certified but no Ipopt call."""
    from openflowsheet.studies.nlp import revision

    problem = (
        "PyNumero loads /home/user/.pyomo/lib/libpynumero_ASL.so (sha256 00), not the audited "
        "build; set PYOMO_CONFIG_DIR=<env>/share/pyomo"
    )

    def solve_start(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Ipopt was called on an unaudited stack")

    adapter = SimpleNamespace(
        ipopt_version=lambda: "test-double",
        environment_problems=lambda: [problem],
        solve_start=solve_start,
    )
    monkeypatch.setattr(revision, "importlib", SimpleNamespace(import_module=lambda name: adapter))
    document, request = _case("OPT-A1")
    outcome = _optimize(document, request, tmp_path / "record", AVAILABLE)
    report = outcome.report.as_document()
    assert schema_errors("optimization-report.schema.json", report) == []
    assert report["status"] == "UNSUPPORTED"
    (reason,) = report["reasons"]
    assert reason["code"] == "NLP_SOLVER_UNAVAILABLE", reason
    assert reason["detail"].startswith(problem) and "(G-A10: PASS)" in reason["detail"], reason
    assert report["candidate"] is None and report["starts"] == []
    assert report["formulation"]["decisions"], report["formulation"]
    (points,) = outcome.points
    assert points.start is not None and points.start.verified and points.candidate is None


def test_g11_a_fresh_interpreter_loads_neither_pyomo_nor_cyipopt() -> None:
    script = f"""
import json, sys
sys.path.insert(0, {str(REPO / "tests")!r})
from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.studies.nlp.closure import SolverAvailability
from openflowsheet.studies.nlp.revision import optimize_revision
from openflowsheet.verify.certificate import CheckPolicy
opt = {str(OPT)!r}
document = json.load(open(opt + "/flowsheets/OPT-A1.json"))
request = json.load(open(opt + "/requests/OPT-A1.json"))
outcome = optimize_revision(document, request, directory=None,
    solve_policy=resolve_policy(DEFAULT_POLICY_ID, "revision_eo"), check_policy=CheckPolicy(),
    solver_probe=lambda: SolverAvailability(False, "double"))
assert outcome.report.status == "UNSUPPORTED"
print(sorted(m for m in ("pyomo", "cyipopt") if m in sys.modules))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_g9_routes_other_than_revision_eo_are_unsupported() -> None:
    _, request = _case("OPT-A1")
    legacy = CORPUS[A02_FILES[0]]()
    assert getattr(select_route(legacy), "solve_path", None) == "legacy_eo"
    report = _optimize(legacy, request, None, AVAILABLE).report.as_document()
    assert report["status"] == "UNSUPPORTED"
    assert "OPTIMIZATION_ROUTE_UNAVAILABLE" in [r["code"] for r in report["reasons"]]
    assert schema_errors("optimization-report.schema.json", report) == []
    coupled = json.loads((REPO / "benchmarks" / "m02" / "c1-loop-real.json").read_bytes())
    if getattr(select_route(coupled), "solve_path", None) != "revision_coupled":
        pytest.skip("c1-loop-real does not route revision_coupled here")
    report = _optimize(coupled, request, None, AVAILABLE).report.as_document()
    assert report["status"] == "UNSUPPORTED"
    assert "OPTIMIZATION_ROUTE_UNAVAILABLE" in [r["code"] for r in report["reasons"]]
    assert report["revision"]["decision_parameters"] is None
    assert schema_errors("optimization-report.schema.json", report) == []


def test_no_start_certified_is_unsupported_with_every_starts_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4.5: a start that fails the start phase is not run; when none passes the report is
    `UNSUPPORTED` with `SIMULATION_NOT_READY` and `START_NOT_CERTIFIED(<k>, <code>)` per start.
    No Ipopt is reached, so the default install runs it with a solver-probe double."""
    document, request = _case("OPT-A2")

    def refused(self: RevisionNlpHost, decisions: Any) -> CertifiedPoint:
        return CertifiedPoint(
            outcome="MAX_ITERATIONS",
            message="test double: the start does not converge",
            state=None,
            certificate=None,
            signature=None,
            bundle_ref=None,
            parameters=dict(decisions),
        )

    monkeypatch.setattr(RevisionNlpHost, "certify", refused)
    outcome = _optimize(document, request, tmp_path / "record", AVAILABLE)
    report = outcome.report.as_document()
    assert report["status"] == "UNSUPPORTED"
    assert [(r["code"], r["subject"]) for r in report["reasons"]] == [
        ("SIMULATION_NOT_READY", f"start {k}") for k in range(3)
    ]
    assert all(
        r["detail"].startswith(f"START_NOT_CERTIFIED({k}, MAX_ITERATIONS)")
        for k, r in enumerate(report["reasons"])
    )
    assert len(report["formulation"]["starts"]) == 3
    assert schema_errors("optimization-report.schema.json", report) == []
    assert [points.start.outcome for points in outcome.points] == ["MAX_ITERATIONS"] * 3
    assert all(points.candidate is None for points in outcome.points)


def test_an_ill_formed_request_is_an_error_not_a_report() -> None:
    document, request = _case("OPT-A1")
    with pytest.raises(ValueError, match="request_invalid"):
        _optimize(document, {**request, "decisions": []}, None, AVAILABLE)


# -- the assessment binding at the first passing start (D-18, D-26, D-32) ----------------------


def _c0(objective: dict[str, Any] | None = None, **extra: Any) -> tuple[Any, dict[str, Any]]:
    document, request = _case("OPT-C0")
    if objective is not None:
        request = {**request, "objective": {**request["objective"], **objective}}
    return document, {**request, **extra}


def _named(output: str) -> dict[str, Any]:
    return {"expression": {**_c0()[1]["objective"]["expression"], "linear": {output: 1}}}


@pytest.mark.parametrize(
    ("output", "code"),
    [
        ("assessment:tac", "ASSESSMENT_OUTPUT_UNAVAILABLE"),
        ("assessment:opex.NOPE", "ASSESSMENT_OUTPUT_UNKNOWN"),
    ],
)
def test_an_output_the_program_cannot_bind_refuses_the_request(
    tmp_path: Path, output: str, code: str
) -> None:
    """The program planned at start 0 publishes `tac` as null (no capital chain) and has no
    `opex.NOPE`: `UNSUPPORTED` with that program-wide reason, before any Ipopt import. The
    report records the assessment's identity; no start was run."""
    document, request = _c0(_named(output))
    outcome = _optimize(document, request, tmp_path / "record", AVAILABLE)
    report = outcome.report.as_document()
    assert report["status"] == "UNSUPPORTED"
    assert [(r["code"], r["subject"]) for r in report["reasons"]] == [
        (code, output.removeprefix("assessment:"))
    ]
    assert report["starts"] == [] and report["candidate"] is None
    assert schema_errors("optimization-report.schema.json", report) == []
    assert outcome.points[0].start is not None and outcome.points[0].start.verified


def test_an_unscaled_assessment_objective_fails_the_start(tmp_path: Path) -> None:
    """E01 review S1 at the revision's start: `opex` (2419.2 USD/yr at Q = 10500 W) left at
    scale 1 is outside `[1e-3, 1e3]`; the start does not pass, so no start does."""
    document, request = _c0({"scale": 1.0})
    report = _optimize(document, request, None, AVAILABLE).report.as_document()
    assert report["status"] == "UNSUPPORTED"
    assert [(r["code"], r["subject"]) for r in report["reasons"]] == [
        ("SIMULATION_NOT_READY", "start 0")
    ]
    assert report["reasons"][0]["detail"].startswith(
        "START_NOT_CERTIFIED(0, ASSESSMENT_OBJECTIVE_UNSCALED)"
    )
    assert schema_errors("optimization-report.schema.json", report) == []


def test_an_assessment_named_by_no_expression_is_not_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request carrying an assessment that no expression names optimises as without one: the
    program is never planned (OPT-A1 with C0's assessment reaches the solve unchanged)."""
    from openflowsheet.studies.nlp import revision

    document, request = _case("OPT-A1")
    request = {**request, "assessment": _c0()[1]["assessment"]}

    class ReachedError(Exception):
        pass

    def stop(name: str) -> Any:
        raise ReachedError(name)

    monkeypatch.setattr(revision.AssessmentProgram, "build", None)
    monkeypatch.setattr(revision, "importlib", SimpleNamespace(import_module=stop))
    with pytest.raises(ReachedError, match=r"greybox"):
        _optimize(document, request, None, AVAILABLE)
