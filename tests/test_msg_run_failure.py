"""MSG WO-6: `RunResult.failure`, `raise_for_outcome` and `SolveFailedError` (design note §3.4,
§4.8; ADR 0058 D5).

- FB-03's repro (corpus C01, the boiler at 973.15 K) gives `failure.code ==
  "phase_regime_mismatch"`, with the turbine `T` and the stream `S4` among its elements;
- `raise_for_outcome` raises `SolveFailedError`, whose first line is the explanation's summary,
  and returns the result itself on a converged run;
- a 0.3-shaped job (no `diagnosis` in its run facts) still yields `failure`, without numbers; an
  unreadable failure bundle yields the failure of the outcome alone, and reading never raises;
- the run result's document is schema-valid and round-trips, on every transport that carries
  `get_job_result`;
- the CLI: `api` prints the failure's text on stderr; `inspect` prints it under `=== failure`.

The converse — `failure` non-null iff a `failure_bundle` output, over every solve the suite
reads back — is the session fixture in `tests/conftest.py`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from test_msg_surfaces import _c01

from openflowsheet.application import cli
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.store import DATABASE_NAME
from openflowsheet.application.types import (
    ApiError,
    Change,
    RunFailure,
    RunResult,
    SolveFailedError,
    schema_errors,
)
from openflowsheet.messages.render import render_failure

RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"


class Solved:
    def __init__(self, project: Path, failed: RunResult, converged: RunResult) -> None:
        self.project, self.failed, self.converged = project, failed, converged


@pytest.fixture(scope="module")
def solved(tmp_path_factory: pytest.TempPathFactory) -> Solved:
    project = tmp_path_factory.mktemp("msg-wo6") / "project"
    with LocalApplication.create(project, project_id="msg-wo6") as app:
        results = []
        for suffix, document in (
            ("c01", _c01()),
            ("nominal", json.loads(RANKINE.read_text(encoding="utf-8"))),
        ):
            change, _, key = Change.from_change_set(document)
            head = app.get_project().head
            committed = app.commit_change(change, head, f"{key}-{suffix}")
            assert committed.revision_id is not None
            results.append(app.solve(committed.revision_id, "default"))
    failed, converged = results
    assert failed.outcome == "INITIALIZATION_FAILED"
    assert (converged.outcome, converged.verification_status) == ("CONVERGED", "VERIFIED")
    return Solved(project, failed, converged)


def test_fb03_the_failure_names_the_inner_cause_and_its_elements(solved: Solved) -> None:
    failure = solved.failed.failure
    assert failure is not None
    assert failure.code == "phase_regime_mismatch"
    assert failure.chain == ("INITIALIZATION_FAILED", "initializer_failed", "phase_regime_mismatch")
    assert failure.outcome == "INITIALIZATION_FAILED"
    assert failure.message == "initializer_failed(T): phase_regime_mismatch(S4)"
    assert failure.failure_bundle == f"{solved.failed.job_id}:bundle/failure-bundle.json"
    assert {"T", "S4"} <= {element["id"] for element in failure.explanation["elements"]}
    assert failure.explanation["kind"] == "input"
    assert failure.explanation == render_failure(
        outcome=failure.outcome,
        message=failure.message,
        context=_context(solved, failure),
    )
    # The bundle's own members, verbatim.
    with LocalApplication.open(solved.project) as app:
        bundle = json.loads(app.artifact_bytes(failure.failure_bundle))
    assert failure.taxonomy == bundle["taxonomy"]
    assert list(failure.implicated) == bundle["implicated_sources"]
    assert list(failure.suggested_actions) == [a["action"] for a in bundle["suggested_actions"]]
    assert solved.converged.failure is None


def _context(solved: Solved, failure: RunFailure) -> Any:
    from openflowsheet.messages.render import RenderContext

    with LocalApplication.open(solved.project) as app, app._store.reading() as connection:
        revision = app._store.get_revision(connection, solved.failed.revision_id)
    assert revision is not None
    return RenderContext(
        revision=revision.document,
        revision_id=solved.failed.revision_id,
        job_id=solved.failed.job_id,
        bundle_id=failure.failure_bundle.rpartition("/")[0],
    )


def test_raise_for_outcome_raises_solve_failed_with_the_summary_first(solved: Solved) -> None:
    with pytest.raises(SolveFailedError) as raised:
        solved.failed.raise_for_outcome()
    assert not isinstance(raised.value, ApplicationError)
    assert raised.value.result is solved.failed
    failure = solved.failed.failure
    assert failure is not None
    text = str(raised.value)
    assert text.split("\n")[0] == failure.explanation["summary"]
    assert text == str(failure)
    assert text.split("\n")[-1] == (f"  Details: {failure.message} — {failure.failure_bundle}")
    assert solved.converged.raise_for_outcome() is solved.converged


def test_raise_for_outcome_on_an_operational_error_and_a_job_that_did_not_complete(
    solved: Solved,
) -> None:
    import dataclasses

    error = ApiError(code="internal_error", message="a defect", retryable=False)
    errored = dataclasses.replace(solved.converged, error=error)
    with pytest.raises(ApplicationError) as raised:
        errored.raise_for_outcome()
    assert raised.value.error == error
    cancelled = dataclasses.replace(
        solved.converged,
        job_status="cancelled",
        outcome=None,
        verification_status=None,
        outputs=(),
    )
    with pytest.raises(SolveFailedError) as stopped:
        cancelled.raise_for_outcome()
    assert stopped.value.args == (f"cancelled: job {cancelled.job_id}",)
    assert str(stopped.value).split("\n")[-1] == f"  Details: cancelled: job {cancelled.job_id}"


def test_a_failure_requires_a_failure_bundle_output(solved: Solved) -> None:
    import dataclasses

    with pytest.raises(ValueError, match="no failure_bundle output"):
        dataclasses.replace(solved.converged, failure=solved.failed.failure)


def test_the_document_is_schema_valid_and_round_trips(solved: Solved) -> None:
    for result in (solved.failed, solved.converged):
        document = result.as_document()
        assert schema_errors("run-result.schema.json", document) == []
        assert RunResult.from_document(document) == result
    failure = solved.failed.failure
    assert failure is not None
    assert RunFailure.from_document(failure.as_document()) == failure
    missing = {k: v for k, v in solved.failed.as_document().items() if k != "failure"}
    assert any(
        "'failure' is a required property" in e
        for e in schema_errors("run-result.schema.json", missing)
    )


def test_get_job_result_carries_the_failure(solved: Solved) -> None:
    with LocalApplication.open(solved.project) as app:
        response = dispatch(app, "get_job_result", {"job_id": solved.failed.job_id})
    failure = response["run_result"]["failure"]
    assert failure == json.loads(json.dumps(solved.failed.failure.as_document()))  # type: ignore[union-attr]


def _worker_run(project: Path, job_id: str) -> dict[str, Any]:
    connection = sqlite3.connect(project / DATABASE_NAME)
    try:
        (text,) = connection.execute(
            "SELECT worker_result FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    finally:
        connection.close()
    return dict(json.loads(text))


def _set_worker_result(project: Path, job_id: str, document: dict[str, Any]) -> None:
    connection = sqlite3.connect(project / DATABASE_NAME)
    try:
        with connection:
            connection.execute(
                "UPDATE jobs SET worker_result = ? WHERE job_id = ?",
                (json.dumps(document), job_id),
            )
    finally:
        connection.close()


def test_a_0_3_shaped_job_still_yields_its_failure_without_numbers(
    solved: Solved, tmp_path: Path
) -> None:
    import shutil

    project = tmp_path / "copy"
    shutil.copytree(solved.project, project)
    worker = _worker_run(project, solved.failed.job_id)
    worker["run"] = {k: v for k, v in worker["run"].items() if k != "diagnosis"}
    _set_worker_result(project, solved.failed.job_id, worker)
    with LocalApplication.open(project) as app:
        result = app.get_job_result(solved.failed.job_id).run_result
    assert result is not None and result.failure is not None
    assert result.failure.code == "phase_regime_mismatch"
    assert result.failure.explanation["numbers"] == []


def test_an_unreadable_failure_bundle_gives_the_failure_of_the_outcome_alone(
    solved: Solved, tmp_path: Path
) -> None:
    import shutil

    project = tmp_path / "copy"
    shutil.copytree(solved.project, project)
    failure = solved.failed.failure
    assert failure is not None
    with LocalApplication.open(project) as app:
        row = app._store.artifact(failure.failure_bundle)
        assert row is not None
        (app.files_root / row.relpath).write_text("not json", encoding="utf-8")
        result = app.get_job_result(solved.failed.job_id).run_result
    assert result is not None and result.failure is not None
    alone = result.failure
    assert (alone.outcome, alone.message, alone.chain) == (
        "INITIALIZATION_FAILED",
        None,
        ("INITIALIZATION_FAILED",),
    )
    assert (alone.implicated, alone.suggested_actions) == ((), ())
    assert alone.taxonomy == failure.taxonomy  # from the outcome's taxonomy class
    assert schema_errors("run-result.schema.json", result.as_document()) == []


# ======================================================================== the command line


def test_the_cli_prints_a_runs_failure_on_stderr(
    solved: Solved, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["api", "get_job_result", "--project", str(solved.project)]
    code = cli.main([*argv, "--json", json.dumps({"job_id": solved.failed.job_id})])
    out, err = capsys.readouterr()
    assert code == 0
    failure = json.loads(out)["run_result"]["failure"]
    assert err.split("\n")[0] == failure["explanation"]["summary"]
    assert err.endswith(f"  Details: {failure['message']} — {failure['failure_bundle']}\n")
    code = cli.main([*argv, "--json", json.dumps({"job_id": solved.converged.job_id})])
    out, err = capsys.readouterr()
    assert (code, err) == (0, "")


def test_inspect_prints_the_failure_text_under_its_section(
    solved: Solved, capsys: pytest.CaptureFixture[str]
) -> None:
    failure = solved.failed.failure
    assert failure is not None
    with LocalApplication.open(solved.project) as app:
        row = app._store.artifact(failure.failure_bundle.rpartition("/")[0])
        assert row is not None
        directory = app.files_root / row.relpath
    assert cli.main(["inspect", str(directory)]) == 0
    out, _ = capsys.readouterr()
    section = out.split("=== failure", 1)[1].split("\n=== ", 1)[0]
    from openflowsheet.messages.render import RenderContext

    # A bundle read on its own has no project: no revision or job context.
    bare = render_failure(
        outcome=failure.outcome, message=failure.message, context=RenderContext(surface="cli")
    )
    assert f"\n  {bare['summary']}\n" in section
    assert bare["code"] == failure.code
    assert "    Do:      " in section and "    Kind:    " in section
