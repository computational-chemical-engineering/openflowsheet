"""T07 W1 follow-up: ruling round 1's schema and type edits, and the kinds W3 left unnamed.

Design note `docs/design/T07-jobs-and-bindings.md`, ruling round 1 R2.3 (`solve_body.policy_id`
defaults to the reserved `"default"`), R2.4 (`RunResult.solve_path` is `revision_eo | legacy_eo`),
R4 (`JobResult` = `{operation, run_result, replay_report, error}` in
`job.schema.json#/$defs/job_result`), R5 (`RELAXED` in `RunResult.verification_status`) and R6
(lifecycle rules 11 and 12, tested in `test_t07_lifecycle.py`); ruling round 2's `solution_state`
kind; and the `solve_path` kind of `solve-path.json` (§5.4 named none; W3 flagged it).
"""

from __future__ import annotations

import dataclasses
from typing import Any, get_args

import pytest
from conftest import REPO_ROOT, load_json
from t07_support import JOB_ID, ref

from openflowsheet.application import policies
from openflowsheet.application.jobs.model import ARTIFACT_FILE_NAMES, ARTIFACT_KINDS
from openflowsheet.application.types import (
    DEFAULT_SOLVE_POLICY_ID,
    ApiError,
    Budgets,
    DocumentSchemaError,
    JobRequest,
    JobResult,
    Limits,
    RunResult,
    SolveBody,
    SolvePath,
    VerificationStatus,
    _replay_report_build,
    schema_errors,
)
from openflowsheet.run.replay import ReplayReport

JOB_RESULT = "job.schema.json#/$defs/job_result"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas"


def _defs() -> dict[str, Any]:
    defs: dict[str, Any] = load_json(REPO_ROOT / "schemas" / "job.schema.json")["$defs"]
    return defs


def _run_result_properties() -> dict[str, Any]:
    properties: dict[str, Any] = load_json(REPO_ROOT / "schemas" / "run-result.schema.json")[
        "properties"
    ]
    return properties


# -- R2.3: the policy default ------------------------------------------------------------------


def test_the_solve_policy_default_is_the_reserved_default() -> None:
    assert _defs()["solve_body"]["properties"]["policy_id"]["default"] == "default"
    assert DEFAULT_SOLVE_POLICY_ID == policies.DEFAULT_POLICY_ID == "default"
    assert SolveBody("rev-1").policy_id == "default"
    omitted = {"operation": "solve", "idempotency_key": "k", "body": {"revision_id": "rev-1"}}
    assert JobRequest.from_document(omitted).body == SolveBody("rev-1", policy_id="default")
    # A registered id is still accepted as itself, and hashes differently from the alias.
    named = {**omitted, "body": {"revision_id": "rev-1", "policy_id": "T06-revision-v2"}}
    assert JobRequest.from_document(named).request_sha256 != (
        JobRequest.from_document(omitted).request_sha256
    )


# -- R2.4 and R5: the run-result enums ---------------------------------------------------------


def _run_result(**overrides: Any) -> RunResult:
    certificate = ref("solution_certificate", 1, name="solution-certificate.json")
    base = RunResult(
        job_id=JOB_ID,
        run_id=f"run-{JOB_ID}",
        revision_id="rev-1",
        revision_content_sha256="0" * 64,
        policy_id="T04-W12",
        policy_sha256="b" * 64,
        check_policy_sha256="c" * 64,
        job_status="completed",
        outcome="CONVERGED",
        verification_status="RELAXED",
        structural_sha256="d" * 64,
        outputs=(certificate, ref("run_manifest", 2, name="run-manifest.json")),
        solve_path="legacy_eo",
    )
    return dataclasses.replace(base, **overrides)


def test_run_result_solve_path_is_either_route() -> None:
    # M02 (ADR 0034 D2) adds `revision_coupled` to the schema; its producer and `SolvePath` are
    # WO-10's, so the two Python routes below are still every route a run takes today.
    assert _run_result_properties()["solve_path"]["enum"] == [
        "revision_eo",
        "legacy_eo",
        "revision_coupled",
    ]
    assert list(get_args(SolvePath)) == list(get_args(policies.SolvePath))
    for route in ("revision_eo", "legacy_eo"):
        result = _run_result(solve_path=route)
        assert schema_errors("run-result.schema.json", result.as_document()) == []
        assert RunResult.from_document(result.as_document()) == result
    for route in ("tear", "", None):
        document = {**_run_result().as_document(), "solve_path": route}
        assert schema_errors("run-result.schema.json", document) != []


def test_run_result_verification_status_is_the_certificates_own_enum() -> None:
    """R5: copied, never mapped — the enum is the certificate schema's, plus null."""
    certificate = load_json(REPO_ROOT / "schemas" / "solution-certificate.schema.json")
    verdicts = certificate["properties"]["verification_status"]["enum"]
    assert _run_result_properties()["verification_status"]["enum"] == [*verdicts, None]
    assert list(get_args(VerificationStatus)) == verdicts
    for verdict in verdicts:
        result = _run_result(verification_status=verdict)
        assert RunResult.from_document(result.as_document()) == result
    document = {**_run_result().as_document(), "verification_status": "PASSED"}
    assert schema_errors("run-result.schema.json", document) != []


# -- R4: JobResult ----------------------------------------------------------------------------


def _replay_report() -> ReplayReport:
    document = load_json(FIXTURES / "replay_report" / "valid" / "exact_match.json")
    return _replay_report_build(document)


ERROR = ApiError(code="unsupported", message="failure_bundle_unmapped(x)", retryable=False)


@pytest.mark.parametrize(
    "result",
    [
        JobResult("solve", _run_result(), None, None),
        JobResult(
            "solve",
            _run_result(
                job_status="failed",
                outcome=None,
                verification_status=None,
                outputs=(),
                error=ERROR,
            ),
            None,
            ERROR,
        ),
        JobResult("reproduce", None, _replay_report(), None),
        JobResult("reproduce", None, None, ERROR),
    ],
    ids=["solve", "solve-failed", "reproduce", "reproduce-no-report"],
)
def test_a_job_result_round_trips_through_its_schema(result: JobResult) -> None:
    document = result.as_document()
    assert list(document) == ["operation", "run_result", "replay_report", "error"]
    assert schema_errors(JOB_RESULT, document) == []
    rebuilt = JobResult.from_document(document)
    assert rebuilt == result
    assert rebuilt.as_document() == document


def test_the_replay_report_reader_inverts_as_document() -> None:
    for name in ("exact_match", "changed_dependency", "tampered_archive"):
        document = load_json(FIXTURES / "replay_report" / "valid" / f"{name}.json")
        assert _replay_report_build(document).as_document() == document


def test_a_job_result_refuses_the_other_operations_member() -> None:
    solve = JobResult("solve", _run_result(), None, None).as_document()
    reproduce = JobResult("reproduce", None, _replay_report(), None).as_document()
    broken = [
        {**solve, "run_result": None},
        {**solve, "replay_report": reproduce["replay_report"]},
        {**reproduce, "run_result": solve["run_result"]},
        {key: value for key, value in solve.items() if key != "error"},
        {**solve, "operation": "optimize"},
        {**solve, "extra": 1},
    ]
    for document in broken:
        assert schema_errors(JOB_RESULT, document) != [], document
        with pytest.raises(DocumentSchemaError):
            JobResult.from_document(document)
    with pytest.raises(ValueError, match="iff its operation is 'solve'"):
        JobResult("solve", None, None, None)
    with pytest.raises(ValueError, match="iff its operation is 'solve'"):
        JobResult("reproduce", _run_result(), None, None)
    with pytest.raises(ValueError, match="only a 'reproduce'"):
        JobResult("solve", _run_result(), _replay_report(), None)


# -- the artifact kinds ------------------------------------------------------------------------


def test_every_revision_bundle_file_has_a_kind() -> None:
    """§5.4's table plus ruling round 2's `solution_state` and the W1 follow-up's `solve_path`:
    every file `run_revision_session` can write is named by exactly one producer kind."""
    enum = _defs()["artifact_ref"]["properties"]["kind"]["enum"]
    assert list(ARTIFACT_KINDS) == enum == list(ARTIFACT_FILE_NAMES)
    assert ARTIFACT_FILE_NAMES["solve_path"] == "solve-path.json"
    assert ARTIFACT_FILE_NAMES["solution_state"] == "solution-state.json"
    names = [name for name in ARTIFACT_FILE_NAMES.values() if name is not None]
    assert len(names) == len(set(names))
    bundle_files = {
        "solve-events.json",
        "execution-plan.json",
        "solve-plan.json",
        "structural-report.json",
        "revision.json",
        "solve-policy.json",
        "check-policy.json",
        "solve-path.json",
        "solution-certificate.json",
        "solution-state.json",
        "failure-bundle.json",
        "run-manifest.json",
    }
    assert bundle_files <= set(names)
    document = ref("solve_path", name="solve-path.json").as_document()
    assert schema_errors("job.schema.json#/$defs/artifact_ref", document) == []


def test_policy_unsupported_on_route_is_the_unsupported_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R2.3 via §5.8: a listed (policy, route) pair is refused with the `unsupported` code (HTTP
    501), its message naming the pair; the list is empty, so nothing is refused today."""
    from t07_corpus import CORPUS

    import openflowsheet.application.admission as admission

    assert admission.POLICY_UNSUPPORTED_ON_ROUTE == frozenset()
    monkeypatch.setattr(
        admission, "POLICY_UNSUPPORTED_ON_ROUTE", frozenset({("T06-revision-v2", "revision_eo")})
    )
    refused = admission.admit_solve(
        "rev-1",
        CORPUS["SYN-001-nominal"](),
        SolveBody("rev-1"),
        budgets=Budgets(),
        limits=Limits(),
        active_jobs=0,
    )
    assert isinstance(refused, ApiError)
    assert (refused.code, refused.http_status) == ("unsupported", 501)
    assert refused.message == "policy_unsupported_on_route(T06-revision-v2,revision_eo)"
    assert refused.detail == {"policy_id": "T06-revision-v2", "solve_path": "revision_eo"}
