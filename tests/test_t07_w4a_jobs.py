"""T07 W4a: the job runner, the inline executor and `JobControl` on `LocalApplication`.

Design note `docs/design/T07-jobs-and-bindings.md` §4.2 (the methods; `solve` and `reproduce` as
submit → wait → result), §5.4 (outputs and kinds), §5.7 (`RunResult` consistency), §6 (the
lifecycle; every job this module produces is checked, gate G3), §8.1–§8.3 (cooperative
cancellation, wall time, the property-call tightening), §9.1 (the inline executor behind
`COMPUTE_LOCK`), §12.3 (bundles; G6's bundle identity), ruling round 1 R4–R5 and ruling round 2
(the solution state is a bundle member, never an output, never beside an interruption). The
expectations are the note's; the numbers compared against are what an independent direct call of
`run_revision_session` writes.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import (
    PATIENCE_S,
    cancel_while_queued,
    commit,
    lifecycle_violations,
    paused_at,
    response_schema_violations,
)

import openflowsheet.application.revision_run as revision_run
from openflowsheet.application.authz import grant
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.jobs.executor import COMPUTE_LOCK
from openflowsheet.application.jobs.model import lifecycle_warnings
from openflowsheet.application.jobs.runner import SOLVE_STAGES
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policies import (
    APPLICATION_POLICIES,
    DEFAULT_POLICY_ID,
    T06_REVISION_V2,
    resolve_policy,
)
from openflowsheet.application.revision_run import Route, run_revision_session, select_route
from openflowsheet.application.types import (
    Budgets,
    Job,
    JobRequest,
    Limits,
    ReplayPolicy,
    ReproduceBody,
    RunResult,
    SolveBody,
    schema_errors,
)
from openflowsheet.canonical import directory_hash, file_sha256
from openflowsheet.run.bundle import read_artifact, read_manifest, verify_bundle
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.verify.certificate import CheckPolicy
from openflowsheet.verify.checks import KIND_TOLERANCE, VerifierError

NOMINAL = "SYN-001-nominal"
#: One revision per shape: revision_eo with a certificate, legacy_eo with a certificate,
#: legacy_eo with a failure bundle (HOMOTOPY_STALLED, W3a), revision_eo on a T06 network.
G6_REVISIONS = (
    NOMINAL,
    "SYN-001-A02-360",
    "SYN-001-A02-352-vapor-guess-410",
    "SYN-001-T06-NET03",
)
#: W3-Q1: admitted, and ending at the registered initializer's refusal (ruling round 3, Q1).
INITIALIZER_REFUSED = "SYN-001-UL-C3X"
#: The manifest members that differ between two runs of one solve (§9.5 (2)); `run_id` is the
#: same here because the direct call is given the job's.
VOLATILE_MANIFEST = ("started_at", "elapsed_seconds", "hostname", "manifest_sha256")


# -- fixtures ------------------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    """A project on disk; on teardown, every job it holds passes §6.3 (G3)."""
    application = LocalApplication.create(tmp_path / "project", project_id="w4a")
    yield application
    try:
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []  # R4-G3
    finally:
        application.close()


@pytest.fixture
def memory() -> Iterator[LocalApplication]:
    application = LocalApplication.in_memory()
    yield application
    try:
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []  # R4-G3
    finally:
        application.close()


def _solve(app: LocalApplication, revision_id: str, key: str, **body: Any) -> Job:
    budgets = body.pop("budgets", Budgets())
    request = JobRequest("solve", key, SolveBody(revision_id=revision_id, **body), budgets=budgets)
    return app.submit_job(request).job


def _events(app: LocalApplication, job_id: str) -> list[Any]:
    snapshot = app.store.job_snapshot(job_id)
    assert snapshot is not None
    return snapshot[1]


def _path(app: LocalApplication, artifact_id: str) -> Path:
    row = app.store.artifact(artifact_id)
    assert row is not None, artifact_id
    return app.files_root / row.relpath


def _bundle_directory(app: LocalApplication, job: Job) -> Path:
    (bundle,) = [output for output in job.outputs if output.kind == "replay_bundle"]
    return _path(app, bundle.artifact_id)


# -- RunResult consistency (§5.7) ------------------------------------------------------------


def assert_run_result_consistent(app: LocalApplication, result: RunResult) -> None:
    """§5.7 and R4 against the job, its files and its bundle — never against the runner's own
    bookkeeping alone."""
    job = app.get_job(result.job_id)
    assert schema_errors("run-result.schema.json", result.as_document()) == []
    job_result = app.get_job_result(result.job_id)
    assert schema_errors("job.schema.json#/$defs/job_result", job_result.as_document()) == []
    assert job_result.run_result == result and job_result.replay_report is None
    assert (result.job_status, result.outputs, result.error) == (job.status, job.outputs, job.error)
    assert job_result.error == job.error
    body = job.request.body
    assert isinstance(body, SolveBody)
    assert result.revision_id == body.revision_id
    with app.store.reading() as connection:
        revision = app.store.get_revision(connection, body.revision_id)
    assert revision is not None
    assert result.revision_content_sha256 == revision.content_hash
    route = select_route(revision.as_document())
    assert isinstance(route, Route)
    assert result.solve_path == route.solve_path
    kinds = [output.kind for output in result.outputs]
    certified = "solution_certificate" in kinds
    # Non-null only with a certificate output, and then copied from that document.
    if certified:
        certificate = json.loads(_path(app, result.outputs[0].artifact_id).read_bytes())
        assert result.verification_status == certificate["verification_status"]
    else:
        assert result.verification_status is None
    if "run_manifest" in kinds:
        assert kinds in (
            ["solution_certificate", "run_manifest", "replay_bundle"],
            ["failure_bundle", "run_manifest", "replay_bundle"],
        )
        directory = _bundle_directory(app, job)
        manifest, _ = read_manifest(directory)
        assert result.run_id == manifest.run_id == f"run-{job.job_id}"
        assert result.outcome == manifest.outcome
        assert result.policy_id == manifest.policy_id
        assert result.policy_sha256 == manifest.policy_sha256
        assert result.check_policy_sha256 == manifest.check_policy_sha256
        assert result.structural_sha256 == manifest.structural_sha256
        assert manifest.verification_status == result.verification_status
        assert read_artifact(directory, "solve-path.json")["solve_path"] == result.solve_path
        assert verify_bundle(directory).ok
    else:
        assert (result.run_id, result.outcome, result.structural_sha256) == (None, None, None)
        assert kinds in ([], ["partial_solve_trace"])
    # The resolved policy (R2.3): "default" names the route's registered policy.
    requested = body.policy_id
    resolved = resolve_policy(requested, route.solve_path)
    assert resolved is not None and result.policy_id == resolved.policy_id


def test_solve_composition_returns_a_consistent_run_result(memory: LocalApplication) -> None:
    revision_id = commit(memory, CORPUS[NOMINAL]())
    result = memory.solve(revision_id, "default")
    assert_run_result_consistent(memory, result)
    assert result.job_id == "job-000001"
    assert (result.job_status, result.outcome, result.verification_status) == (
        "completed",
        "CONVERGED",
        "VERIFIED",
    )
    assert (result.solve_path, result.policy_id) == ("revision_eo", "T06-revision-v2")
    # Frank's application default: newton_refined with the F4 restart, the registered hash.
    assert result.policy_sha256 == policy_sha256(T06_REVISION_V2)
    assert result.check_policy_sha256 == CheckPolicy().sha256
    job = memory.get_job(result.job_id)
    assert job.request.idempotency_key.startswith("auto:")
    assert job.effective_budgets.max_property_calls == T06_REVISION_V2.max_property_calls
    # The six stages, in order, at their start, then the three outputs, then the end (§6.4).
    events = _events(memory, result.job_id)
    assert [event.kind for event in events] == [
        "accepted",
        "started",
        *["progress"] * 6,
        *["output"] * 3,
        "ended",
    ]
    stages = [(e.progress.completed, e.progress.total, e.progress.stage) for e in events[2:8]]
    assert stages == [(index, 6, stage) for index, stage in enumerate(SOLVE_STAGES)]
    assert job.ending is not None and (job.ending.reason, job.ending.interruption) == (
        "operation_completed",
        None,
    )


def test_a_legacy_eo_revision_solves_under_its_registered_policy(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS["SYN-001-A02-360"]())
    result = app.solve(revision_id, "default")
    assert_run_result_consistent(app, result)
    assert (result.solve_path, result.policy_id) == ("legacy_eo", "T04-W12")
    assert result.policy_sha256 == policy_sha256(APPLICATION_POLICIES["T04-W12"])
    assert result.verification_status == "VERIFIED"


def test_bundle_members_are_registered_and_only_three_are_outputs(app: LocalApplication) -> None:
    """§5.4 and ruling round 2: every bundle file is `<bundle id>/<file>` with its kind; the
    solution state and the route record are members, not outputs."""
    revision_id = commit(app, CORPUS[NOMINAL]())
    job = _solve(app, revision_id, "members")
    bundle_id = f"{job.job_id}:bundle"
    assert [output.artifact_id for output in job.outputs] == [
        f"{bundle_id}/solution-certificate.json",
        f"{bundle_id}/run-manifest.json",
        bundle_id,
    ]
    directory = _bundle_directory(app, job)
    assert job.outputs[2].sha256 == directory_hash(directory)
    members = {row.name: row for row in app.store.artifact_children(bundle_id)}
    manifest, _ = read_manifest(directory)
    assert set(members) == {*manifest.artifacts, "run-manifest.json"}
    assert members["solution-state.json"].kind == "solution_state"
    assert members["solve-path.json"].kind == "solve_path"
    assert "solution_state" not in [output.kind for output in job.outputs]
    for name, row in members.items():
        assert row.artifact_id == f"{bundle_id}/{name}"
        assert row.sha256 == file_sha256(app.files_root / row.relpath)
        assert row.job_id == job.job_id


def test_a_failure_bundle_job_completes(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS["SYN-001-A02-352-vapor-guess-410"]())
    result = app.solve(revision_id, "default")
    assert_run_result_consistent(app, result)
    assert (result.job_status, result.outcome) == ("completed", "HOMOTOPY_STALLED")
    assert [output.kind for output in result.outputs][0] == "failure_bundle"
    assert not (
        _bundle_directory(app, app.get_job(result.job_id)) / "artifacts" / ("solution-state.json")
    ).exists()


# -- G6: the job's bundle is `run_revision_session`'s -----------------------------------------


@pytest.mark.parametrize("name", G6_REVISIONS)
def test_g6_a_jobs_bundle_is_the_direct_calls(
    app: LocalApplication, tmp_path: Path, name: str
) -> None:
    """Byte-identical artifacts, and a manifest equal apart from its volatile members."""
    revision_id = commit(app, CORPUS[name]())
    job = _solve(app, revision_id, f"g6-{name}")
    with app.store.reading() as connection:
        revision = app.store.get_revision(connection, revision_id)
    assert revision is not None
    document = revision.as_document()
    route = select_route(document)
    assert isinstance(route, Route)
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None
    direct = tmp_path / "direct"
    run_revision_session(
        route,
        document,
        direct,
        run_id=f"run-{job.job_id}",
        policy=policy,
        check_policy=CheckPolicy(),
        policy_requested=DEFAULT_POLICY_ID,
    )
    jobs = _bundle_directory(app, job)
    ours = sorted(path.relative_to(jobs) for path in (jobs / "artifacts").rglob("*"))
    theirs = sorted(path.relative_to(direct) for path in (direct / "artifacts").rglob("*"))
    assert ours == theirs and ours
    for relative in ours:
        assert (jobs / relative).read_bytes() == (direct / relative).read_bytes(), relative
    documents = [
        {
            key: value
            for key, value in json.loads((root / "run-manifest.json").read_bytes()).items()
            if key not in VOLATILE_MANIFEST
        }
        for root in (jobs, direct)
    ]
    assert documents[0] == documents[1]


# -- typed ends without a bundle (§12.3) -------------------------------------------------------


def test_q1_a6_an_initializer_refusal_completes_with_a_failure_bundle(
    app: LocalApplication,
) -> None:
    """Ruling round 3, Q1-A6: the job-level half of item 1."""
    revision_id = commit(app, CORPUS[INITIALIZER_REFUSED]())
    result = app.solve(revision_id, "default")
    assert_run_result_consistent(app, result)
    assert (result.job_status, result.outcome, result.verification_status) == (
        "completed",
        "INITIALIZATION_FAILED",
        None,
    )
    assert [output.kind for output in result.outputs] == [
        "failure_bundle",
        "run_manifest",
        "replay_bundle",
    ]
    directory = _bundle_directory(app, app.get_job(result.job_id))
    assert not (directory / "artifacts" / "solution-state.json").exists()


def test_w3q1_an_unmapped_record_is_unsupported_with_no_bundle(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q1 item 4: a detail-less `INITIALIZATION_FAILED` step whose message no registered grammar
    accepts stays unmapped; the grammar is made to refuse UL-C3X's message to reach it."""
    monkeypatch.setattr(revision_run, "initializer_source", lambda _: None)
    revision_id = commit(app, CORPUS[INITIALIZER_REFUSED]())
    result = app.solve(revision_id, "default")
    assert_run_result_consistent(app, result)
    job = app.get_job(result.job_id)
    assert (job.status, job.ending.reason if job.ending else None) == ("failed", "operation_error")
    assert result.error is not None and result.error.code == "unsupported"
    assert result.error.message == (
        "failure_bundle_unmapped(INITIALIZATION_FAILED,solve_eo,NoneType)"
    )
    assert result.outputs == ()
    assert not (app.files_root / "jobs" / job.job_id / "bundle").exists()


def test_a_verifier_error_ends_failed_verifier_refused(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise VerifierError("the verifier's own flash returned FAILED: row 'x'")

    monkeypatch.setattr(revision_run, "verify_revision", refuse)
    revision_id = commit(app, CORPUS[NOMINAL]())
    result = app.solve(revision_id, "default")
    assert_run_result_consistent(app, result)
    job = app.get_job(result.job_id)
    assert job.ending is not None and (job.status, job.ending.reason) == (
        "failed",
        "verifier_refused",
    )
    assert result.error is not None and result.error.message == "verifier_refused"
    assert "row 'x'" not in json.dumps(result.error.as_document())  # D9 (4): no exception text
    assert result.outputs == () and not (app.files_root / "jobs" / job.job_id / "bundle").exists()


def test_a_solution_state_mismatch_ends_failed_with_no_bundle(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = revision_run.solution_state.document

    def skewed(variable_ids: Any, vector: Any) -> dict[str, Any]:
        return dict(real(variable_ids, vector), state_sha256="0" * 64)

    monkeypatch.setattr(revision_run.solution_state, "document", skewed)
    revision_id = commit(app, CORPUS[NOMINAL]())
    result = app.solve(revision_id, "default")
    assert result.job_status == "failed" and result.outputs == ()
    assert result.error is not None
    assert (result.error.code, result.error.message) == (
        "internal_error",
        "solution_state_mismatch",
    )


def test_an_untyped_exception_ends_failed_without_its_text(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: Any, **__: Any) -> Any:
        raise ValueError("secret detail GRANT policy")

    monkeypatch.setattr(revision_run, "execute_plan", broken)
    revision_id = commit(app, CORPUS[NOMINAL]())
    result = app.solve(revision_id, "default")
    assert result.job_status == "failed" and result.error is not None
    assert result.error.code == "internal_error"
    assert "secret" not in json.dumps(result.error.as_document())
    ending = app.get_job(result.job_id).ending
    assert ending is not None and (ending.status, ending.reason) == ("failed", "operation_error")
    assert result.outputs == ()


# -- cancellation (§8.1, G5 at the job level) --------------------------------------------------


def test_cancel_while_queued_ends_with_no_outputs(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    request = JobRequest("solve", "queued", SolveBody(revision_id))
    submitted, cancelled = cancel_while_queued(app, request)
    assert not submitted.replayed
    assert submitted.job == cancelled == app.get_job(cancelled.job_id)
    assert (cancelled.status, cancelled.outputs, cancelled.started_at) == ("cancelled", (), None)
    assert cancelled.cancel_requested
    assert cancelled.ending is not None
    assert cancelled.ending.as_document() == {
        "status": "cancelled",
        "reason": "cancel_requested",
        "interruption": None,
    }
    assert [event.kind for event in _events(app, cancelled.job_id)] == [
        "accepted",
        "cancel_requested",
        "ended",
    ]
    result = app.get_job_result(cancelled.job_id).run_result
    assert result is not None
    assert_run_result_consistent(app, result)
    assert (result.job_status, result.outputs, result.solve_path) == (
        "cancelled",
        (),
        "revision_eo",
    )
    # Idempotent: a second cancel changes nothing and never raises.
    assert app.cancel_job(cancelled.job_id) == cancelled
    assert len(_events(app, cancelled.job_id)) == 3


def _reference_events(app: LocalApplication, revision_id: str) -> tuple[list[Any], int]:
    """An uninterrupted job's solve events and the number of interruption checks it made."""
    counted: list[int] = []
    app.executor.test_hook_on_check = lambda _job, check: counted.append(check)
    try:
        job = _solve(app, revision_id, "reference")
    finally:
        app.executor.test_hook_on_check = None
    events = read_artifact(_bundle_directory(app, job), "solve-events.json")
    return events, len(counted)


def test_cancel_while_running_at_record_k(app: LocalApplication) -> None:
    """The hook cancels through `cancel_job` at the k-th check (a stage boundary or a
    `Trace.record`): the job ends `cancelled`, cooperative, with the events recorded so far as
    its only possible output — a prefix of the uninterrupted run's — and never a certificate, a
    failure bundle, a solution state or a solver outcome."""
    revision_id = commit(app, CORPUS[NOMINAL]())
    reference, checks = _reference_events(app, revision_id)
    assert checks > 21
    for k in (1, 2, 3, 5, 8, 13, 21, checks - 1, checks):

        def cancel_at(job_id: str, check: int, k: int = k) -> None:
            if check == k:
                app.cancel_job(job_id)

        app.executor.test_hook_on_check = cancel_at
        try:
            job = _solve(app, revision_id, f"cancel-{k}")
        finally:
            app.executor.test_hook_on_check = None
        assert job.status == "cancelled", k
        assert job.ending is not None
        assert (job.ending.reason, job.ending.interruption) == ("cancel_requested", "cooperative")
        assert job.cancel_requested and job.error is None
        kinds = [output.kind for output in job.outputs]
        assert kinds in ([], ["partial_solve_trace"]), (k, kinds)
        assert not (app.files_root / "jobs" / job.job_id / "bundle").exists()
        if kinds:
            partial = json.loads(_path(app, job.outputs[0].artifact_id).read_bytes())
            assert partial and partial == reference[: len(partial)], k
            assert job.outputs[0].artifact_id == f"{job.job_id}:partial-solve-events.json"
        result = app.get_job_result(job.job_id).run_result
        assert result is not None
        assert_run_result_consistent(app, result)
        assert (result.outcome, result.verification_status) == (None, None)
        # Rule 8 may warn (a stage in flight finishing); it is never a violation.
        snapshot = app.store.job_snapshot(job.job_id)
        assert snapshot is not None
        assert all(found.rule == 8 for found in lifecycle_warnings(*snapshot))
    # Past the last check the cancellation never fires: the run completes.
    app.executor.test_hook_on_check = lambda job_id, check: (
        app.cancel_job(job_id) if check == checks + 1 else None
    )
    try:
        job = _solve(app, revision_id, "cancel-never")
    finally:
        app.executor.test_hook_on_check = None
    assert job.status == "completed"


def _cancel_rows(app: LocalApplication) -> list[tuple[str, str, str]]:
    return [
        (row["principal_id"], row["outcome"], row["effect"])
        for row in app.store.audit_rows()
        if row["operation"] == "cancel_job"
    ]


def test_s10_1_a_cancel_of_an_ended_job_is_audited_and_changes_nothing(
    app: LocalApplication,
) -> None:
    """Ruling round 5, S10: every allowed `cancel_job` writes one `allowed` row, a no-op too."""
    job = _solve(app, commit(app, CORPUS[NOMINAL]()), "ended")
    assert job.status == "completed"
    events = _events(app, job.job_id)
    assert app.cancel_job(job.job_id) == app.get_job(job.job_id) == job
    assert _events(app, job.job_id) == events
    assert _cancel_rows(app) == [(app.principal_id, "allowed", f"cancel:{job.job_id}")]


def test_s10_2_a_running_job_cancelled_twice_has_two_rows_and_one_event(
    app: LocalApplication,
) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())

    def cancel_twice(job_id: str, check: int) -> None:
        if check == 3:
            app.cancel_job(job_id)
            app.cancel_job(job_id)

    app.executor.test_hook_on_check = cancel_twice
    try:
        job = _solve(app, revision_id, "twice")
    finally:
        app.executor.test_hook_on_check = None
    assert job.status == "cancelled"
    kinds = [event.kind for event in _events(app, job.job_id)]
    assert kinds.count("cancel_requested") == 1
    assert _cancel_rows(app) == [(app.principal_id, "allowed", f"cancel:{job.job_id}")] * 2


def test_s10_3_a_policy_holder_cancelling_anothers_ended_job_is_audited(
    app: LocalApplication,
) -> None:
    """The input V17's G16-a.R5-14 scores against the real store."""
    directory = app.store.directory
    assert directory is not None
    job = _solve(app, commit(app, CORPUS[NOMINAL]()), "owners")
    capability, _ = grant(directory, principal_id="admin", rights=("execute", "policy", "read"))
    with LocalApplication.open(directory, capability=capability) as admin:
        assert admin.cancel_job(job.job_id).status == "completed"
        assert _cancel_rows(admin) == [("admin", "allowed", f"cancel:{job.job_id}")]


def test_wall_time_exhausted_ends_timed_out(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    # A deadline passed before the first check: no stage runs, nothing is recorded.
    job = _solve(app, revision_id, "tiny", budgets=Budgets(wall_time_s=1e-9))
    assert job.status == "timed_out" and job.outputs == ()
    assert job.ending is not None
    assert (job.ending.reason, job.ending.interruption) == ("wall_time_exhausted", "cooperative")
    assert job.effective_budgets.wall_time_s == 1e-9
    # A clock advancing one unit per query crosses a deadline of 20.5 mid-solve.
    ticks = iter(range(10_000))
    app.executor.clock = lambda: float(next(ticks))
    try:
        job = _solve(app, revision_id, "ticks", budgets=Budgets(wall_time_s=20.5))
    finally:
        app.executor.clock = time.monotonic
    assert job.status == "timed_out"
    assert [output.kind for output in job.outputs] == ["partial_solve_trace"]
    result = app.get_job_result(job.job_id).run_result
    assert result is not None
    assert_run_result_consistent(app, result)


def test_keyboard_interrupt_cancels_the_job_and_is_reraised(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())

    def interrupt(_job: str, check: int) -> None:
        if check == 13:
            raise KeyboardInterrupt

    app.executor.test_hook_on_check = interrupt
    try:
        with pytest.raises(KeyboardInterrupt):
            _solve(app, revision_id, "keyboard")
    finally:
        app.executor.test_hook_on_check = None
    (job,) = [job for job in app.list_jobs().items if job.request.idempotency_key == "keyboard"]
    assert job.ending is not None
    assert (job.status, job.ending.reason) == ("cancelled", "keyboard_interrupt")
    assert [output.kind for output in job.outputs] in ([], ["partial_solve_trace"])
    assert not COMPUTE_LOCK.locked()


def test_wait_job_honours_cancellation_and_a_running_result_is_not_ready(
    app: LocalApplication,
) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    request = JobRequest("solve", "paused", SolveBody(revision_id))
    with paused_at(app, request, 5) as (pause, submitted):
        assert pause.job_id is not None
        job = app.get_job(pause.job_id)
        assert job.status == "running"
        with pytest.raises(ApplicationError) as raised:
            app.get_job_result(job.job_id)
        assert (raised.value.code, raised.value.error.retryable) == ("not_ready", True)
        last = _events(app, job.job_id)[-1].sequence
        # Nothing new while it is held: the wait times out, not ended.
        waited = app.wait_job(job.job_id, after_sequence=last, timeout_s=0.2)
        assert (waited.events, waited.ended) == ((), False)
        answers: list[Any] = []
        waiter = threading.Thread(
            target=lambda: answers.append(
                app.wait_job(job.job_id, after_sequence=last, timeout_s=PATIENCE_S)
            )
        )
        waiter.start()
        cancelled = app.cancel_job(job.job_id)
        waiter.join(PATIENCE_S)
        assert cancelled.cancel_requested and cancelled.status == "running"
        (answer,) = answers
        assert [event.kind for event in answer.events] == ["cancel_requested"]
    (result,) = submitted
    assert result.job.status == "cancelled"
    final = app.wait_job(result.job.job_id, after_sequence=last + 1, timeout_s=PATIENCE_S)
    assert final.ended and final.events[-1].kind == "ended"


# -- budgets and verification (§8.3, §10.5) ----------------------------------------------------


def test_a_property_call_tightening_exhausts_the_budget_inside_a_completed_job(
    app: LocalApplication,
) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    job = _solve(app, revision_id, "calls", max_property_calls=50)
    assert job.status == "completed"
    assert job.effective_budgets.max_property_calls == 50
    result = app.get_job_result(job.job_id).run_result
    assert result is not None
    assert_run_result_consistent(app, result)
    assert result.outcome == "BUDGET_EXHAUSTED"
    assert [output.kind for output in result.outputs][0] == "failure_bundle"
    effective = replace(T06_REVISION_V2, max_property_calls=50)
    assert result.policy_id == "T06-revision-v2"
    assert result.policy_sha256 == policy_sha256(effective) != policy_sha256(T06_REVISION_V2)
    directory = _bundle_directory(app, job)
    assert read_artifact(directory, "solve-policy.json") == effective.as_document()
    assert verify_bundle(directory).ok  # W3-Q4 admits the tightening


def test_looser_requests_are_refused_and_create_no_job(app: LocalApplication) -> None:
    """G12.10 and §5.3's ceilings: a refusal is raised, audited, and leaves no job and no ledger
    row (the same key then submits a valid request). G12.1–G12.9, the tightened grid of ruling
    round 5 M1, are `test_t07_g12_no_weakening.py`."""
    revision_id = commit(app, CORPUS[NOMINAL]())
    kind = sorted(KIND_TOLERANCE)[0]
    cases = [
        (
            SolveBody(revision_id, check_tolerances={kind: KIND_TOLERANCE[kind] * 2}),
            "verification_weakening_refused",
        ),
        (SolveBody(revision_id, check_tolerances={"no_such_kind": 1.0}), "invalid_request"),
        (
            SolveBody(revision_id, max_property_calls=T06_REVISION_V2.max_property_calls + 1),
            "budget_exceeds_ceiling",
        ),
        (SolveBody(revision_id, policy_id="no-such-policy"), "not_found"),
        (SolveBody("no-such-revision"), "not_found"),
    ]
    for body, code in cases:
        with pytest.raises(ApplicationError) as raised:
            app.submit_job(JobRequest("solve", "same-key", body))
        assert raised.value.code == code, body
        assert schema_errors("api-error.schema.json", raised.value.error.as_document()) == []
    assert app.store.job_ids() == ()
    refused = [row for row in app.store.audit_rows() if row["outcome"] == "refused"]
    assert [row["code"] for row in refused] == [code for _, code in cases]
    assert _solve(app, revision_id, "same-key").status == "completed"


def test_max_active_jobs_holds_under_concurrent_submissions(app: LocalApplication) -> None:
    """§5.3 step 8 (T07 review S4): the limit is checked inside the accepting transaction.
    Counted in a separate read, 16 concurrent submissions under a limit of 1 were all
    accepted. With the compute lock held no job can end, so exactly one is accepted."""
    directory = app.store.directory
    assert directory is not None
    revision_id = commit(app, CORPUS[NOMINAL]())
    capability, _ = grant(
        directory,
        principal_id="agent",
        rights=("read", "execute"),
        limits=Limits(default_wall_time_s=300, max_wall_time_s=1800, max_active_jobs=1),
    )
    agent = LocalApplication.open(directory, capability=capability)
    submissions = 16
    barrier = threading.Barrier(submissions)
    accepted: list[str] = []
    refused: list[str] = []

    def submit(index: int) -> None:
        request = JobRequest("solve", f"k-{index}", SolveBody(revision_id=revision_id))
        barrier.wait()
        try:
            accepted.append(agent.submit_job(request).job.job_id)
        except ApplicationError as error:
            refused.append(error.code)

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(submissions)]
    try:
        with COMPUTE_LOCK:
            for thread in threads:
                thread.start()
            deadline = time.monotonic() + PATIENCE_S
            while len(refused) < submissions - 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            assert refused == ["limit_exceeded"] * (submissions - 1)
            assert len(agent.store.job_ids()) == 1
        for thread in threads:
            thread.join(PATIENCE_S)
        assert len(accepted) == 1
        assert agent.get_job(accepted[0]).status == "completed"
    finally:
        agent.close()


def test_s5_t5_a_job_with_no_budget_and_no_default_runs_under_the_ceiling(
    app: LocalApplication,
) -> None:
    """Ruling round 5b, S5 (§8.3): the effective wall time is the request's, else the default,
    else the ceiling. Before, a capability with a ceiling and no default ran unbounded."""
    directory = app.store.directory
    assert directory is not None
    revision_id = commit(app, CORPUS[NOMINAL]())
    capability, _ = grant(
        directory,
        principal_id="agent",
        rights=("read", "execute"),
        limits=Limits(None, 1800, 4),
    )
    with LocalApplication.open(directory, capability=capability) as agent:
        job = agent.submit_job(JobRequest("solve", "no-budget", SolveBody(revision_id))).job
        assert agent.get_job(job.job_id).effective_budgets.wall_time_s == 1800


# -- idempotency, lists and waits (§4.2, §7, §11.4) --------------------------------------------


def test_a_resubmission_replays_and_a_different_request_is_refused(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    request = JobRequest("solve", "twice", SolveBody(revision_id))
    first = app.submit_job(request)
    again = app.submit_job(request)
    assert (first.replayed, again.replayed) == (False, True)
    assert again.job == first.job and app.store.job_ids() == (first.job.job_id,)
    changed = JobRequest("solve", "twice", SolveBody(revision_id, max_property_calls=10))
    with pytest.raises(ApplicationError) as raised:
        app.submit_job(changed)
    assert raised.value.code == "idempotency_key_reused"
    assert raised.value.error.detail["original_request_sha256"] == request.request_sha256


def test_lists_page_and_events_page(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    ids = [_solve(app, revision_id, f"list-{index}").job_id for index in range(3)]
    seen: list[str] = []
    cursor = None
    while True:
        page = app.list_jobs(cursor=cursor, limit=2)
        seen.extend(job.job_id for job in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    assert seen == ids
    assert [job.job_id for job in app.list_jobs(status="completed").items] == ids
    assert app.list_jobs(status="queued").items == ()
    events = _events(app, ids[0])
    after, paged = -1, []
    while True:
        page = app.list_job_events(ids[0], after_sequence=after, limit=5)
        paged.extend(page.items)
        if page.next_cursor is None:
            break
        after = int(page.next_cursor)
    assert paged == events
    for call, pointer in (
        (lambda: app.list_jobs(cursor="not-a-cursor"), "/cursor"),
        (lambda: app.list_jobs(limit=0), "/limit"),
        (lambda: app.list_jobs(limit=201), "/limit"),
        (lambda: app.list_jobs(status="finished"), "/status"),  # type: ignore[arg-type]
        (lambda: app.list_job_events(ids[0], limit=501), "/limit"),
        (lambda: app.list_job_events(ids[0], after_sequence=-2), "/after_sequence"),
        (lambda: app.wait_job(ids[0], timeout_s=-1.0), "/timeout_s"),
        (lambda: app.wait_job(ids[0], timeout_s=float("nan")), "/timeout_s"),
    ):
        with pytest.raises(ApplicationError) as raised:
            call()
        assert (raised.value.code, raised.value.error.detail["pointer"]) == (
            "invalid_request",
            pointer,
        )
    for call in (
        lambda: app.get_job("job-999999"),
        lambda: app.list_job_events("job-999999"),
        lambda: app.wait_job("job-999999", timeout_s=0),
        lambda: app.cancel_job("job-999999"),
        lambda: app.get_job_result("job-999999"),
    ):
        with pytest.raises(ApplicationError) as raised:
            call()
        assert raised.value.code == "not_found"
    # An ended job: the wait returns at once, ended, with whatever follows the sequence given.
    waited = app.wait_job(ids[0], after_sequence=events[-1].sequence, timeout_s=PATIENCE_S)
    assert (waited.events, waited.ended) == ((), True)


# -- reproduce (§4.2, §12.3) -------------------------------------------------------------------


def test_reproduce_without_rerun_has_one_output(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    solved = _solve(app, revision_id, "to-reproduce")
    job = app.submit_job(
        JobRequest("reproduce", "inspect", ReproduceBody(f"{solved.job_id}:bundle", rerun=False))
    ).job
    assert job.status == "completed"
    assert [output.kind for output in job.outputs] == ["replay_report"]
    assert job.outputs[0].artifact_id == f"{job.job_id}:replay-report.json"
    stages = [e.progress.stage for e in _events(app, job.job_id) if e.progress is not None]
    assert stages == ["integrity", "compare"]
    result = app.get_job_result(job.job_id)
    assert result.run_result is None and result.replay_report is not None
    assert (result.replay_report.mode, result.replay_report.verdict) == (
        "inspected_archived_results",
        "NOT_RUN",
    )
    assert schema_errors("job.schema.json#/$defs/job_result", result.as_document()) == []


def test_reproduce_composition_imports_and_reruns_to_match(
    app: LocalApplication, tmp_path: Path
) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    solved = _solve(app, revision_id, "to-import")
    # An outside copy with a symlink in it: the import copies regular files only.
    outside = tmp_path / "outside"
    shutil.copytree(_bundle_directory(app, solved), outside)
    (outside / "link.json").symlink_to(outside / "run-manifest.json")
    report = app.reproduce(outside, ReplayPolicy(rerun=True))
    assert report.verdict == "MATCH"
    imported = app.store.artifact("import-000001:bundle")
    assert imported is not None and imported.kind == "replay_bundle" and imported.job_id is None
    assert not (app.files_root / imported.relpath / "link.json").exists()
    members = {row.name: row.kind for row in app.store.artifact_children("import-000001:bundle")}
    assert members["solution-state.json"] == "solution_state"
    assert members["run-manifest.json"] == "run_manifest"
    (job,) = [job for job in app.list_jobs().items if job.operation == "reproduce"]
    assert [output.kind for output in job.outputs] == ["replay_bundle", "replay_report"]
    assert job.outputs[0].artifact_id == f"{job.job_id}:rerun"
    stages = [e.progress.stage for e in _events(app, job.job_id) if e.progress is not None]
    assert stages == ["integrity", "rerun", "compare"]
    for bad, code in ((tmp_path / "missing", "not_found"), (tmp_path, "invalid_request")):
        with pytest.raises(ApplicationError) as raised:
            app.reproduce(bad, ReplayPolicy())
        assert raised.value.code == code


@pytest.mark.parametrize("interruption", ["cancelled", "timed_out"])
def test_a_reproduce_interrupted_during_its_reruns_verify_emits_no_certificate(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch, interruption: str
) -> None:
    """§8.1 (T07 review S2): the rerun's verify records no trace, so the interruption is first
    seen at `compare` — which used to register and emit the rerun's bundle, a VERIFIED
    certificate inside, before checking."""
    revision_id = commit(app, CORPUS[NOMINAL]())
    solved = _solve(app, revision_id, "to-interrupt")
    real = revision_run.verify_revision
    # The job captures the executor's clock at its start; the verify moves this one on.
    skew = [0.0]

    def interrupt_during_verify(*args: Any, **kwargs: Any) -> Any:
        verified = real(*args, **kwargs)
        if interruption == "cancelled":
            for job in app.list_jobs().items:
                if job.status == "running":
                    app.cancel_job(job.job_id)
        else:
            skew[0] = 1e12
        return verified

    monkeypatch.setattr(revision_run, "verify_revision", interrupt_during_verify)
    app.executor.clock = lambda: time.monotonic() + skew[0]
    try:
        job = app.submit_job(
            JobRequest(
                "reproduce",
                "interrupted",
                ReproduceBody(f"{solved.job_id}:bundle", rerun=True),
                budgets=Budgets(wall_time_s=1e6),
            )
        ).job
    finally:
        app.executor.clock = time.monotonic
    assert job.status == interruption
    assert job.ending is not None and job.ending.interruption == "cooperative"
    assert job.outputs == ()
    assert app.store.artifact(f"{job.job_id}:rerun") is None
    assert app.store.artifact_children(f"{job.job_id}:rerun") == []


def test_reproduce_admission(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    solved = _solve(app, revision_id, "for-admission")
    for artifact_id, code in (
        ("import-000009:bundle", "not_found"),
        (f"{solved.job_id}:bundle/run-manifest.json", "invalid_request"),
    ):
        with pytest.raises(ApplicationError) as raised:
            app.submit_job(JobRequest("reproduce", f"r-{code}", ReproduceBody(artifact_id)))
        assert raised.value.code == code


# -- F4: `read` covers every principal's jobs (V17 spec) ---------------------------------------


def test_read_covers_every_principals_jobs(app: LocalApplication) -> None:
    directory = app.store.directory
    assert directory is not None
    revision_id = commit(app, CORPUS[NOMINAL]())
    owned = _solve(app, revision_id, "owners")
    capability, _ = grant(directory, principal_id="reader", rights=("read",))
    with LocalApplication.open(directory, capability=capability) as reader:
        assert reader.get_job(owned.job_id) == app.get_job(owned.job_id)
        assert [job.job_id for job in reader.list_jobs().items] == [owned.job_id]
        assert reader.list_job_events(owned.job_id).items == tuple(_events(app, owned.job_id))
        assert reader.wait_job(owned.job_id, timeout_s=0).ended
        assert reader.get_job_result(owned.job_id) == app.get_job_result(owned.job_id)
        for call in (
            lambda: reader.submit_job(JobRequest("solve", "r", SolveBody(revision_id))),
            lambda: reader.cancel_job(owned.job_id),
            lambda: reader.solve(revision_id, "default"),
        ):
            with pytest.raises(ApplicationError) as raised:
                call()
            assert raised.value.code == "forbidden"
    executor, _ = grant(directory, principal_id="agent", rights=("execute", "read"))
    with LocalApplication.open(directory, capability=executor) as agent:
        # `execute` cancels only the caller's own jobs; another's needs `policy` too (§10.1).
        with pytest.raises(ApplicationError) as raised:
            agent.cancel_job(owned.job_id)
        assert raised.value.code == "forbidden"
        mine = agent.submit_job(JobRequest("solve", "agent-1", SolveBody(revision_id))).job
        assert (mine.principal_id, mine.capability_id) == ("agent", executor.capability_id)
        assert agent.cancel_job(mine.job_id) == mine  # ended: a no-op, never an error
        assert lifecycle_violations(agent) == {}


def test_the_job_records_the_project_policy_at_acceptance(app: LocalApplication) -> None:
    revision_id = commit(app, CORPUS[NOMINAL]())
    job = _solve(app, revision_id, "policy")
    assert job.policy_sha256 == app.policy.policy_sha256


def test_the_in_memory_project_keeps_its_files_until_close() -> None:
    application = LocalApplication.in_memory()
    revision_id = commit(application, CORPUS[NOMINAL]())
    result = application.solve(revision_id, "default")
    root = application.files_root
    assert (root / "jobs" / result.job_id / "bundle" / "run-manifest.json").is_file()
    application.close()
    assert not os.path.exists(root)
