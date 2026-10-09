"""M04 WO-7 in a project: the binder resolves a surrogate's manifest from the project's own
artifact store (spec §8.2; ADR 0037 D2), and a surrogate-bound revision validates, routes and
solves on `revision_eo` with no experiment (spec §8.1; M04.A26's route and attempt clauses).

The surrogate is the stand-in's prefix study, run here through the `surrogate_study` job (the
registered parent a project can study; A16's case). The band and Q0–Q7 values of A26 proper are
the A19 surrogate's, asserted at the revision level in `test_m04_wo7_surrogate_unit.py`: the
smooth parent is test-only and cannot be studied in a project.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_jobs_support import commit, lifecycle_violations, response_schema_violations
from test_m04_study_job import attempts, body, read, submit

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.canonical import document_sha256
from openflowsheet.studies.surrogate import reactor as sr
from openflowsheet.studies.surrogate.manifest import Q0

LOOP_PATH: Path = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project")
    try:
        yield application
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []
    finally:
        application.close()


def surrogate_loop(surrogate_id: str, sha256: str) -> dict[str, Any]:
    """M02's stand-in loop with its reactor bound to the surrogate `sha256`."""
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    (reactor,) = (i for i in document["instances"] if i["id"] == "reactor")
    reactor["model"] = {"id": sr.MODEL_ID, "version": surrogate_id, "artifact_ref": sha256}
    return document


def studied(app: LocalApplication) -> tuple[dict[str, Any], str]:
    """The stand-in's prefix study through the job: its manifest and that manifest's SHA-256."""
    job = submit(app, "standin", body())["job"]
    assert job["status"] == "completed", job["error"]
    output = job["outputs"][0]
    assert output["kind"] == "surrogate_manifest"
    manifest = read(app, output["artifact_id"])
    assert document_sha256(manifest) == output["sha256"]
    return manifest, str(output["sha256"])


def test_a_surrogate_revision_resolves_from_the_project_and_solves_on_revision_eo(
    app: LocalApplication,
) -> None:
    manifest, sha256 = studied(app)
    revision_id = commit(app, surrogate_loop(manifest["surrogate_id"], sha256))
    before = attempts(app)
    assert len(before) == 199  # the study's own experiments

    assert app.validate(revision_id, "simulation").status == "READY_FOR_SIMULATION"
    structure = app.inspect_structure(revision_id).value
    assert structure["solve_path"] == "revision_eo" and structure["route_reason"] is None

    run = app.solve(revision_id, "default")
    assert (run.job_status, run.outcome, run.solve_path) == (
        "completed",
        "CONVERGED",
        "revision_eo",
    )
    assert run.verification_status == "VERIFIED"
    # M04.A26: zero experiment attempts — the solve wrote no experiment record.
    assert attempts(app) == before

    (output,) = (o for o in run.outputs if o.kind == "solution_certificate")
    certificate = read(app, output.artifact_id)
    (check,) = (c for c in certificate["checks"] if c["id"] == "SURROGATE-DOMAIN:reactor")
    assert (check["category"], check["result"], check["tolerance"]) == (
        "bounds_and_domain",
        "pass",
        None,
    )
    (model,) = (item for item in certificate["limitations"] if item["kind"] == "surrogate_model")
    assert model["unit"] == "reactor"
    assert (model["surrogate_id"], model["manifest_sha256"]) == (manifest["surrogate_id"], sha256)
    assert model["qualifications"] == manifest["qualifications"]
    assert model["qualifications"][0] == Q0 and len(model["qualifications"]) == 8
    q_hat = manifest["calibration"]["q_hat"]
    scales = manifest["score"]["scales"]
    assert model["band"] == {"X": q_hat * scales["X"], "dT_K": q_hat * scales["dT_K"]}


def test_without_the_manifest_in_the_project_the_revision_is_unsupported(
    app: LocalApplication, tmp_path: Path
) -> None:
    """Spec §8.2: a hash the project's artifact store does not hold is
    `surrogate_manifest_mismatch(<instance>)`: not READY, and a solve is refused at admission
    `revision_unsupported`."""
    other = LocalApplication.create(tmp_path / "studied")
    try:
        manifest, sha256 = studied(other)
    finally:
        other.close()
    revision_id = commit(app, surrogate_loop(manifest["surrogate_id"], sha256))
    report = app.validate(revision_id, "simulation")
    assert report.status != "READY_FOR_SIMULATION"
    assert "surrogate_manifest_mismatch(reactor)" in json.dumps(report.as_document())
    with pytest.raises(ApplicationError) as refused:
        app.solve(revision_id, "default")
    assert refused.value.code == "revision_not_ready"
