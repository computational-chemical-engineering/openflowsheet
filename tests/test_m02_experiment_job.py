"""M02 WO-6, gate G5 (design note §3.5, §10.1; ADR 0033 D9; ADR 0019 Amendment 4): the
`experiment` job operation.

- An `ok` result, a deterministic refusal and a transient failure all end the job `completed`
  with §3.5's outputs: the request, the attempts and the result the job wrote (a transient
  outcome: no result); `get_job_result` answers with the `result`, or the last `attempt`.
- The same key and body is the same job (`replayed = true`), with no new attempt; a new key with
  the same body is a cache hit — one output, the hit's row, whose parent is the producing result
  — with no new attempt; a bypassed repeat writes one attempt and outputs the producing result.
- Admission: an `artifact_ref` one hex digit off is `invalid_request` at
  `/body/model/artifact_ref`, components in another order at `/body/inlet/components`, and
  neither creates a job.
- Every response about these jobs holds to its published schema, and every job's lifecycle is
  §6.3's (R4-G3); `max_workers = 2` with two jobs on one key executes it once (G4 (i), the job
  level).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_jobs_support import lifecycle_violations, response_schema_violations
from t07_process_support import set_executor, wait_ended

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.store import ExperimentStore
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.jobs.executor import ProcessExecutor
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.types import schema_errors
from openflowsheet.models.c1 import COMPONENTS

STANDIN = variants.registered_variant("standin-x025-v1")
REAL = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v1")
#: M01 spec §8.15's nominal composition at the nominal per-tube flow, over 1000 tubes.
NOMINAL_Y = (0.6975, 0.2325, 0.03, 0.017142857142857144, 0.022857142857142857)
TUBE_FLOW = 0.007146961299302104
N_TUBES = 1000.0
EXPERIMENT_KINDS = ("experiment_request", "experiment_attempt", "experiment_result")


def body(
    variant: variants.Variant = STANDIN,
    *,
    y: tuple[float, ...] = NOMINAL_Y,
    temperature: float = 673.15,
    n_tubes: float = N_TUBES,
    components: tuple[str, ...] = COMPONENTS,
    artifact_ref: str | None = None,
    cache: str = "use",
) -> dict[str, Any]:
    total = TUBE_FLOW * n_tubes
    return {
        "model": {
            "id": variant.model_id,
            "version": variant.variant_id,
            "artifact_ref": artifact_ref or variant.sha256,
        },
        "inlet": {
            "components": list(components),
            "n": [total * value for value in y],
            "T": temperature,
            "P": 1.0e7,
        },
        "n_tubes": n_tubes,
        "cache": cache,
    }


def submit(app: LocalApplication, key: str, document: dict[str, Any]) -> dict[str, Any]:
    request = {"operation": "experiment", "idempotency_key": key, "body": document}
    response: dict[str, Any] = dispatch(app, "submit_job", request)
    return response


def result_of(app: LocalApplication, job_id: str) -> dict[str, Any]:
    answer: dict[str, Any] = dispatch(app, "get_job_result", {"job_id": job_id})
    return answer


def records(app: LocalApplication) -> ExperimentStore:
    return ExperimentStore(app.files_root)


def kinds(job: dict[str, Any]) -> list[str]:
    return [output["kind"] for output in job["outputs"]]


def read(app: LocalApplication, artifact_id: str) -> dict[str, Any]:
    row = app.store.artifact(artifact_id)
    assert row is not None
    document: dict[str, Any] = json.loads((app.files_root / row.relpath).read_bytes())
    return document


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project")
    try:
        yield application
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []  # R4-G3
    finally:
        application.close()


# -- the three outcomes ---------------------------------------------------------------------------


def test_g5_an_ok_experiment_ends_completed_with_the_request_attempt_and_result(
    app: LocalApplication,
) -> None:
    job = submit(app, "ok", body())["job"]
    assert (job["status"], job["error"]) == ("completed", None)
    assert kinds(job) == list(EXPERIMENT_KINDS)
    answer = result_of(app, job["job_id"])
    assert (answer["operation"], answer["run_result"], answer["replay_report"]) == (
        "experiment",
        None,
        None,
    )
    result = answer["experiment"]
    assert schema_errors("experiment.schema.json#/$defs/result", result) == []
    assert result == read(app, job["outputs"][-1]["artifact_id"])
    assert (result["envelope"]["status"], result["produced_by"]["job_id"]) == ("ok", job["job_id"])
    assert result["provenance"]["variant_sha256"] == STANDIN.sha256
    request = read(app, job["outputs"][0]["artifact_id"])
    assert request["experiment_key"] == result["experiment_key"]
    assert request["inputs"]["n"] == body()["inlet"]["n"]  # copied exactly
    events = dispatch(app, "list_job_events", {"job_id": job["job_id"]})["items"]
    stages = [e["progress"]["stage"] for e in events if e["kind"] == "progress"]
    assert stages == ["resolve", "evaluate", "record"]


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        ({"y": (0.70, 0.235, 1e-10, 0.015, 0.05 - 1e-10)}, "unsupported", "nh3_below_trace"),
        ({"temperature": 800.0}, "out_of_domain", None),
    ],
)
def test_g5_a_refused_experiment_ends_completed_with_its_deterministic_result(
    app: LocalApplication, change: dict[str, Any], status: str, code: str | None
) -> None:
    job = submit(app, "refused", body(**change))["job"]
    assert (job["status"], job["error"]) == ("completed", None)
    assert kinds(job) == list(EXPERIMENT_KINDS)
    result = result_of(app, job["job_id"])["experiment"]
    assert result["outcome_class"] == "deterministic"
    assert result["envelope"]["status"] == status and result["envelope"]["outlet"] is None
    if code is not None:
        assert result["envelope"]["code"] == code
    (attempt,) = records(app).attempts(result["experiment_key"])
    assert attempt["execution"]["status"] == "not_executed"


def test_g5_a_transient_failure_ends_completed_with_its_attempt_and_no_result(
    app: LocalApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real variant with no environment built: the handshake is `environment_unavailable`,
    a transient outcome — an attempt, never a result, never outlet values."""
    monkeypatch.setenv("OPENFLOWSHEET_EXTERNAL_ROOT", str(tmp_path / "no-environments"))
    job = submit(app, "transient", body(REAL, n_tubes=1.0))["job"]
    assert (job["status"], job["error"]) == ("completed", None)
    assert kinds(job) == ["experiment_request", "experiment_attempt"]
    attempt = result_of(app, job["job_id"])["experiment"]
    assert schema_errors("experiment.schema.json#/$defs/attempt", attempt) == []
    assert attempt == read(app, job["outputs"][-1]["artifact_id"])
    execution = attempt["execution"]
    assert execution["status"] == "environment_unavailable"
    assert execution["tube_outlet"] is None and "pymrm.env build" in execution["message"]
    assert records(app).result(attempt["experiment_key"]) is None


# -- idempotency and the cache --------------------------------------------------------------------


def test_g5_the_same_key_and_body_is_the_same_job_with_no_new_attempt(
    app: LocalApplication,
) -> None:
    first = submit(app, "same", body())
    again = submit(app, "same", body())
    assert (first["replayed"], again["replayed"]) == (False, True)
    assert again["job"]["job_id"] == first["job"]["job_id"]
    key = result_of(app, first["job"]["job_id"])["experiment"]["experiment_key"]
    assert len(records(app).attempts(key)) == 1


def test_g5_a_new_key_with_the_same_body_is_a_cache_hit_with_no_new_attempt(
    app: LocalApplication,
) -> None:
    first = submit(app, "first", body())["job"]
    second = submit(app, "second", body())["job"]
    assert second["job_id"] != first["job_id"] and second["status"] == "completed"
    assert kinds(second) == ["experiment_result"]
    hit = app.store.artifact(second["outputs"][0]["artifact_id"])
    assert hit is not None and hit.job_id == second["job_id"]
    assert hit.parent_artifact_id == first["outputs"][-1]["artifact_id"]
    answer = result_of(app, second["job_id"])["experiment"]
    assert answer == result_of(app, first["job_id"])["experiment"]
    assert answer["produced_by"]["job_id"] == first["job_id"]
    assert len(records(app).attempts(answer["experiment_key"])) == 1


def test_g5_a_bypassed_repeat_writes_one_attempt_and_answers_with_the_result(
    app: LocalApplication,
) -> None:
    first = submit(app, "produce", body())["job"]
    repeat = submit(app, "repeat", body(cache="bypass"))["job"]
    assert kinds(repeat) == ["experiment_attempt", "experiment_result"]
    attempt = read(app, repeat["outputs"][0]["artifact_id"])
    assert (attempt["repeat_of"], attempt["repeat_bitwise_equal"]) == (1, True)
    assert repeat["outputs"][1]["artifact_id"] == first["outputs"][-1]["artifact_id"]
    answer = result_of(app, repeat["job_id"])["experiment"]
    assert answer["produced_by"]["job_id"] == first["job_id"]


# -- admission ------------------------------------------------------------------------------------


def _refused(app: LocalApplication, document: dict[str, Any]) -> dict[str, Any]:
    before = len(app.store.job_ids())
    with pytest.raises(ApplicationError) as raised:
        submit(app, "refused-at-admission", document)
    assert len(app.store.job_ids()) == before  # no job, no ledger row
    error: dict[str, Any] = raised.value.error.as_document()
    return error


def test_g5_a_mismatched_artifact_ref_is_refused_at_admission(app: LocalApplication) -> None:
    pinned = STANDIN.sha256
    off = pinned[:-1] + ("0" if pinned[-1] != "0" else "1")
    error = _refused(app, body(artifact_ref=off))
    assert error["code"] == "invalid_request"
    assert error["detail"]["pointer"] == "/body/model/artifact_ref"


def test_g5_another_model_or_version_is_refused_at_admission(app: LocalApplication) -> None:
    document = body()
    document["model"]["id"] = "c1.reactor"  # the stand-in's hash under the real model's id
    assert _refused(app, document)["detail"]["pointer"] == "/body/model/artifact_ref"


def test_g5_components_in_another_order_are_refused_at_admission(app: LocalApplication) -> None:
    swapped = (COMPONENTS[1], COMPONENTS[0], *COMPONENTS[2:])
    error = _refused(app, body(components=swapped))
    assert (error["code"], error["detail"]["pointer"]) == (
        "invalid_request",
        "/body/inlet/components",
    )


# -- G4 (i) at the job level ----------------------------------------------------------------------


def test_g4i_two_jobs_on_one_key_under_two_workers_execute_it_once(tmp_path: Path) -> None:
    directory = tmp_path / "project"
    LocalApplication.create(directory).close()
    set_executor(directory, max_workers=2)
    application = LocalApplication.open(directory, executor=ProcessExecutor())
    try:
        jobs = [submit(application, f"twin-{n}", body())["job"] for n in (1, 2)]
        ended = [wait_ended(application, job["job_id"]) for job in jobs]
        assert [job.status for job in ended] == ["completed", "completed"]
        answers = [result_of(application, job["job_id"])["experiment"] for job in jobs]
        key = answers[0]["experiment_key"]
        assert answers[1]["experiment_key"] == key
        attempts = records(application).attempts(key)
        assert [attempt["execution"]["status"] for attempt in attempts] == ["completed"]
        produced = {answer["produced_by"]["job_id"] for answer in answers}
        assert len(produced) == 1
        hits = [job for job in ended if [o.kind for o in job.outputs] == ["experiment_result"]]
        assert len(hits) == 1
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []
    finally:
        application.close()


# -- transport parity (R-096) ---------------------------------------------------------------------


@pytest.mark.parametrize("transport", ["python", "cli", "http", "mcp"])
def test_g5_an_experiment_over_every_transport_is_the_same_record(
    tmp_path: Path, transport: str
) -> None:
    """The same body submitted over each transport that carries `submit_job` ends `completed` with
    the same experiment key and envelope as the in-process call."""
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    import sys

    from t07_transport_support import (
        CliClient,
        Client,
        HttpClient,
        McpClient,
        PythonInline,
        ThreadStream,
    )

    from openflowsheet.application.authz import grant

    project = tmp_path / "project"
    LocalApplication.create(project).close()
    capability, token = grant(
        project, principal_id="agent-m02", rights=("execute", "read"), capability_id="cap-m02"
    )
    client: Client
    with pytest.MonkeyPatch.context() as patch:
        if transport == "cli":
            out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
            patch.setattr(sys, "stdout", out)
            patch.setattr(sys, "stderr", err)
            client = CliClient(project, tmp_path / "raw.bin", out, err)
        elif transport == "python":
            client = PythonInline(project)
        elif transport == "http":
            client = HttpClient(project, token)
        else:
            client = McpClient(project, capability)
        try:
            request = {"operation": "experiment", "idempotency_key": "parity", "body": body()}
            error, submitted = client.call("submit_job", request)
            assert not error, submitted
            job_id = submitted["job"]["job_id"]
            waited: dict[str, Any] = {"ended": False}
            while not waited["ended"]:
                error, waited = client.call("wait_job", {"job_id": job_id, "timeout_s": 30})
                assert not error, waited
            assert waited["job"]["status"] == "completed"
            error, answer = client.call("get_job_result", {"job_id": job_id})
            assert not error, answer
        finally:
            client.close()
    with LocalApplication.in_memory() as reference:
        expected = result_of(reference, submit(reference, "parity", body())["job"]["job_id"])
    result = answer["experiment"]
    assert result["experiment_key"] == expected["experiment"]["experiment_key"]
    assert result["envelope"] == expected["experiment"]["envelope"]


# -- R-252 (design note §14 B7): `experiment` is null iff the job wrote no experiment artifact ----


def test_r252_a_job_cancelled_while_queued_has_no_artifact_and_a_null_experiment(
    app: LocalApplication,
) -> None:
    from t07_jobs_support import cancel_while_queued

    from openflowsheet.application.types import JobRequest

    request = JobRequest.from_document(
        {"operation": "experiment", "idempotency_key": "queued", "body": body()}
    )
    _, cancelled = cancel_while_queued(app, request)
    assert (cancelled.status, cancelled.outputs) == ("cancelled", ())
    assert result_of(app, cancelled.job_id)["experiment"] is None


@pytest.mark.parametrize("variant", [STANDIN, REAL], ids=["ok", "transient"])
def test_r252_a_completed_job_has_an_experiment_artifact_and_a_non_null_experiment(
    app: LocalApplication,
    variant: variants.Variant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other direction: a `completed` experiment job wrote an experiment artifact, and its
    result's `experiment` is the record it answers with (the result, or the last attempt). The
    real variant with no environment built is the transient outcome (an attempt only)."""
    monkeypatch.setenv("OPENFLOWSHEET_EXTERNAL_ROOT", str(tmp_path / "no-environments"))
    job = submit(app, f"completed-{variant.variant_id}", body(variant, n_tubes=1.0))["job"]
    assert job["status"] == "completed"
    assert set(kinds(job)) & set(EXPERIMENT_KINDS)
    assert result_of(app, job["job_id"])["experiment"] is not None
