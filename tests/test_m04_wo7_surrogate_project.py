"""M04 WO-7 in a project: a surrogate's manifest resolves from the project's own artifact store
(spec §8.2; ADR 0037 D2) or the revision is unsupported.

The surrogate is the stand-in's prefix study, run here through the `surrogate_study` job (the
registered parent a project can study; A16's case). It is NOT_PROMOTABLE, so since Amendment 3
(spec §20 A3.1, M04.A48) a first revision binding it is rejected; a promoted surrogate resolved
from a project's store, validated, routed and solved on `revision_eo` with no experiment (M04.A26)
is WO-9's (`test_m04_wo9_synthetic_loop.py`, the smooth parent registered for that module).
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
from openflowsheet.application.types import Change, Edit
from openflowsheet.canonical import document_sha256
from openflowsheet.studies.surrogate import reactor as sr
from openflowsheet.studies.surrogate.manifest import derived_verdict

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


def test_a48_a_first_revision_binding_the_standins_unpromoted_surrogate_is_rejected(
    app: LocalApplication,
) -> None:
    """M04.A48 (spec §20 A3.1, R-360) in the first revision: the stand-in's prefix surrogate
    resolves from the project's store but is NOT_PROMOTABLE, so it does not enter. (A promoted
    surrogate resolved from a project's store and solved on `revision_eo` with no experiment is
    WO-9's A25/A26, `test_m04_wo9_synthetic_loop.py`.)"""
    manifest, sha256 = studied(app)
    assert len(attempts(app)) == 199  # the study's own experiments
    assert derived_verdict(manifest).verdict == "NOT_PROMOTABLE"
    document = surrogate_loop(manifest["surrogate_id"], sha256)
    edits = tuple(Edit("set", (key,), value) for key, value in document.items())
    result = app.commit_change(Change(edits=edits), None, "first")
    assert result.status == "rejected" and result.error is not None
    assert result.error.code == "model_replacement_incompatible"
    assert result.error.detail["reason"] == "surrogate_not_promoted(reactor)"
    assert result.error.detail["cause"] == "verdict=NOT_PROMOTABLE"
    with app.store.reading() as connection:
        assert app.store.head(connection) is None


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
